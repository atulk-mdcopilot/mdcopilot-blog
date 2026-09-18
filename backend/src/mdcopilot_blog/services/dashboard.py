"""Current generation progress and article counts for the dashboard."""

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.schemas_dashboard import (
    DashboardMetricsOut,
    DashboardOut,
    PipelineStageOut,
    PipelineTrackerOut,
    QualitySummaryOut,
    RecommendedTopicOut,
    TodayCardOut,
)
from mdcopilot_blog.db.models import (
    AgentRun,
    Article,
    ArticleVersion,
    BlogRun,
    ResearchRun,
    Review,
    RunAttempt,
    TopicCandidateRecord,
)
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import ArticleStatus, RunStatus
from mdcopilot_blog.services.article_views import build_article_detail, build_article_sources
from mdcopilot_blog.services.config import load_effective_config
from mdcopilot_blog.settings import Settings


async def _count(db: AsyncSession, model: Any, *criteria: Any) -> int:
    return int(await db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0)


async def dashboard(db: AsyncSession, settings: Settings, *, now: datetime | None = None) -> DashboardOut:
    now = now or datetime.now(UTC)
    config = await load_effective_config(db, settings)
    zone = ZoneInfo(config.schedule.timezone)
    today = now.astimezone(zone).date()
    midnight = datetime.combine(today, time.min, zone)
    window = midnight - timedelta(days=29)
    run = await db.scalar(
        select(BlogRun).where(BlogRun.run_date == today).order_by(BlogRun.created_at.desc(), BlogRun.id.desc()).limit(1)
    )
    card = TodayCardOut(
        date=today,
        run_id=run.id if run else None,
        run_status=RunStatus(run.status) if run else None,
        research_status="not_started",
        opportunities_discovered=0,
        recommended_topic=None,
        article_id=None,
        article_status=None,
        headline_options=None,
        quality=None,
    )
    stages = await pipeline_stages(db, run.id if run else None)
    if run:
        research = await db.scalar(
            select(ResearchRun)
            .where(ResearchRun.run_id == run.id, ResearchRun.kind == "broad")
            .order_by(ResearchRun.started_at.desc())
            .limit(1)
        )
        if research:
            card.research_status = (
                "running"
                if research.status == "running"
                else "failed"
                if research.status in {"failed", "insufficient_evidence"}
                else "done"
            )
        else:
            card.research_status = (
                "running"
                if run.status == "RESEARCHING"
                else "failed"
                if run.status == "FAILED"
                else "done"
                if run.status in {"TOPICS_READY", "WAITING_FOR_TOPIC", "PRODUCING", "SUCCEEDED"}
                else "not_started"
            )
        round_no = await db.scalar(
            select(func.max(TopicCandidateRecord.round)).where(TopicCandidateRecord.run_id == run.id)
        )
        candidates = list(
            await db.scalars(
                select(TopicCandidateRecord)
                .where(TopicCandidateRecord.run_id == run.id, TopicCandidateRecord.round == round_no)
                .order_by(TopicCandidateRecord.total_score.desc().nulls_last(), TopicCandidateRecord.position)
            )
        )
        viable = [c for c in candidates if c.status in {"PASSED", "WARNED"}]
        chosen = await db.scalar(
            select(TopicCandidateRecord)
            .where(TopicCandidateRecord.run_id == run.id, TopicCandidateRecord.status == "SELECTED")
            .order_by(TopicCandidateRecord.selected_at.desc().nulls_last(), TopicCandidateRecord.id.desc())
            .limit(1)
        )
        card.opportunities_discovered = sum(c.status != "REJECTED" for c in candidates)
        if chosen or viable:
            c = chosen or viable[0]
            card.recommended_topic = RecommendedTopicOut(
                candidate_id=c.id,
                title=c.title,
                why_now=c.why_now,
                pillar=PillarKey(c.pillar_key),
                evidence_score=c.evidence_score,
                business_relevance=c.business_relevance,
                novelty_score=c.novelty_score,
                total_score=c.total_score,
            )
        article = await db.scalar(
            select(Article)
            .where(Article.run_id == run.id, Article.status.not_in(["SUPERSEDED", "REJECTED"]))
            .order_by(Article.created_at.desc())
            .limit(1)
        )
        if article:
            detail = await build_article_detail(db, article, settings)
            source_rows = await build_article_sources(db, article)
            card.article_id, card.article_status, card.headline_options = (
                article.id,
                ArticleStatus(article.status),
                detail.title_options,
            )
            candidate = await db.get(TopicCandidateRecord, article.candidate_id)
            counted_gate = await db.scalar(
                select(Review)
                .where(
                    Review.version_id == article.current_version_id,
                    Review.kind == "quality_gate",
                    Review.gate_run_kind.in_(["full", "fix_pass", "recheck"]),
                )
                .order_by(Review.created_at.desc(), Review.id.desc())
                .limit(1)
            )
            card.quality = (
                QualitySummaryOut(
                    fact_check_verdict=detail.fact_check.verdict if detail.fact_check else None,
                    source_count=len(source_rows),
                    tier_mix={f"tier{tier}": sum(s.tier == tier for s in source_rows) for tier in (1, 2, 3)},
                    novelty_percent=round(candidate.novelty_score * 100, 1)
                    if candidate and candidate.novelty_score is not None
                    else None,
                    clinical_clear=not any(flag.severity == "BLOCKING" for flag in detail.clinical_review.flags)
                    if detail.clinical_review
                    else None,
                    editorial_score=detail.editorial_review.editorial_score if detail.editorial_review else None,
                    seo_complete=next(
                        (gate.passed for gate in detail.quality_gates.results if gate.gate == "seo_complete"), None
                    )
                    if detail.quality_gates
                    else None,
                    gates_passed=counted_gate.verdict == "PASSED" if counted_gate else None,
                )
                if article.current_version_id
                else None
            )
    metrics = DashboardMetricsOut(
        window_days=30,
        posts_generated=await _count(
            db,
            ArticleVersion,
            ArticleVersion.version_no == 1,
            ArticleVersion.created_at >= window,
            ArticleVersion.created_at <= now,
        ),
        posts_published=await _count(db, Article, Article.published_at >= window, Article.published_at <= now),
        posts_pending=await _count(
            db,
            Article,
            Article.status.in_(["READY_FOR_REVIEW", "QUALITY_GATE_FAILED", "APPROVED", "SCHEDULED", "EXPORTED"]),
        ),
    )
    return DashboardOut(
        generated_at=now,
        timezone=config.schedule.timezone,
        today=card,
        pipeline=PipelineTrackerOut(run_id=run.id if run else None, stages=stages),
        metrics=metrics,
    )


