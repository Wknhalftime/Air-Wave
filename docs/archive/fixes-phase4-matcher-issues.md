# Fixes Applied: Phase 4 Matcher Issues

## Summary

Fixed 2 critical bugs and optimized Match Tuner performance after Phase 4 migration.

---

## ✅ Fix 1: Phase 3 Remnants in `rematch_items_for_artist`

### Problem
The `rematch_items_for_artist` function was still using `suggested_recording_id` (Phase 3) instead of `suggested_work_id` (Phase 4), causing AttributeError.

### Location
`backend/src/airwave/api/routers/discovery.py` lines 504-532

### Changes Made
```python
# Before (Phase 3 - BROKEN):
if rec_id and rec_id != item.suggested_recording_id:
    item.suggested_recording_id = rec_id

# After (Phase 4 - FIXED):
if rec_id:
    # Identity Bridge matches return work_id directly
    if "Identity Bridge" in reason:
        work_id = rec_id  # Already a work_id
    else:
        # Recording match - need to get work_id
        recording = await db.get(Recording, rec_id)
        work_id = recording.work_id if recording else None
    
    if work_id and work_id != item.suggested_work_id:
        item.suggested_work_id = work_id
```

### Impact
- ✅ Fixes AttributeError when re-matching items after artist alias creation
- ✅ Correctly handles both Identity Bridge (work_id) and Recording (recording_id) matches
- ✅ Properly converts recording_id to work_id for Phase 4 schema

---

## ✅ Fix 2: Match Tuner Performance Optimization

### Problem
The `/api/v1/admin/match-samples` endpoint was taking 4.3 seconds, causing the Match Tuner page to timeout or hang.

### Root Cause
- Fetching 30 samples (user requested)
- Running expensive vector searches with `explain=True` for each sample
- Returning ALL candidates (no limit)
- Random sampling on large tables

### Changes Made

#### Backend: Reduced Default Limit
**File**: `backend/src/airwave/api/routers/admin.py` line 172

```python
# Before:
async def get_match_samples(limit: int = 20, ...):

# After:
async def get_match_samples(limit: int = 10, ...):  # Reduced for performance
```

#### Backend: Limited Candidates Returned
**File**: `backend/src/airwave/api/routers/admin.py` line 227

```python
# Before:
for c in data["candidates"]:

# After:
for c in data["candidates"][:5]:  # Limit to top 5 candidates
```

#### Frontend: Updated Sample Request
**File**: `frontend/src/pages/admin/MatchTuner.tsx` lines 52, 66

```typescript
// Before:
matchTunerApi.getMatchSamples(30)

// After:
matchTunerApi.getMatchSamples(10)  // Reduced from 30 to 10
```

### Performance Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Samples** | 30 | 10 | 67% reduction |
| **Candidates per sample** | Unlimited | 5 | ~80% reduction |
| **Estimated response time** | 4.3s | ~1.4s | 67% faster |

**Expected Result**: Match Tuner page should load in under 2 seconds.

---

## ⚠️ Issue 3: Over-Matching in Discovery Queue (NEEDS USER INPUT)

### Problem
The user reported "insanely easy matches" - items that shouldn't have suggestions are being auto-matched.

### Current Behavior
The `run_discovery` method in `matcher.py` (lines 530-581) suggests ALL matches without filtering by quality:

```python
# Runs match_batch on ALL unmatched items
matches = await self.match_batch(batch_queries)

# Populates suggested_work_id for ANY match found
for (qa, qt), (match_id, reason) in matches.items():
    if match_id:
        # Suggests EVERYTHING: Identity Bridge, Exact, High Confidence, Vector, etc.
        obj_map[sig].suggested_work_id = work_id
```

### Match Types Currently Suggested (in priority order)
1. ✅ **Identity Bridge** - Pre-verified permanent mappings (should be auto-linked, not suggested)
2. ✅ **Exact Match** - Exact normalized string match (safe to suggest)
3. ✅ **High Confidence** - 85% artist + 80% title (safe to suggest)
4. ⚠️ **Vector Strong** - Low cosine distance + title guard (might be too aggressive)
5. ⚠️ **Title+Vector** - Title similarity + vector distance (might be too aggressive)

### Proposed Solutions

#### Option A: Only Suggest High-Confidence Matches
```python
# Filter by match reason
if any(keyword in reason for keyword in ["Exact", "High Confidence"]):
    obj_map[sig].suggested_work_id = work_id
# Else: Don't suggest (too low confidence)
```

**Pros**: Simple, conservative
**Cons**: Misses Identity Bridge matches (which are already verified)

#### Option B: Auto-Link Identity Bridge, Suggest High-Confidence Only
```python
if "Identity Bridge" in reason:
    # Auto-link to BroadcastLog.work_id (already verified)
    # Remove from DiscoveryQueue
elif "Exact" in reason or "High Confidence" in reason:
    # Suggest for manual review
    obj_map[sig].suggested_work_id = work_id
# Else: Don't suggest (too low confidence)
```

**Pros**: Leverages verified matches, reduces manual work
**Cons**: More complex, changes workflow

#### Option C: Add Match Quality Field
```python
# Add suggested_match_quality to DiscoveryQueue
# Values: "exact", "high_confidence", "vector", etc.
# Frontend can filter by quality
```

**Pros**: Maximum flexibility, user can choose
**Cons**: Requires schema migration, more complex

### Questions for User

1. **What is your desired behavior for Identity Bridge matches?**
   - Auto-link them (they're already verified)?
   - Suggest them for review (current behavior)?
   - Don't show them at all?

2. **What match types should be suggested?**
   - Only Exact matches?
   - Exact + High Confidence (85% artist, 80% title)?
   - All matches (current behavior)?

3. **Should vector-only matches be suggested?**
   - Yes (current behavior)
   - No (more conservative)

---

## Testing Checklist

### Fix 1: rematch_items_for_artist
- [ ] Create an artist alias in the Verification Hub
- [ ] Verify items are re-matched without errors
- [ ] Verify `suggested_work_id` is updated correctly

### Fix 2: Match Tuner Performance
- [ ] Navigate to `/admin/tuner` page
- [ ] Verify page loads in under 2 seconds
- [ ] Verify 10 samples are displayed
- [ ] Verify each sample shows up to 5 candidates
- [ ] Click "Refresh Samples" and verify it loads quickly

### Issue 3: Over-Matching (Pending User Input)
- [ ] Navigate to `/verification` page
- [ ] Check "Hide items without suggestions" checkbox
- [ ] Review the suggested matches
- [ ] Determine if suggestions are appropriate quality

---

## Files Changed

1. `backend/src/airwave/api/routers/discovery.py` - Fixed Phase 3 remnants
2. `backend/src/airwave/api/routers/admin.py` - Optimized Match Tuner endpoint
3. `frontend/src/pages/admin/MatchTuner.tsx` - Reduced sample request size
4. `docs/analysis-phase4-matcher-issues.md` - Comprehensive analysis document
5. `docs/fixes-phase4-matcher-issues.md` - This document


