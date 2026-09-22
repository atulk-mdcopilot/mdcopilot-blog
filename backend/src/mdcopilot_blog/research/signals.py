"""Signals: URLs found by web search, and date windowing."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from mdcopilot_blog.domain.enums import DateSource, DiscoveredVia

_EARLIEST = datetime(1995, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Signal:
    url: str
    title: str
    published_at: datetime | None
    date_source: DateSource
    discovered_via: DiscoveredVia
    external_ids: Mapping[str, str] = field(default_factory=dict)
    answer_excerpt: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "url": self.url,
            "title": self.title,
            "publishedAt": self.published_at.isoformat() if self.published_at is not None else None,
            "dateSource": self.date_source.value,
            "discoveredVia": self.discovered_via.value,
            "externalIds": dict(self.external_ids),
            "answerExcerpt": self.answer_excerpt,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, object]) -> "Signal":
        published = _optional_str(data.get("publishedAt"))
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
            external_ids=ids,
            answer_excerpt=excerpt,
        )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


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
