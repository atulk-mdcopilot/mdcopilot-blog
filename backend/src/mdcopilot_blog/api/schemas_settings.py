"""Versioned settings and content pillar responses."""

import uuid
from datetime import datetime
from typing import Literal

from mdcopilot_blog.api.schemas import ApiModel, SettingsView
from mdcopilot_blog.domain.config import EffectiveConfig, SettingsValues
from mdcopilot_blog.domain.contracts import PillarKey


class SettingsOut(SettingsView):
    auto_publish_available: Literal[False] = False
    version: int | None
    updated_at: datetime | None
    updated_by: uuid.UUID | None
    effective: EffectiveConfig
    values: SettingsValues


class SettingsUpdate(ApiModel):
    expected_version: int | None
    values: SettingsValues


class PillarOut(ApiModel):
    id: uuid.UUID
    key: PillarKey
    name: str
    description: str
    topics: list[str]
    weekdays: list[int]
    is_active: bool
    sort_order: int
