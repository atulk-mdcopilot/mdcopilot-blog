"""Topic candidates, selected topics and external posts."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk

VECTOR_DIMENSIONS = 1536


class TopicCandidateRecord(UUIDPk, Timestamps, Base):
    """One ideation candidate per (run, round, position)."""

    __tablename__ = "blog_topic_candidates"
    __table_args__ = (
        Index(
            "uq_blog_topic_candidates_wf_step_position",
            "dbos_workflow_id",
            "dbos_step_id",
            "position",
            unique=True,
            postgresql_where=text("dbos_workflow_id IS NOT NULL"),
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="CASCADE"), index=True)
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_research_runs.id", ondelete="SET NULL"))
    round: Mapped[int]
    position: Mapped[int]
    title: Mapped[str] = mapped_column(String(300))
    hook: Mapped[str] = mapped_column(Text)
    why_now: Mapped[str] = mapped_column(Text)
    thesis: Mapped[str] = mapped_column(Text)
    angle: Mapped[str] = mapped_column(Text)
    core_argument: Mapped[str] = mapped_column(Text)
    mdcopilot_connection: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    pillar_key: Mapped[str] = mapped_column(String(16))
    relevant_news: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    source_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    primary_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_sources.id", ondelete="SET NULL"))
    examples: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    rubric: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    novelty_score: Mapped[float | None]
    evidence_score: Mapped[float | None]
    business_relevance: Mapped[float | None]
    editorial_potential: Mapped[float | None]
    timeliness_score: Mapped[float | None]
    audience_relevance: Mapped[float | None]
    total_score: Mapped[float | None]
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    novelty: Mapped[dict[str, Any] | None]
    novelty_decision: Mapped[str | None] = mapped_column(String(16))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(VECTOR_DIMENSIONS))
    argument_embedding: Mapped[list[float] | None] = mapped_column(Vector(VECTOR_DIMENSIONS))
    status: Mapped[str] = mapped_column(String(16), default="PROPOSED", server_default=text("'PROPOSED'"), index=True)
    is_manual: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    edited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    edited_at: Mapped[datetime | None]
    selected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    selected_at: Mapped[datetime | None]
    rejected_reason: Mapped[str | None] = mapped_column(Text)
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]


class Topic(UUIDPk, CreatedAt, Base):
    """A selected topic that an article is written from."""

    __tablename__ = "blog_topics"
    __table_args__ = (Index("ix_blog_topics_created_at", "created_at"),)

    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blog_topic_candidates.id", ondelete="SET NULL"), unique=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_runs.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300))
    pillar_key: Mapped[str] = mapped_column(String(16))
    thesis: Mapped[str] = mapped_column(Text)
    angle: Mapped[str] = mapped_column(Text)
    core_argument: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    examples: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    headline_pattern: Mapped[str] = mapped_column(String(32))
    primary_source_url: Mapped[str | None] = mapped_column(Text)
    source_domains: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIMENSIONS))
    argument_embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIMENSIONS))


class ExternalPost(UUIDPk, Timestamps, Base):
    """A post on the owner's public site, synced for topic-deduplication checks."""

    __tablename__ = "blog_external_posts"
    __table_args__ = (Index("uq_blog_external_posts_origin_slug", "origin", "slug", unique=True),)

    origin: Mapped[str] = mapped_column(String(200))
    external_id: Mapped[str | None] = mapped_column(String(64))
    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    excerpt: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None]
    headline_pattern: Mapped[str] = mapped_column(String(32))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(VECTOR_DIMENSIONS))
    content_hash: Mapped[str] = mapped_column(String(64))
    last_synced_at: Mapped[datetime]
