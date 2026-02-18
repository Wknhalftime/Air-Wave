"""Quick debug script to test scanner with a single file."""

import asyncio
import sys
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent / "backend" / "src"))

from airwave.core.database import get_async_session_maker
from airwave.worker.scanner import FileScanner
from airwave.core.stats import ScanStats


async def test_scan():
    """Test scanning a single directory."""
    # Get database session
    session_maker = get_async_session_maker()
    
    async with session_maker() as session:
        scanner = FileScanner(session)
        stats = ScanStats()
        
        # Test with a single file
        test_file = Path(r"D:\Music\Test\test.flac")  # Replace with actual file path
        
        if not test_file.exists():
            print(f"❌ Test file not found: {test_file}")
            print("Please update the path in test_scan_debug.py")
            return
        
        print(f"🔍 Testing file: {test_file}")
        print(f"📊 Initial stats: {stats.to_dict()}")
        
        try:
            await scanner.process_file(test_file, stats)
            print(f"✅ File processed successfully!")
        except Exception as e:
            print(f"❌ Error processing file: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"📊 Final stats: {stats.to_dict()}")
        print(f"   - Created: {stats.created}")
        print(f"   - Skipped: {stats.skipped}")
        print(f"   - Errors: {stats.errors}")
        
        # Check if file was added to database
        from airwave.core.models import LibraryFile
        from sqlalchemy import select, func
        
        result = await session.execute(select(func.count()).select_from(LibraryFile))
        count = result.scalar()
        print(f"📁 Total files in database: {count}")


if __name__ == "__main__":
    asyncio.run(test_scan())

