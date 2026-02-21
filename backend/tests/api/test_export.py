"""Tests for export endpoints (CSV logs, M3U playlist)."""

from datetime import datetime

import pytest
from airwave.core.models import (
    Artist,
    BroadcastLog,
    ImportBatch,
    LibraryFile,
    Recording,
    Station,
    Work,
)


@pytest.mark.asyncio
async def test_export_m3u_empty(client, db_session):
    """No matched logs returns M3U with only header."""
    s = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    db_session.add(s)
    await db_session.flush()
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=0, processed_rows=0)
    db_session.add(batch)
    await db_session.flush()
    log = BroadcastLog(
        station_id=s.id,
        played_at=datetime(2025, 1, 15, 12, 0, 0),
        raw_artist="Unknown",
        raw_title="Unknown",
        work_id=None,
        import_batch_id=batch.id,
    )
    db_session.add(log)
    await db_session.commit()

    response = await client.get("/api/v1/export/m3u")
    assert response.status_code == 200
    text = response.text
    assert text.strip() == "#EXTM3U"
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert ".m3u" in response.headers.get("Content-Disposition", "")


@pytest.mark.asyncio
async def test_export_m3u_basic(client, db_session):
    """Matched logs with library files produce valid M3U with absolute paths."""
    s = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    db_session.add(s)
    await db_session.flush()
    a = Artist(name="The Beatles")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="Hey Jude", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="Hey Jude", version_type="Original", duration=431.0)
    db_session.add(r)
    await db_session.flush()
    # Use absolute path so we don't depend on DATA_DIR
    lib_path = "/music/The Beatles/1967-1970/08 Hey Jude.mp3"
    f = LibraryFile(recording_id=r.id, path=lib_path)
    db_session.add(f)
    await db_session.flush()
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=1, processed_rows=1)
    db_session.add(batch)
    await db_session.flush()
    log = BroadcastLog(
        station_id=s.id,
        played_at=datetime(2025, 1, 15, 12, 0, 0),
        raw_artist="The Beatles",
        raw_title="Hey Jude",
        work_id=w.id,
        import_batch_id=batch.id,
        match_reason="identity_bridge",
    )
    db_session.add(log)
    await db_session.commit()

    response = await client.get("/api/v1/export/m3u")
    assert response.status_code == 200
    text = response.text
    assert text.startswith("#EXTM3U\n")
    assert "#EXTINF:" in text
    assert "The Beatles - Hey Jude" in text
    assert "Hey Jude.mp3" in text
    assert response.headers.get("X-Airwave-M3U-Included") == "1"
    assert response.headers.get("X-Airwave-M3U-Skipped") == "0"


@pytest.mark.asyncio
async def test_export_m3u_chronological_order(client, db_session):
    """Tracks are ordered by played_at ASC."""
    s = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    db_session.add(s)
    await db_session.flush()
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=2, processed_rows=2)
    db_session.add(batch)
    await db_session.flush()

    a1 = Artist(name="First")
    db_session.add(a1)
    await db_session.flush()
    w1 = Work(title="First Song", artist_id=a1.id)
    db_session.add(w1)
    await db_session.flush()
    r1 = Recording(work_id=w1.id, title="First Song", version_type="Original")
    db_session.add(r1)
    await db_session.flush()
    db_session.add(LibraryFile(recording_id=r1.id, path="/first.mp3"))
    await db_session.flush()

    a2 = Artist(name="Second")
    db_session.add(a2)
    await db_session.flush()
    w2 = Work(title="Second Song", artist_id=a2.id)
    db_session.add(w2)
    await db_session.flush()
    r2 = Recording(work_id=w2.id, title="Second Song", version_type="Original")
    db_session.add(r2)
    await db_session.flush()
    db_session.add(LibraryFile(recording_id=r2.id, path="/second.mp3"))
    await db_session.flush()

    log1 = BroadcastLog(
        station_id=s.id,
        played_at=datetime(2025, 1, 15, 14, 0, 0),
        raw_artist="Second",
        raw_title="Second Song",
        work_id=w2.id,
        import_batch_id=batch.id,
    )
    log2 = BroadcastLog(
        station_id=s.id,
        played_at=datetime(2025, 1, 15, 12, 0, 0),
        raw_artist="First",
        raw_title="First Song",
        work_id=w1.id,
        import_batch_id=batch.id,
    )
    db_session.add(log1)
    db_session.add(log2)
    await db_session.commit()

    response = await client.get("/api/v1/export/m3u")
    assert response.status_code == 200
    text = response.text
    # First Song (12:00) should appear before Second Song (14:00)
    idx_first = text.index("First Song")
    idx_second = text.index("Second Song")
    assert idx_first < idx_second


@pytest.mark.asyncio
async def test_export_m3u_filter_by_station(client, db_session):
    """station_id filter limits results."""
    s1 = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    s2 = Station(callsign="KAWR", frequency="88.1", city="Other")
    db_session.add_all([s1, s2])
    await db_session.flush()
    a = Artist(name="Artist")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="Title", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="Title", version_type="Original")
    db_session.add(r)
    await db_session.flush()
    db_session.add(LibraryFile(recording_id=r.id, path="/track.mp3"))
    await db_session.flush()
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=2, processed_rows=2)
    db_session.add(batch)
    await db_session.flush()

    log1 = BroadcastLog(
        station_id=s1.id,
        played_at=datetime(2025, 1, 15, 12, 0, 0),
        raw_artist="Artist",
        raw_title="Title",
        work_id=w.id,
        import_batch_id=batch.id,
    )
    log2 = BroadcastLog(
        station_id=s2.id,
        played_at=datetime(2025, 1, 15, 13, 0, 0),
        raw_artist="Artist",
        raw_title="Title",
        work_id=w.id,
        import_batch_id=batch.id,
    )
    db_session.add_all([log1, log2])
    await db_session.commit()

    response = await client.get(f"/api/v1/export/m3u?station_id={s1.id}")
    assert response.status_code == 200
    text = response.text
    # Should have exactly one #EXTINF (one track from s1)
    assert text.count("#EXTINF:") == 1


