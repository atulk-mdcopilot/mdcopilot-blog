"""Web-search provider interface and shared result types."""

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    text: str
    allowed_domains: list[str] = Field(default_factory=list)
    max_results: int = 10
    recency_days: int | None = None
    mode: Literal["broad", "deep", "verification"] = "broad"
    route: list[str] | None = None


class SearchProviderError(RuntimeError):
    """A search provider call failed; picklable so DBOS steps can carry it."""

    def __init__(self, provider: str, error_class: str, status_code: int | None, message: str, retryable: bool) -> None:
        super().__init__(provider, error_class, status_code, message, retryable)
        self.provider = provider
        self.error_class = error_class
        self.status_code = status_code
        self.message = message
        self.retryable = retryable

    def __str__(self) -> str:
        prefix = (
            f"{self.error_class} (HTTP {self.status_code}): "
            if self.status_code is not None
            else f"{self.error_class}: "
        )
        return f"{prefix}{self.message}"

    def __reduce__(self) -> tuple[object, ...]:
        return (SearchProviderError, (self.provider, self.error_class, self.status_code, self.message, self.retryable))


class Citation(BaseModel):
    url: str
    title: str | None = None
    start_index: int | None = None
    end_index: int | None = None


class SearchResult(BaseModel):
    provider: str
    model: str
    answer_text: str
    citations: list[Citation]
    sources: list[str]
    search_actions: int
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    latency_ms: int = 0


class WebSearchProvider(Protocol):
    name: str

    async def search(self, query: SearchQuery) -> SearchResult: ...
