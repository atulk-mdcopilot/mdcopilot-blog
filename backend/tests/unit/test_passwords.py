from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from mdcopilot_blog.auth.passwords import hash_password, verify_password


def test_hash_is_argon2id_with_recommended_parameters() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert "correct-horse-battery" not in hashed


def test_same_password_hashes_differently() -> None:
    assert hash_password("correct-horse-battery") != hash_password("correct-horse-battery")


def test_verify_correct_password_needs_no_rehash() -> None:
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed) == (True, None)


def test_verify_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery")
    assert verify_password("wrong-horse-battery", hashed) == (False, None)


def test_verify_garbage_hash_is_false_not_an_error() -> None:
    assert verify_password("correct-horse-battery", "not-a-hash") == (False, None)


def test_weak_parameters_are_upgraded() -> None:
    weak = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash("correct-horse-battery")
    ok, new_hash = verify_password("correct-horse-battery", weak)
    assert ok is True
    assert new_hash is not None
    assert new_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
