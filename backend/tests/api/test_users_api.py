import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.passwords import verify_password
from mdcopilot_blog.db.models import AuditLog, User
from mdcopilot_blog.domain.enums import Role

PASSWORD = "correct-horse-battery"
MakeUser = Callable[..., Awaitable[User]]
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]
NEW_USER = {"email": "New.Person@Example.TEST", "displayName": "New Person", "role": "editor", "password": "x" * 12}


async def _admin_id(client: AsyncClient) -> str:
    return str((await client.get("/api/auth/session")).json()["user"]["id"])


async def test_list_users(login_as: LoginAs, make_user: MakeUser) -> None:
    client, _ = await login_as(Role.ADMIN)
    await make_user(Role.VIEWER, email="listed@example.test")
    response = await client.get("/api/admin/users")
    assert response.status_code == 200
    rows = response.json()
    listed = next(row for row in rows if row["email"] == "listed@example.test")
    assert set(listed) == {"id", "email", "displayName", "role", "isActive", "lastLoginAt", "createdAt"}
    assert (listed["role"], listed["isActive"], listed["lastLoginAt"]) == ("viewer", True, None)
    admin = next(row for row in rows if row["role"] == "admin")
    assert admin["lastLoginAt"] is not None
    assert "passwordHash" not in response.text


async def test_create_user(login_as: LoginAs, db_session: AsyncSession) -> None:
    client, csrf = await login_as(Role.ADMIN)
    response = await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["displayName"], body["role"], body["isActive"]) == (
        "new.person@example.test",
        "New Person",
        "editor",
        True,
    )
    user = await db_session.get(User, uuid.UUID(body["id"]))
    assert user is not None
    assert verify_password("x" * 12, user.password_hash)[0] is True
    audit_row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "user.create"))
    assert audit_row is not None
    assert audit_row.entity_id == body["id"]
    assert audit_row.details == {"email": "new.person@example.test", "role": "editor"}
    assert audit_row.actor_user_id == uuid.UUID(await _admin_id(client))


async def test_created_user_can_log_in(login_as: LoginAs, app: FastAPI) -> None:
    client, csrf = await login_as(Role.ADMIN)
    assert (await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})).status_code == 201
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
    ) as other:
        response = await other.post("/api/auth/login", json={"email": NEW_USER["email"], "password": "x" * 12})
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "editor"


async def test_duplicate_user_is_409(login_as: LoginAs, make_user: MakeUser) -> None:
    client, csrf = await login_as(Role.ADMIN)
    await make_user(Role.VIEWER, email="new.person@example.test")
    response = await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 409
    assert response.json()["title"] == "User already exists"


async def test_invalid_create_payloads_are_422(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    for payload in (
        {**NEW_USER, "password": ""},
        {**NEW_USER, "role": "owner"},
        {**NEW_USER, "email": "not-an-email"},
        {**NEW_USER, "isSuperuser": True},
    ):
        response = await client.post("/api/admin/users", json=payload, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 422, payload
        assert response.json()["title"] == "Request validation failed"


async def test_update_role_is_audited(login_as: LoginAs, make_user: MakeUser, db_session: AsyncSession) -> None:
    client, csrf = await login_as(Role.ADMIN)
    target = await make_user(Role.VIEWER)
    response = await client.patch(
        f"/api/admin/users/{target.id}", json={"role": "publisher"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "publisher"
    audit_row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "user.update"))
    assert audit_row is not None
    assert audit_row.details == {"role": {"from": "viewer", "to": "publisher"}}


async def test_deactivating_a_user_signs_them_out(login_as: LoginAs, make_user: MakeUser, app: FastAPI) -> None:
    admin, csrf = await login_as(Role.ADMIN)
    target = await make_user(Role.EDITOR)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
    ) as other:
        assert (
            await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        ).status_code == 200
        assert (await other.get("/api/auth/session")).status_code == 200

        response = await admin.patch(
            f"/api/admin/users/{target.id}", json={"isActive": False}, headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
        assert response.json()["isActive"] is False

        assert (await other.get("/api/auth/session")).status_code == 401
        relogin = await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        assert relogin.status_code == 401


async def test_password_change_signs_out_existing_sessions(
    login_as: LoginAs, make_user: MakeUser, app: FastAPI
) -> None:
    admin, csrf = await login_as(Role.ADMIN)
    target = await make_user(Role.EDITOR)
    headers = {"X-CSRF-Token": csrf}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
    ) as other:
        assert (
            await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        ).status_code == 200
        short = await admin.patch(f"/api/admin/users/{target.id}", json={"password": ""}, headers=headers)
        assert short.status_code == 422
        assert (await other.get("/api/auth/session")).status_code == 200  # the rejected change did nothing

        changed = await admin.patch(
            f"/api/admin/users/{target.id}", json={"password": "a-brand-new-password"}, headers=headers
        )
        assert changed.status_code == 200
        assert (await other.get("/api/auth/session")).status_code == 401

        old = await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        assert old.status_code == 401
        new = await other.post("/api/auth/login", json={"email": target.email, "password": "a-brand-new-password"})
        assert new.status_code == 200


async def test_admin_cannot_demote_or_deactivate_self(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    me = await _admin_id(client)
    headers = {"X-CSRF-Token": csrf}
    demote = await client.patch(f"/api/admin/users/{me}", json={"role": "viewer"}, headers=headers)
    assert demote.status_code == 409
    assert demote.json()["title"] == "You cannot change your own role"
    deactivate = await client.patch(f"/api/admin/users/{me}", json={"isActive": False}, headers=headers)
    assert deactivate.status_code == 409
    assert deactivate.json()["title"] == "You cannot deactivate yourself"
    same_role = await client.patch(f"/api/admin/users/{me}", json={"role": "admin", "isActive": True}, headers=headers)
    assert same_role.status_code == 200
    # Changing your own password keeps your current session alive.
    own_password = await client.patch(
        f"/api/admin/users/{me}", json={"password": "another-long-password"}, headers=headers
    )
    assert own_password.status_code == 200
    assert (await client.get("/api/auth/session")).status_code == 200


async def test_update_unknown_user_is_404(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    response = await client.patch(
        f"/api/admin/users/{uuid.uuid4()}", json={"role": "viewer"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 404
    assert response.json()["title"] == "User not found"
