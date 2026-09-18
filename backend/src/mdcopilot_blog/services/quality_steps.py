"""Quality review persistence, citation resolution, lineage and deterministic release gates."""

import logging
import uuid
from collections.abc import Sequence
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.agents.clinical_reviewer import CLINICAL_SPEC, run_clinical_reviewer
from mdcopilot_blog.agents.common import number_sources, resolve_markers
from mdcopilot_blog.agents.editorial_reviewer import EDITORIAL_SPEC, run_editorial_reviewer
from mdcopilot_blog.agents.fact_checker import FACT_CHECK_SPEC, ArticleText, run_fact_checker
from mdcopilot_blog.agents.seo_specialist import SEO_SPEC, LinkCandidate, run_seo_specialist
from mdcopilot_blog.db.models import (
    Article,
    ArticleSource,
    ArticleVersion,
    ClaimCheckRecord,
    ExternalPost,
    LedgerSource,
    LlmCall,
    ResearchPacketRecord,
    Review,
    VersionSeo,
)
from mdcopilot_blog.domain.config import BrandProfileValues, EffectiveConfig
from mdcopilot_blog.domain.contracts import (
    ArticleSection,
    AvoidBundle,
    ClaimCheck,
    ClinicalReview,
    Contract,
    EditorialReview,
    FactCheckResult,
    GateReport,
    RevisionFinding,
    SEOMetadata,
    SocialCopy,
    TitleOptions,
)
from mdcopilot_blog.domain.enums import GateRunKind, ReviewVerdict
from mdcopilot_blog.domain.fix_pass import FixPassDecision, decide_fix_pass
from mdcopilot_blog.domain.gates import (
    BAD_STATUSES,
    CitedSource,
    GateInputs,
    LineageReview,
    evaluate_gates,
    fact_check_verdict,
)
from mdcopilot_blog.domain.numeric_scan import locate_sentence
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.llm.gateway import AgentResult, BudgetExceeded
from mdcopilot_blog.services.article_steps import packet_sources
from mdcopilot_blog.services.step_context import StepContext
from mdcopilot_blog.services.versions import effective_seo, version_chain


class FactCheckStepResult(BaseModel):
    review_id: uuid.UUID
    version_id: uuid.UUID
    verdict: str
    independent_check: bool
    claim_count: int


class ReviewStepResult(BaseModel):
    review_id: uuid.UUID
    version_id: uuid.UUID
    verdict: ReviewVerdict
    blocking_flags: int
    required_changes: int


class SeoStepResult(BaseModel):
    seo_id: uuid.UUID
    version_id: uuid.UUID
    slug: str


class GateStepResult(BaseModel):
    review_id: uuid.UUID
    version_id: uuid.UUID
    report: GateReport
    decision: FixPassDecision


async def load_article_version(
    db: AsyncSession, *, article_id: uuid.UUID, version_id: uuid.UUID
) -> tuple[Article, ArticleVersion]:
    article, version = await db.get(Article, article_id), await db.get(ArticleVersion, version_id)
    if article is None or version is None or version.article_id != article_id:
        raise LookupError("article version not found")
    return article, version


async def load_packet_sources(db: AsyncSession, *, article: Article, version: ArticleVersion) -> list[LedgerSource]:
    packet = await db.get(ResearchPacketRecord, version.research_packet_id) if version.research_packet_id else None
    return await packet_sources(db, packet) if packet else []


def article_text(version: ArticleVersion) -> ArticleText:
    return ArticleText(tuple(ArticleSection.model_validate(s) for s in version.sections), version.pull_quote)


