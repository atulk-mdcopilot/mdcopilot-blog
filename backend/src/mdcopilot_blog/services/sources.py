"""Source catalogue reads and audited configuration mutations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas_sources import (
    LedgerSourceOut,
    SourceDomainOut,
    SourceDomainUpdate,
    SourceFeedOut,
    SourceFeedUpdate,
    ThemeOut,
    ThemesUpdate,
)
from mdcopilot_blog.db.models import DiscoveryTheme, LedgerSource, SourceDomain, SourceFeed
from mdcopilot_blog.domain.enums import AccessMode
from mdcopilot_blog.domain.urls import normalize_host
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.audit import audit

MAX_ALLOWLISTED_DOMAINS = 100


def to_ledger_source_out(row: LedgerSource) -> LedgerSourceOut:
    return LedgerSourceOut.model_validate(row)


def to_feed_out(row: SourceFeed) -> SourceFeedOut:
    return SourceFeedOut.model_validate(
        {name: row.group_name if name == "group" else getattr(row, name) for name in SourceFeedOut.model_fields}
    )


async def list_sources(
    db: AsyncSession,
    *,
    domain: str | None,
    tier: int | None,
    access_mode: AccessMode | None,
    q: str | None,
    since: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[LedgerSourceOut], int]:
    stmt = select(LedgerSource)
    if domain:
        stmt = stmt.where(LedgerSource.domain == normalize_host(domain))
    if tier:
        stmt = stmt.where(LedgerSource.tier == tier)
    if access_mode:
        stmt = stmt.where(LedgerSource.access_mode == access_mode.value)
    if q and q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(LedgerSource.title.ilike(f"%{escaped}%", escape="\\"))
    if since:
        stmt = stmt.where(LedgerSource.published_at >= (since if since.tzinfo else since.replace(tzinfo=UTC)))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await db.scalars(
        stmt.order_by(LedgerSource.published_at.desc().nullslast(), LedgerSource.id.desc()).limit(limit).offset(offset)
    )
    return [to_ledger_source_out(row) for row in rows], total or 0


async def list_feeds(db: AsyncSession) -> list[SourceFeedOut]:
    return [
        to_feed_out(row)
        for row in await db.scalars(select(SourceFeed).order_by(SourceFeed.group_name, SourceFeed.name))
    ]


async def update_feed(
    db: AsyncSession, *, feed_id: uuid.UUID, update: SourceFeedUpdate, principal: Principal
) -> SourceFeedOut:
    row = await db.get(SourceFeed, feed_id, with_for_update=True)
    if row is None:
        raise ProblemError(404, "Feed not found", f"no feed with id {feed_id}")
    values = update.model_dump(mode="json", by_alias=False, exclude_unset=True)
    if "theme_keys" in values:
        known = set((await db.scalars(select(DiscoveryTheme.key))).all())
        unknown = set(values["theme_keys"]) - known
        if unknown:
            raise ProblemError(
                422,
                "Request validation failed",
                [
                    {
                        "type": "value_error",
                        "loc": ["body", "themeKeys"],
                        "msg": "unknown theme keys: " + ", ".join(sorted(unknown)),
                    }
                ],
            )
    for key, value in values.items():
        setattr(row, key, value)
    if "is_enabled" in values:
        row.disabled_reason = None if row.is_enabled else "disabled by an administrator"
        if row.is_enabled:
            row.consecutive_failures = 0
    if values:
        await audit(
            db,
            actor_user_id=principal.user_id,
            action="source_feed.update",
            entity_type="blog_source_feed",
            entity_id=str(row.id),
            details={"changes": update.model_dump(mode="json", exclude_unset=True)},
        )
        await db.commit()
    return to_feed_out(row)


async def list_domains(db: AsyncSession) -> list[SourceDomainOut]:
    return [
        SourceDomainOut.model_validate(row)
        for row in await db.scalars(select(SourceDomain).order_by(SourceDomain.domain))
    ]


async def update_domain(
    db: AsyncSession, *, domain_id: uuid.UUID, update: SourceDomainUpdate, principal: Principal
) -> SourceDomainOut:
    # Serialize allow-list capacity checks across different domain rows.
    await db.execute(text("SELECT pg_advisory_xact_lock(7081041)"))
    row = await db.get(SourceDomain, domain_id, with_for_update=True)
    if row is None:
        raise ProblemError(404, "Domain not found", f"no domain with id {domain_id}")
    if update.verification_allowlisted and not row.verification_allowlisted:
        count = await db.scalar(
            select(func.count()).select_from(SourceDomain).where(SourceDomain.verification_allowlisted.is_(True))
        )
        if (count or 0) >= MAX_ALLOWLISTED_DOMAINS:
            raise ProblemError(
                422,
                "Request validation failed",
                [
                    {
                        "type": "value_error",
                        "loc": ["body", "verificationAllowlisted"],
                        "msg": "at most 100 domains may be verification-allowlisted",
                    }
                ],
            )
    for key, value in update.model_dump(mode="json", by_alias=False, exclude_unset=True).items():
        setattr(row, key, value)
    if update.model_fields_set:
        await audit(
            db,
            actor_user_id=principal.user_id,
            action="source_domain.update",
            entity_type="blog_source_domain",
            entity_id=str(row.id),
            details={"changes": update.model_dump(mode="json", exclude_unset=True)},
        )
        await db.commit()
    return SourceDomainOut.model_validate(row)


async def list_themes(db: AsyncSession) -> list[ThemeOut]:
    return [
        ThemeOut.model_validate(row)
        for row in await db.scalars(select(DiscoveryTheme).order_by(DiscoveryTheme.sort_order, DiscoveryTheme.key))
    ]


async def replace_themes(db: AsyncSession, *, update: ThemesUpdate, principal: Principal) -> list[ThemeOut]:
    await db.execute(text("SELECT pg_advisory_xact_lock(7081042)"))
    rows = {row.key: row for row in await db.scalars(select(DiscoveryTheme).with_for_update())}
    created, updated, deactivated = [], [], []
    incoming = {item.key for item in update.items}
    for item in update.items:
        values = item.model_dump(mode="json", by_alias=False)
        if item.key in rows:
            for key, value in values.items():
                setattr(rows[item.key], key, value)
            updated.append(item.key)
        else:
            db.add(DiscoveryTheme(**values))
            created.append(item.key)
    for key, row in rows.items():
        if key not in incoming and row.is_active:
            row.is_active = False
            deactivated.append(key)
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="themes.update",
        entity_type="blog_discovery_theme",
        entity_id=None,
        details={"created": sorted(created), "updated": sorted(updated), "deactivated": sorted(deactivated)},
    )
    await db.commit()
    return await list_themes(db)
