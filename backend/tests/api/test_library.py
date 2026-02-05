from datetime import datetime

import pytest
from airwave.core.models import (
    Artist,
    BroadcastLog,
    IdentityBridge,
    LibraryFile,
    Recording,
    Station,
    Work,
)


@pytest.mark.asyncio
async def test_list_tracks_empty(client):
    """Verify tracks endpoint with empty DB."""
    response = await client.get("/api/v1/library/tracks")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_tracks_with_data(client, db_session):
    """Verify tracks endpoint returns data."""
    # Seed Data
    a = Artist(name="Test Artist")
    db_session.add(a)
    await db_session.flush()

    w = Work(title="Test Title", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()

    r = Recording(work_id=w.id, title="Test Title", version_type="Original")
    db_session.add(r)
    await db_session.flush()

    f = LibraryFile(recording_id=r.id, path="/a.mp3", size=100, format="mp3")
    db_session.add(f)
    await db_session.commit()

    response = await client.get("/api/v1/library/tracks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["artist"] == "Test Artist"
    assert data[0]["title"] == "Test Title"


@pytest.mark.asyncio
async def test_reject_match_creates_new_track(client, db_session):
    """Verify that rejecting a match creates a new virtual track."""
    from sqlalchemy import select

    # 1. Setup Data
    # Station needed for Log FK
    s = Station(callsign="TEST_REJECT", frequency="100.0", city="Test City")
    db_session.add(s)
    await db_session.flush()

    # Existing Recording (Wrong Match)
    a_wrong = Artist(name="Wrong Artist")
    db_session.add(a_wrong)
    await db_session.flush()
    w_wrong = Work(title="Track", artist_id=a_wrong.id)
    db_session.add(w_wrong)
    await db_session.flush()
    r = Recording(work_id=w_wrong.id, title="Track", version_type="Original")
    db_session.add(r)
    await db_session.flush()

    # Log matched to it
    log = BroadcastLog(
        station_id=1,
        raw_artist="New Artist",
        raw_title="New Song",
        played_at=datetime.fromisoformat("2024-01-01T12:00:00"),
        recording_id=r.id,
        match_reason="Wrong Match",
    )
    db_session.add(log)
    await db_session.commit()

    # 2. Call Reject API
    response = await client.post(f"/api/v1/library/matches/{log.id}/reject")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["new_track_id"]

    # 3. Verify DB State
    # A. New Recording Created
    stmt = select(Recording).where(Recording.id == data["new_track_id"])
    res = await db_session.execute(stmt)
    new_track = res.scalar_one_or_none()
    assert new_track

    # B. Log Updated
    await db_session.refresh(log)
    assert log.recording_id == new_track.id
    assert "Verified by User" in log.match_reason

    # C. Identity Bridge Created
    stmt = select(IdentityBridge).where(
        IdentityBridge.recording_id == new_track.id
    )
    res = await db_session.execute(stmt)
    ib = res.scalar_one_or_none()
    assert ib
    assert ib.reference_artist == "New Artist"


@pytest.mark.asyncio
async def test_list_artists(client, db_session):
    """Verify artists endpoint returns aggregated stats."""
    # Seed Data
    a = Artist(name="Stat Artist")
    db_session.add(a)
    await db_session.flush()

    w1 = Work(title="Album 1", artist_id=a.id)
    w2 = Work(title="Album 2", artist_id=a.id)
    db_session.add_all([w1, w2])
    await db_session.flush()

    # w1 has 2 recordings, w2 has 1
    r1 = Recording(work_id=w1.id, title="Track 1", version_type="Original")
    r2 = Recording(work_id=w1.id, title="Track 2", version_type="Remix")
    r3 = Recording(work_id=w2.id, title="Track 3", version_type="Original")
    db_session.add_all([r1, r2, r3])
    await db_session.flush()

    response = await client.get("/api/v1/library/artists?search=Stat Artist")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

    # Find our artist
    stat = next(d for d in data if d["name"] == "Stat Artist")
    assert stat["work_count"] == 2
    assert stat["recording_count"] == 3
    assert stat["avatar_url"] is None
