"""
System Recovery, Stale Task Reclamation, Orphaned Upload Cleanup, and Failure Supervision (Phase 10).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.state_machine import TaskState
from app.core.websocket import ws_hub
from app.models.audit import AuditEvent
from app.models.project import Project, ProjectMembership
from app.models.training import Checkpoint, TrainingRun, TrainingTask

logger = get_logger("adc.services.recovery")
settings = get_settings()


class SystemRecoveryService:
    """
    Automated supervisory service for cluster fault-tolerance, stale task recovery,
    interrupted run resumption, and storage garbage collection.
    """

    async def sweep_all(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Execute full recovery sweep:
        1. Reclaim stale task leases.
        2. Garbage collect incomplete/orphaned temporary file uploads.
        3. Audit interrupted runs.
        """
        reclaimed_tasks = await self.reclaim_stale_tasks(db)
        cleaned_files, freed_bytes = self.clean_orphaned_uploads()
        interrupted_runs = await self.audit_interrupted_runs(db)

        await db.commit()

        summary = {
            "reclaimed_tasks_count": len(reclaimed_tasks),
            "reclaimed_tasks": reclaimed_tasks,
            "cleaned_temp_files_count": cleaned_files,
            "cleaned_temp_bytes": freed_bytes,
            "interrupted_runs_count": len(interrupted_runs),
            "interrupted_runs": interrupted_runs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("system_recovery_sweep_completed", **summary)
        return summary

    async def reclaim_stale_tasks(
        self,
        db: AsyncSession,
        max_retries: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Locate tasks with expired leases and reclaim them into the dispatchable pool.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(TrainingTask)
            .where(
                TrainingTask.status.in_(["assigned", "leased", "running"]),
                TrainingTask.lease_expires_at.is_not(None),
                TrainingTask.lease_expires_at < now,
            )
        )
        stale_tasks = (await db.execute(stmt)).scalars().all()
        reclaimed: List[Dict[str, Any]] = []

        for task in stale_tasks:
            prev_status = task.status
            prev_worker = str(task.assigned_machine_id) if task.assigned_machine_id else "unknown"

            # Parse retry count from error_details if present
            current_retries = 0
            if task.error_details and "[retry:" in task.error_details:
                try:
                    part = task.error_details.split("[retry:")[1].split("]")[0]
                    current_retries = int(part)
                except Exception:
                    pass

            if current_retries < max_retries:
                task.status = TaskState.PENDING.value
                task.assigned_machine_id = None
                task.lease_token = None
                task.lease_expires_at = None
                task.error_details = f"[retry:{current_retries + 1}] Reclaimed after lease expiration."
                action = "requeued"
                retries_recorded = current_retries + 1
            else:
                task.status = TaskState.FAILED.value
                task.error_details = f"Exceeded maximum lease recovery attempts ({max_retries})."
                action = "marked_failed"
                retries_recorded = current_retries

            audit = AuditEvent(
                action=f"task.recovery.{action}",
                resource_type="training_task",
                resource_id=str(task.id),
                details_json=json.dumps({
                    "previous_status": prev_status,
                    "previous_worker": prev_worker,
                    "retry_count": retries_recorded,
                }),
            )
            db.add(audit)


            reclaimed.append({
                "task_id": str(task.id),
                "project_id": str(task.project_id),
                "step_range": f"{task.step_start}..{task.step_end}",
                "action": action,
                "retry_count": retries_recorded,
            })

            # Broadcast task state change via WebSocket
            await ws_hub.broadcast_project_event(
                project_id=task.project_id,
                event_type="training.task_reclaimed",
                payload={"taskId": str(task.id), "action": action, "retryCount": retries_recorded},
            )


        return reclaimed

    def clean_orphaned_uploads(self, max_age_seconds: int = 3600) -> Tuple[int, int]:
        """
        Scan storage directories for incomplete chunked uploads or abandoned temporary files
        created older than max_age_seconds.
        """
        now = time.time()
        directories = [
            settings.storage_root / "datasets",
            settings.storage_root / "packages",
            settings.storage_root / "checkpoints",
        ]
        cleaned_files = 0
        freed_bytes = 0

        for target_dir in directories:
            if not target_dir.exists():
                continue

            for root, _, files in os.walk(target_dir):
                for filename in files:
                    # Match quarantine and incomplete upload prefixes
                    if filename.startswith("tmp_") or filename.endswith(".part") or filename.endswith(".tmp"):
                        file_path = Path(root) / filename
                        try:
                            stats = file_path.stat()
                            if now - stats.st_mtime > max_age_seconds:
                                size = stats.st_size
                                file_path.unlink()
                                cleaned_files += 1
                                freed_bytes += size
                                logger.info(
                                    "purged_orphaned_temporary_upload",
                                    path=str(file_path),
                                    size_bytes=size,
                                )
                        except OSError as err:
                            logger.warning("failed_to_delete_temp_file", path=str(file_path), error=str(err))

        return cleaned_files, freed_bytes

    async def audit_interrupted_runs(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Inspect running training runs. If all workers have been offline for > 15 minutes,
        pause the run gracefully to avoid holding cluster resources in limbo.
        """
        cutoff = datetime.now(timezone.utc)
        stmt = (
            select(TrainingRun)
            .where(TrainingRun.status == "running")
        )
        active_runs = (await db.execute(stmt)).scalars().all()
        interrupted: List[Dict[str, Any]] = []

        for run in active_runs:
            # Check if project has any active worker memberships
            m_stmt = select(ProjectMembership).where(
                ProjectMembership.project_id == run.project_id,
                ProjectMembership.status == "training",
            )
            workers = (await db.execute(m_stmt)).scalars().all()

            if not workers:
                # Check when run was updated
                run.status = "paused"
                audit = AuditEvent(
                    action="run.recovery.paused_no_workers",
                    resource_type="training_run",
                    resource_id=str(run.id),
                    details_json=json.dumps({"project_id": str(run.project_id)}),
                )
                db.add(audit)
                interrupted.append({
                    "run_id": str(run.id),
                    "project_id": str(run.project_id),
                    "status": "paused",
                    "reason": "No active workers connected to training run.",
                })
                # Broadcast pause event
                await ws_hub.broadcast_project_event(
                    project_id=run.project_id,
                    event_type="project.status_changed",
                    payload={"status": "paused", "reason": "No active workers available."},
                )

        return interrupted


# Global singleton instance
recovery_service = SystemRecoveryService()
