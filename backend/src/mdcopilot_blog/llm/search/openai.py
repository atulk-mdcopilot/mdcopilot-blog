"""OpenAI Responses web search: plain text, max_tool_calls, citations+sources."""

import time
from decimal import Decimal
from typing import Any, Final, cast

import httpx2

from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.llm.gateway import ProviderNotAvailable
from mdcopilot_blog.llm.routes import route_for
from mdcopilot_blog.llm.search.base import Citation, SearchProviderError, SearchQuery, SearchResult
from mdcopilot_blog.settings import Settings

SEARCH_TIMEOUT_SECONDS: Final = 120.0
MAX_ALLOWED_DOMAINS: Final = 100
SEARCH_INSTRUCTIONS: Final = (
    "Use web search to answer the question. Reply in plain text in at most 200 words. Cite every source you rely on."
)

_RETRYABLE_STATUS: Final = frozenset({408, 409, 429})


class OpenAISearchResult(SearchResult):
    usage_details: dict[str, str | int | None]


def default_search_model(settings: Settings) -> str:
    try:
        choices = route_for(settings, AgentName.SEARCH)
    except ValueError as exc:
        raise ProviderNotAvailable("search route has no usable openai entry") from exc
    for choice in choices:
        if choice.provider == "openai":
            return choice.model
    raise ProviderNotAvailable("search route has no usable openai entry")


class OpenAIWebSearchProvider:
    """Responses API web search, one plain-text call; the gateway owns pricing."""

    name = "openai"
    model: str

    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ProviderNotAvailable("OPENAI_API_KEY is not set")
        from openai import AsyncOpenAI

        self._settings = settings
        self.model = default_search_model(settings)
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            max_retries=0,
            http_client=httpx2.AsyncClient(timeout=httpx2.Timeout(SEARCH_TIMEOUT_SECONDS)),
        )

    async def search(self, query: SearchQuery) -> OpenAISearchResult:
        if len(query.allowed_domains) > MAX_ALLOWED_DOMAINS:
            raise ValueError("allowed_domains accepts at most 100 domains")
        if query.mode in ("broad", "verification"):
            size = self._settings.search_context_size_broad
            max_calls = self._settings.search_max_tool_calls_broad
        else:
            size = self._settings.search_context_size_deep
            max_calls = self._settings.search_max_tool_calls_deep

        tool: dict[str, Any] = {"type": "web_search", "search_context_size": size}
        if query.allowed_domains:
            tool["filters"] = {"allowed_domains": list(query.allowed_domains)}
        text = query.text
        if query.recency_days is not None:
            text += f"\n\nPrefer sources published in the last {query.recency_days} days."

        started = time.perf_counter()
        try:
            response = await self._client.responses.create(
                model=self.model,
                instructions=SEARCH_INSTRUCTIONS,
                input=text,
                tools=[cast(Any, tool)],
                tool_choice="required",
                include=["web_search_call.action.sources"],
                max_tool_calls=max_calls,
                store=False,
                timeout=SEARCH_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

        if response.status in ("failed", "cancelled"):
            error = getattr(response, "error", None)
            code = error.code if error is not None else None
            message = error.message if error is not None else None
            raise SearchProviderError(
                "openai",
                "ResponseFailed",
                None,
                f"{response.status}: {code if code else 'no error'}: {message if message else ''}",
                retryable=True,
            )

        citations: list[Citation] = []
        source_urls: list[str] = []
        search_items = 0
        action_sources = 0
        for item in response.output:
            item_type = getattr(item, "type", None)
            if item_type == "web_search_call":
                action = getattr(item, "action", None)
                if getattr(action, "type", None) == "search":
                    search_items += 1
                    sources = getattr(action, "sources", None) or []
                    for source in sources:
                        action_sources += 1
                        if source.url not in source_urls:
                            source_urls.append(source.url)
            elif item_type == "message":
                for part in getattr(item, "content", None) or []:
                    if getattr(part, "type", None) == "output_text":
                        for annotation in getattr(part, "annotations", None) or []:
                            if getattr(annotation, "type", None) == "url_citation":
                                citations.append(
                                    Citation(
                                        url=annotation.url,
                                        title=annotation.title,
                                        start_index=annotation.start_index,
                                        end_index=annotation.end_index,
                                    )
                                )
                                if annotation.url not in source_urls:
                                    source_urls.append(annotation.url)

        extra = response.model_extra or {}
        num_requests: int | None = None
        num_requests_source = "output_items"
        tool_usage = extra.get("tool_usage")
        if isinstance(tool_usage, dict):
            web_search = tool_usage.get("web_search")
            if isinstance(web_search, dict):
                candidate = web_search.get("num_requests")
                if isinstance(candidate, int) and candidate >= 0:
                    num_requests = candidate
                    num_requests_source = "tool_usage"
        search_actions = num_requests if num_requests is not None else search_items

        usage = response.usage
        input_tokens = usage.input_tokens if usage is not None else 0
        output_tokens = usage.output_tokens if usage is not None else 0
        cached = 0
        reasoning = 0
        if usage is not None:
            input_details = getattr(usage, "input_tokens_details", None)
            cached = getattr(input_details, "cached_tokens", 0) if input_details is not None else 0
            output_details = getattr(usage, "output_tokens_details", None)
            reasoning = getattr(output_details, "reasoning_tokens", 0) if output_details is not None else 0

        return OpenAISearchResult(
            provider="openai",
            model=response.model,
            answer_text=response.output_text,
            citations=citations,
            sources=source_urls,
            search_actions=search_actions,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=Decimal(0),
            latency_ms=int((time.perf_counter() - started) * 1000),
            usage_details={
                "response_id": response.id,
                "status": response.status,
                "action_source_count": action_sources,
                "citation_count": len(citations),
                "num_requests_source": num_requests_source,
                "cache_read_tokens": cached,
                "reasoning_tokens": reasoning,
                "search_context_size": size,
                "max_tool_calls": max_calls,
            },
        )

    def _map_error(self, exc: Exception) -> Exception:
        status = getattr(exc, "status_code", None)
        if status is not None:
            name = type(exc).__name__
            message = str(getattr(exc, "message", None) or exc)[:500]
            retryable = status in _RETRYABLE_STATUS or status >= 500
            return SearchProviderError("openai", name, status, message, retryable)
        from openai import APIConnectionError

        if isinstance(exc, APIConnectionError | httpx2.TransportError):
            return SearchProviderError("openai", type(exc).__name__, None, str(exc)[:500], retryable=True)
        return exc
