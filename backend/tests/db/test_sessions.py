from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.sessions import (
    ABSOLUTE_TIMEOUT,
    IDLE_TIMEOUT,
    TOUCH_INTERVAL,
    create_session,
    hash_token,
    resolve_session,
    revoke_session,
    revoke_user_sessions,
)
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.models import User, UserSession
from mdcopilot_blog.domain.enums import Role

T0 = datetime(2026, 9, 17, 6, 0, tzinfo=UTC)


async def _user(db: AsyncSession, email: str = "sess@example.test") -> User:
    return await create_user(db, email=email, display_name="S", role=Role.EDITOR, password="correct-horse-battery")


def test_constants() -> None:
    assert timedelta(minutes=30) == IDLE_TIMEOUT
    assert timedelta(hours=12) == ABSOLUTE_TIMEOUT
    assert timedelta(seconds=60) == TOUCH_INTERVAL


def test_hash_token_is_sha256_hex() -> None:
    assert hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


async def test_create_session_stores_only_the_hash(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip="10.0.0.1", user_agent="pytest", now=T0)
    assert len(token) >= 40
    row = await db_session.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert row is not None
    assert row.token_hash == hash_token(token)
    assert row.token_hash != token
    assert row.expires_at == T0 + ABSOLUTE_TIMEOUT
    assert row.last_seen_at == T0
    assert (row.ip, row.user_agent) == ("10.0.0.1", "pytest")
    assert user.last_login_at == T0


async def test_create_session_truncates_long_client_values(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await create_session(db_session, user, ip="1" * 100, user_agent="u" * 1000, now=T0)
    row = await db_session.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert row is not None
    assert row.ip is not None
    assert row.user_agent is not None
    assert (len(row.ip), len(row.user_agent)) == (64, 400)


async def test_resolve_returns_user_and_session(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    resolved = await resolve_session(db_session, token, now=T0 + timedelta(seconds=5))
    assert resolved is not None
    assert resolved.user.id == user.id
    assert resolved.session.token_hash == hash_token(token)


async def test_unknown_and_empty_tokens(db_session: AsyncSession) -> None:
    assert await resolve_session(db_session, "no-such-token", now=T0) is None
    assert await resolve_session(db_session, "", now=T0) is None


async def test_idle_expiry(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=29)) is not None
    # The 29-minute resolve touched last_seen_at, so idle time restarts from there.
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=58)) is not None
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=58 + 31)) is None


async def test_absolute_expiry_even_when_active(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    for step in range(1, 29):  # a request every 25 minutes keeps the session from going idle
        assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=25 * step)) is not None
    assert await resolve_session(db_session, token, now=T0 + ABSOLUTE_TIMEOUT - timedelta(seconds=1)) is not None
    assert await resolve_session(db_session, token, now=T0 + ABSOLUTE_TIMEOUT) is None


async def test_touch_is_throttled(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    first = await resolve_session(db_session, token, now=T0 + timedelta(seconds=30))
    assert first is not None
    assert first.session.last_seen_at == T0
    second = await resolve_session(db_session, token, now=T0 + timedelta(seconds=61))
    assert second is not None
    await db_session.refresh(second.session)
    assert second.session.last_seen_at == T0 + timedelta(seconds=61)


async def test_revoke_session(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    other = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    await revoke_session(db_session, token, now=T0 + timedelta(minutes=1))
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=2)) is None
    assert await resolve_session(db_session, other, now=T0 + timedelta(minutes=2)) is not None
    row = await db_session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    assert row is not None
    await db_session.refresh(row)
    assert row.revoked_at == T0 + timedelta(minutes=1)


async def test_revoke_user_sessions_keeps_one(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    keep = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    drop_a = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    drop_b = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    later = T0 + timedelta(minutes=1)
    assert await revoke_user_sessions(db_session, user.id, now=later, keep_token=keep) == 2
    assert await resolve_session(db_session, keep, now=later) is not None
    assert await resolve_session(db_session, drop_a, now=later) is None
    assert await resolve_session(db_session, drop_b, now=later) is None
    assert await revoke_user_sessions(db_session, user.id, now=later) == 1


async def test_inactive_user_session_is_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    user.is_active = False
    await db_session.flush()
    assert await resolve_session(db_session, token, now=T0 + timedelta(seconds=5)) is None
