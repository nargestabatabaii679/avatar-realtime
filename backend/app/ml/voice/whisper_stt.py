"""
ml/voice/whisper_stt.py
------------------------
Whisper Large V3 speech-to-text engine using faster-whisper for optimised inference.

Features:
- Singleton model loading (faster-whisper CTranslate2 backend)
- Transcription with automatic language detection
- Word-level timestamp extraction
- Real-time streaming transcription from audio chunks
- VAD (Voice Activity Detection) integration via silero-vad
- Persian / Arabic / multilingual support
- Per-segment confidence scoring
- Async wrappers for FastAPI event loop safety
"""

from __future__ import annotations

import asyncio
import io
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="whisper_stt")

WHISPER_SAMPLE_RATE = 16000  # Whisper always expects 16 kHz mono


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class WordTimestamp:
    word: str
    start: float       # seconds
    end: float         # seconds
    confidence: float  # 0-1


@dataclass
class TranscriptionSegment:
    text: str
    start: float
    end: float
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    words: list[WordTimestamp] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        """Estimate confidence from log-probability."""
        return float(np.exp(self.avg_logprob))


@dataclass
class TranscriptionResult:
    text: str = ""
    language: str = "en"
    language_probability: float = 0.0
    segments: list[TranscriptionSegment] = field(default_factory=list)
    duration_seconds: float = 0.0
    inference_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def word_count(self) -> int:
        return len(self.text.split())


# ──────────────────────────────────────────────────────────────────────────────
# WhisperSTT singleton
# ──────────────────────────────────────────────────────────────────────────────


