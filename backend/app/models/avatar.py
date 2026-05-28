"""
Avatar model — digital human appearance asset.

Stores a reference to the source media, extracted face embeddings,
processing status, and rendering metadata.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.video import Video
    from app.models.agent import Agent


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AvatarSourceType(str, enum.Enum):
    PHOTO = "photo"
    VIDEO = "video"
    GENERATED = "generated"


class AvatarStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Avatar(UUIDBase):
    """
    Digital human avatar asset.

    The face_embedding field is a float array stored as a PostgreSQL ARRAY,
    suitable for cosine-similarity queries via pgvector when enabled.
    For large-scale ANN search the embedding is also mirrored into Qdrant.
    """

    __tablename__ = "avatars"

    # ------------------------------------------------------------------ identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User-assigned friendly name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description / use-case notes",
    )

    # ------------------------------------------------------------------ ownership
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who created this avatar",
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning organisation",
    )

    # ------------------------------------------------------------------ source media
    source_type: Mapped[AvatarSourceType] = mapped_column(
        Enum(AvatarSourceType, name="avatar_source_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="How the avatar was created",
    )
    source_file_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Object-storage URL of the original upload",
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Preview image URL",
    )

    # ------------------------------------------------------------------ AI artifacts
    face_embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
        comment="512-d or 1024-d face representation vector",
    )
    motion_template_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="URL of the pre-computed motion template (e.g. .pkl / .npz)",
    )

    # ------------------------------------------------------------------ status
    status: Mapped[AvatarStatus] = mapped_column(
        Enum(AvatarStatus, name="avatar_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AvatarStatus.PROCESSING,
        server_default=text("'processing'"),
        comment="Current processing state",
    )
    processing_duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Wall-clock seconds taken for the processing pipeline",
    )

    # ------------------------------------------------------------------ metadata / quality
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Arbitrary structured data: face landmarks, quality_score, "
            "bounding_box, pose_angles, illumination_score, …"
        ),
    )

    # ------------------------------------------------------------------ visibility / usage
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Shared across the organisation (True) or private to the creator",
    )
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of videos rendered with this avatar",
    )

    # ------------------------------------------------------------------ relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="avatars",
        lazy="selectin",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="avatars",
        lazy="selectin",
    )
    videos: Mapped[list["Video"]] = relationship(
        "Video",
        back_populates="avatar",
        lazy="noload",
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="avatar",
        lazy="noload",
    )
