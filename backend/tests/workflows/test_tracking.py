"""Run, attempt and step bookkeeping (workflows/tracking.py)."""

import asyncio
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable

import pytest
from dbos import DBOS, SetWorkflowID
from sqlalchemy import select

from mdcopilot_blog.db.models import AgentRun, BlogRun, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, RunStatus
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.workflows.names import WORKFLOW_HELLO
from mdcopilot_blog.workflows.runtime import WorkerRuntime, get_runtime
from mdcopilot_blog.workflows.tracking import (
    ensure_attempt,
    finish_attempt,
    get_run_status,
    set_run_status,
    track_step,
)

type MakeRun = Callable[..., Awaitable[uuid.UUID]]

TRACE_ID = "0" * 32
STEP_CALLS: Counter[str] = Counter()


@DBOS.step(name="test.tracked_step", retries_allowed=True, max_attempts=2, interval_seconds=0.01)
async def tracked_step(run_id: str, key: str, failures: int) -> int:
    rt = get_runtime()
    async with track_step(
        rt.sessionmaker, run_id=uuid.UUID(run_id), attempt_id=None, step_name="test.tracked_step", trace_id=TRACE_ID
    ) as handle:
        STEP_CALLS[key] += 1
        if STEP_CALLS[key] <= failures:
            raise ValueError(f"planned failure {STEP_CALLS[key]}")
    return handle.step_id


@DBOS.workflow(name="test.tracked_workflow")
async def tracked_workflow(run_id: str, key: str, failures: int) -> int:
    return await tracked_step(run_id, key, failures)


async def _agent_runs(rt: WorkerRuntime, run_id: uuid.UUID) -> list[AgentRun]:
    async with rt.sessionmaker() as session:
        return list((await session.scalars(select(AgentRun).where(AgentRun.run_id == run_id))).all())


async def _run(rt: WorkerRuntime, run_id: uuid.UUID) -> BlogRun:
    async with rt.sessionmaker() as session:
        run = await session.get(BlogRun, run_id)
    assert run is not None
    return run


async def test_track_step_outside_a_step_raises(dbos_runtime: WorkerRuntime) -> None:
    with pytest.raises(RuntimeError, match="inside a DBOS step"):
        async with track_step(
            dbos_runtime.sessionmaker, run_id=uuid.uuid4(), attempt_id=None, step_name="x", trace_id=TRACE_ID
        ):
            pass


