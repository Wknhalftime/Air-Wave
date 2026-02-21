"""Debug script to test search functionality.

Usage:
    poetry run python -m airwave.scripts.debug_search
"""
import asyncio

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import Artist, Recording, Work
from airwave.core.normalization import Normalizer


async def debug_search():
    """Test search with different queries."""
    test_queries = [
        "All or nothing",
        "All or nothing ",
        "Elton John break",
        "RAGE AGAINST THE MACHINE",
        "RAGE AGAINST THE MACHINE ",
    ]

    async with AsyncSessionLocal() as db:
        for q in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: '{q}' (length: {len(q)})")
            print(f"{'='*60}")

            normalized = Normalizer.clean(q)
            terms = normalized.split()
            print(f"Normalized: '{normalized}'")
            print(f"Terms: {terms}")

            stmt = (
                select(Recording)
                .options(
                    selectinload(Recording.work).selectinload(Work.artist)
                )
                .join(Recording.work)
                .join(Work.artist)
            )

            for word in terms:
                word_pattern = f"%{word}%"
                stmt = stmt.where(
                    or_(
                        Artist.name.ilike(word_pattern),
                        Recording.title.ilike(word_pattern),
                        Work.title.ilike(word_pattern),
                    )
                )

            result = await db.execute(stmt.limit(10))
            recordings = result.scalars().all()

            print(f"\nResults: {len(recordings)}")
            for r in recordings[:5]:
                artist_name = (
                    r.work.artist.name if r.work and r.work.artist else "Unknown"
                )
                print(f"  - {artist_name} - {r.title}")


if __name__ == "__main__":
    asyncio.run(debug_search())
