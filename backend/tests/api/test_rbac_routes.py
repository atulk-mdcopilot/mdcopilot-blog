import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import AsyncClient

from mdcopilot_blog.api.app import ROUTERS
from mdcopilot_blog.api.deps import current_principal
from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import permissions_for

LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]

# (method, path, required permission, JSON body, status when allowed)
PROTECTED: list[tuple[str, str, Permission, dict[str, Any] | None, int]] = [
    ("GET", "/api/admin/users", Permission.SETTINGS, None, 200),
    (
        "POST",
        "/api/admin/users",
        Permission.SETTINGS,
        {"email": "rbac-new@example.test", "displayName": "R", "role": "viewer", "password": "x" * 12},
        201,
    ),
    ("PATCH", f"/api/admin/users/{uuid.uuid4()}", Permission.SETTINGS, {"role": "viewer"}, 404),
    ("GET", "/api/blog-agent/settings", Permission.SETTINGS, None, 200),
]

# Routes that must stay reachable without a session.
PUBLIC_PATHS = {"/healthz", "/readyz", "/api/auth/login"}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize(("method", "path", "permission", "body", "allowed_status"), PROTECTED)
async def test_role_matrix(
    login_as: LoginAs,
    role: Role,
    method: str,
    path: str,
    permission: Permission,
    body: dict[str, Any] | None,
    allowed_status: int,
) -> None:
    client, csrf = await login_as(role)
    response = await client.request(method, path, json=body, headers={"X-CSRF-Token": csrf})
    if permission in permissions_for(role):
        assert response.status_code == allowed_status, response.text
    else:
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == f"missing permission {permission.value}"


@pytest.mark.parametrize(("method", "path", "permission", "body", "allowed_status"), PROTECTED)
async def test_anonymous_is_401(
    client: AsyncClient,
    method: str,
    path: str,
    permission: Permission,
    body: dict[str, Any] | None,
    allowed_status: int,
) -> None:
    response = await client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json()["title"] == "Not authenticated"


def test_only_admin_holds_settings_permission() -> None:
    assert [role for role in Role if Permission.SETTINGS in permissions_for(role)] == [Role.ADMIN]


def _calls(dependant: Dependant) -> set[Any]:
    found = {dependant.call}
    for sub in dependant.dependencies:
        found |= _calls(sub)
    return found


def _declared_routes() -> list[tuple[str, APIRoute]]:
    # FastAPI 0.141 wraps included routers lazily, so read the original routers from ROUTERS.
    return [
        (prefix + route.path, route)
        for router, prefix in ROUTERS
        for route in router.routes
        if isinstance(route, APIRoute)
    ]


def test_every_non_public_route_requires_a_principal() -> None:
    """Deny by default: any route added later without an auth dependency fails here."""
    routes = _declared_routes()
    assert {path for path, _ in routes} >= PUBLIC_PATHS  # the check below cannot pass vacuously
    unprotected = [
        f"{sorted(route.methods)} {path}"
        for path, route in routes
        if path not in PUBLIC_PATHS and current_principal not in _calls(route.dependant)
    ]
    assert unprotected == []


def test_every_served_path_is_declared_in_routers(app: FastAPI) -> None:
    assert set(app.openapi()["paths"]) == {path for path, _ in _declared_routes()}
