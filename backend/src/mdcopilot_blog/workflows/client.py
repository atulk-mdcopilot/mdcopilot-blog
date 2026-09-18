"""The api's only door to DBOS: enqueue and manage workflows by name through DBOSClient (never DBOS.launch())."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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


@dataclass(frozen=True)
class WorkflowDescription:
    status: str
    app_version: str | None
    name: str


class WorkflowClient:
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

    async def describe(self, workflow_id: str) -> WorkflowDescription | None:
        rows = await self._client.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
        return WorkflowDescription(rows[0].status, rows[0].app_version, rows[0].name) if rows else None

    async def fork_from_function_id(
        self, workflow_id: str, start_step: int, *, queue_name: str, timeout_seconds: float | None
    ) -> str:
        handle = await self._client.fork_workflow_async(
            workflow_id,
            start_step,
            application_version=self._app_version,
            queue_name=queue_name,
            timeout_seconds=timeout_seconds,
        )
        return handle.get_workflow_id()

    def close(self) -> None:
        self._client.destroy()
