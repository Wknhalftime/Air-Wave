"""Tests for the Phase 2 Identity Resolution migration (backfill work_id).

Tests verify:
1. Backfill correctly populates work_id from recording relationships
2. Backfill is idempotent (can be re-run safely)
3. Rows without recording_id are not affected
4. Downgrade clears work_id without affecting recording_id
"""

import tempfile
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from alembic import command
from alembic.config import Config


@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    import os

    os.close(fd)
    yield path
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


@pytest.fixture
def alembic_config(temp_db_path):
    """Create Alembic config pointing at temp database."""
    sync_url = f"sqlite:///{temp_db_path}"

    config = Config()
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", sync_url)
    config.set_main_option("prepend_sys_path", str(_BACKEND_DIR / "src"))

    return config


@pytest.fixture
def engine(temp_db_path) -> Engine:
    """Create sync engine for the temp database."""
    eng = create_engine(f"sqlite:///{temp_db_path}")
    yield eng
    eng.dispose()


def setup_test_data(engine):
    """Insert test data for backfill testing."""
    with engine.begin() as conn:
        # Create artist
        conn.execute(
            text(
                "INSERT INTO artists (id, name, created_at, updated_at) "
                "VALUES (1, 'Test Artist', datetime('now'), datetime('now'))"
            )
        )

        # Create works
        conn.execute(
            text(
                "INSERT INTO works (id, title, artist_id, is_instrumental, created_at, updated_at) "
                "VALUES (1, 'Work One', 1, 0, datetime('now'), datetime('now'))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO works (id, title, artist_id, is_instrumental, created_at, updated_at) "
                "VALUES (2, 'Work Two', 1, 0, datetime('now'), datetime('now'))"
            )
        )

        # Create recordings
        conn.execute(
            text(
                "INSERT INTO recordings (id, work_id, title, is_verified, created_at, updated_at) "
                "VALUES (1, 1, 'Recording One', 0, datetime('now'), datetime('now'))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO recordings (id, work_id, title, is_verified, created_at, updated_at) "
                "VALUES (2, 2, 'Recording Two', 0, datetime('now'), datetime('now'))"
            )
        )

        # Create station
        conn.execute(
            text(
                "INSERT INTO stations (id, callsign, created_at, updated_at) "
                "VALUES (1, 'WXYZ', datetime('now'), datetime('now'))"
            )
        )

        # Create identity_bridge entries
        conn.execute(
            text(
                "INSERT INTO identity_bridge (id, log_signature, reference_artist, reference_title, "
                "recording_id, confidence, is_revoked, created_at, updated_at) "
                "VALUES (1, 'sig1', 'Test Artist', 'Work One', 1, 1.0, 0, "
                "datetime('now'), datetime('now'))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO identity_bridge (id, log_signature, reference_artist, reference_title, "
                "recording_id, confidence, is_revoked, created_at, updated_at) "
                "VALUES (2, 'sig2', 'Test Artist', 'Work Two', 2, 1.0, 0, "
                "datetime('now'), datetime('now'))"
            )
        )

        # Create broadcast_logs entries
        conn.execute(
            text(
                "INSERT INTO broadcast_logs (id, station_id, played_at, raw_artist, raw_title, "
                "recording_id, created_at, updated_at) "
                "VALUES (1, 1, datetime('now'), 'Test Artist', 'Work One', 1, "
                "datetime('now'), datetime('now'))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO broadcast_logs (id, station_id, played_at, raw_artist, raw_title, "
                "recording_id, created_at, updated_at) "
                "VALUES (2, 1, datetime('now'), 'Test Artist', 'Work Two', 2, "
                "datetime('now'), datetime('now'))"
            )
        )
        # Broadcast log without recording_id (unmatched)
        conn.execute(
            text(
                "INSERT INTO broadcast_logs (id, station_id, played_at, raw_artist, raw_title, "
                "created_at, updated_at) "
                "VALUES (3, 1, datetime('now'), 'Unknown Artist', 'Unknown Song', "
                "datetime('now'), datetime('now'))"
            )
        )

        # Create discovery_queue entry
        conn.execute(
            text(
                "INSERT INTO discovery_queue (signature, raw_artist, raw_title, count, "
                "suggested_recording_id, created_at, updated_at) "
                "VALUES ('discovery_sig1', 'Test Artist', 'Work One', 5, 1, "
                "datetime('now'), datetime('now'))"
            )
        )
        # Discovery queue without suggestion
        conn.execute(
            text(
                "INSERT INTO discovery_queue (signature, raw_artist, raw_title, count, "
                "created_at, updated_at) "
                "VALUES ('discovery_sig2', 'Unknown', 'Unknown', 3, "
                "datetime('now'), datetime('now'))"
            )
        )


