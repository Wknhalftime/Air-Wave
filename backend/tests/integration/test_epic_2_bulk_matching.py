import pytest
import csv
from pathlib import Path
from airwave.worker.importer import CSVImporter
from airwave.core.models import BroadcastLog, Artist, Work, Recording, Station
from airwave.core.vector_db import VectorDB
from sqlalchemy import select

@pytest.fixture
async def setup_bulk_library(db_session):
    """Setup a library for bulk matching."""
    # 1. Exact Match Target
    beatles = Artist(name="the beatles")
    db_session.add(beatles)
    await db_session.flush()
    jude_work = Work(title="hey jude", artist_id=beatles.id)
    db_session.add(jude_work)
    await db_session.flush()
    jude_rec = Recording(work_id=jude_work.id, title="hey jude", version_type="Original")
    db_session.add(jude_rec)

    # 2. Vector Match Target (e.g. Queen)
    queen = Artist(name="queen")
    db_session.add(queen)
    await db_session.flush()
    boh_work = Work(title="bohemian rhapsody", artist_id=queen.id)
    db_session.add(boh_work)
    await db_session.flush()
    boh_rec = Recording(work_id=boh_work.id, title="bohemian rhapsody", version_type="Original")
    db_session.add(boh_rec)
    
    await db_session.commit()
    
    # Add to Vector DB for fuzzy/vector matching
    # Note: We must ensure VectorDB uses a temp path or safe path?
    # conftest usually handles persistence path? 
    # If VectorDB is singleton, it might reuse existing.
    # We should add tracks explicitly.
    vdb = VectorDB()
    vdb.add_track(jude_rec.id, "the beatles", "hey jude")
    vdb.add_track(boh_rec.id, "queen", "bohemian rhapsody")
    
    return {
        "jude_id": jude_rec.id,
        "boh_id": boh_rec.id
    }

@pytest.mark.asyncio
async def test_bulk_import_matching(db_session, setup_bulk_library, tmp_path):
    """Test full bulk import capability with matching."""
    ids = setup_bulk_library
    
    # Create Dummy CSV
    csv_path = tmp_path / "test_logs.csv"
    headers = ["Date", "Time", "Station", "Artist", "Title"]
    rows = [
        ["2023-10-27", "10:00:00", "WXYZ", "The Beatles", "Hey Jude"],        # Exact Match
        ["2023-10-27", "10:05:00", "WXYZ", "Queen", "Bohemian Raphsody"],     # Typos (Vector) - 'Raphsody'
        ["2023-10-27", "10:10:00", "WXYZ", "Unknown Artiste", "Unknown Song"] # No Match
    ]
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
        
    # Run Importer
    importer = CSVImporter(db_session)
    
    # We need to manually iterate generator as importer.read_csv_stream is sync/generator logic
    # But read_csv_stream can be called directly.
    
    batch_id = 999 
    processed_count = 0
    
    # Use str(csv_path) for compatibility
    for chunk in importer.read_csv_stream(str(csv_path), chunk_size=100):
        count = await importer.process_batch(batch_id, chunk, default_station="WXYZ")
        processed_count += count
        
    assert processed_count == 3
    
    # Verify Logs
    stmt = select(BroadcastLog).where(BroadcastLog.import_batch_id == batch_id)
    res = await db_session.execute(stmt)
    logs = res.scalars().all()
    
    assert len(logs) == 3
    
    jude_log = next(l for l in logs if "Beatles" in l.raw_artist)
    boh_log = next(l for l in logs if "Queen" in l.raw_artist)
    unk_log = next(l for l in logs if "Unknown" in l.raw_artist)
    
    # Check Jude (Exact) - now linked to work, not recording
    assert jude_log.work_id is not None
    assert "Exact" in jude_log.match_reason or "Identity" in jude_log.match_reason
    
    # Check Queen (Vector/Fuzzy)
    # "Bohemian Raphsody" -> "Bohemian Rhapsody"
    # Should be High Confidence or Vector Strong
    assert boh_log.work_id is not None
    # Check reason logic: might be "Exact" if clean normalization fixes it?
    # "Raphsody" is typo. Normalizer probably won't fix it.
    # So Vector Match or Variant.
    assert "Vector" in boh_log.match_reason or "High Confidence" in boh_log.match_reason
    
    # Check Unknown
    assert unk_log.work_id is None
    assert unk_log.match_reason == "No Match Found"
