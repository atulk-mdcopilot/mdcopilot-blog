# Track INT: Automation and integration — implementation plan

Status: plan, 2026-09-17. Binding contract: `docs/blog-agent/plans/phases-2-10/CONTRACT.md` (the contract wins on any disagreement). All paths are relative to `mdcopilot-blog/`; `pkg/` = `backend/src/mdcopilot_blog/`.

## Header

**Goal.** Wire the eight parallel tracks into running DBOS workflows: `discover_topics`, `produce_article` (with the one fix pass), every human-action workflow, the daily/publish-due/maintenance schedules, `apply_schedule`, `control`, run restart/resume/step retry, in-app and webhook notifications, the end-to-end mock daily run (< 60 s to `READY_FOR_REVIEW`), the kill-and-resume acceptance script, the Playwright review smoke test, and the live-validation tooling (paid runs only in W5 after a `Live-go:` line).

**Spec sections implemented.** ARCHITECTURE §5 (5.1–5.5), §6 (run/article transitions as used by workflows), §13 (Agent Runs actions: retry, restart-from, restart, cancel), §18 (step spans, one trace per run), §20 (workflow and failure tests), §21–§22 (measured values, after validation runs); IMPLEMENTATION_PLAN Phase 8 (all bullets) and the INT rows of Phases 2–7 and 9 (CONTRACT §10); CONTRACT §4.1, §4.11, §5.5 (step body rules), §5.6 (seam callers), §5.7 (all), §9 (INT gates), Rules A–C.

**Owned files (CONTRACT §2.3).**

| Path | Notes |
|---|---|
| `pkg/workflows/discover.py`, `produce.py`, `human_actions.py`, `publish_due.py`, `maintenance.py`, `control.py`, `retry.py`, `validation.py` | new |
| `pkg/workflows/schedules.py`, `client.py`, `tracking.py`, `runtime.py`, `hello.py` | Phase 1 files |
| `pkg/worker.py` | registers new workflows, queues, schedules |
| `pkg/services/runs.py`, `pkg/api/routers/runs.py` | Phase 1 files |
| `pkg/services/notifications.py`, `pkg/api/routers/notifications.py`, `pkg/api/schemas_notifications.py` | router/schema stub by FOUND |
| `backend/tests/integration/**`, `backend/tests/workflows/**`, `backend/tests/api/test_runs_api.py`, `backend/tests/db/test_runs_service.py` | |
| `scripts/acceptance/phase2-9.sh`, `scripts/e2e/**` | INT container rules (CONTRACT §2.3) |
| `scripts/validation/**` | live validation tooling |
| `docs/blog-agent/LOCAL_DEVELOPMENT.md` | Phase 2–9 sections; links `PUBLISHING_MANUAL_CHECK.md` |
| `docs/blog-agent/ARCHITECTURE.md` §21–§22 | measured values after validation runs only |
| `docs/blog-agent/plans/phases-2-10/int.md` | this plan (written at `INT.md`, see open questions) |
| `.superpowers/sdd/phases-2-10/requests/int.md` | `Request:` and `Live:` lines |

**Edits INT makes to files it may edit (CONTRACT §2.4), and nothing else:**
- `pkg/workflows/names.py`: only the line `DAILY_TARGET_WORKFLOW = WORKFLOW_DISCOVER_TOPICS` (INT-7).
- `pkg/api/app.py`: lifespan calls `tracing.configure_tracing(settings, service_name="api")` (INT-9).
- `pkg/api/schemas.py`: `RunDetail` v2 fields `error`, `article_ids`, `research_run_ids` (INT-8).
- `.env.example`: the kill-switch comment line above `BLOG_AGENT_ENABLED` (INT-13).
- `pkg/services/articles.py`, `topics.py`, `quality.py`, `publications.py`, `admin_config.py`: no edit planned. INT-10's wiring test proves each API action already enqueues the §5.7 workflow; if one does not, INT makes the one-line replacement and appends it to the "Edits log" at the end of this file.
- `pkg/cli.py`, `pkg/db/seed.py`, `compose.yaml`, `pkg/settings.py`, `pkg/domain/state_machine.py`: no edit planned (every transition INT uses already exists after FOUND; checked against `_RUN`/`_ARTICLE` plus FOUND's three edges).

**Extension points consumed (exact names).**
- FOUND services: `services.step_context.StepContext`, `build_step_context(*, settings, sessionmaker, gateway, prompts, call)`; `services.article_status.set_article_status(db, *, article_id, target)`, `set_article_status_committed(sessionmaker, *, article_id, target)`; `services.config.load_effective_config(db, settings, *, run_id=None)`, `load_brand_profile(db)`, `pillar_for_date(db, day)`, `local_date(now, timezone)`, `ConfigError`; `services.enqueue.enqueue_workflow(client, *, workflow_name, queue_name, workflow_id, args, timeout_seconds)`, `ensure_agent_enabled(settings)`; `services.audit.audit(db, *, actor_user_id, action, entity_type, entity_id, reason, details)`.
- FOUND domain: `domain.config.ScheduleConfig`, `EffectiveConfig` (`schedule`, `topic_selection_mode`, `novelty.max_regeneration_rounds`); `domain.enums` (`ArticleStatus`, `RunStatus`, `AttemptStatus`, `StepStatus`, `CandidateStatus`, `GateRunKind`, `ChangeKind`, `ArticleComponent`, `SectionKey`, `NotificationKind`, `PublicationStatus`, `Permission`, `Role`, `ResearchRunKind`, `AgentName`); `domain.contracts.PillarKey`, `RevisionFinding`, `GateReport`; `domain.fix_pass.FixPassDecision`, `decide_fix_pass`; `domain.errors.InsufficientEvidence`, `PublishingDisabled`; `domain.state_machine.Entity`, `InvalidTransition`, `can_transition`, `require_transition`; `domain.rbac.permissions_for`.
- FOUND names (`pkg/workflows/names.py`): every `WORKFLOW_*`, `QUEUE_PIPELINE`, `QUEUE_INTERACTIVE`, `SCHEDULE_DAILY`, `SCHEDULE_PUBLISH_DUE`, `SCHEDULE_MAINTENANCE`, `HUMAN_ACTION_WORKFLOWS`, every `STEP_*` constant of §5.7 (list in D-2 below).
- Seams (called through the module attribute): `research.steps.gather_signals`, `build_ledger`, `synthesize_research`, `run_deep_research`, `roll_up_feed_health`; `services.topic_steps.ideate_topics`, `check_novelty_and_score`, `select_topic`, `create_manual_candidate`, `promote_candidate`; `services.diversity.build_avoid_bundle`; `services.external_posts.sync_mdcopilot_posts`; `services.article_steps.ensure_article`, `build_research_packet`, `latest_packet_id`, `write_draft`, `revise_article`, `regenerate_component`; `services.quality_steps.fact_check`, `clinical_review`, `editorial_review`, `collect_revision_findings`, `generate_seo`, `run_quality_gates`; `services.publication_steps.publish_article`, `select_due_articles`, `process_due_article`; `observability.tracing.configure_tracing`, `step_span`.
- Gateway/DB: `llm.gateway.CallContext`, `build_gateway`; `llm.routes.route_from_entries`; `prompts.registry.PromptRegistry.from_directory(root, *, agents=None)`, `default_prompt_root()`; `db.models` `BlogRun`, `RunAttempt`, `AgentRun`, `LlmCall`, `Notification` (`dedupe_key`), `User`, `BlogSetting`, `Article`, `ArticleVersion`, `ResearchPacketRecord`, `ResearchRun`, `ResearchFindingRecord`, `FindingSource`, `TopicCandidateRecord`, `Review`, `Publication`, `PriceOverride`; `ids.uuid7`, `new_trace_id`; `logs.bind_log_context`.
- Test fixtures (root conftest, FOUND): `settings`, `dbos_runtime`, `make_run`, `clean_db`, `sessionmaker_committing`, `committed_seed`, `db_session`, `app`, `client`, `login_as`, `make_user`, `fake_workflow_client`, `committing_app`, `committing_client`, `committing_login_as`, `mock_step_context`, `make_research_graph`, `make_article_graph`; `tests/api_shapes.json`. Golden fixtures and scenario overlays `revision_path`, `invented_statistic`, `invented_quote`, `invented_anecdote`, `prohibited_phrase` (QUAL).
- `WorkerRuntime` fields stay exactly `settings, engine, sessionmaker, prompts, gateway` (FOUND's `dbos_runtime` constructs it directly).

**Verified facts this plan relies on** (plan-INT spikes run 2026-09-17 in `mdcopilot-blog-backend:dev`, dbos 3.0.0, against a throwaway `pgvector/pgvector:pg16`; scripts in `.superpowers/sdd/phases-2-10/scratch/plan-int/spike.py`, `spike2.py`, `spike3.py`):
1. Inside a `@DBOS.step`: `DBOS.apply_schedules_async`, `asyncio.to_thread(DBOS.pause_schedule, name)`, `DBOSClient.apply_schedules_async`, `DBOS.cancel_workflow_async`, `DBOS.fork_workflow_async`, `DBOS.delete_workflows_async` all succeed. In a workflow **body** `DBOS.apply_schedules_async` raises `DBOSException("DBOS.apply_schedules cannot be called from within a workflow")`.
2. `DBOS.enqueue_workflow_async` inside a step raises `AssertionError`. From a workflow body under `SetWorkflowID(child) + SetWorkflowTimeout(60)` it works; the child records `parent_workflow_id`, its own queue and `workflow_timeout_ms=60000`, and it finished after its parent's 2 s timeout had passed. Forking the parent re-uses the child id (one child row).
3. `DBOS.run_step_async(options, async_fn, *args)` records the step under `options["name"]` (dynamic names such as `produce.write` and `change_topic.write` in two workflows); `DBOS.step_id` is set inside; `should_retry` + `retries_allowed` re-run the same step id; `fork_workflow_async(id, function_id, queue_name=, timeout_seconds=)` copies earlier steps, re-executes from `function_id`, keeps the given queue/timeout and the forker's app version.
4. A step with `timeout_seconds` raises `dbos._error.DBOSStepTimeoutError` (an `Exception`). `DBOSWorkflowCancelledError` is a `BaseException`.
5. `DBOS.list_workflows_async(end_time=<ISO string>, status=[...])` filters by creation time; after `delete_workflows_async([id])` the id is absent from `list_workflows_async` and `list_workflow_steps_async(id) == []`.
6. `from dbos import StepOptions` works (TypedDict, `total=False`; keys `name, retries_allowed, interval_seconds, max_attempts, backoff_rate, should_retry, preemptible, timeout_seconds`). Decorated workflows expose `fn.dbos_function_name`.
7. `httpx` and `httpx2` both export `TransportError`, `TimeoutException` (subclass of `TransportError`), `HTTPStatusError`, `MockTransport`; `sqlalchemy.exc.OperationalError`/`InterfaceError` subclass `DBAPIError`.
8. Schedules take no workflow timeout (`ScheduleInput` keys: `schedule_name, workflow_fn, schedule, context, automatic_backfill, cron_timezone, queue_name`); scheduled `scheduled_at` is tz-aware in `cron_timezone` (p1facts/dbos.md).

**Test database and commands** (all from `mdcopilot-blog/`, Docker only):
- DB: `BLOG_TEST_DB=mdcopilot_blog_int_test`; a reviewer or a second INT process uses `mdcopilot_blog_int_review_test`.
- Imports check first: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_int_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py`
- One file: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_int_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q <file>`
- Track suite: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_int_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/integration tests/workflows tests/api/test_runs_api.py tests/db/test_runs_service.py`
- Lint/type (INT lints the whole `src`): `docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c "ruff check --no-cache src tests/integration tests/workflows tests/api/test_runs_api.py tests/db/test_runs_service.py && ruff format --check --no-cache src tests/integration tests/workflows tests/api/test_runs_api.py tests/db/test_runs_service.py && mypy --cache-dir=/tmp/mypy src"`
- Shell syntax: `docker run --rm --name p2p-int-bashn -v "$PWD/scripts:/scripts:ro" bash:5 sh -c 'for f in /scripts/acceptance/phase2-9.sh /scripts/e2e/phase6-smoke.sh /scripts/validation/*.sh; do bash -n "$f" || exit 1; done; echo bash-n-ok'`
- JS syntax: `docker run --rm --name p2p-int-nodecheck -v "$PWD/scripts/e2e:/e2e:ro" node:24-alpine node --check /e2e/phase6-smoke.mjs && echo node-check-ok`

**Owner inputs and fallbacks.**

| Input | Needed for | Fallback when missing |
|---|---|---|
| `Live-go: live-broad-scan`, `Live-go: live-daily-run`, `Live-go: validation-runs` lines in `progress.md` + `OPENAI_API_KEY`/`GEMINI_API_KEY` | INT-12 paid runs (W5 only, after PROV review-clean) | Tooling built; `validation plan --dry-run` and the mock-mode tests pass; `live_run.sh` refuses without `LIVE_GO_CONFIRMED=<gate>`; track reported "complete, pending owner input" |
| Owner review of 5 validation runs and explicit approval | enabling `BLOG_AGENT_SCHEDULER_ENABLED=true` | Flag stays `false`; no track changes it |
| Daily-run timezone confirmation | schedule default | `Asia/Kolkata` 07:00 stays |
| ≥ 5 validation runs recorded | ARCHITECTURE §21–§22 measured tables | No ARCHITECTURE edit; `report.sh --summary` prints "pending: N of 5 validation runs" |
| `BLOG_NOTIFY_WEBHOOK_URL` (optional) | webhook delivery | In-app notifications only |

**Rules for every task.** In Verification lines, `pytest … <paths>` means the header "One file" command with those paths on `mdcopilot_blog_int_test`. TDD: write the listed tests, run them red in Docker, implement, run green, record both outputs. No git. No host python/node/npm. Edit only the files named in the task. Every workflow/step name comes from `names.py` constants (or the one INT-local constant `schedules.STEP_DAILY_LOCAL_DATE`). Only `workflows/` and `worker.py` import `dbos`; `services/runs.py` reaches DBOS only through `workflows/client.py`. Model names never appear in INT code. Test basenames start with `test_int_` (Phase 1 files keep their names).

## Shared definitions (used by several tasks)

### D-1. Workflow registry

`D` = `settings.discovery_timeout_minutes * 60` (900.0 by default); `P` = `settings.production_timeout_minutes * 60` (1800.0).

| Registered name | Module · function (all `async`, `@DBOS.workflow(name=...)`) | Queue | Timeout | Workflow id (CONTRACT §5.7) |
|---|---|---|---|---|
| `discover_topics` | `discover.discover_topics(run_id: str) -> dict[str, Any]` | pipeline | D | `manual-{run_id}`, `daily-{date}`, `restart-discover-{run_id}-{uuid7}` |
| `regenerate_topics` | `discover.regenerate_topics(run_id: str) -> dict[str, Any]` | interactive | D | `regen-topics-{run_id}-{uuid7}` |
| `produce_article` | `produce.produce_article(run_id: str, candidate_id: str) -> dict[str, Any]` | pipeline | P | `produce-{run_id}-{candidate_id}`, `restart-produce-{run_id}-{candidate_id}-{uuid7}` |
| `change_topic` | `human_actions.change_topic(run_id: str, candidate_id: str)` | interactive | P | `change-topic-{run_id}-{candidate_id}` |
| `regenerate_component` | `human_actions.regenerate_component(article_id: str, component: str, section_key: str \| None, instructions: str \| None)` | interactive | P | `regen-component-{article_id}-{uuid7}` |
| `regenerate_article` | `human_actions.regenerate_article(article_id: str, instructions: str \| None)` | interactive | P | `regen-article-{article_id}-{uuid7}` |
| `regenerate_research` | `human_actions.regenerate_research(article_id: str)` | interactive | P | `regen-research-{article_id}-{uuid7}` |
| `recheck_article` | `human_actions.recheck_article(article_id: str)` | interactive | P | `recheck-{article_id}-{uuid7}` |
| `publish_article` | `human_actions.publish_article(article_id: str, version_id: str, as_draft: bool)` | interactive | P | `publish-{version_id}-{uuid7}` |
| `apply_schedule` | `schedules.apply_schedule() -> dict[str, Any]` | interactive | 120 | `apply-schedule-v{settings_version}` |
| `control` | `control.control(action: str, workflow_id: str, step_name: str \| None) -> dict[str, Any]` | interactive | 120 | `control-{uuid7}` |
| `publish_due` | `publish_due.publish_due(scheduled_at: datetime, context: Any) -> dict[str, Any]` | schedule `publish_due` on interactive | none (D-6) | DBOS schedule ids |
| `maintenance` | `maintenance.maintenance(scheduled_at: datetime, context: Any) -> dict[str, Any]` | schedule `maintenance_nightly` on interactive | none (D-6) | DBOS schedule ids |
| `daily_trigger`, `hello_pipeline` | Phase 1 (`schedules.py`, `hello.py`) | pipeline | Phase 1 | Phase 1 |

`workflows/client.py` (importable by the API) gains the pure helpers:
```python
PIPELINE_QUEUE_WORKFLOWS: frozenset[str]   # {discover_topics, produce_article, hello_pipeline, daily_trigger}
def queue_for_workflow(workflow_name: str) -> str        # pipeline for PIPELINE_QUEUE_WORKFLOWS, else interactive
def timeout_for_workflow(workflow_name: str, settings: Settings) -> float
    # D for discover_topics, regenerate_topics; 120.0 for apply_schedule, control; P for every other name
def known_step_names() -> frozenset[str]                  # every value of a names.py attribute starting with "STEP_"
```

### D-2. Step names INT uses (all must be `names.py` constants; INT-1 tests the full set)

`PRODUCTION_STAGES` = `deep_research, build_research_packet, write_draft, fact_check, clinical_review, editorial_review, revise, verify_facts, seo, quality_gates, fix_pass.revise, fix_pass.verify_facts, fix_pass.seo, fix_pass.quality_gates`.

| Prefix | Stages (step name = `"<prefix>.<stage>"`) |
|---|---|
| `discover` | `open_attempt, manual_topic, gather_signals, build_ledger, synthesize_research, ideate_topics, check_novelty_and_score, select_topic, finish, mark_failed` |
| `produce` | `open_attempt`, PRODUCTION_STAGES, `finish, mark_failed` |
| `change_topic` | `open_attempt, supersede`, PRODUCTION_STAGES, `finish, mark_failed` |
| `regenerate_topics` | `open_attempt, ideate_topics, check_novelty_and_score, select_topic, finish, mark_failed` |
| `regenerate_component` | `open_attempt, write_component, fact_check, seo, quality_gates, fix_pass.revise, fix_pass.verify_facts, fix_pass.seo, fix_pass.quality_gates, finish, mark_failed` |
| `regenerate_article` | `open_attempt`, PRODUCTION_STAGES from `write_draft` (i.e. without `deep_research`, `build_research_packet`), `finish, mark_failed` |
| `regenerate_research` | `open_attempt`, PRODUCTION_STAGES, `finish, mark_failed` |
| `recheck` | `open_attempt, fact_check, quality_gates, finish, mark_failed` |
| `publish` | `open_attempt, publish, finish, mark_failed` |
| `publish_due` | `select_due, process_due, notify` |
| `maintenance` | `sync_posts, prune_dbos, feed_health, reconcile_costs` |
| `apply_schedule` | `apply` |
| `control` | `control` |

Code builds a production step name with `tracking.stage_step_name(prefix, stage)`, which returns `f"{prefix}.{stage}"` and raises `RuntimeError(f"unknown step name {name}")` when the value is not in `client.known_step_names()`.

### D-3. Production stage table (article status moves go through `tracking.advance_article`)

| Stage | Article move | When | Seam calls (in order) | Output keys (plus `cancelled`) |
|---|---|---|---|---|
| `deep_research` | none | — | `article_steps.ensure_article(sc, run_id=, candidate_id=)`; `research.steps.run_deep_research(sc.with_ids(article_id=), article_id=, candidate_id=, avoid_source_ids=())` | `article_id, research_run_id, source_count` |
| `build_research_packet` | none | — | `article_steps.build_research_packet(sc.with_ids(article_id=), article_id=, research_run_id=)` | `packet_id, packet_version` |
| `write_draft` | `DRAFTING` | after seam succeeds | `diversity.build_avoid_bundle(db, config=sc.config, brand=sc.brand, now=sc.now(), exclude_article_id=)`; packet id = argument, or `article_steps.latest_packet_id(db, article_id=)` when the argument is None (None → `LookupError(f"article {id} has no research packet")`); `article_steps.write_draft(sc.with_ids(article_id=), article_id=, packet_id=, avoid=, instructions=)` | `version_id, version_no, word_count, title_changed` |
| `fact_check`, `verify_facts`, `fix_pass.verify_facts` | `FACT_CHECKING` | before seam (prefix `recheck`: no move) | `quality_steps.fact_check(sc.with_ids(article_id=), article_id=, version_id=)` | `review_id, version_id, verdict, independent_check, claim_count` |
| `clinical_review` | `CLINICAL_REVIEW` | before | `quality_steps.clinical_review(...)` | `review_id, verdict, blocking_flags, required_changes` |
| `editorial_review` | `EDITORIAL_REVIEW` | before | `build_avoid_bundle`; `quality_steps.editorial_review(..., avoid=)`; then `quality_steps.collect_revision_findings(db, article_id=, version_id=)` | `review_id, verdict, required_changes, revision_required` (`any(f.required for f in findings)`) |
| `revise` | `DRAFTING` | before | `collect_revision_findings`; `build_avoid_bundle`; `article_steps.revise_article(..., base_version_id=, findings=, avoid=, change_kind=ChangeKind.REVISION)` | `version_id, version_no, word_count, title_changed` |
| `fix_pass.revise` | `DRAFTING` | before | load the `blog_reviews` row `gate_review_id` → `GateReport.model_validate(payload)` → `decide_fix_pass(report, fix_pass_used=False).findings`; `build_avoid_bundle`; `revise_article(..., change_kind=ChangeKind.FIX_PASS)` | as `revise` |
| `seo`, `fix_pass.seo` | `SEO` | before | `quality_steps.generate_seo(...)` | `seo_id, version_id, slug` |
| `quality_gates`, `fix_pass.quality_gates` | `READY_FOR_REVIEW` (action `ready`), `QUALITY_GATE_FAILED` (action `failed`, or `fix_pass` returned when `fix_pass_used=True`), none (action `fix_pass`) | after seam | `quality_steps.run_quality_gates(..., run_kind=, fix_pass_used=)`; then the D-5 notification for the new status | `review_id, version_id, passed, action, seo_rerun, suggestion, failed_gates` |
| `write_component` | none | — | base = `blog_articles.current_version_id` (None → `LookupError`); `build_avoid_bundle`; `article_steps.regenerate_component(..., base_version_id=, component=ArticleComponent(c), section_key=SectionKey(s) or None, instructions=, avoid=)` | as `write_draft` |

`failed_gates` = sorted `GateId` values of results with `severity == "blocking"` and not passed. Run kinds: `quality_gates` → `full` with `fix_pass_used=False` (prefix `recheck` → `recheck` with `fix_pass_used=True`); `fix_pass.quality_gates` → `fix_pass` with `fix_pass_used=True`. `fix_pass.seo` runs iff `quality_gates.seo_rerun` or `fix_pass.revise.title_changed`.

### D-4. Run status per workflow (Rules A, B)

| Workflow | `open_attempt` | Later moves |
|---|---|---|
| `discover_topics` | restart attempt on terminal run → `QUEUED`; then `advance_run(RESEARCHING)` | `manual_topic` end / final `check_novelty_and_score` → `TOPICS_READY`; `select_topic` → `PRODUCING` (selected) or `WAITING_FOR_TOPIC` |
| `regenerate_topics` | `SUCCEEDED`/`FAILED` → `QUEUED` → `RESEARCHING`; `TOPICS_READY`/`WAITING_FOR_TOPIC` unchanged; `QUEUED` → `RESEARCHING` | as discover |
| `produce_article`, `change_topic` | `advance_run(PRODUCING)` (`SUCCEEDED`/`FAILED` walk through `QUEUED`); original attempt on `CANCELLED` run is recorded `CANCELLED` and the workflow stops | every production stage `advance_run(PRODUCING)`; `finish` → `SUCCEEDED` |
| human actions (`regenerate_*`, `recheck_article`, `publish_article`) | never touch `blog_runs` (`respect_run_cancel=False`) | none |

`mark_failed` moves the run to `FAILED` only for `discover_topics`, `regenerate_topics`, `produce_article`, `change_topic`, `hello_pipeline`.

### D-5. Notifications (CONTRACT §4.11)

| Kind | Recipients (active users) | Dedupe key | Title | Body | Link |
|---|---|---|---|---|---|
| `ready_for_review` | holders of `blog.review` | `ready_for_review:{article_id}:{version_id}` | `Article ready for review` | `"{title}" passed its quality gates and is waiting for review.` | `/articles/{article_id}` |
| `quality_gate_failed` | holders of `blog.review` | `quality_gate_failed:{article_id}:{version_id}` | `Article failed quality gates` | `"{title}" failed quality gates: {", ".join(failed_gates) or "see the gate report"}.` | `/articles/{article_id}` |
| `run_failed` | holders of `blog.agent_runs` | `run_failed:{run_id}:{YYYY-MM-DD}` (local date of the failure in the effective timezone) | `Run failed` | `Run {run_id} failed at {step}: {error class}.` | `/agent-runs?runId={run_id}` |
| `publish_failed` | holders of `blog.publish` | `publish_failed:{article_id}:{version_id}` | `Publishing failed` | `"{title}" could not be published: {error}.` | `/articles/{article_id}` |
| `scheduled_export_due` | holders of `blog.publish` | `scheduled_export_due:{article_id}:{version_id}` | `Scheduled article exported` | `"{title}" reached its scheduled time and was exported. Paste it into MDCopilot and confirm the live URL.` | `/articles/{article_id}` |
| `daily_run_skipped` | role `admin` | `daily_run_skipped:{article_id or manual run_id}:{YYYY-MM-DD}` | `Daily run skipped` | `No daily run was started for {date}: {reason}.` | `/articles/{article_id}` or `/agent-runs?runId={run_id}` |

`{title}` = `blog_articles.title`, or `Untitled article` when null. Title is cut to 300 characters, `{error}` to 500.

### D-6. Scheduled workflows have no DBOS timeout
Schedules accept no timeout (fact 8). CONTRACT §5.7's 240 s (`publish_due`) and P (`maintenance`) budgets are met by bounds instead: `publish_due` handles at most `MAX_DUE_PER_TICK = 3` articles per tick, and `select_due`/`notify` steps use `timeout_seconds=15.0`. `process_due` has no step timeout, because a timeout could cancel a publish mid-request; PUB's `publisher_timeout_seconds` bounds each HTTP call. Maintenance stages are bounded by `PRUNE_BATCH_SIZE = 500` × `PRUNE_MAX_BATCHES = 20` and the seams' own HTTP timeouts.

## Tasks

### INT-0: Pre-flight (read-only; no code)

**Files.** Create nothing except lines in `.superpowers/sdd/phases-2-10/requests/int.md`.

**Interfaces.** Consumes the eight tracks as built.

**Behaviour rules.**
1. Start only when `progress.md` shows FOUND and PROV, RES, TOP, ART, QUAL, PUB, OBS, UI review-clean.
2. Run the imports check (header command). A failure in another track's file becomes a `Request:` line naming the file and error; INT stops that item.
3. Confirm no seam module still raises the FOUND stub error: `docker compose run --rm --no-deps tools python -c "import pathlib,sys; mods=['research/steps.py','services/topic_steps.py','services/diversity.py','services/novelty.py','services/external_posts.py','services/article_steps.py','services/quality_steps.py','domain/fix_pass.py','services/publication_steps.py']; bad=[m for m in mods if 'implements this' in pathlib.Path('src/mdcopilot_blog',m).read_text()]; print('stubs:', bad); sys.exit(1 if bad else 0)"` → expected `stubs: []`.
4. Read (do not edit) and record in the INT report: (a) the name and signature of OBS's cost-reconciliation function in `pkg/services/metrics.py` (CONTRACT has none, see open questions); (b) whether ART's `revise_article`/`regenerate_component` copy the base version's `blog_version_seo` row or QUAL's gate 11 reads an ancestor's SEO (D-3 skips `seo` when the title did not change); (c) the accessible names UI renders for the buttons the smoke test clicks (INT-11 list); (d) PROV's `pkg/llm/pricing.py` public API (INT-12 worst-case pricing).
5. Each mismatch with this plan is a `Request:` line; INT continues with the items that do not depend on it.

**Tests to write first.** None (verification task).

**Verification.** Commands in rules 2–3; expected outputs as stated.

**Acceptance covered.** Precondition for all INT items (CONTRACT §1 "INT starts when all eight tracks are review-clean").

### INT-1: Retry policy and client helpers (`workflows/retry.py`, `workflows/client.py`)

**Files.** Create `pkg/workflows/retry.py`, `backend/tests/workflows/test_int_retry.py`, `backend/tests/workflows/test_int_client.py`. Modify `pkg/workflows/client.py`.

**Interfaces.**
- Produces (`retry.py`):
  ```python
  TRANSIENT_HTTP_STATUSES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})
  STEP_MAX_ATTEMPTS = 3; STEP_INTERVAL_SECONDS = 2.0; STEP_BACKOFF_RATE = 2.0
  def is_transient(exc: BaseException) -> bool
  def step_options(name: str, *, retries: bool = True, timeout_seconds: float | None = None) -> StepOptions
  ```
- Produces (`client.py`, in addition to D-1 helpers):
  ```python
  @dataclass(frozen=True)
  class WorkflowView: workflow_id: str; status: str; name: str | None; app_version: str | None; queue_name: str | None
  class WorkflowClientProtocol(Protocol):   # Phase 1 methods unchanged, plus:
      async def describe(self, workflow_id: str) -> WorkflowView | None: ...
      async def fork_from_function_id(self, workflow_id: str, start_step: int, *, queue_name: str,
                                      timeout_seconds: float | None) -> str: ...
  @dataclass(frozen=True)
  class ForkByIdCall: workflow_id: str; start_step: int; queue_name: str; timeout_seconds: float | None; new_workflow_id: str
  # FakeWorkflowClient gains fields (all with defaults): views: dict[str, WorkflowView], forked_by_id: list[ForkByIdCall],
  # fork_error: Exception | None = None, cancel_error: Exception | None = None
  ```

**Behaviour rules.**
1. `is_transient` returns True for: `httpx.TransportError`, `httpx2.TransportError` (timeouts included), builtin `TimeoutError`; `httpx.HTTPStatusError`/`httpx2.HTTPStatusError` whose `response.status_code` is in `TRANSIENT_HTTP_STATUSES`; `sqlalchemy.exc.OperationalError`, `sqlalchemy.exc.InterfaceError`, `psycopg.OperationalError`; any `sqlalchemy.exc.DBAPIError` with `connection_invalidated is True`. Everything else is False, including `GatewayError` subclasses (`BudgetExceeded`, `RouteExhausted`, `ProviderNotAvailable`), `DomainError` subclasses, `InvalidTransition`, `LookupError`, `ValueError`, `RuntimeError`, `DBOSStepTimeoutError`.
2. `step_options(name)` returns exactly `{"name": name, "retries_allowed": retries, "max_attempts": STEP_MAX_ATTEMPTS, "interval_seconds": STEP_INTERVAL_SECONDS, "backoff_rate": STEP_BACKOFF_RATE, "should_retry": is_transient}` plus `"timeout_seconds"` only when given. Constants are read at call time (tests monkeypatch them).
3. `WorkflowClient.describe` calls `list_workflows_async(workflow_ids=[id], load_input=False, load_output=False)`; empty → None; otherwise maps `workflow_id, status, name, app_version, queue_name`.
4. `WorkflowClient.fork_from_function_id` calls `fork_workflow_async(workflow_id, start_step, application_version=self._app_version, queue_name=queue_name, timeout_seconds=timeout_seconds)` and returns the new id.
5. `FakeWorkflowClient.describe` returns `views[id]` when present, else `WorkflowView(id, statuses[id], None, None, None)` when the id is in `statuses`, else None. `fork_from_function_id` raises `fork_error` when set, else records `ForkByIdCall` with new id `f"{workflow_id}-fork-{len(forked)+len(forked_by_id)+1}"` and sets its status `ENQUEUED`. `cancel` raises `cancel_error` when set (Phase 1 behaviour otherwise).
6. Phase 1 signatures and FakeWorkflowClient defaults stay unchanged (other tracks construct `FakeWorkflowClient()`).

**Tests to write first.**
- `test_int_retry.py::test_transient_errors_are_retried` — parametrized instances: `httpx.ConnectError("x")`, `httpx2.ReadTimeout("x")`, `TimeoutError()`, `httpx.HTTPStatusError("x", request=httpx.Request("GET","http://t"), response=httpx.Response(503))` and the same with 408, 429, 500, 502, 504, `sqlalchemy.exc.OperationalError("s", {}, Exception("x"))`, `psycopg.OperationalError("x")` → each `is_transient(...) is True`.
- `test_int_retry.py::test_permanent_errors_are_not_retried` — `httpx.HTTPStatusError` with 400, 401, 404, 422; `ValueError()`, `LookupError()`, `RuntimeError()`, `InvalidTransition(Entity.RUN, "SUCCEEDED", "PRODUCING")`, `BudgetExceeded("x")`, `InsufficientEvidence("r", 1, 5, 2)` → each False.
- `test_int_retry.py::test_step_options_shape` — `step_options("produce.seo")` equals the rule-2 dict (compare `should_retry is is_transient`); `step_options("x", retries=False, timeout_seconds=15.0)["retries_allowed"] is False` and `["timeout_seconds"] == 15.0`; `"timeout_seconds" not in step_options("x")`.
- `test_int_retry.py::test_every_int_step_name_is_a_names_constant` — build the D-2 set literally in the test (every prefix × stage listed in D-2) and assert `expected - known_step_names() == set()`.
- `test_int_retry.py::test_queue_and_timeout_helpers` — with `settings`: `queue_for_workflow("produce_article") == "pipeline"`, `("discover_topics") == "pipeline"`, `("change_topic") == "interactive"`, `("recheck_article") == "interactive"`; `timeout_for_workflow("discover_topics", settings) == settings.discovery_timeout_minutes * 60`, `("regenerate_topics") == 900.0` with defaults, `("produce_article") == 1800.0`, `("publish_article") == 1800.0`, `("control") == 120.0`, `("apply_schedule") == 120.0`.
- `test_int_client.py::test_fake_client_describe_and_fork_by_id` — fake with `statuses={"w": "PENDING"}` → `describe("w") == WorkflowView("w", "PENDING", None, None, None)`; `describe("nope") is None`; `fork_from_function_id("w", 4, queue_name="pipeline", timeout_seconds=1800.0)` returns `"w-fork-1"` and `forked_by_id == [ForkByIdCall("w", 4, "pipeline", 1800.0, "w-fork-1")]`; with `fork_error=RuntimeError("down")` it raises `RuntimeError`.
- `test_int_client.py::test_real_client_describe_and_fork_from_function_id` (uses `dbos_runtime`, the Phase 1 `workflow_client` pattern with `DBOS.application_version`): run a module-local test workflow `test.int_three_steps` (three `@DBOS.step` returning 1, 2, 3) under id `int-client-<hex>`; `describe(id)` → `status == "SUCCESS"`, `name == "test.int_three_steps"`, `app_version == "pytest"`; `fork_from_function_id(id, 3, queue_name="pipeline", timeout_seconds=60.0)` → new id; its result equals the original result; `describe(new)` → `queue_name == "pipeline"`; `DBOS.list_workflows_async(workflow_ids=[new])[0].forked_from == id` and `.workflow_timeout_ms == 60000`.

**Implementation notes.**
```python
from dbos import StepOptions  # TypedDict, total=False (verified)
```

**Verification.** One-file command for both files → all pass; lint command on the two modules → clean.

**Acceptance covered.** ARCHITECTURE §5.5 "Retry (automatic) only for transient errors"; CONTRACT §5.7 step-name constants.

### INT-2: Notifications service and API

**Files.** Modify `pkg/services/notifications.py` (create if FOUND left it absent), `pkg/api/routers/notifications.py`, `pkg/api/schemas_notifications.py`. Create `backend/tests/integration/int_helpers.py`, `backend/tests/integration/test_int_notifications_service.py`, `backend/tests/integration/test_int_notifications_api.py`. Modify `backend/tests/integration/conftest.py`.

**Interfaces.**
- Produces (`services/notifications.py`):
  ```python
  class NotificationEvent(BaseModel):  # frozen
      kind: NotificationKind; title: str; body: str; link: str | None
      article_id: uuid.UUID | None = None; run_id: uuid.UUID | None = None
      version_id: uuid.UUID | None = None; day: date | None = None
  @dataclass(frozen=True) class NotifyResult: inserted: int; recipients: int; webhook_sent: bool
  RECIPIENT_PERMISSION: Mapping[NotificationKind, Permission | None]   # None = role admin
  def dedupe_key(event: NotificationEvent) -> str
  def ready_for_review_event(*, article_id: uuid.UUID, version_id: uuid.UUID, title: str | None) -> NotificationEvent
  def quality_gate_failed_event(*, article_id, version_id, title: str | None, failed_gates: Sequence[str]) -> NotificationEvent
  def run_failed_event(*, run_id: uuid.UUID, day: date, step: str, error_class: str) -> NotificationEvent
  def publish_failed_event(*, article_id, version_id, title: str | None, error: str) -> NotificationEvent
  def scheduled_export_due_event(*, article_id, version_id, title: str | None) -> NotificationEvent
  def daily_run_skipped_event(*, day: date, reason: str, article_id: uuid.UUID | None, run_id: uuid.UUID | None) -> NotificationEvent
  async def recipients_for(db: AsyncSession, kind: NotificationKind) -> list[uuid.UUID]
  async def notify(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, event: NotificationEvent, *,
                   transport: httpx.AsyncBaseTransport | None = None) -> NotifyResult
  async def list_notifications(db, *, user_id: uuid.UUID, unread_only: bool, limit: int, offset: int) -> tuple[list[Notification], int]
  async def mark_read(db, *, user_id: uuid.UUID, notification_id: uuid.UUID, now: datetime) -> Notification   # LookupError
  async def mark_all_read(db, *, user_id: uuid.UUID, now: datetime) -> int
  ```
- Produces (API, CONTRACT §4.11): `NotificationOut(ApiModel)`: `id: uuid.UUID, kind: NotificationKind, title: str, body: str, link: str | None, read_at: datetime | None, created_at: datetime`. Routes `GET /notifications`, `POST /notifications/{notification_id}/read`, `POST /notifications/read-all` (204), each `require_permission(Permission.VIEW)`.
- Produces (tests): `int_helpers.py` with `WAIT_SECONDS = 120`, `async def create_user_committed(sm, role: Role, email: str) -> User`, `async def activate_settings_values(sm, values: dict[str, Any]) -> int` (deactivates the active `blog_settings` row, inserts `version = max + 1` with the old values merged with `values`, `is_active=True`, commits, returns the version), fixture `manual_topic_selection` (calls `activate_settings_values(sm, {"topicSelectionMode": "manual"})` after `committed_seed`), `async def wait_workflow(workflow_id: str, timeout: float = WAIT_SECONDS) -> Any`, `async def load_run_rows(sm, run_id) -> RunRows` (run, attempts by `attempt_no`, step rows by `created_at, dbos_step_id`, LLM calls, articles by `created_at`), `@contextmanager def record_article_statuses(monkeypatch) -> Iterator[list[ArticleStatus]]` (wraps `article_status.set_article_status` and appends each `target`), `@contextmanager def record_run_statuses(monkeypatch) -> Iterator[list[RunStatus]]` (wraps `tracking.set_run_status`). `tests/integration/conftest.py` imports `manual_topic_selection` from `int_helpers` and `import mdcopilot_blog.worker  # noqa: F401` (worker.py imports every workflow module; INT-4 to INT-8 each add their module to that import block).

