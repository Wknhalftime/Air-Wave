"""Logging configuration and setup."""

import sys

from airwave.core.config import settings
from loguru import logger


def setup_logging() -> None:
    """Configures Loguru logging for console and file output.

    This function removes the default handler, sets up a colorized console
    output to stderr, and initializes a rotated/compressed log file in the
    application's data directory. Async logging is enabled for the file handler.
    """
    logger.remove()  # Remove default handler

    # Console Handler (Stderr)
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # File Handler (Rotated & Compressed)
    log_file = settings.DATA_DIR / "logs" / "airwave.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_file),
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        level=settings.LOG_LEVEL,
        enqueue=True,  # Async logging
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"Logging initialized. Data Dir: {settings.DATA_DIR}")
