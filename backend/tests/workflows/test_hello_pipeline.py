"""hello_pipeline end to end on the test database, with the in-process DBOS worker from `dbos_runtime`."""

import asyncio
import contextlib
import io
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio
from dbos import DBOS, DBOSClient, SetWorkflowID
from sqlalchemy import select

from mdcopilot_blog.db.models import AgentRun, BlogRun, LlmCall, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, RunStatus
from mdcopilot_blog.llm.mock import FixtureRegistry
from mdcopilot_blog.logs import JsonFormatter
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.dbos_config import DBOS_APP_NAME, DBOS_SYSTEM_SCHEMA
from mdcopilot_blog.workflows.hello import finish_step, hello_pipeline
from mdcopilot_blog.workflows.names import (
    QUEUE_PIPELINE,
    STEP_HELLO_ECHO,
    STEP_HELLO_FAIL,
    STEP_HELLO_FINISH,
    STEP_HELLO_OPEN,
    WORKFLOW_HELLO,
)
from mdcopilot_blog.workflows.runtime import WorkerRuntime
from mdcopilot_blog.workflows.tracking import (
    ensure_attempt,
    finish_attempt,
    get_attempt_status,
    get_run_status,
    set_run_status,
)

type MakeRun = Callable[..., Awaitable[uuid.UUID]]
type LogLines = Callable[[], list[dict[str, Any]]]

ECHO = {"message": "Hello from the mock gateway", "word_count": 5}
WAIT_SECONDS = 60
TRACE_ID = "0" * 32
LOOP_CALLS: list[tuple[str | None, str, int | None]] = []


@DBOS.step(name="test.before_loop")
async def before_loop_step() -> int | None:
    LOOP_CALLS.append((DBOS.workflow_id, "before", DBOS.step_id))
    return DBOS.step_id


@DBOS.step(name="test.loop_step")
async def loop_step(index: int) -> int | None:
    LOOP_CALLS.append((DBOS.workflow_id, f"loop{index}", DBOS.step_id))
    return DBOS.step_id


@DBOS.step(name="test.after_loop")
async def after_loop_step() -> int | None:
    LOOP_CALLS.append((DBOS.workflow_id, "after", DBOS.step_id))
    return DBOS.step_id


@DBOS.workflow(name="test.loop_workflow")
async def loop_workflow() -> list[int | None]:
    step_ids = [await before_loop_step()]
    for index in range(3):
        step_ids.append(await loop_step(index))
    step_ids.append(await after_loop_step())
    return step_ids


@DBOS.workflow(name="test.finish_step_twice_workflow")
async def finish_step_twice_workflow(run_id: str, attempt_id: str, trace_id: str) -> None:
    """Call finish_step twice for the same run/attempt, as DBOS would on a crash-then-recovery."""
    with contextlib.suppress(RuntimeError):
        await finish_step(run_id, attempt_id, trace_id)
    await finish_step(run_id, attempt_id, trace_id)


@dataclass
class RunRows:
    run: BlogRun
    attempts: list[RunAttempt]
    steps: list[AgentRun]
    calls: list[LlmCall]


async def load_rows(rt: WorkerRuntime, run_id: uuid.UUID) -> RunRows:
    async with rt.sessionmaker() as session:
        run = await session.get(BlogRun, run_id)
        assert run is not None
        attempts = (
            await session.scalars(select(RunAttempt).where(RunAttempt.run_id == run_id).order_by(RunAttempt.attempt_no))
        ).all()
        steps = (
            await session.scalars(
                select(AgentRun).where(AgentRun.run_id == run_id).order_by(AgentRun.created_at, AgentRun.dbos_step_id)
            )
        ).all()
        calls = (await session.scalars(select(LlmCall).where(LlmCall.run_id == run_id))).all()
    return RunRows(run, list(attempts), list(steps), list(calls))


async def wait_for_result(workflow_id: str) -> Any:
    handle = await DBOS.retrieve_workflow_async(workflow_id)
    return await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS)


