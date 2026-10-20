"""
Automated tests for Distributed Training Strategies, Rank Management, Relay Aggregator,
Pipeline Model Parallelism, and REST APIs (Phase 9).
"""

from __future__ import annotations

import asyncio
import io
import json
import uuid
from pathlib import Path
from typing import Dict, List

import pytest
import torch
import torch.nn as nn
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.models.project import Project, ProjectMembership
from app.models.training import TrainingConfiguration, TrainingRun
from app.models.user import User
from app.training.diffusion import DiffusionUNet
from app.training.strategies.data_parallel import DataParallelStrategy
from app.training.strategies.independent_jobs import IndependentJobsStrategy
from app.training.strategies.model_parallel import (
    DiffusionStage0,
    DiffusionStage1,
    ModelParallelStrategy,
)
from app.training.strategies.registry import StrategyRegistry, strategy_registry
from app.training.strategies.relay import RelayParameterAggregator, relay_aggregator
from app.training.strategies.single_node import SingleNodeStrategy


# Helper: register user and obtain bearer token
async def create_user_and_token(
    client: AsyncClient,
    email: str = "dist_dev@example.com",
    username: str = "distdev",
) -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "display_name": "Distributed Developer",
            "password": "Password123!",
        },
    )
    assert res.status_code == 201
    return res.json()["access_token"]


# Helper: generate PyTorch tensor dictionary
def create_model_state_dict(seed: int = 42) -> Dict[str, torch.Tensor]:
    torch.manual_seed(seed)
    model = nn.Linear(4, 2)
    return {k: v.clone() for k, v in model.state_dict().items()}


# ── 1. Strategy Interface & Compatibility Tests ──────────────────────────────


def test_strategy_registry_and_network_requirements():
    reg = StrategyRegistry()
    strategies = reg.list_all()
    assert len(strategies) >= 4

    names = {s.name for s in strategies}
    assert "single_node" in names
    assert "independent_jobs" in names
    assert "data_parallel" in names
    assert "model_parallel" in names

    # Inspect network requirements
    dp_strat = reg.get("data_parallel")
    req = dp_strat.get_network_requirements()
    assert req.strategy_name == "data_parallel"
    assert req.supports_nat is True  # Relay backend supports NAT
    assert req.inbound_ports_required is False
    assert req.min_bandwidth_mbps > 0.0


def test_data_parallel_rejects_single_worker():
    strat = DataParallelStrategy()
    proj = Project(
        id=uuid.uuid4(),
        name="DP Project",
        model_architecture="diffusion",
        min_cpu_cores=1,
        min_ram_gb=2.0,
    )
    cfg = TrainingConfiguration(
        project_id=proj.id,
        batch_size=16,
        learning_rate=0.001,
        total_steps=100,
    )

    # Incompatible with 1 worker
    valid, err = strat.validate_project_compatibility(proj, cfg, num_eligible_workers=1)
    assert valid is False
    assert "at least 2" in err

    # Compatible with 2 workers
    valid2, err2 = strat.validate_project_compatibility(proj, cfg, num_eligible_workers=2)
    assert valid2 is True
    assert err2 is None

    # Incompatible if batch size < world size
    cfg_small = TrainingConfiguration(project_id=proj.id, batch_size=2)
    valid3, err3 = strat.validate_project_compatibility(proj, cfg_small, num_eligible_workers=4)
    assert valid3 is False
    assert "cannot be smaller than cluster size" in err3


def test_model_parallel_rejects_unsupported_architecture():
    strat = ModelParallelStrategy()
    unsupported_proj = Project(
        id=uuid.uuid4(),
        name="Custom Model",
        model_architecture="custom_arbitrary_neural_net",
        min_cpu_cores=1,
        min_ram_gb=2.0,
    )

    valid, err = strat.validate_project_compatibility(unsupported_proj, None, num_eligible_workers=2)
    assert valid is False
    assert "not supported for model parallelism" in err

    supported_proj = Project(
        id=uuid.uuid4(),
        name="Diffusion Model",
        model_architecture="diffusion_unet_pipeline",
        min_cpu_cores=1,
        min_ram_gb=2.0,
    )
    valid_sup, _ = strat.validate_project_compatibility(supported_proj, None, num_eligible_workers=2)
    assert valid_sup is True


# ── 2. Real Synchronous Parameter Relay AllReduce Tests ──────────────────────


