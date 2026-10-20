"""
Machine identity, credentials, and pairing challenge models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import ProjectMembership
    from app.models.resource import (
        WorkerResourceSnapshot,
        ResourceAllocation,
        MachineContributionSettings,
    )
    from app.models.training import TrainingTask


class Machine(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Physical or virtual computer registered in the ADC cluster.
    
    Enforces 'One Machine, One Role': active_role must be 'none', 'master', or 'worker'.
    """

    __tablename__ = "machines"

    # Cryptographically random installation ID generated on agent setup
    installation_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    public_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    platform: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    # Role: 'none', 'master', 'worker'
    active_role: Mapped[str] = mapped_column(
        String(32),
        default="none",
        nullable=False,
    )
    # Status: 'offline', 'idle', 'training', 'paused'
    status: Mapped[str] = mapped_column(
        String(32),
        default="offline",
        nullable=False,
    )
    is_online: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Active instance lease token and expiry to detect concurrent launches/stale sessions
    lease_token: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paired_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    paired_user: Mapped[User | None] = relationship(
        "User",
        back_populates="machines",
    )
    credentials: Mapped[List[MachineCredential]] = relationship(
        "MachineCredential",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    pairing_challenges: Mapped[List[PairingChallenge]] = relationship(
        "PairingChallenge",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    resource_snapshots: Mapped[List[WorkerResourceSnapshot]] = relationship(
        "WorkerResourceSnapshot",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    allocations: Mapped[List[ResourceAllocation]] = relationship(
        "ResourceAllocation",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[List[ProjectMembership]] = relationship(
        "ProjectMembership",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    contribution_settings: Mapped[MachineContributionSettings | None] = relationship(
        "MachineContributionSettings",
        back_populates="machine",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tasks: Mapped[List[TrainingTask]] = relationship(
        "TrainingTask",
        back_populates="assigned_machine",
    )


class MachineCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Public keys and access credentials for authenticating machines.
    """

    __tablename__ = "machine_credentials"

    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credential_type: Mapped[str] = mapped_column(
        String(32),
        default="ed25519",
        nullable=False,
    )
    public_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    token_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    machine: Mapped[Machine] = relationship(
        "Machine",
        back_populates="credentials",
    )


class PairingChallenge(Base, UUIDPrimaryKeyMixin):
    """
    Short-lived, single-use browser pairing challenge.
    
    Protects pairing codes against guessing, replay, and brute force.
    """

    __tablename__ = "pairing_challenges"

    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    challenge_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    nonce: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    # Status: 'pending', 'completed', 'expired', 'failed'
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )
    selected_role: Mapped[str] = mapped_column(
        String(32),
        default="worker",
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    machine: Mapped[Machine] = relationship(
        "Machine",
        back_populates="pairing_challenges",
    )
