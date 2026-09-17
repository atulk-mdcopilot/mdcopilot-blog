# Research Architecture — MDCopilot Blog Intelligence

Status: Phase 0 proposal, waiting for owner approval
Evidence date: 2026-09-17. Feed URLs, blocking behaviour and extractor timings were measured live from a `python:3.12-slim` container. Revised after independent review.

## Verdict

| Question | Answer |
|---|---|
| 5. What is the fastest reliable web research architecture? | **Feeds and official APIs first** (free, ~3–5 s). **OpenAI web search** covers what feeds miss. Pages are fetched with **direct HTTP + trafilatura**. A **source ledger** records the real URL and publication date of every source. There is no browser in the default stack. |
| 6. Should Gemini Search be primary? | **No, not for now** (see below). Gemini remains the main *reasoning* model: synthesis, ideation, research packet and fact-checking. |
| 7. Where is direct HTTP retrieval used? | By default for everything: feeds, PubMed (including abstracts), the Federal Register API, the FDA AI-device CSV, and every cited page (text and date). |
| 8. Where is browser automation used? | **Nowhere by default.** An optional `browser` Compose profile is reserved for allow-listed, JavaScript-only pages that have no feed or API. It is never used to get past bot walls or paywalls. |
| 9. How is research parallelised? | `asyncio.gather` with separate limits for feeds, searches and page fetches, plus a per-host limit of 1–2. Partial failures don't fail the step as long as coverage thresholds are met. |

### Change from the choice you made: Gemini grounding is not the primary engine

You chose "OpenAI + Gemini only" with Gemini's Google Search grounding as the main engine. The "no extra key" part still holds. What changed is **which** of the two keys does the searching.

The Gemini API Additional Terms (effective 2026-03-23, page updated 2026-04-28) say search-grounded results:
- may be shown only to the end user who submitted the prompt, and only together with the Search Suggestions;
- may not be cached, analysed or learned from;
- may not be modified or mixed with other content;
- may not have their links collected automatically or used to choose pages to crawl.

This pipeline does all of those things: it stores research, passes it to other agents, rewrites it and publishes sources. Google Cloud's Vertex terms (§20(k)/(l), modified 2026-09-16) carry nearly the same limits. The only way around them is written permission from Google. This is an engineering reading of the terms, not legal advice.

**Consequences for the design:**
- Gemini grounding is **not built** in this release; `BLOG_GEMINI_GROUNDING_ENABLED` is reserved for later.
- If counsel approves, or Google grants a waiver, it can be added behind the `WebSearchProvider` interface. At our volume it would be almost free (5k free queries per month).

OpenAI's web-search terms require clearly visible, clickable inline citations when results are shown. We found no restriction on storing or rewriting results. OpenAI's Sharing & Publication Policy **requires** disclosing AI's role in published content, so every article carries inline source links and a mandatory AI-assistance disclosure (ARCHITECTURE §14).

## 0. Approach evaluation (spec §3–§4)

The criteria are the spec's: freshness, source quality, latency, reliability, extraction quality, scalability and cost. **Measured** means we timed it in Docker on 2026-09-17. **Vendor** means the figure is the vendor's claim, and **indep.** means an independent benchmark.

