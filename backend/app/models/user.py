"""
User model — authentication, authorisation, profile, and resource ownership.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.avatar import Avatar
    from app.models.voice_model import VoiceModel
    from app.models.video import Video
    from app.models.agent import Agent
    from app.models.knowledge_base import KnowledgeBase
    from app.models.conversation import Conversation


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    CREATOR = "creator"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class User(UUIDBase):
    """
    Platform user.  Belongs to exactly one Organization (unless super_admin).
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
    )

    # ------------------------------------------------------------------ identity
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Primary login email; must be unique",
    )
    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="URL-safe unique handle",
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Display name shown in the UI",
    )

    # ------------------------------------------------------------------ auth
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="bcrypt hash; NULL for OAuth-only accounts",
    )
    api_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Hashed API key for programmatic access",
    )
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g. google, github, microsoft",
    )
    oauth_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Provider's user identifier",
    )

    # ------------------------------------------------------------------ role / permissions
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.VIEWER,
        server_default=text("'viewer'"),
        comment="RBAC role within the organisation",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Account enabled flag",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Email verified flag",
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Platform-level super admin (bypasses org checks)",
    )

    # ------------------------------------------------------------------ organisation
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Owning organisation; NULL only for platform super admins",
    )

    # ------------------------------------------------------------------ profile
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Profile picture URL",
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="UTC",
        server_default=text("'UTC'"),
        comment="IANA timezone string, e.g. America/New_York",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
        comment="ISO 639-1 language code",
    )
    theme: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="system",
        server_default=text("'system'"),
        comment="UI theme preference: light | dark | system",
    )

    # ------------------------------------------------------------------ activity
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp of most recent successful authentication",
    )
    login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Total number of successful logins",
    )

    # ------------------------------------------------------------------ storage
    storage_used_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Bytes consumed by this user's assets",
    )
    storage_limit_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=10 * 1024 ** 3,       # 10 GiB
        server_default=text("10737418240"),
        comment="Maximum allowed storage for this user",
    )

    # ------------------------------------------------------------------ relationships
    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        back_populates="users",
        lazy="selectin",
    )
    avatars: Mapped[list["Avatar"]] = relationship(
        "Avatar",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    voice_models: Mapped[list["VoiceModel"]] = relationship(
        "VoiceModel",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    videos: Mapped[list["Video"]] = relationship(
        "Video",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        lazy="noload",
    )
