"""Clinical safety and medical framing review."""

from collections.abc import Sequence

from mdcopilot_blog.agents.common import UNTRUSTED_NOTICE, render_brand_voice
from mdcopilot_blog.agents.fact_checker import ArticleText, article_prompt
from mdcopilot_blog.domain.config import BrandProfileValues
from mdcopilot_blog.domain.contracts import ClinicalReview
from mdcopilot_blog.domain.enums import AgentName, ClinicalFlagCode
from mdcopilot_blog.domain.errors import OutputRejected
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway

CLINICAL_SPEC = AgentSpec(
    name=AgentName.CLINICAL,
    version="1",
    prompt_name="clinical/review",
    output_type=ClinicalReview,
    max_output_tokens=3000,
    reasoning="medium",
)


async def run_clinical_reviewer(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    brand: BrandProfileValues,
    article: ArticleText,
    title: str,
    route_override: Sequence[str] | None = None,
) -> AgentResult[ClinicalReview]:
    def validate(output: ClinicalReview) -> None:
        for flag in output.flags:
            if flag.code not in {code.value for code in ClinicalFlagCode}:
                raise OutputRejected("unknown clinical flag code")

    return await gateway.run(
        CLINICAL_SPEC,
        variables={"untrusted_notice": UNTRUSTED_NOTICE, "brand_voice": render_brand_voice(brand)},
        user_prompt=title + "\n" + article_prompt(article),
        ctx=ctx,
        route_override=route_override,
        output_check=validate,
    )
