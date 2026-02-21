# Logging Infrastructure Audit & Recommendations

**Audit Date:** February 2026  
**Scope:** Backend application logs writing to `airwave.log`  
**Objective:** Assess current logging quality and provide actionable recommendations for production troubleshooting

---

## 1. Executive Summary

The Airwave backend uses **Loguru** for logging with a single rotating file (`airwave.log`) and console output. Logging coverage is **inconsistent** across modules: the scanner has extensive logs, but critical paths (matcher, normalization, identity resolution) have minimal or no logging. Three modules use stdlib `logging` instead of Loguru, which may cause their logs to be **lost or unformatted**. There is no request correlation (request IDs), no structured logging for parsing, and no log categorization for filtering.

---

## 2. Current Logging Infrastructure

### 2.1 Configuration (`airwave/core/logger.py`)

| Aspect | Current State |
|--------|---------------|
| Framework | Loguru |
| Log file | `{DATA_DIR}/logs/airwave.log` |
| Rotation | 10 MB |
| Retention | 10 days |
| Compression | ZIP |
| Async file I/O | Yes (`enqueue=True`) |
| Backtrace/diagnose | Enabled for file handler |
| Log level | From `settings.LOG_LEVEL` (default: INFO) |

### 2.2 Modules Using Loguru

- `admin.py`, `scanner.py`, `db.py`, `query_logger.py`, `cache.py`, `main.py` (worker)
- `matcher.py`, `importer.py`, `fingerprint.py`, `seed.py`, `worker/bulk_import.py`
- `performance.py`, `vector_db.py`, `utils.py`

### 2.3 Modules Using stdlib `logging` (Problematic)

| Module | Issue |
|--------|-------|
| `musicbrainz_client.py` | Uses `logging.getLogger(__name__)` – may not appear in airwave.log |
| `export.py` | Same – export operations may be invisible |
| `identity_resolver.py` | Same – artist resolution/splitting logs may be lost |

Loguru does **not** automatically intercept stdlib `logging`. Without `logger.start(intercept_handler=True)` or similar, these modules' output goes to the root stdlib handler, which is typically unconfigured.

### 2.4 Middleware

- **QueryLoggingMiddleware**: Logs slow requests (>1s) at WARNING; other requests at DEBUG
- No request ID / correlation ID
- No per-request context for tracing through the stack

---

## 3. Logging Coverage by Domain

### 3.1 Scanner (`worker/scanner.py`)

**Strength:** Most comprehensive logging in the codebase.

- Start/end of scan, executor init, hash algorithm
- Fuzzy work matching with similarity scores
- File I/O errors, permission denied, metadata extraction failures
- Path index loading, move detection, orphan GC

**Gaps:**
- No timing for individual file processing
- No correlation with `task_id` in most log lines (only in progress updates)
- Race condition IntegrityError logged at DEBUG – hard to spot in production

### 3.2 Matcher (`worker/matcher.py`)

**Strength:** Discovery queue rebuild has INFO logs.

**Gaps:**
- `match_batch()` has **no logging** – impossible to trace why a match failed
- No logs for identity bridge hits vs. exact vs. variant vs. vector vs. alias
- No per-query timing
- No diagnostic output for threshold tuning (e.g., scores just below threshold)

### 3.3 Normalization (`core/normalization.py`)

**Strength:** None.

**Gaps:**
- **Zero logging** – normalization decisions (signature generation, title cleaning, part detection) are opaque
- Critical for debugging "why didn't X match Y" – e.g., unicode, case, punctuation differences

### 3.4 Identity Resolver (`worker/identity_resolver.py`)

**Strength:** Logs heuristic splits (but uses stdlib logging – may be lost).

**Gaps:**
- No logging when alias cache is used vs. miss
- No logging for collaboration splitting decisions
- Batch resolution has no summary (e.g., "Resolved 50/100 names, 3 new splits")

### 3.5 Importer (`worker/importer.py`)

**Strength:** DuckDB read logs, fallback warning.

**Gaps:**
- No per-batch match stats (e.g., "Batch 5: 80 exact, 15 variant, 5 unmatched")
- No logging for station creation/cache hits
- Commented-out trace/warning for invalid rows – no visibility

### 3.6 API Layer

