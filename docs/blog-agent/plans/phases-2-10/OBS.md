# Track OBS: observability, FinOps and admin configuration APIs — implementation plan

Status: plan, 2026-09-17. Binding contract: `docs/blog-agent/plans/phases-2-10/CONTRACT.md` (wins on any disagreement). Paths are relative to `mdcopilot-blog/`; `pkg/` = `backend/src/mdcopilot_blog/`.

## Header

**Goal.** Deliver the Phase 9 observability layer and the admin backends of Phase 6:
- real OpenTelemetry spans behind FOUND's no-op `observability/tracing.py`, one trace per run;
- an optional OpenAI Costs API reconciliation that is off by default and makes no network call while off;
- the cost, latency and dashboard metrics APIs, whose totals equal plain SQL sums over `blog_llm_calls`;
- the Agent Runs read API;
- the Settings, brand profile, pillars and price-override APIs (versioned saves, audit, `apply_schedule` enqueue with compensation);
- the Content Calendar API;
- a check that every `blog_llm_calls` row carries `trace_id` and, outside the D9 exceptions, `run_id`;
- `docs/blog-agent/OBSERVABILITY.md`.

**Spec sections implemented.**
- ARCHITECTURE: §13 (Settings, Content Calendar, Agent Runs and Dashboard backends), §16 (`/calendar`, `/settings*`, `/pillars`, `/agent-runs`, `/metrics/*`), §17 (audit on settings changes), §18 (observability and cost tracking), §19 (configuration precedence, versioned settings and brand).
- IMPLEMENTATION_PLAN: Phase 9 (all bullets); Phase 6 backend parts of Content Calendar, Settings and the Agent Runs timeline.
- CONTRACT: §4.8, §4.9, §4.10, §5.6 `tracing.py`, §5.7 `WORKFLOW_APPLY_SCHEDULE` and Rules A–C, §10.5 and §10.8 OBS rows, ruling D9.

**Owned files (copied from CONTRACT §2.2).**

| Path | Notes |
|---|---|
| `pkg/observability/**` | `__init__.py` and `tracing.py` created by FOUND as working no-ops (§5.6) |
| `pkg/services/metrics.py`, `pkg/services/admin_config.py`, `pkg/services/calendar.py`, `pkg/services/agent_runs.py` | |
| `pkg/api/routers/settings.py` | Phase 1 file; OBS extends it (§4.9) |
| `pkg/api/routers/metrics.py`, `calendar.py`, `agent_runs.py` | stub by FOUND |
| `pkg/api/schemas_admin.py`, `pkg/api/schemas_metrics.py` | stub by FOUND |
| `backend/tests/observability/**`, `backend/tests/api/test_settings_api.py` | |
| `docs/blog-agent/OBSERVABILITY.md` | Phoenix profile how-to, cost SQL |
| `docs/blog-agent/plans/phases-2-10/obs.md` | this plan (the controller asked for it as `OBS.md`) |
| `.superpowers/sdd/phases-2-10/requests/obs.md` | `Request:` lines (§2 rules) |

