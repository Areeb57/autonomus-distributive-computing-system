"""
Automated tests for Hardware Detection, Telemetry, Resource Guard, and Resource API (Phase 4).
"""

from __future__ import annotations

import os
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.common.guard import ResourceGuard
from agents.common.hardware import HardwareDetector, detect_gpus
from app.core.machine_crypto import generate_installation_id, generate_machine_keypair
from app.models.machine import Machine
from app.models.resource import MachineContributionSettings, WorkerResourceSnapshot
from app.models.user import User


# ── 1. Unit Tests for HardwareDetector ──────────────────────────────────────────

def test_hardware_detector_cpu_info():
    """Verify CPU introspection returns valid physical and logical core counts."""
    cpu = HardwareDetector.get_cpu_info()
    assert isinstance(cpu["model"], str)
    assert len(cpu["model"]) > 0
    assert cpu["cores_logical"] >= 1
    assert cpu["cores_physical"] >= 1
    assert 0.0 <= cpu["utilization_pct"] <= 100.0


def test_hardware_detector_ram_info():
    """Verify RAM introspection returns realistic non-zero capacities."""
    ram = HardwareDetector.get_ram_info()
    assert ram["total_gb"] > 0.0
    assert ram["available_gb"] > 0.0
    assert ram["used_gb"] >= 0.0
    assert 0.0 <= ram["utilization_pct"] <= 100.0


def test_hardware_detector_disk_info():
    """Verify storage introspection returns positive disk capacities."""
    disk = HardwareDetector.get_disk_info(".")
    assert disk["total_gb"] > 0.0
    assert disk["free_gb"] > 0.0
    assert 0.0 <= disk["utilization_pct"] <= 100.0


def test_hardware_detector_gpu_detection():
    """Verify GPU detection executes gracefully without crashing on CPU-only machines."""
    gpus = detect_gpus()
    assert "has_gpu" in gpus
    assert isinstance(gpus["has_gpu"], bool)
    assert isinstance(gpus["primary_model"], str)
    assert gpus["total_vram_gb"] >= 0.0
    assert isinstance(gpus["devices"], list)


def test_hardware_profile_shape():
    """Verify get_hardware_profile conforms to frontend TypeScript HardwareProfile."""
    profile = HardwareDetector.get_hardware_profile()
    expected_keys = {
        "cpuModel",
        "cpuCores",
        "ramTotalGB",
        "ramAvailableGB",
        "gpuModel",
        "gpuMemoryTotalGB",
        "diskSpaceAvailableGB",
    }
    assert expected_keys.issubset(set(profile.keys()))
    assert profile["cpuCores"] >= 1
    assert profile["ramTotalGB"] > 0.0


def test_telemetry_snapshot_shape():
    """Verify telemetry snapshot matches WorkerResourceSnapshot schema."""
    snap = HardwareDetector.get_telemetry_snapshot()
    expected_fields = {
        "cpu_model",
        "cpu_cores",
        "cpu_utilization",
        "ram_total_gb",
        "ram_available_gb",
        "ram_usage_pct",
        "gpu_model",
        "gpu_memory_total_gb",
        "gpu_memory_used_gb",
        "gpu_utilization_pct",
        "disk_available_gb",
    }
    assert expected_fields.issubset(set(snap.keys()))
    assert snap["cpu_cores"] >= 1


# ── 2. Unit Tests for ResourceGuard ───────────────────────────────────────────

def test_resource_guard_normal_safety():
    """Verify ResourceGuard reports safe under normal operating conditions."""
    guard = ResourceGuard(
        cpu_cores_budget=2,
        ram_budget_gb=4.0,
        min_host_free_ram_gb=0.1,  # Safe low threshold
        min_host_free_disk_gb=0.1,
        global_paused=False,
    )
    is_safe, reason = guard.check_safety()
    assert is_safe is True
    assert reason is None


def test_resource_guard_global_pause_enforcement():
    """Verify ResourceGuard immediately blocks when global pause is active."""
    guard = ResourceGuard(global_paused=True)
    is_safe, reason = guard.check_safety()
    assert is_safe is False
    assert "paused" in str(reason).lower()


