"""
Strategy Registry and Selection Service (Phase 9).
Manages registered distributed strategies, compatibility evaluation, and active rendezvous tracking.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Tuple

from app.core.exceptions import NotFoundError, ValidationError
from app.models.project import Project, ProjectMembership
from app.models.training import TrainingConfiguration
from app.training.strategies.base import BaseTrainingStrategy, RendezvousState
from app.training.strategies.data_parallel import DataParallelStrategy
from app.training.strategies.independent_jobs import IndependentJobsStrategy
from app.training.strategies.model_parallel import ModelParallelStrategy
from app.training.strategies.single_node import SingleNodeStrategy


class StrategyRegistry:
    """Central registry of all supported ADC training execution strategies."""

    def __init__(self) -> None:
        self._strategies: Dict[str, BaseTrainingStrategy] = {}
        # Active rendezvous states by run_id
        self._active_rendezvous: Dict[uuid.UUID, RendezvousState] = {}

        # Register default supported strategies
        self.register(SingleNodeStrategy())
        self.register(IndependentJobsStrategy())
        self.register(DataParallelStrategy(default_backend="relay"))
        self.register(DataParallelStrategy(default_backend="torch_ddp"))
        self.register(ModelParallelStrategy())

    def register(self, strategy: BaseTrainingStrategy) -> None:
        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> BaseTrainingStrategy:
        strat = self._strategies.get(name)
        if not strat:
            raise NotFoundError(f"Training strategy '{name}' is not registered. Available: {list(self._strategies.keys())}")
        return strat

    def list_all(self) -> List[BaseTrainingStrategy]:
        return list(self._strategies.values())

    def select_strategy(
        self,
        project: Project,
        config: Optional[TrainingConfiguration],
        eligible_workers: List[ProjectMembership],
    ) -> BaseTrainingStrategy:
        """
        Determine the optimal valid strategy for a project and cluster state.
        Rejects invalid configurations immediately.
        """
        num_workers = len(eligible_workers)
        requested_strategy = (project.training_strategy or "").lower().strip()

        # If user explicitly requested a specific strategy, validate it strictly
        if requested_strategy and requested_strategy in self._strategies:
            strat = self.get(requested_strategy)
            valid, err = strat.validate_project_compatibility(project, config, num_workers)
            if not valid:
                raise ValidationError(f"Strategy '{requested_strategy}' incompatible with current cluster: {err}")
            return strat

        # Auto-selection logic:
        # 1. If only 1 worker or master available -> single_node
        if num_workers <= 1:
            return self.get("single_node")

        # 2. If model architecture is explicitly supported for model parallelism and cluster has >= 2 workers
        arch = (project.model_architecture or "").lower()
        if "pipeline" in arch or "model_parallel" in requested_strategy:
            strat = self.get("model_parallel")
            valid, _ = strat.validate_project_compatibility(project, config, num_workers)
            if valid:
                return strat

        # 3. If cluster has multiple workers, prefer data_parallel if batch size allows, else independent_jobs
        dp_strat = self.get("data_parallel")
        valid, _ = dp_strat.validate_project_compatibility(project, config, num_workers)
        if valid:
            return dp_strat

        return self.get("independent_jobs")

    def create_rendezvous(
        self,
        strategy_name: str,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        workers: List[ProjectMembership],
        master_addr: str = "127.0.0.1",
        master_port: int = 29500,
    ) -> RendezvousState:
        """Initialize rendezvous state for an active run."""
        strat = self.get(strategy_name)
        rendezvous = strat.plan_rendezvous(
            project_id=project_id,
            run_id=run_id,
            workers=workers,
            master_addr=master_addr,
            master_port=master_port,
        )
        self._active_rendezvous[run_id] = rendezvous
        return rendezvous

    def get_rendezvous(self, run_id: uuid.UUID) -> Optional[RendezvousState]:
        return self._active_rendezvous.get(run_id)

    def remove_rendezvous(self, run_id: uuid.UUID) -> None:
        self._active_rendezvous.pop(run_id, None)


# Global registry singleton
strategy_registry = StrategyRegistry()
