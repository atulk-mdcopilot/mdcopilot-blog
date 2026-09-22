"""Article production and review stages."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from dbos import DBOS
from sqlalchemy import select

from mdcopilot_blog.db.models import Article
from mdcopilot_blog.domain.contracts import RevisionFinding
from mdcopilot_blog.domain.enums import ArticleStatus, AttemptStatus, ChangeKind, GateRunKind, RunStatus
from mdcopilot_blog.research import deep as research
from mdcopilot_blog.services import article_steps, publications, quality_steps
from mdcopilot_blog.workflows.names import WORKFLOW_PRODUCE_ARTICLE
from mdcopilot_blog.workflows.retry import WorkflowCancelledError
from mdcopilot_blog.workflows.runtime import get_runtime
from mdcopilot_blog.workflows.stages import (
    STOP,
    StageContext,
    advance_article,
    advance_run,
    fail_workflow,
    tracked_stage,
)
from mdcopilot_blog.workflows.tracking import finish_attempt

logger = logging.getLogger(__name__)


@dataclass
class Production:
    run_id: str
    article_id: str | None = None

    async def stage(
        self, name: str, body: Callable[[StageContext], Awaitable[dict[str, Any]]], agent: str | None = None
    ) -> dict[str, Any]:
        async def execute(ctx: StageContext) -> dict[str, Any]:
            if not await advance_run(ctx.run_id, RunStatus.PRODUCING, ctx.step_name):
                return STOP
            return await body(ctx)

        return await tracked_stage(
            f"produce.{name}",
            run_id=self.run_id,
            article_id=self.article_id,
            workflow_name=WORKFLOW_PRODUCE_ARTICLE,
            body=execute,
            agent_name=agent,
        )


async def open_production(p: Production) -> dict[str, Any]:
    async def opened(ctx: StageContext) -> dict[str, Any]:
        return {"run_id": str(ctx.run_id)}

    return await p.stage("open_attempt", opened)


async def run_production(p: Production, *, candidate_id: str) -> dict[str, Any]:
    async def deep(ctx: StageContext) -> dict[str, Any]:
        aid = await article_steps.ensure_article(ctx.sc, run_id=ctx.run_id, candidate_id=uuid.UUID(candidate_id))
        result = await research.run_deep_research(
            ctx.sc.with_ids(article_id=aid, topic_candidate_id=uuid.UUID(candidate_id)),
            article_id=aid,
            candidate_id=uuid.UUID(candidate_id),
        )
        return {"article_id": str(aid), "research_run_id": str(result.research_run_id)}

    result = await p.stage("deep_research", deep, "deep_research")
    if result["cancelled"]:
        return result
    p.article_id = result["article_id"]
    aid = uuid.UUID(result["article_id"])

    async def packet(ctx: StageContext) -> dict[str, Any]:
        output = await article_steps.build_research_packet(
            ctx.sc, article_id=aid, research_run_id=uuid.UUID(result["research_run_id"])
        )
        return output.model_dump(mode="json")

    packet_result = await p.stage("build_research_packet", packet, "deep_research")
    if packet_result["cancelled"]:
        return packet_result

    async def write(ctx: StageContext) -> dict[str, Any]:
        await advance_article(aid, ArticleStatus.DRAFTING)
        output = await article_steps.write_draft(
            ctx.sc, article_id=aid, packet_id=uuid.UUID(packet_result["packet_id"])
        )
        await advance_article(aid, ArticleStatus.DRAFTING, version_id=str(output.version_id))
        return output.model_dump(mode="json")

    draft = await p.stage("write_draft", write, "writer")
    if draft["cancelled"]:
        return draft
    # A finished draft is never lost: from here on a failed review stage is reported with the draft instead of
    # failing the run. Cancellation is not an Exception (DBOS raises a BaseException), so it still propagates.
    review_error = None
    try:
        result = await review_draft(p, draft["version_id"])
        if result["cancelled"]:
            return result
    except Exception as exc:  # noqa: BLE001 - any review failure still saves the draft
        logger.warning("review failed, saving the draft anyway", extra={"error_class": type(exc).__name__})
        review_error = f"automated review did not complete: {type(exc).__name__}: {str(exc)[:300]}"
    return await push_stage(p, review_error)


async def review_draft(p: Production, version_id: str) -> dict[str, Any]:
    aid = uuid.UUID(str(p.article_id))
    result = await fact_stage(p, version_id, "fact_check")
    if result["cancelled"]:
        return result

    async def clinical(ctx: StageContext) -> dict[str, Any]:
        await advance_article(aid, ArticleStatus.CLINICAL_REVIEW, version_id=version_id)
        return (
            await quality_steps.clinical_review(ctx.sc, article_id=aid, version_id=uuid.UUID(version_id))
        ).model_dump(mode="json")

    result = await p.stage("clinical_review", clinical, "clinical")
    if result["cancelled"]:
        return result

    async def editorial(ctx: StageContext) -> dict[str, Any]:
        await advance_article(aid, ArticleStatus.EDITORIAL_REVIEW, version_id=version_id)
        output = await quality_steps.editorial_review(ctx.sc, article_id=aid, version_id=uuid.UUID(version_id))
        async with ctx.sc.sessionmaker() as db:
            findings = await quality_steps.collect_revision_findings(
                db, article_id=aid, version_id=uuid.UUID(version_id)
            )
        return {
            **output.model_dump(mode="json"),
            "findings": [f.model_dump(mode="json") for f in findings],
            "revision_required": any(f.required for f in findings),
        }

    review = await p.stage("editorial_review", editorial, "editorial")
    if review["cancelled"]:
        return review
    if review["revision_required"]:
        revised = await revise_stage(p, version_id, review["findings"], fix=False)
        if revised["cancelled"]:
            return revised
        version_id = revised["version_id"]
        result = await fact_stage(p, version_id, "verify_facts")
        if result["cancelled"]:
            return result
    result = await seo_stage(p, version_id, "seo")
    if result["cancelled"]:
        return result
    return await quality_tail(p, version_id)


async def fact_stage(p: Production, version_id: str, name: str) -> dict[str, Any]:
    async def body(ctx: StageContext) -> dict[str, Any]:
        aid = uuid.UUID(str(p.article_id))
        await advance_article(aid, ArticleStatus.FACT_CHECKING, version_id=version_id)
        return (await quality_steps.fact_check(ctx.sc, article_id=aid, version_id=uuid.UUID(version_id))).model_dump(
            mode="json"
        )

    return await p.stage(name, body, "fact_check")


async def seo_stage(p: Production, version_id: str, name: str) -> dict[str, Any]:
    async def body(ctx: StageContext) -> dict[str, Any]:
        aid = uuid.UUID(str(p.article_id))
        await advance_article(aid, ArticleStatus.SEO, version_id=version_id)
        return (await quality_steps.generate_seo(ctx.sc, article_id=aid, version_id=uuid.UUID(version_id))).model_dump(
            mode="json"
        )

    return await p.stage(name, body, "seo")


async def revise_stage(p: Production, version_id: str, findings: list[dict[str, Any]], *, fix: bool) -> dict[str, Any]:
    async def body(ctx: StageContext) -> dict[str, Any]:
        aid = uuid.UUID(str(p.article_id))
        output = await article_steps.revise_article(
            ctx.sc,
            article_id=aid,
            base_version_id=uuid.UUID(version_id),
            findings=[RevisionFinding.model_validate(f) for f in findings],
            change_kind=ChangeKind.FIX_PASS if fix else ChangeKind.REVISION,
        )
        await advance_article(aid, ArticleStatus.DRAFTING, version_id=str(output.version_id))
        return output.model_dump(mode="json")

    return await p.stage("fix_pass.revise" if fix else "revise", body, "writer")


async def quality_tail(p: Production, version_id: str) -> dict[str, Any]:
    aid = uuid.UUID(str(p.article_id))

    async def gates(name: str, fix_used: bool) -> dict[str, Any]:
        async def body(ctx: StageContext) -> dict[str, Any]:
            result = await quality_steps.run_quality_gates(
                ctx.sc,
                article_id=aid,
                version_id=uuid.UUID(version_id),
                run_kind=GateRunKind.FIX_PASS if fix_used else GateRunKind.FULL,
                fix_pass_used=fix_used,
            )
            return {
                "review_id": str(result.review_id),
                **result.decision.model_dump(mode="json"),
                "passed": result.report.passed,
            }

        return await p.stage(name, body)

    result = await gates("quality_gates", False)
    if result["cancelled"]:
        return result
    if result["action"] == "fix_pass":
        if result["findings"]:
            revised = await revise_stage(p, version_id, result["findings"], fix=True)
            if revised["cancelled"]:
                return revised
            version_id = revised["version_id"]
            checked = await fact_stage(p, version_id, "fix_pass.verify_facts")
            if checked["cancelled"]:
                return checked
            rerun_seo = result["seo_rerun"] or revised.get("title_changed", False)
        else:
            rerun_seo = result["seo_rerun"]
        if rerun_seo:
            seo = await seo_stage(p, version_id, "fix_pass.seo")
            if seo["cancelled"]:
                return seo
        result = await gates("fix_pass.quality_gates", True)
        if result["cancelled"]:
            return result
    return result


async def push_stage(p: Production, review_error: str | None) -> dict[str, Any]:
    aid = uuid.UUID(str(p.article_id))

    async def body(ctx: StageContext) -> dict[str, Any]:
        blog_id = await publications.save_draft(ctx.sc, run_id=ctx.run_id, article_id=aid, review_error=review_error)
        if not await advance_run(ctx.run_id, RunStatus.SUCCEEDED, ctx.step_name):
            return STOP
        await finish_attempt(ctx.sc.sessionmaker, workflow_id=ctx.workflow_id, status=AttemptStatus.SUCCEEDED)
        return {"article_id": str(aid), "backend_blog_id": blog_id, "run_id": str(ctx.run_id)}

    return await p.stage("push_draft", body)


@DBOS.workflow(name=WORKFLOW_PRODUCE_ARTICLE)
async def produce_article(run_id: str, candidate_id: str) -> dict[str, Any]:
    p = Production(run_id)
    try:
        opened = await open_production(p)
        if opened["cancelled"]:
            return opened
        return await run_production(p, candidate_id=candidate_id)
    except (Exception, WorkflowCancelledError) as exc:
        if p.article_id is None:
            async with get_runtime().sessionmaker() as db:
                aid = await db.scalar(
                    select(Article.id).where(
                        Article.run_id == uuid.UUID(run_id),
                        Article.candidate_id == uuid.UUID(candidate_id),
                    )
                )
                p.article_id = str(aid) if aid else None
        await fail_workflow(
            workflow_name=WORKFLOW_PRODUCE_ARTICLE,
            run_id=run_id,
            article_id=p.article_id,
            error=exc,
        )
        raise
