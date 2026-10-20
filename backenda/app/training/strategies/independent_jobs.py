"""
Independent Jobs Strategy implementation (Phase 9).
Distributes independent trials, seeds, or hyperparameter sweeps among multiple workers.
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


class IndependentJobsStrategy(BaseTrainingStrategy):
    """
    Distributes independent training jobs, seeds, experiments, or slice tasks
    across multiple worker nodes.

    IMPORTANT ARCHITECTURAL NOTE:
    Independent jobs DO NOT synchronize weights or gradients during training and do
    NOT constitute distributed parallel training of a single model. Each worker executes
    its own self-contained trial and reports progress back to the master coordinator.
    """

    @property
    def name(self) -> str:
        return "independent_jobs"

    @property
    def description(self) -> str:
        return (
            "Concurrent distribution of independent trials, seed partitions, or hyperparameter sweeps. "
            "Workers execute separate jobs without inter-worker gradient synchronization."
        )

    def get_network_requirements(self) -> NetworkTopologyRequirement:
        return NetworkTopologyRequirement(
            strategy_name=self.name,
            requires_direct_inter_worker_tcp=False,
            inbound_ports_required=False,
            supports_nat=True,
            min_bandwidth_mbps=2.0,
            estimated_sync_latency_ms=0.0,
            firewall_description=(
                "Workers connect outbound via HTTPS/WSS to the central ADC coordinator. "
                "No incoming ports required. Fully functional behind home/carrier-grade NAT."
            ),
            supported_backends=["independent_runner"],
        )

    def validate_project_compatibility(
        self,
        project: Project,
        config: Optional[TrainingConfiguration],
        num_eligible_workers: int,
    ) -> Tuple[bool, Optional[str]]:
        if num_eligible_workers < 1:
            return False, "Independent jobs strategy requires at least 1 eligible worker."
        return True, None

    def plan_rendezvous(
        self,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        workers: List[ProjectMembership],
        master_addr: str = "127.0.0.1",
        master_port: int = 29500,
    ) -> RendezvousState:
        ranks: dict[int, RankAssignment] = {}
        for idx, w in enumerate(workers):
            ranks[idx] = RankAssignment(
                rank=idx,
                world_size=len(workers),
                worker_id=w.user_id,
                machine_id=w.machine_id,
                role=f"worker_trial_{idx}",
            )

        return RendezvousState(
            project_id=project_id,
            run_id=run_id,
            strategy=self.name,
            backend="independent_runner",
            master_addr=master_addr,
            master_port=master_port,
            world_size=len(workers),
            ranks=ranks,
            is_ready=len(ranks) > 0,
        )

    def handle_worker_failure(
        self,
        failed_worker_id: uuid.UUID,
        rendezvous: RendezvousState,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        In independent jobs, worker drop only affects that worker's task.
        Surviving workers continue uninterrupted.
        """
        for r_id, assignment in rendezvous.ranks.items():
            if assignment.worker_id == failed_worker_id:
                assignment.is_healthy = False
                return (
                    True,
                    f"Worker {failed_worker_id} (Rank {r_id}) failed. Task will be re-queued. Other workers continue unaffected.",
                    None,
                )
        return True, f"Worker {failed_worker_id} not found in active assignments.", None
