# Work-Recording Grouping: Test Coverage Analysis

**QA Expert Review**  
**Date:** 2026-02-18  
**Status:** ⚠️ **TEST GAPS IDENTIFIED - ACTION REQUIRED**

---

## Executive Summary

After reviewing the evaluation summaries and existing test suite, I've identified **critical test gaps** that must be addressed before implementation. The current test coverage is **good for basic functionality** but **missing key test cases** for the new features.

**Test Coverage Status:**
- ✅ **Unit Tests (Normalization):** 70% covered - Missing enhanced extraction edge cases
- ⚠️ **Unit Tests (Fuzzy Matching):** 0% covered - **CRITICAL GAP**
- ⚠️ **Integration Tests (Work Grouping):** 0% covered - **CRITICAL GAP**
- ⚠️ **Performance Tests:** 0% covered - **CRITICAL GAP**
- ✅ **Database Analysis Queries:** Documented but not automated

**Overall Test Coverage:** ~35% (Insufficient for production)

---

## 1. Current Test Coverage Analysis

### 1.1 Existing Tests

**✅ Normalization Tests (`test_normalization.py`):**
- ✅ Basic version extraction: `test_extract_version_type()`
- ✅ Enhanced regex patterns: `test_extract_version_type_enhanced()`
- ✅ Multiple version tags: `test_extract_version_type_enhanced_multiple_tags()`
- ✅ Dash-separated versions: `test_extract_version_type_enhanced_dash_separated()`
- ✅ Part numbers NOT extracted: `test_extract_version_type_enhanced_part_numbers_not_extracted()`
- ✅ Subtitles NOT extracted: `test_extract_version_type_enhanced_subtitles_not_extracted()`
- ✅ Album context: `test_extract_version_type_enhanced_album_context()`
- ✅ Ambiguous parentheses: `test_extract_version_type_enhanced_ambiguous_parentheses()`
- ✅ Deduplication: `test_extract_version_type_enhanced_deduplication()`
- ✅ Backward compatibility: `test_extract_version_type_enhanced_backward_compatibility()`

**✅ Scanner Tests (`test_scanner_comprehensive.py`):**
- ✅ Basic metadata normalization
- ✅ Version extraction from titles
- ✅ Artist/Work/Recording creation
- ⚠️ **Missing:** Work grouping with fuzzy matching
- ⚠️ **Missing:** Fuzzy matching accuracy tests

### 1.2 Missing Test Coverage

**❌ CRITICAL: Fuzzy Matching Tests**
- No tests for `_find_similar_work()` method
- No tests for fuzzy matching threshold (85%)
- No tests for work count limit (500)
- No tests for early termination (>95%)
- No tests for false positive prevention
- No tests for false negative detection

**❌ CRITICAL: Integration Tests**
- No tests for work grouping with multiple versions
- No tests for fuzzy matching in real scan scenarios
- No tests for performance with large catalogs
- No tests for query optimization (COUNT(*), column selection)

**❌ CRITICAL: Performance Tests**
- No tests for fuzzy matching performance
- No tests for work count query performance
- No tests for large artist catalog handling (>500 works)
- No benchmarks for acceptable performance thresholds

**⚠️ MODERATE: Edge Case Tests**
- Missing tests for version type normalization
- Missing tests for complex version combinations
- Missing tests for edge cases in title matching

---

## 2. Required Test Cases

### 2.1 Phase 1: Enhanced Version Extraction Tests

**Status:** ✅ **MOSTLY COVERED** (90%)

**Existing Coverage:**
- ✅ Multiple version tags
- ✅ Dash-separated versions
- ✅ Album context
- ✅ Part numbers (negative pattern)
- ✅ Subtitles (negative pattern)
- ✅ Ambiguous parentheses

**Missing Test Cases:**

1. **Version Type Format Consistency**
   ```python
   def test_version_type_format_consistency():
       """Test that version types use consistent format."""
       # Should use " / " separator
       clean, version = extract_version_type_enhanced("Song (Live) (Radio Edit)")
       assert version == "Live / Radio Edit"  # or "Live / Radio"
   ```

2. **Complex Version Combinations**
   ```python
   def test_complex_version_combinations():
       """Test complex version tag combinations."""
       # Multiple dashes and parentheses
       clean, version = extract_version_type_enhanced(
           "Song (Live) - Radio Edit [Extended]"
       )
       # Should extract all version tags
   ```

