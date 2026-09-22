"""Structured article writing with validated source markers."""

import json
from collections.abc import Sequence
from typing import Any

from mdcopilot_blog.agents.common import (
    UNTRUSTED_NOTICE,
    NumberedSource,
    render_avoid_bundle,
    render_brand_voice,
    render_source_list,
    resolve_markers,
)
from mdcopilot_blog.domain.article_assembly import VersionContent, build_version_content
from mdcopilot_blog.domain.config import BrandProfileValues, EffectiveConfig, WordCountRange
from mdcopilot_blog.domain.contracts import ArticleDraft, ResearchPacket, RevisionFinding
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import ArticleStructureError, OutputRejected, UnknownCitationMarker
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway

WRITER_DRAFT_SPEC = AgentSpec(
    name=AgentName.WRITER,
    version="1",
    prompt_name="writer/draft",
    output_type=ArticleDraft,
    max_output_tokens=4500,
    reasoning="medium",
)
WRITER_REVISE_SPEC = AgentSpec(
    name=AgentName.WRITER,
    version="1",
    prompt_name="writer/revise",
    output_type=ArticleDraft,
    max_output_tokens=4500,
    reasoning="medium",
)


def build_variables(
    *, brand: BrandProfileValues, word_count: WordCountRange, voice: str | None = None
) -> dict[str, object]:
    return {
        "untrusted_notice": UNTRUSTED_NOTICE,
        "brand_voice": render_brand_voice(brand),
        "avoid_bundle": render_avoid_bundle(brand),
        "word_count_min": word_count.min,
        "word_count_max": word_count.max,
        "voice": voice or ", ".join(brand.tone),
    }


def check_draft(draft: ArticleDraft, numbered: Sequence[NumberedSource]) -> VersionContent:
    content = build_version_content(
        title_options=draft.title_options,
        sections=draft.sections,
        pull_quote=draft.pull_quote,
        cta=draft.cta,
        excerpt=draft.excerpt,
    )
    resolve_markers(content.citation_markers, numbered)
    return content


async def run_writer(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    config: EffectiveConfig,
    brand: BrandProfileValues,
    topic: dict[str, Any],
    packet: ResearchPacket,
    numbered: Sequence[NumberedSource],
    base: VersionContent | None = None,
    findings: Sequence[RevisionFinding] = (),
    voice: str | None = None,
) -> AgentResult[Any]:
    spec = WRITER_REVISE_SPEC if findings else WRITER_DRAFT_SPEC
    packet_data = packet.model_dump(mode="json", exclude={"source_refs"})
    prompt = (
        "# Topic\n"
        + json.dumps(topic, ensure_ascii=False)
        + "\n# Research packet\n"
        + json.dumps(packet_data, ensure_ascii=False)
        + "\n# Sources\n"
        + render_source_list(numbered, include_text=True)
    )
    if base:
        prompt += "\n# Current article\n" + json.dumps(
            {
                "titleOptions": base.title_options.model_dump(),
                "sections": [s.model_dump() for s in base.sections],
                "pullQuote": base.pull_quote,
                "cta": base.cta,
                "excerpt": base.excerpt,
            }
        )
    mapping = {f"F{i}": finding.finding_id for i, finding in enumerate(findings, 1)}
    if findings:
        prompt += "\n# Findings\n" + json.dumps(
            [{**f.model_dump(), "findingId": marker} for marker, f in zip(mapping, findings, strict=True)]
        )

    def validate(output: Any) -> None:
        try:
            check_draft(output, numbered)
            if findings and (
                {r.finding_id for r in output.resolutions} != set(mapping) or len(output.resolutions) != len(mapping)
            ):
                raise OutputRejected("include exactly one resolution for every F marker")
        except (ArticleStructureError, UnknownCitationMarker) as exc:
            raise OutputRejected(str(exc)) from exc

    result = await gateway.run(
        spec,
        variables=build_variables(brand=brand, word_count=config.word_count, voice=voice),
        user_prompt=prompt,
        ctx=ctx,
        route_override=config.routes[spec.name.value],
        output_check=validate,
    )
    if findings:
        for resolution in result.output.resolutions:
            resolution.finding_id = mapping[resolution.finding_id]
    return result
