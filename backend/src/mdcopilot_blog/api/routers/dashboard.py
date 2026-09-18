"""Generation progress and article counts for the dashboard."""

from typing import Annotated

from fastapi import APIRouter, Depends

from mdcopilot_blog.api.deps import Principal, SessionDep, SettingsDep, require_permission
from mdcopilot_blog.api.schemas_dashboard import DashboardOut
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.services.dashboard import dashboard

router = APIRouter(tags=["dashboard"])
ViewDep = Annotated[Principal, Depends(require_permission(Permission.VIEW))]


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(db: SessionDep, settings: SettingsDep, _: ViewDep) -> DashboardOut:
    return await dashboard(db, settings)
