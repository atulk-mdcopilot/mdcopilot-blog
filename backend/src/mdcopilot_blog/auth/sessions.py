"""Database-backed login sessions. Only the SHA-256 of the session token is stored."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import User, UserSession

IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=12)
TOUCH_INTERVAL = timedelta(seconds=60)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class ResolvedSession:
    user: User
    session: UserSession


async def create_session(db: AsyncSession, user: User, *, ip: str | None, user_agent: str | None, now: datetime) -> str:
    """Create a session row and return the raw token (flush only; the caller commits)."""
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            last_seen_at=now,
            expires_at=now + ABSOLUTE_TIMEOUT,
            ip=ip[:64] if ip else None,
            user_agent=user_agent[:400] if user_agent else None,
        )
    )
    user.last_login_at = now
    await db.flush()
    return token


async def resolve_session(db: AsyncSession, token: str, *, now: datetime) -> ResolvedSession | None:
    """Return the live session for a token, or None if unknown, revoked, idle, expired or the user is inactive."""
    if not token:
        return None
    row = (
        (
            await db.execute(
                select(UserSession, User)
                .join(User, User.id == UserSession.user_id)
                .where(UserSession.token_hash == hash_token(token))
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        return None
    session, user = row
    if session.revoked_at is not None:
        return None
    if now >= session.expires_at:
        return None
    if now - session.last_seen_at >= IDLE_TIMEOUT:
        return None
    if not user.is_active:
        return None
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.flush()
    return ResolvedSession(user=user, session=session)


async def revoke_session(db: AsyncSession, token: str, *, now: datetime) -> None:
    """Mark one session revoked (no commit)."""
    await db.execute(
        update(UserSession)
        .where(UserSession.token_hash == hash_token(token), UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_user_sessions(
    db: AsyncSession, user_id: uuid.UUID, *, now: datetime, keep_token: str | None = None
) -> int:
    """Revoke every live session of a user, optionally keeping one (no commit). Returns the count revoked."""
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if keep_token is not None:
        stmt = stmt.where(UserSession.token_hash != hash_token(keep_token))
    result = await db.execute(stmt)
    assert isinstance(result, CursorResult)
    return int(result.rowcount)
