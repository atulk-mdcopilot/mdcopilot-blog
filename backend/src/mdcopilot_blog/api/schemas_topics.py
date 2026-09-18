"""Topic intelligence API contracts."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.api.schemas_common import SourceRefOut
from mdcopilot_blog.domain.contracts import NewsRef, NoveltyNeighbour, NoveltyResult, PillarKey, ScoreItem
from mdcopilot_blog.domain.enums import ArticleStatus, CandidateStatus, HeadlinePattern, RunStatus


class TopicCandidateOut(ApiModel):
    id: uuid.UUID
    run_id: uuid.UUID
    round: int
    position: int
    title: str
    hook: str
    why_now: str
    thesis: str
    angle: str
    core_argument: str
    mdcopilot_connection: str
    target_audience: str
    pillar: PillarKey
    relevant_news: list[NewsRef]
    sources: list[SourceRefOut]
    examples: list[str]
    novelty_score: float | None
    evidence_score: float | None
    business_relevance: float | None
    editorial_potential: float | None
    timeliness_score: float | None
    audience_relevance: float | None
    total_score: float | None
    score_breakdown: dict[str, ScoreItem]
    novelty: NoveltyResult | None
    status: CandidateStatus
    is_manual: bool
    selected_at: datetime | None
    selected_by: uuid.UUID | None
    rejected_reason: str | None
    article_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class TopicRoundOut(ApiModel):
    run_id: uuid.UUID
    run_status: RunStatus
    round: int
    rounds_available: list[int]
    shortfall: bool
    items: list[TopicCandidateOut]


class TopicsGenerateRequest(ApiModel):
    run_id: uuid.UUID


class TopicSelectRequest(ApiModel):
    confirm_warning: bool = False


class TopicUpdate(ApiModel):
    title: Annotated[str, Field(min_length=1, max_length=300)] | SkipJsonSchema[None] = None
    hook: Annotated[str, Field(min_length=1, max_length=10000)] | SkipJsonSchema[None] = None
    why_now: Annotated[str, Field(min_length=1, max_length=10000)] | SkipJsonSchema[None] = None
    thesis: Annotated[str, Field(min_length=1, max_length=10000)] | SkipJsonSchema[None] = None
    angle: Annotated[str, Field(min_length=1, max_length=10000)] | SkipJsonSchema[None] = None
    core_argument: Annotated[str, Field(min_length=1, max_length=10000)] | SkipJsonSchema[None] = None
    target_audience: Annotated[str, Field(min_length=1, max_length=10000)] | SkipJsonSchema[None] = None
    pillar: PillarKey | SkipJsonSchema[None] = None

    @model_validator(mode="after")
    def check_changes(self) -> "TopicUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} may not be null")
        return self


class TopicHistoryOut(ApiModel):
    id: uuid.UUID
    title: str
    pillar: PillarKey
    thesis: str
    core_argument: str
    headline_pattern: HeadlinePattern
    keywords: list[str]
    examples: list[str]
    primary_source_url: str | None
    article_id: uuid.UUID | None
    article_status: ArticleStatus | None
    created_at: datetime


class ExternalPostOut(ApiModel):
    id: uuid.UUID
    origin: str
    slug: str
    title: str
    excerpt: str
    url: str
    published_at: datetime | None
    headline_pattern: HeadlinePattern
    last_synced_at: datetime


class SimilarityOut(ApiModel):
    text: str
    items: list[NoveltyNeighbour]
