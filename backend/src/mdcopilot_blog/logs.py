"""Structured JSON logs on stdout, carrying `run_id` and `trace_id` from context variables.

Secret values never reach the output: `SecretStr`, `SecretBytes` and `Secret` values in `extra`
(including nested dicts and lists) are replaced with a mask, and pydantic already masks them in
`str()`/`repr()`, which covers `%s`/`%r` message arguments. Never log `get_secret_value()`.
"""

import json
import logging
import sys
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from types import MappingProxyType

from pydantic import Secret, SecretBytes, SecretStr

MASK = "**********"
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
# Attributes every LogRecord has; anything else on a record came from `extra=`. Also skipped:
# "color_message", which uvicorn adds via `extra=` as an ANSI-coloured duplicate of the message.
_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "color_message",
}

LogContext = Mapping[str, str]
_log_context: ContextVar[LogContext | None] = ContextVar("mdcopilot_blog_log_context", default=None)


def bind_log_context(*, run_id: str | None = None, trace_id: str | None = None) -> None:
    """Add `run_id`/`trace_id` to the current task's context."""
    merged = dict(_log_context.get() or {})
    if run_id is not None:
        merged["run_id"] = run_id
    if trace_id is not None:
        merged["trace_id"] = trace_id
    _log_context.set(MappingProxyType(merged))


def log_context() -> dict[str, str]:
    """A copy of the currently bound context (empty when nothing is bound)."""
    return dict(_log_context.get() or {})


def _redact(value: object) -> object:
    if isinstance(value, SecretStr | SecretBytes | Secret):
        return MASK
    if isinstance(value, Mapping):
        return {str(key): _redact(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_redact(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, message, bound context, then `extra` keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(log_context())
        for key, value in record.__dict__.items():
            if key not in _RECORD_ATTRS and not key.startswith("_"):
                payload[key] = _redact(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    """Send every log record to stdout as JSON at `level` (a name such as "INFO").

    Safe to call more than once: it replaces the handler it installed earlier and leaves other root
    handlers alone. Uvicorn's loggers lose their own handlers and
    propagate to the root, so access and error logs are JSON too. Call it after uvicorn has configured
    logging (inside the app factory) and at worker start-up.
    """
    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing.formatter, JsonFormatter):
            root.removeHandler(existing)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
