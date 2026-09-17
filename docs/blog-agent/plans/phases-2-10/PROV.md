# Track PROV: providers, pricing, cost cap, spikes — implementation plan

Status: plan, 2026-09-17. Binding contract: `docs/blog-agent/plans/phases-2-10/CONTRACT.md` (wins over this plan). All paths are relative to `mdcopilot-blog/`; `pkg/` means `backend/src/mdcopilot_blog/`. Inside the `tools` container the working directory is `/app` = `backend/`, so commands below use `tests/…`, `spikes/…`, `src/…`.

## Header

### Goal
Replace Phase 1's real-mode stubs with working providers behind the frozen `LLMGateway` API, without changing mock-mode behaviour:
- Pydantic AI models for OpenAI Responses, Google and Anthropic, SDK retries off, reasoning pinned per agent (`RealModelFactory`).
- `OpenAIWebSearchProvider` (Responses `web_search`, plain text, `max_tool_calls`) and `GeminiEmbeddingProvider` (`gemini-embedding-2`, 1536 dims).
- Pricing: genai-prices 0.1.7 plus `blog_price_overrides` (model overrides and the search-action fee), frozen `price_version`.
- The budget scope of ruling D10 (`CallRecorder.budget_spent`), checked before every attempt of `run` and before `search`; before each `embed` provider request only when `ctx.attempt_id` is set (Changelog rev 3 item 9: API-side embeddings carry a `run_id` but no `attempt_id` and are recorded but never capped).
- One per-provider concurrency limiter per process, shared by `run`, `search`, `embed`.
- `observability.tracing.llm_span` around every attempt.
- Spike S4 mocked half as default tests; live tooling for S2, S3 and the S4 cost half, gated by `Live-go:` lines.

### Spec sections implemented
- ARCHITECTURE §7 (routes, model settings, reasoning pinned, no escalation), §7.1 (route walking guards, recording, budget, concurrency, mock-mode guard), §18 (cost: genai-prices + search-action fee from `blog_price_overrides`), §20 (building a real client in mock mode raises).
- RESEARCH_ARCHITECTURE §3 (`OpenAIWebSearchProvider` settings), §8 (4 concurrent LLM calls per provider).
- IMPLEMENTATION_PLAN Phase 2: spikes S2, S3, S4; build bullets "Pydantic AI provider adapters", "Routing and pricing", "Web search".
- FRAMEWORK_EVALUATION §"Decision" points 2–3 (own route walking; search not through a Pydantic AI agent).
- CONTRACT §0.3 D9 (spike rows), D10 (budget scope); §5.5 "Gateway behaviour PROV delivers"; §6 PROV settings; §9 gates S2/S3/S4 and live-spend rules; §10.1, §10.4 (vendor independence: route override behaviour), §10.8 (`llm_span`, `trace_id` always set).

### Owned files (CONTRACT §2.2 PROV)

| Path | Notes |
|---|---|
| `pkg/llm/gateway.py` | after FOUND's §5.5 edits; frozen signatures (§2 rules (c)); must import cleanly at every save point |
| `pkg/llm/routes.py` | |
| `pkg/llm/recorder.py` | adds `budget_spent(ctx)` (§5.5 Budget) with tests |
| `pkg/llm/providers.py` | `RealModelFactory` |
| `pkg/llm/embeddings.py` | `GeminiEmbeddingProvider`, `EmbeddingProvider` protocol |
| `pkg/llm/pricing.py` | `PriceBook` |
| `pkg/llm/concurrency.py` | per-provider limiter |
| `pkg/llm/search/openai.py` | `OpenAIWebSearchProvider` |
| `pkg/db/seed_data/price_overrides.yaml` | content |
| `backend/spikes/**` | S2/S3/S4 scripts |
| `backend/tests/providers/**` | |
| `backend/tests/unit/test_gateway.py`, `backend/tests/unit/test_routes.py`, `backend/tests/db/test_recorder.py` | may be edited to the new behaviour |
| `docs/blog-agent/spikes/S2-openai-web-search.md`, `S3-gemini.md`, `S4-route-walking.md` | results |
| `docs/blog-agent/plans/phases-2-10/prov.md` | this plan (written as `PROV.md`, see open questions) |
| `.superpowers/sdd/phases-2-10/requests/prov.md` | `Request:` and `Live:` lines (§2 rules) |

Read-only for PROV (a needed change is a `Request:` line): `pkg/llm/mock.py`, `pkg/llm/search/base.py`, `pkg/llm/search/fixture.py` (FOUND-frozen), `pkg/observability/tracing.py` (OBS), `pkg/workflows/names.py`, `pkg/db/models/**`, `pkg/db/seed.py`, `pkg/settings.py`, `pkg/prompts/registry.py`, `backend/tests/conftest.py`, `backend/tests/foundation/**`, `scripts/live/prepare_db.sh`.

### Extension points consumed (exact names, state after FOUND)
- `mdcopilot_blog.llm.gateway`: `AgentSpec` (incl. `reasoning: Literal["minimal","low","medium","high"] | None`), `CallContext`, `AgentResult`, `LLMGateway.run(spec, *, variables, user_prompt, ctx, route_override=None, prompt_version=None, output_check=None)`, `LLMGateway.search(query, *, ctx)`, `LLMGateway.embed(texts, *, ctx)`, `build_gateway(settings, sessionmaker, prompts)`, `build_model_factory(settings)`, `ADVANCE_ERRORS`, `GatewayError`, `BudgetExceeded`, `RouteExhausted`, `ProviderNotAvailable`, `ModelFactory`, `UnavailableModelFactory`, `UnavailableSearchProvider`, `mock_embedding`, `MOCK_EMBEDDING_PROVIDER`, `MOCK_EMBEDDING_MODEL`.
- `mdcopilot_blog.llm.routes`: `Provider`, `ModelChoice`, `parse_choice`, `route_for`, `route_from_entries(settings, agent, entries)`, `HELLO_ROUTE`.
- `mdcopilot_blog.llm.recorder`: `CallRecord`, `CallRecorder.record`, `CallRecorder.run_cost`, `PRICE_VERSION`, `ERROR_MESSAGE_LIMIT`.
- `mdcopilot_blog.llm.mock`: `FixtureRegistry`, `MockModelFactory`.
- `mdcopilot_blog.llm.search.base`: `SearchQuery` (incl. `mode: Literal["broad","deep","verification"]`, `route: list[str] | None = None`), `SearchResult`, `Citation`, `WebSearchProvider`, `SearchProviderError(provider, error_class, status_code, message, retryable)` (FOUND-created there, picklable; PROV raises it and never defines its own copy, so RES can import the same class during the parallel stage); `mdcopilot_blog.llm.search.fixture.FixtureSearchProvider(root=None, *, roots=None)`.
- `mdcopilot_blog.observability.tracing`: `llm_span(operation, *, ctx, provider, model, agent_name) -> ContextManager[SpanRecorder]`, `SpanRecorder.set_usage(*, input_tokens, output_tokens, cost_usd)`, `SpanRecorder.set_error(error_class)`.
- `mdcopilot_blog.workflows.names`: `HUMAN_ACTION_WORKFLOWS`, `WORKFLOW_PRODUCE_ARTICLE`, `WORKFLOW_REGENERATE_COMPONENT`, `WORKFLOW_REGENERATE_ARTICLE`, `WORKFLOW_RECHECK_ARTICLE`.
- `mdcopilot_blog.db.models`: `LlmCall`, `RunAttempt`, `BlogRun`, `PriceOverride`. `mdcopilot_blog.db.seed`: `seed_defaults`, `load_seed_file`, `SeedReport.price_overrides_created`. `mdcopilot_blog.db.engine`: `make_engine`, `make_sessionmaker`.
- `mdcopilot_blog.settings`: `Settings` fields `mock_mode, openai_api_key, gemini_api_key, anthropic_api_key, search_route, embedding_model, embedding_dimensions, max_cost_per_run_usd, provider_concurrency, search_context_size_broad, search_context_size_deep, search_max_tool_calls_broad, search_max_tool_calls_deep, price_auto_update, postgres_db`; `Settings.route_values()`; `get_settings()`.
- `mdcopilot_blog.prompts.registry`: `PromptRegistry.from_directory`, `PromptRegistry.render`, `default_prompt_root`.
- `mdcopilot_blog.ids`: `new_trace_id`, `uuid7`. `mdcopilot_blog.domain.enums`: `AgentName`, `CallKind`, `CallStatus`, `RunKind`, `RunStatus`. `mdcopilot_blog.domain.contracts`: `ArticleDraft`, `ResearchPacket`, `SeoPackage` (S3 only).
- Root `tests/conftest.py` fixtures: `settings`, `db_session`, `clean_db`, `sessionmaker_committing`.
- `scripts/live/prepare_db.sh` (FOUND) before any live spike.

### Import graph (keeps §2 rule (a): every save point imports cleanly)
- `gateway.py` imports at module top: `recorder`, `routes`, `pricing`, `concurrency`, `embeddings` (protocol, `EmbeddingBatch`, `EMBED_BATCH_SIZE` only are used at runtime), `search.base`, `search.fixture`, `prompts.registry`, `settings`.
- `gateway.py` imports lazily, inside function bodies: `mdcopilot_blog.observability.tracing` (it may import `CallContext` from `gateway`), `mdcopilot_blog.llm.providers`, `mdcopilot_blog.llm.search.openai`, `GeminiEmbeddingProvider`, and FOUND's existing lazy `llm.mock` import.
- `pricing.py`, `concurrency.py`, `routes.py` never import `gateway`. `embeddings.py` imports `ProviderNotAvailable` lazily inside `GeminiEmbeddingProvider.__init__`. `providers.py` and `search/openai.py` import `gateway` at module top (they are only imported lazily by `gateway`).
- New modules are created with their tests before `gateway.py` imports them. Other tracks run mock-mode suites against this working tree during the parallel stage, so after every task `tests/unit/test_gateway.py`, `tests/foundation` and `tests/workflows/test_hello_pipeline.py` stay green.

### Test database and commands
- Track DB `mdcopilot_blog_prov_test`; a reviewer or a second PROV process uses `mdcopilot_blog_prov_review_test`.
- Per-task test run (replace `<files>`):
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_prov_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q <files>
  ```
- Import gate before blaming a red test on PROV (§2 rules (b)):
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_prov_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
  ```
- Regression set run after every task that edits `gateway.py`, `routes.py` or `recorder.py`:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_prov_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/unit/test_gateway.py tests/unit/test_routes.py tests/db/test_recorder.py tests/unit/test_search_fixture.py tests/foundation tests/workflows/test_hello_pipeline.py
  ```
- Lint and types (owned paths; `--follow-imports=silent`):
  ```bash
  docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c \
    "ruff check --no-cache src/mdcopilot_blog/llm spikes tests/providers tests/unit/test_gateway.py && ruff format --check --no-cache src/mdcopilot_blog/llm spikes tests/providers tests/unit/test_gateway.py && mypy --cache-dir=/tmp/mypy --follow-imports=silent src/mdcopilot_blog/llm spikes"
  ```
- Default suites make no network call: every real SDK client in tests gets an `httpx2.AsyncClient(transport=httpx2.MockTransport(handler))`; containers of the `tools` service receive `.env` variables, so code must never pass `None` as an API key to an SDK (OpenAI, Anthropic and google-genai all fall back to environment variables).

### Owner inputs and fallback

| Input | Needed for | When missing (CONTRACT §9) |
|---|---|---|
| `OPENAI_API_KEY` and `Live-go: S2` in `progress.md` | S2 live run ($1.50 cap) | Provider built and tested over MockTransport; `S2-openai-web-search.md` says `Status: pending owner input (OPENAI_API_KEY and Live-go: S2)`; `Request:` line in `requests/prov.md` |
| `GEMINI_API_KEY` on a billed project, owner reads billing tier and `gemini-3.8-flash` RPM/TPM/RPD in AI Studio, `Live-go: S3` | S3 live run ($0.50 cap) | `S3-gemini.md` pending; embeddings and Google models tested over MockTransport |
| `Live-go: S4` plus the keys of the route models | S4 cost half ($0.20 cap) | Mocked half (PROV-11) complete; cost half marked pending in `S4-route-walking.md` |
| `ANTHROPIC_API_KEY` (optional) | S4 cost half row for `anthropic:claude-sonnet-5` | Row reported `skipped: ANTHROPIC_API_KEY missing` |

Presence checks print only `set`/`missing`:
```bash
docker compose run --rm --no-deps tools sh -c 'for v in OPENAI_API_KEY GEMINI_API_KEY ANTHROPIC_API_KEY; do eval "x=\${$v}"; test -n "$x" && echo "$v set" || echo "$v missing"; done'
```
Keys in `.env` are not permission to spend (§9 rule 1). Pending owner inputs never block completion (§9 rule 7).

### Verified external facts this plan relies on
Executed 2026-09-17 in `mdcopilot-blog-backend:dev` (`docker run --rm --network none`, containers `p2p-prov-*`, scripts in `.superpowers/sdd/phases-2-10/scratch/plan-prov/`). Versions in the image: pydantic-ai-slim 2.43.0, openai 3.14.1, anthropic 1.6.0, **google-genai 2.24.0**, genai-prices 0.1.7.
1. Real models over `httpx2.MockTransport`: OpenAI `POST https://api.openai.com/v1/responses`, Google `POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent`, Anthropic `POST https://api.anthropic.com/v1/messages?beta=true`. With SDK retries off a 503 makes exactly one HTTP call and raises `ModelHTTPError(status_code=503)` for all three. An `httpx2.ReadTimeout` raised by the transport surfaces as `ModelAPIError` (OpenAI, Anthropic) and as raw `httpx2.ReadTimeout` (Google); one HTTP call each.
2. `ModelSettings` `{"max_tokens": N, "timeout": 120.0}` gives request timeout extension `{"connect": 120.0, "read": 120.0, "write": 120.0, "pool": 120.0}` on all three providers (client built with `httpx2.Timeout(120.0)`).
3. Wire mapping: `openai_reasoning_effort="medium"` → body `"reasoning": {"effort": "medium", "context": "all_turns"}`, `"max_output_tokens"`; `google_thinking_config={"thinking_level": "MINIMAL"}` → `"generationConfig": {"maxOutputTokens": …, "responseModalities": ["TEXT"], "thinkingConfig": {"thinking_level": "MINIMAL"}}` (snake-case key inside camelCase config); `anthropic_effort="low"` → `"output_config": {"effort": "low"}`, `"max_tokens"`. `anthropic_effort` accepts only `low|medium|high|xhigh|max` (no `minimal`); `openai_reasoning_effort` accepts `minimal`; google-genai `ThinkingLevel` has `MINIMAL, LOW, MEDIUM, HIGH`. Auth headers: `x-goog-api-key`, `x-api-key`.
4. Success usage and cost (pydantic-ai fills `usage.cost` from genai-prices): OpenAI response (1000 in, 200 cached, 500 out, 100 reasoning) → cost `0.01328`, `model_name` `gpt-5.6-sol-2026-08-01`, `provider_name` `openai`; Google (1000 prompt, 400 candidates + 100 thoughts) → output_tokens 500, cost `0.002625`, `gemini-3.8-flash-001`; Anthropic (1000/500) → `0.007`, `claude-sonnet-5-20260901`. OpenAI invalid output with `retries={"output": 1}` → 2 HTTP calls, then `UnexpectedModelBehavior("Exceeded maximum output retries (1)")`, each response priced (`0.005` for 1000 in/50 out).
5. `FunctionModel` keeps an explicit `RequestUsage(..., cost=Decimal("0.5"))`; its `provider_name` is `None`.
6. genai-prices `calc_price(Usage(input_tokens=, output_tokens=, cache_read_tokens=), model, provider_id=, genai_request_timestamp=datetime(2026,9,17,1,30,tzinfo=UTC))`: gpt-5.6-luna 1000/1000 → `0.0014`; gpt-5.6-luna-2026-08-01 8600/300 → `0.00208`; gpt-5.6-sol 1000/500/200 → `0.01328`; gemini-embedding-2 100 in → `0.00002`; per 1M tokens at 1000-token scale: sol 4/20, terra 2/12, luna 0.2/1.2, gemini-3.8-flash 0.75/3.75, gemini-3.5-flash-lite 0.3/2.5, claude-sonnet-5 2/10 (1M-token requests hit the >272K tier and double). Unknown provider → `LookupError("Unable to find provider provider_id='fixture'")`; unknown model → `LookupError`. `pydantic_ai.prices.update_in_background()` exists, signature `() -> UpdatePrices`.
7. OpenAI Responses search: `responses.create` accepts `tools=[{"type":"web_search","search_context_size":…,"filters":{"allowed_domains":[…]}}]`, `tool_choice="required"`, `include=["web_search_call.action.sources"]`, `max_tool_calls`, `store=False`, `instructions`, `timeout`. `Response.model_config["extra"] == "allow"`, so `tool_usage` arrives in `response.model_extra` (`{}` when absent). Output items: `ResponseFunctionWebSearch` (`type "web_search_call"`, `action.type` `search|open_page|find_in_page`, `action.sources[].url` for `search`), `ResponseOutputMessage` with `ResponseOutputText.annotations[]` of `AnnotationURLCitation(url, title, start_index, end_index)`; `response.output_text`; `usage.input_tokens_details.cached_tokens`, `usage.output_tokens_details.reasoning_tokens`. Errors with `max_retries=0`: 503 `InternalServerError`, 429 `RateLimitError`, 400 `BadRequestError` (all `APIStatusError` with `.status_code`), transport timeout `APITimeoutError` (subclass of `APIConnectionError`).
8. google-genai embeddings: `client.aio.models.embed_content(model="gemini-embedding-2", contents=[types.Content(parts=[types.Part(text=t)]) for t in texts], config=types.EmbedContentConfig(output_dimensionality=d))` sends one `POST …/models/gemini-embedding-2:batchEmbedContents` with one entry per text and returns one embedding per text. **Passing `contents=["alpha", "beta"]` sends ONE request entry with two parts and returns ONE vector.** `EmbedContentResponse` has only `embeddings`, `metadata` (`billable_character_count`), `sdk_http_response` (body `None`): no token usage. `HttpOptions(httpx_async_client=client, retry_options=HttpRetryOptions(attempts=1), timeout=30000)` → request timeout 30 s; **with `timeout=None` the request has no timeout at all, whatever the client's timeout.** Errors: 503 `google.genai.errors.ServerError`, 400 and 429 `ClientError` (both `APIError` with `.code`); transport timeout raw `httpx2.ReadTimeout`; one HTTP call with `attempts=1`.

---

