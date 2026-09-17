"""Domain enumerations.

The values are the stored and wire representation: status columns are ``String(32)`` holding ``.value``,
and the frontend mirrors the ``Role`` and ``Permission`` values in ``src/features/auth/permissions.ts``.
Member names are UPPER_CASE for every enum; values keep the case shown here.
"""

from enum import StrEnum


class Role(StrEnum):
    """User roles, least to most privileged (ARCHITECTURE §17)."""

    VIEWER = "viewer"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    PUBLISHER = "publisher"
    ADMIN = "admin"


class Permission(StrEnum):
    """Permissions checked by the API (ARCHITECTURE §17)."""

    VIEW = "blog.view"
    GENERATE = "blog.generate"
    EDIT = "blog.edit"
    REVIEW = "blog.review"
    APPROVE = "blog.approve"
    SCHEDULE = "blog.schedule"
    PUBLISH = "blog.publish"
    AGENT_RUNS = "blog.agent_runs"
    SETTINGS = "blog.settings"


class RunKind(StrEnum):
    """How a run was started."""

    DAILY = "daily"
    MANUAL = "manual"


class RunStatus(StrEnum):
    """``blog_runs.status`` (ARCHITECTURE §6)."""

    QUEUED = "QUEUED"
    RESEARCHING = "RESEARCHING"
    TOPICS_READY = "TOPICS_READY"
    WAITING_FOR_TOPIC = "WAITING_FOR_TOPIC"
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
    """``blog_articles.status`` (ARCHITECTURE §6, §6.1)."""

    DRAFTING = "DRAFTING"
    FACT_CHECKING = "FACT_CHECKING"
    CLINICAL_REVIEW = "CLINICAL_REVIEW"
    EDITORIAL_REVIEW = "EDITORIAL_REVIEW"
    SEO = "SEO"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    QUALITY_GATE_FAILED = "QUALITY_GATE_FAILED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    EXPORTED = "EXPORTED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    PUBLISH_FAILED = "PUBLISH_FAILED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class PublicationStatus(StrEnum):
    """``blog_publications.status`` (ARCHITECTURE §6, §14)."""

    PENDING = "PENDING"
    EXPORTED = "EXPORTED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class CallKind(StrEnum):
    """``blog_llm_calls.kind``."""

    AGENT = "agent"
    SEARCH = "search"
    EMBEDDING = "embedding"


class CallStatus(StrEnum):
    """``blog_llm_calls.status``."""

    OK = "ok"
    ERROR = "error"


class AgentName(StrEnum):
    """Route keys for the LLM gateway; ``HELLO`` is the Phase 1 mock agent."""

    SEARCH = "search"
    RESEARCH = "research"
    IDEATION = "ideation"
    DEEP_RESEARCH = "deep_research"
    WRITER = "writer"
    FACT_CHECK = "fact_check"
    CLINICAL = "clinical"
    EDITORIAL = "editorial"
    SEO = "seo"
    HELLO = "hello"


class CandidateStatus(StrEnum):
    """``blog_topic_candidates.status``."""

    PROPOSED = "PROPOSED"
    PASSED = "PASSED"
    WARNED = "WARNED"
    REJECTED = "REJECTED"
    SELECTED = "SELECTED"
    DISMISSED = "DISMISSED"
    SUPERSEDED = "SUPERSEDED"


class ResearchRunKind(StrEnum):
    """``blog_research_runs.kind``."""

    BROAD = "broad"
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

    FEED = "feed"
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

    FEED = "feed"
    PUBMED = "pubmed"
    FEDERAL_REGISTER = "federal_register"
    FDA_CSV = "fda_csv"
    SEARCH = "search"
    DEEP_SEARCH = "deep_search"
    VERIFICATION = "verification"


class FeedKind(StrEnum):
    """``blog_source_feeds.kind``."""

    RSS = "rss"
    ATOM = "atom"
    PUBMED = "pubmed"
    FEDERAL_REGISTER = "federal_register"
    FDA_AI_DEVICES_CSV = "fda_ai_devices_csv"


class ReviewKind(StrEnum):
    """``blog_reviews.kind``."""

    FACT_CHECK = "fact_check"
    CLINICAL = "clinical"
    EDITORIAL = "editorial"
    QUALITY_GATE = "quality_gate"
    HUMAN = "human"


