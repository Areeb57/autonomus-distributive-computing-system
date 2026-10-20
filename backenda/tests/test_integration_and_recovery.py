"""
Integration, Recovery, Orphaned File Cleanup, and Frontend Parity Tests (Phase 10).
"""

from __future__ import annotations

import io
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.state_machine import TaskState
from app.core.websocket import ws_hub
from app.models.project import Project, ProjectMembership
from app.models.training import TrainingConfiguration, TrainingRun, TrainingTask
from app.models.user import User
from app.schemas.project import ProjectDetailResponse, WorkerNodeResponse
from app.services.recovery import recovery_service

settings = get_settings()


# Helper: register user and obtain bearer token
async def create_user_and_token(
    client: AsyncClient,
    email: str = "recovery_dev@example.com",
    username: str = "recoverydev",
) -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "display_name": "Recovery Operator",
            "password": "Password123!",
        },
    )
    assert res.status_code == 201
    return res.json()["access_token"]


# ── 1. Stale Task Reclamation Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_reclaim_stale_tasks_requeues_and_increments_retry(test_session: AsyncSession):
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Create stale task with expired lease
    stale_task = TrainingTask(
        id=uuid.uuid4(),
        project_id=project_id,
        run_id=run_id,
        status="leased",
        step_start=0,
        step_end=50,
        lease_token="expired_token_123",
        lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    test_session.add(stale_task)
    await test_session.commit()

    reclaimed = await recovery_service.reclaim_stale_tasks(test_session, max_retries=3)
    await test_session.commit()

    assert len(reclaimed) >= 1
    found = next((r for r in reclaimed if r["task_id"] == str(stale_task.id)), None)
    assert found is not None
    assert found["action"] == "requeued"
    assert found["retry_count"] == 1

    # Verify database state
    await test_session.refresh(stale_task)
    assert stale_task.status == TaskState.PENDING.value
    assert stale_task.lease_token is None
    assert "[retry:1]" in (stale_task.error_details or "")


@pytest.mark.asyncio
async def test_reclaim_stale_tasks_marks_failed_after_max_retries(test_session: AsyncSession):
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()

    exhausted_task = TrainingTask(
        id=uuid.uuid4(),
        project_id=project_id,
        run_id=run_id,
        status="running",
        step_start=50,
        step_end=100,
        lease_token="expired_token_456",
        lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        error_details="[retry:3] Previous failure.",
    )
    test_session.add(exhausted_task)
    await test_session.commit()


    reclaimed = await recovery_service.reclaim_stale_tasks(test_session, max_retries=3)
    await test_session.commit()

    found = next((r for r in reclaimed if r["task_id"] == str(exhausted_task.id)), None)
    assert found is not None
    assert found["action"] == "marked_failed"

    await test_session.refresh(exhausted_task)
    assert exhausted_task.status == TaskState.FAILED.value
    assert "maximum lease recovery" in (exhausted_task.error_details or "").lower()


# ── 2. Orphaned Temporary Upload Cleanup Tests ────────────────────────────────


def test_clean_orphaned_temporary_uploads(tmp_path: Path, monkeypatch):
    test_storage = tmp_path / "test_storage"
    datasets_dir = test_storage / "datasets"
    packages_dir = test_storage / "packages"
    datasets_dir.mkdir(parents=True)
    packages_dir.mkdir(parents=True)

    # 1. Create abandoned temporary file (> 1 hour old)
    old_temp_file = datasets_dir / "tmp_abandoned_upload_123.bin"
    old_temp_file.write_bytes(b"A" * 1024)
    two_hours_ago = time.time() - 7200
    os.utime(old_temp_file, (two_hours_ago, two_hours_ago))

    # 2. Create fresh temporary file (< 5 minutes old)
    fresh_temp_file = datasets_dir / "tmp_active_upload_456.bin"
    fresh_temp_file.write_bytes(b"B" * 512)

    # 3. Create permanent file (should NOT be deleted regardless of age)
    perm_file = datasets_dir / "dataset_final.zip"
    perm_file.write_bytes(b"C" * 2048)
    os.utime(perm_file, (two_hours_ago, two_hours_ago))

    # Point settings to test storage
    monkeypatch.setattr(settings, "storage_root", test_storage)

    cleaned_count, freed_bytes = recovery_service.clean_orphaned_uploads(max_age_seconds=3600)

    assert cleaned_count == 1
    assert freed_bytes == 1024
    assert not old_temp_file.exists()
    assert fresh_temp_file.exists()
    assert perm_file.exists()


# ── 3. Administrative REST API Sweep & Detailed Health Tests ─────────────────


@pytest.mark.asyncio
async def test_system_recovery_sweep_and_health_apis(client: AsyncClient):
    token = await create_user_and_token(client, email="sys_admin@example.com", username="sysadmin")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Trigger recovery sweep
    sweep_res = await client.post("/api/v1/system/recovery/sweep", headers=auth_headers)
    assert sweep_res.status_code == 200
    sweep_data = sweep_res.json()
    assert sweep_data["status"] == "completed"
    assert "report" in sweep_data
    report = sweep_data["report"]
    assert "reclaimed_tasks_count" in report
    assert "cleaned_temp_files_count" in report

    # 2. Query detailed system health
    health_res = await client.get("/api/v1/system/health/detailed")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["status"] == "healthy"
    assert "storage" in health_data
    assert "cluster" in health_data
    assert "total_users" in health_data["cluster"]
    assert "registered_machines" in health_data["cluster"]


# ── 4. Frontend Schema Parity & Contract Matching Tests ───────────────────────


@pytest.mark.asyncio
async def test_frontend_project_schema_parity(client: AsyncClient):
    token = await create_user_and_token(client, email="parity_user@example.com", username="parityuser")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Create project
    create_res = await client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": "Frontend Parity Verification Project",
            "description": "Verifying exact field matching with frontenda/src/types/index.ts",
            "trainingObjective": "Fine-tune diffusion",
            "modelArchitecture": "Diffusion (UNet / DiT 180M)",
            "expectedDuration": "2 hours",
            "workersNeeded": 2,
        },
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    # Query project detail
    detail_res = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert detail_res.status_code == 200
    p = detail_res.json()

    # Invariants: check every key present in frontenda/src/types/index.ts Project interface
    expected_frontend_keys = {
        "id",
        "name",
        "description",
        "trainingObjective",
        "modelArchitecture",
        "datasetName",
        "datasetDescription",
        "datasetSize",
        "codeFileName",
        "codeFileSize",
        "status",
        "visibility",
        "owner",
        "createdAt",
        "expectedDuration",
        "trainingStrategy",
        "workersNeeded",
        "requirements",
        "trainingConfig",
        "workers",
        "metrics",
        "logs",
    }
    for key in expected_frontend_keys:
        assert key in p, f"Missing frontend contract key: '{key}'"

    # Check metrics structure matches TrainingMetrics interface
    metrics = p["metrics"]
    assert "currentStep" in metrics
    assert "totalSteps" in metrics
    assert "progressPercent" in metrics
    assert "currentLoss" in metrics
    assert "trainingSpeed" in metrics
    assert "elapsedTimeSeconds" in metrics
    assert "estimatedRemainingSeconds" in metrics
    assert "history" in metrics

    # Check owner matches { id, name, isCurrentUser }
    owner = p["owner"]
    assert "id" in owner
    assert "name" in owner
    assert "isCurrentUser" in owner
    assert owner["isCurrentUser"] is True


@pytest.mark.asyncio
async def test_websocket_broadcast_parity():
    """Verify WebSocket broadcaster packages events matching frontend types."""
    project_id = uuid.uuid4()

    user_id = uuid.uuid4()
    captured_messages: List[Dict] = []

    class MockWebSocket:
        async def accept(self):
            pass

        async def send_text(self, text: str):
            import json
            captured_messages.append(json.loads(text))

    mock_ws = MockWebSocket()
    await ws_hub.connect_website(mock_ws, user_id=user_id, project_id=project_id)

    # Broadcast event
    await ws_hub.broadcast_project_event(
        project_id=project_id,
        event_type="training.progress",
        payload={
            "step": 50,
            "loss": 0.35,
            "speed": 14.2,
        },
    )

    # Initial was connection_status, second was training.progress
    assert len(captured_messages) >= 2
    msg = captured_messages[1]
    assert msg["event"] == "training.progress"
    assert msg["entity_id"] == str(project_id)
    assert msg["payload"]["step"] == 50
    assert msg["payload"]["loss"] == 0.35

    ws_hub.disconnect_website(mock_ws, user_id=user_id, project_id=project_id)

