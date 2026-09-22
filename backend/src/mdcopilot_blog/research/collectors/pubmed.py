"""PubMed E-utilities client: esearch, esummary, efetch, rate spacing."""

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from mdcopilot_blog.domain import urls
from mdcopilot_blog.domain.enums import DateSource, DiscoveredVia, FetchStatus
from mdcopilot_blog.research.environment import ResearchEnvironment
from mdcopilot_blog.research.retriever import fetch
from mdcopilot_blog.research.signals import (
    MAX_ITEMS_PER_FEED,
    FeedOutcome,
    FeedSpec,
    Signal,
    in_window,
    newest_first,
    plausible,
)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EFETCH_BATCH = 200
DOI_BATCH = 20
PUBMED_TOOL = "mdcopilot-blog"


class PubMedError(Exception):
    """An E-utilities call failed."""


@dataclass(frozen=True)
class PubMedSummary:
    pmid: str
    title: str
    journal: str | None
    published_at: datetime | None
    doi: str | None
    is_preprint: bool


class PubMedClient:
    def __init__(self, env: ResearchEnvironment) -> None:
        self._env = env
        self._last = float("-inf")
        self._lock = asyncio.Lock()

    def _common(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = [("db", "pubmed"), ("tool", PUBMED_TOOL)]
        if self._env.settings.ncbi_contact_email:
            pairs.append(("email", self._env.settings.ncbi_contact_email))
        if self._env.settings.ncbi_api_key is not None:
            pairs.append(("api_key", self._env.settings.ncbi_api_key.get_secret_value()))
        return pairs

    def esearch_url(self, term: str, *, retmax: int, sort: str | None, reldate: int | None) -> str:
        pairs = [
            ("db", "pubmed"),
            ("term", term),
            ("retmode", "json"),
            ("retmax", str(retmax)),
        ]
        if sort:
            pairs.append(("sort", sort))
        pairs.append(("datetype", "pdat"))
        if reldate is not None:
            pairs.append(("reldate", str(reldate)))
        pairs.append(("tool", PUBMED_TOOL))
        if self._env.settings.ncbi_contact_email:
            pairs.append(("email", self._env.settings.ncbi_contact_email))
        if self._env.settings.ncbi_api_key is not None:
            pairs.append(("api_key", self._env.settings.ncbi_api_key.get_secret_value()))
        return str(httpx.URL(f"{EUTILS_BASE}/esearch.fcgi", params=pairs))

    def esummary_url(self, pmids: Sequence[str]) -> str:
        joined = ",".join(sorted(pmids, key=lambda value: int(value)))
        pairs = [("db", "pubmed"), ("id", joined), ("retmode", "json"), *self._common()]
        return str(httpx.URL(f"{EUTILS_BASE}/esummary.fcgi", params=pairs))

    def efetch_url(self, pmids: Sequence[str]) -> str:
        joined = ",".join(sorted(pmids, key=lambda value: int(value)))
        pairs = [
            ("db", "pubmed"),
            ("id", joined),
            ("rettype", "abstract"),
            ("retmode", "xml"),
            *self._common(),
        ]
        return str(httpx.URL(f"{EUTILS_BASE}/efetch.fcgi", params=pairs))

    async def _spaced(self) -> None:
        async with self._lock:
            wait = self._last + self._env.pubmed_min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()

    async def _get(self, url: str, endpoint: str) -> dict[str, Any]:
        await self._spaced()
        result = await fetch(self._env, url, check_robots=False)
        if result.status != FetchStatus.OK:
            raise PubMedError(f"{endpoint}: {result.error}")
        import json

        try:
            payload: dict[str, Any] = json.loads(result.body)
        except json.JSONDecodeError as exc:
            raise PubMedError(f"{endpoint}: unexpected response") from exc
        return payload

    async def esearch(self, term: str, *, retmax: int, sort: str | None, reldate: int | None) -> list[str]:
        data = await self._get(self.esearch_url(term, retmax=retmax, sort=sort, reldate=reldate), "esearch")
        try:
            idlist = data["esearchresult"]["idlist"]
        except (KeyError, TypeError) as exc:
            raise PubMedError("esearch: unexpected response") from exc
        return [str(pmid) for pmid in idlist]

    async def esummary(self, pmids: Sequence[str]) -> dict[str, PubMedSummary]:
        if not pmids:
            return {}
        data = await self._get(self.esummary_url(pmids), "esummary")
        result = data.get("result") or {}
        summaries: dict[str, PubMedSummary] = {}

        for uid in result.get("uids", []):
            record: dict[str, Any] = result.get(uid) or {}
            title = str(record.get("title", "")).strip()
            journal = record.get("fulljournalname") or record.get("source") or None
            published_at: datetime | None = None
            sortpubdate = record.get("sortpubdate")
            if isinstance(sortpubdate, str):
                try:
                    published_at = datetime.strptime(sortpubdate, "%Y/%m/%d %H:%M").replace(
                        tzinfo=__import__("datetime").UTC
                    )
                except ValueError:
                    published_at = None
            if published_at is not None:
                published_at = plausible(published_at, now=self._env.now())
            doi = None
            for article_id in record.get("articleids", []):
                if isinstance(article_id, dict) and article_id.get("idtype") == "doi":
                    doi = str(article_id.get("value") or "")
                    break
            pubtypes = record.get("pubtype", [])
            summaries[str(uid)] = PubMedSummary(
                pmid=str(uid),
                title=title,
                journal=str(journal) if journal else None,
                published_at=published_at,
                doi=doi or None,
                is_preprint="Preprint" in pubtypes if isinstance(pubtypes, list) else False,
            )
        return summaries

    async def efetch_abstracts(self, pmids: Sequence[str]) -> dict[str, str]:
        if not pmids:
            return {}
        abstracts: dict[str, str] = {}
        for start in range(0, len(pmids), EFETCH_BATCH):
            batch = pmids[start : start + EFETCH_BATCH]
            await self._spaced()
            result = await fetch(self._env, self.efetch_url(batch), check_robots=False)
            if result.status != FetchStatus.OK:
                raise PubMedError(f"efetch: {result.error}")
            try:
                root = ET.fromstring(result.body)
            except ET.ParseError as exc:
                raise PubMedError("efetch: unparseable XML") from exc
            for article in root.iter("PubmedArticle"):
                pmid_element = article.find("./MedlineCitation/PMID")
                if pmid_element is None or not (pmid_element.text or "").strip():
                    continue
                pmid = (pmid_element.text or "").strip()
                parts: list[str] = []
                for element in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
                    text = "".join(element.itertext()).strip()
                    if not text:
                        continue
                    label = element.get("Label")
                    parts.append(f"{label}: {text}" if label else text)
                abstract = "\n".join(parts)
                if abstract:
                    abstracts[pmid] = abstract
        return abstracts


async def resolve_dois(
    env: ResearchEnvironment, dois: Sequence[str], *, now: datetime | None = None
) -> list[PubMedSummary]:
    unique: dict[str, str] = {}
    for doi in dois:
        if doi and doi.lower() not in unique:
            unique[doi.lower()] = doi
    client = PubMedClient(env)
    matched: list[PubMedSummary] = []
    spellings = list(unique.values())
    for start in range(0, len(spellings), DOI_BATCH):
        batch = spellings[start : start + DOI_BATCH]
        term = " OR ".join(f"{doi}[doi]" for doi in batch)
        ids = await client.esearch(term, retmax=DOI_BATCH, sort=None, reldate=None)
        if not ids:
            continue
        summaries = await client.esummary(ids)
        by_doi = {summary.doi.lower(): summary for summary in summaries.values() if summary.doi}
        for doi in batch:
            summary = by_doi.get(doi.lower())
            if summary is not None:
                matched.append(summary)
    return matched


async def collect_pubmed_search(
    env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int
) -> FeedOutcome:
    quirks: dict[str, Any] = dict(feed.quirks or {})
    params: Any = quirks.get("query_params") or {}
    term = params.get("term")
    if not isinstance(term, str) or not term:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error="pubmed feed has no term",
            http_status=None,
            not_modified=False,
            new_state=dict(feed.state or {}),
            items_in_window=0,
        )
    retmax = int(str(params.get("retmax", "20")))
    sort: Any = params.get("sort")
    reldate = window_days
    client = PubMedClient(env)
    try:
        ids = await client.esearch(term, retmax=retmax, sort=str(sort) if sort else None, reldate=reldate)
        summaries = await client.esummary(ids)
    except PubMedError as exc:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error=str(exc),
            http_status=None,
            not_modified=False,
            new_state=dict(feed.state or {}),
            items_in_window=0,
        )
    signals: list[Signal] = []
    for pmid, summary in summaries.items():
        signals.append(
            Signal(
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                title=summary.title,
                published_at=summary.published_at,
                date_source=DateSource.API if summary.published_at else DateSource.NONE,
                discovered_via=DiscoveredVia.PUBMED,
                feed_id=feed.id,
                external_ids={"pmid": pmid, **({"doi": summary.doi} if summary.doi else {})},
            )
        )
    kept = [signal for signal in signals if in_window(signal.published_at, now=now, window_days=window_days)]
    ordered = newest_first(kept, limit=MAX_ITEMS_PER_FEED)
    return FeedOutcome(
        feed=feed,
        ok=True,
        fetched=True,
        signals=ordered,
        error=None,
        http_status=None,
        not_modified=False,
        new_state=dict(feed.state or {}),
        items_in_window=len(kept),
    )


def pmid_from_url(url: str) -> str | None:
    try:
        host = urls.host_of(url)
    except urls.InvalidUrl:
        return None
    if host != "pubmed.ncbi.nlm.nih.gov":
        return None
    path = url.split("?")[0]
    match = re.match(r"^/(\d+)/?$", path[len("https://pubmed.ncbi.nlm.nih.gov") :] if path.startswith("http") else path)
    if match:
        return match.group(1)

    path = urlsplit(url).path
    match = re.match(r"^/(\d+)/?$", path)
    return match.group(1) if match else None
