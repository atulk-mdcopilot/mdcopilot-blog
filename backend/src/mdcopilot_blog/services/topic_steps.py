"""Durable ideation, evidence scoring and topic selection steps."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.agents import topic_strategist as strategist
from mdcopilot_blog.agents.common import number_sources, resolve_markers
from mdcopilot_blog.db.models import (
    BlogRun,
    ContentPillar,
    DiscoveryTheme,
    ExternalPost,
    FindingSource,
    LedgerSource,
    ResearchFindingRecord,
    ResearchRun,
    Topic,
    TopicCandidateRecord,
)
from mdcopilot_blog.domain.contracts import NewsRef, NoveltyResult, PillarKey
from mdcopilot_blog.domain.diversity import extract_keywords
from mdcopilot_blog.domain.headlines import classify_headline
from mdcopilot_blog.domain.novelty import (
    assess_novelty,
    candidate_embedding_text,
    candidate_status,
    novelty_justification,
    novelty_score,
    round_shortfall,
)
from mdcopilot_blog.domain.scoring import RubricItem, ScoreInputs, score_candidate
from mdcopilot_blog.services.config import pillar_for_date
from mdcopilot_blog.services.novelty import candidate_signals
from mdcopilot_blog.services.step_context import StepContext


class IdeateResult(BaseModel):
    candidate_ids: list[uuid.UUID]
    round: int


class NoveltyScoreResult(BaseModel):
    passed_ids: list[uuid.UUID]
    warned_ids: list[uuid.UUID]
    rejected_ids: list[uuid.UUID]


class SelectResult(BaseModel):
    candidate_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    shortfall: bool


async def ideate_topics(
    sc: StepContext, *, research_run_id: uuid.UUID, round_no: int, avoid_candidate_ids: Sequence[uuid.UUID]
) -> IdeateResult:
    if round_no < 1:
        raise ValueError("round_no must be >= 1")
    async with sc.sessionmaker() as db:
        rr = await db.get(ResearchRun, research_run_id)
        if rr is None:
            raise LookupError(f"research run {research_run_id} not found")
        if sc.call.run_id is not None and rr.run_id != sc.call.run_id:
            raise ValueError("research run belongs to another run")
        if sc.call.dbos_workflow_id:
            existing = (
                await db.scalars(
                    select(TopicCandidateRecord)
                    .where(
                        TopicCandidateRecord.dbos_workflow_id == sc.call.dbos_workflow_id,
                        TopicCandidateRecord.dbos_step_id == sc.call.dbos_step_id,
                    )
                    .order_by(TopicCandidateRecord.position)
                )
            ).all()
            if len(existing) == 3:
                return IdeateResult(candidate_ids=[r.id for r in existing], round=round_no)
        by_id = {
            str(r.id): r
            for r in await db.scalars(
                select(LedgerSource).where(LedgerSource.id.in_([uuid.UUID(x) for x in rr.source_ids]))
            )
        }
        sources = [by_id[x] for x in rr.source_ids if x in by_id]
        if not sources:
            raise ValueError("research run has no ledger sources")
        numbered = number_sources(sources, preserve_order=True)
        marker_by_id = {source.id: f"S{i + 1}" for i, source in enumerate(sources)}
        findings = []
        for finding in await db.scalars(
            select(ResearchFindingRecord)
            .where(ResearchFindingRecord.research_run_id == rr.id)
            .order_by(ResearchFindingRecord.position)
        ):
            ids = (
                await db.scalars(select(FindingSource.source_id).where(FindingSource.finding_id == finding.id))
            ).all()
            findings.append(
                strategist.FindingBrief(
                    finding.claim,
                    finding.claim_type,
                    finding.importance,
                    finding.confidence,
                    tuple(marker_by_id[x] for x in ids if x in marker_by_id),
                )
            )
        pillars = [
            strategist.PillarBrief(p.key, p.name, p.description, tuple(p.topics))
            for p in await db.scalars(
                select(ContentPillar).where(ContentPillar.is_active.is_(True)).order_by(ContentPillar.sort_order)
            )
        ]
        if not pillars:
            raise LookupError("no active content pillar")
        run = await db.get(BlogRun, rr.run_id)
        if run is None:
            raise LookupError("run not found")
        target_key = run.params.get("pillar") or await pillar_for_date(db, run.run_date)
        target = next((p for p in pillars if p.key == target_key), pillars[0])
        avoid_rows = (
            await db.scalars(select(TopicCandidateRecord).where(TopicCandidateRecord.id.in_(avoid_candidate_ids)))
        ).all()
        history = (
            await db.scalars(
                select(Topic)
                .where(Topic.created_at >= sc.now() - timedelta(days=sc.config.novelty.lookback_days))
                .order_by(Topic.created_at.desc())
                .limit(30)
            )
        ).all()
        external = (
            await db.scalars(select(ExternalPost).order_by(ExternalPost.published_at.desc().nullslast()).limit(30))
        ).all()
        avoid = (
            [strategist.AvoidTopic(c.title, c.thesis) for c in avoid_rows]
            + [strategist.AvoidTopic(c.title, c.thesis) for c in history]
            + [strategist.AvoidTopic(p.title, p.excerpt) for p in external]
        )
        counts = {
            key: count
            for key, count in (
                (
                    await db.execute(
                        select(Topic.pillar_key, func.count())
                        .where(Topic.created_at >= sc.now() - timedelta(days=30))
                        .group_by(Topic.pillar_key)
                    )
                ).all()
            )
        }
        recent_scans = (
            await db.scalars(
                select(ResearchRun).where(
                    ResearchRun.kind == "broad",
                    ResearchRun.started_at >= sc.now() - timedelta(days=sc.config.diversity.lookback_days),
                )
            )
        ).all()
        theme_counts = {
            theme.key: sum(theme.key in scan.themes_covered for scan in recent_scans)
            for theme in await db.scalars(
                select(DiscoveryTheme)
                .where(DiscoveryTheme.is_active.is_(True))
                .order_by(DiscoveryTheme.sort_order, DiscoveryTheme.key)
            )
        }
    result = await strategist.run_topic_strategist(
        sc.gateway,
        ctx=sc.call,
        numbered=numbered,
        avoid=avoid,
        variables=strategist.build_variables(
            brand=sc.brand,
            target_pillar=target,
            pillars=pillars,
            pillar_counts=counts,
            theme_counts=theme_counts,
            avoid=avoid,
        ),
        user_prompt=strategist.build_user_prompt(
            round_no=round_no, target_pillar=target, findings=findings, numbered=numbered
        ),
        route_override=sc.config.routes["ideation"],
        prompt_version=sc.config.prompt_versions.get("ideation/topics"),
    )
    async with sc.sessionmaker() as db:
        await db.get(BlogRun, rr.run_id, with_for_update=True)
        if sc.call.dbos_workflow_id:
            existing = (
                await db.scalars(
                    select(TopicCandidateRecord)
                    .where(
                        TopicCandidateRecord.dbos_workflow_id == sc.call.dbos_workflow_id,
                        TopicCandidateRecord.dbos_step_id == sc.call.dbos_step_id,
                    )
                    .order_by(TopicCandidateRecord.position)
                )
            ).all()
            if len(existing) == 3:
                return IdeateResult(candidate_ids=[r.id for r in existing], round=round_no)
        await db.execute(
            update(TopicCandidateRecord)
            .where(
                TopicCandidateRecord.run_id == rr.run_id,
                TopicCandidateRecord.round < round_no,
                TopicCandidateRecord.status.in_(["PROPOSED", "PASSED", "WARNED", "REJECTED"]),
            )
            .values(status="SUPERSEDED")
        )
        ids = []
        for position, idea in enumerate(result.output.ideas):
            source_ids = list(dict.fromkeys(resolve_markers(idea.source_markers, numbered)))
            values = idea.model_dump(
                by_alias=False,
                exclude={
                    "pillar",
                    "source_markers",
                    "primary_marker",
                    "business_relevance",
                    "audience_relevance",
                    "editorial_potential",
                },
            )
            row = TopicCandidateRecord(
                **values,
                run_id=rr.run_id,
                research_run_id=rr.id,
                round=round_no,
                position=position,
                pillar_key=idea.pillar.value,
                source_ids=[str(x) for x in source_ids],
                primary_source_id=resolve_markers([idea.primary_marker], numbered)[0],
                relevant_news=[
                    NewsRef(
                        title=by_id[str(x)].title, url=by_id[str(x)].url, published_at=by_id[str(x)].published_at
                    ).model_dump(mode="json")
                    for x in source_ids
                ],
                rubric={
                    "businessRelevance": idea.business_relevance.model_dump(mode="json"),
                    "audienceRelevance": idea.audience_relevance.model_dump(mode="json"),
                    "editorialPotential": idea.editorial_potential.model_dump(mode="json"),
                },
                status="PROPOSED",
                is_manual=False,
                dbos_workflow_id=sc.call.dbos_workflow_id,
                dbos_step_id=sc.call.dbos_step_id,
            )
            db.add(row)
            await db.flush()
            ids.append(row.id)
        await db.commit()
    return IdeateResult(candidate_ids=ids, round=round_no)


async def check_novelty_and_score(sc: StepContext, *, candidate_ids: Sequence[uuid.UUID]) -> NoveltyScoreResult:
    result = NoveltyScoreResult(passed_ids=[], warned_ids=[], rejected_ids=[])
    async with sc.sessionmaker() as db:
        existing_ids = set(
            (await db.scalars(select(TopicCandidateRecord.id).where(TopicCandidateRecord.id.in_(candidate_ids)))).all()
        )
        if set(candidate_ids) - existing_ids:
            raise LookupError("topic candidate not found")
    for candidate_id in candidate_ids:
        async with sc.sessionmaker() as db:
            c = await db.get(TopicCandidateRecord, candidate_id)
            if c is None:
                raise LookupError("topic candidate not found")
            if c.status == "PROPOSED":
                if c.embedding is None or c.argument_embedding is None:
                    vectors = await sc.gateway.embed(
                        [
                            candidate_embedding_text(title=c.title, hook=c.hook, thesis=c.thesis, angle=c.angle),
                            c.core_argument.strip(),
                        ],
                        ctx=sc.with_ids(topic_candidate_id=c.id).call,
                    )
                    if len(vectors) != 2 or any(len(v) != 1536 for v in vectors):
                        raise ValueError("expected two embeddings with 1536 dimensions")
                    c.embedding, c.argument_embedding = vectors
                rows = (
                    await db.scalars(
                        select(LedgerSource).where(LedgerSource.id.in_([uuid.UUID(x) for x in c.source_ids]))
                    )
                ).all()
                primary = await db.get(LedgerSource, c.primary_source_id) if c.primary_source_id else None
                signals, neighbours = await candidate_signals(
                    db,
                    embedding=c.embedding,
                    argument_embedding=c.argument_embedding,
                    title=c.title,
                    primary_canonical_url=primary.canonical_url if primary else None,
                    examples=c.examples,
                    exclude_candidate_id=c.id,
                    config=sc.config.novelty,
                    now=sc.now(),
                )
                assessment = assess_novelty(signals, sc.config.novelty)
                rubric_values = {key: RubricItem(**value) for key, value in c.rubric.items()}
                card = score_candidate(
                    ScoreInputs(
                        newest_published_at=max((r.published_at for r in rows if r.published_at), default=None),
                        dated_sources=sum(r.published_at is not None for r in rows),
                        total_sources=len(rows),
                        tier12_sources=sum(r.tier <= 2 for r in rows),
                        primary_source_present=primary is not None,
                        novelty_score=novelty_score(assessment.max_similarity),
                        novelty_justification=novelty_justification(assessment),
                        business_relevance=rubric_values.get("businessRelevance"),
                        audience_relevance=rubric_values.get("audienceRelevance"),
                        editorial_potential=rubric_values.get("editorialPotential"),
                    ),
                    weights=sc.config.score_weights,
                    min_source_count=sc.config.research.min_source_count,
                    now=sc.now(),
                )
                c.novelty_score, c.evidence_score, c.timeliness_score = card.novelty, card.evidence, card.timeliness
                c.business_relevance, c.audience_relevance, c.editorial_potential = (
                    card.business_relevance,
                    card.audience_relevance,
                    card.editorial_potential,
                )
                c.total_score, c.score_breakdown = (
                    card.total,
                    {k: v.model_dump(mode="json") for k, v in card.breakdown.items()},
                )
                c.novelty_decision = assessment.decision.value
                c.novelty = NoveltyResult(
                    decision=assessment.decision, max_similarity=assessment.max_similarity, neighbours=neighbours
                ).model_dump(mode="json")
                c.status = candidate_status(assessment.decision, is_manual=c.is_manual).value
                await db.commit()
            if c.status in {"PASSED", "SELECTED"}:
                result.passed_ids.append(c.id)
            elif c.status == "WARNED":
                result.warned_ids.append(c.id)
            elif c.status == "REJECTED":
                result.rejected_ids.append(c.id)
    return result


async def promote_candidate(db: AsyncSession, *, candidate_id: uuid.UUID, selected_by: uuid.UUID | None) -> uuid.UUID:
    c = await db.get(TopicCandidateRecord, candidate_id, with_for_update=True)
    if c is None:
        raise LookupError(f"topic candidate {candidate_id} not found")
    existing = await db.scalar(select(Topic).where(Topic.candidate_id == c.id))
    if c.status == "SELECTED" and existing:
        return existing.id
    if c.status not in {"PASSED", "WARNED", "SELECTED"}:
        raise ValueError(f"candidate {candidate_id} is {c.status}; only PASSED or WARNED can be selected")
    if c.embedding is None or c.argument_embedding is None:
        raise ValueError("candidate has no embeddings")
    rows = (
        await db.scalars(select(LedgerSource).where(LedgerSource.id.in_([uuid.UUID(x) for x in c.source_ids])))
    ).all()
    primary = await db.get(LedgerSource, c.primary_source_id) if c.primary_source_id else None
    row = Topic(
        candidate_id=c.id,
        run_id=c.run_id,
        title=c.title,
        pillar_key=c.pillar_key,
        thesis=c.thesis,
        angle=c.angle,
        core_argument=c.core_argument,
        keywords=extract_keywords(f"{c.title}\n{c.thesis}\n{c.core_argument}", limit=10),
        examples=c.examples,
        headline_pattern=classify_headline(c.title).value,
        primary_source_url=primary.canonical_url if primary else None,
        source_domains=list(dict.fromkeys(r.domain for r in rows)),
        embedding=c.embedding,
        argument_embedding=c.argument_embedding,
    )
    if c.status != "SELECTED":
        c.status, c.selected_by, c.selected_at = "SELECTED", selected_by, datetime.now(UTC)
    db.add(row)
    await db.flush()
    return row.id


async def select_topic(sc: StepContext, *, run_id: uuid.UUID, mode: Literal["auto", "manual"]) -> SelectResult:
    async with sc.sessionmaker() as db:
        round_no = await db.scalar(
            select(func.max(TopicCandidateRecord.round)).where(TopicCandidateRecord.run_id == run_id)
        )
        if round_no is None:
            return SelectResult(candidate_id=None, topic_id=None, shortfall=False)
        rows = (
            await db.scalars(
                select(TopicCandidateRecord)
                .where(TopicCandidateRecord.run_id == run_id, TopicCandidateRecord.round == round_no)
                .order_by(TopicCandidateRecord.total_score.desc().nullslast(), TopicCandidateRecord.position)
            )
        ).all()
        shortfall = round_shortfall(
            statuses=[r.status for r in rows],
            round_no=round_no,
            max_regeneration_rounds=sc.config.novelty.max_regeneration_rounds,
        )
        selected = next((r for r in rows if r.status == "SELECTED"), None)
        selected = selected or next((r for r in rows if r.is_manual and r.status in {"PASSED", "WARNED"}), None)
        if selected is None and mode == "auto":
            selected = next((r for r in rows if r.status == "PASSED"), None)
        topic_id = await promote_candidate(db, candidate_id=selected.id, selected_by=None) if selected else None
        await db.commit()
        return SelectResult(candidate_id=selected.id if selected else None, topic_id=topic_id, shortfall=shortfall)


async def create_manual_candidate(
    sc: StepContext,
    *,
    run_id: uuid.UUID,
    topic: str,
    pillar_key: PillarKey | None,
    audience: str | None,
    tone: str | None,
) -> IdeateResult:
    if not 1 <= len(topic.strip()) <= 300:
        raise ValueError("manual topic must be 1..300 characters")
    async with sc.sessionmaker() as db:
        run = await db.get(BlogRun, run_id, with_for_update=True)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        row = None
        if sc.call.dbos_workflow_id:
            row = await db.scalar(
                select(TopicCandidateRecord).where(
                    TopicCandidateRecord.dbos_workflow_id == sc.call.dbos_workflow_id,
                    TopicCandidateRecord.dbos_step_id == sc.call.dbos_step_id,
                    TopicCandidateRecord.position == 0,
                )
            )
        if row is None:
            key = (
                pillar_key
                or await pillar_for_date(db, run.run_date)
                or await db.scalar(
                    select(ContentPillar.key)
                    .where(ContentPillar.is_active.is_(True))
                    .order_by(ContentPillar.sort_order)
                    .limit(1)
                )
            )
            if key is None:
                raise LookupError("no active content pillar")
            row = TopicCandidateRecord(
                run_id=run_id,
                research_run_id=None,
                round=1,
                position=0,
                title=topic.strip(),
                thesis=topic.strip(),
                core_argument=topic.strip(),
                hook="",
                why_now="",
                angle="",
                mdcopilot_connection="",
                target_audience=audience.strip() if audience and audience.strip() else sc.brand.target_audience,
                pillar_key=str(key),
                source_ids=[],
                relevant_news=[],
                examples=[],
                rubric={},
                status="PROPOSED",
                is_manual=True,
                dbos_workflow_id=sc.call.dbos_workflow_id,
                dbos_step_id=sc.call.dbos_step_id,
            )
            db.add(row)
            await db.flush()
        candidate_id = row.id
        await db.commit()
    await check_novelty_and_score(sc, candidate_ids=[candidate_id])
    return IdeateResult(candidate_ids=[candidate_id], round=1)
