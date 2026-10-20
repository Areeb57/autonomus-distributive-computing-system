"""
Audit logging helper for recording operational and security events.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditEvent

logger = get_logger(__name__)


async def record_audit_event(
    db: AsyncSession,
    action: str,
    user_id: Optional[uuid.UUID] = None,
    machine_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditEvent:
    """
    Persist an audit record to the database and structured logs.
    """
    details_str = json.dumps(details) if details else None

    event = AuditEvent(
        action=action,
        user_id=user_id,
        machine_id=machine_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=details_str,
        ip_address=ip_address,
    )

    db.add(event)
    await db.flush()

    logger.info(
        "audit_event_recorded",
        action=action,
        user_id=str(user_id) if user_id else None,
        machine_id=str(machine_id) if machine_id else None,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    return event
