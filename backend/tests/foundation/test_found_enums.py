import pytest

from mdcopilot_blog.domain import enums

VALUE_LISTS: dict[str, list[str]] = {
    "CandidateStatus": ["PROPOSED", "PASSED", "WARNED", "REJECTED", "SELECTED", "DISMISSED", "SUPERSEDED"],
    "ResearchRunKind": ["broad", "deep", "verification"],
    "ResearchRunStatus": ["running", "succeeded", "partial", "insufficient_evidence", "failed"],
    "AccessMode": ["full_text", "abstract_only", "metadata_only"],
    "DateSource": ["feed", "api", "jsonld", "meta", "htmldate", "none"],
    "FetchStatus": ["ok", "blocked", "robots_disallowed", "error", "not_fetched"],
    "DiscoveredVia": ["feed", "pubmed", "federal_register", "fda_csv", "search", "deep_search", "verification"],
    "FeedKind": ["rss", "atom", "pubmed", "federal_register", "fda_ai_devices_csv"],
    "ReviewKind": ["fact_check", "clinical", "editorial", "quality_gate", "human"],
    "ReviewVerdict": [
        "PASS",
        "FAIL",
        "CLEAR",
        "BLOCKED",
        "COMPLETED",
        "PASSED",
        "FAILED",
        "APPROVED",
        "OVERRIDE_APPROVED",
        "REJECTED",
    ],
    "GateRunKind": ["full", "fix_pass", "deterministic", "recheck"],
    "ChangeKind": ["draft", "revision", "fix_pass", "human_edit", "component_regeneration", "article_regeneration"],
    "SectionKey": [
        "introduction",
        "context",
        "core_argument",
        "evidence",
        "mdcopilot_perspective",
        "practical_implications",
        "conclusion",
    ],
    "ArticleComponent": ["headline", "introduction", "section", "pull_quote", "cta", "article", "research"],
    "TitleKey": ["provocative", "operational", "visionary", "custom"],
    "ApprovalMode": ["draft", "publish"],
    "PublisherKey": ["manual_export", "mdcopilot_api", "null"],
    "SlotStatus": ["planned", "cancelled"],
    "NotificationKind": [
        "ready_for_review",
        "quality_gate_failed",
        "run_failed",
        "publish_failed",
        "scheduled_export_due",
        "daily_run_skipped",
    ],
    "HeadlinePattern": [
        "question",
        "how_to",
        "why",
        "what_if",
        "number_list",
        "colon_split",
        "versus",
        "imperative",
        "statement",
    ],
    "ClinicalFlagCode": [
        "medical_advice",
        "autonomous_clinical_decision",
        "misinformation",
        "invented_anecdote",
        "invented_physician_experience",
        "safety_framing",
        "other",
    ],
    "GateId": [
        "sources_present",
        "claims_verified",
        "no_unsupported_statistics",
        "no_fabricated_quotes",
        "no_unsourced_anecdotes",
        "no_duplicate_topic",
        "word_count",
        "required_structure",
        "cta_fresh",
        "no_prohibited_language",
        "seo_complete",
        "fact_check_passed",
        "clinical_clear",
        "editorial_completed",
        "disclosure_present",
        "independent_fact_check",
        "opening_diversity",
        "headline_diversity",
        "source_domain_diversity",
    ],
}

ALL_ENUMS = tuple(getattr(enums, name) for name in VALUE_LISTS)


@pytest.mark.parametrize("name", list(VALUE_LISTS))
def test_enum_values(name: str) -> None:
    enum = getattr(enums, name)
    assert [m.value for m in enum] == VALUE_LISTS[name]


@pytest.mark.parametrize("name", list(VALUE_LISTS))
def test_member_names_are_upper_case_values(name: str) -> None:
    enum = getattr(enums, name)
    assert all(m.name == m.value.upper() for m in enum)


def test_phase1_enums_unchanged() -> None:
    assert [v.value for v in enums.ArticleStatus] == [
        "DRAFTING",
        "FACT_CHECKING",
        "CLINICAL_REVIEW",
        "EDITORIAL_REVIEW",
        "SEO",
        "READY_FOR_REVIEW",
        "QUALITY_GATE_FAILED",
        "APPROVED",
        "SCHEDULED",
        "EXPORTED",
        "PUBLISHING",
        "PUBLISHED",
        "PUBLISH_FAILED",
        "REJECTED",
        "FAILED",
        "SUPERSEDED",
    ]
    assert [v.value for v in enums.AgentName][-1] == "hello"
