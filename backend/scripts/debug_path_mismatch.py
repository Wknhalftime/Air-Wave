#!/usr/bin/env python3
"""Debug script to identify path normalization mismatches.

This script compares paths stored in the database with how they're normalized
during skip checks to identify mismatches.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select
from airwave.core.db import AsyncSessionLocal
from airwave.core.models import LibraryFile


async def debug_paths():
    """Compare database paths with normalized scanner paths."""
    async with AsyncSessionLocal() as session:
        # Get sample of paths from database
        stmt = select(LibraryFile.path).limit(50)
        result = await session.execute(stmt)
        db_paths = [row.path for row in result.all()]
        
        print(f"Found {len(db_paths)} sample paths in database\n")
        print("=" * 80)
        print("PATH NORMALIZATION DEBUG")
        print("=" * 80)
        
        mismatches = []
        for db_path in db_paths:
            # How scanner normalizes when loading index (line ~666)
            try:
                resolved_db = Path(db_path).resolve().as_posix()
            except (OSError, ValueError) as e:
                resolved_db = db_path.replace("\\", "/")
                print(f"⚠️  Could not resolve {db_path}: {e}")
            
            if sys.platform == "win32":
                normalized_db = resolved_db.lower()
            else:
                normalized_db = resolved_db
            
            # How scanner normalizes when checking skip (line ~1502)
            # Simulate what happens when we scan the same file
            try:
                file_path_obj = Path(db_path)
                if file_path_obj.exists():
                    resolved_check = file_path_obj.resolve().as_posix()
                else:
                    resolved_check = str(file_path_obj).replace("\\", "/")
                    print(f"⚠️  File doesn't exist: {db_path}")
            except Exception as e:
                resolved_check = str(db_path).replace("\\", "/")
                print(f"⚠️  Error resolving {db_path}: {e}")
            
            if sys.platform == "win32":
                normalized_check = resolved_check.lower()
            else:
                normalized_check = resolved_check
            
            # Check for mismatches
            if normalized_db != normalized_check:
                mismatches.append({
                    "db_path": db_path,
                    "normalized_db": normalized_db,
                    "normalized_check": normalized_check,
                    "resolved_db": resolved_db,
                    "resolved_check": resolved_check
                })
        
        if mismatches:
            print(f"\n❌ FOUND {len(mismatches)} PATH NORMALIZATION MISMATCHES:\n")
            for i, mismatch in enumerate(mismatches[:10], 1):  # Show first 10
                print(f"Mismatch {i}:")
                print(f"  DB Path:        {mismatch['db_path']}")
                print(f"  Resolved DB:    {mismatch['resolved_db']}")
                print(f"  Normalized DB:  {mismatch['normalized_db']}")
                print(f"  Resolved Check: {mismatch['resolved_check']}")
                print(f"  Normalized Check: {mismatch['normalized_check']}")
                print("-" * 80)
        else:
            print("\n✅ No path normalization mismatches found in sample")
        
        # Check if stored paths are already normalized
        print("\n" + "=" * 80)
        print("STORED PATH ANALYSIS")
        print("=" * 80)
        
        stored_lowercase = 0
        stored_mixed_case = 0
        for db_path in db_paths[:20]:
            if db_path.islower():
                stored_lowercase += 1
            else:
                stored_mixed_case += 1
                print(f"Mixed case stored: {db_path}")
        
        print(f"\nStored lowercase: {stored_lowercase}")
        print(f"Stored mixed case: {stored_mixed_case}")
        
        if stored_mixed_case > 0:
            print("\n⚠️  Some paths are stored with mixed case!")
            print("   These need to be normalized to lowercase on Windows.")


if __name__ == "__main__":
    asyncio.run(debug_paths())
