"""
app/api/v1/endpoints/avatars.py
--------------------------------
Avatar management: upload, processing dispatch, status polling, marketplace,
thumbnail regeneration, and duplication.
"""

from __future__ import annotations

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
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    Role,
    TokenData,
    assert_owner_or_admin,
    get_current_token_data,
    has_minimum_role,
)
from app.models.avatar import Avatar, AvatarSourceType, AvatarStatus

logger = structlog.get_logger(__name__)

router = APIRouter()

# Allowed MIME types / extensions
_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "mp4", "mov"}
_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "video/mp4",
    "video/quicktime",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AvatarResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    source_type: str
    source_file_url: str | None
    thumbnail_url: str | None
    status: str
    is_public: bool
    usage_count: int
    metadata: dict
    processing_duration_seconds: float | None
    user_id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvatarListResponse(BaseModel):
    items: list[AvatarResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UpdateAvatarRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_public: bool | None = None


class AvatarStatusResponse(BaseModel):
    avatar_id: uuid.UUID
    status: str
    processing_duration_seconds: float | None
    thumbnail_url: str | None
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_avatar_or_404(db: AsyncSession, avatar_id: uuid.UUID) -> Avatar:
    result = await db.execute(
        select(Avatar).where(Avatar.id == avatar_id, Avatar.is_deleted.is_(False))
    )
    av = result.scalar_one_or_none()
    if av is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    return av


def _validate_file(file: UploadFile, max_bytes: int) -> str:
    """Return the file extension; raise 422 on unsupported type or size violation."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )
    content_type = file.content_type or ""
    if content_type and content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported MIME type '{content_type}'",
        )
    return ext


async def _upload_to_minio(file: UploadFile, object_name: str, bucket: str) -> str:
    """Upload a file to MinIO and return its object URL."""
    try:
        from miniopy_async import Minio  # noqa: PLC0415

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        content = await file.read()
        content_type = file.content_type or "application/octet-stream"

        import io  # noqa: PLC0415
        await client.put_object(
            bucket,
            object_name,
            io.BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
        scheme = "https" if settings.MINIO_SECURE else "http"
        return f"{scheme}://{settings.MINIO_ENDPOINT}/{bucket}/{object_name}"
    except Exception as exc:  # noqa: BLE001
        logger.error("minio_upload_failed", object=object_name, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
        ) from exc


async def _get_presigned_url(object_name: str, bucket: str) -> str | None:
    """Return a presigned GET URL for an object, or None on failure."""
    try:
        from miniopy_async import Minio  # noqa: PLC0415

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        url = await client.presigned_get_object(
            bucket,
            object_name,
            expires=settings.MINIO_PRESIGNED_EXPIRY,
        )
        return url
    except Exception as exc:  # noqa: BLE001
        logger.warning("presigned_url_failed", object=object_name, error=str(exc))
        return None


def _dispatch_avatar_processing(avatar_id: uuid.UUID) -> None:
    """Dispatch Celery task for avatar processing pipeline."""
    try:
        from app.workers.celery_app import celery_app  # noqa: PLC0415
        celery_app.send_task(
            "workers.avatar.process_avatar",
            args=[str(avatar_id)],
            queue="gpu",
        )
        logger.info("avatar_processing_dispatched", avatar_id=str(avatar_id))
    except Exception as exc:  # noqa: BLE001
        logger.error("celery_dispatch_failed", avatar_id=str(avatar_id), error=str(exc))


def _dispatch_thumbnail_regen(avatar_id: uuid.UUID) -> None:
    """Dispatch thumbnail regeneration Celery task."""
    try:
        from app.workers.celery_app import celery_app  # noqa: PLC0415
        celery_app.send_task(
            "workers.avatar.regenerate_thumbnail",
            args=[str(avatar_id)],
            queue="cpu",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("thumbnail_dispatch_failed", avatar_id=str(avatar_id), error=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AvatarResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and create a new avatar",
)
async def create_avatar(
    background_tasks: BackgroundTasks,
    name: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(None),
    is_public: bool = Form(False),
    file: UploadFile = File(..., description="Source image (jpg/png) or video (mp4/mov)"),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Avatar:
    """
    Upload a photo or video to create a digital-human avatar.

    Processing pipeline (async via Celery):
    1. Face detection and quality scoring
    2. Embedding extraction (InsightFace)
    3. Motion template pre-computation
    4. Thumbnail generation
    """
    ext = _validate_file(file, settings.max_upload_size_bytes)

    # Determine source type
    if ext in {"jpg", "jpeg", "png"}:
        source_type = AvatarSourceType.PHOTO
        size_limit = settings.max_image_size_bytes
    else:
        source_type = AvatarSourceType.VIDEO
        size_limit = settings.max_video_size_bytes

    # Read content to check size
    content = await file.read()
    if len(content) > size_limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {size_limit // 1024 // 1024} MB",
        )

    # Re-wrap content for upload
    import io  # noqa: PLC0415
    file.file = io.BytesIO(content)  # type: ignore[attr-defined]

    avatar_id = uuid.uuid4()
    object_name = f"{token_data.user_id}/{avatar_id}/source.{ext}"

    # Upload to MinIO
    source_url = await _upload_to_minio(file, object_name, settings.MINIO_BUCKET_AVATARS)

    if token_data.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization to create avatars",
        )

    avatar = Avatar(
        id=avatar_id,
        name=name,
        description=description,
        user_id=token_data.user_id,
        organization_id=token_data.organization_id,
        source_type=source_type,
        source_file_url=source_url,
        status=AvatarStatus.PROCESSING,
        is_public=is_public,
    )
    db.add(avatar)
    await db.flush()

    # Dispatch async processing
    background_tasks.add_task(_dispatch_avatar_processing, avatar.id)

    logger.info("avatar_created", avatar_id=str(avatar.id), user_id=str(token_data.user_id))
    return avatar


@router.get(
    "",
    response_model=AvatarListResponse,
    summary="List user avatars",
)
async def list_avatars(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: AvatarStatus | None = Query(None, alias="status"),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> AvatarListResponse:
    """List avatars owned by the current user, with optional status filtering."""
    query = select(Avatar).where(
        Avatar.user_id == token_data.user_id,
        Avatar.is_deleted.is_(False),
    )
    if status_filter is not None:
        query = query.where(Avatar.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Avatar.created_at.desc()).offset(offset).limit(page_size)
    )
    avatars = result.scalars().all()
    pages = (total + page_size - 1) // page_size

    return AvatarListResponse(
        items=[AvatarResponse.model_validate(a) for a in avatars],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/public",
    response_model=AvatarListResponse,
    summary="List public avatars (marketplace)",
)
async def list_public_avatars(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_token_data),
) -> AvatarListResponse:
    """List all publicly shared avatars available in the marketplace."""
    query = select(Avatar).where(
        Avatar.is_public.is_(True),
        Avatar.status == AvatarStatus.READY,
        Avatar.is_deleted.is_(False),
    )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Avatar.usage_count.desc(), Avatar.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    avatars = result.scalars().all()
    pages = (total + page_size - 1) // page_size

    return AvatarListResponse(
        items=[AvatarResponse.model_validate(a) for a in avatars],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{avatar_id}",
    response_model=AvatarResponse,
    summary="Get avatar details with presigned URLs",
)
async def get_avatar(
    avatar_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    """Retrieve avatar details. Source URLs are returned as presigned MinIO URLs."""
    avatar = await _get_avatar_or_404(db, avatar_id)
    assert_owner_or_admin(avatar.user_id, token_data)

    response = AvatarResponse.model_validate(avatar)

    # Enrich with presigned URLs if source file exists
    if avatar.source_file_url:
        # Extract object name from stored URL
        parts = avatar.source_file_url.split(f"/{settings.MINIO_BUCKET_AVATARS}/")
        if len(parts) == 2:
            presigned = await _get_presigned_url(parts[1], settings.MINIO_BUCKET_AVATARS)
            if presigned:
                response.source_file_url = presigned

    if avatar.thumbnail_url:
        parts = avatar.thumbnail_url.split(f"/{settings.MINIO_BUCKET_AVATARS}/")
        if len(parts) == 2:
            presigned = await _get_presigned_url(parts[1], settings.MINIO_BUCKET_AVATARS)
            if presigned:
                response.thumbnail_url = presigned

    return response


@router.put(
    "/{avatar_id}",
    response_model=AvatarResponse,
    summary="Update avatar metadata",
)
async def update_avatar(
    avatar_id: uuid.UUID,
    payload: UpdateAvatarRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Avatar:
    """Update an avatar's name, description, or visibility."""
    avatar = await _get_avatar_or_404(db, avatar_id)
    assert_owner_or_admin(avatar.user_id, token_data)

    update_values: dict[str, Any] = {}
    if payload.name is not None:
        update_values["name"] = payload.name
    if payload.description is not None:
        update_values["description"] = payload.description
    if payload.is_public is not None:
        update_values["is_public"] = payload.is_public

    if update_values:
        await db.execute(update(Avatar).where(Avatar.id == avatar_id).values(**update_values))
        await db.refresh(avatar)

    return avatar


@router.delete(
    "/{avatar_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete avatar and remove from storage",
)
async def delete_avatar(
    avatar_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete the avatar record and schedule storage cleanup."""
    avatar = await _get_avatar_or_404(db, avatar_id)
    assert_owner_or_admin(avatar.user_id, token_data)

    source_url = avatar.source_file_url
    thumbnail_url = avatar.thumbnail_url

    avatar.soft_delete()
    logger.info("avatar_deleted", avatar_id=str(avatar_id))

    # Schedule storage cleanup
    if source_url or thumbnail_url:
        background_tasks.add_task(
            _cleanup_avatar_storage, str(avatar_id), source_url, thumbnail_url
        )


@router.get(
    "/{avatar_id}/status",
    response_model=AvatarStatusResponse,
    summary="Poll avatar processing status",
)
async def get_avatar_status(
    avatar_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> AvatarStatusResponse:
    """Poll the processing status of an avatar."""
    avatar = await _get_avatar_or_404(db, avatar_id)
    assert_owner_or_admin(avatar.user_id, token_data)

    error_msg: str | None = None
    if avatar.status == AvatarStatus.FAILED:
        error_msg = avatar.metadata.get("error_message") if avatar.metadata else None

    return AvatarStatusResponse(
        avatar_id=avatar_id,
        status=avatar.status.value,
        processing_duration_seconds=avatar.processing_duration_seconds,
        thumbnail_url=avatar.thumbnail_url,
        error=error_msg,
    )


@router.post(
    "/{avatar_id}/regenerate-thumbnail",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger thumbnail regeneration",
)
async def regenerate_thumbnail(
    avatar_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Dispatch a Celery task to regenerate the avatar's thumbnail image."""
    avatar = await _get_avatar_or_404(db, avatar_id)
    assert_owner_or_admin(avatar.user_id, token_data)

    if avatar.status != AvatarStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thumbnail can only be regenerated for avatars with status 'ready'",
        )

    background_tasks.add_task(_dispatch_thumbnail_regen, avatar.id)
    return {"detail": "Thumbnail regeneration queued", "avatar_id": str(avatar_id)}


@router.post(
    "/{avatar_id}/duplicate",
    response_model=AvatarResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone an existing avatar",
)
async def duplicate_avatar(
    avatar_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    name: str | None = Query(None, max_length=255),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Avatar:
    """
    Create a copy of an existing avatar.

    The source file URL is shared (no re-upload); processing is re-dispatched
    to compute fresh embeddings and motion templates.
    """
    source = await _get_avatar_or_404(db, avatar_id)

    # Allow duplicating own avatars OR public avatars
    if not source.is_public:
        assert_owner_or_admin(source.user_id, token_data)

    if token_data.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    new_avatar = Avatar(
        name=name or f"{source.name} (copy)",
        description=source.description,
        user_id=token_data.user_id,
        organization_id=token_data.organization_id,
        source_type=source.source_type,
        source_file_url=source.source_file_url,  # Share the source file
        status=AvatarStatus.PROCESSING,
        is_public=False,
        metadata={},
    )
    db.add(new_avatar)
    await db.flush()

    background_tasks.add_task(_dispatch_avatar_processing, new_avatar.id)
    logger.info(
        "avatar_duplicated",
        source_id=str(avatar_id),
        new_id=str(new_avatar.id),
        user_id=str(token_data.user_id),
    )
    return new_avatar


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------


async def _cleanup_avatar_storage(
    avatar_id: str,
    source_url: str | None,
    thumbnail_url: str | None,
) -> None:
    """Remove avatar files from MinIO after soft-delete."""
    try:
        from miniopy_async import Minio  # noqa: PLC0415

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        bucket = settings.MINIO_BUCKET_AVATARS

        for url in [source_url, thumbnail_url]:
            if not url:
                continue
            parts = url.split(f"/{bucket}/")
            if len(parts) == 2:
                try:
                    await client.remove_object(bucket, parts[1])
                    logger.info("storage_object_deleted", object=parts[1])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("storage_delete_failed", object=parts[1], error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("storage_cleanup_failed", avatar_id=avatar_id, error=str(exc))
