"""Editorial quality, brand voice and revision recommendations."""

from collections.abc import Sequence

from mdcopilot_blog.agents.common import UNTRUSTED_NOTICE, render_brand_voice
from mdcopilot_blog.agents.fact_checker import ArticleText, article_prompt
from mdcopilot_blog.domain.config import BrandProfileValues, WordCountRange
from mdcopilot_blog.domain.contracts import AvoidBundle, EditorialReview, TitleOptions
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import OutputRejected
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway

EDITORIAL_SPEC = AgentSpec(
    name=AgentName.EDITORIAL,
    version="1",
    prompt_name="editorial/review",
    output_type=EditorialReview,
    max_output_tokens=3000,
    reasoning="medium",
)


async def run_editorial_reviewer(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    brand: BrandProfileValues,
    avoid: AvoidBundle,
    word_count: WordCountRange,
    article: ArticleText,
    title_options: TitleOptions,
    cta: str,
    excerpt: str,
    route_override: Sequence[str] | None = None,
    prompt_version: int | None = None,
) -> AgentResult[EditorialReview]:
    def validate(output: EditorialReview) -> None:
        changes = output.required_changes + output.optional_changes
        if len({c.id for c in changes}) != len(changes):
            raise OutputRejected("change ids must be unique")

    return await gateway.run(
        EDITORIAL_SPEC,
        variables={
            "untrusted_notice": UNTRUSTED_NOTICE,
            "brand_voice": render_brand_voice(brand),
            "avoid_bundle": avoid.model_dump_json(),
            "word_count_min": word_count.min,
            "word_count_max": word_count.max,
        },
        user_prompt=title_options.model_dump_json()
        + "\n"
        + article_prompt(article)
        + "\nCTA: "
        + cta
        + "\nExcerpt: "
        + excerpt,
        ctx=ctx,
        route_override=route_override,
        prompt_version=prompt_version,
        output_check=validate,
    )
