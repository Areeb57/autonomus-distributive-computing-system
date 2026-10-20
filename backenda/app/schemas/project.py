"""
Pydantic schemas for projects, uploads, manifests, project codes, and worker memberships.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TrainingConfigSchema(BaseModel):
    """Hyperparameter and training configuration."""
    model_config = ConfigDict(populate_by_name=True)

    batch_size: int = Field(128, alias="batchSize", ge=1)
    total_steps: int = Field(10000, alias="totalSteps", ge=1)
    learning_rate: str = Field("2e-4", alias="learningRate")
    optimizer: str = Field("AdamW", alias="optimizer")
    precision: str = Field("fp16", alias="precision", pattern=r"^(fp16|bf16|fp32)$")
    checkpoint_interval: int = Field(500, alias="checkpointInterval", ge=10)
    gradient_accumulation_steps: int = Field(2, alias="gradientAccumulationSteps", ge=1)


class ProjectRequirementsSchema(BaseModel):
    """Hardware requirements for nodes contributing compute to this project."""
    model_config = ConfigDict(populate_by_name=True)

    min_cpu_cores: int = Field(2, alias="minCpuCores", ge=1)
    min_ram_gb: int = Field(4, alias="minRamGB", ge=1)
    gpu_recommended: bool = Field(True, alias="gpuRecommended")
    min_vram_gb: int = Field(0, alias="minVramGB", ge=0)


class ProjectCreateRequest(BaseModel):
    """Payload to create a new training project."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=3, max_length=128, description="Project name")
    description: str = Field("", max_length=2000, description="Project summary")
    training_objective: str = Field("", alias="trainingObjective", max_length=1000)
    model_architecture: str = Field("Diffusion (UNet / DiT 180M)", alias="modelArchitecture", max_length=128)
    dataset_name: str = Field("", alias="datasetName", max_length=128)
    dataset_description: str = Field("", alias="datasetDescription", max_length=1000)
    expected_duration: str = Field("Unknown", alias="expectedDuration", max_length=64)
    visibility: str = Field("public", pattern=r"^(public|unlisted)$")
    workers_needed: int = Field(1, alias="workersNeeded", ge=1, le=1000)
    training_strategy: str = Field("independent_jobs", alias="trainingStrategy")
    training_config: Optional[TrainingConfigSchema] = Field(None, alias="trainingConfig")
    requirements: Optional[ProjectRequirementsSchema] = Field(None)


class ProjectUpdateRequest(BaseModel):
    """Payload to modify existing project metadata."""
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=3, max_length=128)
    description: Optional[str] = Field(None, max_length=2000)
    training_objective: Optional[str] = Field(None, alias="trainingObjective", max_length=1000)
    model_architecture: Optional[str] = Field(None, alias="modelArchitecture", max_length=128)
    expected_duration: Optional[str] = Field(None, alias="expectedDuration", max_length=64)
    visibility: Optional[str] = Field(None, pattern=r"^(public|unlisted)$")
    workers_needed: Optional[int] = Field(None, alias="workersNeeded", ge=1, le=1000)
    training_strategy: Optional[str] = Field(None, alias="trainingStrategy")


class DatasetResponse(BaseModel):
    """Metadata for an uploaded dataset."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    description: str
    size_bytes: int = Field(..., serialization_alias="sizeBytes")
    format: str
    checksum_sha256: str = Field(..., serialization_alias="checksumSha256")
    is_validated: bool = Field(..., serialization_alias="isValidated")
    validation_error: Optional[str] = Field(None, serialization_alias="validationError")
    created_at: datetime = Field(..., serialization_alias="createdAt")


class ModelPackageResponse(BaseModel):
    """Metadata for an uploaded training code package."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    file_name: str = Field(..., serialization_alias="fileName")
    file_size_bytes: int = Field(..., serialization_alias="fileSizeBytes")
    entrypoint: str
    checksum_sha256: str = Field(..., serialization_alias="checksumSha256")
    is_validated: bool = Field(..., serialization_alias="isValidated")
    validation_error: Optional[str] = Field(None, serialization_alias="validationError")
    manifest: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(..., serialization_alias="createdAt")


class WorkerNodeResponse(BaseModel):
    """Connected worker node information matching frontend WorkerNode."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    machine_id: uuid.UUID = Field(..., serialization_alias="machineId")
    name: str
    is_current_user: bool = Field(..., serialization_alias="isCurrentUser")
    status: str
    cpu_model: str = Field("Unknown", serialization_alias="cpuModel")
    cpu_cores_total: int = Field(1, serialization_alias="cpuCoresTotal")
    cpu_cores_contributed: int = Field(..., serialization_alias="cpuCoresContributed")
    ram_total_gb: float = Field(0.0, serialization_alias="ramTotalGB")
    ram_contributed_gb: float = Field(..., serialization_alias="ramContributedGB")
    gpu_model: str = Field("None", serialization_alias="gpuModel")
    gpu_memory_total_gb: float = Field(0.0, serialization_alias="gpuMemoryTotalGB")
    gpu_enabled: bool = Field(..., serialization_alias="gpuEnabled")
    storage_budget_gb: float = Field(..., serialization_alias="storageBudgetGB")
    network_preference: str = Field(..., serialization_alias="networkPreference")
    current_batch: int = Field(0, serialization_alias="currentBatch")
    steps_processed: int = Field(0, serialization_alias="stepsProcessed")
    joined_at: datetime = Field(..., serialization_alias="joinedAt")
    contribution_status: str = Field(..., serialization_alias="contributionStatus")


class ProjectOwnerResponse(BaseModel):
    """Owner metadata matching frontend expectation."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    is_current_user: bool = Field(..., serialization_alias="isCurrentUser")


