"""
ADC Training Execution & Sandboxing Package.

Provides isolated process sandboxing, static AST code security scanning,
resource budget containment, training adapter contracts, and execution backends.
"""

from __future__ import annotations

from agents.executor.adapter import ADCReporter, TrainingAdapter, TrainingTelemetry
from agents.executor.base import BaseTrainingExecutor, ExecutionResult, TaskExecutionConfig
from agents.executor.docker_executor import DockerTrainingExecutor
from agents.executor.manifest import PackageManifest, ResourceRequirements, parse_manifest_file
from agents.executor.sandbox import ExecutionSandbox
from agents.executor.security import CodeSecurityScanner, SecurityViolationError
from agents.executor.subprocess_executor import SubprocessTrainingExecutor

__all__ = [
    "ADCReporter",
    "TrainingAdapter",
    "TrainingTelemetry",
    "BaseTrainingExecutor",
    "ExecutionResult",
    "TaskExecutionConfig",
    "PackageManifest",
    "ResourceRequirements",
    "parse_manifest_file",
    "ExecutionSandbox",
    "CodeSecurityScanner",
    "SecurityViolationError",
    "SubprocessTrainingExecutor",
    "DockerTrainingExecutor",
]
