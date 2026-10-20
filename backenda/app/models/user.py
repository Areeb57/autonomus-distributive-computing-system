"""
User and UserSession database models for authentication and session management.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.project import Project, ProjectMembership
    from app.models.resource import MachineContributionSettings
    from app.models.audit import AuditEvent


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registered user account in ADC."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    machines: Mapped[List[Machine]] = relationship(
        "Machine",
        back_populates="paired_user",
    )
    projects: Mapped[List[Project]] = relationship(
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[List[ProjectMembership]] = relationship(
        "ProjectMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[List[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="user",
    )
    sessions: Mapped[List[UserSession]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    contribution_settings: Mapped[List[MachineContributionSettings]] = relationship(
        "MachineContributionSettings",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Active authenticated session tracking for a user.
    
    Enables remote logout, session listing, device tracking, and token revocation.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="sessions",
    )
