"""Topic candidates and selected topics."""

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class TopicCandidateRecord(UUIDPk, Timestamps, Base):
    """The manual topic of a run, as a writer brief."""

    __tablename__ = "blog_topic_candidates"
    __table_args__ = (
        Index(
            "uq_blog_topic_candidates_wf_step",
            "dbos_workflow_id",
            "dbos_step_id",
            unique=True,
            postgresql_where=text("dbos_workflow_id IS NOT NULL"),
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    hook: Mapped[str] = mapped_column(Text)
    why_now: Mapped[str] = mapped_column(Text)
    thesis: Mapped[str] = mapped_column(Text)
    angle: Mapped[str] = mapped_column(Text)
    core_argument: Mapped[str] = mapped_column(Text)
    mdcopilot_connection: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    pillar_key: Mapped[str] = mapped_column(String(16))
    examples: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    status: Mapped[str] = mapped_column(String(16), index=True)
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]


class Topic(UUIDPk, CreatedAt, Base):
    """A selected topic that an article is written from."""

    __tablename__ = "blog_topics"

    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blog_topic_candidates.id", ondelete="SET NULL"), unique=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_runs.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300))
    pillar_key: Mapped[str] = mapped_column(String(16))
    thesis: Mapped[str] = mapped_column(Text)
    angle: Mapped[str] = mapped_column(Text)
    core_argument: Mapped[str] = mapped_column(Text)