class TestPhase2Backfill:
    """Test Phase 2 backfill functionality."""

    PHASE1_REVISION = "phase1_work_linking"
    PHASE2_REVISION = "phase2_backfill_work_ids"

    def test_backfill_identity_bridge(self, alembic_config, engine):
        """Backfill correctly populates identity_bridge.work_id."""
        # Upgrade to Phase 1 first
        command.upgrade(alembic_config, self.PHASE1_REVISION)
        setup_test_data(engine)

        # Verify work_id is NULL before backfill
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, recording_id, work_id FROM identity_bridge ORDER BY id")
            )
            rows = result.mappings().all()
            assert len(rows) == 2
            assert rows[0]["work_id"] is None
            assert rows[1]["work_id"] is None

        # Run Phase 2 backfill
        command.upgrade(alembic_config, self.PHASE2_REVISION)

        # Verify work_id is now populated correctly
        engine.dispose()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, recording_id, work_id FROM identity_bridge ORDER BY id")
            )
            rows = result.mappings().all()
            assert rows[0]["work_id"] == 1  # Recording 1 -> Work 1
            assert rows[1]["work_id"] == 2  # Recording 2 -> Work 2

    def test_backfill_broadcast_logs(self, alembic_config, engine):
        """Backfill correctly populates broadcast_logs.work_id."""
        command.upgrade(alembic_config, self.PHASE1_REVISION)
        setup_test_data(engine)

        command.upgrade(alembic_config, self.PHASE2_REVISION)

        engine.dispose()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT id, recording_id, work_id FROM broadcast_logs ORDER BY id"
                )
            )
            rows = result.mappings().all()
            assert len(rows) == 3
            assert rows[0]["work_id"] == 1  # Recording 1 -> Work 1
            assert rows[1]["work_id"] == 2  # Recording 2 -> Work 2
            assert rows[2]["work_id"] is None  # No recording_id, should stay NULL

    def test_backfill_discovery_queue(self, alembic_config, engine):
        """Backfill correctly populates discovery_queue.suggested_work_id."""
        command.upgrade(alembic_config, self.PHASE1_REVISION)
        setup_test_data(engine)

        command.upgrade(alembic_config, self.PHASE2_REVISION)

        engine.dispose()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT signature, suggested_recording_id, suggested_work_id "
                    "FROM discovery_queue ORDER BY signature"
                )
            )
            rows = result.mappings().all()
            assert len(rows) == 2
            # discovery_sig1 has suggested_recording_id = 1 -> work_id = 1
            assert rows[0]["suggested_work_id"] == 1
            # discovery_sig2 has no suggested_recording_id
            assert rows[1]["suggested_work_id"] is None

    def test_backfill_is_idempotent(self, alembic_config, engine):
        """Backfill can be re-run without changing already-backfilled data."""
        command.upgrade(alembic_config, self.PHASE2_REVISION)
        setup_test_data(engine)

        # Manually update to simulate partial backfill
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE identity_bridge SET work_id = 1 WHERE id = 1")
            )

        # Run backfill migration again (downgrade then upgrade)
        command.downgrade(alembic_config, self.PHASE1_REVISION)
        command.upgrade(alembic_config, self.PHASE2_REVISION)

        # Data should be restored correctly
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, work_id FROM identity_bridge ORDER BY id")
            )
            rows = result.mappings().all()
            assert rows[0]["work_id"] == 1
            assert rows[1]["work_id"] == 2

    def test_downgrade_clears_work_id(self, alembic_config, engine):
        """Downgrade clears work_id but preserves recording_id."""
        command.upgrade(alembic_config, self.PHASE2_REVISION)
        setup_test_data(engine)

        # Manually set work_id to simulate completed backfill
        with engine.begin() as conn:
            conn.execute(text("UPDATE identity_bridge SET work_id = 1 WHERE id = 1"))
            conn.execute(text("UPDATE identity_bridge SET work_id = 2 WHERE id = 2"))
            conn.execute(text("UPDATE broadcast_logs SET work_id = 1 WHERE id = 1"))

        # Downgrade
        command.downgrade(alembic_config, self.PHASE1_REVISION)

        engine.dispose()
        with engine.connect() as conn:
            # work_id should be cleared
            result = conn.execute(
                text("SELECT id, recording_id, work_id FROM identity_bridge ORDER BY id")
            )
            rows = result.mappings().all()
            assert rows[0]["work_id"] is None
            assert rows[0]["recording_id"] == 1  # recording_id preserved!

            result = conn.execute(
                text("SELECT id, recording_id, work_id FROM broadcast_logs ORDER BY id")
            )
            rows = result.mappings().all()
            assert rows[0]["work_id"] is None
            assert rows[0]["recording_id"] == 1  # recording_id preserved!

    def test_rows_with_existing_work_id_unchanged(self, alembic_config, engine):
        """Rows that already have work_id set are not changed by backfill."""
        command.upgrade(alembic_config, self.PHASE1_REVISION)
        setup_test_data(engine)

        # Manually set work_id to a different value to verify it's not overwritten
        with engine.begin() as conn:
            # Set work_id to 999 (different from what backfill would set)
            conn.execute(
                text("UPDATE identity_bridge SET work_id = 999 WHERE id = 1")
            )

        # Verify our manual update
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, work_id FROM identity_bridge WHERE id = 1")
            )
            row = result.mappings().first()
            assert row["work_id"] == 999

        command.upgrade(alembic_config, self.PHASE2_REVISION)

        engine.dispose()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, recording_id, work_id FROM identity_bridge ORDER BY id")
            )
            rows = result.mappings().all()
            # Row 1 should retain the manually-set value (999), not be overwritten
            assert rows[0]["work_id"] == 999
            # Row 2 should be backfilled normally
            assert rows[1]["work_id"] == 2


