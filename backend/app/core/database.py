"""
app/core/database.py
--------------------
Async SQLAlchemy engine and session management for the AI Digital Human Platform.

Provides:
  - ``engine``        — shared AsyncEngine instance
  - ``AsyncSessionLocal`` — session factory
  - ``Base``          — re-exported from models.base for convenience
  - ``get_db``        — FastAPI dependency that yields a per-request session
  - ``init_db``       — create all tables on startup (dev/test only; prod uses Alembic)
  - ``check_db_health`` — simple connectivity probe used by the readiness endpoint
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.models.base import Base  # noqa: F401  — re-exported for convenience

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_CONNECT_ARGS: dict[str, Any] = {}

# asyncpg-specific tuning
if "asyncpg" in str(settings.DATABASE_URL):
    _CONNECT_ARGS = {
        "server_settings": {
            "application_name": settings.APP_NAME,
            "jit": "off",           # Disable JIT for OLTP-style short queries
        },
        "command_timeout": 60,      # seconds
    }

engine: AsyncEngine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,             # Detect stale connections before use
    connect_args=_CONNECT_ARGS,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,         # Avoid lazy-load errors after commit
    autocommit=False,
    autoflush=False,
)

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a transactional database session.

    The session is automatically committed on success and rolled back on any
    unhandled exception.  It is always closed at the end of the request.

    Usage::

        @router.post("/items")
        async def create_item(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("db_session_error", error=str(exc), exc_info=True)
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Transactional context manager (for service-layer use)
# ---------------------------------------------------------------------------


class DatabaseTransaction:
    """
    Async context manager that wraps a single database transaction.

    Commits on clean exit; rolls back and re-raises on any exception.

    Usage::

        async with DatabaseTransaction() as session:
            session.add(my_object)
    """

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        self._session = AsyncSessionLocal()
        return self._session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        assert self._session is not None  # noqa: S101
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
                return False
        finally:
            await self._session.close()
        return False


# ---------------------------------------------------------------------------
# Database initialisation helpers
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """
    Create all database tables defined via ``Base`` metadata.

    This is intended for **development and testing only**.
    Production environments rely on Alembic migrations.

    In production (``ENVIRONMENT=production``) this function is a no-op to
    prevent accidental schema changes.
    """
    if settings.is_production:
        logger.info("db_init_skipped", reason="production environment — use Alembic migrations")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("db_tables_created", tables=list(Base.metadata.tables.keys()))


async def drop_db() -> None:
    """
    Drop all database tables.

    **Destructive — for testing only.**  Raises ``RuntimeError`` if called in
    a production environment.
    """
    if settings.is_production:
        raise RuntimeError("drop_db() must never be called in production")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("db_tables_dropped", tables=list(Base.metadata.tables.keys()))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


async def check_db_health() -> dict[str, str]:
    """
    Execute a trivial query to confirm the database is reachable.

    Returns:
        Dict with ``"status": "ok"`` on success.

    Raises:
        ``SQLAlchemyError`` or ``Exception`` on failure — caller decides how to handle.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.scalar()
        if row != 1:
            raise RuntimeError(f"Unexpected SELECT 1 result: {row!r}")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Utility: run arbitrary SQL in a fresh connection (migrations / scripts)
# ---------------------------------------------------------------------------


async def execute_raw(sql: str, params: dict[str, Any] | None = None) -> Any:
    """
    Execute raw SQL and return all rows.

    Intended for administrative scripts and migration helpers — not for
    application code (prefer the ORM or explicit queries).

    Args:
        sql:    SQL string (may use ``:name`` style bind-parameters).
        params: Optional bind-parameter dict.

    Returns:
        List of ``RowMapping`` objects.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        await conn.commit()
        return result.mappings().all()


# ---------------------------------------------------------------------------
# Connection-level context manager (for low-level use)
# ---------------------------------------------------------------------------


async def get_connection() -> AsyncGenerator[AsyncConnection, None]:
    """
    Yield a raw ``AsyncConnection`` for operations that must bypass the ORM.

    Usage::

        async with get_connection() as conn:
            await conn.execute(text("VACUUM ANALYZE"))
    """
    async with engine.connect() as conn:
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
