"""
System Health, Audit, and Recovery Sweep API Endpoints (Phase 10).
"""

from __future__ import annotations

import shutil
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.websocket import ws_hub
from app.models.machine import Machine
from app.models.project import Project
from app.models.training import TrainingRun, TrainingTask
from app.models.user import User
from app.services.recovery import recovery_service

logger = get_logger("adc.system.api")
settings = get_settings()

router = APIRouter(prefix="/system", tags=["System & Operations"])


@router.post(
    "/recovery/sweep",
    summary="Trigger an administrative system fault-recovery and storage cleanup sweep",
)
async def trigger_recovery_sweep(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Execute full supervisory sweep:
    - Reclaims stale tasks with expired leases.
    - Purges orphaned temporary upload files.
    - Gracefully pauses orphaned runs without active workers.
    """
    logger.info("administrative_recovery_sweep_triggered", user_id=str(current_user.id))
    report = await recovery_service.sweep_all(db)
    return {
        "status": "completed",
        "report": report,
    }


@router.get(
    "/health/detailed",
    summary="Detailed system metrics, storage volumes, and active cluster stats",
)
async def get_detailed_system_health(
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Return operational health metrics for monitoring and infrastructure telemetry."""
    # Storage disk usage
    storage_root = settings.storage_root
    total_bytes, used_bytes, free_bytes = 0, 0, 0
    try:
        usage = shutil.disk_usage(storage_root)
        total_bytes = usage.total
        used_bytes = usage.used
        free_bytes = usage.free
    except Exception:
        pass

    # Database entity counts
    project_count = (await db.execute(select(func.count(Project.id)))).scalar() or 0
    machine_count = (await db.execute(select(func.count(Machine.id)))).scalar() or 0
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    active_runs = (
        await db.execute(
            select(func.count(TrainingRun.id)).where(TrainingRun.status.in_(["running", "pending"]))
        )
    ).scalar() or 0

    return {
        "status": "healthy",
        "environment": settings.app_env,
        "storage": {
            "root": str(storage_root),
            "total_gb": round(total_bytes / (1024**3), 2),
            "used_gb": round(used_bytes / (1024**3), 2),
            "free_gb": round(free_bytes / (1024**3), 2),
            "percent_free": round((free_bytes / total_bytes * 100), 1) if total_bytes > 0 else 0,
        },
        "cluster": {
            "total_users": user_count,
            "total_projects": project_count,
            "registered_machines": machine_count,
            "active_training_runs": active_runs,
            "active_websocket_connections": sum(len(s) for s in ws_hub.website_users.values()) + len(ws_hub.agent_connections),
        },
    }
