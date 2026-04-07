from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import get_settings
from logger import app_logger

# ------------------------------------------------------------------------------
# Module-level client — created once, reused across all requests.
# Motor manages its own internal connection pool, so a single client is correct.
# ------------------------------------------------------------------------------

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Returns the shared Motor client. Raises if not yet initialised."""
    if _client is None:
        raise RuntimeError("Database client is not initialised. Call connect_database() first.")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """
    FastAPI dependency — returns the active MongoDB database instance.

    Usage in a router:
        from fastapi import Depends
        from database import get_database

        @router.get("/")
        async def handler(db: AsyncIOMotorDatabase = Depends(get_database)):
            ...
    """
    settings = get_settings()
    return get_client()[settings.mongo.db_name]


# ------------------------------------------------------------------------------
# Lifecycle helpers — called from main.py lifespan
# ------------------------------------------------------------------------------

async def connect_database() -> None:
    """Opens the Motor client connection pool."""
    global _client
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongo.url)
    app_logger.info("MongoDB client initialised.")


async def ping_database() -> None:
    """
    Sends a lightweight 'ping' command to MongoDB.
    Raises an exception on startup if the database is unreachable,
    so we catch the problem before the first real request arrives.
    """
    db = get_database()
    await db.command("ping")
    app_logger.info("MongoDB ping successful — connection is healthy.")


async def close_database() -> None:
    """Closes the Motor client and releases all pooled connections."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        app_logger.info("MongoDB client closed.")