class ReviewVerdict(StrEnum):
    """``blog_reviews.verdict``."""

    PASS = "PASS"
    FAIL = "FAIL"
    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    APPROVED = "APPROVED"
    OVERRIDE_APPROVED = "OVERRIDE_APPROVED"
    REJECTED = "REJECTED"


class GateRunKind(StrEnum):
    """``blog_reviews.gate_run_kind``."""

    FULL = "full"
    FIX_PASS = "fix_pass"
    DETERMINISTIC = "deterministic"
    RECHECK = "recheck"


class ChangeKind(StrEnum):
    """``blog_article_versions.change_kind``."""

    DRAFT = "draft"
    REVISION = "revision"
    FIX_PASS = "fix_pass"
    HUMAN_EDIT = "human_edit"
    COMPONENT_REGENERATION = "component_regeneration"
    ARTICLE_REGENERATION = "article_regeneration"


class SectionKey(StrEnum):
    """The seven article sections, in assembly order."""

    INTRODUCTION = "introduction"
    CONTEXT = "context"
    CORE_ARGUMENT = "core_argument"
    EVIDENCE = "evidence"
    MDCOPILOT_PERSPECTIVE = "mdcopilot_perspective"
    PRACTICAL_IMPLICATIONS = "practical_implications"
    CONCLUSION = "conclusion"


class ArticleComponent(StrEnum):
    """Regenerable parts of an article."""

    HEADLINE = "headline"
    INTRODUCTION = "introduction"
    SECTION = "section"
    PULL_QUOTE = "pull_quote"
    CTA = "cta"
    ARTICLE = "article"
    RESEARCH = "research"


class TitleKey(StrEnum):
    """Keys of ``TitleOptions``."""

    PROVOCATIVE = "provocative"
    OPERATIONAL = "operational"
    VISIONARY = "visionary"
    CUSTOM = "custom"


class ApprovalMode(StrEnum):
    """``blog_articles.approval_mode``."""

    DRAFT = "draft"
    PUBLISH = "publish"


class PublisherKey(StrEnum):
    """``BLOG_PUBLISHER`` values."""

    MANUAL_EXPORT = "manual_export"
    MDCOPILOT_API = "mdcopilot_api"
    NULL = "null"


class SlotStatus(StrEnum):
    """``blog_calendar_slots.status``."""

    PLANNED = "planned"
    CANCELLED = "cancelled"


class NotificationKind(StrEnum):
    """``blog_notifications.kind``."""

    READY_FOR_REVIEW = "ready_for_review"
    QUALITY_GATE_FAILED = "quality_gate_failed"
    RUN_FAILED = "run_failed"
    PUBLISH_FAILED = "publish_failed"
    SCHEDULED_EXPORT_DUE = "scheduled_export_due"
    DAILY_RUN_SKIPPED = "daily_run_skipped"


class HeadlinePattern(StrEnum):
    """``blog_version_features.headline_pattern``."""

    QUESTION = "question"
    HOW_TO = "how_to"
    WHY = "why"
    WHAT_IF = "what_if"
    NUMBER_LIST = "number_list"
    COLON_SPLIT = "colon_split"
    VERSUS = "versus"
    IMPERATIVE = "imperative"
    STATEMENT = "statement"


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
    """Quality gates in display order (first 15 blocking, last 4 warnings)."""

    SOURCES_PRESENT = "sources_present"
    CLAIMS_VERIFIED = "claims_verified"
    NO_UNSUPPORTED_STATISTICS = "no_unsupported_statistics"
    NO_FABRICATED_QUOTES = "no_fabricated_quotes"
    NO_UNSOURCED_ANECDOTES = "no_unsourced_anecdotes"
    NO_DUPLICATE_TOPIC = "no_duplicate_topic"
    WORD_COUNT = "word_count"
    REQUIRED_STRUCTURE = "required_structure"
    CTA_FRESH = "cta_fresh"
    NO_PROHIBITED_LANGUAGE = "no_prohibited_language"
    SEO_COMPLETE = "seo_complete"
    FACT_CHECK_PASSED = "fact_check_passed"
    CLINICAL_CLEAR = "clinical_clear"
    EDITORIAL_COMPLETED = "editorial_completed"
    DISCLOSURE_PRESENT = "disclosure_present"
    INDEPENDENT_FACT_CHECK = "independent_fact_check"
    OPENING_DIVERSITY = "opening_diversity"
    HEADLINE_DIVERSITY = "headline_diversity"
    SOURCE_DOMAIN_DIVERSITY = "source_domain_diversity"
