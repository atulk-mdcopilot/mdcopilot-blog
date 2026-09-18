"""Topic strategist with exactly three evidence-backed and distinct ideas."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import Field

from mdcopilot_blog.agents.common import (
    UNTRUSTED_NOTICE,
    NumberedSource,
    render_brand_voice,
    render_source_list,
    resolve_markers,
)
from mdcopilot_blog.domain.config import BrandProfileValues
from mdcopilot_blog.domain.contracts import Contract, Marker, PillarKey
from mdcopilot_blog.domain.diversity import normalize_words
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import OutputRejected, UnknownCitationMarker
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway


class RubricScore(Contract):
    score: int = Field(ge=1, le=5)
    justification: str = Field(min_length=1, max_length=600)


class TopicIdea(Contract):
    title: str = Field(min_length=1, max_length=300)
    hook: str = Field(min_length=1, max_length=1000)
    why_now: str = Field(min_length=1, max_length=1000)
    thesis: str = Field(min_length=1, max_length=1000)
    angle: str = Field(min_length=1, max_length=1000)
    core_argument: str = Field(min_length=1, max_length=600)
    mdcopilot_connection: str = Field(min_length=1, max_length=1000)
    target_audience: str = Field(min_length=1, max_length=300)
    pillar: PillarKey
    source_markers: list[Marker] = Field(min_length=1, max_length=8)
    primary_marker: Marker
    examples: list[str] = Field(max_length=8)
    business_relevance: RubricScore
    audience_relevance: RubricScore
    editorial_potential: RubricScore


class TopicIdeas(Contract):
    ideas: list[TopicIdea] = Field(min_length=3, max_length=3)


TOPIC_STRATEGIST_SPEC = AgentSpec(
    name=AgentName.IDEATION,
    version="1",
    prompt_name="ideation/topics",
    output_type=TopicIdeas,
    max_output_tokens=5000,
    output_retries=1,
    timeout_seconds=120.0,
    reasoning="low",
)


@dataclass(frozen=True)
class PillarBrief:
    key: str
    name: str
    description: str
    topics: tuple[str, ...]


@dataclass(frozen=True)
class FindingBrief:
    claim: str
    claim_type: str
    importance: str
    confidence: float
    markers: tuple[str, ...]


@dataclass(frozen=True)
class AvoidTopic:
    title: str
    thesis: str


def build_variables(
    *,
    brand: BrandProfileValues,
    target_pillar: PillarBrief,
    pillars: Sequence[PillarBrief],
    pillar_counts: Mapping[str, int],
    theme_counts: Mapping[str, int],
    avoid: Sequence[AvoidTopic],
) -> dict[str, str]:
    return {
        "untrusted_notice": UNTRUSTED_NOTICE,
        "brand_name": brand.name,
        "brand_voice": render_brand_voice(brand),
        "brand_mission": brand.mission,
        "target_audience": brand.target_audience,
        "target_pillar": f"{target_pillar.key} — {target_pillar.name}: {target_pillar.description}",
        "pillar_catalogue": "\n".join(f"{p.key}: {p.name}: {p.description}" for p in pillars),
        "coverage_counts": f"Pillars: {dict(pillar_counts)}\nThemes: {dict(theme_counts)}",
        "avoid_list": "\n".join(f"- {a.title} — {a.thesis}" for a in avoid) or "(none)",
    }


def build_user_prompt(
    *, round_no: int, target_pillar: PillarBrief, findings: Sequence[FindingBrief], numbered: Sequence[NumberedSource]
) -> str:
    return (
        f"Round: {round_no}\nTarget pillar: {target_pillar.key} — {target_pillar.name}\nFindings:\n"
        + "\n".join(
            f"[{f.claim_type}, {f.importance}, {f.confidence:.2f}] {f.claim} — sources: {', '.join(f.markers)}"
            for f in findings
        )
        + "\nSources:\n"
        + render_source_list(numbered, include_text=False)
    )


def check_ideas(ideas: TopicIdeas, *, numbered: Sequence[NumberedSource], avoid: Sequence[AvoidTopic]) -> None:
    titles = {normalize_words(a.title) for a in avoid}
    theses = {normalize_words(a.thesis) for a in avoid if a.thesis.strip()}
    for idea in ideas.ideas:
        try:
            resolve_markers([*idea.source_markers, idea.primary_marker], numbered)
        except UnknownCitationMarker as exc:
            raise OutputRejected("Use only provided source markers") from exc
        if idea.primary_marker not in idea.source_markers:
            raise OutputRejected("Primary marker must be included in source markers")
        if normalize_words(idea.title) in titles or normalize_words(idea.thesis) in theses:
            raise OutputRejected("Ideas must not repeat earlier titles or theses")
        titles.add(normalize_words(idea.title))
        theses.add(normalize_words(idea.thesis))


async def run_topic_strategist(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    variables: Mapping[str, str],
    user_prompt: str,
    numbered: Sequence[NumberedSource],
    avoid: Sequence[AvoidTopic],
    route_override: Sequence[str] | None,
    prompt_version: int | None,
) -> AgentResult[TopicIdeas]:
    return await gateway.run(
        TOPIC_STRATEGIST_SPEC,
        variables=variables,
        user_prompt=user_prompt,
        ctx=ctx,
        route_override=route_override,
        prompt_version=prompt_version,
        output_check=lambda output: check_ideas(output, numbered=numbered, avoid=avoid),
    )
