"""Tests for the audio file scanner worker."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from airwave.core.models import (
    Album,
    Artist,
    LibraryFile,
    Recording,
    Work,
    WorkArtist,
)
from airwave.core.stats import ScanStats
from airwave.worker.matcher import Matcher
from airwave.worker.scanner import FileScanner


@pytest.mark.asyncio
async def test_process_file_new_track():
    """Test processing a new file creates a track."""
    # Setup
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    file_scanner = FileScanner(mock_session)
    file_scanner.matcher = AsyncMock(spec=Matcher)
    file_scanner.matcher._vector_db = MagicMock()
    file_scanner.executor = MagicMock()  # Mock Executor

    file_path = MagicMock()
    file_path.__str__.return_value = "/music/Artist - Title.mp3"
    file_path.stat.return_value.st_size = 1024
    file_path.suffix = ".mp3"
    file_path.stem = "Artist - Title"

    stats = ScanStats()

    mock_audio = MagicMock()
    mock_audio.get.side_effect = lambda k, d=None: {
        "artist": ["Artist"],
        "title": ["Title"],
    }.get(k, d)
    mock_audio.info = MagicMock()
    mock_audio.info.length = 300.0

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value=mock_audio
        )

        # Mock DB: No existing LibraryFile
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Mock helpers to simplify logic
        with patch.object(
            file_scanner, "_get_or_create_artist", new_callable=AsyncMock
        ) as mock_artist, patch.object(
            file_scanner, "_get_or_create_work", new_callable=AsyncMock
        ) as mock_work, patch.object(
            file_scanner, "_get_or_create_recording", new_callable=AsyncMock
        ) as mock_rec:
            mock_artist.return_value = Artist(id=1, name="Artist")
            mock_work.return_value = Work(id=1, title="Title", artist_id=1)
            mock_rec.return_value = Recording(
                id=1, work_id=1, title="Title", version_type="Original"
            )

            # Execute
            await file_scanner.process_file(file_path, stats)

            # Assertions
            assert stats.created == 1
            assert mock_session.add.called

            # Check that LibraryFile was created
            args, _ = mock_session.add.call_args
            new_file = args[0]
            assert isinstance(new_file, LibraryFile)
            assert new_file.path == str(file_path)
            assert new_file.recording_id == 1


@pytest.mark.asyncio
async def test_process_file_existing_track():
    """Test skipping a file executed if path already exists."""
    mock_session = AsyncMock()
    file_scanner = FileScanner(mock_session)

    file_path = Path("/music/existing.mp3")
    stats = ScanStats()

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value={})

        # Mock DB: LibraryFile exists
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = LibraryFile(
            id=1, path=str(file_path)
        )
        mock_session.execute.return_value = mock_result

        await file_scanner.process_file(file_path, stats)

        assert stats.skipped == 1


@pytest.mark.asyncio
async def test_scan_directory_structure():
    """Test os.scandir integration (mocked)."""
    mock_session = AsyncMock()
    file_scanner = FileScanner(mock_session)
    file_scanner.matcher = AsyncMock()
    file_scanner.matcher._vector_db = MagicMock()

    root = "/music"

    with patch("asyncio.get_running_loop") as mock_loop, patch(
        "pathlib.Path.exists", return_value=True
    ), patch.object(FileScanner, "process_file") as mock_process:
        entry1 = MagicMock()
        entry1.is_dir.return_value = False
        entry1.is_file.return_value = True
        entry1.name = "song1.mp3"
        entry1.path = "/music/song1.mp3"

        entry2 = MagicMock()
        entry2.is_dir.return_value = False
        entry2.is_file.return_value = True
        entry2.name = "song2.flac"
        entry2.path = "/music/song2.flac"

        f1 = asyncio.Future()
        f1.set_result(2)
        f2 = asyncio.Future()
        f2.set_result([entry1, entry2])
        mock_loop.return_value.run_in_executor.side_effect = [f1, f2]

        stats = await file_scanner.scan_directory(root)

        assert mock_process.call_count == 2
        assert stats.processed == 2


@pytest.mark.asyncio
async def test_process_file_with_albumartist():
    """Test that ALBUMARTIST is prioritized for Works and Album artist."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    file_scanner = FileScanner(mock_session)
    file_scanner.matcher = AsyncMock(spec=Matcher)
    file_scanner.matcher._vector_db = MagicMock()
    file_scanner.executor = MagicMock()

    file_path = MagicMock()
    file_path.__str__.return_value = "/music/Collaboration.mp3"
    file_path.stat.return_value.st_size = 1024
    file_path.suffix = ".mp3"
    file_path.stem = "Collaboration"

    stats = ScanStats()

    # Mock tags: albumartist="Artist A", artist="Artist A & Artist B"
    mock_audio = MagicMock()
    mock_audio.get.side_effect = lambda k, d=None: {
        "artist": ["Artist A & Artist B"],
        "albumartist": ["Artist A"],
        "title": ["Song Title"],
        "album": ["Album X"],
    }.get(k, d)
    mock_audio.info = MagicMock()
    mock_audio.info.length = 300.0

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value=mock_audio
        )

        # Mock DB
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch.object(
            file_scanner, "_get_or_create_artist", new_callable=AsyncMock
        ) as mock_artist, patch.object(
            file_scanner, "_get_or_create_work", new_callable=AsyncMock
        ) as mock_work, patch.object(
            file_scanner, "_get_or_create_recording", new_callable=AsyncMock
        ) as mock_rec, patch.object(
            file_scanner, "_get_or_create_album", new_callable=AsyncMock
        ) as mock_album:
            # Setup return values
            artist_a = Artist(id=1, name="artist a")
            work = Work(id=1, title="song title", artist_id=1)
            recording = Recording(
                id=1, work_id=1, title="Song Title", version_type="Original"
            )
            album = Album(id=1, title="Album X", artist_id=1)

            mock_artist.return_value = artist_a
            mock_work.return_value = work
            mock_rec.return_value = recording
            mock_album.return_value = album

            # Execute
            await file_scanner.process_file(file_path, stats)

            # Assertions
            # 1. _get_or_create_artist should be called with "Artist A" (from albumartist)
            # Actually it's called twice in my implementation: one for primary, one for album artist
            # Both should be "Artist A" in this case.
            artist_calls = [call.args[0] for call in mock_artist.call_args_list]
            assert "artist a" in artist_calls

            # 2. _get_or_create_work should use the ID of the primary artist (Artist A)
            # Implementation passes title as is to _get_or_create_work
            mock_work.assert_called_with("song title", artist_a.id)

            # 3. _get_or_create_album should use the ID of the album artist (Artist A)
            mock_album.assert_called_with("album x", artist_a.id, None)