def test_resource_guard_memory_pressure_threshold():
    """Verify ResourceGuard trips if host free memory falls below required safety threshold."""
    # Setting safety threshold to 100,000 GB guarantees trip on any standard machine
    guard = ResourceGuard(min_host_free_ram_gb=100000.0)
    is_safe, reason = guard.check_safety()
    assert is_safe is False
    assert "host memory pressure" in str(reason).lower()


def test_resource_guard_disk_pressure_threshold():
    """Verify ResourceGuard trips if host free disk falls below required threshold."""
    guard = ResourceGuard(
        min_host_free_ram_gb=0.01,
        min_host_free_disk_gb=10000000.0,
    )
    is_safe, reason = guard.check_safety()
    assert is_safe is False
    assert "disk space" in str(reason).lower()


def test_resource_guard_process_resource_budget():
    """Verify child process memory monitoring detects budget violation."""
    my_pid = os.getpid()
    # Setting RAM budget to an impossibly low 0.000001 GB (~1KB) must detect violation
    guard = ResourceGuard(ram_budget_gb=0.000001)
    is_ok, reason = guard.check_process_resource_usage(my_pid)
    assert is_ok is False
    assert "exceeded allocated ram budget" in str(reason).lower()

    # Setting RAM budget to generous 1000 GB should pass
    generous_guard = ResourceGuard(ram_budget_gb=1000.0)
    is_ok2, reason2 = generous_guard.check_process_resource_usage(my_pid)
    assert is_ok2 is True
    assert reason2 is None


def test_resource_guard_update_settings():
    """Verify ResourceGuard properly updates limits from dictionary."""
    guard = ResourceGuard()
    guard.update_settings({
        "cpuCores": 6,
        "ramBudgetGB": 16.0,
        "storageBudgetGB": 80.0,
        "gpuEnabled": True,
        "selectedGpu": "RTX 4090",
        "globalPaused": True,
    })
    assert guard.cpu_cores_budget == 6
    assert guard.ram_budget_gb == 16.0
    assert guard.storage_budget_gb == 80.0
    assert guard.gpu_enabled is True
    assert guard.selected_gpu == "RTX 4090"
    assert guard.global_paused is True


# ── 3. REST API Integration Tests (/api/v1/resources/*) ───────────────────────