async def start_hello(run_id: uuid.UUID) -> Any:
    """Start hello_pipeline directly (not through the queue) and return its result."""
    with SetWorkflowID(f"manual-{run_id}"):
        handle = await DBOS.start_workflow_async(hello_pipeline, str(run_id))
    return await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS)


@pytest_asyncio.fixture(loop_scope="session")
async def workflow_client(dbos_runtime: WorkerRuntime) -> AsyncIterator[WorkflowClient]:
    """The API's client, pointed at the test DB and at the version the in-process worker runs."""
    dbos_client = DBOSClient(
        system_database_url=dbos_runtime.settings.dbos_system_database_url,
        dbos_system_schema=DBOS_SYSTEM_SCHEMA,
        application_name=DBOS_APP_NAME,
        lazy=True,
    )
    client = WorkflowClient(dbos_client, DBOS.application_version)
    yield client
    await asyncio.to_thread(client.close)


@pytest.fixture
def step_log_lines() -> Iterator[LogLines]:
    """JSON lines (JsonFormatter) that workflows/tracking.py logs during the test."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    tracking_logger = logging.getLogger("mdcopilot_blog.workflows.tracking")
    previous_level = tracking_logger.level
    tracking_logger.addHandler(handler)
    tracking_logger.setLevel(logging.INFO)
    try:
        yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    finally:
        tracking_logger.removeHandler(handler)
        tracking_logger.setLevel(previous_level)


async def enqueue_hello(client: WorkflowClient, run_id: uuid.UUID, timeout_seconds: float = 120) -> str:
    return await client.enqueue(
        workflow_name=WORKFLOW_HELLO,
        queue_name=QUEUE_PIPELINE,
        workflow_id=f"manual-{run_id}",
        args=(str(run_id),),
        timeout_seconds=timeout_seconds,
    )


async def test_hello_pipeline_runs_end_to_end(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient
) -> None:
    run_id = await make_run()
    workflow_id = await enqueue_hello(workflow_client, run_id)
    assert workflow_id == f"manual-{run_id}"

    assert await wait_for_result(workflow_id) == {"run_id": str(run_id), "echo": ECHO}
    assert await workflow_client.status(workflow_id) == "SUCCESS"

    rows = await load_rows(dbos_runtime, run_id)
    assert (rows.run.status, rows.run.stage, rows.run.error) == ("SUCCEEDED", STEP_HELLO_FINISH, None)
    assert rows.run.started_at is not None
    assert rows.run.finished_at is not None

    [attempt] = rows.attempts
    assert (attempt.attempt_no, attempt.status, attempt.dbos_workflow_id) == (1, "SUCCEEDED", workflow_id)
    assert (attempt.workflow_name, attempt.forked_from_workflow_id, attempt.start_step) == (WORKFLOW_HELLO, None, 1)
    assert attempt.finished_at is not None

    assert [(s.step_name, s.dbos_step_id, s.status, s.tries) for s in rows.steps] == [
        (STEP_HELLO_OPEN, 1, "SUCCEEDED", 1),
        (STEP_HELLO_ECHO, 2, "SUCCEEDED", 1),
        (STEP_HELLO_FINISH, 3, "SUCCEEDED", 1),
    ]
    assert all(s.attempt_id == attempt.id and s.trace_id == rows.run.trace_id for s in rows.steps)
    echo_row = rows.steps[1]
    assert (echo_row.agent_name, echo_row.agent_version, echo_row.model) == ("hello", "1", "mock:hello")
    assert (echo_row.prompt_name, echo_row.prompt_version) == ("hello/echo", 1)
    assert (echo_row.input_tokens, echo_row.output_tokens) == (20, 8)

    [call] = rows.calls
    assert (call.kind, call.status, call.agent_run_id) == ("agent", "ok", echo_row.id)
    assert (call.attempt_id, call.dbos_workflow_id, call.dbos_step_id) == (attempt.id, workflow_id, 2)
    assert call.trace_id == rows.run.trace_id

    steps = await workflow_client.list_steps(workflow_id)
    assert [(s.function_id, s.function_name) for s in steps] == [
        (1, STEP_HELLO_OPEN),
        (2, STEP_HELLO_ECHO),
        (3, STEP_HELLO_FINISH),
    ]


async def test_step_logs_carry_run_and_trace_ids(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, step_log_lines: LogLines
) -> None:
    run_id = await make_run()
    await start_hello(run_id)
    trace_id = (await load_rows(dbos_runtime, run_id)).run.trace_id
    assert re.fullmatch(r"[0-9a-f]{32}", trace_id)

    finished = [
        line for line in step_log_lines() if line["message"] == "step finished" and line.get("run_id") == str(run_id)
    ]
    assert [(line["step"], line["status"], line["tries"], line["level"]) for line in finished] == [
        (STEP_HELLO_OPEN, "SUCCEEDED", 1, "INFO"),
        (STEP_HELLO_ECHO, "SUCCEEDED", 1, "INFO"),
        (STEP_HELLO_FINISH, "SUCCEEDED", 1, "INFO"),
    ]
    assert all(line["trace_id"] == trace_id for line in finished)
    assert all(isinstance(line["duration_ms"], int) for line in finished)


async def test_hello_pipeline_failure_marks_run_and_attempt_failed(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_fixture(self: FixtureRegistry, agent: str, prompt_name: str) -> dict[str, Any]:
        raise FileNotFoundError(f"mock fixture missing for {agent}/{prompt_name}")

    monkeypatch.setattr(FixtureRegistry, "load", missing_fixture)
    run_id = await make_run()
    workflow_id = f"manual-{run_id}"
    with pytest.raises(FileNotFoundError, match="mock fixture missing"):
        await start_hello(run_id)

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.status == "FAILED"
    assert rows.run.error is not None
    assert rows.run.error["class"] == "FileNotFoundError"
    assert rows.run.finished_at is not None

    [attempt] = rows.attempts
    assert attempt.status == "FAILED"
    assert attempt.error is not None
    assert attempt.error["class"] == "FileNotFoundError"
    assert attempt.finished_at is not None

    assert [(s.step_name, s.status, s.tries) for s in rows.steps] == [
        (STEP_HELLO_OPEN, "SUCCEEDED", 1),
        (STEP_HELLO_ECHO, "FAILED", 1),
    ]
    echo_row = rows.steps[1]
    assert echo_row.error is not None
    assert echo_row.error["class"] == "FileNotFoundError"
    assert "mock fixture missing" in str(echo_row.error["message"])

    [status] = await DBOS.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
    assert status.status == "ERROR"
    dbos_steps = await DBOS.list_workflow_steps_async(workflow_id)
    assert [s["function_name"] for s in dbos_steps] == [STEP_HELLO_OPEN, STEP_HELLO_ECHO, STEP_HELLO_FAIL]


async def test_fork_from_finish_adds_an_attempt_and_does_not_rerun_echo(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient
) -> None:
    run_id = await make_run()
    original_id = await enqueue_hello(workflow_client, run_id)
    await wait_for_result(original_id)

    fork_id = await workflow_client.fork_from_step(original_id, STEP_HELLO_FINISH, queue_name=QUEUE_PIPELINE)
    assert fork_id != original_id
    assert await wait_for_result(fork_id) == {"run_id": str(run_id), "echo": ECHO}

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.status == "SUCCEEDED"
    assert [
        (a.attempt_no, a.dbos_workflow_id, a.status, a.forked_from_workflow_id, a.start_step) for a in rows.attempts
    ] == [
        (1, original_id, "SUCCEEDED", None, 1),
        (2, fork_id, "SUCCEEDED", original_id, 3),
    ]
    assert len(rows.calls) == 1  # echo was copied, not re-executed
    assert [(s.dbos_workflow_id, s.step_name, s.status, s.tries) for s in rows.steps] == [
        (original_id, STEP_HELLO_OPEN, "SUCCEEDED", 1),
        (original_id, STEP_HELLO_ECHO, "SUCCEEDED", 1),
        (original_id, STEP_HELLO_FINISH, "SUCCEEDED", 1),
        (fork_id, STEP_HELLO_FINISH, "SUCCEEDED", 1),
    ]
    assert rows.steps[3].attempt_id == rows.attempts[1].id
    assert rows.steps[3].dbos_step_id == 3

    fork_steps = await workflow_client.list_steps(fork_id)
    assert [s.function_name for s in fork_steps] == [STEP_HELLO_OPEN, STEP_HELLO_ECHO, STEP_HELLO_FINISH]


async def test_finish_step_survives_a_crash_between_run_succeeded_and_attempt_closed(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker killed between set_run_status(SUCCEEDED) committing and finish_attempt committing leaves
    the run SUCCEEDED but the attempt still RUNNING. DBOS re-runs finish_step on recovery: it must only
    close the attempt, not retry SUCCEEDED -> PRODUCING (illegal, and used to fail the step, the attempt
    and the whole workflow while the run stayed SUCCEEDED)."""
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    workflow_id = f"finish-twice-{uuid.uuid4().hex}"
    attempt_id = await ensure_attempt(sm, run_id=run_id, workflow_id=workflow_id, workflow_name=WORKFLOW_HELLO)
    await set_run_status(sm, run_id=run_id, target=RunStatus.RESEARCHING)
    await set_run_status(sm, run_id=run_id, target=RunStatus.TOPICS_READY)

    real_finish_attempt = finish_attempt
    calls = 0

    async def crash_before_first_commit(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:  # simulates the worker dying after the run reached SUCCEEDED
            raise RuntimeError("worker killed before finish_attempt committed")
        await real_finish_attempt(*args, **kwargs)

    monkeypatch.setattr("mdcopilot_blog.workflows.hello.finish_attempt", crash_before_first_commit)

    with SetWorkflowID(workflow_id):
        handle = await DBOS.start_workflow_async(finish_step_twice_workflow, str(run_id), str(attempt_id), TRACE_ID)
    await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS)  # would raise InvalidTransition pre-fix

    assert calls == 2
    assert await get_run_status(sm, run_id) is RunStatus.SUCCEEDED
    assert await get_attempt_status(sm, workflow_id) is AttemptStatus.SUCCEEDED


