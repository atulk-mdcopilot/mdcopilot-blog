"""Shared pytest fixtures. Tests only ever touch the disposable database ``mdcopilot_blog_test``."""

import asyncio
import contextlib
import io
import itertools
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from dbos import DBOS, run_dbos_database_migrations
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog.api.app import create_app
from mdcopilot_blog.api.deps import get_session
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.db.models import BlogRun, User
from mdcopilot_blog.domain.enums import Role, RunKind, RunStatus
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.settings import Settings, get_settings
from mdcopilot_blog.workflows.client import FakeWorkflowClient
from mdcopilot_blog.workflows.dbos_config import build_dbos_config
from mdcopilot_blog.workflows.names import QUEUE_INTERACTIVE, QUEUE_PIPELINE
from mdcopilot_blog.workflows.runtime import WorkerRuntime, build_runtime, set_runtime

# --- T5: database fixtures ---------------------------------------------------------------------------

TEST_DB = "mdcopilot_blog_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
TRUNCATE_COMMITTED_SQL = (
    "TRUNCATE app.blog_llm_calls, app.blog_agent_runs, app.blog_run_attempts, app.blog_runs, "
    "app.audit_log, app.login_attempts, app.user_sessions, app.users RESTART IDENTITY CASCADE"
)


def _admin_connect_kwargs(settings: Settings) -> dict[str, Any]:
    # Keyword args, not a URI: render_as_string() does not percent-encode spaces, which libpq rejects.
    return settings.database_url("postgres").translate_connect_args(username="user", database="dbname")


def _recreate_test_db(settings: Settings, *, drop_only: bool = False) -> None:
    with psycopg.connect(**_admin_connect_kwargs(settings), autocommit=True) as conn:  # no tx for (CREATE|DROP) DB
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB)))
        if not drop_only:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))


def _dbos_migrate(settings: Settings) -> None:
    # In-process (what `dbos migrate` runs): the password never sits in a child process's argv.
    url = settings.database_url(TEST_DB).render_as_string(hide_password=False)
    password = settings.postgres_password.get_secret_value()
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):  # dbos echoes a failure's cause to stdout
            run_dbos_database_migrations(url, schema="dbos")
    except RuntimeError:  # dbos echoes the cause, then raises click.exceptions.Exit(1), a RuntimeError
        output = captured.getvalue().replace(url, "***").replace(password, "***")[-2000:]
        msg = f"DBOS migrations failed for {TEST_DB}:\n{output}"
        raise RuntimeError(msg) from None


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings().model_copy(
        update={
            "postgres_db": TEST_DB,
            "mock_mode": True,
            "session_cookie_secure": False,
            "public_app_url": "http://test",
        }
    )


