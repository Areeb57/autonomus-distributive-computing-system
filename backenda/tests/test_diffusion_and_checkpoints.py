"""
Automated tests for Real Diffusion Models, Checkpoint Storage, Integrity, Resumption, and REST APIs (Phase 8).
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pytest
import torch
import torch.nn as nn
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.executor.adapter import ADCReporter, TrainingTelemetry
from agents.executor.base import TaskExecutionConfig
from agents.executor.subprocess_executor import SubprocessTrainingExecutor
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.project import Project
from app.models.training import Checkpoint, TrainingConfiguration, TrainingRun
from app.models.user import User
from app.services.checkpoint import checkpoint_service
from app.training.diffusion import (
    DiffusionUNet,
    GaussianDiffusion,
    load_checkpoint_dict,
    save_checkpoint_dict,
)


# Helper: register user and obtain token
async def create_user_and_token(
    client: AsyncClient,
    email: str = "diffusion_dev@example.com",
    username: str = "diffdev",
) -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "display_name": "Diffusion Developer",
            "password": "Password123!",
        },
    )
    assert res.status_code == 201
    return res.json()["access_token"]


# Helper: create valid in-memory checkpoint binary bytes
def create_mock_pytorch_checkpoint_bytes(step: int = 50, loss: float = 0.35) -> bytes:
    model = nn.Linear(4, 2)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    payload = save_checkpoint_dict(model, optimizer, step=step, loss=loss)
    buf = io.BytesIO()
    torch.save(payload, buf)
    return buf.getvalue()


# ── 1. Diffusion Model & Mathematics Unit Tests ──────────────────────────────


def test_diffusion_unet_forward_pass():
    model = DiffusionUNet(in_channels=1, out_channels=1, base_channels=16, time_dim=32)
    x = torch.randn(2, 1, 16, 16)
    t = torch.tensor([10, 50], dtype=torch.long)
    out = model(x, t)

    assert out.shape == (2, 1, 16, 16)
    assert not torch.isnan(out).any()


def test_gaussian_diffusion_noise_schedule_and_loss():
    diffusion = GaussianDiffusion(timesteps=100, beta_start=0.001, beta_end=0.02)
    x_0 = torch.randn(4, 1, 16, 16)

    # 1. Forward sampling q_sample
    t = torch.tensor([5, 20, 50, 80], dtype=torch.long)
    noisy_x, noise = diffusion.q_sample(x_0, t)
    assert noisy_x.shape == x_0.shape
    assert noise.shape == x_0.shape

    # 2. Real loss computation and backpropagation
    model = DiffusionUNet(in_channels=1, out_channels=1, base_channels=16, time_dim=32)
    loss = diffusion.compute_loss(model, x_0, t)

    assert loss.item() > 0.0
    loss.backward()

    # Verify gradients computed across parameters
    has_grads = any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.parameters())
    assert has_grads is True


def test_diffusion_checkpoint_serialization(tmp_path: Path):
    model1 = nn.Linear(8, 4)
    opt1 = torch.optim.Adam(model1.parameters(), lr=0.005)
    ckpt_path = tmp_path / "diff_ckpt.pt"

    # Save
    payload = save_checkpoint_dict(model1, opt1, step=120, loss=0.145, extra={"val_loss": 0.160})
    torch.save(payload, ckpt_path)

    # Load into fresh model
    model2 = nn.Linear(8, 4)
    opt2 = torch.optim.Adam(model2.parameters(), lr=0.005)
    resumed_step = load_checkpoint_dict(ckpt_path, model2, opt2)

    assert resumed_step == 120
    # Parameter weights must match exactly
    for p1, p2 in zip(model1.parameters(), model2.parameters()):
        assert torch.allclose(p1, p2)


# ── 2. Checkpoint Service & Integrity Validation Tests ───────────────────────


@pytest.mark.asyncio
async def test_checkpoint_service_atomic_publish_and_validation(
    test_session: AsyncSession,
):
    user = User(
        email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
        username=f"owner_{uuid.uuid4().hex[:6]}",
        display_name="Test Owner",
        hashed_password="mock_hash",
    )
    test_session.add(user)
    await test_session.flush()

    project_id = uuid.uuid4()
    # Create test project and run
    proj = Project(
        id=project_id,
        owner_id=user.id,
        name="Test Checkpoint Proj",
        model_architecture="diffusion",
        min_cpu_cores=1,
        min_ram_gb=1.0,
    )
    run = TrainingRun(
        project_id=project_id,
        run_number=1,
        status="running",
        current_step=0,
        total_steps=500,
    )
    test_session.add(proj)
    test_session.add(run)
    await test_session.commit()

    # Stream valid checkpoint
    ckpt_bytes = create_mock_pytorch_checkpoint_bytes(step=100, loss=0.22)

    async def mock_stream():
        yield ckpt_bytes[: len(ckpt_bytes) // 2]
        yield ckpt_bytes[len(ckpt_bytes) // 2 :]

    checkpoint = await checkpoint_service.save_and_validate_checkpoint(
        db=test_session,
        project_id=project_id,
        run_id=run.id,
        step=100,
        file_stream=mock_stream(),
        filename="model_100.pt",
        metrics_dict={"loss": 0.22, "speed": 15.0},
    )
    await test_session.commit()

    assert checkpoint.step == 100
    assert checkpoint.is_validated is True
    assert checkpoint.file_size_bytes == len(ckpt_bytes)
    assert Path(checkpoint.file_path).is_file()

    # Query latest checkpoint
    latest = await checkpoint_service.get_latest_checkpoint(test_session, project_id)
    assert latest is not None
    assert latest.id == checkpoint.id
    assert latest.step == 100

    # Resume from checkpoint
    p_id, resumed_step, c_id = await checkpoint_service.resume_from_checkpoint(
        test_session,
        project_id=project_id,
        checkpoint_id=checkpoint.id,
    )
    assert resumed_step == 100


@pytest.mark.asyncio
async def test_checkpoint_service_rejects_corrupted_file(
    test_session: AsyncSession,
):
    user = User(
        email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
        username=f"owner_{uuid.uuid4().hex[:6]}",
        display_name="Test Owner",
        hashed_password="mock_hash",
    )
    test_session.add(user)
    await test_session.flush()

    project_id = uuid.uuid4()
    proj = Project(
        id=project_id,
        owner_id=user.id,
        name="Test Corrupt Checkpoint",
        model_architecture="diffusion",
        min_cpu_cores=1,
        min_ram_gb=1.0,
    )
    run = TrainingRun(project_id=project_id, run_number=1, status="running", current_step=0, total_steps=500)
    test_session.add(proj)
    test_session.add(run)
    await test_session.commit()

    corrupt_bytes = b"NOT_A_VALID_PYTORCH_FILE_HEADER_XYZ123"

    async def mock_corrupt_stream():
        yield corrupt_bytes

    with pytest.raises(ValidationError) as exc:
        await checkpoint_service.save_and_validate_checkpoint(
            db=test_session,
            project_id=project_id,
            run_id=run.id,
            step=50,
            file_stream=mock_corrupt_stream(),
            filename="corrupt.pt",
        )
    assert "integrity" in str(exc.value).lower()


# ── 3. Checkpoint REST API Endpoints Tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_checkpoint_rest_api_lifecycle(client: AsyncClient):
    token = await create_user_and_token(client, email="checkpoint_tester@example.com", username="ckpttester")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create project
    proj_res = await client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": "Diffusion LoRA Checkpoints",
            "model_architecture": "stable-diffusion-v1-5",
            "min_cpu_cores": 2,
            "min_ram_gb": 4.0,
            "total_steps": 300,
            "batch_size": 16,
        },
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Upload checkpoint
    ckpt_bytes = create_mock_pytorch_checkpoint_bytes(step=50, loss=0.45)
    upload_res = await client.post(
        f"/api/v1/projects/{project_id}/checkpoints",
        headers=auth_headers,
        data={"step": "50", "metrics_json": json.dumps({"loss": 0.45, "lr": 0.001})},
        files={"file": ("ckpt_50.pt", ckpt_bytes, "application/octet-stream")},
    )
    assert upload_res.status_code == 201
    ckpt_data = upload_res.json()
    ckpt_id = ckpt_data["id"]
    assert ckpt_data["step"] == 50
    assert ckpt_data["isValidated"] is True
    assert ckpt_data["fileSizeBytes"] == len(ckpt_bytes)

    # 3. List checkpoints
    list_res = await client.get(f"/api/v1/projects/{project_id}/checkpoints", headers=auth_headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert list_res.json()["checkpoints"][0]["id"] == ckpt_id

    # 4. Get latest checkpoint
    latest_res = await client.get(f"/api/v1/projects/{project_id}/checkpoints/latest", headers=auth_headers)
    assert latest_res.status_code == 200
    assert latest_res.json()["id"] == ckpt_id
    assert latest_res.json()["step"] == 50

    # 5. Download checkpoint file stream
    dl_res = await client.get(f"/api/v1/projects/{project_id}/checkpoints/{ckpt_id}/download", headers=auth_headers)
    assert dl_res.status_code == 200
    assert len(dl_res.content) == len(ckpt_bytes)

    # Verify downloaded content is valid PyTorch weights
    loaded_data = torch.load(io.BytesIO(dl_res.content), weights_only=True)
    assert loaded_data["step"] == 50
    assert loaded_data["loss"] == 0.45

    # 6. Resume project from checkpoint
    resume_res = await client.post(
        f"/api/v1/projects/{project_id}/checkpoints/{ckpt_id}/resume",
        headers=auth_headers,
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["resumedStep"] == 50
    assert resume_res.json()["status"] == "resumed"


# ── 4. Real PyTorch Training Resumption in Child Sandbox ─────────────────────


@pytest.mark.asyncio
async def test_training_executor_resumes_from_checkpoint(tmp_path: Path):
    """
    1. Run training job from step 0 to step 5, saving a checkpoint.
    2. Run second training job with resume_checkpoint_path pointing to step 5 checkpoint,
       resuming from step 5 to step 10.
    """
    # Create package that supports resumption via ADC_RESUME_CHECKPOINT
    pkg_zip = tmp_path / "resumable_pkg.zip"
    code = """
