"""The in-process DBOS worker used by workflow tests, and the worker's DBOS configuration."""

import asyncio
import uuid

from dbos import DBOS, SetWorkflowID

from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.dbos_config import build_dbos_config
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE
from mdcopilot_blog.workflows.runtime import WorkerRuntime, get_runtime


@DBOS.step(name="test.probe_step")
async def probe_step(value: int) -> dict[str, object]:
    return {
        "workflow_id": DBOS.workflow_id,
        "step_id": DBOS.step_id,
        "value": value,
        "runtime_db": get_runtime().settings.postgres_db,
    }


@DBOS.workflow(name="test.probe_workflow")
async def probe_workflow(value: int) -> dict[str, object]:
    return await probe_step(value)


async def test_dbos_runs_a_queued_workflow_on_the_pytest_loop(dbos_runtime: WorkerRuntime) -> None:
    assert DBOS.executor_id == "pytest"
    assert DBOS.application_version == "pytest"
    workflow_id = f"probe-{uuid.uuid4().hex}"
    with SetWorkflowID(workflow_id):
        handle = await DBOS.enqueue_workflow_async(QUEUE_PIPELINE, probe_workflow, 7)
    result = await asyncio.wait_for(handle.get_result(), timeout=30)
    assert result == {"workflow_id": workflow_id, "step_id": 1, "value": 7, "runtime_db": "mdcopilot_blog_test"}


def test_build_dbos_config_pins_recovery_identity(settings: Settings) -> None:
    custom = settings.model_copy(update={"app_version": "9.9.9", "worker_executor_id": "worker-7"})
    config = build_dbos_config(custom)
    assert config["name"] == "mdcopilot-blog"
    assert config["application_version"] == "9.9.9"
    assert config["executor_id"] == "worker-7"
    assert config["dbos_system_schema"] == "dbos"
    assert config["system_database_url"] == custom.dbos_system_database_url
    assert config["system_database_url"].startswith("postgresql+psycopg://")
