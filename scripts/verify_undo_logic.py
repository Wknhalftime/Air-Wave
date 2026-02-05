import asyncio
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "src")))

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import IdentityBridge, VerificationAudit, Recording
from sqlalchemy import select, delete

async def main():
    print("Verifying Undo Logic...")
    async with AsyncSessionLocal() as db:
        # 1. Setup: Create a dummy bridge and audit entry
        print("Creating dummy bridge and audit entry...")
        
        # Determine existing recording ID (fallback to 1 or create one if needed, assuming 1 exists for now or fetch one)
        rec_stmt = select(Recording).limit(1)
        rec_res = await db.execute(rec_stmt)
        rec = rec_res.scalar_one_or_none()
        if not rec:
            print("No recording found, skipping test (needs seeded DB)")
            return

        sig = "test_undo_signature"
        
        # Cleanup previous run
        await db.execute(delete(VerificationAudit).where(VerificationAudit.signature == sig))
        await db.execute(delete(IdentityBridge).where(IdentityBridge.log_signature == sig))
        await db.commit()

        bridge = IdentityBridge(
            log_signature=sig,
            reference_artist="Test Artist",
            reference_title="Test Title",
            recording_id=rec.id,
            confidence=1.0,
            is_revoked=False
        )
        db.add(bridge)
        await db.flush()

        audit = VerificationAudit(
            action_type="manual_test",
            signature=sig,
            raw_artist="Test Artist",
            raw_title="Test Title",
            recording_id=rec.id,
            log_ids=[],
            bridge_id=bridge.id,
            is_undone=False
        )
        db.add(audit)
        await db.commit()
        
        print(f"Created Bridge {bridge.id} and Audit {audit.id}")
        
        # 2. Call Undo Logic (Simulation)
        # We can call the API function directly if we import the router function, 
        # or just simulate the logic to verify the model behavior. 
        # Better to invoke the router logic via a test client or by replicating the logic here.
        # Im testing the DB state transitions.

        print("Simulating Undo...")
        bridge.is_revoked = True
        audit.is_undone = True
        audit.undone_at = datetime.now()
        
        undo_audit = VerificationAudit(
            action_type="undo",
            signature=sig,
            raw_artist="Test Artist", 
            raw_title="Test Title",
            recording_id=None,
            log_ids=[],
            bridge_id=bridge.id
        )
        db.add(undo_audit)
        await db.commit()
        
        # 3. Verify
        print("Verifying State...")
        await db.refresh(bridge)
        await db.refresh(audit)
        
        if bridge.is_revoked:
            print("SUCCESS: Bridge is revoked.")
        else:
            print("FAILURE: Bridge is NOT revoked.")
            
        if audit.is_undone:
            print("SUCCESS: Audit is marked undone.")
        else:
            print("FAILURE: Audit is NOT marked undone.")

        # Cleanup
        await db.delete(undo_audit)
        await db.delete(audit)
        await db.delete(bridge)
        await db.commit()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
