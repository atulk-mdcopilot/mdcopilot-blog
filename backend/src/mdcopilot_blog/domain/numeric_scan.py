"""Sentence locations and numeric-claim detection, excluding dates and identifiers."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from mdcopilot_blog.domain.contracts import ArticleSection
from mdcopilot_blog.domain.text import normalize_for_match, strip_citation_markers

PULL_QUOTE_KEY = "pull_quote"
_ABBREVIATIONS = {"e.g", "i.e", "U.S", "U.K", "Dr", "Mr", "Ms", "Mrs", "Prof", "vs", "Inc", "Ltd", "Jr", "Sr"}
_END = re.compile(r"""[.!?]["”’')\]]*(?:\s*\[S[1-9][0-9]*\])*(?=\s|$)""")
_TIME = re.compile(
    r"\b\d{1,2}:\d{2}(?:\s?[ap]\.?m\.?)?|\b\d{1,2}\s?[ap]\.?m\.?(?![a-z])|\b24\s?[/x×]\s?7(?:\s?/\s?365)?\b",
    re.IGNORECASE,
)
_LABEL = re.compile(
    r"\b(?:step|phase|stage|tier|level|part|chapter|section|version|type|class|grade|round|category|figure|table)\s?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SentenceRef:
    section_key: str
    index: int
    text: str


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"(?m)^ {0,3}(?:[-*+] |\d+\. )", "\n\n", text.replace("\r\n", "\n"))
    text = re.sub(r"(?m)^ {0,3}> ?", "", text)
    sentences = []
    for block in re.split(r"\n[ \t]*\n", text):
        block = re.sub(r"\s+", " ", block).strip()
        start = 0
        for match in _END.finditer(block):
            if (
                block[match.start()] == "."
                and block[: match.start()].split()[-1:]
                and block[: match.start()].split()[-1] in _ABBREVIATIONS
            ):
                continue
            value = block[start : match.end()].strip()
            if value:
                sentences.append(value)
            start = match.end()
        if block[start:].strip():
            sentences.append(block[start:].strip())
    return sentences


def locate_sentence(text: str, span: str) -> int | None:
    needle = normalize_for_match(strip_citation_markers(span))
    return next(
        (
            i
            for i, s in enumerate(split_sentences(text))
            if needle and needle in normalize_for_match(strip_citation_markers(s))
        ),
        None,
    )


def article_sentences(sections: Sequence[ArticleSection], pull_quote: str) -> list[SentenceRef]:
    return [
        SentenceRef(key, i, sentence)
        for key, text in [*((s.key.value, s.body_markdown) for s in sections), (PULL_QUOTE_KEY, pull_quote)]
        for i, sentence in enumerate(split_sentences(text))
    ]


def numeric_tokens(sentence: str) -> list[str]:
    text = re.sub(r"https?://\S+", "", re.sub(r"\]\([^)]*\)", "]", strip_citation_markers(sentence)))
    times = [(m.start(), m.end()) for m in _TIME.finditer(text)]
    result = []
    for match in re.finditer(r"\d+(?:[.,]\d+)*", text):
        value, before, after = match.group(), text[: match.start()], text[match.end() :]
        if (
            len(value) == 4
            and value.isdigit()
            and 1900 <= int(value) <= 2100
            and not after.startswith("%")
            and not before.endswith("$")
            and not re.match(r"\s*percent", after, re.IGNORECASE)
        ):
            continue
        if (
            re.match(r"(?:st|nd|rd|th)(?![a-z])", after, re.IGNORECASE)
            or any(a <= match.start() < b for a, b in times)
            or _LABEL.search(before)
        ):
            continue
        if re.search(r"[A-Za-z][-_]?$", before) or re.match(r"[A-Z]{1,3}(?![A-Za-z])", after):
            continue
        result.append(value)
    return result


def numeric_sentences(sections: Sequence[ArticleSection], pull_quote: str) -> list[SentenceRef]:
    return [sentence for sentence in article_sentences(sections, pull_quote) if numeric_tokens(sentence.text)]
