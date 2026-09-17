"""Typed contracts (ARCHITECTURE §12): every field present, camelCase on the wire, strict input, bounded scores."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from mdcopilot_blog.domain import contracts as c
from mdcopilot_blog.domain.enums import (
    AgentName,
    ArticleStatus,
    AttemptStatus,
    CallKind,
    CallStatus,
    RunKind,
    RunStatus,
    StepStatus,
)

Builder = Callable[[], dict[str, Any]]

NOW = "2026-09-17T07:00:00Z"


# --- valid snake_case payloads, one builder per contract -------------------------------------------------------


def research_source() -> dict[str, Any]:
    return {
        "id": "src_1",
        "title": "FDA updates its list of AI-enabled medical devices",
        "url": "https://www.fda.gov/medical-devices/ai-enabled-devices?utm_source=feed",
        "canonical_url": "https://www.fda.gov/medical-devices/ai-enabled-devices",
        "publisher": "U.S. Food and Drug Administration",
        "domain": "fda.gov",
        "published_at": "2026-09-15T00:00:00Z",
        "date_source": "feed",
        "retrieved_at": NOW,
        "source_type": "government",
        "tier": 1,
        "access_mode": "full_text",
        "relevance_score": 0.9,
    }


def research_finding() -> dict[str, Any]:
    return {
        "id": "fnd_1",
        "claim": "The FDA list now includes more than 1,200 AI-enabled devices.",
        "evidence": "The September update lists 1,247 devices.",
        "source_ids": ["src_1"],
        "confidence": 0.8,
        "category": "regulation",
        "claim_type": "FACT",
        "importance": "high",
    }


def news_ref() -> dict[str, Any]:
    return {"title": "FDA list update", "url": "https://www.fda.gov/news/1", "published_at": NOW}


def score_item() -> dict[str, Any]:
    return {"weight": 0.25, "score": 1.0, "justification": "Primary source published within 48 hours."}


def novelty_neighbour() -> dict[str, Any]:
    return {"kind": "article", "ref_id": "art_9", "title": "What the FDA device list tells us", "similarity": 0.42}


def novelty_result() -> dict[str, Any]:
    return {"decision": "PASS", "max_similarity": 0.42, "neighbours": [novelty_neighbour()]}


def topic_candidate() -> dict[str, Any]:
    return {
        "topic_id": "top_1",
        "title": "The FDA's AI device list is a workload map",
        "hook": "Radiology holds most of the clearances.",
        "why_now": "The list was updated this week.",
        "relevant_news": [news_ref()],
        "mdcopilot_connection": "Specialist leverage on the imaging bottleneck.",
        "target_audience": "Hospital CMIOs",
        "pillar": "A",
        "novelty_score": 0.58,
        "evidence_score": 0.9,
        "business_relevance": 0.75,
        "editorial_potential": 0.5,
        "timeliness_score": 1.0,
        "audience_relevance": 0.75,
        "total_score": 0.8,
        "score_breakdown": {"timeliness": score_item(), "novelty": score_item()},
        "novelty": novelty_result(),
        "sources": ["src_1"],
        "status": "PROPOSED",
    }


def title_options() -> dict[str, Any]:
    return {
        "provocative": "Most AI clearances point at one specialty",
        "operational": "Reading the FDA AI device list",
        "visionary": "Where specialist leverage goes next",
    }


def internal_link() -> dict[str, Any]:
    return {"title": "Specialist leverage", "url": "https://www.mdcopilot.health/blog/specialist-leverage"}


def seo_metadata() -> dict[str, Any]:
    return {
        "seo_title": "Reading the FDA AI device list",
        "meta_description": "What the latest FDA list of AI-enabled devices says about where specialist time goes.",
        "slug": "fda-ai-device-list",
        "primary_keyword": "FDA AI devices",
        "secondary_keywords": ["AI-enabled medical devices", "radiology AI"],
        "og_title": "Reading the FDA AI device list",
        "og_description": "Where the clearances cluster, and why.",
        "tags": ["regulation", "radiology"],
        "category": "Healthcare AI",
        "internal_link_suggestions": [internal_link()],
        "external_references": ["src_1"],
    }


def social_copy() -> dict[str, Any]:
    return {
        "linkedin": "The FDA list is a workload map.",
        "x_post": "Most AI clearances point at one specialty.",
        "newsletter_teaser": "This week: reading the FDA list.",
    }


def blog_source() -> dict[str, Any]:
    return {
        "marker": "S1",
        "source_id": "src_1",
        "title": "FDA updates its list of AI-enabled medical devices",
        "url": "https://www.fda.gov/medical-devices/ai-enabled-devices",
        "publisher": "U.S. Food and Drug Administration",
        "published_at": "2026-09-15T00:00:00Z",
    }


def claim_check() -> dict[str, Any]:
    return {
        "claim": "The list includes 1,247 devices.",
        "kind": "statistic",
        "importance": "high",
        "section_key": "evidence",
        "sentence_index": 2,
        "span": "1,247 devices",
        "citation_markers": ["S1"],
        "source_id": "src_1",
        "verification_status": "SUPPORTED",
        "confidence": 0.95,
        "recommended_revision": None,
    }


def fact_check_result() -> dict[str, Any]:
    return {"verdict": "PASS", "independent_check": True, "claims": [claim_check()]}


def clinical_flag() -> dict[str, Any]:
    return {
        "code": "autonomous_ai_claim",
        "severity": "WARNING",
        "message": "Implies the model reads scans without a radiologist.",
        "location": "core_argument:3",
    }


def clinical_review() -> dict[str, Any]:
    return {"flags": [clinical_flag()], "summary": "No blocking issues."}


def change() -> dict[str, Any]:
    return {"id": "chg_1", "description": "Tighten the opening.", "location": "introduction:0"}


def editorial_review() -> dict[str, Any]:
    return {
        "editorial_score": 0.82,
        "strengths": ["Clear thesis"],
        "weaknesses": ["Long opening"],
        "required_changes": [change()],
        "optional_changes": [],
        "final_recommendation": "Revise, then approve.",
    }


def gate_result() -> dict[str, Any]:
    return {"gate": "word_count", "passed": True, "severity": "blocking", "details": "1012 words"}


def gate_report() -> dict[str, Any]:
    return {"passed": True, "results": [gate_result()]}


def generated_blog_post() -> dict[str, Any]:
    return {
        "id": "art_1",
        "topic_id": "top_1",
        "title_options": title_options(),
        "selected_title": "Reading the FDA AI device list",
        "slug": "fda-ai-device-list",
        "content_markdown": "Radiology holds most of the clearances [S1].\n\n## Context\n\nText.",
        "excerpt": "Where the clearances cluster, and why.",
        "pull_quote": "The list is a workload map.",
        "cta": "See how MDCopilot supports specialists.",
        "category": "Healthcare AI",
        "tags": ["regulation"],
        "seo": seo_metadata(),
        "social": social_copy(),
        "sources": [blog_source()],
        "research_summary": "Seven dated sources, two Tier-1.",
        "fact_check": fact_check_result(),
        "clinical_review": clinical_review(),
        "editorial_review": editorial_review(),
        "quality_gates": gate_report(),
        "novelty": novelty_result(),
        "status": "READY_FOR_REVIEW",
        "pipeline_status": "SUCCEEDED",
        "version_no": 2,
        "created_at": NOW,
        "updated_at": NOW,
    }


def source_ref() -> dict[str, Any]:
    return {"marker": "S1", "source_id": "src_1"}


def packet_fact() -> dict[str, Any]:
    return {"statement": "The list includes 1,247 devices.", "markers": ["S1"], "importance": "high"}


def packet_statistic() -> dict[str, Any]:
    return {"statement": "Clearances grew 30%", "value": "30%", "markers": ["S1"], "as_of": "2026-09-15"}


def research_packet() -> dict[str, Any]:
    return {
        "summary": "Seven dated sources, two Tier-1.",
        "key_facts": [packet_fact()],
        "statistics": [packet_statistic()],
        "primary_markers": ["S1"],
        "supporting_markers": ["S2"],
        "counterarguments": [],
        "industry_context": "Imaging AI is the largest clearance category.",
        "mdcopilot_connection": "Specialist leverage on the imaging bottleneck.",
        "claims_needing_verification": ["The 1,247 figure"],
        "source_refs": [source_ref()],
    }


def article_section() -> dict[str, Any]:
    return {"key": "context", "heading": "Context", "body_markdown": "The FDA list is updated monthly."}


def finding_resolution() -> dict[str, Any]:
    return {"finding_id": "claim:c1", "action": "fixed", "note": "Reworded the statistic."}


def article_draft() -> dict[str, Any]:
    sections = [
        {"key": "introduction", "heading": None, "body_markdown": "Radiology holds most of the clearances [S1]."},
        {"key": "context", "heading": "Context", "body_markdown": "The FDA list is updated monthly."},
        {"key": "core_argument", "heading": "Core argument", "body_markdown": "The list is a workload map."},
        {"key": "evidence", "heading": "Evidence", "body_markdown": "Most clearances cluster in imaging."},
        {"key": "mdcopilot_perspective", "heading": "MDCopilot perspective", "body_markdown": "Specialists gain leverage."},
        {"key": "practical_implications", "heading": "Practical implications", "body_markdown": "Teams can plan capacity."},
        {"key": "conclusion", "heading": "Conclusion", "body_markdown": "Watch the next update."},
    ]
    return {
        "title_options": title_options(),
        "sections": sections,
        "pull_quote": "The list is a workload map.",
        "cta": "See how MDCopilot supports specialists.",
        "excerpt": "Where the clearances cluster, and why.",
        "resolutions": [finding_resolution()],
    }


def component_draft() -> dict[str, Any]:
    return {"component": "pull_quote", "section_key": None, "title_options": None, "section": None,
            "pull_quote": "The list is a workload map.", "cta": None}


def revision_finding() -> dict[str, Any]:
    return {
        "finding_id": "claim:c1",
        "origin": "claim_check",
        "description": "Statistic is unsupported.",
        "location": "evidence:2",
        "recommended_revision": "Remove the figure.",
        "required": True,
    }


def recent_article_ref() -> dict[str, Any]:
    return {"title": "Specialist leverage", "core_argument": "AI gives specialists leverage.", "opening_sentence": "Clinicians are busy."}


def avoid_bundle() -> dict[str, Any]:
    return {
        "recent_articles": [recent_article_ref()],
        "recent_titles": ["Specialist leverage"],
        "recent_openings": ["Clinicians are busy."],
        "recent_ctas": ["Book a demo."],
        "recent_primary_sources": ["fda.gov"],
        "overused_phrases": ["game changer"],
        "prohibited_language": ["revolutionary"],
    }


def seo_package() -> dict[str, Any]:
    return {"seo": seo_metadata(), "social": social_copy()}


def human_decision() -> dict[str, Any]:
    return {"decision": "APPROVED", "mode": "draft", "reason": None, "version_id": "ver_1"}


BUILDERS: dict[type[c.Contract], Builder] = {
    c.ResearchSource: research_source,
    c.ResearchFinding: research_finding,
    c.NewsRef: news_ref,
    c.ScoreItem: score_item,
    c.NoveltyNeighbour: novelty_neighbour,
    c.NoveltyResult: novelty_result,
    c.TopicCandidate: topic_candidate,
    c.TitleOptions: title_options,
    c.InternalLink: internal_link,
    c.SEOMetadata: seo_metadata,
    c.SocialCopy: social_copy,
    c.BlogSource: blog_source,
    c.ClaimCheck: claim_check,
    c.FactCheckResult: fact_check_result,
    c.ClinicalFlag: clinical_flag,
    c.ClinicalReview: clinical_review,
    c.Change: change,
    c.EditorialReview: editorial_review,
    c.GateResult: gate_result,
    c.GateReport: gate_report,
    c.GeneratedBlogPost: generated_blog_post,
    c.SourceRef: source_ref,
    c.PacketFact: packet_fact,
    c.PacketStatistic: packet_statistic,
    c.ResearchPacket: research_packet,
    c.ArticleSection: article_section,
    c.FindingResolution: finding_resolution,
    c.ArticleDraft: article_draft,
    c.ComponentDraft: component_draft,
    c.RevisionFinding: revision_finding,
    c.RecentArticleRef: recent_article_ref,
    c.AvoidBundle: avoid_bundle,
    c.SeoPackage: seo_package,
    c.HumanDecision: human_decision,
}

# Field names from ARCHITECTURE §12 and the Phase 1 contract, written out by hand.
EXPECTED_FIELDS: dict[type[c.Contract], set[str]] = {
    c.ResearchSource: {
        "id",
        "title",
        "url",
        "canonical_url",
        "publisher",
        "domain",
        "published_at",
        "date_source",
        "retrieved_at",
        "source_type",
        "tier",
        "access_mode",
        "relevance_score",
    },
    c.ResearchFinding: {
        "id",
        "claim",
        "evidence",
        "source_ids",
        "confidence",
        "category",
        "claim_type",
        "importance",
    },
    c.NewsRef: {"title", "url", "published_at"},
    c.ScoreItem: {"weight", "score", "justification"},
    c.NoveltyNeighbour: {"kind", "ref_id", "title", "similarity"},
    c.NoveltyResult: {"decision", "max_similarity", "neighbours"},
    c.TopicCandidate: {
        "topic_id",
        "title",
        "hook",
        "why_now",
        "relevant_news",
        "mdcopilot_connection",
        "target_audience",
        "pillar",
        "novelty_score",
        "evidence_score",
        "business_relevance",
        "editorial_potential",
        "timeliness_score",
        "audience_relevance",
        "total_score",
        "score_breakdown",
        "novelty",
        "sources",
        "status",
    },
    c.TitleOptions: {"provocative", "operational", "visionary"},
    c.InternalLink: {"title", "url"},
    c.SEOMetadata: {
        "seo_title",
        "meta_description",
        "slug",
        "primary_keyword",
        "secondary_keywords",
        "og_title",
        "og_description",
        "tags",
        "category",
        "internal_link_suggestions",
        "external_references",
    },
    c.SocialCopy: {"linkedin", "x_post", "newsletter_teaser"},
    c.BlogSource: {"marker", "source_id", "title", "url", "publisher", "published_at"},
    c.ClaimCheck: {
        "claim",
        "kind",
        "importance",
        "section_key",
        "sentence_index",
        "span",
        "citation_markers",
        "source_id",
        "verification_status",
        "confidence",
        "recommended_revision",
    },
    c.FactCheckResult: {"verdict", "independent_check", "claims"},
    c.ClinicalFlag: {"code", "severity", "message", "location"},
    c.ClinicalReview: {"flags", "summary"},
    c.Change: {"id", "description", "location"},
    c.EditorialReview: {
        "editorial_score",
        "strengths",
        "weaknesses",
        "required_changes",
        "optional_changes",
        "final_recommendation",
    },
    c.GateResult: {"gate", "passed", "severity", "details"},
    c.GateReport: {"passed", "results"},
    c.GeneratedBlogPost: {
        "id",
        "topic_id",
        "title_options",
        "selected_title",
        "slug",
        "content_markdown",
        "excerpt",
        "pull_quote",
        "cta",
        "category",
        "tags",
        "seo",
        "social",
        "sources",
        "research_summary",
        "fact_check",
        "clinical_review",
        "editorial_review",
        "quality_gates",
        "novelty",
        "status",
        "pipeline_status",
        "version_no",
        "created_at",
        "updated_at",
    },
    c.SourceRef: {"marker", "source_id"},
    c.PacketFact: {"statement", "markers", "importance"},
    c.PacketStatistic: {"statement", "value", "markers", "as_of"},
    c.ResearchPacket: {
        "summary",
        "key_facts",
        "statistics",
        "primary_markers",
        "supporting_markers",
        "counterarguments",
        "industry_context",
        "mdcopilot_connection",
        "claims_needing_verification",
        "source_refs",
    },
    c.ArticleSection: {"key", "heading", "body_markdown"},
    c.FindingResolution: {"finding_id", "action", "note"},
    c.ArticleDraft: {"title_options", "sections", "pull_quote", "cta", "excerpt", "resolutions"},
    c.ComponentDraft: {"component", "section_key", "title_options", "section", "pull_quote", "cta"},
    c.RevisionFinding: {"finding_id", "origin", "description", "location", "recommended_revision", "required"},
    c.RecentArticleRef: {"title", "core_argument", "opening_sentence"},
    c.AvoidBundle: {
        "recent_articles",
        "recent_titles",
        "recent_openings",
        "recent_ctas",
        "recent_primary_sources",
        "overused_phrases",
        "prohibited_language",
    },
    c.SeoPackage: {"seo", "social"},
    c.HumanDecision: {"decision", "mode", "reason", "version_id"},
}

# Every score or confidence in the contracts.
BOUNDED: list[tuple[type[c.Contract], str]] = [
    (c.ResearchSource, "relevance_score"),
    (c.ResearchFinding, "confidence"),
    (c.ScoreItem, "weight"),
    (c.ScoreItem, "score"),
    (c.NoveltyNeighbour, "similarity"),
    (c.NoveltyResult, "max_similarity"),
    (c.TopicCandidate, "novelty_score"),
    (c.TopicCandidate, "evidence_score"),
    (c.TopicCandidate, "business_relevance"),
    (c.TopicCandidate, "editorial_potential"),
    (c.TopicCandidate, "timeliness_score"),
    (c.TopicCandidate, "audience_relevance"),
    (c.TopicCandidate, "total_score"),
    (c.ClaimCheck, "confidence"),
    (c.EditorialReview, "editorial_score"),
]

MODELS = [pytest.param(model, id=model.__name__) for model in BUILDERS]


def _param(model: type[c.Contract], field: str, value: object) -> Any:
    return pytest.param(model, field, value, id=f"{model.__name__}.{field}={value!r}")


def _keys_with_underscores(value: object, path: str = "") -> list[str]:
    """Return every JSON object key containing "_" (dict-valued data such as scoreBreakdown is skipped)."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if "_" in key:
                found.append(f"{path}.{key}")
            if key != "scoreBreakdown":
                found.extend(_keys_with_underscores(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_keys_with_underscores(item, f"{path}[{index}]"))
    return found


# --- enums -----------------------------------------------------------------------------------------------------


def test_contract_enum_values() -> None:
    assert [v.value for v in c.SourceType] == [
        "government",
        "journal",
        "preprint",
        "trade_press",
        "company_announcement",
        "blog",
        "social",
        "other",
    ]
    assert [v.value for v in c.ClaimType] == ["FACT", "ANALYSIS", "OPINION", "PREDICTION", "MARKETING_CLAIM"]
    assert [v.value for v in c.VerificationStatus] == [
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "UNSUPPORTED",
        "OUTDATED",
        "MISLEADING",
        "OPINION",
    ]
    assert [v.value for v in c.ClaimKind] == [
        "statistic",
        "regulatory",
        "trial_result",
        "workforce",
        "company_announcement",
        "quote_or_attribution",
        "anecdote_or_vignette",
        "general_fact",
        "opinion",
    ]
    assert [v.value for v in c.NoveltyDecision] == ["PASS", "WARN", "REJECT_TOPIC"]
    assert [v.value for v in c.PillarKey] == ["A", "B", "C", "D", "E", "NARRATIVE"]


def test_shared_enum_wire_values() -> None:
    assert [v.value for v in RunKind] == ["daily", "manual"]
    assert [v.value for v in AttemptStatus] == ["ENQUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    assert [v.value for v in StepStatus] == ["RUNNING", "SUCCEEDED", "FAILED"]
    assert [v.value for v in CallKind] == ["agent", "search", "embedding"]
    assert [v.value for v in CallStatus] == ["ok", "error"]
    assert {v.name: v.value for v in AgentName} == {
        "SEARCH": "search",
        "RESEARCH": "research",
        "IDEATION": "ideation",
        "DEEP_RESEARCH": "deep_research",
        "WRITER": "writer",
        "FACT_CHECK": "fact_check",
        "CLINICAL": "clinical",
        "EDITORIAL": "editorial",
        "SEO": "seo",
        "HELLO": "hello",
    }


# --- field coverage --------------------------------------------------------------------------------------------


def test_every_contract_model_is_covered_by_these_tests() -> None:
    defined = {
        obj
        for obj in vars(c).values()
        if isinstance(obj, type) and issubclass(obj, c.Contract) and obj is not c.Contract
    }
    assert defined == set(BUILDERS) == set(EXPECTED_FIELDS)


@pytest.mark.parametrize("model", MODELS)
def test_model_has_exactly_the_specified_fields(model: type[c.Contract]) -> None:
    assert set(model.model_fields) == EXPECTED_FIELDS[model]


@pytest.mark.parametrize("model", MODELS)
def test_every_field_is_required(model: type[c.Contract]) -> None:
    # §12 gives no defaults: nullable fields must still be sent explicitly (as null).
    assert all(info.is_required() for info in model.model_fields.values())


# --- parsing ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("model", MODELS)
def test_parses_snake_case(model: type[c.Contract]) -> None:
    instance = model.model_validate(BUILDERS[model]())
    assert set(type(instance).model_fields) == EXPECTED_FIELDS[model]


@pytest.mark.parametrize("model", MODELS)
def test_camel_case_round_trip(model: type[c.Contract]) -> None:
    original = model.model_validate(BUILDERS[model]())
    wire = original.model_dump(mode="json")
    assert model.model_validate(wire) == original
    assert model.model_validate_json(original.model_dump_json()) == original


def test_parses_hand_written_camel_case_payload() -> None:
    seo = c.SEOMetadata.model_validate(
        {
            "seoTitle": "Reading the FDA AI device list",
            "metaDescription": "What the latest FDA list says.",
            "slug": "fda-ai-device-list",
            "primaryKeyword": "FDA AI devices",
            "secondaryKeywords": ["radiology AI"],
            "ogTitle": "Reading the list",
            "ogDescription": "Where the clearances cluster.",
            "tags": ["regulation"],
            "category": "Healthcare AI",
            "internalLinkSuggestions": [{"title": "Leverage", "url": "https://www.mdcopilot.health/blog/x"}],
            "externalReferences": ["src_1"],
        }
    )
    assert seo.seo_title == "Reading the FDA AI device list"
    assert seo.internal_link_suggestions == [
        c.InternalLink(title="Leverage", url="https://www.mdcopilot.health/blog/x")
    ]
    social = c.SocialCopy.model_validate({"linkedin": "a", "xPost": "b", "newsletterTeaser": "c"})
    assert (social.x_post, social.newsletter_teaser) == ("b", "c")


def test_parses_mixed_case_payload() -> None:
    neighbour = c.NoveltyNeighbour.model_validate({"kind": "external", "refId": "ext_1", "title": "t", "similarity": 0})
    assert neighbour.ref_id == "ext_1"
    source = c.BlogSource.model_validate(
        {"marker": "S2", "sourceId": "src_2", "title": "t", "url": "u", "publisher": "p", "published_at": None}
    )
    assert (source.source_id, source.published_at) == ("src_2", None)


def test_python_constructor_uses_field_names() -> None:
    item = c.ScoreItem(weight=0.1, score=0.2, justification="because")
    assert item.model_dump() == {"weight": 0.1, "score": 0.2, "justification": "because"}


def test_values_are_typed_after_parsing() -> None:
    post = c.GeneratedBlogPost.model_validate(generated_blog_post())
    assert post.status is ArticleStatus.READY_FOR_REVIEW
    assert post.pipeline_status is RunStatus.SUCCEEDED
    assert post.created_at == datetime(2026, 9, 17, 7, 0, tzinfo=UTC)
    assert post.fact_check.claims[0].kind is c.ClaimKind.STATISTIC
    assert post.fact_check.claims[0].verification_status is c.VerificationStatus.SUPPORTED
    assert post.novelty.decision is c.NoveltyDecision.PASS
    candidate = c.TopicCandidate.model_validate(topic_candidate())
    assert candidate.pillar is c.PillarKey.A
    assert candidate.score_breakdown["timeliness"].weight == 0.25
    source = c.ResearchSource.model_validate(research_source())
    assert source.source_type is c.SourceType.GOVERNMENT
    assert c.ResearchFinding.model_validate(research_finding()).claim_type is c.ClaimType.FACT


# --- serialisation ---------------------------------------------------------------------------------------------


def test_generated_blog_post_serialises_camel_case() -> None:
    wire = c.GeneratedBlogPost.model_validate(generated_blog_post()).model_dump(mode="json")
    assert set(wire) == {
        "id",
        "topicId",
        "titleOptions",
        "selectedTitle",
        "slug",
        "contentMarkdown",
        "excerpt",
        "pullQuote",
        "cta",
        "category",
        "tags",
        "seo",
        "social",
        "sources",
        "researchSummary",
        "factCheck",
        "clinicalReview",
        "editorialReview",
        "qualityGates",
        "novelty",
        "status",
        "pipelineStatus",
        "versionNo",
        "createdAt",
        "updatedAt",
    }
    assert set(wire["seo"]) == {
        "seoTitle",
        "metaDescription",
        "slug",
        "primaryKeyword",
        "secondaryKeywords",
        "ogTitle",
        "ogDescription",
        "tags",
        "category",
        "internalLinkSuggestions",
        "externalReferences",
    }
    assert set(wire["social"]) == {"linkedin", "xPost", "newsletterTeaser"}
    assert set(wire["sources"][0]) == {"marker", "sourceId", "title", "url", "publisher", "publishedAt"}
    assert set(wire["factCheck"]) == {"verdict", "independentCheck", "claims"}
    assert set(wire["factCheck"]["claims"][0]) == {
        "claim",
        "kind",
        "importance",
        "sectionKey",
        "sentenceIndex",
        "span",
        "citationMarkers",
        "sourceId",
        "verificationStatus",
        "confidence",
        "recommendedRevision",
    }
    assert set(wire["editorialReview"]) == {
        "editorialScore",
        "strengths",
        "weaknesses",
        "requiredChanges",
        "optionalChanges",
        "finalRecommendation",
    }
    assert set(wire["novelty"]) == {"decision", "maxSimilarity", "neighbours"}
    assert set(wire["novelty"]["neighbours"][0]) == {"kind", "refId", "title", "similarity"}
    assert wire["status"] == "READY_FOR_REVIEW"
    assert wire["pipelineStatus"] == "SUCCEEDED"
    assert wire["createdAt"] == "2026-09-17T07:00:00Z"
    assert wire["factCheck"]["claims"][0]["recommendedRevision"] is None


def test_research_and_topic_contracts_serialise_camel_case() -> None:
    source = c.ResearchSource.model_validate(research_source()).model_dump(mode="json")
    assert set(source) == {
        "id",
        "title",
        "url",
        "canonicalUrl",
        "publisher",
        "domain",
        "publishedAt",
        "dateSource",
        "retrievedAt",
        "sourceType",
        "tier",
        "accessMode",
        "relevanceScore",
    }
    finding = c.ResearchFinding.model_validate(research_finding()).model_dump(mode="json")
    assert {"sourceIds", "claimType"} <= set(finding)
    candidate = c.TopicCandidate.model_validate(topic_candidate()).model_dump(mode="json")
    assert set(candidate) == {
        "topicId",
        "title",
        "hook",
        "whyNow",
        "relevantNews",
        "mdcopilotConnection",
        "targetAudience",
        "pillar",
        "noveltyScore",
        "evidenceScore",
        "businessRelevance",
        "editorialPotential",
        "timelinessScore",
        "audienceRelevance",
        "totalScore",
        "scoreBreakdown",
        "novelty",
        "sources",
        "status",
    }
    assert set(candidate["relevantNews"][0]) == {"title", "url", "publishedAt"}


@pytest.mark.parametrize("model", MODELS)
def test_default_dump_uses_camel_case_everywhere(model: type[c.Contract]) -> None:
    instance = model.model_validate(BUILDERS[model]())
    assert _keys_with_underscores(instance.model_dump(mode="json")) == []
    assert _keys_with_underscores(instance.model_dump()) == []


def test_dict_keys_inside_data_are_not_renamed() -> None:
    data = topic_candidate()
    data["score_breakdown"] = {"mdcopilot_relevance": score_item()}
    wire = c.TopicCandidate.model_validate(data).model_dump(mode="json")
    assert set(wire["scoreBreakdown"]) == {"mdcopilot_relevance"}
    assert set(wire["scoreBreakdown"]["mdcopilot_relevance"]) == {"weight", "score", "justification"}


def test_json_schema_uses_camel_case_and_requires_every_field() -> None:
    schema = c.GeneratedBlogPost.model_json_schema()
    assert {"contentMarkdown", "pipelineStatus", "qualityGates", "versionNo"} <= set(schema["properties"])
    assert set(schema["required"]) == set(schema["properties"])


# --- strictness ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("model", MODELS)
def test_unknown_field_is_rejected(model: type[c.Contract]) -> None:
    data = BUILDERS[model]()
    data["unexpected"] = 1
    with pytest.raises(ValidationError) as caught:
        model.model_validate(data)
    assert [(e["type"], e["loc"]) for e in caught.value.errors()] == [("extra_forbidden", ("unexpected",))]


def test_unknown_nested_field_is_rejected() -> None:
    data = generated_blog_post()
    data["seo"]["unexpected"] = 1
    data["fact_check"]["claims"][0]["articleLocation"] = "evidence:2"
    with pytest.raises(ValidationError) as caught:
        c.GeneratedBlogPost.model_validate(data)
    assert {(e["type"], e["loc"]) for e in caught.value.errors()} == {
        ("extra_forbidden", ("seo", "unexpected")),
        ("extra_forbidden", ("fact_check", "claims", 0, "articleLocation")),
    }


def test_error_location_names_the_key_the_client_sent() -> None:
    snake = claim_check()
    snake["sentence_index"] = -1
    with pytest.raises(ValidationError) as from_snake:
        c.ClaimCheck.model_validate(snake)
    assert [e["loc"] for e in from_snake.value.errors()] == [("sentence_index",)]

    camel = c.ClaimCheck.model_validate(claim_check()).model_dump(mode="json")
    camel["sentenceIndex"] = -1
    with pytest.raises(ValidationError) as from_camel:
        c.ClaimCheck.model_validate(camel)
    assert [e["loc"] for e in from_camel.value.errors()] == [("sentenceIndex",)]

    del camel["sourceId"]
    camel["sentenceIndex"] = 2
    with pytest.raises(ValidationError) as missing:
        c.ClaimCheck.model_validate(camel)
    assert [(e["type"], e["loc"]) for e in missing.value.errors()] == [("missing", ("sourceId",))]


@pytest.mark.parametrize(
    ("model", "field"),
    [
        pytest.param(c.NewsRef, "published_at", id="NewsRef.published_at"),
        pytest.param(c.ResearchSource, "published_at", id="ResearchSource.published_at"),
        pytest.param(c.BlogSource, "published_at", id="BlogSource.published_at"),
        pytest.param(c.ClaimCheck, "source_id", id="ClaimCheck.source_id"),
        pytest.param(c.ClaimCheck, "recommended_revision", id="ClaimCheck.recommended_revision"),
        pytest.param(c.GeneratedBlogPost, "selected_title", id="GeneratedBlogPost.selected_title"),
        pytest.param(c.GeneratedBlogPost, "social", id="GeneratedBlogPost.social"),
        pytest.param(c.PacketStatistic, "as_of", id="PacketStatistic.as_of"),
        pytest.param(c.RevisionFinding, "recommended_revision", id="RevisionFinding.recommended_revision"),
        pytest.param(c.HumanDecision, "mode", id="HumanDecision.mode"),
        pytest.param(c.HumanDecision, "reason", id="HumanDecision.reason"),
    ],
)
def test_nullable_field_accepts_null_but_must_be_present(model: type[c.Contract], field: str) -> None:
    data = BUILDERS[model]()
    data[field] = None
    assert getattr(model.model_validate(data), field) is None
    del data[field]
    with pytest.raises(ValidationError) as caught:
        model.model_validate(data)
    assert [e["type"] for e in caught.value.errors()] == ["missing"]


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        _param(c.ResearchSource, "source_type", "wire_service"),
        _param(c.ResearchSource, "tier", 4),
        _param(c.ResearchSource, "tier", 0),
        _param(c.ResearchSource, "date_source", "guess"),
        _param(c.ResearchSource, "access_mode", "paywalled"),
        _param(c.ResearchSource, "retrieved_at", "yesterday"),
        _param(c.ResearchFinding, "claim_type", "fact"),
        _param(c.ResearchFinding, "importance", "low"),
        _param(c.NoveltyResult, "decision", "REJECT"),
        _param(c.TopicCandidate, "pillar", "F"),
        _param(c.ClaimCheck, "kind", "rumour"),
        _param(c.ClaimCheck, "importance", "critical"),
        _param(c.ClaimCheck, "verification_status", "VERIFIED"),
        _param(c.ClaimCheck, "sentence_index", -1),
        _param(c.FactCheckResult, "verdict", "MAYBE"),
        _param(c.ClinicalFlag, "severity", "blocking"),
        _param(c.GateResult, "severity", "BLOCKING"),
        _param(c.GeneratedBlogPost, "status", "DONE"),
        _param(c.GeneratedBlogPost, "pipeline_status", "DRAFTING"),
        _param(c.GeneratedBlogPost, "version_no", 0),
        _param(c.SourceRef, "marker", "S0"),
        _param(c.PacketFact, "importance", "urgent"),
        _param(c.FindingResolution, "action", "ignored"),
        _param(c.RevisionFinding, "origin", "reader"),
        _param(c.HumanDecision, "decision", "MAYBE"),
        _param(c.TopicCandidate, "status", "BOGUS"),
    ],
)
def test_invalid_value_is_rejected(model: type[c.Contract], field: str, value: object) -> None:
    data = BUILDERS[model]()
    data[field] = value
    with pytest.raises(ValidationError) as caught:
        model.model_validate(data)
    assert {e["loc"][0] for e in caught.value.errors()} == {field}


