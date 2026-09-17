# Track UI: Review dashboard — implementation plan

Status: plan, 2026-09-17. Binding: `docs/blog-agent/plans/phases-2-10/CONTRACT.md` (revision 2). When this plan and the contract disagree, the contract wins. Paths are relative to `mdcopilot-blog/`; `src/` means `frontend/src/`; `B` means the string `/api/blog-agent`.

## Header

**Goal.** Replace FOUND's page stubs with the working review dashboard: Dashboard (Today card, pipeline tracker, metrics, diversity, costs), Today's Ideas, Research, Drafts, Review Queue, Published, Article review (split screen), Topics, Content Calendar, Sources, Settings, Agent Runs, and the notifications bell. Every human action in CONTRACT §4 is wired to its endpoint, with controls shown by permission and article status. Suites mock `fetch`; this track changes no backend file, no package file and no frozen frontend file.

**Spec sections implemented.**
- ARCHITECTURE §13 (every page, the export UX), §6 (article and run states used as UI gates), §10 (gate display), §11 (human edits, versions, diff), §14 (export, publish, schedule controls), §17 (role-aware controls, DOMPurify on the preview, reasoning never shown), §18 (cost views), §19 (Settings, brand, pillars, prompt versions).
- IMPLEMENTATION_PLAN: the Phase 2 UI bullet (Research, Sources), the Phase 3 UI bullet (Ideas cards, Topics), all of Phase 6, the Phase 7 export UX, the Phase 8 in-app notifications (bell), and the Phase 9 cost views, price-override UI, per-article cost and P50/P90.
- CONTRACT §4.12 (routes, endpoints, heading rule), §5.1 (TS enum mirrors), §5.7 Rules A–C (UI polling), §8.3 (shape file), §10.1/10.2/10.3/10.5/10.6/10.7/10.8 (UI rows).

**Owned files (CONTRACT §2.2, UI).**

| Path | Notes |
|---|---|
| `frontend/src/routes/**` except `app-layout.tsx`, `login-page*`, `require-permission.tsx`, `forbidden-page.tsx` | page stubs by FOUND |
| `frontend/src/features/**` except `features/auth/**` | `api.ts` stubs by FOUND |
| `frontend/src/components/**` | app components; the shadcn primitives FOUND installed (§2.1) |
| `frontend/src/routes/app-layout.tsx` | UI may add the notifications bell only |
| `frontend/src/test/fixtures/**` | UI-owned mock payloads, plus `shapes.test.ts` (§8.3) |
| `frontend/src/router.test.tsx`, `frontend/src/test/setup.ts`, `frontend/src/test/helpers.tsx`, `frontend/src/index.css`, `frontend/src/lib/utils.ts`, `frontend/src/hooks/**` | handed over by FOUND when it is review-clean (§2.1) |
| `docs/blog-agent/plans/phases-2-10/ui.md` | (this plan; the assignment names the file `UI.md`) |

Also owned by rule (CONTRACT §2): `.superpowers/sdd/phases-2-10/requests/ui.md` (Request lines only).

**Read-only for UI.** `src/router.tsx`, `src/app/nav.ts`, `src/app/nav.test.ts`, `src/lib/api.ts`, `src/lib/query-client.ts`, `src/main.tsx` (not assigned in §2; treated as frozen), `src/test/api-shapes.json`, `src/features/auth/**`, `src/routes/login-page*`, `src/routes/require-permission.tsx`, `src/routes/forbidden-page.tsx`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `package.json`, `package-lock.json`, everything under `backend/`.

UI never runs `npm install`, `npm uninstall` or `npx shadcn add`. A missing package or primitive is a `Request:` line (CONTRACT §2.2).

**Extension points consumed (exact names).**
- Routes and page components (FOUND, §4.12). Each is a named export in its file: `DashboardPage` (`routes/dashboard-page.tsx`), `IdeasPage` (`routes/ideas-page.tsx`), `ResearchPage` (`routes/research-page.tsx`), `DraftsPage` (`routes/drafts-page.tsx`), `ReviewQueuePage` (`routes/review-queue-page.tsx`), `PublishedPage` (`routes/published-page.tsx`), `ArticleReviewPage` (`routes/article-review-page.tsx`, route `/articles/:articleId`, param `articleId`), `TopicsPage` (`routes/topics-page.tsx`), `CalendarPage` (`routes/calendar-page.tsx`), `SourcesPage` (`routes/sources-page.tsx`), `SettingsPage` (`routes/settings-page.tsx`), `AgentRunsPage` (`routes/agent-runs-page.tsx`). UI keeps every file name and export name.
- `NAV_ITEMS`, `NavItem`, `visibleNavItems` (`app/nav.ts`).
- `apiFetch<T>(path, init)`, `ApiRequestInit` (`json` field), `ApiError` (`status`, `body`), `problemMessage`, `setCsrfToken`, `getCsrfToken` (`lib/api.ts`). `apiFetch` sends `X-CSRF-Token` on POST/PUT/PATCH/DELETE and returns `undefined` for an empty 204 body.
- `createQueryClient()` (no retry on 4xx, `staleTime` 30 s) (`lib/query-client.ts`).
- `sessionQueryOptions`, `SessionUser`, `SessionResponse` (`features/auth/session.ts`); `hasPermission`, `Permission`, `Role` (`features/auth/permissions.ts`); `RequirePermission` and `ForbiddenPage` are used by FOUND's router only.
- `features/runs/api.ts`: `RunStatus`, `RunKind`, `RunOut`, `Page<T>`, `isTerminalRunStatus`, `RUNS_QUERY_KEY`, `runsQueryOptions`, `createRun`, `cancelRun`, `formatCost`. `features/runs/runs-table.tsx`: `RunsTable`.
- Test helpers (`test/helpers.tsx`): `sessionFor`, `jsonResponse`, `problemResponse`, `makeRun`, `runsPage`, `mockApi`, `callsTo`, `renderRoutes`.
- jsdom stubs FOUND adds to `test/setup.ts`: `ResizeObserver`, `IntersectionObserver`, `Range.prototype.getClientRects`, `Range.prototype.getBoundingClientRect`, `document.elementFromPoint`, `navigator.clipboard.write`/`writeText`, global `ClipboardItem`.
- shadcn primitives in `components/ui/`: `badge`, `button`, `card`, `dropdown-menu`, `input`, `label`, `separator`, `sheet`, `skeleton`, `sonner`, `table` (Phase 1), plus FOUND's `dialog`, `alert-dialog`, `tabs`, `textarea`, `select`, `tooltip`, `popover`, `checkbox`, `switch`, `scroll-area`, `resizable`, `toggle-group`.
- npm packages (CONTRACT §7): `@uiw/react-codemirror` 4.25.11 (it re-exports `@codemirror/view` and `@codemirror/state`, so `EditorView` is imported from `@uiw/react-codemirror`), `@codemirror/lang-markdown`, `@fullcalendar/{core,daygrid,interaction,list,react}` 6.1.21, `diff` 9 (`diffWords`), `dompurify` 3.4.15, `recharts` 3.10.1.
- The frozen shape file `src/test/api-shapes.json` (`{"<Model>": {"props": [...], "nullable": [...]}}`).

**Test database.** None. UI tests never touch Postgres; every command uses `--no-deps`.

**Docker commands (run from `mdcopilot-blog/`; the only way this track runs node).**
```bash
docker compose run --rm --no-deps web npx vitest run <path-or-file>   # one task's tests (red, then green)
docker compose run --rm --no-deps web npm test                        # whole frontend suite
docker compose run --rm --no-deps web npm run lint
docker compose run --rm --no-deps web npm run typecheck
docker compose run --rm --no-deps web npm run build
cmp backend/tests/api_shapes.json frontend/src/test/api-shapes.json   # read-only check; must print nothing
```
A reviewer or a second process uses the same commands: the web container has no shared state beyond the bind mount, and vitest 5 writes no cache directory into it.

**Owner inputs.** None is required.

| Input | Fallback built by this plan |
|---|---|
| Gate override policy (ARCHITECTURE §24.2, owned by QUAL) | Admins see "Override and approve" only when `article.gateOverridePolicy === "admin_with_reason"` (from `ArticleDetailOut`, CONTRACT §4.5); a `never` policy hides it. Settings' General tab still shows and edits the same policy for admins. |
| Network publisher (`BLOG_PUBLISHING_ENABLED`, S5) | "Publish to MDCopilot" appears to any `blog.publish` holder — not just admins — when `article.networkPublishingActive` is true (from `ArticleDetailOut`, CONTRACT §4.5/§4.7); everyone else gets the manual export flow. Schedule additionally requires `blog.publish` while it is true (CONTRACT §4.7). Cross-check finding 1 (was open item O3): resolved by adding these two fields to `ArticleDetailOut` instead of gating on `GET /settings`. |
| Daily-run timezone confirmation | Settings shows and edits whatever `effective.schedule` holds. |

### Verified facts this plan relies on (throwaway `node:24-alpine` containers `p2p-ui-*`, 2026-09-17, against the §7 dependency tree in `scratch/deps/frontend`)
1. `@uiw/react-codemirror` renders in jsdom with the FOUND stubs. `.cm-content` has role `textbox`. `userEvent.click` + `userEvent.keyboard('XYZ')` edits it and fires `onChange`. `EditorView.findFromDOM(el)` returns the view. The component's `aria-label` prop does **not** reach the textbox; `EditorView.contentAttributes.of({ 'aria-label': 'Article Markdown' })` does. `readOnly` sets `aria-readonly="true"`. `React.lazy` loading shows the fallback, then the editor.
2. FullCalendar 6.1.21 (`dayGridMonth`, `listMonth`, `timeZone="UTC"`) renders event titles in jsdom. `eventClick` fires on `userEvent.click`. `datesSet` fires on mount with `view.currentStart` = `2026-09-01T00:00:00.000Z` for `initialDate="2026-09-01"`. The toolbar title is `September 2026`, and a button named `Next month` moves it to `October 2026`. **`dateClick` does not fire in jsdom**; a `<button>` rendered through `dayCellContent` is clickable.
3. DOMPurify 3.4.15 with `{ ALLOWED_TAGS: ['h2','h3','p','strong','em','s','a','ul','ol','li','blockquote','img'], ALLOWED_ATTR: ['href','rel','src','alt'], ALLOWED_URI_REGEXP: /^https?:\/\//i, ADD_URI_SAFE_ATTR: ['rel'] }` turns the XSS probe into `<h2>T</h2><p>a <a href="https://x.org" rel="noopener noreferrer">ok</a> <a>js</a> <a>js2</a> <a>data</a></p><img><img src="https://i.org/a.png" alt="a"><blockquote>q</blockquote><ol><li>r</li></ol>t`. Scripts, iframes, SVG, tables, `style`, `class`, event handlers, and `javascript:`/`data:`/relative URLs are removed. Without `ADD_URI_SAFE_ATTR: ['rel']`, `rel` is dropped.
4. Radix `Dialog`, `AlertDialog`, `Tabs`, `Switch`, `Checkbox`, `ToggleGroup` (items have role `radio`), `Popover` and `Tooltip` work in jsdom with `userEvent`. Radix `Select` throws `target.hasPointerCapture is not a function` until `Element.prototype.hasPointerCapture`, `releasePointerCapture` and `scrollIntoView` are stubbed; with them, trigger role `combobox` → option role `option` → `onValueChange` fires.
5. Recharts 3.10.1: `ResponsiveContainer` renders no `<svg>` in jsdom, and a fixed-size chart renders an `<svg>` with no bars. Tests assert on the data table next to each chart, never on the SVG.
6. `diffWords('Book a demo today', 'Book a call today')` → `[{value:'Book a '},{removed:true,value:'demo'},{added:true,value:'call'},{value:' today'}]`.
7. A `ClipboardItem` stub with `types` and `getType()` lets tests read back both `text/html` and `text/plain` blobs (`await blob.text()` works in jsdom 30). `URL.createObjectURL` exists in jsdom 30.
8. Node ICU 78.3 in `node:24-alpine` formats IANA zones: `formatToParts` with `timeZoneName: 'longOffset'` gives `GMT+05:30` for Asia/Kolkata and `GMT-04:00` for New York on 2026-03-08 07:30Z. `Intl.supportedValuesOf('timeZone')` does **not** contain `Asia/Kolkata` or `UTC` (it lists `Asia/Calcutta`), so zone validation must construct `Intl.DateTimeFormat`.
9. Under the frozen `tsconfig.app.json` (TS 6.0.3), `import shapes from '@/test/api-shapes.json'` type-checks.
10. Lint (`eslint-plugin-react-hooks` 7.1.1 recommended, all errors): `Date.now()` in a component body fails `react-hooks/purity`, and `setState` inside `useEffect` fails `react-hooks/set-state-in-effect`. `new Date()` in render, `useState(() => Date.now())`, module helpers called in render, and `Date.now()` in event handlers all pass.

## Conventions (apply to every task)

**C1. URLs.** Every call goes through `apiFetch`. Paths are built with `blogPath(...segments)` (`B/` + each segment `encodeURIComponent`-ed, joined with `/`) and `buildQuery(params)` (UI-1). Query parameters appear in the order listed in UI-3. Tests key `mockApi` routes on those exact strings.

**C2. Query keys.** Lists use `['<area>', 'list', params]`. Everything about one article uses the prefix `['articles', articleId]` (`'detail'`, `'versions'`, `'sources'`, `'research-packets'`, `'fact-check'`, `'reviews'`, `'quality-gates'`, `'preview'`, `'publications'`, `'cost'`). Other keys: `['runs', …]` (Phase 1 prefix `RUNS_QUERY_KEY`), `['dashboard']`, `['topics', …]`, `['research-runs', …]`, `['sources', …]`, `['calendar', month]`, `['settings', …]`, `['pillars']`, `['users']`, `['agent-runs', …]`, `['metrics', …]`, `['notifications', …]`.

**C3. Invalidation (`features/shared/invalidation.ts`, UI-3).** After a mutation succeeds, call exactly the helper named in the task:
- `afterArticleChange(qc, articleId)`: prefixes `['articles', articleId]`, `['articles', 'list']`, `['dashboard']`, `['calendar']`.
- `afterWorkflowStarted(qc, articleId | null)`: `afterArticleChange` when `articleId` is not null, plus `RUNS_QUERY_KEY`, `['agent-runs']`, `['dashboard']`, `['topics']`.
- `afterTopicChange(qc)`: `['topics']`, `RUNS_QUERY_KEY`, `['dashboard']`, `['articles', 'list']`.
- `afterRunChange(qc)`: `RUNS_QUERY_KEY`, `['agent-runs']`, `['dashboard']`.

**C4. Errors.** A failed mutation shows `toast.error(describeProblem(error, '<fallback>'))`, which gives `title` or `title: detail` (UI-1). A failed query shows `QueryState`'s alert `Could not load <label>: <describeProblem>`, or the task's not-found text for a 404. Every page's `<h1>` sits outside every `QueryState` and `Suspense` boundary (CONTRACT §4.12 heading rule).

**C5. Permissions and status.** Mutating controls render only when `useCan(<permission>)` is true, **and** the status rule in `features/shared/status.ts` allows the action. Controls are not merely disabled: they are absent. The only exceptions are the Approve button's explained disabled state for a user who holds `blog.approve` (UI-12) and read-only form fields for users without `blog.settings`. The API remains the enforcement point.

**C6. Time.** Components never call `Date.now()` in render (fact 10). Server timestamps are shown with `formatDateTime(iso, timeZone)` / `formatDate(iso, timeZone)` as `YYYY-MM-DD HH:mm` / `YYYY-MM-DD`. The zone is the API-provided settings zone where a response carries one (`DashboardOut.timezone`, `CalendarMonthOut.timezone`) and `localTimeZone()` elsewhere. Tests compute expected strings with the same helper and never hard-code the container's zone.

**C7. Forms seeded from server data.** A form component takes the loaded object as a prop, is mounted with `key={<version or id>}`, and initialises state with `useState(() => fromServer(prop))`. No effect copies server data into state (fact 10).

**C8. Lazy heavy modules.** CodeMirror (`features/articles/components/markdown-editor.tsx`), FullCalendar (`features/calendar/components/month-calendar.tsx`) and Recharts (`features/metrics/components/cost-chart.tsx`) are imported only through `React.lazy(() => import(…).then((m) => ({ default: m.<Name> })))` inside `<Suspense fallback={<Skeleton aria-label="Loading <label>" />}>`. Tests find lazy content with `findBy…(…, { timeout: 5000 })`.

**C9. Test style.** `mockApi` exact keys; unsafe calls assert `X-CSRF-Token` equals `csrf-<role>` at least once per module; request bodies are read with `bodyOf` (UI-1). Polling queries are asserted with `toBeGreaterThanOrEqual`, never an exact call count. Files that spy on globals call `vi.restoreAllMocks()` in `afterEach`.

## Accessible names (tests use these; INT's Playwright smoke `scripts/e2e/phase6-smoke.sh` may rely on them)

| Where | Element | Accessible name |
|---|---|---|
| every page | `<h1>` | the nav label; the article page's is `Article review` |
| Dashboard | buttons | `Generate today's blog`, `Generate with options`, `Select recommended topic`, `Approve`, `Regenerate article` |
| Dashboard | links | `Review research`, `Open article`, `Change topic` |
| Ideas | buttons | `Regenerate topics`, `Select topic: <title>`, `Edit topic: <title>`, `Reject topic: <title>`, `Select anyway` (confirm dialog) |
| Article lists | link / controls | the article title (or `Untitled draft`); `Pillar` (select), `Search` (input and button), `Previous page`, `Next page` |
| Article review | tab lists | `Evidence` (`Topic`, `Research`, `Sources`, `Claims`, `Quality`, `Summary`), `Editor` (`Edit`, `Preview`, `Headline`, `SEO`, `Versions`, `Publish`) |
| Article review | action bar buttons | `Re-check`, `Approve`, `Reject`, `Regenerate` |
| Article review | editor | textbox `Article Markdown`; inputs `Pull quote`, `CTA`, `Excerpt`; button `Save` |
| Approve dialog | dialog / controls | dialog `Approve article`; radios `Approve as draft`, `Approve for publishing`; textbox `Override reason`; buttons `Approve`, `Override and approve` |
| Reject dialog | dialog / controls | dialog `Reject article`; textbox `Reason`; button `Reject article` |
| Regenerate dialog | dialog / controls | dialog `Regenerate`; selects `Component`, `Section`; textbox `Instructions`; button `Start regeneration` |
| Schedule dialog | dialog / controls | dialog `Schedule article`; inputs `Date`, `Time`; button `Schedule article` |
| Publish tab | buttons / input | `Export`, `Copy article`, `Copy title`, `Copy slug`, `Copy excerpt`, `Download bundle`, `Download HTML`, input `Published URL`, `Confirm published`, `Publish to MDCopilot`, `Schedule`, `Unschedule` |
| Calendar | buttons | `Open day <YYYY-MM-DD>` (day cells), `Cancel slot`, `Restore slot`, `Save note`, `Move: <title>`, `Unschedule: <title>`, `Schedule: <title>`, `Regenerate article: <title>` |
| Agent Runs | buttons | `Details for run <id>`, `Cancel run <id>` (Phase 1), `Cancel run`, `Restart run`, `Resume run`, `Retry step <step_name>`, `Restart from <step_name>`, `LLM calls for <step_name>` |
| Layout | button | `Notifications` or `Notifications (<n> unread)`; menu item `Mark all read` |

## Tasks

TDD order in every task: write the listed tests, run them red with the task's vitest command, implement, run them green, then run lint and typecheck on the whole project. Record the red and green output lines in the track report.

### UI-0: Handover check, jsdom stubs, request lines

