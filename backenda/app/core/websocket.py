"""
WebSocket Event Hub, connection registries, and real-time streaming protocols.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("adc.websocket")


class WSEvent(BaseModel):
    """Standardized event envelope matching Section 18 protocol."""

    event: str
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    entity_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return self.model_dump_json()


class WebSocketHub:
    """
    Central connection manager coordinating browser subscriptions and agent bi-directional streams.
    """

    def __init__(self) -> None:
        # Browser client connections: user_id -> set of active WebSockets
        self.website_users: Dict[uuid.UUID, Set[WebSocket]] = {}
        # Project rooms: project_id -> set of active WebSockets
        self.project_subscribers: Dict[uuid.UUID, Set[WebSocket]] = {}
        # Agent connections: machine_id -> WebSocket
        self.agent_connections: Dict[uuid.UUID, WebSocket] = {}

    # ── Website / Browser Connections ────────────────────────────────────────

    async def connect_website(
        self,
        websocket: WebSocket,
        user_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Register an authenticated browser client."""
        await websocket.accept()

        if user_id not in self.website_users:
            self.website_users[user_id] = set()
        self.website_users[user_id].add(websocket)

        if project_id:
            if project_id not in self.project_subscribers:
                self.project_subscribers[project_id] = set()
            self.project_subscribers[project_id].add(websocket)

        # Send initial connection acknowledgement event
        evt = WSEvent(
            event="connection_status",
            entity_id=str(user_id),
            payload={"status": "connected", "user_id": str(user_id)},
        )
        await websocket.send_text(evt.to_json())
        logger.info("ws_website_connected", user_id=str(user_id), project_id=str(project_id))

    def disconnect_website(
        self,
        websocket: WebSocket,
        user_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Remove a disconnected browser client."""
        if user_id in self.website_users:
            self.website_users[user_id].discard(websocket)
            if not self.website_users[user_id]:
                del self.website_users[user_id]

        if project_id and project_id in self.project_subscribers:
            self.project_subscribers[project_id].discard(websocket)
            if not self.project_subscribers[project_id]:
                del self.project_subscribers[project_id]

        logger.info("ws_website_disconnected", user_id=str(user_id))

    async def broadcast_website_event(
        self,
        event: str,
        entity_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        project_id: Optional[uuid.UUID] = None,
    ) -> None:
        """
        Broadcast event to browser clients subscribed to a specific project or globally.
        """
        envelope = WSEvent(
            event=event,
            entity_id=entity_id,
            payload=payload or {},
        )
        json_str = envelope.to_json()

        targets: Set[WebSocket] = set()
        if project_id and project_id in self.project_subscribers:
            targets.update(self.project_subscribers[project_id])
        else:
            # Broadcast to all connected browser users
            for sockets in self.website_users.values():
                targets.update(sockets)

        dead_sockets: List[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(json_str)
            except Exception:
                dead_sockets.append(ws)

        # Cleanup failed connections
        for ws in dead_sockets:
            for uid, user_sockets in list(self.website_users.items()):
                user_sockets.discard(ws)
            for pid, proj_sockets in list(self.project_subscribers.items()):
                proj_sockets.discard(ws)

    async def broadcast_project_event(
        self,
        project_id: uuid.UUID,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Broadcast event to all browser clients subscribed to a specific project."""
        await self.broadcast_website_event(
            event=event_type,
            entity_id=str(project_id),
            payload=payload,
            project_id=project_id,
        )

    # ── Agent Connections ────────────────────────────────────────────────────


    async def connect_agent(
        self,
        websocket: WebSocket,
        machine_id: uuid.UUID,
    ) -> None:
        """Register an active agent compute node."""
        await websocket.accept()
        self.agent_connections[machine_id] = websocket

        evt = WSEvent(
            event="connection_status",
            entity_id=str(machine_id),
            payload={"status": "connected", "machine_id": str(machine_id)},
        )
        await websocket.send_text(evt.to_json())
        logger.info("ws_agent_connected", machine_id=str(machine_id))

    def disconnect_agent(
        self,
        websocket: WebSocket,
        machine_id: uuid.UUID,
    ) -> None:
        """Remove a disconnected agent."""
        if machine_id in self.agent_connections and self.agent_connections[machine_id] == websocket:
            del self.agent_connections[machine_id]
        logger.info("ws_agent_disconnected", machine_id=str(machine_id))

    async def send_agent_event(
        self,
        machine_id: uuid.UUID,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send a direct control message to a connected compute agent."""
        ws = self.agent_connections.get(machine_id)
        if not ws:
            return False

        envelope = WSEvent(
            event=event,
            entity_id=str(machine_id),
            payload=payload or {},
        )
        try:
            await ws.send_text(envelope.to_json())
            return True
        except Exception as exc:
            logger.warning("ws_agent_send_failed", machine_id=str(machine_id), error=str(exc))
            self.agent_connections.pop(machine_id, None)
            return False


# Global singleton WebSocket hub instance
ws_hub = WebSocketHub()
