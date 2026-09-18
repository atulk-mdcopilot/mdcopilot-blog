"""Nightly source-snapshot retention, independently bounded and restartable."""

from datetime import UTC, datetime
from typing import Any, cast

from dbos import DBOS

from mdcopilot_blog.services.retention import purge_source_snapshots
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.names import QUEUE_INTERACTIVE
from mdcopilot_blog.workflows.retry import step_options
from mdcopilot_blog.workflows.runtime import get_runtime


@DBOS.workflow(name="snapshot_retention")
async def snapshot_retention(scheduled_at: datetime, context: Any) -> dict[str, Any]:
    async def purge() -> dict[str, Any]:
        rt = get_runtime()
        return (
            await purge_source_snapshots(rt.sessionmaker, settings=rt.settings, now=scheduled_at.astimezone(UTC))
        ).model_dump(mode="json")

    return await DBOS.run_step_async(step_options("snapshot_retention.purge", timeout_seconds=180), purge)


async def apply_retention_schedule(settings: Settings) -> None:
    await DBOS.apply_schedules_async(
        [
            {
                "schedule_name": "snapshot_retention_nightly",
                "workflow_fn": cast(Any, snapshot_retention),
                "schedule": "15 3 * * *",
                "context": None,
                "automatic_backfill": False,
                "cron_timezone": settings.timezone,
                "queue_name": QUEUE_INTERACTIVE,
            }
        ]
    )
