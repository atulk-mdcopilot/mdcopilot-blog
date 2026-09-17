"""ids.py: UUIDv7 primary keys and trace ids."""

import re
import uuid

from mdcopilot_blog.ids import new_trace_id, uuid7


def test_uuid7_returns_stdlib_uuid_version_7() -> None:
    value = uuid7()
    assert type(value) is uuid.UUID
    assert value.version == 7


def test_uuid7_values_are_unique_and_time_ordered() -> None:
    values = [uuid7() for _ in range(1000)]
    assert len(set(values)) == 1000
    assert values == sorted(values)


def test_new_trace_id_is_32_lowercase_hex_chars() -> None:
    trace_id = new_trace_id()
    assert re.fullmatch(r"[0-9a-f]{32}", trace_id)


def test_new_trace_ids_are_unique() -> None:
    assert len({new_trace_id() for _ in range(1000)}) == 1000
