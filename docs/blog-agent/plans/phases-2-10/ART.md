# Track ART: Articles (Phase 4) — implementation plan

Status: plan for the parallel stage (W3). Binding contract: `docs/blog-agent/plans/phases-2-10/CONTRACT.md` (revision 2). When this plan and the contract disagree, the contract wins. Paths are relative to `mdcopilot-blog/`; `pkg/` = `backend/src/mdcopilot_blog/`.

## Header

**Goal.** Deliver the article layer: the Deep Research Analyst and Writer agents, immutable article versions with deterministic Markdown assembly and positional parsing, the `article_steps` seams INT calls (P1 `ensure_article`, P2, P3, revise, component regeneration), and the §4.5 article API (list, detail, human edit with deterministic gates, versions, diff, regenerate intake, title selection, sources, research packets). All in mock mode; no paid calls.

**Spec sections implemented.**
- ARCHITECTURE §5.2 P1 (`ensure_article` part), P2, P3, P7/fix-pass Writer step bodies; §5.3 step bodies and API intake for `regenerate_component`, `regenerate_article`, `regenerate_research`; §7 (Deep Research Analyst, Writer); §11 (versions, assembly, human edits, regeneration); §12 (article API view); §13 (article review data); §15 writes to `blog_articles`, `blog_research_packets`, `blog_article_versions`, `blog_article_sources`, `blog_version_seo` (human edits only); §16 article endpoints.
- RESEARCH_ARCHITECTURE §6 (research packet output of deep research; regenerate research keeps old packet).
- IMPLEMENTATION_PLAN Phase 4 (Build and Acceptance).
- CONTRACT §4.5, §5.3 (use of text helpers), §5.5 step body rules, §5.6 (ART agent specs, `article_steps`), §5.8 (ART fixture invariants), §10.3 (ART rows), §10.4 row "Regenerating the article creates new versions and keeps old".

**Owned files (CONTRACT §2.2 ART).**

| Path | Notes |
|---|---|
| `pkg/agents/deep_research_analyst.py`, `pkg/agents/writer.py` | |
| `pkg/services/articles.py`, `pkg/services/article_views.py`, `pkg/services/versions.py` | API services |
| `pkg/services/article_steps.py` | stub by FOUND |
| `pkg/domain/article_assembly.py` | pure: builds versions from drafts and edits, maps `split_markdown` pairs to `SECTION_ORDER` keys, marker validation; Markdown text is produced and parsed only by `domain.text.assemble_markdown`/`split_markdown` |
| `pkg/api/routers/articles.py`, `pkg/api/schemas_articles.py` | stub by FOUND |
| `backend/prompts/deep_research/**`, `backend/prompts/writer/**` | |
| `backend/fixtures/mock/llm/deep_research/**`, `backend/fixtures/mock/llm/writer/**` | `writer_draft.json` output must equal the golden article |
| `backend/fixtures/mock/scenarios/articles_*/**` | |
| `backend/tests/articles/**` | including the FOUND-created `__init__.py` and `conftest.py` |
| `docs/blog-agent/plans/phases-2-10/art.md` | this plan (written as `ART.md`; see open questions) |
| `.superpowers/sdd/phases-2-10/requests/art.md` | `Request:` lines (CONTRACT §2 rules) |

**Extension points consumed (exact names; FOUND unless marked Phase 1).**
- `mdcopilot_blog.domain.text`: `CITATION_MARKER_RE`, `assemble_markdown`, `split_markdown`, `body_word_count`, `extract_markers`.
- `mdcopilot_blog.domain.errors`: `ArticleStructureError`, `UnknownCitationMarker`, `OutputRejected`, `InsufficientEvidence`.
- `mdcopilot_blog.domain.contracts`: `SECTION_ORDER`, `ArticleSection`, `ArticleDraft`, `ComponentDraft`, `ResearchPacket`, `PacketFact`, `PacketStatistic`, `SourceRef`, `FindingResolution`, `RevisionFinding`, `AvoidBundle`, `RecentArticleRef`, `HumanDecision` (not written by ART), and Phase 1 `TitleOptions`, `SEOMetadata`, `SocialCopy`, `BlogSource`, `FactCheckResult`, `ClinicalReview`, `EditorialReview`, `GateReport`, `GateResult`, `NoveltyResult`, `PillarKey`.
- `mdcopilot_blog.domain.enums`: `ChangeKind`, `SectionKey`, `ArticleComponent`, `TitleKey`, `ReviewKind`, `ReviewVerdict`, `GateRunKind`, `GateId`, `AccessMode`, `DateSource`, `ApprovalMode`; Phase 1 `ArticleStatus`, `RunStatus`, `AgentName`, `Permission`, `Role`.
- `mdcopilot_blog.domain.config`: `EffectiveConfig`, `BrandProfileValues`, `WordCountRange`.
- `mdcopilot_blog.agents.common`: `UNTRUSTED_NOTICE`, `NumberedSource`, `number_sources`, `render_source_list`, `resolve_markers`.
- `mdcopilot_blog.llm.gateway`: `LLMGateway` (`run(spec, *, variables, user_prompt, ctx, route_override, prompt_version, output_check)`), `AgentSpec` (with `reasoning`), `AgentResult`, `CallContext`, `RouteExhausted`, `build_gateway`, `build_model_factory` (patched in tests only).
- `mdcopilot_blog.prompts.registry`: `PromptRegistry.from_directory(root, *, agents=...)`, `default_prompt_root`.
- `mdcopilot_blog.services.step_context`: `StepContext` (`with_ids`, `call`, `config`, `brand`, `sessionmaker`, `gateway`), `build_api_step_context`.
- `mdcopilot_blog.services.config`: `load_effective_config`, `load_brand_profile`.
- `mdcopilot_blog.services.article_status`: `set_article_status`.
- `mdcopilot_blog.services.enqueue`: `ensure_agent_enabled`, `enqueue_workflow`, `ActionAcceptedParts`.
- Seams of other tracks, always called through the module attribute: `mdcopilot_blog.services.diversity.record_version_features` (TOP), `mdcopilot_blog.services.quality_steps.run_deterministic_gates` (QUAL). Both raise `NotImplementedError` during the parallel stage, so every ART test that reaches them monkeypatches them.
- Stub to implement: `mdcopilot_blog.services.article_steps` (`ensure_article`, `PacketResult`, `build_research_packet`, `latest_packet_id`, `VersionResult`, `write_draft`, `revise_article`, `regenerate_component`) with the §5.6 signatures unchanged.
- `mdcopilot_blog.workflows.names`: `WORKFLOW_REGENERATE_COMPONENT`, `WORKFLOW_REGENERATE_ARTICLE`, `WORKFLOW_REGENERATE_RESEARCH`, Phase 1 `QUEUE_INTERACTIVE`.
- `mdcopilot_blog.api.schemas_common`: `ActionAccepted`, `SourceRefOut`. Phase 1: `mdcopilot_blog.api.schemas.ApiModel`, `Page`; `mdcopilot_blog.api.deps.Principal`, `SessionDep`, `SettingsDep`, `WorkflowClientDep`, `require_permission`; `mdcopilot_blog.errors.ProblemError`; `mdcopilot_blog.services.audit.audit`; `mdcopilot_blog.ids.uuid7`, `new_trace_id`.
- Global problem mappings (FOUND, §4.0): `ArticleStructureError` → 422 `Article structure invalid`; `UnknownCitationMarker` → 422 `Unknown citation marker` (detail `unknown markers: S9, S12`); `InvalidTransition` → 409.
- ORM (`mdcopilot_blog.db.models`): `Article`, `ArticleVersion`, `ResearchPacketRecord`, `VersionSeo`, `ArticleSource`, `LedgerSource`, `ResearchRun`, `TopicCandidateRecord`, `Topic`, `Review`; Phase 1 `BlogRun`, `ContentPillar`, `AuditLog`, `LlmCall`. ART reads RES/TOP/QUAL tables and writes only `blog_articles`, `blog_research_packets`, `blog_article_versions`, `blog_article_sources`, `blog_version_seo` (PATCH only).
- Test fixtures (root `tests/conftest.py`, §8.1): `settings`, `db_session`, `seeded_db`, `clean_db`, `sessionmaker_committing`, `committed_seed`, `app`, `client`, `login_as`, `fake_workflow_client`, `committing_app`, `committing_client`, `committing_login_as`, `mock_step_context`, `make_research_graph`, `make_article_graph` (`tests/graph_builders.py`: `ArticleGraphIds`, `ResearchGraphIds`). Golden data: `backend/fixtures/mock/golden/{article_draft,seo,fact_check,clinical,editorial,gate_report}.json`. Shape file: `backend/tests/api_shapes.json`. Phase 1 `mdcopilot_blog.workflows.client.FakeWorkflowClient`, `EnqueueCall`; `mdcopilot_blog.db.seed.load_seed_file`.

**Test database and commands (all from `mdcopilot-blog/`; containers only).**
- Test DB: `mdcopilot_blog_art_test`. A reviewer or any second concurrent ART process uses `mdcopilot_blog_art_review_test`.
- Test directory `backend/tests/articles/`, basenames `test_art_*.py`.
- Run one file or the track:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/<file>
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles
  ```
- Shared import surface check before reporting any red test as ART's own (§2 rules (b)):
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
  ```
- Lint and types (owned paths; the task text lists the paths that exist at that point; the full list is in ART-final):
  ```bash
  docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c \
    "ruff check --no-cache <paths> tests/articles && ruff format --check --no-cache <paths> tests/articles && mypy --cache-dir=/tmp/mypy --follow-imports=silent <paths>"
  ```

**Owner inputs.** None. ART makes no paid calls (§9 rule 1). The "live drafts from the 5 validation runs recorded" bullet is INT's (§10.3). Fallback if missing: not applicable.

**Track rules applied in every task.**
1. TDD: write the listed tests, run them red in Docker and record the failing summary line, implement, run green, then lint. Record red/green lines in the track report.
2. Save points (§2 rules (a)): `api/routers/articles.py`, `api/schemas_articles.py` and `services/article_steps.py` are imported by the app and by `test_found_imports.py`; they must import cleanly after every edit. Prompt drafts are written as `<name>.v1.md.wip` and renamed to `<name>.v1.md` only when the front matter and body are complete.
3. Anything needed outside the owned files is a `Request:` line in `.superpowers/sdd/phases-2-10/requests/art.md`; stop that item, continue the others.
4. Tests may update single columns of rows created by the §8.1 graph builders (test setup only). Production code never writes RES, TOP, QUAL, PUB or INT tables.
5. Error detail strings below are exact; tests assert them.

## Tasks

### ART-1: Pure article assembly (`domain/article_assembly.py`)

**Files.**
- Create `pkg/domain/article_assembly.py`.
- Modify `backend/tests/articles/conftest.py` (add golden helpers below).
- Create `backend/tests/articles/test_art_assembly.py`.

**Interfaces.**
- Consumes: `domain.text.{CITATION_MARKER_RE, assemble_markdown, split_markdown, body_word_count, extract_markers}`; `domain.errors.{ArticleStructureError, UnknownCitationMarker}`; `domain.contracts.{SECTION_ORDER, ArticleSection, ComponentDraft, TitleOptions, SEOMetadata}`; `domain.enums.{ArticleComponent, SectionKey, TitleKey}`. Imports nothing outside `domain/`.
- Produces:
  ```python
  TITLE_MAX_CHARS = 200
  EXCERPT_MAX_CHARS = 500
  NON_BODY_FIELDS: tuple[str, ...] = ("titleOptions.provocative", "titleOptions.operational", "titleOptions.visionary", "pullQuote", "cta", "excerpt")
  SEO_DIFF_KEYS: tuple[str, ...] = ("seoTitle", "metaDescription", "slug", "primaryKeyword", "secondaryKeywords", "ogTitle", "ogDescription", "tags", "category", "internalLinkSuggestions", "externalReferences")

  @dataclass(frozen=True)
  class VersionContent:
      title_options: TitleOptions
      sections: tuple[ArticleSection, ...]
      pull_quote: str
      cta: str
      excerpt: str
      content_markdown: str
      word_count: int
      citation_markers: tuple[str, ...]

  def normalize_section(section: ArticleSection) -> ArticleSection
  def normalize_title_options(options: TitleOptions) -> TitleOptions
  def sections_from_markdown(md: str) -> list[ArticleSection]
  def build_version_content(*, title_options: TitleOptions, sections: Sequence[ArticleSection], pull_quote: str, cta: str, excerpt: str) -> VersionContent
  def edit_content(base: VersionContent, *, content_markdown: str | None, title_options: TitleOptions | None, pull_quote: str | None, cta: str | None, excerpt: str | None) -> VersionContent
  def apply_component(base: VersionContent, draft: ComponentDraft) -> VersionContent
  def marker_number(marker: str) -> int
  def resolve_packet_markers(markers: Sequence[str], source_ids: Sequence[uuid.UUID]) -> dict[str, uuid.UUID]
  def title_for_key(options: TitleOptions, key: TitleKey) -> str | None
  def merge_seo(base: SEOMetadata, edits: Mapping[str, object]) -> SEOMetadata
  def diff_fields(content: VersionContent, seo: SEOMetadata | None) -> dict[str, str | None]
  def field_changes(before: Mapping[str, str | None], after: Mapping[str, str | None]) -> list[tuple[str, str | None, str | None]]
  def unified_markdown_diff(before_md: str, after_md: str, *, before_no: int, after_no: int) -> str
  ```

**Behaviour rules.**
1. `normalize_section`: returns a copy with `body_markdown.strip()` and `heading.strip()` (a `None` heading stays `None`). `normalize_title_options`: strips each of the three options. Neither function is applied implicitly by `build_version_content`; callers normalize new input only, so stored sections that are copied from a base version are never rewritten.
2. `sections_from_markdown(md)`: `pairs = split_markdown(md)` (its `ArticleStructureError` propagates unchanged, e.g. `expected 6 H2 sections, found 5`); returns `[ArticleSection(key=SECTION_ORDER[i], heading=pairs[i][0], body_markdown=pairs[i][1]) for i in range(7)]`. Heading text may differ from the base; mapping is by position only.
3. `build_version_content` checks, in this order, raising `ArticleStructureError` with the exact message:
   1. keys of `sections` equal `SECTION_ORDER` in order and there are exactly 7 → else `sections must be introduction, context, core_argument, evidence, mdcopilot_perspective, practical_implications, conclusion in this order`;
   2. the introduction heading is `None` → else `introduction must not have a heading`;
   3. for every later section in order, `heading is not None and heading.strip()` → else `section <key> needs a heading`;
   4. for every section in order, `body_markdown.strip()` non-empty → else `section <key> has an empty body`;
   5. `split_markdown(assemble_markdown(sections))` (an `ArticleStructureError` from it propagates unchanged) equals `[(s.heading.strip() if s.heading is not None else None, s.body_markdown.strip()) for s in sections]` → else `section <key> does not survive Markdown assembly` naming the first mismatching position's key;
   6. for `provocative`, `operational`, `visionary` in that order: `1 <= len(option.strip()) <= 200` → else `title option <name> must be 1 to 200 characters`;
   7. `pull_quote.strip()` non-empty → else `pullQuote must not be empty`; `cta.strip()` non-empty → else `cta must not be empty`; `excerpt.strip()` non-empty → else `excerpt must not be empty`; `len(excerpt) <= 500` → else `excerpt must be at most 500 characters`;
   8. the fields of `NON_BODY_FIELDS` (in that order) whose text matches `CITATION_MARKER_RE` → if any: `citation markers are allowed only in section bodies: <comma-and-space-joined field names>`.
   Then it computes `content_markdown = assemble_markdown(sections)`, `word_count = body_word_count(sections)`, `citation_markers = tuple(extract_markers("\n\n".join(s.body_markdown for s in sections)))` and returns `VersionContent` holding the given objects unchanged.
4. `edit_content`: `sections = sections_from_markdown(content_markdown)` when given, else `base.sections`; `title_options = normalize_title_options(title_options)` when given, else base; `pull_quote`, `cta`, `excerpt` = given value `.strip()` when not `None`, else base; then `build_version_content`.
5. `apply_component(base, draft)`:
   - `draft.component` in {`article`, `research`} → `ValueError("<component> is not a component regeneration")`.
   - `headline` → new `title_options = normalize_title_options(draft.title_options)`.
   - `introduction` → `draft.section.key` must be `introduction`, else `ArticleStructureError("expected section introduction, got <key>")`; replace position 0 with `normalize_section(draft.section)`.
   - `section` → `draft.section_key` must equal `draft.section.key` and must not be `introduction`, else `ArticleStructureError("expected section <section_key>, got <section.key>")`; replace the section with that key with `normalize_section(draft.section)`.
   - `pull_quote` / `cta` → the stripped new value.
   - Every other field and every other section object is taken from `base` unchanged; result = `build_version_content(...)`.
6. `marker_number("S12") == 12`. `resolve_packet_markers(markers, source_ids)`: walks markers de-duplicated in first-appearance order; a marker is known iff it matches `^S[1-9][0-9]*$` and `1 <= n <= len(source_ids)`; unknown markers (first-appearance order, de-duplicated) → `UnknownCitationMarker(unknown)`; else returns `{marker: source_ids[n - 1]}` in first-appearance order.
7. `title_for_key(options, key)`: the option text for `provocative`/`operational`/`visionary`; `None` for `custom`.
8. `merge_seo(base, edits)`: `SEOMetadata.model_validate({**base.model_dump(by_alias=False), **edits})`; `edits` uses Python field names and holds only fields to change.
9. `diff_fields(content, seo)` returns keys in this order with these values: `pullQuote`, `cta`, `excerpt`, `titleOptions.provocative`, `titleOptions.operational`, `titleOptions.visionary` (strings), then `seo.<key>` for each `SEO_DIFF_KEYS` entry taken from `seo.model_dump(mode="json")[key]`: a string as is, any other value as `json.dumps(value, ensure_ascii=False, separators=(",", ":"))`; every `seo.*` value is `None` when `seo is None`.
10. `field_changes(before, after)`: in `before`'s key order, `(key, before[key], after[key])` for keys whose values differ.
11. `unified_markdown_diff`: `"\n".join(difflib.unified_diff(before_md.splitlines(), after_md.splitlines(), fromfile=f"v{before_no}", tofile=f"v{after_no}", n=3, lineterm=""))`; identical inputs give `""`.

**Tests to write first** (`backend/tests/articles/test_art_assembly.py`; unit, no database).

