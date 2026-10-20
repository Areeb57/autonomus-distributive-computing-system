"""
Data-Parallel Training Strategy implementation (Phase 9).
Replicas of the model train on distinct dataset partitions with synchronized updates.
Supports both direct collective torch.distributed (Gloo/NCCL) and NAT-friendly Relay AllReduce.
"""

from __future__ import annotations

import uuid
from typing import List, Optional, Tuple

from app.models.project import Project, ProjectMembership
from app.models.training import TrainingConfiguration
from app.training.strategies.base import (
    BaseTrainingStrategy,
    NetworkTopologyRequirement,
    RankAssignment,
    RendezvousState,
)


class DataParallelStrategy(BaseTrainingStrategy):
    """
    Data-Parallel Distributed Training Strategy.

    Replicas of the identical model architecture reside on each worker node.
    Batches are partitioned across workers (mini-batch per worker = global_batch_size / world_size).
    Gradients or parameter updates are synchronized at each training step via:
    1. 'relay': ADC Synchronous AllReduce Relay (outbound HTTPS, NAT-friendly, home compute compatible).
    2. 'torch_ddp': Native PyTorch DistributedDataParallel (direct TCP interconnect, Gloo/NCCL, requires open ports).
    """

    def __init__(self, default_backend: str = "relay", name: Optional[str] = None) -> None:
        self.default_backend = default_backend
        self._name = name or ("data_parallel" if default_backend == "relay" else "data_parallel_ddp")

    @property
    def name(self) -> str:
        return self._name


    @property
    def description(self) -> str:
        return (
            "Synchronized data-parallel training across multiple worker nodes. "
            "Model replicas train on distinct data partitions with synchronous parameter averaging."
        )

    def get_network_requirements(self) -> NetworkTopologyRequirement:
        if self.default_backend == "torch_ddp":
            return NetworkTopologyRequirement(
                strategy_name=self.name,
                requires_direct_inter_worker_tcp=True,
                inbound_ports_required=True,
                supports_nat=False,
                min_bandwidth_mbps=50.0,
                estimated_sync_latency_ms=15.0,
                firewall_description=(
                    "Requires open inbound TCP port 29500 on Rank 0 and unblocked direct worker-to-worker "
                    "interconnects (LAN, VPC, or Tailscale/WireGuard overlay). Incompatible with symmetric NAT."
                ),
                supported_backends=["gloo", "nccl"],
            )

        # Default: relay backend
        return NetworkTopologyRequirement(
            strategy_name=self.name,
            requires_direct_inter_worker_tcp=False,
            inbound_ports_required=False,
            supports_nat=True,
            min_bandwidth_mbps=15.0,
            estimated_sync_latency_ms=80.0,
            firewall_description=(
                "Workers connect outbound to the central ADC Relay Aggregator over HTTPS. "
                "No open inbound ports required. Operates across home NATs, consumer firewalls, and mixed networks."
            ),
            supported_backends=["relay"],
        )

    def validate_project_compatibility(
        self,
        project: Project,
        config: Optional[TrainingConfiguration],
        num_eligible_workers: int,
    ) -> Tuple[bool, Optional[str]]:
        # 1. Require at least 2 workers for parallel training
        if num_eligible_workers < 2:
            return False, f"Data-parallel training requires at least 2 eligible worker nodes (found {num_eligible_workers})."

        # 2. Check model architecture compatibility
        arch = (project.model_architecture or "").lower()
        if not arch:
            return False, "Project does not specify a model architecture."

        # 3. Check batch size divisibility if config is present
        if config and config.batch_size:
            if config.batch_size < num_eligible_workers:
                return (
                    False,
                    f"Global batch size ({config.batch_size}) cannot be smaller than cluster size ({num_eligible_workers}).",
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
        world_size = len(workers)
        ranks: dict[int, RankAssignment] = {}

        for idx, w in enumerate(workers):
            role = "primary" if idx == 0 else "worker"
            ranks[idx] = RankAssignment(
                rank=idx,
                world_size=world_size,
                worker_id=w.user_id,
                machine_id=w.machine_id,
                role=role,
            )

        return RendezvousState(
            project_id=project_id,
            run_id=run_id,
            strategy=self.name,
            backend=self.default_backend,
            master_addr=master_addr,
            master_port=master_port,
            world_size=world_size,
            ranks=ranks,
            is_ready=world_size >= 2,
        )

    def handle_worker_failure(
        self,
        failed_worker_id: uuid.UUID,
        rendezvous: RendezvousState,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Synchronous data-parallel training requires all ranks to progress in unison.
        When a rank drops:
        1. Halt training across remaining ranks.
        2. Evict the dead rank.
        3. If surviving ranks >= 2, reconfigure new world_size = N - 1, reassign ranks 0..N-2,
           and signal rollback to the latest validated checkpoint.
        4. If surviving ranks < 2, downgrade to single_node or pause project.
        """
        failed_rank: Optional[int] = None
        for r_id, assignment in rendezvous.ranks.items():
            if assignment.worker_id == failed_worker_id:
                failed_rank = r_id
                assignment.is_healthy = False
                break

        if failed_rank is None:
            return True, f"Worker {failed_worker_id} not registered in active ranks.", None

        surviving_ranks = [a for a in rendezvous.ranks.values() if a.is_healthy]
        surviving_count = len(surviving_ranks)

        if surviving_count >= 2:
            return (
                True,
                (
                    f"Rank {failed_rank} dropped. Cluster reconfiguring from world size {rendezvous.world_size} "
                    f"to {surviving_count}. Surviving nodes will rollback to last checkpoint and resume."
                ),
                -1,  # -1 signifies rollback to latest validated checkpoint
            )
        else:
            return (
                False,
                f"Rank {failed_rank} dropped. Insufficient surviving workers ({surviving_count}) for data parallelism. Training paused.",
                None,
            )
