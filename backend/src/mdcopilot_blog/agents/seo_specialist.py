"""SEO and social metadata constrained to supplied link and source candidates."""

from collections.abc import Sequence
from dataclasses import dataclass

from mdcopilot_blog.agents.common import UNTRUSTED_NOTICE, NumberedSource, render_source_list, resolve_markers
from mdcopilot_blog.agents.fact_checker import ArticleText, article_prompt
from mdcopilot_blog.domain.config import BrandProfileValues
from mdcopilot_blog.domain.contracts import SeoPackage
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import OutputRejected, UnknownCitationMarker
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway


@dataclass(frozen=True)
class LinkCandidate:
    title: str
    url: str


SEO_SPEC = AgentSpec(
    name=AgentName.SEO,
    version="1",
    prompt_name="seo/package",
    output_type=SeoPackage,
    max_output_tokens=3000,
    reasoning="minimal",
)


async def run_seo_specialist(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    brand: BrandProfileValues,
    site_url: str,
    category: str,
    article: ArticleText,
    title: str,
    excerpt: str,
    numbered: Sequence[NumberedSource],
    link_candidates: Sequence[LinkCandidate],
    route_override: Sequence[str] | None = None,
    prompt_version: int | None = None,
) -> AgentResult[SeoPackage]:
    def validate(output: SeoPackage) -> None:
        try:
            resolve_markers(output.seo.external_references, numbered)
        except UnknownCitationMarker as exc:
            raise OutputRejected(str(exc)) from exc
        if any(
            link.url not in {candidate.url for candidate in link_candidates}
            for link in output.seo.internal_link_suggestions
        ):
            raise OutputRejected("internal links must come from the supplied candidates")

    prompt = (
        title
        + "\n"
        + excerpt
        + "\n"
        + article_prompt(article)
        + "\n# Sources\n"
        + render_source_list(numbered, include_text=False)
        + "\n# Internal link candidates\n"
        + "\n".join(f"{link.title}: {link.url}" for link in link_candidates)
    )
    return await gateway.run(
        SEO_SPEC,
        variables={"untrusted_notice": UNTRUSTED_NOTICE, "category": category, "site_url": site_url},
        user_prompt=prompt,
        ctx=ctx,
        route_override=route_override,
        prompt_version=prompt_version,
        output_check=validate,
    )
