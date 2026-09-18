"""Weighted, explainable topic scoring."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from mdcopilot_blog.domain.config import ScoreWeights
from mdcopilot_blog.domain.contracts import ScoreItem


@dataclass(frozen=True)
class RubricItem:
    score: int
    justification: str


@dataclass(frozen=True)
class ScoreInputs:
    newest_published_at: datetime | None
    dated_sources: int
    total_sources: int
    tier12_sources: int
    primary_source_present: bool
    novelty_score: float
    novelty_justification: str
    business_relevance: RubricItem | None
    audience_relevance: RubricItem | None
    editorial_potential: RubricItem | None


@dataclass(frozen=True)
class ScoreCard:
    timeliness: float
    novelty: float
    evidence: float
    business_relevance: float
    audience_relevance: float
    editorial_potential: float
    total: float
    breakdown: dict[str, ScoreItem]


def timeliness_score(newest_published_at: datetime | None, *, now: datetime) -> float:
    if newest_published_at is None:
        return 0.1
    age = now - newest_published_at
    return (
        1.0
        if age <= timedelta(hours=48)
        else 0.7
        if age <= timedelta(days=7)
        else 0.3
        if age <= timedelta(days=30)
        else 0.1
    )


def evidence_score(
    *, dated_sources: int, total_sources: int, tier12_sources: int, primary_source_present: bool, min_source_count: int
) -> float:
    if min_source_count < 1:
        raise ValueError("min_source_count must be positive")
    return (
        0.4 * min(dated_sources, min_source_count) / min_source_count
        + 0.4 * (tier12_sources / total_sources if total_sources else 0)
        + 0.2 * primary_source_present
    )


def rubric_to_unit(score: int) -> float:
    if not 1 <= score <= 5:
        raise ValueError("rubric score must be 1..5")
    return (score - 1) / 4


def score_candidate(inputs: ScoreInputs, *, weights: ScoreWeights, min_source_count: int, now: datetime) -> ScoreCard:
    time = timeliness_score(inputs.newest_published_at, now=now)
    evidence = evidence_score(
        dated_sources=inputs.dated_sources,
        total_sources=inputs.total_sources,
        tier12_sources=inputs.tier12_sources,
        primary_source_present=inputs.primary_source_present,
        min_source_count=min_source_count,
    )
    components = [
        (
            "timeliness",
            weights.timeliness,
            time,
            "no dated source"
            if inputs.newest_published_at is None
            else f"newest source {max(0, int((now - inputs.newest_published_at).total_seconds() / 3600))} hours old",
        ),
        ("novelty", weights.novelty, inputs.novelty_score, inputs.novelty_justification),
        (
            "evidence",
            weights.evidence,
            evidence,
            f"{inputs.dated_sources} dated sources; {inputs.tier12_sources} tier 1-2 sources",
        ),
    ]
    for key, weight, rubric in (
        ("mdcopilotRelevance", weights.mdcopilot_relevance, inputs.business_relevance),
        ("audience", weights.audience, inputs.audience_relevance),
        ("editorial", weights.editorial, inputs.editorial_potential),
    ):
        components.append(
            (
                key,
                weight,
                rubric_to_unit(rubric.score) if rubric else 0.5,
                rubric.justification if rubric else "manual topic; neutral rubric",
            )
        )
    breakdown = {
        key: ScoreItem(weight=weight, score=round(score, 6), justification=reason)
        for key, weight, score, reason in components
    }
    return ScoreCard(
        time,
        inputs.novelty_score,
        evidence,
        breakdown["mdcopilotRelevance"].score,
        breakdown["audience"].score,
        breakdown["editorial"].score,
        round(sum(x.weight * x.score for x in breakdown.values()), 6),
        breakdown,
    )
