"""Login throttling backed by the login_attempts table."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.users import normalize_email
from mdcopilot_blog.db.models import LoginAttempt

WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_IP = 20


async def _failures(db: AsyncSession, *, since: datetime, email: str | None = None, ip: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.succeeded.is_(False), LoginAttempt.created_at > since)
    )
    if email is not None:
        stmt = stmt.where(LoginAttempt.email == email)
    if ip is not None:
        stmt = stmt.where(LoginAttempt.ip == ip)
    return int(await db.scalar(stmt) or 0)


async def login_allowed(db: AsyncSession, *, email: str, ip: str | None, now: datetime) -> bool:
    """False once an email has 5, or an IP has 20, failed attempts inside the last 15 minutes."""
    since = now - WINDOW
    if await _failures(db, since=since, email=normalize_email(email)) >= MAX_FAILURES_PER_EMAIL:
        return False
    return not (ip is not None and await _failures(db, since=since, ip=ip[:64]) >= MAX_FAILURES_PER_IP)


async def record_login_attempt(db: AsyncSession, *, email: str, ip: str | None, succeeded: bool) -> None:
    """Insert one attempt row (flush only). created_at comes from the database clock."""
    db.add(LoginAttempt(email=normalize_email(email)[:320], ip=ip[:64] if ip else None, succeeded=succeeded))
    await db.flush()
