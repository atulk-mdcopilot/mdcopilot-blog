"""Fork-aware step contexts, transitions, cancellation and failure bookkeeping."""

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from dbos import DBOS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import Article, RunAttempt
from mdcopilot_blog.domain.enums import ArticleStatus, AttemptStatus, RunStatus
from mdcopilot_blog.domain.state_machine import Entity, InvalidTransition, can_transition
from mdcopilot_blog.logs import bind_log_context
from mdcopilot_blog.services.article_status import set_article_status
from mdcopilot_blog.services.step_context import StepContext, build_step_context
from mdcopilot_blog.workflows.names import HUMAN_ACTION_WORKFLOWS, KNOWN_STEP_NAMES
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
PROTECTED_ARTICLE_STATUSES = frozenset(
    {"APPROVED", "SCHEDULED", "EXPORTED", "PUBLISHING", "PUBLISHED", "PUBLISH_FAILED", "REJECTED", "SUPERSEDED"}
)


class StaleWorkflowError(RuntimeError):
    """A newer edit or human decision makes this workflow's output obsolete."""


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
        if current == target:
            return True
        next_status = target
        if not can_transition(Entity.RUN, current, target):
            if current in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
                next_status = RunStatus.QUEUED
            elif current == RunStatus.QUEUED and target in {RunStatus.TOPICS_READY, RunStatus.WAITING_FOR_TOPIC}:
                next_status = RunStatus.RESEARCHING
            elif current == RunStatus.RESEARCHING and target == RunStatus.WAITING_FOR_TOPIC:
                next_status = RunStatus.TOPICS_READY
        try:
            await set_run_status(sm, run_id=run_id, target=next_status, stage=stage if next_status == target else None)
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
    if article.status in PROTECTED_ARTICLE_STATUSES:
        raise StaleWorkflowError(f"article is now {article.status}")
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
                ArticleStatus.READY_FOR_REVIEW,
                ArticleStatus.QUALITY_GATE_FAILED,
            }:
                next_status = forward[current]
        await set_article_status(db, article_id=article_id, target=next_status)


async def tracked_stage(
    step_name: str,
    *,
    run_id: str | None,
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
        if run_id is None:
            async with rt.sessionmaker() as db:
                rid = await db.scalar(select(Article.run_id).where(Article.id == uuid.UUID(str(article_id))))
            if rid is None:
                raise LookupError(f"article {article_id} not found")
        else:
            rid = uuid.UUID(run_id)
        human = workflow_name in HUMAN_ACTION_WORKFLOWS
        aid = await ensure_attempt(
            rt.sessionmaker,
            run_id=rid,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            respect_run_cancel=not human,
        )
        if await get_attempt_status(rt.sessionmaker, workflow_id) == AttemptStatus.CANCELLED or (
            not human and await get_run_status(rt.sessionmaker, rid) == RunStatus.CANCELLED
        ):
            await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
            return STOP
        trace_id = await get_run_trace_id(rt.sessionmaker, rid)
        bind_log_context(run_id=str(rid), trace_id=trace_id)
        async with track_step(
            rt.sessionmaker, run_id=rid, attempt_id=aid, step_name=step_name, trace_id=trace_id, agent_name=agent_name
        ) as handle:
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
                not human and await get_run_status(rt.sessionmaker, rid) == RunStatus.CANCELLED
            ):
                await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
                return STOP
            return {"cancelled": False, **output}

    return await DBOS.run_step_async(step_options(step_name, retries=retries), execute)


async def fail_workflow(
    *,
    workflow_name: str,
    run_id: str | None,
    article_id: str | None,
    error: BaseException,
    version_id: str | None = None,
) -> None:
    rt = get_runtime()
    workflow_id = DBOS.workflow_id
    if not workflow_id:
        return
    if (
        isinstance(error, (WorkflowCancelledError, asyncio.CancelledError))
        or await get_attempt_status(rt.sessionmaker, workflow_id) == AttemptStatus.CANCELLED
    ):
        await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
        return
    payload = {"class": type(error).__name__, "message": str(error)[:2000]}

    async def failed() -> None:
        rid = uuid.UUID(run_id) if run_id else None
        stale = isinstance(error, StaleWorkflowError)
        async with rt.sessionmaker() as db:
            attempt = await db.scalar(select(RunAttempt).where(RunAttempt.dbos_workflow_id == workflow_id))
            if attempt is None or attempt.status == "CANCELLED":
                return
            rid = rid or attempt.run_id
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
            if article is not None:
                stale = stale or (version_id is not None and str(article.current_version_id) != version_id)
                target = ArticleStatus.PUBLISH_FAILED if article.status == "PUBLISHING" else ArticleStatus.FAILED
                if not stale and can_transition(Entity.ARTICLE, article.status, target):
                    await set_article_status(db, article_id=article.id, target=target)
            await db.commit()
        if rid and not stale and workflow_name not in HUMAN_ACTION_WORKFLOWS:
            with contextlib.suppress(InvalidTransition, LookupError):
                await set_run_status(rt.sessionmaker, run_id=rid, target=RunStatus.FAILED, error=payload)
        await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.FAILED, error=payload)

    prefix = (
        "recheck"
        if workflow_name == "recheck_article"
        else "publish"
        if workflow_name == "publish_article"
        else "discover"
        if workflow_name == "discover_topics"
        else "produce"
        if workflow_name == "produce_article"
        else workflow_name
    )
    await DBOS.run_step_async(step_options(f"{prefix}.mark_failed"), failed)