async def test_fork_from_a_repeated_step_restarts_at_its_last_execution(
    dbos_runtime: WorkerRuntime, workflow_client: WorkflowClient
) -> None:
    workflow_id = f"loop-{uuid.uuid4().hex}"
    with SetWorkflowID(workflow_id):
        handle = await DBOS.start_workflow_async(loop_workflow)
    assert await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS) == [1, 2, 3, 4, 5]

    fork_id = await workflow_client.fork_from_step(workflow_id, "test.loop_step", queue_name=QUEUE_PIPELINE)
    assert await wait_for_result(fork_id) == [1, 2, 3, 4, 5]

    fork_steps = await workflow_client.list_steps(fork_id)
    assert [(s.function_id, s.function_name) for s in fork_steps] == [
        (1, "test.before_loop"),
        (2, "test.loop_step"),
        (3, "test.loop_step"),
        (4, "test.loop_step"),
        (5, "test.after_loop"),
    ]
    # function ids 1-3 were copied; only the last loop_step execution (id 4) and what follows ran again
    assert [(name, step_id) for wf, name, step_id in LOOP_CALLS if wf == workflow_id] == [
        ("before", 1),
        ("loop0", 2),
        ("loop1", 3),
        ("loop2", 4),
        ("after", 5),
    ]
    assert [(name, step_id) for wf, name, step_id in LOOP_CALLS if wf == fork_id] == [("loop2", 4), ("after", 5)]


