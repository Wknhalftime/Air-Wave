import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from airwave.core.db import AsyncSessionLocal
from airwave.worker.scanner import FileScanner


async def run(path: str):
    target = Path(path)
    if not target.exists():
        print(f"Error: Path {path} does not exist.")
        return

    print(f"Scanning directory: {target.resolve()}...")

    async with AsyncSessionLocal() as session:
        scanner = FileScanner(session)
        stats = await scanner.scan_directory(str(target))
        print("\nScan Complete!")
        print(stats)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scan_library.py <directory_path>")
    else:
        try:
            asyncio.run(run(sys.argv[1]))
        except KeyboardInterrupt:
            print("\nScan interrupted.")
