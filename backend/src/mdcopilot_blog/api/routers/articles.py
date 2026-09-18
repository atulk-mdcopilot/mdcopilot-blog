"""Article library, editing, regeneration, sources and immutable version history."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from mdcopilot_blog.api.deps import Principal, SessionDep, SettingsDep, WorkflowClientDep, require_permission
from mdcopilot_blog.api.schemas import Page
from mdcopilot_blog.api.schemas_articles import (
    ArticleDetailOut,
    ArticleEditRequest,
    ArticleSourceOut,
    ArticleSummaryOut,
    RegenerateRequest,
    ResearchPacketOut,
    SelectTitleRequest,
    VersionDetailOut,
    VersionDiffOut,
    VersionSummaryOut,
)
from mdcopilot_blog.api.schemas_common import ActionAccepted
from mdcopilot_blog.db.models import ArticleVersion
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import ArticleStatus, Permission
from mdcopilot_blog.services import article_views, articles

router = APIRouter(tags=["articles"])
CanView = Annotated[Principal, Depends(require_permission(Permission.VIEW))]
CanEdit = Annotated[Principal, Depends(require_permission(Permission.EDIT))]
CanGenerate = Annotated[Principal, Depends(require_permission(Permission.GENERATE))]


@router.get("/articles")
async def list_articles(
    db: SessionDep,
    _: CanView,
    view: Literal["all", "drafts", "review", "published"] = "all",
    status: Annotated[list[ArticleStatus] | None, Query()] = None,
    pillar: PillarKey | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ArticleSummaryOut]:
    return await article_views.list_articles(
        db, view=view, statuses=status, pillar=pillar, q=q, limit=min(limit, 100), offset=offset
    )


@router.get("/articles/{article_id}")
async def get_article(article_id: uuid.UUID, db: SessionDep, settings: SettingsDep, _: CanView) -> ArticleDetailOut:
    return await article_views.build_article_detail(db, await article_views.get_article(db, article_id), settings)


@router.patch("/articles/{article_id}")
async def edit_article(
    article_id: uuid.UUID,
    body: ArticleEditRequest,
    request: Request,
    db: SessionDep,
    settings: SettingsDep,
    principal: CanEdit,
) -> ArticleDetailOut:
    article = await articles.edit_article(
        db,
        article_id=article_id,
        body=body,
        principal=principal,
        settings=settings,
        sessionmaker=request.app.state.sessionmaker,
    )
    return await article_views.build_article_detail(db, article, settings)


@router.post("/articles/{article_id}/select-title")
async def select_title(
    article_id: uuid.UUID, body: SelectTitleRequest, db: SessionDep, settings: SettingsDep, principal: CanEdit
) -> ArticleDetailOut:
    return await article_views.build_article_detail(
        db, await articles.select_title(db, article_id=article_id, body=body, principal=principal), settings
    )


@router.post("/articles/{article_id}/regenerate", status_code=202)
async def regenerate(
    article_id: uuid.UUID,
    body: RegenerateRequest,
    db: SessionDep,
    settings: SettingsDep,
    client: WorkflowClientDep,
    principal: CanGenerate,
) -> ActionAccepted:
    return await articles.request_regeneration(
        db, client, article_id=article_id, body=body, principal=principal, settings=settings
    )


@router.get("/articles/{article_id}/versions")
async def versions(article_id: uuid.UUID, db: SessionDep, _: CanView) -> list[VersionSummaryOut]:
    await article_views.get_article(db, article_id)
    rows = (
        await db.scalars(
            select(ArticleVersion)
            .where(ArticleVersion.article_id == article_id)
            .order_by(ArticleVersion.version_no.desc())
        )
    ).all()
    return [await article_views.version_summary(db, row) for row in rows]


@router.get("/articles/{article_id}/versions/{version_id}")
async def version(article_id: uuid.UUID, version_id: uuid.UUID, db: SessionDep, _: CanView) -> VersionDetailOut:
    return await article_views.build_version_detail(db, article_id, version_id)


@router.get("/articles/{article_id}/diff")
async def diff(
    article_id: uuid.UUID, from_: Annotated[uuid.UUID, Query(alias="from")], to: uuid.UUID, db: SessionDep, _: CanView
) -> VersionDiffOut:
    return await article_views.build_version_diff(db, article_id, from_, to)


@router.get("/articles/{article_id}/sources")
async def sources(
    article_id: uuid.UUID,
    db: SessionDep,
    _: CanView,
    version_id: Annotated[uuid.UUID | None, Query(alias="versionId")] = None,
) -> list[ArticleSourceOut]:
    return await article_views.build_article_sources(db, await article_views.get_article(db, article_id), version_id)


@router.get("/articles/{article_id}/research-packets")
async def packets(article_id: uuid.UUID, db: SessionDep, _: CanView) -> list[ResearchPacketOut]:
    return await article_views.build_research_packets(db, article_id)