**Files.** Modify `src/test/setup.ts` and `src/test/setup.test.ts` (both created by FOUND and handed to UI, CONTRACT Revision 3 item 2; UI extends the one file FOUND created instead of adding a second jsdom-stub test file — `src/test/fixtures/**` is reserved for UI's builder and shape tests, §UI-2). Append to `.superpowers/sdd/phases-2-10/requests/ui.md`.

**Interfaces.** Consumes FOUND's stubs (Header). Produces three extra stubs: `Element.prototype.hasPointerCapture(): boolean` (returns `false`), `Element.prototype.releasePointerCapture(): void`, `Element.prototype.scrollIntoView(): void`, and `afterEach` also calls `setCsrfToken(null)`.

**Behaviour rules.**
1. Start only after `progress.md` records FOUND as review-clean. `ls frontend/src/components/ui` must list `alert-dialog.tsx checkbox.tsx dialog.tsx popover.tsx resizable.tsx scroll-area.tsx select.tsx switch.tsx tabs.tsx textarea.tsx toggle-group.tsx tooltip.tsx`, and `frontend/src/test/api-shapes.json` must exist. A missing file becomes a `Request:` line, and the tasks that need it stop.
2. Baseline before any edit: `npm test`, `npm run lint`, `npm run typecheck` and `npm run build` all exit 0. Record the test-file and test counts.
3. Each new stub is installed with `Object.defineProperty(Element.prototype, name, { configurable: true, writable: true, value })`, and only when `typeof Element.prototype[name] !== 'function'`. This matches FOUND's `matchMedia` pattern, so `vi.unstubAllGlobals()` leaves the stubs in place.
4. Check only, expected to be a no-op: FOUND-19's `ClipboardItem` stub already provides `types: string[]` and `getType(type): Promise<Blob>` (cross-check finding 5, verified against FOUND.md). If a later FOUND change regresses that shape, replace it (one `Object.defineProperty(window, 'ClipboardItem', …)`) with a class that stores the record, sets `types = Object.keys(record)`, and has `getType` resolve the stored value (a string becomes `new Blob([value], { type })`) — inside the shared `setup.ts`, never by adding a second stub file.
5. Append these lines to `requests/ui.md` unless `progress.md` already rules on them:
   - `Request: O1 — §4.12 Dashboard row: add GET /articles/{id} (Approve needs ArticleDetailOut.currentVersionId; TodayCardOut has no version id). UI calls it; no backend change.`
   - `Request: O2 — §4.12 Settings row: add GET/PUT /themes (§10.5 puts themes in Settings; §4.12 lists them only for Sources). UI shows the same editor on both pages.`
   - `Request: O3 — RESOLVED (cross-check finding 1; CONTRACT §4.5, Revision 3 item 17): no blog.view response used to expose the active publisher, publishing_enabled or gate_override_policy; only GET /settings (blog.settings) did, so a publisher role could never see 'Publish to MDCopilot' and a reviewer could not tell Schedule also needs blog.publish. ArticleDetailOut now carries network_publishing_active and gate_override_policy directly, filled by ART from load_effective_config(run_id=article.run_id); UI-2/UI-5/UI-15 consume those fields instead of querying settings. No further action needed.`
   - `Request: O4 — Phase 1 final-review minor (session handling): in-page 401s never redirect to /login and the layout route has no errorElement. lib/query-client.ts, router.tsx and main.tsx are not UI-owned. Ruled (CONTRACT Revision 3 items 2, 22, 25): HARD-3 owns the /login redirect, the "/" route's errorElement, and the X-Session-Activity: passive polling header — no FOUND follow-up. Every refetchInterval in this track composes with features/shared/polling.ts's unlessUnauthorized/pollingInterval (UI-1), so HARD-3 adds the passive header at that one call site. UI already stops polling on 401.`
   - `Request: O5 — Phase 1 final-review minor (run permissions): GET /runs/{id} is blog.view and cancel is blog.generate, while /agent-runs is guarded by blog.agent_runs. UI follows §4.12; the owner or INT picks one guard.`
   - `Request: O6 — §4.5 VersionDiffOut.unified_diff: fix the text as "\n".join(difflib.unified_diff(a, b, fromfile, tofile, n=3, lineterm="")) so the UI can split lines on "\n".`

**Tests to write first** (append to `src/test/setup.test.ts`, the file FOUND created and handed over — add a `describe('jsdom stubs')` block there rather than a new file):
- `provides layout and observer stubs`: `typeof window.ResizeObserver === 'function'` and `typeof new ResizeObserver(() => {}).observe === 'function'`; the same for `IntersectionObserver`; `document.createRange().getClientRects().length === 0`; `document.createRange().getBoundingClientRect().width === 0`; `document.elementFromPoint(1, 1) === null`.
- `provides pointer-capture stubs for Radix Select`: `document.createElement('div').hasPointerCapture(1) === false`; `typeof Element.prototype.releasePointerCapture === 'function'`; `typeof Element.prototype.scrollIntoView === 'function'`.
- `provides a readable ClipboardItem and clipboard`: `item = new ClipboardItem({ 'text/html': new Blob(['<p>x</p>'], { type: 'text/html' }), 'text/plain': new Blob(['x'], { type: 'text/plain' }) })`; `item.types` equals `['text/html', 'text/plain']`; `await (await item.getType('text/html')).text() === '<p>x</p>'`; `await navigator.clipboard.write([item])` resolves `undefined`; `await navigator.clipboard.writeText('x')` resolves `undefined`.
- `keeps the stubs after vi.unstubAllGlobals()`: after calling `vi.unstubAllGlobals()`, `typeof window.ResizeObserver`, `typeof window.ClipboardItem` and `typeof Element.prototype.hasPointerCapture` are all `'function'`.
- `holds a token within a test`: `setCsrfToken('x')`; `getCsrfToken() === 'x'`.
- `clears the CSRF token between tests` (declared directly after the previous test): `getCsrfToken() === null`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/test/setup.test.ts` → red (the pointer-capture test fails) → green `Tests 6 passed` (added to whatever FOUND's handover already had in that file). Then `npm test` must show the baseline count plus 6, and `npm run lint` must exit 0.

**Acceptance covered.** Enables §10.5 (CodeMirror/Radix/FullCalendar suites), §10.6 clipboard tests.

### UI-1: Shared helpers

**Files.** Create in `src/features/shared/`: `query-string.ts`, `problems.ts`, `format.ts`, `time.ts`, `status.ts`, `use-can.ts`, `polling.ts`, `sanitize.ts`, `download.ts`, and a `*.test.ts` next to each (`use-can.test.tsx`). Modify `src/features/runs/api.ts` (runs polling, status filter) and `src/test/helpers.tsx`. Create `src/test/fixtures/helpers.test.tsx` and `src/features/runs/api.test.ts`.

**Interfaces produced.**
```ts
// query-string.ts
export const API_BASE = '/api/blog-agent'
export type QueryValue = string | number | boolean | null | undefined | readonly string[]
export function buildQuery(params: Record<string, QueryValue>): string
export function blogPath(...segments: string[]): string
// problems.ts
export function problemTitle(error: unknown): string | null
export function problemDetail(error: unknown): string | null
export function describeProblem(error: unknown, fallback: string): string
export function isProblem(error: unknown, status: number, title?: string): boolean
export function isUnauthorized(error: unknown): boolean
// format.ts
export function formatDateTime(iso: string | null, timeZone: string): string
export function formatDate(iso: string | null, timeZone: string): string
export function formatUsd(value: string | null): string
export function formatPercent(fraction: number | null): string
export function formatShare(fraction: number | null): string
export function formatScore(value: number | null): string
export function formatMs(ms: number | null): string
export function formatSeconds(seconds: number | null): string
export function humanizeKey(key: string): string
// time.ts
export function localTimeZone(): string
export function isValidTimeZone(zone: string): boolean
export function zonedWallTimeToIso(date: string, time: string, timeZone: string): string
export function monthOf(iso: string, timeZone: string): string
export function shiftMonth(month: string, delta: number): string
// status.ts
export const PILLAR_KEYS: readonly PillarKey[]
export const ARTICLE_STATUS_LABELS: Record<ArticleStatus, string>
export function articleStatusVariant(status: ArticleStatus): 'default' | 'secondary' | 'destructive' | 'outline'
export const IN_PROGRESS_ARTICLE_STATUSES: ReadonlySet<ArticleStatus>
export function isApprovedOrLater(status: ArticleStatus): boolean
export const GATE_LABELS: Record<GateId, string>
export function gateLabel(gate: string): string
export const articleActions: {
  canSaveEdit(s: ArticleStatus): boolean; canSelectTitle(s: ArticleStatus): boolean; canRecheck(s: ArticleStatus): boolean
  canRegenerate(s: ArticleStatus, component: ArticleComponent): boolean; canApprove(s: ArticleStatus): boolean
  canOverrideApprove(s: ArticleStatus): boolean; canReject(s: ArticleStatus): boolean; canExport(s: ArticleStatus): boolean
  canConfirmPublished(s: ArticleStatus): boolean; canPublish(s: ArticleStatus): boolean
  canSchedule(s: ArticleStatus): boolean; canUnschedule(s: ArticleStatus): boolean
}
// use-can.ts
export function useSessionUser(): SessionUser | undefined
export function useCan(permission: Permission): boolean
export function useIsAdmin(): boolean
// polling.ts
export const ACTIVE_POLL_MS = 3_000
export const NOTIFICATION_POLL_MS = 60_000
export const PENDING_ACTION_TIMEOUT_MS = 600_000
export function unlessUnauthorized(error: unknown, interval: number | false): number | false
export function runsRefetchInterval(page: Page<RunOut> | undefined, error: unknown): number | false
// sanitize.ts
export const PREVIEW_SANITIZE_CONFIG: DOMPurify.Config   // fact 3, exactly
export function sanitizePreviewHtml(html: string): string
// download.ts
export function downloadFile(filename: string, content: string, mimeType: string): void
// features/runs/api.ts (changed)
export function runsQueryOptions(limit: number, status?: RunStatus | null): …  // key [...RUNS_QUERY_KEY, { limit, status: status ?? null }]
// test/helpers.tsx (additions)
export function mockApi(routes: Record<string, RouteHandler>, fallback?: RouteHandler)
export function bodyOf(fetchMock: ReturnType<typeof mockApi>, method: string, path: string, index?: number): unknown
export function renderPage(element: ReactNode, options: { path: string; url?: string; role?: Role; permissions?: Permission[] })
export function pageOf<T>(items: T[], options?: { limit?: number; offset?: number; total?: number }): Page<T>
```
`PillarKey`, `ArticleStatus`, `GateId` and `ArticleComponent` come from `features/shared/types.ts` (UI-2). UI-1 creates that file with just these four unions, and UI-2 completes it.

**Behaviour rules.**
1. `buildQuery` skips `null`, `undefined` and `''`, and keeps insertion order. An array repeats its key for each non-empty item. Booleans become `true`/`false`, and numbers use `String(n)`. Keys and values go through `encodeURIComponent`. It returns `''` when nothing remains, else `?` plus the pairs joined with `&`.
2. `blogPath` returns `API_BASE + '/' + segments.map(encodeURIComponent).join('/')`.
3. `problemTitle` reads `error.body.title` for an `ApiError` whose body is an object with a string `title`; otherwise `null`. `problemDetail` handles four body shapes: a string `detail` returns the string; an array of `{field, message}` gives `field: message` items joined by `; `; an array of `{loc, msg}` gives `loc.join('.'): msg` items joined by `; `; anything else returns `null`. `describeProblem` returns `title: detail`, or `title`, or `fallback` when there is no title. `isProblem` checks `ApiError.status` and, when given, the title. `isUnauthorized` is `isProblem(error, 401)`.
4. `formatDateTime` builds `YYYY-MM-DD HH:mm` from `Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts`. `formatDate` gives `YYYY-MM-DD`, and returns an input matching `^\d{4}-\d{2}-\d{2}$` unchanged. Both return `—` for `null`.
5. `formatUsd` delegates to Phase 1 `formatCost` (`$` + 4 decimals); `null` → `—`. `formatPercent(f)` → `${Math.round(f * 100)}%`. `formatShare(f)` → `${(f * 100).toFixed(1)}%`. `formatScore(v)` → `v.toFixed(2)`. `formatMs(ms)` → `${ms} ms` below 1000, else `${(ms / 1000).toFixed(1)} s`. `formatSeconds(s)` → `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`. All give `—` for `null`. `humanizeKey` splits on `_` and on lower→upper camel boundaries, lower-cases the words, joins them with spaces, and capitalises the first letter.
6. `localTimeZone()` is `Intl.DateTimeFormat().resolvedOptions().timeZone`. `isValidTimeZone(z)` is `false` for `''`, `true` when `new Intl.DateTimeFormat('en-US', { timeZone: z })` does not throw, else `false` (fact 8).
7. `zonedWallTimeToIso(date 'YYYY-MM-DD', time 'HH:mm', zone)` finds the offset `O(t)` of instant `t` from the `timeZoneName: 'longOffset'` part (`GMT` means `+00:00`). It sets `guess = Date.UTC(wall)`, `o1 = O(guess)`, `o2 = O(guess − o1)`, and `offset = o2`. It returns `${date}T${time}:00${±HH:MM of offset}`. Times inside a DST gap are not validated.
8. `monthOf(iso, zone)` is `formatDate(iso, zone).slice(0, 7)`. `shiftMonth('YYYY-MM', delta)` does calendar arithmetic across years.
9. `ARTICLE_STATUS_LABELS` replace `_` with spaces and use sentence case (`READY_FOR_REVIEW` → `Ready for review`, `PUBLISH_FAILED` → `Publish failed`), except `SEO` → `SEO`. `articleStatusVariant`: `destructive` for FAILED, QUALITY_GATE_FAILED, PUBLISH_FAILED, REJECTED; `default` for APPROVED, SCHEDULED, EXPORTED, PUBLISHED; `outline` for SUPERSEDED; `secondary` otherwise.
10. `IN_PROGRESS_ARTICLE_STATUSES` = {DRAFTING, FACT_CHECKING, CLINICAL_REVIEW, EDITORIAL_REVIEW, SEO, PUBLISHING}. `isApprovedOrLater` = {APPROVED, SCHEDULED, EXPORTED, PUBLISHING, PUBLISHED, PUBLISH_FAILED}.
11. `articleActions` (CONTRACT §4.5–§4.7 status rules):
    - `canSaveEdit`: READY_FOR_REVIEW, QUALITY_GATE_FAILED, APPROVED.
    - `canSelectTitle`, `canRecheck`: READY_FOR_REVIEW, QUALITY_GATE_FAILED.
    - `canRegenerate(s, c)`: READY_FOR_REVIEW or QUALITY_GATE_FAILED, plus FAILED when `c === 'research'`.
    - `canApprove`: READY_FOR_REVIEW. `canOverrideApprove`: QUALITY_GATE_FAILED.
    - `canReject`: READY_FOR_REVIEW, QUALITY_GATE_FAILED, APPROVED, SCHEDULED, EXPORTED.
    - `canExport`: APPROVED, SCHEDULED, EXPORTED. `canConfirmPublished`: EXPORTED. `canPublish`: APPROVED, PUBLISH_FAILED.
    - `canSchedule`: APPROVED. `canUnschedule`: SCHEDULED.
12. `GATE_LABELS` maps all 19 `GateId`s: `sources_present` → `Sources present`, `claims_verified` → `Claims verified`, `no_unsupported_statistics` → `No unsupported statistics`, `no_fabricated_quotes` → `No fabricated quotes`, `no_unsourced_anecdotes` → `No unsourced anecdotes`, `no_duplicate_topic` → `No duplicate topic`, `word_count` → `Word count`, `required_structure` → `Required structure`, `cta_fresh` → `CTA present and fresh`, `no_prohibited_language` → `No prohibited language`, `seo_complete` → `SEO complete`, `fact_check_passed` → `Fact check passed`, `clinical_clear` → `Clinical review clear`, `editorial_completed` → `Editorial review completed`, `disclosure_present` → `AI disclosure present`, `independent_fact_check` → `Independent fact check`, `opening_diversity` → `Opening diversity`, `headline_diversity` → `Headline diversity`, `source_domain_diversity` → `Source domain diversity`. `gateLabel` falls back to the raw id.
13. `useSessionUser` reads `useQuery(sessionQueryOptions).data?.user`. `useCan` is `hasPermission(user, p)`. `useIsAdmin` is `user?.role === 'admin'`.
14. `unlessUnauthorized` returns `false` when `isUnauthorized(error)`, else `interval`. `runsRefetchInterval` returns `ACTIVE_POLL_MS` when any item's status is non-terminal, else `false`, passed through `unlessUnauthorized`. A run that was SUCCEEDED and now reads QUEUED or PRODUCING is non-terminal, so polling restarts on the next fetch (CONTRACT §5.7 Rules A–C, UI note).
15. `runsQueryOptions(limit, status)` fetches `blogPath('runs') + buildQuery({ status, limit })`, so without a status the URL stays `B/runs?limit=<n>` (Phase 1 tests). Its `refetchInterval` is `(query) => runsRefetchInterval(query.state.data, query.state.error)`.
16. `sanitizePreviewHtml(html)` = `DOMPurify.sanitize(html, PREVIEW_SANITIZE_CONFIG)`.
17. `downloadFile` creates `URL.createObjectURL(new Blob([content], { type: mimeType }))`. It appends an `<a>` with that `href` and `download=filename`, calls `click()`, removes the anchor, then calls `URL.revokeObjectURL(url)`.
18. `mockApi`'s optional `fallback` replaces the default `404 Not mocked` response. `bodyOf` returns `JSON.parse(String(init.body))` of the `index`-th call matching method and path. `renderPage` builds `sessionFor(role ?? 'admin', permissions)`, calls `setCsrfToken(session.csrfToken)`, and returns `renderRoutes([{ path, element }], { initialEntries: [url ?? path], session })`. `pageOf` returns `{ items, total: total ?? items.length, limit: limit ?? 20, offset: offset ?? 0 }`.

**Tests to write first.**
- `query-string.test.ts` › `buildQuery`:
  - `returns an empty string for no params`: `buildQuery({}) === ''`.
  - `skips empty values and keeps order`: `buildQuery({ view: 'drafts', status: undefined, pillar: null, q: '', limit: 20, offset: 0 }) === '?view=drafts&limit=20&offset=0'`.
  - `repeats array keys`: `buildQuery({ status: ['READY_FOR_REVIEW', 'APPROVED'] }) === '?status=READY_FOR_REVIEW&status=APPROVED'`.
  - `writes booleans`: `buildQuery({ unreadOnly: true }) === '?unreadOnly=true'`.
  - `percent-encodes values`: `buildQuery({ text: 'a b&c', since: '2026-09-01T00:00:00+05:30' }) === '?text=a%20b%26c&since=2026-09-01T00%3A00%3A00%2B05%3A30'`.
- `query-string.test.ts` › `blogPath` › `encodes each segment`: `blogPath('runs', 'r 1', 'steps', 'produce.fact_check', 'retry') === '/api/blog-agent/runs/r%201/steps/produce.fact_check/retry'`.
- `problems.test.ts`:
  - `reads a title-only problem`: `e = new ApiError(409, { type: 'about:blank', title: 'Version conflict', status: 409 })` gives `problemTitle(e) === 'Version conflict'`, `problemDetail(e) === null` and `describeProblem(e, 'fb') === 'Version conflict'`.
  - `joins title and string detail`: `new ApiError(403, { title: 'Forbidden', status: 403, detail: 'missing permission blog.publish' })` → `'Forbidden: missing permission blog.publish'`.
  - `formats FastAPI validation errors`: detail `[{ type: 'string_too_short', loc: ['body', 'reason'], msg: 'String should have at least 1 character' }]` → `problemDetail === 'body.reason: String should have at least 1 character'`.
  - `formats publish issues`: detail `[{ field: 'excerpt', message: 'too long' }, { field: 'slug', message: 'missing' }]` → `'excerpt: too long; slug: missing'`.
  - `falls back for non-problems`: `describeProblem(new TypeError('x'), 'fb') === 'fb'`; `isUnauthorized(new ApiError(401, {}))` is true; `isProblem(new ApiError(404, { title: 'Fact check not found' }), 404, 'Fact check not found')` is true, and with title `'Article not found'` it is false.
- `format.test.ts`:
  - `formats date-times in a zone`: `formatDateTime('2026-09-17T01:30:00Z', 'Asia/Kolkata') === '2026-09-17 07:00'`; `formatDateTime(null, 'UTC') === '—'`.
  - `formats dates in a zone`: `formatDate('2026-09-17T20:00:00Z', 'Asia/Kolkata') === '2026-09-18'`; `formatDate('2026-09-17', 'UTC') === '2026-09-17'`.
  - `formats money, percentages and scores`: `formatUsd('0.012300') === '$0.0123'`, `formatUsd(null) === '—'`, `formatPercent(0.8234) === '82%'`, `formatShare(0.3333) === '33.3%'`, `formatScore(0.82) === '0.82'`.
  - `formats durations`: `formatMs(950) === '950 ms'`, `formatMs(61500) === '61.5 s'`, `formatSeconds(125.4) === '2m 05s'`, `formatSeconds(null) === '—'`.
  - `humanizes keys`: `humanizeKey('mdcopilotRelevance') === 'Mdcopilot relevance'`, `humanizeKey('business_relevance') === 'Business relevance'`.
- `time.test.ts`:
  - `validates zones`: `isValidTimeZone('Asia/Kolkata')` and `isValidTimeZone('UTC')` are true; `'Mars/Base'` and `''` are false; `isValidTimeZone(localTimeZone())` is true.
  - `converts wall time to an offset timestamp`: `('2026-09-20', '09:30', 'Asia/Kolkata')` → `'2026-09-20T09:30:00+05:30'`; `('2026-03-08', '12:00', 'America/New_York')` → `'2026-03-08T12:00:00-04:00'`; `('2026-01-15', '12:00', 'America/New_York')` → `'2026-01-15T12:00:00-05:00'`; `('2026-09-20', '09:30', 'UTC')` → `'2026-09-20T09:30:00+00:00'`.
  - `computes months`: `monthOf('2026-09-30T20:00:00Z', 'Asia/Kolkata') === '2026-10'`; `shiftMonth('2026-12', 1) === '2027-01'`; `shiftMonth('2026-01', -1) === '2025-12'`.
- `status.test.ts`:
  - `labels and colours statuses`: `ARTICLE_STATUS_LABELS.READY_FOR_REVIEW === 'Ready for review'`; `articleStatusVariant('QUALITY_GATE_FAILED') === 'destructive'`; `('PUBLISHED')` → `'default'`; `('SUPERSEDED')` → `'outline'`; `('DRAFTING')` → `'secondary'`.
  - `lists in-progress and approved-or-later statuses`: exact set equality with rule 10.
  - `applies the action status rules`: a table of all 16 `ArticleStatus` values × each `articleActions` function, with expected booleans exactly as rule 11 (including `canRegenerate('FAILED', 'research') === true` and `canRegenerate('FAILED', 'article') === false`).
  - `labels gates`: `gateLabel('no_unsupported_statistics') === 'No unsupported statistics'`; `gateLabel('made_up') === 'made_up'`; `Object.keys(GATE_LABELS).length === 19`.
- `use-can.test.tsx` › `reads permissions and role from the cached session`: `renderHook` inside a `QueryClientProvider` whose cache holds `sessionFor('editor')` → `useCan('blog.edit')` true, `useCan('blog.approve')` false, `useIsAdmin()` false; with `sessionFor('admin')`, `useIsAdmin()` is true; with an empty cache, `useCan('blog.view')` is false.
- `polling.test.ts`:
  - `polls runs while any run is moving`: `runsRefetchInterval(pageOf([makeRun({ status: 'SUCCEEDED' }), makeRun({ status: 'QUEUED' })]), null) === 3000`; all terminal → `false`; `undefined` → `false`.
  - `treats a SUCCEEDED run that returns to PRODUCING as live again`: `pageOf([makeRun({ id: 'r', status: 'PRODUCING' })])` → `3000`.
  - `stops polling after a 401`: the QUEUED page with `new ApiError(401, {})` → `false`.
- `sanitize.test.ts` › `strips scripts, handlers, styles and non-http links but keeps rel`: the fact-3 probe input gives exactly the fact-3 output string.
- `download.test.ts` › `downloads a blob through a temporary anchor`: spy `URL.createObjectURL` (returns `'blob:test'`), `URL.revokeObjectURL`, and `HTMLAnchorElement.prototype.click` (capturing `this`). After `downloadFile('a.json', '{"x":1}', 'application/json')`: the captured anchor has `download === 'a.json'` and `href` ending in `blob:test`; `await (createObjectURL.mock.calls[0][0] as Blob).text() === '{"x":1}'`; `revokeObjectURL` was called with `'blob:test'`; no `<a>` is left in `document.body`.
- `features/runs/api.test.ts`:
  - `keeps the Phase 1 runs URL without a status`: mock `GET B/runs?limit=10`; `queryClient.fetchQuery(runsQueryOptions(10))` resolves the page.
  - `adds the status filter first`: mock `GET B/runs?status=FAILED&limit=50`; fetch resolves.
  - `stops polling on 401`: call `runsQueryOptions(10).refetchInterval` with `{ state: { data: pageOf([makeRun({ status: 'QUEUED' })]), error: new ApiError(401, {}) } }` → `false`.
- `src/test/fixtures/helpers.test.tsx`:
  - `mockApi uses the fallback for unmocked routes`: `mockApi({}, () => problemResponse(500, 'Boom'))`; `(await fetch('/x')).status === 500`.
  - `bodyOf parses the JSON body of the matching call`: two `POST /p` calls with `{a:1}` and `{a:2}` → `bodyOf(mock, 'POST', '/p', 1)` equals `{ a: 2 }`.
  - `renderPage renders at its path and stores the CSRF token`: `renderPage(<h1>Hi</h1>, { path: '/p', role: 'editor' })` → heading `Hi` found; `getCsrfToken() === 'csrf-editor'`.

**Implementation notes.**
- `zonedWallTimeToIso` offset parser: `const part = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'longOffset' }).formatToParts(new Date(t)).find((p) => p.type === 'timeZoneName')!.value` → `'GMT'` or `'GMT+05:30'` (fact 8). The sign and `HH:MM` are parsed with `/^GMT(?:([+-])(\d{2}):(\d{2}))?$/`.
- `runs/api.ts` keeps every Phase 1 export name.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/shared src/features/runs src/test/fixtures/helpers.test.tsx` → red, then green with every listed test passing. `npm test` (existing Phase 1/FOUND tests still green), `npm run lint`, `npm run typecheck` → exit 0.

**Acceptance covered.** §5.7 Rules A–C UI polling note; §10.5 XSS (DOMPurify config); O4 partial (polling stops on 401).

### UI-2: Wire types and fixture builders (shape-checked)

**Files.** Create `src/features/shared/types.ts` (UI-1 created its first four unions) and `src/features/runs/types.ts`. Create `types.ts` in each of `src/features/{research,sources,topics,articles,quality,publishing,calendar,settings,agent-runs,metrics,dashboard,notifications}/`. Create `src/test/fixtures/{common,runs,research,sources,topics,articles,quality,publishing,calendar,settings,agent-runs,metrics,dashboard,notifications}.ts`, `src/test/fixtures/index.ts` and `src/test/fixtures/shapes.test.ts`.

**Interfaces produced.** One exported TS type per wire model, one builder `make<Model>(overrides?: Partial<Model>): Model` per type, and `BUILDERS: Record<string, () => object>` keyed by model name.

| File | Types |
|---|---|
| `shared/types.ts` | unions: `ArticleStatus`, `PillarKey`, `SourceType`, `ClaimType`, `VerificationStatus`, `ClaimKind`, `NoveltyDecision`, `CandidateStatus`, `ResearchRunKind`, `ResearchRunStatus`, `AccessMode`, `DateSource`, `FetchStatus`, `DiscoveredVia`, `FeedKind`, `ReviewKind`, `ReviewVerdict`, `GateRunKind`, `GateId`, `ChangeKind`, `SectionKey`, `ArticleComponent`, `TitleKey`, `ApprovalMode`, `PublisherKey`, `PublicationStatus`, `SlotStatus`, `NotificationKind`, `HeadlinePattern`, `ClinicalFlagCode`, `AttemptStatus`, `StepStatus`, `CallKind`, `CallStatus`, `AgentName`. Models: `ActionAccepted`, `ArticleStateOut`, `SourceRefOut`, `ReasonRequest`, `NewsRef`, `ScoreItem`, `NoveltyNeighbour`, `NoveltyResult`, `TitleOptions`, `InternalLink`, `SEOMetadata`, `SocialCopy`, `BlogSource`, `ClaimCheck`, `FactCheckResult`, `ClinicalFlag`, `ClinicalReview`, `Change`, `EditorialReview`, `GateResult`, `GateReport`, `SourceRef`, `PacketFact`, `PacketStatistic`, `ResearchPacket`, `ArticleSection`, `FindingResolution`, `HumanDecision`. Also the constant `SECTION_ORDER: readonly SectionKey[]` |
| `runs/types.ts` | `ManualRunRequest`, `AttemptOut`, `StepOut`, `RunDetail` (v2). `RunOut`/`Page`/`RunStatus`/`RunKind` stay in `runs/api.ts` |
| `research/types.ts` | `ResearchQueryOut`, `ResearchRunOut`, `FindingOut`, `ResearchRunDetail` |
| `sources/types.ts` | `LedgerSourceOut`, `SourceFeedOut`, `SourceFeedUpdate`, `SourceDomainOut`, `SourceDomainUpdate`, `ThemeOut`, `ThemeIn`, `ThemesUpdate` |
| `topics/types.ts` | `TopicCandidateOut`, `TopicRoundOut`, `TopicsGenerateRequest`, `TopicSelectRequest`, `TopicUpdate`, `TopicHistoryOut`, `ExternalPostOut`, `SimilarityOut`, `PillarCountOut`, `DomainShareOut`, `PhraseCountOut`, `DiversityPanelOut` |
| `articles/types.ts` | `ArticleListView` (`'drafts' \| 'review' \| 'published' \| 'all'`), `GateBadgeOut`, `ArticleSummaryOut`, `ArticleDetailOut`, `SeoEdit`, `ArticleEditRequest`, `VersionSummaryOut`, `VersionDetailOut`, `FieldChangeOut`, `VersionDiffOut`, `RegenerateRequest`, `SelectTitleRequest`, `ArticleSourceOut`, `ResearchPacketOut` |
| `quality/types.ts` | `ClaimCheckOut`, `FactCheckOut`, `ReviewOut`, `QualityGatesOut`, `ApproveRequest` |
| `publishing/types.ts` | `IssueOut`, `PreviewOut`, `ExportBundleOut`, `ConfirmPublishedRequest`, `PublishRequest`, `ScheduleRequest`, `PublicationOut` |
| `calendar/types.ts` | `CalendarEntryKind`, `CalendarEntryOut`, `CalendarDayOut`, `CalendarMonthOut`, `CalendarSlotUpdate` |
| `settings/types.ts` | `ProviderKeyView`, `WordCountRange`, `ScheduleConfig`, `ScoreWeights`, `NoveltyConfig`, `DiversityConfig`, `ResearchConfig`, `EffectiveConfig`, `SettingsValues`, `BrandProfileValues`, `SettingsOut`, `SettingsUpdate`, `BrandProfileOut`, `BrandProfileUpdate`, `PillarOut`, `PillarIn`, `PillarsUpdate`, `PriceOverrideOut`, `PriceOverrideCreate`, `UserOut`, `UserCreate`, `UserUpdate` |
| `agent-runs/types.ts` | `AgentRunOut`, `LlmCallOut`, `AgentRunDetailOut` |
| `metrics/types.ts` | `CostGroupBy`, `CostRowOut`, `CostReportOut`, `LatencyRowOut`, `LatencyReportOut` |
| `dashboard/types.ts` | `RecommendedTopicOut`, `QualitySummaryOut`, `TodayCardOut`, `PipelineStageOut`, `PipelineTrackerOut`, `DashboardMetricsOut`, `DashboardOut` |
| `notifications/types.ts` | `NotificationOut` |

**Behaviour rules (type derivation, from CONTRACT §4, §5.1, §5.2, §5.4 and Phase 1 `api/schemas.py`/`domain/contracts.py`).**
1. The field name is Pydantic `to_camel(snake_name)` (`why_now` → `whyNow`, `x_post` → `xPost`, `p50_ms` → `p50Ms`, `per_1k_calls` → `per1kCalls`, `headline_pattern_max_7d` → `headlinePatternMax7d`). Aliased fields use the wire name: `FieldChangeOut.from`/`to`, `CostReportOut.from`/`to`.
2. `X | None` becomes `X | null`, and the key is still required. `uuid`, `datetime`, `date` and `Decimal` become `string`. `int`/`float` become `number`. `dict[str, T]` becomes `Record<string, T>`, and `dict[str, Any]` becomes `Record<string, unknown>`. `list[T]` becomes `T[]`. A `Literal`/enum becomes a string-literal union of its values.
3. Response types have every key required. A request model field with a Pydantic default is optional (`?:`) in the TS type, but its builder still sets every key.
4. Enum values are exactly CONTRACT §5.1 and the Phase 1 enums: `SourceType`, `ClaimType`, `VerificationStatus`, `ClaimKind`, `NoveltyDecision`, `PillarKey`, `AttemptStatus`, `StepStatus`, `CallKind`, `CallStatus`, `AgentName` (without `hello`), `PublicationStatus`. `GateId` holds the 19 values of the §5.2 gate table. `GateResult.gate` is typed `string` (the Phase 1 contract field is `str`) and shown through `gateLabel`.
5. `SECTION_ORDER` = `['introduction','context','core_argument','evidence','mdcopilot_perspective','practical_implications','conclusion']`.
6. Builders return fresh objects, nest other builders, and apply `overrides` with a shallow spread. They are `.ts` files, so the react-refresh rule does not apply.
7. `BUILDERS` has one entry per exported type that also appears as a key in `api-shapes.json` (a union or a UI-only type such as `ArticleListView` has no builder). `UNUSED_BY_UI: readonly string[]` in `fixtures/index.ts` lists every `api-shapes.json` key that no UI type mirrors, each with a one-line comment giving the reason. The implementer fills it from the frozen file; the expected content is empty.

**Builder defaults tests rely on** (every other field: any value valid for its type).

| Builder | Defaults used by tests |
|---|---|
| `ARTICLE_MARKDOWN` (const, `fixtures/common.ts`) | `Specialist access is a scheduling problem [S1].` then six sections `## Context`, `## The core argument`, `## Evidence`, `## The MDCopilot perspective`, `## Practical implications`, `## Conclusion`, each one sentence ending with `[S1]`, `[S2]` or `[S3]`, and exactly one trailing `\n` |
| `makeTitleOptions` | `provocative: 'Why specialist access cannot wait'`, `operational: 'How clinics can widen specialist access'`, `visionary: 'The specialist clinic of the next decade'` |
| `makeSourceRefOut` | `id: 'source-1'`, `marker: 'S1'`, `title: 'CMS finalises prior authorization rule'`, `url: 'https://www.cms.gov/newsroom/prior-auth'`, `publisher: 'CMS'`, `domain: 'cms.gov'`, `tier: 1`, `publishedAt: '2026-09-15T00:00:00Z'`, `accessMode: 'full_text'` |
| `makeActionAccepted` | `workflowId: 'wf-1'`, `workflowName: 'regenerate_component'`, `queue: 'interactive'`, `runId: 'run-1'`, `articleId: 'article-1'`, `candidateId: null` |
| `makeArticleStateOut` | `id: 'article-1'`, `status: 'APPROVED'`, `currentVersionId: 'version-2'`, `approvedVersionId: 'version-2'`, `approvalMode: 'draft'`, `updatedAt: '2026-09-17T02:00:00Z'` |
| `makeArticleDetailOut` | `id: 'article-1'`, `runId: 'run-1'`, `runDate: '2026-09-17'`, `candidateId: 'candidate-1'`, `titleOptions: makeTitleOptions()`, `selectedTitle: 'How clinics can widen specialist access'`, `selectedTitleKey: 'operational'`, `slug: 'widen-specialist-access'`, `contentMarkdown: ARTICLE_MARKDOWN`, `pullQuote: 'Access is a design choice.'`, `cta: 'See how MDCopilot supports specialists.'`, `excerpt: 'A practical look at widening specialist access.'`, `category: 'Specialist Access'`, `tags: ['specialist access']`, `pillar: 'A'`, `seo: makeSEOMetadata()`, `social: makeSocialCopy()`, `status: 'READY_FOR_REVIEW'`, `pipelineStatus: 'SUCCEEDED'`, `versionNo: 2`, `currentVersionId: 'version-2'`, `approvedVersionId: null`, `recheckRequired: false`, `gatesPassedOnCurrentVersion: true`, `approvalMode: null`, `createdAt: '2026-09-17T01:30:00Z'`, `updatedAt: '2026-09-17T01:45:00Z'` |
| `makeSEOMetadata` | `seoTitle: 'Widening specialist access'`, `slug: 'widen-specialist-access'`, `primaryKeyword: 'specialist access'`, `secondaryKeywords: ['referral bottlenecks']`, `tags: ['specialist access']`, `category: 'Specialist Access'` |
| `makeEditorialReview` | `editorialScore: 0.82`, `requiredChanges: []`, `optionalChanges: [makeChange()]`, `weaknesses: ['Long conclusion']` |
| `makeChange` | `id: 'change-1'`, `description: 'Tighten the introduction.'`, `location: 'introduction'` |
| `makeGateReport` | `passed: true`, `results: [{ gate: 'word_count', passed: true, severity: 'blocking', details: 'Body has 980 words (850–1150).' }, { gate: 'opening_diversity', passed: true, severity: 'warning', details: 'Opening is distinct.' }]` |
| `makeNoveltyResult` | `decision: 'PASS'`, `maxSimilarity: 0.62`, `neighbours: [{ kind: 'external_post', refId: 'post-1', title: 'Prior auth, explained', similarity: 0.62 }]` |
| `makeArticleSummaryOut` | `id: 'article-1'`, `title: 'How clinics can widen specialist access'`, `status: 'READY_FOR_REVIEW'`, `pillar: 'A'`, `currentVersionNo: 2`, `wordCount: 980`, `gateBadge: { passed: true, failedGates: [], recheckRequired: false }`, `factCheckVerdict: 'PASS'`, `editorialScore: 0.82` |
| `makeVersionSummaryOut` | `id: 'version-2'`, `versionNo: 2`, `parentVersionId: 'version-1'`, `changeKind: 'revision'`, `wordCount: 980`, `createdByKind: 'agent'`, `factCheckVerdict: 'PASS'`, `gatesPassed: true` |
| `makeVersionDiffOut` | `fromVersionId: 'version-1'`, `toVersionId: 'version-2'`, `fromVersionNo: 1`, `toVersionNo: 2`, `unifiedDiff: '--- v1\n+++ v2\n@@ -1,3 +1,3 @@\n Specialist access is a scheduling problem [S1].\n-Old line\n+New line'`, `fieldChanges: [{ field: 'cta', from: 'Book a demo today', to: 'Book a call today' }]` |
| `makeFactCheckOut` | `reviewId: 'review-fc-1'`, `versionId: 'version-2'`, `versionNo: 2`, `verdict: 'PASS'`, `independentCheck: true`, `writerProvider: 'openai'`, `checkerProvider: 'google'`, `claims: [makeClaimCheckOut()]` |
| `makeClaimCheckOut` | `id: 'claim-1'`, `claim: 'CMS finalised the rule this week.'`, `kind: 'regulatory'`, `importance: 'high'`, `sectionKey: 'context'`, `sentenceIndex: 0`, `span: 'CMS finalised the rule this week'`, `citationMarkers: ['S1']`, `verificationStatus: 'SUPPORTED'`, `confidence: 0.9`, `recommendedRevision: null`, `verificationSources: [makeSourceRefOut()]` |
| `makeQualityGatesOut` | `reviewId: 'review-gate-1'`, `versionNo: 2`, `runKind: 'full'`, `passed: true`, `report: makeGateReport()`, `recheckRequired: false` |
| `makeExportBundleOut` | `publicationId: 'publication-1'`, `articleId: 'article-1'`, `versionId: 'version-2'`, `title: 'How clinics can widen specialist access'`, `slug: 'widen-specialist-access'`, `excerpt: 'A practical look at widening specialist access.'`, `html: '<p>Specialist access is a scheduling problem.</p>'`, `text: 'Specialist access is a scheduling problem.'`, `status: 'EXPORTED'` |
| `makePreviewOut` | `versionId: 'version-2'`, `html: '<h2>Context</h2><p>CMS finalised the rule this week.</p>'`, `issues: []` |
| `makePublicationOut` | `id: 'publication-1'`, `publisher: 'manual_export'`, `target: 'manual'`, `status: 'EXPORTED'`, `attempts: 1`, `lastError: null` |
| `makeTopicCandidateOut` | `id: 'candidate-1'`, `runId: 'run-1'`, `round: 1`, `position: 0`, `title: 'How clinics can widen specialist access'`, `whyNow: 'CMS finalised the prior authorization rule this week.'`, `mdcopilotConnection: 'Digital twins extend specialist reach.'`, `pillar: 'A'`, `totalScore: 0.79`, `scoreBreakdown: { timeliness: { weight: 0.25, score: 0.8, justification: 'Rule finalised this week.' } }`, `novelty: makeNoveltyResult()`, `sources: [makeSourceRefOut()]`, `relevantNews: [{ title: 'CMS finalises prior authorization rule', url: 'https://www.cms.gov/newsroom/prior-auth', publishedAt: '2026-09-15T00:00:00Z' }]`, `status: 'PASSED'`, `articleId: null` |
| `makeTopicRoundOut` | `runId: 'run-1'`, `runStatus: 'WAITING_FOR_TOPIC'`, `round: 1`, `roundsAvailable: [1]`, `shortfall: false`, `items`: `candidate-1` (defaults), `candidate-2` (`position: 1`, `title: 'Prior auth, explained again'`, `status: 'WARNED'`, novelty `{ decision: 'WARN', maxSimilarity: 0.91, neighbours: [{ kind: 'article', refId: 'article-0', title: 'Prior auth, explained', similarity: 0.91 }] }`), `candidate-3` (`position: 2`, `title: 'AI in the clinic', status: 'REJECTED'`, novelty `REJECT_TOPIC` 0.97) |
| `makeResearchRunOut` / `makeResearchRunDetail` | `id: 'research-run-1'`, `runId: 'run-1'`, `articleId: null`, `kind: 'broad'`, `status: 'succeeded'`, `windowDays: 7`, `themesCovered: ['prior_authorization']`, `phaseLatencyMs: { search: 1200, retrieval: 3400, extraction: 800, llm: 5100, total: 10500 }`, `counts: { sourcesTotal: 6, findings: 4 }`, `sourceCount: 6`, `findingCount: 4`, `startedAt: '2026-09-17T01:31:00Z'`; detail adds `queries: [{ text: 'prior authorization rule', themeKey: 'prior_authorization', status: 'ok', searchActions: 1, sourceCount: 3, error: null }, { text: 'specialist wait times', themeKey: null, status: 'failed', searchActions: 0, sourceCount: 0, error: 'HTTP 503' }]`, `findings: [{ id: 'finding-1', position: 0, claim: 'CMS finalised the rule.', claimType: 'FACT', confidence: 0.85, importance: 'high', sources: [makeSourceRefOut()] … }]`, `sources: [makeLedgerSourceOut()]` |
| `makeDashboardOut` | `timezone: 'Asia/Kolkata'`, `today`: `date: '2026-09-17'`, `runId: 'run-1'`, `runStatus: 'SUCCEEDED'`, `researchStatus: 'done'`, `opportunitiesDiscovered: 3`, `recommendedTopic: { candidateId: 'candidate-1', title: 'How clinics can widen specialist access', whyNow: 'CMS finalised the prior authorization rule this week.', pillar: 'A', evidenceScore: 0.7, businessRelevance: 0.9, noveltyScore: 0.8, totalScore: 0.79 }`, `articleId: 'article-1'`, `articleStatus: 'READY_FOR_REVIEW'`, `headlineOptions: makeTitleOptions()`, `quality: { factCheckVerdict: 'PASS', sourceCount: 6, tierMix: { tier1: 3, tier2: 2, tier3: 1 }, noveltyPercent: 87, clinicalClear: true, editorialScore: 0.82, seoComplete: true, gatesPassed: true }`; `pipeline.stages`: `discover.gather_signals` (`Gather signals`, `done`) and `produce.write_draft` (`Write draft`, `running`); `metrics`: `postsGenerated: 12`, `postsPublished: 4`, `postsPending: 3`, `topicsGenerated: 36`, `researchSources: 210`, `avgGenerationSeconds: 125.4`, `avgEditorialScore: 0.8`, `duplicateTopicRate: 0.1`, `factCheckPassRate: 0.9`, `costTodayUsd: '1.234500'`, `costWeekUsd: '5.000000'`, `costMonthUsd: '20.000000'` |
| `makeDiversityPanelOut` | `days: 30`, `pillarMix: [{ pillar: 'A', count: 4 }]`, `sourceDomainConcentration: [{ domain: 'statnews.com', count: 3, share: 0.3333 }]`, `topRepeatedPhrases: [{ phrase: 'specialist access', count: 5 }]` |
| `makeCostReportOut` | `groupBy: 'day'`, `totalUsd: '1.500000'`, `rows: [{ key: '2026-09-16', label: '2026-09-16', costUsd: '1.000000', calls: 10, inputTokens: 1000, outputTokens: 200, searchActions: 3 }, { key: '2026-09-17', label: '2026-09-17', costUsd: '0.500000', calls: 5, inputTokens: 500, outputTokens: 100, searchActions: 1 }]` |
| `makeCalendarMonthOut` | `month: '2026-09'`, `timezone: 'Asia/Kolkata'`, `days`: all 30 September days with `plannedPillar` from the seed rotation, `slotId: null`, `slotStatus: null`, `isOverride: false`, `note: null`, `entries: []`; except `2026-09-15`: `entries: [{ kind: 'published', articleId: 'article-9', runId: 'run-9', researchRunId: null, title: 'Scarcity', status: 'PUBLISHED', at: '2026-09-15T04:00:00Z', pillar: 'B' }]`; and `2026-09-20`: `entries: [{ kind: 'scheduled', articleId: 'article-1', runId: 'run-1', researchRunId: null, title: 'Access', status: 'SCHEDULED', at: '2026-09-20T04:00:00Z', pillar: 'A' }]` |
| `makeSettingsOut` | `version: 3`, `publishingEnabled: false`, `humanApprovalRequired: true`, `autoPublishAvailable: false`, `providers: { openai: { configured: true, preview: 'sk-…abcd' }, gemini: { configured: false, preview: null }, anthropic: { configured: false, preview: null }, ncbi: { configured: false, preview: null }, openaiAdmin: { configured: false, preview: null } }`, `effective`: `schedule: { time: '07:00', timezone: 'Asia/Kolkata' }`, `topicSelectionMode: 'auto'`, `wordCount: { min: 850, max: 1150 }`, `publisher: 'manual_export'`, `routes: { search: ['openai:gpt-s'], research: ['google:gem-r'], ideation: ['google:gem-i'], deep_research: ['openai:gpt-d'], writer: ['openai:gpt-w'], fact_check: ['google:gem-f', 'openai:gpt-f'], clinical: ['google:gem-c'], editorial: ['google:gem-e'], seo: ['google:gem-s'] }`, `promptVersions: {}`, `scoreWeights` = the §5.4 defaults, `research.windowDays: 7`, `research.minSourceCount: 5`, `novelty.topicThreshold: 0.85`, `gateOverridePolicy: 'admin_with_reason'`, `defaultCategory: 'Healthcare AI'`, `siteUrl: 'https://www.mdcopilot.health'`; `values` = every `SettingsValues` key `null` |
| `makeBrandProfileOut` | `version: 2`, `values` = the seed `brand_profile.yaml` in camelCase |
| `makePillarOut` / `PILLARS` (const) | the six seed pillars: A `weekdays: [0]` … E `[4]`, NARRATIVE `[5, 6]`, all `isActive: true`, `sortOrder` 0–5, ids `pillar-A` … `pillar-NARRATIVE` |
| `makeRunDetail` | `id: 'run-done'`, `status: 'FAILED'`, `attempts: [{ id: 'attempt-1', dbosWorkflowId: 'manual-run-done', workflowName: 'discover_topics', attemptNo: 1, status: 'FAILED' … }]`, `steps: [{ id: 'step-1', stepName: 'produce.write_draft', status: 'SUCCEEDED' … }, { id: 'step-2', stepName: 'produce.fact_check', status: 'FAILED', error: { message: 'Fact checker timed out' } … }]`, `error: { message: 'Fact checker timed out' }`, `articleIds: ['article-1']`, `researchRunIds: ['research-run-1']` |
| `makeAgentRunOut` / `makeAgentRunDetailOut` | `id: 'agent-run-1'`, `runId: 'run-done'`, `stepName: 'produce.write_draft'`, `agentName: 'writer'`, `model: 'openai:gpt-w'`, `status: 'SUCCEEDED'`, `costUsd: '0.120000'`; detail `llmCalls: [{ id: 'llm-call-1', kind: 'agent', providerServed: 'openai', modelServed: 'gpt-w-2026', fallbackFrom: null, status: 'ok', costUsd: '0.120000', priceVersion: 'genai-prices==0.1.7' … }]` |
| `makeLatencyReportOut` | `days: 30`, `rows: [{ stepName: 'produce.write_draft', count: 5, p50Ms: 12000, p90Ms: 18000 }]` |
| `makeNotificationOut` | `id: 'notification-1'`, `kind: 'ready_for_review'`, `title: 'Article ready for review'`, `body: 'How clinics can widen specialist access'`, `link: '/articles/article-1'`, `readAt: null` |
| `makeSourceFeedOut` | `id: 'feed-1'`, `name: 'STAT News'`, `group: 'trade_press'`, `tier: 2`, `isEnabled: true`, `consecutiveFailures: 0`, `lastSuccessAt: '2026-09-17T01:00:00Z'`, `lastError: null`, `disabledReason: null` |
| `makeSourceDomainOut` | `id: 'domain-1'`, `domain: 'cms.gov'`, `tier: 1`, `fetchPolicy: 'fetch'`, `verificationAllowlisted: true` |
| `makeThemeOut` | `id: 'theme-1'`, `key: 'prior_authorization'`, `name: 'Prior authorization'`, `queryTemplates: ['prior authorization {year}']`, `pillarKeys: ['C']`, `isActive: true`, `sortOrder: 0` |
| `makeUserOut` | `id: 'user-2'`, `email: 'editor@example.com'`, `displayName: 'Editor'`, `role: 'editor'`, `isActive: true` |
| `makePriceOverrideOut` | `id: 'override-1'`, `provider: 'openai'`, `sku: 'web_search_call'`, `per1kCalls: '10.000000'`, `effectiveFrom: '2026-09-01T00:00:00Z'`, `priceVersion: 'ovr:0123456789ab'` |

