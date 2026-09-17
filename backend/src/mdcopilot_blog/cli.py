"""Operator commands: ``python -m mdcopilot_blog.cli <command>``.

Commands: migrate, migrate-dbos, seed, sync-prompts, create-admin, create-user.
Passwords are read from an environment variable, never from the command line.
"""

import argparse
import asyncio
import io
import logging
import os
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, redirect_stdout

from alembic import command
from alembic.config import Config
from dbos import run_dbos_database_migrations
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.users import (
    MIN_PASSWORD_LENGTH,
    UserExists,
    create_user,
    get_user_by_email,
    normalize_email,
)
from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.db.seed import SeedReport, seed_defaults
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.prompts.registry import PromptRegistry, PromptRegistryError, default_prompt_root
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.settings import Settings, get_settings

ALEMBIC_INI = "alembic.ini"  # relative to the working directory (/app in every backend container)
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


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
            run_dbos_database_migrations(url, schema="dbos")
    except RuntimeError:  # dbos echoes the cause, then raises click.exceptions.Exit(1), a RuntimeError
        detail = _redact(captured.getvalue().strip(), url, settings.postgres_password.get_secret_value())
        print(f"migrate-dbos: {detail or 'DBOS migrations failed'}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        dbos_logger.setLevel(previous_level)
    print("migrate-dbos: DBOS system tables are up to date (schema dbos)")
    return EXIT_OK


async def _seed(settings: Settings) -> SeedReport:
    async with _session(settings) as db:
        report = await seed_defaults(db)
        await db.commit()
    return report


def seed(settings: Settings) -> int:
    report = asyncio.run(_seed(settings))
    print(
        f"seed: settings_created={report.settings_created} brand_created={report.brand_created} "
        f"pillars_created={report.pillars_created}"
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


async def _create_account(
    settings: Settings, *, email: str, display_name: str, role: Role, password: str
) -> tuple[bool, str]:
    """Return (created, stored email). An existing account is never modified."""
    normalized = normalize_email(email)
    async with _session(settings) as db:
        if await get_user_by_email(db, normalized) is not None:
            return False, normalized
        try:
            user = await create_user(db, email=normalized, display_name=display_name, role=role, password=password)
        except UserExists:
            await db.rollback()
            return False, normalized
        await db.flush()
        await audit(
            db,
            actor_user_id=None,
            action="user.create",
            entity_type="user",
            entity_id=str(user.id),
            details={"role": role.value, "via": "cli"},
        )
        await db.commit()
        return True, user.email


def create_account(settings: Settings, *, email: str, display_name: str, role: Role, password_env: str) -> int:
    if "@" not in email:
        print(f"--email must be an email address, got {email!r}", file=sys.stderr)
        return EXIT_USAGE
    password = os.environ.get(password_env, "")
    if not password:
        print(f"{password_env} is not set; put the password in that environment variable", file=sys.stderr)
        return EXIT_USAGE
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"the password in {password_env} is empty", file=sys.stderr)
        return EXIT_USAGE
    created, stored_email = asyncio.run(
        _create_account(settings, email=email, display_name=display_name, role=role, password=password)
    )
    if created:
        print(f"created {role.value} {stored_email}")
    else:
        print(f"user {stored_email} already exists; nothing changed")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mdcopilot_blog.cli", description="mdcopilot-blog operator commands"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="alembic upgrade head, then migrate-dbos, seed and sync-prompts")
    sub.add_parser("migrate-dbos", help="create or upgrade the DBOS system tables (schema dbos)")
    sub.add_parser("seed", help="insert default settings, brand profile and content pillars (idempotent)")
    sub.add_parser("sync-prompts", help="register prompt files in blog_prompt_versions")

    admin = sub.add_parser("create-admin", help="create an admin account; no change if the email exists")
    admin.add_argument("--email", required=True)
    admin.add_argument("--display-name", required=True)
    admin.add_argument("--password-env", default="BOOTSTRAP_ADMIN_PASSWORD", metavar="VAR")

    user = sub.add_parser("create-user", help="create an account with a role; no change if the email exists")
    user.add_argument("--email", required=True)
    user.add_argument("--display-name", required=True)
    user.add_argument("--role", required=True, choices=[role.value for role in Role])
    user.add_argument("--password-env", required=True, metavar="VAR")
    return parser


def main(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int:
    """Run one command. Tests pass ``settings`` (the test database); then logging is left alone."""
    args = build_parser().parse_args(argv)
    if settings is None:
        settings = get_settings()
        configure_logging(settings.log_level)

    name: str = args.command
    if name == "migrate":
        return migrate(settings)
    if name == "migrate-dbos":
        return migrate_dbos(settings)
    if name == "seed":
        return seed(settings)
    if name == "sync-prompts":
        return sync_prompts(settings)
    role = Role.ADMIN if name == "create-admin" else Role(args.role)
    return create_account(
        settings, email=args.email, display_name=args.display_name, role=role, password_env=args.password_env
    )


if __name__ == "__main__":
    raise SystemExit(main())
