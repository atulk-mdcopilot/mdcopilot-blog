"""Local user accounts."""

import asyncio
from functools import cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.passwords import hash_password, verify_password
from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Role

# The owner removed the 12-character rule (2026-09-17); only empty passwords are refused.
MIN_PASSWORD_LENGTH = 1


class UserExists(ValueError):
    """A user with this email already exists."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("password must not be empty")


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result: User | None = await db.scalar(select(User).where(User.email == normalize_email(email)))
    return result


async def create_user(db: AsyncSession, *, email: str, display_name: str, role: Role, password: str) -> User:
    """Insert a user and flush (no commit). Raises UserExists or ValueError (empty password)."""
    validate_password(password)
    normalized = normalize_email(email)
    if await get_user_by_email(db, normalized) is not None:
        raise UserExists(normalized)
    user = User(
        email=normalized,
        display_name=display_name.strip(),
        role=Role(role).value,
        password_hash=await asyncio.to_thread(hash_password, password),
        is_active=True,
    )
    try:
        # A SAVEPOINT keeps the caller's transaction usable if a concurrent insert wins the race.
        async with db.begin_nested():
            db.add(user)
            await db.flush()
    except IntegrityError as exc:
        raise UserExists(normalized) from exc
    return user


@cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def _dummy_verify(password: str) -> None:
    """Spend the same Argon2 time for unknown emails, so timing does not reveal which emails exist."""
    verify_password(password, _dummy_hash())


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User | None:
    """Return the active user for these credentials, or None. Upgrades an outdated hash in place (flush only)."""
    user = await get_user_by_email(db, email)
    if user is None:
        await asyncio.to_thread(_dummy_verify, password)
        return None
    ok, new_hash = await asyncio.to_thread(verify_password, password, user.password_hash)
    if not ok or not user.is_active:
        return None
    if new_hash is not None:
        user.password_hash = new_hash
        await db.flush()
    return user
