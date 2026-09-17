"""The foundation migration: schema placement, named indexes, partial uniques, round trip, no drift."""

import io
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import URL, Connection, pool, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog.db.engine import make_engine
from mdcopilot_blog.db.models import BlogRun, BlogSetting

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

APP_TABLES = {
    "alembic_version",
    "audit_log",
    "blog_agent_runs",
    "blog_brand_profiles",
    "blog_content_pillars",
    "blog_llm_calls",
    "blog_notifications",
    "blog_prompt_versions",
    "blog_run_attempts",
    "blog_runs",
    "blog_settings",
    "login_attempts",
    "user_sessions",
    "users",
}

PARTIAL_UNIQUE_INDEXES = {
    "uq_blog_settings_active": (
        "CREATE UNIQUE INDEX uq_blog_settings_active ON app.blog_settings USING btree (is_active) WHERE is_active"
    ),
    "uq_blog_brand_profiles_active": (
        "CREATE UNIQUE INDEX uq_blog_brand_profiles_active ON app.blog_brand_profiles "
        "USING btree (is_active) WHERE is_active"
    ),
    "uq_blog_runs_daily_date": (
        "CREATE UNIQUE INDEX uq_blog_runs_daily_date ON app.blog_runs USING btree (run_date) "
        "WHERE ((kind)::text = 'daily'::text)"
    ),
}


def _alembic_config(output: io.StringIO | None = None) -> Config:
    cfg = Config(str(ALEMBIC_INI), stdout=output) if output is not None else Config(str(ALEMBIC_INI))
    cfg.attributes["configure_logger"] = False
    return cfg


def _run_alembic(sync_conn: Connection, cfg: Config, action: str, revision: str) -> None:
    # connection sharing: env.py uses this connection instead of calling asyncio.run()
    cfg.attributes["connection"] = sync_conn
    if action == "upgrade":
        command.upgrade(cfg, revision)
    elif action == "downgrade":
        command.downgrade(cfg, revision)
    else:
        command.check(cfg)


async def _app_tables(session: AsyncSession) -> set[str]:
    rows = await session.scalars(text("select table_name from information_schema.tables where table_schema = 'app'"))
    return set(rows.all())


def test_single_head_is_0001() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_heads() == ["0001"]
    revision = script.get_revision("0001")
    assert revision is not None
    assert revision.down_revision is None


async def test_tables_live_in_schema_app(db_session: AsyncSession) -> None:
    assert await _app_tables(db_session) == APP_TABLES
    public = await db_session.scalars(
        text("select table_name from information_schema.tables where table_schema = 'public'")
    )
    assert public.all() == []
    assert await db_session.scalar(text("select version_num from app.alembic_version")) == "0001"


async def test_vector_extension_and_dbos_schema_exist(db_session: AsyncSession) -> None:
    assert await db_session.scalar(text("select extname from pg_extension where extname = 'vector'")) == "vector"
    dbos_tables = await db_session.scalar(
        text("select count(*) from information_schema.tables where table_schema = 'dbos'")
    )
    assert dbos_tables is not None
    assert dbos_tables > 0


async def test_partial_unique_indexes_exist(db_session: AsyncSession) -> None:
    rows = await db_session.execute(
        text("select indexname, indexdef from pg_indexes where schemaname = 'app' and indexname = any(:names)"),
        {"names": list(PARTIAL_UNIQUE_INDEXES)},
    )
    assert dict(rows.tuples().all()) == PARTIAL_UNIQUE_INDEXES


async def test_named_indexes_exist(db_session: AsyncSession) -> None:
    rows = await db_session.scalars(text("select indexname from pg_indexes where schemaname = 'app'"))
    names = set(rows.all())
    assert {
        "ix_blog_runs_created_at",
        "ix_blog_runs_run_date",
        "ix_blog_runs_status",
        "ix_blog_llm_calls_provider_model",
        "ix_blog_llm_calls_created_at",
        "ix_blog_agent_runs_created_at",
        "uq_blog_agent_runs_wf_step",
        "uq_blog_run_attempts_dbos_workflow_id",
        "uq_blog_prompt_versions_name_version",
        "uq_users_email",
        "uq_user_sessions_token_hash",
        "uq_blog_content_pillars_key",
    } <= names


async def test_only_one_active_settings_version(db_session: AsyncSession) -> None:
    db_session.add(BlogSetting(version=1, values={}, is_active=True))
    await db_session.flush()
    db_session.add(BlogSetting(version=2, values={}, is_active=False))
    await db_session.flush()  # any number of inactive versions is fine
    db_session.add(BlogSetting(version=3, values={}, is_active=True))
    with pytest.raises(IntegrityError, match="uq_blog_settings_active"):
        await db_session.flush()
    await db_session.rollback()


async def test_one_daily_run_per_date_but_many_manual_runs(db_session: AsyncSession) -> None:
    day = date(2026, 9, 17)
    db_session.add_all(
        [
            BlogRun(kind="manual", run_date=day, status="QUEUED", trace_id="a" * 32),
            BlogRun(kind="manual", run_date=day, status="QUEUED", trace_id="b" * 32),
            BlogRun(kind="daily", run_date=day, status="QUEUED", trace_id="c" * 32),
        ]
    )
    await db_session.flush()
    db_session.add(BlogRun(kind="daily", run_date=day, status="QUEUED", trace_id="d" * 32))
    with pytest.raises(IntegrityError, match="uq_blog_runs_daily_date"):
        await db_session.flush()
    await db_session.rollback()


async def test_sessionmaker_committing_really_commits(
    sessionmaker_committing: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    async with sessionmaker_committing() as db:
        db.add(BlogRun(kind="manual", run_date=date(2026, 9, 18), status="QUEUED", trace_id="e" * 32))
        await db.commit()
    async with engine.connect() as conn:
        assert await conn.scalar(text("select count(*) from app.blog_runs")) == 1


async def test_clean_db_removed_the_committed_run(db_session: AsyncSession) -> None:
    assert await db_session.scalar(text("select count(*) from app.blog_runs")) == 0


async def test_downgrade_to_base_then_upgrade_to_head(database_url: URL) -> None:
    # own NullPool engine: the round trip must not share pooled connections with other tests
    eng = make_engine(database_url, poolclass=pool.NullPool)
    try:
        async with eng.connect() as conn:
            await conn.execute(text("SET lock_timeout = '10s'"))
            await conn.run_sync(_run_alembic, _alembic_config(), "downgrade", "base")
            remaining = await conn.scalars(
                text("select table_name from information_schema.tables where table_schema = 'app'")
            )
            assert remaining.all() == ["alembic_version"]
            await conn.run_sync(_run_alembic, _alembic_config(), "upgrade", "head")
            restored = await conn.scalars(
                text("select table_name from information_schema.tables where table_schema = 'app'")
            )
            assert set(restored.all()) == APP_TABLES
            assert await conn.scalar(text("select version_num from app.alembic_version")) == "0001"
    finally:
        await eng.dispose()


async def test_alembic_check_reports_no_drift(database_url: URL) -> None:
    output = io.StringIO()
    eng = make_engine(database_url, poolclass=pool.NullPool)
    try:
        async with eng.connect() as conn:
            await conn.run_sync(_run_alembic, _alembic_config(output), "check", "head")
    finally:
        await eng.dispose()
    assert "No new upgrade operations detected." in output.getvalue()
