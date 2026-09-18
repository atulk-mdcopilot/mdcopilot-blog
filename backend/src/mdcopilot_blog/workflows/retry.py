"""A single bounded retry policy for durable steps."""

import psycopg
from dbos import StepOptions
from dbos._error import DBOSWorkflowCancelledError as WorkflowCancelledError
from sqlalchemy.exc import InterfaceError, OperationalError

STEP_MAX_ATTEMPTS = 6
STEP_INTERVAL_SECONDS = 2.0
STEP_BACKOFF_RATE = 2.0


def transient(exc: BaseException) -> bool:
    return isinstance(exc, (OperationalError, InterfaceError, psycopg.OperationalError, ConnectionError))


def step_options(name: str, *, retries: bool = True, timeout_seconds: float | None = None) -> StepOptions:
    return {
        "name": name,
        "retries_allowed": retries,
        "max_attempts": STEP_MAX_ATTEMPTS if retries else 1,
        "interval_seconds": STEP_INTERVAL_SECONDS,
        "backoff_rate": STEP_BACKOFF_RATE,
        "should_retry": transient,
        "timeout_seconds": timeout_seconds,
    }


__all__ = ["WorkflowCancelledError", "step_options", "transient"]
