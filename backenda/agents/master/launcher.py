"""
ADC Master Agent Launcher.

Entry point for running the Master coordination agent on a user's workstation.
Enforces:
- Identity registration with Ed25519 keypair
- Browser pairing workflow
- Active Master role lease and periodic heartbeats
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import Optional

from agents.common.client import AgentBackendClient
from agents.common.identity import MachineIdentity
from agents.common.lease import LeaseManager
from app.core.logging import get_logger

logger = get_logger("adc.agent.master")


class MasterAgent:
    """Master node coordination agent."""

    def __init__(self, backend_url: str = "http://localhost:8000") -> None:
        self.backend_url = backend_url
        self.identity = MachineIdentity.load_or_create()
        self.client = AgentBackendClient(base_url=backend_url, identity=self.identity)
        self.lease_manager: Optional[LeaseManager] = None
        self._running = False

    async def run(self) -> None:
        """Main agent startup and coordination loop."""
        self._running = True
        print(f"\n[ADC Master Agent] Initializing on {self.identity.name} ({self.identity.installation_id})")

        # 1. Register machine with backend
        try:
            reg_info = await self.client.register()
            print(f"[ADC Master Agent] Registered with backend: {reg_info.get('name')}")
        except Exception as exc:
            print(f"[ADC Master Agent] Warning: Registration check returned: {exc}")

        # 2. Check current status
        status = await self.client.get_status()
        active_role = status.get("activeRole", "none")
        paired_user = status.get("pairedUserId")

        # 3. Handle pairing if not paired or wrong role
        if not paired_user or active_role != "master":
            challenge = await self.client.request_pairing_challenge()
            code = challenge["challengeCode"]

            print("\n" + "=" * 70)
            print("  ADC MASTER AGENT — BROWSER PAIRING REQUIRED")
            print("=" * 70)
            print(f"\n  Your Pairing Code:    >>>  {code}  <<<")
            print("  Expires in:           5 minutes\n")
            print("  Instructions:")
            print("  1. Open http://localhost:5173/ in your browser")
            print("  2. Log in to your ADC account")
            print("  3. Complete pairing selecting the 'Master' role")
            print("=" * 70 + "\n")
            print("Waiting for browser pairing to complete...")

            while self._running:
                await asyncio.sleep(3)
                status = await self.client.get_status()
                if status.get("pairedUserId") and status.get("activeRole") == "master":
                    print("\n[ADC Master Agent] Pairing confirmed! Role: Master")
                    break

        # 4. Acquire/start lease manager
        self.client.lease_token = status.get("leaseToken") or "local-dev-lease"
        self.lease_manager = LeaseManager(
            client=self.client,
            interval_seconds=20,
            status_getter=lambda: "idle",
        )
        await self.lease_manager.start()

        print("[ADC Master Agent] Master agent is online and ready for project coordination.")
        print("[ADC Master Agent] Press Ctrl+C to stop.\n")

        # Keep running
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully release lease and close connection."""
        print("\n[ADC Master Agent] Shutting down...")
        self._running = False
        if self.lease_manager:
            await self.lease_manager.stop()
        await self.client.close()
        print("[ADC Master Agent] Stopped.")


def main() -> None:
    """CLI entrypoint for adc-master."""
    backend_url = os.environ.get("ADC_BACKEND_URL", "http://localhost:8000")
    agent = MasterAgent(backend_url=backend_url)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal():
        loop.create_task(agent.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except (NotImplementedError, RuntimeError):
            pass  # Windows does not support add_signal_handler for some loops

    try:
        loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        loop.run_until_complete(agent.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
