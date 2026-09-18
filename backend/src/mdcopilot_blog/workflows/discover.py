"""Daily/manual discovery, novelty ranking and durable production handoff."""

import uuid
from typing import Any

from dbos import DBOS, SetWorkflowID, SetWorkflowTimeout
from sqlalchemy import func, select

from mdcopilot_blog.db.models import Article, BlogRun, ResearchRun, TopicCandidateRecord
from mdcopilot_blog.domain.contracts import PillarKey
from mdcopilot_blog.domain.enums import AttemptStatus, RunStatus
from mdcopilot_blog.research import broad as research
from mdcopilot_blog.services import topic_steps
from mdcopilot_blog.services.config import pillar_for_date
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_DISCOVER_TOPICS, WORKFLOW_REGENERATE_TOPICS
from mdcopilot_blog.workflows.produce import produce_article
from mdcopilot_blog.workflows.retry import WorkflowCancelledError
from mdcopilot_blog.workflows.runtime import get_runtime
from mdcopilot_blog.workflows.stages import STOP, StageContext, advance_run, fail_workflow, tracked_stage
from mdcopilot_blog.workflows.tracking import finish_attempt


async def _discover(run_id: str, *, regenerate: bool) -> dict[str, Any]:
    prefix = "regenerate_topics" if regenerate else "discover"
    name = WORKFLOW_REGENERATE_TOPICS if regenerate else WORKFLOW_DISCOVER_TOPICS

    async def stage(key: str, body: Any, agent: str | None = None) -> dict[str, Any]:
        return await tracked_stage(f"{prefix}.{key}", run_id=run_id, workflow_name=name, body=body, agent_name=agent)

    try:

        async def opened(ctx: StageContext) -> dict[str, Any]:
            async with ctx.sc.sessionmaker() as db:
                run = await db.get(BlogRun, ctx.run_id)
                if run is None:
                    raise LookupError("run not found")
                pillar = run.params.get("pillar") or await pillar_for_date(db, run.run_date)
                latest = await db.scalar(
                    select(ResearchRun.id)
                    .where(ResearchRun.run_id == ctx.run_id, ResearchRun.kind == "broad")
                    .order_by(ResearchRun.created_at.desc())
                    .limit(1)
                )
                round_no = (
                    await db.scalar(
                        select(func.max(TopicCandidateRecord.round)).where(TopicCandidateRecord.run_id == ctx.run_id)
                    )
                    or 0
                )
                previous = list(
                    await db.scalars(select(TopicCandidateRecord.id).where(TopicCandidateRecord.run_id == ctx.run_id))
                )
                live = await db.scalar(
                    select(Article.id)
                    .where(Article.run_id == ctx.run_id, Article.status.not_in(["REJECTED", "SUPERSEDED"]))
                    .limit(1)
                )
                params = dict(run.params)
                status = run.status
            if status not in {"TOPICS_READY", "WAITING_FOR_TOPIC"} and not await advance_run(
                ctx.run_id, RunStatus.RESEARCHING, ctx.step_name
            ):
                return STOP
            return {
                "params": params,
                "pillar": str(pillar) if pillar else None,
                "research_run_id": str(latest) if latest else None,
                "round": round_no + 1,
                "avoid": [str(i) for i in previous],
                "mode": "manual" if live else ctx.sc.config.topic_selection_mode,
                "max_rounds": ctx.sc.config.novelty.max_regeneration_rounds + 1,
            }

        info = await stage("open_attempt", opened)
        if info["cancelled"]:
            return info
        manual = info["params"].get("topic") if not regenerate else None
        if manual:

            async def create(ctx: StageContext) -> dict[str, Any]:
                output = await topic_steps.create_manual_candidate(
                    ctx.sc,
                    run_id=ctx.run_id,
                    topic=manual,
                    pillar_key=PillarKey(info["pillar"]) if info["pillar"] else None,
                    audience=info["params"].get("audience"),
                    tone=info["params"].get("tone"),
                )
                await advance_run(ctx.run_id, RunStatus.TOPICS_READY, ctx.step_name)
                return output.model_dump(mode="json")

            result = await stage("manual_topic", create)
            if result["cancelled"]:
                return result
            mode = "auto"
        else:
            research_id = info["research_run_id"]
            if not regenerate:

                async def gather(ctx: StageContext) -> dict[str, Any]:
                    return (
                        await research.gather_signals(
                            ctx.sc, pillar_key=PillarKey(info["pillar"]) if info["pillar"] else None
                        )
                    ).model_dump(mode="json")

                result = await stage("gather_signals", gather, "research")
                if result["cancelled"]:
                    return result
                research_id = result["research_run_id"]

                async def ledger(ctx: StageContext) -> dict[str, Any]:
                    return (await research.build_ledger(ctx.sc, research_run_id=uuid.UUID(research_id))).model_dump(
                        mode="json"
                    )

                result = await stage("build_ledger", ledger, "research")
                if result["cancelled"]:
                    return result

                async def synthesize(ctx: StageContext) -> dict[str, Any]:
                    return (
                        await research.synthesize_research(ctx.sc, research_run_id=uuid.UUID(research_id))
                    ).model_dump(mode="json")

                result = await stage("synthesize_research", synthesize, "research")
                if result["cancelled"]:
                    return result
            if research_id is None:
                raise LookupError(f"run {run_id} has no broad research run")
            avoid = info["avoid"]
            for round_no in range(info["round"], info["round"] + info["max_rounds"]):

                async def ideate(
                    ctx: StageContext, round_no: int = round_no, avoid: list[str] = avoid
                ) -> dict[str, Any]:
                    return (
                        await topic_steps.ideate_topics(
                            ctx.sc,
                            research_run_id=uuid.UUID(research_id),
                            round_no=round_no,
                            avoid_candidate_ids=[uuid.UUID(i) for i in avoid],
                        )
                    ).model_dump(mode="json")

                proposed = await stage("ideate_topics", ideate, "ideation")
                if proposed["cancelled"]:
                    return proposed
                ids = proposed["candidate_ids"]

                async def score(ctx: StageContext, ids: list[str] = ids) -> dict[str, Any]:
                    return (
                        await topic_steps.check_novelty_and_score(ctx.sc, candidate_ids=[uuid.UUID(i) for i in ids])
                    ).model_dump(mode="json")

                scores = await stage("check_novelty_and_score", score, "ideation")
                if scores["cancelled"]:
                    return scores
                avoid = [*avoid, *ids]
                if len(scores["passed_ids"]) + len(scores["warned_ids"]) >= 3:
                    break
            mode = info["mode"]

        async def select_topic(ctx: StageContext) -> dict[str, Any]:
            if not await advance_run(ctx.run_id, RunStatus.TOPICS_READY, ctx.step_name):
                return STOP
            output = await topic_steps.select_topic(
                ctx.sc, run_id=ctx.run_id, mode="auto" if mode == "auto" else "manual"
            )
            await advance_run(
                ctx.run_id, RunStatus.PRODUCING if output.candidate_id else RunStatus.WAITING_FOR_TOPIC, ctx.step_name
            )
            return output.model_dump(mode="json")

        chosen = await stage("select_topic", select_topic)
        if chosen["cancelled"]:
            return chosen
        child = None
        if candidate_id := chosen["candidate_id"]:
            with (
                SetWorkflowID(f"produce-{run_id}-{candidate_id}"),
                SetWorkflowTimeout(get_runtime().settings.production_timeout_minutes * 60),
            ):
                handle = await DBOS.enqueue_workflow_async(QUEUE_PIPELINE, produce_article, run_id, candidate_id)
            child = handle.get_workflow_id()

        async def finish(ctx: StageContext) -> dict[str, Any]:
            await finish_attempt(ctx.sc.sessionmaker, workflow_id=ctx.workflow_id, status=AttemptStatus.SUCCEEDED)
            return {
                "run_id": run_id,
                "candidate_id": chosen["candidate_id"],
                "production_workflow_id": child,
                "shortfall": chosen["shortfall"],
            }

        return await stage("finish", finish)
    except (Exception, WorkflowCancelledError) as exc:
        await fail_workflow(workflow_name=name, run_id=run_id, article_id=None, error=exc)
        raise


@DBOS.workflow(name=WORKFLOW_DISCOVER_TOPICS)
async def discover_topics(run_id: str) -> dict[str, Any]:
    return await _discover(run_id, regenerate=False)


@DBOS.workflow(name=WORKFLOW_REGENERATE_TOPICS)
async def regenerate_topics(run_id: str) -> dict[str, Any]:
    return await _discover(run_id, regenerate=True)
