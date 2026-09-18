"""Source catalogue and ledger API contracts."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.domain.contracts import PillarKey, SourceType
from mdcopilot_blog.domain.enums import AccessMode, DateSource, DiscoveredVia, FeedKind, FetchStatus


class LedgerSourceOut(ApiModel):
    id: uuid.UUID
    title: str
    url: str
    canonical_url: str
    publisher: str
    domain: str
    source_type: SourceType
    tier: int
    published_at: datetime | None
    date_source: DateSource
    retrieved_at: datetime
    access_mode: AccessMode
    fetch_status: FetchStatus
    word_count: int
    is_preprint: bool
    discovered_via: DiscoveredVia
    relevance_score: float


class SourceFeedOut(ApiModel):
    id: uuid.UUID
    name: str
    url: str
    kind: FeedKind
    group: str
    tier: int
    source_type: SourceType
    pillar_keys: list[PillarKey]
    theme_keys: list[str]
    header_profile: str
    is_enabled: bool
    is_preprint: bool
    last_fetched_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    disabled_reason: str | None
    item_count_last: int


class SourceFeedUpdate(ApiModel):
    is_enabled: bool | SkipJsonSchema[None] = None
    tier: Annotated[int, Field(ge=1, le=3)] | SkipJsonSchema[None] = None
    header_profile: Literal["default", "browser_like"] | SkipJsonSchema[None] = None
    pillar_keys: list[PillarKey] | SkipJsonSchema[None] = None
    theme_keys: list[str] | SkipJsonSchema[None] = None

    @model_validator(mode="after")
    def reject_null(self) -> "SourceFeedUpdate":
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} may not be null")
        return self


class SourceDomainOut(ApiModel):
    id: uuid.UUID
    domain: str
    tier: int
    source_type: SourceType
    publisher: str | None
    header_profile: str
    fetch_policy: Literal["fetch", "metadata_only", "never"]
    verification_allowlisted: bool
    notes: str | None


class SourceDomainUpdate(ApiModel):
    tier: Annotated[int, Field(ge=1, le=3)] | SkipJsonSchema[None] = None
    source_type: SourceType | SkipJsonSchema[None] = None
    publisher: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    header_profile: Literal["default", "browser_like"] | SkipJsonSchema[None] = None
    fetch_policy: Literal["fetch", "metadata_only", "never"] | SkipJsonSchema[None] = None
    verification_allowlisted: bool | SkipJsonSchema[None] = None
    notes: Annotated[str, Field(max_length=2000)] | None = None

    @model_validator(mode="after")
    def reject_null(self) -> "SourceDomainUpdate":
        for name in self.model_fields_set - {"publisher", "notes"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} may not be null")
        return self


class ThemeOut(ApiModel):
    id: uuid.UUID
    key: str
    name: str
    description: str
    query_templates: list[str]
    pillar_keys: list[PillarKey]
    is_active: bool
    last_searched_at: datetime | None
    sort_order: int


class ThemeIn(ApiModel):
    key: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=2000)
    query_templates: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(min_length=1, max_length=10)
    pillar_keys: list[PillarKey]
    is_active: bool
    sort_order: int = Field(ge=0)


class ThemesUpdate(ApiModel):
    items: list[ThemeIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_keys(self) -> "ThemesUpdate":
        if len({item.key for item in self.items}) != len(self.items):
            raise ValueError("duplicate theme keys")
        return self
