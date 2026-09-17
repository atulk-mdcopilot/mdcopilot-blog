"""Alembic environment (async template, edited).

Edits from the `alembic init -t async` template:
- the URL comes from Config.attributes["database_url"] or Settings.database_url(), never from alembic.ini
  (ConfigParser interpolation breaks on "%" in percent-encoded passwords);
- every table and alembic_version live in schema "app"; autogenerate only looks at that schema;
- pgvector columns render as Vector(n) with an import (later phases add vector columns);
- a caller can pass an open sync connection in Config.attributes["connection"] (used inside event loops).
"""

import asyncio
from collections.abc import Mapping
from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import URL, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import mdcopilot_blog.db.models  # noqa: F401  (registers every table on Base.metadata)
from mdcopilot_blog.db.base import SCHEMA, Base

config = context.config

# Callers (pytest, the CLI) pass attributes["configure_logger"] = False to keep their own logging.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str | URL:
    url: str | URL | None = config.attributes.get("database_url")
    if url:
        return url  # never str(URL): SQLAlchemy masks the password as ***
    from mdcopilot_blog.settings import get_settings

    return get_settings().database_url()


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    if type_ == "type" and isinstance(obj, VECTOR):
        autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
        return f"Vector({obj.dim})"
    return False


def include_name(name: str | None, type_: str, parent_names: Mapping[str, str | None]) -> bool:
    if type_ == "schema":
        return name == SCHEMA
    return True


CONFIGURE_KW: dict[str, Any] = {
    "target_metadata": target_metadata,
    "version_table_schema": SCHEMA,
    "include_schemas": True,
    "include_name": include_name,
    "compare_server_default": True,
    "render_item": render_item,
}


def run_migrations_offline() -> None:
    context.configure(url=get_url(), literal_binds=True, dialect_opts={"paramstyle": "named"}, **CONFIGURE_KW)
    with context.begin_transaction():
        context.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # The schema must exist before Alembic creates app.alembic_version. Commit it so Alembic
    # still owns (and commits) its own transaction below.
    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    connection.commit()
    context.configure(connection=connection, **CONFIGURE_KW)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    connection: Connection | None = config.attributes.get("connection")
    if connection is None:
        asyncio.run(run_async_migrations())
    else:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
