"""Quality reviews and their per-claim fact checks."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, UUIDPk


class Review(UUIDPk, CreatedAt, Base):
    """Insert-only review of a version (fact check, clinical, editorial or quality gate)."""

    __tablename__ = "blog_reviews"
    __table_args__ = (
        Index("ix_blog_reviews_version_id_kind", "version_id", "kind"),
        Index("ix_blog_reviews_created_at", "created_at"),
        Index(
            "uq_blog_reviews_wf_step_kind",
            "dbos_workflow_id",
            "dbos_step_id",
            "kind",
            unique=True,
            postgresql_where=text("dbos_workflow_id IS NOT NULL"),
        ),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_articles.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_article_versions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    verdict: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]]
    score: Mapped[float | None]
    independent_check: Mapped[bool | None]
    writer_provider: Mapped[str | None] = mapped_column(String(32))
    agent_provider: Mapped[str | None] = mapped_column(String(32))
    agent_model: Mapped[str | None] = mapped_column(String(128))
    gate_run_kind: Mapped[str | None] = mapped_column(String(16))
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]


class ClaimCheckRecord(UUIDPk, CreatedAt, Base):
    """Insert-only per-claim verification result of a fact-check review."""

    __tablename__ = "blog_claim_checks"
    __table_args__ = (
        Index("uq_blog_claim_checks_review_id_position", "review_id", "position", unique=True),
        Index("ix_blog_claim_checks_version_id_kind", "version_id", "kind"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_reviews.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_article_versions.id", ondelete="CASCADE"))
    position: Mapped[int]
    claim: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    importance: Mapped[str] = mapped_column(String(16))
    section_key: Mapped[str] = mapped_column(String(64))
    sentence_index: Mapped[int]
    span: Mapped[str] = mapped_column(Text)
    citation_markers: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_sources.id", ondelete="SET NULL"))
    verification_status: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float]
    recommended_revision: Mapped[str | None] = mapped_column(Text)
    verification_source_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
