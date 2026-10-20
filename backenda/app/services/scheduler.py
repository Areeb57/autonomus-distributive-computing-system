"""
Modular distributed training scheduler, worker eligibility evaluator, and task coordinator.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.state_machine import ProjectState, TaskState, WorkerState
from app.core.websocket import ws_hub
from app.models.machine import Machine
from app.models.project import Project, ProjectMembership
from app.models.resource import MachineContributionSettings, ResourceAllocation
from app.models.training import TrainingConfiguration, TrainingMetric, TrainingRun, TrainingTask

logger = get_logger("adc.scheduler")


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Helper ensuring naive datetimes (e.g. from SQLite) are localized to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class StrategySelector:
    """
    Deterministic rule-based training strategy selector (Section 15).
    Modular design allows future ML-based coordination extensions.
    """

    @classmethod
    def select_strategy(
        cls,
        project: Project,
        num_eligible_workers: int,
        total_cluster_vram_gb: float,
    ) -> str:
        """
        Evaluate cluster capacity and select best execution strategy.
        """
        if num_eligible_workers <= 1:
            return "single_node"

        # If project explicitly requested data parallel and multiple nodes are available
        if project.training_strategy in ["data_parallel", "ddp"]:
            return "data_parallel"

        # If model architecture is massive and cluster has high aggregate VRAM
        if "70b" in project.model_architecture.lower() or "large" in project.model_architecture.lower():
            if total_cluster_vram_gb >= 48.0:
                return "model_parallel"

        return "independent_jobs"


class WorkerEligibilityEvaluator:
    """Evaluates whether a worker machine qualifies to execute project tasks."""

    @classmethod
    def evaluate_worker(
        cls,
        machine: Machine,
        membership: ProjectMembership,
        settings: Optional[MachineContributionSettings],
        project: Project,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check connectivity, role, global pause, and resource thresholds.
        """
        # 1. Check machine status and role
        if machine.active_role != "worker":
            return False, f"Machine active role is '{machine.active_role}', expected 'worker'."

        if not machine.is_online and machine.status == "offline":
            return False, "Machine is offline."

        # 2. Check global contribution pause
        if settings and settings.global_paused:
            return False, "Machine has global contribution pause enabled."

        # 3. Check project membership status
        if membership.contribution_status != "active":
            return False, f"Membership contribution status is '{membership.contribution_status}'."

        if membership.status in ["paused", "offline", "stopped"]:
            return False, f"Worker membership status is '{membership.status}'."

        # 4. Check minimum resource requirements
        if membership.cpu_cores_contributed < project.min_cpu_cores:
            return False, f"Contributed cores ({membership.cpu_cores_contributed}) below project minimum ({project.min_cpu_cores})."

        if membership.ram_contributed_gb < project.min_ram_gb:
            return False, f"Contributed RAM ({membership.ram_contributed_gb} GB) below project minimum ({project.min_ram_gb} GB)."

        if project.gpu_recommended and not membership.gpu_enabled and project.min_vram_gb > 0:
            return False, f"Project requires GPU with at least {project.min_vram_gb} GB VRAM."

        return True, None


