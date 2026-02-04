import pytest
from airwave.worker.matcher import Matcher
from airwave.core.models import Artist, Work, Recording
from sqlalchemy import select

@pytest.fixture
async def setup_tracks(db_session, db_engine):
    """Setup a library with known tracks for matching."""
    # 1. Exact Target: "The Beatles - Hey Jude"
    beatles = Artist(name="the beatles")
    db_session.add(beatles)
    await db_session.flush()
    
    jude_work = Work(title="hey jude", artist_id=beatles.id)
    db_session.add(jude_work)
    await db_session.flush()
    
    jude_rec = Recording(work_id=jude_work.id, title="hey jude", version_type="Original")
    db_session.add(jude_rec)
    await db_session.commit()
    
    return {
        "beatles_id": jude_rec.id
    }

@pytest.mark.asyncio
async def test_exact_match(db_session, setup_tracks):
    """Test Exact Matching strategy."""
    ids = setup_tracks
    
    # Create Matcher
    matcher = Matcher(db_session)

    # DIRECT CHECK
    print(f"DEBUG: IDs: {ids}")
    from sqlalchemy import tuple_
    stmt = (
        select(Recording)
        .join(Work)
        .join(Artist)
        .where(tuple_(Artist.name, Recording.title).in_([("the beatles", "hey jude")]))
    )
    res = await db_session.execute(stmt)
    rec = res.scalar_one_or_none()
    print(f"DEBUG: Recording via Tuple Query: {rec}")

    # "The Beatles" (Exact) vs "The Beatles" in DB
    print("DEBUG: Testing Exact Match...")
    results = await matcher.match_batch([("The Beatles", "Hey Jude")])
    match = results.get(("The Beatles", "Hey Jude"))
    
    assert match is not None, f"Exact match failed. Results: {results}"
    assert match[0] == ids["beatles_id"], f"Expected {ids['beatles_id']}, got {match}"
    assert "Exact" in match[1]