**Tests to write first** (`src/test/fixtures/shapes.test.ts`, `import shapes from '@/test/api-shapes.json'`):
- `it.each(Object.entries(BUILDERS))('%s builder has exactly the wire properties', …)`: `Object.keys(builder()).sort()` equals `[...shapes[name].props].sort()`.
- `it('classifies every model in the shape file')`: `Object.keys(shapes).sort()` equals `[...Object.keys(BUILDERS), ...UNUSED_BY_UI].sort()`.
- `it('builds a golden-shaped article')`: `makeArticleDetailOut().contentMarkdown` matches `/^(?:.*\n)*?## /` and has exactly 6 lines starting with `## `; `SECTION_ORDER.length === 7`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/test/fixtures` → red (builders missing) → green. `npm run typecheck` exits 0; this is the only check that types and builders agree on nullability, so review `types.ts` against CONTRACT §4 field by field.

**Acceptance covered.** CONTRACT D8 and §8.3 (UI side of the shape check).

### UI-3: API modules and invalidation

**Files.** Replace the FOUND stubs `src/features/{dashboard,topics,research,articles,quality,publishing,calendar,sources,settings,agent-runs,metrics,notifications}/api.ts`. Modify `src/features/runs/api.ts`. Create `src/features/shared/invalidation.ts`, and an `api.test.ts` in every module above plus `src/features/shared/invalidation.test.ts`.

**Interfaces produced.** Every `*QueryOptions` returns `queryOptions({ queryKey, queryFn, refetchInterval? })`. Every mutation function returns `Promise<T>` from `apiFetch`. The URLs follow; `q(...)` is `buildQuery` with keys in the order shown, and `P(...)` is `blogPath`.

| Module | Export | Method and URL | Body | Returns | Key / polling |
|---|---|---|---|---|---|
| runs | `runDetailQueryOptions(runId)` | GET `P('runs', runId)` | — | `RunDetail` | `['runs','detail',runId]`; `ACTIVE_POLL_MS` while status non-terminal, `unlessUnauthorized` |
| runs | `createRun(body: ManualRunRequest \| Record<string, never> = {})` | POST `P('runs')` | `body` | `RunOut` | — |
| runs | `restartRun(runId)` / `resumeRun(runId)` | POST `P('runs', runId, 'restart' \| 'resume')` | none | `RunOut` | — |
| runs | `retryStep(runId, step)` / `restartFromStep(runId, step)` | POST `P('runs', runId, 'steps', step, 'retry' \| 'restart')` | none | `RunOut` | — |
| research | `researchRunsQueryOptions({ runId?, articleId?, kind?, limit = 20, offset = 0 })` | GET `P('research-runs') + q({runId, articleId, kind, limit, offset})` | — | `Page<ResearchRunOut>` | `['research-runs','list',params]` |
| research | `researchRunQueryOptions(id)` | GET `P('research-runs', id)` | — | `ResearchRunDetail` | `['research-runs','detail',id]`; poll while `status === 'running'` |
| sources | `ledgerQueryOptions({ domain?, tier?, accessMode?, q?, since?, limit = 20, offset = 0 })` | GET `P('sources') + q({domain, tier, accessMode, q, since, limit, offset})` | — | `Page<LedgerSourceOut>` | `['sources','ledger',params]` |
| sources | `feedsQueryOptions()`, `updateFeed(id, body)` | GET `P('sources','feeds')`; PATCH `P('sources','feeds',id)` | `SourceFeedUpdate` (changed keys only) | `SourceFeedOut[]` / `SourceFeedOut` | `['sources','feeds']` |
| sources | `domainsQueryOptions()`, `updateDomain(id, body)` | GET `P('sources','domains')`; PATCH `P('sources','domains',id)` | `SourceDomainUpdate` (changed keys only) | `SourceDomainOut[]` / `SourceDomainOut` | `['sources','domains']` |
| sources | `themesQueryOptions()`, `saveThemes(body)` | GET `P('themes')`; PUT `P('themes')` | `ThemesUpdate` | `ThemeOut[]` | `['sources','themes']` |
| topics | `topicRoundQueryOptions({ runId?, round?, status? })` | GET `P('topics') + q({runId, round, status})` | — | `TopicRoundOut` | `['topics','round',params]`; poll while `runStatus` ∈ QUEUED, RESEARCHING, TOPICS_READY |
| topics | `generateTopics(runId)` | POST `P('topics','generate')` | `{ runId }` | `ActionAccepted` | — |
| topics | `selectTopic(candidateId, confirmWarning)` | POST `P('topics', candidateId, 'select')` | `{ confirmWarning }` | `ActionAccepted` | — |
| topics | `updateTopic(candidateId, body)` | PATCH `P('topics', candidateId)` | `TopicUpdate` (changed keys only) | `TopicCandidateOut` | — |
| topics | `rejectTopic(candidateId, reason)` | POST `P('topics', candidateId, 'reject')` | `{ reason }` | `TopicCandidateOut` | — |
| topics | `topicHistoryQueryOptions({ q?, limit = 20, offset = 0 })` | GET `P('topics','history') + q({q, limit, offset})` | — | `Page<TopicHistoryOut>` | `['topics','history',params]` |
| topics | `externalPostsQueryOptions({ limit = 20, offset = 0 })` | GET `P('topics','external-posts') + q({limit, offset})` | — | `Page<ExternalPostOut>` | `['topics','external-posts',params]` |
| topics | `similarTopicsQueryOptions(text, limit = 5)` | GET `P('topics','similar') + q({text, limit})` | — | `SimilarityOut` | `['topics','similar',text,limit]`; `enabled: text.trim().length >= 3` |
| topics | `diversityQueryOptions(days = 30)` | GET `P('topics','diversity') + q({days})` | — | `DiversityPanelOut` | `['topics','diversity',days]` |
| articles | `articlesQueryOptions({ view?, status?, pillar?, q?, limit = 20, offset = 0 })` | GET `P('articles') + q({view, status, pillar, q, limit, offset})` | — | `Page<ArticleSummaryOut>` | `['articles','list',params]` |
| articles | `articleQueryOptions(id, refetchInterval?)` | GET `P('articles', id)` | — | `ArticleDetailOut` | `['articles',id,'detail']`; the caller passes the interval function (UI-12) |
| articles | `saveArticle(id, body)` | PATCH `P('articles', id)` | `ArticleEditRequest` | `ArticleDetailOut` | — |
| articles | `versionsQueryOptions(id)` | GET `P('articles', id, 'versions')` | — | `VersionSummaryOut[]` | `['articles',id,'versions']` |
| articles | `versionQueryOptions(id, versionId)` | GET `P('articles', id, 'versions', versionId)` | — | `VersionDetailOut` | `['articles',id,'versions',versionId]` |
| articles | `diffQueryOptions(id, from, to)` | GET `P('articles', id, 'diff') + q({from, to})` | — | `VersionDiffOut` | `['articles',id,'diff',from,to]` |
| articles | `regenerateArticle(id, body)` | POST `P('articles', id, 'regenerate')` | `RegenerateRequest` (all three keys; unused ones `null`) | `ActionAccepted` | — |
| articles | `selectTitle(id, body)` | POST `P('articles', id, 'select-title')` | `{ key, customTitle }` (the unused one `null`) | `ArticleDetailOut` | — |
| articles | `articleSourcesQueryOptions(id, versionId?)` | GET `P('articles', id, 'sources') + q({versionId})` | — | `ArticleSourceOut[]` | `['articles',id,'sources',versionId ?? 'current']` |
| articles | `researchPacketsQueryOptions(id)` | GET `P('articles', id, 'research-packets')` | — | `ResearchPacketOut[]` | `['articles',id,'research-packets']` |
| quality | `factCheckQueryOptions(id, versionId?)` | GET `P('articles', id, 'fact-check') + q({versionId})` | — | `FactCheckOut` | `['articles',id,'fact-check',versionId ?? 'current']` |
| quality | `reviewsQueryOptions(id, { versionId?, kind? })` | GET `P('articles', id, 'reviews') + q({versionId, kind})` | — | `ReviewOut[]` | `['articles',id,'reviews',params]` |
| quality | `qualityGatesQueryOptions(id, versionId?)` | GET `P('articles', id, 'quality-gates') + q({versionId})` | — | `QualityGatesOut` | `['articles',id,'quality-gates',versionId ?? 'current']` |
| quality | `recheckArticle(id)` | POST `P('articles', id, 'recheck')` | none | `ActionAccepted` | — |
| quality | `approveArticle(id, body)` | POST `P('articles', id, 'approve')` | `ApproveRequest` | `ArticleStateOut` | — |
| quality | `rejectArticle(id, reason)` | POST `P('articles', id, 'reject')` | `{ reason }` | `ArticleStateOut` | — |
| publishing | `previewQueryOptions(id, versionId?)` | GET `P('articles', id, 'preview') + q({versionId})` | — | `PreviewOut` | `['articles',id,'preview',versionId ?? 'current']` |
| publishing | `exportArticle(id)` | POST `P('articles', id, 'export')` | none | `ExportBundleOut` | — |
| publishing | `confirmPublished(id, url)` | POST `P('articles', id, 'confirm-published')` | `{ url }` | `ArticleStateOut` | — |
| publishing | `publishArticle(id, asDraft)` | POST `P('articles', id, 'publish')` | `{ asDraft }` | `ActionAccepted` | — |
| publishing | `scheduleArticle(id, at)` / `unscheduleArticle(id)` | POST `P('articles', id, 'schedule')` / `…'unschedule'` | `{ at }` / none | `ArticleStateOut` | — |
| publishing | `publicationsQueryOptions(id)` | GET `P('articles', id, 'publications')` | — | `PublicationOut[]` | `['articles',id,'publications']` |
| calendar | `calendarQueryOptions(month)` | GET `P('calendar') + q({month})` | — | `CalendarMonthOut` | `['calendar',month]` |
| calendar | `updateSlot(date, body)` | PATCH `P('calendar','slots',date)` | `CalendarSlotUpdate` (changed keys only) | `CalendarDayOut` | — |
| settings | `settingsQueryOptions()`, `saveSettings(body)` | GET / PUT `P('settings')` | `SettingsUpdate` | `SettingsOut` | `['settings']` |
| settings | `brandQueryOptions()`, `saveBrand(body)` | GET / PUT `P('settings','brand')` | `BrandProfileUpdate` | `BrandProfileOut` | `['settings','brand']` |
| settings | `pillarsQueryOptions()`, `savePillars(body)` | GET / PUT `P('pillars')` | `PillarsUpdate` | `PillarOut[]` | `['pillars']` |
| settings | `priceOverridesQueryOptions()`, `createPriceOverride(body)` | GET / POST `P('settings','price-overrides')` | `PriceOverrideCreate` | `PriceOverrideOut[]` / `PriceOverrideOut` | `['settings','price-overrides']` |
| settings | `usersQueryOptions()`, `createUser(body)`, `updateUser(id, body)` | GET / POST `/api/admin/users`; PATCH `/api/admin/users/{encodeURIComponent(id)}` | `UserCreate` / `UserUpdate` (changed keys only) | `UserOut[]` / `UserOut` | `['users']` |
| agent-runs | `agentRunsQueryOptions({ runId?, status?, agentName?, limit = 50, offset = 0 })` | GET `P('agent-runs') + q({runId, status, agentName, limit, offset})` | — | `Page<AgentRunOut>` | `['agent-runs','list',params]` |
| agent-runs | `agentRunQueryOptions(id)` | GET `P('agent-runs', id)` | — | `AgentRunDetailOut` | `['agent-runs','detail',id]` |
| metrics | `costsQueryOptions({ groupBy, from?, to?, articleId?, runId? })` | GET `P('metrics','costs') + q({groupBy, from, to, articleId, runId})` | — | `CostReportOut` | `['metrics','costs',params]` |
| metrics | `latencyQueryOptions(days = 30)` | GET `P('metrics','latency') + q({days})` | — | `LatencyReportOut` | `['metrics','latency',days]` |
| dashboard | `dashboardQueryOptions()` | GET `P('metrics','dashboard')` | — | `DashboardOut` | `['dashboard']`; `dashboardRefetchInterval` |
| dashboard | `dashboardRefetchInterval(data?: DashboardOut, error?: unknown)` | — | — | `number \| false` | — |
| notifications | `notificationsQueryOptions({ unreadOnly = true, limit = 10 })` | GET `P('notifications') + q({unreadOnly, limit})` | — | `Page<NotificationOut>` | `['notifications',params]`; `unlessUnauthorized(error, NOTIFICATION_POLL_MS)` |
| notifications | `markNotificationRead(id)` / `markAllNotificationsRead()` | POST `P('notifications', id, 'read')` / `P('notifications','read-all')` | none | `NotificationOut` / `void` | — |
| shared | `afterArticleChange`, `afterWorkflowStarted`, `afterTopicChange`, `afterRunChange` | — | — | `Promise<void>` | C3 |

**Behaviour rules.**
1. A request body with "changed keys only" contains just the keys whose values differ from the loaded object; the caller computes the diff.
2. `dashboardRefetchInterval` returns `ACTIVE_POLL_MS` when `today.runStatus` is non-null and non-terminal, when `today.articleStatus` is in `IN_PROGRESS_ARTICLE_STATUSES`, or when any pipeline stage is `running`. Otherwise it returns `false`. A 401 always gives `false`.
3. The invalidation helpers call `queryClient.invalidateQueries({ queryKey })` once per key listed in C3 and await them all.

**Tests to write first.** One table-driven file per module: `it.each(CASES)('$name', …)`. Each row calls the export (a query through `createQueryClient().fetchQuery(options)`) against a `mockApi` with the row's exact key and a response from UI-2's builder. Each row asserts:
(a) the resolved value `toEqual`s the builder output (`undefined` for read-all);
(b) exactly one call to that method and URL;
(c) for a body row, `bodyOf(...)` `toEqual`s the row body.
Every module also has `sends the CSRF token on unsafe calls`: after `setCsrfToken('csrf-t')`, the module's first unsafe row's request header `X-CSRF-Token === 'csrf-t'`.
Rows, with fixed arguments:
- runs: `runDetailQueryOptions('run-done')` → `GET B/runs/run-done`; `createRun({ runDate: '2026-09-18', pillar: 'B', topic: 'Prior auth reform', audience: null, tone: null, wordCount: 900 })` → POST `B/runs` with that body; `restartRun('run-done')` → `POST B/runs/run-done/restart`; `resumeRun('run-done')` → `POST B/runs/run-done/resume`; `retryStep('run-done', 'produce.fact_check')` → `POST B/runs/run-done/steps/produce.fact_check/retry`; `restartFromStep('run-done', 'produce.fact_check')` → `POST B/runs/run-done/steps/produce.fact_check/restart`.
- research: `researchRunsQueryOptions({ runId: 'run-1', kind: 'deep' })` → `GET B/research-runs?runId=run-1&kind=deep&limit=20&offset=0`; `researchRunQueryOptions('research-run-1')` → `GET B/research-runs/research-run-1`.
- sources: `ledgerQueryOptions({ domain: 'cms.gov', tier: 1, accessMode: 'full_text', q: 'prior auth', since: '2026-09-01T00:00:00Z' })` → `GET B/sources?domain=cms.gov&tier=1&accessMode=full_text&q=prior%20auth&since=2026-09-01T00%3A00%3A00Z&limit=20&offset=0`; `updateFeed('feed-1', { isEnabled: false })` → PATCH `B/sources/feeds/feed-1` body `{ isEnabled: false }`; `updateDomain('domain-1', { tier: 2 })` → PATCH `B/sources/domains/domain-1`; `saveThemes({ items: [makeThemeIn()] })` → PUT `B/themes`; `feedsQueryOptions()`, `domainsQueryOptions()`, `themesQueryOptions()` GET rows.
- topics: `topicRoundQueryOptions({ runId: 'run-1', round: 2 })` → `GET B/topics?runId=run-1&round=2`; `topicRoundQueryOptions({})` → `GET B/topics`; `generateTopics('run-1')` → body `{ runId: 'run-1' }`; `selectTopic('candidate-2', true)` → `POST B/topics/candidate-2/select` body `{ confirmWarning: true }`; `updateTopic('candidate-1', { title: 'New title' })` → PATCH body `{ title: 'New title' }`; `rejectTopic('candidate-1', 'Off pillar')` → body `{ reason: 'Off pillar' }`; `topicHistoryQueryOptions({ q: 'access' })` → `GET B/topics/history?q=access&limit=20&offset=0`; `externalPostsQueryOptions({ offset: 20 })` → `GET B/topics/external-posts?limit=20&offset=20`; `similarTopicsQueryOptions('prior auth reform')` → `GET B/topics/similar?text=prior%20auth%20reform&limit=5`; `diversityQueryOptions()` → `GET B/topics/diversity?days=30`.
- articles: `articlesQueryOptions({ view: 'review', pillar: 'A', q: 'access', offset: 20 })` → `GET B/articles?view=review&pillar=A&q=access&limit=20&offset=20`; `articleQueryOptions('article-1')`; `saveArticle('article-1', { baseVersionId: 'version-2', cta: 'Book a call' })` → PATCH body exactly that; `versionsQueryOptions`; `versionQueryOptions('article-1', 'version-1')` → `GET B/articles/article-1/versions/version-1`; `diffQueryOptions('article-1', 'version-1', 'version-2')` → `GET B/articles/article-1/diff?from=version-1&to=version-2`; `regenerateArticle('article-1', { component: 'section', sectionKey: 'evidence', instructions: 'Use the newest figures.' })`; `selectTitle('article-1', { key: 'visionary', customTitle: null })`; `articleSourcesQueryOptions('article-1', 'version-1')` → `GET B/articles/article-1/sources?versionId=version-1`; `articleSourcesQueryOptions('article-1')` → `GET B/articles/article-1/sources`; `researchPacketsQueryOptions('article-1')`.
- quality: `factCheckQueryOptions('article-1')` → `GET B/articles/article-1/fact-check`; `reviewsQueryOptions('article-1', { kind: 'editorial' })` → `GET B/articles/article-1/reviews?kind=editorial`; `qualityGatesQueryOptions('article-1', 'version-1')` → `…/quality-gates?versionId=version-1`; `recheckArticle('article-1')` → `POST …/recheck` with `init.body === undefined`; `approveArticle('article-1', { mode: 'publish', versionId: 'version-2', overrideReason: null })`; `rejectArticle('article-1', 'Off-brand tone')` → body `{ reason: 'Off-brand tone' }`.
- publishing: `previewQueryOptions('article-1')`; `exportArticle('article-1')`; `confirmPublished('article-1', 'https://www.mdcopilot.health/blog/widen-specialist-access')` → body `{ url: … }`; `publishArticle('article-1', true)` → body `{ asDraft: true }`; `scheduleArticle('article-1', '2026-09-20T09:30:00+05:30')` → body `{ at: '2026-09-20T09:30:00+05:30' }`; `unscheduleArticle('article-1')`; `publicationsQueryOptions('article-1')`.
- calendar: `calendarQueryOptions('2026-09')` → `GET B/calendar?month=2026-09`; `updateSlot('2026-09-15', { status: 'cancelled' })` → PATCH `B/calendar/slots/2026-09-15` body `{ status: 'cancelled' }`.
- settings: GET rows for settings, brand, pillars, price overrides, users; `saveSettings({ expectedVersion: 3, values: makeSettingsValues() })`; `saveBrand({ expectedVersion: 2, values: makeBrandProfileValues() })`; `savePillars({ items: [makePillarIn()] })`; `createPriceOverride(makePriceOverrideCreate())`; `createUser({ email: 'new@example.com', displayName: 'New', role: 'viewer', password: 'pw' })` → `POST /api/admin/users`; `updateUser('user-2', { role: 'reviewer' })` → `PATCH /api/admin/users/user-2` body `{ role: 'reviewer' }`.
- agent-runs: `agentRunsQueryOptions({ runId: 'run-done' })` → `GET B/agent-runs?runId=run-done&limit=50&offset=0`; `agentRunQueryOptions('agent-run-1')` → `GET B/agent-runs/agent-run-1`.
- metrics: `costsQueryOptions({ groupBy: 'article', from: '2026-09-17T01:30:00Z', articleId: 'article-1' })` → `GET B/metrics/costs?groupBy=article&from=2026-09-17T01%3A30%3A00Z&articleId=article-1`; `costsQueryOptions({ groupBy: 'day' })` → `GET B/metrics/costs?groupBy=day`; `latencyQueryOptions()` → `GET B/metrics/latency?days=30`.
- dashboard: `dashboardQueryOptions()` → `GET B/metrics/dashboard`. Also `dashboardRefetchInterval` unit rows: `makeDashboardOut()` (SUCCEEDED run, READY_FOR_REVIEW article, but one stage `running`) → `3000`; the same with every stage `done` → `false`; `runStatus: 'PRODUCING'` → `3000`; `articleStatus: 'SEO'` with every stage done and a SUCCEEDED run → `3000`; any data with `new ApiError(401, {})` → `false`; `undefined` → `false`.
- notifications: `notificationsQueryOptions({})` → `GET B/notifications?unreadOnly=true&limit=10`; `markNotificationRead('notification-1')` → `POST B/notifications/notification-1/read`; `markAllNotificationsRead()` → `POST B/notifications/read-all` answered `new Response(null, { status: 204 })`, resolves `undefined`.
- `shared/invalidation.test.ts` › `invalidates the documented keys`: spy on `qc.invalidateQueries`. `afterArticleChange(qc, 'article-1')` calls `[['articles','article-1'], ['articles','list'], ['dashboard'], ['calendar']]` in that order. `afterWorkflowStarted(qc, null)` calls `[['runs'], ['agent-runs'], ['dashboard'], ['topics']]`. `afterWorkflowStarted(qc, 'article-1')` calls the article keys followed by those four (duplicate `['dashboard']` allowed). `afterTopicChange` calls `[['topics'], ['runs'], ['dashboard'], ['articles','list']]`. `afterRunChange` calls `[['runs'], ['agent-runs'], ['dashboard']]`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features` → red → green. `npm test`, `npm run lint`, `npm run typecheck` → exit 0.

**Acceptance covered.** §4.12 endpoint wiring for every page; the precondition for every §10 UI row.

### UI-4: Shared presentation components

**Files.** Create in `src/components/`: `page-header.tsx`, `query-state.tsx`, `status-badge.tsx`, `reason-dialog.tsx`, `confirm-dialog.tsx`, `pagination.tsx`, `source-ref-list.tsx`, `safe-html.tsx`, `copy-button.tsx`, `score-breakdown.tsx`, `novelty-panel.tsx`, `gate-badge.tsx`, `json-block.tsx`, and `src/components/shared-components.test.tsx`.

**Interfaces produced.**
```tsx
PageHeader({ title, description?, actions? }: { title: string; description?: string; actions?: ReactNode })
QueryState({ query, label, notFound?, children }: { query: { isPending: boolean; isError: boolean; error: unknown }; label: string; notFound?: { status?: number; title?: string; message: string }; children: ReactNode })
ArticleStatusBadge({ status }: { status: ArticleStatus }); RunStatusBadge({ status }: { status: RunStatus }); CandidateStatusBadge({ status }: { status: CandidateStatus })
ReasonDialog({ open, onOpenChange, title, description, submitLabel, pending, onSubmit }: { …; onSubmit: (reason: string) => void })
ConfirmDialog({ open, onOpenChange, title, description, confirmLabel, pending, onConfirm }: { …; onConfirm: () => void })
Pagination({ total, limit, offset, onOffsetChange }: { total: number; limit: number; offset: number; onOffsetChange: (offset: number) => void })
SourceRefList({ sources }: { sources: SourceRefOut[] })
SafeHtml({ html, label }: { html: string; label: string })
CopyButton({ label, text }: { label: string; text: string })
ScoreBreakdown({ breakdown, total }: { breakdown: Record<string, ScoreItem>; total: number | null })
NoveltyPanel({ novelty }: { novelty: NoveltyResult | null })
GateBadge({ badge }: { badge: GateBadgeOut })
JsonBlock({ label, value }: { label: string; value: unknown })
```

