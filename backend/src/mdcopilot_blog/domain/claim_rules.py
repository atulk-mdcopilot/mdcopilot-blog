"""Claim rules: enforced in code, not prompts."""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from mdcopilot_blog.domain.contracts import ClaimType, SourceType
from mdcopilot_blog.domain.enums import AccessMode
from mdcopilot_blog.domain.text import normalize_for_match

FindingCategory = Literal[
    "regulatory",
    "clinical_research",
    "workforce",
    "product_announcement",
    "policy",
    "market",
    "technology",
    "operations",
    "other",
]

ANNOUNCEMENT_CATEGORIES: frozenset[str] = frozenset({"product_announcement", "regulatory"})
MAX_FINDINGS = 25


@dataclass(frozen=True)
class EvidenceSource:
    source_id: uuid.UUID
    tier: int
    access_mode: AccessMode
    published_at: datetime | None
    source_type: SourceType
    is_preprint: bool


@dataclass(frozen=True)
class DraftFinding:
    claim: str
    evidence: str
    confidence: float
    category: FindingCategory
    claim_type: ClaimType
    importance: Literal["high", "normal"]
    self_reported: bool
    source_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class RuledFinding:
    claim: str
    evidence: str
    confidence: float
    category: FindingCategory
    claim_type: ClaimType
    importance: Literal["high", "normal"]
    is_preprint: bool
    downgraded_from: str | None
    rule: (
        Literal["marketing_self_report", "preprint_only", "undated", "high_importance_evidence", "metadata_only"] | None
    )
    source_ids: tuple[uuid.UUID, ...]


def apply_claim_rules(
    findings: Sequence[DraftFinding], sources: Mapping[uuid.UUID, EvidenceSource]
) -> list[RuledFinding]:
    kept: list[RuledFinding] = []
    seen_claims: set[str] = set()
    for finding in findings:
        cited = [sources[source_id] for source_id in finding.source_ids]
        if len(kept) >= MAX_FINDINGS:
            break
        normalized = normalize_for_match(finding.claim)
        if normalized in seen_claims:
            continue
        seen_claims.add(normalized)
        is_preprint = any(source.is_preprint for source in cited)
        claim_type = finding.claim_type
        downgraded_from: str | None = None
        rule: (
            Literal["marketing_self_report", "preprint_only", "undated", "high_importance_evidence", "metadata_only"]
            | None
        ) = None
        if finding.claim_type == ClaimType.FACT:
            if (
                finding.self_reported
                and cited
                and all(source.source_type == SourceType.COMPANY_ANNOUNCEMENT for source in cited)
            ):
                claim_type, downgraded_from, rule = ClaimType.MARKETING_CLAIM, "FACT", "marketing_self_report"
            elif cited and all(source.is_preprint for source in cited):
                claim_type, downgraded_from, rule = ClaimType.ANALYSIS, "FACT", "preprint_only"
            elif cited and all(source.published_at is None for source in cited):
                claim_type, downgraded_from, rule = ClaimType.ANALYSIS, "FACT", "undated"
            elif finding.importance == "high" and not any(
                source.tier <= 2 and source.access_mode in (AccessMode.FULL_TEXT, AccessMode.ABSTRACT_ONLY)
                for source in cited
            ):
                claim_type, downgraded_from, rule = ClaimType.ANALYSIS, "FACT", "high_importance_evidence"
            elif (
                cited
                and all(source.access_mode == AccessMode.METADATA_ONLY for source in cited)
                and finding.category not in ANNOUNCEMENT_CATEGORIES
            ):
                claim_type, downgraded_from, rule = ClaimType.ANALYSIS, "FACT", "metadata_only"
        kept.append(
            RuledFinding(
                claim=finding.claim,
                evidence=finding.evidence,
                confidence=finding.confidence,
                category=finding.category,
                claim_type=claim_type,
                importance=finding.importance,
                is_preprint=is_preprint,
                downgraded_from=downgraded_from,
                rule=rule,
                source_ids=finding.source_ids,
            )
        )
    return kept
