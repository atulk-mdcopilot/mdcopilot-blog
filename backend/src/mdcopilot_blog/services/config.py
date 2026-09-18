"""Effective configuration loader.

Precedence: code defaults < Settings (env) < the active ``blog_settings.values`` row; a run's
``wordCount`` parameter overlays the word count for that run only. Safety switches are env-only
and never read from ``blog_settings``.
"""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas_settings import (
    PillarOut,
    SettingsUpdate,
)
from mdcopilot_blog.db.models import BlogRun, BlogSetting, BrandProfile, ContentPillar, PromptVersion
from mdcopilot_blog.domain.config import (
    BrandProfileValues,
    DiversityConfig,
    EffectiveConfig,
    NoveltyConfig,
    ResearchConfig,
    ScheduleConfig,
    ScoreWeights,
    SettingsValues,
    WordCountRange,
)
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import PublisherKey
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.services.enqueue import enqueue_workflow
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.names import QUEUE_INTERACTIVE, WORKFLOW_APPLY_SCHEDULE


class ConfigError(RuntimeError):
    """Stored configuration values failed validation."""


def _env_effective_config(settings: Settings) -> EffectiveConfig:
    return EffectiveConfig(
        schedule=ScheduleConfig(time=settings.daily_run_time, timezone=settings.timezone),
        topic_selection_mode="auto",
        word_count=WordCountRange(min=settings.word_count_min, max=settings.word_count_max),
        default_category=settings.default_category,
        site_url=settings.site_url,
        publisher=PublisherKey(settings.publisher),
        routes=settings.route_values(),
        prompt_versions={},
        score_weights=ScoreWeights(),
        novelty=NoveltyConfig(topic_threshold=settings.novelty_threshold),
        diversity=DiversityConfig(),
        research=ResearchConfig(window_days=settings.research_window_days, min_source_count=settings.min_source_count),
        gate_override_policy="admin_with_reason",
    )


async def load_effective_config(
    db: AsyncSession, settings: Settings, *, run_id: uuid.UUID | None = None
) -> EffectiveConfig:
    config = _env_effective_config(settings)

    row = await db.scalar(select(BlogSetting).where(BlogSetting.is_active))
    if row is not None:
        try:
            stored = SettingsValues.model_validate(row.values)
        except ValidationError as exc:
            raise ConfigError(f"active settings version {row.version} is invalid: {exc.error_count()} errors") from exc

        replacements: dict[str, object] = {}
        for name in (
            "schedule",
            "topic_selection_mode",
            "word_count",
            "default_category",
            "site_url",
            "publisher",
            "prompt_versions",
            "score_weights",
            "diversity",
            "research",
            "gate_override_policy",
        ):
            value = getattr(stored, name)
            if value is not None:
                replacements[name] = value
        if stored.routes is not None:
            replacements["routes"] = {**config.routes, **stored.routes}
        if stored.novelty is not None:
            replacements["novelty"] = stored.novelty
        elif stored.novelty_threshold is not None:
            replacements["novelty"] = NoveltyConfig(topic_threshold=stored.novelty_threshold)
        config = config.model_copy(update=replacements)

    if run_id is not None:
        run = await db.get(BlogRun, run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        word_count = run.params.get("wordCount")
        if isinstance(word_count, int) and not isinstance(word_count, bool):
            config = config.model_copy(
                update={"word_count": WordCountRange(min=round(word_count * 0.85), max=round(word_count * 1.15))}
            )

    return EffectiveConfig.model_validate(config.model_dump(mode="python", by_alias=False))


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


def local_date(now: datetime, tz: str) -> date:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(ZoneInfo(tz)).date()


async def config_lock(db: AsyncSession, name: str) -> None:
    # The advisory lock also serializes the first save, when no active row exists.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": f"blog-config:{name}"})


async def save_settings(
    db: AsyncSession, settings: Settings, principal: Principal, body: SettingsUpdate, client: WorkflowClient
) -> None:
    await config_lock(db, "settings")
    old = await db.scalar(select(BlogSetting).where(BlogSetting.is_active).with_for_update())
    if (old.version if old else None) != body.expected_version:
        raise ProblemError(409, "Settings version conflict", "Reload settings before saving your changes.")
    before = await load_effective_config(db, settings)
    if body.values.prompt_versions:
        for name, version in body.values.prompt_versions.items():
            if (
                await db.scalar(
                    select(PromptVersion.id).where(PromptVersion.name == name, PromptVersion.version == version)
                )
                is None
            ):
                raise ProblemError(422, "Request validation failed", f"Unknown prompt version: {name} v{version}")
    if old:
        old.is_active = False
        await db.flush()
    new = BlogSetting(
        version=int(await db.scalar(select(func.coalesce(func.max(BlogSetting.version), 0))) or 0) + 1,
        values=body.values.model_dump(mode="json", exclude_none=True),
        is_active=True,
        created_by=principal.user_id,
    )
    db.add(new)
    await db.flush()
    try:
        after = await load_effective_config(db, settings)
    except (ValueError, ValidationError) as exc:
        await db.rollback()
        raise ProblemError(422, "Request validation failed", str(exc)) from exc
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="settings.update",
        entity_type="blog_setting",
        entity_id=str(new.id),
        details={"version": new.version},
    )
    new_id, version, old_id = new.id, new.version, old.id if old else None
    await db.commit()
    if before.schedule == after.schedule:
        return
    try:
        await enqueue_workflow(
            client,
            workflow_name=WORKFLOW_APPLY_SCHEDULE,
            queue_name=QUEUE_INTERACTIVE,
            workflow_id=f"apply-schedule-v{version}",
            args=(),
            timeout_seconds=120,
        )
    except ProblemError:
        await config_lock(db, "settings")
        current = await db.scalar(select(BlogSetting).where(BlogSetting.is_active).with_for_update())
        # A concurrent successful save must never be rolled back by this request.
        if current and current.id == new_id:
            current.is_active = False
            await db.flush()
            if old_id:
                previous = await db.get(BlogSetting, old_id)
                if previous:
                    previous.is_active = True
        await audit(
            db,
            actor_user_id=principal.user_id,
            action="settings.update_reverted",
            entity_type="blog_setting",
            entity_id=str(new_id),
            details={"version": version},
        )
        await db.commit()
        raise


async def list_pillars(db: AsyncSession) -> list[PillarOut]:
    return [
        PillarOut.model_validate(row)
        for row in await db.scalars(select(ContentPillar).order_by(ContentPillar.sort_order, ContentPillar.key))
    ]
