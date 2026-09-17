from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr

from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings

LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]

FAKE_OPENAI = "sk-proj-FAKE" + "a" * 40 + "WXYZ"
FAKE_GEMINI = "AIza" + "b" * 35


def _leaked(body: str, secrets: dict[str, str]) -> list[str]:
    """Names (never values) of secrets that appear in the body, so a failure cannot print a key."""
    return [name for name, value in secrets.items() if value and value in body]


async def test_settings_view_masks_provider_keys(app: FastAPI, login_as: LoginAs, settings: Settings) -> None:
    app.state.settings = settings.model_copy(
        update={
            "openai_api_key": SecretStr(FAKE_OPENAI),
            "gemini_api_key": SecretStr(FAKE_GEMINI),
            "anthropic_api_key": None,
            "ncbi_api_key": SecretStr("short"),
        }
    )
    client, _ = await login_as(Role.ADMIN)
    response = await client.get("/api/blog-agent/settings")
    assert response.status_code == 200
    assert _leaked(response.text, {"openai": FAKE_OPENAI, "gemini": FAKE_GEMINI, "ncbi": "short"}) == []
    assert response.json()["providers"] == {
        "openai": {"configured": True, "preview": "sk-…WXYZ"},
        "gemini": {"configured": True, "preview": "AIz…bbbb"},
        "anthropic": {"configured": False, "preview": None},
        "ncbi": {"configured": True, "preview": "set"},
    }


async def test_real_environment_keys_never_appear(login_as: LoginAs, settings: Settings) -> None:
    # The tools container gets the real .env, so this guards the actual keys too.
    real = {
        name: key.get_secret_value()
        for name, key in {
            "openai": settings.openai_api_key,
            "gemini": settings.gemini_api_key,
            "anthropic": settings.anthropic_api_key,
            "ncbi": settings.ncbi_api_key,
            "session_secret": settings.session_secret,
            "postgres_password": settings.postgres_password,
        }.items()
        if key is not None
    }
    client, _ = await login_as(Role.ADMIN)
    response = await client.get("/api/blog-agent/settings")
    assert response.status_code == 200
    assert _leaked(response.text, real) == []


async def test_settings_view_shape(login_as: LoginAs, settings: Settings) -> None:
    client, _ = await login_as(Role.ADMIN)
    body = (await client.get("/api/blog-agent/settings")).json()
    assert set(body) == {
        "appVersion",
        "mockMode",
        "agentEnabled",
        "schedulerEnabled",
        "publishingEnabled",
        "geminiGroundingEnabled",
        "humanApprovalRequired",
        "schedule",
        "routes",
        "limits",
        "publisher",
        "providers",
    }
    assert body["humanApprovalRequired"] is True
    assert body["mockMode"] is True
    assert body["appVersion"] == settings.app_version
    assert body["schedule"] == {"dailyRunTime": settings.daily_run_time, "timezone": settings.timezone}
    assert body["routes"] == settings.route_values()
    assert body["limits"]["maxCostPerRunUsd"] == str(settings.max_cost_per_run_usd)
    assert body["limits"]["wordCountMin"] == settings.word_count_min
    assert body["publisher"] == settings.publisher


async def test_settings_requires_admin(login_as: LoginAs) -> None:
    client, _ = await login_as(Role.PUBLISHER)
    response = await client.get("/api/blog-agent/settings")
    assert response.status_code == 403
    assert response.json()["detail"] == "missing permission blog.settings"