**Behaviour rules.**
1. Recipients: users with `is_active = true` whose `permissions_for(Role(role))` contains the kind's permission (D-5); `daily_run_skipped` → users with `role == "admin"`. Order by `created_at, id`.
2. `dedupe_key` exactly as D-5 (`day.isoformat()`; for `daily_run_skipped` the id part is `article_id` when set, else `run_id`).
3. Builders produce the D-5 titles, bodies and links exactly; `title` cut to 300 characters; `error` in `publish_failed` cut to 500.
4. `notify` in one session: fetch recipients, `INSERT … ON CONFLICT (user_id, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id` per recipient, commit. `inserted` = rows returned.
5. Webhook: only when `settings.notify_webhook_url` is set and (`inserted > 0` or `recipients == 0`). One `POST` with JSON `{"kind", "title", "body", "link", "url", "articleId", "runId", "versionId", "date", "dedupeKey"}` (`url` = `settings.public_app_url.rstrip("/") + link` or null; ids as strings or null; `date` ISO or null), timeout `settings.notify_webhook_timeout_seconds`, `follow_redirects=False`, client built with `transport` when given. `webhook_sent` True iff the response is 2xx. Any exception or non-2xx logs WARNING `notification webhook failed` with `status` or `error_class` only (never the URL) and returns `webhook_sent=False`; `notify` never raises for webhook problems.
6. `list_notifications`: rows with `user_id == principal`, optional `read_at IS NULL`, ordered `created_at desc, id desc`; `total` counts the same filter; limit capped at 100.
7. `mark_read`: row must belong to the user, else `LookupError` → 404 `Notification not found` (same for unknown id). Already read → unchanged `read_at`. Commit.
8. `mark_all_read`: `UPDATE … SET read_at = now WHERE user_id = principal AND read_at IS NULL`; returns count; 204 with empty body. No audit rows (CONTRACT §4.11 names no audit action; see open questions).

**Tests to write first.**
- `test_int_notifications_service.py::test_recipients_by_kind` — committed users (viewer, editor, reviewer, publisher, admin, and an inactive reviewer via `is_active=False`), parametrized: `ready_for_review` and `quality_gate_failed` → {reviewer, publisher, admin}; `run_failed` → {reviewer, publisher, admin}; `publish_failed` and `scheduled_export_due` → {publisher, admin}; `daily_run_skipped` → {admin}. Assert `set(await recipients_for(db, kind)) == expected ids`.
- `::test_notify_inserts_once_per_recipient` — `ready_for_review_event(article_id=A, version_id=V, title="Hello")` twice → first `NotifyResult(3, 3, False)`, second `NotifyResult(0, 3, False)`; 3 rows with `dedupe_key == f"ready_for_review:{A}:{V}"`, `title == "Article ready for review"`, `body == '"Hello" passed its quality gates and is waiting for review.'`, `link == f"/articles/{A}"`.
- `::test_event_builders` — exact title/body/link/dedupe for each of the six builders with fixed ids and `day=date(2026, 9, 17)`; `quality_gate_failed_event(..., failed_gates=[])` body ends `failed quality gates: see the gate report.`; `title=None` renders `"Untitled article"`.
- `::test_webhook_posts_once` — settings copy `notify_webhook_url="http://hooks.test/notify"`; `httpx.MockTransport` handler records requests and returns 204; two `notify` calls → exactly 1 request, method POST, `json.loads(body)` keys == the 10 rule-5 keys, `url == f"http://test/articles/{A}"`, `dedupeKey == f"ready_for_review:{A}:{V}"`; first result `webhook_sent is True`, second `False`.
- `::test_webhook_failures_do_not_raise` — handler raising `httpx.ConnectError("down")` → result `inserted == 3`, `webhook_sent is False`; handler returning 500 → `webhook_sent is False`; caplog WARNING message `notification webhook failed` and `"hooks.test"` not in any record text.
- `::test_webhook_sent_when_nobody_can_receive` — no users → `NotifyResult(0, 0, True)`.
- `test_int_notifications_api.py::test_list_returns_only_own_rows_newest_first` — `login_as(Role.VIEWER)`; insert in `db_session` 3 rows for that user (created_at t1<t2<t3, t2 read) and 1 row for another user → `GET /api/blog-agent/notifications` 200: `total == 3`, ids ordered t3, t2, t1, keys of each item == `{"id","kind","title","body","link","readAt","createdAt"}`; `?unreadOnly=true` → `total == 2`; `?limit=1&offset=1` → one item (t2), `limit == 1`, `offset == 1`.
- `::test_list_requires_login` → 401.
- `::test_mark_read` — POST `/notifications/{id}/read` with CSRF → 200, `readAt` not null; second POST → same `readAt`; another user's id → 404 title `Notification not found`; random uuid → 404; `/notifications/not-a-uuid/read` → 422; without `X-CSRF-Token` → 403.
- `::test_read_all` — POST `/notifications/read-all` → 204, empty body; `?unreadOnly=true` → `total == 0`; the other user's row still has `read_at IS NULL`.
- (No 403 test: every role holds `blog.view`; recorded under INT-final.)

**Implementation notes.**
```python
stmt = insert(Notification).values(...).on_conflict_do_nothing(
    index_elements=["user_id", "dedupe_key"], index_where=text("dedupe_key IS NOT NULL")
).returning(Notification.id)
```

**Verification.** One-file command on the three test files → pass; `tests/api/test_rbac_routes.py` → pass.

**Acceptance covered.** Phase 8 "Notifications: in-app + optional webhook" (service + API tests); CONTRACT §4.11.

### INT-3: Tracking extensions, stage harness, cancellation handling (`workflows/tracking.py`, `workflows/hello.py`)

**Files.** Modify `pkg/workflows/tracking.py`, `pkg/workflows/hello.py`. Create `backend/tests/workflows/test_int_tracking.py`, `backend/tests/workflows/conftest.py`. Phase 1 `tests/workflows/test_tracking.py` and `test_hello_pipeline.py` must stay green unchanged.

