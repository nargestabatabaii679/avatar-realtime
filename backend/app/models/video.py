"""
Video — a generated video asset produced by the rendering pipeline.

Stores the generation request parameters, processing status, output artefacts,
and Celery job tracking reference.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Enum,
    Float,
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
    from app.models.avatar import Avatar
    from app.models.voice_model import VoiceModel
    from app.models.video_job import VideoJob


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VideoResolution(str, enum.Enum):
    R_720P = "720p"
    R_1080P = "1080p"
    R_4K = "4k"


class VideoStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Video(UUIDBase):
    """
    A rendered video asset.

    The ``metadata`` JSONB column stores codec details, bitrate, fps, and any
    per-render engine diagnostics.  The ``job_id`` field is the Celery task ID
    used to correlate async workers with this record.
    """

    __tablename__ = "videos"

    # ------------------------------------------------------------------ identity
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable title assigned by the user or defaulted from the script",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of the video",
    )

    # ------------------------------------------------------------------ ownership
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who initiated this generation job",
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning organisation",
    )

    # ------------------------------------------------------------------ generation inputs
    avatar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("avatars.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Avatar used as the digital-human appearance source",
    )
    voice_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("voice_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Voice-clone model used for speech synthesis; NULL uses the default TTS",
    )
    script_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full script / narration text passed to TTS",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
        comment="ISO 639-1 language code for TTS synthesis",
    )
    resolution: Mapped[VideoResolution] = mapped_column(
        Enum(VideoResolution, name="video_resolution_enum"),
        nullable=False,
        default=VideoResolution.R_1080P,
        server_default=text("'1080p'"),
        comment="Output resolution of the rendered video",
    )

    # ------------------------------------------------------------------ template
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Optional reference to a scene / layout template",
    )

    # ------------------------------------------------------------------ output
    output_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Object-storage URL of the final rendered video file",
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Object-storage URL of the video preview frame",
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Playback duration in seconds",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Compressed file size in bytes",
    )

    # ------------------------------------------------------------------ status / job tracking
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, name="video_status_enum"),
        nullable=False,
        default=VideoStatus.QUEUED,
        server_default=text("'queued'"),
        index=True,
        comment="Current pipeline stage",
    )
    job_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Celery task UUID; used for progress polling and revocation",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable error description when status='failed'",
    )
    processing_duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Wall-clock seconds from job dispatch to completion",
    )

    # ------------------------------------------------------------------ codec metadata
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Render diagnostics: fps, codec, bitrate, audio_codec, "
            "audio_sample_rate, encoder_preset, gpu_id, …"
        ),
    )

    # ------------------------------------------------------------------ usage
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of times the video has been viewed",
    )

    # ------------------------------------------------------------------ relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="videos",
        lazy="selectin",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="videos",
        lazy="selectin",
    )
    avatar: Mapped["Avatar"] = relationship(
        "Avatar",
        back_populates="videos",
        lazy="selectin",
    )
    voice_model: Mapped["VoiceModel | None"] = relationship(
        "VoiceModel",
        back_populates="videos",
        lazy="selectin",
    )
    jobs: Mapped[list["VideoJob"]] = relationship(
        "VideoJob",
        back_populates="video",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