## Tasks

TDD order in every task: write the listed tests, run them in Docker and see them fail for the stated reason (red), implement, run them green, then run the regression set and the lint gate. Record red and green output lines in the track report.

### PROV-1: Test scaffolding and per-attempt model settings (reasoning)

**Files**
- create `backend/tests/providers/prov_fakes.py`, `backend/tests/providers/test_prov_model_settings.py`
- modify `backend/tests/providers/conftest.py` (FOUND left a docstring only)
- modify `pkg/llm/routes.py`, `pkg/llm/gateway.py`

**Interfaces**
- Consumes: `AgentSpec.reasoning`, `ModelChoice`, `pydantic_ai.settings.ModelSettings`.
- Produces in `routes.py`:
  ```python
  Reasoning = Literal["minimal", "low", "medium", "high"]
  def model_settings_for(choice: ModelChoice, *, max_tokens: int, timeout_seconds: float,
                         reasoning: Reasoning | None) -> ModelSettings: ...
  ```
- Produces in `tests/providers/prov_fakes.py` (test helpers, extended by later tasks):
  - `class Draft(BaseModel)`: `title: str`, `words: int`.
  - `class FakeRecorder(CallRecorder)`: `__init__(self, *, spend: Decimal = Decimal(0), spend_per_ok: Decimal = Decimal(0))` without calling `super().__init__`; `records: list[CallRecord]`; `budget_queries: list[CallContext]`; `async record(rec) -> uuid.UUID` appends and adds `spend_per_ok` to `spend` when `rec.status == CallStatus.OK`; `async budget_spent(ctx) -> Decimal` appends `ctx` and returns `spend`; `async run_cost(run_id) -> Decimal` returns `spend`.
  - `@dataclass class ScriptedFactory(ModelFactory)`: `scripts: dict[str, Callable[[], Model]]`, `built: list[str]`; `build(choice, spec)` appends `choice.ref()` and returns `scripts[choice.ref()]()`.
  - `ok_model(model_name: str, payload: dict[str, Any], *, usage: RequestUsage | None = None, seen: list[AgentInfo] | None = None) -> Callable[[], Model]` (default usage `RequestUsage(input_tokens=50, output_tokens=12)`); `failing_model(model_name: str, exc: Exception, *, seen: list[AgentInfo] | None = None)`; `invalid_model(model_name: str, calls: list[int])` (returns `{"title": "t", "words": "not-a-number"}` with usage 10/3). All use `ToolCallPart(info.output_tools[0].name, payload)`.
  - `write_writer_prompt(root: Path) -> PromptRegistry`: writes `root/writer/draft.v1.md` with front matter `name: writer/draft`, `version: 1`, `agent: writer`, `output: Draft`, `variables: [topic]`, body `Write about {{ topic }}.`, returns `PromptRegistry.from_directory(root)`.
- Produces in `tests/providers/conftest.py` (fixtures):
  - `prompts(tmp_path) -> PromptRegistry` = `write_writer_prompt(tmp_path / "prompts")`.
  - `mock_settings(settings) -> Settings`: copy with `mock_mode=True`, `writer_route=["openai:model-a", "google:model-b"]`, `max_cost_per_run_usd=Decimal("1.00")`, `embedding_model="google:gemini-embedding-test"`, `embedding_dimensions=8`, `provider_concurrency=4`.
  - `real_settings(settings) -> Settings`: copy with `mock_mode=False`, `openai_api_key=SecretStr("sk-test")`, `gemini_api_key=SecretStr("g-test")`, `anthropic_api_key=SecretStr("a-test")`, `writer_route=["openai:model-a", "google:model-b"]`, `max_cost_per_run_usd=Decimal("1.00")`, `embedding_dimensions=3`, `provider_concurrency=4`.
  - `ctx() -> CallContext` = `CallContext(trace_id=new_trace_id(), run_id=uuid7(), attempt_id=uuid7(), dbos_workflow_id="wf-prov")`.
  - `fixed_clock() -> Callable[[], datetime]` returning `datetime(2026, 9, 17, 1, 30, tzinfo=UTC)`.
  - `allow_model_requests(monkeypatch)`: `monkeypatch.setattr(pydantic_ai.models, "ALLOW_MODEL_REQUESTS", True)`.
  - `search_fixture_root(tmp_path) -> Path`: copies `backend/fixtures/mock/search/default.json` (FOUND-frozen Phase 1 content) into `tmp_path / "search"` and returns that directory.

**Behaviour rules**
1. `model_settings_for` always returns `max_tokens` and `timeout` (a float; never an `httpx`/`httpx2` `Timeout` object, which Google rejects).
2. `reasoning is None` → no other key.
3. `openai` → adds `openai_reasoning_effort: reasoning` (all four values).
4. `google` → adds `google_thinking_config: {"thinking_level": reasoning.upper()}`.
5. `anthropic` → adds `anthropic_effort`: `"low"` for `minimal` and `low`, `"medium"` for `medium`, `"high"` for `high`.
6. `mock` → no reasoning key.
7. `LLMGateway.run` builds the settings per attempt from that attempt's `ModelChoice` and `spec.reasoning`; a later attempt never gets a higher level; no other key is added. The recorded `params` dict stays exactly as FOUND leaves it.

**Tests to write first** (`tests/providers/test_prov_model_settings.py`, 18 tests)
1. `test_no_reasoning_sets_only_tokens_and_timeout` — parametrize provider `openai|google|anthropic|mock`; `model_settings_for(ModelChoice(p, "m"), max_tokens=900, timeout_seconds=45.0, reasoning=None) == {"max_tokens": 900, "timeout": 45.0}`. (4)
2. `test_openai_effort` — parametrize the four levels; result `== {"max_tokens": 900, "timeout": 45.0, "openai_reasoning_effort": level}`. (4)
3. `test_google_thinking_level` — parametrize `(minimal, MINIMAL)`, `(low, LOW)`, `(medium, MEDIUM)`, `(high, HIGH)`; result `== {"max_tokens": 900, "timeout": 45.0, "google_thinking_config": {"thinking_level": upper}}`. (4)
4. `test_anthropic_effort_maps_minimal_to_low` — parametrize `(minimal, low)`, `(low, low)`, `(medium, medium)`, `(high, high)`; result `== {"max_tokens": 900, "timeout": 45.0, "anthropic_effort": mapped}`. (4)
5. `test_mock_provider_ignores_reasoning` — `ModelChoice("mock", "hello")`, `reasoning="high"` → `== {"max_tokens": 900, "timeout": 45.0}`. (1)
6. `test_gateway_passes_each_attempts_reasoning` — `mock_settings`, `FakeRecorder()`, spec `AgentSpec(name=AgentName.WRITER, version="1", prompt_name="writer/draft", output_type=Draft, max_output_tokens=300, reasoning="medium")`; `ScriptedFactory({"openai:model-a": failing_model("fixture-a", ModelHTTPError(status_code=503, model_name="model-a"), seen=first), "google:model-b": ok_model("fixture-b", {"title": "B", "words": 1}, seen=second)})`; `await gateway.run(spec, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx)`. Assert `first[0].model_settings["openai_reasoning_effort"] == "medium"`, `"google_thinking_config" not in first[0].model_settings`, `second[0].model_settings["google_thinking_config"] == {"thinking_level": "MEDIUM"}`, `"openai_reasoning_effort" not in second[0].model_settings`, `second[0].model_settings["max_tokens"] == 300`, `second[0].model_settings["timeout"] == 120.0`. (1) (`failing_model` appends `info` to `seen` before raising.)

**Implementation notes**
- The provider TypedDicts (`OpenAIResponsesModelSettings`, `GoogleModelSettings`, `AnthropicModelSettings`) are subclasses of `ModelSettings`; build the provider dict and return it as `ModelSettings` (use `cast` where mypy needs it). `routes.py` may import `pydantic_ai.settings` (only `llm/` imports `pydantic_ai`).
- In `gateway.run`, replace the single `model_settings` built before the loop with `model_settings_for(choice, max_tokens=spec.max_output_tokens, timeout_seconds=spec.timeout_seconds, reasoning=spec.reasoning)` inside the loop. Keep FOUND's `route_override`, `prompt_version` and `output_check` code paths unchanged.

**Verification**
- Red: `pytest … tests/providers/test_prov_model_settings.py` → collection error `ImportError: cannot import name 'model_settings_for'`.
- Green: `18 passed`; regression set passes with no failures; lint gate prints `All checks passed!` and `Success: no issues found`.

**Acceptance covered**: CONTRACT §5.5 "`ModelSettings` carries `max_tokens`, numeric `timeout`, and the reasoning mapping … (never raised on retry)"; ARCHITECTURE §7 "Model settings".

### PROV-2: Per-provider concurrency limiter

**Files**
- create `pkg/llm/concurrency.py`, `backend/tests/providers/test_prov_concurrency.py`
- modify `pkg/llm/gateway.py`

**Interfaces**
- Produces (`concurrency.py`):
  ```python
  class ProviderLimiter:
      def __init__(self, limit: int) -> None: ...
      @property
      def limit(self) -> int: ...
      @asynccontextmanager
      async def slot(self, provider: str) -> AsyncIterator[None]: ...
  def process_limiter(limit: int) -> ProviderLimiter: ...
  ```
