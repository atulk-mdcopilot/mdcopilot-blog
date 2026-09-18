"""Version-specific review inspection and explicit human decisions."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from mdcopilot_blog.api.deps import Principal, SessionDep, SettingsDep, WorkflowClientDep, require_permission, utcnow
from mdcopilot_blog.api.schemas_common import ActionAccepted, ArticleStateOut, ReasonRequest
from mdcopilot_blog.api.schemas_quality import ApproveRequest
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.services import quality

router = APIRouter(tags=["quality"])
CanView = Annotated[Principal, Depends(require_permission(Permission.VIEW))]
CanGenerate = Annotated[Principal, Depends(require_permission(Permission.GENERATE))]
CanApprove = Annotated[Principal, Depends(require_permission(Permission.APPROVE))]
CanReview = Annotated[Principal, Depends(require_permission(Permission.REVIEW))]


@router.post("/articles/{article_id}/approve")
async def approve(
    article_id: uuid.UUID, body: ApproveRequest, db: SessionDep, settings: SettingsDep, principal: CanApprove
) -> ArticleStateOut:
    return quality.to_state_out(
        await quality.approve_article(
            db, article_id=article_id, request=body, principal=principal, settings=settings, now=utcnow()
        )
    )


@router.post("/articles/{article_id}/reject")
async def reject(article_id: uuid.UUID, body: ReasonRequest, db: SessionDep, principal: CanReview) -> ArticleStateOut:
    return quality.to_state_out(
        await quality.reject_article(db, article_id=article_id, request=body, principal=principal, now=utcnow())
    )


@router.post("/articles/{article_id}/recheck", status_code=202)
async def recheck(
    article_id: uuid.UUID, db: SessionDep, settings: SettingsDep, client: WorkflowClientDep, principal: CanGenerate
) -> ActionAccepted:
    return await quality.request_recheck(db, client, article_id=article_id, principal=principal, settings=settings)