@pytest.mark.asyncio
async def test_process_file_compilation():
    """Test that ALBUMARTIST="Various Artists" is handled correctly."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    file_scanner = FileScanner(mock_session)
    file_scanner.matcher = AsyncMock(spec=Matcher)
    file_scanner.matcher._vector_db = MagicMock()
    file_scanner.executor = MagicMock()

    file_path = MagicMock()
    file_path.__str__.return_value = "/music/Compilation.mp3"
    file_path.stat.return_value.st_size = 1024
    file_path.suffix = ".mp3"
    file_path.stem = "Compilation"

    stats = ScanStats()

    # Mock tags: albumartist="Various Artists", artist="Specific Artist"
    mock_audio = MagicMock()
    mock_audio.get.side_effect = lambda k, d=None: {
        "artist": ["Specific Artist"],
        "albumartist": ["Various Artists"],
        "title": ["Song Title"],
        "album": ["Soundtrack"],
    }.get(k, d)
    mock_audio.info = MagicMock()
    mock_audio.info.length = 300.0

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value=mock_audio
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch.object(
            file_scanner, "_get_or_create_artist", new_callable=AsyncMock
        ) as mock_artist, patch.object(
            file_scanner, "_get_or_create_work", new_callable=AsyncMock
        ) as mock_work, patch.object(
            file_scanner, "_get_or_create_recording", new_callable=AsyncMock
        ) as mock_rec, patch.object(
            file_scanner, "_get_or_create_album", new_callable=AsyncMock
        ) as mock_album:
            specific_artist = Artist(id=1, name="specific artist")
            various_artists = Artist(id=2, name="various artists")

            # Mock artist lookup to return different objects based on name
            async def side_effect(name):
                if name == "specific artist":
                    return specific_artist
                return various_artists

            mock_artist.side_effect = side_effect

            mock_work.return_value = Work(id=1, title="song title", artist_id=1)
            mock_rec.return_value = Recording(
                id=1, work_id=1, title="Song Title", version_type="Original"
            )
            mock_album.return_value = Album(
                id=1, title="Soundtrack", artist_id=2
            )

            # Execute
            await file_scanner.process_file(file_path, stats)

            # Assertions
            # 1. Work should be linked to Specific Artist
            mock_work.assert_called_with("song title", specific_artist.id)

            # 2. Album should be linked to Various Artists
            mock_album.assert_called_with(
                "soundtrack", various_artists.id, None
            )


@pytest.mark.asyncio
async def test_process_file_multi_artist():
    """Test that multiple artists are extracted and associated with the Work."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    file_scanner = FileScanner(mock_session)
    file_scanner.matcher = AsyncMock(spec=Matcher)
    file_scanner.matcher._vector_db = MagicMock()
    file_scanner.executor = MagicMock()

    file_path = MagicMock()
    file_path.__str__.return_value = "/music/Collaboration.mp3"
    file_path.stat.return_value.st_size = 1024
    file_path.suffix = ".mp3"
    file_path.stem = "Collaboration"

    stats = ScanStats()

    # Mock tags: artist="Artist A & Artist B"
    mock_audio = MagicMock()
    mock_audio.get.side_effect = lambda k, d=None: {
        "artist": ["Artist A & Artist B"],
        "albumartist": ["Artist A"],
        "title": ["Song Title"],
        "album": ["Album X"],
    }.get(k, d)
    mock_audio.info = MagicMock()
    mock_audio.info.length = 300.0

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value=mock_audio
        )

        # Mock DB: LibraryFile does not exist
        # We need to mock multiple execute calls for WorkArtist checks
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result_none

        with patch.object(
            file_scanner, "_get_or_create_artist", new_callable=AsyncMock
        ) as mock_artist, patch.object(
            file_scanner, "_get_or_create_work", new_callable=AsyncMock
        ) as mock_work, patch.object(
            file_scanner, "_get_or_create_recording", new_callable=AsyncMock
        ) as mock_rec, patch.object(
            file_scanner, "_get_or_create_album", new_callable=AsyncMock
        ) as mock_album:
            artist_a = Artist(id=1, name="artist a")
            artist_b = Artist(id=2, name="artist b")

            async def artist_side_effect(name):
                if "artist a" in name:
                    return artist_a
                return artist_b

            mock_artist.side_effect = artist_side_effect

            mock_work.return_value = Work(
                id=10, title="Song Title", artist_id=1
            )
            mock_rec.return_value = Recording(
                id=100, work_id=10, title="Song Title", version_type="Original"
            )
            mock_album.return_value = Album(
                id=1000, title="Album X", artist_id=1
            )

            # Execute
            await file_scanner.process_file(file_path, stats)

            # Assertions
            # Check that WorkArtist bridge entries were added
            added_objects = [
                call.args[0] for call in mock_session.add.call_args_list
            ]
            wa_entries = [
                obj for obj in added_objects if isinstance(obj, WorkArtist)
            ]

            assert len(wa_entries) == 2
            work_ids = {entry.work_id for entry in wa_entries}
            artist_ids = {entry.artist_id for entry in wa_entries}

            assert work_ids == {10}
            assert artist_ids == {1, 2}


