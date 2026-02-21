"""In-memory store for tracking background task progress."""

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

    Thread-safe. Use the module-level functions (create_task, update_progress, etc.)
    for the global singleton, or instantiate TaskStore() for isolated state (e.g. tests).

    Usage (module-level - recommended):
        from airwave.core.task_store import create_task, update_progress, get_task

        task = create_task("task-123", "scan", total=100)
        update_progress("task-123", current=50, message="Processing...")
        status = get_task("task-123")

    Usage (instance-based, e.g. for dependency injection):
        task_store = TaskStore()
        task = task_store.create_task("task-123", "scan", total=100)
    """

    def __init__(self) -> None:
        """Initialize a new task store instance with isolated state."""
        self._tasks: Dict[str, TaskProgress] = {}
        self._lock = threading.Lock()

    def create_task(self, task_id: str, task_type: str, total: int) -> TaskProgress:
        """Initialize a new task with progress tracking."""
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
                task.progress = task.current / task.total if task.total > 0 else 0.0

    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """Retrieve the status of a task."""
        with self._lock:
            return self._tasks.get(task_id)

    def complete_task(
        self, task_id: str, success: bool = True, error: Optional[str] = None
    ) -> None:
        """Mark a task as completed or failed."""
        with self._lock:
            if task := self._tasks.get(task_id):
                task.status = "completed" if success else "failed"
                task.completed_at = datetime.now(timezone.utc)
                task.error = error
                task.progress = 1.0 if success else task.progress
                task.message = "Completed successfully" if success else f"Failed: {error}"

    def cleanup_old_tasks(self, hours: int = 1) -> None:
        """Remove completed tasks older than specified hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._lock:
            to_remove = [
                tid
                for tid, task in self._tasks.items()
                if task.completed_at and task.completed_at < cutoff
            ]
            for tid in to_remove:
                del self._tasks[tid]

    def get_all_tasks(self) -> Dict[str, TaskProgress]:
        """Get all tasks (for debugging/admin purposes)."""
        with self._lock:
            return self._tasks.copy()

    def cancel_task(self, task_id: str) -> bool:
        """Request cancellation of a running task."""
        with self._lock:
            if task := self._tasks.get(task_id):
                if task.status == "running":
                    task.cancel_requested = True
                    task.message = "Cancellation requested..."
                    return True
        return False

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been requested to cancel."""
        with self._lock:
            if task := self._tasks.get(task_id):
                return task.cancel_requested
        return False

    def mark_cancelled(self, task_id: str) -> None:
        """Mark a task as cancelled (called by the task itself when it stops)."""
        with self._lock:
            if task := self._tasks.get(task_id):
                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                task.message = "Cancelled by user"


# Global singleton instance
task_store = TaskStore()

# Module-level functions delegating to global task_store
create_task = task_store.create_task
update_progress = task_store.update_progress
update_total = task_store.update_total
get_task = task_store.get_task
complete_task = task_store.complete_task
cleanup_old_tasks = task_store.cleanup_old_tasks
get_all_tasks = task_store.get_all_tasks
cancel_task = task_store.cancel_task
is_cancelled = task_store.is_cancelled
mark_cancelled = task_store.mark_cancelled


def get_task_store() -> TaskStore:
    """Return the global task store instance (for dependency injection)."""
    return task_store
