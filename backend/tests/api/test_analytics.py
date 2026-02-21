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
async def test_history_logs_with_station_id(client, db_session):
    """History logs filtered by station_id."""
    s1 = Station(callsign="H1")
    s2 = Station(callsign="H2")
    db_session.add_all([s1, s2])
    await db_session.flush()
    log1 = BroadcastLog(
        station_id=s1.id,
        raw_artist="A1",
        raw_title="T1",
        played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
    )
    log2 = BroadcastLog(
        station_id=s2.id,
        raw_artist="A2",
        raw_title="T2",
        played_at=datetime.fromisoformat("2024-01-01T11:00:00"),
    )
    db_session.add_all([log1, log2])
    await db_session.commit()
    response = await client.get("/api/v1/history/logs", params={"station_id": s1.id})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["raw_artist"] == "A1"


@pytest.mark.asyncio
async def test_history_logs_with_date(client, db_session):
    """History logs filtered by date (chronological order)."""
    s = Station(callsign="HD")
    db_session.add(s)
    await db_session.flush()
    log1 = BroadcastLog(
        station_id=s.id,
        raw_artist="Early",
        raw_title="T1",
        played_at=datetime.fromisoformat("2024-06-15T09:00:00"),
    )
    log2 = BroadcastLog(
        station_id=s.id,
        raw_artist="Late",
        raw_title="T2",
        played_at=datetime.fromisoformat("2024-06-15T14:00:00"),
    )
    db_session.add_all([log1, log2])
    await db_session.commit()
    response = await client.get("/api/v1/history/logs", params={"date": "2024-06-15"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["raw_artist"] == "Early"
    assert data[1]["raw_artist"] == "Late"


@pytest.mark.asyncio
async def test_history_logs_invalid_date_ignored(client, db_session):
    """Invalid date parameter does not filter (ValueError caught)."""
    s = Station(callsign="HI")
    db_session.add(s)
    await db_session.flush()
    log = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="T",
        played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
    )
    db_session.add(log)
    await db_session.commit()
    response = await client.get("/api/v1/history/logs", params={"date": "not-a-date"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


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

    # 2 Logs for this recording (link to work)
    log1 = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="B",
        played_at=datetime.now(),
        work_id=w.id,
    )
    log2 = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="B",
        played_at=datetime.now(),
        work_id=w.id,
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


@pytest.mark.asyncio
async def test_get_top_artists(client, db_session):
    """Top artists endpoint returns play counts by artist."""
    s = Station(callsign="TA")
    db_session.add(s)
    a = Artist(name="Top Artist")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="Song", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="Song", version_type="Original")
    db_session.add(r)
    await db_session.flush()
    for _ in range(3):
        log = BroadcastLog(
            station_id=s.id,
            raw_artist="A",
            raw_title="T",
            played_at=datetime.now(),
            work_id=w.id,
        )
        db_session.add(log)
    await db_session.commit()
    response = await client.get("/api/v1/analytics/top-artists")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Top Artist"
    assert data[0]["count"] == 3


@pytest.mark.asyncio
async def test_get_daily_activity(client, db_session):
    """Daily activity returns play counts per day."""
    s = Station(callsign="DA")
    db_session.add(s)
    await db_session.flush()
    log = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="T",
        played_at=datetime.fromisoformat("2024-06-10T12:00:00"),
    )
    db_session.add(log)
    await db_session.commit()
    response = await client.get("/api/v1/analytics/daily-activity", params={"days": 7})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_victory_stats(client, db_session):
    """Victory stats returns match rate and breakdown."""
    s = Station(callsign="VS")
    db_session.add(s)
    await db_session.flush()
    a = Artist(name="V")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="W", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="W", version_type="Original")
    db_session.add(r)
    await db_session.flush()
    log_matched = BroadcastLog(
        station_id=s.id,
        raw_artist="A",
        raw_title="T",
        played_at=datetime.now(),
        work_id=w.id,
        match_reason="Identity Bridge (Exact Match)",
    )
    log_unmatched = BroadcastLog(
        station_id=s.id,
        raw_artist="Unknown",
        raw_title="Unknown",
        played_at=datetime.now(),
    )
    db_session.add_all([log_matched, log_unmatched])
    await db_session.commit()
    response = await client.get("/api/v1/analytics/victory")
    assert response.status_code == 200
    data = response.json()
    assert data["total_logs"] == 2
    assert data["matched_logs"] == 1
    assert data["unmatched_logs"] == 1
    assert data["match_rate"] == 50.0
    assert "breakdown" in data
    assert "summary" in data
