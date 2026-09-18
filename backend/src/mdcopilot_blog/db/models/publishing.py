"""Publications: one row per (article, publisher, target) export or publish."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, Timestamps, UUIDPk


class Publication(UUIDPk, Timestamps, Base):
    """One export or publish attempt; a re-publish of a newer version updates this row."""

    __tablename__ = "blog_publications"
    __table_args__ = (
        Index("uq_blog_publications_article_id_publisher_target", "article_id", "publisher", "target", unique=True),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_articles.id", ondelete="RESTRICT"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("blog_article_versions.id", ondelete="RESTRICT"))
    publisher: Mapped[str] = mapped_column(String(32))
    target: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    external_post_id: Mapped[str | None] = mapped_column(String(64))
    published_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    export_bundle: Mapped[dict[str, Any] | None]
    as_draft: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    last_error: Mapped[dict[str, Any] | None]
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
