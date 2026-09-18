"""Research ledger: discovery themes, feed and domain catalogue, research runs, sources and findings."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class DiscoveryTheme(UUIDPk, Timestamps, Base):
    """A saved search theme whose query templates expand into discovery queries."""

    __tablename__ = "blog_discovery_themes"

    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    query_templates: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    pillar_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    last_searched_at: Mapped[datetime | None]
    sort_order: Mapped[int] = mapped_column(default=0, server_default=text("0"))


class SourceFeed(UUIDPk, Timestamps, Base):
    """A configured feed (RSS, Atom, PubMed, Federal Register, FDA CSV) the retriever polls."""

    __tablename__ = "blog_source_feeds"
    __table_args__ = (CheckConstraint("tier BETWEEN 1 AND 3", name="tier"),)

    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    kind: Mapped[str] = mapped_column(String(32))
    group_name: Mapped[str] = mapped_column(String(64))
    tier: Mapped[int] = mapped_column(SmallInteger)
    source_type: Mapped[str] = mapped_column(String(32))
    pillar_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    theme_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    header_profile: Mapped[str] = mapped_column(String(32), default="default", server_default=text("'default'"))
    quirks: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    is_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    is_preprint: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    state: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    last_fetched_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    disabled_reason: Mapped[str | None] = mapped_column(String(200))
    item_count_last: Mapped[int] = mapped_column(default=0, server_default=text("0"))


class SourceDomain(UUIDPk, Timestamps, Base):
    """Per-domain policy: tier, fetch policy, publisher and verification allowlisting."""

    __tablename__ = "blog_source_domains"
    __table_args__ = (
        CheckConstraint("tier BETWEEN 1 AND 3", name="tier"),
        CheckConstraint("fetch_policy IN ('fetch','metadata_only','never')", name="fetch_policy"),
    )

    domain: Mapped[str] = mapped_column(String(253), unique=True)
    tier: Mapped[int] = mapped_column(SmallInteger)
    source_type: Mapped[str] = mapped_column(String(32))
    publisher: Mapped[str | None] = mapped_column(String(200))
    header_profile: Mapped[str] = mapped_column(String(32), default="default", server_default=text("'default'"))
    fetch_policy: Mapped[str] = mapped_column(String(32), default="fetch", server_default=text("'fetch'"))
    verification_allowlisted: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text)


class ResearchRun(UUIDPk, CreatedAt, Base):
    """One research execution for a run: queries, gathered signals, sources and phase timings."""

    __tablename__ = "blog_research_runs"
    __table_args__ = (
        Index("ix_blog_research_runs_created_at", "created_at"),
        Index(
            "uq_blog_research_runs_wf_step",
            "dbos_workflow_id",
            "dbos_step_id",
            unique=True,
            postgresql_where=text("dbos_workflow_id IS NOT NULL"),
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blog_articles.id", ondelete="SET NULL", use_alter=True)
    )
    kind: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32))
    pillar_key: Mapped[str | None] = mapped_column(String(16))
    window_days: Mapped[int]
    queries: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    themes_covered: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    signals: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    source_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    phase_latency_ms: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    counts: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    error: Mapped[dict[str, Any] | None]
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    trace_id: Mapped[str] = mapped_column(String(32))
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]


class LedgerSource(UUIDPk, Timestamps, Base):
    """One URL in the source ledger (the S1..Sn citation markers point at these rows)."""

    __tablename__ = "blog_sources"
    __table_args__ = (CheckConstraint("tier BETWEEN 1 AND 3", name="tier"),)

    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(253), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    tier: Mapped[int] = mapped_column(SmallInteger, index=True)
    published_at: Mapped[datetime | None] = mapped_column(index=True)
    date_source: Mapped[str] = mapped_column(String(16))
    retrieved_at: Mapped[datetime]
    access_mode: Mapped[str] = mapped_column(String(16))
    fetch_status: Mapped[str] = mapped_column(String(32))
    http_status: Mapped[int | None]
    content_hash: Mapped[str | None] = mapped_column(String(64))
    word_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    text_snapshot: Mapped[str | None] = mapped_column(Text)
    is_preprint: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    external_ids: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    discovered_via: Mapped[str] = mapped_column(String(32))
    first_research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blog_research_runs.id", ondelete="SET NULL")
    )
    relevance_score: Mapped[float] = mapped_column(default=0, server_default=text("0"))
    snapshot_purged_at: Mapped[datetime | None]


class ResearchFindingRecord(UUIDPk, CreatedAt, Base):
    """One extracted claim with its evidence, scored and categorised by the research analyst."""

    __tablename__ = "blog_research_findings"
    __table_args__ = (
        Index("uq_blog_research_findings_research_run_id_position", "research_run_id", "position", unique=True),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
    )

    research_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blog_research_runs.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    claim: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float]
    category: Mapped[str] = mapped_column(String(64))
    claim_type: Mapped[str] = mapped_column(String(32))
    importance: Mapped[str] = mapped_column(String(16))
    is_preprint: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    downgraded_from: Mapped[str | None] = mapped_column(String(32))


class FindingSource(Base):
    """Many-to-many link between findings and the ledger sources that support them."""

    __tablename__ = "blog_finding_sources"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blog_research_findings.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blog_sources.id", ondelete="CASCADE"), primary_key=True, index=True
    )
