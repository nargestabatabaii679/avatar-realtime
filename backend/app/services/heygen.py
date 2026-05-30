"""
app/services/heygen.py
-----------------------
HeyGen API client for cloud avatar video generation and real-time streaming.

Docs: https://docs.heygen.com/reference/
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

HEYGEN_BASE_URL = "https://api.heygen.com"


class HeyGenError(Exception):
    """Raised when the HeyGen API returns an error."""


class HeyGenService:
    """Async HeyGen API client."""

    def __init__(self) -> None:
        api_key: str = getattr(settings, "HEYGEN_API_KEY", "")
        if not api_key:
            raise HeyGenError("HEYGEN_API_KEY is not configured")
        self._headers = {
            "X-Api-Key": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Video generation
    # ------------------------------------------------------------------

    async def generate_video(
        self,
        script: str,
        language: str = "en",
        avatar_id: str | None = None,
        voice_id: str | None = None,
        width: int = 1280,
        height: int = 720,
    ) -> str:
        """
        Submit a video generation request to HeyGen.

        Returns the HeyGen video ID to poll with ``get_video_status``.
        """
        heygen_avatar_id: str = avatar_id or getattr(settings, "HEYGEN_DEFAULT_AVATAR_ID", "default_avatar")
        heygen_voice_id: str = voice_id or getattr(settings, "HEYGEN_DEFAULT_VOICE_ID", "")

        payload: dict[str, Any] = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": heygen_avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": script,
                        "voice_id": heygen_voice_id,
                        "speed": 1.0,
                    },
                    "background": {
                        "type": "color",
                        "value": "#FAFAFA",
                    },
                }
            ],
            "dimension": {"width": width, "height": height},
            "aspect_ratio": None,
            "test": getattr(settings, "HEYGEN_TEST_MODE", True),
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{HEYGEN_BASE_URL}/v2/video/generate",
                json=payload,
                headers=self._headers,
            )

        self._raise_for_status(resp, "generate_video")
        data = resp.json()
        video_id: str = data["data"]["video_id"]
        logger.info("heygen_video_queued", heygen_video_id=video_id)
        return video_id

    async def get_video_status(self, heygen_video_id: str) -> dict[str, Any]:
        """
        Poll the status of a HeyGen video generation job.

        Returns a dict with at minimum: ``{"status": "...", "video_url": "..."}``
        Possible statuses: ``pending``, ``processing``, ``completed``, ``failed``.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{HEYGEN_BASE_URL}/v1/video_status.get",
                params={"video_id": heygen_video_id},
                headers=self._headers,
            )

        self._raise_for_status(resp, "get_video_status")
        data = resp.json().get("data", {})
        return {
            "status": data.get("status", "unknown"),
            "video_url": data.get("video_url"),
            "thumbnail_url": data.get("thumbnail_url"),
            "duration": data.get("duration"),
            "error": data.get("error"),
        }

    # ------------------------------------------------------------------
    # Avatar management
    # ------------------------------------------------------------------

    async def list_avatars(self) -> list[dict[str, Any]]:
        """List available HeyGen avatar IDs."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{HEYGEN_BASE_URL}/v2/avatars",
                headers=self._headers,
            )
        self._raise_for_status(resp, "list_avatars")
        return resp.json().get("data", {}).get("avatars", [])

    async def list_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """List available HeyGen voice IDs, optionally filtered by language."""
        params: dict[str, str] = {}
        if language:
            params["language"] = language
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{HEYGEN_BASE_URL}/v2/voices",
                params=params,
                headers=self._headers,
            )
        self._raise_for_status(resp, "list_voices")
        return resp.json().get("data", {}).get("voices", [])

    # ------------------------------------------------------------------
    # Streaming (real-time avatar)
    # ------------------------------------------------------------------

    async def create_streaming_session(
        self,
        avatar_id: str | None = None,
        quality: str = "medium",
    ) -> dict[str, Any]:
        """
        Create a HeyGen real-time streaming session.

        Returns ``{"session_id": ..., "sdp": ..., "ice_servers": [...]}``
        which the frontend can use to establish a WebRTC connection.
        """
        heygen_avatar_id = avatar_id or getattr(settings, "HEYGEN_DEFAULT_AVATAR_ID", "default_avatar")
        payload = {
            "avatar_id": heygen_avatar_id,
            "quality": quality,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{HEYGEN_BASE_URL}/v1/streaming.new",
                json=payload,
                headers=self._headers,
            )
        self._raise_for_status(resp, "create_streaming_session")
        return resp.json().get("data", {})

    async def send_streaming_text(self, session_id: str, text: str) -> None:
        """Send text to a streaming session for real-time lip-sync."""
        payload = {
            "session_id": session_id,
            "text": text,
            "task_type": "repeat",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{HEYGEN_BASE_URL}/v1/streaming.task",
                json=payload,
                headers=self._headers,
            )
        self._raise_for_status(resp, "send_streaming_text")

    async def close_streaming_session(self, session_id: str) -> None:
        """Terminate a HeyGen streaming session."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{HEYGEN_BASE_URL}/v1/streaming.stop",
                json={"session_id": session_id},
                headers=self._headers,
            )
        try:
            self._raise_for_status(resp, "close_streaming_session")
        except HeyGenError:
            # Best-effort close — don't propagate errors
            logger.warning("heygen_close_failed", session_id=session_id)

    async def submit_streaming_sdp(
        self,
        session_id: str,
        sdp: str,
    ) -> dict[str, Any]:
        """Exchange WebRTC SDP answer with HeyGen."""
        payload = {"session_id": session_id, "sdp": {"type": "answer", "sdp": sdp}}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{HEYGEN_BASE_URL}/v1/streaming.sdp",
                json=payload,
                headers=self._headers,
            )
        self._raise_for_status(resp, "submit_streaming_sdp")
        return resp.json().get("data", {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(resp: httpx.Response, action: str) -> None:
        if resp.status_code >= 400:
            body = ""
            try:
                body = resp.json().get("message", resp.text)
            except Exception:
                body = resp.text
            raise HeyGenError(f"HeyGen {action} failed [{resp.status_code}]: {body}")
