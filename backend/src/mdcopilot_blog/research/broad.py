"""Durable broad research: independent collection, ledger retrieval and synthesis."""

import asyncio
import uuid
from collections.abc import Sequence
from datetime import datetime
from time import perf_counter

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.agents.common import number_sources, order_sources, resolve_markers
from mdcopilot_blog.agents.research_analyst import MAX_HINTS, SearchHint, build_variables, run_research_analyst
from mdcopilot_blog.db.models import (
    ContentPillar,
    DiscoveryTheme,
    FindingSource,
    LedgerSource,
    ResearchFindingRecord,
    ResearchRun,
    SourceFeed,
)
from mdcopilot_blog.domain.claim_rules import DraftFinding, EvidenceSource, apply_claim_rules
from mdcopilot_blog.domain.contracts import PillarKey, SourceType
from mdcopilot_blog.domain.enums import AccessMode, DiscoveredVia, ResearchRunKind, ResearchRunStatus
from mdcopilot_blog.domain.errors import InsufficientEvidence
from mdcopilot_blog.domain.query_plan import plan_broad_queries
from mdcopilot_blog.domain.tiers import keyword_set
from mdcopilot_blog.research.catalog import load_domain_rules, load_feed_specs, load_pillar, load_theme_states
from mdcopilot_blog.research.collectors import collect_feed
from mdcopilot_blog.research.environment import open_environment
from mdcopilot_blog.research.ledger import (
    StageTimer,
    load_existing,
    merge_signals,
    retrieve,
    select_candidates,
    upsert_sources,
)
from mdcopilot_blog.research.runs import (
    error_payload,
    get_research_run,
    mark_run,
    merged,
    open_research_run,
    query_status_counts,
)
from mdcopilot_blog.research.search import outcome_signals, query_json, run_search_queries
from mdcopilot_blog.research.signals import Signal, in_window
from mdcopilot_blog.services.config import local_date
from mdcopilot_blog.services.step_context import StepContext

MAX_ANALYST_SOURCES = 40


class GatherSignalsResult(BaseModel):
    research_run_id: uuid.UUID
    signal_count: int
    queries_ok: int
    queries_failed: int
    themes_covered: list[str]


class BuildLedgerResult(BaseModel):
    research_run_id: uuid.UUID
    sources_total: int
    sources_new: int
    sources_blocked: int
    dated_sources: int
    tier12_sources: int


class SynthesizeResult(BaseModel):
    research_run_id: uuid.UUID
    finding_count: int


def broad_keywords(pillar: ContentPillar | None, theme_names: Sequence[str]) -> frozenset[str]:
    return keyword_set(([pillar.name, *pillar.topics] if pillar else []) + list(theme_names))


def search_hints(run: ResearchRun) -> list[SearchHint]:
    signals = [s for s in run.signals if s.get("discoveredVia") == "search"]
    hints: list[SearchHint] = []
    seen: set[str] = set()
    offset = 0
    for query in run.queries:
        size = int(query.get("sourceCount", 0))
        group = signals[offset : offset + size]
        offset += size
        excerpt = group[0].get("answerExcerpt") if group else None
        if query.get("status") == "ok" and isinstance(excerpt, str) and excerpt and excerpt not in seen:
            hints.append(SearchHint(query=str(query["text"]), excerpt=excerpt))
            seen.add(excerpt)
    return hints[:MAX_HINTS]


