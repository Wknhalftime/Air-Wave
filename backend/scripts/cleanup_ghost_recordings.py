#!/usr/bin/env python3
"""
Cleanup Ghost Recordings Script

This script removes "ghost" Virtual Recordings that were created by the old
scan_and_promote logic. Ghost recordings are defined as:
- Recordings with no LibraryFile (has_file == False)
- Recordings with is_verified == False (not user-verified)

The cleanup process:
1. Finds all ghost recordings
2. Deletes IdentityBridges pointing to them
3. Sets BroadcastLog.recording_id to NULL for logs pointing to them
4. Deletes the ghost recordings
5. Optionally deletes orphaned Works and Artists

Usage:
    python scripts/cleanup_ghost_recordings.py [--dry-run] [--delete-orphans]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from sqlalchemy import delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.core.database import AsyncSessionLocal
from airwave.core.models import (
    Artist,
    BroadcastLog,
    IdentityBridge,
    LibraryFile,
    Recording,
    Work,
)


async def cleanup_ghosts(dry_run: bool = True, delete_orphans: bool = False):
    """Remove ghost recordings from the database.
    
    Args:
        dry_run: If True, only report what would be deleted without making changes.
        delete_orphans: If True, also delete orphaned Works and Artists.
    """
    async with AsyncSessionLocal() as session:
        logger.info("Starting ghost recording cleanup...")
        
        # 1. Find Ghost Recordings
        # Ghost = No LibraryFile AND is_verified == False
        ghost_stmt = (
            select(Recording)
            .outerjoin(LibraryFile, Recording.id == LibraryFile.recording_id)
            .where(
                Recording.is_verified == False,
                LibraryFile.id.is_(None)
            )
        )
        
        result = await session.execute(ghost_stmt)
        ghosts = result.scalars().all()
        ghost_ids = [g.id for g in ghosts]
        
        logger.info(f"Found {len(ghosts)} ghost recordings")
        
        if not ghosts:
            logger.success("No ghost recordings found. Database is clean!")
            return
        
        # Show sample
        logger.info("Sample ghost recordings:")
        for ghost in ghosts[:10]:
            logger.info(f"  - ID {ghost.id}: {ghost.title}")
        
        if dry_run:
            logger.warning("DRY RUN MODE - No changes will be made")
            
            # Count affected entities
            bridge_count_stmt = select(func.count(IdentityBridge.id)).where(
                IdentityBridge.recording_id.in_(ghost_ids)
            )
            bridge_count = (await session.execute(bridge_count_stmt)).scalar()
            
            log_count_stmt = select(func.count(BroadcastLog.id)).where(
                BroadcastLog.recording_id.in_(ghost_ids)
            )
            log_count = (await session.execute(log_count_stmt)).scalar()
            
            logger.info(f"Would delete {bridge_count} identity bridges")
            logger.info(f"Would unlink {log_count} broadcast logs")
            logger.info(f"Would delete {len(ghosts)} ghost recordings")
            
            return
        
        # 2. Delete IdentityBridges
        logger.info("Deleting identity bridges...")
        bridge_delete_stmt = delete(IdentityBridge).where(
            IdentityBridge.recording_id.in_(ghost_ids)
        )
        bridge_result = await session.execute(bridge_delete_stmt)
        logger.success(f"Deleted {bridge_result.rowcount} identity bridges")
        
        # 3. Unlink BroadcastLogs
        logger.info("Unlinking broadcast logs...")
        log_update_stmt = (
            update(BroadcastLog)
            .where(BroadcastLog.recording_id.in_(ghost_ids))
            .values(recording_id=None, match_reason=None)
        )
        log_result = await session.execute(log_update_stmt)
        logger.success(f"Unlinked {log_result.rowcount} broadcast logs")
        
        # 4. Delete Ghost Recordings
        logger.info("Deleting ghost recordings...")
        recording_delete_stmt = delete(Recording).where(
            Recording.id.in_(ghost_ids)
        )
        recording_result = await session.execute(recording_delete_stmt)
        logger.success(f"Deleted {recording_result.rowcount} ghost recordings")
        
        # 5. Optionally delete orphaned Works and Artists
        if delete_orphans:
            logger.info("Cleaning up orphaned works...")
            orphan_works_stmt = (
                delete(Work)
                .where(
                    ~Work.id.in_(
                        select(Recording.work_id).distinct()
                    )
                )
            )
            work_result = await session.execute(orphan_works_stmt)
            logger.success(f"Deleted {work_result.rowcount} orphaned works")
            
            # Note: We don't delete orphaned artists as they might be referenced
            # by other entities or be useful for future matching
        
        await session.commit()
        logger.success("✅ Ghost cleanup complete!")


async def main():
    parser = argparse.ArgumentParser(description="Cleanup ghost recordings")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without making changes"
    )
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help="Also delete orphaned Works (not recommended)"
    )
    
    args = parser.parse_args()
    
    await cleanup_ghosts(dry_run=args.dry_run, delete_orphans=args.delete_orphans)


if __name__ == "__main__":
    asyncio.run(main())

