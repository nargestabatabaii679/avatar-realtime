"""
VoiceModel — voice-clone asset produced by a TTS/voice-cloning pipeline.

Stores sample file references, the trained model artifact, quality metrics,
and engine-specific metadata.
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
    from app.models.video import Video
    from app.models.agent import Agent


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VoiceStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class TTSEngine(str, enum.Enum):
    XTTS = "xtts"
    COSYVOICE = "cosyvoice"
    F5TTS = "f5tts"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class VoiceModel(UUIDBase):
    """
    Voice-clone model asset.

    ``sample_files`` is a PostgreSQL text-array of object-storage URLs pointing
    to the raw audio samples used for training.  The trained artefact lives at
    ``model_file_url`` and the extracted voice fingerprint at
    ``voice_fingerprint_url``.
    """

    __tablename__ = "voice_models"

    # ------------------------------------------------------------------ identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User-assigned friendly name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description or intended use",
    )

    # ------------------------------------------------------------------ ownership
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who created this voice model",
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning organisation",
    )

    # ------------------------------------------------------------------ source material
    sample_files: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
        comment="Array of object-storage URLs for the training audio samples",
    )

    # ------------------------------------------------------------------ trained artefacts
    model_file_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Object-storage URL of the serialised TTS checkpoint",
    )
    voice_fingerprint_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="URL for the d-vector / speaker embedding file used for similarity",
    )

    # ------------------------------------------------------------------ linguistic metadata
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
        comment="ISO 639-1 language code the model was trained on",
    )
    accent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional accent descriptor, e.g. 'british', 'american'",
    )

    # ------------------------------------------------------------------ status / quality
    status: Mapped[VoiceStatus] = mapped_column(
        Enum(VoiceStatus, name="voice_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VoiceStatus.PROCESSING,
        server_default=text("'processing'"),
        comment="Current processing state",
    )
    quality_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="MOS-like quality score in [0.0, 5.0]",
    )

    # ------------------------------------------------------------------ engine
    tts_engine: Mapped[TTSEngine] = mapped_column(
        Enum(TTSEngine, name="tts_engine_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TTSEngine.XTTS,
        server_default=text("'xtts'"),
        comment="TTS back-end used for synthesis",
    )

    # ------------------------------------------------------------------ metadata
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Engine-specific data: speaker_embedding_dim, sample_rate, "
            "num_samples_used, training_epochs, noise_level, …"
        ),
    )

    # ------------------------------------------------------------------ visibility / usage
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Shared across the organisation (True) or private to the creator",
    )
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of videos / conversations generated with this voice",
    )

    # ------------------------------------------------------------------ relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="voice_models",
        lazy="selectin",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="voice_models",
        lazy="selectin",
    )
    videos: Mapped[list["Video"]] = relationship(
        "Video",
        back_populates="voice_model",
        lazy="noload",
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="voice_model",
        lazy="noload",
    )