New files inside owned globs: `pkg/observability/reconciliation.py`, `backend/tests/observability/conftest.py` (content replaces FOUND's docstring-only file), and the `test_obs_*.py` files named in each task.

**Extension points consumed (exact names).**
- Phase 1:
  - `api.schemas`: `ApiModel`, `Page`, `SettingsView`, `ProviderKeyView`, `mask_secret`.
  - `api.deps`: `Principal`, `SessionDep`, `SettingsDep`, `WorkflowClientDep`, `require_permission`.
  - `errors`: `ProblemError`, `VALIDATION_TITLE`.
  - `services.audit.audit`.
  - `db.models`: `AgentRun`, `AuditLog`, `BlogRun`, `BlogSetting`, `BrandProfile`, `ContentPillar`, `LlmCall`, `PromptVersion`, `RunAttempt`.
  - `domain.enums`: `Permission`, `Role`, `StepStatus`, `AgentName`, `CallKind`, `CallStatus`, `RunStatus`, `RunKind`, `ArticleStatus`, `AttemptStatus`, `PublicationStatus`.
  - `domain.contracts`: `PillarKey`, `TitleOptions`, `GateReport`, `EditorialReview`.
  - `llm.gateway.CallContext`; `llm.routes.parse_choice`.
  - `workflows.client`: `WorkflowClientProtocol`, `FakeWorkflowClient`, `EnqueueCall`.
  - `workflows.names.QUEUE_INTERACTIVE`; `workflows.hello.hello_pipeline` (test only).
  - `ids.uuid7`; `settings.Settings` (fields `timezone`, `otel_exporter_otlp_endpoint`, `app_version`, `app_env`, `mock_mode`, `openai_api_key`, `gemini_api_key`, `anthropic_api_key`, `ncbi_api_key`).
- FOUND:
  - `domain.config`: `EffectiveConfig`, `SettingsValues`, `BrandProfileValues`.
  - `services.config`: `load_effective_config`, `load_brand_profile`, `pillar_for_date`, `local_date`, `ConfigError`.
  - `services.enqueue.enqueue_workflow`.
  - `workflows.names`: `WORKFLOW_APPLY_SCHEDULE`, `WORKFLOW_DISCOVER_TOPICS`, `WORKFLOW_PRODUCE_ARTICLE`, `WORKFLOW_CHANGE_TOPIC`, `HUMAN_ACTION_WORKFLOWS`, and the `STEP_*` values of §5.7.
  - Enums: `SlotStatus`, `ResearchRunKind`, `ResearchRunStatus`, `ReviewKind`, `ReviewVerdict`, `GateRunKind`, `CandidateStatus`, `PublisherKey`.
  - ORM: `CalendarSlot`, `PriceOverride`, `Article`, `ArticleVersion`, `ArticleSource`, `LedgerSource`, `Review`, `ResearchRun`, `TopicCandidateRecord`, `Publication`.
  - Settings fields `openai_admin_api_key`, `cost_reconciliation_enabled`.
  - The `tracing.py` signatures (§5.6).
  - Test fixtures `settings`, `app`, `client`, `login_as`, `db_session`, `seeded_db`, `committing_app`, `committing_client`, `committing_login_as`, `committed_seed`, `sessionmaker_committing`, `clean_db`, `fake_workflow_client`, `make_article_graph`, `make_research_graph`, `database_url`, `dbos_runtime`, `make_run`.
  - `backend/tests/api_shapes.json`; golden files `backend/fixtures/mock/golden/{article_draft.json, ledger.json, editorial.json, gate_report.json}`.

**Test database and Docker commands** (run from `mdcopilot-blog/`; reviewers replace the database with `mdcopilot_blog_obs_review_test`):
```bash
# import surface gate (run first; a failure in another track's file is a Request:, not an OBS fix)
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_obs_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
# one file (per task)
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_obs_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/observability/<file>.py
# whole track
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_obs_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/observability tests/api/test_settings_api.py tests/api/test_rbac_routes.py
# lint and types on owned paths
docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c \
  "ruff check --no-cache src/mdcopilot_blog/observability src/mdcopilot_blog/services/metrics.py src/mdcopilot_blog/services/admin_config.py src/mdcopilot_blog/services/calendar.py src/mdcopilot_blog/services/agent_runs.py src/mdcopilot_blog/api/routers/settings.py src/mdcopilot_blog/api/routers/metrics.py src/mdcopilot_blog/api/routers/calendar.py src/mdcopilot_blog/api/routers/agent_runs.py src/mdcopilot_blog/api/schemas_admin.py src/mdcopilot_blog/api/schemas_metrics.py tests/observability tests/api/test_settings_api.py \
   && ruff format --check --no-cache src/mdcopilot_blog/observability src/mdcopilot_blog/services/metrics.py src/mdcopilot_blog/services/admin_config.py src/mdcopilot_blog/services/calendar.py src/mdcopilot_blog/services/agent_runs.py src/mdcopilot_blog/api/routers/settings.py src/mdcopilot_blog/api/routers/metrics.py src/mdcopilot_blog/api/routers/calendar.py src/mdcopilot_blog/api/routers/agent_runs.py src/mdcopilot_blog/api/schemas_admin.py src/mdcopilot_blog/api/schemas_metrics.py tests/observability tests/api/test_settings_api.py \
   && mypy --cache-dir=/tmp/mypy --follow-imports=silent src/mdcopilot_blog/observability src/mdcopilot_blog/services/metrics.py src/mdcopilot_blog/services/admin_config.py src/mdcopilot_blog/services/calendar.py src/mdcopilot_blog/services/agent_runs.py src/mdcopilot_blog/api/routers/settings.py src/mdcopilot_blog/api/routers/metrics.py src/mdcopilot_blog/api/routers/calendar.py src/mdcopilot_blog/api/routers/agent_runs.py src/mdcopilot_blog/api/schemas_admin.py src/mdcopilot_blog/api/schemas_metrics.py"
```
Below, `OBS_TEST <file>` means the "one file" command with that file.

**Owner inputs and fallbacks.**

| Input | Needed for | If missing |
|---|---|---|
| `OPENAI_ADMIN_API_KEY` and `BLOG_COST_RECONCILIATION_ENABLED=true` | a real Costs API reconciliation | Reconciliation reports `status="disabled"` and sends nothing. It is built and tested only against `httpx.MockTransport`. OBS never calls the real API (§9 rule 1: OBS makes no live calls). |
| Owner runs the `observability` profile (Phoenix) | viewing traces | Tracing stays exporter-less (no-op spans). Phoenix is not part of acceptance; `OBSERVABILITY.md` documents the steps. |
| Nothing else | — | — |

**Contract gaps and the decisions this plan takes.** The implementer files one `Request:` line per item in `requests/obs.md` at the start of OBS-1 and builds the stated fallback:
1. INT's `maintenance.reconcile_costs` step has no seam signature in §5.6. OBS provides `observability.reconciliation.reconcile_openai_costs` (OBS-2).
2. §10.8 says "OBS (test)" for the D9 trace check, but the full mock run is INT's. OBS provides `services.metrics.find_untraced_llm_calls` and tests it on seeded rows and on a real `hello_pipeline` run (OBS-7). INT calls it after `test_int_daily_mock_run.py`.
3. `GET /settings/brand` lists no error, but `load_brand_profile` raises `LookupError` when no row is active. OBS answers 404 `Brand profile not found`.
4. `PUT /pillars` lists "unknown key" under 422 `Pillar rotation invalid`, but `PillarIn.key: PillarKey` makes FastAPI reject an unknown key with 422 `Request validation failed` first. OBS keeps the typed field. Missing or duplicate keys, weekdays outside 0..6 and conflicts give `Pillar rotation invalid`.
5. The `PUT /settings` compensation writes a second audit action, `settings.update_reverted`, which is not in §4.9's list.
6. The compensation test assumes `committing_app` uses the function-scoped `fake_workflow_client` fixture, as `app` does.
7. Wire conventions UI must mirror are listed in OBS-final.

**Layering.**
- `observability/` imports `opentelemetry`, `httpx`, `db.models`, `settings`, `llm.gateway.CallContext` and nothing from `pydantic_ai`, `openai` or `dbos`.
- `services/*` import `api.schemas*` and `api.deps.Principal`, as Phase 1's `services/runs.py` does.
- No OBS module calls `opentelemetry.trace.set_tracer_provider`.

---

### OBS-1: Tracing (`observability/tracing.py`)

**Files.** Modify `pkg/observability/tracing.py` (replace FOUND's no-op bodies, keep every signature). Keep `pkg/observability/__init__.py` as a docstring-only module. Create `backend/tests/observability/conftest.py` (fixture `in_memory_spans` only in this task) and `backend/tests/observability/test_obs_tracing.py`. Create `.superpowers/sdd/phases-2-10/requests/obs.md` lines (gaps 1–6 above).

**Interfaces.**
- Consumes: `Settings.otel_exporter_otlp_endpoint`, `Settings.app_version`, `Settings.app_env`; `llm.gateway.CallContext`.
- Produces (contract signatures unchanged):
  - `class SpanRecorder(Protocol)` with `set_usage(self, *, input_tokens: int, output_tokens: int, cost_usd: Decimal) -> None` and `set_error(self, error_class: str) -> None`.
  - `def configure_tracing(settings: Settings, *, service_name: Literal["api", "worker"]) -> None`
  - `def otel_trace_id(trace_id: str) -> int`
  - `@contextmanager def llm_span(operation: Literal["chat", "web_search", "embeddings"], *, ctx: CallContext, provider: str, model: str, agent_name: str | None) -> Iterator[SpanRecorder]`
  - `@contextmanager def step_span(step_name: str, *, run_id: uuid.UUID | None, attempt_id: uuid.UUID | None, trace_id: str, agent_name: str | None = None) -> Iterator[None]`
- Additive public helpers (OBS-owned, not in §5.6; used by tests and INT): `def use_tracer_provider(provider: TracerProvider | None) -> None` and `def current_tracer_provider() -> TracerProvider | None`. Module constants: `TRACER_NAME = "mdcopilot_blog"`, `COST_ATTRIBUTE = "mdcopilot_blog.cost_usd"`.

**Behaviour rules.**
1. The module holds one private `_provider: TracerProvider | None = None`. While it is `None`, both context managers use `NoOpTracerProvider().get_tracer(TRACER_NAME)`: spans are non-recording and every recorder call is a no-op. The global OTel provider is never read or set.
2. `use_tracer_provider(p)` shuts down the previous `_provider`, but only if it was created by `configure_tracing` and is not `p`. It then sets `_provider = p`.
3. `configure_tracing`:
   - Strips the endpoint. If it is `None` or empty after the strip, it calls `use_tracer_provider(None)` and returns without constructing an exporter.
   - Otherwise the export URL is the endpoint with trailing `/` removed, plus `/v1/traces` unless it already ends with `/v1/traces`.
   - It builds `TracerProvider(resource=Resource.create({"service.name": f"mdcopilot-blog-{service_name}", "service.version": settings.app_version, "deployment.environment": settings.app_env}))`, adds `BatchSpanProcessor(OTLPSpanExporter(endpoint=<url>, timeout=10))`, marks it as configured and installs it with rule 2. A second call replaces and shuts down the first provider.
   - `OTLPSpanExporter` is referenced through the module attribute, so tests can patch it.
4. `otel_trace_id(trace_id)` returns `int(trace_id, 16)`. It raises `ValueError` unless `trace_id` is exactly 32 characters of `[0-9a-f]` (case-insensitive) and the value is non-zero.
5. Parent selection, shared by both context managers:
   - If the current span's context is valid and its `trace_id` equals `otel_trace_id(<trace id>)`, the new span is a child of the current span.
   - Otherwise the parent is a synthetic remote `SpanContext(trace_id=otel_trace_id(<trace id>), span_id=RandomIdGenerator().generate_span_id(), is_remote=True, trace_flags=TraceFlags(TraceFlags.SAMPLED))`.
   - If `otel_trace_id` raises `ValueError`, the span starts with no explicit context (a fresh trace). Tracing never raises into the caller.
6. `llm_span`:
   - Span name `f"{operation} {model}"`, kind `SpanKind.CLIENT`.
   - Attributes at start: `gen_ai.operation.name`=operation, `gen_ai.system`=provider, `gen_ai.request.model`=model, `trace_id`=ctx.trace_id. Also `run_id`=str(ctx.run_id), `attempt_id`=str(ctx.attempt_id) and `gen_ai.agent.name`=agent_name, each only when not `None` (OTel drops `None` with a warning; verified).
   - `set_usage` sets `gen_ai.usage.input_tokens` (int), `gen_ai.usage.output_tokens` (int) and `mdcopilot_blog.cost_usd` = `float(cost_usd)`. OTel drops `Decimal` values (verified).
   - `set_error(c)` sets `error.type`=c and `Status(StatusCode.ERROR, c)`.
7. `step_span`: span name `f"step {step_name}"`, kind `SpanKind.INTERNAL`, attributes `step_name`, `trace_id`, and `run_id`, `attempt_id`, `agent_name` only when not `None`.
8. Exceptions inside either block:
   - Spans start with `record_exception=False, set_status_on_exception=False`.
   - The wrapper catches `BaseException`. Unless `error.type` is already set, it sets `error.type = type(exc).__name__` and `Status(StatusCode.ERROR, type(exc).__name__)`, then re-raises.
   - No exception event and no exception message are ever put on a span, because messages can carry model output.
9. Spans never carry prompt text, model output, source text, URLs or secrets. The signatures accept none of them.

**Tests to write first** (`tests/observability/test_obs_tracing.py`; fixture `in_memory_spans` in `tests/observability/conftest.py` builds `TracerProvider()` with `SimpleSpanProcessor(InMemorySpanExporter())`, calls `use_tracer_provider(provider)`, yields the exporter, then calls `use_tracer_provider(None)`; an autouse fixture in this test module calls `use_tracer_provider(None)` after each test; `T = "0123456789abcdef0123456789abcdef"`, `R = uuid.UUID("01965b7e-0000-7000-8000-000000000001")`, `A = uuid.UUID("01965b7e-0000-7000-8000-000000000002")`):
1. `test_obs_otel_trace_id_parses_hex`:
   - `otel_trace_id(T) == 0x0123456789ABCDEF0123456789ABCDEF`.
   - `otel_trace_id(T.upper()) == 0x0123456789ABCDEF0123456789ABCDEF`.
   - `pytest.raises(ValueError)` for `"xyz"`, `"0"*32`, `T[:31]` and `T + "0"`.
2. `test_obs_spans_are_noops_without_provider`: no provider installed. `with llm_span("chat", ctx=CallContext(trace_id=T), provider="openai", model="m", agent_name=None) as rec:` then `rec.set_usage(input_tokens=1, output_tokens=2, cost_usd=Decimal("0.1"))` and `rec.set_error("X")` raise nothing, and `trace.get_current_span().is_recording() is False` inside the block. `current_tracer_provider() is None`.
3. `test_obs_llm_span_records_gen_ai_attributes` (`in_memory_spans`): `llm_span("chat", ctx=CallContext(trace_id=T, run_id=R, attempt_id=A), provider="openai", model="gpt-x", agent_name="writer")` with `set_usage(input_tokens=12, output_tokens=34, cost_usd=Decimal("0.012345"))`. Exactly one finished span, where:
   - `name == "chat gpt-x"`, `kind == SpanKind.CLIENT`, `context.trace_id == int(T, 16)`, `status.status_code == StatusCode.UNSET`, `events == ()`.
   - `dict(attributes) == {"gen_ai.operation.name": "chat", "gen_ai.system": "openai", "gen_ai.request.model": "gpt-x", "gen_ai.agent.name": "writer", "trace_id": T, "run_id": str(R), "attempt_id": str(A), "gen_ai.usage.input_tokens": 12, "gen_ai.usage.output_tokens": 34, "mdcopilot_blog.cost_usd": 0.012345}`.
4. `test_obs_llm_span_omits_missing_ids` (`in_memory_spans`, `caplog` at WARNING): `llm_span("embeddings", ctx=CallContext(trace_id=T), provider="google", model="gemini-embedding-2", agent_name=None)`.
   - The span name is `"embeddings gemini-embedding-2"`.
   - The attribute keys are exactly `{"gen_ai.operation.name", "gen_ai.system", "gen_ai.request.model", "trace_id"}`.
   - No `caplog` record comes from logger `opentelemetry.attributes`.
5. `test_obs_step_span_parents_llm_span` (`in_memory_spans`): `with step_span("produce.write_draft", run_id=R, attempt_id=A, trace_id=T, agent_name="writer"):` containing `with llm_span("web_search", ctx=CallContext(trace_id=T, run_id=R), provider="openai", model="gpt-s", agent_name="search"):`.
   - Two spans. The llm span's `parent.span_id == step span context.span_id`.
   - Both have `trace_id == int(T, 16)`.
   - The step span has name `"step produce.write_draft"`, kind `INTERNAL`, attributes `{"step_name": "produce.write_draft", "trace_id": T, "run_id": str(R), "attempt_id": str(A), "agent_name": "writer"}`.
   - The llm span name is `"web_search gpt-s"`.
6. `test_obs_llm_span_with_other_trace_is_not_nested` (`in_memory_spans`): inside `step_span(..., trace_id=T)`, open `llm_span` with `ctx=CallContext(trace_id="f"*32)`. The llm span has `context.trace_id == int("f"*32, 16)`, and its `parent.span_id != step span context.span_id`.
7. `test_obs_set_error_marks_span` (`in_memory_spans`): `rec.set_error("ModelHTTPError")`, giving status `ERROR`, `status.description == "ModelHTTPError"` and `attributes["error.type"] == "ModelHTTPError"`.
8. `test_obs_exception_marks_span_without_message` (`in_memory_spans`): raise `ValueError("secret prompt text")` inside `llm_span`.
   - `pytest.raises(ValueError)` passes.
   - The span has status `ERROR`, `description == "ValueError"`, `attributes["error.type"] == "ValueError"` and `events == ()`.
   - `"secret prompt text"` occurs neither in `str(dict(span.attributes))` nor in `span.status.description`.
9. `test_obs_exception_keeps_explicit_error_type` (`in_memory_spans`): `rec.set_error("RouteExhausted")` then raise `RuntimeError()`. `attributes["error.type"] == "RouteExhausted"` and `status.description == "RouteExhausted"`.
10. `test_obs_invalid_trace_id_still_records` (`in_memory_spans`): `CallContext(trace_id="not-hex")` gives exactly one span with `attributes["trace_id"] == "not-hex"` and `context.trace_id != 0`, and no exception.
11. `test_obs_configure_tracing_blank_endpoint_installs_nothing` (monkeypatch `tracing.OTLPSpanExporter` with a recording stub class): for endpoint `None` and `"   "`, `configure_tracing(settings.model_copy(update={"otel_exporter_otlp_endpoint": v}), service_name="api")` leaves `current_tracer_provider() is None` and the stub is constructed 0 times.
12. `test_obs_configure_tracing_builds_otlp_exporter`: the stub `RecordingExporter(SpanExporter)` stores its init kwargs, exported spans and a shutdown count. For endpoints `"http://phoenix:6006"`, `"http://phoenix:6006/"` and `"http://phoenix:6006/v1/traces"`:
    - `configure_tracing(..., service_name="worker")` constructs the stub once with `endpoint == "http://phoenix:6006/v1/traces"` and `timeout == 10`.
    - `current_tracer_provider().resource.attributes["service.name"] == "mdcopilot-blog-worker"`.
    - After `llm_span("chat", ctx=CallContext(trace_id=T), provider="openai", model="m", agent_name=None)` and `current_tracer_provider().force_flush()`, the stub has exported one span named `"chat m"`.
13. `test_obs_configure_tracing_twice_shuts_down_previous`: two calls. The first stub's shutdown count is 1, and the provider object changed.
14. `test_obs_global_tracer_provider_untouched`: `before = trace.get_tracer_provider()`, configure with the stub, then `trace.get_tracer_provider() is before`.

**Implementation notes** (verified in `mdcopilot-blog-backend:dev` + `opentelemetry-sdk==1.44.0`, `opentelemetry-exporter-otlp-proto-http==1.44.0`, 2026-09-17):
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import NonRecordingSpan, NoOpTracerProvider, SpanContext, SpanKind, Status, StatusCode, TraceFlags
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

parent = trace.set_span_in_context(NonRecordingSpan(SpanContext(
    trace_id=tid, span_id=RandomIdGenerator().generate_span_id(), is_remote=True,
    trace_flags=TraceFlags(TraceFlags.SAMPLED))))
with tracer.start_as_current_span(name, context=parent, kind=SpanKind.CLIENT, attributes=attrs,
                                  record_exception=False, set_status_on_exception=False) as span: ...
# tests: from opentelemetry.sdk.trace.export import SimpleSpanProcessor
#        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
```
- `OTLPSpanExporter(endpoint=...)` uses the given URL as is, while the environment-variable form appends `/v1/traces`. That is why rule 3 appends the suffix itself.
- `TracerProvider(shutdown_on_exit=True)` is the default, so batched spans flush at interpreter exit.
- A span started with `context=` inherits that context's `trace_id`, and a nested `start_as_current_span` without `context=` becomes a child.

**Verification.** `OBS_TEST test_obs_tracing.py`.
- Red: before the implementation, FOUND's no-ops export nothing, so tests 3–10 and 12–13 fail on span-count assertions, and `use_tracer_provider` raises `AttributeError` in the fixture.
- Green: `14 passed`.
- Also run the import gate: `1 passed` or more, with no failure in `tracing.py`.

**Acceptance covered.** §10.8 "OpenTelemetry `gen_ai.*` spans, one `trace_id` per run" (OBS part: in-memory span exporter tests); "Phoenix optional, not part of acceptance" (tracing is off without an endpoint).

---

### OBS-2: Optional OpenAI Costs reconciliation (`observability/reconciliation.py`)

**Files.** Create `pkg/observability/reconciliation.py` and `backend/tests/observability/test_obs_reconciliation.py`. Extend `tests/observability/conftest.py` with `add_llm_call` (defined in OBS-3; if OBS-2 is built first, add it here with the OBS-3 signature).

**Interfaces.**
- Consumes: `Settings.cost_reconciliation_enabled`, `Settings.openai_admin_api_key`, `Settings.mock_mode`; `LlmCall`.
- Produces:
```python
OPENAI_COSTS_URL = "https://api.openai.com/v1/organization/costs"
COSTS_API_TIMEOUT_SECONDS = 30.0
MAX_COST_PAGES = 10
class CostReconciliation(BaseModel):
    status: Literal["disabled", "ok", "error"]
    day: date | None
    provider_usd: Decimal | None
    recorded_usd: Decimal | None
    difference_usd: Decimal | None
    error: str | None
async def reconcile_openai_costs(sessionmaker: async_sessionmaker[AsyncSession], *, settings: Settings, now: datetime,
                                 transport: httpx.AsyncBaseTransport | None = None) -> CostReconciliation: ...
```

**Behaviour rules.**
1. Disabled when any of these holds: `settings.cost_reconciliation_enabled` is false, `settings.openai_admin_api_key` is `None` or its value is blank, or `settings.mock_mode` is true. In that case it returns `CostReconciliation(status="disabled", day=None, provider_usd=None, recorded_usd=None, difference_usd=None, error=None)`, creates no HTTP client and opens no session.
2. The reconciled day is `(now.astimezone(UTC).date() - 1 day)`. The window is `[day 00:00:00Z, day+1 00:00:00Z)`, because the Costs API buckets are UTC.
3. Request: `GET OPENAI_COSTS_URL` with query `start_time=<int epoch of window start>`, `end_time=<int epoch of window end>`, `bucket_width=1d` and `limit=1`, plus `page=<next_page>` on later pages. Headers are `Authorization: Bearer <admin key>` and `Accept: application/json`. The client is `httpx.AsyncClient(transport=transport, timeout=COSTS_API_TIMEOUT_SECONDS)`.
4. Pagination: while `has_more` is true and `next_page` is a non-empty string, it requests the next page. It sends at most `MAX_COST_PAGES` requests. If more pages remain after the 10th, the result is `error="OpenAI Costs API returned more than 10 pages"`.
5. `provider_usd` is the sum, over every bucket in `data` and every result whose `object == "organization.costs.result"`, of `Decimal(str(result["amount"]["value"]))`. Results whose `amount` or `value` is null are skipped. The sum is quantized to `Decimal("0.000001")`. A result whose `amount.currency` is present and not `usd` (case-insensitive) gives `error=f"OpenAI Costs API returned currency {currency.lower()}"`.
6. `recorded_usd` is `SUM(cost_usd)` over `blog_llm_calls` with `created_at >= start AND created_at < end AND COALESCE(provider_served, provider_requested) = 'openai'` (0 when there are no rows), quantized to 6 places. It is read in its own session.
7. On success it returns `status="ok"`, `day`, `provider_usd`, `recorded_usd`, `difference_usd = provider_usd - recorded_usd` and `error=None`. It logs one `logging.INFO` line `"cost reconciliation"` with `extra={"day", "provider_usd", "recorded_usd", "difference_usd"}` as strings.
8. Errors return `status="error"`, `day` set, the three amounts `None`, and one of these messages:
   - HTTP status other than 200: `f"OpenAI Costs API returned HTTP {status}"`.
   - `httpx.HTTPError` raised by the transport: `f"OpenAI Costs API request failed: {type(exc).__name__}"`.
   - Invalid JSON, a missing `data` list, or a non-list `results`: `"OpenAI Costs API response not understood"`.
   - The rule 4 and rule 5 messages.

   No error text includes the response body, headers or the key. Errors are logged at WARNING with the same message.
9. The function never raises, whatever the network or response, except for database errors.

**Tests to write first** (`tests/observability/test_obs_reconciliation.py`). Setup: `sessionmaker_committing`. A handler records every `httpx.Request` in a list. `enabled = settings.model_copy(update={"mock_mode": False, "cost_reconciliation_enabled": True, "openai_admin_api_key": SecretStr("sk-admin-test-key")})`. `NOW = datetime(2026, 9, 17, 6, 30, tzinfo=UTC)`.
1. `test_obs_reconciliation_disabled_without_flag`: flag false with the key set. The result equals `CostReconciliation(status="disabled", day=None, provider_usd=None, recorded_usd=None, difference_usd=None, error=None)`, and the request list is empty.
2. `test_obs_reconciliation_disabled_without_key`: flag true, key `None`, then key `SecretStr("  ")`. Both give `status == "disabled"` and zero requests.
3. `test_obs_reconciliation_disabled_in_mock_mode`: flag true, key set, `mock_mode=True`. `status == "disabled"`, zero requests.
4. `test_obs_reconciliation_compares_openai_spend`. Rows committed with `add_llm_call`:
   - (a) `provider_served="openai"`, `created_at=2026-09-16T10:00:00Z`, cost `1.000000`;
   - (b) `provider_served=None`, `provider_requested="openai"`, `2026-09-16T23:59:59Z`, `0.500000`;
   - (c) `provider_served="google"`, `2026-09-16T12:00:00Z`, `9.000000`;
   - (d) `provider_served="openai"`, `2026-09-17T00:00:00Z`, `3.000000`;
   - (e) `provider_requested="openai"`, `provider_served="google"`, `2026-09-16T11:00:00Z`, `2.000000`.

   The handler returns 200 JSON `{"object": "page", "data": [{"object": "bucket", "start_time": 1789516800, "end_time": 1789603200, "results": [{"object": "organization.costs.result", "amount": {"value": 1.25, "currency": "usd"}}, {"object": "organization.costs.result", "amount": {"value": 0.5, "currency": "usd"}}]}], "has_more": false, "next_page": null}`. Assert:
   - result `status == "ok"`, `day == date(2026, 9, 16)`, `provider_usd == Decimal("1.750000")`, `recorded_usd == Decimal("1.500000")`, `difference_usd == Decimal("0.250000")`, `error is None`;
   - exactly 1 request, with `method == "GET"`, `url.host == "api.openai.com"`, `url.path == "/v1/organization/costs"`;
   - `dict(url.params) == {"start_time": "1789516800", "end_time": "1789603200", "bucket_width": "1d", "limit": "1"}` and `headers["authorization"] == "Bearer sk-admin-test-key"`.
5. `test_obs_reconciliation_follows_pages`: the first response has `has_more: true, next_page: "p2"` and one amount `1.0`. The second has `has_more: false` and amount `0.5`. Assert `provider_usd == Decimal("1.500000")`, 2 requests, and the second request has `params["page"] == "p2"`.
6. `test_obs_reconciliation_http_error_hides_key` (`caplog` at DEBUG): the handler returns 401 with body `{"error": "sk-admin-test-key invalid"}`. Assert `status == "error"`, `error == "OpenAI Costs API returned HTTP 401"`, `provider_usd is None`, and that `"sk-admin-test-key"` is not in `caplog.text`.
7. `test_obs_reconciliation_transport_failure`: the handler raises `httpx.ConnectTimeout("t")`. `error == "OpenAI Costs API request failed: ConnectTimeout"`.
8. `test_obs_reconciliation_rejects_other_currency`: amount `{"value": 1, "currency": "EUR"}` gives `error == "OpenAI Costs API returned currency eur"`.
9. `test_obs_reconciliation_rejects_unknown_shape`: body `{"data": "x"}` gives `error == "OpenAI Costs API response not understood"`. A non-JSON body `"<html>"` gives the same error.
10. `test_obs_reconciliation_stops_after_ten_pages`: every response has `has_more: true, next_page: "again"`. `error == "OpenAI Costs API returned more than 10 pages"` and there are exactly 10 requests.

**Implementation notes** (read from the `openai==3.14.1` SDK source in `mdcopilot-blog-backend:dev`, `openai/resources/admin/organization/usage.py::costs` and `types/admin/organization/usage_costs_response.py`; OBS must not import `openai`, see layering):
- Path `/organization/costs` on base `https://api.openai.com/v1`.
- Query `start_time` (Unix seconds, inclusive), `end_time` (exclusive), `bucket_width` (`1d` only), `limit` (1..180 buckets) and `page` (cursor from `next_page`).
- Auth header `Authorization: Bearer <admin key>`.
- Response `{"object": "page", "data": [{"object": "bucket", "start_time": int, "end_time": int, "results": [{"object": "organization.costs.result", "amount": {"value": float | null, "currency": str | null}, "line_item": str | null, "project_id": str | null, "api_key_id": str | null, "quantity": float | null, "quantity_unit": ... | null}]}], "has_more": bool, "next_page": str | null}`.
- The organization total covers every OpenAI project on the key's organization, so `difference_usd` is informational. `OBSERVABILITY.md` says so.

**Verification.** `OBS_TEST test_obs_reconciliation.py`. Red: `ModuleNotFoundError: mdcopilot_blog.observability.reconciliation`. Green: `10 passed`.

**Acceptance covered.** §10.8 "optional OpenAI Costs reconciliation (off) … reconciliation returns `disabled` without key/flag and makes no network call".

---

### OBS-3: Agent Runs API (`GET /agent-runs`, `GET /agent-runs/{id}`)

**Files.**
- Modify `pkg/api/schemas_metrics.py` (add `AgentRunOut`, `LlmCallOut`, `AgentRunDetailOut`).
- Create `pkg/services/agent_runs.py`; modify `pkg/api/routers/agent_runs.py`.
- Extend `tests/observability/conftest.py` (helpers below).
- Create `tests/observability/test_obs_agent_runs_api.py` and `tests/observability/test_obs_openapi.py`.

**Interfaces.**
- Produces, in `schemas_metrics.py`, models with the exact §4.10 fields:
  - `AgentRunOut`: `id: uuid.UUID`, `run_id: uuid.UUID`, `attempt_id: uuid.UUID | None`, `dbos_workflow_id: str`, `dbos_step_id: int`, `step_name: str`, `agent_name: str | None`, `agent_version: str | None`, `model: str | None`, `prompt_name: str | None`, `prompt_version: int | None`, `status: StepStatus`, `tries: int`, `started_at: datetime`, `completed_at: datetime | None`, `duration_ms: int | None`, `input_tokens: int`, `output_tokens: int`, `cost_usd: Decimal`, `sources_used: list[str]`, `error: dict[str, Any] | None`, `trace_id: str`, `created_at: datetime`.
  - `LlmCallOut`: `id`, `kind: CallKind`, `agent_name: str | None`, `prompt_name: str | None`, `prompt_version: int | None`, `prompt_sha: str | None`, `provider_requested: str`, `model_requested: str`, `provider_served: str | None`, `model_served: str | None`, `fallback_from: str | None`, `attempt_index: int`, `input_tokens: int`, `output_tokens: int`, `cache_read_tokens: int`, `cache_write_tokens: int`, `reasoning_tokens: int`, `search_actions: int`, `latency_ms: int`, `status: CallStatus`, `error_class: str | None`, `error_message: str | None`, `cost_usd: Decimal`, `price_version: str`, `trace_id: str`, `created_at: datetime`.
  - `AgentRunDetailOut(AgentRunOut)`: `+ llm_calls: list[LlmCallOut]`.
- Produces in `services/agent_runs.py`:
```python
async def list_agent_runs(db: AsyncSession, *, run_id: uuid.UUID | None, status: StepStatus | None,
                          agent_name: AgentName | None, limit: int, offset: int) -> tuple[list[AgentRun], int]: ...
async def get_agent_run_detail(db: AsyncSession, agent_run_id: uuid.UUID) -> tuple[AgentRun, list[LlmCall]] | None: ...
```
- Test helpers in `tests/observability/conftest.py` (all flush only; `TRACE = "0123456789abcdef0123456789abcdef"`; `FIXED_NOW = datetime(2026, 9, 17, 6, 30, tzinfo=UTC)`, which is 12:00 Asia/Kolkata on a Thursday):
```python
async def add_run(db, *, run_date=date(2026, 9, 17), status=RunStatus.SUCCEEDED, kind=RunKind.MANUAL) -> BlogRun
async def add_attempt(db, *, run_id, workflow_name, started_at, finished_at, status=AttemptStatus.SUCCEEDED, workflow_id=None) -> RunAttempt   # workflow_id default f"wf-{uuid7()}"
async def add_agent_run(db, *, run_id, attempt_id, step_name, started_at, duration_ms, dbos_step_id,
                        status=StepStatus.SUCCEEDED, workflow_id="wf-test", agent_name=None) -> AgentRun   # completed_at = started_at + duration when duration_ms is not None
async def add_llm_call(db, *, created_at, cost_usd, run_id=None, agent_name=None, provider_requested="openai", model_requested="m",
                       provider_served=None, model_served=None, article_id=None, topic_candidate_id=None, attempt_id=None,
                       agent_run_id=None, dbos_workflow_id=None, kind=CallKind.AGENT, status=CallStatus.OK,
                       search_actions=0, input_tokens=0, output_tokens=0, trace_id=TRACE) -> LlmCall   # attempt_index 0, latency_ms 10, price_version "genai-prices==0.1.7"
```

**Behaviour rules.**
1. `GET /agent-runs` requires `Permission.AGENT_RUNS`.
   - Query: `runId: uuid | None` (alias), `status: StepStatus | None`, `agentName: AgentName | None` (alias), `limit: int = Query(20, ge=1, le=100)`, `offset: int = Query(0, ge=0)`.
   - Filters combine with AND: `run_id ==`, `status == status.value`, `agent_name == agent_name.value`.
   - Order `started_at DESC, id DESC`. `total` counts the filtered rows. Response `Page[AgentRunOut]`.
2. `GET /agent-runs/{agent_run_id}` requires `Permission.AGENT_RUNS`. A missing row gives 404 `Agent run not found` (detail `f"agent run {agent_run_id} not found"`). `llm_calls` are the rows with `agent_run_id == id`, ordered `created_at ASC, id ASC`.
3. An invalid `status`, `agentName` or non-UUID path gives 422 `Request validation failed`.
4. Read-only: no audit, no commit.

**Tests to write first.**
- `tests/observability/test_obs_openapi.py`:
  - Module constant `OBS_MODELS: list[str]`, extended by each later task. Here it is `["AgentRunOut", "LlmCallOut", "AgentRunDetailOut"]`.
  - `test_obs_model_matches_shape_file[model]`:
    - `SHAPES = json.loads((Path(__file__).resolve().parents[1] / "api_shapes.json").read_text())`.
    - `schemas = create_app(settings).openapi()["components"]["schemas"]`.
    - The component is the single existing key among `model`, `f"{model}-Output"` and `f"{model}-Input"` (assert exactly one exists).
    - `sorted(component["properties"]) == SHAPES[model]["props"]`.
    - `sorted(p for p, s in component["properties"].items() if {"type": "null"} in s.get("anyOf", [])) == SHAPES[model]["nullable"]`.
- `tests/observability/test_obs_agent_runs_api.py` (fixtures `app`, `client`, `login_as`, `db_session`). Setup: `add_run` gives R1 and R2. `add_attempt(R1, workflow_name="produce_article", started_at=FIXED_NOW, finished_at=FIXED_NOW)` gives A1. Then:
  - S1: R1, A1, `produce.write_draft`, writer, SUCCEEDED, started `FIXED_NOW - 3 min`, step id 1;
  - S2: R1, A1, `produce.fact_check`, fact_check, FAILED, `FIXED_NOW - 2 min`, step id 2;
  - S3: R2, attempt `None`, `discover.gather_signals`, agent `None`, RUNNING, `FIXED_NOW - 1 min`, step id 3, duration `None`, workflow_id `"wf-other"`;
  - three `add_llm_call` rows with `agent_run_id=S1.id` at `FIXED_NOW - 170 s`, `- 175 s` and `- 160 s`, costs `0.1`, `0.2`, `0.3`.

  Tests:
  1. `test_obs_agent_runs_list_newest_first`: reviewer gets 200. `[i["id"] for i in body["items"]] == [str(S3.id), str(S2.id), str(S1.id)]`, `total == 3`, `limit == 20`, `offset == 0`. `set(body["items"][0]) == set(SHAPES["AgentRunOut"]["props"])`.
  2. `test_obs_agent_runs_filters`: `?runId=<R1>` gives ids `[S2, S1]` and total 2. `?status=FAILED` gives `[S2]`. `?agentName=writer` gives `[S1]`. `?runId=<R1>&status=RUNNING` gives `[]` and total 0.
  3. `test_obs_agent_runs_pagination`: `?limit=1&offset=1` gives items `[S2]`, total 3. `?limit=0` gives 422; `?limit=101` gives 422; `?offset=-1` gives 422.
  4. `test_obs_agent_runs_invalid_filters_422`: `?status=DONE` and `?agentName=nobody` give 422 with title `Request validation failed`.
  5. `test_obs_agent_run_detail_lists_calls_in_order`: `GET /agent-runs/<S1>` gives 200. `[c["costUsd"] for c in body["llmCalls"]] == ["0.200000", "0.100000", "0.300000"]`, `body["stepName"] == "produce.write_draft"` and `set(body) == set(SHAPES["AgentRunDetailOut"]["props"])`.
  6. `test_obs_agent_run_detail_404`: a random UUID gives 404, title `Agent run not found`.
  7. `test_obs_agent_runs_rbac`: an editor on both routes gets 403 with detail `missing permission blog.agent_runs`. The anonymous `client` gets 401 with title `Not authenticated` on both.

**Implementation notes.** Routers follow Phase 1's `runs.py`: `Annotated[Principal, Depends(require_permission(Permission.AGENT_RUNS))]`, `response_model=Page[AgentRunOut]`, and conversion with `AgentRunOut.model_validate(row)` (`from_attributes`). Query aliases use `Query(alias="runId")`.

**Verification.**
- `OBS_TEST test_obs_agent_runs_api.py`. Red: 404 `Not Found` for every route (stub router). Green: `7 passed`.
- `OBS_TEST test_obs_openapi.py`. Red: `StopIteration` or an assertion because the components are missing. Green: `3 passed`.
- `tests/api/test_rbac_routes.py` still green.

**Acceptance covered.** §10.5 "Agent Runs timeline … OBS (`/agent-runs`)"; §8.3 route test set.

---

### OBS-4: Cost report (`GET /metrics/costs`) and reporting timezone

**Files.** Modify `pkg/api/schemas_metrics.py` (`CostRowOut`, `CostReportOut`, `CostGroupBy`). Create `pkg/services/metrics.py` (this task's part). Modify `pkg/api/routers/metrics.py`. Extend conftest (`add_research_run`, `CostDataset`, `add_cost_dataset`). Create `tests/observability/test_obs_costs.py` and `test_obs_costs_api.py`. Extend `OBS_MODELS`.

**Interfaces.**
```python
# schemas_metrics.py
CostGroupBy = Literal["day", "week", "month", "agent", "model", "article", "research_run", "topic"]
class CostRowOut(ApiModel): key: str; label: str; cost_usd: Decimal; calls: int; input_tokens: int; output_tokens: int; search_actions: int
class CostReportOut(ApiModel):
    group_by: str
    from_at: datetime = Field(alias="from")
    to_at: datetime = Field(alias="to")
    total_usd: Decimal
    rows: list[CostRowOut]
# services/metrics.py
def utcnow() -> datetime: ...                      # datetime.now(UTC); routers call metrics.utcnow() through the module attribute
async def reporting_timezone(db: AsyncSession, settings: Settings) -> str: ...   # (await load_effective_config(db, settings)).schedule.timezone
async def cost_report(db: AsyncSession, settings: Settings, *, group_by: CostGroupBy, from_at: datetime | None,
                      to_at: datetime | None, article_id: uuid.UUID | None, run_id: uuid.UUID | None, now: datetime) -> CostReportOut: ...
```
Conftest:
```python
async def add_research_run(db, *, run_id, kind, status, started_at, finished_at=None, themes_covered=()) -> ResearchRun  # window_days 7, trace_id TRACE
@dataclass(frozen=True)
class CostDataset: run1: uuid.UUID; run2: uuid.UUID; article_a1: uuid.UUID; topic_t1: uuid.UUID; rr1: uuid.UUID; rr2: uuid.UUID; human_attempt: uuid.UUID
async def add_cost_dataset(db) -> CostDataset
```
`add_cost_dataset` inserts runs R1 and R2, then the research runs:
- RR1: R1, `broad`, `succeeded`, started `2026-09-13T18:30:00Z`, finished `2026-09-13T19:30:00Z`;
- RR2: R2, `deep`, `running`, started `2026-08-31T18:55:00Z`, finished `None`.

It also inserts attempt H (R1, `workflow_name="regenerate_component"`). A1 and T1 are fixed UUIDs with no rows. The seven calls:

| call | created_at (UTC) | cost | agent_name | requested | served | run | attempt | article | topic | search_actions | in/out |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c1 | 2026-09-17T06:00:00Z | 0.100000 | writer | openai:gpt-a | openai:gpt-a-2026 | R1 | H | A1 | — | 0 | 1000/200 |
| c2 | 2026-09-16T18:00:00Z | 0.200000 | writer | openai:gpt-a | google:gem-b | R1 | — | A1 | — | 0 | 2000/300 |
| c3 | 2026-09-13T19:00:00Z | 0.300000 | search | openai:gpt-s | — / — | R1 | — | — | — | 2 | 500/50 |
| c4 | 2026-09-13T18:00:00Z | 0.400000 | — | google:emb | google:emb | R2 | — | — | T1 | 0 | 100/0 |
| c5 | 2026-08-31T19:00:00Z | 0.500000 | research | google:gem-b | google:gem-b | R2 | — | — | — | 0 | 3000/400 |
| c6 | 2026-08-31T18:00:00Z | 0.600000 | ideation | google:gem-b | google:gem-b | R2 | — | — | T1 | 0 | 4000/500 |
| c7 | 2026-09-17T07:00:00Z | 0.700000 | search | openai:gpt-s | openai:gpt-s | R1 | — | — | — | 1 | 600/60 |

**Behaviour rules.**
1. `GET /metrics/costs` requires `Permission.VIEW`.
   - Query `groupBy: CostGroupBy` (alias, required), `from: datetime | None` (alias), `to: datetime | None` (alias), `articleId: uuid | None` (alias), `runId: uuid | None` (alias).
   - The router passes `now=metrics.utcnow()`.
2. Window: `to_at = to or now`, `from_at = from or (to_at - 30 days)`, half-open `created_at >= from_at AND created_at < to_at`.
   - A naive `from` or `to` gives 422 `Request validation failed`, detail `[{"type": "value_error", "loc": ["query", "<from|to>"], "msg": "must include a timezone offset"}]`.
   - `from_at >= to_at` gives the same shape with `loc ["query", "from"]` and `msg "must be earlier than to"`.
   - A missing or unknown `groupBy` gives FastAPI's 422.
3. Filters: `article_id == articleId`, `run_id == runId`, combined with AND on top of the window.
4. Timezone `tz = await reporting_timezone(db, settings)`.
5. Grouping keys and labels (`key` never null):
   - `day`, `week`, `month`: `bucket = date_trunc('<unit>', timezone(tz, created_at))`. `key = bucket.date().isoformat()`. Label: day `YYYY-MM-DD`; week `f"{iso_year}-W{iso_week:02d}"` from `bucket.date().isocalendar()`; month `YYYY-MM`. Rows are ordered by key ascending.
   - `agent`: `key = agent_name`, `label = key`. Null gives key `none`, label `No agent`.
   - `model`: when `model_served IS NULL`, `key = provider_requested || ':' || model_requested`; otherwise `COALESCE(provider_served, provider_requested) || ':' || model_served`. `label = key`.
   - `article`: `key = str(article_id)`. Label is `blog_articles.title`, else `blog_articles.slug`, else `f"Article {key[:8]}"` (LEFT JOIN). Null gives key `none`, label `No article`.
   - `topic`: `key = str(topic_candidate_id)`. Label is `blog_topic_candidates.title`, else `f"Topic {key[:8]}"`. Null gives key `none`, label `No topic`.
   - `research_run`: only for calls with `agent_name IN ('search','research')` and `run_id` not null. The matching research run comes from a LEFT JOIN LATERAL on `blog_research_runs rr` with `rr.run_id = call.run_id AND rr.started_at <= call.created_at AND (rr.finished_at IS NULL OR rr.finished_at >= call.created_at)`, ordered `rr.started_at DESC, rr.id DESC`, `LIMIT 1`. `key = str(rr.id)`, `label = f"{rr.kind} research {timezone(tz, rr.started_at).date().isoformat()}"`. Every other call gets key `none`, label `No research run`.
   - Non-time groups are ordered `cost_usd DESC, key ASC`.
6. Each row: `cost_usd = SUM(cost_usd)`, `calls = COUNT(*)`, `input_tokens = SUM(input_tokens)`, `output_tokens = SUM(output_tokens)`, `search_actions = SUM(search_actions)`, over all statuses. Groups with no calls are not returned (no zero-fill).
7. `total_usd` is one separate `SELECT COALESCE(SUM(cost_usd), 0)` with the same window and filters. It therefore equals the sum of the rows' `cost_usd`.
8. Rule A: `runId` totals include every attempt's calls, including human-action attempts. Rule C does not apply to cost views.

**Tests to write first.**
`tests/observability/test_obs_costs.py` (`db_session` after `seed_defaults`, so the timezone is `Asia/Kolkata`; `ds = await add_cost_dataset(db)`; `NOW = FIXED_NOW`; `W = (datetime.fromisoformat("2026-09-13T00:00:00+05:30"), datetime.fromisoformat("2026-09-18T00:00:00+05:30"))`; `ALL = (datetime.fromisoformat("2026-08-01T00:00:00+05:30"), datetime.fromisoformat("2026-10-01T00:00:00+05:30"))`). Rows are compared as `[(r.key, r.label, r.cost_usd, r.calls) ...]` with `Decimal` values:
1. `test_obs_costs_by_day`: window W gives `[("2026-09-13","2026-09-13",Decimal("0.4"),1), ("2026-09-14","2026-09-14",Decimal("0.3"),1), ("2026-09-16","2026-09-16",Decimal("0.2"),1), ("2026-09-17","2026-09-17",Decimal("0.8"),2)]` and `total_usd == Decimal("1.7")`.
2. `test_obs_costs_by_week`: W gives `[("2026-09-07","2026-W37",Decimal("0.4"),1), ("2026-09-14","2026-W38",Decimal("1.3"),4)]`.
3. `test_obs_costs_by_month`: ALL gives `[("2026-08-01","2026-08",Decimal("0.6"),1), ("2026-09-01","2026-09",Decimal("2.2"),6)]` and total `2.8`.
4. `test_obs_costs_by_agent`: ALL gives `[("search","search",Decimal("1.0"),2), ("ideation","ideation",Decimal("0.6"),1), ("research","research",Decimal("0.5"),1), ("none","No agent",Decimal("0.4"),1), ("writer","writer",Decimal("0.3"),2)]`. The `search` row has `search_actions == 3`, `input_tokens == 1100` and `output_tokens == 110`.
5. `test_obs_costs_by_model`: ALL gives `[("google:gem-b","google:gem-b",Decimal("1.3"),3), ("openai:gpt-s","openai:gpt-s",Decimal("1.0"),2), ("google:emb","google:emb",Decimal("0.4"),1), ("openai:gpt-a-2026","openai:gpt-a-2026",Decimal("0.1"),1)]`.
6. `test_obs_costs_by_article`: ALL gives `[("none","No article",Decimal("2.5"),5), (str(ds.article_a1), f"Article {str(ds.article_a1)[:8]}", Decimal("0.3"), 2)]`.
7. `test_obs_costs_by_article_uses_title`: separate DB state. `g = await make_article_graph(db)`, then `UPDATE app.blog_articles SET title='Specialist access' WHERE id=g.article_id`. One `add_llm_call(article_id=g.article_id, cost_usd=Decimal("0.05"), created_at=NOW - timedelta(hours=1))`. `group_by="article"` with the default window gives one row with `(str(g.article_id), "Specialist access", Decimal("0.05"), 1)`.
8. `test_obs_costs_by_topic`: ALL gives `[("none","No topic",Decimal("1.8"),5), (str(ds.topic_t1), f"Topic {str(ds.topic_t1)[:8]}", Decimal("1.0"), 2)]`.
9. `test_obs_costs_by_research_run`: ALL gives `[("none","No research run",Decimal("2.0"),5), (str(ds.rr2),"deep research 2026-09-01",Decimal("0.5"),1), (str(ds.rr1),"broad research 2026-09-14",Decimal("0.3"),1)]`.
10. `test_obs_costs_filters_and_rule_a`:
    - `article_id=ds.article_a1`, `group_by="day"`, ALL gives `[("2026-09-16",…,Decimal("0.2"),1), ("2026-09-17",…,Decimal("0.1"),1)]` and total `0.3`.
    - `run_id=ds.run1`, `group_by="agent"`, ALL gives total `Decimal("1.3")` with keys `["search","writer"]`. The writer row (`Decimal("0.3")`, 2 calls) includes c1, recorded on the human-action attempt H.
    - `run_id=ds.run2`, `group_by="research_run"`, ALL gives `[("none","No research run",Decimal("1.0"),2), (str(ds.rr2),"deep research 2026-09-01",Decimal("0.5"),1)]`. RR2 has `finished_at IS NULL`, so it matches c5. c7 (search on R1, after RR1 finished) is `none` in the unfiltered test 9.
11. `test_obs_costs_default_window`: `from_at=None, to_at=None, now=NOW`, `group_by="agent"`. `report.from_at == datetime(2026, 8, 18, 6, 30, tzinfo=UTC)`, `report.to_at == NOW`, `total_usd == Decimal("2.1")` (c7 at `07:00Z` is excluded).
12. `test_obs_costs_total_equals_raw_sql[group_by]`, parametrized over all eight values: window ALL, and `report.total_usd == await db.scalar(text("SELECT COALESCE(SUM(cost_usd),0) FROM app.blog_llm_calls WHERE created_at >= :f AND created_at < :t"), {"f": ALL[0], "t": ALL[1]})` and `sum(r.cost_usd for r in report.rows) == report.total_usd`.

`tests/observability/test_obs_costs_api.py` (`app`, `login_as`, `db_session` with seed and `add_cost_dataset`):
1. `test_obs_costs_api_day`: a viewer requesting `GET /api/blog-agent/metrics/costs?groupBy=day&from=2026-09-13T00:00:00%2B05:30&to=2026-09-18T00:00:00%2B05:30` gets 200 with:
   - `body["groupBy"] == "day"`, `body["totalUsd"] == "1.700000"`;
   - `[r["key"] for r in body["rows"]] == ["2026-09-13","2026-09-14","2026-09-16","2026-09-17"]`;
   - `set(body) == {"groupBy","from","to","totalUsd","rows"}`, `datetime.fromisoformat(body["from"]) == W[0]`, `set(body["rows"][0]) == set(SHAPES["CostRowOut"]["props"])`.
2. `test_obs_costs_api_validation`: missing `groupBy`, `groupBy=year`, `from=2026-09-13T00:00:00` (naive), and `from=2026-09-18T00:00:00%2B05:30&to=2026-09-13T00:00:00%2B05:30` each give 422 with title `Request validation failed`. For the naive case, `body["detail"][0]["msg"] == "must include a timezone offset"`. For the reversed case, `body["detail"][0]["msg"] == "must be earlier than to"`.
3. `test_obs_costs_api_default_window_uses_now`: `monkeypatch.setattr(metrics, "utcnow", lambda: FIXED_NOW)`, then `?groupBy=agent` gives `totalUsd == "2.100000"`.
4. `test_obs_costs_api_requires_session`: anonymous gives 401. No 403 case exists, because all five roles hold `blog.view`; the viewer 200 is asserted in test 1.

`OBS_MODELS += ["CostRowOut", "CostReportOut"]`.

**Implementation notes** (verified against `pgvector/pgvector:pg16` with SQLAlchemy 2.0.54 and psycopg 3 on 2026-09-17: `GROUP BY date_trunc('week', timezone('Asia/Kolkata', created_at))` with bound parameters works, and `2026-09-13T17:00Z` falls in the week of 2026-09-07):
```python
bucket = func.date_trunc("week", func.timezone(tz, LlmCall.created_at))
stmt = select(bucket, func.sum(LlmCall.cost_usd), func.count()).where(...).group_by(bucket).order_by(bucket)
rr = (select(ResearchRun.id, ResearchRun.kind, ResearchRun.started_at)
      .where(ResearchRun.run_id == LlmCall.run_id, ResearchRun.started_at <= LlmCall.created_at,
             or_(ResearchRun.finished_at.is_(None), ResearchRun.finished_at >= LlmCall.created_at))
      .order_by(ResearchRun.started_at.desc(), ResearchRun.id.desc()).limit(1).lateral("rr"))
stmt = select(...).select_from(LlmCall).outerjoin(rr, true())
```
The lateral subquery applies only when `LlmCall.agent_name.in_(("search", "research"))`. Put that condition inside a `CASE` for the key, not in `WHERE`, so other calls land in `none`.

**Verification.**
- `OBS_TEST test_obs_costs.py`. Red: `ModuleNotFoundError` or `AttributeError: cost_report`. Green: `19 passed` (11 plain tests plus 8 parametrized cases).
- `OBS_TEST test_obs_costs_api.py`. Green: `4 passed`.
- `OBS_TEST test_obs_openapi.py`. Green: `5 passed`.

**Acceptance covered.**
- §10.8: "Cost views: … per article, research run, topic, agent, model"; "Dashboard totals equal the SQL sum of `blog_llm_calls` over the same window (tested)" (cost report part); "Per-article cost shown on the article page" (API side, `groupBy=article&articleId=`).
- Rule A (run totals include human-action attempts).

---

### OBS-5: Latency report (`GET /metrics/latency`)

**Files.** Modify `schemas_metrics.py` (`LatencyRowOut`, `LatencyReportOut`), `services/metrics.py` and `routers/metrics.py`. Create `tests/observability/test_obs_latency.py`. Extend `OBS_MODELS`.

**Interfaces.**
```python
class LatencyRowOut(ApiModel): step_name: str; count: int; p50_ms: int; p90_ms: int
class LatencyReportOut(ApiModel): days: int; rows: list[LatencyRowOut]
STAGE_ORDER: tuple[str, ...]   # services/metrics.py, see rule 4
async def latency_report(db: AsyncSession, settings: Settings, *, days: int, now: datetime) -> LatencyReportOut: ...
```

**Behaviour rules.**
1. `GET /metrics/latency` requires `Permission.VIEW`. Query `days: int = Query(30, ge=1, le=90)`. The router passes `now=metrics.utcnow()`.
2. Window start = local midnight (reporting timezone) of `local_date(now, tz) - (days - 1)`, as UTC. Upper bound `<= now`.
3. Step rows (Rule C): `blog_agent_runs` joined to `blog_run_attempts` on `attempt_id`, with:
   - `attempts.workflow_name IN ('discover_topics','produce_article')`;
   - `agent_runs.status = 'SUCCEEDED'`, `duration_ms IS NOT NULL`;
   - `agent_runs.started_at >= start AND <= now`.

   Grouped by `step_name`: `count = COUNT(*)`, `p50_ms = round(percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms)::numeric)::int`, and `p90_ms` the same with 0.9. Rows with a null `attempt_id` are excluded.
4. Workflow rows: `step_name` is `discover_topics` or `produce_article`, computed over `blog_run_attempts` with that `workflow_name`, `status = 'SUCCEEDED'`, `finished_at IS NOT NULL`, `started_at >= start AND <= now`, and duration `(extract(epoch from finished_at - started_at) * 1000)::bigint`. The same count, p50 and p90 apply. A workflow with no attempts gets no row.
5. Order:
   - First, step rows in the order of `STAGE_ORDER`: `discover.open_attempt`, `discover.manual_topic`, `discover.gather_signals`, `discover.build_ledger`, `discover.synthesize_research`, `discover.ideate_topics`, `discover.check_novelty_and_score`, `discover.select_topic`, `discover.finish`, `discover.mark_failed`, then `produce.open_attempt`, `produce.deep_research`, `produce.build_research_packet`, `produce.write_draft`, `produce.fact_check`, `produce.clinical_review`, `produce.editorial_review`, `produce.revise`, `produce.verify_facts`, `produce.seo`, `produce.quality_gates`, `produce.fix_pass.revise`, `produce.fix_pass.verify_facts`, `produce.fix_pass.seo`, `produce.fix_pass.quality_gates`, `produce.finish`, `produce.mark_failed`.
   - Then step names not in `STAGE_ORDER`, alphabetically.
   - Then the `discover_topics` row, then the `produce_article` row.

**Tests to write first** (`tests/observability/test_obs_latency.py`; `db_session` with seed). Setup: run R. Attempts:
- AT1 `discover_topics` SUCCEEDED `2026-09-17T01:00:00Z`–`01:05:00Z`;
- AT2 `produce_article` SUCCEEDED `01:10:00Z`–`01:20:00Z`;
- AT3 `regenerate_article` SUCCEEDED `02:00:00Z`–`02:01:00Z`;
- AT4 `produce_article` FAILED `03:00:00Z`–`03:00:30Z`.

Agent runs (`workflow_id` per attempt, unique step ids):
- AT1 `discover.gather_signals` 1000, 2000, 3000 ms;
- AT2 `produce.write_draft` 100, 200, 300, 400 ms;
- AT2 `produce.write_draft` FAILED 9999 ms;
- AT2 `produce.write_draft` SUCCEEDED `duration_ms=None`;
- AT3 `regenerate_article.write_draft` 5000 ms;
- AT2 `produce.write_draft` 50000 ms started `2026-08-01T00:00:00Z`;
- AT2 `zz.custom_step` 10 ms.

All started on 2026-09-17 unless stated.
1. `test_obs_latency_percentiles_rule_c`: `latency_report(days=30, now=FIXED_NOW)` rows as `(step_name, count, p50_ms, p90_ms)` equal `[("discover.gather_signals",3,2000,2800), ("produce.write_draft",4,250,370), ("zz.custom_step",1,10,10), ("discover_topics",1,300000,300000), ("produce_article",1,600000,600000)]` and `days == 30`.
2. `test_obs_latency_rounds_half_up`: an extra step `produce.seo` with 1 ms and 2 ms under AT2 gives the row `("produce.seo", 2, 2, 2)`. It is placed after `produce.write_draft` and before `zz.custom_step`.
3. `test_obs_latency_window`: `days=1, now=FIXED_NOW` makes the window start `2026-09-16T18:30:00Z`; all 2026-09-17 rows are counted, and the 2026-08-01 row is still excluded. A row started `2026-09-16T18:00:00Z` (`produce.fact_check`, 70 ms, AT2) is absent from the `days=1` result and present with count 1 in the `days=30` result.
4. `test_obs_latency_api`: viewer `GET /api/blog-agent/metrics/latency` with `metrics.utcnow` monkeypatched to `FIXED_NOW` gives 200, `body["days"] == 30` and `body["rows"][0] == {"stepName": "discover.gather_signals", "count": 3, "p50Ms": 2000, "p90Ms": 2800}`. `?days=0` and `?days=91` give 422. Anonymous gives 401.

`OBS_MODELS += ["LatencyRowOut", "LatencyReportOut"]`.

**Implementation notes** (verified on `pgvector/pgvector:pg16`, 2026-09-17: `round(percentile_cont(0.5) … ::numeric)` gives 2 for (1, 2); p50/p90 are 250/370 for (100..400) and p90 is 2800 for (1000, 2000, 3000); the epoch difference of 2.5 s is 2500 ms). Compiled form checked with SQLAlchemy 2.0.54:
```python
p50 = cast(func.round(cast(func.percentile_cont(0.5).within_group(AgentRun.duration_ms), Numeric)), Integer)
```
Do not use `round()` on `double precision`, whose tie rounding is platform-dependent.

**Verification.** `OBS_TEST test_obs_latency.py`. Red: `AttributeError: latency_report` and 404 on the route. Green: `4 passed`. `test_obs_openapi.py`: `7 passed`.

**Acceptance covered.** §10.8 "measured P50/P90 per stage" (API; INT copies measured values into ARCHITECTURE §21–§22). Rule C for `/metrics/latency`.

---

### OBS-6: Dashboard (`GET /metrics/dashboard`)

**Files.** Modify `schemas_metrics.py` (`RecommendedTopicOut`, `QualitySummaryOut`, `TodayCardOut`, `PipelineStageOut`, `PipelineTrackerOut`, `DashboardMetricsOut`, `DashboardOut`), `services/metrics.py` and `routers/metrics.py`. Extend conftest with `add_candidate`. Create `tests/observability/test_obs_dashboard.py`. Extend `OBS_MODELS`.

**Interfaces.**
- Schemas use the exact §4.10 fields.
  - Date fields are declared `date: dt.date` with `import datetime as dt`, so the field name does not shadow the type under mypy.
  - `PipelineStageOut.status: Literal["pending","running","done","failed","skipped"]`.
  - `TodayCardOut.research_status: Literal["not_started","running","done","failed"]`.
```python
TRACKER_STAGES: tuple[tuple[str, str], ...]   # (step value, label), rule 6
async def build_dashboard(db: AsyncSession, settings: Settings, *, now: datetime) -> DashboardOut: ...
```
Conftest:
```python
async def add_candidate(db, *, run_id, round_no, position, status, total_score=None, novelty_score=None, evidence_score=None,
                        business_relevance=None, title="Candidate", why_now="Now", pillar_key="A", created_at=None,
                        selected_at=None) -> TopicCandidateRecord   # other NOT NULL text columns "x"
```

**Behaviour rules.**
1. `GET /metrics/dashboard` requires `Permission.VIEW`. The router passes `now=metrics.utcnow()`.
   - `generated_at = now` and `timezone = reporting_timezone`.
   - `today_local = local_date(now, tz)`.
   - `today_start` = local midnight of `today_local`; `week_start` = local midnight of `today_local - today_local.weekday()` days; `month_start` = local midnight of `today_local.replace(day=1)`; `window_start` = local midnight of `today_local - 29 days`. All windows end inclusive at `now`.
2. The day's run is the newest `blog_runs` row with `run_date == today_local` (`created_at DESC, id DESC`), or `None`.
3. `TodayCardOut`:
   - `date = today_local`, `run_id`, `run_status` (current status; Rule B: a re-opened run shows `QUEUED` or `PRODUCING`).
   - `research_status`, with no run giving `not_started`. Otherwise, from the newest `blog_research_runs` row of the run with `kind = broad` (by `started_at DESC, id DESC`): `running` → `running`; `succeeded` or `partial` → `done`; `insufficient_evidence` or `failed` → `failed`. With no such row, from the run status: `RESEARCHING` → `running`; `FAILED` → `failed`; `TOPICS_READY`, `WAITING_FOR_TOPIC`, `PRODUCING`, `SUCCEEDED` → `done`; `QUEUED`, `CANCELLED` → `not_started`.
   - `opportunities_discovered` is the count of the run's candidates with `round == max(round)` for the run and `status != 'REJECTED'` (0 when there are none).
   - `recommended_topic`: the run's `SELECTED` candidate with the newest `selected_at` (tie `id DESC`). If there is none, the candidate in the newest round with status `PASSED` or `WARNED` and the highest `total_score` (nulls last, tie `position ASC`). If there is none, `None`.
   - The article is the run's newest (`created_at DESC, id DESC`) article with status not in (`REJECTED`, `SUPERSEDED`). This gives `article_id` and `article_status`.
   - `headline_options = TitleOptions.model_validate(current_version.title_options)`, or `None` when there is no article or no current version.
   - `quality` is `None` when there is no article or no current version. Otherwise:
     - `fact_check_verdict`: newest (`created_at DESC, id DESC`) `fact_check` review on the current version, `verdict`, or `None`.
     - `source_count`: `COUNT(*)` of `blog_article_sources` for the current version.
     - `tier_mix`: `{"tier1": n1, "tier2": n2, "tier3": n3}` counted by `blog_sources.tier` over those rows. All three keys are always present.
     - `novelty_percent`: `round(candidate.novelty_score * 100, 1)` of the article's `candidate_id`, or `None`.
     - `clinical_clear`: newest `clinical` review on the current version or an ancestor (the `parent_version_id` chain), giving `verdict == "CLEAR"`, or `None`.
     - `editorial_score`: newest `editorial` review in the same chain, its `score`, or `None`.
     - `seo_complete`: newest `quality_gate` review of the current version (any `gate_run_kind`), then the `passed` of the result whose `gate == "seo_complete"`, or `None` when there is no review or no such result.
     - `gates_passed`: newest `quality_gate` review of the current version with `gate_run_kind IN ('full','fix_pass','recheck')`, giving `verdict == "PASSED"`, or `None`.
4. `DashboardMetricsOut`:
   - `window_days = 30`.
   - `posts_generated = COUNT(*)` of `blog_article_versions` with `version_no = 1` and `created_at` in `[window_start, now]`.
   - `posts_published = COUNT(*)` of `blog_articles` with `published_at` in the window.
   - `posts_pending = COUNT(*)` of `blog_articles` with status in (`READY_FOR_REVIEW`,`QUALITY_GATE_FAILED`,`APPROVED`,`SCHEDULED`,`EXPORTED`), not windowed: it is the current queue.
   - `topics_generated = COUNT(*)` of `blog_topic_candidates` with `created_at` in the window.
   - `research_sources = COUNT(*)` of `blog_sources` with `created_at` in the window.
   - `avg_generation_seconds`: for each run with at least one `produce_article` attempt that is `SUCCEEDED` with `finished_at` in the window, the sum of `finished_at - started_at` over that run's `SUCCEEDED` attempts whose `workflow_name` is `discover_topics` or `produce_article` (Rule C). The average over those runs, `round(x, 1)`, or `None`.
   - `avg_editorial_score = round(AVG(score), 4)` over `editorial` reviews with a non-null score created in the window, or `None`.
   - `duplicate_topic_rate = round(REJECTED / all, 4)` over candidates created in the window, or `None` when there are none.
   - `fact_check_pass_rate = round(PASS / all, 4)` over `fact_check` reviews created in the window, or `None`.
   - `cost_today_usd`, `cost_week_usd`, `cost_month_usd` = `COALESCE(SUM(cost_usd), 0)` over `blog_llm_calls` with `created_at >= <start> AND created_at <= now`.
5. `PipelineTrackerOut.run_id` is the day's run. `stages` are always the 17 entries of `TRACKER_STAGES` in order.
6. `TRACKER_STAGES`:

   | Step value | Label |
   |---|---|
   | `discover.open_attempt` | Start run |
   | `discover.gather_signals` | Gather signals |
   | `discover.build_ledger` | Build source ledger |
   | `discover.synthesize_research` | Synthesize research |
   | `discover.ideate_topics` | Ideate topics |
   | `discover.check_novelty_and_score` | Check novelty and score |
   | `discover.select_topic` | Select topic |
   | `produce.deep_research` | Deep research |
   | `produce.build_research_packet` | Build research packet |
   | `produce.write_draft` | Write draft |
   | `produce.fact_check` | Fact check |
   | `produce.clinical_review` | Clinical review |
   | `produce.editorial_review` | Editorial review |
   | `produce.revise` | Revise |
   | `produce.verify_facts` | Verify facts |
   | `produce.seo` | SEO |
   | `produce.quality_gates` | Quality gates |

7. Stage status. Rows are the run's `blog_agent_runs` whose `step_name` is an alias of the stage:
   - A `discover.<s>` stage matches `discover.<s>`.
   - A `produce.<s>` stage matches `produce.<s>` and `change_topic.<s>`. For `revise`, `verify_facts`, `seo` and `quality_gates` it also matches `produce.fix_pass.<s>` and `change_topic.fix_pass.<s>`.
   - Rule C: `regenerate_*`, `recheck.*` and `publish.*` never match.
   - The newest matching row (`started_at DESC, id DESC`) decides: `RUNNING` → `running`, `SUCCEEDED` → `done`, `FAILED` → `failed`, with `started_at` and `finished_at = completed_at`.
   - With no matching row, the stage is `skipped` when a later stage of the same group (D1–D7 or P1–P10) has a matching row. Otherwise it is `pending`, with both times `None`.
8. Read-only; no commit.

**Tests to write first** (`tests/observability/test_obs_dashboard.py`; `db_session` with `seed_defaults`; `NOW = FIXED_NOW` unless stated; golden files are read with `json.loads(Path(...).read_text())` relative to `backend/fixtures/mock/golden/`):
1. `test_obs_dashboard_empty`:
   - `generated_at == NOW`, `timezone == "Asia/Kolkata"`.
   - `today == TodayCardOut(date=date(2026,9,17), run_id=None, run_status=None, research_status="not_started", opportunities_discovered=0, recommended_topic=None, article_id=None, article_status=None, headline_options=None, quality=None)`.
   - `pipeline.run_id is None`, `[s.key for s in pipeline.stages] == [k for k, _ in TRACKER_STAGES]`, all statuses `pending`.
   - `metrics == DashboardMetricsOut(window_days=30, posts_generated=0, posts_published=0, posts_pending=0, topics_generated=0, research_sources=0, avg_generation_seconds=None, avg_editorial_score=None, duplicate_topic_rate=None, fact_check_pass_rate=None, cost_today_usd=Decimal("0"), cost_week_usd=Decimal("0"), cost_month_usd=Decimal("0"))`.
2. `test_obs_dashboard_today_card_with_article`:
   - Setup: `g = await make_article_graph(db, reviews=(ReviewKind.FACT_CHECK, ReviewKind.CLINICAL, ReviewKind.EDITORIAL, ReviewKind.QUALITY_GATE))`. `UPDATE blog_runs SET run_date='2026-09-17', status='SUCCEEDED'` for `g.run_id`. `UPDATE blog_topic_candidates SET novelty_score=0.9123, total_score=0.8, evidence_score=0.7, business_relevance=0.6, selected_at='2026-09-17T01:00:00Z'` for `g.candidate_id`. Read `rnd` = that candidate's `round`. `add_candidate(run_id=g.run_id, round_no=rnd, position=1, status=CandidateStatus.REJECTED, total_score=0.95)` and `add_candidate(..., position=2, status=CandidateStatus.PASSED, total_score=0.5)`.
   - `today.run_id == g.run_id`, `run_status == RunStatus.SUCCEEDED`, `research_status == "done"`, `opportunities_discovered == 2`.
   - `recommended_topic.candidate_id == g.candidate_id` with `total_score == 0.8`, `novelty_score == 0.9123`, `evidence_score == 0.7`, `business_relevance == 0.6`.
   - `article_id == g.article_id`, `article_status == ArticleStatus.READY_FOR_REVIEW`.
   - `headline_options == TitleOptions.model_validate(article_draft["output"]["titleOptions"])`.
   - Quality: `fact_check_verdict == "PASS"`, `source_count == 5`, `tier_mix == {"tier1": n1, "tier2": n2, "tier3": n3}` where `n<t>` = count of `ledger["sources"][0:5]` with `tier == t`, `novelty_percent == 91.2`, `clinical_clear is True`, `editorial_score == editorial["editorialScore"]`, `seo_complete is True`, `gates_passed is True`.
   - The test relies on FOUND's builder storing the golden payload's `editorialScore` in `blog_reviews.score` (contract §3.1: `score` is the editorial score). If the builder leaves it NULL, file a `Request:` instead of changing the service.
3. `test_obs_dashboard_quality_uses_ancestor_reviews`: graph as in test 2. Insert a child `ArticleVersion` (`version_no=2`, `parent_version_id=g.version_id`, content copied from the base row, `change_kind="human_edit"`, `created_by_kind="human"`) and set `blog_articles.current_version_id` to it.
   - `quality.clinical_clear is True` and `editorial_score == editorial["editorialScore"]` (ancestor rule).
   - `fact_check_verdict is None`, `gates_passed is None`, `seo_complete is None`, `source_count == 0`, `tier_mix == {"tier1": 0, "tier2": 0, "tier3": 0}`.
4. `test_obs_dashboard_research_status[case]`, parametrized over (run status, broad research status or `None`) → expected:
   - `("RESEARCHING","running")→running`, `("TOPICS_READY","succeeded")→done`, `("TOPICS_READY","partial")→done`, `("FAILED","insufficient_evidence")→failed`, `("FAILED","failed")→failed`;
   - `("QUEUED",None)→not_started`, `("RESEARCHING",None)→running`, `("FAILED",None)→failed`, `("WAITING_FOR_TOPIC",None)→done`, `("PRODUCING",None)→done`, `("CANCELLED",None)→not_started`.

   Setup: `add_run(run_date=date(2026,9,17), status=…)` plus, when not `None`, `add_research_run(kind=broad, status=…, started_at=NOW - 1h)`. A `deep` research run with status `failed` is also added in every case and never changes the result.
5. `test_obs_dashboard_newest_run_and_recommendation`:
   - Setup: run R_old (`run_date` 2026-09-17, inserted first) and run R_new (`run_date` 2026-09-17, inserted second), plus run R_yesterday (`run_date` 2026-09-16, inserted last).
   - Candidates of R_new: round 1 `PASSED` total 0.99 position 0; round 2 `PASSED` total 0.5 position 0; round 2 `WARNED` total 0.9 position 1; round 2 `REJECTED` total 0.95 position 2; round 2 `PASSED` total `None` position 3.
   - `today.run_id == R_new.id`, `opportunities_discovered == 3`, `recommended_topic.total_score == 0.9` (the WARNED one).
6. `test_obs_dashboard_recommendation_tie_breaks_by_position`: newest round of the day's run has `PASSED` total 0.7 position 2 and `PASSED` total 0.7 position 0. The recommended candidate is the position-0 row.
7. `test_obs_dashboard_pipeline_tracker`. Run today with `add_agent_run` rows (`started_at` on 2026-09-17, times in UTC):
   - `discover.open_attempt` SUCCEEDED 00:00; `discover.manual_topic` SUCCEEDED 00:01; `discover.select_topic` SUCCEEDED 00:02;
   - `produce.deep_research` SUCCEEDED 00:10; `produce.build_research_packet` SUCCEEDED 00:12;
   - `produce.write_draft` FAILED 00:15; `produce.write_draft` RUNNING 00:40 (fork);
   - `regenerate_article.fact_check` SUCCEEDED 01:00.

   Expected statuses in order: `done, skipped, skipped, skipped, skipped, skipped, done, done, done, running, pending, pending, pending, pending, pending, pending, pending`. The `produce.write_draft` stage has `started_at == 00:40` and `finished_at is None`. The `discover.open_attempt` stage has `finished_at == started_at + duration`.
8. `test_obs_dashboard_pipeline_aliases`: rows `change_topic.write_draft` SUCCEEDED 00:10, `produce.quality_gates` SUCCEEDED 00:20, `produce.fix_pass.quality_gates` FAILED 00:30. Stage `produce.write_draft` is `done`. Stage `produce.quality_gates` is `failed` with `started_at` 00:30. Stages `produce.fact_check` through `produce.seo` are `skipped`. `produce.deep_research` and `produce.build_research_packet` are `skipped`, and every D stage is `pending`.
9. `test_obs_dashboard_costs_equal_raw_sql`:
   - Setup: `add_cost_dataset(db)` (OBS-4). Expected `cost_today_usd == Decimal("0.1")`, `cost_week_usd == Decimal("0.6")`, `cost_month_usd == Decimal("1.5")`.
   - For each window, the value equals `SELECT COALESCE(SUM(cost_usd),0) FROM app.blog_llm_calls WHERE created_at >= :start AND created_at <= :now`, with `:start` = `2026-09-16T18:30:00Z`, `2026-09-13T18:30:00Z` and `2026-08-31T18:30:00Z` respectively, and `:now = NOW`.
10. `test_obs_dashboard_windowed_counts`:
    - Setup: `now = await db.scalar(select(func.now()))`. `g = await make_article_graph(db, reviews=(ReviewKind.FACT_CHECK, ReviewKind.EDITORIAL))`.
    - Candidates on `g.run_id`: `REJECTED` created `now - 1 day`; `PASSED` created `now - 1 day`; `PASSED` created `now - 40 days`.
    - Reviews on `g.article_id`/`g.version_id`: `fact_check` `FAIL` (payload = golden fact_check with `verdict` `FAIL`) created `now - 2 days`; `fact_check` `PASS` created `now - 40 days`; `editorial` `COMPLETED` with `score=0.5` created `now - 3 days`.
    - One `LedgerSource` row with `created_at = now - 40 days` (unique url).
    - Expected with `build_dashboard(now=now)`:
      - `posts_generated == 1`, `topics_generated == 3`, `duplicate_topic_rate == 0.3333`, `fact_check_pass_rate == 0.5`;
      - `avg_editorial_score == round((graph_editorial_score + 0.5) / 2, 4)`, where `graph_editorial_score` is read from the graph's editorial review row;
      - `research_sources == await db.scalar(select(func.count()).select_from(LedgerSource).where(LedgerSource.created_at == now))`: the graph's ledger rows share the transaction timestamp, and the extra row at `now - 40 days` is excluded;
      - `posts_pending == 1`.
11. `test_obs_dashboard_posts_published_window[offset_days, expected]`, for `(5, 1)` and `(40, 0)`: `now = await db.scalar(select(func.now()))`; `g = await make_article_graph(db, status=ArticleStatus.PUBLISHED, approved=True)`; `UPDATE blog_articles SET published_at = :now - make_interval(days => :offset)` for `g.article_id`. `build_dashboard(now=now).metrics.posts_published == expected`.
12. `test_obs_dashboard_posts_pending_statuses[status, expected]`: READY_FOR_REVIEW→1, QUALITY_GATE_FAILED→1, APPROVED→1, SCHEDULED→1, EXPORTED→1, DRAFTING→0, PUBLISHED→0, REJECTED→0. Uses `approved=True` for APPROVED, SCHEDULED, EXPORTED and PUBLISHED.
13. `test_obs_dashboard_avg_generation_seconds_rule_c`:
    - Run A (today): `discover_topics` SUCCEEDED 60 s and `produce_article` SUCCEEDED 240 s, finished `NOW - 1h`.
    - Run B: `produce_article` SUCCEEDED 100 s finished `NOW - 2h`; `discover_topics` SUCCEEDED 20 s; `regenerate_article` SUCCEEDED 50 s; `produce_article` FAILED 30 s.
    - Run C: `discover_topics` SUCCEEDED 500 s and no produce attempt.
    - Run D: `produce_article` SUCCEEDED 999 s finished `NOW - 40 days`.
    - `avg_generation_seconds == 210.0`.
14. `test_obs_dashboard_api`: `monkeypatch.setattr(metrics, "utcnow", lambda: FIXED_NOW)`. Viewer `GET /api/blog-agent/metrics/dashboard` gives 200, `set(body) == {"generatedAt","timezone","today","pipeline","metrics"}`, `body["today"]["date"] == "2026-09-17"`, `len(body["pipeline"]["stages"]) == 17`, `body["metrics"]["costTodayUsd"] == "0"`. Anonymous gives 401.

`OBS_MODELS += ["RecommendedTopicOut", "QualitySummaryOut", "TodayCardOut", "PipelineStageOut", "PipelineTrackerOut", "DashboardMetricsOut", "DashboardOut"]`.

**Implementation notes.**
- Build the windows with `datetime.combine(d, time.min, tzinfo=ZoneInfo(tz)).astimezone(UTC)`.
- Load the ancestor chain in Python: select `id, parent_version_id` for the article's versions, then walk from the current version.
- Graph rows come from FOUND's builders, and this test file never inserts article or topic rows by hand except the child version and extra reviews and candidates listed above.

**Verification.** `OBS_TEST test_obs_dashboard.py`. Red: `AttributeError: build_dashboard`. Green: `32 passed` (11 plain tests, plus 11 cases in test 4, 2 in test 11 and 8 in test 12). `test_obs_openapi.py`: `14 passed`.

**Acceptance covered.**
- §10.5 "Dashboard Today card, pipeline tracker, metrics … OBS (`/metrics/dashboard`)".
- §10.8 "Dashboard metrics (spec §26)"; "Dashboard totals equal the SQL sum of `blog_llm_calls` over the same window (tested)".
- Rule B (the today card shows the run's current status).
- Rule C (`avg_generation_seconds` and the tracker include only `discover_topics`, `produce_article` and `change_topic` steps).

---

### OBS-7: Trace coverage check (ruling D9)

**Files.** Modify `pkg/services/metrics.py`. Create `tests/observability/test_obs_trace_coverage.py`.

**Interfaces.**
```python
TRACED_WORKFLOW_PREFIXES: tuple[str, ...] = ("daily-", "manual-", "produce-", "change-topic-", "regen-", "recheck-", "publish-", "restart-")
async def find_untraced_llm_calls(db: AsyncSession) -> list[uuid.UUID]: ...   # consumer: INT (test_int_daily_mock_run.py)
```

**Behaviour rules.**
1. It returns the ids, ordered `created_at ASC, id ASC`, of every `blog_llm_calls` row where:
   - `trace_id` is empty after `trim`, or
   - `run_id IS NULL` and any of: `dbos_workflow_id` starts with a prefix in `TRACED_WORKFLOW_PREFIXES`, `attempt_id IS NOT NULL`, `article_id IS NOT NULL`, `topic_candidate_id IS NOT NULL`.
2. Rows allowed by D9 are not returned: run-less rows without those markers, for example `GET /topics/similar` embeddings, `maintenance` steps (workflow ids without a listed prefix), spike scripts and the live-evaluation harness.
3. Read-only.

**Tests to write first** (`tests/observability/test_obs_trace_coverage.py`):
1. `test_obs_untraced_calls_follow_d9` (`db_session`). Rows via `add_llm_call` (all `created_at` distinct, increasing in this order):
   - ok1: `run_id=R`;
   - ok2: `run_id=None`, no markers;
   - ok3: `run_id=None`, `dbos_workflow_id="maintenance_nightly-2026-09-17"`;
   - bad1: `run_id=None`, `dbos_workflow_id="manual-x"`;
   - bad2: `run_id=None`, `dbos_workflow_id="restart-produce-x"`;
   - bad3: `run_id=None`, `attempt_id=uuid7()`;
   - bad4: `run_id=None`, `article_id=uuid7()`;
   - bad5: `run_id=None`, `topic_candidate_id=uuid7()`;
   - bad6: `run_id=R`, `trace_id=" "`.

   Result `== [bad1.id, bad2.id, bad3.id, bad4.id, bad5.id, bad6.id]`.
2. `test_obs_prefixes_cover_contract_workflow_ids`: for each of `"daily-2026-09-17"`, `"manual-1"`, `"produce-1-2"`, `"change-topic-1-2"`, `"regen-topics-1-x"`, `"regen-component-1-x"`, `"regen-article-1-x"`, `"regen-research-1-x"`, `"recheck-1-x"`, `"publish-1-x"`, `"restart-discover-1-x"`, `"restart-produce-1-2-x"`: `workflow_id.startswith(TRACED_WORKFLOW_PREFIXES)`. For `"apply-schedule-v2"`, `"control-x"` and `"catchup-2026-09-17"` it is false.
3. `test_obs_hello_pipeline_calls_are_traced` (`pytest.mark.usefixtures("database_url", "dbos_runtime", "clean_db")`; the module imports `mdcopilot_blog.workflows.hello` at top level so the workflow registers before DBOS launches):
   - `run_id = await make_run()`. Under `SetWorkflowID(f"manual-{run_id}")`, `handle = await DBOS.start_workflow_async(hello_pipeline, str(run_id))`, then `await asyncio.wait_for(handle.get_result(), timeout=60)`.
   - In a `dbos_runtime.sessionmaker()` session: `await find_untraced_llm_calls(session) == []`.
   - `await session.scalar(select(func.count()).select_from(LlmCall).where(LlmCall.run_id == run_id)) >= 1`.
   - Every row for the run has `trace_id == BlogRun.trace_id` of that run.

**Verification.** `OBS_TEST test_obs_trace_coverage.py`. Red: `ImportError: find_untraced_llm_calls`. Green: `3 passed`.

**Acceptance covered.** §10.8 "Every `blog_llm_calls` row has `run_id` and `trace_id`" (OBS test, D9 exact check). INT reuses the function over the full mock daily run.

---

### OBS-8: Settings (`GET /settings`, `PUT /settings`) with `apply_schedule` enqueue and compensation

**Files.**
- Modify `pkg/api/schemas_admin.py` (`SettingsOut`, `SettingsUpdate`).
- Create `pkg/services/admin_config.py` (settings part); modify `pkg/api/routers/settings.py`.
- Modify `tests/api/test_settings_api.py`.
- Create `tests/observability/test_obs_settings_update_api.py`. Extend `OBS_MODELS`.

**Interfaces.**
```python
# schemas_admin.py
class SettingsOut(SettingsView):                  # Phase 1 fields unchanged
    auto_publish_available: Literal[False] = False
    version: int | None
    updated_at: datetime | None
    updated_by: uuid.UUID | None
    effective: EffectiveConfig
    values: SettingsValues
class SettingsUpdate(ApiModel):
    expected_version: int | None                   # required on the wire (null allowed)
    values: SettingsValues
# services/admin_config.py
ROUTE_AGENT_KEYS: frozenset[str]  # {"search","research","ideation","deep_research","writer","fact_check","clinical","editorial","seo"}
APPLY_SCHEDULE_TIMEOUT_SECONDS = 120.0
async def get_settings_out(db: AsyncSession, settings: Settings) -> SettingsOut: ...
async def update_settings(db: AsyncSession, client: WorkflowClientProtocol, *, settings: Settings, principal: Principal,
                          request: SettingsUpdate) -> SettingsOut: ...
```

**Behaviour rules.**
1. `GET /settings` requires `Permission.SETTINGS`. `active` = `blog_settings` row with `is_active`, or `None`. `config = await load_effective_config(db, settings)`. The response fields:
   - `app_version`, `mock_mode`, `agent_enabled`, `scheduler_enabled`, `publishing_enabled`, `gemini_grounding_enabled`, `human_approval_required`, `limits` and `publisher` come from `Settings`, exactly as Phase 1's `build_settings_view` builds them.
   - `schedule = {"dailyRunTime": config.schedule.time, "timezone": config.schedule.timezone}`; `routes = config.routes`.
   - `providers` = Phase 1's four entries plus `"openaiAdmin": mask_secret(settings.openai_admin_api_key)`.
   - `auto_publish_available = False`; `version = active.version`; `updated_at = active.created_at`; `updated_by = active.created_by` (all `None` without an active row).
   - `effective = config`; `values = SettingsValues.model_validate(active.values)`, or `SettingsValues()` without an active row.
2. `PUT /settings` requires `Permission.SETTINGS`. In one transaction on the request session:
   1. `active` = `SELECT … WHERE is_active FOR UPDATE`; `max_version` = `MAX(version)` (0 when there are no rows).
   2. If `request.expected_version != (active.version if active else None)`: 409 `Settings version conflict`, detail `f"expected version {request.expected_version}, active version {active_version}"` (`None` printed as `none`).
   3. Validate `request.values`. Every problem gives 422 `Request validation failed` with detail `[{"type": "value_error", "loc": [...], "msg": ...}]`:
      - every key of `values.routes` in `ROUTE_AGENT_KEYS` (`loc ["body","values","routes",key]`, msg `"unknown agent route key"`);
      - every list non-empty (msg `"route must list at least one provider:model"`);
      - every entry parses with `llm.routes.parse_choice` with provider in `{"openai","google","anthropic"}` (msg `f"invalid route entry {entry!r}"`);
      - every `(name, version)` in `values.prompt_versions` exists in `blog_prompt_versions` (`loc ["body","values","promptVersions",name]`, msg `f"prompt {name} version {version} is not registered"`).
   4. `before = await load_effective_config(db, settings)`.
   5. If `active`: `active.is_active = False`; flush. Insert `BlogSetting(id=uuid7(), version=max_version + 1, values=request.values.model_dump(mode="json"), is_active=True, created_by=principal.user_id)`; flush.
   6. `after = await load_effective_config(db, settings)`. `ConfigError` → rollback, then 422 `Request validation failed` with `loc ["body","values"]`, `msg str(exc)`.
   7. `audit(db, actor_user_id=principal.user_id, action="settings.update", entity_type="blog_settings", entity_id=str(new.id), details={"version": new.version, "previous_version": active.version or None, "changed_keys": sorted(changed)})`. `changed` is the set of top-level field names whose value differs between `SettingsValues.model_validate(old_values).model_dump(mode="json", by_alias=False)` and `request.values.model_dump(mode="json", by_alias=False)`, with `old_values = {}` when there was no active row.
   8. Commit.
   9. If `after.schedule.time != before.schedule.time` or `after.schedule.timezone != before.schedule.timezone`: `await enqueue.enqueue_workflow(client, workflow_name=WORKFLOW_APPLY_SCHEDULE, queue_name=QUEUE_INTERACTIVE, workflow_id=f"apply-schedule-v{new.version}", args=(), timeout_seconds=APPLY_SCHEDULE_TIMEOUT_SECONDS)`.
   10. Compensation when step 9 raises `ProblemError` with status 503: `await db.rollback()`. In a new transaction on the same session: `DELETE FROM blog_settings WHERE id = new.id`; then, if there was a previous active row, `UPDATE blog_settings SET is_active = true WHERE id = previous.id`; then `audit(action="settings.update_reverted", entity_type="blog_settings", entity_id=str(new.id), details={"version": new.version, "restored_version": previous.version or None, "reason": "apply_schedule was not enqueued"})`; commit; re-raise the same `ProblemError`.
   11. Response: `await get_settings_out(db, settings)`.
3. Safety switches cannot be set: `SettingsValues` forbids extra keys, so `{"values": {"mockMode": false}}` gives FastAPI's 422.
4. A re-used workflow id after a compensated save (`apply-schedule-v<n>` enqueued again by the next successful save) is harmless: `apply_schedule` takes no arguments and reads the current settings.

**Tests to write first.**

`tests/api/test_settings_api.py` (modify; keep the 4 Phase 1 tests, updated):
1. `test_settings_view_masks_provider_keys`: also sets `openai_admin_api_key=SecretStr("sk-admin" + "c"*40 + "QRST")`. `providers["openaiAdmin"] == {"configured": True, "preview": "sk-…QRST"}`, and `_leaked` also checks the admin key → `[]`.
2. `test_real_environment_keys_never_appear`: add `openai_admin_api_key` to the checked set.
3. `test_settings_view_shape` (fixture `seeded_db`): `set(body) ==` the Phase 1 12 keys `| {"autoPublishAvailable", "version", "updatedAt", "updatedBy", "effective", "values"}`, with:
   - `autoPublishAvailable is False`, `humanApprovalRequired is True`, `mockMode is True`, `version == 1`;
   - `values["schedule"] == {"time": "07:00", "timezone": "Asia/Kolkata"}`;
   - `schedule == {"dailyRunTime": effective.schedule.time, "timezone": effective.schedule.timezone}` (from `body["effective"]["schedule"]`);
   - `routes == body["effective"]["routes"]`, `limits["maxCostPerRunUsd"] == str(settings.max_cost_per_run_usd)`, `publisher == settings.publisher`;
   - `set(body["providers"]) == {"openai","gemini","anthropic","ncbi","openaiAdmin"}`.
4. `test_settings_requires_admin`: unchanged (publisher gets 403 `missing permission blog.settings`).
5. New `test_settings_effective_values_override_env` (`seeded_db`): deactivate v1 and insert active v2 with `values={"schedule": {"time": "06:30", "timezone": "Asia/Kolkata"}, "routes": {"writer": ["google:gemini-x"]}}`. The body has `schedule["dailyRunTime"] == "06:30"`, `routes["writer"] == ["google:gemini-x"]`, `routes["seo"] == settings.route_values()["seo"]` and `version == 2`.
6. New `test_settings_without_active_row` (plain `db_session`, no seed): 200, `version is None`, `updatedAt is None`, `schedule == {"dailyRunTime": settings.daily_run_time, "timezone": settings.timezone}`.

`tests/observability/test_obs_settings_update_api.py` (`app`, `login_as`, `seeded_db`, `fake_workflow_client` unless stated; `PUT = "/api/blog-agent/settings"`; `v1 = SettingsValues.model_validate(load_seed_file("settings.yaml")).model_dump(mode="json")`):
1. `test_obs_put_settings_schedule_change_enqueues_apply_schedule`: admin PUT `{"expectedVersion": 1, "values": v1 | {"schedule": {"time": "06:30", "timezone": "Asia/Kolkata"}}}` gives:
   - 200, `body["version"] == 2`, `body["effective"]["schedule"]["time"] == "06:30"`, `body["updatedBy"] == <admin id>`;
   - DB: `SELECT version FROM blog_settings WHERE is_active` gives `[2]`, and v1 row `is_active is False`;
   - `fake_workflow_client.enqueued == [EnqueueCall("apply_schedule", "interactive", "apply-schedule-v2", (), 120.0)]`;
   - one `AuditLog` with `action == "settings.update"`, `details == {"version": 2, "previous_version": 1, "changed_keys": ["schedule"]}`.
2. `test_obs_put_settings_without_schedule_change_does_not_enqueue`: `values = v1 | {"noveltyThreshold": 0.8}` gives 200, `version == 2`, `enqueued == []`, `changed_keys == ["novelty_threshold"]`.
3. `test_obs_put_settings_version_conflict`: `expectedVersion: 7` gives 409, title `Settings version conflict`, detail `"expected version 7, active version 1"`; the row count stays 1; `enqueued == []`. `expectedVersion: null` gives 409 with detail `"expected version none, active version 1"`.
4. `test_obs_put_settings_first_version_without_active_row` (plain `db_session`, no seed): `expectedVersion: null`, `values: {}` gives 200, `version == 1`.
5. `test_obs_put_settings_rejects_env_only_switches[key]`, for `mockMode`, `agentEnabled`, `publishingEnabled`, `schedulerEnabled`, `humanApprovalRequired`, `maxCostPerRunUsd`: `values = v1 | {key: False}` (`"1"` for `maxCostPerRunUsd`) gives 422, title `Request validation failed`, no new row.
6. `test_obs_put_settings_route_validation`:
   - `{"routes": {"hello": ["openai:x"]}}` gives 422 with `detail[0]["loc"] == ["body","values","routes","hello"]`.
   - `{"routes": {"writer": []}}` gives 422 with msg `"route must list at least one provider:model"`.
   - `{"routes": {"writer": ["gpt-x"]}}` gives 422 with msg `"invalid route entry 'gpt-x'"`.
   - `{"routes": {"writer": ["mock:x"]}}` gives 422.
   - `{"routes": {"writer": ["anthropic:claude-x", "openai:gpt-y"]}}` gives 200.

   Each 422 leaves exactly one active row, version 1.
7. `test_obs_put_settings_prompt_version_must_exist`: `{"promptVersions": {"writer/draft": 9}}` gives 422, msg `"prompt writer/draft version 9 is not registered"`. After inserting `PromptVersion(name="writer/draft", version=9, agent="writer", sha256="0"*64, body="x", front_matter={})`, the same PUT gives 200.
8. `test_obs_put_settings_round_trips_section50_fields`: `values = v1 |` the following, then 200 and a follow-up `GET /settings` whose `effective` has each value:
   - `{"schedule": {"time": "08:15", "timezone": "Europe/London"}}`
   - `"wordCount": {"min": 900, "max": 1200}`
   - `"research": {"windowDays": 5, "minSourceCount": 6, "minSuccessfulQueries": 6, "broadQueries": 10, "pillarQueries": 4, "deepQueries": 8, "maxVerificationSearches": 3, "feedDisableAfterFailures": 5}`
   - `"noveltyThreshold": 0.8`
   - `"scoreWeights": {"timeliness": 0.3, "novelty": 0.2, "evidence": 0.2, "mdcopilotRelevance": 0.1, "audience": 0.1, "editorial": 0.1}`
   - `"routes": {"writer": ["google:gemini-x"]}`
   - `"publisher": "manual_export"`, `"defaultCategory": "Clinical AI"`, `"siteUrl": "https://example.test"`, `"topicSelectionMode": "manual"`, `"gateOverridePolicy": "never"`

   Checked effective values: `schedule == {"time": "08:15", "timezone": "Europe/London"}`, `wordCount == {"min": 900, "max": 1200}`, `research["windowDays"] == 5`, `research["minSourceCount"] == 6`, `novelty["topicThreshold"] == 0.8`, `scoreWeights["timeliness"] == 0.3`, `routes["writer"] == ["google:gemini-x"]`, `publisher == "manual_export"`, `defaultCategory == "Clinical AI"`, `siteUrl == "https://example.test"`, `topicSelectionMode == "manual"`, `gateOverridePolicy == "never"`. Exactly one enqueue (`apply-schedule-v2`).
9. `test_obs_put_settings_compensates_when_enqueue_fails` (`committing_app`, `committing_client`, `committing_login_as`, `committed_seed`, `fake_workflow_client`, `sessionmaker_committing`): `fake_workflow_client.enqueue_error = RuntimeError("dbos down")`; admin PUT with the schedule change of test 1. Assert:
   - 503, title `Workflow service unavailable`;
   - in a fresh `sessionmaker_committing()` session: active versions `[1]`, no row with version 2;
   - audit actions ordered by `created_at` `== ["settings.update", "settings.update_reverted"]`, the second with `details == {"version": 2, "restored_version": 1, "reason": "apply_schedule was not enqueued"}`;
   - a follow-up GET gives `version == 1`.
10. `test_obs_put_settings_rbac`: publisher PUT gives 403 with detail `missing permission blog.settings`. Anonymous PUT gives 401. Missing CSRF header gives 403 with title `CSRF token missing or invalid`.

`OBS_MODELS += ["SettingsOut", "SettingsUpdate"]`.

**Implementation notes.**
- `enqueue_workflow` is FOUND's. Call it as `enqueue.enqueue_workflow(...)` (`from mdcopilot_blog.services import enqueue`) so INT can re-point it.
- Deactivate before insert, because `uq_blog_settings_active` is a partial unique index on `is_active`.
- The API commits before enqueueing (§5.5 rule 7, §4.0).

**Verification.**
- `OBS_TEST test_obs_settings_update_api.py`. Red: 405 `Method Not Allowed` on PUT. Green: `15 passed` (9 plain tests plus 6 cases in test 5).
- `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_obs_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/api/test_settings_api.py`. Red: key-set assertion. Green: `6 passed`.
- `tests/api/test_rbac_routes.py` green. `test_obs_openapi.py` `16 passed`.

**Acceptance covered.** §10.5 "Settings: all §50 fields, routes, … schedule time/timezone (saving enqueues `apply_schedule`), masked keys, auto-publish locked OFF" (API + enqueue part). §8.1 compensation test for `PUT /settings`. §4.0 audit (`settings.update`).

---

### OBS-9: Brand profile (`GET /settings/brand`, `PUT /settings/brand`)

**Files.** Modify `schemas_admin.py` (`BrandProfileOut`, `BrandProfileUpdate`), `services/admin_config.py` and `routers/settings.py`. Create `tests/observability/test_obs_brand_api.py`. Extend `OBS_MODELS`.

**Interfaces.**
```python
class BrandProfileOut(ApiModel): version: int; values: BrandProfileValues; created_at: datetime; created_by: uuid.UUID | None
class BrandProfileUpdate(ApiModel): expected_version: int; values: BrandProfileValues
async def get_brand(db: AsyncSession) -> BrandProfileOut: ...
async def update_brand(db: AsyncSession, *, principal: Principal, request: BrandProfileUpdate) -> BrandProfileOut: ...
```

**Behaviour rules.**
1. `GET /settings/brand` requires `Permission.SETTINGS`. It returns the active row, with `values = await load_brand_profile(db)`. With no active row (`LookupError`): 404 `Brand profile not found` (gap 3).
2. `PUT /settings/brand` requires `Permission.SETTINGS`:
   1. Lock the active row `FOR UPDATE`.
   2. If there is no active row, or `expected_version != active.version`: 409 `Brand profile version conflict`, detail `f"expected version {expected}, active version {active_version or 'none'}"`.
   3. Deactivate, flush, then insert `BrandProfile(version=max+1, profile=values.model_dump(mode="json"), is_active=True, created_by=principal.user_id)`.
   4. `audit(action="brand.update", entity_type="blog_brand_profile", entity_id=str(new.id), details={"version", "previous_version", "changed_keys"})`, with `changed_keys` computed as in OBS-8.
   5. Commit. Response is the new row.
3. A blank `aiDisclosure` is rejected by `BrandProfileValues` (FastAPI 422 `Request validation failed`). No enqueue.

**Tests to write first** (`tests/observability/test_obs_brand_api.py`, `app` + `login_as` + `seeded_db`; `b1 = BrandProfileValues.model_validate(load_seed_file("brand_profile.yaml")).model_dump(mode="json")`):
1. `test_obs_get_brand_returns_active_version`: admin gets 200, `body["version"] == 1`, `body["values"] == b1`, `body["createdBy"] is None`.
2. `test_obs_put_brand_creates_version_and_audits`: PUT `{"expectedVersion": 1, "values": b1 | {"tone": ["direct", "evidence-driven"]}}` gives 200, `version == 2`, and `values["tone"] == ["direct", "evidence-driven"]`. `await load_brand_profile(db)` then has `tone == ["direct", "evidence-driven"]`. Exactly one active row. Audit `brand.update` has details `{"version": 2, "previous_version": 1, "changed_keys": ["tone"]}`.
3. `test_obs_put_brand_version_conflict`: `expectedVersion: 3` gives 409, title `Brand profile version conflict`, detail `"expected version 3, active version 1"`, and no new row.
4. `test_obs_put_brand_blank_disclosure_422`: `values = b1 | {"aiDisclosure": "   "}` gives 422, title `Request validation failed`, and the active version stays 1.
5. `test_obs_get_brand_404_without_active_row` (plain `db_session`, admin via `login_as`): 404, title `Brand profile not found`.
6. `test_obs_brand_rbac`: publisher GET and PUT give 403 with detail `missing permission blog.settings`. Anonymous gives 401 on both.
7. `test_obs_brand_cta_and_website_round_trip`: PUT with `cta: "Book a demo at example.test"` and `website: "https://example.test"` gives 200. GET returns both values (§50 "default category and CTA; website").

`OBS_MODELS += ["BrandProfileOut", "BrandProfileUpdate"]`.

**Verification.** `OBS_TEST test_obs_brand_api.py`. Red: 404 `Not Found` on the routes. Green: `7 passed`. `test_obs_openapi.py`: `18 passed`.

**Acceptance covered.** §10.5 Settings (brand profile incl. prohibited language and disclosure; CTA; website). §4.0 audit (`brand.update`).

---

### OBS-10: Pillars (`GET /pillars`, `PUT /pillars`)

**Files.** Modify `schemas_admin.py` (`PillarOut`, `PillarIn`, `PillarsUpdate`), `services/admin_config.py` and `routers/settings.py`. Create `tests/observability/test_obs_pillars_api.py`. Extend `OBS_MODELS`.

**Interfaces.**
```python
class PillarIn(ApiModel):
    key: PillarKey; name: str = Field(min_length=1, max_length=200); description: str; topics: list[str]
    weekdays: list[int]; is_active: bool; sort_order: int
class PillarOut(PillarIn): id: uuid.UUID
class PillarsUpdate(ApiModel): items: list[PillarIn]
async def list_pillars(db: AsyncSession) -> list[PillarOut]: ...
async def update_pillars(db: AsyncSession, *, principal: Principal, request: PillarsUpdate) -> list[PillarOut]: ...
```

**Behaviour rules.**
1. `GET /pillars` requires `Permission.VIEW`. Order `sort_order ASC, key ASC`.
2. `PUT /pillars` requires `Permission.SETTINGS`. Validation happens before any write. Each failure gives 422 `Pillar rotation invalid` with a string detail:
   - The item keys must be exactly the six `PillarKey` values, each once. Detail `"items must list each pillar key exactly once: A, B, C, D, E, NARRATIVE"`.
   - Every weekday must be an integer 0..6. Detail `f"pillar {key}: weekday {d} is outside 0..6"`.
   - No duplicate weekday within one pillar. Detail `f"pillar {key}: weekday {d} is listed twice"`.
   - No weekday claimed by two items with `is_active = true`. Detail `f"weekday {d} is claimed by pillars {k1} and {k2}"`, with keys in `PillarKey` order. Inactive items are ignored.
3. Write:
   1. Lock all `blog_content_pillars` rows `FOR UPDATE` (ordered by key).
   2. For each item, update the row with that key (name, description, topics, weekdays sorted ascending, is_active, sort_order), or insert it if missing.
   3. `changed_keys` = keys whose stored values differ. `audit(action="pillars.update", entity_type="blog_content_pillars", entity_id=None, details={"changed_keys": changed_keys})`.
   4. Commit, then return `list_pillars`.
4. An unknown key such as `"F"` is rejected by `PillarKey` before the service runs: 422 `Request validation failed` (gap 4).

**Tests to write first** (`tests/observability/test_obs_pillars_api.py`, `app` + `login_as` + `seeded_db`; `items()` returns the six seeded pillars as `PillarIn` JSON dicts):
1. `test_obs_get_pillars_viewer`: viewer gets 200. `[p["key"] for p in body] == ["A","B","C","D","E","NARRATIVE"]`, `body[5]["weekdays"] == [5, 6]` and `set(body[0]) == set(SHAPES["PillarOut"]["props"])`.
2. `test_obs_put_pillars_swaps_rotation`: admin PUT with A `weekdays [1]` and B `weekdays [0]` gives 200. `body[0]["weekdays"] == [1]`, `body[1]["weekdays"] == [0]`. `await pillar_for_date(db, date(2026, 9, 7))` (a Monday) returns `PillarKey.B`. Audit `pillars.update` has `details == {"changed_keys": ["A", "B"]}`.
3. `test_obs_put_pillars_rejects_missing_key`: 5 items give 422, title `Pillar rotation invalid`, detail `"items must list each pillar key exactly once: A, B, C, D, E, NARRATIVE"`. A duplicated A (7 items) gives the same.
4. `test_obs_put_pillars_rejects_bad_weekday`: A `weekdays [7]` gives 422 with detail `"pillar A: weekday 7 is outside 0..6"`. A `weekdays [0, 0]` gives 422 with detail `"pillar A: weekday 0 is listed twice"`.
5. `test_obs_put_pillars_rejects_conflict_between_active_pillars`: B `weekdays [0, 1]` with A still `[0]` gives 422, detail `"weekday 0 is claimed by pillars A and B"`. The DB is unchanged (B weekdays still `[1]`).
6. `test_obs_put_pillars_ignores_inactive_conflict`: B `weekdays [0, 1]` and `isActive false` gives 200.
7. `test_obs_put_pillars_unknown_key_is_schema_422`: one item with key `"F"` gives 422, title `Request validation failed`.
8. `test_obs_pillars_rbac`: anonymous GET gives 401. Publisher PUT gives 403 with detail `missing permission blog.settings`. Anonymous PUT gives 401.

`OBS_MODELS += ["PillarOut", "PillarIn", "PillarsUpdate"]`.

**Verification.** `OBS_TEST test_obs_pillars_api.py`. Red: 404 on the routes. Green: `8 passed`. `test_obs_openapi.py`: `21 passed`.

**Acceptance covered.** §10.5 Settings ("preferred pillars and rotation"). §4.0 audit (`pillars.update`).

---

### OBS-11: Price overrides (`GET /settings/price-overrides`, `POST /settings/price-overrides`)

**Files.** Modify `schemas_admin.py` (`PriceOverrideOut`, `PriceOverrideCreate`), `services/admin_config.py` and `routers/settings.py`. Create `tests/observability/test_obs_price_overrides_api.py`. Extend `OBS_MODELS`.

**Interfaces.**
```python
Price = Annotated[Decimal | None, Field(ge=0, max_digits=12, decimal_places=6)]
class PriceOverrideCreate(ApiModel):
    provider: Literal["openai", "google", "anthropic"]; sku: str = Field(min_length=1, max_length=128)
    input_per_mtok: Price = None; output_per_mtok: Price = None; cache_read_per_mtok: Price = None; per_1k_calls: Price = None
    effective_from: datetime; note: str | None = None
class PriceOverrideOut(ApiModel):
    id: uuid.UUID; provider: str; sku: str; input_per_mtok: Decimal | None; output_per_mtok: Decimal | None
    cache_read_per_mtok: Decimal | None; per_1k_calls: Decimal | None; effective_from: datetime; price_version: str
    note: str | None; created_by: uuid.UUID | None; created_at: datetime
async def list_price_overrides(db: AsyncSession) -> list[PriceOverrideOut]: ...
async def create_price_override(db: AsyncSession, *, principal: Principal, request: PriceOverrideCreate) -> PriceOverrideOut: ...
```

**Behaviour rules.**
1. Both routes require `Permission.SETTINGS`. `GET` is ordered `effective_from DESC, created_at DESC, id DESC`.
2. `PriceOverrideCreate` model validators (FastAPI 422 `Request validation failed`):
   - `sku.strip()` is non-empty and is stored stripped.
   - `effective_from.tzinfo` is not `None` (msg `"must include a timezone offset"`).
   - At least one of `input_per_mtok`, `output_per_mtok`, `per_1k_calls` is not `None` (msg `"set input_per_mtok, output_per_mtok or per_1k_calls"`), matching `ck_blog_price_overrides_has_price`.
3. `POST`:
   1. If a row with the same `(provider, sku, effective_from)` exists: 409 `Price override exists`, detail `f"{provider} {sku} already has a price from {effective_from.isoformat()}"`.
   2. `row_id = uuid7()`, `price_version = f"ovr:{row_id.hex[-12:]}"`. Insert with `created_by=principal.user_id`.
   3. `audit(action="price_override.create", entity_type="blog_price_override", entity_id=str(row_id), details={"provider", "sku", "effective_from", "price_version"})`.
   4. Commit, then 201 `PriceOverrideOut`.
   5. An `IntegrityError` on `uq_blog_price_overrides_provider_sku_effective_from` (race): rollback, then the same 409.
4. Wire names follow `to_camel` (verified with pydantic 2.13.5): `inputPerMtok`, `outputPerMtok`, `cacheReadPerMtok`, `per1KCalls`.

**Tests to write first** (`tests/observability/test_obs_price_overrides_api.py`, `app` + `login_as` + `db_session`; `BODY = {"provider": "openai", "sku": "web_search_call", "per1KCalls": "10", "effectiveFrom": "2026-09-01T00:00:00+00:00", "note": "search fee"}`):
1. `test_obs_create_price_override`: admin POST gives 201:
   - `body["priceVersion"] == "ovr:" + uuid.UUID(body["id"]).hex[-12:]`, `len(body["priceVersion"]) == 16`, `"web_search_call" not in body["priceVersion"]`;
   - `Decimal(body["per1KCalls"]) == Decimal("10")`, `body["inputPerMtok"] is None`, `body["createdBy"] == <admin id>`;
   - audit `price_override.create` has `details["price_version"] == body["priceVersion"]`.
2. `test_obs_list_price_overrides_newest_first`: create `effectiveFrom` `2026-08-01T00:00:00+00:00` (sku `gpt-a`, `inputPerMtok "1.5"`), then `2026-09-01…` (sku `gpt-a`, `inputPerMtok "2"`). GET gives `[r["effectiveFrom"] for r in body]` equal to `["2026-09-01T00:00:00Z", "2026-08-01T00:00:00Z"]`, compared via `datetime.fromisoformat`.
3. `test_obs_create_price_override_duplicate_409`: the same BODY twice. The second is 409 with title `Price override exists`, and there is exactly 1 row.
4. `test_obs_create_price_override_validation[body_patch]`, each giving 422 `Request validation failed` and 0 rows:
   - `{"per1KCalls": None, "cacheReadPerMtok": "1"}`;
   - `{"per1KCalls": "-1"}`;
   - `{"per1KCalls": "0.1234567"}`;
   - `{"per1KCalls": "12345678"}` (8 integer digits > `max_digits - decimal_places`);
   - `{"effectiveFrom": "2026-09-01T00:00:00"}`;
   - `{"provider": "mock"}`;
   - `{"sku": "   "}`;
   - `{"sku": "x" * 129}`.
5. `test_obs_price_overrides_rbac`: publisher GET and POST give 403 with detail `missing permission blog.settings`. Anonymous gives 401 on both.

`OBS_MODELS += ["PriceOverrideOut", "PriceOverrideCreate"]`.

**Verification.** `OBS_TEST test_obs_price_overrides_api.py`. Red: 404. Green: `12 passed` (5 functions; test 4 has 8 cases). `test_obs_openapi.py`: `23 passed`.

**Acceptance covered.** §10.8 "price-override UI" (API side). §4.9 `price_version` format. §4.0 audit (`price_override.create`).

---

### OBS-12: Content Calendar (`GET /calendar`, `PATCH /calendar/slots/{slot_date}`)

**Files.** Modify `schemas_admin.py` (`CalendarEntryOut`, `CalendarDayOut`, `CalendarMonthOut`, `CalendarSlotUpdate`). Create `pkg/services/calendar.py`; modify `pkg/api/routers/calendar.py`. Create `tests/observability/test_obs_calendar.py` and `tests/observability/test_obs_calendar_api.py`. Extend `OBS_MODELS`.

**Interfaces.**
```python
class CalendarEntryOut(ApiModel):
    kind: Literal["published", "scheduled", "exported", "draft", "research", "planned"]
    article_id: uuid.UUID | None; run_id: uuid.UUID | None; research_run_id: uuid.UUID | None
    title: str; status: str; at: datetime | None; pillar: PillarKey | None
class CalendarDayOut(ApiModel):
    date: dt.date; planned_pillar: PillarKey | None; slot_id: uuid.UUID | None; slot_status: SlotStatus | None
    is_override: bool; note: str | None; entries: list[CalendarEntryOut]
class CalendarMonthOut(ApiModel): month: str; timezone: str; days: list[CalendarDayOut]
class CalendarSlotUpdate(ApiModel):
    pillar: PillarKey | None = None; status: SlotStatus | None = None; note: str | None = Field(None, max_length=2000)
DRAFT_STATUSES: frozenset[str]  # DRAFTING, FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW, SEO, READY_FOR_REVIEW, QUALITY_GATE_FAILED, APPROVED
async def get_calendar_month(db: AsyncSession, settings: Settings, *, month: str) -> CalendarMonthOut: ...
async def update_calendar_slot(db: AsyncSession, settings: Settings, *, principal: Principal, slot_date: dt.date,
                               request: CalendarSlotUpdate) -> CalendarDayOut: ...
```

**Behaviour rules.**
1. `GET /calendar` requires `Permission.VIEW`. Query `month: str = Query(pattern=r"^[1-9]\d{3}-(0[1-9]|1[0-2])$")`; missing or non-matching gives 422 `Request validation failed`.
   - `tz = metrics.reporting_timezone`.
   - The month's days run from the 1st to the last day (the last day is computed as next month's 1st minus 1 day; never `import calendar` inside `services/calendar.py`).
   - UTC bounds `[local midnight of the 1st, local midnight of next month's 1st)`.
2. Per day:
   - `planned_pillar = await pillar_for_date(db, day)`.
   - The `blog_calendar_slots` row for the date gives `slot_id`, `slot_status`, `note`.
   - `is_override = slot row exists`.
3. Entries:
   - `published`: articles with `status = 'PUBLISHED'`; day = local date of `published_at`; `at = published_at`.
   - `scheduled`: `status = 'SCHEDULED'`; day and `at` from `scheduled_for`.
   - `exported`: `status = 'EXPORTED'`; `at` = `updated_at` of that article's newest `blog_publications` row with `status = 'EXPORTED'` (fallback `blog_articles.updated_at`); day = its local date.
   - `draft`: status in `DRAFT_STATUSES`; day = `run_date`; `at = None`.
   - For all article kinds: `title = article.title or article.slug or "Untitled article"`, `status = article.status`, `pillar = article.pillar_key`, plus `article_id` and `run_id`. Other statuses (PUBLISHING, PUBLISH_FAILED, REJECTED, FAILED, SUPERSEDED) give no entry.
   - `research`: `blog_research_runs` with `kind = 'broad'`; day = local date of `started_at`; `at = started_at`; `title = "Research: " + ", ".join(themes_covered[:3])`, or `"Research run"` when there are no themes; `status = research status`; `pillar = pillar_key`; `research_run_id` and `run_id`.
   - `planned`: one entry when `planned_pillar is not None`, with `title` = that pillar's `name`, `status = "planned"`, `pillar = planned_pillar`, and all ids and `at` `None`.
   - Order within a day: kind order published, scheduled, exported, draft, research, planned; then `at` ascending (nulls last); then entity id ascending.
4. `PATCH /calendar/slots/{slot_date}` requires `Permission.SCHEDULE`; `slot_date: dt.date` path (a bad date gives 422).
   1. If `pillar` is in `model_fields_set` and not `None` and no active pillar has that key: 422 `Request validation failed`, detail `[{"type": "value_error", "loc": ["body", "pillar"], "msg": f"pillar {key} is not active"}]`.
   2. `slot = SELECT … WHERE slot_date = :d FOR UPDATE`.
   3. No slot: `pillar_key = request.pillar or await pillar_for_date(db, slot_date)`. If that is `None`: 422 `Pillar required`, detail `f"no pillar is planned for {slot_date.isoformat()}; send a pillar"`. Otherwise `insert(CalendarSlot).values(id=uuid7(), slot_date=…, pillar_key=…, status=(request.status or SlotStatus.PLANNED).value, note=request.note, created_by=principal.user_id).on_conflict_do_nothing(index_elements=["slot_date"]).returning(CalendarSlot.id)`. If nothing is returned (race), re-select `FOR UPDATE` and continue as an update.
   4. Existing slot: set each field present in `model_fields_set`. `pillar: null` is ignored because the column is NOT NULL; `note: null` clears the note.
   5. `audit(action="calendar.slot_update", entity_type="blog_calendar_slot", entity_id=str(slot_id), details={"date": iso, "created": bool, "pillar": pillar_key, "status": status, "note_changed": "note" in model_fields_set})`.
   6. Commit. Response is the `CalendarDayOut` for that date, built like the GET.

**Tests to write first.**

`tests/observability/test_obs_calendar.py` (service; `db_session` with `seed_defaults`; timezone `Asia/Kolkata`):
1. `test_obs_calendar_month_days_and_rotation`: `get_calendar_month(month="2026-09")` gives:
   - `month == "2026-09"`, `timezone == "Asia/Kolkata"`, `len(days) == 30`, `days[0].date == date(2026, 9, 1)`;
   - `days[0].planned_pillar == PillarKey.B`, `days[4].planned_pillar == PillarKey.NARRATIVE`, `days[6].planned_pillar == PillarKey.A`;
   - `days[0].entries == [CalendarEntryOut(kind="planned", article_id=None, run_id=None, research_run_id=None, title="Cognitive Architecture & Physician Reasoning", status="planned", at=None, pillar=PillarKey.B)]`;
   - `days[0].is_override is False`, `slot_id is None`.

   `get_calendar_month(month="2026-02")` gives `len(days) == 28`.
2. `test_obs_calendar_slots_override_rotation`: insert `CalendarSlot(slot_date=2026-09-15, pillar_key="E", status="planned", note="launch week")` and `CalendarSlot(slot_date=2026-09-16, pillar_key="C", status="cancelled")`.
   - Day 15: `planned_pillar == PillarKey.E`, `slot_status == SlotStatus.PLANNED`, `is_override is True`, `note == "launch week"`, planned entry title `"Governance & Clinical Autonomy"`.
   - Day 16: `planned_pillar is None`, `slot_status == SlotStatus.CANCELLED`, `is_override is True`, `entries == []`.
3. `test_obs_calendar_article_entries[kind]`. Each case builds one `make_article_graph` and applies SQL updates:
   - `published`: `status=PUBLISHED, approved=True`; `UPDATE … SET published_at='2026-09-10T20:00:00Z', title='Published piece'`. Entry on day 11 (IST 01:30): `kind == "published"`, `at == datetime(2026,9,10,20,0,tzinfo=UTC)`, `title == "Published piece"`, `status == "PUBLISHED"`, `article_id == g.article_id`, `run_id == g.run_id`. Day 10 has no `published` entry.
   - `scheduled`: `status=SCHEDULED, approved=True`; `SET scheduled_for='2026-09-20T03:00:00Z'`. Entry on day 20, `at == 2026-09-20T03:00Z`.
   - `exported`: `status=EXPORTED, approved=True, publication=PublisherKey.MANUAL_EXPORT`; `UPDATE blog_publications SET status='EXPORTED', updated_at='2026-09-12T19:00:00Z'`. Entry on day 13 (IST 00:30), `at == 2026-09-12T19:00Z`.
   - `draft`: `status=READY_FOR_REVIEW`; `UPDATE blog_articles SET run_date='2026-09-09', title=NULL, slug=NULL`. Entry on day 9 with `at is None`, `title == "Untitled article"`, `status == "READY_FOR_REVIEW"`.
   - `rejected`: `status=REJECTED`; `run_date='2026-09-09'`. No article entry on any day.

   In every case the article's entry appears exactly once in the whole month.
4. `test_obs_calendar_research_entry[kind]`, parametrized over `broad` and `deep`: `ids = await make_research_graph(db, kind=kind)`; `UPDATE blog_research_runs SET started_at='2026-09-03T20:00:00Z', themes_covered='["ai_agents","prior_auth","burnout","extra"]'`.
   - `broad`: day 4 has one `research` entry with `title == "Research: ai_agents, prior_auth, burnout"`, `research_run_id == ids.research_run_id`, `run_id == ids.run_id`, `at == 2026-09-03T20:00Z`.
   - `deep`: no day of the month has a `research` entry.
5. `test_obs_calendar_entry_order`: a draft article (graph, `run_date='2026-09-09'`) plus a broad research run (`add_research_run` on the graph's run, started `2026-09-09T02:00:00Z`) give kinds `["draft", "research", "planned"]` on day 9.
6. `test_obs_update_slot_existing` (service; `principal` built from `make_user(Role.REVIEWER)` with `permissions_for(Role.REVIEWER)`): an existing slot 2026-09-15, pillar E, planned, note `"a"`.
   - `update_calendar_slot(slot_date=date(2026,9,15), request=CalendarSlotUpdate.model_validate({"note": None}))` gives `note is None` and `planned_pillar == PillarKey.E`.
   - `CalendarSlotUpdate.model_validate({"pillar": None})` keeps pillar E.

`tests/observability/test_obs_calendar_api.py` (`app`, `login_as`, `seeded_db`):
1. `test_obs_get_calendar_viewer`: `GET /api/blog-agent/calendar?month=2026-09` gives 200, `len(body["days"]) == 30`, `set(body["days"][0]) == set(SHAPES["CalendarDayOut"]["props"])`. Anonymous gives 401.
2. `test_obs_get_calendar_bad_month[month]`: missing, `2026-9`, `2026-13`, `0000-01` each give 422, title `Request validation failed`.
3. `test_obs_patch_slot_sets_pillar`: reviewer `PATCH /api/blog-agent/calendar/slots/2026-09-07` `{"pillar": "C", "note": "swap"}` gives 200, `body["date"] == "2026-09-07"`, `plannedPillar == "C"`, `slotStatus == "planned"`, `isOverride is True`, `note == "swap"`. DB has one slot. Audit `calendar.slot_update` has details `{"date": "2026-09-07", "created": True, "pillar": "C", "status": "planned", "note_changed": True}`.
4. `test_obs_patch_slot_cancel_weekday_with_active_pillar`: reviewer PATCH `2026-09-08` (Tuesday) `{"status": "cancelled"}` with no slot gives 200, `plannedPillar is None`, `slotStatus == "cancelled"`, `isOverride is True`. The DB slot has `pillar_key == "B"`.
5. `test_obs_patch_slot_cancel_weekday_without_active_pillar`: `UPDATE blog_content_pillars SET is_active=false WHERE key='NARRATIVE'`, then PATCH `2026-09-12` (Saturday) `{"status": "cancelled"}` gives 422, title `Pillar required`, detail `"no pillar is planned for 2026-09-12; send a pillar"`, and no slot row.
6. `test_obs_patch_slot_inactive_pillar_422`: after deactivating NARRATIVE, PATCH `2026-09-07` `{"pillar": "NARRATIVE"}` gives 422, title `Request validation failed`, `detail[0]["msg"] == "pillar NARRATIVE is not active"`. `{"pillar": "F"}` gives 422 `Request validation failed`.
7. `test_obs_patch_slot_updates_existing`: PATCH `2026-09-07` `{"pillar": "C"}` then `{"status": "cancelled"}` gives, on the second call, 200 with `slotStatus == "cancelled"` and the DB pillar still `"C"`. There is exactly one slot row, and the second audit has `created is False`.
8. `test_obs_patch_slot_validation`: path `2026-02-30` gives 422. `{"note": "x" * 2001}` gives 422.
9. `test_obs_patch_slot_rbac`: editor PATCH gives 403, detail `missing permission blog.schedule`. Anonymous gives 401.

`OBS_MODELS += ["CalendarEntryOut", "CalendarDayOut", "CalendarMonthOut", "CalendarSlotUpdate"]`.

**Verification.** `OBS_TEST test_obs_calendar.py`. Red: `ModuleNotFoundError: mdcopilot_blog.services.calendar`. Green: `11 passed` (4 plain tests, plus 5 cases in test 3 and 2 in test 4). `OBS_TEST test_obs_calendar_api.py`. Red: 404. Green: `12 passed` (test 2 has 4 cases). `test_obs_openapi.py`: `27 passed`.

**Acceptance covered.** §10.5 "Content Calendar (FullCalendar MIT) with `blog_calendar_slots` — OBS (API); OBS API tests", including the §4.8 required test for `{status: "cancelled"}` on a slot-less weekday with and without an active pillar. §4.0 audit (`calendar.slot_update`).

---

### OBS-13: `docs/blog-agent/OBSERVABILITY.md`

**Files.** Create `docs/blog-agent/OBSERVABILITY.md`.

**Content rules.** Sections, in order, with these exact H2 headings:
1. `## 1. What is recorded`: `blog_runs`, `blog_run_attempts`, `blog_agent_runs`, `blog_llm_calls` and the columns used by the metrics. States that one run is one trace (`blog_runs.trace_id`).
2. `## 2. Traces`: the span names and attributes from OBS-1 rules 6–8. Traces are off while `OTEL_EXPORTER_OTLP_ENDPOINT` is blank. No prompt text, output or secrets appear in spans.
3. `## 3. Phoenix (optional profile)`, as owner steps:
   - `docker compose --profile observability up -d phoenix`;
   - set `OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:6006` in `.env` (the owner edits it);
   - `docker compose up -d api worker`;
   - open `http://127.0.0.1:8320`.

   It notes the ELv2 licence, the `phoenix` schema in our Postgres, that Phoenix is not part of any acceptance check, and that the collector path `/v1/traces` on port 6006 is Phoenix's documented OTLP/HTTP endpoint and was not exercised by OBS tests.
4. `## 4. Cost SQL`: four read-only queries against schema `app`:
   - today's cost in `Asia/Kolkata`;
   - cost per article for the last 30 days;
   - cost per `provider_served:model_served`;
   - the check that `GET /metrics/costs` `totalUsd` equals `SELECT COALESCE(SUM(cost_usd),0) FROM app.blog_llm_calls WHERE created_at >= :from AND created_at < :to`.

   Each query uses `timezone('Asia/Kolkata', created_at)`, as in OBS-4.
5. `## 5. Metrics definitions`: the rules of OBS-4 (grouping keys, `none` keys, no zero-fill), OBS-5 (Rule C, workflow rows) and OBS-6 (every dashboard field, window bounds, Rule B, Rule C).
6. `## 6. Cost reconciliation (optional)`: flag and key, the reconciled UTC day, organization-wide totals, disabled in mock mode, never sent while off.
7. `## 7. Trace coverage check`: D9 exceptions and `find_untraced_llm_calls`.

**Tests.** None (documentation). TDD does not apply; the verification below checks structure.

**Verification** (host `grep` only; no interpreter):
```bash
grep -c '^## ' docs/blog-agent/OBSERVABILITY.md          # expect 7
grep -n 'OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:6006' docs/blog-agent/OBSERVABILITY.md   # expect 1 line
grep -c "timezone('Asia/Kolkata', created_at)" docs/blog-agent/OBSERVABILITY.md             # expect >= 4
```

**Acceptance covered.** §10.8 "Phoenix optional, not part of acceptance — doc only"; `OBSERVABILITY.md` "Phoenix profile how-to, cost SQL" (§2.2).

---

### OBS-final: track verification

**Order.**
1. Import gate: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_obs_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py`. Expected: all passed. A failure in a non-OBS file becomes a `Request:` line.
2. Whole track: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_obs_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/observability tests/api/test_settings_api.py tests/api/test_rbac_routes.py`. Expected: 0 failed, 0 errors. The OBS files contribute 14 + 10 + 7 + 27 + 19 + 4 + 4 + 32 + 3 + 15 + 7 + 8 + 12 + 11 + 12 + 6 = 191 tests: tracing, reconciliation, agent runs, openapi, costs, costs API, latency, dashboard, trace coverage, settings update, brand, pillars, price overrides, calendar service, calendar API, settings API. The RBAC file adds its Phase 1 count.
3. Lint and types: the header lint command. Expected `All checks passed!`, `N files already formatted`, `Success: no issues found in 13 source files`.
4. `cmp backend/tests/api_shapes.json frontend/src/test/api-shapes.json` (read-only, FOUND's files). Expected: no output.
5. `docker ps -a --filter name=p2p-obs --format '{{.Names}}'`. Expected: no output (every throwaway container removed).

**Acceptance mapping.**

| Contract row | Where proven |
|---|---|
| §10.8 OpenTelemetry `gen_ai.*` spans, one trace per run (OBS `tracing.py`) | OBS-1 tests 3–14 |
| §10.8 Cost views today/week/month/article/research run/topic/agent/model | OBS-4 tests 1–12; OBS-6 test 9 |
| §10.8 Price-override UI (API) | OBS-11 |
| §10.8 Optional OpenAI Costs reconciliation off, `disabled` without key/flag, no network | OBS-2 tests 1–3 |
| §10.8 Dashboard metrics (spec §26) and measured P50/P90 per stage | OBS-6; OBS-5 |
| §10.8 Dashboard totals equal the SQL sum of `blog_llm_calls` over the same window | OBS-6 test 9; OBS-4 test 12 |
| §10.8 Every `blog_llm_calls` row has `run_id` and `trace_id` (D9 exact check) | OBS-7 (INT runs it over the full mock run) |
| §10.8 Per-article cost on the article page (API) | OBS-4 tests 6, 7, 10 (`groupBy=article`, `articleId`) |
| §10.8 Phoenix optional, not part of acceptance | OBS-1 test 11; OBS-13 |
| §10.5 Content Calendar with `blog_calendar_slots` (OBS API) | OBS-12 |
| §10.5 Settings: §50 fields, routes, brand, pillars, schedule (enqueue `apply_schedule`), masked keys, auto-publish locked OFF | OBS-8 tests 1, 3, 8 and settings API tests 1, 3; OBS-9; OBS-10 |
| §10.5 Agent Runs timeline (OBS `/agent-runs`) | OBS-3 |
| §10.5 Viewer sees no mutating controls; the API rejects the calls (403 tests) | RBAC tests in OBS-3, 8, 9, 10, 11, 12 |
| §8.1 commit-then-enqueue compensation test for `PUT /settings` | OBS-8 test 9 |
| §8.3 OpenAPI component props/nullable equal `api_shapes.json` | `test_obs_openapi.py` (27 models) |
| §4.0 audit actions `settings.update`, `brand.update`, `pillars.update`, `price_override.create`, `calendar.slot_update` | OBS-8 test 1, OBS-9 test 2, OBS-10 test 2, OBS-11 test 1, OBS-12 API test 3 |
| **Rule A**: human-action attempts never change run status; OBS run totals include all attempts | OBS-4 test 10 (`runId` total includes the `regenerate_component` attempt's call) |
| **Rule B**: `produce_article`/`change_topic`/`regenerate_topics` may re-open a terminal run | OBS-6 test 4 (`today.run_status` echoes the current status, for example `PRODUCING`) |
| **Rule C**: generation-time metrics count only `discover_topics`/`produce_article` (plus `change_topic` in the tracker) | OBS-5 test 1; OBS-6 tests 7, 8, 13 |

**Wire conventions for UI and INT** (recorded in `OBSERVABILITY.md` §5 and sent to the controller as a note in `requests/obs.md`):
- Cost rows have no zero-fill.
- Null group keys are `"none"`, with the labels `No agent`, `No article`, `No topic` and `No research run`.
- Week labels are `YYYY-Www`; time keys are `YYYY-MM-DD` bucket starts.
- `/metrics/costs` is half-open `[from, to)`. Dashboard windows end inclusive at now. A naive `from` or `to` gives 422.
- `/metrics/latency` appends workflow rows `discover_topics` and `produce_article`.
- The price-override wire name is `per1KCalls`.
- `SettingsOut.limits` and `publisher` stay environment values; `effective` holds the stored overrides.
- `SettingsUpdate.expectedVersion` must be sent (null only when no version exists).
- INT calls `configure_tracing(settings, service_name="api" | "worker")`, wraps steps in `step_span`, calls `reconcile_openai_costs(sessionmaker, settings=…, now=…)` in `maintenance.reconcile_costs`, and asserts `find_untraced_llm_calls(db) == []` after the mock daily run.
