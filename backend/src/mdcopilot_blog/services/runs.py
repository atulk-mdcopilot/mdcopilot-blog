"""Run service: create, list, read and cancel user-visible runs (``blog_runs``).

The API never executes workflows. It records the run, commits, and only then enqueues the
workflow through the workflow client (``DBOSClient`` in production), so the worker can always
find the row it is handed.
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog import tracing
from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas import DraftOut, ManualRunRequest
from mdcopilot_blog.db.models import AgentRun, Article, BlogRun, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, RunStatus
from mdcopilot_blog.domain.state_machine import Entity, InvalidTransition, require_transition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_DISCOVER_TOPICS

logger = logging.getLogger(__name__)

ACTIVE_ATTEMPT_STATUSES = frozenset({AttemptStatus.ENQUEUED.value, AttemptStatus.RUNNING.value})
ERROR_MESSAGE_LIMIT = 500


def manual_workflow_id(run_id: uuid.UUID) -> str:
    return f"manual-{run_id}"


async def create_manual_run(
    db: AsyncSession,
    client: WorkflowClient,
    *,
    principal: Principal,
    request: ManualRunRequest,
    settings: Settings,
) -> BlogRun:
    if not settings.agent_enabled:
        raise ProblemError(409, "Agent disabled", "BLOG_AGENT_ENABLED is false, so new runs are rejected.")

    # Phase 1: the run's trace id is minted here (the backend sends no traceparent yet), then the blog.run span
    # covers the insert and the enqueue. The worker's stage spans join the same trace via blog_runs.trace_id.
    trace_id = new_trace_id()
    with tracing.run_root(
        trace_id=trace_id,
        user_id=principal.user_id,
        workflow_name=WORKFLOW_DISCOVER_TOPICS,
    ) as obs:
        run = BlogRun(
            status=RunStatus.QUEUED.value,
            params=request.model_dump(mode="json", exclude_none=True),
            trace_id=trace_id,
            created_by=principal.user_id,
        )
        db.add(run)
        await db.flush()
        workflow_id = manual_workflow_id(run.id)
        tracing.annotate(obs, run_id=str(run.id), dbos_workflow_id=workflow_id)
        await db.commit()

        try:
            await client.enqueue(
                workflow_name=WORKFLOW_DISCOVER_TOPICS,
                queue_name=QUEUE_PIPELINE,
                workflow_id=workflow_id,
                args=(str(run.id),),
                timeout_seconds=settings.discovery_timeout_minutes * 60,
            )
        except Exception as exc:
            logger.exception("enqueue failed", extra={"run_id": str(run.id), "workflow_id": workflow_id})
            # run_root's exit records the ProblemError class as the status; keep the real cause class too.
            tracing.annotate(obs, error_class=type(exc).__name__)
            require_transition(Entity.RUN, run.status, RunStatus.FAILED.value)
            run.status = RunStatus.FAILED.value
            run.finished_at = datetime.now(UTC)
            run.error = {"class": type(exc).__name__, "message": str(exc)[:ERROR_MESSAGE_LIMIT]}
            await db.commit()
            raise ProblemError(503, "Workflow service unavailable", f"run {run.id} was marked FAILED") from exc

        logger.info("manual run enqueued", extra={"run_id": str(run.id), "workflow_id": workflow_id})
    return run


async def list_runs(db: AsyncSession, *, limit: int, offset: int) -> tuple[list[BlogRun], int]:
    query = select(BlogRun)
    total = await db.scalar(select(func.count()).select_from(BlogRun))
    # id is a UUIDv7, so it breaks created_at ties in insertion order
    rows = await db.scalars(query.order_by(BlogRun.created_at.desc(), BlogRun.id.desc()).limit(limit).offset(offset))
    return list(rows.all()), int(total or 0)


async def get_run_detail(db: AsyncSession, run_id: uuid.UUID) -> tuple[BlogRun, list[AgentRun]] | None:
    run = await db.get(BlogRun, run_id)
    if run is None:
        return None
    steps = await db.scalars(
        select(AgentRun).where(AgentRun.run_id == run_id).order_by(AgentRun.created_at, AgentRun.dbos_step_id)
    )
    return run, list(steps.all())


async def cancel_run(db: AsyncSession, client: WorkflowClient, *, run: BlogRun) -> BlogRun:
    """Raises ``InvalidTransition`` for a run that is already terminal (CANCELLED included)."""
    if run.status == RunStatus.CANCELLED.value:
        raise InvalidTransition(Entity.RUN, run.status, RunStatus.CANCELLED.value)
    require_transition(Entity.RUN, run.status, RunStatus.CANCELLED.value)

    attempts = list(
        (await db.scalars(select(RunAttempt).where(RunAttempt.run_id == run.id).order_by(RunAttempt.attempt_no))).all()
    )
    active = [attempt for attempt in attempts if attempt.status in ACTIVE_ATTEMPT_STATUSES]
    workflow_ids = [attempt.dbos_workflow_id for attempt in active]
    first_workflow_id = manual_workflow_id(run.id)
    if run.status == RunStatus.QUEUED.value and all(a.dbos_workflow_id != first_workflow_id for a in attempts):
        # The worker writes the attempt row only when the workflow starts, so a run that is still
        # queued has no row for its first workflow yet. Cancel that workflow by its known id.
        workflow_ids.insert(0, first_workflow_id)

    try:
        for workflow_id in workflow_ids:
            await client.cancel(workflow_id)
    except Exception as exc:
        logger.exception("cancel failed", extra={"run_id": str(run.id)})
        raise ProblemError(503, "Workflow service unavailable", f"run {run.id} was not cancelled") from exc

    now = datetime.now(UTC)
    for attempt in active:
        attempt.status = AttemptStatus.CANCELLED.value
        attempt.finished_at = now
    run.status = RunStatus.CANCELLED.value
    run.finished_at = now
    await db.commit()
    return run


async def load_drafts(db: AsyncSession, run_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, DraftOut]:
    """Run id -> the draft saved to MDCopilot Blogs; runs whose draft has not been saved are absent."""
    articles = await db.scalars(
        select(Article).where(Article.run_id.in_(run_ids), Article.backend_blog_id.is_not(None))
    )
    return {
        article.run_id: DraftOut(
            blog_id=article.backend_blog_id,
            title=article.title or "",
            gates_passed=(article.draft_report or {}).get("gatesPassed", False),
            gate_problems=(article.draft_report or {}).get("gateProblems", []),
        )
        for article in articles
    }
