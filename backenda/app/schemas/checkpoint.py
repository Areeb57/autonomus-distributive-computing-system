"""
Pydantic schemas for Model Checkpoints, metadata, atomic publication, and resumption.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CheckpointResponse(BaseModel):
    """Metadata response for a validated model checkpoint."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    project_id: uuid.UUID = Field(..., alias="projectId")
    run_id: uuid.UUID = Field(..., alias="runId")
    step: int
    file_size_bytes: int = Field(..., alias="fileSizeBytes")
    checksum_sha256: str = Field(..., alias="checksumSha256")
    is_validated: bool = Field(..., alias="isValidated")
    metrics: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(..., alias="createdAt")
    download_url: str = Field(..., alias="downloadUrl")


class CheckpointListResponse(BaseModel):
    """List of all checkpoints saved for a training project."""
    model_config = ConfigDict(populate_by_name=True)

    total: int
    checkpoints: List[CheckpointResponse]


class ResumeCheckpointRequest(BaseModel):
    """Payload to resume training from a specific validated checkpoint."""
    model_config = ConfigDict(populate_by_name=True)

    checkpoint_id: uuid.UUID = Field(..., alias="checkpointId")


class ResumeCheckpointResponse(BaseModel):
    """Response confirming project run resumption from checkpoint."""
    model_config = ConfigDict(populate_by_name=True)

    project_id: uuid.UUID = Field(..., alias="projectId")
    resumed_step: int = Field(..., alias="resumedStep")
    checkpoint_id: uuid.UUID = Field(..., alias="checkpointId")
    status: str = "resumed"

