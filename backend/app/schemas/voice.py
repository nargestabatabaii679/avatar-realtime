"""
schemas/voice.py
----------------
Pydantic v2 schemas for the VoiceModel domain.

Covers voice-clone creation, update, full response, the cloning request
workflow, and paginated lists.
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

from app.models.voice_model import TTSEngine, VoiceStatus

# ---------------------------------------------------------------------------
# Metadata sub-schema
# ---------------------------------------------------------------------------


class VoiceMetadata(BaseModel):
    """Structured view of the JSONB metadata column."""

    speaker_embedding_dim: int | None = Field(
        None, description="Dimensionality of the d-vector / speaker embedding"
    )
    sample_rate: int | None = Field(
        None, description="Audio sample rate in Hz (e.g. 22050, 44100)"
    )
    num_samples_used: int | None = Field(
        None, description="Number of audio samples used during training"
    )
    total_audio_seconds: float | None = Field(
        None, description="Cumulative duration of training audio in seconds"
    )
    training_epochs: int | None = None
    noise_level_db: float | None = Field(
        None, description="Estimated background noise level in dB"
    )
    snr_db: float | None = Field(None, description="Signal-to-noise ratio of the samples")
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class VoiceCreate(BaseModel):
    """Request body for POST /voices — provision a voice model record."""

    name: str = Field(min_length=1, max_length=255, description="Friendly voice name")
    description: str | None = Field(None, max_length=2000)
    organization_id: uuid.UUID
    language: str = Field(
        default="en",
        max_length=10,
        description="ISO 639-1 language code",
    )
    accent: str | None = Field(None, max_length=100, description="Optional accent descriptor")
    tts_engine: TTSEngine = Field(
        default=TTSEngine.XTTS,
        description="TTS back-end to use for training and inference",
    )
    is_public: bool = Field(default=False)

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class VoiceUpdate(BaseModel):
    """Request body for PATCH /voices/{id}."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    language: str | None = Field(None, max_length=10)
    accent: str | None = Field(None, max_length=100)
    is_public: bool | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class VoiceResponse(BaseModel):
    """Full voice-model representation returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    user_id: uuid.UUID
    organization_id: uuid.UUID
    sample_files: list[str] | None
    model_file_url: str | None
    voice_fingerprint_url: str | None
    language: str
    accent: str | None
    status: VoiceStatus
    quality_score: float | None
    tts_engine: TTSEngine
    is_public: bool
    usage_count: int
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata", default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}

    @field_validator("sample_files", mode="before")
    @classmethod
    def coerce_sample_files(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        return list(v) if not isinstance(v, list) else v


# ---------------------------------------------------------------------------
# Clone request
# ---------------------------------------------------------------------------


class VoiceCloneRequest(BaseModel):
    """
    Request body for POST /voices/{id}/clone-samples.

    Clients upload audio files separately (multipart) and then call this
    endpoint with the list of resulting object-storage URLs.
    """

    sample_urls: list[str] = Field(
        min_length=1,
        description="Object-storage URLs of the uploaded audio samples",
    )
    language: str = Field(
        default="en",
        max_length=10,
        description="Language of the audio samples",
    )
    tts_engine: TTSEngine = Field(
        default=TTSEngine.XTTS,
        description="TTS back-end to use for this clone job",
    )

    @field_validator("sample_urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        if len(v) > 30:
            raise ValueError("A maximum of 30 audio samples may be submitted per clone job.")
        return v


class VoiceCloneResponse(BaseModel):
    """Immediate response after a clone job is queued."""

    voice_model_id: uuid.UUID
    status: VoiceStatus = VoiceStatus.PROCESSING
    job_id: str | None = None
    estimated_duration_seconds: int | None = None
    message: str = "Voice cloning has started. Poll the voice model for status updates."


# ---------------------------------------------------------------------------
# TTS synthesis
# ---------------------------------------------------------------------------


class TTSSynthesisRequest(BaseModel):
    """Request body for POST /voices/{id}/synthesise."""

    text: str = Field(min_length=1, max_length=5000, description="Text to synthesise")
    language: str = Field(default="en", max_length=10)
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Playback speed multiplier")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Sampling temperature for XTTS / CosyVoice",
    )

    model_config = ConfigDict(extra="forbid")


class TTSSynthesisResponse(BaseModel):
    """Returned after successful TTS synthesis."""

    audio_url: str = Field(description="Object-storage URL of the generated audio file")
    duration_seconds: float
    sample_rate: int
    file_size_bytes: int
    synthesis_duration_ms: int = Field(description="Server-side synthesis latency in milliseconds")


# ---------------------------------------------------------------------------
# List response
# ---------------------------------------------------------------------------


class VoiceListResponse(BaseModel):
    """Paginated list of voice models."""

    items: list[VoiceResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
