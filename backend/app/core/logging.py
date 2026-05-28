"""
app/core/logging.py
-------------------
Structured logging configuration for the AI Digital Human Platform.

Built on structlog with support for:
  - JSON output (production) and human-readable console output (development)
  - Automatic log-level filtering
  - Request-ID propagation via context variables
  - Correlation with Sentry event IDs
  - File rotation (optional, configured via LOG_FILE setting)
"""

from __future__ import annotations

import logging
import logging.config
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Context variables for per-request metadata
# ---------------------------------------------------------------------------

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
organization_id_var: ContextVar[str] = ContextVar("organization_id", default="")

# ---------------------------------------------------------------------------
# Custom processors
# ---------------------------------------------------------------------------


def add_request_context(
    logger: Any,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject per-request context vars into every log record."""
    if rid := request_id_var.get(""):
        event_dict["request_id"] = rid
    if uid := user_id_var.get(""):
        event_dict["user_id"] = uid
    if oid := organization_id_var.get(""):
        event_dict["organization_id"] = oid
    return event_dict


def add_sentry_event_id(
    logger: Any,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Attach the current Sentry event ID if one exists."""
    try:
        import sentry_sdk  # noqa: PLC0415
        if hub := sentry_sdk.Hub.current:
            if scope := hub.scope:
                if event_id := scope._tags.get("sentry_event_id"):
                    event_dict["sentry_event_id"] = event_id
    except Exception:  # noqa: BLE001
        pass
    return event_dict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """
    Configure structlog and the standard-library ``logging`` module.

    Should be called once during application startup (in the lifespan handler).
    Calling it multiple times is safe — subsequent calls are no-ops because
    structlog is already configured.
    """
    # Lazy import to avoid circular imports at module load time
    from app.core.config import settings  # noqa: PLC0415

    log_level = settings.LOG_LEVEL
    use_json = settings.LOG_FORMAT == "json" or settings.is_production

    # ── Standard-library logging → structlog bridge ────────────────────────
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(colors=not use_json),
                    "foreign_pre_chain": _get_pre_chain(),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "plain",
                    "stream": "ext://sys.stdout",
                },
                **_file_handler_config(settings),
            },
            "root": {
                "level": log_level,
                "handlers": _handler_names(settings),
            },
            "loggers": {
                # Silence noisy third-party loggers
                "uvicorn": {"level": "INFO", "propagate": True},
                "uvicorn.access": {"level": "WARNING", "propagate": True},
                "sqlalchemy.engine": {
                    "level": "DEBUG" if settings.DATABASE_ECHO else "WARNING",
                    "propagate": True,
                },
                "celery": {"level": "INFO", "propagate": True},
                "httpx": {"level": "WARNING", "propagate": True},
                "hpack": {"level": "WARNING", "propagate": True},
            },
        }
    )

    # ── structlog configuration ────────────────────────────────────────────
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            add_request_context,
            add_sentry_event_id,
            structlog.processors.dict_tracebacks,
            (
                structlog.processors.JSONRenderer()
                if use_json
                else structlog.dev.ConsoleRenderer(colors=True)
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _get_pre_chain() -> list[Any]:
    """Return processors applied to stdlib log records before structlog takes over."""
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]


def _file_handler_config(settings: Any) -> dict[str, Any]:
    """Return file handler config dict (empty if LOG_FILE is not set)."""
    if not settings.LOG_FILE:
        return {}
    return {
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(settings.LOG_FILE),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "formatter": "plain",
        }
    }


def _handler_names(settings: Any) -> list[str]:
    """Return the list of active handler names."""
    handlers = ["console"]
    if settings.LOG_FILE:
        handlers.append("file")
    return handlers


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog logger bound to *name*.

    Usage::

        logger = get_logger(__name__)
        logger.info("event_name", key="value")
    """
    return structlog.get_logger(name)  # type: ignore[return-value]