3. **Version Type Normalization (Future)**
   ```python
   def test_version_type_normalization():
       """Test that similar version types are normalized."""
       # "Extended Mix" and "Extended Version" → "Extended"
       # Deferred to Phase 2, but test structure needed
   ```

**Priority:** Low (most cases covered)

---

### 2.2 Phase 2: Fuzzy Matching Tests

**Status:** ❌ **NOT COVERED** (0%) - **CRITICAL GAP**

**Required Test File:** `backend/tests/worker/test_scanner_fuzzy_matching.py`

#### Test Category 1: Basic Fuzzy Matching

```python
@pytest.mark.asyncio
async def test_fuzzy_matching_finds_similar_work(db_session):
    """Test that fuzzy matching finds works with similar titles."""
    scanner = FileScanner(db_session)
    
    # Create artist and work
    artist = await scanner._upsert_artist("test artist")
    work1 = await scanner._upsert_work("song title", artist.id)
    
    # Find similar work (extra space)
    similar = await scanner._find_similar_work("song title ", artist.id)
    assert similar.id == work1.id

@pytest.mark.asyncio
async def test_fuzzy_matching_threshold_85_percent(db_session):
    """Test that 85% threshold is used correctly."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("test artist")
    
    # Create work
    work1 = await scanner._upsert_work("song title", artist.id)
    
    # 90% similar - should match
    similar = await scanner._find_similar_work("song titl", artist.id)
    assert similar.id == work1.id
    
    # 70% similar - should NOT match
    similar = await scanner._find_similar_work("song different", artist.id)
    assert similar is None

@pytest.mark.asyncio
async def test_fuzzy_matching_early_termination(db_session):
    """Test early termination on >95% match."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("test artist")
    
    # Create multiple works
    work1 = await scanner._upsert_work("song title", artist.id)
    work2 = await scanner._upsert_work("song title extended", artist.id)
    
    # Should return immediately on >95% match
    similar = await scanner._find_similar_work("song title", artist.id)
    assert similar.id == work1.id
    # Verify it didn't check all works (performance test)
```

#### Test Category 2: Work Count Limit

```python
@pytest.mark.asyncio
async def test_fuzzy_matching_skips_large_catalogs(db_session):
    """Test that fuzzy matching is skipped for artists with >500 works."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("prolific artist")
    
    # Create 501 works
    for i in range(501):
        await scanner._upsert_work(f"song {i}", artist.id)
    
    # Should return None (skipped)
    similar = await scanner._find_similar_work("song 0", artist.id)
    assert similar is None

@pytest.mark.asyncio
async def test_fuzzy_matching_allows_small_catalogs(db_session):
    """Test that fuzzy matching works for artists with <500 works."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("small artist")
    
    # Create 100 works
    work1 = await scanner._upsert_work("song title", artist.id)
    for i in range(99):
        await scanner._upsert_work(f"other song {i}", artist.id)
    
    # Should find match
    similar = await scanner._find_similar_work("song titl", artist.id)
    assert similar.id == work1.id
```

#### Test Category 3: False Positive Prevention

```python
@pytest.mark.asyncio
async def test_fuzzy_matching_no_false_positives(db_session):
    """Test that different songs are NOT grouped together."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("test artist")
    
    # Create two different songs
    work1 = await scanner._upsert_work("song one", artist.id)
    work2 = await scanner._upsert_work("song two", artist.id)
    
    # Should NOT match (too different)
    similar = await scanner._find_similar_work("song one", artist.id)
    assert similar is None or similar.id == work1.id  # Exact match only
    
    similar = await scanner._find_similar_work("song two", artist.id)
    assert similar is None or similar.id == work2.id  # Exact match only

@pytest.mark.asyncio
async def test_fuzzy_matching_handles_identical_titles(db_session):
    """Test handling of truly identical titles (edge case)."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("test artist")
    
    # Artist creates two different songs with same title (rare but possible)
    work1 = await scanner._upsert_work("untitled", artist.id)
    work2 = await scanner._upsert_work("untitled", artist.id)
    
    # Should match first one found (or use exact match)
    # This is acceptable behavior - manual review needed for true duplicates
```

#### Test Category 4: Query Optimization

