"""Runs API: create, list, detail and cancel, with the workflow client faked (no DBOS here)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import AgentRun, AuditLog, BlogRun, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, Role, RunKind, RunStatus, StepStatus
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import EnqueueCall, FakeWorkflowClient

RUNS = "/api/blog-agent/runs"
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]

RUN_KEYS = {"id", "kind", "runDate", "status", "stage", "traceId", "costUsd", "createdAt", "startedAt", "finishedAt"}
DETAIL_KEYS = RUN_KEYS | {"params", "attempts", "steps"}
ATTEMPT_KEYS = {
    "id",
    "dbosWorkflowId",
    "workflowName",
    "attemptNo",
    "status",
    "startedAt",
    "finishedAt",
    "forkedFromWorkflowId",
}
STEP_KEYS = {
    "id",
    "stepName",
    "dbosStepId",
    "status",
    "tries",
    "agentName",
    "model",
    "promptName",
    "promptVersion",
    "inputTokens",
    "outputTokens",
    "costUsd",
    "durationMs",
    "error",
}


@pytest.fixture(autouse=True)
def _agent_enabled(app: FastAPI, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the kill switch on whatever .env says (the `app` fixture has already set app.state.settings)."""
    monkeypatch.setattr(app.state, "settings", settings.model_copy(update={"agent_enabled": True}))


def add_run(
    db: AsyncSession,
    *,
    status: RunStatus = RunStatus.QUEUED,
    kind: RunKind = RunKind.MANUAL,
    run_date: date = date(2026, 9, 17),
    created_at: datetime | None = None,
) -> BlogRun:
    run = BlogRun(kind=kind.value, run_date=run_date, status=status.value, params={}, trace_id=new_trace_id())
    if created_at is not None:
        run.created_at = created_at
    db.add(run)
    return run


async def audit_rows(db: AsyncSession, action: str, entity_id: uuid.UUID) -> list[AuditLog]:
    rows = await db.scalars(select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == str(entity_id)))
    return list(rows.all())


async def run_count(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(BlogRun)) or 0)


# --- POST /runs -------------------------------------------------------------------------------------------


async def test_editor_creates_manual_run_and_enqueues_hello_pipeline(
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
    settings: Settings,
) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body) == RUN_KEYS
    assert body["kind"] == "manual"
    assert body["status"] == "QUEUED"
    assert body["runDate"] == datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    assert len(body["traceId"]) == 32
    assert Decimal(str(body["costUsd"])) == 0
    assert body["startedAt"] is None
    assert body["finishedAt"] is None

    run_id = uuid.UUID(body["id"])
    run = await db_session.get(BlogRun, run_id)
    assert run is not None
    assert (run.kind, run.status, run.params) == ("manual", "QUEUED", {})
    assert run.created_by is not None

    # Literal names on purpose: the worker registers exactly these.
    assert fake_workflow_client.enqueued == [
        EnqueueCall(
            workflow_name="hello_pipeline",
            queue_name="pipeline",
            workflow_id=f"manual-{run_id}",
            args=(str(run_id),),
            timeout_seconds=settings.production_timeout_minutes * 60,
        )
    ]

    [created] = await audit_rows(db_session, "run.create", run_id)
    assert created.actor_user_id == run.created_by
    assert created.entity_type == "blog_run"
    assert created.details["workflow_id"] == f"manual-{run_id}"


