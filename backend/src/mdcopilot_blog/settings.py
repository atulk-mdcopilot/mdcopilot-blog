"""Application settings, read from the process environment.

Compose passes `.env` to every backend container through `env_file`, so the loader reads only
`os.environ` (`env_file=None`). Every field names its variable with `validation_alias`, using exactly
the names in `.env.example` (no prefix).

`validate_by_name` is deliberately not set: a variable spelled like a field name (e.g. `TIMEZONE`) is
never read, only the alias names below. Code that needs a variant uses `model_copy(update=…)`.

Secrets are `SecretStr`. They never appear in repr, logs or validation errors (`hide_input_in_errors=True`).
"""

import re
from decimal import Decimal
from functools import lru_cache
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL, make_url

MIN_SESSION_SECRET_LENGTH = 32
LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})
_HH_MM = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")
_OPENAI_GPT_VERSION = re.compile(r"^openai:gpt-(\d+)(?:\.(\d+))?", re.IGNORECASE)
MAX_OPENAI_GPT_VERSION = (5, 4)

# "a, b ,,c" -> ["a", "b", "c"]. NoDecode stops pydantic-settings from JSON-decoding the value first.
RouteList = Annotated[list[str], NoDecode]

ROUTE_FIELDS = (
    "search_route",
    "research_route",
    "ideation_route",
    "deep_research_route",
    "writer_route",
    "fact_check_route",
    "clinical_route",
    "editorial_route",
    "seo_route",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        env_ignore_empty=True,
        validate_by_alias=True,
        hide_input_in_errors=True,
    )

    # --- App ---
    app_env: Literal["development", "production"] = Field("development", validation_alias="APP_ENV")
    app_version: str = Field("0.1.0", validation_alias="APP_VERSION")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")

    # --- Sessions ---
    session_secret: SecretStr = Field(validation_alias="SESSION_SECRET")
    session_cookie_secure: bool = Field(False, validation_alias="SESSION_COOKIE_SECURE")
    public_app_url: str = Field("http://localhost:8310", validation_alias="PUBLIC_APP_URL")

    # --- Database: the mdcopilot-backend database (same DATABASE_URL format the backend uses) ---
    database_dsn: SecretStr = Field(validation_alias="DATABASE_URL")

    # --- Provider keys ---
    openai_api_key: SecretStr | None = Field(None, validation_alias="OPENAI_API_KEY")
    gemini_api_key: SecretStr | None = Field(None, validation_alias="GEMINI_API_KEY")
    anthropic_api_key: SecretStr | None = Field(None, validation_alias="ANTHROPIC_API_KEY")
    ncbi_api_key: SecretStr | None = Field(None, validation_alias="NCBI_API_KEY")
    ncbi_contact_email: str | None = Field(None, validation_alias="NCBI_CONTACT_EMAIL")

    # --- Flags (environment-only safety switches) ---
    agent_enabled: bool = Field(True, validation_alias="BLOG_AGENT_ENABLED")
    scheduler_enabled: bool = Field(False, validation_alias="BLOG_AGENT_SCHEDULER_ENABLED")
    human_approval_required: bool = Field(True, validation_alias="BLOG_HUMAN_APPROVAL_REQUIRED")
    publishing_enabled: bool = Field(False, validation_alias="BLOG_PUBLISHING_ENABLED")

    # --- Schedule and content ---
    daily_run_time: str = Field("07:00", validation_alias="BLOG_AGENT_DAILY_RUN_TIME")
    timezone: str = Field("Asia/Kolkata", validation_alias="BLOG_AGENT_TIMEZONE")
    research_window_days: int = Field(7, ge=1, validation_alias="BLOG_AGENT_RESEARCH_WINDOW_DAYS")
    min_source_count: int = Field(5, ge=1, validation_alias="BLOG_AGENT_MIN_SOURCE_COUNT")
    novelty_threshold: float = Field(0.85, ge=0, le=1, validation_alias="BLOG_AGENT_NOVELTY_THRESHOLD")
    word_count_min: int = Field(850, ge=1, validation_alias="BLOG_AGENT_WORD_COUNT_MIN")
    word_count_max: int = Field(1150, ge=1, validation_alias="BLOG_AGENT_WORD_COUNT_MAX")
    site_url: str = Field("https://www.mdcopilot.health", validation_alias="BLOG_SITE_URL")
    default_category: str = Field("Healthcare AI", validation_alias="BLOG_DEFAULT_CATEGORY")

    # --- Model routes: ordered "provider:model" lists, first = primary (defaults = .env.example) ---
    search_route: RouteList = Field(
        default_factory=lambda: ["openai:gpt-5.4-mini"],
        validation_alias="BLOG_AGENT_SEARCH_ROUTE",
    )
    research_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.8-flash", "openai:gpt-5.4-mini"],
        validation_alias="BLOG_AGENT_RESEARCH_ROUTE",
    )
    ideation_route: RouteList = Field(
        default_factory=lambda: [
            "google:gemini-3.5-flash-lite",
            "google:gemini-3.8-flash",
            "openai:gpt-5.4-mini",
        ],
        validation_alias="BLOG_AGENT_IDEATION_ROUTE",
    )
    deep_research_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.8-flash", "openai:gpt-5.4-mini"],
        validation_alias="BLOG_AGENT_DEEP_RESEARCH_ROUTE",
    )
    writer_route: RouteList = Field(
        default_factory=lambda: ["openai:gpt-5.4", "google:gemini-3.8-flash", "anthropic:claude-sonnet-5"],
        validation_alias="BLOG_AGENT_WRITER_ROUTE",
    )
    fact_check_route: RouteList = Field(
        default_factory=lambda: [
            "google:gemini-3.8-flash",
            "openai:gpt-5.4-mini",
            "anthropic:claude-sonnet-5",
        ],
        validation_alias="BLOG_AGENT_FACT_CHECK_ROUTE",
    )
    clinical_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.8-flash", "openai:gpt-5.4-mini"],
        validation_alias="BLOG_AGENT_CLINICAL_ROUTE",
    )
    editorial_route: RouteList = Field(
        default_factory=lambda: [
            "google:gemini-3.5-flash-lite",
            "google:gemini-3.8-flash",
            "openai:gpt-5.4-mini",
        ],
        validation_alias="BLOG_AGENT_EDITORIAL_ROUTE",
    )
    seo_route: RouteList = Field(
        default_factory=lambda: ["google:gemini-3.5-flash-lite", "openai:gpt-5.4-mini"],
        validation_alias="BLOG_AGENT_SEO_ROUTE",
    )
    embedding_model: str = Field("google:gemini-embedding-2", validation_alias="BLOG_AGENT_EMBEDDING_MODEL")
    embedding_dimensions: int = Field(1536, ge=1, validation_alias="BLOG_AGENT_EMBEDDING_DIMENSIONS")
    provider_concurrency: int = Field(4, ge=1, validation_alias="BLOG_AGENT_PROVIDER_CONCURRENCY")
    search_context_size_broad: Literal["low", "medium", "high"] = Field(
        "low", validation_alias="BLOG_AGENT_SEARCH_CONTEXT_SIZE_BROAD"
    )
    search_context_size_deep: Literal["low", "medium", "high"] = Field(
        "medium", validation_alias="BLOG_AGENT_SEARCH_CONTEXT_SIZE_DEEP"
    )
    search_max_tool_calls_broad: int = Field(1, ge=1, le=5, validation_alias="BLOG_AGENT_SEARCH_MAX_TOOL_CALLS_BROAD")
    search_max_tool_calls_deep: int = Field(2, ge=1, le=5, validation_alias="BLOG_AGENT_SEARCH_MAX_TOOL_CALLS_DEEP")
    price_auto_update: bool = Field(False, validation_alias="BLOG_AGENT_PRICE_AUTO_UPDATE")

    # --- Limits and guardrails ---
    max_cost_per_run_usd: Decimal = Field(Decimal("5.00"), ge=0, validation_alias="BLOG_AGENT_MAX_COST_PER_RUN_USD")
    discovery_timeout_minutes: int = Field(15, ge=1, validation_alias="BLOG_AGENT_DISCOVERY_TIMEOUT_MINUTES")
    production_timeout_minutes: int = Field(30, ge=1, validation_alias="BLOG_AGENT_PRODUCTION_TIMEOUT_MINUTES")
    max_parallel_searches: int = Field(6, ge=1, validation_alias="BLOG_AGENT_MAX_PARALLEL_SEARCHES")
    max_parallel_fetches: int = Field(12, ge=1, validation_alias="BLOG_AGENT_MAX_PARALLEL_FETCHES")
    fetch_contact: str | None = Field(None, validation_alias="BLOG_FETCH_CONTACT")
    fetch_connect_timeout_seconds: float = Field(5.0, gt=0, validation_alias="BLOG_FETCH_CONNECT_TIMEOUT_SECONDS")
    fetch_read_timeout_seconds: float = Field(15.0, gt=0, validation_alias="BLOG_FETCH_READ_TIMEOUT_SECONDS")
    fetch_max_bytes: int = Field(5000000, ge=1, validation_alias="BLOG_FETCH_MAX_BYTES")
    fetch_max_redirects: int = Field(5, ge=0, le=10, validation_alias="BLOG_FETCH_MAX_REDIRECTS")
    fetch_per_host_limit: int = Field(2, ge=1, le=2, validation_alias="BLOG_FETCH_PER_HOST_LIMIT")
    robots_cache_hours: int = Field(24, ge=1, validation_alias="BLOG_FETCH_ROBOTS_CACHE_HOURS")
    dbos_retention_days: int = Field(30, ge=1, validation_alias="BLOG_DBOS_RETENTION_DAYS")
    source_snapshot_retention_days: int = Field(365, ge=1, validation_alias="BLOG_SOURCE_SNAPSHOT_RETENTION_DAYS")

    # --- MDCopilot integration ---
    mdcopilot_public_api_url: str | None = Field(None, validation_alias="BLOG_MDCOPILOT_PUBLIC_API_URL")
    mdcopilot_sync_page_size: int = Field(50, ge=1, le=100, validation_alias="BLOG_MDCOPILOT_SYNC_PAGE_SIZE")
    publisher: Literal["manual_export", "mdcopilot_api"] = Field("manual_export", validation_alias="BLOG_PUBLISHER")
    publisher_api_url: str = Field("http://host.docker.internal:8000/api/v1", validation_alias="BLOG_PUBLISHER_API_URL")
    publisher_login_id: str | None = Field(None, validation_alias="BLOG_PUBLISHER_LOGIN_ID")
    publisher_password: SecretStr | None = Field(None, validation_alias="BLOG_PUBLISHER_PASSWORD")
    publisher_public_url: str = Field("http://localhost:3000", validation_alias="BLOG_PUBLISHER_PUBLIC_URL")
    publisher_login_path: str = Field("/auth/login", pattern=r"^/", validation_alias="BLOG_PUBLISHER_LOGIN_PATH")
    publisher_timeout_seconds: float = Field(20.0, gt=0, validation_alias="BLOG_PUBLISHER_TIMEOUT_SECONDS")

    # --- Worker ---
    worker_executor_id: str = Field("worker-1", validation_alias="WORKER_EXECUTOR_ID")

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        if value not in LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(LOG_LEVELS)}")
        return value

    @field_validator("session_secret")
    @classmethod
    def _check_session_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_SESSION_SECRET_LENGTH:
            raise ValueError(
                f"SESSION_SECRET must be at least {MIN_SESSION_SECRET_LENGTH} characters (openssl rand -hex 32)"
            )
        return value

    @field_validator("daily_run_time")
    @classmethod
    def _check_daily_run_time(cls, value: str) -> str:
        if _HH_MM.fullmatch(value) is None:
            raise ValueError("BLOG_AGENT_DAILY_RUN_TIME must be HH:MM (00:00 to 23:59)")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError(f"unknown timezone {value!r} (use an IANA name such as Asia/Kolkata)") from exc
        return value

    @field_validator(*ROUTE_FIELDS, mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(*ROUTE_FIELDS)
    @classmethod
    def _check_route_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("route must list at least one provider:model")
        for entry in value:
            match = _OPENAI_GPT_VERSION.match(entry)
            if match is None:
                continue
            version = (int(match.group(1)), int(match.group(2) or 0))
            if version > MAX_OPENAI_GPT_VERSION:
                raise ValueError("OpenAI GPT route models may not exceed gpt-5.4")
        return value

    @model_validator(mode="after")
    def _approval_is_mandatory(self) -> Self:
        if not self.human_approval_required:
            raise ValueError("BLOG_HUMAN_APPROVAL_REQUIRED=false is not allowed")
        return self

    @model_validator(mode="after")
    def _check_word_counts(self) -> Self:
        if self.word_count_min >= self.word_count_max:
            raise ValueError("BLOG_AGENT_WORD_COUNT_MIN must be less than BLOG_AGENT_WORD_COUNT_MAX")
        return self

    def database_url(self) -> URL:
        """SQLAlchemy URL (psycopg 3 driver) for DATABASE_URL. `str()`/`repr()` of a URL mask the password."""
        return make_url(self.database_dsn.get_secret_value()).set(drivername="postgresql+psycopg")

    @property
    def dbos_system_database_url(self) -> str:
        """Plain URL string for DBOS (it does not accept a URL object). Contains the password: never log it.

        render_as_string percent-encodes "@", ":", "/" and "%", but NOT spaces, and libpq rejects a raw
        space, so the database password must not contain spaces.
        """
        return self.database_url().render_as_string(hide_password=False)

    @property
    def session_cookie_name(self) -> str:
        """`__Host-` cookies require Secure, so the prefix is only used when secure cookies are on."""
        return "__Host-mdcb_session" if self.session_cookie_secure else "mdcb_session"

    def route_values(self) -> dict[str, list[str]]:
        """Agent key (AgentName value) -> configured route. Returns copies, so callers cannot mutate settings."""
        return {
            "search": list(self.search_route),
            "research": list(self.research_route),
            "ideation": list(self.ideation_route),
            "deep_research": list(self.deep_research_route),
            "writer": list(self.writer_route),
            "fact_check": list(self.fact_check_route),
            "clinical": list(self.clinical_route),
            "editorial": list(self.editorial_route),
            "seo": list(self.seo_route),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache process-wide settings."""
    return Settings()
