"""Run service: create, list, read and cancel user-visible runs (``app.blog_runs``).

The API never executes workflows. It records the run, commits, and only then enqueues the
workflow through the workflow client (``DBOSClient`` in production), so the worker can always
find the row it is handed.
"""

import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas import ManualRunRequest
from mdcopilot_blog.db.models import AgentRun, BlogRun, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, RunKind, RunStatus
from mdcopilot_blog.domain.state_machine import Entity, require_transition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_DISCOVER_TOPICS

logger = logging.getLogger(__name__)

RUN_ENTITY = "blog_run"
ACTIVE_ATTEMPT_STATUSES = frozenset({AttemptStatus.ENQUEUED.value, AttemptStatus.RUNNING.value})
ERROR_MESSAGE_LIMIT = 500


def manual_workflow_id(run_id: uuid.UUID) -> str:
    return f"manual-{run_id}"


def initial_workflow_id(run: BlogRun) -> str:
    """Workflow id of a run's first execution: ``manual-<run id>`` or ``daily-<run date>``."""
    if run.kind == RunKind.DAILY.value:
        return f"daily-{run.run_date.isoformat()}"
    return manual_workflow_id(run.id)


async def create_manual_run(
    db: AsyncSession,
    client: WorkflowClient,
    *,
    principal: Principal,
    request: ManualRunRequest,
    settings: Settings,
    today: date,
) -> BlogRun:
    if not settings.agent_enabled:
        raise ProblemError(409, "Agent disabled", "BLOG_AGENT_ENABLED is false, so new runs are rejected.")

    run = BlogRun(
        kind=RunKind.MANUAL.value,
        run_date=request.run_date or today,
        status=RunStatus.QUEUED.value,
        params=request.model_dump(mode="json", exclude_none=True),
        trace_id=new_trace_id(),
        created_by=principal.user_id,
    )
    db.add(run)
    await db.flush()
    workflow_id = manual_workflow_id(run.id)
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="run.create",
        entity_type=RUN_ENTITY,
        entity_id=str(run.id),
        details={"kind": run.kind, "run_date": run.run_date.isoformat(), "workflow_id": workflow_id},
    )
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
        require_transition(Entity.RUN, run.status, RunStatus.FAILED.value)
        run.status = RunStatus.FAILED.value
        run.finished_at = datetime.now(UTC)
        run.error = {"stage": "enqueue", "message": f"{type(exc).__name__}: {exc}"[:ERROR_MESSAGE_LIMIT]}
        await db.commit()
        raise ProblemError(503, "Workflow service unavailable", f"run {run.id} was marked FAILED") from exc

    logger.info("manual run enqueued", extra={"run_id": str(run.id), "workflow_id": workflow_id})
    return run


async def list_runs(
    db: AsyncSession, *, status: RunStatus | None, limit: int, offset: int
) -> tuple[list[BlogRun], int]:
    query = select(BlogRun)
    count_query = select(func.count()).select_from(BlogRun)
    if status is not None:
        query = query.where(BlogRun.status == status.value)
        count_query = count_query.where(BlogRun.status == status.value)
    total = await db.scalar(count_query)
    # id is a UUIDv7, so it breaks created_at ties in insertion order
    rows = await db.scalars(query.order_by(BlogRun.created_at.desc(), BlogRun.id.desc()).limit(limit).offset(offset))
    return list(rows.all()), int(total or 0)


async def get_run_detail(
    db: AsyncSession, run_id: uuid.UUID
) -> tuple[BlogRun, list[RunAttempt], list[AgentRun]] | None:
    run = await db.get(BlogRun, run_id)
    if run is None:
        return None
    attempts = await db.scalars(select(RunAttempt).where(RunAttempt.run_id == run_id).order_by(RunAttempt.attempt_no))
    steps = await db.scalars(
        select(AgentRun).where(AgentRun.run_id == run_id).order_by(AgentRun.created_at, AgentRun.dbos_step_id)
    )
    return run, list(attempts.all()), list(steps.all())


async def cancel_run(db: AsyncSession, client: WorkflowClient, *, run: BlogRun, principal: Principal) -> BlogRun:
    if run.status == RunStatus.CANCELLED.value:
        # Same-state transition: a no-op under the state machine rules. Nothing is left to cancel.
        return run
    require_transition(Entity.RUN, run.status, RunStatus.CANCELLED.value)
    previous_status = run.status

    attempts = list(
        (await db.scalars(select(RunAttempt).where(RunAttempt.run_id == run.id).order_by(RunAttempt.attempt_no))).all()
    )
    active = [attempt for attempt in attempts if attempt.status in ACTIVE_ATTEMPT_STATUSES]
    workflow_ids = [attempt.dbos_workflow_id for attempt in active]
    first_workflow_id = initial_workflow_id(run)
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
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="run.cancel",
        entity_type=RUN_ENTITY,
        entity_id=str(run.id),
        details={"from_status": previous_status, "workflow_ids": workflow_ids},
    )
    await db.commit()
    return run
