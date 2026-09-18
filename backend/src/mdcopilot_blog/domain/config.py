"""Effective-configuration models.

Snake_case in Python, camelCase on the wire; both spellings accepted on input; unknown keys
rejected. Precedence is handled by ``services.config.load_effective_config``; these models only
validate shapes.
"""

import re
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from mdcopilot_blog.domain.enums import AgentName, PublisherKey

AGENTS = tuple(agent.value for agent in AgentName)
"""The nine configurable agent route keys."""

_HH_MM = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")
_ROUTE_ENTRY = re.compile(r"^(openai|google|anthropic):\S+$")
_OPENAI_GPT_VERSION = re.compile(r"^openai:gpt-(\d+)(?:\.(\d+))?", re.IGNORECASE)
_MAX_OPENAI_GPT_VERSION = (5, 4)


def _validate_openai_model_ceiling(agent: str, entry: str) -> None:
    match = _OPENAI_GPT_VERSION.match(entry)
    if match is None:
        return
    version = (int(match.group(1)), int(match.group(2) or 0))
    if version > _MAX_OPENAI_GPT_VERSION:
        raise ValueError(f"routes.{agent} OpenAI GPT model may not exceed gpt-5.4")


class ConfigModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class WordCountRange(ConfigModel):
    min: Annotated[int, Field(ge=1)]
    max: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def _min_below_max(self) -> "WordCountRange":
        if self.min >= self.max:
            raise ValueError("min must be less than max")
        return self


class ScheduleConfig(ConfigModel):
    time: str = Field(pattern=r"(?:[01]\d|2[0-3]):[0-5]\d")
    timezone: str

    @field_validator("time")
    @classmethod
    def _check_time(cls, value: str) -> str:
        if _HH_MM.fullmatch(value) is None:
            raise ValueError("time must be HH:MM (00:00 to 23:59)")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value


class ScoreWeights(ConfigModel):
    timeliness: Annotated[float, Field(ge=0, le=1)] = 0.25
    novelty: Annotated[float, Field(ge=0, le=1)] = 0.20
    evidence: Annotated[float, Field(ge=0, le=1)] = 0.20
    mdcopilot_relevance: Annotated[float, Field(ge=0, le=1)] = 0.15
    audience: Annotated[float, Field(ge=0, le=1)] = 0.10
    editorial: Annotated[float, Field(ge=0, le=1)] = 0.10

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "ScoreWeights":
        total = (
            self.timeliness + self.novelty + self.evidence + self.mdcopilot_relevance + self.audience + self.editorial
        )
        if abs(total - 1) > 1e-6:
            raise ValueError("score weights must sum to 1")
        return self


class NoveltyConfig(ConfigModel):
    topic_threshold: Annotated[float, Field(ge=0, le=1)]
    argument_threshold: Annotated[float, Field(ge=0, le=1)] = 0.88
    warn_margin: Annotated[float, Field(ge=0, le=1)] = 0.05
    lookback_days: Annotated[int, Field(ge=1)] = 180
    news_reuse_days: Annotated[int, Field(ge=1)] = 30
    example_reuse_days: Annotated[int, Field(ge=1)] = 30
    headline_similarity_warn: Annotated[float, Field(ge=0, le=1)] = 0.6
    headline_pattern_window_days: Annotated[int, Field(ge=1)] = 14
    headline_pattern_warn_count: Annotated[int, Field(ge=1)] = 3
    max_regeneration_rounds: Annotated[int, Field(ge=0)] = 2


class DiversityConfig(ConfigModel):
    lookback_days: Annotated[int, Field(ge=1)] = 30
    cta_similarity_threshold: Annotated[float, Field(ge=0, le=1)] = 0.8
    cta_compare_last: Annotated[int, Field(ge=1)] = 10
    opening_similarity_threshold: Annotated[float, Field(ge=0, le=1)] = 0.9
    opening_compare_last: Annotated[int, Field(ge=1)] = 30
    headline_pattern_max_7d: Annotated[int, Field(ge=1)] = 3
    source_domain_max_7d: Annotated[int, Field(ge=1)] = 3
    phrase_min_count: Annotated[int, Field(ge=1)] = 3
    phrase_min_words: Annotated[int, Field(ge=1)] = 3
    phrase_max_words: Annotated[int, Field(ge=1)] = 5

    @model_validator(mode="after")
    def _word_window(self) -> "DiversityConfig":
        if self.phrase_min_words > self.phrase_max_words:
            raise ValueError("phrase_min_words must not exceed phrase_max_words")
        return self


