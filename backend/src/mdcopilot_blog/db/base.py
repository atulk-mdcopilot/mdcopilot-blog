"""Declarative base, naming convention and shared column mixins.

Every table lives in the shared mdcopilot-backend database, schema ``public``, with a ``blog_`` table-name
prefix (Alembic-managed, version table ``blog_alembic_versions``). DBOS owns schema ``blog_dbos``.
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mdcopilot_blog.ids import uuid7

# "ix" uses table_name + column names (not column_0_label, which would prefix a schema if one were set).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
    }


class UUIDPk:
    """UUIDv7 primary key, generated in Python so ids sort by creation time."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7, sort_order=-100)


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), sort_order=100)


class Timestamps(CreatedAt):
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), sort_order=101)
