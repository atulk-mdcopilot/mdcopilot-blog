# MD Copilot Blog

Docker-only internal blog generator: a FastAPI api and a DBOS worker, with no UI,
no users, and no database of its own (it uses the backend Postgres: `blog_*`
tables, `blog_alembic_versions`, schema `blog_dbos`). Root `docker-compose.yml`
services `blog-api` and `blog-worker`. Called only by mdcopilot-backend
(`/api/v1/admin/blog-agent/*`, ADMIN only); the worker saves each finished
article as a draft in the backend `blogs` table.

The workspace rules in the root `../AGENTS.md` apply here.

Docs: `README.md`, `docs/architecture.md`, `docs/business_logic.md`.
