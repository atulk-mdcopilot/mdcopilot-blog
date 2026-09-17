"""CallRecorder writes committed rows and sums run cost."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import BlogRun, LlmCall
from mdcopilot_blog.domain.enums import CallKind, CallStatus
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.llm.gateway import CallContext
from mdcopilot_blog.llm.recorder import CallRecord, CallRecorder


async def make_run(sessionmaker: async_sessionmaker[AsyncSession]) -> BlogRun:
    async with sessionmaker() as session:
        run = BlogRun(
            kind="manual",
            run_date=date(2026, 9, 17),
            status="QUEUED",
            params={},
            trace_id=new_trace_id(),
        )
        session.add(run)
        await session.commit()
    return run


def make_record(ctx: CallContext, *, cost: str, status: CallStatus = CallStatus.OK, **kw: Any) -> CallRecord:
    return CallRecord(
        kind=CallKind.AGENT,
        ctx=ctx,
        provider_requested="openai",
        model_requested="gpt-test",
        attempt_index=0,
        status=status,
        latency_ms=12,
        cost_usd=Decimal(cost),
        **kw,
    )


async def test_record_commits_row_with_context(
    sessionmaker_committing: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    run = await make_run(sessionmaker_committing)
    recorder = CallRecorder(sessionmaker_committing)
    ctx = CallContext(
        trace_id=run.trace_id,
        run_id=run.id,
        attempt_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        dbos_workflow_id="manual-wf",
        dbos_step_id=2,
    )

    row_id = await recorder.record(
        make_record(
            ctx,
            cost="0.012345",
            agent_name="writer",
            prompt_name="writer/draft",
            prompt_version=1,
            prompt_sha="a" * 64,
            provider_served="openai",
            model_served="gpt-test-2026-09-01",
            fallback_from="google:gemini-test",
            params={"max_tokens": 300},
            input_tokens=100,
            output_tokens=40,
            cache_read_tokens=10,
            reasoning_tokens=5,
            usage_raw={"requests": [{"input_tokens": 100}]},
        )
    )

    async with sessionmaker_committing() as session:  # a fresh session proves the commit
        row = await session.scalar(select(LlmCall).where(LlmCall.id == row_id))
    assert row is not None
    assert row.run_id == run.id
    assert row.attempt_id == ctx.attempt_id
    assert row.agent_run_id == ctx.agent_run_id
    assert row.dbos_workflow_id == "manual-wf"
    assert row.dbos_step_id == 2
    assert row.kind == "agent"
    assert row.status == "ok"
    assert row.agent_name == "writer"
    assert row.prompt_version == 1
    assert row.model_served == "gpt-test-2026-09-01"
    assert row.fallback_from == "google:gemini-test"
    assert row.params == {"max_tokens": 300}
    assert (row.input_tokens, row.output_tokens, row.cache_read_tokens, row.reasoning_tokens) == (100, 40, 10, 5)
    assert row.cost_usd == Decimal("0.012345")
    assert row.price_version == "genai-prices==0.1.7"
    assert row.usage_raw == {"requests": [{"input_tokens": 100}]}
    assert row.trace_id == run.trace_id
    assert row.latency_ms == 12


async def test_error_message_is_truncated(
    sessionmaker_committing: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    recorder = CallRecorder(sessionmaker_committing)
    row_id = await recorder.record(
        make_record(
            CallContext(trace_id=new_trace_id()),
            cost="0",
            status=CallStatus.ERROR,
            error_class="ModelHTTPError",
            error_message="x" * 5000,
        )
    )
    async with sessionmaker_committing() as session:
        row = await session.scalar(select(LlmCall).where(LlmCall.id == row_id))
    assert row is not None
    assert row.run_id is None
    assert row.status == "error"
    assert row.error_class == "ModelHTTPError"
    assert row.error_message == "x" * 2000


async def test_run_cost_sums_only_that_run(
    sessionmaker_committing: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    run = await make_run(sessionmaker_committing)
    other = await make_run(sessionmaker_committing)
    recorder = CallRecorder(sessionmaker_committing)
    ctx = CallContext(trace_id=run.trace_id, run_id=run.id)

    assert await recorder.run_cost(run.id) == Decimal(0)
    await recorder.record(make_record(ctx, cost="0.100000"))
    await recorder.record(make_record(ctx, cost="0.250000", status=CallStatus.ERROR))
    await recorder.record(make_record(CallContext(trace_id=other.trace_id, run_id=other.id), cost="9"))
    await recorder.record(make_record(CallContext(trace_id=new_trace_id()), cost="7"))

    assert await recorder.run_cost(run.id) == Decimal("0.35")
    assert await recorder.run_cost(other.id) == Decimal(9)
    assert await recorder.run_cost(None) == Decimal(0)
    assert await recorder.run_cost(uuid.uuid4()) == Decimal(0)
