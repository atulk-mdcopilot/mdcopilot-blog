"""Research run API contracts, excluding private source snapshots."""

import uuid
from datetime import datetime
from typing import Any, Literal

from mdcopilot_blog.api.schemas import ApiModel
from mdcopilot_blog.api.schemas_common import SourceRefOut
from mdcopilot_blog.api.schemas_sources import LedgerSourceOut
from mdcopilot_blog.domain.contracts import ClaimType, PillarKey
from mdcopilot_blog.domain.enums import ResearchRunKind, ResearchRunStatus


class ResearchQueryOut(ApiModel):
    text: str
    theme_key: str | None
    status: Literal["ok", "failed"]
    search_actions: int = 0
    source_count: int = 0
    error: str | None


class ResearchRunOut(ApiModel):
    id: uuid.UUID
    run_id: uuid.UUID
    article_id: uuid.UUID | None
    kind: ResearchRunKind
    status: ResearchRunStatus
    pillar: PillarKey | None
    window_days: int
    queries: list[ResearchQueryOut]
    themes_covered: list[str]
    phase_latency_ms: dict[str, int]
    counts: dict[str, int]
    source_count: int
    finding_count: int
    started_at: datetime
    finished_at: datetime | None
    error: dict[str, Any] | None
    trace_id: str
    created_at: datetime


class FindingOut(ApiModel):
    id: uuid.UUID
    position: int
    claim: str
    evidence: str
    confidence: float
    category: str
    claim_type: ClaimType
    importance: Literal["high", "normal"]
    is_preprint: bool
    downgraded_from: str | None
    sources: list[SourceRefOut]


class ResearchRunDetail(ResearchRunOut):
    findings: list[FindingOut]
    sources: list[LedgerSourceOut]
