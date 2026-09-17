"""Web search provider interface. Real providers arrive in Phase 2."""

from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    text: str
    allowed_domains: list[str] = Field(default_factory=list)
    max_results: int = 10
    recency_days: int | None = None


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
