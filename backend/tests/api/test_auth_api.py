from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.csrf import csrf_token_for
from mdcopilot_blog.auth.sessions import hash_token
from mdcopilot_blog.db.models import AuditLog, LoginAttempt, User, UserSession
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings

PASSWORD = "correct-horse-battery"
MakeUser = Callable[..., Awaitable[User]]


async def _login(client: AsyncClient, email: str, password: str = PASSWORD) -> tuple[int, dict[str, object], str]:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    return response.status_code, response.json(), response.headers.get("set-cookie", "")


async def test_login_success_sets_strict_http_only_cookie(
    client: AsyncClient, make_user: MakeUser, settings: Settings, db_session: AsyncSession
) -> None:
    user = await make_user(Role.REVIEWER, email="rev@example.test")
    response = await client.post("/api/auth/login", json={"email": "  REV@example.test ", "password": PASSWORD})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"

    cookie_header = response.headers["set-cookie"]
    attributes = [part.strip().lower() for part in cookie_header.split(";")]
    assert attributes[0].startswith("mdcb_session=")
    assert "httponly" in attributes
    assert "samesite=strict" in attributes
    assert "path=/" in attributes
    assert "max-age=43200" in attributes
    assert "secure" not in attributes

    token = client.cookies["mdcb_session"]
    body = response.json()
    assert body["csrfToken"] == csrf_token_for(token, settings.session_secret.get_secret_value())
    assert body["user"] == {
        "id": str(user.id),
        "email": "rev@example.test",
        "displayName": "Reviewer User",
        "role": "reviewer",
        "permissions": sorted(
            [
                "blog.view",
                "blog.generate",
                "blog.edit",
                "blog.review",
                "blog.approve",
                "blog.schedule",
                "blog.agent_runs",
            ]
        ),
    }

    stored = await db_session.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert stored is not None
    assert stored.token_hash == hash_token(token)
    attempts = (await db_session.scalars(select(LoginAttempt).where(LoginAttempt.email == "rev@example.test"))).all()
    assert [a.succeeded for a in attempts] == [True]
    audit_row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.login"))
    assert audit_row is not None
    assert (audit_row.actor_user_id, audit_row.entity_id) == (user.id, str(user.id))


async def test_secure_cookie_uses_host_prefix(
    app: FastAPI, client: AsyncClient, make_user: MakeUser, settings: Settings
) -> None:
    app.state.settings = settings.model_copy(update={"session_cookie_secure": True})
    user = await make_user(Role.VIEWER)
    response = await client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    attributes = [part.strip().lower() for part in response.headers["set-cookie"].split(";")]
    assert attributes[0].startswith("__host-mdcb_session=")
    assert "secure" in attributes
    assert "path=/" in attributes


async def test_wrong_password_is_401_and_recorded(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user(Role.VIEWER)
    status, body, cookie = await _login(client, user.email, "not-the-password")
    assert status == 401
    assert body["title"] == "Invalid email or password"
    assert cookie == ""
    attempts = (await db_session.scalars(select(LoginAttempt).where(LoginAttempt.email == user.email))).all()
    assert [a.succeeded for a in attempts] == [False]


async def test_unknown_email_and_inactive_user_get_the_same_401(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    status, body, _ = await _login(client, "ghost@example.test")
    assert (status, body["title"]) == (401, "Invalid email or password")
    user = await make_user(Role.VIEWER)
    user.is_active = False
    await db_session.flush()
    status, body, _ = await _login(client, user.email)
    assert (status, body["title"]) == (401, "Invalid email or password")


async def test_sixth_attempt_after_five_failures_is_429(client: AsyncClient, make_user: MakeUser) -> None:
    user = await make_user(Role.VIEWER)
    for _ in range(5):
        status, _, _ = await _login(client, user.email, "not-the-password")
        assert status == 401
    status, body, cookie = await _login(client, user.email, PASSWORD)  # correct password, still blocked
    assert status == 429
    assert body["title"] == "Too many login attempts"
    assert cookie == ""


async def test_login_validation_error(client: AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"email": "a@b.test"})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_session_endpoint(client: AsyncClient, make_user: MakeUser) -> None:
    anonymous = await client.get("/api/auth/session")
    assert anonymous.status_code == 401
    assert anonymous.json()["title"] == "Not authenticated"

    user = await make_user(Role.ADMIN)
    _, login_body, _ = await _login(client, user.email)
    response = await client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["csrfToken"] == login_body["csrfToken"]
    assert body["user"]["role"] == "admin"
    assert len(body["user"]["permissions"]) == 9


async def test_garbage_cookie_is_401(client: AsyncClient) -> None:
    client.cookies.set("mdcb_session", "garbage")
    response = await client.get("/api/auth/session")
    assert response.status_code == 401


async def test_logout_revokes_the_session_and_clears_the_cookie(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user(Role.EDITOR)
    _, body, _ = await _login(client, user.email)
    token = client.cookies["mdcb_session"]

    response = await client.post("/api/auth/logout", headers={"X-CSRF-Token": str(body["csrfToken"])})
    assert response.status_code == 204
    assert response.content == b""
    cleared = [part.strip().lower() for part in response.headers["set-cookie"].split(";")]
    assert cleared[0] == 'mdcb_session=""'
    assert "max-age=0" in cleared

    stored = await db_session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    assert stored is not None
    await db_session.refresh(stored)
    assert stored.revoked_at is not None
    assert await db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.logout")) is not None

    # Even if a client kept the old cookie, the session is dead.
    client.cookies.set("mdcb_session", token)
    assert (await client.get("/api/auth/session")).status_code == 401


async def test_logout_without_session_is_401(client: AsyncClient) -> None:
    response = await client.post("/api/auth/logout")
    assert response.status_code == 401


async def test_second_login_revokes_the_previous_session(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user(Role.VIEWER)
    await _login(client, user.email)
    first = client.cookies["mdcb_session"]
    await _login(client, user.email)
    second = client.cookies["mdcb_session"]
    assert first != second
    old = await db_session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(first)))
    assert old is not None
    await db_session.refresh(old)
    assert old.revoked_at is not None
