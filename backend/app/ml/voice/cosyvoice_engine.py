"""
ml/voice/cosyvoice_engine.py
-----------------------------
CosyVoice voice cloning and synthesis engine — alternative to XTTS-v2.

Features:
- Singleton model initialisation (lazy loading)
- Zero-shot voice cloning from reference audio
- Cross-lingual synthesis (speak in a different language while keeping voice)
- Instruct mode for fine-grained emotion and style control
- Streaming audio generation
- Automatic language detection via langdetect
- Async wrappers for FastAPI event loop safety
"""

from __future__ import annotations

import asyncio
import io
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cosyvoice")

COSYVOICE_SAMPLE_RATE = 22050


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class CosyVoiceResult:
    audio: np.ndarray | None = None        # float32, COSYVOICE_SAMPLE_RATE Hz
    sample_rate: int = COSYVOICE_SAMPLE_RATE
    duration_seconds: float = 0.0
    inference_ms: float = 0.0
    language: str = "en"
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.audio is not None

    def to_wav_bytes(self) -> bytes:
        if self.audio is None:
            return b""
        try:
            import soundfile as sf  # noqa: PLC0415

            buf = io.BytesIO()
            sf.write(buf, self.audio, self.sample_rate, format="WAV", subtype="PCM_16")
            return buf.getvalue()
        except ImportError:
            from scipy.io.wavfile import write as wav_write  # noqa: PLC0415

            buf = io.BytesIO()
            pcm = (self.audio * 32767).astype(np.int16)
            wav_write(buf, self.sample_rate, pcm)
            return buf.getvalue()


@dataclass
class CosyVoiceProfile:
    """Reference voice profile used for zero-shot cloning."""

    prompt_audio: np.ndarray          # reference audio float32 array
    prompt_text: str = ""             # transcript of reference audio
    language: str = "en"
    source_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# CosyVoice engine singleton
# ──────────────────────────────────────────────────────────────────────────────


