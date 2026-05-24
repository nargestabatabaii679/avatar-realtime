"""
app/api/v1/endpoints/voices.py
--------------------------------
Voice cloning endpoints: multi-file upload, XTTS-v2 training dispatch,
TTS synthesis, test audio generation, and language listing.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    TokenData,
    assert_owner_or_admin,
    get_current_token_data,
)
from app.models.voice_model import TTSEngine, VoiceModel, VoiceStatus

logger = structlog.get_logger(__name__)

router = APIRouter()

_ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "flac", "m4a", "ogg"}
_ALLOWED_AUDIO_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/x-flac",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "audio/vnd.wave",
}
_MIN_SAMPLES = 1
_MAX_SAMPLES = 20


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class VoiceModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    language: str
    accent: str | None
    status: str
    tts_engine: str
    quality_score: float | None
    is_public: bool
    usage_count: int
    metadata: dict
    user_id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VoiceListResponse(BaseModel):
    items: list[VoiceModelResponse]
    total: int
    page: int
    page_size: int
    pages: int


class VoiceStatusResponse(BaseModel):
    voice_id: uuid.UUID
    status: str
    quality_score: float | None
    error: str | None = None


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice_model_id: uuid.UUID
    language: str = Field("en", max_length=10)
    speed: float = Field(1.0, ge=0.5, le=2.0)
    output_format: str = Field("wav", pattern=r"^(wav|mp3|ogg)$")


class TestVoiceRequest(BaseModel):
    text: str = Field(
        "Hello, this is a test of the voice cloning system.",
        min_length=5,
        max_length=500,
    )
    language: str = Field("en", max_length=10)


class LanguagesResponse(BaseModel):
    languages: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_voice_or_404(db: AsyncSession, voice_id: uuid.UUID) -> VoiceModel:
    result = await db.execute(
        select(VoiceModel).where(VoiceModel.id == voice_id, VoiceModel.is_deleted.is_(False))
    )
    voice = result.scalar_one_or_none()
    if voice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice model not found")
    return voice


def _validate_audio_file(file: UploadFile) -> str:
    """Validate audio file type; return extension."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported audio format '.{ext}'. Allowed: {', '.join(_ALLOWED_AUDIO_EXTENSIONS)}",
        )
    content_type = file.content_type or ""
    if content_type and content_type not in _ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported MIME type '{content_type}'",
        )
    return ext


async def _upload_audio_to_minio(content: bytes, object_name: str) -> str:
    """Upload audio bytes to MinIO and return the object URL."""
    try:
        from miniopy_async import Minio  # noqa: PLC0415

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        bucket = settings.MINIO_BUCKET_AUDIO
        await client.put_object(
            bucket,
            object_name,
            io.BytesIO(content),
            length=len(content),
            content_type="audio/wav",
        )
        scheme = "https" if settings.MINIO_SECURE else "http"
        return f"{scheme}://{settings.MINIO_ENDPOINT}/{bucket}/{object_name}"
    except Exception as exc:  # noqa: BLE001
        logger.error("audio_upload_failed", object=object_name, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
        ) from exc


def _dispatch_voice_cloning(voice_id: uuid.UUID, sample_urls: list[str]) -> None:
    """Dispatch XTTS-v2 voice cloning Celery task."""
    try:
        from app.workers.celery_app import celery_app  # noqa: PLC0415

        celery_app.send_task(
            "workers.voice.clone_voice",
            args=[str(voice_id), sample_urls],
            queue="gpu",
        )
        logger.info("voice_cloning_dispatched", voice_id=str(voice_id))
    except Exception as exc:  # noqa: BLE001
        logger.error("voice_clone_dispatch_failed", voice_id=str(voice_id), error=str(exc))


