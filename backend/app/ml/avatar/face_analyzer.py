"""
ml/avatar/face_analyzer.py
--------------------------
Face analysis service using InsightFace (buffalo_l model).

Capabilities:
- Face detection from images (bytes / numpy / Path)
- 512-dim face embedding extraction
- Face quality scoring (blur, brightness, pose)
- Multiple face handling with ranked selection
- 468-point facial landmark extraction
- Age / gender estimation
- Face alignment and cropping
- 256x256 thumbnail generation
- GPU/CPU auto-detection
- Async wrappers for non-blocking use
"""

from __future__ import annotations

import asyncio
import io
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog
from PIL import Image

logger = structlog.get_logger(__name__)

# Thread-pool used for blocking CPU/GPU calls so the event loop stays free
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="face_analyzer")

# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class FaceResult:
    """Structured output from a single detected face."""

    # Detection
    bbox: list[float]                        # [x1, y1, x2, y2] in pixel coords
    detection_score: float                   # confidence from retinaface
    # Embedding
    embedding: np.ndarray | None = None      # shape (512,)
    embedding_norm: float = 0.0
    # Landmarks
    landmarks_5: np.ndarray | None = None    # 5-point (eyes, nose, mouth corners)
    landmarks_468: np.ndarray | None = None  # MediaPipe-style 468-point (if available)
    # Pose
    pose: dict[str, float] = field(default_factory=dict)  # yaw, pitch, roll
    # Demographics
    age: int | None = None
    gender: str | None = None               # "male" / "female"
    gender_score: float = 0.0
    # Quality
    quality_score: float = 0.0             # 0-1 composite quality
    blur_score: float = 0.0               # Laplacian variance (higher = sharper)
    brightness_score: float = 0.0
    # Crops
    aligned_face: np.ndarray | None = None  # 112x112 aligned face (ArcFace standard)
    thumbnail: np.ndarray | None = None     # 256x256 center-crop thumbnail


@dataclass
class AnalysisResult:
    """Top-level result returned by FaceAnalyzer."""

    faces: list[FaceResult] = field(default_factory=list)
    primary_face: FaceResult | None = None  # highest-quality detected face
    image_shape: tuple[int, int, int] = (0, 0, 0)
    inference_ms: float = 0.0
    error: str | None = None

    @property
    def has_face(self) -> bool:
        return len(self.faces) > 0

    @property
    def face_count(self) -> int:
        return len(self.faces)


# ──────────────────────────────────────────────────────────────────────────────
# FaceAnalyzer singleton
# ──────────────────────────────────────────────────────────────────────────────