async def writer_provider_for(db: AsyncSession, *, article_id: uuid.UUID, version: ArticleVersion) -> str | None:
    if version.dbos_workflow_id is not None:
        provider = await db.scalar(
            select(LlmCall.provider_served)
            .where(
                LlmCall.article_id == article_id,
                LlmCall.agent_name == "writer",
                LlmCall.status == "ok",
                LlmCall.dbos_workflow_id == version.dbos_workflow_id,
                LlmCall.dbos_step_id == version.dbos_step_id,
            )
            .order_by(LlmCall.created_at.desc())
            .limit(1)
        )
        if provider:
            return provider
    return await db.scalar(
        select(LlmCall.provider_served)
        .where(
            LlmCall.article_id == article_id,
            LlmCall.agent_name == "writer",
            LlmCall.status == "ok",
            LlmCall.created_at <= version.created_at,
        )
        .order_by(LlmCall.created_at.desc())
        .limit(1)
    )


def independent_route(entries: Sequence[str], writer_provider: str | None) -> list[str]:
    return sorted(entries, key=lambda entry: entry.split(":", 1)[0] == writer_provider)


async def _existing(db: AsyncSession, sc: StepContext, kind: str) -> Review | None:
    if sc.call.dbos_workflow_id is None or sc.call.dbos_step_id is None:
        return None
    return cast(
        Review | None,
        await db.scalar(
            select(Review).where(
                Review.dbos_workflow_id == sc.call.dbos_workflow_id,
                Review.dbos_step_id == sc.call.dbos_step_id,
                Review.kind == kind,
            )
        ),
    )


async def latest_review(db: AsyncSession, version_id: uuid.UUID, kind: str) -> Review | None:
    return cast(
        Review | None,
        await db.scalar(
            select(Review)
            .where(Review.version_id == version_id, Review.kind == kind)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .limit(1)
        ),
    )


def _review(
    sc: StepContext | None,
    article_id: uuid.UUID,
    version_id: uuid.UUID,
    kind: str,
    verdict: str,
    payload: Contract,
    result: AgentResult[Any] | None = None,
    **kwargs: Any,
) -> Review:
    return Review(
        id=uuid7(),
        article_id=article_id,
        version_id=version_id,
        kind=kind,
        verdict=verdict,
        payload=payload.model_dump(mode="json"),
        agent_provider=result.provider if result else None,
        agent_model=result.model if result else None,
        dbos_workflow_id=sc.call.dbos_workflow_id if sc else None,
        dbos_step_id=sc.call.dbos_step_id if sc else None,
        **kwargs,
    )


def _fact_result(row: Review) -> FactCheckStepResult:
    payload = FactCheckResult.model_validate(row.payload)
    return FactCheckStepResult(
        review_id=row.id,
        version_id=row.version_id,
        verdict=payload.verdict,
        independent_check=payload.independent_check,
        claim_count=len(payload.claims),
    )


