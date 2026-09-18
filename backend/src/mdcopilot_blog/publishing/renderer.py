"""Deterministic Quill-compatible rendering; model HTML is never trusted."""

import hashlib
import html
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

import nh3
from markdown_it import MarkdownIt

from mdcopilot_blog.domain.contracts import BlogSource, SEOMetadata
from mdcopilot_blog.domain.text import CITATION_MARKER_RE, extract_markers, strip_citation_markers
from mdcopilot_blog.publishing.base import Issue, PublishPayload

ALLOWED_TAGS = frozenset({"h2", "h3", "p", "strong", "em", "s", "a", "ul", "ol", "li", "blockquote", "img"})
ALLOWED_ATTRIBUTES = {"a": frozenset({"href"}), "img": frozenset({"src", "alt"})}
TITLE_MAX_LENGTH = SLUG_MAX_LENGTH = 200
EXCERPT_MAX_LENGTH = 500
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VALID_MARKER_RE = re.compile(r"^S[1-9][0-9]*$")
MARKDOWN = MarkdownIt("js-default", {"html": False}).disable("table")


def http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value.strip())
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and not any(ord(c) < 32 or c.isspace() for c in value.strip())
        )
    except ValueError:
        return False


def markdown_to_html(markdown: str) -> str:
    return str(MARKDOWN.render(markdown))


def sanitize_html(value: str) -> str:
    return nh3.clean(
        value,
        tags=set(ALLOWED_TAGS),
        attributes={k: set(v) for k, v in ALLOWED_ATTRIBUTES.items()},
        url_schemes={"http", "https"},
        link_rel="noopener noreferrer",
        attribute_filter=lambda tag, attr, value: None if attr in {"href", "src"} and not http_url(value) else value,
    )


def _references(references: Sequence[BlogSource]) -> list[BlogSource]:
    return sorted((r for r in references if VALID_MARKER_RE.fullmatch(r.marker)), key=lambda r: int(r.marker[1:]))


def link_citations(markdown: str, references: Sequence[BlogSource]) -> str:
    links = {r.marker: (i, r.url) for i, r in enumerate(_references(references), 1)}

    def replace(match: re.Match[str]) -> str:
        marker = match.group(0).strip("[]")
        if marker not in links:
            return match.group(0)
        i, url = links[marker]
        label = f"\\[{i}\\]"
        return f"[{label}](<{quote(url.strip(), safe=":/?#[]@!$&'()*+,;=%")}>)" if http_url(url) else label

    return CITATION_MARKER_RE.sub(replace, markdown)


def render_article_html(
    *, content_markdown: str, pull_quote: str, references: Sequence[BlogSource], disclosure: str
) -> str:
    parts = [markdown_to_html(link_citations(content_markdown, references))]
    if q := strip_citation_markers(pull_quote).strip():
        parts.append(f"<blockquote>{html.escape(q, quote=False)}</blockquote>\n")
    refs = _references(references)
    if refs:
        parts.append("<h2>References</h2>\n<ol>\n")
        for ref in refs:
            url = quote(ref.url.strip(), safe=":/?#[]@!$&'()*+,;=%")
            label = html.escape(ref.title.strip() or url)
            link = f'<a href="{html.escape(url)}">{label}</a>' if http_url(ref.url) else label
            publisher = ", " + html.escape(ref.publisher.strip()) if ref.publisher.strip() else ""
            d = ref.published_at.astimezone(UTC) if ref.published_at else None
            date = f", {d.day} {d:%B} {d.year}" if d else ""
            parts.append(f"<li>{link}{publisher}{date}</li>\n")
        parts.append("</ol>\n")
    if disclosure.strip():
        parts.append(f"<p><em>{html.escape(disclosure.strip(), quote=False)}</em></p>")
    return sanitize_html("".join(parts))


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.current: list[str] = []
        self.lists: list[tuple[str, int]] = []
        self.list_lines: list[str] = []
        self.link: tuple[str, int] | None = None

    def flush(self) -> None:
        value = re.sub(r"\s+", " ", "".join(self.current)).strip()
        if value:
            (self.list_lines if self.lists else self.blocks).append(value)
        self.current = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"li", "ul", "ol"} or (tag in {"p", "h2", "h3", "blockquote"} and not self.lists):
            self.flush()
        if tag in {"ol", "ul"}:
            self.lists.append((tag, 0))
        if tag == "li":
            kind, n = self.lists[-1] if self.lists else ("ul", 0)
            if self.lists:
                self.lists[-1] = (kind, n + 1)
            self.current.append(f"{n + 1}. " if kind == "ol" else "- ")
        if tag == "a":
            self.link = (values.get("href") or "", len(self.current))
        if tag == "img":
            alt = values.get("alt") or ""
            self.current.append(f"[image: {alt}]" if alt else "[image]")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.link:
            url, start = self.link
            if url and url != "".join(self.current[start:]):
                self.current.append(f" ({url})")
            self.link = None
        if tag in {"li", "ul", "ol"} or (tag in {"p", "h2", "h3", "blockquote"} and not self.lists):
            self.flush()
        elif tag in {"p", "h2", "h3", "blockquote"}:
            self.current.append(" ")
        if tag in {"ol", "ul"} and self.lists:
            self.lists.pop()
            if not self.lists and self.list_lines:
                self.blocks.append("\n".join(self.list_lines))
                self.list_lines = []

    def handle_data(self, data: str) -> None:
        self.current.append(data)


