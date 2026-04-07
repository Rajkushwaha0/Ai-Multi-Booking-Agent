import redis.asyncio as aioredis
from redis.asyncio import Redis
from config import get_settings
from logger import app_logger

# ------------------------------------------------------------------------------
# Module-level client — single async Redis connection pool for the whole app.
# All services (locks, idempotency, caching) share this one client.
# ------------------------------------------------------------------------------

_redis: Redis | None = None


def get_redis() -> Redis:
    """
    Returns the shared Redis client instance.

    Usage in any service:
        from redis_client import get_redis
        redis = get_redis()
        await redis.set("key", "value", ex=60)
    """
    if _redis is None:
        raise RuntimeError("Redis client is not initialised. Call connect_redis() first.")
    return _redis


# ------------------------------------------------------------------------------
# Lifecycle helpers — called from main.py lifespan
# ------------------------------------------------------------------------------

async def connect_redis() -> None:
    """
    Creates the async Redis client with a connection pool.
    decode_responses=True means all values come back as strings, not bytes.
    """
    global _redis
    settings = get_settings()
    _redis = aioredis.from_url(
        settings.redis.url,
        encoding="utf-8",
        decode_responses=True,
    )
    app_logger.info("Redis client initialised.")


async def ping_redis() -> None:
    """
    Sends a PING command to Redis on startup.
    Raises if Redis is unreachable so the app fails fast instead of silently.
    """
    client = get_redis()
    response = await client.ping()
    if not response:
        raise ConnectionError("Redis PING returned unexpected response.")
    app_logger.info("Redis ping successful — connection is healthy.")


async def close_redis() -> None:
    """Closes all connections in the Redis pool."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        app_logger.info("Redis client closed.")
