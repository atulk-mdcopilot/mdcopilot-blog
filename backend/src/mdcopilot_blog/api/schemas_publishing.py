"""Publishing wire contracts."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, Field, field_validator

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.domain.contracts import BlogSource, SEOMetadata, SocialCopy
from mdcopilot_blog.domain.enums import ArticleStatus, PublicationStatus, PublisherKey
from mdcopilot_blog.publishing.renderer import http_url


class IssueOut(ApiModel):
    field: str
    message: str


class PreviewOut(ApiModel):
    version_id: uuid.UUID
    html: str
    issues: list[IssueOut]


class ExportBundleOut(ApiModel):
    publication_id: uuid.UUID
    article_id: uuid.UUID
    version_id: uuid.UUID
    title: str = Field(max_length=200)
    slug: str = Field(max_length=200)
    excerpt: str = Field(max_length=500)
    html: str
    text: str
    seo: SEOMetadata
    social: SocialCopy | None
    tags: list[str]
    category: str
    references: list[BlogSource]
    disclosure: str
    status: ArticleStatus


class ConfirmPublishedRequest(ApiModel):
    url: str = Field(max_length=2000)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        if not http_url(value):
            raise ValueError("url must be an absolute http or https URL")
        return value.strip()


class PublishRequest(ApiModel):
    as_draft: bool | None = None


class ScheduleRequest(ApiModel):
    at: AwareDatetime


class PublicationOut(ApiModel):
    id: uuid.UUID
    version_id: uuid.UUID
    publisher: PublisherKey
    target: str
    status: PublicationStatus
    external_post_id: str | None
    published_url: str | None
    published_at: datetime | None
    as_draft: bool
    attempts: int
    last_error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
