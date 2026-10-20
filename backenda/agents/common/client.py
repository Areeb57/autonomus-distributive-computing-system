"""
Async HTTP client for agent-to-backend communication.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from agents.common.identity import MachineIdentity


class AgentBackendClient:
    """Handles communication between agent process and ADC backend API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        identity: Optional[MachineIdentity] = None,
        lease_token: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.identity = identity or MachineIdentity.load_or_create()
        self.lease_token = lease_token
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def register(self) -> Dict[str, Any]:
        """Register the machine's public key with the backend."""
        payload = {
            "installation_id": self.identity.installation_id,
            "name": self.identity.name,
            "public_key": self.identity.public_key_hex,
            "platform": self.identity.platform_name,
        }
        res = await self._client.post("/api/v1/machines/register", json=payload)
        res.raise_for_status()
        return res.json()

    async def get_status(self) -> Dict[str, Any]:
        """Query current machine pairing and role status."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        res = await self._client.get("/api/v1/machines/me", headers=headers)
        res.raise_for_status()
        machines = res.json()
        if machines:
            return machines[0]
        return {}

    async def request_pairing_challenge(self) -> Dict[str, Any]:
        """Generate a browser pairing challenge."""
        ts = int(time.time())
        sig = self.identity.sign_timestamped_nonce(ts)
        payload = {
            "installation_id": self.identity.installation_id,
            "timestamp": ts,
            "signature": sig,
        }
        res = await self._client.post("/api/v1/machines/pairing/challenge", json=payload)
        res.raise_for_status()
        return res.json()

    async def send_heartbeat(
        self,
        status: str = "idle",
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send periodic heartbeat to maintain active instance lease."""
        if not self.lease_token:
            raise ValueError("Cannot send heartbeat without an active lease_token.")

        payload = {
            "installation_id": self.identity.installation_id,
            "lease_token": self.lease_token,
            "status": status,
            "metrics": metrics or {},
        }
        res = await self._client.post("/api/v1/machines/heartbeat", json=payload)
        res.raise_for_status()
        return res.json()

    async def change_role(self, new_role: str, force: bool = False) -> Dict[str, Any]:
        """Request role change (master, worker, none)."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        payload = {"new_role": new_role, "force": force}
        res = await self._client.post("/api/v1/machines/role-change", json=payload, headers=headers)
        res.raise_for_status()
        return res.json()

    async def get_assigned_tasks(self, project_id: Optional[str] = None) -> list[Dict[str, Any]]:
        """Query assigned or available tasks for this machine."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        params: Dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id
        res = await self._client.get("/api/v1/agent/tasks", headers=headers, params=params)
        res.raise_for_status()
        return res.json()

    async def acknowledge_task(self, task_id: str, lease_token: str) -> Dict[str, Any]:
        """Acknowledge task assignment and confirm execution start."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        payload = {"leaseToken": lease_token}
        res = await self._client.post(f"/api/v1/agent/tasks/{task_id}/acknowledge", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    async def report_task_metrics(
        self,
        task_id: str,
        step: int,
        loss: float,
        speed: float = 0.0,
        cluster_cpu_util: float = 0.0,
        cluster_gpu_util: float = 0.0,
        ram_util_gb: float = 0.0,
    ) -> Dict[str, Any]:
        """Report training step telemetry metrics."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        payload = {
            "step": step,
            "loss": loss,
            "speed": speed,
            "clusterCpuUtil": cluster_cpu_util,
            "clusterGpuUtil": cluster_gpu_util,
            "ramUtilGB": ram_util_gb,
        }
        res = await self._client.post(f"/api/v1/agent/tasks/{task_id}/metrics", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result_summary: Optional[str] = None,
        error_details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Report task status (in_progress, paused, completed, failed)."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        payload = {
            "status": status,
            "resultSummary": result_summary,
            "errorDetails": error_details,
        }
        res = await self._client.post(f"/api/v1/agent/tasks/{task_id}/status", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    async def download_file(self, url_path: str, destination_path: Path | str) -> Path:
        """Stream download a file from backend storage to local filesystem."""
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        headers = {"X-Installation-Id": self.identity.installation_id}
        async with self._client.stream("GET", url_path, headers=headers) as res:
            res.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in res.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
        return dest

    async def upload_checkpoint(
        self,
        project_id: str,
        step: int,
        checkpoint_path: Path | str,
        run_id: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Stream upload a created checkpoint to the backend."""
        path = Path(checkpoint_path)
        headers = {"X-Installation-Id": self.identity.installation_id}
        data = {"step": str(step)}
        if run_id:
            data["run_id"] = str(run_id)
        if metrics:
            data["metrics_json"] = json.dumps(metrics)

        with open(path, "rb") as f:
            files = {"file": (path.name, f, "application/octet-stream")}
            res = await self._client.post(
                f"/api/v1/projects/{project_id}/checkpoints",
                headers=headers,
                data=data,
                files=files,
            )
        res.raise_for_status()
        return res.json()

    async def get_latest_checkpoint(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Query the latest validated checkpoint metadata for a project."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        res = await self._client.get(
            f"/api/v1/projects/{project_id}/checkpoints/latest",
            headers=headers,
        )
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def get_distributed_rendezvous(self, project_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Obtain rank assignment and rendezvous parameters for distributed training."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        payload = {"runId": run_id} if run_id else {}
        res = await self._client.post(
            f"/api/v1/projects/{project_id}/distributed/rendezvous",
            headers=headers,
            json=payload,
        )
        res.raise_for_status()
        return res.json()

    async def report_distributed_heartbeat(
        self,
        project_id: str,
        run_id: str,
        rank: int,
        current_step: int,
    ) -> Dict[str, Any]:
        """Send distributed rank heartbeat ping."""
        headers = {"X-Installation-Id": self.identity.installation_id}
        payload = {
            "runId": run_id,
            "rank": rank,
            "currentStep": current_step,
        }
        res = await self._client.post(
            f"/api/v1/projects/{project_id}/distributed/heartbeat",
            headers=headers,
            json=payload,
        )
        res.raise_for_status()
        return res.json()
