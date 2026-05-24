"""
schemas/avatar.py
-----------------
Pydantic v2 schemas for the Avatar domain.

Covers CRUD operations, upload flow, and paginated list responses.
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

from app.models.avatar import AvatarSourceType, AvatarStatus


# ---------------------------------------------------------------------------
# Shared metadata schema
# ---------------------------------------------------------------------------


class AvatarMetadata(BaseModel):
    """Structured representation of the JSONB metadata column."""

    quality_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Overall face quality score [0.0, 1.0]",
    )
    face_landmarks: list[list[float]] | None = Field(
        None,
        description="2-D landmark coordinates [[x, y], …]",
    )
    bounding_box: dict[str, float] | None = Field(
        None,
        description="Face bounding box: {x, y, width, height} in pixels",
    )
    pose_angles: dict[str, float] | None = Field(
        None,
        description="Head pose angles: {yaw, pitch, roll} in degrees",
    )
    illumination_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Illumination uniformity score [0.0, 1.0]",
    )
    symmetry_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Facial symmetry score [0.0, 1.0]",
    )
    source_resolution: str | None = Field(
        None,
        description="Resolution of the source image/video, e.g. '1920x1080'",
    )
    face_count: int | None = Field(
        None,
        ge=0,
        description="Number of faces detected in the source (1 is ideal)",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Engine-specific diagnostics",
    )

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class AvatarCreate(BaseModel):
    """Request body for POST /avatars — create a new avatar record."""

    name: str = Field(min_length=1, max_length=255, description="Friendly avatar name")
    description: str | None = Field(None, max_length=2000)
    source_type: AvatarSourceType
    organization_id: uuid.UUID = Field(description="Owning organisation UUID")
    is_public: bool = Field(default=False, description="Share with all org members")

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class AvatarUpdate(BaseModel):
    """Request body for PATCH /avatars/{id}."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_public: bool | None = None
    thumbnail_url: AnyHttpUrl | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class AvatarResponse(BaseModel):
    """Full avatar representation returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    user_id: uuid.UUID
    organization_id: uuid.UUID
    source_type: AvatarSourceType
    source_file_url: str | None
    thumbnail_url: str | None
    motion_template_url: str | None
    status: AvatarStatus
    is_public: bool
    usage_count: int
    processing_duration_seconds: float | None
    # ORM attribute is 'extra_metadata'; serialise as 'metadata' in JSON
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata", default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}


# ---------------------------------------------------------------------------
# Upload response
# ---------------------------------------------------------------------------


class AvatarUploadResponse(BaseModel):
    """
    Returned immediately after a multipart file upload is accepted.

    The avatar starts in 'processing' status; clients should poll
    GET /avatars/{id} or subscribe to the WebSocket for state changes.
    """

    avatar_id: uuid.UUID
    status: AvatarStatus = AvatarStatus.PROCESSING
    upload_url: str | None = Field(
        None,
        description="Pre-signed URL for direct-to-storage upload; NULL if the file was accepted inline",
    )
    estimated_processing_seconds: int | None = Field(
        None,
        description="Rough ETA for the processing pipeline",
    )
    message: str = "Avatar uploaded successfully. Processing has started."


# ---------------------------------------------------------------------------
# Processing status
# ---------------------------------------------------------------------------


class AvatarStatusResponse(BaseModel):
    """Lightweight status poll response."""

    id: uuid.UUID
    status: AvatarStatus
    progress_percent: int | None = Field(None, ge=0, le=100)
    error_message: str | None = None
    processing_duration_seconds: float | None = None


# ---------------------------------------------------------------------------
# List response (paginated)
# ---------------------------------------------------------------------------


class AvatarListResponse(BaseModel):
    """Paginated list of avatars."""

    items: list[AvatarResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Embedding / search
# ---------------------------------------------------------------------------


class AvatarEmbeddingResponse(BaseModel):
    """Returned when a face embedding search is performed."""

    avatar_id: uuid.UUID
    similarity_score: float = Field(ge=0.0, le=1.0)
    avatar: AvatarResponse
