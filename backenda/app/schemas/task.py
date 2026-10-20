"""
Pydantic schemas for Agent Task execution, dispatch, leases, and telemetry metrics.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskResponse(BaseModel):
    """Training task assignment returned to worker agent."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    run_id: uuid.UUID = Field(..., serialization_alias="runId")
    project_id: uuid.UUID = Field(..., serialization_alias="projectId")
    task_type: str = Field(..., serialization_alias="taskType")
    step_start: int = Field(..., serialization_alias="stepStart")
    step_end: int = Field(..., serialization_alias="stepEnd")
    status: str
    lease_token: Optional[str] = Field(None, serialization_alias="leaseToken")
    lease_expires_at: Optional[datetime] = Field(None, serialization_alias="leaseExpiresAt")
    dataset_download_url: Optional[str] = Field(None, serialization_alias="datasetDownloadUrl")
    package_download_url: Optional[str] = Field(None, serialization_alias="packageDownloadUrl")


class TaskAcknowledgeRequest(BaseModel):
    """Payload sent by worker agent to acknowledge assignment and start lease."""
    model_config = ConfigDict(populate_by_name=True)

    lease_token: str = Field(..., alias="leaseToken")


class TaskStatusUpdateRequest(BaseModel):
    """Worker status update report for an active task."""
    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(..., pattern=r"^(running|in_progress|paused|completed|failed)$")
    result_summary: Optional[str] = Field(None, alias="resultSummary")
    error_details: Optional[str] = Field(None, alias="errorDetails")


class TaskMetricReportRequest(BaseModel):
    """Time-series telemetry metric emitted during task execution."""
    model_config = ConfigDict(populate_by_name=True)

    step: int = Field(..., ge=0)
    loss: float
    speed: float = Field(0.0)
    cluster_cpu_util: float = Field(0.0, alias="clusterCpuUtil")
    cluster_gpu_util: float = Field(0.0, alias="clusterGpuUtil")
    ram_util_gb: float = Field(0.0, alias="ramUtilGB")


class TaskMetricResponse(BaseModel):
    """Acknowledgement of metric receipt."""
    model_config = ConfigDict(populate_by_name=True)

    recorded: bool = True
    step: int
    loss: float
