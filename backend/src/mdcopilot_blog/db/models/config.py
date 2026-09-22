"""Versioned settings, versioned brand profile and content pillars."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, Timestamps, UUIDPk


class BlogSetting(UUIDPk, CreatedAt, Base):
    """One row per saved settings version; at most one row is active."""

    __tablename__ = "blog_settings"
    __table_args__ = (Index("uq_blog_settings_active", "is_active", unique=True, postgresql_where=text("is_active")),)

    version: Mapped[int] = mapped_column(unique=True)
    values: Mapped[dict[str, Any]]
    is_active: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_users.id", ondelete="SET NULL"))


class BrandProfile(UUIDPk, CreatedAt, Base):
    """One row per saved brand-profile version; at most one row is active."""

    __tablename__ = "blog_brand_profiles"
    __table_args__ = (
        Index("uq_blog_brand_profiles_active", "is_active", unique=True, postgresql_where=text("is_active")),
    )

    version: Mapped[int] = mapped_column(unique=True)
    profile: Mapped[dict[str, Any]]
    is_active: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("blog_users.id", ondelete="SET NULL"))


class ContentPillar(UUIDPk, Timestamps, Base):
    """A thematic pillar (spec section 9). ``weekdays`` uses 0 = Monday ... 6 = Sunday."""

    __tablename__ = "blog_content_pillars"

    key: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    weekdays: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(default=0, server_default=text("0"))
