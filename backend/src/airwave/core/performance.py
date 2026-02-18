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
class PerformanceMetrics:
    """Performance metrics for scanner operations."""
    
    # Timing metrics
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    
    # File processing metrics
    files_processed: int = 0
    files_skipped: int = 0
    files_created: int = 0
    files_moved: int = 0
    files_errored: int = 0
    
    # Performance optimization metrics
    metadata_extractions: int = 0
    metadata_extractions_skipped: int = 0
    db_queries_select: int = 0
    db_queries_update: int = 0
    db_queries_insert: int = 0
    commits_executed: int = 0
    commits_skipped: int = 0
    move_detection_queries: int = 0
    move_detection_queries_skipped: int = 0
    
    # Legacy file handling
    legacy_files_updated: int = 0  # Files with mtime=None that were updated
    size_changed_files: int = 0    # Files where size changed
    
    # Batch operation metrics
    touch_batches: int = 0
    touch_files_total: int = 0

    # Parallel processing metrics
    max_concurrent_files: int = 0  # Maximum concurrent file processing limit
    directories_processed: int = 0  # Number of directories scanned
    directories_skipped: int = 0  # Directories skipped (folder-level mtime unchanged)

    # Detailed timing metrics (in seconds)
    time_metadata_extraction: float = 0.0  # Total time spent extracting metadata
    time_file_hashing: float = 0.0  # Total time spent calculating file hashes
    time_database_ops: float = 0.0  # Total time spent in database operations
    time_vector_indexing: float = 0.0  # Total time spent in vector indexing
    
    def finish(self) -> None:
        """Mark the operation as finished and calculate duration."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
    
    @property
    def files_per_second(self) -> float:
        """Calculate files processed per second."""
        if self.duration_seconds and self.duration_seconds > 0:
            return self.files_processed / self.duration_seconds
        return 0.0
    
    @property
    def metadata_extraction_rate(self) -> float:
        """Calculate percentage of files that required metadata extraction."""
        if self.files_processed > 0:
            return (self.metadata_extractions / self.files_processed) * 100
        return 0.0
    
    @property
    def skip_rate(self) -> float:
        """Calculate percentage of files that were skipped (stat-first skip)."""
        if self.files_processed > 0:
            return (self.files_skipped / self.files_processed) * 100
        return 0.0
    
    @property
    def commit_efficiency(self) -> float:
        """Calculate percentage of commits that were skipped (optimization)."""
        total_commit_opportunities = self.commits_executed + self.commits_skipped
        if total_commit_opportunities > 0:
            return (self.commits_skipped / total_commit_opportunities) * 100
        return 0.0
    
    def log_summary(self, operation_name: str = "Scanner") -> None:
        """Log a comprehensive performance summary."""
        if not self.duration_seconds:
            self.finish()
        
        logger.info(
            f"\n{'='*80}\n"
            f"{operation_name} Performance Summary\n"
            f"{'='*80}\n"
            f"Duration: {self.duration_seconds:.2f}s\n"
            f"Files Processed: {self.files_processed:,} ({self.files_per_second:.1f} files/sec)\n"
            f"  - Skipped (unchanged): {self.files_skipped:,} ({self.skip_rate:.1f}%)\n"
            f"  - Created (new): {self.files_created:,}\n"
            f"  - Moved (path changed): {self.files_moved:,}\n"
            f"  - Errors: {self.files_errored:,}\n"
            f"\n"
            f"Parallel Processing:\n"
            f"  - Max concurrent files: {self.max_concurrent_files}\n"
            f"  - Directories processed: {self.directories_processed:,}\n"
            f"  - Directories skipped (folder-level): {self.directories_skipped:,}\n"
            f"\n"
            f"Optimization Metrics:\n"
            f"  - Metadata extractions: {self.metadata_extractions:,} ({self.metadata_extraction_rate:.1f}%)\n"
            f"  - Metadata skipped (Fix 1): {self.metadata_extractions_skipped:,}\n"
            f"  - Legacy files updated (Fix 1): {self.legacy_files_updated:,}\n"
            f"  - Size changed files (Fix 2): {self.size_changed_files:,}\n"
            f"  - Commits executed: {self.commits_executed:,}\n"
            f"  - Commits skipped (Fix 3): {self.commits_skipped:,} ({self.commit_efficiency:.1f}%)\n"
            f"  - Move detection queries: {self.move_detection_queries:,}\n"
            f"  - Move detection skipped (Fix 4): {self.move_detection_queries_skipped:,}\n"
            f"\n"
            f"Database Operations:\n"
            f"  - SELECT queries: {self.db_queries_select:,}\n"
            f"  - UPDATE queries: {self.db_queries_update:,}\n"
            f"  - INSERT queries: {self.db_queries_insert:,}\n"
            f"  - Touch batches: {self.touch_batches:,} ({self.touch_files_total:,} files)\n"
            f"\n"
            f"Timing Breakdown:\n"
            f"  - Metadata extraction: {self.time_metadata_extraction:.2f}s ({self._percentage(self.time_metadata_extraction):.1f}%)\n"
            f"  - File hashing: {self.time_file_hashing:.2f}s ({self._percentage(self.time_file_hashing):.1f}%)\n"
            f"  - Database operations: {self.time_database_ops:.2f}s ({self._percentage(self.time_database_ops):.1f}%)\n"
            f"  - Vector indexing: {self.time_vector_indexing:.2f}s ({self._percentage(self.time_vector_indexing):.1f}%)\n"
            f"{'='*80}\n"
        )

    def _percentage(self, time_value: float) -> float:
        """Calculate percentage of total duration."""
        if self.duration_seconds and self.duration_seconds > 0:
            return (time_value / self.duration_seconds) * 100
        return 0.0
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": self.duration_seconds,
            "files_processed": self.files_processed,
            "files_per_second": self.files_per_second,
            "files_skipped": self.files_skipped,
            "files_created": self.files_created,
            "files_moved": self.files_moved,
            "files_errored": self.files_errored,
            "metadata_extractions": self.metadata_extractions,
            "metadata_extractions_skipped": self.metadata_extractions_skipped,
            "metadata_extraction_rate": self.metadata_extraction_rate,
            "skip_rate": self.skip_rate,
            "legacy_files_updated": self.legacy_files_updated,
            "size_changed_files": self.size_changed_files,
            "commits_executed": self.commits_executed,
            "commits_skipped": self.commits_skipped,
            "commit_efficiency": self.commit_efficiency,
            "move_detection_queries": self.move_detection_queries,
            "move_detection_queries_skipped": self.move_detection_queries_skipped,
            "db_queries_select": self.db_queries_select,
            "db_queries_update": self.db_queries_update,
            "db_queries_insert": self.db_queries_insert,
            "touch_batches": self.touch_batches,
            "touch_files_total": self.touch_files_total,
            "max_concurrent_files": self.max_concurrent_files,
            "directories_processed": self.directories_processed,
            "directories_skipped": self.directories_skipped,
            "time_metadata_extraction": self.time_metadata_extraction,
            "time_file_hashing": self.time_file_hashing,
            "time_database_ops": self.time_database_ops,
            "time_vector_indexing": self.time_vector_indexing,
        }


@contextmanager
def track_operation(operation_name: str = "Operation"):
    """Context manager for tracking operation performance.
    
    Usage:
        with track_operation("Scanner") as metrics:
            # ... do work ...
            metrics.files_processed += 1
        # Automatically logs summary on exit
    """
    metrics = PerformanceMetrics()
    try:
        yield metrics
    finally:
        metrics.finish()
        metrics.log_summary(operation_name)

