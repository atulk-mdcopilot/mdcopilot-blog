"""Domain enumerations.

The values are the stored and wire representation: status columns are ``String(32)`` holding ``.value``.
Member names are UPPER_CASE for every enum; values keep the case shown here.
"""

from enum import StrEnum


class RunStatus(StrEnum):
    """``blog_runs.status``."""

    QUEUED = "QUEUED"
    RESEARCHING = "RESEARCHING"
    TOPICS_READY = "TOPICS_READY"
    PRODUCING = "PRODUCING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptStatus(StrEnum):
    """``blog_run_attempts.status``: one DBOS execution of a run."""

    ENQUEUED = "ENQUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(StrEnum):
    """``blog_agent_runs.status``: one execution of one workflow step."""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ArticleStatus(StrEnum):
    """``blog_articles.status``."""

    DRAFTING = "DRAFTING"
    FACT_CHECKING = "FACT_CHECKING"
    CLINICAL_REVIEW = "CLINICAL_REVIEW"
    EDITORIAL_REVIEW = "EDITORIAL_REVIEW"
    SEO = "SEO"
    DRAFT_SAVED = "DRAFT_SAVED"
    FAILED = "FAILED"


class CallKind(StrEnum):
    """``blog_llm_calls.kind``."""

    AGENT = "agent"
    SEARCH = "search"


class CallStatus(StrEnum):
    """``blog_llm_calls.status``."""

    OK = "ok"
    ERROR = "error"


class AgentName(StrEnum):
    """Route keys for the LLM gateway."""

    SEARCH = "search"
    DEEP_RESEARCH = "deep_research"
    WRITER = "writer"
    FACT_CHECK = "fact_check"
    CLINICAL = "clinical"
    EDITORIAL = "editorial"
    SEO = "seo"


class ResearchRunKind(StrEnum):
    """``blog_research_runs.kind``."""

    DEEP = "deep"
    VERIFICATION = "verification"


class ResearchRunStatus(StrEnum):
    """``blog_research_runs.status``."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"


class AccessMode(StrEnum):
    """``blog_sources.access_mode``."""

    FULL_TEXT = "full_text"
    ABSTRACT_ONLY = "abstract_only"
    METADATA_ONLY = "metadata_only"


class DateSource(StrEnum):
    """``blog_sources.date_source``: where the publication date came from."""

    API = "api"
    JSONLD = "jsonld"
    META = "meta"
    HTMLDATE = "htmldate"
    NONE = "none"


class FetchStatus(StrEnum):
    """``blog_sources.fetch_status``."""

    OK = "ok"
    BLOCKED = "blocked"
    ROBOTS_DISALLOWED = "robots_disallowed"
    ERROR = "error"
    NOT_FETCHED = "not_fetched"


class DiscoveredVia(StrEnum):
    """``blog_sources.discovered_via``."""

    DEEP_SEARCH = "deep_search"
    VERIFICATION = "verification"


class ReviewVerdict(StrEnum):
    """``blog_reviews.verdict``."""

    PASS = "PASS"
    FAIL = "FAIL"
    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    PASSED = "PASSED"
    FAILED = "FAILED"


class GateRunKind(StrEnum):
    """``blog_reviews.gate_run_kind``."""

    FULL = "full"
    FIX_PASS = "fix_pass"


class ChangeKind(StrEnum):
    """``blog_article_versions.change_kind``."""

    DRAFT = "draft"
    REVISION = "revision"
    FIX_PASS = "fix_pass"


class SectionKey(StrEnum):
    """The seven article sections, in assembly order."""

    INTRODUCTION = "introduction"
    CONTEXT = "context"
    CORE_ARGUMENT = "core_argument"
    EVIDENCE = "evidence"
    MDCOPILOT_PERSPECTIVE = "mdcopilot_perspective"
    PRACTICAL_IMPLICATIONS = "practical_implications"
    CONCLUSION = "conclusion"


class ClinicalFlagCode(StrEnum):
    """``ClinicalFlag.code`` values."""

    MEDICAL_ADVICE = "medical_advice"
    AUTONOMOUS_CLINICAL_DECISION = "autonomous_clinical_decision"
    MISINFORMATION = "misinformation"
    INVENTED_ANECDOTE = "invented_anecdote"
    INVENTED_PHYSICIAN_EXPERIENCE = "invented_physician_experience"
    SAFETY_FRAMING = "safety_framing"
    OTHER = "other"


class GateId(StrEnum):
    """Quality gates in display order. Severity is set in ``domain.gates.WARNING_GATES``, not by position."""

    SOURCES_PRESENT = "sources_present"
    CLAIMS_VERIFIED = "claims_verified"
    NO_UNSUPPORTED_STATISTICS = "no_unsupported_statistics"
    NO_FABRICATED_QUOTES = "no_fabricated_quotes"
    NO_UNSOURCED_ANECDOTES = "no_unsourced_anecdotes"
    WORD_COUNT = "word_count"
    REQUIRED_STRUCTURE = "required_structure"
    NO_PROHIBITED_LANGUAGE = "no_prohibited_language"
    SEO_COMPLETE = "seo_complete"
    FACT_CHECK_PASSED = "fact_check_passed"
    CLINICAL_CLEAR = "clinical_clear"
    EDITORIAL_COMPLETED = "editorial_completed"
    DISCLOSURE_PRESENT = "disclosure_present"
    INDEPENDENT_FACT_CHECK = "independent_fact_check"