@pytest.mark.asyncio
async def test_relay_parameter_aggregator_real_tensor_averaging():
    aggregator = RelayParameterAggregator()
    run_id = uuid.uuid4()
    step = 10
    expected_ranks = {0, 1}

    # Rank 0 tensors (W0, b0)
    dict_rank_0 = {
        "weight": torch.tensor([[1.0, 2.0], [3.0, 4.0]], dtype=torch.float32),
        "bias": torch.tensor([0.5, -0.5], dtype=torch.float32),
    }

    # Rank 1 tensors (W1, b1)
    dict_rank_1 = {
        "weight": torch.tensor([[3.0, 4.0], [5.0, 6.0]], dtype=torch.float32),
        "bias": torch.tensor([1.5, 0.5], dtype=torch.float32),
    }

    # Expected average:
    # weight_avg = [[2.0, 3.0], [4.0, 5.0]]
    # bias_avg = [1.0, 0.0]

    async def worker_0_sync():
        return await aggregator.sync_step_tensors(
            run_id=run_id,
            step=step,
            rank=0,
            expected_ranks=expected_ranks,
            tensors=dict_rank_0,
            timeout_seconds=5.0,
        )

    async def worker_1_sync():
        # Add slight asynchronous stagger to simulate network delay
        await asyncio.sleep(0.05)
        return await aggregator.sync_step_tensors(
            run_id=run_id,
            step=step,
            rank=1,
            expected_ranks=expected_ranks,
            tensors=dict_rank_1,
            timeout_seconds=5.0,
        )

    res_0, res_1 = await asyncio.gather(worker_0_sync(), worker_1_sync())

    # Invariant 1: Both ranks receive identical byte payloads
    assert res_0 == res_1

    # Invariant 2: Aggregated tensors match mathematical average
    loaded_0 = torch.load(io.BytesIO(res_0), weights_only=True)
    loaded_1 = torch.load(io.BytesIO(res_1), weights_only=True)

    expected_weight = torch.tensor([[2.0, 3.0], [4.0, 5.0]], dtype=torch.float32)
    expected_bias = torch.tensor([1.0, 0.0], dtype=torch.float32)

    assert torch.allclose(loaded_0["weight"], expected_weight)
    assert torch.allclose(loaded_0["bias"], expected_bias)
    assert torch.allclose(loaded_1["weight"], expected_weight)
    assert torch.allclose(loaded_1["bias"], expected_bias)


@pytest.mark.asyncio
async def test_relay_parameter_aggregator_rejects_nan_inf():
    aggregator = RelayParameterAggregator()
    run_id = uuid.uuid4()
    step = 1

    corrupted_dict = {
        "weight": torch.tensor([[float("nan"), 1.0]], dtype=torch.float32),
    }

    with pytest.raises(ValidationError) as exc:
        await aggregator.sync_step_tensors(
            run_id=run_id,
            step=step,
            rank=0,
            expected_ranks={0},
            tensors=corrupted_dict,
        )
    assert "nan or inf" in str(exc.value).lower()


# ── 3. Pipeline Model Parallelism Tests ──────────────────────────────────────


def test_pipeline_diffusion_stages_forward_and_backward():
    """
    Verify partitioned stages (Stage 0 and Stage 1) produce valid forward noise predictions
    and accept backpropagation through activation gradients.
    """
    stage0 = DiffusionStage0(in_channels=1, base_channels=16, time_dim=32)
    stage1 = DiffusionStage1(out_channels=1, base_channels=16, time_dim=32)

    # Input batch
    x = torch.randn(2, 1, 16, 16)
    t = torch.tensor([5, 25], dtype=torch.long)

    # 1. Forward Stage 0 on Rank 0
    h_bot, skip1, skip2, t_emb = stage0(x, t)
    assert h_bot.shape == (2, 32, 4, 4)
    assert skip1.shape == (2, 16, 16, 16)
    assert skip2.shape == (2, 32, 8, 8)
    assert t_emb.shape == (2, 32)

    # Enable gradient tracking on intermediate activation boundary
    h_bot = h_bot.detach().requires_grad_(True)
    skip1 = skip1.detach().requires_grad_(True)
    skip2 = skip2.detach().requires_grad_(True)

    # 2. Forward Stage 1 on Rank 1
    predicted_noise = stage1(h_bot, skip1, skip2, t_emb)
    assert predicted_noise.shape == (2, 1, 16, 16)

    # 3. Compute loss and backpropagate through Stage 1
    target_noise = torch.randn_like(predicted_noise)
    loss = ((predicted_noise - target_noise) ** 2).mean()
    loss.backward()

    # Verify Stage 1 has computed parameter gradients
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in stage1.parameters())

    # Verify activation gradients were computed for boundary tensors
    assert h_bot.grad is not None
    assert skip1.grad is not None
    assert skip2.grad is not None

    # 4. Backpropagate activation gradients through Stage 0 on Rank 0
    # Re-evaluate Stage 0 with active autograd
    h_bot_0, skip1_0, skip2_0, _ = stage0(x, t)
    torch.autograd.backward(
        tensors=[h_bot_0, skip1_0, skip2_0],
        grad_tensors=[h_bot.grad, skip1.grad, skip2.grad],
    )

    # Verify Stage 0 has computed parameter gradients
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in stage0.parameters())


