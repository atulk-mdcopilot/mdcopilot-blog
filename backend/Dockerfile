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
