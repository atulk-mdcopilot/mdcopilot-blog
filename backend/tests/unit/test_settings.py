"""settings.py: env names, secrets, CSV routes, safety validators and derived URLs."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import URL

from mdcopilot_blog.settings import Settings, get_settings

SESSION_SECRET_VALUE = "s" * 40
DB_PASSWORD_VALUE = "db-pass-4f9e1c"


def _env_names() -> list[str]:
    names: list[str] = []
    for field in Settings.model_fields.values():
        assert isinstance(field.validation_alias, str), "every Settings field must set validation_alias"
        names.append(field.validation_alias)
    return names


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Start from an environment without any Settings variable, then set the two required secrets.

    The tools container receives the real .env through compose `env_file`, so every test clears it first.
    """
    for name in _env_names():
        monkeypatch.delenv(name, raising=False)
    # Field-name spellings (e.g. TIMEZONE) are never read without validate_by_name; cleared anyway so a
    # stray variable cannot hide a regression.
    for field_name in Settings.model_fields:
        monkeypatch.delenv(field_name.upper(), raising=False)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET_VALUE)
    monkeypatch.setenv("POSTGRES_PASSWORD", DB_PASSWORD_VALUE)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_every_field_is_read_from_its_env_name_without_prefix() -> None:
    names = _env_names()
    assert len(names) == len(set(names))
    for expected in (
        "APP_ENV",
        "SESSION_SECRET",
        "POSTGRES_PASSWORD",
        "OPENAI_API_KEY",
        "BLOG_AGENT_ENABLED",
        "BLOG_HUMAN_APPROVAL_REQUIRED",
        "BLOG_AGENT_WRITER_ROUTE",
        "BLOG_AGENT_MAX_COST_PER_RUN_USD",
        "BLOG_PUBLISHER_PASSWORD",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "WORKER_EXECUTOR_ID",
    ):
        assert expected in names