**Interfaces.**
- Consumes: `retry.step_options`, `client.known_step_names`, `notifications.notify`, `notifications.run_failed_event`, `notifications.publish_failed_event`, `services.article_status.set_article_status`, `services.step_context.build_step_context`, `observability.tracing.step_span`, `services.config.load_effective_config`, `services.config.local_date`.
- Produces:
  ```python
  from dbos._error import DBOSWorkflowCancelledError as WorkflowCancelledError   # the only private dbos import in the codebase
  PIPELINE_RUN_WORKFLOWS: frozenset[str]   # {discover_topics, regenerate_topics, produce_article, change_topic, hello_pipeline}
  IN_PROGRESS_ARTICLE_STATUSES: frozenset[ArticleStatus]   # {DRAFTING, FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW, SEO}
  WORKFLOW_CANCELLED_ERROR = {"class": "WorkflowCancelled", "message": "cancelled or timed out by DBOS"}   # moved from hello.py
  async def ensure_attempt(sm, *, run_id: uuid.UUID, workflow_id: str, workflow_name: str, respect_run_cancel: bool = True) -> uuid.UUID
  async def get_attempt_snapshot(sm, workflow_id: str) -> AttemptSnapshot | None   # (id, run_id, status, workflow_name, attempt_no)
  async def advance_run(sm, *, run_id: uuid.UUID, target: RunStatus, stage: str | None = None) -> bool
  async def advance_article(sm, *, article_id: uuid.UUID, target: ArticleStatus) -> ArticleStatus
  async def mock_delay(settings: Settings) -> None
  def stage_step_name(prefix: str, stage: str) -> str
  @dataclass(frozen=True)
  class StageContext: rt: WorkerRuntime; sc: StepContext; run_id: uuid.UUID; attempt_id: uuid.UUID; workflow_id: str; step_name: str; trace_id: str
  type StageBody = Callable[[StageContext], Awaitable[dict[str, Any]]]
  STOP: Final[dict[str, Any]] = {"cancelled": True}
  async def tracked_stage(step_name: str, *, run_id: str | None, workflow_name: str, body: StageBody,
                          article_id: str | None = None, agent_name: str | None = None, agent_version: str | None = None,
                          retries: bool = True) -> dict[str, Any]
      # run_id None: resolved inside the step from blog_articles.run_id of article_id (both None → ValueError)
  async def untracked_step[R](step_name: str, fn: Callable[..., Awaitable[R]], *args: object, retries: bool = False,
                              timeout_seconds: float | None = None, allow_local: bool = False) -> R
      # allow_local=True skips the known_step_names() check (only schedules.STEP_DAILY_LOCAL_DATE uses it)
  async def fail_workflow(*, workflow_id: str, workflow_name: str, run_id: uuid.UUID, article_id: uuid.UUID | None,
                          failed_step: str, error: Mapping[str, object]) -> None
  async def close_cancelled_workflow(*, workflow_id: str, workflow_name: str, run_id: uuid.UUID, article_id: uuid.UUID | None) -> None
  ```

**Behaviour rules.**
1. `ensure_attempt`: existing row with status `ENQUEUED` (pre-created by the restart API) → in one locked transaction set `RUNNING`, `started_at = now`, `start_step = DBOS.step_id`; return its id. Existing row with any other status → return its id unchanged. New row: Phase 1 logic, except (a) `cancelled_before_start` applies only when `respect_run_cancel` is True; (b) a fork re-opens a terminal run to `QUEUED` only when `workflow_name not in HUMAN_ACTION_WORKFLOWS`.
2. `advance_run` (each move is one `set_run_status` call, which locks the row): loop — read status `s`; `s == target` → True; `s == CANCELLED` → False; `can_transition(s, target)` → move, True; `s in {SUCCEEDED, FAILED}` → move to `QUEUED`, continue; `s == QUEUED and target in {TOPICS_READY, WAITING_FOR_TOPIC}` → move to `RESEARCHING`, continue; `s == RESEARCHING and target == WAITING_FOR_TOPIC` → move to `TOPICS_READY`, continue; otherwise raise `InvalidTransition(Entity.RUN, s, target)`. When a move raises `InvalidTransition` and the re-read status is `CANCELLED`, return False; otherwise re-raise. `stage` is passed to the final move only.
3. `advance_article` (each move is `set_article_status` + commit in its own session): loop — `s == target` → return `s`; `can_transition(ARTICLE, s, target)` → move, return target; `s == FAILED` → move to `DRAFTING`, continue; `s` in `DRAFTING, FACT_CHECKING, CLINICAL_REVIEW` and `target` in `CLINICAL_REVIEW, EDITORIAL_REVIEW, SEO, READY_FOR_REVIEW, QUALITY_GATE_FAILED` → move to the next of `DRAFTING → FACT_CHECKING → CLINICAL_REVIEW → EDITORIAL_REVIEW`, continue; otherwise raise `InvalidTransition(Entity.ARTICLE, s, target)`. Missing article → `LookupError`.
4. `mock_delay`: `await asyncio.sleep(settings.mock_step_delay_seconds)` only when `settings.mock_mode` and the delay > 0 (hello.py now imports it).
5. `tracked_stage` runs `DBOS.run_step_async(step_options(step_name, retries=retries), _execute)`. Before anything else it calls `stage_step_name`-style validation (`step_name in known_step_names()`, else `RuntimeError`). `_execute`: `rt = get_runtime()`; `workflow_id = DBOS.workflow_id` (None → `RuntimeError`); when `run_id` is None, read `blog_articles.run_id` for `article_id` (missing → `LookupError(f"article {article_id} not found")`); `trace_id = get_run_trace_id`; `bind_log_context(run_id, trace_id)`; `human = workflow_name in HUMAN_ACTION_WORKFLOWS`; `attempt_id = ensure_attempt(..., respect_run_cancel=not human)`; if the attempt status is `CANCELLED` → return `STOP` (no step row, body not called); if not `human` and the run status is `CANCELLED` → `finish_attempt(CANCELLED)`, return `STOP`. Then `with step_span(step_name, run_id=, attempt_id=, trace_id=, agent_name=)` and `async with track_step(...) as handle`: `sc = await build_step_context(settings=rt.settings, sessionmaker=rt.sessionmaker, gateway=rt.gateway, prompts=rt.prompts, call=handle.call_context())`; `out = await body(StageContext(...))`. If `out.get("cancelled")` is True → `finish_attempt(CANCELLED)` and return `STOP`; else return `{"cancelled": False, **out}`.
6. Stage bodies call `mock_delay` exactly once, after any "before" status move (D-3) and before the first seam call; when a status move returns False (run cancelled) the body returns `STOP` before the delay.
7. `untracked_step` runs `DBOS.run_step_async(step_options(step_name, retries=retries, timeout_seconds=timeout_seconds), fn, *args)` with the same name validation.
8. `fail_workflow` (the body of every `<prefix>.mark_failed` step): attempt snapshot `CANCELLED` → return with no change. Article (when `article_id` given): `workflow_name == publish_article` → `PUBLISHING` moves to `PUBLISH_FAILED` and `notify(publish_failed_event(..., error=error["message"]))`; any other workflow → status in `IN_PROGRESS_ARTICLE_STATUSES` moves to `FAILED`; other statuses unchanged. Run (only `workflow_name in PIPELINE_RUN_WORKFLOWS`): `set_run_status(FAILED, error=dict(error))`; on `InvalidTransition`/`LookupError` log WARNING `run not marked failed` and skip the notification; on success `notify(run_failed_event(run_id=, day=local_date(now, effective timezone), step=failed_step, error_class=error["class"]))`. Finally `finish_attempt(FAILED, error=error)`. `error` = `{"class": type(exc).__name__, "message": str(exc)[:2000], "step": failed_step}`.
9. `close_cancelled_workflow` (plain coroutine, called from `except WorkflowCancelledError`): run status `CANCELLED` or attempt snapshot `CANCELLED` → `finish_attempt(CANCELLED)` only. Otherwise (a DBOS timeout): article handling as rule 8; run (pipeline workflows only) → `FAILED` with `WORKFLOW_CANCELLED_ERROR` plus the `run_failed` notification with `step="workflow_timeout"`, `error_class="WorkflowCancelled"`; attempt → `CANCELLED` with `error=None`. `InvalidTransition`/`LookupError` are suppressed.
10. `hello.py` keeps its public names and behaviour; its `_close_cancelled_workflow` delegates to `close_cancelled_workflow(workflow_id=DBOS.workflow_id, workflow_name=WORKFLOW_HELLO, run_id=..., article_id=None)`, `WORKFLOW_CANCELLED_ERROR` and `_mock_delay` are imported from `tracking` (re-exported names stay importable from `hello`).
11. `tests/workflows/conftest.py`: docstring, `import mdcopilot_blog.worker  # noqa: F401` (registers every workflow before `dbos_runtime` launches), and `from tests.integration.int_helpers import manual_topic_selection  # noqa: F401`.

**Tests to write first** (`test_int_tracking.py`; all use `dbos_runtime` and committed rows; module-local test workflows named `test.int_*`).
- `test_restart_attempt_pre_created_enqueued_is_opened` — `make_run(status=RunStatus.FAILED)`; insert `RunAttempt(workflow_name="discover_topics", dbos_workflow_id="restart-discover-<run>-int", attempt_no=1, status="ENQUEUED", started_at=None)`; start `test.int_open_probe(run_id, "discover_topics")` under that id (its step calls `ensure_attempt`) → returned id == inserted id; row `status == "RUNNING"`, `started_at` not null, `start_step == 1`; run still `FAILED`.
- `test_fork_reopens_pipeline_run_but_not_human_action_run` — parametrized `("produce_article", "QUEUED")`, `("regenerate_component", "SUCCEEDED")`: run `SUCCEEDED`; original probe workflow with that `workflow_name` finishes; fork it from step 1 with `DBOS.fork_workflow_async` → run status equals the expected value; fork attempt `forked_from_workflow_id` == original id.
- `test_respect_run_cancel_flag` — run `CANCELLED`; `ensure_attempt(..., workflow_name="recheck_article", respect_run_cancel=False)` inside a probe → attempt `RUNNING`, run `CANCELLED`; same with `respect_run_cancel=True` and `workflow_name="produce_article"` on a new id → attempt `CANCELLED`, `finished_at` not null.
- `test_advance_run_walks` — parametrized `(start, target, recorded_moves, result)`: `(QUEUED, PRODUCING, [PRODUCING], True)`; `(SUCCEEDED, PRODUCING, [QUEUED, PRODUCING], True)`; `(FAILED, RESEARCHING, [QUEUED, RESEARCHING], True)`; `(QUEUED, TOPICS_READY, [RESEARCHING, TOPICS_READY], True)`; `(QUEUED, WAITING_FOR_TOPIC, [RESEARCHING, TOPICS_READY, WAITING_FOR_TOPIC], True)`; `(WAITING_FOR_TOPIC, TOPICS_READY, [TOPICS_READY], True)`; `(PRODUCING, PRODUCING, [], True)`; `(CANCELLED, PRODUCING, [], False)`. Use `record_run_statuses`. Plus `(PRODUCING, RESEARCHING)` raises `InvalidTransition`. After `SUCCEEDED → PRODUCING`, `finished_at is None`.
- `test_advance_article_walks` — `make_article_graph` committed with the start status; parametrized `(READY_FOR_REVIEW, FACT_CHECKING, [FACT_CHECKING])`; `(FAILED, FACT_CHECKING, [DRAFTING, FACT_CHECKING])`; `(FAILED, SEO, [DRAFTING, FACT_CHECKING, SEO])`; `(FAILED, EDITORIAL_REVIEW, [DRAFTING, FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW])`; `(FAILED, READY_FOR_REVIEW, [DRAFTING, FACT_CHECKING, READY_FOR_REVIEW])`; `(SEO, DRAFTING, [DRAFTING])`; `(QUALITY_GATE_FAILED, QUALITY_GATE_FAILED, [])`. Use `record_article_statuses`. `(SUPERSEDED, DRAFTING)` and `(APPROVED, FACT_CHECKING)` raise `InvalidTransition`.
- `test_tracked_stage_records_step_and_returns_body_output` — probe workflow `test.int_stage_probe` calls `tracked_stage("produce.clinical_review", run_id=, workflow_name="produce_article", body=lambda ctx: {"seen_run": str(ctx.run_id), "has_sc": ctx.sc.call.run_id == ctx.run_id})` → result `{"cancelled": False, "seen_run": run_id, "has_sc": True}`; one `blog_agent_runs` row `step_name == "produce.clinical_review"`, `status == "SUCCEEDED"`, `tries == 1`, `trace_id == run.trace_id`, `attempt_id` == the probe's attempt; `DBOS.list_workflow_steps_async` names == `["produce.clinical_review"]`.
- `test_tracked_stage_stops_on_cancelled_run` — run `CANCELLED` before start, `workflow_name="produce_article"` → result `STOP`; body not called (flag); attempt `CANCELLED`; zero `blog_agent_runs` rows.
- `test_tracked_stage_retries_transient_errors_only` — monkeypatch `retry.STEP_INTERVAL_SECONDS` to 0.01; body raising `httpx.ConnectError("x")` on calls 1–2 then returning `{}` → result `{"cancelled": False}`, the step row `tries == 3`, `status == "SUCCEEDED"`; a second probe whose body raises `ValueError("bad")` → workflow raises `ValueError`, row `tries == 1`, `status == "FAILED"`, `error["class"] == "ValueError"`.
- `test_tracked_stage_rejects_unknown_step_name` — `tracked_stage("produce.nope", ...)` → workflow raises `RuntimeError("unknown step name produce.nope")`; no rows.
- `test_fail_workflow_pipeline` — run `PRODUCING`, article `CLINICAL_REVIEW`, attempt `RUNNING`, reviewer user exists; `fail_workflow(workflow_name="produce_article", failed_step="produce.clinical_review", error={"class": "RuntimeError", "message": "boom", "step": "produce.clinical_review"})` → run `FAILED` with that error; article `FAILED`; attempt `FAILED` with that error; one `run_failed` notification for the reviewer with dedupe `run_failed:<run>:<IST date today>`.
- `test_fail_workflow_human_action_leaves_run` — run `SUCCEEDED`, article `READY_FOR_REVIEW`, `workflow_name="recheck_article"` → article unchanged, run `SUCCEEDED`, attempt `FAILED`, zero notifications; same with article `FACT_CHECKING` → article `FAILED`.
- `test_fail_workflow_publish` — article `PUBLISHING`, publisher user, `workflow_name="publish_article"` → `PUBLISH_FAILED`, one `publish_failed` notification; article `APPROVED` → unchanged, zero notifications.
- `test_fail_workflow_on_cancelled_attempt_changes_nothing` — attempt `CANCELLED`, run `PRODUCING`, article `SEO` → all unchanged.
- `test_close_cancelled_workflow_cases` — (a) attempt `CANCELLED`, run `PRODUCING` → nothing changes; (b) attempt `RUNNING`, run `PRODUCING`, article `SEO`, `produce_article` → run `FAILED` with `WORKFLOW_CANCELLED_ERROR`, article `FAILED`, attempt `(CANCELLED, None)`; (c) run `CANCELLED`, attempt `RUNNING` → attempt `CANCELLED`, run `CANCELLED`, error `None`; (d) `publish_article`, article `PUBLISHING` → `PUBLISH_FAILED`, run unchanged.
- Regression: Phase 1 `test_tracking.py` and `test_hello_pipeline.py` pass unchanged.

**Implementation notes.**
```python
out = await DBOS.run_step_async(step_options(step_name, retries=retries), _execute)   # dynamic step name (fact 3)
```

**Verification.** `pytest … tests/workflows/test_int_tracking.py tests/workflows/test_tracking.py tests/workflows/test_hello_pipeline.py` → all pass.

**Acceptance covered.** Rules A and B foundations (`ensure_attempt` flags, run walks); Phase 1 deferred minor "private `DBOSWorkflowCancelledError` import in one place"; ARCHITECTURE §5 fork-aware identity.

### INT-4: `produce_article` and the shared production stages (`workflows/produce.py`)

**Files.** Create `pkg/workflows/produce.py`, `backend/tests/workflows/test_int_produce.py`. Modify `pkg/worker.py` (add `import mdcopilot_blog.workflows.produce  # noqa: F401` to the registration imports), `backend/tests/integration/int_helpers.py` (add `selected_candidate`).

