import pytest
from unittest.mock import MagicMock
from pathlib import Path
from airwave.worker.scanner import FileScanner
from airwave.core.models import Artist, Work, Recording

@pytest.fixture
def mock_mutagen(monkeypatch):
    """Mock mutagen to return controlled metadata based on filename."""
    def mock_file(path, easy=True):
        mock = MagicMock()
        p = Path(path)
        
        # Default values
        meta = {
            "artist": ["Unknown"],
            "title": ["Untitled"],
            "album": ["Unknown Album"],
            "date": ["2023"],
            "isrc": [""]
        }
        
        if "solo" in p.name:
            meta = {
                "artist": ["Daft Punk"],
                "title": ["Harder Better Faster Stronger"],
                "album": ["Discovery"],
                "date": ["2001"],
                "isrc": ["USV01"]
            }
        elif "collab" in p.name:
            meta = {
                "artist": ["Daft Punk feat. Pharrell Williams"],
                "title": ["Get Lucky"],
                "album": ["Random Access Memories"],
                "date": ["2013"],
                "isrc": ["USV02"]
            }

        mock.get.side_effect = lambda key, default=None: meta.get(key, default)
        mock.info.length = 200.0
        mock.info.bitrate = 320000
        return mock

    monkeypatch.setattr("airwave.worker.scanner.mutagen.File", mock_file)
    # Also patch where it might be imported specifically if needed, but scanner imports 'mutagen' module

@pytest.mark.asyncio
async def test_epic_1_end_to_end_flow(db_session, client, tmp_path, mock_mutagen):
    """
    Test the full Epic 1 flow:
    1. Scan audio files (Scanner)
    2. Populate Library (DB)
    3. Query Artists via API (Story 1.3 UI support)
    """
    # 1. Setup Test Files
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    
    # Create dummy files
    (music_dir / "solo_song.mp3").touch()
    (music_dir / "collab_song.mp3").touch()
    
    # 2. Run Scanner
    scanner = FileScanner(db_session)
    stats = await scanner.scan_directory(str(music_dir), task_id="epic-1-test")
    
    assert stats.processed == 2
    assert stats.created == 2  # 2 Recordings created
    
    # 3. Process proposed splits (simulating background worker or just verify they exist)
    # The scanner splits artists automatically for WorkArtist but normalized Artist names are stored
    
    # 4. Verify API Response
    response = await client.get("/api/v1/library/artists")
    assert response.status_code == 200
    data = response.json()
    
    
    # print(f"\nAPI Data: {data}")
    
    # We expect:
    # 1. "daft punk" (Primary on both)
    # 2. "pharrell williams" (Featured on one)
    
    assert len(data) >= 2
    
    daft_punk = next((a for a in data if a["name"] == "daft punk"), None)
    assert daft_punk is not None
    assert daft_punk["work_count"] == 2
    assert daft_punk["recording_count"] == 2
    
    pharrell = next((a for a in data if a["name"] == "pharrell williams"), None)
    assert pharrell is not None
    # Pharrell is linked to "Get Lucky" work
    assert pharrell["work_count"] == 1 
    
    # 5. Verify Search Functionality
    search_resp = await client.get("/api/v1/library/artists?search=Pharrell")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert len(search_data) == 1
    assert search_data[0]["name"] == "pharrell williams"
