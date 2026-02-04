from datetime import datetime

import pytest
from airwave.core.models import Artist, BroadcastLog, Recording, Station, Work


@pytest.mark.asyncio
async def test_get_dashboard_stats(client, db_session):
    # Setup
    s = Station(callsign="TEST")
    db_session.add(s)
    await db_session.flush()

    log = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="B",
        played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
    )
    db_session.add(log)
    await db_session.commit()

    response = await client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "total_plays" in data
    assert data["total_plays"] == 1
    assert data["active_stations"] == 1


@pytest.mark.asyncio
async def test_history_list(client, db_session):
    # Setup
    s = Station(callsign="TEST_HISTORY")
    db_session.add(s)
    await db_session.flush()

    log = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="B",
        played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
    )
    db_session.add(log)
    await db_session.commit()

    response = await client.get("/api/v1/history/logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["raw_artist"] == "A"


@pytest.mark.asyncio
async def test_get_top_tracks(client, db_session):
    # Setup: 1 Station, 1 Artist, 1 Work, 1 Recording, 2 Logs
    s = Station(callsign="TEST_TOP")
    db_session.add(s)

    a = Artist(name="Top Artist")
    db_session.add(a)
    await db_session.flush()

    w = Work(title="Top Song", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()

    r = Recording(work_id=w.id, title="Top Song", version_type="Original")
    db_session.add(r)
    await db_session.flush()

    # 2 Logs for this recording
    log1 = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="B",
        played_at=datetime.now(),
        recording_id=r.id,
    )
    log2 = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="B",
        played_at=datetime.now(),
        recording_id=r.id,
    )
    db_session.add_all([log1, log2])
    await db_session.commit()

    response = await client.get("/api/v1/analytics/top-tracks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["artist"] == "Top Artist"
    assert data[0]["title"] == "Top Song"
    assert data[0]["count"] == 2
