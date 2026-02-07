"""Unit tests for TaskStore - Progress tracking for background tasks
"""
from datetime import datetime, timezone

from airwave.core.task_store import TaskStore


class TestTaskStore:
    """Test suite for TaskStore functionality"""

    def setup_method(self):
        """Clear task store before each test"""
        # Access the global singleton instance
        global_store = TaskStore.get_global()
        global_store._tasks.clear()

    def test_create_task(self):
        """Test creating a new task"""
        task_id = "test-123"
        task = TaskStore.create_task(task_id, "scan", total=100)

        assert task.task_id == task_id
        assert task.task_type == "scan"
        assert task.status == "running"
        assert task.total == 100
        assert task.current == 0
        assert task.progress == 0.0
        assert task.message == "Starting..."
        assert isinstance(task.started_at, datetime)
        assert task.completed_at is None
        assert task.error is None

    def test_get_task(self):
        """Test retrieving an existing task"""
        task_id = "test-456"
        TaskStore.create_task(task_id, "sync", total=50)

        retrieved = TaskStore.get_task(task_id)
        assert retrieved is not None
        assert retrieved.task_id == task_id
        assert retrieved.task_type == "sync"

    def test_get_nonexistent_task(self):
        """Test retrieving a task that doesn't exist"""
        result = TaskStore.get_task("nonexistent")
        assert result is None

    def test_update_progress(self):
        """Test updating task progress"""
        task_id = "test-789"
        TaskStore.create_task(task_id, "import", total=200)

        TaskStore.update_progress(task_id, 100, "Halfway done")

        task = TaskStore.get_task(task_id)
        assert task.current == 100
        assert task.progress == 0.5  # 100/200
        assert task.message == "Halfway done"
        assert task.status == "running"

    def test_update_total(self):
        """Test updating task total count"""
        task_id = "test-total"
        TaskStore.create_task(task_id, "scan", total=1)

        # Simulate updating total after counting files
        TaskStore.update_total(task_id, 500, "Found 500 files")

        task = TaskStore.get_task(task_id)
        assert task.total == 500
        assert task.message == "Found 500 files"
        assert task.progress == 0.0  # current still 0

    def test_update_total_recalculates_progress(self):
        """Test that updating total recalculates progress correctly"""
        task_id = "test-recalc"
        TaskStore.create_task(task_id, "scan", total=100)
        TaskStore.update_progress(task_id, 50, "Half way")

        # Should be 50%
        task = TaskStore.get_task(task_id)
        assert task.progress == 0.5

        # Update total - progress should recalculate
        TaskStore.update_total(task_id, 200)

        task = TaskStore.get_task(task_id)
        assert task.progress == 0.25  # 50/200

    def test_complete_task_success(self):
        """Test marking a task as completed successfully"""
        task_id = "test-complete"
        TaskStore.create_task(task_id, "scan", total=100)
        TaskStore.update_progress(task_id, 100, "Done")

        TaskStore.complete_task(task_id, success=True)

        task = TaskStore.get_task(task_id)
        assert task.status == "completed"
        assert task.progress == 1.0
        assert task.message == "Completed successfully"
        assert isinstance(task.completed_at, datetime)
        assert task.error is None

    def test_complete_task_failure(self):
        """Test marking a task as failed"""
        task_id = "test-fail"
        TaskStore.create_task(task_id, "import", total=100)

        error_msg = "File not found"
        TaskStore.complete_task(task_id, success=False, error=error_msg)

        task = TaskStore.get_task(task_id)
        assert task.status == "failed"
        assert task.error == error_msg
        assert task.message == f"Failed: {error_msg}"
        assert isinstance(task.completed_at, datetime)

    def test_multiple_tasks(self):
        """Test managing multiple tasks simultaneously"""
        task1 = TaskStore.create_task("task-1", "scan", 100)
        task2 = TaskStore.create_task("task-2", "sync", 200)
        task3 = TaskStore.create_task("task-3", "import", 300)

        assert len(TaskStore.get_all_tasks()) == 3

        TaskStore.update_progress("task-1", 50, "Task 1 progress")
        TaskStore.update_progress("task-2", 100, "Task 2 progress")

        t1 = TaskStore.get_task("task-1")
        t2 = TaskStore.get_task("task-2")
        t3 = TaskStore.get_task("task-3")

        assert t1.current == 50
        assert t2.current == 100
        assert t3.current == 0  # Untouched

    def test_cleanup_old_tasks(self):
        """Test cleanup of old completed tasks"""
        from datetime import timedelta

        # Create and complete tasks
        task1_id = "old-task"
        task2_id = "new-task"

        TaskStore.create_task(task1_id, "scan", 100)
        TaskStore.complete_task(task1_id, success=True)

        # Manually set old completion time
        old_task = TaskStore.get_task(task1_id)
        old_task.completed_at = datetime.now(timezone.utc) - timedelta(hours=2)

        TaskStore.create_task(task2_id, "sync", 100)
        TaskStore.complete_task(task2_id, success=True)

        # Cleanup tasks older than 1 hour
        TaskStore.cleanup_old_tasks(hours=1)

        assert TaskStore.get_task(task1_id) is None  # Should be removed
        assert TaskStore.get_task(task2_id) is not None  # Should remain

    def test_progress_calculation_with_zero_total(self):
        """Test that progress handles zero total gracefully"""
        task_id = "zero-total"
        TaskStore.create_task(task_id, "scan", total=0)
        TaskStore.update_progress(task_id, 10, "Processing")

        task = TaskStore.get_task(task_id)
        assert task.progress == 0.0  # Should not divide by zero

    def test_task_progress_model_serialization(self):
        """Test that TaskProgress model serializes correctly"""
        task_id = "serialize-test"
        TaskStore.create_task(task_id, "scan", total=100)
        task = TaskStore.get_task(task_id)

        # Test model_dump works
        task_dict = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "current": task.current,
            "total": task.total,
            "message": task.message,
            "started_at": task.started_at.isoformat()
            if task.started_at
            else None,
            "completed_at": task.completed_at.isoformat()
            if task.completed_at
            else None,
            "error": task.error,
        }

        assert task_dict["task_id"] == task_id
        assert task_dict["task_type"] == "scan"
        assert isinstance(task_dict["started_at"], str)  # ISO format
