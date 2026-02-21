"""CLI entry point for bulk importing radio station logs from CSV files.

Run from backend directory:
    poetry run python -m airwave.worker.bulk_import

Scans settings.DATA_DIR / "imports" for CSV files and processes them using
run_bulk_import (station inference from filename, progress via task_store when
invoked from API). When run as CLI, no task progress is reported.
"""

import asyncio

from loguru import logger

from airwave.core.config import settings
from airwave.worker.main import run_bulk_import


async def main() -> None:
    """Discover CSVs in data/imports and run bulk import."""
    root_dir = settings.DATA_DIR / "imports"
    if not root_dir.exists():
        logger.error(f"Import directory not found: {root_dir}")
        return

    logger.info(f"Bulk import starting from {root_dir}...")
    await run_bulk_import(str(root_dir), task_id=None)
    logger.success("Bulk import complete.")


if __name__ == "__main__":
    asyncio.run(main())
