"""API models shared by several routers."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.domain.enums import AccessMode, ApprovalMode, ArticleStatus


class ActionAccepted(ApiModel):
    """A human action was recorded and a workflow enqueued."""

    workflow_id: str
    workflow_name: str
    queue: str
    run_id: uuid.UUID
    article_id: uuid.UUID | None
    candidate_id: uuid.UUID | None


class ArticleStateOut(ApiModel):
    """The article row's state after a human action."""

    id: uuid.UUID
    status: ArticleStatus
    current_version_id: uuid.UUID | None
    approved_version_id: uuid.UUID | None
    published_version_id: uuid.UUID | None
    approval_mode: ApprovalMode | None
    scheduled_for: datetime | None
    published_at: datetime | None
    published_url: str | None
    updated_at: datetime


class SourceRefOut(ApiModel):
    """A ledger source as shown with an article version."""

    id: uuid.UUID
    marker: str | None
    title: str
    url: str
    publisher: str
    domain: str
    tier: int
    published_at: datetime | None
    access_mode: AccessMode


class ReasonRequest(ApiModel):
    """The required reason for a reject (and an override approve)."""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
