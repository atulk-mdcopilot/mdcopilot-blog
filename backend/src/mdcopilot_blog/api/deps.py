"""FastAPI dependencies: app state accessors and the internal service guard."""

import hmac
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient

# mdcopilot-backend users.id of the acting admin; stored as blog_runs.created_by.
_ON_BEHALF_OF = re.compile(r"[A-Za-z0-9_.:-]{1,64}")


def _state(request: Request, name: str) -> Any:
    """app.state first (set by create_app, the lifespan), then lifespan-provided request.state."""
    value = getattr(request.app.state, name, None)
    if value is None:
        value = getattr(request.state, name, None)
    if value is None:
        raise RuntimeError(f"application state {name!r} is not initialised")
    return value


def get_settings_dep(request: Request) -> Settings:
    return cast(Settings, _state(request, "settings"))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = cast(async_sessionmaker[AsyncSession], _state(request, "sessionmaker"))
    async with sessionmaker() as session:
        yield session


def get_workflow_client(request: Request) -> WorkflowClient:
    return cast(WorkflowClient, _state(request, "workflow_client"))


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
WorkflowClientDep = Annotated[WorkflowClient, Depends(get_workflow_client)]


@dataclass(frozen=True)
class Principal:
    user_id: str


def require_service(request: Request, settings: SettingsDep) -> Principal:
    """Guard for every /api route: the shared internal token, then the acting user's id."""
    expected = settings.blog_internal_token.get_secret_value() if settings.blog_internal_token else ""
    if not expected:
        raise ProblemError(503, "Internal service auth is not configured")
    supplied = request.headers.get("x-internal-token", "")
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise ProblemError(401, "Not authenticated")
    user_id = request.headers.get("x-on-behalf-of", "")
    if _ON_BEHALF_OF.fullmatch(user_id) is None:
        raise ProblemError(400, "Invalid X-On-Behalf-Of header")
    return Principal(user_id=user_id)


PrincipalDep = Annotated[Principal, Depends(require_service)]
