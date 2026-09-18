"""Deterministic article release gates. Missing evidence always fails closed."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from mdcopilot_blog.domain.config import BrandProfileValues, EffectiveConfig
from mdcopilot_blog.domain.contracts import (
    SECTION_ORDER,
    ArticleSection,
    ClaimCheck,
    ClinicalFlag,
    ClinicalReview,
    Contract,
    EditorialReview,
    FactCheckResult,
    GateReport,
    GateResult,
    SEOMetadata,
    SocialCopy,
    TitleOptions,
)
from mdcopilot_blog.domain.enums import GateId, GateRunKind
from mdcopilot_blog.domain.numeric_scan import numeric_sentences
from mdcopilot_blog.domain.quotes import find_quotes, unverified_quotes
from mdcopilot_blog.domain.text import assemble_markdown, body_word_count, normalize_for_match, strip_citation_markers

BAD_STATUSES = {"UNSUPPORTED", "OUTDATED", "MISLEADING"}
FULL_ORDER = tuple(GateId)
DETERMINISTIC_ORDER = tuple(
    GateId(value)
    for value in (
        "sources_present",
        "no_duplicate_topic",
        "word_count",
        "required_structure",
        "cta_fresh",
        "no_prohibited_language",
        "seo_complete",
        "disclosure_present",
        "opening_diversity",
        "headline_diversity",
        "source_domain_diversity",
    )
)
FIXABLE_BLOCKING = frozenset(g.value for g in list(GateId)[:15]) - {
    "sources_present",
    "no_duplicate_topic",
    "disclosure_present",
}


@dataclass(frozen=True)
class CitedSource:
    source_id: str
    marker: str
    tier: int
    text_snapshot: str | None


@dataclass(frozen=True)
class LineageReview[P: Contract]:
    review_id: str
    version_id: str
    payload: P


@dataclass(frozen=True)
class GateInputs:
    version_id: str
    sections: tuple[ArticleSection, ...]
    content_markdown: str
    title: str
    title_options: TitleOptions
    pull_quote: str
    cta: str
    excerpt: str
    cited_sources: tuple[CitedSource, ...]
    seo: SEOMetadata | None
    social: SocialCopy | None
    slug_taken: bool
    fact_check: FactCheckResult | None
    clinical: LineageReview[ClinicalReview] | None
    clinical_resolved: frozenset[str]
    editorial: LineageReview[EditorialReview] | None
    editorial_resolved: frozenset[str]
    duplicate: GateResult | None
    cta_fresh: GateResult | None
    diversity_warnings: tuple[GateResult, ...]
    config: EffectiveConfig
    brand: BrandProfileValues


def fact_check_verdict(claims: Sequence[ClaimCheck]) -> Literal["PASS", "FAIL"]:
    return (
        "FAIL"
        if any(
            c.verification_status in BAD_STATUSES
            and (c.importance == "high" or c.kind in {"statistic", "quote_or_attribution", "anecdote_or_vignette"})
            for c in claims
        )
        else "PASS"
    )


def _result(gate: str, problems: list[str]) -> GateResult:
    return GateResult(
        gate=str(gate),
        passed=not problems,
        severity="warning" if GateId(gate) in tuple(GateId)[15:] else "blocking",
        details="; ".join(problems) if problems else "ok",
    )


def _location(claim: ClaimCheck) -> str:
    return f"{claim.section_key}#{claim.sentence_index}"


def gate_sources_present(i: GateInputs) -> GateResult:
    n = len({s.source_id for s in i.cited_sources})
    k = len({s.source_id for s in i.cited_sources if s.tier <= 2})
    return _result(
        "sources_present",
        []
        if n >= i.config.research.min_source_count and k
        else [f"{n} distinct cited sources (minimum {i.config.research.min_source_count}); tier 1/2 sources: {k}"],
    )


def gate_claims_verified(i: GateInputs) -> GateResult:
    problems = (
        [
            f"{c.verification_status} {_location(c)}: {c.claim}"
            for c in i.fact_check.claims
            if c.importance == "high" and c.verification_status in BAD_STATUSES
        ]
        if i.fact_check
        else ["no fact check for this version"]
    )
    return _result("claims_verified", problems)


def gate_no_unsupported_statistics(i: GateInputs) -> GateResult:
    if not i.fact_check:
        return _result("no_unsupported_statistics", ["no fact check for this version"])
    problems = [
        f"statistic claims not supported: {_location(c)}"
        for c in i.fact_check.claims
        if c.kind == "statistic" and c.verification_status != "SUPPORTED"
    ]
    for sentence in numeric_sentences(i.sections, i.pull_quote):
        text = normalize_for_match(strip_citation_markers(sentence.text))
        covered = any(
            c.verification_status not in BAD_STATUSES
            and (
                (c.section_key, c.sentence_index) == (sentence.section_key, sentence.index)
                or (
                    normalize_for_match(strip_citation_markers(c.span))
                    and normalize_for_match(strip_citation_markers(c.span)) in text
                )
            )
            for c in i.fact_check.claims
        )
        if not covered:
            problems.append(
                f"numeric sentences without a verified claim: {sentence.section_key}#{sentence.index}: {sentence.text}"
            )
    return _result("no_unsupported_statistics", problems)


def gate_no_fabricated_quotes(i: GateInputs) -> GateResult:
    problems = [
        f"quotes not found in cited sources: “{q.text}” ({q.section_key}#{q.sentence_index})"
        for q in unverified_quotes(find_quotes(i.sections), [s.text_snapshot for s in i.cited_sources])
    ]
    if i.fact_check:
        problems += [
            f"attributions not verified: {_location(c)}: {c.claim}"
            for c in i.fact_check.claims
            if c.kind == "quote_or_attribution" and c.verification_status in BAD_STATUSES
        ]
    return _result("no_fabricated_quotes", problems)


def _clinical_flags(i: GateInputs) -> list[ClinicalFlag]:
    return (
        [
            f
            for index, f in enumerate(i.clinical.payload.flags)
            if f.severity == "BLOCKING" and f"clinical:{i.clinical.review_id}:{index}" not in i.clinical_resolved
        ]
        if i.clinical
        else []
    )


def gate_no_unsourced_anecdotes(i: GateInputs) -> GateResult:
    problems = (
        [
            f"anecdotes without a source: {_location(c)}"
            for c in i.fact_check.claims
            if c.kind == "anecdote_or_vignette" and (c.source_id is None or c.verification_status in BAD_STATUSES)
        ]
        if i.fact_check
        else []
    )
    problems += [
        f"clinical flags: {f.code} ({f.location})"
        for f in _clinical_flags(i)
        if f.code in {"invented_anecdote", "invented_physician_experience"}
    ]
    return _result("no_unsourced_anecdotes", problems)


def gate_no_duplicate_topic(i: GateInputs) -> GateResult:
    return _result(
        "no_duplicate_topic",
        []
        if i.duplicate and i.duplicate.passed
        else [i.duplicate.details if i.duplicate else "duplicate check not run"],
    )


def gate_word_count(i: GateInputs) -> GateResult:
    count = body_word_count(i.sections)
    return _result(
        "word_count",
        []
        if i.config.word_count.min <= count <= i.config.word_count.max
        else [f"body has {count} words; allowed {i.config.word_count.min}–{i.config.word_count.max}"],
    )


def gate_required_structure(i: GateInputs) -> GateResult:
    problems: list[str] = []
    if tuple(s.key for s in i.sections) != SECTION_ORDER:
        problems.append("sections must be " + ", ".join(SECTION_ORDER))
    for section in i.sections:
        if section.key == SECTION_ORDER[0] and section.heading is not None:
            problems.append("introduction must not have a heading")
        if section.key != SECTION_ORDER[0] and not (section.heading or "").strip():
            problems.append(f"section {section.key} has no heading")
        if not section.body_markdown.strip():
            problems.append(f"section {section.key} is empty")
    if not i.pull_quote.strip():
        problems.append("pull quote is empty")
    if not i.cta.strip():
        problems.append("CTA is empty")
    if i.content_markdown != assemble_markdown(i.sections):
        problems.append("content_markdown does not match the sections")
    return _result("required_structure", problems)


def gate_cta_fresh(i: GateInputs) -> GateResult:
    return _result(
        "cta_fresh",
        []
        if i.cta.strip() and i.cta_fresh and i.cta_fresh.passed
        else [
            "CTA is empty" if not i.cta.strip() else i.cta_fresh.details if i.cta_fresh else "CTA freshness not checked"
        ],
    )


def gate_no_prohibited_language(i: GateInputs) -> GateResult:
    fields = (
        [(f"title_options.{k}", v) for k, v in i.title_options.model_dump().items()]
        + [
            (f"sections.{s.key}.{field}", text or "")
            for s in i.sections
            for field, text in (("heading", s.heading), ("body", s.body_markdown))
        ]
        + [("pull_quote", i.pull_quote), ("cta", i.cta), ("excerpt", i.excerpt)]
    )
    if i.seo:
        fields += [
            (f"seo.{field}", getattr(i.seo, field))
            for field in ("seo_title", "meta_description", "og_title", "og_description")
        ]
    if i.social:
        fields += [
            (f"social.{field}", getattr(i.social, field)) for field in ("linkedin", "x_post", "newsletter_teaser")
        ]
    problems: list[str] = []
    for phrase in i.brand.prohibited_language:
        if not phrase.strip():
            continue
        pattern = (
            r"(?<![a-z0-9])"
            + r"\s+".join(re.escape(word) for word in normalize_for_match(phrase).split())
            + r"(?![a-z0-9])"
        )
        problems.extend(
            f"'{phrase}' in {location}"
            for location, text in fields
            if re.search(pattern, normalize_for_match(strip_citation_markers(text)))
        )
    return _result("no_prohibited_language", ["prohibited phrases: " + "; ".join(problems)] if problems else [])


def gate_seo_complete(i: GateInputs) -> GateResult:
    if not i.seo:
        return _result("seo_complete", ["no SEO record for this version"])
    seo = i.seo
    problems = [
        f"{field} is empty"
        for field in (
            "seo_title",
            "meta_description",
            "slug",
            "primary_keyword",
            "og_title",
            "og_description",
            "category",
        )
        if not getattr(seo, field).strip()
    ]
    problems += [
        f"{field} is empty"
        for field in ("secondary_keywords", "tags", "external_references")
        if not any(value.strip() for value in getattr(seo, field))
    ]
    if len(seo.seo_title) > 60:
        problems.append(f"seo_title has {len(seo.seo_title)} characters (maximum 60)")
    if not 120 <= len(seo.meta_description) <= 160:
        problems.append(f"meta_description has {len(seo.meta_description)} characters (allowed 120–160)")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", seo.slug) or len(seo.slug) > 200:
        problems.append("slug is invalid")
    if i.slug_taken:
        problems.append("slug is already used by another article")
    if len(i.title) > 200:
        problems.append(f"title has {len(i.title)} characters (maximum 200)")
    if len(i.excerpt) > 500:
        problems.append(f"excerpt has {len(i.excerpt)} characters (maximum 500)")
    unknown = [source for source in seo.external_references if source not in {s.source_id for s in i.cited_sources}]
    if unknown:
        problems.append("external_references cite sources not in this version: " + ", ".join(unknown))
    if i.social is None or not all(
        (i.social.linkedin.strip(), i.social.x_post.strip(), i.social.newsletter_teaser.strip())
    ):
        problems.append("social copy missing")
    return _result("seo_complete", problems)


def gate_fact_check_passed(i: GateInputs) -> GateResult:
    return _result(
        "fact_check_passed",
        []
        if i.fact_check and i.fact_check.verdict == "PASS"
        else ["fact check verdict FAIL" if i.fact_check else "no fact check for this version"],
    )


def gate_clinical_clear(i: GateInputs) -> GateResult:
    return _result(
        "clinical_clear",
        [f"unresolved blocking flags: {flag.code} ({flag.location}): {flag.message}" for flag in _clinical_flags(i)]
        if i.clinical
        else ["no clinical review for this version or its ancestors"],
    )


def gate_editorial_completed(i: GateInputs) -> GateResult:
    return _result(
        "editorial_completed",
        [
            f"required changes without a resolution: {change.id}: {change.description}"
            for change in i.editorial.payload.required_changes
            if f"editorial:{i.editorial.review_id}:{change.id}" not in i.editorial_resolved
        ]
        if i.editorial
        else ["no editorial review for this version or its ancestors"],
    )


def gate_disclosure_present(i: GateInputs) -> GateResult:
    return _result(
        "disclosure_present", [] if i.brand.ai_disclosure.strip() else ["AI-assistance disclosure text is empty"]
    )


def gate_independent_fact_check(i: GateInputs) -> GateResult:
    return _result(
        "independent_fact_check",
        []
        if i.fact_check and i.fact_check.independent_check
        else [
            "fact check was not independent of the writer's provider"
            if i.fact_check
            else "no fact check for this version"
        ],
    )


def diversity_warnings(i: GateInputs) -> list[GateResult]:
    return [
        next(
            (
                warning.model_copy(update={"severity": "warning"})
                for warning in i.diversity_warnings
                if warning.gate == gate
            ),
            GateResult(gate=gate, passed=True, severity="warning", details="not evaluated"),
        )
        for gate in ("opening_diversity", "headline_diversity", "source_domain_diversity")
    ]


def evaluate_gates(inputs: GateInputs, *, run_kind: GateRunKind) -> GateReport:
    warnings = {r.gate: r for r in diversity_warnings(inputs)}
    functions: dict[GateId, Callable[[GateInputs], GateResult]] = {
        GateId.SOURCES_PRESENT: gate_sources_present,
        GateId.CLAIMS_VERIFIED: gate_claims_verified,
        GateId.NO_UNSUPPORTED_STATISTICS: gate_no_unsupported_statistics,
        GateId.NO_FABRICATED_QUOTES: gate_no_fabricated_quotes,
        GateId.NO_UNSOURCED_ANECDOTES: gate_no_unsourced_anecdotes,
        GateId.NO_DUPLICATE_TOPIC: gate_no_duplicate_topic,
        GateId.WORD_COUNT: gate_word_count,
        GateId.REQUIRED_STRUCTURE: gate_required_structure,
        GateId.CTA_FRESH: gate_cta_fresh,
        GateId.NO_PROHIBITED_LANGUAGE: gate_no_prohibited_language,
        GateId.SEO_COMPLETE: gate_seo_complete,
        GateId.FACT_CHECK_PASSED: gate_fact_check_passed,
        GateId.CLINICAL_CLEAR: gate_clinical_clear,
        GateId.EDITORIAL_COMPLETED: gate_editorial_completed,
        GateId.DISCLOSURE_PRESENT: gate_disclosure_present,
        GateId.INDEPENDENT_FACT_CHECK: gate_independent_fact_check,
    }
    results = [
        warnings[gate.value] if gate.value in warnings else functions[gate](inputs)
        for gate in (DETERMINISTIC_ORDER if run_kind == GateRunKind.DETERMINISTIC else FULL_ORDER)
    ]
    return GateReport(passed=all(result.passed for result in results if result.severity == "blocking"), results=results)
