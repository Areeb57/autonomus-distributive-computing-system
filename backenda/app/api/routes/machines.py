"""
Machine API routes — registration, pairing challenges, heartbeats, role management, and revocation.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db_session
from app.core.audit import record_audit_event
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.machine_crypto import verify_machine_signature
from app.core.security import generate_nonce, generate_pairing_code, generate_secure_token
from app.models.machine import Machine, MachineCredential, PairingChallenge
from app.models.resource import WorkerResourceSnapshot
from app.models.user import User
from app.schemas.machine import (
    MachineHeartbeatRequest,
    MachineHeartbeatResponse,
    MachinePairingChallengeRequest,
    MachinePairingChallengeResponse,
    MachineRegisterRequest,
    MachineResponse,
    MachineRevokeRequest,
    PairingCompleteRequest,
    PairingCompleteResponse,
    RoleChangeRequest,
)

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/machines", tags=["Machines"])


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime object is timezone-aware UTC for cross-database compatibility."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _reconcile_machine_online_status(machine: Machine) -> None:
    """Mark machine offline if heartbeat has timed out."""
    if machine.is_online and machine.last_heartbeat:
        timeout = timedelta(seconds=settings.heartbeat_timeout_seconds)
        now = datetime.now(timezone.utc)
        heartbeat_time = ensure_utc(machine.last_heartbeat)
        if heartbeat_time and (now - heartbeat_time > timeout):
            machine.is_online = False
            machine.status = "offline"


@router.post(
    "/register",
    response_model=MachineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register machine public key with backend",
)
async def register_machine(
    payload: MachineRegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> MachineResponse:
    """
    Register a newly installed agent machine and store its Ed25519 public key.
    """
    stmt = select(Machine).where(Machine.installation_id == payload.installation_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        # If public key matches, update display name and platform
        if existing.public_key == payload.public_key.strip():
            existing.name = payload.name.strip()
            if payload.platform:
                existing.platform = payload.platform.strip()
            db.add(existing)
            await db.flush()
            response.status_code = status.HTTP_200_OK
            return MachineResponse.model_validate(existing)
        else:
            raise ConflictError(
                message="Machine installation ID already registered with a different public key. Revoke the existing machine first."
            )

    # Create new Machine record
    machine = Machine(
        installation_id=payload.installation_id,
        name=payload.name.strip(),
        public_key=payload.public_key.strip(),
        platform=payload.platform.strip() if payload.platform else None,
        active_role="none",
        status="offline",
        is_online=False,
    )
    db.add(machine)
    await db.flush()

    # Create credential record
    cred = MachineCredential(
        machine_id=machine.id,
        credential_type="ed25519",
        public_key=machine.public_key,
    )
    db.add(cred)

    await record_audit_event(
        db=db,
        action="machine.register",
        machine_id=machine.id,
        resource_type="machine",
        resource_id=str(machine.id),
        details={"installation_id": machine.installation_id, "name": machine.name},
        ip_address=request.client.host if request.client else None,
    )

    return MachineResponse.model_validate(machine)


@router.post(
    "/pairing/challenge",
    response_model=MachinePairingChallengeResponse,
    summary="Initiate browser pairing challenge from running agent",
)
async def create_pairing_challenge(
    payload: MachinePairingChallengeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MachinePairingChallengeResponse:
    """
    Generate a short-lived single-use pairing code for an agent machine.
    Requires Ed25519 signature verification over '{installation_id}:{timestamp}'.
    """
    # 1. Fetch machine
    stmt = select(Machine).where(Machine.installation_id == payload.installation_id)
    machine = (await db.execute(stmt)).scalar_one_or_none()
    if not machine:
        raise NotFoundError(message="Machine not registered. Run machine registration first.")

    # 2. Check replay prevention timestamp (within 300 seconds)
    current_ts = int(time.time())
    if abs(current_ts - payload.timestamp) > 300:
        raise ValidationError(message="Challenge timestamp expired or skewed. Check system clock.")

    # 3. Verify signature
    msg = f"{payload.installation_id}:{payload.timestamp}".encode("utf-8")
    if not verify_machine_signature(machine.public_key, msg, payload.signature):
        raise AuthenticationError(message="Cryptographic signature verification failed.")

    # 4. Generate unique 6-character pairing code
    code = generate_pairing_code(length=6)
    nonce = generate_nonce(16)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.pairing_code_expiry_seconds)

    # 5. Invalidate any existing pending challenges for this machine
    stmt_pending = (
        update(PairingChallenge)
        .where(
            PairingChallenge.machine_id == machine.id,
            PairingChallenge.status == "pending",
        )
        .values(status="expired")
    )
    await db.execute(stmt_pending)

    # 6. Save new challenge
    challenge = PairingChallenge(
        machine_id=machine.id,
        challenge_code=code,
        nonce=nonce,
        status="pending",
        selected_role="worker",
        attempts=0,
        max_attempts=settings.pairing_max_attempts,
        expires_at=expires_at,
    )
    db.add(challenge)
    await db.flush()

    logger.info(
        "pairing_challenge_created",
        machine_id=str(machine.id),
        installation_id=machine.installation_id,
        code=code,
    )

    return MachinePairingChallengeResponse(
        challenge_code=code,
        expires_at=expires_at,
        nonce=nonce,
    )


@router.post(
    "/pairing/complete",
    response_model=PairingCompleteResponse,
    summary="Complete pairing in browser and assign role",
)
async def complete_pairing(
    payload: PairingCompleteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> PairingCompleteResponse:
    """
    Complete pairing from the browser: binds machine to user and assigns Master or Worker role.
    Enforces 'One Machine, One Role'.
    """
    clean_code = payload.challenge_code.strip().upper()
    now = datetime.now(timezone.utc)

    # Look up challenge
    stmt = (
        select(PairingChallenge)
        .where(PairingChallenge.challenge_code == clean_code)
    )
    challenge = (await db.execute(stmt)).scalar_one_or_none()

    if not challenge:
        raise NotFoundError(message="Invalid pairing code.")

    # Check attempt limits
    if challenge.attempts >= challenge.max_attempts:
        challenge.status = "failed"
        db.add(challenge)
        raise ValidationError(message="Pairing code has been locked due to too many failed attempts.")

    # Check expiration and status
    chal_expires = ensure_utc(challenge.expires_at)
    if challenge.status != "pending" or (chal_expires and chal_expires < now):
        challenge.status = "expired"
        db.add(challenge)
        raise ValidationError(message="Pairing code has expired or was already used.")

    # Fetch machine
    stmt_m = select(Machine).where(Machine.id == challenge.machine_id)
    machine = (await db.execute(stmt_m)).scalar_one_or_none()
    if not machine:
        raise NotFoundError(message="Machine record not found.")

    # Enforce 'One Machine, One Role':
    # If the machine is already registered to another user, verify permission or disallow
    if machine.paired_user_id and machine.paired_user_id != current_user.id:
        # If the other session's lease is still active, disallow hijacking
        lease_expires = ensure_utc(machine.lease_expires_at)
        if machine.is_online and lease_expires and lease_expires > now:
            raise ConflictError(message="This machine is currently active and paired with another account.")

    # Issue instance lease
    lease_token = generate_secure_token(32)
    lease_expires_at = now + timedelta(seconds=settings.lease_duration_seconds)

    # Bind machine to user and set authoritative role
    machine.paired_user_id = current_user.id
    machine.active_role = payload.selected_role  # 'master' or 'worker'
    machine.status = "idle"
    machine.is_online = True
    machine.last_heartbeat = now
    machine.lease_token = lease_token
    machine.lease_expires_at = lease_expires_at
    db.add(machine)

    # Mark challenge completed
    challenge.status = "completed"
    challenge.user_id = current_user.id
    challenge.selected_role = payload.selected_role
    db.add(challenge)

    await record_audit_event(
        db=db,
        action="machine.paired",
        user_id=current_user.id,
        machine_id=machine.id,
        resource_type="machine",
        resource_id=str(machine.id),
        details={"role": payload.selected_role, "installation_id": machine.installation_id},
        ip_address=request.client.host if request.client else None,
    )

    return PairingCompleteResponse(
        status="paired",
        message=f"Machine paired as {payload.selected_role.title()}.",
        machine=MachineResponse.model_validate(machine),
        lease_token=lease_token,
    )


@router.post(
    "/heartbeat",
    response_model=MachineHeartbeatResponse,
    summary="Agent heartbeat and lease renewal",
)
async def heartbeat(
    payload: MachineHeartbeatRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MachineHeartbeatResponse:
    """
    Heartbeat sent by agent process. Renews active lease and updates status/telemetry.
    """
    now = datetime.now(timezone.utc)

    stmt = select(Machine).where(Machine.installation_id == payload.installation_id)
    machine = (await db.execute(stmt)).scalar_one_or_none()

    if not machine:
        raise NotFoundError(message="Machine not registered.")

    # Check lease token
    if not machine.lease_token or machine.lease_token != payload.lease_token:
        raise AuthenticationError(message="Invalid or missing lease token. Agent must re-pair or re-authenticate.")

    # Check if lease expired and conflicting process acquired it
    lease_expires = ensure_utc(machine.lease_expires_at)
    if lease_expires and lease_expires < now - timedelta(seconds=settings.heartbeat_timeout_seconds):
        machine.is_online = False
        machine.status = "offline"
        db.add(machine)
        raise ConflictError(message="Instance lease expired. Reconnect or re-pair.")

    # Renew lease
    new_expires_at = now + timedelta(seconds=settings.lease_duration_seconds)
    machine.last_heartbeat = now
    machine.is_online = True
    machine.lease_expires_at = new_expires_at
    if payload.status:
        machine.status = payload.status
    db.add(machine)

    # Record hardware metrics snapshot if provided
    if payload.metrics:
        snapshot = WorkerResourceSnapshot(
            machine_id=machine.id,
            cpu_model=payload.metrics.get("cpu_model", "Unknown"),
            cpu_cores_total=int(payload.metrics.get("cpu_cores", 1)),
            cpu_usage_pct=float(payload.metrics.get("cpu_utilization", 0.0)),
            ram_total_gb=float(payload.metrics.get("ram_total_gb", 0.0)),
            ram_available_gb=float(payload.metrics.get("ram_available_gb", 0.0)),
            ram_usage_pct=float(payload.metrics.get("ram_usage_pct", 0.0)),
            gpu_model=payload.metrics.get("gpu_model", "None"),
            gpu_memory_total_gb=float(payload.metrics.get("gpu_memory_total_gb", 0.0)),
            gpu_memory_used_gb=float(payload.metrics.get("gpu_memory_used_gb", 0.0)),
            gpu_utilization_pct=float(payload.metrics.get("gpu_utilization_pct", 0.0)),
            disk_available_gb=float(payload.metrics.get("disk_available_gb", 0.0)),
        )
        db.add(snapshot)

    return MachineHeartbeatResponse(
        acknowledged=True,
        status=machine.status,
        active_role=machine.active_role,
        lease_expires_at=new_expires_at,
    )


@router.get(
    "/me",
    response_model=List[MachineResponse],
    summary="Get user's paired machines and current machine status",
)
async def get_my_machines(
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_active_user),
) -> List[MachineResponse]:
    """
    Return all paired machines belonging to the authenticated user, or the machine matching X-Installation-Id.
    """
    if x_installation_id:
        stmt = select(Machine).where(Machine.installation_id == x_installation_id)
        m = (await db.execute(stmt)).scalar_one_or_none()
        if m:
            _reconcile_machine_online_status(m)
            db.add(m)
            return [MachineResponse.model_validate(m)]
        raise NotFoundError(message="Machine not found.")

    if not current_user:
        raise AuthenticationError(message="Authentication required to list paired machines.")

    stmt = select(Machine).where(Machine.paired_user_id == current_user.id)
    machines = (await db.execute(stmt)).scalars().all()

    for m in machines:
        _reconcile_machine_online_status(m)
        db.add(m)

    return [MachineResponse.model_validate(m) for m in machines]


@router.post(
    "/role-change",
    response_model=MachineResponse,
    summary="Controlled role transition (Master vs Worker)",
)
async def change_role(
    payload: RoleChangeRequest,
    request: Request,
    x_installation_id: Optional[str] = Header(None, alias="X-Installation-Id"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MachineResponse:
    """
    Change machine role between 'master', 'worker', and 'none'.
    Enforces that machines currently executing training jobs cannot change role until stopped.
    """
    # Find machine owned by current user
    stmt = select(Machine).where(Machine.paired_user_id == current_user.id)
    if x_installation_id:
        stmt = stmt.where(Machine.installation_id == x_installation_id)

    machine = (await db.execute(stmt)).scalars().first()
    if not machine:
        raise NotFoundError(message="No paired machine found to change role.")

    # Guard: cannot switch role while in active training
    if machine.status == "training" and not payload.force:
        raise ConflictError(message="Cannot change role while training is active. Stop or pause training first.")

    old_role = machine.active_role
    machine.active_role = payload.new_role
    if payload.new_role == "none":
        machine.is_online = False
        machine.status = "offline"

    db.add(machine)

    await record_audit_event(
        db=db,
        action="machine.role_change",
        user_id=current_user.id,
        machine_id=machine.id,
        resource_type="machine",
        resource_id=str(machine.id),
        details={"old_role": old_role, "new_role": payload.new_role},
        ip_address=request.client.host if request.client else None,
    )

    return MachineResponse.model_validate(machine)


@router.post(
    "/revoke",
    response_model=dict,
    summary="Revoke machine credentials and disconnect",
)
async def revoke_machine(
    payload: MachineRevokeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Revoke a machine's credentials, cancel active leases, and disconnect it.
    """
    stmt = select(Machine).where(
        Machine.installation_id == payload.installation_id,
        or_(Machine.paired_user_id == current_user.id, current_user.is_superuser == True),  # noqa: E712
    )
    machine = (await db.execute(stmt)).scalar_one_or_none()

    if not machine:
        raise NotFoundError(message="Machine not found or not owned by current user.")

    # Revoke credentials
    stmt_cred = (
        update(MachineCredential)
        .where(MachineCredential.machine_id == machine.id)
        .values(
            is_revoked=True,
            revoked_at=datetime.now(timezone.utc),
            revoked_reason=payload.reason,
        )
    )
    await db.execute(stmt_cred)

    # Disconnect and reset machine state
    machine.lease_token = None
    machine.lease_expires_at = None
    machine.is_online = False
    machine.status = "offline"
    machine.active_role = "none"
    machine.paired_user_id = None
    db.add(machine)

    await record_audit_event(
        db=db,
        action="machine.revoked",
        user_id=current_user.id,
        machine_id=machine.id,
        resource_type="machine",
        resource_id=str(machine.id),
        details={"reason": payload.reason, "installation_id": machine.installation_id},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "status": "revoked",
        "message": f"Machine {machine.name} has been revoked and disconnected.",
    }
