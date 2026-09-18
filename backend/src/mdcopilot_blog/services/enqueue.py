"""Enqueue helpers: commit database changes first, then enqueue."""

from dataclasses import dataclass

from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient


@dataclass(frozen=True)
class ActionAcceptedParts:
    workflow_id: str
    workflow_name: str
    queue: str


def ensure_agent_enabled(settings: Settings) -> None:
    if not settings.agent_enabled:
        raise ProblemError(409, "Agent disabled", "BLOG_AGENT_ENABLED is false, so new runs are rejected.")


async def enqueue_workflow(
    client: WorkflowClient,
    *,
    workflow_name: str,
    queue_name: str,
    workflow_id: str,
    args: tuple[object, ...],
    timeout_seconds: float | None,
) -> ActionAcceptedParts:
    """Enqueue through the workflow client; any failure is a 503 problem."""
    try:
        returned = await client.enqueue(
            workflow_name=workflow_name,
            queue_name=queue_name,
            workflow_id=workflow_id,
            args=args,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise ProblemError(503, "Workflow service unavailable", f"{workflow_name} was not enqueued") from exc
    return ActionAcceptedParts(workflow_id=returned, workflow_name=workflow_name, queue=queue_name)
