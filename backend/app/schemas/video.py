"""
schemas/video.py
----------------
Pydantic v2 schemas for the Video generation domain.

Key schemas:
  - VideoGenerateRequest  — job submission
  - VideoResponse         — full video record
  - VideoStatusResponse   — lightweight polling response
  - VideoListResponse     — paginated list
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

from app.models.video import VideoResolution, VideoStatus
from app.models.video_job import JobStatus, JobType


# ---------------------------------------------------------------------------
# Codec / render settings sub-schema
# ---------------------------------------------------------------------------


class VideoRenderSettings(BaseModel):
    """Optional advanced render parameters embedded in VideoGenerateRequest."""

    fps: int = Field(default=25, ge=10, le=60, description="Frames per second")
    codec: str = Field(default="h264", description="Video codec, e.g. h264, h265, vp9")
    audio_codec: str = Field(default="aac", description="Audio codec, e.g. aac, opus")
    audio_sample_rate: int = Field(default=44100, description="Audio sample rate in Hz")
    encoder_preset: str = Field(
        default="medium",
        description="Encoder speed/quality preset, e.g. ultrafast, medium, slow",
    )
    crf: int = Field(default=23, ge=0, le=51, description="Constant Rate Factor (H.264/H.265)")
    background_color: str | None = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Background hex colour when the avatar has transparency",
    )
    watermark_url: str | None = Field(None, description="Object-storage URL of a watermark image")
    face_restoration: bool = Field(
        default=True,
        description="Run GFPGAN / CodeFormer face restoration pass",
    )

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Video generate request
# ---------------------------------------------------------------------------


class VideoGenerateRequest(BaseModel):
    """
    Request body for POST /videos/generate.

    The script is split into sentences internally; each sentence drives one
    TTS + lip-sync pass, and results are concatenated by the encoder step.
    """

    title: str = Field(min_length=1, max_length=255, description="Human-readable video title")
    description: str | None = Field(None, max_length=2000)
    avatar_id: uuid.UUID = Field(description="UUID of the avatar asset to use")
    voice_model_id: uuid.UUID | None = Field(
        None,
        description="UUID of the voice-clone model; uses platform default if omitted",
    )
    script_text: str = Field(
        min_length=1,
        max_length=20_000,
        description="Full narration script passed to TTS",
    )
    language: str = Field(
        default="en",
        max_length=10,
        description="ISO 639-1 language code for TTS synthesis",
    )
    resolution: VideoResolution = Field(
        default=VideoResolution.R_1080P,
        description="Output video resolution",
    )
    template_id: uuid.UUID | None = Field(
        None,
        description="Optional scene / layout template UUID",
    )
    render_settings: VideoRenderSettings = Field(
        default_factory=VideoRenderSettings,
        description="Advanced codec and render configuration",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("script_text")
    @classmethod
    def strip_script(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("script_text must not be empty or whitespace only.")
        return stripped


# ---------------------------------------------------------------------------
# Job status sub-schema
# ---------------------------------------------------------------------------


class VideoJobResponse(BaseModel):
    """Single pipeline stage status embedded in VideoResponse / VideoStatusResponse."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: JobType
    celery_task_id: str | None
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    worker_id: str | None
    gpu_id: str | None
    retry_count: int
    error_details: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Video response
# ---------------------------------------------------------------------------


class VideoResponse(BaseModel):
    """Full video record returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    user_id: uuid.UUID
    organization_id: uuid.UUID
    avatar_id: uuid.UUID
    voice_model_id: uuid.UUID | None
    script_text: str | None
    language: str
    resolution: VideoResolution
    output_url: str | None
    thumbnail_url: str | None
    duration_seconds: float | None
    file_size_bytes: int | None
    status: VideoStatus
    job_id: str | None
    error_message: str | None
    template_id: uuid.UUID | None
    processing_duration_seconds: float | None
    view_count: int
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata", default_factory=dict)
    jobs: list[VideoJobResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}


# ---------------------------------------------------------------------------
# Status response (lightweight polling)
# ---------------------------------------------------------------------------


class VideoStatusResponse(BaseModel):
    """Lightweight status response for polling GET /videos/{id}/status."""

    id: uuid.UUID
    status: VideoStatus
    progress_percent: int | None = Field(None, ge=0, le=100)
    current_stage: str | None = Field(
        None,
        description="Human-readable description of the active pipeline stage",
    )
    output_url: str | None = None
    thumbnail_url: str | None = None
    error_message: str | None = None
    processing_duration_seconds: float | None = None
    estimated_remaining_seconds: int | None = None
    jobs: list[VideoJobResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class VideoUpdate(BaseModel):
    """Partial update for video title / description (admin only)."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# List response
# ---------------------------------------------------------------------------


class VideoListResponse(BaseModel):
    """Paginated list of video records."""

    items: list[VideoResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Download / share
# ---------------------------------------------------------------------------


class VideoDownloadResponse(BaseModel):
    """Pre-signed download URL for a completed video."""

    video_id: uuid.UUID
    download_url: str = Field(description="Pre-signed URL valid for the indicated TTL")
    expires_in_seconds: int = Field(description="TTL of the pre-signed URL in seconds")
    file_size_bytes: int | None = None
    resolution: VideoResolution


class VideoShareResponse(BaseModel):
    """Public share link for embedding or sharing."""

    video_id: uuid.UUID
    share_url: str
    embed_code: str = Field(description="HTML iframe embed snippet")
    expires_at: datetime | None = Field(
        None,
        description="Share link expiry; None means the link is permanent",
    )