**Strength:** QueryLoggingMiddleware for slow requests.

**Gaps:**
- No per-route request logging (only slow ones)
- No 4xx/5xx error logging at ERROR level
- No request ID for correlation
- Library, identity, discovery routers have **no** logging

### 3.7 MusicBrainz & Fingerprint

- **MusicBrainz**: Good error handling (stdlib) but may not reach airwave.log
- **Fingerprint**: Uses Loguru; logs exceptions only

---

## 4. Critical Gaps for Production Troubleshooting

1. **No correlation IDs** – Cannot trace a single request/job through API → matcher → scanner.
2. **Matcher is a black box** – No visibility into which strategy ran or why a match failed.
3. **Normalization is invisible** – Core transformation logic has no logging.
4. **Stdlib vs. Loguru mismatch** – 3 modules' logs may not appear in airwave.log.
5. **No structured fields** – All logs are freeform strings; hard to parse or aggregate.
6. **DEBUG logs only for fast requests** – At INFO, normal requests are invisible.
7. **No audit trail** – Admin actions (merge, bulk import, link) have minimal context.

---

## 5. Recommendations

### 5.1 Immediate Fixes

#### 5.1.1 Fix stdlib logging (choose one)

**Option A – Migrate to Loguru (recommended):**  
Change `musicbrainz_client.py`, `export.py`, and `identity_resolver.py` from:
```python
import logging
logger = logging.getLogger(__name__)
```
to:
```python
from loguru import logger
```

**Option B – Intercept stdlib logging in Loguru:**  
Add to `setup_logging()` after other handlers:

```python
import logging

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
```

Option A is simpler and keeps the codebase consistent.

#### 5.1.2 Add request ID middleware