def html_to_text(value: str) -> str:
    parser = _PlainText()
    parser.feed(value)
    parser.flush()
    return "\n\n".join(parser.blocks) + "\n" if parser.blocks else ""


def compute_payload_hash(*, html: str, title: str, slug: str, excerpt: str) -> str:
    return hashlib.sha256(f"{html}\x1f{title}\x1f{slug}\x1f{excerpt}".encode()).hexdigest()


def _fields(title: str, slug: str | None, excerpt: str, html: str) -> list[Issue]:
    issues = []
    for name, value, limit in [("title", title, 200), ("slug", slug or "", 200), ("excerpt", excerpt, 500)]:
        if not value.strip():
            issues.append(Issue(field=name, message=f"{name} is required"))
        elif len(value) > limit:
            issues.append(Issue(field=name, message=f"{name} must be at most {limit} characters (got {len(value)})"))
        if name == "slug" and value.strip() and not SLUG_RE.fullmatch(value):
            issues.append(
                Issue(field=name, message="slug must contain only lowercase letters, digits and single hyphens")
            )
    if not html.strip():
        issues.append(Issue(field="content", message="content is empty"))
    return issues


def validate_payload(payload: PublishPayload) -> list[Issue]:
    return _fields(payload.title, payload.slug, payload.excerpt, payload.html)


@dataclass(frozen=True)
class PublishableCheck:
    title: str
    slug: str | None
    excerpt: str
    html: str
    content_markdown: str
    seo: SEOMetadata | None
    references: Sequence[BlogSource]
    disclosure: str


def validate_publishable(check: PublishableCheck) -> list[Issue]:
    issues = _fields(check.title, check.slug, check.excerpt, check.html)
    known = {r.marker for r in _references(check.references)}
    unknown = [m for m in extract_markers(check.content_markdown) if m not in known]
    if unknown:
        issues.append(Issue(field="content", message="unknown citation markers: " + ", ".join(unknown)))
    if check.seo is None:
        issues.append(Issue(field="seo", message="SEO metadata is missing for this version"))
    if not check.references:
        issues.append(Issue(field="references", message="at least one cited source is required"))
    for ref in check.references:
        if not VALID_MARKER_RE.fullmatch(ref.marker):
            issues.append(Issue(field="references", message=f"reference marker '{ref.marker}' is invalid"))
        elif not http_url(ref.url):
            issues.append(Issue(field="references", message=f"reference {ref.marker} has no http(s) URL"))
    if not check.disclosure.strip():
        issues.append(Issue(field="disclosure", message="AI-assistance disclosure is required"))
    return issues
