"""CLI entry point for scanning a directory and syncing audio files to the library.

Run from backend directory:
    poetry run python -m airwave.worker.scan_library <directory_path>

Uses run_sync_files (FileScanner) to discover and index audio files.
"""

import asyncio
import sys

from loguru import logger

from airwave.worker.main import run_sync_files


async def main(path: str) -> None:
    """Scan directory and sync to library."""
    if not path:
        logger.error("Usage: python -m airwave.worker.scan_library <directory_path>")
        sys.exit(1)

    from pathlib import Path
    target = Path(path)
    if not target.exists():
        logger.error(f"Path does not exist: {path}")
        sys.exit(1)

    logger.info(f"Scanning directory: {target.resolve()}...")
    await run_sync_files(path, task_id=None)
    logger.success("Scan complete.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        asyncio.run(main(path))
    except KeyboardInterrupt:
        print("\nScan interrupted.")
        sys.exit(130)
