# Testing Action Checklist

## ✅ Immediate Actions (COMPLETED - 2026-02-02)

### 1. Fix API Route Paths ✅
**Files**: `tests/api/test_library.py`, `tests/api/test_system.py`

- [x] Update `test_list_tracks_empty()` route from `/api/library/tracks` to `/api/v1/library/tracks`
- [x] Update `test_list_tracks_with_data()` route from `/api/library/tracks` to `/api/v1/library/tracks`
- [x] Update `test_health_check()` route from `/api/system/health` to `/api/v1/system/health`
- [x] Update `test_config()` route from `/api/system/config` to `/api/v1/system/config`

### 2. Fix Identity Resolver Test ✅
**File**: `tests/worker/test_identity_resolver.py`

- [x] Update `test_detect_split()` to expect `["Gnr", "Slash"]` instead of `["GnR", "Slash"]`

### 3. Fix Matcher Test ✅
**File**: `tests/worker/test_matcher.py`

- [x] Update `test_matcher_logic()` to unpack tuple: `match_id, reason = await matcher.find_match(...)`
- [x] Add assertion for reason: `assert reason == "No Match Found"`

### 4. Remove Obsolete Test ✅
**File**: `tests/test_sanity.py`

- [x] Delete `test_sanity.py` (debug test removed)

**Result**: All broken tests fixed! Test count: 32 (down from 33)

---

## ⚠️ High Priority (Critical Coverage Gaps)

### 5. Create Scanner Tests (0% → 80%)
**New File**: `tests/worker/test_scanner_comprehensive.py`

- [ ] `test_scan_directory_recursive()` - Test directory traversal
- [ ] `test_metadata_extraction_mp3()` - Test MP3 metadata extraction
- [ ] `test_metadata_extraction_flac()` - Test FLAC metadata extraction
- [ ] `test_artist_deduplication()` - Test artist lookup/creation
- [ ] `test_work_deduplication()` - Test work lookup/creation
- [ ] `test_recording_creation()` - Test recording creation
- [ ] `test_progress_tracking()` - Test progress updates
- [ ] `test_corrupt_file_handling()` - Test error handling
- [ ] `test_skip_existing_files()` - Test file already exists

### 6. Expand Matcher Tests (49% → 80%)
**New File**: `tests/worker/test_matcher_comprehensive.py`

- [ ] `test_batch_matching_deduplication()` - Test batch processing
- [ ] `test_variant_match_strategy()` - Test fuzzy matching (85%/80%)
- [ ] `test_vector_semantic_search()` - Test ChromaDB integration
- [ ] `test_alias_match_threshold()` - Test 70% threshold
- [ ] `test_match_explain_mode()` - Test diagnostic output
- [ ] `test_scan_and_promote()` - Test library creation from logs
- [ ] `test_link_orphaned_logs()` - Test auto-linking via identity bridge
- [ ] `test_multi_artist_handling()` - Test collaboration detection

### 7. Expand Vector DB Tests (66% → 90%)
**New File**: `tests/core/test_vector_db_comprehensive.py`

- [ ] `test_singleton_pattern()` - Verify single instance
- [ ] `test_batch_indexing()` - Test add_tracks() bulk operation
- [ ] `test_batch_search()` - Test search_batch() with 500 query chunks
- [ ] `test_persistence()` - Test ChromaDB persistence
- [ ] `test_distance_threshold()` - Test 0.15 distance cutoff
- [ ] `test_empty_query_handling()` - Test edge cases

---

## 📋 Medium Priority (API Coverage)

### 8. Expand Library Router Tests (22% → 70%)
**File**: `tests/api/test_library_comprehensive.py`

- [ ] `test_get_recordings_with_filters()` - Test search/filter
- [ ] `test_get_recordings_pagination()` - Test limit/offset
- [ ] `test_get_artists()` - Test artist listing
- [ ] `test_get_albums()` - Test album listing
- [ ] `test_get_recording_by_id()` - Test single recording fetch

