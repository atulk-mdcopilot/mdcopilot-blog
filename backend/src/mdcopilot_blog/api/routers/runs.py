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
