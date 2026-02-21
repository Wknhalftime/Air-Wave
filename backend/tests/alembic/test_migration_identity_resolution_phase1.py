"""Tests for the Phase 1 Identity Resolution migration.

Tests verify:
1. work_id column added to identity_bridge
2. work_id column added to broadcast_logs  
3. suggested_work_id column added to discovery_queue
4. station_preferences table created
5. format_preferences table created
6. work_default_recordings table created
7. Existing data is preserved during upgrade/downgrade
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


class TestPhase1SchemaChanges:
    """Test Phase 1 schema changes."""

    PREV_REVISION = "add_artist_display_name"
    TARGET_REVISION = "phase1_work_linking"

    def test_upgrade_adds_work_id_to_identity_bridge(self, alembic_config, engine):
        """Verify work_id column is added to identity_bridge table."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        inspector = inspect(engine)
        columns_before = {c["name"] for c in inspector.get_columns("identity_bridge")}
        assert "work_id" not in columns_before

        command.upgrade(alembic_config, self.TARGET_REVISION)

        engine.dispose()
        inspector = inspect(engine)
        columns_after = {c["name"] for c in inspector.get_columns("identity_bridge")}
        assert "work_id" in columns_after

        # Verify column is nullable
        col_info = next(
            c for c in inspector.get_columns("identity_bridge") if c["name"] == "work_id"
        )
        assert col_info["nullable"] is True

    def test_upgrade_adds_work_id_to_broadcast_logs(self, alembic_config, engine):
        """Verify work_id column is added to broadcast_logs table."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        inspector = inspect(engine)
        columns_before = {c["name"] for c in inspector.get_columns("broadcast_logs")}
        assert "work_id" not in columns_before

        command.upgrade(alembic_config, self.TARGET_REVISION)

        engine.dispose()
        inspector = inspect(engine)
        columns_after = {c["name"] for c in inspector.get_columns("broadcast_logs")}
        assert "work_id" in columns_after

        # Verify index is created
        indexes = {idx["name"] for idx in inspector.get_indexes("broadcast_logs")}
        assert "ix_broadcast_logs_work_id" in indexes

    def test_upgrade_adds_suggested_work_id_to_discovery_queue(
        self, alembic_config, engine
    ):
        """Verify suggested_work_id column is added to discovery_queue table."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        inspector = inspect(engine)
        columns_before = {c["name"] for c in inspector.get_columns("discovery_queue")}
        assert "suggested_work_id" not in columns_before

        command.upgrade(alembic_config, self.TARGET_REVISION)

        engine.dispose()
        inspector = inspect(engine)
        columns_after = {c["name"] for c in inspector.get_columns("discovery_queue")}
        assert "suggested_work_id" in columns_after

    def test_upgrade_creates_station_preferences_table(self, alembic_config, engine):
        """Verify station_preferences table is created with correct schema."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        inspector = inspect(engine)
        assert "station_preferences" not in inspector.get_table_names()

        command.upgrade(alembic_config, self.TARGET_REVISION)

        engine.dispose()
        inspector = inspect(engine)
        assert "station_preferences" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("station_preferences")}
        assert columns == {
            "id",
            "station_id",
            "work_id",
            "preferred_recording_id",
            "priority",
            "created_at",
            "updated_at",
        }

        # Verify indexes
        indexes = {idx["name"] for idx in inspector.get_indexes("station_preferences")}
        assert "ix_station_preferences_station_id" in indexes
        assert "ix_station_preferences_work_id" in indexes
        assert "idx_station_pref_lookup" in indexes

    def test_upgrade_creates_format_preferences_table(self, alembic_config, engine):
        """Verify format_preferences table is created with correct schema."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        inspector = inspect(engine)
        assert "format_preferences" not in inspector.get_table_names()

        command.upgrade(alembic_config, self.TARGET_REVISION)

        engine.dispose()
        inspector = inspect(engine)
        assert "format_preferences" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("format_preferences")}
        assert columns == {
            "id",
            "format_code",
            "work_id",
            "preferred_recording_id",
            "exclude_tags",
            "priority",
            "created_at",
            "updated_at",
        }

        # Verify indexes
        indexes = {idx["name"] for idx in inspector.get_indexes("format_preferences")}
        assert "ix_format_preferences_format_code" in indexes
        assert "ix_format_preferences_work_id" in indexes
        assert "idx_format_pref_lookup" in indexes

    def test_upgrade_creates_work_default_recordings_table(
        self, alembic_config, engine
    ):
        """Verify work_default_recordings table is created with correct schema."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        inspector = inspect(engine)
        assert "work_default_recordings" not in inspector.get_table_names()

        command.upgrade(alembic_config, self.TARGET_REVISION)

        engine.dispose()
        inspector = inspect(engine)
        assert "work_default_recordings" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("work_default_recordings")}
        assert columns == {
            "work_id",
            "default_recording_id",
            "created_at",
            "updated_at",
        }

    def test_downgrade_removes_new_columns(self, alembic_config, engine):
        """Verify downgrade removes all new columns."""
        command.upgrade(alembic_config, self.TARGET_REVISION)

        command.downgrade(alembic_config, self.PREV_REVISION)

        engine.dispose()
        inspector = inspect(engine)

        # Check columns removed
        identity_bridge_cols = {
            c["name"] for c in inspector.get_columns("identity_bridge")
        }
        assert "work_id" not in identity_bridge_cols

        broadcast_logs_cols = {
            c["name"] for c in inspector.get_columns("broadcast_logs")
        }
        assert "work_id" not in broadcast_logs_cols

        discovery_queue_cols = {
            c["name"] for c in inspector.get_columns("discovery_queue")
        }
        assert "suggested_work_id" not in discovery_queue_cols

    def test_downgrade_removes_policy_tables(self, alembic_config, engine):
        """Verify downgrade removes all policy tables."""
        command.upgrade(alembic_config, self.TARGET_REVISION)

        command.downgrade(alembic_config, self.PREV_REVISION)

        engine.dispose()
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        assert "station_preferences" not in tables
        assert "format_preferences" not in tables
        assert "work_default_recordings" not in tables


class TestPhase1DataPreservation:
    """Test that existing data is preserved during migration."""

    PREV_REVISION = "add_artist_display_name"
    TARGET_REVISION = "phase1_work_linking"

    def test_existing_identity_bridge_data_preserved(self, alembic_config, engine):
        """Verify existing identity_bridge records are preserved."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        # Insert test data before migration
        with engine.begin() as conn:
            # Need to create required foreign key records first
            conn.execute(
                text(
                    "INSERT INTO artists (id, name, created_at, updated_at) "
                    "VALUES (1, 'Test Artist', datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO works (id, title, artist_id, is_instrumental, created_at, updated_at) "
                    "VALUES (1, 'Test Work', 1, 0, datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO recordings (id, work_id, title, is_verified, created_at, updated_at) "
                    "VALUES (1, 1, 'Test Recording', 0, datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO identity_bridge (id, log_signature, reference_artist, reference_title, "
                    "recording_id, confidence, is_revoked, created_at, updated_at) "
                    "VALUES (1, 'test_sig', 'Test Artist', 'Test Title', 1, 1.0, 0, "
                    "datetime('now'), datetime('now'))"
                )
            )

        command.upgrade(alembic_config, self.TARGET_REVISION)

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM identity_bridge WHERE id = 1")
            )
            row = result.mappings().first()

        assert row is not None
        assert row["log_signature"] == "test_sig"
        assert row["reference_artist"] == "Test Artist"
        assert row["recording_id"] == 1
        assert row["work_id"] is None  # New column should be NULL

    def test_existing_broadcast_logs_data_preserved(self, alembic_config, engine):
        """Verify existing broadcast_logs records are preserved."""
        command.upgrade(alembic_config, self.PREV_REVISION)

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO stations (id, callsign, created_at, updated_at) "
                    "VALUES (1, 'WXYZ', datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO broadcast_logs (id, station_id, played_at, raw_artist, raw_title, "
                    "created_at, updated_at) "
                    "VALUES (1, 1, datetime('now'), 'Test Artist', 'Test Title', "
                    "datetime('now'), datetime('now'))"
                )
            )

        command.upgrade(alembic_config, self.TARGET_REVISION)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM broadcast_logs WHERE id = 1"))
            row = result.mappings().first()

        assert row is not None
        assert row["raw_artist"] == "Test Artist"
        assert row["raw_title"] == "Test Title"
        assert row["work_id"] is None  # New column should be NULL


