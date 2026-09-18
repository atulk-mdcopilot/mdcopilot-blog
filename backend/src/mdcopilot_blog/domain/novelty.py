"""Vector and deterministic novelty rules, independent of persistence."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from mdcopilot_blog.domain.config import NoveltyConfig
from mdcopilot_blog.domain.contracts import NoveltyDecision, NoveltyNeighbour
from mdcopilot_blog.domain.enums import CandidateStatus, HeadlinePattern

NON_LIVE_ARTICLE_STATUSES = frozenset({"REJECTED", "SUPERSEDED"})
APPROVED_OR_LATER_STATUSES = frozenset(
    {"APPROVED", "SCHEDULED", "EXPORTED", "PUBLISHING", "PUBLISHED", "PUBLISH_FAILED"}
)
NEIGHBOUR_LIMIT = 5


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimensions differ")
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return clamp_unit(sum(x * y for x, y in zip(a, b, strict=True)) / denominator) if denominator else 0.0


def candidate_embedding_text(*, title: str, hook: str, thesis: str, angle: str) -> str:
    return "\n".join(v.strip() for v in (title, hook, thesis, angle) if v.strip())


def external_post_embedding_text(*, title: str, excerpt: str) -> str:
    return "\n".join(v.strip() for v in (title, excerpt) if v.strip())


@dataclass(frozen=True)
class NoveltySignals:
    topic_best: NoveltyNeighbour | None
    argument_best: NoveltyNeighbour | None
    news_reuse_url: str | None
    headline_best: tuple[float, str] | None
    pattern: HeadlinePattern
    pattern_uses: int
    reused_examples: tuple[str, ...]


@dataclass(frozen=True)
class NoveltyAssessment:
    decision: NoveltyDecision
    reasons: tuple[str, ...]
    max_similarity: float


def assess_novelty(signals: NoveltySignals, config: NoveltyConfig) -> NoveltyAssessment:
    rejected, reasons = False, []
    similarities = [0.0]
    for label, neighbour, threshold in (
        ("topic", signals.topic_best, config.topic_threshold),
        ("argument", signals.argument_best, config.argument_threshold),
    ):
        if neighbour is None:
            continue
        similarities.append(neighbour.similarity)
        if neighbour.similarity >= threshold:
            rejected = True
            reasons.append(
                f"{label} similarity {neighbour.similarity:.2f} >= {threshold:.2f} ({neighbour.kind} {neighbour.ref_id})"
            )
        elif neighbour.similarity >= threshold - config.warn_margin:
            reasons.append(
                f"{label} similarity {neighbour.similarity:.2f} within {config.warn_margin:.2f} of {threshold:.2f} ({neighbour.kind} {neighbour.ref_id})"
            )
    if signals.news_reuse_url:
        rejected = True
        reasons.append(f"primary news source reused: {signals.news_reuse_url}")
    if signals.headline_best and signals.headline_best[0] >= config.headline_similarity_warn:
        reasons.append(f"headline resembles {signals.headline_best[1]}")
    if signals.pattern_uses >= config.headline_pattern_warn_count:
        reasons.append(f"headline pattern {signals.pattern.value} used {signals.pattern_uses} times")
    if signals.reused_examples:
        reasons.append("examples reused: " + ", ".join(signals.reused_examples))
    return NoveltyAssessment(
        NoveltyDecision.REJECT_TOPIC if rejected else NoveltyDecision.WARN if reasons else NoveltyDecision.PASS,
        tuple(reasons),
        max(similarities),
    )


def novelty_justification(assessment: NoveltyAssessment) -> str:
    return assessment.decision.value + ": " + ("; ".join(assessment.reasons) or "no similar history")


def novelty_score(max_similarity: float) -> float:
    return 1 - clamp_unit(max_similarity)


def candidate_status(decision: NoveltyDecision, *, is_manual: bool) -> CandidateStatus:
    return (
        CandidateStatus.WARNED
        if is_manual and decision != NoveltyDecision.PASS
        else {
            NoveltyDecision.PASS: CandidateStatus.PASSED,
            NoveltyDecision.WARN: CandidateStatus.WARNED,
            NoveltyDecision.REJECT_TOPIC: CandidateStatus.REJECTED,
        }[decision]
    )


def round_shortfall(*, statuses: Sequence[str], round_no: int, max_regeneration_rounds: int) -> bool:
    return round_no >= 1 + max_regeneration_rounds and sum(s in {"PASSED", "WARNED", "SELECTED"} for s in statuses) < 3