async def test_create_run_records_request_params(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    payload = {
        "runDate": "2026-09-20",
        "pillar": "B",
        "topic": "Prior authorisation automation",
        "audience": "CMIOs",
        "wordCount": 900,
    }

    response = await http.post(RUNS, json=payload, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    assert response.json()["runDate"] == "2026-09-20"
    run = await db_session.get(BlogRun, uuid.UUID(response.json()["id"]))
    assert run is not None
    assert run.run_date == date(2026, 9, 20)
    assert run.params == payload
    assert len(fake_workflow_client.enqueued) == 1


async def test_create_run_accepts_an_empty_request_body(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient
) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(RUNS, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    assert len(fake_workflow_client.enqueued) == 1


@pytest.mark.parametrize(
    "payload",
    [{"wordCount": 100}, {"wordCount": 5000}, {"topic": "x" * 301}, {"pillar": "Z"}, {"unexpected": True}],
)
async def test_create_run_rejects_invalid_body(
    payload: dict[str, object],
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(RUNS, json=payload, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


async def test_viewer_cannot_create_run(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.VIEWER)

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "missing permission blog.generate"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


@pytest.mark.parametrize("headers", [{}, {"X-CSRF-Token": "0" * 64}], ids=["missing", "wrong"])
async def test_create_run_without_valid_csrf_token_is_rejected(
    headers: dict[str, str],
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
) -> None:
    http, _ = await login_as(Role.EDITOR)

    response = await http.post(RUNS, json={}, headers=headers)

    assert response.status_code == 403
    assert response.json()["title"] == "CSRF token missing or invalid"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


async def test_create_run_requires_login(client: AsyncClient, fake_workflow_client: FakeWorkflowClient) -> None:
    response = await client.post(RUNS, json={})

    assert response.status_code == 401
    assert fake_workflow_client.enqueued == []


async def test_create_run_is_rejected_when_agent_disabled(
    login_as: LoginAs,
    app: FastAPI,
    settings: Settings,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    monkeypatch.setattr(app.state, "settings", settings.model_copy(update={"agent_enabled": False}))

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Agent disabled"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


async def test_enqueue_failure_returns_503_and_marks_run_failed(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    fake_workflow_client.enqueue_error = ConnectionError("dbos system database unreachable")

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Workflow service unavailable"
    run = (await db_session.scalars(select(BlogRun))).one()
    assert run.status == "FAILED"
    assert run.error == {"stage": "enqueue", "message": "ConnectionError: dbos system database unreachable"}
    assert run.finished_at is not None
    assert fake_workflow_client.enqueued == []  # the fake raises before it records the call


# --- GET /runs --------------------------------------------------------------------------------------------


async def test_list_runs_is_newest_first_and_paginated(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    base = datetime(2026, 9, 1, 7, 0, tzinfo=UTC)
    oldest = add_run(db_session, created_at=base)
    middle = add_run(db_session, created_at=base + timedelta(hours=1))
    newest = add_run(db_session, created_at=base + timedelta(hours=2))
    await db_session.flush()

    first = await http.get(RUNS, params={"limit": 2})
    second = await http.get(RUNS, params={"limit": 2, "offset": 2})

    assert first.status_code == 200, first.text
    page = first.json()
    assert set(page) == {"items", "total", "limit", "offset"}
    assert [item["id"] for item in page["items"]] == [str(newest.id), str(middle.id)]
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 0)
    assert set(page["items"][0]) == RUN_KEYS
    assert second.status_code == 200, second.text
    assert [item["id"] for item in second.json()["items"]] == [str(oldest.id)]
    assert (second.json()["total"], second.json()["offset"]) == (3, 2)


async def test_list_runs_defaults_to_20_items(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    for _ in range(21):
        add_run(db_session)
    await db_session.flush()

    response = await http.get(RUNS)

    assert response.status_code == 200
    page = response.json()
    assert (len(page["items"]), page["total"], page["limit"], page["offset"]) == (20, 21, 20, 0)


async def test_list_runs_filters_by_status(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    failed = add_run(db_session, status=RunStatus.FAILED)
    add_run(db_session, status=RunStatus.SUCCEEDED)
    add_run(db_session, status=RunStatus.QUEUED)
    await db_session.flush()

    response = await http.get(RUNS, params={"status": "FAILED"})

    assert response.status_code == 200
    page = response.json()
    assert [item["id"] for item in page["items"]] == [str(failed.id)]
    assert page["items"][0]["status"] == "FAILED"
    assert page["total"] == 1


async def test_list_runs_caps_limit_at_100(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    for _ in range(101):
        add_run(db_session)
    await db_session.flush()

    response = await http.get(RUNS, params={"limit": 500})

    assert response.status_code == 200
    page = response.json()
    assert (len(page["items"]), page["total"], page["limit"]) == (100, 101, 100)


@pytest.mark.parametrize("query", [{"limit": 0}, {"offset": -1}, {"status": "DONE"}], ids=["limit", "offset", "status"])
async def test_list_runs_rejects_bad_query(query: dict[str, object], login_as: LoginAs) -> None:
    http, _ = await login_as(Role.VIEWER)

    response = await http.get(RUNS, params=query)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_list_runs_requires_login(client: AsyncClient) -> None:
    response = await client.get(RUNS)

    assert response.status_code == 401


# --- GET /runs/{id} ---------------------------------------------------------------------------------------


async def test_run_detail_returns_404_for_unknown_run(login_as: LoginAs) -> None:
    http, _ = await login_as(Role.VIEWER)

    response = await http.get(f"{RUNS}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Run not found"


async def test_run_detail_rejects_malformed_id(login_as: LoginAs) -> None:
    http, _ = await login_as(Role.VIEWER)

    response = await http.get(f"{RUNS}/not-a-uuid")

    assert response.status_code == 422


async def test_run_detail_shape_and_ordering(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    t0 = datetime(2026, 9, 17, 1, 30, tzinfo=UTC)
    run = add_run(db_session, status=RunStatus.SUCCEEDED)
    run.params = {"topic": "Prior authorisation automation"}
    await db_session.flush()
    manual_wf = f"manual-{run.id}"
    retry = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"fork-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=2,
        forked_from_workflow_id=manual_wf,
        status=AttemptStatus.SUCCEEDED.value,
        started_at=t0 + timedelta(minutes=5),
        finished_at=t0 + timedelta(minutes=6),
    )
    original = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=manual_wf,
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.FAILED.value,
        started_at=t0,
        finished_at=t0 + timedelta(minutes=1),
        error={"class": "RouteExhausted", "message": "all models failed"},
    )
    db_session.add_all([retry, original])
    await db_session.flush()
    failed_echo = AgentRun(
        run_id=run.id,
        attempt_id=original.id,
        dbos_workflow_id=manual_wf,
        dbos_step_id=2,
        step_name="hello.echo",
        agent_name="hello",
        status=StepStatus.FAILED.value,
        started_at=t0,
        error={"class": "RouteExhausted", "message": "all models failed"},
        trace_id=run.trace_id,
        created_at=t0 + timedelta(seconds=1),
    )
    first_open = AgentRun(
        run_id=run.id,
        attempt_id=original.id,
        dbos_workflow_id=manual_wf,
        dbos_step_id=1,
        step_name="hello.open_attempt",
        status=StepStatus.SUCCEEDED.value,
        started_at=t0,
        trace_id=run.trace_id,
        created_at=t0 + timedelta(seconds=1),
    )
    retry_finish = AgentRun(
        run_id=run.id,
        attempt_id=retry.id,
        dbos_workflow_id=f"fork-{run.id}",
        dbos_step_id=3,
        step_name="hello.finish",
        status=StepStatus.SUCCEEDED.value,
        started_at=t0 + timedelta(minutes=5),
        trace_id=run.trace_id,
        created_at=t0 + timedelta(minutes=6),
    )
    retry_echo = AgentRun(
        run_id=run.id,
        attempt_id=retry.id,
        dbos_workflow_id=f"fork-{run.id}",
        dbos_step_id=2,
        step_name="hello.echo",
        agent_name="hello",
        agent_version="1",
        model="mock:hello",
        prompt_name="hello/echo",
        prompt_version=1,
        status=StepStatus.SUCCEEDED.value,
        tries=2,
        started_at=t0 + timedelta(minutes=5),
        completed_at=t0 + timedelta(minutes=5, milliseconds=150),
        duration_ms=150,
        input_tokens=20,
        output_tokens=8,
        cost_usd=Decimal("0.000125"),
        trace_id=run.trace_id,
        created_at=t0 + timedelta(minutes=5),
    )
    db_session.add_all([failed_echo, retry_finish, retry_echo, first_open])
    await db_session.flush()

    response = await http.get(f"{RUNS}/{run.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert (body["id"], body["status"], body["kind"]) == (str(run.id), "SUCCEEDED", "manual")
    assert body["params"] == {"topic": "Prior authorisation automation"}

    assert [attempt["attemptNo"] for attempt in body["attempts"]] == [1, 2]
    assert all(set(attempt) == ATTEMPT_KEYS for attempt in body["attempts"])
    second = body["attempts"][1]
    assert second["id"] == str(retry.id)
    assert second["dbosWorkflowId"] == f"fork-{run.id}"
    assert second["workflowName"] == "hello_pipeline"
    assert second["status"] == "SUCCEEDED"
    assert second["forkedFromWorkflowId"] == manual_wf
    assert datetime.fromisoformat(second["startedAt"]) == t0 + timedelta(minutes=5)
    assert datetime.fromisoformat(second["finishedAt"]) == t0 + timedelta(minutes=6)
    assert body["attempts"][0]["forkedFromWorkflowId"] is None

    # created_at first, then dbos_step_id for rows written at the same instant
    assert [step["id"] for step in body["steps"]] == [
        str(first_open.id),
        str(failed_echo.id),
        str(retry_echo.id),
        str(retry_finish.id),
    ]
    assert all(set(step) == STEP_KEYS for step in body["steps"])
    assert body["steps"][1]["status"] == "FAILED"
    assert body["steps"][1]["error"] == {"class": "RouteExhausted", "message": "all models failed"}
    echo = body["steps"][2]
    assert Decimal(str(echo.pop("costUsd"))) == Decimal("0.000125")
    assert echo == {
        "id": str(retry_echo.id),
        "stepName": "hello.echo",
        "dbosStepId": 2,
        "status": "SUCCEEDED",
        "tries": 2,
        "agentName": "hello",
        "model": "mock:hello",
        "promptName": "hello/echo",
        "promptVersion": 1,
        "inputTokens": 20,
        "outputTokens": 8,
        "durationMs": 150,
        "error": None,
    }


# --- POST /runs/{id}/cancel -------------------------------------------------------------------------------


async def test_cancel_queued_run_cancels_its_workflow(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    created = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})
    run_id = uuid.UUID(created.json()["id"])

    response = await http.post(f"{RUNS}/{run_id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body) == RUN_KEYS
    assert body["status"] == "CANCELLED"
    assert body["finishedAt"] is not None
    # No attempt row exists until the worker starts the workflow, so the service cancels it by its id.
    assert fake_workflow_client.cancelled == [f"manual-{run_id}"]
    run = await db_session.get(BlogRun, run_id)
    assert run is not None
    assert run.status == "CANCELLED"
    [cancelled] = await audit_rows(db_session, "run.cancel", run_id)
    assert cancelled.actor_user_id == run.created_by


async def test_cancel_cancels_only_enqueued_and_running_attempts(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    run = add_run(db_session, status=RunStatus.QUEUED)
    await db_session.flush()
    finished = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"manual-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.FAILED.value,
        started_at=datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
        finished_at=datetime(2026, 9, 17, 1, 1, tzinfo=UTC),
    )
    enqueued = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"restart-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=2,
        status=AttemptStatus.ENQUEUED.value,
    )
    running = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"fork-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=3,
        status=AttemptStatus.RUNNING.value,
        started_at=datetime(2026, 9, 17, 1, 5, tzinfo=UTC),
    )
    db_session.add_all([running, finished, enqueued])
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "CANCELLED"
    assert fake_workflow_client.cancelled == [f"restart-{run.id}", f"fork-{run.id}"]
    assert (finished.status, enqueued.status, running.status) == ("FAILED", "CANCELLED", "CANCELLED")
    assert finished.finished_at == datetime(2026, 9, 17, 1, 1, tzinfo=UTC)
    assert enqueued.finished_at is not None
    assert running.finished_at is not None


@pytest.mark.parametrize("status", [RunStatus.SUCCEEDED, RunStatus.FAILED])
async def test_cancel_terminal_run_is_a_conflict(
    status: RunStatus,
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    run = add_run(db_session, status=status)
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Run cannot be cancelled"
    assert fake_workflow_client.cancelled == []
    assert run.status == status.value
    assert await audit_rows(db_session, "run.cancel", run.id) == []


async def test_cancel_already_cancelled_run_changes_nothing(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    finished_at = datetime(2026, 9, 17, 2, 0, tzinfo=UTC)
    run = add_run(db_session, status=RunStatus.CANCELLED)
    run.finished_at = finished_at
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202
    assert response.json()["status"] == "CANCELLED"
    assert fake_workflow_client.cancelled == []
    assert run.finished_at == finished_at
    assert await audit_rows(db_session, "run.cancel", run.id) == []


async def test_cancel_unknown_run_is_404(login_as: LoginAs, fake_workflow_client: FakeWorkflowClient) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(f"{RUNS}/{uuid.uuid4()}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 404
    assert response.json()["title"] == "Run not found"
    assert fake_workflow_client.cancelled == []


async def test_viewer_cannot_cancel_run(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.VIEWER)
    run = add_run(db_session, status=RunStatus.QUEUED)
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 403
    assert response.json()["detail"] == "missing permission blog.generate"
    assert fake_workflow_client.cancelled == []
    assert run.status == "QUEUED"
