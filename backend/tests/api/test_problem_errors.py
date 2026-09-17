"""errors.py: problem+json for ProblemError, HTTP errors and request validation (tiny app, no database)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field, field_validator

from mdcopilot_blog.errors import PROBLEM_JSON, ProblemError, install_problem_handlers


class SignupIn(BaseModel):
    email: str
    password: str = Field(min_length=12)

    @field_validator("email")
    @classmethod
    def _needs_at_sign(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must contain @")
        return value


def build_app() -> FastAPI:
    app = FastAPI()
    install_problem_handlers(app)

    @app.get("/conflict")
    async def conflict() -> None:
        raise ProblemError(
            409,
            "User already exists",
            {"field": "email"},
            type_="https://www.mdcopilot.health/problems/conflict",
        )

    @app.get("/unauthenticated")
    async def unauthenticated() -> None:
        raise ProblemError(401, "Not authenticated")

    @app.get("/typed")
    async def typed() -> None:
        raise ProblemError(400, "Typed detail", {"id": uuid.UUID(int=1), "at": datetime(2026, 9, 17, tzinfo=UTC)})

    @app.get("/items/{item_id}")
    async def item(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    @app.get("/teapot")
    async def teapot() -> None:
        raise HTTPException(status_code=418, detail="Short and stout", headers={"X-Tea": "earl-grey"})

    @app.get("/structured")
    async def structured() -> None:
        raise HTTPException(status_code=400, detail={"reason": "bad"})

    @app.post("/signup")
    async def signup(body: SignupIn) -> dict[str, str]:
        return {"email": body.email}

    return app


@pytest.fixture
async def problem_client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://test") as client:
        yield client


async def test_problem_error_renders_problem_json(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/conflict")
    assert r.status_code == 409
    assert r.headers["content-type"] == PROBLEM_JSON == "application/problem+json"
    assert r.json() == {
        "type": "https://www.mdcopilot.health/problems/conflict",
        "title": "User already exists",
        "status": 409,
        "instance": "/conflict",
        "detail": {"field": "email"},
    }


async def test_problem_error_without_detail_omits_detail(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/unauthenticated")
    assert r.status_code == 401
    assert r.json() == {
        "type": "about:blank",
        "title": "Not authenticated",
        "status": 401,
        "instance": "/unauthenticated",
    }


async def test_problem_detail_is_made_json_safe(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/typed")
    assert r.json()["detail"] == {"id": "00000000-0000-0000-0000-000000000001", "at": "2026-09-17T00:00:00+00:00"}


def test_problem_error_keeps_its_fields() -> None:
    exc = ProblemError(403, "Forbidden", "missing permission blog.settings")
    assert (exc.status, exc.title, exc.detail, exc.type_) == (
        403,
        "Forbidden",
        "missing permission blog.settings",
        "about:blank",
    )
    assert str(exc) == "Forbidden"


async def test_unknown_route_is_problem_json_404(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/nope")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json() == {"type": "about:blank", "title": "Not Found", "status": 404, "instance": "/nope"}


async def test_method_not_allowed_keeps_allow_header(problem_client: AsyncClient) -> None:
    r = await problem_client.post("/conflict")
    assert r.status_code == 405
    assert r.headers["content-type"] == "application/problem+json"
    assert r.headers["allow"] == "GET"
    assert r.json()["title"] == "Method Not Allowed"


async def test_http_exception_keeps_title_and_headers(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/teapot")
    assert r.status_code == 418
    assert r.headers["x-tea"] == "earl-grey"
    assert r.json() == {"type": "about:blank", "title": "Short and stout", "status": 418, "instance": "/teapot"}


async def test_http_exception_with_structured_detail(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/structured")
    assert r.status_code == 400
    assert r.json() == {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "instance": "/structured",
        "detail": {"reason": "bad"},
    }


async def test_path_validation_error_is_problem_json(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/items/abc")
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["title"] == "Request validation failed"
    assert body["instance"] == "/items/abc"
    (error,) = body["detail"]
    assert error["loc"] == ["path", "item_id"]
    assert error["type"] == "int_parsing"
    assert set(error) <= {"type", "loc", "msg", "ctx"}


async def test_body_validation_error_never_echoes_input(problem_client: AsyncClient) -> None:
    r = await problem_client.post("/signup", json={"email": "a@example.com", "password": "tiny-secret"})
    assert r.status_code == 422
    assert "tiny-secret" not in r.text
    (error,) = r.json()["detail"]
    assert error["loc"] == ["body", "password"]
    assert error["type"] == "string_too_short"
    assert error["ctx"] == {"min_length": 12}


async def test_validator_error_context_is_json_safe(problem_client: AsyncClient) -> None:
    r = await problem_client.post("/signup", json={"email": "nobody", "password": "long-enough-password"})
    assert r.status_code == 422
    assert "long-enough-password" not in r.text
    (error,) = r.json()["detail"]
    assert error["loc"] == ["body", "email"]
    assert error["msg"] == "Value error, email must contain @"
    assert error["ctx"] == {"error": "email must contain @"}
