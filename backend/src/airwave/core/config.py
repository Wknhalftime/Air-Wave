import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Project Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = Path(
        os.getenv("AIRWAVE_DATA_DIR", str(BASE_DIR.parent / "data"))
    )

    # Database
    DB_NAME: str = "airwave.db"

    @property
    def DB_PATH(self) -> Path:
        return self.DATA_DIR / self.DB_NAME

    @property
    def DB_URL(self) -> str:
        # Use forward slashes so Windows paths work in the URL (no backslash escapes)
        path = self.DB_PATH.resolve().as_posix()
        return f"sqlite+aiosqlite:///{path}"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_RETENTION: str = "10 days"
    LOG_ROTATION: str = "10 MB"

    # Performance & Debugging
    DB_ECHO: bool = False  # Enable SQLAlchemy query logging (set to True for debugging)

    # Matching Thresholds
    MATCH_VARIANT_ARTIST_SCORE: float = 0.85
    MATCH_VARIANT_TITLE_SCORE: float = 0.80
    
    MATCH_ALIAS_ARTIST_SCORE: float = 0.70    # For Review
    MATCH_ALIAS_TITLE_SCORE: float = 0.70     # For Review

    # Legacy / Vector
    MATCH_CONFIDENCE_HIGH_ARTIST: float = 0.85 # Deprecated, use VARIANT
    MATCH_CONFIDENCE_HIGH_TITLE: float = 0.8  # Deprecated, use VARIANT
    MATCH_VECTOR_STRONG_DIST: float = 0.15
    MATCH_TITLE_VECTOR_TITLE: float = 0.9
    MATCH_TITLE_VECTOR_DIST: float = 0.3
    MATCH_VECTOR_TITLE_GUARD: float = 0.5

    # External APIs
    ACOUSTID_API_KEY: str = ""


settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
