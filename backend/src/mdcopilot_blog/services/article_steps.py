"""Durable article seams: no workflow dependencies and no locks during model calls."""

import uuid
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.agents.common import number_sources
from mdcopilot_blog.agents.deep_research_analyst import run_deep_research_analyst
from mdcopilot_blog.agents.writer import check_draft, run_writer
from mdcopilot_blog.db.models import (
    Article,
    ArticleVersion,
    BlogRun,
    LedgerSource,
    ResearchPacketRecord,
    ResearchRun,
    RunAttempt,
    Topic,
    TopicCandidateRecord,
)
from mdcopilot_blog.domain.article_assembly import apply_component
from mdcopilot_blog.domain.contracts import AvoidBundle, ResearchPacket, RevisionFinding
from mdcopilot_blog.domain.enums import ArticleComponent, ChangeKind, SectionKey
from mdcopilot_blog.domain.errors import InsufficientEvidence
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.services import versions
from mdcopilot_blog.services.step_context import StepContext


class PacketResult(BaseModel):
    packet_id: uuid.UUID
    version: int


class VersionResult(BaseModel):
    version_id: uuid.UUID
    version_no: int
    word_count: int
    title_changed: bool


WRITABLE_STATUSES = frozenset(
    {
        "DRAFTING",
        "FACT_CHECKING",
        "CLINICAL_REVIEW",
        "EDITORIAL_REVIEW",
        "SEO",
        "READY_FOR_REVIEW",
        "QUALITY_GATE_FAILED",
    }
)


async def _ensure_writable(db: AsyncSession, article: Article, sc: StepContext, *, lock_attempt: bool = False) -> None:
    if article.status not in WRITABLE_STATUSES:
        raise ValueError(f"article {article.id} cannot be written while it is {article.status}")
    if sc.call.attempt_id is not None or sc.call.dbos_workflow_id is not None:
        query = (
            select(RunAttempt).where(RunAttempt.id == sc.call.attempt_id)
            if sc.call.attempt_id is not None
            else select(RunAttempt).where(RunAttempt.dbos_workflow_id == sc.call.dbos_workflow_id)
        )
        attempt = await db.scalar(query.with_for_update() if lock_attempt else query)
        if attempt is not None and attempt.status not in {"RUNNING", "ENQUEUED"}:
            raise ValueError(f"workflow attempt {attempt.id} is {attempt.status}; no article changes were saved")


async def ensure_article(sc: StepContext, *, run_id: uuid.UUID, candidate_id: uuid.UUID) -> uuid.UUID:
    async with sc.sessionmaker() as db:
        candidate = await db.scalar(
            select(TopicCandidateRecord).where(TopicCandidateRecord.id == candidate_id).with_for_update()
        )
        if candidate is None:
            raise LookupError(f"candidate {candidate_id} not found")
        if candidate.run_id != run_id:
            raise ValueError("candidate belongs to another run")
        article = await db.scalar(
            select(Article).where(
                Article.run_id == run_id,
                Article.candidate_id == candidate_id,
                Article.status.notin_(["REJECTED", "SUPERSEDED"]),
            )
        )
        if article:
            return article.id
        topic = await db.scalar(select(Topic).where(Topic.candidate_id == candidate_id))
        run = await db.get(BlogRun, run_id)
        if candidate.status != "SELECTED" or topic is None or run is None:
            raise ValueError("article requires a selected candidate with a promoted topic")
        article = Article(
            id=uuid7(),
            run_id=run_id,
            run_date=run.run_date,
            candidate_id=candidate_id,
            topic_id=topic.id,
            status="DRAFTING",
            pillar_key=topic.pillar_key,
            category=sc.config.default_category,
            tags=[],
        )
        db.add(article)
        await db.commit()
        return article.id


