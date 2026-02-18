# Library Navigation API

This document describes the API endpoints for navigating the three-level library hierarchy: **Artist → Work → Recording**.

## Overview

The library navigation system provides a hierarchical view of your music collection:

1. **Artists** - Browse all artists in your library
2. **Works** - View all works (songs/compositions) by a specific artist
3. **Recordings** - View all recordings (versions) of a specific work

All endpoints support pagination and return cached results for optimal performance.

---

## Endpoints

### 1. Get Artist Detail

Retrieve detailed information about a specific artist.

**Endpoint:** `GET /api/v1/library/artists/{artist_id}`

**Parameters:**
- `artist_id` (path, required) - The unique identifier of the artist

**Response:** `ArtistDetail`

```json
{
  "id": 42,
  "name": "Queen",
  "musicbrainz_id": "0383dadf-2a4e-4d10-a46a-e9e041da8eb3",
  "work_count": 156,
  "recording_count": 423
}
```

**Fields:**
- `id` - Unique artist identifier
- `name` - Artist name
- `musicbrainz_id` - MusicBrainz artist ID (nullable)
- `work_count` - Total number of works by this artist
- `recording_count` - Total number of recordings across all works

**Status Codes:**
- `200 OK` - Artist found
- `404 Not Found` - Artist does not exist

**Caching:** 5 minutes (300 seconds)

**Example:**
```bash
curl http://localhost:8000/api/v1/library/artists/42
```

---

### 2. List Artist's Works

Retrieve a paginated list of works by a specific artist.

**Endpoint:** `GET /api/v1/library/artists/{artist_id}/works`

**Parameters:**
- `artist_id` (path, required) - The unique identifier of the artist
- `skip` (query, optional) - Number of records to skip (default: 0)
- `limit` (query, optional) - Maximum number of records to return (default: 100, max: 1000)

**Response:** `List[WorkListItem]`

```json
[
  {
    "id": 123,
    "title": "Bohemian Rhapsody",
    "artist_names": "Queen",
    "recording_count": 5,
    "duration_total": 1770,
    "year": 1975
  },
  {
    "id": 124,
    "title": "Under Pressure",
    "artist_names": "Queen, David Bowie",
    "recording_count": 3,
    "duration_total": 744,
    "year": 1981
  }
]
```

**Fields:**
- `id` - Unique work identifier
- `title` - Work title
- `artist_names` - Comma-separated list of all artists (for collaborations)
- `recording_count` - Number of recordings for this work
- `duration_total` - Total duration of all recordings in seconds (nullable)
- `year` - Year of first recording (nullable)

**Status Codes:**
- `200 OK` - Works retrieved successfully (may be empty array)
- `404 Not Found` - Artist does not exist

**Caching:** 3 minutes (180 seconds)

**Example:**
```bash
# Get first page (24 works)
curl http://localhost:8000/api/v1/library/artists/42/works?limit=24

# Get second page
curl http://localhost:8000/api/v1/library/artists/42/works?skip=24&limit=24
```

**Notes:**
- Works are ordered by title (ascending)
- Multi-artist works appear on all participating artists' pages
- The `artist_names` field shows ALL artists, not just the primary artist

---

### 3. Get Work Detail

Retrieve detailed information about a specific work.

**Endpoint:** `GET /api/v1/library/works/{work_id}`

**Parameters:**
- `work_id` (path, required) - The unique identifier of the work

**Response:** `WorkDetail`

```json
{
  "id": 123,
  "title": "Bohemian Rhapsody",
  "artist_id": 42,
  "artist_name": "Queen",
  "artist_names": "Queen",
  "is_instrumental": false,
  "recording_count": 5
}
```

**Response:** `List[RecordingListItem]`

```json
[
  {
    "id": 456,
    "title": "Bohemian Rhapsody",
    "artist_display": "Queen",
    "duration": 354,
    "version_type": "Studio",
    "is_verified": true,
    "has_file": true
  },
  {
    "id": 457,
    "title": "Bohemian Rhapsody (Live at Wembley)",
    "artist_display": "Queen",
    "duration": 360,
    "version_type": "Live",
    "is_verified": true,
    "has_file": false
  }
]
```

**Fields:**
- `id` - Unique recording identifier
- `title` - Recording title
- `artist_display` - Artist name for display
- `duration` - Duration in seconds (nullable)
- `version_type` - Version type (e.g., "Studio", "Live", "Remix") (nullable)
- `is_verified` - Whether the recording is matched/verified
- `has_file` - Whether a library file exists for this recording

**Status Codes:**
- `200 OK` - Recordings retrieved successfully (may be empty array)
- `404 Not Found` - Work does not exist

**Caching:**
- 3 minutes (180 seconds) for unfiltered requests
- 2 minutes (120 seconds) for filtered requests

**Examples:**

