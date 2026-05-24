"""
models/__init__.py
------------------
Centralised import of every SQLAlchemy model so that:

1. Alembic's ``env.py`` can import ``Base.metadata`` with all tables already
   registered just by importing this package.
2. Application code can do ``from app.models import User, Video, …`` without
   knowing each module's location.
3. Relationship back-references resolve correctly at mapper configuration time
   because all model classes are in the same import graph.

Import order matters: independent models (base, organization) come first so
that FK targets exist before the referencing columns are mapped.
"""

from app.models.base import (
    AuditMixin,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDBase,
)

# ── Core tenant / identity ──────────────────────────────────────────────────
from app.models.organization import Organization, OrganizationPlan
from app.models.user import User, UserRole

# ── Media assets ────────────────────────────────────────────────────────────
from app.models.avatar import Avatar, AvatarSourceType, AvatarStatus
from app.models.voice_model import VoiceModel, VoiceStatus, TTSEngine

# ── Video pipeline ──────────────────────────────────────────────────────────
from app.models.video import Video, VideoResolution, VideoStatus
from app.models.video_job import VideoJob, JobType, JobStatus

# ── Knowledge & RAG ─────────────────────────────────────────────────────────
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus
from app.models.document import Document, DocumentFileType, DocumentStatus

# ── Agent ───────────────────────────────────────────────────────────────────
from app.models.agent import Agent, AgentRole

# ── Conversations ────────────────────────────────────────────────────────────
from app.models.conversation import Conversation, ConversationChannel

# ── Observability ────────────────────────────────────────────────────────────
from app.models.analytics import AnalyticsEvent
from app.models.audit_log import AuditLog

# ── Billing ──────────────────────────────────────────────────────────────────
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus

__all__ = [
    # Base
    "Base",
    "UUIDBase",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    # Organization
    "Organization",
    "OrganizationPlan",
    # User
    "User",
    "UserRole",
    # Avatar
    "Avatar",
    "AvatarSourceType",
    "AvatarStatus",
    # Voice
    "VoiceModel",
    "VoiceStatus",
    "TTSEngine",
    # Video
    "Video",
    "VideoResolution",
    "VideoStatus",
    # VideoJob
    "VideoJob",
    "JobType",
    "JobStatus",
    # Knowledge base
    "KnowledgeBase",
    "KnowledgeBaseStatus",
    # Document
    "Document",
    "DocumentFileType",
    "DocumentStatus",
    # Agent
    "Agent",
    "AgentRole",
    # Conversation
    "Conversation",
    "ConversationChannel",
    # Analytics
    "AnalyticsEvent",
    # Audit
    "AuditLog",
    # Subscription
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
]