**Behaviour rules.**
1. `PageHeader` renders `<h1 className="font-heading text-2xl font-semibold">`, an optional muted `<p>`, and the actions on the right. Pages render it first, outside any data boundary.
2. `QueryState` renders `<Skeleton aria-label={`Loading ${label}`} />` while pending. On error it renders `<p role="alert">`. That alert says `notFound.message` when `isProblem(error, notFound.status ?? 404, notFound.title)`, otherwise `Could not load ${label}: ${describeProblem(error, 'request failed')}`. On success it renders `children`.
3. Badges use `Badge` with `articleStatusVariant` / run variants (Phase 1 `RunsTable` mapping) and show the label text. Candidate variants: PASSED → `default`; WARNED → `secondary`, text `Warned: similar content`; REJECTED → `destructive`, text `Rejected: duplicate`; SELECTED → `default`; DISMISSED and SUPERSEDED → `outline`; PROPOSED → `secondary`.
4. `ReasonDialog` shows a textarea labelled `Reason` with `maxLength={2000}` and a live counter `n / 2000`. Submit (label `submitLabel`) is disabled while `reason.trim()` is empty or `pending`, and calls `onSubmit(reason.trim())`. Closing and reopening clears the text (the dialog body is keyed by an open counter).
5. `ConfirmDialog` is an `AlertDialog` whose confirm action calls `onConfirm` and is disabled while `pending`. `Cancel` closes it.
6. `Pagination` shows `Showing ${offset + 1}–${min(offset + limit, total)} of ${total}`, or `No results` for `total === 0`. `Previous page` is disabled at offset 0 and sets `max(0, offset − limit)`. `Next page` is disabled when `offset + limit >= total` and sets `offset + limit`.
7. `SourceRefList` renders a `<ul>`. Each item has the marker as a `Badge` (or `—`), then the title as `<a href={url} target="_blank" rel="noopener noreferrer">`, publisher, domain, `Tier n`, `formatDate(publishedAt, localTimeZone())` or `Undated`, and an access label (`Full text`, `Abstract only`, `Metadata only`).
8. `SafeHtml` renders `<div role="document" aria-label={label} className="article-preview" dangerouslySetInnerHTML={{ __html: sanitizePreviewHtml(html) }} />`. `index.css` gains an `.article-preview` block styling `h2, h3, p, ul, ol, li, blockquote, a, img` (typography only).
9. `CopyButton` calls `navigator.clipboard.writeText(text)`, then `toast.success(`${label} copied`)`, or `toast.error(`Could not copy ${label.toLowerCase()}`)` on rejection. Its button name is `Copy ${label.toLowerCase()}`.
10. `ScoreBreakdown` renders a table with columns `Component`, `Weight`, `Score`, `Why`: one row per entry, sorted by key, using `humanizeKey(key)`, `formatScore(weight)`, `formatScore(score)` and `justification`. A total row shows `formatScore(total)`.
11. `NoveltyPanel` renders `Not checked` for `null`. Otherwise it shows the decision text (`PASS` → `Novel`, `WARN` → `Similar content exists`, `REJECT_TOPIC` → `Duplicate`), `Max similarity ${formatPercent(maxSimilarity)}`, and a table (`Kind`, `Title`, `Similarity`) of neighbours sorted by similarity descending. Kind labels: `topic` → `Topic`, `article` → `Article`, `external_post` → `Published post`; others via `humanizeKey`.
12. `GateBadge` shows `Re-check required` when `recheckRequired`. Otherwise `passed === null` → `Gates not run`, `true` → `Gates passed`, `false` → `Gates failed` followed by the failed gate labels joined with `, `.
13. `JsonBlock` renders `<figure>` with `<figcaption>{label}</figcaption><pre>{JSON.stringify(value, null, 2)}</pre>`. For an object with a string `message` it shows that message in a `<p>` above the `<pre>`.

**Tests to write first** (`src/components/shared-components.test.tsx`; render with `renderPage` where a QueryClient/toaster is needed).
- `PageHeader renders an h1 with the title`: heading level 1 `Drafts`.
- `QueryState shows loading, not-found, error and content`: pending → element labelled `Loading drafts`; `isError` with `new ApiError(404, { title: 'Fact check not found' })` and `notFound={{ title: 'Fact check not found', message: 'No fact check on this version yet.' }}` → alert with that message; `new ApiError(500, { title: 'Internal Server Error' })` → alert `Could not load drafts: Internal Server Error`; success → children text.
- `ReasonDialog requires a non-blank reason`: open; submit `Reject article` is disabled; type `   ` → still disabled; type `Off-brand` → enabled; click → `onSubmit` called with `'Off-brand'`; the counter reads `9 / 2000`.
- `ConfirmDialog confirms and cancels`: `Change topic` confirm calls `onConfirm` once; `Cancel` calls `onOpenChange(false)`.
- `Pagination moves by page and disables at bounds`: `total=45, limit=20, offset=20` → text `Showing 21–40 of 45`; `Next page` → `onOffsetChange(40)`; `Previous page` → `onOffsetChange(0)`; with `offset=40`, `Next page` is disabled; with `total=0`, text is `No results`.
- `SourceRefList links sources safely`: link `CMS finalises prior authorization rule` has `href` `https://www.cms.gov/newsroom/prior-auth`, `target` `_blank` and `rel` `noopener noreferrer`; the texts `S1`, `Tier 1`, `Full text` and `formatDate('2026-09-15T00:00:00Z', localTimeZone())` are present.
- `SafeHtml never renders scripts, handlers or javascript links`: html `'<p>ok</p><script>window.__xss = 1</script><img src="x" onerror="window.__xss = 1"><a href="javascript:alert(1)">bad</a>'` → `container.querySelector('script')` is null; no element has an `onerror` attribute; link `bad` has no `href` attribute; `(window as any).__xss` is undefined; the `document` role element named by `label` contains `ok`.
- `CopyButton writes text and confirms`: spy `navigator.clipboard.writeText`; click `Copy slug` → called with `'widen-specialist-access'`; toast `Slug copied`; with a rejected spy → toast `Could not copy slug`.
- `ScoreBreakdown and NoveltyPanel show scores and neighbours`: row `Timeliness` with `0.25`, `0.80`, `Rule finalised this week.`; `Novel`, `Max similarity 62%`, row `Published post` / `Prior auth, explained` / `62%`; `NoveltyPanel` with `null` → `Not checked`.
- `GateBadge covers each state`: `{ passed: false, failedGates: ['word_count', 'cta_fresh'], recheckRequired: false }` → `Gates failed: Word count, CTA present and fresh`; `recheckRequired: true` → `Re-check required`; `passed: null` → `Gates not run`.
- `JsonBlock shows a message and the JSON`: value `{ message: 'Fact checker timed out', class: 'TimeoutError' }` → paragraph `Fact checker timed out` and a `<pre>` containing `"class": "TimeoutError"`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/components` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 "Preview never renders raw model HTML (XSS fixture)" (UI part), "reject requires a reason" (shared dialog).

### UI-5: Article action dialogs and publisher/policy hooks

**Files.** Create `src/features/quality/components/approve-dialog.tsx`, `src/features/quality/components/reject-article-dialog.tsx`, `src/features/articles/components/regenerate-dialog.tsx`, `src/features/publishing/components/schedule-dialog.tsx`, `src/features/publishing/use-publisher-mode.ts` and `src/features/quality/use-gate-override-policy.ts`, each with a test next to it (`*.test.tsx`).

**Interfaces produced.**
```tsx
ApproveDialog({ article, open, onOpenChange, onApproved }: { article: ArticleDetailOut; open: boolean; onOpenChange(open: boolean): void; onApproved?(state: ArticleStateOut): void })
RejectArticleDialog({ articleId, open, onOpenChange, onRejected }: { articleId: string; open: boolean; onOpenChange(open: boolean): void; onRejected?(state: ArticleStateOut): void })
RegenerateDialog({ articleId, status, open, onOpenChange, initialComponent, onStarted }: { articleId: string; status: ArticleStatus; open: boolean; onOpenChange(open: boolean): void; initialComponent?: ArticleComponent; onStarted?(accepted: ActionAccepted): void })
ScheduleDialog({ articleId, title, timeZone, mode, open, onOpenChange, onScheduled }: { articleId: string; title: string; timeZone: string; mode: 'schedule' | 'move'; open: boolean; onOpenChange(open: boolean): void; onScheduled?(state: ArticleStateOut): void })
export const SECTION_LABELS: Record<SectionKey, string>          // regenerate-dialog.tsx
export function usePublisherMode(): { known: boolean; network: boolean }
export function useGateOverridePolicy(): 'admin_with_reason' | 'never' | null
```

**Behaviour rules.**
1. `useGateOverridePolicy` runs `useQuery({ ...settingsQueryOptions(), enabled: useIsAdmin() })` and returns `data?.effective.gateOverridePolicy ?? null`. A non-admin session sends no request.
2. `usePublisherMode` runs `useQuery({ ...settingsQueryOptions(), enabled: useCan('blog.settings') })`. `known = data !== undefined`, and `network = known && data.publishingEnabled && data.effective.publisher === 'mdcopilot_api'`.
3. `ApproveDialog` (title `Approve article`; description `v<versionNo>: <selectedTitle ?? 'Untitled draft'>`):
   - A fieldset with legend `Approval mode` holds native radios `Approve as draft` (value `draft`, checked by default) and `Approve for publishing` (value `publish`).
   - READY_FOR_REVIEW: button `Approve` sends `{ mode, versionId: article.currentVersionId, overrideReason: null }`.
   - QUALITY_GATE_FAILED with `useIsAdmin()` and `useGateOverridePolicy() === 'admin_with_reason'`: textarea `Override reason` (`maxLength` 2000), plus button `Override and approve`, disabled while the trimmed reason is empty. It sends `{ mode, versionId, overrideReason: reason.trim() }`.
   - QUALITY_GATE_FAILED otherwise: text `Quality gates failed on this version. Only an admin can override, with a written reason.` and no submit.
   - `currentVersionId === null`: text `No version to approve.` and no submit.
   - Success: `toast.success('Article approved')`, `await afterArticleChange(qc, article.id)`, `onApproved?.(state)`, close.
   - Errors keep the dialog open. 409 `Version conflict` → `toast.error('This article changed. Reload it before approving.')` and `afterArticleChange`. 409 `Recheck required` → `toast.error('Re-check required before approval')`. Anything else → `describeProblem(error, 'Could not approve the article')`.
4. `RejectArticleDialog` wraps `ReasonDialog` with title `Reject article`, description `The article and its versions are kept. A reason is required.` and submit `Reject article`. It sends `rejectArticle(articleId, reason)`, then `toast.success('Article rejected')`, `afterArticleChange`, `onRejected?.(state)` and closes. Errors → `describeProblem(error, 'Could not reject the article')`.
5. `RegenerateDialog` (title `Regenerate`):
   - Radix `Select` `Component` offers only the options `articleActions.canRegenerate(status, c)` allows, in this order and with these labels: `Headline` (`headline`), `Introduction` (`introduction`), `Section` (`section`), `Pull quote` (`pull_quote`), `CTA` (`cta`), `Whole article` (`article`), `Research` (`research`). The default is `initialComponent`, else the first allowed option.
   - `SECTION_LABELS` = `introduction: 'Introduction'`, `context: 'Context'`, `core_argument: 'Core argument'`, `evidence: 'Evidence'`, `mdcopilot_perspective: 'MDCopilot perspective'`, `practical_implications: 'Practical implications'`, `conclusion: 'Conclusion'`. `Select` `Section` appears only for `section` and lists `SECTION_ORDER` without `introduction`. Submit is disabled until a section is chosen.
   - Textarea `Instructions` (`maxLength` 2000) appears for every component except `research`.
   - Button `Start regeneration` sends `{ component, sectionKey: component === 'section' ? key : null, instructions: component === 'research' ? null : (text.trim() || null) }`. Success: `toast.success(component === 'research' ? 'Research regeneration started' : 'Regeneration started')`, `afterWorkflowStarted(qc, articleId)`, `onStarted?.(accepted)`, close. Errors → `describeProblem(error, 'Could not start regeneration')`.
6. `ScheduleDialog`:
   - Title `Schedule article` (mode `schedule`) or `Move scheduled article` (mode `move`). Description `<title> · Time zone: <timeZone>`.
   - Inputs `Date` (`type="date"`, required) and `Time` (`type="time"`, default `09:00`). Submit label: `Schedule article` or `Move`.
   - In the submit handler: `at = zonedWallTimeToIso(date, time, timeZone)`. If `Date.parse(at) <= Date.now()`, show `Schedule time must be in the future` and send nothing.
   - `schedule` mode: `scheduleArticle(articleId, at)`. `move` mode: `unscheduleArticle(articleId)`, then `scheduleArticle(articleId, at)`. If the unschedule fails → `toast.error(describeProblem(e, 'Could not unschedule'))` and stop. If the schedule fails after a successful unschedule → `toast.error('Unscheduled, but could not reschedule: ' + describeProblem(e, 'request failed'))` and `afterArticleChange`.
   - Success: `toast.success('Scheduled for <date> <time> (<timeZone>)')`, `afterArticleChange`, `onScheduled?.(state)`, close. Other errors → `describeProblem(error, 'Could not schedule')`, which gives `Forbidden: missing permission blog.publish` for the network-publisher 403.

**Tests to write first** (render inside `renderPage`; each file `afterEach(() => vi.restoreAllMocks())`).
- `use-publisher-mode.test.tsx`:
  - `reports a network publisher to admins`: admin, `GET B/settings` → `makeSettingsOut({ publishingEnabled: true, effective: { ...makeSettingsOut().effective, publisher: 'mdcopilot_api' } })` → `{ known: true, network: true }`.
  - `reports manual export by default`: admin with default settings → `{ known: true, network: false }`.
  - `stays unknown without blog.settings`: publisher role → `{ known: false, network: false }` and `callsTo(fetchMock, 'GET', 'B/settings')` has length 0.
- `approve-dialog.test.tsx`:
  - `approves a ready article as draft`: reviewer, `POST B/articles/article-1/approve` → `makeArticleStateOut()`. Click `Approve` → body `{ mode: 'draft', versionId: 'version-2', overrideReason: null }`, header `X-CSRF-Token` `csrf-reviewer`, toast `Article approved`, `onApproved` called once.
  - `approves for publishing`: check radio `Approve for publishing` → body `mode: 'publish'`.
  - `lets an admin override a gate-failed version with a reason`: admin, default settings, article `status: 'QUALITY_GATE_FAILED'`. `Override and approve` is disabled; type `Reviewed manually` → enabled; click → body `{ mode: 'draft', versionId: 'version-2', overrideReason: 'Reviewed manually' }`.
  - `hides the override from a non-admin`: reviewer with QUALITY_GATE_FAILED → text `Only an admin can override` present (substring match), no `Override and approve` button, no settings request.
  - `hides the override when the policy is never`: admin with `effective.gateOverridePolicy: 'never'` → no `Override and approve` button.
  - `keeps the dialog open on a version conflict`: 409 `Version conflict` → toast `This article changed. Reload it before approving.`, dialog `Approve article` still present.
- `reject-article-dialog.test.tsx` › `sends the trimmed reason`: type `  Off-brand tone ` → `Reject article` → body `{ reason: 'Off-brand tone' }`; toast `Article rejected`.
- `regenerate-dialog.test.tsx`:
  - `regenerates one section with instructions`: editor, READY_FOR_REVIEW. Pick Component `Section`; the submit is disabled; pick Section `Evidence`; type Instructions `Use the newest figures.` → body `{ component: 'section', sectionKey: 'evidence', instructions: 'Use the newest figures.' }`; toast `Regeneration started`; `onStarted` receives the `ActionAccepted`.
  - `sends nulls for a whole-article regeneration`: `initialComponent: 'article'` → body `{ component: 'article', sectionKey: null, instructions: null }`.
  - `offers only research for a failed article`: status FAILED; opening `Component` lists exactly one option, `Research`; no `Instructions` textbox; body `{ component: 'research', sectionKey: null, instructions: null }`; toast `Research regeneration started`.
  - `shows the problem on 409`: `{ title: 'Invalid state transition', detail: 'illegal article transition: APPROVED -> DRAFTING' }` → toast `Invalid state transition: illegal article transition: APPROVED -> DRAFTING`.
- `schedule-dialog.test.tsx` (`vi.useFakeTimers({ toFake: ['Date'] })`, `vi.setSystemTime(new Date('2026-09-17T00:00:00Z'))`, `vi.useRealTimers()` in `afterEach`):
  - `schedules in the given zone`: Date `2026-09-20`, Time `09:30`, zone `Asia/Kolkata` → body `{ at: '2026-09-20T09:30:00+05:30' }`; toast `Scheduled for 2026-09-20 09:30 (Asia/Kolkata)`.
  - `rejects a past time without calling the API`: Date `2026-09-16` → text `Schedule time must be in the future`; no POST to `…/schedule`.
  - `moves by unscheduling then scheduling`: mode `move`. The POST URLs in `fetchMock.mock.calls` order are `…/unschedule`, then `…/schedule`.
  - `reports a failed reschedule after unscheduling`: the schedule returns 409 `Invalid state transition` → toast text starts with `Unscheduled, but could not reschedule: Invalid state transition`.
  - `shows the permission detail`: 403 with detail `missing permission blog.publish` → toast `Forbidden: missing permission blog.publish`.

**Implementation notes.** Radix `Select` needs UI-0's pointer stubs (fact 4). In tests, open it with `user.click(screen.getByRole('combobox', { name: 'Component' }))`, then click `screen.getByRole('option', { name: 'Section' })`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/quality src/features/articles/components src/features/publishing` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 "every human action wired … reject requires a reason", the approve/reject/regenerate Vitest suites, and the owner gate-override policy as displayed (§9 row, QUAL primary).

### UI-6: Drafts, Review Queue, Published

**Files.** Create `src/features/articles/components/article-list.tsx`. Replace `src/routes/drafts-page.tsx`, `src/routes/review-queue-page.tsx` and `src/routes/published-page.tsx`. Create `src/routes/article-list-pages.test.tsx`.

**Interfaces.** Consumes `articlesQueryOptions`, `Pagination`, `QueryState`, `GateBadge`, `ArticleStatusBadge`. Produces `ArticleList({ view }: { view: 'drafts' | 'review' | 'published' })`.

**Behaviour rules.**
1. Each page renders `PageHeader` first, then `<ArticleList view=…/>`:
   - `DraftsPage`: title `Drafts`, description `Articles being written or waiting for edits.`
   - `ReviewQueuePage`: title `Review Queue`, description `Articles waiting for a review decision.`
   - `PublishedPage`: title `Published`, description `Published, exported and scheduled articles.`
2. `ArticleList` reads the search params `pillar` (must be a `PillarKey`, else ignored), `q`, and `offset` (a non-negative integer, else 0). It queries `articlesQueryOptions({ view, pillar, q, limit: 20, offset })`.
3. A `<form role="search">` holds Radix `Select` `Pillar` (`All pillars`, `Pillar A`…`Pillar E`, `Narrative`), input `Search` (placeholder `Title or slug`) and submit button `Search`. Submitting replaces the search params with the non-empty `pillar` and `q` and removes `offset`. `Pagination.onOffsetChange` sets `offset`.
4. Columns:
   - drafts: `Title`, `Status`, `Pipeline`, `Pillar`, `Version`, `Words`, `Gates`, `Fact check`, `Editorial`, `Updated`.
   - review: `Title`, `Status`, `Pillar`, `Version`, `Gates`, `Fact check`, `Editorial`, `Updated`.
   - published: `Title`, `Status`, `Pillar`, `Published`, `URL`, `Scheduled for`.
5. Cells:
   - Title is `<Link to={`/articles/${id}`}>{title ?? 'Untitled draft'}</Link>`. Version is `v<n>` or `—`.
   - Fact check is `PASS` or `FAIL`, plus ` (independent)` when `independentCheck`, or `—`. Editorial is `formatScore`.
   - Dates use `formatDateTime(…, localTimeZone())`.
   - URL is an external link (`target="_blank"`, `rel="noopener noreferrer"`) with the URL as text, or `—`.
6. An empty page shows `No articles in this view.`, and `QueryState` label `articles`.

**Tests to write first** (`renderPage(<DraftsPage />, { path: '/drafts', role: 'viewer' })` and similar).
- `lists drafts with status, gates and a link`: `GET B/articles?view=drafts&limit=20&offset=0` → `pageOf([makeArticleSummaryOut()])`. Link `How clinics can widen specialist access` has href `/articles/article-1`; texts `Ready for review`, `Gates passed`, `PASS (independent)`, `0.82`, `980`, `v2`.
- `names untitled drafts`: `title: null` → link `Untitled draft`.
- `filters by pillar and search text`: choose Pillar `Pillar A`, type `access`, click `Search` → a call to `GET B/articles?view=drafts&pillar=A&q=access&limit=20&offset=0`.
- `reads filters from the URL`: `url: '/drafts?pillar=B&offset=40'` → `GET B/articles?view=drafts&pillar=B&limit=20&offset=40`.
- `pages forward`: `pageOf(items, { total: 45 })` → `Next page` → `GET B/articles?view=drafts&limit=20&offset=20`.
- `uses the review view`: `ReviewQueuePage` at `/review` (role reviewer) → heading `Review Queue`, `GET B/articles?view=review&limit=20&offset=0`.
- `shows published URLs`: `PublishedPage`, item `publishedUrl: 'https://www.mdcopilot.health/blog/x'` → link with that href and `rel` `noopener noreferrer`; the URL used `view=published`.
- `keeps the heading on errors`: 500 `Internal Server Error` → heading `Drafts` and alert `Could not load articles: Internal Server Error`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/routes/article-list-pages.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 "Drafts, Review Queue, Published" (filtered lists with gate badges).

### UI-7: Today's Ideas

**Files.** Create in `src/features/topics/`: `use-select-topic.ts`, and in `components/`: `select-topic-button.tsx`, `topic-card.tsx`, `topic-round.tsx`, `edit-topic-dialog.tsx`. Replace `src/routes/ideas-page.tsx`. Create `src/routes/ideas-page.test.tsx`.

**Interfaces produced.**
```tsx
export function useSelectTopicMutation(options: { onNeedsConfirmation(candidateId: string): void }):
  UseMutationResult<ActionAccepted, unknown, { candidateId: string; confirmWarning: boolean }>
SelectTopicButton({ candidate, changeTopic }: { candidate: TopicCandidateOut; changeTopic?: boolean })
TopicCard({ candidate, compact, highlighted, changeTopic }: { candidate: TopicCandidateOut; compact?: boolean; highlighted?: boolean; changeTopic?: boolean })
TopicRound({ runId, round, compact, highlightCandidateId, allowChangeTopic, onRoundChange }: { runId?: string; round?: number; compact?: boolean; highlightCandidateId?: string; allowChangeTopic?: boolean; onRoundChange(round: number): void })
EditTopicDialog({ candidate, open, onOpenChange }: { candidate: TopicCandidateOut; open: boolean; onOpenChange(open: boolean): void })
```

**Behaviour rules.**
1. `useSelectTopicMutation` calls `selectTopic(candidateId, confirmWarning)`.
   - On success it toasts by `workflowName`: `produce_article` → `Production started`; `change_topic` → `Changing topic: a new article will be produced`; anything else → `Topic selected`. It then calls `afterTopicChange(qc)`, and `afterArticleChange(qc, accepted.articleId)` when that is not null.
   - A 409 `Topic needs confirmation` calls `onNeedsConfirmation(candidateId)` without a toast. Other errors → `describeProblem(error, 'Could not select the topic')`.
2. `SelectTopicButton` renders only when `useCan('blog.generate')` and `candidate.status` is PASSED or WARNED. Its accessible name is `Select topic: <title>` and its visible text `Select`.
   - Without `changeTopic`: PASSED sends `confirmWarning: false` directly. WARNED opens `ConfirmDialog` titled `Select a similar topic?`, description `Similar to “<neighbour title>” (<formatPercent(similarity)>). Select it anyway?` (the neighbour with the highest similarity), confirm `Select anyway` → `confirmWarning: true`. `onNeedsConfirmation` opens the same dialog.
   - With `changeTopic`: every click opens `ConfirmDialog` titled `Change topic?`, description `The current article will be superseded. Its versions are kept.` (plus the similarity sentence when WARNED), confirm `Change topic` → `confirmWarning: candidate.status === 'WARNED'`.
3. `TopicCard` is `<article aria-labelledby=<h2 id>>` with `aria-current="true"` when `highlighted`. It contains:
   - `<h2>` title; `CandidateStatusBadge`; `Selected topic` badge when highlighted; `Manual topic` badge when `isManual`; `Pillar <key>`; `Score <formatScore(totalScore)>`.
   - A `<dl>` with `Why now`, and unless `compact`: `Hook`, `News trigger` (list of `relevantNews` links, `rel="noopener noreferrer"`, plus `formatDate(publishedAt, localTimeZone())` or `Undated`), `MDCopilot angle` (`mdcopilotConnection`), `Thesis`, `Core argument`, `Angle`, `Audience` (`targetAudience`).
   - Unless `compact`: `<h3>Scores</h3>` + `ScoreBreakdown`, `<h3>Novelty</h3>` + `NoveltyPanel`, `<h3>Sources</h3>` + `SourceRefList`.
   - `Dismissed: <rejectedReason>` when set; link `Open article` to `/articles/<articleId>` when set.
   - Actions: `SelectTopicButton`. `Edit topic: <title>` (visible text `Edit`) when `blog.edit` and status not SELECTED/SUPERSEDED and not `compact`. `Reject topic: <title>` (visible text `Reject`) when `blog.edit`, status PROPOSED/PASSED/WARNED, and not `compact`. Reject opens `ReasonDialog` (title `Reject topic`, description `The topic is dismissed for this run.`, submit `Reject`), sends `rejectTopic`, then `toast.success('Topic dismissed')` and `afterTopicChange`.
4. `EditTopicDialog` (title `Edit topic`) is keyed by `candidate.updatedAt` (C7). Fields: input `Title` (required, 1..300), textareas `Hook`, `Why now`, `Thesis`, `Angle`, `Core argument`, `Target audience`, and Radix `Select` `Pillar`. `Save topic` is disabled while nothing changed or the title is invalid. It sends only the changed keys, then `toast.success('Topic updated')`, `afterTopicChange`, and closes. Errors → `describeProblem(error, 'Could not update the topic')`.
5. `TopicRound` queries `topicRoundQueryOptions({ runId, round })` (`QueryState` label `topic candidates`, not-found `{ title: 'Run not found', message: 'No topic candidates yet. Start a run from the Dashboard.' }`). It renders:
   - the line `Run <runId first 8> · <runStatus> · Round <round>`;
   - Radix `Select` `Round` (`Round <n>` options) when `roundsAvailable.length > 1`;
   - when `shortfall`, a `role="status"` paragraph `Fewer than three usable topics after the regeneration limit. Choose one of the remaining topics or regenerate.`;
   - the cards sorted by `position`, passing `highlighted = id === highlightCandidateId` and `changeTopic = allowChangeTopic`.
6. `IdeasPage` reads the search params `runId` and `round` (a positive integer).
   - `PageHeader`: title `Today's Ideas`, description `Three candidate topics per round, with scores, novelty and sources.`
   - Header action `Regenerate topics`: shown when `blog.generate`, the round has loaded (it reads the same query as `TopicRound`), and `runStatus` is not QUEUED, RESEARCHING, PRODUCING or CANCELLED. It sends `generateTopics(data.runId)`, then `toast.success('Generating new topics')` and `afterTopicChange`.
   - Round changes set the `round` search param (keeping `runId`).

**Tests to write first** (`src/routes/ideas-page.test.tsx`, page at `/ideas`).
- `shows three candidate cards with why-now, news, scores, novelty and sources`: `GET B/topics` → `makeTopicRoundOut()` → three level-2 headings. Within the `candidate-1` article: `CMS finalised the prior authorization rule this week.`, link `CMS finalises prior authorization rule`, row `Timeliness`, `Novel`, `Digital twins extend specialist reach.`, `Score 0.79`. Within the `candidate-3` article: `Rejected: duplicate` and `Duplicate`.
- `selects a passed topic without confirmation`: role editor; `POST B/topics/candidate-1/select` → `makeActionAccepted({ workflowName: 'produce_article', candidateId: 'candidate-1', articleId: null })` → body `{ confirmWarning: false }`, header `csrf-editor`, toast `Production started`, `GET B/topics` called at least twice.
- `asks before selecting a warned topic`: click `Select topic: Prior auth, explained again` → dialog `Select a similar topic?` containing `Prior auth, explained` and `91%` → `Select anyway` → body `{ confirmWarning: true }`.
- `opens the confirmation when the API asks for it`: first `POST …/candidate-1/select` → 409 `Topic needs confirmation`, second → `makeActionAccepted()` → the dialog `Select a similar topic?` appears; confirm → the second call's body is `{ confirmWarning: true }`.
- `offers no select for a rejected topic`: no button `Select topic: AI in the clinic`.
- `regenerates topics for the run`: `POST B/topics/generate` → body `{ runId: 'run-1' }`, toast `Generating new topics`.
- `hides Regenerate topics while the run is researching`: `runStatus: 'RESEARCHING'` → no `Regenerate topics` button.
- `edits a topic`: `Edit topic: How clinics can widen specialist access` → clear `Title`, type `Widen specialist access now` → `Save topic` → `PATCH B/topics/candidate-1` body `{ title: 'Widen specialist access now' }`, toast `Topic updated`.
- `rejects a topic with a reason`: `Reject topic: How clinics can widen specialist access` → type `Off pillar` → `Reject` → body `{ reason: 'Off pillar' }`, toast `Topic dismissed`.
- `shows no actions to a viewer`: role viewer → no button named by `/^(Select topic|Edit topic|Reject topic|Regenerate topics)/`.
- `follows runId and round in the URL`: `url: '/ideas?runId=run-1'` with `roundsAvailable: [1, 2]` → `GET B/topics?runId=run-1`; choose `Round` `Round 2` → `GET B/topics?runId=run-1&round=2`.
- `shows the shortfall notice`: `shortfall: true` → status text `Fewer than three usable topics after the regeneration limit.` (substring).
- `explains when no run has candidates`: 404 `Run not found` → `No topic candidates yet. Start a run from the Dashboard.`; heading `Today's Ideas` present.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/routes/ideas-page.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.2 UI Today's Ideas cards; §10.2 near-duplicate neighbour and similarity shown; §10.5 topic-selection suite; §5.7 Rule B UI (selection invalidates the runs and dashboard queries).

### UI-8: Dashboard

**Files.** Replace `src/routes/dashboard-page.tsx` and extend `src/routes/dashboard-page.test.tsx` (keep its five Phase 1 tests unchanged). Create in `src/features/dashboard/components/`: `today-card.tsx`, `pipeline-tracker.tsx`, `metrics-grid.tsx`, `diversity-panel.tsx`, `generate-run-dialog.tsx`, `dashboard-components.test.tsx`. Create in `src/features/metrics/components/`: `cost-chart.tsx` (lazy target), `cost-table.tsx`, `cost-panel.tsx`.

**Interfaces produced.**
```tsx
TodayCard({ data }: { data: DashboardOut }); PipelineTracker({ data }: { data: DashboardOut }); MetricsGrid({ data }: { data: DashboardOut })
DiversityPanel(); GenerateRunDialog({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void })
CostChart({ rows, label }: { rows: CostRowOut[]; label: string }); CostTable({ report, caption }: { report: CostReportOut; caption: string }); CostPanel()
```

