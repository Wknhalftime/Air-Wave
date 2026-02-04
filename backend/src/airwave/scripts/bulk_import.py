"""Utility script for bulk importing radio station logs from CSV files."""

import asyncio
import glob
import os
from datetime import datetime, timezone

from airwave.core.config import settings
from airwave.core.db import AsyncSessionLocal, init_db
from airwave.core.models import ImportBatch
from airwave.worker.importer import CSVImporter
from loguru import logger


async def main() -> None:
    """Main entry point for the bulk import process.

    Discovers CSV files in the data/imports directory and processes them
    using the CSVImporter worker.
    """
    root_dir = settings.DATA_DIR / "imports"
    if not root_dir.exists():
        logger.error(f"Import directory not found: {root_dir}")
        return

    logger.info(f"Scanning {root_dir}...")

    # Initialize DB (if needed)
    await init_db()

    # Recursively find all CSV files
    csv_files = glob.glob(str(root_dir / "**" / "*.csv"), recursive=True)
    total_files = len(csv_files)
    logger.info(f"Found {total_files} CSV files to process.")

    async with AsyncSessionLocal() as session:
        importer = CSVImporter(session)

        for i, file_path in enumerate(csv_files, 1):
            logger.info(f"[{i}/{total_files}] Processing: {file_path}")

            # Create Import Batch for this file
            batch = ImportBatch(
                filename=os.path.basename(file_path),
                status="processing",
                total_rows=0,
                processed_rows=0,
            )
            session.add(batch)
            await session.commit()

            try:
                processed_count = 0

                # Stream read chunks
                for chunk in importer.read_csv_stream(file_path):
                    # Process batch
                    count = await importer.process_batch(batch.id, chunk)
                    processed_count += count
                    logger.debug(f"  - Processed {processed_count} rows...")

                # Update Batch Status
                batch.status = "completed"
                batch.processed_rows = processed_count
                batch.completed_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(f"  -> Completed: {processed_count} rows.")

            except Exception as e:
                logger.exception(f"Failed to process {file_path}")
                batch.status = "failed"
                batch.error_log = str(e)
                batch.completed_at = datetime.now(timezone.utc)
                await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
