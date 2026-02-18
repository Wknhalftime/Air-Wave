"""Configuration for scanner behavior and performance tuning."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScannerConfig:
    """Configuration for FileScanner behavior.

    This dataclass centralizes all configurable parameters for the scanner,
    replacing magic numbers throughout the codebase with explicit, documented
    configuration values.

    Attributes:
        max_concurrent_files: Maximum files to process in parallel (default: 10)
        metadata_workers: Thread pool size for metadata extraction (default: min(8, max_concurrent_files * 2))
        hashing_workers: Thread pool size for file hashing (default: min(8, max_concurrent_files * 2))
        batch_size: Batch size for database operations (default: 500)
        touch_batch_size: Number of touch updates to batch before flushing (default: 500)
        vector_batch_size: Number of vector tracks to batch before flushing (default: 100)
        commit_interval: Commit every N files processed (default: 100)
        progress_update_interval: Update progress every N files (default: 10)
        missing_chunk_size: Chunk size for missing file queries (default: 5000)
        enable_folder_skip: Skip directories whose mtime is unchanged (default: True)

    Example:
        >>> config = ScannerConfig(max_concurrent_files=20, commit_interval=200)
        >>> scanner = FileScanner(session, config=config)
    """

    max_concurrent_files: int = 10
    metadata_workers: Optional[int] = None  # Default: min(8, max_concurrent_files * 2)
    hashing_workers: Optional[int] = None  # Default: min(8, max_concurrent_files * 2)
    batch_size: int = 500
    touch_batch_size: int = 500
    vector_batch_size: int = 100
    commit_interval: int = 100
    progress_update_interval: int = 10
    missing_chunk_size: int = 5000
    enable_folder_skip: bool = True

    def __post_init__(self):
        """Validate configuration values and set computed defaults.

        Raises:
            ValueError: If any configuration value is invalid.
        """
        if self.metadata_workers is None:
            self.metadata_workers = min(8, self.max_concurrent_files * 2)
        if self.hashing_workers is None:
            self.hashing_workers = min(8, self.max_concurrent_files * 2)
        if self.metadata_workers < 1:
            raise ValueError("metadata_workers must be >= 1")
        if self.hashing_workers < 1:
            raise ValueError("hashing_workers must be >= 1")
        if self.max_concurrent_files < 1:
            raise ValueError("max_concurrent_files must be >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.touch_batch_size < 1:
            raise ValueError("touch_batch_size must be >= 1")
        if self.vector_batch_size < 1:
            raise ValueError("vector_batch_size must be >= 1")
        if self.commit_interval < 1:
            raise ValueError("commit_interval must be >= 1")
        if self.progress_update_interval < 1:
            raise ValueError("progress_update_interval must be >= 1")
        if self.missing_chunk_size < 1:
            raise ValueError("missing_chunk_size must be >= 1")

