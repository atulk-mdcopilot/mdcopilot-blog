"""Deterministic search provider for mock mode and tests."""

import json
from pathlib import Path

from mdcopilot_blog.llm.search.base import SearchQuery, SearchResult


def default_search_fixture_root() -> Path:
    """``backend/fixtures/mock/search`` (editable install), else ``<cwd>/fixtures/mock/search``."""
    candidate = Path(__file__).resolve().parents[4] / "fixtures" / "mock" / "search"
    if candidate.is_dir():
        return candidate
    return Path.cwd() / "fixtures" / "mock" / "search"


class FixtureSearchProvider:
    name = "fixture"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else default_search_fixture_root()

    async def search(self, query: SearchQuery) -> SearchResult:
        path = self.root / "default.json"
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"search fixture not found: {path}") from None
        base = SearchResult.model_validate(json.loads(raw))
        return base.model_copy(update={"answer_text": f"[fixture] {query.text}: {base.answer_text}"})
