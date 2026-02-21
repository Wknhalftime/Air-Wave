# Part Number Matching Improvement Plan

**Status:** Planning  
**Created:** 2026-02-19  
**Priority:** High  
**Estimated Effort:** 4-6 hours  
**Related Issue:** Work 7474 incorrectly grouping different parts together

---

## Problem Statement

The current part number matching logic in the work grouping system has critical flaws that allow recordings with different parts to be incorrectly grouped under the same work. Specifically, work 7474 is grouping different parts together despite having part number detection logic.

### Current Issue

**Example:** Work 7474 contains recordings like:
- "Symphony No. 5 (Part 1)"
- "Symphony No. 5 (Part 2)"
- "Symphony No. 5 (Part 3)"

These should be separate works, but they're being grouped together.

---

## Current Implementation Analysis

### Location
**File:** `backend/src/airwave/worker/scanner.py`  
**Lines:** 482-491 (inside `_find_similar_work()` method)

### Current Code

```python
# NEGATIVE PATTERN: Skip if titles differ by part numbers
# This prevents "Symphony (Part 1)" from matching "Symphony (Part 2)"
import re
title_part = re.search(r'\b(part|pt\.?)\s*(\d+)\b', title_lower)
work_part = re.search(r'\b(part|pt\.?)\s*(\d+)\b', work_title_lower)

if title_part and work_part:
    # Both have part numbers - only match if same part number
    if title_part.group(2) != work_part.group(2):
        continue  # Different part numbers, skip this work
```

### Critical Limitations

1. **Only checks during fuzzy matching** - Part number check happens AFTER exact match fails. If exact match succeeds, parts aren't checked.

