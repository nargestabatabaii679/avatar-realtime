"""
Subscription — Stripe billing record linked to an Organization.

One subscription per organisation at any given time (enforced by the
application layer).  Historical subscriptions (cancelled / replaced) are
retained for audit and revenue analytics.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.organization import Organization


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Subscription(UUIDBase):
    """
    Stripe-backed subscription record.

    ``stripe_subscription_id`` is the Stripe ``sub_…`` identifier; events from
    the Stripe webhook should locate subscriptions by this field.

    ``metadata`` stores Stripe webhook event snapshots and any provider-specific
    fields needed for idempotent event processing.
    """

    __tablename__ = "subscriptions"

    # ------------------------------------------------------------------ foreign key
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organisation this subscription belongs to",
    )

    # ------------------------------------------------------------------ plan / status
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, name="subscription_plan_enum"),
        nullable=False,
        comment="Subscription tier",
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum"),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
        server_default=text("'active'"),
        index=True,
        comment="Current Stripe subscription lifecycle state",
    )

    # ------------------------------------------------------------------ Stripe identifiers
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Stripe subscription ID, e.g. sub_1OaBcDEFghIJ",
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Stripe customer ID, e.g. cus_1OaBcDEFghIJ",
    )
    stripe_price_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Stripe price / plan ID, e.g. price_1OaBcDEFghIJ",
    )

    # ------------------------------------------------------------------ billing period
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC start of the current billing period",
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC end of the current billing period",
    )

    # ------------------------------------------------------------------ cancellation
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="True when the subscription will cancel at the end of the current period",
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the subscription was cancelled",
    )
    trial_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC start of the trial period",
    )
    trial_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC end of the trial period",
    )

    # ------------------------------------------------------------------ metadata
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Stripe event snapshots, coupon codes, proration data, "
            "idempotency keys, custom invoice fields, …"
        ),
    )

    # ------------------------------------------------------------------ relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="subscription",
        foreign_keys=[organization_id],
        lazy="selectin",
    )
