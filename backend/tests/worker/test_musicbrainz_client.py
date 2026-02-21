"""Unit tests for MusicBrainz API client.

This test suite covers:
- Fetching single artist names
- Batch fetching with rate limiting
- Error handling (404, 503, network errors)
- Session management
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("aiohttp")
from aiohttp import ClientError

from airwave.worker.musicbrainz_client import MusicBrainzClient


# Valid MusicBrainz Artist IDs for testing
METALLICA_MBID = "65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab"
NIRVANA_MBID = "5b11f4ce-a62d-471e-81fc-a69a8278c7da"
INVALID_MBID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
class TestMusicBrainzClient:
    """Test suite for MusicBrainzClient."""

    async def test_fetch_artist_name_success(self):
        """Test successful fetch of artist name."""
        client = MusicBrainzClient()

        # Mock the aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"name": "Metallica"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        # Mock the session
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)

        client._session = mock_session

        name = await client.fetch_artist_name(METALLICA_MBID)

        assert name == "Metallica"

    async def test_fetch_artist_name_not_found(self):
        """Test handling of 404 (artist not found)."""
        client = MusicBrainzClient()
        
        mock_response = AsyncMock()
        mock_response.status = 404
        
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock()
        
        client._session = mock_session
        
        name = await client.fetch_artist_name(INVALID_MBID)
        
        assert name is None

    async def test_fetch_artist_name_service_unavailable(self):
        """Test handling of 503 (service unavailable)."""
        client = MusicBrainzClient()
        
        mock_response = AsyncMock()
        mock_response.status = 503
        
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock()
        
        client._session = mock_session
        
        name = await client.fetch_artist_name(METALLICA_MBID)
        
        assert name is None

    async def test_fetch_artist_name_network_error(self):
        """Test handling of network errors."""
        client = MusicBrainzClient()
        
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=ClientError("Network error"))
        
        client._session = mock_session
        
        name = await client.fetch_artist_name(METALLICA_MBID)
        
        assert name is None

    async def test_fetch_artist_names_batch(self):
        """Test batch fetching of artist names."""
        client = MusicBrainzClient()
        
        # Mock responses for different artists
        def mock_get(url):
            mock_response = AsyncMock()
            if METALLICA_MBID in url:
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"name": "Metallica"})
            elif NIRVANA_MBID in url:
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"name": "Nirvana"})
            else:
                mock_response.status = 404
            
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock()
            return mock_response
        
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=mock_get)
        
        client._session = mock_session
        
        # Disable rate limiting for faster tests
        client.RATE_LIMIT_DELAY = 0.01
        
        mbids = [METALLICA_MBID, NIRVANA_MBID, INVALID_MBID]
        results = await client.fetch_artist_names_batch(mbids, batch_size=10)
        
        assert results[METALLICA_MBID] == "Metallica"
        assert results[NIRVANA_MBID] == "Nirvana"
        assert results[INVALID_MBID] is None

    async def test_rate_limiting(self):
        """Test that rate limiting is enforced."""
        client = MusicBrainzClient()
        client.RATE_LIMIT_DELAY = 0.1  # 100ms for testing
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"name": "Test Artist"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        
        client._session = mock_session
        
        # Measure time for 3 requests
        start = asyncio.get_event_loop().time()
        await client.fetch_artist_name("mbid1")
        await client.fetch_artist_name("mbid2")
        await client.fetch_artist_name("mbid3")
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should take at least 2 * RATE_LIMIT_DELAY (between requests)
        assert elapsed >= 0.2  # 2 * 0.1s

    async def test_session_cleanup(self):
        """Test that session is properly closed."""
        client = MusicBrainzClient()
        
        # Client owns the session
        assert client._owns_session is True
        
        # Create a session
        await client._ensure_session()
        assert client._session is not None
        
        # Close should clean up
        await client.close()
        assert client._session is None

