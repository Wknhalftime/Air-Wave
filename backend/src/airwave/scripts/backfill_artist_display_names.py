"""Backfill script to populate display_name for existing artists.

Usage:
    poetry run python -m airwave.scripts.backfill_artist_display_names [--batch-size 50] [--limit 100]
"""
import argparse
import asyncio
from typing import Optional

from loguru import logger
from sqlalchemy import and_, or_, select, update

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import Artist
from airwave.worker.scanner import FileScanner


async def backfill_artists_with_mbids(
    batch_size: int = 50, limit: Optional[int] = None, dry_run: bool = False
):
    async with AsyncSessionLocal() as session:
        scanner = FileScanner(session)
        if dry_run:
            stmt = select(Artist).where(
                and_(
                    Artist.musicbrainz_id.isnot(None),
                    or_(Artist.display_name.is_(None), Artist.display_name == Artist.name)
                )
            )
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            artists = result.scalars().all()
            logger.info(f"[DRY RUN] Would update {len(artists)} artists with MBIDs")
            for artist in artists[:10]:
                logger.info(f"  - {artist.name} (MBID: {artist.musicbrainz_id})")
            if len(artists) > 10:
                logger.info(f"  ... and {len(artists) - 10} more")
            return
        stats = await scanner.update_artist_display_names_from_musicbrainz(
            batch_size=batch_size, limit=limit
        )
        logger.success(
            f"Backfill complete: {stats['updated']} updated, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )


async def backfill_artists_without_mbids():
    async with AsyncSessionLocal() as session:
        stmt = (
            update(Artist)
            .where(and_(Artist.musicbrainz_id.is_(None), Artist.display_name.is_(None)))
            .values(display_name=Artist.name)
        )
        result = await session.execute(stmt)
        count = result.rowcount
        await session.commit()
        logger.info(f"Set display_name = name for {count} artists without MBIDs")


async def main():
    parser = argparse.ArgumentParser(description="Backfill display_name for artists")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-mbid", action="store_true")
    args = parser.parse_args()
    logger.info("Starting artist display_name backfill...")
    if not args.skip_mbid:
        await backfill_artists_with_mbids(
            batch_size=args.batch_size, limit=args.limit, dry_run=args.dry_run
        )
    if not args.dry_run:
        await backfill_artists_without_mbids()
    logger.success("Backfill complete!")


if __name__ == "__main__":
    asyncio.run(main())
