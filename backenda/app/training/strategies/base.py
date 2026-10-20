"""
Base Strategy Interface, Network Topology Specifications, and Rank Management (Phase 9).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import Project, ProjectMembership
from app.models.training import TrainingConfiguration


class NetworkTopologyRequirement(BaseModel):
    """
    Explicit network and firewall requirements for a distributed training strategy.
    Guarantees no silent fallback to simulated synchronization.
    """
    model_config = ConfigDict(populate_by_name=True)

    strategy_name: str = Field(..., alias="strategyName")
    requires_direct_inter_worker_tcp: bool = Field(..., alias="requiresDirectInterWorkerTcp")
    inbound_ports_required: bool = Field(..., alias="inboundPortsRequired")
    supports_nat: bool = Field(..., alias="supportsNat")
    min_bandwidth_mbps: float = Field(..., alias="minBandwidthMbps")
    estimated_sync_latency_ms: float = Field(..., alias="estimatedSyncLatencyMs")
    firewall_description: str = Field(..., alias="firewallDescription")
    supported_backends: List[str] = Field(default_factory=list, alias="supportedBackends")


class RankAssignment(BaseModel):
    """Assignment of a compute node to a specific rank within the distributed world."""
    model_config = ConfigDict(populate_by_name=True)

    rank: int
    world_size: int = Field(..., alias="worldSize")
    worker_id: uuid.UUID = Field(..., alias="workerId")
    machine_id: Optional[uuid.UUID] = Field(None, alias="machineId")
    role: str = "worker"  # "primary", "worker", "stage_0", "stage_1"
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="assignedAt")
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="lastHeartbeat")
    is_healthy: bool = Field(True, alias="isHealthy")


class RendezvousState(BaseModel):
    """Cluster-wide rendezvous and communication state for an active training run."""
    model_config = ConfigDict(populate_by_name=True)

    project_id: uuid.UUID = Field(..., alias="projectId")
    run_id: uuid.UUID = Field(..., alias="runId")
    strategy: str
    backend: str  # "relay", "gloo", "nccl"
    master_addr: str = Field("127.0.0.1", alias="masterAddr")
    master_port: int = Field(29500, alias="masterPort")
    world_size: int = Field(..., alias="worldSize")
    ranks: Dict[int, RankAssignment] = Field(default_factory=dict)
    is_ready: bool = Field(False, alias="isReady")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt")


class BaseTrainingStrategy(ABC):
    """
    Abstract interface for ADC training strategies.
    Every strategy must specify real communication mechanics, failure handling,
    and rigorous compatibility rules.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of how compute is distributed."""
        pass

    @abstractmethod
    def get_network_requirements(self) -> NetworkTopologyRequirement:
        """
        Return the physical/logical network and firewall requirements.
        """
        pass

    @abstractmethod
    def validate_project_compatibility(
        self,
        project: Project,
        config: Optional[TrainingConfiguration],
        num_eligible_workers: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate whether the project and cluster configuration are compatible.
        Rejects invalid configurations before starting training.
        """
        pass

    @abstractmethod
    def plan_rendezvous(
        self,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        workers: List[ProjectMembership],
        master_addr: str = "127.0.0.1",
        master_port: int = 29500,
    ) -> RendezvousState:
        """
        Assign ranks and establish the rendezvous coordination plan.
        """
        pass

    @abstractmethod
    def handle_worker_failure(
        self,
        failed_worker_id: uuid.UUID,
        rendezvous: RendezvousState,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Handle a worker drop or heartbeat lease expiry during training.
        Returns: (can_continue: bool, message: str, rollback_step: Optional[int])
        """
        pass
