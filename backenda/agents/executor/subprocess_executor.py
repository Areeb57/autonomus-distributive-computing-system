"""
Local Subprocess Training Executor with resource supervision, log capture, and tree cleanup.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

import psutil

from agents.executor.adapter import TrainingAdapter
from agents.executor.base import (
    BaseTrainingExecutor,
    ExecutionResult,
    MetricCallback,
    TaskExecutionConfig,
)
from agents.executor.sandbox import ExecutionSandbox
from agents.executor.security import SecurityViolationError
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger("adc.executor.subprocess")


class ResourceLimitExceededError(Exception):
    """Raised when training child process exceeds memory or runtime quotas."""
    pass


class SubprocessTrainingExecutor(BaseTrainingExecutor):
    """
    Supervises training execution in an isolated child process using dedicated sandbox workspace.
    """

    def __init__(self, sandbox_base_dir: Optional[Path | str] = None) -> None:
        self.sandbox_base_dir = sandbox_base_dir
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._is_cancelled = False
        self._sandbox: Optional[ExecutionSandbox] = None

    async def execute(
        self,
        config: TaskExecutionConfig,
        on_metric: Optional[MetricCallback] = None,
    ) -> ExecutionResult:
        """Execute training task with async log streaming and resource bounds."""
        self._is_cancelled = False
        start_time = time.time()
        task_id = config.task_id

        # 1. Initialize isolated sandbox
        sandbox = ExecutionSandbox(task_id=task_id, base_dir=self.sandbox_base_dir)
        self._sandbox = sandbox
        sandbox.setup_directories()

        log_path = sandbox.logs_dir / "execution.log"
        log_file = open(log_path, "w", encoding="utf-8")

        steps_completed = config.step_start
        last_loss = None
        found_checkpoints: List[str] = []

        try:
            # 2. Extract and inspect package & dataset
            manifest = sandbox.extract_package(config.package_path)
            sandbox.extract_dataset(config.dataset_path)

            # 3. Build sanitized environment
            env = sandbox.get_sanitized_environment(
                step_start=config.step_start,
                step_end=config.step_end,
                total_steps=config.total_steps,
                resume_checkpoint_path=config.resume_checkpoint_path,
                extra_env=config.extra_env,
            )

            # 4. Resolve python interpreter and entrypoint
            python_bin = config.python_executable or sys.executable
            entrypoint_path = sandbox.code_dir / manifest.entrypoint

            cmd = [python_bin, "-u", str(entrypoint_path)]

            logger.info(
                "launching_training_subprocess",
                task_id=task_id,
                entrypoint=manifest.entrypoint,
                step_start=config.step_start,
                step_end=config.step_end,
            )

            # 5. Spawn child process
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(sandbox.code_dir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self._proc = proc

            # 6. Stream stdout lines and supervise execution
            monitor_task = asyncio.create_task(
                self._supervise_resources(proc.pid, config.max_ram_gb, config.max_runtime_seconds)
            )

            try:
                assert proc.stdout is not None
                while True:
                    line_bytes = await proc.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace")
                    log_file.write(line)
                    log_file.flush()

                    # Parse real-time training telemetry
                    telemetry = TrainingAdapter.parse_stdout_line(line)
                    if telemetry:
                        if telemetry.step:
                            steps_completed = telemetry.step
                        if telemetry.loss is not None:
                            last_loss = telemetry.loss
                        if telemetry.checkpoint_path:
                            found_checkpoints.append(telemetry.checkpoint_path)

                        if on_metric:
                            try:
                                await on_metric(telemetry)
                            except Exception as m_exc:
                                logger.warning("on_metric_callback_error", error=str(m_exc))

                exit_code = await proc.wait()
            finally:
                monitor_task.cancel()

            # 7. Discover any checkpoints created in checkpoints_dir
            for f in sandbox.checkpoints_dir.glob("*"):
                if f.is_file() and str(f) not in found_checkpoints:
                    found_checkpoints.append(str(f))

            duration = time.time() - start_time
            success = exit_code == 0 and not self._is_cancelled

            return ExecutionResult(
                task_id=task_id,
                success=success,
                exit_code=exit_code,
                steps_completed=steps_completed,
                last_loss=last_loss,
                duration_seconds=duration,
                checkpoints=found_checkpoints,
                log_file_path=str(log_path),
                error_message=None if success else f"Process exited with non-zero exit code {exit_code}",
                audit_provenance={
                    "entrypoint": manifest.entrypoint,
                    "manifest_version": manifest.version,
                    "start_time": start_time,
                    "duration_seconds": duration,
                    "exit_code": exit_code,
                    "pid": proc.pid,
                },
            )

        except (SecurityViolationError, ValidationError, ResourceLimitExceededError) as exc:
            duration = time.time() - start_time
            logger.error("training_execution_failed", task_id=task_id, error=str(exc))
            return ExecutionResult(
                task_id=task_id,
                success=False,
                exit_code=1,
                steps_completed=steps_completed,
                last_loss=last_loss,
                duration_seconds=duration,
                checkpoints=found_checkpoints,
                log_file_path=str(log_path),
                error_message=str(exc),
                audit_provenance={"error": str(exc), "duration": duration},
            )

        finally:
            log_file.close()
            # Clean up unpacked code and dataset, preserving checkpoints and logs
            sandbox.cleanup(keep_outputs=True)
            self._proc = None

    async def _supervise_resources(
        self,
        pid: int,
        max_ram_gb: float,
        max_runtime_seconds: int,
    ) -> None:
        """
        Background task periodically checking child process memory usage and execution timeout.
        """
        start = time.time()
        max_bytes = int(max_ram_gb * 1024 * 1024 * 1024)

        try:
            ps_proc = psutil.Process(pid)
            while True:
                await asyncio.sleep(1.0)
                # Check runtime timeout
                if time.time() - start > max_runtime_seconds:
                    logger.error("training_execution_timeout", pid=pid, limit_sec=max_runtime_seconds)
                    await self.cancel()
                    raise ResourceLimitExceededError(
                        f"Execution exceeded maximum allotted runtime of {max_runtime_seconds} seconds."
                    )

                # Check memory pressure
                try:
                    mem_info = ps_proc.memory_info()
                    if mem_info.rss > max_bytes:
                        logger.error(
                            "training_memory_limit_exceeded",
                            pid=pid,
                            used_gb=mem_info.rss / (1024**3),
                            limit_gb=max_ram_gb,
                        )
                        await self.cancel()
                        raise ResourceLimitExceededError(
                            f"Memory usage ({mem_info.rss / (1024**3):.2f} GB) exceeded limit ({max_ram_gb:.2f} GB)."
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
        except (psutil.NoSuchProcess, asyncio.CancelledError):
            pass

    async def cancel(self) -> None:
        """
        Cooperatively terminate the running process tree.
        Sends SIGINT/SIGTERM, gives grace period, then tree-kills with psutil.
        """
        self._is_cancelled = True
        proc = self._proc
        if not proc or proc.returncode is not None:
            return

        pid = proc.pid
        logger.info("cancelling_training_process", pid=pid)

        # 1. Cooperative termination request
        try:
            proc.terminate()
        except ProcessLookupError:
            return

        # 2. Wait up to 3 seconds for graceful shutdown
        for _ in range(30):
            if proc.returncode is not None:
                return
            await asyncio.sleep(0.1)

        # 3. Force tree-kill if still running
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        try:
            proc.kill()
        except ProcessLookupError:
            pass
