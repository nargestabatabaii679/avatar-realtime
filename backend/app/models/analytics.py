"""
AnalyticsEvent — immutable event record for platform observability.

Events are written by workers, API handlers, and background tasks.
The ``date_bucket`` column (truncated to the day) allows efficient
time-series aggregation queries without a full table scan.

For very high-volume deployments this table can be partitioned by
``date_bucket`` using PostgreSQL declarative partitioning.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
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


class AnalyticsEvent(UUIDBase):
    """
    A single analytics event.

    ``event_type`` is a dot-separated namespaced string such as::

        "video.generated"
        "agent.conversation_started"
        "user.login"
        "storage.quota_exceeded"

    ``entity_type`` + ``entity_id`` form a polymorphic reference to whichever
    domain object generated the event (video, agent, avatar, …).

    ``metrics`` stores numeric KPIs relevant to the specific event, e.g.::

        {"duration_seconds": 45.2, "tokens_used": 512, "fps": 25}

    ``gpu_seconds_used`` and ``storage_bytes_delta`` are first-class columns so
    they can be aggregated cheaply for billing and quota enforcement.
    """

    __tablename__ = "analytics_events"

    # ------------------------------------------------------------------ foreign keys
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant that generated this event",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who triggered the event; NULL for system-generated events",
    )

    # ------------------------------------------------------------------ event classification
    event_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Dot-namespaced event type, e.g. 'video.generated'",
    )
    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Domain object type, e.g. 'video', 'agent', 'avatar'",
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID of the specific domain object",
    )

    # ------------------------------------------------------------------ time
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Exact UTC timestamp of the event",
    )
    date_bucket: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Day-truncated date for partition-friendly aggregations",
    )

    # ------------------------------------------------------------------ metrics
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Event-specific numeric and string KPIs",
    )
    gpu_seconds_used: Mapped[float | None] = mapped_column(
        Integer,
        nullable=True,
        comment="GPU compute time consumed by this event (seconds × GPU count)",
    )
    storage_bytes_delta: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Change in storage consumption (positive = added, negative = freed)",
    )

    # ------------------------------------------------------------------ relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="analytics_events",
        lazy="selectin",
    )
    user: Mapped["User | None"] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[user_id],
    )
