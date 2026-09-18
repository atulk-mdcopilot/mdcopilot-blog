"""Typed contracts shared by agents, workflows and the API.

Attributes are snake_case in Python and camelCase on the wire. Input may use either spelling,
unknown keys are rejected, and every score or confidence is bounded to 0..1.
Every field is required: a nullable field must still be sent, as null.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from mdcopilot_blog.domain.enums import (
    ApprovalMode,
    ArticleComponent,
    SectionKey,
)
from mdcopilot_blog.domain.text import ATX_HEADING_RE

UnitScore = Annotated[float, Field(ge=0, le=1)]
"""A score, weight, similarity or confidence in the closed interval 0..1."""

Marker = Annotated[str, Field(pattern=r"^S[1-9][0-9]*$")]
"""A citation marker ``S<n>`` as emitted by agents and stored in the article Markdown."""

SECTION_ORDER: tuple[SectionKey, ...] = tuple(SectionKey)
"""The seven article sections in assembly order."""


class Contract(BaseModel):
    """Base for every contract: camelCase aliases, both spellings accepted, no extra keys."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="forbid",
    )


# --- enums -----------------------------------------------------------------------------------------------------


class SourceType(StrEnum):
    GOVERNMENT = "government"
    JOURNAL = "journal"
    PREPRINT = "preprint"
    TRADE_PRESS = "trade_press"
    COMPANY_ANNOUNCEMENT = "company_announcement"
    BLOG = "blog"
    SOCIAL = "social"
    OTHER = "other"


class ClaimType(StrEnum):
    FACT = "FACT"
    ANALYSIS = "ANALYSIS"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    MARKETING_CLAIM = "MARKETING_CLAIM"


class VerificationStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    OUTDATED = "OUTDATED"
    MISLEADING = "MISLEADING"
    OPINION = "OPINION"


class ClaimKind(StrEnum):
    STATISTIC = "statistic"
    REGULATORY = "regulatory"
    TRIAL_RESULT = "trial_result"
    WORKFORCE = "workforce"
    COMPANY_ANNOUNCEMENT = "company_announcement"
    QUOTE_OR_ATTRIBUTION = "quote_or_attribution"
    ANECDOTE_OR_VIGNETTE = "anecdote_or_vignette"
    GENERAL_FACT = "general_fact"
    OPINION = "opinion"


