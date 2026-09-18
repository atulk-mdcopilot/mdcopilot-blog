"""Validate and assemble immutable article content without persistence concerns."""

import difflib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from mdcopilot_blog.domain.contracts import SECTION_ORDER, ArticleSection, ComponentDraft, SEOMetadata, TitleOptions
from mdcopilot_blog.domain.enums import ArticleComponent
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


def normalize_section(section: ArticleSection) -> ArticleSection:
    return section.model_copy(
        update={
            "heading": section.heading.strip() if section.heading else None,
            "body_markdown": section.body_markdown.strip(),
        }
    )


def normalize_title_options(options: TitleOptions) -> TitleOptions:
    return TitleOptions(**{key: value.strip() for key, value in options.model_dump().items()})


def sections_from_markdown(md: str) -> list[ArticleSection]:
    return [
        ArticleSection(key=key, heading=heading, body_markdown=body)
        for key, (heading, body) in zip(SECTION_ORDER, split_markdown(md), strict=True)
    ]


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


def edit_content(
    base: VersionContent,
    *,
    content_markdown: str | None = None,
    title_options: TitleOptions | None = None,
    pull_quote: str | None = None,
    cta: str | None = None,
    excerpt: str | None = None,
) -> VersionContent:
    return build_version_content(
        title_options=normalize_title_options(title_options) if title_options else base.title_options,
        sections=sections_from_markdown(content_markdown) if content_markdown is not None else base.sections,
        pull_quote=pull_quote.strip() if pull_quote is not None else base.pull_quote,
        cta=cta.strip() if cta is not None else base.cta,
        excerpt=excerpt.strip() if excerpt is not None else base.excerpt,
    )


def apply_component(base: VersionContent, draft: ComponentDraft) -> VersionContent:
    sections = list(base.sections)
    if draft.section is not None:
        target = SECTION_ORDER[0] if draft.component == ArticleComponent.INTRODUCTION else draft.section_key
        if draft.section.key != target:
            raise ArticleStructureError(f"expected section {target}, got {draft.section.key}")
        sections[SECTION_ORDER.index(draft.section.key)] = normalize_section(draft.section)
    return build_version_content(
        title_options=normalize_title_options(draft.title_options) if draft.title_options else base.title_options,
        sections=sections,
        pull_quote=draft.pull_quote.strip() if draft.pull_quote is not None else base.pull_quote,
        cta=draft.cta.strip() if draft.cta is not None else base.cta,
        excerpt=base.excerpt,
    )


def resolve_packet_markers(markers: Sequence[str], source_ids: Sequence[uuid.UUID]) -> dict[str, uuid.UUID]:
    numbered = {f"S{i}": value for i, value in enumerate(source_ids, 1)}
    unknown = [marker for marker in markers if marker not in numbered]
    if unknown:
        raise UnknownCitationMarker(unknown)
    return {marker: numbered[marker] for marker in markers}


def merge_seo(base: SEOMetadata, edits: Mapping[str, object]) -> SEOMetadata:
    return SEOMetadata.model_validate({**base.model_dump(), **edits})


def unified_markdown_diff(before_md: str, after_md: str, *, before_no: int, after_no: int) -> str:
    return "\n".join(
        difflib.unified_diff(
            before_md.splitlines(),
            after_md.splitlines(),
            fromfile=f"v{before_no}",
            tofile=f"v{after_no}",
            n=3,
            lineterm="",
        )
    )


def diff_fields(content: VersionContent, seo: SEOMetadata | None) -> dict[str, str | None]:
    fields: dict[str, str | None] = {
        f"titleOptions.{key}": value for key, value in content.title_options.model_dump().items()
    }
    fields.update(pullQuote=content.pull_quote, cta=content.cta, excerpt=content.excerpt)
    if seo:
        for key, value in seo.model_dump(mode="json").items():
            fields[f"seo.{key}"] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return fields


def field_changes(
    before: Mapping[str, str | None], after: Mapping[str, str | None]
) -> list[tuple[str, str | None, str | None]]:
    return [
        (key, before.get(key), after.get(key))
        for key in dict.fromkeys([*before, *after])
        if before.get(key) != after.get(key)
    ]
