"""Durable publication steps, with short transactions surrounding network I/O."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import Article, Publication, User
from mdcopilot_blog.domain.config import EffectiveConfig
from mdcopilot_blog.domain.enums import ArticleStatus, Permission, PublicationStatus, Role
from mdcopilot_blog.domain.rbac import permissions_for
from mdcopilot_blog.domain.state_machine import Entity, InvalidTransition, require_transition
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.ids import uuid7
from mdcopilot_blog.publishing.base import PublicationResult
from mdcopilot_blog.publishing.factory import (
    build_publisher,
    ensure_network_publishing,
    idempotency_key,
    network_publishing_active,
    publisher_target,
)
from mdcopilot_blog.services.article_status import set_article_status
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.services.publications import export_locked, get_article, render_version
from mdcopilot_blog.settings import Settings


class PublishOutcome(BaseModel):
    publication_id: uuid.UUID
    status: PublicationStatus
    article_status: ArticleStatus
    external_post_id: str | None
    published_url: str | None
    error: str | None


class DueArticle(BaseModel):
    article_id: uuid.UUID
    version_id: uuid.UUID
    scheduled_for: datetime
    scheduled_by: uuid.UUID | None


class DueOutcome(BaseModel):
    article_id: uuid.UUID
    action: Literal["exported", "published", "publish_failed", "skipped_state", "skipped_permission"]
    publication_id: uuid.UUID | None
    detail: str | None = None


class ScheduleChanged(RuntimeError):
    """The human changed the schedule before the publishing claim was acquired."""


def _outcome(row: Publication, article: Article) -> PublishOutcome:
    return PublishOutcome(
        publication_id=row.id,
        status=PublicationStatus(row.status),
        article_status=ArticleStatus(article.status),
        external_post_id=row.external_post_id,
        published_url=row.published_url,
        error=str(row.last_error.get("message")) if row.last_error else None,
    )


async def publish_article(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    settings: Settings,
    config: EffectiveConfig,
    article_id: uuid.UUID,
    version_id: uuid.UUID,
    as_draft: bool,
    scheduled_for: datetime | None = None,
) -> PublishOutcome:
    ensure_network_publishing(settings, config)
    key = str(config.publisher)
    target, ikey = publisher_target(settings, key), idempotency_key(key, version_id)
    async with sessionmaker() as db:
        article = await get_article(db, article_id, lock=True)
        if scheduled_for is not None and (
            article.status not in {"SCHEDULED", "PUBLISHING"} or article.scheduled_for != scheduled_for
        ):
            raise ScheduleChanged("article schedule changed before publishing")
        if version_id != article.approved_version_id:
            raise ValueError(f"version {version_id} is not the approved version of article {article_id}")
        if article.approval_mode == "draft" and not as_draft:
            raise ValueError("draft-only approval cannot publish publicly")
        row = await db.scalar(
            select(Publication)
            .where(Publication.article_id == article_id, Publication.publisher == key, Publication.target == target)
            .with_for_update()
        )
        if row and row.idempotency_key == ikey and row.status == "PUBLISHED":
            return _outcome(row, article)
        resumable = (
            article.status == "PUBLISHING" and row and row.status == "IN_PROGRESS" and row.idempotency_key == ikey
        )
        if resumable and row is not None and row.as_draft != as_draft:
            raise ProblemError(409, "Publication in progress", "the in-progress publication has a different draft mode")
        if article.status not in {"APPROVED", "SCHEDULED", "PUBLISH_FAILED"} and not resumable:
            raise InvalidTransition(Entity.ARTICLE, article.status, ArticleStatus.PUBLISHING)
        rendered = await render_version(db, article=article, version_id=version_id)
        if row is None:
            row = Publication(
                id=uuid7(),
                article_id=article_id,
                version_id=version_id,
                publisher=key,
                target=target,
                status="PENDING",
                idempotency_key=ikey,
                payload_hash=rendered.payload_hash(),
                attempts=0,
                as_draft=as_draft,
            )
            db.add(row)
        require_transition(Entity.PUBLICATION, row.status, PublicationStatus.IN_PROGRESS)
        row.status, row.version_id, row.idempotency_key, row.as_draft = "IN_PROGRESS", version_id, ikey, as_draft
        row.attempts += 1
        row.payload_hash = rendered.payload_hash()
        await set_article_status(db, article_id=article_id, target=ArticleStatus.PUBLISHING)
        if rendered.issues:
            row.status = "FAILED"
            row.last_error = {
                "kind": "validation",
                "message": "; ".join(f"{i.field}: {i.message}" for i in rendered.issues),
            }
            await set_article_status(db, article_id=article_id, target=ArticleStatus.PUBLISH_FAILED)
            await db.commit()
            return _outcome(row, article)
        payload = rendered.to_payload(as_draft=as_draft, external_post_id=row.external_post_id)
        publication_id = row.id
        await db.commit()
    try:
        result = await build_publisher(settings, key).publish(payload, idempotency_key=ikey, as_draft=as_draft)
    except Exception as exc:  # noqa: BLE001 -- persist failure at the publisher boundary
        result = PublicationResult(
            status=PublicationStatus.FAILED,
            external_id=None,
            published_url=None,
            published_at=None,
            message=f"publisher failed: {type(exc).__name__}",
        )
    async with sessionmaker() as db:
        article = await get_article(db, article_id, lock=True)
        row = await db.get(Publication, publication_id, with_for_update=True)
        assert row is not None
        if article.status != "PUBLISHING" or row.idempotency_key != ikey:
            return _outcome(row, article)
        row.external_post_id = result.external_id or row.external_post_id
        if result.status == PublicationStatus.PUBLISHED:
            row.status, row.last_error, row.published_url = "PUBLISHED", None, result.published_url
            row.published_at = result.published_at or datetime.now(UTC)
            await set_article_status(db, article_id=article_id, target=ArticleStatus.PUBLISHED)
            article.published_at, article.published_url, article.published_version_id = (
                row.published_at,
                row.published_url,
                version_id,
            )
            article.scheduled_for = None
        else:
            row.status, row.last_error = "FAILED", {"kind": "publisher", "message": result.message}
            await set_article_status(db, article_id=article_id, target=ArticleStatus.PUBLISH_FAILED)
        await db.commit()
        return _outcome(row, article)


async def select_due_articles(db: AsyncSession, *, now: datetime) -> list[DueArticle]:
    rows = await db.scalars(
        select(Article)
        .where(Article.status == "SCHEDULED", Article.scheduled_for <= now, Article.approved_version_id.is_not(None))
        .order_by(Article.scheduled_for, Article.id)
        .limit(3)
    )
    return [
        DueArticle(
            article_id=a.id,
            version_id=a.approved_version_id,
            scheduled_for=a.scheduled_for,
            scheduled_by=a.scheduled_by,
        )
        for a in rows
        if a.approved_version_id and a.scheduled_for
    ]


async def process_due_article(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    settings: Settings,
    config: EffectiveConfig,
    article_id: uuid.UUID,
    now: datetime,
) -> DueOutcome:
    async with sessionmaker() as db:
        article = await get_article(db, article_id, lock=True)
        if (
            article.status not in {"SCHEDULED", "PUBLISHING"}
            or article.scheduled_for is None
            or article.scheduled_for > now
            or article.approved_version_id is None
        ):
            return DueOutcome(article_id=article_id, action="skipped_state", publication_id=None)
        if network_publishing_active(settings, config):
            user = await db.get(User, article.scheduled_by) if article.scheduled_by else None
            if article.status == "SCHEDULED" and (
                user is None or not user.is_active or Permission.PUBLISH not in permissions_for(Role(user.role))
            ):
                await set_article_status(db, article_id=article_id, target=ArticleStatus.APPROVED)
                article.scheduled_for, article.scheduled_by = None, None
                await db.commit()
                return DueOutcome(
                    article_id=article_id,
                    action="skipped_permission",
                    publication_id=None,
                    detail="scheduler no longer has blog.publish",
                )
            version_id, as_draft = article.approved_version_id, article.approval_mode == "draft"
            scheduled_for = article.scheduled_for
            await audit(
                db,
                actor_user_id=article.scheduled_by,
                action="article.publish",
                entity_type="blog_article",
                entity_id=str(article_id),
                details={"trigger": "schedule", "versionId": version_id},
            )
            await db.commit()
        else:
            if article.status == "PUBLISHING":
                return DueOutcome(
                    article_id=article_id,
                    action="skipped_state",
                    publication_id=None,
                    detail="publishing is disabled; resume the in-progress publication after restoring configuration",
                )
            try:
                bundle = await export_locked(
                    db, article=article, actor_user_id=article.scheduled_by, trigger="schedule"
                )
                await db.commit()
                return DueOutcome(article_id=article_id, action="exported", publication_id=bundle.publication_id)
            except ProblemError as exc:
                await db.rollback()
                article = await get_article(db, article_id, lock=True)
                await set_article_status(db, article_id=article_id, target=ArticleStatus.APPROVED)
                article.scheduled_for, article.scheduled_by = None, None
                await db.commit()
                return DueOutcome(
                    article_id=article_id, action="publish_failed", publication_id=None, detail=str(exc.detail)
                )
    try:
        result = await publish_article(
            sessionmaker,
            settings=settings,
            config=config,
            article_id=article_id,
            version_id=version_id,
            as_draft=as_draft,
            scheduled_for=scheduled_for,
        )
    except ScheduleChanged:
        return DueOutcome(article_id=article_id, action="skipped_state", publication_id=None)
    return DueOutcome(
        article_id=article_id,
        action="published" if result.status == PublicationStatus.PUBLISHED else "publish_failed",
        publication_id=result.publication_id,
        detail=result.error,
    )