| Approach | Freshness | Source quality | Latency | Reliability | Extraction / dates | Scalability | Cost | Verdict |
|---|---|---|---|---|---|---|---|---|
| Curated RSS/Atom + official APIs (PubMed, Federal Register, FDA CSV) | Minutes–hours | Tier 1/2 by construction | ~3–5 s for 17–21 feeds (measured) | Medium-high: some feeds blocked or malformed, handled per feed | Reliable dates; titles and summaries; PubMed abstracts via `efetch` | High | Free | **Use: primary discovery** |
| OpenAI Responses `web_search` | High | Mixed; allow-listing available (100 domains) | Unpublished per call (the biggest unknown) | Medium: citation quirks with strict JSON, avoided by plain-text calls | Answer text + real URLs; **no dates** | Tier 1: 500 RPM per model | $10 per 1k search actions + search tokens | **Use: primary search** |
| Gemini Google Search grounding | High | Mixed | Unpublished | Redirect URLs; no dates | Text + `vertexaisearch` redirect URIs | Good | ~Free at our volume (5k queries/month) | **Excluded:** terms (above). Revisit with a waiver. |
| Gemini URL context tool | n/a (fetches the URLs given) | = input | Unpublished | Unknown on bot-walled sites | Google-side page text; billed as input tokens | Good | Tokens | **Deferred:** no specific terms clause found; needs the same legal reading. Our own fetcher covers the need. |
| Anthropic `web_search` | High | Mixed | Unpublished | Citations + JSON output together return a 400 | Direct URLs + `page_age` | Good | $10 per 1k + tokens | **Deferred:** optional key; add as a search fallback when a key exists |
| Tavily | High (news topic) | Domain filters (300) | Basic 1.9 s (indep.) | Good | `published_date` is an estimate | Good | $0.008/credit; 1k free per month | **Excluded:** owner decision, no paid search key. Add behind the same interface if OpenAI search quality falls short. |
| Exa | High | Domain filters (1,200) | Instant 0.4 s (indep.) | Good | `publishedDate` is an estimate; text capped at 10k chars | Good | $7 per 1k | **Excluded:** same reason; the second candidate |
| Brave Search API | High | Operators only | Unmeasured | Good | `page_age` | Good | $5 per 1k | **Rejected:** standard plans grant no right to store results |
| Google Custom Search / Serper / Perplexity Search | — | — | — | — | — | — | — | **Rejected:** Google CSE is closed to new customers; Serper has no domain filter; Perplexity caps domains at 20 |
| httpx (HTTP/2) + trafilatura + htmldate | = source | = source | 18–44 ms per page to extract (measured) | Blocked on some Tier-1 sites | F1 0.924; dates matched feeds on 12 of 13 pages | High | Free | **Use** |
| newspaper4k | = source | = source | 103–569 ms per page | Good | Recovered an HHS page that trafilatura cut short | High | Free | **Use as fallback only** (<150 words) |
| readability-lxml | = source | = source | 1–30 ms | Under-extracts | Weaker | High | Free | **Rejected** |
| Jina Reader | = source | = source | 0.5–8 s | Returns challenge pages as HTTP 200 | Good when it works | Rate-limited | Free tier | **Rejected for now:** routing bot-walled pages through a third party is a terms question |
| Firecrawl (self-host) / Crawl4AI | = source | = source | — | No anti-bot handling in self-host | Good | Heavy (AGPL; 1.6 GB image, 4 GB RAM) | Ops cost | **Rejected** |
| Playwright | = source | = source | Seconds per page | Does not reliably pass Cloudflare | Renders JS | ~1 GB image | Ops cost | **Optional profile only** |
| pypdfium2 (PDF) | = source | = source | 0.08–0.12 s for a 67-page FDA PDF (measured) | Good | Good | High | Free (Apache/BSD) | **Use**. PyMuPDF rejected (AGPL); pdfplumber rejected (about 35× slower). |

## 1. Layered design

