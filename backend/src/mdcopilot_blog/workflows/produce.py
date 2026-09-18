"""Article production and review stages, shared by initial runs and human actions."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from dbos import DBOS
from sqlalchemy import select

from mdcopilot_blog.db.models import Article, RunAttempt
from mdcopilot_blog.domain.contracts import RevisionFinding
from mdcopilot_blog.domain.enums import (
    ArticleComponent,
    ArticleStatus,
    AttemptStatus,
    ChangeKind,
    GateRunKind,
    RunStatus,
    SectionKey,
)
from mdcopilot_blog.research import deep as research
from mdcopilot_blog.services import article_steps, diversity, quality_steps
from mdcopilot_blog.workflows.names import WORKFLOW_PRODUCE_ARTICLE
from mdcopilot_blog.workflows.retry import WorkflowCancelledError
from mdcopilot_blog.workflows.runtime import get_runtime
from mdcopilot_blog.workflows.stages import (
    PROTECTED_ARTICLE_STATUSES,
    STOP,
    StageContext,
    StaleWorkflowError,
    advance_article,
    advance_run,
    fail_workflow,
    tracked_stage,
)
from mdcopilot_blog.workflows.tracking import finish_attempt


@dataclass
class Production:
    prefix: str
    workflow_name: str
    run_id: str | None
    pipeline: bool
    article_id: str | None = None
    version_id: str | None = None
    approval_at: str | None = None

    async def stage(
        self, name: str, body: Callable[[StageContext], Awaitable[dict[str, Any]]], agent: str | None = None
    ) -> dict[str, Any]:
        async def execute(ctx: StageContext) -> dict[str, Any]:
            if self.article_id and self.prefix != "publish":
                async with ctx.sc.sessionmaker() as db:
                    article = await db.get(Article, uuid.UUID(self.article_id))
                    if article is None:
                        raise LookupError("article not found")
                    if article.status in PROTECTED_ARTICLE_STATUSES and not (
                        self.prefix == "recheck" and article.status == "APPROVED"
                    ):
                        raise StaleWorkflowError(f"article is now {article.status}")
                    if (
                        self.prefix == "recheck"
                        and name != "open_attempt"
                        and (article.approved_at.isoformat() if article.approved_at else None) != self.approval_at
                    ):
                        raise StaleWorkflowError("article approval changed while rechecking")
            if self.pipeline and not await advance_run(ctx.run_id, RunStatus.PRODUCING, ctx.step_name):
                return STOP
            return await body(ctx)

        return await tracked_stage(
            f"{self.prefix}.{name}",
            run_id=self.run_id,
            article_id=self.article_id,
            workflow_name=self.workflow_name,
            body=execute,
            agent_name=agent,
        )


async def _avoid(ctx: StageContext, article_id: uuid.UUID) -> Any:
    async with ctx.sc.sessionmaker() as db:
        return await diversity.build_avoid_bundle(
            db, config=ctx.sc.config, brand=ctx.sc.brand, now=ctx.sc.now(), exclude_article_id=article_id
        )


async def open_production(p: Production) -> dict[str, Any]:
    async def opened(ctx: StageContext) -> dict[str, Any]:
        article = None
        if p.article_id:
            async with ctx.sc.sessionmaker() as db:
                article = await db.get(Article, uuid.UUID(p.article_id))
            if article is None:
                raise LookupError("article not found")
        return {
            "run_id": str(ctx.run_id),
            "candidate_id": str(article.candidate_id) if article else None,
            "version_id": str(article.current_version_id) if article and article.current_version_id else None,
            "approved_at": article.approved_at.isoformat() if article and article.approved_at else None,
        }

    result = await p.stage("open_attempt", opened)
    if not result["cancelled"]:
        p.version_id, p.approval_at = result["version_id"], result["approved_at"]
    return result


async def run_production(
    p: Production, *, candidate_id: str | None = None, start: str = "deep_research", instructions: str | None = None
) -> dict[str, Any]:
    packet_id = None
    if start == "deep_research":

        async def deep(ctx: StageContext) -> dict[str, Any]:
            if candidate_id is None:
                raise ValueError("candidate required for deep research")
            aid = await article_steps.ensure_article(ctx.sc, run_id=ctx.run_id, candidate_id=uuid.UUID(candidate_id))
            if p.article_id and aid != uuid.UUID(p.article_id):
                raise ValueError("candidate produced a different article")
            async with ctx.sc.sessionmaker() as db:
                article = await db.get(Article, aid)
                if article is None or article.status in PROTECTED_ARTICLE_STATUSES:
                    raise StaleWorkflowError("article cannot be regenerated in its current state")
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

        async def packet(ctx: StageContext) -> dict[str, Any]:
            output = await article_steps.build_research_packet(
                ctx.sc, article_id=uuid.UUID(str(p.article_id)), research_run_id=uuid.UUID(result["research_run_id"])
            )
            return output.model_dump(mode="json")

        packet_result = await p.stage("build_research_packet", packet, "deep_research")
        if packet_result["cancelled"]:
            return packet_result
        packet_id = packet_result["packet_id"]
    if p.article_id is None:
        raise ValueError("article required")
    aid = uuid.UUID(p.article_id)

    async def write(ctx: StageContext) -> dict[str, Any]:
        async with ctx.sc.sessionmaker() as db:
            pid = uuid.UUID(packet_id) if packet_id else await article_steps.latest_packet_id(db, article_id=aid)
        if pid is None:
            raise LookupError("article has no research packet")
        await advance_article(aid, ArticleStatus.DRAFTING)
        output = await article_steps.write_draft(
            ctx.sc, article_id=aid, packet_id=pid, avoid=await _avoid(ctx, aid), instructions=instructions
        )
        await advance_article(aid, ArticleStatus.DRAFTING, version_id=str(output.version_id))
        return output.model_dump(mode="json")

    draft = await p.stage("write_draft", write, "writer")
    if draft["cancelled"]:
        return draft
    p.version_id = version_id = draft["version_id"]
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
        output = await quality_steps.editorial_review(
            ctx.sc, article_id=aid, version_id=uuid.UUID(version_id), avoid=await _avoid(ctx, aid)
        )
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
        p.version_id = version_id = revised["version_id"]
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
        if p.prefix != "recheck":
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
            avoid=await _avoid(ctx, aid),
            change_kind=ChangeKind.FIX_PASS if fix else ChangeKind.REVISION,
        )
        await advance_article(aid, ArticleStatus.DRAFTING, version_id=str(output.version_id))
        return output.model_dump(mode="json")

    return await p.stage("fix_pass.revise" if fix else "revise", body, "writer")


async def quality_tail(p: Production, version_id: str, *, recheck: bool = False) -> dict[str, Any]:
    aid = uuid.UUID(str(p.article_id))

    async def gates(name: str, fix_used: bool) -> dict[str, Any]:
        async def body(ctx: StageContext) -> dict[str, Any]:
            result = await quality_steps.run_quality_gates(
                ctx.sc,
                article_id=aid,
                version_id=uuid.UUID(version_id),
                run_kind=GateRunKind.RECHECK if recheck else GateRunKind.FIX_PASS if fix_used else GateRunKind.FULL,
                fix_pass_used=fix_used,
            )
            return {
                "review_id": str(result.review_id),
                **result.decision.model_dump(mode="json"),
                "passed": result.report.passed,
            }

        return await p.stage(name, body)

    result = await gates("quality_gates", recheck)
    if result["cancelled"]:
        return result
    if result["action"] == "fix_pass" and not recheck:
        if result["findings"]:
            revised = await revise_stage(p, version_id, result["findings"], fix=True)
            if revised["cancelled"]:
                return revised
            p.version_id = version_id = revised["version_id"]
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
    status = ArticleStatus.READY_FOR_REVIEW if result["action"] == "ready" else ArticleStatus.QUALITY_GATE_FAILED

    async def finish(ctx: StageContext) -> dict[str, Any]:
        async with ctx.sc.sessionmaker() as db:
            attempt = await db.get(RunAttempt, ctx.attempt_id, with_for_update=True)
            if attempt is None or attempt.status == "CANCELLED":
                return STOP
            article = await db.scalar(select(Article).where(Article.id == aid).with_for_update())
            if article is None or str(article.current_version_id) != version_id:
                raise StaleWorkflowError("article version changed before quality completion")
            if recheck and article.status == "APPROVED":
                if (article.approved_at.isoformat() if article.approved_at else None) != p.approval_at:
                    raise StaleWorkflowError("article was approved while this recheck was running")
                # Rechecking an approved version requires a fresh human decision on the new report.
                article.status = "READY_FOR_REVIEW"
                article.approved_version_id = article.approved_by = article.approved_at = None
                article.approval_mode = None
            await advance_article(aid, status, version_id=version_id, db=db)
            await db.commit()
        if p.pipeline:
            await advance_run(ctx.run_id, RunStatus.SUCCEEDED, ctx.step_name)
        await finish_attempt(ctx.sc.sessionmaker, workflow_id=ctx.workflow_id, status=AttemptStatus.SUCCEEDED)
        return {"article_id": str(aid), "version_id": version_id, "status": status.value, "run_id": str(ctx.run_id)}

    return await p.stage("finish", finish)


@DBOS.workflow(name=WORKFLOW_PRODUCE_ARTICLE)
async def produce_article(run_id: str, candidate_id: str) -> dict[str, Any]:
    p = Production("produce", WORKFLOW_PRODUCE_ARTICLE, run_id, True)
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
                        Article.status.not_in(["REJECTED", "SUPERSEDED"]),
                    )
                )
                p.article_id = str(aid) if aid else None
        await fail_workflow(
            workflow_name=p.workflow_name, run_id=run_id, article_id=p.article_id, error=exc, version_id=p.version_id
        )
        raise


async def write_component_stage(
    p: Production, version_id: str, component: str, section_key: str | None, instructions: str | None
) -> dict[str, Any]:
    async def body(ctx: StageContext) -> dict[str, Any]:
        aid = uuid.UUID(str(p.article_id))
        return (
            await article_steps.regenerate_component(
                ctx.sc,
                article_id=aid,
                base_version_id=uuid.UUID(version_id),
                component=ArticleComponent(component),
                section_key=SectionKey(section_key) if section_key else None,
                instructions=instructions,
                avoid=await _avoid(ctx, aid),
            )
        ).model_dump(mode="json")

    return await p.stage("write_component", body, "writer")
