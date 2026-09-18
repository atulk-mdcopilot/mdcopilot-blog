"""Persist immutable version features and enforce editorial diversity."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import (
    Article,
    ArticleSource,
    ArticleVersion,
    ExternalPost,
    LedgerSource,
    Topic,
    VersionEmbedding,
    VersionFeatures,
)
from mdcopilot_blog.domain.config import BrandProfileValues, EffectiveConfig
from mdcopilot_blog.domain.contracts import AvoidBundle, GateResult, RecentArticleRef
from mdcopilot_blog.domain.diversity import (
    count_repeated_phrases,
    extract_keywords,
    normalize_words,
    opening_sentence,
    trigram_jaccard,
)
from mdcopilot_blog.domain.headlines import classify_headline
from mdcopilot_blog.domain.novelty import NON_LIVE_ARTICLE_STATUSES, cosine_similarity
from mdcopilot_blog.domain.text import strip_citation_markers
from mdcopilot_blog.services.step_context import StepContext


class DiversityEvaluation(BaseModel):
    cta_fresh: GateResult
    warnings: list[GateResult]


async def _history(
    db: AsyncSession,
    *,
    exclude_article_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Any:
    stmt = (
        select(Article, ArticleVersion, VersionFeatures)
        .join(ArticleVersion, ArticleVersion.id == Article.current_version_id)
        .join(VersionFeatures, VersionFeatures.version_id == Article.current_version_id)
        .where(Article.status.not_in(NON_LIVE_ARTICLE_STATUSES))
    )
    if exclude_article_id:
        stmt = stmt.where(Article.id != exclude_article_id)
    if since:
        stmt = stmt.where(Article.created_at >= since)
    if until:
        stmt = stmt.where(Article.created_at <= until)
    return (await db.execute(stmt.order_by(Article.created_at.desc(), Article.id.desc()))).all()


async def build_avoid_bundle(
    db: AsyncSession,
    *,
    config: EffectiveConfig,
    brand: BrandProfileValues,
    now: datetime,
    exclude_article_id: uuid.UUID | None = None,
) -> AvoidBundle:
    since = now - timedelta(days=config.diversity.lookback_days)
    rows = await _history(db, exclude_article_id=exclude_article_id, since=since)
    external = (
        await db.scalars(
            select(ExternalPost.title)
            .where(ExternalPost.published_at >= since)
            .order_by(ExternalPost.published_at.desc())
            .limit(30)
        )
    ).all()
    titles = [a.title or v.title_options["operational"] for a, v, _ in rows] + list(external)
    unique, seen = [], set()
    for title in titles:
        key = normalize_words(title)
        if key not in seen:
            unique.append(title)
            seen.add(key)
    return AvoidBundle(
        recent_articles=[
            RecentArticleRef(
                title=a.title or v.title_options["operational"],
                core_argument=f.core_argument,
                opening_sentence=f.opening_sentence,
            )
            for a, v, f in rows[:10]
        ],
        recent_titles=unique[:30],
        recent_openings=[f.opening_sentence for _, _, f in rows[: config.diversity.opening_compare_last]],
        recent_ctas=[v.cta for _, v, _ in rows[: config.diversity.cta_compare_last]],
        recent_primary_sources=list(dict.fromkeys(d for _, _, f in rows for d in f.primary_source_domains)),
        overused_phrases=[
            p
            for p, _ in count_repeated_phrases(
                [strip_citation_markers(v.content_markdown) for _, v, _ in rows],
                min_words=config.diversity.phrase_min_words,
                max_words=config.diversity.phrase_max_words,
                min_count=config.diversity.phrase_min_count,
            )
        ],
        prohibited_language=list(brand.prohibited_language),
    )


async def record_version_features(sc: StepContext, *, version_id: uuid.UUID) -> None:
    async with sc.sessionmaker() as db:
        version = await db.get(ArticleVersion, version_id)
        if version is None:
            raise LookupError(f"version {version_id} not found")
        article = await db.get(Article, version.article_id)
        if article is None:
            raise LookupError("article not found")
        topic = await db.get(Topic, article.topic_id)
        if topic is None:
            raise LookupError("topic not found")
        existing = set(
            (await db.scalars(select(VersionEmbedding.kind).where(VersionEmbedding.version_id == version_id))).all()
        )
        has_features = await db.scalar(select(VersionFeatures.id).where(VersionFeatures.version_id == version_id))
        if has_features and existing >= {"article", "opening", "argument"}:
            return
        source_rows = (
            await db.execute(
                select(ArticleSource, LedgerSource)
                .join(LedgerSource, LedgerSource.id == ArticleSource.source_id)
                .where(ArticleSource.version_id == version_id)
                .order_by(ArticleSource.marker)
            )
        ).all()
    title = article.title or version.title_options["operational"]
    body = strip_citation_markers(version.content_markdown)
    opening = opening_sentence(body)
    domains = list(dict.fromkeys(s.domain for link, s in source_rows if link.is_primary))
    if not domains:
        domains = [s.domain for link, s in source_rows if link.marker == "S1"]
    texts = {"article": title + "\n" + body, "opening": opening, "argument": topic.core_argument}
    missing = [key for key in texts if key not in existing]
    vectors = (
        await sc.gateway.embed([texts[k] for k in missing], ctx=sc.with_ids(article_id=article.id).call)
        if missing
        else []
    )
    if len(vectors) != len(missing) or any(len(v) != 1536 for v in vectors):
        raise ValueError("expected 1536-dimensional embeddings")
    async with sc.sessionmaker() as db:
        await db.execute(
            insert(VersionFeatures)
            .values(
                version_id=version_id,
                opening_sentence=opening,
                headline_pattern=classify_headline(title).value,
                industry_tags=[tag for tag in sc.brand.focus_areas if normalize_words(tag) in normalize_words(body)],
                keywords=extract_keywords(body, limit=10),
                core_argument=topic.core_argument,
                examples=topic.examples,
                primary_source_domains=domains,
                cta_normalized=normalize_words(version.cta),
            )
            .on_conflict_do_nothing(index_elements=["version_id"])
        )
        for kind, vector in zip(missing, vectors, strict=True):
            await db.execute(
                insert(VersionEmbedding)
                .values(
                    version_id=version_id,
                    kind=kind,
                    model=sc.settings.embedding_model,
                    dimensions=1536,
                    embedding=vector,
                )
                .on_conflict_do_nothing(index_elements=["version_id", "kind"])
            )
        await db.commit()


async def evaluate_diversity(
    db: AsyncSession, *, version_id: uuid.UUID, config: EffectiveConfig
) -> DiversityEvaluation:
    version = await db.get(ArticleVersion, version_id)
    if version is None:
        raise LookupError(f"version {version_id} not found")
    article = await db.get(Article, version.article_id)
    if article is None:
        raise LookupError("article not found")
    features = await db.scalar(select(VersionFeatures).where(VersionFeatures.version_id == version_id))
    if features is None:
        raise LookupError(f"version features not recorded for {version_id}")
    others = await _history(db, exclude_article_id=article.id, until=article.created_at)
    cfg = config.diversity
    cta = max(
        (trigram_jaccard(features.cta_normalized, f.cta_normalized) for _, _, f in others[: cfg.cta_compare_last]),
        default=0.0,
    )
    own = await db.scalar(
        select(VersionEmbedding).where(VersionEmbedding.version_id == version_id, VersionEmbedding.kind == "opening")
    )
    ids = [v.id for _, v, _ in others[: cfg.opening_compare_last]]
    opening_vectors = (
        await db.scalars(
            select(VersionEmbedding).where(VersionEmbedding.version_id.in_(ids), VersionEmbedding.kind == "opening")
        )
    ).all()
    opening = (
        max((cosine_similarity(own.embedding, vector.embedding) for vector in opening_vectors), default=0.0)
        if own
        else 0.0
    )
    recent = [(a, v, f) for a, v, f in others if a.created_at >= article.created_at - timedelta(days=7)]
    pattern_count = 1 + sum(f.headline_pattern == features.headline_pattern for _, _, f in recent)
    concentration = max(
        (
            1 + sum(domain in f.primary_source_domains for _, _, f in recent)
            for domain in features.primary_source_domains
        ),
        default=0,
    )
    return DiversityEvaluation(
        cta_fresh=GateResult(
            gate="cta_fresh",
            passed=cta < cfg.cta_similarity_threshold,
            severity="blocking",
            details=f"max CTA similarity {cta:.2f}",
        ),
        warnings=[
            GateResult(
                gate="opening_diversity",
                passed=opening < cfg.opening_similarity_threshold,
                severity="warning",
                details=f"max opening similarity {opening:.2f}",
            ),
            GateResult(
                gate="headline_diversity",
                passed=pattern_count < cfg.headline_pattern_max_7d,
                severity="warning",
                details=f"headline pattern {features.headline_pattern} used {pattern_count} times in 7 days",
            ),
            GateResult(
                gate="source_domain_diversity",
                passed=concentration < cfg.source_domain_max_7d,
                severity="warning",
                details=f"largest primary source domain count: {concentration} in 7 days",
            ),
        ],
    )
