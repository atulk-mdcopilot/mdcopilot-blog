# Implementation Plan — MDCopilot Blog Intelligence

Status: Phase 0 complete (this document set); **Phase 1 built; acceptance passed 2026-09-17** (`scripts/acceptance/phase1.sh`)
Date: 2026-09-17 (revised after independent review)
Design: [ARCHITECTURE.md](ARCHITECTURE.md) · [FRAMEWORK_EVALUATION.md](FRAMEWORK_EVALUATION.md) · [RESEARCH_ARCHITECTURE.md](RESEARCH_ARCHITECTURE.md)

## How each phase runs

1. Inspect what already exists in `mdcopilot-blog/`. Write a task-level plan to `docs/blog-agent/plans/phase-<N>.md` and **stop for review**.
2. Build only that phase. Everything runs in Docker; no Python on the host.
3. Verify with the acceptance checks below. Each is a command or an observable result inside containers. Report results plainly, failures included.
4. No git branches, commits or pushes (spec Rule 10). The owner handles version control.
5. Never modify `mdcopilot-backend` or `mdcopilot-frontend`.

Sizes are relative and used for sequencing only (S ≈ 1–2 days, M ≈ 3–5, L ≈ 1–2 weeks of focused work).

## Owner inputs

| Input | Needed by | Where |
|---|---|---|
| `OPENAI_API_KEY`, `GEMINI_API_KEY` (Gemini project **with billing enabled**) | Phase 2 spikes | `.env` |
| `ANTHROPIC_API_KEY` (optional extra fallback) | Any time | `.env` |
| `NCBI_API_KEY` + contact email (free; raises PubMed from 3 to 10 req/s) | Phase 2 | `.env` |
| `BLOG_FETCH_CONTACT` (URL or email for the crawler User-Agent) | Phase 2 | `.env` |
| Bootstrap admin email and password | Phase 1 | `.env` |
| MDCopilot production public API base URL (novelty sync of published posts) | Phase 3 | `.env` `BLOG_MDCOPILOT_PUBLIC_API_URL` |
| Decision: may an admin approve a gate-failed version (ARCHITECTURE §24.2)? | Phase 5 | reply |
| Local-dev MDCopilot admin account with its login second factor disabled, for the API publisher | Phase 7 | `.env` `BLOG_PUBLISHER_LOGIN_ID` / `BLOG_PUBLISHER_PASSWORD` |
| Confirm daily-run timezone (default `Asia/Kolkata`, 07:00) | Phase 8 | `.env` / Settings |
| Gemini grounding: legal reading or waiver from Google (optional) | Any time | reply |
| MDCopilot backend service token for production publishing (backend team's own task) | After Phase 7 | backend team |
| The Gemini content-strategy conversation (optional) | Any time | paste; it becomes brand, pillar and theme settings |

## Phase 1 — Application foundation (L)

**Build**
- **Bootstrap.** Generate the lock files in throwaway containers (ARCHITECTURE §3), then write `compose.yaml` with these services:
  - `db` (pgvector pg16), `migrate`, `api`, `worker`, `web` (Vite dev), and `tools` (profile).
  - Host ports, all on `127.0.0.1`: web `8310`, api `8300`, db `5440`.
- **Backend image.** `python:3.12-slim` with uv, `pyproject.toml` and `uv.lock`, a non-root user, and `dev` and `runtime` targets.
- **Frontend image.**
  - Vite + React + TypeScript + Tailwind + shadcn/ui + TanStack Query + react-router.
  - The dev server proxies `/api`, with `server.allowedHosts` including `web`.
  - The production target is nginx.
- **Core modules** (`backend/src/mdcopilot_blog/settings.py`, `logs.py`, `ids.py`, `errors.py`). Settings from `.env` (secrets as `SecretStr`); structured JSON logs carrying `run_id` and `trace_id`.
- **Alembic baseline.** Create these tables:
  - `users`, `user_sessions`, `login_attempts`, `audit_log`;
  - `blog_settings`, `blog_brand_profiles` (seeded from spec §8 and §18, including prohibited language and the disclosure text);
  - `blog_content_pillars` (seeded from spec §9);
  - `blog_runs`, `blog_run_attempts`, `blog_agent_runs`, `blog_llm_calls`;
  - `blog_prompt_versions`, `blog_notifications`.
- **Domain.** Typed contracts (ARCHITECTURE §12) and the run, article and publication state machine (§6).
- **Auth.** Argon2 passwords, database sessions, CSRF (token + Origin allowlist + `Sec-Fetch-Site` rule), login rate limit, and `python -m mdcopilot_blog.cli create-admin`.
- **RBAC.** The permission matrix (§17) as one dependency, deny by default.
- **Interfaces, mock implementations only:**
  - `LLMGateway` (`run`, `search`, `embed`), with route parsing from `.env`;
  - `FixtureSearchProvider`;
  - `NullPublisher`.
- **Prompt registry.** Loads `prompts/**/<name>.vN.md`, hashes each file and registers it. Startup fails if a prompt's text changed but its version number did not.
- **DBOS worker skeleton.**
  - `DBOS.launch()` runs in the worker only, with explicit `application_version` and `executor_id`.
  - A `hello_pipeline` workflow with three steps.
  - The API enqueues through `DBOSClient`.
  - The `daily_trigger` wrapper is registered, and its schedule is paused.
- **UI shell.** Login, the spec §25 navigation with placeholder pages, and a role-aware menu.
- **Docs.** `docs/blog-agent/LOCAL_DEVELOPMENT.md` (spec §55). It states that there is no Redis and that DBOS is the queue.

**Spike S1 (first day): DBOS.** Test dbos 3.0.x and 2.31.x in Docker, checking each of the following:
- a schedule with `cron_timezone`;
- pause and resume;
- the wrapper setting the child workflow ID;
- enqueue from the API via `DBOSClient`;
- fork, cancel and list via the client;
- the step-name → `function_id` mapping in a workflow with a loop;
- a forked step that inserts a new row without touching the old one;
- automatic recovery after `docker compose kill worker` mid-step (using `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS`).

**Result:** passed in research on 2026-09-17; pinned `dbos==3.0.0`; re-verified by Task 11 tests and the Task 14 acceptance run (`scripts/acceptance/phase1.sh`). Details are in `plans/phase-1.md`.

**Acceptance**
- `docker compose up -d --wait` leaves `db`, `api`, `worker` and `web` healthy, and `migrate` exits 0.
- `docker compose run --rm tools pytest -q` passes: contracts, state machine, RBAC matrix, prompt registry, auth, CSRF.
- At http://localhost:8310, the bootstrap admin can log in and every nav page renders. A `viewer` gets 403 on `POST /api/blog-agent/runs`.
- A POST made through the Vite proxy from a browser container (`http://web:5173`) passes the CSRF checks.
- Kill the worker during `hello_pipeline` and start it again: the workflow completes, and `blog_agent_runs` shows no repeated completed steps.
- No secrets leak:
  - `docker compose logs api worker | grep -E 'sk-|AIza'` prints nothing;
  - `GET /api/blog-agent/settings` returns keys masked.

## Phase 2 — Research engine (L)

**Spikes first.** These need the API keys and cost about $2 in API usage.
- **S2, OpenAI web search.** Run 20 plain-text calls each on `gpt-5.6-luna` and `gpt-5.6-terra`, at `search_context_size` low and medium, with `max_tool_calls` set to 1 and 2. Measure:
  - how often annotations are present, and how often a sources list is present;
  - `num_requests` per call;
  - input tokens per call;
  - latency P50/P90.
- **S3, Gemini project.**
  - Confirm the billing tier, and read the rate limits in AI Studio.
  - Test `gemini-3.8-flash` structured output on the nested contracts through Pydantic AI.
  - Test `gemini-embedding-2` at 1536 dims.
- **S4, gateway route walking.**
  - Simulate a 503, an `httpx2` timeout and invalid output; confirm each moves to the next model.
  - Confirm there is one `blog_llm_calls` row per attempt.
  - Confirm `usage` cost is populated for the chosen models.
  - Confirm `FunctionModel` fixtures work with `ALLOW_MODEL_REQUESTS=False`.

**Build**
- **Pydantic AI provider adapters** in `app/llm`: OpenAI Responses and Google, plus Anthropic when a key is set.
- **Routing and pricing.** Per-agent routes, call recorder, pricing (pinned `genai-prices` plus `blog_price_overrides` for search actions), and the run cost cap.
- **Web search.** `OpenAIWebSearchProvider` in `app/llm/search/`, in plain-text mode with `max_tool_calls`.
- **Tables.** `blog_source_feeds` and `blog_source_domains` (seeded with the confirmed catalogue and tier rules), `blog_discovery_themes` (seeded with the 15 spec §7 themes), `blog_price_overrides`, `blog_sources`, `blog_research_runs`, `blog_research_findings`, `blog_finding_sources`.
- **Collectors.** RSS/Atom with per-feed quirks; PubMed (`esearch`, `esummary`, `efetch` abstracts); Federal Register; FDA AI-device CSV diff.
- **Retriever.** httpx HTTP/2, per-host limits, Protego robots.txt, SSRF guard, conditional GET, bot-wall detection.
- **Extraction and ledger.**
  - Extractor: trafilatura, htmldate, newspaper4k fallback, pypdfium2.
  - Source ledger with tiers, canonical URLs, `date_source` and `access_mode`.
- **Research.**
  - Query planner with theme rotation.
  - **Research Analyst** agent, with claim rules enforced in code.
  - `record-fixtures` CLI and a full mock fixture set.
- **UI.**
  - Research page: runs, themes covered, typed findings with sources and dates, per-phase latency.
  - Sources page: ledger, feed health, tiers, themes.

**Acceptance**
- In mock mode, the broad scan finishes in under 10 s, and every `FACT` finding cites a ledger ID.
- The live broad scan:
  - returns at least `min_source_count` dated sources;
  - has zero findings that cite a URL missing from the ledger (enforced and tested);
  - writes a `blog_llm_calls` row with `search_actions` and non-zero cost for every search call;
  - stores latency for each phase.
- A recorded PubMed fixture produces a source with non-empty abstract text and `access_mode=abstract_only`.
- Failure tests pass:
  - one feed is down;
  - a search call returns 5xx, and coverage stays partial;
  - a blocked page becomes a metadata-only source;
  - invalid analyst output is retried and then escalates to the next model.

## Phase 3 — Topic intelligence (M)

**Build**
- **Topic Strategist** agent. Its schema enforces exactly 3 candidates.
- **Novelty.**
  - Tables: `blog_topic_candidates`, `blog_topics`, `blog_external_posts`.
  - `sync_mdcopilot_posts`: read-only, pages through the public `GET /api/v1/blogs`, and stays off while its URL setting is blank.
  - Embeddings and the novelty engine (ARCHITECTURE §8), with the regeneration loop (at most 2 rounds).
- **Scoring.** The model from §9, with configurable weights and a stored breakdown.
- **Workflow.** `discover_topics` D1–D7 in auto and manual modes, plus `regenerate_topics`.
- **UI.** Today's Ideas cards (score breakdown, novelty neighbours, sources) and the Topics page (history and external posts, with similarity search).

**Acceptance**
- There are always exactly 3 candidates, or a flagged shortfall after 2 regeneration rounds.
- A seeded near-duplicate of an **external** MDCopilot post is rejected, and the neighbour and similarity are shown.
- Weighted totals match a fixture computed by hand.
- `POST /topics/generate` returns 3 new candidates that do not repeat the previous round.
- Manual mode stops at `WAITING_FOR_TOPIC`. Selecting a candidate then enqueues production (stubbed until Phase 4).

## Phase 4 — Article generation (M)

**Build**
- **Research packet.** The **Deep Research Analyst** agent, and `blog_research_packets` (versioned, with a summary).
- **Writer agent.**
  - Produces a typed `ArticleDraft`: 3 headlines, pull quote, CTA and citation markers.
  - Inputs: the avoid bundle and recent articles (§8.1, §11).
  - Deterministic assembly and positional parsing.
  - Revise mode records a resolution for each finding.
  - Component regeneration covers headline, introduction, section, pull quote and CTA.
- **Tables.**
  - `blog_articles`.
  - `blog_article_versions`: an **UPDATE-blocking trigger**.
  - Side tables: `blog_version_embeddings`, `blog_version_features`, `blog_article_sources`.
  - Version history and diff API.
- **Workflows.** `produce_article` P1–P3 (the later steps are stubbed), plus `regenerate_component` and `regenerate_research` in skeleton form.

**Acceptance**
- The word-count and structure checks pass on the draft fixture. In live mode, the drafts from the 5 validation runs are recorded.
- Unknown citation markers are rejected.
- Regenerating one section creates exactly one new version, and every other section stays byte-identical.
- Regenerating research creates a new packet version and keeps the old one.
- Any UPDATE on `blog_article_versions` fails at the database level.
- A save whose H2 count is wrong returns 422.

## Phase 5 — Quality system (M)

**Build**
- **Fact Checker.** Extracts claims with kind, location and markers, including attributions and anecdotes, per ARCHITECTURE §10. Enforces vendor independence. Stores results in `blog_claim_checks`, with ≤3 verification searches.
- **Reviewers.** **Clinical Reviewer** (including invented-anecdote detection) and **Editorial Reviewer** (with the avoid bundle), run in sequence. Results go in `blog_reviews`.
- **SEO Specialist.** The full spec §22 output, internal link suggestions from published and external posts, and LinkedIn, X and newsletter copy. Stored in `blog_version_seo`.
- **Gates.** All 15 gates from §10, including the numeric scan that excludes years, ordinals and times, the diversity checks, and the **one fix pass**.
- **Workflows.** `produce_article` P4–P10, `recheck_article`, and full `regenerate_article`.
- **Owner decision.** Apply the owner's gate-override policy.

**Acceptance (mock mode: routing)**
- An invented-statistic fixture leads to a fix pass, and then to either `READY_FOR_REVIEW` with the statistic removed or `QUALITY_GATE_FAILED` naming gate 3.
- The same applies to an invented quote (gate 4), an invented anecdote (gate 5) and a prohibited phrase (gate 10).
- The numeric-scan false-positive fixture passes. It includes "In 2026", "24/7" and "Step 2".
- Regenerating the article creates new versions and keeps the old ones.
- A full mock daily run reaches `READY_FOR_REVIEW` in under 60 s, with all gates recorded on the final version and a fact check recorded for that exact version.

**Acceptance (live evaluation, stated pass rate):** 10 seeded drafts per defect type (invented statistic, invented quote, invented anecdote, autonomous-clinical-decision claim). The detection rate for each type is reported, with a target of at least 9 out of 10.

## Phase 6 — Review dashboard (L)

**Build**
- **Dashboard.** A **Today card** (spec §57), pipeline tracker, metrics and diversity panel. Also Drafts, Review Queue and Published pages.
- **Article review split screen.**
  - Left: the 3 candidates with scores, the packet, sources, claim checks, a quality summary, gate results and structured summaries.
  - Right: CodeMirror editor, sanitised preview, headline picker, SEO/tags/category editor, versions and diff.
- **Actions.** Every human action is wired to the API with role-aware visibility, and reject requires a reason.
- **Content Calendar** (FullCalendar, MIT parts only), with `blog_calendar_slots`.
- **Settings.** All spec §50 fields: routes, brand, pillars, themes, and schedule time/timezone (saving enqueues `apply_schedule`). Keys are masked. Auto-publish shows as locked OFF.
- **Agent Runs timeline**, with retry, restart-from, restart and cancel.

**Acceptance**
- Vitest suites cover topic selection, review, approve, reject, regenerate, export/publish and permission gating.
- A Playwright smoke test in a container runs select topic → open article → edit → save (new version) → re-check → approve.
- A reject stores the reason and writes an `audit_log` row.
- A `viewer` sees no mutating controls, and the API rejects those calls anyway.
- The preview never renders raw HTML from the model (XSS fixture).

## Phase 7 — Publishing (M)

**Spike S5: local MDCopilot publisher.** Against the local backend, using the dev admin account:
1. Log in, then read the access-token cookie.
2. Call with `Authorization: Bearer` and confirm the CSRF behaviour for bearer-only requests.
3. Create a draft.
4. Simulate a client timeout after the create.
5. Reconcile by exact slug.
6. Confirm exactly one post exists.
7. Confirm that PUT with `slug` keeps the URL.

**Build**
- **Renderer.**
  1. markdown-it-py (`js-default`, tables off), then nh3 with the Quill-safe allowlist.
  2. Pull-quote blockquote and references.
  3. Mandatory disclosure.
- **ManualExportPublisher (default).**
  - Export bundle, with rich-text clipboard copy and field copy buttons.
  - Download, and `confirm-published`.
  - Article moves `APPROVED → EXPORTED → PUBLISHED`.
- **MDCopilotApiPublisher (behind the flag).**
  - Logs in with credentials.
  - Creates or updates, always sending `slug`, as draft or published.
  - Validates field limits.
  - Reconciles with `find_existing`.
  - Uses `BLOG_PUBLISHER_PUBLIC_URL` for `published_url`.
  - Handles `PUBLISH_FAILED` with retry.
- **Tables.** `blog_publications`, with its unique constraints.
- **Scheduling.**
  - `SCHEDULED` state and a `publish_due` job every 5 minutes.
  - In manual mode, a due article is exported and a notification is sent.
  - In network mode, the job re-checks that the scheduler holds `blog.publish`.
- **Test double.** A fake MDCopilot API container that **mirrors the real behaviour**: search ignores slug, PUT without a slug regenerates it, and duplicate slugs are rejected.

**Acceptance**
- Rendered HTML contains only allow-listed tags; `javascript:` links and `<script>` are stripped.
- With default settings (`BLOG_PUBLISHING_ENABLED=false`):
  - `/export` and `/confirm-published` work;
  - every network publish path returns 409, and nothing is sent.
- On the fake API, publishing twice, or retrying after a timeout that followed a successful create, results in **exactly one** post.
- A scheduled article is handled exactly once at its time, and a second tick does nothing.
- Manual check: paste the exported bundle into the local MDCopilot admin BlogEditor and save. `/blog/{slug}` then shows the headings, links, blockquote, references and disclosure.
- The S5 flow creates a draft on the local MDCopilot backend.

## Phase 8 — Automation (M)

**Build**
- **Daily schedule.**
  - Built from settings: wrapper, `daily-YYYY-MM-DD` ID, a same-day startup check, and skipping a date that a manual run already covers.
  - Paused until `BLOG_AGENT_SCHEDULER_ENABLED=true`.
- **Maintenance workflow.** Post sync, DBOS record pruning and feed-health roll-up.
- **Notifications.**
  - In-app, plus an optional webhook (`BLOG_NOTIFY_WEBHOOK_URL`).
  - Events: `READY_FOR_REVIEW`, `QUALITY_GATE_FAILED`, `FAILED`, `PUBLISH_FAILED`, scheduled export due.
- **Validation period.** 5 live manual runs, reviewed by the owner, before the scheduler flag is turned on.

**Acceptance**
- A test schedule set to the next minute creates one run, and a duplicate trigger creates none.
- With `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=20`, killing the worker during the Writer step resumes the run without repeating completed steps.
- A forced failure at P4 can be retried from P4, and earlier versions are kept.
- **One live daily run** reaches `READY_FOR_REVIEW` and is exported, with cost rows and a `trace_id` on every call.
- The 5 validation runs are reviewed, and the owner explicitly approves enabling the schedule.

## Phase 9 — Observability and FinOps (S–M)

**Build**
- OpenTelemetry setup (`gen_ai.*` spans; one `trace_id` per run, stored on the run), plus the optional `observability` profile with Phoenix.
- Cost views: today, week, month, per article, per research run, per topic, per agent and per model. Also a price-override UI and an optional reconciliation against the OpenAI Costs API.
- Dashboard metrics (spec §26), and measured P50/P90 per stage replacing the estimates in ARCHITECTURE §21–§22.

**Acceptance**
- Dashboard totals equal the SQL sum of `blog_llm_calls` over the same window (tested).
- Every `blog_llm_calls` row has `run_id` and `trace_id`.
- Per-article cost is shown on the article page.
- Phoenix is optional and not part of acceptance.

## Phase 10 — Production hardening (M)

**Build and verify**
- **Security review.** Secrets, SSRF, XSS, CSRF, RBAC and prompt injection; fix the findings.
- **Testing.**
  - RBAC matrix across every route.
  - Failure-injection suite (spec §53).
  - Light load test: 20 concurrent human actions plus one daily run.
- **Database and data.**
  - Alembic upgrade and downgrade on a copy.
  - Postgres backup/restore runbook.
  - DBOS retention.
  - Retention for the source-snapshot text.
- **Production Compose profile.** nginx web, no reload, resource limits, restart policies, digest-pinned images.
- **Client addresses behind the proxy.** The dev `api` ignores proxy headers (`--no-proxy-headers`), and the runtime image's default command still trusts every sender (`--forwarded-allow-ips "*"`). For production, trust only the nginx container's address. nginx must set `X-Forwarded-For` to `$remote_addr`, not append to it with `$proxy_add_x_forwarded_for`. Otherwise clients choose the IP that the login rate limit records.
- **Deployment doc.** The target host is decided with the owner.
- **Optional.** TOTP MFA; a prompt-version rollback drill.

**Acceptance**
- The security review has no open critical or high findings.
- All suites pass in Docker.
- Restoring a backup to a fresh volume brings back runs, articles and versions.
- In the production profile, only `web` is exposed.

## Definition of done (spec §60) → where it is verified

| Requirement | Verified in |
|---|---|
| Daily trigger → research → extraction → synthesis → 3 candidates → novelty → scoring → selection → deep research → writing → fact check → clinical → editorial → SEO → gates → `READY_FOR_REVIEW` | Phase 5 (mock), Phase 8 (live daily run) |
| Human review UI → edit / regenerate / approve → publish or export → published | Phase 6 smoke test, Phase 7 manual paste check and S5 |
| Manual generation | Phase 3 (manual mode); Phase 8 live runs |
| Topic selection / topic regeneration | Phase 3 |
| Article / section / research regeneration | Phase 4, Phase 5 |
| Human editing, approval, rejection | Phase 6 |
| Scheduling | Phase 7 |
| Publishing + retry, no duplicates | Phase 7 |
| Resume | Phase 1 (S1), Phase 8 |
| Historical versions | Phase 4 |
| Source tracking | Phase 2 |
| Agent tracing | Phase 1 (rows), Phase 9 (traces) |
| Cost tracking | Phase 2 (rows), Phase 9 (views) |

## Top risks

| Risk | Phase | Mitigation |
|---|---|---|
| DBOS 3.0 immaturity; client capabilities | 1 | Spike S1, version pin, control-workflow fallback, Plan B = LangGraph 1.2.x |
| OpenAI web search citations and token size | 2 | Spike S2, plain-text calls, `max_tool_calls`, cost cap |
| Bot-walled Tier-1 publishers | 2 | Feeds, PubMed abstracts, DOI metadata; no bypassing |
| Latency above the estimate | 2–5 | Per-stage output caps; measured P50/P90; per-workflow timeouts (15 / 30 min) |
| Gemini price doubling (2027-01-01); end of Sol promotion (after 2026-11-21) | 9 | Per-agent routes in Settings, cost dashboards, budget review |
| Production publishing blocked by MFA | 7 | Manual export by default; service-token request to the backend team |
| Scope size | all | Owner review at each phase gate; mock mode keeps UI work free of API spend |
