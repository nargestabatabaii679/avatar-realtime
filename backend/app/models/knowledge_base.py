"""
KnowledgeBase — RAG document collection backed by Qdrant vector search.

Each KnowledgeBase maps 1-to-1 with a Qdrant collection and can be
attached to one or more Agents for grounded Q&A.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
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
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.document import Document
    from app.models.agent import Agent


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KnowledgeBaseStatus(str, enum.Enum):
    EMPTY = "empty"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    REBUILDING = "rebuilding"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class KnowledgeBase(UUIDBase):
    """
    A named collection of documents that are chunked, embedded, and stored
    in Qdrant for retrieval-augmented generation.

    ``qdrant_collection_id`` is the UUID / string key of the corresponding
    Qdrant collection.  ``embedding_model`` identifies the sentence-transformer
    or OpenAI embedding model used so that queries are encoded consistently.
    """

    __tablename__ = "knowledge_bases"

    # ------------------------------------------------------------------ identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User-facing name of the knowledge base",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of the knowledge domain",
    )

    # ------------------------------------------------------------------ ownership
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who created this knowledge base",
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning organisation",
    )

    # ------------------------------------------------------------------ Qdrant reference
    qdrant_collection_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        comment="Identifier of the corresponding Qdrant collection",
    )

    # ------------------------------------------------------------------ statistics
    document_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of source documents ingested",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Total number of text chunks stored in Qdrant",
    )

    # ------------------------------------------------------------------ configuration
    embedding_model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="text-embedding-3-large",
        server_default=text("'text-embedding-3-large'"),
        comment="Name of the embedding model; must stay consistent within a collection",
    )

    # ------------------------------------------------------------------ status
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(KnowledgeBaseStatus, name="knowledge_base_status_enum"),
        nullable=False,
        default=KnowledgeBaseStatus.EMPTY,
        server_default=text("'empty'"),
        comment="Current indexing state",
    )

    # ------------------------------------------------------------------ visibility
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Whether the knowledge base is accessible to all org members",
    )

    # ------------------------------------------------------------------ settings
    settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Chunking strategy, chunk_size, chunk_overlap, "
            "retrieval_top_k, rerank_enabled, language_filter, …"
        ),
    )

    # ------------------------------------------------------------------ relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="knowledge_bases",
        lazy="selectin",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="knowledge_bases",
        lazy="selectin",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="knowledge_base",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="knowledge_base",
        lazy="noload",
    )
