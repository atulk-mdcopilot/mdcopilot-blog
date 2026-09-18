"""Read models over article heads, immutable versions and review lineage."""

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.schemas import Page
from mdcopilot_blog.api.schemas_articles import (
    ArticleDetailOut,
    ArticleSourceOut,
    ArticleSummaryOut,
    FieldChangeOut,
    GateBadgeOut,
    ResearchPacketOut,
    VersionDetailOut,
    VersionDiffOut,
    VersionSummaryOut,
)
from mdcopilot_blog.api.schemas_common import SourceRefOut
from mdcopilot_blog.db.models import (
    Article,
    ArticleSource,
    ArticleVersion,
    BlogRun,
    LedgerSource,
    ResearchPacketRecord,
    Review,
    TopicCandidateRecord,
)
from mdcopilot_blog.domain.article_assembly import unified_markdown_diff
from mdcopilot_blog.domain.contracts import BlogSource, ClinicalReview, EditorialReview
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.quality_steps import latest_review, lineage_review
from mdcopilot_blog.services.versions import effective_seo
from mdcopilot_blog.settings import Settings

QUALITY_RUN_KINDS = ("full", "fix_pass", "recheck")
VIEW_STATUSES = {
    "drafts": {"DRAFTING", "FACT_CHECKING", "CLINICAL_REVIEW", "EDITORIAL_REVIEW", "SEO", "FAILED"},
    "review": {"READY_FOR_REVIEW", "QUALITY_GATE_FAILED"},
    "published": {"APPROVED", "SCHEDULED", "EXPORTED", "PUBLISHING", "PUBLISH_FAILED", "PUBLISHED"},
}


async def get_article(db: AsyncSession, article_id: uuid.UUID, *, lock: bool = False) -> Article:
    query = select(Article).where(Article.id == article_id)
    row = await db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise ProblemError(404, "Article not found", f"no article with id {article_id}")
    return row


async def get_version(db: AsyncSession, article_id: uuid.UUID, version_id: uuid.UUID | None) -> ArticleVersion:
    row = await db.get(ArticleVersion, version_id)
    if row is None or row.article_id != article_id:
        raise ProblemError(404, "Version not found", f"no version {version_id} for article {article_id}")
    return row


async def counting_gate(db: AsyncSession, version_id: uuid.UUID | None) -> Review | None:
    return cast(
        Review | None,
        await db.scalar(
            select(Review)
            .where(
                Review.version_id == version_id,
                Review.kind == "quality_gate",
                Review.gate_run_kind.in_(QUALITY_RUN_KINDS),
            )
            .order_by(Review.created_at.desc(), Review.id.desc())
            .limit(1)
        ),
    )


async def build_article_sources(
    db: AsyncSession, article: Article, version_id: uuid.UUID | None = None
) -> list[ArticleSourceOut]:
    target = version_id or article.current_version_id
    if target is None:
        return []
    await get_version(db, article.id, target)
    rows = (
        await db.execute(
            select(ArticleSource, LedgerSource)
            .join(LedgerSource, LedgerSource.id == ArticleSource.source_id)
            .where(ArticleSource.version_id == target)
        )
    ).all()
    rows = sorted(rows, key=lambda pair: int(pair[0].marker[1:]))
    return [
        ArticleSourceOut(
            marker=link.marker,
            source_id=source.id,
            title=source.title,
            url=source.url,
            canonical_url=source.canonical_url,
            publisher=source.publisher,
            domain=source.domain,
            tier=source.tier,
            published_at=source.published_at,
            date_source=source.date_source,
            access_mode=source.access_mode,
            is_primary=link.is_primary,
        )
        for link, source in rows
    ]


