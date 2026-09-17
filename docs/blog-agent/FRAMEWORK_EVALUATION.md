# Framework Evaluation — MDCopilot Blog Intelligence

Status: Phase 0 proposal, waiting for owner approval
Evidence date: 2026-09-17. Versions, prices and API behaviour come from live primary sources opened on that date. A second agent re-checked every claim that affects the decision.

## Verdict

| Question | Answer |
|---|---|
| 1. Should we use CrewAI? | **No.** |
| 2. Should we use LangGraph? | **No, but it is the documented Plan B** (LangGraph 1.2.x, never the backend's `<1.0` pin). |
| 3. Should we use a hybrid architecture? | **Yes, of a specific kind:** one durable-workflow engine plus one LLM/agent library, each with a single job. We do not mix CrewAI with LangGraph. |
| 4. Is another framework more suitable? | **Yes: DBOS Transact (workflows) + Pydantic AI (agents and LLM calls).** Both run as libraries on our own Postgres, with no extra servers. |

**Why.** This product is a fixed pipeline of about 12 stages. Most stages are one typed LLM call, and none is an open-ended multi-agent conversation. It needs:
- durable per-step state in Postgres;
- retry of a single step, restart from a step, and automatic resume after a crash;
- a timezone-aware daily schedule;
- provider fallback, cost tracking per call, and a deterministic mock mode.

DBOS provides the first three natively. Pydantic AI provides typed outputs across Gemini, OpenAI and Anthropic, a fallback chain, usage and cost data, and test models for mock mode. CrewAI and LangGraph each leave several of these as custom code; see the matrix below.

## Capability matrix

Scores run 1–5, where 5 is best. For **Complexity**, 5 means simplest to build and run. "Alternative" means **DBOS Transact + Pydantic AI**.

| Capability | CrewAI 1.15.21 | LangGraph 1.2.11 | Alternative: DBOS + Pydantic AI |
|---|---|---|---|
| Multi-agent orchestration | 4: Crews plus Flows (`@start`/`@listen`/`@router`) | 4: StateGraph, conditional edges, `Send` fan-out | 4: plain async Python calling typed agents inside durable workflows |
| Stateful workflows | 3: Flow state persists to **local SQLite only**; Postgres needs a custom backend | 5: Postgres checkpointer saves at every step boundary | 5: every step checkpointed in Postgres; workflow status queryable |
| Parallel execution | 3: `and_`/`or_` fan-in; open async bugs (#7183, #7332, #7252) | 4: `Send` API with reducer fields | 4: `asyncio.gather` inside steps; queues with concurrency and rate limits |
| Human-in-the-loop | 3: `@human_feedback` can wait days, but `emit=` routing sends every button click to an LLM | 4: `interrupt()` / `Command(resume=)` waits indefinitely; node re-runs from its first line on resume | 4: durable `recv()` waits; we instead end workflows at human gates and start short new ones |
| Retry / recovery | 2: `@persist` restores state, not progress; a reload runs again from `@start` | 4: `RetryPolicy`, `TimeoutPolicy`, error handlers (≥1.2); **no automatic resume at startup in the OSS library** | 5: per-step retries with backoff, automatic recovery of interrupted workflows at startup, `fork_workflow(start_step)` |
| Web research integration | 3: OpenAI `web_search` mapped to the legacy preview tool; citations not surfaced; no Gemini grounding | 3: nothing built in; you call SDKs yourself | 4: Pydantic AI exposes OpenAI web-search sources (`openai_include_web_search_sources`); we still call the search SDK directly for full citation data |
| Structured outputs | 4: `output_pydantic`, with a converter-call fallback | 3: nothing built in outside LangChain | 5: `output_type=<Pydantic model>` on all three providers, with validation retries |
| Observability | 4: built-in integrations, but **telemetry on by default** | 3: LangSmith, or manual OpenTelemetry | 3: OpenTelemetry instrumentation in Pydantic AI; DBOS workflow UI is paid, so we build our own run page |
| Production readiness | 3: 44 stable releases in 2026; persistence bug in current stable with datetime/UUID state (#7358) | 4: 1.x stable; checkpoint security advisories fixed in 1.0.10 / checkpoint 4.1.1 | 4: DBOS MIT, Postgres-only; **3.0.0 is one day old (breaking)**; Pydantic AI V2 stable since 2026-06-23 |
| Complexity (5 = simplest) | 2: 134 packages / ~248 MB of wheels (chromadb, lancedb, onnxruntime…) | 3: checkpoint tables sit outside Alembic; own scheduler; own startup sweeper | 4: two libraries, no new containers, domain tables stay ours |
| Latency | 3: agent/ReAct loops and output conversion can add LLM calls | 4: one checkpoint write per step; negligible next to LLM time | 5: direct calls; one checkpoint row per step |
| Maintainability | 2: dependency pins clash with the sibling backend (`httpx`, `openai`); fast churn | 4: flat graph is readable; node rename/removal breaks parked threads | 4: plain Python functions; fallback and pricing hidden behind our own gateway |
| **Total (of 60)** | **36** | **45** | **51** |

### Other alternatives considered

| Option | Total | Why not the backbone |
|---|---|---|
| Temporal | 46 | The most mature engine, but self-hosting adds a server, a UI and setup containers, plus strict determinism rules. Too much to run for one article a day. |
| Hatchet | 40 | Best runner-up if a free built-in dashboard matters. However, the server is still 0.x, cron is UTC-only, missed runs are not replayed, and it adds a container plus gRPC token setup. |
| OpenAI Agents SDK | 39 | Pre-1.0 (0.22.2); hosted web search works only on OpenAI models; durability is delegated to other engines. |
| Google ADK 2.x | 39 | Built around Gemini; restricts how built-in tools combine; resume re-runs tools ("at least once"). |
| Plain asyncio + Procrastinate 3.9 | 38 | Works, but we would hand-write resume, fork and the step state machine. Its cron has no timezone, and stalled-job recovery is manual. |
| Pydantic AI alone (incl. `pydantic-graph`) | — | Excellent agent layer, but no durable state or resume without an engine. |

## How the chosen stack meets each requirement

| Requirement (spec §) | Mechanism |
|---|---|
| Parallel research (§5) | `asyncio.gather` with per-host and per-provider semaphores inside a research step; limits come from settings |
| Persisted workflow state (§39) | DBOS step checkpoints (schema `dbos`), plus our own read model (schema `app`): `blog_runs`, `blog_run_attempts` (one per DBOS execution) and `blog_agent_runs` (keyed by DBOS workflow ID + step ID) |
| Retry step (§39) | DBOS step `retries_allowed` / `max_attempts` / backoff, applied only to transient provider errors |
| Restart step (§39) | The API maps a step name to its latest `function_id` (`list_workflow_steps`) and calls `fork_workflow(workflow_id, start_step)`. Fork copies the original inputs, so steps resolve their attempt from `DBOS.workflow_id` and write only inserts. |
| Resume interrupted run (§39) | DBOS automatic recovery of PENDING workflows when the worker starts. `application_version` and `executor_id` are set explicitly. |
| Restart entire run (§39) | New workflow with the same inputs, recorded as a new attempt |
| Human approval gate (§24, §58) | Workflows **end** at `READY_FOR_REVIEW` (and at `WAITING_FOR_TOPIC` in manual mode). Each human action starts a new short workflow, so no run waits across a deploy. |
| Daily 07:00 (§32) | A DBOS schedule (cron + `cron_timezone`, no automatic backfill) runs a wrapper workflow. The wrapper starts `discover_topics` with the workflow ID `daily-YYYY-MM-DD`, so a date can never produce two runs. A startup check covers a slot missed earlier the same day. |
| Fallback provider (§39) | `LLMGateway` walks each agent's ordered model route itself, moving on after API errors, timeouts and exhausted validation retries. It records one row per attempt. |
| Model routing (§36) | Per-agent route config (`provider:model` plus parameters). No model names in business logic. |
| Cost tracking (§46) | Usage data from Pydantic AI, priced with pinned `genai-prices`, plus our own table for search-action fees. One `blog_llm_calls` row per attempt, including web-search calls. |
| Mock mode (§54) | Pydantic AI `FunctionModel` fixtures plus `ALLOW_MODEL_REQUESTS=False`; fixture search/feed/publisher providers |

## Deliberate deviations from the research recommendation

1. **We do not use Pydantic AI's `DBOSDurability` integration at first.** Each pipeline stage is one `@DBOS.step`, and the agent is called inside it as ordinary async code. A crash mid-stage repeats that stage's LLM calls, which costs cents at this volume. In return, the design does not depend on the pydantic-ai × dbos-3.0 combination, which nobody has tested yet (pydantic-ai CI still pins dbos 2.10). We can adopt per-call durability later without changing workflows.
2. **No `FallbackModel`. Our `LLMGateway` walks the model route itself.** Three reasons:
   - Validation failures never trigger `FallbackModel`, so escalation needs our own loop anyway.
   - We need one recorded row per attempt.
   - Pydantic AI V3 (possible any time after 2026-09-23) may replace `FallbackModel`.
3. **Web search does not go through a Pydantic AI agent.** The search provider (in `app/llm/search/`, called via `LLMGateway.search()`) uses the OpenAI Responses API directly, in plain-text mode. That keeps `url_citation` annotations, `web_search_call.action.sources` and the `tool_usage` counters intact, while the same cost cap and recording apply. See RESEARCH_ARCHITECTURE.md.

## Risks and how we contain them

| Risk | Containment |
|---|---|
| DBOS 3.0.0 is brand new (released 2026-09-16, breaking schema) | Phase 1 **Spike S1**: pin `dbos==3.0.*` only if a patch release or our Docker smoke test passes. Otherwise pin `dbos>=2.31.1,<3`, using only APIs present in both: schedules, queues and enqueue, `fork_workflow`, `list_workflow_steps`, and cancel. A fresh app has no data, so choose before the first real run. |
| The API process must never execute workflows | `DBOS.launch()` runs **only in `worker`**. The API uses `DBOSClient` to enqueue, fork, cancel and list. S1 checks that the pinned client supports all four; any that is missing goes through a small control workflow enqueued to the worker. |
| DBOS only recovers workflows for the matching `application_version` | Set `APP_VERSION` explicitly. Bump it whenever any workflow's steps are added, removed or reordered, and when upgrading dbos from 2.x to 3.x; never run mixed-version workers. Keep workflows short. Move stranded runs with `fork_workflow(..., application_version=)`. |
| DBOS steps run at least once, and forks copy inputs | Step rows are keyed by `(dbos_workflow_id, dbos_step_id)`. Content writes are inserts only (new versions, reviews, claim checks). Publishing uses an idempotency key. |
| DBOS management UI (Conductor) is paid | Build the **Agent Runs** page in our dashboard; the spec requires it anyway (§25, §35). |
| Pydantic AI V3 breaking change | Pin `pydantic-ai-slim[openai,google,anthropic]==2.43.*`. Only `app/llm/` imports it. |
| Gemini request timeouts surface as raw `httpx2` errors | The gateway catches `ModelAPIError`, `httpx`/`httpx2` timeouts, connection errors and `UnexpectedModelBehavior` itself, with SDK retries disabled. Spike S4 tests this. |
| Team knows LangGraph | The backend runs 0.6.11 with no checkpointer, so there is no durable pattern to reuse. Plan B remains available. |

## Plan B — LangGraph 1.2.x

If the owner prefers LangGraph:
- Pin `langgraph>=1.2.11,<2`, `langgraph-checkpoint-postgres>=3.1.2,<4`, and `psycopg[binary]`.
- Build one flat `StateGraph`, compiled with `AsyncPostgresSaver` and `durability="sync"`.
- Use `set_node_defaults(retry_policy=..., timeout=..., error_handler=...)`.
- Add a startup sweeper that calls `ainvoke(None, config)` for runs marked RUNNING.
- Use a separate scheduler (DBOS or APScheduler 3.11 used only as a trigger).
- Keep checkpoint tables in their own schema via `search_path`, excluded from Alembic, with a retention job using `adelete_thread`.
- Never rename or remove nodes while articles await review.

The rest of this architecture (gateway, research layer, data model, UI) is unchanged under Plan B.

## Rejected explicitly

- **CrewAI.** We would still write Postgres persistence, idempotent steps, a fallback wrapper and cost accounting ourselves. On top of that come 134 dependencies, telemetry on by default, a known persistence bug in stable, and version pins incompatible with the sibling backend.
- **LangGraph Platform / LangSmith Deployment.** Paid and licensed; not needed when the library is embedded.
- **Celery, Arq, RQ, APScheduler 4.** Celery lacks native async and needs a single beat plus a broker. Arq is in maintenance-only mode. RQ's cron is beta. APScheduler 4 is a pre-release.

## Sources (opened 2026-09-17)

- CrewAI: https://pypi.org/pypi/crewai/json · https://docs.crewai.com/en/concepts/flows · https://docs.crewai.com/en/concepts/checkpointing · https://github.com/crewAIInc/crewAI/issues/7358
- LangGraph: https://docs.langchain.com/oss/python/langgraph/durable-execution · https://docs.langchain.com/oss/python/langgraph/checkpointers.md · https://docs.langchain.com/oss/python/langgraph/interrupts.md · https://docs.langchain.com/oss/python/langgraph/fault-tolerance.md · https://docs.langchain.com/langsmith/cron-jobs · https://docs.langchain.com/langsmith/self-hosted
- DBOS: https://docs.dbos.dev/python/tutorials/workflow-tutorial · https://docs.dbos.dev/python/tutorials/queue-tutorial · https://docs.dbos.dev/python/tutorials/scheduled-workflows · https://docs.dbos.dev/python/tutorials/workflow-management · https://docs.dbos.dev/python/upgrading · https://docs.dbos.dev/production/conductor · https://api.github.com/repos/dbos-inc/dbos-transact-py/releases/tags/3.0.0
- Pydantic AI: https://ai.pydantic.dev/ · https://api.github.com/repos/pydantic/pydantic-ai/releases
- Others: https://docs.temporal.io/self-hosted-guide/deployment · https://docs.hatchet.run/self-hosting · https://docs.hatchet.run/home/cron-runs · https://adk.dev/runtime/resume/ · https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html · https://apscheduler.readthedocs.io/en/3.x/faq.html
