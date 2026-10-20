"""
Hardware resource telemetry snapshots, allocation records, and contribution settings.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.project import Project
    from app.models.user import User


class WorkerResourceSnapshot(Base, UUIDPrimaryKeyMixin):
    """Periodic hardware capability and utilization telemetry snapshot."""

    __tablename__ = "worker_resource_snapshots"

    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cpu_model: Mapped[str] = mapped_column(
        String(128),
        default="Unknown",
        nullable=False,
    )
    cpu_cores_total: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    cpu_usage_pct: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    ram_total_gb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    ram_available_gb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    ram_usage_pct: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    gpu_model: Mapped[str] = mapped_column(
        String(128),
        default="None",
        nullable=False,
    )
    gpu_memory_total_gb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    gpu_memory_used_gb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    gpu_utilization_pct: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    disk_available_gb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    machine: Mapped[Machine] = relationship(
        "Machine",
        back_populates="resource_snapshots",
    )


class ResourceAllocation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Reserved and active compute resource allocation committed by a worker machine to a project.
    """

    __tablename__ = "resource_allocations"

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
    cpu_cores: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    ram_gb: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    gpu_indices: Mapped[str] = mapped_column(
        String(64),
        default="",
        nullable=False,
    )
    storage_gb: Mapped[float] = mapped_column(
        Float,
        default=10.0,
        nullable=False,
    )
    # Status: 'reserved', 'active', 'released'
    status: Mapped[str] = mapped_column(
        String(32),
        default="reserved",
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="allocations",
    )
    machine: Mapped[Machine] = relationship(
        "Machine",
        back_populates="allocations",
    )


class MachineContributionSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Configurable resource contribution budgets, hardware preferences, and global pause toggle.
    """

    __tablename__ = "machine_contribution_settings"

    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cpu_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    cpu_cores: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
    )
    ram_budget_gb: Mapped[float] = mapped_column(
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
    global_paused: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    machine: Mapped[Machine] = relationship(
        "Machine",
        back_populates="contribution_settings",
    )
    user: Mapped[User] = relationship(
        "User",
        back_populates="contribution_settings",
    )
