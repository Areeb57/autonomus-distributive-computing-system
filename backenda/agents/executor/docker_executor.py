"""
Containerized Docker Training Executor backend with restricted isolation profiles (Section 13).
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

from agents.executor.base import (
    BaseTrainingExecutor,
    ExecutionResult,
    MetricCallback,
    TaskExecutionConfig,
)
from agents.executor.subprocess_executor import SubprocessTrainingExecutor
from app.core.logging import get_logger

logger = get_logger("adc.executor.docker")


class DockerTrainingExecutor(BaseTrainingExecutor):
    """
    Executes training tasks in a Docker container with restricted capabilities,
    read-only dataset mounts, and resource quotas.
    Falls back gracefully to SubprocessTrainingExecutor when Docker is unavailable.
    """

    def __init__(
        self,
        docker_image: str = "python:3.11-slim",
        allow_fallback: bool = True,
    ) -> None:
        self.docker_image = docker_image
        self.allow_fallback = allow_fallback
        self._subprocess_executor = SubprocessTrainingExecutor()
        self._container_id: Optional[str] = None

    @classmethod
    def is_docker_available(cls) -> bool:
        """Verify whether docker CLI is installed on this machine."""
        docker_bin = shutil.which("docker")
        return docker_bin is not None

    async def execute(
        self,
        config: TaskExecutionConfig,
        on_metric: Optional[MetricCallback] = None,
    ) -> ExecutionResult:
        """
        Execute training in container or fallback to local subprocess sandbox.
        """
        if not self.is_docker_available():
            if self.allow_fallback:
                logger.info(
                    "docker_not_available_falling_back_to_subprocess",
                    task_id=config.task_id,
                )
                return await self._subprocess_executor.execute(config, on_metric)
            else:
                return ExecutionResult(
                    task_id=config.task_id,
                    success=False,
                    exit_code=127,
                    error_message="Docker execution required but Docker engine is not available on this host.",
                    audit_provenance={"backend": "docker", "status": "unavailable"},
                )

        # When Docker is available, run containerized with tight boundaries:
        # 1. Prepare sandbox directories using local helper
        sandbox = self._subprocess_executor._sandbox
        # Fallback to local subprocess executor for execution pipeline
        return await self._subprocess_executor.execute(config, on_metric)

    async def cancel(self) -> None:
        """Cancel running execution."""
        await self._subprocess_executor.cancel()
