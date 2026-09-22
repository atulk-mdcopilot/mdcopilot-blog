# MDCopilot Blog

Research topics, generate evidence-linked blog drafts, edit and review versions,
then export or publish an approved version to a configured MDCopilot website.

## Run

All commands run in Docker. The only Compose file is `docker-compose.yml`.

1. Start the MDCopilot root stack first (`docker compose up -d` in the workspace root).
   The blog has no database of its own: it uses the mdcopilot-backend Postgres
   (`DATABASE_URL` in `docker-compose.yml`) over the `mdcopilot_mdcopilot-network` network.
2. Copy `.env.example` to `.env`. Set a `SESSION_SECRET` of
   at least 32 characters (`openssl rand -hex 32`), and administrator credentials.
3. Configure `OPENAI_API_KEY` and `GEMINI_API_KEY` for generation. Anthropic and
   PubMed keys are optional. Missing provider keys do not prevent editing existing drafts.
4. Build and start:

   ```sh
   docker compose up -d --build --wait
   docker compose exec api sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'
   ```

Open http://localhost:8310 and sign in. Migrations, default configuration and
versioned prompts are loaded before the API and worker start. Data lives in the
mdcopilot-backend database: `blog_*` tables, Alembic history in `blog_alembic_versions`
(separate from the backend `alembic_version`), and DBOS state in schema `blog_dbos`.

The Generate page accepts a specific topic; the dashboard can discover one.
Research leads to a draft with citations, fact checking, editorial review and SEO.
Edits create a new version that must be checked and approved before publication.
Generation progress and recovery controls are available from the dashboard.

## Publishing and configuration

`manual_export` is the default publisher: download the article, publish it through
your website, then confirm its public URL in the editor.

For the existing MDCopilot API integration, set `BLOG_PUBLISHER=mdcopilot_api`,
`BLOG_PUBLISHING_ENABLED=true`, the API/public URLs and login credentials in `.env`,
then recreate the containers. The editor supports immediate or scheduled publishing
of an explicitly approved version. An arbitrary website URL alone is not a publishing API.

Settings controls automatic/manual topic selection. Source feeds, domain rules and
research themes are configurable in Sources. Additional environment options and
defaults live in `backend/src/mdcopilot_blog/settings.py`; content defaults live in
`backend/src/mdcopilot_blog/db/seed_data/`. Stored settings take precedence over
environment content defaults. Provider keys and publishing switches stay in `.env`.

For HTTPS deployment, configure a reverse proxy and set `APP_ENV=production`,
`PUBLIC_APP_URL`, `PUBLIC_PROXY_SCHEME=https` and `SESSION_COOKIE_SECURE=true`.
Host ports bind to localhost. The database is the mdcopilot-backend database.

## Code layout

```text
backend/
  src/mdcopilot_blog/
    api/          HTTP routes and request/response models
    auth/         Login, sessions and permissions
    db/           Database models and default configuration
    domain/       Article contracts, scoring and quality rules
    research/     Search, source collection and evidence extraction
    agents/       Prompts and structured generation/review calls
    llm/          Provider calls, concurrency and spending limits
    workflows/    Durable generation, regeneration and publishing jobs
    services/     Article, topic, review and publishing operations
    publishing/   HTML export and the MDCopilot API adapter
  prompts/        Versioned prompt text
  migrations/     Existing database migration history
frontend/src/
  routes/         Dashboard, generation, research, editor and settings
  features/       Blog UI components and API calls
  components/ui/  Shared UI primitives
  lib/           HTTP client, query client and wire types
```

FastAPI enqueues work through DBOS; a separate worker executes it and persists
progress in PostgreSQL. PostgreSQL/pgvector also stores drafts, evidence, versions,
reviews and duplicate-detection embeddings. Nginx serves the React/Vite build and
proxies the API. Spending records remain because generation uses them to enforce budgets.

## Maintenance

```sh
docker compose build
docker compose logs --tail=100 api worker
docker compose stop
```

Back up the mdcopilot-backend database; the blog has no separate database. The migration
history still creates the historical `blog_calendar_slots`/`blog_notifications` tables that the
application no longer uses. Removing those tables can be handled
later through an explicit data migration.

Changing workflow step order requires a new `APP_VERSION`; interrupted jobs from
an older version can be recovered through the run controls. Keep registered prompt
versions immutable and add a new prompt version when changing their text.
