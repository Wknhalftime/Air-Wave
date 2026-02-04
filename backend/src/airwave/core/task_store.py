import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class TaskProgress(BaseModel):
    """Model representing the progress of a background task."""

    task_id: str
    task_type: str  # 'scan', 'sync', 'import'
    status: str  # 'running', 'completed', 'failed'
    progress: float  # 0.0 to 1.0
    current: int
    total: int
    message: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    @field_serializer('started_at', 'completed_at')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        """Serialize datetime fields to ISO format strings."""
        return dt.isoformat() if dt else None


class TaskStore:
    """In-memory store for tracking background task progress.
    Thread-safe singleton for sharing state across async workers.

    Usage:
        # Create new task
        task = TaskStore.create_task("task-123", "scan", total=100)

        # Update progress
        TaskStore.update_progress("task-123", current=50, message="Processing file 50")

        # Mark complete
        TaskStore.complete_task("task-123", success=True)

        # Retrieve status
        status = TaskStore.get_task("task-123")
    """

    _tasks: Dict[str, TaskProgress] = {}
    _lock = threading.Lock()

    @classmethod
    def create_task(
        cls, task_id: str, task_type: str, total: int
    ) -> TaskProgress:
        """Initialize a new task with progress tracking.

        Args:
            task_id: Unique identifier for the task
            task_type: Type of task ('scan', 'sync', 'import')
            total: Total number of items to process

        Returns:
            TaskProgress instance
        """
        with cls._lock:
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
            cls._tasks[task_id] = task
            return task

    @classmethod
    def update_progress(cls, task_id: str, current: int, message: str) -> None:
        """Update the progress of an existing task and its message."""
        with cls._lock:
            if task := cls._tasks.get(task_id):
                task.current = current
                task.progress = current / task.total if task.total > 0 else 0.0
                task.message = message

    @classmethod
    def update_total(
        cls, task_id: str, total: int, message: Optional[str] = None
    ) -> None:
        """Update the total count for a task during processing."""
        with cls._lock:
            if task := cls._tasks.get(task_id):
                task.total = total
                if message:
                    task.message = message
                # Recalculate progress
                task.progress = (
                    task.current / task.total if task.total > 0 else 0.0
                )

    @classmethod
    def get_task(cls, task_id: str) -> Optional[TaskProgress]:
        """Retrieve the status of a task.

        Args:
            task_id: Task identifier

        Returns:
            TaskProgress instance or None if not found
        """
        with cls._lock:
            return cls._tasks.get(task_id)

    @classmethod
    def complete_task(
        cls, task_id: str, success: bool = True, error: Optional[str] = None
    ) -> None:
        """Mark a task as completed or failed and set the final message."""
        with cls._lock:
            if task := cls._tasks.get(task_id):
                task.status = "completed" if success else "failed"
                task.completed_at = datetime.now(timezone.utc)
                task.error = error
                task.progress = 1.0 if success else task.progress
                task.message = (
                    "Completed successfully" if success else f"Failed: {error}"
                )

    @classmethod
    def cleanup_old_tasks(cls, hours: int = 1) -> None:
        """Remove completed tasks older than specified hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with cls._lock:
            to_remove = [
                task_id
                for task_id, task in cls._tasks.items()
                if task.completed_at and task.completed_at < cutoff
            ]
            for task_id in to_remove:
                del cls._tasks[task_id]

    @classmethod
    def get_all_tasks(cls) -> Dict[str, TaskProgress]:
        """Get all tasks (for debugging/admin purposes).

        Returns:
            Dictionary of all tasks
        """
        with cls._lock:
            return cls._tasks.copy()
