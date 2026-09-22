"""Effective configuration loader.

The effective config comes from Settings (env) only; a run's ``wordCount`` parameter overlays the word
count for that run. The brand profile and content pillars are seeded rows.
"""

import uuid
from datetime import date

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogRun, BrandProfile, ContentPillar
from mdcopilot_blog.domain.config import BrandProfileValues, EffectiveConfig, ResearchConfig, WordCountRange
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.settings import Settings


class ConfigError(RuntimeError):
    """Stored configuration values failed validation."""


async def load_effective_config(
    db: AsyncSession, settings: Settings, *, run_id: uuid.UUID | None = None
) -> EffectiveConfig:
    word_count = WordCountRange(min=settings.word_count_min, max=settings.word_count_max)
    if run_id is not None:
        run = await db.get(BlogRun, run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        requested = run.params.get("wordCount")
        if isinstance(requested, int) and not isinstance(requested, bool):
            word_count = WordCountRange(min=round(requested * 0.85), max=round(requested * 1.15))
    return EffectiveConfig(
        word_count=word_count,
        default_category=settings.default_category,
        site_url=settings.site_url,
        routes=settings.route_values(),
        research=ResearchConfig(window_days=settings.research_window_days, min_source_count=settings.min_source_count),
    )


async def load_brand_profile(db: AsyncSession) -> BrandProfileValues:
    row = await db.scalar(select(BrandProfile).where(BrandProfile.is_active))
    if row is None:
        raise LookupError("no active brand profile")
    try:
        return BrandProfileValues.model_validate(row.profile)
    except ValidationError as exc:
        raise ConfigError(f"active brand profile version {row.version} is invalid: {exc.error_count()} errors") from exc


async def pillar_for_date(db: AsyncSession, day: date) -> PillarKey | None:
    pillars = (
        await db.scalars(
            select(ContentPillar).where(ContentPillar.is_active).order_by(ContentPillar.sort_order, ContentPillar.key)
        )
    ).all()
    for pillar in pillars:
        if day.weekday() in pillar.weekdays:
            return PillarKey(pillar.key)
    return None
