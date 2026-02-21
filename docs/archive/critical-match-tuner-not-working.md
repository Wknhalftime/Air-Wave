# CRITICAL BUG: Match Tuner Thresholds Are Not Being Used

## Executive Summary

**The Match Tuner UI has NO EFFECT on matching behavior.** The matcher uses different threshold settings than what the Match Tuner updates, causing the entire Match Tuner feature to be non-functional.

---

## Root Cause

### The Match Tuner Updates These Settings:
```python
# From admin.py lines 287-290
await update_setting("MATCH_VARIANT_ARTIST_SCORE", settings_in.artist_auto)
await update_setting("MATCH_ALIAS_ARTIST_SCORE", settings_in.artist_review)
await update_setting("MATCH_VARIANT_TITLE_SCORE", settings_in.title_auto)
await update_setting("MATCH_ALIAS_TITLE_SCORE", settings_in.title_review)
```

### But The Matcher Uses DIFFERENT Settings:
```python
# From matcher.py lines 354-397
elif (
    artist_sim > settings.MATCH_CONFIDENCE_HIGH_ARTIST  # ❌ Different setting!
    and title_sim > settings.MATCH_CONFIDENCE_HIGH_TITLE  # ❌ Different setting!
):
    candidate_info["match_type"] = "High Confidence"
    
elif (
    dist < settings.MATCH_VECTOR_STRONG_DIST  # ❌ Not controlled by Match Tuner
    and title_sim >= settings.MATCH_VECTOR_TITLE_GUARD  # ❌ Not controlled by Match Tuner
):
    candidate_info["match_type"] = "Vector Strong"
```

### Settings Comparison Table

| Match Tuner UI | Updates Setting | Matcher Uses | Default Value |
|----------------|-----------------|--------------|---------------|
| `artist_auto` | `MATCH_VARIANT_ARTIST_SCORE` | `MATCH_CONFIDENCE_HIGH_ARTIST` ❌ | 0.85 |
| `artist_review` | `MATCH_ALIAS_ARTIST_SCORE` | **Not used at all** ❌ | 0.70 |
| `title_auto` | `MATCH_VARIANT_TITLE_SCORE` | `MATCH_CONFIDENCE_HIGH_TITLE` ❌ | 0.80 |
| `title_review` | `MATCH_ALIAS_TITLE_SCORE` | **Not used at all** ❌ | 0.70 |

**Result**: Adjusting the Match Tuner sliders has ZERO effect on matching behavior.

---

## Additional Issues

### Issue 1: No Auto-Accept Logic

The user expects three ranges:
1. **Auto-Accept Range** - High confidence → Auto-link, bypass Discovery Queue
2. **Review Range** - Medium confidence → Appear in Discovery Queue
3. **Reject Range** - Low confidence → Don't appear in Discovery Queue

**Current Behavior**: ALL matches appear in Discovery Queue, regardless of confidence.

### Issue 2: No Filtering by Match Quality

`run_discovery` (lines 530-581) suggests ALL matches:
```python
# Populates suggested_work_id for ANY match found
for (qa, qt), (match_id, reason) in matches.items():
    if match_id:
        # Suggests EVERYTHING: Identity Bridge, Exact, High Confidence, Vector, etc.
        obj_map[sig].suggested_work_id = work_id
```

No filtering by:
- Match type (Exact vs Vector)
- Confidence level (High vs Low)
- Threshold ranges (Auto vs Review vs Reject)

### Issue 3: Identity Bridge Matches Should Auto-Link

Identity Bridge matches are pre-verified permanent mappings. They should be auto-linked to `BroadcastLog.work_id`, not just suggested in the Discovery Queue.

---

## Impact

1. **Match Tuner is completely non-functional** - Users can adjust sliders but nothing changes
2. **Discovery Queue is polluted** - Low-confidence matches appear that shouldn't
3. **Manual work is excessive** - High-confidence matches require manual review instead of auto-linking
4. **User confusion** - "Insanely easy matches" appear because vector matches are too aggressive

---

## Proposed Solution

### Step 1: Fix Threshold Settings (Use Match Tuner Values)

**Change matcher.py to use the correct settings:**

