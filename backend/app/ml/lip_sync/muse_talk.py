"""
ml/lip_sync/muse_talk.py
-------------------------
MuseTalk real-time lip synchronisation module.

Features:
- UNet + VAE + audio encoder model loading (lazy singleton)
- Real-time lip sync from 20 ms audio chunks (<500 ms target latency)
- Double-buffered frame queue for smooth streaming
- Memory-efficient streaming inference without storing full audio
- WebRTC integration helpers (frame timestamp alignment)
- Batch inference mode for offline generation
- GPU memory monitoring and proactive cache eviction
- Async wrappers for FastAPI / WebSocket handlers
"""

from __future__ import annotations

import asyncio
import gc
import queue
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="musetalk")

TARGET_LATENCY_MS = 500.0
MUSETALK_FPS = 25
MUSETALK_AUDIO_SR = 16000
MUSETALK_FACE_SIZE = (256, 256)       # MuseTalk input resolution
MUSETALK_LATENT_SIZE = (32, 32)


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class MuseTalkFrame:
    """A single lip-synced output frame."""

    frame: np.ndarray              # BGR uint8
    timestamp_ms: float = 0.0
    latency_ms: float = 0.0


@dataclass
class MuseTalkResult:
    frames: list[MuseTalkFrame] = field(default_factory=list)
    fps: float = float(MUSETALK_FPS)
    duration_seconds: float = 0.0
    avg_latency_ms: float = 0.0
    inference_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.frames) > 0

    @property
    def bgr_frames(self) -> list[np.ndarray]:
        return [f.frame for f in self.frames]


# ──────────────────────────────────────────────────────────────────────────────
# MuseTalk model wrapper
# ──────────────────────────────────────────────────────────────────────────────


