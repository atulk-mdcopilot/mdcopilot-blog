"""Operator commands: ``python -m mdcopilot_blog.cli <command>``.

Commands: migrate, migrate-dbos, seed, sync-prompts.
"""

import argparse
import asyncio
import io
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, redirect_stdout

from alembic import command
from alembic.config import Config
from dbos import run_dbos_database_migrations
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.db.seed import SeedReport, seed_defaults
from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.prompts.registry import PromptRegistry, PromptRegistryError, default_prompt_root
from mdcopilot_blog.settings import Settings, get_settings
from mdcopilot_blog.workflows.dbos_config import DBOS_SYSTEM_SCHEMA

ALEMBIC_INI = "alembic.ini"  # relative to the working directory (/app in every backend container)
EXIT_OK = 0
EXIT_FAILED = 1


@asynccontextmanager
async def _session(settings: Settings) -> AsyncIterator[AsyncSession]:
    engine = make_engine(settings.database_url())
    try:
        async with make_sessionmaker(engine)() as session:
            yield session
    finally:
        await engine.dispose()


def alembic_upgrade(settings: Settings) -> int:
    cfg = Config(ALEMBIC_INI)
    cfg.attributes["database_url"] = settings.database_url()
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    print("migrate: alembic upgrade head done")
    return EXIT_OK


def _redact(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def migrate_dbos(settings: Settings) -> int:
    """Create or upgrade the DBOS system tables in-process (what ``dbos migrate`` runs).

    In-process, so the password never sits in a child process's argv, where ``ps`` could read it.
    """
    url = settings.dbos_system_database_url
    dbos_logger = logging.getLogger("dbos")
    previous_level = dbos_logger.level
    dbos_logger.setLevel(logging.WARNING)  # dbos logs the (masked) URL at INFO; keep URLs out of our output
    captured = io.StringIO()
    try:
        with redirect_stdout(captured):  # dbos echoes a failure's cause to stdout
            run_dbos_database_migrations(url, schema=DBOS_SYSTEM_SCHEMA)
    except RuntimeError:  # dbos echoes the cause, then raises click.exceptions.Exit(1), a RuntimeError
        detail = _redact(captured.getvalue().strip(), url, settings.database_url().password or "")
        print(f"migrate-dbos: {detail or 'DBOS migrations failed'}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        dbos_logger.setLevel(previous_level)
    print(f"migrate-dbos: DBOS system tables are up to date (schema {DBOS_SYSTEM_SCHEMA})")
    return EXIT_OK


async def _seed(settings: Settings) -> SeedReport:
    async with _session(settings) as db:
        report = await seed_defaults(db)
        await db.commit()
    return report


def seed(settings: Settings) -> int:
    report = asyncio.run(_seed(settings))
    print(
        f"seed: brand_created={report.brand_created} pillars_created={report.pillars_created} "
        f"domains_created={report.domains_created} price_overrides_created={report.price_overrides_created}"
    )
    return EXIT_OK


async def _sync_prompts(settings: Settings) -> int:
    registry = PromptRegistry.from_directory(default_prompt_root())
    async with _session(settings) as db:
        inserted = await registry.sync_to_db(db)
        await db.commit()
    return inserted


def sync_prompts(settings: Settings) -> int:
    try:
        inserted = asyncio.run(_sync_prompts(settings))
    except PromptRegistryError as exc:
        print(f"sync-prompts: {exc}", file=sys.stderr)
        return EXIT_FAILED
    print(f"sync-prompts: {inserted} inserted")
    return EXIT_OK


def migrate(settings: Settings) -> int:
    for step in (alembic_upgrade, migrate_dbos, seed, sync_prompts):
        code = step(settings)
        if code != EXIT_OK:
            return code
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mdcopilot_blog.cli", description="mdcopilot-blog operator commands"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="alembic upgrade head, then migrate-dbos, seed and sync-prompts")
    sub.add_parser("migrate-dbos", help=f"create or upgrade the DBOS system tables (schema {DBOS_SYSTEM_SCHEMA})")
    sub.add_parser(
        "seed",
        help="insert the default brand profile, content pillars, source domains and price overrides (idempotent)",
    )
    sub.add_parser("sync-prompts", help="register prompt files in blog_prompt_versions")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)

    name: str = args.command
    if name == "migrate":
        return migrate(settings)
    if name == "migrate-dbos":
        return migrate_dbos(settings)
    if name == "seed":
        return seed(settings)
    return sync_prompts(settings)


if __name__ == "__main__":
    raise SystemExit(main())