class NoveltyDecision(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    REJECT_TOPIC = "REJECT_TOPIC"


class PillarKey(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    NARRATIVE = "NARRATIVE"


# --- research --------------------------------------------------------------------------------------------------


# --- topics and novelty ----------------------------------------------------------------------------------------


class NewsRef(Contract):
    title: str
    url: str
    published_at: datetime | None


class ScoreItem(Contract):
    """One component of a topic score."""

    weight: UnitScore
    score: UnitScore
    justification: str


class NoveltyNeighbour(Contract):
    """One of the nearest stored items to a candidate."""

    kind: str
    ref_id: str
    title: str
    similarity: UnitScore


class NoveltyResult(Contract):
    decision: NoveltyDecision
    max_similarity: UnitScore
    neighbours: list[NoveltyNeighbour]


# --- article parts ---------------------------------------------------------------------------------------------


class TitleOptions(Contract):
    provocative: str
    operational: str
    visionary: str


class InternalLink(Contract):
    title: str
    url: str


class SEOMetadata(Contract):
    """SEO output for one article version."""

    seo_title: str
    meta_description: str
    slug: str
    primary_keyword: str
    secondary_keywords: list[str]
    og_title: str
    og_description: str
    tags: list[str]
    category: str
    internal_link_suggestions: list[InternalLink]
    external_references: list[str]


class SocialCopy(Contract):
    linkedin: str
    x_post: str
    newsletter_teaser: str


class BlogSource(Contract):
    """A cited source as shown with the article; ``marker`` is the ``S<n>`` citation marker."""

    marker: str
    source_id: str
    title: str
    url: str
    publisher: str
    published_at: datetime | None


# --- reviews ---------------------------------------------------------------------------------------------------


class ClaimCheck(Contract):
    """One extracted claim and its verification."""

    claim: str
    kind: ClaimKind
    importance: Literal["high", "normal"]
    section_key: str
    sentence_index: Annotated[int, Field(ge=0)]
    span: str
    citation_markers: list[str]
    source_id: str | None
    verification_status: VerificationStatus
    confidence: UnitScore
    recommended_revision: str | None


class FactCheckResult(Contract):
    verdict: Literal["PASS", "FAIL"]
    independent_check: bool
    claims: list[ClaimCheck]


class ClinicalFlag(Contract):
    code: str
    severity: Literal["BLOCKING", "WARNING"]
    message: str
    location: str


class ClinicalReview(Contract):
    flags: list[ClinicalFlag]
    summary: str


class Change(Contract):
    """An editorial change request; the writer records a resolution against ``id``."""

    id: str
    description: str
    location: str


class EditorialReview(Contract):
    editorial_score: UnitScore
    strengths: list[str]
    weaknesses: list[str]
    required_changes: list[Change]
    optional_changes: list[Change]
    final_recommendation: str


class GateResult(Contract):
    gate: str
    passed: bool
    severity: Literal["blocking", "warning"]
    details: str


class GateReport(Contract):
    passed: bool
    results: list[GateResult]


# --- research packet -------------------------------------------------------------------------------------------


class SourceRef(Contract):
    """A marker-to-ledger-id mapping; code fills this from the numbered source list."""

    marker: Marker
    source_id: str


class PacketFact(Contract):
    statement: str
    markers: list[Marker]
    importance: Literal["high", "normal"]


class PacketStatistic(Contract):
    statement: str
    value: str
    markers: list[Marker]
    as_of: str | None


class ResearchPacket(Contract):
    summary: str
    key_facts: list[PacketFact]
    statistics: list[PacketStatistic]
    primary_markers: list[Marker]
    supporting_markers: list[Marker]
    counterarguments: list[PacketFact]
    industry_context: str
    mdcopilot_connection: str
    claims_needing_verification: list[str]
    source_refs: list[SourceRef]


# --- article draft ---------------------------------------------------------------------------------------------


class ArticleSection(Contract):
    key: SectionKey
    heading: str | None
    body_markdown: str

    @model_validator(mode="after")
    def _check_heading_rule(self) -> "ArticleSection":
        if (self.key == SectionKey.INTRODUCTION) != (self.heading is None):
            raise ValueError("heading must be null for the introduction and non-null for every other section")
        return self

    @model_validator(mode="after")
    def _check_body_has_no_headings(self) -> "ArticleSection":
        for line in self.body_markdown.splitlines():
            if ATX_HEADING_RE.match(line):
                raise ValueError("body_markdown must not contain headings")
        return self


class FindingResolution(Contract):
    finding_id: str
    action: Literal["fixed", "removed", "declined"]
    note: str


class ArticleDraft(Contract):
    title_options: TitleOptions
    sections: list[ArticleSection]
    pull_quote: str
    cta: str
    excerpt: Annotated[str, Field(max_length=500)]
    resolutions: list[FindingResolution]

    @model_validator(mode="after")
    def _check_section_order(self) -> "ArticleDraft":
        if [section.key for section in self.sections] != list(SECTION_ORDER):
            raise ValueError("sections must follow SECTION_ORDER")
        return self


class ComponentDraft(Contract):
    component: ArticleComponent
    section_key: SectionKey | None
    title_options: TitleOptions | None
    section: ArticleSection | None
    pull_quote: str | None
    cta: str | None

    @model_validator(mode="after")
    def _check_component_field_rule(self) -> "ComponentDraft":
        if self.component in (ArticleComponent.ARTICLE, ArticleComponent.RESEARCH):
            raise ValueError("component article/research has no draft field")
        matching = {
            ArticleComponent.HEADLINE: self.title_options,
            ArticleComponent.INTRODUCTION: self.section,
            ArticleComponent.SECTION: self.section,
            ArticleComponent.PULL_QUOTE: self.pull_quote,
            ArticleComponent.CTA: self.cta,
        }[self.component]
        present = [
            value for value in (self.title_options, self.section, self.pull_quote, self.cta) if value is not None
        ]
        if len(present) != 1 or matching is None:
            raise ValueError("exactly the field matching component must be set")
        return self


class RevisionFinding(Contract):
    finding_id: str
    origin: Literal["claim_check", "clinical_flag", "editorial_change", "quality_gate"]
    description: str
    location: str
    recommended_revision: str | None
    required: bool


class RecentArticleRef(Contract):
    title: str
    core_argument: str
    opening_sentence: str


class AvoidBundle(Contract):
    recent_articles: list[RecentArticleRef]
    recent_titles: list[str]
    recent_openings: list[str]
    recent_ctas: list[str]
    recent_primary_sources: list[str]
    overused_phrases: list[str]
    prohibited_language: list[str]


class SeoPackage(Contract):
    seo: SEOMetadata
    social: SocialCopy


class HumanDecision(Contract):
    decision: Literal["APPROVED", "OVERRIDE_APPROVED", "REJECTED"]
    mode: ApprovalMode | None
    reason: str | None
    version_id: str


# --- article view ----------------------------------------------------------------------------------------------
