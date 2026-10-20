"""
Pydantic schemas for machine identity, registration, pairing, heartbeats, and roles.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class MachineBase(BaseModel):
    """Base machine properties."""
    installation_id: str = Field(..., min_length=8, max_length=64, description="Unique installation ID")
    name: str = Field(..., min_length=1, max_length=128, description="Machine display name/hostname")
    public_key: str = Field(..., min_length=32, description="Ed25519 public key hex or PEM")
    platform: Optional[str] = Field(None, max_length=64, description="OS platform (windows, linux, darwin)")


class MachineRegisterRequest(MachineBase):
    """Payload to register a new machine with the backend."""
    pass


class MachineResponse(BaseModel):
    """Public machine information."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    installation_id: str = Field(..., serialization_alias="installationId")
    name: str
    public_key: str = Field(..., serialization_alias="publicKey")
    platform: Optional[str] = None
    active_role: str = Field(..., serialization_alias="activeRole")
    status: str
    is_online: bool = Field(..., serialization_alias="isOnline")
    last_heartbeat: Optional[datetime] = Field(None, serialization_alias="lastHeartbeat")
    paired_user_id: Optional[uuid.UUID] = Field(None, serialization_alias="pairedUserId")
    lease_expires_at: Optional[datetime] = Field(None, serialization_alias="leaseExpiresAt")
    created_at: datetime = Field(..., serialization_alias="createdAt")


class MachinePairingChallengeRequest(BaseModel):
    """Agent request to initiate a pairing challenge."""
    installation_id: str = Field(..., description="Machine installation ID")
    timestamp: int = Field(..., description="Unix timestamp of request")
    signature: str = Field(..., description="Ed25519 hex signature over '{installation_id}:{timestamp}'")


class MachinePairingChallengeResponse(BaseModel):
    """Response returned to agent with single-use pairing code."""
    model_config = ConfigDict(populate_by_name=True)

    challenge_code: str = Field(..., serialization_alias="challengeCode")
    expires_at: datetime = Field(..., serialization_alias="expiresAt")
    nonce: str
    message: str = "Enter this 6-character code in the browser to pair your machine."


class PairingCompleteRequest(BaseModel):
    """Browser request to bind a machine to the user account with a chosen role."""
    challenge_code: str = Field(..., min_length=4, max_length=16, description="Pairing code entered by user")
    selected_role: str = Field(..., pattern=r"^(master|worker)$", description="Role to assume: 'master' or 'worker'")


class PairingCompleteResponse(BaseModel):
    """Response returned upon successful pairing."""
    model_config = ConfigDict(populate_by_name=True)

    status: str = "paired"
    message: str = "Machine paired successfully."
    machine: MachineResponse
    lease_token: Optional[str] = Field(None, serialization_alias="leaseToken")


class MachineHeartbeatRequest(BaseModel):
    """Heartbeat sent by agent process to maintain online lease."""
    installation_id: str
    lease_token: str
    status: Optional[str] = Field("idle", description="Current status: idle, training, paused")
    metrics: Optional[Dict[str, Any]] = None


class MachineHeartbeatResponse(BaseModel):
    """Heartbeat acknowledgement and lease renewal."""
    model_config = ConfigDict(populate_by_name=True)

    acknowledged: bool = True
    status: str
    active_role: str = Field(..., serialization_alias="activeRole")
    lease_expires_at: datetime = Field(..., serialization_alias="leaseExpiresAt")


class RoleChangeRequest(BaseModel):
    """Controlled role transition request."""
    new_role: str = Field(..., pattern=r"^(none|master|worker)$", description="New active role")
    force: bool = Field(False, description="Force transition even if previous lease has not fully expired")


class MachineRevokeRequest(BaseModel):
    """Machine credential revocation request."""
    installation_id: str = Field(..., description="Installation ID to revoke")
    reason: Optional[str] = Field("User requested revocation", description="Reason for revocation")
