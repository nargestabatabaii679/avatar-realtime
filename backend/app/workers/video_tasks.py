from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

import structlog

from app.core.celery_app import celery_app
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def _update_job_progress(video_id: str, progress: int, step: str, db_session=None) -> None:
    """Update video job progress in DB and broadcast via Redis."""
    try:
        from app.core.redis_client import get_redis_client
        import json
        import asyncio

        async def _broadcast():
            redis = await get_redis_client()
            await redis.publish(
                f"video_progress:{video_id}",
                json.dumps({"video_id": video_id, "progress": progress, "step": step}),
            )

        asyncio.run(_broadcast())
    except Exception as e:
        logger.warning("progress_broadcast_failed", error=str(e))


@celery_app.task(
    bind=True,
    name="workers.video_tasks.generate_video_task",
    queue="gpu",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=1800,
    time_limit=2400,
)
def generate_video_task(
    self,
    video_id: str,
    avatar_id: str,
    voice_model_id: str,
    script: str,
    language: str,
    resolution: str,
    organization_id: str,
    user_id: str,
    options: Optional[dict] = None,
) -> dict:
    """
    Full video generation pipeline:
    1. Download avatar image from MinIO
    2. Synthesize TTS audio with XTTS-v2
    3. Apply lip sync with LivePortrait / Wav2Lip
    4. Compose final video with FFmpeg
    5. Upload to MinIO, update DB record
    """
    options = options or {}
    log = logger.bind(video_id=video_id, task_id=self.request.id)
    log.info("video_generation_started")

    import asyncio

    async def _run_pipeline():
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import AsyncSessionLocal
        from app.models.video import Video, VideoStatus
        from app.models.video_job import VideoJob, JobStatus
        from sqlalchemy import select, update

        async with AsyncSessionLocal() as db:
            # ---- Mark job as running ----
            await db.execute(
                update(VideoJob)
                .where(VideoJob.video_id == UUID(video_id))
                .values(
                    status=JobStatus.RUNNING,
                    celery_task_id=self.request.id,
                    started_at=__import__("datetime").datetime.utcnow(),
                )
            )
            await db.execute(
                update(Video)
                .where(Video.id == UUID(video_id))
                .values(status=VideoStatus.PROCESSING)
            )
            await db.commit()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            avatar_path = tmp / "avatar.jpg"
            audio_path = tmp / "speech.wav"
            lipsync_path = tmp / "lipsync.mp4"
            final_path = tmp / f"output_{resolution}.mp4"
            thumb_path = tmp / "thumbnail.jpg"

            # ---- Step 1: Download avatar (20%) ----
            _update_job_progress(video_id, 5, "downloading_assets")
            from app.services.storage.minio_service import download_to_path, BUCKETS
            from app.models.avatar import Avatar
            from app.models.voice_model import VoiceModel

            async with AsyncSessionLocal() as db:
                avatar = await db.get(Avatar, UUID(avatar_id))
                voice = await db.get(VoiceModel, UUID(voice_model_id))

            if not avatar or not voice:
                raise ValueError("Avatar or voice model not found")

            # Extract bucket + object_name from stored URL: "bucket/org_id/type/file"
            avatar_obj = "/".join(avatar.source_file_url.split("/")[1:])
            await download_to_path("avatars", avatar_obj, avatar_path)
            _update_job_progress(video_id, 15, "assets_downloaded")

            # ---- Step 2: TTS Synthesis (40%) ----
            _update_job_progress(video_id, 20, "tts_synthesis")

            # Download voice fingerprint from MinIO
            voice_model_obj = "/".join(voice.model_file_url.split("/")[1:])
            voice_fp_path = tmp / "voice_fingerprint.npz"
            await download_to_path("voices", voice_model_obj, voice_fp_path)

            # Load fingerprint
            import numpy as np
            from app.ml.voice.xtts_engine import VoiceFingerprint, XTTSEngine
            fp_data = np.load(str(voice_fp_path), allow_pickle=True)
            fingerprint = VoiceFingerprint(
                speaker_embedding=fp_data["speaker_embedding"],
                gpt_cond_latent=fp_data["gpt_cond_latent"],
                language=language,
            )

            tts_start = time.time()

            if language == "fa":
                # Use Persian-optimised synthesizer
                from app.ml.voice.persian_tts import get_persian_synthesizer
                synth = get_persian_synthesizer()
                audio_array = synth.synthesize(
                    text=script,
                    fingerprint=fingerprint,
                    speed=options.get("speed", 1.0),
                    language="fa",
                )
                wav_bytes = synth.to_wav_bytes(audio_array)
                audio_path.write_bytes(wav_bytes)
            else:
                engine_xtts = XTTSEngine.get_instance()
                result = engine_xtts.synthesize(
                    text=script,
                    fingerprint=fingerprint,
                    language=language,
                    speed=options.get("speed", 1.0),
                )
                if result.success:
                    audio_path.write_bytes(result.to_wav_bytes())
                else:
                    raise RuntimeError(f"TTS failed: {result.error}")

            log.info("tts_completed", duration_ms=int((time.time() - tts_start) * 1000))
            _update_job_progress(video_id, 40, "tts_completed")

            # ---- Step 3: Ultra-Natural Lip Sync (70%) ----
            _update_job_progress(video_id, 42, "lip_sync_started")

            import cv2
            import soundfile as sf
            from app.ml.avatar.ultra_lipsync import (
                UltraLipSyncPipeline, UltraLipSyncConfig, FaceAnalyzer, synthesize_ultra_natural
            )
            from app.utils.video_utils import frames_to_video

            source_image = cv2.imread(str(avatar_path))
            audio_array, audio_sr = sf.read(str(audio_path), dtype="float32")
            if audio_array.ndim > 1:
                audio_array = audio_array[:, 0]  # mono

            lipsync_config = UltraLipSyncConfig(
                fps=25.0,
                upsample_fps=True,                # 50fps output
                use_poisson_blend=True,           # seamless blending
                temporal_smooth_alpha=0.6,
                enable_eye_blinks=True,
                enable_micro_expressions=True,
                micro_expression_strength=0.55,
            )

            lipsync_frames = synthesize_ultra_natural(
                source_image=source_image,
                audio=audio_array,
                audio_sr=audio_sr,
                config=lipsync_config,
            )

            output_fps = 50 if lipsync_config.upsample_fps else 25
            await frames_to_video(lipsync_frames, str(audio_path), str(lipsync_path), fps=output_fps)
            log.info("ultra_lipsync_completed", frames=len(lipsync_frames), fps=output_fps)
            _update_job_progress(video_id, 70, "lip_sync_completed")

            # ---- Step 4: FFmpeg Render (90%) ----
            _update_job_progress(video_id, 72, "rendering")
            from app.utils.video_utils import render_final_video, extract_thumbnail

            await render_final_video(
                input_path=str(lipsync_path),
                audio_path=str(audio_path),
                output_path=str(final_path),
                resolution=resolution,
                options=options,
            )

            await extract_thumbnail(str(final_path), str(thumb_path))
            _update_job_progress(video_id, 88, "rendering_completed")

            # ---- Step 5: Upload to MinIO (100%) ----
            _update_job_progress(video_id, 90, "uploading")
            from app.services.storage.minio_service import upload_file_path

            video_object = f"{organization_id}/videos/{video_id}_{resolution}.mp4"
            thumb_object = f"{organization_id}/thumbnails/{video_id}_thumb.jpg"

            await upload_file_path("videos", video_object, final_path, "video/mp4")
            await upload_file_path("thumbnails", thumb_object, thumb_path, "image/jpeg")

            # ---- Update DB ----
            from app.models.video import VideoStatus
            import datetime

            stat = final_path.stat()
            duration = await _get_video_duration(str(final_path))

            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Video)
                    .where(Video.id == UUID(video_id))
                    .values(
                        status=VideoStatus.COMPLETED,
                        output_url=f"videos/{video_object}",
                        thumbnail_url=f"thumbnails/{thumb_object}",
                        file_size_bytes=stat.st_size,
                        duration_seconds=duration,
                    )
                )
                await db.execute(
                    update(VideoJob)
                    .where(VideoJob.video_id == UUID(video_id))
                    .values(
                        status=JobStatus.COMPLETED,
                        progress=100,
                        completed_at=datetime.datetime.utcnow(),
                    )
                )
                await db.commit()

            _update_job_progress(video_id, 100, "completed")
            log.info("video_generation_completed", object=video_object)

            # Track analytics event
            await _track_video_event(video_id, organization_id, user_id, duration, stat.st_size)

            return {
                "video_id": video_id,
                "status": "completed",
                "output_url": video_object,
                "duration_seconds": duration,
                "file_size_bytes": stat.st_size,
            }

    try:
        return asyncio.run(_run_pipeline())
    except Exception as exc:
        log.error("video_generation_failed", error=str(exc), exc_info=True)
        asyncio.run(_mark_failed(video_id, str(exc)))
        raise self.retry(exc=exc, countdown=30)


