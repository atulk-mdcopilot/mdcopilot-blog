from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import URL, text
from sqlalchemy.exc import OperationalError

from mdcopilot_blog.api.app import ROUTERS, create_app
from mdcopilot_blog.api.deps import get_session
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import FakeWorkflowClient, WorkflowClient


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_with_database(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


class _BrokenSession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        raise OperationalError("select 1", {}, ConnectionRefusedError("db down"))


async def test_readyz_reports_database_unavailable(app: FastAPI, client: AsyncClient) -> None:
    async def _broken() -> AsyncIterator[_BrokenSession]:
        yield _BrokenSession()

    app.dependency_overrides[get_session] = _broken
    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Database unavailable",
        "status": 503,
        "instance": "/readyz",
    }


async def test_unknown_route_is_problem_json(client: AsyncClient) -> None:
    response = await client.get("/api/nope")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not Found"


def test_routers_are_registered_in_order() -> None:
    assert [prefix for _, prefix in ROUTERS][:4] == ["", "/api/auth", "/api/admin/users", "/api/blog-agent"]


async def test_lifespan_sets_state_and_closes_injected_client(settings: Settings, database_url: URL) -> None:
    fake = FakeWorkflowClient()
    application = create_app(settings, workflow_client=fake)
    async with application.router.lifespan_context(application) as state:
        assert state is not None
        assert set(state) == {"settings", "engine", "sessionmaker", "workflow_client"}
        assert state["workflow_client"] is fake
        assert application.state.workflow_client is fake
        assert application.state.sessionmaker is state["sessionmaker"]
        async with state["sessionmaker"]() as session:
            assert await session.scalar(text("select current_database()")) == "mdcopilot_blog_test"
    assert fake.closed is True


async def test_lifespan_builds_a_real_workflow_client(settings: Settings, database_url: URL) -> None:
    application = create_app(settings)
    async with application.router.lifespan_context(application) as state:
        assert state is not None
        assert isinstance(state["workflow_client"], WorkflowClient)
