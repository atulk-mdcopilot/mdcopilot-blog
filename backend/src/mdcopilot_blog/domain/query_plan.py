"""Query planner: theme rotation, broad and deep."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

MONTH_YEAR_TOKEN = "{month_year}"
MAX_QUERY_CHARS = 300


@dataclass(frozen=True)
class ThemeState:
    key: str
    name: str
    query_templates: tuple[str, ...]
    pillar_keys: tuple[str, ...]
    is_active: bool
    last_searched_at: datetime | None
    sort_order: int


@dataclass(frozen=True)
class PlannedQuery:
    text: str
    theme_key: str | None
    facet: str | None


DEEP_FACETS: tuple[tuple[str, str], ...] = (
    ("primary_source", '"{title}" primary source'),
    ("announcement", "{title} official announcement"),
    ("research", "{thesis} peer-reviewed study PubMed"),
    ("regulatory", "{title} FDA CMS HHS regulation guidance"),
    ("statistics", "{title} statistics data {month_year}"),
    ("expert_commentary", "{title} physician expert commentary"),
    ("counterarguments", "{thesis} limitations criticism risks"),
    ("industry_context", "{title} healthcare industry context {pillar}"),
)


def render_template(template: str, *, today: date) -> str:
    rendered = template.replace(MONTH_YEAR_TOKEN, today.strftime("%B %Y"))
    rendered = re.sub(r"\s+", " ", rendered).strip()
    return rendered[:MAX_QUERY_CHARS]


def _theme_order_key(theme: ThemeState) -> tuple[bool, datetime, int, str]:
    return (
        theme.last_searched_at is not None,
        theme.last_searched_at or datetime.min.replace(tzinfo=UTC),
        theme.sort_order,
        theme.key,
    )


def plan_broad_queries(
    themes: Sequence[ThemeState],
    *,
    pillar_key: str | None,
    today: date,
    broad_queries: int,
    pillar_queries: int,
) -> list[PlannedQuery]:
    usable = [theme for theme in themes if theme.is_active and theme.query_templates]
    pillar_candidates = [theme for theme in usable if pillar_key is not None and pillar_key in theme.pillar_keys]
    other_candidates = [theme for theme in usable if pillar_key is None or pillar_key not in theme.pillar_keys]
    pillar_candidates.sort(key=_theme_order_key)
    other_candidates.sort(key=_theme_order_key)
    pillar_picks = pillar_candidates[: min(pillar_queries, len(pillar_candidates))]
    other_picks = other_candidates[: max(0, broad_queries - len(pillar_picks))]

    picked: list[ThemeState] = [*pillar_picks, *other_picks]
    output: list[PlannedQuery] = []
    seen: set[str] = set()

    def _add(theme: ThemeState, template_index: int) -> bool:
        query = render_template(theme.query_templates[template_index % len(theme.query_templates)], today=today)
        if query.lower() in seen:
            return False
        seen.add(query.lower())
        output.append(PlannedQuery(text=query, theme_key=theme.key, facet=None))
        return True

    for theme in picked:
        _add(theme, today.toordinal() % len(theme.query_templates))

    if len(output) < broad_queries and picked:
        k = 1
        made_progress = True
        while len(output) < broad_queries and made_progress:
            made_progress = False
            for theme in picked:
                if len(output) >= broad_queries:
                    break
                base = today.toordinal() % len(theme.query_templates)
                if _add(theme, (base + k) % len(theme.query_templates)):
                    made_progress = True
            k += 1
    return output


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.strip()


def plan_deep_queries(
    *,
    title: str,
    thesis: str,
    pillar_name: str | None,
    today: date,
    deep_queries: int,
) -> list[PlannedQuery]:
    if not 1 <= deep_queries <= 8:
        raise ValueError("deep_queries must be between 1 and 8")
    short_title = _shorten(title, 120)
    short_thesis = _shorten(thesis, 160)
    pillar = pillar_name or ""
    output: list[PlannedQuery] = []
    for facet, template in DEEP_FACETS[:deep_queries]:
        text = template.format(
            title=short_title, thesis=short_thesis, pillar=pillar, month_year=today.strftime("%B %Y")
        )
        output.append(PlannedQuery(text=render_template(text, today=today), theme_key=None, facet=facet))
    return output
