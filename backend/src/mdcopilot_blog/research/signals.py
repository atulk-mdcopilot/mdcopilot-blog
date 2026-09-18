"""Signals: what collectors produce; windowing and ordering."""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from mdcopilot_blog.domain.contracts import SourceType
from mdcopilot_blog.domain.enums import DateSource, DiscoveredVia, FeedKind
from mdcopilot_blog.domain.tiers import FeedHint, HeaderProfile

MAX_ITEMS_PER_FEED = 20
_EARLIEST = datetime(1995, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class FeedSpec:
    id: uuid.UUID | None
    name: str
    url: str
    kind: FeedKind
    group: str
    tier: int
    source_type: SourceType
    header_profile: HeaderProfile
    quirks: Mapping[str, object]
    is_preprint: bool
    state: Mapping[str, object]
    last_fetched_at: datetime | None

    def hint(self) -> FeedHint:
        return FeedHint(
            feed_url=self.url,
            feed_name=self.name,
            tier=self.tier,
            source_type=self.source_type,
            is_preprint=self.is_preprint,
            header_profile=self.header_profile,
        )


@dataclass(frozen=True)
class Signal:
    url: str
    title: str
    published_at: datetime | None
    date_source: DateSource
    discovered_via: DiscoveredVia
    feed_id: uuid.UUID | None
    external_ids: Mapping[str, str] = field(default_factory=dict)
    answer_excerpt: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "url": self.url,
            "title": self.title,
            "publishedAt": self.published_at.isoformat() if self.published_at is not None else None,
            "dateSource": self.date_source.value,
            "discoveredVia": self.discovered_via.value,
            "feedId": str(self.feed_id) if self.feed_id is not None else None,
            "externalIds": dict(self.external_ids),
            "answerExcerpt": self.answer_excerpt,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, object]) -> "Signal":
        published = _optional_str(data.get("publishedAt"))
        feed_id = _optional_str(data.get("feedId"))
        raw_ids = data.get("externalIds")
        ids: dict[str, str] = (
            {str(key): str(value) for key, value in raw_ids.items()} if isinstance(raw_ids, dict) else {}
        )
        excerpt = _optional_str(data.get("answerExcerpt"))
        return cls(
            url=str(data["url"]),
            title=str(data["title"]),
            published_at=datetime.fromisoformat(published) if published else None,
            date_source=DateSource(str(data["dateSource"])),
            discovered_via=DiscoveredVia(str(data["discoveredVia"])),
            feed_id=uuid.UUID(feed_id) if feed_id else None,
            external_ids=ids,
            answer_excerpt=excerpt,
        )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


@dataclass(frozen=True)
class FeedOutcome:
    feed: FeedSpec
    ok: bool
    fetched: bool
    signals: list[Signal]
    error: str | None
    http_status: int | None
    not_modified: bool
    new_state: dict[str, object]
    items_in_window: int


def in_window(published_at: datetime | None, *, now: datetime, window_days: int) -> bool:
    if published_at is None:
        return True
    return published_at >= now - timedelta(days=window_days)


def plausible(value: datetime | None, *, now: datetime) -> datetime | None:
    if value is None:
        return None
    if value > now + timedelta(days=1) or value < _EARLIEST:
        return None
    return value


def newest_first(signals: Sequence[Signal], *, limit: int) -> list[Signal]:
    dated = [signal for signal in signals if signal.published_at is not None]
    undated = [signal for signal in signals if signal.published_at is None]
    ordered = sorted(dated, key=lambda signal: signal.published_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    return (ordered + list(undated))[:limit]
