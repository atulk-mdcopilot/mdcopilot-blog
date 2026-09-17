"""WorkflowClient against the real dbos schema of the test database (migrated by the T5 database_url fixture)."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import URL

from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient


@pytest_asyncio.fixture(loop_scope="session")
async def real_client(settings: Settings, database_url: URL) -> AsyncIterator[WorkflowClient]:
    client = WorkflowClient.from_settings(settings)
    try:
        yield client
    finally:
        client.close()


async def test_unknown_workflow_has_no_status_or_steps(real_client: WorkflowClient) -> None:
    assert await real_client.status("does-not-exist") is None
    assert await real_client.list_steps("does-not-exist") == []


async def test_fork_of_unknown_workflow_raises_lookup_error(real_client: WorkflowClient) -> None:
    with pytest.raises(LookupError):
        await real_client.fork_from_step("does-not-exist", "hello.echo", queue_name="pipeline")


async def test_enqueue_writes_an_enqueued_row(real_client: WorkflowClient) -> None:
    # The row stays ENQUEUED (nobody consumes t9-probe-queue); cancelling then marks it CANCELLED.
    workflow_id = await real_client.enqueue(
        workflow_name="hello_pipeline",
        queue_name="t9-probe-queue",  # no worker listens here, so nothing runs it
        workflow_id="t9-enqueue-probe",
        args=("00000000-0000-0000-0000-000000000000",),
        timeout_seconds=60.0,
    )
    assert workflow_id == "t9-enqueue-probe"
    assert await real_client.status(workflow_id) == "ENQUEUED"
    await real_client.cancel(workflow_id)
    assert await real_client.status(workflow_id) == "CANCELLED"