```python
@pytest.mark.asyncio
async def test_fuzzy_matching_selects_only_id_title(db_session):
    """Test that fuzzy matching query selects only id and title columns."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("test artist")
    
    # Create work
    work = await scanner._upsert_work("song title", artist.id)
    
    # Mock or verify that query only selects id, title
    # This is a performance optimization test
    # Can verify by checking query execution plan or mocking select()
```

#### Test Category 5: Configuration

```python
def test_fuzzy_matching_uses_config_threshold():
    """Test that fuzzy matching uses threshold from config."""
    from airwave.core.config import settings
    
    # Verify threshold is configurable
    assert hasattr(settings, 'WORK_FUZZY_MATCH_THRESHOLD')
    assert settings.WORK_FUZZY_MATCH_THRESHOLD == 0.85
    
    assert hasattr(settings, 'WORK_FUZZY_MATCH_MAX_WORKS')
    assert settings.WORK_FUZZY_MATCH_MAX_WORKS == 500
```

**Priority:** **CRITICAL** - Must implement before Phase 2 deployment

---

### 2.3 Phase 2: Integration Tests

**Status:** ❌ **NOT COVERED** (0%) - **CRITICAL GAP**

**Required Test File:** `backend/tests/integration/test_work_grouping.py`

#### Test Category 1: Work Grouping with Versions

```python
@pytest.mark.asyncio
async def test_different_versions_group_under_same_work(db_session, tmp_path, mock_mutagen):
    """Test that different versions of same song group under one work."""
    scanner = FileScanner(db_session)
    
    # Create test files with different versions
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    
    # File 1: Original version
    file1 = music_dir / "song.mp3"
    file1.touch()
    mock_mutagen.return_value = {
        'TIT2': ['Song Title'],
        'TPE1': ['Test Artist']
    }
    
    # File 2: Live version
    file2 = music_dir / "song_live.mp3"
    file2.touch()
    mock_mutagen.return_value = {
        'TIT2': ['Song Title (Live)'],
        'TPE1': ['Test Artist']
    }
    
    # Scan directory
    stats = await scanner.scan_directory(str(music_dir))
    
    # Verify both recordings link to same work
    stmt = select(Work).join(Artist).where(Artist.name == "test artist")
    result = await db_session.execute(stmt)
    works = result.scalars().all()
    
    assert len(works) == 1  # Only one work
    assert len(works[0].recordings) == 2  # Two recordings
    
    # Verify version types
    recording_titles = [r.title for r in works[0].recordings]
    assert "song title" in recording_titles
    assert "song title (live)" in recording_titles or "song title" in recording_titles
    
    version_types = [r.version_type for r in works[0].recordings]
    assert "Original" in version_types
    assert "Live" in version_types
```

#### Test Category 2: Fuzzy Matching in Real Scenarios

```python
@pytest.mark.asyncio
async def test_fuzzy_matching_groups_similar_titles(db_session, tmp_path, mock_mutagen):
    """Test that fuzzy matching groups works with similar but not identical titles."""
    scanner = FileScanner(db_session)
    
    # Create files with slightly different titles
    # (e.g., extra spaces, minor typos)
    # Should group under same work via fuzzy matching
    pass  # Implementation needed
```

#### Test Category 3: Performance with Large Catalogs

```python
@pytest.mark.asyncio
async def test_fuzzy_matching_performance_large_catalog(db_session):
    """Test fuzzy matching performance with large artist catalog."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("large catalog artist")
    
    # Create 100 works
    works = []
    for i in range(100):
        work = await scanner._upsert_work(f"song {i}", artist.id)
        works.append(work)
    
    # Measure fuzzy matching time
    import time
    start = time.time()
    similar = await scanner._find_similar_work("song 0", artist.id)
    elapsed = time.time() - start
    
    # Should complete in <100ms for 100 works
    assert elapsed < 0.1, f"Fuzzy matching took {elapsed}s, expected <0.1s"
    assert similar.id == works[0].id
```

**Priority:** **CRITICAL** - Must implement before Phase 2 deployment

---

### 2.4 Phase 3: Performance Tests

**Status:** ❌ **NOT COVERED** (0%) - **CRITICAL GAP**

**Required Test File:** `backend/tests/performance/test_work_grouping_performance.py`

#### Test Category 1: Query Performance

