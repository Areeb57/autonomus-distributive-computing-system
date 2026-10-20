"""
Pydantic schemas for Distributed Training Strategies, Rendezvous, and Sync APIs (Phase 9).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.training.strategies.base import NetworkTopologyRequirement, RankAssignment


class StrategyInfoResponse(BaseModel):
    """Detailed metadata and network requirement specifications for a training strategy."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    network_requirements: NetworkTopologyRequirement = Field(..., alias="networkRequirements")


class StrategyListResponse(BaseModel):
    """List of all registered training strategies."""
    model_config = ConfigDict(populate_by_name=True)

    total: int
    strategies: List[StrategyInfoResponse]


class RendezvousRequest(BaseModel):
    """Worker node querying or registering for distributed rank assignment."""
    model_config = ConfigDict(populate_by_name=True)

    run_id: Optional[uuid.UUID] = Field(None, alias="runId")


class RendezvousResponse(BaseModel):
    """Rendezvous instructions and rank assignment for a compute node."""
    model_config = ConfigDict(populate_by_name=True)

    project_id: uuid.UUID = Field(..., alias="projectId")
    run_id: uuid.UUID = Field(..., alias="runId")
    strategy: str
    backend: str
    rank: int
    world_size: int = Field(..., alias="worldSize")
    master_addr: str = Field(..., alias="masterAddr")
    master_port: int = Field(..., alias="masterPort")
    relay_sync_url: str = Field(..., alias="relaySyncUrl")
    is_ready: bool = Field(..., alias="isReady")
    role: str = "worker"


class DistributedHeartbeatRequest(BaseModel):
    """Liveness ping from a distributed worker node."""
    model_config = ConfigDict(populate_by_name=True)

    run_id: uuid.UUID = Field(..., alias="runId")
    rank: int
    current_step: int = Field(..., alias="currentStep")


class DistributedHeartbeatResponse(BaseModel):
    """Coordinator response to distributed heartbeat."""
    model_config = ConfigDict(populate_by_name=True)

    status: str
    is_healthy: bool = Field(..., alias="isHealthy")
    active_ranks: List[int] = Field(..., alias="activeRanks")


class DistributedStatusResponse(BaseModel):
    """Full cluster coordination and rank status for a training run."""
    model_config = ConfigDict(populate_by_name=True)

    project_id: uuid.UUID = Field(..., alias="projectId")
    run_id: uuid.UUID = Field(..., alias="runId")
    strategy: str
    backend: str
    world_size: int = Field(..., alias="worldSize")
    ranks: Dict[int, RankAssignment]
    is_ready: bool = Field(..., alias="isReady")
