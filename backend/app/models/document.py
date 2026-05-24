"""
Document — a source file uploaded to a KnowledgeBase for RAG ingestion.

Documents are chunked, embedded, and stored in Qdrant during the indexing
pipeline.  This table tracks the raw file reference and chunking status.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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
    from app.models.knowledge_base import KnowledgeBase


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DocumentFileType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    TXT = "txt"
    URL = "url"
    PRODUCT_CATALOG = "product_catalog"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Document(UUIDBase):
    """
    A single source document within a KnowledgeBase.

    ``filename`` is the sanitised storage key; ``original_filename`` preserves
    the name as uploaded by the user.  For URL sources, ``file_url`` holds the
    target URL and ``file_size_bytes`` may be NULL.

    The ``metadata`` JSONB column stores extraction diagnostics::

        {
            "page_count": 12,
            "language_detected": "en",
            "char_count": 34512,
            "extractor": "pypdfium2",
            "indexed_at": "2025-01-01T00:00:00Z",
            "error_detail": null
        }
    """

    __tablename__ = "documents"

    # ------------------------------------------------------------------ foreign key
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent knowledge base",
    )

    # ------------------------------------------------------------------ file identity
    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Sanitised storage key / filename used in object-storage",
    )
    original_filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Original filename as supplied by the uploader",
    )

    # ------------------------------------------------------------------ file type & location
    file_type: Mapped[DocumentFileType] = mapped_column(
        Enum(DocumentFileType, name="document_file_type_enum"),
        nullable=False,
        comment="Content type / document category",
    )
    file_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Object-storage URL for file types; the target URL for URL sources",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Raw file size in bytes; NULL for URL sources",
    )

    # ------------------------------------------------------------------ indexing status
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum"),
        nullable=False,
        default=DocumentStatus.PENDING,
        server_default=text("'pending'"),
        index=True,
        comment="Current stage of the ingestion pipeline",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of text chunks produced after splitting",
    )

    # ------------------------------------------------------------------ metadata
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Extraction diagnostics: page_count, language_detected, "
            "char_count, extractor, error_detail, …"
        ),
    )

    # ------------------------------------------------------------------ relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        back_populates="documents",
        lazy="selectin",
    )
