"""
Background heartbeat and instance lease manager for ADC agents.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

from agents.common.client import AgentBackendClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class LeaseManager:
    """Maintains active instance lease through periodic heartbeats."""

    def __init__(
        self,
        client: AgentBackendClient,
        interval_seconds: int = 25,
        status_getter: Optional[Callable[[], str]] = None,
        metrics_getter: Optional[Callable[[], dict]] = None,
    ) -> None:
        self.client = client
        self.interval_seconds = interval_seconds
        self.status_getter = status_getter or (lambda: "idle")
        self.metrics_getter = metrics_getter or (lambda: {})
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background heartbeat task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("heartbeat_loop_started", interval=self.interval_seconds)

    async def stop(self) -> None:
        """Cancel and wait for background heartbeat task to terminate."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("heartbeat_loop_stopped")

    async def _heartbeat_loop(self) -> None:
        """Send heartbeats periodically until stopped or cancelled."""
        while self._running:
            try:
                current_status = self.status_getter()
                current_metrics = self.metrics_getter()
                response = await self.client.send_heartbeat(
                    status=current_status,
                    metrics=current_metrics,
                )
                logger.debug(
                    "heartbeat_acknowledged",
                    status=response.get("status"),
                    lease_expires_at=response.get("leaseExpiresAt"),
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("heartbeat_failed", error=str(exc))

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
