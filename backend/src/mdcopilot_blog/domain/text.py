"""Text primitives shared by every article-producing track.

Only the standard library and ``mdcopilot_blog.domain`` modules are imported here.
``contracts.py`` imports ``ATX_HEADING_RE`` from this module, so this module must not import
``contracts`` at runtime.
"""

import re
import unicodedata
from collections.abc import Sequence
from typing import TYPE_CHECKING

from mdcopilot_blog.domain.errors import ArticleStructureError

if TYPE_CHECKING:
    from mdcopilot_blog.domain.contracts import ArticleSection

CITATION_MARKER_RE = re.compile(r"\[(S[1-9][0-9]*)\]")
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
ATX_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")


def strip_citation_markers(text: str) -> str:
    """Remove every ``[S<n>]`` marker and the single space before it."""
    return re.sub(r" ?\[S[1-9][0-9]*\]", "", text)


def count_words(text: str) -> int:
    """Word count with citation markers removed (markers contain digits; numbers are written as words)."""
    return len(WORD_RE.findall(strip_citation_markers(text)))


def extract_markers(text: str) -> list[str]:
    """Unique citation markers in first-appearance order."""
    seen: set[str] = set()
    markers: list[str] = []
    for marker in CITATION_MARKER_RE.findall(text):
        if marker not in seen:
            seen.add(marker)
            markers.append(marker)
    return markers


def normalize_for_match(text: str) -> str:
    """NFKC, curly quotes/apostrophes to straight, lowercase, whitespace collapsed, stripped."""
    text = unicodedata.normalize("NFKC", text)
    for opening, closing in (("“", '"'), ("”", '"'), ("„", '"'), ("‟", '"')):
        text = text.replace(opening, closing)
    for opening, closing in (("‘", "'"), ("’", "'"), ("‚", "'"), ("‛", "'")):
        text = text.replace(opening, closing)
    return re.sub(r"\s+", " ", text.lower()).strip()


def body_word_count(sections: Sequence["ArticleSection"]) -> int:
    """Sum of body word counts; headings, pull quote and CTA are excluded."""
    return sum(count_words(section.body_markdown) for section in sections)


def assemble_markdown(sections: Sequence["ArticleSection"]) -> str:
    """Render the seven sections to the frozen article Markdown format."""
    from mdcopilot_blog.domain.contracts import SECTION_ORDER

    if [section.key for section in sections] != list(SECTION_ORDER):
        raise ArticleStructureError("sections must be the seven SECTION_ORDER keys in order")
    parts = [sections[0].body_markdown.strip()]
    for section in sections[1:]:
        heading = section.heading
        if heading is None:
            raise ArticleStructureError("sections must be the seven SECTION_ORDER keys in order")
        parts.append(f"## {heading.strip()}")
        parts.append(section.body_markdown.strip())
    return "\n\n".join(parts) + "\n"


def split_markdown(md: str) -> list[tuple[str | None, str]]:
    """Parse the frozen article Markdown format back into ``[(heading, body), …]`` pairs."""
    md = md.replace("\r\n", "\n")
    lines = md.split("\n")
    headings: list[tuple[int, str]] = []  # (line index, heading text)
    for index, line in enumerate(lines):
        match = ATX_HEADING_RE.match(line)
        if match is None:
            continue
        level = len(match.group(1))
        if level != 2:
            raise ArticleStructureError(f"heading level {level} is not allowed: {line.strip()}")
        headings.append((index, str(match.group(2) or "").strip()))

    if len(headings) != 6:
        raise ArticleStructureError(f"expected 6 H2 sections, found {len(headings)}")
    for position, (_, text) in enumerate(headings, start=1):
        if not text:
            raise ArticleStructureError(f"section {position} heading is empty")

    intro = "\n".join(lines[: headings[0][0]]).strip()
    if not intro:
        raise ArticleStructureError("introduction body is empty")

    pairs: list[tuple[str | None, str]] = [(None, intro)]
    for position, (index, text) in enumerate(headings, start=1):
        end = headings[position][0] if position < len(headings) else len(lines)
        body = "\n".join(lines[index + 1 : end]).strip()
        if not body:
            raise ArticleStructureError(f"section {position} body is empty")
        pairs.append((text, body))
    return pairs