class MuseTalkSyncer:
    """
    Singleton wrapper around the MuseTalk real-time lip-sync pipeline.

    Example::

        syncer = MuseTalkSyncer.get_instance()
        result = syncer.sync_batch(face_image_bgr, audio_array)
    """

    _instance: "MuseTalkSyncer | None" = None

    def __init__(self, model_dir: Path, device: str = "cuda") -> None:
        self._model_dir = Path(model_dir)
        self._device = device
        # Sub-models
        self._unet: Any = None
        self._vae: Any = None
        self._audio_encoder: Any = None
        self._whisper: Any = None
        self._face_detector: Any = None
        self._initialized = False

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "MuseTalkSyncer":
        if cls._instance is None:
            from app.core.config import settings  # noqa: PLC0415

            device = "cuda" if settings.USE_GPU else "cpu"
            cls._instance = cls(model_dir=settings.MUSETALK_MODEL_DIR, device=device)
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

            from musetalk.models.unet import UNet  # type: ignore[import]  # noqa: PLC0415
            from musetalk.models.vae import VAE  # type: ignore[import]  # noqa: PLC0415
            from musetalk.models.audio_encoder import AudioEncoder  # type: ignore[import]  # noqa: PLC0415
            import torch  # noqa: PLC0415

            # VAE
            vae_path = self._model_dir / "models" / "sd-vae-ft-mse"
            self._vae = VAE(str(vae_path)).to(self._device)
            self._vae.eval()

            # UNet
            unet_path = self._model_dir / "models" / "musetalk" / "pytorch_model.bin"
            self._unet = UNet().to(self._device)
            state = torch.load(str(unet_path), map_location=self._device)
            self._unet.load_state_dict(state)
            self._unet.eval()

            # Audio encoder (Whisper feature extractor)
            whisper_path = self._model_dir / "models" / "whisper" / "tiny.pt"
            self._audio_encoder = AudioEncoder(str(whisper_path)).to(self._device)
            self._audio_encoder.eval()

            elapsed = (time.perf_counter() - t0) * 1000
            self._initialized = True
            logger.info(
                "musetalk_loaded",
                model_dir=str(self._model_dir),
                device=self._device,
                load_ms=round(elapsed, 1),
            )
        except ImportError as exc:
            logger.warning("musetalk_not_available", error=str(exc))
            self._initialized = True  # stub mode
        except Exception as exc:
            logger.error("musetalk_load_failed", error=str(exc))
            raise

    # ── Public API ────────────────────────────────────────────────────────────

    def sync_batch(
        self,
        face_image: np.ndarray,
        audio: np.ndarray,
        audio_sr: int = MUSETALK_AUDIO_SR,
        batch_size: int = 8,
    ) -> MuseTalkResult:
        """
        Offline batch lip sync — full audio-driven animation.

        Args:
            face_image: BGR numpy array of the source face.
            audio: float32 mono audio at ``audio_sr`` Hz.
            audio_sr: Sample rate of ``audio``.
            batch_size: Number of frames per GPU batch.

        Returns:
            MuseTalkResult with all output frames.
        """
        t0 = time.perf_counter()
        result = MuseTalkResult()

        try:
            audio_features = self._extract_audio_features(audio, audio_sr)
            n_frames = len(audio_features)
            face_latent = self._encode_face(face_image)

            frames: list[MuseTalkFrame] = []
            for i in range(0, n_frames, batch_size):
                batch_features = audio_features[i : i + batch_size]
                t_batch = time.perf_counter()
                batch_frames = self._decode_batch(face_latent, batch_features)
                batch_latency = (time.perf_counter() - t_batch) * 1000 / max(len(batch_features), 1)
                for j, frame_bgr in enumerate(batch_frames):
                    frames.append(
                        MuseTalkFrame(
                            frame=frame_bgr,
                            timestamp_ms=(i + j) * 1000.0 / MUSETALK_FPS,
                            latency_ms=batch_latency,
                        )
                    )
                self._maybe_free_gpu()

            result.frames = frames
            result.duration_seconds = len(frames) / MUSETALK_FPS
            result.avg_latency_ms = (
                sum(f.latency_ms for f in frames) / len(frames) if frames else 0.0
            )
            result.inference_ms = (time.perf_counter() - t0) * 1000

            logger.info(
                "musetalk_batch_done",
                frames=len(frames),
                duration_s=round(result.duration_seconds, 2),
                avg_latency_ms=round(result.avg_latency_ms, 1),
            )

        except Exception as exc:
            logger.error("musetalk_batch_error", error=str(exc), exc_info=True)
            result.error = str(exc)

        return result

    def sync_realtime_stream(
        self,
        face_image: np.ndarray,
        audio_chunk_iter: Iterator[np.ndarray],
        audio_sr: int = MUSETALK_AUDIO_SR,
    ) -> Iterator[MuseTalkFrame]:
        """
        Real-time streaming lip sync.

        Accepts an iterator of 20 ms audio chunks and yields rendered frames
        as soon as each is ready. Target end-to-end latency: <500 ms.

        Args:
            face_image: BGR face image (static source).
            audio_chunk_iter: Iterator producing float32 arrays at ``audio_sr`` Hz.
            audio_sr: Sample rate of incoming audio.

        Yields:
            MuseTalkFrame as each frame is rendered.
        """
        face_latent = self._encode_face(face_image)
        buffer: list[np.ndarray] = []
        samples_per_frame = int(audio_sr / MUSETALK_FPS)

        for chunk in audio_chunk_iter:
            buffer.append(chunk)
            total = sum(len(c) for c in buffer)

            while total >= samples_per_frame:
                # Extract exactly one frame's worth of audio
                flat = np.concatenate(buffer)
                frame_audio = flat[:samples_per_frame]
                buffer = [flat[samples_per_frame:]] if len(flat) > samples_per_frame else []
                total = sum(len(c) for c in buffer)

                t0 = time.perf_counter()
                feature = self._extract_audio_features(frame_audio, audio_sr)
                if len(feature) > 0:
                    frames = self._decode_batch(face_latent, feature[:1])
                    latency_ms = (time.perf_counter() - t0) * 1000
                    if frames:
                        yield MuseTalkFrame(
                            frame=frames[0],
                            timestamp_ms=time.perf_counter() * 1000,
                            latency_ms=latency_ms,
                        )

    def create_frame_buffer(
        self, face_image: np.ndarray, buffer_size: int = 10
    ) -> "FrameBuffer":
        """Create a thread-safe frame buffer for WebRTC integration."""
        return FrameBuffer(self, face_image, buffer_size=buffer_size)

    # ── Async wrappers ────────────────────────────────────────────────────────

    @classmethod
    async def async_sync_batch(
        cls,
        face_image: np.ndarray,
        audio: np.ndarray,
        audio_sr: int = MUSETALK_AUDIO_SR,
    ) -> MuseTalkResult:
        loop = asyncio.get_event_loop()
        syncer = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: syncer.sync_batch(face_image, audio, audio_sr=audio_sr),
        )

    @classmethod
    async def async_sync_realtime(
        cls,
        face_image: np.ndarray,
        audio_chunk_queue: asyncio.Queue,
        audio_sr: int = MUSETALK_AUDIO_SR,
    ) -> AsyncIterator[MuseTalkFrame]:
        """Async generator for real-time WebRTC streaming."""
        syncer = cls.get_instance()
        face_latent = await asyncio.get_event_loop().run_in_executor(
            _EXECUTOR, lambda: syncer._encode_face(face_image)
        )

        samples_per_frame = int(audio_sr / MUSETALK_FPS)
        buffer: list[np.ndarray] = []

        while True:
            try:
                chunk = await asyncio.wait_for(audio_chunk_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                break

            if chunk is None:  # sentinel
                break

            buffer.append(chunk)
            total = sum(len(c) for c in buffer)

            while total >= samples_per_frame:
                flat = np.concatenate(buffer)
                frame_audio = flat[:samples_per_frame]
                buffer = [flat[samples_per_frame:]] if len(flat) > samples_per_frame else []
                total = sum(len(c) for c in buffer)

                def _infer(la=face_latent, fa=frame_audio):
                    feat = syncer._extract_audio_features(fa, audio_sr)
                    if feat:
                        return syncer._decode_batch(la, feat[:1])
                    return []

                t0 = time.perf_counter()
                frames = await asyncio.get_event_loop().run_in_executor(_EXECUTOR, _infer)
                latency_ms = (time.perf_counter() - t0) * 1000

                for frm in frames:
                    yield MuseTalkFrame(frame=frm, timestamp_ms=time.perf_counter() * 1000, latency_ms=latency_ms)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _encode_face(self, face_image: np.ndarray) -> Any:
        """Encode a face image into its VAE latent representation."""
        if self._vae is None:
            return face_image  # stub

        try:
            import torch  # noqa: PLC0415

            face_resized = cv2.resize(face_image, MUSETALK_FACE_SIZE)
            face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
            face_tensor = (
                torch.FloatTensor(face_rgb).permute(2, 0, 1).unsqueeze(0) / 127.5 - 1.0
            ).to(self._device)

            with torch.no_grad():
                latent = self._vae.encode(face_tensor).latent_dist.sample()
                latent = latent * 0.18215
            return latent
        except Exception as exc:
            logger.warning("musetalk_encode_face_error", error=str(exc))
            return face_image

    def _extract_audio_features(
        self, audio: np.ndarray, sr: int
    ) -> list[np.ndarray]:
        """Extract per-frame Whisper audio features."""
        if self._audio_encoder is None:
            n = max(1, len(audio) * MUSETALK_FPS // sr)
            return [np.zeros(384, dtype=np.float32) for _ in range(n)]

        try:
            import torch  # noqa: PLC0415

            audio_tensor = torch.FloatTensor(audio).unsqueeze(0).to(self._device)
            with torch.no_grad():
                features = self._audio_encoder(audio_tensor)
            # features shape: (1, T, D) — split into per-frame list
            return [features[0, t].cpu().numpy() for t in range(features.shape[1])]
        except Exception as exc:
            logger.warning("musetalk_audio_feature_error", error=str(exc))
            return []

    def _decode_batch(
        self, face_latent: Any, audio_features: list[np.ndarray]
    ) -> list[np.ndarray]:
        """Run UNet denoising and VAE decoding for a batch of features."""
        if self._unet is None or not audio_features:
            # Stub: return face image repeated
            if isinstance(face_latent, np.ndarray):
                return [face_latent.copy() for _ in audio_features]
            return []

        try:
            import torch  # noqa: PLC0415

            feat_tensor = torch.FloatTensor(
                np.stack(audio_features)
            ).to(self._device)  # (B, D)

            B = len(audio_features)
            latent_batch = face_latent.repeat(B, 1, 1, 1)

            with torch.no_grad():
                out_latent = self._unet(latent_batch, feat_tensor)
                out_latent = out_latent / 0.18215
                out_images = self._vae.decode(out_latent).sample

            out_np = out_images.cpu().numpy()  # (B, C, H, W)
            frames: list[np.ndarray] = []
            for i in range(B):
                img = ((out_np[i].transpose(1, 2, 0) + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
                frames.append(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            return frames

        except Exception as exc:
            logger.error("musetalk_decode_error", error=str(exc), exc_info=True)
            return []

    @staticmethod
    def _maybe_free_gpu() -> None:
        try:
            import torch  # noqa: PLC0415

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        gc.collect()

    def gpu_stats(self) -> dict[str, float]:
        try:
            import torch  # noqa: PLC0415

            if torch.cuda.is_available():
                alloc = torch.cuda.memory_allocated() / 1024**2
                total = torch.cuda.get_device_properties(0).total_memory / 1024**2
                return {"allocated_mb": round(alloc, 1), "total_mb": round(total, 1)}
        except ImportError:
            pass
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# FrameBuffer for WebRTC
# ──────────────────────────────────────────────────────────────────────────────


class FrameBuffer:
    """
    Thread-safe double-buffer for MuseTalk → WebRTC frame delivery.

    A background thread runs MuseTalk inference and pushes frames
    into the buffer. The WebRTC thread pulls frames at 25 fps.
    """

    def __init__(
        self,
        syncer: MuseTalkSyncer,
        face_image: np.ndarray,
        buffer_size: int = 10,
    ) -> None:
        self._syncer = syncer
        self._face_image = face_image
        self._face_latent = syncer._encode_face(face_image)
        self._q: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=buffer_size)
        self._audio_q: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=100)
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info("musetalk_frame_buffer_started")

    def stop(self) -> None:
        self._running = False
        self._audio_q.put(None)  # sentinel
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("musetalk_frame_buffer_stopped")

    def push_audio(self, chunk: np.ndarray) -> None:
        """Push an audio chunk for processing."""
        if not self._audio_q.full():
            self._audio_q.put_nowait(chunk)

    def get_frame(self, timeout: float = 0.05) -> np.ndarray | None:
        """Pull the next rendered frame (non-blocking, returns None if empty)."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def _worker(self) -> None:
        buffer: list[np.ndarray] = []
        samples_per_frame = MUSETALK_AUDIO_SR // MUSETALK_FPS

        while self._running:
            try:
                chunk = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                continue

            if chunk is None:
                break

            buffer.append(chunk)
            total = sum(len(c) for c in buffer)

            while total >= samples_per_frame:
                flat = np.concatenate(buffer)
                frame_audio = flat[:samples_per_frame]
                buffer = [flat[samples_per_frame:]] if len(flat) > samples_per_frame else []
                total = sum(len(c) for c in buffer)

                features = self._syncer._extract_audio_features(frame_audio, MUSETALK_AUDIO_SR)
                if features:
                    frames = self._syncer._decode_batch(self._face_latent, features[:1])
                    for frm in frames:
                        if not self._q.full():
                            self._q.put_nowait(frm)
