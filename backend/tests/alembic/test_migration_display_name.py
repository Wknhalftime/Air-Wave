"""Tests for the add_artist_display_name Alembic migration."""

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


def test_migration_add_artist_display_name_upgrade_downgrade(
    alembic_config, engine, temp_db_path
):
    """Migration add_artist_display_name upgrades and downgrades cleanly."""
    prev_revision = "9066bd9d27ae"

    # Upgrade to revision just before add_artist_display_name
    command.upgrade(alembic_config, prev_revision)

    inspector = inspect(engine)
    assert "artists" in inspector.get_table_names()

    # Upgrade to add_artist_display_name (idempotent if display_name already exists)
    command.upgrade(alembic_config, "add_artist_display_name")

    # Force fresh connection to see migrated schema
    engine.dispose()
    inspector = inspect(engine)
    columns_after = {c["name"] for c in inspector.get_columns("artists")}
    assert "display_name" in columns_after

    # Downgrade
    command.downgrade(alembic_config, prev_revision)

    engine.dispose()
    inspector = inspect(engine)
    columns_after_downgrade = {c["name"] for c in inspector.get_columns("artists")}
    assert "display_name" not in columns_after_downgrade


def test_migration_backfills_display_name_on_upgrade(
    alembic_config, engine, temp_db_path
):
    """On upgrade, existing artists get display_name = name."""
    prev_revision = "9066bd9d27ae"

    # Upgrade to add_artist_display_name, then downgrade to remove display_name.
    # This simulates an old DB with artists but no display_name column.
    command.upgrade(alembic_config, "add_artist_display_name")
    command.downgrade(alembic_config, prev_revision)

    # Insert an artist while display_name column is absent
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO artists (id, name, created_at, updated_at) "
                "VALUES (1, 'test_artist', datetime('now'), datetime('now'))"
            )
        )

    # Upgrade
    command.upgrade(alembic_config, "add_artist_display_name")

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, name, display_name FROM artists WHERE id = 1")
        )
        row = result.mappings().first()

    assert row is not None
    assert row["name"] == "test_artist"
    assert row["display_name"] == "test_artist"