class ResearchConfig(ConfigModel):
    window_days: Annotated[int, Field(ge=1)]
    min_source_count: Annotated[int, Field(ge=1)]
    min_successful_queries: Annotated[int, Field(ge=1)] = 6
    broad_queries: Annotated[int, Field(ge=1)] = 10
    pillar_queries: Annotated[int, Field(ge=1)] = 4
    deep_queries: Annotated[int, Field(ge=1)] = 8
    max_verification_searches: Annotated[int, Field(ge=1)] = 3
    feed_disable_after_failures: Annotated[int, Field(ge=1)] = 5


class EffectiveConfig(ConfigModel):
    schedule: ScheduleConfig
    topic_selection_mode: Literal["auto", "manual"] = "auto"
    word_count: WordCountRange
    default_category: str
    site_url: str
    publisher: PublisherKey
    routes: dict[str, list[str]]
    prompt_versions: dict[str, Annotated[int, Field(ge=1)]] = {}
    score_weights: ScoreWeights = ScoreWeights()
    novelty: NoveltyConfig
    diversity: DiversityConfig = DiversityConfig()
    research: ResearchConfig
    gate_override_policy: Literal["admin_with_reason", "never"] = "admin_with_reason"

    @model_validator(mode="after")
    def _routes_cover_every_agent(self) -> "EffectiveConfig":
        if set(self.routes) != set(AGENTS):
            raise ValueError(f"routes must contain exactly the agent keys {sorted(AGENTS)}")
        for agent, route in self.routes.items():
            if not route:
                raise ValueError(f"routes.{agent} must list at least one provider:model")
            for entry in route:
                _validate_openai_model_ceiling(agent, entry)
        return self


class SettingsValues(ConfigModel):
    """The stored ``blog_settings.values`` document: every EffectiveConfig block, optional."""

    schedule: ScheduleConfig | None = None
    topic_selection_mode: Literal["auto", "manual"] | None = None
    word_count: WordCountRange | None = None
    default_category: str | None = None
    site_url: str | None = None
    publisher: PublisherKey | None = None
    routes: dict[str, list[str]] | None = None
    prompt_versions: dict[str, Annotated[int, Field(ge=1)]] | None = None
    score_weights: ScoreWeights | None = None
    novelty: NoveltyConfig | None = None
    diversity: DiversityConfig | None = None
    research: ResearchConfig | None = None
    gate_override_policy: Literal["admin_with_reason", "never"] | None = None
    novelty_threshold: Annotated[float, Field(ge=0, le=1)] | None = None

    @model_validator(mode="after")
    def _routes_are_known_agents(self) -> "SettingsValues":
        if self.routes is not None:
            unknown = sorted(set(self.routes) - set(AGENTS))
            if unknown:
                raise ValueError(f"routes must contain only the agent keys {sorted(AGENTS)}; got {unknown}")
            for agent, route in self.routes.items():
                for entry in route:
                    if _ROUTE_ENTRY.fullmatch(entry) is None:
                        raise ValueError(f"routes.{agent} entry {entry!r} is not a provider:model")
                    _validate_openai_model_ceiling(agent, entry)
        return self


class BrandProfileValues(ConfigModel):
    """The stored ``blog_brand_profiles.profile`` document."""

    name: str
    description: str
    target_audience: str
    mission: str
    narrative: str
    focus_areas: list[str]
    emphasis: list[str]
    tone: list[str]
    avoid: list[str]
    prohibited_language: list[str]
    cta: str
    website: str
    target_word_count: WordCountRange | None = None
    ai_disclosure: str

    @field_validator("ai_disclosure")
    @classmethod
    def _disclosure_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ai_disclosure must not be blank")
        return value
