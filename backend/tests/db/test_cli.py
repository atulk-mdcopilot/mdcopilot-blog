"""CLI commands, called in-process through main(argv, settings=...) against the test database."""

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

import click
import pytest
import pytest_asyncio
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog import cli
from mdcopilot_blog.db.models import AuditLog, ContentPillar, PromptVersion, User
from mdcopilot_blog.settings import Settings

PASSWORD_ENV = "MDCB_TEST_CLI_PASSWORD"
LEAK_CANARY = "pw-canary-must-not-leak-7f3a"
TRUNCATE_CLI_SQL = (
    "TRUNCATE app.blog_content_pillars, app.blog_settings, app.blog_brand_profiles, "
    "app.blog_prompt_versions, app.audit_log, app.users RESTART IDENTITY CASCADE"
)


@pytest_asyncio.fixture(loop_scope="session")
async def cli_tables(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """The CLI commits for real, so empty its tables before and after each test."""
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_CLI_SQL))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_CLI_SQL))


async def run_cli(argv: Sequence[str], settings: Settings) -> int:
    # main() calls asyncio.run(); a worker thread has no running loop, so that is allowed there
    return await asyncio.to_thread(cli.main, list(argv), settings=settings)


async def test_seed_command_prints_report_and_is_idempotent(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run_cli(["seed"], settings) == 0
    assert "seed: settings_created=True brand_created=True pillars_created=6" in capsys.readouterr().out

    assert await run_cli(["seed"], settings) == 0
    assert "seed: settings_created=False brand_created=False pillars_created=0" in capsys.readouterr().out

    async with cli_tables() as db:
        assert await db.scalar(select(func.count()).select_from(ContentPillar)) == 6


async def test_sync_prompts_command_registers_prompt_files_once(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run_cli(["sync-prompts"], settings) == 0
    first = capsys.readouterr().out
    assert await run_cli(["sync-prompts"], settings) == 0
    assert "sync-prompts: 0 inserted" in capsys.readouterr().out

    async with cli_tables() as db:
        names = (await db.scalars(select(PromptVersion.name))).all()
    assert "hello/echo" in names
    assert f"sync-prompts: {len(names)} inserted" in first


async def test_create_admin_creates_admin_from_env_password(
    cli_tables: async_sessionmaker[AsyncSession],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "correct-horse-battery")
    argv = [
        "create-admin",
        "--email",
        " Admin@Example.TEST ",
        "--display-name",
        "Admin",
        "--password-env",
        PASSWORD_ENV,
    ]

    assert await run_cli(argv, settings) == 0
    out = capsys.readouterr().out
    assert "created admin admin@example.test" in out
    assert "correct-horse-battery" not in out

    async with cli_tables() as db:
        user = await db.scalar(select(User))
        actions = (await db.scalars(select(AuditLog.action))).all()
    assert user is not None
    assert (user.email, user.display_name, user.role, user.is_active) == ("admin@example.test", "Admin", "admin", True)
    assert user.password_hash.startswith("$argon2id$")
    assert actions == ["user.create"]


async def test_create_admin_twice_changes_nothing(
    cli_tables: async_sessionmaker[AsyncSession],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "correct-horse-battery")
    argv = ["create-admin", "--email", "admin@example.test", "--display-name", "Admin", "--password-env", PASSWORD_ENV]
    assert await run_cli(argv, settings) == 0
    monkeypatch.setenv(PASSWORD_ENV, "a-different-password-123")

    assert await run_cli(argv, settings) == 0
    assert "user admin@example.test already exists; nothing changed" in capsys.readouterr().out

    async with cli_tables() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1
        assert await db.scalar(select(func.count()).select_from(AuditLog)) == 1


async def test_create_admin_uses_bootstrap_password_variable_by_default(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password-123")
    assert await run_cli(["create-admin", "--email", "boot@example.test", "--display-name", "Boot"], settings) == 0
    async with cli_tables() as db:
        assert await db.scalar(select(User.role).where(User.email == "boot@example.test")) == "admin"


async def test_create_admin_refuses_bad_password_or_email(
    cli_tables: async_sessionmaker[AsyncSession],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["create-admin", "--email", "a@example.test", "--display-name", "A", "--password-env", PASSWORD_ENV]
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    assert await run_cli(argv, settings) == 2
    assert f"{PASSWORD_ENV} is not set" in capsys.readouterr().err

    # MIN_PASSWORD_LENGTH is now 1, so only an empty password is refused. os.environ.get(password_env, "")
    # returns "" for both an unset and an empty-string env var, and the CLI's "is not set" guard runs
    # before the length check, so an empty BOOTSTRAP_ADMIN_PASSWORD is still caught there (unchanged
    # missing-variable behaviour), not by the length branch's "is empty" message.
    monkeypatch.setenv(PASSWORD_ENV, "")
    assert await run_cli(argv, settings) == 2
    assert f"{PASSWORD_ENV} is not set" in capsys.readouterr().err

    monkeypatch.setenv(PASSWORD_ENV, "correct-horse-battery")
    blank_email = ["create-admin", "--email", "", "--display-name", "A", "--password-env", PASSWORD_ENV]
    assert await run_cli(blank_email, settings) == 2
    assert "--email must be an email address" in capsys.readouterr().err

    async with cli_tables() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_create_user_sets_the_requested_role(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "reviewer-password-123")
    argv = [
        "create-user",
        "--email",
        "rev@example.test",
        "--display-name",
        "Rev",
        "--role",
        "reviewer",
        "--password-env",
        PASSWORD_ENV,
    ]
    assert await run_cli(argv, settings) == 0
    async with cli_tables() as db:
        assert await db.scalar(select(User.role).where(User.email == "rev@example.test")) == "reviewer"


def test_create_user_rejects_unknown_role(settings: Settings) -> None:
    argv = ["create-user", "--email", "x@example.test", "--display-name", "X", "--role", "owner"]
    with pytest.raises(SystemExit) as excinfo:
        cli.main([*argv, "--password-env", PASSWORD_ENV], settings=settings)
    assert excinfo.value.code == 2


def _canary_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"postgres_password": SecretStr(LEAK_CANARY)})


def test_migrate_dbos_runs_in_process_and_never_prints_the_url(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    canary = _canary_settings(settings)
    calls: list[tuple[str, dict[str, Any]]] = []
    dbos_level_before = logging.getLogger("dbos").level

    def fake_migrations(system_database_url: str, **kwargs: Any) -> None:
        calls.append((system_database_url, kwargs))
        # dbos 3.0.0 logs this at INFO, with the password masked
        logging.getLogger("dbos").info("Initializing DBOS system database with URL: postgresql+psycopg://u:***@db/x")

    monkeypatch.setattr(cli, "run_dbos_database_migrations", fake_migrations)
    caplog.set_level(logging.INFO)

    assert cli.main(["migrate-dbos"], settings=canary) == 0

    assert calls == [(canary.dbos_system_database_url, {"schema": "dbos"})]
    assert LEAK_CANARY in calls[0][0]
    captured = capsys.readouterr()
    assert "migrate-dbos: DBOS system tables are up to date (schema dbos)" in captured.out
    assert LEAK_CANARY not in captured.out + captured.err + caplog.text
    assert "postgresql" not in captured.out + captured.err + caplog.text
    assert logging.getLogger("dbos").level == dbos_level_before


def test_migrate_dbos_failure_prints_the_redacted_cause(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing_migrations(system_database_url: str, **kwargs: Any) -> None:
        # dbos 3.0.0 echoes the cause to stdout, then raises click.exceptions.Exit(code=1)
        print(f"DBOS migrations failed: cannot use {system_database_url} ({LEAK_CANARY})")
        raise click.exceptions.Exit(code=1)

    monkeypatch.setattr(cli, "run_dbos_database_migrations", failing_migrations)

    assert cli.main(["migrate-dbos"], settings=_canary_settings(settings)) == 1
    captured = capsys.readouterr()
    assert "migrate-dbos: DBOS migrations failed: cannot use *** (***)" in captured.err
    assert LEAK_CANARY not in captured.out + captured.err
    assert "postgresql" not in captured.out + captured.err


def test_migrate_runs_alembic_then_dbos_seed_and_prompts(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def fake_upgrade(cfg: Config, revision: str) -> None:
        assert revision == "head"
        assert cfg.config_file_name == "alembic.ini"
        assert cfg.attributes["database_url"].database == settings.postgres_db
        assert cfg.attributes["configure_logger"] is False
        order.append("alembic")

    def step(name: str) -> Any:
        def _run(passed: Settings) -> int:
            assert passed is settings
            order.append(name)
            return 0

        return _run

    monkeypatch.setattr(cli.command, "upgrade", fake_upgrade)
    monkeypatch.setattr(cli, "migrate_dbos", step("dbos"))
    monkeypatch.setattr(cli, "seed", step("seed"))
    monkeypatch.setattr(cli, "sync_prompts", step("prompts"))

    assert cli.main(["migrate"], settings=settings) == 0
    assert order == ["alembic", "dbos", "seed", "prompts"]


def test_migrate_stops_at_the_first_failing_step(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    monkeypatch.setattr(cli.command, "upgrade", lambda cfg, revision: order.append("alembic"))
    monkeypatch.setattr(cli, "migrate_dbos", lambda s: order.append("dbos") or 1)
    monkeypatch.setattr(cli, "seed", lambda s: order.append("seed") or 0)
    monkeypatch.setattr(cli, "sync_prompts", lambda s: order.append("prompts") or 0)

    assert cli.main(["migrate"], settings=settings) == 1
    assert order == ["alembic", "dbos"]
