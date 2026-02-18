# Caching Architecture

This document describes the caching system used in the library navigation feature.

## Overview

The library navigation system uses an in-memory cache with TTL (Time-To-Live) support to optimize performance and reduce database load.

**Key Features:**
- Thread-safe in-memory cache
- Automatic expiration based on TTL
- Function-level caching with decorator
- Cache statistics and monitoring
- Manual cache invalidation

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      API Endpoints                          │
│  /library/artists/{id}  /library/works/{id}  etc.          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   @cached Decorator                         │
│  - Generates cache key from function name + args            │
│  - Checks cache before calling function                     │
│  - Stores result in cache with TTL                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    SimpleCache Class                        │
│  - Thread-safe dictionary storage                           │
│  - TTL-based expiration                                     │
│  - Automatic cleanup of expired entries                     │
│  - Statistics tracking (hits, misses, expired)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Database Queries                          │
│  SQLAlchemy async queries with optimizations                │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation

### SimpleCache Class

**Location:** `backend/src/airwave/core/cache.py`

**Key Methods:**

```python
class SimpleCache:
    def __init__(self, default_ttl: int = 300):
        """Initialize cache with default TTL (5 minutes)"""
        
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, return None if expired/missing"""
        
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Store value in cache with TTL"""
        
    def delete(self, key: str):
        """Remove specific key from cache"""
        
    def clear(self):
        """Clear all cache entries"""
        
    def stats(self) -> dict:
        """Get cache statistics"""
```

**Storage Format:**

Each cache entry is stored as a tuple:
```python
(value, expiration_timestamp)
```

**Thread Safety:**

The cache uses Python's built-in dictionary which is thread-safe for basic operations in CPython due to the GIL (Global Interpreter Lock).

---

### @cached Decorator

**Usage:**

```python
from airwave.core.cache import cached

@cached(ttl=300)  # 5 minutes
async def get_artist(db: AsyncSession, artist_id: int) -> Optional[Artist]:
    # Database query here
    pass
```

**How It Works:**

1. **Key Generation:** Combines function name and arguments
   ```python
   key = f"{func.__name__}:{args}:{kwargs}"
   ```

2. **Cache Lookup:** Checks if key exists and is not expired
   ```python
   cached_value = cache.get(key)
   if cached_value is not None:
       return cached_value
   ```

3. **Function Execution:** If cache miss, execute function
   ```python
   result = await func(*args, **kwargs)
   ```

4. **Cache Storage:** Store result with TTL
   ```python
   cache.set(key, result, ttl=ttl)
   return result
   ```

---

## TTL Strategy

Different endpoints use different TTL values based on data volatility:

| Endpoint | TTL | Rationale |
|----------|-----|-----------|
| `GET /library/artists/{id}` | 300s (5 min) | Artist metadata rarely changes |
| `GET /library/works/{id}` | 300s (5 min) | Work metadata rarely changes |
| `GET /library/artists/{id}/works` | 180s (3 min) | Work lists change moderately |
| `GET /library/works/{id}/recordings` (no filters) | 180s (3 min) | Recording lists change moderately |
| `GET /library/works/{id}/recordings` (with filters) | 120s (2 min) | Filtered results change frequently |

**Design Principles:**

1. **Detail endpoints** (single resource) → Longer TTL (5 min)
   - Less likely to change
   - Higher cache hit rate
   
2. **List endpoints** (multiple resources) → Medium TTL (3 min)
   - Moderate change frequency
   - Balance between freshness and performance

3. **Filtered endpoints** → Shorter TTL (2 min)
   - More volatile data
   - User-specific results

---

## Cache Key Design

Cache keys are generated from function name and arguments:

```python
# Example: get_artist(db, artist_id=42)
key = "get_artist:42"

# Example: list_artist_works(db, artist_id=42, skip=0, limit=24)
key = "list_artist_works:42:0:24"

# Example: list_work_recordings(db, work_id=123, status="matched", source="library")
key = "list_work_recordings:123:matched:library"
```

**Important:** The `db` session is excluded from the key to ensure consistent caching across requests.

---

## Cache Statistics

