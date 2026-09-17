# Track RES: Research engine — implementation plan

Status: plan for review. Date: 2026-09-17 (revised 2026-09-17 by `plan-fix-RES` to apply the RES cross-check findings; see the appendix "Cross-check findings applied" at the end of this file). Binding: `CONTRACT.md` (revision 3) wins over this plan; the spec wins over this plan.

## Header

**Goal.** Build Phase 2's research engine behind the §5.6 seam `pkg/research/steps.py`: free signal collectors (RSS/Atom, PubMed, Federal Register, FDA AI-device CSV), paid broad/deep/verification search through `LLMGateway.search`, a direct-HTTP retriever (HTTP/2, per-host limits, Protego, SSRF guard, bot-wall detection, conditional GET), an extractor (trafilatura → newspaper4k fallback, JSON-LD/meta/htmldate dates, pypdfium2), a source ledger with tiers and canonical URLs, the Research Analyst agent with claim rules enforced in code, the research/sources/themes API (§4.2, §4.3), the seeded catalogue (feeds, domains, 15 themes), a complete mock fixture set that satisfies the §5.8 RES golden-path invariants, and the `record-fixtures` CLI. RES makes no paid calls (§9 rule 1).

**Spec sections implemented.** RESEARCH_ARCHITECTURE §1–§8, §10, §11 (whole document except the browser profile, Gemini grounding and Anthropic search, which stay unbuilt); ARCHITECTURE §5.1 D2–D4, §5.2 P1 (research half), §7 Research Analyst row, §7.1 prompt rendering with `<untrusted_source>` blocks, §12 `ResearchSource`/`ResearchFinding`, §13 Research and Sources pages (API side), §15 research tables (writes), §16 research/sources/themes routes, §17 SSRF and prompt-injection items, §19 discovery themes; IMPLEMENTATION_PLAN Phase 2 build items "Collectors", "Retriever", "Extraction and ledger", "Research", and acceptance bullets assigned to RES in CONTRACT §10.1.

**Owned files (CONTRACT §2.2 RES, copied).**

| Path | Notes |
|---|---|
| `pkg/research/**` | `__init__.py` and `steps.py` stub by FOUND; `record_fixtures.py` stub by FOUND |
| `pkg/agents/research_analyst.py` | |
| `pkg/services/research_runs.py`, `pkg/services/sources.py` | API services |
| `pkg/api/routers/research.py`, `pkg/api/routers/sources.py` | stub by FOUND |
| `pkg/api/schemas_research.py`, `pkg/api/schemas_sources.py` | stub by FOUND |
| `pkg/domain/claim_rules.py`, `pkg/domain/tiers.py`, `pkg/domain/urls.py`, `pkg/domain/query_plan.py` | pure |
| `pkg/db/seed_data/feeds.yaml`, `domains.yaml`, `themes.yaml` | content (§3.4) |
| `backend/prompts/research/**` | |
| `backend/fixtures/mock/llm/research/**` | |
| `backend/fixtures/mock/search/**` except `default.json` | RES adds `broad.json`, `deep.json`, `verification.json` (§5.8 invariants); `default.json` stays FOUND-frozen |
| `backend/fixtures/mock/feeds/**`, `pages/**`, `pdfs/**`, `pubmed/**`, `federal_register/**`, `fda/**` | |
| `backend/fixtures/mock/scenarios/research_*/**` | |
| `backend/tests/research/**` | |
| `docs/blog-agent/plans/phases-2-10/res.md` | this plan (written at `RES.md` as assigned; see open questions) |
| `.superpowers/sdd/phases-2-10/requests/res.md` | `Request:` lines (§2 rules) |

`pkg/` = `backend/src/mdcopilot_blog/`. New modules RES creates under `pkg/research/`: `environment.py`, `fixtures.py`, `retriever.py`, `extract.py`, `signals.py`, `catalog.py`, `search.py`, `ledger.py`, `runs.py`, `broad.py`, `deep.py`, `verification.py`, `feed_health.py`, `collectors/__init__.py`, `collectors/feeds.py`, `collectors/pubmed.py`, `collectors/federal_register.py`, `collectors/fda_csv.py`.