@pytest.mark.asyncio
async def test_resources_me_unauthorized(client: AsyncClient):
    """Verify /api/v1/resources/me rejects requests without authentication."""
    res = await client.get("/api/v1/resources/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_resources_me_get_default(client: AsyncClient):
    """Verify authenticated user can query hardware profile and contribution settings."""
    # 1. Register & login user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "resource_tester@example.com",
            "username": "resourcetester",
            "display_name": "Resource Tester",
            "password": "Password123!",
        },
    )
    assert reg_res.status_code == 201
    token = reg_res.json()["access_token"]

    # 2. Query resources
    res = await client.get(
        "/api/v1/resources/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()

    assert "hardwareProfile" in data
    assert "contributionSettings" in data
    assert "availableGpus" in data
    assert "clusterSummary" in data

    hw = data["hardwareProfile"]
    assert hw["cpuCores"] >= 1
    assert hw["ramTotalGB"] > 0

    settings = data["contributionSettings"]
    assert settings["cpuEnabled"] is True
    assert settings["globalPaused"] is False


@pytest.mark.asyncio
async def test_resources_me_patch_valid(client: AsyncClient):
    """Verify modifying contribution budgets via PATCH /api/v1/resources/me."""
    # Register & login
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "patch_tester@example.com",
            "username": "patchtester",
            "display_name": "Patch Tester",
            "password": "Password123!",
        },
    )
    token = reg_res.json()["access_token"]

    # Update settings
    patch_payload = {
        "cpuEnabled": True,
        "cpuCores": 2,
        "ramBudgetGB": 4.0,
        "storageBudgetGB": 35.0,
        "networkPreference": "saver",
    }
    patch_res = await client.patch(
        "/api/v1/resources/me",
        json=patch_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["cpuCores"] == 2
    assert data["ramBudgetGB"] == 4.0
    assert data["storageBudgetGB"] == 35.0
    assert data["networkPreference"] == "saver"


@pytest.mark.asyncio
async def test_resources_me_patch_physical_limit_validation(client: AsyncClient):
    """Verify allocating more cores than physically present is rejected with 422."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "limit_tester@example.com",
            "username": "limittester",
            "display_name": "Limit Tester",
            "password": "Password123!",
        },
    )
    token = reg_res.json()["access_token"]

    # Request absurd core count
    patch_res = await client.patch(
        "/api/v1/resources/me",
        json={"cpuCores": 500},  # Exceeds host cores
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 422
    err_msg = patch_res.json()["error"]["message"].lower()
    assert "exceeds" in err_msg or "cores" in err_msg or "logical" in err_msg


@pytest.mark.asyncio
async def test_resources_me_pause_and_resume_all(client: AsyncClient):
    """Verify global pause and resume toggle endpoints."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "pause_tester@example.com",
            "username": "pausetester",
            "display_name": "Pause Tester",
            "password": "Password123!",
        },
    )
    token = reg_res.json()["access_token"]

    # 1. Trigger Pause All
    pause_res = await client.post(
        "/api/v1/resources/me/pause-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["globalPaused"] is True

    # 2. Trigger Resume All
    resume_res = await client.post(
        "/api/v1/resources/me/resume-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["globalPaused"] is False


@pytest.mark.asyncio
async def test_resources_paired_machine_integration(
    client: AsyncClient,
    test_session: AsyncSession,
):
    """Verify paired machine settings persistence and telemetry snapshot reflection."""
    # 1. Register user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "paired_worker@example.com",
            "username": "pairedworker",
            "display_name": "Paired Worker User",
            "password": "Password123!",
        },
    )
    token = reg_res.json()["access_token"]

    # 2. Register machine & create pairing challenge
    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()
    await client.post(
        "/api/v1/machines/register",
        json={"installation_id": inst_id, "name": "telemetry-worker", "public_key": pub_hex},
    )

    import time
    from app.core.machine_crypto import sign_message
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))
    chal_res = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": sig},
    )
    code = chal_res.json()["challengeCode"]

    # 3. Complete pairing as worker
    pair_res = await client.post(
        "/api/v1/machines/pairing/complete",
        json={"challenge_code": code, "selected_role": "worker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pair_res.status_code == 200
    lease_token = pair_res.json()["leaseToken"]

    # 4. Agent sends heartbeat with telemetry snapshot
    telemetry = HardwareDetector.get_telemetry_snapshot()
    hb_res = await client.post(
        "/api/v1/machines/heartbeat",
        json={
            "installation_id": inst_id,
            "lease_token": lease_token,
            "status": "idle",
            "metrics": telemetry,
        },
    )
    assert hb_res.status_code == 200

    # 5. User queries resources: should link to machine and reflect telemetry
    res = await client.get(
        "/api/v1/resources/me",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Installation-Id": inst_id,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["hardwareProfile"]["cpuCores"] == telemetry["cpu_cores"]
    assert data["hardwareProfile"]["cpuModel"] == telemetry["cpu_model"]

    # 6. User modifies contribution settings for this machine
    patch_res = await client.patch(
        "/api/v1/resources/me",
        json={"cpuCores": 3, "ramBudgetGB": 6.0},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Installation-Id": inst_id,
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["cpuCores"] == 3
    assert patch_res.json()["ramBudgetGB"] == 6.0

    # 7. Check database settings record
    stmt = select(MachineContributionSettings).where(
        MachineContributionSettings.user_id == User.id  # query join or by machine_id
    )
    machine_stmt = select(Machine).where(Machine.installation_id == inst_id)
    m = (await test_session.execute(machine_stmt)).scalar_one()
    settings_stmt = select(MachineContributionSettings).where(
        MachineContributionSettings.machine_id == m.id
    )
    saved_settings = (await test_session.execute(settings_stmt)).scalar_one_or_none()
    assert saved_settings is not None
    assert saved_settings.cpu_cores == 3
    assert saved_settings.ram_budget_gb == 6.0