async def gather_signals(sc: StepContext, *, pillar_key: PillarKey | None) -> GatherSignalsResult:
    if sc.call.run_id is None:
        raise ValueError("gather_signals needs sc.call.run_id")
    now, cfg = sc.now(), sc.config.research
    handle = await open_research_run(
        sc.sessionmaker,
        call=sc.call,
        run_id=sc.call.run_id,
        kind=ResearchRunKind.BROAD,
        pillar_key=pillar_key.value if pillar_key else None,
        window_days=cfg.window_days,
        article_id=None,
        now=now,
    )
    try:
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, handle.id)
            if "feedItems" in run.counts:
                ok, failed = query_status_counts(run)
                return GatherSignalsResult(
                    research_run_id=run.id,
                    signal_count=len(run.signals),
                    queries_ok=ok,
                    queries_failed=failed,
                    themes_covered=run.themes_covered,
                )
            feeds = await load_feed_specs(db)
            themes = await load_theme_states(db)
        planned = plan_broad_queries(
            themes,
            pillar_key=pillar_key.value if pillar_key else None,
            today=local_date(now, sc.config.schedule.timezone),
            broad_queries=cfg.broad_queries,
            pillar_queries=cfg.pillar_queries,
        )
        start = perf_counter()
        async with open_environment(sc) as env:
            async with asyncio.TaskGroup() as group:
                feed_tasks = [
                    group.create_task(collect_feed(env, feed, now=now, window_days=cfg.window_days)) for feed in feeds
                ]
                search_task = group.create_task(
                    run_search_queries(
                        sc, env, planned, mode="broad", recency_days=cfg.window_days, allowed_domains=(), ctx=sc.call
                    )
                )
            feed_results = [task.result() for task in feed_tasks]
            outcomes = search_task.result()
        feed_signals = [signal for result in feed_results for signal in result.signals]
        query_signals = [outcome_signals(result, discovered_via=DiscoveredVia.SEARCH) for result in outcomes]
        covered = list(dict.fromkeys(o.planned.theme_key for o in outcomes if o.status == "ok" and o.planned.theme_key))
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, handle.id, for_update=True)
            run.signals = [s.to_json() for s in feed_signals + [s for group in query_signals for s in group]]
            run.queries = [
                query_json(o, source_count=len(signals)) for o, signals in zip(outcomes, query_signals, strict=True)
            ]
            run.themes_covered = covered
            run.counts = merged(
                run.counts, feedItems=len(feed_signals), searchResults=sum(len(o.source_urls) for o in outcomes)
            )
            run.phase_latency_ms = merged(run.phase_latency_ms, search=int((perf_counter() - start) * 1000))
            for result in feed_results:
                if not result.fetched or result.feed.id is None:
                    continue
                row = await db.get(SourceFeed, result.feed.id, with_for_update=True)
                if row is None:
                    continue
                row.last_fetched_at, row.state = now, result.new_state
                if result.ok:
                    row.consecutive_failures, row.last_error = 0, None
                    row.last_success_at, row.item_count_last = now, result.items_in_window
                else:
                    row.consecutive_failures += 1
                    row.last_error = (result.error or "feed request failed")[:2000]
                    if row.consecutive_failures >= cfg.feed_disable_after_failures:
                        row.is_enabled = False
                        row.disabled_reason = (
                            f"auto-disabled {now:%Y-%m-%d} after {row.consecutive_failures} consecutive failures"
                        )
            keys = {q.theme_key for q in planned}
            for theme in await db.scalars(select(DiscoveryTheme).where(DiscoveryTheme.key.in_(keys))):
                theme.last_searched_at = now
            ok, failed = query_status_counts(run)
            gathered = GatherSignalsResult(
                research_run_id=run.id,
                signal_count=len(run.signals),
                queries_ok=ok,
                queries_failed=failed,
                themes_covered=covered,
            )
            await db.commit()
        return gathered
    except Exception as exc:
        failure: BaseException = exc
        while isinstance(failure, BaseExceptionGroup) and len(failure.exceptions) == 1:
            failure = failure.exceptions[0]
        await mark_run(
            sc.sessionmaker, handle.id, status=ResearchRunStatus.FAILED, error=error_payload(failure), now=sc.now()
        )
        if failure is not exc:
            raise failure from exc
        raise


