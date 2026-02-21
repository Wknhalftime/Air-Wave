"""Deduplication audit: IdentityBridge duplicates, match consistency, signature generation.

Usage:
    poetry run python -m airwave.scripts.audit_deduplication
"""
import asyncio

from sqlalchemy import func, select

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import IdentityBridge, BroadcastLog
from airwave.core.normalization import Normalizer


async def audit_identity_bridges():
    async with AsyncSessionLocal() as session:
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
            print(f"Found {len(duplicates)} duplicate log_signature values")
        else:
            print("No duplicate log_signature values found")
        total = (await session.execute(select(func.count(IdentityBridge.id)))).scalar_one()
        print(f"Total IdentityBridge entries: {total}")


async def audit_match_consistency():
    async with AsyncSessionLocal() as session:
        stmt = (
            select(BroadcastLog.match_reason, func.count(BroadcastLog.id).label("count"))
            .where(BroadcastLog.match_reason.is_not(None))
            .group_by(BroadcastLog.match_reason)
        )
        result = await session.execute(stmt)
        for row in result.all():
            print(f"  {row.match_reason}: {row.count}")


async def audit_signature_generation():
    test_cases = [("GODSMACK", "Voodoo"), ("godsmack", "voodoo")]
    sigs = {Normalizer.generate_signature(a, t) for a, t in test_cases}
    print("All variations same signature" if len(sigs) == 1 else "Signature mismatch!")


async def main():
    print("AIRWAVE DEDUPLICATION AUDIT")
    await audit_identity_bridges()
    await audit_match_consistency()
    await audit_signature_generation()
    print("AUDIT COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