**Interfaces.**
- Consumes: D-3 seams; `tracking.tracked_stage`, `untracked_step`, `advance_run`, `advance_article`, `mock_delay`, `stage_step_name`, `fail_workflow`, `close_cancelled_workflow`, `WorkflowCancelledError`, `finish_attempt`, `get_attempt_status`, `get_run_status`; `notifications.notify`, `ready_for_review_event`, `quality_gate_failed_event`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class Production:
      prefix: str              # "produce" | "change_topic" | "regenerate_article" | "regenerate_research" | "regenerate_component" | "recheck"
      workflow_name: str
      run_id: str
      pipeline: bool           # True for produce_article and change_topic (run moves), False for human actions
  async def stage_deep_research(p: Production, *, article_id: str | None, candidate_id: str) -> dict[str, Any]
  async def stage_build_packet(p: Production, *, article_id: str, research_run_id: str) -> dict[str, Any]
  async def stage_write_draft(p: Production, *, article_id: str, packet_id: str | None, instructions: str | None) -> dict[str, Any]
  async def stage_fact_check(p: Production, *, stage: Literal["fact_check", "verify_facts", "fix_pass.verify_facts"], article_id: str, version_id: str) -> dict[str, Any]
  async def stage_clinical(p: Production, *, article_id: str, version_id: str) -> dict[str, Any]
  async def stage_editorial(p: Production, *, article_id: str, version_id: str) -> dict[str, Any]
  async def stage_revise(p: Production, *, article_id: str, base_version_id: str) -> dict[str, Any]
  async def stage_fix_revise(p: Production, *, article_id: str, base_version_id: str, gate_review_id: str) -> dict[str, Any]
  async def stage_seo(p: Production, *, stage: Literal["seo", "fix_pass.seo"], article_id: str, version_id: str) -> dict[str, Any]
  async def stage_gates(p: Production, *, stage: Literal["quality_gates", "fix_pass.quality_gates"], article_id: str, version_id: str,
                        run_kind: GateRunKind, fix_pass_used: bool) -> dict[str, Any]
  async def run_quality_tail(p: Production, tracker: StageTracker, *, article_id: str, version_id: str) -> dict[str, Any]
      # quality_gates (+ fix pass); returns {"cancelled", "version_id", "status"}
  async def run_production(p: Production, tracker: StageTracker, *, start: Literal["deep_research", "write_draft"],
                           article_id: str | None, candidate_id: str | None, instructions: str | None) -> dict[str, Any]
  async def finish_stage(p: Production, *, article_id: str | None) -> dict[str, Any]
  def error_payload_with_step(exc: BaseException, step: str) -> dict[str, object]   # {"class", "message"[:2000], "step"}
  async def fail_workflow_step(workflow_id: str, workflow_name: str, run_id: str, article_id: str | None, failed_step: str,
                               error: dict[str, object], candidate_id: str | None = None) -> None
      # resolves the live article for (run_id, candidate_id) when article_id is None, then tracking.fail_workflow(...)
  class StageTracker:        # plain object in the workflow body: remembers the step currently awaited, for mark_failed
      current: str; article_id: str | None
  @DBOS.workflow(name=WORKFLOW_PRODUCE_ARTICLE)
  async def produce_article(run_id: str, candidate_id: str) -> dict[str, Any]
      # returns {"run_id", "article_id", "version_id", "status", "cancelled"}
  ```
- Test helper `int_helpers.selected_candidate(mock_step_context, sm) -> SelectedRun(run_id: uuid.UUID, candidate_id: uuid.UUID, research_run_id: uuid.UUID)`: `sc = await mock_step_context()`; `make_research_graph(db, kind=ResearchRunKind.BROAD, run_id=sc.call.run_id)` committed; `topic_steps.ideate_topics(sc, research_run_id=, round_no=1, avoid_candidate_ids=[])`; `check_novelty_and_score(sc, candidate_ids=)`; `select_topic(sc, run_id=, mode="auto")`; assert `candidate_id is not None`.

**Behaviour rules.**
1. Every stage function wraps one `tracked_stage(stage_step_name(p.prefix, stage), run_id=p.run_id, workflow_name=p.workflow_name, body=...)` and sets `tracker.current` to that step name before awaiting it (the caller passes the tracker; stage functions take it through `run_production`/`run_quality_tail`, which set it).
2. When `p.pipeline` is True, each stage body first calls `advance_run(target=RunStatus.PRODUCING, stage=<step name>)`; False → return `STOP`. Human-action productions (`pipeline=False`) never call `advance_run`.
3. Article moves and seams exactly as D-3 (moves before the delay for "before", after the seam for "after"). `agent_name`/`agent_version` passed to `tracked_stage`: `deep_research` → `deep_research`/`"1"`, `build_research_packet` → `deep_research`, `write_draft`/`revise`/`fix_pass.revise`/`write_component` → `writer`, fact-check stages → `fact_check`, `clinical_review` → `clinical`, `editorial_review` → `editorial`, SEO stages → `seo`, `quality_gates` stages → None.
4. `stage_deep_research`: `ensure_article` result is the article id; when `article_id` argument is given and differs → `RuntimeError(f"ensure_article returned {got}, expected {article_id}")`.
5. `run_production(start="deep_research")`: `deep_research` → `build_research_packet` → `write_draft(packet_id=<new>)` → then the common tail. `start="write_draft"`: `write_draft(packet_id=None)` (latest packet) → tail. Tail: `fact_check(v)` → `clinical_review(v)` → `editorial_review(v)` → if `revision_required`: `revise(base=v)` → `verify_facts(v2)`, `v = v2` → `seo(v)` → `run_quality_tail(v)`. Any stage returning `cancelled` ends the sequence with `{"cancelled": True}`.
6. `run_quality_tail`: `g = quality_gates(v, run_kind=FULL, fix_pass_used=False)` (prefix `recheck`: `RECHECK`, True). `g.action == "ready"` or `"failed"` → return with the status set by the stage. `g.action == "fix_pass"` → `r = fix_pass.revise(base=v, gate_review_id=g.review_id)` → `fix_pass.verify_facts(r.version_id)` → if `g.seo_rerun or r.title_changed`: `fix_pass.seo(r.version_id)` → `g2 = fix_pass.quality_gates(r.version_id, run_kind=FIX_PASS, fix_pass_used=True)`.
7. Gate stage body after the seam: action `ready` → `advance_article(READY_FOR_REVIEW)` then `notify(ready_for_review_event)`; action `failed`, or `fix_pass` when `fix_pass_used` is True → `advance_article(QUALITY_GATE_FAILED)` then `notify(quality_gate_failed_event(failed_gates=...))`; action `fix_pass` with `fix_pass_used` False → no move, no notification. Title for events is read from `blog_articles.title` in the same step.
8. `finish_stage` (`<prefix>.finish`, tracked): pipeline → if the attempt is not already `SUCCEEDED`: when the run is not `SUCCEEDED`, `advance_run(SUCCEEDED, stage=<finish step>)` (False → `STOP`); then `finish_attempt(SUCCEEDED)`. Human action → `finish_attempt(SUCCEEDED)` only. Returns `{"article_status": <current status or None>}`.
9. `produce_article` body:
   ```text
   p = Production("produce", WORKFLOW_PRODUCE_ARTICLE, run_id, pipeline=True); tracker = StageTracker("produce.open_attempt", None)
   try:
     try:
       opened = produce.open_attempt (tracked): advance_run(PRODUCING, stage) (False → STOP); mock_delay; returns {"trace_id"}
       if cancelled → return {"run_id", "article_id": None, "version_id": None, "status": None, "cancelled": True}
       out = run_production(p, tracker, start="deep_research", article_id=None, candidate_id=candidate_id, instructions=None)
       tracker.article_id is set from the deep_research output
       if out cancelled → return cancelled result
       finish_stage(...)
       return {"run_id", "article_id", "version_id": out.version_id, "status": out.status, "cancelled": False}
     except Exception as exc:
       await untracked_step(stage_step_name("produce", "mark_failed"), fail_workflow_step, workflow_id, WORKFLOW_PRODUCE_ARTICLE,
                            run_id, tracker.article_id, tracker.current, error_payload_with_step(exc, tracker.current), candidate_id)
       raise
   except WorkflowCancelledError:
     await close_cancelled_workflow(workflow_id=DBOS.workflow_id, workflow_name=..., run_id=..., article_id=tracker.article_id)
     raise
   ```
   When `tracker.article_id` is None at failure time, `fail_workflow_step` looks up the live article for `(run_id, candidate_id)` (status not `REJECTED`/`SUPERSEDED`) and uses it when found.
10. Original attempt on a `CANCELLED` run: `open_attempt` returns `STOP` (attempt recorded `CANCELLED` by `ensure_attempt`), so the workflow returns the cancelled result with no article and no further steps.
11. Step outputs are JSON-safe (`model_dump(mode="json")`, ids as `str`).

**Tests to write first** (`test_int_produce.py`; fixtures `dbos_runtime`, `committed_seed`, `mock_step_context`, `sessionmaker_committing`; a reviewer user is created with `create_user_committed`; workflows started with `SetWorkflowID(f"produce-{run}-{cand}")` + `SetWorkflowTimeout(1800)` + `DBOS.start_workflow_async(produce_article, str(run), str(cand))`; results awaited with `wait_workflow`).
- `test_golden_path_reaches_ready_for_review` — with `record_article_statuses`: result `status == "READY_FOR_REVIEW"`, `cancelled is False`; step names in order `["produce.open_attempt", "produce.deep_research", "produce.build_research_packet", "produce.write_draft", "produce.fact_check", "produce.clinical_review", "produce.editorial_review", "produce.seo", "produce.quality_gates", "produce.finish"]`, all `SUCCEEDED`, `tries == 1`; recorded statuses `[FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW, SEO, READY_FOR_REVIEW]`; run `SUCCEEDED`, `stage == "produce.finish"`; one attempt `(workflow_name, status) == ("produce_article", "SUCCEEDED")`; article `current_version_id == result["version_id"]`; exactly 1 version (`change_kind == "draft"`), 1 packet, 1 `deep` research run for the article; reviews on that version: `fact_check` `PASS` with `independent_check is True`, `clinical` `CLEAR`, `editorial` `COMPLETED`, `quality_gate` `PASSED` with `gate_run_kind == "full"`; every `blog_llm_calls` row of the run has `trace_id == run.trace_id`, `attempt_id` == the attempt id and `agent_run_id` not null; one `ready_for_review` notification for the reviewer with dedupe `ready_for_review:{article}:{version}`.
- `test_revision_path_runs_revise_and_verify_facts` — monkeypatch `dbos_runtime.settings` and `dbos_runtime.gateway` to `build_gateway(settings.model_copy(update={"mock_scenario": "revision_path"}), rt.sessionmaker, rt.prompts)` → steps between `produce.editorial_review` and `produce.seo` are `["produce.revise", "produce.verify_facts"]`; recorded statuses `[FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW, DRAFTING, FACT_CHECKING, SEO, <READY_FOR_REVIEW or QUALITY_GATE_FAILED>]`; 2 versions (`draft`, `revision` with `parent_version_id` = v1); a `fact_check` review exists for v1 and for v2; the latest `quality_gate` review is on v2; `current_version_id` = v2.
- `test_fix_pass_runs_once` — parametrized `seo_rerun` in `(False, True)`: monkeypatch `quality_steps.run_quality_gates` with a wrapper recording `(run_kind, fix_pass_used)` that calls the real function and, on its first call only, returns `GateStepResult(review_id=r.review_id, version_id=r.version_id, report=r.report, decision=FixPassDecision(action="fix_pass", seo_rerun=seo_rerun, findings=[RevisionFinding(finding_id="gate:word_count", origin="quality_gate", description="forced", location="article", recommended_revision=None, required=True)], suggestion=None))` → recorded calls `[(FULL, False), (FIX_PASS, True)]`; steps after `produce.quality_gates` are `["produce.fix_pass.revise", "produce.fix_pass.verify_facts"] + (["produce.fix_pass.seo"] if seo_rerun or <fix_pass.revise output title_changed> else []) + ["produce.fix_pass.quality_gates", "produce.finish"]`; 2 versions, the second with `change_kind == "fix_pass"`; final article status is `READY_FOR_REVIEW` or `QUALITY_GATE_FAILED` and equals the status implied by the last gate review (`PASSED` → READY).
- `test_failed_gates_set_quality_gate_failed_and_notify` — wrapper returns the real report with `decision=FixPassDecision(action="failed", seo_rerun=False, findings=[], suggestion="change_topic")` → no `fix_pass.*` steps; article `QUALITY_GATE_FAILED`; run `SUCCEEDED`; one `quality_gate_failed` notification for the reviewer, dedupe `quality_gate_failed:{article}:{version}`.
- `test_stage_failure_marks_article_run_and_attempt_failed` — monkeypatch `quality_steps.clinical_review` raising `RuntimeError("boom")` → workflow raises `RuntimeError`; run `FAILED`, `error == {"class": "RuntimeError", "message": "boom", "step": "produce.clinical_review"}`; attempt `FAILED` with the same error; article `FAILED`; row `produce.clinical_review` `FAILED`; DBOS step names end with `"produce.mark_failed"`; one `run_failed` notification (dedupe `run_failed:{run}:{IST date}`).
- `test_failure_before_article_exists` — monkeypatch `article_steps.ensure_article` raising `LookupError("no topic")` → run `FAILED` with `error["step"] == "produce.deep_research"`; zero articles for the run.
- `test_insufficient_evidence_fails_article` — monkeypatch `research.steps.run_deep_research` raising `InsufficientEvidence("rr", 1, 5, 2)` → article `FAILED` (from `DRAFTING`); run error class `InsufficientEvidence`.
- `test_produce_on_succeeded_run_reopens_it` — set run `SUCCEEDED` first; `record_run_statuses` → recorded `[QUEUED, PRODUCING, SUCCEEDED]`; attempt `SUCCEEDED`.
- `test_produce_on_cancelled_run_changes_nothing` — run `CANCELLED` → result `cancelled is True`; attempt `CANCELLED`; zero articles; zero `blog_agent_runs` rows; run `CANCELLED`.
- `test_cancel_between_stages_stops_production` — wrapper around `quality_steps.clinical_review` calls the real seam, then `finish_attempt(CANCELLED)` + `set_run_status(CANCELLED)` (what the runs API does) → result `cancelled is True`; no `produce.editorial_review` row; article `CLINICAL_REVIEW`; run `CANCELLED`; attempt `CANCELLED`.
- `test_mock_delay_runs_before_each_seam_call` — shared list; monkeypatch `tracking.mock_delay` to append `"delay"` and `article_steps.write_draft` to append `"write_draft"` then delegate → the entry before `"write_draft"` is `"delay"`; the count of `"delay"` equals the count of tracked stages executed (10).
- `test_workflow_timeout_fails_run_and_in_progress_article` — `dbos_runtime.settings` with `mock_step_delay_seconds=2.0`; enqueue through `QUEUE_PIPELINE` with `SetWorkflowTimeout(3)` → awaiting raises (message contains `cancelled`); within `WAIT_SECONDS` run `FAILED` with `WORKFLOW_CANCELLED_ERROR`; attempt `(CANCELLED, None)`; any article of the run is `FAILED`.

**Implementation notes.**
```python
# the only way to start a child from a workflow (fact 2): body, not a step; always an explicit timeout
with SetWorkflowID(child_id), SetWorkflowTimeout(timeout_seconds):
    await DBOS.enqueue_workflow_async(QUEUE_PIPELINE, produce_article, run_id, candidate_id)
