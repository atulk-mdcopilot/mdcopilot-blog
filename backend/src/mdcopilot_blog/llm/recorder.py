"""Writes one ``blog_llm_calls`` row per model/search/embedding attempt, in its own transaction."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import LlmCall
from mdcopilot_blog.domain.enums import CallKind, CallStatus

if TYPE_CHECKING:
    from mdcopilot_blog.llm.gateway import CallContext

ERROR_MESSAGE_LIMIT = 2000
PRICE_VERSION = "genai-prices==0.1.7"


@dataclass(frozen=True)
class CallRecord:
    kind: CallKind
    ctx: CallContext
    provider_requested: str
    model_requested: str
    attempt_index: int
    status: CallStatus
    latency_ms: int
    agent_name: str | None = None
    prompt_name: str | None = None
    prompt_version: int | None = None
    prompt_sha: str | None = None
    provider_served: str | None = None
    model_served: str | None = None
    fallback_from: str | None = None
    params: Mapping[str, object] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    search_actions: int = 0
    cost_usd: Decimal = Decimal(0)
    price_version: str = PRICE_VERSION
    usage_raw: Mapping[str, object] = field(default_factory=dict)
    error_class: str | None = None
    error_message: str | None = None


class CallRecorder:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def record(self, rec: CallRecord) -> uuid.UUID:
        """Insert one row and commit immediately (own session), so failed runs keep their rows."""
        ctx = rec.ctx
        row = LlmCall(
            run_id=ctx.run_id,
            attempt_id=ctx.attempt_id,
            agent_run_id=ctx.agent_run_id,
            article_id=ctx.article_id,
            topic_candidate_id=ctx.topic_candidate_id,
            dbos_workflow_id=ctx.dbos_workflow_id,
            dbos_step_id=ctx.dbos_step_id,
            kind=rec.kind.value,
            agent_name=rec.agent_name,
            prompt_name=rec.prompt_name,
            prompt_version=rec.prompt_version,
            prompt_sha=rec.prompt_sha,
            provider_requested=rec.provider_requested,
            model_requested=rec.model_requested,
            provider_served=rec.provider_served,
            model_served=rec.model_served,
            fallback_from=rec.fallback_from,
            attempt_index=rec.attempt_index,
            params=dict(rec.params),
            input_tokens=rec.input_tokens,
            output_tokens=rec.output_tokens,
            cache_read_tokens=rec.cache_read_tokens,
            cache_write_tokens=rec.cache_write_tokens,
            reasoning_tokens=rec.reasoning_tokens,
            search_actions=rec.search_actions,
            latency_ms=rec.latency_ms,
            status=rec.status.value,
            error_class=rec.error_class,
            error_message=None if rec.error_message is None else rec.error_message[:ERROR_MESSAGE_LIMIT],
            usage_raw=dict(rec.usage_raw),
            cost_usd=rec.cost_usd,
            price_version=rec.price_version,
            trace_id=ctx.trace_id,
        )
        async with self._sessionmaker() as session:
            session.add(row)
            await session.commit()
        return row.id

    async def run_cost(self, run_id: uuid.UUID | None) -> Decimal:
        """Total recorded cost for a run; 0 when ``run_id`` is None."""
        if run_id is None:
            return Decimal(0)
        async with self._sessionmaker() as session:
            total = await session.scalar(
                select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(LlmCall.run_id == run_id)
            )
        return Decimal(str(total))
