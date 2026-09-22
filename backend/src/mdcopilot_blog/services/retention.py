"""Bounded snapshot retention; active article research remains available."""

from datetime import datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.settings import Settings

SNAPSHOT_PURGE_BATCH_SIZE = 500
SNAPSHOT_PURGE_MAX_BATCHES = 20


class SnapshotRetentionReport(BaseModel):
    cutoff: datetime
    purged: int
    batches: int
    more_remaining: bool


async def purge_source_snapshots(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    settings: Settings,
    now: datetime,
    batch_size: int = SNAPSHOT_PURGE_BATCH_SIZE,
    max_batches: int = SNAPSHOT_PURGE_MAX_BATCHES,
) -> SnapshotRetentionReport:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if not 1 <= batch_size <= 5000 or not 1 <= max_batches <= 100:
        raise ValueError("invalid retention batch limits")
    cutoff = now - timedelta(days=settings.source_snapshot_retention_days)
    purged = batches = 0
    more = False
    for _ in range(max_batches):
        async with sessionmaker() as db:
            result = await db.execute(
                text("""
                WITH eligible AS (
                    SELECT s.id FROM blog_sources s
                    WHERE s.text_snapshot IS NOT NULL AND s.retrieved_at < :cutoff
                    AND NOT EXISTS (
                        SELECT 1 FROM blog_research_packets p JOIN blog_articles a ON a.id = p.article_id
                        WHERE a.status NOT IN ('PUBLISHED', 'REJECTED', 'SUPERSEDED', 'FAILED')
                        AND p.source_ids @> jsonb_build_array(s.id::text)
                    )
                    ORDER BY s.retrieved_at, s.id LIMIT :batch_size FOR UPDATE OF s SKIP LOCKED
                )
                UPDATE blog_sources s SET text_snapshot = NULL, snapshot_purged_at = :now, updated_at = :now
                FROM eligible e WHERE s.id = e.id RETURNING s.id
            """),
                {"cutoff": cutoff, "now": now, "batch_size": batch_size},
            )
            count = len(result.all())
            await db.commit()
        batches += 1
        purged += count
        more = count == batch_size
        if not more:
            break
    return SnapshotRetentionReport(cutoff=cutoff, purged=purged, batches=batches, more_remaining=more)