```

**Verification.** `pytest … tests/workflows/test_int_produce.py` → all pass, each test under 60 s.

**Acceptance covered.** Phase 4 "`produce_article` P1–P3"; Phase 5 "`produce_article` P4–P10", "one fix pass" orchestration, "gates recorded on the final version, fact check for that exact version"; Rule B for `produce_article`; article status rules 2 (`mark_failed`).

### INT-5: `discover_topics` and `regenerate_topics` (`workflows/discover.py`)

**Files.** Create `pkg/workflows/discover.py`, `backend/tests/workflows/test_int_discover.py`. Modify `pkg/worker.py` (registration import).

**Interfaces.**
- Consumes: `research.steps.gather_signals`, `build_ledger`, `synthesize_research`; `topic_steps.ideate_topics`, `check_novelty_and_score`, `select_topic`, `create_manual_candidate`, `promote_candidate`; `services.config.pillar_for_date`; `produce.produce_article`; `client.timeout_for_workflow`; tracking helpers.
- Produces:
  ```python
  @DBOS.workflow(name=WORKFLOW_DISCOVER_TOPICS)
  async def discover_topics(run_id: str) -> dict[str, Any]
      # {"run_id", "candidate_id": str | None, "topic_id": str | None, "shortfall": bool, "produce_workflow_id": str | None, "cancelled": bool}
  @DBOS.workflow(name=WORKFLOW_REGENERATE_TOPICS)
  async def regenerate_topics(run_id: str) -> dict[str, Any]    # same keys
  def produce_workflow_id(run_id: str, candidate_id: str) -> str   # f"produce-{run_id}-{candidate_id}"
  ```

**Behaviour rules.**
1. `discover.open_attempt` (tracked): if the attempt row was pre-created with a `restart-` workflow id and the run status is `SUCCEEDED`, `FAILED` or `CANCELLED` → `set_run_status(QUEUED)`; then `advance_run(RESEARCHING)` (False → `STOP`); `mock_delay`; returns `{"topic", "pillar", "audience", "tone", "run_date", "created_by"}` read from `blog_runs.params` (`topic`, `pillar`, `audience`, `tone`; missing → None), `run_date` ISO, `created_by` str or None.
2. Manual topic (`topic` not None): `discover.manual_topic` (tracked, agent `ideation`): `pillar_key = PillarKey(pillar)` when given else `await pillar_for_date(db, run_date)`; `create_manual_candidate(sc, run_id=, topic=, pillar_key=, audience=, tone=)`; then `advance_run(TOPICS_READY)`; returns `{"candidate_id": ids[0], "round"}`. Then `discover.select_topic` (tracked): `promote_candidate(db, candidate_id=, selected_by=created_by)` + commit; `advance_run(PRODUCING)`; returns `{"candidate_id", "topic_id", "shortfall": False}`. D2–D6 are not executed.
3. Research path: `discover.gather_signals` (tracked, agent `research`): `advance_run(RESEARCHING)`; `gather_signals(sc, pillar_key=<rule-2 pillar>)`; output `GatherSignalsResult` dump. `discover.build_ledger`: `build_ledger(sc, research_run_id=)`. `discover.synthesize_research` (agent `research`): `synthesize_research(sc, research_run_id=)`.
4. Ideation loop in the body: `round_no = 1`, `avoid: list[str] = []`. Repeat: `discover.ideate_topics` (tracked, agent `ideation`) → `ideate_topics(sc, research_run_id=, round_no=, avoid_candidate_ids=[UUID(a) for a in avoid])`, output adds `max_regeneration_rounds = sc.config.novelty.max_regeneration_rounds`; `discover.check_novelty_and_score` (tracked) → `check_novelty_and_score(sc, candidate_ids=)`; `non_rejected = len(passed_ids) + len(warned_ids)`; `final = non_rejected >= 3 or round_no >= 1 + max_regeneration_rounds`; when `final`, the same step calls `advance_run(TOPICS_READY)`; output adds `final`. If not `final`: `avoid += candidate_ids`, `round_no += 1`, repeat. (Default config: at most 3 ideation rounds.)
5. `discover.select_topic` (tracked): `mode = sc.config.topic_selection_mode`; `r = select_topic(sc, run_id=, mode=mode)`; `r.candidate_id` not None → `advance_run(PRODUCING)`; else `advance_run(WAITING_FOR_TOPIC)`; output `{"candidate_id", "topic_id", "shortfall", "mode"}`.
6. Body after `select_topic` with a candidate: enqueue `produce_article(run_id, candidate_id)` on `QUEUE_PIPELINE` under `SetWorkflowID(produce_workflow_id(...))` + `SetWorkflowTimeout(timeout_for_workflow(WORKFLOW_PRODUCE_ARTICLE, rt.settings))` (read `rt = get_runtime()` for settings only); `produce_workflow_id` goes in the result.
7. `discover.finish` (tracked): `finish_attempt(SUCCEEDED)` unless already `SUCCEEDED`; the run status is not changed.
8. Failure/cancel wrapper as INT-4 rule 9 with prefix `discover`, `article_id=None`.
9. `regenerate_topics.open_attempt` (tracked): run `SUCCEEDED`/`FAILED` → `advance_run(RESEARCHING)` (walks through `QUEUED`); `QUEUED` → `RESEARCHING`; `TOPICS_READY`/`WAITING_FOR_TOPIC` → no move; any other status → `InvalidTransition(Entity.RUN, status, RESEARCHING)`. Output: `research_run_id` = newest `blog_research_runs` of kind `broad` for the run (none → `LookupError(f"run {run_id} has no broad research run")`), `round_no = max(round) + 1` over the run's candidates (1 when none), `avoid` = every candidate id of the run, `has_live_article` = any `blog_articles` of the run with status not in `REJECTED`, `SUPERSEDED`.
10. `regenerate_topics` body: one `regenerate_topics.ideate_topics` (with that round and avoid list) → `regenerate_topics.check_novelty_and_score` (`final` is always True; moves to `TOPICS_READY`, which from `WAITING_FOR_TOPIC` is a direct edge and from `TOPICS_READY` a no-op) → `regenerate_topics.select_topic` with `mode = "manual"` when `has_live_article` else `sc.config.topic_selection_mode` → enqueue production as rule 6 when selected → `regenerate_topics.finish`.

**Tests to write first** (`test_int_discover.py`; `dbos_runtime`, `committed_seed`, `make_run`; reviewer user; start with `SetWorkflowID(f"manual-{run}")` + `SetWorkflowTimeout(900)`).
- `test_auto_mode_selects_and_enqueues_production` — `record_run_statuses` → result `candidate_id` not None, `shortfall is False`, `produce_workflow_id == f"produce-{run}-{cand}"`; step names `["discover.open_attempt", "discover.gather_signals", "discover.build_ledger", "discover.synthesize_research", "discover.ideate_topics", "discover.check_novelty_and_score", "discover.select_topic", "discover.finish"]`, all `SUCCEEDED`; recorded statuses start `[RESEARCHING, TOPICS_READY, PRODUCING]`; 3 candidates with `round == 1`, exactly one `SELECTED`; child row: `parent_workflow_id == f"manual-{run}"`, `queue_name == "pipeline"`, `workflow_timeout_ms == 1800000`; after `wait_workflow(child)`: run `SUCCEEDED`, article `READY_FOR_REVIEW`; attempts `[("discover_topics", "SUCCEEDED"), ("produce_article", "SUCCEEDED")]`.
- `test_manual_mode_stops_waiting_for_topic` (fixture `manual_topic_selection`) — run `WAITING_FOR_TOPIC`; attempt `SUCCEEDED`; result `candidate_id is None`, `produce_workflow_id is None`; `DBOS.list_workflows_async(workflow_id_prefix=f"produce-{run}")` → `[]`; 3 candidates, none `SELECTED`; select step output `mode == "manual"`.
- `test_regeneration_loop_is_bounded` — fakes on `topic_steps`: `ideate_topics` records `(round_no, [str(a) for a in avoid])` and returns 3 fresh uuid7 ids; `check_novelty_and_score` returns `passed=[ids[0]], warned=[], rejected=ids[1:]`; `select_topic` returns `SelectResult(candidate_id=None, topic_id=None, shortfall=True)` and records `mode` → ideate records `[(1, []), (2, <3 ids of round 1>), (3, <6 ids of rounds 1–2>)]`; check called 3 times; select called once with `"auto"`; result `shortfall is True`; run `WAITING_FOR_TOPIC`; recorded run statuses `[RESEARCHING, TOPICS_READY, WAITING_FOR_TOPIC]`; 3 `discover.ideate_topics` rows with distinct `dbos_step_id`.
- `test_regeneration_stops_when_three_pass` — as above but round 2 returns 3 passed → ideate rounds `[1, 2]`.
- `test_manual_topic_skips_research` — run params `{"topic": "AI scribes and specialist wait times", "pillar": "A"}`; spy on `create_manual_candidate` (delegates to the real seam) → called with `topic="AI scribes and specialist wait times"`, `pillar_key=PillarKey.A`, `audience=None`, `tone=None`; steps `["discover.open_attempt", "discover.manual_topic", "discover.select_topic", "discover.finish"]`; candidate `is_manual is True` and `SELECTED`; after the child finishes run `SUCCEEDED`.
- `test_pillar_comes_from_params_or_rotation` — spy on `gather_signals` recording `pillar_key`; run A: params `{}`, `run_date=date(2026, 1, 15)` → recorded value equals `await pillar_for_date(db, date(2026, 1, 15))` computed in the test; run B: params `{"pillar": "NARRATIVE"}` → `PillarKey.NARRATIVE` (both with fakes for ideate/check/select returning a shortfall so no production starts).
- `test_research_failure_fails_run` — `gather_signals` raising `RuntimeError("feeds down")` → run `FAILED`, `error["step"] == "discover.gather_signals"`; attempt `FAILED`; `run_failed` notification for the reviewer.
- `test_insufficient_evidence_at_build_ledger_fails_run` — `build_ledger` raising `InsufficientEvidence("rr", 2, 5, 3)` → run error class `InsufficientEvidence`, step `discover.build_ledger`.
- `test_discover_on_cancelled_run_changes_nothing` — `make_run(status=CANCELLED)` → result `cancelled is True`; attempt `CANCELLED`; zero step rows; zero candidates.
- `test_regenerate_topics_on_waiting_run` (`manual_topic_selection`) — discover to `WAITING_FOR_TOPIC`; spy on `ideate_topics`; start `regenerate_topics` under `regen-topics-{run}-{uuid7}` → spy called with `round_no=2` and the 3 round-1 ids; recorded run statuses `[TOPICS_READY, WAITING_FOR_TOPIC]`; 3 candidates with `round == 2`; no production child.
- `test_regenerate_topics_on_succeeded_run_keeps_live_article` — auto discover + production to `SUCCEEDED`; spy on `select_topic` → mode `"manual"`; recorded run statuses `[QUEUED, RESEARCHING, TOPICS_READY, WAITING_FOR_TOPIC]`; article still `READY_FOR_REVIEW`; `list_workflows_async(workflow_id_prefix=f"produce-{run}")` has exactly 1 row (the original).
- `test_regenerate_topics_without_broad_research_fails` — manual-topic run (rule 2) finished → `regenerate_topics` → run `FAILED`, `error["message"] == f"run {run} has no broad research run"`.

**Implementation notes.** Enqueue from the body exactly as INT-4's note; never from a step (fact 2).

**Verification.** `pytest … tests/workflows/test_int_discover.py` → all pass.

**Acceptance covered.** Phase 3 "`discover_topics` D1–D7 auto and manual; `regenerate_topics`" (primary), "Embeddings + novelty engine + regeneration loop ≤ 2 rounds" (INT loop), "Always exactly 3 candidates or flagged shortfall after 2 rounds" (INT workflow part), "Manual mode stops at `WAITING_FOR_TOPIC`"; Rule B for `regenerate_topics`.

### INT-6: Human-action workflows and `change_topic` (`workflows/human_actions.py`)

**Files.** Create `pkg/workflows/human_actions.py`, `backend/tests/workflows/test_int_human_actions.py`. Modify `pkg/worker.py` (registration import).

**Interfaces.**
- Consumes: `produce.Production`, `StageTracker`, the stage functions, `run_production`, `run_quality_tail`, `finish_stage`; `article_steps.ensure_article`; `publication_steps.publish_article`; `services.config.load_effective_config`; `notifications.publish_failed_event`; `DBOS.cancel_workflow_async`; tracking helpers.
- Produces (registered names and argument order exactly as D-1):
  ```python
  @DBOS.workflow(name=WORKFLOW_CHANGE_TOPIC) async def change_topic(run_id: str, candidate_id: str) -> dict[str, Any]
  @DBOS.workflow(name=WORKFLOW_REGENERATE_COMPONENT) async def regenerate_component(article_id: str, component: str, section_key: str | None, instructions: str | None) -> dict[str, Any]
  @DBOS.workflow(name=WORKFLOW_REGENERATE_ARTICLE) async def regenerate_article(article_id: str, instructions: str | None) -> dict[str, Any]
  @DBOS.workflow(name=WORKFLOW_REGENERATE_RESEARCH) async def regenerate_research(article_id: str) -> dict[str, Any]
  @DBOS.workflow(name=WORKFLOW_RECHECK_ARTICLE) async def recheck_article(article_id: str) -> dict[str, Any]
  @DBOS.workflow(name=WORKFLOW_PUBLISH_ARTICLE) async def publish_article(article_id: str, version_id: str, as_draft: bool) -> dict[str, Any]
  # each returns {"article_id", "version_id": str | None, "status": str | None, "cancelled": bool}
  APPROVAL_STATUSES: frozenset[ArticleStatus]   # {APPROVED, SCHEDULED, EXPORTED, PUBLISHING, PUBLISHED, PUBLISH_FAILED}
  PRODUCTION_WORKFLOWS: frozenset[str]          # {produce_article, change_topic, regenerate_article, regenerate_research, regenerate_component, recheck_article}
  ```

**Behaviour rules.**
1. Human-action `open_attempt` (prefixes `regenerate_component`, `regenerate_article`, `regenerate_research`, `recheck`, `publish`): `tracked_stage(stage_step_name(prefix, "open_attempt"), run_id=None, article_id=article_id, ...)`, so the step resolves the run from `blog_articles.run_id` and `ensure_attempt(..., respect_run_cancel=False)` records the attempt on that run (the workflow name is in `HUMAN_ACTION_WORKFLOWS`). The body calls `mock_delay` and returns `{"run_id", "article_status", "current_version_id", "candidate_id"}` read from the article row. Later stages pass that `run_id`. No run status is read or changed (Rule A). Productions use `Production(prefix, workflow_name, run_id, pipeline=False)`.
2. `regenerate_component`: `write_component` (D-3; no status move) → `fact_check(v)` (moves to `FACT_CHECKING`) → `seo(v)` only when `write_component.title_changed` → `run_quality_tail` with the `regenerate_component` prefix (run kind `full`, then the fix pass) → `finish`.
3. `regenerate_article`: `run_production(start="write_draft", article_id=article_id, instructions=instructions)` → `finish`.
4. `regenerate_research`: candidate = `blog_articles.candidate_id` (returned by `open_attempt`) → `run_production(start="deep_research", article_id=article_id, candidate_id=...)` → `finish`. `run_deep_research` gets `avoid_source_ids=()`.
5. `recheck_article`: version = `current_version_id` (None → `LookupError`) → `recheck.fact_check` with **no** status move → `recheck.quality_gates` (`run_kind=RECHECK`, `fix_pass_used=True`; `ready` → `READY_FOR_REVIEW`, anything else → `QUALITY_GATE_FAILED`, D-5 notification) → `recheck.finish`. No `fix_pass.*` stages.
6. Article status rule 1 (CONTRACT §5.7): the first status write happens only after `write_component` (component), `write_draft` (article, research) or `fact_check` (recheck) succeeds; a failure before that leaves the status unchanged (`fail_workflow` only fails `IN_PROGRESS_ARTICLE_STATUSES`).
7. `publish_article`: `publish.publish` (tracked, `retries=False`): `config = load_effective_config(db, rt.settings, run_id=run_id)`; `o = publication_steps.publish_article(rt.sessionmaker, settings=rt.settings, config=config, article_id=, version_id=, as_draft=)`; `o.article_status == PUBLISH_FAILED` → `notify(publish_failed_event(..., error=o.error or "unknown error"))`; output `PublishOutcome` dump. `publish.finish` → attempt `SUCCEEDED`. Exceptions (including `PublishingDisabled`) → `publish.mark_failed` → `fail_workflow` (article `PUBLISHING` → `PUBLISH_FAILED` + notification; otherwise unchanged).
8. `change_topic.open_attempt` (tracked, pipeline): before any run move, collect the run's live articles (status not `REJECTED`/`SUPERSEDED`) whose `candidate_id != candidate_id`; if any is in `APPROVAL_STATUSES` → raise `InvalidTransition(Entity.ARTICLE, status, SUPERSEDED)` (the run stays as it was: `fail_workflow`'s `set_run_status(FAILED)` from `SUCCEEDED` is illegal and is logged and skipped). Otherwise `advance_run(PRODUCING)` (Rule B).
9. `change_topic.supersede` (tracked, pipeline): (a) `new_article_id = ensure_article(sc, run_id=, candidate_id=)`; (b) old articles = rule-8 set; old candidates = their `candidate_id`s; (c) cancel set = active attempts (`ENQUEUED`/`RUNNING`) of the run with `workflow_name in PRODUCTION_WORKFLOWS` and `dbos_workflow_id != DBOS.workflow_id`, plus `produce-{run_id}-{old_candidate}` for each old candidate; (d) in one transaction: those attempts → `CANCELLED` with `finished_at = now`; commit **before** (e) `await DBOS.cancel_workflow_async(id)` for each id (ids unknown to DBOS are skipped: check `list_workflows_async(workflow_ids=[id])` first); (f) for each old article `advance_article(SUPERSEDED)` and `UPDATE blog_articles SET superseded_by_article_id = new_article_id`; old candidates with status `SELECTED` → `SUPERSEDED`; commit. Output `{"new_article_id", "superseded_article_ids", "cancelled_workflow_ids"}`.
10. `change_topic` body: `open_attempt` → `supersede` → `run_production(start="deep_research", article_id=new_article_id, candidate_id=candidate_id)` → `finish` (run → `SUCCEEDED`).
11. All six wrappers use INT-4 rule 9's failure/cancel structure; `tracker.article_id` = the argument (`change_topic`: the new article id once known).

**Tests to write first** (`test_int_human_actions.py`; `dbos_runtime`, `committed_seed`; articles from `make_article_graph(db, status=..., with_seo=True, reviews=(FACT_CHECK, CLINICAL, EDITORIAL, QUALITY_GATE))` committed, then the run set to `SUCCEEDED` with `finished_at` fixed via SQL; reviewer and publisher users; each workflow started under its D-1 id with timeout 1800).
- `test_regenerate_component_section` — `regenerate_component(article, "section", "evidence", None)` with `record_article_statuses`: steps `["regenerate_component.open_attempt", "regenerate_component.write_component", "regenerate_component.fact_check"] + (["regenerate_component.seo"] if title_changed else []) + ["regenerate_component.quality_gates", "regenerate_component.finish"]` (from the `write_component` output); versions +1, the new one `change_kind == "component_regeneration"` with `parent_version_id` = previous current; every section except `evidence` has identical `heading` and `body_markdown` to the parent; `fact_check` and `quality_gate` (`full`) reviews exist on the new version; recorded statuses `[FACT_CHECKING, READY_FOR_REVIEW]` when no SEO step ran; run `status`, `stage`, `finished_at`, `error` equal their values before the workflow (Rule A); one attempt `("regenerate_component", "SUCCEEDED")` on the article's run.
- `test_regenerate_component_failure_before_write_keeps_status` — `article_steps.regenerate_component` raising `RuntimeError("writer down")` → article `READY_FOR_REVIEW`; attempt `FAILED` with `error["step"] == "regenerate_component.write_component"`; run unchanged; zero `run_failed` notifications.
- `test_regenerate_component_failure_in_fact_check_fails_article` — `quality_steps.fact_check` raising → article `FAILED`; run `SUCCEEDED`.
- `test_regenerate_article_keeps_old_versions` — `regenerate_article(article, "Tighten the evidence section.")`; spy on `write_draft` → called with `instructions="Tighten the evidence section."` and `packet_id` == the graph's packet; steps `["regenerate_article.open_attempt", "regenerate_article.write_draft", "regenerate_article.fact_check", "regenerate_article.clinical_review", "regenerate_article.editorial_review", "regenerate_article.seo", "regenerate_article.quality_gates", "regenerate_article.finish"]`; the old version row still exists; new version `change_kind == "article_regeneration"`; recorded statuses `[DRAFTING, FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW, SEO, READY_FOR_REVIEW]`.
- `test_regenerate_research_adds_packet_version` — steps `["regenerate_research.open_attempt", "regenerate_research.deep_research", "regenerate_research.build_research_packet", "regenerate_research.write_draft", "regenerate_research.fact_check", "regenerate_research.clinical_review", "regenerate_research.editorial_review", "regenerate_research.seo", "regenerate_research.quality_gates", "regenerate_research.finish"]` (golden fixtures: no revise, no fix pass); packets for the article have versions `[1, 2]`; the new article version's `research_packet_id` == packet version 2; the first recorded status is `DRAFTING`.
- `test_regenerate_research_from_failed_article` — graph status `FAILED` (no reviews) → recorded statuses start `[DRAFTING, FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW]`; final `READY_FOR_REVIEW`.
- `test_recheck_after_gate_failure` — graph `QUALITY_GATE_FAILED`, `reviews=()`; spy on `run_quality_gates` → called with `run_kind=GateRunKind.RECHECK`, `fix_pass_used=True`; steps `["recheck.open_attempt", "recheck.fact_check", "recheck.quality_gates", "recheck.finish"]`; recorded statuses `[READY_FOR_REVIEW]`; latest gate review `gate_run_kind == "recheck"` on the current version; one `ready_for_review` notification.
- `test_recheck_fact_check_failure_keeps_status` — graph `QUALITY_GATE_FAILED`; `fact_check` raising → status `QUALITY_GATE_FAILED`; attempt `FAILED`.
- `test_human_action_on_cancelled_run_runs` — run `CANCELLED`; `recheck_article` → attempt `SUCCEEDED`; run `CANCELLED`, `finished_at` unchanged.
- `test_change_topic_supersedes_and_produces` — auto discover + production to `SUCCEEDED`; a second candidate from round 1 with status `PASSED` promoted with `promote_candidate` + commit; `record_run_statuses`; start `change_topic` under `change-topic-{run}-{cand2}` → steps `["change_topic.open_attempt", "change_topic.supersede", "change_topic.deep_research", "change_topic.build_research_packet", "change_topic.write_draft", "change_topic.fact_check", "change_topic.clinical_review", "change_topic.editorial_review", "change_topic.seo", "change_topic.quality_gates", "change_topic.finish"]`; old article `SUPERSEDED` with `superseded_by_article_id` = new article id; old candidate `SUPERSEDED`; new article `READY_FOR_REVIEW`; recorded run statuses `[QUEUED, PRODUCING, SUCCEEDED]`; attempts `discover_topics, produce_article, change_topic` all `SUCCEEDED`.
- `test_change_topic_cancels_in_flight_production` — `mock_step_delay_seconds=1.0`; enqueue production for candidate 1; wait until a `produce.write_draft` row is `RUNNING`; promote candidate 2 and start `change_topic` → `supersede` output `cancelled_workflow_ids` contains `produce-{run}-{cand1}`; that DBOS workflow status becomes `CANCELLED`; its attempt `CANCELLED`; run ends `SUCCEEDED` (never `FAILED`); old article `SUPERSEDED`.
- `test_change_topic_refuses_approved_article` — graph `APPROVED` with `approved=True`, run `SUCCEEDED`; another candidate promoted → workflow raises `InvalidTransition`; article `APPROVED`; run `SUCCEEDED`; attempt `FAILED`.
- `test_publish_article_outcomes` — monkeypatch `publication_steps.publish_article`: (a) returns `PublishOutcome(publication_id=<uuid7>, status=PublicationStatus.PUBLISHED, article_status=ArticleStatus.PUBLISHED, external_post_id="42", published_url="http://localhost:3000/blog/golden", error=None)` → attempt `SUCCEEDED`, zero notifications, run unchanged; (b) returns `PublishOutcome(publication_id=<uuid7>, status=PublicationStatus.FAILED, article_status=ArticleStatus.PUBLISH_FAILED, external_post_id=None, published_url=None, error="timeout")` → one `publish_failed` notification per publisher-permission holder with dedupe `publish_failed:{article}:{version}`.
- `test_publish_article_exception_from_publishing` — fake sets the article `APPROVED → PUBLISHING` with `set_article_status_committed`, then raises `RuntimeError("socket closed")` → article `PUBLISH_FAILED`; attempt `FAILED`; one `publish_failed` notification.
- `test_publish_article_publishing_disabled` — real seam with default settings (`publishing_enabled=False`) → attempt `FAILED`, `error["class"] == "PublishingDisabled"`; article `APPROVED`; zero notifications.

**Verification.** `pytest … tests/workflows/test_int_human_actions.py` → all pass.

**Acceptance covered.** Phase 4 "`regenerate_component`, `regenerate_research`" (primary), "Regenerating one section → exactly one new version, other sections byte-identical" and "Regenerating research → new packet version, old kept" (INT workflow tests); Phase 5 "`recheck_article`, full `regenerate_article`" (primary), "Regenerating the article creates new versions and keeps old"; Phase 7 "`publish_article` workflow"; Rule A; article status rules 1–3; ARCHITECTURE §5.3 `change_topic`.

### INT-7: Schedules, `apply_schedule`, `publish_due`, `maintenance`

**Files.** Modify `pkg/workflows/schedules.py`, `pkg/workflows/names.py` (only the `DAILY_TARGET_WORKFLOW` line), `pkg/worker.py` (registration imports), `backend/tests/workflows/test_schedules.py` (Phase 1 tests whose child now runs `discover_topics`). Create `pkg/workflows/publish_due.py`, `pkg/workflows/maintenance.py`, `backend/tests/workflows/test_int_schedules.py`, `backend/tests/workflows/test_int_publish_due.py`, `backend/tests/workflows/test_int_maintenance.py`.

**Interfaces.**
- Produces (`schedules.py`; Phase 1 names keep their signatures, new keyword arguments have defaults):
  ```python
  STEP_DAILY_LOCAL_DATE = "daily.local_date"          # INT-local step name (worker only)
  DAILY_TARGETS: dict[str, Callable[[str], Coroutine[Any, Any, dict[str, object]]]]   # {hello_pipeline, discover_topics}
  PUBLISH_DUE_CRON = "*/5 * * * *"; MAINTENANCE_CRON = "30 2 * * *"
  def cron_for(schedule: ScheduleConfig) -> str                       # "MM HH * * *"
  async def load_schedule(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> ScheduleConfig   # effective config; ConfigError propagates
  async def apply_daily_schedule(settings: Settings, schedule: ScheduleConfig | None = None) -> None   # None → env time/timezone (Phase 1)
  async def apply_all_schedules(settings: Settings, schedule: ScheduleConfig, *, activate_background: bool) -> None
  async def catch_up_today(settings: Settings, now: datetime, *, schedule: ScheduleConfig | None = None) -> str | None
  async def create_daily_run_step(run_date_iso: str) -> str | None     # Phase 1 step, extended skip rules
  @DBOS.workflow(name=WORKFLOW_DAILY_TRIGGER) async def daily_trigger(scheduled_at: datetime, context: Any) -> str | None
  @DBOS.workflow(name=WORKFLOW_APPLY_SCHEDULE) async def apply_schedule() -> dict[str, Any]   # {"time", "timezone", "scheduler_enabled"}
  ```
- Produces (`publish_due.py`): `MAX_DUE_PER_TICK = 3`; `@DBOS.workflow(name=WORKFLOW_PUBLISH_DUE) async def publish_due(scheduled_at: datetime, context: Any) -> dict[str, Any]` → `{"due": int, "outcomes": list[dict]}`.
- Produces (`maintenance.py`): `PRUNE_BATCH_SIZE = 500`, `PRUNE_MAX_BATCHES = 20`, `TERMINAL_DBOS_STATUSES = ["SUCCESS", "ERROR", "CANCELLED", "MAX_RECOVERY_ATTEMPTS_EXCEEDED"]`; `async def prune_dbos_records(*, cutoff: datetime, exclude_workflow_ids: Collection[str] = ()) -> int`; `@DBOS.workflow(name=WORKFLOW_MAINTENANCE) async def maintenance(scheduled_at: datetime, context: Any) -> dict[str, Any]` → keys `sync_posts`, `prune_dbos`, `feed_health`, `reconcile_costs`, each `{"status": "ok" | "failed" | "disabled", ...}`.

**Behaviour rules.**
1. `names.py`: `DAILY_TARGET_WORKFLOW = WORKFLOW_DISCOVER_TOPICS`. `daily_trigger` enqueues `DAILY_TARGETS[DAILY_TARGET_WORKFLOW]` with `SetWorkflowTimeout(timeout_for_workflow(DAILY_TARGET_WORKFLOW, settings))` (900 s for discover).
2. `daily_trigger`: `local = await untracked_step(STEP_DAILY_LOCAL_DATE, ...)` computes `scheduled_at.astimezone(ZoneInfo(effective timezone)).date().isoformat()` in a step (the effective timezone comes from `load_schedule`); `STEP_DAILY_LOCAL_DATE` is excluded from the `known_step_names()` check (INT-local constant, `untracked_step` accepts it through an explicit `allow_local=True` argument). Then Phase 1 behaviour with `create_daily_run_step(local)`.
3. `create_daily_run_step(run_date_iso)` order: (a) a daily run exists → Phase 1 (return it if still `QUEUED`, else None); (b) an article with `run_date == date` and status in `{READY_FOR_REVIEW, QUALITY_GATE_FAILED, APPROVED, SCHEDULED, EXPORTED, PUBLISHING, PUBLISHED, PUBLISH_FAILED}` exists → `notify(daily_run_skipped_event(day=, reason=f"an article for this date is already {status}", article_id=<newest such article>, run_id=None))`, return None; (c) an active manual run for the date (Phase 1 rule: status not `FAILED`/`CANCELLED`) → `notify(daily_run_skipped_event(day=, reason="a manual run for this date is active", article_id=None, run_id=<that run>))`, return None; (d) insert as Phase 1.
4. `apply_all_schedules` builds three `ScheduleInput`s and calls `DBOS.apply_schedules_async` once: `daily_generation` (`daily_trigger`, `cron_for(schedule)`, `schedule.timezone`, queue `pipeline`, `automatic_backfill=False`, context `{"source": "schedule"}`); `publish_due` (`publish_due`, `PUBLISH_DUE_CRON`, `"UTC"`, queue `interactive`, `automatic_backfill=False`, context `{"source": "schedule"}`); `maintenance_nightly` (`maintenance`, `MAINTENANCE_CRON`, `schedule.timezone`, queue `interactive`, `automatic_backfill=False`, context `{"source": "schedule"}`). Then `daily_generation` → resume iff `settings.scheduler_enabled`, else pause; `publish_due` and `maintenance_nightly` → resume iff `activate_background`, else pause (sync pause/resume via `asyncio.to_thread`). Log one INFO line `schedules applied` with cron, timezone and the three statuses.
5. `apply_schedule` workflow: one `untracked_step("apply_schedule.apply", ...)` that loads the schedule with `load_schedule` and calls `apply_all_schedules(rt.settings, schedule, activate_background=True)`; returns `{"time", "timezone", "scheduler_enabled"}`. It never calls `apply_schedules_async` in the body (fact 1).
6. `catch_up_today(..., schedule=)` uses `schedule.time`/`schedule.timezone` when given (env values otherwise); the rest is Phase 1.
7. `publish_due` body: `select_due` (`untracked_step`, `timeout_seconds=15.0`): `config = load_effective_config(db, settings)`, `due = select_due_articles(db, now=scheduled_at)[:MAX_DUE_PER_TICK]` → list of `DueArticle` dumps plus article titles. For each due article (in order): `process_due` (`untracked_step`, no timeout, `retries=False`) → `process_due_article(rt.sessionmaker, settings=, config=, article_id=, now=scheduled_at)` dump; an exception is caught in the body and recorded as `{"article_id", "action": "error", "error": {"class", "message"[:500]}}`, and the loop continues. `notify` (`untracked_step`, `timeout_seconds=15.0`): for each outcome `exported` → `scheduled_export_due_event(article_id, version_id from the due item, title)`; `publish_failed` → `publish_failed_event(..., error="scheduled publish failed")`; other actions → none. Result `{"due": len(due), "outcomes": [...]}`.
8. `maintenance` body, each stage an `untracked_step` wrapped in its own `try/except Exception` in the body (`{"status": "failed", "error": {"class", "message"}}` and continue):
   - `maintenance.sync_posts`: `sc = build_step_context(..., call=CallContext(trace_id=new_trace_id()))`; `external_posts.sync_mdcopilot_posts(sc, now=scheduled_at)` → `{"status": "ok", "report": <SyncReport dump>}`.
   - `maintenance.prune_dbos`: `cutoff = scheduled_at - timedelta(days=settings.dbos_retention_days)`; `deleted = prune_dbos_records(cutoff=cutoff, exclude_workflow_ids=[DBOS.workflow_id])` → `{"status": "ok", "deleted": deleted, "cutoff": cutoff.isoformat()}`.
   - `maintenance.feed_health`: `research.steps.roll_up_feed_health(rt.sessionmaker, settings=, now=scheduled_at)` → `{"status": "ok", "report": ...}`.
   - `maintenance.reconcile_costs`: when `settings.cost_reconciliation_enabled` is False or `settings.openai_admin_api_key` is None → `{"status": "disabled"}` without importing OBS code; otherwise call OBS's reconciliation function recorded in INT-0 (4a) → `{"status": "ok", "report": ...}`.
9. `prune_dbos_records`: up to `PRUNE_MAX_BATCHES` times: `rows = DBOS.list_workflows_async(end_time=cutoff.isoformat(), status=TERMINAL_DBOS_STATUSES, load_input=False, load_output=False, limit=PRUNE_BATCH_SIZE)`; ids = those not in `exclude_workflow_ids`; none → stop; `DBOS.delete_workflows_async(ids)`; sum. Non-terminal workflows are never deleted. Returns the count.

**Tests to write first.**
- `test_int_schedules.py::test_cron_for` — `ScheduleConfig(time="06:45", timezone="Asia/Kolkata")` → `"45 6 * * *"`; `"00:05"` → `"5 0 * * *"`.
- `::test_apply_all_schedules_paused_by_default` — `apply_all_schedules(settings(scheduler_enabled=False), ScheduleConfig(time="06:45", timezone="Asia/Kolkata"), activate_background=False)`; `DBOS.get_schedule_async`: `daily_generation` → `(status, schedule, cron_timezone, queue_name, workflow_name, automatic_backfill) == ("PAUSED", "45 6 * * *", "Asia/Kolkata", "pipeline", "daily_trigger", False)`; `publish_due` → `("PAUSED", "*/5 * * * *", "UTC", "interactive", "publish_due", False)`; `maintenance_nightly` → `("PAUSED", "30 2 * * *", "Asia/Kolkata", "interactive", "maintenance", False)`.
- `::test_apply_all_schedules_activates_background` — `activate_background=True`, scheduler disabled → daily `PAUSED`, the other two `ACTIVE`; `finally` re-applies with `activate_background=False` and asserts both `PAUSED`.
- `::test_load_schedule_prefers_stored_settings` — `committed_seed`; `activate_settings_values(sm, {"schedule": {"time": "05:10", "timezone": "Europe/London"}})` → `load_schedule(settings, sm) == ScheduleConfig(time="05:10", timezone="Europe/London")`.
- `::test_apply_schedule_workflow_uses_stored_schedule` — same stored values → start `apply_schedule()` under `apply-schedule-v2` → result `{"time": "05:10", "timezone": "Europe/London", "scheduler_enabled": False}`; `daily_generation.schedule == "10 5 * * *"`, `cron_timezone == "Europe/London"`; `maintenance_nightly.cron_timezone == "Europe/London"`; DBOS steps `["apply_schedule.apply"]`; `finally` pauses background schedules.
- `::test_daily_trigger_runs_discover_topics` (`manual_topic_selection`) — `daily_trigger(datetime(2026, 3, 1, 20, 0, tzinfo=UTC), {"source": "test"})` → `"daily-2026-03-02"`; child row `name == "discover_topics"`, `queue_name == "pipeline"`, `workflow_timeout_ms == 900000`; after the child finishes the daily run for 2026-03-02 is `WAITING_FOR_TOPIC`.
- `::test_daily_trigger_uses_stored_timezone` (`manual_topic_selection`, stored timezone `UTC`) → `"daily-2026-03-01"` for the same instant.
- `::test_daily_run_skipped_for_reviewable_article` — admin user; `make_article_graph(status=READY_FOR_REVIEW)` with its article `run_date` set to 2026-05-04 → `create_daily_run_step("2026-05-04") is None`; zero daily runs for that date; one admin notification with dedupe `daily_run_skipped:{article}:2026-05-04`, body `No daily run was started for 2026-05-04: an article for this date is already READY_FOR_REVIEW.`, link `/articles/{article}`.
- `::test_daily_run_not_skipped_for_rejected_article` — same with `REJECTED` → returns a run id.
- `::test_active_manual_run_skip_notifies_admins` — admin user; `make_run(kind=MANUAL, run_date=date(2026, 2, 11), status=PRODUCING)` → None; notification dedupe `daily_run_skipped:{manual run}:2026-02-11`.
- `::test_schedule_next_minute_creates_one_run_and_duplicate_trigger_creates_none` (Phase 8 acceptance; `manual_topic_selection`) — `now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))`; `slot = now_ist.replace(second=0, microsecond=0) + timedelta(minutes=1 if now_ist.second < 40 else 2)`; store `{"schedule": {"time": slot.strftime("%H:%M"), "timezone": "Asia/Kolkata"}}`; `apply_all_schedules(settings(scheduler_enabled=True), load_schedule(...), activate_background=False)`; poll ≤ 150 s until a `daily` run with `run_date == slot.date()` exists; wait `daily-{slot.date()}` to finish; then `daily_trigger(slot, {"source": "duplicate"}) is None`; exactly 1 daily run for that date; `list_workflows_async(workflow_ids=[f"daily-{slot.date()}"])` has 1 row; `finally` re-applies with `scheduler_enabled=False` and asserts `PAUSED`.
- `::test_catch_up_uses_stored_schedule` (`manual_topic_selection`, stored time `06:00`) → `catch_up_today(settings(scheduler_enabled=True), datetime(2026, 4, 11, 1, 0, tzinfo=UTC), schedule=ScheduleConfig(time="06:00", timezone="Asia/Kolkata")) == "catchup-2026-04-11"`; the child daily run ends `WAITING_FOR_TOPIC`.
- `test_schedules.py` (Phase 1) updates: tests that wait for the child add `committed_seed` + `manual_topic_selection` and assert `result["run_id"]` via the discover result key `run_id` and final run status `WAITING_FOR_TOPIC` instead of `SUCCEEDED`; the timeout assertion becomes `900000`; all other Phase 1 assertions unchanged.
- `test_int_publish_due.py::test_exports_due_manual_article_once` — publisher and admin users; `make_article_graph(status=SCHEDULED, approved=True)` committed; SQL sets `scheduled_for = now() - interval '1 minute'`, `scheduled_by = publisher.id`; start `publish_due(now, {"source": "test"})` under `test-publish-due-1` → `{"due": 1, "outcomes": [{"article_id": A, "action": "exported", "publication_id": <not null>}]}`; article `EXPORTED`; 1 `blog_publications` row (`manual_export`); 2 `scheduled_export_due` notifications (publisher, admin), dedupe `scheduled_export_due:{A}:{version}`; DBOS steps `["publish_due.select_due", "publish_due.process_due", "publish_due.notify"]`; second tick under `test-publish-due-2` → `{"due": 0, "outcomes": []}`, notifications still 2, publications still 1.
- `::test_caps_articles_per_tick` — fake `select_due_articles` returning 4 `DueArticle`s and fake `process_due_article` returning `exported` → first result `due == 3`, 3 outcomes.
- `::test_process_due_error_is_isolated` — fake raises `RuntimeError("boom")` for the first article, `exported` for the second → outcomes `[{"article_id": a1, "action": "error", "error": {"class": "RuntimeError", "message": "boom"}}, {"article_id": a2, "action": "exported", "publication_id": p2}]` where `p2` is the id the fake returned; notifications only for a2.
- `::test_publish_failed_outcome_notifies` — fake returns `publish_failed` → one `publish_failed` notification per publish holder.
- `test_int_maintenance.py::test_runs_all_stages` — default test settings → result `sync_posts == {"status": "ok", "report": {"enabled": False, "fetched": 0, "inserted": 0, "updated": 0, "embedded": 0}}`, `prune_dbos["status"] == "ok"`, `feed_health["status"] == "ok"`, `reconcile_costs == {"status": "disabled"}`; DBOS steps `["maintenance.sync_posts", "maintenance.prune_dbos", "maintenance.feed_health", "maintenance.reconcile_costs"]`.
- `::test_prune_deletes_only_old_terminal_workflows` — finish probe workflow A; `cutoff = datetime.now(UTC)`; sleep 0.05 s; finish probe C; start probe B whose step waits on an `asyncio.Event` (PENDING) → `prune_dbos_records(cutoff=cutoff)` ≥ 1; A absent from `list_workflows_async`; B and C present; set the event and await B.
- `::test_stage_failure_does_not_stop_later_stages` — `external_posts.sync_mdcopilot_posts` raising `RuntimeError("boom")` → `sync_posts == {"status": "failed", "error": {"class": "RuntimeError", "message": "boom"}}`; the other three keys present with their normal status.
- `::test_reconcile_disabled_combinations` — parametrized `(False, None)`, `(True, None)`, `(False, SecretStr("sk-test-admin"))` → `{"status": "disabled"}`; OBS function monkeypatched to raise is never called.
- `::test_reconcile_calls_obs_when_enabled` — `(True, SecretStr("sk-test-admin"))` with the OBS function monkeypatched to return a report → `{"status": "ok", "report": <that report>}`.

**Implementation notes.**
```python
await DBOS.apply_schedules_async([...])   # only inside a step (fact 1); pause/resume via asyncio.to_thread(DBOS.pause_schedule, name)
rows = await DBOS.list_workflows_async(end_time=cutoff.isoformat(), status=TERMINAL_DBOS_STATUSES,
                                       load_input=False, load_output=False, limit=PRUNE_BATCH_SIZE)   # fact 5
