import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from airwave.core.models import BroadcastLog, Station, Artist, Work, Recording, IdentityBridge

@pytest.fixture
async def setup_verification_data(db_session):
    """Setup data for verification tests."""
    # Station
    station = Station(callsign="VERIFY-FM")
    db_session.add(station)
    await db_session.flush()

    # Artists
    artist_a = Artist(name="Artist A")
    artist_b = Artist(name="Artist B")
    db_session.add_all([artist_a, artist_b])
    await db_session.flush()

    # Works/Recordings
    work_a = Work(title="Song A", artist_id=artist_a.id)
    work_b = Work(title="Song B", artist_id=artist_b.id)
    db_session.add_all([work_a, work_b])
    await db_session.flush()

    rec_a = Recording(work_id=work_a.id, title="Song A", version_type="Original")
    rec_b = Recording(work_id=work_b.id, title="Song B", version_type="Original")
    db_session.add_all([rec_a, rec_b])
    await db_session.flush()

    # Logs
    # 1. Pending Match (Low Confidence / Variant)
    log_1 = BroadcastLog(
        station_id=station.id,
        played_at=func.now(),
        raw_artist="Artiste A",
        raw_title="Song A",
        recording_id=rec_a.id,
        match_reason="Variant Match (0.85)"
    )
    
    # 2. Another Pending Match (Older)
    import datetime
    older_time = datetime.datetime.now() - datetime.timedelta(hours=1)
    
    log_2 = BroadcastLog(
        station_id=station.id,
        played_at=older_time,
        raw_artist="Artiste B",
        raw_title="Song B",
        recording_id=rec_b.id,
        match_reason="Vector Match (0.2)"
    )

    # 3. Batch candidate (Same artist/title as log_1 but different time)
    log_3 = BroadcastLog(
        station_id=station.id,
        played_at=func.now(),
        raw_artist="Artiste A",
        raw_title="Song A",
        recording_id=rec_a.id,
        match_reason="Variant Match (0.85)"
    )

    db_session.add_all([log_1, log_2, log_3])
    await db_session.commit()
    
    return {
        "log_1_id": log_1.id,
        "log_2_id": log_2.id,
        "log_3_id": log_3.id,
        "station_id": station.id,
        "rec_a_id": rec_a.id
    }

@pytest.mark.asyncio
async def test_verification_queue_order(async_client: AsyncClient, setup_verification_data):
    """Scenario 1: Verify Queue returns items in chronological order (desc)."""
    ids = setup_verification_data
    
    resp = await async_client.get("/api/v1/library/matches/pending")
    assert resp.status_code == 200
    data = resp.json()
    
    # Should have at least 2 items (grouping might merge log_1 and log_3 if logic groups by raw_artist/title)
    # The queue logic in library.py groups by raw_artist, raw_title.
    # So log_1 and log_3 (Artiste A / Song A) should be grouped into ONE item.
    # log_2 is distinct.
    
    assert len(data) >= 2
    
    # Order: Most recent first.
    # log_1/3 is NOW. log_2 is -1 hour.
    # So first item should be Artiste A.
    
    assert data[0]["raw_artist"] == "Artiste A"
    assert data[1]["raw_artist"] == "Artiste B"

@pytest.mark.asyncio
async def test_approval_creates_identity_bridge(async_client: AsyncClient, db_session, setup_verification_data):
    """Scenario 2: Approval creates Identity Bridge."""
    ids = setup_verification_data
    log_id = ids["log_1_id"]
    
    # Approve
    resp = await async_client.post(f"/api/v1/library/matches/{log_id}/verify")
    assert resp.status_code == 200
    
    # Verify Identity Bridge
    # raw: Artiste A / Song A -> rec_a
    stmt = select(IdentityBridge).where(
        IdentityBridge.reference_artist == "Artiste A",
        IdentityBridge.reference_title == "Song A"
    )
    res = await db_session.execute(stmt)
    ib = res.scalar_one_or_none()
    
    assert ib is not None
    assert ib.recording_id == ids["rec_a_id"]
    assert ib.confidence == 1.0

@pytest.mark.asyncio
async def test_batch_approval_updates_all(async_client: AsyncClient, db_session, setup_verification_data):
    """Scenario 4: Batch Verify updates all matching logs."""
    # We use log_3 which is same type as log_1.
    # If we approve log_1 with apply_to_artist=True (or even just batching by logic),
    # verifying log_1 usually verifies specific ID unless logic handles grouping.
    # The API takes log_id.
    # The logic says: "if apply_to_artist: Find all logs with same raw_artist AND matched to a recording by this artist"
    # Wait, the current logic in library.py:
    # "processed_sigs = set()... for target in target_logs..."
    # It updates target.match_reason.
    
    # Let's reset status first if needed, but test isolation should handle it via rollback?
    # No, session fixture usually rolls back. But here we committed in setup.
    # We might need to handle DB state. Tests run in separate transactions if configured right.
    # Assuming standard pytest-asyncio session handling.
    
    ids = setup_verification_data
    log_id = ids["log_1_id"]
    
    resp = await async_client.post(f"/api/v1/library/matches/{log_id}/verify?apply_to_artist=true")
    assert resp.status_code == 200
    
    # Check log_3
    stmt = select(BroadcastLog).where(BroadcastLog.id == ids["log_3_id"])
    res = await db_session.execute(stmt)
    log_3 = res.scalar_one()
    
    assert "Verified" in log_3.match_reason

@pytest.mark.asyncio
async def test_rejection_creates_virtual_recording(async_client: AsyncClient, db_session, setup_verification_data):
    """Scenario 3: Rejection creates Virtual Recording."""
    ids = setup_verification_data
    log_id = ids["log_2_id"] # Artiste B
    
    resp = await async_client.post(f"/api/v1/library/matches/{log_id}/reject")
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["status"] == "rejected"
    assert "new_track_id" in data
    new_id = data["new_track_id"]
    
    # Check Log updated
    stmt = select(BroadcastLog).where(BroadcastLog.id == log_id)
    res = await db_session.execute(stmt)
    log = res.scalar_one()
    
    assert log.recording_id == new_id
    assert "Verified by User (Separate Track)" in log.match_reason
    
    # Check Identity Bridge for NEW track
    # raw: Artiste B / Song B -> new_id
    stmt = select(IdentityBridge).where(
        IdentityBridge.reference_artist == "Artiste B",
        IdentityBridge.recording_id == new_id
    )
    res = await db_session.execute(stmt)
    ib = res.scalar_one_or_none()
    assert ib is not None