**Extension points consumed (exact names, all from FOUND or Phase 1).**
- Seam signatures and result models in `pkg/research/steps.py` (§5.6): `GatherSignalsResult`, `gather_signals`, `BuildLedgerResult`, `build_ledger`, `SynthesizeResult`, `synthesize_research`, `DeepResearchResult`, `run_deep_research`, `VerificationResult`, `verification_lookup`, `FeedHealthReport`, `roll_up_feed_health`. Signatures are not changed.
- `mdcopilot_blog.services.step_context.StepContext` (`settings`, `config`, `brand`, `sessionmaker`, `gateway`, `prompts`, `call`, `clock`, `with_ids`, `now`).
- `mdcopilot_blog.llm.gateway`: `LLMGateway.run(spec, *, variables, user_prompt, ctx, route_override, prompt_version, output_check)`, `LLMGateway.search(query, *, ctx)`, `AgentSpec` (with `reasoning`), `AgentResult`, `CallContext`, `BudgetExceeded`, `RouteExhausted`, `ProviderNotAvailable`, `ModelFactory`, `LLMGateway.__init__(*, settings, prompts, recorder, model_factory, search_provider)` (tests only).
- `mdcopilot_blog.llm.search.base`: `SearchQuery(text, allowed_domains, max_results, recency_days, mode)`, `SearchResult`. `mdcopilot_blog.llm.search.fixture.FixtureSearchProvider` (roots v2). `mdcopilot_blog.llm.recorder.CallRecorder`. `mdcopilot_blog.llm.mock.MockModelFactory`, `FixtureRegistry.default(scenario)`.
- `mdcopilot_blog.agents.common`: `UNTRUSTED_NOTICE`, `NumberedSource`, `PromptSource`, `order_sources`, `number_sources`, `untrusted_block`, `render_source_list`, `resolve_markers`.
- `mdcopilot_blog.domain.errors`: `InsufficientEvidence(research_run_id, found_sources, required_sources, successful_queries)`, `UnknownCitationMarker`, `OutputRejected`.
- `mdcopilot_blog.domain.enums`: `ResearchRunKind`, `ResearchRunStatus`, `AccessMode`, `DateSource`, `FetchStatus`, `DiscoveredVia`, `FeedKind`, `AgentName`, `Permission`, `Role`, `CallKind`, `CallStatus`, `ArticleStatus`.
- `mdcopilot_blog.domain.contracts`: `Contract`, `Marker`, `UnitScore`, `SourceType`, `ClaimType`, `PillarKey`.
- `mdcopilot_blog.domain.text`: `count_words`, `normalize_for_match`.
- `mdcopilot_blog.domain.config`: `EffectiveConfig`, `ResearchConfig` (`window_days`, `min_source_count`, `min_successful_queries`, `broad_queries`, `pillar_queries`, `deep_queries`, `max_verification_searches`, `feed_disable_after_failures`). `mdcopilot_blog.services.config.load_effective_config`.
- `mdcopilot_blog.db.models`: `DiscoveryTheme`, `SourceFeed`, `SourceDomain`, `ResearchRun`, `LedgerSource`, `ResearchFindingRecord`, `FindingSource`, `ContentPillar`, `BlogRun`, `Article` (read), `TopicCandidateRecord` (read).
- `mdcopilot_blog.db.seed.load_seed_file` (YAML loaders are FOUND's; RES only fills the files).
- API: `mdcopilot_blog.api.schemas.ApiModel`, `Page`; `mdcopilot_blog.api.schemas_common.SourceRefOut`; `mdcopilot_blog.api.deps.SessionDep`, `Principal`, `require_permission`; `mdcopilot_blog.errors.ProblemError`, `VALIDATION_TITLE`; `mdcopilot_blog.services.audit.audit`; `router = APIRouter(tags=[...])` stubs already in `api/app.py::ROUTERS`.
- Settings (§6 and Phase 1): `mock_mode`, `mock_scenario`, `app_version`, `site_url`, `fetch_contact`, `fetch_connect_timeout_seconds`, `fetch_read_timeout_seconds`, `fetch_max_bytes`, `fetch_max_redirects`, `fetch_per_host_limit`, `robots_cache_hours`, `max_parallel_fetches`, `max_parallel_searches`, `ncbi_api_key`, `ncbi_contact_email`, `research_window_days`.
- Test fixtures (§8.1): `settings`, `db_session`, `seeded_db`, `sessionmaker_committing`, `clean_db`, `committed_seed`, `effective_config`, `mock_step_context(agents=…, scenario=…)`, `make_research_graph`, `make_article_graph`, `app`, `client`, `login_as`, `make_user`, `fake_workflow_client`; `backend/tests/api_shapes.json`; `tests/foundation/test_found_imports.py`.
- CLI: `cli.py` `record-fixtures` dispatch to `mdcopilot_blog.research.record_fixtures.main(argv, settings)`.

**Test database and commands.** `BLOG_TEST_DB=mdcopilot_blog_res_test` (reviewers and second processes: `mdcopilot_blog_res_review_test`). Test directory `backend/tests/research/`, basename prefix `test_res_`.

```bash
# one file (TDD red/green)
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/research/<file>.py
# whole track
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/research
# shared load surface (run before reporting any red test as RES's own)
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
# lint/type gate (owned paths)
docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c \
  "ruff check --no-cache src/mdcopilot_blog/research src/mdcopilot_blog/agents/research_analyst.py src/mdcopilot_blog/services/research_runs.py src/mdcopilot_blog/services/sources.py src/mdcopilot_blog/api/routers/research.py src/mdcopilot_blog/api/routers/sources.py src/mdcopilot_blog/api/schemas_research.py src/mdcopilot_blog/api/schemas_sources.py src/mdcopilot_blog/domain/claim_rules.py src/mdcopilot_blog/domain/tiers.py src/mdcopilot_blog/domain/urls.py src/mdcopilot_blog/domain/query_plan.py tests/research && ruff format --check --no-cache src/mdcopilot_blog/research src/mdcopilot_blog/agents/research_analyst.py src/mdcopilot_blog/services/research_runs.py src/mdcopilot_blog/services/sources.py src/mdcopilot_blog/api/routers/research.py src/mdcopilot_blog/api/routers/sources.py src/mdcopilot_blog/api/schemas_research.py src/mdcopilot_blog/api/schemas_sources.py src/mdcopilot_blog/domain/claim_rules.py src/mdcopilot_blog/domain/tiers.py src/mdcopilot_blog/domain/urls.py src/mdcopilot_blog/domain/query_plan.py tests/research && mypy --cache-dir=/tmp/mypy --follow-imports=silent src/mdcopilot_blog/research src/mdcopilot_blog/agents/research_analyst.py src/mdcopilot_blog/services/research_runs.py src/mdcopilot_blog/services/sources.py src/mdcopilot_blog/api/routers/research.py src/mdcopilot_blog/api/routers/sources.py src/mdcopilot_blog/api/schemas_research.py src/mdcopilot_blog/api/schemas_sources.py src/mdcopilot_blog/domain/claim_rules.py src/mdcopilot_blog/domain/tiers.py src/mdcopilot_blog/domain/urls.py src/mdcopilot_blog/domain/query_plan.py"
```
Below, `RES_PYTEST <file>` abbreviates the first command, and `RES_LINT` the last one.

**Owner inputs and fallbacks.**

| Input | Used for | When missing |
|---|---|---|
| `NCBI_API_KEY` | PubMed rate 10 req/s and `api_key=` parameter | 3 req/s spacing (`0.34 s`), no `api_key` parameter. Default suites never need it. |
| `NCBI_CONTACT_EMAIL` | PubMed `email=` parameter | parameter omitted; `tool=mdcopilot-blog` still sent |
| `BLOG_FETCH_CONTACT` | crawler User-Agent contact | UA `mdcopilot-blog-bot/<app_version> (+<site_url>)` without contact |
| Keys + `Live-go: live-broad-scan` | live broad scan acceptance | INT's gate (§9); RES ships the mock tests only and never makes a paid call |
| Gemini content-strategy conversation | refined themes | the 15 spec §7 themes seeded below; editable via `PUT /themes` |

**Verified facts this plan relies on** (throwaway `p2p-plan-res-*` containers, 2026-09-17; pinned versions feedparser 6.0.14, trafilatura 2.2.0, htmldate 1.10.0, newspaper4k 0.9.6, pypdfium2 5.13.0, protego 0.6.2, python-dateutil 2.9.0.post0, httpx 0.28.1 with h2, mypy 2.3.1; FastAPI/pydantic from `mdcopilot-blog-backend:dev`):
1. `trafilatura.bare_extraction(html, url=…, with_metadata=True, favor_precision=True)` returns a `trafilatura.settings.Document` (attributes `text`, `title`, `sitename`, `date`), never a dict unless `as_dict=True` (deprecated); for tiny pages it returns a `Document` whose `text` is short, not `None`.
2. `htmldate.find_date(html, extensive_search=True, original_date=True, outputformat="%Y-%m-%dT%H:%M:%S%z")` returns `"2026-09-15T10:00:00-0400"` when a time zone is known and `"2026-09-11T00:00:00"` (no offset) for a `<time datetime="2026-09-11">` element or a visible "Published September 11, 2026" byline; `None` when nothing is found.
3. `newspaper.Article(url).download(input_html=html)` then `.parse()` gives `.text`, `.title`, `.publish_date` (aware `datetime` from JSON-LD); never call `.nlp()` (DEPS.md).
4. `pypdfium2.PdfDocument(data: bytes)`, `len(pdf)`, `pdf[i].get_textpage().get_text_range()`; invalid data raises `pypdfium2.PdfiumError` (top-level export).
5. `Protego.parse(text).can_fetch(url, user_agent)`; a `User-agent: mdcopilot-blog-bot` group matches the full UA string `mdcopilot-blog-bot/0.1.0 (+https://www.mdcopilot.health)`.
6. CMS feed: feedparser `entry.title` is `<a href="https://www.cms.gov/newsroom/press-releases/…" hreflang="en">Title</a>` (href already absolute), `entry.link` is a URL-encoded copy of the anchor (404), `entry.published` is `"Tue, 09/15/2026 - 10:01"` with `published_parsed=None`, and `entry.time == {"datetime": "2026-09-15T10:01:40-04:00"}`.
7. Fierce: `entry.published == "Sep 16, 2026 5:39pm"`, `published_parsed=None`; `dateutil.parser.parse` gives a naive `2026-09-16 17:39`.
8. JAMA items carry `entry.prism_doi`; medRxiv items carry `entry.dc_identifier == "doi:10.64898/…"` and only `updated_parsed`.
9. FDA AI-device CSV header: `Date of Final Decision,Submission Number,Device,Company,Panel (Lead),Primary Product Code`; dates `MM/DD/YYYY`; response has `Last-Modified`, no `ETag`.
10. E-utilities: `esearch` JSON `esearchresult.idlist`; `esummary` JSON `result.uids` and per-uid `title`, `sortpubdate` (`"2026/09/16 00:00"`), `fulljournalname`, `articleids[{idtype, value}]` (doi), `pubtype`; `efetch` (`rettype=abstract&retmode=xml`) `PubmedArticle/MedlineCitation/PMID` and `…/Article/Abstract/AbstractText` elements with optional `Label`.
11. Federal Register `documents.json` `results[]` with requested `fields[]` `title, abstract, document_number, html_url, publication_date, type, agencies`.
12. Feed catalogue reachability: HHS returns 403 to honest headers and 200 to the `browser_like` profile; npj returns an unparseable 200 to honest headers and 8 dated entries to `browser_like`; Lancet Digital Health and NEJM AI return 403 to both profiles; `blog.google/technology/ai/rss/` and `/technology/health/rss/` redirect to `/innovation-and-ai/technology/…/rss/`; CMS (10 entries) and Fierce (25 entries) have no parseable dates without quirks; every other catalogue URL below returned 200 with dated entries.
13. mypy strict: `feedparser`, `newspaper`, `pypdfium2` have no `py.typed` (`import-untyped`); `dateutil` has no stubs; `trafilatura`, `htmldate`, `protego`, `httpx`, `h2` are typed.
14. FastAPI OpenAPI: a field typed `T | SkipJsonSchema[None] = None` is emitted without `null` (not nullable) while still accepting an explicit `null`; `T | None = None` is emitted as `anyOf [T, null]`; component names are the class names (`Page[FeedOut]` → `Page_FeedOut_`), no `-Input`/`-Output` split for these `ApiModel` shapes.
15. `ipaddress`: `93.184.215.14` and `2606:4700::1111` are global; `100.64.0.1`, `169.254.169.254`, `10.0.0.1`, `fd00:ec2::254`, `::1` are not; `::ffff:127.0.0.1` has `ipv4_mapped == 127.0.0.1` (not global).
16. `httpx.AsyncClient(http2=True, transport=httpx.MockTransport(handler), follow_redirects=False)` streams with `client.stream("GET", url)`; a 302 exposes `response.headers["location"]` and `response.url.join(location)`; `httpx.Timeout(15.0, connect=5.0)` gives connect 5, read/write/pool 15.

---

## Track-wide rules (apply to every task)

1. **Layering.** `domain/*.py` files import only `domain/` and the standard library. `agents/research_analyst.py` imports `domain/`, `agents.common`, `llm.gateway` types (`AgentSpec`, `AgentResult`, `CallContext`, `LLMGateway`) and never `pydantic_ai` or `db`. Only `pkg/research/**`, `services/research_runs.py` and `services/sources.py` touch the database.
2. **Untyped imports.** Every import of `feedparser`, `newspaper`, `pypdfium2` and `dateutil` carries `# type: ignore[import-untyped, unused-ignore]` (the `unused-ignore` code keeps mypy strict green if stubs are added later). `newspaper`, `trafilatura`, `htmldate` and `pypdfium2` are imported inside the functions that use them (slow imports; `research.steps` is imported by `test_found_imports.py` and the worker).
3. **Save points.** `pkg/research/steps.py`, the two routers and the two schema modules import cleanly at every save point (CONTRACT §2 rule (a)). New helper modules may be incomplete while nothing imports them. The prompt is drafted as `backend/prompts/research/synthesize.v1.md.wip` and renamed when complete.
4. **Time.** Step code reads time only through `sc.now()`. Helpers take `now: datetime` arguments. Every stored timestamp is timezone-aware UTC. A naive datetime parsed from a source is interpreted as UTC.
5. **Mock mode.** Default suites make no network calls: the research environment (RES-7) uses `FixtureTransport` and a fixture resolver whenever `settings.mock_mode` is true, and unit tests pass `httpx.MockTransport` explicitly.
6. **Idempotent step bodies** (§5.5 rule 2): `blog_research_runs` rows are inserted with `dbos_workflow_id`/`dbos_step_id` from `sc.call` using `INSERT … ON CONFLICT DO NOTHING` on `uq_blog_research_runs_wf_step` and read back; with `sc.call.dbos_workflow_id is None` a new row is always inserted.
7. **Errors on research runs** use `error_payload(exc) -> {"class": type(exc).__name__, "message": str(exc)[:2000]}`; for `InsufficientEvidence` the payload adds `foundSources`, `requiredSources`, `successfulQueries`.
8. **Constants** (module-level, not settings): `MAX_ITEMS_PER_FEED = 20`, `MAX_LEDGER_CANDIDATES = 40`, `MAX_ANALYST_SOURCES = 40`, `MAX_PACKET_SOURCES = 20`, `MIN_FULL_TEXT_WORDS = 50`, `FALLBACK_WORD_THRESHOLD = 150`, `REFETCH_AFTER = timedelta(hours=24)`, `SEARCH_ATTEMPTS = 3`, `SEARCH_BACKOFF_SECONDS = (0.5, 1.0)`, `ANSWER_EXCERPT_CHARS = 1500`, `FDA_CSV_POLL_INTERVAL = timedelta(days=7)`, `FDA_CSV_MAX_NEW_ROWS = 20`, `PUBMED_TOOL = "mdcopilot-blog"`.
9. **TDD per task**: write the listed tests, run `RES_PYTEST <file>` and see them fail (import error or assertion), implement, run green, then `RES_LINT`. Record red and green output lines in the track report.

---

## Mock fixture set (shared by RES-7 and later tasks)

**Layout.** Each of `backend/fixtures/mock/{feeds,pubmed,federal_register,fda,pages,pdfs}/` holds an `index.json` and the body files it names. Scenario overlays use the same layout under `backend/fixtures/mock/scenarios/<research_*>/<dir>/index.json`.

`index.json` schema (validated at load; any violation raises `ValueError` naming the file):
```json
{"anchor": "2026-09-17T01:30:00Z",
 "entries": [{"url": "https://…", "file": "fda_press.xml", "status": 200, "headers": {"content-type": "application/rss+xml"}}]}
```
- `anchor`: ISO-8601 UTC; every loaded index (base and overlay) must carry the same anchor, else `ValueError("fixture anchors differ: <a> != <b>")`.
- `file`: relative to the index directory, may be shared by several entries, or `null` (empty body).
- `status`: int; `headers`: lowercase names → string values.
- Match key: `fixture_match_key(url)` = lowercase scheme and host, path, and the query pairs sorted, excluding `VOLATILE_PARAMS = {"api_key", "tool", "email", "reldate", "conditions[publication_date][gte]"}`; fragment dropped. Duplicate keys inside one index are a `ValueError`. Overlay entries replace base entries with the same key.

**Anchor** `2026-09-17T01:30:00Z` equals the §8.1 fixture clock (`2026-09-17T07:00:00+05:30`), so the date shift in tests is zero.

**Default broad-scan data** (dates before shifting; T = tier, AM = access mode). The ordering column is `agents.common.order_sources` (tier asc, `published_at` desc nulls last, `canonical_url` asc) and is asserted in RES-16.

| Marker | Canonical URL (fixture) | Discovered via | T | Source type | Date (UTC) / `date_source` | AM / fetch status |
|---|---|---|---|---|---|---|
| S1 | `https://fda.gov/news-events/press-announcements/fda-outlines-oversight-approach-ai-enabled-clinical-decision-support` | feed FDA press releases | 1 | government | 2026-09-16T19:30Z / feed | full_text / ok |
| S2 | `https://ama-assn.org/practice-management/digital-health/physicians-report-ai-scribes-cut-after-hours-documentation` | search | 1 | other | 2026-09-16T15:30Z / jsonld | full_text / ok |
| S3 | `https://pubmed.ncbi.nlm.nih.gov/40000002` | feed PubMed AI clinical practice | 1 | journal | 2026-09-16T00:00Z / api | abstract_only / ok |
| S4 | `https://cms.gov/newsroom/press-releases/cms-announces-prior-authorization-technology-pilot` | feed CMS (quirks) | 1 | government | 2026-09-15T14:01:40Z / feed | full_text / ok |
| S5 | `https://hhs.gov/about/news/2026/09/15/hhs-releases-ai-strategy-update.html` | feed HHS | 1 | government | 2026-09-15T12:00Z / feed | metadata_only / blocked (403 + `cf-mitigated: challenge`) |
| S6 | `https://federalregister.gov/documents/2026/09/15/2026-19001/clinical-decision-support-software-request-for-comments` | Federal Register API | 1 | government | 2026-09-15T00:00Z / api | full_text / ok |
| S7 | `https://pubmed.ncbi.nlm.nih.gov/40000001` | feed JAMA → PubMed (DOI `10.1001/jama.2026.90001`) | 1 | journal | 2026-09-14T00:00Z / api | abstract_only / ok |
| S8 | `https://nih.gov/news-events/news-releases/nih-study-ai-assisted-specialist-referrals` | search | 1 | government | none / none | metadata_only / not_fetched (domain `nih.gov` policy `metadata_only`) |
| S9 | `https://statnews.com/2026/09/16/specialist-wait-times-ai-triage` (fetched URL has `?utm_campaign=rss`) | feed STAT health tech | 2 | trade_press | 2026-09-16T14:00Z / feed | full_text / ok |
| S10 | `https://fiercehealthcare.com/ai-and-machine-learning/health-systems-pilot-ai-referral-routing` | feed Fierce (`Sep 16, 2026 5:39am`) | 2 | trade_press | 2026-09-16T05:39Z / feed | full_text / ok |
| S11 | `https://beckershospitalreview.com/healthcare-information-technology/ai/health-systems-expand-ai-scribes.html` | search | 2 | trade_press | 2026-09-15T09:00Z / meta | full_text / ok |
| S12 | `https://medrxiv.org/content/10.64898/2026.09.12.26390001v1` (feed link has `?rss=1`) | feed medRxiv (DOI `10.64898/2026.09.12.26390001`) | 2 | preprint | 2026-09-14T00:00Z / feed | metadata_only / not_fetched (domain `medrxiv.org` policy `metadata_only`), `is_preprint=true` |

Extra fixture items that must not become sources: an FDA press item dated 2026-08-28 (outside the 7-day window) and a CMS item dated 2026-08-20. The FDA AI CSV fixture has 3 rows (`K260001`, `DEN260002`, `P260003`) and produces no signal on the first poll (baseline). Every page body used for `full_text` has at least 180 words after extraction and no date other than the one listed (the S2 page has only JSON-LD `datePublished`; the S11 page has only `<meta property="article:published_time">`; S1, S4, S6, S9 and S10 pages have no date markup, so the feed/API date is used). Every enabled feed not listed above is served `feeds/empty_rss.xml` (a valid RSS 2.0 channel with no items).

**`search/broad.json`** (Phase 1 single-result form): `provider: "fixture"`, `model: "fixture-search"`, `search_actions: 1`, `input_tokens: 1500`, `output_tokens: 200`, `cost_usd: "0"`, `latency_ms: 0`, `answer_text` of about 60 words, `citations` for the three URLs below, `sources`: `https://www.ama-assn.org/practice-management/digital-health/physicians-report-ai-scribes-cut-after-hours-documentation`, `https://www.nih.gov/news-events/news-releases/nih-study-ai-assisted-specialist-referrals`, `https://www.beckershospitalreview.com/healthcare-information-technology/ai/health-systems-expand-ai-scribes.html`.

**Deep data** (`search/deep.json`, same form, `search_actions: 1`), sources in this order: `https://www.fda.gov/media/190001/download` (PDF, `pdfs/`, ≥200 words, undated → `full_text`, date none), `https://pubmed.ncbi.nlm.nih.gov/40000003/` (esummary `sortpubdate 2026/09/10 00:00`, abstract), `https://www.hrsa.gov/news/press-releases/specialist-workforce-projections-2026` (JSON-LD 2026-09-12T10:00:00Z), `https://www.statnews.com/2026/09/12/ai-referral-triage-health-systems/` (meta 2026-09-12T08:00:00Z), `https://www.kffhealthnews.org/news/article/specialist-wait-times-rural-2026/` (only a visible "Published September 11, 2026" byline → `htmldate`, 2026-09-11T00:00:00Z), `https://www.aamc.org/news/physician-shortage-projections-ai-2026` (meta 2026-09-09T12:00:00Z), `https://www.healthaffairs.org/content/forefront/ai-specialist-access-evidence` (domain policy `metadata_only`, undated). Result: 7 sources, 5 dated, 6 Tier 1/2 with text.

**Verification data** (`search/verification.json`, same form, `search_actions: 1`), sources: `https://www.cdc.gov/nchs/products/databriefs/db-ai-adoption-2026.htm` (JSON-LD 2026-09-08T00:00:00Z, full text), `https://www.fda.gov/news-events/press-announcements/fda-outlines-oversight-approach-ai-enabled-clinical-decision-support` (same page as S1), `https://www.example-health-blog.com/ai-physicians` (not allow-listed; must be filtered out, no page fixture).

**Scenario overlays** (RES-owned): `research_feed_down` (the FDA press releases feed URL → status 503, `file: null`), `research_all_blocked` (every broad page URL in the table → status 403 with `cf-mitigated: challenge`; PubMed efetch → status 500), `research_unknown_marker` (`llm/research/research_synthesize.json` identical to the default analyst fixture except finding 0 cites `S99`).

---

## Tasks

### RES-1: URL canonicalisation and domains (`domain/urls.py`)

**Files.** Create `pkg/domain/urls.py`, `backend/tests/research/test_res_urls.py`.

**Interfaces (produces).**
```python
TRACKING_PARAMS: frozenset[str]   # {"fbclid","gclid","dclid","msclkid","mc_cid","mc_eid","_ga","_gl","igshid","rss","cmpid","ncid","ito"}
TRACKING_PREFIXES: tuple[str, ...]   # ("utm_",)
MULTI_LABEL_SUFFIXES: frozenset[str] # {"co.uk","org.uk","ac.uk","gov.uk","nhs.uk","com.au","org.au","gov.au","co.in","gov.in","co.jp","com.br"}
class InvalidUrl(ValueError): ...
def is_http_url(url: str) -> bool
def host_of(url: str) -> str                 # raises InvalidUrl
def normalize_host(host: str) -> str
def canonicalize_url(url: str) -> str        # raises InvalidUrl
def url_hash(canonical_url: str) -> str      # sha256 hex, 64 chars
def registrable_domain(host: str) -> str
def domain_suffixes(host: str) -> list[str]
def fixture_match_key(url: str, volatile: frozenset[str]) -> str
```

**Behaviour rules.**
1. `is_http_url`: true iff `urlsplit(url.strip())` has scheme `http`/`https` (case-insensitive), a non-empty hostname, and no userinfo.
2. `normalize_host`: lowercase, strip one trailing `.`, strip one leading `www.`.
3. `host_of`: `normalize_host(urlsplit(url).hostname)`; `InvalidUrl` when `is_http_url` is false.
4. `canonicalize_url`: `InvalidUrl(f"not an http(s) URL: {url!r}")` when `is_http_url` is false. Output scheme `https`; host per rule 2; port kept only when present and not 80/443; empty path → `/`; one trailing `/` removed when the path is longer than `/`; query pairs from `parse_qsl(keep_blank_values=True)` minus keys whose lowercase form is in `TRACKING_PARAMS` or starts with a `TRACKING_PREFIXES` entry, sorted by `(key, value)`, joined with `urlencode`; `?` omitted when no pairs remain; fragment dropped; path percent-encoding unchanged.
5. `registrable_domain`: IP literal → unchanged; after `normalize_host`, one or two labels → host; last two labels in `MULTI_LABEL_SUFFIXES` → last three labels; otherwise last two labels.
6. `domain_suffixes`: `normalize_host(host)` then every suffix with at least two labels, longest first.
7. `fixture_match_key`: `"<scheme>://<host><path>?<sorted pairs>"` using the raw lowercase host (no `www.` stripping), raw path, query pairs sorted with keys in `volatile` removed, fragment dropped.

**Tests to write first** (`test_res_urls.py`, pure):
- `test_canonicalize_examples` (parametrised): `"HTTP://WWW.Example.org:443/a/b/?utm_source=x&b=2&a=1#frag"` → `"https://example.org/a/b?a=1&b=2"`; `"https://www.statnews.com/2026/09/16/x/?utm_campaign=rss"` → `"https://statnews.com/2026/09/16/x"`; `"https://pubmed.ncbi.nlm.nih.gov/42749085/"` → `"https://pubmed.ncbi.nlm.nih.gov/42749085"`; `"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K253628"` → `"https://accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K253628"`; `"https://example.org"` → `"https://example.org/"`; `"http://example.org:8080/x"` → `"https://example.org:8080/x"`; `"https://www.medrxiv.org/content/10.64898/2026.09.12.26390001v1?rss=1"` → `"https://medrxiv.org/content/10.64898/2026.09.12.26390001v1"`.
- `test_canonicalize_rejects` (parametrised): `"ftp://x.org/a"`, `"https://"`, `"https://user:pw@x.org/"`, `"javascript:alert(1)"`, `"/relative/path"` → `InvalidUrl`.
- `test_url_hash_is_sha256_of_canonical`: `url_hash("https://example.org/")` equals `hashlib.sha256(b"https://example.org/").hexdigest()`, length 64.
- `test_registrable_domain` (parametrised): `ai.nejm.org` → `nejm.org`; `www.bbc.co.uk` → `bbc.co.uk`; `pubmed.ncbi.nlm.nih.gov` → `nih.gov`; `fda.gov` → `fda.gov`; `WWW.FDA.GOV.` → `fda.gov`; `93.184.215.14` → `93.184.215.14`.
- `test_domain_suffixes`: `"a.b.fda.gov"` → `["a.b.fda.gov", "b.fda.gov", "fda.gov"]`; `"www.fda.gov"` → `["fda.gov"]`.
- `test_fixture_match_key_ignores_volatile_params`: keys of `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?term=x&db=pubmed&email=a@b&reldate=7` and `…?db=pubmed&term=x` with `volatile={"email","reldate"}` are equal and end with `?db=pubmed&term=x`.

**Implementation notes.** `urllib.parse` only. `hostname` from `urlsplit` is already lowercase and bracket-free for IPv6.

**Verification.** `RES_PYTEST tests/research/test_res_urls.py`: red `ModuleNotFoundError: No module named 'mdcopilot_blog.domain.urls'`; green `21 passed`. `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Extractor + ledger … canonical URLs" (canonical part).

### RES-2: Tiers, domain rules, relevance (`domain/tiers.py`)

**Files.** Create `pkg/domain/tiers.py`, `backend/tests/research/test_res_tiers.py`.

**Interfaces (produces).**
```python
HeaderProfile = Literal["default", "browser_like"]
FetchPolicy = Literal["fetch", "metadata_only", "never"]
TIER_WEIGHT: Mapping[int, float]          # {1: 1.0, 2: 0.7, 3: 0.3}
STOPWORDS: frozenset[str]                 # {"of","in","on","to","by","an","as","at","is","it","or","be","we","us","the","and","for","with","from","that","this","are","was","were","has","have","its","into","about","over","after","new","how","why","what"}
@dataclass(frozen=True)
class DomainRule:
    domain: str; tier: int; source_type: SourceType; publisher: str | None
    header_profile: HeaderProfile; fetch_policy: FetchPolicy; verification_allowlisted: bool
@dataclass(frozen=True)
class FeedHint:
    feed_url: str; feed_name: str; tier: int; source_type: SourceType; is_preprint: bool; header_profile: HeaderProfile
@dataclass(frozen=True)
class Classification:
    domain: str; tier: int; source_type: SourceType; header_profile: HeaderProfile
    fetch_policy: FetchPolicy; is_preprint: bool; rule_publisher: str | None; feed_publisher: str | None
def match_domain_rule(host: str, rules: Mapping[str, DomainRule]) -> DomainRule | None
def classify_source(url: str, *, rules: Mapping[str, DomainRule], feed: FeedHint | None) -> Classification
def resolve_publisher(*, rule_publisher: str | None, journal: str | None, feed_publisher: str | None, sitename: str | None, domain: str) -> str
def tokenize(text: str) -> frozenset[str]
def keyword_set(phrases: Iterable[str]) -> frozenset[str]
def relevance_score(*, text: str, keywords: frozenset[str], published_at: datetime | None, now: datetime, window_days: int, tier: int) -> float
```

**Behaviour rules.**
1. `rules` is keyed by the lowercase `domain`. `match_domain_rule` walks `urls.domain_suffixes(host)` longest first and returns the first hit, else `None`.
2. `classify_source`: `domain = urls.registrable_domain(urls.host_of(url))`. The feed hint applies only when `registrable_domain(host_of(url)) == registrable_domain(host_of(feed.feed_url))`. Tier/source type/header profile: from the rule when a rule matches; else from the applicable feed hint; else tier 3, `SourceType.OTHER`, `"default"`. `fetch_policy`: rule's, else `"fetch"`. `is_preprint`: applicable `feed.is_preprint`, or rule source type `PREPRINT`. `rule_publisher` = rule's publisher; `feed_publisher` = applicable feed's `feed_name`, else `None`.
3. `resolve_publisher`: first non-blank (after strip) of `journal`, `rule_publisher`, `feed_publisher`, `sitename`, `domain`, truncated to 200 characters (a PubMed record is published by its journal, not by "PubMed").
4. `tokenize`: lowercase, `re.findall(r"[a-z0-9]+", …)`, drop tokens shorter than 2 characters and tokens in `STOPWORDS`.
5. `keyword_set`: union of `tokenize` over the phrases.
6. `relevance_score`: `overlap = 0.0` if `keywords` is empty, else `min(1.0, len(keywords & tokenize(text)) / min(len(keywords), 10))`; `recency = 0.0` if `published_at` is None, else `max(0.0, 1.0 - max(0.0, (now - published_at).total_seconds()) / (window_days * 86400))`; result `round(0.4 * overlap + 0.35 * recency + 0.25 * TIER_WEIGHT[tier], 4)`. A tier outside 1..3 raises `ValueError`.

**Tests to write first** (`test_res_tiers.py`, pure). Fixture `RULES` built in the test: `fda.gov` (1, government, "U.S. Food and Drug Administration", default, fetch, True), `accessdata.fda.gov` (1, government, None, default, metadata_only, True), `nih.gov` (1, government, "National Institutes of Health", default, metadata_only, True), `pubmed.ncbi.nlm.nih.gov` (1, journal, "PubMed", default, metadata_only, True), `medrxiv.org` (2, preprint, "medRxiv", default, metadata_only, False).
- `test_match_prefers_longest_suffix`: `pubmed.ncbi.nlm.nih.gov` → rule domain `pubmed.ncbi.nlm.nih.gov`; `www.accessdata.fda.gov` → `accessdata.fda.gov`; `www.cdc.gov` → `None`.
- `test_classify_rule_wins_over_feed`: url `https://www.fda.gov/x`, feed hint (`https://www.fda.gov/…/rss.xml`, "FDA press releases", tier 2, trade_press, False, browser_like) → tier 1, government, `default`, `fetch`, `rule_publisher == "U.S. Food and Drug Administration"`, `feed_publisher == "FDA press releases"`, domain `fda.gov`.
- `test_classify_feed_applies_only_to_same_domain`: feed hint (`https://tools.cdc.gov/api/v2/…`, "CDC newsroom", 1, government, False, default) with url `https://www.cdc.gov/media/x.html` → tier 1, government, `feed_publisher == "CDC newsroom"`; the same hint with url `https://example.org/a` → tier 3, other, `feed_publisher is None`, `fetch_policy == "fetch"`.
- `test_classify_preprint`: `https://www.medrxiv.org/content/10.1/x` with no feed → `is_preprint is True`, tier 2, `fetch_policy == "metadata_only"`.
- `test_resolve_publisher_order`: `("PubMed", "JAMA", "JAMA feed", "Site", "jamanetwork.com")` → `"JAMA"`; `("U.S. Food and Drug Administration", None, "FDA press releases", "FDA", "fda.gov")` → `"U.S. Food and Drug Administration"`; `(None, None, None, "  ", "example.org")` → `"example.org"`; `("A"*250, …)` → length 200.
- `test_relevance_hand_computed`: keywords `keyword_set(["specialist wait times"])`, text `"Specialist wait times grow"`, `now = 2026-09-17T00:00Z`, `published_at = 2026-09-16T00:00Z`, window 7, tier 1 → `0.95`; same with `published_at=None`, tier 3 → `0.475`; empty keywords, published now, tier 2 → `0.525`.
- `test_relevance_rejects_bad_tier`: tier 4 → `ValueError`.
- `test_tokenize_keeps_ai_and_drops_stopwords`: `tokenize("AI and the Future of Specialist care")` == `{"ai", "future", "specialist", "care"}`.

**Implementation notes.** Pure; imports `domain.contracts.SourceType` and `domain.urls`.

**Verification.** red `ModuleNotFoundError`; green `8 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Extractor + ledger … tiers"; RESEARCH_ARCHITECTURE §7 deterministic relevance.

### RES-3: Claim rules (`domain/claim_rules.py`)

**Files.** Create `pkg/domain/claim_rules.py`, `backend/tests/research/test_res_claim_rules.py`.

**Interfaces (produces).**
```python
FindingCategory = Literal["regulatory", "clinical_research", "workforce", "product_announcement", "policy", "market", "technology", "operations", "other"]
ANNOUNCEMENT_CATEGORIES: frozenset[str]   # {"product_announcement", "regulatory"}
MAX_FINDINGS = 25
@dataclass(frozen=True)
class EvidenceSource:
    source_id: uuid.UUID; tier: int; access_mode: AccessMode; published_at: datetime | None
    source_type: SourceType; is_preprint: bool
@dataclass(frozen=True)
class DraftFinding:
    claim: str; evidence: str; confidence: float; category: FindingCategory; claim_type: ClaimType
    importance: Literal["high", "normal"]; self_reported: bool; source_ids: tuple[uuid.UUID, ...]
@dataclass(frozen=True)
class RuledFinding:
    claim: str; evidence: str; confidence: float; category: FindingCategory; claim_type: ClaimType
    importance: Literal["high", "normal"]; is_preprint: bool; downgraded_from: str | None
    rule: Literal["marketing_self_report", "preprint_only", "undated", "high_importance_evidence", "metadata_only"] | None
    source_ids: tuple[uuid.UUID, ...]
def apply_claim_rules(findings: Sequence[DraftFinding], sources: Mapping[uuid.UUID, EvidenceSource]) -> list[RuledFinding]
```

**Behaviour rules** (processed in input order):
1. A `source_id` missing from `sources` raises `KeyError` (the caller has already resolved markers, so this is a programming error).
2. A finding whose `normalize_for_match(claim)` equals an earlier kept finding's is dropped. At most `MAX_FINDINGS` findings are kept (later ones dropped).
3. `is_preprint` = any cited source has `is_preprint`.
4. Rules apply only while `claim_type == FACT`; the first rule that fires sets `claim_type`, `downgraded_from = "FACT"` and `rule`, and no later rule runs. Importance and confidence never change.
   - R1 `marketing_self_report`: `self_reported` and every cited source has `source_type == COMPANY_ANNOUNCEMENT` → `MARKETING_CLAIM`.
   - R2 `preprint_only`: every cited source `is_preprint` → `ANALYSIS`.
   - R3 `undated`: no cited source has `published_at` → `ANALYSIS`.
   - R4 `high_importance_evidence`: `importance == "high"` and no cited source has `tier <= 2` and `access_mode in {FULL_TEXT, ABSTRACT_ONLY}` → `ANALYSIS`.
   - R5 `metadata_only`: every cited source has `access_mode == METADATA_ONLY` and `category not in ANNOUNCEMENT_CATEGORIES` → `ANALYSIS`.
5. Non-FACT findings keep their type, `downgraded_from=None`, `rule=None`.

**Tests to write first** (`test_res_claim_rules.py`, pure). Helper `src(tier, access, dated=True, type=SourceType.GOVERNMENT, preprint=False)`; `NOW = 2026-09-17T00:00Z`.
- `test_supported_high_fact_is_kept`: high FACT citing a tier-1 full_text dated source → `claim_type FACT`, `downgraded_from None`, `rule None`.
- `test_marketing_self_report`: self_reported FACT citing only a company_announcement tier-1 full_text source → `MARKETING_CLAIM`, `"FACT"`, `"marketing_self_report"`; adding a second, independent trade_press source keeps `FACT`.
- `test_preprint_only_fact_becomes_analysis`: citing one preprint → `ANALYSIS`, rule `preprint_only`, `is_preprint True`; citing a preprint and a journal source → `FACT`, `is_preprint True`.
- `test_undated_fact_becomes_analysis`: normal FACT citing an undated tier-1 full_text source → `ANALYSIS`, rule `undated`.
- `test_high_fact_needs_tier12_text`: high FACT citing tier-3 full_text dated → rule `high_importance_evidence`; citing tier-1 metadata_only dated → same rule; citing tier-2 abstract_only dated → `FACT`.
- `test_metadata_only_normal_fact`: normal FACT, category `market`, only metadata_only dated sources → `ANALYSIS`, rule `metadata_only`; same with category `regulatory` → `FACT`.
- `test_first_rule_wins`: self_reported high FACT citing only an undated company_announcement metadata_only source → rule `marketing_self_report` only.
- `test_non_fact_untouched`: `PREDICTION` citing an undated metadata_only source → unchanged, `rule None`.
- `test_duplicates_and_cap`: 30 findings where findings 1 and 2 differ only by case and curly apostrophe → 25 kept, the duplicate removed, order preserved.
- `test_unknown_source_raises`: → `KeyError`.

**Implementation notes.** Imports `domain.contracts.ClaimType`, `SourceType`, `domain.enums.AccessMode`, `domain.text.normalize_for_match`.

**Verification.** red `ModuleNotFoundError`; green `10 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Research Analyst with claim rules in code"; RESEARCH_ARCHITECTURE §7 claim rules; §5.2/§12 `ClaimType`.

### RES-4: Query planner (`domain/query_plan.py`)

**Files.** Create `pkg/domain/query_plan.py`, `backend/tests/research/test_res_query_plan.py`.

**Interfaces (produces).**
```python
MONTH_YEAR_TOKEN = "{month_year}"
MAX_QUERY_CHARS = 300
@dataclass(frozen=True)
class ThemeState:
    key: str; name: str; query_templates: tuple[str, ...]; pillar_keys: tuple[str, ...]
    is_active: bool; last_searched_at: datetime | None; sort_order: int
@dataclass(frozen=True)
class PlannedQuery:
    text: str; theme_key: str | None; facet: str | None
DEEP_FACETS: tuple[tuple[str, str], ...]
def render_template(template: str, *, today: date) -> str
def plan_broad_queries(themes: Sequence[ThemeState], *, pillar_key: str | None, today: date, broad_queries: int, pillar_queries: int) -> list[PlannedQuery]
def plan_deep_queries(*, title: str, thesis: str, pillar_name: str | None, today: date, deep_queries: int) -> list[PlannedQuery]
```

**Behaviour rules.**
1. `render_template`: replaces every `{month_year}` with `today.strftime("%B %Y")`, collapses runs of whitespace to one space, strips, truncates to `MAX_QUERY_CHARS`. No other placeholder processing.
2. Ordering key for themes: `(last_searched_at is not None, last_searched_at or datetime.min.replace(tzinfo=UTC), sort_order, key)`.
3. `plan_broad_queries`: consider only `is_active` themes with at least one template. Pillar themes = those whose `pillar_keys` contains `pillar_key` (none when `pillar_key` is None), ordered by rule 2, first `min(pillar_queries, len)` taken. Other themes = the remaining active themes, ordered by rule 2, first `broad_queries - len(pillar picks)` taken. Each picked theme yields one query from template index `today.toordinal() % len(templates)`. Output order: pillar picks, then others.
4. Second pass, only when the output has fewer than `broad_queries` items: loop `k = 1, 2, …` over the picked themes in output order, adding template index `(base + k) % len(templates)`, until `broad_queries` items exist or a full loop adds nothing new.
5. Queries whose text equals (case-insensitive) an earlier query's text are skipped. `facet` is None for broad queries.
6. `DEEP_FACETS` (facet, template), in order: `("primary_source", '"{title}" primary source')`, `("announcement", "{title} official announcement")`, `("research", "{thesis} peer-reviewed study PubMed")`, `("regulatory", "{title} FDA CMS HHS regulation guidance")`, `("statistics", "{title} statistics data {month_year}")`, `("expert_commentary", "{title} physician expert commentary")`, `("counterarguments", "{thesis} limitations criticism risks")`, `("industry_context", "{title} healthcare industry context {pillar}")`.
7. `plan_deep_queries`: `title` shortened to 120 characters and `thesis` to 160 characters, each cut at the last space at or before the limit (hard cut if no space); `{pillar}` = `pillar_name or ""`; each text goes through `render_template`; the first `deep_queries` facets (1..8; outside → `ValueError`); `theme_key=None`; `facet` set.

**Tests to write first** (`test_res_query_plan.py`, pure). Helper builds the 15 themes of RES-5's `themes.yaml` (keys, pillar keys and sort order from the table in RES-5, two templates each, `last_searched_at=None`).
- `test_render_template`: `render_template("healthcare AI news  {month_year}", today=date(2026, 9, 17))` == `"healthcare AI news September 2026"`.
- `test_pillar_day_picks`: pillar `A`, today 2026-09-14, 10/4 → 10 queries; `theme_key`s == `["specialist_shortages", "access_problems", "workforce_trends", "ai_news", "healthcare_ai", "physician_workflow", "agentic_ai", "clinical_ai_research", "regulation", "ai_model_developments"]`.
- `test_least_recently_searched_first`: same as above, but `ai_news` has `last_searched_at=2026-09-13T00:00Z` → `ai_news` absent and `digital_twins` present.
- `test_every_theme_within_three_days`: simulate 30 days from 2026-09-14 with pillars from weekday (Mon A … Fri E, Sat/Sun NARRATIVE), setting `last_searched_at = day 07:00 UTC` for every planned theme; every window of 3 consecutive days covers all 15 keys.
- `test_second_pass_fills_from_picked_themes`: 3 active themes with 3 templates each, broad 10, pillar None → 9 queries (3 per theme), no duplicates.
- `test_no_pillar`: pillar None → first 10 themes by sort order.
- `test_inactive_and_empty_themes_skipped`: an inactive theme and an active theme with `query_templates=()` never appear.
- `test_deep_queries`: title `"FDA outlines oversight approach for AI clinical decision support"`, thesis `"Oversight clarity lets specialists adopt decision support safely"`, pillar `"Governance & Clinical Autonomy"`, deep 8 → facets in `DEEP_FACETS` order; text[0] == `'"FDA outlines oversight approach for AI clinical decision support" primary source'`; text[4] ends with `"statistics data September 2026"`; deep 6 → 6 queries; deep 0 → `ValueError`.
- `test_deep_truncation`: a 400-character title yields texts ≤ 300 characters and no word cut mid-word.

**Verification.** red `ModuleNotFoundError`; green `9 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Query planner with theme rotation"; RESEARCH_ARCHITECTURE §6 rotation (4 pillar + 6 least-recently-searched; every theme within 3 days).

### RES-5: Seeded catalogue (`feeds.yaml`, `domains.yaml`, `themes.yaml`)

**Files.** Modify (FOUND created them with empty lists) `pkg/db/seed_data/feeds.yaml`, `pkg/db/seed_data/domains.yaml`, `pkg/db/seed_data/themes.yaml`. Create `backend/tests/research/test_res_seed_catalogue.py`.

**Interfaces.** Consumes FOUND's loaders (§3.4 item fields and natural keys). Produces catalogue rows used by RES-9 to RES-19.

**Behaviour rules (file content).**
1. Each file starts with a comment naming the source (`RESEARCH_ARCHITECTURE §2/§6/§7`), the verification date `2026-09-17`, and "edits after seeding happen in the Sources page; seeding never updates existing rows".
2. `feeds.yaml`, top-level `feeds`, exactly these 31 items (all `kind: rss` unless stated; `is_preprint: false` unless stated; `quirks: {}` unless stated; `header_profile: default` unless stated):

| name | url | kind | group | tier | source_type | pillar_keys | theme_keys | other fields |
|---|---|---|---|---|---|---|---|---|
| FDA press releases | `https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml` | rss | fda | 1 | government | [E, D] | [regulation, healthcare_ai] | |
| FDA MedWatch safety alerts | `https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch/rss.xml` | rss | fda | 1 | government | [E] | [regulation] | |
| FDA drugs | `https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/drugs/rss.xml` | rss | fda | 1 | government | [E] | [regulation] | |
| FDA biologics | `https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/biologics/rss.xml` | rss | fda | 1 | government | [E] | [regulation] | |
| FDA recalls | `https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/recalls/rss.xml` | rss | fda | 1 | government | [E] | [regulation] | |
| FDA AI-enabled medical devices list | `https://www.fda.gov/media/178541/download?attachment` | fda_ai_devices_csv | fda | 1 | government | [E, D] | [regulation, healthcare_ai] | |
| CMS newsroom | `https://www.cms.gov/newsroom/rss-feeds` | rss | cms | 1 | government | [A, C, E] | [regulation, access_problems, administrative_overload] | `quirks: {link_from_title_href: true, date_path: "time@datetime"}` |
| Federal Register: FDA and CMS documents | `https://www.federalregister.gov/api/v1/documents.json#fda-cms` | federal_register | federal_register | 1 | government | [E] | [regulation] | `quirks: {query_params: {"conditions[agencies][]": "food-and-drug-administration,centers-for-medicare-medicaid-services", order: newest, per_page: "20"}}` |
| HHS news | `https://www.hhs.gov/rss/news.xml` | rss | hhs | 1 | government | [A, E] | [regulation, access_problems] | `header_profile: browser_like` |
| CDC newsroom | `https://tools.cdc.gov/api/v2/resources/media/132608.rss?max=20` | rss | cdc | 1 | government | [A] | [access_problems, workforce_trends] | |
| ASTP/ONC Health IT Buzz | `https://healthit.gov/blog/feed/` | rss | onc | 1 | government | [E, D] | [regulation, healthcare_ai] | |
| AMA news | `https://www.ama-assn.org/rss.xml` | rss | ama | 1 | other | [C, A] | [burnout, administrative_overload, physician_workflow, workforce_trends] | |
| PubMed: AI in clinical practice | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi#ai-clinical-practice` | pubmed | pubmed | 1 | journal | [B, D] | [clinical_ai_research, clinical_reasoning_systems] | `quirks: {query_params: {term: '("artificial intelligence"[tiab] OR "machine learning"[tiab] OR "large language model"[tiab]) AND (physician[tiab] OR clinician[tiab] OR specialist[tiab])', retmax: "20", sort: pub_date}}` |
| PubMed: physician burnout and workload | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi#burnout-workload` | pubmed | pubmed | 1 | journal | [C] | [burnout, administrative_overload] | `quirks: {query_params: {term: '(burnout[tiab] OR "administrative burden"[tiab] OR "documentation burden"[tiab]) AND (physician[tiab] OR clinician[tiab])', retmax: "20", sort: pub_date}}` |
| JAMA | `https://jamanetwork.com/rss/site_3/67.xml` | rss | journals | 1 | journal | [B] | [clinical_ai_research] | `quirks: {resolve_to: pubmed}` |
| JAMA online first | `https://jamanetwork.com/rss/site_3/onlineFirst_67.xml` | rss | journals | 1 | journal | [B] | [clinical_ai_research] | `quirks: {resolve_to: pubmed}` |
| Lancet Digital Health | `https://www.thelancet.com/rssfeed/landig_online.xml` | rss | journals | 1 | journal | [B] | [clinical_ai_research] | `header_profile: browser_like`, `quirks: {resolve_to: pubmed}`, `is_enabled: false` (403 to both profiles on 2026-09-17) |
| npj Digital Medicine | `https://www.nature.com/npjdigitalmed.rss` | rss | journals | 1 | journal | [B, D] | [clinical_ai_research, digital_twins] | `header_profile: browser_like`, `quirks: {resolve_to: pubmed}` |
| NEJM AI | `https://ai.nejm.org/action/showFeed?jc=ai&type=etoc&feed=rss` | rss | journals | 1 | journal | [B] | [clinical_ai_research] | `quirks: {resolve_to: pubmed}`, `is_enabled: false` (403 to both profiles on 2026-09-17) |
| medRxiv Health Informatics | `https://connect.medrxiv.org/medrxiv_xml.php?subject=Health_Informatics` | rss | preprints | 2 | preprint | [B, D] | [clinical_ai_research] | `quirks: {resolve_to: doi}`, `is_preprint: true` |
| arXiv cs.AI | `https://rss.arxiv.org/rss/cs.AI` | rss | preprints | 2 | preprint | [D] | [ai_model_developments, agentic_ai] | `is_preprint: true` |
| STAT | `https://www.statnews.com/feed/` | rss | trade_press | 2 | trade_press | [A, C, E] | [healthcare_ai, workforce_trends] | |
| STAT health tech | `https://www.statnews.com/category/health-tech/feed/` | rss | trade_press | 2 | trade_press | [B, D] | [healthcare_ai, automation] | |
| Fierce Healthcare | `https://www.fiercehealthcare.com/rss/xml` | rss | trade_press | 2 | trade_press | [A, C] | [healthcare_ai, workforce_trends] | `quirks: {date_parser: dateutil}` |
| MedCity News | `https://medcitynews.com/feed/` | rss | trade_press | 2 | trade_press | [D] | [healthcare_ai, automation] | |
| Becker's Hospital Review | `https://www.beckershospitalreview.com/feed/` | rss | trade_press | 2 | trade_press | [C, D] | [healthcare_ai, workforce_trends, automation] | |
| OpenAI news | `https://openai.com/news/rss.xml` | rss | ai_labs | 1 | company_announcement | [D] | [ai_news, ai_model_developments] | |
| Google AI blog | `https://blog.google/innovation-and-ai/technology/ai/rss/` | rss | ai_labs | 1 | company_announcement | [D] | [ai_news, ai_model_developments] | |
| Google health blog | `https://blog.google/innovation-and-ai/technology/health/rss/` | rss | ai_labs | 1 | company_announcement | [D, B] | [healthcare_ai] | |
| Google Research blog | `https://research.google/blog/rss/` | rss | ai_labs | 1 | company_announcement | [D, B] | [ai_model_developments, clinical_ai_research] | |
| Google DeepMind blog | `https://deepmind.google/blog/rss.xml` | rss | ai_labs | 1 | company_announcement | [D] | [ai_model_developments, agentic_ai] | |

3. `domains.yaml`, top-level `domains`, exactly these 44 items (`header_profile: default`, `fetch_policy: fetch`, `notes: null` unless stated):

| domain | tier | source_type | publisher | allow-listed | stated fields |
|---|---|---|---|---|---|
| fda.gov | 1 | government | U.S. Food and Drug Administration | true | |
| accessdata.fda.gov | 1 | government | U.S. Food and Drug Administration | true | `fetch_policy: metadata_only`, notes "device database pages; cite as metadata" |
| cms.gov | 1 | government | Centers for Medicare & Medicaid Services | true | |
| medicaid.gov | 1 | government | Medicaid.gov | true | |
| hhs.gov | 1 | government | U.S. Department of Health and Human Services | true | `header_profile: browser_like` |
| cdc.gov | 1 | government | Centers for Disease Control and Prevention | true | |
| nih.gov | 1 | government | National Institutes of Health | true | `fetch_policy: metadata_only`, notes "Cloudflare challenge to direct fetch (2026-09-17)" |
| healthit.gov | 1 | government | ASTP/ONC | true | |
| federalregister.gov | 1 | government | Federal Register | true | |
| ahrq.gov | 1 | government | Agency for Healthcare Research and Quality | true | |
| hrsa.gov | 1 | government | Health Resources and Services Administration | true | |
| va.gov | 1 | government | U.S. Department of Veterans Affairs | true | |
| gao.gov | 1 | government | U.S. Government Accountability Office | true | |
| who.int | 1 | government | World Health Organization | true | |
| pubmed.ncbi.nlm.nih.gov | 1 | journal | PubMed | true | `fetch_policy: metadata_only`, notes "abstracts come from E-utilities efetch" |
| jamanetwork.com | 1 | journal | JAMA Network | true | `fetch_policy: metadata_only`, notes "article pages bot-walled; resolve to PubMed" |
| thelancet.com | 1 | journal | The Lancet | true | `fetch_policy: metadata_only` |
| nejm.org | 1 | journal | NEJM | true | `fetch_policy: metadata_only` |
| nature.com | 1 | journal | Nature Portfolio | true | `header_profile: browser_like` |
| bmj.com | 1 | journal | The BMJ | true | `fetch_policy: metadata_only` |
| healthaffairs.org | 1 | journal | Health Affairs | true | `fetch_policy: metadata_only` |
| ama-assn.org | 1 | other | American Medical Association | true | |
| aamc.org | 1 | other | Association of American Medical Colleges | true | |
| acponline.org | 1 | other | American College of Physicians | true | |
| aha.org | 1 | other | American Hospital Association | true | |
| medrxiv.org | 2 | preprint | medRxiv | false | `fetch_policy: metadata_only` |
| biorxiv.org | 2 | preprint | bioRxiv | false | `fetch_policy: metadata_only` |
| arxiv.org | 2 | preprint | arXiv | false | |
| reuters.com | 2 | trade_press | Reuters | true | `fetch_policy: never`, notes "robots.txt disallows unknown bots; search covers it" |
| apnews.com | 2 | trade_press | Associated Press | true | |
| statnews.com | 2 | trade_press | STAT | true | |
| fiercehealthcare.com | 2 | trade_press | Fierce Healthcare | true | |
| medcitynews.com | 2 | trade_press | MedCity News | true | |
| beckershospitalreview.com | 2 | trade_press | Becker's Hospital Review | true | |
| healthcareitnews.com | 2 | trade_press | Healthcare IT News | true | `fetch_policy: metadata_only`, notes "Cloudflare challenge to direct fetch (2026-09-17)" |
| modernhealthcare.com | 2 | trade_press | Modern Healthcare | true | |
| kffhealthnews.org | 2 | trade_press | KFF Health News | true | |
| axios.com | 2 | trade_press | Axios | true | |
| technologyreview.com | 2 | trade_press | MIT Technology Review | true | |
| openai.com | 1 | company_announcement | OpenAI | false | `fetch_policy: metadata_only`, notes "article pages bot-walled; Tier 1 for its own announcements only" |
| blog.google | 1 | company_announcement | Google | false | notes "Tier 1 for its own announcements only" |
| research.google | 1 | company_announcement | Google Research | false | notes "Tier 1 for its own announcements only" |
| deepmind.google | 1 | company_announcement | Google DeepMind | false | notes "Tier 1 for its own announcements only" |
| anthropic.com | 1 | company_announcement | Anthropic | false | notes "no feed; Tier 1 for its own announcements only" |

4. `themes.yaml`, top-level `themes`, exactly these 15 items (`sort_order` = row index 0..14; `description` = the one sentence given):

| key | name | pillar_keys | description | query_templates |
|---|---|---|---|---|
| ai_news | AI news | [D, NARRATIVE] | Notable artificial intelligence news relevant to medicine. | `artificial intelligence news healthcare {month_year}`; `major AI announcements this week medicine` |
| healthcare_ai | Healthcare AI | [B, D, E] | AI deployments and results inside health systems. | `healthcare AI deployment hospitals {month_year}`; `health system artificial intelligence adoption results` |
| physician_workflow | Physician workflow | [B, C] | How AI changes the daily work of physicians. | `physician workflow AI tools clinical documentation`; `AI in specialist clinic workflow {month_year}` |
| specialist_shortages | Specialist shortages | [A] | Shortages of specialist physicians and their causes. | `specialist physician shortage {month_year}`; `specialty care workforce shortage data` |
| access_problems | Access problems | [A] | Patient access to specialist care, wait times and regional gaps. | `specialist appointment wait times patients`; `patient access to specialty care rural {month_year}` |
| agentic_ai | Agentic AI | [D] | AI agents that act inside clinical and operational workflows. | `agentic AI healthcare workflows`; `AI agents clinical operations {month_year}` |
| clinical_ai_research | Clinical AI research | [B, E] | Peer-reviewed and preprint research on clinical AI. | `clinical study artificial intelligence physicians results {month_year}`; `randomized trial AI clinical decision support` |
| regulation | Regulation | [E] | FDA, CMS, HHS and ONC actions that govern clinical AI. | `FDA AI medical device guidance {month_year}`; `CMS HHS artificial intelligence policy rule` |
| workforce_trends | Workforce trends | [A, C] | Physician and clinician workforce data and trends. | `physician workforce trends report {month_year}`; `clinician staffing survey AI` |
| ai_model_developments | AI model developments | [B, D] | New model releases and capabilities relevant to medicine. | `new large language model release medical {month_year}`; `AI model benchmark clinical reasoning` |
| digital_twins | Digital twins | [D, NARRATIVE] | Digital twins of patients, physicians and care processes. | `digital twin healthcare patient model`; `physician digital twin AI {month_year}` |
| clinical_reasoning_systems | Clinical reasoning systems | [B] | Systems that model or support diagnostic and clinical reasoning. | `AI clinical reasoning diagnosis study`; `large language model diagnostic accuracy physicians {month_year}` |
| automation | Automation | [C, D] | Automation of administrative and operational healthcare work. | `healthcare administrative automation AI {month_year}`; `prior authorization automation artificial intelligence` |
| burnout | Burnout | [C] | Physician burnout, its drivers and interventions. | `physician burnout survey {month_year}`; `clinician burnout electronic health record inbox` |
| administrative_overload | Administrative overload | [C] | Documentation, inbox and portal-message load on clinicians. | `physician administrative burden documentation time`; `patient portal message volume physicians {month_year}` |

**Tests to write first** (`test_res_seed_catalogue.py`).
- `test_feeds_yaml_is_valid` (pure, `load_seed_file("feeds.yaml")["feeds"]`): 31 items; URLs unique and `urls.is_http_url`; `kind` in `FeedKind` values; `tier` in 1..3; `source_type` in `SourceType` values; `header_profile` in {default, browser_like}; quirks keys ⊆ {link_from_title_href, date_path, query_params, date_parser, resolve_to}; `resolve_to` values ⊆ {pubmed, doi}; `date_parser` values ⊆ {dateutil}; `pillar_keys` ⊆ `PillarKey` values; `theme_keys` ⊆ the 15 theme keys; `len(name) <= 200`, `1 <= len(group) <= 64`; enabled count 29; the disabled URLs are exactly the Lancet and NEJM AI URLs; `is_preprint` true exactly for medRxiv and arXiv.
- `test_domains_yaml_is_valid`: 44 items; each `domain == urls.normalize_host(domain)`; unique; `tier` 1..3; `source_type` valid; `fetch_policy` in {fetch, metadata_only, never}; `header_profile` valid; `publisher` 1..200 characters; allow-listed count 36 (≤ 100).
- `test_themes_yaml_is_valid`: keys in the table order; each key matches `^[a-z0-9_]{1,64}$`; `sort_order == index`; 2 templates each, 1..300 characters; every `{…}` placeholder in a template equals `{month_year}`; pillar keys valid; every pillar key A–E and NARRATIVE is linked by at least 2 themes.
- `test_every_enabled_feed_classifies` (pure): building `DomainRule`s from `domains.yaml`, `tiers.classify_source(feed.url, rules=rules, feed=None)` never raises for enabled feeds; `fda.gov`, `cms.gov`, `hhs.gov`, `healthit.gov`, `ama-assn.org` feeds get tier 1; `statnews.com`, `fiercehealthcare.com`, `medcitynews.com`, `beckershospitalreview.com` feeds get tier 2.
- `test_seeded_catalogue_rows` (DB, `seeded_db`): `count(SourceFeed) == 31`, `count(SourceDomain) == 44`, `count(DiscoveryTheme) == 15`; the CMS row's `quirks == {"link_from_title_href": True, "date_path": "time@datetime"}` and `group_name == "cms"`; theme `regulation` has `pillar_keys == ["E"]`, `is_active is True`, `last_searched_at is None`; every feed has `state == {}` and `consecutive_failures == 0`.

**Verification.** Red: the first four fail on the empty lists (`assert 0 == 31`); green `5 passed`. Also run `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/db/test_seed.py tests/db/test_cli.py` → all passed (FOUND's count assertions follow the files).

**Acceptance covered.** §10.1 tables row ("Also: RES seed YAML"); RESEARCH_ARCHITECTURE §2 catalogue, §6 15 themes, §7 tier table; ARCHITECTURE §19 themes.

### RES-6: HTTP environment and retriever (`research/environment.py`, `research/retriever.py`)

**Files.** Create `pkg/research/environment.py`, `pkg/research/retriever.py`, `backend/tests/research/conftest.py` (add fixtures below; keep FOUND's docstring), `backend/tests/research/test_res_retriever.py`.

**Interfaces (produces).**
```python
# environment.py
Resolver = Callable[[str, int], Awaitable[list[str]]]
DEFAULT_ACCEPT = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5"
BROWSER_LIKE_HEADERS: Mapping[str, str]
def user_agent(settings: Settings) -> str
def profile_headers(profile: HeaderProfile, settings: Settings) -> dict[str, str]
def build_http_client(settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient
async def system_resolver(host: str, port: int) -> list[str]
class HostLimiter:
    def __init__(self, per_host: int) -> None
    def slot(self, host: str) -> asyncio.Semaphore
@dataclass(frozen=True)
class RobotsPolicy:
    allow_all: bool; disallow_all: bool; body: str
class RobotsCache:
    def __init__(self) -> None
    def get(self, origin: str, *, now: datetime, ttl: timedelta) -> RobotsPolicy | None
    def put(self, origin: str, policy: RobotsPolicy, *, now: datetime) -> None
    def clear(self) -> None
ROBOTS_CACHE: RobotsCache                     # process-wide, real mode only
@dataclass
class ResearchEnvironment:
    settings: Settings
    client: httpx.AsyncClient
    resolver: Resolver
    robots: RobotsCache
    now: Callable[[], datetime]
    date_shift: timedelta
    sleep: Callable[[float], Awaitable[None]]
    pubmed_min_interval: float
    fetch_slots: asyncio.Semaphore
    host_limiter: HostLimiter
    def shift(self, value: datetime | None) -> datetime | None
def make_environment(settings: Settings, *, client: httpx.AsyncClient, resolver: Resolver, now: Callable[[], datetime],
                     date_shift: timedelta = timedelta(0), robots: RobotsCache | None = None,
                     sleep: Callable[[float], Awaitable[None]] | None = None, pubmed_min_interval: float = 0.0) -> ResearchEnvironment
# retriever.py
REDIRECT_STATUSES: frozenset[int]   # {301, 302, 303, 307, 308}
ROBOTS_MAX_BYTES = 512_000
class UrlNotAllowed(Exception): ...
async def check_url_allowed(url: str, resolver: Resolver) -> None
def is_bot_wall(status: int, headers: Mapping[str, str], body: bytes) -> bool
@dataclass(frozen=True)
class FetchResult:
    url: str; final_url: str; status: FetchStatus; http_status: int | None; content_type: str | None
    body: bytes; etag: str | None; last_modified: str | None; not_modified: bool; error: str | None; elapsed_ms: int
async def robots_allows(env: ResearchEnvironment, url: str) -> bool
async def fetch(env: ResearchEnvironment, url: str, *, header_profile: HeaderProfile = "default",
                etag: str | None = None, last_modified: str | None = None, check_robots: bool = True,
                max_bytes: int | None = None) -> FetchResult
```

**Behaviour rules.**
1. `user_agent`: `f"mdcopilot-blog-bot/{settings.app_version} (+{settings.site_url}; {settings.fetch_contact})"` when `fetch_contact` is non-blank, else `f"mdcopilot-blog-bot/{settings.app_version} (+{settings.site_url})"`. The robots token is `mdcopilot-blog-bot`.
2. `profile_headers("default")` = `{"User-Agent": user_agent(settings), "Accept": DEFAULT_ACCEPT, "Accept-Encoding": "gzip, deflate"}`. `profile_headers("browser_like")` = `BROWSER_LIKE_HEADERS` = `User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36`, `Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8`, `Accept-Language: en-US,en;q=0.9`, `Accept-Encoding: gzip, deflate`, `Sec-Fetch-Dest: document`, `Sec-Fetch-Mode: navigate`, `Sec-Fetch-Site: none`, `Sec-Fetch-User: ?1`, `Upgrade-Insecure-Requests: 1` (verified fact 12: HHS answers 200 only to this set). No TLS fingerprint changes.
3. `build_http_client` = `httpx.AsyncClient(http2=True, follow_redirects=False, timeout=httpx.Timeout(settings.fetch_read_timeout_seconds, connect=settings.fetch_connect_timeout_seconds), limits=httpx.Limits(max_connections=settings.max_parallel_fetches, max_keepalive_connections=settings.max_parallel_fetches), transport=transport)`.
4. `system_resolver`: `await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)`, returns the unique address strings in result order.
5. `HostLimiter.slot(host)` returns one `asyncio.Semaphore(per_host)` per normalised host, created on first use. `make_environment` sets `fetch_slots = asyncio.Semaphore(settings.max_parallel_fetches)`, `host_limiter = HostLimiter(settings.fetch_per_host_limit)`, `robots = robots or RobotsCache()`, `sleep = sleep or asyncio.sleep`. `shift(None)` is `None`; otherwise `value + date_shift`.
6. `check_url_allowed` raises `UrlNotAllowed(reason)` with reasons exactly: `"unsupported URL"` (not `urls.is_http_url`), `"port not allowed"` (explicit port other than 80/443), `"host did not resolve"` (resolver raised `OSError` or returned no address), `f"non-public address {ip}"` (any resolved address, or an IP-literal host, that is not `is_global` after unwrapping `ipv4_mapped`).
7. `is_bot_wall`: true when `status in {401, 403}`, or header `cf-mitigated` equals `challenge` (case-insensitive), or `re.search(rb"<title[^>]*>\s*just a moment", body[:65536], re.IGNORECASE)` matches.
8. `robots_allows(env, url)`: origin = `scheme://host[:port]` of `url`; cache TTL `timedelta(hours=settings.robots_cache_hours)` against `env.now()`. On a miss, `fetch(env, origin + "/robots.txt", check_robots=False, max_bytes=ROBOTS_MAX_BYTES)`: `OK` with a 2xx status → policy from the body (UTF-8, `errors="replace"`); an `ERROR`/`BLOCKED` result whose `http_status` is 400–499 → `allow_all`; anything else (5xx, transport error, SSRF rejection, size cap) → `disallow_all`. Decision: `allow_all` → True, `disallow_all` → False, else `Protego.parse(body).can_fetch(url, user_agent(settings))`.
9. `fetch` algorithm (all timings with `time.perf_counter`):
   1. Acquire `env.fetch_slots` for the whole call. `robots_allows` fetches robots.txt through the internal `_fetch(env, url, …, slotted=False)` (same algorithm without the global slot), so a page fetch holding a slot never waits on itself; the host slot is taken per hop only (step 3), never across the robots check.
   2. For hop `0..settings.fetch_max_redirects`: run `check_url_allowed(current, env.resolver)` → on `UrlNotAllowed(r)` return `ERROR`, `error=f"url not allowed: {r}"`, `http_status=None`. If `check_robots` and not `await robots_allows(env, current)` → return `ROBOTS_DISALLOWED`, `error="robots.txt disallows this URL"`.
   3. Request headers = `profile_headers(header_profile)`, plus on hop 0 `If-None-Match: etag` and `If-Modified-Since: last_modified` when given. Inside `env.host_limiter.slot(host)`, `async with env.client.stream("GET", current, headers=…) as response`.
   4. Status in `REDIRECT_STATUSES` with a `location` header → `current = str(response.url.join(location))`, next hop. When hops are exhausted → `ERROR`, `error="too many redirects"`.
   5. `304` → `OK`, `not_modified=True`, `body=b""`.
   6. Body read with `aiter_bytes()` up to `max_bytes or settings.fetch_max_bytes`; exceeding → `ERROR`, `error=f"body exceeds {cap} bytes"`, `http_status=status`.
   7. `is_bot_wall(...)` → `BLOCKED`, `error="bot wall"`. Status ≥ 400 → `ERROR`, `error=f"HTTP {status}"`. 2xx → `OK` with `content_type` (header value, lowercase, parameters kept), `etag`, `last_modified`, `final_url=str(response.url)`. Any other status → `ERROR`, `error=f"HTTP {status}"`.
   8. `httpx.TimeoutException` → `ERROR`, `error="timeout"`; any other `httpx.HTTPError` → `ERROR`, `error=type(exc).__name__`. No retries.

**Test fixtures** (`tests/research/conftest.py`): `PUBLIC_IP = "93.184.215.14"`; `fixed_now` → `datetime(2026, 9, 17, 1, 30, tzinfo=UTC)`; `static_resolver(mapping: dict[str, str] | None = None)` → a `Resolver` returning `[mapping.get(host, PUBLIC_IP)]`; `make_env(settings, handler, *, resolver=None, now=None, **overrides)` → `make_environment(settings.model_copy(update=overrides), client=httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False), resolver=resolver or static_resolver(), now=now or (lambda: FIXED_NOW))`.

**Tests to write first** (`test_res_retriever.py`, no DB):
- `test_build_http_client_arguments`: monkeypatch `environment.httpx.AsyncClient` with a recorder class; `build_http_client(settings)` passes `http2=True`, `follow_redirects=False`, `timeout == httpx.Timeout(15.0, connect=5.0)`, `limits.max_connections == 12`.
- `test_user_agent`: `fetch_contact=None` → `"mdcopilot-blog-bot/0.1.0 (+https://www.mdcopilot.health)"` (with `app_version="0.1.0"`, `site_url="https://www.mdcopilot.health"` forced in the test); `fetch_contact="ops@mdcopilot.health"` → `"… (+https://www.mdcopilot.health; ops@mdcopilot.health)"`.
- `test_ssrf_rejections` (parametrised, 8 cases; handler records calls): resolver → `10.0.0.1`, `169.254.169.254`, `::ffff:127.0.0.1`, `100.64.0.1`; URL `http://127.0.0.1/`; URL `https://x.org:8443/` → `"url not allowed: port not allowed"`; URL `file:///etc/passwd` → `"url not allowed: unsupported URL"`; resolver raising `OSError` → `"url not allowed: host did not resolve"`. All: `status == FetchStatus.ERROR`, handler call count 0 (`check_robots=False`).
- `test_redirect_to_private_address_rejected`: `https://a.test/x` → 302 `Location: http://internal.test/admin`; resolver maps `internal.test` → `10.0.0.5` → `ERROR`, `error == "url not allowed: non-public address 10.0.0.5"`, one handler call.
- `test_redirect_limit`: 3 hops then 200 → `OK`, `final_url` is the last URL; 6 hops with `fetch_max_redirects=5` → `error == "too many redirects"`; relative `Location: /next` resolves against the current URL.
- `test_body_cap`: `fetch_max_bytes=1000`, 5000-byte body → `error == "body exceeds 1000 bytes"`, `http_status == 200`.
- `test_bot_wall_variants` (parametrised, 4 cases): 403 → `BLOCKED`, `http_status 403`; 200 + `cf-mitigated: challenge` → `BLOCKED`; 200 with `<title>Just a moment...</title>` → `BLOCKED`; 200 ordinary HTML → `OK`.
- `test_http_errors`: 503 → `ERROR`, `"HTTP 503"`, `http_status 503`; handler raises `httpx.ReadTimeout("t")` → `"timeout"`; `httpx.ConnectError("c")` → `"ConnectError"`.
- `test_conditional_get`: `etag='"abc"'`, `last_modified="Wed, 16 Sep 2026 22:49:45 GMT"` → request carries `If-None-Match` and `If-Modified-Since` with those values; 304 → `OK`, `not_modified is True`, `body == b""`.
- `test_header_profiles`: `browser_like` request has the Chrome `User-Agent` and `Sec-Fetch-Mode: navigate`; `default` request has `User-Agent` starting `mdcopilot-blog-bot/` and `Accept == DEFAULT_ACCEPT`.
- `test_robots_disallow_and_cache`: robots body `User-agent: mdcopilot-blog-bot\nDisallow: /private/\n` → `/private/a` gives `ROBOTS_DISALLOWED` with the page handler not called; `/public` gives `OK`; robots.txt requested exactly once across both fetches.
- `test_robots_status_rules` (parametrised, 3 cases): robots 404 → page `OK`; robots 503 → `ROBOTS_DISALLOWED`; robots `httpx.ConnectError` → `ROBOTS_DISALLOWED`.
- `test_robots_cache_expires`: after the first fetch, `now` moves forward by `robots_cache_hours + 1` hours → robots.txt requested a second time.
- `test_per_host_limit`: `fetch_per_host_limit=2`; 6 concurrent fetches to `a.test` and 6 to `b.test`, async handler sleeping 20 ms and tracking in-flight counts → max in-flight per host == 2 and max in-flight overall ≥ 3.

**Implementation notes.** Streaming with a cap (verified fact 16):
```python
async with env.client.stream("GET", current, headers=headers) as response:
    if response.status_code in REDIRECT_STATUSES and "location" in response.headers:
        current = str(response.url.join(response.headers["location"]))
        continue
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body += chunk
        if len(body) > cap:
            return _error(url, current, f"body exceeds {cap} bytes", response.status_code, started)
```
Protego (verified fact 5): `from protego import Protego`; `Protego.parse(text).can_fetch(url, ua)`.

**Verification.** red `ModuleNotFoundError: No module named 'mdcopilot_blog.research.environment'`; green `26 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Retriever (HTTP/2, per-host limits, Protego, SSRF guard incl. redirects, conditional GET, bot-wall)"; ARCHITECTURE §17 SSRF; RESEARCH_ARCHITECTURE §4.

### RES-7: Fixture transport, environment factory, shipped mock fixture files

**Files.** Create `pkg/research/fixtures.py`; modify `pkg/research/environment.py` (add the factories below); create every file listed in "Mock fixture set" above under `backend/fixtures/mock/{feeds,pubmed,federal_register,fda,pages,pdfs,search}/` (except `search/default.json`) and `backend/fixtures/mock/scenarios/research_feed_down/`, `research_all_blocked/`; create `backend/tests/research/test_res_fixtures.py`.

**Interfaces (produces).**
```python
# fixtures.py
FIXTURE_DIRS: tuple[str, ...]            # ("feeds", "pubmed", "federal_register", "fda", "pages", "pdfs")
VOLATILE_PARAMS: frozenset[str]          # {"api_key", "tool", "email", "reldate", "conditions[publication_date][gte]"}
FIXTURE_RESOLVED_IP = "93.184.215.14"
def default_mock_fixture_root() -> Path  # backend/fixtures/mock (editable install) else <cwd>/fixtures/mock
@dataclass(frozen=True)
class FixtureResponse:
    url: str; status: int; headers: Mapping[str, str]; body_path: Path | None; kind: str   # kind = the FIXTURE_DIRS entry
@dataclass(frozen=True)
class FixtureSet:
    anchor: datetime; responses: Mapping[str, FixtureResponse]   # keyed by urls.fixture_match_key(url, VOLATILE_PARAMS)
def load_fixture_set(root: Path, *, scenario: str | None) -> FixtureSet
class FixtureTransport(httpx.AsyncBaseTransport):
    def __init__(self, fixtures: FixtureSet) -> None
    requested: list[str]
    missing: list[str]
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response
async def fixture_resolver(host: str, port: int) -> list[str]
# environment.py additions
TransportWrapper = Callable[[httpx.AsyncBaseTransport], httpx.AsyncBaseTransport]
@asynccontextmanager
async def open_environment_for(settings: Settings, *, now: Callable[[], datetime], wrap_transport: TransportWrapper | None = None) -> AsyncIterator[ResearchEnvironment]
@asynccontextmanager
async def open_environment(sc: StepContext) -> AsyncIterator[ResearchEnvironment]   # open_environment_for(sc.settings, now=sc.now)
```

**Behaviour rules.**
1. `load_fixture_set`: reads `root/<dir>/index.json` for each `FIXTURE_DIRS` entry that exists, then, when `scenario` is set, `root/scenarios/<scenario>/<dir>/index.json` for each that exists (a scenario with no research overlay is valid). Validation errors raise `ValueError` whose message names the index path: missing or non-ISO `anchor`; anchor different from the first loaded anchor (`"fixture anchors differ: <a> != <b>"`); an entry without `url`/`status`; duplicate match key inside one index; `file` naming a missing file. Overlay entries replace base entries with the same key. No index found at all → `ValueError(f"no research fixtures under {root}")`.
2. `FixtureTransport.handle_async_request`: appends `str(request.url)` to `requested`; a method other than GET → 405, empty body. Known key → `httpx.Response(status, headers=headers, content=<file bytes or b"">, request=request)`. Unknown key → 404, empty body, header `x-fixture-missing: 1`, and the URL is appended to `missing` unless its path ends with `/robots.txt` (robots.txt is 404 → allowed by RES-6 rule 8).
3. `fixture_resolver` returns `[FIXTURE_RESOLVED_IP]` for every host.
4. `open_environment_for`, mock mode (`settings.mock_mode`): fixtures = `load_fixture_set(default_mock_fixture_root(), scenario=settings.mock_scenario)`; transport = `FixtureTransport(fixtures)` (wrapped by `wrap_transport` when given); client = `build_http_client(settings, transport=…)`; resolver `fixture_resolver`; `robots=RobotsCache()` (fresh); `date_shift = now() - fixtures.anchor`; `sleep` = an async no-op; `pubmed_min_interval = 0.0`.
5. Real mode: transport `httpx.AsyncHTTPTransport(http2=True)` only when `wrap_transport` is given (then wrapped), else `None`; resolver `system_resolver`; `robots=ROBOTS_CACHE`; `date_shift=timedelta(0)`; `sleep=asyncio.sleep`; `pubmed_min_interval = 0.1` when `settings.ncbi_api_key` is set, else `0.34`.
6. The client is closed (`aclose`) when the context exits, including on exceptions.
7. Shipped fixture files follow the "Mock fixture set" section exactly: one `feeds/index.json` entry (status 200, `content-type: application/rss+xml`) for each of the 25 enabled `rss` feeds (the FDA press, CMS, HHS, STAT health tech, Fierce, JAMA and medRxiv entries point at their item files; the other 18 point at `empty_rss.xml`); `fda/index.json` one entry for the CSV URL with `last-modified: Fri, 04 Sep 2026 11:54:10 GMT`; `pubmed/`, `federal_register/` entries use the exact request URLs built by RES-10/RES-11 builders; `pages/` and `pdfs/` hold one entry per fetched page in the broad, deep and verification tables (S5 and the `research_all_blocked` pages: status 403, `cf-mitigated: challenge`, `file: null`). Feed item files use the verified quirk shapes (facts 6–8): the CMS item has the `<title><a href="/newsroom/press-releases/cms-announces-prior-authorization-technology-pilot" hreflang="en">…</a></title>`, the URL-encoded `<link>`, `pubDate` `Tue, 09/15/2026 - 10:01` and `<dc:creator><time datetime="2026-09-15T10:01:40-04:00">Tue, 09/15/2026 - 10:01</time></dc:creator>`; the Fierce item `pubDate` is `Sep 16, 2026 5:39am`; the JAMA item carries `<prism:doi>10.1001/jama.2026.90001</prism:doi>` and `pubDate` `Mon, 14 Sep 2026 00:00:00 GMT`; the medRxiv RSS 1.0 item carries `<dc:identifier>doi:10.64898/2026.09.12.26390001</dc:identifier>` and `<dc:date>2026-09-14</dc:date>`. Every page and PDF body says "(fixture)" in its title.

**Tests to write first** (`test_res_fixtures.py`; tmp-dir tests write their own indexes):
- `test_load_rejects_mixed_anchors`: base `feeds` anchor `2026-09-17T01:30:00Z`, base `pages` anchor `2026-09-16T00:00:00Z` → `ValueError` containing `fixture anchors differ`.
- `test_load_rejects_duplicate_keys`: two entries `https://a.test/x?b=1&a=2` and `https://a.test/x?a=2&b=1` → `ValueError` naming `pages/index.json`.
- `test_load_rejects_missing_body_file`: `file: "nope.xml"` → `ValueError` containing `nope.xml`.
- `test_overlay_replaces_base_entry`: base 200 body `ok`, overlay (scenario `research_x`) 503 → transport returns 503 for that URL; with `scenario=None` → 200 `ok`.
- `test_missing_entry_is_404_and_tracked`: unknown page → 404 and in `missing`; `https://a.test/robots.txt` → 404 and not in `missing`; both in `requested`; `POST` → 405.
- `test_volatile_params_ignored`: entry `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=x`; request with `&tool=t&email=e&api_key=k&reldate=7` added → 200.
- `test_shipped_fixture_sets_load`: `load_fixture_set(default_mock_fixture_root(), scenario=s)` for `s` in `None`, `"research_feed_down"`, `"research_all_blocked"` → anchor `datetime(2026, 9, 17, 1, 30, tzinfo=UTC)`; in `research_feed_down` the FDA press releases URL has status 503.
- `test_shipped_feed_index_covers_enabled_rss_feeds`: every enabled `rss` feed URL in `feeds.yaml` has a `feeds` entry with status 200; the FDA CSV URL has an `fda` entry.
- `test_shipped_search_fixture_invariants`: `broad.json`, `deep.json`, `verification.json` validate as `SearchResult`; `provider == "fixture"`, `model == "fixture-search"`; `broad.search_actions == 1`; the source URLs equal the lists in "Mock fixture set"; every broad and deep source URL either has a `pages`/`pdfs` entry, is a `pubmed.ncbi.nlm.nih.gov` URL, or matches a `domains.yaml` rule with `fetch_policy` `metadata_only` or `never`.
- `test_open_environment_for_modes`: mock settings, `now = anchor` → `date_shift == timedelta(0)`, `await env.resolver("x.test", 443) == ["93.184.215.14"]`, `(await env.client.get("https://www.fda.gov/media/178541/download?attachment")).status_code == 200`; `now = anchor + 2 days` → `date_shift == timedelta(days=2)`; real settings (`mock_mode=False`) → `env.resolver is system_resolver`, `env.robots is ROBOTS_CACHE`, `env.pubmed_min_interval == 0.34`, and with `ncbi_api_key=SecretStr("k")` → `0.1`; no network request is issued (the test only builds the environment).

**Implementation notes.** `default_mock_fixture_root()`: `Path(__file__).resolve().parents[3] / "fixtures" / "mock"` when that directory exists, else `Path.cwd() / "fixtures" / "mock"` (same pattern as Phase 1 `default_llm_fixture_root`). The PDF fixture is produced once in a `p2p-res-pdf` throwaway container with a minimal hand-built PDF (single-font text objects), checked with `pypdfium2` text extraction (≥ 200 words), and committed as bytes.

**Verification.** red `ModuleNotFoundError: No module named 'mdcopilot_blog.research.fixtures'`; green `10 passed`; `RES_LINT` exits 0; `docker ps -a --filter name=p2p-res-` prints nothing afterwards.

**Acceptance covered.** §10.1 "full mock fixture set"; RESEARCH_ARCHITECTURE §11 (`FixtureFeedCollector`/`FixtureRetriever` behaviour as a transport-level fixture); §5.8 RES invariants (search fixture provider/model/search_actions).

### RES-8: Extractor (`research/extract.py`)

**Files.** Create `pkg/research/extract.py`, `backend/tests/research/test_res_extract.py`, test data `backend/tests/research/data/extract/{article_full.html, article_jsonld.html, article_meta.html, article_htmldate.html, article_short.html, doc.pdf}` (test-owned copies, not the mock fixture set).

**Interfaces (produces).**
```python
ExtractionMethod = Literal["trafilatura_precision", "trafilatura_recall", "newspaper4k", "pdfium", "none"]
@dataclass(frozen=True)
class DatedValue:
    value: datetime; source: DateSource
@dataclass(frozen=True)
class Extraction:
    text: str | None; word_count: int; title: str | None; sitename: str | None
    published: DatedValue | None; method: ExtractionMethod; access_mode: AccessMode; content_hash: str | None
def structured_date(html: str) -> DatedValue | None          # JSON-LD, then article:published_time meta
def htmldate_date(html: str) -> DatedValue | None
def parse_datetime(value: str) -> datetime | None
def extract_html(html: str, *, url: str, now: datetime) -> Extraction
def extract_pdf(data: bytes) -> Extraction
def looks_like_pdf(content_type: str | None, body: bytes) -> bool
def looks_like_html(content_type: str | None, body: bytes) -> bool
```

**Behaviour rules.**
1. `parse_datetime`: accepts ISO-8601 with or without offset (`datetime.fromisoformat`, after replacing a trailing `Z` with `+00:00` and a `±HHMM` offset with `±HH:MM`), and `YYYY-MM-DD`; naive → UTC; otherwise converted to UTC; unparseable → `None`.
2. `structured_date`: parse the HTML with a stdlib `html.parser.HTMLParser` subclass. JSON-LD: every `<script type="application/ld+json">` body is `json.loads`'d (invalid JSON skipped); walk dicts, lists and `@graph` depth-first; the first `datePublished` string that `parse_datetime` accepts → `DatedValue(…, DateSource.JSONLD)`. Otherwise the first `<meta property="article:published_time">` or `<meta name="article:published_time">` `content` accepted → `DateSource.META`. Otherwise `None`.
3. `htmldate_date`: `htmldate.find_date(html, extensive_search=True, original_date=True, outputformat="%Y-%m-%dT%H:%M:%S%z")` (fact 2) → `parse_datetime` → `DateSource.HTMLDATE`; any exception or `None` → `None`.
4. Plausibility (applies to every date in rules 2–3 and 5): a date later than `now + 1 day` or earlier than `1995-01-01T00:00Z` is ignored and the next date source is tried.
5. `extract_html`:
   1. `_run_trafilatura(html, url, favor_recall=False)` → `(text, title, sitename)` from `bare_extraction(html, url=url, with_metadata=True, favor_precision=True)` (fact 1; `None` result → `("", None, None)`).
   2. When `count_words(text) < FALLBACK_WORD_THRESHOLD` (150): `_run_trafilatura(html, url, favor_recall=True)` (`favor_recall=True`, `favor_precision=False`); kept only when it has more words; method `trafilatura_recall`.
   3. Still `< 150`: `_run_newspaper(html, url)` → `(text, title)` via `newspaper.Article(url)`, `.download(input_html=html)`, `.parse()` (fact 3); any exception → `("", None)`; kept only when it has more words; method `newspaper4k`.
   4. `word_count = count_words(best text)`. `word_count >= MIN_FULL_TEXT_WORDS` (50) → `access_mode FULL_TEXT`, `text` = best text stripped, `content_hash = sha256(text.encode()).hexdigest()`. Otherwise `access_mode METADATA_ONLY`, `text=None`, `content_hash=None`, method `none` when all three produced zero words.
   5. `title` = first non-blank of trafilatura title, newspaper title. `sitename` = trafilatura sitename.
   6. `published` = `structured_date(html)` or `htmldate_date(html)` (rule 4 applied). Feed/API dates are applied by the caller (RES-13) before this value.
6. `extract_pdf`: `pypdfium2.PdfDocument(data)` (fact 4); up to 200 pages, `get_text_range()` per page joined with `"\n"`; `PdfiumError` → `Extraction(text=None, word_count=0, …, method="none", access_mode=METADATA_ONLY)`; ≥ 50 words → `FULL_TEXT`, method `pdfium`; every page, text page and the document are closed; `published=None`, `title=None`, `sitename=None`.
7. `looks_like_pdf`: content type starts with `application/pdf`, or body starts with `b"%PDF-"`. `looks_like_html`: content type contains `html`, or the first non-whitespace body byte is `<` and the body is not PDF.
8. Imports of `trafilatura`, `htmldate`, `newspaper` and `pypdfium2` happen inside the functions (track-wide rule 2).

**Tests to write first** (`test_res_extract.py`, no DB; `NOW = 2026-09-17T01:30Z`):
- `test_full_article_uses_trafilatura_precision`: `article_full.html` (≥ 300 words, no dates) → method `trafilatura_precision`, `access_mode FULL_TEXT`, `word_count >= 300`, `content_hash == sha256(text)`, `published is None`.
- `test_jsonld_date_wins_over_meta`: `article_jsonld.html` (JSON-LD `datePublished 2026-09-14T09:00:00Z` inside `@graph`, meta `2026-09-15T10:00:00-04:00`) → `published.value == 2026-09-14T09:00Z`, `source == JSONLD`.
- `test_meta_date_when_no_jsonld`: `article_meta.html` → `2026-09-15T14:00Z`, `META`.
- `test_htmldate_fallback`: `article_htmldate.html` (visible byline "Published September 11, 2026" only) → `2026-09-11T00:00Z`, `HTMLDATE`.
- `test_future_and_ancient_dates_ignored`: JSON-LD `2026-12-01` and meta `1990-01-01`, visible byline September 11, 2026 → `HTMLDATE`, `2026-09-11`.
- `test_recall_then_newspaper_fallback`: monkeypatch `extract._run_trafilatura` to return 40 words for precision and 90 for recall, and `extract._run_newspaper` to return 400 words → method `newspaper4k`, `word_count == 400`; with newspaper returning 60 words → method `trafilatura_recall`, `word_count == 90`.
- `test_short_page_is_metadata_only`: `article_short.html` (about 20 words) → `access_mode METADATA_ONLY`, `text is None`, `content_hash is None`, `word_count < 50`.
- `test_pdf_extraction`: `doc.pdf` → method `pdfium`, `FULL_TEXT`, `word_count >= 50`; `extract_pdf(b"not a pdf")` → method `none`, `METADATA_ONLY`.
- `test_parse_datetime_forms` (parametrised, 5): `"2026-09-15T10:00:00-0400"` → `14:00Z`; `"2026-09-15T10:00:00Z"`; `"2026-09-11T00:00:00"` (naive → UTC); `"2026-09-11"`; `"yesterday"` → `None`.
- `test_content_sniffing`: `looks_like_pdf("application/pdf", b"")`, `looks_like_pdf(None, b"%PDF-1.4")` true; `looks_like_html("text/html; charset=utf-8", b"")`, `looks_like_html(None, b"  <html>")` true; `looks_like_html("application/json", b"{}")` false.

**Verification.** red `ModuleNotFoundError`; green `14 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Extractor + ledger (trafilatura, htmldate, newspaper4k fallback <150 words, pypdfium2 … date_source, access_mode)"; RESEARCH_ARCHITECTURE §5.

### RES-9: Signals, catalogue loading, RSS/Atom collector

**Files.** Create `pkg/research/signals.py`, `pkg/research/catalog.py`, `pkg/research/collectors/__init__.py`, `pkg/research/collectors/feeds.py`, `backend/tests/research/test_res_feeds.py`.

**Interfaces (produces).**
```python
# signals.py
@dataclass(frozen=True)
class FeedSpec:
    id: uuid.UUID | None; name: str; url: str; kind: FeedKind; group: str; tier: int; source_type: SourceType
    header_profile: HeaderProfile; quirks: Mapping[str, object]; is_preprint: bool; state: Mapping[str, object]
    last_fetched_at: datetime | None
    def hint(self) -> FeedHint
@dataclass(frozen=True)
class Signal:
    url: str; title: str; published_at: datetime | None; date_source: DateSource; discovered_via: DiscoveredVia
    feed_id: uuid.UUID | None; external_ids: Mapping[str, str]; answer_excerpt: str | None
    def to_json(self) -> dict[str, object]
    @classmethod
    def from_json(cls, data: Mapping[str, object]) -> "Signal"
@dataclass(frozen=True)
class FeedOutcome:
    feed: FeedSpec; ok: bool; fetched: bool; signals: list[Signal]; error: str | None; http_status: int | None
    not_modified: bool; new_state: dict[str, object]; items_in_window: int
def in_window(published_at: datetime | None, *, now: datetime, window_days: int) -> bool
def plausible(value: datetime | None, *, now: datetime) -> datetime | None
def newest_first(signals: Sequence[Signal], *, limit: int) -> list[Signal]
# catalog.py
async def load_feed_specs(db: AsyncSession, *, enabled_only: bool = True) -> list[FeedSpec]
async def load_domain_rules(db: AsyncSession) -> dict[str, DomainRule]
async def load_theme_states(db: AsyncSession) -> list[ThemeState]
async def load_pillar(db: AsyncSession, key: str | None) -> ContentPillar | None
def feed_specs_from_seed(items: Sequence[Mapping[str, object]]) -> list[FeedSpec]
def domain_rules_from_seed(items: Sequence[Mapping[str, object]]) -> dict[str, DomainRule]
# collectors/__init__.py
async def collect_feed(env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int) -> FeedOutcome
# collectors/feeds.py
@dataclass(frozen=True)
class RawItem:
    link: str; title: str; published_at: datetime | None; doi: str | None
def parse_feed_entries(body: bytes, feed: FeedSpec, *, now: datetime, date_shift: timedelta) -> tuple[list[RawItem], str | None]
async def collect_rss(env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int) -> FeedOutcome
```

**Behaviour rules.**
1. `Signal.to_json` = `{"url", "title", "publishedAt": ISO string or None, "dateSource": value, "discoveredVia": value, "feedId": str or None, "externalIds": dict, "answerExcerpt": str or None}` (the §3.1 `signals` item keys, nothing else); `from_json` is the exact inverse.
2. `in_window`: `published_at is None` or `published_at >= now - timedelta(days=window_days)`. `plausible`: `None` for values later than `now + 1 day` or earlier than `1995-01-01T00:00Z`. `newest_first`: sort by `published_at` descending with `None` last, stable, first `limit`.
3. `catalog.load_feed_specs` orders by `group_name, name`; `enabled_only` filters `is_enabled`. `load_domain_rules` keys by `domain`. `load_theme_states` returns every theme ordered `sort_order, key`. `*_from_seed` build the same dataclasses from `load_seed_file` items (`id=None`, `state={}`, `last_fetched_at=None`).
4. `collect_feed` dispatches on `feed.kind`: `rss`/`atom` → `collect_rss`; `pubmed` → `pubmed.collect_pubmed_search`; `federal_register` → `federal_register.collect_federal_register`; `fda_ai_devices_csv` → `fda_csv.collect_fda_csv`. Any exception other than `asyncio.CancelledError` becomes `FeedOutcome(ok=False, fetched=True, signals=[], error=f"{type(exc).__name__}: {exc}"[:2000], http_status=None, not_modified=False, new_state=dict(feed.state), items_in_window=0)`.
5. `collect_rss`:
   1. `result = await fetch(env, feed.url, header_profile=feed.header_profile, etag=state.get("etag"), last_modified=state.get("lastModified"), check_robots=False)`.
   2. `status != OK` → `ok=False`, `error=result.error`, `http_status=result.http_status`, `new_state=dict(feed.state)`.
   3. `not_modified` → signals = `Signal.from_json` of `state.get("items", [])` kept by `in_window`, `newest_first(limit=MAX_ITEMS_PER_FEED)`; `ok=True`, `new_state=dict(feed.state)`.
   4. Otherwise `items, error = await asyncio.to_thread(parse_feed_entries, result.body, feed, now=now, date_shift=env.date_shift)`; `error` → `ok=False`, `error=error`, `http_status=result.http_status`.
   5. Items are kept by `in_window`, ordered `newest_first(limit=MAX_ITEMS_PER_FEED)` on their dates; `items_in_window` = number kept.
   6. Signals by `quirks.get("resolve_to")`: `"pubmed"` → DOIs of kept items go to `pubmed.resolve_dois(env, dois)`; a resolved item becomes `Signal(url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", title=summary.title, published_at=summary.published_at or item.published_at, date_source=API if summary.published_at else (FEED if item.published_at else NONE), discovered_via=PUBMED, feed_id=feed.id, external_ids={"pmid": pmid, "doi": doi})`; an unresolved item, or every item when `resolve_dois` raises `PubMedError`, becomes a feed signal with `external_ids={"doi": doi}` when a DOI exists. `"doi"` → feed signals with `external_ids={"doi": doi}` when present. No quirk → feed signal `Signal(url=item.link, title=item.title, published_at=item.published_at, date_source=FEED if dated else NONE, discovered_via=FEED, feed_id=feed.id, external_ids={}, answer_excerpt=None)`.
   7. `new_state = {**feed.state, "etag": result.etag or state etag, "lastModified": result.last_modified or state lastModified, "items": [s.to_json() for s in signals]}` with `None` values removed. `ok=True`.
6. `parse_feed_entries` (sync; `feedparser.parse(body)`):
   1. `parsed.bozo` and no entries → `([], f"unparseable feed: {type(parsed.bozo_exception).__name__}")`.
   2. Link: quirk `link_from_title_href` → first `href="…"` in `entry.title` (fact 6), joined with `feed.url` by `urljoin`; otherwise `entry.link`, else `entry.id` when it is an http(s) URL. Entries without an http(s) link are skipped.
   3. Title: `html.unescape(re.sub(r"<[^>]+>", " ", entry.title))` with whitespace collapsed; blank → the link.
   4. Date, first that yields a value: quirk `date_path` `"<key>@<attr>"` → `entry.get(key)` mapping `.get(attr)` → `extract.parse_datetime`; `published_parsed`, then `updated_parsed` → `datetime(*t[:6], tzinfo=UTC)`; quirk `date_parser == "dateutil"` → `dateutil.parser.parse(entry.published or entry.updated)` (naive → UTC; any exception → none). The value then gets `+ date_shift` and `plausible(…, now=now)`.
   5. DOI (only when `resolve_to` is set): `entry.prism_doi`; else `entry.dc_identifier` with a leading `doi:` removed; else the first `10\.\d{4,9}/[^\s?#"<>]+` match in the link with a trailing `v\d+` removed.

**Tests to write first** (`test_res_feeds.py`, no DB; `make_env` from RES-6 conftest with inline bodies; `NOW = 2026-09-17T01:30Z`, window 7; helper `feed_spec(**overrides)`):
- `test_signal_json_round_trip`: a signal with every field set → `Signal.from_json(s.to_json()) == s`; key set equals the §3.1 list.
- `test_rss_window_and_order`: 3 items dated 2026-09-12, 2026-09-16, 2026-08-01 → 2 signals, `published_at` [09-16, 09-12], `date_source FEED`, `discovered_via FEED`, `feed_id == spec.id`; `items_in_window == 2`; response `ETag: "e1"` → `new_state["etag"] == '"e1"'` and `len(new_state["items"]) == 2`.
- `test_cms_quirks`: the CMS-shaped item (fact 6) with `link_from_title_href` and `date_path "time@datetime"` → url `https://www.cms.gov/newsroom/press-releases/cms-announces-prior-authorization-technology-pilot`, title `CMS Announces Prior Authorization Technology Pilot`, `published_at == 2026-09-15T14:01:40Z`.
- `test_fierce_dateutil_quirk`: `pubDate "Sep 16, 2026 5:39am"` with `date_parser: dateutil` → `2026-09-16T05:39Z`, `FEED`; the same body without the quirk → `published_at is None`, `date_source NONE` (kept: undated items stay in window).
- `test_atom_updated_date`: Atom entry with only `<updated>2026-09-16T08:00:00Z</updated>` → `2026-09-16T08:00Z`.
- `test_medrxiv_doi_quirk`: RSS 1.0 item with `dc:identifier doi:10.64898/2026.09.12.26390001` and `dc:date 2026-09-14`, `resolve_to: doi` → `external_ids == {"doi": "10.64898/2026.09.12.26390001"}`, `published_at == 2026-09-14T00:00Z`.
- `test_jama_resolve_to_pubmed`: handler serves the feed (two items; one with `prism:doi 10.1001/jama.2026.90001`, one without), the esearch JSON (idlist `["40000001"]`) and esummary JSON (fact 10 shape, doi `10.1001/jama.2026.90001`, sortpubdate `2026/09/14 00:00`) → first signal url `https://pubmed.ncbi.nlm.nih.gov/40000001/`, `PUBMED`, `API`, `external_ids == {"pmid": "40000001", "doi": "10.1001/jama.2026.90001"}`; second signal is the item link with `FEED`.
- `test_resolve_failure_falls_back_to_feed_signals`: esearch returns 500 → two feed signals, `ok is True`.
- `test_http_failure_outcome`: 503 → `ok False`, `error == "HTTP 503"`, `http_status 503`, `signals == []`, `new_state == spec.state`.
- `test_unparseable_feed`: body `b"<html><body>no feed"` → `ok False`, error starts with `unparseable feed:`.
- `test_not_modified_reuses_cached_items`: state `items` holds one signal dated 2026-09-16 and one dated 2026-08-01, response 304 → `ok True`, `not_modified True`, signals = only the 09-16 one; request carried `If-None-Match` from state.
- `test_max_items_per_feed`: 30 items dated within window → 20 signals, newest first.
- `test_date_shift_applied`: env `date_shift=timedelta(days=2)`, item dated 2026-09-13 → `published_at == 2026-09-15`.
- `test_collect_feed_dispatch_catches_errors`: monkeypatch `collectors.feeds.collect_rss` to raise `RuntimeError("boom")` → `ok False`, `error == "RuntimeError: boom"`.

**Implementation notes.** `import feedparser  # type: ignore[import-untyped, unused-ignore]` and `from dateutil import parser as dateparser  # type: ignore[import-untyped, unused-ignore]` (fact 13). feedparser is synchronous; large feeds (OpenAI 736 KB, arXiv 648 KB) parse in `asyncio.to_thread`. Collectors never touch the database.

**Verification.** red `ModuleNotFoundError`; green `14 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Collectors (RSS/Atom quirks …)"; RESEARCH_ARCHITECTURE §2 quirks (CMS title href and ISO time, Fierce dates, journals resolved to PubMed, preprints labelled), §4 conditional GET for feeds.

### RES-10: PubMed E-utilities (`research/collectors/pubmed.py`)

**Files.** Create `pkg/research/collectors/pubmed.py`, `backend/tests/research/test_res_pubmed.py`.

**Interfaces (produces).**
```python
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EFETCH_BATCH = 200
DOI_BATCH = 20
@dataclass(frozen=True)
class PubMedSummary:
    pmid: str; title: str; journal: str | None; published_at: datetime | None; doi: str | None; is_preprint: bool
class PubMedError(Exception): ...
class PubMedClient:
    def __init__(self, env: ResearchEnvironment) -> None
    def esearch_url(self, term: str, *, retmax: int, sort: str | None, reldate: int | None) -> str
    def esummary_url(self, pmids: Sequence[str]) -> str
    def efetch_url(self, pmids: Sequence[str]) -> str
    async def esearch(self, term: str, *, retmax: int, sort: str | None, reldate: int | None) -> list[str]
    async def esummary(self, pmids: Sequence[str]) -> dict[str, PubMedSummary]
    async def efetch_abstracts(self, pmids: Sequence[str]) -> dict[str, str]
async def resolve_dois(env: ResearchEnvironment, dois: Sequence[str]) -> dict[str, PubMedSummary]
async def collect_pubmed_search(env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int) -> FeedOutcome
def pmid_from_url(url: str) -> str | None
```

**Behaviour rules.**
1. URLs are `str(httpx.URL(f"{EUTILS_BASE}/<endpoint>.fcgi", params=pairs))` with pairs in this order. `esearch`: `db=pubmed`, `term`, `retmode=json`, `retmax`, `sort` (when given), `datetype=pdat` and `reldate` (when `reldate` given), `tool=mdcopilot-blog`, `email` (when `settings.ncbi_contact_email` is set), `api_key` (when `settings.ncbi_api_key` is set). `esummary`: `db=pubmed`, `id` = pmids sorted numerically joined by `,`, `retmode=json`, `tool`, `email?`, `api_key?`. `efetch`: `db=pubmed`, `id`, `rettype=abstract`, `retmode=xml`, `tool`, `email?`, `api_key?`.
2. Every request waits for spacing first: under an `asyncio.Lock`, `wait = self._last + env.pubmed_min_interval - time.monotonic()`; when `wait > 0`, `await env.sleep(wait)`; then `self._last = time.monotonic()`. `_last` starts at `-inf`. Requests use `fetch(env, url, check_robots=False)`; a non-`OK` result raises `PubMedError(f"{endpoint}: {result.error}")`.
3. `esearch` returns `esearchresult.idlist` (strings); a missing key or invalid JSON raises `PubMedError("esearch: unexpected response")`.
4. `esummary` (fact 10): for each uid in `result.uids`: `title` stripped; `journal` = `fulljournalname` or `source` or `None`; `published_at` = `sortpubdate` parsed with `%Y/%m/%d %H:%M` as UTC, then `env.shift`, else `None`; `doi` = `value` of the first `articleids` item with `idtype == "doi"`; `is_preprint` = `"Preprint"` in `pubtype`. Empty `pmids` → `{}` without a request.
5. `efetch_abstracts` parses XML with `xml.etree.ElementTree.fromstring` in batches of `EFETCH_BATCH`; for each `PubmedArticle`: pmid = `MedlineCitation/PMID` text; parts = each `MedlineCitation/Article/Abstract/AbstractText` as `"".join(el.itertext()).strip()`, prefixed `f"{Label}: "` when the `Label` attribute exists; abstract = non-empty parts joined with `"\n"`; empty abstracts are omitted. `ParseError` raises `PubMedError("efetch: unparseable XML")`.
6. `resolve_dois`: unique DOIs (case-insensitive, first spelling kept); per batch of `DOI_BATCH`, term `" OR ".join(f"{doi}[doi]")`, `retmax=DOI_BATCH`, no sort, no reldate; then `esummary` of the ids; result maps each input DOI whose lowercase equals a summary's lowercase `doi` to that summary.
7. `collect_pubmed_search`: `params = feed.quirks["query_params"]`; no `term` → `ok=False`, `error="pubmed feed has no term"`; `retmax = int(params.get("retmax", "20"))`, `sort = params.get("sort")`, `reldate = window_days`. Signals: `Signal(url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", title, published_at, date_source=API if dated else NONE, discovered_via=PUBMED, feed_id=feed.id, external_ids={"pmid": pmid} plus "doi" when known, answer_excerpt=None)`, filtered by `in_window` and `newest_first(limit=MAX_ITEMS_PER_FEED)`. `PubMedError` → `ok=False`, `error=str(exc)`. `new_state = dict(feed.state)`.
8. `pmid_from_url`: host (after `normalize_host`) `pubmed.ncbi.nlm.nih.gov` and path matching `^/(\d+)/?$` → the digits; otherwise `None`.

**Tests to write first** (`test_res_pubmed.py`, no DB, inline JSON/XML in the verified shapes):
- `test_url_builders`: `esearch_url("x y", retmax=20, sort="pub_date", reldate=7)` without email/key == `"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=x+y&retmode=json&retmax=20&sort=pub_date&datetype=pdat&reldate=7&tool=mdcopilot-blog"`; with `ncbi_contact_email="ops@example.org"` and `ncbi_api_key=SecretStr("k")` the URL ends with `&email=ops%40example.org&api_key=k`; `esummary_url(["42", "7"])` contains `id=7%2C42`.
- `test_esummary_parse`: → `PubMedSummary(pmid="42749085", title=…, journal="International journal of cardiology", published_at=2026-09-16T00:00Z, doi="10.1016/j.ijcard.2026.134786", is_preprint=False)`; with `pubtype ["Preprint"]` → `is_preprint True`.
- `test_efetch_abstract_labels`: two labelled `AbstractText` → `"BACKGROUND: A.\nMETHODS: B."`; an article with no `Abstract` is absent from the dict.
- `test_collect_pubmed_search_signals`: esearch `["40000002"]`, esummary with doi `10.1/x` → one signal, url `https://pubmed.ncbi.nlm.nih.gov/40000002/`, `PUBMED`, `API`, `external_ids == {"pmid": "40000002", "doi": "10.1/x"}`; request query has `reldate=7`.
- `test_pubmed_http_error_is_feed_failure`: esearch 500 → `ok False`, `error == "esearch: HTTP 500"`.
- `test_missing_term`: quirks without `term` → `error == "pubmed feed has no term"`, no request.
- `test_rate_limit_spacing`: `pubmed_min_interval=0.34`, a recording `sleep`, `pubmed.time.monotonic` patched to return `100.0` → three sequential requests record sleeps `[0.34, 0.34]`.
- `test_resolve_dois_batches`: 25 DOIs → 2 esearch requests and 2 esummary requests; returned mapping keys are the input spellings for matched DOIs only.
- `test_pmid_from_url` (parametrised, 3): `https://pubmed.ncbi.nlm.nih.gov/40000003/` → `"40000003"`; `https://pubmed.ncbi.nlm.nih.gov/?term=x` → `None`; `https://example.org/123/` → `None`.

**Verification.** red `ModuleNotFoundError`; green `11 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "PubMed esearch/esummary/efetch"; "PubMed fixture → non-empty abstract, access_mode=abstract_only" (parser half; the ledger half is RES-13/RES-16).

### RES-11: Federal Register and FDA AI-device CSV collectors

**Files.** Create `pkg/research/collectors/federal_register.py`, `pkg/research/collectors/fda_csv.py`, `backend/tests/research/test_res_fr_fda.py`.

**Interfaces (produces).**
```python
# federal_register.py
FR_FIELDS: tuple[str, ...]   # ("title", "abstract", "document_number", "html_url", "publication_date", "type", "agencies")
def federal_register_url(feed: FeedSpec, *, since: date) -> str
async def collect_federal_register(env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int) -> FeedOutcome
# fda_csv.py
REQUIRED_COLUMNS: tuple[str, ...]   # ("Submission Number", "Date of Final Decision")
def submission_url(number: str) -> str | None
async def collect_fda_csv(env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int) -> FeedOutcome
```

**Behaviour rules.**
1. `federal_register_url`: base = `feed.url` without fragment; pairs from `quirks["query_params"]` in insertion order, where a key ending in `[]` whose value contains `,` becomes one pair per comma-separated value; then `("conditions[publication_date][gte]", since.isoformat())`; then `("fields[]", f)` for each `FR_FIELDS`; `str(httpx.URL(base, params=pairs))`.
2. `collect_federal_register`: `since = (now - timedelta(days=window_days)).date()`; `fetch(…, check_robots=False)`; non-`OK` → failure outcome. JSON without a `results` list → `ok=False`, `error="unexpected federal register response"`. Each result with an http(s) `html_url` → `Signal(url=html_url, title=title, published_at=env.shift(datetime.combine(date.fromisoformat(publication_date), time(0), UTC)), date_source=API, discovered_via=FEDERAL_REGISTER, feed_id=feed.id, external_ids={"frDocumentNumber": document_number}, answer_excerpt=None)`; invalid dates → `published_at=None`, `date_source=NONE`; then `in_window` and `newest_first(limit=MAX_ITEMS_PER_FEED)`. `new_state = dict(feed.state)`.
3. `collect_fda_csv`:
   1. `feed.last_fetched_at` set and `now - feed.last_fetched_at < FDA_CSV_POLL_INTERVAL` → `ok=True`, `fetched=False`, no request, `signals=[]`, `new_state=dict(feed.state)`.
   2. `fetch` with state `etag`/`lastModified`, `check_robots=False`; non-`OK` → failure; `not_modified` → `ok=True`, `signals=[]`, `new_state=dict(feed.state)`.
   3. Body decoded `utf-8-sig` (`errors="replace"`) and read with `csv.DictReader`; header names are stripped and matched case-insensitively; missing required columns → `ok=False`, `error="FDA CSV missing columns: " + ", ".join(missing)`.
   4. Rows: number stripped (blank rows skipped); decision date `datetime.strptime(v, "%m/%d/%Y")` at 00:00 UTC or `None`; device from `Device`, company from `Company` (blank when absent).
   5. `state.get("knownIds")` not a list → baseline: `signals=[]`, `new_state["knownIds"] = sorted(all numbers)`.
   6. Otherwise new rows = numbers not in `knownIds`, ordered decision date descending (None last) then number; first `FDA_CSV_MAX_NEW_ROWS`; rows whose `submission_url` is `None` are skipped. `published_at` = `email.utils.parsedate_to_datetime(result.last_modified)` in UTC plus `env.shift`, else `None`. Signal: `title = f"FDA AI-enabled device list adds {device} ({company}; {number}; decision {d:%Y-%m-%d})"` (`decision unknown` when undated), `date_source=API` when dated else `NONE`, `discovered_via=FDA_CSV`, `external_ids={"fdaSubmissionNumber": number}`; then `in_window`.
   7. `new_state = {**feed.state, "knownIds": sorted(set(known) | all numbers), "etag": …, "lastModified": …}` (None values removed).
4. `submission_url`: `^K\d{6}$` → `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=<n>`; `^DEN\d{6}$` → `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?ID=<n>`; `^P\d{6}(/S\d+)?$` → `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=<P number without supplement>`; otherwise `None`.

**Tests to write first** (`test_res_fr_fda.py`, no DB):
- `test_federal_register_url`: the seeded Federal Register spec, `since=date(2026, 9, 10)` → exactly `https://www.federalregister.gov/api/v1/documents.json?conditions%5Bagencies%5D%5B%5D=food-and-drug-administration&conditions%5Bagencies%5D%5B%5D=centers-for-medicare-medicaid-services&order=newest&per_page=20&conditions%5Bpublication_date%5D%5Bgte%5D=2026-09-10&fields%5B%5D=title&fields%5B%5D=abstract&fields%5B%5D=document_number&fields%5B%5D=html_url&fields%5B%5D=publication_date&fields%5B%5D=type&fields%5B%5D=agencies`.
- `test_federal_register_signals`: one result (`publication_date 2026-09-15`, `document_number 2026-19001`) and one dated 2026-08-01 → one signal, `published_at == 2026-09-15T00:00Z`, `FEDERAL_REGISTER`, `API`, `external_ids == {"frDocumentNumber": "2026-19001"}`.
- `test_federal_register_bad_json`: `{"count": 0}` → `error == "unexpected federal register response"`.
- `test_fda_csv_baseline`: 3-row CSV (fact 9 header), empty state → `signals == []`, `new_state["knownIds"] == ["DEN260002", "K260001", "P260003"]`, `new_state["lastModified"]` set.
- `test_fda_csv_diff`: state `knownIds ["K260001"]`, `Last-Modified: Wed, 16 Sep 2026 10:00:00 GMT` → 2 signals, urls for `DEN260002` (denovo) and `P260003` (pma), `published_at == 2026-09-16T10:00Z`, `FDA_CSV`, titles start with `FDA AI-enabled device list adds`; `knownIds` has 3 entries.
- `test_fda_csv_poll_interval`: `last_fetched_at = NOW - 2 days` → `fetched False`, handler never called.
- `test_fda_csv_missing_columns`: header `Device,Company` → `error == "FDA CSV missing columns: Submission Number, Date of Final Decision"`.
- `test_submission_url` (parametrised, 5): `K253628`, `DEN250001`, `P200003`, `P200003/S012` (→ `id=P200003`), `BK123` (→ `None`).

**Verification.** red `ModuleNotFoundError`; green `12 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Collectors (… Federal Register, FDA CSV diff)"; RESEARCH_ARCHITECTURE §2 (FR JSON with `publication_date`; weekly conditional GET for the CSV compared by submission number).

### RES-12: Search runner with retries (`research/search.py`)

**Files.** Create `pkg/research/search.py`, `backend/tests/research/test_res_search.py`.

**Interfaces (consumes).** `StepContext.gateway.search(query, *, ctx)`, `StepContext.settings.max_parallel_searches`, `SearchQuery`, `SearchResult`, `BudgetExceeded`, `ProviderNotAvailable`, `ResearchEnvironment.sleep`, `PlannedQuery`.

**Interfaces (produces).**
```python
TRANSIENT_STATUS_CODES: frozenset[int]   # {408, 429, 500, 502, 503, 504}
TRANSIENT_CLASS_NAMES: frozenset[str]    # {"APIConnectionError", "APITimeoutError"}
SearchMode = Literal["broad", "deep", "verification"]
@dataclass(frozen=True)
class QueryOutcome:
    planned: PlannedQuery; status: Literal["ok", "failed"]; search_actions: int; source_urls: list[str]
    source_titles: dict[str, str]; answer_excerpt: str | None; error: str | None; attempts: int
def is_transient_search_error(exc: BaseException) -> bool
async def run_search_queries(sc: StepContext, env: ResearchEnvironment, queries: Sequence[PlannedQuery], *, mode: SearchMode,
                             recency_days: int | None, allowed_domains: Sequence[str], ctx: CallContext) -> list[QueryOutcome]
def outcome_signals(outcome: QueryOutcome, *, discovered_via: DiscoveredVia, keep: Callable[[str], bool] | None = None) -> list[Signal]
def query_json(outcome: QueryOutcome, *, source_count: int) -> dict[str, object]
```

**Behaviour rules.**
1. At most `sc.settings.max_parallel_searches` queries run at once (`asyncio.Semaphore`); outcomes are returned in input order.
2. Each query sends `SearchQuery(text=planned.text, mode=mode, recency_days=recency_days, allowed_domains=list(allowed_domains), max_results=10)` through `sc.gateway.search(query, ctx=ctx)` (the gateway records every attempt in `blog_llm_calls`).
3. Success → `status="ok"`; `source_urls` = `result.sources` followed by citation URLs not yet present, keeping only `urls.is_http_url` URLs, deduplicated by `canonicalize_url`, first 10; `source_titles[url]` = the first non-blank citation title for that URL; `answer_excerpt = result.answer_text[:ANSWER_EXCERPT_CHARS]` (None when blank); `search_actions = result.search_actions`; `error=None`.
4. `BudgetExceeded` propagates immediately (the step fails; no further queries start).
5. `is_transient_search_error`: true for `httpx.TransportError`, `httpx2.TransportError`, any exception whose `status_code` attribute is in `TRANSIENT_STATUS_CODES`, and any exception whose class name is in `TRANSIENT_CLASS_NAMES`; false otherwise.
6. A transient error with attempts left (`SEARCH_ATTEMPTS = 3`) sleeps `env.sleep(SEARCH_BACKOFF_SECONDS[attempt - 1])` and retries. Any other error, or the last transient failure → `status="failed"`, `search_actions=0`, `source_urls=[]`, `error=f"{type(exc).__name__}: {exc}"[:500]`, `attempts` = attempts made.
7. `outcome_signals`: for each kept URL in order → `Signal(url, title=source_titles.get(url, url), published_at=None, date_source=NONE, discovered_via=discovered_via, feed_id=None, external_ids={}, answer_excerpt=outcome.answer_excerpt)`; failed outcomes → `[]`.
8. `query_json` = `{"text", "themeKey": planned.theme_key, "status", "searchActions", "sourceCount": source_count, "error"}` (the §3.1 `queries` item keys, nothing else).

**Tests to write first** (`test_res_search.py`, no DB; `sc` is a `SimpleNamespace(gateway=FakeGateway(script), settings=settings)`; `env` from `make_env` with a recording `sleep`):
- `test_transient_classification` (parametrised, 6): `httpx.ConnectError("x")` → True; `httpx2.ReadTimeout("x")` → True; exception with `status_code=503` → True; `status_code=400` → False; an exception class named `APITimeoutError` → True; `ProviderNotAvailable("x")` → False.
- `test_ok_query_collects_sources`: result `sources [A, B, A + "?utm_source=x"]`, citations `[C titled "C"]`, answer of 2000 characters → `source_urls == [A, B, C]`, `source_titles == {C: "C"}`, `len(answer_excerpt) == 1500`, `search_actions == 1`, `attempts == 1`.
- `test_transient_retry_then_success`: first call raises an error with `status_code=503`, second succeeds → `ok`, `attempts == 2`, sleeps `[0.5]`.
- `test_transient_exhausted`: always 503 → `failed`, `attempts == 3`, sleeps `[0.5, 1.0]`, `error` starts with the class name.
- `test_non_transient_fails_once`: `ProviderNotAvailable` → `failed`, `attempts == 1`, no sleep.
- `test_budget_exceeded_propagates`: `BudgetExceeded` raised → `pytest.raises(BudgetExceeded)`.
- `test_order_and_concurrency`: 10 queries, `max_parallel_searches=3`, fake search sleeping 10 ms and tracking in-flight → max in-flight 3; outcome texts in input order.
- `test_search_query_fields`: the recorded `SearchQuery` has `mode="verification"`, `recency_days=None`, `allowed_domains=["cdc.gov", "fda.gov"]`, `max_results=10`; the recorded `ctx` is the one passed.
- `test_outcome_signals_and_query_json`: `outcome_signals(ok, discovered_via=SEARCH, keep=lambda u: "b.test" not in u)` drops the `b.test` URL, titles fall back to the URL, `answer_excerpt` copied; `query_json(ok, source_count=2)` key set equals the §3.1 list and `sourceCount == 2`.

**Verification.** red `ModuleNotFoundError`; green `14 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Failure: … search 5xx → partial coverage" (retry and failure recording); RESEARCH_ARCHITECTURE §3 "When a search call fails" steps 1–2.

### RES-13: Source ledger (`research/ledger.py`)

**Files.** Create `pkg/research/ledger.py`, `backend/tests/research/test_res_ledger.py`.

**Interfaces (consumes).** RES-1 `canonicalize_url`, `url_hash`; RES-2 `classify_source`, `resolve_publisher`, `relevance_score`, `DomainRule`; RES-6 `fetch`; RES-8 `extract_html`, `extract_pdf`, `looks_like_pdf`, `looks_like_html`; RES-9 `Signal`, `FeedSpec`, `in_window`; RES-10 `PubMedClient`, `PubMedError`, `pmid_from_url`; `db.models.LedgerSource`.

**Interfaces (produces).**
```python
DISCOVERY_PRIORITY: Mapping[DiscoveredVia, int]  # PUBMED 0, FEED 1, FEDERAL_REGISTER 2, FDA_CSV 3, SEARCH 4, DEEP_SEARCH 4, VERIFICATION 4
@dataclass
class StageTimer:
    extraction_ms: int = 0   # each asyncio.to_thread(extract_html|extract_pdf) adds its elapsed milliseconds
@dataclass(frozen=True)
class Candidate:
    signal: Signal; canonical_url: str; url_hash: str; classification: Classification; pmid: str | None; pre_score: float
@dataclass(frozen=True)
class SourceDraft:
    url: str; canonical_url: str; url_hash: str; title: str; publisher: str; domain: str; source_type: SourceType; tier: int
    published_at: datetime | None; date_source: DateSource; retrieved_at: datetime; access_mode: AccessMode
    fetch_status: FetchStatus; http_status: int | None; content_hash: str | None; word_count: int; text_snapshot: str | None
    is_preprint: bool; external_ids: dict[str, str]; discovered_via: DiscoveredVia; relevance_score: float; fetched: bool
@dataclass(frozen=True)
class Reused:
    source_id: uuid.UUID; url_hash: str
@dataclass(frozen=True)
class UpsertOutcome:
    source_id: uuid.UUID; created: bool; refreshed: bool; fetched: bool; fetch_status: FetchStatus
def merge_signals(signals: Sequence[Signal]) -> list[Signal]
def select_candidates(signals: Sequence[Signal], *, rules: Mapping[str, DomainRule], feeds: Mapping[uuid.UUID, FeedSpec],
                      keywords: frozenset[str], now: datetime, window_days: int, limit: int = MAX_LEDGER_CANDIDATES) -> list[Candidate]
def needs_retrieval(existing: LedgerSource | None, *, now: datetime) -> bool
async def load_existing(db: AsyncSession, hashes: Iterable[str]) -> dict[str, LedgerSource]
async def retrieve(env: ResearchEnvironment, candidates: Sequence[Candidate], *, existing: Mapping[str, LedgerSource],
                   keywords: frozenset[str], now: datetime, window_days: int, timer: StageTimer | None = None) -> list[SourceDraft | Reused]
async def upsert_sources(db: AsyncSession, items: Sequence[SourceDraft | Reused], *, existing: Mapping[str, LedgerSource],
                         research_run_id: uuid.UUID) -> list[UpsertOutcome]
```

**Behaviour rules.**
1. `merge_signals`: signals whose URL raises `InvalidUrl` are skipped. Groups by canonical URL, in order of first appearance. Representative = lowest `DISCOVERY_PRIORITY`, ties by input order; merged `url`, `discovered_via`, `feed_id` come from it; `title` = representative title unless it equals its URL, then the first title (priority order) that is not a URL; `published_at`/`date_source` = first signal in priority order that has a date; `external_ids` = union, lower-priority keys never overwrite; `answer_excerpt` = first non-None in input order.
2. `select_candidates`: per merged signal, `classification = classify_source(url, rules=rules, feed=feeds[feed_id].hint() if feed_id in feeds else None)`; `pmid = external_ids.get("pmid") or pmid_from_url(url)`; a dated signal outside `in_window` is dropped; `pre_score = relevance_score(text=title, keywords=keywords, published_at=…, now=now, window_days=window_days, tier=classification.tier)`; result sorted by `pre_score` descending (stable), first `limit`.
3. `needs_retrieval`: no row → True; `snapshot_purged_at` set → False; `access_mode` `full_text`/`abstract_only` → False; `now - retrieved_at >= REFETCH_AFTER` → True; otherwise False. Candidates with an existing row and `needs_retrieval False` become `Reused` and make no request.
4. `retrieve` (candidates processed concurrently with `asyncio.gather`; page fetches are bounded inside `fetch`; result order = candidate order; `now` is the retrieval time):
   1. **PubMed** (`pmid` set): one `PubMedClient` for the call; `esummary` for pmids whose signal is undated or whose title equals its URL; `efetch_abstracts` for all pmids (batched). Abstract found → `access_mode ABSTRACT_ONLY`, `fetch_status OK`, `http_status 200`, `text_snapshot` = abstract, `word_count = count_words(abstract)`, `content_hash = sha256(abstract)`; efetch succeeded without an abstract → `METADATA_ONLY`, `OK`, `200`, no text; `PubMedError` → `METADATA_ONLY`, `fetch_status ERROR`, `http_status None`. Summary fills a missing title and date (`date_source API`), sets `journal` for the publisher, sets `is_preprint` when the summary says so, and adds `pmid`/`doi` to `external_ids`. `fetched=False`.
   2. **Policy** `never` or `metadata_only` without a pmid → `METADATA_ONLY`, `NOT_FETCHED`, `http_status None`, `word_count 0`, `fetched=False`.
   3. **Fetch** → `fetch(env, signal.url, header_profile=classification.header_profile, check_robots=True)`, `fetched=True`. `OK` and `looks_like_pdf` → `await asyncio.to_thread(extract_pdf, body)`; `OK` and `looks_like_html` → `await asyncio.to_thread(extract_html, body.decode("utf-8", errors="replace"), url=final_url, now=now)`; `OK` with another content type → `METADATA_ONLY`, `fetch_status ERROR`; `BLOCKED`, `ROBOTS_DISALLOWED`, `ERROR` → `METADATA_ONLY` with that status and `http_status`. Extraction results set `access_mode`, `text_snapshot`, `word_count`, `content_hash`; a `METADATA_ONLY` extraction keeps `fetch_status OK`.
   4. **Dates**: the signal's date and `date_source` win; else the extraction's `published` (already plausibility-checked) shifted by `env.date_shift`; else `None`/`NONE`.
   5. **Title**: signal title unless it equals the URL, else extraction title, else canonical URL; truncated to 1000 characters. **Publisher**: `resolve_publisher(rule_publisher=…, journal=…, feed_publisher=…, sitename=…, domain=classification.domain)`. `is_preprint = classification.is_preprint or summary.is_preprint`. `relevance_score` over `title + " " + (text_snapshot or "")[:2000]`. `retrieved_at = now`. `discovered_via` = merged signal's.
5. `load_existing` selects `LedgerSource` rows whose `url_hash` is in the set, keyed by hash.
6. `upsert_sources` (flush only; the caller commits):
   1. `Reused` → `UpsertOutcome(source_id, created=False, refreshed=False, fetched=False, fetch_status=<row status>)`.
   2. Draft without an existing row → `insert(LedgerSource).values(…, first_research_run_id=research_run_id).on_conflict_do_nothing(index_elements=["url_hash"]).returning(LedgerSource.id)`; no id returned → select the id by hash; `created` = id returned.
   3. Draft with an existing row (`needs_retrieval` was True): text draft → UPDATE `text_snapshot, content_hash, word_count, access_mode, fetch_status, http_status, retrieved_at, relevance_score`; metadata draft → UPDATE `fetch_status, http_status, retrieved_at` only; both → also `published_at`/`date_source` when the row's `published_at` is NULL, and `external_ids` = draft ids overlaid by the row's ids. Existing text is never cleared. `refreshed=True`.
   4. Outcomes are returned in input order.

**Tests to write first** (`test_res_ledger.py`; `NOW = 2026-09-17T01:30Z`; rules from `domains.yaml` via `domain_rules_from_seed`):
- `test_merge_signals_priority`: the same URL from search (undated, excerpt "E") and from a feed (dated 2026-09-16, with `?utm_campaign=rss`) → one signal, `discovered_via FEED`, `published_at 2026-09-16`, `answer_excerpt "E"`, `url` = the feed URL.
- `test_merge_skips_invalid_urls`: `ftp://x/y` dropped.
- `test_select_candidates_window_and_rank`: signals dated 2026-09-16, 2026-08-01 (dropped), undated (kept); `limit=1` → the one with the highest `pre_score` (the dated tier-1 fda.gov page).
- `test_needs_retrieval` (parametrised, 5): no row → True; purged row → False; full_text row retrieved 30 days ago → False; metadata_only retrieved 25 h ago → True; metadata_only retrieved 1 h ago → False.
- `test_retrieve_html_full_text` (MockTransport): FDA feed signal dated 2026-09-16T19:30Z, page of 300 words → `FULL_TEXT`, `OK`, `http_status 200`, `date_source FEED`, `publisher "U.S. Food and Drug Administration"`, `tier 1`, `content_hash` of the text, `fetched True`.
- `test_retrieve_search_page_uses_page_date`: undated search signal, page with JSON-LD 2026-09-16T15:30Z → `date_source JSONLD`, `published_at 2026-09-16T15:30Z`.
- `test_retrieve_blocked_page`: hhs.gov page 403 + `cf-mitigated: challenge` → `METADATA_ONLY`, `BLOCKED`, `http_status 403`, `text_snapshot None`, `word_count 0`, feed date kept; the request used the `browser_like` User-Agent.
- `test_retrieve_policy_metadata_only_is_not_fetched`: nih.gov search signal → `NOT_FETCHED`, `METADATA_ONLY`, no request issued.
- `test_retrieve_pubmed_abstract`: PubMed signal `pmid 40000002` (dated, titled) → one efetch request, no esummary request; `ABSTRACT_ONLY`, non-empty `text_snapshot`, `OK`, `publisher` = the esummary-less fallback `"PubMed"`; a search signal `https://pubmed.ncbi.nlm.nih.gov/40000003/` → esummary requested, `published_at 2026-09-10T00:00Z`, `date_source API`, `publisher` = journal name.
- `test_retrieve_pdf`: `application/pdf` body → `FULL_TEXT`, `word_count >= 50`.
- `test_retrieve_reuses_existing_text_row`: existing full_text row for the hash → `Reused`, no request.
- `test_upsert_insert_then_conflict` (DB, `db_session` plus a research run from `make_research_graph`): new draft → `created True`, row fields equal the draft, `first_research_run_id` set; the same draft again with an empty `existing` map → `created False`, same id.
- `test_upsert_refresh_upgrades_metadata_only` (DB): existing metadata_only row with `published_at NULL` and `first_research_run_id = R1`; text draft dated 2026-09-15 → `refreshed True`; row is `FULL_TEXT` with text, `published_at 2026-09-15`, `first_research_run_id` still `R1`.
- `test_upsert_never_clears_text` (DB): existing full_text row, metadata draft → `text_snapshot` unchanged, `fetch_status` updated.

**Implementation notes.** `from sqlalchemy.dialects.postgresql import insert` for `on_conflict_do_nothing(index_elements=["url_hash"])`. CPU-bound extraction runs in `asyncio.to_thread`; when `timer` is given, the elapsed milliseconds of each extraction call are added to `timer.extraction_ms`.

**Verification.** red `ModuleNotFoundError`; green `18 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Extractor + ledger (… tiers, canonical URLs, `date_source`, `access_mode`)", "blocked page → metadata-only", "PubMed fixture → non-empty abstract, `access_mode=abstract_only`"; RESEARCH_ARCHITECTURE §5 (blocked → metadata-only, abstracts → abstract_only), §7 ledger row fields.

### RES-14: Research Analyst agent, prompt, default LLM fixture

**Files.** Create `pkg/agents/research_analyst.py`, `backend/prompts/research/synthesize.v1.md` (drafted as `synthesize.v1.md.wip`, renamed when complete), `backend/fixtures/mock/llm/research/research_synthesize.json`, `backend/fixtures/mock/scenarios/research_unknown_marker/llm/research/research_synthesize.json`, `backend/tests/research/test_res_research_analyst.py`; add `FakeRecorder` and `ScriptedFactory` helpers to `backend/tests/research/conftest.py`.

**Interfaces (consumes).** `AgentSpec`, `AgentResult`, `CallContext`, `LLMGateway.run(..., route_override, prompt_version, output_check)`, `agents.common.{UNTRUSTED_NOTICE, NumberedSource, untrusted_block, render_source_list, resolve_markers}`, `domain.errors.{UnknownCitationMarker, OutputRejected}`, `domain.contracts.{Contract, Marker, UnitScore, ClaimType}`, `domain.claim_rules.{FindingCategory, MAX_FINDINGS}`.

**Interfaces (produces).**
```python
class AnalystFinding(Contract):
    claim: str = Field(min_length=1, max_length=1000)
    evidence: str = Field(min_length=1, max_length=2000)
    confidence: UnitScore
    category: FindingCategory
    claim_type: ClaimType
    importance: Literal["high", "normal"]
    self_reported: bool
    markers: list[Marker] = Field(min_length=1, max_length=8)
class AnalystDigest(Contract):
    findings: list[AnalystFinding] = Field(max_length=MAX_FINDINGS)
RESEARCH_ANALYST_SPEC: AgentSpec[AnalystDigest]   # AgentSpec(name=AgentName.RESEARCH, version="1", prompt_name="research/synthesize", output_type=AnalystDigest, max_output_tokens=6000, output_retries=1, timeout_seconds=120.0, reasoning="low")
MAX_HINTS = 10
@dataclass(frozen=True)
class SearchHint:
    query: str; excerpt: str
def build_variables(*, pillar_name: str | None, pillar_topics: Sequence[str], window_days: int, today: date) -> dict[str, object]
def build_user_prompt(*, numbered: Sequence[NumberedSource], hints: Sequence[SearchHint]) -> str
def digest_markers(digest: AnalystDigest) -> list[str]
def marker_check(numbered: Sequence[NumberedSource]) -> Callable[[AnalystDigest], None]
async def run_research_analyst(gateway: LLMGateway, *, ctx: CallContext, numbered: Sequence[NumberedSource], hints: Sequence[SearchHint],
                               variables: Mapping[str, object], route_override: Sequence[str] | None,
                               prompt_version: int | None) -> AgentResult[AnalystDigest]
```

**Behaviour rules.**
1. `build_variables` returns exactly `{"untrusted_notice": UNTRUSTED_NOTICE, "pillar_name": pillar_name or "none (general scan)", "pillar_topics": ", ".join(pillar_topics) or "none", "window_days": window_days, "today": today.isoformat(), "max_findings": MAX_FINDINGS}`.
2. `build_user_prompt` = `"Numbered sources (cite by marker only):\n\n" + render_source_list(numbered, include_text=True) + "\n\nSearch answer hints (unverified summaries; never cite them):\n\n" + hint blocks`, where hint `i` (1-based, first `MAX_HINTS`) is `untrusted_block(f"H{i}", f"Query: {hint.query}\n{hint.excerpt}")` joined by `"\n\n"`, or the text `none` when there are no hints.
3. `digest_markers`: every marker of every finding, unique, first-appearance order.
4. `marker_check(numbered)` returns a closure that calls `resolve_markers(digest_markers(output), numbered)` and turns `UnknownCitationMarker` into `OutputRejected(f"unknown markers: {', '.join(exc.args[0])}")` (§0.2, §5.6).
5. `run_research_analyst` calls `gateway.run(RESEARCH_ANALYST_SPEC, variables=variables, user_prompt=build_user_prompt(numbered=numbered, hints=hints), ctx=ctx, route_override=route_override, prompt_version=prompt_version, output_check=marker_check(numbered))` and returns its result. The module never imports `pydantic_ai` or `db`.
6. Prompt file `backend/prompts/research/synthesize.v1.md`, exactly:
```markdown
---
name: research/synthesize
version: 1
agent: research
output: AnalystDigest
variables:
  - untrusted_notice
  - pillar_name
  - pillar_topics
  - window_days
  - today
  - max_findings
---
You are the Research Analyst for a healthcare and AI editorial team. Today is {{ today }}. The research window is the last {{ window_days }} days. The pillar of the day is {{ pillar_name }} (topics: {{ pillar_topics }}).

{{ untrusted_notice }}

Read the numbered sources and return at most {{ max_findings }} findings, most important first. Each finding has:
- claim: one sentence stating what the sources say, with no citation markers inside the text;
- evidence: a short quotation or close paraphrase from the cited source text that supports the claim;
- markers: the source markers (S1, S2, ...) that support the claim; use only markers from the numbered list, never URLs, titles or hint ids;
- claim_type: FACT (verifiable and stated by a source), ANALYSIS (an interpretation), OPINION (a view attributed to someone), PREDICTION (a statement about the future) or MARKETING_CLAIM (an organisation promoting its own product or results);
- importance: high for statistics, regulatory actions, trial results and workforce numbers; normal otherwise;
- self_reported: true when the claim is an organisation's statement about its own product, service or results;
- category: regulatory, clinical_research, workforce, product_announcement, policy, market, technology, operations or other;
- confidence: 0 to 1, how well the cited text supports the claim.

Rules:
- A source marked as metadata only supports only that the item was published or announced.
- A source without a publication date cannot support a FACT about current events.
- Label preprint findings as ANALYSIS unless a peer-reviewed source is also cited.
- Search answer hints are unverified summaries for orientation only; never cite them and never take facts from them that the numbered sources do not state.
- Do not invent numbers, quotes, people or events.
```
7. Default LLM fixture `research_synthesize.json` (Phase 1 form): `usage {"input_tokens": 30000, "output_tokens": 2500}`; `output.findings` exactly 6 items in camelCase: (0) `claimType FACT`, `importance high`, `category regulatory`, `selfReported false`, `markers ["S1"]`, confidence 0.9; (1) `FACT`, `normal`, `clinical_research`, `["S3"]`, 0.8; (2) `ANALYSIS`, `normal`, `workforce`, `["S2", "S4"]`, 0.7; (3) `FACT`, `high`, `policy`, `["S5"]`, 0.6; (4) `PREDICTION`, `normal`, `market`, `["S2"]`, 0.5; (5) `FACT`, `normal`, `technology`, `["S1", "S3"]`, 0.8. Claims and evidence are consistent with the fixture page text of the cited sources and contain no marker text. With the default ledger order this yields after claim rules: `[FACT, FACT, ANALYSIS, ANALYSIS (rule high_importance_evidence, S5 is metadata-only), PREDICTION, FACT]`.

**Tests to write first** (`test_res_research_analyst.py`; conftest helpers: `FakeRecorder` with `records: list[CallRecord]`, `async record(rec) -> uuid`, `async run_cost(run_id) -> Decimal(0)`, `async budget_spent(ctx) -> Decimal(0)`; `ScriptedFactory(scripts: dict[str, Callable[[], Model]])` building `FunctionModel`s whose responses use `ToolCallPart(info.output_tools[0].name, payload)` as in Phase 1 `tests/unit/test_gateway.py`; gateway = `LLMGateway(settings=settings, prompts=PromptRegistry.from_directory(default_prompt_root(), agents=["research"]), recorder=FakeRecorder(), model_factory=factory, search_provider=FixtureSearchProvider())`; `numbered` = two `NumberedSource`s S1, S2):
- `test_spec_values`: name `AgentName.RESEARCH`, `prompt_name "research/synthesize"`, `output_type is AnalystDigest`, `max_output_tokens 6000`, `output_retries 1`, `timeout_seconds 120.0`, `reasoning "low"`, `version "1"`.
- `test_output_schema_limits`: camelCase payload (`claimType`, `selfReported`) validates; `markers []` → `ValidationError`; `markers ["S0"]` and `["https://x.org"]` → `ValidationError`; 26 findings → `ValidationError`; `category "gossip"` → `ValidationError`.
- `test_prompt_renders_with_variables`: rendered text contains `UNTRUSTED_NOTICE`, `Governance & Clinical Autonomy`, `last 7 days`, `at most 25 findings`; `render` with `max_findings` missing → `PromptRegistryError`.
- `test_user_prompt_blocks`: contains `<untrusted_source id="S1">` and `<untrusted_source id="H1">` holding `Query: q1`; 12 hints → only `H1`…`H10`; no hints → the section ends with `none`.
- `test_default_fixture_matches_invariants`: `FixtureRegistry.default().load("research", "research/synthesize")["output"]` validates as `AnalystDigest`; `digest_markers ⊆ {S1..S6}`; finding 0 is high `FACT` citing `S1`; the scenario fixture differs only in finding 0 markers `["S99"]`.
- `test_unknown_marker_retried_then_valid`: one route entry whose model answers `markers ["S9"]` first and a valid digest second → success, 2 model requests, `FakeRecorder.records` has 1 row with `status OK`.
- `test_invalid_output_advances_to_next_model`: `route_override=["google:model-a", "openai:model-b"]`; model-a always answers `S99`, model-b valid → `result.attempts == 2`; records: `[ERROR (error_class "UnexpectedModelBehavior", provider_requested "google"), OK (fallback_from "google:model-a")]`; model-a was called twice (1 output retry).
- `test_route_exhausted_when_all_invalid`: both entries answer `S99` → `RouteExhausted`.

**Verification.** Before and after writing the prompt: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py tests/unit/test_prompt_registry.py` → all passed. `RES_PYTEST tests/research/test_res_research_analyst.py`: red `ModuleNotFoundError: No module named 'mdcopilot_blog.agents.research_analyst'`; green `8 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Research Analyst with claim rules in code" (agent half), "zero findings citing a URL outside the ledger (enforced and tested)", "invalid analyst output retried then next model"; §0.2 markers; §5.6 agent spec row; ARCHITECTURE §7.1 untrusted blocks; §5.8 RES analyst-fixture invariant.

### RES-15: `gather_signals` (D2)

**Files.** Modify `pkg/research/steps.py` (bodies of `gather_signals`, `build_ledger`, `synthesize_research`, `run_deep_research`, `verification_lookup`, `roll_up_feed_health` become one-line delegations as their tasks land; models and signatures unchanged). Create `pkg/research/runs.py`, `pkg/research/broad.py`, `backend/tests/research/test_res_gather.py`.

**Interfaces (produces).**
```python
# runs.py
@dataclass(frozen=True)
class ResearchRunHandle:
    id: uuid.UUID; existed: bool
async def open_research_run(sessionmaker: async_sessionmaker[AsyncSession], *, call: CallContext, run_id: uuid.UUID, kind: ResearchRunKind,
                            pillar_key: str | None, window_days: int, article_id: uuid.UUID | None, now: datetime) -> ResearchRunHandle
async def get_research_run(db: AsyncSession, research_run_id: uuid.UUID, *, for_update: bool = False) -> ResearchRun   # LookupError
def error_payload(exc: BaseException) -> dict[str, object]
async def mark_run(sessionmaker: async_sessionmaker[AsyncSession], research_run_id: uuid.UUID, *, status: ResearchRunStatus,
                   error: dict[str, object] | None, now: datetime) -> None
def query_status_counts(run: ResearchRun) -> tuple[int, int]            # (ok, failed) from run.queries
def merged(mapping: Mapping[str, int], **values: int) -> dict[str, int]
# broad.py
async def gather_signals_impl(sc: StepContext, *, pillar_key: PillarKey | None) -> GatherSignalsResult
def broad_keywords(pillar: ContentPillar | None, theme_names: Sequence[str]) -> frozenset[str]
# steps.py (unchanged signature)
async def gather_signals(sc: StepContext, *, pillar_key: PillarKey | None) -> GatherSignalsResult:
    from mdcopilot_blog.research import broad   # local import: broad imports this module's result models
    return await broad.gather_signals_impl(sc, pillar_key=pillar_key)
```

**Behaviour rules.**
1. `open_research_run`: new row `kind`, `status=running`, `run_id`, `article_id`, `pillar_key`, `window_days`, `started_at=now`, `trace_id=call.trace_id`, `dbos_workflow_id`/`dbos_step_id` from `call`. When `call.dbos_workflow_id` is set: `insert(...).on_conflict_do_nothing(index_elements=["dbos_workflow_id", "dbos_step_id"], index_where=text("dbos_workflow_id IS NOT NULL")).returning(ResearchRun.id)`; no id → select the existing id (`existed=True`). Commits.
2. `mark_run` row-locks, sets `status`, `error`, `finished_at=now`, commits. `error_payload` per track-wide rule 7.
3. `gather_signals_impl`:
   1. `sc.call.run_id is None` → `ValueError("gather_signals needs sc.call.run_id")`. `now = sc.now()`; `research = sc.config.research`; `today = services.config.local_date(now, sc.config.schedule.timezone)`.
   2. Open the run (`kind BROAD`, `pillar_key.value` or None, `window_days=research.window_days`). When `existed` and the row's `counts` has key `feedItems`: return `GatherSignalsResult` from the row (`signal_count=len(signals)`, `queries_ok/failed` from `query_status_counts`, `themes_covered`) with no network call and no write.
   3. Read enabled `FeedSpec`s, `ThemeState`s and the pillar in one session. `planned = plan_broad_queries(themes, pillar_key=…, today=today, broad_queries=research.broad_queries, pillar_queries=research.pillar_queries)`.
   4. `async with open_environment(sc) as env`, inside an `asyncio.TaskGroup`: all `collect_feed(env, feed, now=now, window_days=research.window_days)` and `run_search_queries(sc, env, planned, mode="broad", recency_days=research.window_days, allowed_domains=(), ctx=sc.call)`. `search_ms` = wall time of this block.
   5. `signals` = feed outcome signals in feed order, then `outcome_signals(o, discovered_via=SEARCH)` for each query outcome in plan order. `queries` = `query_json(o, source_count=len(outcome_signals(o, discovered_via=SEARCH)))`. `themes_covered` = theme keys of `ok` queries, unique, plan order.
   6. One transaction: lock the run; set `signals` (`to_json` list), `queries`, `themes_covered`, `counts = merged(counts, feedItems=<number of feed signals>, searchResults=<sum of len(source_urls)>)`, `phase_latency_ms = merged(…, search=search_ms)`. For each outcome whose feed has an id and `fetched` is true: `last_fetched_at=now`, `state=new_state`; ok → `consecutive_failures=0`, `last_error=None`, `last_success_at=now`, `item_count_last=items_in_window`; failure → `consecutive_failures += 1`, `last_error=error[:2000]`, and when `consecutive_failures >= research.feed_disable_after_failures` and the feed is enabled → `is_enabled=False`, `disabled_reason=f"auto-disabled {now:%Y-%m-%d} after {n} consecutive failures"`. Every theme with a planned query gets `last_searched_at=now`. Commit.
   7. Return `GatherSignalsResult(research_run_id, signal_count, queries_ok, queries_failed, themes_covered)`. The research run stays `running`.
   8. Any exception after step 2 (including `BudgetExceeded`) → `mark_run(status=FAILED, error=error_payload(exc))`, then re-raise.
4. `broad_keywords` = `keyword_set(([pillar.name, *pillar.topics] if pillar is not None else []) + list(theme_names))`.

**Tests to write first** (`test_res_gather.py`; `sc = await mock_step_context(agents=["research"])`; step ids set with `dataclasses.replace(sc, call=dataclasses.replace(sc.call, dbos_workflow_id="wf-res-gather", dbos_step_id=2))` where needed):
- `test_gather_default_fixtures`: `gather_signals(sc, pillar_key=PillarKey.A)` → `signal_count == 39`, `queries_ok == 10`, `queries_failed == 0`, `themes_covered == ["specialist_shortages", "access_problems", "workforce_trends", "ai_news", "healthcare_ai", "physician_workflow", "agentic_ai", "clinical_ai_research", "regulation", "ai_model_developments"]`. The row: `kind "broad"`, `status "running"`, `pillar_key "A"`, `window_days 7`, `run_id == sc.call.run_id`, `trace_id == sc.call.trace_id`, `counts == {"feedItems": 9, "searchResults": 30}`, `"search" in phase_latency_ms`, 10 `queries` with the §3.1 key set. `blog_llm_calls`: 10 rows `kind "search"`, `run_id == sc.call.run_id`, `search_actions == 1`. The 10 covered themes have `last_searched_at == sc.now()`, the other 5 `None`. FDA press releases feed: `consecutive_failures 0`, `last_success_at == sc.now()`, `item_count_last 1`, `len(state["items"]) == 1`. FDA CSV feed: `len(state["knownIds"]) == 3`.
- `test_gather_same_step_is_idempotent`: with step ids, two calls → same `research_run_id`; `blog_llm_calls` search rows stay 10; FDA press `last_success_at` unchanged by the second call.
- `test_gather_without_step_ids_inserts_new_rows`: two calls → two different `research_run_id`s.
- `test_one_feed_down` (`scenario="research_feed_down"`): result returned; FDA press feed `consecutive_failures 1`, `last_error "HTTP 503"`, `last_success_at None`, `is_enabled True`; `counts["feedItems"] == 8`; no signal URL contains `fda-outlines-oversight-approach`.
- `test_feed_auto_disabled_at_threshold`: FDA press feed committed with `consecutive_failures=4`; scenario `research_feed_down` → `is_enabled False`, `disabled_reason == "auto-disabled 2026-09-17 after 5 consecutive failures"`.
- `test_search_failures_recorded`: `monkeypatch.setattr(sc.gateway, "search", fake)` where `fake` raises an error with `status_code=503` for the `ai_news` query, `ProviderNotAvailable` for the `regulation` query, and delegates to the original bound method otherwise → `queries_failed == 2`; the failed items have `status "failed"`, `searchActions 0`, `sourceCount 0`, non-null `error`; `themes_covered` lacks both keys; both themes still have `last_searched_at == sc.now()`; the fake was called 3 times for `ai_news` and once for `regulation`.
- `test_budget_exceeded_marks_run_failed`: `fake` raises `BudgetExceeded("cap")` → `pytest.raises(BudgetExceeded)`; the newest research run has `status "failed"`, `error["class"] == "BudgetExceeded"`, `finished_at` set.
- `test_gather_requires_run_id`: `call.run_id=None` → `ValueError`.

**Verification.** red `NotImplementedError: RES implements this` (FOUND stub); green `8 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §5.6 `gather_signals` (D2); §10.1 "Failure: one feed down; search 5xx → partial coverage" (gather half); ARCHITECTURE §5.1 D2; RESEARCH_ARCHITECTURE §6 (queries, themes covered, per-phase latency), §8 parallel pools, §10 feed failure and auto-disable; §5.5 step body rules 1–6.

### RES-16: `build_ledger` (D3)

**Files.** Modify `pkg/research/broad.py`, `pkg/research/steps.py` (delegation); create `backend/tests/research/test_res_build_ledger.py`.

**Interfaces (produces).** `async def build_ledger_impl(sc: StepContext, *, research_run_id: uuid.UUID) -> BuildLedgerResult`; `async def ledger_stats(db: AsyncSession, source_ids: Sequence[uuid.UUID], *, now: datetime, window_days: int, require_window: bool) -> tuple[int, int]` (returns `(dated_sources, tier12_sources)`).

**Behaviour rules.**
1. Load the run; `kind != broad` → `ValueError("build_ledger expects a broad research run")`.
2. Idempotent return: when `counts` has key `sourcesTotal`, compute stats from the stored `source_ids` and apply rule 6 again (raising again if thresholds fail); otherwise return `BuildLedgerResult(research_run_id, sources_total=counts["sourcesTotal"], sources_new=counts["sourcesNew"], sources_blocked=counts["sourcesBlocked"], dated_sources, tier12_sources)`. No network call, no ledger write.
3. Inputs: `signals = [Signal.from_json(s) for s in run.signals]`; `feeds` = all feed specs (enabled or not) keyed by id; `rules = load_domain_rules`; `keywords = broad_keywords(pillar, names of run.themes_covered)`; `merged = merge_signals(signals)`; `candidates = select_candidates(merged, rules=…, feeds=…, keywords=…, now=sc.now(), window_days=run.window_days)`; `existing = load_existing(db, hashes)`.
4. `async with open_environment(sc) as env`: `timer = StageTimer()`; `items = await retrieve(env, candidates, existing=existing, keywords=keywords, now=sc.now(), window_days=run.window_days, timer=timer)`; `retrieval_ms` = wall time.
5. One transaction: `outcomes = upsert_sources(db, items, existing=existing, research_run_id=run.id)`; unique ids in outcome order; rows loaded and ordered with `agents.common.order_sources`; `run.source_ids = [str(row.id) for row in ordered]`; `counts = merged(counts, urlsFetched=<outcomes with fetched>, sourcesNew=<created>, sourcesTotal=<unique ids>, sourcesBlocked=<outcomes whose fetch_status is blocked or robots_disallowed>)`; `phase_latency_ms = merged(…, retrieval=retrieval_ms, extraction=timer.extraction_ms)`. Commit.
6. Thresholds: `dated_sources` = rows with `published_at` not null and `in_window` (`require_window=True`); `tier12_sources` = rows with `tier <= 2` and `access_mode` in (`full_text`, `abstract_only`); `ok, _ = query_status_counts(run)`. When `dated_sources < research.min_source_count` or `ok < research.min_successful_queries`: `exc = InsufficientEvidence(str(run.id), dated_sources, research.min_source_count, ok)`; `mark_run(status=INSUFFICIENT_EVIDENCE, error={**error_payload(exc), "foundSources": dated_sources, "requiredSources": research.min_source_count, "successfulQueries": ok})`; `raise exc`. Ledger rows stay committed.
7. Otherwise return `BuildLedgerResult(research_run_id, sources_total, sources_new, sources_blocked, dated_sources, tier12_sources)`; status stays `running`.
8. Other exceptions → `mark_run(status=FAILED, …)`, re-raise.

**Tests to write first** (`test_res_build_ledger.py`; each test runs `gather_signals(sc, pillar_key=PillarKey.A)` first on `mock_step_context(agents=["research"])`):
- `test_build_ledger_default_fixtures`: result `sources_total 12`, `sources_new 12`, `sources_blocked 1`, `dated_sources 11`, `tier12_sources 9`. `[canonical_url of run.source_ids]` equals the S1…S12 order of the "Mock fixture set" table. Row checks: S3 `access_mode "abstract_only"`, non-empty `text_snapshot`, `external_ids["pmid"] == "40000002"`; S5 `fetch_status "blocked"`, `access_mode "metadata_only"`, `published_at 2026-09-15T12:00Z`, `text_snapshot None`; S8 `fetch_status "not_fetched"`, `published_at None`; S12 `is_preprint True`, `tier 2`; S9 `url` ends with `?utm_campaign=rss` and `canonical_url` has no query; S10 `published_at 2026-09-16T05:39Z`, `date_source "feed"`; S2 `date_source "jsonld"`; S11 `date_source "meta"`; S6 `discovered_via "federal_register"`; S7 `discovered_via "pubmed"`; every row `first_research_run_id == research_run_id`. `counts` includes `urlsFetched 8`, `sourcesNew 12`, `sourcesTotal 12`, `sourcesBlocked 1`; `phase_latency_ms` has `retrieval` and `extraction`.
- `test_second_run_reuses_ledger_rows`: a second gather + build (no step ids) → `sources_new 0`, `sources_total 12`, `counts["urlsFetched"] == 0`, `sources_blocked 1`, `count(LedgerSource) == 12`.
- `test_same_step_is_idempotent`: build called twice with step ids `("wf-res-ledger", 3)` → equal results; the second call issues no HTTP request (monkeypatch `broad.open_environment` to fail if entered after the first call) and the ledger still has 12 rows.
- `test_insufficient_evidence_on_sources`: `sc2 = dataclasses.replace(sc, config=<research.min_source_count=50>)` → `InsufficientEvidence` with `args == (str(research_run_id), 11, 50, 10)`; row `status "insufficient_evidence"`, `error["foundSources"] == 11`, `error["requiredSources"] == 50`, `error["successfulQueries"] == 10`, `finished_at` set; 12 ledger rows exist.
- `test_insufficient_evidence_on_queries`: gather with `sc.gateway.search` patched to fail 5 of 10 queries with `ProviderNotAvailable` → build raises `InsufficientEvidence` whose `args[3] == 5`.
- `test_all_blocked_scenario`: `scenario="research_all_blocked"` → no raise; `tier12_sources 0`; every fetched page row `fetch_status "blocked"`; S3 and S7 rows `access_mode "metadata_only"`, `fetch_status "error"`; `dated_sources 11`.
- `test_rejects_non_broad_run`: a `make_research_graph(kind=DEEP)` run id → `ValueError`.

**Verification.** red `NotImplementedError`; green `7 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §5.6 `build_ledger` (D3, `InsufficientEvidence` below thresholds); §10.1 "Extractor + ledger", "PubMed fixture → non-empty abstract, `access_mode=abstract_only`", "blocked page → metadata-only", "per-phase latency stored"; §5.8 RES invariants (≥6 dated sources, ≥3 Tier 1/2 with text, anchor-shifted dates); RESEARCH_ARCHITECTURE §3 `INSUFFICIENT_EVIDENCE`, §10 coverage below minimum.

### RES-17: `synthesize_research` (D4), mock broad-scan acceptance and failure paths

**Files.** Modify `pkg/research/broad.py`, `pkg/research/steps.py` (delegation); create `backend/tests/research/test_res_synthesize.py`, `backend/tests/research/test_res_broad_scan.py`.

**Interfaces (produces).** `async def synthesize_research_impl(sc: StepContext, *, research_run_id: uuid.UUID) -> SynthesizeResult`; `def search_hints(run: ResearchRun) -> list[SearchHint]`.

**Behaviour rules.**
1. Load the run; `kind != broad` → `ValueError("synthesize_research expects a broad research run")`. When findings already exist for the run → return `SynthesizeResult(research_run_id, finding_count=<count>)` with no model call.
2. `rows` = ledger rows for `run.source_ids` in stored order, first `MAX_ANALYST_SOURCES`; `numbered = number_sources(rows, preserve_order=True)`.
3. `search_hints`: search signals (`discoveredVia == "search"`) in stored order are split into consecutive groups of `queries[i].sourceCount` (queries in stored order); each `ok` query with a group whose first signal has an `answerExcerpt` yields `SearchHint(query=queries[i]["text"], excerpt=…)`; hints with an excerpt equal to an earlier one are dropped; first `MAX_HINTS`.
4. `variables = build_variables(pillar_name=…, pillar_topics=…, window_days=run.window_days, today=local_date(sc.now(), sc.config.schedule.timezone))`; `result = await run_research_analyst(sc.gateway, ctx=sc.call, numbered=numbered, hints=hints, variables=variables, route_override=sc.config.routes["research"], prompt_version=sc.config.prompt_versions.get("research/synthesize"))`; `llm_ms` = wall time.
5. Findings: per analyst finding, `source_ids = tuple(resolve_markers(f.markers, numbered))`; `EvidenceSource` from the rows; `apply_claim_rules`.
6. One transaction: insert `ResearchFindingRecord(research_run_id, position=i, claim, evidence, confidence, category, claim_type=value, importance, is_preprint, downgraded_from)` and one `FindingSource` per unique source id; update the run: `counts = merged(…, findings=n)`, `phase_latency_ms = merged(…, llm=llm_ms, total=search + retrieval + extraction + llm)` (missing keys count 0), `status = partial` when any query failed else `succeeded`, `error=None`, `finished_at=sc.now()`. Commit. Return `SynthesizeResult(research_run_id, finding_count=n)`.
7. Exceptions (including `RouteExhausted`, `BudgetExceeded`) → `mark_run(status=FAILED, …)`, re-raise; no findings are written.

**Tests to write first.**

`test_res_synthesize.py` (gather with `PillarKey.A` + build first):
- `test_synthesize_default_fixture`: `finding_count 6`; rows by position have `claim_type [FACT, FACT, ANALYSIS, ANALYSIS, PREDICTION, FACT]`, `downgraded_from [None, None, None, "FACT", None, None]`, position 0 `importance "high"` and exactly one `FindingSource` = S1's id; run `status "succeeded"`, `counts["findings"] == 6`, `phase_latency_ms` keys `{search, retrieval, extraction, llm, total}` with `total` equal to the sum of the other four; one `blog_llm_calls` row `kind "agent"`, `agent_name "research"`, `prompt_name "research/synthesize"`, `run_id == sc.call.run_id`.
- `test_synthesize_is_idempotent`: a second call → `finding_count 6`; still one agent row.
- `test_search_hints_partition`: a stored run with queries `[ok sourceCount 2 "q1", failed 0 "q2", ok 1 "q3"]` and 3 search signals with excerpts `E1, E1, E3` → hints `[("q1", "E1"), ("q3", "E3")]`.
- `test_unknown_marker_output_fails_the_step` (`scenario="research_unknown_marker"`): `RouteExhausted` raised; run `status "failed"`, `error["class"] == "RouteExhausted"`; zero findings; two agent rows with `status "error"`.
- `test_partial_when_a_query_failed`: gather with 2 queries failing (patched search) → after build and synthesize the run `status "partial"`.

`test_res_broad_scan.py` (acceptance):
- `test_mock_broad_scan_under_ten_seconds`: `t0 = time.perf_counter()`; gather (`PillarKey.A`) → build → synthesize; `time.perf_counter() - t0 < 10.0`; every finding with `claim_type "FACT"` has ≥ 1 `FindingSource`; every `FindingSource.source_id` of the run is in `run.source_ids` and exists in `blog_sources`.
- `test_default_broad_scan_requests_are_all_indexed`: monkeypatch `environment.FixtureTransport` with a subclass that registers instances → after gather and build, every instance has `missing == []`.
- `test_golden_path_invariants`: the first 6 `source_ids` rows are dated within `window_days` of `sc.now()`; ≥ 3 rows have `tier <= 2` with text; `query_status_counts(run)[0] >= sc.config.research.min_successful_queries`; stored findings cite only sources among the first 6 `source_ids`; ≥ 1 stored finding is high-importance `FACT` citing a tier ≤ 2 source.
- `test_invalid_analyst_output_retried_then_next_model`: after gather and build, `sc2 = dataclasses.replace(sc, gateway=LLMGateway(settings=sc.settings, prompts=sc.prompts, recorder=CallRecorder(sc.sessionmaker), model_factory=ScriptedFactory({"google:gemini-3.8-flash": always S99, "openai:gpt-5.6-terra": the default fixture output}), search_provider=FixtureSearchProvider()))` → `finding_count 6`; agent rows for the run ordered by `created_at`: `[error (error_class "UnexpectedModelBehavior", provider_requested "google"), ok (fallback_from "google:gemini-3.8-flash")]`; the google model was called twice.
- `test_search_5xx_gives_partial_coverage`: patched search raises an error with `status_code=503` for 3 queries (each attempted 3 times) → gather `queries_failed 3`; build succeeds (`7 >= 6`); synthesize succeeds; run `status "partial"`; the 3 failed `queries` items carry `error` text starting with the error class name.

**Verification.** `RES_PYTEST tests/research/test_res_synthesize.py` red `NotImplementedError`, green `5 passed`; `RES_PYTEST tests/research/test_res_broad_scan.py` green `5 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "Mock broad scan < 10 s and every `FACT` finding cites a ledger id"; "Live broad scan … zero findings citing a URL outside the ledger (enforced and tested) … per-phase latency stored" (mock enforcement); "Failure: one feed down (RES-15); search 5xx → partial coverage; blocked page → metadata-only (RES-16); invalid analyst output retried then next model"; §5.6 `synthesize_research` (D4); §5.8 RES invariants; RESEARCH_ARCHITECTURE §7 claim rules applied in code, §10 analyst output invalid.

### RES-18: `run_deep_research` (P1)

**Files.** Create `pkg/research/deep.py`, `backend/tests/research/test_res_deep.py`; modify `pkg/research/steps.py` (delegation).

**Interfaces (consumes).** `Article` (read: `run_id`, `candidate_id`, `pillar_key`), `TopicCandidateRecord` (read: `title`, `thesis`, `angle`, `pillar_key`, `source_ids`, `primary_source_id`), RES-4 `plan_deep_queries`, RES-12, RES-13, `StepContext.with_ids`.

**Interfaces (produces).**
```python
async def run_deep_research_impl(sc: StepContext, *, article_id: uuid.UUID, candidate_id: uuid.UUID,
                                 avoid_source_ids: Sequence[uuid.UUID]) -> DeepResearchResult
def compose_packet_sources(*, new_ids: Sequence[uuid.UUID], candidate_ids: Sequence[uuid.UUID], primary_id: uuid.UUID | None,
                           avoid: Collection[uuid.UUID], rows: Mapping[uuid.UUID, PromptSource], min_dated: int,
                           limit: int = MAX_PACKET_SOURCES) -> list[uuid.UUID]
```

**Behaviour rules.**
1. Missing article → `LookupError(f"article {article_id} not found")`; missing candidate → `LookupError(f"candidate {candidate_id} not found")`; `article.candidate_id != candidate_id` → `ValueError("candidate does not belong to article")`.
2. `ctx = sc.with_ids(article_id=article_id).call`; open the run with `kind DEEP`, `run_id=article.run_id`, `article_id`, `pillar_key=candidate.pillar_key`, `window_days=research.window_days`. An existing row with status `succeeded`/`partial` → return `DeepResearchResult(research_run_id, source_ids=<stored ids>)`; with status `insufficient_evidence` → raise `InsufficientEvidence(str(id), error["foundSources"], error["requiredSources"], error["successfulQueries"])`; `running`/`failed` → run again on the same row.
3. `planned = plan_deep_queries(title=candidate.title, thesis=candidate.thesis, pillar_name=<pillar name or None>, today=local_date(...), deep_queries=research.deep_queries)`; `outcomes = run_search_queries(sc, env, planned, mode="deep", recency_days=None, allowed_domains=(), ctx=ctx)`; signals `outcome_signals(o, discovered_via=DEEP_SEARCH)`; store `signals`, `queries`, `counts(feedItems=0, searchResults=…)`, `phase_latency_ms.search`; commit.
4. `keywords = keyword_set([candidate.title, candidate.thesis, candidate.angle])`; merge, select (limit `MAX_LEDGER_CANDIDATES`), retrieve with a `StageTimer`, upsert — as RES-16 rules 3–5, with `research_run_id` = this run.
5. `new_ids` = this run's upserted ids ordered by `order_sources`; `candidate_ids` = `candidate.source_ids` parsed as UUIDs (invalid strings skipped) that exist in `blog_sources`; `primary_id` = `candidate.primary_source_id` when it exists.
6. `compose_packet_sources`: `pool` = unique `new_ids + candidate_ids` in that order; `avoid_set = set(avoid) - {primary_id}`; `chosen = ([primary_id] if primary_id else []) + [x for x in pool if x != primary_id and x not in avoid_set]`, truncated to `limit`; then for `x` in `[p for p in pool if p in avoid_set]` ordered by `order_sources`, while the number of `chosen` rows with `published_at` set is below `min_dated` and `len(chosen) < limit`, append `x` when its row is dated; result = `chosen` ordered by `order_sources` (ids).
7. Final `source_ids = compose_packet_sources(..., min_dated=research.min_source_count)`; store `source_ids`, `counts` (`urlsFetched`, `sourcesNew`, `sourcesTotal=len(final)`, `sourcesBlocked`), `phase_latency_ms` (`retrieval`, `extraction`, `total = search + retrieval + extraction`); commit.
8. Thresholds on the final rows: `dated` = rows with `published_at` set (no window for deep runs); `tier12` = rows with tier ≤ 2 and text; `ok` = successful queries; `required_ok = min(research.min_successful_queries, len(planned))`. `dated < research.min_source_count` or `tier12 < 1` or `ok < required_ok` → `INSUFFICIENT_EVIDENCE` exactly as RES-16 rule 6 and raise.
9. Otherwise status `partial` when any query failed, else `succeeded`; `finished_at`; return `DeepResearchResult(research_run_id, source_ids=final)`.
10. Other exceptions → `mark_run(FAILED)`, re-raise. The step never changes `blog_articles` or `blog_runs`.

**Tests to write first** (`test_res_deep.py`; `sc = await mock_step_context(agents=["research"])`; graph via `make_article_graph(db, status=ArticleStatus.DRAFTING, with_seo=False)` in a `sc.sessionmaker()` session, committed):
- `test_compose_packet_sources`: rows as `SimpleNamespace(id, tier, published_at, canonical_url)`: `n1` tier 1 dated 2026-09-16, `n2` tier 1 dated 2026-09-15, `c1` tier 1 dated 2026-09-14, `c2` tier 2 undated. (a) `new=[n1, n2]`, `candidate=[c1, c2]`, `primary=c1`, `avoid={c1, n2}`, `min_dated=3` → `[n1, n2, c1, c2]`; (b) the same with `limit=2` → `[n1, c1]`; (c) `primary=None`, `avoid={n1, n2, c1}`, `min_dated=2` → `[n1, n2, c2]`.
- `test_deep_research_default_fixtures`: result contains the 7 deep-fixture canonical URLs; the run: `kind "deep"`, `article_id`, `run_id == graph.run_id`, `status "succeeded"`, 8 queries all `ok` with `themeKey None`; 8 `blog_llm_calls` search rows with `article_id == graph.article_id`. Rows: the KFF page `date_source "htmldate"`, `published_at 2026-09-11T00:00Z`; PubMed `40000003` `abstract_only`; the FDA PDF `full_text` with `published_at None`; healthaffairs `not_fetched`; HRSA `date_source "jsonld"`.
- `test_deep_same_step_is_idempotent`: step ids `("wf-res-deep", 1)` → two calls return equal `source_ids`; search rows stay 8.
- `test_avoided_sources_fill_only_to_minimum`: candidate committed with `source_ids=[]`, `primary_source_id=None`; first call → `R1`; second call (no step ids) with `avoid_source_ids=R1` → result has exactly 5 ids, all dated, all in `R1`.
- `test_deep_insufficient_evidence`: `min_source_count=50` → `InsufficientEvidence`, row `status "insufficient_evidence"`; a second call with the same step ids re-raises with the same `args` and adds no search rows.
- `test_deep_requires_one_tier12_text_source`: `sc.gateway.search` patched to return only `https://www.nih.gov/news-events/news-releases/deep-x` (metadata-only policy), candidate sources emptied, a committed dated metadata-only ledger row set as `primary_source_id`, `min_source_count=1` → `InsufficientEvidence`.
- `test_bad_ids`: unknown candidate → `LookupError`; a second candidate of another graph → `ValueError`.

**Verification.** red `NotImplementedError`; green `7 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §5.6 `run_deep_research` (P1, raises `InsufficientEvidence`); §10.3 "Deep Research Analyst + versioned packets" (Also: RES) and "Regenerating research → new packet version, old kept" (avoid-hint input); §5.8 RES deep invariant (≥5 dated, ≥2 Tier 1/2 with text); RESEARCH_ARCHITECTURE §6 deep research and regenerate research rows; ruling D10 (calls carry the article's ids through `ctx`).

### RES-19: `verification_lookup`

**Files.** Create `pkg/research/verification.py`, `backend/tests/research/test_res_verification.py`; modify `pkg/research/steps.py` (delegation).

**Interfaces (produces).** `async def verification_lookup_impl(sc: StepContext, *, article_id: uuid.UUID, queries: Sequence[str]) -> VerificationResult`; `def partition_signals(run: ResearchRun) -> list[list[Signal]]`.

**Behaviour rules.**
1. `texts` = input queries stripped, blanks removed, original indexes kept; none → `VerificationResult(research_run_id=None, source_ids_by_query={})`.
2. Missing article → `LookupError`.
3. `allow` = `SourceDomain` rows with `verification_allowlisted`, domains sorted; empty → `VerificationResult(None, {})` with no search.
4. Only the first `research.max_verification_searches` texts are searched; their original input indexes are the result keys.
5. Open the run: `kind VERIFICATION`, `run_id=article.run_id`, `article_id`, `pillar_key=article.pillar_key`, `window_days=research.window_days`. Existing row with status other than `running` → return the mapping rebuilt by rule 9 from the row.
6. `outcomes = run_search_queries(sc, env, planned, mode="verification", recency_days=None, allowed_domains=allow, ctx=sc.with_ids(article_id=article_id).call)`; `keep(url)` = `match_domain_rule(host_of(url), allow_rules)` is not `None` (URLs failing `host_of` are dropped); per query `outcome_signals(o, discovered_via=VERIFICATION, keep=keep)`; `queries` JSON with `sourceCount` = kept signals; signals stored in query order.
7. Ledger: `merge_signals`, `select_candidates` (keywords from the query texts), `retrieve`, `upsert_sources`; `source_ids` = unique rows in `order_sources` order; counts and latency as RES-16 (`total = search + retrieval + extraction`).
8. Status: all queries failed → `failed` with `error {"class": "SearchFailed", "message": "all verification searches failed"}` (no exception raised); some failed → `partial`; else `succeeded`; `finished_at` set; commit.
9. Mapping: `partition_signals(run)` splits stored signals into consecutive groups of `queries[i].sourceCount`; for key `k` (the i-th searched query's input index) the value is the unique ledger ids of that group's canonical URLs in group order (URLs without a ledger row are skipped); failed queries map to `[]`.
10. Return `VerificationResult(research_run_id, source_ids_by_query=mapping)`.

**Tests to write first** (`test_res_verification.py`; graph as RES-18):
- `test_verification_default`: `queries=["q1", "q2"]` → `research_run_id` set; keys `{0, 1}`; each value `== [<cdc.gov row id>, <S1 fda.gov row id>]` (the example-health-blog URL is filtered); the run `kind "verification"`, `article_id`, `run_id == graph.run_id`; the captured `SearchQuery.allowed_domains` equals the 36 allow-listed domains sorted, `mode "verification"`; search rows have `article_id` set.
- `test_verification_caps_searches`: 5 queries → keys `{0, 1, 2}`; 3 search rows.
- `test_blank_queries_keep_input_indexes`: `["", "q"]` → keys `{1}`.
- `test_no_allowlist_or_no_queries`: all domains set `verification_allowlisted=false` → `(None, {})`, no search row, no research run; `queries=["  "]` → `(None, {})`.
- `test_verification_same_step_is_idempotent`: step ids → second call returns the same mapping; search rows unchanged.
- `test_all_searches_failed`: search patched with `ProviderNotAvailable` → mapping `{0: [], 1: []}`; run `status "failed"`, `error["class"] == "SearchFailed"`.
- `test_unknown_article`: → `LookupError`.

**Verification.** red `NotImplementedError`; green `7 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §5.6 `verification_lookup` (≤ `max_verification_searches`, allow-listed domains, `mode="verification"`); §10.4 "Fact Checker … ≤3 verification searches" (Also: RES); RESEARCH_ARCHITECTURE §3 (`filters.allowed_domains` for verification), §6 verification lookups row.

### RES-20: `roll_up_feed_health`

**Files.** Create `pkg/research/feed_health.py`, `backend/tests/research/test_res_feed_health.py`; modify `pkg/research/steps.py` (delegation).

**Interfaces (produces).** `async def roll_up_feed_health_impl(sessionmaker: async_sessionmaker[AsyncSession], *, settings: Settings, now: datetime) -> FeedHealthReport`.

**Behaviour rules.**
1. One session: `config = await load_effective_config(db, settings)`; `threshold = config.research.feed_disable_after_failures`.
2. Enabled feeds are selected `FOR UPDATE`, ordered `group_name, name`; `feeds_checked` = their count.
3. Each with `consecutive_failures >= threshold` → `is_enabled=False`, `disabled_reason=f"auto-disabled {now:%Y-%m-%d} after {consecutive_failures} consecutive failures"`; `feeds_disabled` counts them.
4. `failing_feed_ids` = ids of those enabled-at-start feeds with `consecutive_failures > 0`, in the same order.
5. Commit; return `FeedHealthReport(feeds_checked, feeds_disabled, failing_feed_ids)`. No network access.

**Tests to write first** (`test_res_feed_health.py`; `committed_seed` + `sessionmaker_committing`; `NOW = 2026-09-17T21:00Z`):
- `test_roll_up_counts`: "AMA news" `consecutive_failures=5`, "CDC newsroom" `2` → report `feeds_checked 29`, `feeds_disabled 1`, `failing_feed_ids == [AMA id, CDC id]` (group order `ama` < `cdc`); AMA `is_enabled False`, `disabled_reason == "auto-disabled 2026-09-17 after 5 consecutive failures"`; CDC still enabled.
- `test_disabled_feeds_are_ignored`: Lancet (seeded disabled) with `consecutive_failures=9` → not counted, not listed.
- `test_second_roll_up`: after `test_roll_up_counts`' setup and one roll-up, a second call → `feeds_checked 28`, `feeds_disabled 0`, `failing_feed_ids == [CDC id]`.

**Verification.** red `NotImplementedError`; green `3 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §5.6 `roll_up_feed_health`; §10.7 "Maintenance: … feed-health roll-up" (Also: RES seam); RESEARCH_ARCHITECTURE §10 auto-disable after N failures.

### RES-21: Research runs API (§4.2)

**Files.** Modify `pkg/api/schemas_research.py`, `pkg/api/routers/research.py` (FOUND stubs); create `pkg/services/research_runs.py`, `backend/tests/research/test_res_research_api.py`. `LedgerSourceOut` comes from RES-22's `schemas_sources.py`; write that model first (RES-22 rule 1) if RES-22 has not landed.

**Interfaces (produces).**
```python
# schemas_research.py (fields exactly as CONTRACT §4.2)
class ResearchQueryOut(ApiModel): text: str; theme_key: str | None; status: Literal["ok", "failed"]; search_actions: int; source_count: int; error: str | None
class ResearchRunOut(ApiModel): id: uuid.UUID; run_id: uuid.UUID; article_id: uuid.UUID | None; kind: ResearchRunKind; status: ResearchRunStatus; pillar: PillarKey | None; window_days: int; queries: list[ResearchQueryOut]; themes_covered: list[str]; phase_latency_ms: dict[str, int]; counts: dict[str, int]; source_count: int; finding_count: int; started_at: datetime; finished_at: datetime | None; error: dict[str, Any] | None; trace_id: str; created_at: datetime
class FindingOut(ApiModel): id: uuid.UUID; position: int; claim: str; evidence: str; confidence: float; category: str; claim_type: ClaimType; importance: Literal["high", "normal"]; is_preprint: bool; downgraded_from: str | None; sources: list[SourceRefOut]
class ResearchRunDetail(ResearchRunOut): findings: list[FindingOut]; sources: list[LedgerSourceOut]
# services/research_runs.py
async def list_research_runs(db: AsyncSession, *, run_id: uuid.UUID | None, article_id: uuid.UUID | None, kind: ResearchRunKind | None,
                             limit: int, offset: int) -> tuple[list[ResearchRunOut], int]
async def get_research_run_detail(db: AsyncSession, research_run_id: uuid.UUID) -> ResearchRunDetail | None
def to_research_run_out(run: ResearchRun, *, finding_count: int) -> ResearchRunOut
def to_source_ref(row: LedgerSource, *, marker: str | None) -> SourceRefOut
# routers/research.py
@router.get("/research-runs") -> Page[ResearchRunOut]
@router.get("/research-runs/{research_run_id}") -> ResearchRunDetail
```

**Behaviour rules.**
1. Both routes depend on `require_permission(Permission.VIEW)`. Query parameters: `run_id: Annotated[uuid.UUID | None, Query(alias="runId")] = None`, `article_id: Annotated[uuid.UUID | None, Query(alias="articleId")] = None`, `kind: ResearchRunKind | None = None`, `limit: Annotated[int, Query(ge=1)] = 20` (capped to 100 in the response and the query), `offset: Annotated[int, Query(ge=0)] = 0`.
2. List: equality filters; order `created_at DESC, id DESC`; `total` = count with the same filters; `finding_count` per run from one grouped count query.
3. `to_research_run_out`: `pillar = PillarKey(run.pillar_key)` or `None`; `source_count = len(run.source_ids)`; `queries` built from each stored dict with explicit keys (`text`, `themeKey`, `status`, `searchActions` default 0, `sourceCount` default 0, `error`), non-dict items skipped; `phase_latency_ms` and `counts` copied with `int` values.
4. Detail: 404 `ProblemError(404, "Research run not found", f"no research run with id {research_run_id}")` when missing. `sources` = `LedgerSourceOut` for rows of `source_ids` in stored order (missing ids skipped). `findings` ordered by `position`; each finding's `sources` = its `FindingSource` rows as `SourceRefOut` with `marker = f"S{index + 1}"` where `index` is the source's position in the run's `source_ids`, ordered by that index; sources absent from `source_ids` get `marker=None` and come last ordered by `canonical_url`. No text snapshot is serialised anywhere.

**Tests to write first** (`test_res_research_api.py`; `app`/`client`/`login_as` on `db_session`; data via `make_research_graph(db_session)`; props from `tests/api_shapes.json`):
- `test_list_research_runs`: viewer; a broad graph then a deep graph → `GET /api/blog-agent/research-runs` 200, `total 2`, first item is the deep run; `set(item) == props["ResearchRunOut"]`; `?kind=deep` → 1 item; `?runId=<broad graph run_id>` → 1 item; `?limit=1&offset=1` → `total 2`, 1 item; `?limit=500` → body `limit == 100`.
- `test_list_requires_session`: no login → 401.
- `test_list_invalid_filters`: `?kind=wide` → 422; `?limit=0` → 422; `?runId=nope` → 422.
- `test_get_research_run_detail`: → 200; `sourceCount 6`; `findingCount == len(graph.finding_ids)`; `[s["id"] for s in body["sources"]] == [str(i) for i in graph.source_ids]`; every source key set equals `props["LedgerSourceOut"]` and lacks `textSnapshot`; findings ordered by `position`; each finding source `marker == f"S{graph.source_ids.index(UUID(id)) + 1}"`.
- `test_get_research_run_404`: random id → 404, `title "Research run not found"`.
- `test_get_detail_requires_session`: → 401.

(Every role holds `blog.view`, so no role can receive 403 on these routes; `tests/api/test_rbac_routes.py::test_every_non_public_route_requires_a_principal` covers the dependency.)

**Verification.** red: FOUND's empty router yields 404 on both paths (assertions fail); green `6 passed`; `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/api/test_rbac_routes.py` → all passed; `RES_LINT` exits 0.

**Acceptance covered.** §4.2 (both routes, models, 404); §8.3 route tests; §10.1 "UI Research page and Sources page" (Also: RES API); ARCHITECTURE §13 Research page data (runs, themes covered, findings with claim type/confidence/sources/dates, per-phase latency).

### RES-22: Sources, feeds, domains and themes API (§4.3)

**Files.** Modify `pkg/api/schemas_sources.py`, `pkg/api/routers/sources.py`; create `pkg/services/sources.py`, `backend/tests/research/test_res_sources_api.py`.

**Interfaces (produces).**
```python
# schemas_sources.py (fields exactly as CONTRACT §4.3)
class LedgerSourceOut(ApiModel): id; title; url; canonical_url; publisher; domain; source_type: SourceType; tier: int; published_at: datetime | None; date_source: DateSource; retrieved_at: datetime; access_mode: AccessMode; fetch_status: FetchStatus; word_count: int; is_preprint: bool; discovered_via: DiscoveredVia; relevance_score: float
class SourceFeedOut(ApiModel): id; name; url; kind: FeedKind; group: str; tier: int; source_type: SourceType; pillar_keys: list[PillarKey]; theme_keys: list[str]; header_profile: str; is_enabled: bool; is_preprint: bool; last_fetched_at: datetime | None; last_success_at: datetime | None; last_error: str | None; consecutive_failures: int; disabled_reason: str | None; item_count_last: int
class SourceFeedUpdate(ApiModel): is_enabled; tier (1..3); header_profile: Literal["default", "browser_like"]; pillar_keys: list[PillarKey]; theme_keys: list[str]   # all optional
class SourceDomainOut(ApiModel): id; domain; tier: int; source_type: SourceType; publisher: str | None; header_profile: str; fetch_policy: Literal["fetch", "metadata_only", "never"]; verification_allowlisted: bool; notes: str | None
class SourceDomainUpdate(ApiModel): tier (1..3); source_type: SourceType; publisher (1..200); header_profile: Literal[...]; fetch_policy: Literal[...]; verification_allowlisted: bool; notes (≤2000)   # all optional
class ThemeOut(ApiModel): id; key; name; description; query_templates: list[str]; pillar_keys: list[PillarKey]; is_active: bool; last_searched_at: datetime | None; sort_order: int
class ThemeIn(ApiModel): key (^[a-z0-9_]{1,64}$); name (1..200); description (≤2000); query_templates (1..10 items, each 1..300); pillar_keys: list[PillarKey]; is_active: bool; sort_order: int (≥0)
class ThemesUpdate(ApiModel): items: list[ThemeIn]   # 1..50 items, unique keys
# services/sources.py
MAX_ALLOWLISTED_DOMAINS = 100
def to_ledger_source_out(row: LedgerSource) -> LedgerSourceOut
async def list_sources(db: AsyncSession, *, domain: str | None, tier: int | None, access_mode: AccessMode | None, q: str | None,
                       since: datetime | None, limit: int, offset: int) -> tuple[list[LedgerSourceOut], int]
async def list_feeds(db: AsyncSession) -> list[SourceFeedOut]
async def update_feed(db: AsyncSession, *, feed_id: uuid.UUID, update: SourceFeedUpdate, principal: Principal) -> SourceFeedOut
async def list_domains(db: AsyncSession) -> list[SourceDomainOut]
async def update_domain(db: AsyncSession, *, domain_id: uuid.UUID, update: SourceDomainUpdate, principal: Principal) -> SourceDomainOut
async def list_themes(db: AsyncSession) -> list[ThemeOut]
async def replace_themes(db: AsyncSession, *, update: ThemesUpdate, principal: Principal) -> list[ThemeOut]
```

**Behaviour rules.**
1. Optional update fields: a field listed in `backend/tests/api_shapes.json` `nullable` for its model is typed `T | None = None` (explicit `null` clears the column: `publisher`, `notes`); every other optional field is typed `T | SkipJsonSchema[None] = None` (fact 14) and a `model_validator(mode="after")` rejects an explicit `null` with `ValueError(f"{alias} may not be null")` (→ 422). Only `model_fields_set` fields are applied.
2. Routes and permissions: `GET /sources`, `GET /sources/feeds`, `GET /sources/domains`, `GET /themes` → VIEW; `PATCH /sources/feeds/{feed_id}`, `PATCH /sources/domains/{domain_id}`, `PUT /themes` → SETTINGS.
3. `GET /sources` query: `domain: str | None`, `tier: Annotated[int | None, Query(ge=1, le=3)]`, `access_mode: Annotated[AccessMode | None, Query(alias="accessMode")]`, `q: Annotated[str | None, Query(max_length=200)]`, `since: datetime | None` (naive → UTC), `limit`/`offset` as RES-21. Filters: `domain == urls.normalize_host(domain)`; `tier`; `access_mode`; `q` stripped, blank ignored, `title ILIKE %q%` with `\`, `%`, `_` escaped (`escape="\\"`); `published_at >= since`. Order `published_at DESC NULLS LAST, id DESC`. Response `Page[LedgerSourceOut]`.
4. `GET /sources/feeds` ordered `group_name, name` (`group` ← `group_name`); `GET /sources/domains` ordered `domain`; `GET /themes` ordered `sort_order, key` (inactive themes included).
5. `update_feed`: row `SELECT … FOR UPDATE`; missing → `ProblemError(404, "Feed not found", f"no feed with id {feed_id}")`. Empty `model_fields_set` → current row, no audit. `theme_keys` containing keys not in `blog_discovery_themes` → `ProblemError(422, VALIDATION_TITLE, [{"type": "value_error", "loc": ["body", "themeKeys"], "msg": "unknown theme keys: " + ", ".join(sorted(unknown))}])`. `is_enabled: true` also sets `consecutive_failures=0`, `disabled_reason=None`; `is_enabled: false` sets `disabled_reason="disabled by an administrator"`. `audit(db, actor_user_id=principal.user_id, action="source_feed.update", entity_type="blog_source_feed", entity_id=str(feed_id), details={"changes": update.model_dump(mode="json", include=fields_set)})`; commit.
6. `update_domain`: same pattern, 404 `Domain not found`. When `verification_allowlisted` is set true on a row that is currently false and the count of other allow-listed rows is ≥ `MAX_ALLOWLISTED_DOMAINS` → `ProblemError(422, VALIDATION_TITLE, [{"type": "value_error", "loc": ["body", "verificationAllowlisted"], "msg": "at most 100 domains may be verification-allowlisted"}])`. Audit `source_domain.update`, `entity_type "blog_source_domain"`.
7. `ThemesUpdate` validator: duplicate keys → `ValueError("duplicate theme keys: …")` (422). `replace_themes`: themes locked `FOR UPDATE`; existing key → update `name, description, query_templates, pillar_keys, is_active, sort_order` (`last_searched_at` kept); new key → insert; existing keys absent from `items` that are active → `is_active=False` (never deleted). Audit `themes.update`, `entity_type "blog_discovery_theme"`, `entity_id None`, `details {"created": sorted, "updated": sorted, "deactivated": sorted}`; commit; return `list_themes`.

**Tests to write first** (`test_res_sources_api.py`; `seeded_db` for catalogue rows; `login_as(Role.ADMIN)` for writes with `X-CSRF-Token`):
- `test_list_sources_filters_and_order`: four ledger rows (dated 09-16, 09-14, undated, 09-15; titles `"100% of clinics"`, `"100 of clinics"`, `"Undated"`, `"Tier two"`; one `abstract_only`, one tier 2, domains `fda.gov`/`cms.gov`) → default order `[09-16, 09-15, 09-14, undated]`; `?domain=WWW.FDA.GOV` returns only fda.gov rows; `?tier=2` one row; `?accessMode=abstract_only` one row; `?q=100%25` returns only `"100% of clinics"`; `?since=2026-09-15T00:00:00Z` two rows; item keys equal `props["LedgerSourceOut"]`.
- `test_list_sources_validation`: `?tier=4` → 422; `?accessMode=bogus` → 422.
- `test_list_catalogue`: viewer → feeds 31, first `group "ai_labs"`, keys equal `props["SourceFeedOut"]`; domains 44 ordered by `domain`; themes 15 ordered by `sortOrder`.
- `test_patch_feed_enable_clears_failures`: Lancet row with `consecutive_failures=3`, `disabled_reason "x"` → `{"isEnabled": true}` → 200, `isEnabled true`, `consecutiveFailures 0`, `disabledReason null`; one `audit_log` row `source_feed.update` with `details == {"changes": {"isEnabled": true}}`; `{"tier": 2, "themeKeys": ["regulation"]}` → applied.
- `test_patch_feed_disable_sets_reason`: `{"isEnabled": false}` → `disabledReason "disabled by an administrator"`.
- `test_patch_feed_errors`: unknown id → 404 `Feed not found`; `{"tier": 5}` → 422; `{"themeKeys": ["nope"]}` → 422 with `detail[0]["msg"] == "unknown theme keys: nope"`; `{"isEnabled": null}` → 422 when `isEnabled` is not in the shape file's `nullable`; `{}` → 200 and no audit row.
- `test_patch_feed_rbac`: no session → 401; `Role.PUBLISHER` → 403, `detail "missing permission blog.settings"`.
- `test_patch_domain`: `{"publisher": null, "fetchPolicy": "never"}` → 200, `publisher null`, `fetchPolicy "never"`; audit `source_domain.update`.
- `test_domain_allowlist_cap`: add allow-listed domains until 100 rows are allow-listed; `{"verificationAllowlisted": true}` on a non-allow-listed domain → 422, `title "Request validation failed"`, `detail[0]["msg"] == "at most 100 domains may be verification-allowlisted"`; the same body on an already allow-listed domain → 200.
- `test_patch_domain_errors_and_rbac`: unknown id → 404 `Domain not found`; no session → 401; `Role.REVIEWER` → 403.
- `test_put_themes`: `regulation.last_searched_at` set first; body = the 14 seeded themes except `burnout` (with `regulation` renamed `Regulation and policy`) plus new `digital_health_equity` → 200 list of 16; `burnout` `isActive false`; `regulation` name changed and `lastSearchedAt` unchanged; audit `details == {"created": ["digital_health_equity"], "updated": <14 keys sorted>, "deactivated": ["burnout"]}`.
- `test_put_themes_validation_and_rbac`: duplicate keys → 422; key `"Bad Key"` → 422; 11 templates → 422; `{"items": []}` → 422; no session → 401; `Role.EDITOR` → 403.

**Verification.** red: assertions fail against FOUND's empty router (404s); green `12 passed`; `tests/api/test_rbac_routes.py` passes; `RES_LINT` exits 0.

**Acceptance covered.** §4.3 (all seven routes, models, errors, audit actions `source_feed.update`, `source_domain.update`, `themes.update`); §8.3 success/401/403/problem tests; §10.1 "UI … Sources page" (Also: RES API); §10.5 "Settings: … themes" (Also: RES themes API); ARCHITECTURE §13 Sources page actions (enable/disable feed, edit tier, edit themes).

### RES-23: OpenAPI shape test

**Files.** Create `backend/tests/research/test_res_openapi.py`.

**Interfaces (consumes).** `app.openapi()` (the `app` fixture), `backend/tests/api_shapes.json` (FOUND, frozen).

**Behaviour rules.**
1. `RES_MODELS = ["ResearchQueryOut", "ResearchRunOut", "FindingOut", "ResearchRunDetail", "LedgerSourceOut", "SourceFeedOut", "SourceFeedUpdate", "SourceDomainOut", "SourceDomainUpdate", "ThemeOut", "ThemeIn", "ThemesUpdate"]`.
2. Component lookup: `components[name]`, else `components[f"{name}-Output"]`, else `components[f"{name}-Input"]`; none → test failure naming the model.
3. `nullable(component)` = property names whose schema has an `anyOf` containing `{"type": "null"}`.
4. A mismatch is never fixed by editing `api_shapes.json`: the model is corrected, or a `Request:` line goes to `requests/res.md` (§8.3).

**Tests to write first.**
- `test_component_matches_shape_file` (parametrised over `RES_MODELS`, 12): `set(component["properties"]) == set(shapes[name]["props"])` and `nullable(component) == set(shapes[name]["nullable"])`.
- `test_research_and_sources_routes_declared`: the OpenAPI `paths` contain exactly these RES operations with these success response schemas: `GET /api/blog-agent/research-runs` → `Page_ResearchRunOut_`; `GET /api/blog-agent/research-runs/{research_run_id}` → `ResearchRunDetail`; `GET /api/blog-agent/sources` → `Page_LedgerSourceOut_`; `GET /api/blog-agent/sources/feeds` → array of `SourceFeedOut`; `PATCH /api/blog-agent/sources/feeds/{feed_id}` → `SourceFeedOut`; `GET /api/blog-agent/sources/domains` → array of `SourceDomainOut`; `PATCH /api/blog-agent/sources/domains/{domain_id}` → `SourceDomainOut`; `GET /api/blog-agent/themes` → array of `ThemeOut`; `PUT /api/blog-agent/themes` → array of `ThemeOut`; and the operations tagged `research` or `sources` are exactly these nine.

**Verification.** red before RES-21/RES-22 (components missing); green `13 passed`; `RES_LINT` exits 0.

**Acceptance covered.** §8.3 per-track OpenAPI test against the frozen shape file; D8.

### RES-24: `record-fixtures` CLI

**Files.** Modify `pkg/research/record_fixtures.py` (FOUND stub); create `backend/tests/research/test_res_record_fixtures.py`.

**Interfaces (produces).**
```python
RECORDED_HEADERS: frozenset[str]   # {"content-type", "etag", "last-modified", "cf-mitigated", "location"}
@dataclass(frozen=True)
class RecordedResponse:
    url: str; status: int; headers: dict[str, str]; body: bytes; kind: str
class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport, *, feed_keys: Collection[str]) -> None
    records: list[RecordedResponse]
def live_recording_allowed(settings: Settings, environ: Mapping[str, str]) -> bool
def classify_recording(url: str, *, content_type: str | None, body: bytes, feed_keys: Collection[str]) -> str
def write_fixture_dirs(out: Path, records: Sequence[RecordedResponse], *, anchor: datetime) -> dict[str, int]
async def record(settings: Settings, *, out: Path, pillar: str | None, max_pages: int, now: Callable[[], datetime]) -> dict[str, int]
def build_parser() -> argparse.ArgumentParser
def main(argv: Sequence[str], settings: Settings) -> int
```

**Behaviour rules.**
1. `main`: a leading `"record-fixtures"` token in `argv` is dropped (FOUND's dispatch may pass either form). Options: `--out PATH` (required), `--pillar {A,B,C,D,E,NARRATIVE}`, `--max-pages INT` (1..200, default 40), `--force`. Parse errors (`SystemExit`) → return 2.
2. `live_recording_allowed` = `settings.mock_mode` or (`environ.get("BLOG_LIVE_TESTS") == "1"` and `environ.get("BLOG_LIVE_MAX_SPEND_USD", "").strip() != ""`). False → stderr `record-fixtures: refused: recording with BLOG_AGENT_MOCK_MODE=false needs BLOG_LIVE_TESTS=1 and BLOG_LIVE_MAX_SPEND_USD (CONTRACT §9 rule 6)`, return 2, nothing created.
3. `--out` exists, is non-empty and `--force` is absent → stderr `record-fixtures: refused: <out> is not empty (use --force)`, return 2.
4. `record` (run with `asyncio.run`; `now` = `lambda: datetime.now(UTC)` in `main`): enabled feeds from `feed_specs_from_seed(load_seed_file("feeds.yaml")["feeds"])`, rules from `domain_rules_from_seed(load_seed_file("domains.yaml")["domains"])`, keywords from `load_seed_file("pillars.yaml")` (the chosen pillar's name and topics, or every pillar's when `--pillar` is absent); `open_environment_for(settings, now=now, wrap_transport=lambda inner: recording)`; every feed collected (`window_days=settings.research_window_days`); `merge_signals` → `select_candidates(limit=max_pages)` → `retrieve(existing={})`. It opens no database session, builds no gateway, and makes no search or model call (no paid calls).
5. `RecordingTransport` forwards to `inner` and records each response (`url`, `status`, headers filtered to `RECORDED_HEADERS`, full body read, `kind` from `classify_recording`).
6. `classify_recording`: `fixture_match_key(url, VOLATILE_PARAMS)` in `feed_keys` → `feeds`; host `eutils.ncbi.nlm.nih.gov` → `pubmed`; host `www.federalregister.gov` with path under `/api/` → `federal_register`; path `/media/178541/download` on `www.fda.gov` → `fda`; content type starting `application/pdf` or body starting `%PDF-` → `pdfs`; else `pages`.
7. `write_fixture_dirs`: per kind `out/<kind>/index.json` = `{"anchor": anchor as "YYYY-MM-DDTHH:MM:SSZ", "entries": [...]}` sorted by `url`; a later response with the same match key replaces an earlier one; body file name `sha256(match_key).hexdigest()[:16]` plus `.xml` (feeds), `.json`/`.xml` by content type (pubmed), `.json` (federal_register), `.csv` (fda), `.pdf` (pdfs), `.html` (pages); an empty body gives `"file": null`. With `--force`, each written kind directory is emptied first. Returns entry counts per kind.
8. Success → stdout `record-fixtures: feeds=<n> pubmed=<n> federal_register=<n> fda=<n> pages=<n> pdfs=<n> out=<out>`, return 0. Any other exception → stderr `record-fixtures: failed: <Class>: <message>`, return 1.

**Tests to write first** (`test_res_record_fixtures.py`; mock `settings`; `main` runs in `asyncio.to_thread` because it calls `asyncio.run`):
- `test_record_in_mock_mode_through_cli`: `cli.main(["record-fixtures", "--out", str(tmp_path / "rec")], settings=settings)` → 0; stdout matches `^record-fixtures: feeds=25 pubmed=\d+ federal_register=1 fda=1 pages=\d+ pdfs=\d+ out=.+$`; `load_fixture_set(tmp_path / "rec", scenario=None)` succeeds; for every `feeds` entry the written body equals the shipped fixture body for that URL; the `pages` index contains the S1 page URL.
- `test_live_recording_allowed` (parametrised, 4): mock mode, empty environ → True; real mode, empty environ → False; real mode, `BLOG_LIVE_TESTS=1` only → False; real mode, both set → True.
- `test_refuses_live_without_env`: `settings.model_copy(update={"mock_mode": False})`, both variables removed with `monkeypatch.delenv(..., raising=False)` → 2; stderr contains `refused`; the out directory does not exist.
- `test_refuses_non_empty_out_without_force`: out holds `x.txt` → 2; with `--force` → 0.
- `test_argv_forms`: `main(["--out", p1], settings)` → 0; `main(["record-fixtures", "--out", p2], settings)` → 0; `main([], settings)` → 2; `main(["--out", p3, "--max-pages", "0"], settings)` → 2.
- `test_classify_recording` (parametrised, 6): a seeded feed URL → `feeds`; esearch URL → `pubmed`; `https://www.federalregister.gov/api/v1/documents.json?x=1` → `federal_register`; the FDA CSV URL → `fda`; a page with `application/pdf` → `pdfs`; an HTML page → `pages`.

**Verification.** red `NotImplementedError: RES implements this` (FOUND stub, exit through the CLI); green `14 passed`; `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/db/test_cli.py` → all passed; `RES_LINT` exits 0.

**Acceptance covered.** §10.1 "`record-fixtures` CLI … CLI test in mock mode"; §9 live-spend rule 6 (exit 2 guard only when mock mode is off); RESEARCH_ARCHITECTURE §11 (capture of feed, page, PDF and PubMed fixtures).

### RES-final: track verification

**Steps (Docker only).**
1. `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py` → all passed.
2. `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/research` → `267 passed` (per-task counts RES-1…RES-24: 21, 8, 10, 9, 5, 26, 10, 14, 14, 11, 12, 14, 18, 8, 8, 7, 10, 7, 7, 3, 6, 12, 13, 14), with no failures, errors or skips.
3. `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_res_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/api/test_rbac_routes.py tests/db/test_seed.py tests/db/test_cli.py tests/unit/test_prompt_registry.py tests/unit/test_search_fixture.py tests/unit/test_gateway.py` → all passed (shared surfaces RES content affects: routers, seed YAML, CLI dispatch, prompt files, `broad.json` shadowing `default.json`).
4. `RES_LINT` → `All checks passed!`, `… files already formatted`, `Success: no issues found`.
5. `grep -rn "gpt-\|gemini-\|claude-" backend/src/mdcopilot_blog/research backend/src/mdcopilot_blog/agents/research_analyst.py backend/src/mdcopilot_blog/services/research_runs.py backend/src/mdcopilot_blog/services/sources.py` → no output (§11 rule 12).
6. `grep -rn "import pydantic_ai\|from pydantic_ai\|from mdcopilot_blog.db" backend/src/mdcopilot_blog/agents/research_analyst.py backend/src/mdcopilot_blog/domain/urls.py backend/src/mdcopilot_blog/domain/tiers.py backend/src/mdcopilot_blog/domain/claim_rules.py backend/src/mdcopilot_blog/domain/query_plan.py` → no output (layering).
7. `docker ps -a --filter name=p2p-res- --format '{{.Names}}'` → no output.
8. Track report lists red/green evidence per task, the `Request:` lines filed in `requests/res.md` (if any), and "RES makes no paid calls; no `Live:` lines".


**Acceptance mapping (CONTRACT §10.1 RES rows and RES "Also" items).**

| Bullet | Where proven |
|---|---|
| Collectors (RSS/Atom quirks, PubMed esearch/esummary/efetch, Federal Register, FDA CSV diff) | RES-9, RES-10, RES-11 |
| Retriever (HTTP/2, per-host limits, Protego, SSRF guard incl. redirects, conditional GET, bot-wall) | RES-6 (`test_build_http_client_arguments` asserts `http2=True`) |
| Extractor + ledger (trafilatura, htmldate, newspaper4k fallback < 150 words, pypdfium2, tiers, canonical URLs, `date_source`, `access_mode`) | RES-1, RES-2, RES-8, RES-13, RES-16 |
| Query planner with theme rotation | RES-4 (`test_every_theme_within_three_days`), RES-15 |
| Research Analyst with claim rules in code | RES-3, RES-14, RES-17 |
| `record-fixtures` CLI; full mock fixture set | RES-24; RES-7 |
| Mock broad scan < 10 s and every `FACT` finding cites a ledger id | RES-17 `test_mock_broad_scan_under_ten_seconds` |
| Live broad scan: zero findings citing a URL outside the ledger (enforced and tested); per-phase latency stored | RES-14 (marker-only output check), RES-17 (ledger-id check, latency keys); the live run itself is INT's §9 gate |
| PubMed fixture → non-empty abstract, `access_mode=abstract_only` | RES-13 `test_retrieve_pubmed_abstract`, RES-16 S3 row |
| Failure: one feed down | RES-15 `test_one_feed_down` |
| Failure: search 5xx → partial coverage | RES-12, RES-17 `test_search_5xx_gives_partial_coverage` |
| Failure: blocked page → metadata-only | RES-13 `test_retrieve_blocked_page`, RES-16 S5 row |
| Failure: invalid analyst output retried then next model | RES-14, RES-17 `test_invalid_analyst_output_retried_then_next_model` |
| UI Research and Sources pages (Also: RES API) | RES-21, RES-22, RES-23 |
| Tables and seed YAML (Also: RES) | RES-5 |
| §5.8 RES golden-path invariants | RES-7, RES-14, RES-16, RES-17 `test_golden_path_invariants`, RES-18 (deep) |
| §5.6 seams for INT/QUAL/ART | RES-15 to RES-20 |
| Phase 3 `discover_topics` (Also: RES seams), Phase 4 deep research and regenerate research (Also: RES), Phase 5 ≤3 verification searches (Also: RES), Phase 8 feed-health roll-up (Also: RES) | RES-15/16/17, RES-18, RES-19, RES-20 |
| §8.3 route tests and OpenAPI shape test | RES-21, RES-22, RES-23 |

---

## Decisions this plan makes inside the contract

1. **Signals item shape.** `blog_research_runs.signals` keeps exactly the §3.1 keys. PubMed abstracts are therefore fetched in `build_ledger` (efetch is retrieval), and verification per-query source lists and synthesis search hints are rebuilt by splitting stored signals by `queries[i].sourceCount`.
2. **`partial` status** means at least one search query failed; feed failures stay on the feed rows (the `counts` keys are fixed).
3. **Deep research thresholds**: "dated" means any `published_at` (no window), and at least one Tier 1/2 source with text is also required, matching quality gate 1.
4. **Ledger rows** are updated only to add text to a metadata-only row (or refresh its fetch status after 24 h); existing text snapshots are never overwritten or cleared.
5. **Preprints** are Tier 2; medical associations use `SourceType.OTHER` with Tier 1 (the enum has no association value).
6. **Robots.txt** is checked for page fetches only; feeds and official APIs (E-utilities, Federal Register, FDA CSV) are machine endpoints and skip it.
7. **FDA CSV** first poll is a silent baseline; later polls emit new submission numbers dated by the CSV's `Last-Modified`.
8. **`ThemesUpdate.items`** accepts 1..50 items (an empty list would deactivate every theme and stop the broad scan).

## Open questions for the controller (the plan follows the contract meanwhile)

1. **Plan path.** This file is `RES.md` as assigned; CONTRACT §2.2 names `res.md`. They are the same file on the default macOS filesystem but not on a case-sensitive one.
2. **`record-fixtures` dispatch.** FOUND's parser must hand the options after the subcommand to `record_fixtures.main(argv, settings)` (for example `argparse.REMAINDER`); RES accepts both forms. The CLI records free sources only (feeds, APIs, pages, PDFs), because recording search or model output is a paid call, while RESEARCH_ARCHITECTURE §11 also lists search and model fixtures.
3. **Type stubs.** `feedparser`, `newspaper4k` and `pypdfium2` ship no `py.typed`, and `dateutil` has no stubs in the dev group. RES uses per-import `# type: ignore[import-untyped, unused-ignore]`; the alternative is a ruling that adds `types-python-dateutil` and mypy overrides in FOUND's `pyproject.toml`.
4. **Test gateway construction.** `LLMGateway.__init__` and the recorder interface are not in the frozen list. RES tests build `LLMGateway(settings=, prompts=, recorder=, model_factory=, search_provider=)` with a fake recorder implementing `run_cost` and `budget_spent`, as Phase 1 tests do. PROV should keep any new constructor parameters defaulted.
5. **Search error types.** Retry classification relies on the exceptions `OpenAIWebSearchProvider` raises (a `status_code` attribute, `httpx`/`httpx2` transport errors, or the names `APIConnectionError`/`APITimeoutError`). PROV should confirm these, or map them to one gateway exception.
6. **Ledger updates.** §5.5 rule 3 lists the head tables that may be updated and does not mention `blog_sources`. RES updates a ledger row only to add text to a metadata-only row, or to refresh its fetch status after 24 h. The alternative is never to update, so a source blocked once stays metadata-only.
7. **Update-model nullability.** §4.3 marks the update models "all optional" without saying which fields accept `null`. RES follows `api_shapes.json`; the suggestion is that only `SourceDomainUpdate.publisher` and `notes` are nullable.
8. **Catalogue drift (verified 2026-09-17).** The Lancet Digital Health and NEJM AI feeds return 403 even with browser headers (seeded disabled); npj and HHS need `browser_like`; the Google blog feed URLs moved. RESEARCH_ARCHITECTURE §2 still lists these as confirmed.
9. **FDA device URLs.** The accessdata `pmn.cfm`, `denovo.cfm` and `pma.cfm` patterns were not verified live. The signals are metadata-only.
10. **SSRF residual risk.** The guard resolves then connects, which leaves a DNS-rebinding window. Pinning the connection to the checked address is left for HARD to assess.
11. **403 tests.** §8.3 asks for a 403 test per route, but every role holds `blog.view`, so the four RES GET routes cannot return 403.
