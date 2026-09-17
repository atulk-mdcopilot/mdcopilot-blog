# Track PUB: Publishing — implementation plan

Status: plan for review (W1 planning). Date: 2026-09-17. Binding contract: `docs/blog-agent/plans/phases-2-10/CONTRACT.md` (revision 3). When this plan and the contract disagree, the contract wins. Paths are relative to `mdcopilot-blog/`; `pkg/` means `backend/src/mdcopilot_blog/`.

**Cross-check findings applied 2026-09-17** (see Appendix: Cross-check findings at the end of this file for the full verification and any rejections): §5.6 `services.lineage.effective_seo` now backs `render_version`'s SEO lookup (finding 1); `POST /publish` calls `ensure_agent_enabled` (finding 3); test graphs use FOUND's `graph_builders.make_child_version` in place of PUB's own `add_version_copy` (finding 4); `request_publish` returns `candidate_id=article.candidate_id` (finding 5); `DueOutcome.detail` is filled on a due export validation failure (finding 6). Finding 2 (`ArticleDetailOut.network_publishing_active`/`gate_override_policy`) is ART's and UI's fix; see the appendix for what, if anything, that means for PUB.

## Header

### Goal
Build the Phase 7 publishing backend:
- a Quill-safe renderer (markdown-it-py → nh3 allowlist → pull quote, references, mandatory disclosure);
- the manual export path (`APPROVED → EXPORTED → PUBLISHED`) with an export bundle for the UI's clipboard, copy and download controls;
- the MDCopilot API publisher behind `BLOG_PUBLISHING_ENABLED` (credential login, bearer-only calls, create/update that always sends `slug`, exact-slug reconciliation, exactly one remote post per article);
- scheduling (`SCHEDULED`, the `publish_due` seams INT wraps);
- the §4.7 API;
- a fake MDCopilot blog API (in-process and as the `fake-mdcopilot` compose service) that mirrors the real backend;
- Spike S5 tooling and results file, and the owner's manual paste-check steps.

With default settings nothing is ever sent over the network.

### Spec sections implemented
- ARCHITECTURE §6: article and publication transitions used by publishing, and the rule that `BLOG_PUBLISHING_ENABLED` gates only network publishers.
- ARCHITECTURE §13 "Export UX": the backend half (bundle with `html`, `text`, title, slug, excerpt, SEO, social copy, references).
- ARCHITECTURE §14 Publishing: protocol, `ManualExportPublisher`, `MDCopilotApiPublisher`, rendering and validation, idempotency, scheduling.
- ARCHITECTURE §16 rows `preview`, `export`, `confirm-published`, `publish`, `schedule`, `unschedule`.
- ARCHITECTURE §17: `blog.publish`, `blog.schedule` (+ `blog.publish` while a network publisher is active), HTML safety, audit of export/publish/schedule.
- IMPLEMENTATION_PLAN Phase 7 (Spike S5, Build, Acceptance).
- CONTRACT §2.2 PUB, §2.5 `fake-mdcopilot`, §3.1 `blog_publications`, §4.7, §5.6 `publication_steps`, §5.8 PUB golden invariant, §6 publisher settings and publisher facts, §9 rows "Spike S5" and "Manual paste check", §10.5 rows "Preview never renders raw model HTML" (PUB part) and "Viewer sees no mutating controls; the API rejects the calls anyway" (PUB routes), §10.6 every row.

### Owned files (CONTRACT §2.2 PUB, copied)

| Path | Notes |
|---|---|
| `pkg/publishing/renderer.py`, `manual_export.py`, `mdcopilot_api.py`, `factory.py` | |
| `pkg/publishing/__init__.py`, `pkg/publishing/null.py` | Phase 1 files (`NullPublisher`, used by the factory) |
| `pkg/publishing/base.py` | may add fields with defaults only |
| `docs/blog-agent/spikes/S5-mdcopilot-publisher.md` | Spike S5 results (§9) |
| `docs/blog-agent/PUBLISHING_MANUAL_CHECK.md` | owner's manual paste-check steps (§9); INT links it from `LOCAL_DEVELOPMENT.md` |
| `pkg/services/publications.py` | API services |
| `pkg/services/publication_steps.py` | stub by FOUND |
| `pkg/api/routers/publishing.py`, `pkg/api/schemas_publishing.py` | stub by FOUND |
| `backend/fakes/**` | fake MDCopilot API (`fakes/__init__.py`, `fakes/mdcopilot_api/__init__.py`, `fakes/mdcopilot_api/app.py`) |
| `backend/tests/publishing/**`, `backend/tests/unit/test_null_publisher.py` | |
| `docs/blog-agent/plans/phases-2-10/pub.md` | |

Also owned (CONTRACT §2 rules): `.superpowers/sdd/phases-2-10/requests/pub.md` (`Request:` and `Live:` lines).

