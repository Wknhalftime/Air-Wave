import argparse
import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import or_, select, update
from sqlalchemy.orm import selectinload

from airwave.core.db import AsyncSessionLocal, init_db
from airwave.core.logger import setup_logging
from airwave.core.models import (
    BroadcastLog,
    ImportBatch,
    Recording,
    Work,
)
from airwave.core.task_store import TaskStore
from airwave.core.utils import guess_station_from_filename
from airwave.core.vector_db import VectorDB
from airwave.worker.importer import CSVImporter
from airwave.worker.matcher import Matcher
from airwave.worker.scanner import FileScanner


async def run_import(file_path: str, task_id: Optional[str] = None) -> None:
    """Executes a single file import job.

    Args:
        file_path: Absolute path to the CSV file.
        task_id: Optional Task ID for progress tracking.
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"File not found: {file_path}")
        if task_id:
            TaskStore.complete_task(
                task_id, success=False, error="File not found"
            )
        return

    async with AsyncSessionLocal() as session:
        # Create Batch Record
        batch = ImportBatch(
            filename=path.name,
            status="PROCESSING",
            total_rows=0,  # Will update later
            processed_rows=0,
        )
        session.add(batch)
        await session.commit()

        try:
            importer = CSVImporter(session)
            total_rows = 0

            # Accurate row count for progress
            if task_id:
                TaskStore.update_progress(task_id, 0, "Counting rows...")
                # Fast line count
                with open(path, "rb") as f:
                    actual_rows = sum(1 for _ in f) - 1  # Subtract Header
                batch.total_rows = actual_rows
                TaskStore.update_total(
                    task_id, actual_rows, f"Importing {actual_rows} rows..."
                )

            # Process in chunks (Limit 400 to avoid SQLite variable limit)
            for chunk in importer.read_csv_stream(str(path), chunk_size=400):
                count = await importer.process_batch(batch.id, chunk)
                total_rows += count
                logger.info(f"Imported {total_rows} rows...")

                # Update progress
                if task_id:
                    TaskStore.update_progress(
                        task_id, total_rows, f"Imported {total_rows} rows"
                    )

            # Update Batch
            batch.status = "COMPLETED"
            batch.processed_rows = total_rows  # Use processed_rows instead of row_count for consistency
            await session.commit()
            logger.success(f"Import complete! Total rows: {total_rows}")

            if task_id:
                # Set final accurate total in case of small discrepancies
                TaskStore.update_total(task_id, total_rows)
                TaskStore.complete_task(task_id, success=True)

            await session.commit()

        except Exception as e:
            logger.exception("Import failed")
            batch.status = "FAILED"
            batch.error_log = str(e)
            await session.commit()

            if task_id:
                TaskStore.complete_task(task_id, success=False, error=str(e))


async def run_scan(task_id: Optional[str] = None) -> None:
    """Phase 2: Populate Library Tracks from Raw Logs."""
    try:
        async with AsyncSessionLocal() as session:
            matcher = Matcher(session)
            logger.info("Starting Library Scan...")

            # Step 1: Rebuild Discovery Queue (was promote)
            # We no longer auto-promote. We queue for verification.
            total_items = await matcher.run_discovery(task_id)
            logger.success(
                f"Discovery Queue Rebuilt. {total_items} items awaiting verification."
            )

            # Step 2: Link Orphaned Logs?
            # run_discovery checks for suggestions but doesn't hard-link logs to recordings yet
            # unless we implement an 'Auto-Link' policy.
            # For now, we trust the Queue Rebuild to be the primary 'Scan' action.
            
            if task_id:
                TaskStore.complete_task(task_id, success=True)

    except Exception as e:
        logger.exception("Scan failed")
        if task_id:
            TaskStore.complete_task(task_id, success=False, error=str(e))


async def run_re_evaluate(task_id: Optional[str] = None) -> None:
    """Re-evaluate unmatched and flagged broadcast logs with current thresholds."""
    try:
        async with AsyncSessionLocal() as session:
            matcher = Matcher(session)
            logger.info(
                "Starting re-evaluation of unmatched and flagged logs..."
            )

            # Query UNIQUE (raw_artist, raw_title) pairs that are either unmatched OR flagged
            # This is much more efficient than processing 2.4M individual logs
            stmt = (
                select(BroadcastLog.raw_artist, BroadcastLog.raw_title)
                .where(
                    or_(
                        BroadcastLog.recording_id.is_(None),  # Unmatched
                        BroadcastLog.match_reason.like(
                            "%Review%"
                        ),  # Flagged for review
                    )
                )
                .distinct()
            )

            result = await session.execute(stmt)
            unique_pairs = result.all()

            total_pairs = len(unique_pairs)
            logger.info(f"Found {total_pairs} unique song pairs to re-evaluate")

            if task_id:
                TaskStore.update_total(task_id, total_pairs)
                TaskStore.update_progress(
                    task_id, 0, f"Re-evaluating {total_pairs} unique songs..."
                )

            # Convert to list of tuples for batch matching
            queries = [(ra, rt) for ra, rt in unique_pairs]

            # Batch match all unique pairs with current thresholds
            results = await matcher.match_batch(queries)

            # Update logs in bulk for each unique pair
            updated_count = 0
            processed = 0

            for raw_artist, raw_title in unique_pairs:
                key = (raw_artist, raw_title)

                if key in results:
                    match_id, match_reason = results[key]

                    # Bulk update ALL logs with this exact raw_artist/raw_title pair
                    stmt_update = (
                        update(BroadcastLog)
                        .where(
                            BroadcastLog.raw_artist == raw_artist,
                            BroadcastLog.raw_title == raw_title,
                            or_(
                                BroadcastLog.recording_id.is_(None),
                                BroadcastLog.match_reason.like("%Review%"),
                            ),
                        )
                        .values(
                            recording_id=match_id, match_reason=match_reason
                        )
                    )

                    result = await session.execute(stmt_update)
                    rows_updated = result.rowcount

                    if rows_updated > 0:
                        updated_count += rows_updated

                processed += 1

                # Update progress every 100 pairs
                if task_id and processed % 100 == 0:
                    TaskStore.update_progress(
                        task_id,
                        processed,
                        f"Processed {processed}/{total_pairs} songs ({updated_count} logs updated)",
                    )

            await session.commit()
            logger.success(
                f"Re-evaluation complete. Updated {updated_count} logs across {total_pairs} unique songs."
            )

            if task_id:
                TaskStore.complete_task(task_id, success=True)

    except Exception as e:
        logger.exception("Re-evaluation failed")
        if task_id:
            TaskStore.complete_task(task_id, success=False, error=str(e))


async def run_reindex() -> None:
    """Populate VectorDB from SQL Tracks."""
    logger.info("Re-indexing all tracks to VectorDB...")
    vector_db = VectorDB()

    async with AsyncSessionLocal() as session:
        # Join Rec -> Work -> Artist
        stmt = select(Recording).options(
            selectinload(Recording.work).selectinload(Work.artist)
        )
        result = await session.stream(stmt)

        count = 0
        batch = []
        batch_size = 100

        async for row in result:
            rec = row.Recording
            if rec.work and rec.work.artist:
                # Format: "Artist - Title"
                batch.append((rec.id, rec.work.artist.name, rec.title))

            if len(batch) >= batch_size:
                vector_db.add_tracks(batch)
                count += len(batch)
                logger.info(f"Indexed {count} recordings...")
                batch = []

        if batch:
            vector_db.add_tracks(batch)
            count += len(batch)

    logger.success(f"Re-indexing complete. Total: {count}")


async def run_sync_files(path: str, task_id: Optional[str] = None) -> None:
    """Sync local audio files to library.

    Args:
        path: Directory path to scan.
        task_id: Optional Task ID for progress tracking.
    """
    logger.info(f"Syncing files from: {path}")

    async with AsyncSessionLocal() as session:
        scanner = FileScanner(session)
        stats = await scanner.scan_directory(path, task_id)

    logger.info("Sync Complete.")
    logger.info(f"Processed: {stats.processed}, Skipped: {stats.skipped}, Created: {stats.created}, Moved: {stats.moved}")


async def run_bulk_import(root_dir: str, task_id: str = None):
    """Recursively imports CSV files from a directory.
    Uses CSVImporter and tracks progress via TaskStore.
    """
    import glob
    import os

    from airwave.core.task_store import TaskStore

    path = Path(root_dir)
    if not path.exists():
        logger.error(f"Directory not found: {root_dir}")
        if task_id:
            TaskStore.complete_task(
                task_id, success=False, error=f"Directory not found: {root_dir}"
            )
        return

    logger.info(f"Scanning {root_dir}...")

    # Recursively find all CSV files
    # Only support .csv for now
    csv_files = glob.glob(os.path.join(root_dir, "**", "*.csv"), recursive=True)
    total_files = len(csv_files)
    logger.info(f"Found {total_files} CSV files to process.")

    if task_id:
        TaskStore.update_progress(
            task_id, 0, f"Found {total_files} files. Starting import..."
        )
        # We can track "files processed" rather than rows for the parent task?
        # Or just use total files as the unit.
        TaskStore.update_total(task_id, total_files)

    for i, file_path in enumerate(csv_files, 1):
        async with AsyncSessionLocal() as session:
            importer = CSVImporter(session)
            logger.info(f"[{i}/{total_files}] Processing: {file_path}")

            filename = os.path.basename(file_path)

            # Infer Station from Filename Strategy:
            station_guess = guess_station_from_filename(filename)

            # Create Import Batch
            batch = ImportBatch(
                filename=filename,
                status="PROCESSING",
                total_rows=0,
                processed_rows=0,
            )
            session.add(batch)
            await session.commit()

            try:
                processed_count = 0

                # Stream read chunks
                for chunk in importer.read_csv_stream(file_path):
                    # Process batch with INFERRED STATION
                    count = await importer.process_batch(
                        batch.id, chunk, default_station=station_guess
                    )
                    processed_count += count

                # Update Batch Status
                batch.status = "COMPLETED"
                batch.processed_rows = processed_count
                await session.commit()

                if task_id:
                    TaskStore.update_progress(
                        task_id,
                        i,
                        f"Imported {filename} as {station_guess} ({processed_count} rows)",
                    )

            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}")
                batch.status = "FAILED"
                batch.error_log = str(
                    e
                )  # Fixed: field is error_log, not error_message
                await session.commit()
                # Don't fail the whole task, just log error

    if task_id:
        TaskStore.complete_task(task_id, success=True)
    logger.success(f"Bulk import complete. Processed {total_files} files.")


async def run_discovery_task(task_id: Optional[str] = None) -> None:
    """Rebuild the DiscoveryQueue from unmatched logs.

    This is the background task wrapper for the Matcher.run_discovery method.

    Args:
        task_id: Optional Task ID for progress tracking.
    """
    try:
        async with AsyncSessionLocal() as session:
            matcher = Matcher(session)
            logger.info("Starting Discovery Queue Rebuild...")

            total_items = await matcher.run_discovery(task_id=task_id)

            logger.success(f"Discovery complete. Queue size: {total_items}")

            if task_id:
                TaskStore.complete_task(task_id, success=True)
    except Exception as e:
        logger.exception("Discovery failed")
        if task_id:
            TaskStore.complete_task(task_id, success=False, error=str(e))


async def run_debug_match(artist: str, title: str) -> None:
    """Debug the matching logic for a specific pair.

    Args:
        artist: Artist name.
        title: Title name.
    """
    logger.info(f"Debugging match for: '{artist}' - '{title}'")

    async with AsyncSessionLocal() as session:
        matcher = Matcher(session)
        # matches returns (id, reason)
        match_id, reason = await matcher.find_match(artist, title)

        if match_id:
            stmt = (
                select(Recording)
                .options(
                    selectinload(Recording.work).selectinload(Work.artist),
                    selectinload(Recording.files),
                )
                .where(Recording.id == match_id)
            )

            res = await session.execute(stmt)
            track = res.scalar_one()

            artist_name = (
                track.work.artist.name
                if track.work and track.work.artist
                else "Unknown"
            )

            logger.success(f"MATCH FOUND: ID {track.id}")
            logger.info(f"Track: {artist_name} - {track.title}")
            logger.info(f"Reason: {reason}")
            if track.files:
                logger.info(f"Path: {track.files[0].path}")
        else:
            logger.warning("NO MATCH FOUND.")


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Airwave Worker")
    subparsers = parser.add_subparsers(dest="command")

    # ... existing commands ...
    # Import Command
    import_parser = subparsers.add_parser(
        "import", help="Import a CSV log file"
    )
    import_parser.add_argument("file", help="Path to CSV file")

    # Init DB Command
    subparsers.add_parser("init-db", help="Initialize Database Tables")

    # Scan Command (Phase 2)
    subparsers.add_parser("scan", help="Scan logs and populate Library Tracks")

    # Reindex Command
    subparsers.add_parser("reindex", help="Rebuild Vector Search Index")

    # Sync Files Command (Phase 3)
    sync_parser = subparsers.add_parser(
        "sync-files", help="Sync local audio files"
    )
    sync_parser.add_argument("path", help="Directory path to scan")

    # Debug Match Command (Phase 4)
    debug_parser = subparsers.add_parser(
        "debug-match", help="Debug matching logic"
    )
    debug_parser.add_argument("artist", help="Artist name")
    debug_parser.add_argument("title", help="Title name")

    args = parser.parse_args()

    if args.command == "init-db":
        asyncio.run(init_db())
        logger.info("Database initialized.")

    elif args.command == "import":
        # Ensure DB is ready
        asyncio.run(init_db())
        asyncio.run(run_import(args.file))

    elif args.command == "scan":
        asyncio.run(run_scan())

    elif args.command == "reindex":
        asyncio.run(run_reindex())

    elif args.command == "sync-files":
        asyncio.run(run_sync_files(args.path))

    elif args.command == "debug-match":
        asyncio.run(run_debug_match(args.artist, args.title))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
