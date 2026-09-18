"""Durable human actions; attempts share the original run without reopening it."""

import uuid
from datetime import UTC, datetime
from typing import Any

from dbos import DBOS
from sqlalchemy import select

from mdcopilot_blog.db.models import Article, RunAttempt, TopicCandidateRecord
from mdcopilot_blog.domain.enums import AttemptStatus
from mdcopilot_blog.services import article_steps
from mdcopilot_blog.services.publication_steps import publish_article as publish_step
from mdcopilot_blog.workflows.names import (
    WORKFLOW_CHANGE_TOPIC,
    WORKFLOW_PUBLISH_ARTICLE,
    WORKFLOW_RECHECK_ARTICLE,
    WORKFLOW_REGENERATE_ARTICLE,
    WORKFLOW_REGENERATE_COMPONENT,
    WORKFLOW_REGENERATE_RESEARCH,
)
from mdcopilot_blog.workflows.produce import (
    Production,
    fact_stage,
    open_production,
    quality_tail,
    run_production,
    seo_stage,
    write_component_stage,
)
from mdcopilot_blog.workflows.retry import WorkflowCancelledError
from mdcopilot_blog.workflows.stages import (
    PROTECTED_ARTICLE_STATUSES,
    StageContext,
    StaleWorkflowError,
    fail_workflow,
    tracked_stage,
)
from mdcopilot_blog.workflows.tracking import finish_attempt


async def _human(
    article_id: str,
    *,
    name: str,
    prefix: str,
    instructions: str | None = None,
    component: str | None = None,
    section_key: str | None = None,
) -> dict[str, Any]:
    p = Production(prefix, name, None, False, article_id)
    try:
        info = await open_production(p)
        if info["cancelled"]:
            return info
        p.run_id = info["run_id"]
        if prefix == "recheck":
            checked = await fact_stage(p, info["version_id"], "fact_check")
            return checked if checked["cancelled"] else await quality_tail(p, info["version_id"], recheck=True)
        if component:
            draft = await write_component_stage(p, info["version_id"], component, section_key, instructions)
            if draft["cancelled"]:
                return draft
            p.version_id = draft["version_id"]
            checked = await fact_stage(p, draft["version_id"], "fact_check")
            if checked["cancelled"]:
                return checked
            if draft["title_changed"]:
                seo = await seo_stage(p, draft["version_id"], "seo")
                if seo["cancelled"]:
                    return seo
            return await quality_tail(p, draft["version_id"])
        return await run_production(
            p,
            candidate_id=info["candidate_id"],
            start="deep_research" if prefix == "regenerate_research" else "write_draft",
            instructions=instructions,
        )
    except (Exception, WorkflowCancelledError) as exc:
        await fail_workflow(
            workflow_name=name, run_id=p.run_id, article_id=article_id, error=exc, version_id=p.version_id
        )
        raise


@DBOS.workflow(name=WORKFLOW_REGENERATE_COMPONENT)
async def regenerate_component(
    article_id: str, component: str, section_key: str | None, instructions: str | None
) -> dict[str, Any]:
    return await _human(
        article_id,
        name=WORKFLOW_REGENERATE_COMPONENT,
        prefix="regenerate_component",
        component=component,
        section_key=section_key,
        instructions=instructions,
    )


@DBOS.workflow(name=WORKFLOW_REGENERATE_ARTICLE)
async def regenerate_article(article_id: str, instructions: str | None) -> dict[str, Any]:
    return await _human(
        article_id, name=WORKFLOW_REGENERATE_ARTICLE, prefix="regenerate_article", instructions=instructions
    )


@DBOS.workflow(name=WORKFLOW_REGENERATE_RESEARCH)
async def regenerate_research(article_id: str) -> dict[str, Any]:
    return await _human(article_id, name=WORKFLOW_REGENERATE_RESEARCH, prefix="regenerate_research")


@DBOS.workflow(name=WORKFLOW_RECHECK_ARTICLE)
async def recheck_article(article_id: str) -> dict[str, Any]:
    return await _human(article_id, name=WORKFLOW_RECHECK_ARTICLE, prefix="recheck")


