"""Catalogue loading: domain rules and pillars from the database."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import ContentPillar, SourceDomain
from mdcopilot_blog.domain.contracts import SourceType
from mdcopilot_blog.domain.tiers import DomainRule


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


async def load_pillar(db: AsyncSession, key: str | None) -> ContentPillar | None:
    if key is None:
        return None
    row = await db.scalar(select(ContentPillar).where(ContentPillar.key == key))
    return row if isinstance(row, ContentPillar) else None
