"""logs.py: one JSON object per line, run/trace context, extra keys, and no secret values."""

import asyncio
import io
import json
import logging
import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from pydantic import SecretBytes, SecretStr

from mdcopilot_blog.logs import (
    JsonFormatter,
    bind_log_context,
    configure_logging,
    log_context,
    reset_log_context,
)


@pytest.fixture
def captured() -> Iterator[tuple[logging.Logger, io.StringIO]]:
    """A private logger that writes JSON lines into a buffer (does not touch the root logger)."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("tests.logs.captured")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    yield logger, buffer
    logger.handlers = []


@pytest.fixture
def restore_root_logging() -> Iterator[None]:
    root = logging.getLogger()
    level = root.level
    yield
    for handler in list(root.handlers):
        if isinstance(handler.formatter, JsonFormatter):
            root.removeHandler(handler)
    root.setLevel(level)


def _lines(buffer: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines()]


def test_each_record_is_one_json_object(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info("hello %s", "world")
    logger.warning("second line")
    first, second = _lines(buffer)
    assert set(first) == {"ts", "level", "logger", "message"}
    assert first["level"] == "INFO"
    assert first["logger"] == "tests.logs.captured"
    assert first["message"] == "hello world"
    assert second["level"] == "WARNING"
    assert isinstance(first["ts"], str)
    assert datetime.fromisoformat(first["ts"]).utcoffset() == UTC.utcoffset(None)


def test_bound_context_is_added_and_reset(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    token = bind_log_context(run_id="run-123", trace_id="a" * 32)
    try:
        logger.info("inside")
    finally:
        reset_log_context(token)
    logger.info("outside")
    inside, outside = _lines(buffer)
    assert inside["run_id"] == "run-123"
    assert inside["trace_id"] == "a" * 32
    assert "run_id" not in outside
    assert "trace_id" not in outside


def test_bind_merges_with_existing_context() -> None:
    assert log_context() == {}
    outer = bind_log_context(run_id="run-1")
    inner = bind_log_context(trace_id="b" * 32)
    try:
        assert log_context() == {"run_id": "run-1", "trace_id": "b" * 32}
    finally:
        reset_log_context(inner)
        assert log_context() == {"run_id": "run-1"}
        reset_log_context(outer)
    assert log_context() == {}


def test_log_context_returns_a_copy() -> None:
    token = bind_log_context(run_id="run-1")
    try:
        log_context()["run_id"] = "tampered"
        assert log_context() == {"run_id": "run-1"}
    finally:
        reset_log_context(token)


async def test_context_is_isolated_per_task(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured

    async def work(run_id: str) -> None:
        bind_log_context(run_id=run_id)
        await asyncio.sleep(0)
        logger.info("step")

    await asyncio.gather(work("run-a"), work("run-b"))
    assert sorted(str(line["run_id"]) for line in _lines(buffer)) == ["run-a", "run-b"]
    assert log_context() == {}


def test_extra_keys_are_included(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info("step finished", extra={"step": "hello.echo", "attempt": 2, "tags": ("a", "b"), "ok": True})
    (line,) = _lines(buffer)
    assert line["step"] == "hello.echo"
    assert line["attempt"] == 2
    assert line["tags"] == ["a", "b"]
    assert line["ok"] is True


def test_uvicorn_color_message_is_dropped(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info(
        "Uvicorn running on %s",
        "http://0.0.0.0:8000",
        extra={"color_message": "Uvicorn running on \x1b[1m%s\x1b[0m"},
    )
    output = buffer.getvalue()
    (line,) = _lines(buffer)
    assert "color_message" not in line
    assert line["message"] == "Uvicorn running on http://0.0.0.0:8000"
    assert "\x1b" not in output
    assert "\\u001b" not in output


def test_explicit_extra_overrides_bound_context(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    token = bind_log_context(run_id="from-context")
    try:
        logger.info("override", extra={"run_id": "from-extra"})
    finally:
        reset_log_context(token)
    assert _lines(buffer)[0]["run_id"] == "from-extra"


def test_non_json_values_are_stringified(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    when = datetime(2026, 9, 17, 7, 0, tzinfo=UTC)
    ident = uuid.UUID(int=1)
    logger.info("typed", extra={"when": when, "ident": ident, "nested": {"ids": [ident]}})
    (line,) = _lines(buffer)
    assert line["when"] == "2026-09-17 07:00:00+00:00"
    assert line["ident"] == "00000000-0000-0000-0000-000000000001"
    assert line["nested"] == {"ids": ["00000000-0000-0000-0000-000000000001"]}


def test_secret_values_never_appear(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info(
        "key=%s repr=%r",
        SecretStr("sk-live-message-arg"),
        SecretStr("sk-live-repr-arg"),
        extra={
            "api_key": SecretStr("sk-live-extra"),
            "raw_bytes": SecretBytes(b"bytes-secret-value"),
            "nested": {"password": SecretStr("nested-password"), "list": [SecretStr("listed-secret")]},
        },
    )
    output = buffer.getvalue()
    for raw in ("sk-live-message-arg", "sk-live-repr-arg", "sk-live-extra", "bytes-secret-value"):
        assert raw not in output
    assert "nested-password" not in output
    assert "listed-secret" not in output
    (line,) = _lines(buffer)
    assert line["api_key"] == "**********"
    assert line["raw_bytes"] == "**********"
    assert line["nested"] == {"password": "**********", "list": ["**********"]}


def test_exception_text_is_included(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("step failed")
    (line,) = _lines(buffer)
    assert line["level"] == "ERROR"
    assert "ValueError: boom" in str(line["exc_info"])


@pytest.mark.usefixtures("restore_root_logging")
def test_configure_logging_installs_one_json_handler_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("debug")
    configure_logging("DEBUG")
    root = logging.getLogger()
    ours = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
    assert len(ours) == 1
    assert isinstance(ours[0], logging.StreamHandler)
    assert ours[0].stream is sys.stdout
    assert root.level == logging.DEBUG
    logging.getLogger("tests.logs.root").debug("via root", extra={"step": "x"})
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[-1]["message"] == "via root"
    assert lines[-1]["step"] == "x"


@pytest.mark.usefixtures("restore_root_logging")
def test_configure_logging_routes_uvicorn_loggers_through_root() -> None:
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addHandler(logging.NullHandler())
    uvicorn_access.propagate = False
    configure_logging("INFO")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True
