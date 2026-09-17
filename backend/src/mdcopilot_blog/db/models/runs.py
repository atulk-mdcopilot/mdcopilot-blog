"""User-visible runs, one row per DBOS execution (attempt), and one row per step execution."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class BlogRun(UUIDPk, Timestamps, Base):
    __tablename__ = "blog_runs"
    __table_args__ = (
        Index("ix_blog_runs_created_at", "created_at"),
        # at most one scheduled (daily) run per local date; manual runs are unrestricted
        Index("uq_blog_runs_daily_date", "run_date", unique=True, postgresql_where=text("kind = 'daily'")),
    )

    kind: Mapped[str] = mapped_column(String(32))
    run_date: Mapped[date] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str | None] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    trace_id: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0), server_default=text("0"))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error: Mapped[dict[str, Any] | None]


class RunAttempt(UUIDPk, CreatedAt, Base):
    __tablename__ = "blog_run_attempts"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="CASCADE"), index=True)
    dbos_workflow_id: Mapped[str] = mapped_column(String(128), unique=True)
    workflow_name: Mapped[str] = mapped_column(String(128))
    attempt_no: Mapped[int]
    forked_from_workflow_id: Mapped[str | None] = mapped_column(String(128))
    start_step: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error: Mapped[dict[str, Any] | None]


class AgentRun(UUIDPk, CreatedAt, Base):
    """One row per DBOS step execution; a re-executed step increments ``tries``."""

    __tablename__ = "blog_agent_runs"
    __table_args__ = (
        UniqueConstraint("dbos_workflow_id", "dbos_step_id", name="uq_blog_agent_runs_wf_step"),
        Index("ix_blog_agent_runs_created_at", "created_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_run_attempts.id", ondelete="CASCADE"))
    dbos_workflow_id: Mapped[str] = mapped_column(String(128))
    dbos_step_id: Mapped[int]
    step_name: Mapped[str] = mapped_column(String(128))
    agent_name: Mapped[str | None] = mapped_column(String(64))
    agent_version: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(32), index=True)
    tries: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None]
    input_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0), server_default=text("0"))
    sources_used: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    error: Mapped[dict[str, Any] | None]
    trace_id: Mapped[str] = mapped_column(String(32))
