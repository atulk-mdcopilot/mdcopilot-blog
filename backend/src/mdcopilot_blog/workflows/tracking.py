"""Run, attempt and step bookkeeping shared by every workflow.

- A run (blog_runs) is what the user sees. Every DBOS execution of it (original, fork) is an attempt
  (blog_run_attempts) keyed by dbos_workflow_id. Recovery re-uses the same workflow id, so it re-uses the attempt.
- Steps resolve their attempt from DBOS.workflow_id, never from inputs: fork_workflow copies earlier step outputs.
- Step rows (blog_agent_runs) are keyed by (dbos_workflow_id, dbos_step_id); a re-executed step bumps `tries`.
- Every write uses its own short session and commits immediately.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from dbos import DBOS
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import AgentRun, BlogRun, LlmCall, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, CallStatus, RunStatus, StepStatus
from mdcopilot_blog.domain.state_machine import Entity, require_transition
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.llm.gateway import CallContext
from mdcopilot_blog.workflows.names import HUMAN_ACTION_WORKFLOWS

type SessionMaker = async_sessionmaker[AsyncSession]

logger = logging.getLogger(__name__)

TERMINAL_RUN_STATUSES = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})
OPEN_ATTEMPT_STATUSES = (AttemptStatus.ENQUEUED.value, AttemptStatus.RUNNING.value)
MAX_ERROR_MESSAGE = 2000


def _now() -> datetime:
    return datetime.now(UTC)


def error_payload(exc: BaseException) -> dict[str, object]:
    return {"class": type(exc).__name__, "message": str(exc)[:MAX_ERROR_MESSAGE]}


async def get_run_status(sm: SessionMaker, run_id: uuid.UUID) -> RunStatus:
    async with sm() as session:
        status = await session.scalar(select(BlogRun.status).where(BlogRun.id == run_id))
    if status is None:
        raise LookupError(f"run {run_id} not found")
    return RunStatus(status)


async def get_run_trace_id(sm: SessionMaker, run_id: uuid.UUID) -> str:
    async with sm() as session:
        trace_id = await session.scalar(select(BlogRun.trace_id).where(BlogRun.id == run_id))
    if trace_id is None:
        raise LookupError(f"run {run_id} not found")
    return trace_id


async def get_attempt_status(sm: SessionMaker, workflow_id: str) -> AttemptStatus | None:
    async with sm() as session:
        status = await session.scalar(select(RunAttempt.status).where(RunAttempt.dbos_workflow_id == workflow_id))
    return None if status is None else AttemptStatus(status)


async def _attempt_id_for(session: AsyncSession, workflow_id: str) -> uuid.UUID | None:
    attempt_id: uuid.UUID | None = await session.scalar(
        select(RunAttempt.id).where(RunAttempt.dbos_workflow_id == workflow_id)
    )
    return attempt_id


async def ensure_attempt(
    sm: SessionMaker, *, run_id: uuid.UUID, workflow_id: str, workflow_name: str, respect_run_cancel: bool = True
) -> uuid.UUID:
    """Return the attempt for `workflow_id`, creating it on first use.

    A new attempt of a forked workflow re-opens a finished run (SUCCEEDED/FAILED/CANCELLED -> QUEUED),
    so the re-executed steps can move it forward again. An original attempt never re-opens a run:
    for a run cancelled before its workflow started, the attempt is recorded as CANCELLED at once.
    """
    async with sm() as session:
        found = await _attempt_id_for(session, workflow_id)
        if found is not None:
            attempt = await session.get(RunAttempt, found, with_for_update=True)
            if attempt is not None and attempt.status == AttemptStatus.ENQUEUED.value:
                attempt.status = AttemptStatus.RUNNING.value
                attempt.started_at = _now()
                attempt.start_step = DBOS.step_id
                await session.commit()
            return found

    statuses = await DBOS.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
    forked_from = statuses[0].forked_from if statuses else None

    async with sm() as session:
        run = await session.get(BlogRun, run_id, with_for_update=True)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        raced = await _attempt_id_for(session, workflow_id)
        if raced is not None:  # created concurrently while we waited for the run lock
            return raced
        count = await session.scalar(select(func.count()).select_from(RunAttempt).where(RunAttempt.run_id == run_id))
        now = _now()
        # the API cancelled the run while its workflow was still queued: nothing will ever close this attempt
        cancelled_before_start = respect_run_cancel and forked_from is None and run.status == RunStatus.CANCELLED
        attempt = RunAttempt(
            id=uuid7(),
            run_id=run_id,
            dbos_workflow_id=workflow_id,
            workflow_name=workflow_name,
            attempt_no=(count or 0) + 1,
            forked_from_workflow_id=forked_from,
            start_step=DBOS.step_id,
            status=(AttemptStatus.CANCELLED if cancelled_before_start else AttemptStatus.RUNNING).value,
            started_at=now,
            finished_at=now if cancelled_before_start else None,
        )
        session.add(attempt)
        if (
            forked_from is not None
            and workflow_name not in HUMAN_ACTION_WORKFLOWS
            and RunStatus(run.status) in TERMINAL_RUN_STATUSES
        ):
            require_transition(Entity.RUN, run.status, RunStatus.QUEUED)
            run.status = RunStatus.QUEUED.value
            run.finished_at = None
            run.error = None
        await session.commit()
        return attempt.id


async def finish_attempt(
    sm: SessionMaker, *, workflow_id: str, status: AttemptStatus, error: Mapping[str, object] | None = None
) -> None:
    """Close the attempt of `workflow_id`. No-op if it is missing or already closed (e.g. cancelled by the API)."""
    async with sm() as session:
        await session.execute(
            update(RunAttempt)
            .where(RunAttempt.dbos_workflow_id == workflow_id, RunAttempt.status.in_(OPEN_ATTEMPT_STATUSES))
            .values(status=status.value, finished_at=_now(), error=None if error is None else dict(error))
        )
        await session.commit()


async def set_run_status(
    sm: SessionMaker,
    *,
    run_id: uuid.UUID,
    target: RunStatus,
    stage: str | None = None,
    error: Mapping[str, object] | None = None,
) -> None:
    """Move a run through the state machine. Raises InvalidTransition (illegal move) or LookupError (no run)."""
    async with sm() as session:
        run = await session.get(BlogRun, run_id, with_for_update=True)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        if run.status == target:
            return
        require_transition(Entity.RUN, run.status, target)
        now = _now()
        run.status = target.value
        if stage is not None:
            run.stage = stage
        if error is not None:
            run.error = dict(error)
        if target is not RunStatus.QUEUED and run.started_at is None:
            run.started_at = now
        if target in TERMINAL_RUN_STATUSES:
            run.finished_at = now
        if target is RunStatus.QUEUED:  # a retry re-opens the run
            run.finished_at = None
            if error is None:
                run.error = None
        await session.commit()


@dataclass(frozen=True)
class StepHandle:
    agent_run_id: uuid.UUID
    workflow_id: str
    step_id: int
    trace_id: str
    run_id: uuid.UUID
    attempt_id: uuid.UUID | None

    def call_context(self) -> CallContext:
        return CallContext(
            trace_id=self.trace_id,
            run_id=self.run_id,
            attempt_id=self.attempt_id,
            agent_run_id=self.agent_run_id,
            dbos_workflow_id=self.workflow_id,
            dbos_step_id=self.step_id,
        )


async def _open_step_row(
    sm: SessionMaker,
    *,
    run_id: uuid.UUID,
    attempt_id: uuid.UUID | None,
    workflow_id: str,
    step_id: int,
    step_name: str,
    trace_id: str,
    agent_name: str | None,
    agent_version: str | None,
    started_at: datetime,
) -> tuple[uuid.UUID, int]:
    """Insert or re-open the step row; return its id and the number of executions so far."""
    stmt = insert(AgentRun).values(
        id=uuid7(),
        run_id=run_id,
        attempt_id=attempt_id,
        dbos_workflow_id=workflow_id,
        dbos_step_id=step_id,
        step_name=step_name,
        agent_name=agent_name,
        agent_version=agent_version,
        status=StepStatus.RUNNING.value,
        tries=1,
        started_at=started_at,
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal(0),
        sources_used=[],
        trace_id=trace_id,
    )
    upsert = stmt.on_conflict_do_update(
        constraint="uq_blog_agent_runs_wf_step",
        set_={
            "tries": AgentRun.tries + 1,
            "status": StepStatus.RUNNING.value,
            "attempt_id": attempt_id,
            "started_at": started_at,
            "completed_at": None,
            "duration_ms": None,
            "error": None,
        },
    ).returning(AgentRun.id, AgentRun.tries)
    async with sm() as session:
        agent_run_id, tries = (await session.execute(upsert)).one()
        await session.commit()
    return agent_run_id, tries


async def _close_step_row(
    sm: SessionMaker,
    *,
    agent_run_id: uuid.UUID,
    run_id: uuid.UUID,
    status: StepStatus,
    duration_ms: int,
    error: Mapping[str, object] | None,
) -> None:
    async with sm() as session:
        in_tokens, out_tokens, cost = (
            await session.execute(
                select(
                    func.coalesce(func.sum(LlmCall.input_tokens), 0),
                    func.coalesce(func.sum(LlmCall.output_tokens), 0),
                    func.coalesce(func.sum(LlmCall.cost_usd), 0),
                ).where(LlmCall.agent_run_id == agent_run_id)
            )
        ).one()
        last_ok = (
            await session.execute(
                select(
                    LlmCall.provider_requested,
                    LlmCall.model_requested,
                    LlmCall.model_served,
                    LlmCall.prompt_name,
                    LlmCall.prompt_version,
                )
                .where(LlmCall.agent_run_id == agent_run_id, LlmCall.status == CallStatus.OK.value)
                .order_by(LlmCall.created_at.desc())
                .limit(1)
            )
        ).first()
        values: dict[str, object] = {
            "status": status.value,
            "completed_at": _now(),
            "duration_ms": duration_ms,
            "input_tokens": int(in_tokens),
            "output_tokens": int(out_tokens),
            "cost_usd": Decimal(cost),
            "error": None if error is None else dict(error),
        }
        if last_ok is not None:
            provider, model_requested, model_served, prompt_name, prompt_version = last_ok
            values["model"] = model_served or f"{provider}:{model_requested}"
            values["prompt_name"] = prompt_name
            values["prompt_version"] = prompt_version
        await session.execute(update(AgentRun).where(AgentRun.id == agent_run_id).values(**values))
        run_cost = select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(LlmCall.run_id == run_id)
        await session.execute(update(BlogRun).where(BlogRun.id == run_id).values(cost_usd=run_cost.scalar_subquery()))
        await session.commit()


@asynccontextmanager
async def track_step(
    sm: SessionMaker,
    *,
    run_id: uuid.UUID,
    attempt_id: uuid.UUID | None,
    step_name: str,
    trace_id: str,
    agent_name: str | None = None,
    agent_version: str | None = None,
) -> AsyncIterator[StepHandle]:
    """Record one execution of the current DBOS step in blog_agent_runs. Must run inside a DBOS step.

    Each execution ends with one "step finished" log line. It carries the run_id/trace_id the step bound
    with bind_log_context.
    """
    workflow_id = DBOS.workflow_id
    step_id = DBOS.step_id
    if workflow_id is None or step_id is None:
        raise RuntimeError("track_step must be used inside a DBOS step (DBOS.workflow_id/step_id are unset)")
    started_at = _now()
    t0 = time.monotonic()
    agent_run_id, tries = await _open_step_row(
        sm,
        run_id=run_id,
        attempt_id=attempt_id,
        workflow_id=workflow_id,
        step_id=step_id,
        step_name=step_name,
        trace_id=trace_id,
        agent_name=agent_name,
        agent_version=agent_version,
        started_at=started_at,
    )
    handle = StepHandle(
        agent_run_id=agent_run_id,
        workflow_id=workflow_id,
        step_id=step_id,
        trace_id=trace_id,
        run_id=run_id,
        attempt_id=attempt_id,
    )
    try:
        yield handle
    except (Exception, asyncio.CancelledError) as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        await _close_step_row(
            sm,
            agent_run_id=agent_run_id,
            run_id=run_id,
            status=StepStatus.FAILED,
            duration_ms=duration_ms,
            error=error_payload(exc),
        )
        logger.warning(
            "step finished",
            extra={
                "step": step_name,
                "status": StepStatus.FAILED.value,
                "duration_ms": duration_ms,
                "tries": tries,
                "error_class": type(exc).__name__,
            },
        )
        raise
    duration_ms = int((time.monotonic() - t0) * 1000)
    await _close_step_row(
        sm,
        agent_run_id=agent_run_id,
        run_id=run_id,
        status=StepStatus.SUCCEEDED,
        duration_ms=duration_ms,
        error=None,
    )
    logger.info(
        "step finished",
        extra={"step": step_name, "status": StepStatus.SUCCEEDED.value, "duration_ms": duration_ms, "tries": tries},
    )
