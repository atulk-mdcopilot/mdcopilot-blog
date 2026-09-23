# syntax=docker/dockerfile:1
# Same Python base image as mdcopilot-backend and mdcopilot-drive.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3 /uv /bin/uv
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# Optional image target for linting and working on bind-mounted source.
FROM builder AS dev
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
CMD ["uvicorn", "--factory", "mdcopilot_blog.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-proxy-headers"]

FROM python:3.12-slim AS runtime
RUN groupadd --system --gid 999 app \
 && useradd --system --gid 999 --uid 999 --create-home app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/prompts /app/prompts
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/alembic.ini /app/alembic.ini
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /app
USER app
EXPOSE 8000
CMD ["uvicorn", "--factory", "mdcopilot_blog.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