await DBOS.delete_workflows_async([r.workflow_id for r in rows])
```

**Verification.** `pytest … tests/workflows/test_schedules.py tests/workflows/test_int_schedules.py tests/workflows/test_int_publish_due.py tests/workflows/test_int_maintenance.py` → all pass.

**Acceptance covered.** Phase 8 "Daily schedule from settings: wrapper, `daily-YYYY-MM-DD`, same-day startup check, skip dates covered by a manual run, paused until enabled; target switched to `discover_topics`", "Maintenance: post sync, DBOS record pruning, feed-health roll-up", "Test schedule set to the next minute creates one run; duplicate trigger creates none"; Phase 7 "`publish_due` every 5 min; manual → export + notification" (INT schedule/workflow/notification) and "Scheduled article handled exactly once; second tick does nothing" (INT workflow test); Phase 6 "saving enqueues `apply_schedule`" (INT workflow); Phase 3 `sync_mdcopilot_posts` maintenance wiring; CONTRACT §2.3 "`maintenance.prune_dbos` is the only DBOS pruning".

### INT-8: `control` workflow and the runs API (§4.1)

**Files.** Create `pkg/workflows/control.py`, `backend/tests/workflows/test_int_control.py`, `backend/tests/integration/test_int_openapi.py`. Modify `pkg/services/runs.py`, `pkg/api/routers/runs.py`, `pkg/api/schemas.py` (RunDetail v2 only), `pkg/worker.py` (registration import), `backend/tests/api/test_runs_api.py`, `backend/tests/db/test_runs_service.py`, `backend/tests/workflows/test_runs_api_dbos.py`.

**Interfaces.**
- Produces (`control.py`):
  ```python
  @DBOS.workflow(name=WORKFLOW_CONTROL)
  async def control(action: str, workflow_id: str, step_name: str | None) -> dict[str, Any]
      # fork   → {"action": "fork", "workflow_id", "step_name", "start_step": int, "forked_workflow_id"}
      # cancel → {"action": "cancel", "workflow_id"}
  def control_workflow_id() -> str   # f"control-{uuid7()}"
  ```
- Produces (`api/schemas.py`): `class RunDetail(RunOut): params: dict[str, Any]; attempts: list[AttemptOut]; steps: list[StepOut]; error: dict[str, Any] | None; article_ids: list[uuid.UUID]; research_run_ids: list[uuid.UUID]`.
- Produces (`services/runs.py`):
  ```python
  RESTART_STATUSES = frozenset({SUCCEEDED, FAILED, CANCELLED})
  @dataclass(frozen=True) class RunDetailRows: run: BlogRun; attempts: list[RunAttempt]; steps: list[AgentRun]; article_ids: list[uuid.UUID]; research_run_ids: list[uuid.UUID]
  async def create_manual_run(db, client, *, principal, request, settings, today) -> BlogRun          # now enqueues discover_topics, timeout D
  async def get_run_detail(db, run_id) -> RunDetailRows | None
  async def cancel_run(db, client, *, run, principal) -> BlogRun                                        # Phase 1 behaviour
  async def restart_run(db, client, *, run: BlogRun, principal: Principal, settings: Settings) -> BlogRun
  async def resume_run(db, client, *, run: BlogRun, principal: Principal, settings: Settings) -> BlogRun
  async def retry_step(db, client, *, run: BlogRun, step_name: str, principal: Principal) -> BlogRun
  async def restart_from_step(db, client, *, run: BlogRun, step_name: str, principal: Principal) -> BlogRun
  ```
- Routes (`routers/runs.py`, prefix `/api/blog-agent`): Phase 1 four routes plus `POST /runs/{run_id}/restart`, `POST /runs/{run_id}/resume`, `POST /runs/{run_id}/steps/{step_name}/retry`, `POST /runs/{run_id}/steps/{step_name}/restart` — all `require_permission(Permission.AGENT_RUNS)`, status 202, response `RunOut`, run row loaded `with_for_update=True`.

**Behaviour rules.**
1. `create_manual_run`: unchanged except the enqueue is `workflow_name="discover_topics"`, `queue_name="pipeline"`, `workflow_id=f"manual-{run.id}"`, `args=(str(run.id),)`, `timeout_seconds=timeout_for_workflow("discover_topics", settings)`.
2. `get_run_detail` adds `article_ids` (`blog_articles.run_id == run_id` ordered `created_at, id`) and `research_run_ids` (`blog_research_runs.run_id == run_id` ordered `started_at, id`); the router fills `error=run.error`.
3. `restart_run`: status not in `RESTART_STATUSES` → 409 `Run cannot be restarted`, detail `run is <status>`. Target: newest live article of the run (status not `REJECTED`/`SUPERSEDED`) → `produce_article` with that article's `candidate_id`; else newest candidate with status `SELECTED` (by `selected_at desc`) → `produce_article`; else `discover_topics`. Workflow id `restart-produce-{run_id}-{candidate_id}-{uuid7()}` or `restart-discover-{run_id}-{uuid7()}`; args `(run_id, candidate_id)` or `(run_id,)`; queue `pipeline`; timeout from `timeout_for_workflow`. Insert `RunAttempt(run_id, dbos_workflow_id, workflow_name, attempt_no=count+1, status="ENQUEUED", started_at=None)`; commit; enqueue. Enqueue failure → the attempt → `FAILED` with `finished_at=now`, `error={"stage": "enqueue", "message": f"{type}: {exc}"[:500]}`; commit; 503 `Workflow service unavailable` detail `run {id} was not restarted`; no audit row. Success → audit `run.restart` (`entity_type="blog_run"`, details `{"workflow_id", "workflow_name", "from_status"}`), commit. The run status is not changed here; the new workflow's `open_attempt` re-opens it (INT-4 rule 9 / INT-5 rule 1 via `advance_run` and the restart-attempt rule).
4. `resume_run`: for the run's attempts with status `ENQUEUED` or `RUNNING`, newest `attempt_no` first: `view = client.describe(id)`; the first with `view.status in {"PENDING", "ENQUEUED"}` and `view.app_version is not None and view.app_version != settings.app_version` is the target. None → 409 `Nothing to resume`, detail `no interrupted workflow on an older application version`. Then `steps = client.list_steps(id)`; `start = max(function_id) + 1` (1 when no steps); `client.cancel(id)`; `new = client.fork_from_function_id(id, start, queue_name=queue_for_workflow(attempt.workflow_name), timeout_seconds=timeout_for_workflow(...))`; the old attempt → `CANCELLED`, `finished_at=now`; audit `run.resume` details `{"workflow_id", "forked_workflow_id", "start_step"}`; commit. Client exception → 503 `Workflow service unavailable` detail `run {id} was not resumed`, nothing committed.
5. Step name validation (retry and restart): `step_name not in known_step_names()` → 404 `Step not found`, detail `unknown step {step_name}`. Rows = `blog_agent_runs` of the run with that `step_name`; none → 404 `Step not found`, detail `run {id} has no step {step_name}`. The attempt = the attempt with the highest `attempt_no` among those rows' `attempt_id`s.
6. `retry_step`: attempt status must be `FAILED` and that attempt's newest row for the step must be `FAILED`, else 409 `Step cannot be retried` (detail `latest attempt is <status>` or `step <name> did not fail in the latest attempt`). `client.describe(attempt.dbos_workflow_id)` None → 409 `Step cannot be retried`, detail `DBOS records for {wf} were pruned`. Enqueue `control` (`workflow_name="control"`, `queue_name="interactive"`, `workflow_id=control_workflow_id()`, `args=("fork", wf, step_name)`, `timeout_seconds=120.0`); failure → 503 `Workflow service unavailable` (detail `step retry for run {id} was not enqueued`), no audit. Success → audit `run.step_retry` details `{"step_name", "workflow_id", "control_workflow_id"}`; commit.
7. `restart_from_step`: run status not in `RESTART_STATUSES` → 409 `Step cannot be restarted`, detail `run is <status>`; pruned → 409 `Step cannot be restarted` with the rule-6 detail; enqueue as rule 6; audit `run.step_restart`.
8. `control` body, one `untracked_step("control.control", ...)`: `fork` → `steps = DBOS.list_workflow_steps_async(workflow_id)`; ids with `function_name == step_name`; none → `LookupError(f"step {step_name!r} not found in workflow {workflow_id!r}")`; `start = max(ids)`; `row = DBOS.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)[0]`; `handle = DBOS.fork_workflow_async(workflow_id, start, application_version=DBOS.application_version, queue_name=queue_for_workflow(row.name), timeout_seconds=timeout_for_workflow(row.name, settings))`. `cancel` → `DBOS.cancel_workflow_async(workflow_id)`. Any other action → `ValueError(f"unknown control action {action!r}")`.
9. The fork's steps re-resolve their attempt (INT-3); forks of pipeline workflows re-open the terminal run to `QUEUED`, and the first re-executed stage walks it forward (`advance_run`, `advance_article` from `FAILED`).

**Tests to write first.**
- `test_runs_api.py` updates: `test_editor_creates_manual_run_and_enqueues_discover_topics` (replaces the hello test) → `fake_workflow_client.enqueued == [EnqueueCall("discover_topics", "pipeline", f"manual-{id}", (id,), 900.0)]`; `test_run_detail_shape_and_ordering` adds keys `error` (value from the inserted run's error), `articleIds`, `researchRunIds` (graph rows in `db_session`: 1 article id, 2 research run ids in `started_at` order); every other Phase 1 test unchanged.
- `test_runs_api.py` new (FakeWorkflowClient, `db_session` rows, `login_as`):
  - `test_restart_failed_run_without_candidates_enqueues_discover` — reviewer; run `FAILED` with one `FAILED` attempt → 202, body `status == "FAILED"`; one EnqueueCall: name `discover_topics`, queue `pipeline`, id matches `^restart-discover-{run}-[0-9a-f-]{36}$`, args `(run,)`, timeout 900.0; a new attempt row `ENQUEUED`, `attempt_no == 2`, `dbos_workflow_id` == that id; audit `run.restart` with `details["workflow_name"] == "discover_topics"`.
  - `test_restart_with_live_article_enqueues_produce` — `make_article_graph(db_session, status=FAILED)`, run set `FAILED` → id matches `^restart-produce-{run}-{candidate}-[0-9a-f-]{36}$`, args `(run, candidate)`, timeout 1800.0.
  - `test_restart_with_selected_candidate_only_enqueues_produce` — candidate `SELECTED`, no article → `produce_article` with that candidate.
  - `test_restart_active_run_is_409` — parametrized `QUEUED, RESEARCHING, TOPICS_READY, WAITING_FOR_TOPIC, PRODUCING` → 409 title `Run cannot be restarted`; nothing enqueued; no new attempt.
  - `test_restart_enqueue_failure` — `enqueue_error=RuntimeError("dbos down")` → 503 `Workflow service unavailable`; the new attempt `FAILED` with `error["stage"] == "enqueue"`; run unchanged; zero `run.restart` audit rows.
  - `test_resume_forks_old_version_workflow` — attempt `RUNNING` `produce-{run}-{cand}` (`workflow_name="produce_article"`); `views[wf] = WorkflowView(wf, "PENDING", "produce_article", "0.0.9", "pipeline")`; `steps[wf]` = function ids 1, 2, 3 → 202; `cancelled == [wf]`; `forked_by_id == [ForkByIdCall(wf, 4, "pipeline", 1800.0, f"{wf}-fork-1")]`; attempt `CANCELLED`; audit `run.resume` details `start_step == 4`.
  - `test_resume_nothing_to_resume` — parametrized: same app version (`settings.app_version`); status `SUCCESS` with old version; no active attempts → 409 `Nothing to resume`; nothing cancelled or forked.
  - `test_resume_client_failure` — `fork_error=RuntimeError("down")` → 503; attempt still `RUNNING`; no audit.
  - `test_retry_failed_step_enqueues_control` — attempt `FAILED` (`produce-…`), step rows `produce.write_draft` `SUCCEEDED` and `produce.fact_check` `FAILED` in that attempt, `statuses[wf] = "ERROR"` → POST `/runs/{run}/steps/produce.fact_check/retry` → 202; one EnqueueCall `("control", "interactive", ^control-…$, ("fork", wf, "produce.fact_check"), 120.0)`; audit `run.step_retry` with `details["step_name"] == "produce.fact_check"`.
  - `test_retry_step_errors` — `produce.nope` → 404 `Step not found`; `produce.seo` with no row → 404 `Step not found`; latest attempt `SUCCEEDED` → 409 `Step cannot be retried`; attempt `FAILED` but the step row `SUCCEEDED` → 409; workflow unknown to the fake (pruned) → 409 with detail `DBOS records for {wf} were pruned`; `enqueue_error` → 503 and zero `run.step_retry` audits.
  - `test_restart_from_step` — run `SUCCEEDED`, row `produce.seo` `SUCCEEDED` → 202 control fork args `("fork", wf, "produce.seo")`, audit `run.step_restart`; run `PRODUCING` → 409 `Step cannot be restarted`.
  - `test_new_run_routes_permissions` — for each of the four new routes: no login → 401; `Role.EDITOR` (lacks `blog.agent_runs`) → 403 `Forbidden`; unknown run → 404 `Run not found`; missing CSRF token → 403.
- `test_runs_service.py` updates: `create_manual_run` enqueue assertion as above; attempt fixtures keep `workflow_name="hello_pipeline"` (data only).
- `test_int_control.py` (`dbos_runtime`, `committed_seed`, golden production from INT-4's helper):
  - `test_control_fork_from_latest_step` — finished `produce-{run}-{cand}`; start `control("fork", wf, "produce.seo")` under `control_workflow_id()` → result `action == "fork"`, `start_step` == the function id of `produce.seo`; new workflow row `forked_from == wf`, `queue_name == "pipeline"`, `workflow_timeout_ms == 1800000`, `app_version == "pytest"`; after it finishes: a second `blog_version_seo` row for the current version, versions still 1, run `SUCCEEDED`, 2 `produce_article` attempts.
  - `test_control_cancel` — enqueue a probe workflow sleeping 5 s in a step → `control("cancel", id, None)` → `{"action": "cancel", "workflow_id": id}`; the probe's DBOS status becomes `CANCELLED`.
  - `test_control_unknown_step` → the control workflow raises `LookupError` with message `step 'produce.nope' not found in workflow '<wf>'`.
  - `test_control_unknown_action` → raises `ValueError("unknown control action 'pause'")`.
- `test_int_openapi.py::test_int_models_match_shape_file` — `create_app(settings).openapi()["components"]["schemas"]` for `RunOut`, `RunDetail`, `AttemptOut`, `StepOut`, `ManualRunRequest`, `NotificationOut`: property names == `api_shapes.json[model]["props"]`; properties whose schema has `anyOf` containing `{"type": "null"}` == `["nullable"]`.
- `test_runs_api_dbos.py` (Phase 1 e2e) update: add `committed_seed`; after POST `/runs` wait for `SUCCEEDED` (timeout 120 s) → attempts `[(f"manual-{id}", "discover_topics", "SUCCEEDED"), (<produce id>, "produce_article", "SUCCEEDED")]`; `articleIds` has 1 id.

**Verification.** `pytest … tests/api/test_runs_api.py tests/db/test_runs_service.py tests/workflows/test_int_control.py tests/workflows/test_runs_api_dbos.py tests/integration/test_int_openapi.py tests/api/test_rbac_routes.py` → all pass.

**Acceptance covered.** CONTRACT §4.1 (all routes, RunDetail v2, audit actions); Phase 6 "Agent Runs timeline with retry, restart-from, restart, cancel" (INT runs API); ARCHITECTURE §5.5 restart/resume; Phase 1 deferred minor "RunDetail has no error field" (run half; see open questions for `AttemptOut.error`).

### INT-9: Worker and API wiring (`worker.py`, `api/app.py` lifespan)

**Files.** Modify `pkg/worker.py`, `pkg/api/app.py` (lifespan only), `backend/tests/integration/conftest.py` (worker import). Create `backend/tests/workflows/test_int_worker.py`, `backend/tests/integration/test_int_app_tracing.py`.

**Interfaces.**
- Produces (`worker.py`):
  ```python
  REGISTERED_WORKFLOW_NAMES: tuple[str, ...]   # the 15 D-1 names
  async def startup_schedules(rt: WorkerRuntime, now: datetime) -> str | None   # load_schedule → apply_all_schedules(activate_background=True) → catch_up_today(schedule=)
  ```
- Consumes: `observability.tracing.configure_tracing` (called as `tracing.configure_tracing` through the module).

**Behaviour rules.**
1. `worker.py` imports `hello`, `schedules`, `discover`, `produce`, `human_actions`, `publish_due`, `maintenance`, `control` for registration before `DBOS.launch()`.
2. `_run_dbos`: first line `tracing.configure_tracing(settings, service_name="worker")`; then Phase 1 order (runtime, prompt sync, `DBOS(...)`, launch, queues `pipeline`=1 and `interactive`=4); then `caught_up = await startup_schedules(rt, datetime.now(UTC))` replaces `apply_daily_schedule` + `catch_up_today`. A `ConfigError` from `load_schedule` is logged at ERROR (`stored schedule settings are invalid`) and re-raised (the worker exits; compose restarts show the error).
3. `main()` keeps the kill-switch behaviour (no DBOS launch while `agent_enabled` is False); only the log text stays as Phase 1.
4. `api/app.py` lifespan calls `tracing.configure_tracing(settings, service_name="api")` right after `configure_logging(settings.log_level)`; nothing else in `app.py` changes.

**Tests to write first.**
- `test_int_worker.py::test_every_workflow_is_registered` — after `import mdcopilot_blog.worker`, for each `(module attribute, name)` pair of D-1 (`discover.discover_topics` → `"discover_topics"`, `discover.regenerate_topics` → `"regenerate_topics"`, `produce.produce_article` → `"produce_article"`, `human_actions.change_topic` → `"change_topic"`, `human_actions.regenerate_component` → `"regenerate_component"`, `human_actions.regenerate_article` → `"regenerate_article"`, `human_actions.regenerate_research` → `"regenerate_research"`, `human_actions.recheck_article` → `"recheck_article"`, `human_actions.publish_article` → `"publish_article"`, `schedules.apply_schedule` → `"apply_schedule"`, `control.control` → `"control"`, `publish_due.publish_due` → `"publish_due"`, `maintenance.maintenance` → `"maintenance"`, `schedules.daily_trigger` → `"daily_trigger"`, `hello.hello_pipeline` → `"hello_pipeline"`) assert `fn.dbos_function_name == name`; `set(worker.REGISTERED_WORKFLOW_NAMES)` equals the 15 names.
- `::test_startup_schedules` (`dbos_runtime`, `committed_seed`, stored schedule `06:00` Asia/Kolkata) — `monkeypatch.setattr(dbos_runtime, "settings", settings(scheduler_enabled=False))` → `startup_schedules(dbos_runtime, datetime(2026, 4, 12, 5, 0, tzinfo=UTC)) is None`; `daily_generation` `PAUSED` with `"0 6 * * *"`; `publish_due` and `maintenance_nightly` `ACTIVE`; `finally` pauses both.
- `::test_run_dbos_configures_tracing_first` — monkeypatch `tracing.configure_tracing` to record calls and `worker.build_runtime` to raise `RuntimeError("stop here")` → `pytest.raises(RuntimeError)` on `worker._run_dbos(settings, asyncio.Event())`; recorded `[(settings, "worker")]`.
- `test_int_app_tracing.py::test_lifespan_configures_tracing` — monkeypatch `tracing.configure_tracing` recorder; `app = create_app(settings, workflow_client=FakeWorkflowClient())`; `async with app.router.lifespan_context(app)` → recorded `[(settings, "api")]` exactly once.

**Verification.** `pytest … tests/workflows/test_int_worker.py tests/integration/test_int_app_tracing.py tests/workflows/test_worker.py` → pass. Imports check (header) → pass.

**Acceptance covered.** Phase 9 "OpenTelemetry … INT (`step_span`, `configure_tracing` in worker and api lifespan)"; Phase 8 schedule registration at startup and same-day catch-up.

### INT-10: End-to-end integration tests

**Files.** Create `backend/tests/integration/test_int_daily_mock_run.py`, `test_int_retry_from_p4.py`, `test_int_quality_scenarios.py`, `test_int_topic_flows.py`, `test_int_seam_wiring.py`. Modify `backend/tests/integration/int_helpers.py` (add `e2e_app`).

**Interfaces.**
- Produces (`int_helpers.py`): `@asynccontextmanager async def e2e_app(settings: Settings) -> AsyncIterator[FastAPI]` (`create_app(settings.model_copy(update={"app_version": "pytest", "agent_enabled": True}))` inside `app.router.lifespan_context`, so the real `WorkflowClient` enqueues to the in-process worker); `async def api_login(http: AsyncClient, email: str) -> str` (returns the CSRF token; password `TEST_PASSWORD`); `async def poll(fn: Callable[[], Awaitable[T | None]], timeout: float) -> T`.
- Consumes every INT workflow, the runs API and the parallel tracks' API routes.

**Behaviour rules.**
1. These tests use committed rows (`committed_seed`, users from `create_user_committed`) and the real `WorkflowClient`; no `db_session`.
2. Each test waits for every workflow it starts, including enqueued children, before returning.
3. The D9 check (CONTRACT §10.8) is expressed exactly: every `blog_llm_calls` row has `trace_id IS NOT NULL`; rows with a `dbos_workflow_id` starting with `daily-`, `manual-`, `produce-`, `change-topic-`, `regen-`, `recheck-`, `publish-` or `restart-`, or with non-null `attempt_id`, `article_id` or `topic_candidate_id`, have `run_id IS NOT NULL`.

**Tests to write first.**
- `test_int_daily_mock_run.py::test_manual_run_reaches_ready_for_review_under_60_seconds` — users: editor (creates the run), reviewer, viewer. `t0 = time.monotonic()`; POST `/api/blog-agent/runs` `{}` as editor → 202; poll GET `/runs/{id}` until `status == "SUCCEEDED"` and `articleIds` non-empty and GET `/articles/{articleIds[0]}` has `status == "READY_FOR_REVIEW"`; `time.monotonic() - t0 < 60`. Then: attempts `[("discover_topics", "SUCCEEDED"), ("produce_article", "SUCCEEDED")]`; step names of the produce attempt equal the INT-4 golden list; no step name contains `fix_pass`; GET `/articles/{a}/quality-gates` → `passed is True`, `versionId == currentVersionId`, `runKind == "full"`; GET `/articles/{a}/fact-check` → `versionId == currentVersionId`, `independentCheck is True`; SQL: every call of the run has `trace_id == run.trace_id`; the D9 query over the whole table returns 0 violations; reviewer GET `/notifications` → one item `kind == "ready_for_review"`, `link == f"/articles/{a}"`; viewer GET `/notifications` → `total == 0`.
- `test_int_retry_from_p4.py::test_forced_failure_at_p4_is_retried_from_p4` — monkeypatch `quality_steps.fact_check` with a wrapper that raises `RuntimeError("forced fact check failure")` on its first call and delegates afterwards. POST `/runs` (editor) → poll run `FAILED`; produce attempt `FAILED`, `error["step"] == "produce.fact_check"`; article `FAILED`; version ids = `[v1]`. As reviewer POST `/runs/{id}/steps/produce.fact_check/retry` → 202. Poll run `SUCCEEDED` (≤ 120 s). Attempts: `discover_topics SUCCEEDED`, `produce_article FAILED`, `produce_article SUCCEEDED` with `forkedFromWorkflowId` == the failed attempt's workflow id; the fork attempt's step rows start with `produce.fact_check` (no `deep_research`, `build_research_packet`, `write_draft` rows for it); versions still exactly `[v1]` (same id); packets 1; writer LLM calls for the run: 1; article `READY_FOR_REVIEW`; audit row `run.step_retry`.
- `test_int_quality_scenarios.py::test_fix_pass_under_defect_scenario` — parametrized `(scenario, gate)`: `("invented_statistic", "no_unsupported_statistics")`, `("invented_quote", "no_fabricated_quotes")`, `("invented_anecdote", "no_unsourced_anecdotes")`, `("prohibited_phrase", "no_prohibited_language")`. Worker gateway/settings monkeypatched to the scenario (INT-4 pattern); run golden `produce_article` via `selected_candidate`. Assert: exactly one `produce.fix_pass.revise` and one `produce.fix_pass.quality_gates` row; final status is `READY_FOR_REVIEW` with the latest gate review `PASSED`, or `QUALITY_GATE_FAILED` with `gate` among the latest gate report's failed blocking results; a `fix_pass` version exists and has a `fact_check` review.
- `::test_revision_path_scenario` — `revision_path` → `produce.revise` and `produce.verify_facts` present; the latest gate review's `version_id` == `current_version_id`, and a `fact_check` review exists for it.
- `test_int_topic_flows.py::test_manual_mode_select_starts_production` (`manual_topic_selection`) — POST `/runs` → poll `WAITING_FOR_TOPIC`; GET `/topics?runId=` → 3 items; POST `/topics/{items[0].id}/select` `{"confirmWarning": false}` (editor) → 202, `workflowName == "produce_article"`; poll run `SUCCEEDED` and article `READY_FOR_REVIEW`.
- `::test_generate_topics_returns_three_new_candidates` (`manual_topic_selection`) — run to `WAITING_FOR_TOPIC`; POST `/topics/generate` `{"runId": id}` → 202 `workflowName == "regenerate_topics"`; poll GET `/topics?runId=` until `round == 2`; 3 items; their ids are disjoint from round 1's; each item's `title` differs from every round-1 title.
- `::test_change_topic_via_api` — auto run `SUCCEEDED`; POST `/topics/{a PASSED candidate}/select` → 202 `workflowName == "change_topic"`; poll old article `SUPERSEDED` and the run's newest article `READY_FOR_REVIEW`.
- `test_int_seam_wiring.py::test_api_actions_enqueue_int_workflows` — `committing_client` with `fake_workflow_client`, golden graphs: each call → the recorded `EnqueueCall` name, queue, id pattern and args shape: POST `/articles/{a}/regenerate` `{"component": "section", "sectionKey": "evidence"}` → `("regenerate_component", "interactive", ^regen-component-{a}-…$, (a, "section", "evidence", None))`; `{"component": "article"}` → `("regenerate_article", …, (a, None))`; `{"component": "research"}` → `("regenerate_research", …, (a,))`; POST `/articles/{a}/recheck` → `("recheck_article", "interactive", ^recheck-{a}-…$, (a,))`; POST `/articles/{approved}/publish` with settings `publishing_enabled=True`, `publisher="mdcopilot_api"` → `("publish_article", "interactive", ^publish-{v}-…$, (a, v, <bool>))`; POST `/topics/generate` → `("regenerate_topics", "interactive", ^regen-topics-{run}-…$, (run,))`; PUT `/settings` changing `schedule.time` → `("apply_schedule", "interactive", f"apply-schedule-v{n}", ())`; every timeout equals `timeout_for_workflow(name, settings)`. A mismatch is fixed by a one-line edit in the owning service (Edits log) only when the service calls a seam instead of enqueueing; any other mismatch is a `Request:` line.

**Verification.** `pytest … tests/integration` → all pass; `test_int_daily_mock_run` prints its measured seconds in the assertion message.

**Acceptance covered.** Phase 5 "Full mock daily run → `READY_FOR_REVIEW` < 60 s, gates recorded on the final version, fact check for that exact version" (primary); Phase 8 "Forced failure at P4 retried from P4; earlier versions kept" (primary); Phase 5 scenario routing (INT end-to-end part); Phase 3 "`POST /topics/generate` → 3 new candidates" and "selecting enqueues production" (INT e2e); Phase 9 "Every `blog_llm_calls` row has `run_id` and `trace_id`" (INT part, D9); golden-path invariant "independent fact check" (CONTRACT §5.8, INT verifies).

### INT-11: Acceptance script and Playwright smoke test

**Files.** Create `scripts/acceptance/phase2-9.sh`, `scripts/e2e/phase6-smoke.sh`, `scripts/e2e/phase6-smoke.mjs`. Append one `Request:` line to `requests/int.md` asking the controller to record the Playwright pin (`mcr.microsoft.com/playwright:v1.63.0-noble`, `playwright@1.63.0`) in DEPS.md.

**Interfaces.**
- `scripts/acceptance/phase2-9.sh` — env: `SKIP_E2E=1` (skip the smoke test), `KEEP_ACCEPT_STACK=1` (skip the final `down -v`). Host tools: docker (compose), curl, jq (pinned `ghcr.io/jqlang/jq:1.8.1` container fallback as in Phase 1), openssl. Ends with `PHASE 2-9 ACCEPTANCE: PASS (<n> checks, <w> warnings)` or exits 1 at the first failure.
- `scripts/e2e/phase6-smoke.sh` — env: `E2E_PROJECT` (default `mdcopilot-blog-accept`), `E2E_API` (default `http://127.0.0.1:${API_HOST_PORT}`), optional `E2E_ADMIN_EMAIL`/`E2E_ADMIN_PASSWORD`/`E2E_REVIEWER_EMAIL`/`E2E_REVIEWER_PASSWORD` (created with generated passwords when absent). Prints `key=value` lines and `PHASE 6 SMOKE: PASS` or exits 1.
- `scripts/e2e/phase6-smoke.mjs` — plain `playwright` library script (Chromium), env `E2E_BASE_URL`, `E2E_EMAIL`, `E2E_PASSWORD`, `E2E_RUN_ID`; prints `key=value` lines.

