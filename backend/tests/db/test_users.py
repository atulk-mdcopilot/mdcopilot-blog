import pytest
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.passwords import verify_password
from mdcopilot_blog.auth.users import (
    MIN_PASSWORD_LENGTH,
    UserExists,
    authenticate,
    create_user,
    get_user_by_email,
    normalize_email,
    set_password,
)
from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Role

PASSWORD = "correct-horse-battery"


def test_normalize_email() -> None:
    assert normalize_email("  Ann@Example.TEST ") == "ann@example.test"


def test_min_password_length_is_1() -> None:
    assert MIN_PASSWORD_LENGTH == 1


async def test_create_user_stores_normalized_email_and_hash(db_session: AsyncSession) -> None:
    user = await create_user(
        db_session, email=" Ann@Example.TEST ", display_name=" Ann ", role=Role.EDITOR, password=PASSWORD
    )
    assert user.id is not None
    assert user.email == "ann@example.test"
    assert user.display_name == "Ann"
    assert user.role == "editor"
    assert user.is_active is True
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash) == (True, None)
    assert user.created_at is not None


async def test_duplicate_email_raises_user_exists_and_session_stays_usable(db_session: AsyncSession) -> None:
    await create_user(db_session, email="dup@example.test", display_name="A", role=Role.VIEWER, password=PASSWORD)
    with pytest.raises(UserExists):
        await create_user(db_session, email="DUP@example.test", display_name="B", role=Role.ADMIN, password=PASSWORD)
    count = await db_session.scalar(select(func.count()).select_from(User).where(User.email == "dup@example.test"))
    assert count == 1


async def test_user_exists_is_a_value_error() -> None:
    assert issubclass(UserExists, ValueError)


async def test_short_password_is_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await create_user(db_session, email="short@example.test", display_name="S", role=Role.VIEWER, password="")
    assert await get_user_by_email(db_session, "short@example.test") is None


async def test_authenticate_success_and_failures(db_session: AsyncSession) -> None:
    await create_user(db_session, email="auth@example.test", display_name="A", role=Role.VIEWER, password=PASSWORD)
    user = await authenticate(db_session, email=" AUTH@example.test", password=PASSWORD)
    assert user is not None
    assert user.email == "auth@example.test"
    assert await authenticate(db_session, email="auth@example.test", password="wrong-password-123") is None
    assert await authenticate(db_session, email="nobody@example.test", password=PASSWORD) is None


async def test_authenticate_rejects_inactive_user(db_session: AsyncSession) -> None:
    user = await create_user(
        db_session, email="off@example.test", display_name="Off", role=Role.VIEWER, password=PASSWORD
    )
    user.is_active = False
    await db_session.flush()
    assert await authenticate(db_session, email="off@example.test", password=PASSWORD) is None


async def test_authenticate_rehashes_outdated_hash(db_session: AsyncSession) -> None:
    user = await create_user(
        db_session, email="old@example.test", display_name="Old", role=Role.VIEWER, password=PASSWORD
    )
    weak = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash(PASSWORD)
    user.password_hash = weak
    await db_session.flush()
    assert await authenticate(db_session, email="old@example.test", password=PASSWORD) is not None
    await db_session.refresh(user)
    assert user.password_hash != weak
    assert user.password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")


async def test_set_password(db_session: AsyncSession) -> None:
    user = await create_user(db_session, email="pw@example.test", display_name="P", role=Role.VIEWER, password=PASSWORD)
    with pytest.raises(ValueError, match="must not be empty"):
        await set_password(user, "")
    # the owner removed the 12-character minimum: a 9-character password is now accepted.
    await set_password(user, "Admin@123")
    await db_session.flush()
    assert await authenticate(db_session, email="pw@example.test", password=PASSWORD) is None
    assert await authenticate(db_session, email="pw@example.test", password="Admin@123") is not None
