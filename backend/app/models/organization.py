"""
Organization model — multi-tenant root entity.

Every piece of user data belongs to exactly one organization.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.avatar import Avatar
    from app.models.voice_model import VoiceModel
    from app.models.video import Video
    from app.models.agent import Agent
    from app.models.knowledge_base import KnowledgeBase
    from app.models.analytics import AnalyticsEvent
    from app.models.subscription import Subscription


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrganizationPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Organization(UUIDBase):
    """
    Top-level tenant.  All resource ownership chains back to this model.
    """

    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organizations_slug"),
        UniqueConstraint("domain", name="uq_organizations_domain"),
    )

    # ------------------------------------------------------------------ identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable display name",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="URL-safe unique identifier, e.g. 'acme-corp'",
    )
    domain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Verified domain for SSO / email matching",
    )

    # ------------------------------------------------------------------ plan / billing
    plan: Mapped[OrganizationPlan] = mapped_column(
        Enum(OrganizationPlan, name="organization_plan_enum"),
        nullable=False,
        default=OrganizationPlan.FREE,
        server_default=text("'free'"),
        comment="Subscription tier",
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="FK to subscriptions (denormalised for quick access)",
    )

    # ------------------------------------------------------------------ quotas
    max_users: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default=text("5"),
        comment="Maximum number of active members",
    )
    max_storage_gb: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        server_default=text("10"),
        comment="Storage quota in gigabytes",
    )
    max_videos_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        server_default=text("10"),
        comment="Monthly video generation cap",
    )

    # ------------------------------------------------------------------ branding
    logo_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Object-storage URL for organisation logo",
    )
    primary_color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        comment="Hex colour code, e.g. #3B82F6",
    )

    # ------------------------------------------------------------------ settings / metadata
    settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Arbitrary key-value configuration (feature flags, integrations, …)",
    )

    # ------------------------------------------------------------------ status / lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="False means the org is suspended / archived",
    )
    trial_ends_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC expiry of trial period; NULL if not on trial",
    )

    # ------------------------------------------------------------------ relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    avatars: Mapped[list["Avatar"]] = relationship(
        "Avatar",
        back_populates="organization",
        lazy="selectin",
    )
    voice_models: Mapped[list["VoiceModel"]] = relationship(
        "VoiceModel",
        back_populates="organization",
        lazy="selectin",
    )
    videos: Mapped[list["Video"]] = relationship(
        "Video",
        back_populates="organization",
        lazy="selectin",
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="organization",
        lazy="selectin",
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="organization",
        lazy="selectin",
    )
    analytics_events: Mapped[list["AnalyticsEvent"]] = relationship(
        "AnalyticsEvent",
        back_populates="organization",
        lazy="noload",
    )
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription",
        back_populates="organization",
        uselist=False,
        lazy="selectin",
        foreign_keys="[Subscription.organization_id]",
    )
