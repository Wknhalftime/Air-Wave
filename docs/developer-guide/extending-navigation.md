# Extending the Library Navigation System

This guide explains how to extend the library navigation system with new features, endpoints, and UI components.

## Table of Contents

1. [Adding New API Endpoints](#adding-new-api-endpoints)
2. [Adding Caching to Endpoints](#adding-caching-to-endpoints)
3. [Creating New Frontend Components](#creating-new-frontend-components)
4. [Adding New Filters](#adding-new-filters)
5. [Testing Your Changes](#testing-your-changes)

---

## Adding New API Endpoints

### Step 1: Define Response Schema

Create a Pydantic model in `backend/src/airwave/api/schemas/library.py`:

```python
from pydantic import BaseModel, ConfigDict

class RecordingDetail(BaseModel):
    """Detailed recording information"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    artist_display: str
    duration: int | None
    version_type: str | None
    is_verified: bool
    has_file: bool
    # Add new fields here
    file_path: str | None
    file_format: str | None
    bitrate: int | None
```

### Step 2: Create Database Query Function

Add a query function in `backend/src/airwave/api/routers/library.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_recording(
    db: AsyncSession,
    recording_id: int
) -> RecordingDetail | None:
    """Get detailed recording information"""
    
    # Build query
    stmt = (
        select(Recording)
        .where(Recording.id == recording_id)
    )
    
    # Execute query
    result = await db.execute(stmt)
    recording = result.scalar_one_or_none()
    
    if not recording:
        return None
    
    # Return schema
    return RecordingDetail.model_validate(recording)
```

### Step 3: Create API Endpoint

Add the endpoint to the router:

```python
from fastapi import APIRouter, Depends, HTTPException
from airwave.core.cache import cached

router = APIRouter()

@router.get("/recordings/{recording_id}", response_model=RecordingDetail)
@cached(ttl=300)  # 5 minutes
async def get_recording_detail(
    recording_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a recording"""
    
    recording = await get_recording(db, recording_id)
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    return recording
```

### Step 4: Add Tests

Create tests in `backend/tests/api/test_library.py`:

```python
@pytest.mark.asyncio
async def test_get_recording(client, db_session):
    # Setup: Create test data
    artist = Artist(name="Test Artist")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Test Work", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    recording = Recording(
        title="Test Recording",
        work_id=work.id,
        duration=180,
        is_verified=True
    )
    db_session.add(recording)
    await db_session.commit()
    
    # Test: Get recording
    response = await client.get(f"/api/v1/library/recordings/{recording.id}")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == recording.id
    assert data["title"] == "Test Recording"
    assert data["duration"] == 180
    assert data["is_verified"] is True
```

---

## Adding Caching to Endpoints

### Using the @cached Decorator

The simplest way to add caching is using the `@cached` decorator:

```python
from airwave.core.cache import cached

@router.get("/artists/{artist_id}")
@cached(ttl=300)  # Cache for 5 minutes
async def get_artist(artist_id: int, db: AsyncSession = Depends(get_db)):
    # Your endpoint logic here
    pass
```

### Choosing the Right TTL

Use these guidelines:

| Data Type | TTL | Example |
|-----------|-----|---------|
| Static metadata | 300s (5 min) | Artist/Work details |
| Dynamic lists | 180s (3 min) | Work lists, recording lists |
| User-specific data | 120s (2 min) | Filtered results |
| Real-time data | 60s (1 min) | Playback status |

### Custom Cache Keys

For more control over cache keys:

```python
from airwave.core.cache import cache

@router.get("/artists/{artist_id}/works")
async def list_works(
    artist_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    # Generate custom cache key
    cache_key = f"artist_works:{artist_id}:{skip}:{limit}"
    
    # Check cache
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Fetch from database
    result = await fetch_works(db, artist_id, skip, limit)
    
    # Store in cache
    cache.set(cache_key, result, ttl=180)
    
    return result
```

### Cache Invalidation

Invalidate cache when data changes:

```python
from airwave.core.cache import cache

@router.post("/artists/{artist_id}")
async def update_artist(
    artist_id: int,
    data: ArtistUpdate,
    db: AsyncSession = Depends(get_db)
):
    # Update artist
    await update_artist_in_db(db, artist_id, data)
    
    # Invalidate related cache entries
    cache.delete(f"get_artist:{artist_id}")
    cache.delete(f"list_artist_works:{artist_id}:*")  # Pattern matching (future)
    
    return {"status": "ok"}
```

---

## Creating New Frontend Components

### Step 1: Define TypeScript Interface

Add interface to `frontend/src/hooks/useLibrary.ts`:

```typescript
export interface RecordingDetail {
  id: number;
  title: string;
  artist_display: string;
  duration: number | null;
  version_type: string | null;
  is_verified: boolean;
  has_file: boolean;
  file_path: string | null;
  file_format: string | null;
  bitrate: number | null;
}
```

### Step 2: Create React Query Hook

Add hook to `frontend/src/hooks/useLibrary.ts`:

```typescript
export function useRecording(recordingId: number) {
  return useQuery<RecordingDetail>({
    queryKey: ['recording', recordingId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/library/recordings/${recordingId}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch recording');
      }
      return response.json();
    },
  });
}
```

### Step 3: Create Component

Create `frontend/src/pages/RecordingDetail.tsx`:

```typescript
import { useParams } from 'react-router-dom';
import { useRecording } from '../hooks/useLibrary';

export default function RecordingDetail() {
  const { id } = useParams<{ id: string }>();
  const recordingId = parseInt(id || '0', 10);
  
  const { data: recording, isLoading, error } = useRecording(recordingId);
  
  if (isLoading) {
    return <div>Loading...</div>;
  }
  
  if (error || !recording) {
    return <div>Recording not found</div>;
  }
  
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-4">{recording.title}</h1>
      <p className="text-gray-600">{recording.artist_display}</p>
      
      <div className="mt-6 grid grid-cols-2 gap-4">
        <div>
          <span className="font-semibold">Duration:</span>{' '}
          {recording.duration ? `${Math.floor(recording.duration / 60)}:${(recording.duration % 60).toString().padStart(2, '0')}` : 'Unknown'}
        </div>
        <div>
          <span className="font-semibold">Version:</span>{' '}
          {recording.version_type || 'Unknown'}
        </div>
        <div>
          <span className="font-semibold">Status:</span>{' '}
          {recording.is_verified ? 'Matched' : 'Unmatched'}
        </div>
        <div>
          <span className="font-semibold">Source:</span>{' '}
          {recording.has_file ? 'Library' : 'Metadata'}
        </div>
      </div>
    </div>
  );
}
```

### Step 4: Add Route

Update `frontend/src/App.tsx`:

```typescript
import RecordingDetail from './pages/RecordingDetail';

// In your Routes component:
<Route path="/library/recordings/:id" element={<RecordingDetail />} />
```

---

## Adding New Filters

### Backend: Add Filter Parameter

Update the endpoint to accept new filter:

```python
from enum import Enum

class RecordingFormat(str, Enum):
    ALL = "all"
    FLAC = "flac"
    MP3 = "mp3"
    AAC = "aac"

@router.get("/works/{work_id}/recordings")
async def list_recordings(
    work_id: int,
    status: RecordingStatus = RecordingStatus.ALL,
    source: RecordingSource = RecordingSource.ALL,
    format: RecordingFormat = RecordingFormat.ALL,  # New filter
    db: AsyncSession = Depends(get_db)
):
    # Build query with new filter
    stmt = select(Recording).where(Recording.work_id == work_id)
    
    if format != RecordingFormat.ALL:
        stmt = stmt.join(LibraryFile).where(
            LibraryFile.path.like(f"%.{format.value}")
        )
    
    # ... rest of query
```

### Frontend: Add Filter Control

Update `frontend/src/pages/WorkDetail.tsx`:

```typescript
const [formatFilter, setFormatFilter] = useState<string>('all');

// In your component JSX:
<select
  value={formatFilter}
  onChange={(e) => setFormatFilter(e.target.value)}
  className="px-4 py-2 border border-gray-300 rounded-lg"
>
  <option value="all">All Formats</option>
  <option value="flac">FLAC</option>
  <option value="mp3">MP3</option>
  <option value="aac">AAC</option>
</select>

// Update query hook:
const { data: recordings } = useWorkRecordings(
  workId,
  page,
  statusFilter,
  sourceFilter,
  formatFilter  // Pass new filter
);
```

---

## Testing Your Changes

### Backend Tests

```python
@pytest.mark.asyncio
async def test_new_endpoint(client, db_session):
    # 1. Setup test data
    # 2. Call endpoint
    # 3. Assert response
    pass

@pytest.mark.asyncio
async def test_new_filter(client, db_session):
    # 1. Create recordings with different formats
    # 2. Test filter returns correct results
    # 3. Test filter combinations
    pass
```

### Frontend Tests

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import RecordingDetail from './RecordingDetail';

describe('RecordingDetail', () => {
  it('renders recording information', () => {
    render(<RecordingDetail />);
    expect(screen.getByText('Test Recording')).toBeInTheDocument();
  });
});
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_navigation_with_new_feature(client, db_session):
    # Test complete user journey including new feature
    pass
```

---

## Best Practices

1. **Always add caching** to new endpoints
2. **Write tests** for all new code
3. **Document** new endpoints in API docs
4. **Use TypeScript** for type safety
5. **Follow existing patterns** for consistency
6. **Optimize queries** to avoid N+1 problems
7. **Handle errors** gracefully
8. **Add loading states** to UI components

---

## See Also

- [API Documentation](../api/library-navigation.md)
- [Architecture](../architecture/caching.md)
- [Testing Guide](../testing/integration-tests.md)

