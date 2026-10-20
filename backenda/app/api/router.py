"""
Central router collecting all /api/v1 endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.machines import router as machines_router
from app.api.routes.resources import router as resources_router
from app.api.routes.projects import router as projects_router
from app.api.routes.agent_tasks import router as agent_tasks_router
from app.api.routes.websocket import router as websocket_router
from app.api.routes.checkpoints import router as checkpoints_router
from app.api.routes.distributed import router as distributed_router
from app.api.routes.system import router as system_router

api_v1_router = APIRouter(prefix="/api/v1")

# Mount API route groups
api_v1_router.include_router(auth_router)
api_v1_router.include_router(machines_router)
api_v1_router.include_router(resources_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(agent_tasks_router)
api_v1_router.include_router(websocket_router)
api_v1_router.include_router(checkpoints_router)
api_v1_router.include_router(distributed_router)
api_v1_router.include_router(system_router)