**Behaviour rules.**
1. Compose project for every stack command: `docker compose -p mdcopilot-blog-accept` with exported `DB_HOST_PORT=5441`, `API_HOST_PORT=8301`, `WEB_HOST_PORT=8311`, `FAKE_MDCOPILOT_HOST_PORT=8331`, `PHOENIX_HOST_PORT=8321`. Never `-p mdcopilot-blog`, never `--build`, never touch `blog_pgdata`. The only destructive command is `docker compose -p mdcopilot-blog-accept down -v` at the end (skipped with `KEEP_ACCEPT_STACK=1`). The script never reads `.env`; passwords are generated with `openssl rand -hex 16` into env vars passed by name.
2. `phase2-9.sh` sequence (each numbered item is one or more `ok` checks):
   1. Preflight: `docker image inspect mdcopilot-blog-backend:dev mdcopilot-blog-web:dev` succeed; `docker compose -p mdcopilot-blog-accept up -d --no-build --wait --wait-timeout 300 db migrate api worker web` → healthy; `migrate` exited 0.
   2. Accounts via `exec -T -e ACC_PW api python -m mdcopilot_blog.cli create-user --email <role>-<tag>@example.test --display-name <Role> --role <role> --password-env ACC_PW` for admin, editor, reviewer, viewer (one generated password each); login each through host curl (`Origin: http://127.0.0.1:8301`, cookie jar per user).
   3. Mock daily run timing: editor POST `/api/blog-agent/runs` `{}`; poll every 1 s: run `SUCCEEDED` and first article `READY_FOR_REVIEW`; elapsed < 60 s; detail attempts' `workflowName` list == `["discover_topics","produce_article"]`; every step `SUCCEEDED`; `/articles/{a}/quality-gates` `.passed == true` and `.versionId == currentVersionId`; `/articles/{a}/fact-check` `.independentCheck == true`.
   4. SQL (accept db, `exec -T db sh -c 'psql -X -At -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`): `select count(*) from app.blog_llm_calls where run_id = '<run>' and trace_id <> '<trace>'` → `0`; `select count(*) from app.blog_llm_calls c join app.blog_run_attempts a on a.id = c.attempt_id where a.run_id = '<run>' and c.run_id is null` → `0`.
   5. Notifications: reviewer GET `/notifications` contains `kind == "ready_for_review"` with `link == "/articles/<a>"`; viewer `total == 0`.
   6. Kill and resume: `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=20 docker compose -p mdcopilot-blog-accept up -d --no-deps --wait worker`; editor POST `/runs`; poll (≤ 600 s) until the detail has a step `produce.write_draft` with `status == "RUNNING"`; `docker compose -p mdcopilot-blog-accept kill worker`; `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=20 … up -d --no-deps --wait worker`; poll run `SUCCEEDED` (≤ 900 s); `produce.write_draft` `tries == 2`; every other step `tries == 1`; SQL `select count(*) from app.blog_llm_calls where run_id = '<run>' and agent_name = 'writer'` → `1`; worker logs contain `Recovering`. A trap restores `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0` on the worker on exit.
   7. Unless `SKIP_E2E=1`: run `scripts/e2e/phase6-smoke.sh` with `E2E_PROJECT=mdcopilot-blog-accept` and the admin/reviewer credentials by name; expect its final line `PHASE 6 SMOKE: PASS`.
   8. Secrets: `logs --no-color api worker` piped through the Phase 1 `mask` patterns shows no `sk-`/`AIza` key material (grep count 0 before masking); admin GET `/settings` body contains no value longer than the masked preview for any provider (`.providers[] .preview` is null, `"set"` or matches `^.{3}….{4}$`).
   9. `down -v` for the accept project unless `KEEP_ACCEPT_STACK=1`; print the PASS line.