```text
                   ┌───────────────────────────────────────────────┐
                   │ QueryPlanner (app/research): pillar of the    │
                   │ day + theme rotation + research window        │
                   └───────┬───────────────────┬───────────────────┘
          parallel         │                   │           parallel
     ┌─────────────────────▼───┐   ┌───────────▼──────────────────────┐
     │ SignalCollectors (free) │   │ LLMGateway.search() (paid)       │
     │ RSS/Atom · PubMed       │   │ → OpenAIWebSearchProvider        │
     │ Federal Register        │   │   (app/llm/search; cost-capped,  │
     │ FDA AI-device CSV diff  │   │    recorded, mock-able)          │
     └────────────┬────────────┘   └───────────────┬──────────────────┘
                  └──── candidate URLs + search answers ─┘
                                 │  normalise + dedupe
                   ┌─────────────▼───────────────────────────────┐
                   │ Retriever: httpx HTTP/2, per-host limits,   │
                   │ robots.txt (Protego), SSRF guard, ETags     │
                   └─────────────┬───────────────────────────────┘
                   ┌─────────────▼───────────────────────────────┐
                   │ Extractor: trafilatura (+htmldate)          │
                   │ → newspaper4k if <150 words                 │
                   │ → pypdfium2 for PDFs                        │
                   │ → bot-wall detector → metadata-only source  │
                   └─────────────┬───────────────────────────────┘
                   ┌─────────────▼───────────────────────────────┐
                   │ SourceLedger (blog_sources)                 │
                   │ canonical URL · publisher · tier · type     │
                   │ published_at + date_source · retrieved_at   │
                   │ content hash · text snapshot · access mode  │
                   └─────────────┬───────────────────────────────┘
                   ┌─────────────▼───────────────────────────────┐
                   │ Research Analyst (Gemini, no tools)         │
                   │ typed findings citing ledger ids only       │
                   └─────────────────────────────────────────────┘
```

Only the Research Analyst uses an LLM to read and interpret sources. Collection, retrieval, extraction, dating and tiering are deterministic code: fast, free, testable and replayable.

## 2. Signal collectors (discovery without an LLM)

Feeds live in `blog_source_feeds`: URL, tier, pillar/theme tags, header profile, parser quirks, enabled flag and health. Edits need no deploy. The catalogue below was confirmed live on 2026-09-17 (HTTP 200, valid XML, dated items).

| Group | Feed / API | Notes |
|---|---|---|
| FDA (Tier 1) | `https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml`, plus the `medwatch`, `drugs`, `biologics` and `recalls` feeds | Use an honest User-Agent; a spoofed browser UA gets 404. There is no device feed. |
| FDA AI devices (Tier 1) | CSV `https://www.fda.gov/media/178541/download?attachment` | Weekly conditional GET; compare by submission number |
| CMS (Tier 1) | `https://www.cms.gov/newsroom/rss-feeds` | Malformed: take the link from the href inside `<title>` and the date from `dc:creator/time@datetime` |
| CMS / FDA rules (Tier 1) | `https://www.federalregister.gov/api/v1/documents.json` (filter by agency) | JSON with `publication_date`; prefer its HTML/XML to the PDFs |
| HHS (Tier 1) | `https://www.hhs.gov/rss/news.xml` | Needs the full browser-header profile |
| CDC (Tier 1) | `https://tools.cdc.gov/api/v2/resources/media/132608.rss?max=20` | Always add `?max=20` (the full feed is 1.4 MB) |
| ONC/ASTP (Tier 1) | `https://healthit.gov/blog/feed/` | Low volume |
| AMA (Tier 1) | `https://www.ama-assn.org/rss.xml` | |
| PubMed (Tier 1) | E-utilities `esearch` → `esummary` (metadata) → **`efetch` (`rettype=abstract`, batched PMIDs)** | 3 requests/s without a key, 10 with the free `NCBI_API_KEY`. Send `tool=` and `email=`. The abstract is the text snapshot (`access_mode=abstract_only`). |
| Journals (Tier 1) | JAMA `https://jamanetwork.com/rss/site_3/67.xml` and `.../onlineFirst_67.xml`; Lancet Digital Health `https://www.thelancet.com/rssfeed/landig_online.xml`; npj Digital Medicine `https://www.nature.com/npjdigitalmed.rss`; NEJM AI `https://ai.nejm.org/action/showFeed?jc=ai&type=etoc&feed=rss` | Article pages are bot-walled. Resolve items to **PubMed records (abstracts)** or DOI metadata instead. The NEJM AI feed returns 403 to httpx and stays disabled until verified. |
| Preprints | medRxiv `https://connect.medrxiv.org/medrxiv_xml.php?subject=Health_Informatics`; arXiv `https://rss.arxiv.org/rss/cs.AI` | Labelled as preprints. Their claims count as ANALYSIS unless peer-reviewed. arXiv dates come from the feed's announce date. |
| Trade press (Tier 2) | STAT `https://www.statnews.com/feed/` and `/category/health-tech/feed/`; Fierce Healthcare `https://www.fiercehealthcare.com/rss/xml`; MedCity `https://medcitynews.com/feed/`; Becker's `https://www.beckershospitalreview.com/feed/` | Fierce dates are not RFC 822 (use a dateutil fallback), and Fierce blocks the default httpx User-Agent |
| AI labs (Tier 1 for their own announcements) | OpenAI `https://openai.com/news/rss.xml`; Google `https://blog.google/technology/ai/rss/` and `/technology/health/rss/`; Google Research `https://research.google/blog/rss/`; DeepMind `https://deepmind.google/blog/rss.xml` | Parse large feeds in a worker thread (feedparser is synchronous) |