class WhisperSTT:
    """
    Speech-to-text engine backed by faster-whisper.

    Usage::

        stt = WhisperSTT.get_instance()
        result = stt.transcribe(audio_bytes)
        # or
        result = await WhisperSTT.async_transcribe(audio_path)
    """

    _instance: "WhisperSTT | None" = None

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        download_root: Path | None = None,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._download_root = download_root
        self._model: Any = None
        self._vad_model: Any = None
        self._initialized = False

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "WhisperSTT":
        if cls._instance is None:
            from app.core.config import settings  # noqa: PLC0415

            device = settings.WHISPER_DEVICE if settings.USE_GPU else "cpu"
            compute_type = settings.WHISPER_COMPUTE_TYPE if settings.USE_GPU else "int8"
            cls._instance = cls(
                model_size=settings.WHISPER_MODEL_SIZE,
                device=device,
                compute_type=compute_type,
                download_root=settings.WHISPER_DOWNLOAD_DIR,
            )
            cls._instance._load()
        return cls._instance

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._initialized:
            return
        t0 = time.perf_counter()
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]  # noqa: PLC0415

            download_dir = str(self._download_root) if self._download_root else None
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=download_dir,
                num_workers=2,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            self._initialized = True
            logger.info(
                "whisper_loaded",
                model_size=self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                load_ms=round(elapsed, 1),
            )
            self._load_vad()
        except ImportError as exc:
            logger.warning("faster_whisper_not_available", error=str(exc))
            self._initialized = True  # stub mode
        except Exception as exc:
            logger.error("whisper_load_failed", error=str(exc))
            raise

    def _load_vad(self) -> None:
        """Load Silero VAD model for voice activity detection."""
        try:
            import torch  # noqa: PLC0415

            vad_model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )
            self._vad_model = vad_model
            logger.info("silero_vad_loaded")
        except Exception as exc:
            logger.warning("silero_vad_not_available", error=str(exc))

    # ── Public API ────────────────────────────────────────────────────────────

    def transcribe(
        self,
        audio: bytes | np.ndarray | str | Path,
        language: str | None = None,
        task: str = "transcribe",
        word_timestamps: bool = True,
        vad_filter: bool = True,
        vad_threshold: float = 0.4,
        beam_size: int = 5,
        best_of: int = 5,
        initial_prompt: str | None = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio: Raw WAV bytes, float32 numpy array at 16 kHz, or file path.
            language: Force language (e.g. ``"fa"`` for Persian). Auto-detect if None.
            task: ``"transcribe"`` or ``"translate"`` (to English).
            word_timestamps: Extract per-word start/end timestamps.
            vad_filter: Apply VAD to remove silence before transcription.
            vad_threshold: VAD speech probability threshold (0-1).
            beam_size: Beam search width (higher = more accurate, slower).
            best_of: Number of candidates in sampling (used when temperature > 0).
            initial_prompt: Optional text hint to guide transcription style.

        Returns:
            TranscriptionResult with full text, segments, and word timestamps.
        """
        t0 = time.perf_counter()
        result = TranscriptionResult()

        try:
            audio_np = self._to_float32_audio(audio)

            if self._model is None:
                logger.warning("whisper_stub_transcribe")
                result.text = "[stub transcription]"
                result.language = language or "en"
                return result

            segments_gen, info = self._model.transcribe(
                audio_np,
                language=language,
                task=task,
                word_timestamps=word_timestamps,
                vad_filter=vad_filter and self._vad_model is not None,
                vad_parameters={"threshold": vad_threshold},
                beam_size=beam_size,
                best_of=best_of,
                initial_prompt=initial_prompt,
            )

            result.language = info.language
            result.language_probability = float(info.language_probability)
            result.duration_seconds = float(info.duration)

            segments: list[TranscriptionSegment] = []
            full_text_parts: list[str] = []

            for seg in segments_gen:
                words: list[WordTimestamp] = []
                if word_timestamps and seg.words:
                    for w in seg.words:
                        words.append(
                            WordTimestamp(
                                word=w.word,
                                start=float(w.start),
                                end=float(w.end),
                                confidence=float(np.exp(w.probability)) if hasattr(w, "probability") else 0.0,
                            )
                        )

                ts = TranscriptionSegment(
                    text=seg.text.strip(),
                    start=float(seg.start),
                    end=float(seg.end),
                    avg_logprob=float(seg.avg_logprob),
                    no_speech_prob=float(seg.no_speech_prob),
                    words=words,
                )
                segments.append(ts)
                full_text_parts.append(ts.text)

            result.segments = segments
            result.text = " ".join(full_text_parts)
            result.inference_ms = (time.perf_counter() - t0) * 1000

            logger.info(
                "whisper_transcribe_done",
                language=result.language,
                lang_prob=round(result.language_probability, 2),
                segments=len(segments),
                word_count=result.word_count,
                inference_ms=round(result.inference_ms, 1),
            )

        except Exception as exc:
            logger.error("whisper_transcribe_error", error=str(exc), exc_info=True)
            result.error = str(exc)

        return result

    def transcribe_streaming(
        self,
        audio_chunk_iter: Iterator[np.ndarray],
        language: str | None = None,
        chunk_duration_seconds: float = 5.0,
    ) -> Iterator[TranscriptionResult]:
        """
        Real-time streaming transcription.

        Accumulates audio chunks until ``chunk_duration_seconds`` of audio is
        collected, then transcribes and yields a result. Designed for WebSocket
        and WebRTC use cases.

        Args:
            audio_chunk_iter: Iterator of float32 audio chunks at 16 kHz.
            language: Force language code.
            chunk_duration_seconds: How many seconds of audio to batch before transcribing.

        Yields:
            TranscriptionResult for each accumulated chunk.
        """
        chunk_samples = int(WHISPER_SAMPLE_RATE * chunk_duration_seconds)
        buffer: list[np.ndarray] = []
        buffer_len = 0

        for chunk in audio_chunk_iter:
            buffer.append(chunk)
            buffer_len += len(chunk)

            if buffer_len >= chunk_samples:
                audio_segment = np.concatenate(buffer).astype(np.float32)
                yield self.transcribe(audio_segment, language=language, word_timestamps=False)
                buffer = []
                buffer_len = 0

        # Flush remaining audio
        if buffer:
            audio_segment = np.concatenate(buffer).astype(np.float32)
            if len(audio_segment) > WHISPER_SAMPLE_RATE // 2:  # at least 0.5 s
                yield self.transcribe(audio_segment, language=language, word_timestamps=False)

    def detect_language(self, audio: bytes | np.ndarray | str | Path) -> tuple[str, float]:
        """
        Detect the spoken language without full transcription.

        Returns:
            Tuple of (language_code, probability).
        """
        if self._model is None:
            return ("en", 0.0)

        audio_np = self._to_float32_audio(audio)
        # Use only first 30 s for language detection
        audio_np = audio_np[: WHISPER_SAMPLE_RATE * 30]

        _, info = self._model.transcribe(
            audio_np,
            task="transcribe",
            beam_size=1,
            word_timestamps=False,
        )
        return (info.language, float(info.language_probability))

    def apply_vad(
        self, audio: np.ndarray, threshold: float = 0.4
    ) -> list[tuple[float, float]]:
        """
        Run VAD and return speech segments as (start_sec, end_sec) pairs.

        Args:
            audio: float32 numpy array at 16 kHz.
            threshold: Speech probability threshold.
        """
        if self._vad_model is None:
            return [(0.0, len(audio) / WHISPER_SAMPLE_RATE)]

        try:
            import torch  # noqa: PLC0415
            from silero_vad import get_speech_timestamps  # type: ignore[import]  # noqa: PLC0415

            tensor = torch.FloatTensor(audio)
            timestamps = get_speech_timestamps(
                tensor,
                self._vad_model,
                threshold=threshold,
                sampling_rate=WHISPER_SAMPLE_RATE,
                return_seconds=True,
            )
            return [(t["start"], t["end"]) for t in timestamps]
        except Exception as exc:
            logger.warning("vad_apply_error", error=str(exc))
            return [(0.0, len(audio) / WHISPER_SAMPLE_RATE)]

    # ── Async wrappers ────────────────────────────────────────────────────────

    @classmethod
    async def async_transcribe(
        cls,
        audio: bytes | np.ndarray | str | Path,
        language: str | None = None,
        word_timestamps: bool = True,
    ) -> TranscriptionResult:
        loop = asyncio.get_event_loop()
        stt = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: stt.transcribe(audio, language=language, word_timestamps=word_timestamps),
        )

    @classmethod
    async def async_detect_language(
        cls, audio: bytes | np.ndarray | str | Path
    ) -> tuple[str, float]:
        loop = asyncio.get_event_loop()
        stt = cls.get_instance()
        return await loop.run_in_executor(_EXECUTOR, lambda: stt.detect_language(audio))

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _to_float32_audio(
        audio: bytes | np.ndarray | str | Path,
    ) -> np.ndarray:
        """Convert any audio input to float32 numpy at 16 kHz mono."""
        if isinstance(audio, np.ndarray):
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            return audio.astype(np.float32)

        if isinstance(audio, (str, Path)):
            try:
                import librosa  # noqa: PLC0415

                wav, _ = librosa.load(str(audio), sr=WHISPER_SAMPLE_RATE, mono=True)
                return wav.astype(np.float32)
            except ImportError:
                import soundfile as sf  # noqa: PLC0415

                wav, sr = sf.read(str(audio), dtype="float32")
                if wav.ndim > 1:
                    wav = wav.mean(axis=1)
                if sr != WHISPER_SAMPLE_RATE:
                    raise ValueError(
                        f"Audio must be at {WHISPER_SAMPLE_RATE} Hz, got {sr} Hz. "
                        "Install librosa for automatic resampling."
                    )
                return wav

        if isinstance(audio, (bytes, bytearray, memoryview)):
            try:
                import librosa  # noqa: PLC0415

                wav, _ = librosa.load(io.BytesIO(bytes(audio)), sr=WHISPER_SAMPLE_RATE, mono=True)
                return wav.astype(np.float32)
            except ImportError:
                import soundfile as sf  # noqa: PLC0415

                wav, sr = sf.read(io.BytesIO(bytes(audio)), dtype="float32")
                if wav.ndim > 1:
                    wav = wav.mean(axis=1)
                return wav.astype(np.float32)

        raise TypeError(f"Unsupported audio type: {type(audio)}")
