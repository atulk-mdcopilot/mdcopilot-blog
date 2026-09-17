"""Phase 1 durable mock pipeline: three tracked steps through the LLM gateway (mock fixtures only).

Every step body is safe to execute twice. DBOS re-executes a step after a crash when the step finished its
side effects but its output was not yet recorded. So echo_step waits (mock delay) before its gateway call, and
a worker killed during that wait leaves no recorded call behind.

A run can be cancelled (Task 12) while a step executes. The step then stops without changing the run, closes
its attempt as CANCELLED and returns normally; DBOS stops the workflow when the next step starts.
"""

import asyncio
import contextlib
import logging
import uuid

from dbos import DBOS
from dbos._error import DBOSWorkflowCancelledError
from pydantic import BaseModel

from mdcopilot_blog.domain.enums import AgentName, AttemptStatus, RunStatus
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.llm.gateway import AgentSpec
from mdcopilot_blog.logs import bind_log_context
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.names import (
    STEP_HELLO_ECHO,
    STEP_HELLO_FAIL,
    STEP_HELLO_FINISH,
    STEP_HELLO_OPEN,
    WORKFLOW_HELLO,
)
from mdcopilot_blog.workflows.runtime import WorkerRuntime, get_runtime
from mdcopilot_blog.workflows.tracking import (
    ensure_attempt,
    finish_attempt,
    get_attempt_status,
    get_run_status,
    get_run_trace_id,
    set_run_status,
    track_step,
)

logger = logging.getLogger(__name__)

WORKFLOW_CANCELLED_ERROR = {"class": "WorkflowCancelled", "message": "cancelled or timed out by DBOS"}


class EchoOutput(BaseModel):
    message: str
    word_count: int


HELLO_SPEC = AgentSpec(
    name=AgentName.HELLO,
    version="1",
    prompt_name="hello/echo",
    output_type=EchoOutput,
    max_output_tokens=200,
)


def _current_workflow_id() -> str:
    workflow_id = DBOS.workflow_id
    if workflow_id is None:
        raise RuntimeError("hello steps must run inside the hello_pipeline workflow")
    return workflow_id


async def _mock_delay(settings: Settings) -> None:
    if settings.mock_mode and settings.mock_step_delay_seconds > 0:
        await asyncio.sleep(settings.mock_step_delay_seconds)


async def _attempt_of_current_workflow(rt: WorkerRuntime, run_id: uuid.UUID, copied_attempt_id: str) -> uuid.UUID:
    """A fork copies earlier step outputs, including the original attempt id. Resolve our own attempt instead."""
    attempt_id = await ensure_attempt(
        rt.sessionmaker, run_id=run_id, workflow_id=_current_workflow_id(), workflow_name=WORKFLOW_HELLO
    )
    if str(attempt_id) != copied_attempt_id:
        logger.info(
            "step runs in a forked workflow; using its own attempt",
            extra={"attempt_id": str(attempt_id), "copied_attempt_id": copied_attempt_id},
        )
    return attempt_id


async def _stop_if_cancelled(rt: WorkerRuntime, run_id: uuid.UUID, workflow_id: str) -> bool:
    """True if the run is CANCELLED. This workflow's attempt is then closed as CANCELLED."""
    if await get_run_status(rt.sessionmaker, run_id) is not RunStatus.CANCELLED:
        return False
    await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
    logger.info("run is cancelled; the step stops without changing it", extra={"workflow_id": workflow_id})
    return True


async def _advance(rt: WorkerRuntime, run_id: uuid.UUID, workflow_id: str, target: RunStatus, stage: str) -> bool:
    """Move the run to `target`. False if the run was cancelled first (the move is then skipped)."""
    try:
        await set_run_status(rt.sessionmaker, run_id=run_id, target=target, stage=stage)
    except InvalidTransition:
        # set_run_status locks the run row, so a cancel either landed before this move (CANCELLED -> target is
        # illegal and lands here) or after it (and the API cancels from the new status).
        if await _stop_if_cancelled(rt, run_id, workflow_id):
            return False
        raise
    return True


@DBOS.step(name=STEP_HELLO_OPEN)
async def open_attempt_step(run_id: str) -> dict[str, str]:
    rt = get_runtime()
    rid = uuid.UUID(run_id)
    workflow_id = _current_workflow_id()
    trace_id = await get_run_trace_id(rt.sessionmaker, rid)
    bind_log_context(run_id=run_id, trace_id=trace_id)
    attempt_id = await ensure_attempt(
        rt.sessionmaker, run_id=rid, workflow_id=workflow_id, workflow_name=WORKFLOW_HELLO
    )
    opened = {"attempt_id": str(attempt_id), "trace_id": trace_id}
    async with track_step(
        rt.sessionmaker, run_id=rid, attempt_id=attempt_id, step_name=STEP_HELLO_OPEN, trace_id=trace_id
    ):
        if not await _advance(rt, rid, workflow_id, RunStatus.RESEARCHING, STEP_HELLO_OPEN):
            return opened
        await _mock_delay(rt.settings)
    return opened