**Not reachable by direct fetch, so web search covers them:** NIH news (Cloudflare challenge), Healthcare IT News (Cloudflare challenge), Reuters (no RSS; its robots.txt disallows unknown bots, so it is **never fetched**), Anthropic (no feed) and AAMC (no feed).

## 3. Web search (paid; through the gateway)

```python
class WebSearchProvider(Protocol):          # implementations live in app/llm/search/
    name: str
    async def search(self, query: SearchQuery) -> SearchResult: ...
    # SearchResult = answer_text, citations[(url, title, span)], sources[url],
    #                search_actions, usage, latency_ms
```

Research code calls `LLMGateway.search()`. Search spend therefore goes through the same cost cap, concurrency limit, mock-mode guard and `blog_llm_calls` recording as agent calls.

| Implementation | Status | Notes |
|---|---|---|
| `OpenAIWebSearchProvider` | **Built; primary** | Responses API with the `web_search` tool (not the legacy `web_search_preview`). Settings: `tool_choice="required"`, `include=["web_search_call.action.sources"]`, `search_context_size="low"` for broad searches and `"medium"` for deep ones, and **`max_tool_calls` of 1 for broad and 2 for deep**. Verification searches use `filters.allowed_domains` (the Tier-1/2 list, up to 100 domains); discovery searches are unfiltered. **Plain-text output**: no JSON schema in the same call. The provider stores the answer text, `url_citation` annotations, `action.sources` and `tool_usage.web_search.num_requests`. |
| `FixtureSearchProvider` | **Built** | Mock mode; replays recorded responses |
| `AnthropicWebSearchProvider` | Deferred | Added when an Anthropic key exists (direct URLs + `page_age`) |
| `GeminiGroundedSearchProvider` | Deferred | Added only after a legal reading or a waiver |

**No separate structuring call.** A search call returns text and URLs. Those URLs go into the ledger (fetched and dated). The **Research Analyst** then turns ledger text into typed findings, with the search answer text attached only as a hint. Findings may cite **only ledger IDs**, and any URL not in the ledger is rejected in code.

**When a search call fails:**
1. Retry with backoff, for transient errors only.
2. Mark that query failed and continue with the rest.
3. Fail the step with `INSUFFICIENT_EVIDENCE` if coverage drops below `min_successful_queries` or `BLOG_AGENT_MIN_SOURCE_COUNT`. A failed step can be retried, and because every run ends at human review, an outage only delays the article.

## 4. Retriever (direct HTTP)

- **Client:** `httpx.AsyncClient(http2=True, follow_redirects=True)`.
  - Timeouts: 5 s connect, 15 s read.
  - Limits: at most 5 redirects, 5 MB body cap.
  - Per-host concurrency: a semaphore of 1–2 per host, because httpx pools connections without per-host limits.
