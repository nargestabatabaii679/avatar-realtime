"""
schemas/analytics.py
--------------------
Pydantic v2 schemas for the Analytics and Observability domain.

Covers:
  - DashboardStats     — top-level org dashboard summary
  - UsageMetrics       — resource consumption over a time window
  - GPUMetrics         — compute resource utilisation
  - EventFilter        — query parameters for analytics endpoints
  - TimeSeriesPoint    — generic time-bucketed data point
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Time-series helpers
# ---------------------------------------------------------------------------


class TimeSeriesPoint(BaseModel):
    """A single data point in a time-series aggregation."""

    date: date
    value: float
    label: str | None = None


class TimeSeriesData(BaseModel):
    """Named time-series used in chart responses."""

    name: str
    unit: str = Field(description="Unit of the values, e.g. 'count', 'seconds', 'bytes', 'USD'")
    points: list[TimeSeriesPoint]
    total: float = Field(description="Sum of all points in the series")
    average: float | None = None
    peak: float | None = None


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------


class VideoStats(BaseModel):
    """Video generation statistics."""

    total: int = Field(ge=0, description="All-time video count")
    this_month: int = Field(ge=0, description="Videos generated this calendar month")
    monthly_limit: int = Field(ge=0, description="Plan monthly limit (-1 = unlimited)")
    monthly_remaining: int = Field(ge=-1)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    processing: int = Field(ge=0, description="Currently in-flight jobs")
    avg_duration_seconds: float | None = None
    total_duration_seconds: float = Field(ge=0.0)


class StorageStats(BaseModel):
    """Storage consumption statistics."""

    used_bytes: int = Field(ge=0)
    limit_bytes: int = Field(ge=0, description="Org storage quota in bytes")
    available_bytes: int = Field(ge=0)
    used_percent: float = Field(ge=0.0, le=100.0)
    avatars_bytes: int = Field(ge=0)
    videos_bytes: int = Field(ge=0)
    audio_bytes: int = Field(ge=0)
    models_bytes: int = Field(ge=0)


class AgentStats(BaseModel):
    """Agent and conversation statistics."""

    total_agents: int = Field(ge=0)
    active_agents: int = Field(ge=0)
    total_conversations: int = Field(ge=0)
    conversations_this_month: int = Field(ge=0)
    avg_satisfaction_score: float | None = Field(None, ge=1.0, le=5.0)
    total_messages: int = Field(ge=0)


class UserStats(BaseModel):
    """User and team statistics."""

    total_users: int = Field(ge=0)
    active_users: int = Field(ge=0)
    max_users: int = Field(ge=0, description="Plan user limit")
    pending_invitations: int = Field(ge=0)
    role_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="User count per role, e.g. {'admin': 2, 'creator': 8}",
    )


class DashboardStats(BaseModel):
    """
    Top-level dashboard summary returned by GET /analytics/dashboard.

    Aggregates the most important KPIs across all sub-domains so the UI
    can render the main dashboard in a single API call.
    """

    organization_id: uuid.UUID
    organization_name: str
    plan: str
    as_of: datetime = Field(description="Timestamp when these stats were computed")
    videos: VideoStats
    storage: StorageStats
    agents: AgentStats
    users: UserStats
    avatars_count: int = Field(ge=0)
    voice_models_count: int = Field(ge=0)
    knowledge_bases_count: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Usage metrics
# ---------------------------------------------------------------------------


class UsageMetrics(BaseModel):
    """
    Resource consumption breakdown over a requested time window.

    Returned by GET /analytics/usage?start=…&end=…&granularity=day|week|month
    """

    organization_id: uuid.UUID
    start_date: date
    end_date: date
    granularity: Literal["day", "week", "month"]

    # Time-series
    videos_generated: TimeSeriesData
    gpu_seconds: TimeSeriesData
    storage_bytes: TimeSeriesData
    api_requests: TimeSeriesData
    conversation_count: TimeSeriesData

    # Totals for the window
    total_videos: int = Field(ge=0)
    total_gpu_seconds: float = Field(ge=0.0)
    total_storage_delta_bytes: int
    total_api_requests: int = Field(ge=0)
    total_conversations: int = Field(ge=0)
    total_tokens_used: int = Field(ge=0)

    # Cost estimate (if billing is configured)
    estimated_cost_usd: float | None = Field(
        None,
        ge=0.0,
        description="Estimated cost in USD based on metered usage",
    )


# ---------------------------------------------------------------------------
# GPU metrics
# ---------------------------------------------------------------------------


class GPUWorkerMetrics(BaseModel):
    """Per-worker GPU utilisation snapshot."""

    worker_id: str
    gpu_id: str
    gpu_name: str | None = None
    utilization_percent: float = Field(ge=0.0, le=100.0)
    memory_used_mb: float = Field(ge=0.0)
    memory_total_mb: float = Field(ge=0.0)
    memory_used_percent: float = Field(ge=0.0, le=100.0)
    temperature_c: float | None = Field(None, description="GPU die temperature in °C")
    power_draw_watts: float | None = None
    active_tasks: int = Field(ge=0)
    tasks_completed_today: int = Field(ge=0)
    avg_task_duration_seconds: float | None = None
    last_heartbeat: datetime


class GPUMetrics(BaseModel):
    """
    Fleet-level GPU resource snapshot returned by GET /analytics/gpu.

    Intended for the admin infrastructure dashboard, not end-user analytics.
    """

    as_of: datetime
    total_workers: int = Field(ge=0)
    active_workers: int = Field(ge=0)
    total_gpus: int = Field(ge=0)
    avg_gpu_utilization_percent: float = Field(ge=0.0, le=100.0)
    avg_gpu_memory_used_percent: float = Field(ge=0.0, le=100.0)
    queued_jobs: int = Field(ge=0)
    processing_jobs: int = Field(ge=0)
    workers: list[GPUWorkerMetrics]
    gpu_seconds_used_today: float = Field(ge=0.0)
    gpu_seconds_used_this_month: float = Field(ge=0.0)


# ---------------------------------------------------------------------------
# Event filter (query params / request body)
# ---------------------------------------------------------------------------


class EventFilter(BaseModel):
    """
    Filter parameters for POST /analytics/events/query.

    All fields are optional; omitting a field removes that filter.
    """

    organization_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    event_types: list[str] | None = Field(
        None,
        description="Allowlist of event_type values to include",
    )
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    start: datetime | None = None
    end: datetime | None = None
    granularity: Literal["hour", "day", "week", "month"] = "day"
    limit: int = Field(default=100, ge=1, le=10_000)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_date_range(self) -> "EventFilter":
        if self.start and self.end and self.start >= self.end:
            raise ValueError("start must be before end.")
        return self


class AnalyticsEventResponse(BaseModel):
    """A single analytics event record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID | None
    event_type: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    metrics: dict[str, Any]
    timestamp: datetime
    date_bucket: date
    gpu_seconds_used: float | None
    storage_bytes_delta: int | None


class AnalyticsEventListResponse(BaseModel):
    """Paginated list of analytics events."""

    items: list[AnalyticsEventResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=10_000)
    pages: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Content performance
# ---------------------------------------------------------------------------


class TopVideoEntry(BaseModel):
    """A video ranked by view count or engagement."""

    video_id: uuid.UUID
    title: str
    view_count: int
    duration_seconds: float | None
    resolution: str
    created_at: datetime
    thumbnail_url: str | None


class TopAgentEntry(BaseModel):
    """An agent ranked by conversation count or satisfaction score."""

    agent_id: uuid.UUID
    name: str
    conversation_count: int
    avg_satisfaction_score: float | None
    role: str


class ContentPerformanceResponse(BaseModel):
    """Top-N content items for a given time window."""

    organization_id: uuid.UUID
    start_date: date
    end_date: date
    top_videos: list[TopVideoEntry]
    top_agents: list[TopAgentEntry]
