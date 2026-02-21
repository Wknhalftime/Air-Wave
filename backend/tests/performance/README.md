# Performance Testing Tools

This directory contains performance testing tools for the library navigation system.

## Tools

### 1. Load Testing (`load_test.py`)

Simulates realistic user behavior with concurrent users browsing the library.

**Features:**
- Concurrent user simulation
- Realistic browsing patterns (artist → works → recordings)
- Random filter application
- Response time tracking
- Throughput measurement
- Percentile calculations (P50, P95, P99)

**Usage:**

```bash
# Install dependencies
pip install aiohttp rich

# Run with default settings (10 users, 60 seconds)
python -m tests.performance.load_test

# Run with 50 concurrent users for 2 minutes
python -m tests.performance.load_test --users 50 --duration 120

# Test against production
python -m tests.performance.load_test --url https://api.example.com --users 100 --duration 300
```

**Output:**
- Detailed table of endpoint performance
- Summary statistics (total requests, errors, throughput)
- Response time percentiles

---

### 2. Cache Analysis (`cache_analysis.py`)

Measures cache effectiveness by comparing first-request (cache miss) vs second-request (cache hit) performance.

**Features:**
- Cache hit rate calculation
- Response time comparison (hit vs miss)
- Speedup measurement
- Recommendations for TTL tuning

**Usage:**

```bash
# Run with default settings (50 requests per endpoint)
python -m tests.performance.cache_analysis

# Run with 100 requests per endpoint
python -m tests.performance.cache_analysis --requests 100

# Test against production
python -m tests.performance.cache_analysis --url https://api.example.com
```

**Output:**
- Cache hit rates by endpoint
- Average response times (hit vs miss)
- Speedup factors
- Recommendations for improvement

---

## Quick Start

### 1. Set Up Test Environment

```bash
# Start the backend server
cd backend
poetry run uvicorn airwave.api.main:app --reload

# In another terminal, seed the database with test data
poetry run python -m airwave.worker.seed  # if available
```

### 2. Run Load Test

```bash
# Quick test (10 users, 30 seconds)
python -m tests.performance.load_test --users 10 --duration 30
```

### 3. Run Cache Analysis

```bash
# Analyze cache performance
python -m tests.performance.cache_analysis --requests 50
```

### 4. Review Results

Check the output for:
- Response times (should be < 100ms for uncached, < 10ms for cached)
- Cache hit rates (should be > 60%)
- Error rates (should be 0%)
- Throughput (should be > 10 req/s for 10 users)

---

## Performance Targets

### Response Times

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Cached requests | < 5ms | < 10ms | > 10ms |
| Uncached requests | < 50ms | < 100ms | > 100ms |
| P95 | < 50ms | < 200ms | > 200ms |
| P99 | < 100ms | < 500ms | > 500ms |

### Cache Performance

| Endpoint | Target Hit Rate |
|----------|----------------|
| GET /artists/{id} | > 80% |
| GET /works/{id} | > 80% |
| GET /artists/{id}/works | > 60% |
| GET /works/{id}/recordings | > 50% |

### Throughput

| Concurrent Users | Target Throughput |
|------------------|-------------------|
| 10 | > 20 req/s |
| 50 | > 80 req/s |
| 100 | > 150 req/s |

---

## Troubleshooting

### "No artists found" Error

**Problem:** The database is empty.

**Solution:** Seed the database with test data:

```bash
# Option 1: Use existing library data
# Make sure you have artists, works, and recordings in the database

# Option 2: Create test data manually
poetry run python
>>> from airwave.core.models import Artist, Work, Recording
>>> # Create test data...
```

### Low Cache Hit Rates

**Problem:** Cache hit rates are below target.

**Possible Causes:**
1. TTL too short - Increase TTL in endpoint decorators
2. Too many unique requests - Normal for filtered endpoints
3. Cache not enabled - Check cache configuration

**Solution:**

```python
# Increase TTL in backend/src/airwave/api/routers/library.py
@cached(ttl=600)  # Increase from 300 to 600 seconds
async def get_artist(...):
    ...
```

### High Response Times

**Problem:** Response times exceed targets.

**Possible Causes:**
1. Database not indexed - Check migration applied
2. Large result sets - Reduce pagination limits
3. N+1 queries - Already optimized, check query logs

**Solution:**

```bash
# Enable query logging to identify slow queries
export DB_ECHO=true
poetry run uvicorn airwave.api.main:app

# Check for slow queries in logs
# Look for queries > 100ms
```

### Low Throughput

**Problem:** Throughput is below target.

**Possible Causes:**
1. Single-threaded server - Use multiple workers
2. Database connection pool too small - Increase pool size
3. CPU/memory limits - Check resource usage

**Solution:**

```bash
# Run with multiple workers
poetry run uvicorn airwave.api.main:app --workers 4

# Or use gunicorn
poetry run gunicorn airwave.api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## Advanced Usage

### Custom Test Scenarios

Modify `load_test.py` to test specific scenarios:

```python
# Example: Test only filtered recordings
async def simulate_user_session(self, session, artist_ids, user_id):
    # ... get artist and work ...
    
    # Always apply filters
    for status in ["matched", "unmatched"]:
        for source in ["library", "metadata"]:
            await self.test_endpoint(
                session,
                f"GET /works/{work_id}/recordings?status={status}&source={source}",
                ...
            )
```

### Continuous Performance Testing

Integrate into CI/CD pipeline:

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on: [push, pull_request]

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: pip install aiohttp rich
      - name: Run load test
        run: python -m tests.performance.load_test --users 10 --duration 30
      - name: Run cache analysis
        run: python -m tests.performance.cache_analysis --requests 50
```

---

## See Also

- [Performance Testing Guide](../../docs/testing/performance-testing.md) - Detailed guide
- [Architecture Documentation](../../docs/architecture/caching.md) - Caching system design
- [API Documentation](../../docs/api/library-navigation.md) - Endpoint specifications

