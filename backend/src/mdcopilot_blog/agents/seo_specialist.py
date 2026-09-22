"""SEO and social metadata constrained to supplied link and source candidates."""

from collections.abc import Sequence

from mdcopilot_blog.agents.common import UNTRUSTED_NOTICE, NumberedSource, render_source_list, resolve_markers
from mdcopilot_blog.agents.fact_checker import ArticleText, article_prompt
from mdcopilot_blog.domain.config import BrandProfileValues
from mdcopilot_blog.domain.contracts import SeoPackage
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import OutputRejected, UnknownCitationMarker
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway

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
    route_override: Sequence[str] | None = None,
) -> AgentResult[SeoPackage]:
    def validate(output: SeoPackage) -> None:
        try:
            resolve_markers(output.seo.external_references, numbered)
        except UnknownCitationMarker as exc:
            raise OutputRejected(str(exc)) from exc
        if output.seo.internal_link_suggestions:
            raise OutputRejected("no internal link candidates were supplied; internalLinkSuggestions must be []")

    prompt = (
        title
        + "\n"
        + excerpt
        + "\n"
        + article_prompt(article)
        + "\n# Sources\n"
        + render_source_list(numbered, include_text=False)
        + "\n# Internal link candidates\n(none)"
    )
    return await gateway.run(
        SEO_SPEC,
        variables={"untrusted_notice": UNTRUSTED_NOTICE, "category": category, "site_url": site_url},
        user_prompt=prompt,
        ctx=ctx,
        route_override=route_override,
        output_check=validate,
    )
