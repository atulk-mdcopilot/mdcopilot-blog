# Architecture — MDCopilot Blog Intelligence (`mdcopilot-blog`)

Status: Phase 0 proposal, waiting for owner approval (no application code exists yet)
Date: 2026-09-17 (revised after an independent three-lens review)
Companion docs: [FRAMEWORK_EVALUATION.md](FRAMEWORK_EVALUATION.md) · [RESEARCH_ARCHITECTURE.md](RESEARCH_ARCHITECTURE.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

## Summary

`mdcopilot-blog` is a standalone, Docker-only application. It has four parts: a FastAPI API, a DBOS worker, its own PostgreSQL 16 + pgvector database, and a Vite/React dashboard.

Every morning a durable DBOS workflow runs these stages:
1. It gathers fresh AI + healthcare news from curated feeds and official APIs, OpenAI web search, and direct page fetches, and records each source in a dated source ledger.
2. Typed Pydantic AI agents synthesise the research and propose three topics.
3. Deterministic code checks the topics for novelty against our own history and MDCopilot's published posts, then scores them.
4. The agents research the chosen topic in depth, write the article, fact-check it, run clinical and editorial review, revise it once, fact-check the final text again, and add SEO.
5. Quality gates run, and the workflow **stops at `READY_FOR_REVIEW`**.

A human then edits, regenerates parts, approves, schedules or rejects the article. Publishing works in two ways:
- **Manual export (default):** produces Quill-compatible HTML to paste into the existing MDCopilot admin editor.
- **API publisher (off by default):** calls MDCopilot's `POST /api/v1/admin/blogs` against a local dev backend.

Every run, step attempt, LLM/search call, cost, source and article version is stored in our own tables. Estimated run time is **~7–12 minutes** and estimated cost is **~$1.25 per article** (range ~$0.90–2.40). Measured values replace both estimates after the first real runs.

## 1. Context and constraints

| Constraint | Source | Consequence |
|---|---|---|
| Must not modify `mdcopilot-backend` / `mdcopilot-frontend`, or read their DB | Spec §2, Rule 9 | Integration only over MDCopilot's HTTP API |
| Docker only; no Python on the host | Owner, 2026-09-17 | Every build, test, migration and CLI runs via `docker compose` |
| Guaranteed keys: OpenAI + Gemini; Anthropic optional; no paid search key | Owner, 2026-09-17 | OpenAI web search does the searching; Gemini does most of the reasoning |
| Publishing: manual handoff now, API later | Owner, 2026-09-17 | Production MDCopilot login requires MFA and has no service token, so the API publisher targets a **local dev** backend only |
| Content strategy: spec §8–9 now, Gemini conversation later | Owner, 2026-09-17 | Brand, pillars, themes and voice are **database settings** seeded from the spec |
| No git workflow in this project | Spec Rule 10 | No branches, commits or pushes by the agent |
| Human approval mandatory; no auto-publishing | Spec §24, §58 | Enforced in the state machine and API. Auto-publish does not exist in this release. |

**Publish-target facts.** These were read from the sibling repos, which were not modified.

`POST /api/v1/admin/blogs` and `PUT /api/v1/admin/blogs/{id}` take:

| Field | Type / limit |
|---|---|
| `title` | ≤200 |
| `slug` | ≤200, unique |
| `content` | HTML |
| `excerpt` | ≤500 |
| `featured_image` | |
| `status` | `draft` or `published` |

Behaviour to design around:
- `content` is **HTML**: it comes from Quill 1.3.7 and is rendered through DOMPurify on the frontend. The backend stores it unsanitised.
- A duplicate slug returns a validation error.
- `PUT` with `title` but no `slug` **regenerates the slug**.
- `GET /admin/blogs?search=` matches title, excerpt and content only, **not slug**. It returns pages of 50, newest first.
- The public `GET /api/v1/blogs` needs no auth.
- Admin auth accepts cookie or bearer. The access token is issued **only as an HttpOnly cookie** that lasts 15 minutes, and password login starts an OTP challenge unless an admin setting disables it.
- There are no SEO, tag or category columns.
- The public post URL is `<site>/blog/{slug}`.

## 2. System overview

```text
 ┌──────────────── Browser (internal users) ────────────────┐
 │ Dashboard(Today) · Ideas · Research · Drafts · Review ·   │
 │ Published · Topics · Calendar · Sources · Settings · Runs │
 └───────────────────────────┬───────────────────────────────┘
                             │ same origin (/ and /api)
 ┌───────────────────────────▼───────────────────────────────┐
 │ web: nginx (prod) / Vite dev server (dev) → proxies /api  │
 └───────────────────────────┬───────────────────────────────┘
 ┌───────────────────────────▼───────────────────────────────┐
 │ api: FastAPI — auth/RBAC · CRUD · human actions ·          │
 │      DBOSClient (enqueue/fork/cancel/list) · metrics       │
 └───────────────┬───────────────────────────────┬───────────┘
                 │ SQL (schema app)              │ enqueue
 ┌───────────────▼───────────────┐   ┌───────────▼───────────┐
 │ db: Postgres 16 + pgvector    │◄──┤ worker: DBOS.launch() │
 │  schema app  (Alembic)        │   │ workflows · queues ·  │
 │  schema dbos (DBOS system)    │   │ schedules · steps     │
 └───────────────────────────────┘   └───┬───────┬───────┬───┘
                     ┌───────────────────▼┐ ┌────▼─────────┐ ┌▼───────────────┐
                     │ research/          │ │ llm/ gateway │ │ publishing/    │
                     │ query plan · feeds │ │ agents ·     │ │ manual export ·│
                     │ fetch · extract ·  │ │ web search · │ │ MDCopilot API  │
                     │ ledger · tiers     │ │ embeddings   │ │ (flag, off)    │
                     └─────────┬──────────┘ └────┬─────────┘ └───────┬────────┘
                               ▼                 ▼                   ▼
                    public web / feeds   OpenAI · Gemini ·     MDCopilot backend
                                         (Anthropic)           (local dev; public
                                                                read API for sync)
```

## 3. Runtime topology (Docker Compose)

The stack is one `compose.yaml` with project name `mdcopilot-blog`. Host ports bind to `127.0.0.1` only and avoid the ports used by the existing local stacks (3000, 8000, 8100, 5433, 5434, 6379, 9000/9001, 7001–7003, 5103, 5109, 5380).

| Service | Image / build | Command | Host port | Notes |
|---|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` (digest-pinned) | postgres | `127.0.0.1:5440` | Volume `blog_pgdata`; `pg_isready` healthcheck. pg16 is what DBOS's own tooling uses. |
| `migrate` | `backend` (`dev`) | `python -m mdcopilot_blog.cli migrate` (Alembic upgrade, DBOS system migrations, seed, prompt sync) | — | One-shot. `api`/`worker` wait for `service_completed_successfully`. |
| `api` | `backend` | `uvicorn --factory mdcopilot_blog.api.app:create_app` (`--reload` + bind mount in dev) | `127.0.0.1:8300` | **Never calls `DBOS.launch()`**. Uses `DBOSClient` only. |
| `worker` | `backend` | `python -m mdcopilot_blog.worker` | — | `DBOS.launch()` with fixed `executor_id` (`WORKER_EXECUTOR_ID=worker-1`) and explicit `application_version` (`APP_VERSION`). `stop_grace_period: 60s` (`DBOS.destroy` waits up to 25 s). Healthcheck on a heartbeat file. `extra_hosts: host.docker.internal:host-gateway` for the dev publisher. |
| `web` | `frontend` (`dev`: Vite; `prod`: nginx) | — | `127.0.0.1:8310` | Proxies `/api` to `api:8000`, so the app is same-origin. Vite `server.allowedHosts` includes `web` for container browsers. |
| `tools` | `backend` `dev` target | `uv …`, `pytest …`, CLI | — | Profile `tools`, e.g. `docker compose run --rm tools pytest` |
| `phoenix` | Arize Phoenix | — | `127.0.0.1:8320` | Profile `observability`, off by default. Schema `phoenix`. ELv2 licence. |
| `browser` | Playwright `v1.63.0-noble` | — | — | Profile `browser`. **Not built** until an allow-listed JS-only source needs it. |

**No Redis.** DBOS queues and schedules, sessions and rate limits all live in Postgres.

**Images**
- `backend`: multi-stage `python:3.12-slim`, matching the team's image. It copies `uv 0.12.x` from `ghcr.io/astral-sh/uv`, runs `uv sync --locked`, and runs as a non-root user.
- `frontend`: builds in `node:24-alpine` and serves with `nginx:1.30-alpine`. Node 24 enters maintenance on 2026-10-20, so re-check the line in Phase 1.

**First-time bootstrap.** No lock files exist yet and there is no host Python or Node, so the lock files are generated in throwaway containers before the first build:

```bash
docker run --rm -v "$PWD/backend:/work" -w /work -e UV_PYTHON_DOWNLOADS=0 ghcr.io/astral-sh/uv:0.12.15-python3.12-trixie-slim uv lock
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npm install --package-lock-only
```

These commands appear first in LOCAL_DEVELOPMENT.md.

## 4. Code layout

```text
mdcopilot-blog/
├── compose.yaml · .env · .env.example · .gitignore
├── scripts/acceptance/phase1.sh   Phase 1 acceptance run (host needs only docker, curl, openssl, jq)
├── docs/blog-agent/   ARCHITECTURE · FRAMEWORK_EVALUATION · RESEARCH_ARCHITECTURE ·
│                      IMPLEMENTATION_PLAN · LOCAL_DEVELOPMENT · plans/phase-N.md
├── backend/
│   ├── Dockerfile · .dockerignore · pyproject.toml · uv.lock · alembic.ini · migrations/
│   ├── prompts/<agent>/<name>.v<N>.md   Phase 1: hello/echo.v1.md; later research, ideation, deep_research,
│   │                                    writer, fact_checker, clinical_reviewer, editor, seo
│   ├── fixtures/mock/          llm/<agent>/<prompt>.json, search/default.json; later feeds, pages, PDFs
│   ├── src/mdcopilot_blog/     installed package (uv_build, src layout)
│   │   ├── settings.py · logs.py · ids.py · errors.py   settings, JSON logging, ids, problem responses
│   │   ├── cli.py · worker.py  CLI (migrate, seed, prompts, users) and the DBOS worker entrypoint
│   │   ├── domain/        typed contracts (§12), enums, RBAC matrix, state machines; later scoring, novelty &
│   │   │                  diversity rules, quality gates, article assembly/parsing — pure, no I/O
│   │   ├── db/            SQLAlchemy 2 async base, engine, models, seed data
│   │   ├── api/           app factory, routers, schemas, dependencies (auth, RBAC, CSRF)
│   │   ├── auth/          passwords, sessions, CSRF tokens, login rate limit, users
│   │   ├── services/      use cases behind the API (runs, audit)
│   │   ├── llm/           LLMGateway (agents, web search, embeddings), routes, call recorder, mock models;
│   │   │                  later provider adapters and pricing — the ONLY place provider SDKs are imported
│   │   ├── prompts/       prompt registry (files → blog_prompt_versions)
│   │   ├── workflows/     DBOS workflows, steps, queues, schedules, step tracking, API-side DBOS client
│   │   ├── publishing/    BlogPublisher protocol, null publisher; later renderer, manual export,
│   │   │                  MDCopilot API, sync of MDCopilot posts
│   │   ├── research/      (Phase 2) query planning, feed collectors, retriever, extractor, ledger, tiers
│   │   ├── agents/        (Phase 2+) one module per agent: prompt id, input builder, output type
│   │   └── observability/ (Phase 9) OpenTelemetry setup, metrics SQL
│   └── tests/             unit · db · api · workflows (later agents · failure)
└── frontend/
    ├── Dockerfile · nginx/ · package.json · package-lock.json · vite.config.ts
    └── src/  app (navigation) · routes (pages) · features (auth, runs) · components/ui (shadcn) · lib (API client)
```

**Layering rule (spec Rule 2).**
- `api` and `workflows` call `agents`, `research` and `publishing`.
- Those call `llm` and `db` (the persistence layer).
- `domain` depends on nothing.
- Agents never touch the database, and prompts contain no database logic.

**Paths elsewhere in these docs.** Other sections and the companion documents write module paths as `app/<package>/` (for example `app/llm/search/`). Read them as `backend/src/mdcopilot_blog/<package>/`.

## 5. Workflows

All workflows run in `worker`. Each numbered stage is one `@DBOS.step`.

**Identity and idempotency (DBOS fork-aware).**
- A user-visible run is a `blog_runs` row. Every DBOS execution of it, whether the original, a fork or a restart, is a `blog_run_attempts` row keyed by `dbos_workflow_id`.
- Steps find their attempt from `DBOS.workflow_id`, never from inputs, because `fork_workflow` copies the original inputs.
- Step side effects and `blog_agent_runs` rows are keyed by `(dbos_workflow_id, dbos_step_id)`. Every content write is an **insert** (new article version, new review, new claim checks), so a forked step never overwrites earlier results.

### 5.1 `discover_topics(run_id)`

Triggered by the daily schedule or a manual run. Timeout 15 min.

| # | Step | Kind | Output / run status |
|---|---|---|---|
| D1 | `open_attempt` | code | attempt row. Run → `RESEARCHING`. |
| D2 | `gather_signals` | code + web search | feeds ∥ PubMed ∥ Federal Register ∥ broad web search, in parallel (RESEARCH_ARCHITECTURE §2, §7) |
| D3 | `build_ledger` | code | fetch + extract + date + tier → `blog_sources` |
| D4 | `synthesize_research` | **Research Analyst** | typed findings linked to ledger sources |
| D5 | `ideate_topics` | **Topic Strategist** | exactly 3 candidates with rubric scores |
| D6 | `check_novelty_and_score` | code (embeddings) | novelty result and weighted score per candidate. If fewer than 3 pass, D5 runs again with an avoid-list, at most 2 times. Run → `TOPICS_READY`. |
| D7 | `select_topic` | code | **Auto mode:** the best passing candidate goes to `produce_article`, enqueued; run → `PRODUCING`. **Manual mode:** run → `WAITING_FOR_TOPIC` and the workflow ends. |

A manual run that supplies a topic skips D2–D6. The novelty check still runs, as a warning only, and D7 starts production.

### 5.2 `produce_article(run_id, candidate_id)`

Timeout 30 min.

| # | Step | Kind | Output / article status |
|---|---|---|---|
| P1 | `deep_research` | web search + code | packet sources added to the ledger |
| P2 | `build_research_packet` | **Deep Research Analyst** | research packet (spec §16) as a new packet version |
| P3 | `write_draft` | **Writer** | article **v1** → `DRAFTING` |
| P4 | `fact_check` | **Fact Checker** + ≤3 verification searches | claim checks for v1 → `FACT_CHECKING` |
| P5 | `clinical_review` | **Clinical Reviewer** | review of v1 → `CLINICAL_REVIEW` |
| P6 | `editorial_review` | **Editorial Reviewer** | review of v1 → `EDITORIAL_REVIEW` |
| P7 | `revise` | **Writer** (revise mode) | **v2**. Applies every unsupported-claim fix and every required change. The writer records a resolution for each finding ID. Skipped if nothing is required. |
| P8 | `verify_facts` | **Fact Checker** | full claim checks on **the final version** (v2, or v1 if P7 was skipped and P4 already covers it) |
| P9 | `seo` | **SEO Specialist** | SEO/social record for the final version → `SEO` |
| P10 | `quality_gates` | code | Pass → `READY_FOR_REVIEW`; workflow ends. Fail → **one fix pass** (§10). Still failing → `QUALITY_GATE_FAILED`; workflow ends. |

The reviews run one after another. Running them concurrently would save about 20 s but complicate status and tracing.

### 5.3 Human-action workflows

Each human action starts a short workflow, enqueued to the `interactive` queue so it never waits behind a daily run.

| Workflow | Trigger | Steps |
|---|---|---|
| `regenerate_component(article_id, component, section_key?, instructions?)` | Regenerate headline / introduction / section / pull quote / CTA | Writer on that component, using neighbouring sections and the packet → new version → **full** fact check → SEO if the title changed → gates → `READY_FOR_REVIEW` / `QUALITY_GATE_FAILED` |
| `regenerate_article(article_id, instructions?)` | Regenerate entire article | P3–P10 on the current packet |
| `regenerate_research(article_id)` | Regenerate research | P1–P10 (new packet version; the old one is kept) |
| `regenerate_topics(run_id)` | Regenerate topics | D5–D7, with the previous candidates in the avoid-list |
| `change_topic(run_id, candidate_id)` | Select another topic | Current article → `SUPERSEDED`, then `produce_article` for the new candidate |
| `recheck_article(article_id)` | "Re-check" after a human edit | Full fact check → gates |
| `publish_article(article_id, version_id)` | Publish (network publisher) or schedule due | validate → render → `BlogPublisher.publish` (idempotent) |
| `apply_schedule()` | Daily time or timezone changed in Settings | `DBOS.apply_schedules(...)` on the worker |
| `control(action, workflow_id, step?)` | Fallback when the pinned `DBOSClient` cannot fork or cancel | Performs the fork or cancel inside the worker |

Save-edit, select-title, approve, reject, export, confirm-published and schedule are plain API transactions.

### 5.4 Schedules

- **`daily_generation`.** A DBOS schedule (cron `0 7 * * *`, `cron_timezone` from settings, `automatic_backfill=False`) runs a small wrapper workflow `daily_trigger(scheduled_time)`. The wrapper:
  1. works out the local date;
  2. skips and notifies if an article for that date already exists (for example from a manual run) at or beyond `READY_FOR_REVIEW`;
  3. otherwise starts `discover_topics` with workflow ID `daily-<YYYY-MM-DD>`, so that date can never have two scheduled runs.

  At worker start, if today's slot has passed and no `daily-<today>` workflow exists, the worker starts one (same day only). Manual runs use `manual-<uuid>` IDs.

  While `BLOG_AGENT_SCHEDULER_ENABLED=false`, the schedule is paused. Changing the time or timezone in Settings enqueues `apply_schedule`.
- **`publish_due`** runs every 5 minutes and handles `SCHEDULED` articles whose time has come (§13).
- **`maintenance`** runs nightly. It syncs MDCopilot's published posts (§8), prunes old DBOS workflow records, rolls up feed health, and reconciles costs (optional).

Exact DBOS signatures (`apply_schedules`, `backfill_schedule`, pause/resume, `SetWorkflowID`) are confirmed in Spike S1.

### 5.5 Retry, restart, resume (spec §39)

| Operation | Implementation |
|---|---|
| **Retry (automatic)** | DBOS step retries with backoff, only for transient errors (HTTP 408/429/5xx, timeouts, connection errors). Inside a step, the gateway walks the agent's model route (§7.1). |
| **Retry failed run / restart from step (UI)** | The API maps the step name to the **latest** matching `function_id` (`list_workflow_steps`) and calls `fork_workflow(workflow_id, start_step=function_id)`. That creates a new attempt, and later steps insert new versions. |
| **Resume interrupted run** | Automatic: DBOS recovers PENDING workflows when the worker starts. If `APP_VERSION` changed, the UI "Resume" forks with `application_version=current`. |
| **Restart entire run** | New workflow with the same inputs, recorded as a new attempt |
| **Cancel** | `cancel_workflow`; run → `CANCELLED` |
| **Manual intervention** | Failed runs show the error class, a summary of the step inputs, and buttons for retry / restart-from / cancel |

**Limits.** Each workflow has its own timeout (discover 15 min, produce 30 min). Human waits never count, because workflows end at human gates. A per-run cost cap (`BLOG_AGENT_MAX_COST_PER_RUN_USD`, default 5) is checked by the gateway before every paid call. A kill switch, `BLOG_AGENT_ENABLED=false`, pauses schedules and rejects new runs.

## 6. State machines

**Run** (`blog_runs.status`): `QUEUED → RESEARCHING → TOPICS_READY → (WAITING_FOR_TOPIC | PRODUCING) → SUCCEEDED | FAILED | CANCELLED`

**Article** (`blog_articles.status`):

```text
DRAFTING → FACT_CHECKING → CLINICAL_REVIEW → EDITORIAL_REVIEW → (revise, verify) → SEO
   → READY_FOR_REVIEW | QUALITY_GATE_FAILED
READY_FOR_REVIEW | QUALITY_GATE_FAILED → (human edit / regenerate / recheck) → READY_FOR_REVIEW | QUALITY_GATE_FAILED
READY_FOR_REVIEW → APPROVED
APPROVED → EXPORTED → PUBLISHED                                 (manual export: confirm-published)
APPROVED → PUBLISHING → PUBLISHED | PUBLISH_FAILED → PUBLISHING (network publisher, flag on)
APPROVED → SCHEDULED → (due) → EXPORTED (+ notification)  |  PUBLISHING (network publisher)
READY_FOR_REVIEW | QUALITY_GATE_FAILED | APPROVED | SCHEDULED | EXPORTED → REJECTED
in-progress → FAILED (workflow failed) · SUPERSEDED (topic changed)
```

**Transition rules**
- All transitions live in one table in `domain/state_machine.py`, used by both the API and the workflows. An illegal transition raises an error.
- Approval requires the gates to pass on **that exact version**. Approving a gate-failed version is an open decision (§24.2).
- `BLOG_PUBLISHING_ENABLED` gates **only network publishers**. Export and confirm-published are always available to `blog.publish` holders.
- No transition leads from any agent-produced state straight to `EXPORTED`, `PUBLISHING` or `PUBLISHED`. Every path goes through a human `APPROVED`.

**Publication** (`blog_publications.status`): `PENDING → EXPORTED → CONFIRMED` (manual) or `PENDING → IN_PROGRESS → PUBLISHED | FAILED` (network).

### 6.1 Mapping to the spec's status list (§23): deliberate deviations

| Spec status | Here |
|---|---|
| `RESEARCHING`, `TOPICS_READY` | Run statuses. No article exists yet. The article API exposes `pipelineStatus` from the run. |
| `DRAFTING`, `FACT_CHECKING`, `EDITORIAL_REVIEW`, `READY_FOR_REVIEW`, `APPROVED`, `REJECTED`, `PUBLISHED`, `FAILED` | Same names |
| *(added)* `CLINICAL_REVIEW`, `SEO` | Spec §20 and §22 stages, made visible |
| *(added)* `QUALITY_GATE_FAILED`, `PUBLISH_FAILED` | Named in spec §47 and §31 |
| *(added)* `SCHEDULED`, `EXPORTED`, `PUBLISHING`, `SUPERSEDED` | Scheduling, manual handoff, in-flight publish, changed topic |

## 7. Agents and model routing

There are **eight LLM agents**. Everything else is deterministic code. Routes are ordered lists read from `.env`, which Settings can override per agent. `anthropic:` entries are skipped when no Anthropic key is set. Model IDs were checked against provider pages on 2026-09-17.

| Agent | Job | Default route |
|---|---|---|
| Research Analyst | Turn ledger text plus search answers into typed findings; classify claims | `google:gemini-3.8-flash` → `openai:gpt-5.6-terra` |
| Topic Strategist | Exactly 3 candidates plus rubric scores | `google:gemini-3.8-flash` → `openai:gpt-5.6-terra` |
| Deep Research Analyst | Research packet | `google:gemini-3.8-flash` → `openai:gpt-5.6-terra` |
| Writer | Draft, revise, regenerate components | `openai:gpt-5.6-sol` → `google:gemini-3.8-flash` → `anthropic:claude-sonnet-5` |
| Fact Checker | Claim extraction and verification (§10) | `google:gemini-3.8-flash` → `openai:gpt-5.6-terra` → `anthropic:claude-sonnet-5`, with the **vendor-independence rule** below |
| Clinical Reviewer | Clinical plausibility, safety framing, invented anecdotes, autonomous-AI claims | `openai:gpt-5.6-sol` → `google:gemini-3.8-flash` |
| Editorial Reviewer | Clarity, originality, tone, headline/CTA quality, AI-style language, repetition | `openai:gpt-5.6-terra` → `google:gemini-3.8-flash` |
| SEO Specialist | Full spec §22 output | `google:gemini-3.5-flash-lite` → `openai:gpt-5.6-luna` |
| *(web search)* | Search calls (not an agent) | `openai:gpt-5.6-luna` + `web_search` |
| *(embeddings)* | Novelty and diversity vectors | `google:gemini-embedding-2` @ 1536 dims. No fallback to another embedding model. |

**Model settings**
- Reasoning effort and thinking level are pinned per agent and never raised on retry. "Max" adds 2–3 minutes per call.
- Output-token caps come from the §21 table.
- `gemini-3.1-pro-preview` (still in preview) and `claude-haiku-4-5` (retirement possible from 2026-10-15) are not used.

**Vendor-independence rule.** The Fact Checker uses the first model in its route whose provider differs from the provider that **actually served** the Writer call for this version, looked up in `blog_llm_calls`. If no such model is available, it runs anyway and records `independent_check=false`. The review page then shows a warning, and the corresponding gate is a warning, not a blocker.

### 7.1 LLM gateway (spec §36, Q15)

```python
class LLMGateway:
    async def run(self, agent: AgentSpec, inputs: BaseModel, *, ctx: CallContext) -> AgentResult[T]: ...
    async def search(self, query: SearchQuery, *, ctx: CallContext) -> SearchResult: ...
    async def embed(self, texts: list[str], *, ctx: CallContext) -> list[Vector]: ...

AgentSpec   = name, agent_version, prompt_id, output_type, route_key, max_output_tokens, reasoning
ModelRoute  = [ModelChoice(provider, model, params)]
CallContext = run_id, attempt_id, dbos_workflow_id, dbos_step_id, article_id?, topic_candidate_id?, trace_id
```

**Route handling.** `run()` walks the route itself; there is no `FallbackModel`. For each `ModelChoice`, it calls a Pydantic AI `Agent(output_type=...)` with SDK retries off and a bounded number of output-validation retries. It moves to the next choice on any of:
- `ModelAPIError`;
- `httpx`/`httpx2` timeouts;
- connection errors;
- `UnexpectedModelBehavior`, which covers exhausted validation retries.

Every attempt writes **one `blog_llm_calls` row**, with `fallback_from` set on fallback attempts.

**Web search.** `search()` sends web-search calls through the same budget, concurrency and recording path as `run()`. The provider clients live in `app/llm/search/`, and `app/research/` only plans queries and handles the results.

**Prompt rendering.** The versioned prompt receives brand, pillar and **diversity** variables (§8.1). Fetched web text is wrapped in `<untrusted_source id=…>` blocks, and every system prompt says to treat those blocks as data.

**Recording.** Each `blog_llm_calls` row stores:
- provider/model requested and served, and `fallback_from`;
- params;
- input, output, cached and reasoning tokens, plus `search_actions`;
- latency, status and error class;
- `cost_usd` and `price_version`;
- `prompt_name`, `prompt_version`, `prompt_sha`;
- the full `CallContext`.

**Guards**
- **Budget.** The per-run cost cap is checked before each call. Per-provider concurrency is limited.
- **Mock mode.** Every model is a `FunctionModel` fixture, `ALLOW_MODEL_REQUESTS=False` is set, search returns fixtures, and building a real client raises an error.
- **Isolation.** Only `app/llm/` imports `pydantic_ai`, `openai`, `google.genai` or `anthropic`.

## 8. Novelty engine (spec §14, deterministic)

**What is compared.** Each candidate's text (title + hook + thesis + angle) is embedded at 1536 dimensions and compared against:
- our topics and articles from the last 180 days;
- **MDCopilot's already-published posts.** The nightly `sync_mdcopilot_posts` job pages through the public, unauthenticated `GET /api/v1/blogs` and upserts rows into `blog_external_posts` with their embeddings and headline patterns. It is read-only and off while `BLOG_MDCOPILOT_PUBLIC_API_URL` is blank.

**Checks**

| Check | Method |
|---|---|
| Topic similarity | Cosine via pgvector, exact search (well under 10k rows, so no index yet) |
| Argument similarity | The candidate's core-argument sentence against stored article arguments |
| News-story reuse | Candidate primary-source canonical URLs against sources that anchored articles in the last 30 days |
| Headline repetition | Normalised trigram Jaccard against past headlines, plus headline-pattern counts over the last 14 days |
| Example reuse | Named companies, studies and regulations used in the last 30 days |

**Decision**
- **`REJECT_TOPIC`** if any of these holds:
  - topic similarity ≥ `novelty_threshold` (default 0.85);
  - argument similarity ≥ 0.88;
  - the same primary news URL was used in the last 30 days.
- **`WARN`** if within 0.05 of a threshold, or if the headline pattern or examples repeat.
- **`PASS`** otherwise.

`novelty_score = 1 − max_similarity`. The five nearest neighbours are stored and shown. **Under-covered angles:** the Topic Strategist receives pillar and theme coverage counts for the last 30 days. All thresholds are settings.

### 8.1 Content diversity (spec §48)

**Features stored per version.** For each version, an insert-only `blog_version_features` row records:
- the opening sentence, with its embedding;
- headline pattern;
- industry/segment tags;
- keywords;
- the core argument, with its embedding;
- examples;
- primary source domains;
- the normalised CTA text.

**Avoid bundle.** Built per run and passed as prompt variables to the **Writer** and **Editorial Reviewer**. It contains, from the last 30 days:
- recent titles and openings;
- recent CTAs;
- recent primary sources;
- overused 3–5-word phrases (frequency ≥3 across recent articles).

It also carries the brand's **prohibited-language list**. That list is seeded with the spec §8/§18 anti-patterns, for example "AI is transforming healthcare", "revolutionize", "game-changer", "in today's fast-paced world" and "unlock the power of".

**Enforcement**

| Check | Result on failure |
|---|---|
| Prohibited phrase present | Gate failure |
| CTA near-duplicate (trigram Jaccard ≥0.8 against the last 10) | Gate failure |
| Opening similarity ≥0.9 against the last 30 | Warning |
| Headline pattern used ≥3 times in 7 days | Warning |
| Primary-source domain used ≥3 times in 7 days | Warning |

The dashboard has a diversity panel showing pillar mix, source-domain concentration and top repeated phrases.

## 9. Topic scoring (spec §15)

| Component | Default weight | How computed |
|---|---|---|
| Timeliness | 25% | Deterministic, from the newest supporting source's `published_at`: ≤48 h = 1.0, ≤7 d = 0.7, ≤30 d = 0.3, else 0.1 |
| Novelty | 20% | From §8 |
| Evidence quality (`evidence_score`) | 20% | Deterministic: number of dated sources, Tier-1/2 share, primary source present |
| MDCopilot relevance (`business_relevance`) | 15% | LLM rubric 1–5 with a justification, normalised |
| Audience relevance | 10% | LLM rubric 1–5 |
| Editorial potential | 10% | LLM rubric 1–5 |

Weights are settings. The full breakdown is stored and shown on each topic card. A human can select any `PASS` candidate, or a `WARN` candidate after confirming.

## 10. Quality gates (spec §47, §18, §19)

**Fact Checker output.** For every claim it extracts, the Fact Checker records:
- `claim`;
- `kind` ∈ {statistic, regulatory, trial_result, workforce, company_announcement, quote_or_attribution, anecdote_or_vignette, general_fact, opinion};
- `importance`;
- `article_location`, given as a section key, sentence index and exact span;
- `citation_markers`;
- `source_id`;
- `verification_status` ∈ {SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, OUTDATED, MISLEADING, OPINION};
- `confidence`;
- `recommended_revision`.

The Writer prompt forbids invented anecdotes, vignettes, first-person clinician experiences and quotes.

| # | Gate (checked on the exact version being gated) | Method | On failure |
|---|---|---|---|
| 1 | Sources present | ≥ `min_source_count` distinct cited ledger sources, ≥1 Tier-1/2 | `QUALITY_GATE_FAILED`, suggest "Regenerate research" |
| 2 | Current claims verified | A fact check exists **for this version**. No high-importance claim is UNSUPPORTED/OUTDATED/MISLEADING. | fix pass |
| 3 | No unsupported statistics | Every `statistic` claim is SUPPORTED. A numeric scan (ignoring years 1900–2100, ordinals, times, headings and the CTA) finds no numeric sentence without a matching claim. | fix pass |
| 4 | No fabricated quotes or attributions | Every quoted span attributed to a person or organisation (any length), and every other quoted span of ≥6 words, appears in a cited source's text snapshot | fix pass |
| 5 | No unsourced anecdotes | No `anecdote_or_vignette` claim lacks a source. The Clinical Reviewer raised no "invented anecdote / physician experience" BLOCKING flag. | fix pass |
| 6 | No duplicate topic | Candidate novelty ≠ REJECT. Article embedding is below the threshold against published and external posts. | `QUALITY_GATE_FAILED`, suggest "Change topic" |
| 7 | Word count | Body words within settings (default 850–1150) | fix pass |
| 8 | Required structure | Introduction, context, core argument, evidence, MDCopilot perspective, practical implications, conclusion, pull quote and CTA are all present | fix pass |
| 9 | CTA present and fresh | Non-empty, and not a near-duplicate of the last 10 CTAs | fix pass |
| 10 | No prohibited language | No brand-prohibited phrase present | fix pass |
| 11 | SEO complete and within target limits | Every spec §22 field is present. SEO title ≤60, meta description 120–160, slug valid and unique, and MDCopilot limits met (title ≤200, slug ≤200, excerpt ≤500). | SEO re-run within the fix pass |
| 12 | Fact check passed | Verdict PASS for this version | fix pass |
| 13 | Clinical review clear | No unresolved BLOCKING flag: medical advice, autonomous clinical decisions, misinformation, invented anecdote | fix pass |
| 14 | Editorial review completed | An editorial review exists for the version the revision was based on, and every `required_change` has a recorded resolution in this version | fix pass |
| 15 | AI-assistance disclosure present | Brand disclosure text is non-empty | `QUALITY_GATE_FAILED` (configuration) |
| — | Independent fact check · opening/headline/source diversity | §7, §8.1 | warning only |

**Fix pass (at most one).** The Writer revises using every failed-gate message. Then `verify_facts` runs on the new version, SEO re-runs if gate 11 failed or the title or slug changed, and the gates run again. Any gate still failing sets `QUALITY_GATE_FAILED`, with the details on the review page. Each gate run is stored as a `blog_reviews` row (`kind=quality_gate`) with per-gate results.

## 11. Articles, versions, regeneration (spec §17, §34, §40)

**What the Writer produces.** A typed `ArticleDraft` (§12). It receives:
- the topic;
- the research packet;
- the brand voice;
- the pillar;
- a list of recent articles (titles, arguments, openings);
- the avoid bundle (§8.1);
- the cited source list, with `[S<n>]` markers.

**Assembly.** The introduction has no heading, and each other body section is an H2 in a fixed order. The pull quote and CTA are separate fields. `content_markdown` is assembled from these parts deterministically. Unknown citation markers are rejected.

**Versions are immutable.**
- `blog_article_versions` holds content only: sections JSONB, assembled Markdown, word count, parent, change kind and scope, and `created_by`.
- A trigger rejects **every** UPDATE on it.
- SEO/social copy, embeddings, features and research-packet links go into **insert-only side tables** keyed by `version_id`.
- The article row points to `current_version_id`, `approved_version_id` and `published_version_id`. Example history: v1, v2, v3 (human edit), with v3 approved and published.

**Regeneration.** A component regeneration changes only the targeted field and inserts a new version. The whole new version is then fact-checked again, costing about $0.06 and 30–45 s; partial re-checking is not attempted.

**Human edits**
- The editor edits the assembled Markdown. On save, the server maps text before the first H2 to the introduction and each H2 block to the section keys **by position**. Heading text may change.
- A save with the wrong number of H2 blocks is rejected with a 422 that names the problem.
- Pull quote, CTA, titles and SEO have their own fields.
- A save creates a new version and immediately runs the deterministic gates.
- "Re-check" runs `recheck_article`. Approval requires the fact-check-based gates to have run on that version.

## 12. Typed contracts (spec §12, §13, §23)

These are Pydantic models in `domain/`. The article API response is generated into TypeScript types.

```python
class ResearchSource(BaseModel):          # blog_sources
    id: str; title: str; url: str; canonical_url: str; publisher: str; domain: str
    published_at: datetime | None; date_source: Literal["feed","api","jsonld","meta","htmldate","none"]
    retrieved_at: datetime; source_type: SourceType; tier: Literal[1,2,3]
    access_mode: Literal["full_text","abstract_only","metadata_only"]; relevance_score: float

class ResearchFinding(BaseModel):         # blog_research_findings (+ blog_finding_sources)
    id: str; claim: str; evidence: str; source_ids: list[str]; confidence: float
    category: str; claim_type: Literal["FACT","ANALYSIS","OPINION","PREDICTION","MARKETING_CLAIM"]
    importance: Literal["high","normal"]

class TopicCandidate(BaseModel):          # blog_topic_candidates
    topic_id: str; title: str; hook: str; why_now: str; relevant_news: list[NewsRef]
    mdcopilot_connection: str; target_audience: str; pillar: PillarKey
    novelty_score: float; evidence_score: float; business_relevance: float; editorial_potential: float
    timeliness_score: float; audience_relevance: float; total_score: float
    score_breakdown: dict[str, ScoreItem]; novelty: NoveltyResult; sources: list[str]; status: CandidateStatus

class GeneratedBlogPost(BaseModel):       # API view over blog_articles + current version + side tables
    id: str; topic_id: str
    title_options: TitleOptions            # provocative / operational / visionary
    selected_title: str | None; slug: str; content_markdown: str; excerpt: str
    pull_quote: str; cta: str; category: str; tags: list[str]
    seo: SEOMetadata; social: SocialCopy | None; sources: list[BlogSource]
    research_summary: str                  # from the research packet
    fact_check: FactCheckResult; clinical_review: ClinicalReview; editorial_review: EditorialReview
    quality_gates: GateReport; novelty: NoveltyResult
    status: ArticleStatus; pipeline_status: RunStatus; version_no: int
    created_at: datetime; updated_at: datetime

class SEOMetadata(BaseModel):
    seo_title: str; meta_description: str; slug: str; primary_keyword: str; secondary_keywords: list[str]
    og_title: str; og_description: str; tags: list[str]; category: str
    internal_link_suggestions: list[InternalLink]    # from our published and external MDCopilot posts
    external_references: list[str]                   # ledger source ids

class EditorialReview(BaseModel):
    editorial_score: float; strengths: list[str]; weaknesses: list[str]
    required_changes: list[Change]; optional_changes: list[Change]; final_recommendation: str
```

The JSON over the wire uses camelCase aliases, matching the spec's TypeScript interface.

## 13. Human review experience (spec §24–§29, §49, §57)

| Page | Contents | Key actions |
|---|---|---|
| **Dashboard: Today** | **Today card:** research status, "N opportunities discovered", the recommended topic with *why* (why-now, evidence, relevance, novelty), article status, the 3 headline options, a quality summary (fact check, source count and tier mix, novelty %, clinical, editorial score, SEO). Also the pipeline tracker, metrics (§17) and diversity panel. | Generate today's blog · Review research · Open article · Approve · Regenerate · Change topic |
| **Today's Ideas** | 3 topic cards showing why now, news trigger, pillar, MDCopilot angle, score breakdown, novelty neighbours, sources | Select · Regenerate topics · Edit · Reject |
| **Research** | Research runs, themes covered, findings (claim type, confidence, sources, dates), per-phase latency | Regenerate research |
| **Drafts / Review Queue / Published** | Filtered lists with gate badges | Open |
| **Article review** | **Left pane:** the 3 candidates with the selected one highlighted and scores shown; the research packet; sources with dates and tiers; claim checks; quality summary; gate results; structured summaries (why selected, supporting evidence, thesis, fact-check status, editorial issues). Raw model reasoning is never shown. **Right pane:** CodeMirror Markdown editor, server-rendered sanitised preview, headline picker, SEO/tags/category panel, version history and diff. | Save · Regenerate (component / article / research) · Change topic · Re-check · Approve as draft · Approve & export (or Approve & publish when a network publisher is on) · Schedule · Reject (reason required) |
| **Topics** | Topic history and external posts, with similarity search | — |
| **Content Calendar** | FullCalendar month/list view of published, scheduled, exported, draft, research and planned slots (pillar rotation) | Move · Schedule · Change pillar · Cancel · Regenerate |
| **Sources** | Ledger browser, feed health, domain tier rules, discovery themes | Enable/disable feed · Edit tier · Edit themes |
| **Settings** | Daily time and timezone; word count; preferred pillars and rotation; research window; minimum sources; novelty threshold; score weights; model route per agent; publishing mode; default category and CTA; website; brand profile (incl. prohibited language and disclosure). Human approval shows as locked ON. Automatic publishing shows as locked OFF ("not available in this release"). | Save (versioned) |
| **Agent Runs** | Run and attempt list; step timeline with agent, model, prompt version, tokens, cost, latency, sources used, errors | Retry · Restart from step · Restart run · Cancel |

**Export UX.**
- "Copy article" writes both `text/html` and `text/plain` clipboard items (`navigator.clipboard.write`), so pasting into Quill keeps the formatting.
- Separate copy buttons exist for title, slug and excerpt.
- A download button saves the full bundle (HTML, metadata JSON, social copy).
- After pasting, the user enters the live post URL through "Confirm published".

## 14. Publishing (spec §30–§31, Q16)

```python
class BlogPublisher(Protocol):
    key: str
    network: bool                                   # gated by BLOG_PUBLISHING_ENABLED when True
    def capabilities(self) -> PublisherCapabilities: ...
    async def validate(self, payload: PublishPayload) -> list[Issue]: ...
    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult: ...
    async def find_existing(self, payload: PublishPayload) -> RemotePost | None: ...
```

| Implementation | Default | Behaviour |
|---|---|---|
| `ManualExportPublisher` (network=False) | **Yes** | Builds the export bundle (sanitised HTML, title, slug, excerpt, SEO fields, tags, OG text, social copy, references). Article → `EXPORTED`. "Confirm published" (URL) → `PUBLISHED`. |
| `MDCopilotApiPublisher` (network=True) | Off | Signs in with local-dev admin credentials (`BLOG_PUBLISHER_LOGIN_ID` / `BLOG_PUBLISHER_PASSWORD`, for an account whose login second factor is disabled by the backend's existing admin setting). It reads the 15-minute access-token cookie and sends it as `Authorization: Bearer`, then calls `POST /api/v1/admin/blogs` or `PUT /{id}` with `status=draft` or `published`, **always sending `slug`**. Production needs a backend-owned service token, which is outside this project. Exact login endpoint and CSRF behaviour are confirmed in Spike S5. |
| `NullPublisher` | Mock mode | Records the payload only |

Ghost and WordPress publishers are **not built**; the spec says not to assume them. The protocol leaves room for them.

**Rendering and validation**
1. Validate content, SEO, sources, target field limits and disclosure.
2. Render Markdown with `markdown-it-py` (`js-default`, tables off).
3. Sanitise with `nh3` using a Quill-1.3.7-safe allowlist: `h2 h3 p strong em s a[href] ul ol li blockquote img[src,alt]`, http/https links only, `rel="noopener noreferrer"`.
4. Add the pull quote as `<blockquote>`, then the references list, then the **mandatory** AI-assistance disclosure. Its text is editable in the brand profile but must be present; OpenAI's publication policy requires disclosing AI's role.

**Idempotency**
- `blog_publications` is unique on `(article_id, publisher, target)`, with `idempotency_key = version_id`.
- If `external_post_id` is known, the publisher updates instead of creating.
- Otherwise, before creating (and after any timeout or duplicate-slug error), `find_existing` pages through `GET /admin/blogs` (limit 50, newest first, optionally `search=<title>`) and matches **`slug` exactly on our side**. If the post is already published, `GET /api/v1/blogs/{slug}` is also checked. A found post is adopted.

A retry therefore never creates a second post. On success the publisher stores `published_at`, `published_url` (from `BLOG_PUBLISHER_PUBLIC_URL` + `/blog/<slug>`), `external_post_id`, `publisher`, status and payload hash.

**Scheduling**
- **Manual mode:** at the scheduled time, `publish_due` builds the bundle, sets `EXPORTED` and notifies. A human still pastes the post.
- **Network mode:** `publish_due` publishes only if the user who scheduled it still holds `blog.publish`. Scheduling requires `blog.schedule`, and also `blog.publish` while a network publisher is active.

**Known gap.** MDCopilot has no SEO, tag or category fields, so those stay in our app and in the export bundle.

## 15. Data model (spec §40–§41)

Everything lives in our own PostgreSQL 16 + pgvector (Q13):
- schema `app` (Alembic) holds our tables;
- schema `dbos` holds DBOS system tables.

All IDs are UUIDv7 and all timestamps are `timestamptz`. Tables arrive in the phase that first needs them (IMPLEMENTATION_PLAN).

| Table | Purpose | Key constraints / indexes |
|---|---|---|
| `users`, `user_sessions`, `login_attempts`, `audit_log` | Auth, RBAC, audit | email unique; session token hash; audit (actor, action, entity, reason, at) |
| `blog_settings`, `blog_brand_profiles` | Versioned settings (incl. schedule time and timezone) and brand profile | `version` unique; one active each |
| `blog_content_pillars`, `blog_discovery_themes` | Pillars A–E + Narrative with rotation; 15 spec §7 themes → query templates → pillars | `key` unique |
| `blog_calendar_slots` | Planned pillar per date, overrides | `date` unique |
| `blog_source_feeds`, `blog_source_domains` | Feed catalogue and health; domain → tier/type rules | `url` unique; `domain` unique |
| `blog_runs`, `blog_run_attempts` | User-visible runs; one row per DBOS execution (original, fork, restart) | runs: `status`, `created_at`, `run_date`, `kind`; attempts: `dbos_workflow_id` unique |
| `blog_agent_runs` | One row per step execution (spec §35 fields) | `(dbos_workflow_id, dbos_step_id)` unique; `status`; `created_at` |
| `blog_llm_calls` | One row per LLM, search or embedding attempt | `created_at`; `(provider, model)`; `run_id`; `article_id`; `topic_candidate_id` |
| `blog_research_runs` | Research sessions: themes covered, per-phase latency | `run_id`; `kind` |
| `blog_sources` | Source ledger (incl. text snapshot, internal only) | `url_hash` unique; `domain`; `published_at`; `tier` |
| `blog_research_findings`, `blog_finding_sources` | Typed findings ↔ sources | `research_run_id` |
| `blog_research_packets` | Versioned packets per article | `(article_id, version)` unique |
| `blog_topic_candidates` | 3 per round; scores; novelty; `embedding vector(1536)` | `run_id`; `status` |
| `blog_topics` | Topics that became articles (history): embeddings, argument, keywords, examples, headline pattern | `created_at` |
| `blog_external_posts` | MDCopilot published posts from the read-only sync; embedding, headline pattern | `(origin, slug)` unique |
| `blog_articles` | Article head: status, slug, pillar, category, tags, scheduled_for, scheduled_by, version pointers | `status`, `created_at`, `slug` unique, `topic_id`, `published_at`, `scheduled_for` |
| `blog_article_versions` | **Immutable** content versions | `(article_id, version_no)` unique; UPDATE blocked by trigger |
| `blog_version_seo`, `blog_version_embeddings`, `blog_version_features`, `blog_article_sources` | Insert-only per-version side data; citation markers | keyed by `version_id` |
| `blog_reviews`, `blog_claim_checks` | Fact-check, clinical, editorial, gate and human reviews; per-claim checks; resolution records | `(version_id, kind)` |
| `blog_publications` | Publication attempts and results | `(article_id, publisher, target)` unique; `idempotency_key` unique; `published_at` |
| `blog_prompt_versions` | Registered prompt versions (immutable) | `(name, version)` unique; `sha` |
| `blog_price_overrides` | Search fees and missing model prices | `(provider, sku, effective_from)` |
| `blog_notifications` | In-app notifications | `user_id`, `read_at` |

## 16. API (spec §42)

REST under `/api/blog-agent`, JSON with camelCase. Errors use `application/problem+json`. TypeScript types are generated from the OpenAPI schema.

```text
POST   /runs                              manual run {date, pillar?, topic?, audience?, tone?, wordCount?}
GET    /runs · GET /runs/{id}             list / detail (attempts, steps, costs, errors)
POST   /runs/{id}/cancel · /restart · /resume
POST   /runs/{id}/steps/{step}/retry · /runs/{id}/steps/{step}/restart
GET    /topics · POST /topics/generate {runId} · POST /topics/{id}/select · PATCH /topics/{id} · POST /topics/{id}/reject
GET    /research-runs · GET /research-runs/{id}
GET    /articles · GET /articles/{id} · PATCH /articles/{id}                (save edit → new version)
GET    /articles/{id}/versions · /versions/{vid} · /diff?from=&to=
POST   /articles/{id}/regenerate {component: headline|introduction|section|pull_quote|cta|article|research, sectionKey?, instructions?}
POST   /articles/{id}/select-title · /recheck · /approve {mode: draft|publish} · /reject {reason}
POST   /articles/{id}/export · /confirm-published {url} · /publish · /schedule {at} · /unschedule
GET    /articles/{id}/sources · /fact-check · /reviews · /quality-gates · /preview (sanitised HTML)
GET    /sources · PATCH /sources/feeds/{id} · PATCH /sources/domains/{id} · GET/PUT /themes
GET    /calendar?month= · PATCH /calendar/slots/{date}
GET/PUT /settings · GET/PUT /settings/brand · GET/PUT /pillars
GET    /agent-runs · GET /agent-runs/{id}
GET    /metrics/dashboard · GET /metrics/costs?groupBy=day|week|month|agent|model|article|research_run|topic
/api/auth/login · /logout · /session     /api/admin/users (CRUD, roles)     /healthz · /readyz
```

## 17. Authentication, RBAC, security (spec §43–§44)

**Authentication**
- **Accounts.** Local users with Argon2id passwords (`pwdlib[argon2]`). The first admin is created with `docker compose exec api sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'` (password from `BOOTSTRAP_ADMIN_PASSWORD`; see LOCAL_DEVELOPMENT.md §7), and admins invite everyone else.
- **Sessions.** An opaque random session ID is stored hashed. The cookie is HttpOnly and SameSite=Strict. In production it is also Secure with the `__Host-` prefix; in http dev the cookie name and Secure flag are configurable. Idle timeout is 30 minutes and the absolute limit is 12 hours.
- **CSRF.** Every unsafe method requires a session-bound `X-CSRF-Token` and an `Origin` on the allowlist. A request carrying `Sec-Fetch-Site` with any value other than `same-origin` is rejected. The header's absence alone is not a rejection, because plain-http container browsers don't send it.
- **Login protection.** Attempts are rate-limited per IP and per account in Postgres. TOTP MFA is a Phase 10 option.

**Permissions**

| Permission | viewer | editor | reviewer | publisher | admin |
|---|---|---|---|---|---|
| `blog.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `blog.generate` | | ✓ | ✓ | ✓ | ✓ |
| `blog.edit` | | ✓ | ✓ | ✓ | ✓ |
| `blog.review` | | | ✓ | ✓ | ✓ |
| `blog.approve` | | | ✓ | ✓ | ✓ |
| `blog.schedule` (+ `blog.publish` when a network publisher is on) | | | ✓ | ✓ | ✓ |
| `blog.publish` (export, confirm-published, publish) | | | | ✓ | ✓ |
| `blog.agent_runs` | | | ✓ | ✓ | ✓ |
| `blog.settings` (+ users) | | | | | ✓ |

One FastAPI dependency enforces permissions on every route, denying by default. Approve, reject, export, publish, schedule and settings changes are written to `audit_log`.

**Security**
- **Secrets.** Read from the environment only (`SecretStr`). They are never returned by the API (Settings shows them masked), never logged, and never put in prompts. `.env` is git-ignored with mode 600.
- **LLM output.** Always parsed into Pydantic models. No generated text is executed. No agent has tools that write or execute.
- **HTML safety.** Markdown is rendered with raw HTML disabled, then sanitised with `nh3`. The preview also runs DOMPurify. Only http/https links are allowed. nginx sends a CSP.
- **Prompt injection.** Fetched pages are untrusted and delimited. Agents may cite only ledger IDs, and URLs outside the ledger are rejected in code.
- **SSRF.** The fetcher blocks private and metadata IP ranges, including after redirects, and enforces size and time limits.
- **Reasoning.** Only structured summary fields are shown (spec Rule 7). Provider reasoning content is never stored or displayed.
- **Dependencies.** Pinned via `uv.lock` and `package-lock.json`. The LiteLLM package is not used.

## 18. Observability and cost tracking (spec §35, §45–§46, Q17–Q18)

**Source of truth.** Everything is recorded in our own tables, `blog_runs`, `blog_run_attempts`, `blog_agent_runs` and `blog_llm_calls`. From them, plain SQL gives the Agent Runs page and the dashboard metrics:
- posts generated, published and pending;
- topics generated and research sources;
- average generation time;
- average quality (editorial score);
- duplicate-topic rate;
- fact-check pass rate;
- LLM cost for today, week and month, and per article, per research run, per topic, per agent and per model.

**Cost.** Token cost uses the pinned `genai-prices` data at request time. Search fees come from `blog_price_overrides`: OpenAI web search is $10 per 1k **search actions**, counted from `tool_usage.web_search.num_requests`. Each row freezes its `price_version`. Reconciliation against the OpenAI Costs API is optional (Phase 9).

**Tracing**
- OpenTelemetry spans use `gen_ai.*` attributes and carry `run_id`, `attempt_id`, `trace_id`, agent and step.
- The `trace_id` is created when the run is created and passed to every workflow via the run row, so one run is one trace.
- OTLP export is **off by default**. The `observability` profile runs Phoenix locally.

**Logs and health.** Structured JSON logs carry `run_id` and `trace_id`. `/healthz` reports liveness and `/readyz` reports database status. The worker's health is its heartbeat file (`/tmp/worker-heartbeat`), which the compose healthcheck reads.

## 19. Configuration, brand, prompts (spec §50–§52, §56)

**Precedence.** `.env` supplies defaults, and the active `blog_settings` version overrides them at runtime.

**Environment-only safety settings**
- `BLOG_AGENT_ENABLED`: kill switch.
- `BLOG_HUMAN_APPROVAL_REQUIRED`: must be true, or the app refuses to start.
- `BLOG_PUBLISHING_ENABLED`: gates network publishers only.
- `BLOG_GEMINI_GROUNDING_ENABLED`: reserved; provider not built.
- `BLOG_AGENT_MOCK_MODE`.

Automatic publishing has no setting because it does not exist in this release.

**Brand profile.** Seeded from spec §8 and §18, and editable without code:
- name, description, target audience, mission;
- narrative: "an amplifier of specialist leverage, not a replacement for physicians";
- tone and prohibited language;
- CTA and website;
- target word count;
- AI-disclosure text (required).

**Pillars and themes.**
- **Pillars** (seeded from spec §9): A Specialist Scarcity & Access · B Cognitive Architecture & Physician Reasoning · C Burnout & Administrative Overload · D The Agentic Shift · E Governance & Clinical Autonomy · Narrative Edition.
- **Default rotation:** Mon–Fri A–E, Sat–Sun Narrative. The rotation is editable.
- **Discovery themes:** the 15 themes from spec §7, each with query templates and pillar links. Rotation rules are in RESEARCH_ARCHITECTURE §6.

**Prompts.** Stored as `backend/prompts/<agent>/<name>.v<N>.md`.
- Front matter holds name, version, agent, output type and variables. Rendering uses Jinja2 with `StrictUndefined`.
- At startup each prompt is hashed and registered in `blog_prompt_versions`. If a registered version's text has changed without a version bump, the app refuses to start.
- The active version is a setting, so a prompt can be rolled back.
- Every call records `prompt_name`, `prompt_version`, `prompt_sha`, the model and its params.

## 20. Mock mode and testing (spec §53–§54)

**Mock mode.** `BLOG_AGENT_MOCK_MODE=true` means no real LLM calls, searches or network publishing; the gateway and publisher factory enforce this. Deterministic fixtures let a full daily run finish in seconds. `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS` adds artificial step time so crash and resume can be tested.

All tests run in Docker via `docker compose run --rm tools pytest` (frontend: `docker compose run --rm web npm test`).

| Layer | What is tested |
|---|---|
| Unit | Contracts, state machine, scoring, novelty and diversity rules, tiering, date extraction, each quality gate (including numeric-scan false positives), article parsing and assembly, sanitiser, publisher idempotency, RBAC matrix |
| Agent | Each agent with `FunctionModel`: output validation, citation-marker enforcement, prompt rendering, gateway route walking |
| Workflow | Discover → select → produce → `READY_FOR_REVIEW` on a test Postgres; component, article and research regeneration; change topic; fix pass |
| Failure | Gemini or OpenAI 5xx or timeout → next route entry; search failure → partial coverage; invalid JSON → retry then escalate; missing sources → gate; duplicate topic → reject; publisher 5xx or timeout-after-create → exactly one post; DB outage → step retry; worker killed mid-step → resume |
| Live evaluation | Small fixture sets run against real models with a stated pass rate: invented statistic removed, fabricated quote detected, autonomous-AI claim flagged. Not part of CI. |
| API | Auth, CSRF (incl. through the Vite proxy from a container), per-route permissions, problem responses |
| Frontend | Vitest + Testing Library for topic selection, review, approve, reject, regenerate, export/publish, permission gating; Playwright smoke test in a container |

## 21. Expected latency of one daily run (Q19)

These are **estimates**, derived from the same token assumptions as §22 and from independent median speeds (Artificial Analysis, 72-hour P50, read 2026-09-17):

| Model | Output speed | Time to first token |
|---|---|---|
| Sol | ~60 tok/s | 3.4 s |
| Terra | ~85 tok/s | 1.7 s |
| Luna | ~111 tok/s | 2.4 s |
| Gemini 3.8 Flash | ~332 tok/s | ~16 s at high thinking |
| Flash-Lite | ~374 tok/s | ~9 s |

No vendor publishes per-call search latency, so the search rows are the least certain. After about 10 real runs, the dashboard shows measured P50/P90 instead.

| Stage | Output tokens (cap) | Estimate |
|---|---|---|
| Feeds ∥ broad search (10 calls, 6 at a time) | 1.5k per search call | 20–60 s |
| Fetch + extract + ledger | — | 10–30 s |
| Synthesis (Flash) | 6k | 30–40 s |
| Ideation (Flash) | 5k | 30–35 s |
| Novelty + scoring | — | 1–3 s |
| Deep research (8 calls) + fetch | 2k per call | 30–90 s |
| Research packet (Flash) | 8k | 35–45 s |
| Writer (Sol) | 4.5k | 70–90 s |
| Fact check v1 (Flash) + ≤3 verification searches | 6k | 30–60 s |
| Clinical review (Sol) | 2.5k | 40–55 s |
| Editorial review (Terra) | 2.5k | 25–40 s |
| Revision (Sol) | 4.5k | 70–90 s |
| Verify facts on final version (Flash) | 6k | 30–45 s |
| SEO (Flash-Lite) | 3k | 15–20 s |
| **Total** | | **≈ 7–12 min typical.** A fix pass adds ~3–4 min. |

Timeouts are 15 min for discovery and 30 min for production.

## 22. Estimated cost per article (Q20)

These are **estimates** from list prices on 2026-09-17, using the §21 token assumptions:

| Model / service | Price |
|---|---|
| Luna | $0.20 / $1.20 per 1M tokens (in/out) |
| Terra | $2 / $12 |
| Sol | $4 / $20 (promotional) |
| Flash | $0.75 / $3.75 (promotional) |
| Flash-Lite | $0.30 / $2.50 |
| OpenAI web search | $10 per 1k search actions |

Measured values replace these after the first runs.

| Stage | Assumption (in / out tokens) | Cost |
|---|---|---|
| Broad search (Luna) | 10 calls × ~10k / 1.5k, `max_tool_calls=1` → 10 actions | $0.14 |
| Synthesis (Flash) | 40k / 6k | $0.05 |
| Ideation (Flash) | 20k / 5k | $0.03 |
| Deep research (Luna) | 8 calls × ~15k / 2k, `max_tool_calls=2` → ~12 actions | $0.16 |
| Research packet (Flash) | 60k / 8k | $0.08 |
| Writer (Sol) | 25k / 4.5k | $0.19 |
| Fact check v1 (Flash) + ≤3 verification searches | 50k / 6k + ~$0.04 | $0.10 |
| Clinical review (Sol) | 20k / 2.5k | $0.13 |
| Editorial review (Terra) | 20k / 2.5k | $0.07 |
| Revision (Sol) | 35k / 4.5k | $0.23 |
| Verify facts on final version (Flash) | 50k / 6k | $0.06 |
| SEO (Flash-Lite) | 12k / 3k | $0.01 |
| Embeddings | ~6k tokens | <$0.01 |
| **Typical** | | **≈ $1.25** |

**Range.**
- **Low, ≈ $0.90:** no revision was needed, so there is no re-verification and no verification searches.
- **High, ≈ $2.40:** Terra used for deep research (+$0.39), one fix pass (+$0.30), one Writer retry (+$0.19), and twice the search actions (+$0.22 in fees).

**Monthly (one article a day):** ≈ $38 typical; $27–72 range.

**Known price changes ahead**
- GPT-5.6 Sol's promotional price is guaranteed only through 2026-11-21. At an *assumed* $5/$30 (inferred from GPT-5.5; the real price is unpublished), the cost rises by about +$0.20.
- Gemini 3.8 Flash doubles on 2027-01-01, adding about +$0.28.
- Together that makes a typical article about $1.73 in 2027.

**Guardrails.** A $5 cap per run, and budget reviews in Nov 2026 and Jan 2027. Gemini grounding (5k free queries a month) would cut about $0.25 of search fees but stays off (RESEARCH_ARCHITECTURE).

## 23. Answers to the 20 architecture questions

| # | Question | Answer | Where |
|---|---|---|---|
| 1 | CrewAI? | No | FRAMEWORK_EVALUATION |
| 2 | LangGraph? | No; documented Plan B (1.2.x) | FRAMEWORK_EVALUATION |
| 3 | Hybrid? | Yes: DBOS for durable workflows + Pydantic AI for typed agent calls, one job each | FRAMEWORK_EVALUATION |
| 4 | Better framework? | DBOS Transact + Pydantic AI | FRAMEWORK_EVALUATION |
| 5 | Fastest reliable research? | Feeds and official APIs, then OpenAI web search, then httpx + trafilatura, into a dated source ledger | RESEARCH_ARCHITECTURE |
| 6 | Gemini Search primary? | No. Its grounding terms forbid storing, modifying and mixing results. Revisit with a legal waiver. | RESEARCH_ARCHITECTURE |
| 7 | Direct HTTP where? | Feeds, PubMed (incl. abstracts), Federal Register, FDA CSV, and every cited page | RESEARCH_ARCHITECTURE §3 |
| 8 | Browser automation where? | Nowhere by default; an optional profile for allow-listed JS-only pages | RESEARCH_ARCHITECTURE |
| 9 | Parallel research? | `asyncio.gather` with pool and per-host limits inside a DBOS step; tolerates partial failure | RESEARCH_ARCHITECTURE §7 |
| 10 | Workflow state? | DBOS step checkpoints, plus our runs / attempts / agent-runs read model | §5, §15 |
| 11 | Retry failed agents? | Gateway route walking, DBOS transient retries, and fork from the failed step | §5.5, §7.1 |
| 12 | Resume interrupted workflows? | DBOS recovers them automatically when the worker starts; a fork with `application_version` handles version changes | §5.5 |
| 13 | Database? | Own PostgreSQL 16 + pgvector | §3, §15 |
| 14 | Background jobs? | DBOS queues and schedules in `worker`; no Redis or Celery | §3, §5.4 |
| 15 | LLM provider abstraction? | `LLMGateway` (run / search / embed) with per-agent routes; SDKs used only in `app/llm` | §7.1 |
| 16 | Publishing abstraction? | `BlogPublisher` protocol: manual export (default), MDCopilot API (flag), null (mock) | §14 |
| 17 | Cost tracking? | One `blog_llm_calls` row per attempt; pinned prices plus search-fee overrides; frozen price version | §18 |
| 18 | Observability? | Our own tables plus OTel `gen_ai.*` spans (one trace per run); optional Phoenix | §18 |
| 19 | Latency per run? | ≈ 7–12 min typical | §21 |
| 20 | Cost per article? | ≈ $1.25 typical ($0.90–2.40) | §22 |

## 24. Open decisions and assumptions

1. **Gemini grounding.** Off. The owner can seek a legal reading or a written waiver from Google.
2. **Approving a gate-failed version.** Proposed: allowed for admins only, with a written reason that is audited. The alternative is never allowing it.
3. **Production publishing.** Needs a backend-owned service token on MDCopilot; ideally also an idempotency key, SEO fields and a slug lookup. Manual export covers the gap until then.
4. **Public API URL for the novelty sync.** `BLOG_MDCOPILOT_PUBLIC_API_URL` stays blank until the owner provides the production API base URL.
5. **Timezone.** The daily run defaults to 07:00 **Asia/Kolkata**, this machine's timezone. It can be changed in Settings or `.env`.
6. **Deployment target.** Local Docker Compose for now. The production host is decided in Phase 10.
7. **Gemini conversation.** When provided, it updates the brand, pillar and theme settings; no code changes are needed.
8. **Gemini key.** Must belong to a project with billing enabled; verified in Spike S3.
