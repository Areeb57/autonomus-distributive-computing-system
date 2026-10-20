"""
Pydantic schemas for hardware profiles, contribution settings, budgets, and cluster capacity.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HardwareProfileResponse(BaseModel):
    """Physical hardware capabilities detected on the machine."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    cpu_model: str = Field(..., alias="cpuModel", serialization_alias="cpuModel")
    cpu_cores: int = Field(..., alias="cpuCores", serialization_alias="cpuCores")
    ram_total_gb: float = Field(..., alias="ramTotalGB", serialization_alias="ramTotalGB")
    ram_available_gb: float = Field(..., alias="ramAvailableGB", serialization_alias="ramAvailableGB")
    gpu_model: str = Field("None", alias="gpuModel", serialization_alias="gpuModel")
    gpu_memory_total_gb: float = Field(0.0, alias="gpuMemoryTotalGB", serialization_alias="gpuMemoryTotalGB")
    disk_space_available_gb: float = Field(..., alias="diskSpaceAvailableGB", serialization_alias="diskSpaceAvailableGB")


class ContributionSettingsResponse(BaseModel):
    """User-configured volunteer compute budgets and global pause toggle."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    cpu_enabled: bool = Field(True, alias="cpuEnabled", serialization_alias="cpuEnabled")
    cpu_cores: int = Field(2, alias="cpuCores", serialization_alias="cpuCores")
    ram_budget_gb: float = Field(4.0, alias="ramBudgetGB", serialization_alias="ramBudgetGB")
    gpu_enabled: bool = Field(False, alias="gpuEnabled", serialization_alias="gpuEnabled")
    selected_gpu: str = Field("", alias="selectedGpu", serialization_alias="selectedGpu")
    storage_budget_gb: float = Field(20.0, alias="storageBudgetGB", serialization_alias="storageBudgetGB")
    network_preference: str = Field("unlimited", alias="networkPreference", serialization_alias="networkPreference")
    global_paused: bool = Field(False, alias="globalPaused", serialization_alias="globalPaused")


class ContributionSettingsUpdate(BaseModel):
    """Payload to modify contribution settings and budgets."""
    model_config = ConfigDict(populate_by_name=True)

    cpu_enabled: Optional[bool] = Field(None, alias="cpuEnabled")
    cpu_cores: Optional[int] = Field(None, alias="cpuCores", ge=1, le=512)
    ram_budget_gb: Optional[float] = Field(None, alias="ramBudgetGB", ge=0.5, le=1024.0)
    gpu_enabled: Optional[bool] = Field(None, alias="gpuEnabled")
    selected_gpu: Optional[str] = Field(None, alias="selectedGpu")
    storage_budget_gb: Optional[float] = Field(None, alias="storageBudgetGB", ge=1.0, le=100000.0)
    network_preference: Optional[str] = Field(
        None,
        alias="networkPreference",
        pattern=r"^(unlimited|moderate|saver)$",
    )
    global_paused: Optional[bool] = Field(None, alias="globalPaused")


class ClusterCapacitySummary(BaseModel):
    """Aggregated capacity metrics across all active worker nodes."""
    model_config = ConfigDict(populate_by_name=True)

    active_workers_count: int = Field(0, serialization_alias="activeWorkersCount")
    total_contributed_cpu_cores: int = Field(0, serialization_alias="totalContributedCpuCores")
    total_contributed_ram_gb: float = Field(0.0, serialization_alias="totalContributedRamGB")
    total_contributed_storage_gb: float = Field(0.0, serialization_alias="totalContributedStorageGB")


class UserResourcesResponse(BaseModel):
    """Consolidated resource endpoint response for frontend Resource pages."""
    model_config = ConfigDict(populate_by_name=True)

    hardware_profile: HardwareProfileResponse = Field(..., serialization_alias="hardwareProfile")
    contribution_settings: ContributionSettingsResponse = Field(..., serialization_alias="contributionSettings")
    available_gpus: List[str] = Field(default_factory=list, serialization_alias="availableGpus")
    cluster_summary: Optional[ClusterCapacitySummary] = Field(None, serialization_alias="clusterSummary")


class PauseResumeResponse(BaseModel):
    """Response returned upon toggling global contribution pause."""
    model_config = ConfigDict(populate_by_name=True)

    global_paused: bool = Field(..., serialization_alias="globalPaused")
    message: str
    affected_machines: int = Field(..., serialization_alias="affectedMachines")
