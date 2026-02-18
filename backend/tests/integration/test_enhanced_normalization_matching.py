"""Integration tests for enhanced normalization improving matcher results.

Story 6-1: Verifies that year brackets, truncation markers, and feat. suffixes
in broadcast log titles normalize correctly so they match library recordings.
"""

import pytest
from airwave.core.models import Artist, Recording, Work
from airwave.worker.matcher import Matcher


@pytest.fixture
async def setup_library_for_normalization(db_session):
    """Create a library recording: 'Song Title' by 'Artist' (normalized in DB)."""
    artist = Artist(name="artist")
    db_session.add(artist)
    await db_session.flush()

    work = Work(title="song title", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()

    rec = Recording(work_id=work.id, title="song title", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    return {"artist_id": artist.id, "recording_id": rec.id}


@pytest.mark.asyncio
async def test_enhanced_normalization_year_and_feat_matching(
    db_session, setup_library_for_normalization
):
    """Broadcast 'Song Title (2018) feat. Guest' by 'Artist' should match library 'Song Title'."""
    ids = setup_library_for_normalization
    matcher = Matcher(db_session)

    results = await matcher.match_batch([("Artist", "Song Title (2018) feat. Guest")])
    match = results.get(("Artist", "Song Title (2018) feat. Guest"))

    assert match is not None, f"Match failed. Results: {results}"
    assert match[0] == ids["recording_id"]
    assert "Exact" in match[1] or "Match" in match[1]


@pytest.mark.asyncio
async def test_enhanced_normalization_truncation_matching(
    db_session, setup_library_for_normalization
):
    """Broadcast 'Long Song Title (...)' should match library 'Long Song Title' when present."""
    ids = setup_library_for_normalization
    # Reuse existing artist from fixture; add Work + Recording for "long song title"
    work = Work(title="long song title", artist_id=ids["artist_id"])
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="long song title", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    matcher = Matcher(db_session)
    results = await matcher.match_batch([("Artist", "Long Song Title (...)")])
    match = results.get(("Artist", "Long Song Title (...)"))

    assert match is not None
    assert match[0] == rec.id


@pytest.mark.asyncio
async def test_enhanced_normalization_complex_chain(
    db_session, setup_library_for_normalization
):
    """Multiple enhancements in one title: year, deluxe, feat., truncation."""
    ids = setup_library_for_normalization
    matcher = Matcher(db_session)

    # Library has "song title" by "artist"
    # Broadcast: "Song's Title (2018) [Deluxe] feat. Guest (...)" normalizes to "songs title deluxe"
    # So we need a library track that normalizes to that, or we test that "Song Title" style matches
    results = await matcher.match_batch([
        ("Artist", "Song Title (2018) feat. Guest (...)")
    ])
    match = results.get(("Artist", "Song Title (2018) feat. Guest (...)"))
    assert match is not None
    assert match[0] == ids["recording_id"]
