# Artist Linking Decoupling Fix

**Date:** 2026-02-20  
**Status:** Implemented

---

## Problem Statement

The Artist Linking feature was incorrectly coupled with song matching, showing ONLY artists from unmatched songs in the DiscoveryQueue. This violated the principle of separation of concerns and prevented proactive artist alias creation.

### Incorrect Behavior (Before)
- ❌ Artist Linking tab only showed artists from **DiscoveryQueue** (unmatched songs)
- ❌ Couldn't create artist aliases for matched songs
- ❌ Artist linking was reactive (only after songs failed to match)
- ❌ Coupling between artist identity and song matching

### Expected Behavior (After)
- ✅ Artist Linking tab shows artists from **ALL BroadcastLog** entries
- ✅ Can create artist aliases proactively, regardless of match status
- ✅ Artist linking is independent of song matching
- ✅ Proper separation of concerns

---

## Root Cause

The `/artist-queue` endpoint was querying `DiscoveryQueue` instead of `BroadcastLog`:

**Before (Incorrect):**
```python
stmt = (
    select(
        DiscoveryQueue.raw_artist,  # ❌ Only unmatched songs
        func.count(DiscoveryQueue.signature).label("item_count"),
    )
    .where(DiscoveryQueue.raw_artist.notin_(subq_verified))
    .group_by(DiscoveryQueue.raw_artist)
    ...
)
```

**After (Correct):**
```python
stmt = (
    select(
        BroadcastLog.raw_artist,  # ✅ All broadcast logs
        func.count(BroadcastLog.id).label("item_count")
    )
    .where(BroadcastLog.raw_artist.notin_(subq_verified))
    .group_by(BroadcastLog.raw_artist)
    ...
)
```

---

## Solution

### 1. Changed Data Source

**File:** `backend/src/airwave/api/routers/discovery.py`

Changed the `/artist-queue` endpoint to query `BroadcastLog` instead of `DiscoveryQueue`.

### 2. Added Filter Options

Added optional `filter_type` parameter to allow filtering by match status:

```python
@router.get("/artist-queue", response_model=List[ArtistQueueItem])
async def get_artist_queue(
    limit: int = 100,
    offset: int = 0,
    filter_type: str = "all",  # NEW: "all", "matched", "unmatched"
    db: AsyncSession = Depends(get_db)
):
```

**Filter Options:**
- `"all"` (default): Show all artists from all broadcast logs
- `"matched"`: Show only artists from matched songs (work_id IS NOT NULL)
- `"unmatched"`: Show only artists from unmatched songs (work_id IS NULL)

### 3. Updated Documentation

Updated the endpoint docstring to clarify the decoupling:

```python
"""Get list of raw artist names that need linking to library artists.

DECOUPLED FROM SONG MATCHING: Returns artists from ALL broadcast logs,
not just unmatched songs. This allows proactive artist alias creation.
```

---

## Impact

### Before Fix
- **Artist Linking (100)**: Only showed artists from 100 unmatched songs
- **Example**: "BEATLES" only appeared if Beatles songs were unmatched

### After Fix
- **Artist Linking (100)**: Shows top 100 artists by play count from ALL logs
- **Example**: "BEATLES" appears regardless of whether Beatles songs matched

---

## Benefits

1. **Proactive Alias Creation**: Users can create artist aliases before songs fail to match
2. **Better Data Quality**: Can normalize artist names across the entire dataset
3. **Separation of Concerns**: Artist identity is independent of song matching
4. **Flexibility**: Can filter by match status if needed

---

## Use Cases

### Use Case 1: Proactive Normalization
**Scenario:** User notices "BEATLES" in logs (all uppercase)  
**Action:** Create alias "BEATLES" → "The Beatles"  
**Result:** Future songs by "BEATLES" will match better

### Use Case 2: Fixing Matched Songs
**Scenario:** Songs matched correctly, but artist name is inconsistent  
**Action:** Create alias to normalize the artist name  
**Result:** Improved data consistency across matched songs

### Use Case 3: Bulk Cleanup
**Scenario:** User wants to normalize all artist names  
**Action:** Use `filter_type="all"` to see all artists  
**Result:** Can systematically create aliases for all variations

---

## Testing

### Test 1: Verify All Artists Shown
1. Navigate to Verification Hub → Artist Linking
2. Verify artists from BOTH matched and unmatched songs appear
3. Verify count reflects total broadcast logs, not just DiscoveryQueue

### Test 2: Verify Filtering Works
1. Add `?filter_type=matched` to URL
2. Verify only artists from matched songs appear
3. Add `?filter_type=unmatched` to URL
4. Verify only artists from unmatched songs appear

### Test 3: Verify Alias Creation Works
1. Create an alias for an artist from a matched song
2. Verify the alias is created successfully
3. Verify the artist no longer appears in the queue

---

## Files Changed

- `backend/src/airwave/api/routers/discovery.py`
  - Changed `/artist-queue` endpoint to query `BroadcastLog`
  - Added `filter_type` parameter
  - Updated documentation

---

## Future Enhancements

### Optional: Frontend Filter UI
Add a filter dropdown in the Verification Hub to allow users to switch between:
- All Artists
- Matched Only
- Unmatched Only

### Optional: Batch Alias Creation
Allow users to create multiple aliases at once for common patterns (e.g., all uppercase → title case).

---

## Summary

✅ **Artist Linking is now decoupled from song matching**  
✅ **Shows all artists from all broadcast logs**  
✅ **Supports proactive alias creation**  
✅ **Maintains backward compatibility with filtering**

This fix aligns the implementation with the correct architectural principle: **Artist identity resolution should be independent of song matching**.

