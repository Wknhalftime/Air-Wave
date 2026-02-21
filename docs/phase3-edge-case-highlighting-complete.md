# Phase 3: Edge Case Highlighting - COMPLETE ✅

**Date:** 2026-02-20  
**Status:** Implemented and Ready for Testing

---

## Overview

Phase 3 adds **edge case detection and highlighting** to help administrators identify matches that are near threshold boundaries. These are critical matches where small threshold adjustments could change the outcome (auto-link vs review vs reject).

---

## What Was Implemented

### 1. Backend: Edge Case Detection Logic

**File:** `backend/src/airwave/api/routers/admin.py`

**New Function:** `detect_edge_case()`
- Detects if a match is within 5% of any threshold boundary
- Returns edge case type:
  - `"near_auto_threshold"`: Either artist or title similarity is within 5% of auto threshold
  - `"near_review_threshold"`: Either artist or title similarity is within 5% of review threshold
  - `None`: Not an edge case

**Example:**
```python
# With thresholds: artist_auto=85%, title_auto=80%
# Match: artist_sim=83%, title_sim=95%
# Result: "near_auto_threshold" (artist is 83%, within 5% of 85%)
```

### 2. Backend: MatchCandidate Model Update

**Added Field:**
```python
class MatchCandidate(BaseModel):
    # ... existing fields ...
    edge_case: Optional[str] = None  # Edge case type if near threshold
```

### 3. Backend: Populate Edge Cases in Match Samples

**Updated:** Match samples endpoint now calls `detect_edge_case()` for each candidate and populates the `edge_case` field.

---

### 4. Frontend: Edge Case Badge Component

**File:** `frontend/src/components/admin/ExampleMatches.tsx`

**New Helper Functions:**
- `getEdgeCaseLabel()`: Returns human-readable label
- `getEdgeCaseDescription()`: Returns explanation text

**Visual Design:**
- Amber/yellow color scheme (distinct from quality warnings which are orange)
- AlertTriangle icon
- Prominent callout box with explanation

### 5. Frontend: Edge Case Display in Example Cards

**Visual Treatment:**
Each match card now shows an edge case warning if applicable:

```
┌─────────────────────────────────────────────────┐
│ Raw: "Pink Floyde" - "Wish You Were Hear"      │
│ Match: "Pink Floyd" - "Wish You Were Here"     │
│                                                 │
│ Artist: 86.0%  Title: 81.0%  (High Confidence) │
│                                                 │
│ ⚠️ Near Auto Threshold                         │
│ Within 5% of auto-link threshold - small       │
│ changes could affect this match                │
└─────────────────────────────────────────────────┘
```

### 6. Frontend: Edge Case Counter in Header

**Added:**
- Badge showing count of edge cases (e.g., "⚠️ 5 Edge Cases")
- Helper text explaining what edge cases mean
- Only shown when edge cases are present

---

## User Benefits

### Before Phase 3:
❌ No visibility into borderline matches  
❌ Risk of accidentally excluding good matches  
❌ Trial-and-error threshold adjustment  

### After Phase 3:
✅ **Immediate visibility** of matches near threshold boundaries  
✅ **Informed decisions** - see exactly which matches are affected by small changes  
✅ **Confidence** - understand the impact before saving thresholds  

---

## Example Scenarios

### Scenario 1: Near Auto Threshold
**Thresholds:** artist_auto=85%, title_auto=80%  
**Match:** "Beatles" → "The Beatles" (artist=87%, title=95%)  
**Edge Case:** `near_auto_threshold` (artist is 87%, within 5% of 85%)  
**User Insight:** "If I lower artist_auto to 86%, this match will still auto-link. But if I lower it to 82%, it will go to review."

### Scenario 2: Near Review Threshold
**Thresholds:** artist_review=70%, title_review=70%  
**Match:** "Various" → "Various Artists" (artist=68%, title=55%)  
**Edge Case:** `near_review_threshold` (artist is 68%, within 5% of 70%)  
**User Insight:** "This match is currently rejected. If I lower artist_review to 67%, it will go to review queue."

---

## Technical Details

### Edge Case Detection Algorithm

```python
def detect_edge_case(artist_sim, title_sim, thresholds, edge_threshold=0.05):
    # Check if within 5% of auto threshold
    if abs(artist_sim - thresholds["artist_auto"]) <= 0.05:
        return "near_auto_threshold"
    if abs(title_sim - thresholds["title_auto"]) <= 0.05:
        return "near_auto_threshold"
    
    # Check if within 5% of review threshold
    if abs(artist_sim - thresholds["artist_review"]) <= 0.05:
        return "near_review_threshold"
    if abs(title_sim - thresholds["title_review"]) <= 0.05:
        return "near_review_threshold"
    
    return None
```

### Performance Impact

- **Minimal** - Edge case detection is a simple comparison (O(1))
- No additional database queries
- Runs during existing match sample processing

---

## Testing Checklist

- [ ] Navigate to Match Tuner (`/admin/tuner`)
- [ ] Click "Refresh" on Example Matches
- [ ] Verify edge case badge appears in header if edge cases exist
- [ ] Verify edge case warning boxes appear on relevant match cards
- [ ] Adjust thresholds and verify edge cases update correctly
- [ ] Verify edge case warnings use amber/yellow color scheme
- [ ] Verify helper text explains what edge cases mean

---

## Next Steps (Optional Enhancements)

### Not Implemented (from original plan):
- **Sensitivity zone visualization on sliders** - Show visual indicators on sliders where edge cases exist
- **Sort/filter to show edge cases first** - Currently edge cases are shown in their category, but not prioritized
- **Click to adjust threshold to edge case** - Quick action to set threshold to exact edge case value

These could be added in a future enhancement if users request them.

---

## Files Changed

### Backend
- `backend/src/airwave/api/routers/admin.py`
  - Added `detect_edge_case()` function
  - Updated `MatchCandidate` model with `edge_case` field
  - Updated match samples endpoint to populate edge cases

### Frontend
- `frontend/src/components/admin/ExampleMatches.tsx`
  - Updated `MatchCandidate` interface with `edge_case?: string`
  - Added `getEdgeCaseLabel()` and `getEdgeCaseDescription()` helpers
  - Added edge case warning display in match cards
  - Added edge case counter in header

---

**Phase 3 is complete and ready for user testing!** 🎉

