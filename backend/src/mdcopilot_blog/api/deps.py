"""FastAPI dependencies: app state accessors, the authenticated principal, RBAC and CSRF."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.auth.csrf import SAFE_METHODS, csrf_token_for, origin_allowed, tokens_match
from mdcopilot_blog.auth.sessions import resolve_session
from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import permissions_for
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient

LOGIN_PATH = "/api/auth/login"


def utcnow() -> datetime:
    return datetime.now(UTC)


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
    user_id: uuid.UUID
    email: str
    display_name: str
    role: Role
    permissions: frozenset[Permission]
    session_token: str


async def current_principal(request: Request, db: SessionDep, settings: SettingsDep) -> Principal:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise ProblemError(401, "Not authenticated")
    passive = request.method in SAFE_METHODS and request.headers.get("x-session-activity") == "passive"
    resolved = await resolve_session(db, token, now=utcnow(), touch=not passive)
    if resolved is None:
        raise ProblemError(401, "Not authenticated")
    await db.commit()  # persists the throttled last_seen_at touch
    user = resolved.user
    role = Role(user.role)
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=role,
        permissions=permissions_for(role),
        session_token=token,
    )


PrincipalDep = Annotated[Principal, Depends(current_principal)]


def require_permission(permission: Permission) -> Callable[..., Awaitable[Principal]]:
    async def _require(principal: PrincipalDep) -> Principal:
        if permission not in principal.permissions:
            raise ProblemError(403, "Forbidden", f"missing permission {permission.value}")
        return principal

    return _require


async def enforce_csrf(request: Request, settings: SettingsDep) -> None:
    """App-wide guard for unsafe methods: Fetch Metadata, then Origin, then the session-bound token."""
    if request.method in SAFE_METHODS:
        return
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None and fetch_site != "same-origin":
        raise ProblemError(403, "Cross-site request blocked")
    if not origin_allowed(
        request.headers.get("origin"),
        host=request.headers.get("host"),
        forwarded_proto=request.headers.get("x-forwarded-proto"),
        scheme=request.url.scheme,
        public_app_url=settings.public_app_url,
    ):
        raise ProblemError(403, "Origin not allowed")
    if request.url.path == LOGIN_PATH:
        return
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        return  # no session: the route's auth dependency answers 401
    expected = csrf_token_for(session_token, settings.session_secret.get_secret_value())
    if not tokens_match(expected, request.headers.get("x-csrf-token", "")):
        raise ProblemError(403, "CSRF token missing or invalid")
