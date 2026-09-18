"""Dashboard summaries and generation progress."""

import uuid
from datetime import date, datetime
from typing import Literal

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.domain.contracts import PillarKey, TitleOptions
from mdcopilot_blog.domain.enums import ArticleStatus, RunStatus


class RecommendedTopicOut(ApiModel):
    candidate_id: uuid.UUID
    title: str
    why_now: str
    pillar: PillarKey
    evidence_score: float | None
    business_relevance: float | None
    novelty_score: float | None
    total_score: float | None


class QualitySummaryOut(ApiModel):
    fact_check_verdict: Literal["PASS", "FAIL"] | None
    source_count: int
    tier_mix: dict[str, int]
    novelty_percent: float | None
    clinical_clear: bool | None
    editorial_score: float | None
    seo_complete: bool | None
    gates_passed: bool | None


class TodayCardOut(ApiModel):
    date: date
    run_id: uuid.UUID | None
    run_status: RunStatus | None
    research_status: Literal["not_started", "running", "done", "failed"]
    opportunities_discovered: int
    recommended_topic: RecommendedTopicOut | None
    article_id: uuid.UUID | None
    article_status: ArticleStatus | None
    headline_options: TitleOptions | None
    quality: QualitySummaryOut | None


class PipelineStageOut(ApiModel):
    key: str
    label: str
    status: Literal["pending", "running", "done", "failed", "skipped"]
    started_at: datetime | None
    finished_at: datetime | None


class PipelineTrackerOut(ApiModel):
    run_id: uuid.UUID | None
    stages: list[PipelineStageOut]


class DashboardMetricsOut(ApiModel):
    window_days: int
    posts_generated: int
    posts_published: int
    posts_pending: int


class DashboardOut(ApiModel):
    generated_at: datetime
    timezone: str
    today: TodayCardOut
    pipeline: PipelineTrackerOut
    metrics: DashboardMetricsOut
