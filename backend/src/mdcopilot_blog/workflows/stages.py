"""Step contexts, transitions, cancellation and failure bookkeeping."""

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from dbos import DBOS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog import tracing
from mdcopilot_blog.db.models import Article, RunAttempt
from mdcopilot_blog.domain.enums import ArticleStatus, AttemptStatus, RunStatus
from mdcopilot_blog.domain.state_machine import Entity, InvalidTransition, can_transition
from mdcopilot_blog.logs import bind_log_context
from mdcopilot_blog.services.article_status import set_article_status
from mdcopilot_blog.services.step_context import StepContext, build_step_context
from mdcopilot_blog.workflows.names import KNOWN_STEP_NAMES, WORKFLOW_DISCOVER_TOPICS
from mdcopilot_blog.workflows.retry import WorkflowCancelledError, step_options
from mdcopilot_blog.workflows.runtime import get_runtime
from mdcopilot_blog.workflows.tracking import (
    ensure_attempt,
    finish_attempt,
    get_attempt_status,
    get_run_status,
    get_run_trace_id,
    set_run_status,
    track_step,
)

STOP: dict[str, Any] = {"cancelled": True}
KNOWN_STEPS = KNOWN_STEP_NAMES


class StaleWorkflowError(RuntimeError):
    """The article moved on (a newer version or attempt), so this workflow's output is obsolete."""


@dataclass(frozen=True)
class StageContext:
    sc: StepContext
    run_id: uuid.UUID
    attempt_id: uuid.UUID
    workflow_id: str
    step_name: str
    trace_id: str


async def advance_run(run_id: uuid.UUID, target: RunStatus, stage: str | None = None) -> bool:
    sm = get_runtime().sessionmaker
    while True:
        current = await get_run_status(sm, run_id)
        if current == RunStatus.CANCELLED:
            return False
        if current == RunStatus.SUCCEEDED and target == RunStatus.PRODUCING:
            return True  # push_draft re-executed after it already succeeded; its body is idempotent
        if current == target and stage is None:
            return True
        try:
            # Same status with a stage only records the new stage (the progress label on the Generate page).
            await set_run_status(sm, run_id=run_id, target=target, stage=stage)
            if current == target:
                return True
        except InvalidTransition:
            if await get_run_status(sm, run_id) == RunStatus.CANCELLED:
                return False
            raise


async def advance_article(
    article_id: uuid.UUID,
    target: ArticleStatus,
    *,
    version_id: str | None = None,
    db: AsyncSession | None = None,
) -> None:
    if db is None:
        async with get_runtime().sessionmaker() as session:
            await advance_article(article_id, target, version_id=version_id, db=session)
            await session.commit()
        return
    article = await db.scalar(select(Article).where(Article.id == article_id).with_for_update())
    if article is None:
        raise LookupError(f"article {article_id} not found")
    if version_id is not None and article.current_version_id != uuid.UUID(version_id):
        raise StaleWorkflowError("article version changed while this workflow was running")
    forward = {
        "DRAFTING": ArticleStatus.FACT_CHECKING,
        "FACT_CHECKING": ArticleStatus.CLINICAL_REVIEW,
        "CLINICAL_REVIEW": ArticleStatus.EDITORIAL_REVIEW,
    }
    while True:
        current = article.status
        if current == target:
            return
        next_status = target
        if not can_transition(Entity.ARTICLE, current, target):
            if current == "FAILED":
                next_status = ArticleStatus.DRAFTING
            elif current in forward and target in {
                ArticleStatus.CLINICAL_REVIEW,
                ArticleStatus.EDITORIAL_REVIEW,
                ArticleStatus.SEO,
            }:
                next_status = forward[current]
        await set_article_status(db, article_id=article_id, target=next_status)


