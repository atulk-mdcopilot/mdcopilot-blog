"""Model routes: ordered ``provider:model`` lists from Settings, filtered by available keys."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.settings import Settings

Provider = Literal["openai", "google", "anthropic", "mock"]

_PROVIDERS: Mapping[str, Provider] = {
    "openai": "openai",
    "google": "google",
    "anthropic": "anthropic",
    "mock": "mock",
}

HELLO_ROUTE: tuple[str, ...] = ("mock:hello",)

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
    if provider == "anthropic":
        return settings.anthropic_api_key is not None
    return True  # "mock" needs no key


def route_for(settings: Settings, agent: AgentName) -> tuple[ModelChoice, ...]:
    """Ordered choices for ``agent``.

    Mock mode returns the route unfiltered (the mock factory ignores the provider).
    Otherwise entries whose provider key is not configured are dropped.
    """
    if agent == AgentName.HELLO:
        raw_route: tuple[str, ...] = HELLO_ROUTE
    else:
        raw_route = tuple(_ROUTE_GETTERS[agent](settings))
    choices = tuple(parse_choice(entry) for entry in raw_route)
    if not settings.mock_mode:
        choices = tuple(choice for choice in choices if _key_configured(settings, choice.provider))
    if not choices:
        raise ValueError(f"no usable model route for agent {agent.value!r}")
    return choices
