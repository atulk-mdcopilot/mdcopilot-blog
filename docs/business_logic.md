# MDCopilot Blog: product and business logic

State after the 2026-09-22 minimization. For the API, tables, settings and deployment see
[architecture.md](architecture.md).

## 1. What the product does

An MDCopilot ADMIN types one or more topics on **Admin -> Generate Blogs**. For each topic the service
researches it, writes an article, runs automated fact, clinical and editorial reviews, and saves the result
as a **draft in MDCopilot Blogs**. The admin then reads, edits, saves and publishes that draft with the
existing Blogs list and editor. The human editor is the final reviewer; nothing is published automatically.

The seeded brand targets specialist physicians, clinical leaders, and healthcare operations teams. Its editorial position is that AI supports specialist expertise while physicians remain in control. It favors specific evidence, practical workflow implications, responsible AI, and clinically grounded language. The brand profile and source catalog are stored configuration; these are defaults, not hardcoded guarantees about every deployment's content.̌


It is an authoring aid, not the public website and not clinical decision support.

Source: [brand seed](../backend/src/mdcopilot_blog/db/seed_data/brand_profile.yaml), [workflows](../backend/src/mdcopilot_blog/workflows/).

## 2. Terms

| Term | Meaning |
| --- | --- |
| Run | One topic, from request to saved draft, with status, cost and the acting admin's id |
| Attempt / step | One workflow execution of a run / one tracked stage of it; not every step calls a model |
| Research run | Focused deep research or a targeted verification search, with its queries and sources |
| Source ledger | Saved source URLs, dates, tier, accessibility and extracted text; citation markers point here |
| Topic candidate / topic | The typed topic stored as a writer brief, and its promoted form |
| Research packet | The writing brief built from the research: facts, statistics, counterarguments, evidence |
| Article / version | The lifecycle record, and immutable content snapshots (draft, revision, fix pass) |
| Review / gate report | Assessment of one version: fact check, clinical, editorial, deterministic gates |
| Draft | The `blogs` row in mdcopilot-backend (`status="draft"`) that the run ends with |

## 3. Research

Deep research plans queries across facets (primary source, announcement, research, regulatory, statistics,
expert commentary, counterarguments, industry context), searches the web, retrieves pages (SSRF guard,
robots rules, size caps), extracts text and dates, and adds PubMed abstracts. Source domains carry a seeded
tier and fetch policy. The run stops with `insufficient_evidence` when there are fewer dated sources than
`BLOG_AGENT_MIN_SOURCE_COUNT` (default 5) or no tier 1/2 source with text; a niche topic can fail this way
and the Generate page shows the message. At most 20 sources feed the packet, which the Deep Research Analyst
writes as a separate step.

Source: [research](../backend/src/mdcopilot_blog/research/), [packet creation](../backend/src/mdcopilot_blog/services/article_steps.py).

## 4. Draft structure

Every draft has seven sections in this order: introduction (no heading), context, core argument, evidence,
MDCopilot perspective, practical implications, conclusion. It also has provocative, operational and
visionary title options (the operational one is used), a pull quote, CTA and excerpt. Citation markers bind
a version to sources from its packet. Word count counts section bodies only. The writer is told the brand's
prohibited language; there is no article history to avoid any more.

## 5. Reviews and bounded repair

Writer -> Fact Checker -> Clinical Reviewer -> Editorial Reviewer. Unsupported or incorrect claims, blocking
clinical flags and required editorial changes become revision findings; if any exist, the Writer produces a
new version with one resolution per finding and facts are re-checked. SEO is generated afterwards. Clinical
and editorial reviews are not re-run after a revision; gates use the nearest ancestor review plus the
recorded resolutions.

The fact check runs on a route re-ordered so the provider that wrote the draft comes last. For unsupported
high-importance or statistical claims it may run up to three allowlisted verification searches and re-check
once if new evidence was found. A claim the model returns in an invalid shape (quoted span not in the
article, unknown marker or section, "supported" without a source) is dropped and logged; the answer is
rejected only when no claim survives or more than half were dropped.

After SEO the deterministic gates run. If a fixable blocking gate fails there is exactly one fix pass
(revise, re-check facts, SEO again if needed, gates again). Missing source coverage or a missing disclosure
is not fixable by the writer and skips the fix pass.

