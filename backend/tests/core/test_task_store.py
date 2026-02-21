"""Unit tests for TaskStore."""
from datetime import datetime, timedelta, timezone

from airwave.core.task_store import (
    cleanup_old_tasks,
    complete_task,
    create_task,
    get_all_tasks,
    get_task,
    get_task_store,
    update_progress,
    update_total,
)


class TestTaskStore:
    """Test suite for TaskStore."""

    def setup_method(self):
        """Clear task store before each test."""
        get_task_store()._tasks.clear()

    def test_create_task(self):
        task = create_task("test-123", "scan", total=100)
        assert task.task_id == "test-123"
        assert task.task_type == "scan"
        assert task.status == "running"
        assert task.total == 100
        assert task.current == 0
        assert task.progress == 0.0
        assert isinstance(task.started_at, datetime)
        assert task.completed_at is None

    def test_get_task(self):
        create_task("test-456", "sync", total=50)
        retrieved = get_task("test-456")
        assert retrieved is not None
        assert retrieved.task_id == "test-456"

    def test_get_nonexistent_task(self):
        assert get_task("nonexistent") is None

    def test_update_progress(self):
        create_task("test-789", "import", total=200)
        update_progress("test-789", 100, "Halfway done")
        task = get_task("test-789")
        assert task.current == 100
        assert task.progress == 0.5

    def test_update_total(self):
        create_task("test-total", "scan", total=1)
        update_total("test-total", 500, "Found 500 files")
        task = get_task("test-total")
        assert task.total == 500
        assert task.progress == 0.0

    def test_update_total_recalculates_progress(self):
        create_task("test-recalc", "scan", total=100)
        update_progress("test-recalc", 50, "Half way")
        assert get_task("test-recalc").progress == 0.5
        update_total("test-recalc", 200)
        assert get_task("test-recalc").progress == 0.25

    def test_complete_task_success(self):
        create_task("test-complete", "scan", total=100)
        update_progress("test-complete", 100, "Done")
        complete_task("test-complete", success=True)
        task = get_task("test-complete")
        assert task.status == "completed"
        assert task.progress == 1.0
        assert task.error is None

    def test_complete_task_failure(self):
        create_task("test-fail", "import", total=100)
        complete_task("test-fail", success=False, error="File not found")
        task = get_task("test-fail")
        assert task.status == "failed"
        assert task.error == "File not found"

    def test_multiple_tasks(self):
        create_task("task-1", "scan", 100)
        create_task("task-2", "sync", 200)
        create_task("task-3", "import", 300)
        assert len(get_all_tasks()) == 3
        update_progress("task-1", 50, "Task 1 progress")
        update_progress("task-2", 100, "Task 2 progress")
        assert get_task("task-1").current == 50
        assert get_task("task-2").current == 100
        assert get_task("task-3").current == 0

    def test_cleanup_old_tasks(self):
        create_task("old-task", "scan", 100)
        complete_task("old-task", success=True)
        get_task("old-task").completed_at = datetime.now(timezone.utc) - timedelta(hours=2)
        create_task("new-task", "sync", 100)
        complete_task("new-task", success=True)
        cleanup_old_tasks(hours=1)
        assert get_task("old-task") is None
        assert get_task("new-task") is not None

    def test_progress_calculation_with_zero_total(self):
        create_task("zero-total", "scan", total=0)
        update_progress("zero-total", 10, "Processing")
        task = get_task("zero-total")
        assert 0.0 <= task.progress <= 1.0
        assert not (task.progress != task.progress)

    def test_task_progress_model_serialization(self):
        create_task("serialize-test", "scan", total=100)
        task = get_task("serialize-test")
        d = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "started_at": task.started_at.isoformat() if task.started_at else None,
        }
        assert d["task_id"] == "serialize-test"
        assert d["task_type"] == "scan"
        assert isinstance(d["started_at"], str)
