"""
app/main.py
-----------
Main FastAPI application entry-point for the AI Digital Human Platform.

Features:
  - Lifespan context manager (startup / shutdown hooks)
  - Configurable CORS middleware
  - Per-route rate limiting via slowapi
  - Prometheus metrics middleware
  - Sentry error tracking
  - Structured JSON logging with structlog
  - API v1 router registration
  - WebSocket support
  - Health-check and readiness probes
  - Static-file serving
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.database import engine, init_db
from app.core.logging import configure_logging, get_logger
from app.core.redis_client import redis_client

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP request count",
    ["method", "endpoint", "http_status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Number of currently active HTTP requests",
)
WS_CONNECTIONS = Gauge(
    "websocket_connections_active",
    "Number of currently active WebSocket connections",
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=str(settings.REDIS_URL),
)

# ---------------------------------------------------------------------------
# Sentry initialisation
# ---------------------------------------------------------------------------


def _init_sentry() -> None:
    if not settings.SENTRY_DSN:
        logger.info("sentry_disabled", reason="SENTRY_DSN not configured")
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"{settings.APP_NAME}@{settings.APP_VERSION}",
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,
    )
    logger.info("sentry_initialised", dsn_host=settings.SENTRY_DSN.split("@")[-1])


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """
    Manage application startup and shutdown.

    Startup order:
      1. Configure structured logging
      2. Initialise Sentry
      3. Connect to Redis
      4. Run DB migrations / health-check
      5. Create local storage directories
      6. Warm up ML model registry (deferred — done by worker processes)

    Shutdown order (reverse):
      1. Flush in-flight tasks
      2. Close Redis connection pool
      3. Dispose SQLAlchemy engine
    """
    # ── Startup ────────────────────────────────────────────────────────────
    configure_logging()
    logger.info(
        "platform_starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    _init_sentry()

    # Connect Redis
    try:
        await redis_client.connect()
        await redis_client.ping()
        logger.info("redis_connected", url=str(settings.REDIS_URL))
    except Exception as exc:  # noqa: BLE001
        logger.error("redis_connection_failed", error=str(exc))
        # Non-fatal in development; fatal in production
        if settings.is_production:
            raise

    # Initialise database
    try:
        await init_db()
        logger.info("database_ready")
    except Exception as exc:  # noqa: BLE001
        logger.error("database_init_failed", error=str(exc))
        if settings.is_production:
            raise

    # Ensure local scratch directories exist
    for directory in [
        settings.UPLOAD_DIR,
        settings.PROCESSED_DIR,
        settings.CACHE_DIR,
        settings.TEMP_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info("storage_dirs_ready", base=str(settings.STORAGE_BASE_DIR))

    logger.info("platform_ready", host=settings.HOST, port=settings.PORT)

    yield  # ── Application running ────────────────────────────────────────

    # ── Shutdown ───────────────────────────────────────────────────────────
    logger.info("platform_shutting_down")

    try:
        await redis_client.disconnect()
        logger.info("redis_disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis_disconnect_error", error=str(exc))

    try:
        await engine.dispose()
        logger.info("database_engine_disposed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("database_dispose_error", error=str(exc))

    logger.info("platform_shutdown_complete")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_application() -> FastAPI:
    """Construct and configure the FastAPI application."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Enterprise AI Digital Human Platform — real-time avatar generation, "
            "voice cloning, lip-sync, and conversational AI."
        ),
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
        root_path=settings.ROOT_PATH,
    )

    # ── Middlewares (order matters: outermost = first in, last out) ─────────

    # 1. GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # 2. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.CORS_ORIGINS],
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    # 3. Rate-limiting (SlowAPI)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # ── Prometheus middleware ───────────────────────────────────────────────

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next: object) -> Response:
        # Exclude the metrics endpoint itself from instrumentation
        if request.url.path == settings.PROMETHEUS_METRICS_PATH:
            return await call_next(request)  # type: ignore[operator]

        start_time = time.perf_counter()
        ACTIVE_REQUESTS.inc()

        try:
            response: Response = await call_next(request)  # type: ignore[operator]
        except Exception:
            ACTIVE_REQUESTS.dec()
            raise

        duration = time.perf_counter() - start_time
        ACTIVE_REQUESTS.dec()

        endpoint = request.url.path
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            http_status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)

        # Propagate request-id for distributed tracing
        request_id = request.headers.get("X-Request-ID", "")
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Request / access logging middleware ────────────────────────────────

    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next: object) -> Response:
        start_time = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[operator]
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", ""),
        )
        return response

    # ── API routers ────────────────────────────────────────────────────────

    _register_routers(app)

    # ── Built-in routes ────────────────────────────────────────────────────

    @app.get(
        "/health",
        tags=["ops"],
        summary="Liveness probe",
        status_code=status.HTTP_200_OK,
    )
    async def health_check() -> JSONResponse:
        """Kubernetes liveness probe — returns 200 if the process is alive."""
        return JSONResponse({"status": "ok", "version": settings.APP_VERSION})

    @app.get(
        "/ready",
        tags=["ops"],
        summary="Readiness probe",
        status_code=status.HTTP_200_OK,
    )
    async def readiness_check() -> JSONResponse:
        """
        Kubernetes readiness probe.
        Verifies that Redis and PostgreSQL are reachable before accepting traffic.
        """
        checks: dict[str, str] = {}
        overall_ok = True

        # Redis
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc}"
            overall_ok = False

        # Database
        try:
            from app.core.database import check_db_health
            await check_db_health()
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["database"] = f"error: {exc}"
            overall_ok = False

        http_status = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(
            {"status": "ready" if overall_ok else "not_ready", "checks": checks},
            status_code=http_status,
        )

    @app.get(
        settings.PROMETHEUS_METRICS_PATH,
        tags=["ops"],
        summary="Prometheus metrics",
        include_in_schema=False,
    )
    async def metrics() -> Response:
        """Expose Prometheus metrics for scraping."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # ── Static files ───────────────────────────────────────────────────────
    _mount_static_files(app)

    return app


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


def _register_routers(app: FastAPI) -> None:
    """
    Import and register all API v1 routers.

    Each sub-module exposes a ``router`` attribute (APIRouter instance).
    Routers are imported lazily here so that missing optional dependencies
    (e.g. GPU libs) only cause errors when the relevant endpoint is actually
    requested, not at startup.
    """
    from app.api.v1 import router as api_v1_router  # noqa: PLC0415

    app.include_router(api_v1_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------


def _mount_static_files(app: FastAPI) -> None:
    """Mount static file directories if they exist."""
    import os  # noqa: PLC0415

    static_dir = settings.STORAGE_BASE_DIR / "static"
    if static_dir.exists() and static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("static_files_mounted", path=str(static_dir))
    else:
        # Create a minimal placeholder directory so the mount doesn't crash
        os.makedirs(str(static_dir), exist_ok=True)
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ---------------------------------------------------------------------------
# Application instance (imported by uvicorn / gunicorn)
# ---------------------------------------------------------------------------

app = create_application()
