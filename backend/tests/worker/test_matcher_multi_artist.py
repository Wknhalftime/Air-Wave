from unittest.mock import AsyncMock, MagicMock

import pytest
from airwave.core.models import Artist, Recording, Work
from airwave.worker.matcher import Matcher, Normalizer


@pytest.mark.asyncio
async def test_matcher_multi_artist_scoring():
    """Test that Matcher correctly scores using multiple associated artists."""
    mock_session = AsyncMock()
    matcher = Matcher(mock_session)

    # Setup mocks for vector search and DB fetch
    matcher._vector_db = MagicMock()

    # Cleaned query: artist="Artist B", title="Song X"
    # We want to match this to a Work that has primary_artist="Artist A"
    # but also associated_artist="Artist B"

    clean_a = "artist b"
    clean_t = "song x"

    # Mock Vector Search result
    matcher._vector_db.search_batch.return_value = [
        [(100, 0.1)]
    ]  # recording_id=100, dist=0.1

    # Mock DB Recording fetch
    artist_a = Artist(id=1, name="Artist A")
    artist_b = Artist(id=2, name="Artist B")
    work = Work(id=10, title="Song X", artist_id=1)
    work.artist = artist_a
    work.artists = [artist_a, artist_b]  # Multi-artist association

    recording = Recording(id=100, work_id=10, title="Song X")
    recording.work = work

    # Mock multiple execute calls
    # 1. Identity Bridge lookup (no matches)
    mock_res_bridge = MagicMock()
    mock_res_bridge.scalars.return_value.all.return_value = []

    # 2. Exact match lookup (no matches - Artist B is not primary artist)
    mock_res_exact = MagicMock()
    mock_res_exact.scalars.return_value.all.return_value = []

    # 3. Candidate fetch (finds recording via vector search)
    mock_res_candidates = MagicMock()
    mock_res_candidates.scalars.return_value.all.return_value = [recording]

    mock_session.execute.side_effect = [
        mock_res_bridge,
        mock_res_exact,
        mock_res_candidates,
    ]

    # Execute batch match
    results = await matcher.match_batch([("Artist B", "Song X")])

    # Assertions
    match = results.get(("Artist B", "Song X"))
    assert match is not None
    recording_id, reason = match

    assert recording_id == 100
    # The reason should indicate a high confidence match because Artist B matched perfectly
    assert "High Confidence" in reason or "Exact" in reason

    # Verify distance/similarity logic roughly
    # If it was only Artist A vs Artist B, similarity would be low.
    # Because Artist B is in work.artists, similarity should be 1.0


@pytest.mark.asyncio
async def test_normalizer_split_artists():
    """Test the artist splitting logic."""
    assert Normalizer.split_artists("A & B") == ["a", "b"]
    assert Normalizer.split_artists("A / B") == ["a", "b"]
    assert Normalizer.split_artists("A feat. B") == ["a", "b"]
    assert Normalizer.split_artists("A ft B") == ["a", "b"]
    assert Normalizer.split_artists("A featuring B") == ["a", "b"]
    assert Normalizer.split_artists("A with B") == ["a", "b"]
    assert Normalizer.split_artists("A, B and C") == ["a", "b", "c"]
    assert Normalizer.split_artists("  Artist A & Artist B  ") == [
        "artist a",
        "artist b",
    ]
    assert Normalizer.split_artists("A & A") == ["a"]  # Deduplication