class TestPhase2DataIntegrity:
    """Test data integrity after Phase 2 backfill."""

    PHASE2_REVISION = "phase2_backfill_work_ids"

    def test_work_id_matches_recording_work_id(self, alembic_config, engine):
        """All backfilled work_id values match their recording's work_id."""
        command.upgrade(alembic_config, self.PHASE2_REVISION)
        setup_test_data(engine)

        # Re-run the backfill by downgrading and upgrading
        command.downgrade(alembic_config, "phase1_work_linking")
        command.upgrade(alembic_config, self.PHASE2_REVISION)

        engine.dispose()
        with engine.connect() as conn:
            # Check identity_bridge
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*) as mismatch_count
                    FROM identity_bridge ib
                    JOIN recordings r ON ib.recording_id = r.id
                    WHERE ib.work_id IS NOT NULL AND ib.work_id != r.work_id
                    """
                )
            )
            assert result.scalar() == 0

            # Check broadcast_logs
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*) as mismatch_count
                    FROM broadcast_logs bl
                    JOIN recordings r ON bl.recording_id = r.id
                    WHERE bl.work_id IS NOT NULL AND bl.work_id != r.work_id
                    """
                )
            )
            assert result.scalar() == 0

            # Check discovery_queue
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*) as mismatch_count
                    FROM discovery_queue dq
                    JOIN recordings r ON dq.suggested_recording_id = r.id
                    WHERE dq.suggested_work_id IS NOT NULL 
                      AND dq.suggested_work_id != r.work_id
                    """
                )
            )
            assert result.scalar() == 0
