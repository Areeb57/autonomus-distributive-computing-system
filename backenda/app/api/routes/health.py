"""
Health and readiness endpoints.

- GET /health          — basic liveness check
- GET /health/ready    — readiness check (database connectivity)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.database.session import check_db_connection

router = APIRouter(tags=["Health"])

_startup_time = datetime.now(timezone.utc)


@router.get("/health")
async def health() -> dict:
    """Liveness probe — always returns 200 if the process is running."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": "adc-backend",
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": (datetime.now(timezone.utc) - _startup_time).total_seconds(),
    }


@router.get("/health/ready")
async def readiness() -> dict:
    """
    Readiness probe — returns 200 only when the database is reachable.

    If the database is down, returns 503.
    """
    db_ok = await check_db_connection()

    status_code = 200 if db_ok else 503
    response = {
        "status": "ready" if db_ok else "not_ready",
        "checks": {
            "database": "connected" if db_ok else "unreachable",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not db_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status_code, content=response)

    return response
