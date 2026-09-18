"""Search runner: parallel queries, transient retries, source collection."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import httpx
import httpx2

from mdcopilot_blog.domain import urls
from mdcopilot_blog.domain.enums import DateSource, DiscoveredVia
from mdcopilot_blog.domain.query_plan import PlannedQuery
from mdcopilot_blog.llm.gateway import BudgetExceeded, CallContext
from mdcopilot_blog.llm.search.base import SearchQuery
from mdcopilot_blog.research.environment import ResearchEnvironment
from mdcopilot_blog.research.signals import Signal

TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})
TRANSIENT_CLASS_NAMES: frozenset[str] = frozenset({"APIConnectionError", "APITimeoutError"})
SEARCH_ATTEMPTS = 3
SEARCH_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0)
ANSWER_EXCERPT_CHARS = 1500

SearchMode = Literal["broad", "deep", "verification"]


@dataclass(frozen=True)
class QueryOutcome:
    planned: PlannedQuery
    status: Literal["ok", "failed"]
    search_actions: int
    source_urls: list[str]
    source_titles: dict[str, str]
    answer_excerpt: str | None
    error: str | None
    attempts: int


def is_transient_search_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError | httpx2.TransportError):
        return True
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code in TRANSIENT_STATUS_CODES:
        return True
    return type(exc).__name__ in TRANSIENT_CLASS_NAMES


async def _run_one(
    sc: object,
    env: ResearchEnvironment,
    planned: PlannedQuery,
    *,
    mode: SearchMode,
    recency_days: int | None,
    allowed_domains: Sequence[str],
    ctx: CallContext,
) -> QueryOutcome:
    attempts = 0
    last_error: BaseException | None = None
    while attempts < SEARCH_ATTEMPTS:
        attempts += 1
        try:
            result = await sc.gateway.search(  # type: ignore[attr-defined]
                SearchQuery(
                    text=planned.text,
                    mode=mode,
                    recency_days=recency_days,
                    allowed_domains=list(allowed_domains),
                    max_results=10,
                ),
                ctx=ctx,
            )
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - classified below
            last_error = exc
            if is_transient_search_error(exc) and attempts < SEARCH_ATTEMPTS:
                await asyncio.sleep(SEARCH_BACKOFF_SECONDS[attempts - 1])
                continue
            return QueryOutcome(
                planned=planned,
                status="failed",
                search_actions=0,
                source_urls=[],
                source_titles={},
                answer_excerpt=None,
                error=f"{type(exc).__name__}: {exc}"[:500],
                attempts=attempts,
            )
        source_urls: list[str] = []
        source_titles: dict[str, str] = {}
        seen_canonical: set[str] = set()
        citations_by_url: dict[str, str] = {}
        for citation in result.citations:
            if citation.title and citation.url not in citations_by_url:
                citations_by_url[citation.url] = citation.title
        for url in [*result.sources, *(c.url for c in result.citations)]:
            if len(source_urls) >= 10:
                break
            if not urls.is_http_url(url):
                continue
            canonical = urls.canonicalize_url(url)
            if canonical in seen_canonical:
                continue
            seen_canonical.add(canonical)
            source_urls.append(url)
            title = citations_by_url.get(url, "")
            if title.strip():
                source_titles[url] = title
        answer = result.answer_text.strip()
        return QueryOutcome(
            planned=planned,
            status="ok",
            search_actions=result.search_actions,
            source_urls=source_urls,
            source_titles=source_titles,
            answer_excerpt=answer[:ANSWER_EXCERPT_CHARS] if answer else None,
            error=None,
            attempts=attempts,
        )
    return QueryOutcome(
        planned=planned,
        status="failed",
        search_actions=0,
        source_urls=[],
        source_titles={},
        answer_excerpt=None,
        error=f"{type(last_error).__name__}: {last_error}"[:500] if last_error else "unknown error",
        attempts=attempts,
    )


async def run_search_queries(
    sc: object,
    env: ResearchEnvironment,
    queries: Sequence[PlannedQuery],
    *,
    mode: SearchMode,
    recency_days: int | None,
    allowed_domains: Sequence[str],
    ctx: CallContext,
) -> list[QueryOutcome]:
    semaphore = asyncio.Semaphore(sc.settings.max_parallel_searches)  # type: ignore[attr-defined]

    async def guarded(planned: PlannedQuery) -> QueryOutcome:
        async with semaphore:
            return await _run_one(
                sc, env, planned, mode=mode, recency_days=recency_days, allowed_domains=allowed_domains, ctx=ctx
            )

    return list(await asyncio.gather(*(guarded(planned) for planned in queries)))


def outcome_signals(
    outcome: QueryOutcome, *, discovered_via: DiscoveredVia, keep: Callable[[str], bool] | None = None
) -> list[Signal]:
    if outcome.status != "ok":
        return []
    signals: list[Signal] = []
    for url in outcome.source_urls:
        if keep is not None and not keep(url):
            continue
        signals.append(
            Signal(
                url=url,
                title=outcome.source_titles.get(url, url),
                published_at=None,
                date_source=DateSource.NONE,
                discovered_via=discovered_via,
                feed_id=None,
                external_ids={},
                answer_excerpt=outcome.answer_excerpt,
            )
        )
    return signals


def query_json(outcome: QueryOutcome, *, source_count: int) -> dict[str, object]:
    return {
        "text": outcome.planned.text,
        "themeKey": outcome.planned.theme_key,
        "status": outcome.status,
        "searchActions": outcome.search_actions,
        "sourceCount": source_count,
        "error": outcome.error,
    }
