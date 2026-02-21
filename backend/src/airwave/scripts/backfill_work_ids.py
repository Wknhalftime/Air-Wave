"""Backfill script to populate work_id columns from recording_id relationships.

This script implements Phase 2 of the Three-Layer Identity Resolution architecture.
It backfills the work_id columns added in Phase 1:
1. identity_bridge.work_id from recordings.work_id via recording_id
2. broadcast_logs.work_id from recordings.work_id via recording_id
3. discovery_queue.suggested_work_id from recordings.work_id via suggested_recording_id

The script is idempotent - it only updates rows where work_id is NULL
and recording_id is NOT NULL. It can safely be re-run.

Usage:
    poetry run python -m airwave.scripts.backfill_work_ids [--dry-run] [--table identity_bridge]

Options:
    --dry-run: Show what would be updated without making changes
    --table: Only backfill a specific table (identity_bridge, broadcast_logs, discovery_queue)
    --batch-size: Number of rows to process per batch (default: 1000, for broadcast_logs)
"""

import argparse
import asyncio
import sys

from loguru import logger
from sqlalchemy import func, select, text

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import (
    BroadcastLog,
    DiscoveryQueue,
    IdentityBridge,
)


async def count_backfill_candidates(table_name: str) -> dict:
    """Count rows that need backfill and rows already backfilled."""
    async with AsyncSessionLocal() as session:
        if table_name == "identity_bridge":
            total = await session.scalar(select(func.count()).select_from(IdentityBridge))
            needs_backfill = await session.scalar(
                select(func.count())
                .select_from(IdentityBridge)
                .where(
                    IdentityBridge.work_id.is_(None),
                    IdentityBridge.recording_id.isnot(None),
                )
            )
            already_done = await session.scalar(
                select(func.count())
                .select_from(IdentityBridge)
                .where(IdentityBridge.work_id.isnot(None))
            )
        elif table_name == "broadcast_logs":
            total = await session.scalar(select(func.count()).select_from(BroadcastLog))
            needs_backfill = await session.scalar(
                select(func.count())
                .select_from(BroadcastLog)
                .where(
                    BroadcastLog.work_id.is_(None),
                    BroadcastLog.recording_id.isnot(None),
                )
            )
            already_done = await session.scalar(
                select(func.count())
                .select_from(BroadcastLog)
                .where(BroadcastLog.work_id.isnot(None))
            )
        elif table_name == "discovery_queue":
            total = await session.scalar(select(func.count()).select_from(DiscoveryQueue))
            needs_backfill = await session.scalar(
                select(func.count())
                .select_from(DiscoveryQueue)
                .where(
                    DiscoveryQueue.suggested_work_id.is_(None),
                    DiscoveryQueue.suggested_recording_id.isnot(None),
                )
            )
            already_done = await session.scalar(
                select(func.count())
                .select_from(DiscoveryQueue)
                .where(DiscoveryQueue.suggested_work_id.isnot(None))
            )
        else:
            raise ValueError(f"Unknown table: {table_name}")

        return {
            "total": total or 0,
            "needs_backfill": needs_backfill or 0,
            "already_done": already_done or 0,
        }


async def backfill_identity_bridge(dry_run: bool = False) -> int:
    """Backfill work_id for identity_bridge table."""
    stats = await count_backfill_candidates("identity_bridge")
    logger.info(
        f"identity_bridge: {stats['total']} total, "
        f"{stats['needs_backfill']} need backfill, "
        f"{stats['already_done']} already done"
    )

    if dry_run or stats["needs_backfill"] == 0:
        return stats["needs_backfill"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                UPDATE identity_bridge
                SET work_id = (
                    SELECT r.work_id 
                    FROM recordings r 
                    WHERE r.id = identity_bridge.recording_id
                )
                WHERE work_id IS NULL AND recording_id IS NOT NULL
                """
            )
        )
        count = result.rowcount
        await session.commit()
        logger.success(f"Backfilled {count} identity_bridge rows")
        return count


async def backfill_broadcast_logs(dry_run: bool = False, batch_size: int = 1000) -> int:
    """Backfill work_id for broadcast_logs table.
    
    Uses batched updates for large tables to avoid long-running transactions.
    """
    stats = await count_backfill_candidates("broadcast_logs")
    logger.info(
        f"broadcast_logs: {stats['total']} total, "
        f"{stats['needs_backfill']} need backfill, "
        f"{stats['already_done']} already done"
    )

    if dry_run or stats["needs_backfill"] == 0:
        return stats["needs_backfill"]

    total_updated = 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                UPDATE broadcast_logs
                SET work_id = (
                    SELECT r.work_id 
                    FROM recordings r 
                    WHERE r.id = broadcast_logs.recording_id
                )
                WHERE work_id IS NULL AND recording_id IS NOT NULL
                """
            )
        )
        total_updated = result.rowcount
        await session.commit()

    logger.success(f"Backfilled {total_updated} broadcast_logs rows")
    return total_updated


