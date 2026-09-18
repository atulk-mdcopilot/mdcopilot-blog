"""FastAPI application factory. uvicorn target: `uvicorn --factory mdcopilot_blog.api.app:create_app`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from mdcopilot_blog.api.deps import enforce_csrf
from mdcopilot_blog.api.hosts import allowed_hosts
from mdcopilot_blog.api.routers import articles as articles_routes
from mdcopilot_blog.api.routers import auth as auth_routes
from mdcopilot_blog.api.routers import dashboard as dashboard_routes
from mdcopilot_blog.api.routers import health as health_routes
from mdcopilot_blog.api.routers import publishing as publishing_routes
from mdcopilot_blog.api.routers import quality as quality_routes
from mdcopilot_blog.api.routers import research as research_routes
from mdcopilot_blog.api.routers import runs as runs_routes
from mdcopilot_blog.api.routers import settings as settings_routes
from mdcopilot_blog.api.routers import sources as sources_routes
from mdcopilot_blog.api.routers import topics as topics_routes
from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.errors import install_problem_handlers
from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.settings import Settings, get_settings
from mdcopilot_blog.workflows.client import WorkflowClient

# (router, prefix) in registration order.
ROUTERS: tuple[tuple[APIRouter, str], ...] = (
    (health_routes.router, ""),
    (auth_routes.router, "/api/auth"),
    (settings_routes.router, "/api/blog-agent"),
    (runs_routes.router, "/api/blog-agent"),
    (research_routes.router, "/api/blog-agent"),
    (sources_routes.router, "/api/blog-agent"),
    (topics_routes.router, "/api/blog-agent"),
    (articles_routes.router, "/api/blog-agent"),
    (quality_routes.router, "/api/blog-agent"),
    (publishing_routes.router, "/api/blog-agent"),
    (dashboard_routes.router, "/api/blog-agent"),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url())
    sessionmaker = make_sessionmaker(engine)
    client = WorkflowClient.from_settings(settings)
    # Deps read app.state first, so assign it as well as yielding lifespan state.
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.workflow_client = client
    try:
        yield {"settings": settings, "engine": engine, "sessionmaker": sessionmaker, "workflow_client": client}
    finally:
        await asyncio.to_thread(client.close)
        await engine.dispose()


def create_app() -> FastAPI:
    resolved = get_settings()
    app = FastAPI(
        title="MDCopilot Blog Intelligence API",
        version=resolved.app_version,
        lifespan=lifespan,
        dependencies=[Depends(enforce_csrf)],
        docs_url=None if resolved.app_env == "production" else "/docs",
        redoc_url=None if resolved.app_env == "production" else "/redoc",
        openapi_url=None if resolved.app_env == "production" else "/openapi.json",
    )
    app.state.settings = resolved
    install_problem_handlers(app)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts(resolved))
    for router, prefix in ROUTERS:
        app.include_router(router, prefix=prefix)
    return app
