"""Source and discovery theme configuration routes."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from mdcopilot_blog.api.deps import Principal, SessionDep, require_permission
from mdcopilot_blog.api.schemas import Page
from mdcopilot_blog.api.schemas_sources import (
    LedgerSourceOut,
    SourceDomainOut,
    SourceDomainUpdate,
    SourceFeedOut,
    SourceFeedUpdate,
    ThemeOut,
    ThemesUpdate,
)
from mdcopilot_blog.domain.enums import AccessMode, Permission
from mdcopilot_blog.services import sources

router = APIRouter(tags=["sources"])
CanView = Annotated[Principal, Depends(require_permission(Permission.VIEW))]
CanSettings = Annotated[Principal, Depends(require_permission(Permission.SETTINGS))]


@router.get("/sources")
async def list_sources(
    db: SessionDep,
    _: CanView,
    domain: str | None = None,
    tier: Annotated[int | None, Query(ge=1, le=3)] = None,
    access_mode: Annotated[AccessMode | None, Query(alias="accessMode")] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[LedgerSourceOut]:
    items, total = await sources.list_sources(
        db, domain=domain, tier=tier, access_mode=access_mode, q=q, since=since, limit=min(limit, 100), offset=offset
    )
    return Page(items=items, total=total, limit=min(limit, 100), offset=offset)


@router.get("/sources/feeds")
async def feeds(db: SessionDep, _: CanView) -> list[SourceFeedOut]:
    return await sources.list_feeds(db)


@router.patch("/sources/feeds/{feed_id}")
async def update_feed(
    feed_id: uuid.UUID, body: SourceFeedUpdate, db: SessionDep, principal: CanSettings
) -> SourceFeedOut:
    return await sources.update_feed(db, feed_id=feed_id, update=body, principal=principal)


@router.get("/sources/domains")
async def domains(db: SessionDep, _: CanView) -> list[SourceDomainOut]:
    return await sources.list_domains(db)


@router.patch("/sources/domains/{domain_id}")
async def update_domain(
    domain_id: uuid.UUID, body: SourceDomainUpdate, db: SessionDep, principal: CanSettings
) -> SourceDomainOut:
    return await sources.update_domain(db, domain_id=domain_id, update=body, principal=principal)


@router.get("/themes")
async def themes(db: SessionDep, _: CanView) -> list[ThemeOut]:
    return await sources.list_themes(db)


@router.put("/themes")
async def update_themes(body: ThemesUpdate, db: SessionDep, principal: CanSettings) -> list[ThemeOut]:
    return await sources.replace_themes(db, update=body, principal=principal)
