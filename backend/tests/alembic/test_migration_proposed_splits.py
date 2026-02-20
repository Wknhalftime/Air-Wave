"""Tests for the proposed_splits data migration in a43de339102a migration."""

import tempfile
from pathlib import Path

import pytest

# Resolve paths relative to backend directory (parent of tests/)
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
        pass  # Ignore on Windows if file still in use


@pytest.fixture
def alembic_config(temp_db_path):
    """Create Alembic config pointing at temp database."""
    # Sync URL for Alembic (uses sync sqlite)
    sync_url = f"sqlite:///{temp_db_path}"

    config = Config()
    config.set_main_option(
        "script_location", str(_BACKEND_DIR / "alembic")
    )
    config.set_main_option("sqlalchemy.url", sync_url)
    config.set_main_option("prepend_sys_path", str(_BACKEND_DIR / "src"))

    return config


@pytest.fixture
def engine(temp_db_path) -> Engine:
    """Create sync engine for the temp database."""
    eng = create_engine(f"sqlite:///{temp_db_path}")
    yield eng
    eng.dispose()


def test_migration_proposed_splits_data_migration_upgrade(
    alembic_config, engine, temp_db_path
):
    """Test that data is correctly migrated from old columns to new columns on upgrade."""
    # The migration a43de339102a has down_revision = "4489d4180af6"
    prev_revision = "4489d4180af6"
    target_revision = "a43de339102a"

    # Upgrade to revision just before a43de339102a
    command.upgrade(alembic_config, prev_revision)

    # Verify proposed_splits table exists with old schema
    inspector = inspect(engine)
    assert "proposed_splits" in inspector.get_table_names()
    columns_before = {c["name"] for c in inspector.get_columns("proposed_splits")}
    
    # Old schema should have original_artist and split_parts
    assert "original_artist" in columns_before
    assert "split_parts" in columns_before
    assert "raw_artist" not in columns_before
    assert "proposed_artists" not in columns_before

    # Insert test data with old column names
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO proposed_splits (id, original_artist, split_parts, status, created_at, updated_at) "
                "VALUES (1, 'Test Artist & Another Artist', '[\"Test Artist\", \"Another Artist\"]', 'PENDING', datetime('now'), datetime('now'))"
            )
        )

    # Upgrade to a43de339102a
    command.upgrade(alembic_config, target_revision)

    # Force fresh connection to see migrated schema
    engine.dispose()
    inspector = inspect(engine)
    columns_after = {c["name"] for c in inspector.get_columns("proposed_splits")}
    
    # New schema should have raw_artist and proposed_artists
    assert "raw_artist" in columns_after
    assert "proposed_artists" in columns_after
    assert "confidence" in columns_after
    # Old columns should be dropped
    assert "original_artist" not in columns_after
    assert "split_parts" not in columns_after

    # Verify data was migrated correctly
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, raw_artist, proposed_artists FROM proposed_splits WHERE id = 1")
        )
        row = result.mappings().first()

    assert row is not None
    assert row["raw_artist"] == "Test Artist & Another Artist"
    assert row["proposed_artists"] == '["Test Artist", "Another Artist"]'


def test_migration_proposed_splits_data_migration_downgrade(
    alembic_config, engine, temp_db_path
):
    """Test that data is correctly migrated back from new columns to old columns on downgrade."""
    prev_revision = "4489d4180af6"
    target_revision = "a43de339102a"

    # Start with the new schema (a43de339102a)
    command.upgrade(alembic_config, target_revision)

    # Insert test data with new column names
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO proposed_splits (id, raw_artist, proposed_artists, confidence, status, created_at, updated_at) "
                "VALUES (1, 'Test Artist & Another Artist', '[\"Test Artist\", \"Another Artist\"]', 0.95, 'PENDING', datetime('now'), datetime('now'))"
            )
        )

    # Downgrade to previous revision
    command.downgrade(alembic_config, prev_revision)

    # Force fresh connection to see migrated schema
    engine.dispose()
    inspector = inspect(engine)
    columns_after = {c["name"] for c in inspector.get_columns("proposed_splits")}
    
    # Old schema should be restored
    assert "original_artist" in columns_after
    assert "split_parts" in columns_after
    # New columns should be dropped
    assert "raw_artist" not in columns_after
    assert "proposed_artists" not in columns_after
    assert "confidence" not in columns_after

    # Verify data was migrated back correctly
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, original_artist, split_parts FROM proposed_splits WHERE id = 1")
        )
        row = result.mappings().first()

    assert row is not None
    assert row["original_artist"] == "Test Artist & Another Artist"
    assert row["split_parts"] == '["Test Artist", "Another Artist"]'

