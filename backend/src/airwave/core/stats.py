"""Statistics tracking dataclasses for scan and match operations.

This module provides type-safe dataclasses for tracking statistics during
file scanning and matching operations, replacing primitive dict usage with
structured, validated data types.
"""

from dataclasses import dataclass, field


@dataclass
class ScanStats:
    """Statistics for file scanning operations.

    Tracks the progress and results of scanning audio files in a directory.
    Provides type safety and validation for scan statistics.

    Attributes:
        processed: Total number of files processed (attempted).
        created: Number of new library files created.
        skipped: Number of files skipped (already exist or invalid).
        errors: Number of files that failed to process.
        linked: Number of files linked to existing recordings (currently unused).
        moved: Number of files detected as moved (path update, same content).

    Example:
        >>> stats = ScanStats()
        >>> stats.processed += 1
        >>> stats.created += 1
        >>> print(stats.to_dict())
        {'processed': 1, 'created': 1, 'skipped': 0, 'errors': 0, 'linked': 0, 'moved': 0}
    """

    processed: int = 0
    created: int = 0
    skipped: int = 0
    errors: int = 0
    linked: int = 0
    moved: int = 0
    cancelled: bool = False  # Set when user requests cancel; scanner exits after current batch

    def to_dict(self) -> dict:
        """Convert stats to dictionary for API responses.

        Returns:
            Dictionary with all stat fields.
        """
        return {
            "processed": self.processed,
            "created": self.created,
            "skipped": self.skipped,
            "errors": self.errors,
            "linked": self.linked,
            "moved": self.moved,
        }

    def __str__(self) -> str:
        """Human-readable string representation.

        Returns:
            Formatted string with key statistics.
        """
        return (
            f"ScanStats(processed={self.processed}, created={self.created}, "
            f"skipped={self.skipped}, errors={self.errors}, moved={self.moved})"
        )

