"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-15 10:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === ENUMS ===
    op.execute("CREATE TYPE userrole AS ENUM ('super_admin','admin','manager','creator','viewer')")
    op.execute("CREATE TYPE orgplan AS ENUM ('free','starter','professional','enterprise')")
    op.execute("CREATE TYPE avatarsource AS ENUM ('photo','video','multi_photo','generated')")
    op.execute("CREATE TYPE avatarstatuse AS ENUM ('uploading','processing','ready','failed')")
    op.execute("CREATE TYPE voicestatus AS ENUM ('cloning','ready','failed')")
    op.execute("CREATE TYPE ttsenginee AS ENUM ('xtts','cosyvoice','f5tts')")
    op.execute("CREATE TYPE videostatus AS ENUM ('queued','processing','rendering','completed','failed')")
    op.execute("CREATE TYPE resolution AS ENUM ('720p','1080p','4k')")
    op.execute("CREATE TYPE jobstatus AS ENUM ('pending','running','completed','failed','cancelled')")
    op.execute("CREATE TYPE documentstatus AS ENUM ('uploading','processing','ready','failed')")
    op.execute("CREATE TYPE filetype AS ENUM ('pdf','docx','pptx','xlsx','txt','url','product_catalog')")
    op.execute("CREATE TYPE channel AS ENUM ('web','api','embed','kiosk','mobile')")

    # === ORGANIZATIONS ===
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("plan", sa.Text, server_default="free", nullable=False),
        sa.Column("max_users", sa.Integer, server_default="5"),
        sa.Column("max_storage_gb", sa.Integer, server_default="10"),
        sa.Column("max_videos_per_month", sa.Integer, server_default="50"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("trial_ends_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # === USERS ===
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("username", sa.String(100), unique=True, nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.Text, nullable=True),
        sa.Column("role", sa.Text, server_default="creator", nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True, index=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_verified", sa.Boolean, server_default="false"),
        sa.Column("is_superuser", sa.Boolean, server_default="false"),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("language", sa.String(10), server_default="en"),
        sa.Column("theme", sa.String(10), server_default="dark"),
        sa.Column("last_login", sa.DateTime, nullable=True),
        sa.Column("login_count", sa.Integer, server_default="0"),
        sa.Column("api_key_hash", sa.Text, nullable=True),
        sa.Column("oauth_provider", sa.String(50), nullable=True),
        sa.Column("oauth_id", sa.String(255), nullable=True),
        sa.Column("storage_used_bytes", sa.BigInteger, server_default="0"),
        sa.Column("storage_limit_bytes", sa.BigInteger, server_default=str(10 * 1024**3)),
        sa.Column("email_verification_token", sa.String(255), nullable=True),
        sa.Column("password_reset_token", sa.String(255), nullable=True),
        sa.Column("password_reset_expires", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # === SUBSCRIPTIONS ===
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("plan", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("current_period_start", sa.DateTime, nullable=True),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, server_default="false"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # === AVATARS ===
    op.create_table(
        "avatars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("source_type", sa.Text, server_default="photo"),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("source_file_url", sa.Text, nullable=False),
        sa.Column("face_embedding", postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column("motion_template_url", sa.Text, nullable=True),
        sa.Column("status", sa.Text, server_default="processing"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("is_public", sa.Boolean, server_default="false"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("processing_duration_seconds", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("is_deleted", sa.Boolean, server_default="false", index=True),
    )

    # === VOICE MODELS ===
    op.create_table(
        "voice_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("sample_files", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("model_file_url", sa.Text, nullable=True),
        sa.Column("voice_fingerprint_url", sa.Text, nullable=True),
        sa.Column("language", sa.String(10), server_default="en"),
        sa.Column("accent", sa.String(50), nullable=True),
        sa.Column("status", sa.Text, server_default="cloning"),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("tts_engine", sa.Text, server_default="xtts"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # === KNOWLEDGE BASES ===
    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("qdrant_collection_id", sa.String(255), nullable=False),
        sa.Column("document_count", sa.Integer, server_default="0"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("embedding_model", sa.String(100), server_default="multilingual-e5-large"),
        sa.Column("status", sa.String(50), server_default="ready"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # === AGENTS ===
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("avatar_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avatars.id"), nullable=True),
        sa.Column("voice_model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("voice_models.id"), nullable=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=True),
        sa.Column("llm_provider", sa.String(50), server_default="openai"),
        sa.Column("llm_model", sa.String(100), server_default="gpt-4o-mini"),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("personality_traits", postgresql.JSONB, server_default="{}"),
        sa.Column("capabilities", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_public", sa.Boolean, server_default="false"),
        sa.Column("conversation_count", sa.Integer, server_default="0"),
        sa.Column("avg_rating", sa.Float, nullable=True),
        sa.Column("webhook_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # === VIDEOS ===
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("avatar_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avatars.id"), nullable=True),
        sa.Column("voice_model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("voice_models.id"), nullable=True),
        sa.Column("script_text", sa.Text, nullable=False),
        sa.Column("language", sa.String(10), server_default="en"),
        sa.Column("resolution", sa.Text, server_default="1080p"),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("output_url", sa.Text, nullable=True),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("status", sa.Text, server_default="queued", index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("job_id", sa.String(255), nullable=True),
        sa.Column("template_id", sa.String(100), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("processing_duration_seconds", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # === VIDEO JOBS ===
    op.create_table(
        "video_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id"), nullable=False, unique=True, index=True),
        sa.Column("job_type", sa.String(50), server_default="generate_video"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("status", sa.Text, server_default="pending", index=True),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("worker_id", sa.String(100), nullable=True),
        sa.Column("gpu_id", sa.String(20), nullable=True),
        sa.Column("log_messages", postgresql.JSONB, server_default="[]"),
        sa.Column("error_details", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # === DOCUMENTS ===
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False, index=True),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.Text, server_default="pdf"),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, server_default="0"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.Text, server_default="processing"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # === CONVERSATIONS ===
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("session_id", sa.String(255), nullable=True, index=True),
        sa.Column("messages", postgresql.JSONB, server_default="[]"),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("user_satisfaction_score", sa.Float, nullable=True),
        sa.Column("channel", sa.Text, server_default="web"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # === ANALYTICS ===
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metrics", postgresql.JSONB, server_default="{}"),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now(), index=True),
        sa.Column("date_bucket", sa.Date, nullable=True, index=True),
        sa.Column("gpu_seconds_used", sa.Float, server_default="0"),
        sa.Column("storage_bytes_delta", sa.BigInteger, server_default="0"),
    )

    # === AUDIT LOGS ===
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("action", sa.String(200), nullable=False, index=True),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("request_data", postgresql.JSONB, nullable=True),
        sa.Column("response_code", sa.Integer, nullable=True),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now(), index=True),
    )

    # === INDEXES ===
    op.create_index("ix_videos_org_created", "videos", ["organization_id", "created_at"])
    op.create_index("ix_analytics_org_event_ts", "analytics_events", ["organization_id", "event_type", "timestamp"])
    op.create_index("ix_audit_logs_ts", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("analytics_events")
    op.drop_table("conversations")
    op.drop_table("documents")
    op.drop_table("video_jobs")
    op.drop_table("videos")
    op.drop_table("agents")
    op.drop_table("knowledge_bases")
    op.drop_table("voice_models")
    op.drop_table("avatars")
    op.drop_table("subscriptions")
    op.drop_table("users")
    op.drop_table("organizations")

    for enum in ["userrole","orgplan","avatarsource","avatarstatuse","voicestatus",
                 "ttsenginee","videostatus","resolution","jobstatus","documentstatus",
                 "filetype","channel"]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
