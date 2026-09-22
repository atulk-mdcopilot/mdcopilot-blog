"""The api's only door to DBOS: enqueue and cancel workflows by name through DBOSClient (never DBOS.launch())."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dbos import DBOSClient, EnqueueOptions, WorkflowHandleAsync

if TYPE_CHECKING:
    from mdcopilot_blog.settings import Settings

DBOS_SYSTEM_SCHEMA = "blog_dbos"  # blog_ namespace in the shared mdcopilot-backend database
DBOS_APPLICATION_NAME = "mdcopilot-blog"


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

    def close(self) -> None:
        self._client.destroy()
