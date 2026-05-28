"""
Conversation — a session of messages between a user and an Agent.

The full message history is stored as a JSONB array for flexibility and
to avoid the overhead of a dedicated messages table for most read patterns.
For high-volume deployments this column can be offloaded to a time-series
store and replaced with a reference.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.user import User


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConversationChannel(str, enum.Enum):
    WEB = "web"
    API = "api"
    EMBED = "embed"
    KIOSK = "kiosk"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Conversation(UUIDBase):
    """
    A single conversation session.

    Each element of ``messages`` follows the structure::

        {
            "role": "user" | "assistant" | "system",
            "content": "...",
            "timestamp": "2025-01-01T00:00:00Z",
            "tokens_used": 42,
            "latency_ms": 350,
            "video_url": null
        }

    ``session_id`` is a client-generated or server-generated opaque token that
    groups multiple API requests into the same logical conversation, useful for
    stateless REST integrations.
    """

    __tablename__ = "conversations"

    # ------------------------------------------------------------------ foreign keys
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Agent this conversation belongs to",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Platform user; NULL for anonymous sessions",
    )

    # ------------------------------------------------------------------ session identity
    session_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Client or server generated session token for correlation",
    )

    # ------------------------------------------------------------------ channel
    channel: Mapped[ConversationChannel] = mapped_column(
        Enum(ConversationChannel, name="conversation_channel_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ConversationChannel.WEB,
        server_default=text("'web'"),
        comment="Interface through which the conversation was initiated",
    )

    # ------------------------------------------------------------------ message history
    messages: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Ordered array of message objects with role, content, timestamp, …",
    )

    # ------------------------------------------------------------------ aggregates
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Cached count of messages; updated on each turn",
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Wall-clock duration from first to last message",
    )
    user_satisfaction_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="User-provided rating [1.0, 5.0]; NULL if not rated",
    )

    # ------------------------------------------------------------------ metadata
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Arbitrary session context: browser_info, referrer, geo, "
            "total_tokens_used, rag_retrievals, …"
        ),
    )

    # ------------------------------------------------------------------ relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="conversations",
        lazy="selectin",
    )
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="conversations",
        lazy="selectin",
    )