@DBOS.step(name=STEP_HELLO_ECHO)
async def echo_step(run_id: str, attempt_id: str, trace_id: str) -> dict[str, object]:
    rt = get_runtime()
    rid = uuid.UUID(run_id)
    workflow_id = _current_workflow_id()
    bind_log_context(run_id=run_id, trace_id=trace_id)
    own_attempt_id = await _attempt_of_current_workflow(rt, rid, attempt_id)
    async with track_step(
        rt.sessionmaker,
        run_id=rid,
        attempt_id=own_attempt_id,
        step_name=STEP_HELLO_ECHO,
        trace_id=trace_id,
        agent_name=AgentName.HELLO.value,
        agent_version=HELLO_SPEC.version,
    ) as handle:
        # a fork that starts at this step re-opened the run; enter the research stage first
        reopened = await get_run_status(rt.sessionmaker, rid) is RunStatus.QUEUED
        if reopened and not await _advance(rt, rid, workflow_id, RunStatus.RESEARCHING, STEP_HELLO_ECHO):
            return {}
        # delay first: a crash during the delay must not leave a recorded (in Phase 2, paid) call behind
        await _mock_delay(rt.settings)
        if await _stop_if_cancelled(rt, rid, workflow_id):  # no gateway call for a cancelled run
            return {}
        result = await rt.gateway.run(
            HELLO_SPEC,
            variables={"brand_name": "MDCopilot", "topic": "hello"},
            user_prompt="Say hello.",
            ctx=handle.call_context(),
        )
        await _advance(rt, rid, workflow_id, RunStatus.TOPICS_READY, STEP_HELLO_ECHO)
    return result.output.model_dump()


@DBOS.step(name=STEP_HELLO_FINISH)
async def finish_step(run_id: str, attempt_id: str, trace_id: str) -> None:
    rt = get_runtime()
    rid = uuid.UUID(run_id)
    bind_log_context(run_id=run_id, trace_id=trace_id)
    own_attempt_id = await _attempt_of_current_workflow(rt, rid, attempt_id)
    workflow_id = _current_workflow_id()
    async with track_step(
        rt.sessionmaker, run_id=rid, attempt_id=own_attempt_id, step_name=STEP_HELLO_FINISH, trace_id=trace_id
    ):
        # skip on re-execution: a crash after finish_attempt committed must not move a SUCCEEDED run again
        if await get_attempt_status(rt.sessionmaker, workflow_id) is not AttemptStatus.SUCCEEDED:
            # a crash between the run reaching SUCCEEDED and finish_attempt committing leaves the run
            # SUCCEEDED but the attempt still RUNNING; re-running here must only close the attempt
            # (SUCCEEDED -> PRODUCING is illegal and would fail the step and the whole attempt).
            if await get_run_status(rt.sessionmaker, rid) is not RunStatus.SUCCEEDED:
                for target in (RunStatus.PRODUCING, RunStatus.SUCCEEDED):
                    if not await _advance(rt, rid, workflow_id, target, STEP_HELLO_FINISH):
                        return
            await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.SUCCEEDED)
        await _mock_delay(rt.settings)


@DBOS.step(name=STEP_HELLO_FAIL)
async def mark_failed_step(run_id: str, error_class: str, message: str) -> None:
    rt = get_runtime()
    error = {"class": error_class, "message": message[:2000]}
    try:
        await set_run_status(rt.sessionmaker, run_id=uuid.UUID(run_id), target=RunStatus.FAILED, error=error)
    except (LookupError, ValueError) as exc:  # InvalidTransition is a ValueError: the run is already final
        logger.warning("run not marked failed", extra={"run_id": run_id, "reason": str(exc)})
    await finish_attempt(rt.sessionmaker, workflow_id=_current_workflow_id(), status=AttemptStatus.FAILED, error=error)


async def _close_cancelled_workflow(run_id: str) -> None:
    """Close the run and attempt of a workflow that DBOS cancelled (API cancel or workflow timeout).

    A plain coroutine, not a DBOS step: no step of a cancelled workflow can start. A run the API already
    cancelled stays CANCELLED (CANCELLED -> FAILED is illegal); a timed-out run becomes FAILED.
    """
    rt = get_runtime()
    with contextlib.suppress(InvalidTransition, LookupError):
        await set_run_status(
            rt.sessionmaker, run_id=uuid.UUID(run_id), target=RunStatus.FAILED, error=WORKFLOW_CANCELLED_ERROR
        )
    await finish_attempt(rt.sessionmaker, workflow_id=_current_workflow_id(), status=AttemptStatus.CANCELLED)
    logger.warning("workflow cancelled by DBOS", extra={"run_id": run_id})


@DBOS.workflow(name=WORKFLOW_HELLO)
async def hello_pipeline(run_id: str) -> dict[str, object]:
    # DBOS reports a cancel and a workflow timeout as DBOSWorkflowCancelledError, raised when the next step
    # starts. It is a BaseException, so the inner `except Exception` never records it as a step failure.
    try:
        try:
            opened = await open_attempt_step(run_id)
            echo = await echo_step(run_id, opened["attempt_id"], opened["trace_id"])
            await finish_step(run_id, opened["attempt_id"], opened["trace_id"])
        except Exception as exc:
            await mark_failed_step(run_id, type(exc).__name__, str(exc))
            raise
    except DBOSWorkflowCancelledError:
        await _close_cancelled_workflow(run_id)
        raise
    return {"run_id": run_id, "echo": echo}
