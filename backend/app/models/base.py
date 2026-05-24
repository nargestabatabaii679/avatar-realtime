"""
Base SQLAlchemy model with enterprise-grade shared fields and mixin classes.

Provides:
  - UUIDBase: UUID primary key, audit timestamps, soft-delete, to_dict()
  - TimestampMixin: created_at / updated_at only (for join tables etc.)
  - SoftDeleteMixin: deleted_at / is_deleted columns
  - AuditMixin: combined timestamps + soft delete
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""

    # Allow all models to use the 'postgresql' dialect JSON / ARRAY types
    # without importing them individually.


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------

class TimestampMixin:
    """Adds created_at and updated_at to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("NOW()"),
        comment="UTC timestamp when this row was first inserted",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=text("NOW()"),
        comment="UTC timestamp of the last update",
    )


class SoftDeleteMixin:
    """Adds soft-delete support.  Rows with is_deleted=True are treated as gone."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        index=True,
        comment="Logical deletion flag",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="UTC timestamp when soft-deleted (NULL if active)",
    )

    def soft_delete(self) -> None:
        """Mark this row as deleted without removing from the database."""
        self.is_deleted = True
        self.deleted_at = _utcnow()

    def restore(self) -> None:
        """Undo a soft-delete."""
        self.is_deleted = False
        self.deleted_at = None


class AuditMixin(TimestampMixin, SoftDeleteMixin):
    """Combines timestamp + soft-delete mixins."""


# ---------------------------------------------------------------------------
# UUID primary-key base model
# ---------------------------------------------------------------------------

class UUIDBase(Base, AuditMixin):
    """
    Abstract base for all domain models.

    Every concrete model inherits:
      - id              (UUID v4, primary key)
      - created_at      (timestamp with TZ)
      - updated_at      (timestamp with TZ, auto-updated)
      - is_deleted      (bool, default False)
      - deleted_at      (timestamp with TZ, nullable)
      - to_dict()       (serialisation helper)
      - soft_delete()   (inherited from SoftDeleteMixin)
      - restore()       (inherited from SoftDeleteMixin)
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="Globally unique identifier (UUID v4)",
    )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(
        self,
        *,
        exclude: set[str] | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """
        Return a plain-Python dict representation of this row.

        Args:
            exclude: Column names to skip.
            include_deleted: If False (default) and the row is soft-deleted,
                             the dict still contains the row data (caller decides
                             what to do with it).  Pass True to surface
                             deleted_at / is_deleted.
        """
        exclude = exclude or set()
        result: dict[str, Any] = {}

        for column in self.__table__.columns:  # type: ignore[attr-defined]
            name = column.name
            if name in exclude:
                continue
            value = getattr(self, name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[name] = value

        return result

    def __repr__(self) -> str:
        cls = type(self).__name__
        pk = getattr(self, "id", "?")
        return f"<{cls} id={pk}>"
