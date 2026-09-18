"""Article editing and immutable version API contracts."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.api.schemas_common import SourceRefOut
from mdcopilot_blog.domain.contracts import (
    ArticleSection,
    BlogSource,
    ClinicalReview,
    EditorialReview,
    FactCheckResult,
    FindingResolution,
    GateReport,
    NoveltyResult,
    PillarKey,
    ResearchPacket,
    SEOMetadata,
    SocialCopy,
    TitleOptions,
)
from mdcopilot_blog.domain.enums import (
    AccessMode,
    ApprovalMode,
    ArticleComponent,
    ArticleStatus,
    ChangeKind,
    DateSource,
    GateId,
    RunStatus,
    SectionKey,
    TitleKey,
)

Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class GateBadgeOut(ApiModel):
    passed: bool | None
    failed_gates: list[GateId]
    recheck_required: bool


class ArticleSummaryOut(ApiModel):
    id: uuid.UUID
    run_id: uuid.UUID
    run_date: date
    title: str | None
    slug: str | None
    status: ArticleStatus
    pipeline_status: RunStatus
    pillar: PillarKey
    category: str
    current_version_no: int | None
    word_count: int | None
    gate_badge: GateBadgeOut
    fact_check_verdict: Literal["PASS", "FAIL"] | None
    independent_check: bool | None
    editorial_score: float | None
    scheduled_for: datetime | None
    published_at: datetime | None
    published_url: str | None
    created_at: datetime
    updated_at: datetime


class ArticleDetailOut(ApiModel):
    id: uuid.UUID
    run_id: uuid.UUID
    run_date: date
    topic_id: uuid.UUID
    candidate_id: uuid.UUID
    title_options: TitleOptions | None
    selected_title: str | None
    selected_title_key: TitleKey | None
    slug: str | None
    content_markdown: str | None
    sections: list[ArticleSection] | None
    excerpt: str | None
    pull_quote: str | None
    cta: str | None
    category: str
    tags: list[str]
    pillar: PillarKey
    seo: SEOMetadata | None
    social: SocialCopy | None
    sources: list[BlogSource]
    research_summary: str | None
    research_packet_id: uuid.UUID | None
    research_packet_version: int | None
    fact_check: FactCheckResult | None
    clinical_review: ClinicalReview | None
    editorial_review: EditorialReview | None
    quality_gates: GateReport | None
    novelty: NoveltyResult | None
    status: ArticleStatus
    pipeline_status: RunStatus
    version_no: int | None
    current_version_id: uuid.UUID | None
    approved_version_id: uuid.UUID | None
    published_version_id: uuid.UUID | None
    recheck_required: bool
    gates_passed_on_current_version: bool
    network_publishing_active: bool
    gate_override_policy: Literal["admin_with_reason", "never"]
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    approval_mode: ApprovalMode | None
    rejection_reason: str | None
    scheduled_for: datetime | None
    scheduled_by: uuid.UUID | None
    published_at: datetime | None
    published_url: str | None
    created_at: datetime
    updated_at: datetime


class SeoEdit(ApiModel):
    seo_title: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=200)
    meta_description: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=500)
    slug: str | SkipJsonSchema[None] = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=200)
    primary_keyword: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=200)
    secondary_keywords: list[Tag] | SkipJsonSchema[None] = Field(default=None, max_length=50)
    og_title: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=200)
    og_description: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=500)
    tags: list[Tag] | SkipJsonSchema[None] = Field(default=None, max_length=50)
    category: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=100)

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("omit unchanged fields; explicit null is not allowed")
        return value

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("seo must change at least one field")
        return self


class ArticleEditRequest(ApiModel):
    base_version_id: uuid.UUID
    content_markdown: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=60000)
    pull_quote: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=500)
    cta: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=500)
    excerpt: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=500)
    title_options: TitleOptions | SkipJsonSchema[None] = None
    seo: SeoEdit | SkipJsonSchema[None] = None
    tags: list[Tag] | SkipJsonSchema[None] = Field(default=None, max_length=50)
    category: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=100)

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("omit unchanged fields; explicit null is not allowed")
        return value

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not any(
            value is not None for key, value in self.model_dump(by_alias=False).items() if key != "base_version_id"
        ):
            raise ValueError("provide at least one field to change besides baseVersionId")
        return self


class VersionSummaryOut(ApiModel):
    id: uuid.UUID
    version_no: int
    parent_version_id: uuid.UUID | None
    change_kind: ChangeKind
    change_scope: dict[str, Any]
    word_count: int
    created_by: uuid.UUID | None
    created_by_kind: Literal["agent", "human"]
    created_at: datetime
    fact_check_verdict: Literal["PASS", "FAIL"] | None
    gates_passed: bool | None


class VersionDetailOut(VersionSummaryOut):
    title_options: TitleOptions
    sections: list[ArticleSection]
    pull_quote: str
    cta: str
    excerpt: str
    content_markdown: str
    citation_markers: list[str]
    resolutions: list[FindingResolution]
    research_packet_id: uuid.UUID | None
    seo: SEOMetadata | None
    social: SocialCopy | None


class FieldChangeOut(ApiModel):
    field: str
    from_value: str | None = Field(alias="from")
    to_value: str | None = Field(alias="to")


class VersionDiffOut(ApiModel):
    from_version_id: uuid.UUID
    to_version_id: uuid.UUID
    from_version_no: int
    to_version_no: int
    unified_diff: str
    field_changes: list[FieldChangeOut]


class RegenerateRequest(ApiModel):
    component: ArticleComponent
    section_key: SectionKey | None = None
    instructions: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def valid_component(self) -> Self:
        self.instructions = self.instructions.strip() or None if self.instructions else None
        if self.component == ArticleComponent.SECTION and self.section_key is None:
            raise ValueError("sectionKey is required when component is section")
        if self.component == ArticleComponent.SECTION and self.section_key == SectionKey.INTRODUCTION:
            raise ValueError("sectionKey must not be introduction; use component introduction")
        if self.component != ArticleComponent.SECTION and self.section_key is not None:
            raise ValueError("sectionKey is allowed only when component is section")
        return self


class SelectTitleRequest(ApiModel):
    key: Literal["provocative", "operational", "visionary"] | None = None
    custom_title: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        self.custom_title = self.custom_title.strip() or None if self.custom_title else None
        if (self.key is None) == (self.custom_title is None):
            raise ValueError("provide exactly one of key or customTitle")
        return self


class ArticleSourceOut(ApiModel):
    marker: str
    source_id: uuid.UUID
    title: str
    url: str
    canonical_url: str
    publisher: str
    domain: str
    tier: int
    published_at: datetime | None
    date_source: DateSource
    access_mode: AccessMode
    is_primary: bool


class ResearchPacketOut(ApiModel):
    id: uuid.UUID
    article_id: uuid.UUID
    version: int
    summary: str
    packet: ResearchPacket
    sources: list[SourceRefOut]
    research_run_id: uuid.UUID | None
    created_at: datetime
