"""Simple in-memory cache with TTL for API responses.

This module provides a lightweight caching mechanism for read-heavy endpoints
without requiring external dependencies like Redis. It's suitable for single-
instance deployments and development environments.

For production multi-instance deployments, consider replacing with Redis.
"""

import inspect
import threading
import time
from functools import wraps
from typing import Any, Callable, Optional
from loguru import logger


class SimpleCache:
    """Thread-safe in-memory cache with TTL support.
    
    This cache stores function results with a time-to-live (TTL) to reduce
    database load for frequently accessed, slowly changing data like artist
    and work details.
    
    Attributes:
        _cache: Dictionary storing cached values with timestamps.
        _default_ttl: Default time-to-live in seconds for cached entries.
    """
    
    def __init__(self, default_ttl: int = 300):
        """Initialize cache with default TTL.
        
        Args:
            default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes).
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired.
        
        Args:
            key: Cache key to retrieve.
            
        Returns:
            Cached value if found and not expired, None otherwise.
        """
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    logger.debug(f"Cache HIT: {key}")
                    return value
                del self._cache[key]
                logger.debug(f"Cache EXPIRED: {key}")
            logger.debug(f"Cache MISS: {key}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL.
        
        Args:
            key: Cache key to store.
            value: Value to cache.
            ttl: Time-to-live in seconds (uses default if None).
        """
        with self._lock:
            expiry = time.time() + (ttl or self._default_ttl)
            self._cache[key] = (value, expiry)
            logger.debug(f"Cache SET: {key} (TTL: {ttl or self._default_ttl}s)")
    
    def delete(self, key: str) -> None:
        """Delete value from cache.
        
        Args:
            key: Cache key to delete.
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache DELETE: {key}")
    
    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries from cache.
        
        Returns:
            Number of expired entries removed.
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if now >= expiry
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                logger.info(f"Cache cleanup: removed {len(expired_keys)} expired entries")
            return len(expired_keys)
    
    def stats(self) -> dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache size and expired count.
        """
        with self._lock:
            now = time.time()
            expired_count = sum(
                1 for _, expiry in self._cache.values()
                if now >= expiry
            )
            return {
                "total_entries": len(self._cache),
                "expired_entries": expired_count,
                "active_entries": len(self._cache) - expired_count,
            }


# Global cache instance
cache = SimpleCache(default_ttl=300)  # 5 minutes default


# Param names excluded from cache key generation (e.g. db session, request objects)
_DEFAULT_SKIP_PARAMS = frozenset({"db", "session", "request"})


def cached(
    ttl: Optional[int] = None,
    key_prefix: str = "",
    skip_params: frozenset[str] | None = None,
):
    """Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds (uses cache default if None).
        key_prefix: Prefix for cache keys to avoid collisions.
        skip_params: Param names to exclude from cache key (default: db, session, request).

    Returns:
        Decorated function that caches results.

    Example:
        @cached(ttl=600, key_prefix="artist")
        async def get_artist(artist_id: int, db: AsyncSession):
            return artist_data
    """
    skip = skip_params if skip_params is not None else _DEFAULT_SKIP_PARAMS

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments.
            # Skip params in skip_params (db, session, etc.) - they must not affect cache key.
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())
            cache_args = [
                str(arg) for i, arg in enumerate(args)
                if i < len(param_names) and param_names[i] not in skip
            ]
            cache_kwargs = {k: str(v) for k, v in kwargs.items() if k not in skip}
            
            key_parts = [key_prefix or func.__name__] + cache_args
            if cache_kwargs:
                key_parts.append(str(sorted(cache_kwargs.items())))
            
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

