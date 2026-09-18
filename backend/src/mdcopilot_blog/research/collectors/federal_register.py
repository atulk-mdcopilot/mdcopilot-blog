"""Federal Register collector: documents.json with fields and date window."""

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx

from mdcopilot_blog.domain.enums import DateSource, DiscoveredVia, FetchStatus
from mdcopilot_blog.research.environment import ResearchEnvironment
from mdcopilot_blog.research.retriever import fetch
from mdcopilot_blog.research.signals import (
    MAX_ITEMS_PER_FEED,
    FeedOutcome,
    FeedSpec,
    Signal,
    in_window,
    newest_first,
    plausible,
)

FR_FIELDS: tuple[str, ...] = (
    "title",
    "abstract",
    "document_number",
    "html_url",
    "publication_date",
    "type",
    "agencies",
)


def federal_register_url(feed: FeedSpec, *, since: date) -> str:
    base = feed.url.split("#", 1)[0]
    pairs: list[tuple[str, str]] = []
    quirks = dict(feed.quirks or {})
    params = quirks.get("query_params") or {}
    if isinstance(params, dict):
        for key, value in params.items():
            if key.endswith("[]") and isinstance(value, str) and "," in value:
                for item in value.split(","):
                    pairs.append((key, item))
            else:
                pairs.append((key, str(value)))
    pairs.append(("conditions[publication_date][gte]", since.isoformat()))
    for field_name in FR_FIELDS:
        pairs.append(("fields[]", field_name))
    return str(httpx.URL(base, params=pairs))


async def collect_federal_register(
    env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int
) -> FeedOutcome:
    since = (now - timedelta(days=window_days)).date()
    result = await fetch(env, federal_register_url(feed, since=since), check_robots=False)
    if result.status != FetchStatus.OK:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error=result.error,
            http_status=result.http_status,
            not_modified=False,
            new_state=dict(feed.state or {}),
            items_in_window=0,
        )
    try:
        data: Any = json.loads(result.body)
    except json.JSONDecodeError:
        data = None
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error="unexpected federal register response",
            http_status=result.http_status,
            not_modified=False,
            new_state=dict(feed.state or {}),
            items_in_window=0,
        )
    signals: list[Signal] = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        html_url = entry.get("html_url")
        if not isinstance(html_url, str) or not html_url.startswith(("http://", "https://")):
            continue
        published_at: datetime | None = None
        publication_date = entry.get("publication_date")
        if isinstance(publication_date, str):
            try:
                published_at = datetime.combine(date.fromisoformat(publication_date), time(0), UTC)
            except ValueError:
                published_at = None
        published_at = plausible(published_at, now=now)
        document_number = entry.get("document_number")
        signals.append(
            Signal(
                url=html_url,
                title=str(entry.get("title") or html_url),
                published_at=published_at,
                date_source=DateSource.API if published_at else DateSource.NONE,
                discovered_via=DiscoveredVia.FEDERAL_REGISTER,
                feed_id=feed.id,
                external_ids={"frDocumentNumber": str(document_number)} if document_number else {},
                answer_excerpt=None,
            )
        )
    kept = [signal for signal in signals if in_window(signal.published_at, now=now, window_days=window_days)]
    ordered = newest_first(kept, limit=MAX_ITEMS_PER_FEED)
    return FeedOutcome(
        feed=feed,
        ok=True,
        fetched=True,
        signals=ordered,
        error=None,
        http_status=result.http_status,
        not_modified=False,
        new_state=dict(feed.state or {}),
        items_in_window=len(kept),
    )
