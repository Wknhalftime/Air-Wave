# Artist Display Names

## Overview

The `display_name` field on the `Artist` model provides canonical artist names for display purposes. This ensures that artists are shown with their official names from MusicBrainz when available, while falling back to normalized names from metadata.

## Implementation

### Database Schema

The `Artist` model has been extended with a new `display_name` column:

```python
class Artist(Base, TimestampMixin):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(36), ...)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

### Logic

1. **Primary source**: If the artist has a MusicBrainz ID (MBID), the `display_name` is fetched from the MusicBrainz API
2. **Fallback**: If no MBID exists, `display_name` is set to the normalized artist name

### Components

#### 1. MusicBrainz API Client

**File**: `backend/src/airwave/worker/musicbrainz_client.py`

Provides a client for fetching canonical artist names from MusicBrainz:

- **Rate limiting**: Respects MusicBrainz's 1 request/second limit
- **Batch fetching**: Processes multiple artists efficiently
- **Error handling**: Gracefully handles 404, 503, and network errors

**Usage**:
```python
from airwave.worker.musicbrainz_client import MusicBrainzClient

client = MusicBrainzClient()
name = await client.fetch_artist_name(mbid)
await client.close()
```

#### 2. Scanner Integration

**File**: `backend/src/airwave/worker/scanner.py`

The `FileScanner` class has been updated:

- `_upsert_artist()`: Sets `display_name = name` as fallback during artist creation
- `update_artist_display_names_from_musicbrainz()`: Batch-updates display names from MusicBrainz API

**Usage**:
```python
scanner = FileScanner(session)
stats = await scanner.update_artist_display_names_from_musicbrainz(
    batch_size=50,
    limit=100  # Optional
)
```

#### 3. Backfill Script

**File**: `backend/src/airwave/scripts/backfill_artist_display_names.py`

Standalone script to populate `display_name` for existing artists:

```bash
# Dry run (show what would be updated)
poetry run python -m airwave.scripts.backfill_artist_display_names --dry-run

# Update all artists with MBIDs
poetry run python -m airwave.scripts.backfill_artist_display_names --batch-size 50

# Update limited number (for testing)
poetry run python -m airwave.scripts.backfill_artist_display_names --limit 100

# Only update artists without MBIDs
poetry run python -m airwave.scripts.backfill_artist_display_names --skip-mbid
```

#### 4. Database Migration

**File**: `backend/alembic/versions/add_artist_display_name.py`

Alembic migration to add the `display_name` column:

```bash
# Run migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Workflow

### For New Artists (During Scanning)

1. File is scanned and artist metadata is extracted
2. If MBID is present in file tags, artist is created with MBID
3. `display_name` is initially set to normalized name
4. Backfill script can be run periodically to fetch canonical names from MusicBrainz

### For Existing Artists (Backfill)

1. Run the backfill script: `poetry run python -m airwave.scripts.backfill_artist_display_names`
2. Script finds all artists with MBIDs but no display_name
3. Fetches canonical names from MusicBrainz in batches (respecting rate limits)
4. Updates `display_name` in database
5. For artists without MBIDs, sets `display_name = name`

## MusicBrainz API Details

- **Base URL**: `https://musicbrainz.org/ws/2`
- **Artist endpoint**: `GET /artist/{mbid}?fmt=json`
- **Rate limit**: 1 request/second (unauthenticated)
- **User-Agent**: Required header (set to `AirWave/0.1.0`)

### Example Response

```json
{
  "id": "65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab",
  "name": "Metallica",
  "type": "Group",
  "country": "US",
  ...
}
```

## Testing

### MusicBrainz Client

Unit tests in `backend/tests/worker/test_musicbrainz_client.py`:

```bash
pytest tests/worker/test_musicbrainz_client.py -v
```

Tests cover:
- Successful artist name fetching
- Error handling (404, 503, network errors)
- Batch fetching
- Rate limiting
- Session management

### Scanner

`tests/worker/test_scanner_display_names.py` covers `update_artist_display_names_from_musicbrainz` with mocked MusicBrainz. `test_scanner_comprehensive.py` asserts `_upsert_artist` sets `display_name = name`.

### Backfill Script

`tests/scripts/test_backfill_artist_display_names.py` covers `--dry-run`, `--skip-mbid`, and non-MBID backfill.

### Migration

`tests/alembic/test_migration_display_name.py` covers upgrade/downgrade and backfill behavior.

### QA Assessment

For full test coverage analysis and gaps, see `backend/docs/artist-display-names-qa-assessment.md`.

## Performance Considerations

- **Batch size**: Default is 50 artists per batch
- **Rate limiting**: 1.1 seconds between requests (conservative)
- **Async processing**: Uses aiohttp for non-blocking I/O
- **Database updates**: Committed in batches to minimize transaction overhead

## Future Enhancements

1. **Caching**: Cache MusicBrainz responses to reduce API calls
2. **Background task**: Automatically update display names during scanning
3. **User override**: Allow manual override of display names
4. **Localization**: Support for localized artist names from MusicBrainz

