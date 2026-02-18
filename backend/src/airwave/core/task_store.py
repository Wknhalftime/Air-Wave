import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class TaskProgress(BaseModel):
    """Model representing the progress of a background task."""

    task_id: str
    task_type: str  # 'scan', 'sync', 'import'
    status: str  # 'running', 'completed', 'failed', 'cancelled'
    progress: float  # 0.0 to 1.0
    current: int
    total: int
    message: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    cancel_requested: bool = False  # Flag to request cancellation

    @field_serializer('started_at', 'completed_at')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        """Serialize datetime fields to ISO format strings."""
        return dt.isoformat() if dt else None


class TaskStore:
    """In-memory store for tracking background task progress.
    Thread-safe instance-based store with backward-compatible class methods.

    Usage (Instance-based - Recommended):
        # Create task store instance
        task_store = TaskStore()

        # Create new task
        task = task_store.create_task("task-123", "scan", total=100)

        # Update progress
        task_store.update_progress("task-123", current=50, message="Processing file 50")

        # Mark complete
        task_store.complete_task("task-123", success=True)

        # Retrieve status
        status = task_store.get_task("task-123")

    Usage (Class methods - Backward Compatible):
        # Uses global singleton instance
        task = TaskStore.create_task("task-123", "scan", total=100)
        TaskStore.update_progress("task-123", current=50, message="Processing file 50")
    """

    def __init__(self):
        """Initialize a new task store instance with isolated state."""
        self._tasks: Dict[str, TaskProgress] = {}
        self._lock = threading.Lock()

    def create_task(
        self, task_id: str, task_type: str, total: int
    ) -> TaskProgress:
        """Initialize a new task with progress tracking.

        Args:
            task_id: Unique identifier for the task
            task_type: Type of task ('scan', 'sync', 'import')
            total: Total number of items to process

        Returns:
            TaskProgress instance
        """
        with self._lock:
            task = TaskProgress(
                task_id=task_id,
                task_type=task_type,
                status="running",
                progress=0.0,
                current=0,
                total=total,
                message="Starting...",
                started_at=datetime.now(timezone.utc),
            )
            self._tasks[task_id] = task
            return task

    def update_progress(self, task_id: str, current: int, message: str) -> None:
        """Update the progress of an existing task and its message."""
        with self._lock:
            if task := self._tasks.get(task_id):
                task.current = current
                if task.total > 0:
                    task.progress = current / task.total
                else:
                    # Sync/scan does not know total in advance; use pseudo-progress so UI bar advances
                    task.progress = min(0.99, current / (current + 100)) if current > 0 else 0.0
                task.message = message

    def update_total(
        self, task_id: str, total: int, message: Optional[str] = None
    ) -> None:
        """Update the total count for a task during processing."""
        with self._lock:
            if task := self._tasks.get(task_id):
                task.total = total
                if message:
                    task.message = message
                # Recalculate progress
                task.progress = (
                    task.current / task.total if task.total > 0 else 0.0
                )

    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """Retrieve the status of a task.

        Args:
            task_id: Task identifier

        Returns:
            TaskProgress instance or None if not found
        """
        with self._lock:
            return self._tasks.get(task_id)

    def complete_task(
        self, task_id: str, success: bool = True, error: Optional[str] = None
    ) -> None:
        """Mark a task as completed or failed and set the final message."""
        with self._lock:
            if task := self._tasks.get(task_id):
                task.status = "completed" if success else "failed"
                task.completed_at = datetime.now(timezone.utc)
                task.error = error
                task.progress = 1.0 if success else task.progress
                task.message = (
                    "Completed successfully" if success else f"Failed: {error}"
                )

    def cleanup_old_tasks(self, hours: int = 1) -> None:
        """Remove completed tasks older than specified hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._lock:
            to_remove = [
                task_id
                for task_id, task in self._tasks.items()
                if task.completed_at and task.completed_at < cutoff
            ]
            for task_id in to_remove:
                del self._tasks[task_id]

    def get_all_tasks(self) -> Dict[str, TaskProgress]:
        """Get all tasks (for debugging/admin purposes).

        Returns:
            Dictionary of all tasks
        """
        with self._lock:
            return self._tasks.copy()

    def cancel_task(self, task_id: str) -> bool:
        """Request cancellation of a running task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancellation was requested, False if task not found or already completed
        """
        with self._lock:
            if task := self._tasks.get(task_id):
                if task.status == "running":
                    task.cancel_requested = True
                    task.message = "Cancellation requested..."
                    return True
        return False

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been requested to cancel.

        Args:
            task_id: Task identifier

        Returns:
            True if cancellation was requested, False otherwise
        """
        with self._lock:
            if task := self._tasks.get(task_id):
                return task.cancel_requested
        return False

    def mark_cancelled(self, task_id: str) -> None:
        """Mark a task as cancelled (called by the task itself when it stops).

        Args:
            task_id: Task identifier
        """
        with self._lock:
            if task := self._tasks.get(task_id):
                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                task.message = "Cancelled by user"


