from __future__ import annotations

import asyncio
import json
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/realtime", tags=["Real-Time Avatar"])

# Active WebSocket sessions: session_id -> WebSocket
_active_sessions: dict[str, WebSocket] = {}


@router.websocket("/connect")
async def realtime_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    agent_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    avatar_id: Optional[str] = Query(None),
    use_heygen: bool = Query(False),
):
    """
    Real-time conversational avatar WebSocket endpoint.

    Protocol:
    - Client → Server: {"type": "audio_chunk", "data": "<base64_pcm_16k>"}
                       {"type": "text", "content": "Hello"}
                       {"type": "end_turn"}
                       {"type": "ping"}
    - Server → Client: {"type": "transcription", "text": "...", "is_final": true}
                       {"type": "llm_chunk", "text": "..."}
                       {"type": "audio_chunk", "data": "<base64_pcm>"}
                       {"type": "turn_complete", "latency_ms": 850}
                       {"type": "error", "code": "...", "message": "..."}
    """
    # Authenticate
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    sid = session_id or str(uuid.uuid4())
    await websocket.accept()
    _active_sessions[sid] = websocket

    log = logger.bind(session_id=sid, user_id=user_id)
    log.info("realtime_session_started")

    audio_buffer: list[bytes] = []

    # Optionally create a HeyGen streaming session for lip-synced avatar
    heygen_session_id: Optional[str] = None
    heygen_sdp: Optional[str] = None
    if use_heygen and avatar_id:
        try:
            from app.services.heygen import HeyGenService  # noqa: PLC0415
            heygen = HeyGenService()
            streaming_data = await heygen.create_streaming_session(avatar_id=avatar_id)
            heygen_session_id = streaming_data.get("session_id")
            heygen_sdp = streaming_data.get("sdp", {}).get("sdp")
            log.info("heygen_streaming_session_created", heygen_session_id=heygen_session_id)
        except Exception as exc:
            log.warning("heygen_streaming_init_failed", error=str(exc))

    try:
        connected_payload: dict = {"type": "connected", "session_id": sid}
        if heygen_session_id:
            connected_payload["heygen_session_id"] = heygen_session_id
            connected_payload["heygen_sdp"] = heygen_sdp
        await websocket.send_json(connected_payload)

        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "code": "INVALID_JSON"})
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "audio_chunk":
                import base64
                chunk_bytes = base64.b64decode(msg["data"])
                audio_buffer.append(chunk_bytes)

            elif msg_type == "end_turn" or msg_type == "text":
                import time
                start_ts = time.time()

                if msg_type == "text":
                    user_text = msg.get("content", "")
                else:
                    # Transcribe audio buffer
                    if not audio_buffer:
                        await websocket.send_json({"type": "error", "code": "NO_AUDIO"})
                        continue

                    audio_data = b"".join(audio_buffer)
                    audio_buffer.clear()

                    try:
                        user_text = await _transcribe_audio(audio_data)
                        await websocket.send_json({
                            "type": "transcription",
                            "text": user_text,
                            "is_final": True,
                        })
                    except Exception as e:
                        await websocket.send_json({"type": "error", "code": "STT_FAILED", "message": str(e)})
                        continue

                if not user_text.strip():
                    continue

                # LLM response
                try:
                    await websocket.send_json({"type": "llm_thinking"})
                    llm_response = await _get_llm_response(user_text, agent_id, user_id, sid)

                    for chunk in _split_into_chunks(llm_response, size=50):
                        await websocket.send_json({"type": "llm_chunk", "text": chunk})
                        await asyncio.sleep(0.01)

                except Exception as e:
                    await websocket.send_json({"type": "error", "code": "LLM_FAILED", "message": str(e)})
                    continue

                # TTS synthesis + optional HeyGen lip-sync
                try:
                    if heygen_session_id:
                        # Send text to HeyGen streaming session for real-time lip-sync
                        try:
                            from app.services.heygen import HeyGenService  # noqa: PLC0415
                            heygen = HeyGenService()
                            await heygen.send_streaming_text(heygen_session_id, llm_response)
                            await websocket.send_json({
                                "type": "heygen_speaking",
                                "session_id": heygen_session_id,
                                "text": llm_response,
                            })
                        except Exception as heygen_exc:
                            log.warning("heygen_streaming_text_failed", error=str(heygen_exc))

                    # Always synthesize audio as fallback / primary
                    audio_bytes = await _synthesize_speech(llm_response, agent_id)
                    import base64
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "data": base64.b64encode(audio_bytes).decode(),
                        "sample_rate": 24000,
                    })
                except Exception as e:
                    log.warning("tts_failed", error=str(e))

                latency_ms = int((time.time() - start_ts) * 1000)
                await websocket.send_json({"type": "turn_complete", "latency_ms": latency_ms})
                log.info("turn_completed", latency_ms=latency_ms)

    except WebSocketDisconnect:
        log.info("realtime_session_disconnected")
    except Exception as e:
        log.error("realtime_session_error", error=str(e))
        try:
            await websocket.send_json({"type": "error", "code": "SERVER_ERROR", "message": str(e)})
        except Exception:
            pass
    finally:
        _active_sessions.pop(sid, None)
        if heygen_session_id:
            try:
                from app.services.heygen import HeyGenService  # noqa: PLC0415
                heygen = HeyGenService()
                await heygen.close_streaming_session(heygen_session_id)
            except Exception:
                pass
        log.info("realtime_session_ended")