# --- 0..1 bounds -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("model", "field", "value"), [_param(m, f, v) for m, f in BOUNDED for v in (0, 0.5, 1)])
def test_bounded_field_accepts_values_in_range(model: type[c.Contract], field: str, value: float) -> None:
    data = BUILDERS[model]()
    data[field] = value
    assert getattr(model.model_validate(data), field) == value


@pytest.mark.parametrize(
    ("model", "field", "value", "error_type"),
    [
        pytest.param(m, f, v, t, id=f"{m.__name__}.{f}={v}")
        for m, f in BOUNDED
        for v, t in ((-0.01, "greater_than_equal"), (1.01, "less_than_equal"))
    ],
)
def test_bounded_field_rejects_values_out_of_range(
    model: type[c.Contract], field: str, value: float, error_type: str
) -> None:
    snake = BUILDERS[model]()
    snake[field] = value
    with pytest.raises(ValidationError) as from_snake:
        model.model_validate(snake)
    assert [(e["type"], e["loc"]) for e in from_snake.value.errors()] == [(error_type, (field,))]

    alias = model.model_fields[field].alias
    assert alias is not None
    camel = model.model_validate(BUILDERS[model]()).model_dump(mode="json")
    camel[alias] = value
    with pytest.raises(ValidationError) as from_camel:
        model.model_validate(camel)
    assert [(e["type"], e["loc"]) for e in from_camel.value.errors()] == [(error_type, (alias,))]


