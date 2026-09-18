"""Topics and novelty API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request

from mdcopilot_blog.api.deps import Principal, SessionDep, SettingsDep, WorkflowClientDep, require_permission
from mdcopilot_blog.api.schemas import Page
from mdcopilot_blog.api.schemas_common import ActionAccepted, ReasonRequest
from mdcopilot_blog.api.schemas_topics import (
    ExternalPostOut,
    SimilarityOut,
    TopicCandidateOut,
    TopicHistoryOut,
    TopicRoundOut,
    TopicSelectRequest,
    TopicsGenerateRequest,
    TopicUpdate,
)
from mdcopilot_blog.domain.enums import CandidateStatus, Permission
from mdcopilot_blog.services import topics
from mdcopilot_blog.services.novelty import nearest_neighbours
from mdcopilot_blog.services.step_context import build_api_step_context

router = APIRouter(tags=["topics"])
CanView = Annotated[Principal, Depends(require_permission(Permission.VIEW))]
CanGenerate = Annotated[Principal, Depends(require_permission(Permission.GENERATE))]
CanEdit = Annotated[Principal, Depends(require_permission(Permission.EDIT))]


@router.get("/topics")
async def get_topics(
    db: SessionDep,
    settings: SettingsDep,
    _: CanView,
    run_id: Annotated[uuid.UUID | None, Query(alias="runId")] = None,
    round_no: Annotated[int | None, Query(alias="round", ge=1)] = None,
    status: CandidateStatus | None = None,
) -> TopicRoundOut:
    return await topics.get_topic_round(db, settings=settings, run_id=run_id, round_no=round_no, status=status)


@router.get("/topics/history")
async def history(
    db: SessionDep,
    _: CanView,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TopicHistoryOut]:
    return await topics.list_history(db, q=q, limit=min(limit, 100), offset=offset)


@router.get("/topics/external-posts")
async def external_posts(
    db: SessionDep, _: CanView, limit: Annotated[int, Query(ge=1)] = 20, offset: Annotated[int, Query(ge=0)] = 0
) -> Page[ExternalPostOut]:
    return await topics.list_external_posts(db, limit=min(limit, 100), offset=offset)


@router.get("/topics/similar")
async def similar(
    request: Request,
    db: SessionDep,
    settings: SettingsDep,
    _: CanView,
    text: Annotated[str, Query(min_length=3, max_length=1000)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> SimilarityOut:
    sc = await build_api_step_context(
        settings=settings, sessionmaker=request.app.state.sessionmaker, run_id=None, article_id=None
    )
    vectors = await sc.gateway.embed([text], ctx=sc.call)
    return SimilarityOut(text=text, items=await nearest_neighbours(db, embedding=vectors[0], limit=limit))


@router.post("/topics/generate", status_code=202)
async def generate(
    body: TopicsGenerateRequest,
    db: SessionDep,
    settings: SettingsDep,
    client: WorkflowClientDep,
    principal: CanGenerate,
) -> ActionAccepted:
    return await topics.generate_topics(db, client, run_id=body.run_id, principal=principal, settings=settings)


@router.post("/topics/{candidate_id}/select", status_code=202)
async def select_topic(
    candidate_id: uuid.UUID,
    db: SessionDep,
    settings: SettingsDep,
    client: WorkflowClientDep,
    principal: CanGenerate,
    body: Annotated[TopicSelectRequest | None, Body()] = None,
) -> ActionAccepted:
    return await topics.select_candidate(
        db,
        client,
        candidate_id=candidate_id,
        confirm_warning=(body or TopicSelectRequest()).confirm_warning,
        principal=principal,
        settings=settings,
    )


@router.patch("/topics/{candidate_id}")
async def edit_topic(
    candidate_id: uuid.UUID, body: TopicUpdate, db: SessionDep, principal: CanEdit
) -> TopicCandidateOut:
    return await topics.update_candidate(db, candidate_id=candidate_id, update=body, principal=principal)


@router.post("/topics/{candidate_id}/reject")
async def reject_topic(
    candidate_id: uuid.UUID, body: ReasonRequest, db: SessionDep, principal: CanEdit
) -> TopicCandidateOut:
    return await topics.reject_candidate(db, candidate_id=candidate_id, reason=body.reason, principal=principal)
