"""Performance monitoring utilities for tracking operation metrics.

This module provides utilities for tracking and logging performance metrics
across the application, with a focus on scanner operations.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from loguru import logger


@dataclass
class FileMetrics:
    """File processing and optimization metrics."""

    files_processed: int = 0
    files_skipped: int = 0
    files_created: int = 0
    files_moved: int = 0
    files_errored: int = 0
    metadata_extractions: int = 0
    metadata_extractions_skipped: int = 0
    legacy_files_updated: int = 0  # Files with mtime=None that were updated
    size_changed_files: int = 0  # Files where size changed
    touch_batches: int = 0
    touch_files_total: int = 0
    max_concurrent_files: int = 0
    directories_processed: int = 0
    directories_skipped: int = 0


@dataclass
class DbMetrics:
    """Database operation metrics."""

    db_queries_select: int = 0
    db_queries_update: int = 0
    db_queries_insert: int = 0
    commits_executed: int = 0
    commits_skipped: int = 0
    move_detection_queries: int = 0
    move_detection_queries_skipped: int = 0


@dataclass
class TimingMetrics:
    """Timing and duration metrics."""

    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    time_metadata_extraction: float = 0.0
    time_file_hashing: float = 0.0
    time_database_ops: float = 0.0
    time_vector_indexing: float = 0.0


@dataclass
class PerformanceMetrics:
    """Performance metrics for scanner operations.

    Composes FileMetrics, DbMetrics, and TimingMetrics for structured organization.
    """

    file: FileMetrics = field(default_factory=FileMetrics)
    db: DbMetrics = field(default_factory=DbMetrics)
    timing: TimingMetrics = field(default_factory=TimingMetrics)

    def finish(self) -> None:
        """Mark the operation as finished and calculate duration."""
        self.timing.end_time = time.time()
        self.timing.duration_seconds = (
            self.timing.end_time - self.timing.start_time
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Duration in seconds (convenience access)."""
        return self.timing.duration_seconds

    @property
    def files_per_second(self) -> float:
        """Calculate files processed per second."""
        d = self.timing.duration_seconds
        if d and d > 0:
            return self.file.files_processed / d
        return 0.0

    @property
    def metadata_extraction_rate(self) -> float:
        """Calculate percentage of files that required metadata extraction."""
        if self.file.files_processed > 0:
            return (
                self.file.metadata_extractions / self.file.files_processed
            ) * 100
        return 0.0

    @property
    def skip_rate(self) -> float:
        """Calculate percentage of files that were skipped (stat-first skip)."""
        if self.file.files_processed > 0:
            return (self.file.files_skipped / self.file.files_processed) * 100
        return 0.0

    @property
    def commit_efficiency(self) -> float:
        """Calculate percentage of commits that were skipped (optimization)."""
        total = self.db.commits_executed + self.db.commits_skipped
        if total > 0:
            return (self.db.commits_skipped / total) * 100
        return 0.0

    def _percentage(self, time_value: float) -> float:
        """Calculate percentage of total duration."""
        d = self.timing.duration_seconds
        if d and d > 0:
            return (time_value / d) * 100
        return 0.0

    def log_summary(self, operation_name: str = "Scanner") -> None:
        """Log a comprehensive performance summary."""
        if not self.timing.duration_seconds:
            self.finish()

        f, d, t = self.file, self.db, self.timing
        logger.info(
            f"\n{'='*80}\n"
            f"{operation_name} Performance Summary\n"
            f"{'='*80}\n"
            f"Duration: {t.duration_seconds:.2f}s\n"
            f"Files Processed: {f.files_processed:,} ({self.files_per_second:.1f} files/sec)\n"
            f"  - Skipped (unchanged): {f.files_skipped:,} ({self.skip_rate:.1f}%)\n"
            f"  - Created (new): {f.files_created:,}\n"
            f"  - Moved (path changed): {f.files_moved:,}\n"
            f"  - Errors: {f.files_errored:,}\n"
            f"\n"
            f"Parallel Processing:\n"
            f"  - Max concurrent files: {f.max_concurrent_files}\n"
            f"  - Directories processed: {f.directories_processed:,}\n"
            f"  - Directories skipped (folder-level): {f.directories_skipped:,}\n"
            f"\n"
            f"Optimization Metrics:\n"
            f"  - Metadata extractions: {f.metadata_extractions:,} ({self.metadata_extraction_rate:.1f}%)\n"
            f"  - Metadata skipped (Fix 1): {f.metadata_extractions_skipped:,}\n"
            f"  - Legacy files updated (Fix 1): {f.legacy_files_updated:,}\n"
            f"  - Size changed files (Fix 2): {f.size_changed_files:,}\n"
            f"  - Commits executed: {d.commits_executed:,}\n"
            f"  - Commits skipped (Fix 3): {d.commits_skipped:,} ({self.commit_efficiency:.1f}%)\n"
            f"  - Move detection queries: {d.move_detection_queries:,}\n"
            f"  - Move detection skipped (Fix 4): {d.move_detection_queries_skipped:,}\n"
            f"\n"
            f"Database Operations:\n"
            f"  - SELECT queries: {d.db_queries_select:,}\n"
            f"  - UPDATE queries: {d.db_queries_update:,}\n"
            f"  - INSERT queries: {d.db_queries_insert:,}\n"
            f"  - Touch batches: {f.touch_batches:,} ({f.touch_files_total:,} files)\n"
            f"\n"
            f"Timing Breakdown:\n"
            f"  - Metadata extraction: {t.time_metadata_extraction:.2f}s ({self._percentage(t.time_metadata_extraction):.1f}%)\n"
            f"  - File hashing: {t.time_file_hashing:.2f}s ({self._percentage(t.time_file_hashing):.1f}%)\n"
            f"  - Database operations: {t.time_database_ops:.2f}s ({self._percentage(t.time_database_ops):.1f}%)\n"
            f"  - Vector indexing: {t.time_vector_indexing:.2f}s ({self._percentage(t.time_vector_indexing):.1f}%)\n"
            f"{'='*80}\n"
        )

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for JSON serialization."""
        f, d, t = self.file, self.db, self.timing
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": t.duration_seconds,
            "files_processed": f.files_processed,
            "files_per_second": self.files_per_second,
            "files_skipped": f.files_skipped,
            "files_created": f.files_created,
            "files_moved": f.files_moved,
            "files_errored": f.files_errored,
            "metadata_extractions": f.metadata_extractions,
            "metadata_extractions_skipped": f.metadata_extractions_skipped,
            "metadata_extraction_rate": self.metadata_extraction_rate,
            "skip_rate": self.skip_rate,
            "legacy_files_updated": f.legacy_files_updated,
            "size_changed_files": f.size_changed_files,
            "commits_executed": d.commits_executed,
            "commits_skipped": d.commits_skipped,
            "commit_efficiency": self.commit_efficiency,
            "move_detection_queries": d.move_detection_queries,
            "move_detection_queries_skipped": d.move_detection_queries_skipped,
            "db_queries_select": d.db_queries_select,
            "db_queries_update": d.db_queries_update,
            "db_queries_insert": d.db_queries_insert,
            "touch_batches": f.touch_batches,
            "touch_files_total": f.touch_files_total,
            "max_concurrent_files": f.max_concurrent_files,
            "directories_processed": f.directories_processed,
            "directories_skipped": f.directories_skipped,
            "time_metadata_extraction": t.time_metadata_extraction,
            "time_file_hashing": t.time_file_hashing,
            "time_database_ops": t.time_database_ops,
            "time_vector_indexing": t.time_vector_indexing,
        }


@contextmanager
def track_operation(operation_name: str = "Operation"):
    """Context manager for tracking operation performance.

    Usage:
        with track_operation("Scanner") as metrics:
            metrics.file.files_processed += 1
        # Automatically logs summary on exit
    """
    metrics = PerformanceMetrics()
    try:
        yield metrics
    finally:
        metrics.finish()
        metrics.log_summary(operation_name)