# ── 4. Rank Failure & Checkpoint Rollback Handling ───────────────────────────


def test_data_parallel_worker_failure_triggers_checkpoint_rollback():
    strat = DataParallelStrategy()
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()

    w0 = ProjectMembership(project_id=project_id, user_id=uuid.uuid4(), machine_id=uuid.uuid4(), status="active")
    w1 = ProjectMembership(project_id=project_id, user_id=uuid.uuid4(), machine_id=uuid.uuid4(), status="active")
    w2 = ProjectMembership(project_id=project_id, user_id=uuid.uuid4(), machine_id=uuid.uuid4(), status="active")

    # Plan 3-worker rendezvous
    rendezvous = strat.plan_rendezvous(
        project_id=project_id,
        run_id=run_id,
        workers=[w0, w1, w2],
    )
    assert rendezvous.world_size == 3
    assert len(rendezvous.ranks) == 3

    # Worker 2 drops
    can_continue, msg, rollback_step = strat.handle_worker_failure(
        failed_worker_id=w2.user_id,
        rendezvous=rendezvous,
    )
    assert can_continue is True
    assert rollback_step == -1  # Indicates rollback to latest validated checkpoint
    assert "Rank 2 dropped" in msg

    # Worker 1 drops leaving only 1 surviving worker
    can_continue2, msg2, rollback_step2 = strat.handle_worker_failure(
        failed_worker_id=w1.user_id,
        rendezvous=rendezvous,
    )
    assert can_continue2 is False
    assert "Insufficient surviving workers" in msg2


# ── 5. Distributed REST API Lifecycle Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_distributed_rest_api_lifecycle(client: AsyncClient):
    token = await create_user_and_token(client, email="dist_api_user@example.com", username="distapiuser")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create project
    proj_res = await client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": "Distributed Diffusion Project",
            "model_architecture": "diffusion",
            "min_cpu_cores": 1,
            "min_ram_gb": 2.0,
            "total_steps": 200,
            "batch_size": 16,
            "training_strategy": "single_node",
        },
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. List available strategies
    strat_res = await client.get(
        f"/api/v1/projects/{project_id}/distributed/strategies",
        headers=auth_headers,
    )
    assert strat_res.status_code == 200
    strat_data = strat_res.json()
    assert strat_data["total"] >= 4
    strategy_names = [s["name"] for s in strat_data["strategies"]]
    assert "single_node" in strategy_names
    assert "data_parallel" in strategy_names

    # 3. Coordinate Rendezvous
    rendezvous_res = await client.post(
        f"/api/v1/projects/{project_id}/distributed/rendezvous",
        headers=auth_headers,
        json={},
    )
    assert rendezvous_res.status_code == 200
    r_data = rendezvous_res.json()
    assert r_data["projectId"] == project_id
    assert r_data["rank"] == 0
    assert "relaySyncUrl" in r_data
    run_id = r_data["runId"]

    # 4. Report Distributed Heartbeat
    hb_res = await client.post(
        f"/api/v1/projects/{project_id}/distributed/heartbeat",
        headers=auth_headers,
        json={"runId": run_id, "rank": 0, "currentStep": 5},
    )
    assert hb_res.status_code == 200
    assert hb_res.json()["status"] == "ok"

    # 5. Get Distributed Status
    status_res = await client.get(
        f"/api/v1/projects/{project_id}/distributed/status?run_id={run_id}",
        headers=auth_headers,
    )
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["runId"] == run_id
    assert s_data["worldSize"] >= 1

    # 6. Synchronize weights via relay endpoint
    test_weights = {"param": torch.tensor([1.0, 2.0, 3.0])}
    buf = io.BytesIO()
    torch.save(test_weights, buf)

    sync_res = await client.post(
        f"/api/v1/projects/{project_id}/distributed/sync",
        headers=auth_headers,
        data={"run_id": run_id, "step": "1", "rank": "0"},
        files={"file": ("weights_0.pt", buf.getvalue(), "application/octet-stream")},
    )
    assert sync_res.status_code == 200
    returned_weights = torch.load(io.BytesIO(sync_res.content), weights_only=True)
    assert "param" in returned_weights
    assert torch.allclose(returned_weights["param"], torch.tensor([1.0, 2.0, 3.0]))


def test_adc_distributed_client_single_node_noop():
    from agents.executor.distributed_adapter import ADCDistributedClient

    client = ADCDistributedClient(strategy="single_node", world_size=1)
    assert client.is_distributed is False
    model = nn.Linear(4, 2)
    # Verifies sync_model safely no-ops without requiring relay or network
    client.sync_model(step=1, model=model)

