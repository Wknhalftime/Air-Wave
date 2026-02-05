"""Debug script to test search functionality."""
import asyncio
from airwave.core.db import AsyncSessionLocal
from airwave.core.normalization import Normalizer
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from airwave.core.models import Recording, Work, Artist, LibraryFile

async def debug_search():
    """Test search with different queries."""

    test_queries = [
        "All or nothing",
        "All or nothing ",  # With trailing space
        "Elton John break",
        "RAGE AGAINST THE MACHINE",
        "RAGE AGAINST THE MACHINE ",  # With trailing space
    ]

    async with AsyncSessionLocal() as db:
        for q in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: '{q}' (length: {len(q)})")
            print(f"{'='*60}")

            # Normalize
            normalized = Normalizer.clean(q)
            terms = normalized.split()
            print(f"Normalized: '{normalized}'")
            print(f"Terms: {terms}")

            # Build query
            stmt = (
                select(Recording)
                .options(
                    selectinload(Recording.work).selectinload(Work.artist)
                )
                .join(Recording.work)
                .join(Work.artist)
            )

            # Apply multi-term search
            for word in terms:
                word_pattern = f"%{word}%"
                stmt = stmt.where(
                    or_(
                        Artist.name.ilike(word_pattern),
                        Recording.title.ilike(word_pattern),
                        Work.title.ilike(word_pattern),
                    )
                )

            # Execute
            result = await db.execute(stmt.limit(10))
            recordings = result.scalars().all()

            print(f"\nResults: {len(recordings)}")
            for r in recordings[:5]:
                artist_name = r.work.artist.name if r.work and r.work.artist else "Unknown"
                print(f"  - {artist_name} - {r.title}")

if __name__ == "__main__":
    asyncio.run(debug_search())

