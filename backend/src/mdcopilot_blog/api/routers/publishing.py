"""Human-controlled export, publishing and scheduling."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from mdcopilot_blog.api.deps import Principal, SessionDep, SettingsDep, WorkflowClientDep, require_permission
from mdcopilot_blog.api.schemas_common import ActionAccepted, ArticleStateOut
from mdcopilot_blog.api.schemas_publishing import (
    ConfirmPublishedRequest,
    ExportBundleOut,
    PreviewOut,
    PublicationOut,
    PublishRequest,
    ScheduleRequest,
)
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.services import publications

router = APIRouter(tags=["publishing"])
View = Annotated[Principal, Depends(require_permission(Permission.VIEW))]
Publish = Annotated[Principal, Depends(require_permission(Permission.PUBLISH))]
Schedule = Annotated[Principal, Depends(require_permission(Permission.SCHEDULE))]


@router.get("/articles/{article_id}/preview", response_model=PreviewOut)
async def preview(
    article_id: uuid.UUID,
    db: SessionDep,
    _: View,
    version_id: Annotated[uuid.UUID | None, Query(alias="versionId")] = None,
) -> PreviewOut:
    return await publications.preview_article(db, article_id=article_id, version_id=version_id)


@router.post("/articles/{article_id}/export", response_model=ExportBundleOut)
async def export(article_id: uuid.UUID, db: SessionDep, principal: Publish) -> ExportBundleOut:
    return await publications.export_article(db, article_id=article_id, principal=principal)


@router.post("/articles/{article_id}/confirm-published", response_model=ArticleStateOut)
async def confirm(
    article_id: uuid.UUID, body: ConfirmPublishedRequest, db: SessionDep, principal: Publish
) -> ArticleStateOut:
    return await publications.confirm_published(
        db, article_id=article_id, principal=principal, url=body.url, now=datetime.now(UTC)
    )


@router.post("/articles/{article_id}/publish", response_model=ActionAccepted, status_code=202)
async def publish(
    article_id: uuid.UUID,
    body: PublishRequest,
    db: SessionDep,
    settings: SettingsDep,
    client: WorkflowClientDep,
    principal: Publish,
) -> ActionAccepted:
    return await publications.request_publish(
        db, article_id=article_id, principal=principal, settings=settings, client=client, as_draft=body.as_draft
    )


@router.post("/articles/{article_id}/schedule", response_model=ArticleStateOut)
async def schedule(
    article_id: uuid.UUID, body: ScheduleRequest, db: SessionDep, settings: SettingsDep, principal: Schedule
) -> ArticleStateOut:
    return await publications.schedule_article(
        db, article_id=article_id, principal=principal, settings=settings, at=body.at
    )


@router.post("/articles/{article_id}/unschedule", response_model=ArticleStateOut)
async def unschedule(
    article_id: uuid.UUID, db: SessionDep, settings: SettingsDep, principal: Schedule
) -> ArticleStateOut:
    return await publications.schedule_article(
        db, article_id=article_id, principal=principal, settings=settings, at=None
    )


@router.get("/articles/{article_id}/publications", response_model=list[PublicationOut])
async def listing(article_id: uuid.UUID, db: SessionDep, _: View) -> list[PublicationOut]:
    return await publications.list_publications(db, article_id)
