"""Focused source discovery and bounded allow-listed verification."""

import uuid
from collections.abc import Collection, Mapping, Sequence
from time import perf_counter
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from mdcopilot_blog.agents.common import PromptSource, order_sources
from mdcopilot_blog.db.models import Article, LedgerSource, TopicCandidateRecord
from mdcopilot_blog.domain.enums import DiscoveredVia, ResearchRunKind, ResearchRunStatus
from mdcopilot_blog.domain.errors import InsufficientEvidence
from mdcopilot_blog.domain.query_plan import PlannedQuery, plan_deep_queries
from mdcopilot_blog.domain.tiers import keyword_set
from mdcopilot_blog.domain.urls import canonicalize_url, host_of
from mdcopilot_blog.research.broad import require_evidence, retrieve_run_sources
from mdcopilot_blog.research.catalog import load_domain_rules, load_pillar
from mdcopilot_blog.research.environment import open_environment
from mdcopilot_blog.research.runs import (
    error_payload,
    get_research_run,
    mark_run,
    merged,
    open_research_run,
    query_status_counts,
)
from mdcopilot_blog.research.search import outcome_signals, query_json, run_search_queries
from mdcopilot_blog.services.config import local_date
from mdcopilot_blog.services.step_context import StepContext

MAX_PACKET_SOURCES = 20


class DeepResearchResult(BaseModel):
    research_run_id: uuid.UUID
    source_ids: list[uuid.UUID]


class VerificationResult(BaseModel):
    research_run_id: uuid.UUID | None
    source_ids_by_query: dict[int, list[uuid.UUID]]


def compose_packet_sources(
    *,
    new_ids: Sequence[uuid.UUID],
    candidate_ids: Sequence[uuid.UUID],
    primary_id: uuid.UUID | None,
    avoid: Collection[uuid.UUID],
    rows: Mapping[uuid.UUID, PromptSource],
    min_dated: int,
    limit: int = MAX_PACKET_SOURCES,
) -> list[uuid.UUID]:
    pool = list(dict.fromkeys([*new_ids, *candidate_ids]))
    pool = [x for x in pool if x in rows]
    excluded = set(avoid) - {primary_id}
    chosen = ([primary_id] if primary_id is not None and primary_id in rows else []) + [
        x for x in pool if x != primary_id and x not in excluded
    ]
    chosen = chosen[:limit]
    for row in order_sources([rows[x] for x in pool if x in excluded]):
        if len(chosen) >= limit or sum(rows[x].published_at is not None for x in chosen) >= min_dated:
            break
        if row.published_at is not None:
            chosen.append(row.id)
    return [row.id for row in order_sources([rows[x] for x in chosen])]


async def store_search(
    sc: StepContext,
    research_run_id: uuid.UUID,
    planned: Sequence[PlannedQuery],
    *,
    mode: Literal["deep", "verification"],
    article_id: uuid.UUID,
    allowed_domains: Sequence[str] = (),
) -> None:
    start = perf_counter()
    async with open_environment(sc) as env:
        outcomes = await run_search_queries(
            sc,
            env,
            planned,
            mode=mode,
            recency_days=None,
            allowed_domains=allowed_domains,
            ctx=sc.with_ids(article_id=article_id).call,
        )

    def keep(url: str) -> bool:
        if not allowed_domains:
            return True
        host = host_of(url)
        return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)

    groups = [
        outcome_signals(
            o,
            discovered_via=DiscoveredVia.VERIFICATION if mode == "verification" else DiscoveredVia.DEEP_SEARCH,
            keep=keep,
        )
        for o in outcomes
    ]
    async with sc.sessionmaker() as db:
        run = await get_research_run(db, research_run_id, for_update=True)
        run.signals = [s.to_json() for group in groups for s in group]
        run.queries = [query_json(o, source_count=len(group)) for o, group in zip(outcomes, groups, strict=True)]
        run.counts = merged(run.counts, feedItems=0, searchResults=sum(len(g) for g in groups))
        run.phase_latency_ms = merged(run.phase_latency_ms, search=int((perf_counter() - start) * 1000))
        await db.commit()


