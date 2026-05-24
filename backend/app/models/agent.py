"""
Agent — a conversational AI persona combining a digital avatar, voice model,
knowledge base, and LLM configuration.

Agents are the top-level interactive entities that end users talk to via
the web embed, kiosk, or API.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.avatar import Avatar
    from app.models.voice_model import VoiceModel
    from app.models.knowledge_base import KnowledgeBase
    from app.models.conversation import Conversation


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentRole(str, enum.Enum):
    CUSTOMER_SUPPORT = "customer_support"
    SALES = "sales"
    HR = "hr"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    ENTERTAINMENT = "entertainment"
    GENERAL = "general"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Agent(UUIDBase):
    """
    AI conversational agent with a digital human persona.

    The ``personality_traits`` JSONB column stores free-form traits used in
    the system prompt scaffolding, e.g.::

        {"tone": "professional", "empathy_level": "high", "verbosity": "concise"}

    The ``capabilities`` text-array enumerates enabled feature flags, e.g.
    ``["rag", "web_search", "calendar", "crm"]``.
    """

    __tablename__ = "agents"

    # ------------------------------------------------------------------ identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name shown to end users",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short description of the agent's role and purpose",
    )
    role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, name="agent_role_enum"),
        nullable=False,
        default=AgentRole.GENERAL,
        server_default=text("'general'"),
        comment="Primary functional role of the agent",
    )

    # ------------------------------------------------------------------ ownership
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who created this agent",
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning organisation",
    )

    # ------------------------------------------------------------------ assets
    avatar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("avatars.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Digital avatar used for video responses",
    )
    voice_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("voice_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Voice model used for audio synthesis",
    )
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Primary RAG knowledge source attached to this agent",
    )

    # ------------------------------------------------------------------ LLM configuration
    llm_provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="openai",
        server_default=text("'openai'"),
        comment="LLM provider identifier, e.g. openai, anthropic, google, local",
    )
    llm_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="gpt-4o",
        server_default=text("'gpt-4o'"),
        comment="Model name / version string",
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full system prompt injected at the start of every conversation",
    )

    # ------------------------------------------------------------------ personality
    personality_traits: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Free-form key-value pairs used to modulate tone and behaviour",
    )
    capabilities: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
        comment="Enabled feature flags, e.g. ['rag', 'web_search', 'calendar']",
    )

    # ------------------------------------------------------------------ visibility / status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Whether this agent accepts new conversations",
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Accessible to unauthenticated users via public embed link",
    )

    # ------------------------------------------------------------------ analytics
    conversation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Lifetime number of conversations handled",
    )
    avg_rating: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Rolling average of user satisfaction scores [1.0, 5.0]",
    )

    # ------------------------------------------------------------------ integrations
    webhook_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="URL to notify on conversation events (POST JSON payload)",
    )

    # ------------------------------------------------------------------ relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="agents",
        lazy="selectin",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="agents",
        lazy="selectin",
    )
    avatar: Mapped["Avatar | None"] = relationship(
        "Avatar",
        back_populates="agents",
        lazy="selectin",
    )
    voice_model: Mapped["VoiceModel | None"] = relationship(
        "VoiceModel",
        back_populates="agents",
        lazy="selectin",
    )
    knowledge_base: Mapped["KnowledgeBase | None"] = relationship(
        "KnowledgeBase",
        back_populates="agents",
        lazy="selectin",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="agent",
        lazy="noload",
        cascade="all, delete-orphan",
    )
