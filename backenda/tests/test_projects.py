"""
Automated tests for Projects, Uploads, Package Manifests, 9-Digit Codes, and Worker Joining (Phase 5).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.project_code import (
    format_nine_digit_code,
    generate_nine_digit_code,
    generate_unique_project_code,
    normalize_project_code,
)
from app.core.upload import inspect_and_validate_package, validate_dataset_archive
from app.models.dataset import Dataset, ModelPackage
from app.models.machine import Machine
from app.models.project import Project, ProjectCode, ProjectMembership
from app.models.resource import MachineContributionSettings, ResourceAllocation
from app.models.training import TrainingConfiguration
from app.models.user import User


# Helper: register and get auth bearer token
async def create_user_and_token(
    client: AsyncClient,
    email: str = "project_owner@example.com",
    username: str = "projowner",
) -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "display_name": "Project Owner",
            "password": "Password123!",
        },
    )
    assert res.status_code == 201
    return res.json()["access_token"]


# Helper: create a valid in-memory zip archive with train.py and manifest.json
def create_valid_model_package_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "train.py",
            "# ADC Real Training Script\nprint('Initializing Latent Diffusion Training...')\n",
        )
        manifest = {
            "name": "Latent Diffusion Model",
            "version": "1.0.0",
            "entrypoint": "train.py",
            "framework": "PyTorch",
            "parameters": {"batch_size": 128, "lr": 0.0002},
        }
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("requirements.txt", "torch>=2.0.0\npsutil>=5.9.0\n")
    return buf.getvalue()


# Helper: create in-memory dataset zip archive
def create_valid_dataset_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps({"num_samples": 1000, "classes": 10}))
        zf.writestr("data_001.bin", b"\x00" * 1024)
    return buf.getvalue()


# ── 1. Nine-Digit Code Generation Tests ────────────────────────────────────────

def test_nine_digit_code_helpers():
    """Verify 9-digit code generation, formatting, and normalization."""
    raw = generate_nine_digit_code()
    assert len(raw) == 9
    assert raw.isdigit()

    formatted = format_nine_digit_code(raw)
    assert len(formatted) == 11
    assert formatted[3] == "-" and formatted[7] == "-"

    # Test normalization of various user inputs
    assert normalize_project_code(raw) == formatted
    assert normalize_project_code(formatted) == formatted
    assert normalize_project_code(f"  {raw}  ") == formatted


@pytest.mark.asyncio
async def test_generate_unique_project_code_db(
    client: AsyncClient,
    test_session: AsyncSession,
):
    """Verify unique project code database persistence."""
    token = await create_user_and_token(client, "code_tester@example.com", "codetester")

    # Create dummy project
    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Code Test Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    p_id = p_res.json()["id"]

    code_record = await generate_unique_project_code(test_session, p_id)
    assert code_record is not None
    assert len(code_record.code) == 11
    assert code_record.is_active is True


# ── 2. Project Creation & CRUD Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_project_with_config(client: AsyncClient):
    """Verify creating a project with training config and requirements."""
    token = await create_user_and_token(client, "creator@example.com", "creator")

    payload = {
        "name": "Latent Diffusion Model from Scratch",
        "description": "Distributed 180M parameter latent diffusion model.",
        "trainingObjective": "Evaluate classifier-free guidance on synthetic manifolds.",
        "modelArchitecture": "Diffusion (UNet / DiT 180M)",
        "visibility": "public",
        "workersNeeded": 4,
        "trainingStrategy": "independent_jobs",
        "trainingConfig": {
            "batchSize": 64,
            "totalSteps": 5000,
            "learningRate": "1e-4",
            "optimizer": "AdamW",
            "precision": "fp16",
            "checkpointInterval": 250,
            "gradientAccumulationSteps": 2,
        },
        "requirements": {
            "minCpuCores": 4,
            "minRamGB": 8,
            "gpuRecommended": True,
            "minVramGB": 6,
        },
    }

    res = await client.post(
        "/api/v1/projects",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == payload["name"]
    assert data["trainingObjective"] == payload["trainingObjective"]
    assert data["status"] == "online"
    assert data["workersNeeded"] == 4
    assert data["owner"]["isCurrentUser"] is True
    assert data["trainingConfig"]["batchSize"] == 64
    assert data["requirements"]["minCpuCores"] == 4
    assert data["requirements"]["minRamGB"] == 8


@pytest.mark.asyncio
async def test_list_and_filter_projects(client: AsyncClient):
    """Verify listing public projects and filtering by ownership."""
    token1 = await create_user_and_token(client, "user1@example.com", "userone")
    token2 = await create_user_and_token(client, "user2@example.com", "usertwo")

    # User 1 creates 2 projects (1 public, 1 unlisted)
    await client.post(
        "/api/v1/projects",
        json={"name": "Public Project One", "visibility": "public"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    await client.post(
        "/api/v1/projects",
        json={"name": "Private Project One", "visibility": "unlisted"},
        headers={"Authorization": f"Bearer {token1}"},
    )

    # Public list for anonymous user
    res_anon = await client.get("/api/v1/projects")
    assert res_anon.status_code == 200
    anon_projs = res_anon.json()["projects"]
    assert all(p["visibility"] == "public" for p in anon_projs)

    # User 1 queries my_projects
    res_my = await client.get(
        "/api/v1/projects?my_projects=true",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res_my.status_code == 200
    my_projs = res_my.json()["projects"]
    assert len(my_projs) == 2


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    """Verify updating project description and strategy parameters."""
    token = await create_user_and_token(client, "updater@example.com", "updater")

    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Initial Name", "description": "Initial desc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    p_id = p_res.json()["id"]

    patch_res = await client.patch(
        f"/api/v1/projects/{p_id}",
        json={"name": "Updated Name", "workersNeeded": 8},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Updated Name"
    assert patch_res.json()["workersNeeded"] == 8


# ── 3. Dataset & Package Uploads Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_and_download_dataset(client: AsyncClient):
    """Verify streaming upload of dataset with SHA-256 hash and download stream."""
    token = await create_user_and_token(client, "data_uploader@example.com", "datauploader")

    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Dataset Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    p_id = p_res.json()["id"]

    ds_bytes = create_valid_dataset_bytes()
    files = {"file": ("tiny_imagenet.zip", ds_bytes, "application/zip")}
    data = {"name": "TinyImageNet", "description": "Small synthetic test dataset"}

    upload_res = await client.post(
        f"/api/v1/projects/{p_id}/datasets",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 201
    ds_data = upload_res.json()
    assert ds_data["name"] == "TinyImageNet"
    assert ds_data["isValidated"] is True
    assert len(ds_data["checksumSha256"]) == 64
    assert ds_data["sizeBytes"] == len(ds_bytes)
    ds_id = ds_data["id"]

    # Verify download
    down_res = await client.get(
        f"/api/v1/projects/{p_id}/datasets/{ds_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert down_res.status_code == 200
    assert down_res.content == ds_bytes


@pytest.mark.asyncio
async def test_upload_and_inspect_model_package(client: AsyncClient):
    """Verify uploading model training code package, inspecting train.py and manifest."""
    token = await create_user_and_token(client, "pkg_uploader@example.com", "pkguploader")

    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Package Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    p_id = p_res.json()["id"]

    pkg_bytes = create_valid_model_package_bytes()
    files = {"file": ("diffusion_trainer.zip", pkg_bytes, "application/zip")}

    upload_res = await client.post(
        f"/api/v1/projects/{p_id}/packages",
        files=files,
        data={"entrypoint": "train.py"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 201
    pkg_data = upload_res.json()
    assert pkg_data["fileName"] == "diffusion_trainer.zip"
    assert pkg_data["entrypoint"] == "train.py"
    assert pkg_data["isValidated"] is True
    assert pkg_data["manifest"] is not None
    assert pkg_data["manifest"]["framework"] == "PyTorch"
    pkg_id = pkg_data["id"]

    # Download package
    down_res = await client.get(
        f"/api/v1/projects/{p_id}/packages/{pkg_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert down_res.status_code == 200
    assert down_res.content == pkg_bytes


@pytest.mark.asyncio
async def test_model_package_path_traversal_rejection(client: AsyncClient):
    """Verify malicious archive with ZipSlip path traversal is rejected."""
    token = await create_user_and_token(client, "sec_tester@example.com", "sectester")

    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Security Test Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    p_id = p_res.json()["id"]

    # Create zip with path traversal
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:::")
        zf.writestr("train.py", "print('hello')")
    bad_bytes = buf.getvalue()

    upload_res = await client.post(
        f"/api/v1/projects/{p_id}/packages",
        files={"file": ("malicious.zip", bad_bytes, "application/zip")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 201
    pkg_data = upload_res.json()
    assert pkg_data["isValidated"] is False
    assert "malicious" in pkg_data["validationError"].lower() or "traversal" in pkg_data["validationError"].lower()


# ── 4. Put Project Online Workflow ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_put_project_online_workflow(client: AsyncClient):
    """Verify Put Project Online validates assets and returns active 9-digit code."""
    token = await create_user_and_token(client, "online_tester@example.com", "onlinetester")

    # 1. Create project
    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Workflow Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    p_id = p_res.json()["id"]

    # Attempt to put online without assets -> must fail
    fail_res = await client.post(
        f"/api/v1/projects/{p_id}/online",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fail_res.status_code == 422
    assert "dataset" in fail_res.json()["error"]["message"].lower()

    # 2. Upload dataset
    await client.post(
        f"/api/v1/projects/{p_id}/datasets",
        files={"file": ("ds.zip", create_valid_dataset_bytes(), "application/zip")},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Attempt again without package -> must fail
    fail2_res = await client.post(
        f"/api/v1/projects/{p_id}/online",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fail2_res.status_code == 422
    assert "training code" in fail2_res.json()["error"]["message"].lower() or "package" in fail2_res.json()["error"]["message"].lower()

    # 3. Upload model package
    await client.post(
        f"/api/v1/projects/{p_id}/packages",
        files={"file": ("pkg.zip", create_valid_model_package_bytes(), "application/zip")},
        headers={"Authorization": f"Bearer {token}"},
    )

    # 4. Put online successfully
    online_res = await client.post(
        f"/api/v1/projects/{p_id}/online",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert online_res.status_code == 200
    data = online_res.json()
    assert data["status"] == "online"
    code = data["projectCode"]
    assert len(code) == 11
    assert code[3] == "-" and code[7] == "-"
    assert data["project"]["status"] == "looking_for_workers"
    assert data["project"]["activeCode"] == code


# ── 5. Worker Joining Workflow & Membership Tests ─────────────────────────────

@pytest.mark.asyncio
async def test_worker_join_by_code_and_membership(client: AsyncClient):
    """Verify worker node joins project using 9-digit code, updates resources, and leaves."""
    # 1. Setup project owner and put project online
    owner_token = await create_user_and_token(client, "owner_node@example.com", "ownernode")
    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Joinable Cluster Project", "requirements": {"minCpuCores": 2, "minRamGB": 4}},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    p_id = p_res.json()["id"]

    await client.post(
        f"/api/v1/projects/{p_id}/datasets",
        files={"file": ("ds.zip", create_valid_dataset_bytes(), "application/zip")},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    await client.post(
        f"/api/v1/projects/{p_id}/packages",
        files={"file": ("pkg.zip", create_valid_model_package_bytes(), "application/zip")},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    online_res = await client.post(
        f"/api/v1/projects/{p_id}/online",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    code = online_res.json()["projectCode"]

    # 2. Setup Worker user and paired machine
    worker_token = await create_user_and_token(client, "worker_vol@example.com", "workervol")
    from app.core.machine_crypto import generate_installation_id, generate_machine_keypair, sign_message
    import time

    priv, pub_hex = generate_machine_keypair()
    inst_id = generate_installation_id()
    await client.post(
        "/api/v1/machines/register",
        json={"installation_id": inst_id, "name": "worker-cluster-01", "public_key": pub_hex},
    )
    ts = int(time.time())
    sig = sign_message(priv, f"{inst_id}:{ts}".encode("utf-8"))
    chal = await client.post(
        "/api/v1/machines/pairing/challenge",
        json={"installation_id": inst_id, "timestamp": ts, "signature": sig},
    )
    await client.post(
        "/api/v1/machines/pairing/complete",
        json={"challenge_code": chal.json()["challengeCode"], "selected_role": "worker"},
        headers={"Authorization": f"Bearer {worker_token}"},
    )

    # 3. Worker joins project using code
    join_res = await client.post(
        "/api/v1/projects/join-by-code",
        json={"code": code, "cpuCores": 4, "ramGB": 8.0, "storageGB": 30.0},
        headers={
            "Authorization": f"Bearer {worker_token}",
            "X-Installation-Id": inst_id,
        },
    )
    assert join_res.status_code == 200
    mem_data = join_res.json()
    assert mem_data["cpuCoresContributed"] == 4
    assert mem_data["ramContributedGB"] == 8.0
    assert mem_data["status"] == "idle"

    # 4. Check project workers endpoint
    workers_res = await client.get(
        f"/api/v1/projects/{p_id}/workers",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert workers_res.status_code == 200
    workers = workers_res.json()
    assert len(workers) == 1
    assert workers[0]["name"] == "worker-cluster-01"
    assert workers[0]["cpuCoresContributed"] == 4
    assert workers[0]["isCurrentUser"] is True

    # 5. Worker updates membership resource allocation
    patch_mem = await client.patch(
        f"/api/v1/projects/{p_id}/membership/resources",
        json={"cpuCores": 6, "ramGB": 12.0},
        headers={
            "Authorization": f"Bearer {worker_token}",
            "X-Installation-Id": inst_id,
        },
    )
    assert patch_mem.status_code == 200
    assert patch_mem.json()["cpuCoresContributed"] == 6
    assert patch_mem.json()["ramContributedGB"] == 12.0

    # 6. Worker leaves project
    leave_res = await client.post(
        f"/api/v1/projects/{p_id}/leave",
        headers={
            "Authorization": f"Bearer {worker_token}",
            "X-Installation-Id": inst_id,
        },
    )
    assert leave_res.status_code == 200

    # Verify workers list is now empty
    workers_after = await client.get(f"/api/v1/projects/{p_id}/workers")
    assert len(workers_after.json()) == 0


# ── 6. Project Lifecycle Transitions ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_project_lifecycle_transitions(client: AsyncClient):
    """Verify project pause, resume, stop, and complete lifecycle."""
    token = await create_user_and_token(client, "lifecycle@example.com", "lifecycle")

    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "Lifecycle Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    p_id = p_res.json()["id"]

    # 1. Pause
    p_pause = await client.post(
        f"/api/v1/projects/{p_id}/pause",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert p_pause.status_code == 200
    assert p_pause.json()["status"] == "paused"

    # 2. Resume
    p_resume = await client.post(
        f"/api/v1/projects/{p_id}/resume",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert p_resume.status_code == 200
    assert p_resume.json()["status"] == "online"

    # 3. Stop
    p_stop = await client.post(
        f"/api/v1/projects/{p_id}/stop",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert p_stop.status_code == 200
    assert p_stop.json()["status"] == "stopped"

    # 4. End / Complete
    p_end = await client.post(
        f"/api/v1/projects/{p_id}/end",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert p_end.status_code == 200
    assert p_end.json()["status"] == "completed"
