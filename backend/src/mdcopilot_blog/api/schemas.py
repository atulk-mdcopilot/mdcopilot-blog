"""HTTP request/response models. JSON is camelCase; Python attributes stay snake_case."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from mdcopilot_blog.domain.enums import RunStatus, StepStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="forbid",
        from_attributes=True,
    )


class ManualRunRequest(ApiModel):
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    audience: str | None = Field(None, max_length=300)
    tone: str | None = Field(None, max_length=300)
    word_count: int | None = Field(None, ge=300, le=3000)


class DraftOut(ApiModel):
    """The draft saved to MDCopilot Blogs."""

    blog_id: str
    title: str
    gates_passed: bool
    gate_problems: list[str]


class RunOut(ApiModel):
    id: uuid.UUID
    topic: str
    status: RunStatus
    stage: str | None
    error: dict[str, Any] | None  # blog_runs.error: {"class", "message"}
    cost_usd: Decimal
    created_by: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    draft: DraftOut | None = None


class StepOut(ApiModel):
    step_name: str
    status: StepStatus
    tries: int
    agent_name: str | None
    model: str | None
    cost_usd: Decimal
    duration_ms: int | None
    error: dict[str, Any] | None


class RunDetail(RunOut):
    steps: list[StepOut]


class Page[T](ApiModel):
    items: list[T]
    total: int
    limit: int
    offset: int
