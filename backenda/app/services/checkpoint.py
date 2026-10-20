"""
Checkpoint management service: streaming storage, atomic publication, SHA-256, and PyTorch integrity validation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import torch
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.websocket import ws_hub
from app.models.project import Project
from app.models.training import Checkpoint, TrainingRun

logger = get_logger("adc.service.checkpoint")


def _ensure_uuid(val: uuid.UUID | str) -> uuid.UUID:
    """Normalize string or UUID instance to uuid.UUID."""
    if isinstance(val, str):
        return uuid.UUID(val)
    return val


class CheckpointService:
    """Coordinates checkpoint storage, integrity checks, and resumption."""

    @classmethod
    async def save_and_validate_checkpoint(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID | str,
        run_id: uuid.UUID | str,
        step: int,
        file_stream: AsyncIterator[bytes],
        filename: str = "model.pt",
        metrics_dict: Optional[Dict[str, Any]] = None,
    ) -> Checkpoint:
        """
        Stream upload checkpoint, calculate SHA-256, validate PyTorch weights_only,
        atomically publish, and persist record in database.
        """
        pid = _ensure_uuid(project_id)
        rid = _ensure_uuid(run_id)

        # 1. Verify project exists
        p_stmt = select(Project).where(Project.id == pid)
        project = (await db.execute(p_stmt)).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found.")

        # 2. Target storage paths
        settings = get_settings()
        target_dir = settings.checkpoints_dir / str(pid)
        target_dir.mkdir(parents=True, exist_ok=True)

        temp_file = target_dir / f"tmp_{uuid.uuid4().hex[:12]}_{filename}"
        sha256 = hashlib.sha256()
        total_bytes = 0

        try:
            # 3. Stream write file in chunks
            with open(temp_file, "wb") as f:
                async for chunk in file_stream:
                    if chunk:
                        f.write(chunk)
                        sha256.update(chunk)
                        total_bytes += len(chunk)

            if total_bytes == 0:
                raise ValidationError("Uploaded checkpoint file is empty.")

            checksum = sha256.hexdigest()

            # 4. Verify PyTorch format integrity using weights_only=True
            try:
                ckpt_data = torch.load(temp_file, map_location="cpu", weights_only=True)
                if not isinstance(ckpt_data, dict):
                    raise ValidationError("Checkpoint does not contain a valid PyTorch dictionary payload.")
            except Exception as exc:
                raise ValidationError(f"Checkpoint integrity verification failed: {exc}")

            # 5. Atomically rename to definitive path
            ext = Path(filename).suffix or ".pt"
            final_name = f"checkpoint_step_{step}_{checksum[:8]}{ext}"
            final_path = target_dir / final_name
            temp_file.replace(final_path)

            # 6. Save Checkpoint model
            checkpoint = Checkpoint(
                project_id=pid,
                run_id=rid,
                step=step,
                file_path=str(final_path),
                file_size_bytes=total_bytes,
                checksum_sha256=checksum,
                is_validated=True,
                metrics_json=json.dumps(metrics_dict) if metrics_dict else None,
            )
            db.add(checkpoint)

            # Update run current step
            r_stmt = select(TrainingRun).where(TrainingRun.id == rid)
            run = (await db.execute(r_stmt)).scalar_one_or_none()
            if run:
                run.current_step = max(run.current_step, step)

            await db.flush()

            logger.info(
                "checkpoint_published",
                checkpoint_id=str(checkpoint.id),
                project_id=str(pid),
                step=step,
                size_bytes=total_bytes,
                checksum=checksum,
            )

            # 7. Broadcast checkpoint_saved event to browser clients
            await ws_hub.broadcast_website_event(
                event="checkpoint_saved",
                entity_id=str(pid),
                payload={
                    "checkpoint_id": str(checkpoint.id),
                    "project_id": str(pid),
                    "step": step,
                    "file_size_bytes": total_bytes,
                },
                project_id=pid,
            )

            return checkpoint

        except Exception:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise

    @classmethod
    async def get_checkpoints(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID | str,
    ) -> List[Checkpoint]:
        """List all validated checkpoints for a project, newest step first."""
        pid = _ensure_uuid(project_id)
        stmt = (
            select(Checkpoint)
            .where(Checkpoint.project_id == pid)
            .order_by(desc(Checkpoint.step))
        )
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def get_latest_checkpoint(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID | str,
    ) -> Optional[Checkpoint]:
        """Retrieve the latest validated checkpoint for a project."""
        pid = _ensure_uuid(project_id)
        stmt = (
            select(Checkpoint)
            .where(Checkpoint.project_id == pid, Checkpoint.is_validated.is_(True))
            .order_by(desc(Checkpoint.step))
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    @classmethod
    async def resume_from_checkpoint(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID | str,
        checkpoint_id: uuid.UUID | str,
    ) -> Tuple[uuid.UUID, int, uuid.UUID]:
        """
        Validate checkpoint and restore training run state to resume from checkpoint step.
        """
        pid = _ensure_uuid(project_id)
        cid = _ensure_uuid(checkpoint_id)

        c_stmt = select(Checkpoint).where(Checkpoint.id == cid, Checkpoint.project_id == pid)
        checkpoint = (await db.execute(c_stmt)).scalar_one_or_none()
        if not checkpoint:
            raise NotFoundError("Checkpoint not found for this project.")

        if not checkpoint.is_validated:
            raise ConflictError("Cannot resume from unvalidated checkpoint.")

        # Update run step
        r_stmt = select(TrainingRun).where(TrainingRun.id == checkpoint.run_id)
        run = (await db.execute(r_stmt)).scalar_one_or_none()
        if run:
            run.current_step = checkpoint.step
            run.status = "running"

        await db.flush()

        logger.info(
            "training_resumed_from_checkpoint",
            project_id=str(pid),
            checkpoint_id=str(cid),
            resumed_step=checkpoint.step,
        )

        return pid, checkpoint.step, cid


checkpoint_service = CheckpointService()