@pytest.mark.parametrize("model", MODELS)
def test_every_float_field_is_bounded_to_unit_interval(model: type[c.Contract]) -> None:
    properties = model.model_json_schema()["properties"]
    float_fields = {name for name, info in model.model_fields.items() if info.annotation is float}
    assert float_fields == {field for m, field in BOUNDED if m is model}
    for name in float_fields:
        prop = properties[model.model_fields[name].alias]
        assert (prop["type"], prop["minimum"], prop["maximum"]) == ("number", 0, 1)


# --- Phase 2-10 additions ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["S1", "S10", "S999"])
def test_marker_pattern_accepts(value: str) -> None:
    assert c.SourceRef(marker=value, source_id="x").marker == value


@pytest.mark.parametrize("value", ["S0", "s1", "S01", "S", "[S1]"])
def test_marker_pattern_rejects(value: str) -> None:
    with pytest.raises(ValidationError) as caught:
        c.SourceRef(marker=value, source_id="x")
    assert {e["loc"][0] for e in caught.value.errors()} == {"marker"}


def test_article_section_heading_rule() -> None:
    with pytest.raises(ValidationError):
        c.ArticleSection(key="introduction", heading="X", body_markdown="Body.")
    with pytest.raises(ValidationError):
        c.ArticleSection(key="context", heading=None, body_markdown="Body.")
    assert c.ArticleSection(key="context", heading="Context", body_markdown="Body.").heading == "Context"
    assert c.ArticleSection(key="introduction", heading=None, body_markdown="Body.").heading is None


