"""Tests for airwave.worker.seed."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from airwave.core.models import Artist, LibraryFile, Recording, Work
from airwave.worker import seed as seed_module


@pytest.mark.asyncio
async def test_seed_creates_artists_works_recordings(db_engine, monkeypatch):
    """Running seed() creates expected artists, works, recordings, and library files."""
    async_session_maker = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async def init_db_noop():
        pass

    monkeypatch.setattr(seed_module, "AsyncSessionLocal", async_session_maker)
    monkeypatch.setattr(seed_module, "init_db", init_db_noop)

    await seed_module.seed()

    async with async_session_maker() as session:
        stmt = select(Artist).where(Artist.name.in_(["Nirvana", "Pearl Jam", "Soundgarden"]))
        res = await session.execute(stmt)
        artists = res.scalars().all()
        assert len(artists) == 3

        stmt = select(Work).where(Work.title.in_(["Smells Like Teen Spirit", "Alive", "Black Hole Sun"]))
        res = await session.execute(stmt)
        works = res.scalars().all()
        assert len(works) == 3

        stmt = select(Recording)
        res = await session.execute(stmt)
        recordings = res.scalars().all()
        assert len(recordings) == 3

        stmt = select(LibraryFile)
        res = await session.execute(stmt)
        files = res.scalars().all()
        assert len(files) == 3