```python
# BEFORE (lines 354-357):
elif (
    artist_sim > settings.MATCH_CONFIDENCE_HIGH_ARTIST  # ❌ Wrong setting
    and title_sim > settings.MATCH_CONFIDENCE_HIGH_TITLE  # ❌ Wrong setting
):

# AFTER:
elif (
    artist_sim > settings.MATCH_VARIANT_ARTIST_SCORE  # ✅ Match Tuner "auto" threshold
    and title_sim > settings.MATCH_VARIANT_TITLE_SCORE  # ✅ Match Tuner "auto" threshold
):
```

### Step 2: Implement Three-Range Filtering

**Add filtering logic to `run_discovery`:**

```python
for (qa, qt), (match_id, reason) in matches.items():
    if not match_id:
        continue
    
    sig = Normalizer.generate_signature(qa, qt)
    
    # Calculate match confidence (for non-exact matches)
    if "Identity Bridge" in reason:
        # Auto-link Identity Bridge matches (already verified)
        # TODO: Link directly to BroadcastLog.work_id
        # Don't add to Discovery Queue
        continue
    
    elif "Exact" in reason:
        # Exact matches always go to Discovery Queue for review
        obj_map[sig].suggested_work_id = work_id
    
    elif "High Confidence" in reason:
        # Check if above auto-accept threshold
        # Extract similarity scores from reason string or re-calculate
        # If above artist_auto AND title_auto: auto-link
        # If above artist_review AND title_review: suggest
        # Else: reject (don't add to queue)
        obj_map[sig].suggested_work_id = work_id
    
    else:
        # Vector matches - check if above review threshold
        # If below review threshold: reject (don't add to queue)
        pass
```

### Step 3: Deprecate Old Settings

**Remove or deprecate unused settings in config.py:**

```python
# Deprecated - Use MATCH_VARIANT_* instead (controlled by Match Tuner)
# MATCH_CONFIDENCE_HIGH_ARTIST: float = 0.85
# MATCH_CONFIDENCE_HIGH_TITLE: float = 0.8
```

---

## Implementation Plan

### Phase 1: Fix Threshold Settings (Critical)
1. ✅ Update matcher.py to use `MATCH_VARIANT_*` instead of `MATCH_CONFIDENCE_HIGH_*`
2. ✅ Update matcher.py to use `MATCH_ALIAS_*` for review threshold
3. ✅ Test that Match Tuner sliders now affect matching behavior

### Phase 2: Implement Auto-Accept Logic (High Priority)
1. ✅ Add logic to auto-link matches above auto-accept threshold
2. ✅ Add logic to reject matches below review threshold
3. ✅ Update `run_discovery` to filter by confidence ranges

### Phase 3: Identity Bridge Auto-Linking (Medium Priority)
1. ✅ Auto-link Identity Bridge matches to BroadcastLog.work_id
2. ✅ Remove Identity Bridge matches from Discovery Queue

---

## Testing Checklist

### Test 1: Match Tuner Affects Matching
- [ ] Set `artist_auto` to 0.95 (very strict)
- [ ] Run discovery
- [ ] Verify fewer "High Confidence" matches appear
- [ ] Set `artist_auto` to 0.70 (very loose)
- [ ] Run discovery
- [ ] Verify more "High Confidence" matches appear

### Test 2: Auto-Accept Range
- [ ] Set `artist_auto` to 0.90, `artist_review` to 0.70
- [ ] Create a match with 0.95 artist similarity (above auto threshold)
- [ ] Verify it's auto-linked, NOT in Discovery Queue

### Test 3: Review Range
- [ ] Create a match with 0.80 artist similarity (between review and auto)
- [ ] Verify it appears in Discovery Queue with suggestion

### Test 4: Reject Range
- [ ] Create a match with 0.60 artist similarity (below review threshold)
- [ ] Verify it does NOT appear in Discovery Queue

---

## Files to Change

1. `backend/src/airwave/worker/matcher.py` - Use correct threshold settings
2. `backend/src/airwave/worker/matcher.py` - Add three-range filtering logic
3. `backend/src/airwave/core/config.py` - Deprecate old settings
4. `docs/critical-match-tuner-not-working.md` - This document


