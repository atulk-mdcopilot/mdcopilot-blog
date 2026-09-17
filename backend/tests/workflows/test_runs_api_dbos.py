"""End to end: POST /api/blog-agent/runs through the real WorkflowClient, executed by in-process DBOS.

Uses Task 11's `dbos_runtime` fixture, which launches DBOS on the pytest event loop against the test
database. The app is built without an injected client, so its lifespan creates
`WorkflowClient.from_settings(...)` exactly as the api container does. The API and the worker commit
in their own sessions, so this test uses committed data and `clean_db`, not `db_session`.

`dbos_runtime` does not import workflow modules; test modules do, at collection time, so every workflow is
registered before DBOS launches. This module imports `workflows.hello` for that reason: run on its own, it would
otherwise leave `hello_pipeline` unregistered (DBOS Error 4) and the run QUEUED.
"""

import asyncio
import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import mdcopilot_blog.workflows.hello  # noqa: F401  (registers hello_pipeline before dbos_runtime launches DBOS)
from mdcopilot_blog.api.app import create_app
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClientProtocol
from mdcopilot_blog.workflows.names import STEP_HELLO_ECHO, STEP_HELLO_FINISH, STEP_HELLO_OPEN

RUNS = "/api/blog-agent/runs"
EMAIL = "e2e-editor@example.test"
PASSWORD = "correct-horse-battery"
TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}
TERMINAL_WORKFLOW_STATUSES = {"SUCCESS", "ERROR", "CANCELLED", "MAX_RECOVERY_ATTEMPTS_EXCEEDED"}
TIMEOUT_SECONDS = 60.0


async def wait_for_run(http: AsyncClient, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        response = await http.get(f"{RUNS}/{run_id}")
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        if body["status"] in TERMINAL_RUN_STATUSES:
            return body
        if time.monotonic() > deadline:
            pytest.fail(f"run {run_id} is still {body['status']} after {TIMEOUT_SECONDS}s")
        await asyncio.sleep(0.2)


async def wait_for_workflow(client: WorkflowClientProtocol, workflow_id: str) -> str | None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        status = await client.status(workflow_id)
        if status in TERMINAL_WORKFLOW_STATUSES or time.monotonic() > deadline:
            return status
        await asyncio.sleep(0.2)


# database_url first: the test database must exist (and be migrated) before DBOS launches against it.
@pytest.mark.usefixtures("database_url", "dbos_runtime", "clean_db")
async def test_manual_run_executes_hello_pipeline_through_dbos(
    settings: Settings, sessionmaker_committing: async_sessionmaker[AsyncSession]
) -> None:
    # dbos_runtime launches DBOS with application_version "pytest". The client stamps settings.app_version
    # on every enqueue, and DBOS leaves a workflow ENQUEUED forever if no executor runs that version.
    e2e_settings = settings.model_copy(update={"app_version": "pytest", "agent_enabled": True})
    async with sessionmaker_committing() as db:
        await create_user(db, email=EMAIL, display_name="E2E Editor", role=Role.EDITOR, password=PASSWORD)
        await db.commit()

    app = create_app(e2e_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
        ) as http,
    ):
        login = await http.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert login.status_code == 200, login.text
        csrf = login.json()["csrfToken"]

        created = await http.post(RUNS, json={"topic": "hello"}, headers={"X-CSRF-Token": csrf})
        assert created.status_code == 202, created.text
        assert created.json()["status"] == "QUEUED"
        run_id = created.json()["id"]

        detail = await wait_for_run(http, run_id)
        workflow_status = await wait_for_workflow(app.state.workflow_client, f"manual-{run_id}")

    assert detail["status"] == "SUCCEEDED", detail
    assert detail["stage"] == STEP_HELLO_FINISH
    assert detail["startedAt"] is not None
    assert detail["finishedAt"] is not None
    assert detail["params"] == {"topic": "hello"}
    assert workflow_status == "SUCCESS"

    [attempt] = detail["attempts"]
    assert (attempt["dbosWorkflowId"], attempt["workflowName"], attempt["attemptNo"], attempt["status"]) == (
        f"manual-{run_id}",
        "hello_pipeline",
        1,
        "SUCCEEDED",
    )
    assert attempt["forkedFromWorkflowId"] is None

    steps = detail["steps"]
    assert [(step["stepName"], step["dbosStepId"], step["status"], step["tries"]) for step in steps] == [
        (STEP_HELLO_OPEN, 1, "SUCCEEDED", 1),
        (STEP_HELLO_ECHO, 2, "SUCCEEDED", 1),
        (STEP_HELLO_FINISH, 3, "SUCCEEDED", 1),
    ]
    assert all(step["error"] is None for step in steps)
    echo = steps[1]
    assert (echo["agentName"], echo["model"], echo["promptName"], echo["promptVersion"]) == (
        "hello",
        "mock:hello",
        "hello/echo",
        1,
    )
    # usage recorded by the mock fixture fixtures/mock/llm/hello/hello_echo.json
    assert (echo["inputTokens"], echo["outputTokens"]) == (20, 8)
