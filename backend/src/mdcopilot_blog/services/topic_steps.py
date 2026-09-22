"""Durable manual-topic intake and topic selection steps."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogRun, ContentPillar, Topic, TopicCandidateRecord
from mdcopilot_blog.services.config import pillar_for_date
from mdcopilot_blog.services.step_context import StepContext


class CandidateResult(BaseModel):
    candidate_id: uuid.UUID


class SelectResult(BaseModel):
    candidate_id: uuid.UUID | None
    topic_id: uuid.UUID | None


async def promote_candidate(db: AsyncSession, *, candidate_id: uuid.UUID) -> uuid.UUID:
    c = await db.get(TopicCandidateRecord, candidate_id, with_for_update=True)
    if c is None:
        raise LookupError(f"topic candidate {candidate_id} not found")
    existing = await db.scalar(select(Topic).where(Topic.candidate_id == c.id))
    if c.status == "SELECTED" and existing:
        return existing.id
    if c.status not in {"PASSED", "SELECTED"}:
        raise ValueError(f"candidate {candidate_id} is {c.status}; only PASSED can be selected")
    row = Topic(
        candidate_id=c.id,
        run_id=c.run_id,
        title=c.title,
        pillar_key=c.pillar_key,
        thesis=c.thesis,
        angle=c.angle,
        core_argument=c.core_argument,
    )
    c.status = "SELECTED"
    db.add(row)
    await db.flush()
    return row.id


async def select_topic(sc: StepContext, *, run_id: uuid.UUID) -> SelectResult:
    async with sc.sessionmaker() as db:
        # one manual candidate per run
        selected = await db.scalar(
            select(TopicCandidateRecord).where(
                TopicCandidateRecord.run_id == run_id, TopicCandidateRecord.status.in_(["PASSED", "SELECTED"])
            )
        )
        topic_id = await promote_candidate(db, candidate_id=selected.id) if selected else None
        await db.commit()
        return SelectResult(candidate_id=selected.id if selected else None, topic_id=topic_id)


async def create_manual_candidate(
    sc: StepContext, *, run_id: uuid.UUID, topic: str, audience: str | None
) -> CandidateResult:
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
                )
            )
        if row is None:
            key = await pillar_for_date(db, run.created_at.date()) or await db.scalar(
                select(ContentPillar.key)
                .where(ContentPillar.is_active.is_(True))
                .order_by(ContentPillar.sort_order)
                .limit(1)
            )
            if key is None:
                raise LookupError("no active content pillar")
            # A manual topic is accepted as typed: no novelty scoring, so it is PASSED at once.
            row = TopicCandidateRecord(
                run_id=run_id,
                title=topic.strip(),
                thesis=topic.strip(),
                core_argument=topic.strip(),
                hook="",
                why_now="",
                angle="",
                mdcopilot_connection="",
                target_audience=audience.strip() if audience and audience.strip() else sc.brand.target_audience,
                pillar_key=str(key),
                examples=[],
                status="PASSED",
                dbos_workflow_id=sc.call.dbos_workflow_id,
                dbos_step_id=sc.call.dbos_step_id,
            )
            db.add(row)
            await db.flush()
        candidate_id = row.id
        await db.commit()
    return CandidateResult(candidate_id=candidate_id)
