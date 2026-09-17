# Track TOP: Topic intelligence — implementation plan

Status: plan for the parallel stage (W3). Date: 2026-09-17. Binding contract: `docs/blog-agent/plans/phases-2-10/CONTRACT.md` (revision 2). When this plan and the contract disagree, the contract wins. Paths: `pkg/` = `backend/src/mdcopilot_blog/`. (The contract names this file `top.md`; the macOS file system is case-insensitive, so `TOP.md` is the same file.)

## Header

**Goal.** Build Phase 3 topic intelligence as step bodies, pure domain code and API routes, with no workflow code:
- the Topic Strategist agent (exactly 3 ideas, marker-checked);
- the novelty engine (topic, argument, news-reuse, headline and example checks against our topics, articles and MDCopilot's published posts);
- weighted topic scoring with a stored breakdown;
- candidate selection and promotion;
- the read-only MDCopilot post sync;
- the content-diversity services other tracks call (avoid bundle, version features, diversity gates, duplicate gate);
- every `/topics*` endpoint.
INT wires the steps into `discover_topics`, `regenerate_topics`, `change_topic` and `maintenance`.

**Spec sections implemented.**
- ARCHITECTURE §5.1 (the D5, D6 and D7 step bodies and the manual-topic path), §5.3 (the `regenerate_topics` and `change_topic` intake from the API), §7 (Topic Strategist row), §8 (novelty engine), §8.1 (content diversity: features, avoid bundle, enforcement, diversity panel data), §9 (topic scoring), §13 (the Today's Ideas and Topics page APIs and the dashboard diversity panel API), §16 (topics endpoints).
- IMPLEMENTATION_PLAN Phase 3 (build and acceptance).
- CONTRACT §4.4, §5.6 (TOP seams: `topic_steps`, `diversity`, `novelty`, `external_posts`; agent spec row), §5.8 (TOP golden-path invariant), §10.2 (TOP rows) and the TOP "Also" rows in §10.3, §10.4, §10.5 and §10.8, plus Rule B's API half (§5.7).

**Owned files (CONTRACT §2.2 TOP).**

| Path | Notes |
|---|---|
| `pkg/agents/topic_strategist.py` | |
| `pkg/services/topics.py` | API services |
| `pkg/services/topic_steps.py` | stub by FOUND |
| `pkg/services/novelty.py`, `pkg/services/diversity.py`, `pkg/services/external_posts.py` | stubs by FOUND |
| `pkg/domain/scoring.py`, `pkg/domain/novelty.py`, `pkg/domain/diversity.py`, `pkg/domain/headlines.py` | pure |
| `pkg/api/routers/topics.py`, `pkg/api/schemas_topics.py` | stub by FOUND |
| `backend/prompts/ideation/**` | |
| `backend/fixtures/mock/llm/ideation/**` | |
| `backend/fixtures/mock/mdcopilot_public_api/**` | recorded `GET /api/v1/blogs` pages |
| `backend/fixtures/mock/scenarios/topics_*/**` | (this plan creates no scenario overlay) |
| `backend/tests/topics/**` | |
| `docs/blog-agent/plans/phases-2-10/top.md` | this plan |
| `.superpowers/sdd/phases-2-10/requests/top.md` | `Request:` lines (§2 rules) |

**Extension points consumed.**
- Phase 1:
  - `api.deps`: `SessionDep`, `SettingsDep`, `WorkflowClientDep`, `Principal`, `require_permission`, `utcnow`.
  - `api.schemas`: `ApiModel`, `Page`.
  - `errors.ProblemError`, `services.audit.audit`.
  - `db.models`: `BlogRun`, `ContentPillar`, `AuditLog`, `LlmCall`.
  - `domain.enums`: `Permission`, `Role`, `RunStatus`, `ArticleStatus`, `AgentName`, `CallKind`.
  - `domain.contracts`: `Contract`, `PillarKey`, `NewsRef`, `ScoreItem`, `NoveltyNeighbour`, `NoveltyResult`, `NoveltyDecision`, `GateResult`, `TitleOptions`.
  - `llm.gateway`: `AgentSpec`, `CallContext`, `AgentResult`, `LLMGateway`, `RouteExhausted`, `build_gateway`, `mock_embedding`.
  - `llm.recorder.CallRecorder`, `llm.routes.ModelChoice`, `llm.search.fixture.FixtureSearchProvider`.
  - `prompts.registry`: `PromptRegistry`, `default_prompt_root`.
  - `ids`: `uuid7`, `new_trace_id`.
  - `settings.Settings`.
  - `workflows.client`: `FakeWorkflowClient`, `EnqueueCall`, `WorkflowClientProtocol`.
- FOUND:
  - `domain.enums`: `CandidateStatus`, `HeadlinePattern`, `GateId`, `AccessMode`, `ResearchRunKind`.
  - `domain.contracts`: `Marker`, `AvoidBundle`, `RecentArticleRef`, `ArticleSection`.
  - `domain.config`: `EffectiveConfig`, `NoveltyConfig`, `DiversityConfig`, `ScoreWeights`, `BrandProfileValues`.
  - `domain.text`: `strip_citation_markers`, `normalize_for_match`, `WORD_RE`.
  - `domain.errors`: `OutputRejected`, `UnknownCitationMarker`.
  - `agents.common`: `UNTRUSTED_NOTICE`, `NumberedSource`, `number_sources`, `render_source_list`, `resolve_markers`.
  - `services.config`: `load_effective_config`, `load_brand_profile`, `pillar_for_date`.
  - `services.step_context`: `StepContext` (`with_ids`, `now`), `build_api_step_context`.
  - `services.enqueue`: `ensure_agent_enabled`, `enqueue_workflow`.
  - `api.schemas_common`: `ActionAccepted`, `SourceRefOut`, `ReasonRequest`.
  - `workflows.names`: `WORKFLOW_PRODUCE_ARTICLE`, `WORKFLOW_CHANGE_TOPIC`, `WORKFLOW_REGENERATE_TOPICS`, `QUEUE_PIPELINE`, `QUEUE_INTERACTIVE`.
  - ORM: `TopicCandidateRecord`, `Topic`, `ExternalPost`, `LedgerSource`, `ResearchRun`, `ResearchFindingRecord`, `FindingSource`, `DiscoveryTheme`, `Article`, `ArticleVersion`, `ArticleSource`, `VersionFeatures`, `VersionEmbedding`.
  - Seam stub modules and result models in §5.6: `IdeateResult`, `NoveltyScoreResult`, `SelectResult`, `DiversityEvaluation`, `SyncReport`.
  - `LLMGateway.run(..., route_override=, prompt_version=, output_check=)`, `AgentSpec.reasoning`, `FixtureRegistry` cases form (`promptContains`).
  - Settings: `mdcopilot_public_api_url`, `mdcopilot_sync_page_size`, `fetch_connect_timeout_seconds`, `fetch_read_timeout_seconds`, `embedding_model`, `embedding_dimensions`, `discovery_timeout_minutes`, `production_timeout_minutes`, `agent_enabled`, `app_version`.
  - Test fixtures: `settings`, `db_session`, `sessionmaker_committing`, `committed_seed`, `mock_step_context`, `make_research_graph`, `make_article_graph`, `app`, `client`, `login_as`, `committing_client`, `committing_login_as`, `fake_workflow_client`; `tests/api_shapes.json`; `tests/foundation/test_found_imports.py`.
- PROV: nothing beyond the frozen gateway signatures. TOP runs only in mock mode and never makes a paid call (§9 rule 1).

**Test database and commands** (run from `mdcopilot-blog/`; the stack's `db` service must be up).
- Database: `BLOG_TEST_DB=mdcopilot_blog_top_test`. A reviewer, or a second process of this track, uses `mdcopilot_blog_top_review_test`.
- One file:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/<file>.py
  ```
- Whole track:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics
  ```
- Shared-surface check (before calling a red test TOP's own failure, §2 rules (b)):
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
  ```
- Lint and type gate (owned paths only):
  ```bash
  docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c "ruff check --no-cache src/mdcopilot_blog/agents/topic_strategist.py src/mdcopilot_blog/services/topics.py src/mdcopilot_blog/services/topic_steps.py src/mdcopilot_blog/services/novelty.py src/mdcopilot_blog/services/diversity.py src/mdcopilot_blog/services/external_posts.py src/mdcopilot_blog/domain/scoring.py src/mdcopilot_blog/domain/novelty.py src/mdcopilot_blog/domain/diversity.py src/mdcopilot_blog/domain/headlines.py src/mdcopilot_blog/api/routers/topics.py src/mdcopilot_blog/api/schemas_topics.py tests/topics && ruff format --check --no-cache src/mdcopilot_blog/agents/topic_strategist.py src/mdcopilot_blog/services/topics.py src/mdcopilot_blog/services/topic_steps.py src/mdcopilot_blog/services/novelty.py src/mdcopilot_blog/services/diversity.py src/mdcopilot_blog/services/external_posts.py src/mdcopilot_blog/domain/scoring.py src/mdcopilot_blog/domain/novelty.py src/mdcopilot_blog/domain/diversity.py src/mdcopilot_blog/domain/headlines.py src/mdcopilot_blog/api/routers/topics.py src/mdcopilot_blog/api/schemas_topics.py tests/topics && mypy --cache-dir=/tmp/mypy --follow-imports=silent src/mdcopilot_blog/agents/topic_strategist.py src/mdcopilot_blog/services/topics.py src/mdcopilot_blog/services/topic_steps.py src/mdcopilot_blog/services/novelty.py src/mdcopilot_blog/services/diversity.py src/mdcopilot_blog/services/external_posts.py src/mdcopilot_blog/domain/scoring.py src/mdcopilot_blog/domain/novelty.py src/mdcopilot_blog/domain/diversity.py src/mdcopilot_blog/domain/headlines.py src/mdcopilot_blog/api/routers/topics.py src/mdcopilot_blog/api/schemas_topics.py"
  ```
  This command is called **TOP-LINT** below.

**Owner inputs.**

| Input | Needed for | When it is missing (the default) |
|---|---|---|
| `BLOG_MDCOPILOT_PUBLIC_API_URL` (production public API base URL including `/api/v1`) | Live novelty sync of published posts | `sync_mdcopilot_posts` returns `SyncReport(enabled=False, fetched=0, inserted=0, updated=0, embedded=0)` and opens no connection. Tests use hand-built pages in `backend/fixtures/mock/mdcopilot_public_api/` over `httpx.MockTransport`. The page shape comes from `mdcopilot-backend/app/schemas/blog.py::BlogResponse` (read-only, 2026-09-17): a JSON array of `{id, title, slug, content, excerpt, featured_image, status, author_id, author_name, created_at, updated_at, published_at}`, paged by `skip`/`limit`, newest `published_at` first. The track is "complete, pending owner input" (§9 rule 7). |
| Provider keys | Nothing in TOP | TOP never makes paid calls. |

**Plan rulings (design choices inside the contract; reviewers check code against these).**
- P1. `PATCH /topics/{id}` changes stored text only. It does not re-embed, re-check novelty or re-score. The stored `novelty` describes the text as proposed (open question 4).
- P2. The novelty headline-pattern warning ignores `HeadlinePattern.STATEMENT`. Most headlines are statements, so a daily cadence would put every statement candidate in WARN, and auto mode selects only PASSED. The diversity gate `headline_diversity` counts every pattern, including `statement`, because it only warns.
- P3. Repetition counts include the item being checked: `uses = stored matches in the window + 1`.
- P4. The diversity gates and gate 6 compare a version's article only with **other live articles created at or before it** (`other.created_at <= this article's created_at`, `other.id != this id`). A recheck of an older article is never failed by a later copy of itself.
- P5. External posts have no time window in similarity searches. Gate 6 skips the external post whose `slug` equals the article's head `slug`, so our own published article, once synced back, is not its own duplicate.
- P6. The mock ideation fixture has five idea sets (round 1 and rounds 2–5, selected by `Round: <n>\n` in the user prompt). In mock mode, rounds 6 and later exhaust the route, because every set repeats an avoided title.
- P7. `score_breakdown` keys are camelCase: `timeliness`, `novelty`, `evidence`, `mdcopilotRelevance`, `audience`, `editorial` (open question 5).
- P8. `blog_topic_candidates` has no keywords column, so `promote_candidate` derives `blog_topics.keywords` deterministically with `domain.diversity.extract_keywords` (open question 9).
- P9. When a new round is ideated, earlier-round candidates in `PROPOSED`, `PASSED`, `WARNED` or `REJECTED` become `SUPERSEDED`. `SELECTED` (a machine or human choice) and `DISMISSED` (a human decision) keep their status.
- P10. A manual candidate's pillar falls back in this order: the `pillar_key` argument, then `pillar_for_date(run.run_date)`, then the first active pillar by `sort_order`. `tone` is not stored on the candidate, because the Writer reads `blog_runs.params["tone"]` (§5.4).
- P11. The sync never deletes `blog_external_posts` rows. A post that disappears from the public list keeps its row.
- P12. `GET /topics` for an existing run with no candidates returns 200 with `round: 0`, `roundsAvailable: []`, `shortfall: false` and `items: []`.
- P13. Selecting a `PROPOSED` candidate (novelty not run yet) returns 409 `Topic cannot be selected`, because `promote_candidate` accepts only PASSED or WARNED.
- P14. A `PATCH /topics/{id}` body with no fields returns 422 `Request validation failed`.
- P15. `POST /topics/{id}/reject` on any status except `SELECTED` sets `DISMISSED` and overwrites `rejected_reason`.
- P16. Candidate `sources` in API responses carry `marker: null`, because markers are per-prompt numbering and are not stored.

**Shared definitions used by every task.**
- **Live article:** `blog_articles.status NOT IN ('REJECTED','SUPERSEDED')`. `FAILED` is live (§4.4).
- **APPROVED_OR_LATER** = `{APPROVED, SCHEDULED, EXPORTED, PUBLISHING, PUBLISHED, PUBLISH_FAILED}`, exported as `APPROVED_OR_LATER_STATUSES: frozenset[str]` from `domain/novelty.py`, next to `NON_LIVE_ARTICLE_STATUSES = frozenset({"REJECTED", "SUPERSEDED"})`.
- **Current-version rows:** `blog_version_embeddings` and `blog_version_features` rows whose `version_id = blog_articles.current_version_id`.
- **Similarity:** `min(1.0, max(0.0, 1.0 - cosine_distance))`, rounded to 6 decimals wherever it is stored or returned.
- **Test vectors** (fixture `vectors`, TOP-0):
  - `e(i)` is a 1536-float list with `1.0` at index `i` and `0.0` elsewhere.
  - `mix(a, i, j)` is `a·e(i) + sqrt(1 − a²)·e(j)`, whose cosine with `e(i)` is exactly `a`.
- **Time:**
  - Step bodies read time only through `sc.now()`.
  - API services use `api.deps.utcnow()`.
  - `promote_candidate` uses `datetime.now(UTC)`.
  - `evaluate_diversity` and `check_article_duplicate` take the reference time from `blog_articles.created_at` of the version's article.
- **Save points:** every owned module must import cleanly at every save (§2 rules (a)). Draft the prompt as `backend/prompts/ideation/topics.v1.md.wip` and rename it when it is complete.
- **Cross-module calls** inside TOP go through the module attribute (`from mdcopilot_blog.services import novelty` then `novelty.nearest_neighbours(...)`), the same way other tracks call TOP (§2.4).
- **Verified external-API facts:** ran 2026-09-17 in `mdcopilot-blog-backend:dev` against `pgvector/pgvector:pg16`, in throwaway containers `p2p-top-*`, script `.superpowers/sdd/phases-2-10/scratch/plan-top/verify.py`.
  - `Vector` columns read back as `list[float]`.
  - `.cosine_distance(list)` orders correctly and returns `float`.
  - `ON CONFLICT` against a partial unique index needs `index_where`; without it Postgres raises `InvalidColumnReference: there is no unique or exclusion constraint matching the ON CONFLICT specification`.
  - Under async psycopg `result.rowcount` is `-1`, so inserts use `RETURNING`.
  - `mock_embedding` vectors of 39 distinct texts have `|cosine| ≤ 0.056` against another one; `base + 0.2·noise` has cosine `0.979609` with `base`.
  - `httpx.MockTransport` works with `httpx.AsyncClient` (httpx 0.28.1).

**Task order:** TOP-0 → TOP-1 → TOP-2 → TOP-3 → TOP-4 → TOP-5 → TOP-6 → TOP-7 → TOP-8 → TOP-9 → TOP-10 → TOP-11 → TOP-12 → TOP-final. Each task follows TDD: write the listed tests, run them red in Docker, implement, then run them green.

---
### TOP-0: Preflight gate and shared test helpers

**Files:**
- Modify `backend/tests/topics/conftest.py` (FOUND's docstring-only stub).
- Create `backend/tests/topics/test_top_preflight.py`.

**Interfaces.**
- Consumes the FOUND fixtures listed in the header, plus `llm.gateway.mock_embedding`, `llm.gateway.LLMGateway`, `llm.recorder.CallRecorder` and `llm.search.fixture.FixtureSearchProvider`.
- Produces these fixtures in `tests/topics/conftest.py` (function scope unless stated):
  - `vectors` (session, sync) → an object with `e(i: int) -> list[float]` and `mix(a: float, i: int, j: int) -> list[float]` (1536 floats each).
  - `make_candidate` → `async (db: AsyncSession, *, run_id: uuid.UUID, research_run_id: uuid.UUID | None = None, round_no: int = 1, position: int = 0, status: CandidateStatus = CandidateStatus.PASSED, title: str | None = None, hook: str = "Hook text", why_now: str = "Why now text", thesis: str | None = None, angle: str = "Angle text", core_argument: str | None = None, pillar_key: str = "A", source_ids: Sequence[uuid.UUID] = (), primary_source_id: uuid.UUID | None = None, examples: Sequence[str] = (), total_score: float | None = 0.5, novelty: NoveltyResult | None = None, embedding: list[float] | None = None, argument_embedding: list[float] | None = None, with_embeddings: bool = True, is_manual: bool = False) -> TopicCandidateRecord`.
    - `title` defaults to `f"Candidate {round_no}-{position}"`, `thesis` to `f"Thesis {round_no}-{position}"` and `core_argument` to `f"Argument {round_no}-{position}"`.
    - When `with_embeddings` is true and `embedding`/`argument_embedding` are None, they are `mock_embedding(title, 1536)` and `mock_embedding(core_argument, 1536)`.
    - `mdcopilot_connection="Connection text"` and `target_audience="Specialists"`.
    - `novelty` is stored as `model_dump(mode="json")` and `novelty_decision` as its `decision.value`.
    - Adds the row and flushes.
  - `make_topic` → `async (db, *, title: str, pillar_key: str = "A", thesis: str = "Thesis", angle: str = "Angle", core_argument: str = "Core argument", examples: Sequence[str] = (), keywords: Sequence[str] = (), headline_pattern: HeadlinePattern = HeadlinePattern.STATEMENT, primary_source_url: str | None = None, source_domains: Sequence[str] = (), embedding: list[float], argument_embedding: list[float], candidate_id: uuid.UUID | None = None, run_id: uuid.UUID | None = None, created_at: datetime | None = None) -> Topic` (flush; when `created_at` is given it is set explicitly).
  - `make_external_post` → `async (db, *, slug: str, title: str, excerpt: str = "", published_at: datetime | None = None, embedding: list[float] | None = None, origin: str = "api.mdcopilot.test", headline_pattern: HeadlinePattern = HeadlinePattern.STATEMENT) -> ExternalPost`.
    - `url = f"https://www.mdcopilot.health/blog/{slug}"`, `content_hash = sha256(f"{title}\n{excerpt}")` hex, `last_synced_at = datetime.now(UTC)`, `external_id = None`.
    - Flushes.
  - `add_version_embedding` → `async (db, *, version_id: uuid.UUID, kind: Literal["article", "opening", "argument"], embedding: list[float]) -> None` (`model="google:gemini-embedding-2"`, `dimensions=1536`; flush).
  - `function_model_gateway` → `(respond: FunctionDef, sessionmaker: async_sessionmaker[AsyncSession]) -> LLMGateway`. It builds `LLMGateway(settings=settings, prompts=PromptRegistry.from_directory(default_prompt_root(), agents=["ideation"]), recorder=CallRecorder(sessionmaker), model_factory=<factory returning FunctionModel(respond, model_name="mock:ideation-test")>, search_provider=FixtureSearchProvider())`.
  - `topics_url` (sync) → `"/api/blog-agent/topics"`.

**Behaviour rules.**
1. These tests are **gate tests**: they check what TOP needs from FOUND and are expected to pass as soon as they are written. A red gate test is not fixed inside TOP.
2. If `test_top_make_article_graph_is_repeatable` fails, append this line to `.superpowers/sdd/phases-2-10/requests/top.md`: `Request: make_article_graph/make_research_graph must be callable more than once in one session (reuse blog_sources rows by url_hash) — TOP diversity, gate-6 and diversity-panel tests need two or more articles — TOP-5, TOP-8, TOP-10 multi-article tests blocked`. Continue with every task. Multi-article tests stay red until FOUND follows up.
3. If `test_top_api_shapes_has_top_models` fails, file `Request: tests/api_shapes.json lacks <missing names>` and continue.
4. No fixture writes rows owned by another track. Only `blog_topic_candidates`, `blog_topics`, `blog_external_posts` and `blog_version_embeddings` (TOP's own write tables) are hand-written.

**Tests to write FIRST** (`backend/tests/topics/test_top_preflight.py`).
- `test_top_found_seams_import`
  - Import `mdcopilot_blog.services.topic_steps`, `.novelty`, `.diversity` and `.external_posts`, plus `mdcopilot_blog.api.routers.topics` and `mdcopilot_blog.api.schemas_topics`.
  - Assert these attributes exist and are coroutine functions: `ideate_topics`, `check_novelty_and_score`, `select_topic`, `create_manual_candidate`, `promote_candidate`, `build_avoid_bundle`, `record_version_features`, `evaluate_diversity`, `check_article_duplicate`, `nearest_neighbours`, `sync_mdcopilot_posts`.
  - Assert `topics.router.tags == ["topics"]`.
- `test_top_api_shapes_has_top_models`
  - Load `backend/tests/api_shapes.json`.
  - Assert its keys include `TopicCandidateOut`, `TopicRoundOut`, `TopicsGenerateRequest`, `TopicSelectRequest`, `TopicUpdate`, `TopicHistoryOut`, `ExternalPostOut`, `SimilarityOut`, `PillarCountOut`, `DomainShareOut`, `PhraseCountOut`, `DiversityPanelOut`.
- `test_top_make_article_graph_is_repeatable`
  - `a = await make_article_graph(db_session)` then `b = await make_article_graph(db_session)`.
  - Assert `a.article_id != b.article_id` and that `SELECT count(*) FROM app.blog_articles` returns 2.
- `test_top_helpers_build_rows`
  - Research graph `g = await make_research_graph(db_session)`.
  - `c = await make_candidate(db_session, run_id=g.run_id, research_run_id=g.research_run_id, source_ids=g.source_ids[:2], primary_source_id=g.source_ids[0])`.
  - `t = await make_topic(db_session, title="T", embedding=vectors.e(0), argument_embedding=vectors.e(1))`.
  - `p = await make_external_post(db_session, slug="s", title="P", embedding=vectors.e(2))`.
  - Assert:
    - `c.status == "PASSED"`, `len(c.embedding) == 1536` and `c.source_ids == [str(g.source_ids[0]), str(g.source_ids[1])]`;
    - reading `t` back gives `embedding[0] == 1.0`;
    - `p.url == "https://www.mdcopilot.health/blog/s"`;
    - `sum(x * y for x, y in zip(vectors.mix(0.9, 0, 1), vectors.e(0))) == pytest.approx(0.9)`.

**Implementation notes.** `make_candidate` stores `source_ids` as strings and `relevant_news=[]`, `rubric={}`, `score_breakdown={}`.

**Verification** (TDD order: write the four tests, run them, expect green; any red gate test follows rules 2 and 3):
```bash
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_preflight.py
```
Expected: `4 passed`.

**Acceptance bullets covered:** none directly. This is the gate for §10.2 test infrastructure.

---

### TOP-1: Headline patterns and text-similarity primitives (pure)

**Files:**
- Create or modify `pkg/domain/headlines.py` and `pkg/domain/diversity.py` (both TOP-owned, created here).
- Create `backend/tests/topics/test_top_headlines.py` and `backend/tests/topics/test_top_diversity_text.py`.

**Interfaces.**
- Consumes `domain.text.strip_citation_markers`, `domain.text.normalize_for_match`, `domain.text.WORD_RE` and `domain.enums.HeadlinePattern`.
- Produces:
```python
# pkg/domain/diversity.py
STOPWORDS: frozenset[str]
def normalize_words(text: str) -> str
def tokenize_words(text: str) -> list[str]
def char_trigrams(text: str) -> frozenset[str]
def trigram_jaccard(a: str, b: str) -> float
def extract_keywords(text: str, *, limit: int) -> list[str]
def count_repeated_phrases(texts: Sequence[str], *, min_words: int, max_words: int, min_count: int, limit: int = 20) -> list[tuple[str, int]]
def opening_sentence(text: str, *, max_chars: int = 500) -> str
def domain_shares(domains: Sequence[str], *, limit: int = 20) -> list[tuple[str, int, float]]

# pkg/domain/headlines.py
IMPERATIVE_VERBS: frozenset[str]
def classify_headline(title: str) -> HeadlinePattern
```

**Behaviour rules.**
1. `STOPWORDS` is exactly: `a an the and or but if of to in on at by for with from as is are was were be been being it its this that these those we our you your they their he she his her i not no can will would should could may might must do does did has have had than then so such into about over more most also just only how what why when where which who`.
2. `normalize_words(text)` does these steps in order:
   1. `strip_citation_markers`;
   2. `normalize_for_match` (NFKC, curly quotes straightened, lowercase, whitespace collapsed);
   3. delete every `'`;
   4. replace each run of characters outside `[a-z0-9]` with one space;
   5. `strip()`.
   Example: `"The Agentic Shift: What’s NEXT? [S1]"` → `"the agentic shift whats next"`.
3. `tokenize_words(text)` returns `WORD_RE.findall(strip_citation_markers(text).lower())`.
4. `char_trigrams(text)` works on `s = normalize_words(text)`:
   - `len(s) >= 3` → `frozenset(s[i:i+3] for i in range(len(s) - 2))`;
   - `1 <= len(s) < 3` → `frozenset({s})`;
   - empty → `frozenset()`.
5. `trigram_jaccard(a, b)` returns `|A∩B| / |A∪B|` over the two trigram sets, or `0.0` when the union is empty.
6. `extract_keywords(text, *, limit)`:
   - Tokens come from `tokenize_words`.
   - Drop tokens in `STOPWORDS`, tokens shorter than 4 characters and tokens made only of digits.
   - Count occurrences, then sort by count descending, then by index of first appearance ascending.
   - Return the first `limit`. `limit <= 0` returns `[]`.
7. `count_repeated_phrases(texts, *, min_words, max_words, min_count, limit)`:
   1. Split each text into segments with `re.split(r"[.!?;:\n]+", strip_citation_markers(text))`.
   2. Tokenize each segment with `tokenize_words`.
   3. For each `n` in `min_words..max_words`, collect every contiguous n-gram inside one segment whose first and last words are not in `STOPWORDS`, joined with single spaces.
   4. Count each phrase **once per text** (document frequency).
   5. Keep phrases with frequency `>= min_count`.
   6. Remove any kept phrase that is a contiguous word sub-sequence of another kept phrase with the **same** count.
   7. Sort by count descending, then word count descending, then phrase ascending, and return the first `limit` pairs.
8. `opening_sentence(text, *, max_chars)`:
   - Take `strip_citation_markers(text)` with whitespace collapsed to single spaces and stripped.
   - Return the text up to and including the first `.`, `!` or `?` that is followed by whitespace or the end of the text.
   - If there is no such character, use the whole text.
   - Truncate to `max_chars` characters.
9. `domain_shares(domains, *, limit)`:
   - Count each domain.
   - `share = round(count / len(domains), 4)`.
   - Sort by count descending, then domain ascending, and return the first `limit` triples.
   - An empty input returns `[]`.
10. `IMPERATIVE_VERBS` is exactly: `stop start build rethink rebuild make let give put treat measure design keep use ask meet consider forget imagine fix choose prepare plan dont avoid embrace bring move trust teach train`.
11. `classify_headline(title)` works on `t = title.strip()` and `low = t.lower()`. The first matching rule wins:
    1. `what_if`: `low` starts with `"what if "`.
    2. `how_to`: `re.match(r"how\b", low)`.
    3. `why`: `re.match(r"why\b", low)`.
    4. `number_list`: `re.match(r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+\S", low)`.
    5. `versus`: `re.search(r"\bvs\b\.?|\bversus\b", low)`.
    6. `question`: `t.endswith("?")`.
    7. `colon_split`: `":" in t`.
    8. `imperative`: the first word of `normalize_words(t)` is in `IMPERATIVE_VERBS`.
    9. Otherwise `statement`, including the empty string.
12. The module imports only the standard library and `mdcopilot_blog.domain.*`.

**Tests to write FIRST.**

`backend/tests/topics/test_top_headlines.py`
- `test_top_classify_headline_table` is parametrized with `(title, expected)`:

  | Title | Expected |
  |---|---|
  | `"What if specialists had a digital twin?"` | `what_if` |
  | `"How to cut prior authorisation delays"` | `how_to` |
  | `"How ambient scribes change clinic flow"` | `how_to` |
  | `"Why specialist wait times keep growing"` | `why` |
  | `"   why   now"` | `why` |
  | `"5 lessons from the FDA device list"` | `number_list` |
  | `"Three ways agents reduce inbox load"` | `number_list` |
  | `"10x better triage"` | `statement` |
  | `"Copilots vs agents in specialist care"` | `versus` |
  | `"Human oversight versus full autonomy"` | `versus` |
  | `"Can generic LLMs reason like a cardiologist?"` | `question` |
  | `"Why AI vs humans?"` | `why` |
  | `"The agentic shift: what changes for clinics"` | `colon_split` |
  | `"Stop treating AI scribes as a cure for burnout"` | `imperative` |
  | `"Don’t automate the physician away"` | `imperative` |
  | `"Specialist scarcity is a routing problem"` | `statement` |
  | `""` | `statement` |

  Assert `classify_headline(title) == HeadlinePattern(expected)`.

`backend/tests/topics/test_top_diversity_text.py`
- `test_top_normalize_words`
  - `normalize_words("The Agentic Shift: What’s NEXT? [S1]") == "the agentic shift whats next"`;
  - `normalize_words("  A--B  ") == "a b"`;
  - `normalize_words("") == ""`.
- `test_top_tokenize_words`: `tokenize_words("Clinics [S1] can't wait—really.") == ["clinics", "can't", "wait", "really"]`.
- `test_top_char_trigrams`: `char_trigrams("abcd") == frozenset({"abc", "bcd"})`, `char_trigrams("ab") == frozenset({"ab"})` and `char_trigrams("!!") == frozenset()`.
- `test_top_trigram_jaccard`
  - `trigram_jaccard("abcde", "abcdf") == 0.5`;
  - `trigram_jaccard("ABC-DE", "abc de") == 1.0`;
  - `trigram_jaccard("", "") == 0.0`;
  - `trigram_jaccard("abc", "xyz") == 0.0`.
- `test_top_extract_keywords`
  - `extract_keywords("Prior authorisation delays. Prior authorisation burden hits specialists; authorisation again 2026", limit=3) == ["authorisation", "prior", "delays"]`;
  - `limit=0` returns `[]`.
- `test_top_count_repeated_phrases_counts_documents`
  - Texts:
    - `"Prior authorisation delays hurt patients. Specialist wait times grow."`
    - `"Prior authorisation delays slow care. Specialist wait times grow again."`
    - `"New data on prior authorisation delays and specialist wait times."`
  - With `min_words=3, max_words=5, min_count=3`, the result is `[("prior authorisation delays", 3), ("specialist wait times", 3)]`.
- `test_top_count_repeated_phrases_suppresses_subphrases`
  - Three texts, each `"Clinical decision support tools."`.
  - With `min_words=3, max_words=4, min_count=3`, the result is `[("clinical decision support tools", 3)]`.
  - Its 3-word sub-phrases `"clinical decision support"` and `"decision support tools"` have the same count (3), so they are removed.
- `test_top_count_repeated_phrases_skips_stopword_edges_and_low_counts`
  - Three texts, each `"of the clinic today"`, with `min_words=3, max_words=3, min_count=3` → `[]`.
  - Two texts `"prior authorisation delays"` with `min_count=3` → `[]`.
- `test_top_count_repeated_phrases_does_not_cross_sentences`: three texts `"care delays. prior visits"` with `min_words=3, max_words=3, min_count=1` → `[]`.
- `test_top_opening_sentence`
  - `opening_sentence("AI scribes cut notes by half [S1]. Clinics noticed.") == "AI scribes cut notes by half."`;
  - `opening_sentence("Is this real? Yes.") == "Is this real?"`;
  - `opening_sentence("No terminal punctuation here") == "No terminal punctuation here"`;
  - `opening_sentence("x" * 600) == "x" * 500`;
  - `opening_sentence("Version 2.5 ships today. More") == "Version 2.5 ships today."`.
- `test_top_domain_shares`: `domain_shares(["b.org", "a.org", "b.org", "c.org"]) == [("b.org", 2, 0.5), ("a.org", 1, 0.25), ("c.org", 1, 0.25)]` and `domain_shares([]) == []`.

**Implementation notes.** Pure code; no snippets needed.

**Verification.**
1. Red: run the two files before the modules exist. Expect `ImportError` collection errors or `AttributeError`.
2. Implement.
3. Green:
```bash
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_headlines.py tests/topics/test_top_diversity_text.py
```
Expected: 0 failed, 0 errors. Then run TOP-LINT and expect a clean exit, with `Success: no issues found` from mypy.

**Acceptance bullets covered:** §10.2 "Embeddings + novelty engine" (headline repetition primitives); §10.4 "diversity checks" (TOP's primitives).

---
### TOP-2: Topic scoring (pure)

**Files:**
- Create or modify `pkg/domain/scoring.py`.
- Create `backend/tests/topics/test_top_scoring.py`.

**Interfaces.**
- Consumes `domain.config.ScoreWeights` and `domain.contracts.ScoreItem`.
- Produces:
```python
SCORE_KEYS: tuple[str, ...] = ("timeliness", "novelty", "evidence", "mdcopilotRelevance", "audience", "editorial")
MANUAL_RUBRIC_JUSTIFICATION = "manual topic: no rubric"

@dataclass(frozen=True)
class RubricItem:
    score: int            # 1..5
    justification: str

@dataclass(frozen=True)
class ScoreInputs:
    newest_published_at: datetime | None
    dated_sources: int
    total_sources: int
    tier12_sources: int
    primary_source_present: bool
    novelty_score: float
    novelty_justification: str
    business_relevance: RubricItem | None
    audience_relevance: RubricItem | None
    editorial_potential: RubricItem | None

@dataclass(frozen=True)
class ScoreCard:
    timeliness: float
    novelty: float
    evidence: float
    business_relevance: float
    audience_relevance: float
    editorial_potential: float
    total: float
    breakdown: dict[str, ScoreItem]    # keys = SCORE_KEYS

def timeliness_score(newest_published_at: datetime | None, *, now: datetime) -> float
def timeliness_justification(newest_published_at: datetime | None, *, now: datetime) -> str
def evidence_score(*, dated_sources: int, total_sources: int, tier12_sources: int, primary_source_present: bool, min_source_count: int) -> float
def evidence_justification(*, dated_sources: int, total_sources: int, tier12_sources: int, primary_source_present: bool) -> str
def rubric_to_unit(score: int) -> float
def score_candidate(inputs: ScoreInputs, *, weights: ScoreWeights, min_source_count: int, now: datetime) -> ScoreCard
```

**Behaviour rules.**
1. **Timeliness** uses `age = now − newest_published_at`:
   - `age <= 48 h` → `1.0` (this includes future dates);
   - `age <= 7 days` → `0.7`;
   - `age <= 30 days` → `0.3`;
   - otherwise, or when `newest_published_at is None` → `0.1`.
2. `timeliness_justification`:
   - no date → `"no dated source"`;
   - otherwise `f"newest source {h} hours old"` with `h = max(0, floor(age.total_seconds() / 3600))`.
3. **Evidence** is `0.4·(min(dated_sources, min_source_count) / min_source_count) + 0.4·(tier12_sources / total_sources if total_sources > 0 else 0.0) + 0.2·(1.0 if primary_source_present else 0.0)`. `min_source_count < 1` raises `ValueError`.
4. `evidence_justification` returns `f"{dated_sources} dated sources, {pct}% tier 1-2, primary source {'present' if primary_source_present else 'missing'}"`, where `pct = round(100 * tier12_sources / total_sources)` when `total_sources > 0`, else `0`.
5. **Rubric:** `rubric_to_unit(s) = (s − 1) / 4`. `s` outside `1..5` raises `ValueError`.
6. **Score card:**
   - A `None` rubric item scores `0.5` with justification `MANUAL_RUBRIC_JUSTIFICATION`.
   - Every component score is `round(x, 6)`.
   - `total = round(Σ weight·score, 6)` over the rounded component scores.
   - Breakdown entries are `ScoreItem(weight=<weight>, score=<score>, justification=<text>)` with key → weight field:
     - `timeliness` → `weights.timeliness`;
     - `novelty` → `weights.novelty`;
     - `evidence` → `weights.evidence`;
     - `mdcopilotRelevance` → `weights.mdcopilot_relevance`;
     - `audience` → `weights.audience`;
     - `editorial` → `weights.editorial`.
   - Rubric justifications are the agent's text verbatim. The novelty justification is `inputs.novelty_justification`.
7. `novelty` in the card is `round(inputs.novelty_score, 6)`. Its value is not recomputed here.

**Tests to write FIRST** (`backend/tests/topics/test_top_scoring.py`; `NOW = datetime(2026, 9, 17, 1, 30, tzinfo=UTC)`).
- `test_top_timeliness_boundaries`, parametrized `(delta, expected)`:

  | Delta | Expected |
  |---|---|
  | `-1 h` (future) | `1.0` |
  | `48 h` | `1.0` |
  | `48 h + 1 s` | `0.7` |
  | `7 d` | `0.7` |
  | `7 d + 1 s` | `0.3` |
  | `30 d` | `0.3` |
  | `30 d + 1 s` | `0.1` |

  Assert `timeliness_score(NOW - delta, now=NOW) == expected`. Also assert `timeliness_score(None, now=NOW) == 0.1`.
- `test_top_timeliness_justification`: `timeliness_justification(NOW - timedelta(hours=30, minutes=59), now=NOW) == "newest source 30 hours old"` and `timeliness_justification(None, now=NOW) == "no dated source"`.
- `test_top_evidence_score_formula`, parametrized with `min_source_count=5`:

  | dated, total, tier12, primary | Expected |
  |---|---|
  | `(5, 5, 3, True)` | `pytest.approx(0.84)` |
  | `(0, 0, 0, False)` | `0.0` |
  | `(10, 10, 10, True)` | `pytest.approx(1.0)` |
  | `(2, 2, 1, False)` | `pytest.approx(0.36)` |

  Also assert that `min_source_count=0` raises `ValueError`.
- `test_top_evidence_justification`: `(5, 5, 3, True)` → `"5 dated sources, 60% tier 1-2, primary source present"`; `(0, 0, 0, False)` → `"0 dated sources, 0% tier 1-2, primary source missing"`.
- `test_top_rubric_to_unit`: 1→0.0, 2→0.25, 3→0.5, 4→0.75, 5→1.0; 0 and 6 raise `ValueError`.
- `test_top_score_candidate_matches_hand_computed_default_weights`
  - Inputs:
    - `newest_published_at = NOW - 30 h`;
    - `(dated=5, total=5, tier12=3, primary=True)`;
    - `novelty_score = 0.9`, `novelty_justification = "PASS: no similar history"`;
    - rubric business `RubricItem(4, "Directly about referral routing")`, audience `RubricItem(3, "Relevant to CMIOs")`, editorial `RubricItem(5, "Strong contrarian angle")`;
    - `weights = ScoreWeights()` (0.25, 0.20, 0.20, 0.15, 0.10, 0.10), `min_source_count = 5`.
  - Assert:
    - `card.timeliness == 1.0`, `card.novelty == 0.9`, `card.evidence == 0.84`;
    - `card.business_relevance == 0.75`, `card.audience_relevance == 0.5`, `card.editorial_potential == 1.0`;
    - `card.total == 0.8605`;
    - `list(card.breakdown) == list(SCORE_KEYS)`;
    - `card.breakdown["mdcopilotRelevance"] == ScoreItem(weight=0.15, score=0.75, justification="Directly about referral routing")`;
    - `card.breakdown["timeliness"].justification == "newest source 30 hours old"`;
    - `card.breakdown["evidence"].justification == "5 dated sources, 60% tier 1-2, primary source present"`;
    - `card.breakdown["novelty"].justification == "PASS: no similar history"`.
- `test_top_score_candidate_matches_hand_computed_custom_weights`
  - Inputs:
    - weights `ScoreWeights(timeliness=0.4, novelty=0.1, evidence=0.1, mdcopilot_relevance=0.2, audience=0.1, editorial=0.1)`;
    - `newest = NOW - 5 d`, `(dated=2, total=2, tier12=1, primary=False)`, `novelty_score = 0.7`;
    - rubric 2, 5 and 1.
  - Assert the component scores `0.7, 0.7, 0.36, 0.25, 1.0, 0.0` and `card.total == 0.536`.
- `test_top_score_candidate_manual_rubric`
  - All three rubric items `None`, `(0, 0, 0, False)`, `novelty_score = 1.0`, no date, default weights.
  - Assert:
    - the three rubric scores are `0.5` with justification `"manual topic: no rubric"`;
    - `card.total == round(0.25*0.1 + 0.2*1.0 + 0.2*0.0 + 0.15*0.5 + 0.1*0.5 + 0.1*0.5, 6) == 0.4`.

**Implementation notes.** Pure; no snippets.

**Verification.**
1. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_scoring.py` fails with ImportError.
2. Implement.
3. Green: 0 failed. Then TOP-LINT clean.

**Acceptance bullets covered:** §10.2 "Scoring with configurable weights and stored breakdown" (formula part); §10.2 "Weighted totals match a hand-computed fixture".

---

### TOP-3: Novelty decision rules (pure)

**Files:**
- Create or modify `pkg/domain/novelty.py`.
- Create `backend/tests/topics/test_top_novelty_rules.py`.

**Interfaces.**
- Consumes `domain.config.NoveltyConfig`, `domain.contracts.NoveltyDecision`, `domain.contracts.NoveltyNeighbour`, `domain.enums.CandidateStatus` and `domain.enums.HeadlinePattern`.
- Produces:
```python
NON_LIVE_ARTICLE_STATUSES: frozenset[str] = frozenset({"REJECTED", "SUPERSEDED"})
APPROVED_OR_LATER_STATUSES: frozenset[str] = frozenset({"APPROVED", "SCHEDULED", "EXPORTED", "PUBLISHING", "PUBLISHED", "PUBLISH_FAILED"})
NEIGHBOUR_LIMIT = 5

def clamp_unit(value: float) -> float
def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float
def candidate_embedding_text(*, title: str, hook: str, thesis: str, angle: str) -> str
def external_post_embedding_text(*, title: str, excerpt: str) -> str

@dataclass(frozen=True)
class NoveltySignals:
    topic_best: NoveltyNeighbour | None       # highest topic-space neighbour
    argument_best: NoveltyNeighbour | None    # highest argument-space neighbour
    news_reuse_url: str | None
    headline_best: tuple[float, str] | None   # (trigram Jaccard, other headline)
    pattern: HeadlinePattern
    pattern_uses: int                         # stored uses in the window + 1 (the candidate)
    reused_examples: tuple[str, ...]

@dataclass(frozen=True)
class NoveltyAssessment:
    decision: NoveltyDecision
    reasons: tuple[str, ...]
    max_similarity: float

def assess_novelty(signals: NoveltySignals, config: NoveltyConfig) -> NoveltyAssessment
def novelty_justification(assessment: NoveltyAssessment) -> str
def novelty_score(max_similarity: float) -> float
def candidate_status(decision: NoveltyDecision, *, is_manual: bool) -> CandidateStatus
def round_shortfall(*, statuses: Sequence[str], round_no: int, max_regeneration_rounds: int) -> bool
```

**Behaviour rules.**
1. `clamp_unit(x) = min(1.0, max(0.0, x))`.
2. `cosine_similarity(a, b)`:
   - `len(a) != len(b)` raises `ValueError("vector lengths differ: <len a> != <len b>")`;
   - a zero norm on either side returns `0.0`;
   - otherwise `dot / (|a|·|b|)`, not clamped.
3. `candidate_embedding_text` is `"\n".join(p.strip() for p in (title, hook, thesis, angle) if p.strip())`. `external_post_embedding_text` does the same over `(title, excerpt)`.
4. `assess_novelty`:
   - Let `t = signals.topic_best.similarity` (0.0 if None), `g = signals.argument_best.similarity` (0.0 if None), `T = config.topic_threshold`, `A = config.argument_threshold` and `m = config.warn_margin`.
   - Every warn boundary is rounded before comparing: `T − m` means `round(T - m, 6)` and `A − m` means `round(A - m, 6)`. In float arithmetic `0.88 - 0.05 == 0.8300000000000001`, which would wrongly let 0.83 pass.
   - Reasons are collected in this fixed order (numbers use `:.2f`):
     1. `t >= T` → `f"topic similarity {t:.2f} >= {T:.2f} ({kind} {ref_id})"` (REJECT). Otherwise `t >= T − m` → `f"topic similarity {t:.2f} within {m:.2f} of {T:.2f} ({kind} {ref_id})"` (WARN).
     2. `g >= A` → `f"argument similarity {g:.2f} >= {A:.2f} ({kind} {ref_id})"` (REJECT). Otherwise `g >= A − m` → `f"argument similarity {g:.2f} within {m:.2f} of {A:.2f} ({kind} {ref_id})"` (WARN).
     3. `news_reuse_url is not None` → `f"primary news source reused within {config.news_reuse_days} days ({url})"` (REJECT).
     4. `headline_best` with Jaccard `j >= config.headline_similarity_warn` → `f'headline similarity {j:.2f} >= {config.headline_similarity_warn:.2f} ("{other}")'` (WARN).
     5. `pattern != STATEMENT and pattern_uses >= config.headline_pattern_warn_count` → `f"headline pattern {pattern.value} used {pattern_uses} times in {config.headline_pattern_window_days} days"` (WARN).
     6. `reused_examples` non-empty → `f"examples reused within {config.example_reuse_days} days: {', '.join(reused_examples)}"` (WARN).
   - `decision` is `REJECT_TOPIC` if any REJECT reason fired, else `WARN` if any reason fired, else `PASS`.
   - `max_similarity = round(clamp_unit(max(t, g)), 6)`.
5. `novelty_justification` returns `f"{decision.value}: {'; '.join(reasons)}"`, or `"PASS: no similar history"` when there are no reasons.
6. `novelty_score(x) = round(clamp_unit(1.0 − x), 6)`.
7. `candidate_status`: `PASS` → `PASSED`, `WARN` → `WARNED`, `REJECT_TOPIC` → `REJECTED`. When `is_manual`, `REJECT_TOPIC` → `WARNED` (§5.6: never REJECTED).
8. `round_shortfall` is true iff `round_no >= 1 + max_regeneration_rounds` and fewer than 3 of `statuses` are not `"REJECTED"`.

**Tests to write FIRST** (`backend/tests/topics/test_top_novelty_rules.py`).
- Config and helper:
  - `CFG = NoveltyConfig(topic_threshold=0.85)`, keeping the §5.4 defaults for the other fields. If FOUND made more fields required, pass their §5.4 defaults explicitly.
  - Helper `nb(kind, sim) = NoveltyNeighbour(kind=kind, ref_id="r1", title="Old", similarity=sim)`.
  - Base signals `S0`: everything None or empty, `pattern=STATEMENT`, `pattern_uses=1`.
- `test_top_clamp_and_cosine`
  - `clamp_unit(-0.2) == 0.0`, `clamp_unit(1.0000001) == 1.0`;
  - `cosine_similarity([1, 0], [0, 1]) == 0.0`, `cosine_similarity([2, 0], [1, 0]) == 1.0`, `cosine_similarity([0, 0], [1, 0]) == 0.0`;
  - `cosine_similarity([1], [1, 0])` raises `ValueError`.
- `test_top_embedding_texts`
  - `candidate_embedding_text(title=" T ", hook="", thesis="Th", angle="A") == "T\nTh\nA"`;
  - `external_post_embedding_text(title="P", excerpt="") == "P"`.
- `test_top_assess_empty_history_passes`: `assess_novelty(S0, CFG) == NoveltyAssessment(PASS, (), 0.0)` and `novelty_justification(...) == "PASS: no similar history"`.
- `test_top_assess_topic_thresholds`, parametrized `(sim, decision, reason)`:
  - `(0.85, REJECT_TOPIC, "topic similarity 0.85 >= 0.85 (external_post r1)")`;
  - `(0.84, WARN, "topic similarity 0.84 within 0.05 of 0.85 (external_post r1)")`;
  - `(0.80, WARN, "topic similarity 0.80 within 0.05 of 0.85 (external_post r1)")`;
  - `(0.79, PASS, None)`.
  - Signals are `S0` with `topic_best=nb("external_post", sim)`.
  - Assert the decision, and `reasons == (reason,)` or `()`.
- `test_top_assess_argument_thresholds`, parametrized:
  - `(0.88, REJECT_TOPIC, "argument similarity 0.88 >= 0.88 (topic r1)")`;
  - `(0.83, WARN, "argument similarity 0.83 within 0.05 of 0.88 (topic r1)")`;
  - `(0.8299, PASS, None)`.
- `test_top_assess_news_reuse_rejects`: `news_reuse_url="https://ex.org/a"` → `REJECT_TOPIC` with reasons `("primary news source reused within 30 days (https://ex.org/a)",)`.
- `test_top_assess_headline_similarity`: `(0.6, "Old headline")` → WARN, reason `'headline similarity 0.60 >= 0.60 ("Old headline")'`; `(0.59, "x")` → PASS.
- `test_top_assess_headline_pattern`
  - `(HOW_TO, 3)` → WARN, reason `"headline pattern how_to used 3 times in 14 days"`;
  - `(HOW_TO, 2)` → PASS;
  - `(STATEMENT, 10)` → PASS.
- `test_top_assess_examples_reused`: `("Epic", "CMS rule")` → WARN, reason `"examples reused within 30 days: Epic, CMS rule"`.
- `test_top_assess_reason_order_and_max_similarity`
  - Signals: `topic_best=nb("topic", 0.82)`, `argument_best=nb("article", 0.9)`, `news_reuse_url="u"`, `reused_examples=("X",)`.
  - Assert:
    - decision `REJECT_TOPIC`;
    - `reasons[0].startswith("topic similarity 0.82 within")`, `reasons[1].startswith("argument similarity 0.90 >=")`, `reasons[2].startswith("primary news source")`, `reasons[3].startswith("examples reused")`;
    - `max_similarity == 0.9`;
    - `novelty_justification(a) == "REJECT_TOPIC: " + "; ".join(a.reasons)`.
- `test_top_novelty_score`: `novelty_score(0.3) == 0.7`, `novelty_score(1.2) == 0.0`.
- `test_top_candidate_status`: the three mappings; `candidate_status(REJECT_TOPIC, is_manual=True) == WARNED`; `candidate_status(PASS, is_manual=True) == PASSED`.
- `test_top_round_shortfall`, parametrized `(statuses, round_no, expected)` with `max_regeneration_rounds=2`:
  - `(["PASSED", "REJECTED", "REJECTED"], 3, True)`;
  - `(["PASSED", "WARNED", "PASSED"], 3, False)`;
  - `(["PASSED", "REJECTED", "REJECTED"], 2, False)`;
  - `(["DISMISSED", "SELECTED", "REJECTED"], 3, True)`;
  - `(["PASSED", "REJECTED", "REJECTED"], 4, True)`.
- `test_top_status_sets`: `APPROVED_OR_LATER_STATUSES == {"APPROVED", "SCHEDULED", "EXPORTED", "PUBLISHING", "PUBLISHED", "PUBLISH_FAILED"}` and `NON_LIVE_ARTICLE_STATUSES == {"REJECTED", "SUPERSEDED"}`.

**Implementation notes.** Pure; `domain/novelty.py` imports only the standard library and `mdcopilot_blog.domain.*`.

**Verification.**
1. Red, then implement.
2. Green: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_novelty_rules.py` → 0 failed.
3. TOP-LINT clean.

**Acceptance bullets covered:** §10.2 "Embeddings + novelty engine + regeneration loop ≤2 rounds" (decision rules and `round_shortfall`); §10.2 "Always exactly 3 candidates or flagged shortfall after 2 rounds" (shortfall rule).

---
### TOP-4: Topic Strategist agent, prompt and mock fixture

**Files:**
- Create or modify `pkg/agents/topic_strategist.py`.
- Create `backend/prompts/ideation/topics.v1.md` (draft as `topics.v1.md.wip`, then rename).
- Create `backend/fixtures/mock/llm/ideation/ideation_topics.json`.
- Create `backend/tests/topics/test_top_strategist.py`.

**Interfaces.**
- Consumes:
  - `llm.gateway`: `AgentSpec`, `CallContext`, `AgentResult`, `LLMGateway`;
  - `domain.contracts`: `Contract`, `Marker`, `PillarKey`;
  - `domain.config.BrandProfileValues`;
  - `domain.errors`: `OutputRejected`, `UnknownCitationMarker`;
  - `agents.common`: `UNTRUSTED_NOTICE`, `NumberedSource`, `render_source_list`, `resolve_markers`;
  - `domain.diversity.normalize_words`.
- Produces:
```python
class RubricScore(Contract):
    score: Annotated[int, Field(ge=1, le=5)]
    justification: Annotated[str, Field(min_length=1, max_length=600)]

class TopicIdea(Contract):
    title: Annotated[str, Field(min_length=1, max_length=300)]
    hook: Annotated[str, Field(min_length=1, max_length=1000)]
    why_now: Annotated[str, Field(min_length=1, max_length=1000)]
    thesis: Annotated[str, Field(min_length=1, max_length=1000)]
    angle: Annotated[str, Field(min_length=1, max_length=1000)]
    core_argument: Annotated[str, Field(min_length=1, max_length=600)]
    mdcopilot_connection: Annotated[str, Field(min_length=1, max_length=1000)]
    target_audience: Annotated[str, Field(min_length=1, max_length=300)]
    pillar: PillarKey
    source_markers: Annotated[list[Marker], Field(min_length=1, max_length=8)]
    primary_marker: Marker
    examples: Annotated[list[Annotated[str, Field(min_length=1, max_length=200)]], Field(max_length=8)]
    business_relevance: RubricScore
    audience_relevance: RubricScore
    editorial_potential: RubricScore

class TopicIdeas(Contract):
    ideas: Annotated[list[TopicIdea], Field(min_length=3, max_length=3)]

TOPIC_STRATEGIST_SPEC: AgentSpec[TopicIdeas] = AgentSpec(
    name=AgentName.IDEATION, version="1", prompt_name="ideation/topics", output_type=TopicIdeas,
    max_output_tokens=5000, output_retries=1, timeout_seconds=120.0, reasoning="low")

@dataclass(frozen=True)
class PillarBrief:
    key: str
    name: str
    description: str
    topics: tuple[str, ...]

@dataclass(frozen=True)
class FindingBrief:
    claim: str
    claim_type: str
    importance: str
    confidence: float
    markers: tuple[str, ...]

@dataclass(frozen=True)
class AvoidTopic:
    title: str
    thesis: str

def render_brand_voice(brand: BrandProfileValues) -> str
def build_variables(*, brand: BrandProfileValues, target_pillar: PillarBrief, pillars: Sequence[PillarBrief],
                    pillar_counts: Mapping[str, int], theme_counts: Mapping[str, int], avoid: Sequence[AvoidTopic]) -> dict[str, str]
def build_user_prompt(*, round_no: int, target_pillar: PillarBrief, findings: Sequence[FindingBrief],
                      numbered: Sequence[NumberedSource]) -> str
def check_ideas(ideas: TopicIdeas, *, numbered: Sequence[NumberedSource], avoid: Sequence[AvoidTopic]) -> None
async def run_topic_strategist(gateway: LLMGateway, *, ctx: CallContext, variables: Mapping[str, str], user_prompt: str,
                               numbered: Sequence[NumberedSource], avoid: Sequence[AvoidTopic],
                               route_override: Sequence[str] | None, prompt_version: int | None) -> AgentResult[TopicIdeas]
```

**Behaviour rules.**
1. The module never imports `pydantic_ai` or `mdcopilot_blog.db` (§11 rule 10).
2. `render_brand_voice(brand)` returns exactly these five lines joined with `"\n"`:
   - `f"Tone: {', '.join(brand.tone)}"`
   - `f"Narrative: {brand.narrative}"`
   - `f"Emphasis: {', '.join(brand.emphasis)}"`
   - `f"Avoid: {', '.join(brand.avoid)}"`
   - `f"Prohibited language: {'; '.join(brand.prohibited_language)}"`
3. `build_variables` returns exactly the keys `untrusted_notice, brand_name, brand_voice, brand_mission, target_audience, target_pillar, pillar_catalogue, coverage_counts, avoid_list`:
   - `untrusted_notice = UNTRUSTED_NOTICE`
   - `brand_name = brand.name`
   - `brand_voice = render_brand_voice(brand)`
   - `brand_mission = brand.mission`
   - `target_audience = brand.target_audience`
   - `target_pillar = f"{p.key} — {p.name}: {p.description}\nTopics: {', '.join(p.topics)}"`
   - `pillar_catalogue` is one line `f"- {p.key} — {p.name}: {p.description}"` per pillar, in the given order.
   - `coverage_counts` is two lines:
     - `"Pillars (last 30 days): " + ", ".join(f"{p.key}={pillar_counts.get(p.key, 0)}" for p in pillars)`
     - `"Themes (last 30 days): " + (", ".join(f"{k}={v}" for k, v in theme_counts.items()) or "none")`
   - `avoid_list` is one line `f"- {a.title} — {a.thesis}"` per avoid item, or `"(none)"` when there are none.
4. `build_user_prompt` returns, joined with `"\n"`:
   - `f"Round: {round_no}"`
   - `f"Target pillar: {target_pillar.key} — {target_pillar.name}"`
   - `""`
   - `"Findings:"`
   - one line per finding `f"F{i} [{f.claim_type}, {f.importance}, confidence {f.confidence:.2f}] {f.claim} — sources: {', '.join(f.markers)}"` (1-based `i`), or the single line `"(none)"`
   - `""`
   - `"Sources:"`
   - `render_source_list(numbered, include_text=False)`
   - and it ends with one trailing `"\n"`.
   The first line followed by a newline (`"Round: 2\n"`) is what the mock fixture cases match.
5. `check_ideas` raises `OutputRejected` on the first failing rule:
   1. Collect markers in first-appearance order: for each idea, its `source_markers`, then its `primary_marker`. Call `resolve_markers(collected, numbered)`. On `UnknownCitationMarker` raise `OutputRejected(f"unknown markers: {', '.join(exc.args[0])}")`.
   2. Idea `i` (1-based) whose `primary_marker` is not in its `source_markers` → `OutputRejected(f"primary marker {m} is not among source markers of idea {i}")`.
   3. Two ideas with equal `normalize_words(title)` → `OutputRejected(f"duplicate idea title: {title}")`, naming the later idea's title.
   4. An idea whose `normalize_words(title)` equals `normalize_words(a.title)`, or whose `normalize_words(thesis)` equals `normalize_words(a.thesis)`, for any `a` in `avoid` → `OutputRejected(f"idea repeats an avoided topic: {title}")`.
6. `run_topic_strategist` calls `gateway.run(TOPIC_STRATEGIST_SPEC, variables=variables, user_prompt=user_prompt, ctx=ctx, route_override=route_override, prompt_version=prompt_version, output_check=<closure calling check_ideas(output, numbered=numbered, avoid=avoid)>)` and returns its result unchanged.
7. **Prompt** `backend/prompts/ideation/topics.v1.md`:
   - Front matter: `name: ideation/topics`, `version: 1`, `agent: ideation`, `output: TopicIdeas`, `variables:` in the order of rule 3.
   - Body uses every variable once, with `{{ untrusted_notice }}` as its own paragraph, and states each of these:
     1. You are the Topic Strategist for `{{ brand_name }}`; the audience is `{{ target_audience }}`; the mission is `{{ brand_mission }}`; the voice is `{{ brand_voice }}`.
     2. Propose **exactly three** distinct ideas with different angles.
     3. Cite evidence only with the source markers shown in the user message (`S1`, `S2`, …) in `sourceMarkers`. `primaryMarker` must be one of them. Never write URLs or ids.
     4. `whyNow` must name a dated finding or source.
     5. Never invent statistics, quotes, anecdotes or physician experiences.
     6. At least one idea uses the target pillar `{{ target_pillar }}`; the pillar list is `{{ pillar_catalogue }}`.
     7. Prefer under-covered pillars and themes: `{{ coverage_counts }}`.
     8. Do not repeat or closely paraphrase any avoided topic: `{{ avoid_list }}`.
     9. `examples` lists the named companies, studies, regulations and products the idea relies on (an empty list is allowed).
     10. Score `businessRelevance` (connection to MDCopilot's product and mission), `audienceRelevance` (importance to specialist physicians and clinical leaders) and `editorialPotential` (originality and argument strength), each 1–5 with a one-sentence justification.
   - Once written, the file is never edited (§11 rule 15).
8. **Fixture** `backend/fixtures/mock/llm/ideation/ideation_topics.json` uses the cases form:
   - The file is `{"cases": [c2, c3, c4, c5, c1]}`, with camelCase keys inside every output.
   - `c<n>` for `n` in 2..5 is `{"when": {"promptContains": "Round: <n>\n"}, "output": <set n>, "usage": {"input_tokens": 12000, "output_tokens": 2400}}`.
   - `c1` is `{"output": <set 1>, "usage": {"input_tokens": 12000, "output_tokens": 2400}}`, the default case with no `when`.
   - Sets 1–5 are the "set A"–"set E" named in the tests.
   - Invariants (§5.8 TOP row):
     - every set validates as `TopicIdeas`;
     - all 15 `normalize_words(title)` values are distinct;
     - inside each set, `hook`, `thesis` and `angle` texts are pairwise distinct;
     - every marker is in `S1`–`S6`;
     - `primaryMarker` ∈ `sourceMarkers`;
     - inside each set, `0.15·u(business) + 0.10·u(audience) + 0.10·u(editorial)` (with `u = rubric_to_unit`) differs for all three ideas;
     - no title, hook or thesis contains a phrase from the seeded `prohibited_language`.

**Tests to write FIRST** (`backend/tests/topics/test_top_strategist.py`).
- Helpers:
  - `idea(i, markers=["S1", "S2"], primary="S1")` returns a camelCase dict of a valid `TopicIdea` with title `f"Idea {i}"`.
  - `numbered6` is six `NumberedSource(marker=f"S{n}", source_id=uuid.uuid4(), title=f"Source {n}", publisher="Pub", domain="ex.org", url=f"https://ex.org/{n}", published_at=None, tier=1, access_mode=AccessMode.FULL_TEXT, text="")`.
- `test_top_topic_ideas_requires_exactly_three`
  - `TopicIdeas.model_validate({"ideas": [idea(1), idea(2)]})` raises `ValidationError` whose `errors()[0]["type"] == "too_short"`.
  - Four ideas → `"too_long"`.
  - Three ideas validate.
- `test_top_topic_idea_field_validation`: `sourceMarkers=["X1"]` → `ValidationError`; `sourceMarkers=[]` → `ValidationError`; `businessRelevance.score=6` → `ValidationError`.
- `test_top_spec_constants`: `TOPIC_STRATEGIST_SPEC.name is AgentName.IDEATION`, `.prompt_name == "ideation/topics"`, `.output_type is TopicIdeas`, `.max_output_tokens == 5000`, `.reasoning == "low"`, `.version == "1"`, `.output_retries == 1`, `.timeout_seconds == 120.0`.
- `test_top_render_brand_voice`: brand from `BrandProfileValues.model_validate(load_seed_file("brand_profile.yaml"))`; the first line is `"Tone: authoritative, clinically grounded, intellectually sharp, pragmatic, empathetic, evidence-driven"` and there are 5 lines.
- `test_top_prompt_renders_with_build_variables`
  - `registry = PromptRegistry.from_directory(default_prompt_root(), agents=["ideation"])`.
  - Variables from `build_variables` with the seeded brand, `PillarBrief("A", "Specialist Scarcity & Access", "desc", ("wait times",))`, `pillars=[that]`, `pillar_counts={"A": 2}`, `theme_counts={}` and `avoid=[AvoidTopic("Old", "Old thesis")]`.
  - `rendered = registry.render("ideation/topics", variables)` succeeds.
  - Assert `UNTRUSTED_NOTICE in rendered.text`, `"MDCopilot" in rendered.text`, `"exactly three" in rendered.text.lower()`, `"- Old — Old thesis" in rendered.text` and `"Pillars (last 30 days): A=2" in rendered.text`.
- `test_top_build_variables_empty_lists`: with `avoid=[]` and `theme_counts={}`, `variables["avoid_list"] == "(none)"` and `variables["coverage_counts"].endswith("Themes (last 30 days): none")`.
- `test_top_build_user_prompt_layout`
  - Input: `round_no=2`, findings `[FindingBrief("Claim one", "FACT", "high", 0.9, ("S1", "S3"))]`, `numbered6`.
  - Assert:
    - `prompt.startswith("Round: 2\nTarget pillar: A — Specialist Scarcity & Access\n\nFindings:\n")`;
    - the line `"F1 [FACT, high, confidence 0.90] Claim one — sources: S1, S3"` is present;
    - `render_source_list(numbered6, include_text=False) in prompt`;
    - `prompt.endswith("\n")`.
  - With no findings the line `"(none)"` follows `"Findings:"`.
- `test_top_check_ideas_rules`, one assertion each, on `numbered6`:
  - an idea with marker `S9` → `OutputRejected` with `str(exc) == "unknown markers: S9"`;
  - `primary="S3"` with markers `["S1"]` → `"primary marker S3 is not among source markers of idea 1"`;
  - titles `"Idea 1"` and `"idea 1!"` → `"duplicate idea title: idea 1!"`;
  - avoid `[AvoidTopic("Idea 2", "x")]` → `"idea repeats an avoided topic: Idea 2"`;
  - avoid `[AvoidTopic("Other", "Thesis 3")]` against an idea whose thesis is `"thesis 3"` → rejected;
  - valid ideas → returns `None`.
- `test_top_run_strategist_retries_unknown_marker_then_succeeds` (`sessionmaker_committing`)
  - Responder: call 1 returns three ideas with idea 1 citing `S9`; call 2 returns three valid ideas.
  - `gateway = function_model_gateway(respond, sessionmaker_committing)`.
  - `result = await run_topic_strategist(gateway, ctx=CallContext(trace_id=new_trace_id()), variables=<build_variables(...)>, user_prompt="Round: 1\n", numbered=numbered6, avoid=[], route_override=["google:m1"], prompt_version=None)`.
  - Assert:
    - `len(result.output.ideas) == 3`;
    - the responder was called 2 times;
    - `SELECT count(*) FROM app.blog_llm_calls WHERE agent_name='ideation'` returns 1, with `status == "ok"` and `prompt_name == "ideation/topics"`.
- `test_top_run_strategist_two_ideas_exhausts_route`: the responder always returns two ideas. `pytest.raises(RouteExhausted)` holds, `exc.failures == [("google:m1", "UnexpectedModelBehavior")]`, and the responder was called 2 times (`output_retries=1`).
- `test_top_default_fixture_satisfies_golden_invariants`
  - Load the fixture JSON.
  - Assert:
    - `[c["when"]["promptContains"] for c in cases[:-1]] == ["Round: 2\n", "Round: 3\n", "Round: 4\n", "Round: 5\n"]` and `"when" not in cases[-1]`;
    - every rule-8 invariant holds, as written, over all five outputs, with prohibited phrases from `load_seed_file("brand_profile.yaml")["prohibited_language"]` matched case-insensitively.
- `test_top_mock_gateway_returns_round_specific_ideas` (`sessionmaker_committing`)
  - `gateway = build_gateway(settings, sessionmaker_committing, PromptRegistry.from_directory(default_prompt_root(), agents=["ideation"]))`.
  - Run with `user_prompt=build_user_prompt(round_no=2, target_pillar=..., findings=[], numbered=numbered6)` and `avoid=[]`.
  - Assert the output titles equal the set-B titles in the fixture file.
  - Repeat with `round_no=1` and assert the set-A titles.

**Implementation notes.** FunctionModel responder shape, verified in Phase 1 `llm/mock.py` and in the p1facts `pydantic_ai` notes (use `info.output_tools[0].name`, never a hard-coded tool name):
```python
calls = 0
async def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    nonlocal calls
    calls += 1
    payload = bad_payload if calls == 1 else good_payload
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, copy.deepcopy(payload))],
                         usage=RequestUsage(input_tokens=10, output_tokens=10))
```
`FunctionModel` works while `models.ALLOW_MODEL_REQUESTS` is `False`. The tests may import `pydantic_ai`; `src` modules outside `llm/` may not.

**Verification.**
1. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_strategist.py` fails with ImportError.
2. Write the module and the `.wip` prompt; rename the prompt when complete; write the fixture.
3. Green: 0 failed.
4. Run `tests/foundation/test_found_imports.py` (it parses all prompts): 0 failed.
5. TOP-LINT clean.

**Acceptance bullets covered:** §10.2 "Topic Strategist schema enforces exactly 3"; §5.8 TOP golden-path invariant (fixture); §0.2 marker rule (unknown marker → retry); §10.2 "`POST /topics/generate` → 3 new candidates not repeating the previous round" (avoid-list enforcement in code).

---
### TOP-5: Novelty service (similarity search, candidate signals, gate 6)

**Files:**
- Modify `pkg/services/novelty.py` (FOUND stub).
- Create `backend/tests/topics/test_top_novelty_service.py`.

**Interfaces.**
- Consumes:
  - ORM `Topic`, `ExternalPost`, `Article`, `ArticleVersion`, `VersionEmbedding`, `ArticleSource`, `LedgerSource`;
  - `domain.novelty` (TOP-3), `domain.diversity.trigram_jaccard` and `normalize_words`, `domain.headlines.classify_headline`;
  - `domain.config` `EffectiveConfig` and `NoveltyConfig`; `domain.contracts` `NoveltyNeighbour` and `GateResult`; `domain.enums.GateId`.
- Produces (the first two signatures are frozen by §5.6):
```python
async def nearest_neighbours(db: AsyncSession, *, embedding: Sequence[float], limit: int,
                             exclude_article_id: uuid.UUID | None = None) -> list[NoveltyNeighbour]
async def check_article_duplicate(db: AsyncSession, *, version_id: uuid.UUID, config: EffectiveConfig) -> GateResult

EMBEDDING_DIMENSIONS = 1536
Space = Literal["topic", "argument"]
Kind = Literal["topic", "article", "external_post"]

async def similar_items(db: AsyncSession, *, embedding: Sequence[float], space: Space, kinds: Collection[Kind], limit: int,
                        since: datetime | None, until: datetime | None, exclude_article_id: uuid.UUID | None = None,
                        exclude_candidate_id: uuid.UUID | None = None,
                        exclude_external_slug: str | None = None) -> list[NoveltyNeighbour]
async def candidate_signals(db: AsyncSession, *, embedding: Sequence[float], argument_embedding: Sequence[float], title: str,
                            primary_canonical_url: str | None, examples: Sequence[str],
                            exclude_candidate_id: uuid.UUID | None, config: NoveltyConfig,
                            now: datetime) -> tuple[NoveltySignals, list[NoveltyNeighbour]]
```

**Behaviour rules.**
1. `similar_items`:
   - `len(embedding) != EMBEDDING_DIMENSIONS` raises `ValueError(f"expected {EMBEDDING_DIMENSIONS} dimensions, got {n}")`. `limit < 1` returns `[]`.
   - It runs one query per requested kind, each `ORDER BY distance, id LIMIT limit`, where `distance = <vector column>.cosine_distance(embedding)` (snippet below).
   - **topic kind:** the column is `Topic.embedding` (space `topic`) or `Topic.argument_embedding` (space `argument`). Filters:
     - column not null;
     - `Topic.created_at >= since` when `since` is set, `<= until` when `until` is set;
     - `Topic.candidate_id IS DISTINCT FROM exclude_candidate_id` when `exclude_candidate_id` is set;
     - `Topic.id != (SELECT topic_id FROM blog_articles WHERE id = exclude_article_id)` when `exclude_article_id` is set.
     - `ref_id = str(topic.id)`, `title = topic.title`.
   - **article kind:** join `Article` → `VersionEmbedding` on `version_id = Article.current_version_id` with `kind = "article"` (space `topic`) or `"argument"` (space `argument`), then join `ArticleVersion` on the same id. Filters:
     - `Article.status NOT IN NON_LIVE_ARTICLE_STATUSES`;
     - `Article.created_at` inside `since`/`until`;
     - `Article.id != exclude_article_id`.
     - `ref_id = str(article.id)`, `title = article.title or version.title_options["operational"]`.
   - **external_post kind** (space `topic` only; ignored for `argument`). Filters: `ExternalPost.embedding` not null; `ExternalPost.slug != exclude_external_slug` when set. **No time filter.**
     - `ref_id = str(post.id)`, `title = post.title`.
   - `similarity = round(clamp_unit(1.0 − distance), 6)`.
   - Merge the per-kind results, sort by similarity descending, then kind ascending, then `ref_id` ascending, and return the first `limit` as `NoveltyNeighbour(kind, ref_id, title, similarity)`.
2. `nearest_neighbours` = `similar_items(space="topic", kinds={"topic", "article", "external_post"}, limit=limit, since=None, until=None, exclude_article_id=exclude_article_id)`.
3. `candidate_signals` (let `D(n) = now − timedelta(days=n)`):
   - `neighbours = similar_items(space="topic", kinds=all three, limit=NEIGHBOUR_LIMIT, since=D(config.lookback_days), until=None, exclude_candidate_id=...)`; `topic_best = neighbours[0] if neighbours else None`.
   - `argument_best` = the first of `similar_items(space="argument", kinds={"topic", "article"}, limit=1, since=D(config.lookback_days), until=None, exclude_candidate_id=...)`, or None.
   - `news_reuse_url = primary_canonical_url` when it is not None and either:
     - a `Topic` exists with `primary_source_url == primary_canonical_url`, `created_at >= D(config.news_reuse_days)` and `candidate_id IS DISTINCT FROM exclude_candidate_id`; or
     - a live `Article` exists with `created_at >= D(config.news_reuse_days)` whose current version has an `ArticleSource` with `is_primary = true` joined to a `LedgerSource` with `canonical_url == primary_canonical_url`.
     - Otherwise None.
   - `headline_best`:
     - Candidate titles are `Topic.title` (created `>= D(config.lookback_days)`, excluding the candidate's own topic), non-null titles of live `Article` rows created `>= D(config.lookback_days)`, and every `ExternalPost.title`.
     - Take the max of `trigram_jaccard(title, other)`; ties are broken by the other title ascending.
     - It is `(round(j, 6), other)`, or None when there are no titles.
   - `pattern = classify_headline(title)`.
   - `pattern_uses = count(Topic where headline_pattern == pattern.value and created_at >= D(config.headline_pattern_window_days), excluding the candidate's topic) + count(ExternalPost where headline_pattern == pattern.value and published_at >= D(config.headline_pattern_window_days)) + 1`.
   - `reused_examples`: let `seen` be the set of `normalize_words(x)` over `Topic.examples` of topics created `>= D(config.example_reuse_days)` (excluding the candidate's topic). The result is the candidate `examples` whose `normalize_words` is in `seen`, in candidate order, with original spelling, first occurrence only.
   - It returns `(NoveltySignals(...), neighbours)`.
4. `check_article_duplicate`:
   - Loads the version (`LookupError(f"version {version_id} not found")`) and its article. `ref = article.created_at`.
   - Loads the version's `VersionEmbedding` rows of kinds `article` and `argument`. If either is missing: `LookupError(f"version embeddings not recorded for {version_id}")`.
   - `top = similar_items(space="topic", kinds={"article", "external_post"}, limit=1, since=ref − timedelta(days=config.novelty.lookback_days), until=ref, exclude_article_id=article.id, exclude_external_slug=article.slug)`.
   - `arg = similar_items(space="argument", kinds={"article"}, limit=1, <same window and exclusion>)`.
   - Let `t`, `g` be their similarities (0.0 when empty) and `T = config.novelty.topic_threshold`, `A = config.novelty.argument_threshold`.
   - Result:
     - `t >= T` → failed, `details = f'similarity {t:.2f} >= {T:.2f} with {kind} "{title}" ({ref_id})'`;
     - else `g >= A` → failed, `details = f'argument similarity {g:.2f} >= {A:.2f} with {kind} "{title}" ({ref_id})'`;
     - else passed, `details = f"max similarity {max(t, g):.2f} (limit {T:.2f})"`.
   - Returns `GateResult(gate=GateId.NO_DUPLICATE_TOPIC.value, passed=..., severity="blocking", details=...)`.
   - Read-only: no insert, update or commit.
5. The module never commits and never calls the gateway.

**Tests to write FIRST** (`backend/tests/topics/test_top_novelty_service.py`; `db_session`, `vectors`, TOP-0 factories; `NOW = datetime.now(UTC)` read once per test; multi-article tests depend on the TOP-0 gate).
- `test_top_nearest_neighbours_ranks_across_kinds`
  - Setup:
    - `a = await make_article_graph(db_session)`;
    - `UPDATE app.blog_topics SET embedding = e(2), argument_embedding = e(3) WHERE id = a.topic_id` (through the ORM);
    - `add_version_embedding(version_id=a.version_id, kind="article", embedding=mix(0.6, 0, 1))`;
    - topics `T1` (`embedding=e(0)`) and `T2` (`embedding=e(1)`), with `argument_embedding=e(4)`;
    - external posts `P1` (`mix(0.8, 0, 1)`) and `P2` (`[-v for v in e(0)]`).
  - `nearest_neighbours(db_session, embedding=e(0), limit=3)` equals `[NoveltyNeighbour(kind="topic", ref_id=str(T1.id), title="T1", similarity=1.0), NoveltyNeighbour(kind="external_post", ref_id=str(P1.id), title="P1", similarity=0.8), NoveltyNeighbour(kind="article", ref_id=str(a.article_id), title=<article.title or version.title_options["operational"] read from the DB>, similarity=0.6)]`.
- `test_top_nearest_neighbours_excludes_article_and_its_topic`
  - Same setup, with `limit=10, exclude_article_id=a.article_id`.
  - The `ref_id` list is `[T1, P1, P2, T2]`: the three zero-similarity items are ordered `external_post` before `topic`. Neither `a.article_id` nor `a.topic_id` appears.
- `test_top_nearest_neighbours_live_articles_only`, parametrized `(ArticleStatus.SUPERSEDED, False), (ArticleStatus.REJECTED, False), (ArticleStatus.FAILED, True)`: `make_article_graph(db_session, status=status)`, add article embedding `e(0)` → `any(n.kind == "article" for n in result)` equals the expected flag.
- `test_top_similar_items_time_window`: topic `T1` `e(0)` with `created_at=NOW - 181 days` and topic `T2` `mix(0.5, 0, 1)` with `created_at=NOW`. `similar_items(space="topic", kinds={"topic"}, limit=5, since=NOW - 180 days, until=None)` returns only `T2`. `until=NOW - 1 day` returns only `T1` when `since=None`.
- `test_top_similar_items_rejects_wrong_dimension`: `embedding=[1.0]` raises `ValueError("expected 1536 dimensions, got 1")`.
- `test_top_candidate_signals_empty_history`: `candidate_signals(embedding=e(0), argument_embedding=e(1), title="Specialist scarcity is a routing problem", primary_canonical_url="https://ex.org/a", examples=["Epic"], exclude_candidate_id=None, config=CFG, now=NOW)` returns `(NoveltySignals(None, None, None, None, HeadlinePattern.STATEMENT, 1, ()), [])`.
- `test_top_candidate_signals_topic_and_argument`: topic `T1` with `embedding=mix(0.9, 0, 1)` and `argument_embedding=e(5)`. With candidate `embedding=e(0)` and `argument_embedding=e(5)`: `signals.topic_best.similarity == 0.9` and `.ref_id == str(T1.id)`, `signals.argument_best.similarity == 1.0`, `neighbours[0].ref_id == str(T1.id)`.
- `test_top_candidate_signals_news_reuse_from_topics`: topic with `primary_source_url="https://ex.org/a"` and `created_at=NOW - 10 days` → `news_reuse_url == "https://ex.org/a"`. With `created_at=NOW - 31 days` → None.
- `test_top_candidate_signals_news_reuse_from_articles`
  - `a = make_article_graph(db_session)`.
  - Test setup marks `S1` primary: `UPDATE app.blog_article_sources SET is_primary = true WHERE version_id = a.version_id AND marker = 'S1'`.
  - Read that source's `canonical_url` as `u`.
  - `candidate_signals(primary_canonical_url=u, ...)` gives `news_reuse_url == u`.
- `test_top_candidate_signals_headline_and_pattern`
  - Setup:
    - topic `"How to cut prior authorisation delays"` (`headline_pattern=HOW_TO`, `created_at=NOW - 3 days`);
    - topic `"How AI helps"` (`HOW_TO`, `NOW - 20 days`);
    - external post `"How clinics adapt"` (`HOW_TO`, `published_at=NOW - 1 day`).
  - Candidate title `"How to cut prior authorisation delay"`.
  - Assert:
    - `signals.headline_best == (round(trigram_jaccard("How to cut prior authorisation delay", "How to cut prior authorisation delays"), 6), "How to cut prior authorisation delays")`;
    - `signals.pattern == HOW_TO`;
    - `signals.pattern_uses == 3`.
- `test_top_candidate_signals_reused_examples`: topic `examples=["Epic Systems", "CMS-0057-F"]` created `NOW - 5 days`; candidate examples `["epic systems", "Mayo", "Epic Systems"]` → `reused_examples == ("epic systems",)`. With the topic created `NOW - 31 days` → `()`.
- `test_top_candidate_signals_excludes_own_candidate`: a topic with `candidate_id=cand.id` and `embedding=e(0)`, and `exclude_candidate_id=cand.id` → `topic_best is None`.
- `test_top_check_article_duplicate_article_similarity`
  - `x = make_article_graph(db_session)`, `y = make_article_graph(db_session)`.
  - Embeddings: x `article=e(0), argument=e(10)`; y `article=mix(0.9, 0, 1), argument=e(11)`.
  - `check_article_duplicate(db_session, version_id=x.version_id, config=effective_config)` returns `GateResult(gate="no_duplicate_topic", passed=False, severity="blocking", details=f'similarity 0.90 >= 0.85 with article "{y_title}" ({y.article_id})')`.
- `test_top_check_article_duplicate_passes_below_threshold`: y `article=mix(0.84, 0, 1)` → `passed is True`, `details == "max similarity 0.84 (limit 0.85)"`.
- `test_top_check_article_duplicate_argument_similarity`: y `article=e(1)`, `argument=mix(0.88, 10, 12)` → `passed is False`, `details.startswith("argument similarity 0.88 >= 0.88 with article")`.
- `test_top_check_article_duplicate_external_posts`: x has head `slug` from `with_seo=True`. External post with slug `x.slug` and `embedding=mix(0.95, 0, 1)` → passed. The same post with slug `"other-post"` → `passed is False` and `'with external_post "' in details`.
- `test_top_check_article_duplicate_window_and_status`, parametrized, each with y `article=mix(0.9, 0, 1)` → `passed is True` in all three cases:
  - (a) `y.created_at = x.created_at - 181 days`;
  - (b) `y.created_at = x.created_at + 1 day`;
  - (c) `y.status = "SUPERSEDED"`.
- `test_top_check_article_duplicate_missing_embeddings`: no version embeddings → `LookupError` with message `f"version embeddings not recorded for {x.version_id}"`. A random `version_id` → `LookupError`.

**Implementation notes.**
Verified 2026-09-17 in `mdcopilot-blog-backend:dev` against `pgvector/pgvector:pg16` (async psycopg; results are `float`; vectors read back as `list[float]`):
```python
distance = Topic.embedding.cosine_distance(list(embedding))
rows = (await db.execute(
    select(Topic.id, Topic.title, distance.label("distance"))
    .where(Topic.embedding.is_not(None))
    .order_by(distance, Topic.id)
    .limit(limit)
)).all()
similarity = round(min(1.0, max(0.0, 1.0 - float(row.distance))), 6)
```
The `is_primary` update in the news-reuse test is test-only setup on FOUND graph rows. Production code in this module performs no writes.

**Verification.**
1. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_novelty_service.py` fails with `NotImplementedError` or ImportError.
2. Implement.
3. Green: 0 failed. TOP-LINT clean.

**Acceptance bullets covered:**
- §10.2 "Embeddings + novelty engine" (history comparisons against topics, articles and external posts; 180-day lookback; news and example reuse; headline repetition).
- §10.2 "Seeded near-duplicate external post rejected, neighbour and similarity shown" (similarity part).
- §10.4 "All 15 gates … diversity checks" (gate 6 `check_article_duplicate`, TOP part).
- §10.4 "SEO Specialist … internal links from published and external posts" (`nearest_neighbours`, TOP part).

---
### TOP-6: Step bodies D5 and D6 — `ideate_topics`, `check_novelty_and_score`

**Files:**
- Modify `pkg/services/topic_steps.py` (FOUND stub; keep every §5.6 model and signature).
- Create `backend/tests/topics/test_top_steps_ideate.py` and `backend/tests/topics/test_top_steps_novelty.py`.

**Interfaces.**
- Consumes:
  - `StepContext` (`settings`, `config`, `brand`, `sessionmaker`, `gateway`, `call`, `with_ids`, `now`);
  - `agents.topic_strategist` (TOP-4), called as `topic_strategist.run_topic_strategist`;
  - `agents.common.number_sources`; `services.config.pillar_for_date`;
  - `services.novelty.candidate_signals` (TOP-5); `domain.novelty` (TOP-3); `domain.scoring` (TOP-2);
  - ORM `ResearchRun`, `LedgerSource`, `ResearchFindingRecord`, `FindingSource`, `BlogRun`, `ContentPillar`, `DiscoveryTheme`, `Topic`, `ExternalPost`, `TopicCandidateRecord`.
- Produces (frozen by §5.6):
```python
class IdeateResult(BaseModel): candidate_ids: list[uuid.UUID]; round: int
async def ideate_topics(sc: StepContext, *, research_run_id: uuid.UUID, round_no: int,
                        avoid_candidate_ids: Sequence[uuid.UUID]) -> IdeateResult
class NoveltyScoreResult(BaseModel): passed_ids: list[uuid.UUID]; warned_ids: list[uuid.UUID]; rejected_ids: list[uuid.UUID]
async def check_novelty_and_score(sc: StepContext, *, candidate_ids: Sequence[uuid.UUID]) -> NoveltyScoreResult
```

**Behaviour rules — `ideate_topics`.**
1. Validation:
   - `round_no < 1` → `ValueError(f"round_no must be >= 1, got {round_no}")`.
   - Load `ResearchRun` → `LookupError(f"research run {research_run_id} not found")`.
   - If `sc.call.run_id is not None and sc.call.run_id != rr.run_id` → `ValueError(f"research run {research_run_id} belongs to run {rr.run_id}, not {sc.call.run_id}")`.
2. **Replay:** when `sc.call.dbos_workflow_id is not None` and 3 candidate rows already exist with that `(dbos_workflow_id, dbos_step_id)`, return `IdeateResult(candidate_ids=<ids by position>, round=round_no)` without calling the gateway.
3. **Sources:** load `LedgerSource` rows for `rr.source_ids`, in that order, skipping ids with no row. If none → `ValueError(f"research run {research_run_id} has no ledger sources")`. `numbered = number_sources(rows, preserve_order=True)`, so `S<n>` follows `rr.source_ids`.
4. **Findings:** `ResearchFindingRecord` rows of `rr` ordered by `position`, each as `FindingBrief(claim, claim_type, importance, confidence, markers)`. `markers` are the markers of its `FindingSource.source_id`s that appear in `numbered`, sorted by marker number.
5. **Pillars:**
   - Active `ContentPillar` rows by `sort_order` become `PillarBrief`.
   - If none → `LookupError("no active content pillar")`.
   - Target pillar, in order: `BlogRun.params.get("pillar")` when it names an active pillar; else `pillar_for_date(db, run.run_date)` when it names an active pillar; else the first active pillar.
6. **Coverage** (window `W = sc.now() − config.diversity.lookback_days days`):
   - `pillar_counts[key]` = number of `Topic` rows with `created_at >= W` and that `pillar_key`.
   - `theme_counts` is an ordered dict over active `DiscoveryTheme` rows by `(sort_order, key)`. Each value is the number of `ResearchRun` rows with `kind == "broad"`, `started_at >= W` and `key in themes_covered`.
7. **Avoid list** (`AvoidTopic`s in this order, deduplicated by `normalize_words(title)`, first kept):
   1. the candidates in `avoid_candidate_ids`, in the given order, as `(title, thesis)` (ids with no row are skipped);
   2. up to 30 `Topic` rows with `created_at >= sc.now() − config.novelty.lookback_days`, newest first, as `(title, thesis)`;
   3. up to 30 `ExternalPost` rows ordered by `published_at DESC NULLS LAST, id DESC`, as `(title, excerpt)`.
8. **Call:** `result = await topic_strategist.run_topic_strategist(sc.gateway, ctx=sc.call, variables=build_variables(...), user_prompt=build_user_prompt(round_no=..., target_pillar=..., findings=..., numbered=numbered), numbered=numbered, avoid=avoid, route_override=sc.config.routes[AgentName.IDEATION.value], prompt_version=sc.config.prompt_versions.get("ideation/topics"))`.
9. **Write** (one session, one commit):
   1. Supersede earlier rounds: `UPDATE blog_topic_candidates SET status='SUPERSEDED' WHERE run_id = rr.run_id AND round < round_no AND status IN ('PROPOSED','PASSED','WARNED','REJECTED')` (P9).
   2. For idea `i` (0-based position), resolve its markers through `numbered` to rows:
      - `source_ids` = unique `str(ledger id)` of `source_markers`, in marker order;
      - `primary_source_id` = the ledger id of `primary_marker`;
      - `relevant_news` = `[NewsRef(title=row.title, url=row.url, published_at=row.published_at).model_dump(mode="json")]` for the same unique rows in the same order;
      - `rubric = {"businessRelevance": idea.business_relevance.model_dump(mode="json"), "audienceRelevance": idea.audience_relevance.model_dump(mode="json"), "editorialPotential": idea.editorial_potential.model_dump(mode="json")}`;
      - `examples = idea.examples`, `pillar_key = idea.pillar.value`, `status = "PROPOSED"`, `is_manual = False`, `round = round_no`, `position = i`;
      - `research_run_id = rr.id`, `run_id = rr.run_id`;
      - `dbos_workflow_id` and `dbos_step_id` from `sc.call`;
      - every text field copied verbatim;
      - embeddings, scores and novelty NULL.
   3. Insert each row with `ON CONFLICT DO NOTHING` on the partial unique index `uq_blog_topic_candidates_wf_step_position` (snippet below). When nothing is returned, read the existing id by `(dbos_workflow_id, dbos_step_id, position)`.
   4. Commit, then return `IdeateResult(candidate_ids=[id0, id1, id2], round=round_no)`.
10. The body never changes `blog_runs.status` (§5.5 rule 4).

**Behaviour rules — `check_novelty_and_score`.**
1. Load the candidates. Any missing id → `LookupError(f"topic candidate {id} not found")` before any work.
2. For each candidate, in input order, with `status == "PROPOSED"`:
   1. If `embedding` or `argument_embedding` is NULL:
      - `vectors = await sc.gateway.embed([candidate_embedding_text(title=c.title, hook=c.hook, thesis=c.thesis, angle=c.angle), c.core_argument.strip()], ctx=sc.with_ids(topic_candidate_id=c.id).call)`;
      - each vector must have 1536 floats, else `ValueError`;
      - store both in their own session and commit.
   2. Load the candidate's `LedgerSource` rows (`source_ids`) and the primary source's `canonical_url`.
   3. `signals, neighbours = await novelty.candidate_signals(db, embedding=c.embedding, argument_embedding=c.argument_embedding, title=c.title, primary_canonical_url=<canonical_url from step 2, or None>, examples=c.examples, exclude_candidate_id=c.id, config=sc.config.novelty, now=sc.now())`.
   4. `a = assess_novelty(signals, sc.config.novelty)`, `ns = novelty_score(a.max_similarity)`.
   5. `card = score_candidate(ScoreInputs(...), weights=sc.config.score_weights, min_source_count=sc.config.research.min_source_count, now=sc.now())` with:
      - `newest_published_at` = max non-null `published_at`;
      - `dated_sources` = count with `published_at`;
      - `total_sources` = row count;
      - `tier12_sources` = count with `tier in (1, 2)`;
      - `primary_source_present = c.primary_source_id is not None`;
      - `novelty_score = ns`, `novelty_justification = novelty_justification(a)`;
      - rubric items from `c.rubric[<camelCase key>]`, or None when the key is absent.
   6. `UPDATE blog_topic_candidates WHERE id = c.id AND status = 'PROPOSED'` setting:
      - `novelty = NoveltyResult(decision=a.decision, max_similarity=a.max_similarity, neighbours=neighbours).model_dump(mode="json")`;
      - `novelty_decision = a.decision.value`;
      - `novelty_score = card.novelty`, `timeliness_score = card.timeliness`, `evidence_score = card.evidence`, `business_relevance = card.business_relevance`, `audience_relevance = card.audience_relevance`, `editorial_potential = card.editorial_potential`, `total_score = card.total`;
      - `score_breakdown = {k: v.model_dump(mode="json") for k, v in card.breakdown.items()}`;
      - `status = candidate_status(a.decision, is_manual=c.is_manual).value`.
      Then commit.
3. Candidates not in `PROPOSED` are not modified and make no gateway call.
4. **Result:** walk the input ids in order after processing and classify by `novelty_decision`:
   - `PASS` → `passed_ids`;
   - `WARN` → `warned_ids`;
   - `REJECT_TOPIC` → `rejected_ids`, or `warned_ids` when `is_manual`;
   - `NULL` → omitted.

**Tests to write FIRST.**
All use `sessionmaker_committing` and `sc = await mock_step_context(agents=["ideation"])`. `graph` is created with `make_research_graph(db, run_id=sc.call.run_id)` in a committing session and committed. `SETS` is the fixture file loaded as JSON (set A is the last case, B–E the `Round: n` cases).

`backend/tests/topics/test_top_steps_ideate.py`
- `test_top_ideate_creates_three_proposed_candidates`
  - `r = await topic_steps.ideate_topics(sc, research_run_id=graph.research_run_id, round_no=1, avoid_candidate_ids=[])`.
  - Assert:
    - `r.round == 1` and `len(r.candidate_ids) == 3`;
    - the rows by position have `[c.position for c in rows] == [0, 1, 2]`, all `status == "PROPOSED"`, `research_run_id == graph.research_run_id` and `run_id == sc.call.run_id`;
    - titles equal set A titles;
    - for idea 0, `rows[0].source_ids == [str(graph.source_ids[int(m[1:]) - 1]) for m in <unique sourceMarkers>]` and `rows[0].primary_source_id == graph.source_ids[int(primary[1:]) - 1]`;
    - `rows[0].relevant_news[0]["title"]` equals the ledger title of the first marker;
    - `rows[0].rubric["businessRelevance"]["score"]` equals the fixture value;
    - exactly one `blog_llm_calls` row with `agent_name == "ideation"`, `run_id == sc.call.run_id`, `prompt_name == "ideation/topics"`, `status == "ok"`.
- `test_top_ideate_round_two_supersedes_and_avoids`
  - Round 1. Then, in a committing session, set position statuses to `SELECTED`, `DISMISSED`, `PASSED`.
  - Round 2 with `avoid_candidate_ids=<round-1 ids>`.
  - Assert:
    - round-1 statuses are now `["SELECTED", "DISMISSED", "SUPERSEDED"]`;
    - round-2 titles equal set B titles;
    - `{normalize_words(t) for t in round2} & {normalize_words(t) for t in round1} == set()`.
- `test_top_ideate_passes_avoid_list_prompt_and_route`
  - `monkeypatch.setattr(topic_strategist, "run_topic_strategist", spy)`, where `spy` records its kwargs and awaits the original.
  - Round 1, then round 2 with the round-1 ids.
  - For the round-2 call assert:
    - `[a.title for a in kw["avoid"][:3]] == <round-1 titles>`;
    - `kw["user_prompt"].startswith("Round: 2\n")`;
    - `kw["route_override"] == sc.config.routes["ideation"]` and `kw["prompt_version"] is None`;
    - `kw["variables"]["target_pillar"].startswith(f"{expected} — ")`, where `expected` is `await pillar_for_date(db, run.run_date)`, or the first active pillar key when that is None.
- `test_top_ideate_uses_run_params_pillar`: set `blog_runs.params = {"pillar": "D"}` for `sc.call.run_id` (committed) → the spy sees `variables["target_pillar"].startswith("D — ")`.
- `test_top_ideate_is_idempotent_with_dbos_ids`
  - `sc2 = dataclasses.replace(sc, call=dataclasses.replace(sc.call, dbos_workflow_id="wf-top-ideate", dbos_step_id=4))`.
  - Call `ideate_topics(sc2, research_run_id=graph.research_run_id, round_no=1, avoid_candidate_ids=[])` twice.
  - Assert both results have equal `candidate_ids`, `SELECT count(*) FROM app.blog_topic_candidates` returns 3, and the ideation `blog_llm_calls` count is 1.
- `test_top_ideate_rejects_foreign_research_run`: `other = make_research_graph(db)` (its own run), committed → `ValueError` whose message contains `"belongs to run"`.
- `test_top_ideate_requires_sources`: test-only setup `UPDATE app.blog_research_runs SET source_ids='[]'` for `graph.research_run_id` → `ValueError(f"research run {graph.research_run_id} has no ledger sources")`.
- `test_top_ideate_rejects_round_zero`: `round_no=0` → `ValueError("round_no must be >= 1, got 0")`.

`backend/tests/topics/test_top_steps_novelty.py`
- `test_top_novelty_golden_path_all_pass_with_distinct_totals`
  - Ideate round 1, then `res = await topic_steps.check_novelty_and_score(sc, candidate_ids=r.candidate_ids)`.
  - Assert:
    - `res.passed_ids == r.candidate_ids` and `res.warned_ids == res.rejected_ids == []`;
    - every row has `status == "PASSED"`, `novelty_decision == "PASS"`, `novelty == {"decision": "PASS", "maxSimilarity": 0.0, "neighbours": []}`, `novelty_score == 1.0`, non-null embeddings of 1536 floats and `list(score_breakdown) == list(SCORE_KEYS)`;
    - `len({row.total_score for row in rows}) == 3`;
    - three `blog_llm_calls` rows with `kind == "embedding"`, `run_id == sc.call.run_id` and `topic_candidate_id` equal to each candidate id;
    - for row 0, `total_score == score_candidate(<inputs rebuilt from the row's ledger sources and rubric>, weights=sc.config.score_weights, min_source_count=sc.config.research.min_source_count, now=sc.now()).total`.
- `test_top_novelty_rejects_seeded_near_duplicate_external_post`
  - Ideate round 1 and read row 0.
  - `base = mock_embedding(candidate_embedding_text(title=row.title, hook=row.hook, thesis=row.thesis, angle=row.angle), 1536)`, `noise = mock_embedding("noise", 1536)`, `near = [b + 0.2 * n for b, n in zip(base, noise)]`.
  - Commit `await make_external_post(db, slug="near-dup", title="Existing MDCopilot post", embedding=near)` in a committing session.
  - Run `check_novelty_and_score`.
  - Assert:
    - `res.rejected_ids == [row.id]`;
    - row 0 has `status == "REJECTED"`;
    - `novelty["neighbours"][0]["kind"] == "external_post"`, `["refId"] == str(post.id)`, `["title"] == "Existing MDCopilot post"`, `["similarity"] == pytest.approx(round(cosine_similarity(base, near), 6), abs=1e-6)`;
    - `novelty["maxSimilarity"]` is equal to that similarity;
    - `novelty_score == pytest.approx(round(1 - novelty["maxSimilarity"], 6), abs=1e-6)`;
    - `score_breakdown["novelty"]["justification"].startswith("REJECT_TOPIC: topic similarity 0.98 >= 0.85 (external_post ")`;
    - the other two candidates are `PASSED`.
- `test_top_novelty_is_idempotent`: a second `check_novelty_and_score` call on the same ids leaves the embedding-row count unchanged and returns the same result lists, and every row keeps its `total_score`.
- `test_top_novelty_reuses_stored_embeddings`: a `PROPOSED` candidate from `make_candidate(status=PROPOSED)` with embeddings set (committed) → no `kind == "embedding"` row is written, and the status is no longer `PROPOSED`.
- `test_top_novelty_manual_candidate_reject_becomes_warned`
  - Committed topic with `embedding=vectors.e(0)` and `argument_embedding=vectors.e(1)`.
  - `make_candidate(status=PROPOSED, is_manual=True, embedding=vectors.e(0), argument_embedding=vectors.e(2), total_score=None)`.
  - Run the check.
  - Assert `res.warned_ids == [cand.id]`, `status == "WARNED"` and `novelty_decision == "REJECT_TOPIC"`.
- `test_top_novelty_skips_non_proposed`: a `PASSED` candidate with `novelty` set (decision PASS) and `total_score=0.42` → `res.passed_ids == [cand.id]`, `total_score` stays `0.42`, and no embedding row.
- `test_top_novelty_missing_candidate`: `candidate_ids=[uuid.uuid4()]` → `LookupError`.

**Implementation notes.**
Verified 2026-09-17 in `mdcopilot-blog-backend:dev` against `pgvector/pgvector:pg16`:
- Without `index_where`, Postgres raises `InvalidColumnReference`.
- `result.rowcount` is `-1` under async psycopg, so use `RETURNING`.
- `dbos_workflow_id IS NULL` rows always insert.
```python
stmt = (
    insert(TopicCandidateRecord)
    .values(**row)
    .on_conflict_do_nothing(
        index_elements=["dbos_workflow_id", "dbos_step_id", "position"],
        index_where=text("dbos_workflow_id IS NOT NULL"),
    )
    .returning(TopicCandidateRecord.id)
)
inserted_id = (await db.execute(stmt)).scalar_one_or_none()
```

**Verification.**
1. Red: run both files; expect `NotImplementedError`.
2. Implement.
3. Green:
```bash
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_steps_ideate.py tests/topics/test_top_steps_novelty.py
```
Expected: 0 failed. TOP-LINT clean.

**Acceptance bullets covered:**
- §10.2 "Always exactly 3 candidates" (3 rows per round).
- "Embeddings + novelty engine" (D6 end to end).
- "Scoring … stored breakdown".
- "Seeded near-duplicate external post rejected, neighbour and similarity shown" (step half).
- "`POST /topics/generate` → 3 new candidates not repeating the previous round" (avoid list and supersede).
- §5.8 TOP invariant (all 3 PASS on empty history, distinct totals).

---
### TOP-7: Step bodies D7 and manual topic — `promote_candidate`, `select_topic`, `create_manual_candidate`

**Files:**
- Modify `pkg/services/topic_steps.py`.
- Create `backend/tests/topics/test_top_steps_select.py`.

**Interfaces.**
- Consumes TOP-1 (`classify_headline`, `extract_keywords`), TOP-3 (`round_shortfall`), TOP-6 (`check_novelty_and_score`, called as `topic_steps.check_novelty_and_score` inside `create_manual_candidate`), `services.config.pillar_for_date`, and ORM `TopicCandidateRecord`, `Topic`, `LedgerSource`, `BlogRun` and `ContentPillar`.
- Produces (frozen by §5.6):
```python
class SelectResult(BaseModel): candidate_id: uuid.UUID | None; topic_id: uuid.UUID | None; shortfall: bool
async def select_topic(sc: StepContext, *, run_id: uuid.UUID, mode: Literal["auto", "manual"]) -> SelectResult
async def create_manual_candidate(sc: StepContext, *, run_id: uuid.UUID, topic: str, pillar_key: PillarKey | None,
                                  audience: str | None, tone: str | None) -> IdeateResult
async def promote_candidate(db: AsyncSession, *, candidate_id: uuid.UUID, selected_by: uuid.UUID | None) -> uuid.UUID
KEYWORD_LIMIT = 10
```

**Behaviour rules — `promote_candidate`** (API and step code both call it; flush only, never commit).
1. `SELECT … FOR UPDATE` the candidate. Missing → `LookupError(f"topic candidate {candidate_id} not found")`.
2. `status == "SELECTED"`: return the id of the `Topic` whose `candidate_id` is this candidate, inserting the topic (rule 5) if none exists. `selected_by` and `selected_at` are left unchanged.
3. Any status other than `PASSED` or `WARNED` → `ValueError(f"candidate {candidate_id} is {status}; only PASSED or WARNED can be selected")`.
4. `embedding` or `argument_embedding` NULL → `ValueError(f"candidate {candidate_id} has no embeddings")`.
5. Set `status="SELECTED"`, `selected_by=selected_by` and `selected_at=datetime.now(UTC)`. Then insert a `Topic` with:
   - `candidate_id`, `run_id`, `title`, `pillar_key`, `thesis`, `angle`, `core_argument` and `examples` copied from the candidate;
   - `keywords = extract_keywords("\n".join([title, thesis, core_argument]), limit=KEYWORD_LIMIT)`;
   - `headline_pattern = classify_headline(title).value`;
   - `primary_source_url` = the `canonical_url` of the primary `LedgerSource`, or None;
   - `source_domains` = the unique `domain` values of the candidate's `source_ids` rows, in `source_ids` order;
   - `embedding` and `argument_embedding` copied.
   Insert with `ON CONFLICT (candidate_id) DO NOTHING RETURNING id`; on conflict read the existing id. Flush and return the topic id.

**Behaviour rules — `select_topic`.**
1. In its own session: load the run's candidates of the newest round, `max(round)` for `run_id`. No candidates → `SelectResult(candidate_id=None, topic_id=None, shortfall=False)`.
2. `shortfall = round_shortfall(statuses=<statuses in that round, read before any change>, round_no=<newest>, max_regeneration_rounds=sc.config.novelty.max_regeneration_rounds)`.
3. A `SELECTED` candidate already in that round → return it with its topic id (from `promote_candidate`, which is idempotent) and `shortfall`. Commit.
4. An `is_manual` candidate in `PASSED` or `WARNED` in that round → promote it with `selected_by=None`, whatever `mode` is. The human already chose the topic (ARCHITECTURE §5.1).
5. `mode == "auto"`: take the `PASSED` candidates by `total_score` descending (NULL last), then `position` ascending. Promote the first with `selected_by=None`. None → no selection.
6. `mode == "manual"`: select nothing.
7. Commit and return `SelectResult(candidate_id, topic_id, shortfall)`.
8. Never changes `blog_runs.status` (INT moves it to `WAITING_FOR_TOPIC` or `PRODUCING`).

**Behaviour rules — `create_manual_candidate`.**
1. Load `BlogRun` → `LookupError(f"run {run_id} not found")`. `topic.strip()` must be 1..300 characters, else `ValueError("manual topic must be 1..300 characters")`.
2. **Replay:** when `sc.call.dbos_workflow_id` is set and a row exists with that `(dbos_workflow_id, dbos_step_id, position=0)`, run rule 5 on it and return `IdeateResult([id], 1)`.
3. **Pillar (P10):** `pillar_key.value` when given; else `await pillar_for_date(db, run.run_date)`; else the first active `ContentPillar.key` by `sort_order`; none → `LookupError("no active content pillar")`.
4. Insert (same partial-index `ON CONFLICT` as TOP-6) with:
   - `title = thesis = core_argument = topic.strip()`;
   - `hook = why_now = angle = mdcopilot_connection = ""`;
   - `target_audience = audience.strip() if audience and audience.strip() else sc.brand.target_audience`, truncated to 10,000 characters;
   - `pillar_key` from rule 3;
   - `round = 1`, `position = 0`, `is_manual = True`, `status = "PROPOSED"`;
   - `research_run_id = None`, `source_ids = []`, `relevant_news = []`, `primary_source_id = None`, `examples = []`, `rubric = {}`;
   - `run_id` from the argument and the dbos ids from `sc.call`.
   Commit. `tone` is not stored (P10).
5. `await topic_steps.check_novelty_and_score(sc, candidate_ids=[id])`, which embeds, assesses and scores; a REJECT becomes `WARNED`.
6. Return `IdeateResult(candidate_ids=[id], round=1)`.

**Tests to write FIRST** (`backend/tests/topics/test_top_steps_select.py`).
- `test_top_promote_passed_candidate_creates_topic` (`db_session`)
  - Setup: `g = make_research_graph(db_session)`; `c = make_candidate(run_id=g.run_id, research_run_id=g.research_run_id, source_ids=g.source_ids[:3], primary_source_id=g.source_ids[1], title="How to cut prior authorisation delays", thesis="Delays are a routing failure", core_argument="Routing beats hiring", examples=["CMS-0057-F"])`; `user = make_user(Role.EDITOR)`.
  - `tid = await promote_candidate(db_session, candidate_id=c.id, selected_by=user.id)`.
  - Assert:
    - `c.status == "SELECTED"`, `c.selected_by == user.id`, `c.selected_at is not None`;
    - the topic row has `candidate_id == c.id`, `run_id == g.run_id`, `title == c.title`, `pillar_key == "A"`, `thesis`, `angle`, `core_argument` and `examples == ["CMS-0057-F"]`;
    - `keywords == extract_keywords("How to cut prior authorisation delays\nDelays are a routing failure\nRouting beats hiring", limit=10)`;
    - `headline_pattern == "how_to"`;
    - `primary_source_url` equals the ledger `canonical_url` of `g.source_ids[1]`;
    - `source_domains` equals the unique domains of the first three ledger rows in order;
    - `embedding == c.embedding` (element-wise `pytest.approx`).
- `test_top_promote_warned_candidate_allowed`: a `WARNED` candidate → returns an id and the status is `SELECTED`.
- `test_top_promote_is_idempotent`: promote twice → same id; `SELECT count(*) FROM app.blog_topics WHERE candidate_id = c.id` returns 1.
- `test_top_promote_rejects_other_statuses`, parametrized over `PROPOSED`, `REJECTED`, `DISMISSED`, `SUPERSEDED` → `ValueError` with message `f"candidate {c.id} is {status}; only PASSED or WARNED can be selected"`.
- `test_top_promote_requires_embeddings`: `make_candidate(with_embeddings=False)` → `ValueError(f"candidate {c.id} has no embeddings")`.
- `test_top_promote_missing_candidate`: a random id → `LookupError`.

The following use committing sessions, `sc = await mock_step_context()`, and candidates made with `make_candidate(db, run_id=sc.call.run_id, round_no=<round>, position=<position>, status=<status>, total_score=<score>)` using the values each test lists (other arguments default), committed.
- `test_top_select_auto_picks_highest_passed`: round 1 with positions 0/1/2 = `PASSED 0.7`, `WARNED 0.95`, `PASSED 0.9` → `select_topic(sc, run_id=sc.call.run_id, mode="auto")` returns `candidate_id` = position 2, a non-null `topic_id` and `shortfall=False`. Position 2's status is `SELECTED`; positions 0 and 1 are unchanged.
- `test_top_select_auto_tie_breaks_by_position`: `PASSED 0.8`, `PASSED 0.8`, `REJECTED 0.99` → position 0.
- `test_top_select_uses_newest_round_only`: round 1 position 0 `PASSED 0.99`; round 2 positions 0..2 `PASSED 0.5`, `REJECTED 0.9`, `REJECTED 0.9` → selects round 2 position 0.
- `test_top_select_manual_mode_selects_nothing`: three `PASSED` → `SelectResult(candidate_id=None, topic_id=None, shortfall=False)`; statuses unchanged; no topic rows.
- `test_top_select_flags_shortfall_after_regeneration_limit`: round 3 with `PASSED 0.6`, `REJECTED`, `REJECTED` (and `max_regeneration_rounds == 2` from the seeded config) → `shortfall=True` and `candidate_id` = the PASSED one. The same statuses in round 2 → `shortfall=False`.
- `test_top_select_auto_without_passed`: `WARNED`, `REJECTED`, `REJECTED` in round 1 → `candidate_id is None`, `topic_id is None`.
- `test_top_select_manual_candidate_selected_in_manual_mode`: one `is_manual=True` `WARNED` candidate at round 1 position 0 → `mode="manual"` returns its id; status `SELECTED`.
- `test_top_select_is_idempotent`: after one auto select, a second call returns the same `candidate_id` and `topic_id`; one topic row.
- `test_top_create_manual_candidate_passes_on_empty_history`
  - `sc = await mock_step_context()`; `r = await create_manual_candidate(sc, run_id=sc.call.run_id, topic="  AI triage for referral backlogs  ", pillar_key=PillarKey.C, audience=None, tone="warm")`.
  - Assert:
    - `r.round == 1`, `len(r.candidate_ids) == 1`;
    - the row has `is_manual is True`, `title == thesis == core_argument == "AI triage for referral backlogs"`, `hook == ""`, `pillar_key == "C"`, `target_audience == sc.brand.target_audience`, `research_run_id is None`, `source_ids == []`, `status == "PASSED"`;
    - non-null `embedding` and `total_score`;
    - `score_breakdown["mdcopilotRelevance"]["justification"] == "manual topic: no rubric"`.
- `test_top_create_manual_candidate_pillar_fallback`
  - `pillar_key=None` → `pillar_key == await pillar_for_date(db, run.run_date)` (the seeded rotation always returns a pillar).
  - Then commit `UPDATE blog_content_pillars SET weekdays='[]'` for every pillar (test setup on seeded rows). A new run → `pillar_key` is the first active pillar by `sort_order` (`"A"`).
- `test_top_create_manual_candidate_near_duplicate_is_warned`
  - Let `t = "AI triage for referral backlogs"`. A manual candidate's embedding text is `candidate_embedding_text(title=t, hook="", thesis=t, angle="") == f"{t}\n{t}"`.
  - Commit a topic with `embedding=mock_embedding(f"{t}\n{t}", 1536)` (similarity 1.0 with the candidate) and `argument_embedding=vectors.e(1)`.
  - Call `create_manual_candidate(sc, run_id=sc.call.run_id, topic=t, pillar_key=None, audience=None, tone=None)`.
  - Assert the manual candidate's `status == "WARNED"` and `novelty_decision == "REJECT_TOPIC"`.
- `test_top_create_manual_candidate_rejects_blank_topic`: `topic="   "` → `ValueError("manual topic must be 1..300 characters")`.

**Implementation notes.** `ON CONFLICT (candidate_id)` targets the full unique constraint `uq_blog_topics_candidate_id`, so `index_elements=["candidate_id"]` needs no `index_where`. Use `.returning(Topic.id)` for the same `rowcount` reason as TOP-6.

**Verification.**
1. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_steps_select.py` gives `NotImplementedError`.
2. Implement.
3. Green: 0 failed. TOP-LINT clean.

**Acceptance bullets covered:**
- §10.2 "Embeddings + novelty engine + regeneration loop ≤2 rounds" (the `select_topic` shortfall flag).
- "Always exactly 3 candidates or flagged shortfall after 2 rounds".
- "Manual mode stops at `WAITING_FOR_TOPIC`" (TOP half: `mode="manual"` selects nothing).
- §5.1 manual topic (novelty as a warning only; D7 starts production).

---
### TOP-8: Diversity service — `record_version_features`, `build_avoid_bundle`, `evaluate_diversity`

**Files:**
- Modify `pkg/services/diversity.py` (FOUND stub).
- Create `backend/tests/topics/test_top_diversity_service.py`.

**Interfaces.**
- Consumes TOP-1 (`opening_sentence`, `extract_keywords`, `normalize_words`, `trigram_jaccard`, `count_repeated_phrases`), `domain.headlines.classify_headline`, `domain.novelty` (`NON_LIVE_ARTICLE_STATUSES`, `clamp_unit`), `domain.text` (`strip_citation_markers`, `normalize_for_match`), `domain.contracts` (`AvoidBundle`, `RecentArticleRef`, `ArticleSection`, `GateResult`), `domain.enums.GateId`, and ORM `Article`, `ArticleVersion`, `ArticleSource`, `LedgerSource`, `Topic`, `ExternalPost`, `VersionFeatures`, `VersionEmbedding`.
- Produces (frozen by §5.6):
```python
async def build_avoid_bundle(db: AsyncSession, *, config: EffectiveConfig, brand: BrandProfileValues, now: datetime,
                             exclude_article_id: uuid.UUID | None = None) -> AvoidBundle
async def record_version_features(sc: StepContext, *, version_id: uuid.UUID) -> None
class DiversityEvaluation(BaseModel): cta_fresh: GateResult; warnings: list[GateResult]
async def evaluate_diversity(db: AsyncSession, *, version_id: uuid.UUID, config: EffectiveConfig) -> DiversityEvaluation
DIVERSITY_WINDOW_DAYS = 7
RECENT_ARTICLES_LIMIT = 10
RECENT_TITLES_LIMIT = 30
OVERUSED_PHRASES_LIMIT = 20
EMBEDDING_KINDS: tuple[str, ...] = ("article", "opening", "argument")
```

**Behaviour rules — `record_version_features`.**
1. **Read session:**
   - Load the version (`LookupError(f"version {version_id} not found")`), its article, and the article's `Topic` (by `topic_id`).
   - Load the existing `VersionFeatures` row and the existing `VersionEmbedding` kinds for the version.
   - Load the version's `ArticleSource` rows joined to `LedgerSource`, sorted by `int(marker[1:])`.
   - Close the session.
2. If a features row exists and all three kinds exist, return `None`: no gateway call and no write.
3. **Values:**
   - `sections = [ArticleSection.model_validate(s) for s in version.sections]`.
   - `intro` is the section with key `introduction`.
   - `article_text = strip_citation_markers(version.content_markdown)`.
   - `opening = opening_sentence(intro.body_markdown)`.
   - `headline_pattern = classify_headline(article.title or version.title_options["operational"]).value`.
   - `industry_tags` are the entries of `sc.brand.focus_areas` whose `normalize_for_match(tag)` is a substring of `normalize_for_match(article_text)`, in `focus_areas` order.
   - `keywords = extract_keywords(article_text, limit=10)`.
   - `core_argument = topic.core_argument`, `examples = topic.examples`.
   - `primary_source_domains`:
     - the unique domains of rows with `is_primary = true`, in marker order;
     - when there are none, `[domain of the S1 row]` when an `S1` row exists;
     - else `[]`.
   - `cta_normalized = normalize_words(version.cta)`.
4. **Missing embeddings:** texts are taken in `EMBEDDING_KINDS` order, filtered to the missing kinds: `article → article_text`, `opening → opening`, `argument → topic.core_argument`. One call: `vectors = await sc.gateway.embed(texts, ctx=sc.with_ids(article_id=article.id).call)`. Each vector must have 1536 floats, else `ValueError`.
5. **Write session:**
   - Insert features with `ON CONFLICT (version_id) DO NOTHING`.
   - Insert each missing embedding with `ON CONFLICT (version_id, kind) DO NOTHING`, `model=sc.settings.embedding_model`, `dimensions=sc.settings.embedding_dimensions`.
   - Commit.
6. It never changes article status.

**Behaviour rules — `build_avoid_bundle`** (read-only; `L = now − config.diversity.lookback_days days`).
1. **Qualifying articles:** live (`status NOT IN NON_LIVE_ARTICLE_STATUSES`), `current_version_id IS NOT NULL`, `created_at >= L`, `id != exclude_article_id`, inner-joined to the current version and to its `VersionFeatures`. Order by `created_at DESC, id DESC`.
2. `recent_articles`: the first `RECENT_ARTICLES_LIMIT` as `RecentArticleRef(title=article.title or version.title_options["operational"], core_argument=features.core_argument, opening_sentence=features.opening_sentence)`.
3. `recent_titles`:
   - the titles (same rule) of the first `RECENT_TITLES_LIMIT` qualifying articles;
   - then `ExternalPost.title` for posts with `published_at >= L`, ordered `published_at DESC, id DESC`;
   - deduplicated by `normalize_words` (first kept) and capped at `RECENT_TITLES_LIMIT`.
4. `recent_openings`: `features.opening_sentence` of the first `config.diversity.opening_compare_last` qualifying articles.
5. `recent_ctas`: `version.cta` of the first `config.diversity.cta_compare_last` qualifying articles.
6. `recent_primary_sources`: the unique domains across `features.primary_source_domains` of all qualifying articles, in article order then list order.
7. `overused_phrases`: the phrase strings of `count_repeated_phrases([strip_citation_markers(v.content_markdown) for all qualifying], min_words=config.diversity.phrase_min_words, max_words=config.diversity.phrase_max_words, min_count=config.diversity.phrase_min_count, limit=OVERUSED_PHRASES_LIMIT)`.
8. `prohibited_language = list(brand.prohibited_language)`.

**Behaviour rules — `evaluate_diversity`** (read-only).
1. **Load:**
   - the version (`LookupError(f"version {version_id} not found")`), its article and its `VersionFeatures`;
   - missing features → `LookupError(f"version features not recorded for {version_id}")`;
   - `ref = article.created_at`.
2. **Others:** live articles with `id != article.id`, `current_version_id IS NOT NULL` and `created_at <= ref` (P4), joined to their current version's `VersionFeatures`. Order by `created_at DESC, id DESC`.
3. **`cta_fresh`** (gate `GateId.CTA_FRESH`, severity `blocking`):
   - Compare `features.cta_normalized` with the `cta_normalized` of the first `config.diversity.cta_compare_last` others. `m` = max `trigram_jaccard`; the best article is the first reaching it; `n` = number compared.
   - `m >= config.diversity.cta_similarity_threshold` → failed, `details = f"CTA similarity {m:.2f} >= {t:.2f} with article {other_id}"`.
   - Else passed, `details = f"max CTA similarity {m:.2f} across {n} recent articles"` (`m = 0.0` when `n = 0`).
4. **`opening_diversity`** (`GateId.OPENING_DIVERSITY`, severity `warning`):
   - Take this version's `opening` embedding. If it is missing → passed with `details = "opening embedding not recorded"`.
   - Otherwise compute the similarity (pgvector cosine distance, clamped, 6 decimals) against the `opening` embeddings of the first `config.diversity.opening_compare_last` others that have one.
   - `m >= config.diversity.opening_similarity_threshold` → failed, `f"opening similarity {m:.2f} >= {t:.2f} with article {other_id}"`.
   - Else passed, `f"max opening similarity {m:.2f} across {n} recent articles"`.
5. **`headline_diversity`** (`GateId.HEADLINE_DIVERSITY`, severity `warning`):
   - `uses = 1 + count(others with created_at >= ref − DIVERSITY_WINDOW_DAYS days and features.headline_pattern == features.headline_pattern)` (P3). There is no statement exclusion (P2).
   - `uses >= config.diversity.headline_pattern_max_7d` → failed, `f"headline pattern {p} used {uses} times in 7 days (limit {max})"`.
   - Else passed, `f"headline pattern {p} used {uses} times in 7 days"`.
6. **`source_domain_diversity`** (`GateId.SOURCE_DOMAIN_DIVERSITY`, severity `warning`):
   - For each domain `d` in `features.primary_source_domains` (in order): `uses_d = 1 + count(others in the same 7-day window whose primary_source_domains contain d)`.
   - Any `uses_d >= config.diversity.source_domain_max_7d` → failed, with details `"; ".join(f"primary source domain {d} used {uses_d} times in 7 days (limit {max})")` over the failing domains.
   - Else passed, `f"no primary source domain used {max} or more times in 7 days"`.
7. Return `DiversityEvaluation(cta_fresh=<3>, warnings=[<4>, <5>, <6>])` in that order.

**Tests to write FIRST** (`backend/tests/topics/test_top_diversity_service.py`).

Setup, unless a test says otherwise:
- `sc = await mock_step_context()`.
- Graph articles `make_article_graph(db)` are built in committing sessions and committed one at a time. Each later article therefore has a later `created_at`; tests create the comparison articles first and the target last.
- `cfg = sc.config`.

Tests:
- `test_top_record_version_features_writes_row_and_embeddings`
  - Article `x`: `await diversity.record_version_features(sc, version_id=x.version_id)`.
  - Features row:
    - `opening_sentence == opening_sentence(<introduction body of the golden version>)`;
    - `headline_pattern == classify_headline(<head title or operational option>).value`;
    - `keywords == extract_keywords(strip_citation_markers(content_markdown), limit=10)`;
    - `core_argument` equals the graph topic's `core_argument`;
    - `cta_normalized == normalize_words(version.cta)`;
    - `industry_tags` is a list whose every item is in `sc.brand.focus_areas`;
    - `primary_source_domains` follows rule 3 as evaluated in the test from the `blog_article_sources` rows.
  - `sorted(kind for kind in <embedding rows>) == ["argument", "article", "opening"]`, each with 1536 floats.
  - Exactly one `blog_llm_calls` row with `kind == "embedding"`, `article_id == x.article_id` and `params["count"] == 3`.
- `test_top_record_version_features_skips_when_present`: calling twice leaves one features row, three embedding rows and one embedding `blog_llm_calls` row.
- `test_top_record_version_features_fills_missing_kinds`: before the call, commit an `opening` embedding with `add_version_embedding` → after the call, 3 embedding rows, and the single embedding call has `params["count"] == 2`.
- `test_top_record_version_features_missing_version`: a random id → `LookupError`.
- `test_top_build_avoid_bundle_fields`
  - Articles `y`, then `x`, each with features recorded; one external post `"Existing post"` with `published_at = sc.now() − 1 day`.
  - `b = await diversity.build_avoid_bundle(db, config=cfg, brand=sc.brand, now=sc.now())`.
  - Assert:
    - `len(b.recent_articles) == 2`, newest first (`x` first);
    - `b.recent_openings` has 2 entries;
    - `b.recent_ctas == [<x cta>, <y cta>]`;
    - `"Existing post" in b.recent_titles`;
    - `b.prohibited_language == list(sc.brand.prohibited_language)`;
    - `b.recent_primary_sources` equals the unique union computed from the two features rows.
  - With `exclude_article_id=x.article_id`, `recent_articles` has 1 entry.
- `test_top_build_avoid_bundle_windows_and_status`
  - The same two articles.
  - Commit `UPDATE app.blog_articles SET created_at = <sc.now() − 31 days>` for `y` (test-only setup) → `len(recent_articles) == 1`.
  - Reset it, then set `y.status = "SUPERSEDED"` → `len(recent_articles) == 1`.
- `test_top_build_avoid_bundle_overused_phrases`: three graph articles with features (identical golden content) → `len(b.overused_phrases) == 20`, and every phrase's first and last word is not in `STOPWORDS`.
- `test_top_evaluate_diversity_identical_articles_fail`
  - `y`, then `x`, both with features recorded (golden content: same CTA, same opening text and embedding, same pattern and domains).
  - `ev = await diversity.evaluate_diversity(db, version_id=x.version_id, config=cfg)`.
  - Assert:
    - `ev.cta_fresh == GateResult(gate="cta_fresh", passed=False, severity="blocking", details=f"CTA similarity 1.00 >= 0.80 with article {y.article_id}")`;
    - `[w.gate for w in ev.warnings] == ["opening_diversity", "headline_diversity", "source_domain_diversity"]`;
    - `ev.warnings[0].passed is False` and `ev.warnings[0].details == f"opening similarity 1.00 >= 0.90 with article {y.article_id}"`;
    - `ev.warnings[1].passed is True` (uses 2 < 3) and `details == f"headline pattern {p} used 2 times in 7 days"`;
    - `ev.warnings[2].passed is True`.
- `test_top_evaluate_diversity_three_articles_warn_on_pattern_and_domain`: `z`, `y`, then `x` → `ev.warnings[1]` has `passed False`, `details == f"headline pattern {p} used 3 times in 7 days (limit 3)"`; `ev.warnings[2]` has `passed False` and `details` starting with `"primary source domain "` and containing `"used 3 times in 7 days (limit 3)"`.
- `test_top_evaluate_diversity_distinct_cta_and_opening_pass`
  - `y`, then `x`. Test setup commits `UPDATE app.blog_version_features SET cta_normalized='book a demo with our clinical team today'` for `y`'s version, and replaces `y`'s `opening` embedding with `vectors.e(7)` (delete and insert on TOP's table).
  - Assert:
    - `ev.cta_fresh.passed is True` with `details == f"max CTA similarity {m:.2f} across 1 recent articles"`, where `m = trigram_jaccard(<x cta_normalized>, "book a demo with our clinical team today")` and `m < 0.8`;
    - `ev.warnings[0].passed is True` and `ev.warnings[0].details.endswith("across 1 recent articles")`.
- `test_top_evaluate_diversity_windows`: `y`, then `x`; set `y.created_at = x.created_at − 8 days` → `ev.warnings[1].details == f"headline pattern {p} used 1 times in 7 days"` and `ev.cta_fresh.passed is False` (CTA comparison is not windowed). Set `y.created_at = x.created_at + 1 day` → `ev.cta_fresh.details == "max CTA similarity 0.00 across 0 recent articles"`.
- `test_top_evaluate_diversity_single_article_passes`: only `x` → `ev.cta_fresh.passed is True`, `details == "max CTA similarity 0.00 across 0 recent articles"`; all warnings passed.
- `test_top_evaluate_diversity_requires_features`: `x` without features → `LookupError(f"version features not recorded for {x.version_id}")`.

**Implementation notes.**
- Opening similarity reuses the TOP-5 pgvector pattern (`VersionEmbedding.embedding.cosine_distance(this_vector)`) over the other articles' current-version `opening` rows.
- Feature and embedding inserts use `insert(...).on_conflict_do_nothing(index_elements=["version_id"])` and `index_elements=["version_id", "kind"]`. These are full unique constraints, so no `index_where`.

**Verification.**
1. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_diversity_service.py` gives `NotImplementedError`.
2. Implement.
3. Green: 0 failed. The multi-article tests need the TOP-0 gate. TOP-LINT clean.

**Acceptance bullets covered:**
- §10.3 "Writer: … avoid bundle + recent articles inputs" (TOP `build_avoid_bundle`).
- §10.4 "Clinical Reviewer … and Editorial Reviewer (avoid bundle)" (TOP part).
- §10.4 "All 15 gates, … diversity checks" (gate 9 `cta_fresh` and the three diversity warnings).
- §4.5 PATCH step 2 and §5.6 `run_quality_gates` dependency (`record_version_features`).

---
### TOP-9: MDCopilot published-post sync — `sync_mdcopilot_posts`

**Files:**
- Modify `pkg/services/external_posts.py` (FOUND stub).
- Create `backend/fixtures/mock/mdcopilot_public_api/README.md`, `blogs_skip_0_limit_2.json`, `blogs_skip_2_limit_2.json` and `blogs_skip_0_limit_2_changed.json`.
- Create `backend/tests/topics/test_top_external_posts.py`.

**Interfaces.**
- Consumes `httpx` (0.28.1), `domain.headlines.classify_headline`, `domain.novelty.external_post_embedding_text`, `StepContext`, ORM `ExternalPost`, and `EffectiveConfig.site_url` (via `sc.config.site_url`).
- Produces (the first signature is frozen by §5.6):
```python
class SyncReport(BaseModel): enabled: bool; fetched: int; inserted: int; updated: int; embedded: int
async def sync_mdcopilot_posts(sc: StepContext, *, now: datetime) -> SyncReport

class ExternalPostsSyncError(RuntimeError): ...
class PublicBlogPost(BaseModel):   # model_config = ConfigDict(extra="ignore")
    id: str
    slug: Annotated[str, Field(min_length=1, max_length=200)]
    title: Annotated[str, Field(min_length=1)]
    excerpt: str | None = None
    published_at: datetime | None = None
    status: str | None = None
MAX_PAGES = 200
EMBED_BATCH_SIZE = 50
def build_public_api_client(settings: Settings) -> httpx.AsyncClient
async def sync_posts_with_client(sc: StepContext, *, now: datetime, client: httpx.AsyncClient) -> SyncReport
```

**Behaviour rules.**
1. **Disabled:** `sync_mdcopilot_posts` checks `sc.settings.mdcopilot_public_api_url`. When it is None or blank after `strip()`, it returns `SyncReport(enabled=False, fetched=0, inserted=0, updated=0, embedded=0)`, builds no client and touches no row.
2. **Enabled:** `async with build_public_api_client(sc.settings) as client: return await sync_posts_with_client(sc, now=now, client=client)`. The call goes through the module attribute, so tests can monkeypatch `external_posts.build_public_api_client`.
3. `build_public_api_client` returns `httpx.AsyncClient(timeout=httpx.Timeout(settings.fetch_read_timeout_seconds, connect=settings.fetch_connect_timeout_seconds), headers={"Accept": "application/json", "User-Agent": f"mdcopilot-blog/{settings.app_version}"}, follow_redirects=False)`.
4. `sync_posts_with_client`:
   1. `base = url.strip().rstrip("/")`. If `base` does not start with `http://` or `https://` → `ExternalPostsSyncError("BLOG_MDCOPILOT_PUBLIC_API_URL must be an http(s) URL")`. `origin = urlsplit(base).hostname`.
   2. **Paging:** `limit = sc.settings.mdcopilot_sync_page_size`, `skip = 0`. `GET f"{base}/blogs"` with `params={"skip": skip, "limit": limit}`.
      - A non-200 status → `ExternalPostsSyncError(f"GET /blogs skip={skip} returned {status}")`.
      - A body that is not a JSON array → `ExternalPostsSyncError(f"GET /blogs skip={skip} did not return a JSON array")`.
      - Each item is validated as `PublicBlogPost`. On failure → `ExternalPostsSyncError(f"invalid post at skip={skip} index={i}")`.
      - Items with `status` not None and not `"published"` are skipped.
      - Stop when a page has fewer than `limit` items, or after `MAX_PAGES` pages.
      - `httpx.HTTPError` propagates unchanged.
      - **No database write happens before every page has been fetched.**
   3. `fetched` = number of kept items. A slug seen again later in the same sync is ignored.
   4. **Per post:**
      - `excerpt = post.excerpt or ""`;
      - `published_at` naive → `replace(tzinfo=UTC)`;
      - `url = f"{sc.config.site_url.rstrip('/')}/blog/{slug}"`;
      - `content_hash = sha256(f"{title}\n{excerpt}".encode()).hexdigest()`;
      - `headline_pattern = classify_headline(title).value`;
      - `title` truncated to 300 characters, `external_id = post.id[:64]`.
   5. **Upsert** in one session by `(origin, slug)`:
      - New row → insert with `embedding=None`, `last_synced_at=now` (`inserted += 1`).
      - Existing row where any of `external_id, title, excerpt, url, published_at, headline_pattern, content_hash` differ → update those columns. When `content_hash` changed, also set `embedding=None` (`updated += 1`).
      - `last_synced_at = now` on every fetched row.
      - Rows not fetched are left untouched (P11).
      - Commit.
   6. **Embed:**
      - Rows with `origin == origin` and `embedding IS NULL`, ordered by `slug`, in batches of `EMBED_BATCH_SIZE`.
      - `vectors = await sc.gateway.embed([external_post_embedding_text(title=r.title, excerpt=r.excerpt) for r in batch], ctx=dataclasses.replace(sc.call, run_id=None, attempt_id=None))` (ruling D9).
      - Store each vector, commit per batch, `embedded += len(batch)`.
   7. Return `SyncReport(enabled=True, fetched, inserted, updated, embedded)`.
5. The code never calls any path other than `GET {base}/blogs`, and never sends credentials.
6. **Fixtures:**
   - `blogs_skip_0_limit_2.json`: two `BlogResponse` objects with every field (`id, title, slug, content, excerpt, featured_image, status: "published", author_id, author_name, created_at, updated_at, published_at` with a `+00:00` offset):
     - slugs `why-specialist-wait-times-keep-growing` and `the-agentic-shift-in-specialist-clinics`;
     - titles `Why specialist wait times keep growing` and `The agentic shift: what changes for specialist clinics`.
   - `blogs_skip_2_limit_2.json`: one object, slug `human-oversight-versus-full-autonomy`, title `Human oversight versus full autonomy`, `excerpt: null`, `published_at: "2026-08-01T09:00:00"` (naive on purpose).
   - `blogs_skip_0_limit_2_changed.json`: the same as page 1, except the first post's `excerpt` is `"Updated excerpt."`.
   - `README.md` says the pages are hand-built from `mdcopilot-backend/app/schemas/blog.py::BlogResponse` (read 2026-09-17) because `BLOG_MDCOPILOT_PUBLIC_API_URL` is not yet provided, and that no network call produced them.

**Tests to write FIRST** (`backend/tests/topics/test_top_external_posts.py`)

Setup: `sc = await mock_step_context()`; `sc_on = dataclasses.replace(sc, settings=sc.settings.model_copy(update={"mdcopilot_public_api_url": "https://api.mdcopilot.test/api/v1", "mdcopilot_sync_page_size": 2}))`; the handler below serves the fixture pages; `NOW = sc.now()`.

- `test_top_sync_disabled_makes_no_request`
  - `monkeypatch.setattr(external_posts, "build_public_api_client", <function raising AssertionError>)`.
  - `sync_mdcopilot_posts(sc, now=NOW)` → `SyncReport(enabled=False, fetched=0, inserted=0, updated=0, embedded=0)`, and the `blog_external_posts` count is 0.
  - The same with `mdcopilot_public_api_url="   "`.
- `test_top_sync_pages_inserts_and_embeds`
  - Monkeypatch `build_public_api_client` to return `httpx.AsyncClient(transport=httpx.MockTransport(handler))`, with the handler recording request URLs.
  - `report = await external_posts.sync_mdcopilot_posts(sc_on, now=NOW)`.
  - Assert:
    - `report == SyncReport(enabled=True, fetched=3, inserted=3, updated=0, embedded=3)`;
    - the recorded URLs are `["https://api.mdcopilot.test/api/v1/blogs?skip=0&limit=2", "https://api.mdcopilot.test/api/v1/blogs?skip=2&limit=2"]`;
    - the three rows have `origin == "api.mdcopilot.test"`;
    - the row `human-oversight-versus-full-autonomy` has `excerpt == ""`, `published_at == datetime(2026, 8, 1, 9, 0, tzinfo=UTC)`, `headline_pattern == "versus"`, `url == f"{sc.config.site_url.rstrip('/')}/blog/human-oversight-versus-full-autonomy"`;
    - the row `why-specialist-wait-times-keep-growing` has `headline_pattern == "why"` and `content_hash == sha256("Why specialist wait times keep growing\n<its excerpt>")`;
    - every `embedding` is non-null with 1536 floats;
    - `last_synced_at == NOW`;
    - the `blog_llm_calls` rows with `kind == "embedding"` number 1, with `run_id is None` and `attempt_id is None`.
- `test_top_sync_is_idempotent`: two syncs with unchanged pages → the second report is `SyncReport(enabled=True, fetched=3, inserted=0, updated=0, embedded=0)`; still 3 rows and 1 embedding call.
- `test_top_sync_updates_changed_post_and_reembeds`: sync once; then serve `blogs_skip_0_limit_2_changed.json` for skip 0 → the report is `SyncReport(enabled=True, fetched=3, inserted=0, updated=1, embedded=1)`; the first post has `excerpt == "Updated excerpt."`, a new `content_hash` and a non-null embedding differing from before.
- `test_top_sync_error_writes_nothing`: the handler returns 500 for skip 2 → `pytest.raises(ExternalPostsSyncError, match="GET /blogs skip=2 returned 500")`, and the `blog_external_posts` count is 0.
- `test_top_sync_rejects_non_array_and_invalid_items`: `{"detail": "x"}` → error `"did not return a JSON array"`; `[{"id": "1"}]` → error `"invalid post at skip=0 index=0"`.
- `test_top_sync_skips_unpublished_and_duplicate_slugs`: the handler returns a page with 2 items for skip 0, the second with `status: "draft"`, then `[]` for skip 2 → `fetched == 1`. A page repeating a slug → one row.
- `test_top_sync_rejects_non_http_url`: `mdcopilot_public_api_url="ftp://x"` with a client from the monkeypatched builder → `ExternalPostsSyncError("BLOG_MDCOPILOT_PUBLIC_API_URL must be an http(s) URL")`.
- `test_top_build_public_api_client_settings`: `client = build_public_api_client(sc.settings)` gives `client.timeout.read == sc.settings.fetch_read_timeout_seconds`, `client.timeout.connect == sc.settings.fetch_connect_timeout_seconds`, `client.headers["User-Agent"] == f"mdcopilot-blog/{sc.settings.app_version}"`, `client.follow_redirects is False`. Close it with `await client.aclose()`.

**Implementation notes.** Verified 2026-09-17 (httpx 0.28.1, `mdcopilot-blog-backend:dev`): an absolute URL with `params` produces `…/blogs?skip=0&limit=2`, and `httpx.MockTransport` serves `httpx.AsyncClient`.
```python
PAGES_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "mock" / "mdcopilot_public_api"

def handler(request: httpx.Request) -> httpx.Response:
    skip = int(request.url.params["skip"])
    limit = int(request.url.params["limit"])
    path = PAGES_ROOT / f"blogs_skip_{skip}_limit_{limit}.json"
    if not path.is_file():
        return httpx.Response(404, json={"detail": "not recorded"})
    return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
```

**Verification.**
1. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_external_posts.py` gives `NotImplementedError`.
2. Implement.
3. Green: 0 failed. TOP-LINT clean.

**Acceptance bullets covered:**
- §10.2 "`sync_mdcopilot_posts` read-only, paged, off while URL blank" (TOP primary; INT wires `maintenance.sync_posts`).
- §9 owner-input fallback for `BLOG_MDCOPILOT_PUBLIC_API_URL`.
- Ruling D9 (maintenance embeddings have `run_id NULL`).

---
### TOP-10: Topics API — schemas and read endpoints

**Files:**
- Modify `pkg/api/schemas_topics.py`, `pkg/api/routers/topics.py` (FOUND stubs).
- Create or modify `pkg/services/topics.py`.
- Create `backend/tests/topics/test_top_api_read.py` and `backend/tests/topics/test_top_api_committing.py`.

**Interfaces.**
- Consumes:
  - Phase 1: `api.deps`, `api.schemas.ApiModel`, `api.schemas.Page`, `errors.ProblemError`.
  - FOUND: `api.schemas_common.SourceRefOut`, `services.config.load_effective_config`, `services.step_context.build_api_step_context`.
  - TOP: `services.novelty.nearest_neighbours`, `domain.novelty.round_shortfall`, `domain.diversity` (`count_repeated_phrases`, `domain_shares`), `domain.novelty.NON_LIVE_ARTICLE_STATUSES`.
- Produces schemas (`api/schemas_topics.py`; every model extends `ApiModel`; field names and types exactly as in §4.4):
```python
class TopicCandidateOut(ApiModel):
    id: uuid.UUID; run_id: uuid.UUID; round: int; position: int; title: str; hook: str; why_now: str; thesis: str; angle: str
    core_argument: str; mdcopilot_connection: str; target_audience: str; pillar: PillarKey; relevant_news: list[NewsRef]
    sources: list[SourceRefOut]; examples: list[str]
    novelty_score: float | None; evidence_score: float | None; business_relevance: float | None; editorial_potential: float | None
    timeliness_score: float | None; audience_relevance: float | None; total_score: float | None
    score_breakdown: dict[str, ScoreItem]; novelty: NoveltyResult | None; status: CandidateStatus; is_manual: bool
    selected_at: datetime | None; selected_by: uuid.UUID | None; rejected_reason: str | None; article_id: uuid.UUID | None
    created_at: datetime; updated_at: datetime
class TopicRoundOut(ApiModel):
    run_id: uuid.UUID; run_status: RunStatus; round: int; rounds_available: list[int]; shortfall: bool; items: list[TopicCandidateOut]
class TopicsGenerateRequest(ApiModel): run_id: uuid.UUID
class TopicSelectRequest(ApiModel): confirm_warning: bool = False
class TopicUpdate(ApiModel):
    title: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    hook: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    why_now: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    thesis: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    angle: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    core_argument: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    target_audience: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    pillar: PillarKey | None = None
    # model_validator(mode="after"): at least one field is not None, else ValueError("at least one field must be provided")
class TopicHistoryOut(ApiModel):
    id: uuid.UUID; title: str; pillar: PillarKey; thesis: str; core_argument: str; headline_pattern: HeadlinePattern
    keywords: list[str]; examples: list[str]; primary_source_url: str | None; article_id: uuid.UUID | None
    article_status: ArticleStatus | None; created_at: datetime
class ExternalPostOut(ApiModel):
    id: uuid.UUID; origin: str; slug: str; title: str; excerpt: str; url: str; published_at: datetime | None
    headline_pattern: HeadlinePattern; last_synced_at: datetime
class SimilarityOut(ApiModel): text: str; items: list[NoveltyNeighbour]
class PillarCountOut(ApiModel): pillar: PillarKey; count: int
class DomainShareOut(ApiModel): domain: str; count: int; share: float
class PhraseCountOut(ApiModel): phrase: str; count: int
class DiversityPanelOut(ApiModel):
    days: int; pillar_mix: list[PillarCountOut]; source_domain_concentration: list[DomainShareOut]; top_repeated_phrases: list[PhraseCountOut]
```
- Produces services (`services/topics.py`):
```python
DEFAULT_PAGE_SIZE = 20; MAX_PAGE_SIZE = 100; DIVERSITY_PANEL_LIMIT = 20
async def to_candidate_out(db: AsyncSession, rows: Sequence[TopicCandidateRecord]) -> list[TopicCandidateOut]
async def get_topic_round(db: AsyncSession, *, settings: Settings, run_id: uuid.UUID | None, round_no: int | None,
                          status: CandidateStatus | None) -> TopicRoundOut
async def list_topic_history(db: AsyncSession, *, q: str | None, limit: int, offset: int) -> Page[TopicHistoryOut]
async def list_external_posts(db: AsyncSession, *, limit: int, offset: int) -> Page[ExternalPostOut]
async def similar_topics(db: AsyncSession, *, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession], text: str,
                         limit: int) -> SimilarityOut
async def diversity_panel(db: AsyncSession, *, days: int, now: datetime) -> DiversityPanelOut
```
- Routes (router prefix `/api/blog-agent`; static paths are declared before `/topics/{candidate_id}` routes):

| Method | Path | Permission | Parameters | Response |
|---|---|---|---|---|
| GET | `/topics` | VIEW | `run_id: Annotated[uuid.UUID \| None, Query(alias="runId")] = None`, `round_no: Annotated[int \| None, Query(alias="round", ge=1)] = None`, `status: CandidateStatus \| None = None` | `TopicRoundOut` |
| GET | `/topics/history` | VIEW | `q: str \| None = None`, `limit: Annotated[int, Query(ge=1)] = 20`, `offset: Annotated[int, Query(ge=0)] = 0` | `Page[TopicHistoryOut]` |
| GET | `/topics/external-posts` | VIEW | `limit`, `offset` as above | `Page[ExternalPostOut]` |
| GET | `/topics/similar` | VIEW | `text: Annotated[str, Query(min_length=3, max_length=1000)]`, `limit: Annotated[int, Query(ge=1, le=20)] = 5`, `request: Request` | `SimilarityOut` |
| GET | `/topics/diversity` | VIEW | `days: Annotated[int, Query(ge=1, le=90)] = 30` | `DiversityPanelOut` |

**Behaviour rules.**
1. `to_candidate_out`:
   - `sources` are `SourceRefOut(id, marker=None, title, url, publisher, domain, tier, published_at, access_mode)` built from `LedgerSource` rows in each row's `source_ids` order; ids without a row are skipped (P16).
   - `article_id` is the newest `blog_articles.id` (by `created_at DESC, id DESC`) with `candidate_id` equal to the row id, of any status, else None.
   - `pillar = PillarKey(row.pillar_key)`; `relevant_news` validated with `NewsRef`; `score_breakdown` values with `ScoreItem`; `novelty` with `NoveltyResult` or None.
   - Batch queries: one for sources, one for articles.
2. `get_topic_round`:
   1. When `run_id` is None, pick the newest `BlogRun` (by `created_at DESC, id DESC`) with at least one candidate. None exists → `ProblemError(404, "Run not found", "no run has topic candidates yet")`.
   2. When `run_id` is given and there is no such run → `ProblemError(404, "Run not found", f"no run with id {run_id}")`.
   3. `rounds_available` = the distinct candidate rounds of the run, ascending. When it is empty → `TopicRoundOut(run_id, run_status, round=0, rounds_available=[], shortfall=False, items=[])` (P12).
   4. `round = round_no if round_no is not None else max(rounds_available)`.
   5. `shortfall = round == max(rounds_available) and round_shortfall(statuses=<all statuses of that round>, round_no=round, max_regeneration_rounds=(await load_effective_config(db, settings, run_id=run.id)).novelty.max_regeneration_rounds)`. A requested round that is not the newest always gives `False`.
   6. `items` = the candidates of that round ordered by `position`, filtered by `status` when given.
3. `list_topic_history`:
   - `Topic` rows ordered by `created_at DESC, id DESC`.
   - `q` (stripped, non-empty) filters `title ILIKE p OR thesis ILIKE p OR core_argument ILIKE p`, where `p = "%" + escaped + "%"` and `escaped` replaces `\` with `\\`, `%` with `\%` and `_` with `\_`, with `escape="\\"`.
   - `limit` is capped at `MAX_PAGE_SIZE`.
   - `article_id`/`article_status` come from the newest article with `topic_id` equal to the topic id.
4. `list_external_posts`: ordered by `published_at DESC NULLS LAST, id DESC`, with the same cap.
5. `similar_topics`:
   - `stripped = text.strip()`. `len(stripped) < 3` → `ProblemError(422, "Request validation failed", "text must contain at least 3 non-space characters")`.
   - `sc = await build_api_step_context(settings=settings, sessionmaker=sessionmaker, run_id=None, article_id=None)`.
   - `[vector] = await sc.gateway.embed([stripped], ctx=sc.call)`: `run_id` is None and the trace id is fresh (ruling D9).
   - `items = await novelty.nearest_neighbours(db, embedding=vector, limit=limit)`.
   - Return `SimilarityOut(text=stripped, items=items)`.
   - The router passes `request.app.state.sessionmaker`.
6. `diversity_panel` uses the live articles with `created_at >= now − days days`:
   - `pillar_mix` = one `PillarCountOut` per `PillarKey` member, in enum order, counting those articles by `pillar_key` (zeros included).
   - `source_domain_concentration` = `domain_shares([LedgerSource.domain for every ArticleSource row of those articles' current versions], limit=DIVERSITY_PANEL_LIMIT)` mapped to `DomainShareOut`.
   - `top_repeated_phrases` = `count_repeated_phrases([strip_citation_markers(v.content_markdown) for their current versions], min_words=3, max_words=5, min_count=3, limit=DIVERSITY_PANEL_LIMIT)` mapped to `PhraseCountOut`. The panel uses the §5.4 `DiversityConfig` defaults as constants, because the endpoint has no config parameter.
   - The router passes `now=utcnow()`.
7. Every route depends on `require_permission(Permission.VIEW)`. The GET routes write no audit rows.

**Tests to write FIRST.**

`backend/tests/topics/test_top_api_read.py` (`client`, `login_as`, `db_session`, TOP-0 factories). `KEYS_CANDIDATE` is the set of camelCase names of `TopicCandidateOut`.
- `test_top_get_topics_defaults_to_newest_run_and_round`
  - Setup: run A (`make_research_graph`) with round 1 candidates; run B, created later, with rounds 1 and 2. Test setup sets `blog_runs.created_at` of A to `now − 1 day`.
  - Viewer `GET /api/blog-agent/topics` → 200 with `body["runId"] == str(B.run_id)`, `body["round"] == 2`, `body["roundsAvailable"] == [1, 2]`, `[i["position"] for i in body["items"]] == [0, 1, 2]`, `set(body["items"][0]) == KEYS_CANDIDATE` and `body["runStatus"]` equal to B's status.
- `test_top_get_topics_explicit_run_round_and_status_filter`: `?runId=<A>&round=1&status=PASSED`, where A's round 1 has `PASSED`, `REJECTED`, `PASSED` → 2 items, positions `[0, 2]`.
- `test_top_get_topics_candidate_payload`
  - Candidate with `source_ids=g.source_ids[:2]`, `novelty=NoveltyResult(decision=WARN, max_similarity=0.82, neighbours=[NoveltyNeighbour(kind="external_post", ref_id="p1", title="Old", similarity=0.82)])`, `total_score=0.61`.
  - Assert:
    - `item["sources"][0]` has keys `{"id", "marker", "title", "url", "publisher", "domain", "tier", "publishedAt", "accessMode"}` and `marker is None`;
    - `item["novelty"]["neighbours"][0] == {"kind": "external_post", "refId": "p1", "title": "Old", "similarity": 0.82}`;
    - `item["totalScore"] == 0.61`;
    - `item["articleId"] is None`.
- `test_top_get_topics_article_id_from_graph`: `a = make_article_graph(db_session)` → `GET ?runId=<a.run_id>` gives the item with id `a.candidate_id` and `articleId == str(a.article_id)`.
- `test_top_get_topics_shortfall_flag`: run with round 3 statuses `PASSED`, `REJECTED`, `REJECTED` → `shortfall is True`; `?round=2` on a run with rounds 2 and 3 → `shortfall is False`.
- `test_top_get_topics_run_without_candidates`: `make_research_graph` only → `GET ?runId=<run>` gives 200, `{"runId": str(g.run_id), "runStatus": <that run's status>, "round": 0, "roundsAvailable": [], "shortfall": False, "items": []}`.
- `test_top_get_topics_not_found`: `?runId=<uuid4>` → 404, `title == "Run not found"`. With no candidates at all → 404, `detail == "no run has topic candidates yet"`.
- `test_top_get_topics_validation`: `?round=0` → 422; `?status=NOPE` → 422.
- `test_top_topics_history_order_query_and_article`
  - Topics `T_old` (`created_at = now − 2 days`, thesis `"Referral backlog math"`) and `T_new` (`now`); `a = make_article_graph(db_session)` (its topic is created now).
  - `GET /topics/history` → `total == 3`, `body["items"][-1]["id"] == str(T_old.id)`, and the `createdAt` values are non-increasing.
  - `?q=backlog` → `[T_old]`. `?q=%` → `total == 0`.
  - The graph topic's item has `articleId == str(a.article_id)` and `articleStatus == "READY_FOR_REVIEW"`.
  - `?limit=500` → `body["limit"] == 100`.
- `test_top_external_posts_order_and_paging`: posts with `published_at` of `now − 1 day`, `now − 3 days` and `None` → the order is `[1 day, 3 days, None]`; `?limit=1&offset=1` returns the 3-day post with `total == 3`.
- `test_top_diversity_panel`
  - Two graph articles (TOP-0 gate), then `GET /topics/diversity`.
  - Assert:
    - `body["days"] == 30`;
    - `[p["pillar"] for p in body["pillarMix"]] == ["A", "B", "C", "D", "E", "NARRATIVE"]` and `sum(p["count"] for p in body["pillarMix"]) == 2`;
    - `sum(d["share"] for d in body["sourceDomainConcentration"]) == pytest.approx(1.0, abs=0.001)`;
    - every `count` is even (identical articles);
    - `len(body["topRepeatedPhrases"]) <= 20`.
  - `?days=0` → 422; `?days=91` → 422.
- `test_top_read_routes_require_session`, parametrized over the five paths (`/topics`, `/topics/history`, `/topics/external-posts`, `/topics/similar?text=abc`, `/topics/diversity`) with anonymous `client` → 401. Every role holds `blog.view`, so no role can get 403 on these routes and there is no 403 case.

`backend/tests/topics/test_top_api_committing.py` (`committing_client`, `committing_login_as`, `sessionmaker_committing`, `mock_step_context`)
- `test_top_similar_embeds_without_run_and_ranks`
  - Commit an external post `P` with `embedding=mock_embedding("prior authorisation delays", 1536)` and a topic `T` with `embedding=vectors.e(0)`.
  - Viewer `GET /api/blog-agent/topics/similar?text=%20prior%20authorisation%20delays%20&limit=2` → 200.
  - Assert:
    - `body["text"] == "prior authorisation delays"`;
    - `body["items"][0]["refId"] == str(P.id)`, with `kind "external_post"` and `similarity == pytest.approx(1.0, abs=1e-6)`;
    - `len(body["items"]) == 2`;
    - exactly one new `blog_llm_calls` row with `kind == "embedding"`, `run_id is None`, `len(trace_id) == 32`.
- `test_top_similar_validation`: `text=ab` → 422; `text=%20%20%20` → 422 with `detail == "text must contain at least 3 non-space characters"`; `limit=21` → 422.
- `test_top_near_duplicate_external_post_shown_in_get_topics`
  - `sc = await mock_step_context(agents=["ideation"])`; research graph for `sc.call.run_id` (committed).
  - `ideate_topics(round_no=1)`; commit the near-duplicate external post for candidate 0 exactly as in TOP-6; `check_novelty_and_score`.
  - Viewer `GET /api/blog-agent/topics?runId=<sc.call.run_id>` → `items[0]["status"] == "REJECTED"`, `items[0]["novelty"]["decision"] == "REJECT_TOPIC"`, `items[0]["novelty"]["neighbours"][0]["kind"] == "external_post"`, `["title"] == "Existing MDCopilot post"`, `["similarity"] >= 0.85`, and `items[0]["noveltyScore"] == pytest.approx(1 - items[0]["novelty"]["maxSimilarity"], abs=1e-6)`.

**Implementation notes.**
- The router follows Phase 1 `routers/runs.py`: `CanView = Annotated[Principal, Depends(require_permission(Permission.VIEW))]`.
- FastAPI treats `Query(alias="round")` on a parameter named `round_no` as the wire name `round`.

**Verification.**
1. Red: run both files; expect failures (404/405 from the empty router, ImportError on services).
2. Implement.
3. Green:
```bash
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_api_read.py tests/topics/test_top_api_committing.py tests/api/test_rbac_routes.py
```
Expected: 0 failed. TOP-LINT clean.

**Acceptance bullets covered:**
- §10.2 "Seeded near-duplicate external post rejected, neighbour and similarity shown" (`GET /topics` half).
- "UI Today's Ideas cards, Topics page" (TOP API).
- §10.5 "Dashboard … diversity panel" (TOP `/topics/diversity`).
- §10.8 / ruling D9 (`GET /topics/similar` embeddings with `run_id NULL`).
- §8.3 route test rules (success, 401, problem responses).

---
### TOP-11: Topics API — mutations (generate, select with compensation, edit, reject)

**Files:**
- Modify `pkg/api/routers/topics.py` and `pkg/services/topics.py`.
- Create `backend/tests/topics/test_top_api_mutations.py` and `backend/tests/topics/test_top_api_select_compensation.py`.

**Interfaces.**
- Consumes:
  - FOUND `services.enqueue` (`ensure_agent_enabled`, `enqueue_workflow`), `api.schemas_common` (`ActionAccepted`, `ReasonRequest`) and `workflows.names` constants;
  - Phase 1 `services.audit.audit`;
  - TOP-7 `topic_steps.promote_candidate` (called through the module attribute);
  - TOP-10 `to_candidate_out`.
- Produces services:
```python
CANDIDATE_ENTITY = "blog_topic_candidate"
RUN_ENTITY = "blog_run"
REGENERATE_BLOCKED_RUN_STATUSES = frozenset({"QUEUED", "RESEARCHING", "PRODUCING", "CANCELLED"})
async def regenerate_topics(db: AsyncSession, client: WorkflowClientProtocol, *, settings: Settings, principal: Principal,
                            run_id: uuid.UUID) -> ActionAccepted
async def select_candidate(db: AsyncSession, client: WorkflowClientProtocol, *, settings: Settings, principal: Principal,
                           candidate_id: uuid.UUID, confirm_warning: bool) -> ActionAccepted
async def update_candidate(db: AsyncSession, *, principal: Principal, candidate_id: uuid.UUID, body: TopicUpdate,
                           now: datetime) -> TopicCandidateOut
async def dismiss_candidate(db: AsyncSession, *, principal: Principal, candidate_id: uuid.UUID, reason: str) -> TopicCandidateOut
```
- Routes:

| Method | Path | Permission | Body | Response |
|---|---|---|---|---|
| POST | `/topics/generate` | GENERATE | `TopicsGenerateRequest` | 202 `ActionAccepted` |
| POST | `/topics/{candidate_id}/select` | GENERATE | `TopicSelectRequest` | 202 `ActionAccepted` |
| PATCH | `/topics/{candidate_id}` | EDIT | `TopicUpdate` | `TopicCandidateOut` |
| POST | `/topics/{candidate_id}/reject` | EDIT | `ReasonRequest` | `TopicCandidateOut` |

**Behaviour rules — `regenerate_topics`** (checks run in this order).
1. `enqueue.ensure_agent_enabled(settings)` → 409 `Agent disabled`.
2. `SELECT … FOR UPDATE` the `BlogRun`. Missing → 404 `Run not found`, `f"no run with id {run_id}"`.
3. `run.status in REGENERATE_BLOCKED_RUN_STATUSES` → 409 `Topics cannot be regenerated`, detail `f"run is {run.status}"`. This covers Rule B's CANCELLED rejection.
4. Any `blog_articles` row of the run with `status in APPROVED_OR_LATER_STATUSES` → 409 `Topics cannot be regenerated`, detail `f"article {article.id} is {article.status}"`, for the first such article by `created_at`.
5. `workflow_id = f"regen-topics-{run.id}-{uuid7()}"`. Then `audit(db, actor_user_id=principal.user_id, action="topics.regenerate", entity_type=RUN_ENTITY, entity_id=str(run.id), details={"workflow_id": workflow_id, "run_status": run.status})` and `await db.commit()`.
6. `parts = await enqueue.enqueue_workflow(client, workflow_name=WORKFLOW_REGENERATE_TOPICS, queue_name=QUEUE_INTERACTIVE, workflow_id=workflow_id, args=(str(run.id),), timeout_seconds=settings.discovery_timeout_minutes * 60)`. A failure raises 503 `Workflow service unavailable` inside `enqueue_workflow`; nothing needs compensating.
7. Return `ActionAccepted(workflow_id=parts.workflow_id, workflow_name=parts.workflow_name, queue=parts.queue, run_id=run.id, article_id=None, candidate_id=None)`.

**Behaviour rules — `select_candidate`** (the §4.4 select sequence; checks run in this order).
1. `ensure_agent_enabled(settings)` → 409 `Agent disabled`.
2. `SELECT … FOR UPDATE` the candidate. Missing → 404 `Topic not found`, `f"no topic candidate with id {candidate_id}"`.
3. Load the run. `run.status == "CANCELLED"` → 409 `Topic cannot be selected`, `"run is CANCELLED"`.
4. `status == "REJECTED"` → 409 `Topic rejected by novelty`, `f"candidate {id} was rejected by the novelty check"`.
5. `status in {"SELECTED", "DISMISSED", "SUPERSEDED", "PROPOSED"}` → 409 `Topic cannot be selected`, `f"candidate is {status}"` (P13).
6. Load the live articles of the run (`status NOT IN NON_LIVE_ARTICLE_STATUSES`), ordered by `created_at DESC, id DESC`. Any with `status in APPROVED_OR_LATER_STATUSES` → 409 `Topic cannot be selected`, `f"article {id} is {status}"`.
7. `status == "WARNED" and not confirm_warning` → 409 `Topic needs confirmation`, `f"candidate {id} has a novelty warning; resend with confirmWarning true"`.
8. Choose the workflow. Let `live` be the newest live article, or None.
   - `live is None` → `WORKFLOW_PRODUCE_ARTICLE`, `QUEUE_PIPELINE`, `workflow_id = f"produce-{run.id}-{candidate.id}"`.
   - Otherwise → `WORKFLOW_CHANGE_TOPIC`, `QUEUE_INTERACTIVE`, `f"change-topic-{run.id}-{candidate.id}"`.
   - `args = (str(run.id), str(candidate.id))`, `timeout_seconds = settings.production_timeout_minutes * 60`.
9. `previous_status = candidate.status`. Then `topic_id = await topic_steps.promote_candidate(db, candidate_id=candidate.id, selected_by=principal.user_id)`.
10. `audit(…, action="topic.select", entity_type=CANDIDATE_ENTITY, entity_id=str(candidate.id), details={"run_id": run.id, "topic_id": topic_id, "workflow_name": …, "workflow_id": …, "previous_status": previous_status, "confirm_warning": confirm_warning})`, then `await db.commit()`.
11. Enqueue via `enqueue.enqueue_workflow(...)`. On `ProblemError` with status 503, run the **compensating transaction** on `db`, then re-raise the same exception:
    1. `SELECT … FOR UPDATE` the candidate;
    2. `status = previous_status`, `selected_by = None`, `selected_at = None`;
    3. `DELETE FROM blog_topics WHERE id = topic_id AND candidate_id = candidate.id`;
    4. commit.
    No audit row is added (open question 6).
12. Return `ActionAccepted(workflow_id, workflow_name, queue, run_id=run.id, article_id=live.id if live else None, candidate_id=candidate.id)`.

**Behaviour rules — `update_candidate` and `dismiss_candidate`.**
1. **Update:**
   - Lock the candidate. Missing → 404 `Topic not found`.
   - `status in {"SELECTED", "SUPERSEDED"}` → 409 `Topic cannot be edited`, `f"candidate is {status}"`.
   - Apply every non-None field (`pillar` → `pillar_key = pillar.value`), then `edited_by = principal.user_id`, `edited_at = now`.
   - Novelty, embeddings and scores are not touched (P1).
   - `audit(action="topic.update", entity_type=CANDIDATE_ENTITY, entity_id=…, details={"fields": <sorted snake_case names of provided fields>})`, commit.
   - Return `(await to_candidate_out(db, [row]))[0]`.
   - An empty body is rejected with 422 by `TopicUpdate`'s validator (P14).
2. **Dismiss:**
   - Lock. Missing → 404 `Topic not found`.
   - `status == "SELECTED"` → 409 `Topic cannot be rejected`, `"candidate is SELECTED"`.
   - Otherwise `previous = status`, `status = "DISMISSED"`, `rejected_reason = reason` (already stripped and validated by `ReasonRequest`).
   - `audit(action="topic.reject", entity_type=CANDIDATE_ENTITY, entity_id=…, reason=reason, details={"previous_status": previous})`, commit.
   - Return `TopicCandidateOut` (P15).
3. The router passes `now=utcnow()` to update and never catches `ProblemError`.

**Tests to write FIRST.**

`backend/tests/topics/test_top_api_mutations.py` (`client`, `login_as`, `db_session`, `fake_workflow_client`, `settings`, `app`, TOP-0 factories). An autouse fixture sets `app.state.settings = settings.model_copy(update={"agent_enabled": True})`, as in Phase 1 `test_runs_api.py`. `BASE = "/api/blog-agent/topics"`.

*Generate*
- `test_top_generate_enqueues_regenerate_topics`
  - `g = make_research_graph(db_session)`; set run status `WAITING_FOR_TOPIC`; editor POST `BASE + "/generate"` with `{"runId": str(g.run_id)}` and the CSRF header.
  - Assert:
    - 202 with `set(body) == {"workflowId", "workflowName", "queue", "runId", "articleId", "candidateId"}`, `body["workflowName"] == "regenerate_topics"`, `body["queue"] == "interactive"`, `body["articleId"] is None`;
    - `fake_workflow_client.enqueued` has one `EnqueueCall` with `workflow_name == "regenerate_topics"`, `queue_name == "interactive"`, `workflow_id` starting with `f"regen-topics-{g.run_id}-"` and equal to `body["workflowId"]`, `args == (str(g.run_id),)`, `timeout_seconds == settings.discovery_timeout_minutes * 60`;
    - one `audit_log` row with `action == "topics.regenerate"`, `entity_type == "blog_run"`, `entity_id == str(g.run_id)` and `details["workflow_id"] == body["workflowId"]`.
- `test_top_generate_run_status_rules`, parametrized:
  - 409 for `QUEUED`, `RESEARCHING`, `PRODUCING`, `CANCELLED`, each with `title == "Topics cannot be regenerated"`, `detail == f"run is {status}"` and nothing enqueued;
  - 202 for `TOPICS_READY`, `WAITING_FOR_TOPIC`, `SUCCEEDED`, `FAILED`.
- `test_top_generate_blocked_by_approved_article`: `a = make_article_graph(db_session, status=APPROVED, approved=True)`, run status `SUCCEEDED` → 409 with `detail == f"article {a.article_id} is APPROVED"`. With `status=READY_FOR_REVIEW` instead → 202.
- `test_top_generate_errors`:
  - unknown `runId` → 404 `Run not found`;
  - body `{}` → 422;
  - `agent_enabled=False` → 409 `Agent disabled`;
  - `fake_workflow_client.enqueue_error = RuntimeError("down")` → 503 `Workflow service unavailable`;
  - viewer → 403 with `detail == "missing permission blog.generate"`;
  - anonymous → 401.

*Select*
- `test_top_select_passed_without_live_article_enqueues_production`
  - `g = make_research_graph(db_session)`, run `WAITING_FOR_TOPIC`, `c = make_candidate(run_id=g.run_id, status=PASSED)`; editor POST `f"{BASE}/{c.id}/select"` with `{}`.
  - Assert:
    - 202 with `workflowName == "produce_article"`, `queue == "pipeline"`, `workflowId == f"produce-{g.run_id}-{c.id}"`, `articleId is None`, `candidateId == str(c.id)`;
    - `EnqueueCall.args == (str(g.run_id), str(c.id))` and `timeout_seconds == settings.production_timeout_minutes * 60`;
    - `c.status == "SELECTED"`, `c.selected_by` equals the editor's user id;
    - one `Topic` with `candidate_id == c.id`;
    - one `topic.select` audit row with `details["previous_status"] == "PASSED"`.
- `test_top_select_with_live_article_enqueues_change_topic`, parametrized over live statuses `READY_FOR_REVIEW`, `QUALITY_GATE_FAILED`, `FAILED`:
  - `a = make_article_graph(db_session, status=s)`; `c = make_candidate(run_id=a.run_id, round_no=2, status=PASSED)`.
  - → 202 with `workflowName == "change_topic"`, `queue == "interactive"`, `workflowId == f"change-topic-{a.run_id}-{c.id}"`, `articleId == str(a.article_id)`.
- `test_top_select_ignores_non_live_articles`, parametrized over `SUPERSEDED`, `REJECTED`: the graph article in that status → `workflowName == "produce_article"`.
- `test_top_select_blocked_by_approved_article`: `make_article_graph(status=PUBLISHED, approved=True)` plus a PASSED candidate → 409 `Topic cannot be selected` with `detail == f"article {a.article_id} is PUBLISHED"`; the candidate stays `PASSED`.
- `test_top_select_status_rules`, parametrized:

  | Status | Response |
  |---|---|
  | `REJECTED` | 409 `Topic rejected by novelty` |
  | `SELECTED` | 409 `Topic cannot be selected`, detail `"candidate is SELECTED"` |
  | `DISMISSED` | 409 `Topic cannot be selected` |
  | `SUPERSEDED` | 409 `Topic cannot be selected` |
  | `PROPOSED` | 409 `Topic cannot be selected` |

  Each case: nothing enqueued and no topic row.
- `test_top_select_warned_requires_confirmation`: WARNED with `{}` → 409 `Topic needs confirmation`, `detail == f"candidate {c.id} has a novelty warning; resend with confirmWarning true"`. `{"confirmWarning": true}` → 202, and the audit `details["confirm_warning"] is True`.
- `test_top_select_cancelled_run`: run `CANCELLED` with a PASSED candidate → 409 `Topic cannot be selected`, `detail == "run is CANCELLED"`.
- `test_top_select_errors`: unknown id → 404 `Topic not found`; `agent_enabled=False` → 409 `Agent disabled`; viewer → 403; anonymous → 401.

*Edit*
- `test_top_patch_updates_fields`
  - Editor PATCH `{"title": "New title", "pillar": "C"}` on a REJECTED candidate carrying `novelty` → 200.
  - Assert:
    - `body["title"] == "New title"`, `body["pillar"] == "C"`, `body["status"] == "REJECTED"`, and `body["novelty"]` equals the stored novelty (unchanged);
    - the row has `edited_by == <editor id>` and `edited_at` not None;
    - audit `topic.update` with `details == {"fields": ["pillar", "title"]}`.
- `test_top_patch_rules`:
  - SELECTED → 409 `Topic cannot be edited`; SUPERSEDED → 409;
  - `{}` → 422; `{"title": ""}` → 422; `{"title": "x" * 301}` → 422; `{"unknown": 1}` → 422;
  - unknown id → 404 `Topic not found`;
  - viewer → 403 `missing permission blog.edit`; anonymous → 401.

*Reject*
- `test_top_reject_dismisses_with_reason`: editor POST `/reject` with `{"reason": "  Off brand  "}` on a PASSED candidate → 200 with `body["status"] == "DISMISSED"` and `body["rejectedReason"] == "Off brand"`; audit `topic.reject` with `reason == "Off brand"` and `details == {"previous_status": "PASSED"}`.
- `test_top_reject_rules`:
  - SELECTED → 409 `Topic cannot be rejected`;
  - SUPERSEDED → 200 `DISMISSED`;
  - `{"reason": "   "}` → 422;
  - unknown id → 404;
  - viewer → 403 `missing permission blog.edit`; anonymous → 401.

`backend/tests/topics/test_top_api_select_compensation.py` (`committing_client`, `committing_login_as`, `sessionmaker_committing`, `fake_workflow_client`)
- `test_top_select_enqueue_failure_restores_committed_rows`, parametrized over `(PASSED, False)` and `(WARNED, True)`
  - In a committing session: `make_research_graph`, run `WAITING_FOR_TOPIC`, a candidate with the given status; commit.
  - `fake_workflow_client.enqueue_error = RuntimeError("down")`.
  - Editor POST `/select` with `{"confirmWarning": <flag>}`.
  - Assert:
    - 503, `title == "Workflow service unavailable"`, `detail == "produce_article was not enqueued"`;
    - in a new `sessionmaker_committing()` session, the candidate `status` equals the original status, `selected_by is None`, `selected_at is None`;
    - `SELECT count(*) FROM app.blog_topics WHERE candidate_id = :id` returns 0;
    - exactly one `audit_log` row with `action == "topic.select"`.
- `test_top_select_success_commits_before_enqueue`: without an enqueue error, a separate committing session sees the candidate `SELECTED` and one topic row. This proves commit-then-enqueue (§5.5 rule 7).

**Implementation notes.** The routers follow Phase 1 `routers/runs.py`:
- `CanGenerate = Annotated[Principal, Depends(require_permission(Permission.GENERATE))]`;
- `CanEdit = Annotated[Principal, Depends(require_permission(Permission.EDIT))]`;
- `@router.post("/topics/generate", status_code=202)`.

**Verification.**
1. Red: run both files; expect 405/404 and assertion failures.
2. Implement.
3. Green:
```bash
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_api_mutations.py tests/topics/test_top_api_select_compensation.py tests/api/test_rbac_routes.py
```
Expected: 0 failed. TOP-LINT clean.

**Acceptance bullets covered:**
- §10.2 "`POST /topics/generate` → 3 new candidates not repeating the previous round" (TOP intake with `FakeWorkflowClient`; INT covers the workflow end to end).
- "Manual mode stops at `WAITING_FOR_TOPIC`; selecting enqueues production" (TOP select enqueue).
- §4.4 select sequence and compensation.
- Rule B API half (CANCELLED rejected by select and generate).
- §8.3 route rules (success, 401, 403, problem titles); §4.0 audit actions `topics.regenerate`, `topic.select`, `topic.update`, `topic.reject`.

---
### TOP-12: OpenAPI shape check against the frozen shape file

**Files:**
- Create `backend/tests/topics/test_top_openapi.py`.

**Interfaces.**
- Consumes `backend/tests/api_shapes.json` (FOUND, frozen) and the `app` fixture (`app.openapi()`).
- Produces nothing in `src`.

**Behaviour rules.**
1. Models checked are exactly these twelve: `TopicCandidateOut`, `TopicRoundOut`, `TopicsGenerateRequest`, `TopicSelectRequest`, `TopicUpdate`, `TopicHistoryOut`, `ExternalPostOut`, `SimilarityOut`, `PillarCountOut`, `DomainShareOut`, `PhraseCountOut`, `DiversityPanelOut`.
2. Component lookup:
   - Use `components.schemas[name]`.
   - If absent, use `f"{name}-Output"` for the nine response models or `f"{name}-Input"` for `TopicsGenerateRequest`, `TopicSelectRequest` and `TopicUpdate`.
   - If still absent, the test fails naming the model.
3. `props = sorted(component["properties"])`. `nullable` = the sorted property names whose schema has `anyOf` containing `{"type": "null"}`.
4. A mismatch is never fixed by editing `api_shapes.json`, which is frozen. Either the TOP schema is wrong (fix it) or the shape file is wrong (file `Request: tests/api_shapes.json <Model> props/nullable differ from CONTRACT §4.4: <diff>` in `requests/top.md`).

**Tests to write FIRST** (`backend/tests/topics/test_top_openapi.py`).
- `test_top_openapi_models_match_shape_file`, parametrized over the twelve names: `shapes = json.loads((Path(__file__).resolve().parents[1] / "api_shapes.json").read_text())`, then assert `props == shapes[name]["props"]` and `nullable == shapes[name]["nullable"]`.
- `test_top_openapi_paths_present`: `app.openapi()["paths"]` contains:
  - `/api/blog-agent/topics` (`get`);
  - `/api/blog-agent/topics/generate` (`post`);
  - `/api/blog-agent/topics/{candidate_id}/select` (`post`);
  - `/api/blog-agent/topics/{candidate_id}` (`patch`);
  - `/api/blog-agent/topics/{candidate_id}/reject` (`post`);
  - `/api/blog-agent/topics/history`, `/api/blog-agent/topics/external-posts`, `/api/blog-agent/topics/similar`, `/api/blog-agent/topics/diversity` (each `get`).
- `test_top_openapi_query_aliases`: the `get` operation of `/api/blog-agent/topics` has parameter names `{"runId", "round", "status"}`; `/topics/similar` has `{"text", "limit"}`; `/topics/diversity` has `{"days"}`.

**Implementation notes.** None. The test reads only the generated schema.

**Verification.**
1. Red, before TOP-10 and TOP-11 exist: missing components.
2. Green after them: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics/test_top_openapi.py` → 0 failed.
3. TOP-LINT clean.

**Acceptance bullets covered:** D8 and §8.3 (hand-written TS types stay aligned through the shared shape file); §4.4 model shapes.

---

### TOP-final: Track verification

**Files:** none new. Only fixes to owned files found by the runs below.

**Behaviour rules.**
1. Run every command below in order, all in Docker, and record the final output line of each in the track report (§11 rule 18).
2. A red test outside `tests/topics` is investigated with `tests/foundation/test_found_imports.py` first. A failure in another track's file becomes a `Request:` line, never an edit (§2 rules (b)).
3. Check that no `backend/prompts/**/*.wip` file owned by TOP remains, with `docker compose run --rm --no-deps tools sh -c 'ls prompts/ideation'` → prints only `topics.v1.md`.
4. Check that the owned `src` files never import `pydantic_ai`, `openai`, `google.genai`, `anthropic` or `dbos`: `docker compose run --rm --no-deps tools sh -c 'grep -nE "^(from|import) (pydantic_ai|openai|google\.genai|anthropic|dbos)" src/mdcopilot_blog/agents/topic_strategist.py src/mdcopilot_blog/services/topics.py src/mdcopilot_blog/services/topic_steps.py src/mdcopilot_blog/services/novelty.py src/mdcopilot_blog/services/diversity.py src/mdcopilot_blog/services/external_posts.py src/mdcopilot_blog/domain/scoring.py src/mdcopilot_blog/domain/novelty.py src/mdcopilot_blog/domain/diversity.py src/mdcopilot_blog/domain/headlines.py src/mdcopilot_blog/api/routers/topics.py src/mdcopilot_blog/api/schemas_topics.py; test $? -eq 1 && echo clean'` → prints `clean`.
5. Check that `domain/` files import only the standard library, `pydantic` and `mdcopilot_blog.domain`: `docker compose run --rm --no-deps tools sh -c 'grep -nE "^(from|import) mdcopilot_blog\.(api|db|services|llm|agents|workflows)" src/mdcopilot_blog/domain/scoring.py src/mdcopilot_blog/domain/novelty.py src/mdcopilot_blog/domain/diversity.py src/mdcopilot_blog/domain/headlines.py; test $? -eq 1 && echo clean'` → prints `clean`.

**Verification commands and expected results.**
```bash
# 1. Shared surface
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
#    expected: 0 failed
# 2. Whole track
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/topics
#    expected: 0 failed, 0 errors, 0 skipped (TOP has no live tests)
# 3. Route guards and served paths (Phase 1 tests that every track keeps green)
docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_top_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/api/test_rbac_routes.py tests/db/test_migrations.py
#    expected: 0 failed
# 4. Lint and types on owned paths
TOP-LINT   # the command in the header
#    expected: "All checks passed!", "<n> files already formatted", "Success: no issues found in 12 source files"
# 5. Static checks from rules 3-5
```

**Acceptance mapping (CONTRACT §10 rows where TOP is Primary or Also).**

| Contract row | TOP role | Proven by |
|---|---|---|
| §10.2 Topic Strategist schema enforces exactly 3 | Primary | TOP-4 `test_top_topic_ideas_requires_exactly_three`, `test_top_run_strategist_two_ideas_exhausts_route` |
| §10.2 `sync_mdcopilot_posts` read-only, paged, off while URL blank | Primary (INT wires maintenance) | TOP-9 `test_top_sync_disabled_makes_no_request`, `test_top_sync_pages_inserts_and_embeds`, `test_top_sync_error_writes_nothing` |
| §10.2 Embeddings + novelty engine + regeneration loop ≤2 rounds | Primary for the engine and the `select_topic` shortfall flag (INT runs the loop) | TOP-3 rules tests, TOP-5 service tests, TOP-6 `test_top_novelty_golden_path_all_pass_with_distinct_totals`, TOP-7 `test_top_select_flags_shortfall_after_regeneration_limit` |
| §10.2 Scoring with configurable weights and stored breakdown | Primary | TOP-2 hand-computed tests (default and custom weights), TOP-6 stored-column check |
| §10.2 `discover_topics` D1–D7; `regenerate_topics` | Also (seams) | TOP-6 and TOP-7 step tests (INT primary) |
| §10.2 UI Today's Ideas cards, Topics page | Also (API) | TOP-10 read API tests |
| §10.2 Always exactly 3 candidates or flagged shortfall after 2 rounds | Primary | TOP-6 `test_top_ideate_creates_three_proposed_candidates`, TOP-7 shortfall test, TOP-10 `test_top_get_topics_shortfall_flag` |
| §10.2 Seeded near-duplicate external post rejected, neighbour and similarity shown | Primary | TOP-6 `test_top_novelty_rejects_seeded_near_duplicate_external_post`, TOP-10 `test_top_near_duplicate_external_post_shown_in_get_topics` |
| §10.2 Weighted totals match a hand-computed fixture | Primary | TOP-2 `test_top_score_candidate_matches_hand_computed_default_weights`, `…_custom_weights` |
| §10.2 `POST /topics/generate` → 3 new candidates not repeating the previous round | Primary (intake, avoid list) | TOP-11 `test_top_generate_enqueues_regenerate_topics`, TOP-6 `test_top_ideate_round_two_supersedes_and_avoids`, TOP-4 `test_top_check_ideas_rules` |
| §10.2 Manual mode stops at `WAITING_FOR_TOPIC`; selecting enqueues production | Also (select enqueue) | TOP-7 `test_top_select_manual_mode_selects_nothing`, TOP-11 `test_top_select_passed_without_live_article_enqueues_production` |
| §10.3 Writer: avoid bundle + recent articles inputs | Also (`build_avoid_bundle`) | TOP-8 avoid-bundle tests |
| §10.4 Clinical and Editorial Reviewers (avoid bundle) | Also | TOP-8 avoid-bundle tests |
| §10.4 SEO Specialist internal links from published and external posts | Also (`nearest_neighbours`) | TOP-5 nearest-neighbour tests |
| §10.4 All 15 gates, diversity checks | Also (`evaluate_diversity`, `check_article_duplicate`) | TOP-8 evaluate tests, TOP-5 gate-6 tests |
| §10.5 Dashboard diversity panel | Also (`/topics/diversity`) | TOP-10 `test_top_diversity_panel` |
| §10.8 / D9 every `blog_llm_calls` row has `run_id`, with the stated exceptions | Also (`/topics/similar` and maintenance sync write `run_id NULL`; step calls carry `sc.call.run_id`) | TOP-10 `test_top_similar_embeds_without_run_and_ranks`, TOP-9 embedding-row assertions, TOP-6 embedding rows carry `run_id` |
| §5.8 TOP golden-path invariant | Primary | TOP-4 `test_top_default_fixture_satisfies_golden_invariants`, TOP-6 golden-path novelty test |
| §5.7 Rule B (select and generate reject CANCELLED up front) | Also | TOP-11 `test_top_select_cancelled_run`, `test_top_generate_run_status_rules` |
| §4.4 select sequence with compensation on committing fixtures | Primary | TOP-11 `test_top_select_enqueue_failure_restores_committed_rows` |
| §9 `BLOG_MDCOPILOT_PUBLIC_API_URL` owner input | Fallback | TOP-9 disabled test and hand-built pages; the track is "complete, pending owner input" |

---

## Open questions (for the controller; the plan follows the contract meanwhile)

1. **Graph builders called twice.** CONTRACT §8.1 does not say `make_article_graph` / `make_research_graph` can run twice in one session, and both insert the golden ledger (`uq_blog_sources_url_hash`). The multi-article tests in TOP-5, TOP-8 and TOP-10 need two or three articles. TOP-0 gates this and files a `Request:` if needed.
2. **Selection race.** Between D7 auto-selection enqueuing `produce_article` and `ensure_article` creating the article, the run has a SELECTED candidate but no live article. A human selecting another candidate then gets a second `produce_article` (§4.4 rule "no live article → produce"). Proposal: treat a SELECTED candidate of the run as live for the produce/change decision, or return 409 `Topic cannot be selected` while the run is `PRODUCING` with no live article.
3. **Generate on a manual-topic run.** A run created with `topic` has no broad research run. `POST /topics/generate` passes intake, but `regenerate_topics` cannot call `ideate_topics`. Proposal: an additional 409 `Topics cannot be regenerated` with detail `run has no broad research run`. Not implemented, because §4.4 lists the 409 conditions.
4. **Edits and novelty (P1).** `PATCH /topics/{id}` does not re-embed or re-check novelty, so an edited candidate carries embeddings, scores and a novelty decision computed for its original text, and `promote_candidate` copies those embeddings into `blog_topics`.
5. **Score breakdown keys (P7).** §4.4 types `score_breakdown` as `dict[str, ScoreItem]` without naming keys. TOP uses `timeliness, novelty, evidence, mdcopilotRelevance, audience, editorial`; UI should use the same.
6. **Compensation audit.** After an enqueue failure, the committed `topic.select` audit row remains even though the selection was undone. §4.4 lists no compensation audit action.
7. **External post URL.** The public API returns no URL, so TOP stores `EffectiveConfig.site_url + "/blog/" + slug`. Confirm that the production site's post path is `/blog/{slug}`.
8. **Mock regeneration depth (P6).** The mock ideation fixture has five distinct idea sets, so mock regenerations beyond round 5 fail with `RouteExhausted`. That is acceptable for tests; the UI smoke must not regenerate more than four times.
9. **Keywords (P8).** `blog_topic_candidates` has no `keywords` column, so `blog_topics.keywords` is derived deterministically at promotion instead of from the Topic Strategist.
