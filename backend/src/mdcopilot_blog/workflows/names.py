"""Names shared by the api (enqueue by name) and the worker (registration). Never rename without a migration plan."""

from pathlib import Path

# Workflows
WORKFLOW_HELLO = "hello_pipeline"
WORKFLOW_DAILY_TRIGGER = "daily_trigger"

# Queues (registered by the worker after DBOS.launch())
QUEUE_PIPELINE = "pipeline"
QUEUE_INTERACTIVE = "interactive"

# Schedules
SCHEDULE_DAILY = "daily_generation"

# hello_pipeline steps
STEP_HELLO_OPEN = "hello.open_attempt"
STEP_HELLO_ECHO = "hello.echo"
STEP_HELLO_FINISH = "hello.finish"
STEP_HELLO_FAIL = "hello.mark_failed"

# daily_trigger steps
STEP_DAILY_CREATE_RUN = "daily.create_run"

# Phase 3 switches this to discover_topics
DAILY_TARGET_WORKFLOW = WORKFLOW_HELLO

# Touched by the worker every 10 s; the compose healthcheck reads its mtime. Container-local, not shared.
HEARTBEAT_FILE = Path("/tmp/worker-heartbeat")
