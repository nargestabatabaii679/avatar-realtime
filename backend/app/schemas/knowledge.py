"""
schemas/knowledge.py
--------------------
Pydantic v2 schemas for KnowledgeBase and Document domains.

Covers knowledge base CRUD, document upload flow, and RAG search.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.document import DocumentFileType, DocumentStatus
from app.models.knowledge_base import KnowledgeBaseStatus


# ---------------------------------------------------------------------------
# Knowledge base settings sub-schema
# ---------------------------------------------------------------------------


class ChunkingSettings(BaseModel):
    """Controls how documents are split into vector-search chunks."""

    strategy: str = Field(
        default="recursive",
        description="Chunking strategy: 'recursive', 'sentence', 'fixed', 'semantic'",
    )
    chunk_size: int = Field(default=512, ge=64, le=4096, description="Max tokens per chunk")
    chunk_overlap: int = Field(
        default=64,
        ge=0,
        le=512,
        description="Token overlap between consecutive chunks",
    )

    @model_validator(mode="after")
    def overlap_lt_chunk_size(self) -> "ChunkingSettings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size.")
        return self


class RetrievalSettings(BaseModel):
    """Controls how the RAG retriever queries Qdrant."""

    top_k: int = Field(default=5, ge=1, le=50, description="Number of chunks to retrieve")
    score_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for a chunk to be included",
    )
    rerank_enabled: bool = Field(
        default=False,
        description="Run a cross-encoder reranker after initial retrieval",
    )
    rerank_top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of chunks to keep after reranking",
    )
    hybrid_search: bool = Field(
        default=False,
        description="Combine dense + sparse (BM25) retrieval",
    )


class KnowledgeBaseSettings(BaseModel):
    """Aggregated settings stored in the JSONB column."""

    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    language_filter: str | None = Field(
        None,
        max_length=10,
        description="Restrict retrieval to a specific language (ISO 639-1)",
    )
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Knowledge base create / update / response
# ---------------------------------------------------------------------------


class KnowledgeBaseCreate(BaseModel):
    """Request body for POST /knowledge-bases."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    organization_id: uuid.UUID
    embedding_model: str = Field(
        default="text-embedding-3-large",
        max_length=255,
        description="Embedding model name; must be consistent for the lifetime of the collection",
    )
    is_public: bool = Field(default=False)
    settings: KnowledgeBaseSettings = Field(default_factory=KnowledgeBaseSettings)

    model_config = ConfigDict(extra="forbid")


class KnowledgeBaseUpdate(BaseModel):
    """Request body for PATCH /knowledge-bases/{id}."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_public: bool | None = None
    settings: KnowledgeBaseSettings | None = None

    model_config = ConfigDict(extra="forbid")


class KnowledgeBaseResponse(BaseModel):
    """Full knowledge base representation returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    user_id: uuid.UUID
    organization_id: uuid.UUID
    qdrant_collection_id: str | None
    document_count: int
    chunk_count: int
    embedding_model: str
    status: KnowledgeBaseStatus
    is_public: bool
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @field_validator("settings", mode="before")
    @classmethod
    def coerce_settings(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}


class KnowledgeBaseListResponse(BaseModel):
    """Paginated list of knowledge bases."""

    items: list[KnowledgeBaseResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentMetadata(BaseModel):
    """Structured view of the document JSONB metadata column."""

    page_count: int | None = None
    language_detected: str | None = None
    char_count: int | None = None
    word_count: int | None = None
    extractor: str | None = None
    indexed_at: datetime | None = None
    error_detail: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class DocumentResponse(BaseModel):
    """Full document record returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    filename: str
    original_filename: str
    file_type: DocumentFileType
    file_url: str | None
    file_size_bytes: int | None
    status: DocumentStatus
    chunk_count: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}


class DocumentUploadResponse(BaseModel):
    """
    Returned immediately after a document upload is accepted.

    The document starts in 'pending' status and will be processed
    asynchronously by the ingestion pipeline.
    """

    document_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    original_filename: str
    file_type: DocumentFileType
    file_size_bytes: int | None
    status: DocumentStatus = DocumentStatus.PENDING
    upload_url: str | None = Field(
        None,
        description="Pre-signed URL for direct upload; NULL if file was accepted inline",
    )
    message: str = "Document uploaded. Ingestion pipeline has been queued."


class DocumentListResponse(BaseModel):
    """Paginated list of documents within a knowledge base."""

    items: list[DocumentResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)


# ---------------------------------------------------------------------------
# URL ingestion
# ---------------------------------------------------------------------------


class URLIngestRequest(BaseModel):
    """Request body for POST /knowledge-bases/{id}/ingest-url."""

    url: AnyHttpUrl = Field(description="Public URL to scrape and ingest")
    title: str | None = Field(None, max_length=512, description="Optional display title")
    crawl_depth: int = Field(
        default=0,
        ge=0,
        le=3,
        description="How many levels of links to follow (0 = page only)",
    )

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# RAG search
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """Request body for POST /knowledge-bases/{id}/search."""

    query: str = Field(min_length=1, max_length=2000, description="Natural-language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of results to return")
    score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for inclusion",
    )
    filter_document_ids: list[uuid.UUID] | None = Field(
        None,
        description="Restrict search to a subset of document IDs",
    )
    language_filter: str | None = Field(None, max_length=10)
    rerank: bool = Field(
        default=False,
        description="Apply cross-encoder reranking to the candidate set",
    )

    model_config = ConfigDict(extra="forbid")


class SearchResultItem(BaseModel):
    """A single vector-search result."""

    chunk_id: str = Field(description="Qdrant point ID for this chunk")
    document_id: uuid.UUID
    filename: str
    original_filename: str
    chunk_index: int
    content: str = Field(description="Text content of the retrieved chunk")
    score: float = Field(ge=0.0, le=1.0, description="Cosine similarity score")
    metadata: dict[str, Any] = Field(default_factory=dict)
    page_number: int | None = None
    highlight: str | None = Field(
        None,
        description="Query-relevant highlighted excerpt",
    )


class SearchResponse(BaseModel):
    """Response from POST /knowledge-bases/{id}/search."""

    query: str
    total_results: int = Field(ge=0)
    results: list[SearchResultItem]
    search_latency_ms: int = Field(description="Server-side retrieval latency in milliseconds")
    reranked: bool = Field(description="Whether cross-encoder reranking was applied")


# ---------------------------------------------------------------------------
# Re-index
# ---------------------------------------------------------------------------


class ReindexRequest(BaseModel):
    """Request body for POST /knowledge-bases/{id}/reindex."""

    document_ids: list[uuid.UUID] | None = Field(
        None,
        description="Specific documents to re-index; omit to re-index all",
    )
    force: bool = Field(
        default=False,
        description="Re-embed even documents that are already indexed",
    )
