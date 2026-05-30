"""
app/workers/video.py
---------------------
Video generation Celery tasks — re-exports the full pipeline task under the
canonical name ``workers.video.generate_video_pipeline`` so that the API
endpoint's ``send_task()`` call resolves correctly.

The actual implementation lives in ``app.workers.video_tasks`` to avoid
circular imports with the Celery application factory.
"""

from __future__ import annotations

from app.core.celery_app import celery_app
from app.workers.video_tasks import (  # noqa: F401 (re-export)
    generate_video_task,
    _get_video_duration,
    _mark_failed,
    _track_video_event,
)

import structlog

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="workers.video.generate_video_pipeline",
    queue="gpu",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=1800,
    time_limit=2400,
)
def generate_video_pipeline(self, video_id: str, job_id: str) -> dict:
    """
    Entry-point called by the FastAPI endpoint via ``send_task``.

    Looks up the Video record to retrieve generation parameters, then
    delegates to the full pipeline implementation.
    """
    import asyncio

    async def _load_params() -> dict:
        from app.core.database import AsyncSessionLocal
        from app.models.video import Video

        async with AsyncSessionLocal() as db:
            video = await db.get(Video, __import__("uuid").UUID(video_id))
            if not video:
                raise ValueError(f"Video {video_id} not found")
            return {
                "avatar_id": str(video.avatar_id),
                "voice_model_id": str(video.voice_model_id) if video.voice_model_id else None,
                "script": video.script_text or "",
                "language": video.language,
                "resolution": video.resolution.value if hasattr(video.resolution, "value") else video.resolution,
                "organization_id": str(video.organization_id),
                "user_id": str(video.user_id),
                "provider": (video.extra_metadata or {}).get("provider", "local"),
            }

    try:
        params = asyncio.run(_load_params())
    except Exception as exc:
        logger.error("video_params_load_failed", video_id=video_id, error=str(exc))
        asyncio.run(_mark_failed(video_id, str(exc)))
        raise

    provider = params.pop("provider", "local")

    if provider == "heygen":
        return _run_heygen_pipeline(self, video_id, job_id, **params)
    elif provider == "syncso":
        return _run_syncso_pipeline(self, video_id, job_id, **params)
    else:
        # Local GPU pipeline
        return generate_video_task.apply(
            args=[
                video_id,
                params["avatar_id"],
                params["voice_model_id"],
                params["script"],
                params["language"],
                params["resolution"],
                params["organization_id"],
                params["user_id"],
            ]
        ).get()


def _run_heygen_pipeline(self, video_id: str, job_id: str, **params) -> dict:
    """Dispatch video generation to HeyGen cloud API."""
    import asyncio

    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.video import Video, VideoStatus
        from app.models.video_job import VideoJob, JobStatus
        from app.services.heygen import HeyGenService
        from sqlalchemy import update
        import datetime

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(VideoJob)
                .where(VideoJob.video_id == __import__("uuid").UUID(video_id))
                .values(status=JobStatus.STARTED, started_at=datetime.datetime.utcnow())
            )
            await db.execute(
                update(Video)
                .where(Video.id == __import__("uuid").UUID(video_id))
                .values(status=VideoStatus.PROCESSING)
            )
            await db.commit()

        heygen = HeyGenService()
        heygen_video_id = await heygen.generate_video(
            script=params["script"],
            language=params["language"],
            avatar_id=params.get("avatar_id"),
        )

        # Poll until complete (up to 30 min)
        import time
        deadline = time.time() + 1800
        while time.time() < deadline:
            status_data = await heygen.get_video_status(heygen_video_id)
            if status_data["status"] == "completed":
                download_url = status_data.get("video_url", "")
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(Video)
                        .where(Video.id == __import__("uuid").UUID(video_id))
                        .values(
                            status=VideoStatus.COMPLETED,
                            output_url=download_url,
                            duration_seconds=status_data.get("duration"),
                        )
                    )
                    await db.execute(
                        update(VideoJob)
                        .where(VideoJob.video_id == __import__("uuid").UUID(video_id))
                        .values(status=JobStatus.SUCCESS, progress=100, completed_at=datetime.datetime.utcnow())
                    )
                    await db.commit()
                return {"video_id": video_id, "status": "completed", "output_url": download_url}
            elif status_data["status"] == "failed":
                raise RuntimeError(f"HeyGen generation failed: {status_data.get('error')}")
            await asyncio.sleep(10)

        raise TimeoutError("HeyGen video generation timed out after 30 minutes")

    try:
        return asyncio.run(_run())
    except Exception as exc:
        asyncio.run(_mark_failed(video_id, str(exc)))
        raise self.retry(exc=exc, countdown=60)


def _run_syncso_pipeline(self, video_id: str, job_id: str, **params) -> dict:
    """Dispatch lip-sync to Sync.so cloud API."""
    import asyncio

    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.video import Video, VideoStatus
        from app.models.video_job import VideoJob, JobStatus
        from app.services.syncso import SyncSoService
        from sqlalchemy import update, select
        from app.models.avatar import Avatar
        import datetime

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(VideoJob)
                .where(VideoJob.video_id == __import__("uuid").UUID(video_id))
                .values(status=JobStatus.STARTED, started_at=datetime.datetime.utcnow())
            )
            await db.execute(
                update(Video)
                .where(Video.id == __import__("uuid").UUID(video_id))
                .values(status=VideoStatus.PROCESSING)
            )
            avatar = await db.get(Avatar, __import__("uuid").UUID(params["avatar_id"]))
            await db.commit()

        avatar_video_url = (avatar.extra_metadata or {}).get("video_url") if avatar else None
        if not avatar_video_url:
            raise ValueError("Avatar has no reference video for Sync.so lip-sync")

        # First generate TTS audio to get audio URL — use OpenAI TTS as fallback
        from openai import AsyncOpenAI
        from app.core.config import settings as cfg
        import tempfile, os

        client = AsyncOpenAI(api_key=cfg.OPENAI_API_KEY)
        tts_response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=params["script"],
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(tts_response.content)
            audio_tmp = f.name

        try:
            syncso = SyncSoService()
            job_id_syncso = await syncso.create_lipsync(
                video_url=avatar_video_url,
                audio_path=audio_tmp,
            )

            import time
            deadline = time.time() + 1800
            while time.time() < deadline:
                status_data = await syncso.get_status(job_id_syncso)
                if status_data["status"] == "completed":
                    output_url = status_data.get("output_url", "")
                    async with AsyncSessionLocal() as db:
                        await db.execute(
                            update(Video)
                            .where(Video.id == __import__("uuid").UUID(video_id))
                            .values(status=VideoStatus.COMPLETED, output_url=output_url)
                        )
                        await db.execute(
                            update(VideoJob)
                            .where(VideoJob.video_id == __import__("uuid").UUID(video_id))
                            .values(
                                status=JobStatus.SUCCESS,
                                progress=100,
                                completed_at=datetime.datetime.utcnow(),
                            )
                        )
                        await db.commit()
                    return {"video_id": video_id, "status": "completed", "output_url": output_url}
                elif status_data["status"] == "failed":
                    raise RuntimeError(f"Sync.so failed: {status_data.get('error')}")
                await asyncio.sleep(10)

            raise TimeoutError("Sync.so timed out")
        finally:
            os.unlink(audio_tmp)

    try:
        return asyncio.run(_run())
    except Exception as exc:
        asyncio.run(_mark_failed(video_id, str(exc)))
        raise self.retry(exc=exc, countdown=60)
