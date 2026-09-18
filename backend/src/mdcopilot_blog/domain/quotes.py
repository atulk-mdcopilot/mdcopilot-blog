"""Find quotations and verify attributed speech against cited source snapshots."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from mdcopilot_blog.domain.contracts import ArticleSection
from mdcopilot_blog.domain.numeric_scan import locate_sentence, split_sentences
from mdcopilot_blog.domain.text import count_words, normalize_for_match, strip_citation_markers

ATTRIBUTION_CUES = (
    "said",
    "says",
    "say",
    "stated",
    "states",
    "told",
    "tells",
    "wrote",
    "writes",
    "noted",
    "notes",
    "explained",
    "explains",
    "added",
    "adds",
    "argued",
    "argues",
    "commented",
    "comments",
    "remarked",
    "announced",
    "announces",
    "declared",
    "warned",
    "warns",
    "claimed",
    "claims",
    "recalled",
    "recalls",
    "according to",
    "in the words of",
    "put it",
)
_ATTRIBUTION = re.compile(r"\b(?:" + "|".join(re.escape(cue) for cue in ATTRIBUTION_CUES) + r")\b", re.IGNORECASE)
_QUOTE = re.compile(r'“([^”\n]+)”|"([^"\n]+)"|(?m:^\s*>\s?([^\n]+))')


@dataclass(frozen=True)
class QuoteSpan:
    section_key: str
    sentence_index: int
    text: str
    attributed: bool
    word_count: int

    @property
    def requires_verification(self) -> bool:
        return self.attributed or self.word_count >= 6


def find_quotes(sections: Sequence[ArticleSection]) -> list[QuoteSpan]:
    result = []
    for section in sections:
        sentences = split_sentences(section.body_markdown)
        for match in _QUOTE.finditer(section.body_markdown):
            quote = strip_citation_markers(next(group for group in match.groups() if group is not None)).strip()
            if not quote:
                continue
            index = locate_sentence(section.body_markdown, quote)
            if index is None:
                parts = split_sentences(quote)
                index = locate_sentence(section.body_markdown, parts[0]) if parts else None
            index = index if index is not None else 0
            sentence = sentences[index] if index < len(sentences) else ""
            attributed = bool(_ATTRIBUTION.search(sentence.replace(quote, "")))
            result.append(QuoteSpan(section.key.value, index, quote, attributed, count_words(quote)))
    return result


def unverified_quotes(quotes: Sequence[QuoteSpan], snapshots: Sequence[str | None]) -> list[QuoteSpan]:
    texts = [normalize_for_match(value) for value in snapshots if value]
    return [
        quote
        for quote in quotes
        if quote.requires_verification and not any(normalize_for_match(quote.text) in text for text in texts)
    ]