async def fact_check(
    sc: StepContext, *, article_id: uuid.UUID, version_id: uuid.UUID, allow_verification_searches: bool = True
) -> FactCheckStepResult:
    async with sc.sessionmaker() as db:
        existing = await _existing(db, sc, "fact_check")
        if existing:
            return _fact_result(existing)
        article, version = await load_article_version(db, article_id=article_id, version_id=version_id)
        sources = await load_packet_sources(db, article=article, version=version)
        writer_provider = await writer_provider_for(db, article_id=article_id, version=version)
    numbered = number_sources(sources, preserve_order=True)
    route = independent_route(sc.config.routes["fact_check"], writer_provider)
    result = await run_fact_checker(
        sc.gateway,
        ctx=sc.with_ids(article_id=article_id).call,
        article=article_text(version),
        numbered=numbered,
        route_override=route,
        prompt_version=sc.config.prompt_versions.get(FACT_CHECK_SPEC.prompt_name),
    )
    verification_ids = []
    packet_source_count = len(sources)
    unsupported = [
        c.claim
        for c in result.output.claims
        if c.verification_status == "UNSUPPORTED" and (c.importance == "high" or c.kind == "statistic")
    ][: sc.config.research.max_verification_searches]
    if unsupported and allow_verification_searches:
        from mdcopilot_blog.research.deep import verification_lookup

        try:
            lookup = await verification_lookup(
                sc.with_ids(article_id=article_id), article_id=article_id, queries=unsupported
            )
        except (BudgetExceeded, NotImplementedError):
            raise
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "verification lookup failed",
                extra={"article_id": str(article_id), "error_class": type(exc).__name__},
                exc_info=True,
            )
            lookup = None
        async with sc.sessionmaker() as db:
            known = {s.id for s in sources}
            for _, ids in sorted(lookup.source_ids_by_query.items()) if lookup else []:
                for source_id in ids:
                    source = await db.get(LedgerSource, source_id)
                    if source and source_id not in known:
                        sources.append(source)
                        known.add(source_id)
                        verification_ids.append(str(source_id))
        if verification_ids:
            numbered = number_sources(sources, preserve_order=True)
            result = await run_fact_checker(
                sc.gateway,
                ctx=sc.with_ids(article_id=article_id).call,
                article=article_text(version),
                numbered=numbered,
                verification_from=packet_source_count,
                unsupported_claims=unsupported,
                route_override=route,
                prompt_version=sc.config.prompt_versions.get(FACT_CHECK_SPEC.prompt_name),
            )
    claims = []
    for extracted in result.output.claims:
        data = extracted.model_dump(mode="json", exclude={"source_marker", "verification_markers"})
        data["sourceId"] = (
            str(resolve_markers([extracted.source_marker], numbered)[0]) if extracted.source_marker else None
        )
        data["sentenceIndex"] = locate_sentence(
            article_text(version).text_for(extracted.section_key) or "", extracted.span
        )
        claims.append(ClaimCheck.model_validate(data))
    payload = FactCheckResult(
        verdict=fact_check_verdict(claims),
        independent_check=writer_provider is not None and result.provider != writer_provider,
        claims=claims,
    )
    async with sc.sessionmaker() as db:
        await db.execute(select(Article.id).where(Article.id == article_id).with_for_update())
        existing = await _existing(db, sc, "fact_check")
        if existing:
            return _fact_result(existing)
        row = _review(
            sc,
            article_id,
            version_id,
            "fact_check",
            payload.verdict,
            payload,
            result,
            independent_check=payload.independent_check,
            writer_provider=writer_provider,
        )
        db.add(row)
        await db.flush()
        for position, claim in enumerate(claims):
            data = claim.model_dump(by_alias=False)
            data["source_id"] = uuid.UUID(claim.source_id) if claim.source_id else None
            db.add(
                ClaimCheckRecord(
                    id=uuid7(),
                    review_id=row.id,
                    version_id=version_id,
                    position=position,
                    verification_source_ids=[
                        str(value)
                        for value in resolve_markers(result.output.claims[position].verification_markers, numbered)
                    ],
                    **data,
                )
            )
        await db.commit()
        return _fact_result(row)


def _review_result(row: Review) -> ReviewStepResult:
    return ReviewStepResult(
        review_id=row.id,
        version_id=row.version_id,
        verdict=row.verdict,
        blocking_flags=sum(flag["severity"] == "BLOCKING" for flag in row.payload.get("flags", [])),
        required_changes=len(row.payload.get("requiredChanges", [])),
    )


