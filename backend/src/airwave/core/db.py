import datetime
import shutil
from typing import Any, AsyncGenerator

from airwave.core.config import settings
from airwave.core.models import Base
from loguru import logger
from sqlalchemy import Engine, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Create Async Engine
# check_same_thread=False is needed for SQLite, though less critical for asyncio
# busy_timeout (ms) allows SQLite to wait instead of failing immediately with "database is locked"
# echo=True enables SQLAlchemy query logging for debugging (controlled by DB_ECHO setting)
engine = create_async_engine(
    settings.DB_URL,
    echo=settings.DB_ECHO,
    connect_args={"check_same_thread": False, "timeout": 30},
)


# Configure WAL Mode on connection (SQLite Only)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Sets performance pragmas for SQLite.

    WAL (Write-Ahead Logging) mode is critical for multi-process environments like
    FastAPI + Workers, as it allows concurrent reads and writes without locking.
    """
    if settings.DB_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
        cursor.close()


# Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting DB session.

    This yields a scoped session to the FastAPI dependency injection system,
    ensuring each request gets a clean transaction.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def backup_db() -> None:
    """Create a point-in-time backup of the current database file.

    Automated backups preserve the 'airwave.db' state before high-risk operations
    like schema migration or forced initialization.
    """
    src = settings.DB_PATH
    if not src.exists():
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = src.parent / f"{settings.DB_NAME}.{timestamp}.bak"

    try:
        # For SQLite, it's safer to use VACUUM INTO if we have an active connection,
        # but a simple file copy is standard for startup recovery.
        shutil.copy2(src, dst)
        logger.info(f"Database backed up to {dst}")

        # Cleanup old backups (keep last N)
        max_backups = settings.DB_BACKUP_RETENTION
        backups = sorted(src.parent.glob(f"{settings.DB_NAME}.*.bak"))
        if len(backups) > max_backups:
            for b in backups[:-max_backups]:
                b.unlink()
    except (OSError, shutil.Error) as e:
        logger.error(f"Failed to backup database: {e}")


async def init_db(force: bool = False) -> None:
    """Initialize database tables according to current models.

    Args:
        force: If True, drops all existing tables and re-creates them.
            Use with extreme caution as this results in total data loss.
    """
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if force:
        logger.warning(
            "FORCED database initialization. Existing data might be lost."
        )
        await backup_db()

    async with engine.begin() as conn:
        if force:
            # Only drop if explicitly forced
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready.")