async def _get_video_duration(path: str) -> float:
    import subprocess, json
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        capture_output=True, text=True,
    )
    try:
        info = json.loads(result.stdout)
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    return 0.0


async def _mark_failed(video_id: str, error: str) -> None:
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.video import Video, VideoStatus
        from app.models.video_job import VideoJob, JobStatus
        from sqlalchemy import update
        import datetime

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Video)
                .where(Video.id == __import__("uuid").UUID(video_id))
                .values(status=VideoStatus.FAILED, error_message=error[:500])
            )
            await db.execute(
                update(VideoJob)
                .where(VideoJob.video_id == __import__("uuid").UUID(video_id))
                .values(
                    status=JobStatus.FAILED,
                    completed_at=datetime.datetime.utcnow(),
                )
            )
            await db.commit()
    except Exception as e:
        logger.error("mark_failed_error", error=str(e))


async def _track_video_event(
    video_id: str, org_id: str, user_id: str, duration: float, size: int
) -> None:
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.analytics import AnalyticsEvent
        import datetime

        async with AsyncSessionLocal() as db:
            event = AnalyticsEvent(
                organization_id=__import__("uuid").UUID(org_id),
                user_id=__import__("uuid").UUID(user_id),
                event_type="video_generated",
                entity_type="video",
                entity_id=__import__("uuid").UUID(video_id),
                metrics={"duration_seconds": duration, "file_size_bytes": size},
                timestamp=datetime.datetime.utcnow(),
            )
            db.add(event)
            await db.commit()
    except Exception as e:
        logger.warning("analytics_track_failed", error=str(e))
