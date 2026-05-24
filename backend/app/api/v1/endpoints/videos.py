"""
app/api/v1/endpoints/videos.py
--------------------------------
Video generation endpoints: single and batch generation, status polling,
download URLs, sharing, and templates.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    TokenData,
    assert_owner_or_admin,
    get_current_token_data,
)
from app.models.avatar import Avatar, AvatarStatus
from app.models.video import Video, VideoResolution, VideoStatus
from app.models.video_job import JobStatus, JobType, VideoJob
from app.models.voice_model import VoiceModel, VoiceStatus

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class VideoGenerateRequest(BaseModel):
    avatar_id: uuid.UUID
    voice_model_id: uuid.UUID | None = None
    script: str = Field(..., min_length=1, max_length=10000)
    language: str = Field("en", max_length=10)
    resolution: VideoResolution = VideoResolution.R_1080P
    template_id: uuid.UUID | None = None
    title: str | None = Field(None, max_length=255)
    description: str | None = None


class BatchGenerateRequest(BaseModel):
    jobs: list[VideoGenerateRequest] = Field(..., min_length=1, max_length=20)


class VideoResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    avatar_id: uuid.UUID
    voice_model_id: uuid.UUID | None
    script_text: str | None
    language: str
    resolution: str
    status: str
    job_id: str | None
    output_url: str | None
    thumbnail_url: str | None
    duration_seconds: float | None
    file_size_bytes: int | None
    view_count: int
    error_message: str | None
    metadata: dict
    user_id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    total: int
    page: int
    page_size: int
    pages: int


class VideoStatusResponse(BaseModel):
    video_id: uuid.UUID
    status: str
    progress: int
    current_stage: str | None
    error_message: str | None
    job_details: list[dict[str, Any]]


class DownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int
    filename: str


class ShareResponse(BaseModel):
    share_url: str
    share_token: str
    expires_at: datetime | None


class VideoTemplate(BaseModel):
    id: str
    name: str
    description: str
    thumbnail_url: str | None
    resolution: str
    tags: list[str]


class BatchResponse(BaseModel):
    jobs: list[dict[str, str]]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_video_or_404(db: AsyncSession, video_id: uuid.UUID) -> Video:
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.is_deleted.is_(False))
    )
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


async def _validate_avatar(
    db: AsyncSession,
    avatar_id: uuid.UUID,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Avatar:
    result = await db.execute(
        select(Avatar).where(
            Avatar.id == avatar_id,
            Avatar.is_deleted.is_(False),
            or_(Avatar.user_id == user_id, Avatar.is_public.is_(True)),
        )
    )
    avatar = result.scalar_one_or_none()
    if avatar is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found or not accessible",
        )
    if avatar.status != AvatarStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar is not ready for video generation",
        )
    return avatar


async def _validate_voice(
    db: AsyncSession,
    voice_id: uuid.UUID,
    user_id: uuid.UUID,
) -> VoiceModel:
    result = await db.execute(
        select(VoiceModel).where(
            VoiceModel.id == voice_id,
            VoiceModel.is_deleted.is_(False),
            or_(VoiceModel.user_id == user_id, VoiceModel.is_public.is_(True)),
        )
    )
    voice = result.scalar_one_or_none()
    if voice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice model not found or not accessible",
        )
    if voice.status != VoiceStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voice model is not ready for synthesis",
        )
    return voice


def _dispatch_video_pipeline(video_id: uuid.UUID, job_id: uuid.UUID) -> str:
    """Dispatch the full video generation pipeline to Celery; returns Celery task ID."""
    try:
        from app.workers.celery_app import celery_app  # noqa: PLC0415

        result = celery_app.send_task(
            "workers.video.generate_video_pipeline",
            args=[str(video_id), str(job_id)],
            queue="gpu",
        )
        celery_task_id: str = result.id
        logger.info(
            "video_pipeline_dispatched",
            video_id=str(video_id),
            celery_task_id=celery_task_id,
        )
        return celery_task_id
    except Exception as exc:  # noqa: BLE001
        logger.error("video_dispatch_failed", video_id=str(video_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video generation service temporarily unavailable",
        ) from exc


async def _get_presigned_url(object_name: str, bucket: str, expiry: int = 3600) -> str | None:
    try:
        from miniopy_async import Minio  # noqa: PLC0415

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        return await client.presigned_get_object(bucket, object_name, expires=expiry)
    except Exception as exc:  # noqa: BLE001
        logger.warning("presigned_url_failed", object=object_name, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=VideoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a talking avatar video",
)
async def generate_video(
    payload: VideoGenerateRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Video:
    """
    Start a video generation pipeline:

    1. Validates avatar and voice model ownership/readiness
    2. Creates ``Video`` and ``VideoJob`` database records
    3. Dispatches the Celery pipeline: TTS → lip-sync → encode → upload
    4. Returns immediately with ``status=queued``
    """
    if token_data.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    if payload.language not in settings.SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported language. Supported: {', '.join(settings.SUPPORTED_LANGUAGES)}",
        )

    # Validate avatar
    await _validate_avatar(db, payload.avatar_id, token_data.user_id, token_data.organization_id)

    # Validate voice model (optional)
    if payload.voice_model_id is not None:
        await _validate_voice(db, payload.voice_model_id, token_data.user_id)

    # Derive title from script if not provided
    title = payload.title or payload.script[:60].replace("\n", " ")

    video = Video(
        title=title,
        description=payload.description,
        user_id=token_data.user_id,
        organization_id=token_data.organization_id,
        avatar_id=payload.avatar_id,
        voice_model_id=payload.voice_model_id,
        script_text=payload.script,
        language=payload.language,
        resolution=payload.resolution,
        template_id=payload.template_id,
        status=VideoStatus.QUEUED,
    )
    db.add(video)
    await db.flush()

    # Create pipeline job record
    pipeline_job = VideoJob(
        video_id=video.id,
        job_type=JobType.FULL_PIPELINE,
        status=JobStatus.PENDING,
    )
    db.add(pipeline_job)
    await db.flush()

    # Dispatch Celery task
    celery_task_id = _dispatch_video_pipeline(video.id, pipeline_job.id)

    # Store Celery task ID
    await db.execute(
        update(Video).where(Video.id == video.id).values(job_id=celery_task_id)
    )
    await db.execute(
        update(VideoJob)
        .where(VideoJob.id == pipeline_job.id)
        .values(celery_task_id=celery_task_id)
    )

    logger.info(
        "video_generation_started",
        video_id=str(video.id),
        user_id=str(token_data.user_id),
    )
    await db.refresh(video)
    return video


@router.get(
    "",
    response_model=VideoListResponse,
    summary="List videos with pagination and filtering",
)
async def list_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: VideoStatus | None = Query(None, alias="status"),
    avatar_id: uuid.UUID | None = Query(None),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> VideoListResponse:
    """List videos owned by the current user."""
    query = select(Video).where(
        Video.user_id == token_data.user_id,
        Video.is_deleted.is_(False),
    )
    if status_filter is not None:
        query = query.where(Video.status == status_filter)
    if avatar_id is not None:
        query = query.where(Video.avatar_id == avatar_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Video.created_at.desc()).offset(offset).limit(page_size)
    )
    videos = result.scalars().all()

    return VideoListResponse(
        items=[VideoResponse.model_validate(v) for v in videos],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/templates",
    response_model=list[VideoTemplate],
    summary="List available video templates",
)
async def list_templates(
    token_data: TokenData = Depends(get_current_token_data),
) -> list[VideoTemplate]:
    """Return available scene/layout templates for video generation."""
    # In a real system, templates would come from DB or config storage.
    # Returning built-in defaults here.
    return [
        VideoTemplate(
            id="default",
            name="Default",
            description="Plain background with centered avatar",
            thumbnail_url=None,
            resolution="1080p",
            tags=["basic", "professional"],
        ),
        VideoTemplate(
            id="office",
            name="Office",
            description="Professional office background",
            thumbnail_url=None,
            resolution="1080p",
            tags=["office", "professional", "corporate"],
        ),
        VideoTemplate(
            id="studio",
            name="Studio",
            description="Broadcast studio environment",
            thumbnail_url=None,
            resolution="1080p",
            tags=["studio", "broadcast", "news"],
        ),
        VideoTemplate(
            id="minimal_4k",
            name="Minimal 4K",
            description="Minimalist white background at 4K resolution",
            thumbnail_url=None,
            resolution="4k",
            tags=["minimal", "4k", "clean"],
        ),
    ]


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get video details",
)
async def get_video(
    video_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Video:
    """Retrieve video details by ID."""
    video = await _get_video_or_404(db, video_id)
    assert_owner_or_admin(video.user_id, token_data)
    return video


@router.get(
    "/{video_id}/status",
    response_model=VideoStatusResponse,
    summary="Poll video generation status with progress percentage",
)
async def get_video_status(
    video_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> VideoStatusResponse:
    """
    Poll the current status and progress of a video generation job.

    The ``progress`` field is a percentage (0–100).
    ``job_details`` lists each pipeline stage's individual status.
    """
    video = await _get_video_or_404(db, video_id)
    assert_owner_or_admin(video.user_id, token_data)

    # Fetch associated jobs
    jobs_result = await db.execute(
        select(VideoJob).where(VideoJob.video_id == video_id).order_by(VideoJob.created_at.asc())
    )
    jobs = jobs_result.scalars().all()

    # Aggregate progress from jobs
    overall_progress = 0
    current_stage: str | None = None

    if jobs:
        active_jobs = [j for j in jobs if j.status not in (JobStatus.SUCCESS, JobStatus.REVOKED)]
        if active_jobs:
            current_stage = active_jobs[0].job_type.value
            overall_progress = active_jobs[0].progress
        elif all(j.status == JobStatus.SUCCESS for j in jobs):
            overall_progress = 100

    job_details = [
        {
            "job_type": j.job_type.value,
            "status": j.status.value,
            "progress": j.progress,
            "worker_id": j.worker_id,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]

    return VideoStatusResponse(
        video_id=video_id,
        status=video.status.value,
        progress=overall_progress,
        current_stage=current_stage,
        error_message=video.error_message,
        job_details=job_details,
    )


@router.get(
    "/{video_id}/download",
    response_model=DownloadResponse,
    summary="Generate a presigned download URL for the video",
)
async def download_video(
    video_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> DownloadResponse:
    """Generate a time-limited presigned URL for downloading the rendered video."""
    video = await _get_video_or_404(db, video_id)
    assert_owner_or_admin(video.user_id, token_data)

    if video.status != VideoStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video is not ready for download",
        )

    if not video.output_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video output file not found",
        )

    parts = video.output_url.split(f"/{settings.MINIO_BUCKET_VIDEOS}/")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid video storage URL",
        )

    expiry = settings.MINIO_PRESIGNED_EXPIRY
    download_url = await _get_presigned_url(parts[1], settings.MINIO_BUCKET_VIDEOS, expiry)
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate download URL",
        )

    # Increment view count
    await db.execute(
        update(Video).where(Video.id == video_id).values(view_count=Video.view_count + 1)
    )

    filename = f"{video.title.replace(' ', '_')[:50]}_{video_id}.mp4"
    return DownloadResponse(
        download_url=download_url,
        expires_in_seconds=expiry,
        filename=filename,
    )


@router.post(
    "/{video_id}/share",
    response_model=ShareResponse,
    summary="Generate a public shareable link for the video",
)
async def share_video(
    video_id: uuid.UUID,
    expires_hours: int = Query(72, ge=1, le=720),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> ShareResponse:
    """
    Generate a shareable link for the video.

    The link is valid for the specified number of hours (default 72).
    The share token is stored in Redis.
    """
    video = await _get_video_or_404(db, video_id)
    assert_owner_or_admin(video.user_id, token_data)

    if video.status != VideoStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed videos can be shared",
        )

    import secrets  # noqa: PLC0415

    share_token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    try:
        from app.core.redis_client import redis_client  # noqa: PLC0415

        await redis_client.setex(
            f"share:{share_token}",
            expires_hours * 3600,
            str(video_id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("share_token_store_failed", error=str(exc))

    # In production, this would be a proper frontend URL
    share_url = f"{settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else 'http://localhost:3000'}/share/{share_token}"

    return ShareResponse(
        share_url=share_url,
        share_token=share_token,
        expires_at=expires_at,
    )


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a video and its storage files",
)
async def delete_video(
    video_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete the video record and schedule storage cleanup."""
    video = await _get_video_or_404(db, video_id)
    assert_owner_or_admin(video.user_id, token_data)

    output_url = video.output_url
    thumbnail_url = video.thumbnail_url

    # Cancel running Celery task if any
    if video.job_id and video.status in (VideoStatus.QUEUED, VideoStatus.PROCESSING, VideoStatus.RENDERING):
        background_tasks.add_task(_revoke_celery_task, video.job_id)

    video.soft_delete()
    logger.info("video_deleted", video_id=str(video_id))

    if output_url or thumbnail_url:
        background_tasks.add_task(_cleanup_video_storage, str(video_id), output_url, thumbnail_url)


