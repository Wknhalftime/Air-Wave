# Bug Fix: Verification Hub Filter Not Showing Suggestions

## Issue Summary

**Problem**: The "Hide items without suggestions" filter checkbox was working (filtering items), but the filtered items displayed "No suggestion" in the "Suggested Match" column.

**Root Cause**: Incomplete Phase 3 → Phase 4 migration. The codebase was in a partial migration state where:
- ✅ Backend database used `suggested_work_id` (Phase 4)
- ✅ Backend query filtered by `suggested_work_id` (Phase 4)
- ❌ Backend response model didn't serialize the `suggested_work` relationship data
- ❌ Frontend types expected `suggested_recording_id` (Phase 3)
- ❌ Frontend code accessed `item.suggested_recording` (Phase 3)

## Files Changed

### Backend (3 files)

1. **`backend/src/airwave/api/routers/discovery.py`**
   - Added `SuggestedWorkArtist` and `SuggestedWork` Pydantic models
   - Updated `DiscoveryQueueItem` to include `suggested_work` relationship data
   - Changed `LinkRequest` to accept `work_id` instead of `recording_id`
   - Updated link endpoint to validate `Work` directly instead of `Recording`

2. **`backend/src/airwave/api/routers/search.py`**
   - Added `work_id` field to `SearchResultTrack` model
   - Updated search response to include `work_id` from recordings

### Frontend (3 files)

3. **`frontend/src/types.ts`**
   - Changed `QueueItem` interface from `suggested_recording_id` to `suggested_work_id`
   - Changed nested object from `suggested_recording` to `suggested_work`
   - Simplified structure (removed extra nesting level)

4. **`frontend/src/pages/Verification.tsx`**
   - Updated link mutation to send `work_id` instead of `recording_id`
   - Updated optimistic update to use `suggested_work_id` and `suggested_work`
   - Updated bulk link validation to check `suggested_work_id`
   - Updated bulk link requests to send `work_id`
   - Updated display logic to access `item.suggested_work?.artist?.name` and `item.suggested_work?.title`
   - Updated all conditional checks from `suggested_recording_id` to `suggested_work_id`

5. **`frontend/src/components/verification/SearchDrawer.tsx`**
   - Added `work_id` field to `SearchResult` interface

## Technical Details

### Phase 4 Three-Layer Architecture

The fix completes the migration to the three-layer identity resolution architecture:

| Layer | Concern | Data Model |
|-------|---------|------------|
| **Identity** | What song is this? | `DiscoveryQueue.suggested_work_id` → `Work` |
| **Policy** | Which version to use? | `StationPreference`, `FormatPreference`, `WorkDefaultRecording` |
| **Resolution** | Which file is available? | `RecordingResolver` service (runtime) |

### Before (Phase 3)
```typescript
// Frontend expected:
interface QueueItem {
    suggested_recording_id: number | null;
    suggested_recording?: {
        title: string;
        work?: { artist?: { name: string } }
    }
}
```

### After (Phase 4)
```typescript
// Frontend now uses:
interface QueueItem {
    suggested_work_id: number | null;
    suggested_work?: {
        id: number;
        title: string;
        artist?: { name: string }
    }
}
```

## Testing Checklist

- [ ] Navigate to `/verification` page
- [ ] Verify items are displayed with suggestions in "Suggested Match" column
- [ ] Check "Hide items without suggestions" checkbox
- [ ] Verify only items WITH suggestions are shown
- [ ] Verify "Suggested Match" column shows work title and artist name
- [ ] Click "Link" button on an item with a suggestion
- [ ] Verify item is linked successfully
- [ ] Test bulk link functionality with multiple selected items
- [ ] Test search drawer - select a recording and verify it updates the suggestion
- [ ] Verify the filter state persists in localStorage

## Related Documentation

- [Identity Resolution Architecture](./planning/identity-resolution-architecture.md) - Full Phase 4 specification
- [Verification Hub Redesign Plan](C:\Users\lance\.cursor\plans\verification_hub_redesign_a01d08f0.plan.md) - Problem 3 (Filter)

## Migration Notes

This fix is **backward compatible** because:
- The `has_suggestion` parameter defaults to `None` (shows all items)
- Existing API clients that don't send the parameter will see no change
- The database migration to Phase 4 was already complete (columns exist)

## Next Steps

1. Test the fix in development
2. Verify all acceptance criteria from Problem 3 are met
3. Consider adding integration tests for the filter functionality
4. Monitor for any edge cases in production