2. **Asymmetric case failure** - Only prevents matching if BOTH titles have part numbers:
   - "Symphony Part 1" vs "Symphony Part 2" → Correctly prevented ✅
   - "Symphony Part 1" vs "Symphony" → Still matches ❌ (one has part, other doesn't)

3. **Limited regex pattern** - Only matches:
   - "part" or "pt." followed by number
   - Missing: "Movement", "Mvt.", "Mov.", "No.", "Number", Roman numerals (I, II, III, etc.)

4. **Normalization can remove parts** - If part numbers are normalized away during text cleaning, they won't be detected.

5. **No check before exact match** - Exact matching (line 548) doesn't verify parts, so "Symphony Part 1" can match "Symphony Part 2" if normalization makes them identical.

---

## Root Cause Analysis

### Why Work 7474 Fails

1. **Exact match bypass** - If normalization removes part information, exact match succeeds without part checking
2. **Fuzzy match only** - Part check only happens in fuzzy matching loop, not before exact match
3. **Incomplete detection** - Limited regex misses alternative formats (Movement, Mvt., No., etc.)
4. **Asymmetric handling** - Doesn't handle case where one title has part and other doesn't

### Flow Diagram - Current (Broken) Flow

```
process_file()
  └─> _create_new_library_file()
      └─> _upsert_work(title, artist_id)
          ├─> Exact Match Check (line 548)
          │   └─> If found: Return work ❌ (NO PART CHECK!)
          │
          └─> Fuzzy Match Check (line 561)
              └─> _find_similar_work()
                  └─> For each work:
                      └─> Part Check (line 485-491) ✅ (Only here!)
                          └─> If parts differ: Skip
                          └─> Else: Calculate similarity
```

**Problem:** Part check happens too late - after exact match already succeeded.

---

## Proposed Solution

### Strategy Overview

1. **Comprehensive part number extraction** - Support multiple formats
2. **Early part checking** - Check parts BEFORE both exact and fuzzy matching
3. **Asymmetric handling** - Different works if one has part and other doesn't
4. **Preserve fuzzy matching** - Don't compromise fuzzy matching for non-part works

### Enhanced Part Number Detection

Create a comprehensive helper method that detects:
- **Part formats:** "Part 1", "Pt. 2", "Part 3"
- **Movement formats:** "Movement 1", "Mvt. 2", "Mov. 3"
- **Number formats:** "No. 1", "Number 2"
- **Roman numerals:** "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"

### Implementation Plan

#### Step 1: Add Comprehensive Part Extraction Method

**Location:** `backend/src/airwave/worker/scanner.py` (around line 410, before `_find_similar_work`)

```python
@staticmethod
def _extract_part_number(title: str) -> Optional[Tuple[str, int]]:
    """Extract part/movement number from title if present.
    
    Supports multiple formats:
    - "Part 1", "Pt. 2", "Part 3"
    - "Movement 1", "Mvt. 2", "Mov. 3"
    - "No. 1", "Number 2"
    - "I", "II", "III" (Roman numerals 1-10)
    
    Args:
        title: Work title to check
        
    Returns:
        Tuple of (part_type, part_number) if found, None otherwise
        part_type: "part", "movement", "number", or "roman"
        part_number: Integer (1-10 for roman numerals)
    """
    import re
    
    title_lower = title.lower()
    
    # Pattern 1: Part/Pt. followed by number
    match = re.search(r'\b(part|pt\.?)\s*(\d+)\b', title_lower)
    if match:
        return ("part", int(match.group(2)))
    
    # Pattern 2: Movement/Mvt./Mov. followed by number
    match = re.search(r'\b(movement|mvt\.?|mov\.?)\s*(\d+)\b', title_lower)
    if match:
        return ("movement", int(match.group(2)))
    
    # Pattern 3: No./Number followed by number
    match = re.search(r'\b(no\.?|number)\s*(\d+)\b', title_lower)
    if match:
        return ("number", int(match.group(2)))
    
    # Pattern 4: Roman numerals (I-X, case-insensitive)
    roman_map = {
        'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
        'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10
    }
    # Look for standalone roman numerals (word boundaries)
    match = re.search(r'\b([ivx]+)\b', title_lower)
    if match:
        roman = match.group(1).lower()
        if roman in roman_map:
            return ("roman", roman_map[roman])
    
    return None


def _parts_differ(self, title1: str, title2: str) -> bool:
    """Check if two titles have different part numbers.
    
    Returns True if titles have different parts (should be separate works),
    False if they have same parts or no parts (can be same work).
    
    Args:
        title1: First work title
        title2: Second work title
        
    Returns:
        True if parts differ, False otherwise
    """
    part1 = self._extract_part_number(title1)
    part2 = self._extract_part_number(title2)
    
    # If neither has a part number, they can match
    if part1 is None and part2 is None:
        return False
    
    # If one has a part and the other doesn't, they're different works
    if (part1 is None) != (part2 is None):
        return True
    
    # Both have parts - compare them
    # Same part type and number = same work
    if part1[0] == part2[0] and part1[1] == part2[1]:
        return False
    
    # Different part types or numbers = different works
    return True
```

#### Step 2: Update `_upsert_work()` Method

**Location:** `backend/src/airwave/worker/scanner.py` (line 529)

**Changes:**
1. Check parts BEFORE exact match
2. Verify parts even if exact match found
3. Verify parts even if fuzzy match found

```python
async def _upsert_work(self, title: str, artist_id: int) -> Work:
    """Atomically insert or get existing work using database UPSERT.
    
    Enhanced with part number checking to prevent grouping different parts.
    """
    from airwave.core.config import settings

    # FAST PATH: Try exact match first
    stmt = select(Work).where(Work.title == title, Work.artist_id == artist_id)
    result = await self.session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # ENHANCED: Even if exact match, verify parts don't differ
        if self._parts_differ(title, existing.title):
            # Parts differ - create new work even though exact match found
            # This handles edge cases where normalization removed part info
            if settings.DEBUG_WORK_GROUPING:
                logger.info(
                    f"[WORK] Exact match found but parts differ: "
                    f"existing='{existing.title}' vs new='{title}' - creating separate work"
                )
            # Fall through to create new work
        else:
            if settings.DEBUG_WORK_GROUPING:
                logger.debug(
                    f"[WORK] Exact match found: work_id={existing.id}, "
                    f"title='{title}', artist_id={artist_id}"
                )
            return existing

    # FUZZY MATCHING: Try to find similar work
    similar_work = await self._find_similar_work(title, artist_id)
    if similar_work:
        # ENHANCED: Verify parts don't differ even for fuzzy matches
        if self._parts_differ(title, similar_work.title):
            if settings.DEBUG_WORK_GROUPING:
                logger.info(
                    f"[WORK] Fuzzy match found but parts differ: "
                    f"existing='{similar_work.title}' vs new='{title}' - creating separate work"
                )
            # Fall through to create new work
        else:
            if settings.DEBUG_WORK_GROUPING:
                logger.info(
                    f"[WORK] Fuzzy match used: work_id={similar_work.id}, "
                    f"existing_title='{similar_work.title}', new_title='{title}', "
                    f"artist_id={artist_id}"
                )
            return similar_work

    # Insert new work (rest of method unchanged...)
    # ... existing code continues ...
```

#### Step 3: Update `_find_similar_work()` Method

**Location:** `backend/src/airwave/worker/scanner.py` (line 412)

**Changes:**
1. Replace old regex-based part check with new `_parts_differ()` method
2. More comprehensive part detection

```python
for work_id, work_title in work_tuples:
    work_title_lower = work_title.lower()

    # ENHANCED: Use comprehensive part number checking
    if self._parts_differ(title, work_title):
        if settings.DEBUG_WORK_GROUPING:
            logger.debug(
                f"[FUZZY] Skipping work_id={work_id} due to different parts: "
                f"'{title}' vs '{work_title}'"
            )
        continue  # Different parts, skip this work

    # Case-insensitive comparison
    ratio = difflib.SequenceMatcher(None, title_lower, work_title_lower).ratio()
    
    # ... rest of existing code ...
```

---

## Enhanced Flow Diagram

```
process_file()
  └─> _create_new_library_file()
      └─> _upsert_work(title, artist_id)
          ├─> Extract Part Number (NEW)
          │
          ├─> Exact Match Check (line 548)
          │   └─> If found:
          │       └─> Check Parts Differ (NEW) ✅
          │           ├─> If differ: Create new work
          │           └─> If same: Return existing work
          │
          └─> Fuzzy Match Check (line 561)
              └─> _find_similar_work()
                  └─> For each work:
                      └─> Check Parts Differ (ENHANCED) ✅
                          └─> If differ: Skip
                          └─> Else: Calculate similarity
                              └─> If match found:
                                  └─> Check Parts Differ Again (NEW) ✅
                                      └─> If differ: Create new work
                                      └─> If same: Return matched work
```

**Key Changes:**
- ✅ Part check BEFORE exact match
- ✅ Part check during fuzzy matching (enhanced)
- ✅ Part check AFTER fuzzy match found
- ✅ Comprehensive part detection

---

## Benefits

### 1. Better Separation of Multi-Part Works
- Ensures "Symphony Part 1" and "Symphony Part 2" are always separate works
- Handles various part number formats consistently

### 2. More Robust Detection
- Supports Part, Movement, Number, and Roman numeral formats
- Handles edge cases where normalization might remove part info

### 3. Asymmetric Case Handling
- "Symphony Part 1" vs "Symphony" → Different works (correct)
- Previously would match incorrectly

### 4. Doesn't Compromise Fuzzy Matching
- Non-part works still benefit from fuzzy matching
- Part detection is additive, not restrictive

### 5. Early Detection
- Catches part differences before expensive fuzzy matching
- More efficient for multi-part works

---

## Testing Considerations

### Test Cases to Verify

1. **Basic Part Detection**
   - "Symphony Part 1" vs "Symphony Part 2" → Separate works ✅
   - "Symphony Part 1" vs "Symphony Part 1" → Same work ✅

2. **Format Variations**
   - "Symphony Pt. 1" vs "Symphony Part 2" → Separate works ✅
   - "Symphony Movement 1" vs "Symphony Mvt. 2" → Separate works ✅
   - "Symphony No. 1" vs "Symphony Number 2" → Separate works ✅
   - "Symphony I" vs "Symphony II" → Separate works ✅

3. **Asymmetric Cases**
   - "Symphony Part 1" vs "Symphony" → Separate works ✅
   - "Symphony" vs "Symphony Part 1" → Separate works ✅

4. **Edge Cases**
   - "Symphony Part 1 (Live)" vs "Symphony Part 2 (Live)" → Separate works ✅
   - "Symphony Part 1" vs "Symphony Part 10" → Separate works ✅
   - "Symphony Part I" vs "Symphony Part 1" → Separate works (different formats) ✅

5. **Non-Part Works**
   - "Song Title" vs "Song Title " → Same work (fuzzy match still works) ✅
   - "Song Title" vs "Song Title (Live)" → Same work (version extraction works) ✅

### Performance Impact

- **Minimal overhead** - Part extraction is O(1) regex operations
- **Early termination** - Part checks happen before expensive fuzzy matching
- **No database changes** - Pure logic improvement

---

## Migration & Deployment

### Database Changes
- **None required** - This is a logic-only change

### Backward Compatibility
- **Fully compatible** - Existing works remain unchanged
- **New scans** - Will correctly separate parts going forward
- **Existing incorrect groupings** - May need manual review/correction for work 7474

### Rollout Strategy

1. **Phase 1:** Deploy code changes
2. **Phase 2:** Re-scan affected artists (or full library)
3. **Phase 3:** Verify work 7474 is correctly separated
4. **Phase 4:** Monitor for other multi-part works

### Manual Cleanup (Optional)

For work 7474 specifically:
```sql
-- Identify recordings with different parts
SELECT r.id, r.title, w.title as work_title
FROM recordings r
JOIN works w ON r.work_id = w.id
WHERE w.id = 7474
ORDER BY r.title;

-- Manual review and potential work splitting may be needed
```

---

## Configuration

No new configuration options needed. The improvement uses existing settings:
- `WORK_FUZZY_MATCH_THRESHOLD` (0.85) - Still applies to non-part works
- `WORK_FUZZY_MATCH_MAX_WORKS` (500) - Still applies for performance safeguard
- `DEBUG_WORK_GROUPING` - Enhanced logging for part detection

---

## Success Criteria

1. ✅ Work 7474 correctly separates different parts
2. ✅ "Symphony Part 1" and "Symphony Part 2" are separate works
3. ✅ Fuzzy matching still works for non-part works
4. ✅ No performance degradation
5. ✅ Supports Part, Movement, Number, and Roman numeral formats

---

## Related Documentation

- [Work-Recording Grouping Improvement Plan](./work-recording-grouping-improvement.md)
- [Work-Recording Grouping Test Coverage](./work-recording-grouping-test-coverage.md)
- Control Flow Graph: See conversation history for detailed flowchart

---

## Implementation Checklist

- [ ] Add `_extract_part_number()` static method
- [ ] Add `_parts_differ()` instance method
- [ ] Update `_upsert_work()` to check parts before exact match
- [ ] Update `_upsert_work()` to verify parts after exact match found
- [ ] Update `_upsert_work()` to verify parts after fuzzy match found
- [ ] Update `_find_similar_work()` to use `_parts_differ()` method
- [ ] Add unit tests for part number extraction
- [ ] Add unit tests for `_parts_differ()` method
- [ ] Add integration tests for multi-part works
- [ ] Test with work 7474 specifically
- [ ] Update documentation
- [ ] Deploy and verify

---

**Next Steps:** Review this plan and proceed with implementation.
