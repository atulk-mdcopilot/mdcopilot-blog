"""FastAPI application factory. uvicorn target: `uvicorn --factory mdcopilot_blog.api.app:create_app`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI

from mdcopilot_blog import tracing
from mdcopilot_blog.api.deps import require_service
from mdcopilot_blog.api.routers import health as health_routes
from mdcopilot_blog.api.routers import runs as runs_routes
from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.errors import install_problem_handlers
from mdcopilot_blog.logs import configure_logging
from mdcopilot_blog.settings import Settings, get_settings
from mdcopilot_blog.workflows.client import WorkflowClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    tracing.init(settings)  # serves only the blog.run span that create_manual_run opens (§16.10.2, §16.10.3)
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
        await asyncio.to_thread(tracing.shutdown)  # blocks while it flushes, so never inline on the event loop
        await engine.dispose()


def create_app() -> FastAPI:
    resolved = get_settings()
    app = FastAPI(
        title="MDCopilot Blog Intelligence API",
        version=resolved.app_version,
        lifespan=lifespan,
        docs_url=None if resolved.app_env == "production" else "/docs",
        redoc_url=None if resolved.app_env == "production" else "/redoc",
        openapi_url=None if resolved.app_env == "production" else "/openapi.json",
    )
    app.state.settings = resolved
    install_problem_handlers(app)
    app.include_router(health_routes.router)  # probes: no auth
    app.include_router(runs_routes.router, prefix="/api/blog-agent", dependencies=[Depends(require_service)])
    return app
