# Performance Testing Guide

This guide explains how to perform performance testing and tuning for the library navigation system.

## Overview

Performance testing ensures the library navigation system can handle realistic user loads while maintaining acceptable response times.

**Testing Tools:**
- `load_test.py` - Load testing with concurrent users
- `cache_analysis.py` - Cache hit rate analysis
- SQLAlchemy query logging - Database query profiling

---

## Load Testing

### Running Load Tests

The load test script simulates realistic user behavior with concurrent users.

**Basic Usage:**

```bash
# Install dependencies
pip install aiohttp rich

# Run with default settings (10 users, 60 seconds)
python -m tests.performance.load_test

# Run with custom settings
python -m tests.performance.load_test --users 50 --duration 120

# Test against production
python -m tests.performance.load_test --url https://api.example.com --users 100 --duration 300
```

**Parameters:**
- `--users` - Number of concurrent users (default: 10)
- `--duration` - Test duration in seconds (default: 60)
- `--url` - Base URL (default: http://localhost:8000)

### User Simulation

Each simulated user performs the following actions:

1. **Browse Artists** - Select a random artist
2. **View Artist Detail** - GET `/library/artists/{id}`
3. **View Works** - GET `/library/artists/{id}/works?limit=24`
4. **Select Work** - Pick a random work
5. **View Work Detail** - GET `/library/works/{id}`
6. **View Recordings** - GET `/library/works/{id}/recordings?limit=100`
7. **Apply Filters** (50% of the time) - GET with `status` and `source` filters
8. **Think Time** - Wait 1-3 seconds before next action

### Interpreting Results

**Sample Output:**

```
Load Test Results
┌────────────────────────────────┬──────────┬──────────┬──────────┬──────────┬────────┬────────┐
│ Endpoint                       │ Requests │ Avg (ms) │ Min (ms) │ Max (ms) │ Errors │ Req/s  │
├────────────────────────────────┼──────────┼──────────┼──────────┼──────────┼────────┼────────┤
│ GET /artists/{id}              │      245 │     2.34 │     0.89 │    45.23 │      0 │   4.08 │
│ GET /artists/{id}/works        │      245 │     3.12 │     1.23 │    52.34 │      0 │   4.08 │
│ GET /works/{id}                │      245 │     2.45 │     0.95 │    48.12 │      0 │   4.08 │
│ GET /works/{id}/recordings     │      245 │     4.56 │     1.45 │    67.89 │      0 │   4.08 │
│ GET /works/{id}/recordings (*) │      123 │     5.23 │     1.67 │    72.45 │      0 │   2.05 │
└────────────────────────────────┴──────────┴──────────┴──────────┴──────────┴────────┴────────┘

Summary:
Total Requests: 1103
Total Errors: 0
Error Rate: 0.00%
Total Duration: 60.23s
Throughput: 18.31 req/s

Response Time Percentiles:
P50: 2.89ms
P95: 15.67ms
P99: 45.23ms
```

**Key Metrics:**

- **Avg (ms)** - Average response time
  - ✅ Good: < 10ms (cached)
  - ✅ Good: < 100ms (uncached)
  - ⚠️ Warning: 100-500ms
  - ❌ Poor: > 500ms

- **P95/P99** - 95th/99th percentile response times
  - ✅ Good: P95 < 50ms, P99 < 100ms
  - ⚠️ Warning: P95 < 200ms, P99 < 500ms
  - ❌ Poor: P95 > 200ms, P99 > 500ms

- **Throughput** - Requests per second
  - ✅ Good: > 10 req/s (single instance)
  - ⚠️ Warning: 5-10 req/s
  - ❌ Poor: < 5 req/s

- **Error Rate** - Percentage of failed requests
  - ✅ Good: 0%
  - ⚠️ Warning: < 1%
  - ❌ Poor: > 1%

### Performance Targets

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Avg Response Time (cached) | < 5ms | < 10ms | > 10ms |
| Avg Response Time (uncached) | < 50ms | < 100ms | > 100ms |
| P95 Response Time | < 50ms | < 200ms | > 200ms |
| P99 Response Time | < 100ms | < 500ms | > 500ms |
| Throughput (10 users) | > 20 req/s | > 10 req/s | < 10 req/s |
| Error Rate | 0% | < 0.1% | > 0.1% |

---

## Cache Analysis

### Running Cache Analysis

The cache analysis script measures cache effectiveness.

**Basic Usage:**

```bash
# Run with default settings (50 requests per endpoint)
python -m tests.performance.cache_analysis

# Run with more requests
python -m tests.performance.cache_analysis --requests 100

# Test against production
python -m tests.performance.cache_analysis --url https://api.example.com
```

**Parameters:**
- `--requests` - Number of requests per endpoint (default: 50)
- `--url` - Base URL (default: http://localhost:8000)

### Interpreting Results

**Sample Output:**

```
Cache Performance Analysis
┌──────────────────────────┬──────────┬──────────┬──────────────┬───────────────┬─────────┐
│ Endpoint                 │ Requests │ Hit Rate │ Avg Hit (ms) │ Avg Miss (ms) │ Speedup │
├──────────────────────────┼──────────┼──────────┼──────────────┼───────────────┼─────────┤
│ GET /artists/{id}        │      100 │    85.0% │         0.89 │         45.23 │   50.8x │
│ GET /artists/{id}/works  │      100 │    72.0% │         1.23 │         52.34 │   42.6x │
└──────────────────────────┴──────────┴──────────┴──────────────┴───────────────┴─────────┘

Recommendations:
✓ GET /artists/{id}: Excellent hit rate (85.0%)
ℹ GET /artists/{id}/works: Good hit rate (72.0%)

Overall Statistics:
Total Requests: 200
Total Cache Hits: 157
Overall Hit Rate: 78.5%
```

**Key Metrics:**

- **Hit Rate** - Percentage of requests served from cache
  - ✅ Excellent: > 80%
  - ✅ Good: 60-80%
  - ⚠️ Fair: 40-60%
  - ❌ Poor: < 40%

- **Speedup** - How much faster cached requests are
  - ✅ Good: > 20x
  - ⚠️ Warning: 10-20x
  - ❌ Poor: < 10x

### Cache Hit Rate Targets

| Endpoint | Target Hit Rate | Reason |
|----------|----------------|--------|
| GET /artists/{id} | > 80% | Users browse same artists repeatedly |
| GET /works/{id} | > 80% | Work details rarely change |
| GET /artists/{id}/works | > 60% | Pagination reduces hit rate |
| GET /works/{id}/recordings | > 50% | Filters reduce hit rate |

---

## Query Profiling

### Enabling Query Logging

Enable SQLAlchemy query logging to identify slow queries.

**Method 1: Environment Variable**

```bash
# Set environment variable
export DB_ECHO=true

# Start server
python -m uvicorn airwave.api.main:app
```

**Method 2: Configuration File**

```python
# backend/src/airwave/core/config.py
class Settings(BaseSettings):
    DB_ECHO: bool = True  # Enable query logging
```

### Analyzing Query Logs

**Sample Log Output:**

```sql
2024-02-18 10:15:23,456 INFO sqlalchemy.engine.Engine 
SELECT artists.id, artists.name, artists.musicbrainz_id
FROM artists
WHERE artists.id = ?
[45.2ms] (42,)

2024-02-18 10:15:23,502 INFO sqlalchemy.engine.Engine
SELECT works.id, works.title, 
  (SELECT GROUP_CONCAT(artists.name, ', ')
   FROM work_artists
   JOIN artists ON work_artists.artist_id = artists.id
   WHERE work_artists.work_id = works.id) AS artist_names,
  COUNT(recordings.id) AS recording_count
FROM works
LEFT JOIN recordings ON recordings.work_id = works.id
WHERE works.artist_id = ?
GROUP BY works.id
ORDER BY works.title
LIMIT ? OFFSET ?
[123.4ms] (42, 24, 0)
```

**What to Look For:**

1. **Slow Queries** (> 100ms)
   - Check for missing indexes
   - Consider query optimization
   - Add caching

2. **N+1 Queries**
   - Multiple queries for related data
   - Use joins or subqueries
   - Already optimized in current implementation

3. **Full Table Scans**
   - Queries without WHERE clause
   - Missing indexes on foreign keys
   - Already optimized with indexes

### Query Optimization Checklist

✅ **Already Implemented:**
- Indexes on foreign keys (`artist_id`, `work_id`, `recording_id`)
- Correlated scalar subqueries for multi-artist works
- Aggregation at database level (COUNT, GROUP_CONCAT)
- Pagination with LIMIT/OFFSET

🔄 **Future Optimizations:**
- Materialized views for complex aggregations
- Database-level caching (Redis)
- Read replicas for scaling
- Connection pooling tuning

---

## Memory Profiling

### Monitoring Memory Usage

**Using Python's memory_profiler:**

```bash
# Install memory_profiler
pip install memory-profiler

# Profile a specific function
python -m memory_profiler backend/src/airwave/api/routers/library.py
```

**Expected Memory Usage:**

| Component | Memory Usage |
|-----------|--------------|
| Cache (1000 entries) | ~25 MB |
| Database connections | ~10 MB per connection |
| FastAPI app | ~50 MB base |
| **Total (single instance)** | **~100-150 MB** |

### Cache Memory Limits

The in-memory cache grows with usage. Monitor and set limits:

```python
# Future: Add max_size to SimpleCache
class SimpleCache:
    def __init__(self, default_ttl: int = 300, max_size: int = 10000):
        self._max_size = max_size
        # Implement LRU eviction when size exceeds max_size
```

---

## Production Recommendations

### Deployment Configuration

**Recommended Settings:**

```yaml
# docker-compose.yml or similar
services:
  api:
    environment:
      - DB_ECHO=false  # Disable query logging in production
      - CACHE_DEFAULT_TTL=300  # 5 minutes
    resources:
      limits:
        memory: 512M  # Limit memory usage
        cpus: '1.0'   # Limit CPU usage
    deploy:
      replicas: 2  # Run multiple instances
```

**Load Balancer Configuration:**

```nginx
# nginx.conf
upstream api_backend {
    least_conn;  # Use least connections algorithm
    server api1:8000;
    server api2:8000;
}

server {
    location /api/ {
        proxy_pass http://api_backend;
        proxy_cache api_cache;
        proxy_cache_valid 200 5m;
    }
}
```

### Scaling Guidelines

| Concurrent Users | Instances | Memory | CPU |
|------------------|-----------|--------|-----|
| < 50 | 1 | 512 MB | 1 core |
| 50-200 | 2-3 | 1 GB | 2 cores |
| 200-500 | 3-5 | 2 GB | 4 cores |
| > 500 | 5+ | 4 GB+ | 8+ cores |

### Monitoring Alerts

Set up alerts for:

- **Response Time** - Alert if P95 > 200ms
- **Error Rate** - Alert if > 0.1%
- **Cache Hit Rate** - Alert if < 50%
- **Memory Usage** - Alert if > 80% of limit
- **CPU Usage** - Alert if > 80%

---

## See Also

- [Architecture Documentation](../architecture/caching.md) - Caching system design
- [API Documentation](../api/library-navigation.md) - Endpoint specifications
- [Developer Guide](../developer-guide/extending-navigation.md) - Adding new endpoints