```bash
# Get all recordings
curl http://localhost:8000/api/v1/library/works/123/recordings

# Get only matched recordings
curl http://localhost:8000/api/v1/library/works/123/recordings?status=matched

# Get only library files (exclude metadata-only)
curl http://localhost:8000/api/v1/library/works/123/recordings?source=library

# Get unmatched metadata-only recordings
curl http://localhost:8000/api/v1/library/works/123/recordings?status=unmatched&source=metadata

# Pagination
curl http://localhost:8000/api/v1/library/works/123/recordings?skip=0&limit=50
```

**Notes:**
- Recordings are ordered by ID (ascending)
- `status=matched` returns only verified recordings (`is_verified=true`)
- `status=unmatched` returns only unverified recordings (`is_verified=false`)
- `source=library` returns only recordings with library files (`has_file=true`)
- `source=metadata` returns only recordings without library files (`has_file=false`)
- Filters can be combined

---

## Cache Management

The library navigation endpoints use in-memory caching for optimal performance.

### Cache Statistics

**Endpoint:** `GET /api/v1/system/cache/stats`

**Response:**
```json
{
  "cache_enabled": true,
  "total_entries": 42,
  "active_entries": 38,
  "expired_entries": 4
}
```

### Clear Cache

**Endpoint:** `POST /api/v1/system/cache/clear`

**Response:**
```json
{
  "status": "ok",
  "message": "Cache cleared successfully"
}
```

**Use Cases:**
- After bulk data imports
- After manual database changes
- For testing purposes

---

## Error Responses

All endpoints return standard error responses:

**404 Not Found:**
```json
{
  "detail": "Artist not found"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "ensure this value is less than or equal to 1000",
      "type": "value_error.number.not_le"
    }
  ]
}
```

---

## Performance Considerations

### Caching Strategy

- **Artist/Work Detail:** 5-minute cache (infrequently changing data)
- **Work Lists:** 3-minute cache (moderate change frequency)
- **Recording Lists (filtered):** 2-minute cache (frequently changing data)

### Pagination Best Practices

- Use `limit=24` for artist detail work grids (3 columns × 8 rows)
- Use `limit=100` for work detail recording tables (1 page)
- Maximum `limit` is 1000 to prevent memory issues

### Query Optimization

All endpoints use optimized queries with:
- Proper indexes on foreign keys
- Correlated scalar subqueries to avoid N+1 queries
- Aggregation at the database level

---

## Integration Examples

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Get artist detail
artist = requests.get(f"{BASE_URL}/library/artists/42").json()
print(f"Artist: {artist['name']} ({artist['work_count']} works)")

# Get artist's works
works = requests.get(
    f"{BASE_URL}/library/artists/42/works",
    params={"limit": 24}
).json()

for work in works:
    print(f"  - {work['title']} ({work['recording_count']} recordings)")

# Get work's recordings (matched only)
recordings = requests.get(
    f"{BASE_URL}/library/works/123/recordings",
    params={"status": "matched", "source": "library"}
).json()

for rec in recordings:
    print(f"    - {rec['title']} ({rec['duration']}s)")
```

### JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';

// Get artist detail
const artist = await fetch(`${BASE_URL}/library/artists/42`).then(r => r.json());
console.log(`Artist: ${artist.name} (${artist.work_count} works)`);

// Get artist's works with pagination
const works = await fetch(
  `${BASE_URL}/library/artists/42/works?limit=24`
).then(r => r.json());

works.forEach(work => {
  console.log(`  - ${work.title} (${work.recording_count} recordings)`);
});

// Get work's recordings with filters
const params = new URLSearchParams({
  status: 'matched',
  source: 'library',
  limit: 100
});

const recordings = await fetch(
  `${BASE_URL}/library/works/123/recordings?${params}`
).then(r => r.json());

recordings.forEach(rec => {
  console.log(`    - ${rec.title} (${rec.duration}s)`);
});
```

---

## See Also

- [User Guide](../user-guide/library-navigation.md) - End-user documentation
- [Architecture](../architecture/caching.md) - Caching system design
- [Developer Guide](../developer-guide/extending-navigation.md) - Extending the navigation system
- `recording_count` - Number of recordings for this work

**Status Codes:**
- `200 OK` - Work found
- `404 Not Found` - Work does not exist

**Caching:** 5 minutes (300 seconds)

**Example:**
```bash
curl http://localhost:8000/api/v1/library/works/123
```

---

### 4. List Work's Recordings

Retrieve a paginated and filtered list of recordings for a specific work.

**Endpoint:** `GET /api/v1/library/works/{work_id}/recordings`

**Parameters:**
- `work_id` (path, required) - The unique identifier of the work
- `skip` (query, optional) - Number of records to skip (default: 0)
- `limit` (query, optional) - Maximum number of records to return (default: 100, max: 1000)
- `status` (query, optional) - Filter by verification status: `all`, `matched`, `unmatched` (default: `all`)
- `source` (query, optional) - Filter by source: `all`, `library`, `metadata` (default: `all`)

**Response:** `List[RecordingListItem]`

