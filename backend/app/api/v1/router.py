"""
app/api/v1/router.py
--------------------
Main API v1 router.  Aggregates all endpoint sub-routers.

Each endpoint module is imported defensively so that missing optional
ML dependencies only prevent *that* module from loading, not the whole
application.  A warning is logged for any module that fails to import.
"""

from __future__ import annotations

import importlib
from typing import Any

import structlog
from fastapi import APIRouter

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Top-level v1 router (no prefix — the prefix is added in main.py)
# ---------------------------------------------------------------------------

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoint registration helper
# ---------------------------------------------------------------------------

def _include(
    sub_router_path: str,
    *,
    prefix: str,
    tags: list[str],
    **kwargs: Any,
) -> None:
    """
    Dynamically import *sub_router_path* and attach its ``router`` to the v1
    router.  Logs a warning instead of crashing if the import fails.

    Args:
        sub_router_path: Dotted module path, e.g. ``"app.api.v1.endpoints.auth"``.
        prefix:          URL prefix for all routes in this module.
        tags:            OpenAPI tag list.
        **kwargs:        Extra kwargs forwarded to ``include_router``.
    """
    try:
        module = importlib.import_module(sub_router_path)
        sub_router: APIRouter = module.router
        router.include_router(sub_router, prefix=prefix, tags=tags, **kwargs)
        logger.debug("router_registered", module=sub_router_path, prefix=prefix)
    except ImportError as exc:
        logger.warning(
            "router_import_failed",
            module=sub_router_path,
            error=str(exc),
            advice="Check that all dependencies for this module are installed.",
        )
    except AttributeError as exc:
        logger.warning(
            "router_missing_attribute",
            module=sub_router_path,
            error=str(exc),
            advice="Endpoint module must expose a `router` attribute.",
        )


# ---------------------------------------------------------------------------
# Register all v1 endpoint modules
# ---------------------------------------------------------------------------

_ENDPOINT_BASE = "app.api.v1.endpoints"

_include(f"{_ENDPOINT_BASE}.health",       prefix="",              tags=["Health"])
_include(f"{_ENDPOINT_BASE}.auth",         prefix="/auth",         tags=["Authentication"])
_include(f"{_ENDPOINT_BASE}.users",        prefix="/users",        tags=["Users"])
_include(f"{_ENDPOINT_BASE}.organizations",prefix="/organizations", tags=["Organizations"])
_include(f"{_ENDPOINT_BASE}.avatars",      prefix="/avatars",      tags=["Avatars"])
_include(f"{_ENDPOINT_BASE}.voices",       prefix="/voices",       tags=["Voices"])
_include(f"{_ENDPOINT_BASE}.videos",       prefix="/videos",       tags=["Videos"])
_include(f"{_ENDPOINT_BASE}.agents",       prefix="/agents",       tags=["Agents"])
_include(f"{_ENDPOINT_BASE}.knowledge",    prefix="/knowledge",    tags=["Knowledge Base"])
_include(f"{_ENDPOINT_BASE}.analytics",    prefix="/analytics",    tags=["Analytics"])
_include(f"{_ENDPOINT_BASE}.admin",        prefix="/admin",        tags=["Admin"])
_include(f"{_ENDPOINT_BASE}.realtime",     prefix="/realtime",     tags=["Realtime"])
