"""Tiers, domain rules and deterministic relevance."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from mdcopilot_blog.domain import urls
from mdcopilot_blog.domain.contracts import SourceType

HeaderProfile = Literal["default", "browser_like"]
FetchPolicy = Literal["fetch", "metadata_only", "never"]

TIER_WEIGHT: dict[int, float] = {1: 1.0, 2: 0.7, 3: 0.3}
STOPWORDS: frozenset[str] = frozenset(
    {
        "of",
        "in",
        "on",
        "to",
        "by",
        "an",
        "as",
        "at",
        "is",
        "it",
        "or",
        "be",
        "we",
        "us",
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "are",
        "was",
        "were",
        "has",
        "have",
        "its",
        "into",
        "about",
        "over",
        "after",
        "new",
        "how",
        "why",
        "what",
    }
)


@dataclass(frozen=True)
class DomainRule:
    domain: str
    tier: int
    source_type: SourceType
    publisher: str | None
    header_profile: HeaderProfile
    fetch_policy: FetchPolicy
    verification_allowlisted: bool


@dataclass(frozen=True)
class Classification:
    domain: str
    tier: int
    source_type: SourceType
    header_profile: HeaderProfile
    fetch_policy: FetchPolicy
    is_preprint: bool
    rule_publisher: str | None


def match_domain_rule(host: str, rules: Mapping[str, DomainRule]) -> DomainRule | None:
    for suffix in urls.domain_suffixes(host):
        rule = rules.get(suffix)
        if rule is not None:
            return rule
    return None


def classify_source(url: str, *, rules: Mapping[str, DomainRule]) -> Classification:
    domain = urls.registrable_domain(urls.host_of(url))
    rule = match_domain_rule(urls.host_of(url), rules)
    if rule is not None:
        tier = rule.tier
        source_type = rule.source_type
        header_profile = rule.header_profile
        fetch_policy = rule.fetch_policy
        rule_publisher = rule.publisher
    else:
        tier = 3
        source_type = SourceType.OTHER
        header_profile = "default"
        fetch_policy = "fetch"
        rule_publisher = None
    is_preprint = rule is not None and rule.source_type == SourceType.PREPRINT
    return Classification(
        domain=domain,
        tier=tier,
        source_type=source_type,
        header_profile=header_profile,
        fetch_policy=fetch_policy,
        is_preprint=is_preprint,
        rule_publisher=rule_publisher,
    )


def resolve_publisher(
    *,
    rule_publisher: str | None,
    journal: str | None,
    sitename: str | None,
    domain: str,
) -> str:
    for candidate in (journal, rule_publisher, sitename, domain):
        if candidate is not None and candidate.strip():
            return candidate.strip()[:200]
    return domain[:200]


def tokenize(text: str) -> frozenset[str]:
    return frozenset(
        token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 2 and token not in STOPWORDS
    )


def keyword_set(phrases: Iterable[str]) -> frozenset[str]:
    tokens: set[str] = set()
    for phrase in phrases:
        tokens.update(tokenize(phrase))
    return frozenset(tokens)


def relevance_score(
    *,
    text: str,
    keywords: frozenset[str],
    published_at: datetime | None,
    now: datetime,
    window_days: int,
    tier: int,
) -> float:
    if tier not in TIER_WEIGHT:
        raise ValueError(f"tier must be one of {sorted(TIER_WEIGHT)}")
    if not keywords:
        overlap = 0.0
    else:
        overlap = min(1.0, len(keywords & tokenize(text)) / min(len(keywords), 10))
    if published_at is None:
        recency = 0.0
    else:
        recency = max(0.0, 1.0 - max(0.0, (now - published_at).total_seconds()) / (window_days * 86400))
    return round(0.4 * overlap + 0.35 * recency + 0.25 * TIER_WEIGHT[tier], 4)