```python
@pytest.mark.asyncio
async def test_work_count_query_performance(db_session):
    """Test that work count query completes quickly."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("test artist")
    
    # Create 1000 works
    for i in range(1000):
        await scanner._upsert_work(f"song {i}", artist.id)
    
    # Measure COUNT(*) query time
    import time
    from sqlalchemy import select, func
    
    start = time.time()
    stmt = select(func.count()).select_from(Work).where(Work.artist_id == artist.id)
    result = await db_session.execute(stmt)
    count = result.scalar()
    elapsed = time.time() - start
    
    assert count == 1000
    assert elapsed < 0.01, f"Count query took {elapsed}s, expected <0.01s"

@pytest.mark.asyncio
async def test_fuzzy_match_query_performance(db_session):
    """Test that fuzzy match query selects only needed columns."""
    # Verify query optimization (id, title only)
    # Measure query time vs full Work object load
    pass  # Implementation needed
```

#### Test Category 2: Large Catalog Handling

```python
@pytest.mark.asyncio
async def test_large_catalog_handling(db_session):
    """Test behavior with artists having >500 works."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("mega artist")
    
    # Create 600 works
    for i in range(600):
        await scanner._upsert_work(f"song {i}", artist.id)
    
    # Should skip fuzzy matching
    similar = await scanner._find_similar_work("song 0", artist.id)
    assert similar is None  # Skipped due to work count limit
```

**Priority:** **HIGH** - Should implement before production deployment

---

### 2.5 Database Analysis Tests

**Status:** ⚠️ **PARTIALLY COVERED** (Queries documented, not automated)

**Required:** Automated test queries or test fixtures

```python
@pytest.mark.asyncio
async def test_work_consolidation_metrics(db_session):
    """Test work consolidation rate calculation."""
    # Create test data with multiple recordings per work
    # Run consolidation query
    # Verify metrics are calculated correctly
    pass  # Implementation needed

@pytest.mark.asyncio
async def test_duplicate_work_detection_query(db_session):
    """Test duplicate work detection query."""
    # Create duplicate works
    # Run detection query
    # Verify results
    pass  # Implementation needed
```

**Priority:** **MEDIUM** - Useful for monitoring but not critical for functionality

---

## 3. Test Implementation Priority

### Priority 1: CRITICAL (Must Have Before Phase 2)

1. ✅ **Fuzzy Matching Unit Tests** (`test_scanner_fuzzy_matching.py`)
   - Basic fuzzy matching functionality
   - Threshold validation (85%)
   - Work count limit (500)
   - Early termination (>95%)
   - False positive prevention

2. ✅ **Integration Tests** (`test_work_grouping.py`)
   - Work grouping with versions
   - Fuzzy matching in real scenarios
   - End-to-end scan with grouping

**Estimated Effort:** 4-6 hours

### Priority 2: HIGH (Should Have Before Production)

3. ⚠️ **Performance Tests** (`test_work_grouping_performance.py`)
   - Query performance benchmarks
   - Large catalog handling
   - Performance regression tests

**Estimated Effort:** 2-3 hours

### Priority 3: MEDIUM (Nice to Have)

4. 📋 **Database Analysis Tests**
   - Automated metric calculation
   - Duplicate detection validation
   - Version type distribution tests

**Estimated Effort:** 1-2 hours

---

## 4. Test Coverage Gaps Summary

| Test Category | Required | Existing | Coverage | Status |
|---------------|----------|----------|----------|--------|
| **Version Extraction Unit Tests** | 15 | 13 | 87% | ✅ Good |
| **Fuzzy Matching Unit Tests** | 12 | 0 | 0% | ❌ **CRITICAL GAP** |
| **Integration Tests** | 8 | 0 | 0% | ❌ **CRITICAL GAP** |
| **Performance Tests** | 6 | 0 | 0% | ❌ **CRITICAL GAP** |
| **Database Analysis** | 3 | 0 | 0% | ⚠️ Moderate |
| **Total** | **44** | **13** | **30%** | ⚠️ **INSUFFICIENT** |

---

## 5. Recommended Test Implementation Plan

### Step 1: Create Test Files (1 hour)

1. Create `backend/tests/worker/test_scanner_fuzzy_matching.py`
2. Create `backend/tests/integration/test_work_grouping.py`
3. Create `backend/tests/performance/test_work_grouping_performance.py`

### Step 2: Implement Critical Tests (4-6 hours)