async def _brief(db: AsyncSession, article: Article) -> dict[str, Any]:
    candidate = await db.get(TopicCandidateRecord, article.candidate_id)
    if candidate is None:
        raise LookupError("article candidate not found")
    return {
        name: getattr(candidate, name)
        for name in (
            "title",
            "hook",
            "why_now",
            "thesis",
            "angle",
            "core_argument",
            "mdcopilot_connection",
            "target_audience",
            "pillar_key",
            "examples",
        )
    }


async def packet_sources(db: AsyncSession, packet: ResearchPacketRecord) -> list[LedgerSource]:
    result = []
    for value in packet.source_ids:
        source = await db.get(LedgerSource, uuid.UUID(value))
        if source is None:
            raise LookupError(f"packet source {value} not found")
        result.append(source)
    return result


async def build_research_packet(sc: StepContext, *, article_id: uuid.UUID, research_run_id: uuid.UUID) -> PacketResult:
    async with sc.sessionmaker() as db:
        existing = await versions.find_step(db, ResearchPacketRecord, sc.call)
        if existing:
            return PacketResult(packet_id=existing.id, version=existing.version)
        article = await db.get(Article, article_id)
        research = await db.get(ResearchRun, research_run_id)
        if article is None or research is None:
            raise LookupError("article or research run not found")
        if research.run_id != article.run_id:
            raise ValueError("research run belongs to another article run")
        sources = []
        for source_id in research.source_ids[:20]:
            source = await db.get(LedgerSource, uuid.UUID(source_id))
            if source is not None:
                sources.append(source)
        if not sources:
            raise InsufficientEvidence(str(research_run_id), 0, 1, 0)
        numbered = number_sources(sources, preserve_order=True)
        topic = await _brief(db, article)
    result = await run_deep_research_analyst(
        sc.gateway, ctx=sc.with_ids(article_id=article_id).call, config=sc.config, topic=topic, numbered=numbered
    )
    async with sc.sessionmaker() as db:
        await versions.lock_article(db, article_id)
        existing = await versions.find_step(db, ResearchPacketRecord, sc.call)
        if existing:
            return PacketResult(packet_id=existing.id, version=existing.version)
        number = (
            await db.scalar(
                select(func.max(ResearchPacketRecord.version)).where(ResearchPacketRecord.article_id == article_id)
            )
            or 0
        )
        record = ResearchPacketRecord(
            id=uuid7(),
            article_id=article_id,
            version=number + 1,
            research_run_id=research_run_id,
            packet=result.output.model_dump(mode="json"),
            summary=result.output.summary,
            source_ids=[str(n.source_id) for n in numbered],
            dbos_workflow_id=sc.call.dbos_workflow_id,
            dbos_step_id=sc.call.dbos_step_id,
        )
        db.add(record)
        await db.commit()
        return PacketResult(packet_id=record.id, version=record.version)


async def latest_packet_id(db: AsyncSession, *, article_id: uuid.UUID) -> uuid.UUID | None:
    row = await versions.latest_packet(db, article_id)
    return row.id if row else None


def _result(row: ArticleVersion, parent: ArticleVersion | None = None) -> VersionResult:
    return VersionResult(
        version_id=row.id,
        version_no=row.version_no,
        word_count=row.word_count,
        title_changed=parent is None or row.title_options != parent.title_options,
    )


