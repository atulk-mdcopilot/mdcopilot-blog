"""domain tables: research, topics, articles, reviews, publications, calendar, pricing

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18 00:00:00

Rewritten in place 2026-09-22 for the shared mdcopilot-backend database: schema public (was "app"), the four
unprefixed tables renamed users -> blog_users, user_sessions -> blog_user_sessions, login_attempts ->
blog_login_attempts, audit_log -> blog_audit_log (constraint and index names follow), history tracked in
blog_alembic_versions. Columns, types, keys, indexes, defaults and the revision chain are otherwise unchanged.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands hand-written in CONTRACT §3.3 order (autogenerate would inline the deferred FKs) ###
    op.create_table(
        "blog_discovery_themes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "query_templates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "pillar_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_searched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_discovery_themes")),
        sa.UniqueConstraint("key", name=op.f("uq_blog_discovery_themes_key")),
    )
    op.create_table(
        "blog_calendar_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("pillar_key", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'planned'"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('planned','cancelled')", name=op.f("ck_blog_calendar_slots_status")),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_calendar_slots_created_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pillar_key"],
            ["blog_content_pillars.key"],
            name=op.f("fk_blog_calendar_slots_pillar_key_blog_content_pillars"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_calendar_slots")),
        sa.UniqueConstraint("slot_date", name=op.f("uq_blog_calendar_slots_slot_date")),
    )
    op.create_table(
        "blog_source_feeds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("group_name", sa.String(length=64), nullable=False),
        sa.Column("tier", sa.SmallInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column(
            "pillar_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "theme_keys", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("header_profile", sa.String(length=32), server_default=sa.text("'default'"), nullable=False),
        sa.Column(
            "quirks", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_preprint", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "state", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("disabled_reason", sa.String(length=200), nullable=True),
        sa.Column("item_count_last", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tier BETWEEN 1 AND 3", name=op.f("ck_blog_source_feeds_tier")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_source_feeds")),
        sa.UniqueConstraint("url", name=op.f("uq_blog_source_feeds_url")),
    )
    op.create_table(
        "blog_source_domains",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("tier", sa.SmallInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("header_profile", sa.String(length=32), server_default=sa.text("'default'"), nullable=False),
        sa.Column("fetch_policy", sa.String(length=32), server_default=sa.text("'fetch'"), nullable=False),
        sa.Column("verification_allowlisted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tier BETWEEN 1 AND 3", name=op.f("ck_blog_source_domains_tier")),
        sa.CheckConstraint(
            "fetch_policy IN ('fetch','metadata_only','never')", name=op.f("ck_blog_source_domains_fetch_policy")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_source_domains")),
        sa.UniqueConstraint("domain", name=op.f("uq_blog_source_domains_domain")),
    )
    op.create_table(
        "blog_research_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pillar_key", sa.String(length=16), nullable=True),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column(
            "queries", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "themes_covered",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "signals", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "source_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "phase_latency_ms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "counts", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("dbos_step_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["blog_runs.id"], name=op.f("fk_blog_research_runs_run_id_blog_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_research_runs")),
    )
    op.create_index(op.f("ix_blog_research_runs_run_id"), "blog_research_runs", ["run_id"], unique=False)
    op.create_index(op.f("ix_blog_research_runs_kind"), "blog_research_runs", ["kind"], unique=False)
    op.create_index("ix_blog_research_runs_created_at", "blog_research_runs", ["created_at"], unique=False)
    op.create_index(
        "uq_blog_research_runs_wf_step",
        "blog_research_runs",
        ["dbos_workflow_id", "dbos_step_id"],
        unique=True,
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.create_table(
        "blog_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.SmallInteger(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_source", sa.String(length=16), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_mode", sa.String(length=16), nullable=False),
        sa.Column("fetch_status", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("word_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("text_snapshot", sa.Text(), nullable=True),
        sa.Column("is_preprint", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "external_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("discovered_via", sa.String(length=32), nullable=False),
        sa.Column("first_research_run_id", sa.Uuid(), nullable=True),
        sa.Column("relevance_score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("snapshot_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tier BETWEEN 1 AND 3", name=op.f("ck_blog_sources_tier")),
        sa.ForeignKeyConstraint(
            ["first_research_run_id"],
            ["blog_research_runs.id"],
            name=op.f("fk_blog_sources_first_research_run_id_blog_research_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_sources")),
        sa.UniqueConstraint("url_hash", name=op.f("uq_blog_sources_url_hash")),
    )
    op.create_index(op.f("ix_blog_sources_domain"), "blog_sources", ["domain"], unique=False)
    op.create_index(op.f("ix_blog_sources_published_at"), "blog_sources", ["published_at"], unique=False)
    op.create_index(op.f("ix_blog_sources_tier"), "blog_sources", ["tier"], unique=False)
    op.create_table(
        "blog_research_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("claim_type", sa.String(length=32), nullable=False),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("is_preprint", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("downgraded_from", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_blog_research_findings_confidence")),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["blog_research_runs.id"],
            name=op.f("fk_blog_research_findings_research_run_id_blog_research_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_research_findings")),
    )
    op.create_index(
        op.f("ix_blog_research_findings_research_run_id"),
        "blog_research_findings",
        ["research_run_id"],
        unique=False,
    )
    op.create_index(
        "uq_blog_research_findings_research_run_id_position",
        "blog_research_findings",
        ["research_run_id", "position"],
        unique=True,
    )
    op.create_table(
        "blog_finding_sources",
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["blog_research_findings.id"],
            name=op.f("fk_blog_finding_sources_finding_id_blog_research_findings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["blog_sources.id"],
            name=op.f("fk_blog_finding_sources_source_id_blog_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("finding_id", "source_id", name=op.f("pk_blog_finding_sources")),
    )
    op.create_index(op.f("ix_blog_finding_sources_source_id"), "blog_finding_sources", ["source_id"], unique=False)
    op.create_table(
        "blog_topic_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=True),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text(), nullable=False),
        sa.Column("core_argument", sa.Text(), nullable=False),
        sa.Column("mdcopilot_connection", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("pillar_key", sa.String(length=16), nullable=False),
        sa.Column(
            "relevant_news",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("primary_source_id", sa.Uuid(), nullable=True),
        sa.Column(
            "examples", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "rubric", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("novelty_score", sa.Float(), nullable=True),
        sa.Column("evidence_score", sa.Float(), nullable=True),
        sa.Column("business_relevance", sa.Float(), nullable=True),
        sa.Column("editorial_potential", sa.Float(), nullable=True),
        sa.Column("timeliness_score", sa.Float(), nullable=True),
        sa.Column("audience_relevance", sa.Float(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column(
            "score_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("novelty", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("novelty_decision", sa.String(length=16), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("argument_embedding", Vector(1536), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'PROPOSED'"), nullable=False),
        sa.Column("is_manual", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("edited_by", sa.Uuid(), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selected_by", sa.Uuid(), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("dbos_step_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["edited_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_topic_candidates_edited_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_source_id"],
            ["blog_sources.id"],
            name=op.f("fk_blog_topic_candidates_primary_source_id_blog_sources"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["blog_research_runs.id"],
            name=op.f("fk_blog_topic_candidates_research_run_id_blog_research_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["blog_runs.id"], name=op.f("fk_blog_topic_candidates_run_id_blog_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["selected_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_topic_candidates_selected_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_topic_candidates")),
    )
    op.create_index(op.f("ix_blog_topic_candidates_run_id"), "blog_topic_candidates", ["run_id"], unique=False)
    op.create_index(op.f("ix_blog_topic_candidates_status"), "blog_topic_candidates", ["status"], unique=False)
    op.create_index(
        "uq_blog_topic_candidates_wf_step_position",
        "blog_topic_candidates",
        ["dbos_workflow_id", "dbos_step_id", "position"],
        unique=True,
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.create_table(
        "blog_topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("pillar_key", sa.String(length=16), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text(), nullable=False),
        sa.Column("core_argument", sa.Text(), nullable=False),
        sa.Column(
            "keywords", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "examples", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("headline_pattern", sa.String(length=32), nullable=False),
        sa.Column("primary_source_url", sa.Text(), nullable=True),
        sa.Column(
            "source_domains",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("argument_embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["blog_topic_candidates.id"],
            name=op.f("fk_blog_topics_candidate_id_blog_topic_candidates"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["blog_runs.id"], name=op.f("fk_blog_topics_run_id_blog_runs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_topics")),
        sa.UniqueConstraint("candidate_id", name=op.f("uq_blog_topics_candidate_id")),
    )
    op.create_index("ix_blog_topics_created_at", "blog_topics", ["created_at"], unique=False)
    op.create_table(
        "blog_external_posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.String(length=200), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=True),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("excerpt", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("headline_pattern", sa.String(length=32), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_external_posts")),
    )
    op.create_index("uq_blog_external_posts_origin_slug", "blog_external_posts", ["origin", "slug"], unique=True)
    op.create_table(
        "blog_articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("selected_title_key", sa.String(length=16), nullable=True),
        sa.Column("pillar_key", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column(
            "tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("approved_version_id", sa.Uuid(), nullable=True),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_mode", sa.String(length=16), nullable=True),
        sa.Column("approval_override_reason", sa.Text(), nullable=True),
        sa.Column("rejected_by", sa.Uuid(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_url", sa.Text(), nullable=True),
        sa.Column("superseded_by_article_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_articles_approved_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["blog_topic_candidates.id"],
            name=op.f("fk_blog_articles_candidate_id_blog_topic_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_articles_rejected_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["blog_runs.id"], name=op.f("fk_blog_articles_run_id_blog_runs"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scheduled_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_articles_scheduled_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_article_id"],
            ["blog_articles.id"],
            name=op.f("fk_blog_articles_superseded_by_article_id_blog_articles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["blog_topics.id"],
            name=op.f("fk_blog_articles_topic_id_blog_topics"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_articles")),
    )
    op.create_index(op.f("ix_blog_articles_status"), "blog_articles", ["status"], unique=False)
    op.create_index("ix_blog_articles_created_at", "blog_articles", ["created_at"], unique=False)
    op.create_index(op.f("ix_blog_articles_topic_id"), "blog_articles", ["topic_id"], unique=False)
    op.create_index(op.f("ix_blog_articles_published_at"), "blog_articles", ["published_at"], unique=False)
    op.create_index(op.f("ix_blog_articles_scheduled_for"), "blog_articles", ["scheduled_for"], unique=False)
    op.create_index(op.f("ix_blog_articles_run_id"), "blog_articles", ["run_id"], unique=False)
    op.create_index(op.f("ix_blog_articles_run_date"), "blog_articles", ["run_date"], unique=False)
    op.create_index(
        "uq_blog_articles_slug",
        "blog_articles",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL AND status NOT IN ('REJECTED','SUPERSEDED')"),
    )
    op.create_index(
        "uq_blog_articles_run_id_candidate_id",
        "blog_articles",
        ["run_id", "candidate_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('REJECTED','SUPERSEDED')"),
    )
    op.create_table(
        "blog_research_packets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("research_run_id", sa.Uuid(), nullable=True),
        sa.Column("packet", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "source_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("dbos_step_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["blog_articles.id"],
            name=op.f("fk_blog_research_packets_article_id_blog_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_research_packets_created_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["blog_research_runs.id"],
            name=op.f("fk_blog_research_packets_research_run_id_blog_research_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_research_packets")),
    )
    op.create_index(
        "uq_blog_research_packets_article_id_version",
        "blog_research_packets",
        ["article_id", "version"],
        unique=True,
    )
    op.create_index(
        "uq_blog_research_packets_wf_step",
        "blog_research_packets",
        ["dbos_workflow_id", "dbos_step_id"],
        unique=True,
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.create_table(
        "blog_article_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("change_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "change_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("title_options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pull_quote", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column(
            "citation_markers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "resolutions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("research_packet_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_by_kind", sa.String(length=16), nullable=False),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("dbos_step_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["blog_articles.id"],
            name=op.f("fk_blog_article_versions_article_id_blog_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["blog_users.id"], name=op.f("fk_blog_article_versions_created_by_blog_users")
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_article_versions_parent_version_id_blog_article_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["research_packet_id"],
            ["blog_research_packets.id"],
            name=op.f("fk_blog_article_versions_research_packet_id_blog_research_packets"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_article_versions")),
    )
    op.create_index(
        "uq_blog_article_versions_article_id_version_no",
        "blog_article_versions",
        ["article_id", "version_no"],
        unique=True,
    )
    op.create_index(
        "uq_blog_article_versions_wf_step",
        "blog_article_versions",
        ["dbos_workflow_id", "dbos_step_id"],
        unique=True,
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.create_table(
        "blog_version_seo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("seo", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("social", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("dbos_step_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_version_seo_created_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_version_seo_version_id_blog_article_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_version_seo")),
    )
    op.create_index(op.f("ix_blog_version_seo_version_id"), "blog_version_seo", ["version_id"], unique=False)
    op.create_index(
        "uq_blog_version_seo_wf_step",
        "blog_version_seo",
        ["dbos_workflow_id", "dbos_step_id"],
        unique=True,
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.create_table(
        "blog_version_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_version_embeddings_version_id_blog_article_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_version_embeddings")),
    )
    op.create_index(
        "uq_blog_version_embeddings_version_id_kind",
        "blog_version_embeddings",
        ["version_id", "kind"],
        unique=True,
    )
    op.create_table(
        "blog_version_features",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("opening_sentence", sa.Text(), nullable=False),
        sa.Column("headline_pattern", sa.String(length=32), nullable=False),
        sa.Column(
            "industry_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "keywords", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("core_argument", sa.Text(), nullable=False),
        sa.Column(
            "examples", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "primary_source_domains",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("cta_normalized", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_version_features_version_id_blog_article_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_version_features")),
        sa.UniqueConstraint("version_id", name=op.f("uq_blog_version_features_version_id")),
    )
    op.create_table(
        "blog_article_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("marker", sa.String(length=8), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["blog_sources.id"],
            name=op.f("fk_blog_article_sources_source_id_blog_sources"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_article_sources_version_id_blog_article_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_article_sources")),
    )
    op.create_index(
        "uq_blog_article_sources_version_id_marker",
        "blog_article_sources",
        ["version_id", "marker"],
        unique=True,
    )
    op.create_index(
        "uq_blog_article_sources_version_id_source_id",
        "blog_article_sources",
        ["version_id", "source_id"],
        unique=True,
    )
    op.create_index(op.f("ix_blog_article_sources_source_id"), "blog_article_sources", ["source_id"], unique=False)
    op.create_table(
        "blog_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("independent_check", sa.Boolean(), nullable=True),
        sa.Column("writer_provider", sa.String(length=32), nullable=True),
        sa.Column("agent_provider", sa.String(length=32), nullable=True),
        sa.Column("agent_model", sa.String(length=128), nullable=True),
        sa.Column("gate_run_kind", sa.String(length=16), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("dbos_step_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["blog_articles.id"],
            name=op.f("fk_blog_reviews_article_id_blog_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["blog_users.id"], name=op.f("fk_blog_reviews_created_by_blog_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_reviews_version_id_blog_article_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_reviews")),
    )
    op.create_index("ix_blog_reviews_version_id_kind", "blog_reviews", ["version_id", "kind"], unique=False)
    op.create_index(op.f("ix_blog_reviews_article_id"), "blog_reviews", ["article_id"], unique=False)
    op.create_index("ix_blog_reviews_created_at", "blog_reviews", ["created_at"], unique=False)
    op.create_index(
        "uq_blog_reviews_wf_step_kind",
        "blog_reviews",
        ["dbos_workflow_id", "dbos_step_id", "kind"],
        unique=True,
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.create_table(
        "blog_claim_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("section_key", sa.String(length=64), nullable=False),
        sa.Column("sentence_index", sa.Integer(), nullable=False),
        sa.Column("span", sa.Text(), nullable=False),
        sa.Column(
            "citation_markers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("recommended_revision", sa.Text(), nullable=True),
        sa.Column(
            "verification_source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["blog_reviews.id"],
            name=op.f("fk_blog_claim_checks_review_id_blog_reviews"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["blog_sources.id"],
            name=op.f("fk_blog_claim_checks_source_id_blog_sources"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_claim_checks_version_id_blog_article_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_claim_checks")),
    )
    op.create_index(
        "uq_blog_claim_checks_review_id_position",
        "blog_claim_checks",
        ["review_id", "position"],
        unique=True,
    )
    op.create_index("ix_blog_claim_checks_version_id_kind", "blog_claim_checks", ["version_id", "kind"], unique=False)
    op.create_index(op.f("ix_blog_claim_checks_review_id"), "blog_claim_checks", ["review_id"], unique=False)
    op.create_table(
        "blog_publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("publisher", sa.String(length=32), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("external_post_id", sa.String(length=64), nullable=True),
        sa.Column("published_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("export_bundle", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("as_draft", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["blog_articles.id"],
            name=op.f("fk_blog_publications_article_id_blog_articles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_publications_confirmed_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_publications_requested_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["blog_article_versions.id"],
            name=op.f("fk_blog_publications_version_id_blog_article_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_publications")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_blog_publications_idempotency_key")),
    )
    op.create_index(
        "uq_blog_publications_article_id_publisher_target",
        "blog_publications",
        ["article_id", "publisher", "target"],
        unique=True,
    )
    op.create_index(op.f("ix_blog_publications_published_at"), "blog_publications", ["published_at"], unique=False)
    op.create_index(op.f("ix_blog_publications_status"), "blog_publications", ["status"], unique=False)
    op.create_table(
        "blog_price_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("input_per_mtok", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("output_per_mtok", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("cache_read_per_mtok", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("per_1k_calls", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_version", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "input_per_mtok IS NOT NULL OR output_per_mtok IS NOT NULL OR per_1k_calls IS NOT NULL",
            name=op.f("ck_blog_price_overrides_has_price"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["blog_users.id"],
            name=op.f("fk_blog_price_overrides_created_by_blog_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_price_overrides")),
    )
    op.create_index(
        "uq_blog_price_overrides_provider_sku_effective_from",
        "blog_price_overrides",
        ["provider", "sku", "effective_from"],
        unique=True,
    )
    # deferred FKs (CONTRACT §3.3)
    op.create_foreign_key(
        op.f("fk_blog_research_runs_article_id_blog_articles"),
        "blog_research_runs",
        "blog_articles",
        ["article_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_blog_articles_current_version_id_blog_article_versions"),
        "blog_articles",
        "blog_article_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_blog_articles_approved_version_id_blog_article_versions"),
        "blog_articles",
        "blog_article_versions",
        ["approved_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_blog_articles_published_version_id_blog_article_versions"),
        "blog_articles",
        "blog_article_versions",
        ["published_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # §3.2 changes to Phase 1 tables
    op.add_column("blog_notifications", sa.Column("dedupe_key", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_blog_notifications_user_id_dedupe_key",
        "blog_notifications",
        ["user_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    op.create_index("ix_blog_notifications_read_at", "blog_notifications", ["read_at"], unique=False)
    op.create_index("ix_blog_llm_calls_article_id", "blog_llm_calls", ["article_id"], unique=False)
    op.create_index("ix_blog_llm_calls_topic_candidate_id", "blog_llm_calls", ["topic_candidate_id"], unique=False)
    # immutable versions trigger (CONTRACT §3.1)
    op.execute(
        "CREATE FUNCTION blog_article_versions_block_update() RETURNS trigger LANGUAGE plpgsql AS $$\n"
        "BEGIN\n"
        "  RAISE EXCEPTION 'blog_article_versions rows are immutable' USING ERRCODE = 'restrict_violation';\n"
        "END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_blog_article_versions_block_update BEFORE UPDATE ON blog_article_versions\n"
        "  FOR EACH ROW EXECUTE FUNCTION blog_article_versions_block_update()"
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_blog_article_versions_block_update ON blog_article_versions")
    op.execute("DROP FUNCTION IF EXISTS blog_article_versions_block_update()")
    op.drop_constraint(
        op.f("fk_blog_articles_published_version_id_blog_article_versions"),
        "blog_articles",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_blog_articles_approved_version_id_blog_article_versions"),
        "blog_articles",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_blog_articles_current_version_id_blog_article_versions"),
        "blog_articles",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_blog_research_runs_article_id_blog_articles"),
        "blog_research_runs",
        type_="foreignkey",
    )
    op.drop_index("uq_blog_price_overrides_provider_sku_effective_from", table_name="blog_price_overrides")
    op.drop_table("blog_price_overrides")
    op.drop_index(op.f("ix_blog_publications_status"), table_name="blog_publications")
    op.drop_index(op.f("ix_blog_publications_published_at"), table_name="blog_publications")
    op.drop_index("uq_blog_publications_article_id_publisher_target", table_name="blog_publications")
    op.drop_table("blog_publications")
    op.drop_index(op.f("ix_blog_claim_checks_review_id"), table_name="blog_claim_checks")
    op.drop_index("ix_blog_claim_checks_version_id_kind", table_name="blog_claim_checks")
    op.drop_index("uq_blog_claim_checks_review_id_position", table_name="blog_claim_checks")
    op.drop_table("blog_claim_checks")
    op.drop_index(
        "uq_blog_reviews_wf_step_kind",
        table_name="blog_reviews",
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.drop_index("ix_blog_reviews_created_at", table_name="blog_reviews")
    op.drop_index(op.f("ix_blog_reviews_article_id"), table_name="blog_reviews")
    op.drop_index("ix_blog_reviews_version_id_kind", table_name="blog_reviews")
    op.drop_table("blog_reviews")
    op.drop_index(op.f("ix_blog_article_sources_source_id"), table_name="blog_article_sources")
    op.drop_index("uq_blog_article_sources_version_id_source_id", table_name="blog_article_sources")
    op.drop_index("uq_blog_article_sources_version_id_marker", table_name="blog_article_sources")
    op.drop_table("blog_article_sources")
    op.drop_table("blog_version_features")
    op.drop_index("uq_blog_version_embeddings_version_id_kind", table_name="blog_version_embeddings")
    op.drop_table("blog_version_embeddings")
    op.drop_index(
        "uq_blog_version_seo_wf_step",
        table_name="blog_version_seo",
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_blog_version_seo_version_id"), table_name="blog_version_seo")
    op.drop_table("blog_version_seo")
    op.drop_index(
        "uq_blog_article_versions_wf_step",
        table_name="blog_article_versions",
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.drop_index("uq_blog_article_versions_article_id_version_no", table_name="blog_article_versions")
    op.drop_table("blog_article_versions")
    op.drop_index(
        "uq_blog_research_packets_wf_step",
        table_name="blog_research_packets",
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.drop_index("uq_blog_research_packets_article_id_version", table_name="blog_research_packets")
    op.drop_table("blog_research_packets")
    op.drop_index(
        "uq_blog_articles_run_id_candidate_id",
        table_name="blog_articles",
        postgresql_where=sa.text("status NOT IN ('REJECTED','SUPERSEDED')"),
    )
    op.drop_index(
        "uq_blog_articles_slug",
        table_name="blog_articles",
        postgresql_where=sa.text("slug IS NOT NULL AND status NOT IN ('REJECTED','SUPERSEDED')"),
    )
    op.drop_index(op.f("ix_blog_articles_run_date"), table_name="blog_articles")
    op.drop_index(op.f("ix_blog_articles_run_id"), table_name="blog_articles")
    op.drop_index(op.f("ix_blog_articles_scheduled_for"), table_name="blog_articles")
    op.drop_index(op.f("ix_blog_articles_published_at"), table_name="blog_articles")
    op.drop_index(op.f("ix_blog_articles_topic_id"), table_name="blog_articles")
    op.drop_index("ix_blog_articles_created_at", table_name="blog_articles")
    op.drop_index(op.f("ix_blog_articles_status"), table_name="blog_articles")
    op.drop_table("blog_articles")
    op.drop_index("uq_blog_external_posts_origin_slug", table_name="blog_external_posts")
    op.drop_table("blog_external_posts")
    op.drop_index("ix_blog_topics_created_at", table_name="blog_topics")
    op.drop_table("blog_topics")
    op.drop_index(
        "uq_blog_topic_candidates_wf_step_position",
        table_name="blog_topic_candidates",
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_blog_topic_candidates_status"), table_name="blog_topic_candidates")
    op.drop_index(op.f("ix_blog_topic_candidates_run_id"), table_name="blog_topic_candidates")
    op.drop_table("blog_topic_candidates")
    op.drop_index(op.f("ix_blog_finding_sources_source_id"), table_name="blog_finding_sources")
    op.drop_table("blog_finding_sources")
    op.drop_index("uq_blog_research_findings_research_run_id_position", table_name="blog_research_findings")
    op.drop_index(op.f("ix_blog_research_findings_research_run_id"), table_name="blog_research_findings")
    op.drop_table("blog_research_findings")
    op.drop_index(op.f("ix_blog_sources_tier"), table_name="blog_sources")
    op.drop_index(op.f("ix_blog_sources_published_at"), table_name="blog_sources")
    op.drop_index(op.f("ix_blog_sources_domain"), table_name="blog_sources")
    op.drop_table("blog_sources")
    op.drop_index(
        "uq_blog_research_runs_wf_step",
        table_name="blog_research_runs",
        postgresql_where=sa.text("dbos_workflow_id IS NOT NULL"),
    )
    op.drop_index("ix_blog_research_runs_created_at", table_name="blog_research_runs")
    op.drop_index(op.f("ix_blog_research_runs_kind"), table_name="blog_research_runs")
    op.drop_index(op.f("ix_blog_research_runs_run_id"), table_name="blog_research_runs")
    op.drop_table("blog_research_runs")
    op.drop_table("blog_source_domains")
    op.drop_table("blog_source_feeds")
    op.drop_table("blog_calendar_slots")
    op.drop_table("blog_discovery_themes")
    op.drop_index("ix_blog_llm_calls_topic_candidate_id", table_name="blog_llm_calls")
    op.drop_index("ix_blog_llm_calls_article_id", table_name="blog_llm_calls")
    op.drop_index("ix_blog_notifications_read_at", table_name="blog_notifications")
    op.drop_index(
        "uq_blog_notifications_user_id_dedupe_key",
        table_name="blog_notifications",
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    op.drop_column("blog_notifications", "dedupe_key")
    # ### end Alembic commands ###
    # manual: the vector extension stays (created by 0001; IF NOT EXISTS makes re-upgrade safe).
