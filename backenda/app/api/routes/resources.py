"""
Hardware resource telemetry, contribution budgets, and cluster capacity endpoints.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.common.hardware import HardwareDetector, detect_gpus
from app.api.dependencies import get_current_active_user, get_db_session
from app.core.audit import record_audit_event
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.machine import Machine
from app.models.resource import MachineContributionSettings, WorkerResourceSnapshot
from app.models.user import User
from app.schemas.resource import (
    ClusterCapacitySummary,
    ContributionSettingsResponse,
    ContributionSettingsUpdate,
    HardwareProfileResponse,
    PauseResumeResponse,
    UserResourcesResponse,
)

logger = get_logger("adc.resources.api")

router = APIRouter(prefix="/resources", tags=["Resources"])


async def _get_or_create_settings(
    db: AsyncSession,
    user_id: Any,
    machine_id: Any,
) -> MachineContributionSettings:
    """Fetch existing contribution settings for a machine or initialize defaults."""
    stmt = select(MachineContributionSettings).where(
        MachineContributionSettings.machine_id == machine_id
    )
    result = await db.execute(stmt)
    settings = result.scalars().first()

    if not settings:
        cpu_info = HardwareDetector.get_cpu_info()
        ram_info = HardwareDetector.get_ram_info()
        default_cores = max(1, min(4, cpu_info["cores_logical"]))
        default_ram = max(1.0, min(8.0, round(ram_info["total_gb"] / 2.0, 1)))

        settings = MachineContributionSettings(
            machine_id=machine_id,
            user_id=user_id,
            cpu_enabled=True,
            cpu_cores=default_cores,
            ram_budget_gb=default_ram,
            gpu_enabled=False,
            selected_gpu="",
            storage_budget_gb=20.0,
            network_preference="unlimited",
            global_paused=False,
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


@router.get(
    "/me",
    response_model=UserResourcesResponse,
    summary="Get hardware profile and current contribution settings",
)
async def get_my_resources(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
) -> UserResourcesResponse:
    """
    Retrieve hardware capability profile, volunteer contribution budgets,
    available GPUs, and aggregate cluster capacity.
    """
    # 1. Locate paired machine for current user
    machine: Optional[Machine] = None
    if x_installation_id:
        stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        machine = (await db.execute(stmt)).scalars().first()

    if not machine:
        stmt = (
            select(Machine)
            .where(Machine.paired_user_id == current_user.id)
            .order_by(Machine.updated_at.desc())
        )
        machine = (await db.execute(stmt)).scalars().first()

    # 2. Build hardware profile
    if machine:
        latest_snap_stmt = (
            select(WorkerResourceSnapshot)
            .where(WorkerResourceSnapshot.machine_id == machine.id)
            .order_by(WorkerResourceSnapshot.timestamp.desc())
            .limit(1)
        )
        snap = (await db.execute(latest_snap_stmt)).scalars().first()
        if snap:
            hw_profile = HardwareProfileResponse(
                cpu_model=snap.cpu_model,
                cpu_cores=snap.cpu_cores_total,
                ram_total_gb=snap.ram_total_gb,
                ram_available_gb=snap.ram_available_gb,
                gpu_model=snap.gpu_model,
                gpu_memory_total_gb=snap.gpu_memory_total_gb,
                disk_space_available_gb=snap.disk_available_gb,
            )
        else:
            profile_dict = HardwareDetector.get_hardware_profile()
            hw_profile = HardwareProfileResponse(**profile_dict)
    else:
        profile_dict = HardwareDetector.get_hardware_profile()
        hw_profile = HardwareProfileResponse(**profile_dict)

    # 3. Retrieve or build contribution settings
    if machine:
        settings_orm = await _get_or_create_settings(db, current_user.id, machine.id)
        contribution_settings = ContributionSettingsResponse(
            cpu_enabled=settings_orm.cpu_enabled,
            cpu_cores=settings_orm.cpu_cores,
            ram_budget_gb=settings_orm.ram_budget_gb,
            gpu_enabled=settings_orm.gpu_enabled,
            selected_gpu=settings_orm.selected_gpu,
            storage_budget_gb=settings_orm.storage_budget_gb,
            network_preference=settings_orm.network_preference,
            global_paused=settings_orm.global_paused,
        )
    else:
        contribution_settings = ContributionSettingsResponse(
            cpu_enabled=True,
            cpu_cores=min(2, hw_profile.cpu_cores),
            ram_budget_gb=min(4.0, hw_profile.ram_total_gb),
            gpu_enabled=False,
            selected_gpu="",
            storage_budget_gb=20.0,
            network_preference="unlimited",
            global_paused=False,
        )

    # 4. Enumerate available GPUs on host
    gpu_data = detect_gpus()
    available_gpus: List[str] = []
    if gpu_data.get("has_gpu"):
        devices = gpu_data.get("devices", [])
        if devices:
            for dev in devices:
                available_gpus.append(f"{dev['name']} ({dev['total_memory_gb']} GB)")
        else:
            available_gpus.append(
                f"{gpu_data['primary_model']} ({gpu_data['total_vram_gb']} GB)"
            )

    # 5. Calculate cluster aggregate capacity
    workers_stmt = select(Machine).where(
        Machine.active_role == "worker",
        Machine.status.in_(["idle", "training", "paused"]),
    )
    active_workers = (await db.execute(workers_stmt)).scalars().all()
    active_worker_ids = [w.id for w in active_workers]

    total_cpu_cores = 0
    total_ram_gb = 0.0
    total_storage_gb = 0.0

    if active_worker_ids:
        sets_stmt = select(MachineContributionSettings).where(
            MachineContributionSettings.machine_id.in_(active_worker_ids)
        )
        worker_settings = (await db.execute(sets_stmt)).scalars().all()
        for ws in worker_settings:
            if not ws.global_paused:
                if ws.cpu_enabled:
                    total_cpu_cores += ws.cpu_cores
                total_ram_gb += ws.ram_budget_gb
                total_storage_gb += ws.storage_budget_gb

    cluster_summary = ClusterCapacitySummary(
        active_workers_count=len(active_workers),
        total_contributed_cpu_cores=total_cpu_cores,
        total_contributed_ram_gb=round(total_ram_gb, 2),
        total_contributed_storage_gb=round(total_storage_gb, 2),
    )

    return UserResourcesResponse(
        hardware_profile=hw_profile,
        contribution_settings=contribution_settings,
        available_gpus=available_gpus,
        cluster_summary=cluster_summary,
    )


@router.patch(
    "/me",
    response_model=ContributionSettingsResponse,
    summary="Update contribution settings and resource budgets",
)
async def update_my_resources(
    payload: ContributionSettingsUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
) -> ContributionSettingsResponse:
    """
    Update volunteer compute budgets with physical hardware limit validation.
    """
    cpu_info = HardwareDetector.get_cpu_info()
    ram_info = HardwareDetector.get_ram_info()
    disk_info = HardwareDetector.get_disk_info()
    gpu_data = detect_gpus()

    # 1. Physical limit enforcement
    if payload.cpu_cores is not None and payload.cpu_cores > cpu_info["cores_logical"]:
        raise ValidationError(
            f"Cannot allocate {payload.cpu_cores} CPU cores: "
            f"System has only {cpu_info['cores_logical']} logical cores available."
        )

    if payload.ram_budget_gb is not None and payload.ram_budget_gb > ram_info["total_gb"]:
        raise ValidationError(
            f"Cannot allocate {payload.ram_budget_gb} GB RAM: "
            f"System has only {ram_info['total_gb']} GB total physical memory."
        )

    if payload.storage_budget_gb is not None and payload.storage_budget_gb > disk_info["total_gb"]:
        raise ValidationError(
            f"Cannot allocate {payload.storage_budget_gb} GB storage: "
            f"Local disk total capacity is only {disk_info['total_gb']} GB."
        )

    if payload.gpu_enabled is True and not gpu_data.get("has_gpu"):
        raise ValidationError(
            "Cannot enable GPU contribution: No supported GPU or CUDA device detected on host."
        )

    # 2. Find target machine(s) for user
    machines: List[Machine] = []
    if x_installation_id:
        stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        m = (await db.execute(stmt)).scalars().first()
        if m:
            machines.append(m)

    if not machines:
        stmt = select(Machine).where(Machine.paired_user_id == current_user.id)
        machines = list((await db.execute(stmt)).scalars().all())

    # If no machine paired yet, return simulated response confirming valid settings
    if not machines:
        return ContributionSettingsResponse(
            cpu_enabled=payload.cpu_enabled if payload.cpu_enabled is not None else True,
            cpu_cores=payload.cpu_cores if payload.cpu_cores is not None else 2,
            ram_budget_gb=payload.ram_budget_gb if payload.ram_budget_gb is not None else 4.0,
            gpu_enabled=payload.gpu_enabled if payload.gpu_enabled is not None else False,
            selected_gpu=payload.selected_gpu if payload.selected_gpu is not None else "",
            storage_budget_gb=payload.storage_budget_gb if payload.storage_budget_gb is not None else 20.0,
            network_preference=payload.network_preference if payload.network_preference is not None else "unlimited",
            global_paused=payload.global_paused if payload.global_paused is not None else False,
        )

    # Update settings across user's paired machines
    updated_settings: Optional[MachineContributionSettings] = None
    for m in machines:
        settings_orm = await _get_or_create_settings(db, current_user.id, m.id)

        if payload.cpu_enabled is not None:
            settings_orm.cpu_enabled = payload.cpu_enabled
        if payload.cpu_cores is not None:
            settings_orm.cpu_cores = payload.cpu_cores
        if payload.ram_budget_gb is not None:
            settings_orm.ram_budget_gb = payload.ram_budget_gb
        if payload.gpu_enabled is not None:
            settings_orm.gpu_enabled = payload.gpu_enabled
        if payload.selected_gpu is not None:
            settings_orm.selected_gpu = payload.selected_gpu
        if payload.storage_budget_gb is not None:
            settings_orm.storage_budget_gb = payload.storage_budget_gb
        if payload.network_preference is not None:
            settings_orm.network_preference = payload.network_preference
        if payload.global_paused is not None:
            settings_orm.global_paused = payload.global_paused

        updated_settings = settings_orm

    await db.commit()
    if updated_settings:
        await db.refresh(updated_settings)

    await record_audit_event(
        db,
        action="resource.update_contribution_settings",
        user_id=current_user.id,
        details=payload.model_dump(exclude_none=True),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    assert updated_settings is not None
    return ContributionSettingsResponse(
        cpu_enabled=updated_settings.cpu_enabled,
        cpu_cores=updated_settings.cpu_cores,
        ram_budget_gb=updated_settings.ram_budget_gb,
        gpu_enabled=updated_settings.gpu_enabled,
        selected_gpu=updated_settings.selected_gpu,
        storage_budget_gb=updated_settings.storage_budget_gb,
        network_preference=updated_settings.network_preference,
        global_paused=updated_settings.global_paused,
    )


@router.post(
    "/me/pause-all",
    response_model=PauseResumeResponse,
    summary="Pause all volunteer compute contributions globally",
)
async def pause_all_contributions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> PauseResumeResponse:
    """
    Immediately sets global pause across all compute contributions.
    """
    # 1. Update all contribution settings for user
    stmt = (
        update(MachineContributionSettings)
        .where(MachineContributionSettings.user_id == current_user.id)
        .values(global_paused=True)
    )
    result = await db.execute(stmt)
    affected_settings = result.rowcount

    # 2. Set machine status to paused if idle or training
    m_stmt = (
        update(Machine)
        .where(
            Machine.paired_user_id == current_user.id,
            Machine.active_role == "worker",
            Machine.status.in_(["idle", "training"]),
        )
        .values(status="paused")
    )
    m_result = await db.execute(m_stmt)
    affected_machines = m_result.rowcount

    await record_audit_event(
        db,
        action="resource.pause_all_contributions",
        user_id=current_user.id,
        details={"global_paused": True, "affected_machines": affected_machines},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    logger.info(
        "global_pause_activated",
        user_id=str(current_user.id),
        affected_machines=affected_machines,
    )

    return PauseResumeResponse(
        global_paused=True,
        message="All computing resource contributions have been paused across all projects.",
        affected_machines=max(affected_machines, affected_settings),
    )


@router.post(
    "/me/resume-all",
    response_model=PauseResumeResponse,
    summary="Resume all volunteer compute contributions",
)
async def resume_all_contributions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> PauseResumeResponse:
    """
    Clears global pause flag to allow volunteer compute participation.
    """
    stmt = (
        update(MachineContributionSettings)
        .where(MachineContributionSettings.user_id == current_user.id)
        .values(global_paused=False)
    )
    result = await db.execute(stmt)
    affected_settings = result.rowcount

    # Return paused machines back to idle
    m_stmt = (
        update(Machine)
        .where(
            Machine.paired_user_id == current_user.id,
            Machine.active_role == "worker",
            Machine.status == "paused",
        )
        .values(status="idle")
    )
    m_result = await db.execute(m_stmt)
    affected_machines = m_result.rowcount

    await record_audit_event(
        db,
        action="resource.resume_all_contributions",
        user_id=current_user.id,
        details={"global_paused": False, "affected_machines": affected_machines},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    logger.info(
        "global_pause_resumed",
        user_id=str(current_user.id),
        affected_machines=affected_machines,
    )

    return PauseResumeResponse(
        global_paused=False,
        message="Computing resource contributions resumed.",
        affected_machines=max(affected_machines, affected_settings),
    )
