"""Disable persistently failing feeds without performing network requests."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import SourceFeed
from mdcopilot_blog.services.config import load_effective_config
from mdcopilot_blog.settings import Settings


class FeedHealthReport(BaseModel):
    feeds_checked: int
    feeds_disabled: int
    failing_feed_ids: list[uuid.UUID]


async def roll_up_feed_health(
    sessionmaker: async_sessionmaker[AsyncSession], *, settings: Settings, now: datetime
) -> FeedHealthReport:
    async with sessionmaker() as db:
        config = await load_effective_config(db, settings)
        rows = (
            await db.scalars(
                select(SourceFeed)
                .where(SourceFeed.is_enabled.is_(True))
                .order_by(SourceFeed.group_name, SourceFeed.name)
                .with_for_update()
            )
        ).all()
        failed = [row.id for row in rows if row.consecutive_failures > 0]
        disabled = 0
        for row in rows:
            if row.consecutive_failures >= config.research.feed_disable_after_failures:
                row.is_enabled = False
                row.disabled_reason = (
                    f"auto-disabled {now:%Y-%m-%d} after {row.consecutive_failures} consecutive failures"
                )
                disabled += 1
        await db.commit()
        return FeedHealthReport(feeds_checked=len(rows), feeds_disabled=disabled, failing_feed_ids=failed)
