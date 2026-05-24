"""
app/core/celery_app.py
----------------------
Celery application configuration for the AI Digital Human Platform.

Architecture:
  - Broker:  Redis DB 1
  - Backend: Redis DB 2
  - Queues:
      * ``gpu``      — GPU-bound inference tasks (LivePortrait, Wav2Lip, TTS, etc.)
      * ``cpu``      — CPU-bound tasks (file I/O, pre/post-processing)
      * ``default``  — General-purpose tasks
      * ``analytics``— Low-priority analytics aggregation
      * ``priority`` — High-priority real-time tasks (WebSocket push)
  - Beat schedule: Periodic analytics aggregation and cleanup
  - Retry policy:  Exponential back-off with jitter
  - Monitoring:    Task lifecycle signals hooked into structlog + Prometheus
"""

from __future__ import annotations

import os
import time
from typing import Any

import structlog
from celery import Celery, Task, signals
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from kombu import Exchange, Queue
from prometheus_client import Counter, Gauge, Histogram

from app.core.config import settings

logger = structlog.get_logger(__name__)
task_logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------
# Prometheus task metrics
# ---------------------------------------------------------------------------

TASK_SENT = Counter(
    "celery_tasks_sent_total",
    "Total number of Celery tasks sent",
    ["task_name", "queue"],
)
TASK_RECEIVED = Counter(
    "celery_tasks_received_total",
    "Total number of Celery tasks received by a worker",
    ["task_name"],
)
TASK_STARTED = Counter(
    "celery_tasks_started_total",
    "Total number of Celery tasks started",
    ["task_name"],
)
TASK_SUCCEEDED = Counter(
    "celery_tasks_succeeded_total",
    "Total number of Celery tasks that completed successfully",
    ["task_name"],
)
TASK_FAILED = Counter(
    "celery_tasks_failed_total",
    "Total number of Celery tasks that failed",
    ["task_name"],
)
TASK_RETRIED = Counter(
    "celery_tasks_retried_total",
    "Total number of Celery task retries",
    ["task_name"],
)
TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration",
    ["task_name", "queue"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)
ACTIVE_TASKS = Gauge(
    "celery_tasks_active",
    "Number of currently executing Celery tasks",
    ["queue"],
)

# ---------------------------------------------------------------------------
# Queue / Exchange definitions
# ---------------------------------------------------------------------------

_EXCHANGE_DIRECT = Exchange("direct", type="direct", durable=True)
_EXCHANGE_GPU = Exchange("gpu", type="direct", durable=True)

CELERY_QUEUES = (
    # GPU-accelerated inference — route to GPU workers
    Queue(
        "gpu",
        exchange=_EXCHANGE_GPU,
        routing_key="gpu",
        queue_arguments={"x-max-priority": 10},
    ),
    # Real-time priority tasks (WebSocket notifications, auth)
    Queue(
        "priority",
        exchange=_EXCHANGE_DIRECT,
        routing_key="priority",
        queue_arguments={"x-max-priority": 10},
    ),
    # General async tasks (thumbnails, emails, storage ops)
    Queue(
        "default",
        exchange=_EXCHANGE_DIRECT,
        routing_key="default",
    ),
    # CPU-bound pre/post-processing tasks
    Queue(
        "cpu",
        exchange=_EXCHANGE_DIRECT,
        routing_key="cpu",
    ),
    # Low-priority analytics aggregation
    Queue(
        "analytics",
        exchange=_EXCHANGE_DIRECT,
        routing_key="analytics",
    ),
)

# ---------------------------------------------------------------------------
# Task routing (task name prefix → queue)
# ---------------------------------------------------------------------------

CELERY_TASK_ROUTES: dict[str, dict[str, str]] = {
    # GPU inference
    "app.workers.inference.*": {"queue": "gpu"},
    "app.workers.video.*": {"queue": "gpu"},
    "app.workers.tts.*": {"queue": "gpu"},
    "app.workers.stt.*": {"queue": "gpu"},
    "app.workers.face.*": {"queue": "gpu"},
    "app.workers.liveportrait.*": {"queue": "gpu"},
    "app.workers.wav2lip.*": {"queue": "gpu"},
    "app.workers.musetalk.*": {"queue": "gpu"},
    # CPU processing
    "app.workers.preprocessing.*": {"queue": "cpu"},
    "app.workers.postprocessing.*": {"queue": "cpu"},
    "app.workers.audio.*": {"queue": "cpu"},
    "app.workers.storage.*": {"queue": "cpu"},
    # Priority / real-time
    "app.workers.notifications.*": {"queue": "priority"},
    "app.workers.websocket.*": {"queue": "priority"},
    # Analytics (low priority)
    "app.workers.analytics.*": {"queue": "analytics"},
    "app.workers.reports.*": {"queue": "analytics"},
    # Default catchall
    "app.workers.*": {"queue": "default"},
}

