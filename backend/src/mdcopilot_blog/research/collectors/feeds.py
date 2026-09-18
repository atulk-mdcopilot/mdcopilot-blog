"""RSS/Atom collector: per-feed quirks, conditional GET, windowing."""

import asyncio
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

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

_HREF_RE = re.compile(r'href="([^"]+)"')
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s?#\"<>]+")


@dataclass(frozen=True)
class RawItem:
    link: str
    title: str
    published_at: object | None
    doi: str | None


def parse_feed_entries(
    body: bytes, feed: FeedSpec, *, now: object, date_shift: timedelta
) -> tuple[list[RawItem], str | None]:

    import feedparser  # type: ignore[import-untyped, unused-ignore]

    parsed = feedparser.parse(body)
    if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", []):
        return [], f"unparseable feed: {type(parsed.bozo_exception).__name__}"
    items: list[RawItem] = []
    quirks = feed.quirks or {}
    resolve_to = quirks.get("resolve_to")
    for entry in parsed.entries:
        if quirks.get("link_from_title_href"):
            title_text = str(entry.get("title", ""))
            match = _HREF_RE.search(title_text)
            link = urljoin(feed.url, match.group(1)) if match else ""
        else:
            link = str(entry.get("link") or "")
            if not link.startswith(("http://", "https://")):
                candidate = str(entry.get("id") or "")
                link = candidate if candidate.startswith(("http://", "https://")) else ""
        if not link.startswith(("http://", "https://")):
            continue
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(entry.get("title", ""))))).strip()
        if not title:
            title = link

        published: datetime | None = None
        date_quirk = quirks.get("date_path")
        parsed_ok = False
        if isinstance(date_quirk, str) and "@" in date_quirk:
            key, attr = date_quirk.split("@", 1)
            holder = entry.get(key) or {}
            raw_value = holder.get(attr) if isinstance(holder, dict) else None
            if isinstance(raw_value, str):
                from mdcopilot_blog.research.extract import parse_datetime

                published = parse_datetime(raw_value)
                parsed_ok = published is not None
        if not parsed_ok:
            time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if time_struct:
                from mdcopilot_blog.research.extract import parse_datetime

                published = parse_datetime(
                    datetime(*time_struct[:6]).replace(tzinfo=UTC).isoformat()  # noqa: DTZ001
                )
                parsed_ok = published is not None
        if not parsed_ok and quirks.get("date_parser") == "dateutil":
            raw = str(entry.get("published") or entry.get("updated") or "")
            if raw:
                try:
                    from dateutil import parser as dateparser  # type: ignore[import-untyped, unused-ignore]

                    parsed_date = dateparser.parse(raw)
                    if parsed_date.tzinfo is None:
                        parsed_date = parsed_date.replace(tzinfo=UTC)
                    published = parsed_date.astimezone(UTC)
                except Exception:  # noqa: BLE001 - any dateutil failure means no feed date
                    published = None
        if published is None and date_quirk:
            # CMS's older entries can omit the nested time element while retaining
            # its non-RFC pubDate. Keep those dated so stale news is excluded.
            try:
                published = datetime.strptime(str(entry.get("published") or ""), "%a, %m/%d/%Y - %H:%M").replace(
                    tzinfo=UTC
                )
            except ValueError:
                pass
        if published is not None:
            shifted = published + date_shift if isinstance(published, datetime) else None
            published = plausible(shifted, now=now) if isinstance(now, datetime) else None

        doi: str | None = None
        if resolve_to:
            doi = str(entry.get("prism_doi") or "") or None
            if not doi:
                identifier = str(entry.get("dc_identifier") or "")
                if identifier.startswith("doi:"):
                    doi = identifier[4:]
            if not doi:
                match = _DOI_RE.search(link)
                if match:
                    doi = re.sub(r"v\d+$", "", match.group(0))
        items.append(RawItem(link=link, title=title, published_at=published, doi=doi))
    return items, None


