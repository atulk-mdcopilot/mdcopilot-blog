"""Read-only public post sync with staged paging and resumable embeddings."""

import dataclasses
import hashlib
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from mdcopilot_blog.db.models import ExternalPost
from mdcopilot_blog.domain.headlines import classify_headline
from mdcopilot_blog.domain.novelty import external_post_embedding_text
from mdcopilot_blog.services.step_context import StepContext
from mdcopilot_blog.settings import Settings

MAX_PAGES = 200
EMBED_BATCH_SIZE = 50


class SyncReport(BaseModel):
    enabled: bool
    fetched: int
    inserted: int
    updated: int
    embedded: int


class ExternalPostsSyncError(RuntimeError):
    pass


class PublicBlogPost(BaseModel):
    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True)
    id: str
    slug: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1)
    excerpt: str | None = None
    published_at: datetime | None = None
    status: str | None = None


def build_public_api_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.fetch_read_timeout_seconds, connect=settings.fetch_connect_timeout_seconds),
        headers={"Accept": "application/json", "User-Agent": f"mdcopilot-blog/{settings.app_version}"},
        follow_redirects=False,
    )


async def sync_mdcopilot_posts(sc: StepContext, *, now: datetime) -> SyncReport:
    if not (sc.settings.mdcopilot_public_api_url or "").strip():
        return SyncReport(enabled=False, fetched=0, inserted=0, updated=0, embedded=0)
    async with build_public_api_client(sc.settings) as client:
        return await sync_posts_with_client(sc, now=now, client=client)


async def sync_posts_with_client(sc: StepContext, *, now: datetime, client: httpx.AsyncClient) -> SyncReport:
    base = (sc.settings.mdcopilot_public_api_url or "").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ExternalPostsSyncError("BLOG_MDCOPILOT_PUBLIC_API_URL must be an http(s) URL without credentials")
    posts: dict[str, PublicBlogPost] = {}
    for page in range(MAX_PAGES):
        skip = page * sc.settings.mdcopilot_sync_page_size
        response = await client.get(
            base + "/blogs", params={"skip": skip, "limit": sc.settings.mdcopilot_sync_page_size}
        )
        if response.status_code != 200:
            raise ExternalPostsSyncError(f"GET /blogs skip={skip} returned {response.status_code}")
        body = response.json()
        if not isinstance(body, list):
            raise ExternalPostsSyncError(f"GET /blogs skip={skip} did not return a JSON array")
        for item in body:
            post = PublicBlogPost.model_validate(item)
            if post.status in {None, "published"}:
                posts.setdefault(post.slug, post)
        if len(body) < sc.settings.mdcopilot_sync_page_size:
            break
    else:
        raise ExternalPostsSyncError("public post pagination exceeded 200 pages")
    report = SyncReport(enabled=True, fetched=len(posts), inserted=0, updated=0, embedded=0)
    async with sc.sessionmaker() as db:
        for post in posts.values():
            values = {
                "external_id": post.id[:64],
                "title": post.title[:300],
                "excerpt": post.excerpt or "",
                "url": f"{sc.config.site_url.rstrip('/')}/blog/{post.slug}",
                "published_at": post.published_at.replace(tzinfo=UTC)
                if post.published_at and post.published_at.tzinfo is None
                else post.published_at,
                "headline_pattern": classify_headline(post.title).value,
                "content_hash": hashlib.sha256(f"{post.title}\n{post.excerpt or ''}".encode()).hexdigest(),
            }
            row = await db.scalar(
                select(ExternalPost)
                .where(ExternalPost.origin == parsed.hostname, ExternalPost.slug == post.slug)
                .with_for_update()
            )
            if row is None:
                row = ExternalPost(origin=parsed.hostname, slug=post.slug, **values, last_synced_at=now)
                db.add(row)
                report.inserted += 1
            else:
                if any(getattr(row, key) != value for key, value in values.items()):
                    report.updated += 1
                if row.content_hash != values["content_hash"]:
                    row.embedding = None
                for key, value in values.items():
                    setattr(row, key, value)
                row.last_synced_at = now
        await db.commit()
    while True:
        async with sc.sessionmaker() as db:
            rows = (
                await db.scalars(
                    select(ExternalPost)
                    .where(ExternalPost.origin == parsed.hostname, ExternalPost.embedding.is_(None))
                    .order_by(ExternalPost.slug)
                    .limit(EMBED_BATCH_SIZE)
                )
            ).all()
            if not rows:
                break
            vectors = await sc.gateway.embed(
                [external_post_embedding_text(title=r.title, excerpt=r.excerpt) for r in rows],
                ctx=dataclasses.replace(sc.call, run_id=None, attempt_id=None),
            )
            if len(vectors) != len(rows) or any(len(v) != 1536 for v in vectors):
                raise ExternalPostsSyncError("invalid embedding response")
            for row, vector in zip(rows, vectors, strict=True):
                row.embedding = vector
            await db.commit()
            report.embedded += len(rows)
    return report
