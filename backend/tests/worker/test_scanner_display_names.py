"""Tests for FileScanner display_name / MusicBrainz integration."""

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("aiohttp")

from airwave.core.models import Artist
from airwave.worker.scanner import FileScanner

# Ensure submodule is loaded so patch('...musicbrainz_client.MusicBrainzClient') can resolve
import airwave.worker.musicbrainz_client  # noqa: F401


@pytest.mark.asyncio
class TestUpdateArtistDisplayNamesFromMusicBrainz:
    """Tests for update_artist_display_names_from_musicbrainz."""

    async def test_updates_display_name_from_musicbrainz(self, db_session):
        """When MB returns canonical name, display_name is updated."""
        # Create artist with MBID but no display_name
        artist = Artist(
            name="metallica",
            musicbrainz_id="65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab",
            display_name=None,
        )
        db_session.add(artist)
        await db_session.flush()

        mock_results = {
            "65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab": "Metallica",
        }

        with patch(
            "airwave.worker.musicbrainz_client.MusicBrainzClient"
        ) as MockClient:
            mock_instance = AsyncMock()
            mock_instance.fetch_artist_names_batch = AsyncMock(return_value=mock_results)
            mock_instance.close = AsyncMock()
            MockClient.return_value = mock_instance

            scanner = FileScanner(db_session)
            stats = await scanner.update_artist_display_names_from_musicbrainz(
                batch_size=50
            )

        await db_session.refresh(artist)
        assert artist.display_name == "Metallica"
        assert stats["updated"] == 1
        assert stats["failed"] == 0

    async def test_fallback_to_name_on_musicbrainz_failure(self, db_session):
        """When MB returns None, display_name falls back to name."""
        artist = Artist(
            name="unknown_artist",
            musicbrainz_id="00000000-0000-0000-0000-000000000000",
            display_name=None,
        )
        db_session.add(artist)
        await db_session.flush()

        mock_results = {
            "00000000-0000-0000-0000-000000000000": None,
        }

        with patch(
            "airwave.worker.musicbrainz_client.MusicBrainzClient"
        ) as MockClient:
            mock_instance = AsyncMock()
            mock_instance.fetch_artist_names_batch = AsyncMock(return_value=mock_results)
            mock_instance.close = AsyncMock()
            MockClient.return_value = mock_instance

            scanner = FileScanner(db_session)
            stats = await scanner.update_artist_display_names_from_musicbrainz(
                batch_size=50
            )

        await db_session.refresh(artist)
        assert artist.display_name == "unknown_artist"
        assert stats["failed"] == 1
        assert stats["updated"] == 0

    async def test_skips_artists_without_mbid(self, db_session):
        """Artists without MBID are not selected for update."""
        artist = Artist(name="local_artist", musicbrainz_id=None, display_name=None)
        db_session.add(artist)
        await db_session.flush()

        with patch(
            "airwave.worker.musicbrainz_client.MusicBrainzClient"
        ) as MockClient:
            scanner = FileScanner(db_session)
            stats = await scanner.update_artist_display_names_from_musicbrainz(
                batch_size=50
            )

        assert stats["updated"] == 0
        assert stats["failed"] == 0
        assert stats["skipped"] == 0
        # MusicBrainzClient never instantiated when no artists need update
        MockClient.assert_not_called()

    async def test_respects_limit_parameter(self, db_session):
        """limit parameter restricts how many artists are processed."""
        for i in range(5):
            artist = Artist(
                name=f"artist_{i}",
                musicbrainz_id=f"00000000-0000-0000-0000-00000000000{i}",
                display_name=None,
            )
            db_session.add(artist)
        await db_session.flush()

        call_count = 0

        async def mock_batch(mbids, batch_size=50):
            nonlocal call_count
            call_count += 1
            return {mbid: "Canonical" for mbid in mbids}

        with patch(
            "airwave.worker.musicbrainz_client.MusicBrainzClient"
        ) as MockClient:
            mock_instance = AsyncMock()
            mock_instance.fetch_artist_names_batch = AsyncMock(side_effect=mock_batch)
            mock_instance.close = AsyncMock()
            MockClient.return_value = mock_instance

            scanner = FileScanner(db_session)
            stats = await scanner.update_artist_display_names_from_musicbrainz(
                batch_size=50, limit=2
            )

        assert stats["updated"] == 2
        assert call_count == 1  # One batch of 2
