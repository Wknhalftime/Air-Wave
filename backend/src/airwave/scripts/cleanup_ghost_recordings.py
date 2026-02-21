"""Cleanup ghost recordings (no LibraryFile, not verified).

Usage:
    poetry run python -m airwave.scripts.cleanup_ghost_recordings [--dry-run] [--delete-orphans]
"""
import argparse
import asyncio

from loguru import logger
from sqlalchemy import delete, func, select, update

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import BroadcastLog, IdentityBridge, LibraryFile, Recording, Work


async def cleanup_ghosts(dry_run: bool = True, delete_orphans: bool = False):
    async with AsyncSessionLocal() as session:
        logger.info("Starting ghost recording cleanup...")
        ghost_stmt = (
            select(Recording)
            .outerjoin(LibraryFile, Recording.id == LibraryFile.recording_id)
            .where(Recording.is_verified == False, LibraryFile.id.is_(None))
        )
        result = await session.execute(ghost_stmt)
        ghosts = result.scalars().all()
        ghost_ids = [g.id for g in ghosts]
        logger.info("Found %d ghost recordings" % len(ghosts))
        if not ghosts:
            logger.success("No ghost recordings found. Database is clean!")
            return
        for ghost in ghosts[:10]:
            logger.info("  - ID %s: %s" % (ghost.id, ghost.title))
        if dry_run:
            logger.warning("DRY RUN MODE - No changes will be made")
            bridge_count = (await session.execute(
                select(func.count(IdentityBridge.id)).where(
                    IdentityBridge.recording_id.in_(ghost_ids)
                )
            )).scalar()
            log_count = (await session.execute(
                select(func.count(BroadcastLog.id)).where(
                    BroadcastLog.recording_id.in_(ghost_ids)
                )
            )).scalar()
            logger.info("Would delete %s identity bridges" % bridge_count)
            logger.info("Would unlink %s broadcast logs" % log_count)
            logger.info("Would delete %d ghost recordings" % len(ghosts))
            return
        await session.execute(delete(IdentityBridge).where(
            IdentityBridge.recording_id.in_(ghost_ids)
        ))
        await session.execute(
            update(BroadcastLog)
            .where(BroadcastLog.recording_id.in_(ghost_ids))
            .values(recording_id=None, match_reason=None)
        )
        await session.execute(delete(Recording).where(Recording.id.in_(ghost_ids)))
        if delete_orphans:
            await session.execute(
                delete(Work).where(~Work.id.in_(select(Recording.work_id).distinct()))
            )
        await session.commit()
        logger.success("Ghost cleanup complete!")


async def main():
    parser = argparse.ArgumentParser(description="Cleanup ghost recordings")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete-orphans", action="store_true")
    args = parser.parse_args()
    await cleanup_ghosts(dry_run=args.dry_run, delete_orphans=args.delete_orphans)


if __name__ == "__main__":
    asyncio.run(main())
