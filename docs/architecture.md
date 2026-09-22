# MDCopilot Blog: architecture

State after the 2026-09-22 minimization. Product rules (what each review checks, the gates) are in
[business_logic.md](business_logic.md). Workspace-level contracts and the decision record are in
`docs/blog-minimization/` at the workspace root (`CONTRACTS.md`, `PLAN.md`).

## 1. What it is

A FastAPI api and a DBOS worker that research a topic, write a blog article, review it and save it as a
draft in mdcopilot-backend. No frontend, no users, no database of its own. The only caller of the api is
mdcopilot-backend; the only thing the worker calls inside MDCopilot is the backend's internal draft route.

| Compose service | Command | Notes |
| --- | --- | --- |
| `api` | `python -m mdcopilot_blog.cli migrate && exec uvicorn --factory mdcopilot_blog.api.app:create_app` | migrations first (alembic upgrade head, DBOS system tables, seed, prompt sync; idempotent), then serves; network alias `blog-api`, port 8000 on the Docker network only, healthcheck `/readyz` |
| `worker` | `python -m mdcopilot_blog.worker` | waits for the api to be healthy (so migrations are done); executes queue `pipeline`, worker concurrency 1, heartbeat-file healthcheck |

The compose project joins the root stack's network `mdcopilot_mdcopilot-network` (external), so `postgres`
and `backend` resolve. Start the root stack first.

## 2. How it is called

```text
browser (ADMIN) -> mdcopilot-backend /api/v1/admin/blog-agent/runs[/{id}[/cancel]]   cookie auth, require_admin_access
                -> blog api          /api/blog-agent/runs[/{id}[/cancel]]            X-Internal-Token + X-On-Behalf-Of
```

Every `/api/*` route requires `X-Internal-Token` (constant-time compare with `BLOG_INTERNAL_TOKEN`; unset
setting = 503, missing or wrong = 401) and `X-On-Behalf-Of` = the acting admin's backend `users.id`
(`^[A-Za-z0-9_.:-]{1,64}$`, else 400). The id is stored as `blog_runs.created_by` and becomes the draft's
author. `/healthz` and `/readyz` are open. JSON is camelCase; errors are problem+json.

| Route | Body / query | Response |
| --- | --- | --- |
| `POST /api/blog-agent/runs` | `topic` (3..300), optional `wordCount` (300..3000), `tone`, `audience` | 202 `Run` |
| `GET /api/blog-agent/runs` | `limit` 1..100 (20), `offset` | `{items, total, limit, offset}`, newest first |
| `GET /api/blog-agent/runs/{id}` | - | `Run` + `steps[]` |
| `POST /api/blog-agent/runs/{id}/cancel` | - | `Run`; 409 when already terminal |

`Run.status`: `QUEUED`, `RESEARCHING`, `TOPICS_READY`, `PRODUCING`, then terminal `SUCCEEDED`, `FAILED` or
`CANCELLED`. `SUCCEEDED` means the draft was saved to MDCopilot Blogs; `Run.draft` is then
`{blogId, title, gatesPassed, gateProblems[]}`. `FAILED` carries `error: {class, message}`.

## 3. Pipeline

The api inserts a `blog_runs` row and enqueues workflow `discover_topics` on queue `pipeline`; that workflow
enqueues `produce_article`. Every stage is a DBOS step recorded in `blog_agent_runs` (name, status, tries,
model, cost, duration). Registered step names are in `workflows/names.py`.

| Step | What it does |
| --- | --- |
| `discover.manual_topic`, `discover.select_topic` | store the typed topic as a candidate, promote it to a topic |
| `produce.deep_research` | planned web searches (OpenAI web search), page retrieval with SSRF guard and robots check, text extraction, PubMed abstracts; needs enough dated sources and one trusted source with text, else `insufficient_evidence` |
| `produce.build_research_packet` | Deep Research Analyst turns at most 20 sources into the writing packet |
| `produce.write_draft` | Writer produces version 1 (7 sections, title options, excerpt, CTA, citations) |
| `produce.fact_check` | Fact Checker on a route ordered so the writer's provider comes last; invalid claims are dropped, not the whole answer |
| `produce.clinical_review`, `produce.editorial_review` | blocking clinical flags and required editorial changes |
| `produce.revise`, `produce.verify_facts` | only when reviews produced required findings: new version, facts re-checked |
| `produce.seo` | SEO title, meta description, slug |
| `produce.quality_gates` | deterministic gates (13 blocking, 1 warning) |
| `produce.fix_pass.*` | at most one repair pass when a fixable gate failed |
| `produce.push_draft` | render the current version to sanitised HTML, `POST {BACKEND_INTERNAL_URL}/internal/v1/blog/drafts`, store `backend_blog_id` + `draft_report`, article `DRAFT_SAVED`, run `SUCCEEDED` |

