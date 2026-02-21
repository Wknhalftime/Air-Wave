from unittest.mock import AsyncMock, patch

import pytest
from airwave.core.models import SystemSetting
from sqlalchemy import select


@pytest.mark.asyncio
async def test_get_settings(client, db_session):
    # Setup
    setting = SystemSetting(key="test_key", value="test_value")
    db_session.add(setting)
    await db_session.commit()

    response = await client.get("/api/v1/admin/settings")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    found = next((s for s in data if s["key"] == "test_key"), None)
    assert found
    assert found["value"] == "test_value"


@pytest.mark.asyncio
async def test_update_setting(client, db_session):
    payload = {"key": "new_key", "value": "new_value", "description": "desc"}

    response = await client.post("/api/v1/admin/settings", json=payload)
    assert response.status_code == 200

    # Verify in DB
    result = await db_session.execute(
        select(SystemSetting).where(SystemSetting.key == "new_key")
    )
    setting = result.scalar_one_or_none()
    assert setting
    assert setting.value == "new_value"


@pytest.mark.asyncio
async def test_trigger_scan(client):
    # Mock the background task
    with patch(
        "airwave.api.routers.admin.run_sync_files", new_callable=AsyncMock
    ) as mock_sync:
        response = await client.post(
            "/api/v1/admin/scan", json={"path": "/tmp/music"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "task_id" in data

        # Verify Background task was called?
        # FastAPIs BackgroundTasks usually executing after response.
        # With AsyncClient and ASGI, middleware handles it.
        # However, verifying call args might be tricky if it runs async.
        # But we can verify TaskStore content immediately as endpoints create it BEFORE response.

        from airwave.core.task_store import get_task

        task = get_task(data["task_id"])
        assert task
        assert task.status == "running"
        assert task.total == 1  # Initial dummy


@pytest.mark.asyncio
async def test_trigger_internal_scan(client):
    with patch(
        "airwave.api.routers.admin.run_scan", new_callable=AsyncMock
    ) as mock_scan:
        response = await client.post("/api/v1/admin/trigger-scan")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"]

        from airwave.core.task_store import get_task

        task = get_task(data["task_id"])
        assert task
        assert task.task_type == "scan"
