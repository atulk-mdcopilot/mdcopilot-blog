"""Async engine and session factories (psycopg 3 driver)."""

from typing import Any

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def make_engine(url: URL | str, **kw: Any) -> AsyncEngine:
    """Pass a ``URL`` object where possible: ``str(URL)`` masks the password as ``***``."""
    return create_async_engine(url, pool_pre_ping=True, **kw)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