Conftest helpers added in this task (`backend/tests/articles/conftest.py`): `BACKEND_ROOT = Path(__file__).resolve().parents[2]`; `GOLDEN_DIR = BACKEND_ROOT / "fixtures/mock/golden"`; `def load_golden_output(name: str) -> dict[str, Any]` (the `output` object of `GOLDEN_DIR/name`); `def golden_draft() -> ArticleDraft` (`ArticleDraft.model_validate(load_golden_output("article_draft.json"))`); `def golden_content() -> VersionContent` (`build_version_content` over the golden draft's fields).

1. `test_art_golden_draft_builds_version_content` — `c = golden_content()`; assert `c.content_markdown == assemble_markdown(golden_draft().sections)`, `c.word_count == body_word_count(golden_draft().sections)`, `850 <= c.word_count <= 1150`, `set(c.citation_markers) == {"S1","S2","S3","S4","S5"}`, `c.citation_markers == tuple(extract_markers("\n\n".join(s.body_markdown for s in golden_draft().sections)))`. (Acceptance: word-count and structure checks pass on the draft fixture.)
2. `test_art_golden_draft_has_markers_only_in_section_bodies` — for the golden title options, pull quote, CTA and excerpt, `CITATION_MARKER_RE.search(text) is None`. (Guards the FOUND golden against rule 3.8; a failure here is a `Request:`.)
3. `test_art_sections_from_markdown_maps_by_position` — `md = assemble_markdown(sections)` with each `## <golden heading i>` line replaced by `## Heading <i>` (i = 1..6); result keys `== list(SECTION_ORDER)`, headings `== [None, "Heading 1", …, "Heading 6"]`, bodies `== [s.body_markdown.strip() for s in golden sections]`.
4. `test_art_sections_from_markdown_rejects_five_h2_sections` — delete the `## <conclusion heading>` line from the assembled golden Markdown; `pytest.raises(ArticleStructureError)`, `str(exc) == "expected 6 H2 sections, found 5"`.
5. `test_art_build_rejects_sections_out_of_order` — swap context and evidence; message rule 3.1.
6. `test_art_build_rejects_introduction_heading` — introduction heading `"Opening"`; `introduction must not have a heading`.
7. `test_art_build_rejects_blank_heading` — context heading `"   "`; `section context needs a heading`.
8. `test_art_build_rejects_empty_body` — evidence body `"  \n "`; `section evidence has an empty body`.
9. `test_art_build_rejects_heading_that_does_not_round_trip` — context heading `"Two\nLines"`; `section context does not survive Markdown assembly`.
10. `test_art_build_rejects_markers_outside_bodies` — pull quote `+ " [S1]"`, excerpt `+ " [S2]"`; `citation markers are allowed only in section bodies: pullQuote, excerpt`.
11. `test_art_build_rejects_long_title_option` — visionary `"x" * 201`; `title option visionary must be 1 to 200 characters`.
12. `test_art_build_rejects_bad_short_fields` — parametrized: (`pull_quote="  "`, `pullQuote must not be empty`), (`cta=""`, `cta must not be empty`), (`excerpt=" "`, `excerpt must not be empty`), (`excerpt="a" * 501`, `excerpt must be at most 500 characters`).
13. `test_art_citation_markers_keep_first_appearance_order` — golden sections with every marker removed (`CITATION_MARKER_RE.sub("", body)`), then introduction body `"Alpha [S2] beta [S1]."` and context body `"Gamma [S1] delta [S3]."`; `citation_markers == ("S2", "S1", "S3")`.
14. `test_art_resolve_packet_markers_maps_to_source_ids` — `ids = [uuid7(), uuid7(), uuid7()]`; `resolve_packet_markers(["S1", "S3", "S1"], ids) == {"S1": ids[0], "S3": ids[2]}`; `resolve_packet_markers([], ids) == {}`.
15. `test_art_resolve_packet_markers_reports_unknown_in_order` — `resolve_packet_markers(["S2", "S9", "S12", "S9"], ids)` raises `UnknownCitationMarker` with `exc.args[0] == ["S9", "S12"]`.
16. `test_art_edit_content_replaces_only_given_fields` — `edit_content(golden_content(), content_markdown=None, title_options=None, pull_quote="  Specialist time is the scarcest resource in the clinic.  ", cta=None, excerpt=None)`; `pull_quote == "Specialist time is the scarcest resource in the clinic."`, `sections is base.sections` content-equal (`==`), `cta == base.cta`, `title_options == base.title_options`.
17. `test_art_apply_component_section_replaces_only_target` — `ComponentDraft(component="section", section_key="evidence", title_options=None, section=ArticleSection(key="evidence", heading="  What the evidence shows  ", body_markdown="  New evidence body [S3].  "), pull_quote=None, cta=None)`; `new.sections[i] == base.sections[i]` for every `i != 3`; `new.sections[3] == ArticleSection(key="evidence", heading="What the evidence shows", body_markdown="New evidence body [S3].")`; `title_options`, `pull_quote`, `cta`, `excerpt` equal base; the lines of `new.content_markdown` before the line `## What the evidence shows` equal the lines of `base.content_markdown` before `## <golden evidence heading>`.
18. `test_art_apply_component_headline_changes_only_titles` — headline draft with three new options; `new.sections == base.sections`, `new.content_markdown == base.content_markdown`, `new.title_options` equals the stripped new options.
19. `test_art_apply_component_rejects_mismatched_section` — `component="section", section_key="evidence"`, section key `context`; `ArticleStructureError`, `expected section evidence, got context`.
20. `test_art_merge_seo_overrides_only_given_fields` — base `SEOMetadata.model_validate(load_golden_output("seo.json")["seo"])`; `merge_seo(base, {"seo_title": "New SEO title", "tags": ["access"]})` has `seo_title == "New SEO title"`, `tags == ["access"]`, every other field equal to base.
21. `test_art_diff_fields_and_changes` — `before = diff_fields(golden_content(), base_seo)`; `list(before)[:6] == ["pullQuote", "cta", "excerpt", "titleOptions.provocative", "titleOptions.operational", "titleOptions.visionary"]`, `list(before)[6:] == [f"seo.{k}" for k in SEO_DIFF_KEYS]`; `before["seo.secondaryKeywords"] == json.dumps(base_seo.secondary_keywords, ensure_ascii=False, separators=(",", ":"))`; `after` = same with changed pull quote and `merge_seo(base_seo, {"seo_title": "New SEO title"})`; `field_changes(before, after) == [("pullQuote", old_pq, new_pq), ("seo.seoTitle", base_seo.seo_title, "New SEO title")]`; `diff_fields(golden_content(), None)["seo.slug"] is None`.
22. `test_art_unified_markdown_diff_format` — `unified_markdown_diff("a\nb\nc", "a\nB\nc", before_no=1, after_no=2) == "--- v1\n+++ v2\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c"`; `unified_markdown_diff("a", "a", before_no=1, after_no=1) == ""`.
23. `test_art_title_for_key` — parametrized over `provocative`, `operational`, `visionary` (returns the golden option) and `custom` (returns `None`).

**Implementation notes.** `difflib` shape verified in the backend:dev image on 2026-09-17 (`'--- v1\n+++ v2\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c'`, identical inputs → `''`).

**TDD order and verification.**
1. Write conftest helpers and the 23 tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_assembly.py` → collection error `ModuleNotFoundError: No module named 'mdcopilot_blog.domain.article_assembly'`, exit code 2.
2. Implement the module. Green: same command → `29 passed`.
3. Lint: paths `src/mdcopilot_blog/domain/article_assembly.py` → exit 0.

**Acceptance covered.** §10.3 "Writer: … deterministic assembly and positional parsing" (unit part); "Word-count and structure checks pass on the draft fixture" (unit); "Unknown citation markers rejected" (unit).

### ART-2: API models (`api/schemas_articles.py`)

**Files.**
- Modify `pkg/api/schemas_articles.py` (FOUND stub: docstring only).
- Modify `backend/tests/articles/conftest.py` (add `SHAPES`).
- Create `backend/tests/articles/test_art_schemas.py`.

**Interfaces.**
- Consumes: `api.schemas.ApiModel`; the §5.2 contracts and §5.1 enums listed in the header; `domain.contracts.PillarKey`.
- Produces (all extend `ApiModel`; field names Python snake_case, wire camelCase; `uuid` = `uuid.UUID`):

| Model | Fields (type; default) |
|---|---|
| `GateBadgeOut` | `passed: bool \| None`, `failed_gates: list[GateId]`, `recheck_required: bool` |
| `ArticleSummaryOut` | `id: uuid`, `run_id: uuid`, `run_date: date`, `title: str \| None`, `slug: str \| None`, `status: ArticleStatus`, `pipeline_status: RunStatus`, `pillar: PillarKey`, `category: str`, `current_version_no: int \| None`, `word_count: int \| None`, `gate_badge: GateBadgeOut`, `fact_check_verdict: Literal["PASS","FAIL"] \| None`, `independent_check: bool \| None`, `editorial_score: float \| None`, `scheduled_for: datetime \| None`, `published_at: datetime \| None`, `published_url: str \| None`, `created_at: datetime`, `updated_at: datetime` |
| `ArticleDetailOut` | `id: uuid`, `run_id: uuid`, `run_date: date`, `topic_id: uuid`, `candidate_id: uuid`, `title_options: TitleOptions \| None`, `selected_title: str \| None`, `selected_title_key: TitleKey \| None`, `slug: str \| None`, `content_markdown: str \| None`, `sections: list[ArticleSection] \| None`, `excerpt: str \| None`, `pull_quote: str \| None`, `cta: str \| None`, `category: str`, `tags: list[str]`, `pillar: PillarKey`, `seo: SEOMetadata \| None`, `social: SocialCopy \| None`, `sources: list[BlogSource]`, `research_summary: str \| None`, `research_packet_id: uuid \| None`, `research_packet_version: int \| None`, `fact_check: FactCheckResult \| None`, `clinical_review: ClinicalReview \| None`, `editorial_review: EditorialReview \| None`, `quality_gates: GateReport \| None`, `novelty: NoveltyResult \| None`, `status: ArticleStatus`, `pipeline_status: RunStatus`, `version_no: int \| None`, `current_version_id: uuid \| None`, `approved_version_id: uuid \| None`, `published_version_id: uuid \| None`, `recheck_required: bool`, `gates_passed_on_current_version: bool`, `approved_at: datetime \| None`, `approved_by: uuid \| None`, `approval_mode: ApprovalMode \| None`, `rejection_reason: str \| None`, `scheduled_for: datetime \| None`, `scheduled_by: uuid \| None`, `published_at: datetime \| None`, `published_url: str \| None`, `created_at: datetime`, `updated_at: datetime` |
| `SeoEdit` | all `= None`: `seo_title: str \| None` (1..200), `meta_description: str \| None` (1..500), `slug: str \| None` (pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`, max 200), `primary_keyword: str \| None` (1..200), `secondary_keywords: list[str] \| None`, `og_title: str \| None` (1..200), `og_description: str \| None` (1..500), `tags: list[str] \| None`, `category: str \| None` (1..100) |
| `ArticleEditRequest` | `base_version_id: uuid`; all `= None`: `content_markdown: str \| None` (1..60000), `pull_quote: str \| None` (1..500), `cta: str \| None` (1..500), `excerpt: str \| None` (1..500), `title_options: TitleOptions \| None`, `seo: SeoEdit \| None`, `tags: list[str] \| None`, `category: str \| None` (1..100) |
| `VersionSummaryOut` | `id: uuid`, `version_no: int`, `parent_version_id: uuid \| None`, `change_kind: ChangeKind`, `change_scope: dict[str, Any]`, `word_count: int`, `created_by: uuid \| None`, `created_by_kind: Literal["agent","human"]`, `created_at: datetime`, `fact_check_verdict: Literal["PASS","FAIL"] \| None`, `gates_passed: bool \| None` |
| `VersionDetailOut(VersionSummaryOut)` | `+ title_options: TitleOptions`, `sections: list[ArticleSection]`, `pull_quote: str`, `cta: str`, `excerpt: str`, `content_markdown: str`, `citation_markers: list[str]`, `resolutions: list[FindingResolution]`, `research_packet_id: uuid \| None`, `seo: SEOMetadata \| None`, `social: SocialCopy \| None` |
| `FieldChangeOut` | `field: str`, `from_value: str \| None = Field(alias="from")`, `to_value: str \| None = Field(alias="to")` |
| `VersionDiffOut` | `from_version_id: uuid`, `to_version_id: uuid`, `from_version_no: int`, `to_version_no: int`, `unified_diff: str`, `field_changes: list[FieldChangeOut]` |
| `RegenerateRequest` | `component: ArticleComponent`, `section_key: SectionKey \| None = None`, `instructions: str \| None = None` (max 2000) |
| `SelectTitleRequest` | `key: Literal["provocative","operational","visionary"] \| None = None`, `custom_title: str \| None = None` (max 200) |
| `ArticleSourceOut` | `marker: str`, `source_id: uuid`, `title: str`, `url: str`, `canonical_url: str`, `publisher: str`, `domain: str`, `tier: int`, `published_at: datetime \| None`, `date_source: DateSource`, `access_mode: AccessMode`, `is_primary: bool` |
| `ResearchPacketOut` | `id: uuid`, `article_id: uuid`, `version: int`, `summary: str`, `packet: ResearchPacket`, `sources: list[SourceRefOut]`, `research_run_id: uuid \| None`, `created_at: datetime` |

  Module constant `ARTICLE_API_MODELS: tuple[type[ApiModel], ...]` listing the 13 models in the order above.

**Behaviour rules.**
1. List items: `tags` items (both in `SeoEdit` and `ArticleEditRequest`) and `secondary_keywords` items are `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]`; lists have `max_length=50`.
2. `RegenerateRequest` `@model_validator(mode="after")`, in order: `instructions` is stripped and becomes `None` when empty; `component == section` and `section_key is None` → `ValueError("sectionKey is required when component is section")`; `component == section` and `section_key == introduction` → `ValueError("sectionKey must not be introduction; use component introduction")`; `component != section` and `section_key is not None` → `ValueError("sectionKey is allowed only when component is section")`.
3. `SelectTitleRequest` validator: `custom_title` is stripped and becomes `None` when empty; then exactly one of `key`, `custom_title` must be non-`None`, else `ValueError("provide exactly one of key or customTitle")`.
4. `ArticleEditRequest` validator: at least one field other than `base_version_id` is non-`None`, else `ValueError("provide at least one field to change besides baseVersionId")`. `SeoEdit` validator: at least one field non-`None`, else `ValueError("seo must change at least one field")`.
5. Pydantic validation errors raised while FastAPI parses a body become 422 `Request validation failed` (Phase 1 handler); no extra handling in ART.

**Tests to write first** (`backend/tests/articles/test_art_schemas.py`; unit). Conftest addition: `SHAPES: dict[str, dict[str, list[str]]] = json.loads((BACKEND_ROOT / "tests" / "api_shapes.json").read_text())`; helper `def schema_shape(model: type[BaseModel], mode: Literal["validation", "serialization"]) -> tuple[list[str], list[str]]` returning sorted property names and sorted names whose schema is an `anyOf` containing `{"type": "null"}`.
1. `test_art_schema_models_match_shape_file` — parametrized over `ARTICLE_API_MODELS` (13 cases); mode `"serialization"` for names ending in `Out`, else `"validation"`; `schema_shape(model, mode) == (SHAPES[name]["props"], SHAPES[name]["nullable"])`. A mismatch that follows this plan's table and contradicts `api_shapes.json` is a `Request:` (the shape file is frozen).
2. `test_art_regenerate_request_valid` — parametrized: `{"component": "section", "sectionKey": "evidence"}` → `section_key == SectionKey.EVIDENCE`; `{"component": "headline"}` → `section_key is None`; `{"component": "article", "instructions": "   "}` → `instructions is None`.
3. `test_art_regenerate_request_invalid` — parametrized `ValidationError` cases, each asserting the message substring: `{"component": "section"}` (`sectionKey is required when component is section`); `{"component": "section", "sectionKey": "introduction"}` (`sectionKey must not be introduction; use component introduction`); `{"component": "headline", "sectionKey": "evidence"}` (`sectionKey is allowed only when component is section`); `{"component": "article", "instructions": "x" * 2001}` (`at most 2000 characters`); `{"component": "bogus"}` (`Input should be`).
4. `test_art_select_title_request_valid` — `{"key": "operational"}`; `{"customTitle": "  Specialist access needs leverage  "}` → `custom_title == "Specialist access needs leverage"`.
5. `test_art_select_title_request_invalid` — parametrized: both fields; neither; `{"customTitle": "   "}`; `{"customTitle": "x" * 201}`; the first three assert `provide exactly one of key or customTitle`, the fourth `at most 200 characters`.
6. `test_art_edit_request_invalid` — parametrized with a valid `baseVersionId`: nothing else (`provide at least one field to change besides baseVersionId`); `excerpt` 501 chars; `contentMarkdown ""`; `category ""`; `tags [" "]`.
7. `test_art_edit_request_accepts_camel_case` — `ArticleEditRequest.model_validate({"baseVersionId": str(u), "pullQuote": "A", "seo": {"seoTitle": "B"}})` → `pull_quote == "A"`, `seo.seo_title == "B"`.
8. `test_art_seo_edit_slug_rules` — parametrized `(slug, valid)`: `("Bad Slug", False)`, `("a" * 201, False)`, `("good-slug-2", True)`.

**TDD order and verification.**
1. Write the tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_schemas.py` → collection error `ImportError: cannot import name 'ARTICLE_API_MODELS'`.
2. Implement the models. Green: same command → `36 passed`. Import surface: `tests/foundation/test_found_imports.py` → all passed.
3. Lint paths: `src/mdcopilot_blog/domain/article_assembly.py src/mdcopilot_blog/api/schemas_articles.py` → exit 0.

**Acceptance covered.** §8.3 shape conformance (model level; OpenAPI level in ART-9); §10.3 "Save with wrong H2 count → 422" and "Version history and diff API" (request/response models).

### ART-3: Prompts and mock fixtures

**Files.**
- Create `backend/prompts/deep_research/packet.v1.md`, `backend/prompts/writer/draft.v1.md`, `backend/prompts/writer/revise.v1.md`, `backend/prompts/writer/component.v1.md` (each drafted as `*.v1.md.wip`, renamed when complete).
- Create `backend/fixtures/mock/llm/deep_research/deep_research_packet.json`, `backend/fixtures/mock/llm/writer/writer_draft.json`, `backend/fixtures/mock/llm/writer/writer_revise.json`, `backend/fixtures/mock/llm/writer/writer_component.json`, `backend/fixtures/mock/scenarios/articles_revise_two_findings/llm/writer/writer_revise.json`.
- Modify `backend/tests/articles/conftest.py` (invariant helper). Create `backend/tests/articles/test_art_fixtures.py`.

**Interfaces.**
- Consumes: `PromptRegistry.from_directory(default_prompt_root(), agents=["deep_research", "writer"])`; FOUND fixture registry v2 file forms (Phase 1 `{"output", "usage"}` and `{"cases": [...]}`); golden `article_draft.json`; `load_seed_file("brand_profile.yaml")`.
- Produces: prompt templates `deep_research/packet` v1 (agent `deep_research`, output `ResearchPacket`), `writer/draft` v1 (`ArticleDraft`), `writer/revise` v1 (`ArticleDraft`), `writer/component` v1 (`ComponentDraft`). Front-matter `variables`:
  - deep research: `[untrusted_notice, brand_name, brand_voice, brand_mission, pillar]`;
  - all three writer prompts: `[untrusted_notice, brand_name, brand_voice, audience, tone, avoid_bundle, word_count_min, word_count_max, website]`.

**Behaviour rules.**
1. Registry validity: filename `<last name segment>.v1.md`, file under `backend/prompts/<agent>/`, every declared variable used in the body and no other Jinja variable. No bare `---` line inside front-matter values (Phase 1 ledger item 14).
2. Deep research prompt body states, in plain instructions: `{{ untrusted_notice }}`; the analyst writes a research packet for `{{ brand_name }}` (voice `{{ brand_voice }}`, mission `{{ brand_mission }}`, pillar `{{ pillar }}`); it cites sources only as markers `S<n>` from the numbered source list in the user message, in `markers`, `primaryMarkers`, `supportingMarkers` and, inside text, as `[S<n>]`; it never writes URLs; every key fact and statistic carries at least one marker; `importance: "high"` only when a Tier 1 or 2 source with full text or an abstract supports it; a metadata-only source supports only "was published/announced" statements; preprints are named as preprints; no number that the sources do not state; anything uncertain goes to `claimsNeedingVerification`; `sourceRefs` may be an empty list (code fills it).
3. Writer draft prompt body states: `{{ untrusted_notice }}`; write for `{{ brand_name }}` with voice `{{ brand_voice }}`, audience `{{ audience }}`, tone `{{ tone }}`; output seven sections with keys `introduction, context, core_argument, evidence, mdcopilot_perspective, practical_implications, conclusion` in that order; introduction `heading` null, the other six headings plain text without `#`; no heading lines (lines starting with `#`) inside bodies; body word count between `{{ word_count_min }}` and `{{ word_count_max }}` (headings, pull quote and CTA excluded); cite with `[S<n>]` only inside section bodies and only markers from the source list; three title options (provocative, operational, visionary), each at most 90 characters; pull quote of 40–200 characters without quotation marks; a CTA that points readers to `{{ website }}` and differs from every CTA in the avoid bundle; an excerpt of at most 500 characters; never invent statistics, quotes, anecdotes, vignettes or first-person clinician experiences; do not reuse titles, openings, CTAs or overused phrases from the avoid bundle and never use its prohibited phrases: `{{ avoid_bundle }}`; `resolutions` is an empty list.
4. Writer revise prompt body: the same rules as rule 3 (same variables), plus: the user message lists findings as `F1`, `F2`, …; apply every finding marked required and optional ones where they improve the article; record one resolution per finding acted on and exactly one for every required finding, with `findingId` set to the `F<n>` reference, `action` one of `fixed`, `removed`, `declined`, and a non-empty `note`; never add a claim without a marker.
5. Writer component prompt body: the same variables and article rules as rule 3, plus: regenerate only the component named on the `Regenerate component:` line of the user message; set `component` to that component and fill only its field (`titleOptions` for headline, `section` for introduction and section, `pullQuote`, `cta`); for a section keep the same `key` and set `sectionKey` to it (the heading may change); for the introduction `section.key` is `introduction` with a null heading; keep flow with the neighbouring sections; follow the editor instructions when present.
6. `llm/writer/writer_draft.json`: byte copy of `fixtures/mock/golden/article_draft.json`.
7. `llm/deep_research/deep_research_packet.json`: Phase 1 form; `usage` `{"input_tokens": 60000, "output_tokens": 8000}`; `output` is a `ResearchPacket` (camelCase) with non-empty `summary`; at least 3 `keyFacts`, at least one with `importance: "high"`; at least 2 `statistics`; at least 1 `counterarguments` entry; `primaryMarkers: ["S1", "S2"]`; `supportingMarkers: ["S3", "S4", "S5"]`; non-empty `industryContext` and `mdcopilotConnection`; at least 1 `claimsNeedingVerification` item; `sourceRefs: []`; every key fact and statistic has at least one marker; every marker (list fields and inline `[S<n>]` in any text field) is within `S1`–`S5`.
8. `llm/writer/writer_revise.json`: Phase 1 form; `usage` `{"input_tokens": 35000, "output_tokens": 4500}`; `output` = golden draft with the conclusion body rewritten (same markers as the golden conclusion, word count within ±15 words of it) and `resolutions: [{"findingId": "F1", "action": "fixed", "note": "Addressed the finding in the revised conclusion."}]`.
9. `scenarios/articles_revise_two_findings/llm/writer/writer_revise.json`: same content as rule 8 with `resolutions: [{"findingId": "F1", "action": "fixed", "note": "Rewrote the flagged passage."}, {"findingId": "F2", "action": "declined", "note": "The cited source supports the claim as written."}]`.
10. `llm/writer/writer_component.json`: cases form with exactly 10 cases, each `usage` `{"input_tokens": 18000, "output_tokens": 1500}`. Cases 1–9 have `when.promptContains` equal to, in order: `Regenerate component: introduction`, `Regenerate component: section/context`, `Regenerate component: section/core_argument`, `Regenerate component: section/evidence`, `Regenerate component: section/mdcopilot_perspective`, `Regenerate component: section/practical_implications`, `Regenerate component: section/conclusion`, `Regenerate component: pull_quote`, `Regenerate component: cta`; case 10 has no `when` and is the headline. Each `output` is a `ComponentDraft` for its component: section cases keep the golden section key, set `sectionKey` to it, use the same markers as the golden section and a body within ±15 words of the golden body; the introduction case has `sectionKey: null`; headline gives three new title options; pull quote and CTA cases give new text. Every replaced value differs from the golden value.
11. Golden invariants (CONTRACT §5.8 items 1–7) hold for the golden article with any one component case applied, for the revise fixtures, and for the draft fixture.