```python
# airwave/api/middleware/request_id.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

async def dispatch(self, request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    with logger.contextualize(request_id=request_id):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

Use `logger.bind(request_id=request_id)` or Loguru's `contextvars` for async context.

### 5.2 Log Statement Additions

#### 5.2.1 Matcher (`matcher.py`)

| Location | Level | Example |
|----------|-------|---------|
| Start of `match_batch` | DEBUG | `"match_batch: {len(queries)} queries"` |
| After identity bridge lookup | DEBUG | `"Identity bridge hit: {sig} -> rec_id={rec_id}"` |
| After exact match | DEBUG | `"Exact match: {artist} - {title} -> rec_id={rec_id}"` |
| After variant match | INFO | `"Variant match: '{artist}' - '{title}' -> rec_id={rec_id} (artist_sim={a}, title_sim={t})"` |
| After vector match | INFO | `"Vector match: '{artist}' - '{title}' -> rec_id={rec_id} (dist={d})"` |
| No match (when explain=True or DEBUG) | DEBUG | `"No match: '{artist}' - '{title}' (best_candidate=...)"` |
| Batch timing | INFO | `"match_batch: {n} queries in {duration_ms}ms"` |

#### 5.2.2 Normalization (`normalization.py`)

| Location | Level | Example |
|----------|-------|---------|
| `generate_signature` (DEBUG only) | DEBUG | `"generate_signature: '{artist}' - '{title}' -> '{sig}'"` |
| `normalize_title` edge cases | DEBUG | `"normalize_title: '{raw}' -> '{norm}' (part_detected={part})"` |

Guard with `if logger.isEnabledFor("DEBUG")` or use `logger.opt(depth=1).debug(...)` to avoid string formatting overhead at INFO.

#### 5.2.3 Identity Resolver (`identity_resolver.py`)

| Location | Level | Example |
|----------|-------|---------|
| End of `resolve_batch` | INFO | `"resolve_batch: {n} names, {aliases_used} alias hits, {splits_created} new splits"` |
| Alias hit | DEBUG | `"Alias: '{raw}' -> '{resolved}'"` |
| New split proposal | INFO | `"Proposed split: '{raw}' -> {parts}"` (already present; ensure Loguru) |

#### 5.2.4 Importer (`importer.py`)

| Location | Level | Example |
|----------|-------|---------|
| After `process_batch` | INFO | `"process_batch: batch_id={id}, rows={n}, matched={m}, unmatched={u}"` |

#### 5.2.5 API Error Logging

| Location | Level | Example |
|----------|-------|---------|
| Exception handler (add global) | ERROR | `"Unhandled exception: {exc_type}: {exc_msg}"` with traceback |
| 4xx/5xx responses | WARNING/ERROR | `"HTTP {status}: {method} {path}"` |

#### 5.2.6 Scanner Enhancements

| Location | Level | Example |
|----------|-------|---------|
| Per-file processing start | DEBUG | `"Processing: {path} (task_id={task_id})"` |
| IntegrityError | WARNING | Promote from DEBUG so production can surface race conditions |

### 5.3 Structured Logging

Add a JSON handler for production parsing (e.g., ELK, Datadog):

```python
# Optional JSON handler for production
logger.add(
    str(log_file.with_suffix(".json")),
    rotation=settings.LOG_ROTATION,
    retention=settings.LOG_RETENTION,
    format="{message}",
    serialize=True,  # Loguru JSON output
    level=settings.LOG_LEVEL,
    filter=lambda record: record["extra"].get("json", False),
)
```

Use `logger.bind(...)` for structured fields:

```python
logger.bind(task_id=task_id, path=path).info("Processing file")
# Output: {"task_id": "abc", "path": "/foo/bar", "message": "Processing file", ...}
```

### 5.4 Log Level Guidelines

| Level | Use Case |
|-------|----------|
| DEBUG | Per-entity details (each query, each file, each signature) |
| INFO | Batch summaries, start/end of operations, key decisions (variant/vector match) |
| WARNING | Recoverable issues (fallback hash, permission denied, slow request) |
| ERROR | Unrecoverable (IntegrityError, network failure, import failure) |

### 5.5 Log File Organization

**Option A: Single file (current)**  
- Keep one `airwave.log`
- Add a `category` or `component` field: `logger.bind(component="scanner")`
- Filter by field in log aggregators

**Option B: Split by component (optional)**  
- `airwave.log` – API, system, db
- `airwave-scanner.log` – file processing
- `airwave-matcher.log` – matching, discovery, identity

Recommendation: Start with Option A and structured fields. Split only if file size or retention policies require it.

---

## 6. Best Practices Going Forward

1. **Use Loguru everywhere** – Replace `logging.getLogger(__name__)` with `from loguru import logger`.
2. **Include correlation IDs** – For API: `request_id`. For worker tasks: `task_id`. Bind at entry points.
3. **Log decisions, not just events** – "Matched via variant (0.87/0.82)" is more useful than "Match found."
4. **Avoid PII in logs** – No user emails, tokens. Paths and artist/title strings are usually acceptable.
5. **Use appropriate levels** – DEBUG for high volume, INFO for milestones, WARNING/ERROR for issues.
6. **Structured over freeform** – Prefer `logger.info("match", strategy="variant", artist_sim=0.87)` over long f-strings when aggregating.

---

## 7. Implementation Priority

| Priority | Item | Effort |
|----------|------|--------|
| P0 | Migrate musicbrainz_client, export, identity_resolver to Loguru | Low |
| P0 | Add matcher logging (batch start, strategy used, no-match at DEBUG) | Medium |
| P1 | Add request ID middleware | Low |
| P1 | Add importer batch stats | Low |
| P2 | Add normalization DEBUG logs (guarded) | Low |
| P2 | Add identity resolver summary log | Low |
| P3 | Structured JSON handler for production | Medium |
| P3 | Promote scanner IntegrityError to WARNING | Trivial |

---

## 8. Appendix: Current Log Sources (Summary)

| Component | File | Loguru? | Log Count (approx) |
|-----------|------|---------|--------------------|
| Scanner | scanner.py | Yes | ~60 |
| Matcher | matcher.py | Yes | ~4 |
| Importer | importer.py | Yes | ~3 |
| Identity Resolver | identity_resolver.py | No (stdlib) | ~1 |
| MusicBrainz | musicbrainz_client.py | No (stdlib) | ~10 |
| Export | export.py | No (stdlib) | ~3 |
| Admin | admin.py | Yes | ~8 |
| Fingerprint | fingerprint.py | Yes | ~4 |
| DB | db.py | Yes | ~3 |
| Cache | cache.py | Yes | ~6 |
| Query middleware | query_logger.py | Yes | 2 |
| Worker main | main.py | Yes | ~20 |
