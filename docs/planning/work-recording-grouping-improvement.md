# Work-Recording Grouping Algorithm Improvement Plan

**Status:** Planning (Reviewed & Updated)
**Created:** 2026-02-18
**Last Updated:** 2026-02-18 (Post-Review)
**Priority:** Medium
**Estimated Effort:** 11 hours (revised from 10 hours)
**Reviewed By:** Data Scientist Agent, SQL Agent, Implementation Agent

> **Update:** This plan has been reviewed and updated based on feedback from Data Scientist and SQL Agent evaluations.
> See `work-recording-grouping-evaluation-summary.md` for detailed evaluation.

---

## Problem Statement

The library navigation system currently has issues with how recordings are grouped under their parent works. The core problem is that version information is embedded in recording titles (e.g., "Song Title (Live)", "Song Title - Radio Edit"), and the current extraction logic has edge cases that cause incorrect grouping.

### Current Issues

1. **Non-version parentheses create separate works**
   - "Song Title (Live)" → work_title = "song title" ✅
   - "Song Title (The Ballad)" → work_title = "song title the ballad" ❌ (different work!)

2. **Only first version tag extracted**
   - "Song (Live) (Radio Edit)" → Extracts "Live", leaves "(Radio Edit)" in title

3. **Dash-separated versions not extracted**
   - "Song Title - Live Version" → No extraction, entire string becomes work title

4. **Inconsistent version type extraction**
   - "Song (Extended Mix)" → version_type = "Extended"
   - "Song (Extended Version)" → version_type = "Version" (inconsistent!)

### Impact

- Duplicate works for the same song
- Fragmented recording lists in the UI
- Inaccurate work counts per artist
- Difficulty filtering by version type

---

## Current Implementation

### Database Schema (No Changes Needed)

```
Work:
  - id (PK)
  - title (indexed)
  - artist_id (FK)
  - is_instrumental

Recording:
  - id (PK)
  - work_id (FK)
  - title
  - version_type  ← Already exists!
  - duration
  - isrc
  - is_verified
```

### Current Grouping Logic

**File:** `backend/src/airwave/worker/scanner.py`

```python
# Lines 169-175: Version extraction
clean_title, version_type = Normalizer.extract_version_type(raw_title)
self.title = Normalizer.clean(clean_title)
self.version_type = version_type
self.work_title = self.title

# Lines 426-428: Work matching (EXACT match only)
stmt = select(Work).where(
    Work.title == title,
    Work.artist_id == artist_id
)
```

**Problem:** Exact matching means any variation in cleaned title creates a new work.

---

## Proposed Solution: Hybrid Approach

Combine **improved version extraction** with **fuzzy matching** as a safety net.

### Strategy Overview

1. **Enhanced Version Extraction** - Handle more edge cases with negative patterns
2. **Fuzzy Work Matching** - Group similar titles (85%+ similarity, configurable)
3. **Album Context Heuristics** - Use album info to detect live versions (conservative)
4. **Full Version String Storage** - Store "Live / Radio Edit" instead of just "Live"
5. **Performance Safeguards** - Work count limits and early termination

### Benefits

- ✅ Handles ambiguous parentheses gracefully
- ✅ Groups similar titles even when extraction fails
- ✅ Preserves version information
- ✅ Backward compatible (no schema changes, index already exists)
- ✅ Gradual improvement (no full re-scan needed)
- ✅ Configurable thresholds for production tuning
- ✅ Performance safeguards for large artist catalogs

### Key Configuration Parameters

```python
# In backend/src/airwave/config.py
WORK_FUZZY_MATCH_THRESHOLD: float = 0.85  # Aligned with existing artist matching
WORK_FUZZY_MATCH_MAX_WORKS: int = 500     # Skip fuzzy matching for large catalogs
```

---

## Implementation Phases

### Phase 1: Enhanced Version Extraction (~4.5 hours)

**Goal:** Improve `Normalizer.extract_version_type()` to handle more cases with negative patterns.

**Changes:**

