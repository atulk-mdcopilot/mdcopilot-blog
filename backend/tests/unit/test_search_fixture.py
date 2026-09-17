"""FixtureSearchProvider returns the shipped fixture with the query echoed."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from mdcopilot_blog.llm.search.base import SearchQuery, SearchResult, WebSearchProvider
from mdcopilot_blog.llm.search.fixture import FixtureSearchProvider


async def test_default_fixture_is_returned_with_prefixed_answer() -> None:
    provider = FixtureSearchProvider()
    result = await provider.search(SearchQuery(text="specialist wait times"))

    assert provider.name == "fixture"
    assert isinstance(result, SearchResult)
    assert result.provider == "fixture"
    assert result.model == "fixture-search"
    assert result.answer_text.startswith("[fixture] specialist wait times: ")
    assert result.search_actions == 1
    assert len(result.citations) == 2
    assert result.sources == [c.url for c in result.citations]
    assert result.cost_usd == Decimal(0)


async def test_custom_root_is_used(tmp_path: Path) -> None:
    (tmp_path / "default.json").write_text(
        json.dumps(
            {
                "provider": "fixture",
                "model": "custom-model",
                "answer_text": "custom answer",
                "citations": [{"url": "https://example.com/a"}],
                "sources": ["https://example.com/a"],
                "search_actions": 3,
            }
        ),
        encoding="utf-8",
    )
    provider: WebSearchProvider = FixtureSearchProvider(root=tmp_path)
    result = await provider.search(SearchQuery(text="q", allowed_domains=["example.com"], max_results=2))

    assert result.model == "custom-model"
    assert result.answer_text == "[fixture] q: custom answer"
    assert result.search_actions == 3
    assert result.citations[0].title is None
    assert result.input_tokens == 0


async def test_missing_fixture_names_the_path(tmp_path: Path) -> None:
    provider = FixtureSearchProvider(root=tmp_path)
    with pytest.raises(FileNotFoundError, match="default.json"):
        await provider.search(SearchQuery(text="q"))


def test_search_query_defaults() -> None:
    query = SearchQuery(text="q")
    assert query.allowed_domains == []
    assert query.max_results == 10
    assert query.recency_days is None
