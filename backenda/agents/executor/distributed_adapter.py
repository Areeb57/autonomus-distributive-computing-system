"""
Distributed Training Adapter and Relay Client for Worker Sandboxes (Phase 9).
Provides real parameter/gradient synchronization for training scripts running in isolated child processes.
"""

from __future__ import annotations

import io
import os
import sys
import uuid
from typing import Any, Dict, Optional

import httpx
import torch
import torch.nn as nn


class ADCDistributedClient:
    """
    Client library injected into the child sandbox environment.
    Enables real PyTorch scripts to perform synchronous parameter averaging across
    distributed volunteer worker nodes through the ADC Relay Aggregator.
    """

    def __init__(
        self,
        relay_url: Optional[str] = None,
        run_id: Optional[str] = None,
        rank: Optional[int] = None,
        world_size: Optional[int] = None,
        strategy: Optional[str] = None,
        installation_id: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> None:
        self.strategy = strategy or os.environ.get("ADC_STRATEGY", "single_node")
        self.rank = rank if rank is not None else int(os.environ.get("RANK", "0"))
        self.world_size = world_size if world_size is not None else int(os.environ.get("WORLD_SIZE", "1"))
        self.run_id = run_id or os.environ.get("ADC_RUN_ID")
        self.relay_url = relay_url or os.environ.get("ADC_RELAY_URL")
        self.installation_id = installation_id or os.environ.get("ADC_INSTALLATION_ID")
        self.auth_token = auth_token or os.environ.get("ADC_AUTH_TOKEN")

    @property
    def is_distributed(self) -> bool:
        return self.world_size > 1 and self.strategy in ["data_parallel", "model_parallel"]

    def sync_model(self, step: int, model: nn.Module) -> None:
        """
        Synchronize model parameters across all distributed worker ranks for the given step.
        Blocks until all active ranks submit their parameters and returns the synchronized average.
        """
        if not self.is_distributed or not self.relay_url or not self.run_id:
            # Single node or independent jobs do not require inter-node collective sync
            return

        # 1. Serialize local model state dictionary
        buf = io.BytesIO()
        state_dict = model.state_dict()
        torch.save(state_dict, buf)
        buf.seek(0)

        # 2. Prepare headers
        headers: Dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self.installation_id:
            headers["X-Installation-Id"] = self.installation_id

        # 3. Submit to central relay
        files = {
            "file": (f"weights_rank_{self.rank}.pt", buf.getvalue(), "application/octet-stream"),
        }
        data = {
            "run_id": self.run_id,
            "step": str(step),
            "rank": str(self.rank),
        }

        try:
            resp = httpx.post(
                self.relay_url,
                data=data,
                files=files,
                headers=headers,
                timeout=60.0,
            )
            resp.raise_for_status()
        except Exception as exc:
            print(f"[ADC_DISTRIBUTED_ERROR] Step {step} rank {self.rank} sync failed: {exc}", file=sys.stderr)
            raise

        # 4. Load synchronized averaged parameters back into model
        aggregated_dict = torch.load(io.BytesIO(resp.content), weights_only=True)
        model.load_state_dict(aggregated_dict)
        print(f"[ADC_DISTRIBUTED_SYNC] Step {step}: Rank {self.rank} synchronized {len(aggregated_dict)} tensors.")