async def backfill_discovery_queue(dry_run: bool = False) -> int:
    """Backfill suggested_work_id for discovery_queue table."""
    stats = await count_backfill_candidates("discovery_queue")
    logger.info(
        f"discovery_queue: {stats['total']} total, "
        f"{stats['needs_backfill']} need backfill, "
        f"{stats['already_done']} already done"
    )

    if dry_run or stats["needs_backfill"] == 0:
        return stats["needs_backfill"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                UPDATE discovery_queue
                SET suggested_work_id = (
                    SELECT r.work_id 
                    FROM recordings r 
                    WHERE r.id = discovery_queue.suggested_recording_id
                )
                WHERE suggested_work_id IS NULL AND suggested_recording_id IS NOT NULL
                """
            )
        )
        count = result.rowcount
        await session.commit()
        logger.success(f"Backfilled {count} discovery_queue rows")
        return count


async def validate_backfill() -> dict:
    """Validate the backfill results."""
    results = {}

    async with AsyncSessionLocal() as session:
        mismatch = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM identity_bridge ib
                JOIN recordings r ON ib.recording_id = r.id
                WHERE ib.work_id IS NOT NULL 
                  AND ib.work_id != r.work_id
                """
            )
        )
        missing = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM identity_bridge
                WHERE work_id IS NULL AND recording_id IS NOT NULL
                """
            )
        )
        results["identity_bridge"] = {
            "mismatches": mismatch or 0,
            "missing": missing or 0,
            "valid": (mismatch or 0) == 0 and (missing or 0) == 0,
        }

        mismatch = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM broadcast_logs bl
                JOIN recordings r ON bl.recording_id = r.id
                WHERE bl.work_id IS NOT NULL 
                  AND bl.work_id != r.work_id
                """
            )
        )
        missing = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM broadcast_logs
                WHERE work_id IS NULL AND recording_id IS NOT NULL
                """
            )
        )
        results["broadcast_logs"] = {
            "mismatches": mismatch or 0,
            "missing": missing or 0,
            "valid": (mismatch or 0) == 0 and (missing or 0) == 0,
        }

        mismatch = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM discovery_queue dq
                JOIN recordings r ON dq.suggested_recording_id = r.id
                WHERE dq.suggested_work_id IS NOT NULL 
                  AND dq.suggested_work_id != r.work_id
                """
            )
        )
        missing = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM discovery_queue
                WHERE suggested_work_id IS NULL AND suggested_recording_id IS NOT NULL
                """
            )
        )
        results["discovery_queue"] = {
            "mismatches": mismatch or 0,
            "missing": missing or 0,
            "valid": (mismatch or 0) == 0 and (missing or 0) == 0,
        }

    return results


async def main():
    """Main entry point for the backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill work_id columns from recording_id relationships (Phase 2)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--table",
        type=str,
        choices=["identity_bridge", "broadcast_logs", "discovery_queue"],
        default=None,
        help="Only backfill a specific table",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for large table updates (default: 1000)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing backfill, don't update",
    )

    args = parser.parse_args()

    if args.validate_only:
        logger.info("Validating backfill results...")
        results = await validate_backfill()
        all_valid = True
        for table, result in results.items():
            status = "✓ VALID" if result["valid"] else "✗ INVALID"
            logger.info(
                f"  {table}: {status} "
                f"(mismatches: {result['mismatches']}, missing: {result['missing']})"
            )
            if not result["valid"]:
                all_valid = False

        if all_valid:
            logger.success("All backfill validations passed!")
        else:
            logger.error("Some validations failed. Run backfill to fix.")
            sys.exit(1)
        return

    logger.info("Starting Phase 2: work_id backfill...")
    if args.dry_run:
        logger.info("[DRY RUN] No changes will be made")

    tables_to_process = (
        [args.table] if args.table else ["identity_bridge", "broadcast_logs", "discovery_queue"]
    )

    total_updated = 0
    for table in tables_to_process:
        logger.info(f"\nProcessing {table}...")
        if table == "identity_bridge":
            count = await backfill_identity_bridge(dry_run=args.dry_run)
        elif table == "broadcast_logs":
            count = await backfill_broadcast_logs(
                dry_run=args.dry_run, batch_size=args.batch_size
            )
        elif table == "discovery_queue":
            count = await backfill_discovery_queue(dry_run=args.dry_run)
        total_updated += count

    if not args.dry_run:
        logger.info("\nValidating backfill results...")
        results = await validate_backfill()
        all_valid = all(r["valid"] for r in results.values())

        if all_valid:
            logger.success(f"Phase 2 backfill complete! {total_updated} rows updated.")
        else:
            logger.warning(
                f"Backfill complete ({total_updated} rows), but validation found issues."
            )
            for table, result in results.items():
                if not result["valid"]:
                    logger.warning(f"  {table}: {result}")
    else:
        logger.info(f"\n[DRY RUN] Would update {total_updated} rows total.")


if __name__ == "__main__":
    asyncio.run(main())