**Tests to write first** (`backend/tests/articles/test_art_fixtures.py`; unit). Conftest additions: `LLM_ROOT = BACKEND_ROOT / "fixtures/mock/llm"`, `SCENARIO_ROOT = BACKEND_ROOT / "fixtures/mock/scenarios"`; `def assert_golden_invariants(content: VersionContent) -> None` asserting: section keys `== list(SECTION_ORDER)`, introduction heading `None`, six non-blank headings; `900 <= content.word_count <= 1100`; no ASCII digit in title options, headings, bodies, pull quote, CTA or excerpt; none of `"`, `“`, `”` in those texts; no `prohibited_language` phrase from `load_seed_file("brand_profile.yaml")` (case-insensitive) in those texts; `set(content.citation_markers) == {"S1", "S2", "S3", "S4", "S5"}` and no `[S<n>]` outside bodies; `120 <= len(excerpt) <= 500`; each title option `20 <= len <= 90`; `40 <= len(pull_quote) <= 200`; `cta.strip()` non-empty and `!= load_seed_file("brand_profile.yaml")["cta"]`.
1. `test_art_prompt_files_parse_with_declared_variables` — parametrized over the 4 prompt names; `registry.get(name)` has `version == 1`, `agent` (`deep_research` or `writer`), `output` per the list above, `variables` equal to the list above; `"{{ untrusted_notice }}" in template.body`.
2. `test_art_writer_draft_fixture_equals_golden` — `json.loads(LLM_ROOT/"writer/writer_draft.json") == json.loads(GOLDEN_DIR/"article_draft.json")`.
3. `test_art_deep_research_fixture_is_a_valid_packet` — `ResearchPacket.model_validate(output)`; rule 7 assertions, including the collected marker set `⊆ {"S1".."S5"}` (list fields plus `CITATION_MARKER_RE.findall` over `summary`, fact and statistic statements and values, counterargument statements, `industryContext`, `mdcopilotConnection`, `claimsNeedingVerification`); `usage == {"input_tokens": 60000, "output_tokens": 8000}`.
4. `test_art_writer_revise_fixture_keeps_golden_invariants` — `ArticleDraft.model_validate`; `assert_golden_invariants(build_version_content(...))`; `resolutions` dumps `== [{"findingId": "F1", "action": "fixed", "note": "Addressed the finding in the revised conclusion."}]`; conclusion body differs from golden.
5. `test_art_writer_component_fixture_covers_every_component` — 10 cases; last case has no `when`; `{(c.component, c.section_key or (c.section.key if c.component == "introduction" else None))}` covers the 10 variants `headline`, `introduction`, the six section keys, `pull_quote`, `cta`; the `when.promptContains` list equals rule 10's list.
6. `test_art_writer_component_cases_keep_golden_invariants` — parametrized over the 10 cases; `content = apply_component(golden_content(), ComponentDraft.model_validate(case["output"]))`; `assert_golden_invariants(content)`; the replaced value differs from the golden one.
7. `test_art_revise_two_findings_scenario_fixture` — invariants hold; resolutions dumps equal rule 9's list.

**TDD order and verification.**
1. Write the tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_fixtures.py` → failures `PromptRegistryError: unknown prompt deep_research/packet` and `FileNotFoundError` for the fixture files.
2. Write `.wip` prompt files, complete them, rename; write the fixtures. Green: same command → `19 passed`. Then `tests/foundation/test_found_imports.py` → all passed (the whole prompt tree still parses).
3. Lint: `docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c "ruff check --no-cache tests/articles && ruff format --check --no-cache tests/articles"` → exit 0.

**Acceptance covered.** §5.8 ART golden-path invariants (deep research fixture cites only `S1`–`S5`; writer draft = golden; revise and component fixtures keep every golden invariant); §10.3 "Word-count and structure checks pass on the draft fixture" (fixture level).

### ART-4: Agents (`agents/writer.py`, `agents/deep_research_analyst.py`)

**Files.**
- Create `pkg/agents/writer.py`, `pkg/agents/deep_research_analyst.py`.
- Modify `backend/tests/articles/conftest.py` (test model factory, gateway fixture, numbered sources). Create `backend/tests/articles/test_art_agents.py`.

**Interfaces.**
- Consumes: `LLMGateway.run(spec, *, variables, user_prompt, ctx, route_override, prompt_version, output_check)`, `AgentSpec`, `AgentResult`, `CallContext`; `agents.common.{UNTRUSTED_NOTICE, NumberedSource, render_source_list, resolve_markers}`; `domain.article_assembly` (ART-1); `domain.errors.{OutputRejected, ArticleStructureError, UnknownCitationMarker}`; `domain.config.{BrandProfileValues, WordCountRange}`; contracts `ArticleDraft`, `ComponentDraft`, `ResearchPacket`, `SourceRef`, `FindingResolution`, `RevisionFinding`, `AvoidBundle`. Agent modules never import `pydantic_ai` or `db`.
- Produces, `writer.py`:
  ```python
  WRITER_VARIABLES: tuple[str, ...] = ("untrusted_notice", "brand_name", "brand_voice", "audience", "tone", "avoid_bundle", "word_count_min", "word_count_max", "website")
  WRITER_DRAFT_SPEC = AgentSpec(name=AgentName.WRITER, version="1", prompt_name="writer/draft", output_type=ArticleDraft, max_output_tokens=4500, output_retries=1, timeout_seconds=120.0, reasoning="medium")
  WRITER_REVISE_SPEC = AgentSpec(name=AgentName.WRITER, version="1", prompt_name="writer/revise", output_type=ArticleDraft, max_output_tokens=4500, output_retries=1, timeout_seconds=120.0, reasoning="medium")
  WRITER_COMPONENT_SPEC = AgentSpec(name=AgentName.WRITER, version="1", prompt_name="writer/component", output_type=ComponentDraft, max_output_tokens=2000, output_retries=1, timeout_seconds=120.0, reasoning="medium")

  @dataclass(frozen=True)
  class TopicBrief:
      title: str; hook: str; why_now: str; thesis: str; angle: str; core_argument: str
      mdcopilot_connection: str; target_audience: str; pillar_key: str; pillar_name: str; examples: tuple[str, ...]
  @dataclass(frozen=True)
  class WriterVoice:
      audience: str; tone: str
  @dataclass(frozen=True)
  class DraftRequest:
      topic: TopicBrief; packet: ResearchPacket; numbered: tuple[NumberedSource, ...]; instructions: str | None
  @dataclass(frozen=True)
  class ReviseRequest:
      topic: TopicBrief; packet: ResearchPacket; numbered: tuple[NumberedSource, ...]; base: VersionContent; findings: tuple[RevisionFinding, ...]
  @dataclass(frozen=True)
  class ComponentRequest:
      topic: TopicBrief; packet: ResearchPacket; numbered: tuple[NumberedSource, ...]; base: VersionContent
      component: ArticleComponent; section_key: SectionKey | None; instructions: str | None

  def writer_voice(params: Mapping[str, Any], brand: BrandProfileValues) -> WriterVoice
  def render_brand_voice(brand: BrandProfileValues) -> str
  def render_topic_brief(topic: TopicBrief) -> str
  def render_article(content: VersionContent) -> str
  def component_line(component: ArticleComponent, section_key: SectionKey | None) -> str
  def number_findings(findings: Sequence[RevisionFinding]) -> list[tuple[str, RevisionFinding]]
  def build_variables(*, brand: BrandProfileValues, voice: WriterVoice, avoid: AvoidBundle, word_count: WordCountRange) -> dict[str, object]
  def build_user_prompt(request: DraftRequest | ReviseRequest | ComponentRequest) -> str
  def check_draft(draft: ArticleDraft, numbered: Sequence[NumberedSource]) -> VersionContent
  def check_revision(draft: ArticleDraft, numbered: Sequence[NumberedSource], findings: Sequence[RevisionFinding]) -> list[FindingResolution]
  def check_component(output: ComponentDraft, request: ComponentRequest) -> VersionContent
  async def run_writer_draft(gateway: LLMGateway, *, ctx: CallContext, variables: Mapping[str, object], request: DraftRequest, route_override: Sequence[str] | None, prompt_version: int | None) -> AgentResult[ArticleDraft]
  async def run_writer_revise(gateway: LLMGateway, *, ctx: CallContext, variables: Mapping[str, object], request: ReviseRequest, route_override: Sequence[str] | None, prompt_version: int | None) -> AgentResult[ArticleDraft]
  async def run_writer_component(gateway: LLMGateway, *, ctx: CallContext, variables: Mapping[str, object], request: ComponentRequest, route_override: Sequence[str] | None, prompt_version: int | None) -> AgentResult[ComponentDraft]
  ```
- Produces, `deep_research_analyst.py`:
  ```python
  DEEP_RESEARCH_VARIABLES: tuple[str, ...] = ("untrusted_notice", "brand_name", "brand_voice", "brand_mission", "pillar")
  DEEP_RESEARCH_SPEC = AgentSpec(name=AgentName.DEEP_RESEARCH, version="1", prompt_name="deep_research/packet", output_type=ResearchPacket, max_output_tokens=8000, output_retries=1, timeout_seconds=120.0, reasoning="medium")
  MAX_PACKET_SOURCES = 20
  def pillar_label(key: str, name: str, description: str) -> str
  def build_variables(*, brand: BrandProfileValues, pillar: str) -> dict[str, object]
  def build_user_prompt(*, topic: TopicBrief, numbered: Sequence[NumberedSource]) -> str
  def packet_markers(packet: ResearchPacket) -> list[str]
  def check_packet(packet: ResearchPacket, numbered: Sequence[NumberedSource]) -> None
  def with_source_refs(packet: ResearchPacket, numbered: Sequence[NumberedSource]) -> ResearchPacket
  async def run_deep_research_analyst(gateway: LLMGateway, *, ctx: CallContext, variables: Mapping[str, object], topic: TopicBrief, numbered: Sequence[NumberedSource], route_override: Sequence[str] | None, prompt_version: int | None) -> AgentResult[ResearchPacket]
  ```

**Behaviour rules.**
1. `writer_voice`: `audience` = `params["audience"].strip()` when it is a non-blank string, else `brand.target_audience`; `tone` = `params["tone"].strip()` when non-blank, else `", ".join(brand.tone)`.
2. `render_brand_voice` = `f"Narrative: {brand.narrative}\nTone: {', '.join(brand.tone)}\nAvoid: {', '.join(brand.avoid)}"`.
3. `render_topic_brief` = the lines `Title: {title}`, `Pillar: {pillar_key} ({pillar_name})`, `Hook: {hook}`, `Why now: {why_now}`, `Thesis: {thesis}`, `Angle: {angle}`, `Core argument: {core_argument}`, `MDCopilot connection: {mdcopilot_connection}`, `Target audience: {target_audience}`, `Examples: {"; ".join(examples) or "none"}` joined with `\n`.
4. `render_article(content)` = lines `Title options:`, `- provocative: …`, `- operational: …`, `- visionary: …`, `Pull quote: …`, `CTA: …`, `Excerpt: …`, an empty line, then `content.content_markdown` (joined with `\n`).
5. `component_line`: `"Regenerate component: " + value` where value is `headline`, `introduction`, `pull_quote`, `cta`, or `section/<section_key>` for `section`; `article`/`research` → `ValueError("<component> is not a component regeneration")`.
6. `number_findings`: `[(f"F{i}", finding) for i, finding in enumerate(findings, start=1)]`.
7. Writer `build_variables` returns exactly `WRITER_VARIABLES` keys: `UNTRUSTED_NOTICE`, `brand.name`, `render_brand_voice(brand)`, `voice.audience`, `voice.tone`, `json.dumps(avoid.model_dump(mode="json"), ensure_ascii=False, indent=2)`, `word_count.min`, `word_count.max`, `brand.website`. Deep research `build_variables` returns exactly `DEEP_RESEARCH_VARIABLES`: `UNTRUSTED_NOTICE`, `brand.name`, `render_brand_voice(brand)`, `brand.mission`, `pillar`. `pillar_label` = `f"{key} ({name}): {description}"`.
8. Writer `build_user_prompt`: blocks joined with `"\n\n"`, text ends with `"\n"`:
   - every request: `"# Topic\n" + render_topic_brief(topic)`, `"# Research packet\n" + json.dumps(packet.model_dump(mode="json"), ensure_ascii=False, indent=2)`, `"# Sources\n" + render_source_list(numbered, include_text=False)`;
   - `ReviseRequest` and `ComponentRequest` then: `"# Current article\n" + render_article(base)`;
   - `ReviseRequest` then: `"# Findings\n"` + one line per `number_findings` entry: `f"{ref} ({'required' if f.required else 'optional'}, {f.origin}) at {f.location}: {f.description} Recommended revision: {f.recommended_revision or 'none'}"`;
   - `ComponentRequest` then: `component_line(component, section_key)`;
   - `DraftRequest`/`ComponentRequest` with non-`None` instructions: `"# Instructions from the editor\n" + instructions`;
   - last block: `Write the article now.` (draft), `Revise the article now.` (revise), `Write only the requested component now.` (component).
   Deep research `build_user_prompt`: `"# Topic\n" + render_topic_brief(topic)`, `"# Sources\n" + render_source_list(numbered, include_text=True)`, `Build the research packet now.` joined the same way.
9. `check_draft(draft, numbered)`: `content = build_version_content(title_options=normalize_title_options(draft.title_options), sections=[normalize_section(s) for s in draft.sections], pull_quote=draft.pull_quote.strip(), cta=draft.cta.strip(), excerpt=draft.excerpt.strip())`; `ArticleStructureError` → `OutputRejected(str(exc))`; then `resolve_markers(list(content.citation_markers), numbered)`; `UnknownCitationMarker` → `OutputRejected("unknown markers: " + ", ".join(exc.args[0]))`; returns `content`.
10. `check_revision(draft, numbered, findings)`: `check_draft` first; `refs = dict(number_findings(findings))`; walk `draft.resolutions` in order: references not in `refs` (de-duplicated, first-appearance order) → `OutputRejected("unknown finding references: F7")`; a reference seen twice → `OutputRejected("duplicate finding references: F1")`; a blank `note` → `OutputRejected("resolution F1 needs a note")`; required references with no resolution → `OutputRejected("missing resolutions for required findings: F2, F3")` (ascending reference order). Checks run in the order listed. Returns `[FindingResolution(finding_id=refs[r.finding_id].finding_id, action=r.action, note=r.note.strip()) for r in draft.resolutions]`.
11. `check_component(output, request)`: `output.component != request.component` → `OutputRejected("expected component <requested>, got <returned>")`; for `section`, `output.section_key != request.section_key` → `OutputRejected("expected sectionKey <requested>, got <returned or None>")`; for `introduction`, `output.section_key not in (None, introduction)` → `OutputRejected("expected sectionKey introduction, got <returned>")`; then `apply_component(request.base, output)` (`ArticleStructureError` → `OutputRejected(str(exc))`); then marker resolution as rule 9; returns the content.
12. `packet_markers(packet)`: first-appearance, de-duplicated, walking in order: inline markers of `summary`; for each key fact the inline markers of `statement`, then `markers`; for each statistic the inline markers of `statement` and `value`, then `markers`; for each counterargument the inline markers of `statement`, then `markers`; `primary_markers`; `supporting_markers`; inline markers of `industry_context`, `mdcopilot_connection`, each `claims_needing_verification` item. `source_refs` is ignored. Inline markers use `CITATION_MARKER_RE`.
13. `check_packet(packet, numbered)`, in order: unknown markers from `packet_markers` via `resolve_markers` → `OutputRejected("unknown markers: …")`; `summary.strip()` empty → `OutputRejected("summary must not be empty")`; first key fact with `markers == []` → `OutputRejected(f"key facts need at least one source marker: {statement[:80]}")`; first statistic with `markers == []` → `OutputRejected(f"statistics need at least one source marker: {statement[:80]}")`.
14. `with_source_refs` returns `packet.model_copy(update={"source_refs": [SourceRef(marker=n.marker, source_id=str(n.source_id)) for n in numbered]})`.
15. Every `run_*` calls `gateway.run(SPEC, variables=variables, user_prompt=build_user_prompt(...), ctx=ctx, route_override=route_override, prompt_version=prompt_version, output_check=<closure>)`; the closure calls the matching `check_*` and returns `None`. After success:
    - `run_writer_draft` returns `dataclasses.replace(result, output=result.output.model_copy(update={"resolutions": []}))`;
    - `run_writer_revise` returns the result with `output.resolutions` replaced by `check_revision(...)` (real finding ids);
    - `run_writer_component` returns the result unchanged;
    - `run_deep_research_analyst` returns the result with `output = with_source_refs(output, numbered)`.
    Gateway errors (`RouteExhausted`, `BudgetExceeded`) propagate unchanged.

**Tests to write first** (`backend/tests/articles/test_art_agents.py`). Conftest additions:
- `def fake_numbered(count: int) -> list[NumberedSource]` — markers `S1..S<count>`, `source_id=uuid7()`, `title=f"Source {i}"`, `publisher="Example Publisher"`, `domain="example.org"`, `url=f"https://example.org/{i}"`, `published_at=datetime(2026, 9, 15, tzinfo=UTC)`, `tier=1`, `access_mode=AccessMode.FULL_TEXT`, `text=f"Source text {i}."`.
- `def seed_brand() -> BrandProfileValues` — `BrandProfileValues.model_validate(load_seed_file("brand_profile.yaml"))`.
- `def sample_topic() -> TopicBrief` — fixed strings: title `Specialist access needs leverage`, hook `Referral queues keep growing`, why_now `New workforce data this week`, thesis `AI should extend specialist reach`, angle `Operational`, core_argument `Leverage beats replacement`, mdcopilot_connection `Specialist digital twins`, target_audience `Clinical leaders`, pillar_key `A`, pillar_name `Specialist Scarcity & Access`, examples `("referral triage",)`.
- `class SequenceModelFactory` with `outputs: list[dict[str, Any]]`, `calls: int`, `infos: list[AgentInfo]`, `build(choice, spec) -> FunctionModel` (snippet below).
- fixture `function_gateway(settings, sessionmaker_committing, monkeypatch)` → factory `(outputs) -> tuple[LLMGateway, SequenceModelFactory]` that patches `mdcopilot_blog.llm.gateway.build_model_factory` to return the factory and calls `build_gateway(settings, sessionmaker_committing, PromptRegistry.from_directory(default_prompt_root(), agents=["deep_research", "writer"]))`.
- `async def llm_rows(sm, trace_id) -> list[LlmCall]` ordered by `created_at, id`.

Tests (every gateway test uses `ctx = CallContext(trace_id=new_trace_id())`, `variables` from `build_variables(brand=seed_brand(), voice=WriterVoice("Clinical leaders", "pragmatic"), avoid=<empty AvoidBundle>, word_count=WordCountRange(min=850, max=1150))` unless stated, `route_override=["openai:writer-a", "google:writer-b"]`, `prompt_version=None`):
1. `test_art_agent_specs_match_contract` — parametrized over the 4 specs; `(name, version, prompt_name, output_type, max_output_tokens, output_retries, timeout_seconds, reasoning)` equal the values in Interfaces.
2. `test_art_build_variables_match_prompt_templates` — parametrized over the 4 prompt names; `set(build_variables(...)) == set(registry.get(name).variables)`; rendering with `registry.render(name, variables)` raises nothing.
3. `test_art_writer_voice_prefers_run_params` — parametrized: `{"audience": "CMIOs", "tone": "plain and direct"}` → `WriterVoice("CMIOs", "plain and direct")`; `{}` → `WriterVoice(brand.target_audience, ", ".join(brand.tone))`; `{"audience": "   ", "tone": 7}` → brand fallback for both.
4. `test_art_render_brand_voice_format` — equals `"Narrative: an amplifier of specialist leverage, not a replacement for physicians\nTone: authoritative, clinically grounded, intellectually sharp, pragmatic, empathetic, evidence-driven\nAvoid: excessive adjectives, generic AI language, fake urgency, exaggerated claims, unsupported statistics, fabricated anecdotes, fabricated quotes, fabricated physician experiences"` (seed brand).
5. `test_art_draft_prompt_blocks` — parametrized instructions `None` / `"Lead with access data"`; prompt starts with `"# Topic\nTitle: Specialist access needs leverage\n"`; contains the packet JSON string and `"# Sources\n" + render_source_list(numbered, include_text=False)`; contains `"# Instructions from the editor\nLead with access data"` iff instructions given; ends with `"Write the article now.\n"`.
6. `test_art_revise_prompt_numbers_findings` — findings `RevisionFinding(finding_id="gate:word_count", origin="quality_gate", description="Body has 700 words.", location="article", recommended_revision=None, required=True)` and `RevisionFinding(finding_id=f"editorial:{uuid7()}:c1", origin="editorial_change", description="Shorten the opening.", location="introduction", recommended_revision="Cut the first sentence.", required=False)` (keyword arguments; contracts reject positional ones); prompt contains `"F1 (required, quality_gate) at article: Body has 700 words. Recommended revision: none"` and `"F2 (optional, editorial_change) at introduction: Shorten the opening. Recommended revision: Cut the first sentence."`, contains `"# Current article\n" + render_article(golden_content())`, ends with `"Revise the article now.\n"`.
7. `test_art_component_line_values` — parametrized over the 10 variants; expected strings as ART-3 rule 10 plus `Regenerate component: headline`.
8. `test_art_component_fixture_lines_match_component_line` — for cases 1–9 of `writer_component.json`, `when.promptContains == component_line(output.component, output.section_key)`; `component_line("headline", None)` equals the headline line; `build_user_prompt(ComponentRequest(... component=SECTION, section_key=EVIDENCE ...))` contains `Regenerate component: section/evidence`.
9. `test_art_check_draft_accepts_golden` — `check_draft(golden_draft(), fake_numbered(5)).citation_markers` has set `{"S1".."S5"}`.
10. `test_art_check_draft_rejections` — parametrized: evidence body `+ " [S6]"` with 5 sources → `OutputRejected`, `str(exc) == "unknown markers: S6"`; CTA `+ " [S1]"` → `"citation markers are allowed only in section bodies: cta"`.
11. `test_art_check_revision_rejections` — findings: F1 required, F2 required; parametrized resolutions → message: `[F1 fixed, F7 fixed]` → `unknown finding references: F7`; `[F1, F1]` → `duplicate finding references: F1`; `[F1 note "  ", F2]` → `resolution F1 needs a note`; `[F1]` → `missing resolutions for required findings: F2`.
12. `test_art_check_component_rejections` — parametrized (request, output → message): headline requested, CTA output → `expected component headline, got cta`; section/evidence requested, output sectionKey `context` → `expected sectionKey evidence, got context`; section/context requested, section heading `None` → `section context needs a heading`; headline requested, provocative option `+ " [S1]"` → `citation markers are allowed only in section bodies: titleOptions.provocative`.
13. `test_art_check_packet_accepts_fixture` — `check_packet(<deep_research_packet.json output>, fake_numbered(6))` returns `None`.
14. `test_art_check_packet_rejections` — parametrized on the fixture packet: first key fact markers `["S7"]` → `unknown markers: S7`; summary `" "` → `summary must not be empty`; first key fact markers `[]` → `key facts need at least one source marker: <statement[:80]>`; first statistic markers `[]` → `statistics need at least one source marker: <statement[:80]>`.
15. `test_art_run_writer_draft_retries_unknown_marker` — outputs `[golden dump with " [S9]" appended to the evidence body, golden dump]`, numbered 5; result `output == golden_draft()` (resolutions `[]`), `factory.calls == 2`, `result.attempts == 1`; `llm_rows` → exactly 1 row: `status == "ok"`, `agent_name == "writer"`, `prompt_name == "writer/draft"`, `prompt_version == 1`, `provider_requested == "openai"`, `model_requested == "writer-a"`.
16. `test_art_run_writer_draft_exhausts_route_on_persistent_bad_output` — outputs `[golden dump with pull quote + " [S1]"]`; `pytest.raises(RouteExhausted)`; `factory.calls == 4`; 2 rows, both `status == "error"`, `error_class == "UnexpectedModelBehavior"`, `provider_requested` values `["openai", "google"]`.
17. `test_art_run_writer_draft_sends_avoid_bundle_and_brand` — avoid `AvoidBundle(recent_articles=[RecentArticleRef(title="Inbox load is a clinical problem", core_argument="Portal messages eat clinic time", opening_sentence="Every portal message costs minutes.")], recent_titles=["Inbox load is a clinical problem"], recent_openings=["Every portal message costs minutes."], recent_ctas=["Book a walkthrough of MDCopilot today"], recent_primary_sources=["example.org"], overused_phrases=["at the end of the day"], prohibited_language=["revolutionize"])`; outputs `[golden dump]`; `factory.infos[0].instructions` contains each of `Inbox load is a clinical problem`, `Every portal message costs minutes.`, `Book a walkthrough of MDCopilot today`, `at the end of the day`, `revolutionize`, `MDCopilot`, `850`, `1150`, `https://www.mdcopilot.health`, and `UNTRUSTED_NOTICE`. (Acceptance: avoid bundle and recent articles are Writer inputs.)
18. `test_art_run_writer_draft_forces_empty_resolutions` — output golden dump with `resolutions: [{"findingId": "F1", "action": "fixed", "note": "n"}]` → `result.output.resolutions == []`.
19. `test_art_run_writer_revise_maps_finding_references` — findings as test 6; outputs `[golden dump with resolutions [], golden dump with resolutions [{"findingId": "F1", "action": "fixed", "note": " Expanded the evidence section. "}]]`; `factory.calls == 2`; `result.output.resolutions == [FindingResolution(finding_id="gate:word_count", action="fixed", note="Expanded the evidence section.")]`; 1 row with `prompt_name == "writer/revise"`.
20. `test_art_run_writer_component_retries_wrong_component` — request headline on `golden_content()`; outputs `[<cta case output from writer_component.json>, <headline case output>]`; `factory.calls == 2`; `result.output.component == "headline"`; row `prompt_name == "writer/component"`.
21. `test_art_run_deep_research_retries_and_fills_source_refs` — numbered 6; variables from deep research `build_variables(brand=seed_brand(), pillar=pillar_label("A", "Specialist Scarcity & Access", "Why patients wait"))`; outputs `[fixture packet with first key fact markers ["S9"], fixture packet]`; `factory.calls == 2`; `result.output.source_refs == [SourceRef(marker=f"S{i}", source_id=str(n.source_id)) for i, n in enumerate(numbered, 1)]`; row `agent_name == "deep_research"`, `prompt_name == "deep_research/packet"`.
22. `test_art_run_passes_route_override_and_prompt_version` — `run_writer_draft(..., route_override=["google:only-model"], prompt_version=1)` with golden output → 1 row, `provider_requested == "google"`, `model_requested == "only-model"`, `prompt_version == 1`.
23. `test_art_deep_research_prompt_includes_source_text` — `render_source_list(numbered, include_text=True) in deep_research_analyst.build_user_prompt(topic=sample_topic(), numbered=numbered)`; the prompt ends with `"Build the research packet now.\n"`.
24. `test_art_agent_modules_do_not_import_pydantic_ai` — parametrized over both module files; `"pydantic_ai" not in Path(module.__file__).read_text()` and `"mdcopilot_blog.db" not in` the same text.