- Produces (`gateway.py`): `LLMGateway.__init__(…, limiter: ProviderLimiter | None = None)` (keyword-only, after FOUND's parameters); read-only property `LLMGateway.limiter -> ProviderLimiter`.

**Behaviour rules**
1. `ProviderLimiter(limit)` with `limit < 1` raises `ValueError("provider concurrency must be >= 1")`.
2. One `asyncio.Semaphore(limit)` per (running event loop, provider key), created on first use and stored in a `weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Semaphore]]`, so a semaphore is never shared between loops and a closed loop's semaphores are released.
3. `process_limiter(limit)` returns the same `ProviderLimiter` for the same `limit` within the process (module-level dict guarded by a `threading.Lock`).
4. `LLMGateway(limiter=None)` uses `process_limiter(settings.provider_concurrency)`.
5. The gateway holds a slot only around the provider call itself: `agent.run(...)` of one attempt (key `choice.provider`), `provider.search(query)` (key `provider.name`), one embedding provider request or one mock embedding batch (key: provider of `parse_choice(settings.embedding_model)`). Budget checks, pricing and recorder writes run outside the slot.
6. The slot is released when the call raises. No code acquires a slot while holding one.

**Tests to write first** (`test_prov_concurrency.py`, 7 tests)
1. `test_limit_must_be_at_least_one` — `pytest.raises(ValueError, match="provider concurrency must be >= 1")` for `ProviderLimiter(0)`.
2. `test_slot_caps_concurrent_holders` — `ProviderLimiter(2)`; six tasks each enter `slot("openai")`, increment `in_flight`, record `max_in_flight`, `await asyncio.sleep(0.01)`, decrement; after `gather`: `max_in_flight == 2` and six completions.
3. `test_providers_have_independent_slots` — `ProviderLimiter(1)`; task A holds `slot("openai")` until `release_a` is set; task B enters `slot("google")` and sets `b_done`; `await asyncio.wait_for(b_done.wait(), 1)` succeeds while A still holds; then set `release_a`, await A.
4. `test_process_limiter_is_shared_per_limit` — `process_limiter(4) is process_limiter(4)`; `process_limiter(4) is not process_limiter(2)`; `process_limiter(4).limit == 4`.
5. `test_gateway_defaults_to_process_limiter` — `LLMGateway(settings=mock_settings, prompts=prompts, recorder=FakeRecorder(), model_factory=ScriptedFactory({}), search_provider=FixtureSearchProvider(root=search_fixture_root))` → `gateway.limiter is process_limiter(4)`.
6. `test_agent_call_and_search_share_a_provider_slot` — `limiter=ProviderLimiter(1)`, `mock_settings`; `openai:model-a` is an async `FunctionModel` that sets `agent_started`, awaits `release`, then returns `{"title": "A", "words": 1}`; the search provider is a fake with `name = "openai"` whose `search` sets `search_started` and returns `SearchResult(provider="openai", model="fake", answer_text="a", citations=[], sources=[], search_actions=1)`. Start `run` as a task, `await agent_started.wait()`, start `search` as a task, `await asyncio.sleep(0.05)`; assert `not search_started.is_set()`; set `release`; await both; assert `search_started.is_set()`.
7. `test_slot_is_released_when_a_call_fails` — `ProviderLimiter(1)`, `writer_route=["openai:model-a", "openai:model-c"]`, model-a raises `ModelHTTPError(503)`, model-c ok; `result = await asyncio.wait_for(gateway.run(...), 2)`; `result.attempts == 2`.

**Implementation notes**: none beyond the rules (standard library only).

**Verification**
- Red: `ModuleNotFoundError: No module named 'mdcopilot_blog.llm.concurrency'`.
- Green: `7 passed`; regression set green; lint gate clean.

**Acceptance covered**: CONTRACT §5.5 "Per-provider concurrency: one `asyncio.Semaphore(settings.provider_concurrency)` per provider key per process, shared by `run`, `search`, `embed`"; RESEARCH_ARCHITECTURE §8 "LLM calls 4 concurrent per provider".

### PROV-3: `llm_span` around every attempt

**Files**
- modify `pkg/llm/gateway.py`, `backend/tests/providers/prov_fakes.py`
- create `backend/tests/providers/test_prov_tracing.py`

**Interfaces**
- Consumes: `mdcopilot_blog.observability.tracing.llm_span(operation: Literal["chat","web_search","embeddings"], *, ctx: CallContext, provider: str, model: str, agent_name: str | None) -> ContextManager[SpanRecorder]`; `SpanRecorder.set_usage(*, input_tokens: int, output_tokens: int, cost_usd: Decimal)`; `SpanRecorder.set_error(error_class: str)`.
- Produces in `prov_fakes.py`: `class SpanLog` with `entries: list[dict[str, Any]]` and `install(monkeypatch) -> None`, which replaces `mdcopilot_blog.observability.tracing.llm_span` with a context manager appending `{"operation", "ctx", "provider", "model", "agent_name", "usage": None, "error": None, "closed": False}` on enter, filling `usage` as the tuple `(input_tokens, output_tokens, cost_usd)` or `error` as the class name, and setting `closed=True` on exit.

**Behaviour rules**
1. The gateway imports `tracing` lazily inside `run`, `search` and `embed` and calls `tracing.llm_span` through the module attribute, so OBS's implementation and test monkeypatching both apply.
2. `run`: one span per attempt, `operation="chat"`, `provider=choice.provider`, `model=choice.model`, `agent_name=spec.name.value`, entered after that attempt's budget check and before the model is built; closes before the next attempt starts.
3. `search`: one span, `operation="web_search"`, `provider=provider.name`, `model=<model_requested>` (PROV-8 rule 2), `agent_name="search"`.
4. `embed`: one span per provider request (per batch), `operation="embeddings"`, `provider`/`model` from `parse_choice(settings.embedding_model)`, `agent_name=None`.
5. On success `set_usage` receives the recorded input tokens, output tokens and cost (the priced cost from PROV-6/8/9 in real mode). On any exception raised by the call, `set_error(type(exc).__name__)` is called inside the span before the attempt is recorded; the exception then advances or propagates exactly as before.
6. No span is opened when `BudgetExceeded`, `PriceMissing` or a pre-call `ProviderNotAvailable` (no row) is raised.

**Tests to write first** (`test_prov_tracing.py`, 6 tests; all use `mock_settings`, `FakeRecorder`, `ScriptedFactory`, `SpanLog().install(monkeypatch)`)
1. `test_run_success_has_one_chat_span` — `openai:model-a` ok → `len(entries) == 1`; entry `operation == "chat"`, `ctx is ctx`, `provider == "openai"`, `model == "model-a"`, `agent_name == "writer"`, `usage == (50, 12, Decimal(0))`, `error is None`, `closed is True`.
2. `test_fallback_has_one_span_per_attempt` — model-a 503, model-b ok → two entries; first `error == "ModelHTTPError"`, `usage is None`, `closed`; second `provider == "google"`, `model == "model-b"`, `usage == (50, 12, Decimal(0))`.
3. `test_unexpected_error_marks_the_span` — model-a raises `ValueError("bug")` → `pytest.raises(ValueError)`; one entry with `error == "ValueError"`, `closed`.
4. `test_search_span` — `FixtureSearchProvider(root=search_fixture_root)`; `await gateway.search(SearchQuery(text="q"), ctx=ctx)` → one entry `operation == "web_search"`, `provider == "fixture"`, `model == "fixture"`, `agent_name == "search"`, `usage == (0, 0, Decimal("0"))`.
5. `test_embed_span_per_request` — `await gateway.embed(["alpha topic", "beta topic"], ctx=ctx)` → one entry `operation == "embeddings"`, `provider == "google"`, `model == "gemini-embedding-test"`, `agent_name is None`, `usage == (4, 0, Decimal(0))`.
6. `test_budget_exceeded_opens_no_span` — `FakeRecorder(spend=Decimal("1.00"))` → `pytest.raises(BudgetExceeded)`; `entries == []`.

**Implementation notes**: keep FOUND's `output_check` validator registration inside the span. The Phase 1 duplicated `_record_agent_attempt` calls in the two `except` branches may be folded into one helper; behaviour stays identical.

**Verification**: red — `AssertionError` (`entries == []` in tests 1–5); green — `6 passed`; regression set green; lint clean.

**Acceptance covered**: CONTRACT §5.5 "Every attempt runs inside `observability.tracing.llm_span(...)`"; §10.8 "OpenTelemetry `gen_ai.*` spans … PROV (`llm_span` calls)".

### PROV-4: Budget scope (ruling D10) and the `trace_id` guard

**Files**
- modify `pkg/llm/recorder.py`, `pkg/llm/gateway.py`, `backend/tests/unit/test_gateway.py`, `backend/tests/providers/prov_fakes.py`
- create `backend/tests/providers/test_prov_budget.py`

**Interfaces**
- Produces (`recorder.py`):
  ```python
  class CallRecorder:
      async def budget_spent(self, ctx: CallContext) -> Decimal: ...
      async def record(self, rec: CallRecord) -> uuid.UUID: ...   # now rejects a blank trace_id
      async def run_cost(self, run_id: uuid.UUID | None) -> Decimal: ...   # unchanged
  ```
- Produces (`prov_fakes.py`, DB helpers taking `async_sessionmaker[AsyncSession]` and committing): `add_run(sm) -> BlogRun` (`kind="manual"`, `run_date=date(2026, 9, 17)`, `status="QUEUED"`, `params={}`, `trace_id=new_trace_id()`); `add_attempt(sm, *, run_id, workflow_name) -> RunAttempt` (`dbos_workflow_id=f"{workflow_name}-{uuid7()}"`, `attempt_no=1`, `status="RUNNING"`); `add_call(sm, *, run_id, attempt_id, cost: str) -> uuid.UUID` (through `CallRecorder.record` with kind `agent`, provider `openai`, model `gpt-test`, status `ok`, `latency_ms=1`, `trace_id=new_trace_id()`).
- Consumes: `RunAttempt.workflow_name`, `LlmCall.cost_usd/run_id/attempt_id`, `HUMAN_ACTION_WORKFLOWS`.

**Behaviour rules**
1. `budget_spent(ctx)`, one read-only session, no commit:
   a. If `ctx.attempt_id` is set and `SELECT workflow_name FROM blog_run_attempts WHERE id = ctx.attempt_id` is in `HUMAN_ACTION_WORKFLOWS` → `SUM(cost_usd)` of calls with `attempt_id = ctx.attempt_id` (whatever their `run_id`).
   b. Else, if `ctx.run_id` is set → `SUM(blog_llm_calls.cost_usd)` over calls with `run_id = ctx.run_id` `LEFT OUTER JOIN blog_run_attempts ON blog_run_attempts.id = blog_llm_calls.attempt_id` where `blog_run_attempts.workflow_name IS NULL OR blog_run_attempts.workflow_name NOT IN HUMAN_ACTION_WORKFLOWS`. An `attempt_id` with no attempt row counts as pipeline spend.
   c. Else `Decimal(0)`.
   Error rows count (their cost is real spend). Return `Decimal(str(total))`, `coalesce` to 0.
2. `record(rec)` raises `ValueError("CallContext.trace_id is required")` when `rec.ctx.trace_id.strip() == ""`, before opening a session (no row).
3. `LLMGateway._check_budget(ctx)`: if `ctx.run_id is None and ctx.attempt_id is None` → return without a query (uncapped, even when the cap is `0`). Otherwise `spent = await recorder.budget_spent(ctx)`; if `spent >= settings.max_cost_per_run_usd` → `BudgetExceeded(f"run {ctx.run_id} (attempt {ctx.attempt_id}) has spent {spent} USD; the cap is {cap} USD")`.
4. Called before every attempt of `run` (including the first), before `search` (before the fee guard of PROV-8), and before each embedding provider request or mock embedding batch (PROV-9).
5. `run_cost` is unchanged and no longer used by the gateway.
6. Before editing `_check_budget`, run `grep -rn "run_cost" backend/tests/foundation` (read-only). If a FOUND test's fake recorder overrides only `run_cost` and would now reach the database through `budget_spent`, stop this item and add `Request: FOUND follow-up — tests/foundation/<file> fake recorder must implement budget_spent(ctx) (CONTRACT §5.5 Budget)` to `requests/prov.md`; do not edit FOUND files.

**Edits to `tests/unit/test_gateway.py`**: `FakeRecorder` gains `async def budget_spent(self, ctx: CallContext) -> Decimal` that appends `ctx.run_id` to `self.cost_queries` and returns `self.cost`. Every existing assertion (`recorder.cost_queries == [ctx.run_id]`, `match="cap is 1.00 USD"`) keeps passing unchanged.

**Tests to write first** (`test_prov_budget.py`, 11 tests, `clean_db` + `sessionmaker_committing`)

Shared graph (fixture `budget_graph`): runs `R` and `O`; attempts on `R`: `P` (`produce_article`), `H1` (`regenerate_component`), `H2` (`recheck_article`); calls: `(R, P, "1.20")`, `(R, P, "0.30")`, `(R, None, "0.50")`, `(R, H1, "0.75")`, `(R, H2, "0.10")`, `(O, None, "9.00")`, `(None, None, "7.00")`.
1. `test_run_scope_excludes_human_action_attempts` — `budget_spent(CallContext(trace_id=R.trace_id, run_id=R.id)) == Decimal("2.00")`.
2. `test_pipeline_attempt_uses_run_scope` — ctx `(R, P)` → `Decimal("2.00")`.
3. `test_human_action_attempt_is_its_own_scope` — ctx `(R, H1)` → `Decimal("0.75")`; `(R, H2)` → `Decimal("0.10")`; `(run_id=None, attempt_id=H1)` → `Decimal("0.75")`.
4. `test_unknown_attempt_counts_as_pipeline` — ctx `(R, uuid7())` → `Decimal("2.00")`.
5. `test_no_run_and_no_attempt_is_zero` — `CallContext(trace_id=new_trace_id())` → `Decimal(0)`.
6. `test_record_rejects_blank_trace_id` — `pytest.raises(ValueError, match="CallContext.trace_id is required")` for `trace_id="  "`; `SELECT count(*) FROM app.blog_llm_calls` is still 7.

Gateway tests (real `CallRecorder(sessionmaker_committing)`, `mock_settings`, `ScriptedFactory({"openai:model-a": ok_model("fixture-a", {"title": "t", "words": 1})})`, `prompts`):
7. `test_pipeline_spend_at_cap_blocks_next_pipeline_call` — cap `Decimal("2.00")`; ctx `(R, P, trace R)` → `pytest.raises(BudgetExceeded, match="the cap is 2.00 USD")`; `factory.built == []`.
8. `test_human_action_attempt_starts_at_zero_on_a_capped_run` — cap `2.00`; new attempt `H3` (`regenerate_article`) on `R` with no calls; `run` succeeds; the new row has `attempt_id == H3.id` and `run_id == R.id`.
9. `test_human_action_attempts_are_capped_independently` — cap `Decimal("0.75")`; ctx `(R, H1)` raises `BudgetExceeded`; ctx `(R, H2)` succeeds.
10. `test_run_less_calls_are_never_capped` — cap `Decimal("0")`; ctx `CallContext(trace_id=new_trace_id())`; `run` succeeds, `search` with `FixtureSearchProvider(root=search_fixture_root)` succeeds, `embed(["a b"])` succeeds; three new rows with `run_id IS NULL`.
11. `test_search_and_embed_check_the_budget_first` — cap `2.00`, ctx `(R, P)`; `search` and `embed(["x"])` each raise `BudgetExceeded`; row count stays 7.

**Implementation notes**: SQLAlchemy — `select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).select_from(LlmCall).outerjoin(RunAttempt, RunAttempt.id == LlmCall.attempt_id).where(LlmCall.run_id == ctx.run_id, or_(RunAttempt.workflow_name.is_(None), RunAttempt.workflow_name.not_in(sorted(HUMAN_ACTION_WORKFLOWS))))`.

**Verification**: red — `AttributeError: 'CallRecorder' object has no attribute 'budget_spent'` (tests 1–5), test 6 `DID NOT RAISE`, test 8 `BudgetExceeded`; green — `11 passed`; regression set green (`tests/unit/test_gateway.py` `23 passed`, `tests/db/test_recorder.py` `3 passed`); lint clean.

**Acceptance covered**: CONTRACT D10 and §5.5 Budget (all four PROV tests named there); §10.1 "run cost cap … `BudgetExceeded` before run/search/embed"; §10.8 "Every `blog_llm_calls` row has … `trace_id` — PROV (`trace_id` always set)"; INVENTORY §16 item 4 ("`embed()` has no budget check").

### PROV-5: Pricing module and the seeded search-fee row

**Files**
- create `pkg/llm/pricing.py`, `backend/tests/providers/test_prov_pricing.py`, `backend/tests/providers/test_prov_price_book_db.py`
- modify `pkg/db/seed_data/price_overrides.yaml`

**Interfaces** (`pricing.py`; imports `db.models.PriceOverride`, `llm.recorder.PRICE_VERSION`, `genai_prices`, `pydantic_ai.prices`; never `gateway`)
```python
GENAI_PRICES_VERSION: Final = PRICE_VERSION              # "genai-prices==0.1.7"
REAL_PROVIDERS: Final = frozenset({"openai", "google", "anthropic"})
SEARCH_FEE_SKU: Final = "web_search_call"
PricingSource = Literal["genai-prices", "override", "unpriced"]

@dataclass(frozen=True)
class OverridePrice:
    provider: str; sku: str
    input_per_mtok: Decimal | None; output_per_mtok: Decimal | None
    cache_read_per_mtok: Decimal | None; per_1k_calls: Decimal | None
    effective_from: datetime; price_version: str

@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int; output_tokens: int; cache_read_tokens: int = 0

@dataclass(frozen=True)
class PricedCall:
    cost_usd: Decimal; price_version: str; source: PricingSource; override_versions: tuple[str, ...]

class PriceMissing(RuntimeError):
    def __init__(self, provider: str, sku: str) -> None: ...   # str: f"no effective price override for ({provider}, {sku})"

class PriceBook(Protocol):
    async def override_for(self, provider: str, sku: str, *, at: datetime) -> OverridePrice | None: ...

class StaticPriceBook:            # tests, spikes, and the gateway default
    def __init__(self, rows: Iterable[OverridePrice] = ()) -> None: ...
    async def override_for(self, provider: str, sku: str, *, at: datetime) -> OverridePrice | None: ...

class DbPriceBook:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None: ...
    async def override_for(self, provider: str, sku: str, *, at: datetime) -> OverridePrice | None: ...

def quantize_usd(value: Decimal) -> Decimal: ...
def override_token_cost(price: OverridePrice, usage: TokenUsage) -> Decimal | None: ...
def search_fee(price: OverridePrice, search_actions: int) -> Decimal: ...
def genai_token_cost(provider: str, model: str, usage: TokenUsage, *, at: datetime) -> Decimal | None: ...
def price_version_for(override_versions: Sequence[str]) -> str: ...
async def price_agent_attempt(book: PriceBook, *, provider_requested: str, model_requested: str,
                              provider_served: str | None, model_served: str | None, usage: TokenUsage,
                              sdk_cost: Decimal | None, at: datetime) -> PricedCall: ...
async def price_search_call(book: PriceBook, *, provider_requested: str, model_requested: str,
                            provider_served: str, model_served: str, usage: TokenUsage,
                            search_actions: int, fee: OverridePrice, at: datetime) -> PricedCall: ...
async def price_embedding_call(book: PriceBook, *, provider: str, model: str, input_tokens: int,
                               at: datetime) -> PricedCall: ...
def ensure_price_updates(settings: Settings) -> bool: ...
```

**Behaviour rules**
1. Both price books raise `ValueError("at must be timezone-aware")` for a naive `at`. They return the row for `(provider, sku)` with the greatest `effective_from <= at` (inclusive), else `None`. `DbPriceBook` runs `SELECT … FROM app.blog_price_overrides WHERE provider=:p AND sku=:s AND effective_from <= :at ORDER BY effective_from DESC LIMIT 1` in its own session and maps the ORM row to `OverridePrice`.
2. `quantize_usd(v) = v.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)`; every `PricedCall.cost_usd` is quantized.
3. `override_token_cost(price, usage)`: let `cache = min(usage.cache_read_tokens, usage.input_tokens)`, `uncached = usage.input_tokens - cache`, `cache_price = price.cache_read_per_mtok if not None else price.input_per_mtok`. Return `None` (override not usable for tokens) when `input_per_mtok` and `output_per_mtok` are both `None`, or `uncached > 0` and `input_per_mtok is None`, or `cache > 0` and `cache_price is None`, or `output_tokens > 0` and `output_per_mtok is None`. Otherwise `quantize_usd((uncached*input + cache*cache_price + output_tokens*output) / 1_000_000)`, treating a `None` price whose token count is 0 as 0. (Cache-write tokens are inside `input_tokens` for Anthropic and are priced at the input rate.)
4. `search_fee(price, n)`: `n < 0` → `ValueError("search_actions must be >= 0")`; `price.per_1k_calls is None` → `PriceMissing(price.provider, price.sku)`; else `quantize_usd(n * per_1k_calls / 1000)`.
5. `genai_token_cost`: `provider not in REAL_PROVIDERS` → `None`; else `genai_prices.calc_price(Usage(input_tokens=…, output_tokens=…, cache_read_tokens=…), model, provider_id=provider, genai_request_timestamp=at)`; `LookupError` → `None`; else `quantize_usd(total_price)`.
6. `price_version_for([]) == "genai-prices==0.1.7"`; otherwise `"genai-prices==0.1.7;" + ";".join(versions)`; a result longer than 64 characters raises `ValueError("price_version exceeds 64 characters")`.
7. `price_agent_attempt` order: (a) override for `(provider_requested, model_requested)` if `override_token_cost` is not `None`; (b) else override for `(provider_served, model_served)` when both are set and differ from the requested pair, if usable; (c) else `sdk_cost is not None` → `PricedCall(quantize_usd(sdk_cost), GENAI_PRICES_VERSION, "genai-prices", ())`; (d) else `PricedCall(Decimal("0.000000"), GENAI_PRICES_VERSION, "unpriced", ())`. An override result has `source="override"` and `price_version_for([row.price_version])`.
8. `price_search_call`: token part by the same override order (requested, then served); else `genai_token_cost(provider_served, model_served, …)`; else `genai_token_cost(provider_requested, model_requested, …)`; else 0 with source `unpriced`. Total `= token part + search_fee(fee, search_actions)`. `price_version = price_version_for([model override version if used] + [fee.price_version])` (model override first). `source` describes the token part.
9. `price_embedding_call`: override `(provider, model)` with `TokenUsage(input_tokens, 0)` if usable; else `genai_token_cost`; else 0 `unpriced`.
10. `ensure_price_updates(settings)`: returns `False` and does nothing when `settings.mock_mode` or not `settings.price_auto_update`, or when an updater was already started in this process; otherwise calls `pydantic_ai.prices.update_in_background()` through the module attribute, stores the returned `UpdatePrices` in module variable `_PRICE_UPDATER`, returns `True`.
11. `PriceMissing` survives `pickle` (`__reduce__` returns `(PriceMissing, (provider, sku))`).
12. `price_overrides.yaml` holds exactly one item (quoted date so PyYAML yields a string; if FOUND's loader rejects a string, write the unquoted date instead and note it in the task report):
    ```yaml
    price_overrides:
      - provider: openai
        sku: web_search_call
        input_per_mtok: null
        output_per_mtok: null
        cache_read_per_mtok: null
        per_1k_calls: 10.00
        effective_from: "2026-01-01"
        note: "OpenAI Responses web_search tool: $10.00 per 1,000 search calls (openai.com/api/pricing, read 2026-09-17). Search content tokens are billed at the model's token rates."
    ```

**Tests to write first**

`test_prov_pricing.py` (23 tests; `AT = datetime(2026, 9, 17, 1, 30, tzinfo=UTC)`; helper `row(provider, sku, *, inp=None, out=None, cache=None, per_1k=None, eff=datetime(2026, 1, 1, tzinfo=UTC), version)`):
1. `test_override_token_cost_splits_cached_input` — prices 4/20/cache 0.4, `TokenUsage(1000, 500, 200)` → `Decimal("0.013280")`.
2. `test_override_cache_read_falls_back_to_input_price` — 4/20/None, same usage → `Decimal("0.014000")`.
3. `test_override_unusable_when_a_used_component_has_no_price` — parametrize: (inp None, out 20, `TokenUsage(10, 5)`), (inp 4, out None, `TokenUsage(10, 5)`), (inp None, out None, `TokenUsage(0, 0)`) → `None`. (3)
4. `test_override_null_price_with_zero_tokens_is_usable` — inp 0.5, out None, `TokenUsage(1000, 0)` → `Decimal("0.000500")`.
5. `test_search_fee` — per_1k 10: 3 actions → `Decimal("0.030000")`; 0 → `Decimal("0.000000")`; -1 → `ValueError`.
6. `test_search_fee_without_per_1k_calls_raises` — `pytest.raises(PriceMissing, match=r"no effective price override for \(openai, web_search_call\)")`.
7. `test_genai_token_cost_known_models` — parametrize `("openai","gpt-5.6-luna",TokenUsage(1000,1000)) → "0.001400"`, `("openai","gpt-5.6-sol",TokenUsage(1000,500,200)) → "0.013280"`, `("openai","gpt-5.6-luna-2026-08-01",TokenUsage(8600,300)) → "0.002080"`, `("google","gemini-embedding-2",TokenUsage(100,0)) → "0.000020"`, each at `AT`. (4)
8. `test_genai_token_cost_unknown_returns_none` — parametrize `("fixture","fixture-search")`, `("openai","does-not-exist-9")`, `("mock","hello")`. (3)
9. `test_price_version_for` — `[]` → `"genai-prices==0.1.7"`; `["ovr:0123456789ab"]` → `"genai-prices==0.1.7;ovr:0123456789ab"`; `["ovr:aaaaaaaaaaaa","ovr:bbbbbbbbbbbb"]` → that string, `len == 53`; a 65-character result raises `ValueError`.
10. `test_static_price_book_effective_dates` — rows fee 10 (`eff 2026-01-01`, `ovr:000000000001`) and fee 12 (`eff 2026-10-01T00:00Z`, `ovr:000000000002`): at `AT` → version `ovr:000000000001`; at `2026-10-01T00:00Z` → `ovr:000000000002`; at `2025-12-31T23:59Z` → `None`; sku `other` → `None`.
11. `test_price_books_reject_naive_time` — `StaticPriceBook().override_for("openai", "x", at=datetime(2026, 9, 17))` raises `ValueError("at must be timezone-aware")`.
12. `test_agent_attempt_pricing_order` — `TokenUsage(1000, 500, 200)`, requested `("openai","gpt-5.6-sol")`, served `("openai","gpt-5.6-sol-2026-08-01")`, sdk `Decimal("0.01328")`:
    - A: served row inp 1 out 2 `ovr:5e0000000001` → `cost == Decimal("0.002000")`, `price_version == "genai-prices==0.1.7;ovr:5e0000000001"`, `source == "override"`.
    - B: requested row inp 3 out 6 `ovr:7e0000000001` plus the served row → `Decimal("0.006000")`, version `…;ovr:7e0000000001`.
    - C: no rows → `Decimal("0.013280")`, version `"genai-prices==0.1.7"`, source `genai-prices`.
    - D: no rows, `sdk_cost=None` → `Decimal("0.000000")`, source `unpriced`.
    - E: requested row inp None out 6 (unusable) plus served row → result A.
13. `test_search_call_pricing` — served `("openai","gpt-5.6-luna-2026-08-01")`, requested `("openai","gpt-5.6-luna")`, `TokenUsage(8600, 300)`, 1 action, fee row per_1k 10 `ovr:fee000000001`: no model row → `Decimal("0.012080")`, version `"genai-prices==0.1.7;ovr:fee000000001"`, source `genai-prices`; with requested row inp 1 out 1 `ovr:a00000000001` → `Decimal("0.018900")`, version `"genai-prices==0.1.7;ovr:a00000000001;ovr:fee000000001"`, source `override`.
14. `test_embedding_call_pricing` — `("google","gemini-embedding-2", 100)`: no rows → `Decimal("0.000020")`, source `genai-prices`, version plain; row inp 0.5 out None `ovr:e00000000001` → `Decimal("0.000050")`, version `…;ovr:e00000000001`; `("mock","mock:embedding", 100)` → `Decimal("0.000000")`, `unpriced`.
15. `test_price_missing_pickles` — round trip keeps `str(exc)` and `type`.
16. `test_ensure_price_updates_only_for_real_mode_with_flag` — monkeypatch `pydantic_ai.prices.update_in_background` with a counter returning `object()` and `pricing._PRICE_UPDATER` to `None`: mock+flag → `False`, 0 calls; real+no flag → `False`; real+flag → `True`, 1 call; again → `False`, still 1.

`test_prov_price_book_db.py` (4 tests, `clean_db` + `sessionmaker_committing`):
17. `test_db_price_book_picks_latest_effective_row` — insert the two rows of test 10 as `PriceOverride` ORM rows (explicit `price_version`), commit; same four assertions through `DbPriceBook(sm)`; returned `per_1k_calls == Decimal("10.000000")`.
18. `test_db_price_book_rejects_naive_time`.
19. `test_seed_file_declares_the_search_fee_row` — `load_seed_file("price_overrides.yaml")["price_overrides"]` has length 1; item `provider == "openai"`, `sku == "web_search_call"`, the three token prices `None`, `per_1k_calls == 10.0`, `note.startswith("OpenAI Responses web_search tool")`.
20. `test_seeded_search_fee_row_is_effective` — in a committing session `report = await seed_defaults(session)`; commit; `report.price_overrides_created == 1`; `DbPriceBook(sm).override_for("openai", "web_search_call", at=AT)` has `per_1k_calls == Decimal("10.000000")`, `effective_from == datetime(2026, 1, 1, tzinfo=UTC)`, `re.fullmatch(r"ovr:[0-9a-f]{12}", price_version)`; a second `seed_defaults` returns `price_overrides_created == 0`.

**Implementation notes** (verified in the backend image):
```python
from genai_prices import Usage, calc_price
pc = calc_price(Usage(input_tokens=8600, output_tokens=300, cache_read_tokens=0),
                "gpt-5.6-luna-2026-08-01", provider_id="openai",
                genai_request_timestamp=datetime(2026, 9, 17, 1, 30, tzinfo=UTC))
pc.total_price   # Decimal("0.00208"); LookupError for unknown provider or model
from pydantic_ai import prices as pai_prices
updater = pai_prices.update_in_background()   # () -> UpdatePrices; network, never in tests
```

**Verification**: red — `ModuleNotFoundError: No module named 'mdcopilot_blog.llm.pricing'`; test 19 fails on the empty seed list. Green — `27 passed` across both files; also run `tests/db/test_seed.py` (FOUND's) — passes; lint clean.

**Acceptance covered**: CONTRACT §5.5 "Cost …", §3.1 `price_version` format and the 53-character limit, §3.4 `price_overrides.yaml` (PROV content), §9 rule 4 ("must contain the `(openai, web_search_call)` row"); §10.1 "Routing, pricing (genai-prices + `blog_price_overrides` search fee) … tests: override price used, `price_version` format".

### PROV-6: Real-mode pricing of agent attempts

**Files**
- modify `pkg/llm/gateway.py`
- create `backend/tests/providers/test_prov_gateway_pricing.py`

**Interfaces**
- Produces: `LLMGateway.__init__(…, price_book: PriceBook | None = None, clock: Callable[[], datetime] = _utcnow)` (keyword-only; `None` → `StaticPriceBook(())`); module function `_utcnow() -> datetime` (`datetime.now(UTC)`); read-only property `LLMGateway.price_book -> PriceBook`.
- Consumes: `pricing.price_agent_attempt`, `pricing.TokenUsage`, `pricing.quantize_usd`.

**Behaviour rules**
1. Mock mode (`settings.mock_mode is True`): cost, `price_version` and `usage_raw` are recorded exactly as FOUND leaves them (sum of response `usage.cost`, `"genai-prices==0.1.7"`, `{"requests": […]}`); the price book is never called.
2. Real mode, every attempt (success or error): `at = self._clock()` read immediately before the model call; after the call `priced = await price_agent_attempt(self._price_book, provider_requested=choice.provider, model_requested=choice.model, provider_served=<recorded provider_served>, model_served=<recorded model_served>, usage=TokenUsage(input, output, cache_read), sdk_cost=<sum of response costs, or None when no response had a cost>, at=at)`.
3. The row gets `cost_usd=priced.cost_usd`, `price_version=priced.price_version`, `usage_raw={"requests": […], "pricing": priced.source}`; the span gets the priced cost; `AgentResult.cost_usd = priced.cost_usd`.
4. The private `_Usage` gains `any_cost: bool` (true when at least one `ModelResponse.usage.cost` is not `None`).
5. A price book exception propagates (the attempt is not recorded); it is a database failure and the step retries.

**Tests to write first** (`test_prov_gateway_pricing.py`, 6 tests; `real_settings`, `FakeRecorder`, `ScriptedFactory`, `prompts`, `clock=fixed_clock`)
1. `test_real_mode_sdk_cost_without_override` — `ok_model("fixture-a", {...}, usage=RequestUsage(input_tokens=50, output_tokens=12, cost=Decimal("0.5")))`, `StaticPriceBook(())` → `rec.cost_usd == Decimal("0.500000")`, `rec.price_version == "genai-prices==0.1.7"`, `rec.usage_raw["pricing"] == "genai-prices"`, `result.cost_usd == Decimal("0.500000")`.
2. `test_real_mode_requested_override_replaces_sdk_cost` — same model; row `("openai","model-a", inp 1000, out 2000, eff 2026-01-01, "ovr:0000000000a1")` → `rec.cost_usd == Decimal("0.074000")`, `rec.price_version == "genai-prices==0.1.7;ovr:0000000000a1"`, `usage_raw["pricing"] == "override"`.
3. `test_real_mode_invalid_output_attempt_is_priced` — `invalid_model` on model-a, ok on model-b (cost None), rows for both `("openai","model-a")` and `("google","model-b")` at inp 1000 out 2000 → `records[0].status == CallStatus.ERROR`, `records[0].cost_usd == Decimal("0.032000")` (20 in, 6 out), `records[1].cost_usd == Decimal("0.074000")`, both versions end with their `ovr:` value.
4. `test_real_mode_unpriced_without_cost_or_override` — ok model with no cost, empty book → `rec.cost_usd == Decimal("0.000000")`, `usage_raw["pricing"] == "unpriced"`.
5. `test_mock_mode_never_consults_the_price_book` — `mock_settings`; a price book whose `override_for` raises `AssertionError("called")` → run succeeds, `rec.price_version == "genai-prices==0.1.7"`, `"pricing" not in rec.usage_raw`.
6. `test_real_mode_uses_the_clock_for_lookups` — recording book → every captured `at == datetime(2026, 9, 17, 1, 30, tzinfo=UTC)`; captured keys `[("openai","model-a"), ("function","fixture-a")]` (plain `FunctionModel` reports `system == "function"`).

**Implementation notes**: none (internal code).

**Verification**: red — `TypeError: … unexpected keyword argument 'price_book'`; green — `6 passed`; regression set green; lint clean.

**Acceptance covered**: CONTRACT §5.5 "Cost: agent calls use `usage.cost` (genai-prices 0.1.7) unless `blog_price_overrides` has an effective row … lookup order …"; §10.1 "override price used, `price_version` format".

### PROV-7: `RealModelFactory` (OpenAI Responses, Google, Anthropic)

**Files**
- create `pkg/llm/providers.py`, `backend/tests/providers/test_prov_real_factory.py`
- modify `pkg/llm/gateway.py` (`build_model_factory`), `backend/tests/unit/test_gateway.py`, `backend/tests/providers/prov_fakes.py`

**Interfaces**
- Produces (`providers.py`):
  ```python
  HttpClientFactory = Callable[[float], httpx2.AsyncClient]
  def default_http_client(timeout_seconds: float) -> httpx2.AsyncClient: ...  # httpx2.AsyncClient(timeout=httpx2.Timeout(timeout_seconds))
  class RealModelFactory:   # satisfies gateway.ModelFactory
      def __init__(self, settings: Settings, *, http_client_factory: HttpClientFactory | None = None) -> None: ...
      def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model: ...
  ```
- Changes: `build_model_factory(settings)` → FOUND's mock branch unchanged; real mode returns `RealModelFactory(settings)` (lazy import).
- Produces in `prov_fakes.py`: JSON constants `OPENAI_OK`, `OPENAI_INVALID`, `GOOGLE_OK`, `ANTHROPIC_OK`, `ERROR_503` (below); `handler_by_host(handlers: Mapping[str, Callable[[httpx2.Request], httpx2.Response]], calls: list[httpx2.Request]) -> Callable[[httpx2.Request], httpx2.Response]` (records every request, dispatches on `request.url.host`); `mock_client_factory(handler) -> HttpClientFactory` returning `httpx2.AsyncClient(transport=httpx2.MockTransport(handler), timeout=httpx2.Timeout(t))`.

**Behaviour rules**
1. Constructor: `settings.mock_mode` → `ProviderNotAvailable("real model clients cannot be built while BLOG_AGENT_MOCK_MODE is true")`.
2. `build`: provider `mock` → `ProviderNotAvailable(f"route entry '{choice.ref()}' requires mock mode")`.
3. Keys come only from `Settings`. A `None` key raises `ProviderNotAvailable("OPENAI_API_KEY is not set")`, `("GEMINI_API_KEY is not set")` or `("ANTHROPIC_API_KEY is not set")`; an SDK is never constructed with `api_key=None` (each SDK would read its own environment variable).
4. `openai` → `OpenAIResponsesModel(choice.model, provider=OpenAIProvider(openai_client=AsyncOpenAI(api_key=key, max_retries=0, http_client=<client>)))`.
5. `google` → `GoogleModel(choice.model, provider=GoogleProvider(api_key=key, retry_options=HttpRetryOptions(attempts=1), http_client=<client>))`.
6. `anthropic` → `AnthropicModel(choice.model, provider=AnthropicProvider(anthropic_client=AsyncAnthropic(api_key=key, max_retries=0, http_client=<client>)))`.
7. `<client> = http_client_factory(spec.timeout_seconds)` (default `default_http_client`). The pydantic-ai provider object is cached per `(provider, spec.timeout_seconds)` for the factory's lifetime; model objects are built on every call.
8. No tools, no Gemini grounding, no Anthropic web search are ever attached.
9. The factory never changes `pydantic_ai.models.ALLOW_MODEL_REQUESTS`.
10. `ADVANCE_ERRORS` stays Phase 1's tuple; a `RuntimeError` from `ALLOW_MODEL_REQUESTS=False` is recorded and re-raised, never advanced (existing test kept).

**Edits to `tests/unit/test_gateway.py`**: replace `test_real_mode_factory_is_unavailable` with `test_real_mode_builds_real_model_factory`: `real = gw_settings.model_copy(update={"mock_mode": False, "openai_api_key": SecretStr("sk-test"), "gemini_api_key": SecretStr("gm-test")})`; `factory = build_model_factory(real)`; `isinstance(factory, RealModelFactory)`; `isinstance(factory.build(ModelChoice("openai", "model-a"), WRITER_SPEC), OpenAIResponsesModel)`. Remove the now-unused `UnavailableModelFactory` import.

**Response constants** (verified wire shapes; `ERROR_503 = {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE", "type": "server_error"}}`):
```python
OPENAI_OK = {"id": "resp_1", "object": "response", "created_at": 1758096000, "model": "gpt-5.6-sol-2026-08-01",
  "status": "completed", "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
  "output": [{"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "final_result",
              "arguments": "{\"title\":\"t\",\"words\":1}", "status": "completed"}],
  "usage": {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 200}, "output_tokens": 500,
            "output_tokens_details": {"reasoning_tokens": 100}, "total_tokens": 1500}}
OPENAI_INVALID = OPENAI_OK with arguments "{\"title\":\"t\",\"words\":\"not-a-number\"}",
  usage input 1000 (cached 0), output 50 (reasoning 0), total 1050
GOOGLE_OK = {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": "final_result",
  "args": {"title": "t", "words": 1}}}]}, "finishReason": "STOP"}],
  "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 400, "thoughtsTokenCount": 100,
                    "totalTokenCount": 1500}, "modelVersion": "gemini-3.8-flash-001", "responseId": "r1"}
ANTHROPIC_OK = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-20260901",
  "content": [{"type": "tool_use", "id": "toolu_1", "name": "final_result", "input": {"title": "t", "words": 1}}],
  "stop_reason": "tool_use", "stop_sequence": None, "usage": {"input_tokens": 1000, "output_tokens": 500}}
```

**Tests to write first** (`test_prov_real_factory.py`, 20 tests; wire tests request `allow_model_requests`; hosts `api.openai.com`, `generativelanguage.googleapis.com`, `api.anthropic.com`; `SPEC = AgentSpec(name=AgentName.WRITER, version="1", prompt_name="writer/draft", output_type=Draft, max_output_tokens=4500, reasoning="medium")`; gateway tests use `real_settings` with a `RealModelFactory(real_settings, http_client_factory=mock_client_factory(handler_by_host(...)))`, `FakeRecorder`, `StaticPriceBook(())`, `route_override=[entry]` or `[entry, other]`)
1. `test_refuses_mock_mode` — `pytest.raises(ProviderNotAvailable, match="BLOG_AGENT_MOCK_MODE is true")`.
2. `test_builds_provider_models` — parametrize `(ModelChoice("openai","gpt-5.6-sol"), OpenAIResponsesModel, "openai")`, `(ModelChoice("google","gemini-3.8-flash"), GoogleModel, "google")`, `(ModelChoice("anthropic","claude-sonnet-5"), AnthropicModel, "anthropic")` → `isinstance`, `model.model_name == choice.model`, `model.system == system`. (3)
3. `test_missing_key_raises_even_when_env_var_is_set` — parametrize `("openai", "openai_api_key", ["OPENAI_API_KEY"], "OPENAI_API_KEY is not set")`, `("google", "gemini_api_key", ["GEMINI_API_KEY", "GOOGLE_API_KEY"], "GEMINI_API_KEY is not set")`, `("anthropic", "anthropic_api_key", ["ANTHROPIC_API_KEY"], "ANTHROPIC_API_KEY is not set")`; `monkeypatch.setenv` each variable to `"env-key"`; settings key set to `None` → `ProviderNotAvailable` with that message. (3)
4. `test_mock_route_entry_rejected` — `ModelChoice("mock", "hello")` → `ProviderNotAvailable(match="requires mock mode")`.
5. `test_provider_clients_are_cached_per_timeout` — counting factory: build openai with SPEC twice → 1 client; openai with `timeout_seconds=60.0` → 2; google with SPEC → 3.
6. `test_request_shape_usage_and_cost` — parametrize provider (3):
   - openai: one request, URL `https://api.openai.com/v1/responses`, body `model == "gpt-5.6-sol"`, `max_output_tokens == 4500`, `reasoning == {"effort": "medium", "context": "all_turns"}`; `result.provider == "openai"`, `result.model == "gpt-5.6-sol-2026-08-01"`; `rec` tokens `(1000, 500)`, `cache_read_tokens == 200`, `reasoning_tokens == 100`; `rec.cost_usd == genai_token_cost("openai", "gpt-5.6-sol-2026-08-01", TokenUsage(1000, 500, 200), at=datetime.now(UTC))` and `> 0`.
   - google: URL `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent`, `body["generationConfig"]["maxOutputTokens"] == 4500`, `body["generationConfig"]["thinkingConfig"] == {"thinking_level": "MEDIUM"}`, header `x-goog-api-key == "g-test"`; `result.model == "gemini-3.8-flash-001"`; tokens `(1000, 500)`, `reasoning_tokens == 100`; cost equals `genai_token_cost("google", "gemini-3.8-flash-001", TokenUsage(1000, 500), at=now)` and `> 0`.
   - anthropic: URL `https://api.anthropic.com/v1/messages?beta=true`, `body["max_tokens"] == 4500`, `body["output_config"] == {"effort": "medium"}`, header `x-api-key == "a-test"`; `result.model == "claude-sonnet-5-20260901"`; tokens `(1000, 500)`; cost equals `genai_token_cost("anthropic", "claude-sonnet-5-20260901", TokenUsage(1000, 500), at=now)` and `> 0`.
   - all three: `request.extensions["timeout"] == {"connect": 120.0, "read": 120.0, "write": 120.0, "pool": 120.0}` (`SPEC.timeout_seconds` default 120.0).
7. `test_http_503_is_one_request_and_advances` — parametrize pairs `openai→google`, `google→anthropic`, `anthropic→openai` (first host returns 503 `ERROR_503`, second returns its OK body) → requests to the first host `== 1`; `records[0].error_class == "ModelHTTPError"`; `records[1].status == CallStatus.OK`, `records[1].fallback_from == first_entry`; `result.attempts == 2`. (3)
8. `test_timeout_is_one_request_and_advances` — same pairs; first handler raises `httpx2.ReadTimeout("read timed out", request=request)` → one request; `records[0].error_class` is `"ModelAPIError"` (openai), `"ReadTimeout"` (google), `"ModelAPIError"` (anthropic); second attempt ok. (3)
9. `test_route_override_drops_providers_without_keys` — `real_settings` with `anthropic_api_key=None`, `ScriptedFactory` (google ok); `route_override=["anthropic:claude-sonnet-5", "google:gemini-3.8-flash"]` → `factory.built == ["google:gemini-3.8-flash"]`.
10. `test_real_build_model_factory_leaves_allow_flag` — with `allow_model_requests`: `isinstance(build_model_factory(real_settings), RealModelFactory)` and `pydantic_ai.models.ALLOW_MODEL_REQUESTS is True`.

**Implementation notes** (verified construction; no network at construction):
```python
import httpx2
from anthropic import AsyncAnthropic
from google.genai.types import HttpRetryOptions
from openai import AsyncOpenAI
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

client = httpx2.AsyncClient(timeout=httpx2.Timeout(spec.timeout_seconds))
OpenAIResponsesModel(name, provider=OpenAIProvider(openai_client=AsyncOpenAI(api_key=key, max_retries=0, http_client=client)))
GoogleModel(name, provider=GoogleProvider(api_key=key, retry_options=HttpRetryOptions(attempts=1), http_client=client))
AnthropicModel(name, provider=AnthropicProvider(anthropic_client=AsyncAnthropic(api_key=key, max_retries=0, http_client=client)))
```
`OpenAIProvider` asserts `openai_client` is not combined with `api_key`/`base_url`/`http_client`; Google takes its request timeout from the client's read timeout, so the client timeout must equal `spec.timeout_seconds`.

**Verification**: red — `ModuleNotFoundError: No module named 'mdcopilot_blog.llm.providers'`; green — `20 passed`; regression set green (`tests/unit/test_gateway.py` `23 passed`); lint clean.

**Acceptance covered**: CONTRACT §10.1 "Provider adapters (OpenAI Responses, Google, Anthropic when key set) — MockTransport tests per provider: request shape, SDK retries off, 503/timeout advance"; §5.5 `build_model_factory` bullet and "`ADVANCE_ERRORS` keeps Phase 1's tuple"; §10.4 vendor independence "PROV (route override behaviour)"; ARCHITECTURE §20 mock-mode guard.

### PROV-8: `OpenAIWebSearchProvider` and search pricing

**Files**
- create `pkg/llm/search/openai.py`, `backend/tests/providers/test_prov_openai_search.py`
- modify `pkg/llm/gateway.py` (`search`), `backend/tests/providers/prov_fakes.py` (`SEARCH_RESPONSE`)

**Interfaces**
- Produces (`search/openai.py`):
  ```python
  SEARCH_TIMEOUT_SECONDS: Final = 120.0
  MAX_ALLOWED_DOMAINS: Final = 100
  SEARCH_INSTRUCTIONS: Final = ("Use web search to answer the question. Reply in plain text in at most 200 words. "
                                "Cite every source you rely on.")
  class SearchProviderError(RuntimeError):
      def __init__(self, provider: str, error_class: str, status_code: int | None, message: str,
                   retryable: bool) -> None: ...
      # attributes of the same names; str(): f"{error_class} (HTTP {status_code}): {message}",
      # or f"{error_class}: {message}" when status_code is None; picklable (__reduce__)
  class OpenAISearchResult(SearchResult):
      usage_details: dict[str, str | int | None]
  def default_search_model(settings: Settings) -> str: ...
  class OpenAIWebSearchProvider:
      name: str = "openai"
      model: str
      def __init__(self, settings: Settings, *, model: str | None = None,
                   http_client: httpx2.AsyncClient | None = None) -> None: ...
      async def search(self, query: SearchQuery) -> OpenAISearchResult: ...
  ```
- Consumes: `SearchQuery` (`text`, `mode`, `allowed_domains`, `recency_days`), `SearchResult`, `Citation`, `route_for(settings, AgentName.SEARCH)`, `pricing.price_search_call`, `pricing.PriceMissing`, `pricing.SEARCH_FEE_SKU`, `pricing.REAL_PROVIDERS`.

**Provider rules**
1. Constructor: `settings.mock_mode` → `ProviderNotAvailable("real search clients cannot be built while BLOG_AGENT_MOCK_MODE is true")`; `settings.openai_api_key is None` → `ProviderNotAvailable("OPENAI_API_KEY is not set")`; `model` defaults to `default_search_model(settings)`.
2. `default_search_model`: the model of the first `openai` entry of `route_for(settings, AgentName.SEARCH)`; a `ValueError` from `route_for` or no `openai` entry → `ProviderNotAvailable("search route has no usable openai entry")`.
3. Client: `AsyncOpenAI(api_key=<secret>, max_retries=0, http_client=http_client or httpx2.AsyncClient(timeout=httpx2.Timeout(SEARCH_TIMEOUT_SECONDS)))`, built once in the constructor.
4. Per mode: `broad` and `verification` → `search_context_size=settings.search_context_size_broad`, `max_tool_calls=settings.search_max_tool_calls_broad`; `deep` → `settings.search_context_size_deep`, `settings.search_max_tool_calls_deep`.
5. `len(query.allowed_domains) > MAX_ALLOWED_DOMAINS` → `ValueError("allowed_domains accepts at most 100 domains")` before any request.
6. Request (exactly these parameters): `model=self.model`, `instructions=SEARCH_INSTRUCTIONS`, `input=query.text` (plus `"\n\nPrefer sources published in the last {recency_days} days."` when `recency_days` is set), `tools=[{"type": "web_search", "search_context_size": size}]` with `"filters": {"allowed_domains": list(query.allowed_domains)}` added only when the list is non-empty, `tool_choice="required"`, `include=["web_search_call.action.sources"]`, `max_tool_calls=n`, `store=False`, `timeout=SEARCH_TIMEOUT_SECONDS`. `max_results` is not sent (the tool has no result-count parameter). No JSON schema, no second structuring call.
7. Parsing, walking `response.output` in order: a `web_search_call` item whose `action.type == "search"` contributes `action.sources[].url` (sources may be `None`); a `message` item contributes, for each `output_text` part, each `url_citation` annotation as `Citation(url, title, start_index, end_index)` in order (no de-duplication of citations). `sources` = action-source URLs and citation URLs de-duplicated in order of first appearance. `answer_text = response.output_text`.
8. `search_actions` = `response.model_extra["tool_usage"]["web_search"]["num_requests"]` when that path holds an `int >= 0` (`num_requests_source="tool_usage"`); otherwise the count of `web_search_call` items with `action.type == "search"` (`"output_items"`).
9. Result: `provider="openai"`, `model=response.model` (served, dated), `input_tokens`, `output_tokens` from `response.usage` (0 when `usage` is `None`), `cost_usd=Decimal(0)` (the gateway prices), `latency_ms` measured around the request, `usage_details={"response_id": response.id, "status": response.status, "action_source_count": n, "citation_count": n, "num_requests_source": "tool_usage"|"output_items", "cache_read_tokens": cached, "reasoning_tokens": reasoning, "search_context_size": size, "max_tool_calls": n}`.
10. Errors: `openai.APIStatusError` → `SearchProviderError("openai", type(exc).__name__, exc.status_code, <message ≤ 500 chars>, retryable=status in {408, 409, 429} or status >= 500)`; `openai.APIConnectionError` (including `APITimeoutError`) and `httpx2.TransportError` → status `None`, `retryable=True`; `response.status in {"failed", "cancelled"}` → `SearchProviderError("openai", "ResponseFailed", None, f"{response.status}: {error.code if error else 'no error'}: {error.message if error else ''}", retryable=True)`; other exceptions propagate unchanged.

**Gateway `search` rules**
1. Budget check (PROV-4) first.
2. `provider_requested = provider.name`; `model_requested = provider.model` when the provider has a `str` attribute `model`, else `provider.name` (so `FixtureSearchProvider` keeps `("fixture", "fixture")`).
3. Real mode and `provider.name in REAL_PROVIDERS`: `at = clock()`; `fee = await price_book.override_for(provider.name, SEARCH_FEE_SKU, at=at)`; `fee is None or fee.per_1k_calls is None` → raise `PriceMissing(provider.name, "web_search_call")` with no span, no slot, no request and no row.
4. Span `web_search` (PROV-3), slot `provider.name` (PROV-2), `await provider.search(query)`.
5. On exception: `set_error`, record the Phase 1 error row (with rule-2 requested fields, cost 0, `price_version` `"genai-prices==0.1.7"`), re-raise unchanged.
6. On success: `details = result.usage_details` if the attribute exists and is a `Mapping`, else `{}`; `cache_read_tokens`/`reasoning_tokens` = the `int` values in `details`, else 0. Real mode with a `REAL_PROVIDERS` provider → `priced = await price_search_call(book, provider_requested=…, model_requested=…, provider_served=result.provider, model_served=result.model, usage=TokenUsage(result.input_tokens, result.output_tokens, cache_read), search_actions=result.search_actions, fee=fee, at=at)`; otherwise cost `result.cost_usd` and plain `price_version`. `usage_raw = {"search_actions": …, "sources": len(result.sources), "citations": len(result.citations)} | details`, plus `"pricing": priced.source` in the priced case. `params = query.model_dump(mode="json")` (unchanged).

**`SEARCH_RESPONSE`** (verified to parse with openai 3.14.1):
```python
SEARCH_RESPONSE = {"id": "resp_s1", "object": "response", "created_at": 1758096000, "model": "gpt-5.6-luna-2026-08-01",
  "status": "completed", "parallel_tool_calls": True, "tool_choice": "required",
  "tools": [{"type": "web_search", "search_context_size": "low"}],
  "output": [
    {"type": "web_search_call", "id": "ws_1", "status": "completed", "action": {"type": "search", "query": "q1",
     "sources": [{"type": "url", "url": "https://a.example/x"}, {"type": "url", "url": "https://b.example/y"}]}},
    {"type": "web_search_call", "id": "ws_2", "status": "completed", "action": {"type": "open_page", "url": "https://a.example/x"}},
    {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed", "content": [{"type": "output_text",
     "text": "Alpha beta gamma.", "annotations": [
       {"type": "url_citation", "url": "https://c.example/z", "title": "C", "start_index": 0, "end_index": 5},
       {"type": "url_citation", "url": "https://a.example/x", "title": "A", "start_index": 6, "end_index": 10}]}]}],
  "usage": {"input_tokens": 8600, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 300,
            "output_tokens_details": {"reasoning_tokens": 120}, "total_tokens": 8900},
  "tool_usage": {"web_search": {"num_requests": 1}}}
```

**Tests to write first** (`test_prov_openai_search.py`, 24 tests; provider built with `real_settings` and `http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))`; the handler records requests)
1. `test_constructor_refuses_mock_mode`.
2. `test_constructor_requires_openai_key_even_with_env` — `OPENAI_API_KEY` env set, settings key `None` → message `OPENAI_API_KEY is not set`.
3. `test_default_model_is_first_openai_search_route_entry` — `search_route=["google:gemini-3.8-flash", "openai:gpt-5.6-terra", "openai:gpt-5.6-luna"]` → `provider.model == "gpt-5.6-terra"`; `model="gpt-5.6-luna"` argument → `"gpt-5.6-luna"`; code-default route → `"gpt-5.6-luna"`.
4. `test_search_route_without_openai_entry_raises` — `search_route=["google:gemini-3.8-flash"]` → `ProviderNotAvailable(match="no usable openai entry")`.
5. `test_broad_request_body` — `SearchQuery(text="FDA AI device clearances")` → one request to `https://api.openai.com/v1/responses`; `json.loads(request.content) == {"model": "gpt-5.6-luna", "instructions": SEARCH_INSTRUCTIONS, "input": "FDA AI device clearances", "tools": [{"type": "web_search", "search_context_size": "low"}], "tool_choice": "required", "include": ["web_search_call.action.sources"], "max_tool_calls": 1, "store": False}`; timeout extension `read == 120.0`.
6. `test_deep_request_uses_deep_settings` — `mode="deep"` → `tools == [{"type": "web_search", "search_context_size": "medium"}]`, `max_tool_calls == 2`.
7. `test_verification_uses_broad_settings_with_allowed_domains` — `mode="verification"`, `allowed_domains=["fda.gov", "cdc.gov"]` → `tools == [{"type": "web_search", "search_context_size": "low", "filters": {"allowed_domains": ["fda.gov", "cdc.gov"]}}]`, `max_tool_calls == 1`.
8. `test_settings_drive_context_and_tool_calls` — `search_context_size_broad="high"`, `search_max_tool_calls_broad=3` → body values `"high"` and `3`.
9. `test_recency_days_appended_to_input` — `recency_days=7` → `input == "FDA AI device clearances\n\nPrefer sources published in the last 7 days."`.
10. `test_more_than_100_allowed_domains_rejected_before_sending` — 101 domains → `ValueError(match="at most 100")`; no request.
11. `test_parses_answer_citations_sources_and_usage` — `SEARCH_RESPONSE` → `isinstance(result, OpenAISearchResult)`; `provider == "openai"`; `model == "gpt-5.6-luna-2026-08-01"`; `answer_text == "Alpha beta gamma."`; `citations == [Citation(url="https://c.example/z", title="C", start_index=0, end_index=5), Citation(url="https://a.example/x", title="A", start_index=6, end_index=10)]`; `sources == ["https://a.example/x", "https://b.example/y", "https://c.example/z"]`; `search_actions == 1`; `(input_tokens, output_tokens) == (8600, 300)`; `cost_usd == Decimal(0)`; `usage_details == {"response_id": "resp_s1", "status": "completed", "action_source_count": 2, "citation_count": 2, "num_requests_source": "tool_usage", "cache_read_tokens": 0, "reasoning_tokens": 120, "search_context_size": "low", "max_tool_calls": 1}`; `latency_ms >= 0`.
12. `test_search_actions_fall_back_to_search_items` — response without `tool_usage` and with a second `search` item (sources `None`) → `search_actions == 2`, `num_requests_source == "output_items"`.
13. `test_empty_annotations_and_sources` — only a `message` item with `annotations: []` → `citations == []`, `sources == []`, `action_source_count == 0`, `search_actions == 0`.
14. `test_http_errors_map_to_search_provider_error` — parametrize `(503, "InternalServerError", True)`, `(429, "RateLimitError", True)`, `(400, "BadRequestError", False)` → one request; `exc.status_code == status`, `exc.error_class == name`, `exc.retryable is flag`, `str(exc).startswith(f"{name} (HTTP {status}): ")`. (3)
15. `test_timeout_maps_to_retryable_error` — handler raises `httpx2.ReadTimeout` → `error_class == "APITimeoutError"`, `status_code is None`, `retryable is True`, `str(exc).startswith("APITimeoutError: ")`; one request.
16. `test_failed_response_status_raises` — `status: "failed"`, `error: {"code": "server_error", "message": "boom"}` → `error_class == "ResponseFailed"`, `retryable is True`, `"server_error" in str(exc)`.
17. `test_search_provider_error_pickles`.
Gateway (`real_settings`, `FakeRecorder`, `clock=fixed_clock`):
18. `test_real_search_records_a_priced_row` — book `[row("openai", "web_search_call", per_1k=Decimal("10"), version="ovr:fee000000001")]` → `rec.kind == CallKind.SEARCH`, `(provider_requested, model_requested) == ("openai", "gpt-5.6-luna")`, `(provider_served, model_served) == ("openai", "gpt-5.6-luna-2026-08-01")`, `search_actions == 1`, `(input_tokens, output_tokens) == (8600, 300)`, `reasoning_tokens == 120`, `cost_usd == Decimal("0.012080")`, `price_version == "genai-prices==0.1.7;ovr:fee000000001"`, `usage_raw["pricing"] == "genai-prices"`, `usage_raw["sources"] == 3`, `usage_raw["citations"] == 2`, `usage_raw["response_id"] == "resp_s1"`.
19. `test_real_search_without_fee_override_raises_before_calling` — `StaticPriceBook(())` → `pytest.raises(PriceMissing)`; handler not called; `records == []`.
20. `test_real_search_error_is_recorded_and_reraised` — 503 → `pytest.raises(SearchProviderError)`; one row `status == CallStatus.ERROR`, `error_class == "SearchProviderError"`, `error_message.startswith("InternalServerError (HTTP 503)")`, `cost_usd == Decimal(0)`, `model_requested == "gpt-5.6-luna"`.
21. `test_mock_search_row_is_unchanged` — `mock_settings`, `FixtureSearchProvider(root=search_fixture_root)` → `price_version == "genai-prices==0.1.7"`, `cost_usd == Decimal("0")`, `model_requested == "fixture"`, `usage_raw == {"search_actions": 1, "sources": 2, "citations": 2}`.
22. `test_search_cost_row_is_committed_with_the_seeded_fee` — `clean_db` + `sessionmaker_committing`: `seed_defaults` committed; `run = add_run(sm)`; gateway with `CallRecorder(sm)`, `DbPriceBook(sm)`, provider over MockTransport, `clock=fixed_clock`; `search(SearchQuery(text="q"), ctx=CallContext(trace_id=run.trace_id, run_id=run.id))` → the committed `LlmCall` row has `kind == "search"`, `search_actions == 1`, `cost_usd == Decimal("0.012080")` (`> 0`), `re.fullmatch(r"genai-prices==0\.1\.7;ovr:[0-9a-f]{12}", price_version)`, `run_id == run.id`, `trace_id == run.trace_id`.

**Implementation notes** (verified with openai 3.14.1):
```python
response = await client.responses.create(
    model=self.model, instructions=SEARCH_INSTRUCTIONS, input=text,
    tools=[tool], tool_choice="required", include=["web_search_call.action.sources"],
    max_tool_calls=max_calls, store=False, timeout=SEARCH_TIMEOUT_SECONDS)
extra = response.model_extra or {}   # {"tool_usage": {"web_search": {"num_requests": 1}}}; {} when absent
for item in response.output:
    if item.type == "web_search_call" and item.action.type == "search":
        urls = [s.url for s in (item.action.sources or [])]
    elif item.type == "message":
        for part in item.content:
            if part.type == "output_text":
                cites = [a for a in part.annotations if a.type == "url_citation"]
```
`filters.blocked_domains` is not typed in the SDK and is not used.

**Verification**: red — `ModuleNotFoundError: No module named 'mdcopilot_blog.llm.search.openai'`, then gateway tests fail (`PriceMissing` not raised, cost `0`); green — `24 passed`; regression set green; lint clean.

**Acceptance covered**: CONTRACT §10.1 "`OpenAIWebSearchProvider` plain text with `max_tool_calls` — MockTransport test on recorded response shape"; §10.1 live broad scan "a `blog_llm_calls` row with `search_actions` and non-zero cost per search — PROV (cost row test)" (test 22); §5.5 `search(query, *, ctx)` bullet and "Search cost = token cost + `search_actions × per_1k_calls / 1000`"; RESEARCH_ARCHITECTURE §3.

### PROV-9: `GeminiEmbeddingProvider` and real-mode `embed`

**Files**
- create `pkg/llm/embeddings.py`, `backend/tests/providers/test_prov_embeddings.py`
- modify `pkg/llm/gateway.py` (`__init__`, `embed`), `backend/tests/unit/test_gateway.py`

**Interfaces**
- Produces (`embeddings.py`):
  ```python
  EMBED_BATCH_SIZE: Final = 100
  EMBED_TIMEOUT_SECONDS: Final = 30.0
  @dataclass(frozen=True)
  class EmbeddingBatch:
      vectors: list[list[float]]; provider: str; model: str; input_tokens: int
      usage_details: dict[str, str | int | None]
  class EmbeddingProvider(Protocol):
      name: str
      model: str
      async def embed(self, texts: Sequence[str], *, dimensions: int) -> EmbeddingBatch: ...
  class EmbeddingProviderError(RuntimeError):
      def __init__(self, provider: str, error_class: str, status_code: int | None, message: str,
                   retryable: bool) -> None: ...   # same str() and pickling as SearchProviderError
  def estimate_embedding_tokens(text: str) -> int: ...          # max(1, ceil(len(text) / 4))
  def batched(texts: Sequence[str], size: int) -> list[list[str]]: ...
  class GeminiEmbeddingProvider:
      name: str = "google"
      model: str
      def __init__(self, settings: Settings, *, http_client: httpx2.AsyncClient | None = None) -> None: ...
      async def embed(self, texts: Sequence[str], *, dimensions: int) -> EmbeddingBatch: ...
  ```
- Produces (`gateway.py`): `LLMGateway.__init__(…, embedding_provider: EmbeddingProvider | None = None)`; read-only properties `embedding_provider`, `search_provider`, `model_factory`.

**Provider rules**
1. Constructor (imports `ProviderNotAvailable` lazily): `settings.mock_mode` → `ProviderNotAvailable("real embedding clients cannot be built while BLOG_AGENT_MOCK_MODE is true")`; `choice = parse_choice(settings.embedding_model)`, `choice.provider != "google"` → `ProviderNotAvailable(f"embedding model must be a google: entry, got '{choice.ref()}'")`; `settings.gemini_api_key is None` → `ProviderNotAvailable("GEMINI_API_KEY is not set")`. `self.model = choice.model`.
2. Client, built once: `google.genai.Client(vertexai=False, api_key=<secret>, http_options=types.HttpOptions(httpx_async_client=http_client or httpx2.AsyncClient(timeout=httpx2.Timeout(EMBED_TIMEOUT_SECONDS)), retry_options=types.HttpRetryOptions(attempts=1), timeout=int(EMBED_TIMEOUT_SECONDS * 1000)))`. `HttpOptions.timeout` is required: without it the request has no timeout.
3. `embed(texts, dimensions=d)`: empty `texts` → `ValueError("texts must not be empty")`. Send `contents=[types.Content(parts=[types.Part(text=t)]) for t in texts]` (never a plain `list[str]`, which becomes one vector), `config=types.EmbedContentConfig(output_dimensionality=d)`. No `task_type`.
4. Shape check: `response.embeddings` is `None`, or its length differs from `len(texts)`, or any `values` is `None` or has length `!= d` → `EmbeddingProviderError("google", "UnexpectedEmbeddingShape", None, f"expected {len(texts)} vectors of {d} dimensions, got {…}", retryable=False)`. Vectors are returned as given (not normalised; pgvector cosine distance is scale-invariant).
5. Errors: `google.genai.errors.APIError` → `EmbeddingProviderError("google", type(exc).__name__, exc.code, <message ≤ 500 chars>, retryable=exc.code in {408, 429} or exc.code >= 500)`; `httpx2.TransportError` and `httpx.TransportError` → status `None`, `retryable=True`; other exceptions propagate.
6. The API returns no token usage, so `input_tokens = sum(estimate_embedding_tokens(t) for t in texts)`; `usage_details = {"token_source": "estimate_chars_div_4", "billable_character_count": response.metadata.billable_character_count if response.metadata else None}`; `provider="google"`, `model=self.model`.

**Gateway `embed` rules**
1. `texts` empty → return `[]` with no budget query, span, slot or row.
2. `choice = parse_choice(settings.embedding_model)`, `dims = settings.embedding_dimensions`; split with `batched(texts, EMBED_BATCH_SIZE)`; returned vectors keep input order.
3. Per batch: budget check (PROV-4), then:
   - Mock mode: inside span `embeddings` and slot `choice.provider`, `mock_embedding(t, dims)` per text; record FOUND/Phase 1's row shape (`provider_served="mock"`, `model_served="mock:embedding"`, `params={"dimensions": dims, "count": len(batch)}`, `input_tokens=sum(len(t.split()))`, cost 0).
   - Real mode: `self._embedding_provider is None` → `ProviderNotAvailable("no embedding provider is configured (needs GEMINI_API_KEY and a google: embedding model)")` before any span or row. Otherwise span, slot, `await provider.embed(batch, dimensions=dims)`; on exception `set_error`, record an error row (`kind embedding`, requested `choice.provider`/`choice.model`, `params`, cost 0) and re-raise (later batches are not sent; earlier rows stay). On success `priced = await price_embedding_call(book, provider=choice.provider, model=choice.model, input_tokens=batch.input_tokens, at=clock())`; record `provider_served=batch.provider`, `model_served=batch.model`, `input_tokens`, `cost_usd=priced.cost_usd`, `price_version=priced.price_version`, `usage_raw=batch.usage_details | {"pricing": priced.source}`, `params={"dimensions": dims, "count": len(batch)}`.
4. No fallback embedding model.

**Edit to `tests/unit/test_gateway.py`**: replace `test_embed_requires_mock_mode` with `test_embed_in_real_mode_without_provider_raises_before_recording`: `real = gw_settings.model_copy(update={"mock_mode": False, "gemini_api_key": SecretStr("gm-test")})`, gateway without `embedding_provider` → `pytest.raises(ProviderNotAvailable, match="no embedding provider")`; `recorder.records == []`; `recorder.cost_queries == [ctx.run_id]` (budget checked first).

**Tests to write first** (`test_prov_embeddings.py`, 17 tests; `real_settings` has `embedding_dimensions=3`, default `embedding_model` `google:gemini-embedding-2`; handler bodies `{"embeddings": [{"values": [float(int(text[1:])), 0.0, 0.0]} for each request entry]}` where texts are `"t000"`…)
1. `test_constructor_refuses_mock_mode`.
2. `test_constructor_rejects_non_google_model` — `embedding_model="openai:text-embedding-3-small"` → message `embedding model must be a google: entry, got 'openai:text-embedding-3-small'`.
3. `test_constructor_requires_key_even_with_env` — env `GEMINI_API_KEY` and `GOOGLE_API_KEY` set, settings key `None` → `GEMINI_API_KEY is not set`.
4. `test_request_shape` — handler returns two vectors of 1536 zeros; `embed(["alpha", "beta"], dimensions=1536)` → one request `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:batchEmbedContents`; body `== {"requests": [{"content": {"parts": [{"text": "alpha"}]}, "outputDimensionality": 1536, "model": "models/gemini-embedding-2"}, {"content": {"parts": [{"text": "beta"}]}, "outputDimensionality": 1536, "model": "models/gemini-embedding-2"}]}`; header `x-goog-api-key == "g-test"`; timeout extension `read == 30.0`.
5. `test_parses_vectors_and_estimates_tokens` — response `[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]` for `["alpha", "beta"]`, `dimensions=3` → `batch.vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]`, `provider == "google"`, `model == "gemini-embedding-2"`, `input_tokens == 3`, `usage_details == {"token_source": "estimate_chars_div_4", "billable_character_count": None}`.
6. `test_shape_mismatch_raises` — parametrize: one vector for two texts; two vectors of length 2 for `dimensions=3` → `EmbeddingProviderError` with `error_class == "UnexpectedEmbeddingShape"`, `retryable is False`. (2)
7. `test_api_errors_map` — parametrize `(503, "ServerError", True)`, `(429, "ClientError", True)`, `(400, "ClientError", False)` (body `{"error": {"code": status, "message": "bad", "status": "X"}}`) → `status_code == status`, `error_class`, `retryable`; one request. (3)
8. `test_timeout_maps_to_retryable_error` — handler raises `httpx2.ReadTimeout` → `error_class == "ReadTimeout"`, `status_code is None`, `retryable is True`; one request.
9. `test_embedding_provider_error_pickles`.
10. `test_estimate_embedding_tokens` — `""` → 1; `"abcd"` → 1; `"abcde"` → 2.
Gateway:
11. `test_real_embed_batches_and_prices_each_request` — `real_settings`, provider over MockTransport, `StaticPriceBook(())`, `FakeRecorder`, `clock=fixed_clock`; `texts = [f"t{i:03d}" for i in range(150)]` → two requests with 100 and 50 entries; `len(vectors) == 150` and `vectors[i][0] == float(i)` for all `i`; two rows, both `status ok`, `provider_requested == provider_served == "google"`, `model_requested == model_served == "gemini-embedding-2"`, `params == {"dimensions": 3, "count": 100}` then `{"dimensions": 3, "count": 50}`, `input_tokens == 100` then `50`, `cost_usd == Decimal("0.000020")` then `Decimal("0.000010")`, `price_version == "genai-prices==0.1.7"`, `usage_raw["pricing"] == "genai-prices"`.
12. `test_embed_empty_list_does_nothing` — mock: `await gateway.embed([], ctx=ctx) == []`, `records == []`, `budget_queries == []`.
13. `test_budget_checked_before_each_request` — `mock_settings` (cap 1.00), `FakeRecorder(spend_per_ok=Decimal("1.00"))`, 150 texts → `pytest.raises(BudgetExceeded)`; `len(records) == 1`; `len(budget_queries) == 2`.
14. `test_failed_request_stops_remaining_batches` — first request 200, second 503 → `pytest.raises(EmbeddingProviderError)`; rows `[ok, error]` with `records[1].error_class == "EmbeddingProviderError"`; exactly two requests for 250 texts.

**Implementation notes** (verified with google-genai 2.24.0):
```python
from google import genai
from google.genai import errors as genai_errors, types
client = genai.Client(vertexai=False, api_key=key, http_options=types.HttpOptions(
    httpx_async_client=httpx2.AsyncClient(timeout=httpx2.Timeout(30.0)),
    retry_options=types.HttpRetryOptions(attempts=1), timeout=30000))           # milliseconds
resp = await client.aio.models.embed_content(
    model="gemini-embedding-2",
    contents=[types.Content(parts=[types.Part(text=t)]) for t in texts],        # one vector per text
    config=types.EmbedContentConfig(output_dimensionality=dimensions))
vectors = [e.values for e in (resp.embeddings or [])]
# errors: genai_errors.APIError (.code); ServerError for 5xx, ClientError for 4xx; raw httpx2.ReadTimeout on timeout
```

**Verification**: red — `ModuleNotFoundError: No module named 'mdcopilot_blog.llm.embeddings'`; green — `17 passed`; regression set green (`tests/unit/test_gateway.py` `23 passed`, including `test_embed_is_deterministic_in_mock_mode` unchanged); lint clean.

**Acceptance covered**: CONTRACT §5.5 "`embed(texts, *, ctx)`: budget check first; real mode calls `GeminiEmbeddingProvider` (`gemini-embedding-2`, `output_dimensionality=settings.embedding_dimensions`), no fallback model; one `blog_llm_calls` row (kind `embedding`) per provider request with tokens and cost"; ARCHITECTURE §7 embeddings row.

### PROV-10: `build_gateway` wiring and optional price updates

**Files**
- modify `pkg/llm/gateway.py`
- create `backend/tests/providers/test_prov_build_gateway.py`

**Interfaces**
- `build_gateway(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession], prompts: PromptRegistry) -> LLMGateway` (signature frozen, body extended).
- Consumes: `RealModelFactory`, `OpenAIWebSearchProvider`, `GeminiEmbeddingProvider`, `DbPriceBook`, `process_limiter`, `ensure_price_updates`, FOUND's mock construction of `MockModelFactory`/`FixtureSearchProvider`.

**Behaviour rules**
1. `recorder=CallRecorder(sessionmaker)`, `model_factory=build_model_factory(settings)`, `price_book=DbPriceBook(sessionmaker)`, `limiter=process_limiter(settings.provider_concurrency)`, default clock.
2. Search provider: mock mode → exactly FOUND's construction (scenario roots included); real mode → `OpenAIWebSearchProvider(settings)`, and `UnavailableSearchProvider()` when that raises `ProviderNotAvailable` (no key, or no usable `openai` search route entry).
3. Embedding provider: mock mode → `None`; real mode → `GeminiEmbeddingProvider(settings)`, and `None` when it raises `ProviderNotAvailable`.
4. Calls `pricing.ensure_price_updates(settings)` on every build (it is idempotent and a no-op in mock mode or with the flag off).
5. Building touches no network and no database.

**Tests to write first** (`test_prov_build_gateway.py`, 4 tests; `sessionmaker = async_sessionmaker()` (unbound); `update_in_background` monkeypatched to a counter and `pricing._PRICE_UPDATER` reset to `None` in every test)
1. `test_mock_build_uses_fixtures_and_no_real_clients` — `mock_settings` → `isinstance(gw.model_factory, MockModelFactory)`, `isinstance(gw.search_provider, FixtureSearchProvider)`, `gw.embedding_provider is None`, `isinstance(gw.price_book, DbPriceBook)`, `gw.limiter is process_limiter(4)`, counter 0.
2. `test_real_build_with_all_keys` — `real_settings` → `RealModelFactory`, `OpenAIWebSearchProvider` with `model == "gpt-5.6-luna"`, `GeminiEmbeddingProvider` with `model == "gemini-embedding-2"`.
3. `test_real_build_without_keys_degrades` — `real_settings` with all three keys `None` → `isinstance(gw.search_provider, UnavailableSearchProvider)`, `gw.embedding_provider is None`, `isinstance(gw.model_factory, RealModelFactory)`.
4. `test_real_build_starts_price_updates_once_when_enabled` — `real_settings` with `price_auto_update=True`; build twice → counter 1; with `mock_settings` and the flag on → counter stays 0 (fresh reset).

**Implementation notes**: keep the lazy imports inside `build_model_factory`/`build_gateway` (import graph above).

**Verification**: red — `AttributeError: 'LLMGateway' object has no attribute 'search_provider'` or wrong isinstance; green — `4 passed`; regression set green; `tests/foundation/test_found_imports.py` green; lint clean.

**Acceptance covered**: CONTRACT §5.5 `build_model_factory` and `search` real-mode bullets; "`pydantic_ai.prices.update_in_background()` is called only when `settings.price_auto_update` is true (default false: frozen prices)".

### PROV-11: Spike S4, mocked half (route walking on the test database)

**Files**
- create `backend/tests/providers/test_prov_route_walking.py`, `docs/blog-agent/spikes/S4-route-walking.md` (mocked half section)

**Interfaces**
- Consumes everything above: `LLMGateway` in real mode with `RealModelFactory(real_settings, http_client_factory=mock_client_factory(handler_by_host(...)))`, `CallRecorder(sessionmaker_committing)`, `DbPriceBook(sessionmaker_committing)` (no rows), `clock=fixed_clock`, `add_run`, the response constants, `pricing.genai_token_cost`.

**Behaviour rules** (what the tests prove; no production code is expected to change in this task)
1. A 503, an `httpx2` timeout and invalid output each move the route to its next model.
2. Exactly one committed `blog_llm_calls` row per attempt, with `attempt_index`, `fallback_from`, `error_class`, requested and served provider/model, tokens, cost and `trace_id`.
3. `usage.cost` is populated for every code-default route model.
4. `FunctionModel` fixtures still work with `ALLOW_MODEL_REQUESTS=False`.

**Tests to write first** (6 tests, `clean_db` + `sessionmaker_committing` + `allow_model_requests` except test 5; rows read with `select(LlmCall).where(LlmCall.run_id == run.id).order_by(LlmCall.attempt_index)`; `now = datetime.now(UTC)` for expected SDK costs)
1. `test_s4_http_503_advances_and_records_each_attempt` — `route_override=["openai:gpt-5.6-sol", "google:gemini-3.8-flash"]`; openai 503, google `GOOGLE_OK` → `result.provider == "google"`; two rows: row 0 `(provider_requested, model_requested) == ("openai", "gpt-5.6-sol")`, `status == "error"`, `error_class == "ModelHTTPError"`, `attempt_index == 0`, `fallback_from is None`, `cost_usd == Decimal(0)`; row 1 `("google", "gemini-3.8-flash")`, `status == "ok"`, `attempt_index == 1`, `fallback_from == "openai:gpt-5.6-sol"`, `model_served == "gemini-3.8-flash-001"`, `cost_usd == genai_token_cost("google", "gemini-3.8-flash-001", TokenUsage(1000, 500), at=now)` and `> 0`, `price_version == "genai-prices==0.1.7"`; both rows `run_id == run.id`, `trace_id == run.trace_id`.
2. `test_s4_httpx2_timeout_advances` — `["google:gemini-3.8-flash", "anthropic:claude-sonnet-5"]`; google raises `httpx2.ReadTimeout` → rows: `error_class == "ReadTimeout"`; then `anthropic` ok, `model_served == "claude-sonnet-5-20260901"`, cost `> 0`.
3. `test_s4_invalid_output_advances_after_output_retries` — `["openai:gpt-5.6-sol", "google:gemini-3.8-flash"]`; openai returns `OPENAI_INVALID` → exactly 2 requests to `api.openai.com`; row 0 `error_class == "UnexpectedModelBehavior"`, `input_tokens == 2000`, `output_tokens == 100`, `cost_usd == genai_token_cost("openai", "gpt-5.6-sol-2026-08-01", TokenUsage(2000, 100), at=now)` and `> 0`; row 1 google ok.
4. `test_s4_every_attempt_failing_raises_route_exhausted` — both hosts 503 → `pytest.raises(RouteExhausted)` with `failures == [("openai:gpt-5.6-sol", "ModelHTTPError"), ("google:gemini-3.8-flash", "ModelHTTPError")]`; two error rows.
5. `test_s4_function_model_fixtures_work_with_requests_disallowed` — `monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)`; `mock_settings` gateway from `build_gateway(mock_settings, sessionmaker_committing, PromptRegistry.from_directory(default_prompt_root(), agents=["hello"]))`; hello spec (`AgentName.HELLO`, `prompt_name="hello/echo"`, output `message: str`, `word_count: int`) → success; one row `model_served == "mock:hello"`, `status == "ok"`.
6. `test_s4_every_default_route_model_has_a_price` — for every entry in `settings.route_values()` values (the root fixture resets routes to code defaults) plus `settings.embedding_model`: `choice = parse_choice(entry)`; `genai_token_cost(choice.provider, choice.model, TokenUsage(1000, 0 if embedding else 1000), at=datetime(2026, 9, 17, 1, 30, tzinfo=UTC))` is not `None` and `> 0` (models: gpt-5.6-luna, gemini-3.8-flash, gpt-5.6-terra, gpt-5.6-sol, claude-sonnet-5, gemini-3.5-flash-lite, gemini-embedding-2).

**`S4-route-walking.md` content after this task** (sections in this order):
1. Title `# Spike S4 — gateway route walking`.
2. Status line: `Status: mocked half complete (YYYY-MM-DD of the green run); cost half pending owner input (Live-go: S4 and provider keys)`.
3. `## Mocked half`: the exact pytest command used for `tests/providers/test_prov_route_walking.py`, its final output line copied verbatim, and a table `| Check | Test | Result |` with six rows, one per test 1–6, where "Check" is the rule the test proves (503 advances; timeout advances; invalid output advances; route exhausted records every attempt; FunctionModel with requests disallowed; every default route model has a genai-prices price) and "Result" is `pass`.
4. `## Cost half (live)`: `Pending. Script: backend/spikes/s4_route_cost.py (PROV-12). Cap $0.20.`

**Verification**: red — only if an earlier task regressed (these tests exercise PROV-1…PROV-10 together; any failure is fixed in the owning task's module); green — `6 passed`; lint clean.

**Acceptance covered**: CONTRACT §9 S4 mocked half ("503, `httpx2` timeout, invalid output each advance; one `blog_llm_calls` row per attempt; … `FunctionModel` with `ALLOW_MODEL_REQUESTS=False`"), the offline part of "`usage.cost` populated for every route model"; §10.1 "Spikes S2, S3, S4 — … `tests/providers` mocked route-walking tests"; IMPLEMENTATION_PLAN Phase 2 S4; FRAMEWORK_EVALUATION risk row "Gemini request timeouts surface as raw `httpx2` errors … Spike S4 tests this".

### PROV-12: Live spike tooling (S2, S3, S4 cost half) and pending reports

No paid call is made in this task. Scripts run only after the controller records `Live-go: S2|S3|S4` in `progress.md` (§9 rule 1).

**Files**
- create `backend/spikes/__init__.py` (docstring), `backend/spikes/_budget.py`, `backend/spikes/_report.py`, `backend/spikes/s2_openai_web_search.py`, `backend/spikes/s3_gemini.py`, `backend/spikes/s4_route_cost.py`
- create `backend/spikes/prompts/writer/s3_article_draft.v1.md`, `backend/spikes/prompts/deep_research/s3_research_packet.v1.md`, `backend/spikes/prompts/seo/s3_seo_package.v1.md`, `backend/spikes/prompts/editorial/s4_ping.v1.md`
- create `backend/tests/providers/test_prov_spike_helpers.py`
- create `docs/blog-agent/spikes/S2-openai-web-search.md`, `docs/blog-agent/spikes/S3-gemini.md`; modify `docs/blog-agent/spikes/S4-route-walking.md` (cost-half section)
- modify `.superpowers/sdd/phases-2-10/requests/prov.md`

**Interfaces**

`spikes/_budget.py`:
```python
LIVE_DB: Final = "mdcopilot_blog_live"
TOTAL_LIVE_CAP_USD: Final = Decimal("35.20")
GATE_CAPS: Final[Mapping[str, Decimal]] = {"S2": Decimal("1.50"), "S3": Decimal("0.50"), "S4": Decimal("0.20")}
SEARCH_CONTENT_TOKENS_PER_TOOL_CALL: Final = 30_000
SEARCH_WORST_OUTPUT_TOKENS: Final = 8_000
MAX_CONSECUTIVE_ERRORS: Final = 3
class LiveBudgetError(RuntimeError): ...
def require_live_env(env: Mapping[str, str]) -> Decimal: ...
def require_live_settings(settings: Settings) -> None: ...
def estimate_prompt_tokens(chars: int) -> int: ...                       # ceil(chars / 3)
def worst_case_agent_call(*, input_per_mtok: Decimal, output_per_mtok: Decimal, prompt_chars: int,
                          max_output_tokens: int, output_retries: int) -> Decimal: ...
def worst_case_search_call(*, input_per_mtok: Decimal, output_per_mtok: Decimal, max_tool_calls: int,
                           per_1k_calls: Decimal, query_chars: int) -> Decimal: ...
def worst_case_embedding_call(*, input_per_mtok: Decimal, texts: Sequence[str]) -> Decimal: ...
def remaining_budget(*, env_cap: Decimal, gate_cap: Decimal, gate_spent: Decimal, ledger_spent: Decimal) -> Decimal: ...
def run_cap(*, run_spent: Decimal, remaining: Decimal, worst_case: Decimal) -> Decimal: ...
def stop_reason(*, status: str, cost_usd: Decimal, consecutive_errors: int) -> str | None: ...
def per_mtok_prices(provider: str, model: str, *, at: datetime) -> tuple[Decimal, Decimal] | None: ...
async def gate_spent(sessionmaker: async_sessionmaker[AsyncSession], gate: str) -> Decimal: ...
async def ledger_spent(sessionmaker: async_sessionmaker[AsyncSession]) -> Decimal: ...
async def run_spent(sessionmaker: async_sessionmaker[AsyncSession], run_id: uuid.UUID) -> Decimal: ...
async def open_spike_run(sessionmaker: async_sessionmaker[AsyncSession], gate: str, *, today: date) -> BlogRun: ...
async def close_spike_run(sessionmaker: async_sessionmaker[AsyncSession], run_id: uuid.UUID, *, succeeded: bool, now: datetime) -> None: ...
def write_report(gate: str, markdown: str, *, now: datetime, results_dir: Path) -> Path: ...
```
`spikes/_report.py`:
```python
def percentile_nearest_rank(values: Sequence[int], p: float) -> int | None: ...
@dataclass(frozen=True)
class SearchCallRow:
    model: str; status: str; latency_ms: int; input_tokens: int; search_actions: int; cost_usd: Decimal
    citation_count: int; action_source_count: int; num_requests_source: str; context_size: str; max_tool_calls: int
@dataclass(frozen=True)
class SearchSummary:
    model: str; context_size: str; max_tool_calls: int; calls: int; ok: int; errors: int
    annotations_present_pct: int | None; sources_present_pct: int | None
    num_requests_mean: Decimal | None; num_requests_max: int | None; tool_usage_reported: int
    input_tokens_p50: int | None; input_tokens_p90: int | None; latency_ms_p50: int | None; latency_ms_p90: int | None
    cost_usd: Decimal
@dataclass(frozen=True)
class AgentCallRow:
    entry: str; prompt_name: str | None; status: str; model_served: str | None; input_tokens: int; output_tokens: int
    cost_usd: Decimal; price_version: str; latency_ms: int; requests: int; error_class: str | None
def search_call_row(call: LlmCall) -> SearchCallRow: ...
def agent_call_row(call: LlmCall) -> AgentCallRow: ...
def summarize_search_calls(rows: Sequence[SearchCallRow]) -> list[SearchSummary]: ...
def render_s2_markdown(summaries: Sequence[SearchSummary], *, run_id: uuid.UUID, started_at: datetime,
                       finished_at: datetime, stop: str | None, total_cost: Decimal) -> str: ...
def s3_contract_row(rows: Sequence[AgentCallRow]) -> str: ...
def render_s3_markdown(...) -> str: ...
def s4_entry_row(row: AgentCallRow) -> str: ...
def render_s4_markdown(...) -> str: ...
```
Each script module exposes `async def main(env: Mapping[str, str], settings: Settings) -> int` and ends with `if __name__ == "__main__": raise SystemExit(asyncio.run(main(os.environ, get_settings())))`.

**Budget helper rules**
1. `require_live_env`: `env.get("BLOG_LIVE_TESTS") != "1"` → `LiveBudgetError("BLOG_LIVE_TESTS=1 is required")`; missing `BLOG_LIVE_MAX_SPEND_USD` → `"BLOG_LIVE_MAX_SPEND_USD is required"`; not a finite decimal → `"BLOG_LIVE_MAX_SPEND_USD must be a decimal number"`; `<= 0` → `"BLOG_LIVE_MAX_SPEND_USD must be > 0"`; else the `Decimal`.
2. `require_live_settings`: `settings.postgres_db != LIVE_DB` → `LiveBudgetError("POSTGRES_DB must be mdcopilot_blog_live")`; `settings.mock_mode` → `LiveBudgetError("BLOG_AGENT_MOCK_MODE must be false")`.
3. `worst_case_agent_call`: `requests = output_retries + 1`; `input_tokens = requests * estimate_prompt_tokens(prompt_chars) + output_retries * max_output_tokens` (a retry resends the previous output); `output_tokens = requests * max_output_tokens`; `quantize_usd((input_tokens*input_per_mtok + output_tokens*output_per_mtok) / 1_000_000)`.
4. `worst_case_search_call`: `input_tokens = estimate_prompt_tokens(query_chars) + SEARCH_CONTENT_TOKENS_PER_TOOL_CALL * max_tool_calls`; `output_tokens = SEARCH_WORST_OUTPUT_TOKENS`; plus `max_tool_calls * per_1k_calls / 1000`; quantized.
5. `worst_case_embedding_call`: `sum(estimate_embedding_tokens(t)) * input_per_mtok / 1_000_000`, quantized.
6. `remaining_budget = min(env_cap, gate_cap - gate_spent, TOTAL_LIVE_CAP_USD - ledger_spent)`.
7. `run_cap`: `remaining <= worst_case` → `LiveBudgetError(f"remaining budget {remaining} USD is below one worst-case call {worst_case} USD")`; else `run_spent + remaining - worst_case`. The script sets the gateway's `max_cost_per_run_usd` to this value before each call, so the gateway's `BudgetExceeded` check (spent on the run `>=` cap) blocks before the remaining budget can be crossed (§9 rule 3).
8. `stop_reason`: `status == "ok" and cost_usd == 0` → `"paid call recorded cost_usd = 0 (unknown price)"`; `status == "error" and consecutive_errors >= MAX_CONSECUTIVE_ERRORS` → `"3 consecutive errors"`; else `None`.
9. `per_mtok_prices`: `genai_token_cost(provider, model, TokenUsage(1000, 0), at=at)` and `TokenUsage(0, 1000)`, each × 1000; `None` when either is `None`.
10. `gate_spent`: `SUM(blog_llm_calls.cost_usd)` joined to `blog_runs` where `blog_runs.params->>'spike' = gate`; `ledger_spent`: `SUM(cost_usd)` over all rows; `run_spent`: over `run_id`.
11. `open_spike_run`: inserts and commits `BlogRun(kind=RunKind.MANUAL.value, run_date=today, status=RunStatus.QUEUED.value, params={"spike": gate}, trace_id=new_trace_id())`; `close_spike_run` sets `status` to `SUCCEEDED`/`FAILED` and `finished_at=now` (spike rows only; no state machine; live database only).
12. `write_report` writes `results_dir / f"{gate}-{now:%Y%m%dT%H%M%SZ}.md"` (creating the directory) and returns the path. Scripts use `results_dir = Path(__file__).parent / "results"`.

**Report rules**
1. `percentile_nearest_rank(values, p)`: empty → `None`; else `sorted(values)[ceil(p * n) - 1]`.
2. `search_call_row` reads `usage_raw` keys `citation_count`, `action_source_count`, `num_requests_source`, `search_context_size`, `max_tool_calls` (0 / `""` when absent).
3. `summarize_search_calls` groups by `(model, context_size, max_tool_calls)` sorted by `(model, max_tool_calls)`. Percentages, means, maxima and percentiles use `ok` rows only; `*_pct = round_half_up(100 * count / ok)`; `num_requests_mean` quantized to `0.01`; `tool_usage_reported` counts ok rows whose source is `tool_usage`; `cost_usd` sums all rows. `ok == 0` → the ok-only fields are `None`.
4. `render_s2_markdown` starts with `# Spike S2 — OpenAI web search`, then run id, UTC start and finish, total cost and stop reason (`completed` when `None`), then the table header `| Model | Context | Max tool calls | Calls | OK | Errors | Annotations present | Sources present | num_requests mean | num_requests max | tool_usage reported | Input tokens P50 | Input tokens P90 | Latency P50 ms | Latency P90 ms | Cost USD |`, one row per summary; `None` renders `n/a`.
5. `s3_contract_row` (rows of one `prompt_name`): `| <prompt_name> | <runs> | <succeeded> | <sum(max(0, requests - 1))> | <sorted distinct error classes joined by ", " or "none"> | <round_half_up mean input> | <mean output> | <latency P50 over all rows> | <sum cost, 6 dp> |`.
6. `s4_entry_row`: `| <entry> | <status> | <model_served or n/a> | <input> | <output> | <cost 6 dp> | <price_version> | <latency_ms> |`.

**Script rules**
- Common, in this order, returning exit code 2 with one line `<gate>: <message>` on stdout: `require_live_env(env)`; `require_live_settings(settings)`; required keys present (`OPENAI_API_KEY` for S2; `GEMINI_API_KEY` for S3; S4 needs at least one key); engine from `make_engine(settings.database_url())`. S2 additionally needs the `(openai, web_search_call)` override effective now, else `S2: run scripts/live/prepare_db.sh first (search fee override missing)`. A `LiveBudgetError` raised later ends the loop with that stop reason. Every call goes through `LLMGateway` with `CallContext(trace_id=run.trace_id, run_id=run.id)`, `DbPriceBook`, `CallRecorder` on the live database, and a fresh `settings.model_copy(update={"max_cost_per_run_usd": run_cap(...)})` per call. After each call the script reads the newest row of the run and applies `stop_reason`. At the end: `close_spike_run`, render, `write_report`, print the report path and `total spend <x> USD`; exit 0 when completed, 1 when stopped early.
- **S2** (`s2_openai_web_search.py`): `MODELS = ("gpt-5.6-luna", "gpt-5.6-terra")`; `QUERIES`: the 20 queries listed under "S2 queries" below, in that order; for each model, queries 0–9 with `mode="broad"` (settings context `low`, `max_tool_calls` 1) and 10–19 with `mode="deep"` (`medium`, 2); provider `OpenAIWebSearchProvider(live_settings, model=model)`; worst case from `per_mtok_prices("openai", model, at=now)`, `per_1k_calls` of the fee row and `query_chars = len(query) + len(SEARCH_INSTRUCTIONS)`. `SearchProviderError`, `BudgetExceeded` and `PriceMissing` are caught and counted (the gateway already recorded provider errors). Report: `render_s2_markdown(summarize_search_calls([...rows of the run...]))`.
- **S3** (`s3_gemini.py`): `TOPIC = "Ambient AI scribes in outpatient clinics"`, `USER_PROMPT = "Return the structured output now."`, route override `["google:gemini-3.8-flash"]`, prompts from `PromptRegistry.from_directory(Path(__file__).parent / "prompts")`, three runs of each spec: `AgentSpec(name=AgentName.WRITER, version="s3", prompt_name="writer/s3_article_draft", output_type=ArticleDraft, max_output_tokens=4500, reasoning="medium")`, `AgentSpec(name=AgentName.DEEP_RESEARCH, version="s3", prompt_name="deep_research/s3_research_packet", output_type=ResearchPacket, max_output_tokens=8000, reasoning="medium")`, `AgentSpec(name=AgentName.SEO, version="s3", prompt_name="seo/s3_seo_package", output_type=SeoPackage, max_output_tokens=3000, reasoning="minimal")`; worst case with `prompt_chars = len(rendered.text) + len(USER_PROMPT)` and `output_retries=1`; `RouteExhausted` is caught and counted. Then one embedding call through the gateway (`GeminiEmbeddingProvider(live_settings)`) on five fixed healthcare sentences, checking 5 vectors of `settings.embedding_dimensions` values; then an unbilled `countTokens` calibration outside the gateway (`google.genai.Client(...).aio.models.count_tokens(model="gemini-embedding-2", contents=<the five texts>)`), recording `total_tokens` against the chars/4 estimate, or `countTokens unsupported: <exception class>`. The report has one row per spec (`s3_contract_row`), the embedding table, and an "Owner reads in AI Studio" table with rows `Billing tier`, `gemini-3.8-flash RPM`, `gemini-3.8-flash TPM`, `gemini-3.8-flash RPD` whose values the implementer copies from the owner's reply (or `pending owner`).
- **S4** (`s4_route_cost.py`): entries = distinct values of `settings.route_values()` in first-appearance order, skipping entries whose key is missing (reported `skipped: <ENV> missing`); spec `AgentSpec(name=AgentName.EDITORIAL, version="s4", prompt_name="editorial/s4_ping", output_type=PingOut, max_output_tokens=1000, reasoning="low")` with `class PingOut(BaseModel): ok: bool; note: str`; `route_override=[entry]`, variables `{"topic": "route walking"}`; then one `embed(["route walking cost check"])` when `GEMINI_API_KEY` is set. An ok row with `cost_usd == 0` stops the script at once and the report names that entry as `price missing`. Report: `render_s4_markdown` with `s4_entry_row` per call.

**Spike prompt files** (front matter keys as in `backend/prompts/hello/echo.v1.md`; each declares `variables: [topic]` and uses only `{{ topic }}`):
- `writer/s3_article_draft.v1.md` (`output: ArticleDraft`): "You are testing structured output. Write a blog article of 900 to 1100 words about "{{ topic }}" for US healthcare operations leaders. Return exactly seven sections with keys in this order: introduction, context, core_argument, evidence, mdcopilot_perspective, practical_implications, conclusion. The introduction has a null heading; every other section has a short heading. Section bodies are Markdown paragraphs with no # headings. Give three title options (provocative, operational, visionary), a pull quote, a call to action, an excerpt of at most 500 characters, and an empty resolutions list."
- `deep_research/s3_research_packet.v1.md` (`output: ResearchPacket`): "You are testing structured output. Build a research packet about "{{ topic }}" from these sources, citing them only by marker: S1, a health system press release on ambient documentation pilot results; S2, a professional society survey on physician burnout; S3, a regulator page summarising a digital health advisory committee meeting. Use only the markers S1, S2 and S3. Fill every field; sourceRefs may be an empty list."
- `seo/s3_seo_package.v1.md` (`output: SeoPackage`): "You are testing structured output. Produce SEO metadata and social copy for a blog article titled "{{ topic }}". The SEO title has at most 60 characters, the meta description 120 to 160 characters, and the slug only lowercase letters, digits and hyphens. internalLinkSuggestions and externalReferences may be empty lists."
- `editorial/s4_ping.v1.md` (`output: PingOut`): "Reply with ok set to true and a note of at most ten words about {{ topic }}."

**S2 queries** (in order): 1 `FDA AI-enabled medical device authorizations this month`; 2 `CMS prior authorization final rule artificial intelligence`; 3 `ambient AI clinical documentation health system results`; 4 `physician burnout survey 2026 documentation time`; 5 `ONC HTI rule decision support interventions update`; 6 `hospital AI governance committee announcement`; 7 `generative AI patient portal message drafting study`; 8 `AI sepsis prediction model validation news`; 9 `payer AI claims denial lawsuit news`; 10 `digital health funding round AI clinical workflow`; 11 `peer-reviewed study large language model clinical note accuracy`; 12 `FDA guidance predetermined change control plan AI devices`; 13 `Joint Commission responsible use of AI in healthcare guidance`; 14 `AI radiology triage randomized trial results`; 15 `state law AI disclosure patient communications healthcare`; 16 `Medicare Advantage algorithm coverage decisions oversight`; 17 `AI nurse staffing scheduling hospital pilot outcomes`; 18 `EHR vendor generative AI feature rollout clinicians`; 19 `AI medical coding accuracy audit findings`; 20 `WHO guidance large multimodal models health`.

**Tests to write first** (`test_prov_spike_helpers.py`, 29 tests; no live database, no network)
1. `test_require_live_env_rejects` — parametrize `({}, "BLOG_LIVE_TESTS=1 is required")`, `({"BLOG_LIVE_TESTS": "0"}, same)`, `({"BLOG_LIVE_TESTS": "1"}, "BLOG_LIVE_MAX_SPEND_USD is required")`, `({"BLOG_LIVE_TESTS": "1", "BLOG_LIVE_MAX_SPEND_USD": "abc"}, "BLOG_LIVE_MAX_SPEND_USD must be a decimal number")`, `({"BLOG_LIVE_TESTS": "1", "BLOG_LIVE_MAX_SPEND_USD": "0"}, "BLOG_LIVE_MAX_SPEND_USD must be > 0")`. (5)
2. `test_require_live_env_returns_cap` — `"1.25"` → `Decimal("1.25")`.
3. `test_require_live_settings_rejects` — parametrize `(postgres_db="mdcopilot_blog_prov_test", mock_mode=False) → "POSTGRES_DB must be mdcopilot_blog_live"`, `(postgres_db="mdcopilot_blog_live", mock_mode=True) → "BLOG_AGENT_MOCK_MODE must be false"`. (2)
4. `test_require_live_settings_accepts_live_real_settings` — returns `None`.
5. `test_remaining_budget` — `env_cap=1.25, gate_cap=1.50, gate_spent=0.40, ledger_spent=34.50` → `Decimal("0.70")`.
6. `test_worst_case_agent_call` — `(4, 20, prompt_chars=3000, max_output_tokens=4500, output_retries=0)` → `Decimal("0.094000")`; same with `output_retries=1` → `Decimal("0.206000")`.
7. `test_worst_case_search_call` — `(0.2, 1.2, max_tool_calls=2, per_1k_calls=10, query_chars=90)` → `Decimal("0.041606")`.
8. `test_worst_case_embedding_call` — `(0.2, ["abcd", "abcdefgh"])` → `Decimal("0.000001")`.
9. `test_run_cap` — `(run_spent=0.10, remaining=0.70, worst_case=0.094)` → `Decimal("0.706")`; `(0, 0.05, 0.094)` → `LiveBudgetError("remaining budget 0.05 USD is below one worst-case call 0.094 USD")`.
10. `test_stop_reason` — parametrize `("ok", 0, 0) → "paid call recorded cost_usd = 0 (unknown price)"`, `("ok", Decimal("0.01"), 0) → None`, `("error", 0, 2) → None`, `("error", 0, 3) → "3 consecutive errors"`. (4)
11. `test_per_mtok_prices` — `("openai", "gpt-5.6-luna", at=2026-09-17T01:30Z)` → `(Decimal("0.2"), Decimal("1.2"))` (Decimal equality); `("fixture", "x")` → `None`.
12. `test_percentile_nearest_rank` — `[10, 20, 30, 40, 50]`: p 0.5 → 30, p 0.9 → 50; `[]` → `None`.
13. `test_summarize_search_calls` — model `gpt-5.6-luna`, context `low`, max 1; ok rows (latency, input, actions, citations, action sources, source, cost): `(1000, 8000, 1, 2, 3, "tool_usage", "0.01")`, `(2000, 9000, 1, 0, 4, "tool_usage", "0.02")`, `(3000, 10000, 2, 1, 0, "output_items", "0.03")`; one error row `(500, 0, 0, 0, 0, "", "0")` → one summary `calls=4, ok=3, errors=1, annotations_present_pct=67, sources_present_pct=67, num_requests_mean=Decimal("1.33"), num_requests_max=2, tool_usage_reported=2, input_tokens_p50=9000, input_tokens_p90=10000, latency_ms_p50=2000, latency_ms_p90=3000, cost_usd=Decimal("0.06")`.
14. `test_render_s2_markdown` — the test-13 summary → output starts with `# Spike S2 — OpenAI web search` and contains the line `| gpt-5.6-luna | low | 1 | 4 | 3 | 1 | 67% | 67% | 1.33 | 2 | 2 | 9000 | 10000 | 2000 | 3000 | 0.060000 |`.
15. `test_s3_contract_row` — rows for `writer/s3_article_draft`: `(ok, in 800, out 3900, latency 18000, cost 0.015, requests 1)`, `(ok, 1000, 4100, 20000, 0.016, 2)`, `(error "UnexpectedModelBehavior", 900, 4000, 22000, 0.014, 2)` → `| writer/s3_article_draft | 3 | 2 | 2 | UnexpectedModelBehavior | 900 | 4000 | 20000 | 0.045000 |`.
16. `test_s4_entry_row` — `AgentCallRow(entry="openai:gpt-5.6-sol", prompt_name="editorial/s4_ping", status="ok", model_served="gpt-5.6-sol-2026-08-01", input_tokens=120, output_tokens=40, cost_usd=Decimal("0.00128"), price_version="genai-prices==0.1.7", latency_ms=900, requests=1, error_class=None)` → `| openai:gpt-5.6-sol | ok | gpt-5.6-sol-2026-08-01 | 120 | 40 | 0.001280 | genai-prices==0.1.7 | 900 |`.
17. `test_spike_prompts_parse` — `PromptRegistry.from_directory(Path(__file__).resolve().parents[2] / "spikes" / "prompts")` template names `== {"writer/s3_article_draft", "deep_research/s3_research_packet", "seo/s3_seo_package", "editorial/s4_ping"}`; each renders with `{"topic": "x"}`.
18. `test_spike_scripts_refuse_without_live_env` — parametrize `spikes.s2_openai_web_search`, `spikes.s3_gemini`, `spikes.s4_route_cost`: `await module.main({}, settings) == 2`; captured stdout contains `BLOG_LIVE_TESTS=1 is required`. (3)
19. `test_spend_queries` (`clean_db` + `sessionmaker_committing`, test database) — `open_spike_run(sm, "S2")` with calls `0.30`, `0.20`; `open_spike_run(sm, "S3")` with `0.05`; `add_run` with `1.00` → `gate_spent("S2") == Decimal("0.50")`, `gate_spent("S3") == Decimal("0.05")`, `ledger_spent() == Decimal("1.55")`, `run_spent(<S2 run>) == Decimal("0.50")`.

**Reports written in this task (no live results yet)**
- `docs/blog-agent/spikes/S2-openai-web-search.md`: title `# Spike S2 — OpenAI web search`; line `Status: pending owner input (OPENAI_API_KEY and Live-go: S2)`; sections "What it measures" (the §9 S2 list), "How to run" (commands below), "Built without the key" (the PROV-8 test file, its final pytest line and date), "Results" (`None yet.`).
- `docs/blog-agent/spikes/S3-gemini.md`: `# Spike S3 — Gemini project`; `Status: pending owner input (GEMINI_API_KEY on a billed project, AI Studio limits read by the owner, and Live-go: S3)`; same sections, with the PROV-7 Google and PROV-9 test evidence.
- `S4-route-walking.md` "Cost half (live)": `Pending owner input (Live-go: S4; OPENAI_API_KEY, GEMINI_API_KEY; ANTHROPIC_API_KEY optional)`, plus the command.
- Append to `.superpowers/sdd/phases-2-10/requests/prov.md`: `Request: Live-go S2, S3, S4 — PROV spike tooling is ready (backend/spikes); needs OPENAI_API_KEY, GEMINI_API_KEY on a billed project, the owner's AI Studio tier and gemini-3.8-flash RPM/TPM/RPD reading, and scripts/live/prepare_db.sh run; caps $1.50 / $0.50 / $0.20.`

**Live commands** (only after the matching `Live-go:` line; set `<cap>` to the smaller of the gate's remaining cap and $35.20 minus the live ledger sum, §9 rule 2):
```bash
scripts/live/prepare_db.sh
docker compose run --rm -e POSTGRES_DB=mdcopilot_blog_live -e BLOG_AGENT_MOCK_MODE=false -e BLOG_LIVE_TESTS=1 \
  -e BLOG_LIVE_MAX_SPEND_USD=<cap> -e PYTHONDONTWRITEBYTECODE=1 tools python -m spikes.s2_openai_web_search
# same form with spikes.s3_gemini and spikes.s4_route_cost
```
After each run: copy the printed report file (`backend/spikes/results/<gate>-<timestamp>.md`) into the gate's doc under "Results", set the status line to `Status: complete (YYYY-MM-DD of the run)`, and append `Live: <gate> — <calls> calls — $<spend> — docs/blog-agent/spikes/<file>` to `requests/prov.md`.

**Implementation notes**: `python -m spikes.<module>` works because `/app` (backend) is the working directory and `spikes/__init__.py` exists; pytest imports `spikes` the same way (rootdir `backend/` is on `sys.path` since `tests/__init__.py` exists). Spikes are not application code, so `s3_gemini.py` may import `google.genai` directly for the unbilled `countTokens` call.

**Verification**: red — `ModuleNotFoundError: No module named 'spikes'`; green — `29 passed`; lint gate (includes `spikes`) clean. No live command is run in this task.

**Acceptance covered**: CONTRACT §9 gates S2, S3, S4 (tooling, caps enforced before each call, stop on `cost_usd = 0`, live database only, pending reports and `Request:` line when inputs are missing), rules 1–7; D9 (spike rows carry a dedicated run); §10.1 "Spikes S2, S3, S4 — spike reports (§9)"; IMPLEMENTATION_PLAN Phase 2 spikes.

### PROV-final: track verification

**Files**: none new; the track report lists every owned file changed and the red/green evidence of PROV-1…PROV-12.

**Commands and expected results** (all Docker, from `mdcopilot-blog/`)
1. Import gate:
   ```bash
   docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_prov_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
   ```
   → all passed.
2. Track suite:
   ```bash
   docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_prov_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/providers
   ```
   → `175 passed` (18 + 7 + 6 + 11 + 27 + 6 + 20 + 24 + 17 + 4 + 6 + 29), no failures, errors or skips.
3. Edited Phase 1 tests and regression set:
   ```bash
   docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_prov_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/unit/test_gateway.py tests/unit/test_routes.py tests/db/test_recorder.py tests/unit/test_search_fixture.py tests/db/test_seed.py tests/foundation tests/workflows/test_hello_pipeline.py tests/api/test_rbac_routes.py
   ```
   → all passed (`tests/unit/test_gateway.py` contributes 23, `tests/db/test_recorder.py` 3).
4. Lint and types:
   ```bash
   docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c \
     "ruff check --no-cache src/mdcopilot_blog/llm spikes tests/providers tests/unit/test_gateway.py && ruff format --check --no-cache src/mdcopilot_blog/llm spikes tests/providers tests/unit/test_gateway.py && mypy --cache-dir=/tmp/mypy --follow-imports=silent src/mdcopilot_blog/llm spikes"
   ```
   → `All checks passed!`, `… files already formatted`, `Success: no issues found in … source files`.
5. Network guard spot check: `grep -rn "AsyncOpenAI(\|AsyncAnthropic(\|genai.Client(\|GoogleProvider(" backend/tests/providers` shows only constructions that receive a MockTransport client or run inside `pytest.raises(ProviderNotAvailable)`.
6. A reviewer re-runs commands 2–3 with `BLOG_TEST_DB=mdcopilot_blog_prov_review_test`.

**Acceptance mapping**

| Contract item | Where proven |
|---|---|
| §10.1 Spikes S2, S3, S4 | PROV-11 (S4 mocked half, `S4-route-walking.md`); PROV-12 (scripts, caps, pending reports, `Request:` line); live results after `Live-go:` |
| §10.1 Provider adapters: request shape, SDK retries off, 503/timeout advance | PROV-7 tests 6–8; PROV-11 tests 1–3 |
| §10.1 Routing, pricing (genai-prices + override search fee), run cost cap; override price used; `price_version` format; `BudgetExceeded` before run/search/embed | PROV-5, PROV-6, PROV-8 tests 18–19, PROV-4 tests 7–11, PROV-9 test 13 |
| §10.1 `OpenAIWebSearchProvider` plain text with `max_tool_calls` | PROV-8 tests 5–13 |
| §10.1 seed YAML (`blog_price_overrides`, PROV) | PROV-5 tests 19–20 |
| §10.1 live broad scan: row with `search_actions` and non-zero cost per search (PROV cost row test) | PROV-8 test 22 |
| §10.4 vendor independence: route override behaviour | PROV-7 test 9 (keys filter `route_override`); FOUND's mock `provider_served` test stays green (regression set) |
| §10.4 live evaluation (Also PROV) | real providers, pricing and caps ready for QUAL's W5 run (PROV-7…PROV-10) |
| §10.8 `gen_ai` spans: PROV `llm_span` calls | PROV-3 |
| §10.8 every row has `trace_id` (PROV) | PROV-4 test 6; PROV-8 test 22 and PROV-11 test 1 assert the run's `trace_id` |
| §5.5 `build_model_factory` real clients, `ModelSettings`, reasoning mapping, mock-mode guard | PROV-1, PROV-7 tests 1–4, PROV-8 test 1, PROV-9 test 1 |
| §5.5 `ADVANCE_ERRORS` unchanged; `ALLOW_MODEL_REQUESTS` error never advances | Phase 1 `test_allow_model_requests_error_is_reraised_not_advanced` (kept); PROV-7 test 10 |
| §5.5 `embed`: budget first, Gemini, no fallback, one row per provider request | PROV-9 tests 11–14; `test_gateway.py` embed tests |
| §5.5 `search` real mode details (context size, filters, `tool_choice`, `include`, `max_tool_calls`, `store`, citations, sources, `num_requests`) | PROV-8 tests 5–13 |
| §5.5 cost lookup order, search cost, `price_version` ≤ 53 chars, `update_in_background` only when enabled | PROV-5 tests 9, 12–14, 16; PROV-10 test 4 |
| §5.5 per-provider concurrency shared by run/search/embed | PROV-2 |
| §5.5 / D10 budget scope, four named PROV tests | PROV-4 tests 7–10 |
| D9 spike rows | PROV-12 rule 11 (dedicated spike run rows) |
| §9 live-spend rules 1–7 | PROV-12 budget helper rules and tests 1–11, 18–19 |
| INVENTORY §16 item 4 (real providers unbuilt, no limiter, `embed()` unbudgeted) | PROV-2, PROV-4, PROV-7, PROV-9 |

**Done means**: commands 1–4 green; S2/S3 docs `pending owner input` or complete; S4 mocked half complete; `requests/prov.md` holds the `Live-go` request. The track is "complete, pending owner input (Live-go S2/S3/S4, keys)" until the live runs (§9 rule 7).

---

## Open issues for the controller (also returned to the orchestrator)
1. Output name: this plan is written to `PROV.md` as assigned; CONTRACT §2.2 names `prov.md`. On macOS's case-insensitive filesystem they are one file; on a case-sensitive checkout they differ.
2. CONTRACT §8.2 lint paths say `backend/spikes`; inside the `tools` container (working directory `backend/`) the path is `spikes`, which this plan uses.
3. Search model per mode: `search(query, *, ctx)` is frozen and `search_route` is one list, so broad, deep and verification searches use the same model (first `openai` entry, default `gpt-5.6-luna`). The research notes suggest `gpt-5.6-terra` for deep research; a per-mode model needs a settings field and a ruling (S2 measures both).
4. Gemini embeddings return no token usage (google-genai 2.24.0 `EmbedContentResponse`), so embedding rows use an estimate (`ceil(chars / 4)`, `usage_raw.token_source`); S3 calibrates it with `countTokens`. CONTRACT §5.5 says "with tokens and cost".
5. The backend image has google-genai 2.24.0 (DEPS/p1facts cite 2.23.0). Gotchas pinned in this plan: a `list[str]` passed to `embed_content` yields one vector for `gemini-embedding-2`; `HttpOptions.timeout=None` means no timeout.
6. `EMBED_BATCH_SIZE = 100` requests per `batchEmbedContents` call is an assumption not checked against Google's limit; S3 records it.
7. Real-mode search fails closed with `PriceMissing` (no call, no row) when no `(openai, web_search_call)` override is effective; the contract does not say what happens without the row.
8. Partial price overrides: `PriceOverrideCreate` (OBS) accepts any one price; PROV applies a model override only when every non-zero token component has a price, otherwise the lookup falls through to the next key or genai-prices. OBS/UI may want to explain this in the Settings form.
9. Mock mode keeps Phase 1 costs (SDK cost or fixture cost; no overrides, no genai-prices lookups), so mock runs record `0` cost; OBS tests that need non-zero costs must insert rows directly.
10. New public names other tracks may use: `pricing.PriceMissing`, `search.openai.SearchProviderError` and `embeddings.EmbeddingProviderError` (both with `retryable`, useful for RES's retry-with-backoff), `LLMGateway` keyword parameters `price_book`, `embedding_provider`, `limiter`, `clock` (defaults keep Phase 1 constructor calls working) and read-only properties.
11. `BudgetExceeded` message becomes `run <id> (attempt <id>) has spent <x> USD; the cap is <cap> USD`; tests matching `cap is … USD` keep passing.
12. If a FOUND foundation test's fake recorder overrides only `run_cost`, the budget switch in PROV-4 breaks it; PROV files a `Request:` rather than editing FOUND files.
13. `price_overrides.yaml` `effective_from` format (quoted string or YAML date) depends on FOUND's loader; PROV-5 test 20 decides.
14. Google `thinkingConfig` is sent with the snake-case key `thinking_level` (observed wire output of pydantic-ai 2.43 + google-genai 2.24); acceptance by the live API, and `thinking_level` support on `gemini-3.5-flash-lite`, are confirmed only by S3/S4 live runs. A systematic 400 would silently advance every SEO call to its fallback model.
15. `anthropic_effort` has no `minimal`; PROV maps `minimal` to `low` for Anthropic route entries.
16. `embed([])` now returns `[]` without a row (Phase 1 recorded a zero-count row).
