"""Article status writes: the state machine is enforced at the write."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import Article
from mdcopilot_blog.domain.enums import ArticleStatus
from mdcopilot_blog.domain.state_machine import Entity, require_transition


async def set_article_status(db: AsyncSession, *, article_id: uuid.UUID, target: ArticleStatus) -> Article:
    """Row-lock, enforce the transition, write the new status; flush only (caller commits)."""
    article = (await db.execute(select(Article).where(Article.id == article_id).with_for_update())).scalar_one_or_none()
    if article is None:
        raise LookupError(f"article {article_id} not found")
    require_transition(Entity.ARTICLE, article.status, target.value)
    article.status = target.value
    await db.flush()
    return article
