import asyncio
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from airwave.core.db import AsyncSessionLocal, engine
from airwave.core.models import (
    Base,
    BroadcastLog,
    IdentityBridge,
    ImportBatch,
    LibraryFile,
    Station,
)
from airwave.worker.scanner import FileScanner


async def migrate():
    print("Starting BCNF Migration (Optimized v3)...")

    # 1. Reset Database
    print("Resetting Database Schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session = AsyncSessionLocal()

    # 2. Connect to Backup
    backup_path = "data/airwave.db.bak"
    if not os.path.exists(backup_path):
        print(f"ERROR: Backup file {backup_path} not found!")
        return

    src_conn = sqlite3.connect(backup_path)
    src_conn.row_factory = sqlite3.Row
    cur = src_conn.cursor()

    id_map = {}  # old_track_id -> new_recording_id

    try:
        # 3a. Stations
        print("Migrating Stations...")
        cur.execute("SELECT * FROM stations")
        stations = cur.fetchall()
        station_buffer = []
        for s in stations:
            station_buffer.append(
                {
                    "id": s["id"],
                    "callsign": s["callsign"],
                    "frequency": s["frequency"],
                    "city": s["city"],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        if station_buffer:
            await session.execute(insert(Station), station_buffer)
            await session.commit()
        print(f"Finished {len(stations)} Stations.")

        # 3b. Import Batches
        print("Migrating Import Batches...")
        try:
            cur.execute("SELECT * FROM import_batches")
            batches = cur.fetchall()
            b_buffer = []
            for b in batches:
                b_buffer.append(
                    {
                        "id": b["id"],
                        "filename": b["filename"],
                        "status": b["status"],
                        "total_rows": b["total_rows"],
                        "processed_rows": b["processed_rows"],
                        "error_log": b["error_log"],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            if b_buffer:
                await session.execute(insert(ImportBatch), b_buffer)
                await session.commit()
            print(f"Finished {len(batches)} Batches.")
        except sqlite3.OperationalError:
            print("No import_batches table found.")

        # 3c. Tracks (ORM logic needed for Scanner relationships)
        # Using ORM for Tracks because logic is complex and count is low (13k)
        print("Migrating Tracks (ORM)...")
        cur.execute("SELECT * FROM tracks")
        old_tracks = cur.fetchall()

        scanner_instance = FileScanner(session)

        count = 0
        for t in old_tracks:
            old_id = t["id"]
            artist_name = t["artist"]
            title = t["title"]
            path = t["path"]

            artist_obj = await scanner_instance._get_or_create_artist(
                artist_name
            )
            (
                clean_work_title,
                version_type,
            ) = scanner_instance._parse_version_type(title)
            work_obj = await scanner_instance._get_or_create_work(
                clean_work_title, artist_obj.id
            )

            duration = t["duration"] if "duration" in t.keys() else None
            rec_obj = await scanner_instance._get_or_create_recording(
                work_obj.id, title, version_type, duration
            )

            id_map[old_id] = rec_obj.id

            # LibraryFile (only if path matches)
            if path and not path.startswith("virtual://"):
                # Check if we created one? No, just add.
                # Actually, duplicates? Scanner creates them.
                # But we are fresh DB.
                # Just check if associated.
                await session.refresh(rec_obj, attribute_names=["files"])
                exists = any(f.path == path for f in rec_obj.files)
                if not exists:
                    lf = LibraryFile(
                        recording_id=rec_obj.id,
                        path=path,
                        size=0,
                        format=Path(path).suffix.replace(".", ""),
                    )
                    session.add(lf)

            count += 1
            if count % 100 == 0:
                print(f"Processed {count} tracks...")
                await session.commit()

        await session.commit()
        print(f"Finished Tracks. Total: {count}")

        # 4. Broadcast Logs (Massive - Bulk Insert)
        print("Migrating Broadcast Logs (Bulk)...")
        # Ensure count
        total_logs = cur.execute(
            "SELECT count(*) FROM broadcast_logs"
        ).fetchone()[0]
        print(f"Total Logs to migrate: {total_logs}")

        cur.execute("SELECT * FROM broadcast_logs")

        BATCH_SIZE = 10000
        processed_count = 0

        while True:
            rows = cur.fetchmany(BATCH_SIZE)
            if not rows:
                break

            insert_buffer = []
            for l in rows:
                # Parse played_at
                try:
                    played_at_dt = datetime.fromisoformat(l["played_at"])
                except:
                    try:
                        played_at_dt = datetime.strptime(
                            l["played_at"], "%Y-%m-%d %H:%M:%S.%f"
                        )
                    except:
                        # Default?
                        played_at_dt = datetime.now()

                old_track_id = l["track_id"] if "track_id" in l.keys() else None
                new_rec_id = id_map.get(old_track_id) if old_track_id else None

                insert_buffer.append(
                    {
                        "station_id": l["station_id"],
                        "played_at": played_at_dt,
                        "raw_artist": l["raw_artist"],
                        "raw_title": l["raw_title"],
                        "recording_id": new_rec_id,
                        "import_batch_id": l["import_batch_id"]
                        if "import_batch_id" in l.keys()
                        else None,
                        "match_reason": l["match_reason"] or "Migration",
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )

            if insert_buffer:
                await session.execute(insert(BroadcastLog), insert_buffer)
                await session.commit()
                processed_count += len(rows)
                print(f"Migrated {processed_count} / {total_logs} logs...")

        print("Finished Logs.")

        # 5. Identity Bridge (Also potentially large? Usually small)
        print("Migrating Identity Bridge...")
        try:
            cur.execute("SELECT * FROM identity_bridge")
            old_bridges = cur.fetchall()
            b_buffer = []
            for b in old_bridges:
                old_tid = b["track_id"]
                new_rid = id_map.get(old_tid)
                if new_rid:
                    b_buffer.append(
                        {
                            "log_signature": b["log_signature"],
                            "recording_id": new_rid,
                            "reference_artist": b["reference_artist"],
                            "reference_title": b["reference_title"],
                            "confidence": b["confidence"],
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
            if b_buffer:
                await session.execute(insert(IdentityBridge), b_buffer)
                await session.commit()
            print(f"Finished {len(b_buffer)} Bridges.")

        except sqlite3.OperationalError:
            print("No identity_bridge table found matching name.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        src_conn.close()
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
