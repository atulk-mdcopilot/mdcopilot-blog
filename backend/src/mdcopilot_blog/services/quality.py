"""Review APIs and version-bound human approval decisions."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas_common import ActionAccepted, ArticleStateOut, ReasonRequest
from mdcopilot_blog.api.schemas_quality import ApproveRequest
from mdcopilot_blog.db.models import Article, Review
from mdcopilot_blog.domain.contracts import HumanDecision
from mdcopilot_blog.domain.enums import ArticleStatus, Role
from mdcopilot_blog.domain.state_machine import Entity, InvalidTransition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.services import config as config_service
from mdcopilot_blog.services.article_status import set_article_status
from mdcopilot_blog.services.article_views import counting_gate, get_article
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.services.enqueue import enqueue_workflow, ensure_agent_enabled
from mdcopilot_blog.services.quality_steps import latest_review
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient


def to_state_out(article: Article) -> ArticleStateOut:
    return ArticleStateOut.model_validate(article)


async def approve_article(
    db: AsyncSession,
    *,
    article_id: uuid.UUID,
    request: ApproveRequest,
    principal: Principal,
    settings: Settings,
    now: datetime,
) -> Article:
    article = await get_article(db, article_id, lock=True)
    if request.version_id != article.current_version_id:
        raise ProblemError(409, "Version conflict", f"current version is {article.current_version_id}")
    if article.status not in {"READY_FOR_REVIEW", "QUALITY_GATE_FAILED"}:
        raise InvalidTransition(Entity.ARTICLE, article.status, "APPROVED")
    if await latest_review(db, request.version_id, "fact_check") is None:
        raise ProblemError(409, "Recheck required", f"no fact check for version {request.version_id}")
    gate = await counting_gate(db, request.version_id)
    needs_override = article.status == "QUALITY_GATE_FAILED" or gate is None or gate.verdict != "PASSED"
    verdict, reason = "APPROVED", None
    if needs_override:
        config = await config_service.load_effective_config(db, settings, run_id=article.run_id)
        if request.override_reason is None or config.gate_override_policy == "never":
            raise ProblemError(
                409,
                "Quality gates not passed",
                "a passing full, fix_pass or recheck gate report is required"
                if config.gate_override_policy != "never"
                else "gate override policy is never",
            )
        if principal.role != Role.ADMIN:
            raise ProblemError(403, "Forbidden", "only admins may approve a gate-failed version")
        if not request.override_reason.strip():
            raise ProblemError(422, "Override reason required", "an admin override needs a written reason")
        verdict, reason = "OVERRIDE_APPROVED", request.override_reason.strip()
    await set_article_status(db, article_id=article_id, target=ArticleStatus.APPROVED)
    article.approved_version_id, article.approved_by, article.approved_at = request.version_id, principal.user_id, now
    article.approval_mode, article.approval_override_reason = request.mode.value, reason
    decision = HumanDecision(decision=verdict, mode=request.mode, reason=reason, version_id=str(request.version_id))
    db.add(
        Review(
            id=uuid7(),
            article_id=article_id,
            version_id=request.version_id,
            kind="human",
            verdict=verdict,
            payload=decision.model_dump(mode="json"),
            created_by=principal.user_id,
            reason=reason,
        )
    )
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.approve",
        entity_type="blog_article",
        entity_id=str(article_id),
        reason=reason,
        details={"mode": request.mode.value, "versionId": str(request.version_id), "override": needs_override},
    )
    await db.commit()
    await db.refresh(article)
    return article


async def reject_article(
    db: AsyncSession, *, article_id: uuid.UUID, request: ReasonRequest, principal: Principal, now: datetime
) -> Article:
    article = await get_article(db, article_id, lock=True)
    if article.current_version_id is None or article.status == "REJECTED":
        raise InvalidTransition(Entity.ARTICLE, article.status, "REJECTED")
    await set_article_status(db, article_id=article_id, target=ArticleStatus.REJECTED)
    article.rejected_by, article.rejected_at, article.rejection_reason = principal.user_id, now, request.reason.strip()
    decision = HumanDecision(
        decision="REJECTED", mode=None, reason=article.rejection_reason, version_id=str(article.current_version_id)
    )
    db.add(
        Review(
            id=uuid7(),
            article_id=article_id,
            version_id=article.current_version_id,
            kind="human",
            verdict="REJECTED",
            payload=decision.model_dump(mode="json"),
            created_by=principal.user_id,
            reason=article.rejection_reason,
        )
    )
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.reject",
        entity_type="blog_article",
        entity_id=str(article_id),
        reason=article.rejection_reason,
        details={"versionId": str(article.current_version_id), "reason": article.rejection_reason},
    )
    await db.commit()
    await db.refresh(article)
    return article


async def request_recheck(
    db: AsyncSession, client: WorkflowClient, *, article_id: uuid.UUID, principal: Principal, settings: Settings
) -> ActionAccepted:
    article = await get_article(db, article_id, lock=True)
    ensure_agent_enabled(settings)
    if article.current_version_id is None or article.status not in {
        "READY_FOR_REVIEW",
        "QUALITY_GATE_FAILED",
        "APPROVED",
    }:
        raise ProblemError(409, "Invalid state transition", f"cannot recheck while the article is {article.status}")
    workflow_id = f"recheck-{article_id}-{uuid7()}"
    await db.commit()
    accepted = await enqueue_workflow(
        client,
        workflow_name="recheck_article",
        queue_name="interactive",
        workflow_id=workflow_id,
        args=(str(article_id),),
        timeout_seconds=settings.production_timeout_minutes * 60,
    )
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.recheck",
        entity_type="blog_article",
        entity_id=str(article_id),
        details={"workflow_id": workflow_id},
    )
    await db.commit()
    return ActionAccepted(
        workflow_id=accepted.workflow_id,
        workflow_name=accepted.workflow_name,
        queue=accepted.queue,
        run_id=article.run_id,
        article_id=article.id,
        candidate_id=article.candidate_id,
    )