**Behaviour rules.**
1. Page order:
   - `PageHeader` (title `Dashboard`, description `Today's pipeline, review actions and costs.`) with actions `Generate today's blog` and `Generate with options`, both shown only with `blog.generate`.
   - Then `<section aria-labelledby>`s with `<h2>`: `Today`, `Pipeline`, `Last 30 days`, `Diversity`, `Costs`, `Recent runs`. The headings are always rendered; each section's content sits in its own `QueryState`: labels `today`, `pipeline` and `metrics` on `dashboardQueryOptions()`, `diversity`, and `costs`.
   - `Recent runs` keeps the Phase 1 `RunsTable` with `runsQueryOptions(10)`.
   - `Times in <timezone>` appears under the header once the dashboard has loaded.
2. `Generate today's blog` calls `createRun()` (body `{}`), then `toast.success('Run queued', { description: `Run for ${runDate} is ${status}.` })` and `afterRunChange`. Its label while pending is `Starting...`. Errors → `describeProblem(error, 'Could not start the run')` (Phase 1 test: `Agent disabled`).
3. `GenerateRunDialog` (title `Generate a blog`):
   - Fields: `Run date` (`type="date"`), Radix `Select` `Pillar` (`Rotation default` → `null`, then `Pillar A`…`Narrative`), `Topic` (`maxLength` 300), `Audience`, `Tone`, `Word count` (`type="number"`).
   - A word count outside 300..3000 shows `Word count must be between 300 and 3000` and disables `Start run`.
   - The body sets each blank field to `null` and `wordCount` to a number: `{ runDate, pillar, topic, audience, tone, wordCount }`. Success: toast `Run queued`, `afterRunChange`, close.
4. `TodayCard`:
   - `today.runId === null` → `No run today yet.`
   - `Research: <not started|running|done|failed>`; `<n> opportunities discovered`.
   - With a recommended topic: `<h3>Recommended topic</h3>`, its title, `whyNow`, `Pillar <key>`, `Evidence <s> · Relevance <s> · Novelty <s> · Total <s>` (`formatScore`).
   - `Select recommended topic`: shown when `blog.generate`, `recommendedTopic` is set, `articleId === null` and `runStatus` is WAITING_FOR_TOPIC or TOPICS_READY. It uses `useSelectTopicMutation` with `confirmWarning: false`. `onNeedsConfirmation` opens `ConfirmDialog` `Select a similar topic?` (description `This topic is similar to earlier content. Select it anyway?`, confirm `Select anyway`) → `confirmWarning: true`.
   - Links: `Change topic` → `/ideas?runId=<runId>` when `runId` is set; `Review research` → `/research?runId=<runId>` when `researchStatus !== 'not_started'`.
   - With an article: `<h3>Article</h3>`, `ArticleStatusBadge`, link `Open article` → `/articles/<articleId>`, and `<ul aria-label="Headline options">` with the three `headlineOptions` values.
   - With `quality`, `<dl aria-label="Quality summary">`:
     - `Fact check` = verdict or `Not run`; `Sources` = `<n> sources · T1 <tier1> · T2 <tier2> · T3 <tier3>`; `Novelty` = `<round(noveltyPercent)>% novel` or `—`.
     - `Clinical` = `Clear`, `Blocked` or `—`; `Editorial` = `formatScore`; `SEO` = `Complete`, `Incomplete` or `—`; `Gates` = `Passed`, `Failed` or `Not run`.
   - `Approve`: shown when `blog.approve` and `articleStatus === 'READY_FOR_REVIEW'`. A click runs `await qc.fetchQuery(articleQueryOptions(articleId))` in the handler, then opens `ApproveDialog` with the result. A failed fetch → `describeProblem(error, 'Could not load the article')`.
   - `Regenerate article`: shown when `blog.generate` and `articleStatus` is READY_FOR_REVIEW or QUALITY_GATE_FAILED. It opens `RegenerateDialog` with `initialComponent: 'article'` and `status = articleStatus`.
5. `PipelineTracker` renders `No pipeline run today.` when `pipeline.runId === null`. Otherwise `<ol aria-label="Pipeline stages">`: each `<li>` shows the label, status text (`Pending`, `Running`, `Done`, `Failed`, `Skipped`) and `formatDateTime(startedAt, data.timezone)` when set. A running stage's `<li>` has `aria-current="step"`.
6. `MetricsGrid` is a `<dl>` with these term → value pairs:
   - `Posts generated` → n; `Posts published` → n; `Posts pending review` → n; `Topics generated` → n; `Research sources` → n.
   - `Avg generation time` → `formatSeconds`; `Avg editorial score` → `formatScore`; `Duplicate topic rate` → `formatPercent`; `Fact-check pass rate` → `formatPercent`.
   - `Cost today`, `Cost this week`, `Cost this month` → `formatUsd`.
7. `DiversityPanel` queries `diversityQueryOptions(30)` and renders three lists, each with `None in the last 30 days.` when empty:
   - `Pillar mix`: `Pillar <key>: <count>`.
   - `Source domains`: `<domain>: <count> (<formatShare(share)>)`.
   - `Repeated phrases`: `“<phrase>” ×<count>`.
8. `CostPanel` has a Radix `Select` `Group costs by` with options `Day` (`day`, default), `Week` (`week`), `Month` (`month`), `Article` (`article`), `Research run` (`research_run`), `Topic` (`topic`). It queries `costsQueryOptions({ groupBy: <selected> })`, `{ groupBy: 'agent' }` and `{ groupBy: 'model' }`. The selected report renders a lazy `CostChart` (C8, label `Cost by <option label, lower-cased> chart`) and `CostTable` caption `Cost by <option label, lower-cased>`; the other two render `CostTable` captions `Cost by agent` and `Cost by model`.
   - `CostTable` columns: `Group` (label), `Cost` (`formatUsd`), `Calls`, `Input tokens`, `Output tokens`, `Search actions`, with a `<tfoot>` cell `Total <formatUsd(totalUsd)>`. No rows → `No LLM calls in this window.`
   - `CostChart` wraps a Recharts `ResponsiveContainer` (`width="100%" height={220}`) → `BarChart` (data `rows.map(r => ({ label: r.label, cost: Number(r.costUsd) }))`, `XAxis dataKey="label"`, `YAxis`, `Tooltip`, `Bar dataKey="cost" fill="var(--color-chart-1)"`) in `<div role="img" aria-label={label}>`.
9. `dashboardQueryOptions()` polls per `dashboardRefetchInterval` (UI-3).

**Tests to write first.**
- In `dashboard-page.test.tsx` (the five Phase 1 tests stay; new tests mock `GET B/metrics/dashboard` → `makeDashboardOut()`, `GET B/runs?limit=10` → `runsPage([])`, and whatever else each names; everything else answers 404).
  - `renders the Today card`: within region `Today`: `How clinics can widen specialist access` (first match), `3 opportunities discovered`, `Research: done`, list `Headline options` with 3 items, and in the quality summary `PASS`, `6 sources · T1 3 · T2 2 · T3 1`, `87% novel`, `Clear`, `Complete`, `Passed`. Links `Open article` → `/articles/article-1`, `Review research` → `/research?runId=run-1`, `Change topic` → `/ideas?runId=run-1`. Text `Times in Asia/Kolkata`.
  - `marks the running pipeline stage`: within region `Pipeline`, the list item containing `Write draft` has `aria-current="step"` and text `Running`; the item containing `Gather signals` has text `Done`.
  - `shows 30-day metrics`: within region `Last 30 days`: `2m 05s`, `0.80`, `10%`, `90%`, `$1.2345`, `$5.0000`, `$20.0000`.
  - `shows the diversity panel`: `GET B/topics/diversity?days=30` → `makeDiversityPanelOut()` → `Pillar A: 4`, `statnews.com: 3 (33.3%)`, `“specialist access” ×5`.
  - `shows cost tables by day, agent and model`: `GET B/metrics/costs?groupBy=day` → `makeCostReportOut()`; `…groupBy=agent` → `makeCostReportOut({ groupBy: 'agent', totalUsd: '0.900000', rows: [{ key: 'writer', label: 'writer', costUsd: '0.900000', calls: 3, inputTokens: 300, outputTokens: 90, searchActions: 0 }] })`; `…groupBy=model` → `makeCostReportOut({ groupBy: 'model', rows: [] , totalUsd: '0.000000' })`. Table `Cost by day` has a row with `2026-09-16` and `$1.0000` and footer `Total $1.5000`; table `Cost by agent` has a row with `writer`; table `Cost by model` shows `No LLM calls in this window.`
  - `selects the recommended topic when the run waits for a topic`: role editor; today `{ runStatus: 'WAITING_FOR_TOPIC', articleId: null, articleStatus: null, quality: null, headlineOptions: null }`; `POST B/topics/candidate-1/select` → `makeActionAccepted({ workflowName: 'produce_article' })` → body `{ confirmWarning: false }`, toast `Production started`, `GET B/metrics/dashboard` and `GET B/runs?limit=10` each called at least twice.
  - `approves from the Today card`: role reviewer; `GET B/articles/article-1` → `makeArticleDetailOut()`; `POST B/articles/article-1/approve` → `makeArticleStateOut()`. Click `Approve` → dialog `Approve article` → click its `Approve` → body `{ mode: 'draft', versionId: 'version-2', overrideReason: null }`, toast `Article approved`.
  - `regenerates the article from the Today card`: role editor → `Regenerate article` → dialog `Regenerate` → `Start regeneration` → body `{ component: 'article', sectionKey: null, instructions: null }`.
  - `starts a run with options`: role editor → `Generate with options` → `Run date` `2026-09-18`, `Pillar` `Pillar B`, `Topic` `Prior auth reform`, `Word count` `900` → `Start run` → body `{ runDate: '2026-09-18', pillar: 'B', topic: 'Prior auth reform', audience: null, tone: null, wordCount: 900 }`.
  - `hides Today actions from a viewer`: role viewer → no buttons `Select recommended topic`, `Approve`, `Regenerate article`, `Generate with options`; link `Open article` present.
  - `keeps the heading when the dashboard API fails`: `GET B/metrics/dashboard` → 500 `Internal Server Error` → heading `Dashboard` and alert `Could not load today: Internal Server Error`.
  - `explains a day without a run`: today with `runId: null` and every other nullable field `null`, `pipeline: { runId: null, stages: [] }` → `No run today yet.` and `No pipeline run today.`
- In `dashboard-components.test.tsx`:
  - `shows dashes for missing quality values`: `TodayCard` with `quality: { factCheckVerdict: null, sourceCount: 0, tierMix: { tier1: 0, tier2: 0, tier3: 0 }, noveltyPercent: null, clinicalClear: null, editorialScore: null, seoComplete: null, gatesPassed: null }` → `Not run` for the fact check and gates, `—` for novelty, clinical, editorial and SEO.
  - `regroups the cost report`: `CostPanel` (mocks for `day`, `agent`, `model`, and `GET B/metrics/costs?groupBy=research_run` → `makeCostReportOut({ groupBy: 'research_run', rows: [{ key: 'research-run-1', label: 'Broad scan 2026-09-17', costUsd: '0.300000', calls: 11, inputTokens: 900, outputTokens: 120, searchActions: 10 }], totalUsd: '0.300000' })`) → choose `Group costs by` `Research run` → table `Cost by research run` has a row with `Broad scan 2026-09-17` and `$0.3000`.
  - `validates the word count`: `GenerateRunDialog`, `Word count` `100` → `Word count must be between 300 and 3000` and `Start run` disabled.
  - `lazy-loads the cost chart`: `CostPanel` with the day report → `findByRole('img', { name: 'Cost by day chart' }, { timeout: 5000 })` (the `CostChart` label passed is `Cost by day chart`).

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/routes/dashboard-page.test.tsx src/features/dashboard src/features/metrics` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 Dashboard Today card, pipeline tracker, metrics and diversity panel; §10.8 cost views (today/week/month, by agent and model, charts) and dashboard metrics; Phase 1 dashboard behaviour kept (`Generate today's blog`, used by `scripts/acceptance/phase1.sh`).

### UI-9: Research

**Files.** Replace `src/routes/research-page.tsx`. Create `src/features/research/components/research-run-list.tsx`, `src/features/research/components/research-run-detail.tsx` and `src/routes/research-page.test.tsx`.

**Interfaces.** Consumes `researchRunsQueryOptions`, `researchRunQueryOptions`, `regenerateArticle`, `SourceRefList`, `JsonBlock`, `Pagination`. Produces `ResearchRunList({ runId, kind, offset, onOpen, onFilter })` and `ResearchRunDetail({ researchRunId })`.

**Behaviour rules.**
1. `PageHeader`: title `Research`, description `Research runs, themes covered, findings with sources, and per-phase latency.`
2. The search params `runId`, `kind` (a `ResearchRunKind`), `offset` and `researchRunId` drive the page.
3. The list has Radix `Select` `Kind` (`All kinds`, `Broad scan` = `broad`, `Deep research` = `deep`, `Verification` = `verification`).
   - When `runId` is set it also shows `Run <first 8>` and a button `Clear run filter` that removes `runId`.
   - Table columns: `Kind`, `Status`, `Started` (`formatDateTime`), `Sources` (`sourceCount`), `Findings` (`findingCount`), `Total time` (`formatMs(phaseLatencyMs.total ?? null)`), and a button with visible text `Open` named `Open research run <id>` that sets `researchRunId`.
   - Status labels: `running` → `Running`, `succeeded` → `Succeeded`, `partial` → `Partial coverage`, `insufficient_evidence` → `Insufficient evidence`, `failed` → `Failed`.
   - `Pagination`; `QueryState` label `research runs`; an empty page shows `No research runs yet.`
4. The detail renders when `researchRunId` is set (`QueryState` label `research run`, not-found `{ title: 'Research run not found', message: 'Research run not found.' }`):
   - `<h2>Research run <formatDateTime(startedAt)></h2>`, kind and status labels, `Window: <windowDays> days`, `Finished <formatDateTime(finishedAt)>` or `Still running`.
   - `Themes covered` as badges, or `No themes`.
   - Table caption `Phase latency`: rows `Search`, `Retrieval`, `Extraction`, `LLM`, `Total` from `phaseLatencyMs.search/retrieval/extraction/llm/total` through `formatMs` (missing key → `—`).
   - Table caption `Counts`: a row per `counts` entry with `humanizeKey(key)` and the number.
   - Table caption `Queries`: columns `Query`, `Theme` (`themeKey ?? '—'`), `Status` (`OK` or `Failed`), `Search actions`, `Sources`, `Error` (`error ?? '—'`).
   - `<h3>Findings</h3>`: one `<article>` per finding in `position` order, showing `#<position + 1>`, the claim, a `claimType` badge, `High importance` when high, `Confidence <formatPercent>`, the evidence, a `Preprint` badge, `Downgraded from <downgradedFrom>` when set, and `SourceRefList`. No findings → `No findings.`
   - Table caption `Ledger sources`: columns `Title` (external link), `Publisher`, `Tier`, `Published` (`formatDate` or `Undated`), `Date source`, `Access`, `Fetch`, `Words`.
   - `JsonBlock` label `Error` when `error` is set.
   - When `articleId` is set: link `Open article` → `/articles/<articleId>`, and a button `Regenerate research` (with `blog.generate`) that sends `regenerateArticle(articleId, { component: 'research', sectionKey: null, instructions: null })`, then `toast.success('Research regeneration started')` and `afterWorkflowStarted(qc, articleId)`. Errors → `describeProblem(error, 'Could not regenerate research')`.

**Tests to write first** (`src/routes/research-page.test.tsx`).
- `lists research runs`: `GET B/research-runs?limit=20&offset=0` → `pageOf([makeResearchRunOut()])` → a row with `Broad scan`, `Succeeded`, `6`, `4`, `10.5 s`.
- `filters by run from the URL and by kind`: `url: '/research?runId=run-1'` → `GET B/research-runs?runId=run-1&limit=20&offset=0`; text `Run run-1`; choose `Kind` `Deep research` → `GET B/research-runs?runId=run-1&kind=deep&limit=20&offset=0`; click `Clear run filter` → `GET B/research-runs?kind=deep&limit=20&offset=0`.
- `opens a run with themes, queries, findings, latency and sources`: click `Open research run research-run-1` → `GET B/research-runs/research-run-1` → `makeResearchRunDetail()`. Badge `prior_authorization`; `Phase latency` row `Search` `1.2 s`; `Queries` row `specialist wait times` with `Failed` and `HTTP 503`; finding `CMS finalised the rule.` with `FACT`, `High importance`, `Confidence 85%` and marker `S1`; `Ledger sources` has a row with `cms.gov`'s title link.
- `regenerates research for a deep run with an article`: role editor; detail `makeResearchRunDetail({ kind: 'deep', articleId: 'article-1' })`; `POST B/articles/article-1/regenerate` → `makeActionAccepted({ workflowName: 'regenerate_research' })` → body `{ component: 'research', sectionKey: null, instructions: null }`, toast `Research regeneration started`; link `Open article` → `/articles/article-1`.
- `shows the transition problem`: the same POST → 409 `{ title: 'Invalid state transition', detail: 'illegal article transition: APPROVED -> DRAFTING' }` → toast `Invalid state transition: illegal article transition: APPROVED -> DRAFTING`.
- `hides Regenerate research from a viewer`: role viewer with the deep detail → no `Regenerate research` button.
- `shows a missing run`: `url: '/research?researchRunId=nope'`, `GET B/research-runs/nope` → 404 `Research run not found` → `Research run not found.`
- `shows the run error`: detail with `status: 'failed'`, `error: { message: 'insufficient evidence' }` → figure `Error` containing `insufficient evidence`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/routes/research-page.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.1 UI Research page (runs, themes covered, typed findings with sources and dates, per-phase latency, regenerate research).

### UI-10: Sources and the themes editor

**Files.** Replace `src/routes/sources-page.tsx`. Create in `src/features/sources/components/`: `ledger-tab.tsx`, `feeds-tab.tsx`, `domains-tab.tsx`, `domain-edit-dialog.tsx`, `themes-editor.tsx`, `themes-editor.test.tsx`. Create `src/routes/sources-page.test.tsx`. Add `toThemeIn(theme: ThemeOut): ThemeIn` to `src/features/sources/api.ts` (with a row in its `api.test.ts`: the result's keys are exactly `ThemeIn`'s and the values are copied).

**Interfaces produced.** `LedgerTab()`, `FeedsTab()`, `DomainsTab()`, `DomainEditDialog({ domain, open, onOpenChange })`, `ThemesEditor({ readOnly }: { readOnly: boolean })`, `toThemeIn`.

**Behaviour rules.**
1. `PageHeader`: title `Sources`, description `Source ledger, feed health, domain tiers and discovery themes.` Radix `Tabs` with list label `Sources`: `Ledger` (default), `Feeds`, `Domains`, `Themes`.
2. Ledger:
   - `<form role="search">`: input `Domain`; `Select` `Tier` (`All tiers`, `Tier 1`, `Tier 2`, `Tier 3`); `Select` `Access` (`All access modes`, `Full text`, `Abstract only`, `Metadata only`); input `Title contains` (→ `q`); `Published since` (`type="date"`, → `since = <date>T00:00:00Z`); submit `Apply filters`. Filters live in component state and reset `offset` to 0.
   - Table columns `Title` (external link), `Publisher`, `Domain`, `Type` (`humanizeKey(sourceType)`), `Tier`, `Published`, `Date source`, `Access`, `Fetch status`, `Words`, `Discovered via`, `Relevance` (`formatScore`); `Pagination`; `QueryState` label `sources`.
3. Feeds:
   - One `<h3>` per `group` (sorted), each with a table: `Feed` (name linked to `url`), `Kind`, `Tier`, `Health`, `Last success` (`formatDateTime`), `Items`, `Last error` (`lastError ?? '—'`).
   - `Health`: `Disabled` (plus ` — <disabledReason>` when set) if not enabled; else `Failing (<consecutiveFailures>)` if failures > 0; else `Never fetched` if `lastFetchedAt === null`; else `Healthy`.
   - With `blog.settings`: a `Switch` named `Enabled: <name>` sends `updateFeed(id, { isEnabled: checked })` → `toast.success(checked ? 'Feed enabled' : 'Feed disabled')`. A `Select` named `Tier: <name>` sends `updateFeed(id, { tier })` → `toast.success('Feed tier updated')`. Both then invalidate `['sources', 'feeds']`. Without the permission, `Enabled` shows as the text `Yes`/`No`. Errors → `describeProblem(error, 'Could not update the feed')`.
4. Domains:
   - Table columns `Domain`, `Tier`, `Type`, `Publisher`, `Fetch policy` (`Fetch`, `Metadata only`, `Never`), `Verification` (`Allowed`/`Not allowed`), `Notes`.
   - With `blog.settings`: button `Edit domain <domain>` opens `DomainEditDialog` (title `Edit domain`, keyed by `domain.id`). Fields: `Select` `Tier`, `Select` `Source type` (the 8 `SourceType` values via `humanizeKey`), input `Publisher`, `Select` `Fetch policy`, `Checkbox` `Allowed for verification searches`, textarea `Notes`.
   - `Save domain` is disabled when nothing changed. It sends the changed keys only (a blank `Publisher` or `Notes` becomes `null`), then `toast.success('Domain updated')`, invalidates `['sources', 'domains']` and closes. Errors → `describeProblem(error, 'Could not update the domain')`.
5. `ThemesEditor`:
   - It queries `themesQueryOptions()` and renders an inner form keyed by the query's `dataUpdatedAt` (C7), initialised with `data.map(toThemeIn)` plus a per-row `isNew: false`.
   - `readOnly`: a table with columns `Key`, `Name`, `Pillars`, `Active`, `Queries`, `Last searched`, and no inputs or buttons.
   - Editable: one `<fieldset>` per row, legend `<name>` or `New theme`. Fields: `Key` (read-only for existing rows), `Name`, `Description`, `Query templates` (one per line), one `Checkbox` per pillar named `Pillar <key>`, `Switch` `Active`, `Sort order` (number). Controls are labelled within their fieldset; tests use `within(fieldset)`.
   - `Add theme` appends `{ key: '', name: '', description: '', queryTemplates: [], pillarKeys: [], isActive: true, sortOrder: max(sortOrder) + 1 (0 when empty), isNew: true }`.
   - Row errors: `Key must be lowercase letters, digits or underscores (1–64)` (fails `^[a-z0-9_]{1,64}$`); `Key already used` (duplicate); `Name is required` (trimmed empty or over 200 characters); `Add 1 to 10 query templates` (non-empty line count outside 1..10); `Each query template must be 300 characters or fewer`.
   - `Save themes` is disabled while any row has an error, nothing changed, or a save is pending. It sends `saveThemes({ items })`, where each row drops `isNew` and has its query template lines trimmed with empties removed. Then `setQueryData(['sources', 'themes'], response)` and `toast.success('Themes saved')`. Errors → `describeProblem(error, 'Could not save themes')`.
   - Note under the form: `Themes are never deleted. Turn one off to stop using it.` There is no delete control.
6. `SourcesPage` renders `<ThemesEditor readOnly={!useCan('blog.settings')} />` in the `Themes` tab.

**Tests to write first.**
- `src/routes/sources-page.test.tsx`:
  - `lists the ledger and applies filters`: `GET B/sources?limit=20&offset=0` → `pageOf([makeLedgerSourceOut()])` → the title link is present. Fill `Domain` `cms.gov`, `Tier` `Tier 1`, `Access` `Full text`, `Title contains` `prior auth`, `Published since` `2026-09-01` → `Apply filters` → `GET B/sources?domain=cms.gov&tier=1&accessMode=full_text&q=prior%20auth&since=2026-09-01T00%3A00%3A00Z&limit=20&offset=0`.
  - `shows feed health`: tab `Feeds`; `GET B/sources/feeds` → `[makeSourceFeedOut(), makeSourceFeedOut({ id: 'feed-2', name: 'JAMA', consecutiveFailures: 3, lastError: 'HTTP 403' }), makeSourceFeedOut({ id: 'feed-3', name: 'NEJM AI', isEnabled: false, disabledReason: 'Blocked by bot wall' })]` → `Healthy`, `Failing (3)`, `HTTP 403`, `Disabled — Blocked by bot wall`.
  - `lets an admin disable a feed`: admin → switch `Enabled: STAT News` → `PATCH B/sources/feeds/feed-1` body `{ isEnabled: false }`, header `csrf-admin`, toast `Feed disabled`.
  - `lets an admin change a feed tier`: `Tier: STAT News` → `Tier 1` → body `{ tier: 1 }`, toast `Feed tier updated`.
  - `shows feed health to a viewer without controls`: role viewer, tab `Feeds` → `queryAllByRole('switch')` length 0, no combobox `Tier: STAT News`, text `Healthy`.
  - `edits a domain`: admin, tab `Domains`, `GET B/sources/domains` → `[makeSourceDomainOut()]` → `Edit domain cms.gov` → `Fetch policy` `Metadata only` → uncheck `Allowed for verification searches` → `Save domain` → `PATCH B/sources/domains/domain-1` body `{ fetchPolicy: 'metadata_only', verificationAllowlisted: false }`, toast `Domain updated`.
  - `shows the allowlist limit problem`: that PATCH → 422 `{ title: 'Request validation failed', detail: 'more than 100 domains would be allowlisted' }` → toast `Request validation failed: more than 100 domains would be allowlisted`.