def test_defaults_match_env_example(env: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.app_env == "development"
    assert s.app_version == "0.1.0"
    assert s.log_level == "INFO"
    assert s.session_cookie_secure is False
    assert s.public_app_url == "http://localhost:8310"
    assert s.postgres_db == "mdcopilot_blog"
    assert s.postgres_user == "mdcopilot_blog"
    assert s.postgres_host == "db"
    assert s.postgres_port == 5432
    assert s.openai_api_key is None
    assert s.anthropic_api_key is None
    assert s.agent_enabled is True
    assert s.mock_mode is True
    assert s.mock_step_delay_seconds == 0.0
    assert s.scheduler_enabled is False
    assert s.human_approval_required is True
    assert s.publishing_enabled is False
    assert s.gemini_grounding_enabled is False
    assert s.daily_run_time == "07:00"
    assert s.timezone == "Asia/Kolkata"
    assert (s.research_window_days, s.min_source_count) == (7, 5)
    assert s.novelty_threshold == 0.85
    assert (s.word_count_min, s.word_count_max) == (850, 1150)
    assert s.site_url == "https://www.mdcopilot.health"
    assert s.default_category == "Healthcare AI"
    assert s.search_route == ["openai:gpt-5.6-luna"]
    assert s.writer_route == ["openai:gpt-5.6-sol", "google:gemini-3.8-flash", "anthropic:claude-sonnet-5"]
    assert s.seo_route == ["google:gemini-3.5-flash-lite", "openai:gpt-5.6-luna"]
    assert s.embedding_model == "google:gemini-embedding-2"
    assert s.embedding_dimensions == 1536
    assert s.max_cost_per_run_usd == Decimal("5.00")
    assert (s.discovery_timeout_minutes, s.production_timeout_minutes) == (15, 30)
    assert (s.max_parallel_searches, s.max_parallel_fetches) == (6, 12)
    assert s.publisher == "manual_export"
    assert s.publisher_api_url == "http://host.docker.internal:8000/api/v1"
    assert s.publisher_public_url == "http://localhost:3000"
    assert s.worker_executor_id == "worker-1"


@pytest.mark.parametrize("missing", ["SESSION_SECRET", "POSTGRES_PASSWORD"])
def test_required_secrets(env: pytest.MonkeyPatch, missing: str) -> None:
    env.delenv(missing)
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert missing in str(excinfo.value)


def test_empty_secret_counts_as_missing(env: pytest.MonkeyPatch) -> None:
    env.setenv("POSTGRES_PASSWORD", "")
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
        Settings()


def test_short_session_secret_is_refused_without_echoing_it(env: pytest.MonkeyPatch) -> None:
    env.setenv("SESSION_SECRET", "change-me")
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    message = str(excinfo.value)
    assert "at least 32 characters" in message
    assert "change-me" not in message


def test_secrets_are_secretstr_and_masked(env: pytest.MonkeyPatch) -> None:
    env.setenv("OPENAI_API_KEY", "sk-test-abcdef123456")
    env.setenv("BLOG_PUBLISHER_PASSWORD", "publisher-pass-xyz")
    s = Settings()
    assert isinstance(s.session_secret, SecretStr)
    assert isinstance(s.openai_api_key, SecretStr)
    assert s.openai_api_key.get_secret_value() == "sk-test-abcdef123456"
    rendered = repr(s) + str(s) + repr(s.model_dump())
    for raw in (SESSION_SECRET_VALUE, DB_PASSWORD_VALUE, "sk-test-abcdef123456", "publisher-pass-xyz"):
        assert raw not in rendered


def test_empty_optional_values_become_none(env: pytest.MonkeyPatch) -> None:
    env.setenv("OPENAI_API_KEY", "")
    env.setenv("BOOTSTRAP_ADMIN_EMAIL", "")
    env.setenv("BLOG_MDCOPILOT_PUBLIC_API_URL", "")
    s = Settings()
    assert s.openai_api_key is None
    assert s.bootstrap_admin_email is None
    assert s.mdcopilot_public_api_url is None


def test_csv_routes_are_split_and_trimmed(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_RESEARCH_ROUTE", " google:gemini-x , openai:gpt-y ,, ")
    env.setenv("BLOG_AGENT_SEARCH_ROUTE", "openai:only-one")
    s = Settings()
    assert s.research_route == ["google:gemini-x", "openai:gpt-y"]
    assert s.search_route == ["openai:only-one"]


def test_json_looking_route_is_not_json_decoded(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_SEO_ROUTE", '["openai:x"]')
    assert Settings().seo_route == ['["openai:x"]']


def test_empty_route_is_refused(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_WRITER_ROUTE", " , ")
    with pytest.raises(ValidationError, match="route must list at least one provider:model"):
        Settings()


def test_route_values_maps_agent_keys_to_routes(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_CLINICAL_ROUTE", "openai:a,google:b")
    routes = Settings().route_values()
    assert list(routes) == [
        "search",
        "research",
        "ideation",
        "deep_research",
        "writer",
        "fact_check",
        "clinical",
        "editorial",
        "seo",
    ]
    assert routes["clinical"] == ["openai:a", "google:b"]
    assert routes["fact_check"] == [
        "google:gemini-3.8-flash",
        "openai:gpt-5.6-terra",
        "anthropic:claude-sonnet-5",
    ]
    routes["clinical"].append("mutated")
    assert Settings().route_values()["clinical"] == ["openai:a", "google:b"]


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE"])
def test_human_approval_cannot_be_disabled(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_HUMAN_APPROVAL_REQUIRED", value)
    with pytest.raises(ValidationError, match="BLOG_HUMAN_APPROVAL_REQUIRED=false is not allowed"):
        Settings()


def test_boolean_flags_parse_from_env(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_MOCK_MODE", "false")
    env.setenv("BLOG_AGENT_SCHEDULER_ENABLED", "true")
    env.setenv("SESSION_COOKIE_SECURE", "1")
    s = Settings()
    assert (s.mock_mode, s.scheduler_enabled, s.session_cookie_secure) == (False, True, True)


@pytest.mark.parametrize("value", ["00:00", "07:00", "23:59", "09:05"])
def test_daily_run_time_accepts_hh_mm(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_DAILY_RUN_TIME", value)
    assert Settings().daily_run_time == value


@pytest.mark.parametrize("value", ["24:00", "7:00", "07:60", "0700", "07:00:00", "ab:cd", " 07:00"])
def test_daily_run_time_rejects_other_formats(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_DAILY_RUN_TIME", value)
    with pytest.raises(ValidationError, match="HH:MM"):
        Settings()


@pytest.mark.parametrize("value", ["UTC", "Asia/Kolkata", "America/New_York"])
def test_timezone_accepts_iana_names(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_TIMEZONE", value)
    assert Settings().timezone == value


@pytest.mark.parametrize("value", ["Mars/Olympus", "IST+5:30", "../etc/passwd", "Asia/"])
def test_timezone_rejects_unknown_names(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_TIMEZONE", value)
    with pytest.raises(ValidationError, match="unknown timezone"):
        Settings()


@pytest.mark.parametrize(("low", "high"), [("1150", "850"), ("900", "900")])
def test_word_count_min_must_be_below_max(env: pytest.MonkeyPatch, low: str, high: str) -> None:
    env.setenv("BLOG_AGENT_WORD_COUNT_MIN", low)
    env.setenv("BLOG_AGENT_WORD_COUNT_MAX", high)
    with pytest.raises(ValidationError, match="BLOG_AGENT_WORD_COUNT_MIN must be less than BLOG_AGENT_WORD_COUNT_MAX"):
        Settings()


def test_negative_mock_delay_is_refused(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_MOCK_STEP_DELAY_SECONDS", "-1")
    with pytest.raises(ValidationError):
        Settings()


def test_log_level_is_normalised_and_checked(env: pytest.MonkeyPatch) -> None:
    env.setenv("LOG_LEVEL", "debug")
    assert Settings().log_level == "DEBUG"
    env.setenv("LOG_LEVEL", "chatty")
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        Settings()


def test_invalid_literal_values_are_refused(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_PUBLISHER", "wordpress")
    with pytest.raises(ValidationError):
        Settings()


def test_field_name_spellings_are_not_read(env: pytest.MonkeyPatch) -> None:
    env.setenv("TIMEZONE", "UTC")
    env.setenv("MOCK_MODE", "false")
    env.setenv("PUBLISHER", "null")
    s = Settings()
    assert (s.timezone, s.mock_mode, s.publisher) == ("Asia/Kolkata", True, "manual_export")
    by_alias = Settings(POSTGRES_DB="other_db", BLOG_AGENT_MOCK_MODE=False)
    assert (by_alias.postgres_db, by_alias.mock_mode) == ("other_db", False)


def test_database_url_builds_psycopg_url_and_hides_password(env: pytest.MonkeyPatch) -> None:
    env.setenv("POSTGRES_HOST", "db.internal")
    env.setenv("POSTGRES_PORT", "6543")
    s = Settings()
    url = s.database_url()
    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.host, url.port, url.database) == ("mdcopilot_blog", "db.internal", 6543, "mdcopilot_blog")
    assert url.password == DB_PASSWORD_VALUE
    assert DB_PASSWORD_VALUE not in repr(url)
    assert DB_PASSWORD_VALUE not in str(url)
    assert s.database_url("mdcopilot_blog_test").database == "mdcopilot_blog_test"


def test_dbos_system_database_url_renders_the_password(env: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.dbos_system_database_url == (
        f"postgresql+psycopg://mdcopilot_blog:{DB_PASSWORD_VALUE}@db:5432/mdcopilot_blog"
    )
    assert DB_PASSWORD_VALUE not in repr(s)


def test_dbos_system_database_url_percent_encodes_special_characters(env: pytest.MonkeyPatch) -> None:
    env.setenv("POSTGRES_PASSWORD", "p@ss:w/rd%")
    s = Settings()
    assert s.dbos_system_database_url == "postgresql+psycopg://mdcopilot_blog:p%40ss%3Aw%2Frd%25@db:5432/mdcopilot_blog"


def test_session_cookie_name_depends_on_secure_flag(env: pytest.MonkeyPatch) -> None:
    assert Settings().session_cookie_name == "mdcb_session"
    env.setenv("SESSION_COOKIE_SECURE", "true")
    assert Settings().session_cookie_name == "__Host-mdcb_session"


def test_get_settings_is_cached(env: pytest.MonkeyPatch) -> None:
    first = get_settings()
    assert get_settings() is first
    get_settings.cache_clear()
    assert get_settings() is not first


PHASE_2_10_ENV_NAMES = [
    "BLOG_AGENT_MOCK_SCENARIO",
    "BLOG_AGENT_PROVIDER_CONCURRENCY",
    "BLOG_AGENT_SEARCH_CONTEXT_SIZE_BROAD",
    "BLOG_AGENT_SEARCH_CONTEXT_SIZE_DEEP",
    "BLOG_AGENT_SEARCH_MAX_TOOL_CALLS_BROAD",
    "BLOG_AGENT_SEARCH_MAX_TOOL_CALLS_DEEP",
    "BLOG_AGENT_PRICE_AUTO_UPDATE",
    "BLOG_FETCH_CONNECT_TIMEOUT_SECONDS",
    "BLOG_FETCH_READ_TIMEOUT_SECONDS",
    "BLOG_FETCH_MAX_BYTES",
    "BLOG_FETCH_MAX_REDIRECTS",
    "BLOG_FETCH_PER_HOST_LIMIT",
    "BLOG_FETCH_ROBOTS_CACHE_HOURS",
    "BLOG_MDCOPILOT_SYNC_PAGE_SIZE",
    "BLOG_PUBLISHER_TIMEOUT_SECONDS",
    "BLOG_PUBLISHER_LOGIN_PATH",
    "BLOG_NOTIFY_WEBHOOK_TIMEOUT_SECONDS",
    "BLOG_DBOS_RETENTION_DAYS",
    "BLOG_SOURCE_SNAPSHOT_RETENTION_DAYS",
    "BLOG_COST_RECONCILIATION_ENABLED",
    "OPENAI_ADMIN_API_KEY",
]


def test_phase_2_10_env_names() -> None:
    names = _env_names()
    for expected in PHASE_2_10_ENV_NAMES:
        assert expected in names


def test_phase_2_10_defaults(env: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.mock_scenario is None
    assert s.provider_concurrency == 4
    assert s.search_context_size_broad == "low"
    assert s.search_context_size_deep == "medium"
    assert s.search_max_tool_calls_broad == 1
    assert s.search_max_tool_calls_deep == 2
    assert s.price_auto_update is False
    assert s.fetch_connect_timeout_seconds == 5.0
    assert s.fetch_read_timeout_seconds == 15.0
    assert s.fetch_max_bytes == 5000000
    assert s.fetch_max_redirects == 5
    assert s.fetch_per_host_limit == 2
    assert s.robots_cache_hours == 24
    assert s.mdcopilot_sync_page_size == 50
    assert s.publisher_timeout_seconds == 20.0
    assert s.publisher_login_path == "/auth/login"
    assert s.notify_webhook_timeout_seconds == 5.0
    assert s.dbos_retention_days == 30
    assert s.source_snapshot_retention_days == 365
    assert s.cost_reconciliation_enabled is False
    assert s.openai_admin_api_key is None


def test_mock_scenario_values(env: pytest.MonkeyPatch) -> None:
    env.setenv("BLOG_AGENT_MOCK_SCENARIO", "invented_quote")
    assert Settings().mock_scenario == "invented_quote"
    env.setenv("BLOG_AGENT_MOCK_SCENARIO", "")
    assert Settings().mock_scenario is None


@pytest.mark.parametrize("value", ["../x", "Invented", "has-dash", "a" * 65])
def test_mock_scenario_rejects_bad_values(env: pytest.MonkeyPatch, value: str) -> None:
    env.setenv("BLOG_AGENT_MOCK_SCENARIO", value)
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert "BLOG_AGENT_MOCK_SCENARIO" in str(excinfo.value)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("BLOG_AGENT_PROVIDER_CONCURRENCY", "0"),
        ("BLOG_AGENT_SEARCH_CONTEXT_SIZE_BROAD", "huge"),
        ("BLOG_AGENT_SEARCH_MAX_TOOL_CALLS_BROAD", "6"),
        ("BLOG_AGENT_SEARCH_MAX_TOOL_CALLS_DEEP", "0"),
        ("BLOG_FETCH_CONNECT_TIMEOUT_SECONDS", "0"),
        ("BLOG_FETCH_READ_TIMEOUT_SECONDS", "-1"),
        ("BLOG_FETCH_MAX_BYTES", "0"),
        ("BLOG_FETCH_MAX_REDIRECTS", "11"),
        ("BLOG_FETCH_PER_HOST_LIMIT", "3"),
        ("BLOG_FETCH_ROBOTS_CACHE_HOURS", "0"),
        ("BLOG_MDCOPILOT_SYNC_PAGE_SIZE", "101"),
        ("BLOG_PUBLISHER_TIMEOUT_SECONDS", "0"),
        ("BLOG_PUBLISHER_LOGIN_PATH", "auth/login"),
        ("BLOG_NOTIFY_WEBHOOK_TIMEOUT_SECONDS", "0"),
        ("BLOG_DBOS_RETENTION_DAYS", "0"),
        ("BLOG_SOURCE_SNAPSHOT_RETENTION_DAYS", "0"),
    ],
)
def test_phase_2_10_bounds_are_enforced(env: pytest.MonkeyPatch, name: str, value: str) -> None:
    env.setenv(name, value)
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert name in str(excinfo.value)


def test_openai_admin_api_key_is_secret(env: pytest.MonkeyPatch) -> None:
    env.setenv("OPENAI_ADMIN_API_KEY", "sk-admin-test-value-123")
    s = Settings()
    assert isinstance(s.openai_admin_api_key, SecretStr)
    assert "sk-admin-test-value-123" not in repr(s)