1. **New method:** `extract_version_type_enhanced(title, album_title=None)`
   - Extract ALL version tags (not just first)
   - Handle dash-separated versions ("Song - Live Version")
   - Use album context conservatively (if album is "Live at Wembley", mark as Live)
   - Classify ambiguous parentheses using heuristics
   - **NEW:** Add negative patterns for part numbers (don't extract "Part 1" as version)
   - **NEW:** Add negative patterns for subtitles ("The Ballad" is not a version)
   - Return combined version string ("Live / Radio Edit")

2. **Update:** `LibraryMetadata.__init__()` to use enhanced method

3. **Add:** Configuration parameters to `config.py`

**Files to modify:**
- `backend/src/airwave/core/normalization.py`
- `backend/src/airwave/worker/scanner.py`
- `backend/src/airwave/config.py`

**Testing:**
- Unit tests for multiple version tags
- Unit tests for dash-separated versions
- Unit tests for album context
- Unit tests for ambiguous parentheses
- **NEW:** Unit tests for part numbers (should NOT be extracted)
- **NEW:** Unit tests for subtitles (should NOT be extracted)

---

### Phase 2: Fuzzy Work Matching (~3.5 hours)

**Goal:** Add fuzzy matching to group works with similar titles with performance safeguards.

**Changes:**

1. **New method:** `FileScanner._find_similar_work(title, artist_id, threshold=None)`
   - **NEW:** Check work count first (skip if > MAX_WORKS)
   - Query works by artist (select only id, title for performance)
   - Use `difflib.SequenceMatcher` for similarity
   - **NEW:** Early termination on >95% match
   - Return best match if similarity >= threshold (default from config)
   - **NEW:** Enhanced logging with similarity ratio and works_compared

2. **Update:** `FileScanner._upsert_work()` to use fuzzy matching
   - Try exact match first (fast path)
   - If no exact match, try fuzzy match
   - If no fuzzy match, create new work
   - Log fuzzy matches for monitoring

3. **Query optimizations:**
   - Use `COUNT(*)` instead of `COUNT(id)`
   - Select only (id, title) columns, not full Work objects

**Files to modify:**
- `backend/src/airwave/worker/scanner.py`
- `backend/src/airwave/config.py` (add threshold constants)

**Testing:**
- Integration tests for work grouping with versions
- Integration tests for fuzzy matching accuracy
- Performance tests (fuzzy matching on large artist catalogs)
- **NEW:** Test work count limit (should skip fuzzy matching for >500 works)
- **NEW:** Test early termination (should return immediately on >95% match)

---

### Phase 3: Testing & Validation (~3 hours)

**Goal:** Ensure changes work correctly and don't create false positives.

**Test Coverage:**

1. **Unit Tests** (`backend/tests/core/test_normalization_enhanced.py`)
   - Multiple version tags: "Song (Live) (Radio Edit)"
   - Dash-separated: "Song - Live Version"
   - Album context: "Song" + album "Live at Wembley"
   - Ambiguous parentheses: "Song (The Ballad)"
   - Part numbers: "Song (Part 1)"

2. **Integration Tests** (`backend/tests/integration/test_work_grouping.py`)
   - Different versions group under same work
   - Fuzzy matching groups similar titles
   - Fuzzy matching doesn't create false positives
   - Performance with large catalogs

3. **Database Analysis**
   - Query to find current duplicate works
   - Query to measure consolidation after changes
   - Query to validate version type distribution

---

## Database Requirements

### Indexes

**Good News:** ✅ All required indexes already exist!

The critical index `ix_works_artist_id` was added in migration `014b1562348a_add_indexes_for_navigation.py`:

```python
# Lines 38-44 of migration 014b1562348a
op.create_index(
    'ix_works_artist_id',
    'works',
    ['artist_id'],
    unique=False
)
```

**Current Indexes on Works Table:**
- `ix_works_title` - on works.title
- `idx_work_title_artist` - composite on (title, artist_id)
- `ix_works_artist_id` - on works.artist_id ✅

**No new migrations needed!**

---

## Migration Strategy

### Option A: Gradual Migration (Recommended)

1. Deploy new code with enhanced extraction
2. New scans use improved logic automatically
3. Existing data remains unchanged
4. Optional cleanup script to merge duplicate works

**Pros:**
- ✅ No downtime
- ✅ No risk to existing data
- ✅ Can validate gradually
- ✅ No database migrations needed

**Cons:**
- ❌ Existing duplicates remain until re-scan
- ❌ Mixed data quality during transition

### Option B: Full Re-scan

1. Backup database
2. Clear works and recordings tables (keep library_files)
3. Re-scan library with new logic
4. Verify results

**Pros:**
- ✅ Clean slate
- ✅ Consistent data quality

**Cons:**
- ❌ Requires downtime
- ❌ Loses manual verifications (identity bridges)
- ❌ Time-consuming for large libraries

**Recommendation:** Use Option A. The fuzzy matching will gradually consolidate works.

---

## Monitoring & Success Metrics

### Metrics to Track

1. **Work Consolidation Rate**
   ```sql
   SELECT
       COUNT(DISTINCT work_id) as total_works,
       COUNT(*) as total_recordings,
       CAST(COUNT(*) AS FLOAT) / COUNT(DISTINCT work_id) as avg_recordings_per_work
   FROM recordings;
   ```
   - **Before:** Expect ~1.2-1.5 recordings per work
   - **After:** Target ~2.0+ recordings per work
   - **Run this BEFORE deployment** to establish baseline

2. **Fuzzy Match Frequency**
   - Add logging to `_find_similar_work()`
   - Monitor how often fuzzy matching is used
   - Review matched pairs for accuracy
   - Target: <5% of all work lookups use fuzzy matching
   - **Enhanced logging format:**
     ```python
     logger.info(
         f"Fuzzy matched work: '{title}' → '{best_match.title}' "
         f"(similarity={best_ratio:.3f}, artist_id={artist_id}, "
         f"works_compared={len(existing_works)})"
     )
     ```

3. **Version Type Distribution**
   ```sql
   SELECT version_type, COUNT(*) as count
   FROM recordings
   GROUP BY version_type
   ORDER BY count DESC;
   ```
   - **Before:** Mostly "Original"
   - **After:** More diverse (Live, Remix, Radio Edit, etc.)

4. **Duplicate Work Detection**
   ```sql
   -- Find works with suspiciously similar titles
   -- IMPORTANT: Add LIMIT to prevent runaway queries on large databases
   WITH work_pairs AS (
       SELECT
           w1.id as work1_id,
           w1.title as title1,
           w2.id as work2_id,
           w2.title as title2,
           w1.artist_id,
           a.name as artist_name
       FROM works w1
       JOIN works w2 ON w1.artist_id = w2.artist_id AND w1.id < w2.id
       JOIN artists a ON w1.artist_id = a.id
   )
   SELECT
       artist_name,
       title1,
       title2,
       (SELECT COUNT(*) FROM recordings WHERE work_id = work1_id) as recordings1,
       (SELECT COUNT(*) FROM recordings WHERE work_id = work2_id) as recordings2
   FROM work_pairs
   WHERE
       SUBSTR(title1, 1, 20) = SUBSTR(title2, 1, 20)
       OR title1 LIKE '%' || title2 || '%'
       OR title2 LIKE '%' || title1 || '%'
   ORDER BY artist_name, title1
   LIMIT 1000;  -- Prevent performance issues
   ```

### Success Criteria

- ✅ Average recordings per work increases by 30%+
- ✅ Fewer works with single recording (less fragmentation)
- ✅ Version types are more descriptive
- ✅ No false positives in fuzzy matching (manual review of logs)
- ✅ Performance impact <10ms per file scan

---

## Code Examples

### Example 1: Enhanced Version Extraction

**File:** `backend/src/airwave/core/normalization.py`

```python
@staticmethod
def extract_version_type_enhanced(
    title: str,
    album_title: Optional[str] = None
) -> tuple[str, str]:
    """Enhanced version extraction with multiple strategies.

    Improvements over original extract_version_type():
    - Extracts ALL version tags, not just first
    - Handles dash-separated versions
    - Uses album context for live detection
    - Classifies ambiguous parentheses

    Args:
        title: Raw track title
        album_title: Optional album title for context

    Returns:
        Tuple of (clean_title, version_type)

    Examples:
        >>> extract_version_type_enhanced("Song (Live) (Radio Edit)")
        ('Song', 'Live / Radio')

        >>> extract_version_type_enhanced("Song - Live Version")
        ('Song', 'Live')

        >>> extract_version_type_enhanced("Song", album_title="Live at Wembley")
        ('Song', 'Live')
    """
    if not title:
        return "", "Original"

    version_parts = []
    clean_title = title

    # Strategy 1: Extract all parentheses/brackets with version keywords
    matches = list(Normalizer.VERSION_REGEX.finditer(title))
    for match in matches:
        version_parts.append(match.group(1).title())
        clean_title = clean_title.replace(match.group(0), "")

    # Strategy 2: Check for dash-separated versions
    dash_pattern = r"\s+-\s+(live|remix|mix|edit|version|demo|radio|acoustic|unplugged)\b.*$"
    dash_match = re.search(dash_pattern, clean_title, re.IGNORECASE)
    if dash_match:
        version_parts.append(dash_match.group(1).title())
        clean_title = re.sub(dash_pattern, "", clean_title, flags=re.IGNORECASE)

    # Strategy 3: Album context heuristics
    if album_title:
        album_lower = album_title.lower()
        live_keywords = ["live", "concert", "unplugged", "acoustic session"]
        if any(keyword in album_lower for keyword in live_keywords):
            if "Live" not in version_parts and "Unplugged" not in version_parts:
                version_parts.append("Live")

    # Strategy 4: Handle remaining parentheses (IMPROVED with negative patterns)
    # Keep longer parenthetical content (likely subtitles)
    # Extract shorter content if it looks like version info
    remaining_parens = re.findall(r"[\(\[]([^\)\]]+)[\)\]]", clean_title)
    for paren_content in remaining_parens:
        words = paren_content.split()
        paren_lower = paren_content.lower()

        # NEGATIVE PATTERN 1: Skip part numbers (different works, not versions)
        if re.search(r'\b(part|pt\.?)\s*\d+\b', paren_lower):
            continue

        # NEGATIVE PATTERN 2: Skip subtitles starting with "The"
        if paren_lower.startswith("the ") and len(words) > 2:
            continue

        # Extract if short and contains version indicators
        if len(words) <= 3 and any(
            word in paren_lower
            for word in ["edit", "mix", "version", "cut", "take", "session"]
        ):
            version_parts.append(paren_content.title())
            clean_title = clean_title.replace(f"({paren_content})", "")
            clean_title = clean_title.replace(f"[{paren_content}]", "")

    # Clean up the title
    clean_title = re.sub(r"\s*[\(\[]\s*[\)\]]", "", clean_title)  # Empty brackets
    clean_title = re.sub(r"\s+", " ", clean_title).strip()

    # Combine version parts
    if version_parts:
        # Deduplicate while preserving order
        seen = set()
        unique_parts = []
        for part in version_parts:
            if part.lower() not in seen:
                unique_parts.append(part)
                seen.add(part.lower())
        version_type = " / ".join(unique_parts)
    else:
        version_type = "Original"

    return clean_title, version_type
```

### Example 2: Fuzzy Work Matching

**File:** `backend/src/airwave/worker/scanner.py`

```python
async def _find_similar_work(
    self,
    title: str,
    artist_id: int,
    similarity_threshold: float = None
) -> Optional[Work]:
    """Find existing work with similar title using fuzzy matching.

    This is a safety net for cases where version extraction fails
    and creates slightly different work titles.

    Args:
        title: Cleaned work title
        artist_id: Primary artist ID
        similarity_threshold: Minimum similarity ratio (default from config: 0.85)

    Returns:
        Existing work if found, None otherwise

    Example:
        # These would match (similarity > 0.85):
        "song title" vs "song title " (extra space)
        "song title" vs "song title the" (>85% similar)

        # These would NOT match (similarity < 0.85):
        "song title" vs "song title the ballad of love"
        "song title" vs "different song"
    """
    import difflib
    from airwave.core.config import settings

    # Use config default if not specified
    if similarity_threshold is None:
        similarity_threshold = getattr(
            settings,
            'WORK_FUZZY_MATCH_THRESHOLD',
            0.85
        )

    max_works = getattr(
        settings,
        'WORK_FUZZY_MATCH_MAX_WORKS',
        500
    )

    # PERFORMANCE SAFEGUARD: Check work count first
    work_count_stmt = select(func.count()).select_from(Work).where(
        Work.artist_id == artist_id
    )
    work_count_result = await self.session.execute(work_count_stmt)
    work_count = work_count_result.scalar()

    if work_count > max_works:
        logger.debug(
            f"Skipping fuzzy matching for artist_id={artist_id} "
            f"(has {work_count} works, limit={max_works})"
        )
        return None

    # OPTIMIZATION: Select only id and title columns (not full Work objects)
    stmt = select(Work.id, Work.title).where(Work.artist_id == artist_id)
    result = await self.session.execute(stmt)
    work_tuples = result.all()

    # Find best match using fuzzy string matching
    best_match_id = None
    best_ratio = 0.0

    for work_id, work_title in work_tuples:
        ratio = difflib.SequenceMatcher(None, title, work_title).ratio()

        # OPTIMIZATION: Early termination on very high match
        if ratio > 0.95:
            logger.debug(
                f"Early termination: '{title}' → '{work_title}' "
                f"(ratio={ratio:.3f})"
            )
            return await self.session.get(Work, work_id)

        if ratio > best_ratio and ratio >= similarity_threshold:
            best_ratio = ratio
            best_match_id = work_id

    if best_match_id:
        best_match = await self.session.get(Work, best_match_id)
        # ENHANCED LOGGING with structured data
        logger.info(
            f"Fuzzy matched work: '{title}' → '{best_match.title}' "
            f"(similarity={best_ratio:.3f}, artist_id={artist_id}, "
            f"works_compared={len(work_tuples)})"
        )
        return best_match

    return None

async def _upsert_work(self, title: str, artist_id: int) -> Work:
    """Atomically insert or get existing work with fuzzy matching fallback.

    Strategy:
    1. Try exact match first (fast path)
    2. If no exact match, try fuzzy match (handles edge cases)
    3. If no fuzzy match, create new work
    """
    # Step 1: Try exact match (existing logic)
    stmt = select(Work).where(
        Work.title == title,
        Work.artist_id == artist_id
    )
    result = await self.session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    # Step 2: Try fuzzy match (NEW)
    similar_work = await self._find_similar_work(title, artist_id)
    if similar_work:
        # Log for monitoring
        logger.info(
            f"Fuzzy matched work: '{title}' → '{similar_work.title}' "
            f"(artist_id={artist_id})"
        )
        return similar_work

    # Step 3: Create new work (existing logic)
    stmt = sqlite_insert(Work).values(
        title=title,
        artist_id=artist_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    try:
        await self.session.execute(stmt)
        await self.session.flush()

        stmt_select = select(Work).where(
            Work.title == title,
            Work.artist_id == artist_id
        )
        result = await self.session.execute(stmt_select)
        work = result.scalar_one()
        return work
    except IntegrityError:
        # Race condition, query again
        await self.session.rollback()
        stmt = select(Work).where(
            Work.title == title,
            Work.artist_id == artist_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
```

---

## Risk Assessment

### Low Risk ✅

- **No database schema changes** - Uses existing `version_type` field
- **Backward compatible** - Existing data continues to work
- **Gradual rollout** - Only affects new scans
- **High fuzzy threshold** - 90% similarity prevents false positives
- **Logging** - All fuzzy matches are logged for review

### Potential Issues & Mitigations

1. **Performance Impact**
   - **Risk:** Fuzzy matching queries all works per artist
   - **Mitigation:** Only runs when exact match fails (rare)
   - **Mitigation:** Add caching if needed
   - **Mitigation:** Limit to artists with <1000 works

2. **False Positives**
   - **Risk:** Different songs grouped together
   - **Mitigation:** High threshold (90%)
   - **Mitigation:** Logging for manual review
   - **Mitigation:** Can adjust threshold based on results

3. **Version Extraction Errors**
   - **Risk:** Incorrect classification of parentheses
   - **Mitigation:** Comprehensive test coverage
   - **Mitigation:** Conservative heuristics
   - **Mitigation:** Can fall back to original method if needed

---

## Timeline & Effort

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| **Phase 1** | Enhanced version extraction | 4.5 hours |
| | - Implement `extract_version_type_enhanced()` | 2 hours |
| | - Add negative patterns (part numbers, subtitles) | 0.5 hours |
| | - Update `LibraryMetadata` | 0.5 hours |
| | - Add config parameters | 0.5 hours |
| | - Unit tests (including edge cases) | 1 hour |
| **Phase 2** | Fuzzy work matching | 3.5 hours |
| | - Implement `_find_similar_work()` with safeguards | 1.5 hours |
| | - Update `_upsert_work()` | 0.5 hours |
| | - Query optimizations (COUNT(*), column selection) | 0.5 hours |
| | - Integration tests | 1 hour |
| **Phase 3** | Testing & validation | 3 hours |
| | - Collect baseline metrics | 0.5 hours |
| | - Database analysis queries | 0.5 hours |
| | - Performance testing | 1 hour |
| | - Manual validation | 1 hour |
| **Total** | | **11 hours** |

**Change from original estimate:** +1 hour for additional edge case handling and optimizations

---

## Next Steps

1. **Review this plan** - Discuss approach and get feedback
2. **Decide on migration strategy** - Gradual vs full re-scan
3. **Implement Phase 1** - Enhanced version extraction
4. **Test Phase 1** - Validate with sample data
5. **Implement Phase 2** - Fuzzy matching
6. **Test Phase 2** - Integration tests
7. **Deploy to production** - Monitor metrics
8. **Optional cleanup** - Merge existing duplicates

---

## Questions for Discussion

1. ~~**Fuzzy matching threshold:** Is 90% the right threshold, or should it be higher/lower?~~
   - **RESOLVED:** Use 85% (aligned with existing artist matching in config.py)

2. ~~**Performance concerns:** Should we add caching or limit fuzzy matching to artists with <N works?~~
   - **RESOLVED:** Add work count limit of 500 works, skip caching for now

3. ~~**Album context:** Should we use album title for version detection, or is it too risky?~~
   - **RESOLVED:** Use conservatively (only when no version info already extracted)

4. **Migration strategy:** Gradual rollout or full re-scan?
   - **RECOMMENDATION:** Gradual rollout (Option A)

5. **Version type format:** Is "Live / Radio Edit" a good format, or prefer "Live (Radio Edit)"?
   - **CURRENT:** Using " / " separator (can be changed if needed)

6. **Cleanup script:** Should we create a script to merge existing duplicate works?
   - **DEFERRED:** Optional, can be added after deployment if needed

---

## References

- **Current Implementation:** `backend/src/airwave/worker/scanner.py` (lines 169-175, 426-428)
- **Normalization Logic:** `backend/src/airwave/core/normalization.py` (lines 362-401)
- **Database Models:** `backend/src/airwave/core/models.py` (lines 46-73, 116-147)
- **Existing Tests:** `backend/tests/core/test_normalization.py` (lines 69-77, 123-132)
- **Database Indexes:** `backend/alembic/versions/014b1562348a_add_indexes_for_navigation.py` (lines 38-44)
- **Configuration:** `backend/src/airwave/config.py`

---

## Summary of Changes from Original Plan

### ✅ Accepted Recommendations

**From Data Scientist Agent:**
1. Fuzzy threshold lowered to 85% (from 90%)
2. Added configurable parameters in config.py
3. Work count limit of 500 works
4. Early termination on >95% match
5. Negative patterns for part numbers and subtitles
6. Enhanced logging with structured data
7. Baseline metrics collection

**From SQL Agent:**
1. Use COUNT(*) instead of COUNT(id)
2. Select only (id, title) columns for fuzzy matching
3. Add LIMIT to duplicate detection query
4. Confirmed index already exists (no migration needed!)

### ❌ Rejected Recommendations

1. Covering index - Overkill, existing indexes sufficient
2. Version type index - Not needed for current use case
3. Separate transactions - Adds complexity unnecessarily
4. Version normalization dictionary - Defer to Phase 2
5. LRU caching - May cause stale data issues

### 📊 Updated Metrics

- **Effort:** 11 hours (was 10 hours)
- **Fuzzy Threshold:** 85% (was 90%)
- **Work Count Limit:** 500 works (new)
- **Database Migrations:** 0 (was 1) - Index already exists!

---

**Plan Status:** ✅ Ready for implementation after review approval


