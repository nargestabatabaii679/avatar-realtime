"""
app/api/v1/endpoints/health.py
------------------------------
Health check endpoints for liveness, readiness, GPU status, and Prometheus metrics.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import check_db_health, get_db

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _check_redis() -> dict[str, Any]:
    try:
        from app.core.redis_client import redis_client  # noqa: PLC0415
        start = time.perf_counter()
        await redis_client.ping()
        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency_ms, 2)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


async def _check_database(db: AsyncSession) -> dict[str, Any]:
    try:
        start = time.perf_counter()
        await check_db_health()
        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency_ms, 2)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


async def _check_minio() -> dict[str, Any]:
    try:
        from miniopy_async import Minio  # noqa: PLC0415
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        start = time.perf_counter()
        buckets = await client.list_buckets()
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "status": "ok",
            "latency_ms": round(latency_ms, 2),
            "bucket_count": len(buckets),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_gpu() -> dict[str, Any]:
    try:
        import torch  # noqa: PLC0415
        if not torch.cuda.is_available():
            return {"available": False, "reason": "CUDA not available"}
        device_count = torch.cuda.device_count()
        devices = []
        for i in range(device_count):
            props = torch.cuda.get_device_properties(i)
            allocated = torch.cuda.memory_allocated(i)
            reserved = torch.cuda.memory_reserved(i)
            total = props.total_memory
            devices.append(
                {
                    "id": i,
                    "name": props.name,
                    "total_vram_mb": round(total / 1024 / 1024, 1),
                    "allocated_mb": round(allocated / 1024 / 1024, 1),
                    "reserved_mb": round(reserved / 1024 / 1024, 1),
                    "free_mb": round((total - reserved) / 1024 / 1024, 1),
                    "utilisation_pct": round(allocated / total * 100, 1) if total > 0 else 0,
                }
            )
        return {"available": True, "device_count": device_count, "devices": devices}
    except ImportError:
        return {"available": False, "reason": "PyTorch not installed"}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    summary="Basic liveness check",
    status_code=status.HTTP_200_OK,
    response_class=JSONResponse,
)
async def health() -> JSONResponse:
    """Returns 200 as long as the process is alive."""
    return JSONResponse(
        {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }
    )


@router.get(
    "/health/live",
    summary="Kubernetes liveness probe",
    status_code=status.HTTP_200_OK,
    response_class=JSONResponse,
)
async def liveness() -> JSONResponse:
    """Kubernetes liveness probe — confirms the process is alive."""
    return JSONResponse({"status": "alive"})


@router.get(
    "/health/ready",
    summary="Kubernetes readiness probe",
    response_class=JSONResponse,
)
async def readiness(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Kubernetes readiness probe.

    Verifies that PostgreSQL, Redis, and MinIO are reachable.
    Returns 200 if all checks pass, 503 otherwise.
    """
    db_check, redis_check, minio_check = (
        await _check_database(db),
        await _check_redis(),
        await _check_minio(),
    )

    checks = {
        "database": db_check,
        "redis": redis_check,
        "storage": minio_check,
    }
    overall_ok = all(c["status"] == "ok" for c in checks.values())

    http_status = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        {
            "status": "ready" if overall_ok else "not_ready",
            "checks": checks,
        },
        status_code=http_status,
    )


@router.get(
    "/health/gpu",
    summary="GPU availability and VRAM stats",
    response_class=JSONResponse,
)
async def gpu_health() -> JSONResponse:
    """
    Returns GPU availability, device count, and per-device VRAM statistics.
    Does not require authentication — useful for infrastructure monitoring.
    """
    gpu_info = _check_gpu()
    return JSONResponse({"gpu": gpu_info})


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    include_in_schema=False,
)
async def prometheus_metrics() -> Response:
    """Expose Prometheus metrics in the standard text format for scraping."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
