"""
REST API endpoints for Project Checkpoint upload, listing, downloading, and training resumption.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db_session, get_optional_current_user
from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.machine import Machine
from app.models.project import Project, ProjectMembership
from app.models.training import Checkpoint, TrainingRun
from app.models.user import User
from app.schemas.checkpoint import (
    CheckpointListResponse,
    CheckpointResponse,
    ResumeCheckpointRequest,
    ResumeCheckpointResponse,
)
from app.services.checkpoint import checkpoint_service

logger = get_logger("adc.checkpoints.api")

router = APIRouter(prefix="/projects/{project_id}/checkpoints", tags=["Checkpoints"])


async def _resolve_user_or_machine(
    db: AsyncSession,
    current_user: Optional[User],
    x_installation_id: Optional[str],
) -> Tuple[Optional[User], Optional[Machine]]:
    """Authenticate either via bearer user token or volunteer machine installation header."""
    if current_user:
        return current_user, None

    if x_installation_id:
        stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        machine = (await db.execute(stmt)).scalars().first()
        if machine:
            return None, machine

    raise AuthenticationError("Authentication required (Bearer token or X-Installation-Id header).")


def _build_checkpoint_response(ckpt: Checkpoint) -> CheckpointResponse:
    """Serialize Checkpoint ORM model into API schema."""
    metrics_data = None
    if ckpt.metrics_json:
        try:
            metrics_data = json.loads(ckpt.metrics_json)
        except Exception:
            pass

    return CheckpointResponse(
        id=ckpt.id,
        project_id=ckpt.project_id,
        run_id=ckpt.run_id,
        step=ckpt.step,
        file_size_bytes=ckpt.file_size_bytes,
        checksum_sha256=ckpt.checksum_sha256,
        is_validated=ckpt.is_validated,
        metrics=metrics_data,
        created_at=ckpt.created_at if ckpt.created_at is not None else datetime.now(timezone.utc),
        download_url=f"/api/v1/projects/{ckpt.project_id}/checkpoints/{ckpt.id}/download",
    )


@router.post(
    "",
    response_model=CheckpointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a training model checkpoint",
)
async def upload_checkpoint(
    project_id: uuid.UUID,
    step: int = Form(..., ge=0),
    file: UploadFile = File(...),
    run_id: Optional[uuid.UUID] = Form(None),
    metrics_json: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
) -> CheckpointResponse:
    """
    Stream upload a PyTorch model checkpoint (.pt/.safetensors), calculate SHA-256,
    verify format integrity, and publish atomically.
    """
    user, machine = await _resolve_user_or_machine(db, current_user, x_installation_id)

    # 1. Resolve run_id if not supplied
    target_run_id = run_id
    if not target_run_id:
        r_stmt = (
            select(TrainingRun)
            .where(TrainingRun.project_id == project_id)
            .order_by(TrainingRun.created_at.desc())
            .limit(1)
        )
        run = (await db.execute(r_stmt)).scalars().first()
        if not run:
            run = TrainingRun(
                project_id=project_id,
                run_number=1,
                status="running",
                current_step=step,
                total_steps=1000,
            )
            db.add(run)
            await db.flush()
        target_run_id = run.id

    # 2. Parse metrics dict if present
    metrics_dict = None
    if metrics_json:
        try:
            metrics_dict = json.loads(metrics_json)
        except Exception:
            pass

    # 3. Stream upload and validate checkpoint
    async def file_stream_generator():
        while True:
            chunk = await file.read(65536)
            if not chunk:
                break
            yield chunk

    filename = file.filename or "checkpoint.pt"
    checkpoint = await checkpoint_service.save_and_validate_checkpoint(
        db=db,
        project_id=project_id,
        run_id=target_run_id,
        step=step,
        file_stream=file_stream_generator(),
        filename=filename,
        metrics_dict=metrics_dict,
    )
    await db.commit()
    await db.refresh(checkpoint)

    return _build_checkpoint_response(checkpoint)


@router.get(
    "",
    response_model=CheckpointListResponse,
    summary="List all checkpoints for project",
)
async def list_checkpoints(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CheckpointListResponse:
    """Return all checkpoints ordered by step descending."""
    checkpoints = await checkpoint_service.get_checkpoints(db, project_id)
    return CheckpointListResponse(
        total=len(checkpoints),
        checkpoints=[_build_checkpoint_response(c) for c in checkpoints],
    )


@router.get(
    "/latest",
    response_model=CheckpointResponse,
    summary="Retrieve the latest validated checkpoint",
)
async def get_latest_checkpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CheckpointResponse:
    """Return latest checkpoint to resume training or inspect model weights."""
    checkpoint = await checkpoint_service.get_latest_checkpoint(db, project_id)
    if not checkpoint:
        raise NotFoundError("No validated checkpoints found for this project.")
    return _build_checkpoint_response(checkpoint)


@router.get(
    "/{checkpoint_id}/download",
    summary="Download checkpoint weights file stream",
)
async def download_checkpoint(
    project_id: uuid.UUID,
    checkpoint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Stream download checkpoint binary file."""
    stmt = select(Checkpoint).where(
        Checkpoint.id == checkpoint_id,
        Checkpoint.project_id == project_id,
    )
    checkpoint = (await db.execute(stmt)).scalar_one_or_none()
    if not checkpoint:
        raise NotFoundError("Checkpoint not found.")

    file_path = Path(checkpoint.file_path)
    if not file_path.is_file():
        raise NotFoundError("Checkpoint file not found on disk.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.post(
    "/{checkpoint_id}/resume",
    response_model=ResumeCheckpointResponse,
    summary="Resume training project from a validated checkpoint",
)
async def resume_checkpoint(
    project_id: uuid.UUID,
    checkpoint_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> ResumeCheckpointResponse:
    """Restore project training run current_step and state to specified checkpoint."""
    # Check ownership
    p_stmt = select(Project).where(Project.id == project_id)
    project = (await db.execute(p_stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundError("Project not found.")
    if project.owner_id != current_user.id:
        raise AuthorizationError("Only the project owner can trigger training resumption.")

    pid, resumed_step, cid = await checkpoint_service.resume_from_checkpoint(
        db=db,
        project_id=project_id,
        checkpoint_id=checkpoint_id,
    )
    await db.commit()

    return ResumeCheckpointResponse(
        project_id=pid,
        resumed_step=resumed_step,
        checkpoint_id=cid,
        status="resumed",
    )
