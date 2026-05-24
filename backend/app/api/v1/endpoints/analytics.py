from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.analytics import AnalyticsEvent
from app.models.video import Video, VideoStatus
from app.models.avatar import Avatar
from app.models.voice_model import VoiceModel
from app.models.agent import Agent
from app.models.conversation import Conversation

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _period_to_dates(period: str) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    periods = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}
    days = periods.get(period, 30)
    return now - timedelta(days=days), now


@router.get("/dashboard")
async def get_dashboard(
    period: str = Query("30d", regex="^(7d|30d|90d|365d)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since, until = _period_to_dates(period)
    org_id = current_user.organization_id

    # Videos
    video_stats = await db.execute(
        select(
            func.count(Video.id).label("total"),
            func.sum(Video.duration_seconds).label("total_duration"),
            func.sum(Video.file_size_bytes).label("total_size"),
        ).where(
            Video.organization_id == org_id,
            Video.created_at >= since,
            Video.status == VideoStatus.COMPLETED,
        )
    )
    vr = video_stats.one()

    # Avatars
    avatar_count = await db.scalar(
        select(func.count(Avatar.id)).where(
            Avatar.organization_id == org_id, Avatar.is_deleted.is_(False)
        )
    )

    # Voices
    voice_count = await db.scalar(
        select(func.count(VoiceModel.id)).where(
            VoiceModel.organization_id == org_id, VoiceModel.is_deleted.is_(False)
        )
    )

    # Agents
    agent_count = await db.scalar(
        select(func.count(Agent.id)).where(
            Agent.organization_id == org_id, Agent.is_deleted.is_(False)
        )
    )

    conversation_count = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.organization_id == org_id,
            Conversation.created_at >= since,
        )
    )

    return {
        "period": period,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "videos": {
            "total": vr.total or 0,
            "total_duration_hours": round((vr.total_duration or 0) / 3600, 2),
            "total_size_gb": round((vr.total_size or 0) / 1e9, 2),
        },
        "avatars": {"total": avatar_count or 0},
        "voices": {"total": voice_count or 0},
        "agents": {
            "total": agent_count or 0,
            "conversations": conversation_count or 0,
        },
    }


@router.get("/videos")
async def get_video_analytics(
    period: str = Query("30d"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since, _ = _period_to_dates(period)
    org_id = current_user.organization_id

    # Daily video counts
    daily = await db.execute(
        select(
            func.date(Video.created_at).label("date"),
            func.count(Video.id).label("count"),
        ).where(
            Video.organization_id == org_id,
            Video.created_at >= since,
        ).group_by(func.date(Video.created_at)).order_by(func.date(Video.created_at))
    )

    # Resolution breakdown
    resolutions = await db.execute(
        select(
            Video.resolution,
            func.count(Video.id).label("count"),
        ).where(
            Video.organization_id == org_id,
            Video.created_at >= since,
        ).group_by(Video.resolution)
    )

    return {
        "daily": [{"date": str(r.date), "count": r.count} for r in daily],
        "by_resolution": {r.resolution: r.count for r in resolutions},
    }


@router.get("/gpu")
async def get_gpu_metrics(
    current_user: User = Depends(get_current_user),
):
    """Return current GPU utilization via nvidia-smi."""
    try:
        import subprocess, json
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            gpus = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append({
                        "name": parts[0],
                        "memory_used_mb": int(parts[1]) if parts[1].isdigit() else 0,
                        "memory_total_mb": int(parts[2]) if parts[2].isdigit() else 0,
                        "utilization_percent": int(parts[3]) if parts[3].isdigit() else 0,
                        "temperature_c": int(parts[4]) if parts[4].isdigit() else 0,
                        "power_draw_w": float(parts[5]) if len(parts) > 5 else None,
                    })
            return {"gpus": gpus, "available": True}
    except Exception:
        pass
    return {"gpus": [], "available": False, "message": "GPU not available"}


@router.get("/storage")
async def get_storage_analytics(
    current_user: User = Depends(get_current_user),
):
    """Return storage usage breakdown per resource type."""
    try:
        from app.services.storage.minio_service import get_storage_usage
        usage = await get_storage_usage(str(current_user.organization_id))
        total = sum(usage.values())
        return {
            "breakdown": {k: {"bytes": v, "gb": round(v / 1e9, 3)} for k, v in usage.items()},
            "total_bytes": total,
            "total_gb": round(total / 1e9, 3),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/export")
async def export_analytics(
    period: str = Query("30d"),
    resource: str = Query("videos"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export analytics data as CSV."""
    since, _ = _period_to_dates(period)
    import csv, io

    output = io.StringIO()
    writer = csv.writer(output)

    if resource == "videos":
        result = await db.execute(
            select(Video).where(
                Video.organization_id == current_user.organization_id,
                Video.created_at >= since,
            ).order_by(Video.created_at.desc())
        )
        videos = result.scalars().all()
        writer.writerow(["id", "title", "status", "resolution", "duration_s", "size_bytes", "created_at"])
        for v in videos:
            writer.writerow([v.id, v.title, v.status, v.resolution, v.duration_seconds, v.file_size_bytes, v.created_at])

    content = output.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=analytics_{resource}_{period}.csv"},
    )
