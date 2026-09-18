"""Quality reviews and human decisions."""

import uuid

from pydantic import Field

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.domain.enums import ApprovalMode


class ApproveRequest(ApiModel):
    mode: ApprovalMode
    version_id: uuid.UUID
    override_reason: str | None = Field(default=None, max_length=2000)