async def _transcribe_audio(audio_data: bytes) -> str:
    """Transcribe PCM audio bytes using Whisper."""
    import tempfile, os
    from app.ml.voice.whisper_stt import WhisperSTT

    stt = WhisperSTT()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_data)
        tmp_path = f.name

    try:
        result = await stt.transcribe(tmp_path)
        return result.get("text", "")
    finally:
        os.unlink(tmp_path)


async def _get_llm_response(
    user_text: str,
    agent_id: Optional[str],
    user_id: str,
    session_id: str,
) -> str:
    """Get LLM response, optionally using agent's knowledge base and system prompt."""
    from app.ml.llm.llm_router import LLMRouter

    system_prompt = "You are a helpful AI assistant. Be concise and friendly."
    llm_model = settings.LLM_MODEL if hasattr(settings, "LLM_MODEL") else "gpt-4o-mini"
    llm_provider = settings.LLM_PROVIDER if hasattr(settings, "LLM_PROVIDER") else "openai"

    if agent_id:
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.agent import Agent
            async with AsyncSessionLocal() as db:
                agent = await db.get(Agent, uuid.UUID(agent_id))
            if agent:
                system_prompt = agent.system_prompt or system_prompt
                llm_model = agent.llm_model or llm_model
                llm_provider = agent.llm_provider or llm_provider

                # Use knowledge base if available
                if agent.knowledge_base_id:
                    from app.ml.rag.rag_chain import RAGChain
                    chain = RAGChain(
                        knowledge_base_id=str(agent.knowledge_base_id),
                        language="fa",
                        llm_provider=llm_provider,
                        llm_model=llm_model,
                    )
                    return await chain.answer(user_text)
        except Exception as e:
            logger.warning("agent_lookup_failed", error=str(e))

    llm = LLMRouter(provider=llm_provider, model=llm_model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    return await llm.complete(messages)


async def _synthesize_speech(text: str, agent_id: Optional[str] = None) -> bytes:
    """Synthesize speech and return raw WAV bytes."""
    import tempfile, os
    from app.ml.voice.xtts_engine import XTTSEngine

    tts = XTTSEngine()

    # Try to find agent's voice model
    voice_model_path = None
    if agent_id:
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.agent import Agent
            async with AsyncSessionLocal() as db:
                agent = await db.get(Agent, uuid.UUID(agent_id))
            if agent and agent.voice_model_id:
                from app.models.voice_model import VoiceModel
                async with AsyncSessionLocal() as db:
                    voice = await db.get(VoiceModel, agent.voice_model_id)
                if voice and voice.model_file_url:
                    import tempfile as tf
                    tmp_voice = tf.mktemp(suffix=".pth")
                    from app.services.storage.minio_service import download_to_path
                    obj = "/".join(voice.model_file_url.split("/")[1:])
                    await download_to_path("voices", obj, tmp_voice)
                    voice_model_path = tmp_voice
        except Exception:
            pass

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_out = f.name

    try:
        await tts.synthesize(
            text=text,
            language="fa",
            voice_model_path=voice_model_path,
            output_path=tmp_out,
        )
        with open(tmp_out, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_out)
        if voice_model_path:
            try:
                os.unlink(voice_model_path)
            except Exception:
                pass


def _split_into_chunks(text: str, size: int = 50) -> list[str]:
    """Split text into word-boundary chunks for streaming."""
    words = text.split()
    chunks = []
    current = []
    for word in words:
        current.append(word)
        if len(" ".join(current)) >= size:
            chunks.append(" ".join(current) + " ")
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


@router.get("/sessions")
async def list_active_sessions(
    current_user=Depends(lambda: None),
):
    """List currently active real-time sessions."""
    return {"active_sessions": len(_active_sessions), "session_ids": list(_active_sessions.keys())}


@router.post("/heygen/session", summary="Create a HeyGen real-time streaming session")
async def create_heygen_session(
    avatar_id: Optional[str] = None,
    quality: str = "medium",
    token: str = Query(...),
) -> dict:
    """
    Create a HeyGen streaming session and return the WebRTC offer SDP + ICE servers
    so the frontend can establish a direct video connection.
    """
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        from app.services.heygen import HeyGenService  # noqa: PLC0415
        heygen = HeyGenService()
        data = await heygen.create_streaming_session(avatar_id=avatar_id, quality=quality)
        return {"status": "ok", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/heygen/sdp", summary="Submit WebRTC SDP answer to HeyGen")
async def submit_heygen_sdp(
    session_id: str,
    sdp: str,
    token: str = Query(...),
) -> dict:
    """Exchange the WebRTC SDP answer with HeyGen to complete peer connection setup."""
    try:
        decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        from app.services.heygen import HeyGenService  # noqa: PLC0415
        heygen = HeyGenService()
        result = await heygen.submit_streaming_sdp(session_id=session_id, sdp=sdp)
        return {"status": "ok", "data": result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
