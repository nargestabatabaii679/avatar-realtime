from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.video_job import VideoJob
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/admin", tags=["Administration"])

_require_admin = require_role(UserRole.ADMIN)


@router.get("/users")
async def list_all_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    query = select(User)
    if search:
        query = query.where(
            (User.email.ilike(f"%{search}%")) | (User.full_name.ilike(f"%{search}%"))
        )
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(desc(User.created_at)).offset((page - 1) * limit).limit(limit)
    )
    users = result.scalars().all()
    return {"items": users, "total": total, "page": page, "limit": limit}


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot suspend yourself")
    user.is_active = not user.is_active
    await db.commit()
    action = "suspended" if not user.is_active else "activated"
    return {"message": f"User {action}", "user_id": str(user_id), "is_active": user.is_active}


@router.put("/users/{user_id}/role")
async def change_user_role(
    user_id: uuid.UUID,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    # Only super_admin can assign super_admin role
    if role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can assign super_admin role")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    await db.commit()
    return {"message": f"Role updated to {role}", "user_id": str(user_id)}


@router.get("/organizations")
async def list_organizations(
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    total = await db.scalar(select(func.count(Organization.id)))
    result = await db.execute(
        select(Organization)
        .order_by(desc(Organization.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return {"items": result.scalars().all(), "total": total, "page": page}


@router.get("/jobs")
async def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    query = select(VideoJob)
    if status_filter:
        query = query.where(VideoJob.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(desc(VideoJob.created_at)).offset((page - 1) * limit).limit(limit)
    )
    return {"items": result.scalars().all(), "total": total}


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    job = await db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    from app.models.video import Video
    video = await db.get(Video, job.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Associated video not found")

    from app.workers.video_tasks import generate_video_task
    from app.models.video import VideoStatus
    from app.models.video_job import JobStatus

    video.status = VideoStatus.QUEUED
    job.status = JobStatus.PENDING
    job.progress = 0
    await db.commit()

    task = generate_video_task.delay(
        video_id=str(video.id),
        avatar_id=str(video.avatar_id),
        voice_model_id=str(video.voice_model_id),
        script=video.script_text,
        language=video.language,
        resolution=video.resolution,
        organization_id=str(video.organization_id),
        user_id=str(video.user_id),
    )
    job.celery_task_id = task.id
    await db.commit()

    return {"message": "Job requeued", "new_task_id": task.id}


@router.get("/system")
async def get_system_health(
    current_user: User = Depends(_require_admin),
):
    """Full system health overview."""
    health: dict = {"status": "healthy", "services": {}}

    # Database
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        health["services"]["database"] = {"status": "connected"}
    except Exception as e:
        health["services"]["database"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"

    # Redis
    try:
        from app.core.redis_client import get_redis_client
        redis = await get_redis_client()
        await redis.ping()
        health["services"]["redis"] = {"status": "connected"}
    except Exception as e:
        health["services"]["redis"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"

    # MinIO
    try:
        from app.services.storage.minio_service import get_minio_client
        client = get_minio_client()
        client.bucket_exists("avatars")
        health["services"]["minio"] = {"status": "connected"}
    except Exception as e:
        health["services"]["minio"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"

    # GPU
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            health["services"]["gpu"] = {
                "status": "available",
                "name": parts[0] if parts else "unknown",
                "memory_used_mb": int(parts[1]) if len(parts) > 1 else 0,
                "memory_total_mb": int(parts[2]) if len(parts) > 2 else 0,
                "utilization_percent": int(parts[3]) if len(parts) > 3 else 0,
                "temperature_c": int(parts[4]) if len(parts) > 4 else 0,
            }
        else:
            health["services"]["gpu"] = {"status": "unavailable"}
    except Exception:
        health["services"]["gpu"] = {"status": "unavailable"}

    return health


@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    action: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(desc(AuditLog.timestamp)).offset((page - 1) * limit).limit(limit)
    )
    return {"items": result.scalars().all(), "total": total, "page": page}


@router.post("/models/reload")
async def reload_models(
    model_name: Optional[str] = None,
    current_user: User = Depends(_require_admin),
):
    """Signal GPU worker to reload AI models."""
    try:
        from app.core.celery_app import celery_app
        celery_app.send_task(
            "workers.model_tasks.reload_models",
            kwargs={"model_name": model_name},
            queue="gpu",
        )
        return {"message": f"Model reload triggered for: {model_name or 'all models'}"}
    except Exception as e:
        return {"message": "Reload signal sent (worker may not be running)", "error": str(e)}
