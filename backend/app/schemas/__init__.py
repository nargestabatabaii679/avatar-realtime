"""
schemas/__init__.py
-------------------
Centralised re-export of every Pydantic schema so that application code and
API routers can do::

    from app.schemas import UserCreate, VideoGenerateRequest, AgentChatResponse, …

Import groups follow the same order as the models package for readability.
"""

# ── User / Auth ──────────────────────────────────────────────────────────────
from app.schemas.user import (
    APIKeyResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdateResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserBase,
    UserCreate,
    UserInDB,
    UserListResponse,
    UserLogin,
    UserResponse,
    UserUpdate,
)

# ── Avatar ───────────────────────────────────────────────────────────────────
from app.schemas.avatar import (
    AvatarCreate,
    AvatarEmbeddingResponse,
    AvatarListResponse,
    AvatarMetadata,
    AvatarResponse,
    AvatarStatusResponse,
    AvatarUpdate,
    AvatarUploadResponse,
)

# ── Voice ────────────────────────────────────────────────────────────────────
from app.schemas.voice import (
    TTSSynthesisRequest,
    TTSSynthesisResponse,
    VoiceCloneRequest,
    VoiceCloneResponse,
    VoiceCreate,
    VoiceListResponse,
    VoiceMetadata,
    VoiceResponse,
    VoiceUpdate,
)

# ── Video ────────────────────────────────────────────────────────────────────
from app.schemas.video import (
    VideoDownloadResponse,
    VideoGenerateRequest,
    VideoJobResponse,
    VideoListResponse,
    VideoRenderSettings,
    VideoResponse,
    VideoShareResponse,
    VideoStatusResponse,
    VideoUpdate,
)

# ── Agent ────────────────────────────────────────────────────────────────────
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
    ChatMessage,
    LLMConfig,
    PersonalityTraits,
    RAGSource,
)

# ── Knowledge & Documents ────────────────────────────────────────────────────
from app.schemas.knowledge import (
    ChunkingSettings,
    DocumentListResponse,
    DocumentMetadata,
    DocumentResponse,
    DocumentUploadResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseSettings,
    KnowledgeBaseUpdate,
    ReindexRequest,
    RetrievalSettings,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    URLIngestRequest,
)

# ── Analytics ────────────────────────────────────────────────────────────────
from app.schemas.analytics import (
    AgentStats,
    AnalyticsEventListResponse,
    AnalyticsEventResponse,
    ContentPerformanceResponse,
    DashboardStats,
    EventFilter,
    GPUMetrics,
    GPUWorkerMetrics,
    StorageStats,
    TimeSeriesData,
    TimeSeriesPoint,
    TopAgentEntry,
    TopVideoEntry,
    UsageMetrics,
    UserStats,
    VideoStats,
)

__all__ = [
    # User / Auth
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    "UserResponse",
    "UserLogin",
    "TokenResponse",
    "RefreshTokenRequest",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "UserListResponse",
    "APIKeyResponse",
    "ProfileUpdateResponse",
    # Avatar
    "AvatarCreate",
    "AvatarUpdate",
    "AvatarResponse",
    "AvatarUploadResponse",
    "AvatarStatusResponse",
    "AvatarListResponse",
    "AvatarMetadata",
    "AvatarEmbeddingResponse",
    # Voice
    "VoiceCreate",
    "VoiceUpdate",
    "VoiceResponse",
    "VoiceCloneRequest",
    "VoiceCloneResponse",
    "VoiceListResponse",
    "VoiceMetadata",
    "TTSSynthesisRequest",
    "TTSSynthesisResponse",
    # Video
    "VideoGenerateRequest",
    "VideoRenderSettings",
    "VideoResponse",
    "VideoStatusResponse",
    "VideoUpdate",
    "VideoListResponse",
    "VideoJobResponse",
    "VideoDownloadResponse",
    "VideoShareResponse",
    # Agent
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "AgentListResponse",
    "AgentChatRequest",
    "AgentChatResponse",
    "ChatMessage",
    "PersonalityTraits",
    "LLMConfig",
    "RAGSource",
    # Knowledge
    "KnowledgeBaseCreate",
    "KnowledgeBaseUpdate",
    "KnowledgeBaseResponse",
    "KnowledgeBaseListResponse",
    "KnowledgeBaseSettings",
    "ChunkingSettings",
    "RetrievalSettings",
    "DocumentResponse",
    "DocumentUploadResponse",
    "DocumentListResponse",
    "DocumentMetadata",
    "URLIngestRequest",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "ReindexRequest",
    # Analytics
    "DashboardStats",
    "VideoStats",
    "StorageStats",
    "AgentStats",
    "UserStats",
    "UsageMetrics",
    "GPUMetrics",
    "GPUWorkerMetrics",
    "EventFilter",
    "AnalyticsEventResponse",
    "AnalyticsEventListResponse",
    "TimeSeriesPoint",
    "TimeSeriesData",
    "ContentPerformanceResponse",
    "TopVideoEntry",
    "TopAgentEntry",
]
