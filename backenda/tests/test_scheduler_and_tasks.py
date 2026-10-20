"""
Automated tests for Scheduler, State Machines, Training Tasks, Leases, and WebSockets (Phase 6).
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.api.dependencies import get_db_session
from app.core.exceptions import ConflictError
from app.core.project_code import generate_unique_project_code
from app.core.state_machine import (
    ProjectState,
    TaskState,
    WorkerState,
    assert_project_transition,
    assert_task_transition,
    assert_worker_transition,
    can_transition_project,
    can_transition_task,
    can_transition_worker,
)
from app.core.websocket import WSEvent, WebSocketHub, ws_hub
from app.main import create_app
from app.models.dataset import Dataset, ModelPackage
from app.models.machine import Machine
from app.models.project import Project, ProjectMembership
from app.models.resource import MachineContributionSettings
from app.models.training import TrainingConfiguration, TrainingRun, TrainingTask
from app.services.scheduler import StrategySelector, WorkerEligibilityEvaluator, scheduler


# Helper: register user and obtain token
async def create_user_and_token(
    client: AsyncClient,
    email: str = "scheduler_user@example.com",
    username: str = "scheduser",
) -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "display_name": "Scheduler Test User",
            "password": "Password123!",
        },
    )
    assert res.status_code == 201
    return res.json()["access_token"]


# Helper: create zip package
def create_test_package_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("train.py", "print('hello from training!')\n")
        manifest = {
            "entrypoint": "train.py",
            "dependencies": ["torch", "diffusers"],
            "version": "1.0.0",
        }
        zf.writestr("manifest.json", json.dumps(manifest))
    return buf.getvalue()


# Helper: create valid dataset zip archive
def create_test_dataset_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.csv", "sample,label\n1,0\n2,1\n")
    return buf.getvalue()


# ── 1. State Machine Unit Tests ──────────────────────────────────────────────


def test_state_machines_project_transitions():
    # Legal project transitions
    assert can_transition_project(ProjectState.DRAFT.value, ProjectState.ONLINE.value)
    assert can_transition_project(ProjectState.ONLINE.value, ProjectState.RUNNING.value)
    assert can_transition_project(ProjectState.RUNNING.value, ProjectState.PAUSED.value)
    assert can_transition_project(ProjectState.PAUSED.value, ProjectState.RUNNING.value)
    assert can_transition_project(ProjectState.RUNNING.value, ProjectState.COMPLETED.value)
    assert_project_transition(ProjectState.DRAFT.value, ProjectState.ONLINE.value)

    # Illegal project transitions
    assert not can_transition_project(ProjectState.DRAFT.value, ProjectState.COMPLETED.value)
    assert not can_transition_project(ProjectState.COMPLETED.value, ProjectState.RUNNING.value)
    with pytest.raises(ConflictError):
        assert_project_transition(ProjectState.DRAFT.value, ProjectState.COMPLETED.value)


def test_state_machines_worker_transitions():
    # Legal worker transitions
    assert can_transition_worker(WorkerState.OFFLINE.value, WorkerState.ONLINE.value)
    assert can_transition_worker(WorkerState.ONLINE.value, WorkerState.IDLE.value)
    assert can_transition_worker(WorkerState.IDLE.value, WorkerState.ASSIGNED.value)
    assert can_transition_worker(WorkerState.ASSIGNED.value, WorkerState.RUNNING.value)
    assert can_transition_worker(WorkerState.RUNNING.value, WorkerState.IDLE.value)
    assert_worker_transition(WorkerState.IDLE.value, WorkerState.ASSIGNED.value)

    # Illegal worker transitions
    assert not can_transition_worker(WorkerState.OFFLINE.value, WorkerState.RUNNING.value)
    with pytest.raises(ConflictError):
        assert_worker_transition(WorkerState.OFFLINE.value, WorkerState.RUNNING.value)


def test_state_machines_task_transitions():
    # Legal task transitions
    assert can_transition_task(TaskState.PENDING.value, TaskState.ASSIGNED.value)
    assert can_transition_task(TaskState.ASSIGNED.value, TaskState.IN_PROGRESS.value)
    assert can_transition_task(TaskState.IN_PROGRESS.value, TaskState.COMPLETED.value)
    assert_task_transition(TaskState.PENDING.value, TaskState.ASSIGNED.value)

    # Recovery / retry transitions
    assert can_transition_task(TaskState.ASSIGNED.value, TaskState.TIMEOUT.value)
    assert can_transition_task(TaskState.TIMEOUT.value, TaskState.PENDING.value)
    assert can_transition_task(TaskState.IN_PROGRESS.value, TaskState.FAILED.value)
    assert can_transition_task(TaskState.FAILED.value, TaskState.PENDING.value)

    # Illegal task transitions
    assert not can_transition_task(TaskState.COMPLETED.value, TaskState.IN_PROGRESS.value)
    with pytest.raises(ConflictError):
        assert_task_transition(TaskState.COMPLETED.value, TaskState.IN_PROGRESS.value)


# ── 2. Strategy Selector Tests ───────────────────────────────────────────────


def test_deterministic_strategy_selector():
    project = MagicMock(spec=Project)
    project.training_strategy = "auto"
    project.model_architecture = "resnet50"

    # Single worker -> single_node
    assert StrategySelector.select_strategy(project, num_eligible_workers=1, total_cluster_vram_gb=16.0) == "single_node"

    # Data parallel explicit requested
    project.training_strategy = "data_parallel"
    assert StrategySelector.select_strategy(project, num_eligible_workers=4, total_cluster_vram_gb=32.0) == "data_parallel"

    # Massive model (70B) with high aggregate VRAM -> model_parallel
    project.training_strategy = "auto"
    project.model_architecture = "llama-3-70b-instruct"
    assert StrategySelector.select_strategy(project, num_eligible_workers=3, total_cluster_vram_gb=64.0) == "model_parallel"

    # Multiple workers, moderate model -> independent_jobs
    project.model_architecture = "stable-diffusion-v1-5"
    assert StrategySelector.select_strategy(project, num_eligible_workers=3, total_cluster_vram_gb=24.0) == "independent_jobs"


# ── 3. Worker Eligibility Evaluator Tests ────────────────────────────────────


def test_worker_eligibility_evaluator():
    machine = MagicMock(spec=Machine)
    machine.active_role = "worker"
    machine.is_online = True
    machine.status = "idle"

    membership = MagicMock(spec=ProjectMembership)
    membership.contribution_status = "active"
    membership.status = "idle"
    membership.cpu_cores_contributed = 8
    membership.ram_contributed_gb = 16.0
    membership.gpu_enabled = True

    settings = MagicMock(spec=MachineContributionSettings)
    settings.global_paused = False

    project = MagicMock(spec=Project)
    project.min_cpu_cores = 4
    project.min_ram_gb = 8.0
    project.gpu_recommended = False
    project.min_vram_gb = 0.0

    # 1. Fully eligible
    ok, reason = WorkerEligibilityEvaluator.evaluate_worker(machine, membership, settings, project)
    assert ok is True
    assert reason is None

    # 2. Ineligible: Wrong active role
    machine.active_role = "master"
    ok, reason = WorkerEligibilityEvaluator.evaluate_worker(machine, membership, settings, project)
    assert ok is False
    assert "role" in reason.lower()
    machine.active_role = "worker"

    # 3. Ineligible: Global pause enabled
    settings.global_paused = True
    ok, reason = WorkerEligibilityEvaluator.evaluate_worker(machine, membership, settings, project)
    assert ok is False
    assert "global contribution pause" in reason.lower()
    settings.global_paused = False

    # 4. Ineligible: Membership paused
    membership.status = "paused"
    ok, reason = WorkerEligibilityEvaluator.evaluate_worker(machine, membership, settings, project)
    assert ok is False
    assert "paused" in reason.lower()
    membership.status = "idle"

    # 5. Ineligible: Contributed RAM below project minimum
    project.min_ram_gb = 32.0
    ok, reason = WorkerEligibilityEvaluator.evaluate_worker(machine, membership, settings, project)
    assert ok is False
    assert "ram" in reason.lower()


# ── 4. End-to-End Task Coordination & Leases Tests ───────────────────────────


@pytest.mark.asyncio
async def test_agent_tasks_e2e_coordination_lifecycle(
    client: AsyncClient,
    test_session: AsyncSession,
):
    """
    Full workflow:
    1. Register user & worker machine.
    2. Create project, upload artifacts, put project online.
    3. Worker joins project with 9-digit code.
    4. Worker polls for tasks -> scheduler auto-dispatches step 0..50.
    5. Worker acknowledges task with lease token -> in_progress.
    6. Worker reports metric telemetry.
    7. Worker marks task completed.
    """
    token = await create_user_and_token(client, email="coordinator@example.com", username="coorduser")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Register worker machine with real Ed25519 identity
    from app.core.machine_crypto import generate_installation_id, generate_machine_keypair, sign_message
    import time

    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()
    reg_res = await client.post(
        "/api/v1/machines/register",
        json={
            "installation_id": inst_id,
            "name": "Compute Worker 1",
            "public_key": pub_hex,
            "platform": "Linux",
        },
    )
    assert reg_res.status_code == 201

    # Request pairing challenge
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))
    ch_res = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={
            "installation_id": inst_id,
            "timestamp": ts,
            "signature": sig,
        },
    )
    assert ch_res.status_code == 200
    code = ch_res.json()["challengeCode"]

    # Pair machine as worker
    pair_res = await client.post(
        "/api/v1/machines/pairing/complete",
        headers=auth_headers,
        json={"challenge_code": code, "selected_role": "worker"},
    )
    assert pair_res.status_code == 200
    worker_machine_id = pair_res.json()["machine"]["id"]

    # 2. Create project
    proj_res = await client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": "Distributed Diffusion Model",
            "model_architecture": "stable-diffusion-v1-5",
            "min_cpu_cores": 2,
            "min_ram_gb": 4.0,
            "total_steps": 200,
            "batch_size": 16,
        },
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # Upload dataset
    ds_bytes = create_test_dataset_bytes()
    ds_res = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        headers=auth_headers,
        files={"file": ("dataset.zip", ds_bytes, "application/zip")},
    )
    assert ds_res.status_code == 201

    # Upload package
    pkg_bytes = create_test_package_bytes()
    pkg_res = await client.post(
        f"/api/v1/projects/{project_id}/packages",
        headers=auth_headers,
        files={"file": ("training_pkg.zip", pkg_bytes, "application/zip")},
    )
    assert pkg_res.status_code == 201

    # Put project online
    online_res = await client.post(
        f"/api/v1/projects/{project_id}/online",
        headers=auth_headers,
    )
    assert online_res.status_code == 200
    project_code = online_res.json()["projectCode"]

    # 3. Worker joins project using code
    agent_headers = {
        "Authorization": f"Bearer {token}",
        "X-Installation-Id": inst_id,
    }
    join_res = await client.post(
        "/api/v1/projects/join-by-code",
        headers=agent_headers,
        json={
            "code": project_code,
            "cpuCores": 4,
            "ramGB": 8.0,
            "storageGB": 30.0,
            "gpuEnabled": True,
        },
    )
    assert join_res.status_code == 200

    # 4. Worker polls for tasks (triggers scheduler dispatch)
    poll_res = await client.get(
        "/api/v1/agent/tasks",
        headers=agent_headers,
        params={"project_id": project_id},
    )
    assert poll_res.status_code == 200
    tasks = poll_res.json()
    assert len(tasks) == 1
    task = tasks[0]
    task_id = task["id"]
    lease_token = task["leaseToken"]

    assert task["status"] == "assigned"
    assert task["stepStart"] == 0
    assert task["stepEnd"] == 50
    assert lease_token is not None
    assert f"/api/v1/projects/{project_id}/datasets" in task["datasetDownloadUrl"]
    assert f"/api/v1/projects/{project_id}/packages" in task["packageDownloadUrl"]

    # 5. Worker acknowledges task
    # First test invalid lease token
    bad_ack = await client.post(
        f"/api/v1/agent/tasks/{task_id}/acknowledge",
        headers=agent_headers,
        json={"leaseToken": "invalid_token"},
    )
    assert bad_ack.status_code == 409

    # Valid lease token
    ack_res = await client.post(
        f"/api/v1/agent/tasks/{task_id}/acknowledge",
        headers=agent_headers,
        json={"leaseToken": lease_token},
    )
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["status"] == "in_progress"

    # 6. Worker reports metric telemetry
    metric_res = await client.post(
        f"/api/v1/agent/tasks/{task_id}/metrics",
        headers=agent_headers,
        json={
            "step": 25,
            "loss": 0.425,
            "speed": 18.2,
            "clusterCpuUtil": 45.0,
            "clusterGpuUtil": 88.0,
            "ramUtilGB": 4.2,
        },
    )
    assert metric_res.status_code == 200
    assert metric_res.json()["recorded"] is True
    assert metric_res.json()["step"] == 25
    assert metric_res.json()["loss"] == 0.425

    # Verify project progress endpoint reflects real reported telemetry
    prog_res = await client.get(f"/api/v1/projects/{project_id}/progress", headers=auth_headers)
    assert prog_res.status_code == 200
    prog_data = prog_res.json()
    assert prog_data["currentStep"] == 25
    assert prog_data["currentLoss"] == 0.425
    assert prog_data["trainingSpeed"] == 18.2

    # 7. Worker completes task
    status_res = await client.post(
        f"/api/v1/agent/tasks/{task_id}/status",
        headers=agent_headers,
        json={
            "status": "completed",
            "resultSummary": "Steps 0 through 50 finished successfully.",
        },
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "completed"

    # Worker polls again -> receives next slice (step 50..100)
    poll_res2 = await client.get(
        "/api/v1/agent/tasks",
        headers=agent_headers,
        params={"project_id": project_id},
    )
    assert poll_res2.status_code == 200
    tasks2 = poll_res2.json()
    assert len(tasks2) == 1
    task2 = tasks2[0]
    assert task2["stepStart"] == 50
    assert task2["stepEnd"] == 100


# ── 5. Lease Timeout & Failure Recovery Manager ──────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_reclaims_expired_leases(
    test_session: AsyncSession,
):
    """Verify that tasks with expired leases are recovered back to pending queue."""
    # Create test run and an assigned task with expired lease
    project_id = uuid.uuid4()
    run = TrainingRun(
        project_id=project_id,
        run_number=1,
        status="running",
        current_step=0,
        total_steps=500,
    )
    test_session.add(run)
    await test_session.flush()

    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    task = TrainingTask(
        run_id=run.id,
        project_id=project_id,
        task_type="batch",
        step_start=0,
        step_end=50,
        status=TaskState.ASSIGNED.value,
        assigned_machine_id=uuid.uuid4(),
        lease_token="expired_token_123",
        lease_expires_at=past_time,
    )
    test_session.add(task)
    await test_session.commit()

    # Run lease recovery
    reclaimed = await scheduler.reclaim_expired_leases(test_session)
    assert reclaimed == 1
    await test_session.commit()

    # Task should now be pending with cleared assigned machine and lease
    stmt = select(TrainingTask).where(TrainingTask.id == task.id)
    recovered = (await test_session.execute(stmt)).scalar_one()
    assert recovered.status == TaskState.PENDING.value
    assert recovered.assigned_machine_id is None
    assert recovered.lease_token is None
    assert recovered.lease_expires_at is None


# ── 6. WebSocket Hub Unit & Integration Tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_websocket_hub_broadcasting():
    hub = WebSocketHub()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    # Connect client
    await hub.connect_website(mock_ws, user_id=user_id, project_id=project_id)
    assert mock_ws.accept.called
    assert mock_ws.send_text.called

    # Broadcast event
    await hub.broadcast_website_event(
        event="training_progress",
        entity_id=str(project_id),
        payload={"current_step": 100, "loss": 0.25},
        project_id=project_id,
    )
    assert mock_ws.send_text.call_count == 2
    sent_text = mock_ws.send_text.call_args[0][0]
    data = json.loads(sent_text)
    assert data["event"] == "training_progress"
    assert data["payload"]["current_step"] == 100

    # Disconnect client
    hub.disconnect_website(mock_ws, user_id=user_id, project_id=project_id)
    assert user_id not in hub.website_users
    assert project_id not in hub.project_subscribers


def test_websocket_events_endpoint_policy_violation(client: AsyncClient):
    """Test connecting without authentication closes connection with 1008."""
    app = create_app()
    test_client = TestClient(app)

    # Attempt to connect to /ws/events without token or cookie -> WS_1008_POLICY_VIOLATION (4408 / 1008)
    with pytest.raises(Exception):
        with test_client.websocket_connect("/ws/events") as ws:
            pass
