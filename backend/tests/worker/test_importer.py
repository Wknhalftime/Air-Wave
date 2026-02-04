import csv

import pytest
from airwave.core.models import ImportBatch
from airwave.worker.importer import CSVImporter
from sqlalchemy import text


@pytest.fixture
def sample_csv_data():
    return [
        {
            "Station": "KEXP",
            "Date": "01/25/2026",
            "Time": "12:00:00",
            "Artist": "Nirvana",
            "Title": "Smells Like Teen Spirit",
        },
        {
            "Station": "KEXP",
            "Date": "01/25/2026",
            "Time": "12:05:00",
            "Artist": "Pearl Jam",
            "Title": "Alive",
        },
    ]


@pytest.fixture
def sample_csv_data_played_col():
    return [
        {
            "Station": "KNDD",
            "Played": "2026-01-25 12:00:00",
            "Artist": "Foo Fighters",
            "Title": "Everlong",
        },
        {
            "Station": "KNDD",
            "Played": "2026-01-25 12:05:00",
            "Artist": "Soundgarden",
            "Title": "Black Hole Sun",
        },
    ]


@pytest.fixture
def csv_file(tmp_path, sample_csv_data):
    p = tmp_path / "test.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sample_csv_data[0].keys())
        writer.writeheader()
        writer.writerows(sample_csv_data)
    return str(p)


@pytest.mark.asyncio
async def test_import_batch_processing(db_session, csv_file, sample_csv_data):
    # Setup Importer
    importer = CSVImporter(db_session)

    # Test Batched Reading
    chunks = []
    for chunk in importer.read_csv_stream(csv_file, chunk_size=1):
        chunks.append(chunk)

    assert len(chunks) == 2  # 2 rows, chunk_size=1

    # Test Processing
    batch = ImportBatch(filename="test.csv", status="PROCESSING")
    db_session.add(batch)
    await db_session.commit()

    count = await importer.process_batch(batch.id, sample_csv_data)
    assert count == 2

    # Verify DB - Filter by THIS batch to avoid pollution from previous tests (since process_batch commits)
    logs = await db_session.execute(
        text(
            f"SELECT * FROM broadcast_logs JOIN stations ON broadcast_logs.station_id = stations.id WHERE import_batch_id={batch.id}"
        )
    )
    rows = logs.fetchall()
    assert len(rows) == 2

    # Check Station Creation
    station_res = await db_session.execute(
        text("SELECT * FROM stations WHERE callsign='KEXP'")
    )
    station = station_res.fetchone()
    assert station is not None


@pytest.mark.asyncio
async def test_import_played_column(db_session, sample_csv_data_played_col):
    """Test importing data with 'Played' column instead of Date/Time."""
    importer = CSVImporter(db_session)
    batch = ImportBatch(filename="test_played.csv", status="PROCESSING")
    db_session.add(batch)
    await db_session.commit()
    # Capture ID
    batch_id = batch.id

    count = await importer.process_batch(batch_id, sample_csv_data_played_col)
    assert count == 2

    # Verify Data
    res = await db_session.execute(
        text(
            f"SELECT played_at FROM broadcast_logs WHERE import_batch_id={batch_id} ORDER BY played_at"
        )
    )
    rows = res.fetchall()
    assert len(rows) == 2
    # Verify timestamp parsing (Handle optional microseconds from DB)
    ts_str = str(rows[0][0])
    if "." in ts_str:
        ts_str = ts_str.split(".")[0]
    assert ts_str == "2026-01-25 12:00:00"


@pytest.mark.asyncio
async def test_import_large_batch_internal_chunking(db_session):
    """Test that process_batch handles a list larger than the SQLite variable limit safely."""
    importer = CSVImporter(db_session)
    batch = ImportBatch(filename="large.csv", status="PROCESSING")
    db_session.add(batch)
    await db_session.commit()
    batch_id = batch.id

    # Generate 500 rows (more than the internal 400 limit, but within safety for this test speed)
    large_data = []
    for i in range(500):
        large_data.append(
            {
                "Station": "TEST",
                "Date": "01/01/2026",
                "Time": "12:00:00",
                "Artist": f"Artist {i}",
                "Title": f"Title {i}",
            }
        )

    count = await importer.process_batch(batch_id, large_data)
    assert count == 500

    # Verify count in DB
    res = await db_session.execute(
        text(
            f"SELECT count(*) FROM broadcast_logs WHERE import_batch_id={batch_id}"
        )
    )
    assert res.scalar() == 500
