"""Read-only view of the effective configuration. Provider keys are masked."""

from typing import Annotated

from fastapi import APIRouter, Depends

from mdcopilot_blog.api.deps import Principal, SettingsDep, require_permission
from mdcopilot_blog.api.schemas import SettingsView, mask_secret
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.settings import Settings

router = APIRouter(tags=["settings"])


def build_settings_view(settings: Settings) -> SettingsView:
    return SettingsView(
        app_version=settings.app_version,
        mock_mode=settings.mock_mode,
        agent_enabled=settings.agent_enabled,
        scheduler_enabled=settings.scheduler_enabled,
        publishing_enabled=settings.publishing_enabled,
        gemini_grounding_enabled=settings.gemini_grounding_enabled,
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


@router.get("/settings", response_model=SettingsView)
async def get_settings_view(
    _: Annotated[Principal, Depends(require_permission(Permission.SETTINGS))], settings: SettingsDep
) -> SettingsView:
    return build_settings_view(settings)
