import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.auth.users import create_user
from mdcopilot_blog.db.models import AuditLog
from mdcopilot_blog.domain.enums import Role
from mdcopilot_blog.services.audit import audit


async def test_audit_writes_one_row(db_session: AsyncSession) -> None:
    actor = await create_user(
        db_session, email="auditor@example.test", display_name="A", role=Role.ADMIN, password="correct-horse-battery"
    )
    target = uuid.uuid4()
    await audit(
        db_session,
        actor_user_id=actor.id,
        action="user.update",
        entity_type="user",
        entity_id=str(target),
        reason="role change requested",
        details={"target": target, "at": datetime(2026, 9, 17, tzinfo=UTC), "cost": Decimal("1.50"), "n": 2},
    )
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "user.update"))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == actor.id
    assert (row.entity_type, row.entity_id, row.reason) == ("user", str(target), "role change requested")
    assert row.details == {"target": str(target), "at": "2026-09-17 00:00:00+00:00", "cost": "1.50", "n": 2}
    assert row.created_at is not None


async def test_audit_defaults(db_session: AsyncSession) -> None:
    await audit(db_session, actor_user_id=None, action="system.check", entity_type="system")
    row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "system.check"))
    assert row is not None
    assert (row.actor_user_id, row.entity_id, row.reason, row.details) == (None, None, None, {})