**Implementation notes.** Test model factory (pattern verified in the backend:dev image 2026-09-17: `ToolCallPart(info.output_tools[0].name, payload)`; `AgentInfo.instructions` carries the rendered system prompt; an output validator that raises leads to a second request):
```python
class SequenceModelFactory:
    def __init__(self, outputs: Sequence[dict[str, Any]]) -> None:
        self.outputs = [copy.deepcopy(o) for o in outputs]
        self.calls = 0
        self.infos: list[AgentInfo] = []

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model:
        async def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            payload = self.outputs[min(self.calls, len(self.outputs) - 1)]
            self.calls += 1
            self.infos.append(info)
            return ModelResponse(
                parts=[ToolCallPart(info.output_tools[0].name, copy.deepcopy(payload))],
                usage=RequestUsage(input_tokens=10, output_tokens=10),
            )
        return FunctionModel(respond, model_name=f"test:{spec.name.value}")
```
The gateway turns `OutputRejected` from `output_check` into `ModelRetry` (CONTRACT §0.2); agent modules raise only `OutputRejected`.

**TDD order and verification.**
1. Write conftest additions and the 24 tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_agents.py` → collection error `ModuleNotFoundError: No module named 'mdcopilot_blog.agents.writer'`.
2. Implement `writer.py`, then `deep_research_analyst.py`. Green: same command → `53 passed`. `tests/foundation/test_found_imports.py` → all passed.
3. Lint paths: `src/mdcopilot_blog/domain/article_assembly.py src/mdcopilot_blog/api/schemas_articles.py src/mdcopilot_blog/agents/writer.py src/mdcopilot_blog/agents/deep_research_analyst.py` → exit 0.

**Acceptance covered.** §10.3 "Deep Research Analyst" (agent); "Writer: typed `ArticleDraft`, avoid bundle + recent articles inputs, … revise resolutions, component regeneration" (agent level); "Unknown citation markers rejected" (agent output check); §5.6 owner test "a `FunctionModel` returning an unknown marker and then a valid one" for each ART agent.

### ART-5: Version persistence (`services/versions.py`)

**Files.**
- Create `pkg/services/versions.py`.
- Modify `backend/tests/articles/conftest.py` (graph and row helpers). Create `backend/tests/articles/test_art_versions.py`.

**Interfaces.**
- Consumes: ORM `Article`, `ArticleVersion`, `ResearchPacketRecord`, `VersionSeo`, `ArticleSource`, `LedgerSource`; `domain.article_assembly` (ART-1); contracts `ResearchPacket`, `FindingResolution`, `SEOMetadata`, `SocialCopy`, `TitleOptions`, `ArticleSection`; `api.schemas_articles.{VersionDiffOut, FieldChangeOut}` (ART-2); `sqlalchemy.dialects.postgresql.insert`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class NewVersion:
      article_id: uuid.UUID
      parent_version_id: uuid.UUID | None
      change_kind: ChangeKind
      change_scope: dict[str, Any]
      content: VersionContent
      resolutions: Sequence[FindingResolution]
      research_packet_id: uuid.UUID | None
      created_by: uuid.UUID | None
      created_by_kind: Literal["agent", "human"]
      dbos_workflow_id: str | None
      dbos_step_id: int | None

  def change_scope(*, component: ArticleComponent | None, section_key: SectionKey | None, instructions: str | None, finding_ids: Sequence[str]) -> dict[str, Any]
  async def lock_article(db: AsyncSession, article_id: uuid.UUID) -> Article | None
  async def next_version_no(db: AsyncSession, article_id: uuid.UUID) -> int
  async def find_step_version(db: AsyncSession, *, dbos_workflow_id: str | None, dbos_step_id: int | None) -> ArticleVersion | None
  async def insert_version(db: AsyncSession, new: NewVersion) -> tuple[ArticleVersion, bool]
  def version_content(row: ArticleVersion) -> VersionContent
  async def get_version(db: AsyncSession, *, article_id: uuid.UUID, version_id: uuid.UUID) -> ArticleVersion | None
  async def list_versions(db: AsyncSession, article_id: uuid.UUID) -> list[ArticleVersion]
  async def next_packet_version(db: AsyncSession, article_id: uuid.UUID) -> int
  async def find_step_packet(db: AsyncSession, *, dbos_workflow_id: str | None, dbos_step_id: int | None) -> ResearchPacketRecord | None
  async def insert_research_packet(db: AsyncSession, *, article_id: uuid.UUID, research_run_id: uuid.UUID | None, packet: ResearchPacket, source_ids: Sequence[uuid.UUID], created_by: uuid.UUID | None, dbos_workflow_id: str | None, dbos_step_id: int | None) -> tuple[ResearchPacketRecord, bool]
  async def latest_packet(db: AsyncSession, article_id: uuid.UUID) -> ResearchPacketRecord | None
  def packet_source_ids(record: ResearchPacketRecord) -> list[uuid.UUID]
  async def newest_seo(db: AsyncSession, version_id: uuid.UUID) -> VersionSeo | None
  async def insert_seo_copy(db: AsyncSession, *, version_id: uuid.UUID, seo: SEOMetadata, social: SocialCopy | None, created_by: uuid.UUID | None) -> VersionSeo
  async def version_sources(db: AsyncSession, version_id: uuid.UUID) -> list[tuple[ArticleSource, LedgerSource]]
  async def diff_versions(db: AsyncSession, *, article_id: uuid.UUID, from_id: uuid.UUID, to_id: uuid.UUID) -> VersionDiffOut | None
  ```

**Behaviour rules.**
1. `change_scope` returns exactly `{"component": <value or None>, "sectionKey": <value or None>, "instructions": <str or None>, "findingIds": list(finding_ids)}`.
2. `lock_article`: `select(Article).where(Article.id == article_id).with_for_update().execution_options(populate_existing=True)`; `None` when missing. Every version and packet insert happens in a transaction that holds this lock, so `next_version_no` (`coalesce(max(version_no), 0) + 1` for the article) and `next_packet_version` (same over `blog_research_packets.version`) cannot race.
3. `find_step_version` / `find_step_packet`: `None` when either id is `None`; else the row with that `(dbos_workflow_id, dbos_step_id)`.
4. `insert_version(db, new)` (caller holds the lock; flush only):
   1. if `find_step_version` finds a row → return `(row, False)`;
   2. `markers = new.content.citation_markers`; packet = `db.get(ResearchPacketRecord, new.research_packet_id)` when the id is set; `mapping = resolve_packet_markers(markers, packet_source_ids(packet) if packet else [])` (raises `UnknownCitationMarker`, nothing written);
   3. insert `blog_article_versions` with `version_no = await next_version_no(...)`, `parent_version_id`, `change_kind.value`, `change_scope`, `title_options = content.title_options.model_dump(mode="json")`, `sections = [s.model_dump(mode="json") for s in content.sections]`, `pull_quote`, `cta`, `excerpt`, `content_markdown`, `word_count`, `citation_markers = list(markers)`, `resolutions = [r.model_dump(mode="json") for r in new.resolutions]`, `research_packet_id`, `created_by`, `created_by_kind`, `dbos_workflow_id`, `dbos_step_id`. With both dbos ids set the statement is `insert(...).on_conflict_do_nothing(index_elements=["dbos_workflow_id", "dbos_step_id"], index_where=text("dbos_workflow_id IS NOT NULL")).returning(ArticleVersion.id)`; a `None` return means a concurrent duplicate → return `(find_step_version(...), False)`. Without dbos ids it is a plain insert;
   4. insert one `blog_article_sources` row per marker in `markers` order: `source_id = mapping[marker]`, `is_primary = marker in ResearchPacket.model_validate(packet.packet).primary_markers`;
   5. return `(row, True)`.
5. `version_content(row)`: `VersionContent` from the stored columns (`TitleOptions.model_validate`, `ArticleSection.model_validate` per item, `tuple(citation_markers)`), no re-validation of structure.
6. `get_version`: the row only if `row.article_id == article_id`. `list_versions`: `version_no` descending.
7. `insert_research_packet` (caller holds the lock; flush only): same idempotency as rule 4.1/4.3 against `uq_blog_research_packets_wf_step`; inserts `version = next_packet_version`, `research_run_id`, `packet = packet.model_dump(mode="json")`, `summary = packet.summary`, `source_ids = [str(i) for i in source_ids]`, `created_by`, dbos ids. `latest_packet`: highest `version`. `packet_source_ids`: `[uuid.UUID(s) for s in record.source_ids]`.
8. `newest_seo`: rows for the version ordered `created_at desc, id desc`, first. `insert_seo_copy`: inserts `VersionSeo(version_id, seo=seo.model_dump(mode="json"), social=social.model_dump(mode="json") if social else None, slug=seo.slug, created_by, dbos ids None)`; flush.
9. `version_sources`: joined rows ordered by `marker_number(marker)` ascending.
10. `diff_versions`: loads both versions with `get_version` (returns `None` if either is missing); loads `newest_seo` for each; returns `VersionDiffOut(from_version_id, to_version_id, from_version_no, to_version_no, unified_diff=unified_markdown_diff(from.content_markdown, to.content_markdown, before_no=from.version_no, after_no=to.version_no), field_changes=[FieldChangeOut(field=k, from_value=a, to_value=b) for k, a, b in field_changes(diff_fields(from_content, from_seo), diff_fields(to_content, to_seo))])`, with SEO parsed by `SEOMetadata.model_validate(row.seo)`.

**Tests to write first** (`backend/tests/articles/test_art_versions.py`; `db_session`, rolled back). Conftest additions: `async def graph(make_article_graph, db, **kw) -> ArticleGraphIds` (thin wrapper returning `await make_article_graph(db, **kw)`); `def human_version(base: VersionContent, *, article_id, parent_id, packet_id, pull_quote: str | None = None, dbos: tuple[str, int] | None = None) -> NewVersion` (content = `edit_content(base, content_markdown=None, title_options=None, pull_quote=pull_quote, cta=None, excerpt=None)`, change kind `human_edit`, scope `change_scope(component=None, section_key=None, instructions=None, finding_ids=[])`, `created_by=None`, `created_by_kind="human"`).
1. `test_art_insert_version_numbers_and_records_sources` — `g = graph(status=READY_FOR_REVIEW)`; `base = version_content(await db.get(ArticleVersion, g.version_id))`; `await lock_article(db, g.article_id)`; `row, inserted = insert_version(db, human_version(base, article_id=g.article_id, parent_id=g.version_id, packet_id=g.packet_id, pull_quote="Specialist time is the scarcest resource in the clinic."))`; `inserted is True`, `row.version_no == 2`, `row.parent_version_id == g.version_id`, `row.change_scope == {"component": None, "sectionKey": None, "instructions": None, "findingIds": []}`; sources for `row.id` ordered by marker number: markers `== list(row.citation_markers)`, each `source_id == packet_source_ids(packet)[marker_number(m) - 1]`, each `is_primary == (m in ResearchPacket.model_validate(packet.packet).primary_markers)`.
2. `test_art_insert_version_is_idempotent_per_workflow_step` — twice with `dbos=("wf-art-versions", 7)`; second returns `(same id, False)`; `count(versions for article) == 2`; `count(article_sources for row) == len(row.citation_markers)`.
3. `test_art_insert_version_rejects_markers_outside_packet` — content with evidence body `+ " [S6]"` (packet has 5 sources); `pytest.raises(UnknownCitationMarker)` with `args[0] == ["S6"]`; version count stays 1.
4. `test_art_insert_research_packet_next_version` — `packet = ResearchPacket.model_validate(<deep_research_packet.json output>)`, `ids = graph source_ids[:5]`; `record, inserted = insert_research_packet(...)` → `inserted is True`, `record.version == 2`, `record.source_ids == [str(i) for i in ids]`, `record.summary == packet.summary`; `latest_packet(db, g.article_id).id == record.id`; with dbos ids `("wf-art-packet", 3)` twice → same id, second `inserted is False`.
5. `test_art_insert_seo_copy_and_newest_seo` — `old = newest_seo(db, g.version_id)` (golden SEO from the graph); `new = insert_seo_copy(db, version_id=g.version_id, seo=merge_seo(SEOMetadata.model_validate(old.seo), {"seo_title": "New SEO title"}), social=None, created_by=None)`; `newest_seo(db, g.version_id).id == new.id`; `new.slug == old.slug`; `new.seo["seoTitle"] == "New SEO title"`.
6. `test_art_list_versions_newest_first` — after one insert, `[v.version_no for v in list_versions(db, g.article_id)] == [2, 1]`; `get_version(db, article_id=<other graph article>, version_id=g.version_id) is None` (second graph built with `with_seo=False`).
7. `test_art_diff_versions_unified_and_field_changes` — v2 content from `edit_content(base, content_markdown=<assembled golden with the context heading line replaced by "## Why specialists wait">, pull_quote="Specialist time is the scarcest resource in the clinic.", ...)`; `insert_seo_copy` for v2 with `seo_title="New SEO title"`; `out = diff_versions(db, article_id, from_id=v1, to_id=v2)`; `out.unified_diff.startswith("--- v1\n+++ v2\n@@ ")`; lines include `f"-## {golden context heading}"` and `"+## Why specialists wait"`; `out.unified_diff == unified_markdown_diff(v1.content_markdown, v2.content_markdown, before_no=1, after_no=2)`; `[(c.field, c.from_value, c.to_value) for c in out.field_changes] == [("pullQuote", golden pull quote, "Specialist time is the scarcest resource in the clinic."), ("seo.seoTitle", golden seo title, "New SEO title")]`.
8. `test_art_diff_versions_same_version_is_empty` — `from_id == to_id == g.version_id` → `unified_diff == ""`, `field_changes == []`; unknown `to_id` → `None`.
9. `test_art_version_content_round_trips_row` — `version_content(v1_row).content_markdown == v1_row.content_markdown`; `.sections` dumps `== v1_row.sections`; `.word_count == v1_row.word_count`.

