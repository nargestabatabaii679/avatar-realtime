from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from uuid import UUID

import structlog

from app.core.celery_app import celery_app
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@celery_app.task(
    bind=True,
    name="workers.avatar_tasks.process_avatar_upload",
    queue="gpu",
    max_retries=2,
    default_retry_delay=15,
    soft_time_limit=300,
    time_limit=420,
)
def process_avatar_upload(
    self,
    avatar_id: str,
    file_url: str,
    source_type: str,
    organization_id: str,
    user_id: str,
) -> dict:
    """Process an uploaded avatar: detect face, extract embedding, generate thumbnail."""
    log = logger.bind(avatar_id=avatar_id)
    log.info("avatar_processing_started")

    async def _process():
        from app.core.database import AsyncSessionLocal
        from app.models.avatar import Avatar, AvatarStatus
        from app.services.storage.minio_service import download_to_path, upload_file
        from app.ml.avatar.face_analyzer import FaceAnalyzer
        from sqlalchemy import update

        analyzer = FaceAnalyzer()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_ext = Path(file_url).suffix.lower()
            source_path = tmp / f"source{source_ext}"

            # Download source file
            obj_name = "/".join(file_url.split("/")[1:])
            await download_to_path("avatars", obj_name, source_path)

            # Extract first frame if video
            image_path = source_path
            if source_ext in (".mp4", ".mov", ".avi"):
                image_path = tmp / "frame.jpg"
                import subprocess
                subprocess.run(
                    ["ffmpeg", "-i", str(source_path), "-vframes", "1", "-q:v", "2", str(image_path)],
                    capture_output=True, check=True,
                )

            # Run face analysis
            result = await analyzer.analyze(str(image_path))

            if not result.get("face_detected"):
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(Avatar)
                        .where(Avatar.id == UUID(avatar_id))
                        .values(status=AvatarStatus.FAILED, metadata={"error": "no_face_detected"})
                    )
                    await db.commit()
                return {"status": "failed", "error": "no_face_detected"}

            # Save thumbnail
            thumb_path = tmp / "thumbnail.jpg"
            await analyzer.save_thumbnail(str(image_path), str(thumb_path))

            thumb_object = f"{organization_id}/avatars/{avatar_id}/thumbnail.jpg"
            with open(thumb_path, "rb") as f:
                thumb_bytes = f.read()
            await upload_file("avatars", thumb_object, thumb_bytes, "image/jpeg")

            # Update DB record
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Avatar)
                    .where(Avatar.id == UUID(avatar_id))
                    .values(
                        status=AvatarStatus.READY,
                        thumbnail_url=f"avatars/{thumb_object}",
                        face_embedding=result.get("embedding"),
                        metadata={
                            "quality_score": result.get("quality_score"),
                            "landmarks_count": result.get("landmarks_count"),
                            "face_bbox": result.get("bbox"),
                            "age": result.get("age"),
                            "gender": result.get("gender"),
                        },
                    )
                )
                await db.commit()

            log.info("avatar_processing_completed", quality=result.get("quality_score"))
            return {
                "avatar_id": avatar_id,
                "status": "ready",
                "quality_score": result.get("quality_score"),
                "thumbnail_url": thumb_object,
            }

    try:
        return asyncio.run(_process())
    except Exception as exc:
        log.error("avatar_processing_failed", error=str(exc), exc_info=True)
        asyncio.run(_mark_avatar_failed(avatar_id, str(exc)))
        raise self.retry(exc=exc, countdown=15)


async def _mark_avatar_failed(avatar_id: str, error: str) -> None:
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.avatar import Avatar, AvatarStatus
        from sqlalchemy import update

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Avatar)
                .where(Avatar.id == UUID(avatar_id))
                .values(status=AvatarStatus.FAILED, metadata={"error": error[:200]})
            )
            await db.commit()
    except Exception:
        pass
