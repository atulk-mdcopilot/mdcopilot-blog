from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from dbos import DBOSClient

from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import (
    EnqueueCall,
    FakeWorkflowClient,
    ForkCall,
    StepView,
    WorkflowClient,
    WorkflowClientProtocol,
)
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_HELLO


@dataclass
class StubHandle:
    workflow_id: str

    def get_workflow_id(self) -> str:
        return self.workflow_id


@dataclass
class StubStatus:
    status: str


@dataclass
class StubDBOSClient:
    """Records calls with the exact DBOSClient 3.0 *_async signatures the wrapper uses."""

    steps: list[dict[str, Any]] = field(default_factory=list)
    rows: list[StubStatus] = field(default_factory=list)
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    destroyed: bool = False

    async def enqueue_async(self, options: dict[str, Any], *args: Any) -> StubHandle:
        self.calls.append(("enqueue_async", (dict(options), *args), {}))
        return StubHandle(options["workflow_id"])

    async def cancel_workflow_async(self, workflow_id: str) -> None:
        self.calls.append(("cancel_workflow_async", (workflow_id,), {}))

    async def list_workflow_steps_async(self, workflow_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_workflow_steps_async", (workflow_id,), kwargs))
        return self.steps

    async def list_workflows_async(self, **kwargs: Any) -> list[StubStatus]:
        self.calls.append(("list_workflows_async", (), kwargs))
        return self.rows

    async def fork_workflow_async(self, workflow_id: str, start_step: int, **kwargs: Any) -> StubHandle:
        self.calls.append(("fork_workflow_async", (workflow_id, start_step), kwargs))
        return StubHandle(f"forked-{workflow_id}-{start_step}")

    def destroy(self) -> None:
        self.destroyed = True


def _step(function_id: int, name: str, error: Exception | None = None) -> dict[str, Any]:
    return {
        "function_id": function_id,
        "function_name": name,
        "output": None,
        "error": error,
        "child_workflow_id": None,
        "started_at_epoch_ms": 1000 * function_id,
        "completed_at_epoch_ms": 1000 * function_id + 5,
    }


def _wrap(stub: StubDBOSClient) -> WorkflowClient:
    return WorkflowClient(cast(DBOSClient, stub), app_version="1.2.3")


async def test_enqueue_builds_enqueue_options() -> None:
    stub = StubDBOSClient()
    workflow_id = await _wrap(stub).enqueue(
        workflow_name=WORKFLOW_HELLO,
        queue_name=QUEUE_PIPELINE,
        workflow_id="manual-abc",
        args=("run-1",),
        timeout_seconds=1800.0,
    )
    assert workflow_id == "manual-abc"
    assert stub.calls == [
        (
            "enqueue_async",
            (
                {
                    "queue_name": "pipeline",
                    "workflow_name": "hello_pipeline",
                    "workflow_id": "manual-abc",
                    "app_version": "1.2.3",
                    "workflow_timeout": 1800.0,
                },
                "run-1",
            ),
            {},
        )
    ]


async def test_enqueue_without_timeout_omits_the_key() -> None:
    stub = StubDBOSClient()
    await _wrap(stub).enqueue(
        workflow_name=WORKFLOW_HELLO, queue_name=QUEUE_PIPELINE, workflow_id="w", args=(), timeout_seconds=None
    )
    options = stub.calls[0][1][0]
    assert "workflow_timeout" not in options
    assert options["app_version"] == "1.2.3"


async def test_cancel() -> None:
    stub = StubDBOSClient()
    await _wrap(stub).cancel("wf-1")
    assert stub.calls == [("cancel_workflow_async", ("wf-1",), {})]


async def test_list_steps_maps_step_info() -> None:
    stub = StubDBOSClient(steps=[_step(1, "hello.open_attempt"), _step(2, "hello.echo", ValueError("boom"))])
    views = await _wrap(stub).list_steps("wf-1")
    assert views == [
        StepView(1, "hello.open_attempt", 1000, 1005, None),
        StepView(2, "hello.echo", 2000, 2005, "ValueError: boom"),
    ]
    assert stub.calls == [("list_workflow_steps_async", ("wf-1",), {})]


async def test_status() -> None:
    assert await _wrap(StubDBOSClient(rows=[StubStatus("SUCCESS")])).status("wf-1") == "SUCCESS"
    stub = StubDBOSClient()
    assert await _wrap(stub).status("missing") is None
    assert stub.calls == [
        ("list_workflows_async", (), {"workflow_ids": ["missing"], "load_input": False, "load_output": False})
    ]


async def test_fork_from_step_uses_latest_function_id() -> None:
    stub = StubDBOSClient(
        steps=[_step(1, "research"), _step(2, "draft"), _step(3, "review"), _step(4, "draft"), _step(5, "seo")]
    )
    new_id = await _wrap(stub).fork_from_step("wf-1", "draft", queue_name="pipeline")
    assert new_id == "forked-wf-1-4"
    assert stub.calls[0] == ("list_workflow_steps_async", ("wf-1",), {"load_output": False})
    assert stub.calls[1] == (
        "fork_workflow_async",
        ("wf-1", 4),
        {"application_version": "1.2.3", "queue_name": "pipeline"},
    )


async def test_fork_from_unknown_step_raises_lookup_error() -> None:
    stub = StubDBOSClient(steps=[_step(1, "research")])
    with pytest.raises(LookupError, match="'draft' not found"):
        await _wrap(stub).fork_from_step("wf-1", "draft", queue_name="pipeline")
    assert [call[0] for call in stub.calls] == ["list_workflow_steps_async"]


def test_close_destroys_the_client() -> None:
    stub = StubDBOSClient()
    _wrap(stub).close()
    assert stub.destroyed is True


def test_from_settings_is_lazy(settings: Settings) -> None:
    # lazy=True: construction opens no connection, so an unreachable host is fine until first use.
    unreachable = settings.model_copy(update={"postgres_host": "unreachable.invalid"})
    client: WorkflowClientProtocol = WorkflowClient.from_settings(unreachable)
    assert isinstance(client, WorkflowClient)
    client.close()


async def test_fake_records_enqueue_and_cancel() -> None:
    fake = FakeWorkflowClient()
    assert (
        await fake.enqueue(
            workflow_name=WORKFLOW_HELLO,
            queue_name=QUEUE_PIPELINE,
            workflow_id="manual-1",
            args=("run-1",),
            timeout_seconds=60.0,
        )
        == "manual-1"
    )
    assert fake.enqueued == [EnqueueCall("hello_pipeline", "pipeline", "manual-1", ("run-1",), 60.0)]
    assert await fake.status("manual-1") == "ENQUEUED"
    await fake.cancel("manual-1")
    assert fake.cancelled == ["manual-1"]
    assert await fake.status("manual-1") == "CANCELLED"
    assert await fake.status("unknown") is None


async def test_fake_enqueue_error() -> None:
    fake = FakeWorkflowClient(enqueue_error=ConnectionError("dbos down"))
    with pytest.raises(ConnectionError):
        await fake.enqueue(workflow_name="w", queue_name="q", workflow_id="id", args=(), timeout_seconds=None)
    assert fake.enqueued == []


async def test_fake_steps_and_fork() -> None:
    fake = FakeWorkflowClient(steps={"wf": [StepView(1, "a", None, None, None), StepView(3, "a", None, None, None)]})
    assert [s.function_id for s in await fake.list_steps("wf")] == [1, 3]
    assert await fake.list_steps("other") == []
    assert await fake.fork_from_step("wf", "a", queue_name="pipeline") == "wf-fork-1"
    assert await fake.fork_from_step("wf", "a", queue_name="pipeline") == "wf-fork-2"
    assert fake.forked[0] == ForkCall("wf", "a", 3, "pipeline", "wf-fork-1")
    with pytest.raises(LookupError):
        await fake.fork_from_step("wf", "missing", queue_name="pipeline")


def test_fake_close() -> None:
    fake = FakeWorkflowClient()
    fake.close()
    assert fake.closed is True
