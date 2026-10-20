"""
REST API routes for Agent task polling, lease acknowledgements, status updates, and metrics reporting.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.state_machine import TaskState
from app.models.dataset import Dataset, ModelPackage
from app.models.machine import Machine
from app.models.project import Project, ProjectMembership
from app.models.training import TrainingTask
from app.schemas.task import (
    TaskAcknowledgeRequest,
    TaskMetricReportRequest,
    TaskMetricResponse,
    TaskResponse,
    TaskStatusUpdateRequest,
)
from app.services.scheduler import scheduler

logger = get_logger("adc.agent_tasks.api")

router = APIRouter(prefix="/agent/tasks", tags=["Agent Tasks"])


async def _resolve_machine(
    db: AsyncSession,
    installation_id: str,
) -> Machine:
    """Resolve and authenticate machine node via installation ID header."""
    stmt = select(Machine).where(Machine.installation_id == installation_id)
    machine = (await db.execute(stmt)).scalars().first()
    if not machine:
        raise AuthenticationError("Unrecognized or unregistered machine installation ID.")
    return machine


def _build_task_response(task: TrainingTask) -> TaskResponse:
    """Format TrainingTask ORM into TaskResponse with download URLs."""
    ds_url = f"/api/v1/projects/{task.project_id}/datasets"
    pkg_url = f"/api/v1/projects/{task.project_id}/packages"

    return TaskResponse(
        id=task.id,
        run_id=task.run_id,
        project_id=task.project_id,
        task_type=task.task_type,
        step_start=task.step_start,
        step_end=task.step_end,
        status=task.status,
        lease_token=task.lease_token,
        lease_expires_at=task.lease_expires_at,
        dataset_download_url=ds_url,
        package_download_url=pkg_url,
    )


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="Worker polls for assigned or available training tasks",
)
async def get_agent_tasks(
    project_id: Optional[uuid.UUID] = Query(None),
    x_installation_id: str = Header(..., alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> List[TaskResponse]:
    """
    Worker node queries tasks assigned to its installation ID.
    Triggers automated scheduling if no active tasks are currently assigned.
    """
    machine = await _resolve_machine(db, x_installation_id)

    # 1. Clean up any stale expired leases across the cluster
    await scheduler.reclaim_expired_leases(db)

    # 2. Query tasks currently assigned to this machine
    stmt = (
        select(TrainingTask)
        .where(
            TrainingTask.assigned_machine_id == machine.id,
            TrainingTask.status.in_([TaskState.ASSIGNED.value, TaskState.IN_PROGRESS.value]),
        )
        .order_by(desc(TrainingTask.created_at))
    )
    active_tasks = list((await db.execute(stmt)).scalars().all())

    # 3. If no active task and project_id supplied, attempt to dispatch next slice
    if not active_tasks:
        target_pid = project_id
        if not target_pid:
            # Check projects where this machine has an active membership
            mem_stmt = (
                select(ProjectMembership.project_id)
                .where(
                    ProjectMembership.machine_id == machine.id,
                    ProjectMembership.contribution_status == "active",
                )
                .limit(1)
            )
            target_pid = (await db.execute(mem_stmt)).scalars().first()

        if target_pid:
            new_task = await scheduler.dispatch_next_task(
                db,
                target_pid,
                preferred_machine_id=machine.id,
            )
            if new_task and new_task.assigned_machine_id == machine.id:
                active_tasks.append(new_task)
            await db.commit()

    return [_build_task_response(t) for t in active_tasks]


@router.post(
    "/{task_id}/acknowledge",
    response_model=TaskResponse,
    summary="Worker acknowledges task assignment and starts execution lease",
)
async def acknowledge_task(
    task_id: uuid.UUID,
    payload: TaskAcknowledgeRequest,
    x_installation_id: str = Header(..., alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """Acknowledge task receipt, renew execution lease, and mark in_progress."""
    machine = await _resolve_machine(db, x_installation_id)
    task = await scheduler.acknowledge_task(
        db=db,
        task_id=task_id,
        machine_id=machine.id,
        lease_token=payload.lease_token,
    )
    await db.commit()
    await db.refresh(task)
    return _build_task_response(task)


@router.post(
    "/{task_id}/status",
    response_model=TaskResponse,
    summary="Worker reports task execution status",
)
async def update_task_status(
    task_id: uuid.UUID,
    payload: TaskStatusUpdateRequest,
    x_installation_id: str = Header(..., alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """Worker reports running, paused, completed, or failed state."""
    machine = await _resolve_machine(db, x_installation_id)

    if payload.status == "completed":
        task = await scheduler.complete_task(
            db=db,
            task_id=task_id,
            machine_id=machine.id,
            result_summary=payload.result_summary,
        )
    else:
        stmt = select(TrainingTask).where(TrainingTask.id == task_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if not task:
            raise NotFoundError("Task not found.")

        if task.assigned_machine_id != machine.id:
            raise ConflictError("Task is not assigned to this machine.")

        if payload.status == "failed":
            task.status = TaskState.FAILED.value
            task.error_details = payload.error_details
        elif payload.status == "paused":
            task.status = TaskState.PAUSED.value
        elif payload.status in ["running", "in_progress"]:
            task.status = TaskState.IN_PROGRESS.value

    await db.commit()
    await db.refresh(task)
    return _build_task_response(task)


@router.post(
    "/{task_id}/metrics",
    response_model=TaskMetricResponse,
    summary="Worker reports step telemetry metric point",
)
async def report_task_metrics(
    task_id: uuid.UUID,
    payload: TaskMetricReportRequest,
    x_installation_id: str = Header(..., alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> TaskMetricResponse:
    """Record training step loss and speed, updating project progress in real time."""
    machine = await _resolve_machine(db, x_installation_id)

    metric = await scheduler.record_task_progress(
        db=db,
        task_id=task_id,
        machine_id=machine.id,
        current_step=payload.step,
        loss=payload.loss,
        speed=payload.speed,
        cluster_cpu_util=payload.cluster_cpu_util,
        cluster_gpu_util=payload.cluster_gpu_util,
        ram_util_gb=payload.ram_util_gb,
    )
    await db.commit()

    return TaskMetricResponse(
        recorded=True,
        step=metric.step,
        loss=metric.loss,
    )
