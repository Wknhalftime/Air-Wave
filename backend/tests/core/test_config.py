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
    # Normalize paths for cross-platform (Windows uses backslashes, URL may use slashes)
    path_str = str(settings.DB_PATH).replace("\\", "/")
    assert path_str in settings.DB_URL or settings.DB_PATH.name in settings.DB_URL


def test_data_dir_path():
    """Verify DATA_DIR is a valid Path. Existence is ensured by init_db(), not on import."""
    assert isinstance(settings.DATA_DIR, Path)
    assert settings.DATA_DIR.name
