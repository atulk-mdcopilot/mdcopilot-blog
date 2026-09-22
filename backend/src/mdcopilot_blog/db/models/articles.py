"""Articles, research packets, versions and the version child tables."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class Article(UUIDPk, Timestamps, Base):
    """One article produced for a run."""

    __tablename__ = "blog_articles"
    __table_args__ = (
        Index("ix_blog_articles_created_at", "created_at"),
        Index(
            "uq_blog_articles_slug",
            "slug",
            unique=True,
            postgresql_where=text("slug IS NOT NULL"),
        ),
        Index("uq_blog_articles_run_id_candidate_id", "run_id", "candidate_id", unique=True),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="RESTRICT"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_topic_candidates.id", ondelete="RESTRICT"))
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_topics.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    slug: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    pillar_key: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blog_article_versions.id", ondelete="SET NULL", use_alter=True)
    )
    # mdcopilot-backend blogs.id once the draft has been saved there (no FK: another service owns that table)
    backend_blog_id: Mapped[str | None] = mapped_column(String(64))
    # {"gatesPassed": bool, "gateProblems": [str]} as reported when the draft was saved
    draft_report: Mapped[dict[str, Any] | None]


class ResearchPacketRecord(UUIDPk, CreatedAt, Base):
    """One research packet version per article."""

    __tablename__ = "blog_research_packets"
    __table_args__ = (
        Index("uq_blog_research_packets_article_id_version", "article_id", "version", unique=True),
        Index(
            "uq_blog_research_packets_wf_step",
            "dbos_workflow_id",
            "dbos_step_id",
            unique=True,
            postgresql_where=text("dbos_workflow_id IS NOT NULL"),
        ),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_articles.id", ondelete="CASCADE"))
    version: Mapped[int]
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_research_runs.id", ondelete="SET NULL"))
    packet: Mapped[dict[str, Any]]
    summary: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]


class ArticleVersion(UUIDPk, CreatedAt, Base):
    """One immutable version of an article's content."""

    __tablename__ = "blog_article_versions"
    __table_args__ = (
        Index("uq_blog_article_versions_article_id_version_no", "article_id", "version_no", unique=True),
        Index(
            "uq_blog_article_versions_wf_step",
            "dbos_workflow_id",
            "dbos_step_id",
            unique=True,
            postgresql_where=text("dbos_workflow_id IS NOT NULL"),
        ),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_articles.id", ondelete="CASCADE"))
    version_no: Mapped[int]
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_article_versions.id"))
    change_kind: Mapped[str] = mapped_column(String(32))
    change_scope: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    title_options: Mapped[dict[str, Any]]
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    pull_quote: Mapped[str] = mapped_column(Text)
    cta: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    content_markdown: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int]
    citation_markers: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    resolutions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    research_packet_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_research_packets.id"))
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]


class VersionSeo(UUIDPk, CreatedAt, Base):
    """Insert-only SEO metadata for a version; the newest row per version is effective."""

    __tablename__ = "blog_version_seo"
    __table_args__ = (
        Index(
            "uq_blog_version_seo_wf_step",
            "dbos_workflow_id",
            "dbos_step_id",
            unique=True,
            postgresql_where=text("dbos_workflow_id IS NOT NULL"),
        ),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blog_article_versions.id", ondelete="CASCADE"), index=True
    )
    seo: Mapped[dict[str, Any]]
    social: Mapped[dict[str, Any] | None]
    slug: Mapped[str] = mapped_column(String(200))
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]


class ArticleSource(UUIDPk, CreatedAt, Base):
    """Insert-only link between a version and the ledger sources it cites."""

    __tablename__ = "blog_article_sources"
    __table_args__ = (
        Index("uq_blog_article_sources_version_id_marker", "version_id", "marker", unique=True),
        Index("uq_blog_article_sources_version_id_source_id", "version_id", "source_id", unique=True),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_article_versions.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_sources.id", ondelete="RESTRICT"), index=True)
    marker: Mapped[str] = mapped_column(String(8))
    is_primary: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
