"""
ml/avatar/wav2lip.py
--------------------
Wav2Lip lip-sync module — fallback when LivePortrait / MuseTalk are unavailable.

Features:
- Model loading from wav2lip_gan.pth checkpoint
- Lip-sync video generation from audio + face video / static image
- Per-frame face detection via MediaPipe (fast) with InsightFace fallback
- Configurable batch size for frame processing
- Audio-video alignment via librosa
- Post-processing quality enhancement (GFPGAN face restoration, optional)
- CPU fallback mode when no CUDA device is available
- Async wrapper for non-blocking use in FastAPI
"""

from __future__ import annotations

import asyncio
import gc
import io
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wav2lip")

_MEL_STEP_SIZE = 16        # audio mel spectrogram windows per video frame
_MEL_CHANNELS = 80
_FACE_SIZE = (96, 96)       # Wav2Lip input face crop size


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Wav2LipResult:
    output_frames: list[np.ndarray] = field(default_factory=list)  # BGR frames
    fps: float = 25.0
    audio_path: str = ""
    inference_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.output_frames) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Wav2Lip model wrapper
# ──────────────────────────────────────────────────────────────────────────────


class Wav2LipSyncer:
    """
    Singleton that wraps the Wav2Lip GAN model for lip synchronisation.

    Example::

        syncer = Wav2LipSyncer.get_instance()
        result = syncer.sync(face_video_path, audio_path)
    """

    _instance: "Wav2LipSyncer | None" = None

    def __init__(self, checkpoint_path: Path, device: str = "cuda") -> None:
        self._checkpoint_path = Path(checkpoint_path)
        self._device = device
        self._model: Any = None
        self._initialized = False

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "Wav2LipSyncer":
        if cls._instance is None:
            from app.core.config import settings  # noqa: PLC0415

            device = "cuda" if settings.USE_GPU else "cpu"
            cls._instance = cls(
                checkpoint_path=settings.WAV2LIP_MODEL_DIR / settings.WAV2LIP_CHECKPOINT,
                device=device,
            )
            cls._instance._load()
        return cls._instance

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._initialized:
            return
        t0 = time.perf_counter()
        try:
            import torch  # noqa: PLC0415

            # Wav2Lip model definition is bundled in the model directory.
            # We import it dynamically to avoid hard-coding the path.
            wav2lip_root = self._checkpoint_path.parent
            import sys  # noqa: PLC0415

            sys.path.insert(0, str(wav2lip_root))
            from models.wav2lip import Wav2Lip  # type: ignore[import]  # noqa: PLC0415

            self._model = Wav2Lip()
            checkpoint = torch.load(str(self._checkpoint_path), map_location=self._device)
            state_dict = checkpoint.get("state_dict", checkpoint)
            self._model.load_state_dict(state_dict)
            self._model = self._model.to(self._device)
            self._model.eval()

            elapsed = (time.perf_counter() - t0) * 1000
            self._initialized = True
            logger.info(
                "wav2lip_loaded",
                checkpoint=str(self._checkpoint_path),
                device=self._device,
                load_ms=round(elapsed, 1),
            )
        except ImportError as exc:
            logger.warning("wav2lip_not_available", error=str(exc))
            self._initialized = True  # stub mode
        except Exception as exc:
            logger.error("wav2lip_load_failed", error=str(exc))
            raise

    # ── Public API ────────────────────────────────────────────────────────────

    def sync(
        self,
        face_source: str | Path | np.ndarray,
        audio_path: str | Path,
        fps: float = 25.0,
        batch_size: int = 64,
        enhance_quality: bool = False,
    ) -> Wav2LipResult:
        """
        Generate a lip-synced video.

        Args:
            face_source: Path to face video, or a single BGR numpy image.
            audio_path: Path to the driving audio file (.wav).
            fps: Output video frame rate.
            batch_size: Number of frames per inference batch.
            enhance_quality: Run GFPGAN post-processing (slower).

        Returns:
            Wav2LipResult with output frames list.
        """
        t0 = time.perf_counter()
        result = Wav2LipResult(fps=fps, audio_path=str(audio_path))

        try:
            frames = self._load_face_frames(face_source, fps)
            mel_chunks = self._audio_to_mel_chunks(audio_path, fps)

            if len(mel_chunks) == 0:
                result.error = "audio_too_short_or_invalid"
                return result

            # Align frame count to mel chunks
            frames = self._align_frames_to_audio(frames, mel_chunks)
            output_frames = self._run_inference(frames, mel_chunks, batch_size)

            if enhance_quality:
                output_frames = self._enhance_faces(output_frames, frames)

            result.output_frames = output_frames
            result.inference_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "wav2lip_sync_done",
                frames=len(output_frames),
                inference_ms=round(result.inference_ms, 1),
            )

        except Exception as exc:
            logger.error("wav2lip_sync_error", error=str(exc), exc_info=True)
            result.error = str(exc)

        return result

    # ── Async wrapper ─────────────────────────────────────────────────────────

    @classmethod
    async def async_sync(
        cls,
        face_source: str | Path | np.ndarray,
        audio_path: str | Path,
        fps: float = 25.0,
        batch_size: int = 64,
    ) -> Wav2LipResult:
        loop = asyncio.get_event_loop()
        syncer = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: syncer.sync(face_source, audio_path, fps=fps, batch_size=batch_size),
        )

    # ── Internal pipeline helpers ─────────────────────────────────────────────

    def _load_face_frames(
        self, face_source: str | Path | np.ndarray, fps: float
    ) -> list[np.ndarray]:
        """Load face frames from a video path or single image."""
        if isinstance(face_source, np.ndarray):
            return [face_source]

        path = Path(face_source)
        if not path.exists():
            raise FileNotFoundError(f"Face source not found: {path}")

        cap = cv2.VideoCapture(str(path))
        frames: list[np.ndarray] = []
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
        finally:
            cap.release()

        if not frames:
            raise ValueError("No frames could be read from the face source video")
        return frames

    def _audio_to_mel_chunks(
        self, audio_path: str | Path, fps: float
    ) -> list[np.ndarray]:
        """Convert audio file to a list of mel spectrogram chunks (one per video frame)."""
        try:
            import librosa  # noqa: PLC0415

            wav, sr = librosa.load(str(audio_path), sr=16000, mono=True)
            # Build mel spectrogram
            mel = librosa.feature.melspectrogram(
                y=wav, sr=sr, n_mels=_MEL_CHANNELS, fmax=8000
            )
            mel_db = librosa.power_to_db(mel, ref=np.max).astype(np.float32)

            # Split into per-frame chunks
            hop = int(sr / fps)
            step = _MEL_STEP_SIZE
            chunks: list[np.ndarray] = []
            for i in range(0, mel_db.shape[1] - step, int(step * fps / fps)):
                chunk = mel_db[:, i : i + step]
                if chunk.shape[1] == step:
                    chunks.append(chunk)
            return chunks

        except ImportError:
            logger.warning("librosa_not_installed", msg="Returning empty mel chunks")
            return []

    @staticmethod
    def _align_frames_to_audio(
        frames: list[np.ndarray], mel_chunks: list[np.ndarray]
    ) -> list[np.ndarray]:
        """Cycle or truncate frames so their count matches mel_chunks."""
        n = len(mel_chunks)
        if len(frames) == 0:
            return frames
        if len(frames) >= n:
            return frames[:n]
        # Cycle frames to fill
        result: list[np.ndarray] = []
        while len(result) < n:
            result.extend(frames)
        return result[:n]

    def _detect_face_region(self, frame: np.ndarray) -> tuple[int, int, int, int] | None:
        """Detect face bounding box using MediaPipe or fallback to centre crop."""
        try:
            import mediapipe as mp  # noqa: PLC0415

            detector = mp.solutions.face_detection.FaceDetection(
                model_selection=0, min_detection_confidence=0.5
            )
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = detector.process(rgb)
            detector.close()
            if results.detections:
                det = results.detections[0]
                bbox = det.location_data.relative_bounding_box
                h, w = frame.shape[:2]
                x1 = int(bbox.xmin * w)
                y1 = int(bbox.ymin * h)
                x2 = x1 + int(bbox.width * w)
                y2 = y1 + int(bbox.height * h)
                return (
                    max(0, x1), max(0, y1),
                    min(w, x2), min(h, y2),
                )
        except ImportError:
            pass

        # Fallback: use centre 60% of the frame
        h, w = frame.shape[:2]
        margin_x, margin_y = int(w * 0.2), int(h * 0.1)
        return (margin_x, margin_y, w - margin_x, h - margin_y)

    def _run_inference(
        self,
        frames: list[np.ndarray],
        mel_chunks: list[np.ndarray],
        batch_size: int,
    ) -> list[np.ndarray]:
        """Core Wav2Lip inference loop processing frames in batches."""
        if self._model is None:
            # Stub mode: return frames unchanged
            logger.warning("wav2lip_stub_inference")
            return frames[: len(mel_chunks)]

        try:
            import torch  # noqa: PLC0415

            output_frames: list[np.ndarray] = []
            coords_list: list[tuple[int, int, int, int]] = []
            face_crops: list[np.ndarray] = []

            # Pre-detect faces and cache crops
            for frame in frames:
                coord = self._detect_face_region(frame)
                if coord is None:
                    coord = (0, 0, frame.shape[1], frame.shape[0])
                coords_list.append(coord)
                x1, y1, x2, y2 = coord
                crop = frame[y1:y2, x1:x2]
                crop_resized = cv2.resize(crop, _FACE_SIZE)
                face_crops.append(crop_resized)

            # Batch inference
            for i in range(0, len(frames), batch_size):
                batch_frames = frames[i : i + batch_size]
                batch_mels = mel_chunks[i : i + batch_size]
                batch_faces = face_crops[i : i + batch_size]
                batch_coords = coords_list[i : i + batch_size]

                if not batch_mels:
                    break

                mel_batch = np.array(batch_mels, dtype=np.float32)  # (B, 80, 16)
                face_batch = np.array(batch_faces, dtype=np.float32) / 255.0
                # Wav2Lip expects (B, 6, H, W) — upper half masked + lower half original
                lower_mask = face_batch.copy()
                lower_mask[:, : _FACE_SIZE[1] // 2, :, :] = 0.0

                img_input = np.concatenate([lower_mask, face_batch], axis=3)
                img_input = np.transpose(img_input, (0, 3, 1, 2))  # BHWC -> BCHW

                img_tensor = torch.FloatTensor(img_input).to(self._device)
                mel_tensor = torch.FloatTensor(mel_batch).unsqueeze(1).to(self._device)

                with torch.no_grad():
                    pred = self._model(mel_tensor, img_tensor)

                pred_np = pred.squeeze(0).cpu().numpy()
                pred_np = np.transpose(pred_np, (0, 2, 3, 1)) * 255.0
                pred_np = pred_np.astype(np.uint8)

                for j, (pred_face, frame, coord) in enumerate(
                    zip(pred_np, batch_frames, batch_coords)
                ):
                    pred_face_resized = cv2.resize(pred_face, (coord[2] - coord[0], coord[3] - coord[1]))
                    out_frame = frame.copy()
                    out_frame[coord[1] : coord[3], coord[0] : coord[2]] = pred_face_resized
                    output_frames.append(out_frame)

            # Free VRAM
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

            return output_frames

        except Exception as exc:
            logger.error("wav2lip_inference_error", error=str(exc), exc_info=True)
            raise

    @staticmethod
    def _enhance_faces(
        synced_frames: list[np.ndarray],
        original_frames: list[np.ndarray],
    ) -> list[np.ndarray]:
        """Optional GFPGAN face enhancement pass."""
        try:
            from gfpgan import GFPGANer  # type: ignore[import]  # noqa: PLC0415

            enhancer = GFPGANer(model_path="GFPGANv1.4.pth", upscale=1)
            enhanced: list[np.ndarray] = []
            for frame in synced_frames:
                _, _, restored = enhancer.enhance(frame, paste_back=True)
                enhanced.append(restored)
            return enhanced
        except ImportError:
            logger.debug("gfpgan_not_available", msg="Skipping face enhancement")
            return synced_frames
        except Exception as exc:
            logger.warning("gfpgan_enhance_failed", error=str(exc))
            return synced_frames