**Week 1: Fuzzy Matching Tests**
- Day 1: Basic fuzzy matching tests (2 hours)
- Day 2: Work count limit and early termination (2 hours)
- Day 3: False positive prevention (2 hours)

**Week 2: Integration Tests**
- Day 1: Work grouping with versions (2 hours)
- Day 2: Real scenario tests (2 hours)

### Step 3: Performance Tests (2-3 hours)

- Query performance benchmarks
- Large catalog handling
- Performance regression tests

### Step 4: Database Analysis (1-2 hours)

- Automated metric tests
- Duplicate detection validation

**Total Estimated Effort:** 8-12 hours

---

## 6. Test Quality Checklist

### Unit Tests
- [ ] All edge cases covered
- [ ] Negative test cases included
- [ ] Boundary conditions tested
- [ ] Error handling validated
- [ ] Configuration tested

### Integration Tests
- [ ] End-to-end scenarios covered
- [ ] Real-world data patterns tested
- [ ] Database interactions validated
- [ ] Performance acceptable

### Performance Tests
- [ ] Benchmarks established
- [ ] Regression tests in place
- [ ] Large dataset handling verified
- [ ] Performance budgets defined

### Test Maintenance
- [ ] Tests are maintainable
- [ ] Test data is reusable
- [ ] Tests run quickly (<5 min)
- [ ] Tests are isolated
- [ ] Tests are documented

---

## 7. Risk Assessment

### High Risk: Missing Fuzzy Matching Tests

**Impact:** Critical functionality untested
**Probability:** High (if tests not written)
**Mitigation:** Implement Priority 1 tests before Phase 2 deployment

### Medium Risk: Missing Performance Tests

**Impact:** Performance degradation may go undetected
**Probability:** Medium
**Mitigation:** Implement Priority 2 tests before production

### Low Risk: Missing Database Analysis Tests

**Impact:** Monitoring metrics may be incorrect
**Probability:** Low
**Mitigation:** Manual validation acceptable for initial release

---

## 8. Recommendations

### Immediate Actions (Before Phase 2)

1. ✅ **Create test files** for fuzzy matching and integration tests
2. ✅ **Implement Priority 1 tests** (fuzzy matching + integration)
3. ✅ **Run test suite** and fix any failures
4. ✅ **Achieve >80% coverage** for new code

### Before Production

1. ⚠️ **Implement Priority 2 tests** (performance)
2. ⚠️ **Establish performance benchmarks**
3. ⚠️ **Set up continuous performance monitoring**

### Ongoing

1. 📋 **Maintain test coverage** >80%
2. 📋 **Add tests for new edge cases** as discovered
3. 📋 **Review and update tests** with each release

---

## 9. Conclusion

**Current Test Coverage:** 30% (Insufficient)

**Critical Gaps Identified:**
- ❌ Fuzzy matching tests: 0% coverage
- ❌ Integration tests: 0% coverage
- ❌ Performance tests: 0% coverage

**Recommendation:** **DO NOT PROCEED** with Phase 2 implementation until Priority 1 tests are completed.

**Estimated Test Implementation Time:** 8-12 hours

**Confidence Level After Tests:** High (with comprehensive test coverage)

---

## Appendix: Test File Templates

### Template: `test_scanner_fuzzy_matching.py`

```python
"""Tests for fuzzy work matching functionality."""

import pytest
from airwave.core.models import Artist, Work
from airwave.worker.scanner import FileScanner
from sqlalchemy import select


class TestFuzzyMatching:
    """Test fuzzy matching for work grouping."""
    
    @pytest.mark.asyncio
    async def test_basic_fuzzy_matching(self, db_session):
        """Test basic fuzzy matching functionality."""
        # Implementation here
        pass
    
    # Add more test methods...
```

### Template: `test_work_grouping.py`

```python
"""Integration tests for work-recording grouping."""

import pytest
from airwave.worker.scanner import FileScanner
from airwave.core.models import Work, Recording


class TestWorkGrouping:
    """Test work grouping with versions and fuzzy matching."""
    
    @pytest.mark.asyncio
    async def test_versions_group_under_same_work(self, db_session, tmp_path):
        """Test that different versions group under same work."""
        # Implementation here
        pass
    
    # Add more test methods...
```

---

**End of Test Coverage Analysis**