- **Identity:** an honest User-Agent, `mdcopilot-blog-bot/<version> (+<site>; <contact>)`. Named header profiles (`default`, `browser_like`) are chosen per feed or domain. No TLS-fingerprint spoofing.
- **robots.txt:** parsed with Protego (RFC 9309) and cached 24 h. A 4xx response to robots.txt means fetching is allowed; a 5xx or network error means it is not.
- **SSRF guard:** only `http`/`https`. The host is resolved first, and private, loopback, link-local and metadata IP ranges are rejected, including after redirects.
- **Bot-wall detection:** a 401/403 status, a `cf-mitigated: challenge` header, or a `Just a moment...` title marks the page `blocked`. It is never retried through a browser.
- **Change detection:** conditional GET (ETag / Last-Modified) for feeds; content hashes for pages.

## 5. Extractor

1. HTML goes through `trafilatura.bare_extraction(with_metadata=True, favor_precision=True)`. If that returns fewer than ~150 words, retry with `favor_recall=True`, then with `newspaper4k`.
2. The publication date is the first of these that yields one, recorded in `date_source`:
   1. the feed item or API record;
   2. JSON-LD `datePublished`;
   3. `article:published_time` meta;
   4. `htmldate` (extensive mode).
3. PDFs go through `pypdfium2`.
4. Blocked pages become a **metadata-only source**: title, URL and date from the feed, PubMed or DOI record, with `access_mode=metadata_only`. Such a source may support only "X was published/announced" claims.
5. PubMed abstracts use `access_mode=abstract_only` and may support the claims the abstract states: design, sample, primary results.

## 6. Research runs and theme rotation

The 15 spec §7 discovery themes are seeded into `blog_discovery_themes`, each with query templates and pillar links:
- AI news
- healthcare AI
- physician workflow
- specialist shortages
- access problems
- agentic AI
- clinical AI research
- regulation
- workforce trends
- AI model developments
- digital twins
- clinical reasoning systems
- automation
- burnout
- administrative overload

The rotation for the broad scan (~10 queries a day):
- ~4 queries for the themes linked to the **pillar of the day**;
- ~6 queries for the **least recently searched** other themes.

With 15 themes, every theme is searched at least once every 3 days. Each run records which themes it covered, and the Research page shows coverage.

| Run kind | Trigger | Query plan | Output |
|---|---|---|---|
| **Broad scan** | Daily workflow or "Generate today's blog" | Theme rotation above; research window from settings (default 7 days) | Ledger rows + research digest (typed findings) |
| **Deep research** | Topic selected | 6–8 queries: primary source, original announcement, papers (PubMed), regulatory documents, statistics, expert commentary, counterarguments | Research packet (spec §16): key facts, statistics, primary and supporting sources, counterarguments, industry context, MDCopilot connection, claims needing verification, source references, summary |
| **Verification lookups** | Fact Checker finds an unsupported claim | ≤3 searches restricted to allow-listed domains | New ledger rows linked to the claim check |
| **Regenerate research** | Human action | Deep research again, with the previous sources and angles as an avoid-hint | New packet version; the old one is kept |

Every run writes a `blog_research_runs` row with its queries, themes and per-phase latency (search, retrieval, extraction, LLM, total).

## 7. Source ledger, tiers, claim types

**Ledger rows.** `blog_sources` holds one row per canonical URL. URLs are normalised (scheme and host, tracking parameters stripped), and `url_hash` is unique. Each row records:
- publisher and domain;
- tier (1/2/3, from `blog_source_domains`);
- source type;
- `published_at`, `date_source`, `retrieved_at`;
- content hash, word count and `access_mode`;
- a text snapshot. The snapshot is **for internal verification only and is never published**.

Relevance is deterministic, combining pillar/theme keyword overlap, recency decay and tier weight.

**Tiers (spec §11)**

| Tier | Sources |
|---|---|
| 1 | Government (FDA, CMS, NIH, CDC, HHS, ONC); peer-reviewed journals and PubMed; medical associations; official company announcements (for their own news only) |
| 2 | Reuters, AP, STAT, Fierce, MedCity, Becker's; reputable tech press; academic institutions |
| 3 | Blogs, opinion pieces, social media, aggregators. Unknown domains default here. |