async def retrieve_run_sources(
    sc: StepContext, *, research_run_id: uuid.UUID, keywords: frozenset[str]
) -> list[uuid.UUID]:
    async with sc.sessionmaker() as db:
        run = await get_research_run(db, research_run_id)
        feeds = {f.id: f for f in await load_feed_specs(db, enabled_only=False) if f.id is not None}
        rules = await load_domain_rules(db)
        candidates = select_candidates(
            merge_signals([Signal.from_json(s) for s in run.signals]),
            rules=rules,
            feeds=feeds,
            keywords=keywords,
            now=sc.now(),
            window_days=run.window_days,
        )
        existing = await load_existing(db, [c.url_hash for c in candidates])
    start, timer = perf_counter(), StageTimer()
    async with open_environment(sc) as env:
        items = await retrieve(
            env,
            candidates,
            existing=existing,
            keywords=keywords,
            now=sc.now(),
            window_days=run.window_days,
            timer=timer,
        )
    async with sc.sessionmaker() as db:
        # Reattach reused rows before refreshing their snapshots.
        existing = await load_existing(db, [c.url_hash for c in candidates])
        outcomes = await upsert_sources(db, items, existing=existing, research_run_id=research_run_id)
        ids = list(dict.fromkeys(o.source_id for o in outcomes))
        rows = order_sources((await db.scalars(select(LedgerSource).where(LedgerSource.id.in_(ids)))).all())
        run = await get_research_run(db, research_run_id, for_update=True)
        run.source_ids = [str(row.id) for row in rows]
        run.counts = merged(
            run.counts,
            urlsFetched=sum(o.fetched for o in outcomes),
            sourcesNew=sum(o.created for o in outcomes),
            sourcesTotal=len(rows),
            sourcesBlocked=sum(o.fetch_status.value in {"blocked", "robots_disallowed"} for o in outcomes),
        )
        run.phase_latency_ms = merged(
            run.phase_latency_ms, retrieval=int((perf_counter() - start) * 1000), extraction=timer.extraction_ms
        )
        await db.commit()
        return [row.id for row in rows]


async def ledger_stats(
    db: AsyncSession, source_ids: Sequence[uuid.UUID], *, now: datetime, window_days: int, require_window: bool
) -> tuple[int, int]:
    rows = (await db.scalars(select(LedgerSource).where(LedgerSource.id.in_(source_ids)))).all()
    return (
        sum(
            r.published_at is not None
            and (not require_window or in_window(r.published_at, now=now, window_days=window_days))
            for r in rows
        ),
        sum(r.tier <= 2 and r.access_mode in {"full_text", "abstract_only"} for r in rows),
    )


async def require_evidence(
    sc: StepContext,
    research_run_id: uuid.UUID,
    *,
    require_window: bool,
    required_queries: int,
    require_text: bool = False,
) -> tuple[int, int]:
    async with sc.sessionmaker() as db:
        run = await get_research_run(db, research_run_id)
        dated, tier12 = await ledger_stats(
            db,
            [uuid.UUID(x) for x in run.source_ids],
            now=sc.now(),
            window_days=run.window_days,
            require_window=require_window,
        )
        ok, _ = query_status_counts(run)
    if dated < sc.config.research.min_source_count or ok < required_queries or (require_text and tier12 < 1):
        exc = InsufficientEvidence(str(research_run_id), dated, sc.config.research.min_source_count, ok)
        await mark_run(
            sc.sessionmaker,
            research_run_id,
            status=ResearchRunStatus.INSUFFICIENT_EVIDENCE,
            error={
                **error_payload(exc),
                "foundSources": dated,
                "requiredSources": sc.config.research.min_source_count,
                "successfulQueries": ok,
            },
            now=sc.now(),
        )
        raise exc
    return dated, tier12


async def build_ledger(sc: StepContext, *, research_run_id: uuid.UUID) -> BuildLedgerResult:
    try:
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, research_run_id)
            if run.kind != "broad":
                raise ValueError("build_ledger expects a broad research run")
            pillar = await load_pillar(db, run.pillar_key)
            themes = await load_theme_states(db)
            keywords = broad_keywords(pillar, [t.name for t in themes if t.key in run.themes_covered])
        if "sourcesTotal" not in run.counts:
            await retrieve_run_sources(sc, research_run_id=research_run_id, keywords=keywords)
        dated, tier12 = await require_evidence(
            sc, research_run_id, require_window=True, required_queries=sc.config.research.min_successful_queries
        )
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, research_run_id)
            return BuildLedgerResult(
                research_run_id=run.id,
                sources_total=run.counts["sourcesTotal"],
                sources_new=run.counts["sourcesNew"],
                sources_blocked=run.counts["sourcesBlocked"],
                dated_sources=dated,
                tier12_sources=tier12,
            )
    except InsufficientEvidence:
        raise
    except Exception as exc:
        await mark_run(
            sc.sessionmaker, research_run_id, status=ResearchRunStatus.FAILED, error=error_payload(exc), now=sc.now()
        )
        raise