TRACKER_STAGES = [
    ("discover.open_attempt", "Start run"),
    ("discover.gather_signals", "Gather signals"),
    ("discover.build_ledger", "Build source ledger"),
    ("discover.synthesize_research", "Synthesize research"),
    ("discover.ideate_topics", "Ideate topics"),
    ("discover.check_novelty_and_score", "Check novelty and score"),
    ("discover.select_topic", "Select topic"),
    ("produce.deep_research", "Deep research"),
    ("produce.build_research_packet", "Build research packet"),
    ("produce.write_draft", "Write draft"),
    ("produce.fact_check", "Fact check"),
    ("produce.clinical_review", "Clinical review"),
    ("produce.editorial_review", "Editorial review"),
    ("produce.revise", "Revise"),
    ("produce.verify_facts", "Verify facts"),
    ("produce.seo", "SEO"),
    ("produce.quality_gates", "Quality gates"),
]


async def pipeline_stages(db: AsyncSession, run_id: uuid.UUID | None) -> list[PipelineStageOut]:
    rows = (
        list(
            await db.scalars(
                select(AgentRun)
                .join(RunAttempt, AgentRun.attempt_id == RunAttempt.id)
                .where(
                    AgentRun.run_id == run_id,
                    RunAttempt.workflow_name.in_(["discover_topics", "produce_article", "change_topic"]),
                )
                .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
            )
        )
        if run_id
        else []
    )
    matches: list[AgentRun | None] = []
    for key, _ in TRACKER_STAGES:
        aliases = {key}
        if key.startswith("produce."):
            part = key.removeprefix("produce.")
            aliases.add(f"change_topic.{part}")
            if part in {"revise", "verify_facts", "seo", "quality_gates"}:
                aliases.update({f"produce.fix_pass.{part}", f"change_topic.fix_pass.{part}"})
        matches.append(next((row for row in rows if row.step_name in aliases), None))
    output = []
    for index, ((key, label), row) in enumerate(zip(TRACKER_STAGES, matches, strict=True)):
        later = matches[index + 1 : 7] if index < 7 else matches[index + 1 :]
        status = (
            {"SUCCEEDED": "done", "FAILED": "failed", "RUNNING": "running"}.get(row.status, "pending")
            if row
            else "skipped"
            if any(later)
            else "pending"
        )
        output.append(
            PipelineStageOut(
                key=key,
                label=label,
                status=status,
                started_at=row.started_at if row else None,
                finished_at=row.completed_at if row else None,
            )
        )
    return output
