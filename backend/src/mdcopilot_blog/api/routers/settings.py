"""Read-only view of the effective configuration. Provider keys are masked."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from mdcopilot_blog.api.deps import Principal, SessionDep, SettingsDep, WorkflowClientDep, require_permission
from mdcopilot_blog.api.schemas import SettingsView, mask_secret
from mdcopilot_blog.api.schemas_settings import (
    PillarOut,
    SettingsOut,
    SettingsUpdate,
)
from mdcopilot_blog.db.models import BlogSetting
from mdcopilot_blog.domain.config import SettingsValues
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.services.config import list_pillars, load_effective_config, save_settings
from mdcopilot_blog.settings import Settings

router = APIRouter(tags=["settings"])


def build_settings_view(settings: Settings) -> SettingsView:
    return SettingsView(
        app_version=settings.app_version,
        agent_enabled=settings.agent_enabled,
        scheduler_enabled=settings.scheduler_enabled,
        publishing_enabled=settings.publishing_enabled,
        human_approval_required=settings.human_approval_required,
        schedule={"dailyRunTime": settings.daily_run_time, "timezone": settings.timezone},
        routes=settings.route_values(),
        limits={
            "maxCostPerRunUsd": str(settings.max_cost_per_run_usd),
            "discoveryTimeoutMinutes": settings.discovery_timeout_minutes,
            "productionTimeoutMinutes": settings.production_timeout_minutes,
            "maxParallelSearches": settings.max_parallel_searches,
            "maxParallelFetches": settings.max_parallel_fetches,
            "researchWindowDays": settings.research_window_days,
            "minSourceCount": settings.min_source_count,
            "noveltyThreshold": settings.novelty_threshold,
            "wordCountMin": settings.word_count_min,
            "wordCountMax": settings.word_count_max,
        },
        publisher=settings.publisher,
        providers={
            "openai": mask_secret(settings.openai_api_key),
            "gemini": mask_secret(settings.gemini_api_key),
            "anthropic": mask_secret(settings.anthropic_api_key),
            "ncbi": mask_secret(settings.ncbi_api_key),
        },
    )


AdminDep = Annotated[Principal, Depends(require_permission(Permission.SETTINGS))]
ViewDep = Annotated[Principal, Depends(require_permission(Permission.VIEW))]


@router.get("/settings", response_model=SettingsOut)
async def get_settings_view(_: AdminDep, settings: SettingsDep, db: SessionDep) -> SettingsOut:
    view = build_settings_view(settings).model_dump(mode="python", by_alias=False)
    effective = await load_effective_config(db, settings)
    row = await db.scalar(select(BlogSetting).where(BlogSetting.is_active))
    view.update(
        schedule={"dailyRunTime": effective.schedule.time, "timezone": effective.schedule.timezone},
        routes=effective.routes,
        version=row.version if row else None,
        updated_at=row.created_at if row else None,
        updated_by=row.created_by if row else None,
        effective=effective,
        values=SettingsValues.model_validate(row.values) if row else SettingsValues(),
    )
    return SettingsOut.model_validate(view)


@router.put("/settings", response_model=SettingsOut)
async def put_settings(
    body: SettingsUpdate, principal: AdminDep, settings: SettingsDep, db: SessionDep, client: WorkflowClientDep
) -> SettingsOut:
    await save_settings(db, settings, principal, body, client)
    return await get_settings_view(principal, settings, db)


@router.get("/pillars", response_model=list[PillarOut])
async def get_pillars(_: ViewDep, db: SessionDep) -> list[PillarOut]:
    return await list_pillars(db)