**Implementation notes.** The partial-index `ON CONFLICT` form compiles to `ON CONFLICT (dbos_workflow_id, dbos_step_id) WHERE dbos_workflow_id IS NOT NULL DO NOTHING RETURNING …` (verified in the backend:dev image 2026-09-17):
```python
stmt = (
    insert(ArticleVersion)
    .values(**values)
    .on_conflict_do_nothing(index_elements=["dbos_workflow_id", "dbos_step_id"], index_where=text("dbos_workflow_id IS NOT NULL"))
    .returning(ArticleVersion.id)
)
inserted_id = await db.scalar(stmt)
```
`blog_article_versions` rejects every UPDATE (FOUND trigger), so no code path assigns to a loaded `ArticleVersion` attribute.

**TDD order and verification.**
1. Write the 9 tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_versions.py` → collection error `ModuleNotFoundError: No module named 'mdcopilot_blog.services.versions'`.
2. Implement. Green: same command → `9 passed`.
3. Lint paths: ART-4 paths plus `src/mdcopilot_blog/services/versions.py` → exit 0.

**Acceptance covered.** §10.3 "Version history and diff API" (service layer); "Unknown citation markers rejected" (persistence guard); §5.5 step body rule 2 (insert with dbos ids, `ON CONFLICT DO NOTHING`, read back).

### ART-6: Step seams (`services/article_steps.py`)

**Files.**
- Modify `pkg/services/article_steps.py` (FOUND stub; keep `PacketResult`, `VersionResult` and every signature byte-identical).
- Modify `backend/tests/articles/conftest.py` (committing graph and step-context factories). Create `backend/tests/articles/test_art_steps.py`.

**Interfaces.**
- Consumes: `StepContext` (`sc.sessionmaker`, `sc.gateway`, `sc.config`, `sc.brand`, `sc.call`, `sc.with_ids`); `agents.common.number_sources`; `agents.writer` and `agents.deep_research_analyst` (ART-4); `services.versions` (ART-5); `domain.article_assembly`; ORM `Article`, `BlogRun`, `TopicCandidateRecord`, `Topic`, `ContentPillar`, `ResearchRun`, `LedgerSource`, `ResearchPacketRecord`, `ArticleVersion`; `domain.errors.InsufficientEvidence`.
- Produces (CONTRACT §5.6, unchanged):
  ```python
  async def ensure_article(sc: StepContext, *, run_id: uuid.UUID, candidate_id: uuid.UUID) -> uuid.UUID
  class PacketResult(BaseModel): packet_id: uuid.UUID; version: int
  async def build_research_packet(sc: StepContext, *, article_id: uuid.UUID, research_run_id: uuid.UUID) -> PacketResult
  async def latest_packet_id(db: AsyncSession, *, article_id: uuid.UUID) -> uuid.UUID | None
  class VersionResult(BaseModel): version_id: uuid.UUID; version_no: int; word_count: int; title_changed: bool
  async def write_draft(sc: StepContext, *, article_id: uuid.UUID, packet_id: uuid.UUID, avoid: AvoidBundle, instructions: str | None = None) -> VersionResult
  async def revise_article(sc: StepContext, *, article_id: uuid.UUID, base_version_id: uuid.UUID, findings: Sequence[RevisionFinding], avoid: AvoidBundle, change_kind: ChangeKind) -> VersionResult
  async def regenerate_component(sc: StepContext, *, article_id: uuid.UUID, base_version_id: uuid.UUID, component: ArticleComponent, section_key: SectionKey | None, instructions: str | None, avoid: AvoidBundle) -> VersionResult
  ```

**Behaviour rules (all seams).**
1. Plain `async def`, no DBOS import; each opens its own sessions with `async with sc.sessionmaker() as db`, commits before returning, and never changes `blog_articles.status` or `blog_runs.status` (§5.5 rules 1, 4, 5).
2. No database lock is held during an LLM call: session A reads inputs and closes; the agent runs; session B takes `versions.lock_article`, re-runs the idempotency lookup, inserts, updates the head, commits.
3. Agent calls use `ctx = sc.with_ids(article_id=article_id).call`, `route_override = sc.config.routes[spec.name.value]`, `prompt_version = sc.config.prompt_versions.get(spec.prompt_name)`.
4. Idempotency: when `sc.call.dbos_workflow_id` and `sc.call.dbos_step_id` are set, the seam first looks up its row by those ids (`find_step_packet` / `find_step_version`) in session A and, if found, returns the result built from that row without calling the agent. When they are `None` it always inserts.
5. Shared loading (private helper `_load_brief(db, article)`): `Topic` by `article.topic_id`, `TopicCandidateRecord` by `article.candidate_id`, `ContentPillar` by `topic.pillar_key` → `TopicBrief(title=topic.title, hook=candidate.hook, why_now=candidate.why_now, thesis=topic.thesis, angle=topic.angle, core_argument=topic.core_argument, mdcopilot_connection=candidate.mdcopilot_connection, target_audience=candidate.target_audience, pillar_key=topic.pillar_key, pillar_name=pillar.name if pillar else topic.pillar_key, examples=tuple(topic.examples))`; pillar description `pillar.description if pillar else ""`.
6. Packet sources (private `_packet_numbered(db, record)`): load `LedgerSource` rows for `packet_source_ids(record)`; a missing id → `LookupError(f"packet source {id} not found")`; `number_sources(rows_in_stored_order, preserve_order=True)`, so marker `S{i+1}` is `record.source_ids[i]`.
7. Writer variables: `writer.build_variables(brand=sc.brand, voice=writer.writer_voice(run.params, sc.brand), avoid=avoid, word_count=sc.config.word_count)` where `run = BlogRun` of `article.run_id`.
8. Head title after a new version (private `_apply_head_title(article, new_options, *, first_draft)`): first draft → `title = new_options.operational`, `selected_title_key = "operational"`; otherwise, when `selected_title_key` is `provocative`, `operational` or `visionary`, `title = title_for_key(new_options, key)`; `custom` or `None` → unchanged.
9. `VersionResult.title_changed` = parent is `None` or the new `title_options` differ from the parent version's. `word_count` and `version_no` come from the version row.

**Behaviour rules per seam.**
10. `ensure_article`, one session, in order: candidate row `SELECT … FOR UPDATE` → missing: `LookupError(f"candidate {candidate_id} not found")`; `candidate.run_id != run_id` → `ValueError(f"candidate {candidate_id} belongs to run {candidate.run_id}, not {run_id}")`; live article (`run_id`, `candidate_id`, status not in `REJECTED`, `SUPERSEDED`) exists → return its id; `candidate.status != "SELECTED"` → `ValueError(f"candidate {candidate_id} is {candidate.status}, expected SELECTED")`; topic with `candidate_id` missing → `ValueError(f"candidate {candidate_id} has no topic row")`; insert `blog_articles(run_id, run_date=<blog_runs.run_date>, candidate_id, topic_id, status="DRAFTING", slug=None, title=None, selected_title_key=None, pillar_key=topic.pillar_key, category=sc.config.default_category, tags=[])` with `on_conflict_do_nothing(index_elements=["run_id", "candidate_id"], index_where=text("status NOT IN ('REJECTED','SUPERSEDED')"))`; read back the live article id; commit; return it.
11. `build_research_packet`:
    - session A: `article` (missing → `LookupError(f"article {article_id} not found")`); step lookup (rule 4); `ResearchRun` (missing → `LookupError(f"research run {research_run_id} not found")`); `source_ids = [uuid.UUID(s) for s in run.source_ids][:MAX_PACKET_SOURCES]`; empty → `InsufficientEvidence(str(research_run_id), 0, 1, <count of run.queries items whose "status" == "ok">)`; `LedgerSource` rows in that order (missing id → `LookupError(f"ledger source {id} not found")`); `numbered = number_sources(rows, preserve_order=True)`; brief and pillar (rule 5).
    - agent: `run_deep_research_analyst(sc.gateway, ctx=…, variables=deep_research_analyst.build_variables(brand=sc.brand, pillar=pillar_label(topic.pillar_key, pillar_name, pillar_description)), topic=brief, numbered=numbered, route_override=…, prompt_version=…)`.
    - session B: lock article; `insert_research_packet(db, article_id, research_run_id, packet=result.output, source_ids=[n.source_id for n in numbered], created_by=None, dbos ids from sc.call)`; commit; `PacketResult(packet_id=record.id, version=record.version)`.
12. `latest_packet_id(db, *, article_id)` = `(await versions.latest_packet(db, article_id)).id` or `None`. Read only.
13. `write_draft`:
    - session A: article (`LookupError`); step lookup; packet record by `packet_id` (missing → `LookupError(f"packet {packet_id} not found")`; `record.article_id != article_id` → `ValueError(f"packet {packet_id} belongs to article {record.article_id}, not {article_id}")`); numbered (rule 6); brief; run params; `parent = article.current_version_id`.
    - agent: `run_writer_draft(..., request=DraftRequest(topic=brief, packet=ResearchPacket.model_validate(record.packet), numbered=tuple(numbered), instructions=instructions))`; `content = writer.check_draft(result.output, numbered)`.
    - session B: lock article; step re-lookup; `change_kind = DRAFT` when the article has no version rows, else `ARTICLE_REGENERATION`; scope `change_scope(component=None if DRAFT else ArticleComponent.ARTICLE, section_key=None, instructions=instructions, finding_ids=[])`; `parent_version_id = article.current_version_id` (locked value); `insert_version(NewVersion(..., resolutions=[], research_packet_id=packet_id, created_by=None, created_by_kind="agent", dbos ids))`; when inserted: `article.current_version_id = row.id` and rule 8 with `first_draft = (change_kind == DRAFT)`; commit.
14. `revise_article`:
    - pre-checks before any I/O: `change_kind not in {REVISION, FIX_PASS}` → `ValueError(f"revise_article accepts change_kind revision or fix_pass, not {change_kind}")`; `not findings` → `ValueError("revise_article needs at least one finding")`.
    - session A: article; step lookup; `base_version_id != article.current_version_id` → `ValueError(f"base version {base_version_id} is not the current version {article.current_version_id}")`; base row; `base.research_packet_id is None` → `ValueError(f"version {base_version_id} has no research packet")`; packet, numbered, brief, params.
    - agent: `run_writer_revise(..., request=ReviseRequest(topic, packet, tuple(numbered), base=version_content(base_row), findings=tuple(findings)))`; `content = writer.check_draft(result.output, numbered)`.
    - session B: lock; re-lookup; the base-is-current check again (same `ValueError`); insert with `parent=base_version_id`, `change_kind`, scope `change_scope(component=None, section_key=None, instructions=None, finding_ids=[f.finding_id for f in findings])`, `resolutions=result.output.resolutions` (real ids), `research_packet_id=base.research_packet_id`; head update (rule 8, not first draft); commit.
15. `regenerate_component`:
    - pre-checks before any I/O, in order: `component in {ARTICLE, RESEARCH}` → `ValueError(f"{component} is not a component regeneration")`; `component == SECTION and section_key is None` → `ValueError("section regeneration needs a section key")`; `component == SECTION and section_key == INTRODUCTION` → `ValueError("use component introduction for the introduction")`; `component != SECTION and section_key is not None` → `ValueError(f"{component} takes no section key")`.
    - session A and B as rule 14 (same base checks), with `run_writer_component(..., request=ComponentRequest(topic, packet, tuple(numbered), base=version_content(base_row), component=component, section_key=section_key, instructions=instructions))`, `content = writer.check_component(result.output, request)`, `change_kind=COMPONENT_REGENERATION`, scope `change_scope(component=component, section_key=section_key, instructions=instructions, finding_ids=[])`, `resolutions=[]`, `research_packet_id=base.research_packet_id`. Sections other than the target are the base's objects (ART-1 rule 5), so their stored dumps are identical.

**Tests to write first** (`backend/tests/articles/test_art_steps.py`; committed data). Conftest additions:
- fixture `committed_graph(sessionmaker_committing, make_article_graph)` → `async (**kw) -> ArticleGraphIds`: builds in a `sessionmaker_committing()` session and commits.
- fixture `art_step_context(mock_step_context)` → `async (scenario: str | None = None) -> StepContext` returning `await mock_step_context(agents=["deep_research", "writer"], scenario=scenario)`.
- `EMPTY_AVOID = AvoidBundle(recent_articles=[], recent_titles=[], recent_openings=[], recent_ctas=[], recent_primary_sources=[], overused_phrases=[], prohibited_language=[])`.
- `async def fresh_article(sc, committed_graph) -> tuple[ArticleGraphIds, uuid.UUID]`: `g = await committed_graph(status=ArticleStatus.SUPERSEDED, with_seo=False)`; returns `(g, await article_steps.ensure_article(sc, run_id=g.run_id, candidate_id=g.candidate_id))`.
- `async def fetch(sm, model, id)` and `async def count_rows(sm, model, **filters) -> int`.

Every test obtains `sc = await art_step_context()` first (it truncates and seeds), then builds its graph.
1. `test_art_ensure_article_returns_live_article` — `g = committed_graph(status=DRAFTING)`; result `== g.article_id`; articles with `(g.run_id, g.candidate_id)` count `== 1`.
2. `test_art_ensure_article_creates_drafting_article_after_supersede` — `(g, new) = fresh_article(...)`; `new != g.article_id`; row: `status == "DRAFTING"`, `run_id == g.run_id`, `run_date == <BlogRun g.run_id>.run_date`, `candidate_id == g.candidate_id`, `topic_id == g.topic_id`, `pillar_key == <Topic g.topic_id>.pillar_key`, `category == sc.config.default_category`, `tags == []`, `title is None`, `slug is None`, `current_version_id is None`; a second `ensure_article` returns `new`.
3. `test_art_ensure_article_rejects_bad_candidates` — parametrized: (a) superseded graph, then `UPDATE app.blog_topic_candidates SET status='PASSED' WHERE id=:cid` → `ValueError`, message `candidate <cid> is PASSED, expected SELECTED`; (b) `run_id=uuid7()` → `ValueError`, `candidate <cid> belongs to run <g.run_id>, not <other>`; (c) `candidate_id=uuid7()` → `LookupError`, `candidate <x> not found`.
4. `test_art_build_research_packet_creates_versioned_packets` — `(g, new) = fresh_article`; `r1 = build_research_packet(sc, article_id=new, research_run_id=g.research_run_id)` → `r1.version == 1`; record: `research_run_id == g.research_run_id`, `source_ids == <ResearchRun>.source_ids[:20]`, `ResearchPacket.model_validate(packet).source_refs == [SourceRef(marker=f"S{i}", source_id=s) for i, s in enumerate(record.source_ids, 1)]`, `summary == packet summary`, `created_by is None`, `dbos_workflow_id is None`; `LlmCall` rows with `agent_name == "deep_research"` and `article_id == new`: 1, `status == "ok"`, `run_id == sc.call.run_id`; `r2 = build_research_packet(...)` again → `r2.version == 2`, `r2.packet_id != r1.packet_id`, and the r1 record still exists with its original `packet` JSON. (Acceptance: regenerating research creates a new packet version and keeps the old one.)
5. `test_art_build_research_packet_is_idempotent_per_workflow_step` — `sc2 = dataclasses.replace(sc, call=dataclasses.replace(sc.call, dbos_workflow_id="wf-art-steps-packet", dbos_step_id=4))`; two calls return equal `PacketResult`; packets for `new` count `1`; deep research `LlmCall` rows for `new` count `1`.
6. `test_art_build_research_packet_without_sources_raises` — `UPDATE app.blog_research_runs SET source_ids='[]'::jsonb WHERE id=:rr`; `pytest.raises(InsufficientEvidence)`; `exc.args[:3] == (str(g.research_run_id), 0, 1)`; `exc.args[3] ==` count of `queries` items with `status == "ok"` read from the row; no packet rows for `new`.
7. `test_art_latest_packet_id` — `latest_packet_id(db, article_id=new) is None`; after two `build_research_packet` calls it equals the second `packet_id`.
8. `test_art_write_draft_first_draft` — `(g, new)`, `p = build_research_packet(...)`; `res = write_draft(sc, article_id=new, packet_id=p.packet_id, avoid=EMPTY_AVOID)`; `res.version_no == 1`, `res.title_changed is True`; row: `change_kind == "draft"`, `parent_version_id is None`, `change_scope == {"component": None, "sectionKey": None, "instructions": None, "findingIds": []}`, `created_by_kind == "agent"`, `research_packet_id == p.packet_id`, `sections == [s.model_dump(mode="json") for s in golden_draft().sections]`, `content_markdown == assemble_markdown(golden_draft().sections)`, `word_count == res.word_count == body_word_count(golden_draft().sections)`, `sc.config.word_count.min <= word_count <= sc.config.word_count.max`, `resolutions == []`; article sources: markers `== row.citation_markers`, `source_id == uuid.UUID(packet.source_ids[marker_number(m) - 1])`; article head: `current_version_id == res.version_id`, `title == golden operational`, `selected_title_key == "operational"`, `status == "DRAFTING"`; `LlmCall` writer row: `prompt_name == "writer/draft"`, `article_id == new`, `provider_served == "openai"`. (Acceptance: word-count and structure checks pass on the draft; P3.)
9. `test_art_write_draft_regeneration_keeps_old_version` — repeats the setup and first `write_draft` of test 8 in this test, then `res2 = write_draft(..., instructions="Lead with the workforce data")`; `res2.version_no == 2`, `res2.title_changed is False`; v2 row: `change_kind == "article_regeneration"`, `parent_version_id == res.version_id`, `change_scope == {"component": "article", "sectionKey": None, "instructions": "Lead with the workforce data", "findingIds": []}`; v1 row unchanged (`content_markdown` and `sections` equal the values read before); head `current_version_id == res2.version_id`, `title == golden operational`. (Acceptance: regenerating the article creates a new version and keeps the old.)
10. `test_art_write_draft_is_idempotent_per_workflow_step` — `sc2` with dbos ids `("wf-art-steps-draft", 5)`; two `write_draft` calls return equal `VersionResult`; versions for `new` count `1`; writer `LlmCall` rows for `new` count `1`.
11. `test_art_write_draft_rejects_foreign_packet` — `write_draft(sc, article_id=new, packet_id=g.packet_id, avoid=EMPTY_AVOID)` → `ValueError`, `packet <g.packet_id> belongs to article <g.article_id>, not <new>`.
12. `test_art_regenerate_component_section_changes_only_target` — `g = committed_graph(status=READY_FOR_REVIEW)`; `base` = v1 row; `res = regenerate_component(sc, article_id=g.article_id, base_version_id=g.version_id, component=SECTION, section_key=EVIDENCE, instructions="Tighten the evidence section", avoid=EMPTY_AVOID)`; `res.version_no == 2`, `res.title_changed is False`; version count for the article `== 2`; new row: `sections[i] == base.sections[i]` for `i in {0, 1, 2, 4, 5, 6}`, `sections[3] != base.sections[3]`, `sections[3]["key"] == "evidence"`, `title_options == base.title_options`, `pull_quote == base.pull_quote`, `cta == base.cta`, `excerpt == base.excerpt`, `change_kind == "component_regeneration"`, `change_scope == {"component": "section", "sectionKey": "evidence", "instructions": "Tighten the evidence section", "findingIds": []}`, `parent_version_id == g.version_id`, `research_packet_id == base.research_packet_id`; head `current_version_id == res.version_id`, `status == "READY_FOR_REVIEW"`; writer row `prompt_name == "writer/component"`. (Acceptance: regenerating one section creates exactly one new version; other sections byte-identical.)
13. `test_art_regenerate_component_headline_sets_title_changed` — `g` READY; `UPDATE app.blog_articles SET selected_title_key='visionary', title=<base visionary> WHERE id=:a`; headline regeneration → `res.title_changed is True`; new `sections == base.sections`; `title_options != base.title_options`; head `title == new title_options["visionary"]`, `selected_title_key == "visionary"`.
14. `test_art_regenerate_component_rejects_invalid_requests` — parametrized `(component, section_key, base, message)`: `(SECTION, None, current, "section regeneration needs a section key")`; `(SECTION, INTRODUCTION, current, "use component introduction for the introduction")`; `(ARTICLE, None, current, "article is not a component regeneration")`; `(HEADLINE, EVIDENCE, current, "headline takes no section key")`; `(HEADLINE, None, uuid7(), "base version <x> is not the current version <g.version_id>")`; each raises `ValueError` with that message; no `LlmCall` rows with `agent_name == "writer"`.
15. `test_art_revise_article_fix_pass_maps_resolutions` — `g` READY; `findings = [RevisionFinding(finding_id="gate:word_count", origin="quality_gate", description="Body has 700 words; target 850 to 1150.", location="article", recommended_revision=None, required=True)]`; `res = revise_article(sc, article_id=g.article_id, base_version_id=g.version_id, findings=findings, avoid=EMPTY_AVOID, change_kind=FIX_PASS)`; row: `change_kind == "fix_pass"`, `change_scope["findingIds"] == ["gate:word_count"]`, `resolutions == [{"findingId": "gate:word_count", "action": "fixed", "note": "Addressed the finding in the revised conclusion."}]`, `parent_version_id == g.version_id`; writer row `prompt_name == "writer/revise"`.
16. `test_art_revise_article_two_findings_scenario` — `sc = await art_step_context("articles_revise_two_findings")`; findings `editorial:<uuid7>:c1` (required) and `claim:<uuid7>` (required), `change_kind=REVISION`; row `resolutions == [{"findingId": "editorial:<…>:c1", "action": "fixed", "note": "Rewrote the flagged passage."}, {"findingId": "claim:<…>", "action": "declined", "note": "The cited source supports the claim as written."}]`, `change_kind == "revision"`.
17. `test_art_revise_article_missing_resolution_exhausts_route` — default fixtures, the two required findings of test 16; `pytest.raises(RouteExhausted)`; version count stays `1`; writer `LlmCall` rows for the article: `len == len(sc.config.routes["writer"])`, all `status == "error"`.
18. `test_art_revise_article_rejects_invalid_requests` — parametrized: `change_kind=DRAFT` → `ValueError("revise_article accepts change_kind revision or fix_pass, not draft")`; `findings=[]` → `ValueError("revise_article needs at least one finding")`.

**TDD order and verification.**
1. Write conftest additions and the 18 tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_steps.py` → failures `NotImplementedError: ART implements this` (the FOUND stub bodies).
2. Implement `ensure_article`, then `build_research_packet` and `latest_packet_id`, then `write_draft`, `regenerate_component`, `revise_article`, running the file after each. Green: `25 passed`. `tests/foundation/test_found_imports.py` → all passed.
3. Lint paths: ART-5 paths plus `src/mdcopilot_blog/services/article_steps.py` → exit 0.

