"""
Unit tests for the search endpoint to verify multi-term search functionality.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from airwave.core.models import Artist, Work, Recording, LibraryFile
from airwave.api.routers.search import search


@pytest.mark.asyncio
async def test_multi_term_search_artist_and_title(db_session: AsyncSession):
    """
    Test that multi-term search finds records where different words match different fields.
    Example: "Elton John break" should find "Don't Go Breaking My Heart" by Elton John
    """
    # Setup: Create test data
    artist = Artist(name="Elton John")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Don't Go Breaking My Heart", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    recording = Recording(title="Don't Go Breaking My Heart", work_id=work.id, is_verified=True)
    db_session.add(recording)
    await db_session.commit()
    
    # Test: Search with "Elton John break"
    # - "Elton" should match artist name
    # - "John" should match artist name
    # - "break" should match recording title
    result = await search(q="Elton John break", type="track", include_bronze=False, limit=50, db=db_session)
    
    assert len(result.tracks) == 1, f"Expected 1 result, got {len(result.tracks)}"
    assert result.tracks[0].artist == "Elton John"
    assert result.tracks[0].title == "Don't Go Breaking My Heart"


@pytest.mark.asyncio
async def test_multi_term_search_title_only(db_session: AsyncSession):
    """
    Test that multi-term search finds records where all words match the same field.
    Example: "breaking heart" should find "Don't Go Breaking My Heart"
    """
    # Setup
    artist = Artist(name="Elton John")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Don't Go Breaking My Heart", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    recording = Recording(title="Don't Go Breaking My Heart", work_id=work.id, is_verified=True)
    db_session.add(recording)
    await db_session.commit()
    
    # Test: Search with "breaking heart"
    result = await search(q="breaking heart", type="track", include_bronze=False, limit=50, db=db_session)
    
    assert len(result.tracks) >= 1
    found = any(t.title == "Don't Go Breaking My Heart" for t in result.tracks)
    assert found, "Should find 'Don't Go Breaking My Heart' when searching 'breaking heart'"


@pytest.mark.asyncio
async def test_multi_term_search_no_match(db_session: AsyncSession):
    """
    Test that multi-term search returns no results when not all words match.
    Example: "Elton John zzzzzz" should find nothing (no field contains "zzzzzz")
    """
    # Setup
    artist = Artist(name="Elton John")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Don't Go Breaking My Heart", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    recording = Recording(title="Don't Go Breaking My Heart", work_id=work.id, is_verified=True)
    db_session.add(recording)
    await db_session.commit()
    
    # Test: Search with nonsense word
    result = await search(q="Elton John zzzzzz", type="track", include_bronze=False, limit=50, db=db_session)
    
    assert len(result.tracks) == 0, "Should not find any results when one word doesn't match"


@pytest.mark.asyncio
async def test_single_word_search(db_session: AsyncSession):
    """
    Test that single-word search still works correctly.
    """
    # Setup
    artist = Artist(name="The Beatles")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Yesterday", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    recording = Recording(title="Yesterday", work_id=work.id, is_verified=True)
    db_session.add(recording)
    await db_session.commit()
    
    # Test: Search with single word
    result = await search(q="beatles", type="track", include_bronze=False, limit=50, db=db_session)
    
    assert len(result.tracks) >= 1
    found = any(t.artist == "The Beatles" for t in result.tracks)
    assert found, "Should find The Beatles when searching 'beatles'"


@pytest.mark.asyncio
async def test_bronze_filtering(db_session: AsyncSession):
    """
    Test that Bronze recordings are excluded by default.
    """
    # Setup: Create Bronze recording (not verified, no file)
    artist = Artist(name="Test Artist")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Test Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    recording = Recording(title="Test Song", work_id=work.id, is_verified=False)
    db_session.add(recording)
    await db_session.commit()
    
    # Test: Search without including bronze
    result = await search(q="Test", type="track", include_bronze=False, limit=50, db=db_session)
    assert len(result.tracks) == 0, "Bronze recordings should be excluded by default"
    
    # Test: Search with including bronze
    result = await search(q="Test", type="track", include_bronze=True, limit=50, db=db_session)
    assert len(result.tracks) >= 1, "Bronze recordings should be included when include_bronze=True"
