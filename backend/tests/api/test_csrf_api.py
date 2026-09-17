from collections.abc import AsyncIterator, Awaitable, Callable

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings

PASSWORD = "correct-horse-battery"
MakeUser = Callable[..., Awaitable[User]]
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]
NEW_USER = {"email": "csrf-new@example.test", "displayName": "New", "role": "viewer", "password": "x" * 12}


@pytest_asyncio.fixture(loop_scope="session")
async def bare_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A client that sends no Origin header by default."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def _wrong_login(http: AsyncClient, headers: dict[str, str]) -> tuple[int, str]:
    response = await http.post(
        "/api/auth/login", json={"email": "nobody@example.test", "password": "whatever"}, headers=headers
    )
    return response.status_code, str(response.json()["title"])


async def test_cross_site_fetch_metadata_is_blocked(client: AsyncClient) -> None:
    for value in ("cross-site", "same-site", "none"):
        assert await _wrong_login(client, {"Sec-Fetch-Site": value}) == (403, "Cross-site request blocked")


async def test_same_origin_fetch_metadata_passes(client: AsyncClient) -> None:
    # 401 means the request got past CSRF and reached the password check.
    assert await _wrong_login(client, {"Sec-Fetch-Site": "same-origin"}) == (401, "Invalid email or password")


async def test_missing_fetch_metadata_alone_is_not_a_rejection(client: AsyncClient) -> None:
    assert await _wrong_login(client, {}) == (401, "Invalid email or password")


async def test_missing_origin_is_blocked(bare_client: AsyncClient) -> None:
    assert await _wrong_login(bare_client, {}) == (403, "Origin not allowed")


async def test_foreign_origin_is_blocked(client: AsyncClient) -> None:
    assert await _wrong_login(client, {"Origin": "http://evil.example"}) == (403, "Origin not allowed")
    assert await _wrong_login(client, {"Origin": "null"}) == (403, "Origin not allowed")


async def test_same_origin_via_host_and_forwarded_proto(bare_client: AsyncClient) -> None:
    proxied = {"Origin": "https://blog.internal:8443", "Host": "blog.internal:8443", "X-Forwarded-Proto": "https"}
    assert await _wrong_login(bare_client, proxied) == (401, "Invalid email or password")
    without_proto = {"Origin": "https://blog.internal:8443", "Host": "blog.internal:8443"}
    assert await _wrong_login(bare_client, without_proto) == (403, "Origin not allowed")


async def test_vite_proxy_shape_is_allowed(bare_client: AsyncClient) -> None:
    # What the Vite dev proxy forwards (changeOrigin:false, xfwd:true) from a browser at http://web:5173.
    vite = {"Origin": "http://web:5173", "Host": "web:5173", "X-Forwarded-Proto": "http"}
    assert await _wrong_login(bare_client, vite) == (401, "Invalid email or password")


async def test_public_app_url_is_allowed(app: FastAPI, bare_client: AsyncClient, settings: Settings) -> None:
    app.state.settings = settings.model_copy(update={"public_app_url": "http://localhost:8310/"})
    assert await _wrong_login(bare_client, {"Origin": "http://localhost:8310"}) == (401, "Invalid email or password")
    assert await _wrong_login(bare_client, {"Origin": "http://localhost:9999"}) == (403, "Origin not allowed")


async def test_logout_requires_the_csrf_token(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.VIEWER)
    missing = await client.post("/api/auth/logout")
    assert (missing.status_code, missing.json()["title"]) == (403, "CSRF token missing or invalid")
    wrong = await client.post("/api/auth/logout", headers={"X-CSRF-Token": "0" * 64})
    assert wrong.status_code == 403
    assert (await client.get("/api/auth/session")).status_code == 200  # still signed in
    ok = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 204


async def test_users_post_requires_the_csrf_token(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    missing = await client.post("/api/admin/users", json=NEW_USER)
    assert (missing.status_code, missing.json()["title"]) == (403, "CSRF token missing or invalid")
    created = await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201


async def test_token_check_comes_before_body_validation(login_as: LoginAs) -> None:
    client, _ = await login_as(Role.ADMIN)
    response = await client.post("/api/admin/users", json={"nonsense": True})
    assert response.status_code == 403


async def test_login_is_exempt_from_the_token_but_not_from_origin(login_as: LoginAs, make_user: MakeUser) -> None:
    client, _ = await login_as(Role.VIEWER)  # the cookie jar now holds a session, and no token is sent below
    other = await make_user(Role.EDITOR)
    relogin = await client.post("/api/auth/login", json={"email": other.email, "password": PASSWORD})
    assert relogin.status_code == 200
    foreign = await client.post(
        "/api/auth/login",
        json={"email": other.email, "password": PASSWORD},
        headers={"Origin": "http://evil.example"},
    )
    assert (foreign.status_code, foreign.json()["title"]) == (403, "Origin not allowed")


async def test_safe_methods_are_not_checked(login_as: LoginAs) -> None:
    client, _ = await login_as(Role.VIEWER)
    response = await client.get(
        "/api/auth/session", headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 200


async def test_unsafe_request_without_session_reaches_auth(client: AsyncClient) -> None:
    response = await client.post("/api/admin/users", json=NEW_USER)
    assert (response.status_code, response.json()["title"]) == (401, "Not authenticated")
