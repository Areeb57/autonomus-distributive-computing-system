"""
Training execution, configurations, tasks, metrics, checkpoints, and artifacts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.machine import Machine


class TrainingConfiguration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Hyperparameters and configuration for training a project."""

    __tablename__ = "training_configurations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_size: Mapped[int] = mapped_column(
        Integer,
        default=16,
        nullable=False,
    )
    total_steps: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        nullable=False,
    )
    learning_rate: Mapped[str] = mapped_column(
        String(32),
        default="0.0001",
        nullable=False,
    )
    optimizer: Mapped[str] = mapped_column(
        String(32),
        default="adamw",
        nullable=False,
    )
    # Precision: 'fp16', 'bf16', 'fp32'
    precision: Mapped[str] = mapped_column(
        String(16),
        default="fp16",
        nullable=False,
    )
    checkpoint_interval: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
    )
    gradient_accumulation_steps: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    extra_args_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="training_configs",
    )


class TrainingRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An execution instance of training for a project."""

    __tablename__ = "training_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    # Status: 'pending', 'running', 'paused', 'completed', 'failed', 'stopped'
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )
    current_step: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_steps: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        nullable=False,
    )
    current_loss: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    training_speed: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="training_runs",
    )
    tasks: Mapped[List[TrainingTask]] = relationship(
        "TrainingTask",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    metrics: Mapped[List[TrainingMetric]] = relationship(
        "TrainingMetric",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    checkpoints: Mapped[List[Checkpoint]] = relationship(
        "Checkpoint",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class TrainingTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Discrete unit of training work assigned to a worker machine with lease protection."""

    __tablename__ = "training_tasks"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("training_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_machine_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Type: 'batch', 'epoch', 'evaluation', 'sync'
    task_type: Mapped[str] = mapped_column(
        String(32),
        default="batch",
        nullable=False,
    )
    step_start: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    step_end: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    # Status: 'pending', 'assigned', 'in_progress', 'completed', 'failed', 'timeout'
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )
    lease_token: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    result_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    run: Mapped[TrainingRun] = relationship(
        "TrainingRun",
        back_populates="tasks",
    )
    assigned_machine: Mapped[Machine | None] = relationship(
        "Machine",
        back_populates="tasks",
    )


class TrainingMetric(Base, UUIDPrimaryKeyMixin):
    """Time-series telemetry metric emitted during training."""

    __tablename__ = "training_metrics"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("training_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    loss: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    speed: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    cluster_cpu_util: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    cluster_gpu_util: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    ram_util_gb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="metrics",
    )
    run: Mapped[TrainingRun] = relationship(
        "TrainingRun",
        back_populates="metrics",
    )


class Checkpoint(Base, UUIDPrimaryKeyMixin):
    """Model weights checkpoint saved during training."""

    __tablename__ = "checkpoints"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("training_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    is_validated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    metrics_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="checkpoints",
    )
    run: Mapped[TrainingRun] = relationship(
        "TrainingRun",
        back_populates="checkpoints",
    )


class Artifact(Base, UUIDPrimaryKeyMixin):
    """Generated training artifact (exported model, log, chart, etc.)."""

    __tablename__ = "artifacts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("training_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Type: 'model', 'log', 'plot', 'tensorboard'
    artifact_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="artifacts",
    )
