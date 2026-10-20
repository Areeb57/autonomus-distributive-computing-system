"""
ADC Worker Agent Launcher.

Entry point for running the Worker compute agent on a resource-contributing machine.
Enforces:
- Identity registration with Ed25519 keypair
- Browser pairing workflow
- Active Worker role lease and periodic heartbeats
"""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import Optional

from agents.common.client import AgentBackendClient
from agents.common.guard import ResourceGuard
from agents.common.hardware import HardwareDetector
from agents.common.identity import MachineIdentity
from agents.common.lease import LeaseManager
from agents.executor import SubprocessTrainingExecutor, TaskExecutionConfig, TrainingTelemetry
from app.core.logging import get_logger

logger = get_logger("adc.agent.worker")


class WorkerAgent:
    """Worker node compute agent with local resource guard and hardware telemetry."""

    def __init__(self, backend_url: str = "http://localhost:8000") -> None:
        self.backend_url = backend_url
        self.identity = MachineIdentity.load_or_create()
        self.client = AgentBackendClient(base_url=backend_url, identity=self.identity)
        self.guard = ResourceGuard()
        self.lease_manager: Optional[LeaseManager] = None
        self.executor = SubprocessTrainingExecutor()
        self.cache_dir = Path("storage/worker_cache")
        self._running = False

    async def run(self) -> None:
        """Main worker agent startup, pairing, and heartbeat loop."""
        self._running = True
        print(f"\n[ADC Worker Agent] Initializing on {self.identity.name} ({self.identity.installation_id})")

        # 1. Register machine with backend
        try:
            reg_info = await self.client.register()
            print(f"[ADC Worker Agent] Registered with backend: {reg_info.get('name')}")
        except Exception as exc:
            print(f"[ADC Worker Agent] Warning: Registration check returned: {exc}")

        # 2. Check current status
        status = await self.client.get_status()
        active_role = status.get("activeRole", "none")
        paired_user = status.get("pairedUserId")

        # 3. Handle pairing if not paired or wrong role
        if not paired_user or active_role != "worker":
            challenge = await self.client.request_pairing_challenge()
            code = challenge["challengeCode"]

            print("\n" + "=" * 70)
            print("  ADC WORKER AGENT — BROWSER PAIRING REQUIRED")
            print("=" * 70)
            print(f"\n  Your Pairing Code:    >>>  {code}  <<<")
            print("  Expires in:           5 minutes\n")
            print("  Instructions:")
            print("  1. Open http://localhost:5173/ in your browser")
            print("  2. Log in to your ADC account")
            print("  3. Complete pairing selecting the 'Worker' role")
            print("=" * 70 + "\n")
            print("Waiting for browser pairing to complete...")

            while self._running:
                await asyncio.sleep(3)
                status = await self.client.get_status()
                if status.get("pairedUserId") and status.get("activeRole") == "worker":
                    print("\n[ADC Worker Agent] Pairing confirmed! Role: Worker")
                    break

        # 4. Acquire/start lease manager with local resource guard and telemetry
        self.client.lease_token = status.get("leaseToken") or "local-dev-lease"
        self.lease_manager = LeaseManager(
            client=self.client,
            interval_seconds=20,
            status_getter=self._get_worker_status,
            metrics_getter=self._get_telemetry,
        )
        await self.lease_manager.start()

        print("[ADC Worker Agent] Worker node is online and reporting hardware telemetry.")
        print("[ADC Worker Agent] Local Resource Guard active. Ready for training tasks.")
        print("[ADC Worker Agent] Press Ctrl+C to stop.\n")

        # Keep running and poll for training tasks
        try:
            while self._running:
                await self._poll_and_execute_tasks()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def _poll_and_execute_tasks(self) -> None:
        """Poll backend for assigned tasks, acknowledge, and execute training steps."""
        safe, reason = self.guard.check_safety()
        if not safe:
            return

        try:
            tasks = await self.client.get_assigned_tasks()
            if not tasks:
                return

            task = tasks[0]
            task_id = str(task["id"])
            project_id = str(task.get("projectId", ""))
            lease_token = task.get("leaseToken")
            step_start = task.get("stepStart", 0)
            step_end = task.get("stepEnd", step_start + 50)
            pkg_url = task.get("packageDownloadUrl")
            ds_url = task.get("datasetDownloadUrl")

            print(f"[ADC Worker Agent] Received task {task_id} (steps {step_start}..{step_end})")

            # Acknowledge task assignment
            if lease_token:
                await self.client.acknowledge_task(task_id, lease_token)

            # Ensure local artifact downloads
            proj_cache = self.cache_dir / project_id
            proj_cache.mkdir(parents=True, exist_ok=True)
            pkg_path = proj_cache / "package.zip"
            ds_path = proj_cache / "dataset.zip"

            if pkg_url and not pkg_path.exists():
                await self.client.download_file(pkg_url, pkg_path)
            if ds_url and not ds_path.exists():
                await self.client.download_file(ds_url, ds_path)

            if pkg_path.exists() and ds_path.exists():
                # Define real-time telemetry callback
                async def on_metric(metric: TrainingTelemetry) -> None:
                    telemetry = self._get_telemetry()
                    cpu_util = telemetry.get("cpu", {}).get("percent", 15.0)
                    mem_used_gb = telemetry.get("memory", {}).get("usedGb", 2.0)
                    gpu_list = telemetry.get("gpus", [])
                    gpu_util = gpu_list[0].get("utilizationGpu", 0.0) if gpu_list else 0.0

                    await self.client.report_task_metrics(
                        task_id=task_id,
                        step=metric.step,
                        loss=metric.loss if metric.loss is not None else 0.0,
                        speed=metric.speed if metric.speed is not None else 0.0,
                        cluster_cpu_util=cpu_util,
                        cluster_gpu_util=gpu_util,
                        ram_util_gb=mem_used_gb,
                    )

                # Check if a previous checkpoint exists to resume from
                resume_ckpt_path = None
                try:
                    latest_ckpt = await self.client.get_latest_checkpoint(project_id)
                    if latest_ckpt and latest_ckpt.get("step", 0) > 0 and latest_ckpt.get("downloadUrl"):
                        ckpt_file = proj_cache / f"resume_step_{latest_ckpt['step']}.pt"
                        if not ckpt_file.exists():
                            await self.client.download_file(latest_ckpt["downloadUrl"], ckpt_file)
                        resume_ckpt_path = ckpt_file
                except Exception as ckpt_err:
                    logger.debug("checkpoint_check_skipped", error=str(ckpt_err))

                # Query distributed rendezvous and rank assignments
                extra_env: Dict[str, str] = {}
                try:
                    rendezvous = await self.client.get_distributed_rendezvous(project_id)
                    if rendezvous:
                        extra_env["ADC_STRATEGY"] = str(rendezvous.get("strategy", "single_node"))
                        extra_env["RANK"] = str(rendezvous.get("rank", 0))
                        extra_env["WORLD_SIZE"] = str(rendezvous.get("worldSize", 1))
                        extra_env["MASTER_ADDR"] = str(rendezvous.get("masterAddr", "127.0.0.1"))
                        extra_env["MASTER_PORT"] = str(rendezvous.get("masterPort", 29500))
                        extra_env["ADC_RUN_ID"] = str(rendezvous.get("runId", ""))
                        relay_path = rendezvous.get("relaySyncUrl", "")
                        if relay_path:
                            extra_env["ADC_RELAY_URL"] = f"{self.client.base_url}{relay_path}"
                        extra_env["ADC_INSTALLATION_ID"] = self.client.identity.installation_id
                except Exception as r_err:
                    logger.debug("rendezvous_query_skipped", error=str(r_err))

                config = TaskExecutionConfig(
                    task_id=task_id,
                    project_id=project_id,
                    package_path=pkg_path,
                    dataset_path=ds_path,
                    step_start=step_start,
                    step_end=step_end,
                    resume_checkpoint_path=resume_ckpt_path,
                    extra_env=extra_env,
                )

                result = await self.executor.execute(config, on_metric=on_metric)

                if result.success:
                    # Upload any generated checkpoints
                    for ckpt in result.checkpoints:
                        try:
                            await self.client.upload_checkpoint(
                                project_id=project_id,
                                step=result.steps_completed,
                                checkpoint_path=ckpt,
                                metrics={"loss": result.last_loss},
                            )
                            print(f"[ADC Worker Agent] Published checkpoint: {Path(ckpt).name}")
                        except Exception as up_err:
                            logger.warning("checkpoint_publish_failed", error=str(up_err))

                    await self.client.update_task_status(
                        task_id=task_id,
                        status="completed",
                        result_summary=f"Processed steps {step_start} through {result.steps_completed}.",
                    )
                    print(f"[ADC Worker Agent] Successfully completed task {task_id}.")
                else:
                    await self.client.update_task_status(
                        task_id=task_id,
                        status="failed",
                        error_details=result.error_message,
                    )
                    print(f"[ADC Worker Agent] Task {task_id} failed: {result.error_message}")

        except Exception as exc:
            logger.warning("worker_task_execution_error", error=str(exc))

    def _get_worker_status(self) -> str:
        """Evaluate local ResourceGuard before reporting heartbeat status."""
        safe, reason = self.guard.check_safety()
        if not safe:
            logger.warning("worker_resource_guard_active", reason=reason)
            return "paused"
        return "idle"

    def _get_telemetry(self) -> dict:
        """Capture real hardware resource telemetry snapshot."""
        return HardwareDetector.get_telemetry_snapshot()

    async def shutdown(self) -> None:
        """Gracefully release lease, cancel executor, and close connection."""
        print("\n[ADC Worker Agent] Shutting down...")
        self._running = False
        await self.executor.cancel()
        if self.lease_manager:
            await self.lease_manager.stop()
        await self.client.close()
        print("[ADC Worker Agent] Stopped.")


def main() -> None:
    """CLI entrypoint for adc-worker."""
    backend_url = os.environ.get("ADC_BACKEND_URL", "http://localhost:8000")
    agent = WorkerAgent(backend_url=backend_url)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal():
        loop.create_task(agent.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        loop.run_until_complete(agent.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
