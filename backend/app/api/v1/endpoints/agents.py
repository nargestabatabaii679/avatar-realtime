"""
app/api/v1/endpoints/agents.py
-------------------------------
AI Agent management: create/update agents with avatar, voice, knowledge base,
personality; SSE streaming chat; conversation history; embed codes; analytics.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    TokenData,
    assert_owner_or_admin,
    get_current_token_data,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models (Agent / Conversation are defined in models/ but not yet
# materialised as imports here to avoid circular deps — they are referenced
# via inline select() queries using string table names via ORM).
# ---------------------------------------------------------------------------


class PersonalityConfig(BaseModel):
    system_prompt: str = Field(
        "You are a helpful AI assistant.",
        max_length=8000,
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=64, le=8192)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    language: str = Field("en", max_length=10)
    persona_name: str | None = Field(None, max_length=100)


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    avatar_id: uuid.UUID | None = None
    voice_model_id: uuid.UUID | None = None
    knowledge_base_id: uuid.UUID | None = None
    personality: PersonalityConfig = PersonalityConfig()
    is_public: bool = False
    llm_model: str = Field("gpt-4o", max_length=100)
    enable_rag: bool = True
    enable_memory: bool = True


class UpdateAgentRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    avatar_id: uuid.UUID | None = None
    voice_model_id: uuid.UUID | None = None
    knowledge_base_id: uuid.UUID | None = None
    personality: PersonalityConfig | None = None
    is_public: bool | None = None
    llm_model: str | None = Field(None, max_length=100)
    enable_rag: bool | None = None
    enable_memory: bool | None = None


class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    avatar_id: uuid.UUID | None
    voice_model_id: uuid.UUID | None
    knowledge_base_id: uuid.UUID | None
    personality: dict
    is_public: bool
    llm_model: str
    enable_rag: bool
    enable_memory: bool
    conversation_count: int
    user_id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
    total: int
    page: int
    page_size: int


class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str
    timestamp: datetime | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    conversation_id: uuid.UUID | None = None
    stream: bool = True


class ConversationSummary(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None
    messages: list[ChatMessage]
    created_at: datetime
    updated_at: datetime


class EmbedCodeResponse(BaseModel):
    script_tag: str
    iframe_url: str
    api_endpoint: str
    agent_id: str


class AgentAnalyticsResponse(BaseModel):
    agent_id: uuid.UUID
    total_conversations: int
    total_messages: int
    avg_messages_per_conversation: float
    avg_response_time_ms: float | None
    top_topics: list[str]
    satisfaction_score: float | None
    daily_active_users: int
    period_days: int


# ---------------------------------------------------------------------------
# DB helpers (inline — Agent model referenced via import guard)
# ---------------------------------------------------------------------------


async def _get_agent_or_404(db: AsyncSession, agent_id: uuid.UUID) -> Any:
    try:
        from app.models.agent import Agent  # noqa: PLC0415
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent model not available",
        )
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_deleted.is_(False))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


# ---------------------------------------------------------------------------
# LLM streaming helper
# ---------------------------------------------------------------------------


async def _stream_llm_response(
    agent: Any,
    user_message: str,
    conversation_history: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from the LLM (OpenAI-compatible API).

    Formats output as Server-Sent Events (SSE).
    """
    try:
        import openai  # noqa: PLC0415

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        personality = agent.personality or {}

        messages: list[dict[str, str]] = [
            {"role": "system", "content": personality.get("system_prompt", "You are a helpful AI.")}
        ]
        messages.extend(conversation_history[-20:])  # Last 20 messages for context
        messages.append({"role": "user", "content": user_message})

        # RAG augmentation
        if getattr(agent, "enable_rag", False) and agent.knowledge_base_id:
            try:
                rag_context = await _retrieve_rag_context(
                    str(agent.knowledge_base_id), user_message
                )
                if rag_context:
                    messages[0]["content"] += f"\n\nRelevant context:\n{rag_context}"
            except Exception as exc:  # noqa: BLE001
                logger.warning("rag_retrieval_failed", error=str(exc))

        model = getattr(agent, "llm_model", settings.OPENAI_MODEL_CHAT) or settings.OPENAI_MODEL_CHAT
        temperature = float(personality.get("temperature", settings.OPENAI_TEMPERATURE))
        max_tokens = int(personality.get("max_tokens", settings.OPENAI_MAX_TOKENS))

        async with client.beta.chat.completions.stream(  # type: ignore[attr-defined]
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    sse_data = json.dumps({"type": "token", "content": delta})
                    yield f"data: {sse_data}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except ImportError:
        # Fallback stub response when OpenAI is not installed
        stub = f"Echo: {user_message}"
        for word in stub.split():
            sse_data = json.dumps({"type": "token", "content": word + " "})
            yield f"data: {sse_data}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as exc:  # noqa: BLE001
        logger.error("llm_stream_error", error=str(exc))
        error_data = json.dumps({"type": "error", "content": "Failed to generate response"})
        yield f"data: {error_data}\n\n"


async def _retrieve_rag_context(knowledge_base_id: str, query: str, top_k: int = 5) -> str:
    """Retrieve relevant chunks from Qdrant for RAG augmentation."""
    try:
        from qdrant_client import QdrantClient  # noqa: PLC0415
        from qdrant_client.models import SearchRequest  # noqa: PLC0415
        import openai  # noqa: PLC0415

        # Embed query
        oai = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        embed_resp = await oai.embeddings.create(
            model=settings.OPENAI_MODEL_EMBEDDING,
            input=query,
        )
        query_vector = embed_resp.data[0].embedding

        client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        collection = f"kb_{knowledge_base_id}"

        results = client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=top_k,
        )
        chunks = [r.payload.get("text", "") for r in results if r.payload]
        return "\n\n".join(chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag_context_failed", error=str(exc))
        return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an AI agent",
)
async def create_agent(
    payload: CreateAgentRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new AI digital-human agent.

    An agent combines an avatar (appearance), voice model (speech), knowledge
    base (RAG), and personality configuration (system prompt, temperature).
    """
    try:
        from app.models.agent import Agent  # noqa: PLC0415
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent model not available",
        )

    if token_data.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    agent = Agent(
        name=payload.name,
        description=payload.description,
        user_id=token_data.user_id,
        organization_id=token_data.organization_id,
        avatar_id=payload.avatar_id,
        voice_model_id=payload.voice_model_id,
        knowledge_base_id=payload.knowledge_base_id,
        personality=payload.personality.model_dump(),
        is_public=payload.is_public,
        llm_model=payload.llm_model,
        enable_rag=payload.enable_rag,
        enable_memory=payload.enable_memory,
    )
    db.add(agent)
    await db.flush()

    logger.info("agent_created", agent_id=str(agent.id), user_id=str(token_data.user_id))
    return agent


@router.get(
    "",
    response_model=AgentListResponse,
    summary="List agents",
)
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> AgentListResponse:
    """List agents owned by the current user."""
    try:
        from app.models.agent import Agent  # noqa: PLC0415
    except ImportError:
        return AgentListResponse(items=[], total=0, page=page, page_size=page_size)

    query = select(Agent).where(
        Agent.user_id == token_data.user_id, Agent.is_deleted.is_(False)
    )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Agent.created_at.desc()).offset(offset).limit(page_size)
    )
    agents = result.scalars().all()

    return AgentListResponse(
        items=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent details",
)
async def get_agent(
    agent_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Any:
    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)
    return agent


@router.put(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update agent configuration",
)
async def update_agent(
    agent_id: uuid.UUID,
    payload: UpdateAgentRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update agent metadata, personality, or linked resources."""
    try:
        from app.models.agent import Agent  # noqa: PLC0415
    except ImportError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent model unavailable")

    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)

    update_values: dict[str, Any] = {}
    if payload.name is not None:
        update_values["name"] = payload.name
    if payload.description is not None:
        update_values["description"] = payload.description
    if payload.avatar_id is not None:
        update_values["avatar_id"] = payload.avatar_id
    if payload.voice_model_id is not None:
        update_values["voice_model_id"] = payload.voice_model_id
    if payload.knowledge_base_id is not None:
        update_values["knowledge_base_id"] = payload.knowledge_base_id
    if payload.personality is not None:
        update_values["personality"] = payload.personality.model_dump()
    if payload.is_public is not None:
        update_values["is_public"] = payload.is_public
    if payload.llm_model is not None:
        update_values["llm_model"] = payload.llm_model
    if payload.enable_rag is not None:
        update_values["enable_rag"] = payload.enable_rag
    if payload.enable_memory is not None:
        update_values["enable_memory"] = payload.enable_memory

    if update_values:
        await db.execute(update(Agent).where(Agent.id == agent_id).values(**update_values))
        await db.refresh(agent)

    return agent


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agent",
)
async def delete_agent(
    agent_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> None:
    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)
    agent.soft_delete()
    logger.info("agent_deleted", agent_id=str(agent_id))


