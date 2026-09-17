# Local development: MDCopilot Blog Intelligence (`mdcopilot-blog`)

Status: Phase 1 (application foundation)
Companion docs: [ARCHITECTURE.md](ARCHITECTURE.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [FRAMEWORK_EVALUATION.md](FRAMEWORK_EVALUATION.md) · [RESEARCH_ARCHITECTURE.md](RESEARCH_ARCHITECTURE.md)

Everything runs in Docker. Do not install or run Python, pip, uv, Node or npm on your machine. The host needs only:
- Docker Desktop with Docker Engine 25 or newer, which the healthchecks' `start_interval` needs. The stack was verified on Engine 29.8 with Compose v5.5.1. Older Compose v2 releases may fail `docker compose up --wait` when the one-shot `migrate` service exits, so update Docker Desktop if that happens.
- `curl`, `openssl` and `jq`, which ship with macOS.

Run every command below from the `mdcopilot-blog/` folder.

## 1. Lock files (first-time bootstrap and dependency changes)

The lock files are generated in throwaway containers, because there is no Python or Node on the host:

```bash
docker run --rm -v "$PWD/backend:/work" -w /work -e UV_PYTHON_DOWNLOADS=0 ghcr.io/astral-sh/uv:0.12.15-python3.12-trixie-slim uv lock
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npm install --package-lock-only
```

`backend/uv.lock` and `frontend/package-lock.json` already exist and are committed by the owner. Run these again only when you change dependencies.

**Add a backend dependency.**
1. Add it with uv in a container (the package below is only an example):
   ```bash
   docker run --rm -v "$PWD/backend:/work" -w /work -e UV_PYTHON_DOWNLOADS=0 ghcr.io/astral-sh/uv:0.12.15-python3.12-trixie-slim uv add --no-sync "httpx-sse>=0.4,<0.5"
   ```
   For a test or lint tool, run the same container command with `uv add --no-sync --group dev "<package spec>"` at the end.
2. Rebuild the backend image and recreate the services that use it:
   ```bash
   docker compose build tools
   docker compose up -d --wait
   ```

**Add a frontend dependency.**
1. Add it with npm in a container (the package below is only an example). `--package-lock-only` updates `package.json` and the lock file without creating a host `node_modules`:
   ```bash
   docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npm install --package-lock-only --save-exact date-fns@4.1.0
   ```
   Add `-D` for a dev dependency.
2. Rebuild the image and replace the container's `node_modules` volume:
   ```bash
   docker compose up -d --build --renew-anon-volumes web
   ```

**Never mix DBOS versions.** `dbos` is pinned to exactly `3.0.0`, and `api` and `worker` share one image. An older DBOS client against a 3.0 database silently returns `None` results.

## 2. Environment file

1. Create the file and restrict it to your user:
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```
2. Generate the two local secrets, then paste each value into `.env` in your editor:
   ```bash
   openssl rand -hex 32   # SESSION_SECRET (at least 32 characters)
   openssl rand -hex 24   # POSTGRES_PASSWORD (hex only: no spaces or URL-special characters)
   ```
3. Set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` (any non-empty value; use a strong password before the app is reachable from anywhere but localhost) for the first admin account.
4. Leave the safety switches at their defaults for Phase 1:

   | Switch | Phase 1 value | Why |
   |---|---|---|
   | `BLOG_AGENT_MOCK_MODE` | `true` | Real providers are built in Phase 2 |
   | `BLOG_AGENT_SCHEDULER_ENABLED` | `false` | The daily run stays paused until the validation runs are approved (Phase 8) |
   | `BLOG_PUBLISHING_ENABLED` | `false` | Publishing arrives in Phase 7 |
   | `BLOG_HUMAN_APPROVAL_REQUIRED` | `true` | The app refuses to start with `false` |
   | `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS` | `0` | Only raised while testing crash and resume |

**Rules for `.env`.**
- Never print it, paste it into chat or tickets, or copy its values into other files.
- `docker compose config` prints every value from `.env`, secrets included. Use `docker compose config --quiet` to validate the file instead.
- After you edit `.env`, run `docker compose up -d`. That recreates the containers whose environment changed. `docker compose restart` does **not** reload `.env`.
- `POSTGRES_PASSWORD` is applied only when the database volume is first created. Changing it later breaks the connection until the volume is recreated (see section 12).

Check the file without printing any value:

```bash
docker compose run --rm --no-deps tools sh -c 'test ${#SESSION_SECRET} -ge 32 && echo "SESSION_SECRET ok" || echo "SESSION_SECRET too short"'
```

## 3. Provider API keys

| Key | Used for | Needed by |
|---|---|---|
| `OPENAI_API_KEY` | Web search (Responses API) and OpenAI entries in the model routes | Phase 2 |
| `GEMINI_API_KEY` | Gemini reasoning and embeddings. The Google project **must have billing enabled** (paid tier). | Phase 2 |
| `ANTHROPIC_API_KEY` | Optional. While it is empty, `anthropic:*` entries in the routes are skipped. | Any time |
| `NCBI_API_KEY` + `NCBI_CONTACT_EMAIL` | Optional, free. Raises the PubMed limit from 3 to 10 requests per second. | Phase 2 |

How keys are handled:
- Keys are read only from the environment (as `SecretStr`). They are never logged or put in prompts.
- Settings (`GET /api/blog-agent/settings`, and the Settings page later) shows only whether each key is set, plus a masked preview such as `sk-…abcd`.
- In Phase 1 mock mode no key is used. The app runs with every key empty.
- **Rotate a key:** edit `.env`, then run `docker compose up -d`.

Model names live only in the `BLOG_AGENT_*_ROUTE` variables. Each is an ordered `provider:model` list with the primary model first.

## 4. What runs where

| Service | What it is | Host address |
|---|---|---|
| `db` | Postgres 16 + pgvector (digest-pinned image). Schema `app` is managed by Alembic; schema `dbos` belongs to DBOS. It receives only `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` from `.env`. | `127.0.0.1:5440` |
| `migrate` | One-shot: Alembic upgrade, DBOS system migrations, seed data, prompt sync. Exits 0. | none |
| `api` | FastAPI (`uvicorn --reload --no-proxy-headers`). Enqueues workflows through `DBOSClient` and never runs them. | `http://127.0.0.1:8300` |
| `worker` | The only process that calls `DBOS.launch()`. Runs workflows, queues and schedules. | none |
| `web` | Vite dev server for the React dashboard. Proxies `/api` to `api:8000`, so the app is same-origin. | **http://localhost:8310** |
| `tools` | Profile `tools`: pytest, ruff, mypy, alembic and CLI commands, run with `docker compose run --rm tools …`. | none |

Ports bind to `127.0.0.1` only. Change them with `DB_HOST_PORT`, `API_HOST_PORT` and `WEB_HOST_PORT` in `.env`.

**No Redis.** DBOS is the queue. Workflow state, queues (`pipeline` with concurrency 1, `interactive` with concurrency 4) and the daily schedule all live in Postgres (schema `dbos`), as do sessions and login rate limits (schema `app`). There is no Redis, Celery or separate scheduler container.

Code layout:

```text
backend/src/mdcopilot_blog/   settings, logs, ids, errors, cli, worker
  domain/ db/ api/ auth/ services/ llm/ prompts/ workflows/ publishing/
backend/prompts/              <agent>/<name>.v<N>.md
backend/fixtures/mock/        llm/<agent>/<prompt>.json, search/default.json
backend/migrations/           Alembic
backend/tests/                unit/ db/ api/ workflows/
frontend/src/                 app/ routes/ features/ components/ lib/
scripts/acceptance/phase1.sh  Phase 1 acceptance run
```

## 5. Selected framework

The framework decision is **DBOS Transact 3.0.0 + Pydantic AI 2.43**. The reasoning is in [FRAMEWORK_EVALUATION.md](FRAMEWORK_EVALUATION.md).

**DBOS Transact** (library, Postgres only) provides:
- durable workflows and steps;
- queues and cron schedules;
- automatic recovery after a crash;
- `fork_workflow` for "restart from step".

**Rules for DBOS in this app:**
- `api` only enqueues, lists, forks and cancels, through `DBOSClient`.
- `worker` is the single executor.
- Recovery after a crash needs the same `WORKER_EXECUTOR_ID` (`worker-1`, set in `compose.yaml`) and the same `APP_VERSION` (from `.env`).

**Pydantic AI** (`pydantic-ai-slim[openai,google,anthropic]`) provides typed agent calls. Only `mdcopilot_blog.llm` imports it, behind `LLMGateway`. In Phase 1 the gateway uses `FunctionModel` fixtures only.

**Phase 1 workflows:**
- `hello_pipeline`, with the steps `hello.open_attempt`, `hello.echo` (one gateway call) and `hello.finish`.
- `daily_trigger`, attached to the `daily_generation` schedule, which is paused.

**When to bump `APP_VERSION`.** Bump it whenever you add, remove or reorder workflow steps, then recreate both `api` and `worker` with `docker compose up -d`. A workflow that was interrupted on the old version is not recovered automatically; cancel it. The Phase 6 UI adds "Resume".

## 6. Start, watch and stop

```bash
docker compose up -d --build --wait     # builds images, runs migrate, waits until db/api/worker/web are healthy
docker compose ps -a                    # migrate shows "Exited (0)"; the others show "(healthy)"
docker compose logs -f api worker       # follow logs (Ctrl-C stops following, not the stack)
docker compose down                     # stop and remove containers; the database volume is kept
```

The first build takes a few minutes: `npm ci`, `uv sync`, and pulling the Postgres image.

## 7. Running the backend, worker and frontend

**Backend API.**
- `api` reloads automatically when files under `backend/src/` change, because the source is bind-mounted.
- Check it:
  ```bash
  curl -s http://127.0.0.1:8300/healthz    # {"status":"ok"}
  curl -s http://127.0.0.1:8300/readyz     # {"status":"ok","database":"ok"}
  ```

**Worker.**
- The worker does **not** auto-reload. After changing workflow or step code, restart it:
  ```bash
  docker compose up -d --no-deps --force-recreate worker
  ```
  A workflow that is running at that moment resumes when the worker comes back.
- Health comes from a heartbeat file the worker touches every 10 s (`/tmp/worker-heartbeat`).

**Frontend.**
- Open http://localhost:8310. Vite hot-reloads edits under `frontend/src/`.
- If edits are not picked up on macOS, add `VITE_USE_POLLING: "true"` under `web.environment` in `compose.yaml` and run `docker compose up -d web`.
- `node_modules` lives in a container volume. Never run `npm install` on the host.

**CLI** (`python -m mdcopilot_blog.cli`):

| Command | What it does |
|---|---|
| `migrate` | Alembic upgrade, DBOS migrations, seed, prompt sync (what the `migrate` service runs) |
| `migrate-dbos` | DBOS system schema migrations only |
| `seed` | Default settings, brand profile and content pillars (idempotent) |
| `sync-prompts` | Registers new prompt files in `blog_prompt_versions` |
| `create-admin` | Creates an admin. The password comes from an env var; the default var is `BOOTSTRAP_ADMIN_PASSWORD`. |
| `create-user` | Creates a user with `--role viewer\|editor\|reviewer\|publisher\|admin` |

**First admin.** This command uses the email and password from `.env`, inside the running `api` container:

```bash
docker compose exec api sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'
```

Running it again changes nothing. If the stack is stopped, `docker compose run --rm tools sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'` does the same. It starts only `db`, and the schema must already exist from an earlier `docker compose up`.

**More users.** Type the password; it never appears on screen or in shell history:

```bash
printf 'Password for the new user: '; read -rs NEW_USER_PASSWORD; echo; export NEW_USER_PASSWORD
docker compose exec -e NEW_USER_PASSWORD api python -m mdcopilot_blog.cli create-user \
  --email editor@mdcopilot.health --display-name "Editor" --role editor --password-env NEW_USER_PASSWORD
unset NEW_USER_PASSWORD
```

Admins can also create users with `POST /api/admin/users`.

## 8. Running the agent manually

**From the dashboard.**
1. Sign in at http://localhost:8310.
2. On **Dashboard**, press **Generate today's blog**. The button needs the `blog.generate` permission.
3. **Agent Runs** lists runs and their status. **Cancel** stops a run that has not finished.

**From the terminal.** This session uses a cookie jar and the CSRF token, exactly as the browser does:

```bash
API=http://127.0.0.1:8300
JAR="$(mktemp)"
printf 'Email: '; read -r LOGIN_EMAIL
printf 'Password: '; read -rs LOGIN_PASSWORD; echo
CSRF="$(LOGIN_EMAIL="$LOGIN_EMAIL" LOGIN_PASSWORD="$LOGIN_PASSWORD" jq -n '{email: env.LOGIN_EMAIL, password: env.LOGIN_PASSWORD}' |
  curl -s -c "$JAR" -H "Origin: $API" -H 'Content-Type: application/json' --data-binary @- "$API/api/auth/login" | jq -r .csrfToken)"
unset LOGIN_PASSWORD

# start a manual run (202 Accepted)
RUN_ID="$(curl -s -b "$JAR" -H "Origin: $API" -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  -d '{}' "$API/api/blog-agent/runs" | jq -r .id)"

# watch it: status goes QUEUED → RESEARCHING → TOPICS_READY → PRODUCING → SUCCEEDED
curl -s -b "$JAR" "$API/api/blog-agent/runs/$RUN_ID" | jq '{status, steps: [.steps[] | {stepName, status, tries}]}'

# sign out
curl -s -o /dev/null -b "$JAR" -H "Origin: $API" -H "X-CSRF-Token: $CSRF" -X POST "$API/api/auth/logout"
rm -f "$JAR"
```

**Run options.** The request body accepts `runDate`, `pillar` (`A`–`E` or `NARRATIVE`), `topic`, `audience`, `tone` and `wordCount`. Phase 1 stores them on the run; later phases use them.

**The daily schedule** is registered but paused while `BLOG_AGENT_SCHEDULER_ENABLED=false`. Check it:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select schedule_name, status, schedule, cron_timezone from dbos.workflow_schedules"'
```

## 9. Mock mode

With `BLOG_AGENT_MOCK_MODE=true`:
- **No network calls.** No request reaches a real LLM, search or publishing service. The gateway sets Pydantic AI's `ALLOW_MODEL_REQUESTS=False`.
- **LLM fixtures.** Agent calls return fixtures from `backend/fixtures/mock/llm/<agent>/<prompt name with / replaced by _>.json`, shaped `{"output": {...}, "usage": {"input_tokens": n, "output_tokens": n}}`. Example: `hello/hello_echo.json`.
- **Search fixture.** Web search returns `backend/fixtures/mock/search/default.json`.
- **Embeddings.** They are deterministic vectors derived from the text.
- **Call recording.** Every call is still recorded in `blog_llm_calls` with tokens, the prompt version and the trace id. Mock runs therefore exercise the same recording and cost-cap path as real ones.

With `BLOG_AGENT_MOCK_MODE=false`, Phase 1 has no real provider adapters. Runs fail with "real providers are enabled in Phase 2", so keep mock mode on.

**Crash-and-resume demo.** `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS` adds artificial time to each step, so you can kill the worker mid-step:
1. Recreate the worker with a 15-second delay:
   ```bash
   BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=15 docker compose up -d --no-deps worker
   ```
2. Start a run (dashboard or curl). While `hello.echo` shows RUNNING, kill the worker:
   ```bash
   docker compose kill worker
   ```
3. Start the same container again, then watch the logs for "Recovering ... workflows":
   ```bash
   BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=15 docker compose up -d --no-deps worker
   docker compose logs -f worker
   ```
4. When the run reaches SUCCEEDED, restore the default delay:
   ```bash
   BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0 docker compose up -d --no-deps worker
   ```

The run finishes with `hello.open_attempt` and `hello.finish` executed once each. Only the interrupted `hello.echo` shows `tries=2`. The run still has a single `blog_llm_calls` row, because `hello.echo` waits its delay before the gateway call. Check it:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select run_id, count(*) from app.blog_llm_calls group by run_id order by max(created_at) desc limit 3"'
```

## 10. Database

**Open a SQL shell** (it uses the credentials inside the container):

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

GUI clients connect to `127.0.0.1:5440` with `POSTGRES_USER` and `POSTGRES_DB` from `.env`.

**Schemas.**
- `app`: our tables (users, sessions, settings, runs, attempts, step rows, LLM calls, prompts, notifications). Alembic owns it.
- `dbos`: DBOS system tables. The `migrate` service creates them by running the DBOS system-table migrations in-process (the same code `dbos migrate` runs).

**Migrations.**
1. Change the models in `backend/src/mdcopilot_blog/db/models/`.
2. Generate and review a revision:
   ```bash
   docker compose run --rm tools alembic revision --autogenerate --rev-id 0002 -m "describe the change"
   ```
3. Review the new file in `backend/migrations/versions/`, then apply it and confirm nothing is left:
   ```bash
   docker compose run --rm migrate                   # upgrade, DBOS migrations, seed, prompt sync
   docker compose run --rm tools alembic check       # "No new upgrade operations detected."
   ```

**Tests** use a separate database, `mdcopilot_blog_test`. pytest creates it and drops it on every run, and never touches `mdcopilot_blog`.

**Prompts.** Prompt files are versioned. Never edit a registered `*.vN.md`; add `*.vN+1.md` instead. Startup fails if a registered version's text changed.

**Backup before anything risky:**

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "mdcopilot-blog-$(date +%Y%m%d).dump"
```

## 11. Testing

| What | Command | Expected |
|---|---|---|
| Backend tests (all) | `docker compose run --rm tools pytest -q` | `1130 passed` at the end of Phase 1, nothing failed |
| One file / one test | `docker compose run --rm tools pytest tests/api/test_runs_api.py -q -k cancel` | selected tests pass |
| Lint and types | `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"` | `All checks passed!`, `111 files already formatted` and `Success: no issues found in 62 source files` at the end of Phase 1 |
| Migration drift | `docker compose run --rm tools alembic check` | `No new upgrade operations detected.` |
| Frontend tests | `docker compose run --rm web npm test` | `Test Files  6 passed (6)` and `Tests  35 passed (35)` at the end of Phase 1, nothing failed |
| Frontend lint / types / build | `docker compose run --rm web npm run lint` · `docker compose run --rm web npm run typecheck` · `docker compose run --rm web npm run build` | exit 0 |
| Phase 1 acceptance | `scripts/acceptance/phase1.sh` | `PHASE 1 ACCEPTANCE: PASS (83 checks, 0 warnings)` |

Dependency changes need `docker compose build tools` first. New source files do not, because the source is bind-mounted.

**What the acceptance script does.** It needs only Docker, `curl`, `openssl` and `jq`, and it never reads `.env`. It:
1. builds and starts the stack, checks health, and recreates `api` and `worker` so the log checks see only this run;
2. runs the backend and frontend suites;
3. creates two throwaway accounts with generated passwords, and checks that the bootstrap admin from `.env` can sign in;
4. checks RBAC, and checks CSRF directly and through the Vite proxy, using a `curlimages/curl` container on the compose network;
5. checks that a forged `X-Forwarded-For` never becomes the recorded login address;
6. drives a real Chromium (`mcr.microsoft.com/playwright:v1.63.0-noble`) against `http://web:5173`: sign in, every sidebar page, "Generate today's blog" and sign out;
7. runs mock pipelines, and checks that the worker's JSON logs carry `run_id` and `trace_id`;
8. kills the worker mid-step and checks the resume, including that the gateway call was not repeated;
9. checks that logs and the settings response leak no secrets.

At the end it deactivates the throwaway accounts and resets the worker's step delay to 0. Use `SKIP_SUITES=1 scripts/acceptance/phase1.sh` to skip the test suites on a re-run (that run ends with 1 warning).

## 12. Troubleshooting

| Symptom | Check |
|---|---|
| `up --wait` fails, `migrate` exited non-zero | `docker compose logs migrate`. Usually the database password: `POSTGRES_PASSWORD` changed after the volume was created. |
| `api` unhealthy | `docker compose logs api`. A settings validation error names the variable (for example `SESSION_SECRET` too short). |
| `worker` unhealthy | `docker compose logs worker`. The heartbeat starts only after `DBOS.launch()` and the prompt sync succeed. |
| Run stays `QUEUED` | Worker down, or `api` and `worker` on different `APP_VERSION` values. Run `docker compose up -d` to recreate both. |
| Web shows "Blocked request. This host is not allowed" | The service must be named `web`, or the host must be in `server.allowedHosts`. |
| 403 "Origin not allowed" from curl | Send `Origin` equal to the address you call (for example `http://127.0.0.1:8300`). |
| 403 "CSRF token missing or invalid" | Send `X-CSRF-Token` with the `csrfToken` from the login response. |
| Port already in use | Change `API_HOST_PORT`, `WEB_HOST_PORT` or `DB_HOST_PORT` in `.env`, then run `docker compose up -d`. |
| Any compose command says `required variable POSTGRES_PASSWORD is missing a value` | Set `POSTGRES_PASSWORD` in `.env` (section 2). `db` reads it through compose interpolation, and a value exported in your shell overrides `.env`, so do not export it. |
| Login attempts and sessions all show a Docker address (for example the web container's) as the IP | Expected in local dev. `api` runs with `--no-proxy-headers`, so it records the TCP peer and ignores `X-Forwarded-For`, which any client could forge. |
| Frontend dependency missing after a package change | `docker compose up -d --build --renew-anon-volumes web` |

## 13. Stop and clean up

```bash
docker compose down                        # stops everything; keeps the blog_pgdata volume (all data)
docker compose --profile tools down        # also removes a stray tools container, if any
```

`docker compose down -v` **deletes the database volume**: users, runs, settings and DBOS state. Run it only when the owner explicitly asks for a reset, and take a backup first (section 10).

Build output in `frontend/dist/` is git-ignored and safe to delete. Unused images can be removed with `docker image rm mdcopilot-blog-backend:dev mdcopilot-blog-web:dev`.
