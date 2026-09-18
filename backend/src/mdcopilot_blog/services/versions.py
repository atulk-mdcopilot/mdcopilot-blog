"""Insert-only article versions and their explicit source bindings."""

import uuid
from collections.abc import Mapping, Sequence
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import Article, ArticleSource, ArticleVersion, ResearchPacketRecord, VersionSeo
from mdcopilot_blog.domain.article_assembly import VersionContent, build_version_content, resolve_packet_markers
from mdcopilot_blog.domain.contracts import ArticleSection, FindingResolution, TitleOptions
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.llm.gateway import CallContext


async def lock_article(db: AsyncSession, article_id: uuid.UUID) -> Article:
    row = await db.scalar(select(Article).where(Article.id == article_id).with_for_update())
    if row is None:
        raise LookupError(f"article {article_id} not found")
    return row


async def find_step[M: (ArticleVersion, ResearchPacketRecord, VersionSeo)](
    db: AsyncSession, model: type[M], call: CallContext
) -> M | None:
    if call.dbos_workflow_id is None or call.dbos_step_id is None:
        return None
    return cast(
        M | None,
        await db.scalar(
            select(model).where(
                model.dbos_workflow_id == call.dbos_workflow_id, model.dbos_step_id == call.dbos_step_id
            )
        ),
    )


async def latest_packet(db: AsyncSession, article_id: uuid.UUID) -> ResearchPacketRecord | None:
    return cast(
        ResearchPacketRecord | None,
        await db.scalar(
            select(ResearchPacketRecord)
            .where(ResearchPacketRecord.article_id == article_id)
            .order_by(ResearchPacketRecord.version.desc())
            .limit(1)
        ),
    )


def version_content(row: ArticleVersion) -> VersionContent:
    return build_version_content(
        title_options=TitleOptions.model_validate(row.title_options),
        sections=[ArticleSection.model_validate(s) for s in row.sections],
        pull_quote=row.pull_quote,
        cta=row.cta,
        excerpt=row.excerpt,
    )


async def save_version(
    db: AsyncSession,
    *,
    article: Article,
    content: VersionContent,
    packet: ResearchPacketRecord | None,
    parent_id: uuid.UUID | None,
    change_kind: str,
    change_scope: dict[str, Any],
    resolutions: Sequence[FindingResolution] = (),
    created_by: uuid.UUID | None = None,
    call: CallContext | None = None,
) -> ArticleVersion:
    if call:
        existing = await find_step(db, ArticleVersion, call)
        if existing:
            return existing
    if parent_id is not None:
        parent = await db.get(ArticleVersion, parent_id)
        if parent is None or parent.article_id != article.id:
            raise ValueError("parent version does not belong to this article")
    count = (
        await db.scalar(select(func.max(ArticleVersion.version_no)).where(ArticleVersion.article_id == article.id)) or 0
    )
    row = ArticleVersion(
        id=uuid7(),
        article_id=article.id,
        version_no=count + 1,
        parent_version_id=parent_id,
        change_kind=change_kind,
        change_scope=change_scope,
        title_options=content.title_options.model_dump(mode="json"),
        sections=[s.model_dump(mode="json") for s in content.sections],
        pull_quote=content.pull_quote,
        cta=content.cta,
        excerpt=content.excerpt,
        content_markdown=content.content_markdown,
        word_count=content.word_count,
        citation_markers=list(content.citation_markers),
        resolutions=[r.model_dump(mode="json") for r in resolutions],
        research_packet_id=packet.id if packet else None,
        created_by=created_by,
        created_by_kind="human" if created_by else "agent",
        dbos_workflow_id=call.dbos_workflow_id if call else None,
        dbos_step_id=call.dbos_step_id if call else None,
    )
    db.add(row)
    await db.flush()
    source_ids = [uuid.UUID(value) for value in packet.source_ids] if packet else []
    markers = resolve_packet_markers(content.citation_markers, source_ids)
    primary = set(packet.packet.get("primaryMarkers", [])) if packet else set()
    for marker, source_id in markers.items():
        db.add(
            ArticleSource(
                id=uuid7(), version_id=row.id, source_id=source_id, marker=marker, is_primary=marker in primary
            )
        )
    article.current_version_id = row.id
    if count == 0:
        article.selected_title_key = "operational"
    if article.selected_title_key in {"provocative", "operational", "visionary"}:
        article.title = getattr(content.title_options, article.selected_title_key)
    await db.flush()
    return row


def version_chain(parents: Mapping[uuid.UUID, uuid.UUID | None], current_id: uuid.UUID | None) -> list[uuid.UUID]:
    """``current_id`` first, then its ancestors; stops at None, an unknown id, or a cycle."""
    chain: list[uuid.UUID] = []
    visited: set[uuid.UUID] = set()
    node = current_id
    while node is not None and node in parents and node not in visited:
        visited.add(node)
        chain.append(node)
        node = parents[node]
    return chain


async def effective_seo(db: AsyncSession, *, version_id: uuid.UUID) -> VersionSeo | None:
    """The newest SEO row of the version, else of its nearest ancestor that has one."""
    current: uuid.UUID | None = version_id
    visited: set[uuid.UUID] = set()
    while current is not None and current not in visited:
        visited.add(current)
        seo = (
            (
                await db.execute(
                    select(VersionSeo)
                    .where(VersionSeo.version_id == current)
                    .order_by(VersionSeo.created_at.desc(), VersionSeo.id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if seo is not None:
            return seo
        parent_id = (
            await db.execute(select(ArticleVersion.parent_version_id).where(ArticleVersion.id == current))
        ).scalar_one_or_none()
        current = parent_id
    return None
