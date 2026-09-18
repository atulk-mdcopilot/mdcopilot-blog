"""Model routes: ordered ``provider:model`` lists from Settings, filtered by available keys."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from pydantic_ai.settings import ModelSettings

from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.settings import Settings

Provider = Literal["openai", "google", "anthropic"]
Reasoning = Literal["minimal", "low", "medium", "high"]

_PROVIDERS: Mapping[str, Provider] = {
    "openai": "openai",
    "google": "google",
    "anthropic": "anthropic",
}

_ROUTE_GETTERS: Mapping[AgentName, Callable[[Settings], list[str]]] = {
    AgentName.SEARCH: lambda s: s.search_route,
    AgentName.RESEARCH: lambda s: s.research_route,
    AgentName.IDEATION: lambda s: s.ideation_route,
    AgentName.DEEP_RESEARCH: lambda s: s.deep_research_route,
    AgentName.WRITER: lambda s: s.writer_route,
    AgentName.FACT_CHECK: lambda s: s.fact_check_route,
    AgentName.CLINICAL: lambda s: s.clinical_route,
    AgentName.EDITORIAL: lambda s: s.editorial_route,
    AgentName.SEO: lambda s: s.seo_route,
}


@dataclass(frozen=True)
class ModelChoice:
    provider: Provider
    model: str

    def ref(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_choice(raw: str) -> ModelChoice:
    provider_raw, separator, model = raw.strip().partition(":")
    provider_key = provider_raw.strip()
    model = model.strip()
    if not separator or not provider_key or not model:
        raise ValueError(f"invalid model route entry {raw!r}: expected 'provider:model'")
    provider = _PROVIDERS.get(provider_key)
    if provider is None:
        raise ValueError(f"invalid model route entry {raw!r}: unknown provider {provider_key!r}")
    return ModelChoice(provider=provider, model=model)


def _key_configured(settings: Settings, provider: Provider) -> bool:
    if provider == "openai":
        return settings.openai_api_key is not None
    if provider == "google":
        return settings.gemini_api_key is not None
    return settings.anthropic_api_key is not None


def route_from_entries(settings: Settings, agent: AgentName, entries: Sequence[str]) -> tuple[ModelChoice, ...]:
    """Ordered choices for explicit ``entries``, filtered exactly like the configured routes."""
    choices = tuple(parse_choice(entry) for entry in entries)
    choices = tuple(choice for choice in choices if _key_configured(settings, choice.provider))
    if not choices:
        raise ValueError(f"no usable model route for agent {agent.value!r}")
    return choices


def route_for(settings: Settings, agent: AgentName) -> tuple[ModelChoice, ...]:
    """Ordered choices for ``agent``, excluding entries whose provider key is not configured."""
    return route_from_entries(settings, agent, tuple(_ROUTE_GETTERS[agent](settings)))


def model_settings_for(
    choice: ModelChoice, *, max_tokens: int, timeout_seconds: float, reasoning: Reasoning | None
) -> ModelSettings:
    """Per-attempt model settings: token cap, numeric timeout and the provider's reasoning key."""
    if reasoning is None:
        return {"max_tokens": max_tokens, "timeout": timeout_seconds}
    if choice.provider == "openai":
        from pydantic_ai.models.openai import OpenAIResponsesModelSettings

        openai_settings: OpenAIResponsesModelSettings = {
            "max_tokens": max_tokens,
            "timeout": timeout_seconds,
            "openai_reasoning_effort": reasoning,
        }
        return cast(ModelSettings, openai_settings)
    if choice.provider == "google":
        from google.genai.types import ThinkingConfigDict, ThinkingLevel
        from pydantic_ai.models.google import GoogleModelSettings

        thinking: ThinkingConfigDict = {"thinking_level": ThinkingLevel(reasoning.upper())}
        google_settings: GoogleModelSettings = {
            "max_tokens": max_tokens,
            "timeout": timeout_seconds,
            "google_thinking_config": thinking,
        }
        return cast(ModelSettings, google_settings)
    from pydantic_ai.models.anthropic import AnthropicModelSettings
    from pydantic_ai.profiles.anthropic import AnthropicEffort

    effort = cast(AnthropicEffort, "low" if reasoning in ("minimal", "low") else reasoning)
    anthropic_settings: AnthropicModelSettings = {
        "max_tokens": max_tokens,
        "timeout": timeout_seconds,
        "anthropic_effort": effort,
    }
    return cast(ModelSettings, anthropic_settings)