@router.post(
    "/{agent_id}/chat",
    summary="Send a message to the agent (SSE streaming)",
)
async def chat_with_agent(
    agent_id: uuid.UUID,
    payload: ChatRequest,
    request: Request,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Send a message to an AI agent and receive a streamed response (SSE).

    The response is streamed as Server-Sent Events with the following event types:
    - ``token`` — a single generated token
    - ``done`` — stream complete
    - ``error`` — generation failed

    Conversation history is maintained across calls using ``conversation_id``.
    """
    agent = await _get_agent_or_404(db, agent_id)

    # Allow chatting with own agents or public agents
    if not getattr(agent, "is_public", False):
        assert_owner_or_admin(agent.user_id, token_data)

    # Load conversation history
    conversation_history: list[dict[str, str]] = []
    conversation_id = payload.conversation_id

    try:
        from app.models.conversation import Conversation, ConversationMessage  # noqa: PLC0415

        if conversation_id:
            conv_result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.agent_id == agent_id,
                    Conversation.is_deleted.is_(False),
                )
            )
            conversation = conv_result.scalar_one_or_none()
            if conversation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found",
                )
            # Fetch recent messages
            msgs_result = await db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.asc())
                .limit(40)
            )
            for msg in msgs_result.scalars().all():
                conversation_history.append({"role": msg.role, "content": msg.content})
        else:
            # Create new conversation
            conversation = Conversation(
                agent_id=agent_id,
                user_id=token_data.user_id,
            )
            db.add(conversation)
            await db.flush()
            conversation_id = conversation.id

        # Persist user message
        user_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content=payload.message,
        )
        db.add(user_msg)
        await db.flush()
    except ImportError:
        # Conversation models not yet created — proceed without persistence
        pass

    if payload.stream:
        return StreamingResponse(
            _stream_llm_response(agent, payload.message, conversation_history),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
                "X-Conversation-ID": str(conversation_id) if conversation_id else "",
            },
        )
    else:
        # Non-streaming — collect the full response
        full_response = ""
        async for chunk in _stream_llm_response(agent, payload.message, conversation_history):
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:])
                    if data.get("type") == "token":
                        full_response += data.get("content", "")
                except json.JSONDecodeError:
                    pass

        return StreamingResponse(
            iter([json.dumps({"response": full_response, "conversation_id": str(conversation_id)})]),
            media_type="application/json",
        )


@router.get(
    "/{agent_id}/conversations",
    response_model=list[ConversationSummary],
    summary="List conversations for this agent",
)
async def list_conversations(
    agent_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)

    try:
        from app.models.conversation import Conversation  # noqa: PLC0415

        offset = (page - 1) * page_size
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.agent_id == agent_id,
                Conversation.user_id == token_data.user_id,
                Conversation.is_deleted.is_(False),
            )
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all()
    except ImportError:
        return []


@router.get(
    "/{agent_id}/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get full conversation history",
)
async def get_conversation(
    agent_id: uuid.UUID,
    conversation_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> Any:
    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)

    try:
        from app.models.conversation import Conversation, ConversationMessage  # noqa: PLC0415

        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.agent_id == agent_id,
                Conversation.is_deleted.is_(False),
            )
        )
        conv = conv_result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

        msgs_result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
        )
        messages = [
            ChatMessage(role=m.role, content=m.content, timestamp=m.created_at)
            for m in msgs_result.scalars().all()
        ]
        return ConversationDetail(
            id=conv.id,
            agent_id=agent_id,
            title=getattr(conv, "title", None),
            messages=messages,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation model not available",
        )


@router.post(
    "/{agent_id}/test",
    summary="Test the agent with a sample query",
)
async def test_agent(
    agent_id: uuid.UUID,
    payload: ChatRequest,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Send a test message to the agent and receive a complete (non-streamed) response.
    Useful for admin validation without creating persistent conversations.
    """
    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)

    full_response = ""
    import time  # noqa: PLC0415
    start_time = time.perf_counter()

    async for chunk in _stream_llm_response(agent, payload.message, []):
        if chunk.startswith("data: "):
            try:
                data = json.loads(chunk[6:])
                if data.get("type") == "token":
                    full_response += data.get("content", "")
            except json.JSONDecodeError:
                pass

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return {
        "query": payload.message,
        "response": full_response,
        "response_time_ms": duration_ms,
        "agent_id": str(agent_id),
        "llm_model": getattr(agent, "llm_model", "unknown"),
    }