async def run_deep_research(
    sc: StepContext, *, article_id: uuid.UUID, candidate_id: uuid.UUID, avoid_source_ids: Sequence[uuid.UUID] = ()
) -> DeepResearchResult:
    async with sc.sessionmaker() as db:
        article = await db.get(Article, article_id)
        candidate = await db.get(TopicCandidateRecord, candidate_id)
        if article is None or candidate is None:
            raise LookupError("article or candidate not found")
        if article.candidate_id != candidate_id:
            raise ValueError("candidate does not belong to article")
        pillar = await load_pillar(db, candidate.pillar_key)
    handle = await open_research_run(
        sc.sessionmaker,
        call=sc.with_ids(article_id=article_id).call,
        run_id=article.run_id,
        kind=ResearchRunKind.DEEP,
        pillar_key=candidate.pillar_key,
        window_days=sc.config.research.window_days,
        article_id=article_id,
        now=sc.now(),
    )
    try:
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, handle.id)
            if run.status in {"succeeded", "partial"}:
                return DeepResearchResult(research_run_id=run.id, source_ids=run.source_ids)
            if run.status == "insufficient_evidence" and run.error:
                raise InsufficientEvidence(
                    str(run.id), run.error["foundSources"], run.error["requiredSources"], run.error["successfulQueries"]
                )
        planned = plan_deep_queries(
            title=candidate.title,
            thesis=candidate.thesis,
            pillar_name=pillar.name if pillar else None,
            today=local_date(sc.now(), sc.config.schedule.timezone),
            deep_queries=min(sc.config.research.deep_queries, 8),
        )
        await store_search(sc, handle.id, planned, mode="deep", article_id=article_id)
        new_ids = await retrieve_run_sources(
            sc, research_run_id=handle.id, keywords=keyword_set([candidate.title, candidate.thesis, candidate.angle])
        )
        candidate_ids = []
        for value in candidate.source_ids:
            try:
                candidate_ids.append(uuid.UUID(value))
            except ValueError:
                continue
        async with sc.sessionmaker() as db:
            ids = [*new_ids, *candidate_ids] + ([candidate.primary_source_id] if candidate.primary_source_id else [])
            rows = {r.id: r for r in await db.scalars(select(LedgerSource).where(LedgerSource.id.in_(ids)))}
            final = compose_packet_sources(
                new_ids=new_ids,
                candidate_ids=candidate_ids,
                primary_id=candidate.primary_source_id,
                avoid=avoid_source_ids,
                rows=rows,
                min_dated=sc.config.research.min_source_count,
            )
            run = await get_research_run(db, handle.id, for_update=True)
            run.source_ids = [str(x) for x in final]
            run.counts = merged(run.counts, sourcesTotal=len(final))
            run.phase_latency_ms = merged(
                run.phase_latency_ms,
                total=sum(run.phase_latency_ms.get(k, 0) for k in ("search", "retrieval", "extraction")),
            )
            await db.commit()
        await require_evidence(
            sc,
            handle.id,
            require_window=False,
            required_queries=min(len(planned), sc.config.research.min_successful_queries),
            require_text=True,
        )
        await mark_run(
            sc.sessionmaker,
            handle.id,
            status=ResearchRunStatus.PARTIAL if query_status_counts(run)[1] else ResearchRunStatus.SUCCEEDED,
            error=None,
            now=sc.now(),
        )
        return DeepResearchResult(research_run_id=handle.id, source_ids=final)
    except InsufficientEvidence:
        raise
    except Exception as exc:
        await mark_run(
            sc.sessionmaker, handle.id, status=ResearchRunStatus.FAILED, error=error_payload(exc), now=sc.now()
        )
        raise


async def verification_lookup(sc: StepContext, *, article_id: uuid.UUID, queries: Sequence[str]) -> VerificationResult:
    indexed = [(i, q.strip()[:300]) for i, q in enumerate(queries) if q.strip()][
        : sc.config.research.max_verification_searches
    ]
    async with sc.sessionmaker() as db:
        article = await db.get(Article, article_id)
        if article is None:
            raise LookupError(f"article {article_id} not found")
        rules = await load_domain_rules(db)
    allow = sorted(key for key, rule in rules.items() if rule.verification_allowlisted)
    if not indexed or not allow:
        return VerificationResult(research_run_id=None, source_ids_by_query={})
    handle = await open_research_run(
        sc.sessionmaker,
        call=sc.with_ids(article_id=article_id).call,
        run_id=article.run_id,
        kind=ResearchRunKind.VERIFICATION,
        pillar_key=article.pillar_key,
        window_days=sc.config.research.window_days,
        article_id=article_id,
        now=sc.now(),
    )
    try:
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, handle.id)
        if run.status not in {"succeeded", "partial", "failed"}:
            planned = [PlannedQuery(text=q, theme_key=None, facet=None) for _, q in indexed]
            await store_search(
                sc, handle.id, planned, mode="verification", article_id=article_id, allowed_domains=allow
            )
            await retrieve_run_sources(sc, research_run_id=handle.id, keywords=keyword_set([q for _, q in indexed]))
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, handle.id, for_update=True)
            rows = {
                r.canonical_url: r.id
                for r in await db.scalars(
                    select(LedgerSource).where(LedgerSource.id.in_([uuid.UUID(x) for x in run.source_ids]))
                )
            }
            mapping, offset = {}, 0
            for (index, _), query in zip(indexed, run.queries, strict=True):
                count = query.get("sourceCount", 0)
                mapping[index] = list(
                    dict.fromkeys(
                        rows[canonicalize_url(s["url"])]
                        for s in run.signals[offset : offset + count]
                        if canonicalize_url(s["url"]) in rows
                    )
                )
                offset += count
            ok, failed = query_status_counts(run)
            run.status = "failed" if ok == 0 else ("partial" if failed else "succeeded")
            run.error = {"class": "SearchFailed", "message": "all verification searches failed"} if ok == 0 else None
            run.finished_at = sc.now()
            run.phase_latency_ms = merged(
                run.phase_latency_ms,
                total=sum(run.phase_latency_ms.get(k, 0) for k in ("search", "retrieval", "extraction")),
            )
            await db.commit()
        return VerificationResult(research_run_id=handle.id, source_ids_by_query=mapping)
    except Exception as exc:
        await mark_run(
            sc.sessionmaker, handle.id, status=ResearchRunStatus.FAILED, error=error_payload(exc), now=sc.now()
        )
        raise
