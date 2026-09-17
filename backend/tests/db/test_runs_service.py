"""Run service against the test database, with a recording fake workflow client."""

import re
import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas import ManualRunRequest
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.models import AuditLog, BlogRun, RunAttempt
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import AttemptStatus, Role, RunKind, RunStatus
from mdcopilot_blog.domain.rbac import permissions_for
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.services.runs import cancel_run, create_manual_run, get_run_detail, list_runs
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import FakeWorkflowClient

TODAY = date(2026, 9, 17)


class CancelFailingClient(FakeWorkflowClient):
    """The shared fake, except that every cancel fails."""

    async def cancel(self, workflow_id: str) -> None:
        self.cancelled.append(workflow_id)
        raise ConnectionError("dbos system database unreachable")


@pytest.fixture
def workflows() -> FakeWorkflowClient:
    return FakeWorkflowClient()


@pytest.fixture
def enabled_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"agent_enabled": True})


@pytest_asyncio.fixture
async def editor(db_session: AsyncSession) -> Principal:
    user = await create_user(
        db_session,
        email="runs-service-editor@example.test",
        display_name="Runs Service Editor",
        role=Role.EDITOR,
        password="correct-horse-battery",
    )
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=Role.EDITOR,
        permissions=permissions_for(Role.EDITOR),
        session_token="not-used-by-the-service",
    )


def add_run(
    db: AsyncSession,
    *,
    status: RunStatus = RunStatus.QUEUED,
    kind: RunKind = RunKind.MANUAL,
    run_date: date = TODAY,
) -> BlogRun:
    run = BlogRun(kind=kind.value, run_date=run_date, status=status.value, params={}, trace_id=new_trace_id())
    db.add(run)
    return run


async def test_create_manual_run_defaults_to_today_and_audits(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal, enabled_settings: Settings
) -> None:
    run = await create_manual_run(
        db_session,
        workflows,
        principal=editor,
        request=ManualRunRequest(pillar=PillarKey.C),
        settings=enabled_settings,
        today=TODAY,
    )

    assert run.run_date == TODAY
    assert run.kind == "manual"
    assert run.status == "QUEUED"
    assert run.created_by == editor.user_id
    assert run.params == {"pillar": "C"}
    assert re.fullmatch(r"[0-9a-f]{32}", run.trace_id)
    assert [call.workflow_id for call in workflows.enqueued] == [f"manual-{run.id}"]
    audit = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "run.create"))).one()
    assert (audit.actor_user_id, audit.entity_type, audit.entity_id) == (editor.user_id, "blog_run", str(run.id))
    assert audit.details == {"kind": "manual", "run_date": "2026-09-17", "workflow_id": f"manual-{run.id}"}


async def test_create_manual_run_refuses_when_agent_disabled(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal, settings: Settings
) -> None:
    disabled = settings.model_copy(update={"agent_enabled": False})

    with pytest.raises(ProblemError) as caught:
        await create_manual_run(
            db_session, workflows, principal=editor, request=ManualRunRequest(), settings=disabled, today=TODAY
        )

    assert (caught.value.status, caught.value.title) == (409, "Agent disabled")
    assert workflows.enqueued == []
    assert await db_session.scalar(select(func.count()).select_from(BlogRun)) == 0


async def test_list_runs_returns_total_beyond_the_last_page(db_session: AsyncSession) -> None:
    for _ in range(3):
        add_run(db_session)
    add_run(db_session, status=RunStatus.CANCELLED)
    await db_session.flush()

    empty_page, total = await list_runs(db_session, status=None, limit=10, offset=10)
    queued, queued_total = await list_runs(db_session, status=RunStatus.QUEUED, limit=2, offset=0)

    assert (empty_page, total) == ([], 4)
    assert len(queued) == 2
    assert queued_total == 3
    assert {run.status for run in queued} == {"QUEUED"}


async def test_get_run_detail_is_none_for_unknown_run(db_session: AsyncSession) -> None:
    assert await get_run_detail(db_session, uuid.uuid4()) is None


async def test_get_run_detail_orders_attempts_by_number(db_session: AsyncSession) -> None:
    run = add_run(db_session, status=RunStatus.RESEARCHING)
    await db_session.flush()
    for number in (3, 1, 2):
        db_session.add(
            RunAttempt(
                run_id=run.id,
                dbos_workflow_id=f"wf-{number}-{run.id}",
                workflow_name="hello_pipeline",
                attempt_no=number,
                status=AttemptStatus.FAILED.value,
            )
        )
    await db_session.flush()

    found = await get_run_detail(db_session, run.id)

    assert found is not None
    loaded, attempts, steps = found
    assert loaded.id == run.id
    assert [attempt.attempt_no for attempt in attempts] == [1, 2, 3]
    assert steps == []


async def test_cancel_queued_daily_run_cancels_the_daily_workflow(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal
) -> None:
    run = add_run(db_session, kind=RunKind.DAILY, run_date=date(2026, 9, 18))
    await db_session.flush()

    cancelled = await cancel_run(db_session, workflows, run=run, principal=editor)

    assert workflows.cancelled == ["daily-2026-09-18"]
    assert cancelled.status == "CANCELLED"
    assert cancelled.finished_at is not None
    audit = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "run.cancel"))).one()
    assert audit.details == {"from_status": "QUEUED", "workflow_ids": ["daily-2026-09-18"]}


async def test_cancel_researching_run_cancels_its_running_attempt_once(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal
) -> None:
    run = add_run(db_session, status=RunStatus.RESEARCHING)
    await db_session.flush()
    attempt = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"manual-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.RUNNING.value,
        started_at=datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
    )
    db_session.add(attempt)
    await db_session.flush()

    await cancel_run(db_session, workflows, run=run, principal=editor)

    assert workflows.cancelled == [f"manual-{run.id}"]
    assert attempt.status == "CANCELLED"
    assert run.status == "CANCELLED"


@pytest.mark.parametrize("status", [RunStatus.SUCCEEDED, RunStatus.FAILED])
async def test_cancel_terminal_run_raises_invalid_transition(
    status: RunStatus, db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal
) -> None:
    run = add_run(db_session, status=status)
    await db_session.flush()

    with pytest.raises(InvalidTransition):
        await cancel_run(db_session, workflows, run=run, principal=editor)

    assert workflows.cancelled == []
    assert run.status == status.value


async def test_cancel_client_failure_is_503_and_changes_nothing(db_session: AsyncSession, editor: Principal) -> None:
    failing = CancelFailingClient()
    run = add_run(db_session, status=RunStatus.RESEARCHING)
    await db_session.flush()
    attempt = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"manual-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.RUNNING.value,
    )
    db_session.add(attempt)
    await db_session.flush()

    with pytest.raises(ProblemError) as caught:
        await cancel_run(db_session, failing, run=run, principal=editor)

    assert (caught.value.status, caught.value.title) == (503, "Workflow service unavailable")
    assert failing.cancelled == [f"manual-{run.id}"]
    assert (run.status, attempt.status) == ("RESEARCHING", "RUNNING")
    assert run.finished_at is None
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