# Save instance methods before adding class methods
_instance_create_task = TaskStore.create_task
_instance_update_progress = TaskStore.update_progress
_instance_update_total = TaskStore.update_total
_instance_get_task = TaskStore.get_task
_instance_complete_task = TaskStore.complete_task
_instance_cleanup_old_tasks = TaskStore.cleanup_old_tasks
_instance_get_all_tasks = TaskStore.get_all_tasks
_instance_cancel_task = TaskStore.cancel_task
_instance_is_cancelled = TaskStore.is_cancelled
_instance_mark_cancelled = TaskStore.mark_cancelled

# Global singleton instance for backward compatibility
_global_task_store = TaskStore()


# Backward-compatible class methods (delegate to global instance)
# These allow existing code to continue working without changes
@classmethod
def _create_task_classmethod(cls, task_id: str, task_type: str, total: int) -> TaskProgress:
    """Backward-compatible class method."""
    return _instance_create_task(_global_task_store, task_id, task_type, total)


@classmethod
def _update_progress_classmethod(cls, task_id: str, current: int, message: str) -> None:
    """Backward-compatible class method."""
    _instance_update_progress(_global_task_store, task_id, current, message)


@classmethod
def _update_total_classmethod(cls, task_id: str, total: int, message: Optional[str] = None) -> None:
    """Backward-compatible class method."""
    _instance_update_total(_global_task_store, task_id, total, message)


@classmethod
def _get_task_classmethod(cls, task_id: str) -> Optional[TaskProgress]:
    """Backward-compatible class method."""
    return _instance_get_task(_global_task_store, task_id)


@classmethod
def _complete_task_classmethod(cls, task_id: str, success: bool = True, error: Optional[str] = None) -> None:
    """Backward-compatible class method."""
    _instance_complete_task(_global_task_store, task_id, success, error)


@classmethod
def _cleanup_old_tasks_classmethod(cls, hours: int = 1) -> None:
    """Backward-compatible class method."""
    _instance_cleanup_old_tasks(_global_task_store, hours)


@classmethod
def _get_all_tasks_classmethod(cls) -> Dict[str, TaskProgress]:
    """Backward-compatible class method."""
    return _instance_get_all_tasks(_global_task_store)


@classmethod
def _cancel_task_classmethod(cls, task_id: str) -> bool:
    """Backward-compatible class method."""
    return _instance_cancel_task(_global_task_store, task_id)


@classmethod
def _is_cancelled_classmethod(cls, task_id: str) -> bool:
    """Backward-compatible class method."""
    return _instance_is_cancelled(_global_task_store, task_id)


@classmethod
def _mark_cancelled_classmethod(cls, task_id: str) -> None:
    """Backward-compatible class method."""
    _instance_mark_cancelled(_global_task_store, task_id)


@classmethod
def _get_global_classmethod(cls) -> TaskStore:
    """Get the global singleton instance (for backward compatibility)."""
    return _global_task_store


# Add class methods to TaskStore for backward compatibility
TaskStore.create_task = _create_task_classmethod  # type: ignore
TaskStore.update_progress = _update_progress_classmethod  # type: ignore
TaskStore.update_total = _update_total_classmethod  # type: ignore
TaskStore.get_task = _get_task_classmethod  # type: ignore
TaskStore.complete_task = _complete_task_classmethod  # type: ignore
TaskStore.cleanup_old_tasks = _cleanup_old_tasks_classmethod  # type: ignore
TaskStore.get_all_tasks = _get_all_tasks_classmethod  # type: ignore
TaskStore.cancel_task = _cancel_task_classmethod  # type: ignore
TaskStore.is_cancelled = _is_cancelled_classmethod  # type: ignore
TaskStore.mark_cancelled = _mark_cancelled_classmethod  # type: ignore
TaskStore.get_global = _get_global_classmethod  # type: ignore