async def build_article_detail(
    db: AsyncSession, article: Article, settings: Settings | None = None
) -> ArticleDetailOut:
    from mdcopilot_blog.publishing.factory import network_publishing_active
    from mdcopilot_blog.services.config import load_effective_config
    from mdcopilot_blog.settings import get_settings

    settings = settings or get_settings()
    config = await load_effective_config(db, settings, run_id=article.run_id)
    version = await db.get(ArticleVersion, article.current_version_id) if article.current_version_id else None
    run = await db.get(BlogRun, article.run_id)
    if run is None:
        raise LookupError(f"run {article.run_id} not found")
    candidate = await db.get(TopicCandidateRecord, article.candidate_id)
    seo = await effective_seo(db, version_id=version.id) if version else None
    packet = (
        await db.get(ResearchPacketRecord, version.research_packet_id)
        if version and version.research_packet_id
        else None
    )
    fact = await latest_review(db, version.id, "fact_check") if version else None
    gate = await latest_review(db, version.id, "quality_gate") if version else None
    counted = await counting_gate(db, version.id) if version else None
    clinical, _ = await lineage_review(db, version, "clinical", ClinicalReview) if version else (None, None)
    editorial, _ = await lineage_review(db, version, "editorial", EditorialReview) if version else (None, None)
    sources = await build_article_sources(db, article)
    fields = {
        name: getattr(article, name)
        for name in (
            "id",
            "run_id",
            "run_date",
            "topic_id",
            "candidate_id",
            "selected_title_key",
            "slug",
            "category",
            "tags",
            "status",
            "current_version_id",
            "approved_version_id",
            "published_version_id",
            "approved_at",
            "approved_by",
            "approval_mode",
            "rejection_reason",
            "scheduled_for",
            "scheduled_by",
            "published_at",
            "published_url",
            "created_at",
            "updated_at",
        )
    }
    fields.update(
        {
            name: getattr(version, name) if version else None
            for name in ("title_options", "content_markdown", "sections", "excerpt", "pull_quote", "cta", "version_no")
        }
    )
    return ArticleDetailOut(
        **fields,
        selected_title=article.title,
        pillar=article.pillar_key,
        pipeline_status=run.status,
        seo=seo.seo if seo else None,
        social=seo.social if seo else None,
        sources=[
            BlogSource(
                marker=s.marker,
                source_id=str(s.source_id),
                title=s.title,
                url=s.url,
                publisher=s.publisher,
                published_at=s.published_at,
            )
            for s in sources
        ],
        research_summary=packet.summary if packet else None,
        research_packet_id=packet.id if packet else None,
        research_packet_version=packet.version if packet else None,
        fact_check=fact.payload if fact else None,
        clinical_review=clinical.payload if clinical else None,
        editorial_review=editorial.payload if editorial else None,
        quality_gates=gate.payload if gate else None,
        novelty=candidate.novelty if candidate else None,
        recheck_required=version is not None and fact is None,
        gates_passed_on_current_version=counted is not None and counted.verdict == "PASSED",
        network_publishing_active=network_publishing_active(settings, config),
        gate_override_policy=config.gate_override_policy,
    )


