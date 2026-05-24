"""
ml/avatar/live_portrait.py
--------------------------
LivePortrait integration for animating a static face image with a driving video.

Features:
- Lazy singleton model loading (UNet + appearance / motion encoders)
- Animate source image with driving video frames
- Motion template extraction from any driving video
- Apply pre-extracted motion template to a static image
- Batch processing with configurable chunk sizes
- GPU memory monitoring and cache eviction
- Quality / speed trade-off via preset modes
- Full async wrapper so the FastAPI event loop stays unblocked
"""

from __future__ import annotations

import asyncio
import gc
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="live_portrait")

QualityPreset = Literal["fast", "balanced", "quality"]


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class MotionTemplate:
    """Serialisable motion template extracted from a driving video."""

    kp_sequence: list[dict[str, Any]]       # per-frame keypoints
    frame_count: int = 0
    fps: float = 25.0
    source_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kp_sequence": self.kp_sequence,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "source_path": self.source_path,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotionTemplate":
        return cls(
            kp_sequence=data["kp_sequence"],
            frame_count=data.get("frame_count", len(data["kp_sequence"])),
            fps=data.get("fps", 25.0),
            source_path=data.get("source_path", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AnimationResult:
    """Result of a LivePortrait animation job."""

    frames: list[np.ndarray] = field(default_factory=list)  # BGR frames
    fps: float = 25.0
    frame_count: int = 0
    duration_seconds: float = 0.0
    inference_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.frames) > 0


# ──────────────────────────────────────────────────────────────────────────────
# LivePortrait model wrapper
# ──────────────────────────────────────────────────────────────────────────────


class LivePortraitAnimator:
    """
    Singleton wrapper around the LivePortrait inference pipeline.

    Typical usage::

        animator = LivePortraitAnimator.get_instance()
        result = animator.animate(source_image_bgr, driving_video_path)
    """

    _instance: "LivePortraitAnimator | None" = None
    _lock = asyncio.Lock()

    def __init__(self, model_dir: Path, device: str = "cuda") -> None:
        self._model_dir = Path(model_dir)
        self._device = device
        self._pipeline: Any = None
        self._initialized = False

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "LivePortraitAnimator":
        if cls._instance is None:
            from app.core.config import settings  # local import avoids circular deps

            device = "cuda" if settings.USE_GPU else "cpu"
            cls._instance = cls(
                model_dir=settings.LIVEPORTRAIT_MODEL_DIR,
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
            # LivePortrait exposes a top-level pipeline class.
            # We attempt a direct import and fall back to stub mode gracefully.
            import sys  # noqa: PLC0415

            sys.path.insert(0, str(self._model_dir))
            from src.pipelines.liveportrait_pipeline import LivePortraitPipeline  # type: ignore[import]

            cfg_path = self._model_dir / "src" / "config" / "inference_config.yaml"
            self._pipeline = LivePortraitPipeline(
                cfg=str(cfg_path),
                device=self._device,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            self._initialized = True
            logger.info(
                "live_portrait_loaded",
                model_dir=str(self._model_dir),
                device=self._device,
                load_ms=round(elapsed, 1),
            )
        except ImportError as exc:
            logger.warning("live_portrait_not_available", error=str(exc), msg="Running in stub mode")
            self._initialized = True
        except Exception as exc:
            logger.error("live_portrait_load_failed", error=str(exc))
            raise

    # ── Public API ────────────────────────────────────────────────────────────

    def extract_motion_template(
        self,
        driving_video_path: str | Path,
        max_frames: int = 300,
    ) -> MotionTemplate:
        """
        Extract a reusable motion template from a driving video.

        Args:
            driving_video_path: Path to the driving video file.
            max_frames: Cap the number of frames to extract.

        Returns:
            MotionTemplate with per-frame keypoint sequences.
        """
        video_path = Path(driving_video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Driving video not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        kp_sequence: list[dict[str, Any]] = []

        try:
            frame_idx = 0
            while frame_idx < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                kp = self._extract_keypoints_from_frame(frame)
                kp_sequence.append(kp)
                frame_idx += 1
        finally:
            cap.release()

        template = MotionTemplate(
            kp_sequence=kp_sequence,
            frame_count=len(kp_sequence),
            fps=fps,
            source_path=str(video_path),
        )
        logger.info(
            "motion_template_extracted",
            path=str(video_path),
            frames=len(kp_sequence),
            fps=fps,
        )
        return template

    def animate(
        self,
        source_image: np.ndarray,
        driving_video_path: str | Path,
        preset: QualityPreset = "balanced",
        relative_motion: bool = True,
        adapt_movement_scale: bool = True,
    ) -> AnimationResult:
        """
        Animate a source image using a driving video.

        Args:
            source_image: BGR numpy array of the source face.
            driving_video_path: Path to the driving video.
            preset: Quality/speed trade-off — "fast", "balanced", or "quality".
            relative_motion: Use relative motion transfer (recommended).
            adapt_movement_scale: Auto-scale motion amplitude.

        Returns:
            AnimationResult containing all output frames.
        """
        t0 = time.perf_counter()
        result = AnimationResult()

        try:
            template = self.extract_motion_template(driving_video_path)
            result = self.animate_from_template(
                source_image,
                template,
                preset=preset,
                relative_motion=relative_motion,
                adapt_movement_scale=adapt_movement_scale,
            )
        except Exception as exc:
            logger.error("live_portrait_animate_error", error=str(exc), exc_info=True)
            result.error = str(exc)
        finally:
            result.inference_ms = (time.perf_counter() - t0) * 1000

        return result

    def animate_from_template(
        self,
        source_image: np.ndarray,
        template: MotionTemplate,
        preset: QualityPreset = "balanced",
        relative_motion: bool = True,
        adapt_movement_scale: bool = True,
        batch_size: int | None = None,
    ) -> AnimationResult:
        """
        Animate a source image from a pre-extracted motion template.
        More efficient than `animate()` when reusing the same motion.
        """
        t0 = time.perf_counter()
        result = AnimationResult(fps=template.fps)

        try:
            if self._pipeline is None:
                # Stub mode: return the source frame repeated
                logger.warning("live_portrait_stub_mode")
                result.frames = [source_image.copy() for _ in template.kp_sequence]
                result.frame_count = len(result.frames)
                result.duration_seconds = result.frame_count / template.fps
                return result

            chunk = batch_size or self._preset_to_batch_size(preset)
            source_rgb = cv2.cvtColor(source_image, cv2.COLOR_BGR2RGB)
            frames: list[np.ndarray] = []

            # Process in chunks to keep GPU memory bounded
            kp_chunks = [
                template.kp_sequence[i : i + chunk]
                for i in range(0, len(template.kp_sequence), chunk)
            ]
            for kp_chunk in kp_chunks:
                chunk_frames = self._pipeline.run_from_keypoints(
                    source_rgb,
                    kp_chunk,
                    relative_motion=relative_motion,
                    adapt_movement_scale=adapt_movement_scale,
                )
                for f in chunk_frames:
                    frames.append(cv2.cvtColor(f, cv2.COLOR_RGB2BGR))
                self._release_gpu_memory()

            result.frames = frames
            result.frame_count = len(frames)
            result.duration_seconds = len(frames) / template.fps
            result.inference_ms = (time.perf_counter() - t0) * 1000

            logger.info(
                "live_portrait_animation_done",
                frame_count=len(frames),
                duration_s=round(result.duration_seconds, 2),
                inference_ms=round(result.inference_ms, 1),
            )

        except Exception as exc:
            logger.error("live_portrait_template_animate_error", error=str(exc), exc_info=True)
            result.error = str(exc)

        return result

    def batch_animate(
        self,
        source_images: list[np.ndarray],
        template: MotionTemplate,
        preset: QualityPreset = "balanced",
    ) -> list[AnimationResult]:
        """Animate multiple source images from the same motion template."""
        results: list[AnimationResult] = []
        for idx, img in enumerate(source_images):
            logger.debug("batch_animate_frame", index=idx, total=len(source_images))
            res = self.animate_from_template(img, template, preset=preset)
            results.append(res)
        return results

    # ── Async wrappers ────────────────────────────────────────────────────────

    @classmethod
    async def async_animate(
        cls,
        source_image: np.ndarray,
        driving_video_path: str | Path,
        preset: QualityPreset = "balanced",
    ) -> AnimationResult:
        loop = asyncio.get_event_loop()
        animator = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: animator.animate(source_image, driving_video_path, preset=preset),
        )

    @classmethod
    async def async_extract_motion_template(
        cls, driving_video_path: str | Path, max_frames: int = 300
    ) -> MotionTemplate:
        loop = asyncio.get_event_loop()
        animator = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: animator.extract_motion_template(driving_video_path, max_frames),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_keypoints_from_frame(self, frame: np.ndarray) -> dict[str, Any]:
        """Extract motion keypoints from a single BGR video frame."""
        if self._pipeline is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return self._pipeline.get_kp_info(rgb)
            except Exception:
                pass
        # Stub: return a zero-motion keypoint dict
        return {"kp": np.zeros((21, 2), dtype=np.float32).tolist(), "exp": 0.0, "scale": 1.0, "t": [0.0, 0.0]}

    @staticmethod
    def _preset_to_batch_size(preset: QualityPreset) -> int:
        return {"fast": 32, "balanced": 16, "quality": 8}[preset]

    @staticmethod
    def _release_gpu_memory() -> None:
        """Free CUDA cache between chunks to avoid OOM errors."""
        try:
            import torch  # noqa: PLC0415

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        gc.collect()

    def gpu_memory_info(self) -> dict[str, float]:
        """Return current GPU memory usage in MB."""
        try:
            import torch  # noqa: PLC0415

            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1024**2
                reserved = torch.cuda.memory_reserved() / 1024**2
                total = torch.cuda.get_device_properties(0).total_memory / 1024**2
                return {
                    "allocated_mb": round(allocated, 1),
                    "reserved_mb": round(reserved, 1),
                    "total_mb": round(total, 1),
                    "free_mb": round(total - reserved, 1),
                }
        except ImportError:
            pass
        return {}
