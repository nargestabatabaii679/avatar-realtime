"""
app/services/edge_tts_service.py
---------------------------------
Microsoft Edge TTS wrapper — completely free, no API key required.

Uses the same neural TTS engine as Microsoft Edge browser.
Supports 400+ voices including high-quality Persian (Farsi) voices:
  - fa-IR-DilaraNeural  (female, natural)
  - fa-IR-FaridNeural   (male, natural)
"""

from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

# Best Persian voices — in priority order
PERSIAN_VOICES = [
    "fa-IR-DilaraNeural",   # female, warmest
    "fa-IR-FaridNeural",    # male
]

# English fallback voices
ENGLISH_VOICES = [
    "en-US-AriaNeural",
    "en-US-GuyNeural",
]

LANGUAGE_VOICE_MAP: dict[str, list[str]] = {
    "fa": PERSIAN_VOICES,
    "en": ENGLISH_VOICES,
    "ar": ["ar-SA-ZariyahNeural", "ar-SA-HamedNeural"],
    "tr": ["tr-TR-EmelNeural", "tr-TR-AhmetNeural"],
    "de": ["de-DE-KatjaNeural", "de-DE-ConradNeural"],
    "fr": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
    "es": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
    "ru": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"],
    "zh": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
    "ja": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
    "ko": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
    "hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
}


class EdgeTTSService:
    """
    Async wrapper around Microsoft Edge TTS (edge-tts package).

    Completely free — no API key, no rate limits, no account needed.
    """

    @staticmethod
    def _pick_voice(language: str, gender: Literal["female", "male", "any"] = "female") -> str:
        voices = LANGUAGE_VOICE_MAP.get(language, ENGLISH_VOICES)
        if gender == "female":
            return voices[0]
        elif gender == "male" and len(voices) > 1:
            return voices[1]
        return voices[0]

    async def synthesize_to_bytes(
        self,
        text: str,
        language: str = "fa",
        voice: str | None = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
    ) -> bytes:
        """
        Synthesize text to WAV/MP3 bytes.

        Args:
            text:     Text to synthesize.
            language: ISO 639-1 language code (default "fa" for Persian).
            voice:    Override voice name (e.g. "fa-IR-DilaraNeural").
            rate:     Speech rate adjustment, e.g. "+10%" or "-5%".
            pitch:    Pitch adjustment in Hz, e.g. "+5Hz".
            volume:   Volume adjustment, e.g. "+20%".

        Returns:
            Raw MP3 bytes.
        """
        try:
            import edge_tts  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed. Run: pip install edge-tts"
            ) from exc

        selected_voice = voice or self._pick_voice(language)
        communicate = edge_tts.Communicate(
            text=text,
            voice=selected_voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )

        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])

        audio_bytes = buf.getvalue()
        if not audio_bytes:
            raise RuntimeError(f"edge-tts returned empty audio for voice={selected_voice}")

        logger.debug(
            "edge_tts_synthesized",
            voice=selected_voice,
            text_len=len(text),
            bytes=len(audio_bytes),
        )
        return audio_bytes

    async def synthesize_to_file(
        self,
        text: str,
        output_path: str | Path,
        language: str = "fa",
        voice: str | None = None,
        rate: str = "+0%",
    ) -> Path:
        """Synthesize and save to file. Returns the output path."""
        audio_bytes = await self.synthesize_to_bytes(
            text=text, language=language, voice=voice, rate=rate
        )
        path = Path(output_path)
        path.write_bytes(audio_bytes)
        return path

    @staticmethod
    async def list_voices(language: str | None = None) -> list[dict]:
        """List all available voices, optionally filtered by language prefix."""
        try:
            import edge_tts  # noqa: PLC0415
        except ImportError:
            return []

        voices = await edge_tts.list_voices()
        if language:
            prefix = f"{language}-"
            voices = [v for v in voices if v["Locale"].lower().startswith(prefix.lower())]
        return voices


# Module-level singleton
_service: EdgeTTSService | None = None


def get_edge_tts() -> EdgeTTSService:
    global _service
    if _service is None:
        _service = EdgeTTSService()
    return _service