@pytest.mark.asyncio
async def test_process_file_duplicate_artist_ids():
    """Test that variations of the same artist name resolving to the same ID don't cause IntegrityError."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    file_scanner = FileScanner(mock_session)
    file_scanner.matcher = AsyncMock(spec=Matcher)
    file_scanner.matcher._vector_db = MagicMock()
    file_scanner.executor = MagicMock()

    file_path = MagicMock()
    file_path.__str__.return_value = "/music/POD.mp3"
    file_path.suffix = ".mp3"
    file_path.stem = "POD"
    file_path.stat.return_value.st_size = 1024

    stats = ScanStats()

    # Mock tags: artist="P.O.D.", albumartist="P.O.D"
    mock_audio = MagicMock()
    mock_audio.get.side_effect = lambda k, d=None: {
        "artist": ["P.O.D."],
        "albumartist": ["P.O.D"],
        "title": ["Southtown"],
        "album": ["The Fundamental Elements of Southtown"],
    }.get(k, d)
    mock_audio.info = MagicMock()
    mock_audio.info.length = 300.0

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value=mock_audio
        )

        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result_none

        with patch.object(
            file_scanner, "_get_or_create_artist", new_callable=AsyncMock
        ) as mock_artist, patch.object(
            file_scanner, "_get_or_create_work", new_callable=AsyncMock
        ) as mock_work, patch.object(
            file_scanner, "_get_or_create_recording", new_callable=AsyncMock
        ) as mock_rec, patch.object(
            file_scanner, "_get_or_create_album", new_callable=AsyncMock
        ) as mock_album:
            # Both "P.O.D." and "P.O.D" resolve to the same Artist object
            artist_pod = Artist(id=178, name="pod")
            mock_artist.return_value = artist_pod

            mock_work.return_value = Work(
                id=3284, title="Southtown", artist_id=178
            )
            mock_rec.return_value = Recording(
                id=100, work_id=3284, title="Southtown", version_type="Original"
            )
            mock_album.return_value = Album(
                id=1000, title="Album", artist_id=178
            )

            # Execute - should NOT raise IntegrityError because of IDs deduplication
            await file_scanner.process_file(file_path, stats)

            # Assertions
            added_objects = [
                call.args[0] for call in mock_session.add.call_args_list
            ]
            wa_entries = [
                obj for obj in added_objects if isinstance(obj, WorkArtist)
            ]

            # Should only be ONE entry for ID 178
            assert len(wa_entries) == 1
            assert wa_entries[0].artist_id == 178
