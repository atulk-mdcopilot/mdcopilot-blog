import pytest

from mdcopilot_blog.auth.csrf import SAFE_METHODS, csrf_token_for, origin_allowed, tokens_match

SECRET = "s" * 40


def test_token_is_deterministic_hex_sha256() -> None:
    token = csrf_token_for("session-a", SECRET)
    assert token == csrf_token_for("session-a", SECRET)
    assert len(token) == 64
    assert int(token, 16) >= 0


def test_token_depends_on_session_and_secret() -> None:
    assert csrf_token_for("session-a", SECRET) != csrf_token_for("session-b", SECRET)
    assert csrf_token_for("session-a", SECRET) != csrf_token_for("session-a", "t" * 40)


def test_token_is_not_the_session_token() -> None:
    assert "session-a" not in csrf_token_for("session-a", SECRET)


def test_tokens_match() -> None:
    assert tokens_match("abc", "abc") is True
    assert tokens_match("abc", "abd") is False
    assert tokens_match("abc", "") is False


def test_tokens_match_accepts_non_ascii_without_raising() -> None:
    assert tokens_match("abc", "abé") is False


def test_safe_methods() -> None:
    assert frozenset({"GET", "HEAD", "OPTIONS"}) == SAFE_METHODS


def _allowed(origin: str | None, host: str | None = "api:8000", proto: str | None = None, scheme: str = "http") -> bool:
    return origin_allowed(
        origin, host=host, forwarded_proto=proto, scheme=scheme, public_app_url="http://localhost:8310/"
    )


@pytest.mark.parametrize(
    ("origin", "host", "proto", "scheme", "expected"),
    [
        ("http://localhost:8310", "api:8000", None, "http", True),  # public URL, trailing slash stripped
        ("http://web:5173", "web:5173", "http", "http", True),  # Vite proxy with changeOrigin:false
        ("https://blog.example", "blog.example", "https", "http", True),  # TLS terminated upstream
        ("https://blog.example", "blog.example", "https,http", "http", True),  # proxy chain
        ("http://blog.example", "blog.example", "https", "http", False),  # scheme mismatch
        ("https://blog.example", "blog.example", None, "http", False),  # no forwarded proto
        ("http://evil.example", "api:8000", None, "http", False),
        ("null", "api:8000", None, "http", False),
        ("http://WEB:5173", "web:5173", None, "http", True),  # case-insensitive
        (None, "api:8000", None, "http", False),
        ("", "api:8000", None, "http", False),
        ("http://web:5173", None, None, "http", False),
    ],
)
def test_origin_allowed(origin: str | None, host: str | None, proto: str | None, scheme: str, expected: bool) -> None:
    assert _allowed(origin, host, proto, scheme) is expected
