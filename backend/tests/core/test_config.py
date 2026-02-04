from pathlib import Path

from airwave.core.config import settings


def test_config_paths():
    """Verify that paths are correctly resolved."""
    assert isinstance(settings.BASE_DIR, Path)
    assert isinstance(settings.DATA_DIR, Path)
    assert isinstance(settings.DB_PATH, Path)
    assert settings.DB_NAME == "airwave.db"


def test_db_url():
    """Verify DB URL construction."""
    expected_scheme = "sqlite+aiosqlite:///"
    assert settings.DB_URL.startswith(expected_scheme)
    assert str(settings.DB_PATH) in settings.DB_URL


def test_data_dir_creation():
    """Verify DATA_DIR exists (it should be created on import)."""
    assert settings.DATA_DIR.exists()
    assert settings.DATA_DIR.is_dir()