@pytest.fixture(scope="session")
def database_url(settings: Settings) -> Iterator[URL]:
    """Fresh test DB, `alembic upgrade head` and the DBOS system-table migrations, once per session.

    Sync on purpose: migrations/env.py calls asyncio.run(), which fails inside a running loop.
    """
    _recreate_test_db(settings)
    url = settings.database_url()
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = url  # a URL object: no string round-trip of the password
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    _dbos_migrate(settings)
    yield url
    _recreate_test_db(settings, drop_only=True)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(database_url: URL) -> AsyncIterator[AsyncEngine]:
    eng = make_engine(database_url)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test session inside an outer transaction that is always rolled back.

    join_transaction_mode="create_savepoint": commit()/rollback() in code under test only touch
    SAVEPOINTs; nothing a test writes here survives the test.
    """
    async with engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def clean_db(engine: AsyncEngine) -> AsyncIterator[None]:
    """Truncate the tables that committing tests write to, before and after the test.

    TRUNCATE ... CASCADE on app.users also empties every table with a foreign key to users
    (blog_settings, blog_brand_profiles, blog_notifications).
    """
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_COMMITTED_SQL))
    yield
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_COMMITTED_SQL))


@pytest_asyncio.fixture(loop_scope="session")
async def sessionmaker_committing(engine: AsyncEngine, clean_db: None) -> async_sessionmaker[AsyncSession]:
    """A real sessionmaker whose commits persist; `clean_db` removes the rows afterwards."""
    return make_sessionmaker(engine)


# --- T9: API fixtures ---

TEST_PASSWORD = "correct-horse-battery"
TEST_ORIGIN = "http://test"


@pytest.fixture
def fake_workflow_client() -> FakeWorkflowClient:
    return FakeWorkflowClient()


@pytest.fixture
def app(
    settings: Settings, engine: AsyncEngine, db_session: AsyncSession, fake_workflow_client: FakeWorkflowClient
) -> FastAPI:
    application = create_app(settings, workflow_client=fake_workflow_client)

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_session] = _session_override
    # ASGITransport does not run the lifespan, so provide what the lifespan would have set.
    application.state.settings = settings
    application.state.sessionmaker = make_sessionmaker(engine)
    application.state.workflow_client = fake_workflow_client
    return application


@pytest_asyncio.fixture(loop_scope="session")
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=TEST_ORIGIN, headers={"Origin": TEST_ORIGIN}
    ) as http:
        yield http


MakeUser = Callable[..., Awaitable[User]]
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]


@pytest.fixture
def make_user(db_session: AsyncSession) -> MakeUser:
    counter = itertools.count(1)

    async def _make(role: Role, *, email: str | None = None, password: str = TEST_PASSWORD) -> User:
        address = email or f"{role.value}-{next(counter)}@example.test"
        return await create_user(
            db_session, email=address, display_name=f"{role.value.title()} User", role=role, password=password
        )

    return _make


@pytest.fixture
def login_as(client: AsyncClient, make_user: MakeUser) -> LoginAs:
    async def _login(role: Role) -> tuple[AsyncClient, str]:
        user = await make_user(role)
        response = await client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        assert response.status_code == 200, response.text
        return client, str(response.json()["csrfToken"])

    return _login


# --- T11: DBOS fixtures ---
# In-process DBOS under pytest. DBOS.launch() runs inside the pytest-asyncio *session* loop, so queued and directly
# started async workflows run on the same loop as the tests.
# Variant used: in-loop launch (Task 11 Step 7 decision rule; the executor-thread fallback also passed in research).
DBOS_TEST_EXECUTOR_ID = "pytest"
DBOS_TEST_APP_VERSION = "pytest"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dbos_runtime(database_url: URL) -> AsyncIterator[WorkerRuntime]:
    test_settings = get_settings().model_copy(
        update={
            "postgres_db": TEST_DB,
            "mock_mode": True,
            "mock_step_delay_seconds": 0.0,
            "scheduler_enabled": False,
            # tests assert IST dates and must not hit the budget guard, whatever .env says
            "timezone": "Asia/Kolkata",
            "max_cost_per_run_usd": Decimal("5.00"),
        }
    )
    rt = await build_runtime(test_settings)
    async with rt.sessionmaker() as session:
        await rt.prompts.sync_to_db(session)
        await session.commit()
    set_runtime(rt)
    # Workflow modules register their steps and workflows when the test modules import them during
    # collection, which happens before this fixture runs, so they are registered before launch.
    DBOS(
        config=build_dbos_config(test_settings)
        | {"executor_id": DBOS_TEST_EXECUTOR_ID, "application_version": DBOS_TEST_APP_VERSION}
    )
    DBOS.launch()
    await DBOS.register_queue_async(QUEUE_PIPELINE, worker_concurrency=1)
    await DBOS.register_queue_async(QUEUE_INTERACTIVE, worker_concurrency=4)
    try:
        yield rt
    finally:
        await asyncio.to_thread(DBOS.destroy, destroy_registry=False)
        set_runtime(None)
        await rt.engine.dispose()


type MakeRun = Callable[..., Awaitable[uuid.UUID]]


@pytest_asyncio.fixture(loop_scope="session")
async def make_run(dbos_runtime: WorkerRuntime, clean_db: None) -> MakeRun:
    """Insert a blog_runs row through the worker runtime and return its id. Tables are truncated after the test."""

    async def _make(
        *, kind: RunKind = RunKind.MANUAL, run_date: date = date(2026, 1, 15), status: RunStatus = RunStatus.QUEUED
    ) -> uuid.UUID:
        run = BlogRun(kind=kind.value, run_date=run_date, status=status.value, params={}, trace_id=new_trace_id())
        async with dbos_runtime.sessionmaker() as session:
            session.add(run)
            await session.commit()
        return run.id

    return _make
