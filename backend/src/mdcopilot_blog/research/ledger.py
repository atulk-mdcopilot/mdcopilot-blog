"""The source ledger: merge, rank, retrieve, upsert."""

import asyncio
import hashlib
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import LedgerSource
from mdcopilot_blog.domain import urls
from mdcopilot_blog.domain.contracts import SourceType
from mdcopilot_blog.domain.enums import AccessMode, DateSource, DiscoveredVia, FetchStatus
from mdcopilot_blog.domain.text import count_words
from mdcopilot_blog.domain.tiers import Classification, DomainRule, classify_source, relevance_score, resolve_publisher
from mdcopilot_blog.research.environment import ResearchEnvironment
from mdcopilot_blog.research.extract import extract_html, extract_pdf, looks_like_html, looks_like_pdf
from mdcopilot_blog.research.retriever import fetch
from mdcopilot_blog.research.signals import FeedSpec, Signal, in_window

MAX_LEDGER_CANDIDATES = 40
REFETCH_AFTER = timedelta(hours=24)

DISCOVERY_PRIORITY: dict[DiscoveredVia, int] = {
    DiscoveredVia.PUBMED: 0,
    DiscoveredVia.FEED: 1,
    DiscoveredVia.FEDERAL_REGISTER: 2,
    DiscoveredVia.FDA_CSV: 3,
    DiscoveredVia.SEARCH: 4,
    DiscoveredVia.DEEP_SEARCH: 4,
    DiscoveredVia.VERIFICATION: 4,
}


@dataclass
class StageTimer:
    extraction_ms: int = 0


@dataclass(frozen=True)
class Candidate:
    signal: Signal
    canonical_url: str
    url_hash: str
    classification: Classification
    pmid: str | None
    pre_score: float


@dataclass(frozen=True)
class SourceDraft:
    url: str
    canonical_url: str
    url_hash: str
    title: str
    publisher: str
    domain: str
    source_type: SourceType
    tier: int
    published_at: datetime | None
    date_source: DateSource
    retrieved_at: datetime
    access_mode: AccessMode
    fetch_status: FetchStatus
    http_status: int | None
    content_hash: str | None
    word_count: int
    text_snapshot: str | None
    is_preprint: bool
    external_ids: dict[str, str]
    discovered_via: DiscoveredVia
    relevance_score: float
    fetched: bool


@dataclass(frozen=True)
class Reused:
    source_id: uuid.UUID
    url_hash: str


@dataclass(frozen=True)
class UpsertOutcome:
    source_id: uuid.UUID
    created: bool
    refreshed: bool
    fetched: bool
    fetch_status: FetchStatus


def merge_signals(signals: Sequence[Signal]) -> list[Signal]:
    groups: dict[str, list[tuple[int, Signal]]] = {}
    order: list[str] = []
    for index, signal in enumerate(signals):
        try:
            canonical = urls.canonicalize_url(signal.url)
        except urls.InvalidUrl:
            continue
        if canonical not in groups:
            groups[canonical] = []
            order.append(canonical)
        groups[canonical].append((index, signal))
    merged: list[Signal] = []
    for canonical in order:
        members = sorted(
            groups[canonical], key=lambda pair: (DISCOVERY_PRIORITY.get(pair[1].discovered_via, 99), pair[0])
        )
        representative = members[0][1]
        title = representative.title
        if title == representative.url:
            for _, candidate in members:
                if candidate.title != candidate.url:
                    title = candidate.title
                    break
        published_at = representative.published_at
        date_source = representative.date_source
        if published_at is None:
            for _, candidate in members:
                if candidate.published_at is not None:
                    published_at = candidate.published_at
                    date_source = candidate.date_source
                    break
        external_ids: dict[str, str] = {}
        for _, candidate in reversed(members):
            external_ids.update(dict(candidate.external_ids))
        answer_excerpt = next(
            (member.answer_excerpt for _, member in members if member.answer_excerpt is not None), None
        )
        merged.append(
            Signal(
                url=representative.url,
                title=title,
                published_at=published_at,
                date_source=date_source,
                discovered_via=representative.discovered_via,
                feed_id=representative.feed_id,
                external_ids=external_ids,
                answer_excerpt=answer_excerpt,
            )
        )
    return merged


