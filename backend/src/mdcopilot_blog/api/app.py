"""FastAPI application factory. uvicorn target: `uvicorn --factory mdcopilot_blog.api.app:create_app`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI

from mdcopilot_blog.api.deps import enforce_csrf
from mdcopilot_blog.api.routers import auth as auth_routes
from mdcopilot_blog.api.routers import health as health_routes
from mdcopilot_blog.api.routers import runs as runs_routes
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
    (runs_routes.router, "/api/blog-agent"),
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
