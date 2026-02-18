from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.api.deps import get_db
from airwave.core.cache import cache
from airwave.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check system health and DB connection."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    return {"status": "ok", "database": db_status, "version": "0.1.0"}


@router.get("/config")
async def get_config():
    """Return public configuration."""
    return {
        "env": "development",  # Todo: Configurable
        "log_level": settings.LOG_LEVEL,
    }


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics for monitoring.

    Returns information about cache size, hit/miss rates, and expired entries.
    """
    stats = cache.stats()
    return {
        "cache_enabled": True,
        "total_entries": stats["total_entries"],
        "active_entries": stats["active_entries"],
        "expired_entries": stats["expired_entries"],
    }


@router.post("/cache/clear")
async def clear_cache():
    """Clear all cached entries.

    Useful for debugging or after data updates that should invalidate cache.
    """
    cache.clear()
    return {"status": "ok", "message": "Cache cleared successfully"}