@pytest.mark.parametrize("body", ["Line one\n# Title", "Text\n## Sub\nMore"])
def test_article_section_body_rejects_headings(body: str) -> None:
    with pytest.raises(ValidationError) as caught:
        c.ArticleSection(key="context", heading="Context", body_markdown=body)
    assert "body_markdown must not contain headings" in str(caught.value)


def test_article_section_body_accepts_hashtag_words() -> None:
    section = c.ArticleSection(key="context", heading="Context", body_markdown="Text with #hashtag")
    assert section.body_markdown == "Text with #hashtag"


def test_article_draft_section_order() -> None:
    draft = c.ArticleDraft.model_validate(article_draft())
    assert [section.key.value for section in draft.sections] == [key.value for key in c.SECTION_ORDER]

    data = article_draft()
    data["sections"][1], data["sections"][2] = data["sections"][2], data["sections"][1]
    with pytest.raises(ValidationError) as caught:
        c.ArticleDraft.model_validate(data)
    assert "SECTION_ORDER" in str(caught.value)

    data = article_draft()
    data["sections"] = data["sections"][:6]
    with pytest.raises(ValidationError):
        c.ArticleDraft.model_validate(data)


def test_article_draft_excerpt_limit() -> None:
    data = article_draft()
    data["excerpt"] = "x" * 500
    assert c.ArticleDraft.model_validate(data).excerpt == "x" * 500
    data["excerpt"] = "x" * 501
    with pytest.raises(ValidationError):
        c.ArticleDraft.model_validate(data)


