"""
Central Parameter and Gradient Relay Aggregator for NAT/Firewalled Distributed Training (Phase 9).
Provides real synchronous AllReduce parameter averaging across volunteer worker nodes.
"""

from __future__ import annotations

import asyncio
import io
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

import torch

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger

logger = get_logger("adc.training.relay")


class StepSyncBarrier:
    """
    Synchronous barrier holding parameter updates for a single training step
    until all active worker ranks have contributed.
    """

    def __init__(
        self,
        run_id: uuid.UUID,
        step: int,
        expected_ranks: Set[int],
        timeout_seconds: float = 60.0,
    ) -> None:
        self.run_id = run_id
        self.step = step
        self.expected_ranks = set(expected_ranks)
        self.submitted_ranks: Set[int] = set()
        self.received_tensors: Dict[int, Dict[str, torch.Tensor]] = {}
        self.aggregated_tensors: Optional[Dict[str, torch.Tensor]] = None
        self.aggregated_bytes: Optional[bytes] = None
        self.event = asyncio.Event()
        self.created_at = time.time()
        self.timeout_seconds = timeout_seconds
        self.is_failed = False
        self.failure_reason: Optional[str] = None

    def submit_rank_tensors(
        self,
        rank: int,
        tensors: Dict[str, torch.Tensor],
    ) -> bool:
        """Record tensors submitted by a specific rank. Returns True when barrier is satisfied."""
        if rank not in self.expected_ranks:
            raise ValidationError(f"Rank {rank} is not in expected ranks {self.expected_ranks} for run {self.run_id}.")

        if rank in self.submitted_ranks:
            raise ConflictError(f"Rank {rank} already submitted updates for step {self.step}.")

        self.submitted_ranks.add(rank)
        self.received_tensors[rank] = tensors

        logger.info(
            f"Relay barrier [run={self.run_id}, step={self.step}]: Rank {rank} submitted ({len(self.submitted_ranks)}/{len(self.expected_ranks)})"
        )

        if self.submitted_ranks == self.expected_ranks:
            self._aggregate_all_tensors()
            self.event.set()
            return True

        return False

    def _aggregate_all_tensors(self) -> None:
        """
        Compute real mathematical parameter average:
        theta_bar = (1 / N) * sum(theta_i)
        """
        num_ranks = len(self.expected_ranks)
        if num_ranks == 0:
            return

        all_keys = list(self.received_tensors[next(iter(self.expected_ranks))].keys())
        aggregated: Dict[str, torch.Tensor] = {}

        for key in all_keys:
            # Accumulate on CPU with float precision to maintain numerical stability
            accum: Optional[torch.Tensor] = None
            for rank in self.expected_ranks:
                t = self.received_tensors[rank][key]
                if torch.isnan(t).any() or torch.isinf(t).any():
                    self.is_failed = True
                    self.failure_reason = f"Rank {rank} submitted NaN or Inf tensors in parameter '{key}'."
                    raise ValidationError(self.failure_reason)

                t_float = t.detach().cpu().to(torch.float32)
                if accum is None:
                    accum = t_float
                else:
                    accum += t_float

            avg_tensor = accum / float(num_ranks)
            aggregated[key] = avg_tensor

        self.aggregated_tensors = aggregated

        # Pre-serialize aggregated payload once for all waiting ranks
        buf = io.BytesIO()
        torch.save(aggregated, buf)
        self.aggregated_bytes = buf.getvalue()

        # Free individual submitted tensors to conserve coordinator memory
        self.received_tensors.clear()
        logger.info(
            f"Relay barrier [run={self.run_id}, step={self.step}]: Synchronous AllReduce complete ({len(all_keys)} tensors, {len(self.aggregated_bytes)} bytes)."
        )

    def mark_failed(self, reason: str) -> None:
        """Mark barrier as aborted due to rank drop or straggler timeout."""
        self.is_failed = True
        self.failure_reason = reason
        self.received_tensors.clear()
        self.event.set()


class RelayParameterAggregator:
    """
    Coordinator-side relay service providing synchronized parameter/gradient AllReduce.

    Mathematical Invariant:
    Every participating worker rank receives an exact, bit-identical copy of the
    averaged parameters for each training step before proceeding to step + 1.

    Bandwidth & Scalability:
    - Master ingress: N * M bytes per sync step (M = model bytes, N = world size)
    - Master egress: N * M bytes per sync step
    - Latency: max_{r}(worker_step_latency_r) + 2 * network_rtt + aggregation_time
    - Memory: O(M) working accumulator space on Master coordinator
    """

    def __init__(self) -> None:
        # Key: (run_id, step) -> StepSyncBarrier
        self._barriers: Dict[Tuple[uuid.UUID, int], StepSyncBarrier] = {}
        self._lock = asyncio.Lock()

    async def sync_step_tensors(
        self,
        run_id: uuid.UUID,
        step: int,
        rank: int,
        expected_ranks: Set[int],
        tensors: Dict[str, torch.Tensor],
        timeout_seconds: float = 60.0,
    ) -> bytes:
        """
        Worker calls this method to submit local weights/gradients and await
        the synchronized average payload from all ranks.
        """
        key = (run_id, step)
        async with self._lock:
            barrier = self._barriers.get(key)
            if barrier is None:
                barrier = StepSyncBarrier(
                    run_id=run_id,
                    step=step,
                    expected_ranks=expected_ranks,
                    timeout_seconds=timeout_seconds,
                )
                self._barriers[key] = barrier

        # Submit rank updates
        try:
            barrier.submit_rank_tensors(rank, tensors)
        except Exception as exc:
            logger.error(f"Failed to submit tensors for run {run_id}, step {step}, rank {rank}: {exc}")
            raise

        # Wait for all other ranks to submit or timeout
        try:
            await asyncio.wait_for(barrier.event.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            missing_ranks = barrier.expected_ranks - barrier.submitted_ranks
            err_msg = f"Straggler timeout on step {step}. Missing ranks: {sorted(list(missing_ranks))}."
            barrier.mark_failed(err_msg)
            logger.warning(f"Run {run_id}: {err_msg}")
            raise ConflictError(err_msg)

        if barrier.is_failed:
            raise ValidationError(f"Step {step} synchronization failed: {barrier.failure_reason}")

        if not barrier.aggregated_bytes:
            raise NotFoundError("Aggregated tensor payload missing after barrier resolution.")

        # Prune old completed barriers older than 5 steps
        async with self._lock:
            old_steps = [k for k in self._barriers if k[0] == run_id and k[1] < step - 5]
            for old_k in old_steps:
                self._barriers.pop(old_k, None)

        return barrier.aggregated_bytes

    def cleanup_run(self, run_id: uuid.UUID) -> None:
        """Purge all barriers associated with a terminated or aborted run."""
        keys_to_remove = [k for k in self._barriers if k[0] == run_id]
        for k in keys_to_remove:
            self._barriers.pop(k, None)


# Global singleton instance
relay_aggregator = RelayParameterAggregator()