async def _perform_review(
    sc: StepContext, *, article_id: uuid.UUID, version_id: uuid.UUID, kind: str, avoid: AvoidBundle | None = None
) -> ReviewStepResult:
    async with sc.sessionmaker() as db:
        existing = await _existing(db, sc, kind)
        if existing:
            return _review_result(existing)
        article, version = await load_article_version(db, article_id=article_id, version_id=version_id)
    common: dict[str, Any] = {
        "ctx": sc.with_ids(article_id=article_id).call,
        "brand": sc.brand,
        "article": article_text(version),
        "route_override": sc.config.routes[kind],
    }
    result: AgentResult[Any]
    score: float | None = None
    if kind == "clinical":
        result = await run_clinical_reviewer(
            sc.gateway,
            **common,
            title=article.title or "",
            prompt_version=sc.config.prompt_versions.get(CLINICAL_SPEC.prompt_name),
        )
        verdict = "BLOCKED" if any(f.severity == "BLOCKING" for f in result.output.flags) else "CLEAR"
    else:
        if avoid is None:
            raise ValueError("editorial review requires an avoid bundle")
        result = await run_editorial_reviewer(
            sc.gateway,
            **common,
            avoid=avoid,
            word_count=sc.config.word_count,
            title_options=TitleOptions.model_validate(version.title_options),
            cta=version.cta,
            excerpt=version.excerpt,
            prompt_version=sc.config.prompt_versions.get(EDITORIAL_SPEC.prompt_name),
        )
        verdict = "COMPLETED"
        score = result.output.editorial_score
    async with sc.sessionmaker() as db:
        await db.execute(select(Article.id).where(Article.id == article_id).with_for_update())
        existing = await _existing(db, sc, kind)
        if existing:
            return _review_result(existing)
        row = _review(
            sc,
            article_id,
            version_id,
            kind,
            verdict,
            result.output,
            result,
            score=score,
        )
        db.add(row)
        await db.commit()
        return _review_result(row)


async def clinical_review(sc: StepContext, *, article_id: uuid.UUID, version_id: uuid.UUID) -> ReviewStepResult:
    return await _perform_review(sc, article_id=article_id, version_id=version_id, kind="clinical")


async def editorial_review(
    sc: StepContext, *, article_id: uuid.UUID, version_id: uuid.UUID, avoid: AvoidBundle
) -> ReviewStepResult:
    return await _perform_review(sc, article_id=article_id, version_id=version_id, kind="editorial", avoid=avoid)


async def collect_revision_findings(
    db: AsyncSession, *, article_id: uuid.UUID, version_id: uuid.UUID
) -> list[RevisionFinding]:
    await load_article_version(db, article_id=article_id, version_id=version_id)
    findings = []
    for kind in ("fact_check", "clinical", "editorial"):
        row = await latest_review(db, version_id, kind)
        if row is None:
            continue
        if kind == "fact_check":
            for index, claim in enumerate(FactCheckResult.model_validate(row.payload).claims):
                if claim.verification_status in BAD_STATUSES:
                    findings.append(
                        RevisionFinding(
                            finding_id=f"claim:{row.id}:{index}",
                            origin="claim_check",
                            description=claim.claim,
                            location=f"{claim.section_key}#{claim.sentence_index}",
                            recommended_revision=claim.recommended_revision,
                            required=True,
                        )
                    )
        elif kind == "clinical":
            for index, flag in enumerate(ClinicalReview.model_validate(row.payload).flags):
                findings.append(
                    RevisionFinding(
                        finding_id=f"clinical:{row.id}:{index}",
                        origin="clinical_flag",
                        description=flag.message,
                        location=flag.location,
                        recommended_revision=None,
                        required=flag.severity == "BLOCKING",
                    )
                )
        else:
            payload = EditorialReview.model_validate(row.payload)
            for required, changes in ((True, payload.required_changes), (False, payload.optional_changes)):
                for change in changes:
                    findings.append(
                        RevisionFinding(
                            finding_id=f"editorial:{row.id}:{change.id}",
                            origin="editorial_change",
                            description=change.description,
                            location=change.location,
                            recommended_revision=None,
                            required=required,
                        )
                    )
    return findings


