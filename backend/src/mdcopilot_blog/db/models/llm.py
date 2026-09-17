"""One row per LLM, search or embedding attempt, and the registered prompt versions."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, UUIDPk


class LlmCall(UUIDPk, CreatedAt, Base):
    """``attempt_id``, ``agent_run_id``, ``article_id`` and ``topic_candidate_id`` carry no FK yet.

    The recorder truncates ``error_message`` to 2000 characters before insert.
    """

    __tablename__ = "blog_llm_calls"
    __table_args__ = (
        Index("ix_blog_llm_calls_provider_model", "provider_requested", "model_requested"),
        Index("ix_blog_llm_calls_created_at", "created_at"),
    )

    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_runs.id", ondelete="SET NULL"), index=True)
    attempt_id: Mapped[uuid.UUID | None]
    agent_run_id: Mapped[uuid.UUID | None]
    article_id: Mapped[uuid.UUID | None]
    topic_candidate_id: Mapped[uuid.UUID | None]
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]
    kind: Mapped[str] = mapped_column(String(32))
    agent_name: Mapped[str | None] = mapped_column(String(64))
    prompt_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[int | None]
    prompt_sha: Mapped[str | None] = mapped_column(String(64))
    provider_requested: Mapped[str] = mapped_column(String(32))
    model_requested: Mapped[str] = mapped_column(String(128))
    provider_served: Mapped[str | None] = mapped_column(String(32))
    model_served: Mapped[str | None] = mapped_column(String(128))
    fallback_from: Mapped[str | None] = mapped_column(String(200))
    attempt_index: Mapped[int]
    params: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    input_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cache_read_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cache_write_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    reasoning_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    search_actions: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    latency_ms: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    error_class: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    usage_raw: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0), server_default=text("0"))
    price_version: Mapped[str] = mapped_column(String(64))
    trace_id: Mapped[str] = mapped_column(String(32))


class PromptVersion(UUIDPk, CreatedAt, Base):
    """Immutable registry row per (prompt name, version)."""

    __tablename__ = "blog_prompt_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_blog_prompt_versions_name_version"),)

    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[int]
    agent: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    front_matter: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