class FaceAnalyzer:
    """
    Wraps InsightFace's buffalo_l model pack.

    Usage (sync):
        analyzer = FaceAnalyzer.get_instance()
        result = analyzer.analyze(image_bytes)

    Usage (async):
        result = await FaceAnalyzer.async_analyze(image_bytes)
    """

    _instance: "FaceAnalyzer | None" = None
    _lock = asyncio.Lock()

    def __init__(self, model_pack: str = "buffalo_l", gpu_id: int = 0) -> None:
        self._model_pack = model_pack
        self._gpu_id = gpu_id
        self._app: Any = None          # insightface.app.FaceAnalysis
        self._initialized = False

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "FaceAnalyzer":
        if cls._instance is None:
            from app.core.config import settings
            gpu_id = settings.GPU_DEVICE_IDS[0] if settings.USE_GPU else -1
            cls._instance = cls(
                model_pack=settings.INSIGHTFACE_DET_MODEL,
                gpu_id=gpu_id,
            )
            cls._instance._load()
        return cls._instance

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._initialized:
            return

        try:
            import insightface  # noqa: PLC0415
            from insightface.app import FaceAnalysis  # noqa: PLC0415

            t0 = time.perf_counter()
            self._app = FaceAnalysis(
                name=self._model_pack,
                root="/opt/models/insightface",
                providers=self._get_providers(),
            )
            self._app.prepare(ctx_id=self._gpu_id, det_size=(640, 640))
            elapsed = (time.perf_counter() - t0) * 1000

            self._initialized = True
            logger.info(
                "insightface_loaded",
                model=self._model_pack,
                gpu_id=self._gpu_id,
                load_ms=round(elapsed, 1),
            )
        except ImportError:
            logger.warning("insightface_not_installed", msg="Running in stub mode")
            self._initialized = True  # allow graceful degradation
        except Exception as exc:
            logger.error("insightface_load_failed", error=str(exc))
            raise

    def _get_providers(self) -> list[str]:
        try:
            import torch  # noqa: PLC0415
            if torch.cuda.is_available() and self._gpu_id >= 0:
                logger.info("face_analyzer_using_gpu", gpu_id=self._gpu_id)
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        except ImportError:
            pass
        logger.info("face_analyzer_using_cpu")
        return ["CPUExecutionProvider"]

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(
        self,
        image: bytes | np.ndarray | str | Path,
        max_faces: int = 10,
        min_detection_score: float = 0.5,
        extract_landmarks_468: bool = False,
    ) -> AnalysisResult:
        """
        Full face analysis pipeline.

        Args:
            image: Raw JPEG/PNG bytes, BGR numpy array, or file path.
            max_faces: Maximum number of faces to return (sorted by quality desc).
            min_detection_score: Minimum detection confidence threshold.
            extract_landmarks_468: Whether to run 468-point landmark extraction.

        Returns:
            AnalysisResult with all detected faces and their attributes.
        """
        t0 = time.perf_counter()
        result = AnalysisResult()

        try:
            img_bgr = self._to_bgr(image)
            result.image_shape = img_bgr.shape

            if self._app is None:
                result.error = "InsightFace model not loaded"
                return result

            raw_faces = self._app.get(img_bgr)
            if not raw_faces:
                result.error = "no_face_detected"
                return result

            # Filter by confidence
            raw_faces = [f for f in raw_faces if f.det_score >= min_detection_score]
            if not raw_faces:
                result.error = "no_face_above_threshold"
                return result

            face_results: list[FaceResult] = []
            for raw in raw_faces[:max_faces]:
                fr = self._process_single_face(
                    img_bgr, raw, extract_landmarks_468
                )
                face_results.append(fr)

            # Sort by composite quality (desc)
            face_results.sort(key=lambda f: f.quality_score, reverse=True)
            result.faces = face_results
            result.primary_face = face_results[0] if face_results else None
            result.inference_ms = (time.perf_counter() - t0) * 1000

            logger.debug(
                "face_analysis_complete",
                face_count=len(face_results),
                inference_ms=round(result.inference_ms, 1),
            )

        except Exception as exc:
            result.error = str(exc)
            logger.error("face_analysis_error", error=str(exc), exc_info=True)

        return result

    def extract_embedding(self, image: bytes | np.ndarray) -> np.ndarray | None:
        """Fast path: return only the 512-dim embedding of the primary face."""
        result = self.analyze(image, max_faces=1)
        if result.primary_face and result.primary_face.embedding is not None:
            return result.primary_face.embedding
        return None

    def generate_thumbnail(
        self, image: bytes | np.ndarray, size: int = 256
    ) -> bytes | None:
        """Return a JPEG-encoded center-crop thumbnail of the primary face."""
        result = self.analyze(image, max_faces=1)
        if not result.primary_face or result.primary_face.thumbnail is None:
            return None
        thumb_rgb = cv2.cvtColor(result.primary_face.thumbnail, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(thumb_rgb).resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    # ── Async wrappers ────────────────────────────────────────────────────────

    @classmethod
    async def async_analyze(
        cls,
        image: bytes | np.ndarray | str | Path,
        max_faces: int = 10,
        min_detection_score: float = 0.5,
    ) -> AnalysisResult:
        """Non-blocking wrapper — runs analysis in a thread-pool executor."""
        loop = asyncio.get_event_loop()
        analyzer = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: analyzer.analyze(image, max_faces, min_detection_score),
        )

    @classmethod
    async def async_extract_embedding(
        cls, image: bytes | np.ndarray
    ) -> np.ndarray | None:
        loop = asyncio.get_event_loop()
        analyzer = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR, lambda: analyzer.extract_embedding(image)
        )

    @classmethod
    async def async_generate_thumbnail(
        cls, image: bytes | np.ndarray, size: int = 256
    ) -> bytes | None:
        loop = asyncio.get_event_loop()
        analyzer = cls.get_instance()
        return await loop.run_in_executor(
            _EXECUTOR, lambda: analyzer.generate_thumbnail(image, size)
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _to_bgr(self, image: bytes | np.ndarray | str | Path) -> np.ndarray:
        """Convert any supported input format to a BGR numpy array."""
        if isinstance(image, np.ndarray):
            return image
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"Cannot read image from path: {image}")
            return img
        if isinstance(image, (bytes, bytearray, memoryview)):
            arr = np.frombuffer(bytes(image), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Cannot decode image from bytes")
            return img
        raise TypeError(f"Unsupported image type: {type(image)}")

    def _process_single_face(
        self, img_bgr: np.ndarray, raw_face: Any, extract_468: bool
    ) -> FaceResult:
        """Convert a raw InsightFace face object into a FaceResult."""
        bbox = raw_face.bbox.tolist()  # [x1, y1, x2, y2]

        fr = FaceResult(
            bbox=bbox,
            detection_score=float(raw_face.det_score),
        )

        # Embedding
        if hasattr(raw_face, "embedding") and raw_face.embedding is not None:
            emb = raw_face.embedding.astype(np.float32)
            norm = np.linalg.norm(emb)
            fr.embedding = emb / (norm + 1e-8)
            fr.embedding_norm = float(norm)

        # 5-point landmarks
        if hasattr(raw_face, "kps") and raw_face.kps is not None:
            fr.landmarks_5 = raw_face.kps.astype(np.float32)

        # Pose
        if hasattr(raw_face, "pose") and raw_face.pose is not None:
            pose = raw_face.pose
            fr.pose = {
                "yaw": float(pose[1]),
                "pitch": float(pose[0]),
                "roll": float(pose[2]),
            }

        # Age / Gender
        if hasattr(raw_face, "age") and raw_face.age is not None:
            fr.age = int(raw_face.age)
        if hasattr(raw_face, "gender") and raw_face.gender is not None:
            gender_int = int(raw_face.gender)
            fr.gender = "male" if gender_int == 1 else "female"
            fr.gender_score = float(raw_face.det_score)

        # Aligned face (112x112 ArcFace standard)
        fr.aligned_face = self._align_face(img_bgr, fr)

        # 468-point landmarks via MediaPipe (optional, expensive)
        if extract_468:
            fr.landmarks_468 = self._extract_468_landmarks(img_bgr, bbox)

        # Thumbnail
        fr.thumbnail = self._make_thumbnail(img_bgr, bbox, size=256)

        # Quality scoring
        fr.blur_score = self._blur_score(img_bgr, bbox)
        fr.brightness_score = self._brightness_score(img_bgr, bbox)
        fr.quality_score = self._composite_quality(fr)

        return fr

    def _align_face(self, img: np.ndarray, fr: FaceResult) -> np.ndarray | None:
        """Align face to 112x112 using 5-point landmarks (ArcFace convention)."""
        if fr.landmarks_5 is None:
            return self._bbox_crop(img, fr.bbox, 112)
        try:
            from insightface.utils import face_align  # noqa: PLC0415
            return face_align.norm_crop(img, fr.landmarks_5, image_size=112)
        except Exception:
            return self._bbox_crop(img, fr.bbox, 112)

    def _bbox_crop(
        self, img: np.ndarray, bbox: list[float], size: int
    ) -> np.ndarray:
        """Crop and resize face region from bounding box."""
        x1, y1, x2, y2 = (int(v) for v in bbox)
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return np.zeros((size, size, 3), dtype=np.uint8)
        crop = img[y1:y2, x1:x2]
        return cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)

    def _make_thumbnail(
        self, img: np.ndarray, bbox: list[float], size: int = 256
    ) -> np.ndarray:
        """Create a square thumbnail centered on the face bounding box."""
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        face_size = max(x2 - x1, y2 - y1)
        pad = face_size * 0.4  # add 40% padding around face
        half = (face_size + pad) / 2

        h, w = img.shape[:2]
        sx1 = int(max(0, cx - half))
        sy1 = int(max(0, cy - half))
        sx2 = int(min(w, cx + half))
        sy2 = int(min(h, cy + half))

        crop = img[sy1:sy2, sx1:sx2]
        if crop.size == 0:
            return np.zeros((size, size, 3), dtype=np.uint8)
        return cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)

    def _extract_468_landmarks(
        self, img: np.ndarray, bbox: list[float]
    ) -> np.ndarray | None:
        """
        Extract 468 facial landmarks using MediaPipe FaceMesh.
        Returns array of shape (468, 2) in image pixel coordinates.
        """
        try:
            import mediapipe as mp  # noqa: PLC0415

            face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
            )
            x1, y1, x2, y2 = (int(v) for v in bbox)
            h, w = img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = img[y1:y2, x1:x2]
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)
            face_mesh.close()

            if not results.multi_face_landmarks:
                return None

            ch, cw = crop.shape[:2]
            pts = []
            for lm in results.multi_face_landmarks[0].landmark:
                pts.append([lm.x * cw + x1, lm.y * ch + y1])
            return np.array(pts, dtype=np.float32)
        except ImportError:
            return None
        except Exception as exc:
            logger.warning("landmark_468_error", error=str(exc))
            return None

    # ── Quality scoring ───────────────────────────────────────────────────────

    def _blur_score(self, img: np.ndarray, bbox: list[float]) -> float:
        """Laplacian variance — higher value means sharper."""
        x1, y1, x2, y2 = (int(v) for v in bbox)
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        # Normalise to 0-1 range (empirical threshold ~100 for "sharp enough")
        return min(variance / 500.0, 1.0)

    def _brightness_score(self, img: np.ndarray, bbox: list[float]) -> float:
        """Returns a 0-1 score where 0.5 is ideal (too dark or too bright = lower)."""
        x1, y1, x2, y2 = (int(v) for v in bbox)
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0
        mean_brightness = float(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2].mean())
        # Gaussian peaked at 128
        score = float(np.exp(-((mean_brightness - 128) ** 2) / (2 * 60**2)))
        return score

    def _composite_quality(self, fr: FaceResult) -> float:
        """
        Weighted composite score from detection confidence, blur, brightness,
        and face pose (frontal faces score higher).
        """
        weights = {
            "detection": 0.3,
            "blur": 0.35,
            "brightness": 0.2,
            "pose": 0.15,
        }
        pose_score = 1.0
        if fr.pose:
            # Penalise extreme yaw/pitch
            yaw = abs(fr.pose.get("yaw", 0))
            pitch = abs(fr.pose.get("pitch", 0))
            pose_score = max(0.0, 1.0 - (yaw / 90.0) * 0.7 - (pitch / 60.0) * 0.3)

        score = (
            weights["detection"] * fr.detection_score
            + weights["blur"] * fr.blur_score
            + weights["brightness"] * fr.brightness_score
            + weights["pose"] * pose_score
        )
        return round(min(score, 1.0), 4)