### 9. Expand Admin Router Tests (33% → 70%)
**File**: `tests/api/test_admin_comprehensive.py`

- [ ] `test_import_csv_upload()` - Test file upload
- [ ] `test_scan_directory()` - Test scan trigger
- [ ] `test_sync_files()` - Test file sync
- [ ] `test_progress_sse_stream()` - Test SSE progress
- [ ] `test_match_explain()` - Test diagnostic endpoint
- [ ] `test_reindex_vector_db()` - Test reindex trigger

### 10. Expand History Router Tests (38% → 70%)
**File**: `tests/api/test_history_comprehensive.py`

- [ ] `test_get_logs_with_date_filter()` - Test date range
- [ ] `test_get_logs_with_station_filter()` - Test station filter
- [ ] `test_get_logs_pagination()` - Test limit/offset
- [ ] `test_get_logs_with_recording_id()` - Test matched logs

---

## 🔗 Integration Tests (New)

### 11. End-to-End Matching Workflow
**New File**: `tests/integration/test_end_to_end_matching.py`

- [ ] `test_full_matching_pipeline()` - Import CSV → Match → Verify
- [ ] `test_identity_bridge_creation()` - Create bridge → Re-match
- [ ] `test_vector_fallback()` - Exact fails → Vector succeeds

### 12. CSV Import Workflow
**New File**: `tests/integration/test_import_workflow.py`

- [ ] `test_csv_import_with_matching()` - Full import + match
- [ ] `test_station_creation()` - Auto-create station
- [ ] `test_duplicate_log_handling()` - Skip duplicates

### 13. Directory Scan Workflow
**New File**: `tests/integration/test_scan_workflow.py`

- [ ] `test_full_directory_scan()` - Scan → Extract → Index
- [ ] `test_incremental_scan()` - Skip existing files
- [ ] `test_vector_db_indexing()` - Verify ChromaDB updated

---

## 🛠️ Code Quality Improvements

### 14. Fix Pydantic Deprecations
**Files**: `task_store.py`, `identity.py`

- [ ] Replace `class Config` with `model_config = ConfigDict(...)`
- [ ] Update `json_encoders` to use custom serializers

### 15. Fix Datetime Deprecations
**File**: `task_store.py`

- [ ] Replace `datetime.utcnow()` with `datetime.now(UTC)`
- [ ] Update all 3 occurrences

---

## 📊 Progress Tracking

### Coverage Goals

| Phase | Target Coverage | Deadline |
|-------|----------------|----------|
| Phase 1: Fix Broken Tests | 48% → 55% | Week 1 |
| Phase 2: Critical Coverage | 55% → 70% | Week 2 |
| Phase 3: API Coverage | 70% → 75% | Week 3 |
| Phase 4: Integration Tests | 75% → 80% | Week 4 |

### Test Count Goals

| Test Type | Current | Target |
|-----------|---------|--------|
| Unit Tests | 20 | 60 |
| Integration Tests | 13 | 30 |
| E2E Tests | 0 | 10 |
| **Total** | **33** | **100** |

---

## ✅ Completion Criteria

- [ ] All existing tests passing (0 failures)
- [ ] Overall coverage ≥ 80%
- [ ] Core modules coverage ≥ 95%
- [ ] Worker modules coverage ≥ 80%
- [ ] API routers coverage ≥ 75%
- [ ] No Pydantic deprecation warnings
- [ ] No datetime deprecation warnings
- [ ] At least 10 integration tests
- [ ] CI/CD pipeline passing

---

## 🚀 Quick Start Commands

### Run All Tests
```bash
cd backend
poetry run pytest -v
```

### Run with Coverage
```bash
poetry run pytest --cov=airwave --cov-report=html
```

### Run Specific Test File
```bash
poetry run pytest tests/worker/test_matcher.py -v
```

### Run Failed Tests Only
```bash
poetry run pytest --lf -v
```

### Watch Mode (Re-run on changes)
```bash
poetry run pytest-watch
```

