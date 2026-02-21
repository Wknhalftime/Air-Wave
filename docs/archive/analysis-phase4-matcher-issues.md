# Analysis: Phase 4 Matcher Issues

## Issue Summary

After applying the Phase 4 migration fix, two critical issues emerged:

1. **Over-matching in Discovery Queue** - Items are getting suggestions that shouldn't have them
2. **Match Tuner Page Not Loading** - `/api/v1/admin/match-samples` endpoint taking 4.3 seconds

## Root Cause Analysis

### Issue 1: Over-Matching in Discovery Queue

**Problem**: `run_discovery` suggests ALL matches without filtering by quality.

**Current Behavior** (`matcher.py` lines 530-581):
```python
# Runs match_batch on ALL unmatched items
matches = await self.match_batch(batch_queries)

# Populates suggested_work_id for ANY match found
for (qa, qt), (match_id, reason) in matches.items():
    if match_id:
        # Suggests EVERYTHING: Identity Bridge, Exact, High Confidence, Vector, etc.
        obj_map[sig].suggested_work_id = work_id
```

**Match Types Returned by `match_batch`** (in priority order):
1. **Identity Bridge** - Pre-verified permanent mappings (should be auto-linked, not suggested)
2. **Exact Match** - Exact normalized string match (safe to suggest)
3. **High Confidence** - 85% artist + 80% title (safe to suggest)
4. **Vector Strong** - Low cosine distance + title guard (might be too aggressive)
5. **Title+Vector** - Title similarity + vector distance (might be too aggressive)

**The Problem**:
- No filtering by match quality - ALL match types are suggested
- Identity Bridge matches should be auto-linked, not just suggested
- Vector matches might be too aggressive for auto-suggestion
- No concept of "needs review" vs "auto-accept" in DiscoveryQueue

**User's Expectation**:
- ❌ Do NOT suggest low-confidence matches (vector-only matches)
- ❌ Do NOT suggest items that need manual review
- ✅ Only suggest high-confidence matches (Exact, High Confidence)
- ✅ Auto-link Identity Bridge matches (they're already verified)

---

### Issue 2: Match Tuner Page Slow Loading

**Problem**: `/api/v1/admin/match-samples` endpoint taking 4.3 seconds.

**Current Behavior** (`admin.py` lines 170-249):
```python
# Fetches 30 random unmatched logs
logs = await session.execute(
    select(BroadcastLog)
    .where(BroadcastLog.work_id.is_(None))
    .order_by(func.random())
    .limit(30)  # User requested 30 samples
)

# Runs match_batch with explain=True for ALL 30 logs
results = await matcher.match_batch(queries, explain=True)
```

**Why It's Slow**:
1. **Vector search is expensive** - ChromaDB queries for each of 30 samples
2. **`explain=True` returns ALL candidates** - Not just the best match, but all candidates with scoring
3. **No caching** - Every page load runs fresh vector searches
4. **Random sampling** - `ORDER BY func.random()` is slow on large tables

**Performance Breakdown** (estimated):
- Random sampling: ~100ms
- Vector search (30 queries × ~100ms each): ~3000ms
- Candidate scoring and serialization: ~1000ms
- **Total: ~4100ms** ✅ Matches the observed 4384ms

---

### Issue 3: Phase 3 Remnants (Critical Bug)

**Problem**: `rematch_items_for_artist` still uses `suggested_recording_id` (Phase 3).

**Location**: `discovery.py` lines 516-517

```python
if rec_id and rec_id != item.suggested_recording_id:  # ❌ Phase 3
    item.suggested_recording_id = rec_id  # ❌ Phase 3
```

**Impact**: This would cause an `AttributeError` because `DiscoveryQueue` no longer has `suggested_recording_id` in Phase 4.

**Fix**: Change to `suggested_work_id` and handle work_id conversion.

---

## Proposed Solutions

### Solution 1: Filter Suggestions by Match Quality

**Option A: Only suggest high-confidence matches**
```python
# In run_discovery, filter by match reason
for (qa, qt), (match_id, reason) in matches.items():
    if match_id:
        sig = Normalizer.generate_signature(qa, qt)
        
        # Only suggest high-confidence matches
        if any(keyword in reason for keyword in ["Exact", "High Confidence", "Identity Bridge"]):
            # ... populate suggested_work_id
```

**Option B: Auto-link Identity Bridge, suggest high-confidence only**
```python
# Identity Bridge matches should be auto-linked (they're already verified)
if "Identity Bridge" in reason:
    # Auto-link to BroadcastLog.work_id
    # Remove from DiscoveryQueue
else if "Exact" in reason or "High Confidence" in reason:
    # Suggest for manual review
    obj_map[sig].suggested_work_id = work_id
# Else: Don't suggest (too low confidence)
```

**Recommendation**: Option B - Auto-link verified matches, suggest high-confidence only.

---

### Solution 2: Optimize Match Tuner Endpoint

**Option A: Reduce sample size**
```python
# Change default from 30 to 10
@router.get("/match-samples", response_model=List[MatchSample])
async def get_match_samples(
    limit: int = 10,  # Reduced from 20 (user requested 30)
```

**Option B: Add caching**
```python
# Cache results for 5 minutes
from functools import lru_cache
import time

_match_samples_cache = None
_cache_time = 0

@router.get("/match-samples")
async def get_match_samples(limit: int = 20):
    global _match_samples_cache, _cache_time
    
    if time.time() - _cache_time < 300:  # 5 minutes
        return _match_samples_cache[:limit]
    
    # ... fetch and cache
```

**Option C: Use LIMIT on vector search**
```python
# In matcher.py, limit candidates returned in explain mode
if explain:
    # Only return top 5 candidates instead of all
    serializable_candidates = serializable_candidates[:5]
```

**Recommendation**: Combination of A + C - Reduce default limit to 10 and limit candidates to 5.

---

### Solution 3: Fix Phase 3 Remnants

**Fix**: Update `rematch_items_for_artist` to use Phase 4 schema.

```python
async def rematch_items_for_artist(signatures: List[str]):
    for signature in signatures:
        item = await db.get(DiscoveryQueue, signature)
        if item:
            rec_id, reason = await matcher.find_match(item.raw_artist, item.raw_title)
            if rec_id:
                # Phase 4: Convert recording_id to work_id
                recording = await db.get(Recording, rec_id)
                if recording and recording.work_id:
                    if recording.work_id != item.suggested_work_id:
                        item.suggested_work_id = recording.work_id
                        updated_count += 1
```

---

## Implementation Plan

1. ✅ **Fix Phase 3 remnants** (Critical - causes errors)
2. ✅ **Optimize Match Tuner endpoint** (High priority - blocks admin workflow)
3. ⚠️ **Filter suggestions by match quality** (Needs user confirmation on desired behavior)


