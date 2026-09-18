"""Collector dispatch: one entry point, quirks live in the modules."""

import asyncio
from datetime import datetime

from mdcopilot_blog.research.collectors.fda_csv import collect_fda_csv
from mdcopilot_blog.research.collectors.federal_register import collect_federal_register
from mdcopilot_blog.research.collectors.feeds import collect_rss
from mdcopilot_blog.research.collectors.pubmed import collect_pubmed_search
from mdcopilot_blog.research.environment import ResearchEnvironment
from mdcopilot_blog.research.signals import FeedOutcome, FeedSpec

_COLLECTORS = {
    "rss": collect_rss,
    "atom": collect_rss,
    "pubmed": collect_pubmed_search,
    "federal_register": collect_federal_register,
    "fda_ai_devices_csv": collect_fda_csv,
}


async def collect_feed(env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int) -> FeedOutcome:
    collector = _COLLECTORS.get(feed.kind.value)
    if collector is None:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=False,
            signals=[],
            error=f"unsupported feed kind {feed.kind.value}",
            http_status=None,
            not_modified=False,
            new_state=dict(feed.state or {}),
            items_in_window=0,
        )
    try:
        return await collector(env, feed, now=now, window_days=window_days)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - any collector failure becomes a feed outcome
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error=f"{type(exc).__name__}: {exc}"[:2000],
            http_status=None,
            not_modified=False,
            new_state=dict(feed.state or {}),
            items_in_window=0,
        )
