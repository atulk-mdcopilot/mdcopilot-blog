from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.rate_limit import (
    MAX_FAILURES_PER_EMAIL,
    MAX_FAILURES_PER_IP,
    WINDOW,
    login_allowed,
    record_login_attempt,
)
from mdcopilot_blog.db.models import LoginAttempt


def _now() -> datetime:
    # created_at comes from Postgres now(), so tests compare against the real clock.
    return datetime.now(UTC)


def test_constants() -> None:
    assert timedelta(minutes=15) == WINDOW
    assert MAX_FAILURES_PER_EMAIL == 5
    assert MAX_FAILURES_PER_IP == 20


async def _fail(db: AsyncSession, email: str, ip: str | None, times: int) -> None:
    for _ in range(times):
        await record_login_attempt(db, email=email, ip=ip, succeeded=False)


async def test_record_login_attempt_normalizes_email(db_session: AsyncSession) -> None:
    await record_login_attempt(db_session, email=" Rate@Example.TEST ", ip="10.0.0.9", succeeded=True)
    row = await db_session.scalar(select(LoginAttempt).where(LoginAttempt.ip == "10.0.0.9"))
    assert row is not None
    assert (row.email, row.succeeded) == ("rate@example.test", True)
    assert row.created_at is not None


async def test_fifth_failure_blocks_the_email(db_session: AsyncSession) -> None:
    await _fail(db_session, "five@example.test", "10.0.0.1", 4)
    assert await login_allowed(db_session, email="five@example.test", ip="10.0.0.1", now=_now()) is True
    await _fail(db_session, "five@example.test", "10.0.0.1", 1)
    assert await login_allowed(db_session, email="FIVE@example.test", ip="10.0.0.2", now=_now()) is False
    assert await login_allowed(db_session, email="other@example.test", ip="10.0.0.1", now=_now()) is True


async def test_successes_do_not_count(db_session: AsyncSession) -> None:
    for _ in range(10):
        await record_login_attempt(db_session, email="ok@example.test", ip="10.0.0.3", succeeded=True)
    assert await login_allowed(db_session, email="ok@example.test", ip="10.0.0.3", now=_now()) is True


async def test_twentieth_failure_blocks_the_ip(db_session: AsyncSession) -> None:
    for i in range(19):
        await record_login_attempt(db_session, email=f"u{i}@example.test", ip="10.0.0.4", succeeded=False)
    assert await login_allowed(db_session, email="fresh@example.test", ip="10.0.0.4", now=_now()) is True
    await record_login_attempt(db_session, email="u19@example.test", ip="10.0.0.4", succeeded=False)
    assert await login_allowed(db_session, email="fresh@example.test", ip="10.0.0.4", now=_now()) is False
    assert await login_allowed(db_session, email="fresh@example.test", ip="10.0.0.5", now=_now()) is True
    assert await login_allowed(db_session, email="fresh@example.test", ip=None, now=_now()) is True


async def test_failures_outside_the_window_are_ignored(db_session: AsyncSession) -> None:
    now = _now()
    db_session.add_all(
        LoginAttempt(email="old@example.test", ip="10.0.0.6", succeeded=False, created_at=now - timedelta(minutes=16))
        for _ in range(5)
    )
    await db_session.flush()
    assert await login_allowed(db_session, email="old@example.test", ip="10.0.0.6", now=now) is True
    db_session.add_all(
        LoginAttempt(email="old@example.test", ip="10.0.0.6", succeeded=False, created_at=now - timedelta(minutes=14))
        for _ in range(5)
    )
    await db_session.flush()
    assert await login_allowed(db_session, email="old@example.test", ip="10.0.0.6", now=now) is False
    # The same rows fall out of the window once time moves on.
    assert await login_allowed(db_session, email="old@example.test", ip="10.0.0.6", now=now + WINDOW) is True
    total = await db_session.scalar(select(func.count()).select_from(LoginAttempt))
    assert total == 10
