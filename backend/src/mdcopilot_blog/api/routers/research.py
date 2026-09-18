"""Research execution and evidence browser."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from mdcopilot_blog.api.deps import Principal, SessionDep, require_permission
from mdcopilot_blog.api.schemas import Page
from mdcopilot_blog.api.schemas_research import ResearchRunDetail, ResearchRunOut
from mdcopilot_blog.domain.enums import Permission, ResearchRunKind
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.research_runs import get_research_run_detail, list_research_runs

router = APIRouter(tags=["research"])
CanView = Annotated[Principal, Depends(require_permission(Permission.VIEW))]


@router.get("/research-runs")
async def research_runs(
    db: SessionDep,
    _: CanView,
    run_id: Annotated[uuid.UUID | None, Query(alias="runId")] = None,
    article_id: Annotated[uuid.UUID | None, Query(alias="articleId")] = None,
    kind: ResearchRunKind | None = None,
    limit: Annotated[int, Query(ge=1)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ResearchRunOut]:
    items, total = await list_research_runs(
        db, run_id=run_id, article_id=article_id, kind=kind, limit=min(limit, 100), offset=offset
    )
    return Page(items=items, total=total, limit=min(limit, 100), offset=offset)


@router.get("/research-runs/{research_run_id}")
async def research_detail(research_run_id: uuid.UUID, db: SessionDep, _: CanView) -> ResearchRunDetail:
    result = await get_research_run_detail(db, research_run_id)
    if result is None:
        raise ProblemError(404, "Research run not found", f"no research run with id {research_run_id}")
    return result
