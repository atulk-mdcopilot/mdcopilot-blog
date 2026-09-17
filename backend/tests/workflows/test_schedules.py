"""Daily schedule: cron formatting, idempotent daily run creation, trigger child ids, pause state, catch-up."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from dbos import DBOS
from sqlalchemy import select

from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import RunKind, RunStatus
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, SCHEDULE_DAILY, WORKFLOW_DAILY_TRIGGER
from mdcopilot_blog.workflows.runtime import WorkerRuntime
from mdcopilot_blog.workflows.schedules import (
    apply_daily_schedule,
    catch_up_today,
    create_daily_run_step,
    daily_cron,
    daily_trigger,
)

type MakeRun = Callable[..., Awaitable[uuid.UUID]]

IST = ZoneInfo("Asia/Kolkata")
WAIT_SECONDS = 60


async def wait_for_result(workflow_id: str) -> Any:
    handle = await DBOS.retrieve_workflow_async(workflow_id)
    return await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS)


async def daily_runs(rt: WorkerRuntime, run_date: date) -> list[BlogRun]:
    async with rt.sessionmaker() as session:
        rows = await session.scalars(
            select(BlogRun).where(BlogRun.kind == RunKind.DAILY.value, BlogRun.run_date == run_date)
        )
        return list(rows.all())


@pytest.mark.parametrize(
    ("run_time", "expected"),
    [("07:00", "0 7 * * *"), ("23:59", "59 23 * * *"), ("00:05", "5 0 * * *"), ("18:30", "30 18 * * *")],
)
def test_daily_cron_formats_minute_then_hour(settings: Settings, run_time: str, expected: str) -> None:
    assert daily_cron(settings.model_copy(update={"daily_run_time": run_time})) == expected


async def test_create_daily_run_step_is_idempotent_per_date(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    first = await create_daily_run_step("2026-02-10")
    second = await create_daily_run_step("2026-02-10")  # a re-executed step gets the same, still queued, run
    assert first is not None
    assert second == first
    [run] = await daily_runs(dbos_runtime, date(2026, 2, 10))
    assert str(run.id) == first
    assert (run.status, run.params) == ("QUEUED", {"source": "schedule"})
    assert len(run.trace_id) == 32


async def test_create_daily_run_step_skips_date_with_active_manual_run(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    await make_run(kind=RunKind.MANUAL, run_date=date(2026, 2, 11), status=RunStatus.PRODUCING)
    assert await create_daily_run_step("2026-02-11") is None
    assert await daily_runs(dbos_runtime, date(2026, 2, 11)) == []


async def test_create_daily_run_step_ignores_failed_or_cancelled_manual_runs(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    await make_run(kind=RunKind.MANUAL, run_date=date(2026, 2, 12), status=RunStatus.FAILED)
    await make_run(kind=RunKind.MANUAL, run_date=date(2026, 2, 12), status=RunStatus.CANCELLED)
    assert await create_daily_run_step("2026-02-12") is not None
    assert len(await daily_runs(dbos_runtime, date(2026, 2, 12))) == 1


async def test_daily_trigger_starts_child_named_after_the_local_date(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    # 20:00 UTC on 1 March is 01:30 on 2 March in Asia/Kolkata
    child_id = await daily_trigger(datetime(2026, 3, 1, 20, 0, tzinfo=UTC), {"source": "test"})
    assert child_id == "daily-2026-03-02"
    result = await wait_for_result(child_id)
    [run] = await daily_runs(dbos_runtime, date(2026, 3, 2))
    assert result["run_id"] == str(run.id)
    assert run.status == "SUCCEEDED"
    [child] = await DBOS.list_workflows_async(workflow_ids=[child_id], load_input=False, load_output=False)
    assert child.queue_name == QUEUE_PIPELINE  # enqueued behind any in-flight run, never started beside it
    assert child.workflow_timeout_ms == dbos_runtime.settings.production_timeout_minutes * 60 * 1000

    again = await daily_trigger(datetime(2026, 3, 2, 7, 0, tzinfo=IST), {"source": "test"})
    assert again is None
    assert len(await daily_runs(dbos_runtime, date(2026, 3, 2))) == 1


async def test_daily_trigger_starts_the_workflow_of_a_still_queued_daily_run(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    # the worker died after create_daily_run_step's insert committed but before DBOS recorded its output
    orphan = await make_run(kind=RunKind.DAILY, run_date=date(2026, 3, 5), status=RunStatus.QUEUED)
    assert await create_daily_run_step("2026-03-05") == str(orphan)

    child_id = await daily_trigger(datetime(2026, 3, 5, 7, 0, tzinfo=IST), {"source": "test"})
    assert child_id == "daily-2026-03-05"
    assert (await wait_for_result(child_id))["run_id"] == str(orphan)
    [run] = await daily_runs(dbos_runtime, date(2026, 3, 5))
    assert (run.id, run.status) == (orphan, "SUCCEEDED")
    assert await create_daily_run_step("2026-03-05") is None  # the run has left QUEUED


async def test_apply_daily_schedule_is_paused_when_scheduler_disabled(dbos_runtime: WorkerRuntime) -> None:
    disabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": False, "daily_run_time": "07:00"})
    await apply_daily_schedule(disabled)

    schedule = await DBOS.get_schedule_async(SCHEDULE_DAILY)
    assert schedule is not None
    assert schedule["status"] == "PAUSED"
    assert schedule["workflow_name"] == WORKFLOW_DAILY_TRIGGER
    assert schedule["schedule"] == "0 7 * * *"
    assert schedule["cron_timezone"] == "Asia/Kolkata"
    assert schedule["queue_name"] == QUEUE_PIPELINE
    assert schedule["automatic_backfill"] is False
    listed = await DBOS.list_schedules_async(schedule_name_prefix=SCHEDULE_DAILY)
    assert [(s["schedule_name"], s["status"]) for s in listed] == [(SCHEDULE_DAILY, "PAUSED")]


async def test_apply_daily_schedule_follows_the_enabled_flag(dbos_runtime: WorkerRuntime) -> None:
    # a slot 12 hours away, so the schedule cannot fire while it is briefly active
    far_slot = (datetime.now(IST) + timedelta(hours=12)).strftime("%H:%M")
    enabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": True, "daily_run_time": far_slot})
    disabled = enabled.model_copy(update={"scheduler_enabled": False})
    try:
        await apply_daily_schedule(enabled)
        schedule = await DBOS.get_schedule_async(SCHEDULE_DAILY)
        assert schedule is not None
        assert (schedule["status"], schedule["schedule"]) == ("ACTIVE", daily_cron(enabled))
    finally:
        await apply_daily_schedule(disabled)
    schedule = await DBOS.get_schedule_async(SCHEDULE_DAILY)
    assert schedule is not None
    assert schedule["status"] == "PAUSED"


async def test_catch_up_today_does_nothing_when_disabled_or_before_the_slot(dbos_runtime: WorkerRuntime) -> None:
    disabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": False, "daily_run_time": "07:00"})
    enabled = disabled.model_copy(update={"scheduler_enabled": True})
    after_slot = datetime(2026, 4, 9, 5, 0, tzinfo=UTC)  # 10:30 IST
    before_slot = datetime(2026, 4, 9, 1, 0, tzinfo=UTC)  # 06:30 IST
    assert await catch_up_today(disabled, after_slot) is None
    assert await catch_up_today(enabled, before_slot) is None
    assert await DBOS.list_workflows_async(workflow_ids=["daily-2026-04-09"]) == []


async def test_catch_up_today_starts_missed_run_once(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    enabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": True, "daily_run_time": "07:00"})
    now = datetime(2026, 4, 10, 5, 0, tzinfo=UTC)  # 10:30 IST, slot 07:00 IST has passed
    trigger_id = await catch_up_today(enabled, now)
    assert trigger_id == "catchup-2026-04-10"
    assert await wait_for_result(trigger_id) == "daily-2026-04-10"
    await wait_for_result("daily-2026-04-10")
    [run] = await daily_runs(dbos_runtime, date(2026, 4, 10))
    assert run.status == "SUCCEEDED"

    assert await catch_up_today(enabled, now + timedelta(hours=1)) is None