**A finished draft is never lost to a review failure.** Once `write_draft` has produced a version, an
exception in any later review stage is caught, and `push_draft` still saves the newest version; the problem
is reported in `draft.gateProblems` with `gatesPassed=false`. A run is `FAILED` only when no draft version
exists, the push itself fails, or the run is cancelled. The push happens at most once per article.

The backend route inserts a `status="draft"` row in `blogs` (author must be an active ADMIN; the slug is
de-duplicated by the backend). Editing and publishing are the existing MDCopilot Blogs pages.

LLM calls go through `llm/gateway.py`: ordered `provider:model` routes with fallback (a provider without a
key is skipped), every call priced and stored in `blog_llm_calls`, and a per-run budget guard
(`BLOG_AGENT_MAX_COST_PER_RUN_USD`). Transient database/connection errors retry up to 6 times with backoff.

## 4. Data

In the mdcopilot-backend database, schema `public`, prefix `blog_`. One Alembic revision (`0001`), history
table `blog_alembic_versions`, autogenerate filtered to `blog_` tables. DBOS state is in schema `blog_dbos`.
The blog neither creates nor drops the `vector` extension and has no vector column.

| Tables | Purpose |
| --- | --- |
| `blog_runs`, `blog_run_attempts`, `blog_agent_runs` | run, workflow attempt, one row per executed step |
| `blog_topic_candidates`, `blog_topics` | the typed topic as a writer brief, and its promoted form |
| `blog_research_runs`, `blog_sources`, `blog_source_domains` | research executions, the source ledger, per-domain tier and fetch policy (seeded) |
| `blog_articles`, `blog_research_packets`, `blog_article_versions`, `blog_version_seo`, `blog_article_sources` | article, packet, immutable content versions, SEO, citations |
| `blog_reviews`, `blog_claim_checks` | fact-check, clinical, editorial and gate reports; per-claim results |
| `blog_llm_calls`, `blog_price_overrides`, `blog_prompt_versions` | spend log, price override (seeded), prompt registry |
| `blog_brand_profiles`, `blog_content_pillars` | seeded brand voice and pillars |

`blog_article_versions` rows are immutable: a `BEFORE UPDATE` trigger raises `restrict_violation`. Two
circular foreign keys (`blog_articles.current_version_id`, `blog_research_runs.article_id`) are added after
table creation. The trigger and those two keys are hand-written in `0001`; autogenerate does not emit them.
`blog_runs.created_by` is text (backend `users.id`), not a foreign key.

## 5. Settings

Environment only (`settings.py`); there is no settings table or screen.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | set by compose | mdcopilot-backend database |
| `BLOG_INTERNAL_TOKEN` | set by compose | inbound token; unset = every `/api/*` call is 503 |
| `BACKEND_INTERNAL_URL`, `BACKEND_INTERNAL_TOKEN` | set by compose | where and how the worker saves the draft; unset = the push fails the run |
| `BACKEND_TIMEOUT_SECONDS` | 20 | draft POST timeout |
| `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` | - | provider keys; OpenAI is required for web search |
| `NCBI_API_KEY`, `NCBI_CONTACT_EMAIL` | - | optional PubMed key |
| `APP_ENV`, `APP_VERSION`, `LOG_LEVEL` | development, 0.1.0, INFO | `APP_VERSION` is the DBOS application version: bump it when workflow steps change |
| `BLOG_AGENT_ENABLED` | true | false = new runs are refused and the worker idles |
| `BLOG_AGENT_MAX_COST_PER_RUN_USD` | 5.00 | per-run spend cap |
| `BLOG_AGENT_WORD_COUNT_MIN` / `_MAX` | 850 / 1150 | default length; a run's `wordCount` overrides it |
| `BLOG_AGENT_{SEARCH,DEEP_RESEARCH,WRITER,FACT_CHECK,CLINICAL,EDITORIAL,SEO}_ROUTE` | see `.env.example` | ordered model routes |
| `BLOG_SITE_URL`, `BLOG_DEFAULT_CATEGORY` | mdcopilot.health, Healthcare AI | used in prompts and the fetch user agent |

Research window, minimum source count, fetch limits, timeouts and concurrency also have environment names
and working defaults in `settings.py`. In development the two tokens are static values set in both compose
files. Outside development mdcopilot-backend refuses a configured static token, so the feature is off there
until a service-to-service scheme exists; the blog has no production deployment.

## 6. Removed and where things live now

Removed on 2026-09-22: the React app and `web` service, own users/sessions/CSRF/RBAC, audit log, the
settings/sources/research/dashboard/topics/articles/quality/publishing routers, run restart/resume/step
retry, schedules and daily discovery, feed collectors, novelty/diversity/duplicate detection, embeddings and
pgvector, external-post sync, article editing/regeneration/approval, manual export, scheduling, the
login-based publisher and 15 tables. The UI is mdcopilot-frontend (`/admin/blogs/generate`, `/admin/blogs`);
authentication and the ADMIN check are mdcopilot-backend's.
