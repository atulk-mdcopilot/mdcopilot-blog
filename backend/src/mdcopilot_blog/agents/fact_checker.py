"""Independent evidence review with source validation and deterministic claim locations."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from mdcopilot_blog.agents.common import UNTRUSTED_NOTICE, NumberedSource, render_source_list, resolve_markers
from mdcopilot_blog.domain.contracts import ArticleSection, ClaimKind, Contract, Marker, UnitScore, VerificationStatus
from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.domain.errors import OutputRejected, UnknownCitationMarker
from mdcopilot_blog.domain.numeric_scan import locate_sentence
from mdcopilot_blog.llm.gateway import AgentResult, AgentSpec, CallContext, LLMGateway


class ExtractedClaim(Contract):
    claim: str
    kind: ClaimKind
    importance: Literal["high", "normal"]
    section_key: str
    span: str
    citation_markers: list[Marker]
    source_marker: Marker | None
    verification_status: VerificationStatus
    confidence: UnitScore
    recommended_revision: str | None
    verification_markers: list[Marker]


class ExtractedClaims(Contract):
    claims: list[ExtractedClaim]


@dataclass(frozen=True)
class ArticleText:
    sections: tuple[ArticleSection, ...]
    pull_quote: str

    def text_for(self, section_key: str) -> str | None:
        if section_key == "pull_quote":
            return self.pull_quote
        return next((section.body_markdown for section in self.sections if section.key.value == section_key), None)


FACT_CHECK_SPEC = AgentSpec(
    name=AgentName.FACT_CHECK,
    version="1",
    prompt_name="fact_check/check",
    output_type=ExtractedClaims,
    max_output_tokens=6000,
    reasoning="low",
)


def article_prompt(article: ArticleText) -> str:
    return (
        "\n\n".join(f"## section: {section.key.value}\n\n{section.body_markdown}" for section in article.sections)
        + "\n\n## section: pull_quote\n\n"
        + article.pull_quote
    )


def build_variables() -> dict[str, object]:
    return {"untrusted_notice": UNTRUSTED_NOTICE}


def build_user_prompt(
    article: ArticleText,
    numbered: Sequence[NumberedSource],
    *,
    verification_from: int | None = None,
    unsupported_claims: Sequence[str] = (),
) -> str:
    prompt = (
        "# Article\n\n"
        + article_prompt(article)
        + "\n\n# Sources\n\n"
        + render_source_list(numbered[:verification_from], include_text=True)
    )
    if verification_from is not None:
        prompt += (
            "\n\n# Verification sources\n\n"
            + render_source_list(numbered[verification_from:], include_text=True)
            + "\n\n# Previously unsupported claims\n\n"
            + "\n".join(f"- {claim}" for claim in unsupported_claims)
        )
    return prompt


def check_output(
    output: ExtractedClaims,
    *,
    article: ArticleText,
    numbered: Sequence[NumberedSource],
    verification_from: int | None = None,
) -> None:
    verification = (
        {source.marker for source in numbered[verification_from:]} if verification_from is not None else set()
    )
    for claim in output.claims:
        try:
            resolve_markers(
                claim.citation_markers
                + claim.verification_markers
                + ([claim.source_marker] if claim.source_marker else []),
                numbered,
            )
        except UnknownCitationMarker as exc:
            raise OutputRejected(str(exc)) from exc
        if not set(claim.verification_markers) <= verification:
            raise OutputRejected("verification markers used without verification sources")
        body = article.text_for(claim.section_key)
        if body is None:
            raise OutputRejected(f"unknown section key: {claim.section_key}")
        if locate_sentence(body, claim.span) is None:
            raise OutputRejected(f"span not found in {claim.section_key}: {claim.span}")
        if (
            claim.verification_status == VerificationStatus.SUPPORTED
            and claim.source_marker is None
            and claim.kind != ClaimKind.OPINION
        ):
            raise OutputRejected(f"supported claim without a source marker: {claim.claim}")


async def run_fact_checker(
    gateway: LLMGateway,
    *,
    ctx: CallContext,
    article: ArticleText,
    numbered: Sequence[NumberedSource],
    verification_from: int | None = None,
    unsupported_claims: Sequence[str] = (),
    route_override: Sequence[str] | None = None,
    prompt_version: int | None = None,
) -> AgentResult[ExtractedClaims]:
    return await gateway.run(
        FACT_CHECK_SPEC,
        variables=build_variables(),
        user_prompt=build_user_prompt(
            article, numbered, verification_from=verification_from, unsupported_claims=unsupported_claims
        ),
        ctx=ctx,
        route_override=route_override,
        prompt_version=prompt_version,
        output_check=lambda output: check_output(
            output, article=article, numbered=numbered, verification_from=verification_from
        ),
    )
