"""
Single Node Training Strategy implementation.
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


class SingleNodeStrategy(BaseTrainingStrategy):
    """
    Executes a training job on a single compute node (worker or master).
    No distributed synchronization or inter-node communication is involved.
    """

    @property
    def name(self) -> str:
        return "single_node"

    @property
    def description(self) -> str:
        return "Standard execution of training workload on a single machine."

    def get_network_requirements(self) -> NetworkTopologyRequirement:
        return NetworkTopologyRequirement(
            strategy_name=self.name,
            requires_direct_inter_worker_tcp=False,
            inbound_ports_required=False,
            supports_nat=True,
            min_bandwidth_mbps=1.0,
            estimated_sync_latency_ms=0.0,
            firewall_description="No inbound firewall ports or inter-worker communication required.",
            supported_backends=["local"],
        )

    def validate_project_compatibility(
        self,
        project: Project,
        config: Optional[TrainingConfiguration],
        num_eligible_workers: int,
    ) -> Tuple[bool, Optional[str]]:
        if num_eligible_workers < 1:
            return False, "Single node strategy requires at least 1 online eligible worker or master."
        return True, None

    def plan_rendezvous(
        self,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        workers: List[ProjectMembership],
        master_addr: str = "127.0.0.1",
        master_port: int = 29500,
    ) -> RendezvousState:
        assigned_worker = workers[0] if workers else None
        worker_id = assigned_worker.user_id if assigned_worker else uuid.uuid4()
        machine_id = assigned_worker.machine_id if assigned_worker else None

        rank_0 = RankAssignment(
            rank=0,
            world_size=1,
            worker_id=worker_id,
            machine_id=machine_id,
            role="primary",
        )

        return RendezvousState(
            project_id=project_id,
            run_id=run_id,
            strategy=self.name,
            backend="local",
            master_addr="127.0.0.1",
            master_port=master_port,
            world_size=1,
            ranks={0: rank_0},
            is_ready=True,
        )

    def handle_worker_failure(
        self,
        failed_worker_id: uuid.UUID,
        rendezvous: RendezvousState,
    ) -> Tuple[bool, str, Optional[int]]:
        return False, "Single node worker disconnected. Training halted.", None