class CosyVoiceEngine:
    """
    Wrapper around the CosyVoice model family.

    Supported modes:
    - ``zero_shot``: Clone voice from a reference clip without transcription.
    - ``cross_lingual``: Speak in target language using source voice.
    - ``instruct``: Control style/emotion via a natural-language instruction.
    - ``sft`` (supervised fine-tune): Use a pre-trained speaker style.

    Usage::

        engine = CosyVoiceEngine.get_instance()
        profile = engine.create_voice_profile(audio_path, prompt_text="Hello")
        result = engine.zero_shot_synthesize("مرحبا", profile)
    """

    _instance: "CosyVoiceEngine | None" = None

    def __init__(self, model_dir: Path, device: str = "cuda") -> None:
        self._model_dir = Path(model_dir)
        self._device = device
        self._model: Any = None
        self._initialized = False

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "CosyVoiceEngine":
        if cls._instance is None:
            from app.core.config import settings  # noqa: PLC0415

            model_dir = settings.MODELS_BASE_DIR / "CosyVoice"
            device = "cuda" if settings.USE_GPU else "cpu"
            cls._instance = cls(model_dir=model_dir, device=device)
            cls._instance._load()
        return cls._instance

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._initialized:
            return
        t0 = time.perf_counter()
        try:
            import sys  # noqa: PLC0415

            sys.path.insert(0, str(self._model_dir))
            from cosyvoice.cli.cosyvoice import CosyVoice  # type: ignore[import]  # noqa: PLC0415

            model_name = "CosyVoice2-0.5B"
            model_path = self._model_dir / model_name
            if not model_path.exists():
                model_path = self._model_dir  # try root

            self._model = CosyVoice(str(model_path), load_jit=False, load_onnx=False)
            elapsed = (time.perf_counter() - t0) * 1000
            self._initialized = True
            logger.info(
                "cosyvoice_loaded",
                model_dir=str(self._model_dir),
                device=self._device,
                load_ms=round(elapsed, 1),
            )
        except ImportError as exc:
            logger.warning("cosyvoice_not_available", error=str(exc))
            self._initialized = True  # stub mode
        except Exception as exc:
            logger.error("cosyvoice_load_failed", error=str(exc))
            raise

    # ── Public API ────────────────────────────────────────────────────────────

    def create_voice_profile(
        self,
        reference_audio_path: str | Path,
        prompt_text: str = "",
        language: str | None = None,
    ) -> CosyVoiceProfile:
        """
        Build a CosyVoiceProfile from a reference audio clip.

        Args:
            reference_audio_path: Path to a reference WAV/MP3 file.
            prompt_text: Optional verbatim transcript of the reference audio.
            language: Language code; auto-detected if omitted.

        Returns:
            CosyVoiceProfile ready for synthesis.
        """
        audio_path = Path(reference_audio_path)
        audio = self._load_audio(audio_path)
        lang = language or self._detect_language(prompt_text)
        return CosyVoiceProfile(
            prompt_audio=audio,
            prompt_text=prompt_text,
            language=lang,
            source_path=str(audio_path),
        )

    def zero_shot_synthesize(
        self,
        text: str,
        profile: CosyVoiceProfile,
        speed: float = 1.0,
    ) -> CosyVoiceResult:
        """
        Zero-shot voice cloning synthesis.

        Args:
            text: Target text to synthesise.
            profile: Voice profile from ``create_voice_profile()``.
            speed: Playback speed multiplier.

        Returns:
            CosyVoiceResult with audio array.
        """
        t0 = time.perf_counter()
        result = CosyVoiceResult(language=profile.language)

        try:
            if self._model is None:
                logger.warning("cosyvoice_stub_zero_shot")
                result.audio = np.zeros(COSYVOICE_SAMPLE_RATE, dtype=np.float32)
                result.duration_seconds = 1.0
                return result

            import torch  # noqa: PLC0415

            ref_tensor = torch.FloatTensor(profile.prompt_audio).unsqueeze(0)
            audio_segments: list[np.ndarray] = []

            for seg in self._model.inference_zero_shot(
                text,
                profile.prompt_text,
                ref_tensor,
                speed=speed,
                stream=False,
            ):
                audio_segments.append(seg["tts_speech"].squeeze().numpy())

            audio = np.concatenate(audio_segments) if audio_segments else np.zeros(
                COSYVOICE_SAMPLE_RATE, dtype=np.float32
            )
            result.audio = self._normalize_audio(audio)
            result.duration_seconds = len(result.audio) / COSYVOICE_SAMPLE_RATE
            result.inference_ms = (time.perf_counter() - t0) * 1000

            logger.info(
                "cosyvoice_zero_shot_done",
                language=profile.language,
                duration_s=round(result.duration_seconds, 2),
                inference_ms=round(result.inference_ms, 1),
            )

        except Exception as exc:
            logger.error("cosyvoice_zero_shot_error", error=str(exc), exc_info=True)
            result.error = str(exc)

        return result

    def cross_lingual_synthesize(
        self,
        text: str,
        target_language: str,
        profile: CosyVoiceProfile,
        speed: float = 1.0,
    ) -> CosyVoiceResult:
        """
        Cross-lingual synthesis — speak in a different language with the source voice.

        Args:
            text: Target text in ``target_language``.
            target_language: BCP-47 language code for the output language.
            profile: Source voice profile.
            speed: Playback speed multiplier.
        """
        t0 = time.perf_counter()
        result = CosyVoiceResult(language=target_language)

        try:
            if self._model is None:
                logger.warning("cosyvoice_stub_cross_lingual")
                result.audio = np.zeros(COSYVOICE_SAMPLE_RATE, dtype=np.float32)
                result.duration_seconds = 1.0
                return result

            import torch  # noqa: PLC0415

            ref_tensor = torch.FloatTensor(profile.prompt_audio).unsqueeze(0)
            audio_segments: list[np.ndarray] = []

            for seg in self._model.inference_cross_lingual(
                text,
                ref_tensor,
                speed=speed,
                stream=False,
            ):
                audio_segments.append(seg["tts_speech"].squeeze().numpy())

            audio = np.concatenate(audio_segments) if audio_segments else np.zeros(
                COSYVOICE_SAMPLE_RATE, dtype=np.float32
            )
            result.audio = self._normalize_audio(audio)
            result.duration_seconds = len(result.audio) / COSYVOICE_SAMPLE_RATE
            result.inference_ms = (time.perf_counter() - t0) * 1000

            logger.info(
                "cosyvoice_cross_lingual_done",
                target_language=target_language,
                duration_s=round(result.duration_seconds, 2),
            )

        except Exception as exc:
            logger.error("cosyvoice_cross_lingual_error", error=str(exc), exc_info=True)
            result.error = str(exc)

        return result

    def instruct_synthesize(
        self,
        text: str,
        instruction: str,
        profile: CosyVoiceProfile,
        speed: float = 1.0,
    ) -> CosyVoiceResult:
        """
        Instruct-mode synthesis with emotion / style control.

        Args:
            text: Text to synthesise.
            instruction: Natural-language style instruction e.g. "Speak calmly and slowly".
            profile: Source voice profile.
            speed: Playback speed multiplier.
        """
        t0 = time.perf_counter()
        result = CosyVoiceResult(language=profile.language)

        try:
            if self._model is None:
                logger.warning("cosyvoice_stub_instruct")
                result.audio = np.zeros(COSYVOICE_SAMPLE_RATE, dtype=np.float32)
                result.duration_seconds = 1.0
                return result

            import torch  # noqa: PLC0415

            ref_tensor = torch.FloatTensor(profile.prompt_audio).unsqueeze(0)
            audio_segments: list[np.ndarray] = []

            for seg in self._model.inference_instruct2(
                text,
                instruction,
                ref_tensor,
                speed=speed,
                stream=False,
            ):
                audio_segments.append(seg["tts_speech"].squeeze().numpy())

            audio = np.concatenate(audio_segments) if audio_segments else np.zeros(
                COSYVOICE_SAMPLE_RATE, dtype=np.float32
            )
            result.audio = self._normalize_audio(audio)
            result.duration_seconds = len(result.audio) / COSYVOICE_SAMPLE_RATE
            result.inference_ms = (time.perf_counter() - t0) * 1000

        except Exception as exc:
            logger.error("cosyvoice_instruct_error", error=str(exc), exc_info=True)
            result.error = str(exc)

        return result

    def streaming_synthesize(
        self,
        text: str,
        profile: CosyVoiceProfile,
        mode: str = "zero_shot",
        instruction: str = "",
        speed: float = 1.0,
    ) -> Iterator[np.ndarray]:
        """
        Streaming synthesis — yield audio segments as they arrive.

        Args:
            text: Input text.
            profile: Voice profile.
            mode: One of ``"zero_shot"``, ``"cross_lingual"``, ``"instruct"``.
            instruction: Only used in ``"instruct"`` mode.
            speed: Speed multiplier.

        Yields:
            float32 numpy audio chunks.
        """
        if self._model is None:
            yield np.zeros(2048, dtype=np.float32)
            return

        import torch  # noqa: PLC0415

        ref_tensor = torch.FloatTensor(profile.prompt_audio).unsqueeze(0)
        try:
            if mode == "zero_shot":
                gen = self._model.inference_zero_shot(
                    text, profile.prompt_text, ref_tensor, speed=speed, stream=True
                )
            elif mode == "cross_lingual":
                gen = self._model.inference_cross_lingual(
                    text, ref_tensor, speed=speed, stream=True
                )
            else:  # instruct
                gen = self._model.inference_instruct2(
                    text, instruction, ref_tensor, speed=speed, stream=True
                )

            for seg in gen:
                yield seg["tts_speech"].squeeze().cpu().numpy().astype(np.float32)

        except Exception as exc:
            logger.error("cosyvoice_stream_error", error=str(exc), exc_info=True)
            raise

    # ── Async wrappers ────────────────────────────────────────────────────────

    @classmethod
    async def async_zero_shot(
        cls,
        text: str,
        profile: CosyVoiceProfile,
        speed: float = 1.0,
    ) -> CosyVoiceResult:
        loop = asyncio.get_event_loop()
        engine = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: engine.zero_shot_synthesize(text, profile, speed=speed),
        )

    @classmethod
    async def async_cross_lingual(
        cls,
        text: str,
        target_language: str,
        profile: CosyVoiceProfile,
    ) -> CosyVoiceResult:
        loop = asyncio.get_event_loop()
        engine = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: engine.cross_lingual_synthesize(text, target_language, profile),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _load_audio(path: Path, target_sr: int = COSYVOICE_SAMPLE_RATE) -> np.ndarray:
        try:
            import librosa  # noqa: PLC0415

            audio, _ = librosa.load(str(path), sr=target_sr, mono=True)
            return audio.astype(np.float32)
        except ImportError:
            import soundfile as sf  # noqa: PLC0415

            audio, sr = sf.read(str(path), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            return audio

    @staticmethod
    def _normalize_audio(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 1e-8:
            return audio
        target_rms = 10 ** (target_db / 20.0)
        return np.clip(audio * (target_rms / rms), -1.0, 1.0).astype(np.float32)

    @staticmethod
    def _detect_language(text: str) -> str:
        if not text:
            return "en"
        try:
            from langdetect import detect  # noqa: PLC0415

            return detect(text)
        except Exception:
            return "en"