**Acceptance covered.** §10.3 "Deep Research Analyst + versioned `blog_research_packets`"; "Writer: … revise resolutions, component regeneration"; "Regenerating one section → exactly one new version, other sections byte-identical" (service test); "Regenerating research → new packet version, old kept" (service test); "Word-count and structure checks pass on the draft fixture"; §10.4 "Regenerating the article creates new versions and keeps old" (ART part); §5.8 golden-path invariant for ART (mock P2/P3 produce the golden draft).

### ART-7: Article views and read routes

**Files.**
- Create `pkg/services/article_views.py`, `pkg/services/articles.py` (list query and constants only in this task).
- Modify `pkg/api/routers/articles.py` (FOUND stub `router = APIRouter(tags=["articles"])`).
- Create `backend/tests/articles/test_art_views.py`, `backend/tests/articles/test_art_read_api.py`, `backend/tests/articles/test_art_route_auth.py`.

**Interfaces.**
- Consumes: `services.versions` (ART-5); ORM rows listed in the header; `api.schemas_articles` (ART-2); `api.schemas_common.SourceRefOut`; `api.deps.{SessionDep, require_permission}`; `api.schemas.Page`; `errors.ProblemError`.
- Produces, `services/articles.py`:
  ```python
  ARTICLE_ENTITY = "blog_article"
  DEFAULT_PAGE_SIZE = 20
  MAX_PAGE_SIZE = 100
  NOT_LIVE_STATUSES: frozenset[ArticleStatus] = frozenset({ArticleStatus.REJECTED, ArticleStatus.SUPERSEDED})
  VIEW_STATUSES: Mapping[str, frozenset[ArticleStatus]]
  def statuses_for(view: Literal["drafts", "review", "published", "all"], statuses: Sequence[ArticleStatus] | None) -> frozenset[ArticleStatus]
  def article_not_found(article_id: uuid.UUID) -> ProblemError
  def version_not_found(article_id: uuid.UUID, version_id: uuid.UUID) -> ProblemError
  async def get_article(db: AsyncSession, article_id: uuid.UUID) -> Article
  async def list_articles(db: AsyncSession, *, view: Literal["drafts", "review", "published", "all"], statuses: Sequence[ArticleStatus] | None, pillar: PillarKey | None, q: str | None, limit: int, offset: int) -> tuple[list[Article], int]
  ```
- Produces, `services/article_views.py`:
  ```python
  QUALITY_RUN_KINDS: frozenset[str] = frozenset({GateRunKind.FULL, GateRunKind.FIX_PASS, GateRunKind.RECHECK})
  def version_chain(parents: Mapping[uuid.UUID, uuid.UUID | None], current_id: uuid.UUID | None) -> list[uuid.UUID]
  def newest_review(reviews: Iterable[Review], *, kind: ReviewKind, version_ids: Collection[uuid.UUID], run_kinds: Collection[str] | None = None) -> Review | None
  def gate_badge(reviews: Sequence[Review], *, current_version_id: uuid.UUID | None) -> GateBadgeOut
  async def build_summaries(db: AsyncSession, articles: Sequence[Article]) -> list[ArticleSummaryOut]
  async def build_article_detail(db: AsyncSession, article: Article) -> ArticleDetailOut
  async def build_version_summaries(db: AsyncSession, article_id: uuid.UUID) -> list[VersionSummaryOut]
  async def build_version_detail(db: AsyncSession, *, article_id: uuid.UUID, version_id: uuid.UUID) -> VersionDetailOut
  async def build_article_sources(db: AsyncSession, *, article: Article, version_id: uuid.UUID | None) -> list[ArticleSourceOut]
  async def build_research_packets(db: AsyncSession, article_id: uuid.UUID) -> list[ResearchPacketOut]
  ```
- Produces, routes in `api/routers/articles.py` (prefix `/api/blog-agent` from `ROUTERS`):

| Method, path | Dependency | Params | Response |
|---|---|---|---|
| GET `/articles` | `require_permission(Permission.VIEW)` | `view: Literal[...] = "all"`, `status: Annotated[list[ArticleStatus] \| None, Query()] = None`, `pillar: PillarKey \| None = None`, `q: Annotated[str \| None, Query(max_length=200)] = None`, `limit: Annotated[int, Query(ge=1)] = 20`, `offset: Annotated[int, Query(ge=0)] = 0` | `Page[ArticleSummaryOut]` |
| GET `/articles/{article_id}` | VIEW | — | `ArticleDetailOut` |
| GET `/articles/{article_id}/versions` | VIEW | — | `list[VersionSummaryOut]` |
| GET `/articles/{article_id}/versions/{version_id}` | VIEW | — | `VersionDetailOut` |
| GET `/articles/{article_id}/diff` | VIEW | `from_: Annotated[uuid.UUID, Query(alias="from")]`, `to: uuid.UUID` | `VersionDiffOut` |
| GET `/articles/{article_id}/sources` | VIEW | `version_id: Annotated[uuid.UUID \| None, Query(alias="versionId")] = None` | `list[ArticleSourceOut]` |
| GET `/articles/{article_id}/research-packets` | VIEW | — | `list[ResearchPacketOut]` |

