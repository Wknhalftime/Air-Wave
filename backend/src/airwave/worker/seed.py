"""Database seeding utility for development."""

import asyncio

from loguru import logger
from sqlalchemy import select

from airwave.core.db import AsyncSessionLocal, init_db
from airwave.core.models import (
    Artist,
    LibraryFile,
    Recording,
    Work,
)


async def seed():
    """Seeds the database with sample tracks for testing/development."""
    await init_db()
    async with AsyncSessionLocal() as session:
        # Create Tracks (Recordings) for the CSV

        # Helper
        async def create_recording(artist_name, title, path):
            # Artist
            stmt = select(Artist).where(Artist.name == artist_name)
            res = await session.execute(stmt)
            a = res.scalar_one_or_none()
            if not a:
                a = Artist(name=artist_name)
                session.add(a)
                await session.flush()

            # Work
            stmt = select(Work).where(
                Work.title == title, Work.artist_id == a.id
            )
            res = await session.execute(stmt)
            w = res.scalar_one_or_none()
            if not w:
                w = Work(title=title, artist_id=a.id)
                session.add(w)
                await session.flush()

            # Recording
            r = Recording(work_id=w.id, title=title, version_type="Original")
            session.add(r)
            await session.flush()

            # File
            lf = LibraryFile(
                recording_id=r.id, path=path, format="mp3", size=1024
            )
            session.add(lf)
            return r

        await create_recording(
            "Nirvana",
            "Smells Like Teen Spirit",
            "/music/nirvana_teen_spirit.mp3",
        )
        await create_recording(
            "Pearl Jam", "Alive", "/music/pearl_jam_alive.mp3"
        )

        # Soundgarden
        await create_recording(
            "Soundgarden", "Black Hole Sun", "/music/sg_black_hole.mp3"
        )

        await session.commit()
        await session.commit()
        logger.info("Seeded tracks successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
