"""
schemas/agent.py
----------------
Pydantic v2 schemas for the Agent domain.

Covers CRUD operations for agent configuration, real-time chat request /
response, and conversation retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.agent import AgentRole


# ---------------------------------------------------------------------------
# Personality / LLM config sub-schemas
# ---------------------------------------------------------------------------


class PersonalityTraits(BaseModel):
    """Free-form personality configuration stored in the JSONB column."""

    tone: str | None = Field(
        None,
        description="Desired communication tone, e.g. 'professional', 'friendly', 'empathetic'",
    )
    verbosity: str | None = Field(
        None,
        description="Response length preference: 'concise', 'balanced', 'detailed'",
    )
    empathy_level: str | None = Field(
        None,
        description="Empathy calibration: 'low', 'medium', 'high'",
    )
    formality: str | None = Field(
        None,
        description="Formality level: 'informal', 'neutral', 'formal'",
    )
    language_style: str | None = Field(
        None,
        description="Writing style: 'plain', 'technical', 'storytelling'",
    )
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class LLMConfig(BaseModel):
    """LLM provider and model configuration."""

    provider: str = Field(
        default="openai",
        description="Provider identifier: openai, anthropic, google, mistral, local",
    )
    model: str = Field(default="gpt-4o", description="Model name / version string")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=32768)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class AgentCreate(BaseModel):
    """Request body for POST /agents."""

    name: str = Field(min_length=1, max_length=255, description="Display name for the agent")
    description: str | None = Field(None, max_length=2000)
    role: AgentRole = Field(default=AgentRole.GENERAL)
    organization_id: uuid.UUID
    avatar_id: uuid.UUID | None = Field(None, description="Avatar UUID for video responses")
    voice_model_id: uuid.UUID | None = Field(None, description="Voice model UUID for TTS")
    knowledge_base_id: uuid.UUID | None = Field(None, description="Primary RAG knowledge source")
    llm_provider: str = Field(default="openai", max_length=100)
    llm_model: str = Field(default="gpt-4o", max_length=100)
    system_prompt: str | None = Field(None, max_length=32_000)
    personality_traits: PersonalityTraits = Field(default_factory=PersonalityTraits)
    capabilities: list[str] | None = Field(
        None,
        description="Feature flags, e.g. ['rag', 'web_search', 'calendar']",
    )
    is_active: bool = Field(default=True)
    is_public: bool = Field(default=False)
    webhook_url: AnyHttpUrl | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        allowed = {
            "rag", "web_search", "calendar", "crm", "email",
            "sms", "voice_call", "video_call", "analytics",
        }
        invalid = [cap for cap in v if cap not in allowed]
        if invalid:
            raise ValueError(f"Unknown capabilities: {invalid}. Allowed: {sorted(allowed)}")
        return list(dict.fromkeys(v))  # deduplicate preserving order


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class AgentUpdate(BaseModel):
    """Request body for PATCH /agents/{id}."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    role: AgentRole | None = None
    avatar_id: uuid.UUID | None = None
    voice_model_id: uuid.UUID | None = None
    knowledge_base_id: uuid.UUID | None = None
    llm_provider: str | None = Field(None, max_length=100)
    llm_model: str | None = Field(None, max_length=100)
    system_prompt: str | None = Field(None, max_length=32_000)
    personality_traits: PersonalityTraits | None = None
    capabilities: list[str] | None = None
    is_active: bool | None = None
    is_public: bool | None = None
    webhook_url: AnyHttpUrl | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class AgentResponse(BaseModel):
    """Full agent representation returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    role: AgentRole
    user_id: uuid.UUID
    organization_id: uuid.UUID
    avatar_id: uuid.UUID | None
    voice_model_id: uuid.UUID | None
    knowledge_base_id: uuid.UUID | None
    llm_provider: str
    llm_model: str
    system_prompt: str | None
    personality_traits: dict[str, Any]
    capabilities: list[str] | None
    is_active: bool
    is_public: bool
    conversation_count: int
    avg_rating: float | None
    webhook_url: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("personality_traits", mode="before")
    @classmethod
    def coerce_traits(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}

    @field_validator("capabilities", mode="before")
    @classmethod
    def coerce_capabilities(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        return list(v) if not isinstance(v, list) else v


# ---------------------------------------------------------------------------
# Chat schemas
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single message in a conversation turn."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=10_000)
    timestamp: datetime | None = None


class AgentChatRequest(BaseModel):
    """
    Request body for POST /agents/{id}/chat.

    ``session_id`` ties multiple API calls into a single logical conversation.
    If omitted, a new session is created.  ``history`` carries prior turns so
    that stateless clients can maintain context without server-side session
    storage (though the server also persists conversations).
    """

    session_id: str | None = Field(
        None,
        max_length=255,
        description="Opaque session token; omit to start a new session",
    )
    message: str = Field(
        min_length=1,
        max_length=10_000,
        description="User's latest message",
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversation turns for stateless clients",
    )
    generate_video: bool = Field(
        default=False,
        description="If True, trigger avatar video generation for this response",
    )
    language: str = Field(
        default="en",
        max_length=10,
        description="Desired response language override",
    )
    stream: bool = Field(
        default=False,
        description="If True, use Server-Sent Events for streaming the response",
    )

    model_config = ConfigDict(extra="forbid")


class RAGSource(BaseModel):
    """A single retrieved RAG context chunk referenced by the response."""

    document_id: uuid.UUID
    filename: str
    chunk_index: int
    relevance_score: float = Field(ge=0.0, le=1.0)
    excerpt: str = Field(description="Short text excerpt from the retrieved chunk")


class AgentChatResponse(BaseModel):
    """Response to a single chat turn."""

    session_id: str
    conversation_id: uuid.UUID
    message: str = Field(description="Agent's response text")
    role: Literal["assistant"] = "assistant"
    timestamp: datetime
    tokens_used: int | None = None
    latency_ms: int | None = None
    rag_sources: list[RAGSource] = Field(
        default_factory=list,
        description="Knowledge-base chunks that informed this response",
    )
    video_job_id: str | None = Field(
        None,
        description="Celery task ID of the avatar video generation job, if requested",
    )
    video_url: str | None = Field(
        None,
        description="URL of the generated video (available after the job completes)",
    )


# ---------------------------------------------------------------------------
# List response
# ---------------------------------------------------------------------------


class AgentListResponse(BaseModel):
    """Paginated list of agents."""

    items: list[AgentResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