Files this plan creates inside those paths: `backend/fakes/mdcopilot_api/smoke.py`, `backend/tests/publishing/pub_helpers.py`, `backend/tests/publishing/conftest.py` (replacing FOUND's docstring-only file), and the `test_pub_*.py` files named in the tasks. This plan file is `PUB.md`, as assigned by the controller. CONTRACT §2.2 names the file `pub.md`; see open questions.

`pkg/publishing/__init__.py` and `pkg/publishing/null.py` need no edit. `tests/unit/test_null_publisher.py` needs no edit and runs in the track suite.

### Extension points consumed (FOUND and Phase 1, exact names)
- ORM (`mdcopilot_blog.db.models`): `Article`, `ArticleVersion`, `VersionSeo`, `ArticleSource`, `LedgerSource`, `Publication`, `User`, `AuditLog`.
- Enums (`mdcopilot_blog.domain.enums`): `ArticleStatus`, `PublicationStatus`, `PublisherKey`, `ApprovalMode`, `Permission`, `Role`.
- `mdcopilot_blog.domain.state_machine`: `Entity`, `InvalidTransition`, `require_transition`. `mdcopilot_blog.domain.rbac.permissions_for`.
- `mdcopilot_blog.domain.contracts`: `BlogSource`, `SEOMetadata`, `SocialCopy`, `TitleOptions`, `ArticleDraft` (tests).
- `mdcopilot_blog.domain.text`: `CITATION_MARKER_RE`, `strip_citation_markers`, `extract_markers`, `assemble_markdown` (tests).
- `mdcopilot_blog.domain.errors.PublishingDisabled` (global 409 `Publishing disabled`, CONTRACT §4.0).
- `mdcopilot_blog.domain.config.EffectiveConfig` (field `publisher: PublisherKey`).
- `mdcopilot_blog.services.config`: `load_effective_config(db, settings, *, run_id=None)`, `load_brand_profile(db)` (`BrandProfileValues.ai_disclosure`).
- `mdcopilot_blog.services.article_status.set_article_status(db, *, article_id, target) -> Article`.
- `mdcopilot_blog.services.enqueue`: `enqueue_workflow(client, *, workflow_name, queue_name, workflow_id, args, timeout_seconds) -> ActionAcceptedParts`.
- `mdcopilot_blog.services.audit.audit(db, *, actor_user_id, action, entity_type, entity_id=None, reason=None, details=None)`.
- `mdcopilot_blog.workflows.names`: `WORKFLOW_PUBLISH_ARTICLE`, `QUEUE_INTERACTIVE`.
- API: `mdcopilot_blog.api.schemas.ApiModel`; `mdcopilot_blog.api.schemas_common`: `ActionAccepted`, `ArticleStateOut`; `mdcopilot_blog.api.deps`: `Principal`, `SessionDep`, `SettingsDep`, `WorkflowClientDep`, `require_permission`, `utcnow`; `mdcopilot_blog.errors.ProblemError`; the FOUND stub `router = APIRouter(tags=["publishing"])` already registered in `ROUTERS` under `/api/blog-agent`.
- `mdcopilot_blog.ids.uuid7`.
- `Settings` fields: `publishing_enabled`, `publisher`, `publisher_api_url`, `publisher_login_id`, `publisher_password`, `publisher_public_url`, `publisher_timeout_seconds`, `publisher_login_path`, `production_timeout_minutes`, `app_version`.
- Tests: root conftest fixtures `settings`, `db_session`, `seeded_db`, `effective_config`, `app`, `client`, `login_as`, `make_user`, `fake_workflow_client`, `clean_db`, `committed_seed`, `sessionmaker_committing`, `make_article_graph` (CONTRACT §8.1, returns `ArticleGraphIds`); `mdcopilot_blog.auth.users.create_user`; `mdcopilot_blog.db.seed.load_seed_file`; golden files `backend/fixtures/mock/golden/article_draft.json`, `ledger.json`, `seo.json`; `backend/tests/api_shapes.json`; `mdcopilot_blog.api.app.create_app`; `mdcopilot_blog.workflows.client.FakeWorkflowClient` (`enqueued: list[EnqueueCall]`, `enqueue_error`).
- Compose service `fake-mdcopilot` (CONTRACT §2.5, command `uvicorn fakes.mdcopilot_api.app:app --host 0.0.0.0 --port 8000`, working dir `/app`).

### What PUB produces for other tracks
- INT: `publication_steps.publish_article`, `select_due_articles`, `process_due_article` with the CONTRACT §5.6 signatures. `DueOutcome.action` drives notifications: `exported` → `SCHEDULED_EXPORT_DUE`, `publish_failed` → `PUBLISH_FAILED`.
- UI: the §4.7 endpoints. `ExportBundleOut.html` feeds the `text/html` clipboard item, `ExportBundleOut.text` feeds `text/plain`, and `PreviewOut.html` is DOMPurify-ready.
- OBS: `blog_publications` rows (`updated_at` for exported calendar entries) and head columns `scheduled_for`, `published_at`, `published_url`.
- HARD: the fake API for failure injection; `factory.build_publisher(settings, key, *, transport=None)` as the transport injection point.

### Test database and exact Docker commands
- `BLOG_TEST_DB=mdcopilot_blog_pub_test`. Reviewers and any second process use `mdcopilot_blog_pub_review_test`.
- Track suite:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/publishing tests/unit/test_null_publisher.py
  ```
- Single file (used in every task, replace `<file>`):
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/publishing/<file>
  ```
- Import surface check (before reporting any red test as PUB's own):
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
  ```
- Lint and type gate (owned paths only):
  ```bash
  docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools sh -c \
    "ruff check --no-cache src/mdcopilot_blog/publishing src/mdcopilot_blog/services/publications.py src/mdcopilot_blog/services/publication_steps.py src/mdcopilot_blog/api/routers/publishing.py src/mdcopilot_blog/api/schemas_publishing.py fakes tests/publishing tests/unit/test_null_publisher.py \
     && ruff format --check --no-cache src/mdcopilot_blog/publishing src/mdcopilot_blog/services/publications.py src/mdcopilot_blog/services/publication_steps.py src/mdcopilot_blog/api/routers/publishing.py src/mdcopilot_blog/api/schemas_publishing.py fakes tests/publishing tests/unit/test_null_publisher.py \
     && mypy --cache-dir=/tmp/mypy --follow-imports=silent src/mdcopilot_blog/publishing src/mdcopilot_blog/services/publications.py src/mdcopilot_blog/services/publication_steps.py src/mdcopilot_blog/api/routers/publishing.py src/mdcopilot_blog/api/schemas_publishing.py fakes"
  ```
  Below this is called "the PUB lint gate".

### Owner inputs and fallbacks

| Input | Used by | Fallback when missing |
|---|---|---|
| `BLOG_PUBLISHER_LOGIN_ID` / `BLOG_PUBLISHER_PASSWORD` for a local MDCopilot dev admin, and the local MDCopilot backend running with `ENVIRONMENT=development` at `BLOG_PUBLISHER_API_URL` | Spike S5 (PUB-12) | Everything runs against the in-process fake and the `fake-mdcopilot` container. `docs/blog-agent/spikes/S5-mdcopilot-publisher.md` starts with `Status: pending owner input (BLOG_PUBLISHER_LOGIN_ID/BLOG_PUBLISHER_PASSWORD for a local dev admin; local MDCopilot backend with ENVIRONMENT=development)`. `requests/pub.md` gets `Request: S5 pending — needs BLOG_PUBLISHER_LOGIN_ID/BLOG_PUBLISHER_PASSWORD and a running local MDCopilot backend (ENVIRONMENT=development)`. `BLOG_PUBLISHING_ENABLED` stays false. |
| Controller go for S5 (S5 creates and deletes a draft post in the owner's local MDCopilot database) | PUB-12 | Same as above. The live test is never run without a `Request: S5 go` answered by the controller. |
| Owner performs the manual paste check | PUB-12 doc | `docs/blog-agent/PUBLISHING_MANUAL_CHECK.md` ends with `Result: pending owner check`. |

Presence check (prints only `set`/`missing`):
```bash
docker compose run --rm --no-deps tools sh -c 'for v in BLOG_PUBLISHER_LOGIN_ID BLOG_PUBLISHER_PASSWORD; do eval "x=\$$v"; test -n "$x" && echo "$v set" || echo "$v missing"; done'
```

### Track-wide rules
1. TDD in every task: write the listed tests, run them red in Docker, implement, run them green, then run the PUB lint gate. Record the red and green summary lines in the track report.
2. Save points import cleanly. Modules are built in dependency order: renderer → base/manual export → fake → API publisher → factory → services → router → seams. The router gains routes only after the service functions they call exist. `publication_steps.py` keeps FOUND's signatures at every save.
3. Default suites make no network calls. HTTP goes through `httpx.ASGITransport(app=<fake app>)` or `httpx.MockTransport`. The only network test is `test_pub_s5_live.py` (`@pytest.mark.live`).
4. Layering:
   - `pkg/publishing/` imports no `dbos`, no `pydantic_ai`, no `mdcopilot_blog.api` and no `mdcopilot_blog.db`.
   - `backend/fakes/` imports nothing from `mdcopilot_blog`.
   - Services and seams do all database I/O.
5. Secrets:
   - The publisher never logs or returns the password or the access token, and no error message contains them.
   - Tests use the fake's non-secret constants `FAKE_LOGIN_ID` and `FAKE_PASSWORD`.
6. Writes:
   - PUB writes `blog_publications` and `audit_log`.
   - PUB writes these `blog_articles` head columns: `status` (only through `set_article_status`), `scheduled_for`, `scheduled_by`, `published_at`, `published_url`, `published_version_id`.
   - Every other table is read-only for PUB production code.
7. Every publish and export uses `blog_articles.approved_version_id` (the exact human-approved version). The current version is used only by the preview default.
8. Row lock order is always the `blog_articles` row first (`SELECT … FOR UPDATE`), then the `blog_publications` row.
9. Audit rows use `entity_type="blog_article"` (`services.publications.ARTICLE_ENTITY`), `entity_id=str(article.id)`, camelCase detail keys. Seams write `actor_user_id=None`.

### Design decisions fixed by this plan (inside the contract)
- **P1. Network publishing is active** iff `settings.publishing_enabled` is true and the publisher built for `EffectiveConfig.publisher` reports `capabilities().network` true (`factory.network_publishing_active`). Only then:
  - `POST /publish` and the `publish_article` seam proceed;
  - `POST /schedule` also requires `blog.publish`;
  - a due article takes the network path.
  In every other configuration a due article takes the manual export path, and nothing is sent.
- **P2. Export always uses `ManualExportPublisher`** (`publisher=manual_export`, `target=manual`), whatever `EffectiveConfig.publisher` is (ARCHITECTURE §6: export is always available to `blog.publish` holders).
- **P3. Draft publishing** (`as_draft=true`) moves the article to `PUBLISHED` with `published_url = NULL`. The publication row has `as_draft=true` and the remote `external_post_id`.
- **P4. Adoption safety.** `find_existing` matches `slug` exactly. The publisher adopts a found post only when its `title` also equals the payload title; otherwise it fails and never overwrites the post (`RemotePost.title` is added with default `None`).
- **P5. Rendering layout.** Each `[S<n>]` marker becomes an inline link `[k]`, where `k` is the 1-based position of that source in the references list (sorted by marker number). The rendered order is: body, then pull quote `<blockquote>`, then `<h2>References</h2><ol>`, then disclosure `<p><em>…</em></p>`. Reference URLs are `blog_sources.canonical_url`.
- **P6.** When a due article's export fails validation, the article is unscheduled (`SCHEDULED → APPROVED`) and the outcome is `publish_failed`, so INT notifies publish holders.
- **P7.** `publish_article` called with a `version_id` other than `approved_version_id` raises `ValueError`.

---

## Tasks

### PUB-1: Renderer and publish validation

**Files**
- Create `backend/src/mdcopilot_blog/publishing/renderer.py`.
- Create `backend/tests/publishing/pub_helpers.py` (PUB-1 part), `backend/tests/publishing/test_pub_renderer.py`.

**Interfaces**
- Consumes: `domain.contracts.BlogSource`, `SEOMetadata`; `domain.text.CITATION_MARKER_RE`, `strip_citation_markers`, `extract_markers`; `publishing.base.Issue`, `PublishPayload`.
- Produces (`pkg/publishing/renderer.py`):
```python
ALLOWED_TAGS: frozenset[str]                  # {"h2","h3","p","strong","em","s","a","ul","ol","li","blockquote","img"}
ALLOWED_ATTRIBUTES: Mapping[str, frozenset[str]]  # {"a": {"href"}, "img": {"src", "alt"}}
TITLE_MAX_LENGTH = 200
SLUG_MAX_LENGTH = 200
EXCERPT_MAX_LENGTH = 500
SLUG_RE: re.Pattern[str]                      # ^[a-z0-9]+(?:-[a-z0-9]+)*$
VALID_MARKER_RE: re.Pattern[str]              # ^S[1-9][0-9]*$
MARKDOWN: MarkdownIt
def markdown_to_html(markdown: str) -> str
def sanitize_html(html: str) -> str
def link_citations(markdown: str, references: Sequence[BlogSource]) -> str
def render_article_html(*, content_markdown: str, pull_quote: str, references: Sequence[BlogSource], disclosure: str) -> str
def html_to_text(html: str) -> str
def compute_payload_hash(*, html: str, title: str, slug: str, excerpt: str) -> str
def validate_payload(payload: PublishPayload) -> list[Issue]
@dataclass(frozen=True)
class PublishableCheck:
    title: str; slug: str | None; excerpt: str; html: str; content_markdown: str
    seo: SEOMetadata | None; references: Sequence[BlogSource]; disclosure: str
def validate_publishable(check: PublishableCheck) -> list[Issue]
```
- Produces (`tests/publishing/pub_helpers.py`):
  - `ParsedMarkup(tags: list[str], attributes: list[tuple[str, str, str | None]])` and `parse_markup(html: str) -> ParsedMarkup`. Uses stdlib `HTMLParser`; collects start and self-closing tag names and `(tag, attribute, value)` triples.
  - `FIXTURE_NOW = datetime(2026, 9, 17, 1, 30, tzinfo=UTC)`.
  - `golden_render_inputs() -> tuple[str, str, list[BlogSource], str]`, returning `(content_markdown, pull_quote, references, disclosure)`:
    - `content_markdown = assemble_markdown(ArticleDraft.model_validate(article_draft.json["output"]).sections)`;
    - `pull_quote` is the draft's pull quote;
    - references are the first five entries of `ledger.json["sources"]` in list order, as `BlogSource(marker=f"S{i}", source_id=f"golden-S{i}", title, url=canonicalUrl, publisher, published_at=FIXTURE_NOW - timedelta(days=publishedOffsetDays))`;
    - `disclosure = load_seed_file("brand_profile.yaml")["ai_disclosure"]`.
    If FOUND's `ledger.json` uses a different top-level key, the helper follows FOUND's file.
  - `XSS_MARKDOWN: str`. Seven sections with exactly six `## ` headings. Bodies contain `<script>alert(1)</script>`, `<img src=x onerror=alert(1)>`, `[x](javascript:alert(1))`, `![y](javascript:alert(2))`, `<iframe src="https://evil.example"></iframe>`, `[rel](/admin)`, `[data](data:text/html,hi)`, `[mail](mailto:a@b.example)` and the marker `[S1]`.

**Behaviour rules**
1. `MARKDOWN = MarkdownIt("js-default", {"html": False}).disable("table")` at module level. `markdown_to_html(md)` returns `MARKDOWN.render(md)` and does no sanitising.
2. `sanitize_html(html)` calls `nh3.clean` with:
   - `tags=set(ALLOWED_TAGS)`;
   - `attributes` = `ALLOWED_ATTRIBUTES` as sets;
   - `url_schemes={"http", "https"}`;
   - `link_rel="noopener noreferrer"`;
   - an `attribute_filter` that returns `None` for any `href` or `src` value whose stripped, lower-cased form does not start with `http://` or `https://`.
   All other nh3 defaults stay: comments stripped, `script` and `style` content removed, other disallowed tags removed with their text kept.
3. Valid references are those whose `marker` matches `VALID_MARKER_RE`, ordered by `int(marker[1:])`. A reference's number `k` is its 1-based position in that order. Its encoded URL is `E = urllib.parse.quote(url.strip(), safe=":/?#[]@!$&'()*+,;=%")`. It is "http(s)" when `url.strip().lower()` starts with `http://` or `https://`.
4. `link_citations(markdown, references)` replaces every `CITATION_MARKER_RE` match:
   - marker not among the valid references → text unchanged;
   - http(s) reference → `[\[k\]](<E>)`;
   - any other reference → `\[k\]`.
5. `render_article_html(...)` concatenates these parts in order, then calls `sanitize_html` once on the whole string:
   1. `markdown_to_html(link_citations(content_markdown, references))`.
   2. If `q = strip_citation_markers(pull_quote).strip()` is non-empty: `<blockquote>{html.escape(q, quote=False)}</blockquote>\n`.
   3. If there is at least one valid reference: `<h2>References</h2>\n<ol>\n`, then one `<li>{L}{P}{D}</li>\n` per valid reference in rule-3 order, then `</ol>\n`.
      - `L` is `<a href="{html.escape(E)}">{html.escape(title.strip() or E)}</a>` for an http(s) reference, else `html.escape(title.strip() or url.strip())`.
      - `P` is `, {html.escape(publisher.strip())}` when the publisher is non-blank, else empty.
      - `D` is `, {d.day} {d:%B} {d.year}` with `d = published_at.astimezone(UTC)` when `published_at` is not None, else empty.
   4. If `disclosure.strip()` is non-empty: `<p><em>{html.escape(disclosure.strip(), quote=False)}</em></p>`.

   Equal inputs give byte-identical output. When the disclosure is non-blank, the output ends with `</em></p>`.
6. `html_to_text(html)` uses `html.parser.HTMLParser(convert_charrefs=True)`:
   - Start and end tags of `h2`, `h3`, `p` and `blockquote` close the current text block.
   - `ul` and `ol` open a list. Each `li` is one line: `- <text>` inside `ul`, `<n>. <text>` inside `ol` (`n` counts from 1 per list). A list's lines form one block joined by `\n`.
   - At an `a` end tag, ` (<href>)` is appended when the start tag had an `href` whose value differs from the collected link text.
   - An `img` appends `[image: <alt>]`, or `[image]` when `alt` is blank or missing.
   - Whitespace runs inside a block collapse to one space and each block is stripped. Empty blocks are dropped.
   - The result is the blocks joined by `\n\n` plus one trailing `\n`. It is the empty string when there are no blocks.
7. `compute_payload_hash` = `hashlib.sha256("\x1f".join((html, title, slug, excerpt)).encode("utf-8")).hexdigest()`.
8. Field checks, in this order (lengths are `len(str)`):
   - **title**: blank → `title is required`; else longer than 200 → `title must be at most 200 characters (got <n>)`.
   - **slug**: `None` or blank → `slug is required`. Otherwise two independent checks: longer than 200 → `slug must be at most 200 characters (got <n>)`; no `SLUG_RE` match → `slug must contain only lowercase letters, digits and single hyphens`.
   - **excerpt**: blank → `excerpt is required`; else longer than 500 → `excerpt must be at most 500 characters (got <n>)`.
   - **content**: `html.strip()` empty → field `content`, message `content is empty`.
9. `validate_payload(payload)` applies rule 8 to `payload.title`, `slug`, `excerpt`, `html`.
10. `validate_publishable(check)` applies rule 8 to `check.title`, `slug`, `excerpt`, `html`, then appends in order:
    1. Unknown markers: `ms = [m for m in extract_markers(check.content_markdown) if m not in {valid reference markers}]`. If non-empty: `Issue("content", "unknown citation markers: " + ", ".join(ms))`.
    2. `seo is None` → `Issue("seo", "SEO metadata is missing for this version")`.
    3. `references` empty → `Issue("references", "at least one cited source is required")`. Otherwise, for each reference in the given order: invalid marker → `Issue("references", f"reference marker '{m}' is invalid")`; valid marker but URL not http(s) → `Issue("references", f"reference {m} has no http(s) URL")`.
    4. `disclosure.strip()` empty → `Issue("disclosure", "AI-assistance disclosure is required")`.

**Tests to write first** (`tests/publishing/test_pub_renderer.py`; no database; 22 functions, 32 cases)
- `REF1 = BlogSource(marker="S1", source_id="a", title="Study one", url="https://a.example/1", publisher="NIH", published_at=None)`.
- `REF2 = BlogSource(marker="S2", source_id="b", title="Study two", url="https://b.example/2", publisher="FDA", published_at=None)`.
- Unless a test says otherwise, `render_article_html` calls use `content_markdown="Fact [S1].\n"`, `pull_quote=""`, `references=[REF1]`, `disclosure="D."`; `out` is the result.

1. `test_markdown_options_disable_html_linkify_typographer_and_tables`: `renderer.MARKDOWN.options["html"] is False`, `options["linkify"] is False`, `options["typographer"] is False`, `"table" not in renderer.MARKDOWN.get_active_rules()["block"]`.
2. `test_sanitize_removes_disallowed_tags_and_keeps_text`: `out = sanitize_html(markdown_to_html(SOURCE))`. `SOURCE` is a Markdown string with these blocks separated by blank lines:
   - the line `#### h4`;
   - the line `---`;
   - a fenced code block (three backticks) containing the line `code`;
   - a pipe table `| a | b |` / `|---|---|` / `| 1 | 2 |`;
   - the paragraph `` `inline` ``.

   Asserts: `set(parse_markup(out).tags) <= ALLOWED_TAGS`; none of `"<h4"`, `"<hr"`, `"<pre"`, `"<code"`, `"<table"` occurs in `out`; `"h4"`, `"code"`, `"inline"` and `"| a | b |"` occur in `out` as text.
3. `test_raw_html_and_event_handlers_never_become_markup`: `render_article_html(content_markdown="<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n<iframe src=\"https://evil.example\"></iframe>\n", pull_quote="", references=[], disclosure="D.")`. Asserts: `"<script" not in out.lower()`, `"<iframe" not in out.lower()`; no attribute name in `parse_markup(out).attributes` starts with `on`; `"&lt;script&gt;alert(1)&lt;/script&gt;" in out`.
4. `test_only_http_and_https_urls_survive`: markdown `"[a](javascript:alert(1)) [b](/admin) [c](mailto:a@b.example) [d](data:text/html,hi) ![e](javascript:alert(2)) ![f](/x.png) [g](https://ok.example/p?q=1) ![h](https://i.example/a.png)\n"` through `sanitize_html(markdown_to_html(...))`. The `href`/`src` values in `parse_markup(out).attributes` are exactly `["https://ok.example/p?q=1", "https://i.example/a.png"]` in document order.
5. `test_every_link_gets_noopener_noreferrer`: `out = render_article_html(content_markdown=<test 4 markdown> + "\nCited [S1].\n", pull_quote="", references=[REF1], disclosure="D.")`. Every `a` tag in `parse_markup(out)` has exactly one `rel` attribute, whose value is `"noopener noreferrer"`.
6. `test_citation_markers_become_numbered_links`: `render_article_html(content_markdown="Alpha [S1]. Beta [S2] and [S1].\n", pull_quote="", references=[REF1, REF2], disclosure="D.")`. Asserts:
   - `out.count('<a href="https://a.example/1" rel="noopener noreferrer">[1]</a>') == 2` (the two citations; the references entry uses the title `Study one` as its link text);
   - `'<a href="https://b.example/2" rel="noopener noreferrer">[2]</a>' in out`;
   - `'<a href="https://a.example/1" rel="noopener noreferrer">Study one</a>, NIH' in out`;
   - `"[S1]" not in out`.
7. `test_citation_numbers_follow_reference_order_when_markers_skip`: references `[REF1, REF3]` where `REF3` is `REF2` with `marker="S3"`; content `"See [S3].\n"`. Asserts: `'rel="noopener noreferrer">[2]</a>' in out`; the `<ol>` block contains exactly 2 `<li>`.
8. `test_unknown_marker_stays_plain_text`: content `"Claim [S9].\n"`, references `[REF1]`. Asserts: `"Claim [S9]." in out` and no anchor text `[9]`.
9. `test_citation_and_reference_urls_are_percent_encoded`: reference `S1` with url `"https://www.nih.gov/news (x)"`, content `"Fact [S1].\n"`. `out.count('href="https://www.nih.gov/news%20(x)"') == 2`.
10. `test_non_http_reference_renders_plain_number_and_title`: reference `S1` with url `"ftp://files.example/x"`, title `"FTP doc"`, publisher `""`. Asserts: `"Fact [1]." in out`; `"<li>FTP doc</li>" in out`; no `href` attribute in the output.
11. `test_article_parts_are_ordered_and_end_with_disclosure`: content `"Body text.\n"`, pull quote `"Pull line"`, references `[REF1]`, disclosure `"Disclosure text."`. Asserts: `out.index("Body text.") < out.index("<blockquote>Pull line</blockquote>") < out.index("<h2>References</h2>") < out.index("<p><em>Disclosure text.</em></p>")`, and `out.endswith("<p><em>Disclosure text.</em></p>")`.
12. `test_reference_item_format` (parametrized, 2 cases): reference `S1`, title `"Study & results"`, publisher `"NIH"`, url `"https://a.example/1"`.
    - `published_at=datetime(2026, 9, 10, 5, 0, tzinfo=UTC)` → `'<li><a href="https://a.example/1" rel="noopener noreferrer">Study &amp; results</a>, NIH, 10 September 2026</li>' in out`.
    - `published_at=None` → `'<li><a href="https://a.example/1" rel="noopener noreferrer">Study &amp; results</a>, NIH</li>' in out`.
13. `test_blank_pull_quote_and_empty_references_are_omitted`: pull quote `"   "`, references `[]`, disclosure `"D."`. Asserts: `"<blockquote" not in out`, `"References" not in out`, `out.endswith("<p><em>D.</em></p>")`.
14. `test_pull_quote_markers_are_stripped_and_text_escaped`: pull quote `"A <b> quote [S1]"` → `"<blockquote>A &lt;b&gt; quote</blockquote>" in out`.
15. `test_golden_article_renders_allowlisted_markup_ending_with_disclosure`: inputs from `golden_render_inputs()`. Asserts:
    - `set(parse_markup(out).tags) <= ALLOWED_TAGS`;
    - every attribute is one of `("a","href")`, `("a","rel")`, `("img","src")`, `("img","alt")`;
    - `out.count("<h2>") == 7`;
    - for `k` in 1..5 the anchor text `>[k]</a>` occurs at least once;
    - `"[S" not in out`;
    - `out.endswith(f"<p><em>{disclosure}</em></p>")`.
16. `test_render_is_deterministic`: two `render_article_html` calls on the golden inputs return equal strings.
17. `test_html_to_text_rules`: `html_to_text('<h2>Title</h2>\n<p>A <a href="https://x.example">link</a> and <strong>b</strong>.</p>\n<ul>\n<li>one</li>\n<li>two</li>\n</ul>\n<ol>\n<li>first</li>\n</ol>\n<blockquote>Quote</blockquote><p><img src="https://i.example/a.png" alt="chart"></p><p><em>Disclosure.</em></p>')` equals `"Title\n\nA link (https://x.example) and b.\n\n- one\n- two\n\n1. first\n\nQuote\n\n[image: chart]\n\nDisclosure.\n"`. Also `html_to_text("") == ""`.
18. `test_payload_hash_uses_unit_separated_fields`: `compute_payload_hash(html="<p>x</p>", title="T", slug="s", excerpt="e") == hashlib.sha256("<p>x</p>\x1fT\x1fs\x1fe".encode()).hexdigest()`; changing `slug` to `"t"` changes the hash.
19. `test_validate_payload_accepts_values_at_the_limits`: `PublishPayload(article_id=uuid4(), version_id=uuid4(), title="x"*200, slug="a"*200, html="<p>Body</p>", excerpt="x"*500, status="published")` → `validate_payload(...) == []`.
20. `test_validate_payload_field_limits` (parametrized, 10 cases). Base payload: title `"Specialist access"`, slug `"specialist-access"`, excerpt `"Short excerpt"`, html `"<p>Body</p>"`. One field is overridden per case, with the expected `[(field, message)]`:
    1. title `""` → `[("title","title is required")]`
    2. title `"   "` → `[("title","title is required")]`
    3. title `"x"*201` → `[("title","title must be at most 200 characters (got 201)")]`
    4. slug `""` → `[("slug","slug is required")]`
    5. slug `"a"*201` → `[("slug","slug must be at most 200 characters (got 201)")]`
    6. slug `"Bad Slug"` → `[("slug","slug must contain only lowercase letters, digits and single hyphens")]`
    7. slug `"double--hyphen"` → the same pattern message
    8. excerpt `""` → `[("excerpt","excerpt is required")]`
    9. excerpt `"x"*501` → `[("excerpt","excerpt must be at most 500 characters (got 501)")]`
    10. html `"  "` → `[("content","content is empty")]`
21. `test_validate_publishable_reports_every_issue_in_order`: `PublishableCheck(title=" ", slug=None, excerpt="", html="<p>x</p>", content_markdown="Body [S7].", seo=None, references=[], disclosure=" ")` → `[(i.field, i.message) for i in issues]` equals:
    ```
    [("title","title is required"),
     ("slug","slug is required"),
     ("excerpt","excerpt is required"),
     ("content","unknown citation markers: S7"),
     ("seo","SEO metadata is missing for this version"),
     ("references","at least one cited source is required"),
     ("disclosure","AI-assistance disclosure is required")]
    ```
22. `test_validate_publishable_flags_bad_references`: a valid check (title, slug, excerpt, html from test 20's base, `seo = SEOMetadata.model_validate(json.loads(golden seo.json))`, `disclosure="D."`, content `"Text [S2]."`) with references `[BlogSource(marker="X1", source_id="x", title="X", url="https://a.example", publisher="P", published_at=None), BlogSource(marker="S2", source_id="y", title="Y", url="ftp://b.example", publisher="P", published_at=None)]`. The golden `seo.json` is a `SeoPackage`, so `seo = SEOMetadata.model_validate(data["seo"])`. Issues equal `[("references","reference marker 'X1' is invalid"), ("references","reference S2 has no http(s) URL")]`.

**Implementation notes** (verified 2026-09-17 in `python:3.12-slim-trixie` with markdown-it-py 4.2.0 and nh3 0.3.7)
- The constructor below gives `options["html"] is False`, `linkify False`, `typographer False`, and `get_active_rules()["block"]` has no `"table"`. With these options:
  - raw `<script>` renders as escaped text;
  - `[click](javascript:alert(1))` stays literal text (markdown-it's link validator);
  - `[rel](/admin)` and `[m](mailto:…)` become anchors, which the attribute filter strips to `<a rel="noopener noreferrer">`;
  - `<h4>`, `<hr>`, `<pre>` and `<code>` are removed with their text kept;
  - `[\[2\]](<https://example.com/a (b)?x=1&y=2>)` renders `<a href="https://example.com/a%20(b)?x=1&amp;y=2">[2]</a>`.
```python
MARKDOWN = MarkdownIt("js-default", {"html": False}).disable("table")

def _keep_http_urls(tag: str, attribute: str, value: str) -> str | None:
    if attribute in ("href", "src") and not value.strip().lower().startswith(("http://", "https://")):
        return None
    return value

nh3.clean(html, tags=set(ALLOWED_TAGS), attributes={t: set(a) for t, a in ALLOWED_ATTRIBUTES.items()},
          url_schemes={"http", "https"}, link_rel="noopener noreferrer", attribute_filter=_keep_http_urls)
```
- Never put `"rel"` in `attributes` together with `link_rel`: nh3 raises `ValueError: "rel" attribute is not allowed for tag "a" when link_rel is set`.
- nh3 serialises text `&` as `&amp;` and leaves `'` and `"` in text unescaped.
- If `mypy` reports missing stubs for `nh3` or `markdown_it`, put a line-scoped `# type: ignore[import-untyped]` on that import only.

**Verification**
- Red: the single-file command with `<file>` = `test_pub_renderer.py` → collection error `ModuleNotFoundError: No module named 'mdcopilot_blog.publishing.renderer'`.
- Green: same command → `32 passed`.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "Renderer (markdown-it-py js-default tables off → nh3 Quill allowlist → pull quote blockquote + references → mandatory disclosure)".
- §10.6 "Rendered HTML only allow-listed tags; `javascript:` and `<script>` stripped".
- §5.8 PUB golden invariant.
- §10.5 "Preview never renders raw model HTML" (renderer part).

### PUB-2: Payload fields and ManualExportPublisher

**Files**
- Modify `backend/src/mdcopilot_blog/publishing/base.py`: add fields with defaults only.
- Create `backend/src/mdcopilot_blog/publishing/manual_export.py`.
- Create `backend/tests/publishing/test_pub_manual_export.py`.
- `tests/unit/test_null_publisher.py` stays unchanged and must stay green.

**Interfaces**
- Consumes: `renderer.validate_payload`; `publishing.base` models; `domain.enums.PublicationStatus`.
- Produces:
```python
# base.py additions (defaults only)
class PublishPayload(BaseModel): ...; external_post_id: str | None = None   # remote id already known for this article/target
class RemotePost(BaseModel): ...; title: str | None = None                  # remote title, used by the adoption rule (P4)

# manual_export.py
class ManualExportPublisher(BlogPublisher):
    key = "manual_export"
    def capabilities(self) -> PublisherCapabilities: ...
    async def validate(self, payload: PublishPayload) -> list[Issue]: ...
    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult: ...
    async def find_existing(self, payload: PublishPayload) -> RemotePost | None: ...
```

**Behaviour rules**
1. `capabilities()` returns `PublisherCapabilities(network=False, supports_update=False, supports_draft=False, seo_fields=True)`.
2. `validate(payload)` returns `renderer.validate_payload(payload)`.
3. `publish(...)` never touches the network or the database, and ignores `as_draft` and `idempotency_key`.
   - Issues found → `PublicationResult(status=PublicationStatus.FAILED, external_id=None, published_url=None, published_at=None, message="validation failed: " + "; ".join(f"{i.field}: {i.message}" for i in issues))`.
   - No issues → `PublicationResult(status=PublicationStatus.EXPORTED, external_id=None, published_url=None, published_at=None, message="export bundle ready")`.
4. `find_existing(payload)` returns `None`.
5. The class subclasses the `BlogPublisher` Protocol explicitly, as `NullPublisher` does.

**Tests to write first** (`tests/publishing/test_pub_manual_export.py`; no database; 6 tests)

Payload helper `make_payload(**overrides)` builds a valid payload: title `"Specialist access"`, slug `"specialist-access"`, html `"<p>Body</p>"`, excerpt `"Short excerpt"`, status `"published"`.

1. `test_manual_export_capabilities`: `key == "manual_export"`; capabilities equal `network=False, supports_update=False, supports_draft=False, seo_fields=True`.
2. `test_manual_export_validate_uses_payload_limits`: `validate(make_payload(title=" "))` equals `[Issue(field="title", message="title is required")]`; `validate(make_payload()) == []`.
3. `test_manual_export_publish_returns_exported_result`: two calls with `idempotency_key="manual_export:x"` return equal results with `status == PublicationStatus.EXPORTED`, `external_id is None`, `published_url is None`, `published_at is None`, `message == "export bundle ready"`.
4. `test_manual_export_publish_invalid_payload_returns_failed`: `make_payload(title="")` → `status == PublicationStatus.FAILED`, `message == "validation failed: title: title is required"`.
5. `test_manual_export_find_existing_is_none`.
6. `test_new_payload_and_remote_post_fields_default_to_none`: `make_payload().external_post_id is None`; `RemotePost(external_id="1", slug="s", status="draft", url=None).title is None`.

**Implementation notes**
None beyond the rules. Adding defaulted fields keeps every Phase 1 `NullPublisher` test valid.

**Verification**
- Red: single-file command, `<file>` = `test_pub_manual_export.py` → `ModuleNotFoundError: No module named 'mdcopilot_blog.publishing.manual_export'`.
- Green: the same command → `6 passed`.
- Then run:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/unit/test_null_publisher.py
  ```
  Expected: `5 passed`.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "ManualExportPublisher: bundle … `APPROVED → EXPORTED → PUBLISHED`" (publisher part).

### PUB-3: Fake MDCopilot blog API (in-process app and container)

**Files**
- Create `backend/fakes/__init__.py` (docstring only).
- Create `backend/fakes/mdcopilot_api/__init__.py` (docstring only).
- Create `backend/fakes/mdcopilot_api/app.py`.
- Create `backend/fakes/mdcopilot_api/smoke.py`.
- Create `backend/tests/publishing/conftest.py` (fake fixtures).
- Extend `backend/tests/publishing/pub_helpers.py`.
- Create `backend/tests/publishing/test_pub_fake_api.py`.

**Interfaces**
- Consumes: `fastapi`, `pydantic`, stdlib only. No `mdcopilot_blog` import.
- Produces (`fakes/mdcopilot_api/app.py`):
```python
FAKE_LOGIN_ID: Final = "+15550100000"            # not a secret: test double credentials
FAKE_PASSWORD: Final = "fake-publisher-password"
API_PREFIX: Final = "/api/v1"
@dataclass
class FakePost:
    id: str; title: str; slug: str; content: str; excerpt: str | None; featured_image: str | None
    status: str; author_id: str; created_at: datetime; updated_at: datetime | None; published_at: datetime | None; seq: int
@dataclass
class RecordedRequest:
    method: str; path: str; query: dict[str, str]; authorization: str | None; cookie: str | None; origin: str | None
    body: dict[str, object] | None = None
class FakeBlogStore:
    posts: dict[str, FakePost]; requests: list[RecordedRequest]; login_count: int; tokens: dict[str, datetime]  # token -> expiry
    def reset(self) -> None
    def by_slug(self, slug: str) -> FakePost | None
    def generate_slug(self, title: str, exclude_id: str | None = None) -> str
    def add_post(self, *, title: str, slug: str, content: str = "<p>seed</p>", excerpt: str | None = None, status: str = "draft") -> FakePost
def create_fake_app(*, login_id: str = FAKE_LOGIN_ID, password: str = FAKE_PASSWORD,
                    environment: Literal["development", "staging", "production"] = "development",
                    cookie_prefix: str = "", admin: bool = True,
                    allowed_origins: Sequence[str] = ("http://localhost:3000",),
                    token_ttl_seconds: int = 900, clock: Callable[[], datetime] = _utcnow) -> FastAPI   # app.state.store: FakeBlogStore
app: FastAPI = create_fake_app()
```
- Produces (`fakes/mdcopilot_api/smoke.py`): `main(argv: Sequence[str] | None = None) -> int`, runnable as `python -m fakes.mdcopilot_api.smoke <api_base_url>`.
- Produces (`tests/publishing/conftest.py`):
  - `FAKE_API_URL = "http://fake-mdcopilot.test/api/v1"`;
  - fixtures `fake_clock -> MutableClock` (starts `datetime(2026, 9, 17, 3, 30, tzinfo=UTC)`), `fake_app -> FastAPI` (`create_fake_app(clock=fake_clock)`), `fake_store -> FakeBlogStore`, `fake_transport -> httpx.ASGITransport`, `fake_http -> AsyncIterator[httpx.AsyncClient]` (`base_url=FAKE_API_URL`).
- Produces (`pub_helpers.py`): `MutableClock` (`__call__() -> datetime`, `advance(seconds: float) -> None`) and `async def login_token(http: httpx.AsyncClient, *, cookie_name: str = "access_token") -> str`. `login_token` posts valid credentials, reads the cookie value from `Set-Cookie`, calls `http.cookies.clear()` and returns the token.

**Behaviour rules** (each mirrors `mdcopilot-backend`, read-only on 2026-09-17: `app/api/v1/endpoints/blogs.py`, `app/schemas/blog.py`, `app/core/error_handlers.py`, `app/core/csrf.py`, `app/core/auth.py`, `app/api/v1/endpoints/auth.py`)

1. **Error body.** Every error is JSON `{"error": <code>, "message": <text>, "status_code": <int>, "timestamp": <ISO>, "path": <request path>}`, plus `"detail"` only when not None.
2. **Validation errors.** A `RequestValidationError` becomes 422 with `error="VALIDATION_ERROR"`, `message="One or more fields failed validation."` and `detail=[{"field": ".".join(loc[1:]), "message": msg, "type": type}]`.
3. **Login.** `POST /api/v1/auth/login`, body `{phone: str, password: str}`.
   - `environment != "development"` → 404 `NOT_FOUND` `"Not Found"`.
   - Wrong phone or password → 401 `AUTHENTICATION_ERROR` `"Invalid credentials"`.
   - Success: `login_count += 1`; a new token is `secrets.token_urlsafe(24)` with expiry `clock() + token_ttl_seconds`. The response is 200 `{"token_type": "Bearer", "user": {"id": "fake-admin", "role": "admin"}}`, never containing the token. It sets three cookies in this order:
     1. `{prefix}refresh_token` (HttpOnly, path `/api/v1/auth`, SameSite lax);
     2. `{prefix}access_token` = token (HttpOnly, path `/api`, Max-Age `token_ttl_seconds`, SameSite lax);
     3. `{prefix}csrf_token` (not HttpOnly, path `/`, SameSite lax).
4. **CSRF middleware** (HTTP middleware; runs before routing).
   - Applies only to POST/PUT/PATCH/DELETE on paths that do not start with `/api/v1/auth/login` or `/__fake__`, and only when the request carries the cookie `{prefix}access_token`.
   - `Origin` (else `Referer`), normalised to `scheme://netloc`, must be in `allowed_origins`. Otherwise 403 `{"error": "CSRF_FORBIDDEN", "code": "csrf_origin_invalid", "message": "Request origin not allowed"}`.
   - Then, if the cookie `{prefix}csrf_token` is present, the `X-CSRF-Token` header must equal it. Otherwise 403 `{"error": "CSRF_FORBIDDEN", "code": "csrf_token_invalid", "message": "CSRF token missing or invalid"}`.
   - Requests with no access cookie (pure bearer) skip both checks.
5. **Admin auth dependency.**
   - The token comes from the cookie `{prefix}access_token` first, else from `Authorization: Bearer <t>`.
   - No token → 401 `AUTHENTICATION_ERROR` `"Not authenticated"`.
   - Unknown token, or `clock() >= expiry` → 401 `"Invalid token"`.
   - `admin=False` → 403 `AUTHORIZATION_ERROR` `"Admin access required"`.
6. **Recording.**
   - The middleware appends a `RecordedRequest` for every request whose path starts with `/api/v1`: method, path, query dict, `Authorization`, `Cookie` and `Origin` header values (or None).
   - It stores the record's index in `request.state.record_index`.
   - POST and PUT blog handlers set `body = model.model_dump(exclude_unset=True)` on that record.
   - The CSRF middleware records before rejecting.
7. **Slug generation.** `generate_slug(title, exclude_id)` mirrors the backend exactly:
   1. NFKD-normalise `title.lower()`, then ASCII-encode ignoring errors;
   2. `re.sub(r"[^\w\s-]", "", s)`, then `re.sub(r"[-\s]+", "-", s)`, then `.strip("-")`;
   3. an empty result becomes `"blog-post"`;
   4. while a post other than `exclude_id` has the slug, try `f"{base}-{counter}"` with `counter` starting at 1.
8. **`POST /api/v1/admin/blogs`** (admin), body model `BlogCreate`.
   - Fields: `title: str (max_length 200)`, `slug: str | None (≤200)`, `content: str`, `excerpt: str | None (≤500)`, `featured_image: str | None (≤500)`, `status: str = "draft"`. Extra keys are ignored.
   - `slug = body.slug or generate_slug(title)`. An existing slug → 400 `VALIDATION_ERROR` `"Blog with slug '<slug>' already exists"`.
   - The new post has `id=str(uuid4())`, `author_id="fake-admin"`, `created_at=clock()`, `updated_at=None`, `seq` = next integer, `published_at=clock()` iff `status == "published"`.
   - Response 200 is the `BlogResponse` JSON: `title, slug, content, excerpt, featured_image, status, id, author_id, author_name ("Fake Admin"), created_at, updated_at, published_at`.
9. **`PUT /api/v1/admin/blogs/{blog_id}`** (admin), body model `BlogUpdate` (all optional, same limits).
   - Unknown id → 404 `NOT_FOUND` `"Blog with ID '<id>' not found"`.
   - `title` set:
     - `slug` None → `slug = generate_slug(title, exclude_id=id)`;
     - otherwise the slug used by another post → 400 `"Blog with slug '<slug>' already exists"`, else the slug is set.
   - `slug` set and `title` None: the same uniqueness check, then the slug is set.
   - `content`, `excerpt` and `featured_image` are set when not None.
   - `status` set: moving to `published` from another status sets `published_at=clock()`; moving from `published` to another status clears it.
   - `updated_at=clock()`. Response 200 `BlogResponse`.
10. **`GET /api/v1/admin/blogs`** (admin), query `skip: int = 0`, `limit: int = 50`, `status_filter: str | None`, `search: str | None`.
    - Posts are ordered by `(created_at, seq)` descending.
    - `status_filter` filters by exact status.
    - `search` matches `title`, `excerpt` or `content` with SQL `ILIKE '%<search>%'` semantics: `%` → any run, `_` → any one character, case-insensitive, `None` fields never match. It never matches `slug`.
    - The result is sliced `[skip:skip+limit]` and returned as a list of `BlogResponse`.
11. **`GET /api/v1/admin/blogs/{blog_id}`** (admin) → `BlogResponse`, or 404 `"Blog with ID '<id>' not found"`.
12. **`GET /api/v1/blogs`** (no auth), query `skip=0`, `limit=20`, `search`: published posts only, ordered by `published_at` descending, same search rule.
13. **`GET /api/v1/blogs/{slug}`** (no auth): the published post with that slug, else 404 `"Blog with slug '<slug>' not found"`.
14. **Inspection endpoints** (not in the real backend, never recorded, no auth): `GET /__fake__/posts` returns every post as `BlogResponse` JSON in `seq` order; `POST /__fake__/reset` clears posts, requests, tokens and `login_count` and returns 204.
15. **Smoke script** `python -m fakes.mdcopilot_api.smoke <base>`. It uses plain `httpx` with timeout 5 s and runs these checks in order:
    1. `GET <base>/blogs`, retried once per second for up to 30 s until it returns 200;
    2. login returns 200 and sets an `access_token` cookie;
    3. a bearer-only `POST <base>/admin/blogs` (cookie jar cleared first) with title `Smoke <hex8>`, slug `smoke-<hex8>`, content `<p>smoke</p>`, status `draft` returns 200;
    4. a POST sent with the access cookie and no Origin returns 403 with `code == "csrf_origin_invalid"`;
    5. `GET <base>/admin/blogs?search=smoke-<hex8>` returns `[]`, and `GET <base>/admin/blogs` contains the created id;
    6. `PUT <base>/admin/blogs/<id>` with `{"title": "Renamed <hex8>"}` returns slug `renamed-<hex8>`.

    It prints `fake-mdcopilot smoke ok (6 checks)` and returns 0. On the first failed check it prints `fake-mdcopilot smoke failed: check <n>: <reason>` and returns 1.

**Tests to write first** (`tests/publishing/test_pub_fake_api.py`; no database; 23 functions, 26 cases)

Every test uses `fake_http` unless it builds its own app with `create_fake_app(...)` wrapped the same way. `hdr(t) = {"Authorization": f"Bearer {t}"}`.

1. `test_login_sets_three_cookies_and_keeps_token_out_of_body`: 200; `r.json() == {"token_type": "Bearer", "user": {"id": "fake-admin", "role": "admin"}}`; the names parsed from `r.headers.get_list("set-cookie")` equal `["refresh_token", "access_token", "csrf_token"]`; the paths are `/api/v1/auth`, `/api` and `/`; `fake_store.login_count == 1`.
2. `test_login_with_wrong_password_is_401`: status 401; `r.json()["error"] == "AUTHENTICATION_ERROR"` and `["message"] == "Invalid credentials"`; `login_count == 0`.
3. `test_login_outside_development_is_404`: `create_fake_app(environment="production")` → 404, `message == "Not Found"`.
4. `test_bearer_only_write_skips_csrf`: `t = await login_token(fake_http)`; POST `/admin/blogs` with `hdr(t)`, body `{"title": "A", "slug": "a", "content": "<p>x</p>"}` → 200, `status == "draft"`.
5. `test_cookie_session_write_without_origin_is_403`: log in without clearing cookies, POST as in 4 → 403, `r.json() == {"error": "CSRF_FORBIDDEN", "code": "csrf_origin_invalid", "message": "Request origin not allowed"}`; `fake_store.posts == {}`.
6. `test_cookie_session_write_with_origin_and_bad_csrf_token_is_403`: cookies kept, header `Origin: http://localhost:3000`, `X-CSRF-Token: wrong` → 403, `code == "csrf_token_invalid"`.
7. `test_admin_routes_require_a_token` (2 cases): no header → 401 `"Not authenticated"`; `Authorization: Bearer bogus` → 401 `"Invalid token"`.
8. `test_expired_token_is_rejected`: login, `fake_clock.advance(900)`, GET `/admin/blogs` with `hdr(t)` → 401 `"Invalid token"`.
9. `test_non_admin_is_403`: `create_fake_app(admin=False)`, login, GET `/admin/blogs` → 403 `"Admin access required"`.
10. `test_create_generates_unique_slug_from_title`: two POSTs with title `"Hello, World! Ünïcode"` and no slug → slugs `"hello-world-unicode"` and `"hello-world-unicode-1"`.
11. `test_create_with_duplicate_slug_is_400`: second POST with slug `"a"` → 400; body has `error == "VALIDATION_ERROR"`, `message == "Blog with slug 'a' already exists"`, `status_code == 400`; one post in the store.
12. `test_create_over_field_limits_is_422` (3 cases: title `"x"*201`, slug `"a"*201`, excerpt `"x"*501`) → 422; `r.json()["detail"][0]["field"]` is `"title"`, `"slug"`, `"excerpt"` respectively; no post stored.
13. `test_create_sets_published_at_only_when_published`: status `published` → `published_at` is not None; `draft` → `published_at is None`.
14. `test_put_title_without_slug_regenerates_slug`: create title `"First"`, slug `"keep-me"`; PUT `{"title": "Second Title"}` → `slug == "second-title"`.
15. `test_put_with_slug_keeps_slug`: PUT `{"title": "Third", "slug": "keep-me"}` → `slug == "keep-me"`, `title == "Third"`.
16. `test_put_with_duplicate_slug_is_400`: posts `a` and `b`; PUT to `b` with `{"slug": "a"}` → 400 `"Blog with slug 'a' already exists"`; `b`'s slug unchanged.
17. `test_put_status_change_sets_and_clears_published_at`: draft → PUT `{"status": "published"}` → `published_at` not None; PUT `{"status": "draft"}` → `published_at is None`.
18. `test_put_unknown_id_is_404`: PUT `/admin/blogs/nope` → 404 `"Blog with ID 'nope' not found"`.
19. `test_admin_search_matches_title_excerpt_content_but_not_slug`: post title `"Alpha"`, slug `"zeta-unique"`, excerpt `"Beta"`, content `"<p>Gamma</p>"`. Searches: `zeta-unique` → `[]`; `alph` → 1 item; `BETA` → 1; `gam` → 1; `al_ha` → 1.
20. `test_admin_list_is_newest_first_in_pages_of_50`: `fake_store.add_post` 51 times (titles `p0`..`p50`), advancing `fake_clock` by 1 s between posts. GET without limit → 50 items, first title `p50`; `skip=50` → 1 item, title `p0`.
21. `test_public_endpoints_show_only_published_posts`: one draft `d`, one published `p`. `GET /blogs` → slugs `["p"]`; `GET /blogs/d` → 404 `"Blog with slug 'd' not found"`; `GET /blogs/p` → 200.
22. `test_requests_are_recorded_with_auth_and_cookie_headers`: bearer POST → last record has `method == "POST"`, `path == "/api/v1/admin/blogs"`, `authorization == f"Bearer {t}"`, `cookie is None`, `origin is None`, `body == {"title": "A", "slug": "a", "content": "<p>x</p>"}`.
23. `test_inspection_endpoints_list_and_reset`: after one create, `GET /__fake__/posts` → 1 item; `POST /__fake__/reset` → 204; posts, requests and `login_count` all empty or 0.

**Implementation notes** (verified in `python:3.12-slim-trixie` with fastapi 0.141.1 and httpx 0.28.1)
- `Response.set_cookie` calls in this order produce `Set-Cookie` headers in the same order:
```python
response.set_cookie(f"{prefix}refresh_token", refresh, httponly=True, path="/api/v1/auth", samesite="lax")
response.set_cookie(f"{prefix}access_token", token, httponly=True, path="/api", max_age=ttl, samesite="lax")
response.set_cookie(f"{prefix}csrf_token", csrf, httponly=False, path="/", samesite="lax")
```
- `httpx.AsyncClient` stores these cookies and sends the path-`/api` access cookie on later `/api/v1/...` requests until `client.cookies.clear()` is called. Test 5 relies on this.
- Slug generation copied from the backend:
```python
slug = unicodedata.normalize("NFKD", title.lower()).encode("ascii", "ignore").decode("ascii")
slug = re.sub(r"[^\w\s-]", "", slug); slug = re.sub(r"[-\s]+", "-", slug).strip("-") or "blog-post"
```

**Verification**
- Red: single-file command, `<file>` = `test_pub_fake_api.py` → `ModuleNotFoundError: No module named 'fakes'`.
- Green: the same command → `26 passed`.
- Container smoke (own container name; nothing of the owner's stack is recreated or stopped):
  ```bash
  docker compose --profile fakes run -d --rm --no-deps --name p2p-pub-fake fake-mdcopilot
  docker compose run --rm --no-deps -e PYTHONDONTWRITEBYTECODE=1 tools python -m fakes.mdcopilot_api.smoke http://p2p-pub-fake:8000/api/v1
  docker stop p2p-pub-fake
  docker ps -a --filter name=p2p-pub-fake --format '{{.Names}}'
  ```
  Expected: the second command prints `fake-mdcopilot smoke ok (6 checks)` and exits 0; the last command prints nothing.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "Fake MDCopilot API container mirroring real behaviour (search ignores slug, PUT without slug regenerates it, duplicate slug rejected)": in-process tests and the container smoke.

### PUB-4: MDCopilotApiPublisher

**Files**
- Create `backend/src/mdcopilot_blog/publishing/mdcopilot_api.py`.
- Extend `backend/tests/publishing/conftest.py` and `pub_helpers.py`.
- Create `backend/tests/publishing/test_pub_mdcopilot_api.py`.

**Interfaces**
- Consumes:
  - `Settings` (`publisher_api_url`, `publisher_login_path`, `publisher_login_id`, `publisher_password`, `publisher_public_url`, `publisher_timeout_seconds`, `app_version`);
  - `renderer.validate_payload`;
  - `publishing.base` models;
  - `httpx` 0.28.1;
  - `http.cookies.SimpleCookie`.
- Produces:
```python
FIND_EXISTING_PAGE_SIZE = 50
FIND_EXISTING_MAX_PAGES = 20
class PublisherRequestError(RuntimeError): ...            # message never contains a token or password
class MDCopilotApiPublisher(BlogPublisher):
    key = "mdcopilot_api"
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], datetime] = _utcnow) -> None: ...
    def capabilities(self) -> PublisherCapabilities: ...   # network=True, supports_update=True, supports_draft=True, seo_fields=False
    async def validate(self, payload: PublishPayload) -> list[Issue]: ...
    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult: ...
    async def find_existing(self, payload: PublishPayload) -> RemotePost | None: ...   # raises PublisherRequestError
```
- Test support:
  - conftest fixture `api_publisher_settings(settings) -> Settings`: `settings.model_copy(update={"publisher_api_url": FAKE_API_URL, "publisher_login_id": FAKE_LOGIN_ID, "publisher_password": SecretStr(FAKE_PASSWORD), "publisher_public_url": "http://localhost:3000", "publisher_timeout_seconds": 5.0, "publisher_login_path": "/auth/login"})`.
  - `pub_helpers.TimeoutAfterCreate(inner: httpx.AsyncBaseTransport, *, fail_lookups: bool = False)`: after forwarding the first `POST …/admin/blogs` and reading its response, it raises `httpx.ReadTimeout("simulated timeout after create", request=request)`. With `fail_lookups=True`, every later GET raises `httpx.ConnectError("simulated lookup failure", request=request)` without forwarding.
  - `pub_helpers.HideLookups(inner, *, hide_count: int)`: the first `hide_count` GET requests get synthetic responses without being forwarded — `404 {"error": "NOT_FOUND", "message": "hidden"}` for `/blogs/{slug}` and `200 []` for `/admin/blogs`.
  - `pub_helpers.RecordingTransport(handler)`: an `httpx.MockTransport` wrapper that appends every request to `.calls`.
  - `pub_helpers.make_payload(**overrides) -> PublishPayload`: title `"Specialist access in practice"`, slug `"specialist-access-in-practice"`, html `"<p>Body</p>"`, excerpt `"Short excerpt"`, status `"published"`.

**Behaviour rules**
1. **Client.** Each public call opens `httpx.AsyncClient(base_url=settings.publisher_api_url, transport=self._transport, timeout=httpx.Timeout(settings.publisher_timeout_seconds), follow_redirects=False, headers={"Accept": "application/json", "User-Agent": f"mdcopilot-blog/{settings.app_version} publisher"})`. Request paths are relative to the base (`/auth/login`, `/admin/blogs`, `/blogs/{slug}`). The client never sends `Origin`.
2. **Credentials.** If `publisher_login_id` or `publisher_password` is None or blank, `publish` returns `FAILED` with message `publisher credentials are not configured (BLOG_PUBLISHER_LOGIN_ID and BLOG_PUBLISHER_PASSWORD)` and sends no request. `find_existing` raises `PublisherRequestError` with the same message before sending any request.
3. **Validation first.** `publish` calls `validate(payload)`. Issues → `FAILED`, message `validation failed: <field>: <message>; …`, and no request (not even login).
4. **Login** (lazy, cached per instance in `self._token`).
   - `POST {publisher_login_path}` with JSON `{"phone": login_id, "password": password}`.
   - 404 → error `login endpoint not found: the MDCopilot backend must run with ENVIRONMENT=development`.
   - Any other non-200 → `login failed: HTTP <status>`.
   - A transport error → `login failed: <ExceptionClassName>`.
   - On 200, parse each `response.headers.get_list("set-cookie")` value with `SimpleCookie().load(value)`. The token is the value of the first morsel whose key equals `access_token` or ends with `_access_token`. None found → `login succeeded but no access-token cookie was returned`.
   - After reading the token, call `client.cookies.clear()`, so every later request is bearer-only and the backend's CSRF middleware is skipped.
5. **Authenticated requests** send `Authorization: Bearer <token>`. On 401, clear `self._token`, log in again and resend once. A second 401 → error `authentication failed after re-login: HTTP 401 for <METHOD> <path>`.
6. **Errors.**
   - Any other unexpected status → `MDCopilot returned HTTP <status> for <METHOD> <path>`, plus `: <message>` when the JSON body has a string `message`.
   - A transport error on a GET or PUT → `request failed: <ExceptionClassName> for <METHOD> <path>`.
   - In messages, `<path>` is the relative path with the literal id or slug, for example `/admin/blogs/abc`.
7. **Remote rows** parse with a private model (`extra="ignore"`): `id: str`, `title: str`, `slug: str`, `status: str`, `published_at: datetime | None = None`.
   - A remote row maps to `RemotePost(external_id=id, slug=slug, status=status, url=<public url when status == "published" else None>, title=title)`.
   - Public URL = `f"{settings.publisher_public_url.rstrip('/')}/blog/{slug}"`.
8. **`find_existing(payload)`** (exact slug match on our side).
   1. `GET /blogs/{urllib.parse.quote(slug, safe='')}` without Authorization. 200 whose `slug == payload.slug` → return it. 404 → continue. Any other status → error (rule 6).
   2. Page `GET /admin/blogs` with `skip=page*50` and `limit=50`, `page` from 0 up to 19, first with `search=payload.title`. Return the first row whose `slug == payload.slug`. Stop the pass when a page has fewer than 50 rows.
   3. Repeat step 2 without `search`.
   4. Return `None`.
9. **Body** for create and update: `{"title": payload.title, "slug": payload.slug, "content": payload.html, "excerpt": payload.excerpt, "status": "draft" if as_draft else "published"}`. `slug` is always sent; `featured_image` is never sent.
10. **`publish` algorithm** (after rules 2–3; `idempotency_key` is not sent to MDCopilot):
    1. If `payload.external_post_id` is set: `PUT /admin/blogs/{id}`. 200 → success. 404 → forget the id and continue at step 2. Other statuses → failure.
    2. `existing = find_existing(payload)`.
       - Found with `existing.title == payload.title` → `PUT /admin/blogs/{existing.external_id}` → success.
       - Found with a different title → failure `slug '<slug>' is already used by a different post (title '<remote title>')`, and no write.
    3. Not found → `POST /admin/blogs`.
       - 200 → success.
       - 400 whose `message` contains `already exists`: run `find_existing` again and apply step 2's rule. Still not found → failure `MDCopilot reports slug '<slug>' already exists but no post with that slug was found`.
       - `httpx.TimeoutException` or `httpx.TransportError`: run `find_existing` again. If that raises, the failure is `create timed out (<Class>) and reconciliation failed: <message>`. Found → step 2's rule. Not found → failure `create timed out (<Class>) and no post with slug '<slug>' was found`.
    4. Success → `PublicationResult(status=PUBLISHED, external_id=remote.id, published_url=<public url of remote.slug when remote.status == "published", else None>, published_at=remote.published_at or clock(), message=None)`.
    5. Failure → `PublicationResult(status=FAILED, external_id=<id known at the time of failure or None>, published_url=None, published_at=None, message=<message>)`.

    `publish` never raises for HTTP or transport errors. It lets only programming errors propagate.
11. The password and the token never appear in any message, log call or exception.

**Tests to write first** (`tests/publishing/test_pub_mdcopilot_api.py`; no database; 22 tests)

Unless stated, the publisher is `MDCopilotApiPublisher(api_publisher_settings, transport=fake_transport)`. "POSTs" and "PUTs" count `fake_store.requests` entries with that method and path `/api/v1/admin/blogs` (POST) or starting with `/api/v1/admin/blogs/` (PUT).

1. `test_capabilities`: `key == "mdcopilot_api"`; `network=True, supports_update=True, supports_draft=True, seo_fields=False`.
2. `test_validate_reports_field_limits`: `make_payload(slug="Bad Slug")` → one `slug` pattern issue.
3. `test_publish_creates_published_post_with_public_url`: `publish(make_payload(), idempotency_key="k", as_draft=False)`.
   - Result: `status == PUBLISHED`; `external_id == post.id` for the single store post; `published_url == "http://localhost:3000/blog/specialist-access-in-practice"`; `published_at == post.published_at`.
   - Store post: `content == "<p>Body</p>"`, `excerpt == "Short excerpt"`, `status == "published"`.
4. `test_publish_as_draft_creates_draft_without_public_url`: `as_draft=True` → store `status == "draft"`; `result.published_url is None`; `result.published_at is not None`.
5. `test_requests_use_bearer_token_and_never_cookies_or_origin`: after test 3's flow, every record except the login has `cookie is None` and `origin is None`. Every `/api/v1/admin/...` record has an `authorization` starting with `"Bearer "`. The `/api/v1/blogs/...` public lookup record has `authorization is None`.
6. `test_update_always_sends_slug_and_keeps_url`: publish, then publish again with `make_payload(external_post_id=<id>, title="Specialist access in practice, revised")` on a new instance. The last PUT record body contains `"slug": "specialist-access-in-practice"`, the store post slug is unchanged, and there is still 1 post.
7. `test_second_publish_adopts_existing_published_post`: two separate instances publish `make_payload()` with `as_draft=False` → 1 post; POSTs == 1; PUTs == 1; both results have the same `external_id`.
8. `test_second_publish_adopts_existing_draft_post`: the same with `as_draft=True` → 1 post, POSTs == 1, and an admin-list GET record with `query["search"] == "Specialist access in practice"` exists.
9. `test_timeout_after_create_reconciles_to_one_post`: transport `TimeoutAfterCreate(fake_transport)` → `status == PUBLISHED`; `external_id` equals the single post's id; POSTs == 1; PUTs == 1.
10. `test_retry_after_unreconciled_timeout_yields_one_post`:
    - First instance with `TimeoutAfterCreate(fake_transport, fail_lookups=True)` → `status == FAILED`; message starts with `"create timed out (ReadTimeout) and reconciliation failed: request failed: ConnectError for GET /blogs/specialist-access-in-practice"`.
    - Second instance with `fake_transport` → `PUBLISHED`.
    - The store has 1 post and POSTs == 1.
11. `test_foreign_post_with_same_slug_is_never_overwritten`: `fake_store.add_post(title="Human post", slug="specialist-access-in-practice", status="published")`. Publish → `FAILED` with message `"slug 'specialist-access-in-practice' is already used by a different post (title 'Human post')"`; the post title is still `"Human post"`; PUTs == 0; POSTs == 0.
12. `test_stale_external_id_falls_back_to_reconcile_and_create`: `make_payload(external_post_id="missing")` → `PUBLISHED`; the store has 1 post and its id != `"missing"`; one PUT record with path `/api/v1/admin/blogs/missing` exists.
13. `test_expired_token_triggers_one_relogin`: one instance publishes `make_payload(slug="one")`, then `fake_clock.advance(901)`, then publishes `make_payload(title="Second post", slug="two")` → both `PUBLISHED`; `fake_store.login_count == 2`.
14. `test_login_failure_message_has_no_secret`: settings with `publisher_password=SecretStr("wrong-password")` → `FAILED`, `message == "login failed: HTTP 401"`; `"wrong-password" not in result.message`; no record with a path starting `/api/v1/admin`.
15. `test_login_endpoint_missing_explains_development_only`: `create_fake_app(environment="production")` transport → `message == "login endpoint not found: the MDCopilot backend must run with ENVIRONMENT=development"`.
16. `test_missing_credentials_send_nothing`: `publisher_login_id=None`, transport `RecordingTransport(handler raising AssertionError)` → `FAILED` with the rule-2 message; `transport.calls == []`. `find_existing` raises `PublisherRequestError` with the same message; `calls == []`.
17. `test_prefixed_access_token_cookie_is_accepted`: `create_fake_app(cookie_prefix="mdcopilot_demo_")` → `PUBLISHED`.
18. `test_server_error_returns_failed_result`: `RecordingTransport` handler:
    - `POST /api/v1/auth/login` → 200 with header `set-cookie: access_token=tok; Path=/api`;
    - `GET /api/v1/blogs/…` → 404 `{"message": "x"}`;
    - `GET /api/v1/admin/blogs` → 200 `[]`;
    - `POST /api/v1/admin/blogs` → 503 `{"message": "maintenance"}`.

    Result `FAILED`, `message == "MDCopilot returned HTTP 503 for POST /admin/blogs: maintenance"`.
19. `test_find_existing_pages_through_admin_list`: `add_post` the target (title `"Old title"`, slug `"specialist-access-in-practice"`, draft) first, then 55 other drafts (advancing `fake_clock` 1 s each). `find_existing(make_payload())` returns a `RemotePost` with `slug` equal, `title == "Old title"`, `url is None`. The records include an unfiltered admin GET with `query["skip"] == "50"`.
20. `test_find_existing_uses_public_lookup_for_published_posts`: a published post with the payload slug → found; `url == "http://localhost:3000/blog/specialist-access-in-practice"`; no record with path `/api/v1/admin/blogs` exists and `login_count == 0`.
21. `test_invalid_payload_sends_nothing`: `make_payload(title="")` → `FAILED`, `message == "validation failed: title: title is required"`; `fake_store.requests == []`.
22. `test_duplicate_slug_error_adopts_matching_post`: `fake_store.add_post(title="Specialist access in practice", slug="specialist-access-in-practice", status="draft")`; transport `HideLookups(fake_transport, hide_count=3)` → `PUBLISHED`; POSTs == 1 (rejected with 400); PUTs == 1; 1 post; the result `external_id` equals that post's id.

**Implementation notes** (verified 2026-09-17 in `python:3.12-slim-trixie`, httpx 0.28.1)
- With `base_url="http://fake:8000/api/v1"`, `client.post("/auth/login")` requests `http://fake:8000/api/v1/auth/login`.
- The client cookie jar keeps `refresh_token`, `access_token` and `csrf_token` from the login response and sends the path-`/api` ones on later requests until cleared:
```python
for raw in response.headers.get_list("set-cookie"):
    jar = SimpleCookie(); jar.load(raw)
    for name, morsel in jar.items():
        if name == "access_token" or name.endswith("_access_token"):
            token = morsel.value
client.cookies.clear()   # bearer-only from here on
```
- `SimpleCookie.load("mdcopilot_demo_access_token=tok.en; HttpOnly; Path=/api")` yields `("mdcopilot_demo_access_token", "tok.en")`.
- A wrapper transport can forward, read, then time out:
```python
class TimeoutAfterCreate(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self.inner.handle_async_request(request)
        if request.method == "POST" and request.url.path.endswith("/admin/blogs") and not self.fired:
            self.fired = True
            await response.aread()
            raise httpx.ReadTimeout("simulated timeout after create", request=request)
        return response
```
- `httpx.ReadTimeout` is both a `TimeoutException` and a `TransportError`.

**Verification**
- Red: single-file command, `<file>` = `test_pub_mdcopilot_api.py` → `ModuleNotFoundError: No module named 'mdcopilot_blog.publishing.mdcopilot_api'`.
- Green: the same command → `22 passed`.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "MDCopilotApiPublisher: credential login, create/update always sending slug, draft/published, field limits, `find_existing`, `BLOG_PUBLISHER_PUBLIC_URL` URL" (publisher part).
- §10.6 "Publish twice, or retry after timeout-after-create → exactly one post" (publisher level).

### PUB-5: Publisher factory, targets, idempotency keys, network gate

**Files**
- Create `backend/src/mdcopilot_blog/publishing/factory.py`.
- Create `backend/tests/publishing/test_pub_factory.py`.
- Extend `backend/tests/publishing/conftest.py` with fixture `patch_publisher_transport`.

**Interfaces**
- Consumes: `ManualExportPublisher`, `MDCopilotApiPublisher`, `NullPublisher`, `PublisherKey`, `EffectiveConfig`, `PublishingDisabled`, `Settings`.
- Produces:
```python
def build_publisher(settings: Settings, key: PublisherKey | str, *, transport: httpx.AsyncBaseTransport | None = None) -> BlogPublisher
def publisher_target(settings: Settings, key: PublisherKey | str) -> str
def idempotency_key(key: PublisherKey | str, version_id: uuid.UUID) -> str
def network_publishing_active(settings: Settings, config: EffectiveConfig) -> bool
def ensure_network_publishing(settings: Settings, config: EffectiveConfig) -> None   # raises PublishingDisabled
```
- Conftest fixture: `patch_publisher_transport(monkeypatch) -> Callable[[httpx.AsyncBaseTransport], None]`. Calling it replaces `factory.build_publisher` with a wrapper that calls the original with `transport=<given transport>` whenever the caller passed none. Services and seams call `factory.build_publisher` through the module attribute, so the patch reaches them.

**Behaviour rules**
1. `build_publisher` normalises `key` to `str(key)`:
   - `"manual_export"` → `ManualExportPublisher()`;
   - `"mdcopilot_api"` → `MDCopilotApiPublisher(settings, transport=transport)`;
   - `"null"` → `NullPublisher()`;
   - anything else → `ValueError(f"unknown publisher {key!r}")`.
   Construction sends no request.
2. `publisher_target`:
   - `manual_export` → `"manual"`;
   - `null` → `"null"`;
   - `mdcopilot_api` → with `parts = urllib.parse.urlsplit(settings.publisher_api_url)`, the value `f"{parts.scheme.lower()}://{(parts.hostname or '').lower()}"` plus `f":{parts.port}"` when `parts.port` is not None. User info and path are dropped.
   - Unknown keys raise the rule-1 `ValueError`.
3. `idempotency_key(key, version_id)` = `f"{key}:{version_id}"` (50 characters for `manual_export` and `mdcopilot_api`).
4. `network_publishing_active(settings, config)` = `settings.publishing_enabled and build_publisher(settings, config.publisher).capabilities().network`.
5. `ensure_network_publishing`:
   - `settings.publishing_enabled` false → `PublishingDisabled("publishing is disabled (BLOG_PUBLISHING_ENABLED=false)")`;
   - else a non-network publisher → `PublishingDisabled(f"the active publisher {config.publisher} does not publish over the network; use export")`;
   - otherwise returns None.

**Tests to write first** (`tests/publishing/test_pub_factory.py`; the tests using `effective_config` touch the database; 6 functions, 17 cases)
1. `test_build_publisher_returns_the_named_publisher` (3 cases): `"manual_export"` → `isinstance(p, ManualExportPublisher)`; `"mdcopilot_api"` → `MDCopilotApiPublisher`; `PublisherKey.NULL` → `NullPublisher`.
2. `test_build_publisher_rejects_unknown_key`: `pytest.raises(ValueError, match="unknown publisher 'ghost'")`.
3. `test_publisher_target` (4 cases):
   - `manual_export` → `"manual"`;
   - `null` → `"null"`;
   - `mdcopilot_api` with `publisher_api_url="http://host.docker.internal:8000/api/v1"` → `"http://host.docker.internal:8000"`;
   - `mdcopilot_api` with `"https://user:pw@API.Example.com/api/v1"` → `"https://api.example.com"`.
4. `test_idempotency_key_format`: `v = uuid.UUID("0199a2b4-0000-7000-8000-000000000001")`; `idempotency_key("manual_export", v) == "manual_export:0199a2b4-0000-7000-8000-000000000001"` with length 50; `idempotency_key(PublisherKey.MDCOPILOT_API, v)` has length 50.
5. `test_network_publishing_active` (5 cases; `config = effective_config.model_copy(update={"publisher": key})`, `s = settings.model_copy(update={"publishing_enabled": enabled})`):
   - `(False, "manual_export")` → False
   - `(False, "mdcopilot_api")` → False
   - `(True, "manual_export")` → False
   - `(True, "null")` → False
   - `(True, "mdcopilot_api")` → True
6. `test_ensure_network_publishing_messages` (3 cases):
   - `(False, "mdcopilot_api")` raises `PublishingDisabled`, `str(exc) == "publishing is disabled (BLOG_PUBLISHING_ENABLED=false)"`;
   - `(True, "manual_export")` → `"the active publisher manual_export does not publish over the network; use export"`;
   - `(True, "mdcopilot_api")` → returns None.

**Implementation notes**
- `PublishingDisabled(message)` keeps the message in `args` (CONTRACT §5.3), so `str(exc)` is the message the global handler uses as `detail`.

**Verification**
- Red: single-file command, `<file>` = `test_pub_factory.py` → `ModuleNotFoundError: No module named 'mdcopilot_blog.publishing.factory'`.
- Green: the same command → `17 passed`.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "Default settings: … every network publish path 409 and nothing sent" (gate part).
- CONTRACT §3.1 `blog_publications.target` and `idempotency_key` formats.

### PUB-6: API schemas, version rendering service and preview route

**Files**
- Modify (stub by FOUND) `backend/src/mdcopilot_blog/api/schemas_publishing.py`: all §4.7 models.
- Modify `backend/src/mdcopilot_blog/services/publications.py`: rendering helpers and preview.
- Modify (stub by FOUND) `backend/src/mdcopilot_blog/api/routers/publishing.py`: the preview route only.
- Extend `backend/tests/publishing/pub_helpers.py`.
- Create `backend/tests/publishing/test_pub_api_preview.py`.

**Interfaces**
- Consumes:
  - ORM `Article`, `ArticleVersion`, `VersionSeo`, `ArticleSource`, `LedgerSource`;
  - `load_brand_profile`, `renderer.*`, `ProblemError`, `ApiModel`;
  - `TitleOptions`, `SEOMetadata`, `SocialCopy`, `BlogSource`;
  - `api.deps.SessionDep`, `require_permission`.
- Produces (`api/schemas_publishing.py`, all `ApiModel`; field names and nullability exactly as CONTRACT §4.7):
```python
class IssueOut(ApiModel): field: str; message: str
class PreviewOut(ApiModel): version_id: uuid.UUID; html: str; issues: list[IssueOut]
class ExportBundleOut(ApiModel):
    publication_id: uuid.UUID; article_id: uuid.UUID; version_id: uuid.UUID
    title: str = Field(max_length=200); slug: str = Field(max_length=200); excerpt: str = Field(max_length=500)
    html: str; text: str; seo: SEOMetadata; social: SocialCopy | None; tags: list[str]; category: str
    references: list[BlogSource]; disclosure: str; status: ArticleStatus
class ConfirmPublishedRequest(ApiModel): url: str = Field(max_length=2000)   # + validator (rule 6)
class PublishRequest(ApiModel): as_draft: bool | None = None
class ScheduleRequest(ApiModel): at: AwareDatetime
class PublicationOut(ApiModel):
    id: uuid.UUID; version_id: uuid.UUID; publisher: PublisherKey; target: str; status: PublicationStatus
    external_post_id: str | None; published_url: str | None; published_at: datetime | None; as_draft: bool
    attempts: int; last_error: dict[str, Any] | None; created_at: datetime; updated_at: datetime
```
- Produces (`services/publications.py`):
```python
ARTICLE_ENTITY = "blog_article"
@dataclass(frozen=True)
class RenderedArticle:
    article_id: uuid.UUID; version_id: uuid.UUID; title: str; slug: str | None; excerpt: str
    html: str; text: str; seo: SEOMetadata | None; social: SocialCopy | None; tags: list[str]; category: str
    references: list[BlogSource]; disclosure: str; issues: list[Issue]
    def to_payload(self, *, as_draft: bool, external_post_id: str | None = None) -> PublishPayload: ...
    def payload_hash(self) -> str: ...
async def get_article(db: AsyncSession, article_id: uuid.UUID, *, for_update: bool = False) -> Article: ...
async def render_version(db: AsyncSession, *, article: Article, version_id: uuid.UUID,
                         references_override: Sequence[BlogSource] | None = None,
                         disclosure_override: str | None = None) -> RenderedArticle: ...
async def preview_article(db: AsyncSession, *, article_id: uuid.UUID, version_id: uuid.UUID | None) -> PreviewOut: ...
```
- Produces (router): `GET /articles/{article_id}/preview`, permission `blog.view`, query `versionId` (alias), response `PreviewOut`.
- Produces (`pub_helpers.py`): `async def add_version_copy(db: AsyncSession, ids: ArticleGraphIds, *, content_markdown: str | None = None, set_current: bool = True, set_approved: bool = False) -> uuid.UUID`. It inserts a new `ArticleVersion`:
  - copies every content column of `ids.version_id`, with `version_no` = max + 1, `parent_version_id=ids.version_id`, `change_kind="human_edit"`, `created_by_kind="human"`, `dbos_workflow_id=None`;
  - uses `content_markdown` when given;
  - copies the version's `ArticleSource` rows and newest `VersionSeo` row;
  - updates the article's `current_version_id` and/or `approved_version_id` as requested;
  - flushes and returns the new version id.

**Behaviour rules**
1. `get_article`: `select(Article).where(Article.id == article_id)`, with `.with_for_update()` when `for_update`. Missing → `ProblemError(404, "Article not found", f"no article with id {article_id}")`.
2. `render_version`:
   1. `version = await db.get(ArticleVersion, version_id)`. None or `version.article_id != article.id` → `ProblemError(404, "Version not found", f"no version {version_id} for article {article.id}")`.
   2. `seo_row` = the newest `VersionSeo` for the version, ordered `created_at desc, id desc`, limit 1. `seo = SEOMetadata.model_validate(seo_row.seo)` and `social = SocialCopy.model_validate(seo_row.social)` when `seo_row.social` is not None; both None when there is no row.
   3. `references`: `references_override` when given. Otherwise `ArticleSource` rows of the version joined to `LedgerSource`, each mapped to `BlogSource(marker=row.marker, source_id=str(source.id), title=source.title, url=source.canonical_url, publisher=source.publisher, published_at=source.published_at)` and sorted by `int(marker[1:])` (markers that do not match `^S[1-9][0-9]*$` sort last, by marker text).
   4. `disclosure`: `disclosure_override` when given. Otherwise `(await load_brand_profile(db)).ai_disclosure`, or `""` when `load_brand_profile` raises `LookupError`.
   5. `title`: `article.title` when non-blank, else `TitleOptions.model_validate(version.title_options).operational`.
   6. `slug`: `article.slug` when not None, else `seo.slug` when `seo` is not None, else None.
   7. `excerpt = version.excerpt`, `tags = list(article.tags)`, `category = article.category`.
   8. `html = render_article_html(content_markdown=version.content_markdown, pull_quote=version.pull_quote, references=references, disclosure=disclosure)`, and `text = html_to_text(html)`.
   9. `issues = validate_publishable(PublishableCheck(title, slug, excerpt, html, version.content_markdown, seo, references, disclosure))`.
3. `RenderedArticle.to_payload(*, as_draft, external_post_id=None)`: `slug is None` → `ValueError("cannot build a payload without a slug")`. Otherwise `PublishPayload(article_id, version_id, title, slug, html, excerpt, status="draft" if as_draft else "published", seo=seo.model_dump(mode="json") if seo else {}, external_post_id=external_post_id)`.
4. `RenderedArticle.payload_hash()` = `compute_payload_hash(html=html, title=title, slug=slug or "", excerpt=excerpt)`.
5. `preview_article`:
   - `article = get_article(db, article_id)`;
   - `vid = version_id or article.current_version_id`; `vid` None → `ProblemError(404, "Version not found", "article has no current version")`;
   - returns `PreviewOut(version_id=vid, html=r.html, issues=[IssueOut(field=i.field, message=i.message) for i in r.issues])`.
   - Read only; no audit.
6. `ConfirmPublishedRequest.url` validator (after `.strip()`):
   - `urlsplit(url)` must have scheme `http` or `https` and a non-empty `netloc` whose `hostname` is not None;
   - the URL must contain no whitespace or control characters (`any(c.isspace() or ord(c) < 32 for c in url)` is false);
   - any failure → `ValueError("url must be an absolute http or https URL")`, which FastAPI turns into 422 `Request validation failed`.
   - The stored value is the stripped string.
7. `ScheduleRequest.at: AwareDatetime`: a naive datetime is rejected by pydantic → 422 `Request validation failed`.
8. The preview route depends on `require_permission(Permission.VIEW)`.

**Tests to write first** (`tests/publishing/test_pub_api_preview.py`; database; 9 tests)

Setup for API tests: fixtures `seeded_db` and `login_as`; `ids = await make_article_graph(seeded_db, status=ArticleStatus.READY_FOR_REVIEW)`. The viewer client comes from `login_as(Role.VIEWER)`. `URL = f"/api/blog-agent/articles/{ids.article_id}/preview"`. `DISCLOSURE = (await load_brand_profile(seeded_db)).ai_disclosure`.

1. `test_preview_renders_current_version`: GET → 200.
   - `body["versionId"] == str(ids.version_id)`;
   - `body["issues"] == []`;
   - `body["html"].endswith(f"<p><em>{DISCLOSURE}</em></p>")`;
   - `"<h2>References</h2>" in body["html"]`;
   - `set(parse_markup(body["html"]).tags) <= ALLOWED_TAGS`.
2. `test_preview_reports_issues_without_seo`: graph with `with_seo=False` → 200, `body["issues"] == [{"field": "slug", "message": "slug is required"}, {"field": "seo", "message": "SEO metadata is missing for this version"}]`.
3. `test_preview_of_explicit_version_id`: `v2 = await add_version_copy(seeded_db, ids, set_current=True)`; GET `?versionId=<ids.version_id>` → 200 with `versionId == str(ids.version_id)`; GET without the query → `versionId == str(v2)`.
4. `test_preview_unknown_article_is_404`: random uuid → 404, `title == "Article not found"`.
5. `test_preview_version_of_another_article_is_404`: `other = await make_article_graph(seeded_db, with_seo=False)`; GET `?versionId=<other.version_id>` → 404 `"Version not found"`.
6. `test_preview_article_without_current_version_is_404`: set `article.current_version_id = None` and flush → 404 `"Version not found"`, `detail == "article has no current version"`.
7. `test_preview_never_renders_raw_html_from_content`: `await add_version_copy(seeded_db, ids, content_markdown=XSS_MARKDOWN)`; GET → 200. With `m = parse_markup(html)`:
   - `set(m.tags) <= ALLOWED_TAGS`;
   - no attribute name starts with `"on"`;
   - every `href`/`src` value starts with `http://` or `https://`;
   - `"<script" not in html.lower()` and `"<iframe" not in html.lower()`.
8. `test_render_version_uses_head_title_canonical_urls_and_markers` (service-level, `seeded_db`): `a = await seeded_db.get(Article, ids.article_id)`; `r = await render_version(seeded_db, article=a, version_id=ids.version_id)`.
   - `r.title == (a.title or TitleOptions.model_validate(version.title_options).operational)`;
   - `[x.marker for x in r.references] == ["S1", "S2", "S3", "S4", "S5"]`;
   - `r.references[0].url == (await seeded_db.get(LedgerSource, ids.source_ids[0])).canonical_url`;
   - `r.slug == a.slug`, `r.seo is not None`, `r.text == html_to_text(r.html)`, `r.issues == []`;
   - `r.to_payload(as_draft=True).status == "draft"`.
9. `test_render_version_uses_overrides`: `references_override=[r.references[0]]`, `disclosure_override="Override."` → `html.endswith("<p><em>Override.</em></p>")`, `references == [r.references[0]]`, and `html.count("<li>") == 1`.

**Implementation notes**
- `pydantic.AwareDatetime` rejects naive datetimes during validation, so no custom validator is needed for rule 7.
- Query alias: `version_id: Annotated[uuid.UUID | None, Query(alias="versionId")] = None`.
- The router module must import cleanly at every save: add the route only after `preview_article` exists.

**Verification**
- Red: single-file command, `<file>` = `test_pub_api_preview.py` → `ImportError` for `preview_article`, or 404/405 on the route.
- Green: the same command → `9 passed`.
- `tests/foundation/test_found_imports.py` → all passed.
- `tests/api/test_rbac_routes.py`:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/api/test_rbac_routes.py
  ```
  Expected: all passed.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.5 "Preview never renders raw model HTML (XSS fixture)": the server renderer through the API.
- §4.7 `GET /preview`.

### PUB-7: Export, confirm-published and publications list

**Files**
- Modify `backend/src/mdcopilot_blog/services/publications.py`.
- Modify `backend/src/mdcopilot_blog/api/routers/publishing.py`: routes `export`, `confirm-published`, `publications`.
- Create `backend/tests/publishing/test_pub_api_export.py`.

**Interfaces**
- Consumes:
  - `render_version`, `get_article`, `factory.publisher_target`, `factory.idempotency_key`, `ManualExportPublisher`;
  - `set_article_status`, `require_transition`, `InvalidTransition`, `audit`;
  - ORM `Publication`; `ArticleStateOut`; `Principal`.
- Produces (`services/publications.py`):
```python
@dataclass(frozen=True)
class ExportResult:
    publication_id: uuid.UUID | None; bundle: ExportBundleOut | None; issues: list[Issue]; repeated: bool
async def export_locked(db: AsyncSession, *, article: Article, actor_user_id: uuid.UUID | None,
                        trigger: Literal["api", "schedule"]) -> ExportResult: ...   # caller holds the article row lock; flush only
async def export_article(db: AsyncSession, *, principal: Principal, article_id: uuid.UUID) -> ExportBundleOut: ...
async def confirm_published(db: AsyncSession, *, principal: Principal, article_id: uuid.UUID, url: str, now: datetime) -> ArticleStateOut: ...
async def list_publications(db: AsyncSession, *, article_id: uuid.UUID) -> list[PublicationOut]: ...
```
- Produces (router):
  - `POST /articles/{article_id}/export` (PUBLISH) → `ExportBundleOut`;
  - `POST /articles/{article_id}/confirm-published` (PUBLISH), body `ConfirmPublishedRequest` → `ArticleStateOut`;
  - `GET /articles/{article_id}/publications` (VIEW) → `list[PublicationOut]`.

**Behaviour rules**
1. **`export_locked`** (publisher `"manual_export"`, target `"manual"`, `vid = article.approved_version_id`):
   1. `status = article.status`. If `status` is not APPROVED, SCHEDULED or EXPORTED, or `vid` is None → `raise InvalidTransition(Entity.ARTICLE, status, ArticleStatus.EXPORTED)`.
   2. `row` = `Publication` for `(article.id, "manual_export", "manual")`, `with_for_update()`.
   3. **Repeat.** If `status == EXPORTED` and `row` is not None and `row.version_id == vid` and `row.export_bundle` is not None:
      - `stored = ExportBundleOut.model_validate({**row.export_bundle, "html": "", "status": status})`;
      - `r = await render_version(db, article=article, version_id=vid, references_override=stored.references, disclosure_override=stored.disclosure)`;
      - return `ExportResult(row.id, stored.model_copy(update={"html": r.html, "status": ArticleStatus(status)}), [], True)`.
      No write and no audit.
   4. `r = await render_version(db, article=article, version_id=vid)`. `r.issues` non-empty → `ExportResult(None, None, r.issues, False)` with no write.
   5. `result = await ManualExportPublisher().publish(r.to_payload(as_draft=False), idempotency_key=idempotency_key("manual_export", vid), as_draft=False)`. It is `EXPORTED`, because the issues were empty.
   6. Row write:
      - **No row:** `require_transition(Entity.PUBLICATION, PENDING, EXPORTED)`, then insert `Publication(id=uuid7(), article_id, version_id=vid, publisher="manual_export", target="manual", status="EXPORTED", idempotency_key, payload_hash=r.payload_hash(), as_draft=False, attempts=1, requested_by=actor_user_id)`.
      - **Row exists:** `require_transition(Entity.PUBLICATION, row.status, EXPORTED)` (a CONFIRMED row raises `InvalidTransition` for the publication entity), then set `version_id`, `idempotency_key`, `payload_hash`, `status="EXPORTED"`, `attempts = row.attempts + 1`, `requested_by=actor_user_id`, `last_error=None`.
   7. `bundle = ExportBundleOut(publication_id=row.id, article_id=article.id, version_id=vid, title=r.title, slug=r.slug, excerpt=r.excerpt, html=r.html, text=r.text, seo=r.seo, social=r.social, tags=r.tags, category=r.category, references=r.references, disclosure=r.disclosure, status=ArticleStatus.EXPORTED)`.
   8. `row.export_bundle = bundle.model_dump(mode="json", exclude={"html"})`.
   9. If `status != EXPORTED`: `await set_article_status(db, article_id=article.id, target=ArticleStatus.EXPORTED)`.
   10. `audit(db, actor_user_id=actor_user_id, action="article.export", entity_type=ARTICLE_ENTITY, entity_id=str(article.id), details={"versionId": vid, "publicationId": row.id, "payloadHash": row.payload_hash, "trigger": trigger})`.
   11. Flush; return `ExportResult(row.id, bundle, [], False)`.
2. **`export_article`**:
   - `article = get_article(db, article_id, for_update=True)`, then `res = export_locked(db, article=article, actor_user_id=principal.user_id, trigger="api")`.
   - `res.issues` non-empty → `ProblemError(422, "Publish validation failed", [{"field": i.field, "message": i.message} for i in res.issues])`. Nothing is written; the request session rolls back.
   - Otherwise commit (repeat: commit only releases the lock) and return `res.bundle`.
   - `InvalidTransition` propagates to the global 409 `Invalid state transition`.
3. **`confirm_published`**:
   1. `article = get_article(db, article_id, for_update=True)`.
   2. `article.status != EXPORTED` → `raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.PUBLISHED)`.
   3. `row` = the manual row for `(article.id, "manual_export", "manual")` with `version_id == article.approved_version_id`, `for_update`. Missing → `ProblemError(409, "Invalid state transition", "no export record for the approved version")`.
   4. `require_transition(PUBLICATION, row.status, CONFIRMED)`. Set `row.status="CONFIRMED"`, `row.published_url=url`, `row.published_at=now`, `row.confirmed_by=principal.user_id`.
   5. `set_article_status(... PUBLISHED)`. Set `article.published_at=now`, `article.published_url=url`, `article.published_version_id=article.approved_version_id`.
   6. `audit(action="article.confirm_published", details={"url": url, "versionId": article.approved_version_id, "publicationId": row.id})`.
   7. Commit; `await db.refresh(article)`; return `ArticleStateOut.model_validate(article)`.
4. **`list_publications`**: `get_article(db, article_id)` (404), then every `Publication` of the article ordered `created_at desc, id desc`, mapped with `PublicationOut.model_validate`.
5. **Routes.**
   - `export` and `confirm-published` depend on `require_permission(Permission.PUBLISH)`; `publications` on `Permission.VIEW`.
   - `confirm-published` passes `now=utcnow()`.
   - Export returns HTTP 200.

**Tests to write first** (`tests/publishing/test_pub_api_export.py`; database; 13 functions, 18 cases)

Setup:
- fixtures `seeded_db`, `login_as`, `make_article_graph`;
- `ids = await make_article_graph(seeded_db, status=ArticleStatus.APPROVED, approved=True)`;
- `client, csrf = await login_as(Role.PUBLISHER)`, `H = {"X-CSRF-Token": csrf}`;
- `BASE = f"/api/blog-agent/articles/{ids.article_id}"`;
- `rows(article_id)` selects `Publication` rows; `audits(action)` selects `AuditLog` rows by action.

1. `test_export_approved_article_returns_bundle`: `POST BASE/export` → 200.
   - `status == "EXPORTED"`, `articleId == str(ids.article_id)`, `versionId == str(ids.version_id)`;
   - `slug` equals the head `slug`;
   - `seo == SEOMetadata.model_validate(golden seo.json["seo"]).model_dump(mode="json")`;
   - `[r["marker"] for r in references] == ["S1", "S2", "S3", "S4", "S5"]`;
   - `disclosure == seed disclosure`;
   - `html.endswith(f"<p><em>{disclosure}</em></p>")`;
   - `text.endswith(disclosure + "\n")`;
   - `social == SocialCopy.model_validate(golden seo.json["social"]).model_dump(mode="json")`;
   - `tags` and `category` equal the head values;
   - the database article status is `EXPORTED`.
2. `test_export_records_publication_and_audit`: after the export, exactly 1 row with:
   - `publisher == "manual_export"`, `target == "manual"`, `status == "EXPORTED"`;
   - `idempotency_key == f"manual_export:{ids.version_id}"`;
   - `payload_hash == compute_payload_hash(html=body["html"], title=body["title"], slug=body["slug"], excerpt=body["excerpt"])`;
   - `"html" not in row.export_bundle`, `row.export_bundle["title"] == body["title"]`;
   - `attempts == 1`, `as_draft is False`, `requested_by` = the publisher user's id;
   - `body["publicationId"] == str(row.id)`.

   `audits("article.export")` has 1 row with `entity_type == "blog_article"`, `entity_id == str(ids.article_id)`, `details["trigger"] == "api"`.
3. `test_export_repeat_returns_stored_bundle`: a second POST → 200 and `json == first json`; still 1 publication row; still 1 `article.export` audit row.
4. `test_export_scheduled_article`: graph with `status=ArticleStatus.SCHEDULED, approved=True` → 200, `status == "EXPORTED"`.
5. `test_export_wrong_state_is_409`: graph `READY_FOR_REVIEW` → 409, `title == "Invalid state transition"`, `detail == "illegal article transition: READY_FOR_REVIEW -> EXPORTED"`; no publication row.
6. `test_export_validation_failure_is_422`: graph `APPROVED, approved=True, with_seo=False` → 422, `title == "Publish validation failed"`, `detail == [{"field": "slug", "message": "slug is required"}, {"field": "seo", "message": "SEO metadata is missing for this version"}]`; the article is still `APPROVED`; 0 publication rows; 0 `article.export` audits.
7. `test_export_unknown_article_is_404`: `title == "Article not found"`.
8. `test_confirm_published_moves_exported_to_published`: export, then `POST BASE/confirm-published` `{"url": "http://localhost:3000/blog/golden-slug"}` → 200.
   - `status == "PUBLISHED"`, `publishedUrl == "http://localhost:3000/blog/golden-slug"`, `publishedAt` is not None, `publishedVersionId == str(ids.version_id)`;
   - row `status == "CONFIRMED"`, `published_url` equal, `confirmed_by` = the user's id;
   - one `article.confirm_published` audit row with `details["url"]` equal.
9. `test_confirm_published_requires_exported`: without exporting → 409, `detail == "illegal article transition: APPROVED -> PUBLISHED"`.
10. `test_confirm_published_twice_is_409`: the second call → 409, `detail == "illegal article transition: PUBLISHED -> PUBLISHED"`.
11. `test_confirm_published_rejects_bad_urls` (6 cases: `"ftp://files.example/x"`, `"javascript:alert(1)"`, `"/blog/x"`, `"http://"`, `"http://a b.example/x"`, `"https://example.com/" + "a" * 2000`) → 422, `title == "Request validation failed"`; the article stays `EXPORTED`.
12. `test_publications_lists_rows_newest_first`: export; then insert `Publication(article_id, version_id=ids.version_id, publisher="mdcopilot_api", target="http://fake-mdcopilot.test", status="FAILED", idempotency_key=f"mdcopilot_api:{ids.version_id}", payload_hash="0"*64, attempts=1)` and flush. `GET BASE/publications` as the same client → 200.
    - `[p["publisher"] for p in json] == ["mdcopilot_api", "manual_export"]`;
    - item 1 has `status == "EXPORTED"`, `target == "manual"`, `asDraft is False`, `attempts == 1`, `externalPostId is None`.
13. `test_publications_unknown_article_is_404`: `title == "Article not found"`.

**Implementation notes**
- `Timestamps.updated_at` uses `onupdate=func.now()`. After a flush that updates the article, SQLAlchemy expires that attribute, and reading it in async code raises `MissingGreenlet`. Always `await db.refresh(article)` after `commit()` and before `ArticleStateOut.model_validate(article)`.
- Inside one `db_session` test transaction, `created_at` (`now()`) is equal for rows inserted together, so test 12's order relies on the `id desc` tie-break (uuid7 ids increase).

**Verification**
- Red: single-file command, `<file>` = `test_pub_api_export.py` → failures with 404/405 on the new routes.
- Green: the same command → `18 passed`.
- `tests/foundation/test_found_imports.py` and `tests/api/test_rbac_routes.py` → all passed.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "ManualExportPublisher: bundle, … confirm-published; `APPROVED → EXPORTED → PUBLISHED`" (backend).
- §10.6 "`blog_publications` with unique constraints" (manual row upsert and idempotency by key).
- §4.7 export idempotency and audits `article.export`, `article.confirm_published`.

### PUB-8: Publish request, schedule and unschedule

**Files**
- Modify `backend/src/mdcopilot_blog/services/publications.py`.
- Modify `backend/src/mdcopilot_blog/api/routers/publishing.py`: routes `publish`, `schedule`, `unschedule`.
- Create `backend/tests/publishing/test_pub_api_publish.py` and `backend/tests/publishing/test_pub_api_schedule.py`.

**Interfaces**
- Consumes:
  - `load_effective_config`, `factory.ensure_network_publishing`, `factory.network_publishing_active`, `factory.publisher_target`;
  - `enqueue_workflow`, `WORKFLOW_PUBLISH_ARTICLE`, `QUEUE_INTERACTIVE`, `uuid7`;
  - `WorkflowClientProtocol`, `ActionAccepted`, `ArticleStateOut`, `Principal`;
  - `set_article_status`, `audit`.
- Produces (`services/publications.py`):
```python
async def request_publish(db: AsyncSession, client: WorkflowClientProtocol, settings: Settings, *, principal: Principal,
                          article_id: uuid.UUID, as_draft: bool | None) -> ActionAccepted: ...
async def schedule_article(db: AsyncSession, settings: Settings, *, principal: Principal, article_id: uuid.UUID,
                           at: datetime, now: datetime) -> ArticleStateOut: ...
async def unschedule_article(db: AsyncSession, *, principal: Principal, article_id: uuid.UUID) -> ArticleStateOut: ...
async def unschedule_locked(db: AsyncSession, *, article: Article, actor_user_id: uuid.UUID | None,
                            details: Mapping[str, object]) -> None: ...   # caller holds the lock; flush only
```
- Produces (router):
  - `POST /articles/{article_id}/publish` (PUBLISH, `status_code=202`), body `Annotated[PublishRequest | None, Body()] = None` → `ActionAccepted`;
  - `POST /articles/{article_id}/schedule` (SCHEDULE), body `ScheduleRequest` → `ArticleStateOut`;
  - `POST /articles/{article_id}/unschedule` (SCHEDULE) → `ArticleStateOut`.

**Behaviour rules**
1. **`request_publish`**
   1. `article = get_article(db, article_id, for_update=True)`.
   2. `config = await load_effective_config(db, settings, run_id=article.run_id)`, then `factory.ensure_network_publishing(settings, config)`. `PublishingDisabled` propagates → global 409 `Publishing disabled`, detail is the message. Nothing is enqueued and nothing is sent.
   3. `article.status` not APPROVED or PUBLISH_FAILED, or `approved_version_id` None → `raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.PUBLISHING)`.
   4. `draft = as_draft if as_draft is not None else (article.approval_mode == ApprovalMode.DRAFT)`, and `vid = article.approved_version_id`. Keep `run_id = article.run_id`.
   5. `await db.commit()` (releases the lock; nothing changed).
   6. `parts = await enqueue_workflow(client, workflow_name=WORKFLOW_PUBLISH_ARTICLE, queue_name=QUEUE_INTERACTIVE, workflow_id=f"publish-{vid}-{uuid7()}", args=(str(article_id), str(vid), draft), timeout_seconds=settings.production_timeout_minutes * 60)`. Its 503 `ProblemError` propagates, with no audit row.
   7. `audit(db, actor_user_id=principal.user_id, action="article.publish", entity_type=ARTICLE_ENTITY, entity_id=str(article_id), details={"versionId": vid, "asDraft": draft, "publisher": config.publisher, "target": publisher_target(settings, config.publisher), "workflowId": parts.workflow_id})`, then commit.
   8. Return `ActionAccepted(workflow_id=parts.workflow_id, workflow_name=parts.workflow_name, queue=parts.queue, run_id=run_id, article_id=article_id, candidate_id=None)`.

   The article status is not changed here: the `publish_article` seam does it (PUB-9).
2. **`schedule_article`**
   1. `article = get_article(db, article_id, for_update=True)`.
   2. `config = load_effective_config(db, settings, run_id=article.run_id)`. If `network_publishing_active(settings, config)` and `Permission.PUBLISH not in principal.permissions` → `ProblemError(403, "Forbidden", "missing permission blog.publish")`.
   3. `article.status != APPROVED` or `approved_version_id` None → `raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.SCHEDULED)`.
   4. `at <= now` → `ProblemError(422, "Schedule time must be in the future", f"{at.isoformat()} is not after {now.isoformat()}")`.
   5. `set_article_status(... SCHEDULED)`; `article.scheduled_for = at`; `article.scheduled_by = principal.user_id`.
   6. `audit(action="article.schedule", details={"at": at, "versionId": article.approved_version_id, "networkPublishing": <bool from step 2>})`.
   7. Commit, refresh, return `ArticleStateOut`.
3. **`unschedule_locked`**: `set_article_status(... APPROVED)` (SCHEDULED → APPROVED); `previous = article.scheduled_for`; `article.scheduled_for = None`; `article.scheduled_by = None`; `audit(action="article.unschedule", actor_user_id=actor_user_id, details={"previousAt": previous, **details})`; flush.
4. **`unschedule_article`**: `article = get_article(db, article_id, for_update=True)`. `article.status != SCHEDULED` → `raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.APPROVED)`. Then `unschedule_locked(db, article=article, actor_user_id=principal.user_id, details={})`, commit, refresh, return `ArticleStateOut`.
5. **Routes.**
   - `publish`: `require_permission(Permission.PUBLISH)`, `WorkflowClientDep`, `SettingsDep`.
   - `schedule`: `require_permission(Permission.SCHEDULE)`, `now=utcnow()`.
   - `unschedule`: `require_permission(Permission.SCHEDULE)`.

**Tests to write first**

`tests/publishing/test_pub_api_publish.py` (database; 8 functions, 10 cases)

Setup:
- `ids = await make_article_graph(seeded_db, status=ArticleStatus.APPROVED, approved=True)` (approval mode `draft`);
- `client, csrf = await login_as(Role.PUBLISHER)`;
- `enable(app, **kw)` sets `app.state.settings = settings.model_copy(update={"publishing_enabled": True, "publisher": "mdcopilot_api", **kw})`;
- `URL = f"/api/blog-agent/articles/{ids.article_id}/publish"`.

1. `test_publish_enqueues_publish_article_workflow`: `enable(app)`; POST `{}` → 202.
   - Body: `workflowName == "publish_article"`, `queue == "interactive"`, `workflowId.startswith(f"publish-{ids.version_id}-")`, `runId == str(ids.run_id)`, `articleId == str(ids.article_id)`, `candidateId is None`.
   - `fake_workflow_client.enqueued[0]` has `args == (str(ids.article_id), str(ids.version_id), True)` and `timeout_seconds == settings.production_timeout_minutes * 60`.
   - The article status is still `APPROVED`.
   - One `article.publish` audit row with `details["asDraft"] is True` and `details["publisher"] == "mdcopilot_api"`.
2. `test_publish_as_draft_body_overrides_approval_mode`: `enable(app)`; POST `{"asDraft": false}` → `enqueued[0].args[2] is False`.
3. `test_publish_after_publish_failed_is_accepted`: set `article.status = "PUBLISH_FAILED"` and flush; `enable(app)` → 202.
4. `test_publish_disabled_by_default_is_409` (2 cases, publisher `manual_export` and `mdcopilot_api` with `publishing_enabled=False`): 409, `title == "Publishing disabled"`, `detail == "publishing is disabled (BLOG_PUBLISHING_ENABLED=false)"`; `enqueued == []`; no `article.publish` audit.
5. `test_publish_with_non_network_publisher_is_409` (2 cases: `enable(app, publisher="manual_export")` and `publisher="null"`): 409, `detail == f"the active publisher {key} does not publish over the network; use export"`; `enqueued == []`.
6. `test_publish_wrong_state_is_409`: graph `READY_FOR_REVIEW`; `enable(app)` → 409, `detail == "illegal article transition: READY_FOR_REVIEW -> PUBLISHING"`.
7. `test_publish_enqueue_failure_is_503_and_not_audited`: `enable(app)`; `fake_workflow_client.enqueue_error = RuntimeError("down")` → 503, `title == "Workflow service unavailable"`; 0 `article.publish` audit rows.
8. `test_publish_unknown_article_is_404`: `enable(app)` → 404 `"Article not found"`.

`tests/publishing/test_pub_api_schedule.py` (database; 9 functions, 10 cases)

Setup: `ids = await make_article_graph(seeded_db, status=ArticleStatus.APPROVED, approved=True)`; `AT = datetime.now(UTC) + timedelta(days=1)`; `BASE = f"/api/blog-agent/articles/{ids.article_id}"`.

1. `test_schedule_approved_article`: `login_as(Role.REVIEWER)` under default settings; POST `BASE/schedule` `{"at": AT.isoformat()}` → 200.
   - `status == "SCHEDULED"`, `datetime.fromisoformat(scheduledFor) == AT`;
   - database `scheduled_by` equals the reviewer's user id (the only `User` with role `reviewer`);
   - one `article.schedule` audit with `details["networkPublishing"] is False`.
2. `test_schedule_naive_time_is_422`: `{"at": "2030-01-01T09:00:00"}` → 422 `"Request validation failed"`.
3. `test_schedule_past_time_is_422`: `{"at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()}` → 422, `title == "Schedule time must be in the future"`; the article is still `APPROVED`.
4. `test_schedule_requires_approved` (2 cases): graph `READY_FOR_REVIEW` → `detail == "illegal article transition: READY_FOR_REVIEW -> SCHEDULED"`; graph `SCHEDULED, approved=True` → `detail == "illegal article transition: SCHEDULED -> SCHEDULED"`.
5. `test_schedule_requires_publish_permission_when_network_publishing_active`: `app.state.settings = settings.model_copy(update={"publishing_enabled": True, "publisher": "mdcopilot_api"})`.
   - Reviewer → 403, `title == "Forbidden"`, `detail == "missing permission blog.publish"`; the article is still `APPROVED`.
   - Then `login_as(Role.PUBLISHER)` → 200 `SCHEDULED`, with audit `details["networkPublishing"] is True`.
6. `test_schedule_unknown_article_is_404`.
7. `test_unschedule_returns_to_approved`: graph `SCHEDULED, approved=True` with `scheduled_for=AT` and `scheduled_by=None` set and flushed; reviewer POST `BASE/unschedule` → 200, `status == "APPROVED"`, `scheduledFor is None`; one `article.unschedule` audit with `details["previousAt"]` equal to `AT` (ISO string).
8. `test_unschedule_requires_scheduled`: APPROVED → 409, `detail == "illegal article transition: APPROVED -> APPROVED"`.
9. `test_unschedule_unknown_article_is_404`.

**Implementation notes**
- `enqueue_workflow` already maps any client exception to `ProblemError(503, "Workflow service unavailable", ...)` (CONTRACT §5.5). Do not catch it.
- `Principal.permissions` is a `frozenset[Permission]`.

**Verification**
- Red: single-file commands for `test_pub_api_publish.py` and `test_pub_api_schedule.py` → 404/405 failures.
- Green: `10 passed` and `10 passed`.
- `tests/foundation/test_found_imports.py` and `tests/api/test_rbac_routes.py` → all passed.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "Scheduling: `SCHEDULED` …; network → re-check `blog.publish`" (API part: `blog.schedule` + `blog.publish` rule).
- §10.6 "Default settings: … every network publish path 409 and nothing sent" (`/publish`).
- §10.6 "`PUBLISH_FAILED` retry" (API accepts retry).
- §4.7 audits `article.publish`, `article.schedule`, `article.unschedule`.

### PUB-9: Seam `publish_article` (network publish, idempotent by version)

**Files**
- Modify (stub by FOUND) `backend/src/mdcopilot_blog/services/publication_steps.py`: implement `publish_article`, keeping FOUND's models and signatures.
- Extend `backend/tests/publishing/conftest.py`: fixture `network_settings`.
- Extend `backend/tests/publishing/pub_helpers.py`: `committed_graph`, `rows_of`.
- Create `backend/tests/publishing/test_pub_steps_publish.py`.

**Interfaces**
- Consumes:
  - `render_version`, `get_article`, `ARTICLE_ENTITY`;
  - `factory.build_publisher`, `factory.ensure_network_publishing`, `factory.publisher_target`, `factory.idempotency_key`;
  - `set_article_status`, `require_transition`, `audit`;
  - ORM `Publication`.
- Produces (CONTRACT §5.6, unchanged):
```python
class PublishOutcome(BaseModel): publication_id: uuid.UUID; status: PublicationStatus; article_status: ArticleStatus; external_post_id: str | None; published_url: str | None; error: str | None
async def publish_article(sessionmaker: async_sessionmaker[AsyncSession], *, settings: Settings, config: EffectiveConfig,
                          article_id: uuid.UUID, version_id: uuid.UUID, as_draft: bool) -> PublishOutcome: ...
```
  Private helpers, also used by PUB-10:
```python
@dataclass(frozen=True)
class _Prepared: publication_id: uuid.UUID; version_id: uuid.UUID; payload: PublishPayload; idempotency_key: str; as_draft: bool; publisher_key: str
async def _begin_publish(db: AsyncSession, *, settings: Settings, config: EffectiveConfig, article: Article,
                         version_id: uuid.UUID, as_draft: bool) -> _Prepared | PublishOutcome: ...   # article row locked by caller; flush only
async def _send(settings: Settings, prepared: _Prepared) -> PublicationResult: ...
async def _finish(sessionmaker: async_sessionmaker[AsyncSession], *, article_id: uuid.UUID, prepared: _Prepared,
                  result: PublicationResult, now: datetime) -> PublishOutcome: ...
```
- Test support:
  - conftest `network_settings(api_publisher_settings) -> Settings`: `model_copy(update={"publishing_enabled": True, "publisher": "mdcopilot_api"})`.
  - `pub_helpers.committed_graph(sessionmaker, make_graph, **graph_kwargs) -> ArticleGraphIds`: opens a session from the committing sessionmaker, awaits `make_graph(db, **graph_kwargs)` (tests pass the root `make_article_graph` fixture), commits and returns the ids.
  - `pub_helpers.rows_of(sessionmaker, model, **filters) -> list`.

**Behaviour rules**
1. **`publish_article`, transaction 1** (`async with sessionmaker() as db`):
   1. `article` = row lock; missing → `LookupError(f"article {article_id} not found")`.
   2. `factory.ensure_network_publishing(settings, config)` (raises `PublishingDisabled`; nothing written, nothing sent).
   3. `x = await _begin_publish(...)`, then `await db.commit()`.
   4. If `x` is a `PublishOutcome`, return it.
2. **`_begin_publish`** (`key = str(config.publisher)`, `target = publisher_target(settings, key)`, `ikey = idempotency_key(key, version_id)`):
   1. `version_id != article.approved_version_id` → `ValueError(f"version {version_id} is not the approved version of article {article.id}")`.
   2. `row` = `Publication` for `(article.id, key, target)`, `for_update`.
   3. **Already published.** `row` exists with `row.idempotency_key == ikey` and `row.status == "PUBLISHED"` → return `PublishOutcome(publication_id=row.id, status=PUBLISHED, article_status=article.status, external_post_id=row.external_post_id, published_url=row.published_url, error=None)`. No write, no network.
   4. **Allowed article states:** APPROVED, SCHEDULED, PUBLISH_FAILED, or PUBLISHING when `row` exists with `row.idempotency_key == ikey` and `row.status == "IN_PROGRESS"` (resume after a crash). Anything else → `InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.PUBLISHING)`.
   5. `r = await render_version(db, article=article, version_id=version_id)`.
   6. Row upsert:
      - **No row:** `require_transition(PUBLICATION, PENDING, IN_PROGRESS)`, then insert `Publication(id=uuid7(), article_id, version_id, publisher=key, target, status="IN_PROGRESS", idempotency_key=ikey, payload_hash=r.payload_hash(), as_draft, attempts=1)`.
      - **Row exists:** `require_transition(PUBLICATION, row.status, IN_PROGRESS)`, then set `version_id`, `idempotency_key=ikey`, `payload_hash`, `status="IN_PROGRESS"`, `as_draft`, `attempts += 1`. `external_post_id` is kept.
   7. `set_article_status(db, article_id=article.id, target=PUBLISHING)`.
   8. **Validation failure.** If `r.issues` is non-empty:
      - `require_transition(PUBLICATION, "IN_PROGRESS", "FAILED")`; `row.status = "FAILED"`;
      - `row.last_error = {"kind": "validation", "message": msg, "issues": [{"field", "message"}]}` with `msg = "validation failed: " + "; ".join(f"{i.field}: {i.message}")`;
      - `set_article_status(... PUBLISH_FAILED)`; flush;
      - return `PublishOutcome(row.id, FAILED, PUBLISH_FAILED, row.external_post_id, None, msg)`.
   9. Flush; return `_Prepared(row.id, version_id, r.to_payload(as_draft=as_draft, external_post_id=row.external_post_id), ikey, as_draft, key)`.
3. **`_send`** runs outside any transaction: `await factory.build_publisher(settings, prepared.publisher_key).publish(prepared.payload, idempotency_key=prepared.idempotency_key, as_draft=prepared.as_draft)`. Any `Exception` → `PublicationResult(status=FAILED, external_id=None, published_url=None, published_at=None, message=f"{type(exc).__name__}: {exc}"[:2000])`.
4. **`_finish`** (own session):
   1. Lock the article, then the row (`id == prepared.publication_id`).
   2. If `article.status != PUBLISHING` or `row.idempotency_key != prepared.idempotency_key`: a concurrent attempt already finished. Return an outcome built from the current row and article (no write).
   3. On `result.status == PUBLISHED`:
      - row: `status="PUBLISHED"` (transition checked), `external_post_id=result.external_id`, `published_url=result.published_url`, `published_at=result.published_at or now`, `last_error=None`;
      - article: `set_article_status(... PUBLISHED)`, `published_at` = the row's `published_at`, `published_url=result.published_url`, `published_version_id=prepared.version_id`.
   4. Otherwise:
      - row: `status="FAILED"`, `external_post_id=result.external_id or row.external_post_id`, `last_error={"kind": "publisher", "message": result.message, "at": now.isoformat()}`;
      - article: `set_article_status(... PUBLISH_FAILED)`.
   5. Commit; return `PublishOutcome(row.id, row.status, article.status, row.external_post_id, row.published_url, None if PUBLISHED else result.message)`.
5. **Exactly one remote post.** A repeated call after success returns at rule 2.3 with no network. A resumed or concurrent send can only adopt through `find_existing` (PUB-4 rules 8 and 10), so a second remote post is never created.
6. The seam writes no audit row: the API or `process_due_article` audits the request.

**Tests to write first** (`tests/publishing/test_pub_steps_publish.py`; database, committing: fixtures `clean_db`, `committed_seed`, `sessionmaker_committing`, `make_article_graph`, `network_settings`, `patch_publisher_transport`, `fake_transport`, `fake_store`; 12 tests)

Setup:
- `SM = sessionmaker_committing`;
- `ids = await committed_graph(SM, make_article_graph, status=ArticleStatus.APPROVED, approved=True)` (tests that name another graph shape pass those keyword arguments instead);
- `config = load_effective_config(db, network_settings)` in a committing session;
- `patch_publisher_transport(fake_transport)` unless the test says otherwise;
- `call(**kw) = publish_article(SM, settings=network_settings, config=config, article_id=ids.article_id, version_id=ids.version_id, as_draft=False, **kw)`.

1. `test_publish_article_publishes_and_records`: outcome `status == PUBLISHED`, `article_status == PUBLISHED`, `error is None`, `external_post_id == <the single fake post id>`, `published_url == f"http://localhost:3000/blog/{head slug}"`.
   - Database article: `status == "PUBLISHED"`, `published_version_id == ids.version_id`, `published_url` equal, `published_at` not None.
   - Database row: `publisher == "mdcopilot_api"`, `target == "http://fake-mdcopilot.test"`, `status == "PUBLISHED"`, `idempotency_key == f"mdcopilot_api:{ids.version_id}"`, `attempts == 1`, `as_draft is False`, `last_error is None`.
2. `test_publish_article_as_draft_has_no_public_url`: `as_draft=True` → the fake post `status == "draft"`; outcome `published_url is None`; database article `published_url is None` and `status == "PUBLISHED"`.
3. `test_publish_article_twice_sends_nothing_the_second_time`: call twice → equal outcomes. After the second call: `len(fake_store.requests)` unchanged, `fake_store.login_count == 1`, 1 fake post, row `attempts == 1`.
4. `test_publish_article_failure_then_retry_yields_one_post`:
   - First with `patch_publisher_transport(TimeoutAfterCreate(fake_transport, fail_lookups=True))` → outcome `status == FAILED`, `article_status == PUBLISH_FAILED`, `error.startswith("create timed out (ReadTimeout)")`; row `status == "FAILED"`, `attempts == 1`, `last_error["kind"] == "publisher"`.
   - Then `patch_publisher_transport(fake_transport)` and call again → `PUBLISHED`; row `attempts == 2`.
   - 1 fake post; POST records to `/api/v1/admin/blogs` == 1.
5. `test_publish_article_resumes_after_crash_in_progress`: in a committing session, set article `status="PUBLISHING"` and insert row `IN_PROGRESS` with `idempotency_key=f"mdcopilot_api:{ids.version_id}"`, `target="http://fake-mdcopilot.test"`, `payload_hash="0"*64`, `attempts=1`; commit. Also `fake_store.add_post(title=<head title or operational title>, slug=<head slug>, status="published")`. Call → `PUBLISHED`; 1 fake post; row `attempts == 2`; POST records == 0.
6. `test_publish_article_disabled_raises_and_sends_nothing`: `patch_publisher_transport(RecordingTransport(handler raising AssertionError))`; settings `api_publisher_settings` (publishing disabled); `pytest.raises(PublishingDisabled)`; `transport.calls == []`; 0 publication rows; the article is still `APPROVED`.
7. `test_publish_article_wrong_state_raises`: graph `READY_FOR_REVIEW` → `pytest.raises(InvalidTransition)`; 0 rows.
8. `test_publish_article_rejects_version_that_is_not_approved`: `version_id=uuid7()` → `pytest.raises(ValueError, match="is not the approved version")`.
9. `test_publish_article_validation_failure_marks_publish_failed`: graph `APPROVED, approved=True, with_seo=False` → outcome `FAILED`, `article_status == PUBLISH_FAILED`, `error == "validation failed: slug: slug is required; seo: SEO metadata is missing for this version"`; row `status == "FAILED"`, `last_error["kind"] == "validation"`; `fake_store.requests == []`.
10. `test_export_then_api_publish_same_version_creates_two_rows`: graph `APPROVED, approved=True, publication=PublisherKey.MANUAL_EXPORT` → call → `PUBLISHED`; rows for the article: 2, with `{r.publisher for r in rows} == {"manual_export", "mdcopilot_api"}`; no `IntegrityError`.
11. `test_republish_newer_version_updates_the_same_row`:
    - Insert a row `FAILED` for `ids.version_id` (key `mdcopilot_api:<v1>`, target as above, `attempts=1`).
    - `v2 = await add_version_copy(db, ids, set_current=True, set_approved=True)`; commit.
    - Call with `version_id=v2` → `PUBLISHED`.
    - Exactly one `mdcopilot_api` row, with the same `id` as before, `version_id == v2`, `idempotency_key == f"mdcopilot_api:{v2}"`, `attempts == 2`.
12. `test_publish_article_unexpected_publisher_exception_is_recorded`: patch `factory.build_publisher` to return an object whose `publish` raises `RuntimeError("boom")` → outcome `FAILED`, `error == "RuntimeError: boom"`, `article_status == PUBLISH_FAILED`.

**Implementation notes**
- Call the factory through the module attribute (`from mdcopilot_blog.publishing import factory`, then `factory.build_publisher(...)`), so `patch_publisher_transport` and test 12's patch take effect.
- Transaction 1 commits before `_send`, so the network call never holds a row lock or an open transaction.

**Verification**
- Red: single-file command, `<file>` = `test_pub_steps_publish.py` → `NotImplementedError("PUB implements this")` failures.
- Green: the same command → `12 passed`.
- `tests/foundation/test_found_imports.py` → all passed.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "MDCopilotApiPublisher: … `PUBLISH_FAILED` retry" (seam).
- §10.6 "`blog_publications` with unique constraints" (idempotency by key; export then API publish of the same version → two rows; newer version updates the row).
- §10.6 "Publish twice, or retry after timeout-after-create → exactly one post" (seam level).
- CONTRACT §5.6 `publish_article`.

### PUB-10: Seams `select_due_articles` and `process_due_article`

**Files**
- Modify `backend/src/mdcopilot_blog/services/publication_steps.py`.
- Extend `backend/tests/publishing/pub_helpers.py`: `set_schedule`, `committed_user`.
- Create `backend/tests/publishing/test_pub_steps_due.py`.

**Interfaces**
- Consumes:
  - `export_locked`, `unschedule_locked` (PUB-7, PUB-8);
  - `_begin_publish`, `_send`, `_finish` (PUB-9);
  - `factory.network_publishing_active`;
  - ORM `User`; `Role`, `Permission`, `permissions_for`; `audit`.
- Produces (CONTRACT §5.6, unchanged):
```python
class DueArticle(BaseModel): article_id: uuid.UUID; version_id: uuid.UUID; scheduled_for: datetime; scheduled_by: uuid.UUID | None
async def select_due_articles(db: AsyncSession, *, now: datetime) -> list[DueArticle]: ...
class DueOutcome(BaseModel): article_id: uuid.UUID; action: Literal["exported","published","publish_failed","skipped_state","skipped_permission"]; publication_id: uuid.UUID | None
async def process_due_article(sessionmaker: async_sessionmaker[AsyncSession], *, settings: Settings, config: EffectiveConfig,
                              article_id: uuid.UUID, now: datetime) -> DueOutcome: ...
```
- Test support:
  - `pub_helpers.set_schedule(sessionmaker, article_id, *, at: datetime, user_id: uuid.UUID | None) -> None`: sets `scheduled_for` and `scheduled_by` and commits.
  - `pub_helpers.committed_user(sessionmaker, role: Role, *, active: bool = True) -> uuid.UUID`: `create_user` in a committing session, sets `is_active`, commits.

**Behaviour rules**
1. **`select_due_articles`** (read only, no locks) returns `blog_articles` rows with `status = 'SCHEDULED'`, `scheduled_for <= now` and `approved_version_id IS NOT NULL`, ordered `scheduled_for, id`, mapped to `DueArticle(article_id=id, version_id=approved_version_id, scheduled_for, scheduled_by)`.
2. **`process_due_article`, transaction 1** (`async with sessionmaker() as db`, article row lock):
   1. **Skip check.** Article missing, or `status != SCHEDULED`, or `scheduled_for is None`, or `scheduled_for > now`, or `approved_version_id is None` → return `DueOutcome(article_id, "skipped_state", None)` with no write.
   2. **Manual path** when `not factory.network_publishing_active(settings, config)`:
      - `res = await export_locked(db, article=article, actor_user_id=None, trigger="schedule")`.
      - `res.issues` non-empty → `unschedule_locked(db, article=article, actor_user_id=None, details={"reason": "export validation failed", "issues": [{"field": i.field, "message": i.message} for i in res.issues]})`, commit, return `DueOutcome(article_id, "publish_failed", None)`.
      - Otherwise commit and return `DueOutcome(article_id, "exported", res.publication_id)`.
   3. **Network path, permission re-check.** `user = await db.get(User, article.scheduled_by)` when `scheduled_by` is not None.
      - Allowed iff `user is not None and user.is_active and Permission.PUBLISH in permissions_for(Role(user.role))`. A `ValueError` from `Role(...)` means not allowed.
      - Not allowed → `unschedule_locked(db, article=article, actor_user_id=None, details={"reason": "scheduler no longer holds blog.publish", "scheduledBy": article.scheduled_by})` (the details are captured before the column is cleared), commit, return `DueOutcome(article_id, "skipped_permission", None)`.
   4. **Network path, begin.** `x = await _begin_publish(db, settings=settings, config=config, article=article, version_id=article.approved_version_id, as_draft=(article.approval_mode == ApprovalMode.DRAFT))`, then `audit(db, actor_user_id=None, action="article.publish", entity_type=ARTICLE_ENTITY, entity_id=str(article_id), details={"trigger": "schedule", "versionId": article.approved_version_id, "asDraft": <as_draft>, "scheduledBy": article.scheduled_by})`, then commit. The article is now `PUBLISHING`, or `PUBLISH_FAILED` on validation failure, so a concurrent or second tick returns `skipped_state` at step 1.
   5. If `x` is a `PublishOutcome` (validation failure) → return `DueOutcome(article_id, "publish_failed", x.publication_id)`.
3. **Network path, send and finish.** `result = await _send(settings, x)`, `outcome = await _finish(sessionmaker, article_id=article_id, prepared=x, result=result, now=now)`. Return `DueOutcome(article_id, "published" if outcome.status == PUBLISHED else "publish_failed", outcome.publication_id)`.
4. Notifications are INT's job. This seam never writes `blog_notifications`.

**Tests to write first** (`tests/publishing/test_pub_steps_due.py`; database, committing: fixtures `clean_db`, `committed_seed`, `sessionmaker_committing`, `make_article_graph`, `settings`, `network_settings`, `patch_publisher_transport`, `fake_transport`, `fake_store`; 10 functions, 12 cases)

Setup:
- `NOW = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)`;
- `SM = sessionmaker_committing`;
- `sched = await committed_graph(SM, make_article_graph, status=ArticleStatus.SCHEDULED, approved=True)`;
- `config_for(s)` loads `EffectiveConfig` with settings `s`;
- `due(s, article_id)` calls `process_due_article(SM, settings=s, config=config_for(s), article_id=article_id, now=NOW)`.

1. `test_select_due_articles_filters_and_orders`: does not use the shared `sched` graph. It builds four graphs, all with `approved=True` and `with_seo=False` (so head slugs stay NULL and the partial unique slug index is never hit):
   - A: `SCHEDULED`, at `NOW - 2h`;
   - B: `SCHEDULED`, at `NOW - 1h`, `scheduled_by` = a publisher user;
   - C: `SCHEDULED`, at `NOW + 1h`;
   - D: `APPROVED, approved=True`, with `scheduled_for = NOW - 3h` set directly.

   Result `[(d.article_id, d.version_id, d.scheduled_by) for d in select_due_articles(db, now=NOW)] == [(A.article_id, A.version_id, None), (B.article_id, B.version_id, <publisher id>)]`.
2. `test_due_manual_export_is_handled_exactly_once`: `set_schedule(SM, sched.article_id, at=NOW - timedelta(minutes=1), user_id=None)`; default `settings`.
   - First call → `action == "exported"`, `publication_id` not None; the article is `EXPORTED`.
   - Second call → `DueOutcome(article_id, "skipped_state", None)`.
   - 1 publication row, `status == "EXPORTED"`, `requested_by is None`.
   - 1 `article.export` audit with `actor_user_id is None` and `details["trigger"] == "schedule"`.
3. `test_due_concurrent_ticks_handle_the_article_once`: as test 2, but `asyncio.gather(due(settings, id), due(settings, id))` → `sorted(o.action for o in outcomes) == ["exported", "skipped_state"]`; 1 publication row.
4. `test_due_article_not_yet_due_is_skipped`: at `NOW + 1 minute` → `skipped_state`; still `SCHEDULED`; 0 publication rows.
5. `test_due_network_publishes_when_scheduler_holds_publish`: `patch_publisher_transport(fake_transport)`; `user = committed_user(SM, Role.PUBLISHER)`; schedule due with `user_id=user`; `due(network_settings, id)` → `action == "published"`.
   - The article is `PUBLISHED`; 1 fake post, whose `status == "draft"` (graph approval mode `draft`).
   - 1 `article.publish` audit with `details["trigger"] == "schedule"`.
   - A second call → `skipped_state`.
6. `test_due_network_skips_when_scheduler_lost_permission` (3 cases: `committed_user(SM, Role.REVIEWER)`, `committed_user(SM, Role.PUBLISHER, active=False)`, `user_id=None`), with `patch_publisher_transport(fake_transport)`:
   - `action == "skipped_permission"`, `publication_id is None`;
   - the article is `APPROVED` with `scheduled_for is None` and `scheduled_by is None`;
   - `fake_store.requests == []`;
   - 1 `article.unschedule` audit with `actor_user_id is None` and `details["reason"] == "scheduler no longer holds blog.publish"`.
7. `test_due_network_failure_is_publish_failed_once`: `patch_publisher_transport(RecordingTransport(handler))`, where the handler returns login 200 with `set-cookie: access_token=tok; Path=/api`, 404 for `/api/v1/blogs/…`, `[]` for the admin list, and 503 for POST. Publisher user scheduled, due.
   - `action == "publish_failed"`; the article is `PUBLISH_FAILED`; the row is `FAILED`.
   - A second call → `skipped_state`, and no new request is recorded.
8. `test_due_manual_validation_failure_unschedules`: graph `SCHEDULED, approved=True, with_seo=False`, due, default settings.
   - `action == "publish_failed"`, `publication_id is None`.
   - The article is `APPROVED` with `scheduled_for is None`.
   - 1 `article.unschedule` audit with `details["reason"] == "export validation failed"` and `details["issues"][0] == {"field": "slug", "message": "slug is required"}`.
9. `test_due_network_publishing_disabled_falls_back_to_export`: `patch_publisher_transport(RecordingTransport(handler raising AssertionError))`; settings `api_publisher_settings.model_copy(update={"publisher": "mdcopilot_api"})` (publishing disabled); publisher user scheduled, due.
   - `action == "exported"`; `transport.calls == []`.
   - The only row has `publisher == "manual_export"`.
10. `test_due_missing_article_is_skipped`: `due(settings, uuid7())` → `skipped_state`.

**Implementation notes**
- `asyncio.gather` over two `process_due_article` calls uses two pooled connections. The committing sessionmaker's engine (`pool_size=2, max_overflow=3`, CONTRACT §8.1) allows it. The second call blocks on `SELECT … FOR UPDATE` until the first commits, then sees `EXPORTED`.
- `Role(user.role)` raises `ValueError` for an unknown stored role. Treat that as "no permission".

**Verification**
- Red: single-file command, `<file>` = `test_pub_steps_due.py` → `NotImplementedError("PUB implements this")` failures.
- Green: the same command → `12 passed`.
- `tests/foundation/test_found_imports.py` → all passed.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "Scheduling: `SCHEDULED`, `publish_due` every 5 min; manual → export + notification; network → re-check `blog.publish`" (seams; INT owns the schedule and notification).
- §10.6 "Scheduled article handled exactly once; second tick does nothing" (seam level, including concurrent ticks).

### PUB-11: Route authorisation matrix, default-settings no-network guarantee, OpenAPI shapes

**Files**
- Create `backend/tests/publishing/test_pub_api_auth.py`, `backend/tests/publishing/test_pub_no_network.py`, `backend/tests/publishing/test_pub_openapi.py`.
- Production code changes only if a test here exposes a defect in a PUB-owned module.

**Interfaces**
- Consumes: the seven §4.7 routes; `publication_steps.publish_article`, `process_due_article`; `backend/tests/api_shapes.json`; `create_app(settings).openapi()`.
- Produces: tests only.

**Behaviour rules** (asserted here, implemented in PUB-5 to PUB-10)
1. Every §4.7 route depends on `require_permission`:
   - an anonymous request → 401 `Not authenticated`;
   - a role without the permission → 403 `Forbidden`, detail `missing permission <perm>`;
   - viewers are rejected on every mutating route.
2. With the forced test settings (`publishing_enabled=False`, `publisher="manual_export"`):
   - export and confirm-published succeed;
   - `/publish` returns 409;
   - the `publish_article` seam raises `PublishingDisabled`;
   - due processing takes the export path;
   - no HTTP request is ever made, also when `publisher="mdcopilot_api"` with publishing disabled.
3. For each of `IssueOut`, `PreviewOut`, `ExportBundleOut`, `ConfirmPublishedRequest`, `PublishRequest`, `ScheduleRequest`, `PublicationOut`:
   - the OpenAPI component property set equals `props` in `tests/api_shapes.json`;
   - the properties whose schema has an `anyOf` containing `{"type": "null"}` equal `nullable`.

**Tests to write first**

`tests/publishing/test_pub_api_auth.py` (database; 3 functions, 17 cases)

`ROUTES` is a list of `(method, path_template, json_body, permission, lacking_role)`, with `{id}` a random uuid:
```text
("GET",  "/api/blog-agent/articles/{id}/preview",            None,                                         VIEW,     None)
("POST", "/api/blog-agent/articles/{id}/export",             None,                                         PUBLISH,  REVIEWER)
("POST", "/api/blog-agent/articles/{id}/confirm-published",  {"url": "https://example.com/blog/x"},        PUBLISH,  REVIEWER)
("POST", "/api/blog-agent/articles/{id}/publish",            {},                                           PUBLISH,  REVIEWER)
("POST", "/api/blog-agent/articles/{id}/schedule",           {"at": "2030-01-01T09:00:00+00:00"},          SCHEDULE, EDITOR)
("POST", "/api/blog-agent/articles/{id}/unschedule",         None,                                         SCHEDULE, EDITOR)
("GET",  "/api/blog-agent/articles/{id}/publications",       None,                                         VIEW,     None)
```
1. `test_publishing_routes_reject_anonymous` (7 cases, `client` without login) → 401, `json()["title"] == "Not authenticated"`.
2. `test_publishing_routes_reject_roles_without_permission` (5 cases with a lacking role; `login_as(lacking_role)`, header `X-CSRF-Token`) → 403, `detail == f"missing permission {permission.value}"`.
3. `test_viewer_cannot_call_mutating_publishing_routes` (5 POST cases, `login_as(Role.VIEWER)`) → 403, `detail == f"missing permission {permission.value}"`.

`tests/publishing/test_pub_no_network.py` (database; 4 functions, 7 cases)

Fixture `failing`: `RecordingTransport` whose handler raises `AssertionError("network used")`. Every test calls `patch_publisher_transport(failing)`.

1. `test_default_settings_export_and_confirm_work_without_network`:
   - asserts `settings.publishing_enabled is False` and `settings.publisher == "manual_export"`;
   - `seeded_db` graph `APPROVED, approved=True`; publisher login; export → 200 `EXPORTED`; confirm-published `{"url": "https://www.mdcopilot.health/blog/x"}` → 200 `PUBLISHED`;
   - `failing.calls == []`.
2. `test_default_settings_publish_route_is_409_and_sends_nothing` (2 cases: `app.state.settings = settings`, and `settings.model_copy(update={"publisher": "mdcopilot_api"})`) → 409, `title == "Publishing disabled"`; `fake_workflow_client.enqueued == []`; `failing.calls == []`.
3. `test_default_settings_publish_step_raises_and_sends_nothing` (2 cases, the same settings pair; committing fixtures; graph `APPROVED, approved=True`) → `pytest.raises(PublishingDisabled)`; `failing.calls == []`; 0 publication rows with `publisher == "mdcopilot_api"`.
4. `test_default_settings_due_processing_sends_nothing` (2 cases, the same pair; committing; graph `SCHEDULED, approved=True`, due, `scheduled_by` = a publisher user) → `action == "exported"`; `failing.calls == []`; 0 `mdcopilot_api` rows.

`tests/publishing/test_pub_openapi.py` (no database; 2 functions, 8 cases)

1. `test_publishing_models_match_api_shapes` (7 cases, one per model name):
   - `schema = create_app(settings).openapi()["components"]["schemas"][name]`;
   - `sorted(schema["properties"]) == shapes[name]["props"]`;
   - `sorted(p for p, s in schema["properties"].items() if {"type": "null"} in s.get("anyOf", [])) == shapes[name]["nullable"]`.

   `shapes = json.loads((Path(__file__).resolve().parents[1] / "api_shapes.json").read_text())`.
2. `test_publishing_routes_are_registered`:
   - `paths = create_app(settings).openapi()["paths"]`;
   - `"get"` is in `paths["/api/blog-agent/articles/{article_id}/preview"]` and `paths["/api/blog-agent/articles/{article_id}/publications"]`;
   - `"post"` is in each of `export`, `confirm-published`, `publish`, `schedule`, `unschedule` under the same prefix;
   - `paths[".../publish"]["post"]["responses"]` has key `"202"`.

**Implementation notes**
- `create_app(settings)` builds the OpenAPI document without running the lifespan, so no database is needed. The root conftest imports `create_app` only inside fixtures, and these tests import it inside the test functions for the same reason.
- If a shape comparison fails because FOUND's `api_shapes.json` differs from CONTRACT §4.7, do not edit either shapes file. Add `Request: api_shapes <Model> differs: <props/nullable diff>` to `requests/pub.md` and stop on that item.

**Verification**
- TDD order for this task: write the three files at the start of PUB-6, before any route code, and run them red then:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/publishing/test_pub_api_auth.py tests/publishing/test_pub_no_network.py tests/publishing/test_pub_openapi.py
  ```
  Expected red: failures from 404/405 on the missing routes (auth and no-network tests) and `KeyError` for missing components (OpenAPI tests); `NotImplementedError` for the seam cases. They stay red, and are not required green, until PUB-10 is done.
- Green (after PUB-10): the same command → `32 passed` (17 + 7 + 8).
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "Default settings: `/export` and `/confirm-published` work; every network publish path 409 and nothing sent — API tests with a transport that fails on any request".
- §10.5 "Viewer sees no mutating controls; the API rejects the calls anyway" (PUB routes).
- CONTRACT §8.3 (per route: success, 401 and 403 tests; `test_pub_openapi.py`).

### PUB-12: Spike S5 tooling and results file, manual paste-check steps

**Files**
- Create `backend/tests/publishing/test_pub_s5_live.py`.
- Create `docs/blog-agent/spikes/S5-mdcopilot-publisher.md`.
- Create `docs/blog-agent/PUBLISHING_MANUAL_CHECK.md`.
- Append lines to `.superpowers/sdd/phases-2-10/requests/pub.md`.

**Interfaces**
- Consumes:
  - `get_settings()` (real environment, not the forced test settings);
  - `MDCopilotApiPublisher`, `pub_helpers.TimeoutAfterCreate`, `uuid7`, `httpx.AsyncHTTPTransport`, `SimpleCookie`.
- Produces: one live test (`@pytest.mark.live`) and two documents.

**Behaviour rules**
1. **Skipping.** `test_pub_s5_live.py::test_s5_local_mdcopilot_publisher` carries `@pytest.mark.live`. The root conftest skips it unless `BLOG_LIVE_TESTS == "1"`. It also calls `pytest.skip("S5 needs BLOG_PUBLISHER_LOGIN_ID and BLOG_PUBLISHER_PASSWORD")` when either value is None or blank in `get_settings()`. It never requests a database fixture.
2. **Gate.** S5 is run only after the presence check prints `set` for both variables and the controller has answered a `Request: S5 go` line in `requests/pub.md` with an owner go. S5 costs $0 but writes to the owner's local MDCopilot database.
3. **Test data.**
   - `hex12 = uuid7().hex[-12:]`, `title = f"S5 spike draft {hex12}"`, `slug = f"s5-spike-{hex12}"`;
   - `html = "<p>S5 spike post created by mdcopilot-blog. Safe to delete.</p>"`, `excerpt = "S5 spike"`.
4. **Steps.** Each step prints one line `S5 step <n>: <result>`. No line contains the token, password or login id.
   1. Raw `httpx` login `POST {api_url}{login_path}` with `{"phone", "password"}` → print the status code and the name of the access-token cookie found (`access_token` or `*_access_token`). Assert 200 and a cookie found.
   2. Bearer-only `GET /admin/blogs?limit=1` with no cookies → print the status; assert 200. Then a bearer-only POST check happens in step 3; print `bearer-only POST passes CSRF: yes` when step 3 returns 200.
   3. `MDCopilotApiPublisher(get_settings()).publish(payload, idempotency_key=f"s5:{hex12}", as_draft=True)` → print the result status and `external_id`; assert `PUBLISHED`.
   4. A second publisher with `transport=TimeoutAfterCreate(httpx.AsyncHTTPTransport())` publishes a second payload (`title + " timeout"`, `slug + "-timeout"`) as a draft → print the result status and message; assert `PUBLISHED`.
   5. `find_existing` for the step-4 payload → print whether the post was found and its id equals the step-4 id; assert found.
   6. Raw paging of `GET /admin/blogs` (limit 50) counting rows with slug `slug + "-timeout"` → print the count; assert `== 1`.
   7. Raw `PUT /admin/blogs/{step-3 id}` with `{"title": title + " renamed", "slug": slug}` → print the returned slug; assert `== slug`. Then raw `PUT` with only `{"title": title + " no slug"}` → print the returned slug (documents regeneration); no assertion on its value.
   8. Cleanup in `finally`: raw `DELETE /admin/blogs/{id}` for both created posts → print the statuses.
5. **`S5-mdcopilot-publisher.md` sections**, in order:
   - `Status:` — `pending owner input (…)` per the header table, or `complete <YYYY-MM-DD>`;
   - `Owner inputs` (names only, never values);
   - `Command` (the exact live command below);
   - `Results` — a table with one row per step 1–7: step, expected, observed, pass/fail, copied from the printed lines;
   - `Findings` — access-token cookie name; bearer-only requests skip CSRF (yes/no); timeout-after-create reconciliation (one post, yes/no); PUT with slug keeps the URL (yes/no); PUT without slug regenerates it (observed slug);
   - `Deviations from the fake API` (any behaviour the fake does not mirror, each with a follow-up `Request:` line for PUB);
   - `Cleanup` (delete statuses).

   While pending, `Results` and `Findings` read `Not run: pending owner input.`
6. **`PUBLISHING_MANUAL_CHECK.md` sections**, in order:
   - **Purpose:** confirm an exported bundle survives the MDCopilot Quill 1.3.7 editor.
   - **Prerequisites:**
     - local MDCopilot frontend at `http://localhost:3000` and backend running;
     - an MDCopilot admin login;
     - the blog stack running;
     - an article in `APPROVED` with SEO.
   - **Steps:**
     1. Open the article in the blog dashboard (`/articles/<id>`) and choose "Approve & export" (or "Export" if it is already approved). The article shows `EXPORTED`.
     2. In another tab open `http://localhost:3000/admin/blogs/new`.
     3. Use "Copy title" and paste into **Title**.
     4. Use "Copy slug" and paste into **Slug**.
     5. Use "Copy excerpt" and paste into **Excerpt**.
     6. Use "Copy article", click inside the content editor, and paste with Cmd+V or Ctrl+V.
     7. Set **Status** to Published and click **Publish**.
     8. Open `http://localhost:3000/blog/<slug>`.
     9. Tick each checklist item.
     10. In the blog dashboard choose "Confirm published" and paste the public URL; the article shows `PUBLISHED`.
     11. Record the result.
   - **Checklist:**
     - (a) every H2 heading of the article appears as a heading;
     - (b) citation links `[1]`…`[n]` are clickable and open the right source;
     - (c) the pull quote appears as a block quote;
     - (d) a "References" heading is followed by a numbered list whose titles link to the sources;
     - (e) the AI-assistance disclosure is the last paragraph;
     - (f) no raw Markdown (`##`, `**`, `[S1]`) is visible;
     - (g) no empty paragraphs appear between blocks;
     - (h) nested lists, if any, are shown flat. This is expected: Quill 1.3.7 has no true nested lists.
   - **Record:** date, article id, slug, checklist pass/fail per item, notes.
   - **Cleanup:** delete the post in MDCopilot admin if it was only a test.
   - **Result:** `pending owner check`, until the owner records a result.

   INT links this file from `LOCAL_DEVELOPMENT.md`. PUB does not edit `LOCAL_DEVELOPMENT.md`.
7. **`requests/pub.md` lines.**
   - When S5 is pending: `Request: S5 pending — needs BLOG_PUBLISHER_LOGIN_ID/BLOG_PUBLISHER_PASSWORD and a running local MDCopilot backend (ENVIRONMENT=development); S5 creates and deletes two draft posts in that local backend, so PUB also asks for an owner go (Request: S5 go)`.
   - After a run: `Live: S5 — <number of HTTP requests> requests — $0 — docs/blog-agent/spikes/S5-mdcopilot-publisher.md`.

**Tests to write first**
- `tests/publishing/test_pub_s5_live.py::test_s5_local_mdcopilot_publisher`, as in rules 1–4 (1 test, skipped in default runs).

**Implementation notes**
- A real transport for the timeout simulation is `TimeoutAfterCreate(httpx.AsyncHTTPTransport())`. It forwards the POST to the local backend, reads the response, then raises `httpx.ReadTimeout`.
- `tools` resolves `host.docker.internal` on Docker Desktop for macOS, which is the default `BLOG_PUBLISHER_API_URL` host.

**Verification**
- Default suite behaviour:
  ```bash
  docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/publishing/test_pub_s5_live.py
  ```
  Expected: `1 skipped`.
- Presence check (header command). Expected output: `BLOG_PUBLISHER_LOGIN_ID set|missing`, `BLOG_PUBLISHER_PASSWORD set|missing`.
- Live run, only after the rule-2 gate:
  ```bash
  docker compose run --rm -e BLOG_LIVE_TESTS=1 -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q -s -m live tests/publishing/test_pub_s5_live.py
  ```
  Expected: 8 `S5 step` lines and `1 passed`. Copy the lines into the S5 results file.
- Documents: `grep -c "^Status:" docs/blog-agent/spikes/S5-mdcopilot-publisher.md` → `1`; `grep -c "pending owner check" docs/blog-agent/PUBLISHING_MANUAL_CHECK.md` → `1` while pending.
- The PUB lint gate exits 0.

**Acceptance covered**
- §10.6 "Spike S5" and "S5 creates a draft on the local backend" (tooling; result pending owner input).
- §10.6 "Manual paste check into local MDCopilot BlogEditor" (steps document; result pending owner).
- CONTRACT §9 rows S5 and manual paste check.

### PUB-final: Track verification

**Files**
None new. `.superpowers/sdd/phases-2-10/requests/pub.md` gets any `Request:` or `Live:` lines produced during the track.

**Steps and expected results** (all in Docker, from `mdcopilot-blog/`)
1. Import surface:
   ```bash
   docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/foundation/test_found_imports.py
   ```
   Expected: all passed. A failure in another track's file becomes a `Request:` line, not an edit.
2. Full track suite:
   ```bash
   docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/publishing tests/unit/test_null_publisher.py
   ```
   Expected: `211 passed, 1 skipped`. The count is 32 + 6 + 5 + 26 + 22 + 17 + 9 + 18 + 20 + 12 + 12 + 32 passed, plus the S5 live test skipped. If a count differs, the tests listed in the tasks are authoritative and the report states the difference.
3. Shared route guard and state-machine suites that PUB routes and transitions touch:
   ```bash
   docker compose run --rm -e BLOG_TEST_DB=mdcopilot_blog_pub_test -e PYTHONDONTWRITEBYTECODE=1 tools pytest -p no:cacheprovider -q tests/api/test_rbac_routes.py tests/unit/test_state_machine.py
   ```
   Expected: all passed.
4. The PUB lint gate (header). Expected: `All checks passed!`, `<n> files already formatted`, `Success: no issues found in <n> source files`.
5. Fake container smoke (PUB-3 commands). Expected: `fake-mdcopilot smoke ok (6 checks)`, and no `p2p-pub-fake` container left afterwards.
6. Reviewer re-run of step 2 with `-e BLOG_TEST_DB=mdcopilot_blog_pub_review_test`. Expected: the same summary.
7. Hygiene:
   - `docker ps -a --filter name=p2p-pub --format '{{.Names}}'` prints nothing;
   - no file outside the owned list changed: the report lists every file touched, each within the header table;
   - no `.env` access;
   - no git command.

**Acceptance mapping** (CONTRACT §10.6 unless noted)

| Acceptance bullet | Primary proof in this track | Status at track end |
|---|---|---|
| Spike S5 | PUB-12 live test and `S5-mdcopilot-publisher.md` | complete, or pending owner input (S5 credentials and go) |
| Renderer (markdown-it-py js-default tables off → nh3 Quill allowlist → pull quote blockquote + references → mandatory disclosure) | PUB-1 tests 1–16 | complete |
| ManualExportPublisher: bundle, rich-text clipboard + field copy buttons, download, confirm-published; `APPROVED → EXPORTED → PUBLISHED` | PUB-2; PUB-7 tests 1–11 (bundle `html` + `text` for the UI's clipboard items and copy buttons); UI owns the controls | backend complete |
| MDCopilotApiPublisher: credential login, create/update always sending slug, draft/published, field limits, `find_existing`, `BLOG_PUBLISHER_PUBLIC_URL` URL, `PUBLISH_FAILED` retry | PUB-4 tests 1–22; PUB-9 tests 1–4, 11; PUB-8 publish test 3 | complete (INT wires the workflow) |
| `blog_publications` with unique constraints | PUB-7 tests 2–3; PUB-9 tests 3, 10, 11 | complete |
| Scheduling: `SCHEDULED`, `publish_due` every 5 min; manual → export + notification; network → re-check `blog.publish` | PUB-8 schedule tests; PUB-10 tests 1–9 | seams complete (INT: schedule, workflow, notification) |
| Fake MDCopilot API container mirroring real behaviour | PUB-3 tests 1–23 and container smoke | complete |
| Rendered HTML only allow-listed tags; `javascript:` and `<script>` stripped | PUB-1 tests 2–5, 15; PUB-6 test 7 | complete |
| Default settings: `/export` and `/confirm-published` work; every network publish path 409 and nothing sent | PUB-11 no-network tests 1–4; PUB-8 publish tests 4–5; PUB-5 tests 5–6 | complete |
| Publish twice, or retry after timeout-after-create → exactly one post | PUB-4 tests 7–10, 22; PUB-9 tests 3–5 | complete |
| Scheduled article handled exactly once; second tick does nothing | PUB-10 tests 2, 3, 5, 7 | seams complete (INT workflow test) |
| Manual paste check into local MDCopilot BlogEditor | PUB-12 `PUBLISHING_MANUAL_CHECK.md` | pending owner check |
| S5 creates a draft on the local backend | PUB-12 step 3 | pending owner input |
| §10.5 Preview never renders raw model HTML (XSS fixture) | PUB-1 test 3; PUB-6 test 7 | complete (UI adds DOMPurify) |
| §10.5 Viewer sees no mutating controls; the API rejects the calls anyway | PUB-11 auth test 3 | complete for PUB routes |
| §5.8 PUB golden invariant | PUB-1 test 15 | complete |
| §4.7 audits `article.export`, `article.confirm_published`, `article.publish`, `article.schedule`, `article.unschedule` | PUB-7 tests 2, 8; PUB-8 publish test 1, schedule tests 1, 7; PUB-10 tests 2, 5, 6 | complete |
| §8.3 success/401/403 per route and OpenAPI shape test | PUB-6 to PUB-8 success tests; PUB-11 auth and OpenAPI tests | complete |
