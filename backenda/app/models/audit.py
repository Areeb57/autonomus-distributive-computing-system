"""
Audit event model for security, tracking, and operational visibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """
    Append-only security and operational audit trail.
    
    Tracks authentication, role changes, pairing, and critical project actions.
    """

    __tablename__ = "audit_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    machine_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    # Action e.g. 'auth.login', 'auth.register', 'machine.paired', 'role.changed'
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    details_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped[User | None] = relationship(
        "User",
        back_populates="audit_events",
    )
