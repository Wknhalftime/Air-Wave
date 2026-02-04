import pytest
import shutil
from pathlib import Path
from airwave.core.vector_db import VectorDB
from airwave.core.config import settings

@pytest.fixture
def vector_db(tmp_path):
    """Fixture to provide a VectorDB instance with a temporary path."""
    # Use a temp directory for ChromaDB to avoid polluting real data
    db_path = tmp_path / "chroma_test"
    db = VectorDB(persist_path=str(db_path))
    
    # Clear collection before test
    try:
        db.client.delete_collection("tracks")
    except Exception:
        pass
        
    # Re-create
    db.collection = db.client.get_or_create_collection(
        name="tracks",
        embedding_function=db.ef,
        metadata={"hnsw:space": "cosine"}
    )
    
    yield db
    
    # Cleanup is handled by tmp_path, but explicitly resetting singleton might be needed
    # if VectorDB was truly singleton.
    # However, VectorDB singleton logic checks cls._instance.
    # For testing, we might want to bypass singleton or reset it.
    VectorDB._instance = None

def test_singleton_pattern(tmp_path):
    """Verify VectorDB acts as a singleton."""
    VectorDB._instance = None
    path = str(tmp_path / "chroma_singleton")
    db1 = VectorDB(persist_path=path)
    db2 = VectorDB(persist_path=path)
    
    assert db1 is db2
    assert db1.client is db2.client
    
    # Cleanup
    VectorDB._instance = None

def test_add_and_search_track(vector_db):
    """Test adding a track and ensuring it can be found semantically."""
    # Add track
    vector_db.add_track(1, "The Beatles", "Hey Jude")
    
    # Search Exact
    results = vector_db.search("The Beatles", "Hey Jude", limit=1)
    assert len(results) == 1
    track_id, dist = results[0]
    assert track_id == 1
    assert dist < 0.01  # Should be very close to 0

    # Search Semantic (Variant)
    # "Beetles" typo
    results = vector_db.search("The Beetles", "Hey Jude", limit=1)
    assert len(results) == 1
    track_id, dist = results[0]
    assert track_id == 1
    # Distance for "Beetles" vs "The Beatles" is around 0.25
    assert dist < 0.3

def test_search_batch(vector_db):
    """Test batch search functionality."""
    tracks = [
        (1, "Queen", "Bohemian Rhapsody"),
        (2, "Queen", "We Will Rock You"),
        (3, "Queen", "Another One Bites The Dust")
    ]
    vector_db.add_tracks(tracks)
    
    queries = [
        ("Queen", "Bohemian Rhapsody"),
        ("Queen", "We Will Rock You"),
        ("Led Zeppelin", "Stairway to Heaven") # Should match nothing closely
    ]
    
    results = vector_db.search_batch(queries, limit=1)
    assert len(results) == 3
    
    # 1. Bohemian Rhapsody
    assert len(results[0]) == 1
    assert results[0][0][0] == 1
    assert results[0][0][1] < 0.01
    
    # 2. We Will Rock You
    assert len(results[1]) == 1
    assert results[1][0][0] == 2
    assert results[1][0][1] < 0.01
    
    # 3. Stairway (No match in DB, but Vector Search always returns something unless filtered)
    # Chroma returns nearest neighbor.
    # It will probably match one of the Queen songs with high distance.
    assert len(results[2]) == 1
    # Distance should be high
    assert results[2][0][1] > 0.3
