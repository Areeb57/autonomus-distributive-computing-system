"""
Explicit finite state machines for Projects, Workers, and Training Tasks.

Enforces legal transition rules and prevents contradictory cluster states.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set

from app.core.exceptions import ConflictError, ValidationError


class ProjectState(str, Enum):
    """Explicit lifecycle states for distributed training projects."""
    DRAFT = "draft"
    ONLINE = "online"
    LOOKING_FOR_WORKERS = "looking_for_workers"
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSE_REQUESTED = "pause_requested"
    PAUSED = "paused"
    STOP_REQUESTED = "stop_requested"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerState(str, Enum):
    """Explicit lifecycle states for volunteer worker compute nodes."""
    OFFLINE = "offline"
    ONLINE = "online"
    IDLE = "idle"
    ELIGIBLE = "eligible"
    ASSIGNED = "assigned"
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSE_REQUESTED = "pause_requested"
    PAUSED = "paused"
    STOP_REQUESTED = "stop_requested"
    STOPPED = "stopped"
    FAILED = "failed"


class TaskState(str, Enum):
    """Execution states for discrete training step tasks."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# ── Legal State Transitions ──────────────────────────────────────────────────

PROJECT_TRANSITIONS: Dict[str, Set[str]] = {
    ProjectState.DRAFT.value: {
        ProjectState.ONLINE.value,
        ProjectState.LOOKING_FOR_WORKERS.value,
        ProjectState.CANCELLED.value,
    },
    ProjectState.ONLINE.value: {
        ProjectState.LOOKING_FOR_WORKERS.value,
        ProjectState.PREPARING.value,
        ProjectState.RUNNING.value,
        ProjectState.PAUSED.value,
        ProjectState.STOPPED.value,
        ProjectState.CANCELLED.value,
    },
    ProjectState.LOOKING_FOR_WORKERS.value: {
        ProjectState.PREPARING.value,
        ProjectState.RUNNING.value,
        ProjectState.PAUSED.value,
        ProjectState.STOPPED.value,
        ProjectState.CANCELLED.value,
    },
    ProjectState.PREPARING.value: {
        ProjectState.RUNNING.value,
        ProjectState.PAUSED.value,
        ProjectState.STOPPED.value,
        ProjectState.FAILED.value,
    },
    ProjectState.RUNNING.value: {
        ProjectState.PAUSE_REQUESTED.value,
        ProjectState.PAUSED.value,
        ProjectState.STOP_REQUESTED.value,
        ProjectState.STOPPED.value,
        ProjectState.COMPLETED.value,
        ProjectState.FAILED.value,
    },
    ProjectState.PAUSE_REQUESTED.value: {
        ProjectState.PAUSED.value,
        ProjectState.RUNNING.value,
        ProjectState.STOPPED.value,
    },
    ProjectState.PAUSED.value: {
        ProjectState.RUNNING.value,
        ProjectState.ONLINE.value,
        ProjectState.LOOKING_FOR_WORKERS.value,
        ProjectState.STOPPED.value,
        ProjectState.CANCELLED.value,
    },
    ProjectState.STOP_REQUESTED.value: {
        ProjectState.STOPPED.value,
        ProjectState.FAILED.value,
    },
    ProjectState.STOPPED.value: {
        ProjectState.ONLINE.value,  # Restarting
        ProjectState.LOOKING_FOR_WORKERS.value,
        ProjectState.COMPLETED.value,
    },
    ProjectState.COMPLETED.value: set(),  # Terminal state
    ProjectState.FAILED.value: {
        ProjectState.ONLINE.value,  # Retry after fix
    },
    ProjectState.CANCELLED.value: set(),  # Terminal state
}

