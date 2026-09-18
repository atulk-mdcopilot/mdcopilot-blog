"""Catalogue loading: feeds, domain rules, themes from the database or seed files."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import ContentPillar, DiscoveryTheme, SourceDomain, SourceFeed
from mdcopilot_blog.domain.contracts import SourceType
from mdcopilot_blog.domain.enums import FeedKind
from mdcopilot_blog.domain.query_plan import ThemeState
from mdcopilot_blog.domain.tiers import DomainRule
from mdcopilot_blog.research.signals import FeedSpec


async def load_feed_specs(db: AsyncSession, *, enabled_only: bool = True) -> list[FeedSpec]:
    statement = select(SourceFeed).order_by(SourceFeed.group_name, SourceFeed.name)
    rows = (await db.scalars(statement)).all()
    specs: list[FeedSpec] = []
    for row in rows:
        if enabled_only and not row.is_enabled:
            continue
        specs.append(
            FeedSpec(
                id=row.id,
                name=row.name,
                url=row.url,
                kind=FeedKind(row.kind),
                group=row.group_name,
                tier=row.tier,
                source_type=SourceType(row.source_type),
                header_profile=str(row.header_profile),  # type: ignore[arg-type]
                quirks=dict(row.quirks or {}),
                is_preprint=bool(row.is_preprint),
                state=dict(row.state or {}),
                last_fetched_at=row.last_fetched_at,
            )
        )
    return specs


async def load_domain_rules(db: AsyncSession) -> dict[str, DomainRule]:
    rows = (await db.scalars(select(SourceDomain).order_by(SourceDomain.domain))).all()
    return {
        row.domain: DomainRule(
            domain=row.domain,
            tier=row.tier,
            source_type=SourceType(row.source_type),
            publisher=row.publisher,
            header_profile=str(row.header_profile),  # type: ignore[arg-type]
            fetch_policy=str(row.fetch_policy),  # type: ignore[arg-type]
            verification_allowlisted=bool(row.verification_allowlisted),
        )
        for row in rows
    }


async def load_theme_states(db: AsyncSession) -> list[ThemeState]:
    rows = (await db.scalars(select(DiscoveryTheme).order_by(DiscoveryTheme.sort_order, DiscoveryTheme.key))).all()
    return [
        ThemeState(
            key=row.key,
            name=row.name,
            query_templates=tuple(row.query_templates),
            pillar_keys=tuple(row.pillar_keys or []),
            is_active=bool(row.is_active),
            last_searched_at=row.last_searched_at,
            sort_order=row.sort_order,
        )
        for row in rows
    ]


async def load_pillar(db: AsyncSession, key: str | None) -> ContentPillar | None:
    if key is None:
        return None
    row = await db.scalar(select(ContentPillar).where(ContentPillar.key == key))
    return row if isinstance(row, ContentPillar) else None