3. `phase6-smoke.sh`: (a) admin GET `/settings` → PUT `/settings` with `{"expectedVersion": .version, "values": (.values + {"topicSelectionMode": "manual"})}` → 200; (b) reviewer POST `/runs` → poll `WAITING_FOR_TOPIC` (≤ 180 s); (c) `NETWORK` = the accept web container's network; `docker run --rm --name p2p-int-e2e-<tag> --network "$NETWORK" -e E2E_BASE_URL=http://web:5173 -e E2E_EMAIL -e E2E_PASSWORD -e E2E_RUN_ID -v "$PWD/scripts/e2e/phase6-smoke.mjs:/work/smoke.mjs:ro" -w /work mcr.microsoft.com/playwright:v1.63.0-noble sh -c 'npm install --no-save --no-audit --no-fund playwright@1.63.0 >/tmp/npm.log 2>&1 || { tail -n 20 /tmp/npm.log; exit 1; }; node smoke.mjs'`; (d) check the printed keys (rule 4); (e) restore `topicSelectionMode` to its previous value (or remove the key) with another PUT.
4. `phase6-smoke.mjs` flow (selectors are role/label based; before writing, INT confirms each accessible name in UI's components per INT-0 4c and files a `Request:` for UI when a name differs instead of editing UI): sign in at `/login` (`getByLabel('Email')`, `getByLabel('Password')`, `getByRole('button', { name: 'Sign in' })`); open `/ideas`; click the first `getByRole('button', { name: /^Select/ })`; poll `page.request.get('/api/blog-agent/runs/<id>')` until `status == "SUCCEEDED"` and `articleIds[0]` exists and the article is `READY_FOR_REVIEW` (≤ 180 s) → print `article=<id>`; open `/articles/<id>`, wait for `getByRole('heading', { level: 1, name: 'Article review' })`; click `.cm-content`, press `Control+End`, type `" Review time stays focused on the decisions that matter."`; click `getByRole('button', { name: /^Save/ })` and wait for the `PATCH /api/blog-agent/articles/<id>` response → print `save=<status>`; GET `/articles/<id>/versions` length → print `versions=<n>`; click `getByRole('button', { name: /Re-check/ })` → wait for the `POST …/recheck` 202 → poll the article until `READY_FOR_REVIEW` and GET `/quality-gates` `runKind == "recheck"` → print `recheck=ok`; click `getByRole('button', { name: /^Approve/ })`, then in the dialog `getByRole('button', { name: /Approve as draft/ })` → wait for `POST …/approve` → print `approve=<status>`; GET article → print `status=<status>`; print `page_errors=<count of pageerror events>`.
5. Expected smoke keys: `save=200`, `versions=2`, `recheck=ok`, `approve=200`, `status=APPROVED`, `page_errors=0`.

**Tests to write first.** Script tasks are verified by running them. Before writing the scripts, write the expected-output checklist into the task report (rule 2 items and rule 5 keys) and run `bash -n` on an empty skeleton to prove the harness.

**Verification.**
- Header "Shell syntax" and "JS syntax" commands → `bash-n-ok`, `node-check-ok`.
- `scripts/acceptance/phase2-9.sh` → final line `PHASE 2-9 ACCEPTANCE: PASS (… checks, 0 warnings)`; `docker ps -a --filter name=p2p-int-e2e` empty afterwards; `docker compose -p mdcopilot-blog ps` shows the owner's containers with unchanged `CreatedAt`.

**Acceptance covered.** Phase 8 "`BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=20`, kill the worker during the Writer step → resumes without repeating completed steps" (primary); Phase 6 "Playwright smoke in a container: select topic → open article → edit → save (new version) → re-check → approve" (primary); Phase 5 mock daily run timing (process-level confirmation).

### INT-12: Live validation tooling (`workflows/validation.py`, `scripts/validation/**`)

**Files.** Create `pkg/workflows/validation.py`, `scripts/validation/live_run.sh`, `scripts/validation/report.sh`, `scripts/validation/review_stack.sh`, `backend/tests/integration/test_int_validation.py`. `report.sh` writes `docs/blog-agent/validation/<YYYY-MM-DD>.md` (see open questions on ownership).

**Interfaces.**
```python
LIVE_DB = "mdcopilot_blog_live"
CUMULATIVE_CAP_USD = Decimal("35.20")
GATE_CAPS: Mapping[str, Decimal]          # {"live-broad-scan": 5.00, "live-daily-run": 5.00, "validation-runs": 25.00}
GATE_GROUPS: Mapping[str, frozenset[str]] # broad scan and daily run share one $5.00 cap; validation-runs alone
PER_RUN_CAP_USD: Mapping[str, Decimal]    # {"live-broad-scan": 5.00, "live-daily-run": 5.00, "validation-runs": 5.00}
WORST_CASE_INPUT_TOKENS = 120_000
class UnpricedModel(RuntimeError): ...    # (provider: str, model: str)
class LivePlan(BaseModel):
    gate: str; ledger_spent_usd: Decimal; gate_spent_usd: Decimal; remaining_ledger_usd: Decimal; remaining_gate_usd: Decimal
    max_spend_usd: Decimal; worst_case_call_usd: Decimal; run_cap_usd: Decimal; allowed: bool; reason: str | None
async def ledger_spent(db: AsyncSession) -> Decimal
async def gate_spent(db: AsyncSession, gate: str) -> Decimal
async def worst_case_call_usd(db: AsyncSession, settings: Settings, config: EffectiveConfig, *, now: datetime) -> Decimal
async def plan_live_run(db: AsyncSession, settings: Settings, *, gate: str, dry_run: bool, now: datetime) -> LivePlan
async def start_live_run(sm, client: WorkflowClientProtocol, settings: Settings, *, gate: str) -> uuid.UUID
async def run_broad_scan(sm, settings: Settings, *, gate: str) -> dict[str, Any]
async def watch_live_run(sm, client: WorkflowClientProtocol, *, run_id: uuid.UUID, poll_seconds: float, timeout_seconds: float) -> int
async def build_report(db: AsyncSession, *, day: date, timezone: str) -> str
async def build_summary(db: AsyncSession) -> str
def main(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int
    # python -m mdcopilot_blog.workflows.validation {plan --gate G [--dry-run] | start --gate G | watch --run-id ID [--timeout S]
    #                                                 | broad-scan --gate live-broad-scan | report --date YYYY-MM-DD | summary}
```

**Behaviour rules.**
1. `ledger_spent` = `SUM(cost_usd)` over `app.blog_llm_calls` (0 when empty). `gate_spent(gate)` = `SUM(cost_usd)` over calls whose `run_id` belongs to a `blog_runs` row with `params->>'liveGate'` in `GATE_GROUPS[gate]`.
2. `worst_case_call_usd`: for each spec in `(RESEARCH_ANALYST_SPEC, TOPIC_STRATEGIST_SPEC, DEEP_RESEARCH_SPEC, WRITER_DRAFT_SPEC, WRITER_REVISE_SPEC, WRITER_COMPONENT_SPEC, FACT_CHECK_SPEC, CLINICAL_SPEC, EDITORIAL_SPEC, SEO_SPEC)` and each entry of `route_from_entries(settings, spec.name, config.routes[spec.name.value])`: price = the effective `blog_price_overrides` row `(provider, model)` with the greatest `effective_from <= now` → `input_per_mtok × 120000/1e6 + output_per_mtok × max_output_tokens/1e6` (a null price counts as 0 only when the other is set), else the pricing function recorded in INT-0 (4d) for `(provider, model, input=120000, output=max_output_tokens)`; missing price → `UnpricedModel`. Search: each `config.routes["search"]` entry priced for `(120000, 2000)` tokens + `settings.search_max_tool_calls_deep × per_1k_calls / 1000` from override `(openai, web_search_call)` (missing → `UnpricedModel("openai", "web_search_call")`). Embedding: `settings.embedding_model` for `(120000, 0)`. Returns the maximum.
3. `plan_live_run`: unless `dry_run`, refuse (`allowed=False`, `reason` set, `run_cap_usd=0`) when `settings.postgres_db != LIVE_DB` (`reason="not the live database"`), `settings.mock_mode` (`"mock mode is on"`), env `BLOG_LIVE_TESTS != "1"` (`"BLOG_LIVE_TESTS is not 1"`). `remaining_ledger = CUMULATIVE_CAP_USD − ledger_spent`; `remaining_gate = GATE_CAPS[gate] − gate_spent`; `max_spend = min(remaining_ledger, remaining_gate, PER_RUN_CAP_USD[gate])`; `run_cap = max_spend − worst_case`; `UnpricedModel` → `allowed=False`, `reason=f"no price for {provider}:{model}"`; `run_cap <= 0` → `allowed=False`, `reason="remaining budget is below one worst-case call"`. Unknown gate → `ValueError`.
4. `start_live_run`: insert `BlogRun(kind="manual", run_date=local today, status="QUEUED", params={"liveGate": gate, "source": "validation"}, trace_id=new_trace_id())`, commit, enqueue `discover_topics` as `create_manual_run` does; returns the run id.
5. `run_broad_scan`: plan must be allowed (else raise `RuntimeError(reason)`); insert a run as rule 4 with status `RESEARCHING`; gateway `build_gateway(settings, sm, PromptRegistry.from_directory(default_prompt_root(), agents=["research"]))`; `sc = build_step_context(..., call=CallContext(trace_id=run.trace_id, run_id=run.id))`; `gather_signals(sc, pillar_key=None)` → `build_ledger` → `synthesize_research`; after each phase, calls of the run with `status = 'ok'` and `cost_usd = 0` → set the run `FAILED` with `error={"class": "ZeroCostCall", ...}` and return `{"exit": 3}`. Success → run `TOPICS_READY`; returns `{"exit": 0 or 1, "runId", "researchRunId", "datedSources", "minSourceCount", "findingsCitingOutsideLedger", "searchCalls", "searchCallsWithActionsAndCost", "phaseLatencyMs", "costUsd"}`; exit 0 iff `datedSources >= minSourceCount`, `findingsCitingOutsideLedger == 0`, `searchCalls == searchCallsWithActionsAndCost > 0`, and `phaseLatencyMs` has keys `search, retrieval, extraction, llm, total`. `findingsCitingOutsideLedger` = findings of the research run with no `blog_finding_sources` row, plus rows whose `source_id` is not in the research run's `source_ids`.
6. `watch_live_run` returns: 3 when any call of the run has `status = 'ok'` and `cost_usd = 0` (it first cancels every `ENQUEUED`/`RUNNING` attempt through the client, marks them `CANCELLED` and sets the run `CANCELLED`); 0 when the run is `SUCCEEDED` and its newest article is `READY_FOR_REVIEW`; 1 when the run is `FAILED`/`CANCELLED` or the article ends `QUALITY_GATE_FAILED`/`FAILED`; 2 on timeout. Poll every `poll_seconds`.
7. `build_report(day)`: runs with `params ? 'liveGate'` whose `created_at` falls on `day` in `timezone`, oldest first. Per run: id, gate, status, trace id, total cost, duration; a step table (`step_name`, status, tries, `duration_ms`, cost, model, prompt version); newest article: title, status, word count, gate report summary (passed, failed gate ids, warnings), fact-check verdict and `independent_check`, clinical verdict, editorial score, source count and tier mix, full `content_markdown`; LLM call count and whether every call has `run_id` and `trace_id`. Deterministic Markdown (no timestamps other than stored values).
8. `build_summary`: over runs with `params->>'liveGate' in ('live-daily-run', 'validation-runs')` and status `SUCCEEDED`: table `step_name | count | P50 ms | P90 ms` (`percentile_disc`) and `per-article cost P50 | P90 | min | max`; when fewer than 5 `validation-runs` runs exist, the first line is `pending: <n> of 5 validation runs`.
9. `live_run.sh <gate>`: requires `LIVE_GO_CONFIRMED` equal to the gate (the controller sets it only after the `Live-go:` line exists) unless `DRY_RUN=1`; presence checks print `set`/`missing` only (`OPENAI_API_KEY`, `GEMINI_API_KEY`); runs `scripts/live/prepare_db.sh`; `docker compose run --rm -T -e POSTGRES_DB=mdcopilot_blog_live -e BLOG_AGENT_MOCK_MODE=false -e BLOG_LIVE_TESTS=1 tools python -m mdcopilot_blog.workflows.validation plan --gate <gate> [--dry-run]` → JSON; `DRY_RUN=1` prints the plan and exits 0. Not allowed → print `reason`, exit 1. Broad scan → `tools … broad-scan` with `-e BLOG_AGENT_MAX_COST_PER_RUN_USD=<runCapUsd>`. Daily/validation run → `docker compose run -d --rm --no-deps --name p2p-int-live-worker -e POSTGRES_DB=mdcopilot_blog_live -e BLOG_AGENT_MOCK_MODE=false -e BLOG_AGENT_SCHEDULER_ENABLED=false -e BLOG_AGENT_MAX_COST_PER_RUN_USD=<runCapUsd> -e WORKER_EXECUTOR_ID=live-worker-1 worker python -m mdcopilot_blog.worker`, wait for its heartbeat, `tools … start --gate`, `tools … watch --run-id <id> --timeout 2700`, then `docker stop p2p-int-live-worker` (also in an EXIT trap). Finally prints the template `Live: <gate> — <calls> — $<spend> — docs/blog-agent/validation/<date>.md` with values read by `plan` after the run, for the implementer to append to `requests/int.md`. Exit code = the watch/broad-scan exit code.
10. `report.sh [YYYY-MM-DD]` (default: today in `Asia/Kolkata`): `tools … report --date D > docs/blog-agent/validation/D.md` (live DB env); `report.sh --summary` prints `summary`.
11. `review_stack.sh up|down`: `up` starts `p2p-int-live-api` (`docker compose run -d --rm --no-deps --name p2p-int-live-api -p 127.0.0.1:8302:8000 -e POSTGRES_DB=mdcopilot_blog_live -e BLOG_AGENT_MOCK_MODE=false -e BLOG_AGENT_ENABLED=false api uvicorn --factory mdcopilot_blog.api.app:create_app --host 0.0.0.0 --port 8000 --no-proxy-headers`) and `p2p-int-live-web` (`docker compose run -d --rm --no-deps --name p2p-int-live-web -p 127.0.0.1:8312:5173 -e VITE_API_PROXY_TARGET=http://p2p-int-live-api:8000 web`) and prints `open http://localhost:8312`; `down` stops both by name. `BLOG_AGENT_ENABLED=false` makes regenerate/recheck/publish enqueues return 409, so the owner can only review, approve, export and confirm.

**Tests to write first** (`test_int_validation.py`; test DB, mock settings; `sessionmaker_committing`).
- `test_plan_refuses_outside_live_conditions` — `plan_live_run(db, settings, gate="live-daily-run", dry_run=False, now=…)` → `allowed is False`, `reason == "not the live database"`; with `postgres_db` patched to `mdcopilot_blog_live` in a settings copy (no DB access needed beyond the session already open) and `mock_mode=True` → `reason == "mock mode is on"`; with `mock_mode=False` and env `BLOG_LIVE_TESTS` unset → `reason == "BLOG_LIVE_TESTS is not 1"`.
- `test_budget_arithmetic` — insert a `blog_runs` row with `params {"liveGate": "live-broad-scan"}` and calls costing `1.25` and `0.25`, plus an unrelated run's call costing `2.00`; monkeypatch `worst_case_call_usd` to return `Decimal("0.40")` → `dry_run=True` plan for `live-daily-run`: `ledger_spent_usd == 3.50`, `gate_spent_usd == 1.50`, `remaining_ledger_usd == 31.70`, `remaining_gate_usd == 3.50`, `max_spend_usd == 3.50`, `run_cap_usd == 3.10`, `allowed is True`; for `validation-runs`: `gate_spent_usd == 0`, `max_spend_usd == 5.00`, `run_cap_usd == 4.60`.
- `test_worst_case_uses_override_prices` — overrides for every route model of the default `EffectiveConfig` (`input_per_mtok=1`, `output_per_mtok=10`) and `(openai, web_search_call, per_1k_calls=10)` and the embedding model → result == the maximum over specs of `120000/1e6*1 + max_output_tokens/1e6*10` compared with the search value `0.12 + 2000/1e6*10 + settings.search_max_tool_calls_deep*10/1000` and the embedding value `0.12`, computed in the test from the spec constants.
- `test_worst_case_unpriced_model_refuses` — no search-fee override and the pricing lookup monkeypatched to raise `LookupError` → plan `allowed is False`, `reason == "no price for openai:web_search_call"`.
- `test_watch_detects_zero_cost_paid_call` — run with an `ENQUEUED` attempt and an `ok` call with `cost_usd = 0`; `FakeWorkflowClient` → returns 3; `cancelled == [attempt workflow id]`; run `CANCELLED`.
- `test_watch_success_and_failure` — run `SUCCEEDED` with a `READY_FOR_REVIEW` article (graph) and calls with cost `0.01` → 0; run `FAILED` → 1; run `PRODUCING` with `timeout_seconds=0.2` → 2.
- `test_report_and_summary_are_deterministic` — two runs with `liveGate` created on 2026-09-17 IST (graphs + step rows + calls) → `build_report(day=date(2026, 9, 17), timezone="Asia/Kolkata")` called twice returns identical text; contains each run id, each step name, the article title and `content_markdown`; `build_summary` first line `pending: 0 of 5 validation runs` (the runs use `live-daily-run`).
- `test_cli_plan_dry_run_prints_json` — `main(["plan", "--gate", "live-daily-run", "--dry-run"], settings=settings)` → 0; stdout parses as JSON with keys equal to `LivePlan` field aliases.

**Verification.** `pytest … tests/integration/test_int_validation.py` → pass; header "Shell syntax" command → `bash-n-ok`; `DRY_RUN=1 scripts/validation/live_run.sh live-daily-run` (after `scripts/live/prepare_db.sh`; no paid call) → prints a plan JSON and exits 0. Paid runs: none in W4.

**Acceptance covered.** Phase 8 "Validation period: 5 live manual runs reviewed by the owner" (INT tooling), "One live daily run → `READY_FOR_REVIEW` and exported, cost rows and `trace_id` on every call" (tooling; pending owner); Phase 2 "Live broad scan" (INT live run tooling; pending); Phase 4 "live drafts from the 5 validation runs recorded" (report); CONTRACT §9 live-spend rules 1–5.

### INT-13: Documentation (`LOCAL_DEVELOPMENT.md`, `.env.example` comment, ARCHITECTURE §21–§22)

**Files.** Modify `docs/blog-agent/LOCAL_DEVELOPMENT.md`, `.env.example` (one comment line). `docs/blog-agent/ARCHITECTURE.md` §21–§22 only when rule 4's condition holds.

**Interfaces.** None (documentation).

**Behaviour rules.**
1. `LOCAL_DEVELOPMENT.md` changes (keep the existing section numbers; add new sections after §9):
   - §4 code layout: add `research/`, `agents/`, `observability/`, `fakes/`, `scripts/e2e/`, `scripts/validation/`, `scripts/live/`, test directories per track.
   - §8 Running the agent manually: statuses `QUEUED → RESEARCHING → TOPICS_READY → PRODUCING → SUCCEEDED` (or `WAITING_FOR_TOPIC` in manual mode) and article statuses `DRAFTING → … → READY_FOR_REVIEW`; manual topic (`topic` skips research); `topicSelectionMode` setting; the schedules query now lists `daily_generation`, `publish_due`, `maintenance_nightly`.
   - §9 Mock mode: fixture layout (`llm/`, `search/<mode>.json`, `scenarios/<name>/`), `BLOG_AGENT_MOCK_SCENARIO`, the crash-and-resume demo rewritten for `produce.write_draft` with the SQL check `agent_name = 'writer'`.
   - New "Workflows and schedules": D-1 table (name, queue, what starts it); the kill switch: with `BLOG_AGENT_ENABLED=false` the worker does not launch DBOS, so queued runs wait and in-flight workflows are not recovered until it is true again (Phase 1 deferred minor); `publish_due` and `maintenance_nightly` run whenever the worker runs; only `daily_generation` follows `BLOG_AGENT_SCHEDULER_ENABLED`.
   - New "Retry, restart, resume": what each Agent Runs button calls (§4.1), `control` workflow, pruned DBOS records after `BLOG_DBOS_RETENTION_DAYS`.
   - New "Notifications": D-5 table and the webhook payload keys.
   - New "Publishing": link `PUBLISHING_MANUAL_CHECK.md`; `BLOG_PUBLISHING_ENABLED` scope.
   - New "Observability": link `OBSERVABILITY.md`.
   - New "Live validation runs": `Live-go:` rule, budget rules (CONTRACT §9), `live_run.sh`, `report.sh`, `review_stack.sh`, the `mdcopilot_blog_live` database, and "never set `BLOG_AGENT_SCHEDULER_ENABLED=true` before the owner approves five reviewed runs".
   - §11 Testing: per-track `BLOG_TEST_DB` commands (CONTRACT §8.2 table), `scripts/acceptance/phase2-9.sh` (accept project and ports), `scripts/e2e/phase6-smoke.sh`, final suite counts from INT-final's run.
   - §12 Troubleshooting rows: run stuck `QUEUED` after restart (worker down / app version); `Nothing to resume`; `Step cannot be retried … pruned`; worker exits with `stored schedule settings are invalid`.
2. `.env.example`: replace `# Kill switch: false pauses schedules and rejects new runs` with `# Kill switch: false rejects new runs and keeps the worker idle (no schedules, queued runs wait, no recovery until true)`.
3. Every command in the new text is copied from a command that ran green in INT-7…INT-12 or INT-final.
4. ARCHITECTURE §21–§22: only when `scripts/validation/report.sh --summary` no longer starts with `pending:`; replace the two estimate tables' headings with "Measured (N validation runs, <date range>)" tables from the summary and keep the estimate tables below under "Original estimate". Until then no ARCHITECTURE edit, and the INT report says "pending owner: validation runs".

**Tests to write first.** None (documentation). Checks: `grep -n "phase2-9.sh" docs/blog-agent/LOCAL_DEVELOPMENT.md` non-empty; `grep -n "PUBLISHING_MANUAL_CHECK.md" docs/blog-agent/LOCAL_DEVELOPMENT.md` non-empty; `grep -c "Kill switch: false rejects new runs" .env.example` → `1`.

**Verification.** The grep checks above; `tests/unit/test_settings.py` still passes (`.env.example` coverage test): `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_int_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/unit/test_settings.py`.

**Acceptance covered.** CONTRACT §2.3 LOCAL_DEVELOPMENT Phase 2–9 sections and PUBLISHING_MANUAL_CHECK link; Phase 9 "measured P50/P90 per stage replacing the estimates in ARCHITECTURE §21–§22" (INT part, pending owner); Phase 1 deferred minor on the kill switch wording.

### INT-final: Track verification

**Files.** None beyond earlier tasks (report only).

**Behaviour rules.**
1. Run, in order, on `mdcopilot_blog_int_test`: imports check; track suite; lint/type command; shell and JS syntax commands; `scripts/acceptance/phase2-9.sh`.
2. Run the stage gates the controller uses, to report their state (not owned): full backend suite `docker compose run --rm -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q`; `docker compose run --rm --no-deps tools sh -c "ruff check --no-cache . && ruff format --check --no-cache . && mypy --cache-dir=/tmp/mypy src"`; `cmp backend/tests/api_shapes.json frontend/src/test/api-shapes.json`.
3. Confirm no throwaway container remains: `docker ps -a --filter name=p2p-int --format '{{.Names}}'` → empty.
4. Report plainly with the exact commands and their last output lines; list every `Request:` line filed; list owner-pending items.

**Expected results.** Track suite: 0 failed. Lint: `All checks passed!`, `… files already formatted`, `Success: no issues found in … source files`. Acceptance: `PHASE 2-9 ACCEPTANCE: PASS (… checks, 0 warnings)`. `cmp` exit 0.

**Acceptance mapping (CONTRACT §10 rows where INT is Primary or Also).**

| Bullet (CONTRACT §10) | INT role | Proven by |
|---|---|---|
| 10.1 Live broad scan ≥ `min_source_count` dated sources, zero out-of-ledger findings, search cost rows, phase latency | Also (live run) | INT-12 `run_broad_scan` + `live_run.sh live-broad-scan` (pending `Live-go`) |
| 10.2 `sync_mdcopilot_posts` off while URL blank | Also (maintenance wiring) | INT-7 `test_runs_all_stages` |
| 10.2 Regeneration loop ≤ 2 rounds | Also (loop) | INT-5 `test_regeneration_loop_is_bounded`, `test_regeneration_stops_when_three_pass` |
| 10.2 `discover_topics` D1–D7 auto and manual; `regenerate_topics` | Primary | INT-5 tests |
| 10.2 Always exactly 3 or flagged shortfall | Also | INT-5 `test_regeneration_loop_is_bounded` (shortfall flag, `WAITING_FOR_TOPIC`) |
| 10.2 `POST /topics/generate` → 3 new candidates | Also (e2e) | INT-10 `test_generate_topics_returns_three_new_candidates` |
| 10.2 Manual mode stops at `WAITING_FOR_TOPIC`; selecting enqueues production | Primary | INT-5 `test_manual_mode_stops_waiting_for_topic`; INT-10 `test_manual_mode_select_starts_production` |
| 10.3 `produce_article` P1–P3, `regenerate_component`, `regenerate_research` | Primary | INT-4 golden path; INT-6 component/research tests |
| 10.3 Live drafts from the 5 validation runs recorded | Also | INT-12 `build_report` (pending owner) |
| 10.3 One section → one new version, others byte-identical | Also | INT-6 `test_regenerate_component_section` |
| 10.3 Research → new packet version, old kept | Also | INT-6 `test_regenerate_research_adds_packet_version` |
| 10.4 Gates, fix pass orchestration | Also | INT-4 `test_fix_pass_runs_once`, `test_failed_gates_set_quality_gate_failed_and_notify` |
| 10.4 `produce_article` P4–P10, `recheck_article`, full `regenerate_article` | Primary | INT-4 golden/revision tests; INT-6 recheck and regenerate_article tests |
| 10.4 Defect scenarios → fix pass → READY or QGF naming the gate | Also (e2e) | INT-10 `test_fix_pass_under_defect_scenario` |
| 10.4 Regenerating the article keeps old versions | Also | INT-6 `test_regenerate_article_keeps_old_versions` |
| 10.4 Full mock daily run → `READY_FOR_REVIEW` < 60 s, gates on final version, fact check for that version | Primary | INT-10 `test_manual_run_reaches_ready_for_review_under_60_seconds`; INT-11 item 3 |
| 10.5 Settings saving enqueues `apply_schedule` | Also (workflow) | INT-7 `test_apply_schedule_workflow_uses_stored_schedule`; INT-10 wiring test |
| 10.5 Agent Runs retry, restart-from, restart, cancel | Also (runs API) | INT-8 runs API tests |
| 10.5 Playwright smoke: select → open → edit → save → re-check → approve | Primary | INT-11 `phase6-smoke.sh` |
| 10.6 MDCopilotApiPublisher via `publish_article` workflow | Also | INT-6 publish tests; INT-10 wiring test |
| 10.6 Scheduling: `publish_due` every 5 min; manual → export + notification | Also | INT-7 `test_apply_all_schedules_*`, `test_exports_due_manual_article_once` |
| 10.6 Scheduled article handled exactly once; second tick does nothing | Also | INT-7 `test_exports_due_manual_article_once` |
| 10.7 Daily schedule from settings, `daily-YYYY-MM-DD`, startup check, skip covered dates, paused until enabled, target `discover_topics` | Primary | INT-7 schedule tests; INT-9 `test_startup_schedules` |
| 10.7 Maintenance: post sync, DBOS pruning, feed health | Primary | INT-7 maintenance tests |
| 10.7 Notifications: in-app + webhook for READY, QGF, FAILED, PUBLISH_FAILED, export due | Primary | INT-2 service/API tests; INT-4, INT-6, INT-7 notification assertions |
| 10.7 Validation period: 5 live runs reviewed | Primary (tooling) | INT-12 (pending owner) |
| 10.7 Next-minute schedule creates one run; duplicate trigger none | Primary | INT-7 `test_schedule_next_minute_creates_one_run_and_duplicate_trigger_creates_none` |
| 10.7 Delay 20 s, kill worker during Writer → resumes without repeats | Primary | INT-11 item 6 |
| 10.7 Forced failure at P4 retried from P4; earlier versions kept | Primary | INT-10 `test_forced_failure_at_p4_is_retried_from_p4`; INT-8 retry API tests |
| 10.7 One live daily run → READY + exported, cost rows and trace ids | Primary (tooling) | INT-12 `live_run.sh live-daily-run`, `review_stack.sh`, `report.sh` (pending owner) |
| 10.7 Owner approves enabling the schedule | Also | recorded by the controller; flag untouched |
| 10.8 `step_span`, `configure_tracing` in worker and API | Also | INT-3 harness (`step_span`); INT-9 tracing tests |
| 10.8 Measured P50/P90 replace ARCHITECTURE §21–§22 | Also | INT-12 `build_summary`; INT-13 rule 4 (pending owner) |
| 10.8 Every `blog_llm_calls` row has `run_id` and `trace_id` (D9) | Also | INT-10 D9 check; INT-4 golden path call assertions |

**Rules A–C (CONTRACT §5.7).**
- Rule A (human actions never change `blog_runs.status/stage/finished_at/error`; `respect_run_cancel=False`): INT-3 `test_respect_run_cancel_flag`, `test_fork_reopens_pipeline_run_but_not_human_action_run`; INT-6 `test_regenerate_component_section`, `test_human_action_on_cancelled_run_runs`, `test_regenerate_component_failure_before_write_keeps_status`.
- Rule B (`produce_article`/`change_topic` re-open `SUCCEEDED`/`FAILED` runs; original attempts on `CANCELLED` runs stop; `regenerate_topics` moves): INT-4 `test_produce_on_succeeded_run_reopens_it`, `test_produce_on_cancelled_run_changes_nothing`; INT-5 `test_regenerate_topics_on_waiting_run`, `test_regenerate_topics_on_succeeded_run_keeps_live_article`; INT-6 `test_change_topic_supersedes_and_produces`.
- Rule C (OBS generation-time metrics count only `discover_topics`/`produce_article`, plus `change_topic` for the tracker): INT records `blog_run_attempts.workflow_name` exactly as the D-1 registered name for every attempt (asserted in INT-4, INT-5, INT-6 and INT-10 attempt lists), which is the column OBS filters on.

**Known non-applicable checks.** Notifications routes have no 403 test (every role holds `blog.view`).

## Edits log (filled during implementation)

| File (other track) | Line changed | Why |
|---|---|---|
| — | — | — |
