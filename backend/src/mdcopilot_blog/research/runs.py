"""Research run bookkeeping: open/mark runs, error payloads, query counts."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import ResearchRun
from mdcopilot_blog.domain.enums import ResearchRunKind, ResearchRunStatus
from mdcopilot_blog.llm.gateway import CallContext


@dataclass(frozen=True)
class ResearchRunHandle:
    id: uuid.UUID
    existed: bool


def error_payload(exc: BaseException) -> dict[str, object]:
    return {"class": type(exc).__name__, "message": str(exc)[:2000]}


async def open_research_run(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    call: CallContext,
    run_id: uuid.UUID,
    kind: ResearchRunKind,
    pillar_key: str | None,
    window_days: int,
    article_id: uuid.UUID | None,
    now: datetime,
) -> ResearchRunHandle:
    values: dict[str, object] = {
        "run_id": run_id,
        "article_id": article_id,
        "kind": kind.value,
        "status": ResearchRunStatus.RUNNING.value,
        "pillar_key": pillar_key,
        "window_days": window_days,
        "queries": [],
        "themes_covered": [],
        "signals": [],
        "source_ids": [],
        "phase_latency_ms": {},
        "counts": {},
        "trace_id": call.trace_id,
        "started_at": now,
        "dbos_workflow_id": call.dbos_workflow_id,
        "dbos_step_id": call.dbos_step_id,
    }
    async with sessionmaker() as db:
        if call.dbos_workflow_id is not None:
            statement = (
                insert(ResearchRun)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["dbos_workflow_id", "dbos_step_id"],
                    index_where=text("dbos_workflow_id IS NOT NULL"),
                )
                .returning(ResearchRun.id)
            )
            result = await db.execute(statement)
            research_run_id = result.scalar_one_or_none()
            if research_run_id is None:
                research_run_id = await db.scalar(
                    select(ResearchRun.id).where(
                        ResearchRun.dbos_workflow_id == call.dbos_workflow_id,
                        ResearchRun.dbos_step_id == call.dbos_step_id,
                    )
                )
                await db.commit()
                if research_run_id is None:
                    raise LookupError("research run insert failed")
                return ResearchRunHandle(id=research_run_id, existed=True)
            await db.commit()
            return ResearchRunHandle(id=research_run_id, existed=False)
        statement = insert(ResearchRun).values(**values).returning(ResearchRun.id)
        result = await db.execute(statement)
        research_run_id = result.scalar_one()
        await db.commit()
        return ResearchRunHandle(id=research_run_id, existed=False)


async def get_research_run(db: AsyncSession, research_run_id: uuid.UUID, *, for_update: bool = False) -> ResearchRun:
    statement = select(ResearchRun).where(ResearchRun.id == research_run_id)
    if for_update:
        statement = statement.with_for_update()
    row = await db.scalar(statement)
    if row is None:
        raise LookupError(f"research run {research_run_id} not found")
    return row


async def mark_run(
    sessionmaker: async_sessionmaker[AsyncSession],
    research_run_id: uuid.UUID,
    *,
    status: ResearchRunStatus,
    error: dict[str, object] | None,
    now: datetime,
) -> None:
    async with sessionmaker() as db:
        await get_research_run(db, research_run_id, for_update=True)
        await db.execute(
            update(ResearchRun)
            .where(ResearchRun.id == research_run_id)
            .values(
                status=status.value,
                error=error,
                finished_at=now,
            )
        )
        await db.commit()


def query_status_counts(run: ResearchRun) -> tuple[int, int]:
    ok = 0
    failed = 0
    for query in run.queries or []:
        if query.get("status") == "ok":
            ok += 1
        elif query.get("status") == "failed":
            failed += 1
    return ok, failed


def merged(mapping: Mapping[str, int], **values: int) -> dict[str, int]:
    combined = {key: int(value) for key, value in dict(mapping or {}).items() if isinstance(value, int)}
    for key, value in values.items():
        combined[key] = value
    return combined