- `src/features/sources/components/themes-editor.test.tsx` (`GET B/themes` → `[makeThemeOut()]`):
  - `saves an edited theme`: in fieldset `Prior authorization`, set `Name` to `Prior auth` → `Save themes` → `PUT B/themes` body `{ items: [{ key: 'prior_authorization', name: 'Prior auth', description: <makeThemeOut().description>, queryTemplates: ['prior authorization {year}'], pillarKeys: ['C'], isActive: true, sortOrder: 0 }] }`, toast `Themes saved`.
  - `adds a new theme after validation`: `Add theme`; in fieldset `New theme`, `Key` `Bad Key` → text `Key must be lowercase letters, digits or underscores (1–64)` and `Save themes` disabled. Then `Key` `burnout`, `Name` `Burnout`, `Query templates` `physician burnout {year}` → enabled → body `items[1]` equals `{ key: 'burnout', name: 'Burnout', description: '', queryTemplates: ['physician burnout {year}'], pillarKeys: [], isActive: true, sortOrder: 1 }`.
  - `turns a theme off instead of deleting it`: switch `Active` in `Prior authorization` → body `items[0].isActive === false`; no button named `/delete|remove/i`.
  - `rejects duplicate keys`: new row key `prior_authorization` → `Key already used`.
  - `limits query templates`: 11 non-empty lines → `Add 1 to 10 query templates`.
  - `is read-only without blog.settings`: `readOnly` → no textbox, no `Save themes`, no `Add theme`; cell `prior_authorization`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/routes/sources-page.test.tsx src/features/sources` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.1 UI Sources page (ledger, feed health, tiers, themes; enable/disable feed, edit tier, edit themes); §10.5 Settings themes editor (reused in UI-18).

### UI-11: Topics

**Files.** Replace `src/routes/topics-page.tsx`. Create `src/features/topics/components/similarity-search.tsx`, `topic-history.tsx`, `external-posts.tsx` and `src/routes/topics-page.test.tsx`.

**Interfaces.** Consumes `similarTopicsQueryOptions`, `topicHistoryQueryOptions`, `externalPostsQueryOptions`, `Pagination`, `QueryState`. Produces `SimilaritySearch()`, `TopicHistory()`, `ExternalPosts()`.

**Behaviour rules.**
1. `PageHeader`: title `Topics`, description `Topic history, published MDCopilot posts, and similarity search.` Three sections with `<h2>`: `Similarity search`, `Topic history`, `Published MDCopilot posts`.
2. Similarity search:
   - Textarea `Text to compare` (`maxLength` 1000). Button `Find similar` is disabled while the trimmed length is under 3. Clicking stores the trimmed text as `submitted`, which enables `similarTopicsQueryOptions(submitted, 5)`.
   - Results table caption `Similar items`: columns `Kind` (UI-4 kind labels), `Title`, `Similarity` (`formatPercent`), sorted by similarity descending. No items → `Nothing similar found.` `QueryState` label `similar items`.
3. Topic history:
   - Input `Search topics` and button `Search history` (sets `q` and resets `offset`).
   - Table columns `Title`, `Pillar`, `Headline pattern` (`humanizeKey`), `Keywords` (joined with `, `), `Article` (link text `ARTICLE_STATUS_LABELS[articleStatus]` or `Open`, `aria-label` `Article for <title>`, → `/articles/<articleId>`; `—` when `articleId` is null), `Created` (`formatDate`).
   - `Pagination`; `QueryState` label `topic history`; an empty page shows `No topics yet.`
4. Published posts:
   - Table columns `Title` (external link to `url`), `Slug`, `Published` (`formatDate` or `Undated`), `Headline pattern`, `Last synced` (`formatDateTime`); `Pagination`; `QueryState` label `published posts`.
   - An empty page shows `No MDCopilot posts synced yet. The sync stays off until BLOG_MDCOPILOT_PUBLIC_API_URL is set.`

**Tests to write first** (`src/routes/topics-page.test.tsx`; `GET B/topics/history?limit=20&offset=0` and `GET B/topics/external-posts?limit=20&offset=0` mocked in every test unless stated).
- `shows topic history with article links`: `pageOf([makeTopicHistoryOut({ title: 'Widen access', headlinePattern: 'how_to', keywords: ['access', 'triage'], articleId: 'article-1', articleStatus: 'PUBLISHED' })])` → row with `Widen access`, `How to`, `access, triage`; link `Article for Widen access` href `/articles/article-1` with text `Published`.
- `searches history`: type `access` → `Search history` → `GET B/topics/history?q=access&limit=20&offset=0`.
- `lists published MDCopilot posts`: `pageOf([makeExternalPostOut({ title: 'Prior auth, explained', url: 'https://www.mdcopilot.health/blog/prior-auth' })])` → link `Prior auth, explained` with that href and `rel` `noopener noreferrer`.
- `explains an empty post sync`: `pageOf([])` for external posts → `No MDCopilot posts synced yet. The sync stays off until BLOG_MDCOPILOT_PUBLIC_API_URL is set.`
- `finds similar items`: type `prior auth reform` → `Find similar` → `GET B/topics/similar?text=prior%20auth%20reform&limit=5` → `{ text: 'prior auth reform', items: [makeNoveltyNeighbour()] }` → table `Similar items` has a row with `Published post`, `Prior auth, explained`, `62%`.
- `needs at least three characters`: type `ab` → `Find similar` disabled; no request to `B/topics/similar`.
- `shows a similarity error`: the similar request → 422 `Request validation failed` → alert starting `Could not load similar items: Request validation failed`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/routes/topics-page.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.2 UI Topics page (history, external posts, similarity search).

### UI-12: Article review, left pane (evidence panels)

Panels are built and tested one by one (UI-12 to UI-15); the page shell that composes them comes last (UI-16). Every panel takes `{ article: ArticleDetailOut }` and fetches its own data.

**Files.** Create in `src/features/articles/components/review/`: `topic-panel.tsx`, `research-panel.tsx`, `sources-panel.tsx`, `claims-panel.tsx`, `quality-panel.tsx`, `summary-panel.tsx`, `left-panels.test.tsx`.

**Interfaces.** Consumes `TopicRound`, `researchPacketsQueryOptions`, `articleSourcesQueryOptions`, `factCheckQueryOptions`, `qualityGatesQueryOptions`, `topicRoundQueryOptions`, `SourceRefList`, `QueryState`, `gateLabel`. Produces `TopicPanel`, `ResearchPanel`, `SourcesPanel`, `ClaimsPanel`, `QualityPanel`, `SummaryPanel`, each `({ article }: { article: ArticleDetailOut })`.

**Behaviour rules.**
1. `TopicPanel` renders `TopicRound` with:
   - `compact`, `runId={article.runId}`, `highlightCandidateId={article.candidateId}`, and the round in local state (`onRoundChange` sets it);
   - `allowChangeTopic={!isApprovedOrLater(article.status) && article.status !== 'REJECTED' && article.status !== 'SUPERSEDED'}`.
   The highlighted (current) candidate is SELECTED, so it never shows a select button. When `article.candidateId` is not among the items, the panel also shows `The selected topic is from another round.`
2. `ResearchPanel` queries `researchPacketsQueryOptions` (label `research packets`). No packets → `No research packet yet.`
   - Radix `Select` `Packet version`: options `Version <n>`, newest first, the newest selected by default.
   - For the chosen packet: `summary`.
   - `<h3>Key facts</h3>`: `statement`, marker badges, `High importance`.
   - `<h3>Statistics</h3>`: `statement`, `value`, `As of <asOf>` when set, markers.
   - `<h3>Counterarguments</h3>` (same form as key facts); `<h3>Industry context</h3>`; `<h3>MDCopilot connection</h3>`; `<h3>Claims needing verification</h3>` (list); `<h3>Sources</h3>` via `SourceRefList(packet.sources)`.
   - Empty lists → `None.`
3. `SourcesPanel` queries `articleSourcesQueryOptions(article.id)` (label `sources`). Table columns: `Marker`, `Source` (external link), `Publisher`, `Domain`, `Tier`, `Published` (`formatDate` + ` (<dateSource>)`, or `Undated`), `Access` (UI-4 labels), `Primary` (`Primary` or empty).
4. `ClaimsPanel` queries `factCheckQueryOptions(article.id)` (label `fact check`, not-found `{ title: 'Fact check not found', message: 'No fact check on this version yet. Run Re-check.' }`).
   - Heading line: `Fact check <verdict> on v<versionNo>`.
   - `independentCheck` → `Independent check: <checkerProvider> checked <writerProvider> writing`; otherwise `Not independent: <checkerProvider ?? 'unknown'> checked writing from the same provider`.
   - Table columns: `Claim`, `Kind` (`humanizeKey`), `Importance`, `Location` (`<SECTION_LABELS[sectionKey] ?? humanizeKey(sectionKey)> · sentence <sentenceIndex + 1>`), `Span` (in `<q>`), `Markers`, `Status` (`humanizeKey(verificationStatus)` as a badge; `destructive` for UNSUPPORTED, OUTDATED, MISLEADING), `Confidence` (`formatPercent`), `Suggested revision` (`recommendedRevision ?? '—'`), `Verified with` (titles of `verificationSources` joined with `; `, or `—`).
5. `QualityPanel`:
   - First a `<dl aria-label="Quality summary">` built from `article`:
     - `Fact check` = `article.factCheck?.verdict ?? 'Not run'`.
     - `Clinical` = `Blocked` when any flag has severity BLOCKING, else `Clear` when `clinicalReview` is set, else `Not run`.
     - `Editorial score` = `formatScore(article.editorialReview?.editorialScore ?? null)`; `Sources` = `article.sources.length`; `SEO` = `Present`/`Missing`.
     - `Re-check` = `Required`/`Not required`; `Gates on this version` = `Passed`/`Not passed` (`gatesPassedOnCurrentVersion`).
   - Then it queries `qualityGatesQueryOptions(article.id)` (label `quality gates`, not-found `{ title: 'Quality gates not found', message: 'Quality gates have not run on this version.' }`).
     - Line `Gate run: <runKind> on v<versionNo> — <Passed|Failed>`.
     - Table caption `Blocking gates` and table caption `Warnings` (split by `severity`), columns `Gate` (`gateLabel`), `Result` (`Pass`/`Fail`), `Details`.
     - Under a failed blocking gate: `sources_present` → `Suggested: regenerate research`; `no_duplicate_topic` → `Suggested: change topic`; `disclosure_present` → `Suggested: set the AI disclosure in Settings`.
6. `SummaryPanel` renders only named, typed fields (never a whole payload object) in `<section>`s with `<h3>`. It reads `topicRoundQueryOptions({ runId: article.runId })` and `researchPacketsQueryOptions(article.id)`.
   - `Why this topic`: candidate `whyNow` and `hook`, from the candidate whose `id === article.candidateId`, else `Topic details unavailable.`
   - `Thesis`: candidate `thesis` and `coreArgument`.
   - `Supporting evidence`: statements of the newest packet's `keyFacts` with `importance === 'high'`, else `None.`
   - `Fact-check status`: `article.factCheck` verdict and `<Status> <count>` pairs grouped by `verificationStatus`, joined with ` · `, or `Not run`.
   - `Clinical review`: each flag as `<severity> <code>: <message> (<location>)`, or `No flags`, or `Not run`.
   - `Editorial review`: `Score <formatScore>`, then `Required changes` (each `description (location)`), `Weaknesses`, `Optional changes`, or `Not run`.
   - `Research summary`: `article.researchSummary ?? 'None.'`

**Tests to write first** (`left-panels.test.tsx`; `renderPage(<XPanel article={…} />, { path: '/a', role })`).
- `TopicPanel highlights the selected candidate`: `GET B/topics?runId=run-1` → `makeTopicRoundOut({ items: [makeTopicCandidateOut({ status: 'SELECTED', articleId: 'article-1' }), <candidate-2>, <candidate-3>] })`. The `article` labelled `How clinics can widen specialist access` has `aria-current="true"` and contains `Selected topic`.
- `TopicPanel changes topic after confirmation`: role editor; `POST B/topics/candidate-2/select` → `makeActionAccepted({ workflowName: 'change_topic' })`. Click `Select topic: Prior auth, explained again` → dialog `Change topic?` → `Change topic` → body `{ confirmWarning: true }`, toast `Changing topic: a new article will be produced`.
- `TopicPanel hides topic changes once approved`: `article.status = 'APPROVED'` → no button named `/^Select topic:/`.
- `ResearchPanel shows the newest packet and switches versions`: `GET B/articles/article-1/research-packets` → `[makeResearchPacketOut({ id: 'packet-2', version: 2, summary: 'Second packet summary' }), makeResearchPacketOut({ version: 1, summary: 'First packet summary' })]` → text `Second packet summary`; choose `Packet version` `Version 1` → text `First packet summary`.
- `SourcesPanel lists markers with tiers and dates`: `GET B/articles/article-1/sources` → `[makeArticleSourceOut()]` → a row with `S1`, the title link, `cms.gov`, `1`, `formatDate('2026-09-15T00:00:00Z', localTimeZone()) + ' (meta)'`, `Full text`, `Primary`.
- `ClaimsPanel shows claims and independence`: `GET B/articles/article-1/fact-check` → `makeFactCheckOut()` → `Fact check PASS on v2`, `Independent check: google checked openai writing`, a row with `CMS finalised the rule this week.`, `Regulatory`, `Context · sentence 1`, `Supported`, `90%`.
- `ClaimsPanel explains a missing fact check`: 404 `Fact check not found` → `No fact check on this version yet. Run Re-check.`
- `QualityPanel lists failed gates with suggestions`: `GET B/articles/article-1/quality-gates` → `makeQualityGatesOut({ passed: false, report: { passed: false, results: [{ gate: 'sources_present', passed: false, severity: 'blocking', details: 'Only 2 sources' }, { gate: 'opening_diversity', passed: true, severity: 'warning', details: 'Opening is distinct.' }] } })` → `Gate run: full on v2 — Failed`; table `Blocking gates` row `Sources present` / `Fail` / `Only 2 sources`; `Suggested: regenerate research`; table `Warnings` row `Opening diversity`.
- `QualityPanel explains gates that have not run`: 404 `Quality gates not found` → `Quality gates have not run on this version.`; the `Quality summary` list still shows `Fact check` `PASS`.
- `SummaryPanel shows structured summaries and never raw reasoning`: the article's `editorialReview` is `{ ...makeEditorialReview({ requiredChanges: [makeChange()] }), reasoning: 'hidden chain of thought' } as EditorialReview`; `clinicalReview = { flags: [makeClinicalFlag()], summary: 'x' }`; mock topics and packets → `Tighten the introduction. (introduction)`, `BLOCKING medical_advice: Reads as individual medical advice. (practical_implications)`, `CMS finalised the prior authorization rule this week.`; `queryByText(/hidden chain of thought/)` is null.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/articles/components/review/left-panels.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 Article review left pane (candidates with scores and highlight, packet, sources, claim checks, quality summary, gates, structured summaries; raw reasoning never shown); change topic action.

### UI-13: Article review, editor, headline and SEO panels

**Files.** Create `src/features/articles/components/markdown-editor.tsx`, `src/features/articles/structure-hint.ts` and `src/features/articles/structure-hint.test.ts`. Create in `src/features/articles/components/review/`: `edit-panel.tsx`, `headline-panel.tsx`, `seo-panel.tsx`, `editor-panels.test.tsx`.

**Interfaces produced.**
```tsx
MarkdownEditor({ value, onChange, readOnly, label }: { value: string; onChange?(value: string): void; readOnly: boolean; label: string })  // lazy target (C8)
export function h2Hint(markdown: string): string | null
EditPanel({ article }: { article: ArticleDetailOut }); HeadlinePanel({ article }: { article: ArticleDetailOut }); SeoPanel({ article }: { article: ArticleDetailOut })
```

**Behaviour rules.**
1. `MarkdownEditor` renders `<CodeMirror value={value} onChange={onChange} readOnly={readOnly} editable={!readOnly} minHeight="480px" basicSetup={{ foldGutter: false }} extensions={[markdown(), EditorView.lineWrapping, EditorView.contentAttributes.of({ 'aria-label': label })]} />` (fact 1). The panels load it with `React.lazy` (C8, fallback label `Loading editor`).
2. `h2Hint` normalises `\r\n` and tests each line against `^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$`.
   - The first heading of level other than 2 → `Only H2 headings are allowed (found an H<level>)`.
   - Otherwise an H2 count other than 6 → `Expected 6 H2 sections, found <n>`.
   - Otherwise `null`. The hint is advisory; the server's 422 is authoritative.
3. `EditPanel`:
   - `canEdit = useCan('blog.edit') && articleActions.canSaveEdit(article.status)`. `const [base, setBase] = useState(() => article)`.
   - The form is a child keyed by `base.currentVersionId ?? 'none'` (C7), holding `content`, `pullQuote`, `cta` and `excerpt`. Fields: `MarkdownEditor` label `Article Markdown`, input `Pull quote`, input `CTA`, textarea `Excerpt` with counter `<n> / 500`.
   - `base.contentMarkdown === null` → `No version to edit yet.` and no form.
   - When `!canEdit`, the editor and inputs are read-only and there is no `Save`. If the user holds `blog.edit` but the status forbids editing, show `Editing is available for articles ready for review, gate-failed or approved.`
   - When `article.currentVersionId !== base.currentVersionId`: a `role="alert"` `A newer version (v<article.versionNo>) is available.` and a button `Load latest`, which calls `setBase(article)` (unsaved edits are discarded only then).
   - `role="status"` shows `h2Hint(content)` when non-null. `Excerpt` over 500 characters shows `Excerpt must be 500 characters or fewer`.
   - `Save` is enabled when at least one field differs from `base`, the content is 1..60000 characters, the excerpt is ≤500, and no save is pending. The body is `{ baseVersionId: base.currentVersionId, …changed fields only }` using the keys `contentMarkdown`, `pullQuote`, `cta`, `excerpt`.
   - Success: `qc.setQueryData(['articles', article.id, 'detail'], response)`, `setBase(response)`, `toast.success('Saved as version <response.versionNo>')`. When `response.status === 'QUALITY_GATE_FAILED'`, also `toast.warning('Deterministic gates failed on version <n>. See the Quality tab.')`. Then `afterArticleChange`.
   - Errors:
     - 409 `Version conflict` → `role="alert"` `Someone saved a newer version. Load the latest version to continue; your text stays here until you do.` plus invalidate `['articles', id]`.
     - 503 `Version features not recorded` → `toast.error(describeProblem(e, …))` plus `afterArticleChange` (the version was committed).
     - Anything else, including 422 `Article structure invalid` and `Unknown citation marker` → `toast.error(describeProblem(e, 'Could not save the article'))`.
4. `HeadlinePanel`:
   - A fieldset with legend `Headline` holds native radios with `aria-label`s `Provocative`, `Operational`, `Visionary`, `Custom`, each followed by its option text. The initial choice is `article.selectedTitleKey ?? 'operational'`. When `Custom` is chosen, input `Custom title` (1..200) appears, initialised to `selectedTitle` when the key is `custom`.
   - `Use this title` (`blog.edit` and `canSelectTitle`) sends `selectTitle(id, key === 'custom' ? { key: null, customTitle } : { key, customTitle: null })`, then `setQueryData` of the detail, `toast.success('Title updated')`, `afterArticleChange`.
   - `<h3>Title options</h3>`: inputs `Provocative title`, `Operational title`, `Visionary title` (1..200), keyed by `currentVersionId`. `Save title options` (`blog.edit` and `canSaveEdit`, enabled when changed and valid) sends `saveArticle(id, { baseVersionId: article.currentVersionId, titleOptions })`. Success → `setQueryData`, `toast.success('Saved as version <n>')`, `afterArticleChange`. 409 `Version conflict` → `toast.error('Someone saved a newer version. Reload before editing titles.')`. Other errors → `describeProblem`.
   - Viewers: inputs read-only, no buttons. `titleOptions === null` → `No headline options yet.`
5. `SeoPanel`, a form keyed by `currentVersionId`:
   - Fields: `SEO title` (hint `<n> characters (target 60 or fewer)`), `Meta description` (hint `<n> characters (target 120–160)`), `Slug`, `Primary keyword`, `Secondary keywords` (comma-separated), `OG title`, `OG description`, `Tags` (comma-separated; head field), `Category` (head field).
   - `article.seo === null` → note `SEO has not been generated for this version yet.` The SEO fields start empty and `Tags`/`Category` come from the head.
   - Read-only lists: `<h3>Internal link suggestions</h3>` (title links) and `<h3>Social copy</h3>` (`LinkedIn`, `X`, `Newsletter` texts).
   - Validation: `Slug` must match `^[a-z0-9]+(?:-[a-z0-9]+)*$` and be ≤200, else `Use lowercase letters, digits and single hyphens`. `SEO title` 1..200 → `SEO title must be 1–200 characters`. `Meta description` 1..500 → `Meta description must be 1–500 characters`. `Category` 1..100 → `Category must be 1–100 characters`. SEO-field validation applies only when `article.seo` is set or an SEO field was typed into.
   - `Save SEO` (`blog.edit` and `canSaveEdit`; enabled when changed and valid) sends `{ baseVersionId, seo?: { changed SeoEdit keys only }, tags?: [...], category? }`. Lists are split on `,`, trimmed, and empties dropped. `seo` is omitted when no SEO key changed; `tags`/`category` are omitted when unchanged.
   - Success → `setQueryData` and `afterArticleChange`, with `toast.success(response.versionNo !== article.versionNo ? 'Saved as version <n>' : 'Tags and category saved')`.
   - 409 `Slug already in use` → inline text under `Slug`: `Slug already in use: <detail>`. 409 `Version conflict` → the headline panel's conflict toast. Other errors → `describeProblem`.

**Tests to write first.**
- `structure-hint.test.ts`: `h2Hint(ARTICLE_MARKDOWN) === null`; with `## Evidence` changed to `Evidence` → `'Expected 6 H2 sections, found 5'`; with `### Detail` appended → `'Only H2 headings are allowed (found an H3)'`; `ARTICLE_MARKDOWN + '#hashtag\n'` → `null`; CRLF line endings → `null`.
- `editor-panels.test.tsx` (helper `setEditorText(name, text)`: `const view = EditorView.findFromDOM(await screen.findByRole('textbox', { name }, { timeout: 5000 }))!; view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } })`, fact 1):
  - `saves only changed fields as a new version`: role editor; `PATCH B/articles/article-1` → `makeArticleDetailOut({ versionNo: 3, currentVersionId: 'version-3', contentMarkdown: 'Edited intro [S1].\n' + <ARTICLE_MARKDOWN without its first line>, cta: 'Book a call' })`. Set the editor to that content, set `CTA` to `Book a call`, click `Save` → body `{ baseVersionId: 'version-2', contentMarkdown: <that content>, cta: 'Book a call' }`, header `csrf-editor`, toast `Saved as version 3`.
  - `warns about the H2 count but lets the server decide`: content with 5 H2s → status `Expected 6 H2 sections, found 5`; `Save` enabled; PATCH → 422 `{ title: 'Article structure invalid', detail: 'expected 6 H2 sections, found 5' }` → toast `Article structure invalid: expected 6 H2 sections, found 5`.
  - `warns when gates fail after saving`: response `status: 'QUALITY_GATE_FAILED', versionNo: 3` → toasts `Saved as version 3` and `Deterministic gates failed on version 3. See the Quality tab.`
  - `keeps unsaved text on a version conflict`: PATCH → 409 `Version conflict` → alert `Someone saved a newer version.` (substring); `EditorView.findFromDOM(textbox).state.doc.toString()` still equals the edited text.
  - `offers a newer version without discarding edits`: harness `function Harness() { const [a, setA] = useState(makeArticleDetailOut()); return <><button onClick={() => setA(makeArticleDetailOut({ currentVersionId: 'version-3', versionNo: 3, contentMarkdown: 'Newer intro [S1].\n' }))}>swap</button><EditPanel article={a} /></> }`. Edit the text, click `swap` → alert `A newer version (v3) is available.`; the editor still holds the edit; click `Load latest` → the editor doc equals `'Newer intro [S1].\n'`.
  - `reports features not recorded`: PATCH → 503 `{ title: 'Version features not recorded', detail: 'version version-3' }` → toast `Version features not recorded: version version-3`.
  - `is read-only for a viewer`: role viewer → textbox `Article Markdown` has `aria-readonly="true"`; no `Save` button.
  - `explains the lock on a published article`: role editor, `status: 'PUBLISHED'` → text `Editing is available for articles ready for review, gate-failed or approved.`; textbox read-only.
  - `selects the visionary title`: `POST B/articles/article-1/select-title` → `makeArticleDetailOut({ selectedTitleKey: 'visionary' })`. Radio `Visionary` → `Use this title` → body `{ key: 'visionary', customTitle: null }`, toast `Title updated`.
  - `sets a custom title`: radio `Custom` → `Custom title` `Specialist access, redesigned` → body `{ key: null, customTitle: 'Specialist access, redesigned' }`.
  - `saves edited title options as a new version`: `Visionary title` → `The next specialist clinic` → `Save title options` → PATCH body `{ baseVersionId: 'version-2', titleOptions: { provocative: 'Why specialist access cannot wait', operational: 'How clinics can widen specialist access', visionary: 'The next specialist clinic' } }`.
  - `hides title selection after approval`: `status: 'APPROVED'`, role editor → no `Use this title`; `Save title options` present.
  - `saves changed SEO fields and tags`: `Slug` → `specialist-access-now`, `Tags` → `specialist access, triage` → `Save SEO` → body `{ baseVersionId: 'version-2', seo: { slug: 'specialist-access-now' }, tags: ['specialist access', 'triage'] }`.
  - `validates the slug`: `Slug` → `Bad Slug` → `Use lowercase letters, digits and single hyphens`; `Save SEO` disabled.
  - `shows slug conflicts inline`: PATCH → 409 `{ title: 'Slug already in use', detail: 'specialist-access-now' }` → text `Slug already in use: specialist-access-now`.
  - `saves category without a new version`: `Category` → `Clinical Ops`; the response keeps `versionNo: 2` → body `{ baseVersionId: 'version-2', category: 'Clinical Ops' }`, toast `Tags and category saved`.
  - `explains missing SEO`: `seo: null` → `SEO has not been generated for this version yet.`

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/articles` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 right pane (CodeMirror editor, headline picker, SEO/tags/category); §10.3 save with wrong H2 count → 422 shown; human edit creates a new version (UI side of the Playwright smoke "edit → save").

### UI-14: Article review, preview, versions and diff

**Files.** Create `src/features/articles/unified-diff.ts` and `src/features/articles/unified-diff.test.ts`. Create in `src/features/articles/components/review/`: `preview-panel.tsx`, `versions-panel.tsx`, `diff-view.tsx`, `version-view.tsx`, `versions-panels.test.tsx`.

**Interfaces produced.**
```ts
export type DiffLine = { kind: 'header' | 'hunk' | 'added' | 'removed' | 'context'; text: string }
export function parseUnifiedDiff(diff: string): DiffLine[]
export const FIELD_CHANGE_LABELS: Record<string, string>
export function fieldChangeLabel(field: string): string
PreviewPanel({ article }); VersionsPanel({ article })
DiffView({ articleId, from, to }: { articleId: string; from: string; to: string })
VersionView({ articleId, versionId, onClose }: { articleId: string; versionId: string; onClose(): void })
```

**Behaviour rules.**
1. `parseUnifiedDiff` splits on `\n` and drops one trailing empty string.
   - Before the first `@@` line, lines starting `--- ` or `+++ ` are `header`.
   - `@@…` is `hunk`.
   - Inside a hunk: `+` → `added`, `-` → `removed`, a space → `context`. The text drops the first character in all three cases.
   - An empty line → `context` with `''`. `\ No newline at end of file` → `context` with the whole line.
   - `''` input → `[]`.
   This relies on the join format in open item O6.
2. `FIELD_CHANGE_LABELS`: `pullQuote` → `Pull quote`, `cta` → `CTA`, `excerpt` → `Excerpt`, `titleOptions.provocative` → `Provocative title`, `titleOptions.operational` → `Operational title`, `titleOptions.visionary` → `Visionary title`. `fieldChangeLabel('seo.<key>')` → `SEO: <humanizeKey(key)>`. Anything else → the raw field.
3. `PreviewPanel` queries `previewQueryOptions(article.id)` (label `preview`) and renders:
   - `SafeHtml` with label `Preview of version <article.versionNo>`;
   - `<h3>Publishing issues</h3>` with `<field>: <message>` items, or `No publishing issues.`;
   - the note `Rendered by the server and sanitised again in the browser.`
4. `VersionsPanel` queries `versionsQueryOptions(article.id)` (label `versions`).
   - Table columns: `Version` (`v<n>`, plus `Current` when `id === article.currentVersionId`, `Approved` when `=== approvedVersionId`, `Published` when `=== publishedVersionId`); `Change` (`humanizeKey(changeKind)`); `Scope` (`changeScope.component`/`sectionKey`/`instructions` joined with ` · `, or `—`); `Words`; `Fact check` (verdict or `—`); `Gates` (`Passed`, `Failed` or `—`); `By` (`Agent`/`Human`); `Created` (`formatDateTime`); and a button `View v<n>`.
   - Radix `Select`s `Compare from` and `Compare to` list `v<n>`. Defaults: from = the second item, to = the first. Button `Show diff` sets the compared pair, which mounts `DiffView`.
   - A single version shows `Only one version exists.` and no compare controls.
   - `View v<n>` mounts `VersionView` for that id.
5. `DiffView` queries `diffQueryOptions` (label `diff`, not-found `{ title: 'Version not found', message: 'Version not found.' }`).
   - `<h3>Changes from v<fromVersionNo> to v<toVersionNo></h3>`.
   - `<pre aria-label="Unified diff">` with one `<span data-kind>` per non-header line. `added` shows `+ text`, `removed` shows `- text`, and `context` shows two spaces then the text; `hunk` lines are muted.
   - Table caption `Field changes`: columns `Field` (`fieldChangeLabel`), `Before`, `After`. `Before` renders `diffWords(from ?? '', to ?? '')` parts without `added` ones, wrapping `removed` in `<del>`. `After` renders parts without `removed` ones, wrapping `added` in `<ins>`. No changes → `No field changes.`
6. `VersionView` queries `versionQueryOptions` (label `version`) and renders:
   - `<h3>Version <n></h3>` and `MarkdownEditor` (lazy, `readOnly`, label `Version <n> Markdown`);
   - `Pull quote`, `CTA`, `Excerpt`, the three title options;
   - `<h4>Resolutions</h4>` with items `<findingId>: <action> — <note>`, or `None.`;
   - `SEO title` and `Slug` from `seo`;
   - a button `Close version` that calls `onClose`.

**Tests to write first.**
- `unified-diff.test.ts`:
  - `parses a difflib diff`: `parseUnifiedDiff(makeVersionDiffOut().unifiedDiff)` equals `[{ kind: 'header', text: '--- v1' }, { kind: 'header', text: '+++ v2' }, { kind: 'hunk', text: '@@ -1,3 +1,3 @@' }, { kind: 'context', text: 'Specialist access is a scheduling problem [S1].' }, { kind: 'removed', text: 'Old line' }, { kind: 'added', text: 'New line' }]`.
  - `treats --- inside a hunk as a removed line`: `'--- v1\n+++ v2\n@@ -1 +1 @@\n--- rule\n+++ rule'` gives the last two as `{ kind: 'removed', text: '-- rule' }` and `{ kind: 'added', text: '++ rule' }`.
  - `returns nothing for an empty diff`: `parseUnifiedDiff('')` equals `[]`.
  - `labels field changes`: `fieldChangeLabel('seo.metaDescription') === 'SEO: Meta description'`; `fieldChangeLabel('cta') === 'CTA'`.
- `versions-panels.test.tsx`:
  - `renders sanitised server HTML with issues`: `GET B/articles/article-1/preview` → `makePreviewOut({ html: '<h2>Context</h2><script>window.__xss = 1</script><a href="javascript:alert(1)">x</a>', issues: [{ field: 'excerpt', message: 'Excerpt is longer than 500 characters.' }] })`. The document `Preview of version 2` contains heading `Context`; `container.querySelector('script')` is null; link `x` has no `href`; text `excerpt: Excerpt is longer than 500 characters.`
  - `marks current and approved versions`: `GET …/versions` → `[makeVersionSummaryOut(), makeVersionSummaryOut({ id: 'version-1', versionNo: 1, parentVersionId: null, changeKind: 'draft' })]` with `article.approvedVersionId = 'version-1'` → the `v2` row contains `Current`, the `v1` row contains `Approved`.
  - `shows the diff between the two newest versions`: click `Show diff` → `GET B/articles/article-1/diff?from=version-1&to=version-2` → `makeVersionDiffOut()` → heading `Changes from v1 to v2`. Inside `Unified diff`, one span with `data-kind="removed"` contains `Old line` and one with `data-kind="added"` contains `New line`. Table `Field changes` row `CTA` has `<del>demo</del>` and `<ins>call</ins>`.
  - `compares chosen versions`: three versions (`version-3`, `version-2`, `version-1`) → `Compare from` `v1`, `Compare to` `v3` → `Show diff` → `GET …/diff?from=version-1&to=version-3`.
  - `views an older version read-only`: `View v1` → `GET B/articles/article-1/versions/version-1` → `makeVersionDetailOut({ id: 'version-1', versionNo: 1, resolutions: [{ findingId: 'claim:claim-1', action: 'fixed', note: 'Removed the figure.' }] })` → textbox `Version 1 Markdown` (lazy) has `aria-readonly="true"`; text `claim:claim-1: fixed — Removed the figure.`; `Close version` removes the heading `Version 1`.
  - `reports a missing version`: the diff → 404 `Version not found` → `Version not found.`
  - `says when only one version exists`: one version → `Only one version exists.`; no combobox `Compare from`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/articles/unified-diff.test.ts src/features/articles/components/review/versions-panels.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.3 version history and diff (UI); §10.5 sanitised preview with DOMPurify, versions and diff; §10.5 "Preview never renders raw model HTML (XSS fixture)".

### UI-15: Article review, publish panel

**Files.** Create `src/features/publishing/clipboard.ts`, `src/features/publishing/clipboard.test.ts`, `src/features/publishing/components/export-bundle-view.tsx`, `src/features/articles/components/review/publish-panel.tsx` and `src/features/articles/components/review/publish-panel.test.tsx`.

**Interfaces produced.**
```ts
export async function copyRichText(html: string, text: string): Promise<'rich' | 'plain'>
ExportBundleView({ bundle }: { bundle: ExportBundleOut })
PublishPanel({ article, onWorkflowStarted }: { article: ArticleDetailOut; onWorkflowStarted?(accepted: ActionAccepted): void })
```

**Behaviour rules.**
1. `copyRichText`:
   - When `typeof ClipboardItem === 'function'` and `navigator.clipboard.write` exists, it tries `navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([text], { type: 'text/plain' }) })])` and returns `'rich'`.
   - If that path is unavailable or rejects, it awaits `navigator.clipboard.writeText(text)` and returns `'plain'`. A rejection there propagates.
2. `PublishPanel` shows `Status: <label>`, plus `Approved <as draft|for publishing>` when `approvalMode` is set. When the status is before approval (not in `isApprovedOrLater`), it shows only `Publishing opens after approval.` and the publications table.
3. Export (`blog.publish` and `canExport`):
   - Button `Export` sends `exportArticle`, stores the bundle in state from `onSuccess`, then `toast.success('Export ready')` and `afterArticleChange`. Note: `Export can be repeated; it returns the same bundle for this version.`
   - A 422 `Publish validation failed` with an array detail → `role="alert"` `Fix these before exporting:` plus a list of `<field>: <message>`.
   - Other errors → `describeProblem(error, 'Could not export')`.
4. `ExportBundleView`:
   - `Title`, `Slug`, `Excerpt` with `CopyButton`s labelled `Title`, `Slug`, `Excerpt` (names `Copy title`, `Copy slug`, `Copy excerpt`).
   - Button `Copy article` → `copyRichText(bundle.html, bundle.text)`. `'rich'` → `toast.success('Article copied with formatting')`; `'plain'` → `toast.warning('Article copied as plain text (rich copy unavailable)')`; a rejection → `toast.error('Could not copy the article')`.
   - `Download bundle` → `downloadFile(`${slug}-bundle.json`, JSON.stringify(bundle, null, 2), 'application/json')`. `Download HTML` → `downloadFile(`${slug}.html`, bundle.html, 'text/html')`.
   - Read-only: `SEO title`, `Meta description`, `Tags`, `Category`, `<h3>Social copy</h3>` (`LinkedIn`, `X`, `Newsletter`, or `No social copy` when null), `<h3>References</h3>` (`S<n>` title links), and `<h3>Disclosure</h3>`.
5. Confirm published (`blog.publish` and `canConfirmPublished`):
   - Input `Published URL` (`type="url"`). A valid value matches `^https?://`, parses with `new URL`, and is ≤2000 characters; otherwise `Enter an http or https URL` and `Confirm published` is disabled.
   - `Confirm published` sends `confirmPublished`, then `toast.success('Marked as published')` and `afterArticleChange`.
6. Network publish (`blog.publish`, `canPublish`, and `usePublisherMode().network`):
   - `Checkbox` `Publish as draft` (default `article.approvalMode === 'draft'`) and a button `Publish to MDCopilot`, which opens `ConfirmDialog` (`Publish to MDCopilot?`, description `This sends version <versionNo> to the MDCopilot blog.`, confirm `Publish`).
   - Confirm sends `publishArticle(id, asDraft)`, then `toast.success('Publishing started')`, `afterWorkflowStarted(qc, id)`, `onWorkflowStarted?.(accepted)`. A 409 `Publishing disabled` or anything else → `describeProblem`.
   - Status PUBLISH_FAILED → `The last publish attempt failed. You can retry.`