**Claim rules.** Each finding carries `claim_type` (one of `FACT`, `ANALYSIS`, `OPINION`, `PREDICTION`, `MARKETING_CLAIM`), `importance`, `confidence`, `category` and `source_ids`. These rules are enforced in code:
- A `FACT` must cite a dated source.
- A high-importance `FACT` (statistics, regulatory actions, trial results, workforce numbers) needs at least one Tier-1/2 source that is `full_text` or `abstract_only`. Otherwise it is downgraded or dropped.
- A company's claim about its own product is a `MARKETING_CLAIM` unless an independent source corroborates it.
- Preprint findings are labelled as preprints.

## 8. Parallelism and limits

| Pool | Default | Setting |
|---|---|---|
| Feed and page fetches | 12 concurrent; 1–2 per host | `BLOG_AGENT_MAX_PARALLEL_FETCHES` |
| Search calls | 6 concurrent | `BLOG_AGENT_MAX_PARALLEL_SEARCHES` |
| PubMed | ≤3 req/s (≤10 with a key) | token bucket |
| LLM calls | 4 concurrent per provider | gateway |

**Provider limits.** OpenAI Tier 1 allows 500 RPM and 500k TPM per GPT-5.6 model. Google does not publish Tier 1 limits for Gemini 3.8 Flash, so they are read from AI Studio in Spike S3; Tier 1 also has a spend cap of $10 per rolling 10 minutes. A 429 response is treated as a retryable error.

## 9. Latency (estimate; replaced by measured P50/P90)

| Phase | Typical wall time |
|---|---|
| Feeds + PubMed + Federal Register | 3–5 s |
| Broad search (10 calls, 6 at a time) | 20–60 s (per-call latency is unpublished; the largest unknown) |
| Fetch + extract (~40–60 URLs) | 10–30 s |
| Synthesis (Research Analyst) | 30–40 s |
| Deep research (8 calls) + fetch | 30–90 s |
| Research packet | 35–45 s |

Research accounts for about **2–4.5 minutes** of the run described in ARCHITECTURE §21.

## 10. Failure handling

| Failure | Behaviour |
|---|---|
| One feed down or malformed | Recorded on the feed row (`last_error`, `consecutive_failures`); other feeds continue; the feed is auto-disabled after N consecutive failures and flagged on the Sources page |
| Search provider error or 429 | Retry with backoff → query marked failed → the step succeeds if coverage is met |
| Page blocked | Metadata-only source; never bypassed |
| No publication date | Source kept with `published_at=NULL`; it cannot support a current `FACT` |
| Coverage below minimum | `INSUFFICIENT_EVIDENCE` step failure (retryable); the run page shows what was found |
| Research Analyst output invalid | Validation retries → next model in the route → step failure |

## 11. Mock mode

`BLOG_AGENT_MOCK_MODE=true` swaps in fixture versions of four components:
- `FixtureFeedCollector`;
- `FixtureSearchProvider`;
- `FixtureRetriever`, which serves recorded HTML, PDFs and PubMed XML;
- `FunctionModel` LLM fixtures.

A `record-fixtures` CLI captures these from real runs, inside Docker. In mock mode the gateway refuses to build real provider clients.

## Sources (opened 2026-09-17)

- Gemini grounding and terms: https://ai.google.dev/gemini-api/terms · https://ai.google.dev/gemini-api/docs/google-search · https://ai.google.dev/gemini-api/docs/pricing · https://ai.google.dev/gemini-api/docs/url-context · https://ai.google.dev/gemini-api/docs/structured-output
- OpenAI web search: https://developers.openai.com/api/docs/guides/tools-web-search · https://developers.openai.com/api/docs/pricing · https://community.openai.com/t/structured-output-breaks-annotation/1365140
- Search APIs: Tavily and Exa API references; Brave Search API FAQ (storage rights); Google Custom Search JSON API notice; https://artificialanalysis.ai/articles/search-api
- Retrieval and extraction: https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-enabled-medical-devices · https://www.federalregister.gov/developers/documentation/api/v1 · NCBI E-utilities usage guidelines · Protego (RFC 9309) · trafilatura / htmldate evaluation pages · Playwright Docker docs
