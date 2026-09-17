"""Argon2id password hashing (pwdlib)."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hash = PasswordHash.recommended()


def hash_password(pw: str) -> str:
    """Return an Argon2id hash with pwdlib's recommended parameters."""
    return _password_hash.hash(pw)


def verify_password(pw: str, hashed: str) -> tuple[bool, str | None]:
    """Return (ok, new_hash). Persist new_hash when it is not None (the stored parameters were outdated)."""
    try:
        return _password_hash.verify_and_update(pw, hashed)
    except UnknownHashError:
        return False, None