**Whatever the reviews conclude, the draft is saved.** A failed gate, or a review stage that crashed, is
reported on the Generate page as a warning with the list of problems (`gatesPassed=false`,
`gateProblems`); it does not discard the article.

Source: [production sequence](../backend/src/mdcopilot_blog/workflows/produce.py), [fix-pass decisions](../backend/src/mdcopilot_blog/domain/fix_pass.py), [fact checker](../backend/src/mdcopilot_blog/agents/fact_checker.py).

## 6. Quality gates

13 blocking gates and 1 warning. They inspect structured evidence and stored reviews; they are not proof
that every statement is medically correct.

| Blocking gate | Requirement |
| --- | --- |
| Sources present | At least the configured number of distinct cited sources (default 5), one of them tier 1/2 |
| Claims verified | A fact check exists for this version; no high-importance unsupported/outdated/misleading claim |
| No unsupported statistics | Statistic claims are supported; numeric sentences have claim coverage |
| No fabricated quotes | Quotations occur in cited snapshots; attribution claims are supported |
| No unsourced anecdotes | Anecdote claims have source support; no unresolved invented-anecdote flag |
| Word count | Section-body count within the effective min/max |
| Required structure | Seven ordered non-empty sections, heading rules, pull quote and CTA present |
| No prohibited language | Brand phrases absent from titles, body, pull quote, CTA, excerpt and SEO copy |
| SEO complete | SEO title <= 60, meta description 120-160, valid unique slug, title <= 200, excerpt <= 500 |
| Fact check passed | Verdict PASS for this version |
| Clinical clear | No unresolved blocking clinical flag in the version lineage |
| Editorial completed | Required editorial changes have recorded resolutions |
| Disclosure present | The active brand's AI-assistance disclosure is non-blank (rendering appends it) |

Warning: independent fact check (the fact check ran on a different provider than the writer).

Source: [gates](../backend/src/mdcopilot_blog/domain/gates.py).

## 7. What reaches MDCopilot Blogs

The current version is rendered to sanitised, editor-safe HTML with numbered citation links, a References
list and the disclosure. Title = operational title option, excerpt = the draft's excerpt (cut to 500), slug =
the SEO slug when valid (the backend de-duplicates it). SEO title, meta description, tags and category are
not sent. The draft's author is the admin who started the run. Human edits in the Blogs editor are not
versioned or re-checked here.

## 8. States and failures

Run: `QUEUED -> RESEARCHING -> TOPICS_READY -> PRODUCING -> SUCCEEDED | FAILED | CANCELLED`.
Article: `DRAFTING -> FACT_CHECKING -> CLINICAL_REVIEW -> EDITORIAL_REVIEW -> SEO -> DRAFT_SAVED`, or `FAILED`.

| Condition | Response |
| --- | --- |
| Insufficient evidence, or any failure before a draft version exists | Run `FAILED` with `error.message` |
| Review, revise, SEO, gate or fix-pass stage fails after a draft exists | Draft still saved; warning in `gateProblems` |
| Backend refuses or cannot be reached for the draft POST | Connection errors retry; a refusal fails the run (`BackendDraftError`) |
| Model output violates its contract | One retry per model, then the next model in the route; exhaustion fails the stage |
| Missing provider key | That route entry is skipped; web search needs OpenAI |
| Budget reached | The next model call is refused; in-flight calls can exceed the cap slightly |
| Transient database/connection error | Step retried up to 6 times with exponential backoff |
| Cancel | Signals DBOS and records `CANCELLED`; completed external requests are not rolled back |
| Worker restart | DBOS recovers pending workflows of the same `APP_VERSION` from their recorded steps |

## 9. Removed in the 2026-09-22 minimization

Earlier versions of this guide described features that no longer exist: login, roles and permissions; the
dashboard, research, sources and settings screens; researched and daily topic discovery, topic ranking and
novelty/duplicate detection; the article editor with version-aware editing, partial regeneration, re-check,
approval and rejection; manual export, scheduling and the login-based network publisher; run restart, resume
and step retry; external-post import and snapshot retention. Editing, saving and publishing are now the
MDCopilot Blogs pages in mdcopilot-frontend, backed by mdcopilot-backend.
