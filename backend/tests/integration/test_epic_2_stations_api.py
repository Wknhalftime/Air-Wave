import pytest
from httpx import AsyncClient
from airwave.core.models import Station, BroadcastLog, Recording, Work, Artist
from sqlalchemy import func

@pytest.fixture
async def setup_station_data(db_session):
    """Setup station and logs for API testing."""
    # 1. Create Station
    station = Station(callsign="TEST-FM")
    db_session.add(station)
    await db_session.flush()
    
    # 2. Create Match Target
    artist = Artist(name="matched artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="matched song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="matched song", version_type="Original")
    db_session.add(rec)
    await db_session.flush()
    
    # 3. Create Logs (now link to work, not recording)
    # 3x Matched
    for i in range(3):
        log = BroadcastLog(
            station_id=station.id,
            played_at=func.now(),
            raw_artist="matched artist",
            raw_title="matched song",
            work_id=work.id,
            match_reason="Test Match"
        )
        db_session.add(log)
        
    # 2x Unmatched
    for i in range(2):
        log = BroadcastLog(
            station_id=station.id,
            played_at=func.now(),
            raw_artist="unmatched artist",
            raw_title=f"unmatched song {i}"
        )
        db_session.add(log)
        
    await db_session.commit()
    return station.id

@pytest.mark.asyncio
async def test_stations_list(async_client: AsyncClient, setup_station_data):
    """Test GET /stations list."""
    # Note: async_client fixture usually provided by conftest
    resp = await async_client.get("/api/v1/stations/")
    assert resp.status_code == 200
    data = resp.json()
    
    assert len(data) >= 1
    station_data = next(s for s in data if s["callsign"] == "TEST-FM")
    
    assert station_data["total_logs"] == 5
    assert station_data["matched_logs"] == 3
    assert station_data["match_rate"] == 60.0

@pytest.mark.asyncio
async def test_station_health(async_client: AsyncClient, setup_station_data):
    """Test GET /stations/{id}/health."""
    station_id = setup_station_data
    resp = await async_client.get(f"/api/v1/stations/{station_id}/health")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["station"]["callsign"] == "TEST-FM"
    assert "unmatched_tracks" in data
    
    unmatched = data["unmatched_tracks"]
    # 2 Unmatched entries. If they are distinct, we get 2 rows.
    # In setup I used "unmatched song {i}" so distinct.
    assert len(unmatched) == 2
