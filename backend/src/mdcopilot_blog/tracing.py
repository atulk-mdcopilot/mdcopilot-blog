"""Langfuse tracing for the blog (architecture §16.10): one client per process, built from Settings, off by default.

With LANGFUSE_TRACING_ENABLED=false (the default) every helper is a no-op and `langfuse` is never imported.
Input/output reach Langfuse only through `content()` and only when OBSERVABILITY_CAPTURE_CONTENT=full; metadata
only under the META_KEYS allowlist that `_mask` enforces. Statuses carry exception class names, never messages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager, suppress
from typing import TYPE_CHECKING, Any

from dbos._error import DBOSWorkflowCancelledError

from mdcopilot_blog.domain.enums import CallKind, CallStatus

if TYPE_CHECKING:
    from langfuse import Langfuse

    from mdcopilot_blog.llm.recorder import CallRecord
    from mdcopilot_blog.settings import Settings

logger = logging.getLogger("mdcopilot_blog.tracing")

# The only metadata keys `_mask` lets through (§16.10.1). Add a key here before emitting it.
META_KEYS = frozenset(
    {
        "run_id",
        "dbos_workflow_id",
        "dbos_step_id",
        "workflow_name",
        "agent",
        "tries",
        "attempt",
        "attempt_index",
        "fallback_from",
        "requested_model",
        "requests",
        "prompt_name",
        "prompt_version",
        "prompt_sha",
        "agent_run_id",
        "price_source",
        "price_version",
        "ledger_row_id",
        "purpose",
        "mode",
        "search_actions",
        "sources",
        "citations",
        "count",
        "status",
        "bytes",
        "usage_missing",
        "usage_missing_reason",
        "usage_inconsistent",
        "error_class",
    }
)
CAPTURE_VALUES = frozenset({"none", "full"})
# Langfuse environment rule: lowercase, not starting with "langfuse", at most 40 characters.
_ENVIRONMENT = re.compile(r"(?!langfuse)[a-z0-9_-]{1,40}")
# Agent rows: pydantic-ai input_tokens includes cache reads and writes, so the exclusive Langfuse `input` bucket
# subtracts both (§16.10.5 mapping). Evidence: genai-prices 0.1.7 adds Anthropic cache_creation/cache_read into
# input_tokens; Gemini promptTokenCount and OpenAI prompt tokens include cached tokens. Still Requires
# Verification V6 (§26.9): compare usage_raw.requests[*].details for one call per provider, and set this to
# False if the ledger's input_tokens turn out to be exclusive.
INPUT_INCLUDES_CACHE = True

_client: Langfuse | None = None
_capture_full = False


def init(s: Settings) -> Langfuse | None:
    """Build this process's client from Settings after the §17.10 checks (rules 0-5).

    Returns None, with tracing off, when disabled or misconfigured. Logs setting names, never values, and
    never raises: telemetry must not block boot (§17.1 rule 5).
    """
    global _client, _capture_full
    if not s.langfuse_tracing_enabled:
        return None  # rule 1, the kill switch: langfuse is not imported
    required = {
        "LANGFUSE_BASE_URL": s.langfuse_base_url,
        "LANGFUSE_PUBLIC_KEY": s.langfuse_public_key,
        "LANGFUSE_SECRET_KEY": s.langfuse_secret_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:  # rule 2: never fall back to the SDK's EU-cloud default
        logger.warning("langfuse tracing off: required settings are empty", extra={"settings": missing})
        return None
    environment = s.langfuse_tracing_environment or s.app_env
    if not _ENVIRONMENT.fullmatch(environment):  # rule 3
        logger.warning("LANGFUSE_TRACING_ENVIRONMENT is invalid; using APP_ENV")
        environment = s.app_env
    sample_rate = s.langfuse_sample_rate
    if not 0.0 <= sample_rate <= 1.0:  # rule 4: the SDK constructor would raise ValueError
        logger.warning("LANGFUSE_SAMPLE_RATE is outside [0, 1]; using 1.0")
        sample_rate = 1.0
    capture = s.observability_capture_content.strip().lower()
    if capture not in CAPTURE_VALUES:  # rule 5 (blog: none or full)
        logger.warning("OBSERVABILITY_CAPTURE_CONTENT is not none or full; using none")
        capture = "none"
    # rule 0: env-only SDK switches, set before the client exists. Enough while the blog has no @observe.
    os.environ.setdefault("LANGFUSE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED", "false")
    os.environ.setdefault("LANGFUSE_MEDIA_UPLOAD_ENABLED", "false")
    try:
        import langfuse

        lf = langfuse.Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key.get_secret_value(),
            base_url=s.langfuse_base_url,
            environment=environment,
            release=s.langfuse_release or s.app_version,
            sample_rate=sample_rate,
            timeout=s.langfuse_timeout,
            flush_interval=s.langfuse_flush_interval,
            mask=_mask,
        )
    except Exception as exc:  # noqa: BLE001 - telemetry must not block boot
        logger.warning("langfuse tracing off: client not built", extra={"error_class": type(exc).__name__})
        return None
    _client, _capture_full = lf, capture == "full"
    logger.info("langfuse tracing enabled")
    return lf


def client() -> Langfuse | None:
    return _client


def shutdown() -> None:
    """Flush and stop the client. It blocks while it flushes. Never raises.

    API: `await asyncio.to_thread(shutdown)`. Worker: call it inline after `DBOS.destroy` (DBOS shuts down the
    loop's default executor).
    """
    global _client
    if _client is None:
        return
    try:
        _client.shutdown()
    except Exception as exc:  # noqa: BLE001 - shutdown never raises
        logger.warning("langfuse shutdown failed", extra={"error_class": type(exc).__name__})
    _client = None


def capture_full() -> bool:
    return _client is not None and _capture_full


def content(value: Any) -> dict[str, Any] | None:
    """The only way blog code sets input/output: wrapped so that `_mask` can tell content from metadata."""
    return {"mdc_content": value} if capture_full() else None


def _mask(*, data: Any, **_: Any) -> Any:
    """D3 layer 3; the SDK passes input, output and metadata here. It must never raise."""
    try:
        if isinstance(data, dict) and set(data) == {"mdc_content"}:
            return data if capture_full() else None
        if isinstance(data, dict):
            kept = {k: v for k, v in data.items() if k in META_KEYS and isinstance(v, (str, int, float, bool))}
            return kept or None
        return None  # any other shape is unwrapped content: dropped
    except Exception:  # noqa: BLE001 - a mask must never raise (the SDK would log str(exc))
        return None


def _status(exc: BaseException) -> tuple[str, str]:
    """Level and status message for an exception: the class name only, never str(exc) (D7)."""
    if isinstance(exc, (asyncio.CancelledError, DBOSWorkflowCancelledError)):
        return "WARNING", "cancelled"
    return "ERROR", type(exc).__name__


@contextmanager
def _observe(name: str, *, as_type: str = "span", **kwargs: Any) -> Iterator[Any]:
    """Current observation, or None when tracing is off or the SDK cannot open one. An exception from the body is
    caught inside the SDK block and re-raised after it: OpenTelemetry would otherwise record its message on the span."""
    lf = _client  # read once: a concurrent shutdown() cannot set it to None between the check and the call
    stack = ExitStack()
    obs = None
    if lf is not None:
        # Creating the observation parses trace_id (int(trace_id, 16)); entering it starts the OTel span and runs
        # the span processors. Telemetry never raises into business code: the body then runs untraced.
        try:
            obs = stack.enter_context(lf.start_as_current_observation(name=name, as_type=as_type, **kwargs))
        except Exception as exc:  # noqa: BLE001 - telemetry never raises into business code
            logger.warning("langfuse observation not opened", extra={"error_class": type(exc).__name__})
    if obs is None:
        yield None
        return
    error: BaseException | None = None
    try:
        yield obs
    except BaseException as exc:  # noqa: BLE001 - re-raised after the SDK block, class name only
        error = exc
        level, message = _status(exc)
        metadata = None
        if as_type == "generation" and message == "cancelled":
            # no ledger row and no usage for a cancelled call; never send zeros (§11.5, §16.10.5 item 3)
            metadata = {"usage_missing": True, "usage_missing_reason": "cancelled"}
        with suppress(Exception):
            obs.update(level=level, status_message=message, metadata=metadata)
    finally:
        try:  # exits the SDK block with no exception, so OpenTelemetry records no message
            stack.close()
        except Exception as exc:  # noqa: BLE001 - telemetry never raises into business code
            logger.warning("langfuse observation not closed", extra={"error_class": type(exc).__name__})
    if error is not None:
        raise error


def _propagate(stack: ExitStack, **attributes: Any) -> None:
    """Enter propagate_attributes (never as baggage) on `stack`. If that fails, the spans still record, unpropagated."""
    from langfuse import propagate_attributes

    try:
        stack.enter_context(propagate_attributes(as_baggage=False, **attributes))
    except Exception as exc:  # noqa: BLE001 - telemetry never raises into business code
        logger.warning("langfuse attributes not propagated", extra={"error_class": type(exc).__name__})


def annotate(obs: Any, **metadata: Any) -> None:
    """Add metadata to a span from business code. No-op when `obs` is None (tracing off); never raises."""
    if obs is not None:
        with suppress(Exception):
            obs.update(metadata=metadata)


@contextmanager
def run_root(*, trace_id: str, user_id: str | None, workflow_name: str) -> Iterator[Any]:
    """API side (§16.10.3): the `blog.run` span on the run's trace id. Yields the span, or None when off."""
    if _client is None:
        yield None
        return
    with ExitStack() as stack:
        _propagate(stack, user_id=user_id, trace_name="blog.run", tags=["service:blog", f"workflow:{workflow_name}"])
        with _observe("blog.run", trace_context={"trace_id": trace_id}) as obs:
            yield obs


@contextmanager
def stage_span(
    *,
    trace_id: str,
    step_name: str,
    run_id: str,
    user_id: str | None,
    workflow_name: str,
    workflow_id: str | None,
    agent: str | None,
) -> Iterator[Any]:
    """Worker side (§16.10.4): one `stage.<step_name>` span per step execution. Yields the span, or None."""
    if _client is None:
        yield None
        return
    metadata = {"dbos_workflow_id": workflow_id, "workflow_name": workflow_name, "agent": agent}
    with ExitStack() as stack:
        _propagate(
            stack,
            user_id=user_id,
            session_id=f"blog-run:{run_id}",
            trace_name="blog.run",
            tags=["service:blog", f"workflow:{workflow_name}"],
            metadata={"run_id": run_id},
        )
        with _observe(
            f"stage.{step_name}",
            trace_context={"trace_id": trace_id},
            metadata={key: value for key, value in metadata.items() if value is not None},
        ) as obs:
            yield obs


@contextmanager
def generation(
    name: str,
    *,
    model: str,
    model_parameters: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """One generation per ledger row (§16.10.5, §16.10.6), current for its block. Yields it, or None when off."""
    with _observe(
        name,
        as_type="generation",
        model=model,
        model_parameters=model_parameters,
        metadata=metadata,
    ) as obs:
        yield obs


def update_generation(obs: Any, rec: CallRecord, *, ledger_row_id: uuid.UUID | None) -> None:
    """Fill a generation from the CallRecord the ledger just stored. No-op when `obs` is None; never raises.

    Cost is always the ledger's own total, $0 unpriced rows included, so Langfuse never infers a price the
    ledger did not charge (§16.10.5, §12.8 item 2).
    """
    if obs is None:
        return
    try:
        raw = rec.usage_raw
        usage, inconsistent = _usage(rec)
        meta: dict[str, object] = {
            "price_source": raw.get("pricing"),
            "price_version": rec.price_version,
            "ledger_row_id": None if ledger_row_id is None else str(ledger_row_id),
            "agent": rec.agent_name,
            "attempt_index": rec.attempt_index,
            "fallback_from": rec.fallback_from,
            "prompt_name": rec.prompt_name,
            "prompt_version": rec.prompt_version,
            "prompt_sha": rec.prompt_sha,
            "agent_run_id": None if rec.ctx.agent_run_id is None else str(rec.ctx.agent_run_id),
        }
        if rec.model_served and rec.model_served != rec.model_requested:
            meta["requested_model"] = rec.model_requested
        if rec.kind == CallKind.AGENT:
            meta["requests"] = len(_requests(rec))
        else:
            for key in ("search_actions", "sources", "citations"):
                meta[key] = raw.get(key)
        if usage is None:
            meta["usage_missing"] = True
            # §11.5 vocabulary: the call failed, or the provider sent no usage
            meta["usage_missing_reason"] = "error" if rec.status == CallStatus.ERROR else "provider_omitted"
        if inconsistent:
            meta["usage_inconsistent"] = True
        level = status_message = None
        if rec.status == CallStatus.ERROR:
            level, status_message = "ERROR", rec.error_class or "Error"
            meta["error_class"] = status_message
        obs.update(
            model=rec.model_served or rec.model_requested,
            usage_details=usage,
            cost_details={"total": float(rec.cost_usd)},
            metadata={key: value for key, value in meta.items() if value is not None},
            level=level,
            status_message=status_message,
        )
    except Exception as exc:  # noqa: BLE001 - the generation update never raises
        logger.warning("langfuse generation update failed", extra={"error_class": type(exc).__name__})


def _requests(rec: CallRecord) -> list[Mapping[str, object]]:
    """Per-request usage kept by `_sum_usage` in usage_raw["requests"] (agent rows only)."""
    requests = rec.usage_raw.get("requests")
    if not isinstance(requests, list):
        return []
    return [request for request in requests if isinstance(request, Mapping)]


def _count(value: object) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def _usage(rec: CallRecord) -> tuple[dict[str, int] | None, bool]:
    """§16.10.5 mapping into the §11.4 exclusive buckets, plus whether a bucket had to be clamped.

    None when the provider reported nothing (§11.5: never send zeros).
    """
    if rec.kind == CallKind.SEARCH:
        # OpenAI may return response.usage None; llm/search/openai.py:147-149 then stores 0 and 0
        if rec.status != CallStatus.OK or (rec.input_tokens == 0 and rec.output_tokens == 0):
            return None, False
        # OpenAI Responses totals include their detail counts (llm/search/openai.py:147-156)
        usage, inconsistent = _buckets(
            rec.input_tokens - rec.cache_read_tokens,
            rec.cache_read_tokens,
            0,
            rec.output_tokens - rec.reasoning_tokens,
            rec.reasoning_tokens,
        )
        if rec.search_actions > 0:
            usage["web_search_call"] = rec.search_actions
        return usage, inconsistent
    requests = _requests(rec)
    if not requests:
        return None, False
    cached = rec.cache_read_tokens + rec.cache_write_tokens if INPUT_INCLUDES_CACHE else 0
    reasoning = 0
    # Anthropic thinking tokens stay inside `output`: its price rows do not price output_reasoning (§11.4)
    if (rec.provider_served or rec.provider_requested) != "anthropic":
        for request in requests:
            details = request.get("details")
            if isinstance(details, Mapping):  # OpenAI: reasoning_tokens; Google: thoughts_tokens
                reasoning += _count(details.get("reasoning_tokens")) + _count(details.get("thoughts_tokens"))
    return _buckets(
        rec.input_tokens - cached,
        rec.cache_read_tokens,
        rec.cache_write_tokens,
        rec.output_tokens - reasoning,
        reasoning,
    )


def _buckets(
    input_tokens: int,
    cache_read: int,
    cache_write: int,
    output_tokens: int,
    reasoning: int,
) -> tuple[dict[str, int], bool]:
    """`input` and `output` always, clamped at 0 (§11.4 guard 1); the other buckets only when > 0."""
    usage = {"input": max(input_tokens, 0), "output": max(output_tokens, 0)}
    for key, value in (
        ("input_cache_read", cache_read),
        ("input_cache_creation", cache_write),
        ("output_reasoning", reasoning),
    ):
        if value > 0:
            usage[key] = value
    return usage, input_tokens < 0 or output_tokens < 0
