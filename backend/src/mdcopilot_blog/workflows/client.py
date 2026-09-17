"""The api's only door to DBOS: enqueue and manage workflows by name through DBOSClient (never DBOS.launch())."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from dbos import DBOSClient, EnqueueOptions, WorkflowHandleAsync

if TYPE_CHECKING:
    from mdcopilot_blog.settings import Settings

DBOS_SYSTEM_SCHEMA = "dbos"
DBOS_APPLICATION_NAME = "mdcopilot-blog"


@dataclass(frozen=True)
class StepView:
    function_id: int
    function_name: str
    started_at_epoch_ms: int | None
    completed_at_epoch_ms: int | None
    error: str | None


class WorkflowClientProtocol(Protocol):
    async def enqueue(
        self,
        *,
        workflow_name: str,
        queue_name: str,
        workflow_id: str,
        args: tuple[object, ...],
        timeout_seconds: float | None,
    ) -> str: ...

    async def cancel(self, workflow_id: str) -> None: ...

    async def list_steps(self, workflow_id: str) -> list[StepView]: ...

    async def status(self, workflow_id: str) -> str | None: ...

    async def fork_from_step(self, workflow_id: str, step_name: str, *, queue_name: str) -> str: ...

    def close(self) -> None: ...


def _latest_function_id(steps: list[StepView], workflow_id: str, step_name: str) -> int:
    """A step name can repeat (loops, retries); fork from its most recent execution."""
    ids = [step.function_id for step in steps if step.function_name == step_name]
    if not ids:
        raise LookupError(f"step {step_name!r} not found in workflow {workflow_id!r}")
    return max(ids)


class WorkflowClient(WorkflowClientProtocol):
    """Async wrapper over DBOSClient. Only *_async client methods are used, so the event loop never blocks."""

    def __init__(self, client: DBOSClient, app_version: str) -> None:
        self._client = client
        self._app_version = app_version

    @classmethod
    def from_settings(cls, settings: Settings) -> WorkflowClient:
        client = DBOSClient(
            system_database_url=settings.dbos_system_database_url,
            dbos_system_schema=DBOS_SYSTEM_SCHEMA,
            application_name=DBOS_APPLICATION_NAME,
            lazy=True,
        )
        return cls(client, settings.app_version)

    async def enqueue(
        self,
        *,
        workflow_name: str,
        queue_name: str,
        workflow_id: str,
        args: tuple[object, ...],
        timeout_seconds: float | None,
    ) -> str:
        options: EnqueueOptions = {
            "queue_name": queue_name,
            "workflow_name": workflow_name,
            "workflow_id": workflow_id,
            # Must equal the worker's application_version, or the workflow stays ENQUEUED forever.
            "app_version": self._app_version,
        }
        if timeout_seconds is not None:
            options["workflow_timeout"] = timeout_seconds
        handle: WorkflowHandleAsync[Any] = await self._client.enqueue_async(options, *args)
        return handle.get_workflow_id()

    async def cancel(self, workflow_id: str) -> None:
        await self._client.cancel_workflow_async(workflow_id)

    async def list_steps(self, workflow_id: str) -> list[StepView]:
        # load_output=True is required: with False, DBOS also drops the step error.
        steps = await self._client.list_workflow_steps_async(workflow_id)
        return [
            StepView(
                function_id=step["function_id"],
                function_name=step["function_name"],
                started_at_epoch_ms=step["started_at_epoch_ms"],
                completed_at_epoch_ms=step["completed_at_epoch_ms"],
                error=None if step["error"] is None else f"{type(step['error']).__name__}: {step['error']}",
            )
            for step in steps
        ]

    async def status(self, workflow_id: str) -> str | None:
        rows = await self._client.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
        return rows[0].status if rows else None

    async def fork_from_step(self, workflow_id: str, step_name: str, *, queue_name: str) -> str:
        steps = await self._client.list_workflow_steps_async(workflow_id, load_output=False)
        views = [StepView(step["function_id"], step["function_name"], None, None, None) for step in steps]
        start_step = _latest_function_id(views, workflow_id, step_name)
        handle = await self._client.fork_workflow_async(
            workflow_id, start_step, application_version=self._app_version, queue_name=queue_name
        )
        return handle.get_workflow_id()

    def close(self) -> None:
        self._client.destroy()


@dataclass(frozen=True)
class EnqueueCall:
    workflow_name: str
    queue_name: str
    workflow_id: str
    args: tuple[object, ...]
    timeout_seconds: float | None


@dataclass(frozen=True)
class ForkCall:
    workflow_id: str
    step_name: str
    start_step: int
    queue_name: str
    new_workflow_id: str


@dataclass
class FakeWorkflowClient(WorkflowClientProtocol):
    """In-memory stand-in for API tests. Records every call; ids are deterministic."""

    enqueued: list[EnqueueCall] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    forked: list[ForkCall] = field(default_factory=list)
    statuses: dict[str, str] = field(default_factory=dict)
    steps: dict[str, list[StepView]] = field(default_factory=dict)
    enqueue_error: Exception | None = None
    closed: bool = False

    async def enqueue(
        self,
        *,
        workflow_name: str,
        queue_name: str,
        workflow_id: str,
        args: tuple[object, ...],
        timeout_seconds: float | None,
    ) -> str:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.enqueued.append(EnqueueCall(workflow_name, queue_name, workflow_id, tuple(args), timeout_seconds))
        self.statuses.setdefault(workflow_id, "ENQUEUED")
        return workflow_id

    async def cancel(self, workflow_id: str) -> None:
        self.cancelled.append(workflow_id)
        self.statuses[workflow_id] = "CANCELLED"

    async def list_steps(self, workflow_id: str) -> list[StepView]:
        return list(self.steps.get(workflow_id, []))

    async def status(self, workflow_id: str) -> str | None:
        return self.statuses.get(workflow_id)

    async def fork_from_step(self, workflow_id: str, step_name: str, *, queue_name: str) -> str:
        start_step = _latest_function_id(self.steps.get(workflow_id, []), workflow_id, step_name)
        new_workflow_id = f"{workflow_id}-fork-{len(self.forked) + 1}"
        self.forked.append(ForkCall(workflow_id, step_name, start_step, queue_name, new_workflow_id))
        self.statuses[new_workflow_id] = "ENQUEUED"
        return new_workflow_id

    def close(self) -> None:
        self.closed = True
