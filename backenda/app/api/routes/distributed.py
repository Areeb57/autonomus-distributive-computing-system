"""
REST API endpoints for Distributed Training Strategies, Rendezvous, and Synchronous Parameter Relay (Phase 9).
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import torch
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db_session, get_optional_current_user
from app.core.exceptions import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.machine import Machine
from app.models.project import Project, ProjectMembership
from app.models.training import TrainingConfiguration, TrainingRun
from app.models.user import User
from app.schemas.distributed import (
    DistributedHeartbeatRequest,
    DistributedHeartbeatResponse,
    DistributedStatusResponse,
    RendezvousRequest,
    RendezvousResponse,
    StrategyInfoResponse,
    StrategyListResponse,
)
from app.training.strategies.registry import strategy_registry
from app.training.strategies.relay import relay_aggregator

logger = get_logger("adc.distributed.api")

router = APIRouter(prefix="/projects/{project_id}/distributed", tags=["Distributed Training"])


async def _resolve_worker_or_user(
    db: AsyncSession,
    current_user: Optional[User],
    x_installation_id: Optional[str],
) -> Tuple[Optional[User], Optional[Machine]]:
    """Authenticate either via bearer user token or worker machine installation ID."""
    if current_user:
        return current_user, None

    if x_installation_id:
        stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        machine = (await db.execute(stmt)).scalars().first()
        if machine:
            return None, machine

    raise AuthenticationError("Authentication required (Bearer token or X-Installation-Id header).")


@router.get(
    "/strategies",
    response_model=StrategyListResponse,
    summary="List available distributed execution strategies and network requirements",
)
async def list_strategies(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> StrategyListResponse:
    """Return all registered training strategies with explicit network, firewall, and NAT specifications."""
    strategies = strategy_registry.list_all()
    results = [
        StrategyInfoResponse(
            name=s.name,
            description=s.description,
            network_requirements=s.get_network_requirements(),
        )
        for s in strategies
    ]
    return StrategyListResponse(total=len(results), strategies=results)


@router.post(
    "/rendezvous",
    response_model=RendezvousResponse,
    summary="Obtain distributed rank assignment and rendezvous parameters",
)
async def coordinate_rendezvous(
    project_id: uuid.UUID,
    payload: Optional[RendezvousRequest] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> RendezvousResponse:
    """
    Assign node to a deterministic rank and return rendezvous coordination parameters.
    """
    user, machine = await _resolve_worker_or_user(db, current_user, x_installation_id)

    # 1. Resolve project and verify existence
    p_stmt = select(Project).where(Project.id == project_id)
    project = (await db.execute(p_stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError(f"Project '{project_id}' not found.")

    # 2. Resolve active run
    target_run_id = payload.run_id if payload and payload.run_id else None
    if not target_run_id:
        r_stmt = (
            select(TrainingRun)
            .where(
                TrainingRun.project_id == project_id,
                TrainingRun.status.in_(["pending", "running"]),
            )
            .order_by(desc(TrainingRun.created_at))
            .limit(1)
        )
        run = (await db.execute(r_stmt)).scalars().first()
        if not run:
            run = TrainingRun(
                project_id=project_id,
                run_number=1,
                status="running",
                current_step=0,
                total_steps=1000,
            )
            db.add(run)
            await db.flush()
        target_run_id = run.id

    # 3. Check existing rendezvous for this run
    rendezvous = strategy_registry.get_rendezvous(target_run_id)

    # If no rendezvous created yet, create one
    if not rendezvous:
        # Query project memberships
        m_stmt = select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.status == "active",
        )
        members = (await db.execute(m_stmt)).scalars().all()
        if not members and user:
            # Fallback for local single node if no memberships yet
            dummy_mem = ProjectMembership(
                project_id=project_id,
                user_id=user.id,
                machine_id=user.id,
                status="active",
                contribution_status="active",
            )
            members = [dummy_mem]

        cfg_stmt = select(TrainingConfiguration).where(TrainingConfiguration.project_id == project_id)
        config = (await db.execute(cfg_stmt)).scalars().first()

        selected_strat = strategy_registry.select_strategy(project, config, members)
        rendezvous = strategy_registry.create_rendezvous(
            strategy_name=selected_strat.name,
            project_id=project_id,
            run_id=target_run_id,
            workers=members,
        )

    # 4. Find the caller's assigned rank
    caller_id = user.id if user else (machine.id if machine else None)
    assigned_rank = 0
    assigned_role = "worker"
    for r_num, assignment in rendezvous.ranks.items():
        if assignment.worker_id == caller_id or assignment.machine_id == caller_id:
            assigned_rank = r_num
            assigned_role = assignment.role
            break

    await db.commit()

    return RendezvousResponse(
        projectId=project_id,
        runId=target_run_id,
        strategy=rendezvous.strategy,
        backend=rendezvous.backend,
        rank=assigned_rank,
        worldSize=rendezvous.world_size,
        masterAddr=rendezvous.master_addr,
        masterPort=rendezvous.master_port,
        relaySyncUrl=f"/api/v1/projects/{project_id}/distributed/sync",
        isReady=rendezvous.is_ready,
        role=assigned_role,
    )


@router.post(
    "/sync",
    summary="Synchronize step model parameters or gradients across distributed ranks",
)
async def sync_step_parameters(
    project_id: uuid.UUID,
    run_id: uuid.UUID = Form(..., alias="run_id"),
    step: int = Form(..., ge=0),
    rank: int = Form(..., ge=0),
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """
    Synchronous AllReduce endpoint for distributed training over relay.
    Worker uploads local step tensors, blocks until all active ranks submit,
    and receives bit-identical averaged tensors.
    """
    await _resolve_worker_or_user(db, current_user, x_installation_id)

    rendezvous = strategy_registry.get_rendezvous(run_id)
    if not rendezvous:
        raise NotFoundError(f"No active rendezvous found for run '{run_id}'.")

    # Read uploaded weights
    raw_bytes = await file.read()
    if not raw_bytes:
        raise ValidationError("Uploaded parameter buffer is empty.")

    try:
        tensors = torch.load(io.BytesIO(raw_bytes), weights_only=True)
        if not isinstance(tensors, dict):
            raise ValidationError("Payload must be a dictionary of PyTorch tensors.")
    except Exception as exc:
        raise ValidationError(f"Invalid PyTorch tensor dictionary: {exc}")

    expected_ranks = set(rendezvous.ranks.keys())
    if not expected_ranks:
        expected_ranks = {0}

    # Execute synchronous barrier aggregation
    try:
        aggregated_bytes = await relay_aggregator.sync_step_tensors(
            run_id=run_id,
            step=step,
            rank=rank,
            expected_ranks=expected_ranks,
            tensors=tensors,
            timeout_seconds=45.0,
        )
    except Exception as exc:
        logger.error(f"Sync step error for run {run_id}, rank {rank}, step {step}: {exc}")
        raise

    return Response(
        content=aggregated_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="aggregated_step_{step}.pt"'},
    )


@router.post(
    "/heartbeat",
    response_model=DistributedHeartbeatResponse,
    summary="Heartbeat to confirm rank liveness",
)
async def distributed_heartbeat(
    project_id: uuid.UUID,
    payload: DistributedHeartbeatRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> DistributedHeartbeatResponse:
    """Report rank step progress and ensure rank liveness."""
    await _resolve_worker_or_user(db, current_user, x_installation_id)

    rendezvous = strategy_registry.get_rendezvous(payload.run_id)
    if not rendezvous:
        raise NotFoundError("Rendezvous not found.")

    assignment = rendezvous.ranks.get(payload.rank)
    if not assignment:
        raise NotFoundError(f"Rank {payload.rank} not found in active assignments.")

    assignment.last_heartbeat = datetime.now(timezone.utc)
    assignment.is_healthy = True

    active = [r for r, a in rendezvous.ranks.items() if a.is_healthy]
    return DistributedHeartbeatResponse(
        status="ok",
        isHealthy=True,
        activeRanks=active,
    )


@router.get(
    "/status",
    response_model=DistributedStatusResponse,
    summary="Query cluster rank allocation and rendezvous state",
)
async def get_distributed_status(
    project_id: uuid.UUID,
    run_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> DistributedStatusResponse:
    """Inspect active distributed world size, ranks, strategy, and readiness."""
    target_run_id = run_id
    if not target_run_id:
        r_stmt = (
            select(TrainingRun)
            .where(TrainingRun.project_id == project_id)
            .order_by(desc(TrainingRun.created_at))
            .limit(1)
        )
        run = (await db.execute(r_stmt)).scalars().first()
        if not run:
            raise NotFoundError("No training runs found for this project.")
        target_run_id = run.id

    rendezvous = strategy_registry.get_rendezvous(target_run_id)
    if not rendezvous:
        raise NotFoundError(f"No active distributed coordination found for run {target_run_id}.")

    return DistributedStatusResponse(
        projectId=project_id,
        runId=target_run_id,
        strategy=rendezvous.strategy,
        backend=rendezvous.backend,
        worldSize=rendezvous.world_size,
        ranks=rendezvous.ranks,
        isReady=rendezvous.is_ready,
    )
