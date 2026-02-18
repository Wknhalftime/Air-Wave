import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from airwave.core.models import Station, BroadcastLog, ImportBatch, Recording, Work
from airwave.core.db import get_db

@pytest.mark.asyncio
async def test_list_stations(async_client: AsyncClient, db_session: AsyncSession):
    # Setup: Create stations and logs
    station1 = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    station2 = Station(callsign="KCRW", frequency="89.9", city="Santa Monica")
    db_session.add_all([station1, station2])
    await db_session.commit()
    await db_session.refresh(station1)
    await db_session.refresh(station2)
    
    # Create logs for station1 (1 matched, 1 unmatched)
    # We need a recording to match against
    work = Work(title="Test Work")
    recording = Recording(work=work, title="Test Rec")
    db_session.add_all([work, recording])
    await db_session.commit()
    await db_session.refresh(recording)
    
    from datetime import datetime
    
    log1 = BroadcastLog(
        station_id=station1.id, 
        played_at=datetime.fromisoformat("2023-01-01 10:00:00"), 
        raw_artist="Artist", 
        raw_title="Title",
        recording_id=recording.id
    )
    log2 = BroadcastLog(
        station_id=station1.id, 
        played_at=datetime.fromisoformat("2023-01-01 11:00:00"), 
        raw_artist="Artist", 
        raw_title="Unknown"
    )
    db_session.add_all([log1, log2])
    await db_session.commit()
    
    # Test
    response = await async_client.get("/api/v1/stations/")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) >= 2
    
    kexp = next(s for s in data if s["callsign"] == "KEXP")
    assert kexp["total_logs"] == 2
    assert kexp["matched_logs"] == 1
    assert kexp["match_rate"] == 50.0

@pytest.mark.asyncio
async def test_get_station_health(async_client: AsyncClient, db_session: AsyncSession):
    # Setup
    station = Station(callsign="WFMU", frequency="91.1", city="Jersey City")
    db_session.add(station)
    await db_session.commit()
    await db_session.refresh(station)
    
    # Create a batch
    batch = ImportBatch(filename="wfmu_log.txt", status="COMPLETED")
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)
    
    from datetime import datetime

    # Add logs linked to batch and station
    log_unmatched = BroadcastLog(
        station_id=station.id,
        import_batch_id=batch.id,
        played_at=datetime.fromisoformat("2023-01-02 10:00:00"),
        raw_artist="Unmatched Artist",
        raw_title="Unmatched Title"
    )
    db_session.add(log_unmatched)
    await db_session.commit()
    
    # Test
    response = await async_client.get(f"/api/v1/stations/{station.id}/health")
    assert response.status_code == 200
    data = response.json()
    
    assert data["station"]["callsign"] == "WFMU"
    
    # Check recent batches
    assert len(data["recent_batches"]) == 1
    assert data["recent_batches"][0]["filename"] == "wfmu_log.txt"
    assert data["recent_batches"][0]["total"] == 1
    assert data["recent_batches"][0]["match_rate"] == 0.0
    
    # Check unmatched tracks
    assert len(data["unmatched_tracks"]) == 1
    assert data["unmatched_tracks"][0]["artist"] == "Unmatched Artist"
    assert data["unmatched_tracks"][0]["count"] == 1


@pytest.mark.asyncio
async def test_get_station_health_not_found(async_client: AsyncClient, db_session: AsyncSession):
    """Station health for invalid id returns 404."""
    response = await async_client.get("/api/v1/stations/99999/health")
    assert response.status_code == 404
    assert "Station not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_stations_empty_logs(async_client: AsyncClient, db_session: AsyncSession):
    """Station with no logs has match_rate 0."""
    station = Station(callsign="NOLOGS", frequency="88.0", city="Nowhere")
    db_session.add(station)
    await db_session.commit()
    response = await async_client.get("/api/v1/stations/")
    assert response.status_code == 200
    data = response.json()
    nologs = next(s for s in data if s["callsign"] == "NOLOGS")
    assert nologs["total_logs"] == 0
    assert nologs["matched_logs"] == 0
    assert nologs["match_rate"] == 0.0
