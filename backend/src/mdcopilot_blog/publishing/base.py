"""Publisher interface (ARCHITECTURE §14). Phase 1 ships only NullPublisher."""

import uuid
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from mdcopilot_blog.domain.enums import PublicationStatus


class PublishPayload(BaseModel):
    article_id: uuid.UUID
    version_id: uuid.UUID
    title: str
    slug: str
    html: str
    excerpt: str
    status: Literal["draft", "published"]
    seo: dict[str, object] = Field(default_factory=dict)


class PublisherCapabilities(BaseModel):
    network: bool
    supports_update: bool
    supports_draft: bool
    seo_fields: bool


class RemotePost(BaseModel):
    external_id: str
    slug: str
    status: str
    url: str | None


class PublicationResult(BaseModel):
    status: PublicationStatus
    external_id: str | None
    published_url: str | None
    published_at: datetime | None
    message: str | None = None


class Issue(BaseModel):
    field: str
    message: str


class BlogPublisher(Protocol):
    key: str

    def capabilities(self) -> PublisherCapabilities: ...

    async def validate(self, payload: PublishPayload) -> list[Issue]: ...

    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult: ...

    async def find_existing(self, payload: PublishPayload) -> RemotePost | None: ...