class ProjectDetailResponse(BaseModel):
    """Consolidated project detail representation."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    description: str
    training_objective: str = Field(..., serialization_alias="trainingObjective")
    model_architecture: str = Field(..., serialization_alias="modelArchitecture")
    dataset_name: str = Field("", serialization_alias="datasetName")
    dataset_description: str = Field("", serialization_alias="datasetDescription")
    dataset_size: str = Field("0 MB", serialization_alias="datasetSize")
    code_file_name: str = Field("", serialization_alias="codeFileName")
    code_file_size: str = Field("0 MB", serialization_alias="codeFileSize")
    status: str
    visibility: str
    owner: ProjectOwnerResponse
    created_at: datetime = Field(..., serialization_alias="createdAt")
    expected_duration: str = Field(..., serialization_alias="expectedDuration")
    training_strategy: str = Field(..., serialization_alias="trainingStrategy")
    workers_needed: int = Field(..., serialization_alias="workersNeeded")
    requirements: ProjectRequirementsSchema
    training_config: Optional[TrainingConfigSchema] = Field(None, serialization_alias="trainingConfig")
    active_code: Optional[str] = Field(None, serialization_alias="activeCode")
    datasets: List[DatasetResponse] = Field(default_factory=list)
    packages: List[ModelPackageResponse] = Field(default_factory=list)
    workers: List[WorkerNodeResponse] = Field(default_factory=list)
    metrics: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, Any]] = Field(default_factory=list)



class ProjectListResponse(BaseModel):
    """Paginated or filtered list of projects."""
    model_config = ConfigDict(populate_by_name=True)

    projects: List[ProjectDetailResponse]
    total: int


class PutOnlineResponse(BaseModel):
    """Response returned upon putting project online."""
    model_config = ConfigDict(populate_by_name=True)

    status: str = "online"
    project_code: str = Field(..., serialization_alias="projectCode")
    message: str = "Project is now online and accepting volunteer worker nodes."
    project: ProjectDetailResponse


class JoinByCodeRequest(BaseModel):
    """Worker request to join a project using its 9-digit code."""
    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(..., min_length=9, max_length=16, description="9-digit project join code (e.g. 123-456-789)")
    cpu_cores: Optional[int] = Field(None, alias="cpuCores", ge=1)
    ram_gb: Optional[float] = Field(None, alias="ramGB", ge=0.5)
    gpu_enabled: Optional[bool] = Field(None, alias="gpuEnabled")
    storage_gb: Optional[float] = Field(None, alias="storageGB", ge=1.0)
    network_preference: Optional[str] = Field(None, alias="networkPreference", pattern=r"^(unlimited|moderate|saver)$")


class MembershipResponse(BaseModel):
    """Worker membership record."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    project_id: uuid.UUID = Field(..., serialization_alias="projectId")
    machine_id: uuid.UUID = Field(..., serialization_alias="machineId")
    status: str
    contribution_status: str = Field(..., serialization_alias="contributionStatus")
    cpu_cores_contributed: int = Field(..., serialization_alias="cpuCoresContributed")
    ram_contributed_gb: float = Field(..., serialization_alias="ramContributedGB")
    gpu_enabled: bool = Field(..., serialization_alias="gpuEnabled")
    storage_budget_gb: float = Field(..., serialization_alias="storageBudgetGB")
    network_preference: str = Field(..., serialization_alias="networkPreference")
    joined_at: datetime = Field(..., serialization_alias="joinedAt")


class MembershipUpdateRequest(BaseModel):
    """Payload to adjust worker contribution allocation on a project."""
    model_config = ConfigDict(populate_by_name=True)

    cpu_cores: Optional[int] = Field(None, alias="cpuCores", ge=1)
    ram_gb: Optional[float] = Field(None, alias="ramGB", ge=0.5)
    gpu_enabled: Optional[bool] = Field(None, alias="gpuEnabled")
    storage_gb: Optional[float] = Field(None, alias="storageGB", ge=1.0)
    network_preference: Optional[str] = Field(None, alias="networkPreference", pattern=r"^(unlimited|moderate|saver)$")


class ProjectProgressResponse(BaseModel):
    """Training progress and live metrics for a project."""
    model_config = ConfigDict(populate_by_name=True)

    project_id: uuid.UUID = Field(..., serialization_alias="projectId")
    status: str
    current_step: int = Field(0, serialization_alias="currentStep")
    total_steps: int = Field(1000, serialization_alias="totalSteps")
    progress_percent: float = Field(0.0, serialization_alias="progressPercent")
    training_speed: float = Field(0.0, serialization_alias="trainingSpeed")
    current_loss: Optional[float] = Field(None, serialization_alias="currentLoss")
    history: List[Dict[str, Any]] = Field(default_factory=list)
