"""
Abstract Base Training Executor interface and execution data models.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from agents.executor.adapter import TrainingTelemetry


class TaskExecutionConfig(BaseModel):
    """Configuration passed to the executor to run a training step slice."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    task_id: str = Field(..., alias="taskId")
    project_id: str = Field(..., alias="projectId")
    package_path: Path = Field(..., alias="packagePath")
    dataset_path: Path = Field(..., alias="datasetPath")
    step_start: int = Field(0, alias="stepStart")
    step_end: int = Field(50, alias="stepEnd")
    total_steps: int = Field(1000, alias="totalSteps")
    max_runtime_seconds: int = Field(3600, alias="maxRuntimeSeconds")
    max_ram_gb: float = Field(8.0, alias="maxRamGB")
    max_cpu_percent: float = Field(95.0, alias="maxCpuPercent")
    python_executable: Optional[str] = Field(None, alias="pythonExecutable")
    resume_checkpoint_path: Optional[Path] = Field(None, alias="resumeCheckpointPath")
    extra_env: Dict[str, str] = Field(default_factory=dict, alias="extraEnv")


class ExecutionResult(BaseModel):
    """Comprehensive summary returned following training execution."""
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., alias="taskId")
    success: bool
    exit_code: int = Field(..., alias="exitCode")
    steps_completed: int = Field(0, alias="stepsCompleted")
    last_loss: Optional[float] = Field(None, alias="lastLoss")
    duration_seconds: float = Field(0.0, alias="durationSeconds")
    checkpoints: List[str] = Field(default_factory=list)
    log_file_path: Optional[str] = Field(None, alias="logFilePath")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    audit_provenance: Dict[str, Any] = Field(default_factory=dict, alias="auditProvenance")


# Callback type for real-time telemetry updates
MetricCallback = Callable[[TrainingTelemetry], Awaitable[None]]


class BaseTrainingExecutor(abc.ABC):
    """
    Abstract interface for training execution backends (Subprocess, Container).
    """

    @abc.abstractmethod
    async def execute(
        self,
        config: TaskExecutionConfig,
        on_metric: Optional[MetricCallback] = None,
    ) -> ExecutionResult:
        """Execute training task in isolated environment."""
        pass

    @abc.abstractmethod
    async def cancel(self) -> None:
        """Cooperatively terminate running process tree."""
        pass
