"""Price overrides for LLM, search and embedding calls."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mdcopilot_blog.db.base import Base, CreatedAt, UUIDPk


class PriceOverride(UUIDPk, CreatedAt, Base):
    """Insert-only price override; the row with the greatest ``effective_from <= call time`` wins."""

    __tablename__ = "blog_price_overrides"
    __table_args__ = (
        Index("uq_blog_price_overrides_provider_sku_effective_from", "provider", "sku", "effective_from", unique=True),
        CheckConstraint(
            "input_per_mtok IS NOT NULL OR output_per_mtok IS NOT NULL OR per_1k_calls IS NOT NULL",
            name="has_price",
        ),
    )

    provider: Mapped[str] = mapped_column(String(32))
    sku: Mapped[str] = mapped_column(String(128))
    input_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    output_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    cache_read_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    per_1k_calls: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    effective_from: Mapped[datetime]
    price_version: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