7. Scheduling:
   - `blog.schedule` and `canSchedule` → button `Schedule` opens `ScheduleDialog` (mode `schedule`, `timeZone = localTimeZone()`, title = `selectedTitle ?? 'Untitled draft'`).
   - `blog.schedule` and `canUnschedule` → button `Unschedule` sends `unscheduleArticle`, then `toast.success('Unscheduled')` and `afterArticleChange`.
   - When `scheduledFor` is set: `Scheduled for <formatDateTime(scheduledFor, localTimeZone())> (<localTimeZone()>)`.
8. Publications (`publicationsQueryOptions`, label `publications`): columns `Publisher` (`Manual export`, `MDCopilot API`, `Null`), `Target`, `Status` (`humanizeKey`), `Attempts`, `Published URL` (link or `—`), `Last error` (a string `lastError.message`, else `JSON.stringify(lastError)`, else `—`), `Updated`. Empty → `No publications yet.`

**Tests to write first.**
- `clipboard.test.ts` (`afterEach(() => vi.restoreAllMocks())`):
  - `writes html and plain text`: spy on `navigator.clipboard.write` → returns `'rich'`; the single `ClipboardItem` has `types` `['text/html', 'text/plain']`, and its blobs read `<p>x</p>` and `x`.
  - `falls back to plain text when rich copy fails`: `write` rejects → `writeText` called with `'x'`; returns `'plain'`.
  - `falls back without ClipboardItem`: `vi.stubGlobal('ClipboardItem', undefined)` → returns `'plain'`, `write` not called.
  - `rejects when both fail`: both reject → the promise rejects.
- `publish-panel.test.tsx` (`afterEach(() => vi.restoreAllMocks())`; `GET B/articles/article-1/publications` → `[]` unless stated):
  - `exports and copies the article as rich text`: role publisher, `status: 'APPROVED'`, `POST …/export` → `makeExportBundleOut()`. `Export` → toast `Export ready`; `Copy article` → the spied `write` item's `text/html` blob reads `<p>Specialist access is a scheduling problem.</p>` and `text/plain` reads `Specialist access is a scheduling problem.`; toast `Article copied with formatting`.
  - `falls back to plain text`: `write` rejects → `writeText` called with the bundle `text`; toast `Article copied as plain text (rich copy unavailable)`.
  - `copies the slug`: `Copy slug` → `writeText` called with `widen-specialist-access`.
  - `downloads the bundle and the HTML`: spy `URL.createObjectURL` (→ `'blob:test'`), `URL.revokeObjectURL`, and `HTMLAnchorElement.prototype.click` (capturing `this`). `Download bundle` → anchor `download` is `widen-specialist-access-bundle.json` and `JSON.parse(await blob.text())` equals the bundle. `Download HTML` → `widen-specialist-access.html`, blob text equals `bundle.html`.
  - `lists export validation issues`: export → 422 `{ title: 'Publish validation failed', detail: [{ field: 'excerpt', message: 'too long' }] }` → alert `Fix these before exporting:` and item `excerpt: too long`.
  - `confirms the published URL`: `status: 'EXPORTED'`; `Published URL` `not a url` → `Enter an http or https URL`, `Confirm published` disabled. Then `https://www.mdcopilot.health/blog/widen-specialist-access` → `POST …/confirm-published` body `{ url: 'https://www.mdcopilot.health/blog/widen-specialist-access' }`, toast `Marked as published`.
  - `hides network publishing unless an admin session shows it on`: role publisher, APPROVED → no `Publish to MDCopilot`; no request to `B/settings`.
  - `publishes through the API when the network publisher is on`: admin; `GET B/settings` → `makeSettingsOut({ publishingEnabled: true, effective: { ...makeSettingsOut().effective, publisher: 'mdcopilot_api' } })`; APPROVED, `approvalMode: 'draft'` → `Publish as draft` is checked → `Publish to MDCopilot` → `Publish` → `POST …/publish` body `{ asDraft: true }`, toast `Publishing started`, `onWorkflowStarted` called once.
  - `schedules and unschedules`: role reviewer, APPROVED → `Schedule` present and `Export` absent. Rerendered with `status: 'SCHEDULED', scheduledFor: '2026-09-20T04:00:00Z'` → `Unschedule` → `POST …/unschedule`, toast `Unscheduled`; text `Scheduled for <formatDateTime('2026-09-20T04:00:00Z', localTimeZone())>` (substring).
  - `shows publications with errors`: `[makePublicationOut({ status: 'FAILED', lastError: { message: 'HTTP 502' } })]` → a row with `Manual export`, `Failed`, `HTTP 502`.
  - `shows only status and publications to a viewer`: role viewer, EXPORTED → no buttons `Export`, `Schedule`, `Unschedule`, `Confirm published`, `Publish to MDCopilot`.
  - `waits for approval`: READY_FOR_REVIEW → `Publishing opens after approval.`

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/publishing src/features/articles/components/review/publish-panel.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.6 ManualExportPublisher UI (rich-text clipboard `text/html` + `text/plain`, field copy buttons, download, confirm-published); §10.5 export/publish Vitest suite; schedule and unschedule.

### UI-16: Article review page shell

**Files.** Replace `src/routes/article-review-page.tsx`. Create `src/features/articles/article-polling.ts` and `src/features/articles/article-polling.test.ts`. Create in `src/features/articles/components/review/`: `article-header.tsx`, `action-bar.tsx`, `review-layout.tsx`. Create `src/routes/article-review-page.test.tsx`. Add `MUTATING_BUTTON_NAME` to `src/test/helpers.tsx`.

**Interfaces produced.**
```ts
export type PendingAction = { workflowName: string; startedAtMs: number; baselineUpdatedAt: string }
export function isPendingSettled(article: ArticleDetailOut | undefined, pending: PendingAction, nowMs: number): boolean
export function articleRefetchInterval(article: ArticleDetailOut | undefined, pending: PendingAction | null, nowMs: number, error: unknown): number | false
export const WORKFLOW_LABELS: Record<string, string>
ArticleHeader({ article }: { article: ArticleDetailOut })
ActionBar({ article, onWorkflowStarted }: { article: ArticleDetailOut; onWorkflowStarted(accepted: ActionAccepted): void })
ReviewLayout({ left, right }: { left: ReactNode; right: ReactNode })
// test/helpers.tsx
export const MUTATING_BUTTON_NAME: RegExp
```

**Behaviour rules.**
1. `isPendingSettled`: `true` when `nowMs − startedAtMs >= PENDING_ACTION_TIMEOUT_MS`, or when `article` is defined and `article.updatedAt !== baselineUpdatedAt`.
2. `articleRefetchInterval`:
   - `isUnauthorized(error)` → `false`.
   - A `pending` that is not settled → `ACTIVE_POLL_MS`.
   - `article` status in `IN_PROGRESS_ARTICLE_STATUSES` → `ACTIVE_POLL_MS`.
   - Otherwise `false`.
3. `WORKFLOW_LABELS`: `regenerate_component` → `regenerating a component`, `regenerate_article` → `regenerating the article`, `regenerate_research` → `regenerating research`, `recheck_article` → `re-checking the article`, `publish_article` → `publishing`, `change_topic` → `changing the topic`, `produce_article` → `producing the article`.
4. `ArticleReviewPage`:
   - It reads `articleId` from `useParams` and renders `PageHeader` (title `Article review`, description `Evidence on the left, the editable article on the right.`) before anything else.
   - `const [pending, setPending] = useState<PendingAction | null>(null)`. The query is `articleQueryOptions(articleId, (query) => articleRefetchInterval(query.state.data, pending, Date.now(), query.state.error))`; that callback runs outside render (fact 10).
   - `QueryState` label `article`, not-found `{ title: 'Article not found', message: 'Article not found.' }`.
   - `onWorkflowStarted(accepted)` (an event path) calls `setPending({ workflowName: accepted.workflowName, startedAtMs: Date.now(), baselineUpdatedAt: article.updatedAt })`.
   - While `pending` is set and `article.updatedAt === pending.baselineUpdatedAt`: a `role="status"` `Working: <WORKFLOW_LABELS[name] ?? name>…`.
   - Else, when the status is in `IN_PROGRESS_ARTICLE_STATUSES`: `role="status"` `Pipeline step in progress: <status label>`.
   - Then `ArticleHeader`, `ActionBar`, and `ReviewLayout` with:
     - left: Radix `Tabs` (list label `Evidence`, default `Quality`) with `Topic`, `Research`, `Sources`, `Claims`, `Quality`, `Summary` → UI-12 panels;
     - right: `Tabs` (list label `Editor`, default `Edit`) with `Edit`, `Preview`, `Headline`, `SEO`, `Versions`, `Publish` → UI-13 to UI-15 panels. `PublishPanel` receives `onWorkflowStarted`.
   - Inactive tab content is unmounted (Radix default), so a tab's requests start only when it opens.
5. `ArticleHeader`:
   - `<h2>` = `selectedTitle ?? titleOptions?.operational ?? 'Untitled draft'`; `ArticleStatusBadge`; `Pipeline: <pipelineStatus>`; `Version <versionNo>` or `No version yet`; `Pillar <pillar>`; `Category <category>`.
   - `Approved <formatDateTime(approvedAt)> as <draft|for publishing>` when `approvedAt` is set; `Scheduled for <…>` when `scheduledFor` is set; link `Published post` → `publishedUrl` when set; `Rejected: <rejectionReason>` when REJECTED.
   - `Cost <formatUsd(totalUsd)>` from `costsQueryOptions({ groupBy: 'article', from: article.createdAt, articleId: article.id })`, or `Cost —` while pending or on error.
   - Link `Run in Agent Runs` → `/agent-runs?runId=<runId>` when `useCan('blog.agent_runs')`.
   - Banners: SUPERSEDED → `This article was superseded by a topic change.`; FAILED → `Production failed. Regenerate research or check Agent Runs.`
6. `ActionBar` renders only permitted buttons:
   - `Re-check` (`blog.generate`, `canRecheck`) sends `recheckArticle`, then `toast.success('Re-check started')`, `afterWorkflowStarted`, `onWorkflowStarted`. Errors → `describeProblem`.
   - `Approve`: rendered when `blog.approve` and (`canApprove(status)` or (`canOverrideApprove(status)` and `useIsAdmin()`)). It is enabled when (READY_FOR_REVIEW and `!recheckRequired` and `gatesPassedOnCurrentVersion`) or (QUALITY_GATE_FAILED and `!recheckRequired`). When disabled, `aria-describedby` points at `Re-check required before approval` (if `recheckRequired`) or `Quality gates have not passed on this version`. It opens `ApproveDialog`.
   - `Reject` (`blog.review`, `canReject`) opens `RejectArticleDialog`.
   - `Regenerate` (`blog.generate`, and `canRegenerate(status, 'article')` or `canRegenerate(status, 'research')`) opens `RegenerateDialog`, with `onStarted = onWorkflowStarted`.
7. `ReviewLayout` uses the generated `components/ui/resizable.tsx` wrapper exactly as its props are named in that file: a horizontal group with a left panel (default size 45) and a right panel (default 55), and a handle between them, with each pane in `<section aria-label="Evidence pane">` / `<section aria-label="Editor pane">`. If the first red→green run shows `react-resizable-panels` throwing in jsdom, replace the group with `<div className="grid gap-4 lg:grid-cols-[minmax(0,45fr)_minmax(0,55fr)]">` holding the same two sections, and note this in the track report.
8. `MUTATING_BUTTON_NAME = /^(Generate|Select|Regenerate|Edit topic|Reject|Approve|Override|Save|Re-check|Export|Copy article|Confirm published|Publish|Schedule|Unschedule|Move|Change topic|Cancel run|Cancel slot|Restore slot|Restart|Resume|Retry|Add|Invite|Use this title|Start|Mark all read)/`. `Mark all read` is allowed for viewers but appears only in an open menu, so it never matches in page scans.

**Tests to write first.**
- `article-polling.test.ts` (fixed `t = 1_000_000`):
  - `does not poll a settled article`: `articleRefetchInterval(makeArticleDetailOut(), null, t, null) === false`.
  - `polls in-progress statuses`: `status: 'DRAFTING'` → `3000`; `status: 'PUBLISHING'` → `3000`.
  - `polls a pending action until the article changes`: `pending = { workflowName: 'recheck_article', startedAtMs: t, baselineUpdatedAt: '2026-09-17T01:45:00Z' }` → `3000`. With `updatedAt: '2026-09-17T02:10:00Z'` → `false`. With `nowMs = t + 600_000` → `false`. With `article` undefined → `3000`.
  - `stops after a 401`: a DRAFTING article with `new ApiError(401, {})` → `false`.
- `src/routes/article-review-page.test.tsx`, using `renderRoutes([{ path: '/articles/:articleId', element: <ArticleReviewPage /> }], { initialEntries: ['/articles/article-1'], session })` after `setCsrfToken`. Unless stated, mock `GET B/articles/article-1` → `makeArticleDetailOut()`, `GET B/articles/article-1/quality-gates` → `makeQualityGatesOut()`, and `GET B/metrics/costs?groupBy=article&from=2026-09-17T01%3A30%3A00Z&articleId=article-1` → `makeCostReportOut({ groupBy: 'article', totalUsd: '0.420000', rows: [] })`. Test timeout 15 000 ms.
  - `renders the heading before loading and reports a missing article`: the article request → 404 `Article not found`. `screen.getByRole('heading', { level: 1, name: 'Article review' })` succeeds synchronously right after render; then `Article not found.`
  - `shows the header, both panes and the default tabs`: heading `How clinics can widen specialist access` (level 2), `Ready for review`, `Version 2`, `Cost $0.4200`. Tablist `Evidence` has selected tab `Quality`; tablist `Editor` has selected tab `Edit`; textbox `Article Markdown` found (timeout 5000).
  - `approves a ready article`: role reviewer; `POST …/approve` → `makeArticleStateOut()` → `Approve` → dialog → `Approve` → body `{ mode: 'draft', versionId: 'version-2', overrideReason: null }`, toast `Article approved`, the article GET called at least twice.
  - `explains why Approve is disabled`: `recheckRequired: true` → button `Approve` disabled with accessible description `Re-check required before approval`.
  - `lets an admin override a gate-failed version`: admin, `GET B/settings` → `makeSettingsOut()`, `status: 'QUALITY_GATE_FAILED'` → `Approve` enabled → dialog → `Override reason` `Reviewed manually` → `Override and approve` → body `overrideReason: 'Reviewed manually'`.
  - `hides Approve from a non-admin on a gate-failed version`: role reviewer, QUALITY_GATE_FAILED → no `Approve` button.
  - `re-checks and polls until the article changes`: role editor; `POST …/recheck` → `makeActionAccepted({ workflowName: 'recheck_article' })`. The article handler counts calls: calls 1–2 return the default, call 3 onward returns `updatedAt: '2026-09-17T02:10:00Z'`. Click `Re-check` → toast `Re-check started`; status `Working: re-checking the article…`; `await waitFor(() => expect(screen.queryByText(/Working: re-checking the article/)).not.toBeInTheDocument(), { timeout: 8000 })`; the article GET called at least 3 times.
  - `rejects with a reason`: role reviewer; `POST …/reject` → `makeArticleStateOut({ status: 'REJECTED' })` → `Reject` → `Reason` `Off-brand tone` → `Reject article` → body `{ reason: 'Off-brand tone' }`, toast `Article rejected`.
  - `regenerates a section from the action bar`: role editor; `POST …/regenerate` → `makeActionAccepted()` → `Regenerate` → Component `Section`, Section `Evidence` → `Start regeneration` → body `{ component: 'section', sectionKey: 'evidence', instructions: null }`; status `Working: regenerating a component…`.
  - `shows no mutating controls to a viewer anywhere on the page`: role viewer. Also mock topics (`GET B/topics?runId=run-1`), research packets, sources, fact-check, preview, versions and publications with their builders. Click every tab in `Evidence` and `Editor`; after each click, wait for the panel's data, then assert `screen.queryAllByRole('button', { name: MUTATING_BUTTON_NAME })` has length 0. In the `Edit` tab, the textbox `Article Markdown` has `aria-readonly="true"`.
  - `shows the superseded banner`: `status: 'SUPERSEDED'` → `This article was superseded by a topic change.`
  - `links reviewers to Agent Runs`: role reviewer → link `Run in Agent Runs` href `/agent-runs?runId=run-1`; role editor → no such link.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/articles/article-polling.test.ts src/routes/article-review-page.test.tsx` → red → green. Then `npm test` (all earlier tasks still green), lint and typecheck exit 0.

**Acceptance covered.** §10.5 article review split screen (both panes), every review action wired with role-aware visibility (re-check, approve incl. admin override, reject with reason, regenerate), review/approve/reject/regenerate Vitest suites, viewer sees no mutating controls; §10.8 per-article cost on the article page; accessible names for INT's Playwright smoke.

### UI-17: Content Calendar

**Files.** Replace `src/routes/calendar-page.tsx`. Create `src/features/calendar/calendar-events.ts`, `src/features/calendar/calendar-events.test.ts`, `src/features/calendar/components/month-calendar.tsx` (lazy target), `src/features/calendar/components/day-dialog.tsx` and `src/routes/calendar-page.test.tsx`.

**Interfaces produced.**
```ts
export const ENTRY_KIND_LABELS: Record<CalendarEntryKind, string>
export type CalendarEventInput = { id: string; title: string; start: string; allDay: true; extendedProps: { date: string; entryIndex: number } }
export function toCalendarEvents(month: CalendarMonthOut): CalendarEventInput[]
export function monthFromViewStart(currentStart: Date): string
MonthCalendar({ month, data, onMonthChange, onOpenDay }: { month: string; data: CalendarMonthOut; onMonthChange(month: string): void; onOpenDay(date: string): void })
DayDialog({ day, month, timeZone, open, onOpenChange }: { day: CalendarDayOut; month: string; timeZone: string; open: boolean; onOpenChange(open: boolean): void })
```

**Behaviour rules.**
1. `ENTRY_KIND_LABELS`: `published` → `Published`, `scheduled` → `Scheduled`, `exported` → `Exported`, `draft` → `Draft`, `research` → `Research`, `planned` → `Planned`.
2. `toCalendarEvents` emits one event per entry whose kind is not `planned`, in day order and then entry order: `{ id: `${date}:${index}`, title: `${ENTRY_KIND_LABELS[kind]}: ${title}`, start: date, allDay: true, extendedProps: { date, entryIndex: index } }`. Events are placed on the server-assigned `CalendarDayOut.date` (already in the settings zone), and the calendar runs in `timeZone="UTC"`, so the browser's zone never moves an entry to another day.
3. `monthFromViewStart(d)` is `d.toISOString().slice(0, 7)`.
4. `MonthCalendar` renders `<FullCalendar>` with:
   - `plugins={[dayGridPlugin, listPlugin]}`, `initialView="dayGridMonth"`, `initialDate={`${month}-01`}`, `timeZone="UTC"`, `fixedWeekCount={false}`;
   - `headerToolbar={{ left: 'prev,next today', center: 'title', right: 'dayGridMonth,listMonth' }}`;
   - `events={toCalendarEvents(data)}`, `editable={false}`;
   - `eventClick={(arg) => onOpenDay(arg.event.extendedProps.date)}`;
   - `datesSet={(arg) => { const m = monthFromViewStart(arg.view.currentStart); if (m !== month) onMonthChange(m) }}`;
   - `dayCellContent`: for a date present in `data.days`, `<button type="button" aria-label={`Open day ${iso}`} onClick={() => onOpenDay(iso)}>` holding the day number and a tag (`Cancelled` when `slotStatus === 'cancelled'`, else `Pillar <plannedPillar>` when set). Other-month cells show only the number. `iso = arg.date.toISOString().slice(0, 10)`.
   Drag and `dateClick` are not used (fact 2). The interaction plugin is not imported.
5. `CalendarPage`:
   - `PageHeader`: title `Content Calendar`, description `Published, scheduled, exported, draft and research items, with the planned pillar rotation.`
   - `month` is the `month` search param when it matches `^\d{4}-\d{2}$`, else `const [fallbackMonth] = useState(() => monthOf(new Date().toISOString(), localTimeZone()))`. `onMonthChange` sets the `month` search param.
   - `calendarQueryOptions(month)` in `QueryState` label `calendar`, then `Times in <timezone>`, a legend list of the six kind labels, and the lazy `MonthCalendar` (C8, fallback `Loading calendar`).
   - `selectedDate` state; the matching `CalendarDayOut` opens `DayDialog`.
6. `DayDialog` (title `Day <date>`):
   - `Planned pillar: <plannedPillar ?? 'none'>`, plus ` (override)` when `isOverride`; a `Cancelled` badge when cancelled; `Note: <note>` when set.
   - An entries list, where each item shows `<kind label>: <title>`, the status (`ARTICLE_STATUS_LABELS` for article statuses, else the raw status) and `formatDateTime(at, timeZone)` when `at` is set. Links: `Open article: <title>` → `/articles/<articleId>` when `articleId` is set; `Open research: <title>` → `/research?researchRunId=<researchRunId>` when set.
   - With `blog.schedule`:
     - `pillarsQueryOptions()` feeds a Radix `Select` `Planned pillar` listing active pillars as `<key> — <name>`. Choosing one sends `updateSlot(date, { pillar })`.
     - `Cancel slot` (when not cancelled) sends `{ status: 'cancelled' }`; `Restore slot` (when cancelled) sends `{ status: 'planned' }`.
     - Textarea `Note` (initial `note ?? ''`) and `Save note` send `{ note: text.trim() || null }`.
     - Success: `toast.success('Slot updated')` and invalidate `['calendar', month]`. 422 `Pillar required` → `toast.error('Pillar required: choose a pillar for this date first.')`. Other errors → `describeProblem(error, 'Could not update the slot')`.
   - Entry actions (all names end with `: <title>`):
     - `scheduled` with `blog.schedule`: `Move: <title>` opens `ScheduleDialog` (mode `move`, `timeZone`), and `Unschedule: <title>` sends `unscheduleArticle`, then `toast.success('Unscheduled')` and `afterArticleChange`.
     - `draft` with status APPROVED and `blog.schedule`: `Schedule: <title>` opens `ScheduleDialog` (mode `schedule`).
     - `draft` with status READY_FOR_REVIEW or QUALITY_GATE_FAILED and `blog.generate`: `Regenerate article: <title>` opens `RegenerateDialog` (`initialComponent: 'article'`, status from the entry).
   - Without `blog.schedule`, no pillar request is made.

**Tests to write first.**
- `calendar-events.test.ts`:
  - `builds all-day events from entries`: `toCalendarEvents(makeCalendarMonthOut())` equals `[{ id: '2026-09-15:0', title: 'Published: Scarcity', start: '2026-09-15', allDay: true, extendedProps: { date: '2026-09-15', entryIndex: 0 } }, { id: '2026-09-20:0', title: 'Scheduled: Access', start: '2026-09-20', allDay: true, extendedProps: { date: '2026-09-20', entryIndex: 0 } }]`.
  - `skips planned entries`: a day with one `planned` entry adds no event.
  - `reads the month from the view start`: `monthFromViewStart(new Date('2026-10-01T00:00:00Z')) === '2026-10'`.
- `src/routes/calendar-page.test.tsx` (`GET B/calendar?month=2026-09` → `makeCalendarMonthOut()`; `url: '/calendar?month=2026-09'`; `afterEach` `vi.useRealTimers()` and `vi.restoreAllMocks()`):
  - `renders the heading before the calendar loads`: heading `Content Calendar` found synchronously after render.
  - `shows the month's entries`: `findByText('Published: Scarcity', {}, { timeout: 5000 })`, `Scheduled: Access`, `Times in Asia/Kolkata`.
  - `moves to the next month`: click `Next month` → `GET B/calendar?month=2026-10` called; `router.state.location.search === '?month=2026-10'`.
  - `opens a day and cancels its slot`: role reviewer; `GET B/pillars` → `PILLARS`; `PATCH B/calendar/slots/2026-09-16` → the 2026-09-16 day with `slotStatus: 'cancelled'`. `Open day 2026-09-16` → dialog `Day 2026-09-16` → `Cancel slot` → body `{ status: 'cancelled' }`, toast `Slot updated`, the calendar GET called at least twice.
  - `changes the planned pillar`: the same day → `Planned pillar` `B — Cognitive Architecture & Physician Reasoning` → body `{ pillar: 'B' }`.
  - `explains a missing pillar`: PATCH → 422 `Pillar required` → toast `Pillar required: choose a pillar for this date first.`
  - `saves a note`: `Note` `Holiday` → `Save note` → body `{ note: 'Holiday' }`.
  - `moves a scheduled article`: role reviewer; `vi.useFakeTimers({ toFake: ['Date'] })`, `vi.setSystemTime(new Date('2026-09-17T00:00:00Z'))`; `POST B/articles/article-1/unschedule` → `makeArticleStateOut()`, `POST …/schedule` → `makeArticleStateOut({ status: 'SCHEDULED' })`. `Open day 2026-09-20` → `Move: Access` → Date `2026-09-25`, Time `09:30` → `Move` → POST order unschedule then schedule; schedule body `{ at: '2026-09-25T09:30:00+05:30' }`; toast `Scheduled for 2026-09-25 09:30 (Asia/Kolkata)`.
  - `opens the day of a clicked event`: click `Published: Scarcity` → dialog `Day 2026-09-15` with link `Open article: Scarcity` href `/articles/article-9`.
  - `shows entries without controls to a viewer`: role viewer → `Open day 2026-09-20` → no button matching `/^(Move|Unschedule|Schedule|Regenerate article|Cancel slot|Restore slot|Save note)/`; no combobox `Planned pillar`; no request to `B/pillars`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/calendar src/routes/calendar-page.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 Content Calendar (FullCalendar month/list; published, scheduled, exported, draft, research and planned slots; move, schedule, change pillar, cancel, regenerate).

### UI-18: Settings

**Files.** Replace `src/routes/settings-page.tsx`. Create `src/features/settings/settings-values.ts` and `src/features/settings/settings-values.test.ts`. Create in `src/features/settings/components/`: `settings-editor.tsx` (General and Models tabs), `brand-form.tsx`, `pillars-form.tsx`, `price-overrides.tsx`, `users-admin.tsx`, `provider-keys.tsx`. Add `toPillarIn(p: PillarOut): PillarIn` to `src/features/settings/api.ts` (with a row in its `api.test.ts`). Create `src/routes/settings-page.test.tsx`.

**Interfaces produced.**
```ts
export const AGENT_ROUTE_KEYS: readonly ['search','research','ideation','deep_research','writer','fact_check','clinical','editorial','seo']
export const PROMPT_NAMES: readonly ['research/synthesize','ideation/topics','deep_research/packet','writer/draft','writer/revise','writer/component','fact_check/check','clinical/review','editorial/review','seo/package']
export const DAY_NAMES: readonly ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
export type SettingsForm = Pick<EffectiveConfig, 'schedule' | 'topicSelectionMode' | 'wordCount' | 'defaultCategory' | 'siteUrl' | 'publisher' | 'routes' | 'promptVersions' | 'scoreWeights' | 'novelty' | 'research' | 'gateOverridePolicy'>
export function stableStringify(value: unknown): string
export function formFromEffective(effective: EffectiveConfig): SettingsForm
export function buildSettingsValues(stored: SettingsValues, effective: EffectiveConfig, form: SettingsForm): SettingsValues
export function scoreWeightSum(weights: ScoreWeights): number
export function validateSettingsForm(form: SettingsForm): string[]
export function parseLines(text: string): string[]
export function weekdayConflicts(pillars: PillarIn[]): string[]
SettingsEditor({ settings }: { settings: SettingsOut }); BrandForm({ brand }); PillarsForm({ pillars }); PriceOverrides(); UsersAdmin(); ProviderKeys({ settings })
```

**Behaviour rules.**
1. `stableStringify` is JSON with object keys sorted recursively. "Equal" below means equal `stableStringify` output.
2. `buildSettingsValues` starts from `{ ...stored }`.
   - For each key `schedule, topicSelectionMode, wordCount, defaultCategory, siteUrl, publisher, promptVersions, scoreWeights, novelty, research, gateOverridePolicy`: `next[k] = equal(form[k], effective[k]) ? stored[k] : form[k]`. A changed nested block is stored whole (CONTRACT §5.4).
   - `routes`: `changed = AGENT_ROUTE_KEYS.filter((a) => !equal(form.routes[a], effective.routes[a]))`. `next.routes = changed.length === 0 ? stored.routes : { ...(stored.routes ?? {}), ...Object.fromEntries(changed.map((a) => [a, form.routes[a]])) }`.
   - `diversity` and `noveltyThreshold` stay as stored.
3. `validateSettingsForm` returns the messages that apply, in this order:
   - `Daily run time must be HH:MM (24-hour)` (fails `^([01]\d|2[0-3]):[0-5]\d$`);
   - `Unknown time zone` (`!isValidTimeZone`);
   - `Word count minimum must be at least 1 and below the maximum`;
   - `Weights must add up to 1 (now <sum.toFixed(2)>)` when `|sum − 1| > 1e-6`;
   - `Novelty threshold must be between 0 and 1`;
   - `Research window and minimum sources must be at least 1`;
   - `Route for <agent> needs provider:model lines` for each agent whose route is empty or has an entry failing `^[a-z]+:\S+$`;
   - `Website must be an http or https URL`;
   - `Default category must be 1–100 characters`;
   - `Prompt versions must be whole numbers of at least 1`.
4. `parseLines` splits on `\n`, trims, and drops empties. `weekdayConflicts` returns, for each weekday 0..6 claimed by more than one active pillar, `<DAY_NAMES[d]> is assigned to more than one active pillar (<keys joined ', '>)`.
5. `SettingsPage` renders `PageHeader` (title `Settings`, description `Pipeline configuration, models, brand, pillars, themes, costs, users and keys. Changes are versioned.`) and Radix `Tabs` (list label `Settings sections`): `General` (default), `Models`, `Brand`, `Pillars`, `Themes`, `Costs`, `Users`, `Keys`. `General` and `Models` share one `SettingsEditor` state: the tabs sit inside `SettingsEditor`, keyed by `settings.version ?? 0` (C7), so switching between them keeps unsaved edits.
6. `SettingsEditor`, General tab:
   - `<dl aria-label="Safety switches">`:
     - `Human approval` → `Required (locked)`.
     - `Automatic publishing` → a disabled, unchecked `Switch` named `Automatic publishing` plus `Not available in this release`.
     - `Agent`, `Scheduler`, `Network publishing`, `Mock mode`, `Gemini grounding` → `On`/`Off`.
     - `App version`.
     - Note: `These switches are set in .env and cannot be changed here.`
   - Inputs: `Daily run time` (`type="time"`), `Timezone` (text with a `<datalist>` of `Intl.supportedValuesOf('timeZone')` plus `Asia/Kolkata` and `UTC`).
   - Radios `Automatic` / `Manual` (legend `Topic selection`).
   - `Minimum words`, `Maximum words`, `Research window (days)`, `Minimum sources`, `Novelty threshold`.
   - Weights `Timeliness weight`, `Novelty weight`, `Evidence weight`, `MDCopilot relevance weight`, `Audience weight`, `Editorial weight`, with the live text `Sum <scoreWeightSum.toFixed(2)>`.
   - `Select` `Publisher` (`Manual export`, `MDCopilot API`, `None (records only)`), `Default category`, `Website`.
   - Radios `Admin with a written reason` / `Never` (legend `Gate override`).
   - `Save settings`.
