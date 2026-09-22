"""Manual-topic intake and durable production handoff."""

from typing import Any

from dbos import DBOS, SetWorkflowID, SetWorkflowTimeout

from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.enums import AttemptStatus, RunStatus
from mdcopilot_blog.services import topic_steps
from mdcopilot_blog.workflows.names import QUEUE_PIPELINE, WORKFLOW_DISCOVER_TOPICS
from mdcopilot_blog.workflows.produce import produce_article
from mdcopilot_blog.workflows.retry import WorkflowCancelledError
from mdcopilot_blog.workflows.runtime import get_runtime
from mdcopilot_blog.workflows.stages import STOP, StageContext, advance_run, fail_workflow, tracked_stage
from mdcopilot_blog.workflows.tracking import finish_attempt


@DBOS.workflow(name=WORKFLOW_DISCOVER_TOPICS)
async def discover_topics(run_id: str) -> dict[str, Any]:
    async def stage(key: str, body: Any) -> dict[str, Any]:
        return await tracked_stage(f"discover.{key}", run_id=run_id, workflow_name=WORKFLOW_DISCOVER_TOPICS, body=body)

    try:

        async def opened(ctx: StageContext) -> dict[str, Any]:
            async with ctx.sc.sessionmaker() as db:
                run = await db.get(BlogRun, ctx.run_id)
                if run is None:
                    raise LookupError("run not found")
                params = dict(run.params)
                if not params.get("topic"):
                    raise ValueError("run has no topic")
            if not await advance_run(ctx.run_id, RunStatus.RESEARCHING, ctx.step_name):
                return STOP
            return {"params": params}

        info = await stage("open_attempt", opened)
        if info["cancelled"]:
            return info

        async def create(ctx: StageContext) -> dict[str, Any]:
            output = await topic_steps.create_manual_candidate(
                ctx.sc,
                run_id=ctx.run_id,
                topic=info["params"]["topic"],
                audience=info["params"].get("audience"),
            )
            await advance_run(ctx.run_id, RunStatus.TOPICS_READY, ctx.step_name)
            return output.model_dump(mode="json")

        result = await stage("manual_topic", create)
        if result["cancelled"]:
            return result

        async def select_topic(ctx: StageContext) -> dict[str, Any]:
            output = await topic_steps.select_topic(ctx.sc, run_id=ctx.run_id)
            if output.candidate_id is None:
                raise LookupError("the manual topic could not be selected")
            if not await advance_run(ctx.run_id, RunStatus.PRODUCING, ctx.step_name):
                return STOP
            return output.model_dump(mode="json")

        chosen = await stage("select_topic", select_topic)
        if chosen["cancelled"]:
            return chosen
        candidate_id = chosen["candidate_id"]
        with (
            SetWorkflowID(f"produce-{run_id}-{candidate_id}"),
            SetWorkflowTimeout(get_runtime().settings.production_timeout_minutes * 60),
        ):
            handle = await DBOS.enqueue_workflow_async(QUEUE_PIPELINE, produce_article, run_id, candidate_id)
        child = handle.get_workflow_id()

        async def finish(ctx: StageContext) -> dict[str, Any]:
            await finish_attempt(ctx.sc.sessionmaker, workflow_id=ctx.workflow_id, status=AttemptStatus.SUCCEEDED)
            return {"run_id": run_id, "candidate_id": candidate_id, "production_workflow_id": child}

        return await stage("finish", finish)
    except (Exception, WorkflowCancelledError) as exc:
        await fail_workflow(workflow_name=WORKFLOW_DISCOVER_TOPICS, run_id=run_id, article_id=None, error=exc)
        raise
