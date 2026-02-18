#!/usr/bin/env python3
"""Diagnostic script to identify path normalization issues in scanner.

This script helps identify why files are being detected as "new" on re-scan
when they should be skipped.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select
from airwave.core.db import AsyncSessionLocal
from airwave.core.models import LibraryFile


async def diagnose_paths():
    """Compare database paths with normalized scanner paths."""
    async with AsyncSessionLocal() as session:
        # Get sample of paths from database
        stmt = select(LibraryFile.path).limit(100)
        result = await session.execute(stmt)
        db_paths = [row.path for row in result.all()]
        
        print(f"Found {len(db_paths)} sample paths in database\n")
        print("=" * 80)
        print("PATH NORMALIZATION ANALYSIS")
        print("=" * 80)
        
        issues = []
        for db_path in db_paths[:20]:  # Sample first 20
            # How scanner normalizes when loading index
            normalized_db = db_path.replace("\\", "/")
            
            # How scanner normalizes when checking skip
            file_path_obj = Path(db_path)
            normalized_check = str(file_path_obj).replace("\\", "/")
            
            # Check for mismatches
            if normalized_db != normalized_check:
                issues.append({
                    "db_path": db_path,
                    "normalized_db": normalized_db,
                    "normalized_check": normalized_check,
                    "issue": "Mismatch"
                })
        
        if issues:
            print(f"\n⚠️  FOUND {len(issues)} PATH NORMALIZATION ISSUES:\n")
            for issue in issues:
                print(f"DB Path:        {issue['db_path']}")
                print(f"Normalized DB:  {issue['normalized_db']}")
                print(f"Normalized Check: {issue['normalized_check']}")
                print(f"Issue: {issue['issue']}")
                print("-" * 80)
        else:
            print("\n✅ No path normalization issues found in sample")
        
        # Check for case sensitivity issues
        print("\n" + "=" * 80)
        print("CASE SENSITIVITY CHECK")
        print("=" * 80)
        
        # Check if any paths have different casing
        path_lower_map = {}
        case_issues = []
        for db_path in db_paths:
            normalized = db_path.replace("\\", "/")
            lower = normalized.lower()
            if lower in path_lower_map:
                if path_lower_map[lower] != normalized:
                    case_issues.append({
                        "path1": path_lower_map[lower],
                        "path2": normalized
                    })
            else:
                path_lower_map[lower] = normalized
        
        if case_issues:
            print(f"\n⚠️  FOUND {len(case_issues)} CASE SENSITIVITY ISSUES:\n")
            for issue in case_issues[:10]:  # Show first 10
                print(f"Path 1: {issue['path1']}")
                print(f"Path 2: {issue['path2']}")
                print("-" * 80)
        else:
            print("\n✅ No case sensitivity issues found")
        
        # Check for path resolution differences
        print("\n" + "=" * 80)
        print("PATH RESOLUTION CHECK")
        print("=" * 80)
        
        resolution_issues = []
        for db_path in db_paths[:20]:
            try:
                file_path = Path(db_path)
                resolved = file_path.resolve()
                resolved_normalized = str(resolved).replace("\\", "/")
                db_normalized = db_path.replace("\\", "/")
                
                if resolved_normalized.lower() != db_normalized.lower():
                    resolution_issues.append({
                        "db_path": db_path,
                        "db_normalized": db_normalized,
                        "resolved_normalized": resolved_normalized
                    })
            except Exception as e:
                print(f"Error resolving {db_path}: {e}")
        
        if resolution_issues:
            print(f"\n⚠️  FOUND {len(resolution_issues)} PATH RESOLUTION ISSUES:\n")
            for issue in resolution_issues[:10]:
                print(f"DB Path:           {issue['db_path']}")
                print(f"DB Normalized:    {issue['db_normalized']}")
                print(f"Resolved Normalized: {issue['resolved_normalized']}")
                print("-" * 80)
        else:
            print("\n✅ No path resolution issues found")
        
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        
        if issues or case_issues or resolution_issues:
            print("\n🔧 FIX REQUIRED:")
            print("1. Normalize paths consistently when storing (use forward slashes)")
            print("2. Use case-insensitive comparison on Windows")
            print("3. Resolve paths to absolute before storing/comparing")
            print("\nRun: python scripts/fix_path_normalization.py")
        else:
            print("\n✅ Path normalization appears correct")
            print("The issue may be elsewhere - check mtime/size comparison logic")


if __name__ == "__main__":
    asyncio.run(diagnose_paths())
