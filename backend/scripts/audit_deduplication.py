"""Deduplication Audit Script

This script performs a comprehensive audit of the matching system to ensure:
1. No duplicate IdentityBridge entries exist
2. Match confidence scoring is consistent
3. Signature generation is working correctly
"""

import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import IdentityBridge, BroadcastLog
from airwave.core.normalization import Normalizer


async def audit_identity_bridges():
    """Check for duplicate IdentityBridge entries."""
    async with AsyncSessionLocal() as session:
        # 1. Check for duplicate log_signature values
        stmt = (
            select(
                IdentityBridge.log_signature,
                func.count(IdentityBridge.id).label("count")
            )
            .group_by(IdentityBridge.log_signature)
            .having(func.count(IdentityBridge.id) > 1)
        )
        
        result = await session.execute(stmt)
        duplicates = result.all()
        
        if duplicates:
            print(f"❌ Found {len(duplicates)} duplicate log_signature values:")
            for row in duplicates:
                print(f"   - Signature: {row.log_signature} (count: {row.count})")
        else:
            print("✅ No duplicate log_signature values found")
        
        # 2. Check total bridge count
        total_stmt = select(func.count(IdentityBridge.id))
        total_res = await session.execute(total_stmt)
        total_bridges = total_res.scalar_one()
        print(f"📊 Total IdentityBridge entries: {total_bridges}")
        
        # 3. Check for bridges with same reference_artist/reference_title but different signatures
        # This would indicate a normalization issue
        stmt_refs = (
            select(
                IdentityBridge.reference_artist,
                IdentityBridge.reference_title,
                func.count(IdentityBridge.id).label("count")
            )
            .group_by(IdentityBridge.reference_artist, IdentityBridge.reference_title)
            .having(func.count(IdentityBridge.id) > 1)
        )
        
        result_refs = await session.execute(stmt_refs)
        ref_duplicates = result_refs.all()
        
        if ref_duplicates:
            print(f"⚠️  Found {len(ref_duplicates)} duplicate reference pairs:")
            for row in ref_duplicates[:10]:  # Show first 10
                print(f"   - {row.reference_artist} - {row.reference_title} (count: {row.count})")
        else:
            print("✅ No duplicate reference pairs found")


async def audit_match_consistency():
    """Check match reason consistency."""
    async with AsyncSessionLocal() as session:
        # 1. Count logs by match_reason
        stmt = (
            select(
                BroadcastLog.match_reason,
                func.count(BroadcastLog.id).label("count")
            )
            .where(BroadcastLog.match_reason.is_not(None))
            .group_by(BroadcastLog.match_reason)
            .order_by(func.count(BroadcastLog.id).desc())
        )
        
        result = await session.execute(stmt)
        match_reasons = result.all()
        
        print("\n📊 Match Reason Distribution:")
        for row in match_reasons:
            print(f"   - {row.match_reason}: {row.count}")
        
        # 2. Check for logs with recording_id but no match_reason
        stmt_orphans = select(func.count(BroadcastLog.id)).where(
            BroadcastLog.recording_id.is_not(None),
            BroadcastLog.match_reason.is_(None)
        )
        orphan_res = await session.execute(stmt_orphans)
        orphan_count = orphan_res.scalar_one()
        
        if orphan_count > 0:
            print(f"⚠️  Found {orphan_count} logs with recording_id but no match_reason")
        else:
            print("✅ All matched logs have match_reason set")


async def audit_signature_generation():
    """Test signature generation consistency."""
    print("\n🔍 Testing Signature Generation:")
    
    test_cases = [
        ("GODSMACK", "Voodoo"),
        ("Godsmack", "Voodoo"),
        ("godsmack", "voodoo"),
        ("  GODSMACK  ", "  Voodoo  "),
    ]
    
    signatures = set()
    for artist, title in test_cases:
        sig = Normalizer.generate_signature(artist, title)
        signatures.add(sig)
        print(f"   - '{artist}' + '{title}' → {sig}")
    
    if len(signatures) == 1:
        print("✅ All variations produce the same signature")
    else:
        print(f"❌ Found {len(signatures)} different signatures for same track!")


async def main():
    print("=" * 60)
    print("AIRWAVE DEDUPLICATION AUDIT")
    print("=" * 60)
    
    print("\n1. Identity Bridge Audit")
    print("-" * 60)
    await audit_identity_bridges()
    
    print("\n2. Match Consistency Audit")
    print("-" * 60)
    await audit_match_consistency()
    
    print("\n3. Signature Generation Audit")
    print("-" * 60)
    await audit_signature_generation()
    
    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

