"""Version-bound rendering of an article to publishable HTML."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import Article, ArticleSource, ArticleVersion, BlogRun, LedgerSource
from mdcopilot_blog.domain.contracts import BlogSource, GateReport, SEOMetadata, TitleOptions
from mdcopilot_blog.domain.enums import ArticleStatus
from mdcopilot_blog.publishing.backend_client import create_draft
from mdcopilot_blog.publishing.base import Issue
from mdcopilot_blog.publishing.renderer import (
    EXCERPT_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    PublishableCheck,
    render_article_html,
    validate_publishable,
)
from mdcopilot_blog.services.article_status import set_article_status
from mdcopilot_blog.services.config import load_brand_profile
from mdcopilot_blog.services.quality_steps import latest_review
from mdcopilot_blog.services.step_context import StepContext
from mdcopilot_blog.services.versions import effective_seo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderedArticle:
    article_id: uuid.UUID
    version_id: uuid.UUID
    title: str
    slug: str | None
    excerpt: str
    html: str
    issues: list[Issue]


async def render_version(db: AsyncSession, *, article: Article, version_id: uuid.UUID) -> RenderedArticle:
    version = await db.get(ArticleVersion, version_id)
    if version is None or version.article_id != article.id:
        raise LookupError(f"no version {version_id} for article {article.id}")
    row = await effective_seo(db, version_id=version_id)
    seo = SEOMetadata.model_validate(row.seo) if row else None
    sources = (
        await db.execute(
            select(ArticleSource, LedgerSource)
            .join(LedgerSource, LedgerSource.id == ArticleSource.source_id)
            .where(ArticleSource.version_id == version_id)
        )
    ).all()
    refs = [
        BlogSource(
            marker=link.marker,
            source_id=str(source.id),
            title=source.title,
            url=source.canonical_url,
            publisher=source.publisher,
            published_at=source.published_at,
        )
        for link, source in sources
    ]
    refs.sort(key=lambda r: (int(r.marker[1:]) if r.marker[1:].isdigit() else 999999, r.marker))
    try:
        disclosure = (await load_brand_profile(db)).ai_disclosure
    except LookupError:
        disclosure = ""
    title = article.title or TitleOptions.model_validate(version.title_options).operational
    slug = article.slug or (seo.slug if seo else None)
    excerpt = version.excerpt[:EXCERPT_MAX_LENGTH]
    html = render_article_html(
        content_markdown=version.content_markdown, pull_quote=version.pull_quote, references=refs, disclosure=disclosure
    )
    issues = validate_publishable(
        PublishableCheck(title, slug, excerpt, html, version.content_markdown, seo, refs, disclosure)
    )
    return RenderedArticle(article.id, version.id, title, slug, excerpt, html, issues)


async def save_draft(sc: StepContext, *, run_id: uuid.UUID, article_id: uuid.UUID, review_error: str | None) -> str:
    """Save the article's newest version to MDCopilot Blogs, at most once; return the backend blog id."""
    async with sc.sessionmaker() as db:
        article = await db.scalar(select(Article).where(Article.id == article_id).with_for_update())
        if article is None or article.current_version_id is None:
            raise LookupError(f"article {article_id} has no draft version to save")
        if article.backend_blog_id is not None:
            return article.backend_blog_id
        author_id = await db.scalar(select(BlogRun.created_by).where(BlogRun.id == run_id))
        if not author_id:
            raise ValueError(f"run {run_id} has no created_by, so the draft would have no author")
        rendered = await render_version(db, article=article, version_id=article.current_version_id)
        # What the backend would reject fails the step; every other issue travels with the draft as a problem.
        if not rendered.title.strip() or len(rendered.title) > TITLE_MAX_LENGTH or not rendered.html.strip():
            raise ValueError("the draft has no content, or its title is empty or longer than 200 characters")
        gate = await latest_review(db, article.current_version_id, "quality_gate")
        report = GateReport.model_validate(gate.payload) if gate else None
        problems = [
            f"{r.gate}: {r.details}"
            for r in (report.results if report else [])
            if r.severity == "blocking" and not r.passed
        ]
        problems += [issue.message for issue in rendered.issues if issue.field != "slug"]
        if review_error:
            problems.append(review_error)
        # ponytail: a crash between this POST and the commit below saves a second backend draft on retry; the
        # admin deletes the extra one. Upgrade path: an idempotency key on the ingest route.
        blog_id, _ = await create_draft(
            sc.settings,
            author_id=author_id,
            title=rendered.title,
            content=rendered.html,
            excerpt=rendered.excerpt,
            slug=None if any(issue.field == "slug" for issue in rendered.issues) else rendered.slug,
        )
        article.backend_blog_id = blog_id
        article.draft_report = {
            "gatesPassed": report is not None and report.passed and not problems,
            "gateProblems": problems,
        }
        await set_article_status(db, article_id=article.id, target=ArticleStatus.DRAFT_SAVED)
        await db.commit()
    logger.info("draft saved", extra={"article_id": str(article_id), "backend_blog_id": blog_id})
    return blog_id