The cache tracks the following statistics:

```python
{
    "cache_enabled": true,
    "total_entries": 42,      # Total entries in cache
    "active_entries": 38,     # Non-expired entries
    "expired_entries": 4      # Expired but not yet cleaned up
}
```

**Access via API:**
```bash
GET /api/v1/system/cache/stats
```

---

## Cache Invalidation

### Automatic Invalidation

Entries are automatically invalidated when:
- TTL expires
- Cache is full (LRU eviction - not implemented yet)

### Manual Invalidation

**Clear All Cache:**
```bash
POST /api/v1/system/cache/clear
```

**Use Cases:**
- After bulk data imports
- After manual database changes
- For testing purposes

**Implementation:**
```python
from airwave.core.cache import cache

cache.clear()
```

---

## Performance Characteristics

### Memory Usage

**Estimated memory per entry:**
- Cache key: ~50-100 bytes
- Cached value: Varies by endpoint
  - Artist detail: ~200 bytes
  - Work list (24 items): ~5 KB
  - Recording list (100 items): ~20 KB

**Total memory for 1000 active entries:**
- ~25 MB (conservative estimate)

### Cache Hit Rate

**Expected hit rates:**
- Artist detail: 80-90% (users browse same artists)
- Work lists: 60-70% (pagination reduces hit rate)
- Recording lists: 40-50% (filters reduce hit rate)

### Performance Improvement

**Without cache:**
- Artist detail: ~50ms (database query)
- Work list (24 items): ~100ms
- Recording list (100 items): ~200ms

**With cache:**
- All endpoints: <1ms (memory lookup)

**Speedup:** 50-200x faster for cached requests

---

## Limitations

### Current Limitations

1. **Single-Instance Only**
   - Cache is in-memory, not shared across instances
   - Not suitable for multi-instance deployments
   - Solution: Use Redis for distributed caching

2. **No LRU Eviction**
   - Cache grows indefinitely until TTL expires
   - Solution: Implement LRU eviction policy

3. **No Persistence**
   - Cache is lost on server restart
   - Solution: Optional Redis persistence

4. **No Cache Warming**
   - First request after restart is slow
   - Solution: Implement cache warming on startup

### Future Improvements

1. **Redis Integration**
   ```python
   # Optional Redis backend
   if settings.REDIS_URL:
       cache = RedisCache(settings.REDIS_URL)
   else:
       cache = SimpleCache()
   ```

2. **LRU Eviction**
   ```python
   class SimpleCache:
       def __init__(self, max_size: int = 10000):
           self._max_size = max_size
           # Implement LRU eviction
   ```

3. **Cache Warming**
   ```python
   async def warm_cache():
       # Pre-load popular artists
       for artist_id in popular_artist_ids:
           await get_artist(db, artist_id)
   ```

4. **Selective Invalidation**
   ```python
   # Invalidate specific artist's cache
   cache.delete_pattern(f"*:artist_id={artist_id}:*")
   ```

---

## Testing

### Test Fixtures

Tests use a fixture to clear cache before each test:

```python
@pytest.fixture(scope="function")
async def db_engine():
    cache.clear()  # Clear cache before each test
    # ... rest of fixture
```

### Testing Cache Behavior

```python
def test_cache_hit():
    # First call - cache miss
    result1 = get_artist(db, 42)
    assert cache.stats()["total_entries"] == 1
    
    # Second call - cache hit
    result2 = get_artist(db, 42)
    assert result1 == result2
    assert cache.stats()["total_entries"] == 1  # No new entry

def test_cache_expiration():
    # Set short TTL
    @cached(ttl=1)
    async def get_data():
        return "data"
    
    result1 = await get_data()
    time.sleep(2)  # Wait for expiration
    result2 = await get_data()
    
    # Should have fetched twice
    assert cache.stats()["expired_entries"] >= 1
```

---

## See Also

- [API Documentation](../api/library-navigation.md) - Cache management endpoints
- [Developer Guide](../developer-guide/extending-navigation.md) - Adding caching to new endpoints
- [Performance Testing](../testing/performance.md) - Cache performance benchmarks