7. `SettingsEditor`, Models tab: one textarea `Route for <agent>` per `AGENT_ROUTE_KEYS` (lines = entries), and one input `Prompt version for <prompt>` per `PROMPT_NAMES` (blank = latest; values build `promptVersions` from non-blank entries). `Save settings` appears here too.
8. Saving settings:
   - The messages from rule 3 show in a `role="alert"` list. `Save settings` is disabled while there are messages, nothing changed, or a save is pending.
   - It sends `saveSettings({ expectedVersion: settings.version, values: buildSettingsValues(settings.values, settings.effective, form) })`, then `qc.setQueryData(['settings'], response)` and `toast.success('Settings saved (version <response.version>)')`. When `schedule` changed, also `toast.info('The worker will apply the new daily schedule.')`.
   - A 409 `Settings version conflict` → `role="alert"` `Settings changed since you loaded them. Reload to continue.` and a button `Reload settings` that invalidates `['settings']`. Other errors → `describeProblem(error, 'Could not save settings')`.
9. `BrandForm` (keyed by `brand.version`):
   - Inputs `Brand name`, `Description`, `Target audience`, `Mission`, `Narrative`. Textareas (one item per line) `Focus areas`, `Emphasis`, `Tone`, `Avoid`, `Prohibited language`. Inputs `Default CTA`, `Website URL`, `Target minimum words`, `Target maximum words`. Textarea `AI disclosure`.
   - Both word targets blank → `targetWordCount: null`. Otherwise both are required with `min < max`, else `Target word count needs a minimum below the maximum`. A blank `AI disclosure` → `AI disclosure is required`.
   - `Save brand` is disabled while invalid or unchanged. It sends `saveBrand({ expectedVersion: brand.version, values })`, then `setQueryData(['settings', 'brand'])` and `toast.success('Brand profile saved (version <n>)')`.
   - 409 `Brand profile version conflict` → alert `The brand profile changed since you loaded it. Reload to continue.` with button `Reload brand`. Other errors → `describeProblem`.
10. `PillarsForm` (keyed by the query's `dataUpdatedAt`):
    - Per pillar, `<fieldset>` legend `Pillar <key>`: `Name for pillar <key>`, `Description for pillar <key>`, `Topics for pillar <key>` (lines), `Checkbox` `<Day> for pillar <key>` for each of the seven days, `Switch` `Active: pillar <key>`, `Sort order for pillar <key>`.
    - `weekdayConflicts` messages show as an alert. `Save pillars` is disabled while there are conflicts, blank names, nothing changed, or a save is pending.
    - It sends `savePillars({ items })`, then `setQueryData(['pillars'])`, invalidates `['calendar']`, and `toast.success('Pillars saved')`. A 422 `Pillar rotation invalid` or anything else → `describeProblem`.
11. Themes tab: `<ThemesEditor readOnly={false} />`.
12. `PriceOverrides`:
    - Table caption `Price overrides`: columns `Provider`, `SKU`, `Input $/MTok`, `Output $/MTok`, `Cache read $/MTok`, `Per 1k calls`, `Effective from` (`formatDateTime(…, 'UTC')`), `Version`, `Note`.
    - `<h3>Add price override</h3>`: `Select` `Provider` (`OpenAI`, `Google`, `Anthropic`), `SKU`, `Input per MTok`, `Output per MTok`, `Cache read per MTok`, `Per 1k calls`, `Effective date` (`type="date"`), `Effective time (UTC)` (default `00:00`), `Note`. Note text: `Search fees use the SKU web_search_call.`
    - Validation: SKU 1..128 → `SKU must be 1–128 characters`. Each price blank or matching `^\d+(\.\d{1,6})?$` → `Prices must be non-negative numbers with up to 6 decimals`. At least one of input, output or per 1k calls → `Enter an input, output or per-1k-calls price`. A date is required → `Choose an effective date`.
    - `Add override` sends `createPriceOverride({ provider, sku, inputPerMtok, outputPerMtok, cacheReadPerMtok, per1kCalls, effectiveFrom: `${date}T${time}:00Z`, note })`, with blank prices and note as `null` and prices as the trimmed strings. Then `toast.success('Price override added')`, invalidate `['settings', 'price-overrides']`, reset the form. A 409 `Price override exists` or anything else → `describeProblem`.
13. `UsersAdmin`:
    - Table columns `Email`, `Name`, `Role`, `Active`, `Last login`. Per row: `Select` `Role for <email>` → `updateUser(id, { role })` → toast `Role updated`; `Switch` `Active: <email>` → `{ isActive }` → toast `User activated` or `User deactivated`; button `Reset password for <email>` opens a dialog (title `Reset password`, input `New password`, button `Set password`) → `{ password }` → toast `Password updated`.
    - `<h3>Invite user</h3>`: `Email`, `Display name`, `Select` `Role`, `Password` (all required), button `Invite user` → `createUser` → toast `User created`, reset.
    - Every success invalidates `['users']`. Errors → `describeProblem(error, 'Could not update the user')`, which covers `User already exists`, `You cannot change your own role`, and the self-deactivate 409.
14. `ProviderKeys`: `<dl aria-label="Provider keys">` with one term per `providers` key (`openai` → `OpenAI`, `gemini` → `Gemini`, `anthropic` → `Anthropic`, `ncbi` → `NCBI`, `openaiAdmin` → `OpenAI admin`, others via `humanizeKey`) and the value `Configured (<preview>)` or `Not configured`. Note: `Keys are set in .env and are never shown in full.` No inputs.

**Tests to write first.**
- `settings-values.test.ts` (`effective = makeSettingsOut().effective`, `stored = makeSettingsOut().values`):
  - `keeps stored values when nothing changed`: `buildSettingsValues(stored, effective, formFromEffective(effective))` equals `stored`.
  - `stores a changed schedule block whole`: the form with `schedule.time = '08:30'` → `next.schedule` equals `{ time: '08:30', timezone: 'Asia/Kolkata' }`; every other key equals `stored`.
  - `merges only changed agent routes`: `stored.routes = { seo: ['google:gem-s2'] }` and `effective.routes.seo = ['google:gem-s2']`; the form's writer route is `['openai:gpt-w2', 'google:gem-w']` → `next.routes` equals `{ seo: ['google:gem-s2'], writer: ['openai:gpt-w2', 'google:gem-w'] }`.
  - `leaves diversity and the legacy novelty threshold alone`: `stored.noveltyThreshold = 0.8` and `stored.diversity = makeDiversityConfig()` → both unchanged in `next`.
  - `validates the form`: timezone `Mars/Base` → includes `Unknown time zone`; weights summing to 1.1 → includes `Weights must add up to 1 (now 1.10)`; writer route `['gpt-x']` → includes `Route for writer needs provider:model lines`; time `7am` → includes `Daily run time must be HH:MM (24-hour)`; the untouched form → `[]`.
  - `finds weekday conflicts`: A `[0]` and B `[0, 1]` (both active) → `['Monday is assigned to more than one active pillar (A, B)']`; with B inactive → `[]`.
- `src/routes/settings-page.test.tsx` (role admin; `GET B/settings` → `makeSettingsOut()` unless stated):
  - `loads effective settings into the General tab`: `Daily run time` has value `07:00`, `Timezone` `Asia/Kolkata`, `Minimum words` `850`; text `Sum 1.00`.
  - `shows locked safety switches`: `Required (locked)`; switch `Automatic publishing` is disabled and not checked; `Not available in this release`.
  - `saves a changed daily time as a versioned update`: `PUT B/settings` → `makeSettingsOut({ version: 4 })`. `Daily run time` → `08:30` → `Save settings` → body `{ expectedVersion: 3, values: { ...makeSettingsOut().values, schedule: { time: '08:30', timezone: 'Asia/Kolkata' } } }`; toasts `Settings saved (version 4)` and `The worker will apply the new daily schedule.`
  - `reports a version conflict`: PUT → 409 `Settings version conflict` → alert `Settings changed since you loaded them. Reload to continue.`; `Reload settings` → the settings GET called at least twice.
  - `blocks invalid values`: `Timezone` → `Mars/Base` → `Unknown time zone`; `Save settings` disabled.
  - `saves a model route change`: tab `Models` → `Route for writer` replaced with `openai:gpt-w2\ngoogle:gem-w` → `Save settings` → body `values.routes` equals `{ writer: ['openai:gpt-w2', 'google:gem-w'] }`.
  - `keeps General edits when switching tabs`: `Minimum words` `900` → tab `Models` → tab `General` → `Minimum words` value `900`.
  - `shows masked keys without inputs`: tab `Keys` → `OpenAI` with `Configured (sk-…abcd)`, `Gemini` with `Not configured`; no textbox inside the `Keys` tabpanel.
  - `saves the brand profile`: tab `Brand`, `GET B/settings/brand` → `makeBrandProfileOut()`, `PUT B/settings/brand` → `makeBrandProfileOut({ version: 3 })`. `Default CTA` → `New CTA` → `Save brand` → body `{ expectedVersion: 2, values: { ...makeBrandProfileOut().values, cta: 'New CTA' } }`; toast `Brand profile saved (version 3)`.
  - `requires the AI disclosure`: clear `AI disclosure` → `AI disclosure is required`; `Save brand` disabled.
  - `flags weekday conflicts in pillars`: tab `Pillars`, `GET B/pillars` → `PILLARS` → check `Monday for pillar B` → alert `Monday is assigned to more than one active pillar (A, B)`; `Save pillars` disabled.
  - `saves pillars`: `Name for pillar A` → `Access` → `Save pillars` → `PUT B/pillars` body `items` has 6 entries and `items[0]` equals `{ ...toPillarIn(PILLARS[0]), name: 'Access' }`; toast `Pillars saved`.
  - `adds a price override`: tab `Costs`, `GET B/settings/price-overrides` → `[makePriceOverrideOut()]`, `POST` → `makePriceOverrideOut({ id: 'override-2' })`. `Provider` `OpenAI`, `SKU` `web_search_call`, `Per 1k calls` `10`, `Effective date` `2026-10-01` → `Add override` → body `{ provider: 'openai', sku: 'web_search_call', inputPerMtok: null, outputPerMtok: null, cacheReadPerMtok: null, per1kCalls: '10', effectiveFrom: '2026-10-01T00:00:00Z', note: null }`; toast `Price override added`.
  - `requires a price`: SKU and date without any price → `Enter an input, output or per-1k-calls price`; `Add override` disabled.
  - `manages users`: tab `Users`, `GET /api/admin/users` → `[makeUserOut()]`. `Role for editor@example.com` → `Reviewer` → `PATCH /api/admin/users/user-2` body `{ role: 'reviewer' }`, toast `Role updated`. Invite `new@example.com` / `New` / `Viewer` / `pw` → `POST /api/admin/users` body `{ email: 'new@example.com', displayName: 'New', role: 'viewer', password: 'pw' }`; a second invite answered 409 `User already exists` → toast `User already exists`.
  - `edits themes from Settings`: tab `Themes`, `GET B/themes` → `[makeThemeOut()]` → a textbox `Name` with value `Prior authorization`.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/settings src/routes/settings-page.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 Settings (all §19/§13 fields, routes per agent, brand incl. prohibited language and disclosure, pillars and rotation, themes, schedule time/timezone with the apply-schedule notice, masked keys, human approval locked ON, auto-publish locked OFF); §10.8 price-override UI; users admin (§4.12 `/api/admin/users`).

### UI-19: Agent Runs

**Files.** Replace `src/routes/agent-runs-page.tsx`. Extend `src/routes/agent-runs-page.test.tsx`, keeping its three Phase 1 tests unchanged. Create in `src/features/agent-runs/components/`: `run-detail.tsx`, `step-timeline.tsx`, `agent-run-table.tsx`, `llm-calls-dialog.tsx`, `latency-table.tsx`.

**Interfaces produced.** `RunDetailPanel({ runId }: { runId: string })`, `StepTimeline({ run }: { run: RunDetail })`, `AgentRunTable({ runId }: { runId: string })`, `LlmCallsDialog({ agentRunId, open, onOpenChange })`, `LatencyTable()`.

**Behaviour rules.**
1. The header is `PageHeader` with title `Agent Runs`. Its description is the Phase 1 summary: `Showing <n> of <total> runs, newest first.` once loaded, otherwise `Pipeline runs, newest first.`
2. A Radix `Select` named `Status` offers `All statuses` plus the eight `RunStatus` values. It sets the `status` search param. The list query is `runsQueryOptions(50, status)`, so with no filter the URL stays `B/runs?limit=50`.
3. `RunsTable` keeps `showRunId`. `renderActions` renders two things per row:
   - a button with visible text `Details` and `aria-label` `Details for run <id>`, which sets the `runId` search param;
   - the Phase 1 `Cancel` button (`aria-label` `Cancel run <id>`), shown only with `blog.generate` for non-terminal runs. It calls `cancelRun`, toasts `Run cancelled`, then `afterRunChange`.
4. `RunDetailPanel` is shown when `runId` is set. It uses `runDetailQueryOptions` with `QueryState` label `run` and not-found `{ title: 'Run not found', message: 'Run not found.' }`. It renders:
   - `<h2>Run <runDate> (<kind>)</h2>`, `RunStatusBadge`, `Stage <stage ?? '—'>`, `Cost <formatUsd(costUsd)>`, `Trace <traceId>`, `Started`/`Finished` (`formatDateTime`);
   - links `Open article <i + 1>` → `/articles/<id>` for each `articleIds` entry, and `Research run <i + 1>` → `/research?researchRunId=<id>` for each `researchRunIds` entry;
   - `JsonBlock` labelled `Run parameters` when `params` has keys, and `JsonBlock` labelled `Run error` when `error` is set.
5. Run actions:

   | Button | Shown when | Call | Toast on success |
   |---|---|---|---|
   | `Cancel run` | `blog.generate` and status non-terminal | `cancelRun` | `Run cancelled` |
   | `Restart run` | `blog.agent_runs` and status terminal | `restartRun` | `Run restarted` |
   | `Resume run` | `blog.agent_runs` and status non-terminal | `resumeRun` | `Run resumed` |

   Every success calls `afterRunChange`. Errors show `describeProblem(error, 'Could not update the run')`, which covers `Nothing to resume` and `Run cannot be restarted`.
6. Table caption `Attempts` with columns `#` (`attemptNo`), `Workflow`, `Status`, `Started`, `Finished`, `Forked from` (`forkedFromWorkflowId ?? '—'`).
7. `StepTimeline` renders `<ol aria-label="Step timeline">`, one item per step in `steps` order, showing: `stepName`, status badge, `Tries <n>`, `agentName ?? '—'`, `model ?? '—'`, `Prompt <promptName> v<promptVersion>` when set, `Tokens <in> / <out>`, `formatUsd(costUsd)`, `formatMs(durationMs)`, and `JsonBlock` labelled `Step error` when `error` is set.
   - `Retry step <stepName>` is shown with `blog.agent_runs` when the step is FAILED. It calls `retryStep` and toasts `Step retry started`.
   - `Restart from <stepName>` is shown with `blog.agent_runs` when the run status is terminal. It calls `restartFromStep` and toasts `Restart from step started`.
   - Both call `afterRunChange` on success and `describeProblem` on error (`Step cannot be retried`, `Step cannot be restarted`).
8. `AgentRunTable` uses `agentRunsQueryOptions({ runId })` with caption `Agent calls` and columns `Step`, `Agent`, `Model`, `Prompt`, `Status`, `Tokens`, `Cost`, `Duration`, `Sources` (count of `sourcesUsed`), `Error` (`error?.class ?? error?.message ?? '—'` when string-valued). Each row has a button `LLM calls for <stepName>` that opens `LlmCallsDialog`.
9. `LlmCallsDialog` (title `LLM calls`) uses `agentRunQueryOptions`. The table caption is `LLM calls`, with columns:
   - `Kind`, `Requested` (`providerRequested:modelRequested`), `Served` (`providerServed:modelServed`, or `—`), `Fallback from`, `Attempt`;
   - `Tokens` (`in / out · cache <cacheReadTokens> · reasoning <reasoningTokens>`), `Search actions`, `Latency` (`formatMs`), `Status`;
   - `Error` (`errorClass ?? '—'`), `Cost` (`formatUsd`), `Price version`.
10. `LatencyTable` sits under `<h2>Step latency (last 30 days)</h2>` with note `Counts daily and manual pipeline runs only; human actions are excluded.` It uses `latencyQueryOptions(30)` with caption `Latency by step` and columns `Step`, `Runs`, `P50`, `P90` (`formatMs`).

**Tests to write first** (`src/routes/agent-runs-page.test.tsx`; the three Phase 1 tests stay; new tests mock `GET B/runs?limit=50` → `runsPage([makeRun({ id: 'run-done', status: 'FAILED' })], 50)` unless stated).
- `shows run detail with attempts and a step timeline`: role reviewer. Mock `GET B/runs/run-done` → `makeRunDetail()`, and answer agent-runs and latency with empty data. Click `Details for run run-done`. Expect:
  - heading `Run 2026-09-17 (manual)`;
  - table `Attempts` row with `discover_topics`;
  - inside list `Step timeline`, the item containing `produce.fact_check` also contains `Failed` and `Fact checker timed out`;
  - link `Open article 1` → `/articles/article-1`, link `Research run 1` → `/research?researchRunId=research-run-1`.
- `retries a failed step`: role reviewer, `url: '/agent-runs?runId=run-done'`, `POST B/runs/run-done/steps/produce.fact_check/retry` → `makeRun({ id: 'run-done' })`. Click `Retry step produce.fact_check`. Expect header `X-CSRF-Token` `csrf-reviewer`, toast `Step retry started`, and `GET B/runs?limit=50` called at least twice.
- `restarts terminal runs from a step or from the start`: `Restart from produce.write_draft` → `POST B/runs/run-done/steps/produce.write_draft/restart`, toast `Restart from step started`. `Restart run` → `POST B/runs/run-done/restart`, toast `Run restarted`. No `Resume run` button.
- `shows the problem when nothing can resume`: detail `makeRunDetail({ status: 'PRODUCING' })`, `POST B/runs/run-done/resume` → 409 `Nothing to resume`. Click `Resume run` → toast `Nothing to resume`. No `Restart run` button.
- `hides retry, restart and resume without blog.agent_runs`: `sessionFor('viewer', ['blog.view'])` at `/agent-runs?runId=run-done` → no button named `/^(Retry step|Restart|Resume run|Cancel run)/`.
- `lists agent calls and their LLM calls`: `GET B/agent-runs?runId=run-done&limit=50&offset=0` → `pageOf([makeAgentRunOut()], { limit: 50 })`; `GET B/agent-runs/agent-run-1` → `makeAgentRunDetailOut()`. Table `Agent calls` has a row with `writer`. Click `LLM calls for produce.write_draft` → dialog `LLM calls` with a row containing `openai:gpt-w-2026`, `$0.1200` and `genai-prices==0.1.7`.
- `filters runs by status`: choose `Status` `FAILED` → `GET B/runs?status=FAILED&limit=50` called.
- `shows P50 and P90 per step`: `GET B/metrics/latency?days=30` → `makeLatencyReportOut()` → table `Latency by step` has a row with `produce.write_draft`, `5`, `12.0 s`, `18.0 s`, plus the text `human actions are excluded` (substring).

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/routes/agent-runs-page.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 Agent Runs timeline with retry, restart-from, restart, cancel (plus resume); §10.8 measured P50/P90 per stage; §5.7 Rule C note in the UI.

### UI-20: Notifications bell

**Files.** Create `src/features/notifications/components/notifications-bell.tsx`, `src/features/notifications/links.ts`, `src/features/notifications/links.test.ts` and `src/features/notifications/components/notifications-bell.test.tsx`. In `src/routes/app-layout.tsx`, add only the import and the `<NotificationsBell />` element.

**Interfaces produced.** `NotificationsBell()`; `isSafeInternalLink(link: string | null): link is string`.

**Behaviour rules.**
1. `isSafeInternalLink` is true only for a string that starts with `/` and does not start with `//` or `/\`.
2. `NotificationsBell` uses `notificationsQueryOptions({})`. `count = data?.total ?? 0`, and any error counts as 0 with no toast (a 401 stops polling via UI-3).
3. The trigger is a `DropdownMenuTrigger` wrapping a ghost icon `Button` with lucide `BellIcon`. Its `aria-label` is `Notifications` when `count === 0`, otherwise `Notifications (<count> unread)`. It shows a numeric badge when `count > 0`.
4. The menu contains:
   - a `DropdownMenuLabel` reading `Notifications`;
   - one `DropdownMenuItem` per item, showing `title`, `body` and `formatDateTime(createdAt, localTimeZone())`. Selecting an item calls `markNotificationRead(id)` (errors ignored) and invalidates `['notifications']`. When `isSafeInternalLink(link)`, it also calls `navigate(link)`;
   - a disabled item `No unread notifications` when the list is empty;
   - a `Mark all read` item, disabled when `count === 0`. It calls `markAllNotificationsRead()`, invalidates `['notifications']`, and toasts `All notifications marked read`.
5. `AppLayout` renders the bell immediately to the left of the user menu, inside a new `<div className="flex items-center gap-2">`. Nothing else in the file changes.

**Tests to write first.**
- `links.test.ts` › `accepts only same-origin paths`: `'/articles/a'` → true; `'//evil.example'`, `'/\\evil.example'`, `'https://evil.example'` and `null` → false.
- `notifications-bell.test.tsx`, rendered with `renderRoutes([{ path: '/', element: <NotificationsBell /> }, { path: '/articles/:articleId', element: <h1>Article page</h1> }], { session: sessionFor('viewer') })`:
  - `shows the unread count`: `GET B/notifications?unreadOnly=true&limit=10` → `pageOf([makeNotificationOut(), makeNotificationOut({ id: 'notification-2' })], { limit: 10 })` → button `Notifications (2 unread)`.
  - `marks a notification read and follows its link`: `POST B/notifications/notification-1/read` → `makeNotificationOut({ readAt: '2026-09-17T02:00:00Z' })`. Open the menu, click menuitem `Article ready for review` (name match on substring). Expect the POST once, `router.state.location.pathname === '/articles/article-1'`, and heading `Article page`.
  - `does not follow external links`: `link: 'https://evil.example/x'` → the POST happens and the pathname stays `/`.
  - `marks all read`: `POST B/notifications/read-all` → `new Response(null, { status: 204 })`. Click `Mark all read` → toast `All notifications marked read`, and the GET is called at least twice.
  - `shows no count when the API refuses`: GET → 401 → button `Notifications`.
  - `shows an empty menu`: `pageOf([], { limit: 10 })` → menu item `No unread notifications` is disabled.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/features/notifications` → red → green. `npm test` (router tests still green with the bell mounted), lint and typecheck exit 0.

**Acceptance covered.** §10.7 Notifications (UI bell): in-app list, unread count, mark read, mark all read.

### UI-21: Router tests and the viewer matrix

**Files.** Extend `src/router.test.tsx`. Create `src/routes/viewer-controls.test.tsx`. Delete `src/routes/placeholder-page.tsx` only when `grep -rn "placeholder-page" frontend/src` shows no importer (if FOUND's frozen `router.tsx` still imports it, keep the file).

**Interfaces.** Consumes `buildRoutes`, `NAV_ITEMS`, `MUTATING_BUTTON_NAME`, and all UI-2 builders.

**Behaviour rules.**
1. FOUND's router tests stay unchanged and green:
   - the redirect to `/login?next=`;
   - an `<h1>` equal to the nav label for every nav path, and `Article review` for `/articles/stub-article-id`;
   - viewer `Access denied`;
   - unknown path → dashboard;
   - sign-out.
2. The viewer matrix runs each page through `buildRoutes(createQueryClient())` with `sessionFor('viewer')`. It mocks the page's reads with UI-2 builders, waits for the page's data marker, and then asserts that no mutating control is present.

**Tests to write first.**
- `router.test.tsx`:
  - `renders every page heading while every blog-agent call fails`: `mockApi` with `GET /api/auth/session` → admin session and a fallback returning `problemResponse(500, 'Internal Server Error')`. For each `NAV_ITEMS` path and `/articles/stub-article-id`, navigate and expect `findByRole('heading', { level: 1, name })` with the nav label or `Article review`.
  - `shows the notifications bell in the layout`: admin session and `GET B/notifications?unreadOnly=true&limit=10` → `pageOf([makeNotificationOut()], { limit: 10 })` → button `Notifications (1 unread)` in the header.
- `viewer-controls.test.tsx` › `it.each(CASES)('shows a viewer no mutating controls on $path', …)`. For every case, assert `screen.queryAllByRole('button', { name: MUTATING_BUTTON_NAME })` has length 0 and `screen.queryAllByRole('switch')` has length 0.

  | `path` | Mocks | Marker to wait for | Extra step |
  |---|---|---|---|
  | `/` | dashboard, diversity, costs (day, agent, model), runs | text `3 opportunities discovered` | — |
  | `/ideas` | `GET B/topics` | heading `Prior auth, explained again` | — |
  | `/research?researchRunId=research-run-1` | list and detail (`articleId: 'article-1'`, kind `deep`) | text `CMS finalised the rule.` | — |
  | `/drafts` | articles `view=drafts` | link `How clinics can widen specialist access` | — |
  | `/published` | articles `view=published` | link `How clinics can widen specialist access` | — |
  | `/topics` | history → `pageOf([makeTopicHistoryOut({ title: 'Widen access', articleId: 'article-1', articleStatus: 'PUBLISHED' })])`, external posts → `pageOf([])` | row `Widen access` | — |
  | `/calendar?month=2026-09` | calendar | text `Published: Scarcity` | click `Open day 2026-09-20` |
  | `/sources` | ledger, feeds, domains, themes | ledger title link | click tabs `Feeds`, `Domains`, `Themes` in turn and wait for each tab's data |

  For `/sources`, the assertion runs after each tab has loaded.

**Verification.** `docker compose run --rm --no-deps web npx vitest run src/router.test.tsx src/routes/viewer-controls.test.tsx` → red → green. Lint and typecheck exit 0.

**Acceptance covered.** §10.5 "Viewer sees no mutating controls" (UI part), permission-gating Vitest suite; CONTRACT §4.12 heading rule (FOUND's router test plus the all-failing variant).

### UI-final: Track verification

**Files.** None changed. The report goes to the controller (no report file is written).

**Run, in order, from `mdcopilot-blog/`:**
```bash
docker compose run --rm --no-deps web npm test
docker compose run --rm --no-deps web npm run lint
docker compose run --rm --no-deps web npm run typecheck
docker compose run --rm --no-deps web npm run build
docker compose run --rm --no-deps web sh -c 'for s in cm-content fc-daygrid recharts-wrapper; do grep -l "$s" dist/assets/index-*.js && echo "LEAK $s"; done; true'
cmp backend/tests/api_shapes.json frontend/src/test/api-shapes.json
grep -rn "Date.now()" frontend/src --include=*.tsx
```

**Expected results.**
- `npm test` exits 0. Output shows `Test Files <n> passed (<n>)` with no failed files, the Phase 1 and FOUND tests included, and no `Unhandled Errors` block.
- `npm run lint` and `npm run typecheck` exit 0 with no output beyond the npm banner.
- `npm run build` exits 0. Chunk-size warnings are allowed.
- The bundle check prints no `LEAK` line: CodeMirror, FullCalendar and Recharts stay out of the entry chunk (C8).
- `cmp` prints nothing.
- Every `Date.now()` hit in `.tsx` is inside an event handler, a mutation callback, or a `refetchInterval` callback. Lint already enforces this (fact 10); the grep is for the report.
- `docker ps -a --filter name=p2p-ui` lists nothing, because `docker compose run --rm` removes its containers.

**Acceptance mapping.**

| CONTRACT row | Tasks | Proving tests |
|---|---|---|
| §10.1 UI Research page and Sources page | UI-9, UI-10 | `research-page.test.tsx`, `sources-page.test.tsx`, `themes-editor.test.tsx` |
| §10.2 UI Today's Ideas cards, Topics page | UI-7, UI-11 | `ideas-page.test.tsx`, `topics-page.test.tsx` |
| §10.2 Near-duplicate neighbour and similarity shown (UI display) | UI-4, UI-7 | `shared-components.test.tsx` (NoveltyPanel), `ideas-page.test.tsx` (`Duplicate`, `91%`) |
| §10.3 Version history and diff (UI) | UI-14 | `versions-panels.test.tsx`, `unified-diff.test.ts` |
| §10.3 Save with wrong H2 count → 422 (shown) | UI-13 | `editor-panels.test.tsx` |
| §10.5 Dashboard Today card, pipeline tracker, metrics, diversity; Drafts, Review Queue, Published | UI-8, UI-6 | `dashboard-page.test.tsx`, `dashboard-components.test.tsx`, `article-list-pages.test.tsx` |
| §10.5 Article review split screen (left and right panes) | UI-12 to UI-16 | `left-panels.test.tsx`, `editor-panels.test.tsx`, `versions-panels.test.tsx`, `publish-panel.test.tsx`, `article-review-page.test.tsx` |
| §10.5 Every human action wired with role-aware visibility; reject requires a reason | UI-5, UI-7, UI-8, UI-12 to UI-19 | dialog tests, page tests, `viewer-controls.test.tsx` |
| §10.5 Content Calendar with slots | UI-17 | `calendar-page.test.tsx`, `calendar-events.test.ts` |
| §10.5 Settings (all fields, routes, brand, pillars, themes, schedule, masked keys, auto-publish locked OFF) | UI-18, UI-10 | `settings-page.test.tsx`, `settings-values.test.ts` |
| §10.5 Agent Runs timeline with retry, restart-from, restart, cancel | UI-19 | `agent-runs-page.test.tsx` |
| §10.5 Vitest suites: topic selection, review, approve, reject, regenerate, export/publish, permission gating | UI-7, UI-16, UI-5, UI-15, UI-21 | `ideas-page`, `article-review-page`, `approve-dialog`, `reject-article-dialog`, `regenerate-dialog`, `publish-panel`, `viewer-controls` |
| §10.5 Playwright smoke (INT primary) | Accessible-name table (Header) | INT's `scripts/e2e/phase6-smoke.sh` |
| §10.5 Viewer sees no mutating controls | UI-21, UI-16 | `viewer-controls.test.tsx`, `article-review-page.test.tsx` |
| §10.5 Preview never renders raw model HTML (UI DOMPurify) | UI-1, UI-4, UI-14 | `sanitize.test.ts`, `shared-components.test.tsx`, `versions-panels.test.tsx` |
| §10.6 Manual export UX: clipboard `text/html` + `text/plain`, copy buttons, download, confirm-published | UI-15 | `clipboard.test.ts`, `publish-panel.test.tsx` |
| §10.7 Notifications (UI bell) | UI-20, UI-21 | `notifications-bell.test.tsx`, `router.test.tsx` |
| §10.8 Cost views (today/week/month, article, research run, topic, agent, model) and price-override UI | UI-8, UI-16, UI-18 | `dashboard-page.test.tsx`, `dashboard-components.test.tsx`, `article-review-page.test.tsx`, `settings-page.test.tsx` |
| §10.8 Dashboard metrics and measured P50/P90 | UI-8, UI-19 | `dashboard-page.test.tsx`, `agent-runs-page.test.tsx` |
| §10.8 Per-article cost on the article page | UI-16 | `article-review-page.test.tsx` (`Cost $0.4200`) |
| §5.7 Rules A–C (UI: a SUCCEEDED run returning to QUEUED/PRODUCING polls again; human actions excluded from latency) | UI-1, UI-7, UI-19 | `polling.test.ts`, `ideas-page.test.tsx`, `agent-runs-page.test.tsx` |
| Phase 1 final-review minors touching the UI (polling after 401, run permissions) | UI-1, UI-0 | `polling.test.ts`, `api.test.ts` (runs); Request lines O4, O5 |

**Report contents.** For each task: the red and green command lines with their final output lines; the full-run outputs above; any `ReviewLayout` grid fallback (UI-16 rule 7); the `UNUSED_BY_UI` entries (UI-2); every `Request:` line filed; and any test that needed a longer timeout than this plan states.

