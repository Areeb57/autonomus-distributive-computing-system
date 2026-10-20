"""
WebSocket endpoints for website browser events and agent bi-directional command streams.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.core.websocket import WSEvent, ws_hub
from app.models.machine import Machine
from app.models.user import User

logger = get_logger("adc.websocket.routes")

router = APIRouter(prefix="/ws", tags=["WebSockets"])


@router.websocket("/events")
async def website_events_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
) -> None:
    """
    Authenticated WebSocket connection for browser website clients.
    Streams live training metrics, worker join/leave events, and project status changes.
    """
    # 1. Authenticate user from query parameter token or cookies
    auth_token = token
    if not auth_token:
        auth_token = websocket.cookies.get("access_token")

    if not auth_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_access_token(auth_token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id_str = payload.get("sub")
    if not user_id_str:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Register connection
    await ws_hub.connect_website(
        websocket=websocket,
        user_id=user_id,
        project_id=project_id,
    )

    try:
        while True:
            # Keep connection open, handle client heartbeats or queries
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("type") == "ping":
                    pong = WSEvent(event="pong", entity_id=str(user_id))
                    await websocket.send_text(pong.to_json())
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_hub.disconnect_website(websocket, user_id, project_id)
    except Exception as exc:
        logger.warning("ws_website_error", error=str(exc))
        ws_hub.disconnect_website(websocket, user_id, project_id)


@router.websocket("/agent")
async def agent_websocket(
    websocket: WebSocket,
    installation_id: str = Query(..., alias="installation_id"),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Bi-directional WebSocket for connected CLI Master and Worker agents.
    Dispatches task assignments and control signals (pause/resume/checkpoint).
    """
    # 1. Resolve machine node
    stmt = select(Machine).where(Machine.installation_id == installation_id)
    machine = (await db.execute(stmt)).scalars().first()

    if not machine:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Register agent connection
    await ws_hub.connect_agent(websocket=websocket, machine_id=machine.id)

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("type") == "ping":
                    pong = WSEvent(event="pong", entity_id=str(machine.id))
                    await websocket.send_text(pong.to_json())
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_hub.disconnect_agent(websocket, machine.id)
    except Exception as exc:
        logger.warning("ws_agent_error", error=str(exc))
        ws_hub.disconnect_agent(websocket, machine.id)
