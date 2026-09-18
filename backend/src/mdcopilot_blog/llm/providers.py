"""Real provider models: OpenAI Responses, Google, Anthropic.

SDK retries are off (the gateway's route walking owns retries). No tools, no grounding and no
web search are attached here. ``ALLOW_MODEL_REQUESTS`` is never touched by this module.
"""

from typing import Any

import httpx2

from mdcopilot_blog.llm.gateway import AgentSpec
from mdcopilot_blog.llm.routes import ModelChoice
from mdcopilot_blog.settings import Settings


class RealModelFactory:
    """Builds a real provider model per route entry; provider objects are cached per timeout."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._providers: dict[tuple[str, float], Any] = {}

    def _client_for(self, timeout_seconds: float) -> Any:
        return httpx2.AsyncClient(timeout=httpx2.Timeout(timeout_seconds))

    def _openai_provider(self, timeout_seconds: float) -> Any:
        from openai import AsyncOpenAI
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = self._settings.openai_api_key
        if api_key is None:
            from mdcopilot_blog.llm.gateway import ProviderNotAvailable

            raise ProviderNotAvailable("OPENAI_API_KEY is not set")
        return OpenAIProvider(
            openai_client=AsyncOpenAI(
                api_key=api_key.get_secret_value(), max_retries=0, http_client=self._client_for(timeout_seconds)
            )
        )

    def _google_provider(self, timeout_seconds: float) -> Any:
        from google.genai.types import HttpRetryOptions
        from pydantic_ai.providers.google import GoogleProvider

        api_key = self._settings.gemini_api_key
        if api_key is None:
            from mdcopilot_blog.llm.gateway import ProviderNotAvailable

            raise ProviderNotAvailable("GEMINI_API_KEY is not set")
        return GoogleProvider(
            api_key=api_key.get_secret_value(),
            retry_options=HttpRetryOptions(attempts=1),
            http_client=self._client_for(timeout_seconds),
        )

    def _anthropic_provider(self, timeout_seconds: float) -> Any:
        from anthropic import AsyncAnthropic
        from pydantic_ai.providers.anthropic import AnthropicProvider

        api_key = self._settings.anthropic_api_key
        if api_key is None:
            from mdcopilot_blog.llm.gateway import ProviderNotAvailable

            raise ProviderNotAvailable("ANTHROPIC_API_KEY is not set")
        return AnthropicProvider(
            anthropic_client=AsyncAnthropic(
                api_key=api_key.get_secret_value(), max_retries=0, http_client=self._client_for(timeout_seconds)
            )
        )

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Any:
        cache_key = (choice.provider, spec.timeout_seconds)
        provider = self._providers.get(cache_key)
        if provider is None:
            builders = {
                "openai": self._openai_provider,
                "google": self._google_provider,
                "anthropic": self._anthropic_provider,
            }
            provider = builders[choice.provider](spec.timeout_seconds)
            self._providers[cache_key] = provider
        if choice.provider == "openai":
            from pydantic_ai.models.openai import OpenAIResponsesModel

            return OpenAIResponsesModel(choice.model, provider=provider)
        if choice.provider == "google":
            from pydantic_ai.models.google import GoogleModel

            return GoogleModel(choice.model, provider=provider)
        from pydantic_ai.models.anthropic import AnthropicModel

        return AnthropicModel(choice.model, provider=provider)
