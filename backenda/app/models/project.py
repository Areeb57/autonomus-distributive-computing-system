"""
Project, project codes, and worker membership models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.machine import Machine
    from app.models.dataset import Dataset, ModelPackage
    from app.models.training import (
        TrainingConfiguration,
        TrainingRun,
        TrainingMetric,
        Checkpoint,
        Artifact,
    )
    from app.models.resource import ResourceAllocation


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Distributed AI training project created by a user."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    training_objective: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    model_architecture: Mapped[str] = mapped_column(
        String(128),
        default="",
        nullable=False,
    )
    # Status: 'online', 'training', 'paused', 'stopped', 'completed', 'looking_for_workers'
    status: Mapped[str] = mapped_column(
        String(32),
        default="online",
        nullable=False,
    )
    # Visibility: 'public', 'unlisted'
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="public",
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Strategy: 'independent_jobs', 'data_parallel', 'model_parallel'
    training_strategy: Mapped[str] = mapped_column(
        String(64),
        default="independent_jobs",
        nullable=False,
    )
    workers_needed: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    min_cpu_cores: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
    )
    min_ram_gb: Mapped[int] = mapped_column(
        Integer,
        default=4,
        nullable=False,
    )
    gpu_recommended: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    min_vram_gb: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    expected_duration: Mapped[str] = mapped_column(
        String(64),
        default="Unknown",
        nullable=False,
    )

    # Relationships
    owner: Mapped[User] = relationship(
        "User",
        back_populates="projects",
    )
    codes: Mapped[List[ProjectCode]] = relationship(
        "ProjectCode",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[List[ProjectMembership]] = relationship(
        "ProjectMembership",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    datasets: Mapped[List[Dataset]] = relationship(
        "Dataset",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    packages: Mapped[List[ModelPackage]] = relationship(
        "ModelPackage",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    training_configs: Mapped[List[TrainingConfiguration]] = relationship(
        "TrainingConfiguration",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    training_runs: Mapped[List[TrainingRun]] = relationship(
        "TrainingRun",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    metrics: Mapped[List[TrainingMetric]] = relationship(
        "TrainingMetric",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    checkpoints: Mapped[List[Checkpoint]] = relationship(
        "Checkpoint",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[List[Artifact]] = relationship(
        "Artifact",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    allocations: Mapped[List[ResourceAllocation]] = relationship(
        "ResourceAllocation",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectCode(Base, UUIDPrimaryKeyMixin):
    """
    Nine-digit project join code (e.g., '123-456-789').
    Generated when project is put online. Allows workers to discover and join.
    """

    __tablename__ = "project_codes"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        index=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
        back_populates="codes",
    )


class ProjectMembership(Base, UUIDPrimaryKeyMixin):
    """
    Membership linking a worker machine and user to a project with allocated resource budgets.
    """

    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "machine_id", name="uq_project_machine"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Status: 'training', 'idle', 'paused', 'offline'
    status: Mapped[str] = mapped_column(
        String(32),
        default="idle",
        nullable=False,
    )
    # Contribution status: 'active', 'paused', 'offline'
    contribution_status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )
    cpu_cores_contributed: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
    )
    ram_contributed_gb: Mapped[float] = mapped_column(
        Float,
        default=4.0,
        nullable=False,
    )
    gpu_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    selected_gpu: Mapped[str] = mapped_column(
        String(128),
        default="",
        nullable=False,
    )
    storage_budget_gb: Mapped[float] = mapped_column(
        Float,
        default=20.0,
        nullable=False,
    )
    network_preference: Mapped[str] = mapped_column(
        String(32),
        default="unlimited",
        nullable=False,
    )
    steps_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    current_batch: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="memberships",
    )
    machine: Mapped[Machine] = relationship(
        "Machine",
        back_populates="memberships",
    )
    user: Mapped[User] = relationship(
        "User",
        back_populates="memberships",
    )
