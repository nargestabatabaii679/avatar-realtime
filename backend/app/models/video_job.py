"""
VideoJob — per-stage job tracking record for the rendering pipeline.

Each Video may spawn multiple VideoJob records (e.g. TTS, lip-sync, encoding).
Progress, worker assignment, and detailed logs are captured here so that
clients can display granular status via WebSocket or polling.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
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
    from app.models.video import Video


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JobType(str, enum.Enum):
    TTS_SYNTHESIS = "tts_synthesis"
    LIP_SYNC = "lip_sync"
    VIDEO_ENCODE = "video_encode"
    FACE_RESTORE = "face_restore"
    THUMBNAIL = "thumbnail"
    UPLOAD = "upload"
    FULL_PIPELINE = "full_pipeline"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    STARTED = "started"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class VideoJob(UUIDBase):
    """
    Fine-grained job record for a single stage of the rendering pipeline.

    ``log_messages`` is a JSONB array of structured log entries::

        [{"ts": "2025-01-01T00:00:00Z", "level": "INFO", "msg": "Started GPU inference"}, …]

    ``error_details`` captures the exception type, traceback, and retry count
    when a job enters the FAILURE state.
    """

    __tablename__ = "video_jobs"

    # ------------------------------------------------------------------ foreign key
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Video this job belongs to",
    )

    # ------------------------------------------------------------------ job identity
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type_enum"),
        nullable=False,
        comment="Which stage of the pipeline this record tracks",
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Celery task UUID; enables revocation and result retrieval",
    )

    # ------------------------------------------------------------------ status / progress
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum"),
        nullable=False,
        default=JobStatus.PENDING,
        server_default=text("'pending'"),
        index=True,
        comment="Current Celery task state",
    )
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Completion percentage in [0, 100]",
    )

    # ------------------------------------------------------------------ timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the Celery worker began processing",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the job reached a terminal state",
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Wall-clock duration; computed from started_at / completed_at",
    )

    # ------------------------------------------------------------------ worker / hardware
    worker_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Celery worker hostname, e.g. 'celery@gpu-node-01'",
    )
    gpu_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="CUDA device used, e.g. 'cuda:0'",
    )

    # ------------------------------------------------------------------ logs / diagnostics
    log_messages: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Ordered list of structured log entries from the worker",
    )
    error_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Failure diagnostics: exc_type, exc_message, traceback, "
            "retry_count, last_retry_at"
        ),
    )

    # ------------------------------------------------------------------ retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of times this task has been retried",
    )

    # ------------------------------------------------------------------ relationships
    video: Mapped["Video"] = relationship(
        "Video",
        back_populates="jobs",
        lazy="selectin",
    )