@pytest.mark.parametrize(
    ("component", "field"),
    [
        ("headline", "title_options"),
        ("introduction", "section"),
        ("section", "section"),
        ("pull_quote", "pull_quote"),
        ("cta", "cta"),
    ],
)
def test_component_draft_field_rule(component: str, field: str) -> None:
    data = component_draft()
    data["component"] = component
    data["section_key"] = None
    data["title_options"] = None
    data["section"] = None
    data["pull_quote"] = None
    data["cta"] = None
    data[field] = title_options() if field == "title_options" else (
        article_section() if field == "section" else "Draft text."
    )
    assert getattr(c.ComponentDraft.model_validate(data), field) is not None

    extra = "cta" if field != "cta" else "pull_quote"
    data[extra] = "Extra."
    with pytest.raises(ValidationError):
        c.ComponentDraft.model_validate(data)

    data = component_draft()
    data["component"] = component
    data["section_key"] = None
    data["title_options"] = None
    data["section"] = None
    data["pull_quote"] = None
    data["cta"] = None
    with pytest.raises(ValidationError):
        c.ComponentDraft.model_validate(data)


@pytest.mark.parametrize("component", ["article", "research"])
def test_component_draft_rejects_whole_article_components(component: str) -> None:
    data = component_draft()
    data["component"] = component
    with pytest.raises(ValidationError) as caught:
        c.ComponentDraft.model_validate(data)
    assert "no draft field" in str(caught.value)


def test_section_order_constant() -> None:
    assert c.SECTION_ORDER == tuple(c.SectionKey)
    assert len(c.SECTION_ORDER) == 7
