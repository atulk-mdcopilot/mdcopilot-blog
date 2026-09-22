"""Effective-configuration models.

Snake_case in Python, camelCase on the wire; both spellings accepted on input; unknown keys
rejected. ``services.config.load_effective_config`` builds the effective config from the environment; these models
only validate shapes.
"""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from mdcopilot_blog.domain.enums import AgentName

AGENTS = tuple(agent.value for agent in AgentName)
"""The configurable agent route keys."""

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


class ResearchConfig(ConfigModel):
    window_days: Annotated[int, Field(ge=1)]
    min_source_count: Annotated[int, Field(ge=1)]
    min_successful_queries: Annotated[int, Field(ge=1)] = 6
    deep_queries: Annotated[int, Field(ge=1)] = 8
    max_verification_searches: Annotated[int, Field(ge=1)] = 3


class EffectiveConfig(ConfigModel):
    word_count: WordCountRange
    default_category: str
    site_url: str
    routes: dict[str, list[str]]
    research: ResearchConfig

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