async def test_cancelled_run_stays_cancelled(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        dbos_runtime, "settings", dbos_runtime.settings.model_copy(update={"mock_step_delay_seconds": 1.0})
    )
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    workflow_id = await enqueue_hello(workflow_client, run_id)
    async with asyncio.timeout(WAIT_SECONDS):
        while await get_run_status(sm, run_id) is not RunStatus.RESEARCHING:
            await asyncio.sleep(0.05)

    # what the runs API does on cancel (Task 12): cancel in DBOS, then close the attempt and the run
    await workflow_client.cancel(workflow_id)
    await finish_attempt(sm, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
    await set_run_status(sm, run_id=run_id, target=RunStatus.CANCELLED)

    with pytest.raises(Exception, match="cancelled"):  # DBOSAwaitedWorkflowCancelledError
        await wait_for_result(workflow_id)
    async with asyncio.timeout(WAIT_SECONDS):  # the running step finishes; no later step starts
        while (await load_rows(dbos_runtime, run_id)).steps[0].status == "RUNNING":
            await asyncio.sleep(0.05)
    await asyncio.sleep(0.5)

    rows = await load_rows(dbos_runtime, run_id)
    assert (rows.run.status, rows.run.error) == ("CANCELLED", None)
    assert [a.status for a in rows.attempts] == ["CANCELLED"]
    assert [(s.step_name, s.status) for s in rows.steps] == [(STEP_HELLO_OPEN, "SUCCEEDED")]
    assert rows.calls == []
    assert await workflow_client.status(workflow_id) == "CANCELLED"


async def test_workflow_timeout_fails_the_run_and_cancels_the_attempt(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DBOS cancels a workflow whose timeout passed; the next step start raises DBOSWorkflowCancelledError
    monkeypatch.setattr(
        dbos_runtime, "settings", dbos_runtime.settings.model_copy(update={"mock_step_delay_seconds": 2.0})
    )
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    workflow_id = await enqueue_hello(workflow_client, run_id, timeout_seconds=1)
    with pytest.raises(Exception, match="cancelled"):  # DBOSAwaitedWorkflowCancelledError
        await wait_for_result(workflow_id)
    async with asyncio.timeout(WAIT_SECONDS):
        while await get_run_status(sm, run_id) is not RunStatus.FAILED:
            await asyncio.sleep(0.05)

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.error == {"class": "WorkflowCancelled", "message": "cancelled or timed out by DBOS"}
    assert rows.run.finished_at is not None
    [attempt] = rows.attempts
    assert (attempt.status, attempt.error) == ("CANCELLED", None)
    assert attempt.finished_at is not None
    assert [(s.step_name, s.status) for s in rows.steps] == [(STEP_HELLO_OPEN, "SUCCEEDED")]
    assert rows.calls == []
    assert await workflow_client.status(workflow_id) == "CANCELLED"


async def test_workflow_of_a_run_cancelled_while_queued_changes_nothing(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    run_id = await make_run(status=RunStatus.CANCELLED)
    assert await start_hello(run_id) == {"run_id": str(run_id), "echo": {}}

    rows = await load_rows(dbos_runtime, run_id)
    assert (rows.run.status, rows.run.started_at, rows.run.error) == ("CANCELLED", None, None)
    [attempt] = rows.attempts
    assert attempt.status == "CANCELLED"
    assert attempt.finished_at is not None
    assert [(s.step_name, s.status) for s in rows.steps] == [
        (STEP_HELLO_OPEN, "SUCCEEDED"),
        (STEP_HELLO_ECHO, "SUCCEEDED"),
        (STEP_HELLO_FINISH, "SUCCEEDED"),
    ]
    assert rows.calls == []


async def test_cancel_during_the_echo_call_is_not_a_step_failure(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    real_run = dbos_runtime.gateway.run

    async def run_then_cancel(*args: Any, **kwargs: Any) -> Any:
        result = await real_run(*args, **kwargs)
        await set_run_status(sm, run_id=run_id, target=RunStatus.CANCELLED)  # the API cancels meanwhile
        return result

    monkeypatch.setattr(dbos_runtime.gateway, "run", run_then_cancel)
    assert await start_hello(run_id) == {"run_id": str(run_id), "echo": ECHO}

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.status == "CANCELLED"
    assert rows.run.stage == STEP_HELLO_OPEN  # TOPICS_READY was never written
    assert [a.status for a in rows.attempts] == ["CANCELLED"]
    assert [(s.step_name, s.status, s.error) for s in rows.steps] == [
        (STEP_HELLO_OPEN, "SUCCEEDED", None),
        (STEP_HELLO_ECHO, "SUCCEEDED", None),
        (STEP_HELLO_FINISH, "SUCCEEDED", None),
    ]
    assert len(rows.calls) == 1
