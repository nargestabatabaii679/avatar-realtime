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
    name="workers.voice_tasks.clone_voice_task",
    queue="gpu",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=600,
    time_limit=720,
)
def clone_voice_task(
    self,
    voice_model_id: str,
    sample_urls: list[str],
    language: str,
    organization_id: str,
    tts_engine: str = "xtts",
) -> dict:
    """Clone a voice from audio samples using XTTS-v2."""
    log = logger.bind(voice_model_id=voice_model_id, engine=tts_engine)
    log.info("voice_cloning_started")

    async def _clone():
        from app.core.database import AsyncSessionLocal
        from app.models.voice_model import VoiceModel, VoiceModelStatus
        from app.services.storage.minio_service import download_to_path, upload_file_path
        from sqlalchemy import update

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sample_paths: list[str] = []

            # Download all samples
            for i, url in enumerate(sample_urls):
                ext = Path(url).suffix or ".wav"
                dest = tmp / f"sample_{i}{ext}"
                obj = "/".join(url.split("/")[1:])
                await download_to_path("voices", obj, dest)
                sample_paths.append(str(dest))

            # Run voice cloning
            output_model_path = tmp / "voice_model.pth"

            if tts_engine == "xtts":
                from app.ml.voice.xtts_engine import XTTSEngine
                engine = XTTSEngine()
                await engine.clone_voice(
                    sample_paths=sample_paths,
                    language=language,
                    output_path=str(output_model_path),
                )
            elif tts_engine == "cosyvoice":
                from app.ml.voice.cosyvoice_engine import CosyVoiceEngine
                engine = CosyVoiceEngine()
                await engine.clone_voice(
                    sample_paths=sample_paths,
                    language=language,
                    output_path=str(output_model_path),
                )
            else:
                raise ValueError(f"Unsupported TTS engine: {tts_engine}")

            # Upload model file
            model_object = f"{organization_id}/voices/{voice_model_id}/model.pth"
            await upload_file_path("voices", model_object, output_model_path, "application/octet-stream")

            # Generate test audio sample
            test_audio_path = tmp / "test_sample.wav"
            test_texts = {
                "fa": "سلام، این یک نمونه صدای کلون شده است.",
                "en": "Hello, this is a cloned voice sample.",
                "ar": "مرحباً، هذا مثال على الصوت المستنسخ.",
                "tr": "Merhaba, bu klonlanmış bir ses örneğidir.",
                "fr": "Bonjour, ceci est un exemple de voix clonée.",
                "de": "Hallo, dies ist ein geklontes Sprachbeispiel.",
            }
            test_text = test_texts.get(language, test_texts["en"])

            if hasattr(engine, "synthesize"):
                await engine.synthesize(
                    text=test_text,
                    language=language,
                    voice_model_path=str(output_model_path),
                    output_path=str(test_audio_path),
                )

            sample_object = f"{organization_id}/voices/{voice_model_id}/test_sample.wav"
            if test_audio_path.exists():
                await upload_file_path("voices", sample_object, test_audio_path, "audio/wav")

            # Update DB
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(VoiceModel)
                    .where(VoiceModel.id == UUID(voice_model_id))
                    .values(
                        status=VoiceModelStatus.READY,
                        model_file_url=f"voices/{model_object}",
                        metadata={
                            "tts_engine": tts_engine,
                            "sample_count": len(sample_paths),
                            "test_sample_url": f"voices/{sample_object}",
                        },
                    )
                )
                await db.commit()

            log.info("voice_cloning_completed")
            return {"voice_model_id": voice_model_id, "status": "ready", "model_url": model_object}

    try:
        return asyncio.run(_clone())
    except Exception as exc:
        log.error("voice_cloning_failed", error=str(exc), exc_info=True)
        asyncio.run(_mark_voice_failed(voice_model_id, str(exc)))
        raise self.retry(exc=exc, countdown=30)


async def _mark_voice_failed(voice_model_id: str, error: str) -> None:
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.voice_model import VoiceModel, VoiceModelStatus
        from sqlalchemy import update

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(VoiceModel)
                .where(VoiceModel.id == UUID(voice_model_id))
                .values(status=VoiceModelStatus.FAILED, metadata={"error": error[:200]})
            )
            await db.commit()
    except Exception:
        pass