WORKER_TRANSITIONS: Dict[str, Set[str]] = {
    WorkerState.OFFLINE.value: {
        WorkerState.ONLINE.value,
        WorkerState.IDLE.value,
    },
    WorkerState.ONLINE.value: {
        WorkerState.IDLE.value,
        WorkerState.ELIGIBLE.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.IDLE.value: {
        WorkerState.ELIGIBLE.value,
        WorkerState.ASSIGNED.value,
        WorkerState.PAUSED.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.ELIGIBLE.value: {
        WorkerState.ASSIGNED.value,
        WorkerState.IDLE.value,
        WorkerState.PAUSED.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.ASSIGNED.value: {
        WorkerState.PREPARING.value,
        WorkerState.RUNNING.value,
        WorkerState.IDLE.value,
        WorkerState.FAILED.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.PREPARING.value: {
        WorkerState.RUNNING.value,
        WorkerState.FAILED.value,
        WorkerState.IDLE.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.RUNNING.value: {
        WorkerState.PAUSE_REQUESTED.value,
        WorkerState.PAUSED.value,
        WorkerState.STOP_REQUESTED.value,
        WorkerState.STOPPED.value,
        WorkerState.IDLE.value,  # Task finished
        WorkerState.FAILED.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.PAUSE_REQUESTED.value: {
        WorkerState.PAUSED.value,
        WorkerState.RUNNING.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.PAUSED.value: {
        WorkerState.IDLE.value,
        WorkerState.RUNNING.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.STOP_REQUESTED.value: {
        WorkerState.STOPPED.value,
        WorkerState.IDLE.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.STOPPED.value: {
        WorkerState.IDLE.value,
        WorkerState.OFFLINE.value,
    },
    WorkerState.FAILED.value: {
        WorkerState.IDLE.value,
        WorkerState.OFFLINE.value,
    },
}

TASK_TRANSITIONS: Dict[str, Set[str]] = {
    TaskState.PENDING.value: {
        TaskState.ASSIGNED.value,
        TaskState.FAILED.value,
    },
    TaskState.ASSIGNED.value: {
        TaskState.IN_PROGRESS.value,
        TaskState.PENDING.value,  # Lease expired / reclaimed
        TaskState.TIMEOUT.value,
        TaskState.FAILED.value,
    },
    TaskState.IN_PROGRESS.value: {
        TaskState.COMPLETED.value,
        TaskState.PAUSED.value,
        TaskState.FAILED.value,
        TaskState.TIMEOUT.value,
    },
    TaskState.PAUSED.value: {
        TaskState.IN_PROGRESS.value,
        TaskState.FAILED.value,
    },
    TaskState.COMPLETED.value: set(),  # Terminal state
    TaskState.FAILED.value: {
        TaskState.PENDING.value,  # Eligible for retry
    },
    TaskState.TIMEOUT.value: {
        TaskState.PENDING.value,  # Reclaim to pending queue
    },
}


def can_transition_project(current_state: str, new_state: str) -> bool:
    """Return True if project state transition is legally permissible."""
    if current_state == new_state:
        return True
    allowed = PROJECT_TRANSITIONS.get(current_state, set())
    return new_state in allowed


def assert_project_transition(current_state: str, new_state: str) -> None:
    """Validate project transition, raising ConflictError on illegal transition."""
    if not can_transition_project(current_state, new_state):
        raise ConflictError(
            f"Invalid project transition from '{current_state}' to '{new_state}'. "
            f"Allowed next states: {list(PROJECT_TRANSITIONS.get(current_state, []))}"
        )


def can_transition_worker(current_state: str, new_state: str) -> bool:
    """Return True if worker state transition is legally permissible."""
    if current_state == new_state:
        return True
    allowed = WORKER_TRANSITIONS.get(current_state, set())
    return new_state in allowed


def assert_worker_transition(current_state: str, new_state: str) -> None:
    """Validate worker transition, raising ConflictError on illegal transition."""
    if not can_transition_worker(current_state, new_state):
        raise ConflictError(
            f"Invalid worker transition from '{current_state}' to '{new_state}'. "
            f"Allowed next states: {list(WORKER_TRANSITIONS.get(current_state, []))}"
        )


def can_transition_task(current_state: str, new_state: str) -> bool:
    """Return True if task state transition is legally permissible."""
    if current_state == new_state:
        return True
    allowed = TASK_TRANSITIONS.get(current_state, set())
    return new_state in allowed


def assert_task_transition(current_state: str, new_state: str) -> None:
    """Validate task transition, raising ConflictError on illegal transition."""
    if not can_transition_task(current_state, new_state):
        raise ConflictError(
            f"Invalid task transition from '{current_state}' to '{new_state}'. "
            f"Allowed next states: {list(TASK_TRANSITIONS.get(current_state, []))}"
        )
