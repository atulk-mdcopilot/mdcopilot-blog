"""Users, sessions, login attempts and the audit log."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "blog_users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None]


class UserSession(UUIDPk, CreatedAt, Base):
    """A login session. Only the sha256 of the opaque token is stored."""

    __tablename__ = "blog_user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))


class LoginAttempt(UUIDPk, CreatedAt, Base):
    __tablename__ = "blog_login_attempts"
    __table_args__ = (Index("ix_blog_login_attempts_created_at", "created_at"),)

    email: Mapped[str] = mapped_column(String(320), index=True)
    ip: Mapped[str | None] = mapped_column(String(64), index=True)
    succeeded: Mapped[bool]


class AuditLog(UUIDPk, CreatedAt, Base):
    __tablename__ = "blog_audit_log"
    __table_args__ = (Index("ix_blog_audit_log_created_at", "created_at"),)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