# ---------------------------------------------------------------------------
# Beat (periodic task) schedule
# ---------------------------------------------------------------------------

CELERY_BEAT_SCHEDULE: dict[str, Any] = {
    # Aggregate hourly usage metrics
    "aggregate-hourly-analytics": {
        "task": "app.workers.analytics.aggregate_hourly_metrics",
        "schedule": crontab(minute=5),          # Every hour at :05
        "options": {"queue": "analytics", "priority": 1},
    },
    # Aggregate daily session statistics
    "aggregate-daily-analytics": {
        "task": "app.workers.analytics.aggregate_daily_metrics",
        "schedule": crontab(hour=1, minute=0),  # 01:00 UTC
        "options": {"queue": "analytics", "priority": 1},
    },
    # Clean up expired temporary files from local scratch storage
    "cleanup-temp-files": {
        "task": "app.workers.storage.cleanup_temp_files",
        "schedule": crontab(hour="*/4", minute=30),   # Every 4 hours
        "options": {"queue": "cpu"},
    },
    # Purge soft-deleted records older than 30 days
    "purge-soft-deleted-records": {
        "task": "app.workers.storage.purge_soft_deleted_records",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Weekly, Sunday 03:00
        "options": {"queue": "cpu"},
    },
    # Refresh vector embeddings for stale avatar profiles
    "refresh-avatar-embeddings": {
        "task": "app.workers.face.refresh_stale_embeddings",
        "schedule": crontab(hour=2, minute=0),   # Daily 02:00
        "options": {"queue": "gpu"},
    },
    # Evict expired Redis sessions
    "evict-expired-sessions": {
        "task": "app.workers.analytics.evict_expired_sessions",
        "schedule": crontab(minute="*/30"),      # Every 30 minutes
        "options": {"queue": "default"},
    },
    # Generate organisation billing snapshots
    "generate-billing-snapshots": {
        "task": "app.workers.analytics.generate_billing_snapshots",
        "schedule": crontab(hour=0, minute=0),   # Daily midnight
        "options": {"queue": "analytics"},
    },
    # Health probe — keeps at least one worker alive
    "worker-heartbeat": {
        "task": "app.workers.analytics.worker_heartbeat",
        "schedule": 60.0,                        # Every 60 seconds
        "options": {"queue": "priority"},
    },
}

# ---------------------------------------------------------------------------
# Celery application factory
# ---------------------------------------------------------------------------


def create_celery_app() -> Celery:
    """
    Construct and configure the Celery application instance.

    Returns:
        Fully configured ``Celery`` instance ready for use as a decorator
        registry and WSGI app.
    """
    app = Celery(
        "avatar_platform",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            # Worker modules to auto-discover tasks from
            "app.workers.inference",
            "app.workers.video",
            "app.workers.tts",
            "app.workers.stt",
            "app.workers.face",
            "app.workers.liveportrait",
            "app.workers.wav2lip",
            "app.workers.musetalk",
            "app.workers.preprocessing",
            "app.workers.postprocessing",
            "app.workers.audio",
            "app.workers.storage",
            "app.workers.notifications",
            "app.workers.analytics",
            "app.workers.reports",
        ],
    )

    app.conf.update(
        # ── Serialisation ──────────────────────────────────────────────────
        task_serializer=settings.CELERY_TASK_SERIALIZER,
        result_serializer=settings.CELERY_RESULT_SERIALIZER,
        accept_content=settings.CELERY_ACCEPT_CONTENT,
        # ── Timezone ───────────────────────────────────────────────────────
        timezone=settings.CELERY_TIMEZONE,
        enable_utc=True,
        # ── Broker ─────────────────────────────────────────────────────────
        broker_url=settings.CELERY_BROKER_URL,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=10,
        broker_transport_options={
            "visibility_timeout": settings.CELERY_TASK_TIME_LIMIT + 60,
            "max_retries": settings.CELERY_MAX_RETRIES,
            "socket_timeout": 10,
            "socket_connect_timeout": 5,
        },
        # ── Result backend ─────────────────────────────────────────────────
        result_backend=settings.CELERY_RESULT_BACKEND,
        result_expires=86400,          # Keep results for 24 hours
        result_compression="gzip",
        result_extended=True,          # Store task name + args in result
        # ── Task behaviour ─────────────────────────────────────────────────
        task_acks_late=True,           # Ack after task completes (safer)
        task_reject_on_worker_lost=True,
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_max_retries=settings.CELERY_MAX_RETRIES,
        task_default_retry_delay=settings.CELERY_DEFAULT_RETRY_DELAY,
        task_always_eager=False,
        task_eager_propagates=True,
        task_remote_tracebacks=True,
        # ── Queue setup ────────────────────────────────────────────────────
        task_queues=CELERY_QUEUES,
        task_routes=CELERY_TASK_ROUTES,
        task_default_queue="default",
        task_default_exchange="direct",
        task_default_routing_key="default",
        # ── Worker settings ────────────────────────────────────────────────
        worker_prefetch_multiplier=1,  # One task at a time per worker (important for GPU)
        worker_max_tasks_per_child=200,  # Restart workers to avoid memory leaks
        worker_max_memory_per_child=2_000_000,  # 2 GB before restart (KB)
        worker_disable_rate_limits=False,
        worker_send_task_events=True,
        # ── Beat ───────────────────────────────────────────────────────────
        beat_schedule=CELERY_BEAT_SCHEDULE,
        beat_scheduler="celery.beat:PersistentScheduler",
        beat_schedule_filename="/tmp/celerybeat-schedule",  # noqa: S108
        # ── Monitoring ─────────────────────────────────────────────────────
        task_send_sent_event=True,
        task_track_started=True,
        # ── Redis-specific ─────────────────────────────────────────────────
        redis_max_connections=20,
        redis_socket_timeout=5,
        redis_socket_connect_timeout=5,
    )

    return app