import os
import torch
import torch.nn as nn
from agents.executor.adapter import ADCReporter
from app.training.diffusion import save_checkpoint_dict, load_checkpoint_dict

step_start = int(os.environ.get("ADC_STEP_START", "0"))
step_end = int(os.environ.get("ADC_STEP_END", "10"))
ckpt_dir = os.environ.get("ADC_CHECKPOINT_DIR", ".")
resume_ckpt = os.environ.get("ADC_RESUME_CHECKPOINT")

reporter = ADCReporter()

model = nn.Linear(4, 2)
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

# Check if resuming
if resume_ckpt and os.path.isfile(resume_ckpt):
    loaded_step = load_checkpoint_dict(resume_ckpt, model, optimizer)
    print(f"Successfully resumed from checkpoint at step {loaded_step}!")

for step in range(step_start, step_end):
    x = torch.randn(4, 4)
    loss = (model(x) ** 2).mean()
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    
    reporter.report_step(step=step + 1, loss=float(loss.item()))

# Save new checkpoint
final_ckpt = os.path.join(ckpt_dir, f"model_step_{step_end}.pt")
payload = save_checkpoint_dict(model, optimizer, step=step_end, loss=float(loss.item()))
torch.save(payload, final_ckpt)
reporter.report_checkpoint(final_ckpt, step=step_end)
print("Finished!")
"""
    manifest = {
        "name": "resumable_trainer",
        "version": "1.0.0",
        "entrypoint": "train.py",
        "dependencies": ["torch", "numpy"],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("train.py", code)
        zf.writestr("manifest.json", json.dumps(manifest))
    pkg_zip.write_bytes(buf.getvalue())

    ds_zip = tmp_path / "ds.zip"
    buf_ds = io.BytesIO()
    with zipfile.ZipFile(buf_ds, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.txt", "1,2,3,4\n")
    ds_zip.write_bytes(buf_ds.getvalue())

    executor = SubprocessTrainingExecutor(sandbox_base_dir=tmp_path / "ws1")

    # Phase 1: Train steps 0..5
    config1 = TaskExecutionConfig(
        task_id="run_part_1",
        project_id="proj_resumption",
        package_path=pkg_zip,
        dataset_path=ds_zip,
        step_start=0,
        step_end=5,
    )
    res1 = await executor.execute(config1)
    assert res1.success is True
    assert res1.steps_completed == 5
    assert len(res1.checkpoints) >= 1
    step_5_ckpt = res1.checkpoints[0]

    # Phase 2: Resume from step 5 checkpoint, train steps 5..10
    executor2 = SubprocessTrainingExecutor(sandbox_base_dir=tmp_path / "ws2")
    config2 = TaskExecutionConfig(
        task_id="run_part_2",
        project_id="proj_resumption",
        package_path=pkg_zip,
        dataset_path=ds_zip,
        step_start=5,
        step_end=10,
        resume_checkpoint_path=Path(step_5_ckpt),
    )
    res2 = await executor2.execute(config2)
    assert res2.success is True
    assert res2.steps_completed == 10
    assert len(res2.checkpoints) >= 1
    assert any("model_step_10.pt" in c for c in res2.checkpoints)