class TrainingScheduler:
    """
    Coordinates task dispatch, leases, heartbeats, and failure recovery.
    """

    def __init__(self, lease_duration_seconds: int = 120) -> None:
        self.lease_duration_seconds = lease_duration_seconds

    async def get_or_create_active_run(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> TrainingRun:
        """Locate active training run or initialize a new run for the project."""
        stmt = (
            select(TrainingRun)
            .where(
                TrainingRun.project_id == project_id,
                TrainingRun.status.in_(["pending", "running", "paused"]),
            )
            .order_by(desc(TrainingRun.created_at))
        )
        run = (await db.execute(stmt)).scalars().first()
        if not run:
            # Query project total steps from config
            cfg_stmt = select(TrainingConfiguration).where(TrainingConfiguration.project_id == project_id)
            cfg = (await db.execute(cfg_stmt)).scalars().first()
            total_steps = cfg.total_steps if cfg else 1000

            run = TrainingRun(
                project_id=project_id,
                run_number=1,
                status="running",
                current_step=0,
                total_steps=total_steps,
                start_time=datetime.now(timezone.utc),
            )
            db.add(run)
            await db.flush()
        return run

    async def get_eligible_workers(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> List[Tuple[Machine, ProjectMembership]]:
        """Identify all qualified, available worker nodes for project."""
        p_stmt = select(Project).where(Project.id == project_id)
        project = (await db.execute(p_stmt)).scalar_one_or_none()
        if not project:
            return []

        mem_stmt = (
            select(ProjectMembership)
            .options(selectinload(ProjectMembership.machine))
            .where(ProjectMembership.project_id == project_id)
        )
        memberships = (await db.execute(mem_stmt)).scalars().all()

        eligible: List[Tuple[Machine, ProjectMembership]] = []
        for mem in memberships:
            machine = mem.machine
            if not machine:
                continue

            sett_stmt = select(MachineContributionSettings).where(
                MachineContributionSettings.machine_id == machine.id
            )
            settings = (await db.execute(sett_stmt)).scalars().first()

            is_ok, reason = WorkerEligibilityEvaluator.evaluate_worker(
                machine=machine,
                membership=mem,
                settings=settings,
                project=project,
            )
            if is_ok:
                eligible.append((machine, mem))
            else:
                logger.debug("worker_ineligible", machine_id=str(machine.id), reason=reason)

        return eligible

    async def dispatch_next_task(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        preferred_machine_id: Optional[uuid.UUID] = None,
        step_batch_size: int = 50,
    ) -> Optional[TrainingTask]:
        """
        Allocate and assign the next pending training step batch to an eligible worker node.
        """
        if isinstance(project_id, str):
            project_id = uuid.UUID(project_id)
        if isinstance(preferred_machine_id, str):
            preferred_machine_id = uuid.UUID(preferred_machine_id)

        run = await self.get_or_create_active_run(db, project_id)

        # 1. Check if run is already completed
        if run.current_step >= run.total_steps:
            run.status = "completed"
            run.end_time = datetime.now(timezone.utc)
            await db.flush()
            return None

        # 2. Check for existing pending task or create next slice
        task_stmt = (
            select(TrainingTask)
            .where(
                TrainingTask.run_id == run.id,
                TrainingTask.status == TaskState.PENDING.value,
            )
            .order_by(TrainingTask.step_start)
        )
        task = (await db.execute(task_stmt)).scalars().first()

        if not task:
            # Query the highest step_end already scheduled for this run
            max_step_stmt = (
                select(TrainingTask.step_end)
                .where(TrainingTask.run_id == run.id)
                .order_by(desc(TrainingTask.step_end))
                .limit(1)
            )
            highest_step = (await db.execute(max_step_stmt)).scalar_one_or_none()
            step_start = highest_step if highest_step is not None else run.current_step
            step_end = min(run.total_steps, step_start + step_batch_size)
            if step_start >= step_end:
                return None

            task = TrainingTask(
                run_id=run.id,
                project_id=project_id,
                task_type="batch",
                step_start=step_start,
                step_end=step_end,
                status=TaskState.PENDING.value,
            )
            db.add(task)
            await db.flush()

        # 3. Find eligible worker nodes
        workers = await self.get_eligible_workers(db, project_id)
        if not workers:
            logger.info("no_eligible_workers_available", project_id=str(project_id))
            return None

        # 4. Pick preferred worker if eligible, otherwise first eligible worker
        chosen_machine, chosen_membership = workers[0]
        if preferred_machine_id:
            for m, mem in workers:
                if m.id == preferred_machine_id:
                    chosen_machine, chosen_membership = m, mem
                    break

        # Generate single-use lease token
        lease_token = f"task_lease_{secrets.token_hex(24)}"
        lease_expires = datetime.now(timezone.utc) + timedelta(seconds=self.lease_duration_seconds)

        task.assigned_machine_id = chosen_machine.id
        task.status = TaskState.ASSIGNED.value
        task.lease_token = lease_token
        task.lease_expires_at = lease_expires

        chosen_membership.status = "assigned"

        await db.flush()

        logger.info(
            "task_assigned_to_worker",
            task_id=str(task.id),
            machine_id=str(chosen_machine.id),
            step_start=task.step_start,
            step_end=task.step_end,
            lease_token=lease_token,
        )

        # 5. Notify agent via WebSocket if connected
        await ws_hub.send_agent_event(
            machine_id=chosen_machine.id,
            event="task_assignment",
            payload={
                "task_id": str(task.id),
                "project_id": str(project_id),
                "step_start": task.step_start,
                "step_end": task.step_end,
                "lease_token": lease_token,
                "lease_expires_at": lease_expires.isoformat(),
            },
        )

        return task

    async def acknowledge_task(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        machine_id: uuid.UUID,
        lease_token: str,
    ) -> TrainingTask:
        """
        Worker acknowledges receipt and confirms execution start.
        """
        stmt = select(TrainingTask).where(TrainingTask.id == task_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if not task:
            raise NotFoundError("Task not found.")

        if task.assigned_machine_id != machine_id:
            raise ConflictError("Task is not assigned to this machine.")

        if task.lease_token != lease_token:
            raise ConflictError("Invalid or expired task lease token.")

        # Renew lease and transition to in_progress
        task.status = TaskState.IN_PROGRESS.value
        task.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.lease_duration_seconds)

        # Update membership status
        mem_stmt = select(ProjectMembership).where(
            ProjectMembership.project_id == task.project_id,
            ProjectMembership.machine_id == machine_id,
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if mem:
            mem.status = "training"

        await db.flush()
        return task

    async def record_task_progress(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        machine_id: uuid.UUID,
        current_step: int,
        loss: float,
        speed: float = 0.0,
        cluster_cpu_util: float = 0.0,
        cluster_gpu_util: float = 0.0,
        ram_util_gb: float = 0.0,
    ) -> TrainingMetric:
        """Record step telemetry metric and advance run progress."""
        t_stmt = select(TrainingTask).where(TrainingTask.id == task_id)
        task = (await db.execute(t_stmt)).scalar_one_or_none()
        if not task:
            raise NotFoundError("Task not found.")

        # Save metric point
        metric = TrainingMetric(
            project_id=task.project_id,
            run_id=task.run_id,
            step=current_step,
            loss=loss,
            speed=speed,
            cluster_cpu_util=cluster_cpu_util,
            cluster_gpu_util=cluster_gpu_util,
            ram_util_gb=ram_util_gb,
        )
        db.add(metric)

        # Update run stats
        r_stmt = select(TrainingRun).where(TrainingRun.id == task.run_id)
        run = (await db.execute(r_stmt)).scalar_one_or_none()
        if run:
            run.current_step = max(run.current_step, current_step)
            run.current_loss = loss
            run.training_speed = speed

        # Update worker membership batch & step count
        mem_stmt = select(ProjectMembership).where(
            ProjectMembership.project_id == task.project_id,
            ProjectMembership.machine_id == machine_id,
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if mem:
            mem.steps_processed += 1
            mem.current_batch = current_step

        await db.flush()

        # Broadcast progress event to browser clients
        await ws_hub.broadcast_website_event(
            event="training_progress",
            entity_id=str(task.project_id),
            payload={
                "project_id": str(task.project_id),
                "current_step": current_step,
                "loss": loss,
                "speed": speed,
                "total_steps": run.total_steps if run else 1000,
            },
            project_id=task.project_id,
        )

        return metric

    async def complete_task(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        machine_id: uuid.UUID,
        result_summary: Optional[str] = None,
    ) -> TrainingTask:
        """Mark task as successfully completed."""
        stmt = select(TrainingTask).where(TrainingTask.id == task_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if not task:
            raise NotFoundError("Task not found.")

        task.status = TaskState.COMPLETED.value
        task.result_summary = result_summary or f"Steps {task.step_start} to {task.step_end} completed."
        task.lease_token = None

        # Advance run step
        r_stmt = select(TrainingRun).where(TrainingRun.id == task.run_id)
        run = (await db.execute(r_stmt)).scalar_one_or_none()
        if run:
            run.current_step = max(run.current_step, task.step_end)
            if run.current_step >= run.total_steps:
                run.status = "completed"
                run.end_time = datetime.now(timezone.utc)

        # Worker returns to idle
        mem_stmt = select(ProjectMembership).where(
            ProjectMembership.project_id == task.project_id,
            ProjectMembership.machine_id == machine_id,
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if mem:
            mem.status = "idle"

        await db.flush()
        return task

    async def reclaim_expired_leases(self, db: AsyncSession) -> int:
        """
        Failure & Recovery Manager: Reclaim tasks whose active leases have expired
        due to worker crash or disconnection.
        """
        now = datetime.now(timezone.utc)
        stmt = select(TrainingTask).where(
            TrainingTask.status.in_([TaskState.ASSIGNED.value, TaskState.IN_PROGRESS.value]),
            TrainingTask.lease_expires_at.is_not(None),
        )
        expired_candidates = (await db.execute(stmt)).scalars().all()
        reclaimed_count = 0

        for t in expired_candidates:
            exp = ensure_utc(t.lease_expires_at)
            if exp and exp < now:
                logger.warning(
                    "reclaiming_expired_task_lease",
                    task_id=str(t.id),
                    previous_machine=str(t.assigned_machine_id),
                    step_start=t.step_start,
                    step_end=t.step_end,
                )
                t.status = TaskState.PENDING.value
                t.assigned_machine_id = None
                t.lease_token = None
                t.lease_expires_at = None
                reclaimed_count += 1

        if reclaimed_count > 0:
            await db.flush()

        return reclaimed_count


# Global singleton scheduler instance
scheduler = TrainingScheduler()
