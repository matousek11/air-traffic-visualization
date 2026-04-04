"""Lazy Redis client and helpers for optional caching."""


import redis
from redis.exceptions import RedisError

from common.helpers.env import Env
from common.helpers.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)

_redis_client: redis.Redis | None = None
_env = Env()


def get_latest_position_cache_ttl_seconds() -> int:
    """Return TTL for latest-position cache entries.

    Returns:
        TTL in seconds from REDIS_LATEST_POSITION_TTL_SECONDS or default.
    """
    value = _env.int("REDIS_LATEST_POSITION_TTL_SECONDS")

    if value < 0:
        raise ValueError(
            "REDIS_LATEST_POSITION_TTL_SECONDS must be non-negative"
        )
    return value


def _build_redis_client() -> redis.Redis:
    """Create a new Redis client from environment variables.

    Returns:
        Configured redis.Redis instance.
    """
    return redis.Redis(
        host=_env.str("REDIS_HOST", default="localhost"),
        port=_env.int("REDIS_PORT", default=6379),
        db=_env.int("REDIS_DB", default=0),
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
    )


def get_redis() -> redis.Redis:
    """Return a shared Redis client.

    Returns:
        Singleton redis.Redis when configured.
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = _build_redis_client()
    return _redis_client


def try_cache_get(key: str) -> str | None:
    """Read a string value from Redis, return None on miss or error.

    Args:
        key: Redis key.

    Returns:
        Cached string if present, None on miss, misconfiguration, or error.
    """
    try:
        return get_redis().get(key)
    except RedisError as exc:
        logger.warning("Redis GET failed for %s: %s", key, exc)
        return None


def try_cache_set(key: str, ttl_seconds: int, value: str) -> None:
    """Set a key with TTL, log, and ignore on failure.

    Args:
        key: Redis key.
        ttl_seconds: Time to live in seconds.
        value: String payload.
    """
    try:
        get_redis().setex(key, ttl_seconds, value)
    except RedisError as exc:
        logger.warning("Redis SETEX failed for %s: %s", key, exc)
