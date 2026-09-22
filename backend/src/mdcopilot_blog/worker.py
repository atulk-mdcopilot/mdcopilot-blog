"""Worker process: the only process that launches DBOS and executes workflows.

Run with `python -m mdcopilot_blog.worker` (compose service `worker`).
"""

import asyncio
import contextlib
import logging
import os
import signal
from pathlib import Path

from dbos import DBOS

from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.settings import Settings, get_settings
from mdcopilot_blog.workflows import discover  # noqa: F401 -- register workflows before DBOS launch
from mdcopilot_blog.workflows.dbos_config import build_dbos_config
from mdcopilot_blog.workflows.names import HEARTBEAT_FILE, QUEUE_PIPELINE
from mdcopilot_blog.workflows.runtime import build_runtime, set_runtime

logger = logging.getLogger("mdcopilot_blog.worker")

HEARTBEAT_INTERVAL_SECONDS = 10.0
# compose stop_grace_period (60 s) must stay above this
WORKFLOW_COMPLETION_TIMEOUT_SECONDS = 25
PIPELINE_CONCURRENCY = 1


async def heartbeat_loop(
    stop: asyncio.Event, path: Path = HEARTBEAT_FILE, interval: float = HEARTBEAT_INTERVAL_SECONDS
) -> None:
    """Touch `path` every `interval` seconds until `stop` is set. A stale file means the event loop is stuck."""
    while not stop.is_set():
        path.touch()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)


def install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)


async def _run_dbos(settings: Settings, stop: asyncio.Event) -> None:
    rt = await build_runtime(settings)
    launched = False
    try:
        async with rt.sessionmaker() as session:
            inserted = await rt.prompts.sync_to_db(session)  # fails fast on a changed prompt without a version bump
            await session.commit()
        logger.info("prompts synced", extra={"inserted": inserted})
        set_runtime(rt)

        DBOS(config=build_dbos_config(settings))
        DBOS.launch()  # sync; dequeued async workflows then run on this event loop
        launched = True
        logger.info(
            "DBOS launched",
            extra={"executor_id": settings.worker_executor_id, "application_version": settings.app_version},
        )
        # dbos 3.0: a queue can only be registered after launch
        await DBOS.register_queue_async(QUEUE_PIPELINE, worker_concurrency=PIPELINE_CONCURRENCY)

        heartbeat = asyncio.create_task(heartbeat_loop(stop))
        logger.info("worker ready")
        await stop.wait()
        logger.info("shutdown requested; waiting for running workflows")
        await heartbeat
    finally:
        if launched:
            # DBOS.destroy is synchronous and polls with time.sleep; running it on this loop would freeze the
            # async workflows it is waiting for, so it runs in a thread.
            await asyncio.to_thread(DBOS.destroy, workflow_completion_timeout_sec=WORKFLOW_COMPLETION_TIMEOUT_SECONDS)
            logger.info("DBOS destroyed")
        set_runtime(None)
        await rt.engine.dispose()


async def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)
    stop = asyncio.Event()
    install_signal_handlers(stop)
    if not settings.agent_enabled:
        logger.warning("agent disabled (BLOG_AGENT_ENABLED=false); worker is idle and DBOS is not launched")
        await heartbeat_loop(stop)
        return
    await _run_dbos(settings, stop)
    logger.info("worker stopped")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