async def generate_seo(sc: StepContext, *, article_id: uuid.UUID, version_id: uuid.UUID) -> SeoStepResult:
    from mdcopilot_blog.services.versions import find_step

    async with sc.sessionmaker() as db:
        existing = await find_step(db, VersionSeo, sc.call)
        if existing:
            return SeoStepResult(seo_id=existing.id, version_id=version_id, slug=existing.slug)
        article, version = await load_article_version(db, article_id=article_id, version_id=version_id)
        sources = await load_packet_sources(db, article=article, version=version)
        candidates = [
            LinkCandidate(p.title, p.url)
            for p in (
                await db.scalars(select(ExternalPost).where(ExternalPost.published_at.is_not(None)).limit(30))
            ).all()
        ]
        candidates += [
            LinkCandidate(p.title or "", p.published_url or "")
            for p in (
                await db.scalars(
                    select(Article)
                    .where(Article.status == "PUBLISHED", Article.published_url.is_not(None), Article.id != article_id)
                    .limit(30)
                )
            ).all()
        ]
    numbered = number_sources(sources, preserve_order=True)
    cited = [source for source in numbered if source.marker in version.citation_markers]
    result = await run_seo_specialist(
        sc.gateway,
        ctx=sc.with_ids(article_id=article_id).call,
        brand=sc.brand,
        site_url=sc.config.site_url,
        category=article.category,
        article=article_text(version),
        title=article.title or "",
        excerpt=version.excerpt,
        numbered=cited,
        link_candidates=candidates,
        route_override=sc.config.routes["seo"],
        prompt_version=sc.config.prompt_versions.get(SEO_SPEC.prompt_name),
    )
    package = result.output
    package.seo.external_references = [str(value) for value in resolve_markers(package.seo.external_references, cited)]
    async with sc.sessionmaker() as db:
        await db.execute(select(Article.id).where(Article.id == article_id).with_for_update())
        # Serialise slug allocation across articles; protects the unique partial index.
        await db.execute(text("SELECT pg_advisory_xact_lock(717049661)"))
        existing = await find_step(db, VersionSeo, sc.call)
        if existing:
            return SeoStepResult(seo_id=existing.id, version_id=version_id, slug=existing.slug)
        head = await db.get(Article, article_id)
        slug, suffix = package.seo.slug, 1
        while await db.scalar(
            select(Article.id)
            .where(Article.slug == slug, Article.id != article_id, Article.status.notin_(["REJECTED", "SUPERSEDED"]))
            .limit(1)
        ):
            suffix += 1
            slug = f"{package.seo.slug[:190]}-{suffix}"
        package.seo.slug = slug
        row = VersionSeo(
            id=uuid7(),
            version_id=version_id,
            seo=package.seo.model_dump(mode="json"),
            social=package.social.model_dump(mode="json"),
            slug=slug,
            dbos_workflow_id=sc.call.dbos_workflow_id,
            dbos_step_id=sc.call.dbos_step_id,
        )
        db.add(row)
        if head is None:
            raise LookupError(f"article {article_id} not found")
        if head.current_version_id == version_id:
            head.slug, head.tags, head.category = slug, package.seo.tags, package.seo.category
        await db.commit()
        return SeoStepResult(seo_id=row.id, version_id=version_id, slug=slug)


async def lineage_review(
    db: AsyncSession, version: ArticleVersion, kind: str, model: Any
) -> tuple[LineageReview[Any] | None, frozenset[str]]:
    versions = list(
        (await db.scalars(select(ArticleVersion).where(ArticleVersion.article_id == version.article_id))).all()
    )
    by_id = {v.id: v for v in versions}
    resolved: set[str] = set()
    for version_id in version_chain({v.id: v.parent_version_id for v in versions}, version.id):
        review = await latest_review(db, version_id, kind)
        if review:
            return LineageReview(str(review.id), str(version_id), model.model_validate(review.payload)), frozenset(
                resolved
            )
        for resolution in by_id[version_id].resolutions:
            if kind == "editorial" or resolution["action"] in {"fixed", "removed"}:
                resolved.add(resolution["findingId"])
    return None, frozenset(resolved)


