"""Topic projections and audited human selections with enqueue compensation."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas import Page
from mdcopilot_blog.api.schemas_common import ActionAccepted
from mdcopilot_blog.api.schemas_topics import (
    ExternalPostOut,
    TopicCandidateOut,
    TopicHistoryOut,
    TopicRoundOut,
    TopicUpdate,
)
from mdcopilot_blog.db.models import (
    Article,
    BlogRun,
    ExternalPost,
    LedgerSource,
    Topic,
    TopicCandidateRecord,
)
from mdcopilot_blog.domain.enums import CandidateStatus
from mdcopilot_blog.domain.novelty import APPROVED_OR_LATER_STATUSES, NON_LIVE_ARTICLE_STATUSES, round_shortfall
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.services.config import load_effective_config
from mdcopilot_blog.services.enqueue import enqueue_workflow, ensure_agent_enabled
from mdcopilot_blog.services.research_runs import to_source_ref
from mdcopilot_blog.services.topic_steps import promote_candidate
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient


async def to_candidate_out(db: AsyncSession, row: TopicCandidateRecord) -> TopicCandidateOut:
    await db.refresh(row)
    ids = [uuid.UUID(x) for x in row.source_ids]
    sources = {r.id: r for r in await db.scalars(select(LedgerSource).where(LedgerSource.id.in_(ids)))}
    article_id = await db.scalar(
        select(Article.id)
        .where(Article.candidate_id == row.id, Article.status.not_in(NON_LIVE_ARTICLE_STATUSES))
        .order_by(Article.created_at.desc())
        .limit(1)
    )
    values = {
        key: getattr(row, key)
        for key in TopicCandidateOut.model_fields
        if key not in {"pillar", "sources", "article_id"}
    }
    return TopicCandidateOut(
        **values,
        pillar=row.pillar_key,
        sources=[to_source_ref(sources[x], marker=f"S{i + 1}") for i, x in enumerate(ids) if x in sources],
        article_id=article_id,
    )


async def get_topic_round(
    db: AsyncSession,
    *,
    settings: Settings,
    run_id: uuid.UUID | None,
    round_no: int | None,
    status: CandidateStatus | None,
) -> TopicRoundOut:
    if run_id is None:
        run_id = await db.scalar(
            select(TopicCandidateRecord.run_id).order_by(TopicCandidateRecord.created_at.desc()).limit(1)
        )
    run = await db.get(BlogRun, run_id) if run_id else None
    if run is None:
        raise ProblemError(404, "Run not found", "no run with topic candidates")
    rounds = sorted(
        set((await db.scalars(select(TopicCandidateRecord.round).where(TopicCandidateRecord.run_id == run.id))).all())
    )
    current = round_no if round_no is not None else max(rounds, default=0)
    rows = (
        await db.scalars(
            select(TopicCandidateRecord)
            .where(TopicCandidateRecord.run_id == run.id, TopicCandidateRecord.round == current)
            .order_by(TopicCandidateRecord.position)
        )
    ).all()
    config = await load_effective_config(db, settings, run_id=run.id)
    shortfall = round_shortfall(
        statuses=[r.status for r in rows],
        round_no=current,
        max_regeneration_rounds=config.novelty.max_regeneration_rounds,
    )
    return TopicRoundOut(
        run_id=run.id,
        run_status=run.status,
        round=current,
        rounds_available=rounds,
        shortfall=shortfall,
        items=[await to_candidate_out(db, row) for row in rows if status is None or row.status == status.value],
    )


async def list_history(db: AsyncSession, *, q: str | None, limit: int, offset: int) -> Page[TopicHistoryOut]:
    stmt = select(Topic)
    if q and q.strip():
        stmt = stmt.where(Topic.title.icontains(q.strip(), autoescape=True))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = []
    for row in await db.scalars(stmt.order_by(Topic.created_at.desc(), Topic.id.desc()).limit(limit).offset(offset)):
        article = await db.scalar(
            select(Article).where(Article.topic_id == row.id).order_by(Article.created_at.desc()).limit(1)
        )
        values = {
            key: getattr(row, key)
            for key in TopicHistoryOut.model_fields
            if key not in {"pillar", "article_id", "article_status"}
        }
        items.append(
            TopicHistoryOut(
                **values,
                pillar=row.pillar_key,
                article_id=article.id if article else None,
                article_status=article.status if article else None,
            )
        )
    return Page(items=items, total=total or 0, limit=limit, offset=offset)


async def list_external_posts(db: AsyncSession, *, limit: int, offset: int) -> Page[ExternalPostOut]:
    total = await db.scalar(select(func.count()).select_from(ExternalPost))
    rows = await db.scalars(
        select(ExternalPost)
        .order_by(ExternalPost.published_at.desc().nullslast(), ExternalPost.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page(
        items=[ExternalPostOut.model_validate(row) for row in rows], total=total or 0, limit=limit, offset=offset
    )


async def _candidate(db: AsyncSession, candidate_id: uuid.UUID) -> TopicCandidateRecord:
    row = await db.get(TopicCandidateRecord, candidate_id, with_for_update=True)
    if row is None:
        raise ProblemError(404, "Topic not found", f"no topic with id {candidate_id}")
    return row


async def update_candidate(
    db: AsyncSession, *, candidate_id: uuid.UUID, update: TopicUpdate, principal: Principal
) -> TopicCandidateOut:
    row = await _candidate(db, candidate_id)
    if row.status in {"SELECTED", "SUPERSEDED"}:
        raise ProblemError(409, "Topic cannot be edited", f"candidate is {row.status}")
    for key, value in update.model_dump(mode="json", by_alias=False, exclude_unset=True).items():
        setattr(row, "pillar_key" if key == "pillar" else key, value)
    row.edited_by, row.edited_at = principal.user_id, datetime.now(UTC)
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="topic.update",
        entity_type="blog_topic_candidate",
        entity_id=str(row.id),
        details={"fields": sorted(update.model_fields_set)},
    )
    await db.commit()
    return await to_candidate_out(db, row)


async def reject_candidate(
    db: AsyncSession, *, candidate_id: uuid.UUID, reason: str, principal: Principal
) -> TopicCandidateOut:
    row = await _candidate(db, candidate_id)
    if row.status == "SELECTED":
        raise ProblemError(409, "Topic cannot be rejected", "candidate is SELECTED")
    previous = row.status
    row.status, row.rejected_reason = "DISMISSED", reason
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="topic.reject",
        entity_type="blog_topic_candidate",
        entity_id=str(row.id),
        reason=reason,
        details={"previous_status": previous},
    )
    await db.commit()
    return await to_candidate_out(db, row)


async def generate_topics(
    db: AsyncSession, client: WorkflowClient, *, run_id: uuid.UUID, principal: Principal, settings: Settings
) -> ActionAccepted:
    ensure_agent_enabled(settings)
    run = await db.get(BlogRun, run_id, with_for_update=True)
    if run is None:
        raise ProblemError(404, "Run not found", f"no run with id {run_id}")
    if run.status not in {"TOPICS_READY", "WAITING_FOR_TOPIC", "SUCCEEDED", "FAILED"}:
        raise ProblemError(409, "Topics cannot be regenerated", f"run is {run.status}")
    protected = await db.scalar(
        select(Article).where(Article.run_id == run.id, Article.status.in_(APPROVED_OR_LATER_STATUSES)).limit(1)
    )
    if protected:
        raise ProblemError(409, "Topics cannot be regenerated", f"article {protected.id} is {protected.status}")
    workflow_id = f"regen-topics-{run.id}-{uuid.uuid4()}"
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="topics.regenerate",
        entity_type="blog_run",
        entity_id=str(run.id),
        details={"workflow_id": workflow_id},
    )
    await db.commit()
    action = await enqueue_workflow(
        client,
        workflow_name="regenerate_topics",
        queue_name="interactive",
        workflow_id=workflow_id,
        args=(str(run.id),),
        timeout_seconds=settings.discovery_timeout_minutes * 60,
    )
    return ActionAccepted(
        workflow_id=action.workflow_id,
        workflow_name=action.workflow_name,
        queue=action.queue,
        run_id=run.id,
        article_id=None,
        candidate_id=None,
    )


async def select_candidate(
    db: AsyncSession,
    client: WorkflowClient,
    *,
    candidate_id: uuid.UUID,
    confirm_warning: bool,
    principal: Principal,
    settings: Settings,
) -> ActionAccepted:
    ensure_agent_enabled(settings)
    row = await _candidate(db, candidate_id)
    run = await db.get(BlogRun, row.run_id, with_for_update=True)
    if run is None:
        raise ProblemError(404, "Run not found")
    if run.status == "CANCELLED":
        raise ProblemError(409, "Topic cannot be selected", "run is CANCELLED")
    if row.status == "REJECTED":
        raise ProblemError(409, "Topic rejected by novelty")
    if row.status not in {"PASSED", "WARNED"}:
        raise ProblemError(409, "Topic cannot be selected", f"candidate is {row.status}")
    if row.status == "WARNED" and not confirm_warning:
        raise ProblemError(
            409,
            "Topic needs confirmation",
            f"candidate {row.id} has a novelty warning; resend with confirmWarning true",
        )
    live = (
        await db.scalars(
            select(Article)
            .where(Article.run_id == run.id, Article.status.not_in(NON_LIVE_ARTICLE_STATUSES))
            .order_by(Article.created_at.desc())
        )
    ).all()
    protected = next((a for a in live if a.status in APPROVED_OR_LATER_STATUSES), None)
    if protected:
        raise ProblemError(409, "Topic cannot be selected", f"article {protected.id} is {protected.status}")
    if live and live[0].status not in {"READY_FOR_REVIEW", "QUALITY_GATE_FAILED", "FAILED"}:
        raise ProblemError(409, "Topic cannot be selected", f"article {live[0].id} is {live[0].status}")
    selected = await db.scalar(
        select(TopicCandidateRecord.id)
        .where(TopicCandidateRecord.run_id == run.id, TopicCandidateRecord.status == "SELECTED")
        .limit(1)
    )
    if not live and selected:
        raise ProblemError(409, "Topic cannot be selected", "another selected topic is awaiting production")
    previous = row.status
    topic_id = await promote_candidate(db, candidate_id=row.id, selected_by=principal.user_id)
    name, queue = ("change_topic", "interactive") if live else ("produce_article", "pipeline")
    workflow_id = f"{'change-topic' if live else 'produce'}-{run.id}-{row.id}"
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="topic.select",
        entity_type="blog_topic_candidate",
        entity_id=str(row.id),
        details={"previous_status": previous, "confirm_warning": confirm_warning, "workflow_id": workflow_id},
    )
    await db.commit()
    try:
        action = await enqueue_workflow(
            client,
            workflow_name=name,
            queue_name=queue,
            workflow_id=workflow_id,
            args=(str(run.id), str(row.id)),
            timeout_seconds=settings.production_timeout_minutes * 60,
        )
    except ProblemError:
        row = await _candidate(db, candidate_id)
        article_exists = await db.scalar(select(Article.id).where(Article.topic_id == topic_id).limit(1))
        if article_exists is None:
            row.status, row.selected_at, row.selected_by = previous, None, None
            await db.execute(delete(Topic).where(Topic.id == topic_id))
            await audit(
                db,
                actor_user_id=principal.user_id,
                action="topic.select_reverted",
                entity_type="blog_topic_candidate",
                entity_id=str(row.id),
                details={"workflow_id": workflow_id},
            )
            await db.commit()
        raise
    return ActionAccepted(
        workflow_id=action.workflow_id,
        workflow_name=name,
        queue=queue,
        run_id=run.id,
        article_id=live[0].id if live else None,
        candidate_id=row.id,
    )
