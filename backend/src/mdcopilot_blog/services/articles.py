"""Human edits, optimistic version checks and audited regeneration requests."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.api.deps import Principal
from mdcopilot_blog.api.schemas_articles import ArticleEditRequest, RegenerateRequest, SelectTitleRequest
from mdcopilot_blog.api.schemas_common import ActionAccepted
from mdcopilot_blog.db.models import Article, ResearchPacketRecord, VersionSeo
from mdcopilot_blog.domain.article_assembly import edit_content, merge_seo
from mdcopilot_blog.domain.contracts import SEOMetadata
from mdcopilot_blog.domain.enums import ArticleStatus
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.services import article_views, quality_steps, versions
from mdcopilot_blog.services import config as config_service
from mdcopilot_blog.services.article_status import set_article_status
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.services.enqueue import enqueue_workflow, ensure_agent_enabled
from mdcopilot_blog.services.versions import effective_seo
from mdcopilot_blog.settings import Settings
from mdcopilot_blog.workflows.client import WorkflowClient
from mdcopilot_blog.workflows.names import QUEUE_INTERACTIVE

EDITABLE_STATUSES = {"READY_FOR_REVIEW", "QUALITY_GATE_FAILED", "APPROVED"}
REGENERATE_STATUSES = {"READY_FOR_REVIEW", "QUALITY_GATE_FAILED"}
TITLE_LOCKED_STATUSES = {
    "APPROVED",
    "SCHEDULED",
    "EXPORTED",
    "PUBLISHING",
    "PUBLISHED",
    "PUBLISH_FAILED",
    "REJECTED",
    "SUPERSEDED",
}


async def request_regeneration(
    db: AsyncSession,
    client: WorkflowClient,
    *,
    article_id: uuid.UUID,
    body: RegenerateRequest,
    principal: Principal,
    settings: Settings,
) -> ActionAccepted:
    article = await article_views.get_article(db, article_id, lock=True)
    ensure_agent_enabled(settings)
    component = body.component.value
    allowed = REGENERATE_STATUSES | ({"FAILED"} if component == "research" else set())
    if article.status not in allowed or (component != "research" and article.current_version_id is None):
        raise ProblemError(
            409, "Invalid state transition", f"cannot regenerate {component} while the article is {article.status}"
        )
    suffix = component if component in {"article", "research"} else "component"
    workflow = f"regenerate_{suffix}"
    workflow_id = f"regen-{suffix}-{article.id}-{uuid7()}"
    args = (
        (str(article.id),)
        if suffix == "research"
        else (str(article.id), body.instructions)
        if suffix == "article"
        else (str(article.id), component, body.section_key.value if body.section_key else None, body.instructions)
    )
    await db.commit()
    accepted = await enqueue_workflow(
        client,
        workflow_name=workflow,
        queue_name=QUEUE_INTERACTIVE,
        workflow_id=workflow_id,
        args=args,
        timeout_seconds=settings.production_timeout_minutes * 60,
    )
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.regenerate",
        entity_type="blog_article",
        entity_id=str(article.id),
        details={
            "component": component,
            "section_key": body.section_key,
            "instructions": body.instructions,
            "workflow_id": workflow_id,
        },
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


async def select_title(
    db: AsyncSession, *, article_id: uuid.UUID, body: SelectTitleRequest, principal: Principal
) -> Article:
    article = await article_views.get_article(db, article_id, lock=True)
    if article.status in TITLE_LOCKED_STATUSES:
        raise ProblemError(
            409, "Invalid state transition", f"titles cannot change while the article is {article.status}"
        )
    if body.key:
        if article.current_version_id is None:
            raise ProblemError(422, "Request validation failed", "the article has no title options yet")
        version = await article_views.get_version(db, article.id, article.current_version_id)
        article.title = version.title_options[body.key]
        article.selected_title_key = body.key
    else:
        article.title, article.selected_title_key = body.custom_title, "custom"
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.select_title",
        entity_type="blog_article",
        entity_id=str(article.id),
        details={"key": article.selected_title_key, "title": article.title},
    )
    await db.commit()
    await db.refresh(article)
    return article


async def edit_article(
    db: AsyncSession,
    *,
    article_id: uuid.UUID,
    body: ArticleEditRequest,
    principal: Principal,
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> Article:
    article = await article_views.get_article(db, article_id, lock=True)
    if article.status not in EDITABLE_STATUSES:
        raise ProblemError(
            409,
            "Invalid state transition",
            f"articles can be edited only in READY_FOR_REVIEW, QUALITY_GATE_FAILED or APPROVED; this article is {article.status}",
        )
    if body.base_version_id != article.current_version_id:
        raise ProblemError(
            409,
            "Version conflict",
            f"base version {body.base_version_id} is not the current version {article.current_version_id}",
        )
    fields = sorted(key for key, value in body.model_dump().items() if key != "baseVersionId" and value is not None)
    changes_content = any(
        value is not None
        for value in (body.content_markdown, body.title_options, body.pull_quote, body.cta, body.excerpt, body.seo)
    )
    if body.tags is not None:
        article.tags = body.tags
    if body.category is not None:
        article.category = body.category
    if not changes_content:
        await audit(
            db,
            actor_user_id=principal.user_id,
            action="article.edit",
            entity_type="blog_article",
            entity_id=str(article.id),
            details={"version_id": None, "base_version_id": str(body.base_version_id), "fields": fields},
        )
        await db.commit()
        await db.refresh(article)
        return article
    base = await article_views.get_version(db, article_id, body.base_version_id)
    content = edit_content(
        versions.version_content(base),
        content_markdown=body.content_markdown,
        title_options=body.title_options,
        pull_quote=body.pull_quote,
        cta=body.cta,
        excerpt=body.excerpt,
    )
    packet = await db.get(ResearchPacketRecord, base.research_packet_id) if base.research_packet_id else None
    old_seo = await effective_seo(db, version_id=base.id)
    if body.seo and old_seo is None:
        raise ProblemError(422, "Request validation failed", "the base version has no SEO record to edit")
    seo = SEOMetadata.model_validate(old_seo.seo) if old_seo else None
    if body.seo:
        if seo is None:
            raise ProblemError(422, "Request validation failed", "the base version has no SEO record to edit")
        seo = merge_seo(seo, body.seo.model_dump(exclude_none=True))
    if seo:
        await db.execute(text("SELECT pg_advisory_xact_lock(717049661)"))
    if seo and await db.scalar(
        select(Article.id)
        .where(Article.slug == seo.slug, Article.id != article_id, Article.status.notin_(["REJECTED", "SUPERSEDED"]))
        .limit(1)
    ):
        raise ProblemError(409, "Slug already in use", seo.slug)
    row = await versions.save_version(
        db,
        article=article,
        content=content,
        packet=packet,
        parent_id=base.id,
        change_kind="human_edit",
        change_scope={"fields": fields},
        created_by=principal.user_id,
    )
    if seo:
        db.add(
            VersionSeo(
                id=uuid7(),
                version_id=row.id,
                seo=seo.model_dump(mode="json"),
                social=old_seo.social if old_seo else None,
                slug=seo.slug,
                created_by=principal.user_id,
            )
        )
        article.slug = seo.slug
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="article.edit",
        entity_type="blog_article",
        entity_id=str(article.id),
        details={"version_id": str(row.id), "base_version_id": str(body.base_version_id), "fields": fields},
    )
    await db.commit()
    from mdcopilot_blog.services.diversity import record_version_features
    from mdcopilot_blog.services.step_context import build_api_step_context

    sc = await build_api_step_context(
        settings=settings, sessionmaker=sessionmaker, run_id=article.run_id, article_id=article.id
    )
    try:
        await record_version_features(sc, version_id=row.id)
    except Exception as exc:
        raise ProblemError(
            503,
            "Version features not recorded",
            f"features for version {row.id} were not recorded; save again or run a re-check",
        ) from exc
    # Re-lock after the feature transaction and never overwrite a concurrently created head.
    await db.refresh(article)
    article = await article_views.get_article(db, article_id, lock=True)
    if article.current_version_id != row.id:
        raise ProblemError(409, "Version conflict", "article changed while edit checks were running")
    config = await config_service.load_effective_config(db, settings, run_id=article.run_id)
    brand = await config_service.load_brand_profile(db)
    report = await quality_steps.run_deterministic_gates(
        db, article_id=article.id, version_id=row.id, config=config, brand=brand
    )
    target = ArticleStatus.READY_FOR_REVIEW if report.passed else ArticleStatus.QUALITY_GATE_FAILED
    if article.status == "APPROVED":
        await set_article_status(db, article_id=article_id, target=ArticleStatus.READY_FOR_REVIEW)
    if article.status != target.value:
        await set_article_status(db, article_id=article.id, target=target)
    await db.commit()
    await db.refresh(article)
    return article