async def _gate_inputs(
    db: AsyncSession,
    *,
    article_id: uuid.UUID,
    version_id: uuid.UUID,
    config: EffectiveConfig,
    brand: BrandProfileValues,
) -> GateInputs:
    from mdcopilot_blog.services.diversity import evaluate_diversity
    from mdcopilot_blog.services.novelty import check_article_duplicate

    article, version = await load_article_version(db, article_id=article_id, version_id=version_id)
    sources = (
        await db.execute(
            select(ArticleSource, LedgerSource)
            .join(LedgerSource, LedgerSource.id == ArticleSource.source_id)
            .where(ArticleSource.version_id == version_id)
        )
    ).all()
    seo = await effective_seo(db, version_id=version_id)
    fact = await latest_review(db, version_id, "fact_check")
    clinical, clinical_resolved = await lineage_review(db, version, "clinical", ClinicalReview)
    editorial, editorial_resolved = await lineage_review(db, version, "editorial", EditorialReview)
    diversity = await evaluate_diversity(db, version_id=version_id, config=config)
    duplicate = await check_article_duplicate(db, version_id=version_id, config=config)
    slug_taken = bool(
        seo
        and await db.scalar(
            select(Article.id)
            .where(
                Article.slug == seo.slug, Article.id != article_id, Article.status.notin_(["REJECTED", "SUPERSEDED"])
            )
            .limit(1)
        )
    )
    return GateInputs(
        version_id=str(version_id),
        sections=article_text(version).sections,
        content_markdown=version.content_markdown,
        title=article.title or version.title_options["operational"],
        title_options=TitleOptions.model_validate(version.title_options),
        pull_quote=version.pull_quote,
        cta=version.cta,
        excerpt=version.excerpt,
        cited_sources=tuple(
            CitedSource(str(source.id), link.marker, source.tier, source.text_snapshot)
            for link, source in sources
            if link.marker in version.citation_markers
        ),
        seo=SEOMetadata.model_validate(seo.seo) if seo else None,
        social=SocialCopy.model_validate(seo.social) if seo and seo.social else None,
        slug_taken=slug_taken,
        fact_check=FactCheckResult.model_validate(fact.payload) if fact else None,
        clinical=clinical,
        clinical_resolved=clinical_resolved,
        editorial=editorial,
        editorial_resolved=editorial_resolved,
        duplicate=duplicate,
        cta_fresh=diversity.cta_fresh,
        diversity_warnings=tuple(diversity.warnings),
        config=config,
        brand=brand,
    )


async def run_quality_gates(
    sc: StepContext, *, article_id: uuid.UUID, version_id: uuid.UUID, run_kind: GateRunKind, fix_pass_used: bool
) -> GateStepResult:
    from mdcopilot_blog.services.diversity import record_version_features

    await record_version_features(sc, version_id=version_id)
    async with sc.sessionmaker() as db:
        await db.execute(select(Article.id).where(Article.id == article_id).with_for_update())
        existing = await _existing(db, sc, "quality_gate")
        if existing:
            report = GateReport.model_validate(existing.payload)
            return GateStepResult(
                review_id=existing.id,
                version_id=version_id,
                report=report,
                decision=decide_fix_pass(report, fix_pass_used=fix_pass_used),
            )
        inputs = await _gate_inputs(db, article_id=article_id, version_id=version_id, config=sc.config, brand=sc.brand)
        report = evaluate_gates(inputs, run_kind=run_kind)
        row = _review(
            sc,
            article_id,
            version_id,
            "quality_gate",
            "PASSED" if report.passed else "FAILED",
            report,
            gate_run_kind=run_kind.value,
        )
        db.add(row)
        await db.commit()
        return GateStepResult(
            review_id=row.id,
            version_id=version_id,
            report=report,
            decision=decide_fix_pass(report, fix_pass_used=fix_pass_used),
        )


async def run_deterministic_gates(
    db: AsyncSession,
    *,
    article_id: uuid.UUID,
    version_id: uuid.UUID,
    config: EffectiveConfig,
    brand: BrandProfileValues,
) -> GateReport:
    inputs = await _gate_inputs(db, article_id=article_id, version_id=version_id, config=config, brand=brand)
    report = evaluate_gates(inputs, run_kind=GateRunKind.DETERMINISTIC)
    db.add(
        _review(
            None,
            article_id,
            version_id,
            "quality_gate",
            "PASSED" if report.passed else "FAILED",
            report,
            gate_run_kind="deterministic",
        )
    )
    await db.flush()
    return report
