"""Names shared by the api (enqueue by name) and the worker (registration)."""

from pathlib import Path

# Workflows
WORKFLOW_DISCOVER_TOPICS = "discover_topics"
WORKFLOW_PRODUCE_ARTICLE = "produce_article"

# Queue (registered by the worker after DBOS.launch())
QUEUE_PIPELINE = "pipeline"

# Touched by the worker every 10 s; the compose healthcheck reads its mtime. Container-local, not shared.
HEARTBEAT_FILE = Path("/tmp/worker-heartbeat")

# Registered step names; tracked_stage rejects any other name.
STAGES: dict[str, list[str]] = {
    "discover": [
        "open_attempt",
        "manual_topic",
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
        "push_draft",
        "mark_failed",
    ],
}

KNOWN_STEP_NAMES = frozenset(f"{prefix}.{stage}" for prefix, stages in STAGES.items() for stage in stages)
