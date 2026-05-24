"""
AuditLog — immutable audit trail for every state-changing operation.

Records are written synchronously within the request so that each entry
reflects the exact state at the time of the action.  Rows are never
updated or deleted — they are the source of truth for compliance.

For GDPR / data-retention purposes a background job can anonymise the
``request_data`` column by replacing PII with hashed tokens after a
configurable retention window.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class AuditLog(UUIDBase):
    """
    Immutable audit record.

    ``action`` is a verb describing the operation, e.g.::

        "create", "update", "delete", "login", "logout",
        "password_change", "api_key_rotate", "export"

    ``resource_type`` + ``resource_id`` identify the affected entity.

    ``request_data`` stores a sanitised (no secrets) snapshot of the request
    payload.  ``response_code`` is the HTTP status returned.
    """

    __tablename__ = "audit_logs"

    # ------------------------------------------------------------------ foreign keys
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Organisation context; NULL for platform-level actions",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Actor; NULL for anonymous or system-originated actions",
    )

    # ------------------------------------------------------------------ action
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Verb describing the operation, e.g. 'create', 'delete'",
    )
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Affected domain object type, e.g. 'video', 'user'",
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID of the specific resource affected",
    )

    # ------------------------------------------------------------------ request context
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IPv4 or IPv6 address of the client (max 45 chars for IPv6)",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="HTTP User-Agent header from the request",
    )

    # ------------------------------------------------------------------ payload / response
    request_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Sanitised request body / query parameters (secrets redacted)",
    )
    response_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP response status code",
    )

    # ------------------------------------------------------------------ timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Exact UTC timestamp of the audited action",
    )

    # ------------------------------------------------------------------ relationships
    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        lazy="selectin",
        foreign_keys=[organization_id],
    )
    user: Mapped["User | None"] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[user_id],
    )
