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
    WorkArtist,
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
        work_id=w_wrong.id,
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

    # B. Log Updated (now linked to new track's work)
    await db_session.refresh(log)
    assert log.work_id == new_track.work_id
    assert "Verified by User" in log.match_reason

    # C. Identity Bridge Created (links to work)
    stmt = select(IdentityBridge).where(
        IdentityBridge.work_id == new_track.work_id
    )
    res = await db_session.execute(stmt)
    ib = res.scalar_one_or_none()
    assert ib
    assert ib.reference_artist == "New Artist"


@pytest.mark.asyncio
async def test_list_artists_no_search(client, db_session):
    """List artists without search returns all (no search filter)."""
    a = Artist(name="NoSearch Artist")
    db_session.add(a)
    await db_session.commit()
    response = await client.get("/api/v1/library/artists")
    assert response.status_code == 200
    data = response.json()
    assert any(d["name"] == "NoSearch Artist" for d in data)


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


@pytest.mark.asyncio
async def test_get_artist(client, db_session):
    """Verify get single artist endpoint."""
    # Seed Data
    a = Artist(name="Single Artist", musicbrainz_id="test-mbid-123")
    db_session.add(a)
    await db_session.flush()

    w = Work(title="Test Work", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()

    r = Recording(work_id=w.id, title="Test Recording")
    db_session.add(r)
    await db_session.commit()

    response = await client.get(f"/api/v1/library/artists/{a.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == a.id
    assert data["name"] == "Single Artist"
    assert data["musicbrainz_id"] == "test-mbid-123"
    assert data["work_count"] == 1
    assert data["recording_count"] == 1


@pytest.mark.asyncio
async def test_get_artist_not_found(client):
    """Verify 404 for non-existent artist."""
    response = await client.get("/api/v1/library/artists/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_artist_works(client, db_session):
    """Verify list works for artist endpoint."""
    # Seed Data
    a = Artist(name="Work Artist")
    db_session.add(a)
    await db_session.flush()

    w1 = Work(title="Work A", artist_id=a.id)
    w2 = Work(title="Work B", artist_id=a.id)
    db_session.add_all([w1, w2])
    await db_session.flush()

    # Add work_artists entries
    wa1 = WorkArtist(work_id=w1.id, artist_id=a.id)
    wa2 = WorkArtist(work_id=w2.id, artist_id=a.id)
    db_session.add_all([wa1, wa2])
    await db_session.flush()

    # Add recordings
    r1 = Recording(work_id=w1.id, title="Recording 1", duration=180.0)
    r2 = Recording(work_id=w1.id, title="Recording 2", duration=200.0)
    r3 = Recording(work_id=w2.id, title="Recording 3", duration=150.0)
    db_session.add_all([r1, r2, r3])
    await db_session.commit()

    response = await client.get(f"/api/v1/library/artists/{a.id}/works")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Check Work A
    work_a = next(w for w in data if w["title"] == "Work A")
    assert work_a["recording_count"] == 2
    assert work_a["duration_total"] == 380.0
    assert "Work Artist" in work_a["artist_names"]


@pytest.mark.asyncio
async def test_list_artist_works_multi_artist(client, db_session):
    """Verify multi-artist works appear correctly."""
    # Seed Data
    a1 = Artist(name="Artist One")
    a2 = Artist(name="Artist Two")
    db_session.add_all([a1, a2])
    await db_session.flush()

    # Collaboration work
    w = Work(title="Collaboration", artist_id=a1.id)
    db_session.add(w)
    await db_session.flush()

    # Add both artists to work_artists
    wa1 = WorkArtist(work_id=w.id, artist_id=a1.id)
    wa2 = WorkArtist(work_id=w.id, artist_id=a2.id)
    db_session.add_all([wa1, wa2])
    await db_session.commit()

    # Query from Artist One's perspective
    response = await client.get(f"/api/v1/library/artists/{a1.id}/works")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "Artist One" in data[0]["artist_names"]
    assert "Artist Two" in data[0]["artist_names"]

    # Query from Artist Two's perspective
    response2 = await client.get(f"/api/v1/library/artists/{a2.id}/works")
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2) == 1
    assert data2[0]["title"] == "Collaboration"


@pytest.mark.asyncio
async def test_get_work(client, db_session):
    """Verify get single work endpoint."""
    # Seed Data
    a = Artist(name="Work Detail Artist")
    db_session.add(a)
    await db_session.flush()

    w = Work(title="Detail Work", artist_id=a.id, is_instrumental=True)
    db_session.add(w)
    await db_session.flush()

    # Add work_artist entry
    wa = WorkArtist(work_id=w.id, artist_id=a.id)
    db_session.add(wa)
    await db_session.flush()

    r = Recording(work_id=w.id, title="Recording")
    db_session.add(r)
    await db_session.commit()

    response = await client.get(f"/api/v1/library/works/{w.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == w.id
    assert data["title"] == "Detail Work"
    assert data["artist_id"] == a.id
    assert data["artist_name"] == "Work Detail Artist"
    assert data["is_instrumental"] is True
    assert data["recording_count"] == 1


@pytest.mark.asyncio
async def test_get_work_not_found(client):
    """Verify 404 for non-existent work."""
    response = await client.get("/api/v1/library/works/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_work_recordings(client, db_session):
    """Verify list recordings for work endpoint."""
    # Seed Data
    a = Artist(name="Recording Artist")
    db_session.add(a)
    await db_session.flush()

    w = Work(title="Recording Work", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()

    # Add work_artist entry
    wa = WorkArtist(work_id=w.id, artist_id=a.id)
    db_session.add(wa)
    await db_session.flush()

    # Add recordings with different statuses
    r1 = Recording(
        work_id=w.id,
        title="Verified Recording",
        duration=180.0,
        is_verified=True,
    )
    r2 = Recording(
        work_id=w.id,
        title="Unverified Recording",
        duration=200.0,
        is_verified=False,
    )
    db_session.add_all([r1, r2])
    await db_session.flush()

    # Add file to r1 only
    f = LibraryFile(recording_id=r1.id, path="/test.mp3", size=1000, format="mp3")
    db_session.add(f)
    await db_session.commit()

    # Test: Get all recordings
    response = await client.get(f"/api/v1/library/works/{w.id}/recordings")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Test: Filter by status=matched
    response = await client.get(
        f"/api/v1/library/works/{w.id}/recordings?status=matched"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Verified Recording"
    assert data[0]["is_verified"] is True

    # Test: Filter by source=library
    response = await client.get(
        f"/api/v1/library/works/{w.id}/recordings?source=library"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["has_file"] is True

    # Test: Filter by source=metadata
    response = await client.get(
        f"/api/v1/library/works/{w.id}/recordings?source=metadata"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["has_file"] is False
