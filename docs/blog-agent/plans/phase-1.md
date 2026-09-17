# MDCopilot Blog Intelligence: Phase 1 (Application Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Docker-only foundation of `mdcopilot-blog`. When done, `docker compose up` gives:
- a FastAPI API with its own Postgres, login, RBAC and CSRF;
- a DBOS worker that runs a durable mock "hello" pipeline, which survives being killed;
- per-call LLM recording behind the gateway interface;
- a React dashboard shell with role-aware navigation.

Phases 2–10 build on this without restructuring it.

**Architecture:**
- `api` (FastAPI) never executes workflows. It only enqueues them through `DBOSClient`.
- `worker` is the only process that calls `DBOS.launch()`.
- Both share one Postgres 16 + pgvector database: schema `app` is managed by Alembic, and schema `dbos` belongs to DBOS.
- All LLM access goes through `LLMGateway`. In Phase 1 it uses Pydantic AI `FunctionModel` fixtures only.
- The web dashboard is a Vite/React SPA whose dev server proxies `/api`, so the app is same-origin.

**Tech Stack:**
- **Backend:** Python 3.12, uv 0.12.15, FastAPI 0.141.1, SQLAlchemy 2.0.54 (async, psycopg 3.3.5), Alembic 1.20.0, pydantic-settings 2.15.0, pwdlib 0.3.1, DBOS 3.0.0, Pydantic AI 2.43.0, pytest 9.1.1 + pytest-asyncio 1.4.0.
- **Frontend:** Node 24, Vite 8.3.0, React 19.3, TypeScript ~6.0, Tailwind 4.3.3, shadcn 4.21.0, react-router 8.4.0, TanStack Query 5.103.1, Vitest 5.0.1.
- **Infrastructure:** Docker Compose, pgvector/pgvector:pg16 (digest-pinned in `compose.yaml`).

**Spec:**
- `docs/blog-agent/ARCHITECTURE.md` (design)
- `docs/blog-agent/IMPLEMENTATION_PLAN.md` (Phase 1 scope and acceptance)
- `docs/blog-agent/FRAMEWORK_EVALUATION.md`
- `docs/blog-agent/RESEARCH_ARCHITECTURE.md`

Executors read the spec alongside this plan.

## Global Constraints

**Process rules**
- **Docker only.** Never run `python`, `pip`, `uv`, `node` or `npm` on the host. Every command below runs from `mdcopilot-blog/` through `docker compose` or `docker run`.
- **No git operations** of any kind (spec Rule 10). Each task ends with a *Checkpoint* that lists changed files; the owner handles version control.
- **Do not modify `mdcopilot-backend/` or `mdcopilot-frontend/`.**

**Secrets**
- **`.env` holds real secrets** (mode 600). Never print it, copy its values into files, or commit it.
- Tests read it via compose `env_file`.
- Secrets are `SecretStr`, never logged, and never returned by the API unmasked.

**Safety defaults**
- Human approval is mandatory: the app refuses to start with `BLOG_HUMAN_APPROVAL_REQUIRED=false`.
- Mock mode is on by default (`BLOG_AGENT_MOCK_MODE=true`).
- Publishing is off (`BLOG_PUBLISHING_ENABLED=false`).
- The scheduler is paused (`BLOG_AGENT_SCHEDULER_ENABLED=false`).

**Code rules**
- **Model names only in configuration** (`.env` routes / Settings), never in business logic.
- **Tests use the disposable database `mdcopilot_blog_test` only.**
- **Ports** bind to `127.0.0.1` only: web 8310, api 8300, db 5440.
- **Python style:** ruff (line length 120) and mypy strict with the pydantic plugin must pass on `src/`.
- **TypeScript:** `tsc -b`, `eslint` and `vitest` must pass.

## Spike S1 result (DBOS version), recorded 2026-09-17

These checks were run in throwaway containers against `pgvector/pgvector:pg16`, first on dbos **3.0.0** and then on **2.31.1**. Both passed every check:
1. an async workflow with async steps (`DBOS.workflow_id` and `DBOS.step_id` inside steps);
2. queues registered **after** `DBOS.launch()` with `DBOS.register_queue_async`;
3. an API process enqueueing through `DBOSClient` without launching DBOS;
4. `list_workflow_steps`;
5. `fork_workflow` from a step, with earlier steps not re-run;
6. cancelling a long workflow;
7. `asyncio.gather` of steps running concurrently;
8. an `apply_schedules_async` cron with `cron_timezone="Asia/Kolkata"`, where a wrapper starts an idempotent child under `SetWorkflowID("daily-<date>")`;
9. `docker kill` of the worker mid-step, then a restart with the same `executor_id` and `application_version`, after which the workflow completed without re-running finished steps;
10. dedup, timeout, retry, preemptible and resume.

**Decision: pin `dbos==3.0.0`** (locked in `uv.lock`, one version shared by api and worker).

Behaviour to design around:
- **API changes in 3.0:**
  - `Queue(...)` cannot be constructed; use `register_queue_async` after launch.
  - `@DBOS.scheduled` is gone; use `apply_schedules_async`.
  - `DBOSClient` takes keyword arguments only (`system_database_url=`).
  - `WorkflowStatus` fields are attributes, while `StepInfo` is a dict.
- **Async code:** use the `*_async` variants.
- **Recovery:** it needs the same `executor_id` and `application_version`.
- **Fork and resume:** pass `queue_name` to both.
- **Version mixing:** a 2.31 client on a 3.0 database silently returns `None` results, so never mix versions.

Task 11's tests and the Task 14 acceptance run re-verify this inside the project. Fallback if 3.0.x regresses: `dbos==2.31.1`, where the same code ran unchanged.

## Verified versions (installed and run in containers on 2026-09-17)

| Area | Versions |
|---|---|
| Backend | python 3.12.14 (python:3.12-slim-trixie) · uv 0.12.15 · fastapi 0.141.1 · starlette 1.6.0 · uvicorn 0.53.0 · sqlalchemy 2.0.54 · psycopg 3.3.5 · alembic 1.20.0 · pgvector 0.5.0 (server extension 0.8.6) · pydantic 2.13.5 · pydantic-settings 2.15.0 · pwdlib 0.3.1 · httpx 0.28.1 · httpx2 2.13.0 · jinja2 3.1.6 · pyyaml 6.0.3 · uuid-utils 1.0.0 · dbos 3.0.0 · pydantic-ai-slim 2.43.0 · openai 3.14.1 · google-genai 2.23.0 · anthropic 1.6.0 · genai-prices 0.1.7 · pytest 9.1.1 · pytest-asyncio 1.4.0 · ruff 0.16.8 · mypy 2.3.1 |
| Frontend | node 24.21.0 · create-vite 9.2.1 · vite 8.3.0 · @vitejs/plugin-react 6.1.1 · react 19.3.0 · typescript 6.0.3 · tailwindcss 4.3.3 · shadcn 4.21.0 · cn 0.3.0 · radix-ui 1.6.7 · react-router 8.4.0 · @tanstack/react-query 5.103.1 · vitest 5.0.1 · jsdom 30.0.1 · @testing-library/react 16.3.3 · @testing-library/user-event 14.6.7 · @testing-library/jest-dom 7.0.1 · nginx 1.30.5 |

## Task map

| # | Task | Depends on |
|---|---|---|
| 1 | Backend skeleton and tooling | — |
| 2 | Settings | 1 |
| 3 | Logging and problem responses | 1 |
| 4 | Domain model (enums, RBAC, state machine, contracts) | 1 |
| 5 | Database layer, models, first migration | 2, 4 |
| 6 | Prompt registry | 5 |
| 7 | Auth core and audit | 5 |
| 8 | Seed data and CLI | 5, 6, 7 |
| 9 | API app, auth/users/settings routes, workflow client | 3, 7 |
| 10 | LLM gateway, search and publisher interfaces (mock) | 5, 6 |
| 11 | Workflows and worker (DBOS) | 9, 10 |
| 12 | Runs service and runs API | 9, 11 |
| 13 | Frontend shell | 9 (API contract) |
| 14 | Full stack, acceptance run, docs | all |

Run the tasks strictly in numeric order, 1 to 14, even where the "Depends on" column would allow another order. Every expected test count and lint count in this plan assumes that order.

---

### Task 1: Backend skeleton and tooling

Creates the backend project (uv, `uv_build`, src layout), the lock file, the multi-stage Dockerfile, and a first `compose.yaml` with only `db` and `tools`. It then proves the toolchain end to end with `ids.py`, test first.

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/mdcopilot_blog/__init__.py`, `backend/src/mdcopilot_blog/py.typed` (empty)
- Create: `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/conftest.py` (docstring only)
- Create (generated in a container): `backend/uv.lock`
- Create: `backend/.dockerignore`, `backend/Dockerfile`
- Create: `compose.yaml` (`db` and `tools` only; Task 14 replaces it)
- Create: `backend/src/mdcopilot_blog/ids.py`
- Test: `backend/tests/unit/test_ids.py`

**Interfaces:**
- Consumes:
  - the existing `.env`, never printed:
    - backend services (`tools`, and later `migrate`, `api`, `worker`) receive all of it via compose `env_file`;
    - `db` receives only `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD`, which compose interpolates from `.env`;
  - `.env.example` (key names only).
- Produces:
  - `mdcopilot_blog.ids.uuid7() -> uuid.UUID`: a stdlib `UUID` with `version == 7`, time-ordered.
  - `mdcopilot_blog.ids.new_trace_id() -> str`: 32 lowercase hex chars.
  - Compose project `mdcopilot-blog`, plus the `x-backend` anchor that Task 14 reuses. It has two services:
    - `db`: pgvector pg16 on `127.0.0.1:${DB_HOST_PORT:-5440}`. Its healthcheck probes TCP, and it receives only the three `POSTGRES_*` variables.
    - `tools`: profile `tools`, the dev image, `./backend:/app`, and default command `pytest -q`.
  - Image `mdcopilot-blog-backend:dev`, with its venv at `/opt/venv` and the project installed editable from `/app/src`.
  - Dockerfile targets:
    - `base`, `dev`, `builder`, `runtime`;
    - `runtime` copies `/opt/venv`, `src/`, `alembic.ini`, `migrations/`, `prompts/` and `fixtures/`, and runs as uid 999.
  - The pytest, ruff and mypy configuration every later task relies on.

**Note:** do **not** build the `runtime` target in this task. It copies `alembic.ini`, `migrations/`, `prompts/` and `fixtures/`, which appear only in Tasks 5, 6 and 10. BuildKit builds only the stages a target needs, so `docker compose build tools` (target `dev`) is unaffected.

- [ ] **Step 1: Check the starting state**

Run from `mdcopilot-blog/`:
```bash
ls -A
docker compose version
```
Expected:
- `ls -A` prints exactly `.env  .env.example  .gitignore  docs` (in any layout), with no `backend/` and no `compose.yaml`.
- `docker compose version` prints a v2+ version (verified with v5.5.1).

Do not `cat` `.env`.

- [ ] **Step 2: Write `backend/pyproject.toml`**

```toml
[project]
name = "mdcopilot-blog-backend"
version = "0.1.0"
description = "MDCopilot Blog Intelligence backend (API, worker, CLI)"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.141.1,<0.142",
    "uvicorn[standard]>=0.53.0,<0.54",
    "sqlalchemy[asyncio]>=2.0.54,<2.1",
    "psycopg[binary]>=3.3.5,<3.4",
    "alembic>=1.20.0,<1.21",
    "pgvector>=0.5.0,<0.6",
    "pydantic>=2.13.5,<2.14",
    "pydantic-settings>=2.15.0,<2.16",
    "pwdlib[argon2]>=0.3.1,<0.4",
    "httpx>=0.28.1,<0.29",
    "httpx2>=2.13.0,<2.14",
    "jinja2>=3.1.6,<3.2",
    "pyyaml>=6.0.3,<7",
    "uuid-utils>=1.0.0,<2",
    "dbos==3.0.0",
    "pydantic-ai-slim[openai,google,anthropic]>=2.43.0,<2.44",
    "genai-prices==0.1.7",
]

[dependency-groups]
dev = [
    "pytest>=9.1.1,<10",
    "pytest-asyncio>=1.4.0,<1.5",
    "ruff==0.16.8",
    "mypy==2.3.1",
    "types-PyYAML",
]

[build-system]
requires = ["uv_build>=0.12.15,<0.13"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "mdcopilot_blog"

# pytest 9 native TOML table (not [tool.pytest.ini_options])
[tool.pytest]
testpaths = ["tests"]
addopts = ["-ra", "--strict-markers"]
asyncio_mode = "auto"
# The engine fixtures are session-scoped, so fixtures AND tests must share the session loop.
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106", "PLR2004"]
"migrations/versions/*" = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

- [ ] **Step 3: Create the package and test skeleton**

`uv_build` must find `src/mdcopilot_blog/` before `uv sync` can install the project; without it, the image build fails. Create these four files with exactly this content.

`backend/src/mdcopilot_blog/__init__.py`:
```python
"""MDCopilot Blog Intelligence backend."""

__version__ = "0.1.0"
```

`backend/tests/__init__.py`:
```python
"""Backend test suite."""
```

`backend/tests/unit/__init__.py`:
```python
"""Unit tests (no database)."""
```

`backend/tests/conftest.py` (Tasks 5, 9 and 11 append marked blocks later):
```python
"""Shared pytest fixtures. Later tasks append marked blocks (T5 database, T9 API, T11 DBOS)."""
```

Then create the empty PEP 561 marker. Without it, mypy reports `import-untyped` for the package:
```bash
touch backend/src/mdcopilot_blog/py.typed
```

- [ ] **Step 4: Generate `backend/uv.lock` in a throwaway container**

Run from `mdcopilot-blog/`:
```bash
docker run --rm -v "$PWD/backend:/work" -w /work -e UV_PYTHON_DOWNLOADS=0 ghcr.io/astral-sh/uv:0.12.15-python3.12-trixie-slim uv lock
```
Expected:
```text
Using CPython 3.12.14 interpreter at: /usr/local/bin/python3
Resolved 84 packages in <time>
```

Check the key pins:
```bash
grep -c '^\[\[package\]\]' backend/uv.lock
grep -A1 -E '^name = "(dbos|fastapi|pydantic-ai-slim|pydantic-settings|sqlalchemy|genai-prices)"$' backend/uv.lock
```
Expected: `84`, then these name/version pairs:
- dbos 3.0.0
- fastapi 0.141.1
- genai-prices 0.1.7
- pydantic-ai-slim 2.43.0
- pydantic-settings 2.15.0
- sqlalchemy 2.0.54

On 2026-09-17 the lock also resolved:
- openai 3.14.1, google-genai 2.23.0, anthropic 1.6.0, httpx2 2.13.0;
- websockets 16.1.1 (google-genai caps it below 17);
- types-pyyaml 6.0.12.20260906.

`tzdata` is locked for Windows only. The Linux image uses Debian's system zoneinfo, which was verified to resolve `Asia/Kolkata`.

- [ ] **Step 5: Write `backend/.dockerignore`**

```text
.venv/
**/__pycache__/
**/*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
.env.*
```

- [ ] **Step 6: Write `backend/Dockerfile`**

This follows the verified reference with one deliberate change. The builder installs the project **editable**, and `runtime` copies `/app/src`. With the verified `--no-editable` install, `Path(__file__).resolve().parents[3]` (used by `default_prompt_root()` in Task 6 and `FixtureRegistry.default()` in Task 10) resolved to `/opt/venv/lib/python3.12/prompts` in the runtime image. With this Dockerfile it resolves to `/app/prompts`. Both results were verified in a container on 2026-09-17, which also showed that:
- `/app/src` is root-owned and read-only for uid 999;
- `.pyc` files are precompiled;
- neither `uv` nor `pytest` is present in `runtime`;
- package data such as `db/seed_data/*.yaml` is importable via `importlib.resources`.

```dockerfile
# syntax=docker/dockerfile:1
# Pattern: docs.astral.sh/uv/guides/integration/docker + astral-sh/uv-docker-example (multistage).
# Verified 2026-09-17 with uv 0.12.15 on python:3.12-slim-trixie (CPython 3.12.14, Debian 13.6).
ARG PYTHON_IMAGE=python:3.12-slim-trixie

# ---------- base: interpreter + pinned uv ----------
FROM ${PYTHON_IMAGE} AS base
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ---------- dev: all groups (dev included); compose bind-mounts ./backend over /app ----------
# The venv lives in /opt/venv, so the bind mount does not hide it. The project is installed
# editable (.pth -> /app/src), so new source files need no rebuild; dependency changes do.
FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
CMD ["uvicorn", "--factory", "mdcopilot_blog.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]

# ---------- builder: no dev deps; the project is installed editable from /app/src ----------
# Editable on purpose: code that locates backend/prompts and backend/fixtures via
# Path(__file__).resolve().parents[3] must resolve to /app in the runtime image as well.
FROM base AS builder
ENV UV_NO_DEV=1
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked \
 && python -m compileall -q /app/src

# ---------- runtime: no uv, no dev deps, non-root ----------
# Must be the same interpreter image as the builder (venv symlinks point at /usr/local/bin/python3).
# Build this target only after Tasks 5, 6 and 10 exist: it copies alembic.ini, migrations/,
# prompts/ and fixtures/, and a missing source makes the COPY fail.
FROM ${PYTHON_IMAGE} AS runtime
RUN groupadd --system --gid 999 app \
 && useradd --system --gid 999 --uid 999 --create-home app
# The venv stays root-owned (read-only for the app user); bytecode was compiled in the builder.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/prompts /app/prompts
COPY --from=builder /app/fixtures /app/fixtures
ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
USER app
EXPOSE 8000
# Phase 10: replace "*" with the production reverse proxy's address (IMPLEMENTATION_PLAN, Phase 10).
CMD ["uvicorn", "--factory", "mdcopilot_blog.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

The `runtime` target is not used by compose in Phase 1. Its `--forwarded-allow-ips "*"` trusts any caller's `X-Forwarded-*` headers, so Phase 10 must narrow it to the production reverse proxy before the image serves real traffic (Task 14 adds that item to IMPLEMENTATION_PLAN). The compose `api` service in Task 14 runs with `--no-proxy-headers` instead.

- [ ] **Step 7: Write `compose.yaml` (only `db` and `tools`)**

**Deviations from the contract's compose table.** Three parts of `db` differ from the contract, deliberately. All three were checked on 2026-09-17, and they need the owner's approval.

1. **Healthcheck.** It probes TCP: `pg_isready -h 127.0.0.1 -p 5432 ...`, not the contract's socket-only `pg_isready -U ... -d ...`.
   - **Why:** on a fresh volume, the image's entrypoint first runs a temporary init server with `listen_addresses=''`, which listens on the Unix socket only. In 3 of 3 fresh `pgvector/pgvector:pg16` starts, the socket probe passed for about 140 ms while TCP was still refused. A socket probe in that window marks `db` healthy before `db:5432` accepts connections, and `tools` (later `migrate`) connects over TCP with no retry.
   - **Result:** the TCP probe passes only on the final server. Five fresh-volume cycles with `start_interval: 1s` (Task 14's timing) were all healthy, and each one connected over TCP immediately afterwards.
2. **Environment.** `db` uses `environment:` with the three `POSTGRES_*` variables instead of `env_file: [.env]`.
   - **Why:** `env_file` would put every provider key, `SESSION_SECRET`, `BOOTSTRAP_ADMIN_PASSWORD` and `BLOG_PUBLISHER_PASSWORD` into the database container's environment, where `docker inspect` shows them.
   - **How it works:** compose interpolates the three values from `.env` without printing them.
   - **Defaults:** they match `Settings`, so `db` and the backend agree even when `.env` omits `POSTGRES_DB` or `POSTGRES_USER`.
   - **Missing password:** if `POSTGRES_PASSWORD` is missing or empty, every compose command stops with `required variable POSTGRES_PASSWORD is missing a value: set POSTGRES_PASSWORD in .env`.
3. **Image digest.** `db` uses `pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`, not the bare `pgvector/pgvector:pg16` tag.
   - **Why:** ARCHITECTURE §3 asks for digest-pinned images, and a moving `pg16` tag could change the database under the tests without any file changing.
   - **Source:** the digest is the multi-arch index behind the `pg16` tag on 2026-09-17 (`docker buildx imagetools inspect pgvector/pgvector:pg16`). Task 14's final `compose.yaml` uses the same pin.

```yaml
# MDCopilot Blog Intelligence: local stack. Task 1 creates only `db` and `tools`;
# Task 14 replaces this file with the full stack (migrate, api, worker, web).
name: mdcopilot-blog

x-backend: &backend
  build:
    context: ./backend
    target: dev
  image: mdcopilot-blog-backend:dev
  env_file:
    - .env
  environment:
    POSTGRES_HOST: db
    BLOG_AGENT_MOCK_STEP_DELAY_SECONDS: "${BLOG_AGENT_MOCK_STEP_DELAY_SECONDS:-0}"
  volumes:
    - ./backend:/app

services:
  db:
    # pgvector/pgvector:pg16, pinned to its multi-arch index digest (2026-09-17). To move it on purpose:
    # docker buildx imagetools inspect pgvector/pgvector:pg16, then copy the top-level "Digest:" here.
    image: pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b
    # Only the three variables Postgres needs, interpolated from .env. Not env_file, which would hand
    # every provider key and SESSION_SECRET to the database container. Defaults match Settings.
    environment:
      POSTGRES_DB: "${POSTGRES_DB:-mdcopilot_blog}"
      POSTGRES_USER: "${POSTGRES_USER:-mdcopilot_blog}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}"
    ports:
      - "127.0.0.1:${DB_HOST_PORT:-5440}:5432"
    volumes:
      - blog_pgdata:/var/lib/postgresql/data
    healthcheck:
      # Probe TCP (-h 127.0.0.1), not the Unix socket. On a fresh volume the image's temporary init server
      # listens on the socket only, so a socket probe can pass before db:5432 accepts connections.
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -p 5432 -U \"$$POSTGRES_USER\" -d \"$$POSTGRES_DB\""]
      interval: 5s
      retries: 20

  tools:
    <<: *backend
    profiles: [tools]
    depends_on:
      db:
        condition: service_healthy
    command: ["pytest", "-q"]

volumes:
  blog_pgdata: {}
```

- [ ] **Step 8: Validate the compose file without printing secrets**

`docker compose config` without `--quiet` prints the resolved `.env` values. Only use the forms below.
```bash
docker compose config --quiet && echo compose-ok
docker compose --profile tools config --services
```
Expected: `compose-ok`, then two lines: `db` and `tools`.

Decision rule: if the first command fails with `required variable POSTGRES_PASSWORD is missing a value`, `.env` has no non-empty `POSTGRES_PASSWORD`. The owner adds one by hand (for example from `openssl rand -hex 16`); never print `.env`.

- [ ] **Step 9: Build the dev image**

```bash
docker compose build tools
```
Expected:
- the build log contains `+ mdcopilot-blog-backend==0.1.0 (from file:///app)`;
- it ends with `Image mdcopilot-blog-backend:dev Built`.

Naming the profiled service enables its profile, so `--profile` is not needed.

- [ ] **Step 10: Write the failing test `backend/tests/unit/test_ids.py`**

```python
"""ids.py: UUIDv7 primary keys and trace ids."""

import re
import uuid

from mdcopilot_blog.ids import new_trace_id, uuid7


def test_uuid7_returns_stdlib_uuid_version_7() -> None:
    value = uuid7()
    assert type(value) is uuid.UUID
    assert value.version == 7


def test_uuid7_values_are_unique_and_time_ordered() -> None:
    values = [uuid7() for _ in range(1000)]
    assert len(set(values)) == 1000
    assert values == sorted(values)


def test_new_trace_id_is_32_lowercase_hex_chars() -> None:
    trace_id = new_trace_id()
    assert re.fullmatch(r"[0-9a-f]{32}", trace_id)


def test_new_trace_ids_are_unique() -> None:
    assert len({new_trace_id() for _ in range(1000)}) == 1000
```

- [ ] **Step 11: Run the test and watch it fail**

```bash
docker compose run --rm tools pytest tests/unit/test_ids.py -q
```
Expected:
- The first run starts `db` and waits until it is healthy. It stays running afterwards; stop it with `docker compose stop db` when you are done for the day.
- The test collection fails with:
```text
E   ModuleNotFoundError: No module named 'mdcopilot_blog.ids'
ERROR tests/unit/test_ids.py
1 error in <time>
```

Now that `db` is running, check that it is healthy and that it received no application secrets. The second command prints variable **names** only:
```bash
docker compose ps db --format '{{.Service}} {{.Health}}'
docker compose exec -T db sh -c 'env | cut -d= -f1 | grep -E "KEY|SECRET|PASSWORD" | sort'
```
Expected, exactly:
```text
db healthy
POSTGRES_PASSWORD
```
Any other name (for example `OPENAI_API_KEY` or `SESSION_SECRET`) means `db` still reads `.env` through `env_file`. Fix `compose.yaml` to match Step 7, then run `docker compose up -d --force-recreate db`.

- [ ] **Step 12: Write `backend/src/mdcopilot_blog/ids.py`**

```python
"""Identifier helpers: UUIDv7 primary keys and per-run trace ids."""

import uuid

import uuid_utils


def uuid7() -> uuid.UUID:
    """Return a time-ordered UUIDv7 as a stdlib ``uuid.UUID`` (Python 3.12 has no ``uuid.uuid7``)."""
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)


def new_trace_id() -> str:
    """Return a 32-character lowercase hex trace id (the W3C trace-id width)."""
    return uuid.uuid4().hex
```

The source directory is bind-mounted and the package is installed editable, so no rebuild is needed.

- [ ] **Step 13: Run the test and watch it pass**

```bash
docker compose run --rm tools pytest tests/unit/test_ids.py -q
```
Expected: `4 passed`.

The ordering test (1000 ids) is stable. The same check over 50 × 20,000 ids in a row was monotonic and unique in three separate runs.

- [ ] **Step 14: Lint and type-check**

```bash
docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"
```
Expected:
```text
All checks passed!
6 files already formatted
Success: no issues found in 2 source files
```

If `ruff format --check` lists a file, run `docker compose run --rm tools ruff format .` and repeat.

- [ ] **Step 15: Checkpoint: list the files changed in this task (no git)**

```bash
ls -la compose.yaml backend backend/src/mdcopilot_blog backend/tests backend/tests/unit
```
Expected new files:
- `compose.yaml`
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`, `backend/.dockerignore`
- `backend/src/mdcopilot_blog/__init__.py`, `backend/src/mdcopilot_blog/py.typed`, `backend/src/mdcopilot_blog/ids.py`
- `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/unit/__init__.py`, `backend/tests/unit/test_ids.py`

Cache directories (`.ruff_cache`, `.mypy_cache`, `.pytest_cache`, `__pycache__`) may also appear; `.gitignore` already covers them.

---

### Task 2: Settings

Typed settings read from the environment that compose injects from `.env`:
- secrets are `SecretStr`;
- the safety validators refuse to start with an unsafe configuration;
- the class derives the database URLs and the session cookie name.

**Files:**
- Create: `backend/src/mdcopilot_blog/settings.py`
- Test: `backend/tests/unit/test_settings.py`

**Interfaces:**
- Consumes (Task 1): the `tools` service and the pytest, ruff and mypy config.
- Produces:
  - **Class.** `mdcopilot_blog.settings.Settings(BaseSettings)`. It has every field in the contract table, with the same python names, env names (`validation_alias`), types and defaults.
    - `model_config` is the contract's, plus `hide_input_in_errors=True`, which keeps secrets out of `ValidationError` text.
    - Extra validation:
      - `LOG_LEVEL` is upper-cased and must be one of `LOG_LEVELS`;
      - every route list must be non-empty;
      - numeric bounds apply: ports 1..65535, counts ≥ 1, `novelty_threshold` 0..1, cost ≥ 0, delay ≥ 0.
  - **URL and cookie helpers**
    - `Settings.database_url(self, database: str | None = None) -> sqlalchemy.URL` (driver `postgresql+psycopg`).
    - `Settings.dbos_system_database_url -> str` (property): the password is rendered, so never log it.
    - `Settings.session_cookie_name -> str` (property): `"__Host-mdcb_session"` when `session_cookie_secure`, else `"mdcb_session"`.
  - **Routes**
    - `Settings.route_values(self) -> dict[str, list[str]]` returns fresh copies, keyed in this order: `search, research, ideation, deep_research, writer, fact_check, clinical, editorial, seo` (the `AgentName` values except `hello`).
    - `ROUTE_FIELDS: tuple[str, ...]` (the nine route field names) and `RouteList = Annotated[list[str], NoDecode]`.
  - **Other module names**
    - `get_settings() -> Settings`: `@lru_cache(maxsize=1)`. Tests call `get_settings.cache_clear()`.
    - Constants `MIN_SESSION_SECRET_LENGTH = 32` and `LOG_LEVELS: frozenset[str]`.
  - **Error messages** (tests match on these):
    - `"BLOG_HUMAN_APPROVAL_REQUIRED=false is not allowed"`
    - `"SESSION_SECRET must be at least 32 characters ..."`
    - `"BLOG_AGENT_DAILY_RUN_TIME must be HH:MM ..."`
    - `"unknown timezone ..."`
    - `"BLOG_AGENT_WORD_COUNT_MIN must be less than BLOG_AGENT_WORD_COUNT_MAX"`
    - `"route must list at least one provider:model"`

**Behaviour to know** (verified in a container on 2026-09-17):
- **Field-name variables.** With `validate_by_name=True`, pydantic-settings also reads a variable spelled like the *field name* (for example `TIMEZONE`, `MOCK_MODE`, `PUBLISHER`) when the alias variable is absent. The alias wins when both are set, and `.env.example` sets every alias. The test fixture clears both spellings.
- **Empty values.** An empty value (`OPENAI_API_KEY=`) counts as unset (`env_ignore_empty=True`). For the two required secrets, that means "Field required".
- **No JSON decoding of routes.** A JSON-looking route value is **not** JSON-decoded (`NoDecode`).
- **Password characters.** `render_as_string(hide_password=False)` percent-encodes `@ : / %` but not spaces, so `POSTGRES_PASSWORD` must not contain spaces. The real `.env` password is 32 alphanumeric characters, and `SESSION_SECRET` is 64 hex characters. Only lengths and character classes were checked; the values were never printed.

- [ ] **Step 1: Write the failing test `backend/tests/unit/test_settings.py`**

```python
"""settings.py: env names, secrets, CSV routes, safety validators and derived URLs."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import URL

from mdcopilot_blog.settings import Settings, get_settings

SESSION_SECRET_VALUE = "s" * 40
DB_PASSWORD_VALUE = "db-pass-4f9e1c"


def _env_names() -> list[str]:
    names: list[str] = []
    for field in Settings.model_fields.values():
        assert isinstance(field.validation_alias, str), "every Settings field must set validation_alias"
        names.append(field.validation_alias)
    return names


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Start from an environment without any Settings variable, then set the two required secrets.

    The tools container receives the real .env through compose `env_file`, so every test clears it first.
    """
    for name in _env_names():
        monkeypatch.delenv(name, raising=False)
    # validate_by_name=True makes pydantic-settings also read a variable named after the field (e.g. TIMEZONE).
    for field_name in Settings.model_fields:
        monkeypatch.delenv(field_name.upper(), raising=False)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET_VALUE)
    monkeypatch.setenv("POSTGRES_PASSWORD", DB_PASSWORD_VALUE)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_every_field_is_read_from_its_env_name_without_prefix() -> None:
    names = _env_names()
    assert len(names) == len(set(names))
    for expected in (
        "APP_ENV",
        "SESSION_SECRET",
        "POSTGRES_PASSWORD",
        "OPENAI_API_KEY",
        "BLOG_AGENT_ENABLED",
        "BLOG_HUMAN_APPROVAL_REQUIRED",
        "BLOG_AGENT_WRITER_ROUTE",
        "BLOG_AGENT_MAX_COST_PER_RUN_USD",
        "BLOG_PUBLISHER_PASSWORD",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "WORKER_EXECUTOR_ID",
    ):
        assert expected in names


def test_defaults_match_env_example(env: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.app_env == "development"
    assert s.app_version == "0.1.0"
    assert s.log_level == "INFO"
    assert s.session_cookie_secure is False
    assert s.public_app_url == "http://localhost:8310"
    assert s.postgres_db == "mdcopilot_blog"
    assert s.postgres_user == "mdcopilot_blog"
    assert s.postgres_host == "db"
    assert s.postgres_port == 5432
    assert s.openai_api_key is None
    assert s.anthropic_api_key is None
    assert s.agent_enabled is True
    assert s.mock_mode is True
    assert s.mock_step_delay_seconds == 0.0
    assert s.scheduler_enabled is False
    assert s.human_approval_required is True
    assert s.publishing_enabled is False
    assert s.gemini_grounding_enabled is False
    assert s.daily_run_time == "07:00"
    assert s.timezone == "Asia/Kolkata"
    assert (s.research_window_days, s.min_source_count) == (7, 5)
    assert s.novelty_threshold == 0.85
    assert (s.word_count_min, s.word_count_max) == (850, 1150)
    assert s.site_url == "https://www.mdcopilot.health"
    assert s.default_category == "Healthcare AI"
    assert s.search_route == ["openai:gpt-5.6-luna"]
    assert s.writer_route == ["openai:gpt-5.6-sol", "google:gemini-3.8-flash", "anthropic:claude-sonnet-5"]
    assert s.seo_route == ["google:gemini-3.5-flash-lite", "openai:gpt-5.6-luna"]
    assert s.embedding_model == "google:gemini-embedding-2"
    assert s.embedding_dimensions == 1536
    assert s.max_cost_per_run_usd == Decimal("5.00")
    assert (s.discovery_timeout_minutes, s.production_timeout_minutes) == (15, 30)
    assert (s.max_parallel_searches, s.max_parallel_fetches) == (6, 12)
    assert s.publisher == "manual_export"
    assert s.publisher_api_url == "http://host.docker.internal:8000/api/v1"
    assert s.publisher_public_url == "http://localhost:3000"
    assert s.worker_executor_id == "worker-1"


@pytest.mark.parametrize("missing", ["SESSION_SECRET", "POSTGRES_PASSWORD"])
def test_required_secrets(env: pytest.MonkeyPatch, missing: str) -> None:
    env.delenv(missing)
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert missing in str(excinfo.value)


def test_empty_secret_counts_as_missing(env: pytest.MonkeyPatch) -> None:
    env.setenv("POSTGRES_PASSWORD", "")
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
        Settings()


def test_short_session_secret_is_refused_without_echoing_it(env: pytest.MonkeyPatch) -> None:
    env.setenv("SESSION_SECRET", "change-me")
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    message = str(excinfo.value)
    assert "at least 32 characters" in message
    assert "change-me" not in message


def test_secrets_are_secretstr_and_masked(env: pytest.MonkeyPatch) -> None:
    env.setenv("OPENAI_API_KEY", "sk-test-abcdef123456")
    env.setenv("BLOG_PUBLISHER_PASSWORD", "publisher-pass-xyz")
    s = Settings()
    assert isinstance(s.session_secret, SecretStr)
    assert isinstance(s.openai_api_key, SecretStr)
    assert s.openai_api_key.get_secret_value() == "sk-test-abcdef123456"
    rendered = repr(s) + str(s) + repr(s.model_dump())
    for raw in (SESSION_SECRET_VALUE, DB_PASSWORD_VALUE, "sk-test-abcdef123456", "publisher-pass-xyz"):
        assert raw not in rendered


def test_empty_optional_values_become_none(env: pytest.MonkeyPatch) -> None:
    env.setenv("OPENAI_API_KEY", "")
    env.setenv("BOOTSTRAP_ADMIN_EMAIL", "")
    env.setenv("BLOG_MDCOPILOT_PUBLIC_API_URL", "")
    s = Settings()
    assert s.openai_api_key is None
    assert s.bootstrap_admin_email is None
    assert s.mdcopilot_public_api_url is None


def test_csv_routes_are_split_and_trimmed(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_RESEARCH_ROUTE", " google:gemini-x , openai:gpt-y ,, ")
    env.setenv("BLOG_AGENT_SEARCH_ROUTE", "openai:only-one")
    s = Settings()
    assert s.research_route == ["google:gemini-x", "openai:gpt-y"]
    assert s.search_route == ["openai:only-one"]


def test_json_looking_route_is_not_json_decoded(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_SEO_ROUTE", '["openai:x"]')
    assert Settings().seo_route == ['["openai:x"]']


def test_empty_route_is_refused(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_WRITER_ROUTE", " , ")
    with pytest.raises(ValidationError, match="route must list at least one provider:model"):
        Settings()


def test_route_values_maps_agent_keys_to_routes(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_CLINICAL_ROUTE", "openai:a,google:b")
    routes = Settings().route_values()
    assert list(routes) == [
        "search",
        "research",
        "ideation",
        "deep_research",
        "writer",
        "fact_check",
        "clinical",
        "editorial",
        "seo",
    ]
    assert routes["clinical"] == ["openai:a", "google:b"]
    assert routes["fact_check"] == [
        "google:gemini-3.8-flash",
        "openai:gpt-5.6-terra",
        "anthropic:claude-sonnet-5",
    ]
    routes["clinical"].append("mutated")
    assert Settings().route_values()["clinical"] == ["openai:a", "google:b"]


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE"])
def test_human_approval_cannot_be_disabled(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_HUMAN_APPROVAL_REQUIRED", value)
    with pytest.raises(ValidationError, match="BLOG_HUMAN_APPROVAL_REQUIRED=false is not allowed"):
        Settings()


def test_boolean_flags_parse_from_env(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_MOCK_MODE", "false")
    env.setenv("BLOG_AGENT_SCHEDULER_ENABLED", "true")
    env.setenv("SESSION_COOKIE_SECURE", "1")
    s = Settings()
    assert (s.mock_mode, s.scheduler_enabled, s.session_cookie_secure) == (False, True, True)


@pytest.mark.parametrize("value", ["00:00", "07:00", "23:59", "09:05"])
def test_daily_run_time_accepts_hh_mm(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_DAILY_RUN_TIME", value)
    assert Settings().daily_run_time == value


@pytest.mark.parametrize("value", ["24:00", "7:00", "07:60", "0700", "07:00:00", "ab:cd", " 07:00"])
def test_daily_run_time_rejects_other_formats(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_DAILY_RUN_TIME", value)
    with pytest.raises(ValidationError, match="HH:MM"):
        Settings()


@pytest.mark.parametrize("value", ["UTC", "Asia/Kolkata", "America/New_York"])
def test_timezone_accepts_iana_names(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_TIMEZONE", value)
    assert Settings().timezone == value


@pytest.mark.parametrize("value", ["Mars/Olympus", "IST+5:30", "../etc/passwd", "Asia/"])
def test_timezone_rejects_unknown_names(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_TIMEZONE", value)
    with pytest.raises(ValidationError, match="unknown timezone"):
        Settings()


@pytest.mark.parametrize(("low", "high"), [("1150", "850"), ("900", "900")])
def test_word_count_min_must_be_below_max(env: pytest.MonkeyPatch, low: str, high: str) -> None:
    env.setenv("BLOG_AGENT_WORD_COUNT_MIN", low)
    env.setenv("BLOG_AGENT_WORD_COUNT_MAX", high)
    with pytest.raises(ValidationError, match="BLOG_AGENT_WORD_COUNT_MIN must be less than BLOG_AGENT_WORD_COUNT_MAX"):
        Settings()


def test_negative_mock_delay_is_refused(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_MOCK_STEP_DELAY_SECONDS", "-1")
    with pytest.raises(ValidationError):
        Settings()


def test_log_level_is_normalised_and_checked(env: pytest.MonkeyPatch) -> None:
    env.setenv("LOG_LEVEL", "debug")
    assert Settings().log_level == "DEBUG"
    env.setenv("LOG_LEVEL", "chatty")
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        Settings()


def test_invalid_literal_values_are_refused(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_PUBLISHER", "wordpress")
    with pytest.raises(ValidationError):
        Settings()


def test_python_field_names_are_accepted_as_init_kwargs(env: pytest.MonkeyPatch) -> None:
    s = Settings(postgres_db="other_db", mock_mode=False)
    assert (s.postgres_db, s.mock_mode) == ("other_db", False)


def test_database_url_builds_psycopg_url_and_hides_password(env: pytest.MonkeyPatch) -> None:
    env.setenv("POSTGRES_HOST", "db.internal")
    env.setenv("POSTGRES_PORT", "6543")
    s = Settings()
    url = s.database_url()
    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.host, url.port, url.database) == ("mdcopilot_blog", "db.internal", 6543, "mdcopilot_blog")
    assert url.password == DB_PASSWORD_VALUE
    assert DB_PASSWORD_VALUE not in repr(url)
    assert DB_PASSWORD_VALUE not in str(url)
    assert s.database_url("mdcopilot_blog_test").database == "mdcopilot_blog_test"


def test_dbos_system_database_url_renders_the_password(env: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.dbos_system_database_url == (
        f"postgresql+psycopg://mdcopilot_blog:{DB_PASSWORD_VALUE}@db:5432/mdcopilot_blog"
    )
    assert DB_PASSWORD_VALUE not in repr(s)


def test_dbos_system_database_url_percent_encodes_special_characters(env: pytest.MonkeyPatch) -> None:
    env.setenv("POSTGRES_PASSWORD", "p@ss:w/rd%")
    s = Settings()
    assert s.dbos_system_database_url == "postgresql+psycopg://mdcopilot_blog:p%40ss%3Aw%2Frd%25@db:5432/mdcopilot_blog"


def test_session_cookie_name_depends_on_secure_flag(env: pytest.MonkeyPatch) -> None:
    assert Settings().session_cookie_name == "mdcb_session"
    env.setenv("SESSION_COOKIE_SECURE", "true")
    assert Settings().session_cookie_name == "__Host-mdcb_session"


def test_get_settings_is_cached(env: pytest.MonkeyPatch) -> None:
    first = get_settings()
    assert get_settings() is first
    get_settings.cache_clear()
    assert get_settings() is not first
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
docker compose run --rm tools pytest tests/unit/test_settings.py -q
```
Expected:
```text
E   ModuleNotFoundError: No module named 'mdcopilot_blog.settings'
ERROR tests/unit/test_settings.py
1 error in <time>
```

- [ ] **Step 3: Write `backend/src/mdcopilot_blog/settings.py`**

```python
"""Application settings, read from the process environment.

Compose passes `.env` to every backend container through `env_file`, so the loader reads only
`os.environ` (`env_file=None`). Every field names its variable with `validation_alias`, using exactly
the names in `.env.example` (no prefix).

Because `validate_by_name=True`, pydantic-settings also reads a variable spelled like the field name
(e.g. `TIMEZONE`) when the alias variable is absent. The alias wins when both are set, and
`.env.example` sets every alias.

Secrets are `SecretStr`. They never appear in repr, logs or validation errors (`hide_input_in_errors=True`).
"""

import re
from decimal import Decimal
from functools import lru_cache
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

MIN_SESSION_SECRET_LENGTH = 32
LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})
_HH_MM = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")

# "a, b ,,c" -> ["a", "b", "c"]. NoDecode stops pydantic-settings from JSON-decoding the value first.
RouteList = Annotated[list[str], NoDecode]

ROUTE_FIELDS = (
    "search_route",
    "research_route",
    "ideation_route",
    "deep_research_route",
    "writer_route",
    "fact_check_route",
    "clinical_route",
    "editorial_route",
    "seo_route",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        env_ignore_empty=True,
        validate_by_name=True,
        validate_by_alias=True,
        hide_input_in_errors=True,
    )

    # --- App ---
    app_env: Literal["development", "test", "production"] = Field("development", validation_alias="APP_ENV")
    app_version: str = Field("0.1.0", validation_alias="APP_VERSION")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")

    # --- Sessions and bootstrap ---
    session_secret: SecretStr = Field(validation_alias="SESSION_SECRET")
    session_cookie_secure: bool = Field(False, validation_alias="SESSION_COOKIE_SECURE")
    public_app_url: str = Field("http://localhost:8310", validation_alias="PUBLIC_APP_URL")
    bootstrap_admin_email: str | None = Field(None, validation_alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: SecretStr | None = Field(None, validation_alias="BOOTSTRAP_ADMIN_PASSWORD")

    # --- Database ---
    postgres_db: str = Field("mdcopilot_blog", validation_alias="POSTGRES_DB")
    postgres_user: str = Field("mdcopilot_blog", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(validation_alias="POSTGRES_PASSWORD")
    postgres_host: str = Field("db", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, ge=1, le=65535, validation_alias="POSTGRES_PORT")

    # --- Provider keys ---
    openai_api_key: SecretStr | None = Field(None, validation_alias="OPENAI_API_KEY")
    gemini_api_key: SecretStr | None = Field(None, validation_alias="GEMINI_API_KEY")
    anthropic_api_key: SecretStr | None = Field(None, validation_alias="ANTHROPIC_API_KEY")
    ncbi_api_key: SecretStr | None = Field(None, validation_alias="NCBI_API_KEY")
    ncbi_contact_email: str | None = Field(None, validation_alias="NCBI_CONTACT_EMAIL")

    # --- Flags (environment-only safety switches) ---
    agent_enabled: bool = Field(True, validation_alias="BLOG_AGENT_ENABLED")
    mock_mode: bool = Field(True, validation_alias="BLOG_AGENT_MOCK_MODE")
    mock_step_delay_seconds: float = Field(0.0, ge=0, validation_alias="BLOG_AGENT_MOCK_STEP_DELAY_SECONDS")
    scheduler_enabled: bool = Field(False, validation_alias="BLOG_AGENT_SCHEDULER_ENABLED")
    human_approval_required: bool = Field(True, validation_alias="BLOG_HUMAN_APPROVAL_REQUIRED")
    publishing_enabled: bool = Field(False, validation_alias="BLOG_PUBLISHING_ENABLED")
    gemini_grounding_enabled: bool = Field(False, validation_alias="BLOG_GEMINI_GROUNDING_ENABLED")

    # --- Schedule and content ---
    daily_run_time: str = Field("07:00", validation_alias="BLOG_AGENT_DAILY_RUN_TIME")
    timezone: str = Field("Asia/Kolkata", validation_alias="BLOG_AGENT_TIMEZONE")
    research_window_days: int = Field(7, ge=1, validation_alias="BLOG_AGENT_RESEARCH_WINDOW_DAYS")
    min_source_count: int = Field(5, ge=1, validation_alias="BLOG_AGENT_MIN_SOURCE_COUNT")
    novelty_threshold: float = Field(0.85, ge=0, le=1, validation_alias="BLOG_AGENT_NOVELTY_THRESHOLD")
    word_count_min: int = Field(850, ge=1, validation_alias="BLOG_AGENT_WORD_COUNT_MIN")
    word_count_max: int = Field(1150, ge=1, validation_alias="BLOG_AGENT_WORD_COUNT_MAX")
    site_url: str = Field("https://www.mdcopilot.health", validation_alias="BLOG_SITE_URL")
    default_category: str = Field("Healthcare AI", validation_alias="BLOG_DEFAULT_CATEGORY")

    # --- Model routes: ordered "provider:model" lists, first = primary (defaults = .env.example) ---
    search_route: RouteList = Field(
        default_factory=lambda: ["openai:gpt-5.6-luna"],
        validation_alias="BLOG_AGENT_SEARCH_ROUTE",
    )
    research_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.8-flash", "openai:gpt-5.6-terra"],
        validation_alias="BLOG_AGENT_RESEARCH_ROUTE",
    )
    ideation_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.8-flash", "openai:gpt-5.6-terra"],
        validation_alias="BLOG_AGENT_IDEATION_ROUTE",
    )
    deep_research_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.8-flash", "openai:gpt-5.6-terra"],
        validation_alias="BLOG_AGENT_DEEP_RESEARCH_ROUTE",
    )
    writer_route: RouteList = Field(
        default_factory=lambda: ["openai:gpt-5.6-sol", "google:gemini-3.8-flash", "anthropic:claude-sonnet-5"],
        validation_alias="BLOG_AGENT_WRITER_ROUTE",
    )
    fact_check_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.8-flash", "openai:gpt-5.6-terra", "anthropic:claude-sonnet-5"],
        validation_alias="BLOG_AGENT_FACT_CHECK_ROUTE",
    )
    clinical_route: RouteList = Field(
        default_factory=lambda: ["openai:gpt-5.6-sol", "google:gemini-3.8-flash"],
        validation_alias="BLOG_AGENT_CLINICAL_ROUTE",
    )
    editorial_route: RouteList = Field(
        default_factory=lambda: ["openai:gpt-5.6-terra", "google:gemini-3.8-flash"],
        validation_alias="BLOG_AGENT_EDITORIAL_ROUTE",
    )
    seo_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.5-flash-lite", "openai:gpt-5.6-luna"],
        validation_alias="BLOG_AGENT_SEO_ROUTE",
    )
    embedding_model: str = Field("google:gemini-embedding-2", validation_alias="BLOG_AGENT_EMBEDDING_MODEL")
    embedding_dimensions: int = Field(1536, ge=1, validation_alias="BLOG_AGENT_EMBEDDING_DIMENSIONS")

    # --- Limits and guardrails ---
    max_cost_per_run_usd: Decimal = Field(Decimal("5.00"), ge=0, validation_alias="BLOG_AGENT_MAX_COST_PER_RUN_USD")
    discovery_timeout_minutes: int = Field(15, ge=1, validation_alias="BLOG_AGENT_DISCOVERY_TIMEOUT_MINUTES")
    production_timeout_minutes: int = Field(30, ge=1, validation_alias="BLOG_AGENT_PRODUCTION_TIMEOUT_MINUTES")
    max_parallel_searches: int = Field(6, ge=1, validation_alias="BLOG_AGENT_MAX_PARALLEL_SEARCHES")
    max_parallel_fetches: int = Field(12, ge=1, validation_alias="BLOG_AGENT_MAX_PARALLEL_FETCHES")
    fetch_contact: str | None = Field(None, validation_alias="BLOG_FETCH_CONTACT")

    # --- MDCopilot integration ---
    mdcopilot_public_api_url: str | None = Field(None, validation_alias="BLOG_MDCOPILOT_PUBLIC_API_URL")
    publisher: Literal["manual_export", "mdcopilot_api", "null"] = Field(
        "manual_export", validation_alias="BLOG_PUBLISHER"
    )
    publisher_api_url: str = Field("http://host.docker.internal:8000/api/v1", validation_alias="BLOG_PUBLISHER_API_URL")
    publisher_login_id: str | None = Field(None, validation_alias="BLOG_PUBLISHER_LOGIN_ID")
    publisher_password: SecretStr | None = Field(None, validation_alias="BLOG_PUBLISHER_PASSWORD")
    publisher_public_url: str = Field("http://localhost:3000", validation_alias="BLOG_PUBLISHER_PUBLIC_URL")

    # --- Observability and notifications ---
    otel_exporter_otlp_endpoint: str | None = Field(None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    notify_webhook_url: str | None = Field(None, validation_alias="BLOG_NOTIFY_WEBHOOK_URL")

    # --- Worker ---
    worker_executor_id: str = Field("worker-1", validation_alias="WORKER_EXECUTOR_ID")

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        if value not in LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(LOG_LEVELS)}")
        return value

    @field_validator("session_secret")
    @classmethod
    def _check_session_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_SESSION_SECRET_LENGTH:
            raise ValueError(
                f"SESSION_SECRET must be at least {MIN_SESSION_SECRET_LENGTH} characters (openssl rand -hex 32)"
            )
        return value

    @field_validator("daily_run_time")
    @classmethod
    def _check_daily_run_time(cls, value: str) -> str:
        if _HH_MM.fullmatch(value) is None:
            raise ValueError("BLOG_AGENT_DAILY_RUN_TIME must be HH:MM (00:00 to 23:59)")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError(f"unknown timezone {value!r} (use an IANA name such as Asia/Kolkata)") from exc
        return value

    @field_validator(*ROUTE_FIELDS, mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(*ROUTE_FIELDS)
    @classmethod
    def _check_route_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("route must list at least one provider:model")
        return value

    @model_validator(mode="after")
    def _approval_is_mandatory(self) -> Self:
        if not self.human_approval_required:
            raise ValueError("BLOG_HUMAN_APPROVAL_REQUIRED=false is not allowed")
        return self

    @model_validator(mode="after")
    def _check_word_counts(self) -> Self:
        if self.word_count_min >= self.word_count_max:
            raise ValueError("BLOG_AGENT_WORD_COUNT_MIN must be less than BLOG_AGENT_WORD_COUNT_MAX")
        return self

    def database_url(self, database: str | None = None) -> URL:
        """SQLAlchemy URL for the app database (or `database`). `str()`/`repr()` of a URL mask the password."""
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=database or self.postgres_db,
        )

    @property
    def dbos_system_database_url(self) -> str:
        """Plain URL string for DBOS (it does not accept a URL object). Contains the password: never log it.

        render_as_string percent-encodes "@", ":", "/" and "%", but NOT spaces, and libpq rejects a raw
        space, so POSTGRES_PASSWORD must not contain spaces. Generated hex passwords are fine.
        """
        return self.database_url().render_as_string(hide_password=False)

    @property
    def session_cookie_name(self) -> str:
        """`__Host-` cookies require Secure, so the prefix is only used when secure cookies are on."""
        return "__Host-mdcb_session" if self.session_cookie_secure else "mdcb_session"

    def route_values(self) -> dict[str, list[str]]:
        """Agent key (AgentName value) -> configured route. Returns copies, so callers cannot mutate settings."""
        return {
            "search": list(self.search_route),
            "research": list(self.research_route),
            "ideation": list(self.ideation_route),
            "deep_research": list(self.deep_research_route),
            "writer": list(self.writer_route),
            "fact_check": list(self.fact_check_route),
            "clinical": list(self.clinical_route),
            "editorial": list(self.editorial_route),
            "seo": list(self.seo_route),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings. Tests call `get_settings.cache_clear()` after changing the environment."""
    return Settings()
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
docker compose run --rm tools pytest tests/unit/test_settings.py -q
```
Expected: `47 passed`.

- [ ] **Step 5: Confirm the real `.env` satisfies the validators, printing no secrets**

```bash
docker compose run --rm tools python -c "from mdcopilot_blog.settings import get_settings; s = get_settings(); print('settings ok', s.app_env, s.mock_mode, s.scheduler_enabled, s.publisher, list(s.route_values()))"
```
Expected:
```text
settings ok development True False manual_export ['search', 'research', 'ideation', 'deep_research', 'writer', 'fact_check', 'clinical', 'editorial', 'seo']
```

Decision rule:
- **`SESSION_SECRET must be at least 32 characters`:** the owner regenerates it with `openssl rand -hex 32` and edits `.env` by hand.
- **Any other validation error:** fix the named variable in `.env`.

Never print `.env`. Validation errors never include input values (`hide_input_in_errors=True`).

- [ ] **Step 6: Lint and type-check**

```bash
docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"
```
Expected:
```text
All checks passed!
8 files already formatted
Success: no issues found in 3 source files
```

- [ ] **Step 7: Checkpoint: list the files changed in this task (no git)**

```bash
ls -la backend/src/mdcopilot_blog/settings.py backend/tests/unit/test_settings.py
```
Expected new files:
- `backend/src/mdcopilot_blog/settings.py`
- `backend/tests/unit/test_settings.py`

---

### Task 3: Logging and problem responses

Two pieces:
- **Logging:** JSON logs on stdout that carry `run_id`/`trace_id` from context variables and never contain secret values.
- **Problem responses:** `application/problem+json` for every API error, checked against a tiny FastAPI app through httpx `ASGITransport`, with no database.

**Files:**
- Create: `backend/src/mdcopilot_blog/logs.py`
- Create: `backend/src/mdcopilot_blog/errors.py`
- Create: `backend/tests/api/__init__.py`
- Test: `backend/tests/unit/test_logs.py`
- Test: `backend/tests/api/test_problem_errors.py`

**Interfaces:**
- Consumes (Task 1): the `tools` service and the pytest config (`asyncio_mode=auto`, session loop scope).
- Produces (`mdcopilot_blog.logs`):
  - **Setup.** `configure_logging(level: str) -> None`:
    - installs one stdout `StreamHandler` with `JsonFormatter` on the root logger, replacing any handler it installed earlier;
    - leaves other handlers alone;
    - makes `uvicorn`, `uvicorn.error` and `uvicorn.access` propagate to the root with no handlers of their own.

    Task 9 calls it inside `create_app`, and Task 11 calls it at worker start.
  - **Formatter.** `class JsonFormatter(logging.Formatter)`. Each line holds:
    - `ts` (ISO 8601 UTC, in milliseconds), `level`, `logger`, `message`;
    - the bound `run_id`/`trace_id`;
    - `extra` keys (which override the bound context), except uvicorn's `color_message`. That key is a duplicate of the message with ANSI colour codes; uvicorn 0.53.0 adds it to its startup, shutdown and reloader lines;
    - `exc_info`/`stack_info` when present.

    `SecretStr`, `SecretBytes` and `Secret` values, including nested ones, are replaced by `MASK = "**********"`. Other non-JSON values are converted with `str()`.
  - **Context.**
    - `bind_log_context(*, run_id: str | None = None, trace_id: str | None = None) -> contextvars.Token[LogContext | None]`: merges with the existing context.
    - `reset_log_context(token) -> None` and `log_context() -> dict[str, str]` (returns a copy).
    - `LogContext = Mapping[str, str]` and `UVICORN_LOGGERS`.
- Produces (`mdcopilot_blog.errors`):
  - **Constants.** `PROBLEM_JSON = "application/problem+json"` and `VALIDATION_TITLE = "Request validation failed"`.
  - **Exception.** `class ProblemError(Exception)`: `__init__(self, status: int, title: str, detail: object | None = None, type_: str = "about:blank")`.
    - Attributes: `.status`, `.title`, `.detail`, `.type_` (named `type_`, not `type`).
    - `str(exc) == title`.
  - **Response builder.** `problem_response(request, status, title, detail=None, type_="about:blank", *, headers: Mapping[str, str] | None = None) -> JSONResponse`.
    - The body is `{type, title, status, instance, detail?}`, where `instance` is `request.url.path`.
    - `detail` goes through `jsonable_encoder`.
  - **Validation cleanup.** `validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]`:
    - keeps only `type`, `loc`, `msg` and `ctx`;
    - drops `input`, which could echo a submitted password;
    - converts `ctx` values that are not plain JSON with `str()`.

    Task 9 tests must not assert on `input`.
  - **Handlers.** `install_problem_handlers(app: FastAPI) -> None` handles three cases.
    - **`ProblemError`.**
    - **Starlette `HTTPException`.** This includes router 404 and 405, and the response keeps `exc.headers` (e.g. `Allow`).
      - A `str` detail becomes the title.
      - Any other detail becomes `detail`, and the title is then the HTTP status phrase.
    - **`RequestValidationError`.** The response is 422, with title `"Request validation failed"` and `detail = validation_errors(exc)`.

- [ ] **Step 1: Write the failing test `backend/tests/unit/test_logs.py`**

```python
"""logs.py: one JSON object per line, run/trace context, extra keys, and no secret values."""

import asyncio
import io
import json
import logging
import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from pydantic import SecretBytes, SecretStr

from mdcopilot_blog.logs import (
    JsonFormatter,
    bind_log_context,
    configure_logging,
    log_context,
    reset_log_context,
)


@pytest.fixture
def captured() -> Iterator[tuple[logging.Logger, io.StringIO]]:
    """A private logger that writes JSON lines into a buffer (does not touch the root logger)."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("tests.logs.captured")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    yield logger, buffer
    logger.handlers = []


@pytest.fixture
def restore_root_logging() -> Iterator[None]:
    root = logging.getLogger()
    level = root.level
    yield
    for handler in list(root.handlers):
        if isinstance(handler.formatter, JsonFormatter):
            root.removeHandler(handler)
    root.setLevel(level)


def _lines(buffer: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines()]


def test_each_record_is_one_json_object(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info("hello %s", "world")
    logger.warning("second line")
    first, second = _lines(buffer)
    assert set(first) == {"ts", "level", "logger", "message"}
    assert first["level"] == "INFO"
    assert first["logger"] == "tests.logs.captured"
    assert first["message"] == "hello world"
    assert second["level"] == "WARNING"
    assert isinstance(first["ts"], str)
    assert datetime.fromisoformat(first["ts"]).utcoffset() == UTC.utcoffset(None)


def test_bound_context_is_added_and_reset(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    token = bind_log_context(run_id="run-123", trace_id="a" * 32)
    try:
        logger.info("inside")
    finally:
        reset_log_context(token)
    logger.info("outside")
    inside, outside = _lines(buffer)
    assert inside["run_id"] == "run-123"
    assert inside["trace_id"] == "a" * 32
    assert "run_id" not in outside
    assert "trace_id" not in outside


def test_bind_merges_with_existing_context() -> None:
    assert log_context() == {}
    outer = bind_log_context(run_id="run-1")
    inner = bind_log_context(trace_id="b" * 32)
    try:
        assert log_context() == {"run_id": "run-1", "trace_id": "b" * 32}
    finally:
        reset_log_context(inner)
        assert log_context() == {"run_id": "run-1"}
        reset_log_context(outer)
    assert log_context() == {}


def test_log_context_returns_a_copy() -> None:
    token = bind_log_context(run_id="run-1")
    try:
        log_context()["run_id"] = "tampered"
        assert log_context() == {"run_id": "run-1"}
    finally:
        reset_log_context(token)


async def test_context_is_isolated_per_task(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured

    async def work(run_id: str) -> None:
        bind_log_context(run_id=run_id)
        await asyncio.sleep(0)
        logger.info("step")

    await asyncio.gather(work("run-a"), work("run-b"))
    assert sorted(str(line["run_id"]) for line in _lines(buffer)) == ["run-a", "run-b"]
    assert log_context() == {}


def test_extra_keys_are_included(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info("step finished", extra={"step": "hello.echo", "attempt": 2, "tags": ("a", "b"), "ok": True})
    (line,) = _lines(buffer)
    assert line["step"] == "hello.echo"
    assert line["attempt"] == 2
    assert line["tags"] == ["a", "b"]
    assert line["ok"] is True


def test_uvicorn_color_message_is_dropped(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info(
        "Uvicorn running on %s",
        "http://0.0.0.0:8000",
        extra={"color_message": "Uvicorn running on \x1b[1m%s\x1b[0m"},
    )
    output = buffer.getvalue()
    (line,) = _lines(buffer)
    assert "color_message" not in line
    assert line["message"] == "Uvicorn running on http://0.0.0.0:8000"
    assert "\x1b" not in output
    assert "\\u001b" not in output


def test_explicit_extra_overrides_bound_context(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    token = bind_log_context(run_id="from-context")
    try:
        logger.info("override", extra={"run_id": "from-extra"})
    finally:
        reset_log_context(token)
    assert _lines(buffer)[0]["run_id"] == "from-extra"


def test_non_json_values_are_stringified(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    when = datetime(2026, 9, 17, 7, 0, tzinfo=UTC)
    ident = uuid.UUID(int=1)
    logger.info("typed", extra={"when": when, "ident": ident, "nested": {"ids": [ident]}})
    (line,) = _lines(buffer)
    assert line["when"] == "2026-09-17 07:00:00+00:00"
    assert line["ident"] == "00000000-0000-0000-0000-000000000001"
    assert line["nested"] == {"ids": ["00000000-0000-0000-0000-000000000001"]}


def test_secret_values_never_appear(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    logger.info(
        "key=%s repr=%r",
        SecretStr("sk-live-message-arg"),
        SecretStr("sk-live-repr-arg"),
        extra={
            "api_key": SecretStr("sk-live-extra"),
            "raw_bytes": SecretBytes(b"bytes-secret-value"),
            "nested": {"password": SecretStr("nested-password"), "list": [SecretStr("listed-secret")]},
        },
    )
    output = buffer.getvalue()
    for raw in ("sk-live-message-arg", "sk-live-repr-arg", "sk-live-extra", "bytes-secret-value"):
        assert raw not in output
    assert "nested-password" not in output
    assert "listed-secret" not in output
    (line,) = _lines(buffer)
    assert line["api_key"] == "**********"
    assert line["raw_bytes"] == "**********"
    assert line["nested"] == {"password": "**********", "list": ["**********"]}


def test_exception_text_is_included(captured: tuple[logging.Logger, io.StringIO]) -> None:
    logger, buffer = captured
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("step failed")
    (line,) = _lines(buffer)
    assert line["level"] == "ERROR"
    assert "ValueError: boom" in str(line["exc_info"])


@pytest.mark.usefixtures("restore_root_logging")
def test_configure_logging_installs_one_json_handler_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("debug")
    configure_logging("DEBUG")
    root = logging.getLogger()
    ours = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
    assert len(ours) == 1
    assert isinstance(ours[0], logging.StreamHandler)
    assert ours[0].stream is sys.stdout
    assert root.level == logging.DEBUG
    logging.getLogger("tests.logs.root").debug("via root", extra={"step": "x"})
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[-1]["message"] == "via root"
    assert lines[-1]["step"] == "x"


@pytest.mark.usefixtures("restore_root_logging")
def test_configure_logging_routes_uvicorn_loggers_through_root() -> None:
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addHandler(logging.NullHandler())
    uvicorn_access.propagate = False
    configure_logging("INFO")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
docker compose run --rm tools pytest tests/unit/test_logs.py -q
```
Expected:
```text
E   ModuleNotFoundError: No module named 'mdcopilot_blog.logs'
ERROR tests/unit/test_logs.py
1 error in <time>
```

- [ ] **Step 3: Write `backend/src/mdcopilot_blog/logs.py`**

```python
"""Structured JSON logs on stdout, carrying `run_id` and `trace_id` from context variables.

Secret values never reach the output: `SecretStr`, `SecretBytes` and `Secret` values in `extra`
(including nested dicts and lists) are replaced with a mask, and pydantic already masks them in
`str()`/`repr()`, which covers `%s`/`%r` message arguments. Never log `get_secret_value()`.
"""

import json
import logging
import sys
from collections.abc import Mapping
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from types import MappingProxyType

from pydantic import Secret, SecretBytes, SecretStr

MASK = "**********"
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
# Attributes every LogRecord has; anything else on a record came from `extra=`. Also skipped:
# "color_message", which uvicorn adds via `extra=` as an ANSI-coloured duplicate of the message.
_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "color_message",
}

LogContext = Mapping[str, str]
_log_context: ContextVar[LogContext | None] = ContextVar("mdcopilot_blog_log_context", default=None)


def bind_log_context(*, run_id: str | None = None, trace_id: str | None = None) -> Token[LogContext | None]:
    """Add `run_id`/`trace_id` to the current context (merged with what is already bound).

    Returns the token for `reset_log_context`. Each asyncio task works on its own copy of the context.
    """
    merged = dict(_log_context.get() or {})
    if run_id is not None:
        merged["run_id"] = run_id
    if trace_id is not None:
        merged["trace_id"] = trace_id
    return _log_context.set(MappingProxyType(merged))


def reset_log_context(token: Token[LogContext | None]) -> None:
    """Restore the context that was active before the matching `bind_log_context` call."""
    _log_context.reset(token)


def log_context() -> dict[str, str]:
    """A copy of the currently bound context (empty when nothing is bound)."""
    return dict(_log_context.get() or {})


def _redact(value: object) -> object:
    if isinstance(value, SecretStr | SecretBytes | Secret):
        return MASK
    if isinstance(value, Mapping):
        return {str(key): _redact(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_redact(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, message, bound context, then `extra` keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(log_context())
        for key, value in record.__dict__.items():
            if key not in _RECORD_ATTRS and not key.startswith("_"):
                payload[key] = _redact(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    """Send every log record to stdout as JSON at `level` (a name such as "INFO").

    Safe to call more than once: it replaces the handler it installed earlier and leaves other root
    handlers (for example pytest's capture handler) alone. Uvicorn's loggers lose their own handlers and
    propagate to the root, so access and error logs are JSON too. Call it after uvicorn has configured
    logging (inside the app factory) and at worker start-up.
    """
    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing.formatter, JsonFormatter):
            root.removeHandler(existing)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
docker compose run --rm tools pytest tests/unit/test_logs.py -q
```
Expected: `13 passed`.

`test_uvicorn_color_message_is_dropped` covers a real uvicorn 0.53.0 behaviour: `uvicorn/server.py`, `config.py` and `supervisors/*.py` log with `extra={"color_message": ...}`. Without the exclusion, lines such as `Uvicorn running on ...` would carry a second, ANSI-coloured copy of the message.

- [ ] **Step 5: Create `backend/tests/api/__init__.py` and the failing test `backend/tests/api/test_problem_errors.py`**

`backend/tests/api/__init__.py`:
```python
"""API tests (HTTP through httpx ASGITransport)."""
```

`backend/tests/api/test_problem_errors.py`:
```python
"""errors.py: problem+json for ProblemError, HTTP errors and request validation (tiny app, no database)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field, field_validator

from mdcopilot_blog.errors import PROBLEM_JSON, ProblemError, install_problem_handlers


class SignupIn(BaseModel):
    email: str
    password: str = Field(min_length=12)

    @field_validator("email")
    @classmethod
    def _needs_at_sign(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must contain @")
        return value


def build_app() -> FastAPI:
    app = FastAPI()
    install_problem_handlers(app)

    @app.get("/conflict")
    async def conflict() -> None:
        raise ProblemError(
            409,
            "User already exists",
            {"field": "email"},
            type_="https://www.mdcopilot.health/problems/conflict",
        )

    @app.get("/unauthenticated")
    async def unauthenticated() -> None:
        raise ProblemError(401, "Not authenticated")

    @app.get("/typed")
    async def typed() -> None:
        raise ProblemError(400, "Typed detail", {"id": uuid.UUID(int=1), "at": datetime(2026, 9, 17, tzinfo=UTC)})

    @app.get("/items/{item_id}")
    async def item(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    @app.get("/teapot")
    async def teapot() -> None:
        raise HTTPException(status_code=418, detail="Short and stout", headers={"X-Tea": "earl-grey"})

    @app.get("/structured")
    async def structured() -> None:
        raise HTTPException(status_code=400, detail={"reason": "bad"})

    @app.post("/signup")
    async def signup(body: SignupIn) -> dict[str, str]:
        return {"email": body.email}

    return app


@pytest.fixture
async def problem_client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://test") as client:
        yield client


async def test_problem_error_renders_problem_json(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/conflict")
    assert r.status_code == 409
    assert r.headers["content-type"] == PROBLEM_JSON == "application/problem+json"
    assert r.json() == {
        "type": "https://www.mdcopilot.health/problems/conflict",
        "title": "User already exists",
        "status": 409,
        "instance": "/conflict",
        "detail": {"field": "email"},
    }


async def test_problem_error_without_detail_omits_detail(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/unauthenticated")
    assert r.status_code == 401
    assert r.json() == {
        "type": "about:blank",
        "title": "Not authenticated",
        "status": 401,
        "instance": "/unauthenticated",
    }


async def test_problem_detail_is_made_json_safe(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/typed")
    assert r.json()["detail"] == {"id": "00000000-0000-0000-0000-000000000001", "at": "2026-09-17T00:00:00+00:00"}


def test_problem_error_keeps_its_fields() -> None:
    exc = ProblemError(403, "Forbidden", "missing permission blog.settings")
    assert (exc.status, exc.title, exc.detail, exc.type_) == (
        403,
        "Forbidden",
        "missing permission blog.settings",
        "about:blank",
    )
    assert str(exc) == "Forbidden"


async def test_unknown_route_is_problem_json_404(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/nope")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json() == {"type": "about:blank", "title": "Not Found", "status": 404, "instance": "/nope"}


async def test_method_not_allowed_keeps_allow_header(problem_client: AsyncClient) -> None:
    r = await problem_client.post("/conflict")
    assert r.status_code == 405
    assert r.headers["content-type"] == "application/problem+json"
    assert r.headers["allow"] == "GET"
    assert r.json()["title"] == "Method Not Allowed"


async def test_http_exception_keeps_title_and_headers(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/teapot")
    assert r.status_code == 418
    assert r.headers["x-tea"] == "earl-grey"
    assert r.json() == {"type": "about:blank", "title": "Short and stout", "status": 418, "instance": "/teapot"}


async def test_http_exception_with_structured_detail(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/structured")
    assert r.status_code == 400
    assert r.json() == {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "instance": "/structured",
        "detail": {"reason": "bad"},
    }


async def test_path_validation_error_is_problem_json(problem_client: AsyncClient) -> None:
    r = await problem_client.get("/items/abc")
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["title"] == "Request validation failed"
    assert body["instance"] == "/items/abc"
    (error,) = body["detail"]
    assert error["loc"] == ["path", "item_id"]
    assert error["type"] == "int_parsing"
    assert set(error) <= {"type", "loc", "msg", "ctx"}


async def test_body_validation_error_never_echoes_input(problem_client: AsyncClient) -> None:
    r = await problem_client.post("/signup", json={"email": "a@example.com", "password": "tiny-secret"})
    assert r.status_code == 422
    assert "tiny-secret" not in r.text
    (error,) = r.json()["detail"]
    assert error["loc"] == ["body", "password"]
    assert error["type"] == "string_too_short"
    assert error["ctx"] == {"min_length": 12}


async def test_validator_error_context_is_json_safe(problem_client: AsyncClient) -> None:
    r = await problem_client.post("/signup", json={"email": "nobody", "password": "long-enough-password"})
    assert r.status_code == 422
    assert "long-enough-password" not in r.text
    (error,) = r.json()["detail"]
    assert error["loc"] == ["body", "email"]
    assert error["msg"] == "Value error, email must contain @"
    assert error["ctx"] == {"error": "email must contain @"}
```

- [ ] **Step 6: Run the test and watch it fail**

```bash
docker compose run --rm tools pytest tests/api/test_problem_errors.py -q
```
Expected:
```text
E   ModuleNotFoundError: No module named 'mdcopilot_blog.errors'
ERROR tests/api/test_problem_errors.py
1 error in <time>
```

- [ ] **Step 7: Write `backend/src/mdcopilot_blog/errors.py`**

```python
"""Problem details (RFC 9457, `application/problem+json`) for every API error."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"
VALIDATION_TITLE = "Request validation failed"


class ProblemError(Exception):
    """Raise anywhere in a request to return a problem+json response."""

    def __init__(self, status: int, title: str, detail: object | None = None, type_: str = "about:blank") -> None:
        super().__init__(title)
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: object | None = None,
    type_: str = "about:blank",
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Body `{type, title, status, instance, detail?}`; `detail` is made JSON-safe with `jsonable_encoder`."""
    body: dict[str, Any] = {"type": type_, "title": title, "status": status, "instance": request.url.path}
    if detail is not None:
        body["detail"] = jsonable_encoder(detail)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def _status_phrase(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def _plain(value: object) -> object:
    return value if value is None or isinstance(value, str | int | float | bool) else str(value)


def validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """`exc.errors()` without `input` (it can echo a submitted password) and with `ctx` values as plain JSON."""
    cleaned: list[dict[str, Any]] = []
    for error in exc.errors():
        item: dict[str, Any] = {key: error[key] for key in ("type", "loc", "msg") if key in error}
        ctx = error.get("ctx")
        if isinstance(ctx, Mapping):
            item["ctx"] = {str(key): _plain(value) for key, value in ctx.items()}
        cleaned.append(item)
    return cleaned


def install_problem_handlers(app: FastAPI) -> None:
    """Map ProblemError, Starlette/FastAPI HTTPException (incl. 404/405) and RequestValidationError."""

    @app.exception_handler(ProblemError)
    async def _problem_error(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(request, exc.status, exc.title, exc.detail, exc.type_)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, str):
            title, detail = exc.detail, None
        else:
            title, detail = _status_phrase(exc.status_code), exc.detail
        return problem_response(request, exc.status_code, title, detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(request, 422, VALIDATION_TITLE, validation_errors(exc))
```

- [ ] **Step 8: Run the test and watch it pass**

```bash
docker compose run --rm tools pytest tests/api/test_problem_errors.py -q
```
Expected: `11 passed`.

What this proves (verified on 2026-09-17):
- **Content type:** exactly `application/problem+json`.
- **Unknown route:** 404 with title `Not Found` and no `detail`.
- **Wrong method:** 405 keeps `allow: GET`.
- **Validation errors:**
  - a bad path parameter gives `loc == ["path", "item_id"]` and `type == "int_parsing"`;
  - a submitted password never appears in a 422 response;
  - a `ValueError` raised in a validator becomes `ctx == {"error": "<message>"}`.

- [ ] **Step 9: Run the whole suite, then lint and type-check**

```bash
docker compose run --rm tools pytest -q
docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"
```
Expected:
- the test run prints `75 passed` (4 ids, 47 settings, 13 logs, 11 problem responses);
- the lint and type check print:
```text
All checks passed!
13 files already formatted
Success: no issues found in 5 source files
```

- [ ] **Step 10: Checkpoint: list the files changed in this task (no git)**

```bash
ls -la backend/src/mdcopilot_blog/logs.py backend/src/mdcopilot_blog/errors.py backend/tests/unit/test_logs.py backend/tests/api
```
Expected new files:
- `backend/src/mdcopilot_blog/logs.py`, `backend/src/mdcopilot_blog/errors.py`
- `backend/tests/unit/test_logs.py`
- `backend/tests/api/__init__.py`, `backend/tests/api/test_problem_errors.py`

---

### Task 4: Domain model (enums, RBAC, state machine, contracts)

This task builds the pure domain layer. It has no database, network or settings access. It contains:
- the shared enums;
- the role → permission matrix (ARCHITECTURE §17);
- the run, article and publication transition tables (ARCHITECTURE §6);
- the typed contracts (ARCHITECTURE §12).

Every later task imports from here.

**Verified.** The code and tests below were run exactly as written, in throwaway containers, on 2026-09-17.
- **Test result:** 727 passed (60 RBAC, 405 state machine, 262 contracts).
- **Versions:** `ghcr.io/astral-sh/uv:0.12.15-python3.12-trixie-slim`, pydantic 2.13.5, pytest 9.1.1, pytest-asyncio 1.4.0.
- **Lint and types:** `ruff check` (ruff 0.16.8 defaults, line length 120, the contract's per-file ignores) printed "All checks passed!". `ruff format --check` passed. `mypy --strict` with `pydantic.mypy` printed "Success" for `src` and for the test files.
- **Re-checked on the Task 1–3 tree.** On 2026-09-17 the files were re-run in the Task 1–3 dev image, together with the Task 1–3 files.
  - The contract version and the Step 0 "yes" version each gave `727 passed` (`405` for the state machine).
  - Both printed `21 files already formatted` and `no issues found in 10 source files`.
  - With only Task 1 underneath, the counts were 14 and 7.

**Design decisions** (read these before touching other tasks):
- **Enum member names.** Every enum uses UPPER_CASE member names; the values keep the case in the contract. Examples: `Role.ADMIN == "admin"`, `RunKind.MANUAL == "manual"`, `CallKind.SEARCH == "search"`, `CallStatus.OK == "ok"`, `AgentName.HELLO == "hello"`. The contract's CLI line says `Role.admin`; the correct spelling is `Role.ADMIN`.
- **Same-state moves.** `can_transition` returns True when the current state equals the target, for any **known** state. Retried or forked steps can therefore rewrite a status safely.
- **Unknown states.** Unknown or wrong-entity states are never allowed, and neither is wrong case (`"queued"`).
- **Pickling.** `InvalidTransition` keeps `(entity, current, target)` in `args`. That makes it survive pickling, which DBOS 3.0.0's `DefaultSerializer` uses for step errors (checked: it is `pickle` + base64). An exception that passes only a message to `super().__init__` fails to unpickle with `TypeError: __init__() missing 2 required positional arguments`.
  - `str(exc)` is `"illegal <entity> transition: <current> -> <target>"`.
  - `exc.current` and `exc.target` are plain `str`.
- **Read-only tables.** `TRANSITIONS` and `ROLE_PERMISSIONS` are `MappingProxyType`, so they cannot be changed at runtime.
- **Unknown roles.** `permissions_for` returns an empty set for an unknown role (deny by default). A role string read from the database works as-is.
- **Required fields.** §12 gives no defaults, so every contract field is required. Nullable fields (`published_at`, `source_id`, `recommended_revision`, `selected_title`, `social`) must be sent explicitly as `null`.
- **Casing.** Contracts accept snake_case and camelCase input, serialise camelCase by default (`model_dump()`, `model_dump_json()`, `model_json_schema()`), and reject unknown keys.
- **Keys inside data.** Dict keys inside data (for example the keys of `score_breakdown`) are not renamed.
- **Error locations.** A pydantic error `loc` names the key the client actually sent: `("sentence_index",)` for snake input, `("sentenceIndex",)` for camel input. A missing field is reported by its camel alias.
- **Numeric bounds.**
  - Every `float` in the contracts is a score, weight, similarity or confidence, bounded `0 ≤ x ≤ 1` through `UnitScore`. A test enforces that no unbounded float can be added.
  - `ClaimCheck.sentence_index ≥ 0` and `GeneratedBlogPost.version_no ≥ 1`.
- **Field types that differ from §12.**
  - `TopicCandidate.status` is `str` (candidate statuses arrive in Phase 3).
  - `ResearchFinding.claim_type` uses the `ClaimType` enum, whose values are exactly §12's literal.

**Files:**
- Create: `backend/src/mdcopilot_blog/domain/__init__.py`
- Create: `backend/src/mdcopilot_blog/domain/enums.py`
- Create: `backend/src/mdcopilot_blog/domain/rbac.py`
- Create: `backend/src/mdcopilot_blog/domain/state_machine.py`
- Create: `backend/src/mdcopilot_blog/domain/contracts.py`
- Test: `backend/tests/unit/test_rbac.py`
- Test: `backend/tests/unit/test_state_machine.py`
- Test: `backend/tests/unit/test_contracts.py`

**Interfaces:**
- **Consumes** (Task 1 only):
  - the installed `mdcopilot_blog` package (editable from `/app/src`);
  - `pydantic` in `pyproject.toml`;
  - the `[tool.pytest]` / `[tool.ruff]` / `[tool.mypy]` config;
  - the compose `tools` service.
- **Produces:**
  - `mdcopilot_blog.domain.enums`, all `StrEnum` with UPPER_CASE member names:
    - `Role`: VIEWER, EDITOR, REVIEWER, PUBLISHER, ADMIN.
    - `Permission`: VIEW="blog.view", GENERATE, EDIT, REVIEW, APPROVE, SCHEDULE, PUBLISH, AGENT_RUNS="blog.agent_runs", SETTINGS.
    - `RunKind`: DAILY, MANUAL.
    - `RunStatus`, `AttemptStatus`, `StepStatus`, `ArticleStatus`, `PublicationStatus`: values exactly as in the contract.
    - `CallKind`: AGENT, SEARCH, EMBEDDING.
    - `CallStatus`: OK, ERROR.
    - `AgentName`: SEARCH, RESEARCH, IDEATION, DEEP_RESEARCH, WRITER, FACT_CHECK, CLINICAL, EDITORIAL, SEO, HELLO.
  - `mdcopilot_blog.domain.rbac`:
    - `ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]]`
    - `permissions_for(role: Role) -> frozenset[Permission]`
  - `mdcopilot_blog.domain.state_machine`:
    - `class Entity(StrEnum)` with RUN="run", ARTICLE="article", PUBLICATION="publication".
    - `class InvalidTransition(ValueError)`, constructed as `InvalidTransition(entity: Entity, current: str, target: str)`, with attributes `.entity`, `.current` and `.target`.
    - `TRANSITIONS: Mapping[Entity, Mapping[str, frozenset[str]]]`
    - `can_transition(entity: Entity, current: str, target: str) -> bool`
    - `require_transition(entity: Entity, current: str, target: str) -> None`
  - `mdcopilot_blog.domain.contracts`:
    - Base: `Contract`, and the alias `UnitScore = Annotated[float, Field(ge=0, le=1)]`.
    - Enums: `SourceType`, `ClaimType`, `VerificationStatus`, `ClaimKind`, `NoveltyDecision`, `PillarKey`.
    - Research: `ResearchSource`, `ResearchFinding`.
    - Topics and novelty: `NewsRef`, `ScoreItem`, `NoveltyNeighbour`, `NoveltyResult`, `TopicCandidate`.
    - Article parts: `TitleOptions`, `InternalLink`, `SEOMetadata`, `SocialCopy`, `BlogSource`.
    - Reviews: `ClaimCheck`, `FactCheckResult`, `ClinicalFlag`, `ClinicalReview`, `Change`, `EditorialReview`, `GateResult`, `GateReport`.
    - Article view: `GeneratedBlogPost`.
- **Notes for dependants:**
  - **T9 and T12:** map `InvalidTransition` to 409.
  - **T12, cancelling a run.** `require_transition(Entity.RUN, "CANCELLED", "CANCELLED")` does **not** raise (same-state no-op); SUCCEEDED/FAILED → CANCELLED do raise. T12 must decide whether cancelling an already-cancelled run returns 202 (idempotent) or 409.
  - **T11 and T12, finished runs.** "Terminal" for a run means {SUCCEEDED, FAILED, CANCELLED}. Those states can only move to QUEUED; this module exports no terminal-run constant.

All commands run from `mdcopilot-blog/`.

- [ ] **Step 0: Get the owner's decision on `WAITING_FOR_TOPIC → FAILED` (before any code)**

The run table below follows the contract: `WAITING_FOR_TOPIC` can move to `TOPICS_READY`, `PRODUCING` or `CANCELLED`, but **not** to `FAILED`. Ask the owner this question and wait for the answer:

> May a run that is waiting for a human to pick a topic be marked `FAILED`?

**Why it matters.**
- In manual mode, discovery ends with the run in `WAITING_FOR_TOPIC` (ARCHITECTURE §5.1, step D7).
- A later workflow on the same run can still fail while the run is in that state. Examples are `regenerate_topics` (ARCHITECTURE §5.3) or a workflow that times out.
- Without the edge, `require_transition(Entity.RUN, "WAITING_FOR_TOPIC", "FAILED")` raises `InvalidTransition`. That failure can then only be recorded as `CANCELLED`, or not at all.
- **Phase 1 impact:** none at runtime. The hello pipeline never enters `WAITING_FOR_TOPIC`. The first workflow that can reach this case arrives in Phase 3.

**If the answer is "no", or there is no answer yet:** build Steps 1–16 exactly as shown. That is the contract as written.

**If the answer is "yes":** build Steps 1–16 as shown, with the four line changes below. Use the new lines when you create each file.
1. In `backend/src/mdcopilot_blog/domain/state_machine.py` (Step 9), inside `_RUN`, replace this line:
   ```python
           RunStatus.WAITING_FOR_TOPIC: {RunStatus.TOPICS_READY, RunStatus.PRODUCING, RunStatus.CANCELLED},
   ```
   with these lines (the one-line form is over 120 characters, so it is split the way `ruff format` writes it):
   ```python
           RunStatus.WAITING_FOR_TOPIC: {
               RunStatus.TOPICS_READY,
               RunStatus.PRODUCING,
               RunStatus.FAILED,
               RunStatus.CANCELLED,
           },
   ```
2. In `backend/tests/unit/test_state_machine.py` (Step 7), make the same replacement inside `EXPECTED` (same line, same indentation).
3. In the same test file, replace
   ```python
       assert edge_counts == {Entity.RUN: 20, Entity.ARTICLE: 51, Entity.PUBLICATION: 6}
   ```
   with
   ```python
       assert edge_counts == {Entity.RUN: 21, Entity.ARTICLE: 51, Entity.PUBLICATION: 6}
   ```
4. In the same test file, replace
   ```python
       assert (len(ALLOWED), len(ILLEGAL), len(SAME_STATE)) == (77, 249, 30)
   ```
   with
   ```python
       assert (len(ALLOWED), len(ILLEGAL), len(SAME_STATE)) == (78, 248, 30)
   ```

With the edge, there are 78 allowed moves (run 21) and 248 other state pairs. Step 10 still prints `405 passed` and Step 15 still prints `727 passed`, because one case moves from the rejected list to the allowed list. None of the 21 named illegal moves uses this edge, so that list is the same in both versions. Both versions were run in a container on 2026-09-17, and each passed its tests, ruff and mypy.

A "yes" also changes one line outside this task: Task 14's documentation edits must record the new edge in ARCHITECTURE §6, as `WAITING_FOR_TOPIC → FAILED` (a follow-up workflow failed while waiting for a topic). Task 14 Step 13j makes that edit when this task's checkpoint records "added".

Write the owner's answer in the Step 17 checkpoint.

- [ ] **Step 1: Write the failing RBAC test**

Create `backend/tests/unit/test_rbac.py`. It writes the §17 table out row by row, independently of the implementation. It then checks:
- every one of the 45 role × permission cells;
- that the roles are strictly nested;
- that an unknown role gets nothing;
- that the matrix is read-only.

```python
"""RBAC matrix (ARCHITECTURE §17): exact permissions per role, deny by default."""

from itertools import pairwise
from typing import cast

import pytest

from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import ROLE_PERMISSIONS, permissions_for

# ARCHITECTURE §17, one row per permission. Columns: viewer, editor, reviewer, publisher, admin ("X" = granted).
SPEC_MATRIX: dict[Permission, str] = {
    Permission.VIEW: "XXXXX",
    Permission.GENERATE: ".XXXX",
    Permission.EDIT: ".XXXX",
    Permission.REVIEW: "..XXX",
    Permission.APPROVE: "..XXX",
    Permission.SCHEDULE: "..XXX",
    Permission.PUBLISH: "...XX",
    Permission.AGENT_RUNS: "..XXX",
    Permission.SETTINGS: "....X",
}
ROLE_COLUMNS: tuple[Role, ...] = (Role.VIEWER, Role.EDITOR, Role.REVIEWER, Role.PUBLISHER, Role.ADMIN)

EXPECTED: dict[Role, set[Permission]] = {
    Role.VIEWER: {Permission.VIEW},
    Role.EDITOR: {Permission.VIEW, Permission.GENERATE, Permission.EDIT},
    Role.REVIEWER: {
        Permission.VIEW,
        Permission.GENERATE,
        Permission.EDIT,
        Permission.REVIEW,
        Permission.APPROVE,
        Permission.SCHEDULE,
        Permission.AGENT_RUNS,
    },
    Role.PUBLISHER: {
        Permission.VIEW,
        Permission.GENERATE,
        Permission.EDIT,
        Permission.REVIEW,
        Permission.APPROVE,
        Permission.SCHEDULE,
        Permission.AGENT_RUNS,
        Permission.PUBLISH,
    },
    Role.ADMIN: set(Permission),
}

MATRIX_CELLS = [
    pytest.param(role, permission, SPEC_MATRIX[permission][column] == "X", id=f"{role}-{permission}")
    for permission in Permission
    for column, role in enumerate(ROLE_COLUMNS)
]


def test_role_values_match_the_wire_contract() -> None:
    assert [role.value for role in Role] == ["viewer", "editor", "reviewer", "publisher", "admin"]


def test_permission_values_match_the_wire_contract() -> None:
    assert {permission.name: permission.value for permission in Permission} == {
        "VIEW": "blog.view",
        "GENERATE": "blog.generate",
        "EDIT": "blog.edit",
        "REVIEW": "blog.review",
        "APPROVE": "blog.approve",
        "SCHEDULE": "blog.schedule",
        "PUBLISH": "blog.publish",
        "AGENT_RUNS": "blog.agent_runs",
        "SETTINGS": "blog.settings",
    }


def test_spec_matrix_covers_every_permission_and_role() -> None:
    assert set(SPEC_MATRIX) == set(Permission)
    assert set(ROLE_COLUMNS) == set(Role)
    assert all(len(row) == len(ROLE_COLUMNS) for row in SPEC_MATRIX.values())


def test_every_role_has_an_entry() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


@pytest.mark.parametrize("role", list(Role))
def test_role_permissions_are_exact(role: Role) -> None:
    granted = permissions_for(role)
    assert isinstance(granted, frozenset)
    assert granted == EXPECTED[role]
    assert ROLE_PERMISSIONS[role] == EXPECTED[role]


@pytest.mark.parametrize(("role", "permission", "granted"), MATRIX_CELLS)
def test_matrix_cell_matches_spec_table(role: Role, permission: Permission, granted: bool) -> None:
    assert (permission in permissions_for(role)) is granted


def test_roles_are_strictly_nested() -> None:
    chain = [permissions_for(role) for role in ROLE_COLUMNS]
    for lower, higher in pairwise(chain):
        assert lower < higher


def test_admin_has_every_permission() -> None:
    assert permissions_for(Role.ADMIN) == frozenset(Permission)


def test_only_admin_manages_settings_and_users() -> None:
    assert {role for role in Role if Permission.SETTINGS in permissions_for(role)} == {Role.ADMIN}


def test_role_read_from_the_database_as_plain_string_resolves() -> None:
    assert permissions_for(cast(Role, "reviewer")) == EXPECTED[Role.REVIEWER]


def test_unknown_role_gets_no_permissions() -> None:
    assert permissions_for(cast(Role, "superuser")) == frozenset()


def test_matrix_is_read_only() -> None:
    with pytest.raises(TypeError):
        cast(dict[Role, frozenset[Permission]], ROLE_PERMISSIONS)[Role.VIEWER] = frozenset(Permission)
```

- [ ] **Step 2: Run the RBAC test and watch it fail**

Run: `docker compose run --rm tools pytest tests/unit/test_rbac.py -q`

Expected: collection error, exit code 2, ending with:
```text
E   ModuleNotFoundError: No module named 'mdcopilot_blog.domain'
=========================== short test summary info ============================
ERROR tests/unit/test_rbac.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.04s
```

- [ ] **Step 3: Create the domain package**

Create `backend/src/mdcopilot_blog/domain/__init__.py`. It is a docstring only and has no re-exports: callers import from the submodules.

```python
"""Domain model: enums, RBAC matrix, status state machine and typed contracts.

Nothing in this package touches the database, the network or configuration.
"""
```

- [ ] **Step 4: Create the enums**

Create `backend/src/mdcopilot_blog/domain/enums.py`:

```python
"""Domain enumerations.

The values are the stored and wire representation: status columns are ``String(32)`` holding ``.value``,
and the frontend mirrors the ``Role`` and ``Permission`` values in ``src/features/auth/permissions.ts``.
Member names are UPPER_CASE for every enum; values keep the case shown here.
"""

from enum import StrEnum


class Role(StrEnum):
    """User roles, least to most privileged (ARCHITECTURE §17)."""

    VIEWER = "viewer"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    PUBLISHER = "publisher"
    ADMIN = "admin"


class Permission(StrEnum):
    """Permissions checked by the API (ARCHITECTURE §17)."""

    VIEW = "blog.view"
    GENERATE = "blog.generate"
    EDIT = "blog.edit"
    REVIEW = "blog.review"
    APPROVE = "blog.approve"
    SCHEDULE = "blog.schedule"
    PUBLISH = "blog.publish"
    AGENT_RUNS = "blog.agent_runs"
    SETTINGS = "blog.settings"


class RunKind(StrEnum):
    """How a run was started."""

    DAILY = "daily"
    MANUAL = "manual"


class RunStatus(StrEnum):
    """``blog_runs.status`` (ARCHITECTURE §6)."""

    QUEUED = "QUEUED"
    RESEARCHING = "RESEARCHING"
    TOPICS_READY = "TOPICS_READY"
    WAITING_FOR_TOPIC = "WAITING_FOR_TOPIC"
    PRODUCING = "PRODUCING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptStatus(StrEnum):
    """``blog_run_attempts.status``: one DBOS execution of a run."""

    ENQUEUED = "ENQUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(StrEnum):
    """``blog_agent_runs.status``: one execution of one workflow step."""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ArticleStatus(StrEnum):
    """``blog_articles.status`` (ARCHITECTURE §6, §6.1)."""

    DRAFTING = "DRAFTING"
    FACT_CHECKING = "FACT_CHECKING"
    CLINICAL_REVIEW = "CLINICAL_REVIEW"
    EDITORIAL_REVIEW = "EDITORIAL_REVIEW"
    SEO = "SEO"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    QUALITY_GATE_FAILED = "QUALITY_GATE_FAILED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    EXPORTED = "EXPORTED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    PUBLISH_FAILED = "PUBLISH_FAILED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class PublicationStatus(StrEnum):
    """``blog_publications.status`` (ARCHITECTURE §6, §14)."""

    PENDING = "PENDING"
    EXPORTED = "EXPORTED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class CallKind(StrEnum):
    """``blog_llm_calls.kind``."""

    AGENT = "agent"
    SEARCH = "search"
    EMBEDDING = "embedding"


class CallStatus(StrEnum):
    """``blog_llm_calls.status``."""

    OK = "ok"
    ERROR = "error"


class AgentName(StrEnum):
    """Route keys for the LLM gateway; ``HELLO`` is the Phase 1 mock agent."""

    SEARCH = "search"
    RESEARCH = "research"
    IDEATION = "ideation"
    DEEP_RESEARCH = "deep_research"
    WRITER = "writer"
    FACT_CHECK = "fact_check"
    CLINICAL = "clinical"
    EDITORIAL = "editorial"
    SEO = "seo"
    HELLO = "hello"
```

- [ ] **Step 5: Create the RBAC matrix**

Create `backend/src/mdcopilot_blog/domain/rbac.py`:

```python
"""Role to permission matrix (ARCHITECTURE §17). Deny by default."""

from collections.abc import Mapping
from types import MappingProxyType

from mdcopilot_blog.domain.enums import Permission, Role

_VIEWER: frozenset[Permission] = frozenset({Permission.VIEW})
_EDITOR: frozenset[Permission] = _VIEWER | {Permission.GENERATE, Permission.EDIT}
_REVIEWER: frozenset[Permission] = _EDITOR | {
    Permission.REVIEW,
    Permission.APPROVE,
    Permission.SCHEDULE,
    Permission.AGENT_RUNS,
}
_PUBLISHER: frozenset[Permission] = _REVIEWER | {Permission.PUBLISH}
_ADMIN: frozenset[Permission] = frozenset(Permission)

ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = MappingProxyType(
    {
        Role.VIEWER: _VIEWER,
        Role.EDITOR: _EDITOR,
        Role.REVIEWER: _REVIEWER,
        Role.PUBLISHER: _PUBLISHER,
        Role.ADMIN: _ADMIN,
    }
)


def permissions_for(role: Role) -> frozenset[Permission]:
    """Return the permissions granted to ``role``.

    A role string read from the database works too (``StrEnum`` members hash like their values).
    An unknown role gets no permissions.
    """
    return ROLE_PERMISSIONS.get(role, frozenset())
```

- [ ] **Step 6: Run the RBAC test and watch it pass**

Run: `docker compose run --rm tools pytest tests/unit/test_rbac.py -q`

Expected: `60 passed` (the timing varies).

- [ ] **Step 7: Write the failing state-machine test**

Create `backend/tests/unit/test_state_machine.py`. It writes the contract's transition table out by hand as `EXPECTED`, then:
- **Exact match.** It checks that the implementation equals it exactly, so no transition can be missing or extra.
- **Every allowed move.** It parametrizes over all 77 listed transitions (run 20, article 51, publication 6); each must be allowed. With the Step 0 edge, this is 78 (run 21).
- **Every other move.** It parametrizes over all 249 other state pairs (the full complement, not a sample); each must raise `InvalidTransition` with the right attributes. With the Step 0 edge, this is 248.
- **Named illegal moves.** 21 named illegal moves are checked against the exact message.
- **Same-state and terminal states.** All 30 same-state pairs must be no-ops. The terminal states (article PUBLISHED/REJECTED/SUPERSEDED, publication CONFIRMED/PUBLISHED) must have no exits, and they must be the only states with none.
- **Graph check.** No path from an agent-produced article state reaches SCHEDULED, EXPORTED, PUBLISHING, PUBLISH_FAILED or PUBLISHED without passing through APPROVED (ARCHITECTURE §6).
- **Input handling.** Unknown, wrong-case and wrong-entity states are rejected, and plain database strings are accepted.
- **Pickling.** The exception survives pickling.

```python
"""Status transition tables (ARCHITECTURE §6): every listed move is allowed, every other move raises."""

import pickle
from collections import deque
from enum import StrEnum
from typing import cast

import pytest

from mdcopilot_blog.domain.enums import ArticleStatus, PublicationStatus, RunStatus
from mdcopilot_blog.domain.state_machine import (
    TRANSITIONS,
    Entity,
    InvalidTransition,
    can_transition,
    require_transition,
)

# The contract table, written out independently of the implementation.
EXPECTED: dict[Entity, dict[str, set[str]]] = {
    Entity.RUN: {
        RunStatus.QUEUED: {RunStatus.RESEARCHING, RunStatus.PRODUCING, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.RESEARCHING: {RunStatus.TOPICS_READY, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.TOPICS_READY: {
            RunStatus.WAITING_FOR_TOPIC,
            RunStatus.PRODUCING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        },
        RunStatus.WAITING_FOR_TOPIC: {RunStatus.TOPICS_READY, RunStatus.PRODUCING, RunStatus.CANCELLED},
        RunStatus.PRODUCING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.SUCCEEDED: {RunStatus.QUEUED},
        RunStatus.FAILED: {RunStatus.QUEUED},
        RunStatus.CANCELLED: {RunStatus.QUEUED},
    },
    Entity.ARTICLE: {
        ArticleStatus.DRAFTING: {ArticleStatus.FACT_CHECKING, ArticleStatus.FAILED, ArticleStatus.SUPERSEDED},
        ArticleStatus.FACT_CHECKING: {
            ArticleStatus.CLINICAL_REVIEW,
            ArticleStatus.SEO,
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.CLINICAL_REVIEW: {
            ArticleStatus.EDITORIAL_REVIEW,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.EDITORIAL_REVIEW: {
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.SEO,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.SEO: {
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.READY_FOR_REVIEW: {
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.QUALITY_GATE_FAILED: {
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.APPROVED: {
            ArticleStatus.EXPORTED,
            ArticleStatus.PUBLISHING,
            ArticleStatus.SCHEDULED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.READY_FOR_REVIEW,
        },
        ArticleStatus.SCHEDULED: {
            ArticleStatus.EXPORTED,
            ArticleStatus.PUBLISHING,
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
        },
        ArticleStatus.EXPORTED: {ArticleStatus.PUBLISHED, ArticleStatus.REJECTED},
        ArticleStatus.PUBLISHING: {ArticleStatus.PUBLISHED, ArticleStatus.PUBLISH_FAILED},
        ArticleStatus.PUBLISH_FAILED: {ArticleStatus.PUBLISHING, ArticleStatus.APPROVED},
        ArticleStatus.FAILED: {ArticleStatus.DRAFTING},
        ArticleStatus.PUBLISHED: set(),
        ArticleStatus.REJECTED: set(),
        ArticleStatus.SUPERSEDED: set(),
    },
    Entity.PUBLICATION: {
        PublicationStatus.PENDING: {PublicationStatus.EXPORTED, PublicationStatus.IN_PROGRESS},
        PublicationStatus.EXPORTED: {PublicationStatus.CONFIRMED},
        PublicationStatus.CONFIRMED: set(),
        PublicationStatus.IN_PROGRESS: {PublicationStatus.PUBLISHED, PublicationStatus.FAILED},
        PublicationStatus.PUBLISHED: set(),
        PublicationStatus.FAILED: {PublicationStatus.IN_PROGRESS},
    },
}

STATUS_ENUMS: dict[Entity, type[StrEnum]] = {
    Entity.RUN: RunStatus,
    Entity.ARTICLE: ArticleStatus,
    Entity.PUBLICATION: PublicationStatus,
}

# States with no way out. Run end states are not here: they can be re-queued (restart).
TERMINAL: set[tuple[Entity, str]] = {
    (Entity.ARTICLE, ArticleStatus.PUBLISHED),
    (Entity.ARTICLE, ArticleStatus.REJECTED),
    (Entity.ARTICLE, ArticleStatus.SUPERSEDED),
    (Entity.PUBLICATION, PublicationStatus.CONFIRMED),
    (Entity.PUBLICATION, PublicationStatus.PUBLISHED),
}

# Article states an agent workflow can leave an article in (no human has approved it yet).
AGENT_STATES: set[str] = {
    ArticleStatus.DRAFTING,
    ArticleStatus.FACT_CHECKING,
    ArticleStatus.CLINICAL_REVIEW,
    ArticleStatus.EDITORIAL_REVIEW,
    ArticleStatus.SEO,
    ArticleStatus.READY_FOR_REVIEW,
    ArticleStatus.QUALITY_GATE_FAILED,
    ArticleStatus.FAILED,
}
AFTER_APPROVAL: set[str] = {
    ArticleStatus.SCHEDULED,
    ArticleStatus.EXPORTED,
    ArticleStatus.PUBLISHING,
    ArticleStatus.PUBLISH_FAILED,
    ArticleStatus.PUBLISHED,
}

ALLOWED = [
    pytest.param(entity, current, target, id=f"{entity}:{current}->{target}")
    for entity, table in EXPECTED.items()
    for current, targets in table.items()
    for target in sorted(targets)
]
ILLEGAL = [
    pytest.param(entity, current.value, target.value, id=f"{entity}:{current}->{target}")
    for entity, status_enum in STATUS_ENUMS.items()
    for current in status_enum
    for target in status_enum
    if current != target and target not in EXPECTED[entity][current]
]
SAME_STATE = [
    pytest.param(entity, state.value, id=f"{entity}:{state}")
    for entity, status_enum in STATUS_ENUMS.items()
    for state in status_enum
]
# Named examples of moves that must never happen; each is also covered by ILLEGAL.
REPRESENTATIVE_ILLEGAL = [
    pytest.param(Entity.RUN, RunStatus.QUEUED, RunStatus.SUCCEEDED, id="run-skips-all-work"),
    pytest.param(Entity.RUN, RunStatus.RESEARCHING, RunStatus.WAITING_FOR_TOPIC, id="run-waits-before-topics"),
    pytest.param(Entity.RUN, RunStatus.SUCCEEDED, RunStatus.CANCELLED, id="run-cancel-after-success"),
    pytest.param(Entity.RUN, RunStatus.FAILED, RunStatus.CANCELLED, id="run-cancel-after-failure"),
    pytest.param(Entity.RUN, RunStatus.CANCELLED, RunStatus.PRODUCING, id="run-resume-without-requeue"),
    pytest.param(Entity.RUN, RunStatus.WAITING_FOR_TOPIC, RunStatus.SUCCEEDED, id="run-succeeds-while-waiting"),
    pytest.param(Entity.ARTICLE, ArticleStatus.DRAFTING, ArticleStatus.APPROVED, id="article-draft-self-approves"),
    pytest.param(Entity.ARTICLE, ArticleStatus.SEO, ArticleStatus.PUBLISHING, id="article-seo-publishes"),
    pytest.param(
        Entity.ARTICLE, ArticleStatus.READY_FOR_REVIEW, ArticleStatus.EXPORTED, id="article-export-unapproved"
    ),
    pytest.param(
        Entity.ARTICLE, ArticleStatus.READY_FOR_REVIEW, ArticleStatus.PUBLISHED, id="article-publish-unapproved"
    ),
    pytest.param(
        Entity.ARTICLE, ArticleStatus.QUALITY_GATE_FAILED, ArticleStatus.SCHEDULED, id="article-schedule-unapproved"
    ),
    pytest.param(Entity.ARTICLE, ArticleStatus.EXPORTED, ArticleStatus.APPROVED, id="article-unexport"),
    pytest.param(Entity.ARTICLE, ArticleStatus.PUBLISHING, ArticleStatus.REJECTED, id="article-reject-mid-publish"),
    pytest.param(Entity.ARTICLE, ArticleStatus.PUBLISHED, ArticleStatus.DRAFTING, id="article-edit-after-publish"),
    pytest.param(Entity.ARTICLE, ArticleStatus.REJECTED, ArticleStatus.APPROVED, id="article-approve-rejected"),
    pytest.param(Entity.ARTICLE, ArticleStatus.SUPERSEDED, ArticleStatus.DRAFTING, id="article-revive-superseded"),
    pytest.param(Entity.ARTICLE, ArticleStatus.FAILED, ArticleStatus.READY_FOR_REVIEW, id="article-failed-to-review"),
    pytest.param(Entity.PUBLICATION, PublicationStatus.PENDING, PublicationStatus.PUBLISHED, id="pub-skip-in-progress"),
    pytest.param(Entity.PUBLICATION, PublicationStatus.EXPORTED, PublicationStatus.IN_PROGRESS, id="pub-switch-mode"),
    pytest.param(Entity.PUBLICATION, PublicationStatus.CONFIRMED, PublicationStatus.PENDING, id="pub-reopen"),
    pytest.param(
        Entity.PUBLICATION, PublicationStatus.PUBLISHED, PublicationStatus.FAILED, id="pub-fail-after-success"
    ),
]


def _as_sets(entity: Entity) -> dict[str, set[str]]:
    return {state: set(targets) for state, targets in TRANSITIONS[entity].items()}


def test_run_status_values() -> None:
    assert [status.value for status in RunStatus] == [
        "QUEUED",
        "RESEARCHING",
        "TOPICS_READY",
        "WAITING_FOR_TOPIC",
        "PRODUCING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]


def test_article_status_values() -> None:
    assert [status.value for status in ArticleStatus] == [
        "DRAFTING",
        "FACT_CHECKING",
        "CLINICAL_REVIEW",
        "EDITORIAL_REVIEW",
        "SEO",
        "READY_FOR_REVIEW",
        "QUALITY_GATE_FAILED",
        "APPROVED",
        "SCHEDULED",
        "EXPORTED",
        "PUBLISHING",
        "PUBLISHED",
        "PUBLISH_FAILED",
        "REJECTED",
        "FAILED",
        "SUPERSEDED",
    ]


def test_publication_status_values() -> None:
    assert [status.value for status in PublicationStatus] == [
        "PENDING",
        "EXPORTED",
        "CONFIRMED",
        "IN_PROGRESS",
        "PUBLISHED",
        "FAILED",
    ]


def test_entity_values() -> None:
    assert [entity.value for entity in Entity] == ["run", "article", "publication"]


def test_expected_table_is_complete_and_well_formed() -> None:
    assert set(EXPECTED) == set(Entity)
    for entity, status_enum in STATUS_ENUMS.items():
        members = {state.value for state in status_enum}
        assert set(EXPECTED[entity]) == members
        assert all(targets <= members for targets in EXPECTED[entity].values())
    edge_counts = {entity: sum(len(targets) for targets in table.values()) for entity, table in EXPECTED.items()}
    assert edge_counts == {Entity.RUN: 20, Entity.ARTICLE: 51, Entity.PUBLICATION: 6}
    assert (len(ALLOWED), len(ILLEGAL), len(SAME_STATE)) == (77, 249, 30)


@pytest.mark.parametrize("entity", list(Entity))
def test_table_matches_contract_exactly(entity: Entity) -> None:
    assert _as_sets(entity) == EXPECTED[entity]


@pytest.mark.parametrize(("entity", "current", "target"), ALLOWED)
def test_listed_transition_is_allowed(entity: Entity, current: str, target: str) -> None:
    assert can_transition(entity, current, target) is True
    require_transition(entity, current, target)


@pytest.mark.parametrize(("entity", "current", "target"), ILLEGAL)
def test_unlisted_transition_is_rejected(entity: Entity, current: str, target: str) -> None:
    assert can_transition(entity, current, target) is False
    with pytest.raises(InvalidTransition) as caught:
        require_transition(entity, current, target)
    assert (caught.value.entity, caught.value.current, caught.value.target) == (entity, current, target)


@pytest.mark.parametrize(("entity", "current", "target"), REPRESENTATIVE_ILLEGAL)
def test_representative_illegal_transition_raises(entity: Entity, current: str, target: str) -> None:
    assert target not in EXPECTED[entity][current]
    with pytest.raises(InvalidTransition, match=f"^illegal {entity} transition: {current} -> {target}$"):
        require_transition(entity, current, target)


@pytest.mark.parametrize(("entity", "state"), SAME_STATE)
def test_same_state_is_a_noop(entity: Entity, state: str) -> None:
    assert can_transition(entity, state, state) is True
    require_transition(entity, state, state)


@pytest.mark.parametrize(("entity", "state"), sorted(TERMINAL))
def test_terminal_state_has_no_exits(entity: Entity, state: str) -> None:
    assert TRANSITIONS[entity][state] == frozenset()
    for target in STATUS_ENUMS[entity]:
        if target != state:
            assert can_transition(entity, state, target) is False


def test_terminal_states_are_exactly_the_listed_ones() -> None:
    no_exit = {(entity, state) for entity in Entity for state, targets in TRANSITIONS[entity].items() if not targets}
    assert no_exit == TERMINAL


@pytest.mark.parametrize("state", [RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED])
def test_finished_run_can_only_be_requeued(state: RunStatus) -> None:
    assert TRANSITIONS[Entity.RUN][state] == frozenset({RunStatus.QUEUED})


def test_every_publish_path_goes_through_human_approval() -> None:
    graph = _as_sets(Entity.ARTICLE)
    reachable: set[str] = set()
    queue = deque(AGENT_STATES)
    while queue:
        state = queue.popleft()
        for target in graph[state]:
            if target != ArticleStatus.APPROVED and target not in reachable:
                reachable.add(target)
                queue.append(target)
    assert reachable.isdisjoint(AFTER_APPROVAL)


@pytest.mark.parametrize(
    ("entity", "current", "target"),
    [
        pytest.param(Entity.RUN, "BOGUS", RunStatus.QUEUED, id="unknown-current"),
        pytest.param(Entity.RUN, RunStatus.QUEUED, "BOGUS", id="unknown-target"),
        pytest.param(Entity.RUN, "BOGUS", "BOGUS", id="unknown-same-state"),
        pytest.param(Entity.RUN, "queued", "researching", id="wrong-case"),
        pytest.param(Entity.PUBLICATION, ArticleStatus.DRAFTING, ArticleStatus.DRAFTING, id="other-entity-state"),
        pytest.param(Entity.RUN, ArticleStatus.DRAFTING, RunStatus.QUEUED, id="article-state-on-run"),
    ],
)
def test_unknown_states_are_rejected(entity: Entity, current: str, target: str) -> None:
    assert can_transition(entity, current, target) is False
    with pytest.raises(InvalidTransition):
        require_transition(entity, current, target)


def test_plain_strings_from_the_database_are_accepted() -> None:
    assert can_transition(Entity.RUN, "QUEUED", "RESEARCHING") is True
    assert can_transition(Entity.ARTICLE, "APPROVED", "EXPORTED") is True
    assert can_transition(Entity.PUBLICATION, "IN_PROGRESS", "PUBLISHED") is True


def test_invalid_transition_details() -> None:
    with pytest.raises(InvalidTransition) as caught:
        require_transition(Entity.RUN, RunStatus.SUCCEEDED, RunStatus.CANCELLED)
    error = caught.value
    assert isinstance(error, ValueError)
    assert error.entity is Entity.RUN
    assert error.current == "SUCCEEDED"
    assert error.target == "CANCELLED"
    assert type(error.current) is str
    assert str(error) == "illegal run transition: SUCCEEDED -> CANCELLED"


def test_invalid_transition_survives_pickling() -> None:
    # DBOS stores a failed step's exception with its default (pickle-based) serializer.
    error = InvalidTransition(Entity.ARTICLE, "PUBLISHED", "DRAFTING")
    restored = pickle.loads(pickle.dumps(error))
    assert isinstance(restored, InvalidTransition)
    assert (restored.entity, restored.current, restored.target) == (Entity.ARTICLE, "PUBLISHED", "DRAFTING")
    assert str(restored) == str(error)


def test_tables_are_read_only() -> None:
    with pytest.raises(TypeError):
        cast(dict[Entity, object], TRANSITIONS)[Entity.RUN] = {}
    with pytest.raises(TypeError):
        cast(dict[str, frozenset[str]], TRANSITIONS[Entity.RUN])[RunStatus.QUEUED] = frozenset()
```

- [ ] **Step 8: Run the state-machine test and watch it fail**

Run: `docker compose run --rm tools pytest tests/unit/test_state_machine.py -q`

Expected: collection error, exit code 2, ending with:
```text
E   ModuleNotFoundError: No module named 'mdcopilot_blog.domain.state_machine'
=========================== short test summary info ============================
ERROR tests/unit/test_state_machine.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.06s
```

- [ ] **Step 9: Create the state machine**

Create `backend/src/mdcopilot_blog/domain/state_machine.py`.

Do not add `# noqa: N818` to the exception class. ruff 0.16.8's default rule set does not enable N818, so the comment would trigger RUF100 (unused `noqa`).

```python
"""Status transition tables for runs, articles and publications (ARCHITECTURE §6).

The API and the workflows both call ``require_transition`` before writing a status.
Moving to the state an entity is already in is always allowed and changes nothing, so a retried
or forked step can repeat its status write safely.
"""

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType

from mdcopilot_blog.domain.enums import ArticleStatus, PublicationStatus, RunStatus


class Entity(StrEnum):
    """Things that have a status."""

    RUN = "run"
    ARTICLE = "article"
    PUBLICATION = "publication"


class InvalidTransition(ValueError):
    """Raised when a status change is not in the transition table."""

    def __init__(self, entity: Entity, current: str, target: str) -> None:
        # Keep every constructor argument in ``args`` so the exception pickles (DBOS stores step errors).
        super().__init__(entity, current, target)
        self.entity = entity
        self.current = current
        self.target = target

    def __str__(self) -> str:
        return f"illegal {self.entity} transition: {self.current} -> {self.target}"


def _table(edges: Mapping[str, Iterable[str]]) -> Mapping[str, frozenset[str]]:
    return MappingProxyType({state: frozenset(targets) for state, targets in edges.items()})


_RUN = _table(
    {
        RunStatus.QUEUED: {RunStatus.RESEARCHING, RunStatus.PRODUCING, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.RESEARCHING: {RunStatus.TOPICS_READY, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.TOPICS_READY: {
            RunStatus.WAITING_FOR_TOPIC,
            RunStatus.PRODUCING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        },
        RunStatus.WAITING_FOR_TOPIC: {RunStatus.TOPICS_READY, RunStatus.PRODUCING, RunStatus.CANCELLED},
        RunStatus.PRODUCING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED},
        # Finished runs can only be queued again (restart / retry creates a new attempt).
        RunStatus.SUCCEEDED: {RunStatus.QUEUED},
        RunStatus.FAILED: {RunStatus.QUEUED},
        RunStatus.CANCELLED: {RunStatus.QUEUED},
    }
)

_ARTICLE = _table(
    {
        ArticleStatus.DRAFTING: {ArticleStatus.FACT_CHECKING, ArticleStatus.FAILED, ArticleStatus.SUPERSEDED},
        ArticleStatus.FACT_CHECKING: {
            ArticleStatus.CLINICAL_REVIEW,
            ArticleStatus.SEO,
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.CLINICAL_REVIEW: {
            ArticleStatus.EDITORIAL_REVIEW,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.EDITORIAL_REVIEW: {
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.SEO,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.SEO: {
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.READY_FOR_REVIEW: {
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.QUALITY_GATE_FAILED: {
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.SUPERSEDED,
        },
        # Only a human approval leads to scheduling, export or publishing.
        ArticleStatus.APPROVED: {
            ArticleStatus.EXPORTED,
            ArticleStatus.PUBLISHING,
            ArticleStatus.SCHEDULED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.READY_FOR_REVIEW,
        },
        ArticleStatus.SCHEDULED: {
            ArticleStatus.EXPORTED,
            ArticleStatus.PUBLISHING,
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
        },
        ArticleStatus.EXPORTED: {ArticleStatus.PUBLISHED, ArticleStatus.REJECTED},
        ArticleStatus.PUBLISHING: {ArticleStatus.PUBLISHED, ArticleStatus.PUBLISH_FAILED},
        ArticleStatus.PUBLISH_FAILED: {ArticleStatus.PUBLISHING, ArticleStatus.APPROVED},
        ArticleStatus.FAILED: {ArticleStatus.DRAFTING},
        # Terminal.
        ArticleStatus.PUBLISHED: set(),
        ArticleStatus.REJECTED: set(),
        ArticleStatus.SUPERSEDED: set(),
    }
)

_PUBLICATION = _table(
    {
        PublicationStatus.PENDING: {PublicationStatus.EXPORTED, PublicationStatus.IN_PROGRESS},
        PublicationStatus.EXPORTED: {PublicationStatus.CONFIRMED},
        PublicationStatus.IN_PROGRESS: {PublicationStatus.PUBLISHED, PublicationStatus.FAILED},
        PublicationStatus.FAILED: {PublicationStatus.IN_PROGRESS},
        # Terminal.
        PublicationStatus.CONFIRMED: set(),
        PublicationStatus.PUBLISHED: set(),
    }
)

TRANSITIONS: Mapping[Entity, Mapping[str, frozenset[str]]] = MappingProxyType(
    {Entity.RUN: _RUN, Entity.ARTICLE: _ARTICLE, Entity.PUBLICATION: _PUBLICATION}
)


def can_transition(entity: Entity, current: str, target: str) -> bool:
    """Return True if ``entity`` may move from ``current`` to ``target``.

    Same-state is True (a no-op) for any known state. Unknown states are never allowed.
    """
    table = TRANSITIONS[Entity(entity)]
    if current not in table or target not in table:
        return False
    return current == target or target in table[current]


def require_transition(entity: Entity, current: str, target: str) -> None:
    """Raise ``InvalidTransition`` unless ``can_transition`` allows the move."""
    if not can_transition(entity, current, target):
        raise InvalidTransition(Entity(entity), str(current), str(target))
```

- [ ] **Step 10: Run the state-machine test and watch it pass**

Run: `docker compose run --rm tools pytest tests/unit/test_state_machine.py -q`

Expected: `405 passed`.

- [ ] **Step 11: Write the failing contracts test**

Create `backend/tests/unit/test_contracts.py`. It has one builder per contract that returns a valid snake_case payload, and a hand-written list of every field from ARCHITECTURE §12 and the contract. It checks that:
- **Coverage.**
  - Every model in `contracts.py` has a builder and a field list, so a new model cannot go untested.
  - Each model has exactly the listed fields, all required.
- **Parsing.**
  - Snake_case input parses, and so do hand-written camelCase and mixed input.
  - A camelCase JSON round trip returns an equal model.
  - Values come back as the right types (enums, datetimes).
- **Serialisation.**
  - Every dump is camelCase at every depth (explicit key sets for the main models).
  - The keys of `score_breakdown` are left alone.
  - The JSON schema is camelCase with every field required.
- **Strict input.**
  - Unknown fields are rejected at the top level and when nested.
  - Nullable fields accept `null` but must be present.
  - Bad enum, literal, datetime and integer values are rejected.
  - Error locations name the key the client sent.
- **0..1 bounds.**
  - All 15 scores and confidences accept 0, 0.5 and 1.
  - They reject -0.01 and 1.01, whether the payload is snake_case or camelCase.
  - No `float` field is left unbounded.
- **Wire values.** The contract enums and the shared enums (`RunKind`, `AttemptStatus`, `StepStatus`, `CallKind`, `CallStatus`, `AgentName`) have exactly the contract's values.

```python
"""Typed contracts (ARCHITECTURE §12): every field present, camelCase on the wire, strict input, bounded scores."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from mdcopilot_blog.domain import contracts as c
from mdcopilot_blog.domain.enums import (
    AgentName,
    ArticleStatus,
    AttemptStatus,
    CallKind,
    CallStatus,
    RunKind,
    RunStatus,
    StepStatus,
)

Builder = Callable[[], dict[str, Any]]

NOW = "2026-09-17T07:00:00Z"


# --- valid snake_case payloads, one builder per contract -------------------------------------------------------


def research_source() -> dict[str, Any]:
    return {
        "id": "src_1",
        "title": "FDA updates its list of AI-enabled medical devices",
        "url": "https://www.fda.gov/medical-devices/ai-enabled-devices?utm_source=feed",
        "canonical_url": "https://www.fda.gov/medical-devices/ai-enabled-devices",
        "publisher": "U.S. Food and Drug Administration",
        "domain": "fda.gov",
        "published_at": "2026-09-15T00:00:00Z",
        "date_source": "feed",
        "retrieved_at": NOW,
        "source_type": "government",
        "tier": 1,
        "access_mode": "full_text",
        "relevance_score": 0.9,
    }


def research_finding() -> dict[str, Any]:
    return {
        "id": "fnd_1",
        "claim": "The FDA list now includes more than 1,200 AI-enabled devices.",
        "evidence": "The September update lists 1,247 devices.",
        "source_ids": ["src_1"],
        "confidence": 0.8,
        "category": "regulation",
        "claim_type": "FACT",
        "importance": "high",
    }


def news_ref() -> dict[str, Any]:
    return {"title": "FDA list update", "url": "https://www.fda.gov/news/1", "published_at": NOW}


def score_item() -> dict[str, Any]:
    return {"weight": 0.25, "score": 1.0, "justification": "Primary source published within 48 hours."}


def novelty_neighbour() -> dict[str, Any]:
    return {"kind": "article", "ref_id": "art_9", "title": "What the FDA device list tells us", "similarity": 0.42}


def novelty_result() -> dict[str, Any]:
    return {"decision": "PASS", "max_similarity": 0.42, "neighbours": [novelty_neighbour()]}


def topic_candidate() -> dict[str, Any]:
    return {
        "topic_id": "top_1",
        "title": "The FDA's AI device list is a workload map",
        "hook": "Radiology holds most of the clearances.",
        "why_now": "The list was updated this week.",
        "relevant_news": [news_ref()],
        "mdcopilot_connection": "Specialist leverage on the imaging bottleneck.",
        "target_audience": "Hospital CMIOs",
        "pillar": "A",
        "novelty_score": 0.58,
        "evidence_score": 0.9,
        "business_relevance": 0.75,
        "editorial_potential": 0.5,
        "timeliness_score": 1.0,
        "audience_relevance": 0.75,
        "total_score": 0.8,
        "score_breakdown": {"timeliness": score_item(), "novelty": score_item()},
        "novelty": novelty_result(),
        "sources": ["src_1"],
        "status": "PROPOSED",
    }


def title_options() -> dict[str, Any]:
    return {
        "provocative": "Most AI clearances point at one specialty",
        "operational": "Reading the FDA AI device list",
        "visionary": "Where specialist leverage goes next",
    }


def internal_link() -> dict[str, Any]:
    return {"title": "Specialist leverage", "url": "https://www.mdcopilot.health/blog/specialist-leverage"}


def seo_metadata() -> dict[str, Any]:
    return {
        "seo_title": "Reading the FDA AI device list",
        "meta_description": "What the latest FDA list of AI-enabled devices says about where specialist time goes.",
        "slug": "fda-ai-device-list",
        "primary_keyword": "FDA AI devices",
        "secondary_keywords": ["AI-enabled medical devices", "radiology AI"],
        "og_title": "Reading the FDA AI device list",
        "og_description": "Where the clearances cluster, and why.",
        "tags": ["regulation", "radiology"],
        "category": "Healthcare AI",
        "internal_link_suggestions": [internal_link()],
        "external_references": ["src_1"],
    }


def social_copy() -> dict[str, Any]:
    return {
        "linkedin": "The FDA list is a workload map.",
        "x_post": "Most AI clearances point at one specialty.",
        "newsletter_teaser": "This week: reading the FDA list.",
    }


def blog_source() -> dict[str, Any]:
    return {
        "marker": "S1",
        "source_id": "src_1",
        "title": "FDA updates its list of AI-enabled medical devices",
        "url": "https://www.fda.gov/medical-devices/ai-enabled-devices",
        "publisher": "U.S. Food and Drug Administration",
        "published_at": "2026-09-15T00:00:00Z",
    }


def claim_check() -> dict[str, Any]:
    return {
        "claim": "The list includes 1,247 devices.",
        "kind": "statistic",
        "importance": "high",
        "section_key": "evidence",
        "sentence_index": 2,
        "span": "1,247 devices",
        "citation_markers": ["S1"],
        "source_id": "src_1",
        "verification_status": "SUPPORTED",
        "confidence": 0.95,
        "recommended_revision": None,
    }


def fact_check_result() -> dict[str, Any]:
    return {"verdict": "PASS", "independent_check": True, "claims": [claim_check()]}


def clinical_flag() -> dict[str, Any]:
    return {
        "code": "autonomous_ai_claim",
        "severity": "WARNING",
        "message": "Implies the model reads scans without a radiologist.",
        "location": "core_argument:3",
    }


def clinical_review() -> dict[str, Any]:
    return {"flags": [clinical_flag()], "summary": "No blocking issues."}


def change() -> dict[str, Any]:
    return {"id": "chg_1", "description": "Tighten the opening.", "location": "introduction:0"}


def editorial_review() -> dict[str, Any]:
    return {
        "editorial_score": 0.82,
        "strengths": ["Clear thesis"],
        "weaknesses": ["Long opening"],
        "required_changes": [change()],
        "optional_changes": [],
        "final_recommendation": "Revise, then approve.",
    }


def gate_result() -> dict[str, Any]:
    return {"gate": "word_count", "passed": True, "severity": "blocking", "details": "1012 words"}


def gate_report() -> dict[str, Any]:
    return {"passed": True, "results": [gate_result()]}


def generated_blog_post() -> dict[str, Any]:
    return {
        "id": "art_1",
        "topic_id": "top_1",
        "title_options": title_options(),
        "selected_title": "Reading the FDA AI device list",
        "slug": "fda-ai-device-list",
        "content_markdown": "Radiology holds most of the clearances [S1].\n\n## Context\n\nText.",
        "excerpt": "Where the clearances cluster, and why.",
        "pull_quote": "The list is a workload map.",
        "cta": "See how MDCopilot supports specialists.",
        "category": "Healthcare AI",
        "tags": ["regulation"],
        "seo": seo_metadata(),
        "social": social_copy(),
        "sources": [blog_source()],
        "research_summary": "Seven dated sources, two Tier-1.",
        "fact_check": fact_check_result(),
        "clinical_review": clinical_review(),
        "editorial_review": editorial_review(),
        "quality_gates": gate_report(),
        "novelty": novelty_result(),
        "status": "READY_FOR_REVIEW",
        "pipeline_status": "SUCCEEDED",
        "version_no": 2,
        "created_at": NOW,
        "updated_at": NOW,
    }


BUILDERS: dict[type[c.Contract], Builder] = {
    c.ResearchSource: research_source,
    c.ResearchFinding: research_finding,
    c.NewsRef: news_ref,
    c.ScoreItem: score_item,
    c.NoveltyNeighbour: novelty_neighbour,
    c.NoveltyResult: novelty_result,
    c.TopicCandidate: topic_candidate,
    c.TitleOptions: title_options,
    c.InternalLink: internal_link,
    c.SEOMetadata: seo_metadata,
    c.SocialCopy: social_copy,
    c.BlogSource: blog_source,
    c.ClaimCheck: claim_check,
    c.FactCheckResult: fact_check_result,
    c.ClinicalFlag: clinical_flag,
    c.ClinicalReview: clinical_review,
    c.Change: change,
    c.EditorialReview: editorial_review,
    c.GateResult: gate_result,
    c.GateReport: gate_report,
    c.GeneratedBlogPost: generated_blog_post,
}

# Field names from ARCHITECTURE §12 and the Phase 1 contract, written out by hand.
EXPECTED_FIELDS: dict[type[c.Contract], set[str]] = {
    c.ResearchSource: {
        "id",
        "title",
        "url",
        "canonical_url",
        "publisher",
        "domain",
        "published_at",
        "date_source",
        "retrieved_at",
        "source_type",
        "tier",
        "access_mode",
        "relevance_score",
    },
    c.ResearchFinding: {
        "id",
        "claim",
        "evidence",
        "source_ids",
        "confidence",
        "category",
        "claim_type",
        "importance",
    },
    c.NewsRef: {"title", "url", "published_at"},
    c.ScoreItem: {"weight", "score", "justification"},
    c.NoveltyNeighbour: {"kind", "ref_id", "title", "similarity"},
    c.NoveltyResult: {"decision", "max_similarity", "neighbours"},
    c.TopicCandidate: {
        "topic_id",
        "title",
        "hook",
        "why_now",
        "relevant_news",
        "mdcopilot_connection",
        "target_audience",
        "pillar",
        "novelty_score",
        "evidence_score",
        "business_relevance",
        "editorial_potential",
        "timeliness_score",
        "audience_relevance",
        "total_score",
        "score_breakdown",
        "novelty",
        "sources",
        "status",
    },
    c.TitleOptions: {"provocative", "operational", "visionary"},
    c.InternalLink: {"title", "url"},
    c.SEOMetadata: {
        "seo_title",
        "meta_description",
        "slug",
        "primary_keyword",
        "secondary_keywords",
        "og_title",
        "og_description",
        "tags",
        "category",
        "internal_link_suggestions",
        "external_references",
    },
    c.SocialCopy: {"linkedin", "x_post", "newsletter_teaser"},
    c.BlogSource: {"marker", "source_id", "title", "url", "publisher", "published_at"},
    c.ClaimCheck: {
        "claim",
        "kind",
        "importance",
        "section_key",
        "sentence_index",
        "span",
        "citation_markers",
        "source_id",
        "verification_status",
        "confidence",
        "recommended_revision",
    },
    c.FactCheckResult: {"verdict", "independent_check", "claims"},
    c.ClinicalFlag: {"code", "severity", "message", "location"},
    c.ClinicalReview: {"flags", "summary"},
    c.Change: {"id", "description", "location"},
    c.EditorialReview: {
        "editorial_score",
        "strengths",
        "weaknesses",
        "required_changes",
        "optional_changes",
        "final_recommendation",
    },
    c.GateResult: {"gate", "passed", "severity", "details"},
    c.GateReport: {"passed", "results"},
    c.GeneratedBlogPost: {
        "id",
        "topic_id",
        "title_options",
        "selected_title",
        "slug",
        "content_markdown",
        "excerpt",
        "pull_quote",
        "cta",
        "category",
        "tags",
        "seo",
        "social",
        "sources",
        "research_summary",
        "fact_check",
        "clinical_review",
        "editorial_review",
        "quality_gates",
        "novelty",
        "status",
        "pipeline_status",
        "version_no",
        "created_at",
        "updated_at",
    },
}

# Every score or confidence in the contracts.
BOUNDED: list[tuple[type[c.Contract], str]] = [
    (c.ResearchSource, "relevance_score"),
    (c.ResearchFinding, "confidence"),
    (c.ScoreItem, "weight"),
    (c.ScoreItem, "score"),
    (c.NoveltyNeighbour, "similarity"),
    (c.NoveltyResult, "max_similarity"),
    (c.TopicCandidate, "novelty_score"),
    (c.TopicCandidate, "evidence_score"),
    (c.TopicCandidate, "business_relevance"),
    (c.TopicCandidate, "editorial_potential"),
    (c.TopicCandidate, "timeliness_score"),
    (c.TopicCandidate, "audience_relevance"),
    (c.TopicCandidate, "total_score"),
    (c.ClaimCheck, "confidence"),
    (c.EditorialReview, "editorial_score"),
]

MODELS = [pytest.param(model, id=model.__name__) for model in BUILDERS]


def _param(model: type[c.Contract], field: str, value: object) -> Any:
    return pytest.param(model, field, value, id=f"{model.__name__}.{field}={value!r}")


def _keys_with_underscores(value: object, path: str = "") -> list[str]:
    """Return every JSON object key containing "_" (dict-valued data such as scoreBreakdown is skipped)."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if "_" in key:
                found.append(f"{path}.{key}")
            if key != "scoreBreakdown":
                found.extend(_keys_with_underscores(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_keys_with_underscores(item, f"{path}[{index}]"))
    return found


# --- enums -----------------------------------------------------------------------------------------------------


def test_contract_enum_values() -> None:
    assert [v.value for v in c.SourceType] == [
        "government",
        "journal",
        "preprint",
        "trade_press",
        "company_announcement",
        "blog",
        "social",
        "other",
    ]
    assert [v.value for v in c.ClaimType] == ["FACT", "ANALYSIS", "OPINION", "PREDICTION", "MARKETING_CLAIM"]
    assert [v.value for v in c.VerificationStatus] == [
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "UNSUPPORTED",
        "OUTDATED",
        "MISLEADING",
        "OPINION",
    ]
    assert [v.value for v in c.ClaimKind] == [
        "statistic",
        "regulatory",
        "trial_result",
        "workforce",
        "company_announcement",
        "quote_or_attribution",
        "anecdote_or_vignette",
        "general_fact",
        "opinion",
    ]
    assert [v.value for v in c.NoveltyDecision] == ["PASS", "WARN", "REJECT_TOPIC"]
    assert [v.value for v in c.PillarKey] == ["A", "B", "C", "D", "E", "NARRATIVE"]


def test_shared_enum_wire_values() -> None:
    assert [v.value for v in RunKind] == ["daily", "manual"]
    assert [v.value for v in AttemptStatus] == ["ENQUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    assert [v.value for v in StepStatus] == ["RUNNING", "SUCCEEDED", "FAILED"]
    assert [v.value for v in CallKind] == ["agent", "search", "embedding"]
    assert [v.value for v in CallStatus] == ["ok", "error"]
    assert {v.name: v.value for v in AgentName} == {
        "SEARCH": "search",
        "RESEARCH": "research",
        "IDEATION": "ideation",
        "DEEP_RESEARCH": "deep_research",
        "WRITER": "writer",
        "FACT_CHECK": "fact_check",
        "CLINICAL": "clinical",
        "EDITORIAL": "editorial",
        "SEO": "seo",
        "HELLO": "hello",
    }


# --- field coverage --------------------------------------------------------------------------------------------


def test_every_contract_model_is_covered_by_these_tests() -> None:
    defined = {
        obj
        for obj in vars(c).values()
        if isinstance(obj, type) and issubclass(obj, c.Contract) and obj is not c.Contract
    }
    assert defined == set(BUILDERS) == set(EXPECTED_FIELDS)


@pytest.mark.parametrize("model", MODELS)
def test_model_has_exactly_the_specified_fields(model: type[c.Contract]) -> None:
    assert set(model.model_fields) == EXPECTED_FIELDS[model]


@pytest.mark.parametrize("model", MODELS)
def test_every_field_is_required(model: type[c.Contract]) -> None:
    # §12 gives no defaults: nullable fields must still be sent explicitly (as null).
    assert all(info.is_required() for info in model.model_fields.values())


# --- parsing ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("model", MODELS)
def test_parses_snake_case(model: type[c.Contract]) -> None:
    instance = model.model_validate(BUILDERS[model]())
    assert set(type(instance).model_fields) == EXPECTED_FIELDS[model]


@pytest.mark.parametrize("model", MODELS)
def test_camel_case_round_trip(model: type[c.Contract]) -> None:
    original = model.model_validate(BUILDERS[model]())
    wire = original.model_dump(mode="json")
    assert model.model_validate(wire) == original
    assert model.model_validate_json(original.model_dump_json()) == original


def test_parses_hand_written_camel_case_payload() -> None:
    seo = c.SEOMetadata.model_validate(
        {
            "seoTitle": "Reading the FDA AI device list",
            "metaDescription": "What the latest FDA list says.",
            "slug": "fda-ai-device-list",
            "primaryKeyword": "FDA AI devices",
            "secondaryKeywords": ["radiology AI"],
            "ogTitle": "Reading the list",
            "ogDescription": "Where the clearances cluster.",
            "tags": ["regulation"],
            "category": "Healthcare AI",
            "internalLinkSuggestions": [{"title": "Leverage", "url": "https://www.mdcopilot.health/blog/x"}],
            "externalReferences": ["src_1"],
        }
    )
    assert seo.seo_title == "Reading the FDA AI device list"
    assert seo.internal_link_suggestions == [
        c.InternalLink(title="Leverage", url="https://www.mdcopilot.health/blog/x")
    ]
    social = c.SocialCopy.model_validate({"linkedin": "a", "xPost": "b", "newsletterTeaser": "c"})
    assert (social.x_post, social.newsletter_teaser) == ("b", "c")


def test_parses_mixed_case_payload() -> None:
    neighbour = c.NoveltyNeighbour.model_validate({"kind": "external", "refId": "ext_1", "title": "t", "similarity": 0})
    assert neighbour.ref_id == "ext_1"
    source = c.BlogSource.model_validate(
        {"marker": "S2", "sourceId": "src_2", "title": "t", "url": "u", "publisher": "p", "published_at": None}
    )
    assert (source.source_id, source.published_at) == ("src_2", None)


def test_python_constructor_uses_field_names() -> None:
    item = c.ScoreItem(weight=0.1, score=0.2, justification="because")
    assert item.model_dump() == {"weight": 0.1, "score": 0.2, "justification": "because"}


def test_values_are_typed_after_parsing() -> None:
    post = c.GeneratedBlogPost.model_validate(generated_blog_post())
    assert post.status is ArticleStatus.READY_FOR_REVIEW
    assert post.pipeline_status is RunStatus.SUCCEEDED
    assert post.created_at == datetime(2026, 9, 17, 7, 0, tzinfo=UTC)
    assert post.fact_check.claims[0].kind is c.ClaimKind.STATISTIC
    assert post.fact_check.claims[0].verification_status is c.VerificationStatus.SUPPORTED
    assert post.novelty.decision is c.NoveltyDecision.PASS
    candidate = c.TopicCandidate.model_validate(topic_candidate())
    assert candidate.pillar is c.PillarKey.A
    assert candidate.score_breakdown["timeliness"].weight == 0.25
    source = c.ResearchSource.model_validate(research_source())
    assert source.source_type is c.SourceType.GOVERNMENT
    assert c.ResearchFinding.model_validate(research_finding()).claim_type is c.ClaimType.FACT


# --- serialisation ---------------------------------------------------------------------------------------------


def test_generated_blog_post_serialises_camel_case() -> None:
    wire = c.GeneratedBlogPost.model_validate(generated_blog_post()).model_dump(mode="json")
    assert set(wire) == {
        "id",
        "topicId",
        "titleOptions",
        "selectedTitle",
        "slug",
        "contentMarkdown",
        "excerpt",
        "pullQuote",
        "cta",
        "category",
        "tags",
        "seo",
        "social",
        "sources",
        "researchSummary",
        "factCheck",
        "clinicalReview",
        "editorialReview",
        "qualityGates",
        "novelty",
        "status",
        "pipelineStatus",
        "versionNo",
        "createdAt",
        "updatedAt",
    }
    assert set(wire["seo"]) == {
        "seoTitle",
        "metaDescription",
        "slug",
        "primaryKeyword",
        "secondaryKeywords",
        "ogTitle",
        "ogDescription",
        "tags",
        "category",
        "internalLinkSuggestions",
        "externalReferences",
    }
    assert set(wire["social"]) == {"linkedin", "xPost", "newsletterTeaser"}
    assert set(wire["sources"][0]) == {"marker", "sourceId", "title", "url", "publisher", "publishedAt"}
    assert set(wire["factCheck"]) == {"verdict", "independentCheck", "claims"}
    assert set(wire["factCheck"]["claims"][0]) == {
        "claim",
        "kind",
        "importance",
        "sectionKey",
        "sentenceIndex",
        "span",
        "citationMarkers",
        "sourceId",
        "verificationStatus",
        "confidence",
        "recommendedRevision",
    }
    assert set(wire["editorialReview"]) == {
        "editorialScore",
        "strengths",
        "weaknesses",
        "requiredChanges",
        "optionalChanges",
        "finalRecommendation",
    }
    assert set(wire["novelty"]) == {"decision", "maxSimilarity", "neighbours"}
    assert set(wire["novelty"]["neighbours"][0]) == {"kind", "refId", "title", "similarity"}
    assert wire["status"] == "READY_FOR_REVIEW"
    assert wire["pipelineStatus"] == "SUCCEEDED"
    assert wire["createdAt"] == "2026-09-17T07:00:00Z"
    assert wire["factCheck"]["claims"][0]["recommendedRevision"] is None


def test_research_and_topic_contracts_serialise_camel_case() -> None:
    source = c.ResearchSource.model_validate(research_source()).model_dump(mode="json")
    assert set(source) == {
        "id",
        "title",
        "url",
        "canonicalUrl",
        "publisher",
        "domain",
        "publishedAt",
        "dateSource",
        "retrievedAt",
        "sourceType",
        "tier",
        "accessMode",
        "relevanceScore",
    }
    finding = c.ResearchFinding.model_validate(research_finding()).model_dump(mode="json")
    assert {"sourceIds", "claimType"} <= set(finding)
    candidate = c.TopicCandidate.model_validate(topic_candidate()).model_dump(mode="json")
    assert set(candidate) == {
        "topicId",
        "title",
        "hook",
        "whyNow",
        "relevantNews",
        "mdcopilotConnection",
        "targetAudience",
        "pillar",
        "noveltyScore",
        "evidenceScore",
        "businessRelevance",
        "editorialPotential",
        "timelinessScore",
        "audienceRelevance",
        "totalScore",
        "scoreBreakdown",
        "novelty",
        "sources",
        "status",
    }
    assert set(candidate["relevantNews"][0]) == {"title", "url", "publishedAt"}


@pytest.mark.parametrize("model", MODELS)
def test_default_dump_uses_camel_case_everywhere(model: type[c.Contract]) -> None:
    instance = model.model_validate(BUILDERS[model]())
    assert _keys_with_underscores(instance.model_dump(mode="json")) == []
    assert _keys_with_underscores(instance.model_dump()) == []


def test_dict_keys_inside_data_are_not_renamed() -> None:
    data = topic_candidate()
    data["score_breakdown"] = {"mdcopilot_relevance": score_item()}
    wire = c.TopicCandidate.model_validate(data).model_dump(mode="json")
    assert set(wire["scoreBreakdown"]) == {"mdcopilot_relevance"}
    assert set(wire["scoreBreakdown"]["mdcopilot_relevance"]) == {"weight", "score", "justification"}


def test_json_schema_uses_camel_case_and_requires_every_field() -> None:
    schema = c.GeneratedBlogPost.model_json_schema()
    assert {"contentMarkdown", "pipelineStatus", "qualityGates", "versionNo"} <= set(schema["properties"])
    assert set(schema["required"]) == set(schema["properties"])


# --- strictness ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("model", MODELS)
def test_unknown_field_is_rejected(model: type[c.Contract]) -> None:
    data = BUILDERS[model]()
    data["unexpected"] = 1
    with pytest.raises(ValidationError) as caught:
        model.model_validate(data)
    assert [(e["type"], e["loc"]) for e in caught.value.errors()] == [("extra_forbidden", ("unexpected",))]


def test_unknown_nested_field_is_rejected() -> None:
    data = generated_blog_post()
    data["seo"]["unexpected"] = 1
    data["fact_check"]["claims"][0]["articleLocation"] = "evidence:2"
    with pytest.raises(ValidationError) as caught:
        c.GeneratedBlogPost.model_validate(data)
    assert {(e["type"], e["loc"]) for e in caught.value.errors()} == {
        ("extra_forbidden", ("seo", "unexpected")),
        ("extra_forbidden", ("fact_check", "claims", 0, "articleLocation")),
    }


def test_error_location_names_the_key_the_client_sent() -> None:
    snake = claim_check()
    snake["sentence_index"] = -1
    with pytest.raises(ValidationError) as from_snake:
        c.ClaimCheck.model_validate(snake)
    assert [e["loc"] for e in from_snake.value.errors()] == [("sentence_index",)]

    camel = c.ClaimCheck.model_validate(claim_check()).model_dump(mode="json")
    camel["sentenceIndex"] = -1
    with pytest.raises(ValidationError) as from_camel:
        c.ClaimCheck.model_validate(camel)
    assert [e["loc"] for e in from_camel.value.errors()] == [("sentenceIndex",)]

    del camel["sourceId"]
    camel["sentenceIndex"] = 2
    with pytest.raises(ValidationError) as missing:
        c.ClaimCheck.model_validate(camel)
    assert [(e["type"], e["loc"]) for e in missing.value.errors()] == [("missing", ("sourceId",))]


@pytest.mark.parametrize(
    ("model", "field"),
    [
        pytest.param(c.NewsRef, "published_at", id="NewsRef.published_at"),
        pytest.param(c.ResearchSource, "published_at", id="ResearchSource.published_at"),
        pytest.param(c.BlogSource, "published_at", id="BlogSource.published_at"),
        pytest.param(c.ClaimCheck, "source_id", id="ClaimCheck.source_id"),
        pytest.param(c.ClaimCheck, "recommended_revision", id="ClaimCheck.recommended_revision"),
        pytest.param(c.GeneratedBlogPost, "selected_title", id="GeneratedBlogPost.selected_title"),
        pytest.param(c.GeneratedBlogPost, "social", id="GeneratedBlogPost.social"),
    ],
)
def test_nullable_field_accepts_null_but_must_be_present(model: type[c.Contract], field: str) -> None:
    data = BUILDERS[model]()
    data[field] = None
    assert getattr(model.model_validate(data), field) is None
    del data[field]
    with pytest.raises(ValidationError) as caught:
        model.model_validate(data)
    assert [e["type"] for e in caught.value.errors()] == ["missing"]


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        _param(c.ResearchSource, "source_type", "wire_service"),
        _param(c.ResearchSource, "tier", 4),
        _param(c.ResearchSource, "tier", 0),
        _param(c.ResearchSource, "date_source", "guess"),
        _param(c.ResearchSource, "access_mode", "paywalled"),
        _param(c.ResearchSource, "retrieved_at", "yesterday"),
        _param(c.ResearchFinding, "claim_type", "fact"),
        _param(c.ResearchFinding, "importance", "low"),
        _param(c.NoveltyResult, "decision", "REJECT"),
        _param(c.TopicCandidate, "pillar", "F"),
        _param(c.ClaimCheck, "kind", "rumour"),
        _param(c.ClaimCheck, "importance", "critical"),
        _param(c.ClaimCheck, "verification_status", "VERIFIED"),
        _param(c.ClaimCheck, "sentence_index", -1),
        _param(c.FactCheckResult, "verdict", "MAYBE"),
        _param(c.ClinicalFlag, "severity", "blocking"),
        _param(c.GateResult, "severity", "BLOCKING"),
        _param(c.GeneratedBlogPost, "status", "DONE"),
        _param(c.GeneratedBlogPost, "pipeline_status", "DRAFTING"),
        _param(c.GeneratedBlogPost, "version_no", 0),
    ],
)
def test_invalid_value_is_rejected(model: type[c.Contract], field: str, value: object) -> None:
    data = BUILDERS[model]()
    data[field] = value
    with pytest.raises(ValidationError) as caught:
        model.model_validate(data)
    assert {e["loc"][0] for e in caught.value.errors()} == {field}


# --- 0..1 bounds -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("model", "field", "value"), [_param(m, f, v) for m, f in BOUNDED for v in (0, 0.5, 1)])
def test_bounded_field_accepts_values_in_range(model: type[c.Contract], field: str, value: float) -> None:
    data = BUILDERS[model]()
    data[field] = value
    assert getattr(model.model_validate(data), field) == value


@pytest.mark.parametrize(
    ("model", "field", "value", "error_type"),
    [
        pytest.param(m, f, v, t, id=f"{m.__name__}.{f}={v}")
        for m, f in BOUNDED
        for v, t in ((-0.01, "greater_than_equal"), (1.01, "less_than_equal"))
    ],
)
def test_bounded_field_rejects_values_out_of_range(
    model: type[c.Contract], field: str, value: float, error_type: str
) -> None:
    snake = BUILDERS[model]()
    snake[field] = value
    with pytest.raises(ValidationError) as from_snake:
        model.model_validate(snake)
    assert [(e["type"], e["loc"]) for e in from_snake.value.errors()] == [(error_type, (field,))]

    alias = model.model_fields[field].alias
    assert alias is not None
    camel = model.model_validate(BUILDERS[model]()).model_dump(mode="json")
    camel[alias] = value
    with pytest.raises(ValidationError) as from_camel:
        model.model_validate(camel)
    assert [(e["type"], e["loc"]) for e in from_camel.value.errors()] == [(error_type, (alias,))]


@pytest.mark.parametrize("model", MODELS)
def test_every_float_field_is_bounded_to_unit_interval(model: type[c.Contract]) -> None:
    properties = model.model_json_schema()["properties"]
    float_fields = {name for name, info in model.model_fields.items() if info.annotation is float}
    assert float_fields == {field for m, field in BOUNDED if m is model}
    for name in float_fields:
        prop = properties[model.model_fields[name].alias]
        assert (prop["type"], prop["minimum"], prop["maximum"]) == ("number", 0, 1)
```

- [ ] **Step 12: Run the contracts test and watch it fail**

Run: `docker compose run --rm tools pytest tests/unit/test_contracts.py -q`

Expected: collection error, exit code 2, ending with:
```text
E   ImportError: cannot import name 'contracts' from 'mdcopilot_blog.domain' (/app/src/mdcopilot_blog/domain/__init__.py)
=========================== short test summary info ============================
ERROR tests/unit/test_contracts.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.07s
```

- [ ] **Step 13: Create the contracts**

Create `backend/src/mdcopilot_blog/domain/contracts.py`. The config was checked on pydantic 2.13.5:
- `serialize_by_alias=True` makes a plain `model_dump()` / `model_dump_json()` emit camelCase.
- `validate_by_name` + `validate_by_alias` accept both spellings.
- With `alias_generator` and `validate_by_name=True`, the `pydantic.mypy` plugin lets Python code construct models by field name, for example `ScoreItem(weight=..., score=..., justification=...)`.

```python
"""Typed contracts shared by agents, workflows and the API (ARCHITECTURE §12).

Attributes are snake_case in Python and camelCase on the wire. Input may use either spelling,
unknown keys are rejected, and every score or confidence is bounded to 0..1.
Every field is required, as in §12: a nullable field must still be sent, as null.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from mdcopilot_blog.domain.enums import ArticleStatus, RunStatus

UnitScore = Annotated[float, Field(ge=0, le=1)]
"""A score, weight, similarity or confidence in the closed interval 0..1."""


class Contract(BaseModel):
    """Base for every contract: camelCase aliases, both spellings accepted, no extra keys."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="forbid",
    )


# --- enums -----------------------------------------------------------------------------------------------------


class SourceType(StrEnum):
    GOVERNMENT = "government"
    JOURNAL = "journal"
    PREPRINT = "preprint"
    TRADE_PRESS = "trade_press"
    COMPANY_ANNOUNCEMENT = "company_announcement"
    BLOG = "blog"
    SOCIAL = "social"
    OTHER = "other"


class ClaimType(StrEnum):
    FACT = "FACT"
    ANALYSIS = "ANALYSIS"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    MARKETING_CLAIM = "MARKETING_CLAIM"


class VerificationStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    OUTDATED = "OUTDATED"
    MISLEADING = "MISLEADING"
    OPINION = "OPINION"


class ClaimKind(StrEnum):
    STATISTIC = "statistic"
    REGULATORY = "regulatory"
    TRIAL_RESULT = "trial_result"
    WORKFORCE = "workforce"
    COMPANY_ANNOUNCEMENT = "company_announcement"
    QUOTE_OR_ATTRIBUTION = "quote_or_attribution"
    ANECDOTE_OR_VIGNETTE = "anecdote_or_vignette"
    GENERAL_FACT = "general_fact"
    OPINION = "opinion"


class NoveltyDecision(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    REJECT_TOPIC = "REJECT_TOPIC"


class PillarKey(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    NARRATIVE = "NARRATIVE"


# --- research --------------------------------------------------------------------------------------------------


class ResearchSource(Contract):
    """A ledger entry (``blog_sources``)."""

    id: str
    title: str
    url: str
    canonical_url: str
    publisher: str
    domain: str
    published_at: datetime | None
    date_source: Literal["feed", "api", "jsonld", "meta", "htmldate", "none"]
    retrieved_at: datetime
    source_type: SourceType
    tier: Literal[1, 2, 3]
    access_mode: Literal["full_text", "abstract_only", "metadata_only"]
    relevance_score: UnitScore


class ResearchFinding(Contract):
    """A typed finding linked to ledger sources (``blog_research_findings``)."""

    id: str
    claim: str
    evidence: str
    source_ids: list[str]
    confidence: UnitScore
    category: str
    claim_type: ClaimType
    importance: Literal["high", "normal"]


# --- topics and novelty ----------------------------------------------------------------------------------------


class NewsRef(Contract):
    title: str
    url: str
    published_at: datetime | None


class ScoreItem(Contract):
    """One component of a topic score (ARCHITECTURE §9)."""

    weight: UnitScore
    score: UnitScore
    justification: str


class NoveltyNeighbour(Contract):
    """One of the nearest stored items to a candidate (ARCHITECTURE §8)."""

    kind: str
    ref_id: str
    title: str
    similarity: UnitScore


class NoveltyResult(Contract):
    decision: NoveltyDecision
    max_similarity: UnitScore
    neighbours: list[NoveltyNeighbour]


class TopicCandidate(Contract):
    """A proposed topic with its scores (``blog_topic_candidates``)."""

    topic_id: str
    title: str
    hook: str
    why_now: str
    relevant_news: list[NewsRef]
    mdcopilot_connection: str
    target_audience: str
    pillar: PillarKey
    novelty_score: UnitScore
    evidence_score: UnitScore
    business_relevance: UnitScore
    editorial_potential: UnitScore
    timeliness_score: UnitScore
    audience_relevance: UnitScore
    total_score: UnitScore
    score_breakdown: dict[str, ScoreItem]
    novelty: NoveltyResult
    sources: list[str]
    # Candidate statuses arrive in Phase 3; a plain string until then.
    status: str


# --- article parts ---------------------------------------------------------------------------------------------


class TitleOptions(Contract):
    provocative: str
    operational: str
    visionary: str


class InternalLink(Contract):
    title: str
    url: str


class SEOMetadata(Contract):
    """Spec §22 SEO output for one article version."""

    seo_title: str
    meta_description: str
    slug: str
    primary_keyword: str
    secondary_keywords: list[str]
    og_title: str
    og_description: str
    tags: list[str]
    category: str
    internal_link_suggestions: list[InternalLink]
    external_references: list[str]


class SocialCopy(Contract):
    linkedin: str
    x_post: str
    newsletter_teaser: str


class BlogSource(Contract):
    """A cited source as shown with the article; ``marker`` is the ``S<n>`` citation marker."""

    marker: str
    source_id: str
    title: str
    url: str
    publisher: str
    published_at: datetime | None


# --- reviews ---------------------------------------------------------------------------------------------------


class ClaimCheck(Contract):
    """One extracted claim and its verification (ARCHITECTURE §10)."""

    claim: str
    kind: ClaimKind
    importance: Literal["high", "normal"]
    section_key: str
    sentence_index: Annotated[int, Field(ge=0)]
    span: str
    citation_markers: list[str]
    source_id: str | None
    verification_status: VerificationStatus
    confidence: UnitScore
    recommended_revision: str | None


class FactCheckResult(Contract):
    verdict: Literal["PASS", "FAIL"]
    independent_check: bool
    claims: list[ClaimCheck]


class ClinicalFlag(Contract):
    code: str
    severity: Literal["BLOCKING", "WARNING"]
    message: str
    location: str


class ClinicalReview(Contract):
    flags: list[ClinicalFlag]
    summary: str


class Change(Contract):
    """An editorial change request; the writer records a resolution against ``id``."""

    id: str
    description: str
    location: str


class EditorialReview(Contract):
    editorial_score: UnitScore
    strengths: list[str]
    weaknesses: list[str]
    required_changes: list[Change]
    optional_changes: list[Change]
    final_recommendation: str


class GateResult(Contract):
    gate: str
    passed: bool
    severity: Literal["blocking", "warning"]
    details: str


class GateReport(Contract):
    passed: bool
    results: list[GateResult]


# --- article view ----------------------------------------------------------------------------------------------


class GeneratedBlogPost(Contract):
    """API view over an article, its current version and the version's side tables."""

    id: str
    topic_id: str
    title_options: TitleOptions
    selected_title: str | None
    slug: str
    content_markdown: str
    excerpt: str
    pull_quote: str
    cta: str
    category: str
    tags: list[str]
    seo: SEOMetadata
    social: SocialCopy | None
    sources: list[BlogSource]
    research_summary: str
    fact_check: FactCheckResult
    clinical_review: ClinicalReview
    editorial_review: EditorialReview
    quality_gates: GateReport
    novelty: NoveltyResult
    status: ArticleStatus
    pipeline_status: RunStatus
    version_no: Annotated[int, Field(ge=1)]
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 14: Run the contracts test and watch it pass**

Run: `docker compose run --rm tools pytest tests/unit/test_contracts.py -q`

Expected: `262 passed`.

- [ ] **Step 15: Run the whole domain suite**

Run: `docker compose run --rm tools pytest tests/unit/test_rbac.py tests/unit/test_state_machine.py tests/unit/test_contracts.py -q`

Expected: `727 passed`.

- [ ] **Step 16: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, with Tasks 1–3 done first (the task order):
```text
All checks passed!
21 files already formatted
Success: no issues found in 10 source files
```

Where the counts come from:
- **21 files.** Task 3 ended with 13 `.py` files under `backend/`. This task adds 8: five `domain/` modules and three test files.
- **10 source files.** Task 3 ended with 5 modules under `src/`. This task adds the five `domain/` modules.

If this task runs straight after Task 1 (its only dependency), the counts are `14 files already formatted` and `no issues found in 7 source files`.

A different count means a file is missing or extra. Compare the tree with the Files lists of Tasks 1–4.

Any finding in `src/mdcopilot_blog/domain/` or in the three test files is a failure of this task. Those files were already clean under ruff 0.16.8 and mypy 2.3.1, so a finding there means the copy differs from this plan. Re-copy the file instead of adding `noqa` comments.

Optional (the test files are also mypy-strict clean):

Run: `docker compose run --rm tools mypy tests/unit/test_rbac.py tests/unit/test_state_machine.py tests/unit/test_contracts.py`

Expected: `Success: no issues found in 3 source files`

- [ ] **Step 17: Checkpoint: list files changed (no git)**

Created in this task:
- `backend/src/mdcopilot_blog/domain/__init__.py`
- `backend/src/mdcopilot_blog/domain/enums.py`
- `backend/src/mdcopilot_blog/domain/rbac.py`
- `backend/src/mdcopilot_blog/domain/state_machine.py`
- `backend/src/mdcopilot_blog/domain/contracts.py`
- `backend/tests/unit/test_rbac.py`
- `backend/tests/unit/test_state_machine.py`
- `backend/tests/unit/test_contracts.py`

No existing file is modified, and no dependency changes, so `docker compose build tools` is not needed.

Also record the owner's answer from Step 0. Write either "`WAITING_FOR_TOPIC → FAILED`: not added (contract as written)" or "`WAITING_FOR_TOPIC → FAILED`: added; Task 14 records it in ARCHITECTURE §6".

---

### Task 5: Database layer, models, first migration

Builds the SQLAlchemy base and the 13 Phase 1 tables in schema `app`, the Alembic setup, the first migration (`0001`) and the database test fixtures every later task uses.

Everything in this task was run on 2026-09-17 in throwaway containers (`pgvector/pgvector:pg16`, the contract's lock: alembic 1.20.0, sqlalchemy 2.0.54, dbos 3.0.0, ruff 0.16.8, mypy 2.3.1). Minimal stand-ins were used for the Task 2 and Task 4 files. Results: 11 migration tests passed, `alembic check` was clean after a downgrade/upgrade round trip, and ruff and mypy were clean.

After the review fixes (in-process DBOS migrations, the `tests/db` package marker), the task was re-run on a tree holding exactly the files of Tasks 1–5. `pytest tests -q` gave `812 passed`. Task 3 has since gained a 13th logging test, so Tasks 1–5 as written now give `813 passed` (4 + 47 + 24 + 727 + 11). Step 3 (before the `db` package exists) and Step 16 printed exactly the output given in those steps.

**Files:**
- Create: `backend/src/mdcopilot_blog/db/__init__.py`
- Create: `backend/src/mdcopilot_blog/db/base.py`
- Create: `backend/src/mdcopilot_blog/db/engine.py`
- Create: `backend/src/mdcopilot_blog/db/models/__init__.py`, `auth.py`, `config.py`, `runs.py`, `llm.py`, `notifications.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`, `backend/migrations/script.py.mako`
- Create (generated, then edited): `backend/migrations/versions/2026_09_17_0000-0001_foundation.py`
- Modify: `backend/tests/conftest.py` (adds the `# --- T5: database fixtures ---` block)
- Create: `backend/tests/db/__init__.py` (package marker, like `tests/unit/` and `tests/api/`)
- Test: `backend/tests/db/test_migrations.py`

**Interfaces:**
- Consumes:
  - from T1: `mdcopilot_blog.ids.uuid7() -> uuid.UUID`, the `tools` compose service, and `dbos.run_dbos_database_migrations(system_database_url: str, *, schema: str = "dbos", application_role: str | None = None) -> None` from the locked `dbos==3.0.0` (checked in Step 0);
  - from T2: `Settings`, `get_settings()`, `Settings.database_url(database: str | None = None) -> URL`, `Settings.dbos_system_database_url -> str` and `Settings.postgres_password: SecretStr`.
- Produces:
  - **`mdcopilot_blog.db.base`:** `SCHEMA = "app"`, `NAMING_CONVENTION`, `class Base(DeclarativeBase)`, and the mixins `UUIDPk` (`id`), `CreatedAt` (`created_at`) and `Timestamps(CreatedAt)` (adds `updated_at`).
  - **`mdcopilot_blog.db.engine`:** `make_engine(url: URL | str, **kw: Any) -> AsyncEngine` and `make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]`.
  - **`mdcopilot_blog.db.models`:** `User`, `UserSession`, `LoginAttempt`, `AuditLog`, `BlogSetting`, `BrandProfile`, `ContentPillar`, `BlogRun`, `RunAttempt`, `AgentRun`, `LlmCall`, `PromptVersion`, `Notification`. Columns and names are exactly as in the contract, with every enum column `String(32)` holding `StrEnum.value`.
  - **Alembic:** revision `"0001"` (head, `down_revision=None`).
  - **`tests/conftest.py` constants:** `TEST_DB`, `BACKEND_ROOT`, `ALEMBIC_INI` (a `Path`), `TRUNCATE_COMMITTED_SQL`.
  - **`tests/conftest.py` fixtures:**
    - `settings` (session, sync) → `Settings`;
    - `database_url` (session, sync) → `URL`;
    - `engine` (session, `loop_scope="session"`) → `AsyncEngine`;
    - `db_session` → `AsyncSession` (rolled back);
    - `clean_db` → `None` (truncates before and after);
    - `sessionmaker_committing` → `async_sessionmaker[AsyncSession]` (requests `clean_db` itself).

Decisions and deviations, all verified in the container:
- **`NAMING_CONVENTION` index and unique-constraint names.** These use `%(table_name)s_%(column_0_N_name)s` instead of the reference's `%(column_0_label)s`. With `MetaData(schema="app")`, the column label includes the schema, so the reference would produce names like `ix_app_blog_runs_run_date` rather than the contract's `ix_blog_runs_run_date`. Explicitly named indexes and constraints keep their names.
- **Lowercase emails.** `users` has `CHECK (email = lower(email))` (`ck_users_email_lowercase`) to enforce "stored lowercase". Code that inserts `User` rows must store lowercase emails; `normalize_email` does this.
- **Automatic cleanup.** `sessionmaker_committing` requests `clean_db`, so a committing test cannot forget to clean up. `TRUNCATE app.users … CASCADE` also empties every table with a foreign key to `users` (`blog_settings`, `blog_brand_profiles`, `blog_notifications`).
- **`env.py` typing.** `migrations/env.py` is fully typed (no `type: ignore`), and `mypy migrations/env.py` passes.
- **Downgrade keeps the extension.** The migration's downgrade leaves the `vector` extension installed. `CREATE EXTENSION IF NOT EXISTS` makes a second upgrade safe.
- **In-process DBOS migrations (contract deviation).** The contract says the test fixture runs `dbos migrate` with `subprocess`. That puts the rendered URL, password included, in the child process's argv, where `ps` in the container (and on the Docker host) can read it. The fixture instead calls `dbos.run_dbos_database_migrations(url, schema="dbos")`, which is the function `dbos migrate` itself calls. Task 8's `migrate-dbos` does the same.
  - The function is sync, so the sync `database_url` fixture calls it directly, with no `asyncio.to_thread`.
  - On success it prints nothing. It logs `Initializing DBOS system database with URL: postgresql+psycopg://<user>:***@…` at INFO on the `dbos` logger, with the password masked.
  - On failure it prints `DBOS migrations failed: <cause>` to stdout, then raises `click.exceptions.Exit(1)`, which is a `RuntimeError`. The fixture captures stdout, redacts the URL and the password, and raises `RuntimeError(...) from None`, so neither pytest's captured output nor the traceback can show them.
  - It creates the database if it is missing, as `dbos migrate` does.
  - All of this was checked in the container against dbos 3.0.0. dbos 2.31.1, the header's fallback pin, has the same function with one extra optional keyword.
- **`tests/db/__init__.py`.** `tests/db` is a package, like `tests/unit` and `tests/api`. pytest then imports its modules as `tests.db.test_*`, so a future file cannot shadow an installed or stdlib module, or collide with a same-named test file in another folder.

- [ ] **Step 0: Confirm the in-process DBOS migration API**

Run: `docker compose run --rm tools python -c "import dbos, inspect; print(inspect.signature(dbos.run_dbos_database_migrations))"`

Expected: `(system_database_url: str, *, schema: str = 'dbos', application_role: Optional[str] = None) -> None`

Decision rule:
- **That line printed:** continue with Step 1.
- **The lock was deliberately switched to the header's fallback `dbos==2.31.1`:** the line reads `(system_database_url: str, *, app_database_url: Optional[str] = None, schema: str = 'dbos', application_role: Optional[str] = None) -> None`. The call `(url, schema="dbos")` works unchanged, so continue with Step 1.
- **`AttributeError`, or any other signature:** the installed dbos is neither pin this plan allows. Stop: fix `backend/pyproject.toml`/`uv.lock` (Task 1), run `docker compose build tools`, and repeat this step. Do not fall back to `dbos migrate -s <url>`, which exposes the password in the process list.

- [ ] **Step 1: Write the T5 conftest block and the `tests/db` package marker**

Create `backend/tests/db/__init__.py`:

```python
"""Database tests (disposable mdcopilot_blog_test)."""
```

Replace the whole of `backend/tests/conftest.py`. Task 1 left only a docstring in it. This is the full file after Task 5; Tasks 9 and 11 append their own blocks below this one and add their imports at the top.

```python
"""Shared pytest fixtures. Tests only ever touch the disposable database ``mdcopilot_blog_test``."""

import contextlib
import io
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from dbos import run_dbos_database_migrations
from psycopg import sql
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.settings import Settings, get_settings

# --- T5: database fixtures ---------------------------------------------------------------------------

TEST_DB = "mdcopilot_blog_test"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
TRUNCATE_COMMITTED_SQL = (
    "TRUNCATE app.blog_llm_calls, app.blog_agent_runs, app.blog_run_attempts, app.blog_runs, "
    "app.audit_log, app.login_attempts, app.user_sessions, app.users RESTART IDENTITY CASCADE"
)


def _admin_connect_kwargs(settings: Settings) -> dict[str, Any]:
    # Keyword args, not a URI: render_as_string() does not percent-encode spaces, which libpq rejects.
    return settings.database_url("postgres").translate_connect_args(username="user", database="dbname")


def _recreate_test_db(settings: Settings, *, drop_only: bool = False) -> None:
    with psycopg.connect(**_admin_connect_kwargs(settings), autocommit=True) as conn:  # no tx for (CREATE|DROP) DB
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB)))
        if not drop_only:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))


def _dbos_migrate(settings: Settings) -> None:
    # In-process (what `dbos migrate` runs): the password never sits in a child process's argv.
    url = settings.database_url(TEST_DB).render_as_string(hide_password=False)
    password = settings.postgres_password.get_secret_value()
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):  # dbos echoes a failure's cause to stdout
            run_dbos_database_migrations(url, schema="dbos")
    except RuntimeError:  # dbos echoes the cause, then raises click.exceptions.Exit(1), a RuntimeError
        output = captured.getvalue().replace(url, "***").replace(password, "***")[-2000:]
        msg = f"DBOS migrations failed for {TEST_DB}:\n{output}"
        raise RuntimeError(msg) from None


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings().model_copy(
        update={
            "postgres_db": TEST_DB,
            "mock_mode": True,
            "session_cookie_secure": False,
            "public_app_url": "http://test",
        }
    )


@pytest.fixture(scope="session")
def database_url(settings: Settings) -> Iterator[URL]:
    """Fresh test DB, `alembic upgrade head` and the DBOS system-table migrations, once per session.

    Sync on purpose: migrations/env.py calls asyncio.run(), which fails inside a running loop.
    """
    _recreate_test_db(settings)
    url = settings.database_url()
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = url  # a URL object: no string round-trip of the password
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    _dbos_migrate(settings)
    yield url
    _recreate_test_db(settings, drop_only=True)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(database_url: URL) -> AsyncIterator[AsyncEngine]:
    eng = make_engine(database_url)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test session inside an outer transaction that is always rolled back.

    join_transaction_mode="create_savepoint": commit()/rollback() in code under test only touch
    SAVEPOINTs; nothing a test writes here survives the test.
    """
    async with engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def clean_db(engine: AsyncEngine) -> AsyncIterator[None]:
    """Truncate the tables that committing tests write to, before and after the test.

    TRUNCATE ... CASCADE on app.users also empties every table with a foreign key to users
    (blog_settings, blog_brand_profiles, blog_notifications).
    """
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_COMMITTED_SQL))
    yield
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_COMMITTED_SQL))


@pytest_asyncio.fixture(loop_scope="session")
async def sessionmaker_committing(engine: AsyncEngine, clean_db: None) -> async_sessionmaker[AsyncSession]:
    """A real sessionmaker whose commits persist; `clean_db` removes the rows afterwards."""
    return make_sessionmaker(engine)
```

- [ ] **Step 2: Write the failing migration test**

Create `backend/tests/db/test_migrations.py`. The round-trip and `alembic check` tests run Alembic on a sync connection taken from `AsyncConnection.run_sync` (verified "connection sharing" pattern), because `env.py` calls `asyncio.run()`, which cannot run inside the pytest event loop.

```python
"""The foundation migration: schema placement, named indexes, partial uniques, round trip, no drift."""

import io
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import URL, Connection, pool, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog.db.engine import make_engine
from mdcopilot_blog.db.models import BlogRun, BlogSetting

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

APP_TABLES = {
    "alembic_version",
    "audit_log",
    "blog_agent_runs",
    "blog_brand_profiles",
    "blog_content_pillars",
    "blog_llm_calls",
    "blog_notifications",
    "blog_prompt_versions",
    "blog_run_attempts",
    "blog_runs",
    "blog_settings",
    "login_attempts",
    "user_sessions",
    "users",
}

PARTIAL_UNIQUE_INDEXES = {
    "uq_blog_settings_active": (
        "CREATE UNIQUE INDEX uq_blog_settings_active ON app.blog_settings USING btree (is_active) WHERE is_active"
    ),
    "uq_blog_brand_profiles_active": (
        "CREATE UNIQUE INDEX uq_blog_brand_profiles_active ON app.blog_brand_profiles "
        "USING btree (is_active) WHERE is_active"
    ),
    "uq_blog_runs_daily_date": (
        "CREATE UNIQUE INDEX uq_blog_runs_daily_date ON app.blog_runs USING btree (run_date) "
        "WHERE ((kind)::text = 'daily'::text)"
    ),
}


def _alembic_config(output: io.StringIO | None = None) -> Config:
    cfg = Config(str(ALEMBIC_INI), stdout=output) if output is not None else Config(str(ALEMBIC_INI))
    cfg.attributes["configure_logger"] = False
    return cfg


def _run_alembic(sync_conn: Connection, cfg: Config, action: str, revision: str) -> None:
    # connection sharing: env.py uses this connection instead of calling asyncio.run()
    cfg.attributes["connection"] = sync_conn
    if action == "upgrade":
        command.upgrade(cfg, revision)
    elif action == "downgrade":
        command.downgrade(cfg, revision)
    else:
        command.check(cfg)


async def _app_tables(session: AsyncSession) -> set[str]:
    rows = await session.scalars(text("select table_name from information_schema.tables where table_schema = 'app'"))
    return set(rows.all())


def test_single_head_is_0001() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_heads() == ["0001"]
    revision = script.get_revision("0001")
    assert revision is not None
    assert revision.down_revision is None


async def test_tables_live_in_schema_app(db_session: AsyncSession) -> None:
    assert await _app_tables(db_session) == APP_TABLES
    public = await db_session.scalars(
        text("select table_name from information_schema.tables where table_schema = 'public'")
    )
    assert public.all() == []
    assert await db_session.scalar(text("select version_num from app.alembic_version")) == "0001"


async def test_vector_extension_and_dbos_schema_exist(db_session: AsyncSession) -> None:
    assert await db_session.scalar(text("select extname from pg_extension where extname = 'vector'")) == "vector"
    dbos_tables = await db_session.scalar(
        text("select count(*) from information_schema.tables where table_schema = 'dbos'")
    )
    assert dbos_tables is not None
    assert dbos_tables > 0


async def test_partial_unique_indexes_exist(db_session: AsyncSession) -> None:
    rows = await db_session.execute(
        text("select indexname, indexdef from pg_indexes where schemaname = 'app' and indexname = any(:names)"),
        {"names": list(PARTIAL_UNIQUE_INDEXES)},
    )
    assert dict(rows.tuples().all()) == PARTIAL_UNIQUE_INDEXES


async def test_named_indexes_exist(db_session: AsyncSession) -> None:
    rows = await db_session.scalars(text("select indexname from pg_indexes where schemaname = 'app'"))
    names = set(rows.all())
    assert {
        "ix_blog_runs_created_at",
        "ix_blog_runs_run_date",
        "ix_blog_runs_status",
        "ix_blog_llm_calls_provider_model",
        "ix_blog_llm_calls_created_at",
        "ix_blog_agent_runs_created_at",
        "uq_blog_agent_runs_wf_step",
        "uq_blog_run_attempts_dbos_workflow_id",
        "uq_blog_prompt_versions_name_version",
        "uq_users_email",
        "uq_user_sessions_token_hash",
        "uq_blog_content_pillars_key",
    } <= names


async def test_only_one_active_settings_version(db_session: AsyncSession) -> None:
    db_session.add(BlogSetting(version=1, values={}, is_active=True))
    await db_session.flush()
    db_session.add(BlogSetting(version=2, values={}, is_active=False))
    await db_session.flush()  # any number of inactive versions is fine
    db_session.add(BlogSetting(version=3, values={}, is_active=True))
    with pytest.raises(IntegrityError, match="uq_blog_settings_active"):
        await db_session.flush()
    await db_session.rollback()


async def test_one_daily_run_per_date_but_many_manual_runs(db_session: AsyncSession) -> None:
    day = date(2026, 9, 17)
    db_session.add_all(
        [
            BlogRun(kind="manual", run_date=day, status="QUEUED", trace_id="a" * 32),
            BlogRun(kind="manual", run_date=day, status="QUEUED", trace_id="b" * 32),
            BlogRun(kind="daily", run_date=day, status="QUEUED", trace_id="c" * 32),
        ]
    )
    await db_session.flush()
    db_session.add(BlogRun(kind="daily", run_date=day, status="QUEUED", trace_id="d" * 32))
    with pytest.raises(IntegrityError, match="uq_blog_runs_daily_date"):
        await db_session.flush()
    await db_session.rollback()


async def test_sessionmaker_committing_really_commits(
    sessionmaker_committing: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    async with sessionmaker_committing() as db:
        db.add(BlogRun(kind="manual", run_date=date(2026, 9, 18), status="QUEUED", trace_id="e" * 32))
        await db.commit()
    async with engine.connect() as conn:
        assert await conn.scalar(text("select count(*) from app.blog_runs")) == 1


async def test_clean_db_removed_the_committed_run(db_session: AsyncSession) -> None:
    assert await db_session.scalar(text("select count(*) from app.blog_runs")) == 0


async def test_downgrade_to_base_then_upgrade_to_head(database_url: URL) -> None:
    # own NullPool engine: the round trip must not share pooled connections with other tests
    eng = make_engine(database_url, poolclass=pool.NullPool)
    try:
        async with eng.connect() as conn:
            await conn.execute(text("SET lock_timeout = '10s'"))
            await conn.run_sync(_run_alembic, _alembic_config(), "downgrade", "base")
            remaining = await conn.scalars(
                text("select table_name from information_schema.tables where table_schema = 'app'")
            )
            assert remaining.all() == ["alembic_version"]
            await conn.run_sync(_run_alembic, _alembic_config(), "upgrade", "head")
            restored = await conn.scalars(
                text("select table_name from information_schema.tables where table_schema = 'app'")
            )
            assert set(restored.all()) == APP_TABLES
            assert await conn.scalar(text("select version_num from app.alembic_version")) == "0001"
    finally:
        await eng.dispose()


async def test_alembic_check_reports_no_drift(database_url: URL) -> None:
    output = io.StringIO()
    eng = make_engine(database_url, poolclass=pool.NullPool)
    try:
        async with eng.connect() as conn:
            await conn.run_sync(_run_alembic, _alembic_config(output), "check", "head")
    finally:
        await eng.dispose()
    assert "No new upgrade operations detected." in output.getvalue()
```

- [ ] **Step 3: Run the test to see it fail**

Run: `docker compose run --rm tools pytest tests/db/test_migrations.py -q`

Expected: collection fails with
```
ImportError while loading conftest '/app/tests/conftest.py'.
tests/conftest.py:19: in <module>
    from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
E   ModuleNotFoundError: No module named 'mdcopilot_blog.db'
```

- [ ] **Step 4: Write the declarative base and engine factory**

Create `backend/src/mdcopilot_blog/db/__init__.py`:

```python
"""Database layer: declarative base, engine factory, models and seed data (schema ``app``)."""
```

Create `backend/src/mdcopilot_blog/db/base.py`:

```python
"""Declarative base, naming convention and shared column mixins.

Every table lives in the Postgres schema ``app`` (Alembic-managed). DBOS owns schema ``dbos``.
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mdcopilot_blog.ids import uuid7

SCHEMA = "app"

# "ix" uses table_name + column names (not column_0_label, which would prefix the schema: ix_app_...).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
    }


class UUIDPk:
    """UUIDv7 primary key, generated in Python so ids sort by creation time."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7, sort_order=-100)


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), sort_order=100)


class Timestamps(CreatedAt):
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), sort_order=101)
```

Create `backend/src/mdcopilot_blog/db/engine.py`:

```python
"""Async engine and session factories (psycopg 3 driver)."""

from typing import Any

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def make_engine(url: URL | str, **kw: Any) -> AsyncEngine:
    """Pass a ``URL`` object where possible: ``str(URL)`` masks the password as ``***``."""
    return create_async_engine(url, pool_pre_ping=True, **kw)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 5: Write the auth and config models**

Create `backend/src/mdcopilot_blog/db/models/auth.py`:

```python
"""Users, sessions, login attempts and the audit log."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None]


class UserSession(UUIDPk, CreatedAt, Base):
    """A login session. Only the sha256 of the opaque token is stored."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))


class LoginAttempt(UUIDPk, CreatedAt, Base):
    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_created_at", "created_at"),)

    email: Mapped[str] = mapped_column(String(320), index=True)
    ip: Mapped[str | None] = mapped_column(String(64), index=True)
    succeeded: Mapped[bool]


class AuditLog(UUIDPk, CreatedAt, Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_created_at", "created_at"),)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
```

Create `backend/src/mdcopilot_blog/db/models/config.py`:

```python
"""Versioned settings, versioned brand profile and content pillars."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class BlogSetting(UUIDPk, CreatedAt, Base):
    """One row per saved settings version; at most one row is active."""

    __tablename__ = "blog_settings"
    __table_args__ = (Index("uq_blog_settings_active", "is_active", unique=True, postgresql_where=text("is_active")),)

    version: Mapped[int] = mapped_column(unique=True)
    values: Mapped[dict[str, Any]]
    is_active: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class BrandProfile(UUIDPk, CreatedAt, Base):
    """One row per saved brand-profile version; at most one row is active."""

    __tablename__ = "blog_brand_profiles"
    __table_args__ = (
        Index("uq_blog_brand_profiles_active", "is_active", unique=True, postgresql_where=text("is_active")),
    )

    version: Mapped[int] = mapped_column(unique=True)
    profile: Mapped[dict[str, Any]]
    is_active: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ContentPillar(UUIDPk, Timestamps, Base):
    """A thematic pillar (spec section 9). ``weekdays`` uses 0 = Monday ... 6 = Sunday."""

    __tablename__ = "blog_content_pillars"

    key: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    weekdays: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(default=0, server_default=text("0"))
```

- [ ] **Step 6: Write the run, LLM and notification models**

Create `backend/src/mdcopilot_blog/db/models/runs.py`:

```python
"""User-visible runs, one row per DBOS execution (attempt), and one row per step execution."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class BlogRun(UUIDPk, Timestamps, Base):
    __tablename__ = "blog_runs"
    __table_args__ = (
        Index("ix_blog_runs_created_at", "created_at"),
        # at most one scheduled (daily) run per local date; manual runs are unrestricted
        Index("uq_blog_runs_daily_date", "run_date", unique=True, postgresql_where=text("kind = 'daily'")),
    )

    kind: Mapped[str] = mapped_column(String(32))
    run_date: Mapped[date] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str | None] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    trace_id: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0), server_default=text("0"))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error: Mapped[dict[str, Any] | None]


class RunAttempt(UUIDPk, CreatedAt, Base):
    __tablename__ = "blog_run_attempts"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="CASCADE"), index=True)
    dbos_workflow_id: Mapped[str] = mapped_column(String(128), unique=True)
    workflow_name: Mapped[str] = mapped_column(String(128))
    attempt_no: Mapped[int]
    forked_from_workflow_id: Mapped[str | None] = mapped_column(String(128))
    start_step: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error: Mapped[dict[str, Any] | None]


class AgentRun(UUIDPk, CreatedAt, Base):
    """One row per DBOS step execution; a re-executed step increments ``tries``."""

    __tablename__ = "blog_agent_runs"
    __table_args__ = (
        UniqueConstraint("dbos_workflow_id", "dbos_step_id", name="uq_blog_agent_runs_wf_step"),
        Index("ix_blog_agent_runs_created_at", "created_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_runs.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_run_attempts.id", ondelete="CASCADE"))
    dbos_workflow_id: Mapped[str] = mapped_column(String(128))
    dbos_step_id: Mapped[int]
    step_name: Mapped[str] = mapped_column(String(128))
    agent_name: Mapped[str | None] = mapped_column(String(64))
    agent_version: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(32), index=True)
    tries: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None]
    input_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0), server_default=text("0"))
    sources_used: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    error: Mapped[dict[str, Any] | None]
    trace_id: Mapped[str] = mapped_column(String(32))
```

Create `backend/src/mdcopilot_blog/db/models/llm.py`:

```python
"""One row per LLM, search or embedding attempt, and the registered prompt versions."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, UUIDPk


class LlmCall(UUIDPk, CreatedAt, Base):
    """``attempt_id``, ``agent_run_id``, ``article_id`` and ``topic_candidate_id`` carry no FK yet.

    The recorder truncates ``error_message`` to 2000 characters before insert.
    """

    __tablename__ = "blog_llm_calls"
    __table_args__ = (
        Index("ix_blog_llm_calls_provider_model", "provider_requested", "model_requested"),
        Index("ix_blog_llm_calls_created_at", "created_at"),
    )

    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_runs.id", ondelete="SET NULL"), index=True)
    attempt_id: Mapped[uuid.UUID | None]
    agent_run_id: Mapped[uuid.UUID | None]
    article_id: Mapped[uuid.UUID | None]
    topic_candidate_id: Mapped[uuid.UUID | None]
    dbos_workflow_id: Mapped[str | None] = mapped_column(String(128))
    dbos_step_id: Mapped[int | None]
    kind: Mapped[str] = mapped_column(String(32))
    agent_name: Mapped[str | None] = mapped_column(String(64))
    prompt_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[int | None]
    prompt_sha: Mapped[str | None] = mapped_column(String(64))
    provider_requested: Mapped[str] = mapped_column(String(32))
    model_requested: Mapped[str] = mapped_column(String(128))
    provider_served: Mapped[str | None] = mapped_column(String(32))
    model_served: Mapped[str | None] = mapped_column(String(128))
    fallback_from: Mapped[str | None] = mapped_column(String(200))
    attempt_index: Mapped[int]
    params: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    input_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cache_read_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cache_write_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    reasoning_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    search_actions: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    latency_ms: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    error_class: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    usage_raw: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0), server_default=text("0"))
    price_version: Mapped[str] = mapped_column(String(64))
    trace_id: Mapped[str] = mapped_column(String(32))


class PromptVersion(UUIDPk, CreatedAt, Base):
    """Immutable registry row per (prompt name, version)."""

    __tablename__ = "blog_prompt_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_blog_prompt_versions_name_version"),)

    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[int]
    agent: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    front_matter: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
```

Create `backend/src/mdcopilot_blog/db/models/notifications.py`:

```python
"""In-app notifications."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, UUIDPk


class Notification(UUIDPk, CreatedAt, Base):
    """``user_id`` NULL means a broadcast to every user."""

    __tablename__ = "blog_notifications"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500))
    read_at: Mapped[datetime | None]
```

Create `backend/src/mdcopilot_blog/db/models/__init__.py`:

```python
"""All ORM models. Importing this package registers every table on ``Base.metadata``."""

from mdcopilot_blog.db.models.auth import AuditLog, LoginAttempt, User, UserSession
from mdcopilot_blog.db.models.config import BlogSetting, BrandProfile, ContentPillar
from mdcopilot_blog.db.models.llm import LlmCall, PromptVersion
from mdcopilot_blog.db.models.notifications import Notification
from mdcopilot_blog.db.models.runs import AgentRun, BlogRun, RunAttempt

__all__ = [
    "AgentRun",
    "AuditLog",
    "BlogRun",
    "BlogSetting",
    "BrandProfile",
    "ContentPillar",
    "LlmCall",
    "LoginAttempt",
    "Notification",
    "PromptVersion",
    "RunAttempt",
    "User",
    "UserSession",
]
```

- [ ] **Step 7: Check that every model registers**

Run: `docker compose run --rm tools python -c "import mdcopilot_blog.db.models; from mdcopilot_blog.db.base import Base; print(len(Base.metadata.tables), sorted(Base.metadata.tables))"`

Expected:
```
13 ['app.audit_log', 'app.blog_agent_runs', 'app.blog_brand_profiles', 'app.blog_content_pillars', 'app.blog_llm_calls', 'app.blog_notifications', 'app.blog_prompt_versions', 'app.blog_run_attempts', 'app.blog_runs', 'app.blog_settings', 'app.login_attempts', 'app.user_sessions', 'app.users']
```

- [ ] **Step 8: Write the Alembic configuration**

These files are the `alembic init -t async` output (alembic 1.20.0) with the verified edits applied, so do not run `alembic init`. Run `mkdir -p backend/migrations/versions` first.

Create `backend/alembic.ini`. There is no `sqlalchemy.url`, and the ruff post-write hooks are enabled:

```ini
# Alembic configuration (started from `alembic init -t async`, alembic 1.20.0).
# The database URL is NOT stored here: migrations/env.py reads it from
# Config.attributes["database_url"] (tests, CLI) or from Settings.database_url().

[alembic]
script_location = %(here)s/migrations
# 2026_09_17_0000-0001_foundation.py
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
prepend_sys_path = .
path_separator = os

[post_write_hooks]
# every generated revision is linted and formatted with the project's ruff settings
hooks = ruff_fix, ruff_format
ruff_fix.type = exec
ruff_fix.executable = ruff
ruff_fix.options = check --fix REVISION_SCRIPT_FILENAME
ruff_format.type = exec
ruff_format.executable = ruff
ruff_format.options = format REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/migrations/env.py`:

```python
"""Alembic environment (async template, edited).

Edits from the `alembic init -t async` template:
- the URL comes from Config.attributes["database_url"] or Settings.database_url(), never from alembic.ini
  (ConfigParser interpolation breaks on "%" in percent-encoded passwords);
- every table and alembic_version live in schema "app"; autogenerate only looks at that schema;
- pgvector columns render as Vector(n) with an import (later phases add vector columns);
- a caller can pass an open sync connection in Config.attributes["connection"] (used inside event loops).
"""

import asyncio
from collections.abc import Mapping
from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import URL, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import mdcopilot_blog.db.models  # noqa: F401  (registers every table on Base.metadata)
from mdcopilot_blog.db.base import SCHEMA, Base

config = context.config

# Callers (pytest, the CLI) pass attributes["configure_logger"] = False to keep their own logging.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str | URL:
    url: str | URL | None = config.attributes.get("database_url")
    if url:
        return url  # never str(URL): SQLAlchemy masks the password as ***
    from mdcopilot_blog.settings import get_settings

    return get_settings().database_url()


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    if type_ == "type" and isinstance(obj, VECTOR):
        autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
        return f"Vector({obj.dim})"
    return False


def include_name(name: str | None, type_: str, parent_names: Mapping[str, str | None]) -> bool:
    if type_ == "schema":
        return name == SCHEMA
    return True


CONFIGURE_KW: dict[str, Any] = {
    "target_metadata": target_metadata,
    "version_table_schema": SCHEMA,
    "include_schemas": True,
    "include_name": include_name,
    "compare_server_default": True,
    "render_item": render_item,
}


def run_migrations_offline() -> None:
    context.configure(url=get_url(), literal_binds=True, dialect_opts={"paramstyle": "named"}, **CONFIGURE_KW)
    with context.begin_transaction():
        context.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # The schema must exist before Alembic creates app.alembic_version. Commit it so Alembic
    # still owns (and commits) its own transaction below.
    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    connection.commit()
    context.configure(connection=connection, **CONFIGURE_KW)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    connection: Connection | None = config.attributes.get("connection")
    if connection is None:
        asyncio.run(run_async_migrations())
    else:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/migrations/script.py.mako`. It already uses the modern typing forms, so the ruff hook has little left to fix:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 9: Confirm the development database has no revision yet**

Run: `docker compose run --rm tools alembic current`

Expected: only the two `INFO [alembic.runtime.migration] …` lines, with no revision id. If so, go to Step 10.

If a revision id is printed, an earlier attempt (or a later task) has already migrated this database. `env.py` recreates the `app` schema on upgrade, so a reset is safe only while the database holds no accounts. `docker compose run` leaves `db` running; otherwise start it first with `docker compose up -d --wait db`.

1. Check for accounts:
   ```bash
   docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from app.users"'
   ```
2. Apply the decision rule:
   - **The command fails with `ERROR:  relation "app.users" does not exist`, or prints `0`:** there is no owner data. Reset the schema, then run `docker compose run --rm tools alembic current` again and expect no revision id:
     ```bash
     docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA IF EXISTS app CASCADE"'
     ```
   - **It prints any number above 0:** the database holds accounts, so Task 8 or Task 14 has already run against it. **Stop. Do not drop anything.** Ask the owner how to proceed, for example with a `pg_dump` backup first or a fresh `blog_pgdata` volume.

- [ ] **Step 10: Generate the migration inside the container**

Run: `docker compose run --rm tools alembic revision --autogenerate --rev-id 0001 -m foundation`

Expected output:
- 13 `Detected added table` lines, in this order: `app.blog_content_pillars`, `app.blog_prompt_versions`, `app.login_attempts`, `app.users`, `app.audit_log`, `app.blog_brand_profiles`, `app.blog_notifications`, `app.blog_runs`, `app.blog_settings`, `app.user_sessions`, `app.blog_llm_calls`, `app.blog_run_attempts`, `app.blog_agent_runs`;
- `Detected added index` lines for each index;
- then:
  ```
  Generating /app/migrations/versions/<YYYY_MM_DD_HHMM>-0001_foundation.py ...  done
  Running post write hook 'ruff_fix' ...
  All checks passed!
    done
  Running post write hook 'ruff_format' ...
  1 file reformatted
    done
  ```

The timestamp in the generated name is the container's UTC time.

- [ ] **Step 11: Rename the revision file**

Run: `mv backend/migrations/versions/*-0001_foundation.py backend/migrations/versions/2026_09_17_0000-0001_foundation.py && ls backend/migrations/versions`

Expected: `2026_09_17_0000-0001_foundation.py` (plus `__pycache__` if present). Exactly one `*0001*` file must exist.

- [ ] **Step 12: Apply the three manual edits**

1. Replace the module docstring (the first seven lines, from `"""foundation` down to the closing `"""`) with:
   ```python
   """foundation: auth, settings, brand, pillars, runs, attempts, step runs, LLM calls, prompts, notifications

   Revision ID: 0001
   Revises:
   Create Date: 2026-09-17 00:00:00

   """
   ```
2. In `upgrade()`, directly after `"""Upgrade schema."""`, insert:
   ```python
       # manual: autogenerate never emits extensions. No vector columns exist yet; later phases add them.
       op.execute("CREATE EXTENSION IF NOT EXISTS vector")
   ```
3. At the very end of `downgrade()`, after `# ### end Alembic commands ###`, add:
   ```python
       # manual: the vector extension is left installed (it may be shared, and IF NOT EXISTS makes re-upgrade safe).
   ```

- [ ] **Step 13: Compare with the expected migration**

After Step 12 the file must read exactly as below. This listing is the verified autogenerate output (alembic 1.20.0, ruff-formatted) with the three edits applied.

If an operation, column, type, default or name differs, a model in Steps 5–6 differs from this plan:
1. Fix the model.
2. Delete the revision file.
3. Repeat Steps 10–12.

Never hand-edit the generated operations to match.

```python
"""foundation: auth, settings, brand, pillars, runs, attempts, step runs, LLM calls, prompts, notifications

Revision ID: 0001
Revises:
Create Date: 2026-09-17 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # manual: autogenerate never emits extensions. No vector columns exist yet; later phases add them.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "blog_content_pillars",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "topics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "weekdays", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_content_pillars")),
        sa.UniqueConstraint("key", name=op.f("uq_blog_content_pillars_key")),
        schema="app",
    )
    op.create_table(
        "blog_prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("agent", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "front_matter",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_prompt_versions")),
        sa.UniqueConstraint("name", "version", name="uq_blog_prompt_versions_name_version"),
        schema="app",
    )
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
        schema="app",
    )
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"], unique=False, schema="app")
    op.create_index(op.f("ix_login_attempts_email"), "login_attempts", ["email"], unique=False, schema="app")
    op.create_index(op.f("ix_login_attempts_ip"), "login_attempts", ["ip"], unique=False, schema="app")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        schema="app",
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app.users.id"], name=op.f("fk_audit_log_actor_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
        schema="app",
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False, schema="app")
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False, schema="app")
    op.create_table(
        "blog_brand_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app.users.id"], name=op.f("fk_blog_brand_profiles_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_brand_profiles")),
        sa.UniqueConstraint("version", name=op.f("uq_blog_brand_profiles_version")),
        schema="app",
    )
    op.create_index(
        "uq_blog_brand_profiles_active",
        "blog_brand_profiles",
        ["is_active"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "blog_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app.users.id"], name=op.f("fk_blog_notifications_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_notifications")),
        schema="app",
    )
    op.create_index(
        op.f("ix_blog_notifications_user_id"), "blog_notifications", ["user_id"], unique=False, schema="app"
    )
    op.create_table(
        "blog_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column(
            "params", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app.users.id"], name=op.f("fk_blog_runs_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_runs")),
        schema="app",
    )
    op.create_index("ix_blog_runs_created_at", "blog_runs", ["created_at"], unique=False, schema="app")
    op.create_index(op.f("ix_blog_runs_run_date"), "blog_runs", ["run_date"], unique=False, schema="app")
    op.create_index(op.f("ix_blog_runs_status"), "blog_runs", ["status"], unique=False, schema="app")
    op.create_index(
        "uq_blog_runs_daily_date",
        "blog_runs",
        ["run_date"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("kind = 'daily'"),
    )
    op.create_table(
        "blog_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app.users.id"], name=op.f("fk_blog_settings_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_settings")),
        sa.UniqueConstraint("version", name=op.f("uq_blog_settings_version")),
        schema="app",
    )
    op.create_index(
        "uq_blog_settings_active",
        "blog_settings",
        ["is_active"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app.users.id"], name=op.f("fk_user_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
        schema="app",
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False, schema="app")
    op.create_table(
        "blog_llm_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        sa.Column("article_id", sa.Uuid(), nullable=True),
        sa.Column("topic_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("dbos_step_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("prompt_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("prompt_sha", sa.String(length=64), nullable=True),
        sa.Column("provider_requested", sa.String(length=32), nullable=False),
        sa.Column("model_requested", sa.String(length=128), nullable=False),
        sa.Column("provider_served", sa.String(length=32), nullable=True),
        sa.Column("model_served", sa.String(length=128), nullable=True),
        sa.Column("fallback_from", sa.String(length=200), nullable=True),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column(
            "params", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cache_write_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("search_actions", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_class", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "usage_raw", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("price_version", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["app.blog_runs.id"], name=op.f("fk_blog_llm_calls_run_id_blog_runs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_llm_calls")),
        schema="app",
    )
    op.create_index("ix_blog_llm_calls_created_at", "blog_llm_calls", ["created_at"], unique=False, schema="app")
    op.create_index(
        "ix_blog_llm_calls_provider_model",
        "blog_llm_calls",
        ["provider_requested", "model_requested"],
        unique=False,
        schema="app",
    )
    op.create_index(op.f("ix_blog_llm_calls_run_id"), "blog_llm_calls", ["run_id"], unique=False, schema="app")
    op.create_table(
        "blog_run_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_name", sa.String(length=128), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("forked_from_workflow_id", sa.String(length=128), nullable=True),
        sa.Column("start_step", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["app.blog_runs.id"], name=op.f("fk_blog_run_attempts_run_id_blog_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_run_attempts")),
        sa.UniqueConstraint("dbos_workflow_id", name=op.f("uq_blog_run_attempts_dbos_workflow_id")),
        schema="app",
    )
    op.create_index(op.f("ix_blog_run_attempts_run_id"), "blog_run_attempts", ["run_id"], unique=False, schema="app")
    op.create_table(
        "blog_agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("dbos_workflow_id", sa.String(length=128), nullable=False),
        sa.Column("dbos_step_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("agent_version", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("tries", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "sources_used",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["app.blog_run_attempts.id"],
            name=op.f("fk_blog_agent_runs_attempt_id_blog_run_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["app.blog_runs.id"], name=op.f("fk_blog_agent_runs_run_id_blog_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_agent_runs")),
        sa.UniqueConstraint("dbos_workflow_id", "dbos_step_id", name="uq_blog_agent_runs_wf_step"),
        schema="app",
    )
    op.create_index("ix_blog_agent_runs_created_at", "blog_agent_runs", ["created_at"], unique=False, schema="app")
    op.create_index(op.f("ix_blog_agent_runs_run_id"), "blog_agent_runs", ["run_id"], unique=False, schema="app")
    op.create_index(op.f("ix_blog_agent_runs_status"), "blog_agent_runs", ["status"], unique=False, schema="app")
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_blog_agent_runs_status"), table_name="blog_agent_runs", schema="app")
    op.drop_index(op.f("ix_blog_agent_runs_run_id"), table_name="blog_agent_runs", schema="app")
    op.drop_index("ix_blog_agent_runs_created_at", table_name="blog_agent_runs", schema="app")
    op.drop_table("blog_agent_runs", schema="app")
    op.drop_index(op.f("ix_blog_run_attempts_run_id"), table_name="blog_run_attempts", schema="app")
    op.drop_table("blog_run_attempts", schema="app")
    op.drop_index(op.f("ix_blog_llm_calls_run_id"), table_name="blog_llm_calls", schema="app")
    op.drop_index("ix_blog_llm_calls_provider_model", table_name="blog_llm_calls", schema="app")
    op.drop_index("ix_blog_llm_calls_created_at", table_name="blog_llm_calls", schema="app")
    op.drop_table("blog_llm_calls", schema="app")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions", schema="app")
    op.drop_table("user_sessions", schema="app")
    op.drop_index(
        "uq_blog_settings_active", table_name="blog_settings", schema="app", postgresql_where=sa.text("is_active")
    )
    op.drop_table("blog_settings", schema="app")
    op.drop_index(
        "uq_blog_runs_daily_date", table_name="blog_runs", schema="app", postgresql_where=sa.text("kind = 'daily'")
    )
    op.drop_index(op.f("ix_blog_runs_status"), table_name="blog_runs", schema="app")
    op.drop_index(op.f("ix_blog_runs_run_date"), table_name="blog_runs", schema="app")
    op.drop_index("ix_blog_runs_created_at", table_name="blog_runs", schema="app")
    op.drop_table("blog_runs", schema="app")
    op.drop_index(op.f("ix_blog_notifications_user_id"), table_name="blog_notifications", schema="app")
    op.drop_table("blog_notifications", schema="app")
    op.drop_index(
        "uq_blog_brand_profiles_active",
        table_name="blog_brand_profiles",
        schema="app",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_table("blog_brand_profiles", schema="app")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log", schema="app")
    op.drop_index(op.f("ix_audit_log_action"), table_name="audit_log", schema="app")
    op.drop_table("audit_log", schema="app")
    op.drop_table("users", schema="app")
    op.drop_index(op.f("ix_login_attempts_ip"), table_name="login_attempts", schema="app")
    op.drop_index(op.f("ix_login_attempts_email"), table_name="login_attempts", schema="app")
    op.drop_index("ix_login_attempts_created_at", table_name="login_attempts", schema="app")
    op.drop_table("login_attempts", schema="app")
    op.drop_table("blog_prompt_versions", schema="app")
    op.drop_table("blog_content_pillars", schema="app")
    # ### end Alembic commands ###
    # manual: the vector extension is left installed (it may be shared, and IF NOT EXISTS makes re-upgrade safe).
```

- [ ] **Step 14: Round-trip the migration and check for drift**

Run: `docker compose run --rm tools sh -c "alembic upgrade head && alembic check && alembic downgrade base && alembic upgrade head && alembic current && alembic check"`

Expected:
- `Running upgrade  -> 0001, foundation: …`, then `Running downgrade 0001 -> , foundation: …`;
- `0001 (head)`;
- `No new upgrade operations detected.` printed twice, with exit status 0.

- [ ] **Step 15: Run the migration tests to see them pass**

Run: `docker compose run --rm tools pytest tests/db/test_migrations.py -q`

Expected: `11 passed`. The session fixture creates `mdcopilot_blog_test`, migrates it (Alembic, then the in-process DBOS migrations into schema `dbos`) and drops it at the end.

- [ ] **Step 16: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, when Tasks 1–5 have run in order and no later task has:
```
All checks passed!
34 files already formatted
Success: no issues found in 19 source files
```
- **34** is the number of `.py` files under `backend/`: 19 in `src/`, 2 in `migrations/` (`env.py` and the revision) and 13 in `tests/`. ruff 0.16.8 also formats `*.md` files by default, but `backend/` has none until Task 6.
- **19** is the number of modules under `src/`: 2 from Task 1, 1 from Task 2, 2 from Task 3, 5 from Task 4 and 9 from this task.
- A lower count means a file from the Files lists is missing.

Run: `docker compose run --rm tools mypy migrations/env.py`

Expected: `Success: no issues found in 1 source file`.

- [ ] **Step 17: Checkpoint: list the files changed in this task (no git)**

Files changed:
- `backend/src/mdcopilot_blog/db/__init__.py`, `base.py`, `engine.py`
- `backend/src/mdcopilot_blog/db/models/__init__.py`, `auth.py`, `config.py`, `runs.py`, `llm.py`, `notifications.py`
- `backend/alembic.ini`
- `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/2026_09_17_0000-0001_foundation.py`
- `backend/tests/conftest.py`
- `backend/tests/db/__init__.py`, `backend/tests/db/test_migrations.py`

---

### Task 6: Prompt registry

This task loads versioned prompt files from `backend/prompts/<agent>/<name>.v<N>.md`, checks them, renders them with Jinja2 `StrictUndefined`, and registers each file's hash in `app.blog_prompt_versions`. It covers ARCHITECTURE §19 and the Phase 1 "Prompt registry" item: startup fails if a prompt's text changed but its version number did not.

**Verified.** Every file below was run exactly as written, on 2026-09-17, in a throwaway image built from this plan's `pyproject.toml`.
- **Image and database:** `uv lock` resolved pydantic-ai-slim 2.43.0, dbos 3.0.0, jinja2 3.1.6, pyyaml 6.0.3, sqlalchemy 2.0.54, ruff 0.16.8 and mypy 2.3.1 on python 3.12.14. The database was a `pgvector/pgvector:pg16` container.
- **Stand-ins for other tasks:** Task 1, 2, 4 and 5 modules were contract-faithful stand-ins:
  - the enums match Task 4 exactly;
  - `PromptVersion` has the contract's columns;
  - the `db_session` fixture uses the verified `create_savepoint` pattern.
- **Results:**
  - Red phase: `ModuleNotFoundError: No module named 'mdcopilot_blog.prompts'` (2 collection errors).
  - Green phase: **15 passed**.
  - `ruff check`, `ruff format --check` and `mypy src` (strict + pydantic plugin) were clean. mypy was also clean on the test files.

**Design decisions**
- **Filename rule.** The filename must be `<last segment of name>.v<version>.md`, and the first path segment under the root must equal `agent`. So `hello/echo` v1 lives at `prompts/hello/echo.v1.md`. The same (name, version) appearing twice anywhere under the root is rejected.
- **Front matter.**
  - It is the YAML between the first two `---` lines, and the keys `name, version, agent, output, variables` are required.
  - `version` must be a positive `int` (a YAML `true` is refused).
  - `variables` must be a list of unique strings that **exactly equals** `jinja2.meta.find_undeclared_variables(body)`.
- **Body and hash.**
  - The body is everything after the closing `---`, with leading blank lines removed.
  - `sha256` is the digest of the **full file bytes**, so a front-matter edit also needs a version bump.
- **Rendering errors.** `render()` raises `PromptRegistryError` when:
  - a variable is missing or extra (checked before rendering);
  - an attribute is undefined at render time (`StrictUndefined`, e.g. `{{ topic.headline }}` with a plain string).
- **Commits.** `sync_to_db()` **commits** itself, so callers (worker startup, `cli sync-prompts`) only pass a fresh session.
  - It first checks every file against existing rows. On a changed sha it raises `PromptRegistryError("prompt {name} v{version} changed without a version bump")` before inserting anything.
  - Under the test `db_session` (`join_transaction_mode="create_savepoint"`), that commit only releases a savepoint.
- **Default root and the runtime image.** `default_prompt_root()` returns `Path(__file__).resolve().parents[3] / "prompts"` when that directory exists; this covers the editable dev install, where the bind mount is `/app`.
  - **Contract deviation, and the reason for it:** a non-editable runtime install lives in `site-packages`, where `parents[3]` is wrong. So it falls back to `Path.cwd() / "prompts"`.
  - **Constraint on Task 14:** the runtime image must keep `WORKDIR /app` and copy `prompts/` (and `fixtures/`, see Task 10) to `/app`.
- **Extra method.** `templates()` returns every loaded template sorted by (name, version), for sync and diagnostics. It is not in the contract.

**Files:**
- Create: `backend/src/mdcopilot_blog/prompts/__init__.py`
- Create: `backend/src/mdcopilot_blog/prompts/registry.py`
- Create: `backend/prompts/hello/echo.v1.md`
- Test: `backend/tests/unit/test_prompt_registry.py`
- Test: `backend/tests/db/test_prompt_sync.py`

**Interfaces:**
- **Consumes:**
  - `mdcopilot_blog.db.models.PromptVersion` (Task 5; columns `name, version, agent, sha256, body, front_matter`, unique `(name, version)`);
  - pytest fixture `db_session` (Task 5 conftest block);
  - `jinja2` and `pyyaml` (Task 1 dependencies).
- **Produces** (module `mdcopilot_blog.prompts.registry`):
  - `class PromptRegistryError(RuntimeError)`
  - `@dataclass(frozen=True) class PromptTemplate(name: str, version: int, agent: str, output: str, variables: tuple[str, ...], body: str, sha256: str, path: Path)`
  - `@dataclass(frozen=True) class RenderedPrompt(name: str, version: int, sha256: str, text: str)`
  - `def default_prompt_root() -> Path`
  - `class PromptRegistry`:
    - `PromptRegistry.from_directory(root: Path) -> PromptRegistry` (classmethod)
    - `.templates() -> tuple[PromptTemplate, ...]`
    - `.get(name: str, version: int | None = None) -> PromptTemplate`
    - `.render(name: str, variables: Mapping[str, object], version: int | None = None) -> RenderedPrompt`
    - `async .sync_to_db(session: AsyncSession) -> int` (commits)
  - The prompt `hello/echo` v1 (agent `hello`, output `EchoOutput`, variables `brand_name`, `topic`), used by Task 10's gateway test and Task 11's `HELLO_SPEC`.

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/unit/test_prompt_registry.py`:

```python
"""Prompt registry: loading rules, rendering, version selection, hashing (no database)."""

import hashlib
from pathlib import Path

import pytest

from mdcopilot_blog.prompts.registry import (
    PromptRegistry,
    PromptRegistryError,
    RenderedPrompt,
    default_prompt_root,
)


def write_prompt(
    root: Path,
    relative: str,
    *,
    name: str,
    version: int,
    agent: str,
    variables: list[str],
    body: str,
    output: str = "DraftOutput",
) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    variable_lines = "".join(f"  - {v}\n" for v in variables) if variables else ""
    variables_block = f"variables:\n{variable_lines}" if variables else "variables: []\n"
    path.write_text(
        f"---\nname: {name}\nversion: {version}\nagent: {agent}\noutput: {output}\n{variables_block}---\n{body}",
        encoding="utf-8",
    )
    return path


def test_loads_valid_prompt_and_renders(tmp_path: Path) -> None:
    path = write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["brand_name", "topic"],
        body="Write for {{ brand_name }} about {{ topic }}.\n",
    )
    registry = PromptRegistry.from_directory(tmp_path)

    template = registry.get("writer/draft")
    assert template.name == "writer/draft"
    assert template.version == 1
    assert template.agent == "writer"
    assert template.output == "DraftOutput"
    assert template.variables == ("brand_name", "topic")
    assert template.body == "Write for {{ brand_name }} about {{ topic }}.\n"
    assert template.path == path
    assert template.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()

    rendered = registry.render("writer/draft", {"brand_name": "MDCopilot", "topic": "burnout"})
    assert rendered == RenderedPrompt(
        name="writer/draft",
        version=1,
        sha256=template.sha256,
        text="Write for MDCopilot about burnout.\n",
    )


def test_filename_must_match_name_and_version(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v2.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=[],
        body="static\n",
    )
    with pytest.raises(PromptRegistryError, match=r"filename must be 'draft\.v1\.md'"):
        PromptRegistry.from_directory(tmp_path)


def test_file_must_live_under_agent_directory(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "seo/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=[],
        body="static\n",
    )
    with pytest.raises(PromptRegistryError, match="must live under"):
        PromptRegistry.from_directory(tmp_path)


def test_declared_variables_must_match_template(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["topic"],
        body="{{ topic }} for {{ audience }}\n",
    )
    with pytest.raises(PromptRegistryError, match="do not match"):
        PromptRegistry.from_directory(tmp_path)


def test_missing_front_matter_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "writer" / "draft.v1.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: writer/draft\nversion: 1\nagent: writer\n---\nbody\n", encoding="utf-8")
    with pytest.raises(PromptRegistryError, match="missing keys"):
        PromptRegistry.from_directory(tmp_path)


def test_duplicate_name_and_version_is_rejected(tmp_path: Path) -> None:
    for relative in ("writer/draft.v1.md", "writer/archive/draft.v1.md"):
        write_prompt(
            tmp_path,
            relative,
            name="writer/draft",
            version=1,
            agent="writer",
            variables=[],
            body="static\n",
        )
    with pytest.raises(PromptRegistryError, match="duplicate prompt writer/draft v1"):
        PromptRegistry.from_directory(tmp_path)


def test_render_rejects_missing_and_extra_variables(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["topic"],
        body="About {{ topic }}\n",
    )
    registry = PromptRegistry.from_directory(tmp_path)
    with pytest.raises(PromptRegistryError, match=r"missing variables \['topic'\]"):
        registry.render("writer/draft", {})
    with pytest.raises(PromptRegistryError, match=r"unexpected variables \['tone'\]"):
        registry.render("writer/draft", {"topic": "x", "tone": "warm"})


def test_render_strict_undefined_attribute_raises(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["topic"],
        body="Headline: {{ topic.headline }}\n",
    )
    registry = PromptRegistry.from_directory(tmp_path)
    with pytest.raises(PromptRegistryError, match="headline"):
        registry.render("writer/draft", {"topic": "a plain string has no headline"})
    rendered = registry.render("writer/draft", {"topic": {"headline": "Burnout"}})
    assert rendered.text == "Headline: Burnout\n"


def test_get_returns_latest_version_unless_pinned(tmp_path: Path) -> None:
    for version in (1, 2, 10):
        write_prompt(
            tmp_path,
            f"writer/draft.v{version}.md",
            name="writer/draft",
            version=version,
            agent="writer",
            variables=[],
            body=f"version {version}\n",
        )
    registry = PromptRegistry.from_directory(tmp_path)
    assert registry.get("writer/draft").version == 10
    assert registry.get("writer/draft", version=2).body == "version 2\n"
    assert registry.render("writer/draft", {}, version=1).text == "version 1\n"
    with pytest.raises(PromptRegistryError, match="unknown prompt writer/draft v3"):
        registry.get("writer/draft", version=3)
    with pytest.raises(PromptRegistryError, match="unknown prompt writer/missing"):
        registry.get("writer/missing")


def test_sha_is_stable_and_tracks_file_bytes(tmp_path: Path) -> None:
    path = write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=[],
        body="same text\n",
    )
    first = PromptRegistry.from_directory(tmp_path).get("writer/draft").sha256
    second = PromptRegistry.from_directory(tmp_path).get("writer/draft").sha256
    assert first == second

    path.write_text(path.read_text(encoding="utf-8") + "one more line\n", encoding="utf-8")
    changed = PromptRegistry.from_directory(tmp_path).get("writer/draft").sha256
    assert changed != first
    assert changed == hashlib.sha256(path.read_bytes()).hexdigest()


def test_missing_root_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PromptRegistryError, match="does not exist"):
        PromptRegistry.from_directory(tmp_path / "nope")


def test_default_root_loads_hello_echo() -> None:
    registry = PromptRegistry.from_directory(default_prompt_root())
    template = registry.get("hello/echo")
    assert template.version == 1
    assert template.agent == "hello"
    assert template.output == "EchoOutput"
    assert template.variables == ("brand_name", "topic")
    rendered = registry.render("hello/echo", {"brand_name": "MDCopilot", "topic": "hello"})
    assert "MDCopilot" in rendered.text
    assert "hello" in rendered.text
```

- [ ] **Step 2: Write the failing database test**

Create `backend/tests/db/test_prompt_sync.py`:

```python
"""PromptRegistry.sync_to_db against the disposable test database."""

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import PromptVersion
from mdcopilot_blog.prompts.registry import PromptRegistry, PromptRegistryError, default_prompt_root

PROMPT_TEXT = (
    "---\n"
    "name: sync_agent/greet\n"
    "version: 1\n"
    "agent: sync_agent\n"
    "output: GreetOutput\n"
    "variables:\n"
    "  - who\n"
    "---\n"
    "Greet {{ who }}.\n"
)


def make_registry(root: Path) -> PromptRegistry:
    path = root / "sync_agent" / "greet.v1.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PROMPT_TEXT, encoding="utf-8")
    return PromptRegistry.from_directory(root)


async def test_sync_inserts_missing_rows_once(db_session: AsyncSession, tmp_path: Path) -> None:
    registry = make_registry(tmp_path)

    assert await registry.sync_to_db(db_session) == 1
    assert await registry.sync_to_db(db_session) == 0

    rows = (await db_session.scalars(select(PromptVersion).where(PromptVersion.name == "sync_agent/greet"))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.version == 1
    assert row.agent == "sync_agent"
    assert row.sha256 == hashlib.sha256(PROMPT_TEXT.encode("utf-8")).hexdigest()
    assert row.body == "Greet {{ who }}.\n"
    assert row.front_matter == {
        "name": "sync_agent/greet",
        "version": 1,
        "agent": "sync_agent",
        "output": "GreetOutput",
        "variables": ["who"],
    }


async def test_sync_refuses_changed_text_without_version_bump(db_session: AsyncSession, tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    db_session.add(
        PromptVersion(
            name="sync_agent/greet",
            version=1,
            agent="sync_agent",
            sha256="0" * 64,
            body="an older text",
            front_matter={},
        )
    )
    await db_session.flush()

    with pytest.raises(PromptRegistryError, match="prompt sync_agent/greet v1 changed without a version bump"):
        await registry.sync_to_db(db_session)


async def test_sync_registers_the_shipped_prompts(db_session: AsyncSession) -> None:
    registry = PromptRegistry.from_directory(default_prompt_root())
    await registry.sync_to_db(db_session)
    assert await registry.sync_to_db(db_session) == 0
    row = await db_session.scalar(
        select(PromptVersion).where(PromptVersion.name == "hello/echo", PromptVersion.version == 1)
    )
    assert row is not None
    assert row.sha256 == registry.get("hello/echo", version=1).sha256
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_prompt_registry.py tests/db/test_prompt_sync.py -q`

Expected: `Interrupted: 2 errors during collection`, and both errors are `E   ModuleNotFoundError: No module named 'mdcopilot_blog.prompts'`.

- [ ] **Step 4: Create the package marker**

Create `backend/src/mdcopilot_blog/prompts/__init__.py`:

```python
"""Versioned prompt registry (files live in backend/prompts)."""
```

- [ ] **Step 5: Create the seed prompt**

Create `backend/prompts/hello/echo.v1.md`. The file must start with the `---` line; nothing may come before it.

```markdown
---
name: hello/echo
version: 1
agent: hello
output: EchoOutput
variables:
  - brand_name
  - topic
---
You are the {{ brand_name }} pipeline self-test agent.
Reply with one short, friendly greeting about "{{ topic }}".
Return `message` (the greeting) and `word_count` (the number of words in `message`).
```

- [ ] **Step 6: Implement the registry**

Create `backend/src/mdcopilot_blog/prompts/registry.py`:

```python
"""Versioned prompt files: load, validate, render, and register in ``blog_prompt_versions``.

Layout: ``backend/prompts/<agent>/<name-last-segment>.v<version>.md`` with YAML front matter
between the first two ``---`` lines. A registered (name, version) whose file bytes changed
without a version bump is refused (ARCHITECTURE §19).
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2
import yaml
from jinja2 import meta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import PromptVersion

REQUIRED_KEYS = frozenset({"name", "version", "agent", "output", "variables"})
FRONT_MATTER_DELIMITER = "---"


class PromptRegistryError(RuntimeError):
    """A prompt file is invalid, missing, or changed without a version bump."""


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: int
    agent: str
    output: str
    variables: tuple[str, ...]
    body: str
    sha256: str
    path: Path


@dataclass(frozen=True)
class RenderedPrompt:
    name: str
    version: int
    sha256: str
    text: str


def default_prompt_root() -> Path:
    """``backend/prompts``.

    parents[3] is ``backend/`` for the editable install (dev image, bind mount on /app).
    A non-editable install lives in site-packages, so fall back to ``<cwd>/prompts``
    (the runtime image uses WORKDIR /app and copies ``prompts/`` there).
    """
    candidate = Path(__file__).resolve().parents[3] / "prompts"
    if candidate.is_dir():
        return candidate
    return Path.cwd() / "prompts"


def _make_environment() -> jinja2.Environment:
    # Prompts are plain text for an LLM, not HTML, so autoescape is off on purpose.
    return jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=False, keep_trailing_newline=True)


def _split_front_matter(path: Path, text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FRONT_MATTER_DELIMITER:
        raise PromptRegistryError(f"{path}: file must start with a '---' front matter line")
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_DELIMITER:
            raw = "".join(lines[1:index])
            body = "".join(lines[index + 1 :]).lstrip("\n")
            break
    else:
        raise PromptRegistryError(f"{path}: front matter is not closed with a second '---' line")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PromptRegistryError(f"{path}: front matter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise PromptRegistryError(f"{path}: front matter must be a YAML mapping")
    return data, body


def _parse_file(root: Path, path: Path, env: jinja2.Environment) -> tuple[PromptTemplate, dict[str, Any]]:
    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptRegistryError(f"{path}: prompt files must be UTF-8") from exc
    front, body = _split_front_matter(path, text)

    missing = REQUIRED_KEYS - front.keys()
    if missing:
        raise PromptRegistryError(f"{path}: front matter is missing keys {sorted(missing)}")
    name, version, agent, output, variables = (
        front["name"],
        front["version"],
        front["agent"],
        front["output"],
        front["variables"],
    )
    if not isinstance(name, str) or not name or any(not part for part in name.split("/")):
        raise PromptRegistryError(f"{path}: 'name' must be a non-empty string like 'agent/prompt'")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise PromptRegistryError(f"{path}: 'version' must be a positive integer")
    if not isinstance(agent, str) or not agent:
        raise PromptRegistryError(f"{path}: 'agent' must be a non-empty string")
    if not isinstance(output, str) or not output:
        raise PromptRegistryError(f"{path}: 'output' must be a non-empty string")
    if not isinstance(variables, list) or not all(isinstance(v, str) for v in variables):
        raise PromptRegistryError(f"{path}: 'variables' must be a list of strings")
    if len(set(variables)) != len(variables):
        raise PromptRegistryError(f"{path}: 'variables' contains duplicates")

    expected_filename = f"{name.rsplit('/', 1)[-1]}.v{version}.md"
    if path.name != expected_filename:
        raise PromptRegistryError(f"{path}: filename must be {expected_filename!r} for name={name!r} version={version}")
    relative = path.relative_to(root)
    if len(relative.parts) < 2 or relative.parts[0] != agent:
        raise PromptRegistryError(f"{path}: prompt for agent {agent!r} must live under {root / agent}")

    try:
        parsed = env.parse(body)
    except jinja2.TemplateSyntaxError as exc:
        raise PromptRegistryError(f"{path}: template syntax error: {exc}") from exc
    used = meta.find_undeclared_variables(parsed)
    declared = set(variables)
    if used != declared:
        raise PromptRegistryError(
            f"{path}: declared variables {sorted(declared)} do not match the template's {sorted(used)}"
        )

    template = PromptTemplate(
        name=name,
        version=version,
        agent=agent,
        output=output,
        variables=tuple(variables),
        body=body,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        path=path,
    )
    return template, front


class PromptRegistry:
    def __init__(
        self,
        templates: Mapping[tuple[str, int], PromptTemplate],
        front_matter: Mapping[tuple[str, int], Mapping[str, Any]],
    ) -> None:
        self._env = _make_environment()
        self._templates: dict[tuple[str, int], PromptTemplate] = dict(templates)
        self._front_matter: dict[tuple[str, int], dict[str, Any]] = {k: dict(v) for k, v in front_matter.items()}
        self._compiled: dict[tuple[str, int], jinja2.Template] = {
            key: self._env.from_string(t.body) for key, t in self._templates.items()
        }

    @classmethod
    def from_directory(cls, root: Path) -> "PromptRegistry":
        if not root.is_dir():
            raise PromptRegistryError(f"prompt directory {root} does not exist")
        env = _make_environment()
        templates: dict[tuple[str, int], PromptTemplate] = {}
        front_matter: dict[tuple[str, int], dict[str, Any]] = {}
        for path in sorted(root.glob("**/*.v*.md")):
            if not path.is_file():
                continue
            template, front = _parse_file(root, path, env)
            key = (template.name, template.version)
            if key in templates:
                raise PromptRegistryError(
                    f"duplicate prompt {template.name} v{template.version}: {templates[key].path} and {path}"
                )
            templates[key] = template
            front_matter[key] = front
        return cls(templates, front_matter)

    def templates(self) -> tuple[PromptTemplate, ...]:
        return tuple(self._templates[key] for key in sorted(self._templates))

    def get(self, name: str, version: int | None = None) -> PromptTemplate:
        if version is not None:
            try:
                return self._templates[(name, version)]
            except KeyError:
                raise PromptRegistryError(f"unknown prompt {name} v{version}") from None
        versions = [v for (n, v) in self._templates if n == name]
        if not versions:
            raise PromptRegistryError(f"unknown prompt {name}")
        return self._templates[(name, max(versions))]

    def render(self, name: str, variables: Mapping[str, object], version: int | None = None) -> RenderedPrompt:
        template = self.get(name, version)
        declared = set(template.variables)
        given = set(variables)
        if given != declared:
            raise PromptRegistryError(
                f"prompt {template.name} v{template.version}: missing variables {sorted(declared - given)}, "
                f"unexpected variables {sorted(given - declared)}"
            )
        compiled = self._compiled[(template.name, template.version)]
        try:
            text = compiled.render(**variables)
        except jinja2.UndefinedError as exc:
            raise PromptRegistryError(f"prompt {template.name} v{template.version}: {exc}") from exc
        return RenderedPrompt(name=template.name, version=template.version, sha256=template.sha256, text=text)

    async def sync_to_db(self, session: AsyncSession) -> int:
        """Insert missing (name, version) rows and commit. Refuse changed text without a version bump."""
        existing_rows = (
            await session.execute(select(PromptVersion.name, PromptVersion.version, PromptVersion.sha256))
        ).all()
        existing = {(row.name, row.version): row.sha256 for row in existing_rows}
        to_insert: list[PromptTemplate] = []
        for template in self.templates():
            key = (template.name, template.version)
            stored_sha = existing.get(key)
            if stored_sha is None:
                to_insert.append(template)
            elif stored_sha != template.sha256:
                raise PromptRegistryError(f"prompt {template.name} v{template.version} changed without a version bump")
        for template in to_insert:
            session.add(
                PromptVersion(
                    name=template.name,
                    version=template.version,
                    agent=template.agent,
                    sha256=template.sha256,
                    body=template.body,
                    front_matter=self._front_matter[(template.name, template.version)],
                )
            )
        await session.commit()
        return len(to_insert)
```

- [ ] **Step 7: Run the tests and watch them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_prompt_registry.py tests/db/test_prompt_sync.py -q`

Expected: `15 passed` (12 unit, 3 database).

- [ ] **Step 8: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, when Tasks 1–6 are done in plan order and nothing else has been added:
```text
All checks passed!
39 files already formatted
Success: no issues found in 21 source files
```

Where the two numbers come from (checked on 2026-09-17 with ruff 0.16.8 and mypy 2.3.1, on this plan's files for Tasks 1–6; that check gave 38 because its tree did not yet have Task 5's `tests/db/__init__.py`, which this plan creates):
- **39 formatted files.** This is every `.py` file under `backend/` (38) plus the Markdown prompt `backend/prompts/hello/echo.v1.md`, because ruff 0.16.8's `format` includes Markdown files by default.
  - Dot-directories (`.venv`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`) are not counted.
  - Task 5 ended at 34 (34 `.py` files, including `tests/db/__init__.py`, and no Markdown). This task adds 4 `.py` files and 1 Markdown file.
- **21 source files.** This is every `.py` file under `backend/src/`: 19 after Task 5, plus `prompts/__init__.py` and `prompts/registry.py`.

If either number is different, list the files and compare them with the **Files** lists of Tasks 1–6:
```bash
find backend -name '.*' -prune -o -type f \( -name '*.py' -o -name '*.md' \) -print | sort
find backend/src -type f -name '*.py' | sort
```
The first list must have 39 entries and the second must have 21. A missing entry means an earlier step was skipped. An extra entry is a file that is not part of this plan.

If `ruff format --check` lists a file from this task, run `docker compose run --rm tools ruff format src tests`, then re-run Step 7.

- [ ] **Step 9: Checkpoint: list the files changed in this task (no git)**

Files created:
- `backend/src/mdcopilot_blog/prompts/__init__.py`
- `backend/src/mdcopilot_blog/prompts/registry.py`
- `backend/prompts/hello/echo.v1.md`
- `backend/tests/unit/test_prompt_registry.py`
- `backend/tests/db/test_prompt_sync.py`

No other file is modified.

---

### Task 7: Auth core and audit

Local accounts with Argon2id hashing, database sessions that store only a token hash, the CSRF primitives, login throttling, and the audit writer. No HTTP yet; Task 9 wires these into routes.

> Verified 2026-09-17 in a throwaway container (`python:3.12-slim-trixie`, the pinned lock, `pgvector/pgvector:pg16`) against contract-shaped stand-ins for Tasks 2–5: all Task 7 tests passed, and `ruff check`, `ruff format --check` and `mypy --strict` were clean.

**Files:**
- Create: `backend/src/mdcopilot_blog/auth/__init__.py`, `auth/passwords.py`, `auth/csrf.py`, `auth/users.py`, `auth/sessions.py`, `auth/rate_limit.py`
- Create: `backend/src/mdcopilot_blog/services/__init__.py`, `services/audit.py`
- Test: `backend/tests/unit/test_passwords.py`, `backend/tests/unit/test_csrf.py`, `backend/tests/db/test_users.py`, `backend/tests/db/test_sessions.py`, `backend/tests/db/test_rate_limit.py`, `backend/tests/db/test_audit.py`

**Interfaces:**
- Consumes:
  - Task 4: `mdcopilot_blog.domain.enums.Role`.
  - Task 5: `mdcopilot_blog.db.models.User`, `UserSession`, `LoginAttempt`, `AuditLog`; the conftest fixture `db_session` (an `AsyncSession` in `create_savepoint` mode with `expire_on_commit=False`, rolled back after each test).
- Produces:
  - `auth/passwords.py`: `hash_password(pw: str) -> str`; `verify_password(pw: str, hashed: str) -> tuple[bool, str | None]` (an unknown hash format returns `(False, None)`).
  - `auth/csrf.py`: `SAFE_METHODS: frozenset[str]`; `csrf_token_for(session_token: str, secret: str) -> str`; `tokens_match(a: str, b: str) -> bool`; `origin_allowed(origin: str | None, *, host: str | None, forwarded_proto: str | None, scheme: str, public_app_url: str) -> bool`.
  - `auth/users.py`: `MIN_PASSWORD_LENGTH = 12`; `class UserExists(ValueError)`; `normalize_email(email: str) -> str`; `validate_password(password: str) -> None` (raises `ValueError("password must be at least 12 characters")`); `async get_user_by_email(db, email) -> User | None`; `async create_user(db, *, email, display_name, role: Role, password) -> User` (flush only); `async set_password(user: User, password: str) -> None` (validates and hashes; no flush); `async authenticate(db, *, email, password) -> User | None`.
  - `auth/sessions.py`: `IDLE_TIMEOUT`, `ABSOLUTE_TIMEOUT`, `TOUCH_INTERVAL`; `hash_token(token: str) -> str`; `@dataclass(frozen=True) ResolvedSession(user: User, session: UserSession)`; `async create_session(db, user, *, ip, user_agent, now) -> str`; `async resolve_session(db, token, *, now) -> ResolvedSession | None`; `async revoke_session(db, token, *, now) -> None`; `async revoke_user_sessions(db, user_id: uuid.UUID, *, now: datetime, keep_token: str | None = None) -> int`.
  - `auth/rate_limit.py`: `WINDOW`, `MAX_FAILURES_PER_EMAIL`, `MAX_FAILURES_PER_IP`; `async login_allowed(db, *, email, ip, now) -> bool`; `async record_login_attempt(db, *, email, ip, succeeded) -> None`.
  - `services/audit.py`: `async audit(db, *, actor_user_id, action, entity_type, entity_id=None, reason=None, details=None) -> None` (flush only; `details` are stored JSON-safe, so UUIDs, datetimes and Decimals become strings).

**Behaviour decisions (read before implementing):**
- No function here commits. Callers (routes, CLI) own the transaction.
- Argon2 is CPU-bound, so `create_user`, `set_password` and `authenticate` run it in `asyncio.to_thread`. `authenticate` also spends one dummy verify for unknown emails, so response time does not reveal which emails exist.
- `create_user` inserts inside `db.begin_nested()`. If a concurrent insert wins, the SAVEPOINT rolls back, `UserExists` is raised, and the caller's transaction stays usable.
- Session expiry: idle when `now - last_seen_at >= 30 min`; absolute when `now >= expires_at` (`created + 12 h`). `last_seen_at` is rewritten only when it is at least 60 s old.
- `login_attempts.created_at` comes from the database clock (`now()`, which is the transaction start time). `login_allowed` counts failures with `created_at > now - 15 min`, where `now` is the caller's clock. Successful attempts never count.

- [ ] **Step 1: Write the failing password tests**

Create `backend/tests/unit/test_passwords.py`:

```python
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from mdcopilot_blog.auth.passwords import hash_password, verify_password


def test_hash_is_argon2id_with_recommended_parameters() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert "correct-horse-battery" not in hashed


def test_same_password_hashes_differently() -> None:
    assert hash_password("correct-horse-battery") != hash_password("correct-horse-battery")


def test_verify_correct_password_needs_no_rehash() -> None:
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed) == (True, None)


def test_verify_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery")
    assert verify_password("wrong-horse-battery", hashed) == (False, None)


def test_verify_garbage_hash_is_false_not_an_error() -> None:
    assert verify_password("correct-horse-battery", "not-a-hash") == (False, None)


def test_weak_parameters_are_upgraded() -> None:
    weak = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash("correct-horse-battery")
    ok, new_hash = verify_password("correct-horse-battery", weak)
    assert ok is True
    assert new_hash is not None
    assert new_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
```

- [ ] **Step 2: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_passwords.py -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'mdcopilot_blog.auth'`, and `1 error`.

- [ ] **Step 3: Create the auth package and the password module**

Create `backend/src/mdcopilot_blog/auth/__init__.py`:

```python
"""Authentication: passwords, sessions, CSRF, login throttling and users."""
```

Create `backend/src/mdcopilot_blog/auth/passwords.py`:

```python
"""Argon2id password hashing (pwdlib)."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hash = PasswordHash.recommended()


def hash_password(pw: str) -> str:
    """Return an Argon2id hash with pwdlib's recommended parameters."""
    return _password_hash.hash(pw)


def verify_password(pw: str, hashed: str) -> tuple[bool, str | None]:
    """Return (ok, new_hash). Persist new_hash when it is not None (the stored parameters were outdated)."""
    try:
        return _password_hash.verify_and_update(pw, hashed)
    except UnknownHashError:
        return False, None
```

- [ ] **Step 4: Run the password tests and see them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_passwords.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Write the failing CSRF primitive tests**

Create `backend/tests/unit/test_csrf.py`:

```python
import pytest

from mdcopilot_blog.auth.csrf import SAFE_METHODS, csrf_token_for, origin_allowed, tokens_match

SECRET = "s" * 40


def test_token_is_deterministic_hex_sha256() -> None:
    token = csrf_token_for("session-a", SECRET)
    assert token == csrf_token_for("session-a", SECRET)
    assert len(token) == 64
    assert int(token, 16) >= 0


def test_token_depends_on_session_and_secret() -> None:
    assert csrf_token_for("session-a", SECRET) != csrf_token_for("session-b", SECRET)
    assert csrf_token_for("session-a", SECRET) != csrf_token_for("session-a", "t" * 40)


def test_token_is_not_the_session_token() -> None:
    assert "session-a" not in csrf_token_for("session-a", SECRET)


def test_tokens_match() -> None:
    assert tokens_match("abc", "abc") is True
    assert tokens_match("abc", "abd") is False
    assert tokens_match("abc", "") is False


def test_tokens_match_accepts_non_ascii_without_raising() -> None:
    assert tokens_match("abc", "abé") is False


def test_safe_methods() -> None:
    assert frozenset({"GET", "HEAD", "OPTIONS"}) == SAFE_METHODS


def _allowed(origin: str | None, host: str | None = "api:8000", proto: str | None = None, scheme: str = "http") -> bool:
    return origin_allowed(
        origin, host=host, forwarded_proto=proto, scheme=scheme, public_app_url="http://localhost:8310/"
    )


@pytest.mark.parametrize(
    ("origin", "host", "proto", "scheme", "expected"),
    [
        ("http://localhost:8310", "api:8000", None, "http", True),  # public URL, trailing slash stripped
        ("http://web:5173", "web:5173", "http", "http", True),  # Vite proxy with changeOrigin:false
        ("https://blog.example", "blog.example", "https", "http", True),  # TLS terminated upstream
        ("https://blog.example", "blog.example", "https,http", "http", True),  # proxy chain
        ("http://blog.example", "blog.example", "https", "http", False),  # scheme mismatch
        ("https://blog.example", "blog.example", None, "http", False),  # no forwarded proto
        ("http://evil.example", "api:8000", None, "http", False),
        ("null", "api:8000", None, "http", False),
        ("http://WEB:5173", "web:5173", None, "http", True),  # case-insensitive
        (None, "api:8000", None, "http", False),
        ("", "api:8000", None, "http", False),
        ("http://web:5173", None, None, "http", False),
    ],
)
def test_origin_allowed(origin: str | None, host: str | None, proto: str | None, scheme: str, expected: bool) -> None:
    assert _allowed(origin, host, proto, scheme) is expected
```

- [ ] **Step 6: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_csrf.py -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'mdcopilot_blog.auth.csrf'`.

- [ ] **Step 7: Implement the CSRF primitives**

Create `backend/src/mdcopilot_blog/auth/csrf.py`. `origin_allowed` compares case-insensitively and takes the first entry of a comma-separated `X-Forwarded-Proto`. The dev proxy (Task 13) must use `changeOrigin: false` and `xfwd: true`, so the API sees `Host: web:5173` and `X-Forwarded-Proto: http` (verified in research).

```python
"""CSRF primitives: a session-bound token and the Origin allow-list check."""

import hashlib
import hmac

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def csrf_token_for(session_token: str, secret: str) -> str:
    """Derive the CSRF token from the raw session token, so it needs no storage."""
    return hmac.new(secret.encode(), b"csrf:" + session_token.encode(), hashlib.sha256).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    """Constant-time comparison. Bytes, so non-ASCII header values cannot raise TypeError."""
    return hmac.compare_digest(a.encode(), b.encode())


def origin_allowed(
    origin: str | None,
    *,
    host: str | None,
    forwarded_proto: str | None,
    scheme: str,
    public_app_url: str,
) -> bool:
    """True iff Origin is the configured public URL or the origin the request was addressed to."""
    if not origin:
        return False
    candidate = origin.strip().lower()
    if candidate == public_app_url.strip().rstrip("/").lower():
        return True
    if not host:
        return False
    # X-Forwarded-Proto may be a comma-separated chain; the first entry is the client-facing scheme.
    proto = (forwarded_proto or scheme).split(",")[0].strip().lower()
    return candidate == f"{proto}://{host.strip().lower()}"
```

- [ ] **Step 8: Run the CSRF tests and see them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_csrf.py -q`
Expected: `18 passed`.

- [ ] **Step 9: Write the failing user tests**

Create `backend/tests/db/test_users.py`:

```python
import pytest
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.passwords import verify_password
from mdcopilot_blog.auth.users import (
    MIN_PASSWORD_LENGTH,
    UserExists,
    authenticate,
    create_user,
    get_user_by_email,
    normalize_email,
    set_password,
)
from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Role

PASSWORD = "correct-horse-battery"


def test_normalize_email() -> None:
    assert normalize_email("  Ann@Example.TEST ") == "ann@example.test"


def test_min_password_length_is_12() -> None:
    assert MIN_PASSWORD_LENGTH == 12


async def test_create_user_stores_normalized_email_and_hash(db_session: AsyncSession) -> None:
    user = await create_user(
        db_session, email=" Ann@Example.TEST ", display_name=" Ann ", role=Role.EDITOR, password=PASSWORD
    )
    assert user.id is not None
    assert user.email == "ann@example.test"
    assert user.display_name == "Ann"
    assert user.role == "editor"
    assert user.is_active is True
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash) == (True, None)
    assert user.created_at is not None


async def test_duplicate_email_raises_user_exists_and_session_stays_usable(db_session: AsyncSession) -> None:
    await create_user(db_session, email="dup@example.test", display_name="A", role=Role.VIEWER, password=PASSWORD)
    with pytest.raises(UserExists):
        await create_user(db_session, email="DUP@example.test", display_name="B", role=Role.ADMIN, password=PASSWORD)
    count = await db_session.scalar(select(func.count()).select_from(User).where(User.email == "dup@example.test"))
    assert count == 1


async def test_user_exists_is_a_value_error() -> None:
    assert issubclass(UserExists, ValueError)


async def test_short_password_is_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="at least 12"):
        await create_user(db_session, email="short@example.test", display_name="S", role=Role.VIEWER, password="x" * 11)
    assert await get_user_by_email(db_session, "short@example.test") is None


async def test_authenticate_success_and_failures(db_session: AsyncSession) -> None:
    await create_user(db_session, email="auth@example.test", display_name="A", role=Role.VIEWER, password=PASSWORD)
    user = await authenticate(db_session, email=" AUTH@example.test", password=PASSWORD)
    assert user is not None
    assert user.email == "auth@example.test"
    assert await authenticate(db_session, email="auth@example.test", password="wrong-password-123") is None
    assert await authenticate(db_session, email="nobody@example.test", password=PASSWORD) is None


async def test_authenticate_rejects_inactive_user(db_session: AsyncSession) -> None:
    user = await create_user(
        db_session, email="off@example.test", display_name="Off", role=Role.VIEWER, password=PASSWORD
    )
    user.is_active = False
    await db_session.flush()
    assert await authenticate(db_session, email="off@example.test", password=PASSWORD) is None


async def test_authenticate_rehashes_outdated_hash(db_session: AsyncSession) -> None:
    user = await create_user(
        db_session, email="old@example.test", display_name="Old", role=Role.VIEWER, password=PASSWORD
    )
    weak = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash(PASSWORD)
    user.password_hash = weak
    await db_session.flush()
    assert await authenticate(db_session, email="old@example.test", password=PASSWORD) is not None
    await db_session.refresh(user)
    assert user.password_hash != weak
    assert user.password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")


async def test_set_password(db_session: AsyncSession) -> None:
    user = await create_user(db_session, email="pw@example.test", display_name="P", role=Role.VIEWER, password=PASSWORD)
    with pytest.raises(ValueError, match="at least 12"):
        await set_password(user, "short")
    await set_password(user, "a-brand-new-password")
    await db_session.flush()
    assert await authenticate(db_session, email="pw@example.test", password=PASSWORD) is None
    assert await authenticate(db_session, email="pw@example.test", password="a-brand-new-password") is not None
```

- [ ] **Step 10: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/db/test_users.py -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'mdcopilot_blog.auth.users'`.

- [ ] **Step 11: Implement the user functions**

Create `backend/src/mdcopilot_blog/auth/users.py`:

```python
"""Local user accounts."""

import asyncio
from functools import cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.passwords import hash_password, verify_password
from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Role

MIN_PASSWORD_LENGTH = 12


class UserExists(ValueError):
    """A user with this email already exists."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result: User | None = await db.scalar(select(User).where(User.email == normalize_email(email)))
    return result


async def create_user(db: AsyncSession, *, email: str, display_name: str, role: Role, password: str) -> User:
    """Insert a user and flush (no commit). Raises UserExists or ValueError (short password)."""
    validate_password(password)
    normalized = normalize_email(email)
    if await get_user_by_email(db, normalized) is not None:
        raise UserExists(normalized)
    user = User(
        email=normalized,
        display_name=display_name.strip(),
        role=Role(role).value,
        password_hash=await asyncio.to_thread(hash_password, password),
        is_active=True,
    )
    try:
        # A SAVEPOINT keeps the caller's transaction usable if a concurrent insert wins the race.
        async with db.begin_nested():
            db.add(user)
            await db.flush()
    except IntegrityError as exc:
        raise UserExists(normalized) from exc
    return user


async def set_password(user: User, password: str) -> None:
    """Validate and hash a new password onto the user (the caller flushes/commits)."""
    validate_password(password)
    user.password_hash = await asyncio.to_thread(hash_password, password)


@cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def _dummy_verify(password: str) -> None:
    """Spend the same Argon2 time for unknown emails, so timing does not reveal which emails exist."""
    verify_password(password, _dummy_hash())


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User | None:
    """Return the active user for these credentials, or None. Upgrades an outdated hash in place (flush only)."""
    user = await get_user_by_email(db, email)
    if user is None:
        await asyncio.to_thread(_dummy_verify, password)
        return None
    ok, new_hash = await asyncio.to_thread(verify_password, password, user.password_hash)
    if not ok or not user.is_active:
        return None
    if new_hash is not None:
        user.password_hash = new_hash
        await db.flush()
    return user
```

- [ ] **Step 12: Run the user tests and see them pass**

Run: `docker compose run --rm tools pytest tests/db/test_users.py -q`
Expected: `10 passed`.

- [ ] **Step 13: Write the failing session tests**

Every test injects `now`, so no test sleeps. Create `backend/tests/db/test_sessions.py`:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.sessions import (
    ABSOLUTE_TIMEOUT,
    IDLE_TIMEOUT,
    TOUCH_INTERVAL,
    create_session,
    hash_token,
    resolve_session,
    revoke_session,
    revoke_user_sessions,
)
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.models import User, UserSession
from mdcopilot_blog.domain.enums import Role

T0 = datetime(2026, 9, 17, 6, 0, tzinfo=UTC)


async def _user(db: AsyncSession, email: str = "sess@example.test") -> User:
    return await create_user(db, email=email, display_name="S", role=Role.EDITOR, password="correct-horse-battery")


def test_constants() -> None:
    assert timedelta(minutes=30) == IDLE_TIMEOUT
    assert timedelta(hours=12) == ABSOLUTE_TIMEOUT
    assert timedelta(seconds=60) == TOUCH_INTERVAL


def test_hash_token_is_sha256_hex() -> None:
    assert hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


async def test_create_session_stores_only_the_hash(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip="10.0.0.1", user_agent="pytest", now=T0)
    assert len(token) >= 40
    row = await db_session.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert row is not None
    assert row.token_hash == hash_token(token)
    assert row.token_hash != token
    assert row.expires_at == T0 + ABSOLUTE_TIMEOUT
    assert row.last_seen_at == T0
    assert (row.ip, row.user_agent) == ("10.0.0.1", "pytest")
    assert user.last_login_at == T0


async def test_create_session_truncates_long_client_values(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    await create_session(db_session, user, ip="1" * 100, user_agent="u" * 1000, now=T0)
    row = await db_session.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert row is not None
    assert row.ip is not None
    assert row.user_agent is not None
    assert (len(row.ip), len(row.user_agent)) == (64, 400)


async def test_resolve_returns_user_and_session(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    resolved = await resolve_session(db_session, token, now=T0 + timedelta(seconds=5))
    assert resolved is not None
    assert resolved.user.id == user.id
    assert resolved.session.token_hash == hash_token(token)


async def test_unknown_and_empty_tokens(db_session: AsyncSession) -> None:
    assert await resolve_session(db_session, "no-such-token", now=T0) is None
    assert await resolve_session(db_session, "", now=T0) is None


async def test_idle_expiry(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=29)) is not None
    # The 29-minute resolve touched last_seen_at, so idle time restarts from there.
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=58)) is not None
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=58 + 31)) is None


async def test_absolute_expiry_even_when_active(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    for step in range(1, 29):  # a request every 25 minutes keeps the session from going idle
        assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=25 * step)) is not None
    assert await resolve_session(db_session, token, now=T0 + ABSOLUTE_TIMEOUT - timedelta(seconds=1)) is not None
    assert await resolve_session(db_session, token, now=T0 + ABSOLUTE_TIMEOUT) is None


async def test_touch_is_throttled(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    first = await resolve_session(db_session, token, now=T0 + timedelta(seconds=30))
    assert first is not None
    assert first.session.last_seen_at == T0
    second = await resolve_session(db_session, token, now=T0 + timedelta(seconds=61))
    assert second is not None
    await db_session.refresh(second.session)
    assert second.session.last_seen_at == T0 + timedelta(seconds=61)


async def test_revoke_session(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    other = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    await revoke_session(db_session, token, now=T0 + timedelta(minutes=1))
    assert await resolve_session(db_session, token, now=T0 + timedelta(minutes=2)) is None
    assert await resolve_session(db_session, other, now=T0 + timedelta(minutes=2)) is not None
    row = await db_session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    assert row is not None
    await db_session.refresh(row)
    assert row.revoked_at == T0 + timedelta(minutes=1)


async def test_revoke_user_sessions_keeps_one(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    keep = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    drop_a = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    drop_b = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    later = T0 + timedelta(minutes=1)
    assert await revoke_user_sessions(db_session, user.id, now=later, keep_token=keep) == 2
    assert await resolve_session(db_session, keep, now=later) is not None
    assert await resolve_session(db_session, drop_a, now=later) is None
    assert await resolve_session(db_session, drop_b, now=later) is None
    assert await revoke_user_sessions(db_session, user.id, now=later) == 1


async def test_inactive_user_session_is_rejected(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token = await create_session(db_session, user, ip=None, user_agent=None, now=T0)
    user.is_active = False
    await db_session.flush()
    assert await resolve_session(db_session, token, now=T0 + timedelta(seconds=5)) is None
```

- [ ] **Step 14: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/db/test_sessions.py -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'mdcopilot_blog.auth.sessions'`.

- [ ] **Step 15: Implement sessions**

Create `backend/src/mdcopilot_blog/auth/sessions.py`. `Result.tuples()` is used on purpose: `Row.tuple()` is deprecated in SQLAlchemy 2.0.19+ and emits `SADeprecationWarning`.

```python
"""Database-backed login sessions. Only the SHA-256 of the session token is stored."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import User, UserSession

IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=12)
TOUCH_INTERVAL = timedelta(seconds=60)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class ResolvedSession:
    user: User
    session: UserSession


async def create_session(db: AsyncSession, user: User, *, ip: str | None, user_agent: str | None, now: datetime) -> str:
    """Create a session row and return the raw token (flush only; the caller commits)."""
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            last_seen_at=now,
            expires_at=now + ABSOLUTE_TIMEOUT,
            ip=ip[:64] if ip else None,
            user_agent=user_agent[:400] if user_agent else None,
        )
    )
    user.last_login_at = now
    await db.flush()
    return token


async def resolve_session(db: AsyncSession, token: str, *, now: datetime) -> ResolvedSession | None:
    """Return the live session for a token, or None if unknown, revoked, idle, expired or the user is inactive."""
    if not token:
        return None
    row = (
        (
            await db.execute(
                select(UserSession, User)
                .join(User, User.id == UserSession.user_id)
                .where(UserSession.token_hash == hash_token(token))
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        return None
    session, user = row
    if session.revoked_at is not None:
        return None
    if now >= session.expires_at:
        return None
    if now - session.last_seen_at >= IDLE_TIMEOUT:
        return None
    if not user.is_active:
        return None
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.flush()
    return ResolvedSession(user=user, session=session)


async def revoke_session(db: AsyncSession, token: str, *, now: datetime) -> None:
    """Mark one session revoked (no commit)."""
    await db.execute(
        update(UserSession)
        .where(UserSession.token_hash == hash_token(token), UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_user_sessions(
    db: AsyncSession, user_id: uuid.UUID, *, now: datetime, keep_token: str | None = None
) -> int:
    """Revoke every live session of a user, optionally keeping one (no commit). Returns the count revoked."""
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if keep_token is not None:
        stmt = stmt.where(UserSession.token_hash != hash_token(keep_token))
    result = await db.execute(stmt)
    assert isinstance(result, CursorResult)
    return int(result.rowcount)
```

- [ ] **Step 16: Run the session tests and see them pass**

Run: `docker compose run --rm tools pytest tests/db/test_sessions.py -q`
Expected: `12 passed`, with no warnings.

- [ ] **Step 17: Write the failing rate-limit tests**

Create `backend/tests/db/test_rate_limit.py`:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.rate_limit import (
    MAX_FAILURES_PER_EMAIL,
    MAX_FAILURES_PER_IP,
    WINDOW,
    login_allowed,
    record_login_attempt,
)
from mdcopilot_blog.db.models import LoginAttempt


def _now() -> datetime:
    # created_at comes from Postgres now(), so tests compare against the real clock.
    return datetime.now(UTC)


def test_constants() -> None:
    assert timedelta(minutes=15) == WINDOW
    assert MAX_FAILURES_PER_EMAIL == 5
    assert MAX_FAILURES_PER_IP == 20


async def _fail(db: AsyncSession, email: str, ip: str | None, times: int) -> None:
    for _ in range(times):
        await record_login_attempt(db, email=email, ip=ip, succeeded=False)


async def test_record_login_attempt_normalizes_email(db_session: AsyncSession) -> None:
    await record_login_attempt(db_session, email=" Rate@Example.TEST ", ip="10.0.0.9", succeeded=True)
    row = await db_session.scalar(select(LoginAttempt).where(LoginAttempt.ip == "10.0.0.9"))
    assert row is not None
    assert (row.email, row.succeeded) == ("rate@example.test", True)
    assert row.created_at is not None


async def test_fifth_failure_blocks_the_email(db_session: AsyncSession) -> None:
    await _fail(db_session, "five@example.test", "10.0.0.1", 4)
    assert await login_allowed(db_session, email="five@example.test", ip="10.0.0.1", now=_now()) is True
    await _fail(db_session, "five@example.test", "10.0.0.1", 1)
    assert await login_allowed(db_session, email="FIVE@example.test", ip="10.0.0.2", now=_now()) is False
    assert await login_allowed(db_session, email="other@example.test", ip="10.0.0.1", now=_now()) is True


async def test_successes_do_not_count(db_session: AsyncSession) -> None:
    for _ in range(10):
        await record_login_attempt(db_session, email="ok@example.test", ip="10.0.0.3", succeeded=True)
    assert await login_allowed(db_session, email="ok@example.test", ip="10.0.0.3", now=_now()) is True


async def test_twentieth_failure_blocks_the_ip(db_session: AsyncSession) -> None:
    for i in range(19):
        await record_login_attempt(db_session, email=f"u{i}@example.test", ip="10.0.0.4", succeeded=False)
    assert await login_allowed(db_session, email="fresh@example.test", ip="10.0.0.4", now=_now()) is True
    await record_login_attempt(db_session, email="u19@example.test", ip="10.0.0.4", succeeded=False)
    assert await login_allowed(db_session, email="fresh@example.test", ip="10.0.0.4", now=_now()) is False
    assert await login_allowed(db_session, email="fresh@example.test", ip="10.0.0.5", now=_now()) is True
    assert await login_allowed(db_session, email="fresh@example.test", ip=None, now=_now()) is True


async def test_failures_outside_the_window_are_ignored(db_session: AsyncSession) -> None:
    now = _now()
    db_session.add_all(
        LoginAttempt(email="old@example.test", ip="10.0.0.6", succeeded=False, created_at=now - timedelta(minutes=16))
        for _ in range(5)
    )
    await db_session.flush()
    assert await login_allowed(db_session, email="old@example.test", ip="10.0.0.6", now=now) is True
    db_session.add_all(
        LoginAttempt(email="old@example.test", ip="10.0.0.6", succeeded=False, created_at=now - timedelta(minutes=14))
        for _ in range(5)
    )
    await db_session.flush()
    assert await login_allowed(db_session, email="old@example.test", ip="10.0.0.6", now=now) is False
    # The same rows fall out of the window once time moves on.
    assert await login_allowed(db_session, email="old@example.test", ip="10.0.0.6", now=now + WINDOW) is True
    total = await db_session.scalar(select(func.count()).select_from(LoginAttempt))
    assert total == 10
```

- [ ] **Step 18: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/db/test_rate_limit.py -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'mdcopilot_blog.auth.rate_limit'`.

- [ ] **Step 19: Implement the rate limiter**

Create `backend/src/mdcopilot_blog/auth/rate_limit.py`:

```python
"""Login throttling backed by the login_attempts table."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.users import normalize_email
from mdcopilot_blog.db.models import LoginAttempt

WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_IP = 20


async def _failures(db: AsyncSession, *, since: datetime, email: str | None = None, ip: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.succeeded.is_(False), LoginAttempt.created_at > since)
    )
    if email is not None:
        stmt = stmt.where(LoginAttempt.email == email)
    if ip is not None:
        stmt = stmt.where(LoginAttempt.ip == ip)
    return int(await db.scalar(stmt) or 0)


async def login_allowed(db: AsyncSession, *, email: str, ip: str | None, now: datetime) -> bool:
    """False once an email has 5, or an IP has 20, failed attempts inside the last 15 minutes."""
    since = now - WINDOW
    if await _failures(db, since=since, email=normalize_email(email)) >= MAX_FAILURES_PER_EMAIL:
        return False
    return not (ip is not None and await _failures(db, since=since, ip=ip[:64]) >= MAX_FAILURES_PER_IP)


async def record_login_attempt(db: AsyncSession, *, email: str, ip: str | None, succeeded: bool) -> None:
    """Insert one attempt row (flush only). created_at comes from the database clock."""
    db.add(LoginAttempt(email=normalize_email(email)[:320], ip=ip[:64] if ip else None, succeeded=succeeded))
    await db.flush()
```

- [ ] **Step 20: Run the rate-limit tests and see them pass**

Run: `docker compose run --rm tools pytest tests/db/test_rate_limit.py -q`
Expected: `6 passed`.

- [ ] **Step 21: Write the failing audit tests**

Create `backend/tests/db/test_audit.py`:

```python
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.models import AuditLog
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.services.audit import audit


async def test_audit_writes_one_row(db_session: AsyncSession) -> None:
    actor = await create_user(
        db_session, email="auditor@example.test", display_name="A", role=Role.ADMIN, password="correct-horse-battery"
    )
    target = uuid.uuid4()
    await audit(
        db_session,
        actor_user_id=actor.id,
        action="user.update",
        entity_type="user",
        entity_id=str(target),
        reason="role change requested",
        details={"target": target, "at": datetime(2026, 9, 17, tzinfo=UTC), "cost": Decimal("1.50"), "n": 2},
    )
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "user.update"))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == actor.id
    assert (row.entity_type, row.entity_id, row.reason) == ("user", str(target), "role change requested")
    assert row.details == {"target": str(target), "at": "2026-09-17 00:00:00+00:00", "cost": "1.50", "n": 2}
    assert row.created_at is not None


async def test_audit_defaults(db_session: AsyncSession) -> None:
    await audit(db_session, actor_user_id=None, action="system.check", entity_type="system")
    row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "system.check"))
    assert row is not None
    assert (row.actor_user_id, row.entity_id, row.reason, row.details) == (None, None, None, {})
```

- [ ] **Step 22: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/db/test_audit.py -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'mdcopilot_blog.services'`.

- [ ] **Step 23: Implement the audit writer**

Create `backend/src/mdcopilot_blog/services/__init__.py`:

```python
"""Application services shared by the api, the CLI and the worker."""
```

Create `backend/src/mdcopilot_blog/services/audit.py`:

```python
"""Append-only audit trail (audit_log)."""

import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import AuditLog


def _json_safe(details: Mapping[str, object] | None) -> dict[str, Any]:
    """Round-trip through json so UUIDs, datetimes and Decimals are stored as strings."""
    if not details:
        return {}
    safe: dict[str, Any] = json.loads(json.dumps(dict(details), default=str))
    return safe


async def audit(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    reason: str | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    """Add one audit row and flush. The caller's transaction decides whether it is kept."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            details=_json_safe(details),
        )
    )
    await db.flush()
```

- [ ] **Step 24: Run all Task 7 tests**

Run: `docker compose run --rm tools pytest tests/unit/test_passwords.py tests/unit/test_csrf.py tests/db/test_users.py tests/db/test_sessions.py tests/db/test_rate_limit.py tests/db/test_audit.py -q`
Expected: `54 passed`.

- [ ] **Step 25: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, when Tasks 1–7 have run in order and no later task has:
```text
All checks passed!
53 files already formatted
Success: no issues found in 29 source files
```
- **53** is Task 6's 39 plus this task's 14 `.py` files (8 under `src/`, 6 tests).
- **29** is Task 6's 21 plus this task's 8 modules (`auth/` 6, `services/` 2).
- A lower count means a file from the Files lists is missing.

If `ruff format --check` lists one of this task's files, run `docker compose run --rm tools ruff format <file>` and re-run the check.

- [ ] **Step 26: Checkpoint: list files changed (no git)**

Created:
- `backend/src/mdcopilot_blog/auth/__init__.py`, `passwords.py`, `csrf.py`, `users.py`, `sessions.py`, `rate_limit.py`
- `backend/src/mdcopilot_blog/services/__init__.py`, `audit.py`
- `backend/tests/unit/test_passwords.py`, `backend/tests/unit/test_csrf.py`
- `backend/tests/db/test_users.py`, `test_sessions.py`, `test_rate_limit.py`, `test_audit.py`

---

### Task 8: Seed data and CLI

Adds the idempotent default data (settings v1, brand profile v1, the six content pillars from product spec §9) and the operator CLI: `migrate`, `migrate-dbos`, `seed`, `sync-prompts`, `create-admin` and `create-user`.

Verified in throwaway containers on 2026-09-17:
- 5 seed tests and 12 CLI tests passed, with `-W error`.
- A real `python -m mdcopilot_blog.cli migrate` ran twice against a fresh pgvector database. It created 13 `dbos` tables, then reported `settings_created=False … pillars_created=0` and `0 inserted` on the second run.
- `create-admin` ran twice and was idempotent.
- `uv build --wheel` included `mdcopilot_blog/db/seed_data/*.yaml`.

Minimal stand-ins were used for the Task 3, 6 and 7 modules.

After the review fixes (in-process DBOS migrations, the `tests/db` package marker), the task was re-run against the real Task 1–7 files, on a tree holding exactly the files of Tasks 1–8. Results:
- `pytest tests -q` gave `898 passed`.
- `pytest tests/db -q` gave `61 passed`.
- A real `migrate` ran twice with the output shown in Step 10, and `migrate-dbos` with a wrong password exited 1 without printing the URL or the password.
- Task 3 has since gained a 13th logging test, so `pytest tests -q` on Tasks 1–8 as written gives `899 passed`. The `tests/db` count is unchanged.

**Order.** This task imports Task 6 (`prompts.registry`) and Task 7 (`auth.users`, `services.audit`), so it runs after both: tasks run strictly in order 1–14. Step 0 checks this.

**Files:**
- Create: `backend/src/mdcopilot_blog/db/seed_data/settings.yaml`, `brand_profile.yaml`, `pillars.yaml`
- Create: `backend/src/mdcopilot_blog/db/seed.py`
- Create: `backend/src/mdcopilot_blog/cli.py`
- Test: `backend/tests/db/test_seed.py`, `backend/tests/db/test_cli.py`

**Interfaces:**
- Consumes:
  - T5: the models, `make_engine`, `make_sessionmaker`, and the fixtures `settings`, `engine`, `db_session`; `dbos.run_dbos_database_migrations(system_database_url, *, schema="dbos")` (checked in Task 5 Step 0).
  - T2: `Settings`, `get_settings`, `Settings.database_url()`, `Settings.dbos_system_database_url`, `Settings.log_level`, `Settings.postgres_db`, `Settings.postgres_password`.
  - T3: `configure_logging(level: str) -> None`.
  - T4: `Role` (a `StrEnum`). The CLI looks roles up by value (`Role("admin")`), so it does not depend on the member-name case.
  - T6: `PromptRegistry.from_directory(root) -> PromptRegistry`, `PromptRegistry.sync_to_db(session) -> int`, `PromptRegistryError`, `default_prompt_root() -> Path`, and `backend/prompts/hello/echo.v1.md`.
  - T7: `MIN_PASSWORD_LENGTH`, `UserExists`, `create_user(db, *, email, display_name, role, password) -> User`, `get_user_by_email(db, email) -> User | None`, `normalize_email(email) -> str`, and `services.audit.audit(db, *, actor_user_id, action, entity_type, entity_id=None, reason=None, details=None) -> None`.
- Produces:
  - **`mdcopilot_blog.db.seed`:**
    - `SEED_VERSION = 1`
    - `@dataclass(frozen=True) class SeedReport(settings_created: bool, brand_created: bool, pillars_created: int)`
    - `load_seed_file(name: str) -> dict[str, Any]`
    - `async def seed_defaults(session: AsyncSession) -> SeedReport` (flush only; the caller commits)
  - **`mdcopilot_blog.cli`:**
    - `main(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int`
    - `build_parser() -> argparse.ArgumentParser`
    - `alembic_upgrade(settings) -> int`, `migrate_dbos(settings) -> int`, `seed(settings) -> int`, `sync_prompts(settings) -> int`, `migrate(settings) -> int`
    - `create_account(settings, *, email: str, display_name: str, role: Role, password_env: str) -> int`
    - exit codes `EXIT_OK = 0`, `EXIT_FAILED = 1`, `EXIT_USAGE = 2`
    - entry point `python -m mdcopilot_blog.cli <command>`

Behaviour notes:
- **Injected settings.** `main(..., settings=...)` uses the given settings (tests pass the test database) and leaves logging alone. Without it, `main` loads `get_settings()` and calls `configure_logging`.
- **`migrate` order.** `migrate` runs `alembic_upgrade` (with `Config("alembic.ini")`, relative to `/app`), `migrate_dbos`, `seed` and `sync_prompts` in that order, and stops at the first non-zero result.
- **`migrate-dbos` runs in-process (contract deviation).** The contract's form is `subprocess.run(["dbos","migrate","-s", url, ...])`, which puts the rendered URL, password included, in the child process's argv, where `ps` can read it. `migrate-dbos` instead calls `dbos.run_dbos_database_migrations(settings.dbos_system_database_url, schema="dbos")`, the function `dbos migrate` itself runs (see Task 5's decisions). Checked in the container against dbos 3.0.0:
  - **Logging.** The function logs the URL, with the password masked, at INFO on the `dbos` logger. `migrate-dbos` raises that logger to WARNING for the call and restores it afterwards, so the command's JSON log output never contains `postgresql`.
  - **Failure.** The function prints `DBOS migrations failed: <cause>` to stdout, then raises `click.exceptions.Exit(1)`, a `RuntimeError`. `migrate-dbos` captures stdout, replaces the URL and the password with `***`, prints `migrate-dbos: DBOS migrations failed: <cause>` to stderr and exits 1. It catches `RuntimeError`, because ruff 0.16.8 rejects a blind `except Exception` (BLE001), and so does not import `click` itself.
- **Account creation.**
  - `create-admin` and `create-user` read the password from the named environment variable. A missing password, one shorter than 12 characters, or an email without `@` exits 2.
  - An existing email prints `user <email> already exists; nothing changed` and exits 0.
  - A new account also writes an `audit_log` row (`action="user.create"`, `actor_user_id=None`, `details={"role", "via": "cli"}`).
- **Seed content.** Pillar names and topic lists are copied verbatim from product spec §9, and tone and "avoid" come from §18. The spec names the brand fields (§51) but gives no text for description, target audience, mission, CTA or the pillar descriptions. Those are drafted from spec §7–§8 wording for the owner to review; they are editable settings.

- [ ] **Step 0: Check that Tasks 6 and 7 are in place**

Run from `mdcopilot-blog/`:
```bash
ls backend/src/mdcopilot_blog/prompts/registry.py backend/prompts/hello/echo.v1.md \
   backend/src/mdcopilot_blog/auth/users.py backend/src/mdcopilot_blog/services/audit.py
```

Expected: the four paths are printed with no error.

Decision rule:
- **All four printed:** continue with Step 1.
- **`ls` reports `No such file or directory` for a `prompts/` path:** stop and finish Task 6 first.
- **`ls` reports it for `auth/users.py` or `services/audit.py`:** stop and finish Task 7 first.

Without those files, `cli.py` fails at import and `tests/db/test_cli.py` fails at collection.

- [ ] **Step 1: Write the failing seed test**

Create `backend/tests/db/test_seed.py`:

```python
"""seed_defaults: inserts the spec defaults once and never duplicates them."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogSetting, BrandProfile, ContentPillar
from mdcopilot_blog.db.seed import SeedReport, load_seed_file, seed_defaults

PILLAR_A_TOPICS = [
    "specialist shortages",
    "wait times",
    "regional disparities",
    "referral bottlenecks",
    "specialist access",
    "scaling specialist expertise",
    "underserved populations",
]


async def _count(session: AsyncSession, model: type[BlogSetting | BrandProfile | ContentPillar]) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)


async def test_seed_defaults_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_defaults(db_session)
    second = await seed_defaults(db_session)

    assert first == SeedReport(settings_created=True, brand_created=True, pillars_created=6)
    assert second == SeedReport(settings_created=False, brand_created=False, pillars_created=0)
    assert await _count(db_session, BlogSetting) == 1
    assert await _count(db_session, BrandProfile) == 1
    assert await _count(db_session, ContentPillar) == 6


async def test_seeded_versions_are_active_version_one(db_session: AsyncSession) -> None:
    await seed_defaults(db_session)
    setting = await db_session.scalar(select(BlogSetting))
    brand = await db_session.scalar(select(BrandProfile))
    assert setting is not None
    assert brand is not None
    assert (setting.version, setting.is_active) == (1, True)
    assert (brand.version, brand.is_active) == (1, True)
    assert setting.values["schedule"] == {"time": "07:00", "timezone": "Asia/Kolkata"}
    assert setting.values["gate_override_policy"] == "admin_with_reason"
    assert abs(sum(setting.values["score_weights"].values()) - 1.0) < 1e-9
    assert brand.profile["narrative"] == "an amplifier of specialist leverage, not a replacement for physicians"
    assert brand.profile["ai_disclosure"] == (
        "This article was researched and drafted with AI assistance and reviewed by the MDCopilot team."
    )
    assert "AI is transforming healthcare" in brand.profile["prohibited_language"]
    assert brand.profile["target_word_count"] == {"min": 850, "max": 1150}
    assert brand.profile["website"] == "https://www.mdcopilot.health"


async def test_pillars_follow_spec_rotation(db_session: AsyncSession) -> None:
    await seed_defaults(db_session)
    pillars = (await db_session.scalars(select(ContentPillar).order_by(ContentPillar.sort_order))).all()

    assert [(p.key, p.weekdays) for p in pillars] == [
        ("A", [0]),
        ("B", [1]),
        ("C", [2]),
        ("D", [3]),
        ("E", [4]),
        ("NARRATIVE", [5, 6]),
    ]
    assert [p.name for p in pillars] == [
        "Specialist Scarcity & Access",
        "Cognitive Architecture & Physician Reasoning",
        "Burnout & Administrative Overload",
        "The Agentic Shift",
        "Governance & Clinical Autonomy",
        "Narrative Edition",
    ]
    assert pillars[0].topics == PILLAR_A_TOPICS
    assert "deterministic guardrails" in pillars[4].topics
    assert "Clinic of 2030" in pillars[5].topics
    assert all(p.is_active and p.description for p in pillars)


async def test_seed_restores_only_missing_pillars(db_session: AsyncSession) -> None:
    await seed_defaults(db_session)
    edited = await db_session.scalar(select(ContentPillar).where(ContentPillar.key == "A"))
    assert edited is not None
    edited.name = "Edited by an admin"
    await db_session.execute(delete(ContentPillar).where(ContentPillar.key == "C"))
    await db_session.flush()

    report = await seed_defaults(db_session)

    assert report == SeedReport(settings_created=False, brand_created=False, pillars_created=1)
    names = dict((await db_session.execute(select(ContentPillar.key, ContentPillar.name))).tuples().all())
    assert names["A"] == "Edited by an admin"
    assert names["C"] == "Burnout & Administrative Overload"


def test_seed_files_are_package_data() -> None:
    assert len(load_seed_file("pillars.yaml")["pillars"]) == 6
    assert load_seed_file("brand_profile.yaml")["name"] == "MDCopilot"
    assert set(load_seed_file("settings.yaml")) == {
        "schedule",
        "novelty_threshold",
        "score_weights",
        "gate_override_policy",
    }
```

- [ ] **Step 2: Run the test to see it fail**

Run: `docker compose run --rm tools pytest tests/db/test_seed.py -q`

Expected: `1 error` during collection, with `E   ModuleNotFoundError: No module named 'mdcopilot_blog.db.seed'`.

- [ ] **Step 3: Write the seed data files**

Create `backend/src/mdcopilot_blog/db/seed_data/settings.yaml`:

```yaml
# Default blog_settings v1 (seeded once by `python -m mdcopilot_blog.cli seed`).
# Editable later in Settings; each save creates a new version.
schedule:
  time: "07:00"
  timezone: Asia/Kolkata
novelty_threshold: 0.85
# Topic scoring weights (ARCHITECTURE section 9); they sum to 1.0
score_weights:
  timeliness: 0.25
  novelty: 0.20
  evidence: 0.20
  mdcopilot_relevance: 0.15
  audience: 0.10
  editorial: 0.10
# Who may approve a version whose quality gates failed (owner decision pending, ARCHITECTURE 24.2)
gate_override_policy: admin_with_reason
```

Create `backend/src/mdcopilot_blog/db/seed_data/brand_profile.yaml`:

```yaml
# Default brand profile v1, from product spec sections 7, 8, 17, 18 and 51.
# Editable later in Settings (the Gemini content-strategy conversation will refine it).
name: MDCopilot
description: >-
  Thought leadership at the intersection of healthcare, AI, physicians, specialist access,
  clinical operations and agentic AI.
target_audience: >-
  Specialist physicians, clinical leaders and healthcare operations teams evaluating how AI can
  support clinical work.
mission: >-
  Show how AI can amplify specialist expertise, with physicians in control, through specific,
  evidence-backed and differentiated analysis.
narrative: an amplifier of specialist leverage, not a replacement for physicians
focus_areas:
  - healthcare AI
  - specialist physicians
  - digital twins
  - physician reasoning
  - specialist scarcity
  - specialist access
  - physician burnout
  - administrative overload
  - agentic healthcare
  - clinical AI governance
  - human-in-the-loop AI
  - clinical workflow automation
  - AI augmentation
emphasis:
  - clinical reasoning
  - specialist expertise
  - personalized workflows
  - responsible AI
  - human oversight
  - practical healthcare operations
tone:
  - authoritative
  - clinically grounded
  - intellectually sharp
  - pragmatic
  - empathetic
  - evidence-driven
avoid:
  - excessive adjectives
  - generic AI language
  - fake urgency
  - exaggerated claims
  - unsupported statistics
  - fabricated anecdotes
  - fabricated quotes
  - fabricated physician experiences
# Quality gate 10 fails when any of these phrases appears (case-insensitive match is decided in Phase 5)
prohibited_language:
  - AI is transforming healthcare
  - revolutionize
  - revolutionizing
  - game-changer
  - game changer
  - in today's fast-paced world
  - unlock the power of
cta: Learn how MDCopilot supports specialist physicians at www.mdcopilot.health.
website: https://www.mdcopilot.health
target_word_count:
  min: 850
  max: 1150
# Required (quality gate 15); appended to every rendered article
ai_disclosure: This article was researched and drafted with AI assistance and reviewed by the MDCopilot team.
```

Create `backend/src/mdcopilot_blog/db/seed_data/pillars.yaml`:

```yaml
# Content pillars from product spec section 9. weekdays: 0 = Monday ... 6 = Sunday.
# Default rotation: Mon-Fri pillars A-E, Sat-Sun the Narrative Edition. Editable later in Settings.
pillars:
  - key: A
    name: Specialist Scarcity & Access
    description: >-
      Why patients wait for specialist care and how specialist expertise can reach more of them:
      shortages, wait times, regional gaps, referral bottlenecks and underserved populations.
    weekdays: [0]
    topics:
      - specialist shortages
      - wait times
      - regional disparities
      - referral bottlenecks
      - specialist access
      - scaling specialist expertise
      - underserved populations
  - key: B
    name: Cognitive Architecture & Physician Reasoning
    description: >-
      How specialists actually reason (heuristics, edge cases, individual practice styles, decision
      pathways), where generic LLMs fall short, and how AI can augment that reasoning.
    weekdays: [1]
    topics:
      - clinical heuristics
      - specialist reasoning
      - edge cases
      - individualized practice styles
      - clinical decision pathways
      - limitations of generic LLMs
      - reasoning augmentation
  - key: C
    name: Burnout & Administrative Overload
    description: >-
      The administrative load on physicians: inbox and portal messages, phone intake, asynchronous
      consultations, after-hours "pajama time" and the cognitive fatigue that follows.
    weekdays: [2]
    topics:
      - inbox overload
      - pajama time
      - asynchronous consultations
      - phone intake
      - portal messages
      - administrative burden
      - cognitive fatigue
  - key: D
    name: The Agentic Shift
    description: >-
      The move from passive AI tools to active agents: agentic workflows, digital twins, copilots,
      ambient scribes and multi-agent systems in healthcare.
    weekdays: [3]
    topics:
      - AI agents
      - agentic workflows
      - digital twins
      - AI copilots
      - ambient scribes
      - active vs passive AI
      - multi-agent healthcare systems
  - key: E
    name: Governance & Clinical Autonomy
    description: >-
      Keeping clinicians in control: human-in-the-loop design, oversight, safety, liability,
      transparency, deterministic guardrails and clinical autonomy.
    weekdays: [4]
    topics:
      - human-in-the-loop
      - clinical oversight
      - AI safety
      - governance
      - liability
      - transparency
      - deterministic guardrails
      - clinical autonomy
  - key: NARRATIVE
    name: Narrative Edition
    description: >-
      Weekend edition: forward-looking narrative pieces about the future specialist practice.
      Vignettes must be sourced or clearly framed as hypothetical; never an invented first-person
      clinician experience.
    weekdays: [5, 6]
    topics:
      - case vignette
      - future clinic
      - Clinic of 2030
      - physician + digital twin workflows
      - future specialist practice
```

- [ ] **Step 4: Write `seed_defaults`**

Create `backend/src/mdcopilot_blog/db/seed.py`. `seed_data/` is not a Python package; `importlib.resources.files("mdcopilot_blog.db") / "seed_data" / name` reads it in both the editable dev install and a built wheel.

```python
"""Idempotent default data: settings v1, brand profile v1 and the six content pillars.

The YAML files in ``db/seed_data/`` are package data, read with ``importlib.resources``.
``seed_defaults`` only flushes; the caller commits.
"""

from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogSetting, BrandProfile, ContentPillar

SEED_VERSION = 1


@dataclass(frozen=True)
class SeedReport:
    settings_created: bool
    brand_created: bool
    pillars_created: int


def load_seed_file(name: str) -> dict[str, Any]:
    raw = (resources.files("mdcopilot_blog.db") / "seed_data" / name).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = f"seed file {name} must contain a mapping"
        raise TypeError(msg)
    return data


async def seed_defaults(session: AsyncSession) -> SeedReport:
    """Insert whatever is missing. Existing rows (including edited ones) are never touched."""
    settings_created = False
    if await session.scalar(select(BlogSetting.id).limit(1)) is None:
        session.add(BlogSetting(version=SEED_VERSION, values=load_seed_file("settings.yaml"), is_active=True))
        settings_created = True

    brand_created = False
    if await session.scalar(select(BrandProfile.id).limit(1)) is None:
        session.add(BrandProfile(version=SEED_VERSION, profile=load_seed_file("brand_profile.yaml"), is_active=True))
        brand_created = True

    existing_keys = set((await session.scalars(select(ContentPillar.key))).all())
    pillars_created = 0
    for position, item in enumerate(load_seed_file("pillars.yaml")["pillars"]):
        key = str(item["key"])
        if key in existing_keys:
            continue
        session.add(
            ContentPillar(
                key=key,
                name=str(item["name"]),
                description=str(item["description"]),
                topics=[str(topic) for topic in item["topics"]],
                weekdays=[int(day) for day in item["weekdays"]],
                is_active=True,
                sort_order=position,
            )
        )
        pillars_created += 1

    await session.flush()
    return SeedReport(settings_created=settings_created, brand_created=brand_created, pillars_created=pillars_created)
```

- [ ] **Step 5: Run the seed tests to see them pass**

Run: `docker compose run --rm tools pytest tests/db/test_seed.py -q`

Expected: `5 passed`

- [ ] **Step 6: Write the failing CLI test**

Create `backend/tests/db/test_cli.py`.
- Tests that touch the database are async and call `cli.main` through `asyncio.to_thread`: `main()` uses `asyncio.run()`, which is allowed in a worker thread but not inside the pytest loop.
- `migrate` and `migrate-dbos` are tested without real Alembic or DBOS migrations, by monkeypatching `cli.run_dbos_database_migrations`, `alembic.command.upgrade` and the step functions. The fake for `run_dbos_database_migrations` copies dbos 3.0.0: an INFO log line with a masked URL on success, and on failure a `DBOS migrations failed: …` line on stdout followed by `click.exceptions.Exit(code=1)`. `click` is installed as a dbos dependency.
- The `cli_tables` fixture truncates the tables the CLI commits to, before and after each test.

```python
"""CLI commands, called in-process through main(argv, settings=...) against the test database."""

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

import click
import pytest
import pytest_asyncio
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog import cli
from mdcopilot_blog.db.models import AuditLog, ContentPillar, PromptVersion, User
from mdcopilot_blog.settings import Settings

PASSWORD_ENV = "MDCB_TEST_CLI_PASSWORD"
LEAK_CANARY = "pw-canary-must-not-leak-7f3a"
TRUNCATE_CLI_SQL = (
    "TRUNCATE app.blog_content_pillars, app.blog_settings, app.blog_brand_profiles, "
    "app.blog_prompt_versions, app.audit_log, app.users RESTART IDENTITY CASCADE"
)


@pytest_asyncio.fixture(loop_scope="session")
async def cli_tables(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """The CLI commits for real, so empty its tables before and after each test."""
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_CLI_SQL))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_CLI_SQL))


async def run_cli(argv: Sequence[str], settings: Settings) -> int:
    # main() calls asyncio.run(); a worker thread has no running loop, so that is allowed there
    return await asyncio.to_thread(cli.main, list(argv), settings=settings)


async def test_seed_command_prints_report_and_is_idempotent(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run_cli(["seed"], settings) == 0
    assert "seed: settings_created=True brand_created=True pillars_created=6" in capsys.readouterr().out

    assert await run_cli(["seed"], settings) == 0
    assert "seed: settings_created=False brand_created=False pillars_created=0" in capsys.readouterr().out

    async with cli_tables() as db:
        assert await db.scalar(select(func.count()).select_from(ContentPillar)) == 6


async def test_sync_prompts_command_registers_prompt_files_once(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run_cli(["sync-prompts"], settings) == 0
    first = capsys.readouterr().out
    assert await run_cli(["sync-prompts"], settings) == 0
    assert "sync-prompts: 0 inserted" in capsys.readouterr().out

    async with cli_tables() as db:
        names = (await db.scalars(select(PromptVersion.name))).all()
    assert "hello/echo" in names
    assert f"sync-prompts: {len(names)} inserted" in first


async def test_create_admin_creates_admin_from_env_password(
    cli_tables: async_sessionmaker[AsyncSession],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "correct-horse-battery")
    argv = [
        "create-admin",
        "--email",
        " Admin@Example.TEST ",
        "--display-name",
        "Admin",
        "--password-env",
        PASSWORD_ENV,
    ]

    assert await run_cli(argv, settings) == 0
    out = capsys.readouterr().out
    assert "created admin admin@example.test" in out
    assert "correct-horse-battery" not in out

    async with cli_tables() as db:
        user = await db.scalar(select(User))
        actions = (await db.scalars(select(AuditLog.action))).all()
    assert user is not None
    assert (user.email, user.display_name, user.role, user.is_active) == ("admin@example.test", "Admin", "admin", True)
    assert user.password_hash.startswith("$argon2id$")
    assert actions == ["user.create"]


async def test_create_admin_twice_changes_nothing(
    cli_tables: async_sessionmaker[AsyncSession],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "correct-horse-battery")
    argv = ["create-admin", "--email", "admin@example.test", "--display-name", "Admin", "--password-env", PASSWORD_ENV]
    assert await run_cli(argv, settings) == 0
    monkeypatch.setenv(PASSWORD_ENV, "a-different-password-123")

    assert await run_cli(argv, settings) == 0
    assert "user admin@example.test already exists; nothing changed" in capsys.readouterr().out

    async with cli_tables() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1
        assert await db.scalar(select(func.count()).select_from(AuditLog)) == 1


async def test_create_admin_uses_bootstrap_password_variable_by_default(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password-123")
    assert await run_cli(["create-admin", "--email", "boot@example.test", "--display-name", "Boot"], settings) == 0
    async with cli_tables() as db:
        assert await db.scalar(select(User.role).where(User.email == "boot@example.test")) == "admin"


async def test_create_admin_refuses_bad_password_or_email(
    cli_tables: async_sessionmaker[AsyncSession],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["create-admin", "--email", "a@example.test", "--display-name", "A", "--password-env", PASSWORD_ENV]
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    assert await run_cli(argv, settings) == 2
    assert f"{PASSWORD_ENV} is not set" in capsys.readouterr().err

    monkeypatch.setenv(PASSWORD_ENV, "short")
    assert await run_cli(argv, settings) == 2
    assert "shorter than 12 characters" in capsys.readouterr().err

    monkeypatch.setenv(PASSWORD_ENV, "correct-horse-battery")
    blank_email = ["create-admin", "--email", "", "--display-name", "A", "--password-env", PASSWORD_ENV]
    assert await run_cli(blank_email, settings) == 2
    assert "--email must be an email address" in capsys.readouterr().err

    async with cli_tables() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_create_user_sets_the_requested_role(
    cli_tables: async_sessionmaker[AsyncSession], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "reviewer-password-123")
    argv = [
        "create-user",
        "--email",
        "rev@example.test",
        "--display-name",
        "Rev",
        "--role",
        "reviewer",
        "--password-env",
        PASSWORD_ENV,
    ]
    assert await run_cli(argv, settings) == 0
    async with cli_tables() as db:
        assert await db.scalar(select(User.role).where(User.email == "rev@example.test")) == "reviewer"


def test_create_user_rejects_unknown_role(settings: Settings) -> None:
    argv = ["create-user", "--email", "x@example.test", "--display-name", "X", "--role", "owner"]
    with pytest.raises(SystemExit) as excinfo:
        cli.main([*argv, "--password-env", PASSWORD_ENV], settings=settings)
    assert excinfo.value.code == 2


def _canary_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"postgres_password": SecretStr(LEAK_CANARY)})


def test_migrate_dbos_runs_in_process_and_never_prints_the_url(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    canary = _canary_settings(settings)
    calls: list[tuple[str, dict[str, Any]]] = []
    dbos_level_before = logging.getLogger("dbos").level

    def fake_migrations(system_database_url: str, **kwargs: Any) -> None:
        calls.append((system_database_url, kwargs))
        # dbos 3.0.0 logs this at INFO, with the password masked
        logging.getLogger("dbos").info("Initializing DBOS system database with URL: postgresql+psycopg://u:***@db/x")

    monkeypatch.setattr(cli, "run_dbos_database_migrations", fake_migrations)
    caplog.set_level(logging.INFO)

    assert cli.main(["migrate-dbos"], settings=canary) == 0

    assert calls == [(canary.dbos_system_database_url, {"schema": "dbos"})]
    assert LEAK_CANARY in calls[0][0]
    captured = capsys.readouterr()
    assert "migrate-dbos: DBOS system tables are up to date (schema dbos)" in captured.out
    assert LEAK_CANARY not in captured.out + captured.err + caplog.text
    assert "postgresql" not in captured.out + captured.err + caplog.text
    assert logging.getLogger("dbos").level == dbos_level_before


def test_migrate_dbos_failure_prints_the_redacted_cause(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing_migrations(system_database_url: str, **kwargs: Any) -> None:
        # dbos 3.0.0 echoes the cause to stdout, then raises click.exceptions.Exit(code=1)
        print(f"DBOS migrations failed: cannot use {system_database_url} ({LEAK_CANARY})")
        raise click.exceptions.Exit(code=1)

    monkeypatch.setattr(cli, "run_dbos_database_migrations", failing_migrations)

    assert cli.main(["migrate-dbos"], settings=_canary_settings(settings)) == 1
    captured = capsys.readouterr()
    assert "migrate-dbos: DBOS migrations failed: cannot use *** (***)" in captured.err
    assert LEAK_CANARY not in captured.out + captured.err
    assert "postgresql" not in captured.out + captured.err


def test_migrate_runs_alembic_then_dbos_seed_and_prompts(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def fake_upgrade(cfg: Config, revision: str) -> None:
        assert revision == "head"
        assert cfg.config_file_name == "alembic.ini"
        assert cfg.attributes["database_url"].database == settings.postgres_db
        assert cfg.attributes["configure_logger"] is False
        order.append("alembic")

    def step(name: str) -> Any:
        def _run(passed: Settings) -> int:
            assert passed is settings
            order.append(name)
            return 0

        return _run

    monkeypatch.setattr(cli.command, "upgrade", fake_upgrade)
    monkeypatch.setattr(cli, "migrate_dbos", step("dbos"))
    monkeypatch.setattr(cli, "seed", step("seed"))
    monkeypatch.setattr(cli, "sync_prompts", step("prompts"))

    assert cli.main(["migrate"], settings=settings) == 0
    assert order == ["alembic", "dbos", "seed", "prompts"]


def test_migrate_stops_at_the_first_failing_step(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    monkeypatch.setattr(cli.command, "upgrade", lambda cfg, revision: order.append("alembic"))
    monkeypatch.setattr(cli, "migrate_dbos", lambda s: order.append("dbos") or 1)
    monkeypatch.setattr(cli, "seed", lambda s: order.append("seed") or 0)
    monkeypatch.setattr(cli, "sync_prompts", lambda s: order.append("prompts") or 0)

    assert cli.main(["migrate"], settings=settings) == 1
    assert order == ["alembic", "dbos"]
```

- [ ] **Step 7: Run the test to see it fail**

Run: `docker compose run --rm tools pytest tests/db/test_cli.py -q`

Expected: `1 error` during collection, with `E   ImportError: cannot import name 'cli' from 'mdcopilot_blog' (/app/src/mdcopilot_blog/__init__.py)`.

- [ ] **Step 8: Write the CLI**

Create `backend/src/mdcopilot_blog/cli.py`:

```python
"""Operator commands: ``python -m mdcopilot_blog.cli <command>``.

Commands: migrate, migrate-dbos, seed, sync-prompts, create-admin, create-user.
Passwords are read from an environment variable, never from the command line.
"""

import argparse
import asyncio
import io
import logging
import os
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, redirect_stdout

from alembic import command
from alembic.config import Config
from dbos import run_dbos_database_migrations
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.users import (
    MIN_PASSWORD_LENGTH,
    UserExists,
    create_user,
    get_user_by_email,
    normalize_email,
)
from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.db.seed import SeedReport, seed_defaults
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.prompts.registry import PromptRegistry, PromptRegistryError, default_prompt_root
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.settings import Settings, get_settings

ALEMBIC_INI = "alembic.ini"  # relative to the working directory (/app in every backend container)
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


@asynccontextmanager
async def _session(settings: Settings) -> AsyncIterator[AsyncSession]:
    engine = make_engine(settings.database_url())
    try:
        async with make_sessionmaker(engine)() as session:
            yield session
    finally:
        await engine.dispose()


def alembic_upgrade(settings: Settings) -> int:
    cfg = Config(ALEMBIC_INI)
    cfg.attributes["database_url"] = settings.database_url()
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    print("migrate: alembic upgrade head done")
    return EXIT_OK


def _redact(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def migrate_dbos(settings: Settings) -> int:
    """Create or upgrade the DBOS system tables in-process (what ``dbos migrate`` runs).

    In-process, so the password never sits in a child process's argv, where ``ps`` could read it.
    """
    url = settings.dbos_system_database_url
    dbos_logger = logging.getLogger("dbos")
    previous_level = dbos_logger.level
    dbos_logger.setLevel(logging.WARNING)  # dbos logs the (masked) URL at INFO; keep URLs out of our output
    captured = io.StringIO()
    try:
        with redirect_stdout(captured):  # dbos echoes a failure's cause to stdout
            run_dbos_database_migrations(url, schema="dbos")
    except RuntimeError:  # dbos echoes the cause, then raises click.exceptions.Exit(1), a RuntimeError
        detail = _redact(captured.getvalue().strip(), url, settings.postgres_password.get_secret_value())
        print(f"migrate-dbos: {detail or 'DBOS migrations failed'}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        dbos_logger.setLevel(previous_level)
    print("migrate-dbos: DBOS system tables are up to date (schema dbos)")
    return EXIT_OK


async def _seed(settings: Settings) -> SeedReport:
    async with _session(settings) as db:
        report = await seed_defaults(db)
        await db.commit()
    return report


def seed(settings: Settings) -> int:
    report = asyncio.run(_seed(settings))
    print(
        f"seed: settings_created={report.settings_created} brand_created={report.brand_created} "
        f"pillars_created={report.pillars_created}"
    )
    return EXIT_OK


async def _sync_prompts(settings: Settings) -> int:
    registry = PromptRegistry.from_directory(default_prompt_root())
    async with _session(settings) as db:
        inserted = await registry.sync_to_db(db)
        await db.commit()
    return inserted


def sync_prompts(settings: Settings) -> int:
    try:
        inserted = asyncio.run(_sync_prompts(settings))
    except PromptRegistryError as exc:
        print(f"sync-prompts: {exc}", file=sys.stderr)
        return EXIT_FAILED
    print(f"sync-prompts: {inserted} inserted")
    return EXIT_OK


def migrate(settings: Settings) -> int:
    for step in (alembic_upgrade, migrate_dbos, seed, sync_prompts):
        code = step(settings)
        if code != EXIT_OK:
            return code
    return EXIT_OK


async def _create_account(
    settings: Settings, *, email: str, display_name: str, role: Role, password: str
) -> tuple[bool, str]:
    """Return (created, stored email). An existing account is never modified."""
    normalized = normalize_email(email)
    async with _session(settings) as db:
        if await get_user_by_email(db, normalized) is not None:
            return False, normalized
        try:
            user = await create_user(db, email=normalized, display_name=display_name, role=role, password=password)
        except UserExists:
            await db.rollback()
            return False, normalized
        await db.flush()
        await audit(
            db,
            actor_user_id=None,
            action="user.create",
            entity_type="user",
            entity_id=str(user.id),
            details={"role": role.value, "via": "cli"},
        )
        await db.commit()
        return True, user.email


def create_account(settings: Settings, *, email: str, display_name: str, role: Role, password_env: str) -> int:
    if "@" not in email:
        print(f"--email must be an email address, got {email!r}", file=sys.stderr)
        return EXIT_USAGE
    password = os.environ.get(password_env, "")
    if not password:
        print(f"{password_env} is not set; put the password in that environment variable", file=sys.stderr)
        return EXIT_USAGE
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"the password in {password_env} is shorter than {MIN_PASSWORD_LENGTH} characters", file=sys.stderr)
        return EXIT_USAGE
    created, stored_email = asyncio.run(
        _create_account(settings, email=email, display_name=display_name, role=role, password=password)
    )
    if created:
        print(f"created {role.value} {stored_email}")
    else:
        print(f"user {stored_email} already exists; nothing changed")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mdcopilot_blog.cli", description="mdcopilot-blog operator commands"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="alembic upgrade head, then migrate-dbos, seed and sync-prompts")
    sub.add_parser("migrate-dbos", help="create or upgrade the DBOS system tables (schema dbos)")
    sub.add_parser("seed", help="insert default settings, brand profile and content pillars (idempotent)")
    sub.add_parser("sync-prompts", help="register prompt files in blog_prompt_versions")

    admin = sub.add_parser("create-admin", help="create an admin account; no change if the email exists")
    admin.add_argument("--email", required=True)
    admin.add_argument("--display-name", required=True)
    admin.add_argument("--password-env", default="BOOTSTRAP_ADMIN_PASSWORD", metavar="VAR")

    user = sub.add_parser("create-user", help="create an account with a role; no change if the email exists")
    user.add_argument("--email", required=True)
    user.add_argument("--display-name", required=True)
    user.add_argument("--role", required=True, choices=[role.value for role in Role])
    user.add_argument("--password-env", required=True, metavar="VAR")
    return parser


def main(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int:
    """Run one command. Tests pass ``settings`` (the test database); then logging is left alone."""
    args = build_parser().parse_args(argv)
    if settings is None:
        settings = get_settings()
        configure_logging(settings.log_level)

    name: str = args.command
    if name == "migrate":
        return migrate(settings)
    if name == "migrate-dbos":
        return migrate_dbos(settings)
    if name == "seed":
        return seed(settings)
    if name == "sync-prompts":
        return sync_prompts(settings)
    role = Role.ADMIN if name == "create-admin" else Role(args.role)
    return create_account(
        settings, email=args.email, display_name=args.display_name, role=role, password_env=args.password_env
    )


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 9: Run the CLI tests to see them pass**

Run: `docker compose run --rm tools pytest tests/db/test_cli.py -q`

Expected: `12 passed`

- [ ] **Step 10: Smoke-test the CLI against the development database**

Run: `docker compose run --rm tools python -m mdcopilot_blog.cli --help`

Expected: the usage line `python -m mdcopilot_blog.cli [-h] {migrate,migrate-dbos,seed,sync-prompts,create-admin,create-user} ...` and one help line per command.

Run: `docker compose run --rm tools python -m mdcopilot_blog.cli migrate`, then run the same command a second time.

Expected: each run exits 0. Alembic's INFO lines come out as JSON log lines, and the command prints:
- **first run:**
  ```
  migrate: alembic upgrade head done
  migrate-dbos: DBOS system tables are up to date (schema dbos)
  seed: settings_created=True brand_created=True pillars_created=6
  sync-prompts: 1 inserted
  ```
- **second run:** the same, except `seed: settings_created=False brand_created=False pillars_created=0` and `sync-prompts: 0 inserted`.

Neither run prints `postgresql` or the database password. Alembic's JSON line `Context impl PostgresqlImpl.` is expected; it has a capital `P` and holds no URL.

Run: `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select table_schema, count(*) from information_schema.tables group by 1 order by 1"'`

Expected: the output includes `app|14` and `dbos|13`.

Do not create accounts in this smoke test. Once the full stack is up, Task 14 creates the bootstrap admin inside the running `api` container. This is the one form used everywhere in the plan and docs:
```bash
docker compose exec api sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'
```
The single quotes make the container expand the variable from `.env`, so the host never reads `.env`. `exec` reuses the running container; `run` would start a second `api` container and re-run the `migrate` dependency.

- [ ] **Step 11: Run the database test folder**

Run: `docker compose run --rm tools pytest tests/db -q`

Expected, when Tasks 1–8 have run in order and no later task has: `61 passed`. By file:

| File | Task | Tests |
|---|---|---|
| `test_migrations.py` | 5 | 11 |
| `test_seed.py` | 8 | 5 |
| `test_cli.py` | 8 | 12 |
| `test_prompt_sync.py` | 6 | 3 |
| `test_users.py` | 7 | 10 |
| `test_sessions.py` | 7 | 12 |
| `test_rate_limit.py` | 7 | 6 |
| `test_audit.py` | 7 | 2 |

- [ ] **Step 12: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, when Tasks 1–8 have run in order and no later task has:
```
All checks passed!
57 files already formatted
Success: no issues found in 31 source files
```
- **57** is 56 `.py` files under `backend/` plus `backend/prompts/hello/echo.v1.md`, because ruff 0.16.8 also formats `*.md` files by default. The 56 are Task 5's 34, Task 6's 4, Task 7's 14 and this task's 4.
- **31** is the number of modules under `src/`: Task 5's 19, Task 6's 2, Task 7's 8 and this task's 2 (`db/seed.py`, `cli.py`).
- A lower count means a file from the Files lists is missing.

- [ ] **Step 13: Checkpoint: list the files changed in this task (no git)**

Files changed:
- `backend/src/mdcopilot_blog/db/seed_data/settings.yaml`, `brand_profile.yaml`, `pillars.yaml`
- `backend/src/mdcopilot_blog/db/seed.py`
- `backend/src/mdcopilot_blog/cli.py`
- `backend/tests/db/test_seed.py`
- `backend/tests/db/test_cli.py`

---

### Task 9: API app, auth/users/settings routes, workflow client

The FastAPI factory, dependencies (state access, principal, RBAC, CSRF), the auth, users, settings and health routes, the request/response schemas (including the runs schemas Task 12 serves), and the api's DBOS client wrapper.

> Verified 2026-09-17 in a throwaway container (same images and lock as Task 7, `dbos==3.0.0`) against contract-shaped stand-ins for Tasks 2–5: all Task 9 tests passed, `uvicorn --factory` served `/healthz`, `/readyz` and a problem+json 401, and `ruff check`, `ruff format --check` and `mypy --strict` were clean.

**Files:**
- Create: `backend/src/mdcopilot_blog/workflows/__init__.py`, `workflows/names.py`, `workflows/client.py`
- Create: `backend/src/mdcopilot_blog/api/__init__.py`, `api/schemas.py`, `api/deps.py`, `api/app.py`
- Create: `backend/src/mdcopilot_blog/api/routers/__init__.py`, `routers/health.py`, `routers/auth.py`, `routers/users.py`, `routers/settings.py`
- Modify: `backend/tests/conftest.py` (add the T9 block)
- Test: `backend/tests/unit/test_workflow_client.py`, `backend/tests/unit/test_api_schemas.py`, `backend/tests/db/test_workflow_client_db.py`
- Test: `backend/tests/api/test_health.py`, `test_auth_api.py`, `test_users_api.py`, `test_settings_api.py`, `test_csrf_api.py`, `test_rbac_routes.py`

**Interfaces:**
- Consumes:
  - Task 2: `Settings` and `get_settings()`. Fields and members used: `session_secret`, `session_cookie_secure`, `session_cookie_name`, `public_app_url`, `app_version`, `log_level`, `database_url()`, `dbos_system_database_url`, `mock_mode`, `agent_enabled`, `scheduler_enabled`, `publishing_enabled`, `gemini_grounding_enabled`, `human_approval_required`, `daily_run_time`, `timezone`, `route_values()`, `max_cost_per_run_usd`, `discovery_timeout_minutes`, `production_timeout_minutes`, `max_parallel_searches`, `max_parallel_fetches`, `research_window_days`, `min_source_count`, `novelty_threshold`, `word_count_min`, `word_count_max`, `publisher`, `openai_api_key`, `gemini_api_key`, `anthropic_api_key`, `ncbi_api_key`, `postgres_password`, `postgres_host`.
  - Task 3: `ProblemError`, `problem_response`, `install_problem_handlers` (`mdcopilot_blog.errors`); `configure_logging` (`mdcopilot_blog.logs`). Not redefined here.
  - Task 4: `Role`, `Permission`, `RunKind`, `RunStatus`, `AttemptStatus`, `StepStatus`, `permissions_for`, `PillarKey`.
  - Task 5: `make_engine`, `make_sessionmaker`, `User`; conftest fixtures `settings`, `database_url` (must already have run the DBOS system-table migrations on the test DB: in-process, the same code `dbos migrate` runs), `engine`, `db_session`.
  - Task 7: everything listed under its Produces.
- Produces:
  - `workflows/names.py`: every constant in the contract (`WORKFLOW_HELLO`, `WORKFLOW_DAILY_TRIGGER`, `QUEUE_PIPELINE`, `QUEUE_INTERACTIVE`, `SCHEDULE_DAILY`, `STEP_HELLO_OPEN`, `STEP_HELLO_ECHO`, `STEP_HELLO_FINISH`, `STEP_HELLO_FAIL`, `STEP_DAILY_CREATE_RUN`, `DAILY_TARGET_WORKFLOW`, `HEARTBEAT_FILE`).
  - `workflows/client.py`: `StepView`, `WorkflowClientProtocol`, `WorkflowClient(client: DBOSClient, app_version: str)` with `from_settings(settings)`, `FakeWorkflowClient`. The fake is a dataclass with these attributes: `enqueued: list[EnqueueCall]` (`EnqueueCall(workflow_name, queue_name, workflow_id, args, timeout_seconds)`), `cancelled: list[str]`, `forked: list[ForkCall]` (`ForkCall(workflow_id, step_name, start_step, queue_name, new_workflow_id)`), `statuses: dict[str, str]`, `steps: dict[str, list[StepView]]`, `enqueue_error: Exception | None` (raised by `enqueue` when set; use it to test the 503 path), `closed: bool`. `enqueue` returns the given `workflow_id`; a fork returns `f"{workflow_id}-fork-{n}"`.
  - `api/schemas.py`: `ApiModel` (camelCase, `extra="forbid"`, `from_attributes=True`), `LoginRequest`, `SessionUser`, `SessionResponse`, `UserOut`, `UserCreate`, `UserUpdate`, `ProviderKeyView`, `SettingsView`, `mask_secret`, `ManualRunRequest`, `RunOut`, `AttemptOut`, `StepOut`, `RunDetail`, `Page[T]` (PEP 695 generic; use `Page[RunOut]`). `Decimal` fields serialize as JSON strings (for example `"0.001200"`).
  - `api/deps.py`: `utcnow()`, `get_settings_dep`, `get_session`, `get_workflow_client`, the aliases `SettingsDep`, `SessionDep`, `WorkflowClientDep`, `PrincipalDep`, `Principal`, `current_principal`, `require_permission(permission) -> Callable[..., Awaitable[Principal]]`, `enforce_csrf`, `LOGIN_PATH`.
  - `api/app.py`: `create_app(settings=None, *, workflow_client=None) -> FastAPI`, `lifespan`, and `ROUTERS: tuple[tuple[APIRouter, str], ...]`.
  - Router modules each expose `router: APIRouter`; `routers/settings.py` also exposes `build_settings_view(settings) -> SettingsView`.
  - Conftest (T9 block): `TEST_PASSWORD`, `TEST_ORIGIN`, and the fixtures `fake_workflow_client`, `app`, `client`, `make_user(role, *, email=None, password=TEST_PASSWORD)`, `login_as(role) -> (client, csrf_token)`.
  - **Task 12's edit to `api/app.py`** is exactly two insertions. After the line `from mdcopilot_blog.api.routers import health as health_routes`, add `from mdcopilot_blog.api.routers import runs as runs_routes`. After the line `    (settings_routes.router, "/api/blog-agent"),`, add `    (runs_routes.router, "/api/blog-agent"),`.

**Behaviour decisions (read before implementing):**
- **State lookup.** Every dependency reads `request.app.state.<name>` first and falls back to `request.state.<name>` (lifespan state). `create_app` sets `app.state.settings`; the lifespan sets `engine`, `sessionmaker` and `workflow_client` on `app.state` *and* yields them. Tests set `app.state` directly because `ASGITransport` never runs the lifespan.
- **CSRF order** (app-level dependency, unsafe methods only): (1) `Sec-Fetch-Site` present and not `same-origin` → 403 "Cross-site request blocked"; its absence alone is allowed; (2) `Origin` must equal `PUBLIC_APP_URL` or `<X-Forwarded-Proto or scheme>://<Host>`, else 403 "Origin not allowed"; (3) except on `/api/auth/login`, a request that carries the session cookie must send `X-CSRF-Token` equal to `HMAC(SESSION_SECRET, "csrf:" + session token)`, else 403 "CSRF token missing or invalid". A request with no session cookie passes step 3, and the route's auth dependency answers 401. FastAPI resolves this dependency before body validation, so a bad token is 403 even with an invalid body.
- **Login.** The rate limit is checked before the password (429, nothing recorded). A failure records an attempt and commits before raising 401. Success revokes any session cookie the browser already had, creates a new session, records the attempt, audits `auth.login`, commits, sets the cookie (HttpOnly, SameSite=Strict, Path=/, Max-Age=43200, Secure per settings) and returns `Cache-Control: no-store`.
- **Client IP.** The per-IP login limit uses `request.client.host`. With `--proxy-headers`, uvicorn replaces that with an address from `X-Forwarded-For`, but only when the direct peer is listed in `--forwarded-allow-ips`. That flag must name only the real proxy. With `*`, any client can send a new `X-Forwarded-For` on each attempt and get past `MAX_FAILURES_PER_IP`; the per-email limit still applies. A whole compose subnet is also unsafe, because traffic from the host arrives from the subnet's gateway address.
  - Task 14 therefore gives the `web` container (the Vite proxy) a fixed address and trusts only that address.
  - Tests are unaffected: `ASGITransport` always reports `127.0.0.1`.
  - Checked in a container on 2026-09-17 against uvicorn 0.53.0's `ProxyHeadersMiddleware`:
    - With `*`, a forged address was used.
    - With the trust pinned to one address, a direct request kept its real peer address, and a request through the proxy got the rightmost address the proxy appended.
- **Users.** Deactivating a user revokes all their sessions. A password change revokes all of that user's sessions except the acting admin's current one. An admin changing their own role, or deactivating themselves, gets 409; re-sending the current values is a no-op 200. `UserUpdate` uses `model_fields_set` and attributes, never `model_dump()`: `serialize_by_alias=True` makes `model_dump()` return camelCase keys.
- **Settings view.** Keys inside `schedule` and `limits` are written in camelCase by hand, because the alias generator renames fields, not dict keys. `routes` is `settings.route_values()` unchanged. Provider keys go through `mask_secret` only.
- **FastAPI 0.141 routing.** `app.routes` holds `_IncludedRouter` wrappers, not `APIRoute` objects (found during verification). The deny-by-default test therefore walks the original routers in `ROUTERS`, and a second test proves `ROUTERS` covers every path in `app.openapi()`.
- **DBOSClient.** Only `*_async` methods are called. `list_workflow_steps_async(load_output=False)` also drops step errors, so `list_steps` keeps the default. The client is built with `lazy=True`, so the api starts even before the `dbos` schema exists.

- [ ] **Step 1: Write the failing workflow client tests**

The unit tests use a stub with the exact DBOSClient 3.0 `*_async` signatures. Create `backend/tests/unit/test_workflow_client.py`:

```python
from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from dbos import DBOSClient

from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import (
    EnqueueCall,
    FakeWorkflowClient,
    ForkCall,
    StepView,
    WorkflowClient,
    WorkflowClientProtocol,
)
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_HELLO


@dataclass
class StubHandle:
    workflow_id: str

    def get_workflow_id(self) -> str:
        return self.workflow_id


@dataclass
class StubStatus:
    status: str


@dataclass
class StubDBOSClient:
    """Records calls with the exact DBOSClient 3.0 *_async signatures the wrapper uses."""

    steps: list[dict[str, Any]] = field(default_factory=list)
    rows: list[StubStatus] = field(default_factory=list)
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    destroyed: bool = False

    async def enqueue_async(self, options: dict[str, Any], *args: Any) -> StubHandle:
        self.calls.append(("enqueue_async", (dict(options), *args), {}))
        return StubHandle(options["workflow_id"])

    async def cancel_workflow_async(self, workflow_id: str) -> None:
        self.calls.append(("cancel_workflow_async", (workflow_id,), {}))

    async def list_workflow_steps_async(self, workflow_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list_workflow_steps_async", (workflow_id,), kwargs))
        return self.steps

    async def list_workflows_async(self, **kwargs: Any) -> list[StubStatus]:
        self.calls.append(("list_workflows_async", (), kwargs))
        return self.rows

    async def fork_workflow_async(self, workflow_id: str, start_step: int, **kwargs: Any) -> StubHandle:
        self.calls.append(("fork_workflow_async", (workflow_id, start_step), kwargs))
        return StubHandle(f"forked-{workflow_id}-{start_step}")

    def destroy(self) -> None:
        self.destroyed = True


def _step(function_id: int, name: str, error: Exception | None = None) -> dict[str, Any]:
    return {
        "function_id": function_id,
        "function_name": name,
        "output": None,
        "error": error,
        "child_workflow_id": None,
        "started_at_epoch_ms": 1000 * function_id,
        "completed_at_epoch_ms": 1000 * function_id + 5,
    }


def _wrap(stub: StubDBOSClient) -> WorkflowClient:
    return WorkflowClient(cast(DBOSClient, stub), app_version="1.2.3")


async def test_enqueue_builds_enqueue_options() -> None:
    stub = StubDBOSClient()
    workflow_id = await _wrap(stub).enqueue(
        workflow_name=WORKFLOW_HELLO,
        queue_name=QUEUE_PIPELINE,
        workflow_id="manual-abc",
        args=("run-1",),
        timeout_seconds=1800.0,
    )
    assert workflow_id == "manual-abc"
    assert stub.calls == [
        (
            "enqueue_async",
            (
                {
                    "queue_name": "pipeline",
                    "workflow_name": "hello_pipeline",
                    "workflow_id": "manual-abc",
                    "app_version": "1.2.3",
                    "workflow_timeout": 1800.0,
                },
                "run-1",
            ),
            {},
        )
    ]


async def test_enqueue_without_timeout_omits_the_key() -> None:
    stub = StubDBOSClient()
    await _wrap(stub).enqueue(
        workflow_name=WORKFLOW_HELLO, queue_name=QUEUE_PIPELINE, workflow_id="w", args=(), timeout_seconds=None
    )
    options = stub.calls[0][1][0]
    assert "workflow_timeout" not in options
    assert options["app_version"] == "1.2.3"


async def test_cancel() -> None:
    stub = StubDBOSClient()
    await _wrap(stub).cancel("wf-1")
    assert stub.calls == [("cancel_workflow_async", ("wf-1",), {})]


async def test_list_steps_maps_step_info() -> None:
    stub = StubDBOSClient(steps=[_step(1, "hello.open_attempt"), _step(2, "hello.echo", ValueError("boom"))])
    views = await _wrap(stub).list_steps("wf-1")
    assert views == [
        StepView(1, "hello.open_attempt", 1000, 1005, None),
        StepView(2, "hello.echo", 2000, 2005, "ValueError: boom"),
    ]
    assert stub.calls == [("list_workflow_steps_async", ("wf-1",), {})]


async def test_status() -> None:
    assert await _wrap(StubDBOSClient(rows=[StubStatus("SUCCESS")])).status("wf-1") == "SUCCESS"
    stub = StubDBOSClient()
    assert await _wrap(stub).status("missing") is None
    assert stub.calls == [
        ("list_workflows_async", (), {"workflow_ids": ["missing"], "load_input": False, "load_output": False})
    ]


async def test_fork_from_step_uses_latest_function_id() -> None:
    stub = StubDBOSClient(
        steps=[_step(1, "research"), _step(2, "draft"), _step(3, "review"), _step(4, "draft"), _step(5, "seo")]
    )
    new_id = await _wrap(stub).fork_from_step("wf-1", "draft", queue_name="pipeline")
    assert new_id == "forked-wf-1-4"
    assert stub.calls[0] == ("list_workflow_steps_async", ("wf-1",), {"load_output": False})
    assert stub.calls[1] == (
        "fork_workflow_async",
        ("wf-1", 4),
        {"application_version": "1.2.3", "queue_name": "pipeline"},
    )


async def test_fork_from_unknown_step_raises_lookup_error() -> None:
    stub = StubDBOSClient(steps=[_step(1, "research")])
    with pytest.raises(LookupError, match="'draft' not found"):
        await _wrap(stub).fork_from_step("wf-1", "draft", queue_name="pipeline")
    assert [call[0] for call in stub.calls] == ["list_workflow_steps_async"]


def test_close_destroys_the_client() -> None:
    stub = StubDBOSClient()
    _wrap(stub).close()
    assert stub.destroyed is True


def test_from_settings_is_lazy(settings: Settings) -> None:
    # lazy=True: construction opens no connection, so an unreachable host is fine until first use.
    unreachable = settings.model_copy(update={"postgres_host": "unreachable.invalid"})
    client: WorkflowClientProtocol = WorkflowClient.from_settings(unreachable)
    assert isinstance(client, WorkflowClient)
    client.close()


async def test_fake_records_enqueue_and_cancel() -> None:
    fake = FakeWorkflowClient()
    assert (
        await fake.enqueue(
            workflow_name=WORKFLOW_HELLO,
            queue_name=QUEUE_PIPELINE,
            workflow_id="manual-1",
            args=("run-1",),
            timeout_seconds=60.0,
        )
        == "manual-1"
    )
    assert fake.enqueued == [EnqueueCall("hello_pipeline", "pipeline", "manual-1", ("run-1",), 60.0)]
    assert await fake.status("manual-1") == "ENQUEUED"
    await fake.cancel("manual-1")
    assert fake.cancelled == ["manual-1"]
    assert await fake.status("manual-1") == "CANCELLED"
    assert await fake.status("unknown") is None


async def test_fake_enqueue_error() -> None:
    fake = FakeWorkflowClient(enqueue_error=ConnectionError("dbos down"))
    with pytest.raises(ConnectionError):
        await fake.enqueue(workflow_name="w", queue_name="q", workflow_id="id", args=(), timeout_seconds=None)
    assert fake.enqueued == []


async def test_fake_steps_and_fork() -> None:
    fake = FakeWorkflowClient(steps={"wf": [StepView(1, "a", None, None, None), StepView(3, "a", None, None, None)]})
    assert [s.function_id for s in await fake.list_steps("wf")] == [1, 3]
    assert await fake.list_steps("other") == []
    assert await fake.fork_from_step("wf", "a", queue_name="pipeline") == "wf-fork-1"
    assert await fake.fork_from_step("wf", "a", queue_name="pipeline") == "wf-fork-2"
    assert fake.forked[0] == ForkCall("wf", "a", 3, "pipeline", "wf-fork-1")
    with pytest.raises(LookupError):
        await fake.fork_from_step("wf", "missing", queue_name="pipeline")


def test_fake_close() -> None:
    fake = FakeWorkflowClient()
    fake.close()
    assert fake.closed is True
```

The DB-backed test calls the real DBOSClient against the test database's `dbos` schema, which catches signature drift the stub cannot. Create `backend/tests/db/test_workflow_client_db.py`:

```python
"""WorkflowClient against the real dbos schema of the test database (migrated by the T5 database_url fixture)."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import URL

from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient


@pytest_asyncio.fixture(loop_scope="session")
async def real_client(settings: Settings, database_url: URL) -> AsyncIterator[WorkflowClient]:
    client = WorkflowClient.from_settings(settings)
    try:
        yield client
    finally:
        client.close()


async def test_unknown_workflow_has_no_status_or_steps(real_client: WorkflowClient) -> None:
    assert await real_client.status("does-not-exist") is None
    assert await real_client.list_steps("does-not-exist") == []


async def test_fork_of_unknown_workflow_raises_lookup_error(real_client: WorkflowClient) -> None:
    with pytest.raises(LookupError):
        await real_client.fork_from_step("does-not-exist", "hello.echo", queue_name="pipeline")


async def test_enqueue_writes_an_enqueued_row(real_client: WorkflowClient) -> None:
    # The row stays ENQUEUED (nobody consumes t9-probe-queue); cancelling then marks it CANCELLED.
    workflow_id = await real_client.enqueue(
        workflow_name="hello_pipeline",
        queue_name="t9-probe-queue",  # no worker listens here, so nothing runs it
        workflow_id="t9-enqueue-probe",
        args=("00000000-0000-0000-0000-000000000000",),
        timeout_seconds=60.0,
    )
    assert workflow_id == "t9-enqueue-probe"
    assert await real_client.status(workflow_id) == "ENQUEUED"
    await real_client.cancel(workflow_id)
    assert await real_client.status(workflow_id) == "CANCELLED"
```

- [ ] **Step 2: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_workflow_client.py tests/db/test_workflow_client_db.py -q`
Expected: two collection errors, `ModuleNotFoundError: No module named 'mdcopilot_blog.workflows'`.

- [ ] **Step 3: Create the workflows package and the shared names**

Create `backend/src/mdcopilot_blog/workflows/__init__.py` (Task 11 adds modules to this package and must keep this file):

```python
"""Durable workflows (DBOS). The api imports only `names` and `client` from this package."""
```

Create `backend/src/mdcopilot_blog/workflows/names.py`:

```python
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
```

- [ ] **Step 4: Implement the workflow client**

Create `backend/src/mdcopilot_blog/workflows/client.py`:

```python
"""The api's only door to DBOS: enqueue and manage workflows by name through DBOSClient (never DBOS.launch())."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from dbos import DBOSClient, EnqueueOptions, WorkflowHandleAsync

if TYPE_CHECKING:
    from mdcopilot_blog.settings import Settings

DBOS_SYSTEM_SCHEMA = "dbos"
DBOS_APPLICATION_NAME = "mdcopilot-blog"


@dataclass(frozen=True)
class StepView:
    function_id: int
    function_name: str
    started_at_epoch_ms: int | None
    completed_at_epoch_ms: int | None
    error: str | None


class WorkflowClientProtocol(Protocol):
    async def enqueue(
        self,
        *,
        workflow_name: str,
        queue_name: str,
        workflow_id: str,
        args: tuple[object, ...],
        timeout_seconds: float | None,
    ) -> str: ...

    async def cancel(self, workflow_id: str) -> None: ...

    async def list_steps(self, workflow_id: str) -> list[StepView]: ...

    async def status(self, workflow_id: str) -> str | None: ...

    async def fork_from_step(self, workflow_id: str, step_name: str, *, queue_name: str) -> str: ...

    def close(self) -> None: ...


def _latest_function_id(steps: list[StepView], workflow_id: str, step_name: str) -> int:
    """A step name can repeat (loops, retries); fork from its most recent execution."""
    ids = [step.function_id for step in steps if step.function_name == step_name]
    if not ids:
        raise LookupError(f"step {step_name!r} not found in workflow {workflow_id!r}")
    return max(ids)


class WorkflowClient(WorkflowClientProtocol):
    """Async wrapper over DBOSClient. Only *_async client methods are used, so the event loop never blocks."""

    def __init__(self, client: DBOSClient, app_version: str) -> None:
        self._client = client
        self._app_version = app_version

    @classmethod
    def from_settings(cls, settings: Settings) -> WorkflowClient:
        client = DBOSClient(
            system_database_url=settings.dbos_system_database_url,
            dbos_system_schema=DBOS_SYSTEM_SCHEMA,
            application_name=DBOS_APPLICATION_NAME,
            lazy=True,
        )
        return cls(client, settings.app_version)

    async def enqueue(
        self,
        *,
        workflow_name: str,
        queue_name: str,
        workflow_id: str,
        args: tuple[object, ...],
        timeout_seconds: float | None,
    ) -> str:
        options: EnqueueOptions = {
            "queue_name": queue_name,
            "workflow_name": workflow_name,
            "workflow_id": workflow_id,
            # Must equal the worker's application_version, or the workflow stays ENQUEUED forever.
            "app_version": self._app_version,
        }
        if timeout_seconds is not None:
            options["workflow_timeout"] = timeout_seconds
        handle: WorkflowHandleAsync[Any] = await self._client.enqueue_async(options, *args)
        return handle.get_workflow_id()

    async def cancel(self, workflow_id: str) -> None:
        await self._client.cancel_workflow_async(workflow_id)

    async def list_steps(self, workflow_id: str) -> list[StepView]:
        # load_output=True is required: with False, DBOS also drops the step error.
        steps = await self._client.list_workflow_steps_async(workflow_id)
        return [
            StepView(
                function_id=step["function_id"],
                function_name=step["function_name"],
                started_at_epoch_ms=step["started_at_epoch_ms"],
                completed_at_epoch_ms=step["completed_at_epoch_ms"],
                error=None if step["error"] is None else f"{type(step['error']).__name__}: {step['error']}",
            )
            for step in steps
        ]

    async def status(self, workflow_id: str) -> str | None:
        rows = await self._client.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
        return rows[0].status if rows else None

    async def fork_from_step(self, workflow_id: str, step_name: str, *, queue_name: str) -> str:
        steps = await self._client.list_workflow_steps_async(workflow_id, load_output=False)
        views = [StepView(step["function_id"], step["function_name"], None, None, None) for step in steps]
        start_step = _latest_function_id(views, workflow_id, step_name)
        handle = await self._client.fork_workflow_async(
            workflow_id, start_step, application_version=self._app_version, queue_name=queue_name
        )
        return handle.get_workflow_id()

    def close(self) -> None:
        self._client.destroy()


@dataclass(frozen=True)
class EnqueueCall:
    workflow_name: str
    queue_name: str
    workflow_id: str
    args: tuple[object, ...]
    timeout_seconds: float | None


@dataclass(frozen=True)
class ForkCall:
    workflow_id: str
    step_name: str
    start_step: int
    queue_name: str
    new_workflow_id: str


@dataclass
class FakeWorkflowClient(WorkflowClientProtocol):
    """In-memory stand-in for API tests. Records every call; ids are deterministic."""

    enqueued: list[EnqueueCall] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    forked: list[ForkCall] = field(default_factory=list)
    statuses: dict[str, str] = field(default_factory=dict)
    steps: dict[str, list[StepView]] = field(default_factory=dict)
    enqueue_error: Exception | None = None
    closed: bool = False

    async def enqueue(
        self,
        *,
        workflow_name: str,
        queue_name: str,
        workflow_id: str,
        args: tuple[object, ...],
        timeout_seconds: float | None,
    ) -> str:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.enqueued.append(EnqueueCall(workflow_name, queue_name, workflow_id, tuple(args), timeout_seconds))
        self.statuses.setdefault(workflow_id, "ENQUEUED")
        return workflow_id

    async def cancel(self, workflow_id: str) -> None:
        self.cancelled.append(workflow_id)
        self.statuses[workflow_id] = "CANCELLED"

    async def list_steps(self, workflow_id: str) -> list[StepView]:
        return list(self.steps.get(workflow_id, []))

    async def status(self, workflow_id: str) -> str | None:
        return self.statuses.get(workflow_id)

    async def fork_from_step(self, workflow_id: str, step_name: str, *, queue_name: str) -> str:
        start_step = _latest_function_id(self.steps.get(workflow_id, []), workflow_id, step_name)
        new_workflow_id = f"{workflow_id}-fork-{len(self.forked) + 1}"
        self.forked.append(ForkCall(workflow_id, step_name, start_step, queue_name, new_workflow_id))
        self.statuses[new_workflow_id] = "ENQUEUED"
        return new_workflow_id

    def close(self) -> None:
        self.closed = True
```

- [ ] **Step 5: Run the workflow client tests and see them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_workflow_client.py tests/db/test_workflow_client_db.py -q`
Expected: `16 passed`. If the DB test fails with a missing `dbos` schema or table, Task 5's `database_url` fixture did not run the DBOS system-table migrations (in-process, the same code `dbos migrate` runs); fix that fixture, not this test.

- [ ] **Step 6: Write the failing schema tests**

Create `backend/tests/unit/test_api_schemas.py`:

```python
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from mdcopilot_blog.api.schemas import (
    ManualRunRequest,
    Page,
    ProviderKeyView,
    RunOut,
    SessionResponse,
    SessionUser,
    UserCreate,
    UserUpdate,
    mask_secret,
)
from mdcopilot_blog.domain.enums import Permission, Role, RunKind, RunStatus


def test_mask_secret() -> None:
    assert mask_secret(None) == ProviderKeyView(configured=False, preview=None)
    assert mask_secret(SecretStr("")) == ProviderKeyView(configured=False, preview=None)
    assert mask_secret(SecretStr("short-key")) == ProviderKeyView(configured=True, preview="set")
    assert mask_secret(SecretStr("sk-abcdefghWXYZ")) == ProviderKeyView(configured=True, preview="sk-…WXYZ")


def test_session_response_is_camel_case() -> None:
    user_id = uuid.uuid4()
    body = SessionResponse(
        user=SessionUser(
            id=user_id, email="a@b.test", display_name="A", role=Role.VIEWER, permissions=[Permission.VIEW]
        ),
        csrf_token="t",
    ).model_dump(mode="json")
    assert body == {
        "user": {
            "id": str(user_id),
            "email": "a@b.test",
            "displayName": "A",
            "role": "viewer",
            "permissions": ["blog.view"],
        },
        "csrfToken": "t",
    }


def test_user_create_validation() -> None:
    ok = UserCreate.model_validate(
        {"email": " New@Example.TEST ", "displayName": " New ", "role": "editor", "password": "x" * 12}
    )
    assert (ok.email, ok.display_name, ok.role) == ("new@example.test", "New", Role.EDITOR)
    bad_inputs = [
        {"email": "no-at-sign", "displayName": "N", "role": "editor", "password": "x" * 12},
        {"email": "a@b.test", "displayName": "   ", "role": "editor", "password": "x" * 12},
        {"email": "a@b.test", "displayName": "N", "role": "owner", "password": "x" * 12},
        {"email": "a@b.test", "displayName": "N", "role": "editor", "password": "x" * 11},
        {"email": "a@b.test", "displayName": "N", "role": "editor", "password": "x" * 12, "isAdmin": True},
    ]
    for payload in bad_inputs:
        with pytest.raises(ValidationError):
            UserCreate.model_validate(payload)


def test_user_update_tracks_only_sent_fields() -> None:
    update = UserUpdate.model_validate({"isActive": False})
    assert update.model_fields_set == {"is_active"}
    assert (update.role, update.is_active, update.password) == (None, False, None)


def test_manual_run_request_bounds() -> None:
    assert ManualRunRequest.model_validate({}).model_dump(exclude_none=True) == {}
    req = ManualRunRequest.model_validate({"runDate": "2026-09-17", "pillar": "A", "wordCount": 900})
    assert req.model_dump(mode="json", exclude_none=True) == {"runDate": "2026-09-17", "pillar": "A", "wordCount": 900}
    for payload in ({"wordCount": 299}, {"wordCount": 3001}, {"topic": "x" * 301}, {"pillar": "Z"}, {"extra": 1}):
        with pytest.raises(ValidationError):
            ManualRunRequest.model_validate(payload)


def test_page_of_runs_serializes_camel_case_and_decimal_as_string() -> None:
    run = RunOut(
        id=uuid.uuid4(),
        kind=RunKind.MANUAL,
        run_date=date(2026, 9, 17),
        status=RunStatus.QUEUED,
        stage=None,
        trace_id="a" * 32,
        cost_usd=Decimal("0.001200"),
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
        started_at=None,
        finished_at=None,
    )
    body = Page[RunOut](items=[run], total=1, limit=20, offset=0).model_dump(mode="json")
    assert body["total"] == 1
    item = body["items"][0]
    assert item["costUsd"] == "0.001200"
    assert item["runDate"] == "2026-09-17"
    assert item["traceId"] == "a" * 32
    assert "run_date" not in item
```

- [ ] **Step 7: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_api_schemas.py -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'mdcopilot_blog.api'`.

- [ ] **Step 8: Create the api package and the schemas**

Create `backend/src/mdcopilot_blog/api/__init__.py`:

```python
"""HTTP API (FastAPI). Never executes workflows; it enqueues them through DBOSClient."""
```

Create `backend/src/mdcopilot_blog/api/schemas.py`:

```python
"""HTTP request/response models. JSON is camelCase; Python attributes stay snake_case."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic.alias_generators import to_camel

from mdcopilot_blog.auth.users import MIN_PASSWORD_LENGTH
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import AttemptStatus, Permission, Role, RunKind, RunStatus, StepStatus

MAX_EMAIL_LENGTH = 320
MAX_PASSWORD_LENGTH = 1024
MIN_KEY_LENGTH_FOR_PREVIEW = 12  # shorter keys would reveal too large a share


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="forbid",
        from_attributes=True,
    )


def _email(value: str) -> str:
    normalized = value.strip().lower()
    local, _, domain = normalized.partition("@")
    if not local or not domain or "@" in domain or any(ch.isspace() for ch in normalized):
        raise ValueError("must be an email address")
    return normalized


# --- auth ---


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class SessionUser(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    permissions: list[Permission]


class SessionResponse(ApiModel):
    user: SessionUser
    csrf_token: str


# --- users ---


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class UserCreate(ApiModel):
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    display_name: str = Field(min_length=1, max_length=200)
    role: Role
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return _email(value)

    @field_validator("display_name")
    @classmethod
    def _check_display_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class UserUpdate(ApiModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


# --- settings ---


class ProviderKeyView(ApiModel):
    configured: bool
    preview: str | None


class SettingsView(ApiModel):
    app_version: str
    mock_mode: bool
    agent_enabled: bool
    scheduler_enabled: bool
    publishing_enabled: bool
    gemini_grounding_enabled: bool
    human_approval_required: bool
    schedule: dict[str, str]
    routes: dict[str, list[str]]
    limits: dict[str, str | int | float]
    publisher: str
    providers: dict[str, ProviderKeyView]


def mask_secret(value: SecretStr | None) -> ProviderKeyView:
    """Never return a key: 3 leading + 4 trailing characters for long keys, 'set' for short ones."""
    raw = value.get_secret_value() if value is not None else ""
    if not raw:
        return ProviderKeyView(configured=False, preview=None)
    if len(raw) >= MIN_KEY_LENGTH_FOR_PREVIEW:
        return ProviderKeyView(configured=True, preview=f"{raw[:3]}…{raw[-4:]}")
    return ProviderKeyView(configured=True, preview="set")


# --- runs (served by Task 12) ---


class ManualRunRequest(ApiModel):
    run_date: date | None = None
    pillar: PillarKey | None = None
    topic: str | None = Field(None, max_length=300)
    audience: str | None = None
    tone: str | None = None
    word_count: int | None = Field(None, ge=300, le=3000)


class RunOut(ApiModel):
    id: uuid.UUID
    kind: RunKind
    run_date: date
    status: RunStatus
    stage: str | None
    trace_id: str
    cost_usd: Decimal
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AttemptOut(ApiModel):
    id: uuid.UUID
    dbos_workflow_id: str
    workflow_name: str
    attempt_no: int
    status: AttemptStatus
    started_at: datetime | None
    finished_at: datetime | None
    forked_from_workflow_id: str | None


class StepOut(ApiModel):
    id: uuid.UUID
    step_name: str
    dbos_step_id: int
    status: StepStatus
    tries: int
    agent_name: str | None
    model: str | None
    prompt_name: str | None
    prompt_version: int | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    duration_ms: int | None
    error: dict[str, Any] | None


class RunDetail(RunOut):
    params: dict[str, Any]
    attempts: list[AttemptOut]
    steps: list[StepOut]


class Page[T](ApiModel):
    items: list[T]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 9: Run the schema tests and see them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_api_schemas.py -q`
Expected: `6 passed`.

- [ ] **Step 10: Add the T9 block to the shared conftest**

In `backend/tests/conftest.py`, merge these imports into the existing import section (skip any name the T5 block already imports; ruff's import sorting decides the final order):

```python
import itertools
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from mdcopilot_blog.api.app import create_app
from mdcopilot_blog.api.deps import get_session
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.engine import make_sessionmaker
from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import FakeWorkflowClient
```

Append this block at the end of the file, after the T5 block:

```python
# --- T9: API fixtures ---

TEST_PASSWORD = "correct-horse-battery"
TEST_ORIGIN = "http://test"


@pytest.fixture
def fake_workflow_client() -> FakeWorkflowClient:
    return FakeWorkflowClient()


@pytest.fixture
def app(
    settings: Settings, engine: AsyncEngine, db_session: AsyncSession, fake_workflow_client: FakeWorkflowClient
) -> FastAPI:
    application = create_app(settings, workflow_client=fake_workflow_client)

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_session] = _session_override
    # ASGITransport does not run the lifespan, so provide what the lifespan would have set.
    application.state.settings = settings
    application.state.sessionmaker = make_sessionmaker(engine)
    application.state.workflow_client = fake_workflow_client
    return application


@pytest_asyncio.fixture(loop_scope="session")
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=TEST_ORIGIN, headers={"Origin": TEST_ORIGIN}
    ) as http:
        yield http


MakeUser = Callable[..., Awaitable[User]]
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]


@pytest.fixture
def make_user(db_session: AsyncSession) -> MakeUser:
    counter = itertools.count(1)

    async def _make(role: Role, *, email: str | None = None, password: str = TEST_PASSWORD) -> User:
        address = email or f"{role.value}-{next(counter)}@example.test"
        return await create_user(
            db_session, email=address, display_name=f"{role.value.title()} User", role=role, password=password
        )

    return _make


@pytest.fixture
def login_as(client: AsyncClient, make_user: MakeUser) -> LoginAs:
    async def _login(role: Role) -> tuple[AsyncClient, str]:
        user = await make_user(role)
        response = await client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        assert response.status_code == 200, response.text
        return client, str(response.json()["csrfToken"])

    return _login
```

- [ ] **Step 11: Write the failing health and lifespan tests**

Create `backend/tests/api/test_health.py`:

```python
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import URL, text
from sqlalchemy.exc import OperationalError

from mdcopilot_blog.api.app import ROUTERS, create_app
from mdcopilot_blog.api.deps import get_session
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import FakeWorkflowClient, WorkflowClient


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_with_database(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


class _BrokenSession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        raise OperationalError("select 1", {}, ConnectionRefusedError("db down"))


async def test_readyz_reports_database_unavailable(app: FastAPI, client: AsyncClient) -> None:
    async def _broken() -> AsyncIterator[_BrokenSession]:
        yield _BrokenSession()

    app.dependency_overrides[get_session] = _broken
    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Database unavailable",
        "status": 503,
        "instance": "/readyz",
    }


async def test_unknown_route_is_problem_json(client: AsyncClient) -> None:
    response = await client.get("/api/nope")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not Found"


def test_routers_are_registered_in_order() -> None:
    assert [prefix for _, prefix in ROUTERS][:4] == ["", "/api/auth", "/api/admin/users", "/api/blog-agent"]


async def test_lifespan_sets_state_and_closes_injected_client(settings: Settings, database_url: URL) -> None:
    fake = FakeWorkflowClient()
    application = create_app(settings, workflow_client=fake)
    async with application.router.lifespan_context(application) as state:
        assert state is not None
        assert set(state) == {"settings", "engine", "sessionmaker", "workflow_client"}
        assert state["workflow_client"] is fake
        assert application.state.workflow_client is fake
        assert application.state.sessionmaker is state["sessionmaker"]
        async with state["sessionmaker"]() as session:
            assert await session.scalar(text("select current_database()")) == "mdcopilot_blog_test"
    assert fake.closed is True


async def test_lifespan_builds_a_real_workflow_client(settings: Settings, database_url: URL) -> None:
    application = create_app(settings)
    async with application.router.lifespan_context(application) as state:
        assert state is not None
        assert isinstance(state["workflow_client"], WorkflowClient)
```

- [ ] **Step 12: Write the failing auth route tests**

Create `backend/tests/api/test_auth_api.py`:

```python
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.csrf import csrf_token_for
from mdcopilot_blog.auth.sessions import hash_token
from mdcopilot_blog.db.models import AuditLog, LoginAttempt, User, UserSession
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings

PASSWORD = "correct-horse-battery"
MakeUser = Callable[..., Awaitable[User]]


async def _login(client: AsyncClient, email: str, password: str = PASSWORD) -> tuple[int, dict[str, object], str]:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    return response.status_code, response.json(), response.headers.get("set-cookie", "")


async def test_login_success_sets_strict_http_only_cookie(
    client: AsyncClient, make_user: MakeUser, settings: Settings, db_session: AsyncSession
) -> None:
    user = await make_user(Role.REVIEWER, email="rev@example.test")
    response = await client.post("/api/auth/login", json={"email": "  REV@example.test ", "password": PASSWORD})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"

    cookie_header = response.headers["set-cookie"]
    attributes = [part.strip().lower() for part in cookie_header.split(";")]
    assert attributes[0].startswith("mdcb_session=")
    assert "httponly" in attributes
    assert "samesite=strict" in attributes
    assert "path=/" in attributes
    assert "max-age=43200" in attributes
    assert "secure" not in attributes

    token = client.cookies["mdcb_session"]
    body = response.json()
    assert body["csrfToken"] == csrf_token_for(token, settings.session_secret.get_secret_value())
    assert body["user"] == {
        "id": str(user.id),
        "email": "rev@example.test",
        "displayName": "Reviewer User",
        "role": "reviewer",
        "permissions": sorted(
            [
                "blog.view",
                "blog.generate",
                "blog.edit",
                "blog.review",
                "blog.approve",
                "blog.schedule",
                "blog.agent_runs",
            ]
        ),
    }

    stored = await db_session.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert stored is not None
    assert stored.token_hash == hash_token(token)
    attempts = (await db_session.scalars(select(LoginAttempt).where(LoginAttempt.email == "rev@example.test"))).all()
    assert [a.succeeded for a in attempts] == [True]
    audit_row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.login"))
    assert audit_row is not None
    assert (audit_row.actor_user_id, audit_row.entity_id) == (user.id, str(user.id))


async def test_secure_cookie_uses_host_prefix(
    app: FastAPI, client: AsyncClient, make_user: MakeUser, settings: Settings
) -> None:
    app.state.settings = settings.model_copy(update={"session_cookie_secure": True})
    user = await make_user(Role.VIEWER)
    response = await client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    attributes = [part.strip().lower() for part in response.headers["set-cookie"].split(";")]
    assert attributes[0].startswith("__host-mdcb_session=")
    assert "secure" in attributes
    assert "path=/" in attributes


async def test_wrong_password_is_401_and_recorded(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user(Role.VIEWER)
    status, body, cookie = await _login(client, user.email, "not-the-password")
    assert status == 401
    assert body["title"] == "Invalid email or password"
    assert cookie == ""
    attempts = (await db_session.scalars(select(LoginAttempt).where(LoginAttempt.email == user.email))).all()
    assert [a.succeeded for a in attempts] == [False]


async def test_unknown_email_and_inactive_user_get_the_same_401(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    status, body, _ = await _login(client, "ghost@example.test")
    assert (status, body["title"]) == (401, "Invalid email or password")
    user = await make_user(Role.VIEWER)
    user.is_active = False
    await db_session.flush()
    status, body, _ = await _login(client, user.email)
    assert (status, body["title"]) == (401, "Invalid email or password")


async def test_sixth_attempt_after_five_failures_is_429(client: AsyncClient, make_user: MakeUser) -> None:
    user = await make_user(Role.VIEWER)
    for _ in range(5):
        status, _, _ = await _login(client, user.email, "not-the-password")
        assert status == 401
    status, body, cookie = await _login(client, user.email, PASSWORD)  # correct password, still blocked
    assert status == 429
    assert body["title"] == "Too many login attempts"
    assert cookie == ""


async def test_login_validation_error(client: AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"email": "a@b.test"})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_session_endpoint(client: AsyncClient, make_user: MakeUser) -> None:
    anonymous = await client.get("/api/auth/session")
    assert anonymous.status_code == 401
    assert anonymous.json()["title"] == "Not authenticated"

    user = await make_user(Role.ADMIN)
    _, login_body, _ = await _login(client, user.email)
    response = await client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["csrfToken"] == login_body["csrfToken"]
    assert body["user"]["role"] == "admin"
    assert len(body["user"]["permissions"]) == 9


async def test_garbage_cookie_is_401(client: AsyncClient) -> None:
    client.cookies.set("mdcb_session", "garbage")
    response = await client.get("/api/auth/session")
    assert response.status_code == 401


async def test_logout_revokes_the_session_and_clears_the_cookie(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user(Role.EDITOR)
    _, body, _ = await _login(client, user.email)
    token = client.cookies["mdcb_session"]

    response = await client.post("/api/auth/logout", headers={"X-CSRF-Token": str(body["csrfToken"])})
    assert response.status_code == 204
    assert response.content == b""
    cleared = [part.strip().lower() for part in response.headers["set-cookie"].split(";")]
    assert cleared[0] == 'mdcb_session=""'
    assert "max-age=0" in cleared

    stored = await db_session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    assert stored is not None
    await db_session.refresh(stored)
    assert stored.revoked_at is not None
    assert await db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.logout")) is not None

    # Even if a client kept the old cookie, the session is dead.
    client.cookies.set("mdcb_session", token)
    assert (await client.get("/api/auth/session")).status_code == 401


async def test_logout_without_session_is_401(client: AsyncClient) -> None:
    response = await client.post("/api/auth/logout")
    assert response.status_code == 401


async def test_second_login_revokes_the_previous_session(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user(Role.VIEWER)
    await _login(client, user.email)
    first = client.cookies["mdcb_session"]
    await _login(client, user.email)
    second = client.cookies["mdcb_session"]
    assert first != second
    old = await db_session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(first)))
    assert old is not None
    await db_session.refresh(old)
    assert old.revoked_at is not None
```

- [ ] **Step 13: Write the failing user route tests**

Create `backend/tests/api/test_users_api.py`:

```python
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.passwords import verify_password
from mdcopilot_blog.db.models import AuditLog, User
from mdcopilot_blog.domain.enums import Role

PASSWORD = "correct-horse-battery"
MakeUser = Callable[..., Awaitable[User]]
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]
NEW_USER = {"email": "New.Person@Example.TEST", "displayName": "New Person", "role": "editor", "password": "x" * 12}


async def _admin_id(client: AsyncClient) -> str:
    return str((await client.get("/api/auth/session")).json()["user"]["id"])


async def test_list_users(login_as: LoginAs, make_user: MakeUser) -> None:
    client, _ = await login_as(Role.ADMIN)
    await make_user(Role.VIEWER, email="listed@example.test")
    response = await client.get("/api/admin/users")
    assert response.status_code == 200
    rows = response.json()
    listed = next(row for row in rows if row["email"] == "listed@example.test")
    assert set(listed) == {"id", "email", "displayName", "role", "isActive", "lastLoginAt", "createdAt"}
    assert (listed["role"], listed["isActive"], listed["lastLoginAt"]) == ("viewer", True, None)
    admin = next(row for row in rows if row["role"] == "admin")
    assert admin["lastLoginAt"] is not None
    assert "passwordHash" not in response.text


async def test_create_user(login_as: LoginAs, db_session: AsyncSession) -> None:
    client, csrf = await login_as(Role.ADMIN)
    response = await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["displayName"], body["role"], body["isActive"]) == (
        "new.person@example.test",
        "New Person",
        "editor",
        True,
    )
    user = await db_session.get(User, uuid.UUID(body["id"]))
    assert user is not None
    assert verify_password("x" * 12, user.password_hash)[0] is True
    audit_row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "user.create"))
    assert audit_row is not None
    assert audit_row.entity_id == body["id"]
    assert audit_row.details == {"email": "new.person@example.test", "role": "editor"}
    assert audit_row.actor_user_id == uuid.UUID(await _admin_id(client))


async def test_created_user_can_log_in(login_as: LoginAs, app: FastAPI) -> None:
    client, csrf = await login_as(Role.ADMIN)
    assert (await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})).status_code == 201
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
    ) as other:
        response = await other.post("/api/auth/login", json={"email": NEW_USER["email"], "password": "x" * 12})
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "editor"


async def test_duplicate_user_is_409(login_as: LoginAs, make_user: MakeUser) -> None:
    client, csrf = await login_as(Role.ADMIN)
    await make_user(Role.VIEWER, email="new.person@example.test")
    response = await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 409
    assert response.json()["title"] == "User already exists"


async def test_invalid_create_payloads_are_422(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    for payload in (
        {**NEW_USER, "password": "x" * 11},
        {**NEW_USER, "role": "owner"},
        {**NEW_USER, "email": "not-an-email"},
        {**NEW_USER, "isSuperuser": True},
    ):
        response = await client.post("/api/admin/users", json=payload, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 422, payload
        assert response.json()["title"] == "Request validation failed"


async def test_update_role_is_audited(login_as: LoginAs, make_user: MakeUser, db_session: AsyncSession) -> None:
    client, csrf = await login_as(Role.ADMIN)
    target = await make_user(Role.VIEWER)
    response = await client.patch(
        f"/api/admin/users/{target.id}", json={"role": "publisher"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "publisher"
    audit_row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "user.update"))
    assert audit_row is not None
    assert audit_row.details == {"role": {"from": "viewer", "to": "publisher"}}


async def test_deactivating_a_user_signs_them_out(login_as: LoginAs, make_user: MakeUser, app: FastAPI) -> None:
    admin, csrf = await login_as(Role.ADMIN)
    target = await make_user(Role.EDITOR)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
    ) as other:
        assert (
            await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        ).status_code == 200
        assert (await other.get("/api/auth/session")).status_code == 200

        response = await admin.patch(
            f"/api/admin/users/{target.id}", json={"isActive": False}, headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
        assert response.json()["isActive"] is False

        assert (await other.get("/api/auth/session")).status_code == 401
        relogin = await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        assert relogin.status_code == 401


async def test_password_change_signs_out_existing_sessions(
    login_as: LoginAs, make_user: MakeUser, app: FastAPI
) -> None:
    admin, csrf = await login_as(Role.ADMIN)
    target = await make_user(Role.EDITOR)
    headers = {"X-CSRF-Token": csrf}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
    ) as other:
        assert (
            await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        ).status_code == 200
        short = await admin.patch(f"/api/admin/users/{target.id}", json={"password": "short"}, headers=headers)
        assert short.status_code == 422
        assert (await other.get("/api/auth/session")).status_code == 200  # the rejected change did nothing

        changed = await admin.patch(
            f"/api/admin/users/{target.id}", json={"password": "a-brand-new-password"}, headers=headers
        )
        assert changed.status_code == 200
        assert (await other.get("/api/auth/session")).status_code == 401

        old = await other.post("/api/auth/login", json={"email": target.email, "password": PASSWORD})
        assert old.status_code == 401
        new = await other.post("/api/auth/login", json={"email": target.email, "password": "a-brand-new-password"})
        assert new.status_code == 200


async def test_admin_cannot_demote_or_deactivate_self(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    me = await _admin_id(client)
    headers = {"X-CSRF-Token": csrf}
    demote = await client.patch(f"/api/admin/users/{me}", json={"role": "viewer"}, headers=headers)
    assert demote.status_code == 409
    assert demote.json()["title"] == "You cannot change your own role"
    deactivate = await client.patch(f"/api/admin/users/{me}", json={"isActive": False}, headers=headers)
    assert deactivate.status_code == 409
    assert deactivate.json()["title"] == "You cannot deactivate yourself"
    same_role = await client.patch(f"/api/admin/users/{me}", json={"role": "admin", "isActive": True}, headers=headers)
    assert same_role.status_code == 200
    # Changing your own password keeps your current session alive.
    own_password = await client.patch(
        f"/api/admin/users/{me}", json={"password": "another-long-password"}, headers=headers
    )
    assert own_password.status_code == 200
    assert (await client.get("/api/auth/session")).status_code == 200


async def test_update_unknown_user_is_404(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    response = await client.patch(
        f"/api/admin/users/{uuid.uuid4()}", json={"role": "viewer"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 404
    assert response.json()["title"] == "User not found"
```

- [ ] **Step 14: Write the failing settings route tests**

The leak check reports secret *names* only, so a failing assertion never prints a key. The second test also covers the real keys that compose loads from `.env`. Create `backend/tests/api/test_settings_api.py`:

```python
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr

from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings

LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]

FAKE_OPENAI = "sk-proj-FAKE" + "a" * 40 + "WXYZ"
FAKE_GEMINI = "AIza" + "b" * 35


def _leaked(body: str, secrets: dict[str, str]) -> list[str]:
    """Names (never values) of secrets that appear in the body, so a failure cannot print a key."""
    return [name for name, value in secrets.items() if value and value in body]


async def test_settings_view_masks_provider_keys(app: FastAPI, login_as: LoginAs, settings: Settings) -> None:
    app.state.settings = settings.model_copy(
        update={
            "openai_api_key": SecretStr(FAKE_OPENAI),
            "gemini_api_key": SecretStr(FAKE_GEMINI),
            "anthropic_api_key": None,
            "ncbi_api_key": SecretStr("short"),
        }
    )
    client, _ = await login_as(Role.ADMIN)
    response = await client.get("/api/blog-agent/settings")
    assert response.status_code == 200
    assert _leaked(response.text, {"openai": FAKE_OPENAI, "gemini": FAKE_GEMINI, "ncbi": "short"}) == []
    assert response.json()["providers"] == {
        "openai": {"configured": True, "preview": "sk-…WXYZ"},
        "gemini": {"configured": True, "preview": "AIz…bbbb"},
        "anthropic": {"configured": False, "preview": None},
        "ncbi": {"configured": True, "preview": "set"},
    }


async def test_real_environment_keys_never_appear(login_as: LoginAs, settings: Settings) -> None:
    # The tools container gets the real .env, so this guards the actual keys too.
    real = {
        name: key.get_secret_value()
        for name, key in {
            "openai": settings.openai_api_key,
            "gemini": settings.gemini_api_key,
            "anthropic": settings.anthropic_api_key,
            "ncbi": settings.ncbi_api_key,
            "session_secret": settings.session_secret,
            "postgres_password": settings.postgres_password,
        }.items()
        if key is not None
    }
    client, _ = await login_as(Role.ADMIN)
    response = await client.get("/api/blog-agent/settings")
    assert response.status_code == 200
    assert _leaked(response.text, real) == []


async def test_settings_view_shape(login_as: LoginAs, settings: Settings) -> None:
    client, _ = await login_as(Role.ADMIN)
    body = (await client.get("/api/blog-agent/settings")).json()
    assert set(body) == {
        "appVersion",
        "mockMode",
        "agentEnabled",
        "schedulerEnabled",
        "publishingEnabled",
        "geminiGroundingEnabled",
        "humanApprovalRequired",
        "schedule",
        "routes",
        "limits",
        "publisher",
        "providers",
    }
    assert body["humanApprovalRequired"] is True
    assert body["mockMode"] is True
    assert body["appVersion"] == settings.app_version
    assert body["schedule"] == {"dailyRunTime": settings.daily_run_time, "timezone": settings.timezone}
    assert body["routes"] == settings.route_values()
    assert body["limits"]["maxCostPerRunUsd"] == str(settings.max_cost_per_run_usd)
    assert body["limits"]["wordCountMin"] == settings.word_count_min
    assert body["publisher"] == settings.publisher


async def test_settings_requires_admin(login_as: LoginAs) -> None:
    client, _ = await login_as(Role.PUBLISHER)
    response = await client.get("/api/blog-agent/settings")
    assert response.status_code == 403
    assert response.json()["detail"] == "missing permission blog.settings"
```

- [ ] **Step 15: Write the failing CSRF route tests**

Create `backend/tests/api/test_csrf_api.py`:

```python
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings

PASSWORD = "correct-horse-battery"
MakeUser = Callable[..., Awaitable[User]]
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]
NEW_USER = {"email": "csrf-new@example.test", "displayName": "New", "role": "viewer", "password": "x" * 12}


@pytest_asyncio.fixture(loop_scope="session")
async def bare_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A client that sends no Origin header by default."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def _wrong_login(http: AsyncClient, headers: dict[str, str]) -> tuple[int, str]:
    response = await http.post(
        "/api/auth/login", json={"email": "nobody@example.test", "password": "whatever"}, headers=headers
    )
    return response.status_code, str(response.json()["title"])


async def test_cross_site_fetch_metadata_is_blocked(client: AsyncClient) -> None:
    for value in ("cross-site", "same-site", "none"):
        assert await _wrong_login(client, {"Sec-Fetch-Site": value}) == (403, "Cross-site request blocked")


async def test_same_origin_fetch_metadata_passes(client: AsyncClient) -> None:
    # 401 means the request got past CSRF and reached the password check.
    assert await _wrong_login(client, {"Sec-Fetch-Site": "same-origin"}) == (401, "Invalid email or password")


async def test_missing_fetch_metadata_alone_is_not_a_rejection(client: AsyncClient) -> None:
    assert await _wrong_login(client, {}) == (401, "Invalid email or password")


async def test_missing_origin_is_blocked(bare_client: AsyncClient) -> None:
    assert await _wrong_login(bare_client, {}) == (403, "Origin not allowed")


async def test_foreign_origin_is_blocked(client: AsyncClient) -> None:
    assert await _wrong_login(client, {"Origin": "http://evil.example"}) == (403, "Origin not allowed")
    assert await _wrong_login(client, {"Origin": "null"}) == (403, "Origin not allowed")


async def test_same_origin_via_host_and_forwarded_proto(bare_client: AsyncClient) -> None:
    proxied = {"Origin": "https://blog.internal:8443", "Host": "blog.internal:8443", "X-Forwarded-Proto": "https"}
    assert await _wrong_login(bare_client, proxied) == (401, "Invalid email or password")
    without_proto = {"Origin": "https://blog.internal:8443", "Host": "blog.internal:8443"}
    assert await _wrong_login(bare_client, without_proto) == (403, "Origin not allowed")


async def test_vite_proxy_shape_is_allowed(bare_client: AsyncClient) -> None:
    # What the Vite dev proxy forwards (changeOrigin:false, xfwd:true) from a browser at http://web:5173.
    vite = {"Origin": "http://web:5173", "Host": "web:5173", "X-Forwarded-Proto": "http"}
    assert await _wrong_login(bare_client, vite) == (401, "Invalid email or password")


async def test_public_app_url_is_allowed(app: FastAPI, bare_client: AsyncClient, settings: Settings) -> None:
    app.state.settings = settings.model_copy(update={"public_app_url": "http://localhost:8310/"})
    assert await _wrong_login(bare_client, {"Origin": "http://localhost:8310"}) == (401, "Invalid email or password")
    assert await _wrong_login(bare_client, {"Origin": "http://localhost:9999"}) == (403, "Origin not allowed")


async def test_logout_requires_the_csrf_token(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.VIEWER)
    missing = await client.post("/api/auth/logout")
    assert (missing.status_code, missing.json()["title"]) == (403, "CSRF token missing or invalid")
    wrong = await client.post("/api/auth/logout", headers={"X-CSRF-Token": "0" * 64})
    assert wrong.status_code == 403
    assert (await client.get("/api/auth/session")).status_code == 200  # still signed in
    ok = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 204


async def test_users_post_requires_the_csrf_token(login_as: LoginAs) -> None:
    client, csrf = await login_as(Role.ADMIN)
    missing = await client.post("/api/admin/users", json=NEW_USER)
    assert (missing.status_code, missing.json()["title"]) == (403, "CSRF token missing or invalid")
    created = await client.post("/api/admin/users", json=NEW_USER, headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201


async def test_token_check_comes_before_body_validation(login_as: LoginAs) -> None:
    client, _ = await login_as(Role.ADMIN)
    response = await client.post("/api/admin/users", json={"nonsense": True})
    assert response.status_code == 403


async def test_login_is_exempt_from_the_token_but_not_from_origin(login_as: LoginAs, make_user: MakeUser) -> None:
    client, _ = await login_as(Role.VIEWER)  # the cookie jar now holds a session, and no token is sent below
    other = await make_user(Role.EDITOR)
    relogin = await client.post("/api/auth/login", json={"email": other.email, "password": PASSWORD})
    assert relogin.status_code == 200
    foreign = await client.post(
        "/api/auth/login",
        json={"email": other.email, "password": PASSWORD},
        headers={"Origin": "http://evil.example"},
    )
    assert (foreign.status_code, foreign.json()["title"]) == (403, "Origin not allowed")


async def test_safe_methods_are_not_checked(login_as: LoginAs) -> None:
    client, _ = await login_as(Role.VIEWER)
    response = await client.get(
        "/api/auth/session", headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 200


async def test_unsafe_request_without_session_reaches_auth(client: AsyncClient) -> None:
    response = await client.post("/api/admin/users", json=NEW_USER)
    assert (response.status_code, response.json()["title"]) == (401, "Not authenticated")
```

- [ ] **Step 16: Write the failing RBAC matrix tests**

Every role is tested against every protected route; Task 12 covers the runs routes (including viewer 403 on `POST /api/blog-agent/runs`). The last two tests enforce deny-by-default for any route added later, runs included. Create `backend/tests/api/test_rbac_routes.py`:

```python
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from httpx import AsyncClient

from mdcopilot_blog.api.app import ROUTERS
from mdcopilot_blog.api.deps import current_principal
from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import permissions_for

LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]

# (method, path, required permission, JSON body, status when allowed)
PROTECTED: list[tuple[str, str, Permission, dict[str, Any] | None, int]] = [
    ("GET", "/api/admin/users", Permission.SETTINGS, None, 200),
    (
        "POST",
        "/api/admin/users",
        Permission.SETTINGS,
        {"email": "rbac-new@example.test", "displayName": "R", "role": "viewer", "password": "x" * 12},
        201,
    ),
    ("PATCH", f"/api/admin/users/{uuid.uuid4()}", Permission.SETTINGS, {"role": "viewer"}, 404),
    ("GET", "/api/blog-agent/settings", Permission.SETTINGS, None, 200),
]

# Routes that must stay reachable without a session.
PUBLIC_PATHS = {"/healthz", "/readyz", "/api/auth/login"}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize(("method", "path", "permission", "body", "allowed_status"), PROTECTED)
async def test_role_matrix(
    login_as: LoginAs,
    role: Role,
    method: str,
    path: str,
    permission: Permission,
    body: dict[str, Any] | None,
    allowed_status: int,
) -> None:
    client, csrf = await login_as(role)
    response = await client.request(method, path, json=body, headers={"X-CSRF-Token": csrf})
    if permission in permissions_for(role):
        assert response.status_code == allowed_status, response.text
    else:
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == f"missing permission {permission.value}"


@pytest.mark.parametrize(("method", "path", "permission", "body", "allowed_status"), PROTECTED)
async def test_anonymous_is_401(
    client: AsyncClient,
    method: str,
    path: str,
    permission: Permission,
    body: dict[str, Any] | None,
    allowed_status: int,
) -> None:
    response = await client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json()["title"] == "Not authenticated"


def test_only_admin_holds_settings_permission() -> None:
    assert [role for role in Role if Permission.SETTINGS in permissions_for(role)] == [Role.ADMIN]


def _calls(dependant: Dependant) -> set[Any]:
    found = {dependant.call}
    for sub in dependant.dependencies:
        found |= _calls(sub)
    return found


def _declared_routes() -> list[tuple[str, APIRoute]]:
    # FastAPI 0.141 wraps included routers lazily, so read the original routers from ROUTERS.
    return [
        (prefix + route.path, route)
        for router, prefix in ROUTERS
        for route in router.routes
        if isinstance(route, APIRoute)
    ]


def test_every_non_public_route_requires_a_principal() -> None:
    """Deny by default: any route added later without an auth dependency fails here."""
    routes = _declared_routes()
    assert {path for path, _ in routes} >= PUBLIC_PATHS  # the check below cannot pass vacuously
    unprotected = [
        f"{sorted(route.methods)} {path}"
        for path, route in routes
        if path not in PUBLIC_PATHS and current_principal not in _calls(route.dependant)
    ]
    assert unprotected == []


def test_every_served_path_is_declared_in_routers(app: FastAPI) -> None:
    assert set(app.openapi()["paths"]) == {path for path, _ in _declared_routes()}
```

- [ ] **Step 17: Run the API tests and see them fail**

Run: `docker compose run --rm tools pytest tests/api -q`
Expected: `ImportError while loading conftest '/app/tests/conftest.py'` with `ModuleNotFoundError: No module named 'mdcopilot_blog.api.app'`. Until Step 23 is done, every pytest run fails this way, because the conftest imports the app.

- [ ] **Step 18: Implement the dependencies**

Create `backend/src/mdcopilot_blog/api/deps.py`:

```python
"""FastAPI dependencies: app state accessors, the authenticated principal, RBAC and CSRF."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.auth.csrf import SAFE_METHODS, csrf_token_for, origin_allowed, tokens_match
from mdcopilot_blog.auth.sessions import resolve_session
from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import permissions_for
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClientProtocol

LOGIN_PATH = "/api/auth/login"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _state(request: Request, name: str) -> Any:
    """app.state first (set by create_app, the lifespan and test fixtures), then lifespan-provided request.state."""
    value = getattr(request.app.state, name, None)
    if value is None:
        value = getattr(request.state, name, None)
    if value is None:
        raise RuntimeError(f"application state {name!r} is not initialised")
    return value


def get_settings_dep(request: Request) -> Settings:
    return cast(Settings, _state(request, "settings"))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = cast(async_sessionmaker[AsyncSession], _state(request, "sessionmaker"))
    async with sessionmaker() as session:
        yield session


def get_workflow_client(request: Request) -> WorkflowClientProtocol:
    return cast(WorkflowClientProtocol, _state(request, "workflow_client"))


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
WorkflowClientDep = Annotated[WorkflowClientProtocol, Depends(get_workflow_client)]


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str
    display_name: str
    role: Role
    permissions: frozenset[Permission]
    session_token: str


async def current_principal(request: Request, db: SessionDep, settings: SettingsDep) -> Principal:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise ProblemError(401, "Not authenticated")
    resolved = await resolve_session(db, token, now=utcnow())
    if resolved is None:
        raise ProblemError(401, "Not authenticated")
    await db.commit()  # persists the throttled last_seen_at touch
    user = resolved.user
    role = Role(user.role)
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=role,
        permissions=permissions_for(role),
        session_token=token,
    )


PrincipalDep = Annotated[Principal, Depends(current_principal)]


def require_permission(permission: Permission) -> Callable[..., Awaitable[Principal]]:
    async def _require(principal: PrincipalDep) -> Principal:
        if permission not in principal.permissions:
            raise ProblemError(403, "Forbidden", f"missing permission {permission.value}")
        return principal

    return _require


async def enforce_csrf(request: Request, settings: SettingsDep) -> None:
    """App-wide guard for unsafe methods: Fetch Metadata, then Origin, then the session-bound token."""
    if request.method in SAFE_METHODS:
        return
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None and fetch_site != "same-origin":
        raise ProblemError(403, "Cross-site request blocked")
    if not origin_allowed(
        request.headers.get("origin"),
        host=request.headers.get("host"),
        forwarded_proto=request.headers.get("x-forwarded-proto"),
        scheme=request.url.scheme,
        public_app_url=settings.public_app_url,
    ):
        raise ProblemError(403, "Origin not allowed")
    if request.url.path == LOGIN_PATH:
        return
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        return  # no session: the route's auth dependency answers 401
    expected = csrf_token_for(session_token, settings.session_secret.get_secret_value())
    if not tokens_match(expected, request.headers.get("x-csrf-token", "")):
        raise ProblemError(403, "CSRF token missing or invalid")
```

- [ ] **Step 19: Implement the health router**

Create `backend/src/mdcopilot_blog/api/routers/__init__.py`:

```python
"""API routers. Each module exposes `router`; api.app.ROUTERS decides the prefixes."""
```

Create `backend/src/mdcopilot_blog/api/routers/health.py`:

```python
"""Liveness and readiness probes (no auth)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mdcopilot_blog.api.deps import SessionDep
from mdcopilot_blog.errors import problem_response

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
async def readyz(request: Request, db: SessionDep) -> dict[str, str] | JSONResponse:
    try:
        await db.execute(text("select 1"))
    except (SQLAlchemyError, OSError):
        return problem_response(request, 503, "Database unavailable")
    return {"status": "ok", "database": "ok"}
```

- [ ] **Step 20: Implement the auth router**

Create `backend/src/mdcopilot_blog/api/routers/auth.py`:

```python
"""Login, logout and the current session."""

import uuid

from fastapi import APIRouter, Request, Response

from mdcopilot_blog.api.deps import PrincipalDep, SessionDep, SettingsDep, utcnow
from mdcopilot_blog.api.schemas import LoginRequest, SessionResponse, SessionUser
from mdcopilot_blog.auth.csrf import csrf_token_for
from mdcopilot_blog.auth.rate_limit import login_allowed, record_login_attempt
from mdcopilot_blog.auth.sessions import ABSOLUTE_TIMEOUT, create_session, revoke_session
from mdcopilot_blog.auth.users import authenticate, normalize_email
from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import permissions_for
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.settings import Settings

router = APIRouter(tags=["auth"])


def _session_response(
    *, user_id: uuid.UUID, email: str, display_name: str, role: Role, token: str, settings: Settings
) -> SessionResponse:
    permissions: list[Permission] = sorted(permissions_for(role))
    return SessionResponse(
        user=SessionUser(id=user_id, email=email, display_name=display_name, role=role, permissions=permissions),
        csrf_token=csrf_token_for(token, settings.session_secret.get_secret_value()),
    )


def _client_ip(request: Request) -> str | None:
    # uvicorn rewrites request.client from X-Forwarded-For only for peers listed in --forwarded-allow-ips.
    # That list must hold only the real proxy (Task 14), or the per-IP login limit can be bypassed.
    return request.client.host if request.client else None


@router.post("/login", response_model=SessionResponse)
async def login(
    body: LoginRequest, request: Request, response: Response, db: SessionDep, settings: SettingsDep
) -> SessionResponse:
    now = utcnow()
    email = normalize_email(body.email)
    ip = _client_ip(request)
    if not await login_allowed(db, email=email, ip=ip, now=now):
        raise ProblemError(429, "Too many login attempts")
    user = await authenticate(db, email=email, password=body.password)
    if user is None:
        await record_login_attempt(db, email=email, ip=ip, succeeded=False)
        await db.commit()
        raise ProblemError(401, "Invalid email or password")
    previous = request.cookies.get(settings.session_cookie_name)
    if previous:
        await revoke_session(db, previous, now=now)  # never keep two live sessions for one browser
    token = await create_session(db, user, ip=ip, user_agent=request.headers.get("user-agent"), now=now)
    await record_login_attempt(db, email=email, ip=ip, succeeded=True)
    await audit(db, actor_user_id=user.id, action="auth.login", entity_type="user", entity_id=str(user.id))
    await db.commit()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=int(ABSOLUTE_TIMEOUT.total_seconds()),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return _session_response(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=Role(user.role),
        token=token,
        settings=settings,
    )


@router.post("/logout", status_code=204)
async def logout(principal: PrincipalDep, db: SessionDep, settings: SettingsDep) -> Response:
    await revoke_session(db, principal.session_token, now=utcnow())
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="auth.logout",
        entity_type="user",
        entity_id=str(principal.user_id),
    )
    await db.commit()
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/session", response_model=SessionResponse)
async def session(principal: PrincipalDep, response: Response, settings: SettingsDep) -> SessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return _session_response(
        user_id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        role=principal.role,
        token=principal.session_token,
        settings=settings,
    )
```

- [ ] **Step 21: Implement the users router**

Create `backend/src/mdcopilot_blog/api/routers/users.py`:

```python
"""Admin user management (blog.settings)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from mdcopilot_blog.api.deps import Principal, SessionDep, require_permission, utcnow
from mdcopilot_blog.api.schemas import UserCreate, UserOut, UserUpdate
from mdcopilot_blog.auth.sessions import revoke_user_sessions
from mdcopilot_blog.auth.users import UserExists, create_user, set_password
from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.audit import audit

router = APIRouter(tags=["users"])

AdminDep = Annotated[Principal, Depends(require_permission(Permission.SETTINGS))]


@router.get("", response_model=list[UserOut])
async def list_users(_: AdminDep, db: SessionDep) -> list[UserOut]:
    users = (await db.scalars(select(User).order_by(User.created_at, User.email))).all()
    return [UserOut.model_validate(user) for user in users]


@router.post("", status_code=201, response_model=UserOut)
async def create_user_route(body: UserCreate, principal: AdminDep, db: SessionDep) -> UserOut:
    try:
        user = await create_user(
            db, email=body.email, display_name=body.display_name, role=body.role, password=body.password
        )
    except UserExists:
        raise ProblemError(409, "User already exists") from None
    except ValueError as exc:
        raise ProblemError(422, "Request validation failed", str(exc)) from None
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="user.create",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email, "role": user.role},
    )
    await db.commit()
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user_route(user_id: uuid.UUID, body: UserUpdate, principal: AdminDep, db: SessionDep) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise ProblemError(404, "User not found")
    is_self = user.id == principal.user_id
    new_role = body.role.value if body.role is not None else None
    if is_self and new_role is not None and new_role != user.role:
        raise ProblemError(409, "You cannot change your own role")
    if is_self and body.is_active is False:
        raise ProblemError(409, "You cannot deactivate yourself")

    now = utcnow()
    changes: dict[str, object] = {}
    if new_role is not None and new_role != user.role:
        changes["role"] = {"from": user.role, "to": new_role}
        user.role = new_role
    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
        if not body.is_active:
            await revoke_user_sessions(db, user.id, now=now)
    if body.password is not None:
        try:
            await set_password(user, body.password)
        except ValueError as exc:
            raise ProblemError(422, "Request validation failed", str(exc)) from None
        changes["password"] = "changed"
        # Everyone signed in with the old password is signed out, except the admin making the change.
        await revoke_user_sessions(db, user.id, now=now, keep_token=principal.session_token if is_self else None)
    if changes:
        await db.flush()
        await audit(
            db,
            actor_user_id=principal.user_id,
            action="user.update",
            entity_type="user",
            entity_id=str(user.id),
            details=changes,
        )
        await db.commit()
    return UserOut.model_validate(user)
```

- [ ] **Step 22: Implement the settings router**

Create `backend/src/mdcopilot_blog/api/routers/settings.py`:

```python
"""Read-only view of the effective configuration. Provider keys are masked."""

from typing import Annotated

from fastapi import APIRouter, Depends

from mdcopilot_blog.api.deps import Principal, SettingsDep, require_permission
from mdcopilot_blog.api.schemas import SettingsView, mask_secret
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.settings import Settings

router = APIRouter(tags=["settings"])


def build_settings_view(settings: Settings) -> SettingsView:
    return SettingsView(
        app_version=settings.app_version,
        mock_mode=settings.mock_mode,
        agent_enabled=settings.agent_enabled,
        scheduler_enabled=settings.scheduler_enabled,
        publishing_enabled=settings.publishing_enabled,
        gemini_grounding_enabled=settings.gemini_grounding_enabled,
        human_approval_required=settings.human_approval_required,
        schedule={"dailyRunTime": settings.daily_run_time, "timezone": settings.timezone},
        routes=settings.route_values(),
        limits={
            "maxCostPerRunUsd": str(settings.max_cost_per_run_usd),
            "discoveryTimeoutMinutes": settings.discovery_timeout_minutes,
            "productionTimeoutMinutes": settings.production_timeout_minutes,
            "maxParallelSearches": settings.max_parallel_searches,
            "maxParallelFetches": settings.max_parallel_fetches,
            "researchWindowDays": settings.research_window_days,
            "minSourceCount": settings.min_source_count,
            "noveltyThreshold": settings.novelty_threshold,
            "wordCountMin": settings.word_count_min,
            "wordCountMax": settings.word_count_max,
        },
        publisher=settings.publisher,
        providers={
            "openai": mask_secret(settings.openai_api_key),
            "gemini": mask_secret(settings.gemini_api_key),
            "anthropic": mask_secret(settings.anthropic_api_key),
            "ncbi": mask_secret(settings.ncbi_api_key),
        },
    )


@router.get("/settings", response_model=SettingsView)
async def get_settings_view(
    _: Annotated[Principal, Depends(require_permission(Permission.SETTINGS))], settings: SettingsDep
) -> SettingsView:
    return build_settings_view(settings)
```

- [ ] **Step 23: Implement the app factory**

Create `backend/src/mdcopilot_blog/api/app.py`. Task 12 extends `ROUTERS` with the two-line edit given under Interfaces.

```python
"""FastAPI application factory. uvicorn target: `uvicorn --factory mdcopilot_blog.api.app:create_app`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI

from mdcopilot_blog.api.deps import enforce_csrf
from mdcopilot_blog.api.routers import auth as auth_routes
from mdcopilot_blog.api.routers import health as health_routes
from mdcopilot_blog.api.routers import settings as settings_routes
from mdcopilot_blog.api.routers import users as users_routes
from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.errors import install_problem_handlers
from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.settings import Settings, get_settings
from mdcopilot_blog.workflows.client import WorkflowClient, WorkflowClientProtocol

# (router, prefix) in registration order. Task 12 appends the runs router here.
ROUTERS: tuple[tuple[APIRouter, str], ...] = (
    (health_routes.router, ""),
    (auth_routes.router, "/api/auth"),
    (users_routes.router, "/api/admin/users"),
    (settings_routes.router, "/api/blog-agent"),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url())
    sessionmaker = make_sessionmaker(engine)
    injected: WorkflowClientProtocol | None = app.state.injected_workflow_client
    client = injected if injected is not None else WorkflowClient.from_settings(settings)
    # Deps read app.state first, so assign it as well as yielding lifespan state.
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.workflow_client = client
    try:
        yield {"settings": settings, "engine": engine, "sessionmaker": sessionmaker, "workflow_client": client}
    finally:
        await asyncio.to_thread(client.close)
        await engine.dispose()


def create_app(settings: Settings | None = None, *, workflow_client: WorkflowClientProtocol | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    app = FastAPI(
        title="MDCopilot Blog Intelligence API",
        version=resolved.app_version,
        lifespan=lifespan,
        dependencies=[Depends(enforce_csrf)],
    )
    app.state.settings = resolved
    app.state.injected_workflow_client = workflow_client
    install_problem_handlers(app)
    for router, prefix in ROUTERS:
        app.include_router(router, prefix=prefix)
    return app
```

- [ ] **Step 24: Run the API tests and see them pass**

Run: `docker compose run --rm tools pytest tests/api -q`
Expected: `84 passed` (auth 11, csrf 14, health 7, problem_errors 11, rbac 27, settings 4, users 10).

- [ ] **Step 25: Run every Task 7 and Task 9 test together**

Run: `docker compose run --rm tools pytest tests/unit tests/db tests/api -q`
Expected, when Tasks 1–9 have run in order and no later task has: `994 passed`, with no failures or errors. That is Tasks 1–8's 899 (Task 8's verification note) plus this task's 95. Task 7 and Task 9 contribute 149 of them (54 + 95). Every test that exists after Task 9 lives in `tests/unit`, `tests/db` or `tests/api`, so this is also the whole suite at this point.

- [ ] **Step 26: Smoke-test the real uvicorn factory**

This starts the production entry point inside the tools container. It checks that the lifespan builds the engine and a lazy DBOSClient, and that errors are problem+json.

Run:

```bash
docker compose run --rm tools python -c "
import subprocess, time, urllib.error, urllib.request
server = subprocess.Popen(['uvicorn', '--factory', 'mdcopilot_blog.api.app:create_app', '--port', '8000', '--log-level', 'warning'])
try:
    for _ in range(50):
        try:
            print(urllib.request.urlopen('http://127.0.0.1:8000/healthz').read().decode())
            break
        except OSError:
            time.sleep(0.2)
    print(urllib.request.urlopen('http://127.0.0.1:8000/readyz').read().decode())
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/api/auth/session')
    except urllib.error.HTTPError as exc:
        print(exc.code, exc.headers['content-type'], exc.read().decode())
finally:
    server.terminate()
    server.wait(timeout=10)
"
```

Expected output, after two DBOS `INFO` lines that print the URL with the password masked as `***`:

```text
{"status":"ok"}
{"status":"ok","database":"ok"}
401 application/problem+json {"type":"about:blank","title":"Not authenticated","status":401,"instance":"/api/auth/session"}
```

`/readyz` returns `ok` only if the `mdcopilot_blog` database exists. Task 14's `migrate` service creates the schema later; `select 1` needs no tables.

- [ ] **Step 27: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, when Tasks 1–9 have run in order and no later task has:
```text
All checks passed!
78 files already formatted
Success: no issues found in 43 source files
```
- **78** is Task 8's 57 plus this task's 21 `.py` files (12 under `src/`, 9 tests).
- **43** is Task 8's 31 plus this task's 12 modules (`workflows/` 3, `api/` 4, `api/routers/` 5).
- A lower count means a file from the Files lists is missing.

If `ruff check` flags import order in `tests/conftest.py` after the merge in Step 10, run `docker compose run --rm tools ruff check --fix tests/conftest.py` and re-run the check.

- [ ] **Step 28: Checkpoint: list files changed (no git)**

Created:
- `backend/src/mdcopilot_blog/workflows/__init__.py`, `names.py`, `client.py`
- `backend/src/mdcopilot_blog/api/__init__.py`, `schemas.py`, `deps.py`, `app.py`
- `backend/src/mdcopilot_blog/api/routers/__init__.py`, `health.py`, `auth.py`, `users.py`, `settings.py`
- `backend/tests/unit/test_workflow_client.py`, `backend/tests/unit/test_api_schemas.py`
- `backend/tests/db/test_workflow_client_db.py`
- `backend/tests/api/test_health.py`, `test_auth_api.py`, `test_users_api.py`, `test_settings_api.py`, `test_csrf_api.py`, `test_rbac_routes.py`

Modified:
- `backend/tests/conftest.py` (T9 imports and block)

---

### Task 10: LLM gateway, search and publisher interfaces (mock)

This task builds the whole LLM access layer with mock implementations only (ARCHITECTURE §7.1, §14, §18, §20). It has five parts:
- route parsing from Settings;
- the per-call recorder (`app.blog_llm_calls`);
- `LLMGateway.run/search/embed`, which walks routes with fallback, budget checks and error classification;
- the Pydantic AI `FunctionModel` fixture factory, plus the `FixtureSearchProvider` and `NullPublisher` interfaces.

No real provider client is built in Phase 1. In mock mode `models.ALLOW_MODEL_REQUESTS` is set to `False`. Outside mock mode, building a model, searching or embedding raises `ProviderNotAvailable`.

**Verified.** Every file below was run exactly as written, on 2026-09-17, in the same throwaway environment as Task 6.
- **Environment:** `uv lock` from this plan's `pyproject.toml` gave pydantic-ai-slim 2.43.0, httpx 0.28.1, httpx2 2.13.0, genai-prices 0.1.7, dbos 3.0.0 and sqlalchemy 2.0.54. The database was `pgvector/pgvector:pg16`.
- **Stand-ins for other tasks:** Task 1/2/4/5 pieces were contract-faithful stand-ins. The enums are identical to Task 4. `LlmCall`, `BlogRun` and `PromptVersion` have the contract's columns. The conftest has `settings`, `db_session`, `sessionmaker_committing` and `clean_db`.
- **Test results:**

  | File | Result |
  |---|---|
  | routes | 23 passed |
  | search | 4 passed |
  | publisher | 5 passed |
  | gateway + recorder | 26 passed |
  | this task in total | **58 passed** |
  | with Task 6 | **73 passed** |

  Each red step failed with the `ModuleNotFoundError` quoted below.
- **Robustness:** the same 73 passed a second time under three changes: fake `OPENAI_API_KEY`/`GEMINI_API_KEY`/`ANTHROPIC_API_KEY` in the environment, `BLOG_AGENT_MOCK_MODE=false` and an overridden writer route. It also passed without `tests/unit/__init__.py` or `tests/db/__init__.py`.
- **Lint and types:** `ruff check`, `ruff format --check` and `mypy src` were clean. mypy strict was also clean on all 7 test files.
- **Other checks:** importing `mdcopilot_blog.llm.mock` first, or `llm.recorder` first, works (no import cycle), and leaves `ALLOW_MODEL_REQUESTS` at `True`. `FunctionModel(...).system == "function"`, `OpenAIChatModel(...).system == "openai"`, and `RouteExhausted` survives a `pickle` round trip.

**Design decisions** (read these before Task 11/12 use the gateway)
- **Mock mode and anthropic.** The contract's route bullets conflict for `anthropic` in mock mode. This task follows the final bullet and the test list: **mock mode returns the route unfiltered** (every provider, `anthropic` included), because the mock factory ignores the provider.
  - **Outside mock mode:** `openai`, `google` and `anthropic` entries are dropped when `OPENAI_API_KEY`, `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` (respectively) is unset. `mock:` entries need no key.
  - **Empty routes:** an empty result raises `ValueError("no usable model route for agent '<name>'")`.
  - **HELLO:** `AgentName.HELLO` always uses `("mock:hello",)`.
  - **Parsing:** `parse_choice` splits on the first `:`, trims whitespace, and is case-sensitive about the provider (`OpenAI:` is rejected).
- **Generic syntax.** `AgentSpec`, `AgentResult` and `LLMGateway.run` use **PEP 695 generics** (`class AgentSpec[OutputT: BaseModel]`), because ruff 0.16.8's default `UP046` rejects `Generic[OutputT]` with a module-level `TypeVar`. The call sites the contract describes are unchanged: `AgentSpec(name=..., output_type=EchoOutput, ...)` infers `AgentSpec[EchoOutput]`. There is no module-level `OutputT` to import.
- **Budget checks.** The budget is checked before the prompt is rendered (contract step 1), and **again before every fallback model**, because ARCHITECTURE §7.1 says "the per-run cost cap is checked before each call". `search()` checks it too. `embed()` does not, since it is mock-only and costs nothing.
- **Which errors move the route on.** The route advances on `(ModelAPIError, UnexpectedModelBehavior, httpx.TransportError, httpx2.TransportError)`. `ModelHTTPError` is a subclass of `ModelAPIError`, so it advances too.
  - **Recorded, then re-raised:** anything else, including `UsageLimitExceeded`, the plain `RuntimeError` raised when `ALLOW_MODEL_REQUESTS` is `False`, `ProviderNotAvailable`, a missing fixture (`FileNotFoundError`) and bugs (`ValueError`).
  - **Not recorded:** `asyncio.CancelledError` is a `BaseException`, so it is not caught.
- **One row per attempt.** Every model attempt writes exactly one row, whether it succeeds or fails.
  - **Usage of failed attempts:** a failed attempt's usage comes from `pydantic_ai.capture_run_messages()`, so the tokens of exhausted output retries are still accounted (verified: 2 failed requests of 10/3 tokens are recorded as 20/6).
  - `attempt_index` is the route index.
  - `fallback_from` is the previous choice's ref (`"openai:model-a"`), or `None` for the first choice.
  - `AgentResult.attempts` is `index + 1`.
- **Served provider and model.**
  - `provider_served` is `ModelResponse.provider_name` when present, else `model.system`: `"function"` for mock `FunctionModel`, `"openai"` for `OpenAIChatModel`.
  - `model_served` is the last response's `model_name`. The mock factory sets this to `mock:<agent>`.
- **What gets recorded.**
  - `params` is `{"max_tokens", "timeout", "output_retries", "agent_version"}`.
  - `usage_raw` is `{"requests": [...]}` with JSON-safe values; cost is a string.
  - `cost_usd` is the sum of `usage.cost or 0`, which is always 0 for `FunctionModel`.
- **Instructions whitespace.** Pydantic AI strips surrounding whitespace from `instructions`: the rendered `"Write about x.\n"` arrives as `"Write about x."`.
- **Error pickling.** `RouteExhausted(agent, failures)` implements `__reduce__`, because DBOS 3.0.0 pickles step errors (see Task 4's note on `InvalidTransition`). `str(exc)` is `"all models failed for agent 'writer': openai:model-a (ModelHTTPError), ..."`.
- **Import cycle.** `recorder.py` imports `CallContext` only under `TYPE_CHECKING` (with `from __future__ import annotations`), and `build_model_factory` imports `llm.mock` inside the function, because `mock.py` imports `AgentSpec` and `ModelFactory` from `gateway.py`.
- **Outside mock mode.**
  - `build_model_factory` returns `UnavailableModelFactory`.
  - `build_gateway` wires `UnavailableSearchProvider` (`name="unavailable"`), which is not in the contract but is needed so that non-mock search raises `ProviderNotAvailable` instead of silently returning fixtures.
  - `embed()` raises `ProviderNotAvailable` before recording anything.
- **Search rows.**
  - `provider_requested` and `model_requested` are both `search_provider.name`.
  - `provider_served` and `model_served` come from the `SearchResult`.
  - `agent_name` is `"search"` and `params` is `query.model_dump(mode="json")`.
  - A provider exception writes an `error` row and is re-raised.
- **Embedding rows.**
  - `provider_requested` and `model_requested` are parsed from `BLOG_AGENT_EMBEDDING_MODEL`.
  - The served values are `mock` / `mock:embedding`.
  - `input_tokens` is the whitespace word count.
  - Vectors are `random.Random(int(sha256(text)))` uniforms in [-1, 1], of length `embedding_dimensions`.
- **Fixture roots.** The LLM root is `parents[3]/fixtures/mock/llm` and the search root is `parents[4]/fixtures/mock/search`, with a `Path.cwd()` fallback for the non-editable runtime image (same reason as Task 6). `FixtureSearchProvider(root)` takes the **directory** that holds `default.json`.
- **Fixture checks.**
  - A missing fixture raises `FileNotFoundError("no mock fixture for agent 'x' prompt 'y': expected <path>")`.
  - A non-object file, or one without an `output` object, raises `TypeError`.
  - A malformed `usage` raises `ValueError`.
  - Fixture output is deep-copied for every response.
- **NullPublisher.** It subclasses the `BlogPublisher` Protocol explicitly.
  - A repeat `publish` with the same key returns the **stored** result (same `external_id` and `published_at`) and keeps one entry.
  - `as_draft=True` is remembered, so `find_existing` reports `status="draft"`.
- **Test settings.** Tests take Task 5's `settings` fixture and derive variants with `settings.model_copy(update={...})`, so values in `.env` never affect them.

**Files:**
- Create: `backend/src/mdcopilot_blog/llm/__init__.py`
- Create: `backend/src/mdcopilot_blog/llm/routes.py`
- Create: `backend/src/mdcopilot_blog/llm/recorder.py`
- Create: `backend/src/mdcopilot_blog/llm/gateway.py`
- Create: `backend/src/mdcopilot_blog/llm/mock.py`
- Create: `backend/src/mdcopilot_blog/llm/search/__init__.py`
- Create: `backend/src/mdcopilot_blog/llm/search/base.py`
- Create: `backend/src/mdcopilot_blog/llm/search/fixture.py`
- Create: `backend/src/mdcopilot_blog/publishing/__init__.py`
- Create: `backend/src/mdcopilot_blog/publishing/base.py`
- Create: `backend/src/mdcopilot_blog/publishing/null.py`
- Create: `backend/fixtures/mock/llm/hello/hello_echo.json`
- Create: `backend/fixtures/mock/search/default.json`
- Test: `backend/tests/unit/test_routes.py`
- Test: `backend/tests/unit/test_search_fixture.py`
- Test: `backend/tests/unit/test_null_publisher.py`
- Test: `backend/tests/unit/test_gateway.py`
- Test: `backend/tests/db/test_recorder.py`

**Interfaces:**
- **Consumes:**
  - Task 1: `mdcopilot_blog.ids.uuid7`, `new_trace_id`; the dependencies `pydantic-ai-slim[openai,google,anthropic]`, `httpx`, `httpx2`.
  - Task 2: `mdcopilot_blog.settings.Settings` fields `mock_mode`, `openai_api_key`, `gemini_api_key`, `anthropic_api_key`, `search_route`, `research_route`, `ideation_route`, `deep_research_route`, `writer_route`, `fact_check_route`, `clinical_route`, `editorial_route`, `seo_route` (each `list[str]`), `embedding_model`, `embedding_dimensions`, `max_cost_per_run_usd`.
  - Task 4: `mdcopilot_blog.domain.enums.AgentName` (`SEARCH ... SEO, HELLO`), `CallKind` (`AGENT, SEARCH, EMBEDDING`), `CallStatus` (`OK, ERROR`), `PublicationStatus.PUBLISHED`.
  - Task 5: `mdcopilot_blog.db.models.LlmCall` and `BlogRun`; the conftest fixtures `settings`, `sessionmaker_committing` and `clean_db`.
  - Task 6: `PromptRegistry`, `RenderedPrompt`, `default_prompt_root`, and the prompt `hello/echo` v1.
- **Produces** (module `mdcopilot_blog.llm.routes`):
  - `Provider = Literal["openai","google","anthropic","mock"]`
  - `HELLO_ROUTE = ("mock:hello",)`
  - `@dataclass(frozen=True) class ModelChoice(provider: Provider, model: str)`, with `.ref() -> str`
  - `parse_choice(raw: str) -> ModelChoice`
  - `route_for(settings: Settings, agent: AgentName) -> tuple[ModelChoice, ...]`
- **Produces** (module `mdcopilot_blog.llm.recorder`):
  - `ERROR_MESSAGE_LIMIT = 2000`
  - `PRICE_VERSION = "genai-prices==0.1.7"`
  - `@dataclass(frozen=True) class CallRecord(...)`, with exactly the contract's fields
  - `class CallRecorder(sessionmaker)`:
    - `async record(rec: CallRecord) -> uuid.UUID` (own session, commits)
    - `async run_cost(run_id: uuid.UUID | None) -> Decimal`
- **Produces** (module `mdcopilot_blog.llm.gateway`):
  - `ADVANCE_ERRORS`
  - `@dataclass(frozen=True) class AgentSpec[OutputT: BaseModel](name: AgentName, version: str, prompt_name: str, output_type: type[OutputT], max_output_tokens: int, output_retries: int = 1, timeout_seconds: float = 120.0)`
  - `@dataclass(frozen=True) class CallContext(trace_id: str, run_id=None, attempt_id=None, agent_run_id=None, dbos_workflow_id=None, dbos_step_id=None, article_id=None, topic_candidate_id=None)`
  - `@dataclass(frozen=True) class AgentResult[OutputT: BaseModel](output, provider, model, attempts, input_tokens, output_tokens, cost_usd)`
  - Exceptions:
    - `GatewayError(RuntimeError)`
    - `BudgetExceeded(GatewayError)`
    - `RouteExhausted(GatewayError)(agent: str, failures: Sequence[tuple[str, str]])`, with `.agent` and `.failures: list[tuple[str, str]]`
    - `ProviderNotAvailable(GatewayError)`
  - Factories and providers:
    - `ModelFactory(Protocol).build(choice, spec) -> pydantic_ai.models.Model`
    - `UnavailableModelFactory`
    - `UnavailableSearchProvider`
    - `mock_embedding(text: str, dimensions: int) -> list[float]`
  - `class LLMGateway(*, settings, prompts, recorder, model_factory, search_provider)`:
    - `async run(spec, *, variables, user_prompt, ctx) -> AgentResult[OutputT]`
    - `async search(query, *, ctx) -> SearchResult`
    - `async embed(texts, *, ctx) -> list[list[float]]`
  - `build_model_factory(settings) -> ModelFactory`
  - `build_gateway(settings, sessionmaker, prompts) -> LLMGateway`
- **Produces** (module `mdcopilot_blog.llm.mock`):
  - `default_llm_fixture_root() -> Path`
  - `class FixtureRegistry(root: Path)`:
    - `.default()`
    - `.path_for(agent, prompt_name) -> Path`
    - `.load(agent, prompt_name) -> dict[str, Any]`
  - `class MockModelFactory(fixtures: FixtureRegistry)`, whose `.build(...)` returns `FunctionModel(..., model_name="mock:<agent>")`
- **Produces** (module `mdcopilot_blog.llm.search.base`):
  - `SearchQuery`
  - `Citation`
  - `SearchResult`
  - `WebSearchProvider(Protocol)`, with `name: str` and `async search(query) -> SearchResult`
- **Produces** (module `mdcopilot_blog.llm.search.fixture`):
  - `default_search_fixture_root() -> Path`
  - `class FixtureSearchProvider(root: Path | None = None)`, with `name = "fixture"`
- **Produces** (module `mdcopilot_blog.publishing.base`):
  - `PublishPayload`
  - `PublisherCapabilities`
  - `RemotePost`
  - `PublicationResult`
  - `Issue`
  - `BlogPublisher(Protocol)`
- **Produces** (module `mdcopilot_blog.publishing.null`): `class NullPublisher`, with `key = "null"` and `.published: dict[str, PublishPayload]`.
- **Fixture files:**
  - `fixtures/mock/llm/hello/hello_echo.json`: output `{"message": "Hello from the mock gateway", "word_count": 5}`, usage 20/8.
  - `fixtures/mock/search/default.json`.
- **For Task 11:**
  - `build_gateway(settings, sessionmaker, prompts)` is the only constructor the worker needs.
  - `gateway.run(HELLO_SPEC, variables={"brand_name": "MDCopilot", "topic": "hello"}, user_prompt="Say hello.", ctx=handle.call_context())` returns `AgentResult[EchoOutput]` with `model == "mock:hello"`, `input_tokens == 20`, `output_tokens == 8` and `cost_usd == 0`.
  - It writes one `blog_llm_calls` row with `agent_run_id = ctx.agent_run_id`.

**Part A: model routes**

- [ ] **Step 1: Write the failing route tests**

Create `backend/tests/unit/test_routes.py`:

```python
"""Route parsing and key-based filtering."""

import pytest
from pydantic import SecretStr

from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.llm.routes import ModelChoice, parse_choice, route_for
from mdcopilot_blog.settings import Settings

WRITER_ROUTE = ["openai:gpt-test-sol", "google:gemini-test-flash", "anthropic:claude-test"]


def configure(settings: Settings, *, mock_mode: bool, openai: bool, gemini: bool, anthropic: bool) -> Settings:
    return settings.model_copy(
        update={
            "mock_mode": mock_mode,
            "openai_api_key": SecretStr("sk-test-openai") if openai else None,
            "gemini_api_key": SecretStr("test-gemini") if gemini else None,
            "anthropic_api_key": SecretStr("test-anthropic") if anthropic else None,
            "writer_route": list(WRITER_ROUTE),
        }
    )


def test_parse_choice_valid() -> None:
    choice = parse_choice(" openai : gpt-5.6-sol ")
    assert choice == ModelChoice(provider="openai", model="gpt-5.6-sol")
    assert choice.ref() == "openai:gpt-5.6-sol"
    assert parse_choice("google:gemini-3.8-flash").provider == "google"
    assert parse_choice("anthropic:claude-sonnet-5").provider == "anthropic"
    assert parse_choice("mock:hello") == ModelChoice(provider="mock", model="hello")


@pytest.mark.parametrize("raw", ["gpt-5.6-sol", "openai:", ":gpt-5.6-sol", "", "azure:gpt-5", "OpenAI:gpt-5"])
def test_parse_choice_rejects_bad_entries(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid model route entry"):
        parse_choice(raw)


def test_real_mode_drops_providers_without_keys(settings: Settings) -> None:
    only_openai = configure(settings, mock_mode=False, openai=True, gemini=False, anthropic=False)
    assert route_for(only_openai, AgentName.WRITER) == (ModelChoice("openai", "gpt-test-sol"),)

    no_anthropic = configure(settings, mock_mode=False, openai=True, gemini=True, anthropic=False)
    assert [c.ref() for c in route_for(no_anthropic, AgentName.WRITER)] == [
        "openai:gpt-test-sol",
        "google:gemini-test-flash",
    ]

    all_keys = configure(settings, mock_mode=False, openai=True, gemini=True, anthropic=True)
    assert [c.ref() for c in route_for(all_keys, AgentName.WRITER)] == WRITER_ROUTE


def test_real_mode_with_no_usable_entry_raises(settings: Settings) -> None:
    no_keys = configure(settings, mock_mode=False, openai=False, gemini=False, anthropic=False)
    with pytest.raises(ValueError, match="no usable model route for agent 'writer'"):
        route_for(no_keys, AgentName.WRITER)


def test_mock_mode_returns_route_unfiltered(settings: Settings) -> None:
    no_keys = configure(settings, mock_mode=True, openai=False, gemini=False, anthropic=False)
    assert [c.ref() for c in route_for(no_keys, AgentName.WRITER)] == WRITER_ROUTE


def test_empty_route_raises_even_in_mock_mode(settings: Settings) -> None:
    empty = settings.model_copy(update={"mock_mode": True, "seo_route": []})
    with pytest.raises(ValueError, match="no usable model route for agent 'seo'"):
        route_for(empty, AgentName.SEO)


def test_invalid_entry_in_settings_raises(settings: Settings) -> None:
    broken = settings.model_copy(update={"mock_mode": True, "seo_route": ["gemini-without-provider"]})
    with pytest.raises(ValueError, match="invalid model route entry"):
        route_for(broken, AgentName.SEO)


@pytest.mark.parametrize("mock_mode", [True, False])
def test_hello_route_is_fixed_mock(settings: Settings, mock_mode: bool) -> None:
    configured = configure(settings, mock_mode=mock_mode, openai=False, gemini=False, anthropic=False)
    assert route_for(configured, AgentName.HELLO) == (ModelChoice("mock", "hello"),)


@pytest.mark.parametrize("agent", [a for a in AgentName if a != AgentName.HELLO])
def test_each_agent_reads_its_own_route_field(settings: Settings, agent: AgentName) -> None:
    field = f"{agent.value}_route"
    configured = settings.model_copy(update={"mock_mode": True, field: [f"mock:{agent.value}-model"]})
    assert route_for(configured, agent) == (ModelChoice("mock", f"{agent.value}-model"),)
```

- [ ] **Step 2: Run the route tests and watch them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_routes.py -q`

Expected: `Interrupted: 1 error during collection` with `E   ModuleNotFoundError: No module named 'mdcopilot_blog.llm'`.

- [ ] **Step 3: Create the `llm` package marker**

Create `backend/src/mdcopilot_blog/llm/__init__.py`:

```python
"""LLM access layer. Only this package imports pydantic_ai or provider SDKs (ARCHITECTURE §7.1)."""
```

- [ ] **Step 4: Implement the routes**

Create `backend/src/mdcopilot_blog/llm/routes.py`:

```python
"""Model routes: ordered ``provider:model`` lists from Settings, filtered by available keys."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.settings import Settings

Provider = Literal["openai", "google", "anthropic", "mock"]

_PROVIDERS: Mapping[str, Provider] = {
    "openai": "openai",
    "google": "google",
    "anthropic": "anthropic",
    "mock": "mock",
}

HELLO_ROUTE: tuple[str, ...] = ("mock:hello",)

_ROUTE_GETTERS: Mapping[AgentName, Callable[[Settings], list[str]]] = {
    AgentName.SEARCH: lambda s: s.search_route,
    AgentName.RESEARCH: lambda s: s.research_route,
    AgentName.IDEATION: lambda s: s.ideation_route,
    AgentName.DEEP_RESEARCH: lambda s: s.deep_research_route,
    AgentName.WRITER: lambda s: s.writer_route,
    AgentName.FACT_CHECK: lambda s: s.fact_check_route,
    AgentName.CLINICAL: lambda s: s.clinical_route,
    AgentName.EDITORIAL: lambda s: s.editorial_route,
    AgentName.SEO: lambda s: s.seo_route,
}


@dataclass(frozen=True)
class ModelChoice:
    provider: Provider
    model: str

    def ref(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_choice(raw: str) -> ModelChoice:
    provider_raw, separator, model = raw.strip().partition(":")
    provider_key = provider_raw.strip()
    model = model.strip()
    if not separator or not provider_key or not model:
        raise ValueError(f"invalid model route entry {raw!r}: expected 'provider:model'")
    provider = _PROVIDERS.get(provider_key)
    if provider is None:
        raise ValueError(f"invalid model route entry {raw!r}: unknown provider {provider_key!r}")
    return ModelChoice(provider=provider, model=model)


def _key_configured(settings: Settings, provider: Provider) -> bool:
    if provider == "openai":
        return settings.openai_api_key is not None
    if provider == "google":
        return settings.gemini_api_key is not None
    if provider == "anthropic":
        return settings.anthropic_api_key is not None
    return True  # "mock" needs no key


def route_for(settings: Settings, agent: AgentName) -> tuple[ModelChoice, ...]:
    """Ordered choices for ``agent``.

    Mock mode returns the route unfiltered (the mock factory ignores the provider).
    Otherwise entries whose provider key is not configured are dropped.
    """
    if agent == AgentName.HELLO:
        raw_route: tuple[str, ...] = HELLO_ROUTE
    else:
        raw_route = tuple(_ROUTE_GETTERS[agent](settings))
    choices = tuple(parse_choice(entry) for entry in raw_route)
    if not settings.mock_mode:
        choices = tuple(choice for choice in choices if _key_configured(settings, choice.provider))
    if not choices:
        raise ValueError(f"no usable model route for agent {agent.value!r}")
    return choices
```

- [ ] **Step 5: Run the route tests and watch them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_routes.py -q`

Expected: `23 passed`.

**Part B: web search interface and fixture provider**

- [ ] **Step 6: Write the failing search tests**

Create `backend/tests/unit/test_search_fixture.py`:

```python
"""FixtureSearchProvider returns the shipped fixture with the query echoed."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from mdcopilot_blog.llm.search.base import SearchQuery, SearchResult, WebSearchProvider
from mdcopilot_blog.llm.search.fixture import FixtureSearchProvider


async def test_default_fixture_is_returned_with_prefixed_answer() -> None:
    provider = FixtureSearchProvider()
    result = await provider.search(SearchQuery(text="specialist wait times"))

    assert provider.name == "fixture"
    assert isinstance(result, SearchResult)
    assert result.provider == "fixture"
    assert result.model == "fixture-search"
    assert result.answer_text.startswith("[fixture] specialist wait times: ")
    assert result.search_actions == 1
    assert len(result.citations) == 2
    assert result.sources == [c.url for c in result.citations]
    assert result.cost_usd == Decimal(0)


async def test_custom_root_is_used(tmp_path: Path) -> None:
    (tmp_path / "default.json").write_text(
        json.dumps(
            {
                "provider": "fixture",
                "model": "custom-model",
                "answer_text": "custom answer",
                "citations": [{"url": "https://example.com/a"}],
                "sources": ["https://example.com/a"],
                "search_actions": 3,
            }
        ),
        encoding="utf-8",
    )
    provider: WebSearchProvider = FixtureSearchProvider(root=tmp_path)
    result = await provider.search(SearchQuery(text="q", allowed_domains=["example.com"], max_results=2))

    assert result.model == "custom-model"
    assert result.answer_text == "[fixture] q: custom answer"
    assert result.search_actions == 3
    assert result.citations[0].title is None
    assert result.input_tokens == 0


async def test_missing_fixture_names_the_path(tmp_path: Path) -> None:
    provider = FixtureSearchProvider(root=tmp_path)
    with pytest.raises(FileNotFoundError, match="default.json"):
        await provider.search(SearchQuery(text="q"))


def test_search_query_defaults() -> None:
    query = SearchQuery(text="q")
    assert query.allowed_domains == []
    assert query.max_results == 10
    assert query.recency_days is None
```

- [ ] **Step 7: Run the search tests and watch them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_search_fixture.py -q`

Expected: `Interrupted: 1 error during collection` with `E   ModuleNotFoundError: No module named 'mdcopilot_blog.llm.search'`.

- [ ] **Step 8: Create the search package marker and the interface**

Create `backend/src/mdcopilot_blog/llm/search/__init__.py`:

```python
"""Web search providers used through LLMGateway.search()."""
```

Create `backend/src/mdcopilot_blog/llm/search/base.py`:

```python
"""Web search provider interface. Real providers arrive in Phase 2."""

from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    text: str
    allowed_domains: list[str] = Field(default_factory=list)
    max_results: int = 10
    recency_days: int | None = None


class Citation(BaseModel):
    url: str
    title: str | None = None
    start_index: int | None = None
    end_index: int | None = None


class SearchResult(BaseModel):
    provider: str
    model: str
    answer_text: str
    citations: list[Citation]
    sources: list[str]
    search_actions: int
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    latency_ms: int = 0


class WebSearchProvider(Protocol):
    name: str

    async def search(self, query: SearchQuery) -> SearchResult: ...
```

- [ ] **Step 9: Implement the fixture provider and its data file**

Create `backend/src/mdcopilot_blog/llm/search/fixture.py`:

```python
"""Deterministic search provider for mock mode and tests."""

import json
from pathlib import Path

from mdcopilot_blog.llm.search.base import SearchQuery, SearchResult


def default_search_fixture_root() -> Path:
    """``backend/fixtures/mock/search`` (editable install), else ``<cwd>/fixtures/mock/search``."""
    candidate = Path(__file__).resolve().parents[4] / "fixtures" / "mock" / "search"
    if candidate.is_dir():
        return candidate
    return Path.cwd() / "fixtures" / "mock" / "search"


class FixtureSearchProvider:
    name = "fixture"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else default_search_fixture_root()

    async def search(self, query: SearchQuery) -> SearchResult:
        path = self.root / "default.json"
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"search fixture not found: {path}") from None
        base = SearchResult.model_validate(json.loads(raw))
        return base.model_copy(update={"answer_text": f"[fixture] {query.text}: {base.answer_text}"})
```

Create `backend/fixtures/mock/search/default.json`:

```json
{
  "provider": "fixture",
  "model": "fixture-search",
  "answer_text": "Specialist wait times remain long, and health systems are piloting AI-assisted triage.",
  "citations": [
    {
      "url": "https://example.org/specialist-access-report",
      "title": "Specialist access report (fixture)",
      "start_index": 0,
      "end_index": 38
    },
    {
      "url": "https://example.org/ai-triage-pilot",
      "title": "AI-assisted triage pilot (fixture)",
      "start_index": 44,
      "end_index": 88
    }
  ],
  "sources": [
    "https://example.org/specialist-access-report",
    "https://example.org/ai-triage-pilot"
  ],
  "search_actions": 1,
  "input_tokens": 0,
  "output_tokens": 0,
  "cost_usd": "0",
  "latency_ms": 0
}
```

- [ ] **Step 10: Run the search tests and watch them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_search_fixture.py -q`

Expected: `4 passed`.

**Part C: publisher interface and NullPublisher**

- [ ] **Step 11: Write the failing publisher tests**

Create `backend/tests/unit/test_null_publisher.py`:

```python
"""NullPublisher: validation, idempotent publish, lookup by slug."""

import uuid

from mdcopilot_blog.domain.enums import PublicationStatus
from mdcopilot_blog.publishing.base import BlogPublisher, PublishPayload
from mdcopilot_blog.publishing.null import NullPublisher


def make_payload(**overrides: object) -> PublishPayload:
    data: dict[str, object] = {
        "article_id": uuid.uuid4(),
        "version_id": uuid.uuid4(),
        "title": "Specialist access in 2026",
        "slug": "specialist-access-2026",
        "html": "<p>Body</p>",
        "excerpt": "Short excerpt",
        "status": "published",
    }
    data.update(overrides)
    return PublishPayload.model_validate(data)


def test_capabilities() -> None:
    publisher: BlogPublisher = NullPublisher()
    caps = publisher.capabilities()
    assert publisher.key == "null"
    assert caps.network is False
    assert caps.supports_update is True
    assert caps.supports_draft is True
    assert caps.seo_fields is True


async def test_validate_requires_title_slug_and_html() -> None:
    publisher = NullPublisher()
    assert await publisher.validate(make_payload()) == []
    issues = await publisher.validate(make_payload(title=" ", slug="", html=""))
    assert [issue.field for issue in issues] == ["title", "slug", "html"]


async def test_publish_is_idempotent_per_key() -> None:
    publisher = NullPublisher()
    payload = make_payload()
    key = str(payload.version_id)

    first = await publisher.publish(payload, idempotency_key=key, as_draft=False)
    second = await publisher.publish(payload, idempotency_key=key, as_draft=False)

    assert first.status == PublicationStatus.PUBLISHED
    assert first.external_id == f"null-{key}"
    assert first.published_url is None
    assert second == first
    assert list(publisher.published) == [key]
    assert publisher.published[key] == payload


async def test_different_keys_create_separate_entries() -> None:
    publisher = NullPublisher()
    one = await publisher.publish(make_payload(slug="one"), idempotency_key="k1", as_draft=False)
    two = await publisher.publish(make_payload(slug="two"), idempotency_key="k2", as_draft=True)
    assert one.external_id != two.external_id
    assert sorted(publisher.published) == ["k1", "k2"]


async def test_find_existing_matches_slug() -> None:
    publisher = NullPublisher()
    payload = make_payload(slug="adopt-me")
    assert await publisher.find_existing(payload) is None

    await publisher.publish(payload, idempotency_key="v1", as_draft=True)
    found = await publisher.find_existing(make_payload(slug="adopt-me", title="Renamed"))
    assert found is not None
    assert found.external_id == "null-v1"
    assert found.slug == "adopt-me"
    assert found.status == "draft"
    assert found.url is None
    assert await publisher.find_existing(make_payload(slug="other")) is None
```

- [ ] **Step 12: Run the publisher tests and watch them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_null_publisher.py -q`

Expected: `Interrupted: 1 error during collection` with `E   ModuleNotFoundError: No module named 'mdcopilot_blog.publishing'`.

- [ ] **Step 13: Create the publishing package and the interface**

Create `backend/src/mdcopilot_blog/publishing/__init__.py`:

```python
"""Blog publishers (ARCHITECTURE §14)."""
```

Create `backend/src/mdcopilot_blog/publishing/base.py`:

```python
"""Publisher interface (ARCHITECTURE §14). Phase 1 ships only NullPublisher."""

import uuid
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from mdcopilot_blog.domain.enums import PublicationStatus


class PublishPayload(BaseModel):
    article_id: uuid.UUID
    version_id: uuid.UUID
    title: str
    slug: str
    html: str
    excerpt: str
    status: Literal["draft", "published"]
    seo: dict[str, object] = Field(default_factory=dict)


class PublisherCapabilities(BaseModel):
    network: bool
    supports_update: bool
    supports_draft: bool
    seo_fields: bool


class RemotePost(BaseModel):
    external_id: str
    slug: str
    status: str
    url: str | None


class PublicationResult(BaseModel):
    status: PublicationStatus
    external_id: str | None
    published_url: str | None
    published_at: datetime | None
    message: str | None = None


class Issue(BaseModel):
    field: str
    message: str


class BlogPublisher(Protocol):
    key: str

    def capabilities(self) -> PublisherCapabilities: ...

    async def validate(self, payload: PublishPayload) -> list[Issue]: ...

    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult: ...

    async def find_existing(self, payload: PublishPayload) -> RemotePost | None: ...
```

- [ ] **Step 14: Implement NullPublisher**

Create `backend/src/mdcopilot_blog/publishing/null.py`:

```python
"""In-memory publisher for mock mode and tests: records payloads, never touches the network."""

from datetime import UTC, datetime

from mdcopilot_blog.domain.enums import PublicationStatus
from mdcopilot_blog.publishing.base import (
    BlogPublisher,
    Issue,
    PublicationResult,
    PublisherCapabilities,
    PublishPayload,
    RemotePost,
)


class NullPublisher(BlogPublisher):
    key = "null"

    def __init__(self) -> None:
        self.published: dict[str, PublishPayload] = {}
        self._results: dict[str, PublicationResult] = {}
        self._drafts: set[str] = set()

    def capabilities(self) -> PublisherCapabilities:
        return PublisherCapabilities(network=False, supports_update=True, supports_draft=True, seo_fields=True)

    async def validate(self, payload: PublishPayload) -> list[Issue]:
        issues: list[Issue] = []
        for field_name in ("title", "slug", "html"):
            if not getattr(payload, field_name).strip():
                issues.append(Issue(field=field_name, message=f"{field_name} must not be empty"))
        return issues

    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult:
        existing = self._results.get(idempotency_key)
        if existing is not None:
            return existing
        self.published[idempotency_key] = payload
        if as_draft:
            self._drafts.add(idempotency_key)
        result = PublicationResult(
            status=PublicationStatus.PUBLISHED,
            external_id=f"null-{idempotency_key}",
            published_url=None,
            published_at=datetime.now(UTC),
            message="recorded by NullPublisher (draft)" if as_draft else "recorded by NullPublisher",
        )
        self._results[idempotency_key] = result
        return result

    async def find_existing(self, payload: PublishPayload) -> RemotePost | None:
        for key, stored in self.published.items():
            if stored.slug == payload.slug:
                return RemotePost(
                    external_id=f"null-{key}",
                    slug=stored.slug,
                    status="draft" if key in self._drafts else "published",
                    url=None,
                )
        return None
```

- [ ] **Step 15: Run the publisher tests and watch them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_null_publisher.py -q`

Expected: `5 passed`.

**Part D: recorder, gateway and mock models**

- [ ] **Step 16: Write the failing recorder test (database)**

Create `backend/tests/db/test_recorder.py`:

```python
"""CallRecorder writes committed rows and sums run cost."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import BlogRun, LlmCall
from mdcopilot_blog.domain.enums import CallKind, CallStatus
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.llm.gateway import CallContext
from mdcopilot_blog.llm.recorder import CallRecord, CallRecorder


async def make_run(sessionmaker: async_sessionmaker[AsyncSession]) -> BlogRun:
    async with sessionmaker() as session:
        run = BlogRun(
            kind="manual",
            run_date=date(2026, 9, 17),
            status="QUEUED",
            params={},
            trace_id=new_trace_id(),
        )
        session.add(run)
        await session.commit()
    return run


def make_record(ctx: CallContext, *, cost: str, status: CallStatus = CallStatus.OK, **kw: Any) -> CallRecord:
    return CallRecord(
        kind=CallKind.AGENT,
        ctx=ctx,
        provider_requested="openai",
        model_requested="gpt-test",
        attempt_index=0,
        status=status,
        latency_ms=12,
        cost_usd=Decimal(cost),
        **kw,
    )


async def test_record_commits_row_with_context(
    sessionmaker_committing: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    run = await make_run(sessionmaker_committing)
    recorder = CallRecorder(sessionmaker_committing)
    ctx = CallContext(
        trace_id=run.trace_id,
        run_id=run.id,
        attempt_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        dbos_workflow_id="manual-wf",
        dbos_step_id=2,
    )

    row_id = await recorder.record(
        make_record(
            ctx,
            cost="0.012345",
            agent_name="writer",
            prompt_name="writer/draft",
            prompt_version=1,
            prompt_sha="a" * 64,
            provider_served="openai",
            model_served="gpt-test-2026-09-01",
            fallback_from="google:gemini-test",
            params={"max_tokens": 300},
            input_tokens=100,
            output_tokens=40,
            cache_read_tokens=10,
            reasoning_tokens=5,
            usage_raw={"requests": [{"input_tokens": 100}]},
        )
    )

    async with sessionmaker_committing() as session:  # a fresh session proves the commit
        row = await session.scalar(select(LlmCall).where(LlmCall.id == row_id))
    assert row is not None
    assert row.run_id == run.id
    assert row.attempt_id == ctx.attempt_id
    assert row.agent_run_id == ctx.agent_run_id
    assert row.dbos_workflow_id == "manual-wf"
    assert row.dbos_step_id == 2
    assert row.kind == "agent"
    assert row.status == "ok"
    assert row.agent_name == "writer"
    assert row.prompt_version == 1
    assert row.model_served == "gpt-test-2026-09-01"
    assert row.fallback_from == "google:gemini-test"
    assert row.params == {"max_tokens": 300}
    assert (row.input_tokens, row.output_tokens, row.cache_read_tokens, row.reasoning_tokens) == (100, 40, 10, 5)
    assert row.cost_usd == Decimal("0.012345")
    assert row.price_version == "genai-prices==0.1.7"
    assert row.usage_raw == {"requests": [{"input_tokens": 100}]}
    assert row.trace_id == run.trace_id
    assert row.latency_ms == 12


async def test_error_message_is_truncated(
    sessionmaker_committing: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    recorder = CallRecorder(sessionmaker_committing)
    row_id = await recorder.record(
        make_record(
            CallContext(trace_id=new_trace_id()),
            cost="0",
            status=CallStatus.ERROR,
            error_class="ModelHTTPError",
            error_message="x" * 5000,
        )
    )
    async with sessionmaker_committing() as session:
        row = await session.scalar(select(LlmCall).where(LlmCall.id == row_id))
    assert row is not None
    assert row.run_id is None
    assert row.status == "error"
    assert row.error_class == "ModelHTTPError"
    assert row.error_message == "x" * 2000


async def test_run_cost_sums_only_that_run(
    sessionmaker_committing: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    run = await make_run(sessionmaker_committing)
    other = await make_run(sessionmaker_committing)
    recorder = CallRecorder(sessionmaker_committing)
    ctx = CallContext(trace_id=run.trace_id, run_id=run.id)

    assert await recorder.run_cost(run.id) == Decimal(0)
    await recorder.record(make_record(ctx, cost="0.100000"))
    await recorder.record(make_record(ctx, cost="0.250000", status=CallStatus.ERROR))
    await recorder.record(make_record(CallContext(trace_id=other.trace_id, run_id=other.id), cost="9"))
    await recorder.record(make_record(CallContext(trace_id=new_trace_id()), cost="7"))

    assert await recorder.run_cost(run.id) == Decimal("0.35")
    assert await recorder.run_cost(other.id) == Decimal(9)
    assert await recorder.run_cost(None) == Decimal(0)
    assert await recorder.run_cost(uuid.uuid4()) == Decimal(0)
```

- [ ] **Step 17: Write the failing gateway tests**

Create `backend/tests/unit/test_gateway.py`. It uses only `FunctionModel`s, plus one real `OpenAIChatModel` that is blocked by `ALLOW_MODEL_REQUESTS=False` before any HTTP request, so it makes no network calls.

```python
"""LLMGateway route walking, recording, budget, search and embeddings (FunctionModel only, no network)."""

import pickle
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import httpx2
import pytest
from pydantic import BaseModel, SecretStr
from pydantic_ai import ModelResponse, RequestUsage, ToolCallPart, models
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from mdcopilot_blog.domain.enums import AgentName, CallKind, CallStatus
from mdcopilot_blog.ids import new_trace_id, uuid7
from mdcopilot_blog.llm.gateway import (
    AgentResult,
    AgentSpec,
    BudgetExceeded,
    CallContext,
    LLMGateway,
    ModelFactory,
    ProviderNotAvailable,
    RouteExhausted,
    UnavailableModelFactory,
    UnavailableSearchProvider,
    build_model_factory,
)
from mdcopilot_blog.llm.mock import FixtureRegistry, MockModelFactory
from mdcopilot_blog.llm.recorder import CallRecord, CallRecorder
from mdcopilot_blog.llm.routes import ModelChoice
from mdcopilot_blog.llm.search.base import SearchQuery
from mdcopilot_blog.llm.search.fixture import FixtureSearchProvider
from mdcopilot_blog.prompts.registry import PromptRegistry, default_prompt_root
from mdcopilot_blog.settings import Settings

FunctionDef = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


class Draft(BaseModel):
    title: str
    words: int


class EchoOut(BaseModel):
    message: str
    word_count: int


WRITER_SPEC = AgentSpec(
    name=AgentName.WRITER,
    version="1",
    prompt_name="writer/draft",
    output_type=Draft,
    max_output_tokens=300,
    output_retries=1,
)


class FakeRecorder(CallRecorder):
    """In-memory recorder. ``cost_per_error`` simulates spend recorded by failed attempts."""

    def __init__(self, *, cost: Decimal = Decimal(0), cost_per_error: Decimal = Decimal(0)) -> None:
        self.records: list[CallRecord] = []
        self.cost = cost
        self.cost_per_error = cost_per_error
        self.cost_queries: list[Any] = []

    async def record(self, rec: CallRecord) -> Any:
        self.records.append(rec)
        if rec.status == CallStatus.ERROR:
            self.cost += self.cost_per_error
        return uuid7()

    async def run_cost(self, run_id: Any) -> Decimal:
        self.cost_queries.append(run_id)
        return self.cost if run_id is not None else Decimal(0)


@dataclass
class ScriptedFactory(ModelFactory):
    """Maps a route ref ("openai:model-a") to a model builder and remembers what was built."""

    scripts: dict[str, Callable[[], Model]]
    built: list[str] = field(default_factory=list)

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model:
        self.built.append(choice.ref())
        return self.scripts[choice.ref()]()


def ok(model_name: str, payload: dict[str, Any], seen: list[AgentInfo] | None = None) -> Callable[[], Model]:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if seen is not None:
            seen.append(info)
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, payload)],
            usage=RequestUsage(input_tokens=50, output_tokens=12),
        )

    return lambda: FunctionModel(respond, model_name=model_name)


def failing(model_name: str, exc: Exception) -> Callable[[], Model]:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise exc

    return lambda: FunctionModel(respond, model_name=model_name)


def invalid(model_name: str, calls: list[int]) -> Callable[[], Model]:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"title": "t", "words": "not-a-number"})],
            usage=RequestUsage(input_tokens=10, output_tokens=3),
        )

    return lambda: FunctionModel(respond, model_name=model_name)


@pytest.fixture
def prompts(tmp_path: Path) -> PromptRegistry:
    path = tmp_path / "writer" / "draft.v1.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nname: writer/draft\nversion: 1\nagent: writer\noutput: Draft\nvariables:\n  - topic\n---\n"
        "Write about {{ topic }}.\n",
        encoding="utf-8",
    )
    return PromptRegistry.from_directory(tmp_path)


@pytest.fixture
def gw_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "mock_mode": True,
            "writer_route": ["openai:model-a", "google:model-b"],
            "max_cost_per_run_usd": Decimal("1.00"),
            "embedding_model": "google:gemini-embedding-test",
            "embedding_dimensions": 8,
        }
    )


@pytest.fixture
def ctx() -> CallContext:
    return CallContext(trace_id=new_trace_id(), run_id=uuid7(), attempt_id=uuid7(), dbos_workflow_id="wf-1")


def make_gateway(
    settings: Settings,
    prompts: PromptRegistry,
    factory: ModelFactory,
    recorder: FakeRecorder,
    search_provider: Any | None = None,
) -> LLMGateway:
    return LLMGateway(
        settings=settings,
        prompts=prompts,
        recorder=recorder,
        model_factory=factory,
        search_provider=search_provider or FixtureSearchProvider(),
    )


async def test_success_records_one_ok_row(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    seen: list[AgentInfo] = []
    factory = ScriptedFactory({"openai:model-a": ok("fixture-a", {"title": "Hello", "words": 2}, seen)})
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, factory, recorder)

    result = await gateway.run(WRITER_SPEC, variables={"topic": "burnout"}, user_prompt="Go.", ctx=ctx)

    assert isinstance(result, AgentResult)
    assert result.output == Draft(title="Hello", words=2)
    assert (result.model, result.attempts) == ("fixture-a", 1)
    assert (result.input_tokens, result.output_tokens, result.cost_usd) == (50, 12, Decimal(0))
    assert factory.built == ["openai:model-a"]

    assert seen[0].instructions == "Write about burnout."  # pydantic-ai strips surrounding whitespace
    assert seen[0].model_settings is not None
    assert seen[0].model_settings.get("max_tokens") == 300
    assert seen[0].model_settings.get("timeout") == 120.0

    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec.kind == CallKind.AGENT
    assert rec.status == CallStatus.OK
    assert rec.ctx == ctx
    assert (rec.provider_requested, rec.model_requested) == ("openai", "model-a")
    assert (rec.provider_served, rec.model_served) == ("function", "fixture-a")
    assert rec.attempt_index == 0
    assert rec.fallback_from is None
    assert rec.agent_name == "writer"
    assert (rec.prompt_name, rec.prompt_version) == ("writer/draft", 1)
    assert rec.prompt_sha == prompts.get("writer/draft").sha256
    assert (rec.input_tokens, rec.output_tokens) == (50, 12)
    assert rec.params == {"max_tokens": 300, "timeout": 120.0, "output_retries": 1, "agent_version": "1"}
    assert rec.error_class is None
    assert rec.usage_raw["requests"] == [
        {
            "model_name": "fixture-a",
            "provider_name": None,
            "input_tokens": 50,
            "output_tokens": 12,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "details": {},
            "cost": None,
        }
    ]
    assert recorder.cost_queries == [ctx.run_id]


async def test_http_503_falls_back_to_next_model(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing(
                "fixture-a", ModelHTTPError(status_code=503, model_name="model-a", body={"error": "overloaded"})
            ),
            "google:model-b": ok("fixture-b", {"title": "Fallback", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, factory, recorder)

    result = await gateway.run(WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx)

    assert result.output.title == "Fallback"
    assert result.attempts == 2
    assert result.model == "fixture-b"
    assert factory.built == ["openai:model-a", "google:model-b"]

    first, second = recorder.records
    assert (first.status, first.error_class, first.attempt_index, first.fallback_from) == (
        CallStatus.ERROR,
        "ModelHTTPError",
        0,
        None,
    )
    assert first.error_message is not None
    assert "503" in first.error_message
    assert (first.provider_requested, first.model_requested) == ("openai", "model-a")
    assert (second.status, second.attempt_index, second.fallback_from) == (CallStatus.OK, 1, "openai:model-a")
    assert (second.provider_requested, second.model_requested) == ("google", "model-b")
    assert recorder.cost_queries == [ctx.run_id, ctx.run_id]  # budget checked before each model call


@pytest.mark.parametrize(
    "exc",
    [
        ModelAPIError(model_name="model-a", message="Connection error."),
        httpx2.ConnectError("connection refused"),
        httpx2.ReadTimeout("read timed out"),
        httpx.ConnectError("connection refused"),
    ],
    ids=["model-api-error", "httpx2-connect", "httpx2-timeout", "httpx-connect"],
)
async def test_transport_errors_advance_the_route(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext, exc: Exception
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", exc),
            "google:model-b": ok("fixture-b", {"title": "B", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    result = await make_gateway(gw_settings, prompts, factory, recorder).run(
        WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
    )
    assert result.attempts == 2
    assert [r.error_class for r in recorder.records] == [type(exc).__name__, None]


async def test_invalid_output_exhausts_retries_then_advances(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    calls: list[int] = []
    factory = ScriptedFactory(
        {
            "openai:model-a": invalid("fixture-a", calls),
            "google:model-b": ok("fixture-b", {"title": "Valid", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    result = await make_gateway(gw_settings, prompts, factory, recorder).run(
        WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
    )

    assert result.output.title == "Valid"
    assert len(calls) == WRITER_SPEC.output_retries + 1
    failed = recorder.records[0]
    assert failed.status == CallStatus.ERROR
    assert failed.error_class == "UnexpectedModelBehavior"
    assert failed.model_served == "fixture-a"
    assert (failed.input_tokens, failed.output_tokens) == (20, 6)  # both failed requests are accounted
    assert recorder.records[1].fallback_from == "openai:model-a"


async def test_all_models_fail_raises_route_exhausted(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", ModelHTTPError(status_code=503, model_name="model-a")),
            "google:model-b": failing("fixture-b", ModelAPIError(model_name="model-b", message="Request timed out.")),
        }
    )
    recorder = FakeRecorder()
    with pytest.raises(RouteExhausted) as caught:
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )

    assert caught.value.failures == [("openai:model-a", "ModelHTTPError"), ("google:model-b", "ModelAPIError")]
    assert "writer" in str(caught.value)
    assert [(r.status, r.attempt_index, r.fallback_from) for r in recorder.records] == [
        (CallStatus.ERROR, 0, None),
        (CallStatus.ERROR, 1, "openai:model-a"),
    ]


def test_route_exhausted_survives_pickle() -> None:
    original = RouteExhausted("writer", [("openai:model-a", "ModelHTTPError")])
    restored = pickle.loads(pickle.dumps(original))
    assert isinstance(restored, RouteExhausted)
    assert restored.failures == original.failures
    assert str(restored) == str(original)


async def test_budget_exceeded_blocks_before_any_call(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory({"openai:model-a": ok("fixture-a", {"title": "t", "words": 1})})
    recorder = FakeRecorder(cost=Decimal("1.00"))
    with pytest.raises(BudgetExceeded, match="cap is 1.00 USD"):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == []
    assert recorder.records == []


async def test_budget_is_rechecked_before_a_fallback(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", ModelHTTPError(status_code=500, model_name="model-a")),
            "google:model-b": ok("fixture-b", {"title": "t", "words": 1}),
        }
    )
    recorder = FakeRecorder(cost_per_error=Decimal("1.50"))
    with pytest.raises(BudgetExceeded):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == ["openai:model-a"]
    assert len(recorder.records) == 1


async def test_allow_model_requests_error_is_reraised_not_advanced(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    factory = ScriptedFactory(
        {
            # a real model class: with ALLOW_MODEL_REQUESTS False it raises before any HTTP request
            "openai:model-a": lambda: OpenAIChatModel("gpt-test", provider=OpenAIProvider(api_key="sk-test")),
            "google:model-b": ok("fixture-b", {"title": "never", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    with pytest.raises(RuntimeError, match="ALLOW_MODEL_REQUESTS"):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == ["openai:model-a"]
    assert len(recorder.records) == 1
    assert recorder.records[0].status == CallStatus.ERROR
    assert recorder.records[0].error_class == "RuntimeError"
    assert recorder.records[0].provider_served == "openai"


async def test_unexpected_exception_is_recorded_and_reraised(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", ValueError("bug in fixture")),
            "google:model-b": ok("fixture-b", {"title": "never", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    with pytest.raises(ValueError, match="bug in fixture"):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == ["openai:model-a"]
    assert [(r.status, r.error_class) for r in recorder.records] == [(CallStatus.ERROR, "ValueError")]


async def test_real_mode_factory_is_unavailable(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    real = gw_settings.model_copy(
        update={
            "mock_mode": False,
            "openai_api_key": SecretStr("sk-test"),
            "gemini_api_key": SecretStr("gm-test"),
        }
    )
    factory = build_model_factory(real)
    assert isinstance(factory, UnavailableModelFactory)
    recorder = FakeRecorder()
    with pytest.raises(ProviderNotAvailable, match="Phase 2"):
        await make_gateway(real, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert [(r.status, r.error_class) for r in recorder.records] == [(CallStatus.ERROR, "ProviderNotAvailable")]


def test_mock_mode_factory_disables_real_requests(gw_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)
    factory = build_model_factory(gw_settings)
    assert isinstance(factory, MockModelFactory)
    assert models.ALLOW_MODEL_REQUESTS is False


async def test_mock_gateway_runs_hello_fixture_end_to_end(
    gw_settings: Settings, ctx: CallContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)
    recorder = FakeRecorder()
    gateway = make_gateway(
        gw_settings,
        PromptRegistry.from_directory(default_prompt_root()),
        build_model_factory(gw_settings),
        recorder,
    )
    spec = AgentSpec(
        name=AgentName.HELLO, version="1", prompt_name="hello/echo", output_type=EchoOut, max_output_tokens=200
    )

    result = await gateway.run(
        spec, variables={"brand_name": "MDCopilot", "topic": "hello"}, user_prompt="Say hello.", ctx=ctx
    )

    assert result.output == EchoOut(message="Hello from the mock gateway", word_count=5)
    assert (result.model, result.attempts, result.input_tokens, result.output_tokens) == ("mock:hello", 1, 20, 8)
    rec = recorder.records[0]
    assert (rec.provider_requested, rec.model_requested, rec.model_served) == ("mock", "hello", "mock:hello")
    assert rec.prompt_name == "hello/echo"


def test_fixture_registry_reports_missing_and_malformed_files(tmp_path: Path) -> None:
    registry = FixtureRegistry(tmp_path)
    with pytest.raises(FileNotFoundError, match=r"no mock fixture for agent 'writer' prompt 'writer/draft'"):
        registry.load("writer", "writer/draft")

    bad = tmp_path / "writer" / "writer_draft.json"
    bad.parent.mkdir(parents=True)
    bad.write_text('{"output": {"title": "t"}, "usage": {"input_tokens": 1}}', encoding="utf-8")
    with pytest.raises(ValueError, match="'usage' must be"):
        registry.load("writer", "writer/draft")


def test_default_fixture_registry_has_hello_echo() -> None:
    fixture = FixtureRegistry.default().load("hello", "hello/echo")
    assert fixture == {
        "output": {"message": "Hello from the mock gateway", "word_count": 5},
        "usage": {"input_tokens": 20, "output_tokens": 8},
    }


async def test_search_records_a_search_row(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder, FixtureSearchProvider())

    result = await gateway.search(SearchQuery(text="specialist access"), ctx=ctx)

    assert result.answer_text.startswith("[fixture] specialist access: ")
    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec.kind == CallKind.SEARCH
    assert rec.status == CallStatus.OK
    assert (rec.provider_requested, rec.model_requested) == ("fixture", "fixture")
    assert (rec.provider_served, rec.model_served) == ("fixture", "fixture-search")
    assert rec.search_actions == result.search_actions == 1
    assert rec.agent_name == "search"
    assert rec.params["text"] == "specialist access"
    assert rec.ctx == ctx
    assert recorder.cost_queries == [ctx.run_id]


async def test_search_failure_is_recorded_and_reraised(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder, UnavailableSearchProvider())
    with pytest.raises(ProviderNotAvailable):
        await gateway.search(SearchQuery(text="q"), ctx=ctx)
    assert [(r.kind, r.status, r.error_class) for r in recorder.records] == [
        (CallKind.SEARCH, CallStatus.ERROR, "ProviderNotAvailable")
    ]


async def test_search_respects_budget(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    recorder = FakeRecorder(cost=Decimal(2))
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder)
    with pytest.raises(BudgetExceeded):
        await gateway.search(SearchQuery(text="q"), ctx=ctx)
    assert recorder.records == []


async def test_embed_is_deterministic_in_mock_mode(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder)

    first = await gateway.embed(["alpha topic", "beta topic"], ctx=ctx)
    second = await gateway.embed(["alpha topic"], ctx=ctx)

    assert len(first) == 2
    assert all(len(vector) == 8 for vector in first)
    assert all(-1.0 <= value <= 1.0 for vector in first for value in vector)
    assert first[0] == second[0]
    assert first[0] != first[1]

    assert len(recorder.records) == 2
    rec = recorder.records[0]
    assert rec.kind == CallKind.EMBEDDING
    assert rec.status == CallStatus.OK
    assert (rec.provider_requested, rec.model_requested) == ("google", "gemini-embedding-test")
    assert (rec.provider_served, rec.model_served) == ("mock", "mock:embedding")
    assert rec.params == {"dimensions": 8, "count": 2}
    assert rec.input_tokens == 4


async def test_embed_requires_mock_mode(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    recorder = FakeRecorder()
    real = gw_settings.model_copy(update={"mock_mode": False})
    gateway = make_gateway(real, prompts, ScriptedFactory({}), recorder)
    with pytest.raises(ProviderNotAvailable):
        await gateway.embed(["alpha"], ctx=ctx)
    assert recorder.records == []
```

- [ ] **Step 18: Run the recorder and gateway tests and watch them fail**

Run: `docker compose run --rm tools pytest tests/unit/test_gateway.py tests/db/test_recorder.py -q`

Expected: `Interrupted: 2 errors during collection`, and both errors are `E   ModuleNotFoundError: No module named 'mdcopilot_blog.llm.gateway'`.

- [ ] **Step 19: Implement the recorder**

Create `backend/src/mdcopilot_blog/llm/recorder.py`:

```python
"""Writes one ``blog_llm_calls`` row per model/search/embedding attempt, in its own transaction."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import LlmCall
from mdcopilot_blog.domain.enums import CallKind, CallStatus

if TYPE_CHECKING:
    from mdcopilot_blog.llm.gateway import CallContext

ERROR_MESSAGE_LIMIT = 2000
PRICE_VERSION = "genai-prices==0.1.7"


@dataclass(frozen=True)
class CallRecord:
    kind: CallKind
    ctx: CallContext
    provider_requested: str
    model_requested: str
    attempt_index: int
    status: CallStatus
    latency_ms: int
    agent_name: str | None = None
    prompt_name: str | None = None
    prompt_version: int | None = None
    prompt_sha: str | None = None
    provider_served: str | None = None
    model_served: str | None = None
    fallback_from: str | None = None
    params: Mapping[str, object] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    search_actions: int = 0
    cost_usd: Decimal = Decimal(0)
    price_version: str = PRICE_VERSION
    usage_raw: Mapping[str, object] = field(default_factory=dict)
    error_class: str | None = None
    error_message: str | None = None


class CallRecorder:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def record(self, rec: CallRecord) -> uuid.UUID:
        """Insert one row and commit immediately (own session), so failed runs keep their rows."""
        ctx = rec.ctx
        row = LlmCall(
            run_id=ctx.run_id,
            attempt_id=ctx.attempt_id,
            agent_run_id=ctx.agent_run_id,
            article_id=ctx.article_id,
            topic_candidate_id=ctx.topic_candidate_id,
            dbos_workflow_id=ctx.dbos_workflow_id,
            dbos_step_id=ctx.dbos_step_id,
            kind=rec.kind.value,
            agent_name=rec.agent_name,
            prompt_name=rec.prompt_name,
            prompt_version=rec.prompt_version,
            prompt_sha=rec.prompt_sha,
            provider_requested=rec.provider_requested,
            model_requested=rec.model_requested,
            provider_served=rec.provider_served,
            model_served=rec.model_served,
            fallback_from=rec.fallback_from,
            attempt_index=rec.attempt_index,
            params=dict(rec.params),
            input_tokens=rec.input_tokens,
            output_tokens=rec.output_tokens,
            cache_read_tokens=rec.cache_read_tokens,
            cache_write_tokens=rec.cache_write_tokens,
            reasoning_tokens=rec.reasoning_tokens,
            search_actions=rec.search_actions,
            latency_ms=rec.latency_ms,
            status=rec.status.value,
            error_class=rec.error_class,
            error_message=None if rec.error_message is None else rec.error_message[:ERROR_MESSAGE_LIMIT],
            usage_raw=dict(rec.usage_raw),
            cost_usd=rec.cost_usd,
            price_version=rec.price_version,
            trace_id=ctx.trace_id,
        )
        async with self._sessionmaker() as session:
            session.add(row)
            await session.commit()
        return row.id

    async def run_cost(self, run_id: uuid.UUID | None) -> Decimal:
        """Total recorded cost for a run; 0 when ``run_id`` is None."""
        if run_id is None:
            return Decimal(0)
        async with self._sessionmaker() as session:
            total = await session.scalar(
                select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(LlmCall.run_id == run_id)
            )
        return Decimal(str(total))
```

- [ ] **Step 20: Implement the gateway**

Create `backend/src/mdcopilot_blog/llm/gateway.py`:

```python
"""LLM gateway: every model, web-search and embedding call goes through here (ARCHITECTURE §7.1).

``run()`` walks the configured route itself (no FallbackModel). Each attempt writes exactly one
``blog_llm_calls`` row. Phase 1 builds mock models only; real providers arrive in Phase 2.
"""

import hashlib
import random
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx
import httpx2
from pydantic import BaseModel
from pydantic_ai import Agent, ModelResponse, capture_run_messages, models
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.domain.enums import AgentName, CallKind, CallStatus
from mdcopilot_blog.llm.recorder import CallRecord, CallRecorder
from mdcopilot_blog.llm.routes import ModelChoice, parse_choice, route_for
from mdcopilot_blog.llm.search.base import SearchQuery, SearchResult, WebSearchProvider
from mdcopilot_blog.llm.search.fixture import FixtureSearchProvider
from mdcopilot_blog.prompts.registry import PromptRegistry, RenderedPrompt
from mdcopilot_blog.settings import Settings

# Errors that move the route to its next model. Google leaks raw httpx2 transport errors;
# httpx.TransportError is caught for safety. Everything else is recorded and re-raised,
# including UsageLimitExceeded and the plain RuntimeError raised when ALLOW_MODEL_REQUESTS is False.
ADVANCE_ERRORS: tuple[type[Exception], ...] = (
    ModelAPIError,
    UnexpectedModelBehavior,
    httpx.TransportError,
    httpx2.TransportError,
)

MOCK_EMBEDDING_PROVIDER = "mock"
MOCK_EMBEDDING_MODEL = "mock:embedding"


@dataclass(frozen=True)
class AgentSpec[OutputT: BaseModel]:
    name: AgentName
    version: str
    prompt_name: str
    output_type: type[OutputT]
    max_output_tokens: int
    output_retries: int = 1
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class CallContext:
    trace_id: str
    run_id: uuid.UUID | None = None
    attempt_id: uuid.UUID | None = None
    agent_run_id: uuid.UUID | None = None
    dbos_workflow_id: str | None = None
    dbos_step_id: int | None = None
    article_id: uuid.UUID | None = None
    topic_candidate_id: uuid.UUID | None = None


@dataclass(frozen=True)
class AgentResult[OutputT: BaseModel]:
    output: OutputT
    provider: str
    model: str
    attempts: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class GatewayError(RuntimeError):
    """Base class for gateway failures."""


class BudgetExceeded(GatewayError):
    """The run already spent its per-run cost cap."""


class RouteExhausted(GatewayError):
    """Every model in the route failed with a route-advancing error."""

    def __init__(self, agent: str, failures: Sequence[tuple[str, str]]) -> None:
        self.agent = agent
        self.failures: list[tuple[str, str]] = list(failures)
        summary = ", ".join(f"{ref} ({error_class})" for ref, error_class in self.failures)
        super().__init__(f"all models failed for agent {agent!r}: {summary}")

    def __reduce__(self) -> tuple[Any, ...]:
        # keeps the exception picklable (DBOS serialises step errors)
        return (self.__class__, (self.agent, self.failures))


class ProviderNotAvailable(GatewayError):
    """A real provider was requested but is not built or not allowed."""


class ModelFactory(Protocol):
    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model: ...


class UnavailableModelFactory(ModelFactory):
    """Used when mock mode is off. Real model construction lands in Phase 2."""

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model:
        raise ProviderNotAvailable("real providers are enabled in Phase 2")


class UnavailableSearchProvider:
    """Used when mock mode is off. Real search providers land in Phase 2."""

    name = "unavailable"

    async def search(self, query: SearchQuery) -> SearchResult:
        raise ProviderNotAvailable("real search providers are enabled in Phase 2")


@dataclass(frozen=True)
class _Usage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    cost_usd: Decimal
    model_served: str | None
    provider_served: str | None
    raw: dict[str, object]


def _sum_usage(messages: Sequence[ModelMessage]) -> _Usage:
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    requests: list[dict[str, object]] = []
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "reasoning": 0}
    cost = Decimal(0)
    for response in responses:
        usage = response.usage
        reasoning = int(getattr(usage, "output_reasoning_tokens", 0) or 0)
        totals["input"] += usage.input_tokens
        totals["output"] += usage.output_tokens
        totals["cache_read"] += usage.cache_read_tokens
        totals["cache_write"] += usage.cache_write_tokens
        totals["reasoning"] += reasoning
        cost += usage.cost or Decimal(0)
        requests.append(
            {
                "model_name": response.model_name,
                "provider_name": response.provider_name,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_tokens": usage.cache_read_tokens,
                "cache_write_tokens": usage.cache_write_tokens,
                "reasoning_tokens": reasoning,
                "details": dict(usage.details),
                "cost": None if usage.cost is None else str(usage.cost),
            }
        )
    last = responses[-1] if responses else None
    return _Usage(
        input_tokens=totals["input"],
        output_tokens=totals["output"],
        cache_read_tokens=totals["cache_read"],
        cache_write_tokens=totals["cache_write"],
        reasoning_tokens=totals["reasoning"],
        cost_usd=cost,
        model_served=last.model_name if last is not None else None,
        provider_served=last.provider_name if last is not None else None,
        raw={"requests": requests},
    )


def mock_embedding(text: str, dimensions: int) -> list[float]:
    """Deterministic vector in [-1, 1]^dimensions, seeded by sha256(text)."""
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


class LLMGateway:
    def __init__(
        self,
        *,
        settings: Settings,
        prompts: PromptRegistry,
        recorder: CallRecorder,
        model_factory: ModelFactory,
        search_provider: WebSearchProvider,
    ) -> None:
        self._settings = settings
        self._prompts = prompts
        self._recorder = recorder
        self._model_factory = model_factory
        self._search_provider = search_provider

    async def _check_budget(self, ctx: CallContext) -> None:
        spent = await self._recorder.run_cost(ctx.run_id)
        cap = self._settings.max_cost_per_run_usd
        if spent >= cap:
            raise BudgetExceeded(f"run {ctx.run_id} has spent {spent} USD; the cap is {cap} USD")

    async def _record_agent_attempt(
        self,
        *,
        spec: AgentSpec[Any],
        rendered: RenderedPrompt,
        choice: ModelChoice,
        index: int,
        fallback_from: str | None,
        ctx: CallContext,
        params: Mapping[str, object],
        started: float,
        usage: _Usage,
        provider_fallback: str | None,
        error: Exception | None,
    ) -> None:
        await self._recorder.record(
            CallRecord(
                kind=CallKind.AGENT,
                ctx=ctx,
                provider_requested=choice.provider,
                model_requested=choice.model,
                attempt_index=index,
                status=CallStatus.OK if error is None else CallStatus.ERROR,
                latency_ms=_elapsed_ms(started),
                agent_name=spec.name.value,
                prompt_name=rendered.name,
                prompt_version=rendered.version,
                prompt_sha=rendered.sha256,
                provider_served=usage.provider_served or provider_fallback,
                model_served=usage.model_served,
                fallback_from=fallback_from,
                params=params,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                cost_usd=usage.cost_usd,
                usage_raw=usage.raw,
                error_class=None if error is None else type(error).__name__,
                error_message=None if error is None else str(error),
            )
        )

    async def run[OutputT: BaseModel](
        self,
        spec: AgentSpec[OutputT],
        *,
        variables: Mapping[str, object],
        user_prompt: str,
        ctx: CallContext,
    ) -> AgentResult[OutputT]:
        await self._check_budget(ctx)
        rendered = self._prompts.render(spec.prompt_name, variables)
        route = route_for(self._settings, spec.name)
        model_settings: ModelSettings = {"max_tokens": spec.max_output_tokens, "timeout": spec.timeout_seconds}
        params: dict[str, object] = {
            "max_tokens": spec.max_output_tokens,
            "timeout": spec.timeout_seconds,
            "output_retries": spec.output_retries,
            "agent_version": spec.version,
        }
        failures: list[tuple[str, str]] = []
        previous_ref: str | None = None

        for index, choice in enumerate(route):
            if index > 0:
                await self._check_budget(ctx)  # the cap is checked before every model call
            started = time.perf_counter()
            messages: list[ModelMessage] = []
            system: str | None = None
            try:
                with capture_run_messages() as messages:
                    model = self._model_factory.build(choice, spec)
                    system = model.system
                    agent = Agent(
                        model,
                        output_type=spec.output_type,
                        instructions=rendered.text,
                        retries={"output": spec.output_retries},
                    )
                    result = await agent.run(user_prompt, model_settings=model_settings)
            except ADVANCE_ERRORS as exc:
                await self._record_agent_attempt(
                    spec=spec,
                    rendered=rendered,
                    choice=choice,
                    index=index,
                    fallback_from=previous_ref,
                    ctx=ctx,
                    params=params,
                    started=started,
                    usage=_sum_usage(messages),
                    provider_fallback=system,
                    error=exc,
                )
                failures.append((choice.ref(), type(exc).__name__))
                previous_ref = choice.ref()
                continue
            except Exception as exc:
                await self._record_agent_attempt(
                    spec=spec,
                    rendered=rendered,
                    choice=choice,
                    index=index,
                    fallback_from=previous_ref,
                    ctx=ctx,
                    params=params,
                    started=started,
                    usage=_sum_usage(messages),
                    provider_fallback=system,
                    error=exc,
                )
                raise

            usage = _sum_usage(result.all_messages())
            await self._record_agent_attempt(
                spec=spec,
                rendered=rendered,
                choice=choice,
                index=index,
                fallback_from=previous_ref,
                ctx=ctx,
                params=params,
                started=started,
                usage=usage,
                provider_fallback=system,
                error=None,
            )
            return AgentResult(
                output=result.output,
                provider=usage.provider_served or system or choice.provider,
                model=usage.model_served or choice.model,
                attempts=index + 1,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
            )

        raise RouteExhausted(spec.name.value, failures)

    async def search(self, query: SearchQuery, *, ctx: CallContext) -> SearchResult:
        await self._check_budget(ctx)
        provider = self._search_provider
        params = query.model_dump(mode="json")
        started = time.perf_counter()
        try:
            result = await provider.search(query)
        except Exception as exc:
            await self._recorder.record(
                CallRecord(
                    kind=CallKind.SEARCH,
                    ctx=ctx,
                    provider_requested=provider.name,
                    model_requested=provider.name,
                    attempt_index=0,
                    status=CallStatus.ERROR,
                    latency_ms=_elapsed_ms(started),
                    agent_name=AgentName.SEARCH.value,
                    params=params,
                    error_class=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            raise
        await self._recorder.record(
            CallRecord(
                kind=CallKind.SEARCH,
                ctx=ctx,
                provider_requested=provider.name,
                model_requested=provider.name,
                attempt_index=0,
                status=CallStatus.OK,
                latency_ms=result.latency_ms or _elapsed_ms(started),
                agent_name=AgentName.SEARCH.value,
                provider_served=result.provider,
                model_served=result.model,
                params=params,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                search_actions=result.search_actions,
                cost_usd=result.cost_usd,
                usage_raw={
                    "search_actions": result.search_actions,
                    "sources": len(result.sources),
                    "citations": len(result.citations),
                },
            )
        )
        return result

    async def embed(self, texts: Sequence[str], *, ctx: CallContext) -> list[list[float]]:
        if not self._settings.mock_mode:
            raise ProviderNotAvailable("real embeddings are enabled in Phase 2")
        started = time.perf_counter()
        choice = parse_choice(self._settings.embedding_model)
        dimensions = self._settings.embedding_dimensions
        vectors = [mock_embedding(text, dimensions) for text in texts]
        await self._recorder.record(
            CallRecord(
                kind=CallKind.EMBEDDING,
                ctx=ctx,
                provider_requested=choice.provider,
                model_requested=choice.model,
                attempt_index=0,
                status=CallStatus.OK,
                latency_ms=_elapsed_ms(started),
                provider_served=MOCK_EMBEDDING_PROVIDER,
                model_served=MOCK_EMBEDDING_MODEL,
                params={"dimensions": dimensions, "count": len(texts)},
                input_tokens=sum(len(text.split()) for text in texts),
            )
        )
        return vectors


def build_model_factory(settings: Settings) -> ModelFactory:
    if settings.mock_mode:
        # imported here because llm.mock imports AgentSpec/ModelFactory from this module
        from mdcopilot_blog.llm.mock import FixtureRegistry, MockModelFactory

        models.ALLOW_MODEL_REQUESTS = False
        return MockModelFactory(FixtureRegistry.default())
    return UnavailableModelFactory()


def build_gateway(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    prompts: PromptRegistry,
) -> LLMGateway:
    search_provider: WebSearchProvider = FixtureSearchProvider() if settings.mock_mode else UnavailableSearchProvider()
    return LLMGateway(
        settings=settings,
        prompts=prompts,
        recorder=CallRecorder(sessionmaker),
        model_factory=build_model_factory(settings),
        search_provider=search_provider,
    )
```

- [ ] **Step 21: Implement the mock model factory**

Create `backend/src/mdcopilot_blog/llm/mock.py`:

```python
"""Mock-mode models: Pydantic AI ``FunctionModel`` replaying JSON fixtures.

Importing this module changes no global state; ``build_model_factory`` sets
``models.ALLOW_MODEL_REQUESTS = False`` when mock mode is on.
"""

import copy
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelResponse, RequestUsage, ToolCallPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from mdcopilot_blog.llm.gateway import AgentSpec, ModelFactory
from mdcopilot_blog.llm.routes import ModelChoice

USAGE_KEYS = frozenset({"input_tokens", "output_tokens"})


def default_llm_fixture_root() -> Path:
    """``backend/fixtures/mock/llm`` (editable install), else ``<cwd>/fixtures/mock/llm``."""
    candidate = Path(__file__).resolve().parents[3] / "fixtures" / "mock" / "llm"
    if candidate.is_dir():
        return candidate
    return Path.cwd() / "fixtures" / "mock" / "llm"


class FixtureRegistry:
    """Fixtures keyed by (agent, prompt name): ``<root>/<agent>/<prompt_name with '/' -> '_'>.json``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    @classmethod
    def default(cls) -> "FixtureRegistry":
        return cls(default_llm_fixture_root())

    def path_for(self, agent: str, prompt_name: str) -> Path:
        return self.root / agent / f"{prompt_name.replace('/', '_')}.json"

    def load(self, agent: str, prompt_name: str) -> dict[str, Any]:
        key = (agent, prompt_name)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        path = self.path_for(agent, prompt_name)
        if not path.is_file():
            raise FileNotFoundError(f"no mock fixture for agent {agent!r} prompt {prompt_name!r}: expected {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("output"), dict):
            raise TypeError(f"{path}: fixture must be an object with an 'output' object")
        usage = data.get("usage")
        if (
            not isinstance(usage, dict)
            or set(usage) != USAGE_KEYS
            or not all(isinstance(v, int) for v in usage.values())
        ):
            raise ValueError(f"{path}: 'usage' must be {{'input_tokens': int, 'output_tokens': int}}")
        self._cache[key] = data
        return data


class MockModelFactory(ModelFactory):
    """Ignores the provider in ``choice``; every agent replays its fixture."""

    def __init__(self, fixtures: FixtureRegistry) -> None:
        self.fixtures = fixtures

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model:
        fixture = self.fixtures.load(spec.name.value, spec.prompt_name)
        output: dict[str, Any] = fixture["output"]
        input_tokens: int = fixture["usage"]["input_tokens"]
        output_tokens: int = fixture["usage"]["output_tokens"]

        async def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            return ModelResponse(
                parts=[ToolCallPart(info.output_tools[0].name, copy.deepcopy(output))],
                usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            )

        return FunctionModel(respond, model_name=f"mock:{spec.name.value}")
```

- [ ] **Step 22: Run the tests: only the hello-fixture tests should still fail**

Run: `docker compose run --rm tools pytest tests/unit/test_gateway.py tests/db/test_recorder.py -q`

Expected: `2 failed, 24 passed`. The failures are `test_mock_gateway_runs_hello_fixture_end_to_end` and `test_default_fixture_registry_has_hello_echo`, both raising `FileNotFoundError: no mock fixture for agent 'hello' prompt 'hello/echo': expected /app/fixtures/mock/llm/hello/hello_echo.json`.

- [ ] **Step 23: Add the hello fixture**

Create `backend/fixtures/mock/llm/hello/hello_echo.json`:

```json
{
  "output": {
    "message": "Hello from the mock gateway",
    "word_count": 5
  },
  "usage": {
    "input_tokens": 20,
    "output_tokens": 8
  }
}
```

- [ ] **Step 24: Run the recorder and gateway tests and watch them pass**

Run: `docker compose run --rm tools pytest tests/unit/test_gateway.py tests/db/test_recorder.py -q`

Expected: `26 passed` (23 gateway, 3 recorder).

**Part E: whole-task checks**

- [ ] **Step 25: Run every test from this task**

Run: `docker compose run --rm tools pytest tests/unit/test_routes.py tests/unit/test_search_fixture.py tests/unit/test_null_publisher.py tests/unit/test_gateway.py tests/db/test_recorder.py -q`

Expected: `58 passed`.

Then run Task 6's tests with this task's: `docker compose run --rm tools pytest tests/unit/test_prompt_registry.py tests/db/test_prompt_sync.py tests/unit/test_routes.py tests/unit/test_search_fixture.py tests/unit/test_null_publisher.py tests/unit/test_gateway.py tests/db/test_recorder.py -q`

Expected: `73 passed`.

- [ ] **Step 26: Check the import order and the no-global-side-effect rule**

Run: `docker compose run --rm tools python -c "import mdcopilot_blog.llm.mock; from pydantic_ai import models; print('ALLOW_MODEL_REQUESTS', models.ALLOW_MODEL_REQUESTS)"`

Expected: `ALLOW_MODEL_REQUESTS True`. Importing the mock module changes nothing global.

Run: `docker compose run --rm tools python -c "import mdcopilot_blog.llm.recorder, mdcopilot_blog.llm.gateway, mdcopilot_blog.publishing.null; print('imports ok')"`

Expected: `imports ok`, with no circular-import error.

- [ ] **Step 27: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, when Tasks 1–10 are done in plan order and nothing else has been added:
```text
All checks passed!
94 files already formatted
Success: no issues found in 54 source files
```

Where the numbers come from (checked on 2026-09-17 with ruff 0.16.8 and mypy 2.3.1, on this plan's files for Tasks 1–10, using the Task 9 versions of `tests/conftest.py` and `api/app.py`; that check gave 93 because its tree did not yet have Task 5's `tests/db/__init__.py`, which this plan creates):
- **94 formatted files.** This is every `.py` file under `backend/` (93) plus the Markdown prompt `backend/prompts/hello/echo.v1.md`, which ruff 0.16.8's `format` includes by default.
  - Dot-directories and the JSON fixtures are not counted.
  - Task 9 ended at 78. This task adds 16 `.py` files: 11 under `src/` and 5 tests.
- **54 source files.** This is every `.py` file under `backend/src/`: 43 after Task 9, plus this task's 11.
- **If you did this task early.** The totals assume Tasks 7, 8 and 9 ran before this task, as the plan orders them. This task needs only Tasks 5 and 6. For each of Tasks 7–9 that is not done yet, subtract its files:

  | Task | `.py` files (formatted count) | of which under `src/` (source-file count) |
  |---|---|---|
  | 7 | 14 | 8 |
  | 8 | 4 | 2 |
  | 9 | 21 | 12 |

If a number is still different, list the files and compare them with the **Files** lists of the tasks you have done:
```bash
find backend -name '.*' -prune -o -type f \( -name '*.py' -o -name '*.md' \) -print | sort
find backend/src -type f -name '*.py' | sort
```
After Tasks 1–10, the first list has 94 entries and the second has 54. A missing entry means an earlier step was skipped. An extra entry is a file that is not part of this plan.

Notes on ruff 0.16.8's defaults:
- They flag `Generic[...]` (UP046), `Decimal("0")` (FURB157) and unused `noqa` comments (RUF100). The code above already satisfies all three.
- If `ruff format --check` lists a file from this task, run `docker compose run --rm tools ruff format src tests` and re-run Step 25.

- [ ] **Step 28: Checkpoint: list the files changed in this task (no git)**

Files created:
- `backend/src/mdcopilot_blog/llm/__init__.py`
- `backend/src/mdcopilot_blog/llm/routes.py`
- `backend/src/mdcopilot_blog/llm/recorder.py`
- `backend/src/mdcopilot_blog/llm/gateway.py`
- `backend/src/mdcopilot_blog/llm/mock.py`
- `backend/src/mdcopilot_blog/llm/search/__init__.py`
- `backend/src/mdcopilot_blog/llm/search/base.py`
- `backend/src/mdcopilot_blog/llm/search/fixture.py`
- `backend/src/mdcopilot_blog/publishing/__init__.py`
- `backend/src/mdcopilot_blog/publishing/base.py`
- `backend/src/mdcopilot_blog/publishing/null.py`
- `backend/fixtures/mock/llm/hello/hello_echo.json`
- `backend/fixtures/mock/search/default.json`
- `backend/tests/unit/test_routes.py`
- `backend/tests/unit/test_search_fixture.py`
- `backend/tests/unit/test_null_publisher.py`
- `backend/tests/unit/test_gateway.py`
- `backend/tests/db/test_recorder.py`

No other file is modified.

---

### Task 11: Workflows and worker (DBOS)

Builds the durable side of Phase 1:
- the DBOS config and the process-wide `WorkerRuntime`;
- run, attempt and step bookkeeping (`tracking.py`);
- the three-step mock `hello_pipeline`;
- the paused daily schedule with its `daily_trigger` wrapper and same-day catch-up;
- `worker.py`, the only process that calls `DBOS.launch()`.

The tests run DBOS in-process under pytest against `mdcopilot_blog_test`.

**Verified while writing this plan (2026-09-17).** Every code block below ran in throwaway containers (`p1p-t11-*`) with dbos 3.0.0 and pgvector pg16. The first round used a contract-faithful stand-in for Tasks 2–10. After review, the blocks ran again on the tree assembled from every task of this plan:
- **Tests:** `35 passed`, three times in a row, and the whole backend suite passed (Tasks 1–12: `1129 passed`; the plan as written gives `1130`, because Task 3 has since gained a 13th logging test). The red step for each test file was also checked. The new cancellation, timeout, logging and schedule tests fail against the pre-review code, as intended.
- **Lint and types:** ruff and mypy strict are clean. At the end of this task the output is exactly the text in Step 24.
- **Worker startup and shutdown:** the real worker started and logged "DBOS launched". It stopped gracefully on SIGINT and on `docker stop` while a workflow was running; the workflow finished before `DBOS destroyed`.
- **Crash recovery:** the worker was killed in two separate runs, and each time a restart recovered the workflow with exactly one `blog_agent_runs` row per step.
  - **Killed inside `hello.finish` (Step 26):** as Step 26 describes.
  - **Killed inside `hello.echo`'s mock delay:** the run was RESEARCHING with 0 `blog_llm_calls` rows. After the restart, `hello.echo` had `tries=2` and the run had exactly **1** call.
- **Test-fixture fallback:** the executor-thread launch (Step 7) also passed all 35 tests.

**DBOS 3.0.0 facts this task depends on** (`p1facts/dbos.md`, plus Step 1):

*Queues and async APIs*
- **Queues** are registered with `await DBOS.register_queue_async(...)` **after** `DBOS.launch()`. `Queue(...)` raises.
- **Async variants.** Inside a running loop, use the `*_async` APIs, because sync `DBOS.*` calls raise there.
- **Pause and resume.** dbos 3.0.0 has **no** `pause_schedule_async` or `resume_schedule_async`. Call `DBOS.pause_schedule` and `DBOS.resume_schedule` through `asyncio.to_thread`.
- **Shutdown.** `DBOS.destroy` is synchronous and sleeps while it waits, so it runs via `asyncio.to_thread`; otherwise it freezes the workflows it is waiting for.
- **Listing inside a step.** `DBOS.list_workflows_async` called inside a step does not use up a step id: the hello steps stay 1, 2, 3.

*Workflow identity and schedules*
- **Ids inside steps.** `DBOS.workflow_id` and `DBOS.step_id` are set inside steps, and `DBOS.step_id` is `None` in the workflow body. `SetWorkflowID(...)` fixes a child workflow's id.
- **Enqueueing a child.** `SetWorkflowID(...)` also applies to `DBOS.enqueue_workflow_async(queue_name, func, *args)` inside a workflow.
  - Enqueueing again under an id that already exists returns that workflow and runs nothing. This held both while the workflow was ENQUEUED and after it succeeded.
  - `WorkflowStatus.queue_name` stays set after the workflow completes.
- **Schedules.** `DBOS.apply_schedules_async` upserts a schedule and **keeps its current status**, so `apply_daily_schedule` always pauses or resumes explicitly. The queue named in a schedule must already be registered.

*Forks*
- **Fork copies.** `fork_workflow` copies earlier step outputs and the workflow's inputs, and the fork gets a new random workflow id. Steps therefore resolve their attempt from `DBOS.workflow_id` (ARCHITECTURE §5), never from the attempt id a copied step returned.
- **Fork metadata.** `WorkflowStatus.forked_from` holds the original workflow id.

*Exceptions*
- **Cancellation.** `dbos._error.DBOSWorkflowCancelledError` subclasses `BaseException`, not `Exception`, so `except Exception` does not catch it. `hello_pipeline` therefore catches it separately.
- **Timeouts are cancellations.** When a workflow's timeout passes, DBOS marks it CANCELLED; `_schedule_workflow_timeout` in `dbos/_core.py` calls `cancel_workflows`. An API cancel works the same way.
  - Neither interrupts the running step, which is not preemptible. The step finishes, and the workflow body receives `DBOSWorkflowCancelledError` when the **next** step starts.
  - After that the body can still await plain coroutines, but any further DBOS step raises again.
- **Awaiting a cancelled workflow.** `DBOSAwaitedWorkflowCancelledError`, raised by `get_result()` on a cancelled workflow, is an `Exception` whose message contains "cancelled".
- **Retries exhausted.** A step that runs out of retries raises `DBOSMaxStepRetriesExceeded` (an `Exception`) with the message "Step <name> has exceeded its maximum of N retries".

**Choices beyond the contract.** Listed here so reviewers can check them. Items marked **(contract deviation)** change behaviour the contract states; the contract lines to update are listed after this section.

*`tracking.py`*
1. **Extra helpers:** `get_run_status`, `get_run_trace_id`, `get_attempt_status`, `error_payload` and `TERMINAL_RUN_STATUSES`. Unknown runs raise `LookupError`.
2. **`ensure_attempt`:**
   - It stores `start_step = DBOS.step_id`, which is `None` outside a step.
   - When it creates the attempt of a **forked** workflow (`forked_from` set) and the run is SUCCEEDED, FAILED or CANCELLED, it re-opens the run to QUEUED in the same transaction.
   - An original attempt never re-opens a run. If the run is already CANCELLED (the API cancelled it while its workflow was queued), the attempt is inserted as CANCELLED with `finished_at` set, because nothing would ever close it later.
3. **`set_run_status`:** moving to QUEUED clears `finished_at`, and also clears `error` unless one is passed.
4. **`finish_attempt`:** it only closes ENQUEUED or RUNNING attempts. An attempt the API already cancelled stays CANCELLED.
5. **`track_step`:**
   - On exit it also copies `model`, `prompt_name` and `prompt_version` from the step's last `ok` LLM call.
   - It refreshes `blog_runs.cost_usd` as the sum of the run's `blog_llm_calls.cost_usd`.
   - It treats `asyncio.CancelledError` as a failure, like `Exception`.
   - Every execution ends with one JSON log line whose message is `"step finished"`.
     - Extra keys: `step`, `status`, `duration_ms` and `tries`, plus `error_class` on failure. Level: INFO on success, WARNING on failure.
     - The line also carries the `run_id`/`trace_id` that the hello steps bind with `bind_log_context`, which covers the Phase 1 "structured JSON logs carrying run_id and trace_id" bullet end to end.

*`hello.py`*

6. **Safe re-execution.** DBOS runs a step again when the worker dies after the step's commits but before its output is recorded. So:
   - **(contract deviation)** `echo_step` runs its mock delay **before** `gateway.run`, not after it. A worker killed during the delay has recorded no call, so the resumed execution makes the run's only call. Phase 2 must not pay twice for one step.
   - `echo_step` moves a QUEUED run (a fork starting at echo) to RESEARCHING first;
   - `finish_step` skips its status changes when its own attempt is already SUCCEEDED. Its mock delay stays after them; Step 26 relies on that.
7. **Cancellation while a step runs** (Task 12 cancels by committing the run as CANCELLED):
   - `_advance(...)` wraps every `set_run_status` in `open_attempt_step`, `echo_step` and `finish_step`. `mark_failed_step` keeps its own `InvalidTransition` handling. If the move raises `InvalidTransition` and the run is CANCELLED, `_stop_if_cancelled` closes this workflow's attempt as CANCELLED, and the step returns early without further status writes.
     - The step row is then SUCCEEDED, not FAILED with "illegal run transition: CANCELLED -> …".
     - `set_run_status` locks the run row, so a cancel cannot slip between that check and the write.
   - `echo_step` also calls `_stop_if_cancelled` right before `gateway.run`, so a cancelled run makes no LLM call. A cancelled step returns `{}`.
   - When the API also cancelled the DBOS workflow (Task 12 does both), DBOS stops it when the next step starts.
8. **Cancellation or timeout by DBOS.** `hello_pipeline` wraps its body in an outer `except DBOSWorkflowCancelledError`, which calls the plain coroutine `_close_cancelled_workflow` (not a step) and re-raises. That coroutine:
   - sets the run FAILED with `error=WORKFLOW_CANCELLED_ERROR`. A run the API already cancelled stays CANCELLED: `InvalidTransition` is suppressed.
   - closes the attempt as CANCELLED.

   Without this, a run that hit the 30-minute timeout stayed RESEARCHING forever with a RUNNING attempt. The Dashboard would then poll it forever, and `create_daily_run_step` would treat it as an active manual run.

*`schedules.py`*

9. **Target lookup and ids:**
   - `DAILY_TARGETS` maps `DAILY_TARGET_WORKFLOW` to the function to start.
   - `daily_child_workflow_id(date)` gives the child workflow id.
   - `catch_up_today` starts the trigger under `SetWorkflowID(f"catchup-{date}")`, so two quick restarts cannot start it twice.
10. **(contract deviation)** `daily_trigger` **enqueues** the child on `QUEUE_PIPELINE` with `DBOS.enqueue_workflow_async` instead of starting it with `DBOS.start_workflow_async`.
    - The id is still set with `SetWorkflowID(daily-<date>)`.
    - The pipeline queue runs one workflow at a time, so a daily run waits for an in-flight manual run instead of overlapping it.
    - The trigger does not wait for its child, so it cannot block the queue it runs on.
11. **(contract deviation)** When the date already has a daily run, `create_daily_run_step` returns that run's id if the run is still **QUEUED**, and None otherwise. It also checks for an existing daily run before the active-manual-run check.
    - The case this covers: the worker dies after the insert committed but before DBOS recorded the step's output.
    - Recovery re-executes the step. Returning None would then leave a QUEUED run with no workflow forever, and `catch_up_today` could not repair it.
    - Enqueueing `daily-<date>` a second time is harmless.

*Other modules and tests*

12. **`dbos_config.py`** exports `DBOS_APP_NAME = "mdcopilot-blog"` and `DBOS_SYSTEM_SCHEMA = "dbos"`, which the tests use to build the API-side `DBOSClient`.
13. **`worker.py`** exposes `heartbeat_loop(stop, path, interval)` and `install_signal_handlers(stop)`. It destroys DBOS in `finally`, and only if launch succeeded.
14. **`tests/conftest.py`:**
    - The T11 block adds `make_run` and the constants `DBOS_TEST_EXECUTOR_ID` and `DBOS_TEST_APP_VERSION`.
    - `dbos_runtime` pins `timezone="Asia/Kolkata"` and `max_cost_per_run_usd=5.00`, so a different `.env` cannot break the tests.
    - It does **not** import the workflow modules. The test modules import them during collection, which happens before any fixture runs, so everything is registered before launch.
15. **Extra test files:** `tests/workflows/test_dbos_runtime.py` (the DBOS-under-pytest probe, plus the config test) and `tests/workflows/test_worker.py` (heartbeat).
16. **Extra tests:**
    - **Cancel and timeout** (Task 12's cancel flow):
      - `test_cancelled_run_stays_cancelled`: an API cancel during `hello.open_attempt`.
      - `test_workflow_timeout_fails_the_run_and_cancels_the_attempt`: a DBOS timeout.
      - `test_workflow_of_a_run_cancelled_while_queued_changes_nothing`: the run is cancelled before its workflow starts.
      - `test_cancel_during_the_echo_call_is_not_a_step_failure`: the run is cancelled between the gateway call and TOPICS_READY.
    - **Logging:** `test_step_logs_carry_run_and_trace_ids`.
      - It attaches a `JsonFormatter` handler to the `mdcopilot_blog.workflows.tracking` logger for the test.
      - It does not use `capsys` plus `configure_logging`, because that would replace the root handler and level for the rest of the session.
    - **Spike S1, "step name → function_id in a loop":** `test_fork_from_a_repeated_step_restarts_at_its_last_execution` re-verifies it on a real DBOS workflow. It forks from a step that ran three times and checks that only the last execution and later steps run again.
    - **Tracking and schedules:** `test_ensure_attempt_for_a_cancelled_run_is_closed_at_once` and `test_daily_trigger_starts_the_workflow_of_a_still_queued_daily_run`.

**Contract lines this task changes** (for the CONTRACT.md owner):
- `workflows/hello.py`:
  - `echo_step` is "track_step, then (QUEUED→RESEARCHING), mock delay, `gateway.run(...)`, then set_run_status TOPICS_READY".
  - `hello_pipeline` also catches `DBOSWorkflowCancelledError`, closes the run (FAILED unless already CANCELLED) and the attempt (CANCELLED), and re-raises.
- `workflows/schedules.py`:
  - `create_daily_run_step` returns the existing daily run's id when that run is QUEUED, and None when it has left QUEUED.
  - `daily_trigger` enqueues the target with `DBOS.enqueue_workflow_async(QUEUE_PIPELINE, target, run_id)` under `SetWorkflowID(f"daily-{local_date.isoformat()}")`.
- `workflows/tracking.py`:
  - `ensure_attempt` inserts a non-fork attempt for a CANCELLED run as CANCELLED with `finished_at` set.
  - `track_step` logs `"step finished"`.

**Files:**
- Create: `backend/src/mdcopilot_blog/workflows/dbos_config.py`
- Create: `backend/src/mdcopilot_blog/workflows/runtime.py`
- Create: `backend/src/mdcopilot_blog/workflows/tracking.py`
- Create: `backend/src/mdcopilot_blog/workflows/hello.py`
- Create: `backend/src/mdcopilot_blog/workflows/schedules.py`
- Create: `backend/src/mdcopilot_blog/worker.py`
- Modify: `backend/tests/conftest.py` (append the `# --- T11: DBOS fixtures ---` block and add its imports)
- Create: `backend/tests/workflows/__init__.py` (empty, if it does not exist yet)
- Test: `backend/tests/workflows/test_dbos_runtime.py`
- Test: `backend/tests/workflows/test_tracking.py`
- Test: `backend/tests/workflows/test_hello_pipeline.py`
- Test: `backend/tests/workflows/test_schedules.py`
- Test: `backend/tests/workflows/test_worker.py`

**Interfaces:**

**Consumes (exact names from earlier tasks)**

| Task | Names |
|---|---|
| T1 | `mdcopilot_blog.ids.uuid7`, `new_trace_id` |
| T2 | `Settings` (fields listed below), `get_settings()` |
| T3 | `mdcopilot_blog.logs.configure_logging(level)`, `bind_log_context(*, run_id, trace_id)`, `JsonFormatter` (tests only; its JSON uses `json.dumps` default separators, i.e. `"run_id": "…"`) |
| T4 | `domain.enums.AgentName`, `AttemptStatus`, `CallStatus`, `RunKind`, `RunStatus`, `StepStatus`; `domain.state_machine.Entity`, `InvalidTransition`, `require_transition` |
| T5 | `db.models.BlogRun`, `RunAttempt`, `AgentRun`, `LlmCall`; `db.engine.make_engine`, `make_sessionmaker`; conftest `TEST_DB`, `database_url` (session), `settings`, `clean_db` (truncates after the test) |
| T6 | `prompts.registry.PromptRegistry.from_directory`, `.sync_to_db`, `default_prompt_root()` |
| T8 | `python -m mdcopilot_blog.cli migrate` (manual steps only) |
| T9 | `workflows.names` (all constants); `workflows.client.WorkflowClient` (`enqueue`, `cancel`, `list_steps`, `status`, `fork_from_step`, `close`) and `StepView` |
| T10 | `llm.gateway.AgentSpec`, `CallContext`, `LLMGateway`, `build_gateway(settings, sessionmaker, prompts)`; `llm.mock.FixtureRegistry.load(agent, prompt_name)` |

Settings fields used from T2: `app_version`, `worker_executor_id`, `log_level`, `dbos_system_database_url`, `database_url()`, `mock_mode`, `mock_step_delay_seconds`, `scheduler_enabled`, `agent_enabled`, `daily_run_time`, `timezone`, `max_cost_per_run_usd`, `postgres_db`.

**Produces**

`workflows/dbos_config.py`
```text
DBOS_APP_NAME = "mdcopilot-blog"
DBOS_SYSTEM_SCHEMA = "dbos"
def build_dbos_config(settings: Settings) -> DBOSConfig
```

`workflows/runtime.py`
```text
@dataclass class WorkerRuntime: settings; engine; sessionmaker; prompts; gateway
def set_runtime(rt: WorkerRuntime | None) -> None
def get_runtime() -> WorkerRuntime  # RuntimeError if unset
async def build_runtime(settings: Settings) -> WorkerRuntime
```

`workflows/tracking.py`
```text
TERMINAL_RUN_STATUSES: frozenset[RunStatus]
def error_payload(exc: BaseException) -> dict[str, object]  # {"class", "message"[:2000]}
async def get_run_status(sm, run_id: uuid.UUID) -> RunStatus  # LookupError if missing
async def get_run_trace_id(sm, run_id: uuid.UUID) -> str  # LookupError if missing
async def get_attempt_status(sm, workflow_id: str) -> AttemptStatus | None
async def ensure_attempt(sm, *, run_id: uuid.UUID, workflow_id: str, workflow_name: str) -> uuid.UUID
async def finish_attempt(sm, *, workflow_id: str, status: AttemptStatus, error: Mapping[str, object] | None = None) -> None
async def set_run_status(sm, *, run_id: uuid.UUID, target: RunStatus, stage: str | None = None, error: Mapping[str, object] | None = None) -> None
@dataclass(frozen=True) class StepHandle(agent_run_id, workflow_id, step_id, trace_id, run_id, attempt_id); def call_context(self) -> CallContext
@asynccontextmanager async def track_step(sm, *, run_id, attempt_id, step_name, trace_id, agent_name=None, agent_version=None) -> AsyncIterator[StepHandle]
# track_step logs "step finished" (extra: step, status, duration_ms, tries[, error_class]) once per execution
```

`workflows/hello.py`
```text
class EchoOutput(BaseModel): message: str; word_count: int
HELLO_SPEC: AgentSpec[EchoOutput]
WORKFLOW_CANCELLED_ERROR = {"class": "WorkflowCancelled", "message": "cancelled or timed out by DBOS"}
# registered steps: hello.open_attempt, hello.echo, hello.finish, hello.mark_failed
async def open_attempt_step(run_id: str) -> dict[str, str]  # {"attempt_id", "trace_id"}
async def echo_step(run_id: str, attempt_id: str, trace_id: str) -> dict[str, object]  # mock delay, then gateway.run; {} if cancelled first
async def finish_step(run_id: str, attempt_id: str, trace_id: str) -> None
async def mark_failed_step(run_id: str, error_class: str, message: str) -> None
# registered workflow "hello_pipeline"; on DBOSWorkflowCancelledError: run FAILED (unless CANCELLED), attempt CANCELLED, re-raise
async def hello_pipeline(run_id: str) -> dict[str, object]  # {"run_id", "echo"}
```

`workflows/schedules.py`
```text
DAILY_TARGETS: dict[str, Callable[[str], Coroutine[Any, Any, dict[str, object]]]]
def daily_child_workflow_id(local_date: date) -> str  # "daily-YYYY-MM-DD"
def daily_cron(settings: Settings) -> str  # "M H * * *"
# registered step "daily.create_run"; returns the new run id, or the existing daily run's id while it is QUEUED
async def create_daily_run_step(run_date_iso: str) -> str | None
# registered workflow "daily_trigger"; enqueues the child on QUEUE_PIPELINE under "daily-YYYY-MM-DD"
async def daily_trigger(scheduled_at: datetime, context: Any) -> str | None
async def apply_daily_schedule(settings: Settings) -> None
async def catch_up_today(settings: Settings, now: datetime) -> str | None  # returns "catchup-YYYY-MM-DD" or None
```

`worker.py`
```text
async def heartbeat_loop(stop: asyncio.Event, path: Path = HEARTBEAT_FILE, interval: float = 10.0) -> None
def install_signal_handlers(stop: asyncio.Event) -> None
async def main() -> None
def run() -> None
```

`tests/conftest.py`
```text
DBOS_TEST_EXECUTOR_ID = "pytest"
DBOS_TEST_APP_VERSION = "pytest"
fixture dbos_runtime -> WorkerRuntime  # session scope, session loop
fixture make_run -> async (*, kind=RunKind.MANUAL, run_date=date(2026, 1, 15), status=RunStatus.QUEUED) -> uuid.UUID  # requests clean_db
```

Notes for Task 14:
- The worker's `stop_grace_period` (40 s) must stay above `WORKFLOW_COMPLETION_TIMEOUT_SECONDS = 25`.
- The heartbeat file is touched every 10 s.
- **Killing the worker during `hello.echo`.** `echo_step` runs its mock delay **before** `gateway.run`, and sets TOPICS_READY after the call.
  - A kill during the delay leaves the run RESEARCHING with 0 `blog_llm_calls` rows.
  - After the resume, `hello.echo` has `tries=2` and the run has exactly **1** call (total|echo|ok = `1|1|1`).
- **Log lines.** Every step execution logs a JSON line `"message": "step finished"` with `"run_id": "<run uuid>"` and `"trace_id"`, so `docker compose logs worker` shows 3 such lines for a normal run.

- [ ] **Step 1: Confirm the DBOS surface this task relies on (verify in container)**

Run:
```bash
docker compose run --rm tools python -c "import importlib.metadata as m; from dbos import DBOS; from dbos._error import DBOSWorkflowCancelledError as E; print(m.version('dbos')); print(sorted(n for n in dir(DBOS) if 'schedule' in n)); print(issubclass(E, Exception))"
```
Expected (exact, as verified):
```
3.0.0
['apply_schedules', 'apply_schedules_async', 'backfill_schedule', 'create_schedule', 'create_schedule_async', 'delete_schedule', 'delete_schedule_async', 'get_schedule', 'get_schedule_async', 'list_schedules', 'list_schedules_async', 'pause_schedule', 'resume_schedule', 'trigger_schedule']
False
```
Decision rules:
- **Version.** If the version is not `3.0.0`, stop and fix the lock (Task 1).
- **Pause and resume.** If `pause_schedule_async` and `resume_schedule_async` appear (a later patch release), you may switch to them in `apply_daily_schedule`; the `asyncio.to_thread` form below works either way, and the tests do not change.
- **Cancellation error.** If the last line prints `True`, the inner `except Exception` in `hello_pipeline` (Step 14) would catch a cancellation before the outer `except DBOSWorkflowCancelledError` sees it, and would try to start `mark_failed_step`. In that case:
  1. Add `except DBOSWorkflowCancelledError: raise` directly before that inner `except Exception`. The outer handler then still closes the run and attempt.
  2. Continue with Step 2.

- [ ] **Step 2: Write the DBOS-under-pytest probe and config test**

Create `backend/tests/workflows/__init__.py` as an empty file if it does not exist.

Create `backend/tests/workflows/test_dbos_runtime.py`:
```python
"""The in-process DBOS worker used by workflow tests, and the worker's DBOS configuration."""

import asyncio
import uuid

from dbos import DBOS, SetWorkflowID

from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.dbos_config import build_dbos_config
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE
from mdcopilot_blog.workflows.runtime import WorkerRuntime, get_runtime


@DBOS.step(name="test.probe_step")
async def probe_step(value: int) -> dict[str, object]:
    return {
        "workflow_id": DBOS.workflow_id,
        "step_id": DBOS.step_id,
        "value": value,
        "runtime_db": get_runtime().settings.postgres_db,
    }


@DBOS.workflow(name="test.probe_workflow")
async def probe_workflow(value: int) -> dict[str, object]:
    return await probe_step(value)


async def test_dbos_runs_a_queued_workflow_on_the_pytest_loop(dbos_runtime: WorkerRuntime) -> None:
    assert DBOS.executor_id == "pytest"
    assert DBOS.application_version == "pytest"
    workflow_id = f"probe-{uuid.uuid4().hex}"
    with SetWorkflowID(workflow_id):
        handle = await DBOS.enqueue_workflow_async(QUEUE_PIPELINE, probe_workflow, 7)
    result = await asyncio.wait_for(handle.get_result(), timeout=30)
    assert result == {"workflow_id": workflow_id, "step_id": 1, "value": 7, "runtime_db": "mdcopilot_blog_test"}


def test_build_dbos_config_pins_recovery_identity(settings: Settings) -> None:
    custom = settings.model_copy(update={"app_version": "9.9.9", "worker_executor_id": "worker-7"})
    config = build_dbos_config(custom)
    assert config["name"] == "mdcopilot-blog"
    assert config["application_version"] == "9.9.9"
    assert config["executor_id"] == "worker-7"
    assert config["dbos_system_schema"] == "dbos"
    assert config["system_database_url"] == custom.dbos_system_database_url
    assert config["system_database_url"].startswith("postgresql+psycopg://")
```

- [ ] **Step 3: Run it and see it fail**

Run: `docker compose run --rm tools pytest tests/workflows/test_dbos_runtime.py -q`

Expected: a collection error ending in:
```
E   ModuleNotFoundError: No module named 'mdcopilot_blog.workflows.dbos_config'
1 error in 0.05s
```

- [ ] **Step 4: Create `backend/src/mdcopilot_blog/workflows/dbos_config.py`**

```python
"""DBOS configuration for the worker process (the only process that calls DBOS.launch())."""

from dbos import DBOSConfig

from mdcopilot_blog.settings import Settings

DBOS_APP_NAME = "mdcopilot-blog"
DBOS_SYSTEM_SCHEMA = "dbos"


def build_dbos_config(settings: Settings) -> DBOSConfig:
    # Recovery only picks up PENDING workflows whose executor_id AND application_version match,
    # so both are explicit and stable across restarts (never the DBOS defaults).
    return {
        "name": DBOS_APP_NAME,
        "system_database_url": settings.dbos_system_database_url,
        "application_version": settings.app_version,
        "executor_id": settings.worker_executor_id,
        "dbos_system_schema": DBOS_SYSTEM_SCHEMA,
        "log_level": settings.log_level,
    }
```

- [ ] **Step 5: Create `backend/src/mdcopilot_blog/workflows/runtime.py`**

```python
"""Process-wide dependencies for workflow steps.

DBOS steps receive only serialisable arguments, so engine, sessionmaker, prompt registry and gateway
live in one module-level WorkerRuntime that the worker (or the test fixture) sets before DBOS.launch().
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.llm.gateway import LLMGateway, build_gateway
from mdcopilot_blog.prompts.registry import PromptRegistry, default_prompt_root
from mdcopilot_blog.settings import Settings


@dataclass
class WorkerRuntime:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    prompts: PromptRegistry
    gateway: LLMGateway


_runtime: WorkerRuntime | None = None


def set_runtime(rt: WorkerRuntime | None) -> None:
    global _runtime  # one runtime per worker process, set once at startup
    _runtime = rt


def get_runtime() -> WorkerRuntime:
    if _runtime is None:
        raise RuntimeError("worker runtime is not initialised; call set_runtime() before running workflows")
    return _runtime


async def build_runtime(settings: Settings) -> WorkerRuntime:
    engine = make_engine(settings.database_url())
    sessionmaker = make_sessionmaker(engine)
    prompts = PromptRegistry.from_directory(default_prompt_root())
    gateway = build_gateway(settings, sessionmaker, prompts)
    return WorkerRuntime(settings=settings, engine=engine, sessionmaker=sessionmaker, prompts=prompts, gateway=gateway)
```

- [ ] **Step 6: Add the T11 fixture block to `backend/tests/conftest.py`**

Add these imports to the import block at the top of the file, skipping any that the T5 or T9 blocks already added:
```python
import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date
from decimal import Decimal

import pytest_asyncio
from dbos import DBOS
from sqlalchemy import URL

from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import RunKind, RunStatus
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.settings import get_settings
from mdcopilot_blog.workflows.dbos_config import build_dbos_config
from mdcopilot_blog.workflows.names import QUEUE_INTERACTIVE, QUEUE_PIPELINE
from mdcopilot_blog.workflows.runtime import WorkerRuntime, build_runtime, set_runtime
```

Append this block at the end of the file. It uses `TEST_DB`, `database_url` and `clean_db` from the T5 block.
```python
# --- T11: DBOS fixtures ---
# In-process DBOS under pytest. DBOS.launch() runs inside the pytest-asyncio *session* loop, so queued and directly
# started async workflows run on the same loop as the tests.
# Variant used: in-loop launch (Task 11 Step 7 decision rule; the executor-thread fallback also passed in research).
DBOS_TEST_EXECUTOR_ID = "pytest"
DBOS_TEST_APP_VERSION = "pytest"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dbos_runtime(database_url: URL) -> AsyncIterator[WorkerRuntime]:
    test_settings = get_settings().model_copy(
        update={
            "postgres_db": TEST_DB,
            "mock_mode": True,
            "mock_step_delay_seconds": 0.0,
            "scheduler_enabled": False,
            # tests assert IST dates and must not hit the budget guard, whatever .env says
            "timezone": "Asia/Kolkata",
            "max_cost_per_run_usd": Decimal("5.00"),
        }
    )
    rt = await build_runtime(test_settings)
    async with rt.sessionmaker() as session:
        await rt.prompts.sync_to_db(session)
        await session.commit()
    set_runtime(rt)
    # Workflow modules register their steps and workflows when the test modules import them during
    # collection, which happens before this fixture runs, so they are registered before launch.
    DBOS(
        config=build_dbos_config(test_settings)
        | {"executor_id": DBOS_TEST_EXECUTOR_ID, "application_version": DBOS_TEST_APP_VERSION}
    )
    DBOS.launch()
    await DBOS.register_queue_async(QUEUE_PIPELINE, worker_concurrency=1)
    await DBOS.register_queue_async(QUEUE_INTERACTIVE, worker_concurrency=4)
    try:
        yield rt
    finally:
        await asyncio.to_thread(DBOS.destroy, destroy_registry=False)
        set_runtime(None)
        await rt.engine.dispose()


type MakeRun = Callable[..., Awaitable[uuid.UUID]]


@pytest_asyncio.fixture(loop_scope="session")
async def make_run(dbos_runtime: WorkerRuntime, clean_db: None) -> MakeRun:
    """Insert a blog_runs row through the worker runtime and return its id. Tables are truncated after the test."""

    async def _make(
        *, kind: RunKind = RunKind.MANUAL, run_date: date = date(2026, 1, 15), status: RunStatus = RunStatus.QUEUED
    ) -> uuid.UUID:
        run = BlogRun(kind=kind.value, run_date=run_date, status=status.value, params={}, trace_id=new_trace_id())
        async with dbos_runtime.sessionmaker() as session:
            session.add(run)
            await session.commit()
        return run.id

    return _make
```

Then sort the imports and remove any import that is now listed twice: `docker compose run --rm tools sh -c "ruff check --fix tests/conftest.py && ruff format tests/conftest.py"`

ruff 0.16.8 enables I001 (import order) and F811 (redefinition) by default, and `--fix` repairs both. It sorts the block, and it drops a repeated name such as a second `AsyncIterator`, `pytest`, `pytest_asyncio`, `URL` or `get_settings` that a hand merge of the T5, T9 and T11 import lists leaves behind.

Expected, first line:
- `All checks passed!` if the merge was already clean;
- otherwise `Found <n> errors (<n> fixed, 0 remaining).`

Expected, second line: `1 file left unchanged` or `1 file reformatted`.

If ruff reports errors that remain after the fix (`<k> remaining`), correct the listed lines by hand. Then run the command again until the first line is `All checks passed!`.

- [ ] **Step 7: Run the probe and apply the decision rule (in-process DBOS under pytest)**

The research did not cover in-process DBOS under pytest; this step verifies it in the project. (The pattern passed while this plan was written, against a stand-in project.)

Run: `docker compose run --rm tools timeout 120 pytest tests/workflows/test_dbos_runtime.py -q`

Expected: `2 passed` in a few seconds.

Decision rule:
- **`2 passed`: keep the in-loop launch.** Leave the conftest comment as `Variant used: in-loop launch (...)`.
- **Hang or loop error: switch to the fallback.** The failure shows as either:
  - a hang, where `timeout` ends the run with exit code 124 and no summary line;
  - an error mentioning the event loop (`attached to a different loop`, `Event loop is closed`, `no running event loop`).

  To switch, replace the line `    DBOS.launch()` in `dbos_runtime` with
  ```python
      await asyncio.get_running_loop().run_in_executor(None, DBOS.launch)
  ```
  and change the comment line to `# Variant used: executor-thread launch (Task 11 Step 7 decision rule).` Re-run the command; expected `2 passed`. This fallback also passed all 35 workflow tests of this task while this plan was checked.
- **Both variants fail:** stop and report the output. Do not continue to Step 8.

Record which variant was used in the Step 27 checkpoint.

- [ ] **Step 8: Write the failing tracking tests**

Create `backend/tests/workflows/test_tracking.py`:
```python
"""Run, attempt and step bookkeeping (workflows/tracking.py)."""

import asyncio
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable

import pytest
from dbos import DBOS, SetWorkflowID
from sqlalchemy import select

from mdcopilot_blog.db.models import AgentRun, BlogRun, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, RunStatus
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.workflows.names import WORKFLOW_HELLO
from mdcopilot_blog.workflows.runtime import WorkerRuntime, get_runtime
from mdcopilot_blog.workflows.tracking import (
    ensure_attempt,
    finish_attempt,
    get_run_status,
    set_run_status,
    track_step,
)

type MakeRun = Callable[..., Awaitable[uuid.UUID]]

TRACE_ID = "0" * 32
STEP_CALLS: Counter[str] = Counter()


@DBOS.step(name="test.tracked_step", retries_allowed=True, max_attempts=2, interval_seconds=0.01)
async def tracked_step(run_id: str, key: str, failures: int) -> int:
    rt = get_runtime()
    async with track_step(
        rt.sessionmaker, run_id=uuid.UUID(run_id), attempt_id=None, step_name="test.tracked_step", trace_id=TRACE_ID
    ) as handle:
        STEP_CALLS[key] += 1
        if STEP_CALLS[key] <= failures:
            raise ValueError(f"planned failure {STEP_CALLS[key]}")
    return handle.step_id


@DBOS.workflow(name="test.tracked_workflow")
async def tracked_workflow(run_id: str, key: str, failures: int) -> int:
    return await tracked_step(run_id, key, failures)


async def _agent_runs(rt: WorkerRuntime, run_id: uuid.UUID) -> list[AgentRun]:
    async with rt.sessionmaker() as session:
        return list((await session.scalars(select(AgentRun).where(AgentRun.run_id == run_id))).all())


async def _run(rt: WorkerRuntime, run_id: uuid.UUID) -> BlogRun:
    async with rt.sessionmaker() as session:
        run = await session.get(BlogRun, run_id)
    assert run is not None
    return run


async def test_track_step_outside_a_step_raises(dbos_runtime: WorkerRuntime) -> None:
    with pytest.raises(RuntimeError, match="inside a DBOS step"):
        async with track_step(
            dbos_runtime.sessionmaker, run_id=uuid.uuid4(), attempt_id=None, step_name="x", trace_id=TRACE_ID
        ):
            pass


async def test_track_step_records_one_row_per_step(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    run_id = await make_run()
    key = uuid.uuid4().hex
    with SetWorkflowID(f"track-ok-{key}"):
        handle = await DBOS.start_workflow_async(tracked_workflow, str(run_id), key, 0)
    assert await asyncio.wait_for(handle.get_result(), timeout=30) == 1
    [row] = await _agent_runs(dbos_runtime, run_id)
    assert (row.dbos_workflow_id, row.dbos_step_id, row.step_name) == (f"track-ok-{key}", 1, "test.tracked_step")
    assert (row.status, row.tries, row.error) == ("SUCCEEDED", 1, None)
    assert row.completed_at is not None
    assert row.duration_ms is not None
    assert row.duration_ms >= 0
    assert (row.input_tokens, row.output_tokens, row.trace_id) == (0, 0, TRACE_ID)


async def test_track_step_counts_dbos_retries_as_tries(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    run_id = await make_run()
    key = uuid.uuid4().hex
    with SetWorkflowID(f"track-retry-{key}"):
        handle = await DBOS.start_workflow_async(tracked_workflow, str(run_id), key, 1)
    assert await asyncio.wait_for(handle.get_result(), timeout=30) == 1
    [row] = await _agent_runs(dbos_runtime, run_id)
    assert (row.status, row.tries, row.error) == ("SUCCEEDED", 2, None)
    assert STEP_CALLS[key] == 2


async def test_track_step_records_failure_and_reraises(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    run_id = await make_run()
    key = uuid.uuid4().hex
    with SetWorkflowID(f"track-fail-{key}"):
        handle = await DBOS.start_workflow_async(tracked_workflow, str(run_id), key, 5)
    with pytest.raises(Exception, match="exceeded its maximum of 2 retries"):  # DBOSMaxStepRetriesExceeded
        await asyncio.wait_for(handle.get_result(), timeout=30)
    [row] = await _agent_runs(dbos_runtime, run_id)
    assert (row.status, row.tries) == ("FAILED", 2)
    assert row.error == {"class": "ValueError", "message": "planned failure 2"}


async def test_set_run_status_follows_the_state_machine(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    with pytest.raises(InvalidTransition):
        await set_run_status(sm, run_id=run_id, target=RunStatus.SUCCEEDED)

    await set_run_status(sm, run_id=run_id, target=RunStatus.RESEARCHING, stage="first")
    await set_run_status(sm, run_id=run_id, target=RunStatus.RESEARCHING, stage="ignored")  # same state: no-op
    run = await _run(dbos_runtime, run_id)
    assert (run.status, run.stage, run.finished_at) == ("RESEARCHING", "first", None)
    assert run.started_at is not None

    await set_run_status(sm, run_id=run_id, target=RunStatus.FAILED, error={"class": "Boom", "message": "m"})
    run = await _run(dbos_runtime, run_id)
    assert (run.status, run.error) == ("FAILED", {"class": "Boom", "message": "m"})
    assert run.finished_at is not None

    with pytest.raises(InvalidTransition):
        await set_run_status(sm, run_id=run_id, target=RunStatus.PRODUCING)

    await set_run_status(sm, run_id=run_id, target=RunStatus.QUEUED)  # retry re-opens a failed run
    run = await _run(dbos_runtime, run_id)
    assert (run.status, run.finished_at, run.error) == ("QUEUED", None, None)


async def test_set_run_status_unknown_run_raises_lookup_error(dbos_runtime: WorkerRuntime) -> None:
    with pytest.raises(LookupError):
        await set_run_status(dbos_runtime.sessionmaker, run_id=uuid.uuid4(), target=RunStatus.RESEARCHING)


async def test_ensure_attempt_is_idempotent_per_workflow_id(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    suffix = uuid.uuid4().hex
    first = await ensure_attempt(sm, run_id=run_id, workflow_id=f"a-{suffix}", workflow_name=WORKFLOW_HELLO)
    again = await ensure_attempt(sm, run_id=run_id, workflow_id=f"a-{suffix}", workflow_name=WORKFLOW_HELLO)
    second = await ensure_attempt(sm, run_id=run_id, workflow_id=f"b-{suffix}", workflow_name=WORKFLOW_HELLO)
    assert first == again
    assert second != first
    async with sm() as session:
        rows = (await session.scalars(select(RunAttempt).where(RunAttempt.run_id == run_id))).all()
    summary = sorted((r.attempt_no, r.dbos_workflow_id, r.status, r.forked_from_workflow_id) for r in rows)
    assert summary == [(1, f"a-{suffix}", "RUNNING", None), (2, f"b-{suffix}", "RUNNING", None)]
    assert all(r.started_at is not None and r.start_step is None for r in rows)  # called outside a step


async def test_ensure_attempt_for_a_cancelled_run_is_closed_at_once(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run(status=RunStatus.CANCELLED)
    workflow_id = f"c-{uuid.uuid4().hex}"
    attempt_id = await ensure_attempt(sm, run_id=run_id, workflow_id=workflow_id, workflow_name=WORKFLOW_HELLO)
    async with sm() as session:
        attempt = await session.get(RunAttempt, attempt_id)
    assert attempt is not None
    assert (attempt.status, attempt.attempt_no, attempt.forked_from_workflow_id) == ("CANCELLED", 1, None)
    assert attempt.finished_at is not None
    assert await get_run_status(sm, run_id) is RunStatus.CANCELLED  # an original attempt never re-opens a run


async def test_ensure_attempt_unknown_run_raises_lookup_error(dbos_runtime: WorkerRuntime) -> None:
    with pytest.raises(LookupError):
        await ensure_attempt(
            dbos_runtime.sessionmaker, run_id=uuid.uuid4(), workflow_id=uuid.uuid4().hex, workflow_name=WORKFLOW_HELLO
        )


async def test_finish_attempt_closes_only_open_attempts(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    workflow_id = f"fin-{uuid.uuid4().hex}"
    attempt_id = await ensure_attempt(sm, run_id=run_id, workflow_id=workflow_id, workflow_name=WORKFLOW_HELLO)
    await finish_attempt(sm, workflow_id=workflow_id, status=AttemptStatus.SUCCEEDED)
    await finish_attempt(sm, workflow_id=workflow_id, status=AttemptStatus.FAILED, error={"class": "Late"})
    await finish_attempt(sm, workflow_id="does-not-exist", status=AttemptStatus.FAILED)  # no-op
    async with sm() as session:
        attempt = await session.get(RunAttempt, attempt_id)
    assert attempt is not None
    assert (attempt.status, attempt.error) == ("SUCCEEDED", None)
    assert attempt.finished_at is not None
```

- [ ] **Step 9: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/workflows/test_tracking.py -q`

Expected: a collection error ending in:
```
E   ModuleNotFoundError: No module named 'mdcopilot_blog.workflows.tracking'
1 error in 0.06s
```

- [ ] **Step 10: Implement `backend/src/mdcopilot_blog/workflows/tracking.py`**

```python
"""Run, attempt and step bookkeeping shared by every workflow (ARCHITECTURE §5, §18).

- A run (blog_runs) is what the user sees. Every DBOS execution of it (original, fork) is an attempt
  (blog_run_attempts) keyed by dbos_workflow_id. Recovery re-uses the same workflow id, so it re-uses the attempt.
- Steps resolve their attempt from DBOS.workflow_id, never from inputs: fork_workflow copies earlier step outputs.
- Step rows (blog_agent_runs) are keyed by (dbos_workflow_id, dbos_step_id); a re-executed step bumps `tries`.
- Every write uses its own short session and commits immediately.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from dbos import DBOS
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import AgentRun, BlogRun, LlmCall, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, CallStatus, RunStatus, StepStatus
from mdcopilot_blog.domain.state_machine import Entity, require_transition
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.llm.gateway import CallContext

type SessionMaker = async_sessionmaker[AsyncSession]

logger = logging.getLogger(__name__)

TERMINAL_RUN_STATUSES = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})
OPEN_ATTEMPT_STATUSES = (AttemptStatus.ENQUEUED.value, AttemptStatus.RUNNING.value)
MAX_ERROR_MESSAGE = 2000


def _now() -> datetime:
    return datetime.now(UTC)


def error_payload(exc: BaseException) -> dict[str, object]:
    return {"class": type(exc).__name__, "message": str(exc)[:MAX_ERROR_MESSAGE]}


async def get_run_status(sm: SessionMaker, run_id: uuid.UUID) -> RunStatus:
    async with sm() as session:
        status = await session.scalar(select(BlogRun.status).where(BlogRun.id == run_id))
    if status is None:
        raise LookupError(f"run {run_id} not found")
    return RunStatus(status)


async def get_run_trace_id(sm: SessionMaker, run_id: uuid.UUID) -> str:
    async with sm() as session:
        trace_id = await session.scalar(select(BlogRun.trace_id).where(BlogRun.id == run_id))
    if trace_id is None:
        raise LookupError(f"run {run_id} not found")
    return trace_id


async def get_attempt_status(sm: SessionMaker, workflow_id: str) -> AttemptStatus | None:
    async with sm() as session:
        status = await session.scalar(select(RunAttempt.status).where(RunAttempt.dbos_workflow_id == workflow_id))
    return None if status is None else AttemptStatus(status)


async def _attempt_id_for(session: AsyncSession, workflow_id: str) -> uuid.UUID | None:
    attempt_id: uuid.UUID | None = await session.scalar(
        select(RunAttempt.id).where(RunAttempt.dbos_workflow_id == workflow_id)
    )
    return attempt_id


async def ensure_attempt(sm: SessionMaker, *, run_id: uuid.UUID, workflow_id: str, workflow_name: str) -> uuid.UUID:
    """Return the attempt for `workflow_id`, creating it on first use.

    A new attempt of a forked workflow re-opens a finished run (SUCCEEDED/FAILED/CANCELLED -> QUEUED),
    so the re-executed steps can move it forward again. An original attempt never re-opens a run:
    for a run cancelled before its workflow started, the attempt is recorded as CANCELLED at once.
    """
    async with sm() as session:
        found = await _attempt_id_for(session, workflow_id)
    if found is not None:
        return found

    statuses = await DBOS.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
    forked_from = statuses[0].forked_from if statuses else None

    async with sm() as session:
        run = await session.get(BlogRun, run_id, with_for_update=True)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        raced = await _attempt_id_for(session, workflow_id)
        if raced is not None:  # created concurrently while we waited for the run lock
            return raced
        count = await session.scalar(select(func.count()).select_from(RunAttempt).where(RunAttempt.run_id == run_id))
        now = _now()
        # the API cancelled the run while its workflow was still queued: nothing will ever close this attempt
        cancelled_before_start = forked_from is None and run.status == RunStatus.CANCELLED
        attempt = RunAttempt(
            id=uuid7(),
            run_id=run_id,
            dbos_workflow_id=workflow_id,
            workflow_name=workflow_name,
            attempt_no=(count or 0) + 1,
            forked_from_workflow_id=forked_from,
            start_step=DBOS.step_id,
            status=(AttemptStatus.CANCELLED if cancelled_before_start else AttemptStatus.RUNNING).value,
            started_at=now,
            finished_at=now if cancelled_before_start else None,
        )
        session.add(attempt)
        if forked_from is not None and RunStatus(run.status) in TERMINAL_RUN_STATUSES:
            require_transition(Entity.RUN, run.status, RunStatus.QUEUED)
            run.status = RunStatus.QUEUED.value
            run.finished_at = None
            run.error = None
        await session.commit()
        return attempt.id


async def finish_attempt(
    sm: SessionMaker, *, workflow_id: str, status: AttemptStatus, error: Mapping[str, object] | None = None
) -> None:
    """Close the attempt of `workflow_id`. No-op if it is missing or already closed (e.g. cancelled by the API)."""
    async with sm() as session:
        await session.execute(
            update(RunAttempt)
            .where(RunAttempt.dbos_workflow_id == workflow_id, RunAttempt.status.in_(OPEN_ATTEMPT_STATUSES))
            .values(status=status.value, finished_at=_now(), error=None if error is None else dict(error))
        )
        await session.commit()


async def set_run_status(
    sm: SessionMaker,
    *,
    run_id: uuid.UUID,
    target: RunStatus,
    stage: str | None = None,
    error: Mapping[str, object] | None = None,
) -> None:
    """Move a run through the state machine. Raises InvalidTransition (illegal move) or LookupError (no run)."""
    async with sm() as session:
        run = await session.get(BlogRun, run_id, with_for_update=True)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        if run.status == target:
            return
        require_transition(Entity.RUN, run.status, target)
        now = _now()
        run.status = target.value
        if stage is not None:
            run.stage = stage
        if error is not None:
            run.error = dict(error)
        if target is not RunStatus.QUEUED and run.started_at is None:
            run.started_at = now
        if target in TERMINAL_RUN_STATUSES:
            run.finished_at = now
        if target is RunStatus.QUEUED:  # a retry re-opens the run
            run.finished_at = None
            if error is None:
                run.error = None
        await session.commit()


@dataclass(frozen=True)
class StepHandle:
    agent_run_id: uuid.UUID
    workflow_id: str
    step_id: int
    trace_id: str
    run_id: uuid.UUID
    attempt_id: uuid.UUID | None

    def call_context(self) -> CallContext:
        return CallContext(
            trace_id=self.trace_id,
            run_id=self.run_id,
            attempt_id=self.attempt_id,
            agent_run_id=self.agent_run_id,
            dbos_workflow_id=self.workflow_id,
            dbos_step_id=self.step_id,
        )


async def _open_step_row(
    sm: SessionMaker,
    *,
    run_id: uuid.UUID,
    attempt_id: uuid.UUID | None,
    workflow_id: str,
    step_id: int,
    step_name: str,
    trace_id: str,
    agent_name: str | None,
    agent_version: str | None,
    started_at: datetime,
) -> tuple[uuid.UUID, int]:
    """Insert or re-open the step row; return its id and the number of executions so far."""
    stmt = insert(AgentRun).values(
        id=uuid7(),
        run_id=run_id,
        attempt_id=attempt_id,
        dbos_workflow_id=workflow_id,
        dbos_step_id=step_id,
        step_name=step_name,
        agent_name=agent_name,
        agent_version=agent_version,
        status=StepStatus.RUNNING.value,
        tries=1,
        started_at=started_at,
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal(0),
        sources_used=[],
        trace_id=trace_id,
    )
    upsert = stmt.on_conflict_do_update(
        constraint="uq_blog_agent_runs_wf_step",
        set_={
            "tries": AgentRun.tries + 1,
            "status": StepStatus.RUNNING.value,
            "attempt_id": attempt_id,
            "started_at": started_at,
            "completed_at": None,
            "duration_ms": None,
            "error": None,
        },
    ).returning(AgentRun.id, AgentRun.tries)
    async with sm() as session:
        agent_run_id, tries = (await session.execute(upsert)).one()
        await session.commit()
    return agent_run_id, tries


async def _close_step_row(
    sm: SessionMaker,
    *,
    agent_run_id: uuid.UUID,
    run_id: uuid.UUID,
    status: StepStatus,
    duration_ms: int,
    error: Mapping[str, object] | None,
) -> None:
    async with sm() as session:
        in_tokens, out_tokens, cost = (
            await session.execute(
                select(
                    func.coalesce(func.sum(LlmCall.input_tokens), 0),
                    func.coalesce(func.sum(LlmCall.output_tokens), 0),
                    func.coalesce(func.sum(LlmCall.cost_usd), 0),
                ).where(LlmCall.agent_run_id == agent_run_id)
            )
        ).one()
        last_ok = (
            await session.execute(
                select(
                    LlmCall.provider_requested,
                    LlmCall.model_requested,
                    LlmCall.model_served,
                    LlmCall.prompt_name,
                    LlmCall.prompt_version,
                )
                .where(LlmCall.agent_run_id == agent_run_id, LlmCall.status == CallStatus.OK.value)
                .order_by(LlmCall.created_at.desc())
                .limit(1)
            )
        ).first()
        values: dict[str, object] = {
            "status": status.value,
            "completed_at": _now(),
            "duration_ms": duration_ms,
            "input_tokens": int(in_tokens),
            "output_tokens": int(out_tokens),
            "cost_usd": Decimal(cost),
            "error": None if error is None else dict(error),
        }
        if last_ok is not None:
            provider, model_requested, model_served, prompt_name, prompt_version = last_ok
            values["model"] = model_served or f"{provider}:{model_requested}"
            values["prompt_name"] = prompt_name
            values["prompt_version"] = prompt_version
        await session.execute(update(AgentRun).where(AgentRun.id == agent_run_id).values(**values))
        run_cost = select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(LlmCall.run_id == run_id)
        await session.execute(update(BlogRun).where(BlogRun.id == run_id).values(cost_usd=run_cost.scalar_subquery()))
        await session.commit()


@asynccontextmanager
async def track_step(
    sm: SessionMaker,
    *,
    run_id: uuid.UUID,
    attempt_id: uuid.UUID | None,
    step_name: str,
    trace_id: str,
    agent_name: str | None = None,
    agent_version: str | None = None,
) -> AsyncIterator[StepHandle]:
    """Record one execution of the current DBOS step in blog_agent_runs. Must run inside a DBOS step.

    Each execution ends with one "step finished" log line. It carries the run_id/trace_id the step bound
    with bind_log_context.
    """
    workflow_id = DBOS.workflow_id
    step_id = DBOS.step_id
    if workflow_id is None or step_id is None:
        raise RuntimeError("track_step must be used inside a DBOS step (DBOS.workflow_id/step_id are unset)")
    started_at = _now()
    t0 = time.monotonic()
    agent_run_id, tries = await _open_step_row(
        sm,
        run_id=run_id,
        attempt_id=attempt_id,
        workflow_id=workflow_id,
        step_id=step_id,
        step_name=step_name,
        trace_id=trace_id,
        agent_name=agent_name,
        agent_version=agent_version,
        started_at=started_at,
    )
    handle = StepHandle(
        agent_run_id=agent_run_id,
        workflow_id=workflow_id,
        step_id=step_id,
        trace_id=trace_id,
        run_id=run_id,
        attempt_id=attempt_id,
    )
    try:
        yield handle
    except (Exception, asyncio.CancelledError) as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        await _close_step_row(
            sm,
            agent_run_id=agent_run_id,
            run_id=run_id,
            status=StepStatus.FAILED,
            duration_ms=duration_ms,
            error=error_payload(exc),
        )
        logger.warning(
            "step finished",
            extra={
                "step": step_name,
                "status": StepStatus.FAILED.value,
                "duration_ms": duration_ms,
                "tries": tries,
                "error_class": type(exc).__name__,
            },
        )
        raise
    duration_ms = int((time.monotonic() - t0) * 1000)
    await _close_step_row(
        sm,
        agent_run_id=agent_run_id,
        run_id=run_id,
        status=StepStatus.SUCCEEDED,
        duration_ms=duration_ms,
        error=None,
    )
    logger.info(
        "step finished",
        extra={"step": step_name, "status": StepStatus.SUCCEEDED.value, "duration_ms": duration_ms, "tries": tries},
    )
```

- [ ] **Step 11: Run the tracking tests and see them pass**

Run: `docker compose run --rm tools pytest tests/workflows/test_tracking.py -q`

Expected: `10 passed`

- [ ] **Step 12: Write the failing hello pipeline tests**

These tests cover:
- **End to end, through the API's `WorkflowClient`.** The run and attempt reach SUCCEEDED, three step rows are SUCCEEDED with `tries=1`, and one `blog_llm_calls` row has `kind=agent` and `agent_run_id` set.
- **JSON logs.** One `"step finished"` line per step, carrying the run's `run_id` and its 32-hex `trace_id`.
- **Failure.** The path taken when a mock fixture is missing.
- **Forks:**
  - a fork from `hello.finish`;
  - a fork from a step name that ran three times in a loop. Spike S1 is re-verified on a real workflow: the fork restarts at the **last** execution (`max(function_id)`) and copies everything before it.
- **Cancellation:**
  - an API cancel;
  - a DBOS workflow timeout (the run becomes FAILED, the attempt CANCELLED);
  - a run cancelled before its workflow starts (nothing changes; no LLM call);
  - a run cancelled between the echo call and TOPICS_READY (no step row fails).

The four cancellation tests use `monkeypatch` on `dbos_runtime.settings` or `dbos_runtime.gateway`, and pytest restores both after each test.

Create `backend/tests/workflows/test_hello_pipeline.py`:
```python
"""hello_pipeline end to end on the test database, with the in-process DBOS worker from `dbos_runtime`."""

import asyncio
import io
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio
from dbos import DBOS, DBOSClient, SetWorkflowID
from sqlalchemy import select

from mdcopilot_blog.db.models import AgentRun, BlogRun, LlmCall, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, RunStatus
from mdcopilot_blog.llm.mock import FixtureRegistry
from mdcopilot_blog.logs import JsonFormatter
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.dbos_config import DBOS_APP_NAME, DBOS_SYSTEM_SCHEMA
from mdcopilot_blog.workflows.hello import hello_pipeline
from mdcopilot_blog.workflows.names import (
    QUEUE_PIPELINE,
    STEP_HELLO_ECHO,
    STEP_HELLO_FAIL,
    STEP_HELLO_FINISH,
    STEP_HELLO_OPEN,
    WORKFLOW_HELLO,
)
from mdcopilot_blog.workflows.runtime import WorkerRuntime
from mdcopilot_blog.workflows.tracking import finish_attempt, get_run_status, set_run_status

type MakeRun = Callable[..., Awaitable[uuid.UUID]]
type LogLines = Callable[[], list[dict[str, Any]]]

ECHO = {"message": "Hello from the mock gateway", "word_count": 5}
WAIT_SECONDS = 60
LOOP_CALLS: list[tuple[str | None, str, int | None]] = []


@DBOS.step(name="test.before_loop")
async def before_loop_step() -> int | None:
    LOOP_CALLS.append((DBOS.workflow_id, "before", DBOS.step_id))
    return DBOS.step_id


@DBOS.step(name="test.loop_step")
async def loop_step(index: int) -> int | None:
    LOOP_CALLS.append((DBOS.workflow_id, f"loop{index}", DBOS.step_id))
    return DBOS.step_id


@DBOS.step(name="test.after_loop")
async def after_loop_step() -> int | None:
    LOOP_CALLS.append((DBOS.workflow_id, "after", DBOS.step_id))
    return DBOS.step_id


@DBOS.workflow(name="test.loop_workflow")
async def loop_workflow() -> list[int | None]:
    step_ids = [await before_loop_step()]
    for index in range(3):
        step_ids.append(await loop_step(index))
    step_ids.append(await after_loop_step())
    return step_ids


@dataclass
class RunRows:
    run: BlogRun
    attempts: list[RunAttempt]
    steps: list[AgentRun]
    calls: list[LlmCall]


async def load_rows(rt: WorkerRuntime, run_id: uuid.UUID) -> RunRows:
    async with rt.sessionmaker() as session:
        run = await session.get(BlogRun, run_id)
        assert run is not None
        attempts = (
            await session.scalars(select(RunAttempt).where(RunAttempt.run_id == run_id).order_by(RunAttempt.attempt_no))
        ).all()
        steps = (
            await session.scalars(
                select(AgentRun).where(AgentRun.run_id == run_id).order_by(AgentRun.created_at, AgentRun.dbos_step_id)
            )
        ).all()
        calls = (await session.scalars(select(LlmCall).where(LlmCall.run_id == run_id))).all()
    return RunRows(run, list(attempts), list(steps), list(calls))


async def wait_for_result(workflow_id: str) -> Any:
    handle = await DBOS.retrieve_workflow_async(workflow_id)
    return await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS)


async def start_hello(run_id: uuid.UUID) -> Any:
    """Start hello_pipeline directly (not through the queue) and return its result."""
    with SetWorkflowID(f"manual-{run_id}"):
        handle = await DBOS.start_workflow_async(hello_pipeline, str(run_id))
    return await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS)


@pytest_asyncio.fixture(loop_scope="session")
async def workflow_client(dbos_runtime: WorkerRuntime) -> AsyncIterator[WorkflowClient]:
    """The API's client, pointed at the test DB and at the version the in-process worker runs."""
    dbos_client = DBOSClient(
        system_database_url=dbos_runtime.settings.dbos_system_database_url,
        dbos_system_schema=DBOS_SYSTEM_SCHEMA,
        application_name=DBOS_APP_NAME,
        lazy=True,
    )
    client = WorkflowClient(dbos_client, DBOS.application_version)
    yield client
    await asyncio.to_thread(client.close)


@pytest.fixture
def step_log_lines() -> Iterator[LogLines]:
    """JSON lines (JsonFormatter) that workflows/tracking.py logs during the test."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    tracking_logger = logging.getLogger("mdcopilot_blog.workflows.tracking")
    previous_level = tracking_logger.level
    tracking_logger.addHandler(handler)
    tracking_logger.setLevel(logging.INFO)
    try:
        yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    finally:
        tracking_logger.removeHandler(handler)
        tracking_logger.setLevel(previous_level)


async def enqueue_hello(client: WorkflowClient, run_id: uuid.UUID, timeout_seconds: float = 120) -> str:
    return await client.enqueue(
        workflow_name=WORKFLOW_HELLO,
        queue_name=QUEUE_PIPELINE,
        workflow_id=f"manual-{run_id}",
        args=(str(run_id),),
        timeout_seconds=timeout_seconds,
    )


async def test_hello_pipeline_runs_end_to_end(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient
) -> None:
    run_id = await make_run()
    workflow_id = await enqueue_hello(workflow_client, run_id)
    assert workflow_id == f"manual-{run_id}"

    assert await wait_for_result(workflow_id) == {"run_id": str(run_id), "echo": ECHO}
    assert await workflow_client.status(workflow_id) == "SUCCESS"

    rows = await load_rows(dbos_runtime, run_id)
    assert (rows.run.status, rows.run.stage, rows.run.error) == ("SUCCEEDED", STEP_HELLO_FINISH, None)
    assert rows.run.started_at is not None
    assert rows.run.finished_at is not None

    [attempt] = rows.attempts
    assert (attempt.attempt_no, attempt.status, attempt.dbos_workflow_id) == (1, "SUCCEEDED", workflow_id)
    assert (attempt.workflow_name, attempt.forked_from_workflow_id, attempt.start_step) == (WORKFLOW_HELLO, None, 1)
    assert attempt.finished_at is not None

    assert [(s.step_name, s.dbos_step_id, s.status, s.tries) for s in rows.steps] == [
        (STEP_HELLO_OPEN, 1, "SUCCEEDED", 1),
        (STEP_HELLO_ECHO, 2, "SUCCEEDED", 1),
        (STEP_HELLO_FINISH, 3, "SUCCEEDED", 1),
    ]
    assert all(s.attempt_id == attempt.id and s.trace_id == rows.run.trace_id for s in rows.steps)
    echo_row = rows.steps[1]
    assert (echo_row.agent_name, echo_row.agent_version, echo_row.model) == ("hello", "1", "mock:hello")
    assert (echo_row.prompt_name, echo_row.prompt_version) == ("hello/echo", 1)
    assert (echo_row.input_tokens, echo_row.output_tokens) == (20, 8)

    [call] = rows.calls
    assert (call.kind, call.status, call.agent_run_id) == ("agent", "ok", echo_row.id)
    assert (call.attempt_id, call.dbos_workflow_id, call.dbos_step_id) == (attempt.id, workflow_id, 2)
    assert call.trace_id == rows.run.trace_id

    steps = await workflow_client.list_steps(workflow_id)
    assert [(s.function_id, s.function_name) for s in steps] == [
        (1, STEP_HELLO_OPEN),
        (2, STEP_HELLO_ECHO),
        (3, STEP_HELLO_FINISH),
    ]


async def test_step_logs_carry_run_and_trace_ids(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, step_log_lines: LogLines
) -> None:
    run_id = await make_run()
    await start_hello(run_id)
    trace_id = (await load_rows(dbos_runtime, run_id)).run.trace_id
    assert re.fullmatch(r"[0-9a-f]{32}", trace_id)

    finished = [
        line for line in step_log_lines() if line["message"] == "step finished" and line.get("run_id") == str(run_id)
    ]
    assert [(line["step"], line["status"], line["tries"], line["level"]) for line in finished] == [
        (STEP_HELLO_OPEN, "SUCCEEDED", 1, "INFO"),
        (STEP_HELLO_ECHO, "SUCCEEDED", 1, "INFO"),
        (STEP_HELLO_FINISH, "SUCCEEDED", 1, "INFO"),
    ]
    assert all(line["trace_id"] == trace_id for line in finished)
    assert all(isinstance(line["duration_ms"], int) for line in finished)


async def test_hello_pipeline_failure_marks_run_and_attempt_failed(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_fixture(self: FixtureRegistry, agent: str, prompt_name: str) -> dict[str, Any]:
        raise FileNotFoundError(f"mock fixture missing for {agent}/{prompt_name}")

    monkeypatch.setattr(FixtureRegistry, "load", missing_fixture)
    run_id = await make_run()
    workflow_id = f"manual-{run_id}"
    with pytest.raises(FileNotFoundError, match="mock fixture missing"):
        await start_hello(run_id)

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.status == "FAILED"
    assert rows.run.error is not None
    assert rows.run.error["class"] == "FileNotFoundError"
    assert rows.run.finished_at is not None

    [attempt] = rows.attempts
    assert attempt.status == "FAILED"
    assert attempt.error is not None
    assert attempt.error["class"] == "FileNotFoundError"
    assert attempt.finished_at is not None

    assert [(s.step_name, s.status, s.tries) for s in rows.steps] == [
        (STEP_HELLO_OPEN, "SUCCEEDED", 1),
        (STEP_HELLO_ECHO, "FAILED", 1),
    ]
    echo_row = rows.steps[1]
    assert echo_row.error is not None
    assert echo_row.error["class"] == "FileNotFoundError"
    assert "mock fixture missing" in str(echo_row.error["message"])

    [status] = await DBOS.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False)
    assert status.status == "ERROR"
    dbos_steps = await DBOS.list_workflow_steps_async(workflow_id)
    assert [s["function_name"] for s in dbos_steps] == [STEP_HELLO_OPEN, STEP_HELLO_ECHO, STEP_HELLO_FAIL]


async def test_fork_from_finish_adds_an_attempt_and_does_not_rerun_echo(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient
) -> None:
    run_id = await make_run()
    original_id = await enqueue_hello(workflow_client, run_id)
    await wait_for_result(original_id)

    fork_id = await workflow_client.fork_from_step(original_id, STEP_HELLO_FINISH, queue_name=QUEUE_PIPELINE)
    assert fork_id != original_id
    assert await wait_for_result(fork_id) == {"run_id": str(run_id), "echo": ECHO}

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.status == "SUCCEEDED"
    assert [
        (a.attempt_no, a.dbos_workflow_id, a.status, a.forked_from_workflow_id, a.start_step) for a in rows.attempts
    ] == [
        (1, original_id, "SUCCEEDED", None, 1),
        (2, fork_id, "SUCCEEDED", original_id, 3),
    ]
    assert len(rows.calls) == 1  # echo was copied, not re-executed
    assert [(s.dbos_workflow_id, s.step_name, s.status, s.tries) for s in rows.steps] == [
        (original_id, STEP_HELLO_OPEN, "SUCCEEDED", 1),
        (original_id, STEP_HELLO_ECHO, "SUCCEEDED", 1),
        (original_id, STEP_HELLO_FINISH, "SUCCEEDED", 1),
        (fork_id, STEP_HELLO_FINISH, "SUCCEEDED", 1),
    ]
    assert rows.steps[3].attempt_id == rows.attempts[1].id
    assert rows.steps[3].dbos_step_id == 3

    fork_steps = await workflow_client.list_steps(fork_id)
    assert [s.function_name for s in fork_steps] == [STEP_HELLO_OPEN, STEP_HELLO_ECHO, STEP_HELLO_FINISH]


async def test_fork_from_a_repeated_step_restarts_at_its_last_execution(
    dbos_runtime: WorkerRuntime, workflow_client: WorkflowClient
) -> None:
    workflow_id = f"loop-{uuid.uuid4().hex}"
    with SetWorkflowID(workflow_id):
        handle = await DBOS.start_workflow_async(loop_workflow)
    assert await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS) == [1, 2, 3, 4, 5]

    fork_id = await workflow_client.fork_from_step(workflow_id, "test.loop_step", queue_name=QUEUE_PIPELINE)
    assert await wait_for_result(fork_id) == [1, 2, 3, 4, 5]

    fork_steps = await workflow_client.list_steps(fork_id)
    assert [(s.function_id, s.function_name) for s in fork_steps] == [
        (1, "test.before_loop"),
        (2, "test.loop_step"),
        (3, "test.loop_step"),
        (4, "test.loop_step"),
        (5, "test.after_loop"),
    ]
    # function ids 1-3 were copied; only the last loop_step execution (id 4) and what follows ran again
    assert [(name, step_id) for wf, name, step_id in LOOP_CALLS if wf == workflow_id] == [
        ("before", 1),
        ("loop0", 2),
        ("loop1", 3),
        ("loop2", 4),
        ("after", 5),
    ]
    assert [(name, step_id) for wf, name, step_id in LOOP_CALLS if wf == fork_id] == [("loop2", 4), ("after", 5)]


async def test_cancelled_run_stays_cancelled(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        dbos_runtime, "settings", dbos_runtime.settings.model_copy(update={"mock_step_delay_seconds": 1.0})
    )
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    workflow_id = await enqueue_hello(workflow_client, run_id)
    async with asyncio.timeout(WAIT_SECONDS):
        while await get_run_status(sm, run_id) is not RunStatus.RESEARCHING:
            await asyncio.sleep(0.05)

    # what the runs API does on cancel (Task 12): cancel in DBOS, then close the attempt and the run
    await workflow_client.cancel(workflow_id)
    await finish_attempt(sm, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
    await set_run_status(sm, run_id=run_id, target=RunStatus.CANCELLED)

    with pytest.raises(Exception, match="cancelled"):  # DBOSAwaitedWorkflowCancelledError
        await wait_for_result(workflow_id)
    async with asyncio.timeout(WAIT_SECONDS):  # the running step finishes; no later step starts
        while (await load_rows(dbos_runtime, run_id)).steps[0].status == "RUNNING":
            await asyncio.sleep(0.05)
    await asyncio.sleep(0.5)

    rows = await load_rows(dbos_runtime, run_id)
    assert (rows.run.status, rows.run.error) == ("CANCELLED", None)
    assert [a.status for a in rows.attempts] == ["CANCELLED"]
    assert [(s.step_name, s.status) for s in rows.steps] == [(STEP_HELLO_OPEN, "SUCCEEDED")]
    assert rows.calls == []
    assert await workflow_client.status(workflow_id) == "CANCELLED"


async def test_workflow_timeout_fails_the_run_and_cancels_the_attempt(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, workflow_client: WorkflowClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DBOS cancels a workflow whose timeout passed; the next step start raises DBOSWorkflowCancelledError
    monkeypatch.setattr(
        dbos_runtime, "settings", dbos_runtime.settings.model_copy(update={"mock_step_delay_seconds": 2.0})
    )
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    workflow_id = await enqueue_hello(workflow_client, run_id, timeout_seconds=1)
    with pytest.raises(Exception, match="cancelled"):  # DBOSAwaitedWorkflowCancelledError
        await wait_for_result(workflow_id)
    async with asyncio.timeout(WAIT_SECONDS):
        while await get_run_status(sm, run_id) is not RunStatus.FAILED:
            await asyncio.sleep(0.05)

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.error == {"class": "WorkflowCancelled", "message": "cancelled or timed out by DBOS"}
    assert rows.run.finished_at is not None
    [attempt] = rows.attempts
    assert (attempt.status, attempt.error) == ("CANCELLED", None)
    assert attempt.finished_at is not None
    assert [(s.step_name, s.status) for s in rows.steps] == [(STEP_HELLO_OPEN, "SUCCEEDED")]
    assert rows.calls == []
    assert await workflow_client.status(workflow_id) == "CANCELLED"


async def test_workflow_of_a_run_cancelled_while_queued_changes_nothing(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    run_id = await make_run(status=RunStatus.CANCELLED)
    assert await start_hello(run_id) == {"run_id": str(run_id), "echo": {}}

    rows = await load_rows(dbos_runtime, run_id)
    assert (rows.run.status, rows.run.started_at, rows.run.error) == ("CANCELLED", None, None)
    [attempt] = rows.attempts
    assert attempt.status == "CANCELLED"
    assert attempt.finished_at is not None
    assert [(s.step_name, s.status) for s in rows.steps] == [
        (STEP_HELLO_OPEN, "SUCCEEDED"),
        (STEP_HELLO_ECHO, "SUCCEEDED"),
        (STEP_HELLO_FINISH, "SUCCEEDED"),
    ]
    assert rows.calls == []


async def test_cancel_during_the_echo_call_is_not_a_step_failure(
    dbos_runtime: WorkerRuntime, make_run: MakeRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    sm = dbos_runtime.sessionmaker
    run_id = await make_run()
    real_run = dbos_runtime.gateway.run

    async def run_then_cancel(*args: Any, **kwargs: Any) -> Any:
        result = await real_run(*args, **kwargs)
        await set_run_status(sm, run_id=run_id, target=RunStatus.CANCELLED)  # the API cancels meanwhile
        return result

    monkeypatch.setattr(dbos_runtime.gateway, "run", run_then_cancel)
    assert await start_hello(run_id) == {"run_id": str(run_id), "echo": ECHO}

    rows = await load_rows(dbos_runtime, run_id)
    assert rows.run.status == "CANCELLED"
    assert rows.run.stage == STEP_HELLO_OPEN  # TOPICS_READY was never written
    assert [a.status for a in rows.attempts] == ["CANCELLED"]
    assert [(s.step_name, s.status, s.error) for s in rows.steps] == [
        (STEP_HELLO_OPEN, "SUCCEEDED", None),
        (STEP_HELLO_ECHO, "SUCCEEDED", None),
        (STEP_HELLO_FINISH, "SUCCEEDED", None),
    ]
    assert len(rows.calls) == 1
```

- [ ] **Step 13: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/workflows/test_hello_pipeline.py -q`

Expected: a collection error ending in:
```
E   ModuleNotFoundError: No module named 'mdcopilot_blog.workflows.hello'
1 error in 0.06s
```

- [ ] **Step 14: Implement `backend/src/mdcopilot_blog/workflows/hello.py`**

```python
"""Phase 1 durable mock pipeline: three tracked steps through the LLM gateway (mock fixtures only).

Every step body is safe to execute twice. DBOS re-executes a step after a crash when the step finished its
side effects but its output was not yet recorded. So echo_step waits (mock delay) before its gateway call, and
a worker killed during that wait leaves no recorded call behind.

A run can be cancelled (Task 12) while a step executes. The step then stops without changing the run, closes
its attempt as CANCELLED and returns normally; DBOS stops the workflow when the next step starts.
"""

import asyncio
import contextlib
import logging
import uuid

from dbos import DBOS
from dbos._error import DBOSWorkflowCancelledError
from pydantic import BaseModel

from mdcopilot_blog.domain.enums import AgentName, AttemptStatus, RunStatus
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.llm.gateway import AgentSpec
from mdcopilot_blog.logs import bind_log_context
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.names import (
    STEP_HELLO_ECHO,
    STEP_HELLO_FAIL,
    STEP_HELLO_FINISH,
    STEP_HELLO_OPEN,
    WORKFLOW_HELLO,
)
from mdcopilot_blog.workflows.runtime import WorkerRuntime, get_runtime
from mdcopilot_blog.workflows.tracking import (
    ensure_attempt,
    finish_attempt,
    get_attempt_status,
    get_run_status,
    get_run_trace_id,
    set_run_status,
    track_step,
)

logger = logging.getLogger(__name__)

WORKFLOW_CANCELLED_ERROR = {"class": "WorkflowCancelled", "message": "cancelled or timed out by DBOS"}


class EchoOutput(BaseModel):
    message: str
    word_count: int


HELLO_SPEC = AgentSpec(
    name=AgentName.HELLO,
    version="1",
    prompt_name="hello/echo",
    output_type=EchoOutput,
    max_output_tokens=200,
)


def _current_workflow_id() -> str:
    workflow_id = DBOS.workflow_id
    if workflow_id is None:
        raise RuntimeError("hello steps must run inside the hello_pipeline workflow")
    return workflow_id


async def _mock_delay(settings: Settings) -> None:
    if settings.mock_mode and settings.mock_step_delay_seconds > 0:
        await asyncio.sleep(settings.mock_step_delay_seconds)


async def _attempt_of_current_workflow(rt: WorkerRuntime, run_id: uuid.UUID, copied_attempt_id: str) -> uuid.UUID:
    """A fork copies earlier step outputs, including the original attempt id. Resolve our own attempt instead."""
    attempt_id = await ensure_attempt(
        rt.sessionmaker, run_id=run_id, workflow_id=_current_workflow_id(), workflow_name=WORKFLOW_HELLO
    )
    if str(attempt_id) != copied_attempt_id:
        logger.info(
            "step runs in a forked workflow; using its own attempt",
            extra={"attempt_id": str(attempt_id), "copied_attempt_id": copied_attempt_id},
        )
    return attempt_id


async def _stop_if_cancelled(rt: WorkerRuntime, run_id: uuid.UUID, workflow_id: str) -> bool:
    """True if the run is CANCELLED. This workflow's attempt is then closed as CANCELLED."""
    if await get_run_status(rt.sessionmaker, run_id) is not RunStatus.CANCELLED:
        return False
    await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.CANCELLED)
    logger.info("run is cancelled; the step stops without changing it", extra={"workflow_id": workflow_id})
    return True


async def _advance(rt: WorkerRuntime, run_id: uuid.UUID, workflow_id: str, target: RunStatus, stage: str) -> bool:
    """Move the run to `target`. False if the run was cancelled first (the move is then skipped)."""
    try:
        await set_run_status(rt.sessionmaker, run_id=run_id, target=target, stage=stage)
    except InvalidTransition:
        # set_run_status locks the run row, so a cancel either landed before this move (CANCELLED -> target is
        # illegal and lands here) or after it (and the API cancels from the new status).
        if await _stop_if_cancelled(rt, run_id, workflow_id):
            return False
        raise
    return True


@DBOS.step(name=STEP_HELLO_OPEN)
async def open_attempt_step(run_id: str) -> dict[str, str]:
    rt = get_runtime()
    rid = uuid.UUID(run_id)
    workflow_id = _current_workflow_id()
    trace_id = await get_run_trace_id(rt.sessionmaker, rid)
    bind_log_context(run_id=run_id, trace_id=trace_id)
    attempt_id = await ensure_attempt(
        rt.sessionmaker, run_id=rid, workflow_id=workflow_id, workflow_name=WORKFLOW_HELLO
    )
    opened = {"attempt_id": str(attempt_id), "trace_id": trace_id}
    async with track_step(
        rt.sessionmaker, run_id=rid, attempt_id=attempt_id, step_name=STEP_HELLO_OPEN, trace_id=trace_id
    ):
        if not await _advance(rt, rid, workflow_id, RunStatus.RESEARCHING, STEP_HELLO_OPEN):
            return opened
        await _mock_delay(rt.settings)
    return opened


@DBOS.step(name=STEP_HELLO_ECHO)
async def echo_step(run_id: str, attempt_id: str, trace_id: str) -> dict[str, object]:
    rt = get_runtime()
    rid = uuid.UUID(run_id)
    workflow_id = _current_workflow_id()
    bind_log_context(run_id=run_id, trace_id=trace_id)
    own_attempt_id = await _attempt_of_current_workflow(rt, rid, attempt_id)
    async with track_step(
        rt.sessionmaker,
        run_id=rid,
        attempt_id=own_attempt_id,
        step_name=STEP_HELLO_ECHO,
        trace_id=trace_id,
        agent_name=AgentName.HELLO.value,
        agent_version=HELLO_SPEC.version,
    ) as handle:
        # a fork that starts at this step re-opened the run; enter the research stage first
        reopened = await get_run_status(rt.sessionmaker, rid) is RunStatus.QUEUED
        if reopened and not await _advance(rt, rid, workflow_id, RunStatus.RESEARCHING, STEP_HELLO_ECHO):
            return {}
        # delay first: a crash during the delay must not leave a recorded (in Phase 2, paid) call behind
        await _mock_delay(rt.settings)
        if await _stop_if_cancelled(rt, rid, workflow_id):  # no gateway call for a cancelled run
            return {}
        result = await rt.gateway.run(
            HELLO_SPEC,
            variables={"brand_name": "MDCopilot", "topic": "hello"},
            user_prompt="Say hello.",
            ctx=handle.call_context(),
        )
        await _advance(rt, rid, workflow_id, RunStatus.TOPICS_READY, STEP_HELLO_ECHO)
    return result.output.model_dump()


@DBOS.step(name=STEP_HELLO_FINISH)
async def finish_step(run_id: str, attempt_id: str, trace_id: str) -> None:
    rt = get_runtime()
    rid = uuid.UUID(run_id)
    bind_log_context(run_id=run_id, trace_id=trace_id)
    own_attempt_id = await _attempt_of_current_workflow(rt, rid, attempt_id)
    workflow_id = _current_workflow_id()
    async with track_step(
        rt.sessionmaker, run_id=rid, attempt_id=own_attempt_id, step_name=STEP_HELLO_FINISH, trace_id=trace_id
    ):
        # skip on re-execution: a crash after finish_attempt committed must not move a SUCCEEDED run again
        if await get_attempt_status(rt.sessionmaker, workflow_id) is not AttemptStatus.SUCCEEDED:
            for target in (RunStatus.PRODUCING, RunStatus.SUCCEEDED):
                if not await _advance(rt, rid, workflow_id, target, STEP_HELLO_FINISH):
                    return
            await finish_attempt(rt.sessionmaker, workflow_id=workflow_id, status=AttemptStatus.SUCCEEDED)
        await _mock_delay(rt.settings)


@DBOS.step(name=STEP_HELLO_FAIL)
async def mark_failed_step(run_id: str, error_class: str, message: str) -> None:
    rt = get_runtime()
    error = {"class": error_class, "message": message[:2000]}
    try:
        await set_run_status(rt.sessionmaker, run_id=uuid.UUID(run_id), target=RunStatus.FAILED, error=error)
    except (LookupError, ValueError) as exc:  # InvalidTransition is a ValueError: the run is already final
        logger.warning("run not marked failed", extra={"run_id": run_id, "reason": str(exc)})
    await finish_attempt(rt.sessionmaker, workflow_id=_current_workflow_id(), status=AttemptStatus.FAILED, error=error)


async def _close_cancelled_workflow(run_id: str) -> None:
    """Close the run and attempt of a workflow that DBOS cancelled (API cancel or workflow timeout).

    A plain coroutine, not a DBOS step: no step of a cancelled workflow can start. A run the API already
    cancelled stays CANCELLED (CANCELLED -> FAILED is illegal); a timed-out run becomes FAILED.
    """
    rt = get_runtime()
    with contextlib.suppress(InvalidTransition, LookupError):
        await set_run_status(
            rt.sessionmaker, run_id=uuid.UUID(run_id), target=RunStatus.FAILED, error=WORKFLOW_CANCELLED_ERROR
        )
    await finish_attempt(rt.sessionmaker, workflow_id=_current_workflow_id(), status=AttemptStatus.CANCELLED)
    logger.warning("workflow cancelled by DBOS", extra={"run_id": run_id})


@DBOS.workflow(name=WORKFLOW_HELLO)
async def hello_pipeline(run_id: str) -> dict[str, object]:
    # DBOS reports a cancel and a workflow timeout as DBOSWorkflowCancelledError, raised when the next step
    # starts. It is a BaseException, so the inner `except Exception` never records it as a step failure.
    try:
        try:
            opened = await open_attempt_step(run_id)
            echo = await echo_step(run_id, opened["attempt_id"], opened["trace_id"])
            await finish_step(run_id, opened["attempt_id"], opened["trace_id"])
        except Exception as exc:
            await mark_failed_step(run_id, type(exc).__name__, str(exc))
            raise
    except DBOSWorkflowCancelledError:
        await _close_cancelled_workflow(run_id)
        raise
    return {"run_id": run_id, "echo": echo}
```

- [ ] **Step 15: Run the hello pipeline tests and see them pass**

Run: `docker compose run --rm tools pytest tests/workflows/test_hello_pipeline.py -q`

Expected: `9 passed`, in about 12 s. The API-cancel test uses 1 s mock delays, and the timeout test uses 2 s delays with a 1 s workflow timeout.

Diagnostics:
- **Only `echo_row.model == "mock:hello"` fails** in `test_hello_pipeline_runs_end_to_end`. Check that Task 10 records `model_served` as the served `ModelResponse.model_name`. `MockModelFactory` names the model `f"mock:{spec.name}"`.
- **The timeout test hangs for 60 s and then fails in `asyncio.timeout`.** The run never became FAILED, which means the outer `except DBOSWorkflowCancelledError` in `hello_pipeline` is missing or never ran. Compare with Step 14.

- [ ] **Step 16: Write the failing schedule tests**

Create `backend/tests/workflows/test_schedules.py`:
```python
"""Daily schedule: cron formatting, idempotent daily run creation, trigger child ids, pause state, catch-up."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from dbos import DBOS
from sqlalchemy import select

from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import RunKind, RunStatus
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, SCHEDULE_DAILY, WORKFLOW_DAILY_TRIGGER
from mdcopilot_blog.workflows.runtime import WorkerRuntime
from mdcopilot_blog.workflows.schedules import (
    apply_daily_schedule,
    catch_up_today,
    create_daily_run_step,
    daily_cron,
    daily_trigger,
)

type MakeRun = Callable[..., Awaitable[uuid.UUID]]

IST = ZoneInfo("Asia/Kolkata")
WAIT_SECONDS = 60


async def wait_for_result(workflow_id: str) -> Any:
    handle = await DBOS.retrieve_workflow_async(workflow_id)
    return await asyncio.wait_for(handle.get_result(), timeout=WAIT_SECONDS)


async def daily_runs(rt: WorkerRuntime, run_date: date) -> list[BlogRun]:
    async with rt.sessionmaker() as session:
        rows = await session.scalars(
            select(BlogRun).where(BlogRun.kind == RunKind.DAILY.value, BlogRun.run_date == run_date)
        )
        return list(rows.all())


@pytest.mark.parametrize(
    ("run_time", "expected"),
    [("07:00", "0 7 * * *"), ("23:59", "59 23 * * *"), ("00:05", "5 0 * * *"), ("18:30", "30 18 * * *")],
)
def test_daily_cron_formats_minute_then_hour(settings: Settings, run_time: str, expected: str) -> None:
    assert daily_cron(settings.model_copy(update={"daily_run_time": run_time})) == expected


async def test_create_daily_run_step_is_idempotent_per_date(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    first = await create_daily_run_step("2026-02-10")
    second = await create_daily_run_step("2026-02-10")  # a re-executed step gets the same, still queued, run
    assert first is not None
    assert second == first
    [run] = await daily_runs(dbos_runtime, date(2026, 2, 10))
    assert str(run.id) == first
    assert (run.status, run.params) == ("QUEUED", {"source": "schedule"})
    assert len(run.trace_id) == 32


async def test_create_daily_run_step_skips_date_with_active_manual_run(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    await make_run(kind=RunKind.MANUAL, run_date=date(2026, 2, 11), status=RunStatus.PRODUCING)
    assert await create_daily_run_step("2026-02-11") is None
    assert await daily_runs(dbos_runtime, date(2026, 2, 11)) == []


async def test_create_daily_run_step_ignores_failed_or_cancelled_manual_runs(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    await make_run(kind=RunKind.MANUAL, run_date=date(2026, 2, 12), status=RunStatus.FAILED)
    await make_run(kind=RunKind.MANUAL, run_date=date(2026, 2, 12), status=RunStatus.CANCELLED)
    assert await create_daily_run_step("2026-02-12") is not None
    assert len(await daily_runs(dbos_runtime, date(2026, 2, 12))) == 1


async def test_daily_trigger_starts_child_named_after_the_local_date(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    # 20:00 UTC on 1 March is 01:30 on 2 March in Asia/Kolkata
    child_id = await daily_trigger(datetime(2026, 3, 1, 20, 0, tzinfo=UTC), {"source": "test"})
    assert child_id == "daily-2026-03-02"
    result = await wait_for_result(child_id)
    [run] = await daily_runs(dbos_runtime, date(2026, 3, 2))
    assert result["run_id"] == str(run.id)
    assert run.status == "SUCCEEDED"
    [child] = await DBOS.list_workflows_async(workflow_ids=[child_id], load_input=False, load_output=False)
    assert child.queue_name == QUEUE_PIPELINE  # enqueued behind any in-flight run, never started beside it

    again = await daily_trigger(datetime(2026, 3, 2, 7, 0, tzinfo=IST), {"source": "test"})
    assert again is None
    assert len(await daily_runs(dbos_runtime, date(2026, 3, 2))) == 1


async def test_daily_trigger_starts_the_workflow_of_a_still_queued_daily_run(
    dbos_runtime: WorkerRuntime, make_run: MakeRun
) -> None:
    # the worker died after create_daily_run_step's insert committed but before DBOS recorded its output
    orphan = await make_run(kind=RunKind.DAILY, run_date=date(2026, 3, 5), status=RunStatus.QUEUED)
    assert await create_daily_run_step("2026-03-05") == str(orphan)

    child_id = await daily_trigger(datetime(2026, 3, 5, 7, 0, tzinfo=IST), {"source": "test"})
    assert child_id == "daily-2026-03-05"
    assert (await wait_for_result(child_id))["run_id"] == str(orphan)
    [run] = await daily_runs(dbos_runtime, date(2026, 3, 5))
    assert (run.id, run.status) == (orphan, "SUCCEEDED")
    assert await create_daily_run_step("2026-03-05") is None  # the run has left QUEUED


async def test_apply_daily_schedule_is_paused_when_scheduler_disabled(dbos_runtime: WorkerRuntime) -> None:
    disabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": False, "daily_run_time": "07:00"})
    await apply_daily_schedule(disabled)

    schedule = await DBOS.get_schedule_async(SCHEDULE_DAILY)
    assert schedule is not None
    assert schedule["status"] == "PAUSED"
    assert schedule["workflow_name"] == WORKFLOW_DAILY_TRIGGER
    assert schedule["schedule"] == "0 7 * * *"
    assert schedule["cron_timezone"] == "Asia/Kolkata"
    assert schedule["queue_name"] == QUEUE_PIPELINE
    assert schedule["automatic_backfill"] is False
    listed = await DBOS.list_schedules_async(schedule_name_prefix=SCHEDULE_DAILY)
    assert [(s["schedule_name"], s["status"]) for s in listed] == [(SCHEDULE_DAILY, "PAUSED")]


async def test_apply_daily_schedule_follows_the_enabled_flag(dbos_runtime: WorkerRuntime) -> None:
    # a slot 12 hours away, so the schedule cannot fire while it is briefly active
    far_slot = (datetime.now(IST) + timedelta(hours=12)).strftime("%H:%M")
    enabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": True, "daily_run_time": far_slot})
    disabled = enabled.model_copy(update={"scheduler_enabled": False})
    try:
        await apply_daily_schedule(enabled)
        schedule = await DBOS.get_schedule_async(SCHEDULE_DAILY)
        assert schedule is not None
        assert (schedule["status"], schedule["schedule"]) == ("ACTIVE", daily_cron(enabled))
    finally:
        await apply_daily_schedule(disabled)
    schedule = await DBOS.get_schedule_async(SCHEDULE_DAILY)
    assert schedule is not None
    assert schedule["status"] == "PAUSED"


async def test_catch_up_today_does_nothing_when_disabled_or_before_the_slot(dbos_runtime: WorkerRuntime) -> None:
    disabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": False, "daily_run_time": "07:00"})
    enabled = disabled.model_copy(update={"scheduler_enabled": True})
    after_slot = datetime(2026, 4, 9, 5, 0, tzinfo=UTC)  # 10:30 IST
    before_slot = datetime(2026, 4, 9, 1, 0, tzinfo=UTC)  # 06:30 IST
    assert await catch_up_today(disabled, after_slot) is None
    assert await catch_up_today(enabled, before_slot) is None
    assert await DBOS.list_workflows_async(workflow_ids=["daily-2026-04-09"]) == []


async def test_catch_up_today_starts_missed_run_once(dbos_runtime: WorkerRuntime, make_run: MakeRun) -> None:
    enabled = dbos_runtime.settings.model_copy(update={"scheduler_enabled": True, "daily_run_time": "07:00"})
    now = datetime(2026, 4, 10, 5, 0, tzinfo=UTC)  # 10:30 IST, slot 07:00 IST has passed
    trigger_id = await catch_up_today(enabled, now)
    assert trigger_id == "catchup-2026-04-10"
    assert await wait_for_result(trigger_id) == "daily-2026-04-10"
    await wait_for_result("daily-2026-04-10")
    [run] = await daily_runs(dbos_runtime, date(2026, 4, 10))
    assert run.status == "SUCCEEDED"

    assert await catch_up_today(enabled, now + timedelta(hours=1)) is None
```

- [ ] **Step 17: Run them and see them fail**

Run: `docker compose run --rm tools pytest tests/workflows/test_schedules.py -q`

Expected: a collection error ending in:
```
E   ModuleNotFoundError: No module named 'mdcopilot_blog.workflows.schedules'
1 error in 0.06s
```

- [ ] **Step 18: Implement `backend/src/mdcopilot_blog/workflows/schedules.py`**

```python
"""Daily generation schedule (ARCHITECTURE §5.4).

A DBOS cron schedule fires `daily_trigger`, which creates at most one daily run per local date and enqueues the
target pipeline on the `pipeline` queue under the workflow id `daily-<YYYY-MM-DD>`. The queue runs one pipeline
at a time, so a daily run never overlaps a manual run. While BLOG_AGENT_SCHEDULER_ENABLED=false the schedule
exists but is PAUSED.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import date, datetime, time
from typing import Any, cast
from zoneinfo import ZoneInfo

from dbos import DBOS, ScheduleInput, SetWorkflowID
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import RunKind, RunStatus
from mdcopilot_blog.ids import new_trace_id, uuid7
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.hello import hello_pipeline
from mdcopilot_blog.workflows.names import (
    DAILY_TARGET_WORKFLOW,
    QUEUE_PIPELINE,
    SCHEDULE_DAILY,
    STEP_DAILY_CREATE_RUN,
    WORKFLOW_DAILY_TRIGGER,
    WORKFLOW_HELLO,
)
from mdcopilot_blog.workflows.runtime import get_runtime

logger = logging.getLogger(__name__)

# Workflows the daily trigger may start, by registered name. Phase 3 adds discover_topics here.
DAILY_TARGETS: dict[str, Callable[[str], Coroutine[Any, Any, dict[str, object]]]] = {WORKFLOW_HELLO: hello_pipeline}
MANUAL_RUN_FINAL_STATUSES = (RunStatus.FAILED.value, RunStatus.CANCELLED.value)


def daily_child_workflow_id(local_date: date) -> str:
    return f"daily-{local_date.isoformat()}"


def _slot_time(settings: Settings) -> time:
    hour, minute = settings.daily_run_time.split(":")
    return time(hour=int(hour), minute=int(minute))


def daily_cron(settings: Settings) -> str:
    slot = _slot_time(settings)
    return f"{slot.minute} {slot.hour} * * *"


async def _daily_run(session: AsyncSession, run_date: date) -> tuple[uuid.UUID, str] | None:
    row = (
        await session.execute(
            select(BlogRun.id, BlogRun.status).where(BlogRun.kind == RunKind.DAILY.value, BlogRun.run_date == run_date)
        )
    ).first()
    return None if row is None else (row[0], row[1])


@DBOS.step(name=STEP_DAILY_CREATE_RUN)
async def create_daily_run_step(run_date_iso: str) -> str | None:
    """Return the id of the daily run to start for `run_date_iso`, inserting the run if the date has none.

    A daily run that is still QUEUED is returned again. DBOS re-executes this step when the worker dies after
    the insert committed but before the step's output was recorded, and that run still needs its workflow
    (enqueueing `daily-<date>` a second time returns the existing workflow). Returns None when the date's daily
    run has left QUEUED, or when the date has no daily run and a manual run for it is active.
    """
    rt = get_runtime()
    run_date = date.fromisoformat(run_date_iso)
    async with rt.sessionmaker() as session:
        existing = await _daily_run(session, run_date)
        if existing is None:
            active_manual = await session.scalar(
                select(func.count())
                .select_from(BlogRun)
                .where(
                    BlogRun.kind == RunKind.MANUAL.value,
                    BlogRun.run_date == run_date,
                    BlogRun.status.not_in(MANUAL_RUN_FINAL_STATUSES),
                )
            )
            if active_manual:
                logger.info("daily run skipped: a manual run for this date is active", extra={"run_date": run_date_iso})
                return None
            stmt = (
                insert(BlogRun)
                .values(
                    id=uuid7(),
                    kind=RunKind.DAILY.value,
                    run_date=run_date,
                    status=RunStatus.QUEUED.value,
                    params={"source": "schedule"},
                    trace_id=new_trace_id(),
                )
                .on_conflict_do_nothing(index_elements=["run_date"], index_where=text("kind = 'daily'"))
                .returning(BlogRun.id)
            )
            inserted = await session.scalar(stmt)
            await session.commit()
            if inserted is not None:
                return str(inserted)
            existing = await _daily_run(session, run_date)  # another trigger inserted it first
    if existing is not None and existing[1] == RunStatus.QUEUED.value:
        logger.info("daily run is still queued; starting its workflow", extra={"run_date": run_date_iso})
        return str(existing[0])
    logger.info("daily run skipped: this date already has a daily run", extra={"run_date": run_date_iso})
    return None


@DBOS.workflow(name=WORKFLOW_DAILY_TRIGGER)
async def daily_trigger(scheduled_at: datetime, context: Any) -> str | None:
    local_date = scheduled_at.astimezone(ZoneInfo(get_runtime().settings.timezone)).date()
    run_id = await create_daily_run_step(local_date.isoformat())
    if run_id is None:
        return None
    # Enqueued, not started: the pipeline queue (worker_concurrency=1) runs it after any in-flight run.
    # The trigger does not wait for the child, so it frees its own slot on that queue straight away.
    with SetWorkflowID(daily_child_workflow_id(local_date)):
        handle = await DBOS.enqueue_workflow_async(QUEUE_PIPELINE, DAILY_TARGETS[DAILY_TARGET_WORKFLOW], run_id)
    logger.info("daily run enqueued", extra={"run_id": run_id, "context": context})
    return handle.get_workflow_id()


async def apply_daily_schedule(settings: Settings) -> None:
    """Create or replace the daily schedule, then pause or resume it to match BLOG_AGENT_SCHEDULER_ENABLED.

    DBOS keeps a schedule's status on replace, so the status is always set explicitly. dbos 3.0.0 has no
    pause_schedule_async/resume_schedule_async (checked with dir(DBOS)); the sync calls run off the event loop.
    """
    # ScheduleInput types workflow_fn as returning None; DBOS ignores the child id our trigger returns.
    trigger = cast("Callable[[datetime, Any], Coroutine[Any, Any, None]]", daily_trigger)
    schedule: ScheduleInput = {
        "schedule_name": SCHEDULE_DAILY,
        "workflow_fn": trigger,
        "schedule": daily_cron(settings),
        "context": {"source": "schedule"},
        "automatic_backfill": False,
        "cron_timezone": settings.timezone,
        "queue_name": QUEUE_PIPELINE,
    }
    await DBOS.apply_schedules_async([schedule])
    if settings.scheduler_enabled:
        await asyncio.to_thread(DBOS.resume_schedule, SCHEDULE_DAILY)
    else:
        await asyncio.to_thread(DBOS.pause_schedule, SCHEDULE_DAILY)
    logger.info(
        "daily schedule applied",
        extra={"cron": daily_cron(settings), "timezone": settings.timezone, "enabled": settings.scheduler_enabled},
    )


async def catch_up_today(settings: Settings, now: datetime) -> str | None:
    """Start today's daily trigger if the slot already passed and nothing ran for today (same day only)."""
    if not settings.scheduler_enabled:
        return None
    tz = ZoneInfo(settings.timezone)
    local_now = now.astimezone(tz)
    slot = datetime.combine(local_now.date(), _slot_time(settings), tzinfo=tz)
    if local_now < slot:
        return None
    existing = await DBOS.list_workflows_async(
        workflow_ids=[daily_child_workflow_id(slot.date())], load_input=False, load_output=False
    )
    if existing:
        return None
    with SetWorkflowID(f"catchup-{slot.date().isoformat()}"):
        handle = await DBOS.start_workflow_async(daily_trigger, slot, {"source": "catch_up"})
    logger.info("daily catch-up started", extra={"workflow_id": handle.get_workflow_id()})
    return handle.get_workflow_id()
```

- [ ] **Step 19: Run the schedule tests and see them pass**

Run: `docker compose run --rm tools pytest tests/workflows/test_schedules.py -q`

Expected: `13 passed`

- [ ] **Step 20: Write the failing worker test**

Create `backend/tests/workflows/test_worker.py`:
```python
"""Worker process helpers."""

import asyncio
from pathlib import Path

from mdcopilot_blog.worker import heartbeat_loop


async def test_heartbeat_loop_touches_file_until_stopped(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat"
    stop = asyncio.Event()
    task = asyncio.create_task(heartbeat_loop(stop, path=path, interval=0.05))
    await asyncio.sleep(0.02)
    assert path.exists()
    first = path.stat().st_mtime_ns
    await asyncio.sleep(0.15)
    assert path.stat().st_mtime_ns > first
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert task.done()
```

- [ ] **Step 21: Run it and see it fail**

Run: `docker compose run --rm tools pytest tests/workflows/test_worker.py -q`

Expected: a collection error ending in:
```
E   ModuleNotFoundError: No module named 'mdcopilot_blog.worker'
1 error in 0.05s
```

- [ ] **Step 22: Implement `backend/src/mdcopilot_blog/worker.py`**

```python
"""Worker process: the only process that launches DBOS and executes workflows.

Run with `python -m mdcopilot_blog.worker` (compose service `worker`).
"""

import asyncio
import contextlib
import logging
import os
import signal
from datetime import UTC, datetime
from pathlib import Path

from dbos import DBOS

from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.settings import Settings, get_settings
from mdcopilot_blog.workflows.dbos_config import build_dbos_config
from mdcopilot_blog.workflows.names import HEARTBEAT_FILE, QUEUE_INTERACTIVE, QUEUE_PIPELINE
from mdcopilot_blog.workflows.runtime import build_runtime, set_runtime

# Importing schedules also imports hello: both modules register their workflows and steps with DBOS
# at import time, which must happen before DBOS.launch().
from mdcopilot_blog.workflows.schedules import apply_daily_schedule, catch_up_today

logger = logging.getLogger("mdcopilot_blog.worker")

HEARTBEAT_INTERVAL_SECONDS = 10.0
# compose stop_grace_period (40 s) must stay above this
WORKFLOW_COMPLETION_TIMEOUT_SECONDS = 25
PIPELINE_CONCURRENCY = 1
INTERACTIVE_CONCURRENCY = 4


async def heartbeat_loop(
    stop: asyncio.Event, path: Path = HEARTBEAT_FILE, interval: float = HEARTBEAT_INTERVAL_SECONDS
) -> None:
    """Touch `path` every `interval` seconds until `stop` is set. A stale file means the event loop is stuck."""
    while not stop.is_set():
        path.touch()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)


def install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)


async def _run_dbos(settings: Settings, stop: asyncio.Event) -> None:
    rt = await build_runtime(settings)
    launched = False
    try:
        async with rt.sessionmaker() as session:
            inserted = await rt.prompts.sync_to_db(session)  # fails fast on a changed prompt without a version bump
            await session.commit()
        logger.info("prompts synced", extra={"inserted": inserted})
        set_runtime(rt)

        DBOS(config=build_dbos_config(settings))
        DBOS.launch()  # sync; dequeued async workflows then run on this event loop
        launched = True
        logger.info(
            "DBOS launched",
            extra={"executor_id": settings.worker_executor_id, "application_version": settings.app_version},
        )
        # dbos 3.0: queues can only be registered after launch
        await DBOS.register_queue_async(QUEUE_PIPELINE, worker_concurrency=PIPELINE_CONCURRENCY)
        await DBOS.register_queue_async(QUEUE_INTERACTIVE, worker_concurrency=INTERACTIVE_CONCURRENCY)
        await apply_daily_schedule(settings)
        caught_up = await catch_up_today(settings, datetime.now(UTC))
        if caught_up is not None:
            logger.info("started today's missed daily run", extra={"workflow_id": caught_up})

        heartbeat = asyncio.create_task(heartbeat_loop(stop))
        logger.info("worker ready")
        await stop.wait()
        logger.info("shutdown requested; waiting for running workflows")
        await heartbeat
    finally:
        if launched:
            # DBOS.destroy is synchronous and polls with time.sleep; running it on this loop would freeze the
            # async workflows it is waiting for, so it runs in a thread.
            await asyncio.to_thread(DBOS.destroy, workflow_completion_timeout_sec=WORKFLOW_COMPLETION_TIMEOUT_SECONDS)
            logger.info("DBOS destroyed")
        set_runtime(None)
        await rt.engine.dispose()


async def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)
    stop = asyncio.Event()
    install_signal_handlers(stop)
    if not settings.agent_enabled:
        logger.warning("agent disabled (BLOG_AGENT_ENABLED=false); worker is idle and DBOS is not launched")
        await heartbeat_loop(stop)
        return
    await _run_dbos(settings, stop)
    logger.info("worker stopped")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
```

- [ ] **Step 23: Run the worker test, the workflow suite and the whole suite**

Run: `docker compose run --rm tools pytest tests/workflows/test_worker.py -q`

Expected: `1 passed`

Run: `docker compose run --rm tools pytest tests/workflows -q`

Expected: `35 passed` (2 + 10 + 9 + 13 + 1).

Run: `docker compose run --rm tools pytest -q`

Expected: `1087 passed`, with no errors or warnings summary. That is every test from Tasks 1–11: Task 9's 994 plus Task 10's 58 plus this task's 35. (The tree assembled while checking this plan gave `1086`; it predates Task 3's 13th logging test.) `dbos_runtime` starts only for `tests/workflows/*`, and other test modules never launch DBOS.

If the total differs but nothing fails, compare each earlier task's test files with its **Files** list before continuing.

- [ ] **Step 24: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, exactly (counts at the end of Task 11; the tree assembled from Tasks 1–11 while checking this plan gave `105`, because it did not yet have Task 5's `tests/db/__init__.py`, which this plan creates):
```
All checks passed!
106 files already formatted
Success: no issues found in 60 source files
```
- **`106 files`:** the 105 `.py` files under `backend/`, plus `backend/prompts/hello/echo.v1.md`, which ruff 0.16.8 also checks. Task 10 ended at 94; this task adds 12 `.py` files (6 under `src/`, `tests/workflows/__init__.py` and 5 test files).
- **`60 source files`:** the `.py` files under `backend/src/`.

A different count with no errors means a file from an earlier task is missing or extra. List the files with `docker compose run --rm tools sh -c "find . -name '*.py' -not -path '*/__pycache__/*' | sort"` and compare them with the **Files** lists of Tasks 1–11.

Fixes:
- **`ruff check` reports I001 or F811 in `tests/conftest.py`** (from the import merge in Step 6). Run `docker compose run --rm tools ruff check --fix tests/conftest.py`, expect `Found <n> errors (<n> fixed, 0 remaining).`, then re-run the command above.
- **`ruff format --check` lists a Task 11 file.** Run `docker compose run --rm tools ruff format <file>`, then re-run the command above.

- [ ] **Step 25: Manual check: run the worker briefly**

This prepares the dev database, then runs the worker for 20 s and stops it with SIGINT through `timeout`. Task 14 repeats this check with the compose `worker` service.

Run: `docker compose run --rm tools python -m mdcopilot_blog.cli migrate`

Expected: exit code 0.

Run: `docker compose run --rm tools timeout -s INT 20 python -m mdcopilot_blog.worker 2>&1 | grep -E 'DBOS launched|worker ready|DBOS destroyed|worker stopped'`

Expected lines, in this order:
1. DBOS's own `... DBOS launched!` line;
2. JSON log lines whose `message` is `DBOS launched`, `worker ready`, `DBOS destroyed` and `worker stopped`.

Run: `docker compose run --rm -e BLOG_AGENT_ENABLED=false tools sh -c 'timeout -s TERM 5 python -m mdcopilot_blog.worker; test -f /tmp/worker-heartbeat && echo heartbeat-ok'`

Expected:
- a JSON warning line: `agent disabled (BLOG_AGENT_ENABLED=false); worker is idle and DBOS is not launched`;
- then `heartbeat-ok`.

Also confirm that no secret appears in the output: `docker compose run --rm tools timeout -s INT 10 python -m mdcopilot_blog.worker 2>&1 | grep -cE 'sk-|AIza'` prints `0`.

- [ ] **Step 26: Manual check: crash mid-step, recover, stop gracefully**

This is the Phase 1 "kill the worker during hello_pipeline" acceptance, run against one-off `tools` containers. Task 14 repeats it with the compose `worker` service.

The worker below uses the default `WORKER_EXECUTOR_ID` (`worker-1`) and the `.env` `APP_VERSION` on both starts. Both must match for DBOS to recover the workflow.

Run this in one bash or zsh session from `mdcopilot-blog/` (verified in both shells):
```bash
# helper: run one SQL statement in the db container (credentials come from the container env, never printed)
sql() { docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"$1\""; }
# start a worker whose mock steps each take 4 s
docker compose run -d --name mdcopilot-blog-t11-worker -e BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=4 tools python -m mdcopilot_blog.worker
sleep 5
# create a manual run and enqueue it the way the runs API will (Task 12)
WF=$(docker compose run --rm -T tools python - <<'EOF'
import asyncio
from datetime import date

from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.settings import get_settings
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_HELLO


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url())
    run = BlogRun(kind="manual", run_date=date.today(), status="QUEUED", params={}, trace_id=new_trace_id())
    async with make_sessionmaker(engine)() as db:
        db.add(run)
        await db.commit()
    client = WorkflowClient.from_settings(settings)
    workflow_id = await client.enqueue(
        workflow_name=WORKFLOW_HELLO,
        queue_name=QUEUE_PIPELINE,
        workflow_id=f"manual-{run.id}",
        args=(str(run.id),),
        timeout_seconds=600,
    )
    print(workflow_id)
    await asyncio.to_thread(client.close)
    await engine.dispose()


asyncio.run(main())
EOF
)
WF=$(printf '%s\n' "$WF" | tail -n 1)
RUN_ID=${WF#manual-}
echo "enqueued $WF"
# wait (at most 60 s) until hello.finish has committed SUCCEEDED (its 4 s delay is still running), then kill the worker
for _ in $(seq 1 120); do [ "$(sql "select status from app.blog_runs where id = '$RUN_ID'")" = SUCCEEDED ] && break; sleep 0.5; done
[ "$(sql "select status from app.blog_runs where id = '$RUN_ID'")" = SUCCEEDED ] || { echo 'run did not reach SUCCEEDED within 60 s'; docker logs mdcopilot-blog-t11-worker 2>&1 | tail -n 40; }
docker kill mdcopilot-blog-t11-worker
sql "select dbos_step_id, step_name, status, tries from app.blog_agent_runs where run_id = '$RUN_ID' order by dbos_step_id"
# restart with the same executor id and app version: DBOS recovers the workflow
docker rm mdcopilot-blog-t11-worker
docker compose run -d --name mdcopilot-blog-t11-worker -e BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=4 tools python -m mdcopilot_blog.worker
sleep 15
docker logs mdcopilot-blog-t11-worker 2>&1 | grep Recovering
sql "select dbos_step_id, step_name, status, tries from app.blog_agent_runs where run_id = '$RUN_ID' order by dbos_step_id"
sql "select status, recovery_attempts from dbos.workflow_status where workflow_uuid = '$WF'"
sql "select count(*) from app.blog_llm_calls where run_id = '$RUN_ID'"
# graceful stop, then remove the one-off container
docker stop -t 40 mdcopilot-blog-t11-worker
docker logs mdcopilot-blog-t11-worker 2>&1 | grep -E 'DBOS destroyed|worker stopped'
# JSON log lines of this run that carry both run_id and trace_id
docker logs mdcopilot-blog-t11-worker 2>&1 | grep -F "\"run_id\": \"$RUN_ID\"" | grep -c '"trace_id"'
docker rm mdcopilot-blog-t11-worker
```

Expected, in order:
1. **Enqueue.** A container id, then `enqueued manual-<uuid>`.
2. **After `docker kill`.** The kill prints `mdcopilot-blog-t11-worker`, and the step rows show `hello.finish` still RUNNING:
   ```
   1|hello.open_attempt|SUCCEEDED|1
   2|hello.echo|SUCCEEDED|1
   3|hello.finish|RUNNING|1
   ```
3. **After the restart.** `docker rm` prints the container name and `docker compose run -d` prints a new container id. The worker logs `... Recovering 1 workflows from application version <APP_VERSION>`, and the step rows are:
   ```
   1|hello.open_attempt|SUCCEEDED|1
   2|hello.echo|SUCCEEDED|1
   3|hello.finish|SUCCEEDED|2
   ```
   Only the interrupted step ran again. Its guard skipped the second status change, and each step still has one row.
4. **DBOS status.** `SUCCESS|2`.
5. **LLM calls.** `1`: echo was not re-run.
6. **After `docker stop`:**
   - the JSON lines `DBOS destroyed` and `worker stopped`;
   - then `1`: the restarted worker's `"step finished"` line for `hello.finish`, carrying the run's `run_id` and `trace_id`;
   - then the container name from `docker rm`.

Diagnostics:
- **`run did not reach SUCCEEDED within 60 s`.** The script prints the worker's last 40 log lines and carries on; the later checks then fail. Common causes:
  - the run FAILED (look for a traceback);
  - it is still QUEUED because the worker is not running or cannot dequeue. Check `docker ps -a` and `APP_VERSION`: the enqueue and the worker must use the same version.
- **The restarted worker logs `InvalidTransition`.** The idempotency guard in `finish_step` is missing. Compare with Step 14.

- [ ] **Step 27: Checkpoint: list files changed (no git)**

Record the files below, plus the pytest-fixture variant chosen in Step 7 (`in-loop launch` or `executor-thread launch`).
- Created:
  - `backend/src/mdcopilot_blog/workflows/dbos_config.py`
  - `backend/src/mdcopilot_blog/workflows/runtime.py`
  - `backend/src/mdcopilot_blog/workflows/tracking.py`
  - `backend/src/mdcopilot_blog/workflows/hello.py`
  - `backend/src/mdcopilot_blog/workflows/schedules.py`
  - `backend/src/mdcopilot_blog/worker.py`
  - `backend/tests/workflows/__init__.py` (if it was new)
  - `backend/tests/workflows/test_dbos_runtime.py`
  - `backend/tests/workflows/test_tracking.py`
  - `backend/tests/workflows/test_hello_pipeline.py`
  - `backend/tests/workflows/test_schedules.py`
  - `backend/tests/workflows/test_worker.py`
- Modified:
  - `backend/tests/conftest.py` (T11 imports and the `# --- T11: DBOS fixtures ---` block)

---

### Task 12: Runs service and runs API

This task adds the user-visible run endpoints the dashboard needs: create a manual run, list runs, read one run with its attempts and steps, and cancel a run. The API never executes workflows. It writes the `blog_runs` row, commits, and only then enqueues `hello_pipeline` through the workflow client, so the worker always finds the row it is given. One integration test drives the real `WorkflowClient` against in-process DBOS (Task 11's `dbos_runtime`) and waits for the run to reach `SUCCEEDED`.

**Verification note.** The code below ran on 2026-09-17 in throwaway containers with `pgvector/pgvector:pg16` and `dbos==3.0.0`.
- **What it ran against.** The code blocks of Tasks 1–7, 9, 10 and 11, copied verbatim from their plan parts. These are the whole `src/` tree Task 12 touches directly or indirectly: `pyproject.toml`, settings, errors, logs, domain, DB layer and migration, prompts, auth, audit, API, workflow client, gateway, `hello_pipeline`, tracking, schedules, worker, and all three conftest blocks.
- **Results.**
  - The three Task 12 test files gave `43 passed`.
  - Together with Task 9's API tests and Task 11's workflow tests, the run gave `147 passed`.
  - `ruff check`, `ruff format --check` and `mypy src` (strict) were clean.
  - **Red phase, re-checked.** On a full Task 1–12 tree (Task 8 included), with the runs service, router and `app.py` registration removed, Step 6's command gave `33 failed`. The integration test failed with a 404 at `created.status_code == 202`. With the code restored, the three Task 12 files gave `43 passed`, and Step 16 printed `110 files already formatted` and `62 source files`. That tree did not have Task 5's `tests/db/__init__.py`; with it, as this plan builds the tree, the count is `111`.
- **DBOS under pytest.** `DBOS.launch()` ran on the pytest session loop (Task 11's in-loop variant).

**Files:**
- Create: `backend/src/mdcopilot_blog/services/runs.py`
- Create: `backend/src/mdcopilot_blog/api/routers/runs.py`
- Modify: `backend/src/mdcopilot_blog/api/app.py` (a two-line edit: one import line and one `ROUTERS` entry)
- Test: `backend/tests/db/test_runs_service.py`
- Test: `backend/tests/api/test_runs_api.py`
- Test: `backend/tests/workflows/test_runs_api_dbos.py`. This is the integration test. It lives in `tests/workflows/` because the contract reserves `dbos_runtime` for that directory.

**Interfaces:**
- **Consumes, Task 1:**
  - `mdcopilot_blog.ids.new_trace_id() -> str`;
  - the `tools` compose service and the pytest config (`asyncio_mode=auto`, session loop scope).
- **Consumes, Task 2:** `mdcopilot_blog.settings.Settings`. Fields used: `agent_enabled`, `timezone`, `production_timeout_minutes`, `app_version`.
- **Consumes, Task 3:** `mdcopilot_blog.errors.ProblemError(status, title, detail=None)`. The installed handlers render it as `application/problem+json`.
- **Consumes, Task 4:**
  - `mdcopilot_blog.domain.enums`: `AttemptStatus`, `Permission`, `Role`, `RunKind`, `RunStatus`, `StepStatus`. Members are UPPERCASE: `Role.EDITOR`, `Role.VIEWER`, `RunKind.MANUAL`, `RunKind.DAILY`.
  - `mdcopilot_blog.domain.contracts.PillarKey`;
  - `mdcopilot_blog.domain.rbac.permissions_for`;
  - `mdcopilot_blog.domain.state_machine`: `Entity`, `InvalidTransition` (attribute `.current`), `require_transition`. A same-state move is allowed as a no-op.
- **Consumes, Task 5:**
  - `mdcopilot_blog.db.models`: `BlogRun`, `RunAttempt`, `AgentRun`, `AuditLog`;
  - conftest fixtures:
    - `settings`, which does not depend on `database_url`;
    - `database_url`, which recreates and migrates the test DB and runs the DBOS system-table migrations (in-process, the same code `dbos migrate` runs);
    - `db_session`;
    - `clean_db`, which truncates before and after the test;
    - `sessionmaker_committing`, which requests `clean_db` itself.
- **Consumes, Task 7:**
  - `mdcopilot_blog.services.audit.audit(db, *, actor_user_id, action, entity_type, entity_id=None, reason=None, details=None)`, which flushes only;
  - `mdcopilot_blog.auth.users.create_user(db, *, email, display_name, role, password)`;
  - the package `mdcopilot_blog/services/__init__.py`.
- **Consumes, Task 9:**
  - `mdcopilot_blog.api.deps`:
    - `Principal`, `require_permission`;
    - the aliases `SessionDep`, `SettingsDep`, `WorkflowClientDep`;
    - the app-level `enforce_csrf`.
  - `mdcopilot_blog.api.schemas`: `ManualRunRequest`, `RunOut`, `AttemptOut`, `StepOut`, `RunDetail(RunOut)`, `Page[T]`.
    - `ApiModel` is camelCase with `from_attributes=True`.
    - `Decimal` values serialise as JSON strings.
  - `mdcopilot_blog.api.app`: `create_app`, which sets `app.state.settings`, and `ROUTERS: tuple[tuple[APIRouter, str], ...]`.
  - `mdcopilot_blog.workflows.client`:
    - `WorkflowClientProtocol` and `EnqueueCall(workflow_name, queue_name, workflow_id, args, timeout_seconds)`;
    - the dataclass `FakeWorkflowClient`, whose attributes include `enqueued: list[EnqueueCall]` and `cancelled: list[str]`;
    - `FakeWorkflowClient.enqueue_error`: when set, `enqueue` raises it **before** recording the call.
  - `mdcopilot_blog.workflows.names`: `WORKFLOW_HELLO`, `QUEUE_PIPELINE`, and the `STEP_HELLO_*` names.
  - conftest fixtures:
    - `fake_workflow_client`;
    - `app`, which also sets `app.state.settings`, `sessionmaker` and `workflow_client`;
    - `client`;
    - `login_as(role) -> (AsyncClient, csrf)`.
  - `tests/api/test_rbac_routes.py`. Its deny-by-default tests walk `ROUTERS`, so every runs route must depend on `require_permission`.
  - `mdcopilot_blog/api/__init__.py` must stay import-free, because `services/runs.py` imports `api.deps` and `api.schemas`.
- **Consumes, Task 11:**
  - the session-scoped conftest fixture `dbos_runtime`. It:
    - requests `database_url`;
    - launches DBOS with `application_version="pytest"` (`DBOS_TEST_APP_VERSION`);
    - pins `mock_step_delay_seconds=0.0`;
    - registers the `pipeline` queue.

    It does **not** import workflow modules. Test modules must import them, so they are registered before launch.
  - `mdcopilot_blog.workflows.hello`, whose `hello_pipeline` runs three tracked steps (`hello.open_attempt`, `hello.echo`, `hello.finish`). Together they write:
    - `blog_run_attempts` and `blog_agent_runs` rows;
    - `stage="hello.finish"` on success;
    - the echo step's `model="mock:hello"`, prompt `hello/echo` v1, and 20/8 tokens (Task 10's fixture).
  - the directory `backend/tests/workflows/`.
- **Produces, `mdcopilot_blog.services.runs`:**
  - `async def create_manual_run(db: AsyncSession, client: WorkflowClientProtocol, *, principal: Principal, request: ManualRunRequest, settings: Settings, today: date) -> BlogRun`
    1. Raises `ProblemError(409, "Agent disabled")` when `not settings.agent_enabled`, before writing anything.
    2. Inserts `BlogRun(kind="manual", run_date=request.run_date or today, status="QUEUED", params=request.model_dump(mode="json", exclude_none=True), trace_id=new_trace_id(), created_by=principal.user_id)`.
       - `params` keys are camelCase, because `ApiModel` serialises by alias, e.g. `{"runDate": "2026-09-20", "wordCount": 900}`.
    3. Audits `run.create`:
       - `entity_type="blog_run"`, `entity_id=str(run.id)`;
       - `details={"kind", "run_date", "workflow_id"}`.
    4. Commits.
    5. Calls `client.enqueue(workflow_name="hello_pipeline", queue_name="pipeline", workflow_id=f"manual-{run.id}", args=(str(run.id),), timeout_seconds=settings.production_timeout_minutes * 60)`.
    6. If `enqueue` raises:
       - sets the run `FAILED`, sets `finished_at`, and sets `error={"stage": "enqueue", "message": "<ExcClass>: <msg>"}` (at most 500 chars);
       - commits;
       - raises `ProblemError(503, "Workflow service unavailable")`.
  - `async def list_runs(db, *, status: RunStatus | None, limit: int, offset: int) -> tuple[list[BlogRun], int]`
    - Orders by `created_at DESC, id DESC`. The id is a UUIDv7, so it breaks ties in insertion order.
    - The count respects the status filter.
  - `async def get_run_detail(db, run_id: uuid.UUID) -> tuple[BlogRun, list[RunAttempt], list[AgentRun]] | None`
    - Attempts are ordered by `attempt_no`.
    - Steps are ordered by `created_at, dbos_step_id`.
  - `async def cancel_run(db, client, *, run: BlogRun, principal: Principal) -> BlogRun`
    1. **Already `CANCELLED`:** returns the run unchanged. No client call, no audit.
    2. **Otherwise:** `require_transition(RUN, status, CANCELLED)`, which raises `InvalidTransition` for `SUCCEEDED`/`FAILED`.
    3. **Workflows to cancel:** every attempt whose status is `ENQUEUED`/`RUNNING`, in `attempt_no` order.
       - If the run is `QUEUED` and has no attempt row for its first workflow, that workflow is added first: `manual-<run id>`, or `daily-<run date>` for a daily run. The worker writes the attempt row only when the workflow starts.
    4. **Cancel:** calls `client.cancel(id)` for each. Any client error becomes `ProblemError(503, "Workflow service unavailable")`, and nothing is changed.
    5. **Record:**
       - marks those attempts `CANCELLED` with `finished_at`;
       - sets the run to `CANCELLED` with `finished_at`;
       - audits `run.cancel` with `details={"from_status", "workflow_ids"}`;
       - commits.
  - Helpers:
    - `manual_workflow_id(run_id) -> str` and `initial_workflow_id(run) -> str`;
    - constants `RUN_ENTITY = "blog_run"`, `ACTIVE_ATTEMPT_STATUSES`, `ERROR_MESSAGE_LIMIT = 500`.
- **Produces, `mdcopilot_blog.api.routers.runs`:**
  - `router: APIRouter`, mounted through `ROUTERS` with prefix `/api/blog-agent`;
  - `DEFAULT_PAGE_SIZE = 20`, `MAX_PAGE_SIZE = 100`;
  - `to_run_out(run) -> RunOut`, which is `RunOut.model_validate(run)`;
  - `run_not_found(run_id) -> ProblemError`;
  - the aliases `CanView` and `CanGenerate`.
- **Produces, routes.** Problem titles are exact. The frontend (Task 13) and acceptance (Task 14) rely on them.

  | Route | Permission | Success | Errors |
  |---|---|---|---|
  | `POST /api/blog-agent/runs` | `blog.generate` | 202 `RunOut` | 401 (no session) · 403 "Forbidden" (detail `missing permission blog.generate`) · 403 "CSRF token missing or invalid" · 409 "Agent disabled" · 422 · 503 "Workflow service unavailable" |
  | `GET /api/blog-agent/runs?status=&limit=20&offset=0` | `blog.view` | 200 `Page[RunOut]`, newest first | 422 (bad status, `limit < 1`, `offset < 0`) |
  | `GET /api/blog-agent/runs/{run_id}` | `blog.view` | 200 `RunDetail` | 404 "Run not found" · 422 (malformed id) |
  | `POST /api/blog-agent/runs/{run_id}/cancel` | `blog.generate` | 202 `RunOut` | 404 "Run not found" · 409 "Run cannot be cancelled" · 503 "Workflow service unavailable" |

  - **POST body.** Optional: a missing body or `{}` means "today, no hints".
  - **`limit`.** Values above 100 are capped at 100, and the page echoes the capped `limit`.
  - **Cancel status.** Cancelling an already-cancelled run returns 202 and changes nothing.
  - **`RunOut` JSON keys:** `id, kind, runDate, status, stage, traceId, costUsd, createdAt, startedAt, finishedAt`.
  - **`RunDetail` JSON keys:** the `RunOut` keys plus `params`, `attempts` and `steps`.
    - Attempt keys: `id, dbosWorkflowId, workflowName, attemptNo, status, startedAt, finishedAt, forkedFromWorkflowId`.
    - Step keys: `id, stepName, dbosStepId, status, tries, agentName, model, promptName, promptVersion, inputTokens, outputTokens, costUsd, durationMs, error`.

- [ ] **Step 1: Check that Tasks 5, 7, 9 and 11 are in place**

Run from `mdcopilot-blog/`:
```bash
ls backend/src/mdcopilot_blog/services/__init__.py backend/src/mdcopilot_blog/services/audit.py \
   backend/src/mdcopilot_blog/api/deps.py backend/src/mdcopilot_blog/api/schemas.py \
   backend/src/mdcopilot_blog/workflows/client.py backend/src/mdcopilot_blog/workflows/hello.py \
   backend/tests/api backend/tests/db backend/tests/workflows
grep -nF -e 'from mdcopilot_blog.api.routers import health as health_routes' -e '(settings_routes.router, "/api/blog-agent"),' backend/src/mdcopilot_blog/api/app.py
grep -nE "def (settings|database_url|db_session|clean_db|sessionmaker_committing|fake_workflow_client|app|client|login_as|dbos_runtime)\(" backend/tests/conftest.py
grep -nE "^class (EnqueueCall|FakeWorkflowClient)|enqueue_error" backend/src/mdcopilot_blog/workflows/client.py
ls backend/src/mdcopilot_blog/services/runs.py backend/src/mdcopilot_blog/api/routers/runs.py
```

Expected:
- The first `ls` lists every path without an error.
- The `app.py` grep prints exactly 2 lines. They are the Step 10 anchors.
- The conftest grep prints 10 fixture definitions.
- The `client.py` grep shows both classes and the `enqueue_error` field.
- The last `ls` fails with `No such file or directory` for both files. This task creates them.

Decision rule: if anything above is missing, stop and finish the task that owns it (see the contract's ownership table).

- [ ] **Step 2: Write the failing service test `backend/tests/db/test_runs_service.py`**

```python
"""Run service against the test database, with a recording fake workflow client."""

import re
import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas import ManualRunRequest
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.models import AuditLog, BlogRun, RunAttempt
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import AttemptStatus, Role, RunKind, RunStatus
from mdcopilot_blog.domain.rbac import permissions_for
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.services.runs import cancel_run, create_manual_run, get_run_detail, list_runs
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import FakeWorkflowClient

TODAY = date(2026, 9, 17)


class CancelFailingClient(FakeWorkflowClient):
    """The shared fake, except that every cancel fails."""

    async def cancel(self, workflow_id: str) -> None:
        self.cancelled.append(workflow_id)
        raise ConnectionError("dbos system database unreachable")


@pytest.fixture
def workflows() -> FakeWorkflowClient:
    return FakeWorkflowClient()


@pytest.fixture
def enabled_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"agent_enabled": True})


@pytest_asyncio.fixture
async def editor(db_session: AsyncSession) -> Principal:
    user = await create_user(
        db_session,
        email="runs-service-editor@example.test",
        display_name="Runs Service Editor",
        role=Role.EDITOR,
        password="correct-horse-battery",
    )
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=Role.EDITOR,
        permissions=permissions_for(Role.EDITOR),
        session_token="not-used-by-the-service",
    )


def add_run(
    db: AsyncSession,
    *,
    status: RunStatus = RunStatus.QUEUED,
    kind: RunKind = RunKind.MANUAL,
    run_date: date = TODAY,
) -> BlogRun:
    run = BlogRun(kind=kind.value, run_date=run_date, status=status.value, params={}, trace_id=new_trace_id())
    db.add(run)
    return run


async def test_create_manual_run_defaults_to_today_and_audits(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal, enabled_settings: Settings
) -> None:
    run = await create_manual_run(
        db_session,
        workflows,
        principal=editor,
        request=ManualRunRequest(pillar=PillarKey.C),
        settings=enabled_settings,
        today=TODAY,
    )

    assert run.run_date == TODAY
    assert run.kind == "manual"
    assert run.status == "QUEUED"
    assert run.created_by == editor.user_id
    assert run.params == {"pillar": "C"}
    assert re.fullmatch(r"[0-9a-f]{32}", run.trace_id)
    assert [call.workflow_id for call in workflows.enqueued] == [f"manual-{run.id}"]
    audit = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "run.create"))).one()
    assert (audit.actor_user_id, audit.entity_type, audit.entity_id) == (editor.user_id, "blog_run", str(run.id))
    assert audit.details == {"kind": "manual", "run_date": "2026-09-17", "workflow_id": f"manual-{run.id}"}


async def test_create_manual_run_refuses_when_agent_disabled(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal, settings: Settings
) -> None:
    disabled = settings.model_copy(update={"agent_enabled": False})

    with pytest.raises(ProblemError) as caught:
        await create_manual_run(
            db_session, workflows, principal=editor, request=ManualRunRequest(), settings=disabled, today=TODAY
        )

    assert (caught.value.status, caught.value.title) == (409, "Agent disabled")
    assert workflows.enqueued == []
    assert await db_session.scalar(select(func.count()).select_from(BlogRun)) == 0


async def test_list_runs_returns_total_beyond_the_last_page(db_session: AsyncSession) -> None:
    for _ in range(3):
        add_run(db_session)
    add_run(db_session, status=RunStatus.CANCELLED)
    await db_session.flush()

    empty_page, total = await list_runs(db_session, status=None, limit=10, offset=10)
    queued, queued_total = await list_runs(db_session, status=RunStatus.QUEUED, limit=2, offset=0)

    assert (empty_page, total) == ([], 4)
    assert len(queued) == 2
    assert queued_total == 3
    assert {run.status for run in queued} == {"QUEUED"}


async def test_get_run_detail_is_none_for_unknown_run(db_session: AsyncSession) -> None:
    assert await get_run_detail(db_session, uuid.uuid4()) is None


async def test_get_run_detail_orders_attempts_by_number(db_session: AsyncSession) -> None:
    run = add_run(db_session, status=RunStatus.RESEARCHING)
    await db_session.flush()
    for number in (3, 1, 2):
        db_session.add(
            RunAttempt(
                run_id=run.id,
                dbos_workflow_id=f"wf-{number}-{run.id}",
                workflow_name="hello_pipeline",
                attempt_no=number,
                status=AttemptStatus.FAILED.value,
            )
        )
    await db_session.flush()

    found = await get_run_detail(db_session, run.id)

    assert found is not None
    loaded, attempts, steps = found
    assert loaded.id == run.id
    assert [attempt.attempt_no for attempt in attempts] == [1, 2, 3]
    assert steps == []


async def test_cancel_queued_daily_run_cancels_the_daily_workflow(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal
) -> None:
    run = add_run(db_session, kind=RunKind.DAILY, run_date=date(2026, 9, 18))
    await db_session.flush()

    cancelled = await cancel_run(db_session, workflows, run=run, principal=editor)

    assert workflows.cancelled == ["daily-2026-09-18"]
    assert cancelled.status == "CANCELLED"
    assert cancelled.finished_at is not None
    audit = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "run.cancel"))).one()
    assert audit.details == {"from_status": "QUEUED", "workflow_ids": ["daily-2026-09-18"]}


async def test_cancel_researching_run_cancels_its_running_attempt_once(
    db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal
) -> None:
    run = add_run(db_session, status=RunStatus.RESEARCHING)
    await db_session.flush()
    attempt = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"manual-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.RUNNING.value,
        started_at=datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
    )
    db_session.add(attempt)
    await db_session.flush()

    await cancel_run(db_session, workflows, run=run, principal=editor)

    assert workflows.cancelled == [f"manual-{run.id}"]
    assert attempt.status == "CANCELLED"
    assert run.status == "CANCELLED"


@pytest.mark.parametrize("status", [RunStatus.SUCCEEDED, RunStatus.FAILED])
async def test_cancel_terminal_run_raises_invalid_transition(
    status: RunStatus, db_session: AsyncSession, workflows: FakeWorkflowClient, editor: Principal
) -> None:
    run = add_run(db_session, status=status)
    await db_session.flush()

    with pytest.raises(InvalidTransition):
        await cancel_run(db_session, workflows, run=run, principal=editor)

    assert workflows.cancelled == []
    assert run.status == status.value


async def test_cancel_client_failure_is_503_and_changes_nothing(db_session: AsyncSession, editor: Principal) -> None:
    failing = CancelFailingClient()
    run = add_run(db_session, status=RunStatus.RESEARCHING)
    await db_session.flush()
    attempt = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"manual-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.RUNNING.value,
    )
    db_session.add(attempt)
    await db_session.flush()

    with pytest.raises(ProblemError) as caught:
        await cancel_run(db_session, failing, run=run, principal=editor)

    assert (caught.value.status, caught.value.title) == (503, "Workflow service unavailable")
    assert failing.cancelled == [f"manual-{run.id}"]
    assert (run.status, attempt.status) == ("RESEARCHING", "RUNNING")
    assert run.finished_at is None
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
```

- [ ] **Step 3: Run the service test and watch it fail**

Run: `docker compose run --rm tools pytest tests/db/test_runs_service.py -q`

Expected: collection fails with `E   ModuleNotFoundError: No module named 'mdcopilot_blog.services.runs'` and `1 error`.

- [ ] **Step 4: Write the failing API test `backend/tests/api/test_runs_api.py`**

How the fake is wired:
- **Calls.** The test reads Task 9's `FakeWorkflowClient` records directly: `enqueued` holds `EnqueueCall` values and `cancelled` holds workflow ids. The conftest `app` fixture injects the same instance.
- **Failure path.** The 503 case sets `enqueue_error`. The fake raises before recording, so `enqueued` stays empty.
- **The kill switch.** The autouse `_agent_enabled` fixture depends on `app`, so it runs after `app` has set `app.state.settings`. It then pins `agent_enabled=True`, whatever `.env` says. The disabled case sets it to `False` inside its own test.

```python
"""Runs API: create, list, detail and cancel, with the workflow client faked (no DBOS here)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import AgentRun, AuditLog, BlogRun, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, Role, RunKind, RunStatus, StepStatus
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import EnqueueCall, FakeWorkflowClient

RUNS = "/api/blog-agent/runs"
LoginAs = Callable[[Role], Awaitable[tuple[AsyncClient, str]]]

RUN_KEYS = {"id", "kind", "runDate", "status", "stage", "traceId", "costUsd", "createdAt", "startedAt", "finishedAt"}
DETAIL_KEYS = RUN_KEYS | {"params", "attempts", "steps"}
ATTEMPT_KEYS = {
    "id",
    "dbosWorkflowId",
    "workflowName",
    "attemptNo",
    "status",
    "startedAt",
    "finishedAt",
    "forkedFromWorkflowId",
}
STEP_KEYS = {
    "id",
    "stepName",
    "dbosStepId",
    "status",
    "tries",
    "agentName",
    "model",
    "promptName",
    "promptVersion",
    "inputTokens",
    "outputTokens",
    "costUsd",
    "durationMs",
    "error",
}


@pytest.fixture(autouse=True)
def _agent_enabled(app: FastAPI, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the kill switch on whatever .env says (the `app` fixture has already set app.state.settings)."""
    monkeypatch.setattr(app.state, "settings", settings.model_copy(update={"agent_enabled": True}))


def add_run(
    db: AsyncSession,
    *,
    status: RunStatus = RunStatus.QUEUED,
    kind: RunKind = RunKind.MANUAL,
    run_date: date = date(2026, 9, 17),
    created_at: datetime | None = None,
) -> BlogRun:
    run = BlogRun(kind=kind.value, run_date=run_date, status=status.value, params={}, trace_id=new_trace_id())
    if created_at is not None:
        run.created_at = created_at
    db.add(run)
    return run


async def audit_rows(db: AsyncSession, action: str, entity_id: uuid.UUID) -> list[AuditLog]:
    rows = await db.scalars(select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == str(entity_id)))
    return list(rows.all())


async def run_count(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(BlogRun)) or 0)


# --- POST /runs -------------------------------------------------------------------------------------------


async def test_editor_creates_manual_run_and_enqueues_hello_pipeline(
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
    settings: Settings,
) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body) == RUN_KEYS
    assert body["kind"] == "manual"
    assert body["status"] == "QUEUED"
    assert body["runDate"] == datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    assert len(body["traceId"]) == 32
    assert Decimal(str(body["costUsd"])) == 0
    assert body["startedAt"] is None
    assert body["finishedAt"] is None

    run_id = uuid.UUID(body["id"])
    run = await db_session.get(BlogRun, run_id)
    assert run is not None
    assert (run.kind, run.status, run.params) == ("manual", "QUEUED", {})
    assert run.created_by is not None

    # Literal names on purpose: the worker registers exactly these.
    assert fake_workflow_client.enqueued == [
        EnqueueCall(
            workflow_name="hello_pipeline",
            queue_name="pipeline",
            workflow_id=f"manual-{run_id}",
            args=(str(run_id),),
            timeout_seconds=settings.production_timeout_minutes * 60,
        )
    ]

    [created] = await audit_rows(db_session, "run.create", run_id)
    assert created.actor_user_id == run.created_by
    assert created.entity_type == "blog_run"
    assert created.details["workflow_id"] == f"manual-{run_id}"


async def test_create_run_records_request_params(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    payload = {
        "runDate": "2026-09-20",
        "pillar": "B",
        "topic": "Prior authorisation automation",
        "audience": "CMIOs",
        "wordCount": 900,
    }

    response = await http.post(RUNS, json=payload, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    assert response.json()["runDate"] == "2026-09-20"
    run = await db_session.get(BlogRun, uuid.UUID(response.json()["id"]))
    assert run is not None
    assert run.run_date == date(2026, 9, 20)
    assert run.params == payload
    assert len(fake_workflow_client.enqueued) == 1


async def test_create_run_accepts_an_empty_request_body(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient
) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(RUNS, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    assert len(fake_workflow_client.enqueued) == 1


@pytest.mark.parametrize(
    "payload",
    [{"wordCount": 100}, {"wordCount": 5000}, {"topic": "x" * 301}, {"pillar": "Z"}, {"unexpected": True}],
)
async def test_create_run_rejects_invalid_body(
    payload: dict[str, object],
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(RUNS, json=payload, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


async def test_viewer_cannot_create_run(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.VIEWER)

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "missing permission blog.generate"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


@pytest.mark.parametrize("headers", [{}, {"X-CSRF-Token": "0" * 64}], ids=["missing", "wrong"])
async def test_create_run_without_valid_csrf_token_is_rejected(
    headers: dict[str, str],
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
) -> None:
    http, _ = await login_as(Role.EDITOR)

    response = await http.post(RUNS, json={}, headers=headers)

    assert response.status_code == 403
    assert response.json()["title"] == "CSRF token missing or invalid"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


async def test_create_run_requires_login(client: AsyncClient, fake_workflow_client: FakeWorkflowClient) -> None:
    response = await client.post(RUNS, json={})

    assert response.status_code == 401
    assert fake_workflow_client.enqueued == []


async def test_create_run_is_rejected_when_agent_disabled(
    login_as: LoginAs,
    app: FastAPI,
    settings: Settings,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    monkeypatch.setattr(app.state, "settings", settings.model_copy(update={"agent_enabled": False}))

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Agent disabled"
    assert fake_workflow_client.enqueued == []
    assert await run_count(db_session) == 0


async def test_enqueue_failure_returns_503_and_marks_run_failed(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    fake_workflow_client.enqueue_error = ConnectionError("dbos system database unreachable")

    response = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Workflow service unavailable"
    run = (await db_session.scalars(select(BlogRun))).one()
    assert run.status == "FAILED"
    assert run.error == {"stage": "enqueue", "message": "ConnectionError: dbos system database unreachable"}
    assert run.finished_at is not None
    assert fake_workflow_client.enqueued == []  # the fake raises before it records the call


# --- GET /runs --------------------------------------------------------------------------------------------


async def test_list_runs_is_newest_first_and_paginated(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    base = datetime(2026, 9, 1, 7, 0, tzinfo=UTC)
    oldest = add_run(db_session, created_at=base)
    middle = add_run(db_session, created_at=base + timedelta(hours=1))
    newest = add_run(db_session, created_at=base + timedelta(hours=2))
    await db_session.flush()

    first = await http.get(RUNS, params={"limit": 2})
    second = await http.get(RUNS, params={"limit": 2, "offset": 2})

    assert first.status_code == 200, first.text
    page = first.json()
    assert set(page) == {"items", "total", "limit", "offset"}
    assert [item["id"] for item in page["items"]] == [str(newest.id), str(middle.id)]
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 0)
    assert set(page["items"][0]) == RUN_KEYS
    assert second.status_code == 200, second.text
    assert [item["id"] for item in second.json()["items"]] == [str(oldest.id)]
    assert (second.json()["total"], second.json()["offset"]) == (3, 2)


async def test_list_runs_defaults_to_20_items(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    for _ in range(21):
        add_run(db_session)
    await db_session.flush()

    response = await http.get(RUNS)

    assert response.status_code == 200
    page = response.json()
    assert (len(page["items"]), page["total"], page["limit"], page["offset"]) == (20, 21, 20, 0)


async def test_list_runs_filters_by_status(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    failed = add_run(db_session, status=RunStatus.FAILED)
    add_run(db_session, status=RunStatus.SUCCEEDED)
    add_run(db_session, status=RunStatus.QUEUED)
    await db_session.flush()

    response = await http.get(RUNS, params={"status": "FAILED"})

    assert response.status_code == 200
    page = response.json()
    assert [item["id"] for item in page["items"]] == [str(failed.id)]
    assert page["items"][0]["status"] == "FAILED"
    assert page["total"] == 1


async def test_list_runs_caps_limit_at_100(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    for _ in range(101):
        add_run(db_session)
    await db_session.flush()

    response = await http.get(RUNS, params={"limit": 500})

    assert response.status_code == 200
    page = response.json()
    assert (len(page["items"]), page["total"], page["limit"]) == (100, 101, 100)


@pytest.mark.parametrize("query", [{"limit": 0}, {"offset": -1}, {"status": "DONE"}], ids=["limit", "offset", "status"])
async def test_list_runs_rejects_bad_query(query: dict[str, object], login_as: LoginAs) -> None:
    http, _ = await login_as(Role.VIEWER)

    response = await http.get(RUNS, params=query)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_list_runs_requires_login(client: AsyncClient) -> None:
    response = await client.get(RUNS)

    assert response.status_code == 401


# --- GET /runs/{id} ---------------------------------------------------------------------------------------


async def test_run_detail_returns_404_for_unknown_run(login_as: LoginAs) -> None:
    http, _ = await login_as(Role.VIEWER)

    response = await http.get(f"{RUNS}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Run not found"


async def test_run_detail_rejects_malformed_id(login_as: LoginAs) -> None:
    http, _ = await login_as(Role.VIEWER)

    response = await http.get(f"{RUNS}/not-a-uuid")

    assert response.status_code == 422


async def test_run_detail_shape_and_ordering(login_as: LoginAs, db_session: AsyncSession) -> None:
    http, _ = await login_as(Role.VIEWER)
    t0 = datetime(2026, 9, 17, 1, 30, tzinfo=UTC)
    run = add_run(db_session, status=RunStatus.SUCCEEDED)
    run.params = {"topic": "Prior authorisation automation"}
    await db_session.flush()
    manual_wf = f"manual-{run.id}"
    retry = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"fork-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=2,
        forked_from_workflow_id=manual_wf,
        status=AttemptStatus.SUCCEEDED.value,
        started_at=t0 + timedelta(minutes=5),
        finished_at=t0 + timedelta(minutes=6),
    )
    original = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=manual_wf,
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.FAILED.value,
        started_at=t0,
        finished_at=t0 + timedelta(minutes=1),
        error={"class": "RouteExhausted", "message": "all models failed"},
    )
    db_session.add_all([retry, original])
    await db_session.flush()
    failed_echo = AgentRun(
        run_id=run.id,
        attempt_id=original.id,
        dbos_workflow_id=manual_wf,
        dbos_step_id=2,
        step_name="hello.echo",
        agent_name="hello",
        status=StepStatus.FAILED.value,
        started_at=t0,
        error={"class": "RouteExhausted", "message": "all models failed"},
        trace_id=run.trace_id,
        created_at=t0 + timedelta(seconds=1),
    )
    first_open = AgentRun(
        run_id=run.id,
        attempt_id=original.id,
        dbos_workflow_id=manual_wf,
        dbos_step_id=1,
        step_name="hello.open_attempt",
        status=StepStatus.SUCCEEDED.value,
        started_at=t0,
        trace_id=run.trace_id,
        created_at=t0 + timedelta(seconds=1),
    )
    retry_finish = AgentRun(
        run_id=run.id,
        attempt_id=retry.id,
        dbos_workflow_id=f"fork-{run.id}",
        dbos_step_id=3,
        step_name="hello.finish",
        status=StepStatus.SUCCEEDED.value,
        started_at=t0 + timedelta(minutes=5),
        trace_id=run.trace_id,
        created_at=t0 + timedelta(minutes=6),
    )
    retry_echo = AgentRun(
        run_id=run.id,
        attempt_id=retry.id,
        dbos_workflow_id=f"fork-{run.id}",
        dbos_step_id=2,
        step_name="hello.echo",
        agent_name="hello",
        agent_version="1",
        model="mock:hello",
        prompt_name="hello/echo",
        prompt_version=1,
        status=StepStatus.SUCCEEDED.value,
        tries=2,
        started_at=t0 + timedelta(minutes=5),
        completed_at=t0 + timedelta(minutes=5, milliseconds=150),
        duration_ms=150,
        input_tokens=20,
        output_tokens=8,
        cost_usd=Decimal("0.000125"),
        trace_id=run.trace_id,
        created_at=t0 + timedelta(minutes=5),
    )
    db_session.add_all([failed_echo, retry_finish, retry_echo, first_open])
    await db_session.flush()

    response = await http.get(f"{RUNS}/{run.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert (body["id"], body["status"], body["kind"]) == (str(run.id), "SUCCEEDED", "manual")
    assert body["params"] == {"topic": "Prior authorisation automation"}

    assert [attempt["attemptNo"] for attempt in body["attempts"]] == [1, 2]
    assert all(set(attempt) == ATTEMPT_KEYS for attempt in body["attempts"])
    second = body["attempts"][1]
    assert second["id"] == str(retry.id)
    assert second["dbosWorkflowId"] == f"fork-{run.id}"
    assert second["workflowName"] == "hello_pipeline"
    assert second["status"] == "SUCCEEDED"
    assert second["forkedFromWorkflowId"] == manual_wf
    assert datetime.fromisoformat(second["startedAt"]) == t0 + timedelta(minutes=5)
    assert datetime.fromisoformat(second["finishedAt"]) == t0 + timedelta(minutes=6)
    assert body["attempts"][0]["forkedFromWorkflowId"] is None

    # created_at first, then dbos_step_id for rows written at the same instant
    assert [step["id"] for step in body["steps"]] == [
        str(first_open.id),
        str(failed_echo.id),
        str(retry_echo.id),
        str(retry_finish.id),
    ]
    assert all(set(step) == STEP_KEYS for step in body["steps"])
    assert body["steps"][1]["status"] == "FAILED"
    assert body["steps"][1]["error"] == {"class": "RouteExhausted", "message": "all models failed"}
    echo = body["steps"][2]
    assert Decimal(str(echo.pop("costUsd"))) == Decimal("0.000125")
    assert echo == {
        "id": str(retry_echo.id),
        "stepName": "hello.echo",
        "dbosStepId": 2,
        "status": "SUCCEEDED",
        "tries": 2,
        "agentName": "hello",
        "model": "mock:hello",
        "promptName": "hello/echo",
        "promptVersion": 1,
        "inputTokens": 20,
        "outputTokens": 8,
        "durationMs": 150,
        "error": None,
    }


# --- POST /runs/{id}/cancel -------------------------------------------------------------------------------


async def test_cancel_queued_run_cancels_its_workflow(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    created = await http.post(RUNS, json={}, headers={"X-CSRF-Token": csrf})
    run_id = uuid.UUID(created.json()["id"])

    response = await http.post(f"{RUNS}/{run_id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body) == RUN_KEYS
    assert body["status"] == "CANCELLED"
    assert body["finishedAt"] is not None
    # No attempt row exists until the worker starts the workflow, so the service cancels it by its id.
    assert fake_workflow_client.cancelled == [f"manual-{run_id}"]
    run = await db_session.get(BlogRun, run_id)
    assert run is not None
    assert run.status == "CANCELLED"
    [cancelled] = await audit_rows(db_session, "run.cancel", run_id)
    assert cancelled.actor_user_id == run.created_by


async def test_cancel_cancels_only_enqueued_and_running_attempts(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    run = add_run(db_session, status=RunStatus.QUEUED)
    await db_session.flush()
    finished = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"manual-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=1,
        status=AttemptStatus.FAILED.value,
        started_at=datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
        finished_at=datetime(2026, 9, 17, 1, 1, tzinfo=UTC),
    )
    enqueued = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"restart-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=2,
        status=AttemptStatus.ENQUEUED.value,
    )
    running = RunAttempt(
        run_id=run.id,
        dbos_workflow_id=f"fork-{run.id}",
        workflow_name="hello_pipeline",
        attempt_no=3,
        status=AttemptStatus.RUNNING.value,
        started_at=datetime(2026, 9, 17, 1, 5, tzinfo=UTC),
    )
    db_session.add_all([running, finished, enqueued])
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "CANCELLED"
    assert fake_workflow_client.cancelled == [f"restart-{run.id}", f"fork-{run.id}"]
    assert (finished.status, enqueued.status, running.status) == ("FAILED", "CANCELLED", "CANCELLED")
    assert finished.finished_at == datetime(2026, 9, 17, 1, 1, tzinfo=UTC)
    assert enqueued.finished_at is not None
    assert running.finished_at is not None


@pytest.mark.parametrize("status", [RunStatus.SUCCEEDED, RunStatus.FAILED])
async def test_cancel_terminal_run_is_a_conflict(
    status: RunStatus,
    login_as: LoginAs,
    fake_workflow_client: FakeWorkflowClient,
    db_session: AsyncSession,
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    run = add_run(db_session, status=status)
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Run cannot be cancelled"
    assert fake_workflow_client.cancelled == []
    assert run.status == status.value
    assert await audit_rows(db_session, "run.cancel", run.id) == []


async def test_cancel_already_cancelled_run_changes_nothing(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.EDITOR)
    finished_at = datetime(2026, 9, 17, 2, 0, tzinfo=UTC)
    run = add_run(db_session, status=RunStatus.CANCELLED)
    run.finished_at = finished_at
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 202
    assert response.json()["status"] == "CANCELLED"
    assert fake_workflow_client.cancelled == []
    assert run.finished_at == finished_at
    assert await audit_rows(db_session, "run.cancel", run.id) == []


async def test_cancel_unknown_run_is_404(login_as: LoginAs, fake_workflow_client: FakeWorkflowClient) -> None:
    http, csrf = await login_as(Role.EDITOR)

    response = await http.post(f"{RUNS}/{uuid.uuid4()}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 404
    assert response.json()["title"] == "Run not found"
    assert fake_workflow_client.cancelled == []


async def test_viewer_cannot_cancel_run(
    login_as: LoginAs, fake_workflow_client: FakeWorkflowClient, db_session: AsyncSession
) -> None:
    http, csrf = await login_as(Role.VIEWER)
    run = add_run(db_session, status=RunStatus.QUEUED)
    await db_session.flush()

    response = await http.post(f"{RUNS}/{run.id}/cancel", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 403
    assert response.json()["detail"] == "missing permission blog.generate"
    assert fake_workflow_client.cancelled == []
    assert run.status == "QUEUED"
```

- [ ] **Step 5: Write the failing integration test `backend/tests/workflows/test_runs_api_dbos.py`**

Write this test now, before any Task 12 code exists, so it fails first like the other two (Step 6) and passes only once the runs routes are in place (Step 12). It imports nothing that Task 12 creates, so it collects cleanly today.

How the test works:
- **Real wiring.** It builds the app **without** an injected client, so the lifespan creates `WorkflowClient.from_settings(...)` exactly as the `api` container does. It drives the lifespan explicitly, because `ASGITransport` does not run it.
- **Committed data.** The in-process DBOS executor (Task 11's `dbos_runtime`) and the API commit in their own sessions. The test therefore creates its user with `sessionmaker_committing` and cleans up with `clean_db`. It does not use `db_session` or `login_as`: a user created there would be invisible to the app's own sessions.
- **App version.** `app_version` is set to `"pytest"` to match the executor. DBOS leaves a workflow `ENQUEUED` forever when no executor runs its version (verified in research; Step 13 demonstrates it).
- **Workflow registration.** The module imports `mdcopilot_blog.workflows.hello`. `dbos_runtime` relies on test modules to register workflows at collection time. Without the import, running this file alone failed with `DBOS Error 4 ... hello_pipeline is not a registered workflow function`, and the run stayed `QUEUED` (verified).
- **Fixture order.** `database_url` is listed first in `usefixtures`, so the test database exists before DBOS launches, even if `dbos_runtime` ever stops requesting it. In a verified variant where it did not, DBOS launched first, `database_url` then force-dropped the database, and the run stayed `QUEUED`.
- **No skip.** This test must run. It has no skip condition.

```python
"""End to end: POST /api/blog-agent/runs through the real WorkflowClient, executed by in-process DBOS.

Uses Task 11's `dbos_runtime` fixture, which launches DBOS on the pytest event loop against the test
database. The app is built without an injected client, so its lifespan creates
`WorkflowClient.from_settings(...)` exactly as the api container does. The API and the worker commit
in their own sessions, so this test uses committed data and `clean_db`, not `db_session`.

`dbos_runtime` does not import workflow modules; test modules do, at collection time, so every workflow is
registered before DBOS launches. This module imports `workflows.hello` for that reason: run on its own, it would
otherwise leave `hello_pipeline` unregistered (DBOS Error 4) and the run QUEUED.
"""

import asyncio
import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import mdcopilot_blog.workflows.hello  # noqa: F401  (registers hello_pipeline before dbos_runtime launches DBOS)
from mdcopilot_blog.api.app import create_app
from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClientProtocol
from mdcopilot_blog.workflows.names import STEP_HELLO_ECHO, STEP_HELLO_FINISH, STEP_HELLO_OPEN

RUNS = "/api/blog-agent/runs"
EMAIL = "e2e-editor@example.test"
PASSWORD = "correct-horse-battery"
TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}
TERMINAL_WORKFLOW_STATUSES = {"SUCCESS", "ERROR", "CANCELLED", "MAX_RECOVERY_ATTEMPTS_EXCEEDED"}
TIMEOUT_SECONDS = 60.0


async def wait_for_run(http: AsyncClient, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        response = await http.get(f"{RUNS}/{run_id}")
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        if body["status"] in TERMINAL_RUN_STATUSES:
            return body
        if time.monotonic() > deadline:
            pytest.fail(f"run {run_id} is still {body['status']} after {TIMEOUT_SECONDS}s")
        await asyncio.sleep(0.2)


async def wait_for_workflow(client: WorkflowClientProtocol, workflow_id: str) -> str | None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        status = await client.status(workflow_id)
        if status in TERMINAL_WORKFLOW_STATUSES or time.monotonic() > deadline:
            return status
        await asyncio.sleep(0.2)


# database_url first: the test database must exist (and be migrated) before DBOS launches against it.
@pytest.mark.usefixtures("database_url", "dbos_runtime", "clean_db")
async def test_manual_run_executes_hello_pipeline_through_dbos(
    settings: Settings, sessionmaker_committing: async_sessionmaker[AsyncSession]
) -> None:
    # dbos_runtime launches DBOS with application_version "pytest". The client stamps settings.app_version
    # on every enqueue, and DBOS leaves a workflow ENQUEUED forever if no executor runs that version.
    e2e_settings = settings.model_copy(update={"app_version": "pytest", "agent_enabled": True})
    async with sessionmaker_committing() as db:
        await create_user(db, email=EMAIL, display_name="E2E Editor", role=Role.EDITOR, password=PASSWORD)
        await db.commit()

    app = create_app(e2e_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": "http://test"}
        ) as http,
    ):
        login = await http.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert login.status_code == 200, login.text
        csrf = login.json()["csrfToken"]

        created = await http.post(RUNS, json={"topic": "hello"}, headers={"X-CSRF-Token": csrf})
        assert created.status_code == 202, created.text
        assert created.json()["status"] == "QUEUED"
        run_id = created.json()["id"]

        detail = await wait_for_run(http, run_id)
        workflow_status = await wait_for_workflow(app.state.workflow_client, f"manual-{run_id}")

    assert detail["status"] == "SUCCEEDED", detail
    assert detail["stage"] == STEP_HELLO_FINISH
    assert detail["startedAt"] is not None
    assert detail["finishedAt"] is not None
    assert detail["params"] == {"topic": "hello"}
    assert workflow_status == "SUCCESS"

    [attempt] = detail["attempts"]
    assert (attempt["dbosWorkflowId"], attempt["workflowName"], attempt["attemptNo"], attempt["status"]) == (
        f"manual-{run_id}",
        "hello_pipeline",
        1,
        "SUCCEEDED",
    )
    assert attempt["forkedFromWorkflowId"] is None

    steps = detail["steps"]
    assert [(step["stepName"], step["dbosStepId"], step["status"], step["tries"]) for step in steps] == [
        (STEP_HELLO_OPEN, 1, "SUCCEEDED", 1),
        (STEP_HELLO_ECHO, 2, "SUCCEEDED", 1),
        (STEP_HELLO_FINISH, 3, "SUCCEEDED", 1),
    ]
    assert all(step["error"] is None for step in steps)
    echo = steps[1]
    assert (echo["agentName"], echo["model"], echo["promptName"], echo["promptVersion"]) == (
        "hello",
        "mock:hello",
        "hello/echo",
        1,
    )
    # usage recorded by the mock fixture fixtures/mock/llm/hello/hello_echo.json
    assert (echo["inputTokens"], echo["outputTokens"]) == (20, 8)
```

- [ ] **Step 6: Run the API test and the integration test and watch them fail**

Run: `docker compose run --rm tools pytest tests/api/test_runs_api.py tests/workflows/test_runs_api_dbos.py -q`

Expected: `33 failed` (32 from the API test, 1 from the integration test). No runs routes exist yet, so every runs request gets `404 Not Found`.
- **API test (32).** The CSRF and login cases fail too, because the app-level CSRF dependency never runs for an unmatched route.
- **Integration test (1).** DBOS launches, the lifespan starts, and the login returns 200. The test then fails on the POST, at the line `assert created.status_code == 202, created.text`, with:
  ```text
  E           AssertionError: {"type":"about:blank","title":"Not Found","status":404,"instance":"/api/blog-agent/runs"}
  E           assert 404 == 202
  ```

Decision rule: the integration test must fail **only** at that line, with a 404. If it errors during setup (`database_url`, `dbos_runtime`), fails at the login assertion, or fails for any other reason, the fault is in Task 5, 9 or 11. Fix it there before going on, because Step 12 relies on everything except the runs routes already working.

- [ ] **Step 7: Implement `backend/src/mdcopilot_blog/services/runs.py`**

```python
"""Run service: create, list, read and cancel user-visible runs (``app.blog_runs``).

The API never executes workflows. It records the run, commits, and only then enqueues the
workflow through the workflow client (``DBOSClient`` in production), so the worker can always
find the row it is handed.
"""

import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas import ManualRunRequest
from mdcopilot_blog.db.models import AgentRun, BlogRun, RunAttempt
from mdcopilot_blog.domain.enums import AttemptStatus, RunKind, RunStatus
from mdcopilot_blog.domain.state_machine import Entity, require_transition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClientProtocol
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_HELLO

logger = logging.getLogger(__name__)

RUN_ENTITY = "blog_run"
ACTIVE_ATTEMPT_STATUSES = frozenset({AttemptStatus.ENQUEUED.value, AttemptStatus.RUNNING.value})
ERROR_MESSAGE_LIMIT = 500


def manual_workflow_id(run_id: uuid.UUID) -> str:
    return f"manual-{run_id}"


def initial_workflow_id(run: BlogRun) -> str:
    """Workflow id of a run's first execution: ``manual-<run id>`` or ``daily-<run date>``."""
    if run.kind == RunKind.DAILY.value:
        return f"daily-{run.run_date.isoformat()}"
    return manual_workflow_id(run.id)


async def create_manual_run(
    db: AsyncSession,
    client: WorkflowClientProtocol,
    *,
    principal: Principal,
    request: ManualRunRequest,
    settings: Settings,
    today: date,
) -> BlogRun:
    if not settings.agent_enabled:
        raise ProblemError(409, "Agent disabled", "BLOG_AGENT_ENABLED is false, so new runs are rejected.")

    run = BlogRun(
        kind=RunKind.MANUAL.value,
        run_date=request.run_date or today,
        status=RunStatus.QUEUED.value,
        params=request.model_dump(mode="json", exclude_none=True),
        trace_id=new_trace_id(),
        created_by=principal.user_id,
    )
    db.add(run)
    await db.flush()
    workflow_id = manual_workflow_id(run.id)
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="run.create",
        entity_type=RUN_ENTITY,
        entity_id=str(run.id),
        details={"kind": run.kind, "run_date": run.run_date.isoformat(), "workflow_id": workflow_id},
    )
    await db.commit()

    try:
        await client.enqueue(
            workflow_name=WORKFLOW_HELLO,
            queue_name=QUEUE_PIPELINE,
            workflow_id=workflow_id,
            args=(str(run.id),),
            timeout_seconds=settings.production_timeout_minutes * 60,
        )
    except Exception as exc:
        logger.exception("enqueue failed", extra={"run_id": str(run.id), "workflow_id": workflow_id})
        require_transition(Entity.RUN, run.status, RunStatus.FAILED.value)
        run.status = RunStatus.FAILED.value
        run.finished_at = datetime.now(UTC)
        run.error = {"stage": "enqueue", "message": f"{type(exc).__name__}: {exc}"[:ERROR_MESSAGE_LIMIT]}
        await db.commit()
        raise ProblemError(503, "Workflow service unavailable", f"run {run.id} was marked FAILED") from exc

    logger.info("manual run enqueued", extra={"run_id": str(run.id), "workflow_id": workflow_id})
    return run


async def list_runs(
    db: AsyncSession, *, status: RunStatus | None, limit: int, offset: int
) -> tuple[list[BlogRun], int]:
    query = select(BlogRun)
    count_query = select(func.count()).select_from(BlogRun)
    if status is not None:
        query = query.where(BlogRun.status == status.value)
        count_query = count_query.where(BlogRun.status == status.value)
    total = await db.scalar(count_query)
    # id is a UUIDv7, so it breaks created_at ties in insertion order
    rows = await db.scalars(query.order_by(BlogRun.created_at.desc(), BlogRun.id.desc()).limit(limit).offset(offset))
    return list(rows.all()), int(total or 0)


async def get_run_detail(
    db: AsyncSession, run_id: uuid.UUID
) -> tuple[BlogRun, list[RunAttempt], list[AgentRun]] | None:
    run = await db.get(BlogRun, run_id)
    if run is None:
        return None
    attempts = await db.scalars(select(RunAttempt).where(RunAttempt.run_id == run_id).order_by(RunAttempt.attempt_no))
    steps = await db.scalars(
        select(AgentRun).where(AgentRun.run_id == run_id).order_by(AgentRun.created_at, AgentRun.dbos_step_id)
    )
    return run, list(attempts.all()), list(steps.all())


async def cancel_run(
    db: AsyncSession, client: WorkflowClientProtocol, *, run: BlogRun, principal: Principal
) -> BlogRun:
    if run.status == RunStatus.CANCELLED.value:
        # Same-state transition: a no-op under the state machine rules. Nothing is left to cancel.
        return run
    require_transition(Entity.RUN, run.status, RunStatus.CANCELLED.value)
    previous_status = run.status

    attempts = list(
        (await db.scalars(select(RunAttempt).where(RunAttempt.run_id == run.id).order_by(RunAttempt.attempt_no))).all()
    )
    active = [attempt for attempt in attempts if attempt.status in ACTIVE_ATTEMPT_STATUSES]
    workflow_ids = [attempt.dbos_workflow_id for attempt in active]
    first_workflow_id = initial_workflow_id(run)
    if run.status == RunStatus.QUEUED.value and all(a.dbos_workflow_id != first_workflow_id for a in attempts):
        # The worker writes the attempt row only when the workflow starts, so a run that is still
        # queued has no row for its first workflow yet. Cancel that workflow by its known id.
        workflow_ids.insert(0, first_workflow_id)

    try:
        for workflow_id in workflow_ids:
            await client.cancel(workflow_id)
    except Exception as exc:
        logger.exception("cancel failed", extra={"run_id": str(run.id)})
        raise ProblemError(503, "Workflow service unavailable", f"run {run.id} was not cancelled") from exc

    now = datetime.now(UTC)
    for attempt in active:
        attempt.status = AttemptStatus.CANCELLED.value
        attempt.finished_at = now
    run.status = RunStatus.CANCELLED.value
    run.finished_at = now
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="run.cancel",
        entity_type=RUN_ENTITY,
        entity_id=str(run.id),
        details={"from_status": previous_status, "workflow_ids": workflow_ids},
    )
    await db.commit()
    return run
```

- [ ] **Step 8: Run the service test and watch it pass**

Run: `docker compose run --rm tools pytest tests/db/test_runs_service.py -q`

Expected: `10 passed`.

- [ ] **Step 9: Implement `backend/src/mdcopilot_blog/api/routers/runs.py`**

Route and response details:
- **Paths.** Routes are declared with their full `/runs...` paths. `create_app` adds the `/api/blog-agent` prefix.
- **Response model.** The return annotations are the response models. FastAPI serialises them by alias, which gives camelCase.
- **Cancel lookup.** Cancel reads the run with `SELECT ... FOR UPDATE`. Task 11's `set_run_status` takes the same lock, so concurrent cancels and worker status changes serialise, and neither overwrites the other: a step that runs after the cancel sees `CANCELLED` and gets `InvalidTransition`.

```python
"""Runs API (mounted under /api/blog-agent): create, list, read and cancel runs."""

import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, Query

from mdcopilot_blog.api.deps import Principal, SessionDep, SettingsDep, WorkflowClientDep, require_permission
from mdcopilot_blog.api.schemas import AttemptOut, ManualRunRequest, Page, RunDetail, RunOut, StepOut
from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import Permission, RunStatus
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.runs import cancel_run, create_manual_run, get_run_detail, list_runs

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

router = APIRouter(tags=["runs"])

CanView = Annotated[Principal, Depends(require_permission(Permission.VIEW))]
CanGenerate = Annotated[Principal, Depends(require_permission(Permission.GENERATE))]


def run_not_found(run_id: uuid.UUID) -> ProblemError:
    return ProblemError(404, "Run not found", f"no run with id {run_id}")


def to_run_out(run: BlogRun) -> RunOut:
    return RunOut.model_validate(run)


@router.post("/runs", status_code=202)
async def create_run(
    db: SessionDep,
    settings: SettingsDep,
    client: WorkflowClientDep,
    principal: CanGenerate,
    body: Annotated[ManualRunRequest | None, Body()] = None,
) -> RunOut:
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    run = await create_manual_run(
        db, client, principal=principal, request=body or ManualRunRequest(), settings=settings, today=today
    )
    return to_run_out(run)


@router.get("/runs")
async def get_runs(
    db: SessionDep,
    _: CanView,
    status: RunStatus | None = None,
    limit: Annotated[int, Query(ge=1)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RunOut]:
    capped = min(limit, MAX_PAGE_SIZE)
    runs, total = await list_runs(db, status=status, limit=capped, offset=offset)
    return Page[RunOut](items=[to_run_out(run) for run in runs], total=total, limit=capped, offset=offset)


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, db: SessionDep, _: CanView) -> RunDetail:
    found = await get_run_detail(db, run_id)
    if found is None:
        raise run_not_found(run_id)
    run, attempts, steps = found
    return RunDetail(
        **to_run_out(run).model_dump(by_alias=False),
        params=run.params,
        attempts=[AttemptOut.model_validate(attempt) for attempt in attempts],
        steps=[StepOut.model_validate(step) for step in steps],
    )


@router.post("/runs/{run_id}/cancel", status_code=202)
async def cancel(run_id: uuid.UUID, db: SessionDep, client: WorkflowClientDep, principal: CanGenerate) -> RunOut:
    # Row lock, the same one Task 11's set_run_status takes: cancels and worker status writes serialise.
    run = await db.get(BlogRun, run_id, with_for_update=True)
    if run is None:
        raise run_not_found(run_id)
    try:
        cancelled = await cancel_run(db, client, run=run, principal=principal)
    except InvalidTransition as exc:
        raise ProblemError(409, "Run cannot be cancelled", f"run is {exc.current}") from exc
    return to_run_out(cancelled)
```

- [ ] **Step 10: Register the router in `backend/src/mdcopilot_blog/api/app.py` (two-line edit)**

This is the edit Task 9 defines. Make exactly two insertions and change nothing else:
1. After the line `from mdcopilot_blog.api.routers import health as health_routes`, insert:
   ```python
   from mdcopilot_blog.api.routers import runs as runs_routes
   ```
2. After the line `    (settings_routes.router, "/api/blog-agent"),`, insert:
   ```python
       (runs_routes.router, "/api/blog-agent"),
   ```

Afterwards, the router imports and `ROUTERS` in `app.py` read exactly:
```python
from mdcopilot_blog.api.routers import auth as auth_routes
from mdcopilot_blog.api.routers import health as health_routes
from mdcopilot_blog.api.routers import runs as runs_routes
from mdcopilot_blog.api.routers import settings as settings_routes
from mdcopilot_blog.api.routers import users as users_routes

# (router, prefix) in registration order. Task 12 appends the runs router here.
ROUTERS: tuple[tuple[APIRouter, str], ...] = (
    (health_routes.router, ""),
    (auth_routes.router, "/api/auth"),
    (users_routes.router, "/api/admin/users"),
    (settings_routes.router, "/api/blog-agent"),
    (runs_routes.router, "/api/blog-agent"),
)
```

The new import sits in alphabetical order, so ruff's import sorting accepts it unchanged. Then check:
```bash
grep -n "runs_routes" backend/src/mdcopilot_blog/api/app.py
```

Expected: exactly two lines, the import and the `ROUTERS` entry.

- [ ] **Step 11: Run the API test and watch it pass**

Run: `docker compose run --rm tools pytest tests/api/test_runs_api.py -q`

Expected: `32 passed`. The enqueue-failure test logs an `enqueue failed` traceback in the captured log output. That traceback is expected and is not a failure.

- [ ] **Step 12: Run the integration test and watch it pass**

Run: `docker compose run --rm tools pytest tests/workflows/test_runs_api_dbos.py -q`

Expected: `1 passed`, in a few seconds. This is the test that failed in Step 6 with a 404. Steps 7–10 added the service and the routes, so the POST now returns 202, and in-process DBOS carries the run through to `SUCCEEDED`.

Decision rules if it does not pass:
- **`Failed: run ... is still QUEUED after 60.0s`.** The executor never ran the workflow. Check in this order:
  1. **The log shows `DBOS Error 4 ... hello_pipeline is not a registered workflow function`.** The `import mdcopilot_blog.workflows.hello` line is missing from the test module.
  2. **The log shows `Notification listener error ... server closed the connection unexpectedly`.** DBOS launched before `database_url` recreated the database. Run `docker compose run --rm tools pytest tests/workflows/test_runs_api_dbos.py -q --setup-show`: `database_url` must be set up before `dbos_runtime`.
  3. **Version.** Does `dbos_runtime` launch with `application_version="pytest"`? The test's settings must use the same value, because `WorkflowClient.enqueue` sends `app_version` from settings.
  4. **Queue.** Does `dbos_runtime` register queue `pipeline` after `DBOS.launch()`?
  5. **Application name.** Is the `DBOSClient` `application_name` (`DBOS_APPLICATION_NAME` in `workflows/client.py`) `"mdcopilot-blog"`, the same as `DBOS_APP_NAME` in `workflows/dbos_config.py`?
- **The run ends `FAILED`.** The detail's `steps[*].error` names the failing step. Fix it in Task 11's code, not here.
- **`DBOS.launch()` misbehaves inside the pytest loop.** Apply Task 11's recorded fallback (launch in a background thread) in the `dbos_runtime` fixture, and record which variant is in use. This test needs no change either way.

- [ ] **Step 13: Prove the integration test can fail (negative control)**

This makes a throwaway copy that drops the `app_version` pin and shortens the wait, runs it, and deletes it:
```bash
sed -e 's/"app_version": "pytest", //' -e 's/TIMEOUT_SECONDS = 60.0/TIMEOUT_SECONDS = 8.0/' \
  backend/tests/workflows/test_runs_api_dbos.py > backend/tests/workflows/test_zz_negative_control.py
docker compose run --rm tools pytest tests/workflows/test_zz_negative_control.py -q
rm backend/tests/workflows/test_zz_negative_control.py
```

Expected: `1 failed`, with `Failed: run <uuid> is still QUEUED after 8.0s`. Confirm that the temporary file is gone (`ls backend/tests/workflows/`).

- [ ] **Step 14: Run all Task 12 tests together, then with the kill switch set in the environment**

Run:
```bash
docker compose run --rm tools pytest tests/api/test_runs_api.py tests/db/test_runs_service.py tests/workflows/test_runs_api_dbos.py -q
docker compose run --rm -e BLOG_AGENT_ENABLED=false tools pytest tests/api/test_runs_api.py tests/db/test_runs_service.py tests/workflows/test_runs_api_dbos.py -q
```

Expected: `43 passed` both times. The tests pin `agent_enabled` themselves, so an operator's kill switch in `.env` cannot break them. Only the disabled-case tests turn it off.

- [ ] **Step 15: Run Task 9's route guards, then the whole backend suite**

Run:
```bash
docker compose run --rm tools pytest tests/api/test_rbac_routes.py -q
docker compose run --rm tools pytest -q
```

Expected:
- **First command: `27 passed`.** Two of its tests now cover the four runs routes:
  - `test_every_non_public_route_requires_a_principal` walks `ROUTERS`;
  - `test_every_served_path_is_declared_in_routers` compares the OpenAPI paths.
- **Second command:** `1130 passed`, with no failures or errors. That is Task 11's 1087 plus this task's 43.

- [ ] **Step 16: Lint and type-check**

Run: `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"`

Expected, exactly these three lines:
```text
All checks passed!
111 files already formatted
Success: no issues found in 62 source files
```

Where the counts come from (backend tree after Tasks 1–12, from the tasks' Files lists):
- **111 formatted files.** This is 110 `.py` files plus `backend/prompts/hello/echo.v1.md`. ruff 0.16.8 also formats Markdown files by default, and that prompt is the only `.md` file under `backend/`.
  - The 110 `.py` files are 62 in `src/`, 2 in `migrations/` (`env.py` and the `0001_foundation` revision) and 46 in `tests/` (including Task 5's `tests/db/__init__.py`).
  - Task 12 adds 5 of them: `services/runs.py`, `api/routers/runs.py`, `tests/db/test_runs_service.py`, `tests/api/test_runs_api.py` and `tests/workflows/test_runs_api_dbos.py`. After Task 11 the count was 106.
  - ruff skips `.pytest_cache`, `.ruff_cache` and `.mypy_cache`, so earlier test runs do not change the count.
- **62 source files.** These are the `.py` modules under `src/mdcopilot_blog/`: 60 after Task 11, plus this task's `services/runs.py` and `api/routers/runs.py`.

Decision rules for the counts:
- **Lower** (for example `110 files` or `61 source files`). A file from this task or an earlier one is missing. Compare the tree with the Files lists.
- **`112 files already formatted`.** Most likely `tests/workflows/test_zz_negative_control.py` was left behind by Step 13. Delete it and re-run.

These counts were checked in containers on 2026-09-17, against the full backend tree built from the Task 1–12 code blocks, Task 8 included: `110` without `tests/db/__init__.py`, and `111` with it.

If `ruff format --check` flags a Task 12 file, run `docker compose run --rm tools ruff format <path>`, then re-run Steps 14 and 16.

- [ ] **Step 17: Checkpoint: list the files changed in this task (no git)**

Run:
```bash
ls -la backend/src/mdcopilot_blog/services/runs.py backend/src/mdcopilot_blog/api/routers/runs.py \
  backend/tests/db/test_runs_service.py backend/tests/api/test_runs_api.py backend/tests/workflows/test_runs_api_dbos.py
grep -n "runs_routes" backend/src/mdcopilot_blog/api/app.py
```

Files changed:
- Created:
  - `backend/src/mdcopilot_blog/services/runs.py`
  - `backend/src/mdcopilot_blog/api/routers/runs.py`
  - `backend/tests/db/test_runs_service.py`
  - `backend/tests/api/test_runs_api.py`
  - `backend/tests/workflows/test_runs_api_dbos.py`
- Modified: `backend/src/mdcopilot_blog/api/app.py`, with two added lines (the `runs_routes` import and the `ROUTERS` entry).

---

### Task 13: Frontend shell

Build the React dashboard shell in `frontend/`:
- login;
- the eleven spec §25 nav pages, with a role-aware sidebar and a per-page permission gate;
- a Dashboard with "Generate today's blog" and a recent-runs table;
- an Agent Runs page with Cancel;
- the `dev` (Vite) and `prod` (nginx) image targets that Task 14's compose `web` service uses.

`compose.yaml` has no `web` service until Task 14, so every command here uses a throwaway `node:24-alpine` container.

**Run location.** All commands run from `mdcopilot-blog/`.

**Never run `npm`/`node` on the host.** `frontend/node_modules` is installed by Linux containers through the bind mount and contains Linux-native binaries (rolldown, lightningcss, @tailwindcss/oxide). Git and Docker ignore it: `.gitignore` already lists `node_modules/` and `dist/`, and `frontend/.dockerignore` excludes both.

**Verified 2026-09-17.** Every command and file below was run in throwaway `p1p-*` containers (node 24.21.0, npm 11.19.0, nginx 1.30.5), with these results:
- `npm run build`, `npm run lint`, `npm run typecheck` and `npx vitest run` passed (6 files, 35 tests);
- `docker build --target dev` and `--target prod` succeeded;
- `nginx -t` in the prod image passed;
- the prod container started with no `api` host.

**Files:**
- Create (by the scaffold/installer commands; do not hand-edit):
  - `frontend/package-lock.json`, `frontend/.gitignore`, `frontend/README.md`, `frontend/tsconfig.node.json`, `frontend/public/favicon.svg`
  - `frontend/components.json`, `frontend/src/index.css`, `frontend/src/lib/utils.ts`
  - `frontend/src/components/ui/{badge,button,card,dropdown-menu,input,label,separator,sheet,skeleton,sonner,table}.tsx`
- Create (by command, then shown in full for checking): `frontend/package.json`
- Create (hand-written, full code below):
  - Config: `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/vite.config.ts`, `frontend/eslint.config.js`, `frontend/index.html`
  - Docker: `frontend/.dockerignore`, `frontend/Dockerfile`, `frontend/nginx/default.conf.template`
  - App core: `frontend/src/main.tsx`, `frontend/src/router.tsx`, `frontend/src/app/nav.ts`
  - Library: `frontend/src/lib/api.ts`, `frontend/src/lib/query-client.ts`
  - Features: `frontend/src/features/auth/session.ts`, `frontend/src/features/auth/permissions.ts`, `frontend/src/features/runs/api.ts`, `frontend/src/features/runs/runs-table.tsx`
  - Routes: `frontend/src/routes/login-page.tsx`, `app-layout.tsx`, `placeholder-page.tsx`, `forbidden-page.tsx`, `require-permission.tsx`, `dashboard-page.tsx`, `agent-runs-page.tsx`
- Delete (scaffold demo content): `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/src/assets/`, `frontend/public/icons.svg`
- Test:
  - `frontend/src/lib/api.test.ts`
  - `frontend/src/app/nav.test.ts`
  - `frontend/src/routes/login-page.test.tsx`
  - `frontend/src/routes/dashboard-page.test.tsx`
  - `frontend/src/routes/agent-runs-page.test.tsx`
  - `frontend/src/router.test.tsx`
- Test support: `frontend/src/test/setup.ts`, `frontend/src/test/helpers.tsx`

**Interfaces:**
- **Consumes** (the HTTP contract from Task 9 and Task 12). JSON is camelCase, and errors are `application/problem+json` `{type, title, status, instance, detail?}`. The content type is exactly `application/problem+json`; the backend research verified this.
  - `GET /api/auth/session` → 200 `{user: {id, email, displayName, role, permissions: string[]}, csrfToken}`, or 401 problem.
  - `POST /api/auth/login` with body `{email, password}` → 200 (same body as session). Errors: 401 "Invalid email or password"; 429 "Too many login attempts".
  - `POST /api/auth/logout` → 204. Needs the `X-CSRF-Token` header.
  - `GET /api/blog-agent/runs?limit=N` → `{items: RunOut[], total, limit, offset}`.
  - `RunOut` = `{id, kind, runDate, status, stage, traceId, costUsd, createdAt, startedAt, finishedAt}`. `costUsd` is a **string**: Pydantic serialises `Decimal` that way, verified with fastapi 0.141.1 / pydantic 2.13.5 in a container: `{"costUsd":"0.000000","csrfToken":"t"}`.
  - `POST /api/blog-agent/runs` with body `{}` → 202 `RunOut`. Errors: 409 "Agent disabled"; 403.
  - `POST /api/blog-agent/runs/{id}/cancel` → 202 `RunOut`. Errors: 404; 409.
- **Produces** (TypeScript, all under `frontend/src`, imported via `@/`):
  - `lib/api.ts`:
    - `setCsrfToken(token: string | null): void`
    - `getCsrfToken(): string | null`
    - `class ApiError extends Error { status: number; body: unknown }`
    - `type ApiRequestInit`
    - `apiFetch<T>(path: string, init?: ApiRequestInit): Promise<T>`
    - `problemMessage(error: unknown, fallback: string): string`
  - `lib/query-client.ts`: `createQueryClient(): QueryClient`, `queryClient`
  - `features/auth/session.ts`:
    - `type SessionUser = {id, email, displayName, role: Role, permissions: Permission[]}`
    - `type SessionResponse = {user: SessionUser, csrfToken: string}`
    - `type LoginInput`
    - `sessionQueryOptions` (key `['session']`)
    - `login(input): Promise<SessionResponse>`
    - `logout(): Promise<void>`
  - `features/auth/permissions.ts`: `type Role`, `type Permission`, `hasPermission(user: SessionUser | undefined, p: Permission): boolean`
  - `app/nav.ts`: `type NavItem = {label, path, permission}`, `NAV_ITEMS: readonly NavItem[]` (11 items), `visibleNavItems(user: SessionUser | undefined): NavItem[]`
  - `features/runs/api.ts`:
    - types `RunStatus`, `RunKind`, `RunOut`, `Page<T>`
    - `isTerminalRunStatus(status): boolean`
    - `RUNS_QUERY_KEY = ['runs']`
    - `runsQueryOptions(limit: number)` (key `['runs', {limit}]`; polls every 3 s while any listed run is non-terminal)
    - `createRun(): Promise<RunOut>`
    - `cancelRun(runId: string): Promise<RunOut>`
    - `formatCost(value: string): string`
  - `features/runs/runs-table.tsx`: `RunsTable({runs, isPending, isError, showRunId?, renderActions?})`
  - `router.tsx`: `requireSession(client: QueryClient)` (loader), `buildRoutes(client: QueryClient): RouteObject[]`. `main.tsx` creates the browser router, so importing `router.tsx` has no side effects.
  - Route components:
    - `LoginPage`, `AppLayout`, `DashboardPage`, `AgentRunsPage`, `ForbiddenPage`
    - `PlaceholderPage({title})`
    - `RequirePermission({permission, children})`
  - npm scripts: `dev`, `build`, `lint`, `preview`, `test` (`vitest run`), `typecheck` (`tsc -b`).
  - Docker targets for Task 14:
    - `dev`: Vite on 5173, `CMD npm run dev`. It reads `VITE_API_PROXY_TARGET` (default `http://api:8000`) and `VITE_USE_POLLING`. The compose service must be named `web` (`server.allowedHosts`) and needs `volumes: ["./frontend:/app", "/app/node_modules"]`.
    - `prod`: nginx on 8080, proxying `/api/` to `api:8000`, which is resolved at runtime.

- [ ] **Step 1: Scaffold the Vite app**

Only the new, empty `frontend/` directory is mounted, so `.env` never enters the container.

```bash
mkdir frontend
docker run --rm -v "$PWD/frontend:/work/frontend" -w /work node:24-alpine \
  npm create -y vite@9.2.1 frontend -- --template react-ts --eslint --no-interactive --no-immediate
```

Expected: `Scaffolding project in /work/frontend...` then `Done.`. `ls -A frontend` shows `.gitignore README.md eslint.config.js index.html package.json public src tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts`.

- [ ] **Step 2: Set the package name and install the scaffold dependencies**

```bash
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine \
  sh -c 'npm pkg set name=mdcopilot-blog-web && npm install --no-audit --no-fund'
```

Expected: `added 160 packages`. `head -3 frontend/package.json` shows `"name": "mdcopilot-blog-web"`, and `frontend/package-lock.json` now exists with the same name.

- [ ] **Step 3: Write the path alias, Vite, Vitest and ESLint config (needed before `shadcn init`)**

> **Owner gate: do this before writing any file in this step.**
> - **Why it stops.** The scaffold already wrote `frontend/eslint.config.js`, and the local ECC hook `pre:config-protection` blocks replacing it. The hook lives at `~/.claude/plugins/cache/ecc/ecc/2.2.1/scripts/hooks/config-protection.js` and allows only first-time creation, so a Write/Edit here fails with `BLOCKED: Modifying eslint.config.js is not allowed`.
> - **What to ask.** Stop and ask the owner to allow this one write. For example, the owner can run the Task 13 session with `ECC_DISABLED_HOOKS=pre:config-protection` (set in the environment Claude Code starts with) and unset it after Step 3, which means restarting the session without it.
> - **What not to do.** Do not write the file through shell redirection to dodge the hook. Do not delete the file and recreate it either.
> - **What the owner approves.** Exactly two changes to the scaffold's file; the rest of the file is the scaffold's own content:
>   1. `'.vitest'` is added to `globalIgnores`.
>   2. A `src/components/ui/**/*.tsx` block turns off `react-refresh/only-export-components`. shadcn's generated `button.tsx` and `badge.tsx` export cva variant helpers next to their components, and with the scaffold's file `eslint .` reports exactly those 2 errors (re-checked in a `node:24-alpine` container).
>
> The other files in this step are not protected and need no approval.

TypeScript 6 rejects `baseUrl` (TS5101), so the alias uses `paths` only.

`frontend/tsconfig.json`:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

`frontend/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "es2023",
    "lib": ["ES2023", "DOM"],
    "module": "esnext",
    "types": ["vite/client"],
    "allowArbitraryExtensions": true,
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    /* Linting */
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,

    /* Path alias (shadcn) */
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

`frontend/vite.config.ts`. Line 1 must be the vitest reference, or `tsc -b` fails with "'test' does not exist in type 'UserConfigExport'". `changeOrigin: false` keeps the browser's Host, so FastAPI's Origin check matches, exactly as it does behind nginx.

```ts
/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Where the dev server forwards /api. In docker compose the backend service is "api".
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://api:8000'
// Bind-mounted source on Docker Desktop for macOS: inotify events normally arrive,
// but polling is the fallback when HMR does not pick up edits.
const usePolling = process.env.VITE_USE_POLLING === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: ['web', 'localhost'],
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      '/api': {
        target: apiTarget,
        // false keeps the browser's Host (e.g. localhost:5173) so the backend
        // sees the same Host/Origin pair a production nginx would forward.
        changeOrigin: false,
        xfwd: true,
      },
    },
  },
  preview: {
    host: true,
    port: 4173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})
```

`frontend/eslint.config.js`. This replaces the scaffold's file, so it needs the owner gate above. The override is required: without it, shadcn's `button.tsx` and `badge.tsx` fail `react-refresh/only-export-components`.

```js
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', '.vitest']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    // shadcn/ui generated files export cva variant helpers next to components.
    files: ['src/components/ui/**/*.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
```

Temporary `frontend/src/index.css`. `shadcn init` checks for this Tailwind import and then rewrites the file:

```css
@import "tailwindcss";
```

Leave `frontend/tsconfig.node.json` exactly as the scaffold wrote it. It covers only `vite.config.ts`, with `module: nodenext` and `types: ["node"]`.

- [ ] **Step 4: Install Tailwind and initialise shadcn**

`--preset nova` gives style `radix-nova` with base colour `neutral`. There is no `--base-color` flag in shadcn 4.21. Do not use `--defaults`: it means the Next template with Base UI. stdin is closed so the CLI never prompts.

```bash
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine \
  npm install -D --no-audit --no-fund tailwindcss@4.3.3 @tailwindcss/vite@4.3.3
docker run --rm -i -v "$PWD/frontend:/app" -w /app node:24-alpine \
  sh -c 'npx -y shadcn@4.21.0 init --base radix --preset nova --yes --no-monorepo --no-rtl < /dev/null'
docker run --rm -i -v "$PWD/frontend:/app" -w /app node:24-alpine \
  sh -c 'npx -y shadcn@4.21.0 add button input label card dropdown-menu sonner badge separator sheet skeleton table --yes < /dev/null'
```

Expected output:
- **init:** `✔ Created 1 file: src/lib/utils.ts`, `✔ Updating src/index.css`, `Project initialization completed.`
  - `frontend/components.json` has `"style": "radix-nova"`, `"baseColor": "neutral"` and `"iconLibrary": "lucide"`.
  - `frontend/src/lib/utils.ts` is `export { cn } from "cn"`.
  - `frontend/src/index.css` is 129 lines starting with `@import "tailwindcss"; @import "tw-animate-css"; @import "shadcn/tailwind.css"; @import "@fontsource-variable/geist";`.
- **add:** `✔ Created 11 files:`, listing `src/components/ui/button.tsx input.tsx label.tsx card.tsx dropdown-menu.tsx sonner.tsx badge.tsx separator.tsx skeleton.tsx table.tsx sheet.tsx`.
- **Notes:**
  - The generated components import `cn` from the new `cn@0.3.0` package (maintainer shadcn, SLSA provenance), and lucide icons use the `XxxIcon` names.
  - The research did not verify `table`; it was verified for this task (the add exits 0 and the build passes).

- [ ] **Step 5: Add router, TanStack Query, the test stack and the extra scripts**

```bash
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine \
  npm install --no-audit --no-fund react-router@8.4.0 @tanstack/react-query@5.103.1
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine \
  npm install -D --no-audit --no-fund vitest@5.0.1 jsdom@30.0.1 @testing-library/react@16.3.3 @testing-library/dom@10.4.2 @testing-library/user-event@14.6.7 @testing-library/jest-dom@7.0.1
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine \
  sh -c 'npm pkg set scripts.test="vitest run" scripts.typecheck="tsc -b" && npm ls --depth=0'
```

`npm ls` must show:
- UI and data: `react@19.3.0`, `react-router@8.4.0`, `@tanstack/react-query@5.103.1`, `shadcn@4.21.0`, `cn@0.3.0`, `radix-ui@1.6.7`, `sonner@2.0.8`, `lucide-react@1.46.0`
- Build and lint: `vite@8.3.0`, `typescript@6.0.3`, `tailwindcss@4.3.3`, `typescript-eslint@8.70.0`, `eslint-plugin-react-refresh@0.5.7`
- Test: `vitest@5.0.1`, `jsdom@30.0.1`

Do **not** upgrade TypeScript to 7.x: typescript-eslint 8.70 supports `<6.1.0`.

`frontend/package.json` must now read exactly:

```json
{
  "name": "mdcopilot-blog-web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "test": "vitest run",
    "typecheck": "tsc -b"
  },
  "dependencies": {
    "@fontsource-variable/geist": "^5.3.0",
    "@tanstack/react-query": "^5.103.1",
    "class-variance-authority": "^0.7.1",
    "cn": "^0.3.0",
    "lucide-react": "^1.46.0",
    "next-themes": "^0.4.6",
    "radix-ui": "^1.6.7",
    "react": "^19.2.8",
    "react-dom": "^19.2.8",
    "react-router": "^8.4.0",
    "shadcn": "^4.21.0",
    "sonner": "^2.0.8",
    "tw-animate-css": "^1.4.0"
  },
  "devDependencies": {
    "@eslint/js": "^10.0.1",
    "@tailwindcss/vite": "^4.3.3",
    "@testing-library/dom": "^10.4.2",
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.7",
    "@types/node": "^24.13.3",
    "@types/react": "^19.2.18",
    "@types/react-dom": "^19.2.7",
    "@vitejs/plugin-react": "^6.1.1",
    "eslint": "^10.10.0",
    "eslint-plugin-react-hooks": "^7.1.1",
    "eslint-plugin-react-refresh": "^0.5.6",
    "globals": "^17.12.0",
    "jsdom": "^30.0.1",
    "tailwindcss": "^4.3.3",
    "typescript": "~6.0.2",
    "typescript-eslint": "^8.69.0",
    "vite": "^8.3.0",
    "vitest": "^5.0.1"
  }
}
```

`shadcn` stays in `dependencies` because `src/index.css` imports `shadcn/tailwind.css`. Only the build stage sees its large dependency tree; the nginx image ships just `dist/`.

- [ ] **Step 6: Remove the demo content, set the page title, and add the Vitest setup file**

```bash
rm -r frontend/src/App.tsx frontend/src/App.css frontend/src/assets frontend/public/icons.svg
mkdir -p frontend/src/test frontend/src/app frontend/src/features/auth frontend/src/features/runs frontend/src/routes frontend/nginx
```

The scaffold's `src/main.tsx` still imports `./App.tsx`, so `npm run build` fails until Step 18 replaces it. Vitest never loads `main.tsx`.

`frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MDCopilot Blog</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/test/setup.ts`. `globals: false` means cleanup runs explicitly. The `matchMedia` stub is required: without it, every test that renders sonner's `<Toaster />` fails with `TypeError: window.matchMedia is not a function`.

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom has no matchMedia; sonner's Toaster reads prefers-color-scheme through it.
// Defined once here (not with vi.stubGlobal) so unstubAllGlobals below leaves it in place.
if (typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string): MediaQueryList => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
```

- [ ] **Step 7: Write the failing fetch-wrapper test**

`frontend/src/lib/api.test.ts`. The first four tests are the verified ones. The last three pin down problem+json handling: the backend's error content type is exactly `application/problem+json`, which the verified wrapper did not parse.

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, getCsrfToken, problemMessage, setCsrfToken } from '@/lib/api'

function jsonResponse(body: unknown, status = 200, contentType = 'application/json'): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': contentType },
  })
}

function mockFetch(response: Response) {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function sentHeaders(fetchMock: ReturnType<typeof mockFetch>): Headers {
  const init = fetchMock.mock.calls[0]?.[1]
  return new Headers(init?.headers)
}

describe('apiFetch', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('sends the in-memory CSRF token on unsafe methods', async () => {
    setCsrfToken('token-from-memory')
    const fetchMock = mockFetch(jsonResponse({ id: 'r1' }, 202))

    const result = await apiFetch<{ id: string }>('/api/blog-agent/runs', {
      method: 'post',
      json: { topic: 'Hello' },
    })

    expect(result).toEqual({ id: 'r1' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/blog-agent/runs')
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('same-origin')
    expect(init?.body).toBe(JSON.stringify({ topic: 'Hello' }))
    const headers = sentHeaders(fetchMock)
    expect(headers.get('X-CSRF-Token')).toBe('token-from-memory')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('does not send the CSRF token on GET', async () => {
    setCsrfToken('token-from-memory')
    const fetchMock = mockFetch(jsonResponse([]))

    await apiFetch('/api/blog-agent/runs')

    expect(sentHeaders(fetchMock).has('X-CSRF-Token')).toBe(false)
  })

  it('omits the header when no token is held and never persists it', async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }))

    await apiFetch('/api/auth/logout', { method: 'POST' })

    expect(getCsrfToken()).toBeNull()
    expect(sentHeaders(fetchMock).has('X-CSRF-Token')).toBe(false)
    expect(window.localStorage.length).toBe(0)
    expect(document.cookie).toBe('')
  })

  it('throws ApiError with status and parsed body on failure', async () => {
    mockFetch(jsonResponse({ detail: 'CSRF token missing' }, 403))

    const error = await apiFetch('/api/blog-agent/runs', { method: 'DELETE' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(403)
    expect((error as ApiError).body).toEqual({ detail: 'CSRF token missing' })
  })

  it('parses application/problem+json error bodies', async () => {
    const problem = { type: 'about:blank', title: 'Agent disabled', status: 409, instance: '/api/blog-agent/runs' }
    mockFetch(jsonResponse(problem, 409, 'application/problem+json'))

    const error = await apiFetch('/api/blog-agent/runs', { method: 'POST', json: {} }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).body).toEqual(problem)
  })
})

describe('problemMessage', () => {
  it('returns the problem title from an ApiError', () => {
    const error = new ApiError(403, { type: 'about:blank', title: 'Forbidden', status: 403 })

    expect(problemMessage(error, 'fallback')).toBe('Forbidden')
  })

  it('falls back for other errors and bodies without a title', () => {
    expect(problemMessage(new ApiError(500, 'Internal Server Error'), 'fallback')).toBe('fallback')
    expect(problemMessage(new TypeError('Failed to fetch'), 'fallback')).toBe('fallback')
  })
})
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/lib/api.test.ts`

Expected: FAIL with `Error: Failed to resolve import "@/lib/api" from "src/lib/api.test.ts". Does the file exist?`

- [ ] **Step 8: Implement the fetch wrapper and the query client**

`frontend/src/lib/api.ts`:

```ts
// Thin fetch wrapper for the FastAPI backend.
// The CSRF token lives only in module memory: never in localStorage, never in a JS-readable cookie.

let csrfToken: string | null = null

export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

export function getCsrfToken(): string | null {
  return csrfToken
}

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export type ApiRequestInit = Omit<RequestInit, 'body'> & {
  body?: BodyInit | null
  json?: unknown
}

// The backend sends errors as application/problem+json, so accept any JSON media type.
function isJsonContentType(value: string | null): boolean {
  if (value === null) {
    return false
  }
  const mediaType = value.split(';')[0].trim().toLowerCase()
  return mediaType === 'application/json' || mediaType.endsWith('+json')
}

export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { json, headers: initHeaders, body: initBody, method: initMethod, ...rest } = init
  const method = (initMethod ?? 'GET').toUpperCase()
  const headers = new Headers(initHeaders)
  headers.set('Accept', 'application/json')

  let body = initBody
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(json)
  }

  if (UNSAFE_METHODS.has(method) && csrfToken !== null) {
    headers.set('X-CSRF-Token', csrfToken)
  }

  const response = await fetch(path, {
    ...rest,
    method,
    headers,
    body,
    credentials: 'same-origin',
  })

  const text = await response.text()
  const isJson = isJsonContentType(response.headers.get('Content-Type'))
  const data: unknown = text && isJson ? JSON.parse(text) : text || undefined

  if (!response.ok) {
    throw new ApiError(response.status, data)
  }
  return data as T
}

// Human-readable message for a failed request: the problem+json title when there is one.
export function problemMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body = error.body
    if (typeof body === 'object' && body !== null && 'title' in body && typeof body.title === 'string') {
      return body.title
    }
  }
  return fallback
}
```

`frontend/src/lib/query-client.ts`. 4xx errors are never retried, so a 401 from the session probe is requested exactly once.

```ts
import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/lib/api'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false
          }
          return failureCount < 2
        },
      },
    },
  })
}

export const queryClient = createQueryClient()
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/lib/api.test.ts`

Expected: `✓ src/lib/api.test.ts (7 tests)`, `Tests  7 passed (7)`.

- [ ] **Step 9: Write the shared test helpers and the failing nav test**

`frontend/src/test/helpers.tsx`:
- `mockApi` stubs `fetch` with a route table keyed `"METHOD /path?query"`.
- `renderRoutes` renders a memory router with a fresh QueryClient, an optional pre-seeded session, and the sonner `<Toaster />`.
- The RBAC copy keeps **camelCase** names on purpose. `eslint-plugin-react-refresh` 0.5.7 treats any capitalised name matching `^[A-Z][a-zA-Z0-9_]*$`, including SCREAMING_CASE, as a component. It would then report every exported helper in this `.tsx` file (8 errors were seen with `TEST_ROLE_PERMISSIONS`).
- `import type` from `@/features/runs/api` is erased at runtime, so this file loads before that module exists.

```tsx
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { type RouteObject, RouterProvider, createMemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { Toaster } from '@/components/ui/sonner'
import type { Permission, Role } from '@/features/auth/permissions'
import { type SessionResponse, sessionQueryOptions } from '@/features/auth/session'
import type { Page, RunOut } from '@/features/runs/api'
import { createQueryClient } from '@/lib/query-client'

// Copy of the backend matrix (domain/rbac.py ROLE_PERMISSIONS). The server is the source of truth;
// tests use this copy only to build realistic sessions.
// Names stay camelCase: react-refresh/only-export-components treats any capitalised name in a .tsx
// file as a component and would then flag every exported helper below.
const viewerPermissions: Permission[] = ['blog.view']
const editorPermissions: Permission[] = [...viewerPermissions, 'blog.generate', 'blog.edit']
const reviewerPermissions: Permission[] = [
  ...editorPermissions,
  'blog.review',
  'blog.approve',
  'blog.schedule',
  'blog.agent_runs',
]
const publisherPermissions: Permission[] = [...reviewerPermissions, 'blog.publish']
const adminPermissions: Permission[] = [...publisherPermissions, 'blog.settings']

const rolePermissions: Record<Role, Permission[]> = {
  viewer: viewerPermissions,
  editor: editorPermissions,
  reviewer: reviewerPermissions,
  publisher: publisherPermissions,
  admin: adminPermissions,
}

export function sessionFor(role: Role, permissions: Permission[] = rolePermissions[role]): SessionResponse {
  return {
    user: {
      id: `user-${role}`,
      email: `${role}@example.com`,
      displayName: `Test ${role}`,
      role,
      permissions,
    },
    csrfToken: `csrf-${role}`,
  }
}

export function jsonResponse(body: unknown, status = 200, contentType = 'application/json'): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': contentType } })
}

export function problemResponse(status: number, title: string): Response {
  return jsonResponse({ type: 'about:blank', title, status }, status, 'application/problem+json')
}

export function makeRun(overrides: Partial<RunOut> = {}): RunOut {
  return {
    id: 'run-1',
    kind: 'manual',
    runDate: '2026-09-17',
    status: 'QUEUED',
    stage: null,
    traceId: '0123456789abcdef0123456789abcdef',
    costUsd: '0.000000',
    createdAt: '2026-09-17T07:00:00Z',
    startedAt: null,
    finishedAt: null,
    ...overrides,
  }
}

export function runsPage(items: RunOut[], limit = 10): Page<RunOut> {
  return { items, total: items.length, limit, offset: 0 }
}

type RouteHandler = (init: RequestInit | undefined) => Response

// Stubs global fetch. Keys are "METHOD /path?query"; anything else gets a 404 problem.
// Handlers build a new Response per call because a body can only be read once.
export function mockApi(routes: Record<string, RouteHandler>) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const method = (init?.method ?? 'GET').toUpperCase()
    const handler = routes[`${method} ${String(input)}`]
    return handler ? handler(init) : problemResponse(404, 'Not mocked')
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function callsTo(fetchMock: ReturnType<typeof mockApi>, method: string, path: string) {
  return fetchMock.mock.calls.filter(
    ([input, init]) => String(input) === path && (init?.method ?? 'GET').toUpperCase() === method,
  )
}

type RenderRoutesOptions = {
  initialEntries?: string[]
  session?: SessionResponse
  queryClient?: QueryClient
}

export function renderRoutes(routes: RouteObject[], options: RenderRoutesOptions = {}) {
  const queryClient = options.queryClient ?? createQueryClient()
  if (options.session) {
    queryClient.setQueryData(sessionQueryOptions.queryKey, options.session)
  }
  const router = createMemoryRouter(routes, { initialEntries: options.initialEntries ?? ['/'] })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>,
  )
  return { router, queryClient, ...view }
}
```

`frontend/src/app/nav.test.ts`. Of the 11 nav items, 8 need only `blog.view`, so a viewer sees 8 (not 9; see the note at the end of this task).

```ts
import { describe, expect, it } from 'vitest'
import { NAV_ITEMS, visibleNavItems } from '@/app/nav'
import { type Role, hasPermission } from '@/features/auth/permissions'
import { sessionFor } from '@/test/helpers'

function labelsFor(role: Role): string[] {
  return visibleNavItems(sessionFor(role).user).map((item) => item.label)
}

describe('NAV_ITEMS', () => {
  it('lists the spec pages in order with their paths and permissions', () => {
    expect(NAV_ITEMS.map((item) => [item.label, item.path, item.permission])).toEqual([
      ['Dashboard', '/', 'blog.view'],
      ["Today's Ideas", '/ideas', 'blog.view'],
      ['Research', '/research', 'blog.view'],
      ['Drafts', '/drafts', 'blog.view'],
      ['Review Queue', '/review', 'blog.review'],
      ['Published', '/published', 'blog.view'],
      ['Topics', '/topics', 'blog.view'],
      ['Content Calendar', '/calendar', 'blog.view'],
      ['Sources', '/sources', 'blog.view'],
      ['Settings', '/settings', 'blog.settings'],
      ['Agent Runs', '/agent-runs', 'blog.agent_runs'],
    ])
  })
})

describe('visibleNavItems', () => {
  it('shows a viewer the 8 view-only pages', () => {
    const labels = labelsFor('viewer')

    expect(labels).toHaveLength(8)
    expect(labels).not.toContain('Review Queue')
    expect(labels).not.toContain('Settings')
    expect(labels).not.toContain('Agent Runs')
  })

  it('shows an editor the same 8 pages', () => {
    expect(labelsFor('editor')).toEqual(labelsFor('viewer'))
  })

  it('adds Review Queue and Agent Runs for reviewers and publishers', () => {
    for (const role of ['reviewer', 'publisher'] as const) {
      const labels = labelsFor(role)
      expect(labels).toHaveLength(10)
      expect(labels).toContain('Review Queue')
      expect(labels).toContain('Agent Runs')
      expect(labels).not.toContain('Settings')
    }
  })

  it('shows an admin all 11 pages', () => {
    expect(labelsFor('admin')).toEqual(NAV_ITEMS.map((item) => item.label))
  })

  it('shows nothing without a session', () => {
    expect(visibleNavItems(undefined)).toEqual([])
  })
})

describe('hasPermission', () => {
  it('reads the permission list the server sent', () => {
    expect(hasPermission(sessionFor('editor').user, 'blog.generate')).toBe(true)
    expect(hasPermission(sessionFor('viewer').user, 'blog.generate')).toBe(false)
    expect(hasPermission(undefined, 'blog.view')).toBe(false)
  })
})
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/app/nav.test.ts`

Expected: FAIL with `Error: Failed to resolve import "@/app/nav" from "src/app/nav.test.ts". Does the file exist?`

- [ ] **Step 10: Implement the session, permission and nav modules**

`frontend/src/features/auth/session.ts`. This is the verified module adapted to the camelCase `/api/auth/session` contract. `session.ts` and `permissions.ts` import each other's types only (`import type`), so there is no runtime cycle.

```ts
import { queryOptions } from '@tanstack/react-query'
import type { Permission, Role } from '@/features/auth/permissions'
import { apiFetch, setCsrfToken } from '@/lib/api'

// Mirrors backend api/schemas.py SessionUser / SessionResponse (camelCase JSON).
export type SessionUser = {
  id: string
  email: string
  displayName: string
  role: Role
  permissions: Permission[]
}

export type SessionResponse = {
  user: SessionUser
  csrfToken: string
}

export type LoginInput = {
  email: string
  password: string
}

export const sessionQueryOptions = queryOptions({
  queryKey: ['session'],
  queryFn: async () => {
    const session = await apiFetch<SessionResponse>('/api/auth/session')
    setCsrfToken(session.csrfToken)
    return session
  },
  staleTime: 60_000,
  retry: false,
})

export async function login(input: LoginInput): Promise<SessionResponse> {
  const session = await apiFetch<SessionResponse>('/api/auth/login', {
    method: 'POST',
    json: input,
  })
  setCsrfToken(session.csrfToken)
  return session
}

export async function logout(): Promise<void> {
  try {
    await apiFetch<void>('/api/auth/logout', { method: 'POST' })
  } finally {
    setCsrfToken(null)
  }
}
```

`frontend/src/features/auth/permissions.ts`:

```ts
import type { SessionUser } from '@/features/auth/session'

// Mirrors backend domain/enums.py Role and Permission values.
export type Role = 'viewer' | 'editor' | 'reviewer' | 'publisher' | 'admin'

export type Permission =
  | 'blog.view'
  | 'blog.generate'
  | 'blog.edit'
  | 'blog.review'
  | 'blog.approve'
  | 'blog.schedule'
  | 'blog.publish'
  | 'blog.agent_runs'
  | 'blog.settings'

// UI hint only. The API enforces every permission itself (deny by default).
export function hasPermission(user: SessionUser | undefined, permission: Permission): boolean {
  return user?.permissions.includes(permission) ?? false
}
```

`frontend/src/app/nav.ts`:

```ts
import { type Permission, hasPermission } from '@/features/auth/permissions'
import type { SessionUser } from '@/features/auth/session'

export type NavItem = {
  label: string
  path: string
  permission: Permission
}

// Spec §25 navigation, in display order.
export const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Dashboard', path: '/', permission: 'blog.view' },
  { label: "Today's Ideas", path: '/ideas', permission: 'blog.view' },
  { label: 'Research', path: '/research', permission: 'blog.view' },
  { label: 'Drafts', path: '/drafts', permission: 'blog.view' },
  { label: 'Review Queue', path: '/review', permission: 'blog.review' },
  { label: 'Published', path: '/published', permission: 'blog.view' },
  { label: 'Topics', path: '/topics', permission: 'blog.view' },
  { label: 'Content Calendar', path: '/calendar', permission: 'blog.view' },
  { label: 'Sources', path: '/sources', permission: 'blog.view' },
  { label: 'Settings', path: '/settings', permission: 'blog.settings' },
  { label: 'Agent Runs', path: '/agent-runs', permission: 'blog.agent_runs' },
]

export function visibleNavItems(user: SessionUser | undefined): NavItem[] {
  return NAV_ITEMS.filter((item) => hasPermission(user, item.permission))
}
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/app/nav.test.ts`

Expected: `✓ src/app/nav.test.ts (7 tests)`, `Tests  7 passed (7)`.

- [ ] **Step 11: Write the failing login page test**

`frontend/src/routes/login-page.test.tsx`. This is the verified test, adapted to `csrfToken` and the full session user. It adds a wrong-password case and five open-redirect cases, each of which must land on `/`:
- `//evil.example/x` (protocol-relative);
- `/\evil.example` (backslash);
- `/<tab>/evil.example`;
- `/.//evil.example` (dot segment);
- `https://evil.example/x` (absolute URL).

The browser URL parser turns the backslash, tab and dot-segment forms into `//evil.example`. A plain `startsWith('/')` check lets them through, and three cases then fail with `Sign-in failed, please try again` (checked in a container).

```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { sessionQueryOptions } from '@/features/auth/session'
import { getCsrfToken, setCsrfToken } from '@/lib/api'
import { LoginPage } from '@/routes/login-page'
import { callsTo, jsonResponse, mockApi, problemResponse, renderRoutes, sessionFor } from '@/test/helpers'

function renderLogin(initialEntry = '/login') {
  return renderRoutes(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/', element: <p>home route</p> },
      { path: '/drafts', element: <p>drafts route</p> },
    ],
    { initialEntries: [initialEntry] },
  )
}

async function signIn(email: string, password: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('LoginPage', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('renders the sign-in form', () => {
    renderLogin()

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute('type', 'email')
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
  })

  it('logs in, stores the CSRF token in memory, caches the session and follows ?next=', async () => {
    const session = { ...sessionFor('editor'), csrfToken: 'fresh-token' }
    const fetchMock = mockApi({ 'POST /api/auth/login': () => jsonResponse(session) })
    const { router, queryClient } = renderLogin('/login?next=%2Fdrafts')

    await signIn('editor@example.com', 'correct-horse-battery')

    expect(await screen.findByText('drafts route')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/drafts')
    expect(getCsrfToken()).toBe('fresh-token')
    expect(queryClient.getQueryData(sessionQueryOptions.queryKey)).toEqual(session)
    const [call] = callsTo(fetchMock, 'POST', '/api/auth/login')
    expect(call).toBeDefined()
    expect(JSON.parse(String(call![1]?.body))).toEqual({
      email: 'editor@example.com',
      password: 'correct-horse-battery',
    })
  })

  it.each([
    ['protocol-relative', '%2F%2Fevil.example%2Fx'],
    ['backslash', '%2F%5Cevil.example'],
    ['tab', '%2F%09%2Fevil.example'],
    ['dot segment', '%2F.%2F%2Fevil.example'],
    ['absolute URL', 'https%3A%2F%2Fevil.example%2Fx'],
  ])('ignores an off-site ?next= value (%s)', async (_kind, next) => {
    mockApi({ 'POST /api/auth/login': () => jsonResponse(sessionFor('viewer')) })
    const { router } = renderLogin(`/login?next=${next}`)

    await signIn('viewer@example.com', 'correct-horse-battery')

    expect(await screen.findByText('home route')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('shows an error and stays on the page when the credentials are wrong', async () => {
    mockApi({ 'POST /api/auth/login': () => problemResponse(401, 'Invalid email or password') })
    const { router } = renderLogin()

    await signIn('editor@example.com', 'wrong-password-123')

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(getCsrfToken()).toBeNull()
  })
})
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/routes/login-page.test.tsx`

Expected: FAIL with `Error: Failed to resolve import "@/routes/login-page" from "src/routes/login-page.test.tsx". Does the file exist?`

- [ ] **Step 12: Implement the login page**

`frontend/src/routes/login-page.tsx`. This is the verified page, with one change: `safeNextPath` now parses `?next=` against the current origin, as the browser does, instead of checking prefixes.
- **Errors.** A 401 shows a fixed message; any other failure shows the problem title (e.g. 429 "Too many login attempts").
- **Why the `//` guard.** An origin comparison alone is not enough. `new URL('/.//evil.example', origin)` stays on this origin but has the pathname `//evil.example`, which the history API then reads as an off-site URL. Without the guard, the dot-segment test fails (checked in a container).

```tsx
import { type FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { login, sessionQueryOptions } from '@/features/auth/session'
import { ApiError, problemMessage } from '@/lib/api'

// Only allow same-origin paths, to avoid open redirects. The value is parsed the way the browser
// will parse it: '/\evil.example' and tab/newline variants resolve to '//evil.example', so a
// plain startsWith('/') check is not enough.
function safeNextPath(raw: string | null): string {
  if (!raw) {
    return '/'
  }
  try {
    const url = new URL(raw, window.location.origin)
    const path = url.pathname + url.search + url.hash
    // '/.//evil.example' stays on this origin with the pathname '//evil.example', which the
    // history API would then read as a protocol-relative (off-site) URL.
    if (url.origin !== window.location.origin || path.startsWith('//')) {
      return '/'
    }
    return path
  } catch {
    return '/'
  }
}

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async (session) => {
      queryClient.setQueryData(sessionQueryOptions.queryKey, session)
      await navigate(safeNextPath(searchParams.get('next')), { replace: true })
    },
    onError: (error) => {
      const message =
        error instanceof ApiError && error.status === 401
          ? 'Invalid email or password'
          : problemMessage(error, 'Sign-in failed, please try again')
      toast.error(message)
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate({ email, password })
  }

  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <CardHeader>
            <CardTitle>
              <h1>Sign in</h1>
            </CardTitle>
            <CardDescription>Use your MDCopilot Blog account.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? 'Signing in...' : 'Sign in'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </main>
  )
}
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/routes/login-page.test.tsx`

Expected: `✓ src/routes/login-page.test.tsx (8 tests)`, `Tests  8 passed (8)`.

- [ ] **Step 13: Write the failing dashboard test**

`frontend/src/routes/dashboard-page.test.tsx`. It checks four behaviours:
- the button is hidden for a viewer;
- a click POSTs `{}` with the `X-CSRF-Token` header;
- the runs list is re-fetched after the POST, via invalidation of `['runs']`;
- problem titles are shown.

```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import type { Role } from '@/features/auth/permissions'
import { setCsrfToken } from '@/lib/api'
import { DashboardPage } from '@/routes/dashboard-page'
import {
  callsTo,
  jsonResponse,
  makeRun,
  mockApi,
  problemResponse,
  renderRoutes,
  runsPage,
  sessionFor,
} from '@/test/helpers'

const RUNS_URL = '/api/blog-agent/runs?limit=10'
const GENERATE = "Generate today's blog"

function renderDashboard(role: Role) {
  const session = sessionFor(role)
  // The session loader normally stores the token; these tests seed the cache directly.
  setCsrfToken(session.csrfToken)
  return renderRoutes([{ path: '/', element: <DashboardPage /> }], { session })
}

describe('DashboardPage', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('lists recent runs with status, kind, date and cost', async () => {
    mockApi({
      [`GET ${RUNS_URL}`]: () =>
        jsonResponse(
          runsPage([
            makeRun({ id: 'run-a', status: 'SUCCEEDED', kind: 'daily', runDate: '2026-09-16', costUsd: '0.012300' }),
          ]),
        ),
    })

    renderDashboard('viewer')

    expect(await screen.findByText('SUCCEEDED')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Recent runs' })).toBeInTheDocument()
    expect(screen.getByText('daily')).toBeInTheDocument()
    expect(screen.getByText('2026-09-16')).toBeInTheDocument()
    expect(screen.getByText('$0.0123')).toBeInTheDocument()
  })

  it('hides the generate button from a viewer', async () => {
    mockApi({ [`GET ${RUNS_URL}`]: () => jsonResponse(runsPage([])) })

    renderDashboard('viewer')

    expect(await screen.findByText('No runs yet.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: GENERATE })).not.toBeInTheDocument()
  })

  it('starts a run with the CSRF header and refreshes the list', async () => {
    const fetchMock = mockApi({
      [`GET ${RUNS_URL}`]: () => jsonResponse(runsPage([])),
      'POST /api/blog-agent/runs': () => jsonResponse(makeRun({ id: 'run-new' }), 202),
    })
    const user = userEvent.setup()
    renderDashboard('editor')
    await screen.findByText('No runs yet.')

    await user.click(screen.getByRole('button', { name: GENERATE }))

    expect(await screen.findByText('Run queued')).toBeInTheDocument()
    const posts = callsTo(fetchMock, 'POST', '/api/blog-agent/runs')
    expect(posts).toHaveLength(1)
    const init = posts[0]![1]
    expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('csrf-editor')
    expect(init?.body).toBe('{}')
    await waitFor(() => expect(callsTo(fetchMock, 'GET', RUNS_URL)).toHaveLength(2))
  })

  it('shows the problem title when the API refuses the run', async () => {
    mockApi({
      [`GET ${RUNS_URL}`]: () => jsonResponse(runsPage([])),
      'POST /api/blog-agent/runs': () => problemResponse(409, 'Agent disabled'),
    })
    const user = userEvent.setup()
    renderDashboard('admin')
    await screen.findByText('No runs yet.')

    await user.click(screen.getByRole('button', { name: GENERATE }))

    expect(await screen.findByText('Agent disabled')).toBeInTheDocument()
  })

  it('says so when the runs cannot be loaded', async () => {
    mockApi({ [`GET ${RUNS_URL}`]: () => problemResponse(403, 'Forbidden') })

    renderDashboard('viewer')

    expect(await screen.findByText('Could not load runs.')).toBeInTheDocument()
  })
})
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/routes/dashboard-page.test.tsx`

Expected: FAIL with `Error: Failed to resolve import "@/routes/dashboard-page" from "src/routes/dashboard-page.test.tsx". Does the file exist?`

- [ ] **Step 14: Implement the runs API module, the runs table and the dashboard**

`frontend/src/features/runs/api.ts`:

```ts
import { queryOptions } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'

// Mirrors backend domain/enums.py RunStatus and RunKind.
export type RunStatus =
  | 'QUEUED'
  | 'RESEARCHING'
  | 'TOPICS_READY'
  | 'WAITING_FOR_TOPIC'
  | 'PRODUCING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'

export type RunKind = 'daily' | 'manual'

// Mirrors backend api/schemas.py RunOut (camelCase JSON). Pydantic sends Decimal as a string.
export type RunOut = {
  id: string
  kind: RunKind
  runDate: string
  status: RunStatus
  stage: string | null
  traceId: string
  costUsd: string
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
}

export type Page<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

const TERMINAL_RUN_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>(['SUCCEEDED', 'FAILED', 'CANCELLED'])

export function isTerminalRunStatus(status: RunStatus): boolean {
  return TERMINAL_RUN_STATUSES.has(status)
}

// Prefix shared by every runs query; invalidate it after any run mutation.
export const RUNS_QUERY_KEY = ['runs'] as const

const ACTIVE_RUN_POLL_MS = 3_000

export function runsQueryOptions(limit: number) {
  return queryOptions({
    queryKey: [...RUNS_QUERY_KEY, { limit }],
    queryFn: () => apiFetch<Page<RunOut>>(`/api/blog-agent/runs?limit=${limit}`),
    // Keep polling while any listed run is still moving, so status follows the worker.
    refetchInterval: (query) =>
      query.state.data?.items.some((run) => !isTerminalRunStatus(run.status)) ? ACTIVE_RUN_POLL_MS : false,
  })
}

export function createRun(): Promise<RunOut> {
  return apiFetch<RunOut>('/api/blog-agent/runs', { method: 'POST', json: {} })
}

export function cancelRun(runId: string): Promise<RunOut> {
  return apiFetch<RunOut>(`/api/blog-agent/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
}

export function formatCost(value: string): string {
  const amount = Number(value)
  return Number.isFinite(amount) ? `$${amount.toFixed(4)}` : value
}
```

`frontend/src/features/runs/runs-table.tsx`. This one table is shared by the Dashboard and Agent Runs pages.

```tsx
import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { type RunOut, type RunStatus, formatCost } from '@/features/runs/api'

type BadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline'

function statusVariant(status: RunStatus): BadgeVariant {
  switch (status) {
    case 'SUCCEEDED':
      return 'default'
    case 'FAILED':
      return 'destructive'
    case 'CANCELLED':
      return 'outline'
    default:
      return 'secondary'
  }
}

type RunsTableProps = {
  runs: RunOut[] | undefined
  isPending: boolean
  isError: boolean
  showRunId?: boolean
  renderActions?: (run: RunOut) => ReactNode
}

export function RunsTable({ runs, isPending, isError, showRunId = false, renderActions }: RunsTableProps) {
  if (isPending) {
    return <Skeleton className="h-24 w-full" aria-label="Loading runs" />
  }
  if (isError) {
    return <p className="text-sm text-destructive">Could not load runs.</p>
  }
  if (!runs || runs.length === 0) {
    return <p className="text-sm text-muted-foreground">No runs yet.</p>
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {showRunId ? <TableHead>Run</TableHead> : null}
          <TableHead>Status</TableHead>
          <TableHead>Kind</TableHead>
          <TableHead>Date</TableHead>
          <TableHead className="text-right">Cost</TableHead>
          {renderActions ? (
            <TableHead>
              <span className="sr-only">Actions</span>
            </TableHead>
          ) : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            {showRunId ? (
              <TableCell className="font-mono text-xs" title={run.id}>
                {run.id.slice(0, 8)}
              </TableCell>
            ) : null}
            <TableCell>
              <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            </TableCell>
            <TableCell>{run.kind}</TableCell>
            <TableCell>{run.runDate}</TableCell>
            <TableCell className="text-right tabular-nums">{formatCost(run.costUsd)}</TableCell>
            {renderActions ? <TableCell className="text-right">{renderActions(run)}</TableCell> : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

`frontend/src/routes/dashboard-page.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { hasPermission } from '@/features/auth/permissions'
import { sessionQueryOptions } from '@/features/auth/session'
import { RUNS_QUERY_KEY, createRun, runsQueryOptions } from '@/features/runs/api'
import { RunsTable } from '@/features/runs/runs-table'
import { problemMessage } from '@/lib/api'

const RECENT_RUNS_LIMIT = 10

export function DashboardPage() {
  const queryClient = useQueryClient()
  const { data: session } = useQuery(sessionQueryOptions)
  const runs = useQuery(runsQueryOptions(RECENT_RUNS_LIMIT))
  const canGenerate = hasPermission(session?.user, 'blog.generate')

  const generate = useMutation({
    mutationFn: createRun,
    onSuccess: async (run) => {
      toast.success('Run queued', { description: `Run for ${run.runDate} is ${run.status}.` })
      await queryClient.invalidateQueries({ queryKey: RUNS_QUERY_KEY })
    },
    onError: (error) => {
      toast.error(problemMessage(error, 'Could not start the run'))
    },
  })

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Start a pipeline run and follow its progress.</p>
        </div>
        {canGenerate ? (
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
            {generate.isPending ? 'Starting...' : "Generate today's blog"}
          </Button>
        ) : null}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Recent runs</h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <RunsTable runs={runs.data?.items} isPending={runs.isPending} isError={runs.isError} />
        </CardContent>
      </Card>
    </section>
  )
}
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/routes/dashboard-page.test.tsx`

Expected: `✓ src/routes/dashboard-page.test.tsx (5 tests)`, `Tests  5 passed (5)`.

- [ ] **Step 15: Write the failing Agent Runs test**

`frontend/src/routes/agent-runs-page.test.tsx`:

```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import type { SessionResponse } from '@/features/auth/session'
import { setCsrfToken } from '@/lib/api'
import { AgentRunsPage } from '@/routes/agent-runs-page'
import {
  callsTo,
  jsonResponse,
  makeRun,
  mockApi,
  problemResponse,
  renderRoutes,
  runsPage,
  sessionFor,
} from '@/test/helpers'

const RUNS_URL = '/api/blog-agent/runs?limit=50'
const CANCEL_URL = '/api/blog-agent/runs/run-active/cancel'

function renderAgentRuns(session: SessionResponse) {
  setCsrfToken(session.csrfToken)
  return renderRoutes([{ path: '/agent-runs', element: <AgentRunsPage /> }], {
    initialEntries: ['/agent-runs'],
    session,
  })
}

const activeAndFinished = () =>
  jsonResponse(
    runsPage(
      [makeRun({ id: 'run-active', status: 'PRODUCING' }), makeRun({ id: 'run-done', status: 'SUCCEEDED' })],
      50,
    ),
  )

describe('AgentRunsPage', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('offers Cancel only for runs that are still moving and cancels with the CSRF header', async () => {
    const fetchMock = mockApi({
      [`GET ${RUNS_URL}`]: activeAndFinished,
      [`POST ${CANCEL_URL}`]: () => jsonResponse(makeRun({ id: 'run-active', status: 'CANCELLED' }), 202),
    })
    const user = userEvent.setup()
    renderAgentRuns(sessionFor('reviewer'))

    const cancel = await screen.findByRole('button', { name: 'Cancel run run-active' })
    expect(screen.getByRole('heading', { name: 'Agent Runs' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel run run-done' })).not.toBeInTheDocument()

    await user.click(cancel)

    expect(await screen.findByText('Run cancelled')).toBeInTheDocument()
    const posts = callsTo(fetchMock, 'POST', CANCEL_URL)
    expect(posts).toHaveLength(1)
    expect(new Headers(posts[0]![1]?.headers).get('X-CSRF-Token')).toBe('csrf-reviewer')
    await waitFor(() => expect(callsTo(fetchMock, 'GET', RUNS_URL).length).toBeGreaterThanOrEqual(2))
  })

  it('shows the problem title when the run can no longer be cancelled', async () => {
    mockApi({
      [`GET ${RUNS_URL}`]: activeAndFinished,
      [`POST ${CANCEL_URL}`]: () => problemResponse(409, 'Run cannot be cancelled'),
    })
    const user = userEvent.setup()
    renderAgentRuns(sessionFor('admin'))

    await user.click(await screen.findByRole('button', { name: 'Cancel run run-active' }))

    expect(await screen.findByText('Run cannot be cancelled')).toBeInTheDocument()
  })

  it('hides Cancel from a user without blog.generate', async () => {
    mockApi({ [`GET ${RUNS_URL}`]: activeAndFinished })

    renderAgentRuns(sessionFor('viewer', ['blog.view', 'blog.agent_runs']))

    expect(await screen.findByText('PRODUCING')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cancel run/ })).not.toBeInTheDocument()
  })
})
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/routes/agent-runs-page.test.tsx`

Expected: FAIL with `Error: Failed to resolve import "@/routes/agent-runs-page" from "src/routes/agent-runs-page.test.tsx". Does the file exist?`

- [ ] **Step 16: Implement the Agent Runs page**

`frontend/src/routes/agent-runs-page.tsx`. The accessible name `Cancel run <id>` starts with the visible text "Cancel" (WCAG label-in-name), and each row gets a distinct name.

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { hasPermission } from '@/features/auth/permissions'
import { sessionQueryOptions } from '@/features/auth/session'
import {
  RUNS_QUERY_KEY,
  type RunOut,
  cancelRun,
  isTerminalRunStatus,
  runsQueryOptions,
} from '@/features/runs/api'
import { RunsTable } from '@/features/runs/runs-table'
import { problemMessage } from '@/lib/api'

const AGENT_RUNS_LIMIT = 50

export function AgentRunsPage() {
  const queryClient = useQueryClient()
  const { data: session } = useQuery(sessionQueryOptions)
  const runs = useQuery(runsQueryOptions(AGENT_RUNS_LIMIT))
  const canCancel = hasPermission(session?.user, 'blog.generate')

  const cancel = useMutation({
    mutationFn: cancelRun,
    onSuccess: async () => {
      toast.success('Run cancelled')
      await queryClient.invalidateQueries({ queryKey: RUNS_QUERY_KEY })
    },
    onError: (error) => {
      toast.error(problemMessage(error, 'Could not cancel the run'))
    },
  })

  const renderActions = canCancel
    ? (run: RunOut) =>
        isTerminalRunStatus(run.status) ? null : (
          <Button
            variant="outline"
            size="sm"
            aria-label={`Cancel run ${run.id}`}
            disabled={cancel.isPending}
            onClick={() => cancel.mutate(run.id)}
          >
            Cancel
          </Button>
        )
    : undefined

  const summary = runs.data
    ? `Showing ${runs.data.items.length} of ${runs.data.total} runs, newest first.`
    : 'Pipeline runs, newest first.'

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-heading text-2xl font-semibold">Agent Runs</h1>
        <p className="text-sm text-muted-foreground">{summary}</p>
      </div>
      <Card>
        <CardContent>
          <RunsTable
            runs={runs.data?.items}
            isPending={runs.isPending}
            isError={runs.isError}
            showRunId
            renderActions={renderActions}
          />
        </CardContent>
      </Card>
    </section>
  )
}
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/routes/agent-runs-page.test.tsx`

Expected: `✓ src/routes/agent-runs-page.test.tsx (3 tests)`, `Tests  3 passed (3)`.

- [ ] **Step 17: Write the failing router test**

`frontend/src/router.test.tsx` runs the real route tree in a memory router and covers five cases:
- the 401 → `/login?next=` redirect;
- every nav page rendering for an admin (the Phase 1 acceptance "every nav page renders");
- the Access denied page for a viewer on Settings, Review Queue and Agent Runs;
- the unknown-path redirect;
- sign-out through the Radix user menu with the CSRF header.

```tsx
import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { NAV_ITEMS } from '@/app/nav'
import type { SessionResponse } from '@/features/auth/session'
import { getCsrfToken, setCsrfToken } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { buildRoutes } from '@/router'
import {
  callsTo,
  jsonResponse,
  mockApi,
  problemResponse,
  renderRoutes,
  runsPage,
  sessionFor,
} from '@/test/helpers'

function mockBackend(session: SessionResponse | null) {
  return mockApi({
    'GET /api/auth/session': () =>
      session ? jsonResponse(session) : problemResponse(401, 'Not authenticated'),
    'POST /api/auth/logout': () => new Response(null, { status: 204 }),
    'GET /api/blog-agent/runs?limit=10': () => jsonResponse(runsPage([])),
    'GET /api/blog-agent/runs?limit=50': () => jsonResponse(runsPage([], 50)),
  })
}

function renderApp(path: string) {
  const queryClient = createQueryClient()
  return renderRoutes(buildRoutes(queryClient), { initialEntries: [path], queryClient })
}

async function go(router: ReturnType<typeof renderApp>['router'], path: string) {
  await act(async () => {
    await router.navigate(path)
  })
}

describe('router', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('sends a visitor without a session to /login and keeps the requested path in ?next=', async () => {
    mockBackend(null)

    const { router } = renderApp('/drafts?tab=1')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toBe('?next=%2Fdrafts%3Ftab%3D1')
  })

  it('renders every nav page for an admin', async () => {
    const fetchMock = mockBackend(sessionFor('admin'))

    const { router } = renderApp('/')

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    expect(getCsrfToken()).toBe('csrf-admin')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link')).toHaveLength(NAV_ITEMS.length)

    for (const item of NAV_ITEMS.filter((navItem) => navItem.path !== '/')) {
      await go(router, item.path)
      expect(await screen.findByRole('heading', { level: 1, name: item.label })).toBeInTheDocument()
      if (item.path !== '/agent-runs') {
        expect(screen.getByText('Arrives in a later phase.')).toBeInTheDocument()
      }
    }
    expect(callsTo(fetchMock, 'GET', '/api/auth/session')).toHaveLength(1)
  })

  it('shows Access denied when a viewer opens a page outside their role', async () => {
    mockBackend(sessionFor('viewer'))

    const { router } = renderApp('/settings')

    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link')).toHaveLength(8)
    expect(within(nav).queryByRole('link', { name: 'Settings' })).not.toBeInTheDocument()

    for (const path of ['/review', '/agent-runs']) {
      await go(router, path)
      expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument()
    }

    await go(router, '/topics')
    expect(await screen.findByRole('heading', { level: 1, name: 'Topics' })).toBeInTheDocument()
  })

  it('redirects unknown paths to the dashboard', async () => {
    mockBackend(sessionFor('viewer'))

    const { router } = renderApp('/no-such-page')

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('signs out from the user menu with the CSRF token and returns to /login', async () => {
    const fetchMock = mockBackend(sessionFor('editor'))
    const user = userEvent.setup()
    const { router } = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Test editor' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    const posts = callsTo(fetchMock, 'POST', '/api/auth/logout')
    expect(posts).toHaveLength(1)
    expect(new Headers(posts[0]![1]?.headers).get('X-CSRF-Token')).toBe('csrf-editor')
    expect(getCsrfToken()).toBeNull()
  })
})
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/router.test.tsx`

Expected: FAIL with `Error: Failed to resolve import "@/router" from "src/router.test.tsx". Does the file exist?`

- [ ] **Step 18: Implement the shell pages, the permission gate, the layout, the router and the entry point**

`frontend/src/routes/placeholder-page.tsx`:

```tsx
type PlaceholderPageProps = {
  title: string
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section className="flex flex-col gap-2">
      <h1 className="font-heading text-2xl font-semibold">{title}</h1>
      <p className="text-sm text-muted-foreground">Arrives in a later phase.</p>
    </section>
  )
}
```

`frontend/src/routes/forbidden-page.tsx`:

```tsx
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

export function ForbiddenPage() {
  return (
    <section className="flex flex-col items-start gap-3">
      <h1 className="font-heading text-2xl font-semibold">Access denied</h1>
      <p className="text-sm text-muted-foreground">
        Your role does not include this page. Ask an admin if you need access.
      </p>
      <Button asChild variant="outline">
        <Link to="/">Back to dashboard</Link>
      </Button>
    </section>
  )
}
```

`frontend/src/routes/require-permission.tsx`:

```tsx
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type Permission, hasPermission } from '@/features/auth/permissions'
import { sessionQueryOptions } from '@/features/auth/session'
import { ForbiddenPage } from '@/routes/forbidden-page'

type RequirePermissionProps = {
  permission: Permission
  children: ReactNode
}

// UI gate for pages opened directly by URL. The API enforces the same permission on its routes.
export function RequirePermission({ permission, children }: RequirePermissionProps) {
  const { data: session } = useQuery(sessionQueryOptions)
  if (!hasPermission(session?.user, permission)) {
    return <ForbiddenPage />
  }
  return children
}
```

`frontend/src/routes/app-layout.tsx`:
- The sidebar is built from `visibleNavItems`. On small screens the same list opens in a `Sheet`, which is not in the DOM while closed.
- The header user menu shows the email and role and offers Sign out.
- Icons are pre-built elements in a module-level map rather than component references chosen during render. This keeps `eslint-plugin-react-hooks` 7 happy.

```tsx
import { type ReactNode, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActivityIcon,
  CalendarDaysIcon,
  ClipboardCheckIcon,
  FileTextIcon,
  FlaskConicalIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  LightbulbIcon,
  MenuIcon,
  SendIcon,
  SettingsIcon,
  TagsIcon,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { type NavItem, visibleNavItems } from '@/app/nav'
import { logout, sessionQueryOptions } from '@/features/auth/session'
import { cn } from '@/lib/utils'

const ICON_CLASS = 'size-4'

const NAV_ICONS: Record<string, ReactNode> = {
  '/': <LayoutDashboardIcon className={ICON_CLASS} aria-hidden="true" />,
  '/ideas': <LightbulbIcon className={ICON_CLASS} aria-hidden="true" />,
  '/research': <FlaskConicalIcon className={ICON_CLASS} aria-hidden="true" />,
  '/drafts': <FileTextIcon className={ICON_CLASS} aria-hidden="true" />,
  '/review': <ClipboardCheckIcon className={ICON_CLASS} aria-hidden="true" />,
  '/published': <SendIcon className={ICON_CLASS} aria-hidden="true" />,
  '/topics': <TagsIcon className={ICON_CLASS} aria-hidden="true" />,
  '/calendar': <CalendarDaysIcon className={ICON_CLASS} aria-hidden="true" />,
  '/sources': <LibraryIcon className={ICON_CLASS} aria-hidden="true" />,
  '/settings': <SettingsIcon className={ICON_CLASS} aria-hidden="true" />,
  '/agent-runs': <ActivityIcon className={ICON_CLASS} aria-hidden="true" />,
}

type NavListProps = {
  items: NavItem[]
  onNavigate?: () => void
}

function NavList({ items, onNavigate }: NavListProps) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {items.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          end={item.path === '/'}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
              isActive
                ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
            )
          }
        >
          {NAV_ICONS[item.path]}
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

// The route loader (see router.tsx) guarantees a session is cached before this renders.
export function AppLayout() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: session } = useQuery(sessionQueryOptions)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const items = visibleNavItems(session?.user)

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // The server session may already be gone (401); signing out locally is still correct.
    }
    queryClient.clear()
    await navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex h-14 items-center justify-between gap-2 border-b px-4">
        <div className="flex items-center gap-2">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
                <MenuIcon />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64">
              <SheetHeader>
                <SheetTitle>MDCopilot Blog</SheetTitle>
                <SheetDescription>Go to a page.</SheetDescription>
              </SheetHeader>
              <div className="px-4">
                <NavList items={items} onNavigate={() => setMobileNavOpen(false)} />
              </div>
            </SheetContent>
          </Sheet>
          <span className="font-heading font-semibold">MDCopilot Blog</span>
        </div>
        {session ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">{session.user.displayName}</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="flex flex-col gap-0.5">
                <span className="truncate text-foreground">{session.user.email}</span>
                <span className="capitalize">{session.user.role}</span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => void handleLogout()}>Sign out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Skeleton className="h-8 w-32" />
        )}
      </header>
      <div className="flex flex-1">
        <aside className="hidden w-60 shrink-0 border-r bg-sidebar p-3 md:block">
          <NavList items={items} />
        </aside>
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

`frontend/src/router.tsx`:
- `requireSession` is the verified loader: on a 401 it throws `redirect('/login?next=...')`.
- Every nav path is wrapped in `RequirePermission`.
- The catch-all uses `<Navigate>` rather than a loader redirect. With a loader, React Router logs "Matched leaf route ... does not have an element" and "No `HydrateFallback` element provided".
- The file does not create the browser router; `main.tsx` does. Importing the file in tests therefore starts no navigation or fetch.

```tsx
import type { ReactNode } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { type LoaderFunctionArgs, Navigate, type RouteObject, redirect } from 'react-router'
import { NAV_ITEMS, type NavItem } from '@/app/nav'
import { sessionQueryOptions } from '@/features/auth/session'
import { ApiError } from '@/lib/api'
import { AgentRunsPage } from '@/routes/agent-runs-page'
import { AppLayout } from '@/routes/app-layout'
import { DashboardPage } from '@/routes/dashboard-page'
import { LoginPage } from '@/routes/login-page'
import { PlaceholderPage } from '@/routes/placeholder-page'
import { RequirePermission } from '@/routes/require-permission'

export function requireSession(client: QueryClient) {
  return async ({ request }: LoaderFunctionArgs) => {
    try {
      await client.ensureQueryData(sessionQueryOptions)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        const url = new URL(request.url)
        throw redirect(`/login?next=${encodeURIComponent(url.pathname + url.search)}`)
      }
      throw error
    }
    return null
  }
}

function pageFor(item: NavItem): ReactNode {
  switch (item.path) {
    case '/':
      return <DashboardPage />
    case '/agent-runs':
      return <AgentRunsPage />
    default:
      return <PlaceholderPage title={item.label} />
  }
}

function navRoute(item: NavItem): RouteObject {
  const element = <RequirePermission permission={item.permission}>{pageFor(item)}</RequirePermission>
  return item.path === '/' ? { index: true, element } : { path: item.path.slice(1), element }
}

export function buildRoutes(client: QueryClient): RouteObject[] {
  return [
    { path: '/login', element: <LoginPage /> },
    {
      path: '/',
      loader: requireSession(client),
      element: <AppLayout />,
      hydrateFallbackElement: <p className="p-4 text-muted-foreground">Loading...</p>,
      children: NAV_ITEMS.map(navRoute),
    },
    // Unknown paths go to the dashboard; the session loader then applies.
    { path: '*', element: <Navigate to="/" replace /> },
  ]
}
```

`frontend/src/main.tsx` replaces the scaffold file. `RouterProvider` comes from `react-router/dom`, as in the v8 Data Mode docs.

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { Toaster } from '@/components/ui/sonner'
import { queryClient } from '@/lib/query-client'
import { buildRoutes } from '@/router'
import './index.css'

const router = createBrowserRouter(buildRoutes(queryClient))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster richColors />
    </QueryClientProvider>
  </StrictMode>,
)
```

Run: `docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run src/router.test.tsx`

Expected: `✓ src/router.test.tsx (5 tests)`, `Tests  5 passed (5)`, with no React Router warnings on stderr.

- [ ] **Step 19: Run the full frontend gate (build, tests, lint, typecheck)**

```bash
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npm run build
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npx vitest run
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npm run lint
docker run --rm -v "$PWD/frontend:/app" -w /app node:24-alpine npm run typecheck
```

Expected, each command exiting 0:
- **build:** `tsc -b && vite build`, then `vite v8.3.0 building client environment for production...` and `✓ 2127 modules transformed.`.
  - Outputs: `dist/index.html`, 5 `geist-*.woff2` files, `dist/assets/index-*.css` about 47 kB, `dist/assets/index-*.js` about 530 kB (about 167 kB gzip).
  - The warning `(!) Some chunks are larger than 500 kB after minification` is expected and is not an error. Code splitting is deferred; the Vite 8 option is `build.rolldownOptions`.
- **vitest:** 6 files pass, 35 tests: `api.test.ts (7)`, `nav.test.ts (7)`, `agent-runs-page.test.tsx (3)`, `dashboard-page.test.tsx (5)`, `login-page.test.tsx (8)`, `router.test.tsx (5)`. Summary: `Test Files  6 passed (6)`, `Tests  35 passed (35)`.
- **lint:** `eslint .` prints no findings.
- **typecheck:** `tsc -b` prints nothing.

If lint reports `react-refresh/only-export-components` on a new `.tsx` file, check for a capitalised (PascalCase or SCREAMING_CASE) exported non-component, and rename it or move it to a `.ts` file. Do not relax the rule beyond `src/components/ui/**`.

- [ ] **Step 20: Add the Docker build files**

`frontend/.dockerignore`. It keeps host `node_modules`/`dist` out, so `COPY . .` cannot overwrite the image's `npm ci` result.

```text
node_modules
dist
.vitest
coverage
*.local
.env
.env.*
!.env.example
.git
.DS_Store
npm-debug.log*
Dockerfile
.dockerignore
```

`frontend/Dockerfile`. The `build` stage runs only for `--target prod`.

```dockerfile
# syntax=docker/dockerfile:1
# Frontend image. Targets:
#   dev  -> Vite dev server on :5173 (compose bind-mounts the source over /app,
#           plus an anonymous volume on /app/node_modules so the image's deps stay visible)
#   prod -> nginx serving the static build on :8080 and proxying /api/ to api:8000
ARG NODE_IMAGE=node:24-alpine
ARG NGINX_IMAGE=nginx:1.30-alpine

# ---------- stage 1: node (dependencies + source; also the dev target) ----------
FROM ${NODE_IMAGE} AS dev
WORKDIR /app
ENV CI=true
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# Production bundle (type-check + vite build). Only built when --target prod is requested.
FROM dev AS build
RUN npm run build

# ---------- stage 2: nginx (prod target) ----------
FROM ${NGINX_IMAGE} AS prod
# The image entrypoint renders /etc/nginx/templates/*.template into /etc/nginx/conf.d/ with envsubst;
# NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 makes it export NGINX_LOCAL_RESOLVERS from /etc/resolv.conf.
ENV NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

# compose (dev) needs:  volumes: ["./frontend:/app", "/app/node_modules"]
```

`frontend/nginx/default.conf.template`. This is the research's corrected config. It differs from a static `conf.d` file in three ways, and together they let `nginx -t` and startup succeed without an `api` host:
- a runtime `resolver`;
- `zone`;
- `server api:8000 resolve`.

`add_header_inherit merge` keeps the server-level security headers in locations that set `Cache-Control`. `style-src` needs `'unsafe-inline'` for sonner and Radix scroll-lock.

```nginx
# mdcopilot-blog web (prod): serves the Vite SPA build and proxies /api/ to FastAPI.
# Installed as /etc/nginx/templates/default.conf.template. The nginx image entrypoint renders it with
# envsubst into /etc/nginx/conf.d/default.conf (inside http {}). Only defined env vars are replaced,
# so nginx variables such as $http_host stay as they are.

# Re-resolve "api" at runtime (Docker DNS / VPC DNS from /etc/resolv.conf) so nginx starts even when
# the api container is not up yet and follows it when compose recreates it with a new IP.
resolver ${NGINX_LOCAL_RESOLVERS} valid=10s ipv6=off;

upstream api_upstream {
    zone api_upstream 64k;
    server api:8000 resolve;
    keepalive 16;
}

# Keep the scheme the client used when a TLS-terminating load balancer sits in front.
map $http_x_forwarded_proto $forwarded_proto {
    default $http_x_forwarded_proto;
    ""      $scheme;
}

server {
    listen 8080;
    listen [::]:8080;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    server_tokens off;
    client_max_body_size 10m;
    charset utf-8;

    # --- compression ---------------------------------------------------------
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/javascript
        application/json
        application/xml
        application/manifest+json
        image/svg+xml;

    # --- security headers (inherited by every location via add_header_inherit) ---
    # Vite emits only external <script type="module" src=...>, so script-src needs no 'unsafe-inline'.
    # style-src needs 'unsafe-inline': sonner and react-remove-scroll (Radix Dialog/Sheet/DropdownMenu)
    # append <style> elements at runtime without a nonce.
    add_header_inherit merge;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
    add_header Cross-Origin-Opener-Policy "same-origin" always;
    # Browsers ignore HSTS on plain http; it takes effect once served over https.
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # --- API -------------------------------------------------------------------
    location /api/ {
        # No URI part on proxy_pass: the path is forwarded unchanged (/api/...).
        proxy_pass http://api_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        # $http_host keeps the port so FastAPI can compare Origin against Host.
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $forwarded_proto;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_connect_timeout 5s;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        add_header Cache-Control "no-store" always;
    }

    # --- hashed build assets -----------------------------------------------------
    location /assets/ {
        try_files $uri =404;
        access_log off;
        # No "always": a 404 for a missing asset must not be cached as immutable.
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # --- SPA shell: never cache ----------------------------------------------------
    location = /index.html {
        add_header Cache-Control "no-cache" always;
    }

    # --- history fallback ------------------------------------------------------------
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 21: Build both image targets and validate nginx**

```bash
docker build --target dev -t mdcopilot-blog-web:dev frontend
docker build --target prod -t mdcopilot-blog-web:prod frontend
docker run --rm mdcopilot-blog-web:prod nginx -t
```

Expected:
- **dev build:** exits 0. The log shows only `[dev 1/5]`…`[dev 5/5]`, with no `[build` lines, and `npm ci` completes. The image is about 614 MB.
- **prod build:** exits 0. The log shows `[build 1/1] RUN npm run build`, `[prod 2/3] COPY nginx/default.conf.template ...` and `[prod 3/3] COPY --from=build /app/dist ...`. The image is about 102 MB.
- **`nginx -t`:** exits 0 with `/docker-entrypoint.sh: Configuration complete; ready for start up`, `nginx: the configuration file /etc/nginx/nginx.conf syntax is ok` and `nginx: configuration file /etc/nginx/nginx.conf test is successful`. No `--add-host` is needed.

Smoke-check that the prod image starts without an `api` host and serves the SPA fallback. Then check that the dev image starts Vite and serves the titled shell.

```bash
docker run -d --name mdcopilot-blog-web-smoke mdcopilot-blog-web:prod
sleep 2
docker exec mdcopilot-blog-web-smoke sh -c 'wget -S -q -O /dev/null http://127.0.0.1:8080/drafts 2>&1 | grep -E "HTTP/|Cache-Control"; wget -S -q -O /dev/null http://127.0.0.1:8080/api/healthz 2>&1 | head -1'
docker rm -f mdcopilot-blog-web-smoke
docker run -d --name mdcopilot-blog-web-devsmoke mdcopilot-blog-web:dev
sleep 4
docker logs mdcopilot-blog-web-devsmoke 2>&1 | grep -E "VITE|Network"
docker exec mdcopilot-blog-web-devsmoke wget -q -O - http://localhost:5173/agent-runs | grep -o "<title>.*</title>"
docker rm -f mdcopilot-blog-web-devsmoke
```

Expected:
- **prod:** `HTTP/1.1 200 OK` with `Cache-Control: no-cache` (index.html via the history fallback), then `HTTP/1.1 502 Bad Gateway` for `/api/healthz` because no API is running here, while nginx keeps running.
- **dev:** `VITE v8.3.0  ready in … ms`, a `Network: http://172.x.x.x:5173/` line, and `<title>MDCopilot Blog</title>`.
- **Cleanup:** both containers are removed.

- [ ] **Step 22: Checkpoint: list the files changed in this task (no git)**

Tell the owner that the `pre:config-protection` hook was lifted only for the Step 3 write to `frontend/eslint.config.js`, and confirm it has been restored: the session no longer runs with `ECC_DISABLED_HOOKS=pre:config-protection`.

```bash
find frontend -path frontend/node_modules -prune -o -path frontend/dist -prune -o -type f -print | sort
```

Expected: exactly these 52 files. `frontend/node_modules/` and `frontend/dist/` also exist and are git- and docker-ignored.

```text
frontend/.dockerignore
frontend/.gitignore
frontend/Dockerfile
frontend/README.md
frontend/components.json
frontend/eslint.config.js
frontend/index.html
frontend/nginx/default.conf.template
frontend/package-lock.json
frontend/package.json
frontend/public/favicon.svg
frontend/src/app/nav.test.ts
frontend/src/app/nav.ts
frontend/src/components/ui/badge.tsx
frontend/src/components/ui/button.tsx
frontend/src/components/ui/card.tsx
frontend/src/components/ui/dropdown-menu.tsx
frontend/src/components/ui/input.tsx
frontend/src/components/ui/label.tsx
frontend/src/components/ui/separator.tsx
frontend/src/components/ui/sheet.tsx
frontend/src/components/ui/skeleton.tsx
frontend/src/components/ui/sonner.tsx
frontend/src/components/ui/table.tsx
frontend/src/features/auth/permissions.ts
frontend/src/features/auth/session.ts
frontend/src/features/runs/api.ts
frontend/src/features/runs/runs-table.tsx
frontend/src/index.css
frontend/src/lib/api.test.ts
frontend/src/lib/api.ts
frontend/src/lib/query-client.ts
frontend/src/lib/utils.ts
frontend/src/main.tsx
frontend/src/router.test.tsx
frontend/src/router.tsx
frontend/src/routes/agent-runs-page.test.tsx
frontend/src/routes/agent-runs-page.tsx
frontend/src/routes/app-layout.tsx
frontend/src/routes/dashboard-page.test.tsx
frontend/src/routes/dashboard-page.tsx
frontend/src/routes/forbidden-page.tsx
frontend/src/routes/login-page.test.tsx
frontend/src/routes/login-page.tsx
frontend/src/routes/placeholder-page.tsx
frontend/src/routes/require-permission.tsx
frontend/src/test/helpers.tsx
frontend/src/test/setup.ts
frontend/tsconfig.app.json
frontend/tsconfig.json
frontend/tsconfig.node.json
frontend/vite.config.ts
```

**Notes for Task 14 and reviewers**
- **Nav count.** The contract's test note said "viewer sees 9 items". The contract's own `NAV_ITEMS` table has 8 `blog.view` items out of 11 (3 are hidden: Review Queue, Settings, Agent Runs). This task tests 8, and 10 for reviewer and publisher.
- **Compose `web` service.**
  - The service must be named `web` (`server.allowedHosts: ['web','localhost']`; any other hostname gets 403) and must set `VITE_API_PROXY_TARGET: http://api:8000`.
  - It uses `volumes: [./frontend:/app, /app/node_modules]`, so the container uses the image's Linux `node_modules`.
  - After Task 14, `docker compose run --rm web npm test` runs the same 35 tests.
- **Session expiry during use.** No global 401 handler exists. After the 30-minute idle timeout, the pages still show the cached session: actions report "Not authenticated" and lists show "Could not load runs." A reload then redirects to `/login`. A global 401 → `/login` handler is left for a later phase.

---

### Task 14: Full stack, acceptance run, docs

**Files:**
- Modify (replace whole file): `compose.yaml`. Task 1 created it with only `db` and `tools`.
- Verify (normally unchanged): `backend/Dockerfile`. Task 1 already ships the final form, with an editable builder and a `runtime` stage that copies `src/`, `prompts/` and `fixtures/`. Step 6 checks it and replaces it only if the check fails; Step 7 builds and smoke-tests `runtime` for the first time.
- Create: `scripts/acceptance/phase1.sh` (executable)
- Create: `docs/blog-agent/LOCAL_DEVELOPMENT.md`
- Modify: `docs/blog-agent/ARCHITECTURE.md`:
  - §3 table rows and the bootstrap block;
  - §4 layout and layering rule;
  - §16 auth line;
  - §17 create-admin command;
  - §18 health sentence;
  - §6 run line, only if the owner allowed `WAITING_FOR_TOPIC → FAILED` in Task 4 Step 0 (Step 13j).
- Modify: `docs/blog-agent/IMPLEMENTATION_PLAN.md`: the status line, Phase 1 build bullets, the Spike S1 result line and a Phase 10 hardening bullet.
- Modify (comment only): `.env.example` line 27, the stale `app.cli` create-admin comment (Step 3). No variable changes; Step 3 proves none is missing, and adds one only if that check finds a gap.
- Not modified: `.env`. It is never opened or printed. Anything that must change there is an instruction for the owner. If it was copied from the template, it carries the same stale comment; that is cosmetic, and Step 19 tells the owner.
- Test: `scripts/acceptance/phase1.sh` is this task's test. It is written first and fails against the Task 1 compose file (Step 5), then passes against the full stack (Step 11).

**Relies on two Task 11 behaviours.** Step 11 passes only with these two behaviours. Task 11 as written already has both (its "Choices beyond the contract", items 5 and 6); Step 1 confirms them in the tree. They were verified by the Step 11 run (see below).
1. **`workflows/hello.py`, `echo_step`.** `await _mock_delay(rt.settings)` runs before `result = await rt.gateway.run(...)`: after the QUEUED→RESEARCHING check, still inside `track_step`, followed only by the `_stop_if_cancelled` check. `set_run_status(... TOPICS_READY ...)` comes after the call. A worker killed during the delay has therefore not called the gateway, and the resumed execution records the run's only `blog_llm_calls` row. With the old order (call, then delay), the killed execution records a call, the resumed one records another, and in Phase 2 that second call would be paid for twice.
2. **`workflows/tracking.py`, `track_step`.** After each `_close_step_row(...)` call it logs one line: `logger.info("step finished", extra={"step": step_name, "status": ..., "duration_ms": ..., "tries": ...})` on success, and `logger.warning(...)` with the same fields plus `error_class` on failure (`logger = logging.getLogger(__name__)`). The step functions bind `run_id`/`trace_id` first, so this line proves the Build bullet "structured JSON logs carrying `run_id` and `trace_id`".

**Deviations from the contract** (verified 2026-09-17; they need the owner's approval):
1. **`db` healthcheck** probes TCP (`pg_isready -h 127.0.0.1 -p 5432 …`), not the Unix socket. On a fresh volume, the image's temporary init server listens on the socket only. In a throwaway `pgvector/pgvector:pg16` start, the socket probe passed while TCP was still refused, and `migrate` connects over TCP with no retry. Task 1 uses the same probe.
2. **`db` environment.** `db` gets only `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` (interpolated from `.env`, defaults matching Settings), not `env_file: [.env]`, which would put every provider key and `SESSION_SECRET` into the database container (`docker inspect` shows them). Task 1 uses the same block.
3. **`db` image** is digest-pinned, `pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`, as ARCHITECTURE §3 says ("digest-pinned"). This digest is the multi-arch index behind the `pg16` tag on 2026-09-17 (`docker buildx imagetools inspect pgvector/pgvector:pg16`).
4. **`api` ignores proxy headers:** `--no-proxy-headers` instead of `--proxy-headers --forwarded-allow-ips "*"`.
   - **Why.** With `"*"`, uvicorn takes the client address from any caller's `X-Forwarded-For`, and the Vite proxy (`xfwd`) appends to what the browser sent. `app.login_attempts.ip` and the 20-failures-per-IP limit then use a client-chosen value.
   - **Effect.** The api now records the TCP peer: the web container for browser traffic, the Docker gateway for host `curl`. In local dev no real client address is visible either way. CSRF is unaffected, because `enforce_csrf` reads `X-Forwarded-Proto` from the headers itself.
   - **Rejected alternative.** A fixed subnet with `--forwarded-allow-ips <web's fixed IP>` was tried. `docker compose run --rm web …` then fails with `Address already in use` while `web` runs, because `run` copies the static address. The contract, the docs and this script all use that command.
   - **Production.** Phase 10 must trust only the production reverse proxy. Step 14e adds that to IMPLEMENTATION_PLAN.
5. **Healthcheck timings.** `interval`/`timeout`/`retries`/`start_period`/`start_interval` on db, api, worker and web; the contract gave test commands only.
6. **Acceptance also uses a browser.** Besides the `curlimages/curl` probe, `phase1.sh` runs Chromium from the Playwright image that ARCHITECTURE §3 pins (`mcr.microsoft.com/playwright:v1.63.0-noble`) on the compose network. The contract's Docs section mentions only the curl container.

**Interfaces:**
- **Consumes** (from Tasks 1–13, exact names):
  - **Compose and CLI:**
    - compose services `db`, `migrate`, `api`, `worker`, `web`, `tools`;
    - CLI `python -m mdcopilot_blog.cli migrate | create-admin --email --display-name [--password-env] | create-user --email --display-name --role --password-env`. Exit 2 means the password is under 12 characters or the email has no `@`; the reason goes to stderr and never contains the password. An existing user gives exit 0.
  - **Routes:**
    - `GET /healthz` → `{"status":"ok"}`;
    - `GET /readyz`;
    - `POST /api/auth/login` → `SessionResponse {user{id,email,displayName,role,permissions}, csrfToken}` plus a `Set-Cookie`;
    - `GET /api/auth/session`;
    - `POST /api/auth/logout` → 204;
    - `GET /api/admin/users`;
    - `PATCH /api/admin/users/{id}` with `{"isActive": false}`;
    - `GET /api/blog-agent/settings` → `SettingsView {mockMode, agentEnabled, schedulerEnabled, publishingEnabled, humanApprovalRequired, providers{<key>: {configured, preview}}}`;
    - `POST /api/blog-agent/runs` → 202 `RunOut {id, status, …}`;
    - `GET /api/blog-agent/runs?limit=`;
    - `GET /api/blog-agent/runs/{id}` → `RunDetail {status, attempts[], steps[{stepName, status, tries, …}]}`.
  - **Problem titles:**
    - "Not authenticated";
    - "Forbidden";
    - "Origin not allowed";
    - "Cross-site request blocked";
    - "CSRF token missing or invalid".
  - **CSRF rules** (`enforce_csrf`):
    - `Sec-Fetch-Site` must be same-origin when present;
    - `Origin` must equal `PUBLIC_APP_URL`, or `<x-forwarded-proto or scheme>://<Host>`;
    - the token must match, except on `/api/auth/login`.
  - **Workflow:**
    - step names `hello.open_attempt`, `hello.echo`, `hello.finish`;
    - `open_attempt_step` sets the run to RESEARCHING, then waits its mock delay;
    - `echo_step` waits its mock delay **before** `gateway.run`, then sets TOPICS_READY (Task 11; see above);
    - `finish_step` sets the run to SUCCEEDED **before** its mock delay;
    - `track_step` upserts on `(dbos_workflow_id, dbos_step_id)` with `tries += 1`, and logs `step finished` (Task 11; see above);
    - `JsonFormatter` writes `"run_id": "<id>"` and `"trace_id": "<32 hex>"` (Python `json.dumps` spacing) on lines logged after `bind_log_context`.
  - **Tables:**
    - `app.blog_llm_calls(run_id, agent_run_id, status)`;
    - `app.blog_agent_runs(id, step_name)`;
    - `app.users(email, is_active)`;
    - `app.login_attempts(email, ip)`: one row per login, successful or not; `ip` is `request.client.host`;
    - `dbos.workflow_schedules(schedule_name, status)`. Columns were checked on dbos 3.0.0; `status` is `ACTIVE` or `PAUSED`.
  - **Worker:**
    - `HEARTBEAT_FILE = /tmp/worker-heartbeat`, touched every 10 s;
    - `WORKER_EXECUTOR_ID` from compose;
    - `APP_VERSION` from `.env`.
  - **Backend image:** `backend/Dockerfile` from Task 1, with targets `dev` and `runtime`.
  - **Resource paths:** `default_prompt_root()` and `FixtureRegistry.default()` resolve `backend/prompts` and `backend/fixtures` as `Path(__file__).resolve().parents[3] / …`.
  - **Frontend:** npm scripts `test`, `lint`, `typecheck` and `build`; Vite `allowedHosts: ['web','localhost']`; the proxy uses `changeOrigin:false, xfwd:true`.
  - **Frontend DOM** (Task 13), which the browser check drives:
    - `/login` has inputs labelled `Email` and `Password`, a `Sign in` button and an `h1` "Sign in";
    - the layout has one `nav` with `aria-label="Main"` (1280 px wide) holding one link per visible nav item, labelled as in `NAV_ITEMS`;
    - every nav page has exactly one `h1`, equal to its nav label (Dashboard, the placeholders, Agent Runs);
    - Dashboard has a `Generate today's blog` button that POSTs `/api/blog-agent/runs`;
    - the header user menu is a button showing the user's display name, with a `Sign out` menu item;
    - a protected path without a session redirects to `/login`.
- **Produces:**
  - the final `compose.yaml` (project `mdcopilot-blog`, default network `mdcopilot-blog_default`);
  - `scripts/acceptance/phase1.sh`:
    - it exits 0 and prints `PHASE 1 ACCEPTANCE: PASS (<n> checks, <w> warnings)`;
    - env toggle `SKIP_SUITES=1`;
    - it creates the accounts `acceptance-{admin,viewer}-<timestamp>@example.test`, which are deactivated at the end;
    - it runs `curlimages/curl:8.22.0` and `mcr.microsoft.com/playwright:v1.63.0-noble` containers on the compose network;
  - `docs/blog-agent/LOCAL_DEVELOPMENT.md`.

**How this task's code was verified (2026-09-17, throwaway containers and compose projects with the `p1p-` prefix, all removed afterwards):**
- **Against the real Tasks 1–13 code.** The code blocks of Tasks 1–13 were assembled into one tree, and this task's `compose.yaml` and `phase1.sh` were run on it.
  - Host: macOS `/bin/bash` 3.2.57, Docker Engine 29.8.0, Compose v5.5.1.
  - The tree included the two Task 11 behaviours listed above (applied by hand then; Task 11 now contains them). The project name, image names and host ports were changed for the throwaway project.
  - A copy of the owner's `.env` was used and never printed.
  - Results:
    - **Full run:** `PHASE 1 ACCEPTANCE: PASS (83 checks, 0 warnings)`, with `pytest: 1122 passed` and `vitest: Test Files 6 passed (6); Tests 31 passed (31)`. Those suite counts predate later additions (Task 3's 13th logging test, Task 11's 7 review tests, Task 13's 4 extra login-page tests); the plan as written gives `1130 passed` and `Tests 35 passed (35)`. The script does not check the numbers, only that both suites pass, so the check count stays 83.
    - **Second run on the same stack** with `SKIP_SUITES=1`: `PASS (79 checks, 1 warnings)`.
    - **Old `echo_step` order** (gateway call before the delay): the run failed at the kill stage with `run … is TOPICS_READY right after the kill, expected RESEARCHING`, and the trap restored the worker delay to 0.
    - **Task 1's compose file:** the run failed as Step 5 shows, with 4 checks passed.
  - `app.login_attempts` held only Docker peer addresses (the gateway for host curl, the web container for proxied and browser logins, `127.0.0.1` for the in-container bootstrap check), never the forged `203.0.113.7`.
  - `docker inspect` of `db` listed only the `POSTGRES_*` variables from `.env`.
  - **Earlier revision of this task** (`--forwarded-allow-ips "*"`, and `echo_step` calling the gateway before its delay): the same tree passed with 62 checks, and `blog_llm_calls` had 2 rows for the killed run.
- **Secrets-stage branches**, run in bash with crafted log files:
  - a benign `name='Task-6'` line gives a WARN with masked context;
  - 40 benign lines still print only 10 context lines, and the `head` pipe does not abort the script;
  - a `sk-proj-…` string of 20 characters fails, and its context prints as `sk-****`;
  - a clean log passes.
- **Checked separately:**
  - `shellcheck v0.11.0 -S style` is clean;
  - the CLI exits 2 with `--email must be an email address, got 'not-an-email'` for a bad email;
  - the doc edits in Steps 13–14 were applied to copies of the two documents with the assembly's applier;
  - the Step 12 link check and the Step 15 greps give the expected output.
- **`db` healthcheck.** In a fresh `pgvector/pgvector:pg16` container probed every 20 ms, the socket probe (`pg_isready -U … -d …`) returned ready while the TCP probe (`-h 127.0.0.1 -p 5432`) still returned "no response". After that, both were ready.
- **Rejected: a fixed-subnet network with the web container's IP as the only trusted proxy.**
  - `docker compose run --rm web …` failed with `failed to set up container networking: Address already in use` while `web` ran.
  - Changing the network config under running containers made `docker compose run --rm tools …` fail with `network … has active endpoints`.
- **Compose behaviour verified on Compose v5.5.1:**
  - `docker compose up -d --wait` returns 0 when `migrate` exits 0 under `service_completed_successfully`;
  - `up -d --no-deps --force-recreate --wait api worker` gives fresh containers, so their logs start empty;
  - `docker compose exec/run -e NAME` passes a host variable by name;
  - `kill` followed by `up -d --no-deps worker` restarts the same container;
  - changing `BLOG_AGENT_MOCK_STEP_DELAY_SECONDS` in the shell recreates the worker;
  - the heartbeat healthcheck works under dash;
  - busybox `wget http://127.0.0.1:5173/` works against the Vite dev server;
  - the Vite proxy forwards a foreign `Origin` and `Sec-Fetch-Site: cross-site` unchanged, with `Host: web:5173` and `x-forwarded-proto: http`;
  - `${POSTGRES_PASSWORD:?…}` interpolation feeds `db` from `.env`.
- **Browser.** The Playwright image `mcr.microsoft.com/playwright:v1.63.0-noble` runs Chromium headless as root with `playwright@1.63.0` installed inside the container. It reads the bind-mounted mode-600 script from the macOS temp folder.
  - At `http://web:5173` (a non-secure origin), Chromium kept the host-only `SameSite=Strict` cookie and sent `Origin: http://web:5173` with no `Sec-Fetch-Site`, and the CSRF checks accepted the POST.
- **curl 8.22 cookie jars** drop cookies for dotless hosts such as `web`. The in-network curl probe therefore copies the cookie from `Set-Cookie`. Host curl against `127.0.0.1` keeps using a normal cookie jar.
- **Runtime image.** The runtime stage (Task 1's design, and the fallback file in Step 6) was built and run on a minimal project with the same layout. It runs as uid 999 with no uv and no pytest, and `parents[3]` resolves to `/app`, so `/app/prompts` and `/app/fixtures/mock/llm` exist. A `--no-editable` install would resolve these under `/opt/venv/lib/`, which is why the runtime installs the project editable from `/app/src`.
- **dbos 3.0.0 has no `DBOS.pause_schedule_async`.** `await asyncio.to_thread(DBOS.pause_schedule, name)` works, and `dbos.workflow_schedules.status` then reads `PAUSED`. This is Task 11's fallback branch.

**Behaviour the acceptance run asserts** (and why):
- **Kill during `hello.echo`, then resume:**
  - right after the kill, the run is still RESEARCHING, `hello.echo` is RUNNING, and the run has no `blog_llm_calls` row: the kill landed in the mock delay, before the gateway call;
  - after the resume, `hello.open_attempt` and `hello.finish` have `tries=1` and `hello.echo` has `tries=2`;
  - the run has exactly one attempt;
  - `blog_llm_calls` for the run has exactly 1 row, `ok`, on the `hello.echo` step row. A resumed step must not repeat a gateway call that the killed execution never made.
- **Wait for step rows to finish.** After a run reports SUCCEEDED, the script waits until no step row is still RUNNING before it checks steps, because `finish_step` sets SUCCEEDED before its mock delay.
- **Structured logs.** After the first run, the worker's JSON logs contain a line with that run's `run_id` and its `trace_id` (from `GET /api/blog-agent/runs/{id}`).
- **Client address.** Every login sends a forged `X-Forwarded-For: 203.0.113.7`, directly and through the Vite proxy. `app.login_attempts` must record the TCP peer for all of them, never the forged value.
- **A real browser.** Chromium, in the Playwright container on the compose network, opens `http://web:5173`:
  - it signs in as the throwaway admin;
  - it checks the 11 sidebar links and each page's heading;
  - it presses "Generate today's blog", and the POST must return 202, which proves browser-made requests pass the CSRF checks;
  - it signs out.

  The bootstrap admin's own login is checked through the API inside the api container, so the script never reads that password.
- **Secrets in logs.** These checks read only this run's api and worker logs, because the script recreates both containers first.
  - **Hard check.** No configured secret value of 12 or more characters may appear in the logs (provider keys, `SESSION_SECRET`, database and admin passwords, and the two generated passwords). The comparison runs inside the api container, so the values never leave it.
  - **The spec's literal `grep -E 'sk-|AIza'`.** If it matches, the script prints the masked context. It fails when a match is key-shaped, and otherwise records a WARN. Ordinary text such as an asyncio `Task-6` name contains `sk-`.
- **Healthcheck timings.** `compose.yaml` adds `interval`/`timeout`/`retries`/`start_period`/`start_interval` to the healthchecks, which the contract gave as test commands only. With these, `--wait` finishes in seconds rather than after the 30 s default first probe. `start_interval` needs Docker Engine 25+.

- [ ] **Step 1: Confirm Tasks 1–13 are in place**

Run:

```bash
ls backend/src/mdcopilot_blog/workflows/hello.py backend/src/mdcopilot_blog/api/routers/runs.py backend/src/mdcopilot_blog/cli.py frontend/package.json frontend/Dockerfile frontend/vite.config.ts
docker compose run --rm tools pytest -q
```

Expected:
- all six paths are listed;
- pytest ends with `1130 passed` and nothing failed or errored. Step 16 row 3 has the per-task breakdown.

If any file is missing, finish the task whose **Files** list names it first. Also confirm that the two Task 11 behaviours listed under **Relies on two Task 11 behaviours** are in place:

```bash
grep -n -A3 'await _mock_delay(rt.settings)' backend/src/mdcopilot_blog/workflows/hello.py | grep -c 'result = await rt.gateway.run('
grep -cE '^ +"step finished",$' backend/src/mdcopilot_blog/workflows/tracking.py
```

Expected:
- the first command prints `1`: in `echo_step`, the gateway call comes at most three lines after the mock delay (only the `_stop_if_cancelled` check sits between them). `0` means the old order (call, then delay);
- the second command prints `2`: the `"step finished"` message of the `logger.warning(...)` call and of the `logger.info(...)` call. The docstring's mention of "step finished" does not match this pattern.

- [ ] **Step 2: Check `.env` has what Phase 1 needs, without printing values**

Run:

```bash
docker compose run --rm --no-deps tools sh -c '
  for v in SESSION_SECRET POSTGRES_PASSWORD BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_PASSWORD; do
    eval "val=\${$v:-}"
    if [ -n "$val" ]; then state="set (${#val} characters)"; else state="MISSING"; fi
    printf "%-26s %s\n" "$v" "$state"
  done
  [ "${SESSION_SECRET:-}" = change-me ] && echo "SESSION_SECRET still has the template value"
  [ "${POSTGRES_PASSWORD:-}" = change-me ] && echo "POSTGRES_PASSWORD still has the template value"
  true
'
```

Expected:
- all four lines say `set`;
- `SESSION_SECRET` has at least 32 characters;
- `BOOTSTRAP_ADMIN_PASSWORD` has at least 12 characters;
- no "template value" lines.

**If not, stop and hand this to the owner.** Do not open or edit `.env` yourself. The instruction for the owner:
1. Open `.env` in an editor and set the missing values:
   - `SESSION_SECRET` = the output of `openssl rand -hex 32`;
   - `BOOTSTRAP_ADMIN_EMAIL` = your login email;
   - `BOOTSTRAP_ADMIN_PASSWORD` = at least 12 characters.
2. `POSTGRES_PASSWORD`: keep the value the `blog_pgdata` volume was created with in Task 1. Changing it needs a volume reset, which only you can approve.
3. Save the file and keep it at mode 600 (`chmod 600 .env`).

- [ ] **Step 3: Check that `.env.example` lists every setting**

Run:

```bash
docker compose run --rm --no-deps -v "$PWD/.env.example:/env.example:ro" tools python -c '
import os
from pathlib import Path

from mdcopilot_blog.settings import Settings

aliases = sorted({f.validation_alias for f in Settings.model_fields.values() if isinstance(f.validation_alias, str)})
example = set()
for line in Path("/env.example").read_text().splitlines():
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        example.add(s.split("=", 1)[0].strip())
compose_only = {"WORKER_EXECUTOR_ID"}
missing = [a for a in aliases if a not in example and a not in compose_only]
unset = [a for a in aliases if a not in os.environ and a not in compose_only]
print("Settings fields with an env name:", len(aliases))
print("missing from .env.example:", ", ".join(missing) or "none")
print("not set in .env (defaults apply):", ", ".join(unset) or "none")
'
```

Expected: `missing from .env.example: none`. The script prints variable names only, never values; this check was verified on pydantic 2.13.5 and pydantic-settings 2.15.0.

**Decision rule.**
- **If names are listed as missing:** add one line per name to `.env.example`, in the matching section, with the default from the contract's Settings table. Tell the owner to add the same names to `.env` only if they want a non-default value.
- **"not set in .env" lines** are informational; defaults apply.

**Then fix the stale create-admin comment** in `.env.example` (a comment-only edit; no variable changes). The module `app.cli` does not exist, and the old command lacks the required `--email`/`--display-name`. Replace this line (line 27):

```text
# First admin account, created with: docker compose run --rm api python -m app.cli create-admin
```

with:

```text
# First admin account, created with: docker compose exec api sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'
```

Check:

```bash
grep -n 'create-admin' .env.example
```

Expected: exactly one line, `27:# First admin account, created with: docker compose exec api sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'`.

- [ ] **Step 4: Write the acceptance script (this task's test)**

Create `scripts/acceptance/phase1.sh`:

```bash
#!/usr/bin/env bash
# shellcheck disable=SC2016  # jq filters reference $variables inside single quotes on purpose
# Phase 1 acceptance run for mdcopilot-blog (docs/blog-agent/IMPLEMENTATION_PLAN.md, Phase 1 "Acceptance").
#
# Host tools: docker (with compose), curl, openssl, and jq. A pinned jq container is used if jq is missing.
# Never reads or prints .env. The two throwaway accounts get passwords generated here. Those
# passwords live only in environment variables and are passed to containers by variable name.
#
# Usage (from anywhere):
#   scripts/acceptance/phase1.sh                 # full run
#   SKIP_SUITES=1 scripts/acceptance/phase1.sh   # skip pytest / vitest / lint / build (quicker re-run)
#
# Side effects:
#   - builds images and starts the stack (docker compose up -d --wait), then recreates api and worker
#     so the log checks see only this run's logs
#   - creates 2 users (acceptance-*-<timestamp>@example.test) and deactivates them at the end
#   - creates 4 mock runs (one of them from a real Chromium browser)
#   - runs throwaway curl and Playwright containers on the compose network; the Playwright container
#     installs playwright@1.63.0 from the npm registry inside itself
#   - recreates the worker twice: once with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=15, once back at 0
#   - kills the worker once
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CURL_IMAGE="curlimages/curl:8.22.0"
JQ_IMAGE="ghcr.io/jqlang/jq:1.8.1"
BROWSER_IMAGE="mcr.microsoft.com/playwright:v1.63.0-noble"
PLAYWRIGHT_NPM="playwright@1.63.0"
KILL_DELAY_SECONDS=15
SPOOF_IP="203.0.113.7"
RUN_TAG="$(date +%Y%m%d%H%M%S)"
P1_ADMIN_EMAIL="acceptance-admin-${RUN_TAG}@example.test"
P1_VIEWER_EMAIL="acceptance-viewer-${RUN_TAG}@example.test"
export P1_ADMIN_EMAIL P1_VIEWER_EMAIL

PASS_COUNT=0
WARN_COUNT=0
DELAY_CHANGED=0
API=""
WEB=""

TMPD="$(mktemp -d "${TMPDIR:-/tmp}/mdcb-phase1.XXXXXX")"
chmod 700 "$TMPD"
umask 077

step() { printf '\n==> %s\n' "$*"; }
ok() { PASS_COUNT=$((PASS_COUNT + 1)); printf '  PASS  %s\n' "$*"; }
info() { printf '  ....  %s\n' "$*"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); printf '  WARN  %s\n' "$*"; }
fail() { printf '  FAIL  %s\n' "$*" >&2; exit 1; }

# Mask anything that looks like a DB URL password or a provider key before it reaches the terminal.
mask() { sed -E -e 's#(postgres(ql)?(\+psycopg)?://[^:/@ ]+:)[^@ ]*@#\1***@#g' -e 's/(sk-|AIza)[A-Za-z0-9_-]{4,}/\1****/g'; }

# Remove terminal colour codes (portable across BSD and GNU sed).
strip_ansi() { sed "s/$(printf '\033')\\[[0-9;]*m//g"; }

if command -v jq >/dev/null 2>&1; then
  jqr() { jq "$@"; }
else
  jqr() { docker run --rm -i "$JQ_IMAGE" "$@"; }
fi

# Run SQL in the db container as the app's own role (local socket, no password).
sql() {
  docker compose exec -T db sh -c 'psql -X -q -v ON_ERROR_STOP=1 -At -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<<"$1"
}

snapshot_logs() {
  docker compose logs --no-color --timestamps api worker >>"$TMPD/logs.txt" 2>&1 || true
}

cleanup() {
  local status=$?
  set +e
  if [ "$DELAY_CHANGED" = 1 ]; then
    info "restoring BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0 on the worker"
    if ! BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0 docker compose up -d --no-deps --wait worker >/dev/null 2>&1; then
      printf '  WARN  could not restore the worker; run: docker compose up -d --no-deps worker\n' >&2
    fi
  fi
  if [ -n "$API" ]; then
    local who
    for who in admin viewer; do
      if [ -s "$TMPD/$who.jar" ]; then
        curl -sS -o /dev/null -b "$TMPD/$who.jar" -X POST -H "Origin: $API" -H "@$TMPD/$who.csrf" \
          "$API/api/auth/logout" >/dev/null 2>&1
      fi
    done
    # The API cannot deactivate the calling admin, so the throwaway accounts are closed in SQL.
    sql "update app.users set is_active = false where email like 'acceptance-%@example.test' and is_active" >/dev/null 2>&1
  fi
  rm -rf "$TMPD"
  unset P1_ADMIN_PASSWORD P1_VIEWER_PASSWORD
  echo
  if [ "$status" -eq 0 ]; then
    echo "PHASE 1 ACCEPTANCE: PASS (${PASS_COUNT} checks, ${WARN_COUNT} warnings)"
  else
    echo "PHASE 1 ACCEPTANCE: FAIL (${PASS_COUNT} checks passed before the failure)"
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# ---------------------------------------------------------------------------------------------
# HTTP helpers. Host calls go straight to the api port, so Origin is the api's own origin.
# A request's body is written to $TMPD/body and the HTTP status is printed.
# ---------------------------------------------------------------------------------------------
api_call() { # api_call <who> <method> <path> [json-body]
  local who="$1" method="$2" path="$3" body="${4-}"
  local args=(-sS -o "$TMPD/body" -w '%{http_code}' -b "$TMPD/$who.jar" -c "$TMPD/$who.jar" -X "$method" -H "Origin: $API")
  if [ -s "$TMPD/$who.csrf" ]; then args+=(-H "@$TMPD/$who.csrf"); fi
  if [ -n "$body" ]; then args+=(-H 'Content-Type: application/json' --data-binary "$body"); fi
  curl "${args[@]}" "$API$path"
}

body_snippet() { head -c 400 "$TMPD/body" | mask; }

expect_status() { # expect_status <label> <expected> <actual> [--quiet]
  if [ "$3" = "$2" ]; then
    ok "$1 (HTTP $3)"
  elif [ "${4-}" = "--quiet" ]; then
    fail "$1: expected HTTP $2, got $3"
  else
    fail "$1: expected HTTP $2, got $3; body: $(body_snippet)"
  fi
}

expect_problem() { # expect_problem <label> <expected-status> <actual-status> <expected-title>
  local title
  title="$(jqr -r '.title // empty' <"$TMPD/body" 2>/dev/null || true)"
  if [ "$3" = "$2" ] && [ "$title" = "$4" ]; then
    ok "$1 (HTTP $3, \"$title\")"
  else
    fail "$1: expected HTTP $2 \"$4\", got HTTP $3 \"$title\""
  fi
}

login() { # login <who> <email> <password-variable-name>
  # Every login also sends a forged X-Forwarded-For. The check after the CSRF probe proves that the api
  # records the TCP peer, not this header.
  local who="$1" email="$2" pw_var="$3" code
  : >"$TMPD/$who.jar"
  : >"$TMPD/$who.csrf"
  code="$(printf '{"email":"%s","password":"%s"}' "$email" "${!pw_var}" |
    curl -sS -o "$TMPD/body" -w '%{http_code}' -c "$TMPD/$who.jar" -H "Origin: $API" \
      -H "X-Forwarded-For: $SPOOF_IP" -H 'Content-Type: application/json' --data-binary @- "$API/api/auth/login")"
  expect_status "login as $who" 200 "$code"
  printf 'X-CSRF-Token: %s\n' "$(jqr -r '.csrfToken' <"$TMPD/body")" >"$TMPD/$who.csrf"
  jqr -r '.user.id' <"$TMPD/body" >"$TMPD/$who.id"
  [ "$(jqr -r '.user.role' <"$TMPD/body")" = "$who" ] || fail "login as $who: unexpected role in the session response"
}

require_uuid() { # require_uuid <label> <value>
  case "$2" in
    "" | *[!0-9a-f-]*) fail "$1: not a UUID: $2" ;;
  esac
}

create_run() { # create_run <who> -> prints the new run id (caller checks the status file)
  local code
  code="$(api_call "$1" POST /api/blog-agent/runs '{}')"
  printf '%s' "$code" >"$TMPD/create.status"
  jqr -r '.id // empty' <"$TMPD/body" 2>/dev/null || true
}

wait_for_run() { # wait_for_run <who> <run-id> <timeout-seconds>; leaves the detail in $TMPD/run.json
  local who="$1" run_id="$2" timeout="$3" start code status
  start="$(date +%s)"
  while :; do
    code="$(api_call "$who" GET "/api/blog-agent/runs/$run_id")"
    [ "$code" = 200 ] || fail "GET run $run_id returned HTTP $code"
    cp "$TMPD/body" "$TMPD/run.json"
    status="$(jqr -r '.status' <"$TMPD/run.json")"
    case "$status" in
      SUCCEEDED) return 0 ;;
      FAILED | CANCELLED)
        fail "run $run_id ended $status; steps: $(jqr -c '[.steps[] | {stepName, status, tries, error}]' <"$TMPD/run.json" | mask)"
        ;;
    esac
    if [ $(($(date +%s) - start)) -ge "$timeout" ]; then
      fail "run $run_id is still $status after ${timeout}s"
    fi
    sleep 1
  done
}

wait_for_step_running() { # wait_for_step_running <who> <run-id> <step-name> <timeout-seconds>
  local who="$1" run_id="$2" step_name="$3" timeout="$4" start code running status
  start="$(date +%s)"
  while :; do
    code="$(api_call "$who" GET "/api/blog-agent/runs/$run_id")"
    [ "$code" = 200 ] || fail "GET run $run_id returned HTTP $code"
    running="$(jqr -r --arg s "$step_name" '[.steps[] | select(.stepName == $s and .status == "RUNNING")] | length' <"$TMPD/body")"
    if [ "$running" -ge 1 ]; then
      return 0
    fi
    status="$(jqr -r '.status' <"$TMPD/body")"
    case "$status" in
      SUCCEEDED | FAILED | CANCELLED) fail "run $run_id reached $status before $step_name was seen RUNNING" ;;
    esac
    if [ $(($(date +%s) - start)) -ge "$timeout" ]; then
      fail "$step_name was not RUNNING within ${timeout}s (run status $status)"
    fi
    sleep 0.5
  done
}

wait_for_steps_settled() { # wait_for_steps_settled <who> <run-id> <timeout-seconds>; refreshes $TMPD/run.json
  # finish_step marks the run SUCCEEDED before its mock delay, so its step row can still be RUNNING.
  local who="$1" run_id="$2" timeout="$3" start code running
  start="$(date +%s)"
  while :; do
    code="$(api_call "$who" GET "/api/blog-agent/runs/$run_id")"
    [ "$code" = 200 ] || fail "GET run $run_id returned HTTP $code"
    cp "$TMPD/body" "$TMPD/run.json"
    running="$(jqr -r '[.steps[] | select(.status == "RUNNING")] | length' <"$TMPD/run.json")"
    if [ "$running" = 0 ]; then
      return 0
    fi
    if [ $(($(date +%s) - start)) -ge "$timeout" ]; then
      fail "run $run_id still has $running RUNNING step rows after ${timeout}s"
    fi
    sleep 1
  done
}

step_field() { # step_field <step-name> <field>  (reads $TMPD/run.json)
  jqr -r --arg s "$1" --arg f "$2" '[.steps[] | select(.stepName == $s)] | if length == 1 then .[0][$f] else "count=\(length)" end' <"$TMPD/run.json"
}

kv() { # kv <file> <key>: value of the first "key=value" line
  awk -v k="$2" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }' "$1"
}

# ---------------------------------------------------------------------------------------------
step "Preflight"
for tool in docker curl openssl; do
  command -v "$tool" >/dev/null 2>&1 || fail "$tool is not installed on the host"
done
docker compose version >/dev/null 2>&1 || fail "docker compose is not available"
[ -f compose.yaml ] || fail "compose.yaml not found in $ROOT_DIR"
[ -f .env ] || fail ".env not found (copy .env.example to .env and fill it in; see docs/blog-agent/LOCAL_DEVELOPMENT.md)"
ok "host tools, compose.yaml and .env present"

step "Build images"
if ! docker compose build >"$TMPD/build.log" 2>&1; then
  tail -n 40 "$TMPD/build.log" | mask
  fail "docker compose build failed"
fi
ok "docker compose build"

step "Check .env values without printing them"
if ! docker compose run --rm --no-deps -T tools sh -c '
  bad=0
  if [ "${#SESSION_SECRET}" -lt 32 ]; then echo "SESSION_SECRET must be at least 32 characters (openssl rand -hex 32)"; bad=1; fi
  case "${POSTGRES_PASSWORD:-}" in
    "" | change-me) echo "POSTGRES_PASSWORD must be set to a generated value (openssl rand -hex 24)"; bad=1 ;;
    *" "*) echo "POSTGRES_PASSWORD must not contain spaces"; bad=1 ;;
  esac
  if [ -z "${BOOTSTRAP_ADMIN_EMAIL:-}" ] || [ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    echo "BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be set (the acceptance run checks that admin can sign in)"; bad=1
  elif [ "${#BOOTSTRAP_ADMIN_PASSWORD}" -lt 12 ]; then
    echo "BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters"; bad=1
  fi
  lower() { printf %s "$1" | tr "[:upper:]" "[:lower:]"; }
  case "$(lower "${BLOG_AGENT_MOCK_MODE:-true}")" in
    true | 1 | yes | on) ;;
    *) echo "BLOG_AGENT_MOCK_MODE must be true in Phase 1 (real providers arrive in Phase 2)"; bad=1 ;;
  esac
  case "$(lower "${BLOG_AGENT_ENABLED:-true}")" in
    true | 1 | yes | on) ;;
    *) echo "BLOG_AGENT_ENABLED must be true for the acceptance run"; bad=1 ;;
  esac
  exit "$bad"
' >"$TMPD/envcheck.log" 2>&1; then
  grep -v -E '^ *(Volume|Network|Container) ' "$TMPD/envcheck.log" || true
  fail ".env needs the changes listed above"
fi
ok ".env: SESSION_SECRET length, POSTGRES_PASSWORD, bootstrap admin, mock mode and kill switch"

# ---------------------------------------------------------------------------------------------
step "Start the stack and wait for health"
if ! docker compose up -d --wait --wait-timeout 300 >"$TMPD/up.log" 2>&1; then
  tail -n 20 "$TMPD/up.log" | mask
  docker compose ps -a
  for svc in migrate api worker web; do
    echo "--- last log lines: $svc"
    docker compose logs --no-color --tail 30 "$svc" 2>&1 | mask
  done
  fail "docker compose up -d --wait did not reach a healthy stack"
fi
for svc in db api worker web; do
  health="$(docker compose ps --format '{{.Health}}' "$svc" 2>/dev/null || true)"
  [ "$health" = healthy ] || fail "$svc is '${health:-not running or not defined}', expected healthy"
  ok "$svc is healthy"
done
migrate_state="$(docker compose ps -a --format '{{.State}} {{.ExitCode}}' migrate 2>/dev/null || true)"
[ "$migrate_state" = "exited 0" ] || fail "migrate is '${migrate_state:-not defined}', expected 'exited 0'"
ok "migrate exited 0"
# Fresh api and worker containers: the log checks below then read only this run's logs, not lines left
# over from earlier sessions (for example a shutdown traceback from a `docker compose stop`).
if ! docker compose up -d --no-deps --force-recreate --wait --wait-timeout 300 api worker >"$TMPD/up.log" 2>&1; then
  tail -n 20 "$TMPD/up.log" | mask
  fail "api and worker did not come back healthy after being recreated"
fi
ok "api and worker recreated and healthy (the log checks see only this run)"
API="http://$(docker compose port api 8000)"
WEB="http://$(docker compose port web 5173)"
NETWORK="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$(docker compose ps -q web)" | head -n 1)"
[ -n "$NETWORK" ] || fail "could not find the compose network of the web container"
info "api $API, web $WEB, network $NETWORK"
code="$(curl -sS -o "$TMPD/body" -w '%{http_code}' "$API/readyz")"
expect_status "api /readyz" 200 "$code"

# ---------------------------------------------------------------------------------------------
if [ "${SKIP_SUITES:-0}" = 1 ]; then
  step "Test suites skipped (SKIP_SUITES=1)"
  warn "pytest, vitest, lint and build were not run"
else
  step "Backend test suite"
  if docker compose run --rm -T tools pytest -q >"$TMPD/pytest.log" 2>&1; then
    ok "pytest: $(grep -E '[0-9]+ passed' "$TMPD/pytest.log" | tail -n 1)"
  else
    tail -n 60 "$TMPD/pytest.log" | mask
    fail "pytest failed"
  fi

  step "Frontend checks"
  if docker compose run --rm -T -e NO_COLOR=1 web npm test >"$TMPD/vitest.log" 2>&1; then
    ok "vitest: $(strip_ansi <"$TMPD/vitest.log" | grep -E '(Test Files|Tests) +[0-9]+ passed' | tr -s ' ' | paste -s -d ';' -)"
  else
    tail -n 60 "$TMPD/vitest.log"
    fail "npm test failed"
  fi
  if docker compose run --rm -T web npm run lint >"$TMPD/lint.log" 2>&1; then
    ok "npm run lint"
  else
    tail -n 60 "$TMPD/lint.log"
    fail "npm run lint failed"
  fi
  if docker compose run --rm -T web npm run build >"$TMPD/webbuild.log" 2>&1; then
    ok "npm run build (tsc -b && vite build)"
  else
    tail -n 60 "$TMPD/webbuild.log"
    fail "npm run build failed"
  fi
fi

# ---------------------------------------------------------------------------------------------
step "Web dev server serves every nav route and proxies /api"
for path in / /login /ideas /research /drafts /review /published /topics /calendar /sources /settings /agent-runs; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "$WEB$path")"
  [ "$code" = 200 ] || fail "GET $WEB$path returned HTTP $code"
done
ok "12 routes return the SPA shell (HTTP 200)"
code="$(curl -sS -o "$TMPD/body" -w '%{http_code}' "$WEB/api/auth/session")"
expect_problem "GET /api/auth/session through the Vite proxy without a cookie" 401 "$code" "Not authenticated"

# ---------------------------------------------------------------------------------------------
step "Accounts via the CLI (passwords generated here, never printed)"
P1_ADMIN_PASSWORD="$(openssl rand -hex 24)"
P1_VIEWER_PASSWORD="$(openssl rand -hex 24)"
export P1_ADMIN_PASSWORD P1_VIEWER_PASSWORD
docker compose exec -T -e P1_ADMIN_PASSWORD api python -m mdcopilot_blog.cli create-admin \
  --email "$P1_ADMIN_EMAIL" --display-name "Acceptance Admin" --password-env P1_ADMIN_PASSWORD >"$TMPD/cli.log" 2>&1 ||
  { mask <"$TMPD/cli.log"; fail "create-admin failed"; }
ok "create-admin $P1_ADMIN_EMAIL"
docker compose exec -T -e P1_VIEWER_PASSWORD api python -m mdcopilot_blog.cli create-user \
  --email "$P1_VIEWER_EMAIL" --display-name "Acceptance Viewer" --role viewer --password-env P1_VIEWER_PASSWORD >"$TMPD/cli.log" 2>&1 ||
  { mask <"$TMPD/cli.log"; fail "create-user failed"; }
ok "create-user $P1_VIEWER_EMAIL (viewer)"

read -r -d '' BOOTSTRAP_LOGIN_PY <<'PY' || true
import json
import os
import urllib.error
import urllib.request

body = json.dumps(
    {"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"], "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"]}
).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/auth/login",
    data=body,
    method="POST",
    headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:8000"},
)
try:
    with urllib.request.urlopen(req) as resp:
        print(resp.status)
except urllib.error.HTTPError as exc:
    print(exc.code)
PY
set +e
docker compose exec -T api sh -c '
  if [ -z "${BOOTSTRAP_ADMIN_EMAIL:-}" ] || [ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then exit 3; fi
  python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner
' >"$TMPD/cli.log" 2>&1
boot_status=$?
set -e
case "$boot_status" in
  0)
    ok "bootstrap admin from .env exists (create-admin is idempotent)"
    boot_code="$(docker compose exec -T api python -c "$BOOTSTRAP_LOGIN_PY" 2>/dev/null | tail -n 1)"
    [ "$boot_code" = 200 ] || fail "bootstrap admin login returned HTTP $boot_code (the account exists, but BOOTSTRAP_ADMIN_PASSWORD does not match it)"
    ok "bootstrap admin can log in (HTTP 200; credentials stayed inside the api container)"
    ;;
  3) fail "acceptance requires BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD in .env (see LOCAL_DEVELOPMENT.md section 2)" ;;
  2)
    mask <"$TMPD/cli.log"
    fail "create-admin refused BOOTSTRAP_ADMIN_EMAIL/BOOTSTRAP_ADMIN_PASSWORD (reason above: password under 12 characters or email without @)"
    ;;
  *)
    mask <"$TMPD/cli.log"
    fail "create-admin for the bootstrap admin failed (exit $boot_status)"
    ;;
esac

# ---------------------------------------------------------------------------------------------
step "Login with curl cookie jars"
login admin "$P1_ADMIN_EMAIL" P1_ADMIN_PASSWORD
login viewer "$P1_VIEWER_EMAIL" P1_VIEWER_PASSWORD
code="$(api_call viewer GET /api/auth/session)"
expect_status "GET /api/auth/session as viewer" 200 "$code"
[ "$(jqr -r '.user.permissions | join(",")' <"$TMPD/body")" = "blog.view" ] || fail "viewer permissions are not exactly [blog.view]"
ok "viewer permissions are exactly [blog.view]"
code="$(api_call admin GET /api/blog-agent/settings)"
expect_status "GET /api/blog-agent/settings as admin" 200 "$code" --quiet
[ "$(jqr -r '.mockMode' <"$TMPD/body")" = true ] || fail "settings report mockMode=false; Phase 1 needs mock mode"
[ "$(jqr -r '.humanApprovalRequired' <"$TMPD/body")" = true ] || fail "settings report humanApprovalRequired=false"
ok "settings: mockMode=true, humanApprovalRequired=true"
info "settings: agentEnabled=$(jqr -r '.agentEnabled' <"$TMPD/body") schedulerEnabled=$(jqr -r '.schedulerEnabled' <"$TMPD/body") publishingEnabled=$(jqr -r '.publishingEnabled' <"$TMPD/body")"

# ---------------------------------------------------------------------------------------------
step "RBAC"
code="$(api_call viewer GET '/api/blog-agent/runs?limit=5')"
expect_status "viewer GET /api/blog-agent/runs" 200 "$code"
code="$(api_call viewer POST /api/blog-agent/runs '{}')"
expect_problem "viewer POST /api/blog-agent/runs" 403 "$code" "Forbidden"
code="$(api_call viewer GET /api/blog-agent/settings)"
expect_problem "viewer GET /api/blog-agent/settings" 403 "$code" "Forbidden"
code="$(api_call viewer GET /api/admin/users)"
expect_problem "viewer GET /api/admin/users" 403 "$code" "Forbidden"

# ---------------------------------------------------------------------------------------------
step "Admin run: enqueue and complete"
RUN1="$(create_run admin)"
expect_status "admin POST /api/blog-agent/runs" 202 "$(cat "$TMPD/create.status")"
require_uuid "run id" "$RUN1"
wait_for_run admin "$RUN1" 120
wait_for_steps_settled admin "$RUN1" 60
ok "run $RUN1 reached SUCCEEDED"
steps_seen="$(jqr -r '[.steps[] | "\(.stepName):\(.status):\(.tries)"] | sort | join(" ")' <"$TMPD/run.json")"
[ "$steps_seen" = "hello.echo:SUCCEEDED:1 hello.finish:SUCCEEDED:1 hello.open_attempt:SUCCEEDED:1" ] ||
  fail "unexpected steps for $RUN1: $steps_seen"
ok "3 steps, each SUCCEEDED once ($steps_seen)"
calls="$(sql "select count(*) from app.blog_llm_calls where run_id = '$RUN1'")"
[ "$calls" = 1 ] || fail "run $RUN1 has $calls blog_llm_calls rows, expected 1"
ok "run $RUN1 has exactly 1 blog_llm_calls row"
TRACE1="$(jqr -r '.traceId' <"$TMPD/run.json")"
docker compose logs --no-color worker >"$TMPD/worker.log" 2>&1 || true
ctx_lines="$(grep -F "\"run_id\": \"$RUN1\"" "$TMPD/worker.log" | grep -cF "\"trace_id\": \"$TRACE1\"" || true)"
[ "$ctx_lines" -ge 1 ] || fail "worker JSON logs have no line carrying run_id=$RUN1 and its trace_id"
ok "worker JSON logs carry run_id and trace_id for run $RUN1 ($ctx_lines lines)"

# ---------------------------------------------------------------------------------------------
step "CSRF"
code="$(curl -sS -o "$TMPD/body" -w '%{http_code}' -b "$TMPD/admin.jar" -X POST -H "@$TMPD/admin.csrf" \
  -H 'Content-Type: application/json' --data-binary '{}' "$API/api/blog-agent/runs")"
expect_problem "direct POST without an Origin header" 403 "$code" "Origin not allowed"

read -r -d '' PROBE <<'SH' || true
set -eu
base=http://web:5173
printf '{"email":"%s","password":"%s"}' "$P1_ADMIN_EMAIL" "$P1_ADMIN_PASSWORD" >/tmp/login.json
code=$(curl -sS -D /tmp/login.h -o /tmp/login.b -w '%{http_code}' -H 'Origin: http://web:5173' \
  -H "X-Forwarded-For: $SPOOF_IP" -H 'Content-Type: application/json' --data-binary @/tmp/login.json "$base/api/auth/login")
rm -f /tmp/login.json
echo "login=$code"
# curl drops jar cookies for dotless hosts such as "web", so the cookie is copied from Set-Cookie.
cookie=$(sed -n 's/^[Ss]et-[Cc]ookie: *\([^;]*\).*/\1/p' /tmp/login.h | head -n 1)
csrf=$(sed -n 's/.*"csrfToken" *: *"\([^"]*\)".*/\1/p' /tmp/login.b)
title() { sed -n 's/.*"title" *: *"\([^"]*\)".*/\1/p' "$1"; }
post() {
  label=$1
  shift
  code=$(curl -sS -o "/tmp/$label.b" -w '%{http_code}' -X POST -H "Cookie: $cookie" \
    -H 'Content-Type: application/json' --data-binary '{}' "$@" "$base/api/blog-agent/runs")
  echo "$label=$code|$(title "/tmp/$label.b")"
}
post foreign_origin -H 'Origin: http://evil.example' -H "X-CSRF-Token: $csrf"
post cross_site -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: cross-site' -H "X-CSRF-Token: $csrf"
post missing_token -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: same-origin'
post wrong_token -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: same-origin' -H 'X-CSRF-Token: 00'
post same_origin -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: same-origin' -H "X-CSRF-Token: $csrf"
echo "run_id=$(sed -n 's/.*"id" *: *"\([0-9a-f-]*\)".*/\1/p' /tmp/same_origin.b | head -n 1)"
code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H "Cookie: $cookie" -H 'Origin: http://web:5173' \
  -H 'Sec-Fetch-Site: same-origin' -H "X-CSRF-Token: $csrf" "$base/api/auth/logout")
echo "logout=$code"
SH
docker run --rm --network "$NETWORK" -e P1_ADMIN_EMAIL -e P1_ADMIN_PASSWORD -e SPOOF_IP="$SPOOF_IP" \
  --entrypoint sh "$CURL_IMAGE" -c "$PROBE" >"$TMPD/probe.out" 2>&1 ||
  { mask <"$TMPD/probe.out"; fail "CSRF probe container failed"; }
probe() { kv "$TMPD/probe.out" "$1"; }
[ "$(probe login)" = 200 ] || fail "login through the Vite proxy returned $(probe login)"
ok "login through http://web:5173 (HTTP 200)"
[ "$(probe foreign_origin)" = "403|Origin not allowed" ] || fail "foreign Origin through the proxy: $(probe foreign_origin)"
ok "foreign Origin through the proxy is rejected (403 Origin not allowed)"
[ "$(probe cross_site)" = "403|Cross-site request blocked" ] || fail "Sec-Fetch-Site cross-site: $(probe cross_site)"
ok "Sec-Fetch-Site: cross-site is rejected (403 Cross-site request blocked)"
[ "$(probe missing_token)" = "403|CSRF token missing or invalid" ] || fail "missing token: $(probe missing_token)"
ok "missing X-CSRF-Token is rejected (403)"
[ "$(probe wrong_token)" = "403|CSRF token missing or invalid" ] || fail "wrong token: $(probe wrong_token)"
ok "wrong X-CSRF-Token is rejected (403)"
case "$(probe same_origin)" in
  "202|"*) ok "same-origin POST with the token through http://web:5173 is accepted (202)" ;;
  *) fail "same-origin POST through the proxy: $(probe same_origin)" ;;
esac
[ "$(probe logout)" = 204 ] || fail "logout through the proxy returned $(probe logout)"
ok "logout through the proxy (204)"
RUN2="$(probe run_id)"
require_uuid "proxy run id" "$RUN2"
wait_for_run admin "$RUN2" 120
wait_for_steps_settled admin "$RUN2" 60
ok "run $RUN2 (created through the proxy) reached SUCCEEDED"
# Three logins so far (admin and viewer direct, admin through the proxy), each with a forged X-Forwarded-For.
attempt_ips="$(sql "select count(*) filter (where ip = '$SPOOF_IP'), count(*) filter (where coalesce(ip, '') = ''), count(*)
  from app.login_attempts where email in ('$P1_ADMIN_EMAIL', '$P1_VIEWER_EMAIL')")"
[ "$attempt_ips" = "0|0|3" ] ||
  fail "login_attempts (forged ip|empty ip|total) = $attempt_ips, expected 0|0|3; the api must record the TCP peer, not X-Forwarded-For"
ok "a forged X-Forwarded-For is ignored: login_attempts record the TCP peer for all 3 logins"

# ---------------------------------------------------------------------------------------------
step "Browser check (Chromium in a container on the compose network)"
read -r -d '' BROWSER_JS <<'JS' || true
import { chromium } from 'playwright'

const base = 'http://web:5173'
const pages = [
  ['Dashboard', '/'],
  ["Today's Ideas", '/ideas'],
  ['Research', '/research'],
  ['Drafts', '/drafts'],
  ['Review Queue', '/review'],
  ['Published', '/published'],
  ['Topics', '/topics'],
  ['Content Calendar', '/calendar'],
  ['Sources', '/sources'],
  ['Settings', '/settings'],
  ['Agent Runs', '/agent-runs'],
]
const out = (key, value) => console.log(`${key}=${value}`)
const errors = []
const browser = await chromium.launch()
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await context.newPage()
  page.setDefaultTimeout(15000)
  page.on('pageerror', (error) => errors.push(error.message))

  await page.goto(`${base}/login`)
  await page.getByLabel('Email').fill(process.env.P1_ADMIN_EMAIL)
  await page.getByLabel('Password').fill(process.env.P1_ADMIN_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('heading', { level: 1, name: 'Dashboard', exact: true }).waitFor()
  out('login', new URL(page.url()).pathname)

  const nav = page.getByRole('navigation', { name: 'Main' })
  out('nav', (await nav.getByRole('link').allInnerTexts()).map((text) => text.trim()).join('|'))
  for (const [label, path] of pages) {
    await nav.getByRole('link', { name: label, exact: true }).click()
    await page.waitForURL(`${base}${path}`)
    try {
      await page.getByRole('heading', { level: 1, name: label, exact: true }).waitFor()
      out(`page:${path}`, label)
    } catch {
      out(`page:${path}`, `missing heading; h1 texts: ${(await page.locator('h1').allInnerTexts()).join(' / ')}`)
    }
  }

  await nav.getByRole('link', { name: 'Dashboard', exact: true }).click()
  const [created] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/blog-agent/runs'),
    page.getByRole('button', { name: "Generate today's blog" }).click(),
  ])
  const run = await created.json()
  out('generate', `${created.status()}|${run.id ?? run.title ?? ''}`)

  await page.getByRole('button', { name: 'Acceptance Admin' }).click()
  const [loggedOut] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/auth/logout'),
    page.getByRole('menuitem', { name: 'Sign out' }).click(),
  ])
  await page.waitForURL(`${base}/login`)
  out('logout', loggedOut.status())
  await page.goto(`${base}/agent-runs`)
  await page.getByRole('heading', { level: 1, name: 'Sign in' }).waitFor()
  out('after_logout', new URL(page.url()).pathname)
  out('page_errors', errors.length)
} catch (error) {
  out('error', String(error.message).split('\n').slice(0, 5).join(' | '))
  process.exitCode = 1
} finally {
  await browser.close()
}
JS
printf '%s\n' "$BROWSER_JS" >"$TMPD/browser.mjs"
if ! docker run --rm --network "$NETWORK" -e P1_ADMIN_EMAIL -e P1_ADMIN_PASSWORD -e PLAYWRIGHT_NPM="$PLAYWRIGHT_NPM" \
  -v "$TMPD/browser.mjs:/work/browser.mjs:ro" -w /work "$BROWSER_IMAGE" \
  sh -c 'npm install --no-save --no-audit --no-fund "$PLAYWRIGHT_NPM" >/tmp/npm.log 2>&1 || { tail -n 20 /tmp/npm.log; exit 1; }; node browser.mjs' \
  >"$TMPD/browser.out" 2>&1; then
  mask <"$TMPD/browser.out"
  fail "browser check failed (see the output above)"
fi
browser() { kv "$TMPD/browser.out" "$1"; }
[ "$(browser login)" = / ] || fail "browser sign-in did not reach the Dashboard: $(browser login)"
ok "browser: $P1_ADMIN_EMAIL signs in at http://web:5173/login and lands on Dashboard"
expected_nav="Dashboard|Today's Ideas|Research|Drafts|Review Queue|Published|Topics|Content Calendar|Sources|Settings|Agent Runs"
[ "$(browser nav)" = "$expected_nav" ] || fail "browser sidebar shows: $(browser nav)"
ok "browser: the sidebar lists the 11 nav items in spec order"
for entry in "/:Dashboard" "/ideas:Today's Ideas" "/research:Research" "/drafts:Drafts" "/review:Review Queue" \
  "/published:Published" "/topics:Topics" "/calendar:Content Calendar" "/sources:Sources" "/settings:Settings" \
  "/agent-runs:Agent Runs"; do
  path="${entry%%:*}"
  label="${entry#*:}"
  [ "$(browser "page:$path")" = "$label" ] || fail "browser: $path: $(browser "page:$path")"
  ok "browser: sidebar link \"$label\" opens $path and renders its heading"
done
[ "$(browser page_errors)" = 0 ] || fail "browser: $(browser page_errors) uncaught page errors"
ok "browser: no uncaught JavaScript errors"
generated="$(browser generate)"
case "$generated" in
  "202|"*) ok "browser: \"Generate today's blog\" POST /api/blog-agent/runs passed the CSRF checks (202)" ;;
  *) fail "browser: Generate today's blog returned $generated" ;;
esac
RUN_B="${generated#202|}"
require_uuid "browser run id" "$RUN_B"
if [ "$(browser logout)" != 204 ] || [ "$(browser after_logout)" != /login ]; then
  fail "browser sign-out: logout HTTP $(browser logout), then /agent-runs led to $(browser after_logout)"
fi
ok "browser: Sign out (POST /api/auth/logout 204); /agent-runs then leads to /login"
wait_for_run admin "$RUN_B" 120
wait_for_steps_settled admin "$RUN_B" 60
ok "run $RUN_B (created in the browser) reached SUCCEEDED"

# ---------------------------------------------------------------------------------------------
step "Kill the worker during hello.echo and resume"
snapshot_logs
DELAY_CHANGED=1
BLOG_AGENT_MOCK_STEP_DELAY_SECONDS="$KILL_DELAY_SECONDS" docker compose up -d --no-deps --wait --wait-timeout 120 worker >"$TMPD/up.log" 2>&1 ||
  { tail -n 20 "$TMPD/up.log" | mask; fail "worker did not come back healthy with the step delay"; }
[ "$(docker compose exec -T worker printenv BLOG_AGENT_MOCK_STEP_DELAY_SECONDS)" = "$KILL_DELAY_SECONDS" ] ||
  fail "worker did not pick up BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=$KILL_DELAY_SECONDS"
ok "worker recreated with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=$KILL_DELAY_SECONDS"
RUN3="$(create_run admin)"
expect_status "admin POST /api/blog-agent/runs" 202 "$(cat "$TMPD/create.status")"
require_uuid "run id" "$RUN3"
wait_for_step_running admin "$RUN3" hello.echo 120
ok "hello.echo is RUNNING for run $RUN3"
# echo_step sleeps (the mock delay) before its gateway call; 2 s puts the kill inside that sleep,
# so the interrupted execution has not called the gateway yet.
sleep 2
docker compose kill worker >/dev/null 2>&1
killed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ok "docker compose kill worker ($killed_at)"
sleep 2
code="$(api_call admin GET "/api/blog-agent/runs/$RUN3")"
[ "$code" = 200 ] || fail "GET run $RUN3 returned HTTP $code while the worker was down"
cp "$TMPD/body" "$TMPD/run.json"
mid_status="$(jqr -r '.status' <"$TMPD/run.json")"
[ "$mid_status" = RESEARCHING ] || fail "run $RUN3 is $mid_status right after the kill, expected RESEARCHING (killed before the gateway call)"
[ "$(step_field hello.echo status)" = RUNNING ] || fail "hello.echo is not RUNNING after the kill: $(step_field hello.echo status)"
mid_calls="$(sql "select count(*) from app.blog_llm_calls where run_id = '$RUN3'")"
[ "$mid_calls" = 0 ] || fail "run $RUN3 already has $mid_calls blog_llm_calls rows at the kill; the kill must land before the gateway call"
ok "while the worker is down: run RESEARCHING, hello.echo still RUNNING, no gateway call recorded yet"
BLOG_AGENT_MOCK_STEP_DELAY_SECONDS="$KILL_DELAY_SECONDS" docker compose up -d --no-deps worker >"$TMPD/up.log" 2>&1 ||
  { tail -n 20 "$TMPD/up.log" | mask; fail "could not start the worker again"; }
ok "worker started again (same container, same executor id and APP_VERSION)"
wait_for_run admin "$RUN3" 240
wait_for_steps_settled admin "$RUN3" $((KILL_DELAY_SECONDS + 60))
ok "run $RUN3 resumed and reached SUCCEEDED"
info "steps: $(jqr -r '[.steps[] | "\(.stepName) \(.status) tries=\(.tries)"] | join(", ")' <"$TMPD/run.json")"
[ "$(jqr -r '.steps | length' <"$TMPD/run.json")" = 3 ] || fail "run $RUN3 has $(jqr -r '.steps | length' <"$TMPD/run.json") step rows, expected 3"
[ "$(jqr -r '.attempts | length' <"$TMPD/run.json")" = 1 ] || fail "run $RUN3 has more than one attempt; recovery should reuse the workflow"
[ "$(jqr -r '[.steps[] | select(.status != "SUCCEEDED")] | length' <"$TMPD/run.json")" = 0 ] || fail "run $RUN3 has steps that did not succeed"
[ "$(step_field hello.open_attempt tries)" = 1 ] || fail "hello.open_attempt ran again after recovery (tries=$(step_field hello.open_attempt tries))"
[ "$(step_field hello.finish tries)" = 1 ] || fail "hello.finish ran more than once (tries=$(step_field hello.finish tries))"
ok "completed steps were not repeated: hello.open_attempt tries=1, hello.finish tries=1"
echo_tries="$(step_field hello.echo tries)"
[ "$echo_tries" = 2 ] || fail "hello.echo tries=$echo_tries, expected 2 (the interrupted execution plus the resumed one)"
ok "only the interrupted step re-ran: hello.echo tries=2"
# The interrupted execution was killed before its gateway call, so only the resumed execution
# recorded one. The single row belongs to the hello.echo step row and is ok.
call_stats="$(sql "select count(*), count(*) filter (where a.step_name = 'hello.echo'), count(*) filter (where c.status = 'ok')
  from app.blog_llm_calls c left join app.blog_agent_runs a on a.id = c.agent_run_id where c.run_id = '$RUN3'")"
[ "$call_stats" = "1|1|1" ] ||
  fail "run $RUN3 blog_llm_calls (total|echo|ok) = $call_stats, expected 1|1|1 (one gateway call, no duplicate after resume)"
ok "blog_llm_calls for run $RUN3: 1 row on the hello.echo step, ok (no duplicate call after resume)"
recovery_lines="$(docker compose logs --no-color --since "$killed_at" worker 2>&1 | grep -ci 'recover' || true)"
info "worker log lines mentioning recovery since the kill: $recovery_lines"
snapshot_logs
BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0 docker compose up -d --no-deps --wait --wait-timeout 120 worker >"$TMPD/up.log" 2>&1 ||
  { tail -n 20 "$TMPD/up.log" | mask; fail "worker did not come back healthy with the delay restored"; }
[ "$(docker compose exec -T worker printenv BLOG_AGENT_MOCK_STEP_DELAY_SECONDS)" = 0 ] || fail "worker delay was not restored to 0"
DELAY_CHANGED=0
ok "worker recreated with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0"

# ---------------------------------------------------------------------------------------------
step "Secrets"
snapshot_logs
sort -u "$TMPD/logs.txt" >"$TMPD/logs.uniq"
log_lines="$(wc -l <"$TMPD/logs.uniq" | tr -d ' ')"

read -r -d '' LOG_VALUES_PY <<'PY' || true
import os
import sys

text = sys.stdin.read()
names = (
    "OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "NCBI_API_KEY", "SESSION_SECRET",
    "POSTGRES_PASSWORD", "BOOTSTRAP_ADMIN_PASSWORD", "BLOG_PUBLISHER_PASSWORD",
    "P1_ADMIN_PASSWORD", "P1_VIEWER_PASSWORD",
)
checked = [n for n in names if len(os.environ.get(n, "")) >= 12]
found = [n for n in checked if os.environ[n] in text]
if found:
    print("FAIL the values of " + ", ".join(found) + " appear in the logs")
    sys.exit(1)
print(f"{len(checked)} secret values checked")
PY
values_result="$(docker compose exec -T -e P1_ADMIN_PASSWORD -e P1_VIEWER_PASSWORD api python -c "$LOG_VALUES_PY" <"$TMPD/logs.uniq" 2>&1)" ||
  fail "log secret check: $(printf '%s' "$values_result" | tail -n 1 | mask)"
ok "no configured secret value appears in the api/worker logs ($values_result, $log_lines distinct log lines)"

leak_lines="$(grep -Ec 'sk-|AIza' "$TMPD/logs.uniq" || true)"
if [ "$leak_lines" = 0 ]; then
  ok "docker compose logs api worker | grep -E 'sk-|AIza' finds nothing ($log_lines distinct log lines checked)"
else
  key_shaped="$(grep -Ec '(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,}' "$TMPD/logs.uniq" || true)"
  info "grep -E 'sk-|AIza' matched $leak_lines log lines; masked context (at most 10 distinct):"
  { grep -Eo '.{0,20}(sk-|AIza).{0,4}' "$TMPD/logs.uniq" | mask | sort | uniq -c | head -n 10 | sed 's/^/          /'; } || true
  [ "$key_shaped" = 0 ] || fail "api/worker logs contain $key_shaped key-shaped strings ('sk-...' or 'AIza...'); see the masked context above"
  warn "grep -E 'sk-|AIza' matched $leak_lines log lines, none key-shaped and none a configured secret (context above); read them before signing off"
fi

read -r -d '' MASK_CHECK_PY <<'PY' || true
import json
import os
import sys

body = sys.stdin.read()
data = json.loads(body)
names = ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "NCBI_API_KEY")
leaked = [n for n in names if len(os.environ.get(n, "")) >= 12 and os.environ[n] in body]
bad = []
for key, view in sorted(data["providers"].items()):
    preview = view["preview"]
    shaped = preview is None or preview == "set" or (len(preview) == 8 and preview[3] == "…")
    if not shaped or (preview is None) == bool(view["configured"]):
        bad.append(key)
if leaked or bad:
    print(f"FAIL full_keys_in_response={len(leaked)} badly_masked={','.join(bad) or '-'}")
    sys.exit(1)
print("OK " + " ".join(f"{k}={'configured' if v['configured'] else 'unset'}" for k, v in sorted(data["providers"].items())))
PY
code="$(api_call admin GET /api/blog-agent/settings)"
expect_status "GET /api/blog-agent/settings as admin" 200 "$code" --quiet
mask_result="$(docker compose exec -T api python -c "$MASK_CHECK_PY" <"$TMPD/body" 2>&1)" ||
  fail "settings masking check: $(printf '%s' "$mask_result" | tail -n 1 | mask)"
ok "settings return provider keys masked ($mask_result)"

# ---------------------------------------------------------------------------------------------
step "Runtime invariants"
api_launch_lines="$(grep -F 'DBOS launched' "$TMPD/logs.uniq" | grep -c '^api-' || true)"
if [ "$api_launch_lines" != 0 ]; then
  fail "the api process logged 'DBOS launched'; only the worker may call DBOS.launch()"
fi
ok "api never logged 'DBOS launched' (the worker is the only DBOS executor)"
schedule_status="$(sql "select status from dbos.workflow_schedules where schedule_name = 'daily_generation'")"
scheduler_flag="$(docker compose exec -T worker sh -c 'printf %s "${BLOG_AGENT_SCHEDULER_ENABLED:-false}"' | tr '[:upper:]' '[:lower:]')"
case "$scheduler_flag" in
  true | 1 | yes | on) expected_schedule=ACTIVE ;;
  *) expected_schedule=PAUSED ;;
esac
[ "$schedule_status" = "$expected_schedule" ] ||
  fail "daily_generation schedule is '${schedule_status:-missing}', expected $expected_schedule (BLOG_AGENT_SCHEDULER_ENABLED=$scheduler_flag)"
ok "daily_generation schedule is $schedule_status (BLOG_AGENT_SCHEDULER_ENABLED=$scheduler_flag)"

# ---------------------------------------------------------------------------------------------
step "Sign out and close the throwaway accounts"
viewer_id="$(cat "$TMPD/viewer.id")"
require_uuid "viewer id" "$viewer_id"
code="$(api_call admin PATCH "/api/admin/users/$viewer_id" '{"isActive": false}')"
expect_status "admin PATCH /api/admin/users/{viewer} isActive=false" 200 "$code"
code="$(api_call viewer GET /api/auth/session)"
expect_status "deactivated viewer's session no longer resolves" 401 "$code"
code="$(api_call admin POST /api/auth/logout)"
expect_status "admin POST /api/auth/logout" 204 "$code"
code="$(api_call admin GET /api/auth/session)"
expect_status "admin session after logout" 401 "$code"
: >"$TMPD/admin.jar"
: >"$TMPD/viewer.jar"

step "Optional owner check"
info "Open http://localhost:${WEB##*:} in your own browser and sign in as BOOTSTRAP_ADMIN_EMAIL (plan Step 17)."
```

Make it executable and lint it. Both commands run on the host (bash) or in a container, with no Python or Node:

```bash
chmod +x scripts/acceptance/phase1.sh
bash -n scripts/acceptance/phase1.sh && echo "syntax ok"
docker run --rm -v "$PWD/scripts:/mnt:ro" koalaman/shellcheck:v0.11.0 -S style /mnt/acceptance/phase1.sh && echo "shellcheck clean"
```

Expected: `syntax ok`, then `shellcheck clean`.

- [ ] **Step 5: Run the acceptance script against the Task 1 compose file and watch it fail**

Run:

```bash
SKIP_SUITES=1 scripts/acceptance/phase1.sh
```

Expected: exit code 1, ending with:

```text
==> Start the stack and wait for health
  PASS  db is healthy
  FAIL  api is 'not running or not defined', expected healthy

PHASE 1 ACCEPTANCE: FAIL (4 checks passed before the failure)
```

Two other failures would be earlier:
- the `.env` check, which lists what to change (hand that to the owner, as in Step 2);
- `docker compose build`.

- [ ] **Step 6: Check `backend/Dockerfile` (replace it only if the check fails)**

Task 1 already wrote the final Dockerfile. Confirm the two properties Phase 1 relies on:
- the builder installs the project editable (no `--no-editable`);
- `runtime` copies `src/`, `prompts/` and `fixtures/`.

Then `default_prompt_root()` and `FixtureRegistry.default()` resolve to `/app/prompts` and `/app/fixtures` in the runtime image.

```bash
grep -c -- '--no-editable' backend/Dockerfile || true
grep -nE '^COPY --from=builder /app/(src|prompts|fixtures) ' backend/Dockerfile
```

Expected: `0`, then three `COPY --from=builder` lines, for `/app/src`, `/app/prompts` and `/app/fixtures`.

**Decision rule.** If the count is not `0` or a COPY line is missing, replace the whole file with this verified version. It is functionally the same as Task 1's file; only comments differ.

```dockerfile
# syntax=docker/dockerfile:1
# Pattern: docs.astral.sh/uv/guides/integration/docker + astral-sh/uv-docker-example multistage.Dockerfile
# Targets:
#   dev     -> used by compose (migrate, api, worker, tools); the repo is bind-mounted over /app
#   runtime -> non-root image for the Phase 10 production profile (not used by compose in Phase 1)
ARG PYTHON_IMAGE=python:3.12-slim-trixie

# ---------- base: interpreter + pinned uv ----------
FROM ${PYTHON_IMAGE} AS base
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ---------- dev: all groups (dev included), source is bind-mounted over /app ----------
# The venv lives in /opt/venv, so a bind mount of the repo on /app does not hide it.
# The project is installed editable (.pth -> /app/src), so bind-mounted edits are picked up.
FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
CMD ["uvicorn", "--factory", "mdcopilot_blog.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]

# ---------- builder: no dev deps; project installed editable from /app/src ----------
# Editable on purpose: prompts/registry.py and llm/mock.py resolve backend/prompts and
# backend/fixtures as Path(__file__).resolve().parents[3], which is /app only when the
# package is imported from /app/src (a --no-editable install would resolve under /opt/venv/lib).
FROM base AS builder
ENV UV_NO_DEV=1
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked \
 && python -m compileall -q /app/src

# ---------- runtime: no uv, no dev deps, non-root ----------
# Must be the same interpreter image as the builder (venv symlinks point at /usr/local/bin/python3).
FROM ${PYTHON_IMAGE} AS runtime
RUN groupadd --system --gid 999 app \
 && useradd --system --gid 999 --uid 999 --create-home app
# Everything stays root-owned (read-only for the app user); bytecode was compiled in the builder.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/src /app/src
COPY --from=builder /app/prompts /app/prompts
COPY --from=builder /app/fixtures /app/fixtures
ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
USER app
# Phase 10: replace "*" with the production reverse proxy's address (IMPLEMENTATION_PLAN, Phase 10).
CMD ["uvicorn", "--factory", "mdcopilot_blog.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

- [ ] **Step 7: Build and smoke-test both backend targets**

Run:

```bash
docker compose build tools
docker build --target runtime -t mdcopilot-blog-backend:runtime backend
docker run --rm mdcopilot-blog-backend:runtime sh -c 'id -u; command -v uv || echo "no uv"; python -c "import pytest" 2>/dev/null && echo "pytest present" || echo "no pytest"'
docker run --rm mdcopilot-blog-backend:runtime python -c "from mdcopilot_blog.prompts.registry import PromptRegistry, default_prompt_root; from mdcopilot_blog.llm.mock import FixtureRegistry; from mdcopilot_blog.api.app import create_app; reg = PromptRegistry.from_directory(default_prompt_root()); print(default_prompt_root(), reg.get('hello/echo').version, FixtureRegistry.default().load('hello', 'hello/echo')['output']['word_count'], callable(create_app))"
docker run --rm mdcopilot-blog-backend:runtime python -m mdcopilot_blog.cli --help
```

Expected:
1. Both builds succeed.
2. The first `run` prints `999`, `no uv` and `no pytest`.
3. The second prints `/app/prompts 1 5 True`.
4. The third prints the argparse usage, listing `migrate`, `migrate-dbos`, `seed`, `sync-prompts`, `create-admin` and `create-user`.

**Decision rule.** If the second command prints a path under `/opt/venv/lib/...`, the editable install did not happen.
- Check `docker run --rm mdcopilot-blog-backend:runtime sh -c 'cat /opt/venv/lib/python3.12/site-packages/*.pth'`. It must print `/app/src`.
- Make sure the builder's last `uv sync --locked` has no `--no-editable`.

- [ ] **Step 8: Replace `compose.yaml` (final form)**

Replace the whole file with:

```yaml
# mdcopilot-blog local stack (Phase 1). See docs/blog-agent/LOCAL_DEVELOPMENT.md.
# Host ports bind to 127.0.0.1 only. No Redis: DBOS keeps queues and schedules in Postgres.
# Warning: `docker compose config` prints values from .env (secrets included); do not paste its output.
name: mdcopilot-blog

x-backend: &backend
  build:
    context: ./backend
    target: dev
  image: mdcopilot-blog-backend:dev
  env_file:
    - .env
  environment:
    POSTGRES_HOST: db
    BLOG_AGENT_MOCK_STEP_DELAY_SECONDS: "${BLOG_AGENT_MOCK_STEP_DELAY_SECONDS:-0}"
  volumes:
    - ./backend:/app

services:
  db:
    # pgvector/pgvector:pg16, pinned to its multi-arch index digest (2026-09-17). To move it on purpose:
    # docker buildx imagetools inspect pgvector/pgvector:pg16, then copy the top-level "Digest:" here.
    image: pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b
    # Only the three variables Postgres needs, interpolated from .env. Not env_file, which would hand
    # every provider key and SESSION_SECRET to the database container. Defaults match Settings.
    environment:
      POSTGRES_DB: "${POSTGRES_DB:-mdcopilot_blog}"
      POSTGRES_USER: "${POSTGRES_USER:-mdcopilot_blog}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}"
    ports:
      - "127.0.0.1:${DB_HOST_PORT:-5440}:5432"
    volumes:
      - blog_pgdata:/var/lib/postgresql/data
    healthcheck:
      # Probe TCP (-h 127.0.0.1), not the Unix socket. On a fresh volume the image's temporary init server
      # listens on the socket only, so a socket probe can pass before db:5432 accepts connections.
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -p 5432 -U \"$$POSTGRES_USER\" -d \"$$POSTGRES_DB\""]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 10s
      start_interval: 1s

  # One-shot: alembic upgrade head, DBOS system-table migrations (in-process), seed, sync-prompts.
  # api and worker wait for exit 0.
  migrate:
    <<: *backend
    command: ["python", "-m", "mdcopilot_blog.cli", "migrate"]
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

  # Enqueues through DBOSClient only; never calls DBOS.launch().
  api:
    <<: *backend
    command:
      - uvicorn
      - --factory
      - mdcopilot_blog.api.app:create_app
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --reload
      - --reload-dir
      - /app/src
      # Ignore X-Forwarded-For/-Proto: the client address is the TCP peer (the Vite proxy for browser traffic).
      # Trusting them ("--proxy-headers --forwarded-allow-ips *") would let any client choose the IP that the
      # login rate limit and app.login_attempts record. CSRF reads X-Forwarded-Proto itself (auth/csrf.py).
      - --no-proxy-headers
    ports:
      - "127.0.0.1:${API_HOST_PORT:-8300}:8000"
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 60s
      start_interval: 2s

  # The only DBOS executor. Recovery after a crash needs the same WORKER_EXECUTOR_ID and APP_VERSION.
  worker:
    <<: *backend
    command: ["python", "-m", "mdcopilot_blog.worker"]
    environment:
      # YAML merge is shallow: this map replaces the anchor's, so the shared entries are repeated.
      POSTGRES_HOST: db
      BLOG_AGENT_MOCK_STEP_DELAY_SECONDS: "${BLOG_AGENT_MOCK_STEP_DELAY_SECONDS:-0}"
      WORKER_EXECUTOR_ID: worker-1
    # DBOS.destroy waits up to 25 s for running workflows on SIGTERM.
    stop_grace_period: 40s
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    healthcheck:
      # The worker touches /tmp/worker-heartbeat every 10 s once DBOS is launched.
      test: ["CMD-SHELL", "test $$(( $$(date +%s) - $$(stat -c %Y /tmp/worker-heartbeat) )) -lt 60"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 90s
      start_interval: 2s

  # Vite dev server; proxies /api to api:8000 so the app is same-origin.
  # The service must stay named "web" (vite.config.ts allowedHosts).
  web:
    build:
      context: ./frontend
      target: dev
    image: mdcopilot-blog-web:dev
    ports:
      - "127.0.0.1:${WEB_HOST_PORT:-8310}:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      VITE_API_PROXY_TARGET: http://api:8000
    depends_on:
      api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:5173/"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 60s
      start_interval: 2s

  # Tests, lint, alembic and one-off CLI commands: docker compose run --rm tools <cmd>
  tools:
    <<: *backend
    profiles: [tools]
    depends_on:
      db:
        condition: service_healthy
    command: ["pytest", "-q"]

volumes:
  blog_pgdata: {}
```

This file carries deviations 1–5 from the list at the top of this task:
- the `db` TCP healthcheck, three-variable environment and digest pin;
- `--no-proxy-headers` on `api`;
- healthcheck timings on every long-running service.

The `db` block is the same as Task 1's except for the pinned digest and the timings, so Step 9 recreates `db` and keeps the `blog_pgdata` volume. The default network is unchanged from Task 1.

Validate it **without printing the resolved config**. Plain `docker compose config` prints `.env` values, secrets included.

```bash
docker compose config --quiet && echo "compose ok"
docker compose --profile tools config --services
docker image inspect --format '{{index .RepoDigests 0}}' pgvector/pgvector:pg16
```

Expected:
1. `compose ok`. If it prints `required variable POSTGRES_PASSWORD is missing a value`, hand Step 2's owner instruction back to the owner.
2. The six services `db`, `migrate`, `api`, `worker`, `web` and `tools`, one per line in any order.
3. `pgvector/pgvector@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b` (the image Task 1 pulled).

**Decision rule for 3.** If the local digest differs, the `pg16` tag has moved since 2026-09-17. Keep the pinned digest in `compose.yaml`; Step 9 pulls it. Do not re-pin without the owner.

- [ ] **Step 9: Start the full stack**

Run:

```bash
docker compose up -d --build --wait --wait-timeout 300
docker compose ps -a --format 'table {{.Service}}\t{{.Status}}'
```

Expected: the first command exits 0. The first build runs `npm ci` and `uv sync` and can take a few minutes. The table then shows:

```text
SERVICE   STATUS
api       Up <n> seconds (healthy)
db        Up <n> seconds (healthy)
migrate   Exited (0) <n> seconds ago
web       Up <n> seconds (healthy)
worker    Up <n> seconds (healthy)
```

**If `--wait` fails,** check these logs; each command masks passwords in database URLs:
- `docker compose logs migrate | sed -E 's#(://[^:/@ ]+:)[^@ ]*@#\1***@#g' | tail -n 40`
- then the same command for `api`, `worker` and `web`.

Typical causes:
- a database password that differs from the one the volume was created with;
- a settings validation error, which names the variable;
- a prompt sync error.

- [ ] **Step 10: Probe the running stack by hand**

Run:

```bash
curl -s http://127.0.0.1:8300/healthz; echo
curl -s http://127.0.0.1:8300/readyz; echo
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8310/agent-runs
curl -s http://127.0.0.1:8310/api/auth/session; echo
docker compose logs --no-color worker | grep -c 'DBOS launched'
docker compose logs --no-color api | grep -c 'DBOS launched' || true
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$(docker compose ps -q db)" | cut -d= -f1 | grep -E '^POSTGRES_' | sort | paste -s -d ' ' -
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$(docker compose ps -q db)" | cut -d= -f1 | grep -cE 'KEY|SECRET|BOOTSTRAP|PUBLISHER' || true
docker inspect -f '{{json .Args}}' "$(docker compose ps -q api)"
```

Expected, in order:
1. `{"status":"ok"}`
2. `{"status":"ok","database":"ok"}`
3. `200` (the SPA shell)
4. `{"type":"about:blank","title":"Not authenticated","status":401,"instance":"/api/auth/session"}`
5. a number ≥ 1 (the worker launched DBOS)
6. `0` (the api never launches DBOS)
7. `POSTGRES_DB POSTGRES_PASSWORD POSTGRES_USER` (variable names only; `cut` drops the values)
8. `0` (no provider key, session secret or admin password in the database container)
9. `["--factory","mdcopilot_blog.api.app:create_app","--host","0.0.0.0","--port","8000","--reload","--reload-dir","/app/src","--no-proxy-headers"]`

- [ ] **Step 11: Run the acceptance script and watch it pass**

Run (takes about 4–8 minutes; the first run also pulls the Playwright image, about 2 GB):

```bash
scripts/acceptance/phase1.sh
```

Expected: exit code 0. The output walks these stages:
1. Preflight
2. Build images
3. Check .env values without printing them
4. Start the stack and wait for health (then api and worker are recreated)
5. Backend test suite (`pytest: 1130 passed …`)
6. Frontend checks (`vitest: Test Files 6 passed (6); Tests 35 passed (35)`)
7. Web dev server serves every nav route and proxies /api
8. Accounts via the CLI
9. Login with curl cookie jars
10. RBAC
11. Admin run: enqueue and complete
12. CSRF
13. Browser check (Chromium in a container on the compose network)
14. Kill the worker during hello.echo and resume
15. Secrets
16. Runtime invariants
17. Sign out and close the throwaway accounts
18. Optional owner check (an info line pointing at Step 17)

Parts of the output from the verified run:

```text
==> Admin run: enqueue and complete
  PASS  admin POST /api/blog-agent/runs (HTTP 202)
  PASS  run <uuid> reached SUCCEEDED
  PASS  3 steps, each SUCCEEDED once (hello.echo:SUCCEEDED:1 hello.finish:SUCCEEDED:1 hello.open_attempt:SUCCEEDED:1)
  PASS  run <uuid> has exactly 1 blog_llm_calls row
  PASS  worker JSON logs carry run_id and trace_id for run <uuid> (3 lines)
(excerpt skips the "==> CSRF" header and that stage's earlier checks; its last check follows)
  PASS  a forged X-Forwarded-For is ignored: login_attempts record the TCP peer for all 3 logins

==> Browser check (Chromium in a container on the compose network)
  PASS  browser: acceptance-admin-<timestamp>@example.test signs in at http://web:5173/login and lands on Dashboard
  PASS  browser: the sidebar lists the 11 nav items in spec order
  PASS  browser: sidebar link "Dashboard" opens / and renders its heading
  ...   (one line per sidebar link, 11 in total)
  PASS  browser: no uncaught JavaScript errors
  PASS  browser: "Generate today's blog" POST /api/blog-agent/runs passed the CSRF checks (202)
  PASS  browser: Sign out (POST /api/auth/logout 204); /agent-runs then leads to /login
  PASS  run <uuid> (created in the browser) reached SUCCEEDED

==> Kill the worker during hello.echo and resume
  PASS  worker recreated with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=15
  PASS  admin POST /api/blog-agent/runs (HTTP 202)
  PASS  hello.echo is RUNNING for run <uuid>
  PASS  docker compose kill worker (<utc time>)
  PASS  while the worker is down: run RESEARCHING, hello.echo still RUNNING, no gateway call recorded yet
  PASS  worker started again (same container, same executor id and APP_VERSION)
  PASS  run <uuid> resumed and reached SUCCEEDED
  ....  steps: hello.open_attempt SUCCEEDED tries=1, hello.echo SUCCEEDED tries=2, hello.finish SUCCEEDED tries=1
  PASS  completed steps were not repeated: hello.open_attempt tries=1, hello.finish tries=1
  PASS  only the interrupted step re-ran: hello.echo tries=2
  PASS  blog_llm_calls for run <uuid>: 1 row on the hello.echo step, ok (no duplicate call after resume)
  ....  worker log lines mentioning recovery since the kill: 1
  PASS  worker recreated with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0

==> Secrets
  PASS  no configured secret value appears in the api/worker logs (<k> secret values checked, <n> distinct log lines)
  PASS  docker compose logs api worker | grep -E 'sk-|AIza' finds nothing (<n> distinct log lines checked)
  PASS  GET /api/blog-agent/settings as admin (HTTP 200)
  PASS  settings return provider keys masked (OK anthropic=<configured|unset> gemini=… ncbi=… openai=…)
(excerpt skips the rest of Secrets and the stages "Runtime invariants", "Sign out and close the throwaway accounts" and "Optional owner check")
PHASE 1 ACCEPTANCE: PASS (83 checks, 0 warnings)
```

`<k>` counts the secrets that are set and at least 12 characters long; it was 9 in the verified run.

**Reading the final line.**
- A full run ends with exactly `PASS (83 checks, 0 warnings)`. Record that line in the checkpoint.
- `SKIP_SUITES=1` gives `PASS (79 checks, 1 warnings)`: the four suite checks are skipped and a warning says so. That run does not count as the acceptance run.
- **Any other warning** comes from the literal `grep -E 'sk-|AIza'`. It matched log text that is neither key-shaped nor a configured secret, and the script prints the masked context just above the warning. Read that context, and report the warning with the result.
- **Empty `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD`** fail the run at "Check .env values"; hand Step 2's instruction to the owner.

**Where to look when a stage fails.** The script prints the failing check and exits. Its trap always:
- resets the worker delay to 0;
- signs the throwaway accounts out;
- deactivates them;
- removes its temp folder.

| Failing stage | Most likely owner | Look at |
|---|---|---|
| Start the stack | Task 14 compose / Task 11 worker | `docker compose ps -a`; masked `docker compose logs <svc>` |
| Backend test suite | the task that owns the failing test | `docker compose run --rm tools pytest -q -x` |
| Frontend checks | Task 13 | `docker compose run --rm web npm test` / `docker compose run --rm web npm run lint` / `docker compose run --rm web npm run build` |
| Nav routes / proxy 401 | Task 13 (`vite.config.ts`), Task 9 (401 title) | `curl -si http://127.0.0.1:8310/api/auth/session` |
| Accounts via the CLI | Task 8 | `docker compose exec api python -m mdcopilot_blog.cli --help`; for exit 2, the reason line the script printed |
| Login / RBAC | Tasks 7 and 9 | `docker compose logs api` |
| Admin run (steps, calls) | Tasks 11 and 12 | `docker compose logs worker`; `GET /api/blog-agent/runs/<id>` |
| Admin run (no `run_id`/`trace_id` log line) | Task 11 (`track_step` "step finished" log), Task 3 (`JsonFormatter`) | `docker compose logs --no-color worker \| grep -F '"run_id"'` |
| CSRF | Task 9 (`enforce_csrf`, `origin_allowed`) | the `label=status\|title` line the script printed |
| Forged X-Forwarded-For | Task 14 compose (`--no-proxy-headers`), Task 9 (`_client_ip`) | `docker inspect -f '{{json .Args}}' "$(docker compose ps -q api)"` |
| Browser check | Task 13 (DOM contract under Interfaces); a 403 on Generate: Task 9 | the `key=value` lines the script printed (`login`, `nav`, `page:/…`, `generate`, `logout`, `error`) |
| Kill and resume: run `TOPICS_READY` right after the kill, or 2 `blog_llm_calls` rows | Task 11 (`echo_step` must sleep before `gateway.run`; see the top of this task) | `grep -n -A3 'await _mock_delay' backend/src/mdcopilot_blog/workflows/hello.py` |
| Kill and resume (other) | Task 11 (`track_step`, `hello.py`, `worker.py`) | the steps line; `docker compose logs worker` |
| Secrets | Tasks 3 and 9 (log formatter, `mask_secret`) | the masked context the script printed; `docker compose logs api worker \| grep -Eo '.{0,30}(sk-\|AIza).{0,4}'` (shows at most 4 characters of a match) |
| Runtime invariants | Task 11 (`apply_daily_schedule`) | `select schedule_name, status from dbos.workflow_schedules` |

**Verified failure message.** With the old `echo_step` order (gateway call before the delay), the run stops at the kill stage with `FAIL  run <uuid> is TOPICS_READY right after the kill, expected RESEARCHING (killed before the gateway call)`.

Fix the owning task's code, then re-run with `SKIP_SUITES=1 scripts/acceptance/phase1.sh` for a faster loop. Finish with one full run.

- [ ] **Step 12: Write `docs/blog-agent/LOCAL_DEVELOPMENT.md`**

Create `docs/blog-agent/LOCAL_DEVELOPMENT.md` with exactly this content:

````markdown
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
3. Set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` (at least 12 characters) for the first admin account.
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
````

Check that every relative link in it resolves:

```bash
grep -o '](\([A-Z_]*\.md\))' docs/blog-agent/LOCAL_DEVELOPMENT.md | sort -u | sed 's/](\(.*\))/\1/' | while read -r f; do test -f "docs/blog-agent/$f" && echo "ok $f" || echo "MISSING $f"; done
```

Expected: four `ok` lines (`ARCHITECTURE.md`, `FRAMEWORK_EVALUATION.md`, `IMPLEMENTATION_PLAN.md`, `RESEARCH_ARCHITECTURE.md`) and no `MISSING`.

- [ ] **Step 13: Update `docs/blog-agent/ARCHITECTURE.md`**

Apply these exact replacements. Each "Replace" text occurs once in the file.

**13a. §3 table, `migrate` row.** Replace:

```text
| `migrate` | `backend` | `alembic upgrade head` | — | One-shot. `api`/`worker` wait for `service_completed_successfully`. |
```

with:

```text
| `migrate` | `backend` (`dev`) | `python -m mdcopilot_blog.cli migrate` (Alembic upgrade, DBOS system migrations, seed, prompt sync) | — | One-shot. `api`/`worker` wait for `service_completed_successfully`. |
```

**13b. §3 table, `api` row.** Replace:

```text
| `api` | `backend` | `uvicorn app.main:app` (`--reload` + bind mount in dev) | `127.0.0.1:8300` | **Never calls `DBOS.launch()`**. Uses `DBOSClient` only. |
```

with:

```text
| `api` | `backend` | `uvicorn --factory mdcopilot_blog.api.app:create_app` (`--reload` + bind mount in dev) | `127.0.0.1:8300` | **Never calls `DBOS.launch()`**. Uses `DBOSClient` only. |
```

**13c. §3 table, `worker` row.** Replace:

```text
| `worker` | `backend` | `python -m app.worker` | — | `DBOS.launch()` with fixed `executor_id` and explicit `application_version`. `stop_grace_period: 60s`. `extra_hosts: host.docker.internal:host-gateway` for the dev publisher. |
```

with:

```text
| `worker` | `backend` | `python -m mdcopilot_blog.worker` | — | `DBOS.launch()` with fixed `executor_id` (`WORKER_EXECUTOR_ID=worker-1`) and explicit `application_version` (`APP_VERSION`). `stop_grace_period: 40s` (`DBOS.destroy` waits up to 25 s). Healthcheck on a heartbeat file. `extra_hosts: host.docker.internal:host-gateway` for the dev publisher. |
```

**13d. §3 bootstrap commands.** Replace:

```text
docker run --rm -v "$PWD/backend:/app" -w /app ghcr.io/astral-sh/uv:0.12.15 uv lock
```

with:

```text
docker run --rm -v "$PWD/backend:/work" -w /work -e UV_PYTHON_DOWNLOADS=0 ghcr.io/astral-sh/uv:0.12.15-python3.12-trixie-slim uv lock
```

This is the command verified on 2026-09-17. The plain `uv:0.12.15` image has no Python 3.12 and would download one.

**13e. §4 layout.** Replace the whole fenced `text` block under `## 4. Code layout`, which is currently:

````text
```text
mdcopilot-blog/
├── compose.yaml · .env · .env.example · .gitignore
├── docs/blog-agent/   ARCHITECTURE · FRAMEWORK_EVALUATION · RESEARCH_ARCHITECTURE ·
│                      IMPLEMENTATION_PLAN · LOCAL_DEVELOPMENT (Phase 1) · plans/phase-N.md
├── backend/
│   ├── Dockerfile · pyproject.toml · uv.lock · alembic.ini · migrations/
│   ├── prompts/{research,ideation,deep_research,writer,fact_checker,clinical_reviewer,editor,seo}/<name>.v<N>.md
│   ├── fixtures/mock/          recorded feeds, search responses, pages, PDFs, LLM outputs
│   ├── app/
│   │   ├── main.py · worker.py · cli.py
│   │   ├── core/          settings, logging, ids, clock, errors
│   │   ├── domain/        typed contracts (§12), state machines, scoring, novelty & diversity rules,
│   │   │                  quality gates, article assembly/parsing — pure, no I/O
│   │   ├── persistence/   SQLAlchemy 2 async models + repositories
│   │   ├── api/           routers, schemas, dependencies, RBAC
│   │   ├── auth/          users, sessions, password hashing, CSRF
│   │   ├── llm/           LLMGateway (agents, web search, embeddings), routes, provider adapters,
│   │   │                  pricing, call recorder, mock models — the ONLY place provider SDKs are imported
│   │   ├── research/      query planning, feed collectors, retriever, extractor, ledger, tiers
│   │   ├── agents/        one module per agent: prompt id, input builder, output type
│   │   ├── workflows/     DBOS workflows, steps, queues, schedules, control workflows
│   │   ├── publishing/    BlogPublisher protocol, renderer, manual export, MDCopilot API, sync of MDCopilot posts
│   │   └── observability/ OpenTelemetry setup, metrics SQL
│   └── tests/             unit · agents · workflows · failure · api
└── frontend/
    ├── Dockerfile · nginx.conf · package.json · vite.config.ts
    └── src/  routes · pages · components · api (generated types) · lib
```
````

with:

````text
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
````

**13f. §4 layering rule and a note on paths.** Replace:

```text
- Those call `llm` and `persistence`.
- `domain` depends on nothing.
- Agents never touch the database, and prompts contain no database logic.
```

with:

```text
- Those call `llm` and `db` (the persistence layer).
- `domain` depends on nothing.
- Agents never touch the database, and prompts contain no database logic.

**Paths elsewhere in these docs.** Other sections and the companion documents write module paths as `app/<package>/` (for example `app/llm/search/`). Read them as `backend/src/mdcopilot_blog/<package>/`.
```

**13g. §16 auth line.** Replace:

```text
/api/auth/login · /logout · /me     /api/admin/users (CRUD, roles)     /healthz · /readyz
```

with:

```text
/api/auth/login · /logout · /session     /api/admin/users (CRUD, roles)     /healthz · /readyz
```

**13h. §17 first admin.** Replace:

```text
The first admin is created with `docker compose run --rm api python -m app.cli create-admin`, and admins invite everyone else.
```

with:

```text
The first admin is created with `docker compose exec api sh -c 'python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner'` (password from `BOOTSTRAP_ADMIN_PASSWORD`; see LOCAL_DEVELOPMENT.md §7), and admins invite everyone else.
```

**13i. §18 health sentence.** Replace:

```text
`/healthz` and `/readyz` report database status and the worker heartbeat.
```

with:

```text
`/healthz` reports liveness and `/readyz` reports database status. The worker's health is its heartbeat file (`/tmp/worker-heartbeat`), which the compose healthcheck reads.
```

**13j. §6 run line (only if the owner answered "yes" in Task 4 Step 0).** Look up the answer recorded in Task 4's checkpoint. If it says "`WAITING_FOR_TOPIC → FAILED`: not added", or nothing was recorded, skip this edit. If it says "added", replace:

```text
**Run** (`blog_runs.status`): `QUEUED → RESEARCHING → TOPICS_READY → (WAITING_FOR_TOPIC | PRODUCING) → SUCCEEDED | FAILED | CANCELLED`
```

with:

```text
**Run** (`blog_runs.status`): `QUEUED → RESEARCHING → TOPICS_READY → (WAITING_FOR_TOPIC | PRODUCING) → SUCCEEDED | FAILED | CANCELLED`. Also `WAITING_FOR_TOPIC → FAILED` (a follow-up workflow failed while waiting for a topic).
```

Check that the doc matches the code:

```bash
grep -c 'RunStatus.WAITING_FOR_TOPIC: {$' backend/src/mdcopilot_blog/domain/state_machine.py
grep -c 'WAITING_FOR_TOPIC → FAILED' docs/blog-agent/ARCHITECTURE.md
```

Expected: both print `0` (no edge), or both print `1` (edge added). The first command matches only the multi-line `WAITING_FOR_TOPIC` set that the "yes" version of Task 4 writes; the "no" version keeps that set on one line.

- [ ] **Step 14: Update `docs/blog-agent/IMPLEMENTATION_PLAN.md`**

**14a. Phase 1 build, core modules.** Replace:

```text
- **`app/core`.** Settings from `.env` (secrets as `SecretStr`); structured JSON logs carrying `run_id` and `trace_id`.
```

with:

```text
- **Core modules** (`backend/src/mdcopilot_blog/settings.py`, `logs.py`, `ids.py`, `errors.py`). Settings from `.env` (secrets as `SecretStr`); structured JSON logs carrying `run_id` and `trace_id`.
```

**14b. Phase 1 build, auth CLI.** Replace:

```text
login rate limit, and `python -m app.cli create-admin`.
```

with:

```text
login rate limit, and `python -m mdcopilot_blog.cli create-admin`.
```

**14c. Spike S1 result.** Replace:

```text
Pin 3.0.x only if everything passes. Otherwise pin `>=2.31.1,<3`. Record the result in `plans/phase-1.md`.
```

with:

```text
**Result:** passed in research on 2026-09-17; pinned `dbos==3.0.0`; re-verified by Task 11 tests and the Task 14 acceptance run (`scripts/acceptance/phase1.sh`). Details are in `plans/phase-1.md`.
```

**14d. Status line (only after the full Step 11 run passed).** Replace:

```text
Status: Phase 0 complete (this document set); **Phase 1 waits for owner approval**
```

with:

```text
Status: Phase 0 complete (this document set); **Phase 1 built; acceptance passed 2026-09-17** (`scripts/acceptance/phase1.sh`)
```

Write the date of the passing full run (`date +%F` on the day of Step 11) in place of `2026-09-17`. If Step 11 has not passed yet, skip this edit and say so in the checkpoint.

**14e. Phase 10, trusted proxy.** Replace:

```text
- **Production Compose profile.** nginx web, no reload, resource limits, restart policies, digest-pinned images.
```

with:

```text
- **Production Compose profile.** nginx web, no reload, resource limits, restart policies, digest-pinned images.
- **Client addresses behind the proxy.** The dev `api` ignores proxy headers (`--no-proxy-headers`), and the runtime image's default command still trusts every sender (`--forwarded-allow-ips "*"`). For production, trust only the nginx container's address. nginx must set `X-Forwarded-For` to `$remote_addr`, not append to it with `$proxy_add_x_forwarded_for`. Otherwise clients choose the IP that the login rate limit records.
```

- [ ] **Step 15: Verify the doc edits**

Run:

```bash
grep -nE 'app\.cli|app\.main|app\.worker|/me |persistence`|app/core' docs/blog-agent/ARCHITECTURE.md docs/blog-agent/IMPLEMENTATION_PLAN.md .env.example || echo "no stale references"
grep -c 'mdcopilot_blog' docs/blog-agent/ARCHITECTURE.md
grep -n 'Result:\*\* passed in research on 2026-09-17' docs/blog-agent/IMPLEMENTATION_PLAN.md
grep -n '/logout · /session' docs/blog-agent/ARCHITECTURE.md
grep -n '^Status:' docs/blog-agent/IMPLEMENTATION_PLAN.md
grep -c 'Client addresses behind the proxy' docs/blog-agent/IMPLEMENTATION_PLAN.md
grep -rn 'create-admin --email' docs/blog-agent/ARCHITECTURE.md docs/blog-agent/LOCAL_DEVELOPMENT.md .env.example | grep -v 'docker compose exec api sh -c' | grep -v 'docker compose run --rm tools sh -c' || echo "one create-admin form"
```

Expected:
1. `no stale references`;
2. a count of at least 6;
3. one matching line in `IMPLEMENTATION_PLAN.md`;
4. one matching line in `ARCHITECTURE.md`;
5. ``3:Status: Phase 0 complete (this document set); **Phase 1 built; acceptance passed <date>** (`scripts/acceptance/phase1.sh`)``, or the old line if Step 14d was skipped;
6. `1`;
7. `one create-admin form`. The first-admin command is `docker compose exec api sh -c '…'` everywhere; the only other form is LOCAL_DEVELOPMENT §7's `tools` variant for a stopped stack.

`app/llm` and `app/research` mentions in later-phase text and in the companion documents are intentional; the §4 note covers them.

- [ ] **Step 16: Final verification (run every line; record the results in the checkpoint)**

The stack is up from Step 9 or Step 11. Run each command from `mdcopilot-blog/`:

| # | Command | Expected result |
|---|---|---|
| 1 | `docker compose run --rm tools sh -c "ruff check . && ruff format --check . && mypy src"` | `All checks passed!`, then `111 files already formatted`, then `Success: no issues found in 62 source files` (Task 12 Step 16's counts; this task adds no `.py` or `.md` file under `backend/`) |
| 2 | `docker compose run --rm tools alembic check` | `No new upgrade operations detected.` |
| 3 | `docker compose run --rm tools pytest -q` | `1130 passed` with no `failed` or `error`, from 40 test files. That is T1 4 + T2 47 + T3 24 + T4 727 + T5 11 + T6 15 + T7 54 + T8 17 + T9 95 + T10 58 + T11 35 + T12 43. By directory (`docker compose run --rm tools pytest tests/<dir> -q`): unit 901 (15 files), db 77 (11), api 116 (8), workflows 36 (6). Any other total means a task's tests are missing or extra; compare per directory. Record the number. |
| 4 | `docker compose run --rm web npm test` | `Test Files  6 passed (6)` and `Tests  35 passed (35)`, the counts Task 13 recorded; record the actual numbers |
| 5 | `docker compose run --rm web npm run lint` | exit 0, no problems reported |
| 6 | `docker compose run --rm web npm run typecheck` | exit 0, no output from `tsc` |
| 7 | `docker compose run --rm web npm run build` | `✓ built in …`. The warning about chunks over 500 kB is acceptable. |
| 8 | `docker build --target prod -t mdcopilot-blog-web:prod frontend` | build succeeds (Task 13's nginx target) |
| 9 | the Step 7 runtime-image commands | `999`, `no uv`, `no pytest`, `/app/prompts 1 5 True`, CLI usage |
| 10 | `grep -rIlE --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=tests --exclude='*.test.ts' --exclude='*.test.tsx' 'sk-[A-Za-z0-9_-]{16,}\|AIza[0-9A-Za-z_-]{30,}' backend frontend docs scripts compose.yaml .env.example \|\| echo "no key-shaped strings"` | `no key-shaped strings` (no real key was copied into a file) |
| 11 | `scripts/acceptance/phase1.sh` | exit 0 and `PHASE 1 ACCEPTANCE: PASS (83 checks, 0 warnings)`. A warning is acceptable only from the literal `sk-\|AIza` grep, after reading the masked context the script printed (Step 11); report it. |
| 12 | `docker compose ps -a --format 'table {{.Service}}\t{{.Status}}'` | `api`, `db`, `web` and `worker` are `Up … (healthy)`; `migrate` is `Exited (0)` |
| 13 | `docker compose exec -T worker printenv BLOG_AGENT_MOCK_STEP_DELAY_SECONDS` | `0` (the acceptance run restored the default) |

(In row 10, type the command with plain `|` characters; the backslashes are only Markdown table escapes.)

If a row fails, fix the owning task (see the table in Step 11) and re-run from that row, then run row 11 again.

- [ ] **Step 17: Optional owner check in your own browser**

Step 11 already signs in with Chromium at `http://web:5173`, opens every sidebar page, and presses "Generate today's blog" and "Sign out". That run uses the throwaway admin, because the script never reads the bootstrap password; the bootstrap admin's login is checked through the API. This step is an optional extra that the owner does on their own machine, at http://localhost:8310:
1. **Sign-in.** Sign in with `BOOTSTRAP_ADMIN_EMAIL`. Expected: the Dashboard loads with the "Generate today's blog" button and a "Recent runs" table that includes the four runs from the acceptance run.
2. **Sidebar pages.** Click every sidebar entry in order: Dashboard, Today's Ideas, Research, Drafts, Review Queue, Published, Topics, Content Calendar, Sources, Settings, Agent Runs. Expected: each page renders. Placeholders say "Arrives in a later phase."; Agent Runs lists runs.
3. **Viewer menu** (optional). Create a viewer with the `create-user` command in LOCAL_DEVELOPMENT.md §7 and sign in as that user. Expected: 8 sidebar entries, with no Review Queue, Settings or Agent Runs. Opening `/settings` directly shows the "Access denied" page.
4. **Sign out.** Use the user menu. Expected: you return to `/login`.

- [ ] **Step 18: Stopping and cleaning up (for the record; do not run as part of the task)**

| Command | Effect |
|---|---|
| `docker compose down` | Stops and removes the containers. The `blog_pgdata` volume, and with it every user, run and setting, is kept. |
| `docker compose --profile tools down` | Also removes any leftover `tools` container. |
| `docker compose down -v` | **Deletes the database volume.** Run it only when the owner explicitly asks for a reset, and after a backup (`LOCAL_DEVELOPMENT.md` §10). |
| `docker image rm mdcopilot-blog-backend:runtime mdcopilot-blog-web:prod` | Optional. Removes the two verification images built in Steps 7 and 16. |
| `docker image rm mcr.microsoft.com/playwright:v1.63.0-noble` | Optional. Frees about 2 GB; the next acceptance run pulls the image again. |

Other leftovers:
- Each acceptance run leaves four mock runs and two deactivated `acceptance-*@example.test` accounts in the dev database. They are harmless.
- `frontend/dist/` from row 7 is git-ignored.
- The script's curl and Playwright containers run with `--rm` and leave nothing behind.

- [ ] **Step 19: Checkpoint: list the files changed in this task (no git)**

```bash
ls -l compose.yaml backend/Dockerfile scripts/acceptance/phase1.sh docs/blog-agent/LOCAL_DEVELOPMENT.md docs/blog-agent/ARCHITECTURE.md docs/blog-agent/IMPLEMENTATION_PLAN.md .env.example
```

Report the list (include `backend/Dockerfile` only if Step 6 replaced it), plus these recorded results:
- the pytest count (row 3);
- the vitest counts (row 4);
- the final acceptance line (row 11), and any warning with its masked context;
- whether Step 14d was applied, and with which date;
- whether Step 13j was applied (the Task 4 Step 0 answer on `WAITING_FOR_TOPIC → FAILED`);
- what changed in `.env.example`. Expected: only the line-27 comment (Step 3); no variable was added.
- the six contract deviations listed at the top of this task, for the owner's approval.

`.env` is untouched. Tell the owner:
- If your `.env` was copied from `.env.example`, it still carries the old `# First admin account, created with: docker compose run --rm api python -m app.cli create-admin` comment. It is only a comment, so nothing breaks. If you want it to match, replace it with the comment line from Step 3.
- Do not export `POSTGRES_PASSWORD` (or `POSTGRES_DB`/`POSTGRES_USER`) in your shell. `db` reads them through compose interpolation, and a shell value would override `.env` for `db` only.
