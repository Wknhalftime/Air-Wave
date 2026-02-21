# QA Assessment: Artist Display Names

**Date:** 2026-02-19  
**Reviewed against:** `backend/docs/artist-display-names.md`

## Summary

The doc accurately describes the implementation, but **testing is incomplete**. The MusicBrainz client is well-tested; the scanner integration, backfill script, and API contract are not. There is also a **critical gap**: `display_name` is never returned by the API, so the frontend cannot use it.

---

## 1. Implementation Verification ✅

| Component | Doc Claim | Actual | Status |
|-----------|-----------|--------|--------|
| Artist model | `display_name` column | `models.py` has `display_name` | ✅ |
| MusicBrainz client | `musicbrainz_client.py` | Exists, matches doc | ✅ |
| Scanner `_upsert_artist` | Sets `display_name = name` | Sets `display_name = name` | ✅ |
| Scanner `update_artist_display_names_from_musicbrainz` | Batch-updates from MB | Exists, matches doc | ✅ |
| Backfill script | `airwave.scripts.backfill_artist_display_names` | Exists, matches doc | ✅ |
| Migration | `add_artist_display_name.py` | Exists in alembic/versions | ✅ |

---

## 2. Test Coverage Analysis

### 2.1 MusicBrainz Client — ✅ Adequate

**File:** `tests/worker/test_musicbrainz_client.py`

| Claimed Coverage | Test | Status |
|------------------|------|--------|
| Successful artist name fetching | `test_fetch_artist_name_success` | ✅ |
| 404 handling | `test_fetch_artist_name_not_found` | ✅ |
| 503 handling | `test_fetch_artist_name_service_unavailable` | ✅ |
| Network errors | `test_fetch_artist_name_network_error` | ✅ |
| Batch fetching | `test_fetch_artist_names_batch` | ✅ |
| Rate limiting | `test_rate_limiting` | ✅ |
| Session management | `test_session_cleanup` | ✅ |

All 7 tests pass. Doc claims are accurate.

### 2.2 Scanner Integration — ✅ Tested

**File:** `tests/worker/test_scanner_comprehensive.py` (and others)

| Component | Tested? | File |
|-----------|---------|------|
| `_upsert_artist` sets `display_name = name` | Yes | test_scanner_comprehensive |
| `update_artist_display_names_from_musicbrainz` | Yes | test_scanner_display_names |
| Update when MBID fetch fails (fallback to name) | Yes | test_scanner_display_names |

**Implementation:** See `tests/worker/test_scanner_display_names.py`:

### 2.3 Backfill Script — ✅ Tested

**File:** `airwave.scripts.backfill_artist_display_names`

**Implementation:** See `tests/scripts/test_backfill_artist_display_names.py`:

- `test_dry_run_does_not_modify_database`
- `test_skip_mbid_only_updates_artists_without_mbids`
- `test_backfill_artists_without_mbids_sets_display_name`
- `test_main_with_skip_mbid_skips_musicbrainz_step`

### 2.4 Migration — ✅ Tested

**Implementation:** See `tests/alembic/test_migration_display_name.py`:
- `test_migration_add_artist_display_name_upgrade_downgrade` — upgrade/downgrade cycle
- `test_migration_backfills_display_name_on_upgrade` — backfill behavior

**Note:** Migration downgrade was updated to use `batch_alter_table` for SQLite compatibility (SQLite doesn't support DROP COLUMN directly).

### 2.5 API Contract — ⚠️ `display_name` Not Exposed

**Files:** `api/schemas.py`, `api/routers/library.py`

| Endpoint | Returns `display_name`? | Issue |
|----------|-------------------------|-------|
| `GET /artists/{id}` (ArtistDetail) | No | Returns `name` only |
| `GET /artists` (list) | No | Returns `name` only |
| Work/Recording list items | No | Use `artist.name` / `artist_names` |

The doc says display_name is for "display purposes," but the API never returns it. The frontend will always receive `name`, not `display_name`.

**Recommendation:** Either:

- **A)** Add `display_name` to `ArtistDetail` and `ArtistStats`, and return `display_name or name` for display (so UI shows canonical names when available), or  
- **B)** Update the doc to state that `display_name` is for internal/future use and not yet exposed via the API.

---

## 3. Testing Gaps Summary

| Priority | Gap | Status |
|----------|-----|--------|
| High | API does not return `display_name` | Open — add to schemas/router or document |
| ~~High~~ | ~~No tests for update_artist_display_names_from_musicbrainz~~ | ✅ Done |
| ~~Medium~~ | ~~_upsert_artist display_name not asserted~~ | ✅ Done |
| ~~Medium~~ | ~~Backfill script untested~~ | ✅ Done |
| ~~Low~~ | ~~Migration untested~~ | ✅ Done |

---

## 4. Test Cases to Add

### Scanner tests (`test_scanner_comprehensive.py` or new `test_scanner_display_names.py`)

```python
async def test_upsert_artist_sets_display_name(self, db_session):
    """_upsert_artist sets display_name = name as fallback."""
    scanner = FileScanner(db_session)
    artist = await scanner._upsert_artist("nirvana")
    assert artist.display_name == "nirvana"

async def test_update_artist_display_names_from_musicbrainz(self, db_session):
    """Batch-updates display_name from MusicBrainz for artists with MBID."""
    # Create artist with MBID but no display_name
    # Mock MusicBrainzClient.fetch_artist_name to return "Metallica"
    # Call update_artist_display_names_from_musicbrainz
    # Assert artist.display_name == "Metallica"
```

### API schema update (if exposing display_name)

```python
# In schemas.py ArtistDetail:
display_name: Optional[str] = None  # Canonical name from MusicBrainz; fallback to name

# In library.get_artist:
return ArtistDetail(
    ...
    name=row.Artist.name,
    display_name=row.Artist.display_name or row.Artist.name,
    ...
)
```

---

## 5. Conclusion

- **MusicBrainz client tests** — Correct and sufficient.
- **Scanner and backfill** — Implemented per doc but not tested; add tests for display_name behavior and `update_artist_display_names_from_musicbrainz`.
- **API** — `display_name` is not exposed; decide whether to add it to responses and update the doc or explicitly document it as internal-only.
