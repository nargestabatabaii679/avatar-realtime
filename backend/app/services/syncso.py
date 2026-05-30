"""
app/services/syncso.py
-----------------------
Sync.so API client for cloud-based video lip-sync generation.

Docs: https://docs.sync.so/api-reference/
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

SYNCSO_BASE_URL = "https://api.sync.so/v2"


class SyncSoError(Exception):
    """Raised when the Sync.so API returns an error."""


class SyncSoService:
    """Async Sync.so API client for lip-sync video generation."""

    def __init__(self) -> None:
        api_key: str = getattr(settings, "SYNCSO_API_KEY", "")
        if not api_key:
            raise SyncSoError("SYNCSO_API_KEY is not configured")
        self._headers = {
            "x-api-key": api_key,
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Lip-sync generation
    # ------------------------------------------------------------------

    async def create_lipsync(
        self,
        video_url: str,
        audio_path: str | Path | None = None,
        audio_url: str | None = None,
        model: str = "sync-1.6.0",
        output_format: str = "mp4",
        fps: int = 25,
    ) -> str:
        """
        Submit a lip-sync job.

        Provide either a local ``audio_path`` (uploaded first) or a pre-hosted
        ``audio_url``.  Returns the Sync.so job ID to poll with
        ``get_status``.
        """
        if audio_url is None:
            if audio_path is None:
                raise ValueError("Either audio_path or audio_url must be provided")
            audio_url = await self._upload_audio(audio_path)

        payload: dict[str, Any] = {
            "model": model,
            "input": [
                {"type": "video", "url": video_url},
                {"type": "audio", "url": audio_url},
            ],
            "options": {
                "output_format": output_format,
                "fps": fps,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{SYNCSO_BASE_URL}/generate",
                json=payload,
                headers={**self._headers, "Content-Type": "application/json"},
            )

        self._raise_for_status(resp, "create_lipsync")
        data = resp.json()
        job_id: str = data["id"]
        logger.info("syncso_job_created", job_id=job_id)
        return job_id

    async def get_status(self, job_id: str) -> dict[str, Any]:
        """
        Poll the status of a Sync.so lip-sync job.

        Returns: ``{"status": "...", "output_url": "...", "error": "..."}``
        Possible statuses: ``PENDING``, ``PROCESSING``, ``COMPLETED``, ``FAILED``
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{SYNCSO_BASE_URL}/generate/{job_id}",
                headers=self._headers,
            )

        self._raise_for_status(resp, "get_status")
        data = resp.json()

        raw_status: str = data.get("status", "PENDING").upper()
        # Normalise to lowercase for consistency with rest of codebase
        status_map = {
            "PENDING": "pending",
            "PROCESSING": "processing",
            "COMPLETED": "completed",
            "FAILED": "failed",
        }
        status = status_map.get(raw_status, raw_status.lower())

        output_url: str | None = None
        if status == "completed":
            outputs = data.get("outputUrl") or data.get("output_url") or ""
            output_url = outputs if isinstance(outputs, str) else None

        return {
            "status": status,
            "output_url": output_url,
            "error": data.get("error"),
            "created_at": data.get("createdAt"),
            "completed_at": data.get("completedAt"),
        }

    async def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float = 10.0,
        timeout: float = 1800.0,
    ) -> dict[str, Any]:
        """Poll until the job completes or fails, raising on timeout."""
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status_data = await self.get_status(job_id)
            if status_data["status"] in ("completed", "failed"):
                return status_data
            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"Sync.so job {job_id} timed out after {timeout}s")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _upload_audio(self, audio_path: str | Path) -> str:
        """Upload a local audio file to Sync.so and return its hosted URL."""
        path = Path(audio_path)
        mime = "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/wav"

        async with httpx.AsyncClient(timeout=60) as client:
            with open(path, "rb") as f:
                resp = await client.post(
                    f"{SYNCSO_BASE_URL}/upload",
                    files={"file": (path.name, f, mime)},
                    headers=self._headers,
                )

        self._raise_for_status(resp, "upload_audio")
        data = resp.json()
        url: str = data.get("url") or data.get("upload_url", "")
        if not url:
            raise SyncSoError("Sync.so upload returned no URL")
        return url

    @staticmethod
    def _raise_for_status(resp: httpx.Response, action: str) -> None:
        if resp.status_code >= 400:
            body = ""
            try:
                body = resp.json().get("message", resp.text)
            except Exception:
                body = resp.text
            raise SyncSoError(f"Sync.so {action} failed [{resp.status_code}]: {body}")
