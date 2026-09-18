"""Research Analyst agent: typed digest with marker validation in code."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from html import escape
from typing import Literal

from pydantic import Field

from mdcopilot_blog.agents.common import (
    UNTRUSTED_NOTICE,
    NumberedSource,
    render_source_list,
    resolve_markers,
)
from mdcopilot_blog.domain.claim_rules import MAX_FINDINGS
from mdcopilot_blog.domain.contracts import ClaimType, Contract, Marker, UnitScore
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import OutputRejected, UnknownCitationMarker
from mdcopilot_blog.llm.gateway import (
    AgentResult,
    AgentSpec,
    CallContext,
    LLMGateway,
)

MAX_HINTS = 10


class AnalystFinding(Contract):
    claim: str = Field(min_length=1, max_length=1000)
    evidence: str = Field(min_length=1, max_length=2000)
    confidence: UnitScore
    category: Literal[
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
    claim_type: ClaimType
    importance: Literal["high", "normal"]
    self_reported: bool
    markers: list[Marker] = Field(min_length=1, max_length=8)


class AnalystDigest(Contract):
    findings: list[AnalystFinding] = Field(max_length=MAX_FINDINGS)


RESEARCH_ANALYST_SPEC = AgentSpec(
    name=AgentName.RESEARCH,
    version="1",
    prompt_name="research/synthesize",
    output_type=AnalystDigest,
    max_output_tokens=6000,
    output_retries=1,
    timeout_seconds=120.0,
    reasoning="low",
)


@dataclass(frozen=True)
class SearchHint:
    query: str
    excerpt: str


def build_variables(
    *,
    pillar_name: str | None,
    pillar_topics: Sequence[str],
    window_days: int,
    today: date,
) -> dict[str, object]:
    return {
        "untrusted_notice": UNTRUSTED_NOTICE,
        "pillar_name": pillar_name or "none (general scan)",
        "pillar_topics": ", ".join(pillar_topics) or "none",
        "window_days": window_days,
        "today": today.isoformat(),
        "max_findings": MAX_FINDINGS,
    }


def build_user_prompt(*, numbered: Sequence[NumberedSource], hints: Sequence[SearchHint]) -> str:
    blocks = [
        f'<untrusted_search_hint id="H{index}">\n{escape(hint.query)}\n{escape(hint.excerpt)}\n</untrusted_search_hint>'
        for index, hint in enumerate(hints[:MAX_HINTS], start=1)
    ]
    hint_text = "\n\n".join(blocks) if blocks else "none"
    return (
        "Numbered sources (cite by marker only):\n\n"
        + render_source_list(numbered, include_text=True)
        + "\n\nSearch answer hints (unverified summaries; never cite them):\n\n"
        + hint_text
    )


def digest_markers(digest: AnalystDigest) -> list[str]:
    seen: set[str] = set()
    markers: list[str] = []
    for finding in digest.findings:
        for marker in finding.markers:
            if marker not in seen:
                seen.add(marker)
                markers.append(marker)
    return markers


def marker_check(numbered: Sequence[NumberedSource]) -> Callable[[AnalystDigest], None]:
    def check(output: AnalystDigest) -> None:
        try:
            resolve_markers(digest_markers(output), numbered)
        except UnknownCitationMarker as exc:
            raise OutputRejected(f"unknown markers: {', '.join(exc.args[0])}") from exc

    return check


async def run_research_analyst(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    numbered: Sequence[NumberedSource],
    hints: Sequence[SearchHint],
    variables: Mapping[str, object],
    route_override: Sequence[str] | None,
    prompt_version: int | None,
) -> AgentResult[AnalystDigest]:
    return await gateway.run(
        RESEARCH_ANALYST_SPEC,
        variables=variables,
        user_prompt=build_user_prompt(numbered=numbered, hints=hints),
        ctx=ctx,
        route_override=route_override,
        prompt_version=prompt_version,
        output_check=marker_check(numbered),
    )
