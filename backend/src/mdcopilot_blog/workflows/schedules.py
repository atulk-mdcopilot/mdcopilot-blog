"""Daily generation schedule.

A DBOS cron schedule fires `daily_trigger`, which creates at most one daily run per local date and enqueues the
target pipeline on the `pipeline` queue under the workflow id `daily-<YYYY-MM-DD>`. The queue runs one pipeline
at a time, so a daily run never overlaps a manual run. While BLOG_AGENT_SCHEDULER_ENABLED=false the schedule
exists but is PAUSED.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import date, datetime, time
from typing import Any, cast
from zoneinfo import ZoneInfo

from dbos import DBOS, ScheduleInput, SetWorkflowID, SetWorkflowTimeout
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import RunKind, RunStatus
from mdcopilot_blog.ids import new_trace_id, uuid7
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.discover import discover_topics
from mdcopilot_blog.workflows.names import (
    QUEUE_PIPELINE,
    SCHEDULE_DAILY,
    STEP_DAILY_CREATE_RUN,
    WORKFLOW_DAILY_TRIGGER,
)
from mdcopilot_blog.workflows.runtime import get_runtime

logger = logging.getLogger(__name__)

MANUAL_RUN_FINAL_STATUSES = (RunStatus.FAILED.value, RunStatus.CANCELLED.value)


def daily_child_workflow_id(local_date: date) -> str:
    return f"daily-{local_date.isoformat()}"


def _slot_time(settings: Settings) -> time:
    hour, minute = settings.daily_run_time.split(":")
    return time(hour=int(hour), minute=int(minute))


def daily_cron(settings: Settings) -> str:
    slot = _slot_time(settings)
    return f"{slot.minute} {slot.hour} * * *"


async def _daily_run(session: AsyncSession, run_date: date) -> tuple[uuid.UUID, str] | None:
    row = (
        await session.execute(
            select(BlogRun.id, BlogRun.status).where(BlogRun.kind == RunKind.DAILY.value, BlogRun.run_date == run_date)
        )
    ).first()
    return None if row is None else (row[0], row[1])


@DBOS.step(name=STEP_DAILY_CREATE_RUN)
async def create_daily_run_step(run_date_iso: str) -> str | None:
    """Return the id of the daily run to start for `run_date_iso`, inserting the run if the date has none.

    A daily run that is still QUEUED is returned again. DBOS re-executes this step when the worker dies after
    the insert committed but before the step's output was recorded, and that run still needs its workflow
    (enqueueing `daily-<date>` a second time returns the existing workflow). Returns None when the date's daily
    run has left QUEUED, or when the date has no daily run and a manual run for it is active.
    """
    rt = get_runtime()
    run_date = date.fromisoformat(run_date_iso)
    async with rt.sessionmaker() as session:
        existing = await _daily_run(session, run_date)
        if existing is None:
            active_manual = await session.scalar(
                select(func.count())
                .select_from(BlogRun)
                .where(
                    BlogRun.kind == RunKind.MANUAL.value,
                    BlogRun.run_date == run_date,
                    BlogRun.status.not_in(MANUAL_RUN_FINAL_STATUSES),
                )
            )
            if active_manual:
                logger.info("daily run skipped: a manual run for this date is active", extra={"run_date": run_date_iso})
                return None
            stmt = (
                insert(BlogRun)
                .values(
                    id=uuid7(),
                    kind=RunKind.DAILY.value,
                    run_date=run_date,
                    status=RunStatus.QUEUED.value,
                    params={"source": "schedule"},
                    trace_id=new_trace_id(),
                )
                .on_conflict_do_nothing(index_elements=["run_date"], index_where=text("kind = 'daily'"))
                .returning(BlogRun.id)
            )
            inserted = await session.scalar(stmt)
            await session.commit()
            if inserted is not None:
                return str(inserted)
            existing = await _daily_run(session, run_date)  # another trigger inserted it first
    if existing is not None and existing[1] == RunStatus.QUEUED.value:
        logger.info("daily run is still queued; starting its workflow", extra={"run_date": run_date_iso})
        return str(existing[0])
    logger.info("daily run skipped: this date already has a daily run", extra={"run_date": run_date_iso})
    return None


@DBOS.workflow(name=WORKFLOW_DAILY_TRIGGER)
async def daily_trigger(scheduled_at: datetime, context: Any) -> str | None:
    from mdcopilot_blog.workflows.automation import effective_schedule_settings

    effective = await effective_schedule_settings()
    if not effective.scheduler_enabled or not effective.agent_enabled:
        return None
    local_date = scheduled_at.astimezone(ZoneInfo(effective.timezone)).date()
    run_id = await create_daily_run_step(local_date.isoformat())
    if run_id is None:
        return None
    # Same workflow timeout as a manual discovery run (services/runs.py).
    timeout_seconds = get_runtime().settings.discovery_timeout_minutes * 60
    # Enqueued, not started: the pipeline queue (worker_concurrency=1) runs it after any in-flight run.
    # The trigger does not wait for the child, so it frees its own slot on that queue straight away.
    with SetWorkflowID(daily_child_workflow_id(local_date)), SetWorkflowTimeout(timeout_seconds):
        handle = await DBOS.enqueue_workflow_async(QUEUE_PIPELINE, discover_topics, run_id)
    logger.info("daily run enqueued", extra={"run_id": run_id, "context": context})
    return handle.get_workflow_id()


async def apply_daily_schedule(settings: Settings) -> None:
    """Create or replace the daily schedule, then pause or resume it to match BLOG_AGENT_SCHEDULER_ENABLED.

    DBOS keeps a schedule's status on replace, so the status is always set explicitly. dbos 3.0.0 has no
    pause_schedule_async/resume_schedule_async (checked with dir(DBOS)); the sync calls run off the event loop.
    """
    # ScheduleInput types workflow_fn as returning None; DBOS ignores the child id our trigger returns.
    trigger = cast("Callable[[datetime, Any], Coroutine[Any, Any, None]]", daily_trigger)
    schedule: ScheduleInput = {
        "schedule_name": SCHEDULE_DAILY,
        "workflow_fn": trigger,
        "schedule": daily_cron(settings),
        "context": {"source": "schedule"},
        "automatic_backfill": False,
        "cron_timezone": settings.timezone,
        "queue_name": QUEUE_PIPELINE,
    }
    await DBOS.apply_schedules_async([schedule])
    if settings.scheduler_enabled:
        await asyncio.to_thread(DBOS.resume_schedule, SCHEDULE_DAILY)
    else:
        await asyncio.to_thread(DBOS.pause_schedule, SCHEDULE_DAILY)
    logger.info(
        "daily schedule applied",
        extra={"cron": daily_cron(settings), "timezone": settings.timezone, "enabled": settings.scheduler_enabled},
    )


async def catch_up_today(settings: Settings, now: datetime) -> str | None:
    """Start today's daily trigger if the slot already passed and nothing ran for today (same day only)."""
    if not settings.scheduler_enabled:
        return None
    tz = ZoneInfo(settings.timezone)
    local_now = now.astimezone(tz)
    slot = datetime.combine(local_now.date(), _slot_time(settings), tzinfo=tz)
    if local_now < slot:
        return None
    existing = await DBOS.list_workflows_async(
        workflow_ids=[daily_child_workflow_id(slot.date())], load_input=False, load_output=False
    )
    if existing:
        return None
    with SetWorkflowID(f"catchup-{slot.date().isoformat()}"):
        handle = await DBOS.start_workflow_async(daily_trigger, slot, {"source": "catch_up"})
    logger.info("daily catch-up started", extra={"workflow_id": handle.get_workflow_id()})
    return handle.get_workflow_id()