class TestPhase1NonBreaking:
    """Test that Phase 1 is non-breaking - existing queries still work."""

    PREV_REVISION = "add_artist_display_name"
    TARGET_REVISION = "phase1_work_linking"

    def test_existing_queries_work_after_upgrade(self, alembic_config, engine):
        """Verify that queries using recording_id still work after upgrade."""
        command.upgrade(alembic_config, self.TARGET_REVISION)

        with engine.begin() as conn:
            # Setup test data
            conn.execute(
                text(
                    "INSERT INTO artists (id, name, created_at, updated_at) "
                    "VALUES (1, 'Test Artist', datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO works (id, title, artist_id, is_instrumental, created_at, updated_at) "
                    "VALUES (1, 'Test Work', 1, 0, datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO recordings (id, work_id, title, is_verified, created_at, updated_at) "
                    "VALUES (1, 1, 'Test Recording', 0, datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO identity_bridge (id, log_signature, reference_artist, reference_title, "
                    "recording_id, confidence, is_revoked, created_at, updated_at) "
                    "VALUES (1, 'test_sig', 'Test Artist', 'Test Title', 1, 1.0, 0, "
                    "datetime('now'), datetime('now'))"
                )
            )

        # Existing query pattern using recording_id should still work
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT ib.*, r.title as recording_title "
                    "FROM identity_bridge ib "
                    "JOIN recordings r ON ib.recording_id = r.id "
                    "WHERE ib.log_signature = 'test_sig'"
                )
            )
            row = result.mappings().first()

        assert row is not None
        assert row["recording_title"] == "Test Recording"
