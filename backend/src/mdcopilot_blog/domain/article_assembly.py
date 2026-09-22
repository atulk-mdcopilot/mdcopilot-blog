"""Validate and assemble immutable article content without persistence concerns."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from mdcopilot_blog.domain.contracts import SECTION_ORDER, ArticleSection, TitleOptions
from mdcopilot_blog.domain.errors import ArticleStructureError, UnknownCitationMarker
from mdcopilot_blog.domain.text import assemble_markdown, body_word_count, extract_markers, split_markdown


@dataclass(frozen=True)
class VersionContent:
    title_options: TitleOptions
    sections: tuple[ArticleSection, ...]
    pull_quote: str
    cta: str
    excerpt: str
    content_markdown: str
    word_count: int
    citation_markers: tuple[str, ...]


def build_version_content(
    *, title_options: TitleOptions, sections: Sequence[ArticleSection], pull_quote: str, cta: str, excerpt: str
) -> VersionContent:
    if tuple(s.key for s in sections) != SECTION_ORDER:
        raise ArticleStructureError("sections must be " + ", ".join(SECTION_ORDER) + " in this order")
    for section in sections:
        if not section.body_markdown.strip():
            raise ArticleStructureError(f"section {section.key} has an empty body")
        if section.key != SECTION_ORDER[0] and not (section.heading or "").strip():
            raise ArticleStructureError(f"section {section.key} needs a heading")
    fields = {
        **{f"titleOptions.{k}": v for k, v in title_options.model_dump().items()},
        "pullQuote": pull_quote,
        "cta": cta,
        "excerpt": excerpt,
    }
    for key, value in fields.items():
        if not value.strip():
            raise ArticleStructureError(f"{key} must not be empty")
        if key.startswith("titleOptions") and len(value) > 200:
            raise ArticleStructureError(f"{key} must be at most 200 characters")
        if extract_markers(value):
            raise ArticleStructureError(f"citation markers are allowed only in section bodies: {key}")
    if len(excerpt) > 500:
        raise ArticleStructureError("excerpt must be at most 500 characters")
    markdown = assemble_markdown(sections)
    if split_markdown(markdown) != [
        (s.heading.strip() if s.heading else None, s.body_markdown.strip()) for s in sections
    ]:
        raise ArticleStructureError("sections do not survive Markdown assembly")
    return VersionContent(
        title_options,
        tuple(sections),
        pull_quote,
        cta,
        excerpt,
        markdown,
        body_word_count(sections),
        tuple(extract_markers(markdown)),
    )


def resolve_packet_markers(markers: Sequence[str], source_ids: Sequence[uuid.UUID]) -> dict[str, uuid.UUID]:
    numbered = {f"S{i}": value for i, value in enumerate(source_ids, 1)}
    unknown = [marker for marker in markers if marker not in numbered]
    if unknown:
        raise UnknownCitationMarker(unknown)
    return {marker: numbered[marker] for marker in markers}