async def synthesize_research(sc: StepContext, *, research_run_id: uuid.UUID) -> SynthesizeResult:
    try:
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, research_run_id)
            if run.kind != "broad":
                raise ValueError("synthesize_research expects a broad research run")
            count = await db.scalar(
                select(func.count())
                .select_from(ResearchFindingRecord)
                .where(ResearchFindingRecord.research_run_id == run.id)
            )
            if count or "findings" in run.counts:
                return SynthesizeResult(research_run_id=run.id, finding_count=count or 0)
            rows_by_id = {
                str(r.id): r
                for r in await db.scalars(
                    select(LedgerSource).where(LedgerSource.id.in_([uuid.UUID(x) for x in run.source_ids]))
                )
            }
            rows = [rows_by_id[x] for x in run.source_ids if x in rows_by_id][:MAX_ANALYST_SOURCES]
            pillar = await load_pillar(db, run.pillar_key)
        numbered = number_sources(rows, preserve_order=True)
        start = perf_counter()
        result = await run_research_analyst(
            sc.gateway,
            ctx=sc.call,
            numbered=numbered,
            hints=search_hints(run),
            variables=build_variables(
                pillar_name=pillar.name if pillar else None,
                pillar_topics=pillar.topics if pillar else [],
                window_days=run.window_days,
                today=local_date(sc.now(), sc.config.schedule.timezone),
            ),
            route_override=sc.config.routes["research"],
            prompt_version=sc.config.prompt_versions.get("research/synthesize"),
        )
        evidence = {
            r.id: EvidenceSource(
                r.id, r.tier, AccessMode(r.access_mode), r.published_at, SourceType(r.source_type), r.is_preprint
            )
            for r in rows
        }
        drafts = [
            DraftFinding(
                claim=f.claim,
                evidence=f.evidence,
                confidence=f.confidence,
                category=f.category,
                claim_type=f.claim_type,
                importance=f.importance,
                self_reported=f.self_reported,
                source_ids=tuple(resolve_markers(f.markers, numbered)),
            )
            for f in result.output.findings
        ]
        findings = apply_claim_rules(drafts, evidence)
        async with sc.sessionmaker() as db:
            run = await get_research_run(db, research_run_id, for_update=True)
            # The lock makes a recovered concurrent synthesis safe.
            existing_count = await db.scalar(
                select(func.count())
                .select_from(ResearchFindingRecord)
                .where(ResearchFindingRecord.research_run_id == run.id)
            )
            if existing_count:
                return SynthesizeResult(research_run_id=run.id, finding_count=existing_count)
            for position, finding in enumerate(findings):
                row = ResearchFindingRecord(
                    research_run_id=run.id,
                    position=position,
                    claim=finding.claim,
                    evidence=finding.evidence,
                    confidence=finding.confidence,
                    category=finding.category,
                    claim_type=finding.claim_type.value,
                    importance=finding.importance,
                    is_preprint=finding.is_preprint,
                    downgraded_from=finding.downgraded_from,
                )
                db.add(row)
                await db.flush()
                db.add_all(
                    [FindingSource(finding_id=row.id, source_id=source_id) for source_id in set(finding.source_ids)]
                )
            run.counts = merged(run.counts, findings=len(findings))
            run.phase_latency_ms = merged(run.phase_latency_ms, llm=int((perf_counter() - start) * 1000))
            run.phase_latency_ms = merged(
                run.phase_latency_ms,
                total=sum(run.phase_latency_ms.get(k, 0) for k in ("search", "retrieval", "extraction", "llm")),
            )
            run.status = "partial" if query_status_counts(run)[1] else "succeeded"
            run.finished_at, run.error = sc.now(), None
            await db.commit()
        return SynthesizeResult(research_run_id=research_run_id, finding_count=len(findings))
    except Exception as exc:
        await mark_run(
            sc.sessionmaker, research_run_id, status=ResearchRunStatus.FAILED, error=error_payload(exc), now=sc.now()
        )
        raise
