"""
Model-Parallel Training Strategy and Pipeline Partitioning (Phase 9).
Provides pipeline parallelism for explicitly supported neural architectures (e.g. DiffusionUNet).
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn

from app.models.project import Project, ProjectMembership
from app.models.training import TrainingConfiguration
from app.training.diffusion import (
    DiffusionUNet,
    ResidualBlock,
    SinusoidalPositionalEmbedding,
)
from app.training.strategies.base import (
    BaseTrainingStrategy,
    NetworkTopologyRequirement,
    RankAssignment,
    RendezvousState,
)

# Explicit list of supported model partition architectures
SUPPORTED_PIPELINE_ARCHITECTURES = {
    "diffusion_unet_pipeline",
    "pipeline_diffusion",
    "diffusion",
    "stable-diffusion-v1-5-partitioned",
}


class DiffusionStage0(nn.Module):
    """
    Stage 0 of Partitioned Diffusion U-Net (Encoder & Timestep Embedding).
    Executed on Rank 0 node.
    """

    def __init__(
        self,
        in_channels: int = 1,
        base_channels: int = 32,
        time_dim: int = 64,
    ) -> None:
        super().__init__()
        self.time_embed = nn.Sequential(
            SinusoidalPositionalEmbedding(time_dim),
            nn.Linear(time_dim, time_dim),
            nn.SiLU(),
            nn.Linear(time_dim, time_dim),
        )
        self.down1 = ResidualBlock(in_channels, base_channels, time_dim)
        self.pool1 = nn.Conv2d(base_channels, base_channels, kernel_size=3, stride=2, padding=1)
        self.down2 = ResidualBlock(base_channels, base_channels * 2, time_dim)
        self.pool2 = nn.Conv2d(base_channels * 2, base_channels * 2, kernel_size=3, stride=2, padding=1)

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            (h_bottleneck_input, skip_1, skip_2, time_emb)
        """
        t_emb = self.time_embed(t)
        h1 = self.down1(x, t_emb)
        p1 = self.pool1(h1)
        h2 = self.down2(p1, t_emb)
        h_bottleneck_in = self.pool2(h2)
        return h_bottleneck_in, h1, h2, t_emb


class DiffusionStage1(nn.Module):
    """
    Stage 1 of Partitioned Diffusion U-Net (Bottleneck & Decoder).
    Executed on Rank 1 node.
    """

    def __init__(
        self,
        out_channels: int = 1,
        base_channels: int = 32,
        time_dim: int = 64,
    ) -> None:
        super().__init__()
        # Bottleneck
        self.bot = ResidualBlock(base_channels * 2, base_channels * 2, time_dim)

        # Upsampling path
        self.up2 = nn.ConvTranspose2d(base_channels * 2, base_channels * 2, kernel_size=4, stride=2, padding=1)
        self.dec2 = ResidualBlock(base_channels * 4, base_channels, time_dim)

        self.up1 = nn.ConvTranspose2d(base_channels, base_channels, kernel_size=4, stride=2, padding=1)
        self.dec1 = ResidualBlock(base_channels * 2, base_channels, time_dim)

        self.out_conv = nn.Sequential(
            nn.GroupNorm(num_groups=8, num_channels=base_channels),
            nn.SiLU(),
            nn.Conv2d(base_channels, out_channels, kernel_size=3, padding=1),
        )

    def forward(
        self,
        h_bottleneck_in: torch.Tensor,
        skip_1: torch.Tensor,
        skip_2: torch.Tensor,
        t_emb: torch.Tensor,
    ) -> torch.Tensor:
        """Takes intermediate activations from Stage 0 and computes final noise prediction."""
        bot = self.bot(h_bottleneck_in, t_emb)

        u2 = self.up2(bot)
        cat2 = torch.cat([u2, skip_2], dim=1)
        d2 = self.dec2(cat2, t_emb)

        u1 = self.up1(d2)
        cat1 = torch.cat([u1, skip_1], dim=1)
        d1 = self.dec1(cat1, t_emb)

        return self.out_conv(d1)


class ModelParallelStrategy(BaseTrainingStrategy):
    """
    Model-Parallel / Pipeline Training Strategy.

    Divides model layers across multiple nodes. Activations flow sequentially from
    Stage 0 (Rank 0) to Stage 1 (Rank 1), and activation gradients flow in reverse.

    RESTRICTION:
    Only explicitly supported architectures that define valid stage partitions
    can execute this strategy. Arbitrary Python training packages without partition
    interfaces are rejected before execution.
    """

    @property
    def name(self) -> str:
        return "model_parallel"

    @property
    def description(self) -> str:
        return (
            "Pipeline parallelism for large models. The neural network layers are partitioned "
            "across nodes with sequential activation and gradient tensor passing."
        )

    def get_network_requirements(self) -> NetworkTopologyRequirement:
        return NetworkTopologyRequirement(
            strategy_name=self.name,
            requires_direct_inter_worker_tcp=False,
            inbound_ports_required=False,
            supports_nat=True,
            min_bandwidth_mbps=25.0,
            estimated_sync_latency_ms=40.0,
            firewall_description=(
                "Pipeline activation and gradient handoffs flow through the ADC Coordinator Relay. "
                "No open inbound ports required on worker nodes."
            ),
            supported_backends=["pipeline_relay"],
        )

    def validate_project_compatibility(
        self,
        project: Project,
        config: Optional[TrainingConfiguration],
        num_eligible_workers: int,
    ) -> Tuple[bool, Optional[str]]:
        # 1. Pipeline partitioning requires at least 2 workers (1 per stage)
        if num_eligible_workers < 2:
            return (
                False,
                f"Model-parallel pipeline execution requires at least 2 workers (found {num_eligible_workers}).",
            )

        # 2. Check architecture support
        arch = (project.model_architecture or "").lower().strip()
        if arch not in SUPPORTED_PIPELINE_ARCHITECTURES and not any(k in arch for k in ["diffusion", "pipeline"]):
            return (
                False,
                f"Model architecture '{project.model_architecture}' is not supported for model parallelism. "
                f"Supported architectures: {sorted(list(SUPPORTED_PIPELINE_ARCHITECTURES))}.",
            )

        return True, None

    def plan_rendezvous(
        self,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        workers: List[ProjectMembership],
        master_addr: str = "127.0.0.1",
        master_port: int = 29500,
    ) -> RendezvousState:
        # Assign stage 0 and stage 1
        ranks: dict[int, RankAssignment] = {}
        for idx in range(min(2, len(workers))):
            w = workers[idx]
            role = f"stage_{idx}"
            ranks[idx] = RankAssignment(
                rank=idx,
                world_size=2,
                worker_id=w.user_id,
                machine_id=w.machine_id,
                role=role,
            )

        return RendezvousState(
            project_id=project_id,
            run_id=run_id,
            strategy=self.name,
            backend="pipeline_relay",
            master_addr=master_addr,
            master_port=master_port,
            world_size=2,
            ranks=ranks,
            is_ready=len(ranks) >= 2,
        )

    def handle_worker_failure(
        self,
        failed_worker_id: uuid.UUID,
        rendezvous: RendezvousState,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        In pipeline parallelism, both stages are strictly required.
        Failure of either stage halts pipeline and requires stage replacement.
        """
        for r_id, assignment in rendezvous.ranks.items():
            if assignment.worker_id == failed_worker_id:
                assignment.is_healthy = False
                return (
                    False,
                    f"Pipeline node for {assignment.role} (Rank {r_id}) disconnected. "
                    "Pipeline training halted until replacement worker joins.",
                    -1,
                )
        return False, f"Worker {failed_worker_id} not found in active pipeline ranks.", None