def _dispatch_tts(voice_id: uuid.UUID, text: str, language: str, speed: float) -> Any:
    """Dispatch TTS synthesis and return Celery AsyncResult."""
    try:
        from app.workers.celery_app import celery_app  # noqa: PLC0415

        result = celery_app.send_task(
            "workers.voice.synthesize_speech",
            args=[str(voice_id), text, language, speed],
            queue="gpu",
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("tts_dispatch_failed", voice_id=str(voice_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS service temporarily unavailable",
        ) from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/clone",
    response_model=VoiceModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload audio samples and start voice cloning",
)
async def clone_voice(
    background_tasks: BackgroundTasks,
    name: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(None),
    language: str = Form("en", max_length=10),
    accent: str | None = Form(None, max_length=100),
    tts_engine: TTSEngine = Form(TTSEngine.XTTS),
    files: list[UploadFile] = File(..., description="1–20 audio sample files (wav, mp3, flac, m4a)"),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> VoiceModel:
    """
    Upload audio samples and dispatch voice cloning.

    - Accepts 1–20 audio files (wav, mp3, flac, m4a, ogg)
    - Recommended minimum: 30 seconds of clean speech total
    - Dispatches XTTS-v2 (or selected engine) cloning as a Celery task
    - Returns immediately with status ``processing``
    """
    if not files or len(files) < _MIN_SAMPLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"At least {_MIN_SAMPLES} audio file(s) required",
        )
    if len(files) > _MAX_SAMPLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum {_MAX_SAMPLES} audio files allowed per voice",
        )

    if token_data.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    if language not in settings.SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported language. Supported: {', '.join(settings.SUPPORTED_LANGUAGES)}",
        )

    voice_id = uuid.uuid4()
    sample_urls: list[str] = []

    # Upload each sample file
    for i, audio_file in enumerate(files):
        ext = _validate_audio_file(audio_file)
        content = await audio_file.read()

        if len(content) > settings.max_audio_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Audio file {audio_file.filename!r} exceeds {settings.MAX_AUDIO_SIZE_MB} MB limit",
            )

        object_name = f"{token_data.user_id}/{voice_id}/samples/sample_{i:03d}.{ext}"
        url = await _upload_audio_to_minio(content, object_name)
        sample_urls.append(url)

    # Create DB record
    voice_model = VoiceModel(
        id=voice_id,
        name=name,
        description=description,
        user_id=token_data.user_id,
        organization_id=token_data.organization_id,
        sample_files=sample_urls,
        language=language,
        accent=accent,
        tts_engine=tts_engine,
        status=VoiceStatus.PROCESSING,
        metadata={"sample_count": len(files)},
    )
    db.add(voice_model)
    await db.flush()

    # Dispatch cloning task
    background_tasks.add_task(_dispatch_voice_cloning, voice_model.id, sample_urls)

    logger.info(
        "voice_clone_started",
        voice_id=str(voice_id),
        samples=len(files),
        user_id=str(token_data.user_id),
    )
    return voice_model


@router.get(
    "",
    response_model=VoiceListResponse,
    summary="List voice models",
)
async def list_voices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: VoiceStatus | None = Query(None, alias="status"),
    language: str | None = Query(None, max_length=10),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> VoiceListResponse:
    """List voice models owned by the current user."""
    query = select(VoiceModel).where(
        VoiceModel.user_id == token_data.user_id,
        VoiceModel.is_deleted.is_(False),
    )
    if status_filter is not None:
        query = query.where(VoiceModel.status == status_filter)
    if language is not None:
        query = query.where(VoiceModel.language == language)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(VoiceModel.created_at.desc()).offset(offset).limit(page_size)
    )
    voices = result.scalars().all()

    return VoiceListResponse(
        items=[VoiceModelResponse.model_validate(v) for v in voices],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/languages",
    response_model=LanguagesResponse,
    summary="List supported languages for voice cloning / TTS",
)
async def list_languages() -> LanguagesResponse:
    """Return all supported language codes with display names."""
    language_names = {
        "en": "English", "es": "Spanish", "fr": "French", "de": "German",
        "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
        "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
        "hi": "Hindi", "tr": "Turkish", "pl": "Polish", "sv": "Swedish",
        "da": "Danish", "fi": "Finnish", "no": "Norwegian", "cs": "Czech",
    }
    return LanguagesResponse(
        languages=[
            {"code": code, "name": language_names.get(code, code)}
            for code in settings.SUPPORTED_LANGUAGES
        ]
    )


