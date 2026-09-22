"""Runs API (mounted under /api/blog-agent): create, list, read and cancel runs."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from mdcopilot_blog.api.deps import PrincipalDep, SessionDep, SettingsDep, WorkflowClientDep
from mdcopilot_blog.api.schemas import DraftOut, ManualRunRequest, Page, RunDetail, RunOut, StepOut
from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import RunStatus
from mdcopilot_blog.domain.state_machine import InvalidTransition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.runs import cancel_run, create_manual_run, get_run_detail, list_runs, load_drafts

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

router = APIRouter(tags=["runs"])


def run_not_found(run_id: uuid.UUID) -> ProblemError:
    return ProblemError(404, "Run not found", f"no run with id {run_id}")


def to_run_out(run: BlogRun, draft: DraftOut | None = None) -> RunOut:
    return RunOut(
        id=run.id,
        topic=run.params.get("topic", ""),
        status=RunStatus(run.status),
        stage=run.stage,
        error=run.error,
        cost_usd=run.cost_usd,
        created_by=run.created_by,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        draft=draft,
    )


@router.post("/runs", status_code=202)
async def create_run(
    db: SessionDep, settings: SettingsDep, client: WorkflowClientDep, principal: PrincipalDep, body: ManualRunRequest
) -> RunOut:
    run = await create_manual_run(db, client, principal=principal, request=body, settings=settings)
    return to_run_out(run)


@router.get("/runs")
async def get_runs(
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RunOut]:
    runs, total = await list_runs(db, limit=limit, offset=offset)
    drafts = await load_drafts(db, [run.id for run in runs])
    return Page[RunOut](
        items=[to_run_out(run, drafts.get(run.id)) for run in runs], total=total, limit=limit, offset=offset
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, db: SessionDep) -> RunDetail:
    found = await get_run_detail(db, run_id)
    if found is None:
        raise run_not_found(run_id)
    run, steps = found
    return RunDetail(
        **to_run_out(run, (await load_drafts(db, [run.id])).get(run.id)).model_dump(by_alias=False),
        steps=[StepOut.model_validate(step) for step in steps],
    )


@router.post("/runs/{run_id}/cancel")
async def cancel(run_id: uuid.UUID, db: SessionDep, client: WorkflowClientDep) -> RunOut:
    # Row lock, the same one set_run_status takes: cancels and worker status writes serialise.
    run = await db.get(BlogRun, run_id, with_for_update=True)
    if run is None:
        raise run_not_found(run_id)
    try:
        cancelled = await cancel_run(db, client, run=run)
    except InvalidTransition as exc:
        raise ProblemError(409, "Run cannot be cancelled", f"run is {exc.current}") from exc
    return to_run_out(cancelled)