@router.post(
    "/{agent_id}/embed",
    response_model=EmbedCodeResponse,
    summary="Get embed code for integrating agent into a website",
)
async def get_embed_code(
    agent_id: uuid.UUID,
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> EmbedCodeResponse:
    """Return JavaScript/iframe embed code for embedding the agent widget on any website."""
    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)

    base_url = str(settings.CORS_ORIGINS[0]) if settings.CORS_ORIGINS else "http://localhost:3000"
    api_base = f"http://{settings.HOST}:{settings.PORT}"

    iframe_url = f"{base_url}/embed/agent/{agent_id}"
    api_endpoint = f"{api_base}/api/v1/agents/{agent_id}/chat"

    script_tag = (
        f'<script src="{base_url}/embed/agent.js" '
        f'data-agent-id="{agent_id}" '
        f'data-api-url="{api_base}/api/v1" '
        f'async></script>'
    )

    return EmbedCodeResponse(
        script_tag=script_tag,
        iframe_url=iframe_url,
        api_endpoint=api_endpoint,
        agent_id=str(agent_id),
    )


@router.get(
    "/{agent_id}/analytics",
    response_model=AgentAnalyticsResponse,
    summary="Get agent performance analytics",
)
async def get_agent_analytics(
    agent_id: uuid.UUID,
    period_days: int = Query(30, ge=1, le=365),
    token_data: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
) -> AgentAnalyticsResponse:
    """Return conversation and performance metrics for the specified period."""
    agent = await _get_agent_or_404(db, agent_id)
    assert_owner_or_admin(agent.user_id, token_data)

    # Stub metrics — in production these would be computed from analytics tables
    return AgentAnalyticsResponse(
        agent_id=agent_id,
        total_conversations=0,
        total_messages=0,
        avg_messages_per_conversation=0.0,
        avg_response_time_ms=None,
        top_topics=[],
        satisfaction_score=None,
        daily_active_users=0,
        period_days=period_days,
    )