async def collect_rss(env: ResearchEnvironment, feed: FeedSpec, *, now: object, window_days: int) -> FeedOutcome:

    assert isinstance(now, datetime)
    state: dict[str, Any] = dict(feed.state or {})
    etag_object = state.get("etag")
    last_modified_object = state.get("lastModified")
    result = await fetch(
        env,
        feed.url,
        header_profile=feed.header_profile,
        etag=etag_object if isinstance(etag_object, str) else None,
        last_modified=last_modified_object if isinstance(last_modified_object, str) else None,
        check_robots=False,
    )
    if result.status != FetchStatus.OK:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error=result.error,
            http_status=result.http_status,
            not_modified=False,
            new_state=state,
            items_in_window=0,
        )

    quirks = feed.quirks or {}
    resolve_to = quirks.get("resolve_to")
    if result.not_modified:
        items_object = state.get("items", [])
        cached: list[Signal] = [Signal.from_json(item) for item in items_object if isinstance(item, dict)]
        cached_kept = [signal for signal in cached if in_window(signal.published_at, now=now, window_days=window_days)]
        cached_signals = newest_first(cached_kept, limit=MAX_ITEMS_PER_FEED)
        return FeedOutcome(
            feed=feed,
            ok=True,
            fetched=True,
            signals=cached_signals,
            error=None,
            http_status=result.http_status,
            not_modified=True,
            new_state=state,
            items_in_window=len(cached_signals),
        )

    items, parse_error = await asyncio.to_thread(
        parse_feed_entries, result.body, feed, now=now, date_shift=env.date_shift
    )
    if parse_error:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error=parse_error,
            http_status=result.http_status,
            not_modified=False,
            new_state=state,
            items_in_window=0,
        )
    kept: list[RawItem] = [
        item
        for item in items
        if in_window(
            item.published_at if isinstance(item.published_at, datetime | None) else None,
            now=now,
            window_days=window_days,
        )
    ]
    signals: list[Signal] = []
    if not resolve_to:
        signals = newest_first(
            [
                Signal(
                    url=item.link,
                    title=item.title,
                    published_at=item.published_at if isinstance(item.published_at, datetime) else None,
                    date_source=DateSource.FEED if isinstance(item.published_at, datetime) else DateSource.NONE,
                    discovered_via=DiscoveredVia.FEED,
                    feed_id=feed.id,
                    external_ids={"doi": item.doi} if item.doi else {},
                )
                for item in kept
            ],
            limit=MAX_ITEMS_PER_FEED,
        )

    if resolve_to == "pubmed":
        from mdcopilot_blog.research.collectors.pubmed import PubMedError, resolve_dois

        dois = [item.doi for item in kept if item.doi]
        try:
            resolved = await resolve_dois(env, dois, now=now)
        except PubMedError:
            resolved = []
        by_doi = {entry.doi: entry for entry in resolved if entry.doi}
        pending: list[Signal] = []
        for item in kept:
            entry = by_doi.get(item.doi or "")
            item_date = item.published_at if isinstance(item.published_at, datetime) else None
            if entry is not None:
                pending.append(
                    Signal(
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{entry.pmid}/",
                        title=item.title if item.title != item.link else entry.title,
                        published_at=entry.published_at or item_date,
                        date_source=DateSource.API
                        if entry.published_at
                        else (DateSource.FEED if item_date else DateSource.NONE),
                        discovered_via=DiscoveredVia.PUBMED,
                        feed_id=feed.id,
                        external_ids={"pmid": entry.pmid, **({"doi": item.doi} if item.doi else {})},
                    )
                )
            else:
                pending.append(
                    Signal(
                        url=item.link,
                        title=item.title,
                        published_at=item_date,
                        date_source=DateSource.FEED if item_date else DateSource.NONE,
                        discovered_via=DiscoveredVia.FEED,
                        feed_id=feed.id,
                        external_ids={"doi": item.doi} if item.doi else {},
                    )
                )
        signals = newest_first(pending, limit=MAX_ITEMS_PER_FEED)
    elif resolve_to == "doi":
        signals = newest_first(
            [
                Signal(
                    url=item.link,
                    title=item.title,
                    published_at=item.published_at if isinstance(item.published_at, datetime) else None,
                    date_source=DateSource.FEED if isinstance(item.published_at, datetime) else DateSource.NONE,
                    discovered_via=DiscoveredVia.FEED,
                    feed_id=feed.id,
                    external_ids={"doi": item.doi} if item.doi else {},
                )
                for item in kept
            ],
            limit=MAX_ITEMS_PER_FEED,
        )

    new_state = {
        **state,
        "etag": result.etag or state.get("etag"),
        "lastModified": result.last_modified or state.get("lastModified"),
        "items": [signal.to_json() for signal in signals],
    }
    new_state = {key: value for key, value in new_state.items() if value is not None}
    return FeedOutcome(
        feed=feed,
        ok=True,
        fetched=True,
        signals=signals,
        error=None,
        http_status=result.http_status,
        not_modified=False,
        new_state=new_state,
        items_in_window=len(kept),
    )
