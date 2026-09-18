"""Names shared by the api (enqueue by name) and the worker (registration). Never rename without a migration plan."""

from pathlib import Path

# Workflows
WORKFLOW_DAILY_TRIGGER = "daily_trigger"
WORKFLOW_DISCOVER_TOPICS = "discover_topics"
WORKFLOW_PRODUCE_ARTICLE = "produce_article"
WORKFLOW_CHANGE_TOPIC = "change_topic"
WORKFLOW_REGENERATE_TOPICS = "regenerate_topics"
WORKFLOW_REGENERATE_COMPONENT = "regenerate_component"
WORKFLOW_REGENERATE_ARTICLE = "regenerate_article"
WORKFLOW_REGENERATE_RESEARCH = "regenerate_research"
WORKFLOW_RECHECK_ARTICLE = "recheck_article"
WORKFLOW_PUBLISH_ARTICLE = "publish_article"
WORKFLOW_APPLY_SCHEDULE = "apply_schedule"
WORKFLOW_CONTROL = "control"
WORKFLOW_PUBLISH_DUE = "publish_due"
WORKFLOW_MAINTENANCE = "maintenance"

# Queues (registered by the worker after DBOS.launch())
QUEUE_PIPELINE = "pipeline"
QUEUE_INTERACTIVE = "interactive"

# Schedules
SCHEDULE_DAILY = "daily_generation"
SCHEDULE_PUBLISH_DUE = "publish_due"
SCHEDULE_MAINTENANCE = "maintenance_nightly"

# Workflows whose calls are capped per attempt, not per run.
HUMAN_ACTION_WORKFLOWS: frozenset[str] = frozenset(
    {
        WORKFLOW_REGENERATE_COMPONENT,
        WORKFLOW_REGENERATE_ARTICLE,
        WORKFLOW_REGENERATE_RESEARCH,
        WORKFLOW_RECHECK_ARTICLE,
        WORKFLOW_PUBLISH_ARTICLE,
    }
)

# daily_trigger steps
STEP_DAILY_CREATE_RUN = "daily.create_run"

# Touched by the worker every 10 s; the compose healthcheck reads its mtime. Container-local, not shared.
HEARTBEAT_FILE = Path("/tmp/worker-heartbeat")

# Registered step names used by workflow execution and retry controls.
STAGES: dict[str, list[str]] = {
    "discover": [
        "open_attempt",
        "manual_topic",
        "gather_signals",
        "build_ledger",
        "synthesize_research",
        "ideate_topics",
        "check_novelty_and_score",
        "select_topic",
        "finish",
        "mark_failed",
    ],
    "produce": [
        "open_attempt",
        "deep_research",
        "build_research_packet",
        "write_draft",
        "fact_check",
        "clinical_review",
        "editorial_review",
        "revise",
        "verify_facts",
        "seo",
        "quality_gates",
        "fix_pass.revise",
        "fix_pass.verify_facts",
        "fix_pass.seo",
        "fix_pass.quality_gates",
        "finish",
        "mark_failed",
    ],
    "change_topic": [
        "open_attempt",
        "supersede",
        "deep_research",
        "build_research_packet",
        "write_draft",
        "fact_check",
        "clinical_review",
        "editorial_review",
        "revise",
        "verify_facts",
        "seo",
        "quality_gates",
        "fix_pass.revise",
        "fix_pass.verify_facts",
        "fix_pass.seo",
        "fix_pass.quality_gates",
        "finish",
        "mark_failed",
    ],
    "regenerate_topics": [
        "open_attempt",
        "ideate_topics",
        "check_novelty_and_score",
        "select_topic",
        "finish",
        "mark_failed",
    ],
    "regenerate_component": [
        "open_attempt",
        "write_component",
        "fact_check",
        "seo",
        "quality_gates",
        "fix_pass.revise",
        "fix_pass.verify_facts",
        "fix_pass.seo",
        "fix_pass.quality_gates",
        "finish",
        "mark_failed",
    ],
    "regenerate_article": [
        "open_attempt",
        "write_draft",
        "fact_check",
        "clinical_review",
        "editorial_review",
        "revise",
        "verify_facts",
        "seo",
        "quality_gates",
        "fix_pass.revise",
        "fix_pass.verify_facts",
        "fix_pass.seo",
        "fix_pass.quality_gates",
        "finish",
        "mark_failed",
    ],
    "regenerate_research": [
        "open_attempt",
        "deep_research",
        "build_research_packet",
        "write_draft",
        "fact_check",
        "clinical_review",
        "editorial_review",
        "revise",
        "verify_facts",
        "seo",
        "quality_gates",
        "fix_pass.revise",
        "fix_pass.verify_facts",
        "fix_pass.seo",
        "fix_pass.quality_gates",
        "finish",
        "mark_failed",
    ],
    "recheck": ["open_attempt", "fact_check", "quality_gates", "finish", "mark_failed"],
    "publish": ["open_attempt", "publish", "finish", "mark_failed"],
    "publish_due": ["select_due", "process_due"],
    "maintenance": ["sync_posts", "prune_dbos", "feed_health"],
    "apply_schedule": ["apply"],
    "control": ["control"],
}

KNOWN_STEP_NAMES = frozenset(f"{prefix}.{stage}" for prefix, stages in STAGES.items() for stage in stages)
