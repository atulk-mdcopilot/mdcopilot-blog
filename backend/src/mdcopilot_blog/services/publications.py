"""Version-bound publication rendering and human publication actions."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas_common import ActionAccepted, ArticleStateOut
from mdcopilot_blog.api.schemas_publishing import ExportBundleOut, IssueOut, PreviewOut, PublicationOut
from mdcopilot_blog.db.models import Article, ArticleSource, ArticleVersion, LedgerSource, Publication
from mdcopilot_blog.domain.contracts import BlogSource, SEOMetadata, SocialCopy, TitleOptions
from mdcopilot_blog.domain.enums import ArticleStatus, Permission, PublicationStatus
from mdcopilot_blog.domain.state_machine import Entity, InvalidTransition, require_transition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.publishing.base import Issue, PublishPayload
from mdcopilot_blog.publishing.factory import ensure_network_publishing, idempotency_key, network_publishing_active
from mdcopilot_blog.publishing.renderer import (
    PublishableCheck,
    compute_payload_hash,
    html_to_text,
    render_article_html,
    validate_publishable,
)
from mdcopilot_blog.services.article_status import set_article_status
from mdcopilot_blog.services.article_views import get_article
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.services.config import load_brand_profile, load_effective_config
from mdcopilot_blog.services.enqueue import enqueue_workflow, ensure_agent_enabled
from mdcopilot_blog.services.versions import effective_seo
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.names import QUEUE_INTERACTIVE, WORKFLOW_PUBLISH_ARTICLE

ARTICLE_ENTITY = "blog_article"


@dataclass(frozen=True)
class RenderedArticle:
    article_id: uuid.UUID
    version_id: uuid.UUID
    title: str
    slug: str | None
    excerpt: str
    html: str
    text: str
    seo: SEOMetadata | None
    social: SocialCopy | None
    tags: list[str]
    category: str
    references: list[BlogSource]
    disclosure: str
    issues: list[Issue]

    def to_payload(self, *, as_draft: bool, external_post_id: str | None = None) -> PublishPayload:
        if self.slug is None:
            raise ValueError("cannot build a payload without a slug")
        return PublishPayload(
            article_id=self.article_id,
            version_id=self.version_id,
            title=self.title,
            slug=self.slug,
            html=self.html,
            excerpt=self.excerpt,
            status="draft" if as_draft else "published",
            seo=self.seo.model_dump(mode="json") if self.seo else {},
            external_post_id=external_post_id,
        )

    def payload_hash(self) -> str:
        return compute_payload_hash(html=self.html, title=self.title, slug=self.slug or "", excerpt=self.excerpt)


async def render_version(
    db: AsyncSession,
    *,
    article: Article,
    version_id: uuid.UUID,
    references_override: Sequence[BlogSource] | None = None,
    disclosure_override: str | None = None,
) -> RenderedArticle:
    version = await db.get(ArticleVersion, version_id)
    if version is None or version.article_id != article.id:
        raise ProblemError(404, "Version not found", f"no version {version_id} for article {article.id}")
    row = await effective_seo(db, version_id=version_id)
    seo = SEOMetadata.model_validate(row.seo) if row else None
    social = SocialCopy.model_validate(row.social) if row and row.social else None
    if references_override is not None:
        refs = list(references_override)
    else:
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
    if disclosure_override is not None:
        disclosure = disclosure_override
    else:
        try:
            disclosure = (await load_brand_profile(db)).ai_disclosure
        except LookupError:
            disclosure = ""
    title = article.title or TitleOptions.model_validate(version.title_options).operational
    slug = article.slug or (seo.slug if seo else None)
    html = render_article_html(
        content_markdown=version.content_markdown, pull_quote=version.pull_quote, references=refs, disclosure=disclosure
    )
    issues = validate_publishable(
        PublishableCheck(title, slug, version.excerpt, html, version.content_markdown, seo, refs, disclosure)
    )
    return RenderedArticle(
        article.id,
        version.id,
        title,
        slug,
        version.excerpt,
        html,
        html_to_text(html),
        seo,
        social,
        list(article.tags),
        article.category,
        refs,
        disclosure,
        issues,
    )


async def preview_article(db: AsyncSession, *, article_id: uuid.UUID, version_id: uuid.UUID | None) -> PreviewOut:
    article = await get_article(db, article_id)
    vid = version_id or article.current_version_id
    if vid is None:
        raise ProblemError(404, "Version not found", "article has no current version")
    rendered = await render_version(db, article=article, version_id=vid)
    return PreviewOut(
        version_id=vid, html=rendered.html, issues=[IssueOut(field=i.field, message=i.message) for i in rendered.issues]
    )


async def export_locked(
    db: AsyncSession, *, article: Article, actor_user_id: uuid.UUID | None, trigger: str
) -> ExportBundleOut:
    vid = article.approved_version_id
    if article.status not in {"APPROVED", "SCHEDULED", "EXPORTED"} or vid is None:
        raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.EXPORTED)
    row = await db.scalar(
        select(Publication)
        .where(
            Publication.article_id == article.id,
            Publication.publisher == "manual_export",
            Publication.target == "manual",
        )
        .with_for_update()
    )
    if article.status == "EXPORTED" and row and row.version_id == vid and row.export_bundle:
        stored = ExportBundleOut.model_validate({**row.export_bundle, "html": "", "status": "EXPORTED"})
        r = await render_version(
            db,
            article=article,
            version_id=vid,
            references_override=stored.references,
            disclosure_override=stored.disclosure,
        )
        return stored.model_copy(update={"html": r.html})
    r = await render_version(db, article=article, version_id=vid)
    if r.issues:
        raise ProblemError(422, "Publish validation failed", [i.model_dump() for i in r.issues])
    assert r.slug is not None and r.seo is not None
    if row is None:
        row = Publication(
            id=uuid7(),
            article_id=article.id,
            version_id=vid,
            publisher="manual_export",
            target="manual",
            status="PENDING",
            idempotency_key=idempotency_key("manual_export", vid),
            payload_hash=r.payload_hash(),
            attempts=0,
            as_draft=False,
        )
        db.add(row)
    require_transition(Entity.PUBLICATION, row.status, PublicationStatus.EXPORTED)
    row.status, row.version_id, row.requested_by = "EXPORTED", vid, actor_user_id
    row.idempotency_key, row.payload_hash = idempotency_key("manual_export", vid), r.payload_hash()
    row.attempts += 1
    row.last_error = None
    bundle = ExportBundleOut(
        publication_id=row.id,
        article_id=article.id,
        version_id=vid,
        title=r.title,
        slug=r.slug,
        excerpt=r.excerpt,
        html=r.html,
        text=r.text,
        seo=r.seo,
        social=r.social,
        tags=r.tags,
        category=r.category,
        references=r.references,
        disclosure=r.disclosure,
        status=ArticleStatus.EXPORTED,
    )
    row.export_bundle = bundle.model_dump(mode="json", exclude={"html"})
    await set_article_status(db, article_id=article.id, target=ArticleStatus.EXPORTED)
    article.scheduled_for = None
    await audit(
        db,
        actor_user_id=actor_user_id,
        action="article.export",
        entity_type=ARTICLE_ENTITY,
        entity_id=str(article.id),
        details={"versionId": vid, "publicationId": row.id, "trigger": trigger},
    )
    await db.flush()
    return bundle


async def export_article(db: AsyncSession, *, article_id: uuid.UUID, principal: Principal) -> ExportBundleOut:
    result = await export_locked(
        db, article=await get_article(db, article_id, lock=True), actor_user_id=principal.user_id, trigger="api"
    )
    await db.commit()
    return result


async def confirm_published(
    db: AsyncSession, *, article_id: uuid.UUID, principal: Principal, url: str, now: datetime
) -> ArticleStateOut:
    article = await get_article(db, article_id, lock=True)
    if article.status != "EXPORTED":
        raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.PUBLISHED)
    row = await db.scalar(
        select(Publication)
        .where(
            Publication.article_id == article_id,
            Publication.publisher == "manual_export",
            Publication.version_id == article.approved_version_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ProblemError(409, "Invalid state transition", "no export record for the approved version")
    require_transition(Entity.PUBLICATION, row.status, PublicationStatus.CONFIRMED)
    row.status, row.published_url, row.published_at, row.confirmed_by = "CONFIRMED", url, now, principal.user_id
    await set_article_status(db, article_id=article_id, target=ArticleStatus.PUBLISHED)
    article.published_at, article.published_url, article.published_version_id = now, url, article.approved_version_id
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.confirm_published",
        entity_type=ARTICLE_ENTITY,
        entity_id=str(article_id),
        details={"url": url, "versionId": article.approved_version_id},
    )
    await db.commit()
    await db.refresh(article)
    return ArticleStateOut.model_validate(article)


async def list_publications(db: AsyncSession, article_id: uuid.UUID) -> list[PublicationOut]:
    await get_article(db, article_id)
    rows = await db.scalars(
        select(Publication)
        .where(Publication.article_id == article_id)
        .order_by(Publication.created_at.desc(), Publication.id.desc())
    )
    return [PublicationOut.model_validate(row) for row in rows]


async def request_publish(
    db: AsyncSession,
    *,
    article_id: uuid.UUID,
    principal: Principal,
    settings: Settings,
    client: WorkflowClient,
    as_draft: bool | None,
) -> ActionAccepted:
    config = await load_effective_config(db, settings)
    ensure_network_publishing(settings, config)
    ensure_agent_enabled(settings)
    article = await get_article(db, article_id, lock=True)
    if article.status not in {"APPROVED", "PUBLISH_FAILED"} or not article.approved_version_id:
        raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.PUBLISHING)
    if article.approval_mode == "draft" and as_draft is False:
        raise ProblemError(409, "Invalid state transition", "draft-only approval cannot publish publicly")
    draft = article.approval_mode == "draft" if as_draft is None else as_draft
    version_id, run_id, candidate_id = article.approved_version_id, article.run_id, article.candidate_id
    await db.commit()
    accepted = await enqueue_workflow(
        client,
        workflow_name=WORKFLOW_PUBLISH_ARTICLE,
        queue_name=QUEUE_INTERACTIVE,
        workflow_id=f"publish-{version_id}-{uuid7()}",
        args=(str(article_id), str(version_id), draft),
        timeout_seconds=settings.production_timeout_minutes * 60,
    )
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.publish",
        entity_type=ARTICLE_ENTITY,
        entity_id=str(article_id),
        details={"versionId": version_id, "workflowId": accepted.workflow_id, "asDraft": draft},
    )
    await db.commit()
    return ActionAccepted(
        workflow_id=accepted.workflow_id,
        workflow_name=accepted.workflow_name,
        queue=accepted.queue,
        run_id=run_id,
        article_id=article_id,
        candidate_id=candidate_id,
    )


async def schedule_article(
    db: AsyncSession, *, article_id: uuid.UUID, principal: Principal, settings: Settings, at: datetime | None
) -> ArticleStateOut:
    article = await get_article(db, article_id, lock=True)
    if at is None:
        if article.status != "SCHEDULED":
            raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.APPROVED)
        await set_article_status(db, article_id=article_id, target=ArticleStatus.APPROVED)
        article.scheduled_for, article.scheduled_by = None, None
    else:
        config = await load_effective_config(db, settings)
        if network_publishing_active(settings, config) and Permission.PUBLISH not in principal.permissions:
            raise ProblemError(403, "Forbidden", "missing permission blog.publish")
        if at <= datetime.now(UTC):
            raise ProblemError(422, "Schedule time must be in the future")
        if article.status != "APPROVED":
            raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.SCHEDULED)
        await set_article_status(db, article_id=article_id, target=ArticleStatus.SCHEDULED)
        article.scheduled_for, article.scheduled_by = at, principal.user_id
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.schedule" if at else "article.unschedule",
        entity_type=ARTICLE_ENTITY,
        entity_id=str(article_id),
        details={"at": at},
    )
    await db.commit()
    await db.refresh(article)
    return ArticleStateOut.model_validate(article)