@router.post(
    "/batch",
    response_model=BatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch generate multiple videos",
)
async def batch_generate(
    payload: BatchGenerateRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> BatchResponse:
    """
    Dispatch multiple video generation jobs in a single request.

    Maximum 20 jobs per batch. Each job is queued independently.
    Returns the list of video IDs and their initial status.
    """
    if token_data.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    results: list[dict[str, str]] = []

    for job_req in payload.jobs:
        try:
            # Validate avatar
            await _validate_avatar(
                db, job_req.avatar_id, token_data.user_id, token_data.organization_id
            )

            # Validate voice (optional)
            if job_req.voice_model_id:
                await _validate_voice(db, job_req.voice_model_id, token_data.user_id)

            title = job_req.title or job_req.script[:60].replace("\n", " ")
            video = Video(
                title=title,
                description=job_req.description,
                user_id=token_data.user_id,
                organization_id=token_data.organization_id,
                avatar_id=job_req.avatar_id,
                voice_model_id=job_req.voice_model_id,
                script_text=job_req.script,
                language=job_req.language,
                resolution=job_req.resolution,
                template_id=job_req.template_id,
                status=VideoStatus.QUEUED,
            )
            db.add(video)
            await db.flush()

            pipeline_job = VideoJob(
                video_id=video.id,
                job_type=JobType.FULL_PIPELINE,
                status=JobStatus.PENDING,
            )
            db.add(pipeline_job)
            await db.flush()

            celery_task_id = _dispatch_video_pipeline(video.id, pipeline_job.id)
            await db.execute(
                update(Video).where(Video.id == video.id).values(job_id=celery_task_id)
            )

            results.append({
                "video_id": str(video.id),
                "status": "queued",
                "celery_task_id": celery_task_id,
            })
        except HTTPException as exc:
            results.append({
                "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "status": "failed",
            })

    logger.info(
        "batch_generate_started",
        user_id=str(token_data.user_id),
        count=len(payload.jobs),
    )
    return BatchResponse(jobs=results, total=len(results))


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------


def _revoke_celery_task(task_id: str) -> None:
    try:
        from app.workers.celery_app import celery_app  # noqa: PLC0415
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        logger.info("celery_task_revoked", task_id=task_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("celery_revoke_failed", task_id=task_id, error=str(exc))


async def _cleanup_video_storage(
    video_id: str,
    output_url: str | None,
    thumbnail_url: str | None,
) -> None:
    try:
        from miniopy_async import Minio  # noqa: PLC0415

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        bucket = settings.MINIO_BUCKET_VIDEOS

        for url in [output_url, thumbnail_url]:
            if not url:
                continue
            parts = url.split(f"/{bucket}/")
            if len(parts) == 2:
                try:
                    await client.remove_object(bucket, parts[1])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("video_file_delete_failed", url=url, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("video_cleanup_failed", video_id=video_id, error=str(exc))