@DBOS.workflow(name=WORKFLOW_CHANGE_TOPIC)
async def change_topic(run_id: str, candidate_id: str) -> dict[str, Any]:
    p = Production("change_topic", WORKFLOW_CHANGE_TOPIC, run_id, True)
    try:

        async def validate(ctx: StageContext) -> dict[str, Any]:
            async with ctx.sc.sessionmaker() as db:
                protected = await db.scalar(
                    select(Article.id)
                    .where(
                        Article.run_id == ctx.run_id,
                        Article.status.in_(PROTECTED_ARTICLE_STATUSES - {"REJECTED", "SUPERSEDED"}),
                    )
                    .limit(1)
                )
                if protected:
                    raise StaleWorkflowError("cannot change the topic of an approved or published article")
            return {}

        opened = await tracked_stage(
            "change_topic.open_attempt", run_id=run_id, workflow_name=WORKFLOW_CHANGE_TOPIC, body=validate
        )
        if opened["cancelled"]:
            return opened

        async def supersede(ctx: StageContext) -> dict[str, Any]:
            new_id = await article_steps.ensure_article(ctx.sc, run_id=ctx.run_id, candidate_id=uuid.UUID(candidate_id))
            async with ctx.sc.sessionmaker() as db:
                rows = list(
                    await db.scalars(
                        select(Article)
                        .where(
                            Article.run_id == ctx.run_id,
                            Article.candidate_id != uuid.UUID(candidate_id),
                            Article.status.not_in(["REJECTED", "SUPERSEDED"]),
                        )
                        .with_for_update()
                    )
                )
                for article in rows:
                    if article.status not in {
                        "DRAFTING",
                        "FACT_CHECKING",
                        "CLINICAL_REVIEW",
                        "EDITORIAL_REVIEW",
                        "SEO",
                        "READY_FOR_REVIEW",
                        "QUALITY_GATE_FAILED",
                        "FAILED",
                    }:
                        raise StaleWorkflowError("cannot supersede an approved or published article")
                    article.status = "SUPERSEDED"
                    article.superseded_by_article_id = new_id
                    candidate = await db.get(TopicCandidateRecord, article.candidate_id)
                    if candidate and candidate.status == "SELECTED":
                        candidate.status = "SUPERSEDED"
                attempts = list(
                    await db.scalars(
                        select(RunAttempt)
                        .where(
                            RunAttempt.run_id == ctx.run_id,
                            RunAttempt.workflow_name.in_(["produce_article", "change_topic"]),
                            RunAttempt.dbos_workflow_id != ctx.workflow_id,
                            RunAttempt.status.in_(["ENQUEUED", "RUNNING"]),
                        )
                        .with_for_update()
                    )
                )
                for attempt in attempts:
                    attempt.status, attempt.finished_at = "CANCELLED", datetime.now(UTC)
                workflow_ids = {a.dbos_workflow_id for a in attempts} | {
                    f"produce-{run_id}-{a.candidate_id}" for a in rows
                }
                # Recover a crash after this transaction but before cancelling DBOS.
                superseded = list(await db.scalars(select(Article).where(Article.superseded_by_article_id == new_id)))
                workflow_ids.update(f"produce-{run_id}-{a.candidate_id}" for a in superseded)
                await db.commit()
            for workflow_id in workflow_ids:
                if await DBOS.list_workflows_async(workflow_ids=[workflow_id], load_input=False, load_output=False):
                    await DBOS.cancel_workflow_async(workflow_id)
            return {"article_id": str(new_id)}

        result = await p.stage("supersede", supersede)
        if not result["cancelled"]:
            p.article_id = result["article_id"]
        return result if result["cancelled"] else await run_production(p, candidate_id=candidate_id)
    except (Exception, WorkflowCancelledError) as exc:
        await fail_workflow(
            workflow_name=p.workflow_name, run_id=run_id, article_id=p.article_id, error=exc, version_id=p.version_id
        )
        raise


@DBOS.workflow(name=WORKFLOW_PUBLISH_ARTICLE)
async def publish_article(article_id: str, version_id: str, as_draft: bool) -> dict[str, Any]:
    p = Production("publish", WORKFLOW_PUBLISH_ARTICLE, None, False, article_id)
    try:
        opened = await open_production(p)
        if opened["cancelled"]:
            return opened
        p.run_id = opened["run_id"]

        async def publish(ctx: StageContext) -> dict[str, Any]:
            result = await publish_step(
                ctx.sc.sessionmaker,
                settings=ctx.sc.settings,
                config=ctx.sc.config,
                article_id=uuid.UUID(article_id),
                version_id=uuid.UUID(version_id),
                as_draft=as_draft,
            )
            return result.model_dump(mode="json")

        result = await tracked_stage(
            "publish.publish",
            run_id=p.run_id,
            article_id=article_id,
            workflow_name=WORKFLOW_PUBLISH_ARTICLE,
            body=publish,
            retries=False,
        )
        if result["cancelled"]:
            return result

        async def finish(ctx: StageContext) -> dict[str, Any]:
            failed = result["status"] == "FAILED"
            if failed:
                async with ctx.sc.sessionmaker() as db:
                    await db.commit()
            await finish_attempt(
                ctx.sc.sessionmaker,
                workflow_id=ctx.workflow_id,
                status=AttemptStatus.FAILED if failed else AttemptStatus.SUCCEEDED,
            )
            return result

        return await p.stage("finish", finish)
    except (Exception, WorkflowCancelledError) as exc:
        await fail_workflow(
            workflow_name=p.workflow_name, run_id=p.run_id, article_id=article_id, error=exc, version_id=version_id
        )
        raise