async def _write(
    sc: StepContext,
    *,
    article_id: uuid.UUID,
    packet_id: uuid.UUID | None = None,
    base_version_id: uuid.UUID | None = None,
    avoid: AvoidBundle,
    instructions: str | None = None,
    findings: Sequence[RevisionFinding] = (),
    change_kind: ChangeKind | None = None,
    component: ArticleComponent | None = None,
    section_key: SectionKey | None = None,
) -> VersionResult:
    async with sc.sessionmaker() as db:
        existing = await versions.find_step(db, ArticleVersion, sc.call)
        if existing:
            return _result(existing)
        article = await db.get(Article, article_id)
        if article is None:
            raise LookupError(f"article {article_id} not found")
        await _ensure_writable(db, article, sc)
        if base_version_id and base_version_id != article.current_version_id:
            raise ValueError("base version is no longer current")
        parent_id = article.current_version_id
        parent = await db.get(ArticleVersion, parent_id) if parent_id else None
        packet = await db.get(ResearchPacketRecord, packet_id or (parent.research_packet_id if parent else None))
        if packet is None or packet.article_id != article_id:
            raise ValueError("article research packet not found")
        numbered = number_sources(await packet_sources(db, packet), preserve_order=True)
        topic = await _brief(db, article)
        base = versions.version_content(parent) if parent else None
        run = await db.get(BlogRun, article.run_id)
        tone = run.params.get("tone") if run else None
    result = await run_writer(
        sc.gateway,
        ctx=sc.with_ids(article_id=article_id).call,
        config=sc.config,
        brand=sc.brand,
        avoid=avoid,
        topic=topic,
        packet=ResearchPacket.model_validate(packet.packet),
        numbered=numbered,
        base=base if base_version_id else None,
        findings=findings,
        component=component,
        section_key=section_key,
        instructions=instructions,
        voice=tone if isinstance(tone, str) and tone.strip() else None,
    )
    if component and base is None:
        raise ValueError("component regeneration requires a base version")
    content = (
        apply_component(base, result.output) if component and base is not None else check_draft(result.output, numbered)
    )
    async with sc.sessionmaker() as db:
        article = await versions.lock_article(db, article_id)
        existing = await versions.find_step(db, ArticleVersion, sc.call)
        if existing:
            return _result(existing)
        await _ensure_writable(db, article, sc, lock_attempt=True)
        if article.current_version_id != parent_id:
            raise ValueError("article changed while the writer was running")
        kind = change_kind or (ChangeKind.DRAFT if parent is None else ChangeKind.ARTICLE_REGENERATION)
        row = await versions.save_version(
            db,
            article=article,
            content=content,
            packet=packet,
            parent_id=parent_id,
            change_kind=kind.value,
            change_scope={
                "component": component.value if component else None,
                "sectionKey": section_key.value if section_key else None,
                "instructions": instructions,
                "findingIds": [f.finding_id for f in findings],
            },
            resolutions=result.output.resolutions if not component else (),
            call=sc.call,
        )
        await db.commit()
        return _result(row, parent)


async def write_draft(
    sc: StepContext, *, article_id: uuid.UUID, packet_id: uuid.UUID, avoid: AvoidBundle, instructions: str | None = None
) -> VersionResult:
    return await _write(sc, article_id=article_id, packet_id=packet_id, avoid=avoid, instructions=instructions)


async def revise_article(
    sc: StepContext,
    *,
    article_id: uuid.UUID,
    base_version_id: uuid.UUID,
    findings: Sequence[RevisionFinding],
    avoid: AvoidBundle,
    change_kind: ChangeKind,
) -> VersionResult:
    if change_kind not in {ChangeKind.REVISION, ChangeKind.FIX_PASS} or not findings:
        raise ValueError("revision requires findings and change_kind revision or fix_pass")
    return await _write(
        sc,
        article_id=article_id,
        base_version_id=base_version_id,
        avoid=avoid,
        findings=findings,
        change_kind=change_kind,
    )


async def regenerate_component(
    sc: StepContext,
    *,
    article_id: uuid.UUID,
    base_version_id: uuid.UUID,
    component: ArticleComponent,
    section_key: SectionKey | None,
    instructions: str | None,
    avoid: AvoidBundle,
) -> VersionResult:
    if (
        component in {ArticleComponent.ARTICLE, ArticleComponent.RESEARCH}
        or (component == ArticleComponent.SECTION and section_key in {None, SectionKey.INTRODUCTION})
        or (component != ArticleComponent.SECTION and section_key is not None)
    ):
        raise ValueError("invalid component/section combination")
    return await _write(
        sc,
        article_id=article_id,
        base_version_id=base_version_id,
        avoid=avoid,
        component=component,
        section_key=section_key,
        instructions=instructions,
        change_kind=ChangeKind.COMPONENT_REGENERATION,
    )