@router.get(
    "/{voice_id}",
    response_model=VoiceModelResponse,
    summary="Get voice model details",
)
async def get_voice(
    voice_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> VoiceModel:
    """Retrieve a voice model by ID."""
    voice = await _get_voice_or_404(db, voice_id)
    assert_owner_or_admin(voice.user_id, token_data)
    return voice


@router.delete(
    "/{voice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a voice model",
)
async def delete_voice(
    voice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a voice model and schedule storage cleanup."""
    voice = await _get_voice_or_404(db, voice_id)
    assert_owner_or_admin(voice.user_id, token_data)

    sample_files = list(voice.sample_files or [])
    model_url = voice.model_file_url

    voice.soft_delete()
    logger.info("voice_deleted", voice_id=str(voice_id))

    background_tasks.add_task(_cleanup_voice_storage, str(voice_id), sample_files, model_url)


@router.get(
    "/{voice_id}/status",
    response_model=VoiceStatusResponse,
    summary="Check voice cloning status",
)
async def get_voice_status(
    voice_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> VoiceStatusResponse:
    """Poll the processing status of a voice cloning job."""
    voice = await _get_voice_or_404(db, voice_id)
    assert_owner_or_admin(voice.user_id, token_data)

    error_msg: str | None = None
    if voice.status == VoiceStatus.FAILED:
        error_msg = (voice.metadata or {}).get("error_message")

    return VoiceStatusResponse(
        voice_id=voice_id,
        status=voice.status.value,
        quality_score=voice.quality_score,
        error=error_msg,
    )


@router.post(
    "/{voice_id}/test",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a test audio sample",
)
async def test_voice(
    voice_id: uuid.UUID,
    payload: TestVoiceRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Generate a short test audio clip using the cloned voice.

    The clip is generated asynchronously; poll status or use webhooks.
    Returns a task ID to retrieve the audio URL once ready.
    """
    voice = await _get_voice_or_404(db, voice_id)
    assert_owner_or_admin(voice.user_id, token_data)

    if voice.status != VoiceStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voice model must be in 'ready' status to generate test audio",
        )

    task = _dispatch_tts(voice.id, payload.text, payload.language, speed=1.0)
    task_id = task.id if hasattr(task, "id") else str(uuid.uuid4())

    return {
        "detail": "Test audio generation queued",
        "task_id": task_id,
        "voice_id": str(voice_id),
    }


@router.post(
    "/tts",
    summary="Text-to-speech synthesis with a voice model",
)
async def text_to_speech(
    payload: TTSRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Synthesize speech from text using a trained voice model.

    Returns audio bytes as a streaming response.
    For long text, consider using the async batch generation endpoint.
    """
    voice = await _get_voice_or_404(db, payload.voice_model_id)

    # Allow using own voices or public ones
    if not voice.is_public:
        assert_owner_or_admin(voice.user_id, token_data)

    if voice.status != VoiceStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voice model is not ready for synthesis",
        )

    if payload.language not in settings.SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported language '{payload.language}'",
        )

    # Attempt direct synthesis (requires ML workers running in-process)
    try:
        from app.ml.voice.xtts import synthesize  # noqa: PLC0415

        audio_bytes = await synthesize(
            voice_model=voice,
            text=payload.text,
            language=payload.language,
            speed=payload.speed,
        )
        media_type = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
        }.get(payload.output_format, "audio/wav")

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="tts_output.{payload.output_format}"'
            },
        )
    except ImportError:
        # ML not available in API process — dispatch to worker
        task = _dispatch_tts(voice.id, payload.text, payload.language, payload.speed)
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={
                "message": "TTS dispatched to worker",
                "task_id": task.id if hasattr(task, "id") else None,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("tts_synthesis_failed", voice_id=str(voice.id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech synthesis failed",
        ) from exc


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------


async def _cleanup_voice_storage(
    voice_id: str,
    sample_urls: list[str],
    model_url: str | None,
) -> None:
    """Remove voice sample files and model artifacts from MinIO."""
    try:
        from miniopy_async import Minio  # noqa: PLC0415

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        bucket = settings.MINIO_BUCKET_AUDIO

        for url in sample_urls + ([model_url] if model_url else []):
            if not url:
                continue
            parts = url.split(f"/{bucket}/")
            if len(parts) == 2:
                try:
                    await client.remove_object(bucket, parts[1])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("voice_file_delete_failed", url=url, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("voice_storage_cleanup_failed", voice_id=voice_id, error=str(exc))