# ---------------------------------------------------------------------------
# Singleton Celery application
# ---------------------------------------------------------------------------

celery_app: Celery = create_celery_app()

# ---------------------------------------------------------------------------
# Custom base task with retry logic and logging
# ---------------------------------------------------------------------------


class BaseTask(Task):  # type: ignore[type-arg]
    """
    Base class for all platform Celery tasks.

    Features:
      - Structured logging (structlog) for every lifecycle event
      - Prometheus metrics on start / success / failure / retry
      - Exponential back-off with jitter on automatic retries
      - Sentry error capture on failure
    """

    abstract = True
    _start_time: float | None = None

    # Default retry policy — subclasses may override
    max_retries = settings.CELERY_MAX_RETRIES
    default_retry_delay = settings.CELERY_DEFAULT_RETRY_DELAY

    def on_bound(self, app: Celery) -> None:
        """Called when the task is registered with the app."""
        task_logger.debug("Task bound: %s", self.name)

    def before_start(self, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        """Called just before the task body is executed."""
        self._start_time = time.perf_counter()
        TASK_STARTED.labels(task_name=self.name).inc()
        ACTIVE_TASKS.labels(queue=self.request.delivery_info.get("routing_key", "default")).inc()
        logger.info(
            "celery_task_started",
            task_name=self.name,
            task_id=task_id,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()),
        )

    def on_success(
        self,
        retval: Any,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """Called on successful task completion."""
        duration = time.perf_counter() - (self._start_time or time.perf_counter())
        queue = self.request.delivery_info.get("routing_key", "default")
        TASK_SUCCEEDED.labels(task_name=self.name).inc()
        TASK_DURATION.labels(task_name=self.name, queue=queue).observe(duration)
        ACTIVE_TASKS.labels(queue=queue).dec()
        logger.info(
            "celery_task_succeeded",
            task_name=self.name,
            task_id=task_id,
            duration_s=round(duration, 3),
        )

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Called when the task raises an unhandled exception."""
        duration = time.perf_counter() - (self._start_time or time.perf_counter())
        queue = self.request.delivery_info.get("routing_key", "default")
        TASK_FAILED.labels(task_name=self.name).inc()
        ACTIVE_TASKS.labels(queue=queue).dec()
        logger.error(
            "celery_task_failed",
            task_name=self.name,
            task_id=task_id,
            error=str(exc),
            error_type=type(exc).__name__,
            duration_s=round(duration, 3),
        )

        # Capture in Sentry if configured
        try:
            import sentry_sdk  # noqa: PLC0415
            sentry_sdk.capture_exception(exc)
        except ImportError:
            pass

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Called when the task is being retried."""
        TASK_RETRIED.labels(task_name=self.name).inc()
        logger.warning(
            "celery_task_retried",
            task_name=self.name,
            task_id=task_id,
            retry_number=self.request.retries,
            max_retries=self.max_retries,
            error=str(exc),
        )

    def retry_with_backoff(
        self,
        exc: Exception,
        *,
        countdown: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        """
        Retry the task with exponential back-off and jitter.

        Args:
            exc:         The exception that triggered the retry.
            countdown:   Override the computed delay (seconds).
            max_retries: Override the task's default max_retries.
        """
        import random  # noqa: PLC0415

        retries = self.request.retries
        limit = max_retries or self.max_retries

        if countdown is None:
            # Exponential back-off: 2^n * base_delay + jitter
            base = settings.CELERY_DEFAULT_RETRY_DELAY
            delay = min(base * (2 ** retries), 600)  # cap at 10 minutes
            countdown = int(delay + random.uniform(0, delay * 0.1))  # noqa: S311

        raise self.retry(exc=exc, countdown=countdown, max_retries=limit)


# ---------------------------------------------------------------------------
# Signal handlers (Celery signals → structlog + Prometheus)
# ---------------------------------------------------------------------------


@signals.task_sent.connect
def on_task_sent(sender: str = "", **kwargs: Any) -> None:
    headers: dict[str, Any] = kwargs.get("headers", {})
    queue = headers.get("argsrepr", "default")
    TASK_SENT.labels(task_name=sender, queue=queue).inc()


@signals.task_received.connect
def on_task_received(sender: Any = None, **kwargs: Any) -> None:
    task_name = getattr(sender, "name", str(sender))
    TASK_RECEIVED.labels(task_name=task_name).inc()


@signals.worker_ready.connect
def on_worker_ready(sender: Any = None, **kwargs: Any) -> None:
    logger.info("celery_worker_ready", hostname=os.environ.get("HOSTNAME", "unknown"))


@signals.worker_shutdown.connect
def on_worker_shutdown(sender: Any = None, **kwargs: Any) -> None:
    logger.info("celery_worker_shutdown", hostname=os.environ.get("HOSTNAME", "unknown"))


@signals.beat_init.connect
def on_beat_init(sender: Any = None, **kwargs: Any) -> None:
    logger.info("celery_beat_started")


# ---------------------------------------------------------------------------
# Convenience decorators
# ---------------------------------------------------------------------------


def gpu_task(**kwargs: Any) -> Any:
    """
    Decorator for GPU-bound inference tasks.

    Automatically routes to the ``gpu`` queue and applies conservative
    retry settings (GPU OOM errors shouldn't be retried aggressively).

    Usage::

        @gpu_task(name="app.workers.inference.generate_video")
        def generate_video(avatar_id: str, script: str) -> dict:
            ...
    """
    kwargs.setdefault("queue", "gpu")
    kwargs.setdefault("max_retries", 1)
    kwargs.setdefault("default_retry_delay", 30)
    kwargs.setdefault("soft_time_limit", settings.CELERY_TASK_SOFT_TIME_LIMIT)
    kwargs.setdefault("time_limit", settings.CELERY_TASK_TIME_LIMIT)

    def decorator(func: Any) -> Any:
        return celery_app.task(base=BaseTask, **kwargs)(func)

    return decorator


def cpu_task(**kwargs: Any) -> Any:
    """
    Decorator for CPU-bound processing tasks.

    Routes to the ``cpu`` queue with standard retry settings.
    """
    kwargs.setdefault("queue", "cpu")
    kwargs.setdefault("max_retries", settings.CELERY_MAX_RETRIES)
    kwargs.setdefault("default_retry_delay", settings.CELERY_DEFAULT_RETRY_DELAY)

    def decorator(func: Any) -> Any:
        return celery_app.task(base=BaseTask, **kwargs)(func)

    return decorator


def priority_task(**kwargs: Any) -> Any:
    """
    Decorator for high-priority real-time tasks (notifications, WebSocket push).
    """
    kwargs.setdefault("queue", "priority")
    kwargs.setdefault("max_retries", 5)
    kwargs.setdefault("default_retry_delay", 5)

    def decorator(func: Any) -> Any:
        return celery_app.task(base=BaseTask, **kwargs)(func)

    return decorator


def analytics_task(**kwargs: Any) -> Any:
    """
    Decorator for low-priority analytics tasks.
    """
    kwargs.setdefault("queue", "analytics")
    kwargs.setdefault("max_retries", 0)   # Don't retry analytics aggregation
    kwargs.setdefault("ignore_result", True)

    def decorator(func: Any) -> Any:
        return celery_app.task(base=BaseTask, **kwargs)(func)

    return decorator