async def list_articles(
    db: AsyncSession,
    *,
    view: str = "all",
    statuses: Sequence[str] | None = None,
    pillar: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> Page[ArticleSummaryOut]:
    filters: list[ColumnElement[bool]] = []
    allowed = statuses or VIEW_STATUSES.get(view)
    if allowed:
        filters.append(Article.status.in_(allowed))
    if pillar:
        filters.append(Article.pillar_key == pillar)
    if q and q.strip():
        pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        filters.append(or_(Article.title.ilike(pattern, escape="\\"), Article.slug.ilike(pattern, escape="\\")))
    total = await db.scalar(select(func.count()).select_from(Article).where(*filters)) or 0
    rows = list(
        (
            await db.scalars(
                select(Article)
                .where(*filters)
                .order_by(Article.created_at.desc(), Article.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    items = []
    if rows:
        ids = [article.id for article in rows]
        runs = {
            run_id: status
            for run_id, status in (
                await db.execute(select(BlogRun.id, BlogRun.status).where(BlogRun.id.in_([a.run_id for a in rows])))
            ).all()
        }
        versions = {
            v.id: v for v in (await db.scalars(select(ArticleVersion).where(ArticleVersion.article_id.in_(ids)))).all()
        }
        reviews = list(
            (
                await db.scalars(
                    select(Review)
                    .where(Review.article_id.in_(ids))
                    .order_by(Review.created_at.desc(), Review.id.desc())
                )
            ).all()
        )
        for article in rows:
            version = versions.get(article.current_version_id) if article.current_version_id else None
            own = [r for r in reviews if r.article_id == article.id]
            fact = next((r for r in own if r.version_id == article.current_version_id and r.kind == "fact_check"), None)
            gate = next(
                (
                    r
                    for r in own
                    if r.version_id == article.current_version_id
                    and r.kind == "quality_gate"
                    and r.gate_run_kind in QUALITY_RUN_KINDS
                ),
                None,
            )
            from mdcopilot_blog.services.versions import version_chain

            chain = set(
                version_chain(
                    {v.id: v.parent_version_id for v in versions.values() if v.article_id == article.id},
                    article.current_version_id,
                )
            )
            editorial = next((r for r in own if r.kind == "editorial" and r.version_id in chain), None)
            fields = {
                name: getattr(article, name)
                for name in (
                    "id",
                    "run_id",
                    "run_date",
                    "title",
                    "slug",
                    "status",
                    "category",
                    "scheduled_for",
                    "published_at",
                    "published_url",
                    "created_at",
                    "updated_at",
                )
            }
            badge = GateBadgeOut(
                passed=gate.verdict == "PASSED" if gate else None,
                failed_gates=[
                    r["gate"] for r in gate.payload["results"] if not r["passed"] and r["severity"] == "blocking"
                ]
                if gate
                else [],
                recheck_required=version is not None and fact is None,
            )
            items.append(
                ArticleSummaryOut(
                    **fields,
                    pipeline_status=runs[article.run_id],
                    pillar=article.pillar_key,
                    current_version_no=version.version_no if version else None,
                    word_count=version.word_count if version else None,
                    gate_badge=badge,
                    fact_check_verdict=fact.verdict if fact else None,
                    independent_check=fact.independent_check if fact else None,
                    editorial_score=editorial.score if editorial else None,
                )
            )
    return Page[ArticleSummaryOut](items=items, total=total, limit=limit, offset=offset)


async def version_summary(db: AsyncSession, version: ArticleVersion) -> VersionSummaryOut:
    fact = await latest_review(db, version.id, "fact_check")
    gate = await counting_gate(db, version.id)
    return VersionSummaryOut(
        **{
            name: getattr(version, name)
            for name in (
                "id",
                "version_no",
                "parent_version_id",
                "change_kind",
                "change_scope",
                "word_count",
                "created_by",
                "created_by_kind",
                "created_at",
            )
        },
        fact_check_verdict=fact.verdict if fact else None,
        gates_passed=gate.verdict == "PASSED" if gate else None,
    )


async def build_version_detail(
    db: AsyncSession, article_id: uuid.UUID, version_id: uuid.UUID | None
) -> VersionDetailOut:
    await get_article(db, article_id)
    version = await get_version(db, article_id, version_id)
    summary = await version_summary(db, version)
    seo = await effective_seo(db, version_id=version.id)
    return VersionDetailOut(
        **summary.model_dump(),
        **{
            name: getattr(version, name)
            for name in (
                "title_options",
                "sections",
                "pull_quote",
                "cta",
                "excerpt",
                "content_markdown",
                "citation_markers",
                "resolutions",
                "research_packet_id",
            )
        },
        seo=seo.seo if seo else None,
        social=seo.social if seo else None,
    )


async def build_version_diff(
    db: AsyncSession, article_id: uuid.UUID, from_id: uuid.UUID, to_id: uuid.UUID
) -> VersionDiffOut:
    before = await build_version_detail(db, article_id, from_id)
    after = await build_version_detail(db, article_id, to_id)
    from mdcopilot_blog.domain.article_assembly import build_version_content, diff_fields, field_changes

    def fields(value: VersionDetailOut) -> dict[str, str | None]:
        content = build_version_content(
            title_options=value.title_options,
            sections=value.sections,
            pull_quote=value.pull_quote,
            cta=value.cta,
            excerpt=value.excerpt,
        )
        return diff_fields(content, value.seo)

    changes = [
        FieldChangeOut(field=key, from_value=old, to_value=new)
        for key, old, new in field_changes(fields(before), fields(after))
    ]
    return VersionDiffOut(
        from_version_id=from_id,
        to_version_id=to_id,
        from_version_no=before.version_no,
        to_version_no=after.version_no,
        unified_diff=unified_markdown_diff(
            before.content_markdown, after.content_markdown, before_no=before.version_no, after_no=after.version_no
        ),
        field_changes=changes,
    )


async def build_research_packets(db: AsyncSession, article_id: uuid.UUID) -> list[ResearchPacketOut]:
    await get_article(db, article_id)
    rows = (
        await db.scalars(
            select(ResearchPacketRecord)
            .where(ResearchPacketRecord.article_id == article_id)
            .order_by(ResearchPacketRecord.version.desc())
        )
    ).all()
    result = []
    for row in rows:
        sources = []
        for index, value in enumerate(row.source_ids, 1):
            source = await db.get(LedgerSource, uuid.UUID(value))
            if source:
                sources.append(
                    SourceRefOut(
                        id=source.id,
                        marker=f"S{index}",
                        **{
                            name: getattr(source, name)
                            for name in ("title", "url", "publisher", "domain", "tier", "published_at", "access_mode")
                        },
                    )
                )
        result.append(
            ResearchPacketOut(
                id=row.id,
                article_id=article_id,
                version=row.version,
                summary=row.summary,
                packet=row.packet,
                sources=sources,
                research_run_id=row.research_run_id,
                created_at=row.created_at,
            )
        )
    return result
