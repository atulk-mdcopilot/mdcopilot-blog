"""Append-only audit trail (audit_log)."""

import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import AuditLog


def _json_safe(details: Mapping[str, object] | None) -> dict[str, Any]:
    """Round-trip through json so UUIDs, datetimes and Decimals are stored as strings."""
    if not details:
        return {}
    safe: dict[str, Any] = json.loads(json.dumps(dict(details), default=str))
    return safe


async def audit(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    reason: str | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    """Add one audit row and flush. The caller's transaction decides whether it is kept."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            details=_json_safe(details),
        )
    )
    await db.flush()
