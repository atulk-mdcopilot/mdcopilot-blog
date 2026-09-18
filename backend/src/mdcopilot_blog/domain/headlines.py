"""Ordered headline classification."""

import re

from mdcopilot_blog.domain.enums import HeadlinePattern


def classify_headline(title: str) -> HeadlinePattern:
    title = title.strip().lower()
    if title.startswith("what if "):
        return HeadlinePattern.WHAT_IF
    if title.startswith("how to "):
        return HeadlinePattern.HOW_TO
    if title.startswith("why "):
        return HeadlinePattern.WHY
    if title.endswith("?"):
        return HeadlinePattern.QUESTION
    if re.match(r"^\d+\b", title):
        return HeadlinePattern.NUMBER_LIST
    if re.search(r"\b(vs\.?|versus)\b", title):
        return HeadlinePattern.VERSUS
    if ":" in title:
        return HeadlinePattern.COLON_SPLIT
    if re.match(r"^(stop|start|build|consider|make|use|avoid|rethink|prepare|protect)\b", title):
        return HeadlinePattern.IMPERATIVE
    return HeadlinePattern.STATEMENT