def select_candidates(
    signals: Sequence[Signal],
    *,
    rules: Mapping[str, DomainRule],
    feeds: Mapping[uuid.UUID, FeedSpec],
    keywords: frozenset[str],
    now: datetime,
    window_days: int,
    limit: int = MAX_LEDGER_CANDIDATES,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for signal in merge_signals(signals):
        feed = feeds.get(signal.feed_id) if signal.feed_id is not None else None
        classification = classify_source(signal.url, rules=rules, feed=feed.hint() if feed else None)
        pmid = dict(signal.external_ids).get("pmid") or None
        if pmid is None:
            pmid = _pmid_from_url(signal.url)
        if signal.published_at is not None and not in_window(signal.published_at, now=now, window_days=window_days):
            continue
        pre_score = relevance_score(
            text=signal.title,
            keywords=keywords,
            published_at=signal.published_at,
            now=now,
            window_days=window_days,
            tier=classification.tier,
        )
        candidates.append(
            Candidate(
                signal=signal,
                canonical_url=urls.canonicalize_url(signal.url),
                url_hash=urls.url_hash(urls.canonicalize_url(signal.url)),
                classification=classification,
                pmid=pmid,
                pre_score=pre_score,
            )
        )
    candidates.sort(key=lambda candidate: candidate.pre_score, reverse=True)
    return candidates[:limit]


def _pmid_from_url(url: str) -> str | None:
    from mdcopilot_blog.research.collectors.pubmed import pmid_from_url

    return pmid_from_url(url)


def needs_retrieval(existing: LedgerSource | None, *, now: datetime) -> bool:
    if existing is None:
        return True
    if existing.snapshot_purged_at is not None:
        return True
    if existing.access_mode in (AccessMode.FULL_TEXT.value, AccessMode.ABSTRACT_ONLY.value):
        return False
    return now - existing.retrieved_at >= REFETCH_AFTER


async def load_existing(db: AsyncSession, hashes: Iterable[str]) -> dict[str, LedgerSource]:
    hash_list = list(hashes)
    if not hash_list:
        return {}
    rows = (await db.scalars(select(LedgerSource).where(LedgerSource.url_hash.in_(hash_list)))).all()
    return {row.url_hash: row for row in rows}


async def _retrieve_one(
    env: ResearchEnvironment,
    candidate: Candidate,
    *,
    keywords: frozenset[str],
    now: datetime,
    timer: StageTimer | None,
    existing: Mapping[str, LedgerSource],
) -> SourceDraft | Reused:
    signal = candidate.signal
    row = existing.get(candidate.url_hash)
    if row is not None and not needs_retrieval(row, now=now):
        return Reused(source_id=row.id, url_hash=row.url_hash)

    classification = candidate.classification
    text_snapshot: str | None = None
    word_count = 0
    content_hash: str | None = None
    access_mode = AccessMode.METADATA_ONLY
    fetch_status = FetchStatus.NOT_FETCHED
    http_status: int | None = None
    fetched = False
    published_at = signal.published_at
    date_source = signal.date_source
    title = signal.title if signal.title != signal.url else None
    publisher_parts: dict[str, str | None] = {}
    is_preprint = classification.is_preprint
    external_ids = dict(signal.external_ids)

    if candidate.pmid is not None:
        from mdcopilot_blog.research.collectors.pubmed import PubMedClient, PubMedError

        client = PubMedClient(env)
        pmids = [candidate.pmid]
        summary = None
        try:
            needs_summary = published_at is None or title is None
            if needs_summary:
                summaries = await client.esummary(pmids)
                summary = summaries.get(candidate.pmid)
            abstracts = await client.efetch_abstracts(pmids)
        except PubMedError:
            fetch_status = FetchStatus.ERROR
            abstracts = {}
        else:
            fetch_status = FetchStatus.OK
            http_status = 200
            if summary is not None:
                if title is None:
                    title = summary.title
                if published_at is None and summary.published_at is not None:
                    published_at = summary.published_at
                    date_source = DateSource.API
                publisher_parts["journal"] = summary.journal
                is_preprint = is_preprint or summary.is_preprint
                if summary.doi:
                    external_ids["doi"] = summary.doi
        abstract = abstracts.get(candidate.pmid)
        if abstract:
            text_snapshot = abstract
            word_count = count_words(abstract)
            content_hash = hashlib.sha256(abstract.encode("utf-8")).hexdigest()
            access_mode = AccessMode.ABSTRACT_ONLY
        external_ids.setdefault("pmid", candidate.pmid)
    elif classification.fetch_policy == "never" or classification.fetch_policy == "metadata_only":
        fetched = False
    else:
        result = await fetch(env, signal.url, header_profile=classification.header_profile, check_robots=True)
        fetched = True
        fetch_status = result.status
        http_status = result.http_status
        if result.status == FetchStatus.OK:
            body = result.body
            if looks_like_pdf(result.content_type, body):
                started = time.perf_counter()
                extraction = await asyncio.to_thread(extract_pdf, body)
                if timer is not None:
                    timer.extraction_ms += int((time.perf_counter() - started) * 1000)
                text_snapshot, word_count, content_hash = (
                    extraction.text,
                    extraction.word_count,
                    extraction.content_hash,
                )
                access_mode = extraction.access_mode
            elif looks_like_html(result.content_type, body):
                html_text = body.decode("utf-8", errors="replace")
                started = time.perf_counter()
                extraction = await asyncio.to_thread(extract_html, html_text, url=result.final_url, now=now)
                if timer is not None:
                    timer.extraction_ms += int((time.perf_counter() - started) * 1000)
                text_snapshot, word_count, content_hash = (
                    extraction.text,
                    extraction.word_count,
                    extraction.content_hash,
                )
                access_mode = extraction.access_mode
                if extraction.published is not None and published_at is None:
                    published_at = extraction.published.value
                    date_source = extraction.published.source
                if title is None:
                    title = extraction.title
                publisher_parts["sitename"] = extraction.sitename
            else:
                fetch_status = FetchStatus.ERROR

    resolved_title = (title or candidate.canonical_url)[:1000]
    publisher = resolve_publisher(
        rule_publisher=classification.rule_publisher,
        journal=publisher_parts.get("journal"),
        feed_publisher=classification.feed_publisher,
        sitename=publisher_parts.get("sitename"),
        domain=classification.domain,
    )
    if candidate.pmid is not None and publisher_parts.get("journal") is None:
        publisher = publisher or "PubMed"
    score_text = f"{resolved_title} {(text_snapshot or '')[:2000]}"
    return SourceDraft(
        url=signal.url,
        canonical_url=candidate.canonical_url,
        url_hash=candidate.url_hash,
        title=resolved_title,
        publisher=publisher,
        domain=classification.domain,
        source_type=classification.source_type,
        tier=classification.tier,
        published_at=published_at,
        date_source=date_source,
        retrieved_at=now,
        access_mode=access_mode,
        fetch_status=fetch_status,
        http_status=http_status,
        content_hash=content_hash,
        word_count=word_count,
        text_snapshot=text_snapshot,
        is_preprint=is_preprint,
        external_ids=external_ids,
        discovered_via=signal.discovered_via,
        relevance_score=relevance_score(
            text=score_text,
            keywords=keywords,
            published_at=published_at,
            now=now,
            window_days=0 if published_at is None else _window_days_for(env, published_at, now),
            tier=classification.tier,
        ),
        fetched=fetched,
    )


def _window_days_for(env: ResearchEnvironment, published_at: datetime, now: datetime) -> int:

    _ = (env, published_at, now)
    return 7


async def retrieve(
    env: ResearchEnvironment,
    candidates: Sequence[Candidate],
    *,
    existing: Mapping[str, LedgerSource],
    keywords: frozenset[str],
    now: datetime,
    window_days: int,
    timer: StageTimer | None = None,
) -> list[SourceDraft | Reused]:
    _ = window_days
    tasks = [
        _retrieve_one(env, candidate, keywords=keywords, now=now, timer=timer, existing=existing)
        for candidate in candidates
    ]
    return list(await asyncio.gather(*tasks))


async def upsert_sources(
    db: AsyncSession,
    items: Sequence[SourceDraft | Reused],
    *,
    existing: Mapping[str, LedgerSource],
    research_run_id: uuid.UUID,
) -> list[UpsertOutcome]:
    outcomes: list[UpsertOutcome] = []
    for item in items:
        if isinstance(item, Reused):
            row = existing.get(item.url_hash)
            outcomes.append(
                UpsertOutcome(
                    source_id=item.source_id,
                    created=False,
                    refreshed=False,
                    fetched=False,
                    fetch_status=FetchStatus(row.fetch_status) if row is not None else FetchStatus.NOT_FETCHED,
                )
            )
            continue
        row = existing.get(item.url_hash)
        if row is None:
            statement = (
                insert(LedgerSource)
                .values(
                    url=item.url,
                    canonical_url=item.canonical_url,
                    url_hash=item.url_hash,
                    title=item.title,
                    publisher=item.publisher,
                    domain=item.domain,
                    source_type=item.source_type.value,
                    tier=item.tier,
                    published_at=item.published_at,
                    date_source=item.date_source.value,
                    retrieved_at=item.retrieved_at,
                    access_mode=item.access_mode.value,
                    fetch_status=item.fetch_status.value,
                    http_status=item.http_status,
                    content_hash=item.content_hash,
                    word_count=item.word_count,
                    text_snapshot=item.text_snapshot,
                    is_preprint=item.is_preprint,
                    external_ids=item.external_ids,
                    discovered_via=item.discovered_via.value,
                    first_research_run_id=research_run_id,
                    relevance_score=item.relevance_score,
                )
                .on_conflict_do_nothing(index_elements=["url_hash"])
                .returning(LedgerSource.id)
            )
            result = await db.execute(statement)
            source_id = result.scalar_one_or_none()
            if source_id is None:
                source_id = await db.scalar(select(LedgerSource.id).where(LedgerSource.url_hash == item.url_hash))
            outcomes.append(
                UpsertOutcome(
                    source_id=source_id,
                    created=True,
                    refreshed=False,
                    fetched=item.fetched,
                    fetch_status=item.fetch_status,
                )
            )
            continue
        if item.text_snapshot is not None:
            row.text_snapshot = item.text_snapshot
            row.snapshot_purged_at = None
            row.content_hash = item.content_hash
            row.word_count = item.word_count
            row.access_mode = item.access_mode.value
        row.fetch_status = item.fetch_status.value
        row.http_status = item.http_status
        row.retrieved_at = item.retrieved_at
        if row.published_at is None and item.published_at is not None:
            row.published_at = item.published_at
            row.date_source = item.date_source.value
        merged_ids = dict(item.external_ids)
        merged_ids.update({key: value for key, value in (row.external_ids or {}).items() if value})
        row.external_ids = merged_ids
        outcomes.append(
            UpsertOutcome(
                source_id=row.id,
                created=False,
                refreshed=True,
                fetched=item.fetched,
                fetch_status=FetchStatus(row.fetch_status),
            )
        )
    await db.flush()
    return outcomes
