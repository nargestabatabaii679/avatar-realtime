"""
Download all required AI models for Avatar Platform.
Usage: python scripts/setup/download_models.py [--models whisper,xtts,insightface,liveportrait,musetalk]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import urllib.request

MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))

MODELS = {
    "whisper": {
        "description": "Whisper Large V3 (STT)",
        "size": "~3GB",
        "fn": "_download_whisper",
    },
    "xtts": {
        "description": "XTTS-v2 (Voice Cloning + TTS)",
        "size": "~2GB",
        "fn": "_download_xtts",
    },
    "insightface": {
        "description": "InsightFace buffalo_l (Face Analysis)",
        "size": "~500MB",
        "fn": "_download_insightface",
    },
    "embedder": {
        "description": "multilingual-e5-large (Text Embeddings)",
        "size": "~600MB",
        "fn": "_download_embedder",
    },
}


def _progress_hook(count, block_size, total_size):
    percent = min(int(count * block_size * 100 / total_size), 100) if total_size > 0 else 0
    bar = "█" * (percent // 5) + "░" * (20 - percent // 5)
    print(f"\r  [{bar}] {percent}%", end="", flush=True)


def _download_whisper():
    """Download Whisper using faster-whisper (downloads on first use)."""
    try:
        print("  Downloading Whisper Large V3...")
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3", download_root=str(MODEL_DIR / "whisper"))
        del model
        print("\n  ✓ Whisper downloaded")
    except Exception as e:
        print(f"\n  ✗ Whisper download failed: {e}")


def _download_xtts():
    """Download XTTS-v2 model."""
    try:
        print("  Downloading XTTS-v2...")
        from TTS.api import TTS
        tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                  progress_bar=True)
        print("  ✓ XTTS-v2 downloaded")
    except Exception as e:
        print(f"  ✗ XTTS-v2 download failed: {e}")


def _download_insightface():
    """Download InsightFace buffalo_l model."""
    try:
        print("  Downloading InsightFace buffalo_l...")
        import insightface
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", root=str(MODEL_DIR / "insightface"))
        app.prepare(ctx_id=0 if _has_gpu() else -1)
        print("  ✓ InsightFace downloaded")
    except Exception as e:
        print(f"  ✗ InsightFace download failed: {e}")


def _download_embedder():
    """Download multilingual-e5-large embeddings model."""
    try:
        print("  Downloading multilingual-e5-large...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(
            "intfloat/multilingual-e5-large",
            cache_folder=str(MODEL_DIR / "embedder"),
        )
        del model
        print("  ✓ Embedder downloaded")
    except Exception as e:
        print(f"  ✗ Embedder download failed: {e}")


def _has_gpu() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def main(model_names: list[str] | None = None):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    to_download = model_names or list(MODELS.keys())

    print(f"\n{'='*60}")
    print("  AI Model Downloader — Avatar Platform")
    print(f"{'='*60}")
    print(f"  Target directory: {MODEL_DIR}")
    print(f"  GPU available: {'Yes' if _has_gpu() else 'No (CPU mode)'}")
    print(f"  Models to download: {', '.join(to_download)}")
    print()

    fn_map = {
        "whisper": _download_whisper,
        "xtts": _download_xtts,
        "insightface": _download_insightface,
        "embedder": _download_embedder,
    }

    for name in to_download:
        model_info = MODELS.get(name)
        if not model_info:
            print(f"Unknown model: {name}")
            continue
        print(f"\n[{name}] {model_info['description']} ({model_info['size']})")
        fn = fn_map.get(name)
        if fn:
            fn()

    print(f"\n{'='*60}")
    print("  Download complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download AI models for Avatar Platform")
    parser.add_argument("--models", help="Comma-separated list of models to download (default: all)")
    args = parser.parse_args()

    model_list = args.models.split(",") if args.models else None
    main(model_list)