**Behaviour rules.**
1. `VIEW_STATUSES`: `drafts` = {DRAFTING, FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW, SEO, FAILED}; `review` = {READY_FOR_REVIEW, QUALITY_GATE_FAILED}; `published` = {APPROVED, SCHEDULED, EXPORTED, PUBLISHING, PUBLISH_FAILED, PUBLISHED}; `all` = every `ArticleStatus`. `statuses_for` returns `frozenset(statuses)` when `statuses` is non-empty, else `VIEW_STATUSES[view]`.
2. `list_articles`: filter `status IN statuses_for(...)`; `pillar_key == pillar` when given; `q` stripped, ignored when empty, else `title ILIKE :p OR slug ILIKE :p` with `p = "%" + escaped + "%"`, `escape="\\"`, where `escaped` replaces `\` → `\\`, `%` → `\%`, `_` → `\_`; count with the same filters; order `created_at desc, id desc`; the route caps `limit` at 100 and returns the capped value in `Page.limit`.
3. `get_article` → `article_not_found` = `ProblemError(404, "Article not found", f"no article with id {article_id}")`. `version_not_found` = `ProblemError(404, "Version not found", f"no version {version_id} for article {article_id}")`.
4. `version_chain`: starting at `current_id`, follow `parents` until `None`, an id not in `parents`, or an id already visited; returns `[]` for `None`.
5. `newest_review`: among reviews with `kind == kind.value`, `version_id in version_ids` and (when `run_kinds` is given) `gate_run_kind in run_kinds`, the maximum by `(created_at, id)`; `None` if none.
6. `gate_badge`: `gate = newest_review(reviews, kind=QUALITY_GATE, version_ids={current}, run_kinds=QUALITY_RUN_KINDS)`; `passed = None if gate is None else gate.verdict == "PASSED"`; `failed_gates = [GateId(r.gate) for r in GateReport.model_validate(gate.payload).results if not r.passed and r.severity == "blocking"]` (report order; `[]` when `gate is None`); `recheck_required = current_version_id is not None and newest_review(reviews, kind=FACT_CHECK, version_ids={current}) is None`. With `current_version_id is None`: `GateBadgeOut(passed=None, failed_gates=[], recheck_required=False)`.
7. `build_summaries` uses four queries whatever the page size: runs `(id, status)` for the page's `run_id`s; versions `(id, article_id, parent_version_id, version_no, word_count)` for the page's articles; reviews of kinds `fact_check`, `editorial`, `quality_gate` for the page's articles. Per article: `current_version_no`/`word_count` from the current version (`None` without one); `gate_badge`; `fact_check_verdict` and `independent_check` from `newest_review(FACT_CHECK, {current})` (`None` when absent); `editorial_score` = `score` of `newest_review(EDITORIAL, version_chain(...))`; `pillar = article.pillar_key`; `pipeline_status` = run status.
8. `build_article_detail`: current version row (may be `None`); newest SEO of it; `version_sources` of it mapped to `BlogSource(marker, source_id=str(source.id), title, url, publisher, published_at)`; its packet (`research_summary = packet.summary`, `research_packet_id`, `research_packet_version = packet.version`, all `None` when the version or packet is absent); reviews of the article; `fact_check` = `FactCheckResult.model_validate(newest_review(FACT_CHECK, {current}).payload)`; `clinical_review`/`editorial_review` = payload of the newest review of that kind on `version_chain(current)`; `quality_gates` = payload of `newest_review(QUALITY_GATE, {current})` with no run-kind filter; `gates_passed_on_current_version` = `newest_review(QUALITY_GATE, {current}, QUALITY_RUN_KINDS)` exists and its verdict is `PASSED`; `recheck_required` as rule 6; `novelty = NoveltyResult.model_validate(candidate.novelty)` when the candidate's `novelty` is not `None`; `selected_title = article.title`; `title_options`, `sections`, `content_markdown`, `excerpt`, `pull_quote`, `cta`, `version_no` from the current version or `None`; every other field from the article head and the run's status.
9. `build_version_summaries`: 404 `Article not found` when missing; versions `version_no` desc; per version `fact_check_verdict` from `newest_review(FACT_CHECK, {v})`; `gates_passed` = `None` if `newest_review(QUALITY_GATE, {v}, QUALITY_RUN_KINDS)` is `None`, else `verdict == "PASSED"`; `created_by_kind` and `change_scope` from the row.
10. `build_version_detail`: 404 `Article not found`, then 404 `Version not found` (`versions.get_version` returns `None`, including a version of another article); summary fields per rule 9 plus row content, `resolutions` parsed as `FindingResolution`, `seo`/`social` from `newest_seo` (`None` when absent).
11. Diff route: 404 `Article not found`; then `versions.diff_versions`; `None` → 404 `Version not found` naming `from` when that version is missing, else `to`. Missing `from` or `to` query → 422 `Request validation failed` (FastAPI).
12. `build_article_sources`: `version_id` given → `get_version` (404 `Version not found` when `None`); else the current version; no current version → `[]`; rows from `version_sources` mapped to `ArticleSourceOut(marker, source_id, title, url, canonical_url, publisher, domain, tier, published_at, date_source, access_mode, is_primary)`.
13. `build_research_packets`: 404 `Article not found`; records `version` desc; `sources` = for `i, sid` in `packet_source_ids(record)`: `SourceRefOut(id=sid, marker=f"S{i+1}", title, url, publisher, domain, tier, published_at, access_mode)` for ledger rows that exist (missing ids are skipped; numbering keeps the index); `packet = ResearchPacket.model_validate(record.packet)`.

**Tests to write first.**

`backend/tests/articles/test_art_views.py` (unit; `Review` and version objects built in memory, never added to a session). Helper `review(kind, version_id, *, verdict, created_at, gate_run_kind=None, payload=None, score=None)` builds `Review(id=uuid7(), article_id=uuid7(), version_id=…, kind=kind.value, verdict=verdict, payload=payload or {}, gate_run_kind=gate_run_kind, score=score, created_at=created_at)`.
1. `test_art_version_chain_walks_parents` — `parents = {v3: v2, v2: v1, v1: None}` → `version_chain(parents, v3) == [v3, v2, v1]`; `version_chain(parents, None) == []`; a cycle `{a: b, b: a}` → `[a, b]`.
2. `test_art_newest_review_orders_by_created_at_then_id` — two fact checks on `v1` with equal `created_at` and ids `r_low < r_high` (two `uuid7()` calls) → returns `r_high`; a later review on `v2` is excluded by `version_ids={v1}`.
3. `test_art_gate_badge_ignores_deterministic_runs` — current `v1`: a `full` PASSED gate at t0 and a `deterministic` FAILED gate at t1 > t0, plus a fact check → `GateBadgeOut(passed=True, failed_gates=[], recheck_required=False)`.
4. `test_art_gate_badge_lists_failed_blocking_gates` — `recheck` FAILED gate with payload `{"passed": false, "results": [{"gate": "word_count", "passed": false, "severity": "blocking", "details": "short"}, {"gate": "opening_diversity", "passed": false, "severity": "warning", "details": "similar"}, {"gate": "cta_fresh", "passed": false, "severity": "blocking", "details": "repeat"}]}` and no fact check → `passed=False`, `failed_gates == [GateId.WORD_COUNT, GateId.CTA_FRESH]`, `recheck_required=True`.
5. `test_art_gate_badge_without_version` — `gate_badge([], current_version_id=None) == GateBadgeOut(passed=None, failed_gates=[], recheck_required=False)`.
6. `test_art_view_statuses` — parametrized over the 4 views; `statuses_for(view, None) == VIEW_STATUSES[view]` with the literal sets of rule 1; `statuses_for("drafts", [ArticleStatus.REJECTED]) == frozenset({ArticleStatus.REJECTED})` asserted in the `drafts` case.

`backend/tests/articles/test_art_read_api.py` (`seeded_db`, `login_as`, `make_article_graph`; every request made by a `viewer`). Only one graph per test uses `with_seo=True` (slug uniqueness); helper `summary_keys = set(SHAPES["ArticleSummaryOut"]["props"])`, and so on per model.
1. `test_art_list_articles_returns_summaries_newest_first` — `g1 = graph(status=READY_FOR_REVIEW, reviews={FACT_CHECK, QUALITY_GATE, EDITORIAL, CLINICAL})`, `g2 = graph(status=DRAFTING, with_seo=False)`; `GET /api/blog-agent/articles` → 200; `total == 2`; `[i["id"] for i in items] == [str(g2.article_id), str(g1.article_id)]`; `set(items[1]) == summary_keys`; g1 item: `status == "READY_FOR_REVIEW"`, `pipelineStatus ==` its run status from the DB, `currentVersionNo == 1`, `wordCount == body_word_count(golden sections)`, `gateBadge == {"passed": True, "failedGates": [], "recheckRequired": False}`, `factCheckVerdict == "PASS"`, `independentCheck ==` the DB column, `editorialScore == load_golden_output("editorial.json")["editorialScore"]`; g2 item: `gateBadge == {"passed": None, "failedGates": [], "recheckRequired": True}`, `factCheckVerdict is None`, `editorialScore is None`.
2. `test_art_list_articles_view_filters` — graphs (all `with_seo=False`): DRAFTING, READY_FOR_REVIEW, QUALITY_GATE_FAILED, APPROVED (`approved=True`), PUBLISHED (`approved=True`), REJECTED; parametrized `view` → expected status set: `drafts` {DRAFTING}; `review` {READY_FOR_REVIEW, QUALITY_GATE_FAILED}; `published` {APPROVED, PUBLISHED}; `all` all six; `{i["status"] for i in items} ==` expected and `total == len(expected)`.
3. `test_art_list_articles_status_overrides_view` — same graphs; `?view=drafts&status=REJECTED&status=APPROVED` → statuses `{"REJECTED", "APPROVED"}`, `total == 2`.
4. `test_art_list_articles_pillar_and_query_filters` — three graphs (`with_seo=False`); `UPDATE app.blog_articles`: g1 `title='Prior auth is 100% manual', pillar_key='A'`; g2 `title='Prior auth is 1000 manual', pillar_key='C'`; g3 `title=NULL, slug='inbox-load', pillar_key='A'`; `?q=100%25` → `[g1]`; `?q=INBOX` → `[g3]`; `?pillar=A` → ids `{g1, g3}`; `?pillar=A&q=prior` → `[g1]`.
5. `test_art_list_articles_paginates_and_caps_limit` — three graphs; `?limit=2&offset=1` → `len(items) == 2`, `total == 3`, `limit == 2`, `offset == 1`; `?limit=500` → `limit == 100`; `?limit=0` → 422.
6. `test_art_article_detail_with_reviews` — `g = graph(status=READY_FOR_REVIEW, reviews={FACT_CHECK, CLINICAL, EDITORIAL, QUALITY_GATE})`; `GET /articles/{id}` → `set(body) == detail_keys`; `titleOptions == golden title options dump`; `contentMarkdown == assemble_markdown(golden sections)`; `sections == golden section dumps`; `seo == load_golden_output("seo.json")["seo"]`; `social == load_golden_output("seo.json")["social"]`; `[s["marker"] for s in sources] == ["S1", "S2", "S3", "S4", "S5"]` and `sources[i]["sourceId"] == str(<version's article_sources source_id for that marker>)`; `researchSummary ==` the packet row's `summary`; `researchPacketId == str(g.packet_id)`; `researchPacketVersion == 1`; `factCheck`, `clinicalReview`, `editorialReview`, `qualityGates` equal the stored review payloads; `gatesPassedOnCurrentVersion is True`; `recheckRequired is False`; `versionNo == 1`; `currentVersionId == str(g.version_id)`; `novelty ==` the candidate's `novelty` column (`None` stays `None`); `pipelineStatus ==` run status.
7. `test_art_article_detail_without_reviews` — `graph(status=QUALITY_GATE_FAILED, with_seo=False)` → `factCheck`, `clinicalReview`, `editorialReview`, `qualityGates`, `seo`, `social` all `None`; `gatesPassedOnCurrentVersion is False`; `recheckRequired is True`.
8. `test_art_article_detail_uses_ancestor_reviews` — `g = graph(reviews={FACT_CHECK, EDITORIAL})`; `lock_article`; insert v2 with `human_version(...)` and set `article.current_version_id = v2`; flush → `editorialReview ==` v1's editorial payload; `factCheck is None`; `recheckRequired is True`; `versionNo == 2`.
9. `test_art_article_detail_404` — random `uuid7()` → 404, `title == "Article not found"`, `detail == f"no article with id {id}"`.
10. `test_art_list_versions_newest_first_with_verdicts` — `g = graph(reviews={FACT_CHECK, QUALITY_GATE})`, v2 inserted as in test 8 → `[v["versionNo"] for v in body] == [2, 1]`; v1 `factCheckVerdict == "PASS"`, `gatesPassed is True`; v2 `factCheckVerdict is None`, `gatesPassed is None`, `createdByKind == "human"`, `changeKind == "human_edit"`; `set(body[0]) == version_summary_keys`.
11. `test_art_version_detail` — `GET /articles/{a}/versions/{v1}` → `set(body) == version_detail_keys`; `contentMarkdown ==` v1 row; `citationMarkers ==` v1 row; `seo == golden seo`; `resolutions == []`.
12. `test_art_version_of_other_article_404` — `g1` (`with_seo=True`), `g2` (`with_seo=False`) → `GET /articles/{g1.article}/versions/{g2.version}` → 404 `Version not found`, `detail == f"no version {g2.version_id} for article {g1.article_id}"`; `GET /articles/{uuid7()}/versions/{g1.version}` → 404 `Article not found`.
13. `test_art_diff_endpoint` — v2 = `human_version(pull_quote="Specialist time is the scarcest resource in the clinic.")` plus `insert_seo_copy` of v1's SEO → `GET /articles/{a}/diff?from={v1}&to={v2}` → 200; `fromVersionNo == 1`, `toVersionNo == 2`, `unifiedDiff == ""`, `fieldChanges == [{"field": "pullQuote", "from": <golden pull quote>, "to": "Specialist time is the scarcest resource in the clinic."}]`.
14. `test_art_diff_unknown_version_404` — `?from={v1}&to={uuid7()}` → 404 `Version not found`, detail names the `to` id.
15. `test_art_diff_requires_from_and_to` — `?to={v1}` → 422 `Request validation failed`.
16. `test_art_article_sources_current_and_explicit_version` — default → markers `["S1".."S5"]`, `set(item) == article_source_keys`, `isPrimary ==` DB value; `?versionId={v1}` → same list; after inserting v2 whose evidence body lost its markers (edit via `sections_from_markdown`) and setting it current, the default list's markers equal `sorted(v2_row.citation_markers, key=marker_number)` and `?versionId={v1}` still returns five.
17. `test_art_article_sources_404` — unknown article → 404 `Article not found`; `?versionId={uuid7()}` → 404 `Version not found`.
18. `test_art_research_packets_newest_first` — `insert_research_packet(db, article_id=g.article_id, research_run_id=g.research_run_id, packet=<fixture packet>, source_ids=g.source_ids, created_by=None, dbos_workflow_id=None, dbos_step_id=None)` → `[p["version"] for p in body] == [2, 1]`; `body[0]["sources"]` markers `["S1".."S6"]` with ids `[str(i) for i in g.source_ids]`; `set(body[0]) == research_packet_keys`; `body[0]["packet"]["summary"] == fixture summary`.

`backend/tests/articles/test_art_route_auth.py` (`client`). `ROUTES` list of `(method, path_template, body)`; in this task the seven GET routes with random ids (diff with `?from=<id>&to=<id>`).
1. `test_art_route_requires_session` — parametrized over `ROUTES` (7 now); anonymous request → 401, `title == "Not authenticated"`.
There is no 403 case for these routes: every role holds `blog.view`.

**TDD order and verification.**
1. Write the three files. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_views.py tests/articles/test_art_read_api.py tests/articles/test_art_route_auth.py` → `test_art_views.py` collection error (`No module named 'mdcopilot_blog.services.article_views'`); the API tests fail with 404 `Not Found` responses.
2. Implement `articles.py` (list part), `article_views.py`, then the routes. Green: same command → `37 passed` (9 + 21 + 7). `tests/api/test_rbac_routes.py::test_every_non_public_route_requires_a_principal` → passed.
3. Lint paths: ART-6 paths plus `src/mdcopilot_blog/services/article_views.py src/mdcopilot_blog/services/articles.py src/mdcopilot_blog/api/routers/articles.py` → exit 0.

**Acceptance covered.** §10.3 "Version history and diff API" (API tests); §10.5 ART APIs the dashboard uses (`/articles` views with gate badges, article detail for the review split screen); §4.5 GET routes with success, 401 and problem responses.

### ART-8: Regenerate intake and title selection

**Files.**
- Modify `pkg/services/articles.py`, `pkg/api/routers/articles.py`.
- Create `backend/tests/articles/test_art_actions_api.py`; modify `backend/tests/articles/test_art_route_auth.py`, `backend/tests/articles/conftest.py` (`session_user_id`, `audit_rows`).

**Interfaces.**
- Consumes: `services.enqueue.{ensure_agent_enabled, enqueue_workflow}`; `workflows.names.{WORKFLOW_REGENERATE_COMPONENT, WORKFLOW_REGENERATE_ARTICLE, WORKFLOW_REGENERATE_RESEARCH, QUEUE_INTERACTIVE}`; `ids.uuid7`; `services.audit.audit`; `api.schemas_common.ActionAccepted`; `api.deps.{WorkflowClientDep, SettingsDep, Principal}`; `article_views.build_article_detail`; `versions.lock_article`, `versions.version_content`; `article_assembly.title_for_key`.
- Produces, `services/articles.py`:
  ```python
  REGENERATE_STATUSES: frozenset[ArticleStatus] = frozenset({ArticleStatus.READY_FOR_REVIEW, ArticleStatus.QUALITY_GATE_FAILED})
  TITLE_LOCKED_STATUSES: frozenset[ArticleStatus] = frozenset({APPROVED, SCHEDULED, EXPORTED, PUBLISHING, PUBLISHED, PUBLISH_FAILED, REJECTED, SUPERSEDED})
  async def request_regeneration(db: AsyncSession, client: WorkflowClientProtocol, *, settings: Settings, article_id: uuid.UUID, body: RegenerateRequest, principal: Principal) -> ActionAccepted
  async def select_title(db: AsyncSession, *, article_id: uuid.UUID, body: SelectTitleRequest, principal: Principal) -> Article
  ```
- Produces, routes:

| Method, path | Dependency | Body | Response |
|---|---|---|---|
| POST `/articles/{article_id}/regenerate` (status 202) | `require_permission(Permission.GENERATE)` | `RegenerateRequest` | `ActionAccepted` |
| POST `/articles/{article_id}/select-title` | `require_permission(Permission.EDIT)` | `SelectTitleRequest` | `ArticleDetailOut` |

**Behaviour rules.**
1. `request_regeneration`, in order:
   1. `article = await db.get(Article, article_id)` → missing: 404 `Article not found`;
   2. `enqueue.ensure_agent_enabled(settings)` (409 `Agent disabled`);
   3. allowed = `REGENERATE_STATUSES`, plus `FAILED` when `body.component == research`; status not allowed → `ProblemError(409, "Invalid state transition", f"cannot regenerate {component} while the article is {status}")`;
   4. `component != research` and `article.current_version_id is None` → `ProblemError(409, "Invalid state transition", f"cannot regenerate {component}: the article has no version yet")`;
   5. workflow: `headline`, `introduction`, `section`, `pull_quote`, `cta` → `WORKFLOW_REGENERATE_COMPONENT`, id `f"regen-component-{article.id}-{uuid7()}"`, args `(str(article.id), component.value, section_key.value if section_key else None, instructions)`; `article` → `WORKFLOW_REGENERATE_ARTICLE`, `f"regen-article-{article.id}-{uuid7()}"`, `(str(article.id), instructions)`; `research` → `WORKFLOW_REGENERATE_RESEARCH`, `f"regen-research-{article.id}-{uuid7()}"`, `(str(article.id),)`. `instructions` is the validated (stripped or `None`) value;
   6. `audit(db, actor_user_id=principal.user_id, action="article.regenerate", entity_type=ARTICLE_ENTITY, entity_id=str(article.id), details={"component": component.value, "section_key": section_key value or None, "instructions": instructions, "workflow_id": workflow_id})`; `await db.commit()` (Phase 1 order: commit, then enqueue);
   7. `parts = await enqueue.enqueue_workflow(client, workflow_name=…, queue_name=QUEUE_INTERACTIVE, workflow_id=…, args=…, timeout_seconds=settings.production_timeout_minutes * 60)` (any failure → 503 `Workflow service unavailable`, detail `<workflow_name> was not enqueued`; the audit row stays);
   8. return `ActionAccepted(workflow_id=parts.workflow_id, workflow_name=parts.workflow_name, queue=parts.queue, run_id=article.run_id, article_id=article.id, candidate_id=article.candidate_id)`.
   The route calls it with `WorkflowClientDep`, `SettingsDep` and the principal and returns the model with status 202. Body validation errors are 422 before rule 1.
2. `select_title`, in order: `lock_article` → missing: 404; `status in TITLE_LOCKED_STATUSES` → `ProblemError(409, "Invalid state transition", f"titles cannot change while the article is {status}")`; with `key`: `current_version_id is None` → `ProblemError(422, "Request validation failed", "the article has no title options yet")`, else `title = title_for_key(TitleOptions.model_validate(current.title_options), key)`, `selected_title_key = key`; with `custom_title`: `title = custom_title`, `selected_title_key = "custom"`; no version is created; `audit(..., action="article.select_title", details={"key": selected_title_key, "title": title})`; commit; `await db.refresh(article)`; route returns `await article_views.build_article_detail(db, article)`.

**Tests to write first.** Conftest additions: `async def session_user_id(http: AsyncClient) -> uuid.UUID` (`GET /api/auth/session` → `user.id`); `async def audit_rows(db, action: str, entity_id: uuid.UUID) -> list[AuditLog]`.

`backend/tests/articles/test_art_actions_api.py` (`seeded_db`, `login_as`, `make_article_graph`, `fake_workflow_client`, `settings`; mutating requests send `X-CSRF-Token`). `REGEN_ID = re.compile(r"^regen-(component|article|research)-([0-9a-f-]{36})-([0-9a-f-]{36})$")`.
1. `test_art_regenerate_section_enqueues_component_workflow` — editor; `g` READY; body `{"component": "section", "sectionKey": "evidence", "instructions": "Tighten the evidence section"}` → 202; `m = REGEN_ID.match(body["workflowId"])`; `m.group(1) == "component"`, `m.group(2) == str(g.article_id)`, `uuid.UUID(m.group(3)).version == 7`; `body == {"workflowId": wid, "workflowName": "regenerate_component", "queue": "interactive", "runId": str(g.run_id), "articleId": str(g.article_id), "candidateId": str(g.candidate_id)}`; `fake_workflow_client.enqueued == [EnqueueCall("regenerate_component", "interactive", wid, (str(g.article_id), "section", "evidence", "Tighten the evidence section"), settings.production_timeout_minutes * 60)]`; one audit row `article.regenerate` with `entity_type == "blog_article"`, `actor_user_id == session_user_id`, `details == {"component": "section", "section_key": "evidence", "instructions": "Tighten the evidence section", "workflow_id": wid}`.
2. `test_art_regenerate_headline_passes_null_args` — `{"component": "headline"}` → args `(str(g.article_id), "headline", None, None)`.
3. `test_art_regenerate_article_uses_article_workflow` — QUALITY_GATE_FAILED graph; `{"component": "article", "instructions": "   "}` → `workflowName == "regenerate_article"`, `m.group(1) == "article"`, args `(str(g.article_id), None)`.
4. `test_art_regenerate_research_allowed_from_failed` — FAILED graph; `{"component": "research"}` → 202, `workflowName == "regenerate_research"`, args `(str(g.article_id),)`.
5. `test_art_regenerate_rejects_status` — parametrized `(status, body, detail)`: `(APPROVED with approved=True, {"component": "article"}, "cannot regenerate article while the article is APPROVED")`; `(FAILED, {"component": "section", "sectionKey": "evidence"}, "cannot regenerate section while the article is FAILED")`; `(DRAFTING, {"component": "research"}, "cannot regenerate research while the article is DRAFTING")`; → 409, `title == "Invalid state transition"`, `detail` as given; `enqueued == []`.
6. `test_art_regenerate_validation_422` — parametrized bodies: `{"component": "section"}`; `{"component": "section", "sectionKey": "introduction"}`; `{"component": "headline", "sectionKey": "evidence"}`; `{"component": "article", "instructions": "x" * 2001}`; `{"component": "bogus"}` → 422 `Request validation failed`; `enqueued == []`.
7. `test_art_regenerate_agent_disabled_409` — `monkeypatch.setattr(app.state, "settings", settings.model_copy(update={"agent_enabled": False}))` → 409 `Agent disabled`; `enqueued == []`; no `article.regenerate` audit row.
8. `test_art_regenerate_enqueue_failure_503` — `fake_workflow_client.enqueue_error = RuntimeError("queue down")`; `{"component": "cta"}` → 503, `title == "Workflow service unavailable"`, `detail == "regenerate_component was not enqueued"`; one `article.regenerate` audit row exists.
9. `test_art_regenerate_404` — random id → 404 `Article not found`.
10. `test_art_select_title_by_key` — editor; READY graph; `{"key": "visionary"}` → 200; `selectedTitle == golden visionary`; `selectedTitleKey == "visionary"`; versions for the article count `1`; audit `article.select_title` `details == {"key": "visionary", "title": <golden visionary>}`.
11. `test_art_select_custom_title_is_stripped` — `{"customTitle": "  Specialists need leverage, not more portals  "}` → `selectedTitle == "Specialists need leverage, not more portals"`, `selectedTitleKey == "custom"`.
12. `test_art_select_title_validation_422` — parametrized: `{"key": "visionary", "customTitle": "A title"}`; `{}`; `{"customTitle": "   "}`; `{"customTitle": "x" * 201}` → 422 `Request validation failed`.
13. `test_art_select_title_locked_statuses` — parametrized APPROVED (`approved=True`), PUBLISHED (`approved=True`), REJECTED → 409 `Invalid state transition`, `detail == f"titles cannot change while the article is {status}"`.
14. `test_art_select_title_404` — random id → 404 `Article not found`.

`backend/tests/articles/test_art_route_auth.py`: append `("POST", "/api/blog-agent/articles/{id}/regenerate", {"component": "article"})` and `("POST", "/api/blog-agent/articles/{id}/select-title", {"key": "operational"})` to `ROUTES`; add `FORBIDDEN = [(method, path, body, permission)]` with those two routes and `Permission.GENERATE` / `Permission.EDIT`, and:
- `test_art_route_forbidden_without_permission` — parametrized over `FORBIDDEN`; `login_as(Role.VIEWER)`; request with the CSRF token → 403, `title == "Forbidden"`, `detail == f"missing permission {permission.value}"`.

**TDD order and verification.**
1. Write tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_actions_api.py tests/articles/test_art_route_auth.py` → action tests fail with 404/405 (`Not Found` / `Method Not Allowed`); new auth cases fail (expected 401/403, got 404).
2. Implement services and routes. Green: same command → `36 passed` (25 + 11).
3. Lint: ART-7 paths → exit 0.

**Acceptance covered.** §5.7 ART-enqueued workflows (ids, args, queue, timeout); §4.5 regenerate and select-title rules; §10.5 "Every human action wired" (API side of regenerate and headline picker); §8.3 route tests (success, 401, 403, problems).

### ART-9: Human edit (`PATCH /articles/{article_id}`) and OpenAPI shapes

**Files.**
- Modify `pkg/services/articles.py`, `pkg/api/routers/articles.py`.
- Create `backend/tests/articles/test_art_edit_api.py`, `backend/tests/articles/test_art_openapi.py`; modify `backend/tests/articles/test_art_route_auth.py`, `backend/tests/articles/conftest.py` (`quality_fakes`).

**Interfaces.**
- Consumes: `services.step_context.build_api_step_context`; `services.config.{load_effective_config, load_brand_profile}`; `services.diversity.record_version_features`; `services.quality_steps.run_deterministic_gates`; `services.article_status.set_article_status`; `versions.{lock_article, insert_version, newest_seo, insert_seo_copy, version_content, change_scope, NewVersion}`; `article_assembly.{edit_content, merge_seo, title_for_key}`. The service imports modules, not names: `from mdcopilot_blog.services import article_status, diversity, quality_steps, step_context` and `from mdcopilot_blog.services import config as config_service`, and calls `diversity.record_version_features(...)`, `quality_steps.run_deterministic_gates(...)`, `step_context.build_api_step_context(...)`, `config_service.load_effective_config(...)`, `config_service.load_brand_profile(...)`, so tests can patch each attribute.
- Produces:
  ```python
  EDITABLE_STATUSES: frozenset[ArticleStatus] = frozenset({ArticleStatus.READY_FOR_REVIEW, ArticleStatus.QUALITY_GATE_FAILED, ArticleStatus.APPROVED})
  async def edit_article(db: AsyncSession, *, sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, article_id: uuid.UUID, body: ArticleEditRequest, principal: Principal) -> Article
  ```
  Route: PATCH `/articles/{article_id}`, `require_permission(Permission.EDIT)`, body `ArticleEditRequest`, reads `request.app.state.sessionmaker`, returns `ArticleDetailOut` (`build_article_detail` after `db.refresh(article)`).

**Behaviour rules** (CONTRACT §4.5 PATCH transaction order).
1. `fields` = sorted camelCase names of the request fields other than `baseVersionId` that are not `None` (e.g. `["contentMarkdown", "seo"]`). `version_fields` = the subset in {`contentMarkdown`, `pullQuote`, `cta`, `excerpt`, `titleOptions`, `seo`}.
2. **T1 (request session `db`)**, in order:
   1. `article = lock_article(db, article_id)` → `None`: 404 `Article not found`;
   2. status not in `EDITABLE_STATUSES` → `ProblemError(409, "Invalid state transition", f"articles can be edited only in READY_FOR_REVIEW, QUALITY_GATE_FAILED or APPROVED; this article is {status}")`;
   3. `body.base_version_id != article.current_version_id` → `ProblemError(409, "Version conflict", f"base version {body.base_version_id} is not the current version {article.current_version_id}")`;
   4. head-only request (`version_fields` empty): set `tags`/`category` when given; `audit(db, actor_user_id=principal.user_id, action="article.edit", entity_type="blog_article", entity_id=str(article.id), details={"version_id": None, "base_version_id": str(body.base_version_id), "fields": fields})`; commit; return the article (no features, no gates, status unchanged);
   5. `base_row = await db.get(ArticleVersion, article.current_version_id)`; `base = versions.version_content(base_row)`; `content = edit_content(base, content_markdown=body.content_markdown, title_options=body.title_options, pull_quote=body.pull_quote, cta=body.cta, excerpt=body.excerpt)` — `ArticleStructureError` propagates (422 `Article structure invalid`);
   6. `base_seo_row = newest_seo(db, base_row.id)`; `body.seo` given and `base_seo_row is None` → `ProblemError(422, "Request validation failed", "the base version has no SEO record to edit")`; `new_seo = merge_seo(SEOMetadata.model_validate(base_seo_row.seo), body.seo.model_dump(exclude_none=True, by_alias=False))` when `body.seo` given, else the base SEO (or `None`);
   7. when `new_seo` is not `None` and `new_seo.slug != article.slug`: another article with `slug == new_seo.slug`, `id != article.id` and status not in `NOT_LIVE_STATUSES` exists → `ProblemError(409, "Slug already in use", new_seo.slug)`;
   8. `row, _ = insert_version(db, NewVersion(article_id=article.id, parent_version_id=base_row.id, change_kind=ChangeKind.HUMAN_EDIT, change_scope=change_scope(component=None, section_key=None, instructions=None, finding_ids=[]), content=content, resolutions=[], research_packet_id=base_row.research_packet_id, created_by=principal.user_id, created_by_kind="human", dbos_workflow_id=None, dbos_step_id=None))` — `UnknownCitationMarker` propagates (422 `Unknown citation marker`);
   9. when `new_seo` is not `None`: `insert_seo_copy(db, version_id=row.id, seo=new_seo, social=SocialCopy.model_validate(base_seo_row.social) if base_seo_row.social else None, created_by=principal.user_id)`;
   10. head: `current_version_id = row.id`; `slug = new_seo.slug` when it changed; `tags`/`category` when given; when `body.title_options` is given and `selected_title_key` is `provocative`, `operational` or `visionary`: `title = title_for_key(content.title_options, key)`;
   11. commit. An `IntegrityError` whose `orig.diag.constraint_name == "uq_blog_articles_slug"` (a concurrent save) → rollback and `ProblemError(409, "Slug already in use", new_seo.slug)`.
3. **Features (own session).** `sc = await step_context.build_api_step_context(settings=settings, sessionmaker=sessionmaker, run_id=article.run_id, article_id=article.id)`; `await diversity.record_version_features(sc, version_id=row.id)`; any exception → `ProblemError(503, "Version features not recorded", f"features for version {row.id} were not recorded; save again or run a re-check")` (the committed version stays current, the status is unchanged, no gate report and no audit row are written).
4. **T2 (request session).** `config = await config_service.load_effective_config(db, settings, run_id=article.run_id)`; `brand = await config_service.load_brand_profile(db)`; `report = await quality_steps.run_deterministic_gates(db, article_id=article.id, version_id=row.id, config=config, brand=brand)`; if the status is `APPROVED`: `set_article_status(db, article_id=article.id, target=READY_FOR_REVIEW)`; then `set_article_status(db, article_id=article.id, target=READY_FOR_REVIEW if report.passed else QUALITY_GATE_FAILED)`; `approved_version_id` is never changed; `audit(..., action="article.edit", details={"version_id": str(row.id), "base_version_id": str(body.base_version_id), "fields": fields})`; commit.
5. Every route test for PATCH that reaches T1 step 5 uses the committing API fixtures (§8.1), because step 3 opens its own session.

**Tests to write first.** Conftest addition — fixture `quality_fakes(monkeypatch)` returning:
```python
@dataclass
class QualityFakes:
    report: GateReport            # default GateReport(passed=True, results=[GateResult(gate="word_count", passed=True, severity="blocking", details="ok")])
    features_error: Exception | None = None
    features_calls: list[tuple[StepContext, uuid.UUID]] = field(default_factory=list)
    gate_calls: list[dict[str, Any]] = field(default_factory=list)   # {"article_id", "version_id", "config", "brand"}
    config_run_ids: list[uuid.UUID | None] = field(default_factory=list)
```
It patches `mdcopilot_blog.services.diversity.record_version_features` (appends `(sc, version_id)`, then raises `features_error` when set), `mdcopilot_blog.services.quality_steps.run_deterministic_gates` (appends the kwargs, returns `report`, writes nothing), and wraps `mdcopilot_blog.services.config.load_effective_config` with a spy that appends `run_id` and delegates to the real function.

`backend/tests/articles/test_art_edit_api.py` (`committing_client`, `committing_login_as`, `sessionmaker_committing`, `committed_graph` from ART-6, `quality_fakes`; editor unless stated; `PATCH = "/api/blog-agent/articles/{id}"`). `md_renamed` = `assemble_markdown(golden sections)` with the line `## <golden context heading>` replaced by `## Why specialists wait`. `FAIL = GateReport(passed=False, results=[GateResult(gate="word_count", passed=False, severity="blocking", details="body has 700 words")])`.
1. `test_art_patch_content_creates_human_version` — `g = committed_graph(status=READY_FOR_REVIEW)`; body `{"baseVersionId": str(g.version_id), "contentMarkdown": md_renamed}` → 200; `body["versionNo"] == 2`, `body["status"] == "READY_FOR_REVIEW"`, `body["sections"][1]["heading"] == "Why specialists wait"`; v2 row: `parent_version_id == g.version_id`, `change_kind == "human_edit"`, `created_by_kind == "human"`, `created_by == session_user_id`, `change_scope == {"component": None, "sectionKey": None, "instructions": None, "findingIds": []}`, `research_packet_id == g.packet_id`, `content_markdown == assemble_markdown(sections_from_markdown(md_renamed))`, `word_count == body_word_count(golden sections)`; article `current_version_id == v2`; `blog_version_seo` rows for v2: 1, `seo ==` v1's newest SEO `seo`, `slug ==` v1 slug, `created_by == session_user_id`; `blog_article_sources` markers for v2 `== v2.citation_markers`; `[vid for _, vid in quality_fakes.features_calls] == [v2]`; that `sc.call.run_id == g.run_id`, `sc.call.article_id == g.article_id`, `sc.call.trace_id ==` the run's `trace_id`; `quality_fakes.gate_calls[0]["article_id"] == g.article_id`, `["version_id"] == v2`, `["brand"] == await load_brand_profile(db)`; `quality_fakes.config_run_ids == [g.run_id]`; audit `article.edit` `details == {"version_id": str(v2), "base_version_id": str(g.version_id), "fields": ["contentMarkdown"]}`.
2. `test_art_patch_failing_gate_sets_quality_gate_failed` — READY graph; `quality_fakes.report = FAIL`; `{"pullQuote": "Specialist time is the scarcest resource in the clinic."}` → 200, `status == "QUALITY_GATE_FAILED"`, `pullQuote` updated.
3. `test_art_patch_from_quality_gate_failed_passing_returns_ready` — QUALITY_GATE_FAILED graph, passing report → `status == "READY_FOR_REVIEW"`.
4. `test_art_patch_from_approved` — parametrized `(report, expected)`: passing → `READY_FOR_REVIEW`; `FAIL` → `QUALITY_GATE_FAILED`; graph `status=APPROVED, approved=True`; after the call `approvedVersionId == str(g.version_id)`, `currentVersionId == str(v2)`.
5. `test_art_patch_wrong_h2_count_422` — `md_renamed` with the `## <golden conclusion heading>` line removed → 422, `title == "Article structure invalid"`, `detail == "expected 6 H2 sections, found 5"`; version count `1`; `features_calls == []`, `gate_calls == []`. (Acceptance: a save with the wrong H2 count returns 422.)
6. `test_art_patch_unknown_marker_422` — `contentMarkdown = md_renamed.replace("\n\n## " + <golden mdcopilot_perspective heading>, " [S9]\n\n## " + <golden mdcopilot_perspective heading>, 1)` (the marker ends the evidence body) → 422, `title == "Unknown citation marker"`, `detail == "unknown markers: S9"`; version count `1`. (Acceptance: unknown citation markers rejected, API.)
7. `test_art_patch_marker_outside_body_422` — `{"pullQuote": "Specialist time is scarce [S1]"}` → 422 `Article structure invalid`, `detail == "citation markers are allowed only in section bodies: pullQuote"`.
8. `test_art_patch_version_conflict_409` — `baseVersionId = str(uuid7())` → 409 `Version conflict`, `detail == f"base version {x} is not the current version {g.version_id}"`.
9. `test_art_patch_status_conflict_409` — parametrized DRAFTING, PUBLISHED (`approved=True`) → 409 `Invalid state transition`, `detail == f"articles can be edited only in READY_FOR_REVIEW, QUALITY_GATE_FAILED or APPROVED; this article is {status}"`.
10. `test_art_patch_slug_in_use_409` — `g1` READY (`with_seo=True`); `g2` READY `with_seo=False`, then `UPDATE app.blog_articles SET slug='taken-slug' WHERE id=:g2`; `{"seo": {"slug": "taken-slug"}}` on g1 → 409, `title == "Slug already in use"`, `detail == "taken-slug"`; g1 version count `1`.
11. `test_art_patch_slug_free_when_other_article_rejected` — as test 10 with g2 `status=REJECTED` → 200; g1 head `slug == "taken-slug"`; v2 SEO row `slug == "taken-slug"` and `seo["slug"] == "taken-slug"`.
12. `test_art_patch_seo_merge_copies_social` — `{"seo": {"seoTitle": "New SEO title"}}` → v2 SEO row `seo["seoTitle"] == "New SEO title"`, every other key equal to v1's SEO, `social ==` v1's `social`; v2 `content_markdown ==` v1's; audit `fields == ["seo"]`.
13. `test_art_patch_features_failure_503` — QUALITY_GATE_FAILED graph; `quality_fakes.features_error = RuntimeError("embedding service down")`; content edit → 503, `title == "Version features not recorded"`, `detail == f"features for version {v2} were not recorded; save again or run a re-check"` (v2 read from `current_version_id`); article `current_version_id == v2 != g.version_id`, `status == "QUALITY_GATE_FAILED"`; `gate_calls == []`; `article.edit` audit rows `0`.
14. `test_art_patch_head_only_tags_and_category` — `{"tags": ["Access", "Specialists"], "category": "Clinical operations"}` → 200, `versionNo == 1`, `tags == ["Access", "Specialists"]`, `category == "Clinical operations"`, status unchanged; `features_calls == []`, `gate_calls == []`; audit `details == {"version_id": None, "base_version_id": str(g.version_id), "fields": ["category", "tags"]}`.
15. `test_art_patch_requires_a_change_422` — `{"baseVersionId": str(g.version_id)}` → 422 `Request validation failed`.
16. `test_art_patch_title_options_update_head_title` — `POST /articles/{a}/select-title {"key": "operational"}` first; PATCH `titleOptions` = `{"provocative": "Specialist queues are a design choice", "operational": "How to widen specialist access this quarter", "visionary": "The clinic where every specialist scales"}` → `selectedTitle == "How to widen specialist access this quarter"`, `titleOptions` equal the new values.
17. `test_art_patch_seo_edit_without_base_seo_422` — graph `with_seo=False`; `{"seo": {"seoTitle": "New SEO title"}}` → 422 `Request validation failed`, `detail == "the base version has no SEO record to edit"`; version count `1`.
18. `test_art_patch_404` — random id → 404 `Article not found`.
19. `test_art_patch_does_not_touch_approved_version_on_failure_paths` — APPROVED graph (`approved=True`); wrong H2 count request → 422; article `status == "APPROVED"`, `approved_version_id == current_version_id == g.version_id`.

`backend/tests/articles/test_art_openapi.py` (unit over `create_app(settings, workflow_client=FakeWorkflowClient()).openapi()`):
1. `test_art_openapi_models_match_shapes` — parametrized over the 13 names in `ARTICLE_API_MODELS`; component = `schemas[name]`, else `schemas[name + "-Output"]`, else `schemas[name + "-Input"]`; `sorted(component["properties"]) == SHAPES[name]["props"]`; names whose property schema has an `anyOf` containing `{"type": "null"}`, sorted, `== SHAPES[name]["nullable"]`.
2. `test_art_openapi_declares_article_routes` — `paths["/api/blog-agent/articles"]` has `get`; `/articles/{article_id}` has `get` and `patch`; `/versions`, `/versions/{version_id}`, `/diff`, `/sources`, `/research-packets` have `get`; `/regenerate` and `/select-title` have `post`; `paths[".../diff"]["get"]` parameters include a query parameter named `from`.

`backend/tests/articles/test_art_route_auth.py`: append `("PATCH", "/api/blog-agent/articles/{id}", {"baseVersionId": "<uuid>", "tags": ["x"]})` to `ROUTES` and to `FORBIDDEN` with `Permission.EDIT`.

**Implementation notes.** Query alias, repeated list query and the `from` field alias verified in the backend:dev image on 2026-09-17: `from_: Annotated[uuid.UUID, Query(alias="from")]` accepts `?from=…`; `status: Annotated[list[Literal[...]] | None, Query()] = None` collects `?status=A&status=B`; `from_value: str | None = Field(alias="from")` on an `ApiModel` serialises as `"from"` and appears as property `from` in OpenAPI.

**TDD order and verification.**
1. Write the tests. Red: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles/test_art_edit_api.py tests/articles/test_art_openapi.py tests/articles/test_art_route_auth.py` → PATCH tests fail with 405 `Method Not Allowed`; OpenAPI model cases for `ArticleEditRequest` and `SeoEdit` fail with `KeyError`; new auth cases fail.
2. Implement `edit_article` and the route. Green: same command → `48 passed` (21 + 14 + 13).
3. Lint: ART-8 paths → exit 0.

**Acceptance covered.** §10.3 "Save with wrong H2 count → 422" (API); "Unknown citation markers rejected" (API 422); §4.5 PATCH transaction order (T1, features 503, T2 status moves from READY, QGF and APPROVED; slug rule); §10.8 "ART API-side calls carry the article's run and its `trace_id`" (step context built with `run_id=article.run_id`); §8.3 OpenAPI shape conformance for every ART model.

### ART-final: track verification

**Files.** No new files. Fix only owned files if a gate fails.

**Steps (all in Docker, in this order).**
1. Import surface: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py` → all passed. A failure in another track's file is reported as a `Request:` line, not fixed.
2. Full track run: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/articles` → `274 passed` (assembly 29, schemas 36, fixtures 19, agents 53, versions 9, steps 25, views 9, read API 21, actions API 25, edit API 21, OpenAPI 14, route auth 13), 0 failed, 0 errors.
3. Cross-checks owned by others that ART must keep green: `docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_art_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/api/test_rbac_routes.py tests/unit/test_prompt_registry.py tests/unit/test_gateway.py` → all passed (every ART route has a principal dependency; ART prompts parse; the gateway's fixture registry finds no malformed ART fixture).
4. Lint, format and types on every owned path:
   ```bash
   docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c \
     "ruff check --no-cache src/mdcopilot_blog/agents/deep_research_analyst.py src/mdcopilot_blog/agents/writer.py src/mdcopilot_blog/services/articles.py src/mdcopilot_blog/services/article_views.py src/mdcopilot_blog/services/versions.py src/mdcopilot_blog/services/article_steps.py src/mdcopilot_blog/domain/article_assembly.py src/mdcopilot_blog/api/routers/articles.py src/mdcopilot_blog/api/schemas_articles.py tests/articles \
      && ruff format --check --no-cache src/mdcopilot_blog/agents/deep_research_analyst.py src/mdcopilot_blog/agents/writer.py src/mdcopilot_blog/services/articles.py src/mdcopilot_blog/services/article_views.py src/mdcopilot_blog/services/versions.py src/mdcopilot_blog/services/article_steps.py src/mdcopilot_blog/domain/article_assembly.py src/mdcopilot_blog/api/routers/articles.py src/mdcopilot_blog/api/schemas_articles.py tests/articles \
      && mypy --cache-dir=/tmp/mypy --follow-imports=silent src/mdcopilot_blog/agents/deep_research_analyst.py src/mdcopilot_blog/agents/writer.py src/mdcopilot_blog/services/articles.py src/mdcopilot_blog/services/article_views.py src/mdcopilot_blog/services/versions.py src/mdcopilot_blog/services/article_steps.py src/mdcopilot_blog/domain/article_assembly.py src/mdcopilot_blog/api/routers/articles.py src/mdcopilot_blog/api/schemas_articles.py"
   ```
   → `All checks passed!`, `N files already formatted`, `Success: no issues found in 9 source files`.
5. Layering spot checks (read-only greps inside the tools container): `docker compose run --rm --no-deps tools sh -c "grep -n 'pydantic_ai\|mdcopilot_blog.db' src/mdcopilot_blog/agents/writer.py src/mdcopilot_blog/agents/deep_research_analyst.py; grep -n 'from mdcopilot_blog\.\(api\|services\|db\|llm\|agents\)' src/mdcopilot_blog/domain/article_assembly.py"` → no output (exit 1 from `grep` is the expected result).
6. Reviewer re-run uses `BLOG_TEST_DB=mdcopilot_blog_art_review_test` with the step 2 command.
7. Track report: red and green summary lines per task, the step 1–5 final output lines, and every `Request:` line filed.

**Acceptance mapping.**

| Bullet (CONTRACT §10) | ART proof |
|---|---|
| 10.3 Deep Research Analyst + versioned `blog_research_packets` | ART-4 tests 13, 14, 21, 23; ART-6 tests 4, 5, 6, 7; ART-7 test 18 |
| 10.3 Writer: typed `ArticleDraft`, avoid bundle + recent articles inputs, deterministic assembly and positional parsing, revise resolutions, component regeneration | ART-1 tests 1–19; ART-4 tests 9–12, 15–20; ART-6 tests 8, 12, 13, 15, 16, 17 |
| 10.3 Version history and diff API | ART-5 tests 6–8; ART-7 tests 10–15; ART-9 OpenAPI tests |
| 10.3 Word-count and structure checks pass on the draft fixture | ART-1 test 1; ART-3 tests 2, 4, 6, 7; ART-6 test 8 |
| 10.3 Unknown citation markers rejected | ART-1 test 15; ART-4 tests 10, 15; ART-5 test 3; ART-9 test 6 |
| 10.3 Regenerating one section → exactly one new version, other sections byte-identical | ART-1 test 17; ART-6 test 12 (INT adds the workflow test) |
| 10.3 Regenerating research → new packet version, old kept | ART-6 test 4 (INT adds the workflow test) |
| 10.3 Save with wrong H2 count → 422 | ART-1 test 4; ART-9 test 5 |
| 10.3 `produce_article` P1–P3, `regenerate_component`, `regenerate_research` (INT primary) | seams delivered by ART-6; intake and workflow ids by ART-8 |
| 10.3 Tables / UPDATE trigger (FOUND primary) | ART never updates version rows (ART-5 notes); relies on FOUND's migration test |
| 10.4 Regenerating the article creates new versions and keeps old | ART-6 test 9 |
| 10.5 Article review split screen and human actions (UI primary) | ART-7 tests 1–18 (data), ART-8 tests 1–14 (regenerate, headline picker), ART-9 tests 1–19 (save) |
| 10.5 Viewer sees no mutating controls; API rejects the calls | ART-8/ART-9 `test_art_route_forbidden_without_permission` |
| 10.8 API-side calls carry the article's run and `trace_id` | ART-9 test 1 (`sc.call.run_id`, `sc.call.trace_id`) |
| §5.8 ART golden-path invariants | ART-3 tests 2–7; ART-6 tests 8, 12 |
| §8.3 route and shape rules | ART-2 test 1; ART-9 OpenAPI tests; route auth file |

## Open questions and contract gaps (filed as `Request:` lines when the track starts)

1. Plan filename: CONTRACT §2.2 lists `art.md`; this plan was requested as `ART.md` (the same file on the case-insensitive macOS volume).
2. `GET /articles` `view` → status sets are not defined in §4.5. This plan fixes them (ART-7 rule 1); UI must use the same sets.
3. `ActionAccepted.candidate_id` for article actions is unspecified. ART returns `article.candidate_id`; QUAL (`recheck`) and PUB (`publish`) should choose the same.
4. Writer revise uses finding references `F1..Fn` in the order findings are passed, mapped back to real finding ids in code (static fixtures cannot name dynamic ids such as `claim:<uuid>`). QUAL's scenario overlays that shadow `writer/writer_revise.json` and INT's fix-pass tests must use these references.
5. Citation markers are accepted only in section bodies (titles, pull quote, CTA and excerpt are rejected). Not stated in §5.3/§5.8; it constrains QUAL's writer overlays and the FOUND golden article (guarded by ART-1 test 2).
6. The §8.1 graph builders must allow several article graphs in one database session: `blog_sources.url_hash` is unique and `with_seo=True` copies the golden slug into the partial unique `uq_blog_articles_slug`. ART tests build extra graphs with `with_seo=False`; the builder must reuse ledger sources by `url_hash`.
7. PATCH features failure (503) leaves a human-created version without an `article.edit` audit row, because §4.5 places the audit in T2.
8. PATCH with `seo` edits when the base version has no SEO row is unspecified; ART returns 422 `Request validation failed` with a string detail.
9. `recheck_required` with no current version: ART returns `false`.
10. `ArticleDetailOut.quality_gates` follows §4.5 literally (latest gate review of any run kind, including `deterministic`), while `GateBadgeOut` and `gates_passed_on_current_version` ignore deterministic runs.
11. Regenerate writes and commits its audit row before enqueueing (Phase 1 order), so a 503 leaves an `article.regenerate` audit row.
12. Research packet sources are the deep research run's `source_ids` only (first 20); RES's `run_deep_research` must include the candidate's primary source in that run.
13. ART's gateway tests patch `mdcopilot_blog.llm.gateway.build_model_factory` (named in §5.5) because `LLMGateway.__init__` is not frozen; a PROV change that stops `build_gateway` from calling it needs a `Request:`.
