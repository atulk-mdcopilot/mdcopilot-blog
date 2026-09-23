# MDCopilot Blog

Internal service that turns a topic into a researched, fact-checked blog draft and saves it as a **draft in
MDCopilot Blogs** (the mdcopilot-backend `blogs` table). It has no UI, no users and no database of its own.
An MDCopilot ADMIN uses it from mdcopilot-frontend: **Admin -> Generate Blogs** (`/admin/blogs/generate`);
the draft is then edited and published on the existing **Admin -> Blogs** pages.

```text
mdcopilot-frontend  ->  mdcopilot-backend /api/v1/admin/blog-agent/runs*   (require_admin_access)
                              |  X-Internal-Token + X-On-Behalf-Of: <users.id>
                              v
                        blog api (http://blog-api:8000)  --DBOS queue-->  blog worker
                                                                              |  POST /internal/v1/blog/drafts
                                                                              v
                                                                        mdcopilot-backend blogs (status=draft)
```

Details: [docs/architecture.md](docs/architecture.md) (API, pipeline, tables, settings) and
[docs/business_logic.md](docs/business_logic.md) (what the pipeline checks and why).

## Run

Everything runs in Docker. Never run Python on the host.

The blog has no compose file of its own: the workspace-root `docker-compose.yml` runs it with the rest of
MDCopilot (services `blog-api` and `blog-worker`, on the root network, using the root Postgres).

1. Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` (required: web search). `GEMINI_API_KEY` is
   optional but recommended (the default research and review routes put Gemini first; a provider without a key
   is skipped). Anthropic and NCBI keys are optional.
2. `docker compose up -d` in the workspace root starts everything, the blog included.

Services: `blog-api` (starts once postgres and the backend are healthy; applies migrations on startup:
`alembic upgrade head`, DBOS system tables, seed, prompt sync; then serves; no host port) and `blog-worker`
(starts once `blog-api` is healthy). The root `docker-compose.yml` sets `DATABASE_URL` and the development
service tokens, which match the backend's (`BLOG_INTERNAL_TOKEN` = backend `BLOG_AGENT_INTERNAL_TOKEN`,
`BACKEND_INTERNAL_TOKEN` = backend `INTERNAL_TOKEN`).

Data lives in the mdcopilot-backend database: 20 `blog_*` tables, Alembic history in `blog_alembic_versions`
(separate from the backend's `alembic_version`) and DBOS state in schema `blog_dbos`. Blog data is
disposable working state; the finished article lives in the backend `blogs` table.

One run = one topic, about 5 minutes and roughly 0.5 USD with the default routes. Runs execute one at a time
(worker concurrency 1) and each is capped by `BLOG_AGENT_MAX_COST_PER_RUN_USD`.

## Code layout

```text
backend/
  src/mdcopilot_blog/
    api/          4 run routes + health, internal-token dependency
    workflows/    DBOS workflows discover_topics (manual topic) and produce_article
    services/     the work done inside each workflow step
    agents/       deep research analyst, writer, fact checker, clinical, editorial and SEO reviewers
    research/     web search, page retrieval (SSRF guard, robots), extraction, PubMed, source ledger
    llm/          provider calls, route fallback, price recording, per-run budget guard
    domain/       article structure, quality gates, state machine, contracts
    publishing/   Markdown -> sanitised HTML renderer, mdcopilot-backend draft client
    db/           models, engine, seed data (brand profile, pillars, source domains, price override)
  prompts/        versioned prompt text (immutable once registered; add a new version to change one)
  migrations/     one Alembic revision, 0001
```

## Maintenance

```sh
# from the workspace root
docker compose logs --tail=100 blog-api blog-worker
docker compose exec blog-api python -m mdcopilot_blog.cli migrate   # also: migrate-dbos, seed, sync-prompts
# from this directory
docker build --target dev -t mdcopilot-blog-backend:dev-tmp backend   # image with ruff, for lint/format
```

Changing workflow steps requires a new `APP_VERSION`: DBOS only recovers workflows of the running version.

## Removed in the 2026-09-22 minimization

The standalone React app (`frontend/`, `web` service), own login/sessions/CSRF/roles, audit log, settings and
sources screens, topic discovery and daily schedules, novelty/duplicate detection and embeddings (pgvector),
article editing/regeneration/approval, manual export, scheduling and the login-based publisher. The UI now
lives in mdcopilot-frontend; authentication is mdcopilot-backend's ADMIN check.
