"""Identifier helpers: UUIDv7 primary keys and per-run trace ids."""

import uuid

import uuid_utils


def uuid7() -> uuid.UUID:
    """Return a time-ordered UUIDv7 as a stdlib ``uuid.UUID`` (Python 3.12 has no ``uuid.uuid7``)."""
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)


def new_trace_id() -> str:
    """Return a 32-character lowercase hex trace id (the W3C trace-id width)."""
    return uuid.uuid4().hex
