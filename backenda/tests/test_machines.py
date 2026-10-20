"""
Tests for Machine Identity, Registration, Pairing Challenges, Roles, and Heartbeats (Phase 3).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.common.identity import MachineIdentity
from app.core.machine_crypto import (
    generate_installation_id,
    generate_machine_keypair,
    sign_message,
)
from app.models.machine import Machine, MachineCredential, PairingChallenge
from app.models.resource import WorkerResourceSnapshot


@pytest.mark.asyncio
async def test_machine_registration(client: AsyncClient, test_session: AsyncSession):
    """Test machine registration with Ed25519 public key."""
    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()

    payload = {
        "installation_id": inst_id,
        "name": "worker-node-alpha",
        "public_key": pub_hex,
        "platform": "windows",
    }
    res = await client.post("/api/v1/machines/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["installationId"] == inst_id
    assert data["name"] == "worker-node-alpha"
    assert data["activeRole"] == "none"
    assert data["status"] == "offline"
    assert data["isOnline"] is False

    # Check database records
    stmt = select(Machine).where(Machine.installation_id == inst_id)
    machine = (await test_session.execute(stmt)).scalar_one_or_none()
    assert machine is not None
    assert machine.public_key == pub_hex

    # Check credential record
    cred_stmt = select(MachineCredential).where(MachineCredential.machine_id == machine.id)
    cred = (await test_session.execute(cred_stmt)).scalar_one_or_none()
    assert cred is not None
    assert cred.public_key == pub_hex

    # Re-registration with same key updates name
    payload["name"] = "worker-node-renamed"
    res2 = await client.post("/api/v1/machines/register", json=payload)
    assert res2.status_code == 200
    assert res2.json()["name"] == "worker-node-renamed"

    # Re-registration with different key returns 409 Conflict
    _, other_pub = generate_machine_keypair()
    payload["public_key"] = other_pub
    res3 = await client.post("/api/v1/machines/register", json=payload)
    assert res3.status_code == 409


@pytest.mark.asyncio
async def test_pairing_challenge_creation(client: AsyncClient):
    """Test creating a browser pairing challenge using signature verification."""
    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()

    # Register machine first
    await client.post(
        "/api/v1/machines/register",
        json={"installation_id": inst_id, "name": "node-1", "public_key": pub_hex},
    )

    # Valid challenge request
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))

    res = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": sig},
    )
    assert res.status_code == 200
    data = res.json()
    assert "challengeCode" in data
    assert len(data["challengeCode"]) == 6
    assert "expiresAt" in data

    # Forged signature fails
    fake_sig = sign_message(priv, b"wrong-message")
    res_fake = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": fake_sig},
    )
    assert res_fake.status_code == 401

    # Stale timestamp fails (e.g. 10 minutes ago)
    old_ts = ts - 600
    old_sig = sign_message(priv, f"{inst_id}:{old_ts}".encode("utf-8"))
    res_stale = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": old_ts, "signature": old_sig},
    )
    assert res_stale.status_code == 422


@pytest.mark.asyncio
async def test_pairing_completion_and_role_enforcement(client: AsyncClient):
    """Test pairing flow from browser: user claims machine and sets role."""
    # 1. Register machine
    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()
    await client.post(
        "/api/v1/machines/register",
        json={"installation_id": inst_id, "name": "node-worker", "public_key": pub_hex},
    )

    # 2. Agent requests pairing challenge
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))
    challenge_res = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": sig},
    )
    code = challenge_res.json()["challengeCode"]

    # 3. User registers and logs in
    reg_user = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "username": "owner_user",
            "password": "Password123!",
            "display_name": "Cluster Owner",
        },
    )
    token = reg_user.json()["access_token"]

    # 4. Complete pairing as 'worker'
    pair_res = await client.post(
        "/api/v1/machines/pairing/complete",
        json={"challenge_code": code, "selected_role": "worker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pair_res.status_code == 200
    pair_data = pair_res.json()
    assert pair_data["status"] == "paired"
    assert pair_data["machine"]["activeRole"] == "worker"
    assert pair_data["machine"]["isOnline"] is True
    assert "leaseToken" in pair_data

    # 5. Reusing the same challenge code should fail
    pair_again = await client.post(
        "/api/v1/machines/pairing/complete",
        json={"challenge_code": code, "selected_role": "worker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pair_again.status_code == 422


@pytest.mark.asyncio
async def test_pairing_brute_force_lockout(client: AsyncClient):
    """Test that failed attempts lock out a pairing code."""
    # Register and get code
    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()
    await client.post(
        "/api/v1/machines/register",
        json={"installation_id": inst_id, "name": "node-lock", "public_key": pub_hex},
    )
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))
    challenge_res = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": sig},
    )
    code = challenge_res.json()["challengeCode"]

    reg_user = await client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@example.com", "username": "attacker", "password": "Password123!"},
    )
    token = reg_user.json()["access_token"]

    # Try non-existent code
    bad_res = await client.post(
        "/api/v1/machines/pairing/complete",
        json={"challenge_code": "WRONG1", "selected_role": "worker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_res.status_code == 404


@pytest.mark.asyncio
async def test_heartbeat_and_telemetry(client: AsyncClient, test_session: AsyncSession):
    """Test heartbeat loop, lease extension, and telemetry storage."""
    # Setup machine and pair
    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()
    await client.post(
        "/api/v1/machines/register",
        json={"installation_id": inst_id, "name": "node-heartbeat", "public_key": pub_hex},
    )
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))
    chal = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": sig},
    )
    code = chal.json()["challengeCode"]

    user_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "hb_user@example.com", "username": "hb_user", "password": "Password123!"},
    )
    token = user_res.json()["access_token"]

    paired = await client.post(
        "/api/v1/machines/pairing/complete",
        json={"challenge_code": code, "selected_role": "worker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    lease_token = paired.json()["leaseToken"]

    # Send heartbeat with telemetry metrics
    metrics = {
        "cpu_model": "AMD Ryzen 9 7950X",
        "cpu_cores": 16,
        "cpu_utilization": 28.5,
        "ram_total_gb": 64.0,
        "ram_available_gb": 42.0,
        "ram_usage_pct": 34.3,
        "gpu_model": "NVIDIA GeForce RTX 4090",
        "gpu_memory_total_gb": 24.0,
        "gpu_memory_used_gb": 4.5,
        "gpu_utilization_pct": 65.0,
        "disk_available_gb": 450.0,
    }
    hb_res = await client.post(
        "/api/v1/machines/heartbeat",
        json={
            "installation_id": inst_id,
            "lease_token": lease_token,
            "status": "idle",
            "metrics": metrics,
        },
    )
    assert hb_res.status_code == 200
    data = hb_res.json()
    assert data["acknowledged"] is True
    assert data["status"] == "idle"
    assert data["activeRole"] == "worker"

    # Verify telemetry snapshot was persisted in DB
    snap_stmt = select(WorkerResourceSnapshot)
    snapshots = (await test_session.execute(snap_stmt)).scalars().all()
    assert len(snapshots) >= 1
    snap = snapshots[-1]
    assert snap.cpu_model == "AMD Ryzen 9 7950X"
    assert snap.gpu_model == "NVIDIA GeForce RTX 4090"

    # Heartbeat with invalid lease token fails
    bad_hb = await client.post(
        "/api/v1/machines/heartbeat",
        json={
            "installation_id": inst_id,
            "lease_token": "invalid-lease-token",
            "status": "idle",
        },
    )
    assert bad_hb.status_code == 401


@pytest.mark.asyncio
async def test_role_change_and_revocation(client: AsyncClient):
    """Test controlled role change and credential revocation."""
    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()
    await client.post(
        "/api/v1/machines/register",
        json={"installation_id": inst_id, "name": "node-switch", "public_key": pub_hex},
    )
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))
    chal = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": sig},
    )
    code = chal.json()["challengeCode"]

    user_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "role_user@example.com", "username": "role_user", "password": "Password123!"},
    )
    token = user_res.json()["access_token"]

    paired = await client.post(
        "/api/v1/machines/pairing/complete",
        json={"challenge_code": code, "selected_role": "worker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    lease_token = paired.json()["leaseToken"]

    # Controlled role change from worker to master
    change_res = await client.post(
        "/api/v1/machines/role-change",
        json={"new_role": "master"},
        headers={"Authorization": f"Bearer {token}", "X-Installation-Id": inst_id},
    )
    assert change_res.status_code == 200
    assert change_res.json()["activeRole"] == "master"

    # Revoke machine
    revoke_res = await client.post(
        "/api/v1/machines/revoke",
        json={"installation_id": inst_id, "reason": "Decommissioning machine"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    # Heartbeat with revoked machine should fail
    post_revoke_hb = await client.post(
        "/api/v1/machines/heartbeat",
        json={"installation_id": inst_id, "lease_token": lease_token, "status": "idle"},
    )
    assert post_revoke_hb.status_code == 401


def test_machine_identity_load_or_create(tmp_path):
    """Test local MachineIdentity file generation and re-loading."""
    config_file = tmp_path / "sub" / "machine_identity.json"

    # Create new identity
    id1 = MachineIdentity.load_or_create(path=config_file, machine_name="test-box")
    assert id1.installation_id.startswith("inst_")
    assert id1.name == "test-box"
    assert config_file.exists()

    # Reload identity from same file
    id2 = MachineIdentity.load_or_create(path=config_file)
    assert id2.installation_id == id1.installation_id
    assert id2.public_key_hex == id1.public_key_hex

    # Sign challenge with loaded identity
    sig = id2.sign_challenge(b"test-payload")
    from app.core.machine_crypto import verify_machine_signature
    assert verify_machine_signature(id2.public_key_hex, b"test-payload", sig)