async def test_track_step_records_one_row_per_step(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    run_id = await make_run()
    key = uuid.uuid4().hex
    with SetWorkflowID(f"track-ok-{key}"):
        handle = await DBOS.start_workflow_async(tracked_workflow, str(run_id), key, 0)
    assert await asyncio.wait_for(handle.get_result(), timeout=30) == 1
    [row] = await _agent_runs(dbos_runtime, run_id)
    assert (row.dbos_workflow_id, row.dbos_step_id, row.step_name) == (f"track-ok-{key}", 1, "test.tracked_step")
    assert (row.status, row.tries, row.error) == ("SUCCEEDED", 1, None)
    assert row.completed_at is not None
    assert row.duration_ms is not None
    assert row.duration_ms >= 0
    assert (row.input_tokens, row.output_tokens, row.trace_id) == (0, 0, TRACE_ID)


async def test_track_step_counts_dbos_retries_as_tries(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    run_id = await make_run()
    key = uuid.uuid4().hex
    with SetWorkflowID(f"track-retry-{key}"):
        handle = await DBOS.start_workflow_async(tracked_workflow, str(run_id), key, 1)
    assert await asyncio.wait_for(handle.get_result(), timeout=30) == 1
    [row] = await _agent_runs(dbos_runtime, run_id)
    assert (row.status, row.tries, row.error) == ("SUCCEEDED", 2, None)
    assert STEP_CALLS[key] == 2


async def test_track_step_records_failure_and_reraises(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    run_id = await make_run()
    key = uuid.uuid4().hex
    with SetWorkflowID(f"track-fail-{key}"):
        handle = await DBOS.start_workflow_async(tracked_workflow, str(run_id), key, 5)
    with pytest.raises(Exception, match="exceeded its maximum of 2 retries"):  # DBOSMaxStepRetriesExceeded
        await asyncio.wait_for(handle.get_result(), timeout=30)
    [row] = await _agent_runs(dbos_runtime, run_id)
    assert (row.status, row.tries) == ("FAILED", 2)
    assert row.error == {"class": "ValueError", "message": "planned failure 2"}


async def test_set_run_status_follows_the_state_machine(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    with pytest.raises(InvalidTransition):
        await set_run_status(sm, run_id=run_id, target=RunStatus.SUCCEEDED)

    await set_run_status(sm, run_id=run_id, target=RunStatus.RESEARCHING, stage="first")
    await set_run_status(sm, run_id=run_id, target=RunStatus.RESEARCHING, stage="ignored")  # same state: no-op
    run = await _run(dbos_runtime, run_id)
    assert (run.status, run.stage, run.finished_at) == ("RESEARCHING", "first", None)
    assert run.started_at is not None

    await set_run_status(sm, run_id=run_id, target=RunStatus.FAILED, error={"class": "Boom", "message": "m"})
    run = await _run(dbos_runtime, run_id)
    assert (run.status, run.error) == ("FAILED", {"class": "Boom", "message": "m"})
    assert run.finished_at is not None

    with pytest.raises(InvalidTransition):
        await set_run_status(sm, run_id=run_id, target=RunStatus.PRODUCING)

    await set_run_status(sm, run_id=run_id, target=RunStatus.QUEUED)  # retry re-opens a failed run
    run = await _run(dbos_runtime, run_id)
    assert (run.status, run.finished_at, run.error) == ("QUEUED", None, None)


async def test_set_run_status_unknown_run_raises_lookup_error(dbos_runtime: WorkerRuntime) -> None:
    with pytest.raises(LookupError):
        await set_run_status(dbos_runtime.sessionmaker, run_id=uuid.uuid4(), target=RunStatus.RESEARCHING)


async def test_ensure_attempt_is_idempotent_per_workflow_id(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    suffix = uuid.uuid4().hex
    first = await ensure_attempt(sm, run_id=run_id, workflow_id=f"a-{suffix}", workflow_name=WORKFLOW_HELLO)
    again = await ensure_attempt(sm, run_id=run_id, workflow_id=f"a-{suffix}", workflow_name=WORKFLOW_HELLO)
    second = await ensure_attempt(sm, run_id=run_id, workflow_id=f"b-{suffix}", workflow_name=WORKFLOW_HELLO)
    assert first == again
    assert second != first
    async with sm() as session:
        rows = (await session.scalars(select(RunAttempt).where(RunAttempt.run_id == run_id))).all()
    summary = sorted((r.attempt_no, r.dbos_workflow_id, r.status, r.forked_from_workflow_id) for r in rows)
    assert summary == [(1, f"a-{suffix}", "RUNNING", None), (2, f"b-{suffix}", "RUNNING", None)]
    assert all(r.started_at is not None and r.start_step is None for r in rows)  # called outside a step


async def test_ensure_attempt_for_a_cancelled_run_is_closed_at_once(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run(status=RunStatus.CANCELLED)
    workflow_id = f"c-{uuid.uuid4().hex}"
    attempt_id = await ensure_attempt(sm, run_id=run_id, workflow_id=workflow_id, workflow_name=WORKFLOW_HELLO)
    async with sm() as session:
        attempt = await session.get(RunAttempt, attempt_id)
    assert attempt is not None
    assert (attempt.status, attempt.attempt_no, attempt.forked_from_workflow_id) == ("CANCELLED", 1, None)
    assert attempt.finished_at is not None
    assert await get_run_status(sm, run_id) is RunStatus.CANCELLED  # an original attempt never re-opens a run


async def test_ensure_attempt_unknown_run_raises_lookup_error(dbos_runtime: WorkerRuntime) -> None:
    with pytest.raises(LookupError):
        await ensure_attempt(
            dbos_runtime.sessionmaker, run_id=uuid.uuid4(), workflow_id=uuid.uuid4().hex, workflow_name=WORKFLOW_HELLO
        )


async def test_finish_attempt_closes_only_open_attempts(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    workflow_id = f"fin-{uuid.uuid4().hex}"
    attempt_id = await ensure_attempt(sm, run_id=run_id, workflow_id=workflow_id, workflow_name=WORKFLOW_HELLO)
    await finish_attempt(sm, workflow_id=workflow_id, status=AttemptStatus.SUCCEEDED)
    await finish_attempt(sm, workflow_id=workflow_id, status=AttemptStatus.FAILED, error={"class": "Late"})
    await finish_attempt(sm, workflow_id="does-not-exist", status=AttemptStatus.FAILED)  # no-op
    async with sm() as session:
        attempt = await session.get(RunAttempt, attempt_id)
    assert attempt is not None
    assert (attempt.status, attempt.error) == ("SUCCEEDED", None)
    assert attempt.finished_at is not None
