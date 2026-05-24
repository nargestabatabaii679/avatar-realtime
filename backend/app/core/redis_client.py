"""
app/core/redis_client.py
------------------------
Async Redis client for the AI Digital Human Platform.

Provides:
  - ``RedisClient``       — singleton wrapper around redis-py's async client
  - ``redis_client``      — module-level singleton instance
  - Cache helpers         — get / set / delete / expire / get-or-set
  - Session storage       — store and retrieve user session dicts
  - Pub/sub support       — publish events and subscribe to channels
  - Distributed locks     — async context-manager lock backed by Redis SET NX
  - Rate-limit counters   — sliding-window counter helpers
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub
from redis.exceptions import LockError, RedisError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None

# ---------------------------------------------------------------------------
# Client wrapper
# ---------------------------------------------------------------------------


class RedisClient:
    """
    Async Redis client with connection pooling, serialisation helpers, and
    pub/sub primitives.

    The client must be explicitly connected via ``await redis_client.connect()``
    during application startup and disconnected via ``await redis_client.disconnect()``
    on shutdown.  Both calls are idempotent.
    """

    def __init__(self) -> None:
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None  # type: ignore[type-arg]

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialise the connection pool and test connectivity."""
        if self._client is not None:
            return  # Already connected

        self._pool = ConnectionPool.from_url(
            str(settings.REDIS_URL),
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
            decode_responses=True,
            health_check_interval=30,
        )
        self._client = Redis(connection_pool=self._pool)
        logger.info("redis_client_ready", url=str(settings.REDIS_URL))

    async def disconnect(self) -> None:
        """Close all pooled connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
        logger.info("redis_client_closed")

    @property
    def client(self) -> Redis:  # type: ignore[type-arg]
        """Return the underlying redis-py async client (raises if not connected)."""
        if self._client is None:
            raise RuntimeError(
                "RedisClient is not connected. "
                "Call `await redis_client.connect()` during application startup."
            )
        return self._client

    # ── Basic operations ───────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Return True if the server responds to PING."""
        try:
            return await self.client.ping()
        except RedisError as exc:
            logger.error("redis_ping_failed", error=str(exc))
            raise

    async def get_raw(self, key: str) -> str | None:
        """Return the raw string value stored at *key*, or None if absent."""
        return await self.client.get(key)

    async def set_raw(
        self,
        key: str,
        value: str,
        *,
        ttl: int | timedelta | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Store a raw string value at *key*.

        Args:
            key:   Redis key.
            value: String value.
            ttl:   Expiry in seconds or as a timedelta.  None = no expiry.
            nx:    Only set if key does NOT exist (SET NX).
            xx:    Only set if key DOES exist (SET XX).

        Returns:
            True if the value was set; False if NX/XX condition was not met.
        """
        ex: int | None = None
        if isinstance(ttl, timedelta):
            ex = int(ttl.total_seconds())
        elif isinstance(ttl, int):
            ex = ttl

        result = await self.client.set(key, value, ex=ex, nx=nx, xx=xx)
        return result is True

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns the number of keys removed."""
        if not keys:
            return 0
        return await self.client.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """Return the number of *keys* that currently exist."""
        return await self.client.exists(*keys)

    async def expire(self, key: str, ttl: int | timedelta) -> bool:
        """Set (or update) the TTL on an existing key."""
        seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else ttl
        return await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Return the remaining TTL in seconds (-1 = no expiry, -2 = not found)."""
        return await self.client.ttl(key)

    async def keys(self, pattern: str) -> list[str]:
        """Return all keys matching *pattern* (use sparingly in production)."""
        return await self.client.keys(pattern)

    async def incr(self, key: str, amount: int = 1) -> int:
        """Atomically increment a counter by *amount*."""
        return await self.client.incrby(key, amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """Atomically decrement a counter by *amount*."""
        return await self.client.decrby(key, amount)

    # ── JSON cache helpers ─────────────────────────────────────────────────

    async def get(self, key: str) -> JsonValue:
        """
        Retrieve and deserialise a JSON-encoded value from Redis.

        Returns None if the key does not exist.
        """
        raw = await self.client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("redis_json_decode_error", key=key)
            return raw  # type: ignore[return-value]

    async def set(
        self,
        key: str,
        value: JsonValue,
        *,
        ttl: int | timedelta | None = settings.CACHE_TTL_DEFAULT,
        nx: bool = False,
    ) -> bool:
        """
        Serialise *value* to JSON and store it at *key*.

        Args:
            key:   Redis key.
            value: Any JSON-serialisable value.
            ttl:   Expiry in seconds or timedelta.  Defaults to ``CACHE_TTL_DEFAULT``.
            nx:    Only set if the key does NOT already exist.

        Returns:
            True if the value was stored.
        """
        serialised = json.dumps(value, default=str)
        return await self.set_raw(key, serialised, ttl=ttl, nx=nx)

    async def get_or_set(
        self,
        key: str,
        factory: Any,  # Callable[[], Awaitable[JsonValue]]
        *,
        ttl: int | timedelta | None = settings.CACHE_TTL_DEFAULT,
    ) -> JsonValue:
        """
        Return the cached value for *key*, or call *factory* to compute and
        cache it.

        Args:
            key:     Redis key.
            factory: Async callable that returns the value to cache.
            ttl:     Cache TTL.

        Returns:
            The cached or freshly computed value.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set(key, value, ttl=ttl)
        return value

    # ── Hash operations ────────────────────────────────────────────────────

    async def hget(self, name: str, field: str) -> str | None:
        """Return the value of *field* in hash *name*."""
        return await self.client.hget(name, field)

    async def hset(self, name: str, mapping: dict[str, Any]) -> int:
        """Set multiple fields in hash *name*. Returns the number of new fields."""
        return await self.client.hset(name, mapping=mapping)  # type: ignore[arg-type]

    async def hgetall(self, name: str) -> dict[str, str]:
        """Return all fields and values in hash *name*."""
        return await self.client.hgetall(name)

    async def hdel(self, name: str, *fields: str) -> int:
        """Delete one or more fields from hash *name*."""
        return await self.client.hdel(name, *fields)

    # ── List operations ────────────────────────────────────────────────────

    async def lpush(self, key: str, *values: str) -> int:
        """Push values onto the left of list *key*."""
        return await self.client.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        """Push values onto the right of list *key*."""
        return await self.client.rpush(key, *values)

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> list[str]:
        """Return elements from index *start* to *end* (inclusive)."""
        return await self.client.lrange(key, start, end)

    async def llen(self, key: str) -> int:
        """Return the length of list *key*."""
        return await self.client.llen(key)

    # ── Session storage ────────────────────────────────────────────────────

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def create_session(
        self,
        data: dict[str, Any],
        *,
        ttl: int = 3600,
        session_id: str | None = None,
    ) -> str:
        """
        Store a user session and return its ID.

        Args:
            data:       Session payload (must be JSON-serialisable).
            ttl:        Session lifetime in seconds (default: 1 hour).
            session_id: Optional pre-generated session ID.

        Returns:
            The session ID string.
        """
        sid = session_id or str(uuid.uuid4())
        key = self._session_key(sid)
        await self.set(key, data, ttl=ttl)
        return sid

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Retrieve a session by ID.  Returns None if expired or not found.
        """
        key = self._session_key(session_id)
        data = await self.get(key)
        if not isinstance(data, dict):
            return None
        return data

    async def update_session(
        self,
        session_id: str,
        data: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> bool:
        """
        Update the session payload.  Optionally resets the TTL.

        Returns False if the session does not exist.
        """
        key = self._session_key(session_id)
        if not await self.exists(key):
            return False
        remaining = ttl or await self.ttl(key)
        if remaining < 0:
            remaining = 3600
        await self.set(key, data, ttl=remaining)
        return True

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.  Returns True if it existed."""
        return bool(await self.delete(self._session_key(session_id)))

    async def extend_session(self, session_id: str, *, extra_seconds: int = 3600) -> bool:
        """Add *extra_seconds* to a session's remaining TTL."""
        key = self._session_key(session_id)
        remaining = await self.ttl(key)
        if remaining < 0:
            return False
        return await self.expire(key, remaining + extra_seconds)

    # ── Pub/Sub ────────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: JsonValue) -> int:
        """
        Publish *message* to *channel*.

        Args:
            channel: Redis pub/sub channel name.
            message: JSON-serialisable payload.

        Returns:
            Number of subscribers that received the message.
        """
        payload = json.dumps(message, default=str)
        return await self.client.publish(channel, payload)

    async def subscribe(self, *channels: str) -> PubSub:
        """
        Subscribe to one or more channels and return a ``PubSub`` handle.

        The caller is responsible for reading messages and closing the handle.

        Usage::

            pubsub = await redis_client.subscribe("events:avatar")
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
        """
        pubsub: PubSub = self.client.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

    async def psubscribe(self, *patterns: str) -> PubSub:
        """Subscribe to channels matching *patterns* (glob-style)."""
        pubsub: PubSub = self.client.pubsub()
        await pubsub.psubscribe(*patterns)
        return pubsub

    async def listen_to_channel(
        self, channel: str
    ) -> AsyncGenerator[JsonValue, None]:
        """
        Async generator that yields decoded messages from *channel*.

        Automatically cleans up the pubsub connection when the generator is
        exhausted or cancelled.

        Usage::

            async for event in redis_client.listen_to_channel("events:room:42"):
                process(event)
        """
        pubsub = await self.subscribe(channel)
        try:
            async for raw_message in pubsub.listen():
                if raw_message["type"] != "message":
                    continue
                try:
                    yield json.loads(raw_message["data"])
                except json.JSONDecodeError:
                    yield raw_message["data"]
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    # ── Distributed lock ───────────────────────────────────────────────────

    @asynccontextmanager
    async def lock(
        self,
        name: str,
        *,
        timeout: float = 10.0,
        blocking: bool = True,
        blocking_timeout: float = 5.0,
    ) -> AsyncGenerator[bool, None]:
        """
        Acquire a distributed Redis lock.

        Args:
            name:             Lock key (will be prefixed with ``lock:``).
            timeout:          Maximum time the lock is held (seconds).
            blocking:         Whether to block until the lock is acquired.
            blocking_timeout: How long to wait when ``blocking=True``.

        Yields:
            True if the lock was acquired; False otherwise.

        Usage::

            async with redis_client.lock("process:avatar:42") as acquired:
                if acquired:
                    await do_work()
        """
        redis_lock = self.client.lock(
            f"lock:{name}",
            timeout=timeout,
            blocking=blocking,
            blocking_timeout=blocking_timeout,
        )
        try:
            acquired = await redis_lock.acquire()
            yield acquired
        except LockError:
            yield False
        finally:
            try:
                if await redis_lock.owned():
                    await redis_lock.release()
            except LockError:
                pass

    # ── Rate-limit helpers ─────────────────────────────────────────────────

    async def rate_limit_check(
        self,
        identifier: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Sliding-window rate limit check using a Redis counter.

        Args:
            identifier:     Unique key (e.g. ``rate:user:42:upload``).
            limit:          Maximum allowed requests per window.
            window_seconds: Length of the sliding window in seconds.

        Returns:
            A tuple of ``(allowed, current_count, remaining)``.
        """
        key = f"rate:{identifier}"
        pipe = self.client.pipeline(transaction=True)
        await pipe.incr(key)
        await pipe.expire(key, window_seconds)
        results = await pipe.execute()

        current: int = results[0]
        allowed = current <= limit
        remaining = max(0, limit - current)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                current=current,
                limit=limit,
            )

        return allowed, current, remaining

    # ── Pipeline ───────────────────────────────────────────────────────────

    def pipeline(self, *, transaction: bool = True) -> Any:
        """Return a Redis pipeline for batching multiple commands."""
        return self.client.pipeline(transaction=transaction)

    # ── Scan iterator ─────────────────────────────────────────────────────

    async def scan_iter(
        self,
        pattern: str = "*",
        *,
        count: int = 100,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator that iterates over keys matching *pattern* using SCAN.

        Preferred over ``keys()`` in production as it does not block the server.
        """
        async for key in self.client.scan_iter(match=pattern, count=count):
            yield key

    # ── Flush helpers (test/admin only) ───────────────────────────────────

    async def flush_db(self) -> None:
        """
        Flush all keys in the current Redis database.

        **Destructive.** Never call in production.
        """
        if settings.is_production:
            raise RuntimeError("flush_db() must never be called in production")
        await self.client.flushdb(asynchronous=True)
        logger.warning("redis_db_flushed")

    async def flush_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching *pattern*.

        Returns the number of keys deleted.
        """
        count = 0
        async for key in self.scan_iter(pattern):
            await self.delete(key)
            count += 1
        logger.info("redis_pattern_flushed", pattern=pattern, count=count)
        return count

    # ── Async health check ─────────────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """
        Return a dict summarising the connection state.

        Suitable for inclusion in the ``/ready`` probe response.
        """
        try:
            await self.ping()
            info = await self.client.info("server")
            return {
                "status": "ok",
                "version": info.get("redis_version", "unknown"),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", -1),
            }
        except RedisError as exc:
            return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

redis_client: RedisClient = RedisClient()

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """
    FastAPI dependency that yields the shared ``RedisClient`` instance.

    Usage::

        @router.get("/cache/{key}")
        async def read_cache(key: str, cache: RedisClient = Depends(get_redis)):
            return await cache.get(key)
    """
    yield redis_client


# ---------------------------------------------------------------------------
# Pub/Sub broadcast helper (module-level convenience)
# ---------------------------------------------------------------------------


async def broadcast(channel: str, event_type: str, payload: dict[str, Any]) -> None:
    """
    Publish a typed event to a Redis pub/sub channel.

    Args:
        channel:    Target channel name.
        event_type: Short event identifier (e.g. ``"avatar.ready"``).
        payload:    Arbitrary JSON-serialisable data.
    """
    message: dict[str, Any] = {
        "type": event_type,
        "data": payload,
        "ts": asyncio.get_event_loop().time(),
    }
    subscribers = await redis_client.publish(channel, message)
    logger.debug("event_broadcast", channel=channel, event_type=event_type, subscribers=subscribers)