async def tracked_stage(
    step_name: str,
    *,
    run_id: str,
    workflow_name: str,
    body: Callable[[StageContext], Awaitable[dict[str, Any]]],
    article_id: str | None = None,
    agent_name: str | None = None,
    retries: bool = True,
) -> dict[str, Any]:
    if step_name not in KNOWN_STEPS:
        raise RuntimeError(f"unknown step name {step_name}")

    async def execute() -> dict[str, Any]:
        rt = get_runtime()
        workflow_id = DBOS.workflow_id
        if workflow_id is None:
            raise RuntimeError("step must run inside a workflow")
        rid = uuid.UUID(run_id)
        aid = await ensure_attempt(rt.sessionmaker, run_id=rid, workflow_id=workflow_id, workflow_name=workflow_name)
        if await get_attempt_status(rt.sessionmaker, workflow_id) == AttemptStatus.CANCELLED or (
            await get_run_status(rt.sessionmaker, rid) == RunStatus.CANCELLED
        ):
            await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
            return STOP
        trace_id, created_by = await get_run_trace_id(rt.sessionmaker, rid)
        bind_log_context(run_id=str(rid), trace_id=trace_id)
        # One stage.<step_name> span per step execution (a DBOS re-execution is a new span with tries+1).
        # span is None when tracing is off.
        with tracing.stage_span(
            trace_id=trace_id,
            step_name=step_name,
            run_id=str(rid),
            user_id=created_by,
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            agent=agent_name,
        ) as span:
            async with track_step(
                rt.sessionmaker,
                run_id=rid,
                attempt_id=aid,
                step_name=step_name,
                trace_id=trace_id,
                agent_name=agent_name,
            ) as handle:
                tracing.annotate(span, tries=handle.tries, dbos_step_id=handle.step_id)
                sc = await build_step_context(
                    settings=rt.settings,
                    sessionmaker=rt.sessionmaker,
                    gateway=rt.gateway,
                    prompts=rt.prompts,
                    call=handle.call_context(),
                )
                if article_id:
                    sc = sc.with_ids(article_id=uuid.UUID(article_id))
                output = await body(StageContext(sc, rid, aid, workflow_id, step_name, trace_id))
                if await get_attempt_status(rt.sessionmaker, workflow_id) == AttemptStatus.CANCELLED or (
                    await get_run_status(rt.sessionmaker, rid) == RunStatus.CANCELLED
                ):
                    await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
                    return STOP
                return {"cancelled": False, **output}

    return await DBOS.run_step_async(step_options(step_name, retries=retries), execute)


async def fail_workflow(
    *,
    workflow_name: str,
    run_id: str,
    article_id: str | None,
    error: BaseException,
) -> None:
    rt = get_runtime()
    workflow_id = DBOS.workflow_id
    if not workflow_id:
        return
    payload = {"class": type(error).__name__, "message": str(error)[:2000]}
    timed_out = False
    if (
        isinstance(error, (WorkflowCancelledError, asyncio.CancelledError))
        or await get_attempt_status(rt.sessionmaker, workflow_id) == AttemptStatus.CANCELLED
    ):
        # A DBOS deadline (SetWorkflowTimeout) arrives as the same error as a user cancel, but nobody writes a
        # terminal status for it: the run would stay PRODUCING forever. cancel_run cancels in DBOS first and
        # commits CANCELLED right after, so give that commit a moment before deciding this was a timeout.
        # asyncio.CancelledError is a worker shutdown: DBOS resumes that workflow on restart.
        if isinstance(error, WorkflowCancelledError):
            await asyncio.sleep(1)
            timed_out = (
                await get_attempt_status(rt.sessionmaker, workflow_id) != AttemptStatus.CANCELLED
                and await get_run_status(rt.sessionmaker, uuid.UUID(run_id)) != RunStatus.CANCELLED
            )
        if not timed_out:
            await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
            return
        payload = {"class": "WorkflowTimeout", "message": f"{workflow_name} exceeded its time limit"}

    async def failed() -> None:
        rid = uuid.UUID(run_id)
        stale = isinstance(error, StaleWorkflowError)
        async with rt.sessionmaker() as db:
            attempt = await db.scalar(select(RunAttempt).where(RunAttempt.dbos_workflow_id == workflow_id))
            if attempt is None or attempt.status == "CANCELLED":
                return
            newer = await db.scalar(
                select(RunAttempt.id)
                .where(RunAttempt.run_id == rid, RunAttempt.attempt_no > attempt.attempt_no)
                .limit(1)
            )
            stale = stale or newer is not None
            article = (
                await db.scalar(select(Article).where(Article.id == uuid.UUID(article_id)).with_for_update())
                if article_id
                else None
            )
            if article and not stale and can_transition(Entity.ARTICLE, article.status, ArticleStatus.FAILED):
                await set_article_status(db, article_id=article.id, target=ArticleStatus.FAILED)
            await db.commit()
        if not stale:
            with contextlib.suppress(InvalidTransition, LookupError):
                await set_run_status(rt.sessionmaker, run_id=rid, target=RunStatus.FAILED, error=payload)
        await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.FAILED, error=payload)

    if timed_out:
        await failed()  # called directly: a cancelled workflow cannot start another step
        return
    prefix = "discover" if workflow_name == WORKFLOW_DISCOVER_TOPICS else "produce"
    await DBOS.run_step_async(step_options(f"{prefix}.mark_failed"), failed)
