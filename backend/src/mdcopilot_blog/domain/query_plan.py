"""Query planner for deep research."""

import re
from dataclasses import dataclass
from datetime import date

MONTH_YEAR_TOKEN = "{month_year}"
MAX_QUERY_CHARS = 300


@dataclass(frozen=True)
class PlannedQuery:
    text: str
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
        output.append(PlannedQuery(text=render_template(text, today=today), facet=facet))
    return output
