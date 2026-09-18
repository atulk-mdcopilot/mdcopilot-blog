"""Read-only history similarity and duplicate gate."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import (
    Article,
    ArticleSource,
    ArticleVersion,
    ExternalPost,
    LedgerSource,
    Topic,
    VersionEmbedding,
)
from mdcopilot_blog.domain.config import EffectiveConfig, NoveltyConfig
from mdcopilot_blog.domain.contracts import GateResult, NoveltyNeighbour
from mdcopilot_blog.domain.diversity import normalize_words, trigram_jaccard
from mdcopilot_blog.domain.headlines import classify_headline
from mdcopilot_blog.domain.novelty import NON_LIVE_ARTICLE_STATUSES, NoveltySignals, clamp_unit


async def similar_items(
    db: AsyncSession,
    *,
    embedding: Sequence[float],
    space: str = "topic",
    kinds: set[str] | None = None,
    limit: int = 5,
    since: datetime | None = None,
    until: datetime | None = None,
    exclude_article_id: uuid.UUID | None = None,
    exclude_candidate_id: uuid.UUID | None = None,
    exclude_external_slug: str | None = None,
) -> list[NoveltyNeighbour]:
    if len(embedding) != 1536:
        raise ValueError(f"expected 1536 dimensions, got {len(embedding)}")
    kinds = kinds or {"topic", "article", "external_post"}
    found: list[tuple[str, uuid.UUID, str, float]] = []

    def window(statement: Any, column: Any) -> Any:
        if since is not None:
            statement = statement.where(column >= since)
        if until is not None:
            statement = statement.where(column <= until)
        return statement

    if "topic" in kinds:
        column = Topic.embedding if space == "topic" else Topic.argument_embedding
        distance = column.cosine_distance(list(embedding))
        statement = select(Topic.id, Topic.title, distance.label("distance")).where(column.is_not(None))
        statement = window(statement, Topic.created_at)
        if exclude_candidate_id:
            statement = statement.where(Topic.candidate_id.is_distinct_from(exclude_candidate_id))
        if exclude_article_id:
            statement = statement.where(
                Topic.id != select(Article.topic_id).where(Article.id == exclude_article_id).scalar_subquery()
            )
        found.extend(
            ("topic", row.id, row.title, row.distance)
            for row in await db.execute(statement.order_by(distance, Topic.id).limit(limit))
        )
    if "article" in kinds:
        distance = VersionEmbedding.embedding.cosine_distance(list(embedding))
        statement = (
            select(Article.id, Article.title, ArticleVersion.title_options, distance.label("distance"))
            .join(ArticleVersion, ArticleVersion.id == Article.current_version_id)
            .join(VersionEmbedding, VersionEmbedding.version_id == Article.current_version_id)
            .where(
                VersionEmbedding.kind == ("article" if space == "topic" else "argument"),
                Article.status.not_in(NON_LIVE_ARTICLE_STATUSES),
            )
        )
        statement = window(statement, Article.created_at)
        if exclude_article_id:
            statement = statement.where(Article.id != exclude_article_id)
        found.extend(
            ("article", row.id, row.title or row.title_options["operational"], row.distance)
            for row in await db.execute(statement.order_by(distance, Article.id).limit(limit))
        )
    if "external_post" in kinds and space == "topic":
        distance = ExternalPost.embedding.cosine_distance(list(embedding))
        statement = select(ExternalPost.id, ExternalPost.title, distance.label("distance")).where(
            ExternalPost.embedding.is_not(None)
        )
        if exclude_external_slug:
            statement = statement.where(ExternalPost.slug != exclude_external_slug)
        found.extend(
            ("external_post", row.id, row.title, row.distance)
            for row in await db.execute(statement.order_by(distance, ExternalPost.id).limit(limit))
        )
    result = [
        NoveltyNeighbour(kind=kind, ref_id=str(ref), title=title, similarity=round(clamp_unit(1 - float(distance)), 6))
        for kind, ref, title, distance in found
    ]
    return sorted(result, key=lambda n: (-n.similarity, n.kind, n.ref_id))[:limit]


async def nearest_neighbours(
    db: AsyncSession, *, embedding: Sequence[float], limit: int, exclude_article_id: uuid.UUID | None = None
) -> list[NoveltyNeighbour]:
    return await similar_items(db, embedding=embedding, limit=limit, exclude_article_id=exclude_article_id)


async def candidate_signals(
    db: AsyncSession,
    *,
    embedding: Sequence[float],
    argument_embedding: Sequence[float],
    title: str,
    primary_canonical_url: str | None,
    examples: Sequence[str],
    exclude_candidate_id: uuid.UUID | None,
    config: NoveltyConfig,
    now: datetime,
) -> tuple[NoveltySignals, list[NoveltyNeighbour]]:
    since = now - timedelta(days=config.lookback_days)
    neighbours = await similar_items(db, embedding=embedding, since=since, exclude_candidate_id=exclude_candidate_id)
    arguments = await similar_items(
        db,
        embedding=argument_embedding,
        space="argument",
        kinds={"topic", "article"},
        limit=1,
        since=since,
        exclude_candidate_id=exclude_candidate_id,
    )
    statement = select(Topic).where(Topic.created_at >= since)
    if exclude_candidate_id:
        statement = statement.where(Topic.candidate_id.is_distinct_from(exclude_candidate_id))
    topics = (await db.scalars(statement)).all()
    posts = (await db.scalars(select(ExternalPost))).all()
    articles = (
        await db.scalars(
            select(Article).where(Article.created_at >= since, Article.status.not_in(NON_LIVE_ARTICLE_STATUSES))
        )
    ).all()
    titles = [t.title for t in topics] + [p.title for p in posts] + [a.title for a in articles if a.title]
    best = sorted(((round(trigram_jaccard(title, t), 6), t) for t in titles), key=lambda x: (-x[0], x[1]))
    reused = (
        any(
            t.primary_source_url == primary_canonical_url
            and t.created_at >= now - timedelta(days=config.news_reuse_days)
            for t in topics
        )
        if primary_canonical_url
        else False
    )
    if primary_canonical_url and not reused:
        reused = (
            await db.scalar(
                select(Article.id)
                .join(ArticleSource, ArticleSource.version_id == Article.current_version_id)
                .join(LedgerSource, LedgerSource.id == ArticleSource.source_id)
                .where(
                    Article.status.not_in(NON_LIVE_ARTICLE_STATUSES),
                    Article.created_at >= now - timedelta(days=config.news_reuse_days),
                    ArticleSource.is_primary.is_(True),
                    LedgerSource.canonical_url == primary_canonical_url,
                )
                .limit(1)
            )
            is not None
        )
    pattern = classify_headline(title)
    cutoff = now - timedelta(days=config.headline_pattern_window_days)
    uses = (
        1
        + sum(t.headline_pattern == pattern.value and t.created_at >= cutoff for t in topics)
        + sum(
            p.headline_pattern == pattern.value and p.published_at is not None and p.published_at >= cutoff
            for p in posts
        )
    )
    seen_examples = {
        normalize_words(e)
        for t in topics
        if t.created_at >= now - timedelta(days=config.example_reuse_days)
        for e in t.examples
    }
    repeated, seen = [], set()
    for example in examples:
        normalized = normalize_words(example)
        if normalized in seen_examples and normalized not in seen:
            repeated.append(example)
            seen.add(normalized)
    return NoveltySignals(
        neighbours[0] if neighbours else None,
        arguments[0] if arguments else None,
        primary_canonical_url if reused else None,
        best[0] if best else None,
        pattern,
        uses,
        tuple(repeated),
    ), neighbours


async def check_article_duplicate(db: AsyncSession, *, version_id: uuid.UUID, config: EffectiveConfig) -> GateResult:
    version = await db.get(ArticleVersion, version_id)
    if version is None:
        raise LookupError(f"version {version_id} not found")
    article = await db.get(Article, version.article_id)
    if article is None:
        raise LookupError("article not found")
    vectors = {
        v.kind: v.embedding
        for v in await db.scalars(select(VersionEmbedding).where(VersionEmbedding.version_id == version_id))
    }
    if "article" not in vectors or "argument" not in vectors:
        raise LookupError(f"version embeddings not recorded for {version_id}")
    max_similarity = 0.0
    for space, kind, kinds, threshold in (
        ("topic", "article", {"article", "external_post"}, config.novelty.topic_threshold),
        ("argument", "argument", {"article"}, config.novelty.argument_threshold),
    ):
        neighbours = await similar_items(
            db,
            embedding=vectors[kind],
            space=space,
            kinds=kinds,
            limit=1,
            since=article.created_at - timedelta(days=config.novelty.lookback_days),
            until=article.created_at,
            exclude_article_id=article.id,
            exclude_external_slug=article.slug,
        )
        if neighbours:
            neighbour = neighbours[0]
            max_similarity = max(max_similarity, neighbour.similarity)
            if neighbour.similarity >= threshold:
                return GateResult(
                    gate="no_duplicate_topic",
                    passed=False,
                    severity="blocking",
                    details=f'{space} similarity {neighbour.similarity:.2f} >= {threshold:.2f} with {neighbour.kind} "{neighbour.title}" ({neighbour.ref_id})',
                )
    return GateResult(
        gate="no_duplicate_topic",
        passed=True,
        severity="blocking",
        details=f"max similarity {max_similarity:.2f} (limit {config.novelty.topic_threshold:.2f})",
    )
