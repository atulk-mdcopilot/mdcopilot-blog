"""HTTP request/response models. JSON is camelCase; Python attributes stay snake_case."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic.alias_generators import to_camel

from mdcopilot_blog.auth.users import MIN_PASSWORD_LENGTH
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import AttemptStatus, Permission, Role, RunKind, RunStatus, StepStatus

MAX_EMAIL_LENGTH = 320
MAX_PASSWORD_LENGTH = 1024
MIN_KEY_LENGTH_FOR_PREVIEW = 12  # shorter keys would reveal too large a share


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="forbid",
        from_attributes=True,
    )


def _email(value: str) -> str:
    normalized = value.strip().lower()
    local, _, domain = normalized.partition("@")
    if not local or not domain or "@" in domain or any(ch.isspace() for ch in normalized):
        raise ValueError("must be an email address")
    return normalized


# --- auth ---


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class SessionUser(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    permissions: list[Permission]


class SessionResponse(ApiModel):
    user: SessionUser
    csrf_token: str


# --- users ---


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class UserCreate(ApiModel):
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    display_name: str = Field(min_length=1, max_length=200)
    role: Role
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return _email(value)

    @field_validator("display_name")
    @classmethod
    def _check_display_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class UserUpdate(ApiModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


# --- settings ---


class ProviderKeyView(ApiModel):
    configured: bool
    preview: str | None


class SettingsView(ApiModel):
    app_version: str
    mock_mode: bool
    agent_enabled: bool
    scheduler_enabled: bool
    publishing_enabled: bool
    gemini_grounding_enabled: bool
    human_approval_required: bool
    schedule: dict[str, str]
    routes: dict[str, list[str]]
    limits: dict[str, str | int | float]
    publisher: str
    providers: dict[str, ProviderKeyView]


def mask_secret(value: SecretStr | None) -> ProviderKeyView:
    """Never return a key: 3 leading + 4 trailing characters for long keys, 'set' for short ones."""
    raw = value.get_secret_value() if value is not None else ""
    if not raw:
        return ProviderKeyView(configured=False, preview=None)
    if len(raw) >= MIN_KEY_LENGTH_FOR_PREVIEW:
        return ProviderKeyView(configured=True, preview=f"{raw[:3]}…{raw[-4:]}")
    return ProviderKeyView(configured=True, preview="set")


# --- runs (served by Task 12) ---


class ManualRunRequest(ApiModel):
    run_date: date | None = None
    pillar: PillarKey | None = None
    topic: str | None = Field(None, max_length=300)
    audience: str | None = None
    tone: str | None = None
    word_count: int | None = Field(None, ge=300, le=3000)


class RunOut(ApiModel):
    id: uuid.UUID
    kind: RunKind
    run_date: date
    status: RunStatus
    stage: str | None
    trace_id: str
    cost_usd: Decimal
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AttemptOut(ApiModel):
    id: uuid.UUID
    dbos_workflow_id: str
    workflow_name: str
    attempt_no: int
    status: AttemptStatus
    started_at: datetime | None
    finished_at: datetime | None
    forked_from_workflow_id: str | None


class StepOut(ApiModel):
    id: uuid.UUID
    step_name: str
    dbos_step_id: int
    status: StepStatus
    tries: int
    agent_name: str | None
    model: str | None
    prompt_name: str | None
    prompt_version: int | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    duration_ms: int | None
    error: dict[str, Any] | None


class RunDetail(RunOut):
    params: dict[str, Any]
    attempts: list[AttemptOut]
    steps: list[StepOut]


class Page[T](ApiModel):
    items: list[T]
    total: int
    limit: int
    offset: int
