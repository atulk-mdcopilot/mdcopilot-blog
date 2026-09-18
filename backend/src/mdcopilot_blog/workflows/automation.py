"""Schedule application, due publication, bounded nightly maintenance and controls."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from dbos import DBOS, ScheduleInput
from sqlalchemy import select

from mdcopilot_blog.db.models import Article, RunAttempt
from mdcopilot_blog.research.feed_health import roll_up_feed_health
from mdcopilot_blog.services.config import load_effective_config
from mdcopilot_blog.services.external_posts import sync_mdcopilot_posts
from mdcopilot_blog.services.publication_steps import process_due_article, select_due_articles
from mdcopilot_blog.services.step_context import build_api_step_context
from mdcopilot_blog.workflows.names import (
    QUEUE_INTERACTIVE,
    QUEUE_PIPELINE,
    WORKFLOW_APPLY_SCHEDULE,
    WORKFLOW_CONTROL,
    WORKFLOW_DAILY_TRIGGER,
    WORKFLOW_DISCOVER_TOPICS,
    WORKFLOW_MAINTENANCE,
    WORKFLOW_PRODUCE_ARTICLE,
    WORKFLOW_PUBLISH_DUE,
    WORKFLOW_REGENERATE_TOPICS,
)
from mdcopilot_blog.workflows.retry import step_options
from mdcopilot_blog.workflows.runtime import get_runtime


async def effective_schedule_settings() -> Any:
    rt = get_runtime()
    async with rt.sessionmaker() as db:
        config = await load_effective_config(db, rt.settings)
    return rt.settings.model_copy(update={"daily_run_time": config.schedule.time, "timezone": config.schedule.timezone})


@DBOS.workflow(name=WORKFLOW_APPLY_SCHEDULE)
async def apply_schedule() -> None:
    from mdcopilot_blog.workflows.schedules import apply_daily_schedule

    async def apply() -> None:
        settings = await effective_schedule_settings()
        await apply_daily_schedule(settings)
        await apply_maintenance_schedules(settings.timezone)

    await DBOS.run_step_async(step_options("apply_schedule.apply"), apply)


@DBOS.workflow(name=WORKFLOW_PUBLISH_DUE)
async def publish_due(scheduled_at: datetime, context: Any) -> list[dict[str, Any]]:
    rt = get_runtime()

    async def select_due() -> list[str]:
        async with rt.sessionmaker() as db:
            return [str(a.article_id) for a in await select_due_articles(db, now=scheduled_at)]

    ids = await DBOS.run_step_async(step_options("publish_due.select_due"), select_due)
    outcomes = []
    for article_id in ids:

        async def process(article_id: str = article_id) -> dict[str, Any]:

            async with rt.sessionmaker() as db:
                config = await load_effective_config(db, rt.settings)
            return (
                await process_due_article(
                    rt.sessionmaker,
                    settings=rt.settings,
                    config=config,
                    article_id=uuid.UUID(article_id),
                    now=scheduled_at,
                )
            ).model_dump(mode="json")

        outcome = await DBOS.run_step_async(
            step_options("publish_due.process_due", retries=False, timeout_seconds=180), process
        )
        outcomes.append(outcome)

    return outcomes


@DBOS.workflow(name=WORKFLOW_MAINTENANCE)
async def maintenance(scheduled_at: datetime, context: Any) -> dict[str, Any]:
    rt = get_runtime()

    async def sync() -> dict[str, Any]:
        sc = await build_api_step_context(
            settings=rt.settings, sessionmaker=rt.sessionmaker, run_id=None, article_id=None
        )
        return (await sync_mdcopilot_posts(sc, now=scheduled_at)).model_dump(mode="json")

    async def health() -> dict[str, Any]:
        return (await roll_up_feed_health(rt.sessionmaker, settings=rt.settings, now=scheduled_at)).model_dump(
            mode="json"
        )

    async def prune() -> dict[str, Any]:
        cutoff = datetime.now(UTC) - timedelta(days=rt.settings.dbos_retention_days)
        rows = await DBOS.list_workflows_async(
            status=["SUCCESS", "ERROR", "CANCELLED"],
            completed_before=cutoff.isoformat(),
            limit=200,
            load_input=False,
            load_output=False,
        )
        # Keep parents of recoverable children and ancestors used by forks.
        ids = []
        for row in rows:
            children = await DBOS.list_workflows_async(
                parent_workflow_id=row.workflow_id,
                status=["PENDING", "ENQUEUED"],
                limit=1,
                load_input=False,
                load_output=False,
            )
            forks = await DBOS.list_workflows_async(
                forked_from=row.workflow_id, limit=1, load_input=False, load_output=False
            )
            if not children and not forks:
                ids.append(row.workflow_id)
        if ids:
            await DBOS.delete_workflows_async(ids, delete_children=False)
        return {"pruned": len(ids)}

    result = {
        "posts": await DBOS.run_step_async(step_options("maintenance.sync_posts", timeout_seconds=300), sync),
        "feeds": await DBOS.run_step_async(step_options("maintenance.feed_health", timeout_seconds=180), health),
    }
    result["retention"] = await DBOS.run_step_async(step_options("maintenance.prune_dbos", timeout_seconds=120), prune)

    return result


@DBOS.workflow(name=WORKFLOW_CONTROL)
async def control(action: str, workflow_id: str, step_name: str | None) -> str | None:
    async def execute() -> str | None:
        if action == "cancel":
            await DBOS.cancel_workflow_async(workflow_id)
            return None
        if action != "fork":
            raise ValueError("unknown control action")
        steps = await DBOS.list_workflow_steps_async(workflow_id)
        selected = [s["function_id"] for s in steps if s["function_name"] == step_name]
        if not selected:
            raise LookupError("step not found")
        rows = await DBOS.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
        if not rows:
            raise LookupError("workflow history was pruned")
        name = rows[0].name
        rt = get_runtime()
        async with rt.sessionmaker() as db:
            attempt = await db.scalar(select(RunAttempt).where(RunAttempt.dbos_workflow_id == workflow_id))
            if attempt and name not in {"publish_article", "recheck_article"}:
                protected = await db.scalar(
                    select(Article.id)
                    .where(
                        Article.run_id == attempt.run_id,
                        Article.status.in_(
                            ["APPROVED", "SCHEDULED", "EXPORTED", "PUBLISHING", "PUBLISHED", "PUBLISH_FAILED"]
                        ),
                    )
                    .limit(1)
                )
                if protected:
                    raise ValueError("cannot fork generation of an approved or published article")
        pipeline = name in {WORKFLOW_DISCOVER_TOPICS, WORKFLOW_PRODUCE_ARTICLE, WORKFLOW_DAILY_TRIGGER}
        handle = await DBOS.fork_workflow_async(
            workflow_id,
            max(selected),
            application_version=get_runtime().settings.app_version,
            queue_name=QUEUE_PIPELINE if pipeline else QUEUE_INTERACTIVE,
            timeout_seconds=(
                rt.settings.discovery_timeout_minutes
                if name in {WORKFLOW_DISCOVER_TOPICS, WORKFLOW_REGENERATE_TOPICS}
                else rt.settings.production_timeout_minutes
            )
            * 60,
        )
        return handle.get_workflow_id()

    return await DBOS.run_step_async(step_options("control.control", retries=False), execute)


async def apply_maintenance_schedules(timezone: str) -> None:
    schedules: list[ScheduleInput] = [
        {
            "schedule_name": "publish_due",
            "workflow_fn": cast(Any, publish_due),
            "schedule": "*/5 * * * *",
            "cron_timezone": "UTC",
            "queue_name": QUEUE_INTERACTIVE,
            "automatic_backfill": False,
            "context": {},
        },
        {
            "schedule_name": "maintenance_nightly",
            "workflow_fn": cast(Any, maintenance),
            "schedule": "30 2 * * *",
            "cron_timezone": timezone,
            "queue_name": QUEUE_INTERACTIVE,
            "automatic_backfill": False,
            "context": {},
        },
    ]
    await DBOS.apply_schedules_async(schedules)
    for schedule in schedules:
        await asyncio.to_thread(DBOS.resume_schedule, schedule["schedule_name"])
