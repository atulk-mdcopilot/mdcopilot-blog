"""CSRF primitives: a session-bound token and the Origin allow-list check."""

import hashlib
import hmac

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def csrf_token_for(session_token: str, secret: str) -> str:
    """Derive the CSRF token from the raw session token, so it needs no storage."""
    return hmac.new(secret.encode(), b"csrf:" + session_token.encode(), hashlib.sha256).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    """Constant-time comparison. Bytes, so non-ASCII header values cannot raise TypeError."""
    return hmac.compare_digest(a.encode(), b.encode())


def origin_allowed(
    origin: str | None,
    *,
    host: str | None,
    forwarded_proto: str | None,
    scheme: str,
    public_app_url: str,
) -> bool:
    """True iff Origin is the configured public URL or the origin the request was addressed to."""
    if not origin:
        return False
    candidate = origin.strip().lower()
    if candidate == public_app_url.strip().rstrip("/").lower():
        return True
    if not host:
        return False
    # X-Forwarded-Proto may be a comma-separated chain; the first entry is the client-facing scheme.
    proto = (forwarded_proto or scheme).split(",")[0].strip().lower()
    return candidate == f"{proto}://{host.strip().lower()}"
