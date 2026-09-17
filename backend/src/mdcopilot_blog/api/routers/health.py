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
