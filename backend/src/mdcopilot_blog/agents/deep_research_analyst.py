"""Evidence packet synthesis; ledger identities are added only by application code."""

import json
from collections.abc import Sequence
from typing import Any

from mdcopilot_blog.agents.common import UNTRUSTED_NOTICE, NumberedSource, render_source_list, resolve_markers
from mdcopilot_blog.domain.config import EffectiveConfig
from mdcopilot_blog.domain.contracts import ResearchPacket, SourceRef
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import OutputRejected, UnknownCitationMarker
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway

DEEP_RESEARCH_SPEC = AgentSpec(
    name=AgentName.DEEP_RESEARCH,
    version="1",
    prompt_name="deep_research/packet",
    output_type=ResearchPacket,
    max_output_tokens=4000,
    reasoning="medium",
)


async def run_deep_research_analyst(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    config: EffectiveConfig,
    topic: dict[str, Any],
    numbered: Sequence[NumberedSource],
) -> AgentResult[ResearchPacket]:
    def validate(output: ResearchPacket) -> None:
        markers = (
            output.primary_markers
            + output.supporting_markers
            + [m for fact in [*output.key_facts, *output.counterarguments] for m in fact.markers]
            + [m for statistic in output.statistics for m in statistic.markers]
        )
        try:
            resolve_markers(markers, numbered)
        except UnknownCitationMarker as exc:
            raise OutputRejected(str(exc)) from exc
        if output.source_refs:
            raise OutputRejected("sourceRefs must be empty; application code assigns ledger references")

    result = await gateway.run(
        DEEP_RESEARCH_SPEC,
        variables={"untrusted_notice": UNTRUSTED_NOTICE},
        user_prompt="# Topic\n" + json.dumps(topic) + "\n# Sources\n" + render_source_list(numbered, include_text=True),
        ctx=ctx,
        route_override=config.routes["deep_research"],
        prompt_version=config.prompt_versions.get(DEEP_RESEARCH_SPEC.prompt_name),
        output_check=validate,
    )
    result.output.source_refs = [SourceRef(marker=s.marker, source_id=str(s.source_id)) for s in numbered]
    return result