@pytest.mark.asyncio
async def test_export_m3u_recording_with_no_library_files_skipped(client, db_session):
    """Logs whose recording has no library files are skipped."""
    s = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    db_session.add(s)
    await db_session.flush()
    a = Artist(name="NoFile")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="No File Song", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="No File Song", version_type="Original")
    db_session.add(r)
    await db_session.flush()
    # No LibraryFile added
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=1, processed_rows=1)
    db_session.add(batch)
    await db_session.flush()
    log = BroadcastLog(
        station_id=s.id,
        played_at=datetime(2025, 1, 15, 12, 0, 0),
        raw_artist="NoFile",
        raw_title="No File Song",
        work_id=w.id,
        import_batch_id=batch.id,
    )
    db_session.add(log)
    await db_session.commit()

    response = await client.get("/api/v1/export/m3u")
    assert response.status_code == 200
    text = response.text
    assert text.strip() == "#EXTM3U"
    assert "NoFile" not in text


@pytest.mark.asyncio
async def test_export_m3u_invalid_date_returns_400(client):
    """Invalid start_date returns 400."""
    response = await client.get("/api/v1/export/m3u?start_date=not-a-date")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_export_m3u_multiple_files_uses_first(client, db_session):
    """Recording with multiple library files: only first is included."""
    s = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    db_session.add(s)
    await db_session.flush()
    a = Artist(name="Multi")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="Multi", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="Multi", version_type="Original")
    db_session.add(r)
    await db_session.flush()
    db_session.add(LibraryFile(recording_id=r.id, path="/first.mp3"))
    db_session.add(LibraryFile(recording_id=r.id, path="/second.flac"))
    await db_session.flush()
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=1, processed_rows=1)
    db_session.add(batch)
    await db_session.flush()
    log = BroadcastLog(
        station_id=s.id,
        played_at=datetime(2025, 1, 15, 12, 0, 0),
        raw_artist="Multi",
        raw_title="Multi",
        work_id=w.id,
        import_batch_id=batch.id,
    )
    db_session.add(log)
    await db_session.commit()

    response = await client.get("/api/v1/export/m3u")
    assert response.status_code == 200
    text = response.text
    assert text.count("#EXTINF:") == 1
    # First file should appear; path may be normalized on Windows (e.g. D:\first.mp3)
    path_lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    assert len(path_lines) == 1
    assert "first.mp3" in path_lines[0] or "second.flac" in path_lines[0]


@pytest.mark.asyncio
async def test_export_m3u_filter_by_date_range(client, db_session):
    """Only logs within start_date and end_date are included."""
    s = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    db_session.add(s)
    await db_session.flush()
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=3, processed_rows=3)
    db_session.add(batch)
    await db_session.flush()
    a = Artist(name="Artist")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="Track", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="Track", version_type="Original")
    db_session.add(r)
    await db_session.flush()
    db_session.add(LibraryFile(recording_id=r.id, path="/track.mp3"))
    await db_session.flush()

    # Logs: 2025-01-10, 2025-01-15, 2025-01-20
    for day in [10, 15, 20]:
        log = BroadcastLog(
            station_id=s.id,
            played_at=datetime(2025, 1, day, 12, 0, 0),
            raw_artist="Artist",
            raw_title="Track",
            work_id=w.id,
            import_batch_id=batch.id,
        )
        db_session.add(log)
    await db_session.commit()

    # Filter 2025-01-12 to 2025-01-18 -> only day 15
    response = await client.get(
        "/api/v1/export/m3u?start_date=2025-01-12&end_date=2025-01-18"
    )
    assert response.status_code == 200
    assert response.text.count("#EXTINF:") == 1


@pytest.mark.asyncio
async def test_export_m3u_relative_path_resolved_to_absolute(client, db_session, monkeypatch):
    """Relative library file path is resolved using DATA_DIR to absolute in M3U."""
    from pathlib import Path
    import airwave.api.routers.export as export_router
    fake_base = Path("/fake/airwave/data").resolve()
    monkeypatch.setattr(export_router.settings, "DATA_DIR", fake_base)

    s = Station(callsign="KEXP", frequency="90.3", city="Seattle")
    db_session.add(s)
    await db_session.flush()
    a = Artist(name="Artist")
    db_session.add(a)
    await db_session.flush()
    w = Work(title="Title", artist_id=a.id)
    db_session.add(w)
    await db_session.flush()
    r = Recording(work_id=w.id, title="Title", version_type="Original")
    db_session.add(r)
    await db_session.flush()
    db_session.add(LibraryFile(recording_id=r.id, path="music/artist/track.mp3"))
    await db_session.flush()
    batch = ImportBatch(filename="test.csv", status="COMPLETED", total_rows=1, processed_rows=1)
    db_session.add(batch)
    await db_session.flush()
    log = BroadcastLog(
        station_id=s.id,
        played_at=datetime(2025, 1, 15, 12, 0, 0),
        raw_artist="Artist",
        raw_title="Title",
        work_id=w.id,
        import_batch_id=batch.id,
    )
    db_session.add(log)
    await db_session.commit()

    response = await client.get("/api/v1/export/m3u")
    assert response.status_code == 200
    path_lines = [ln for ln in response.text.splitlines() if ln and not ln.startswith("#")]
    assert len(path_lines) == 1
    abs_path = path_lines[0]
    assert Path(abs_path).is_absolute()
    assert "track.mp3" in abs_path
