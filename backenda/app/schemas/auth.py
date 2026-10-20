"""
Authentication schemas for registration, login, token refresh, sessions, and password management.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserResponse


class RegisterRequest(BaseModel):
    """Registration request payload."""
    email: str = Field(..., description="User's email address")
    username: str = Field(..., min_length=3, max_length=64, description="Alphanumeric username")
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext password (min 8 chars)")
    display_name: str | None = Field(None, max_length=128, description="Display name / full name")


class LoginRequest(BaseModel):
    """Login request payload — accepts email or username."""
    username_or_email: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Authentication response returning access and refresh tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request payload."""
    refresh_token: str


class LogoutResponse(BaseModel):
    """Logout confirmation response."""
    status: str = "logged_out"
    message: str = "Successfully logged out"


class ChangePasswordRequest(BaseModel):
    """Password change request payload."""
    current_password: str = Field(..., description="Current plaintext password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (min 8 chars)")


class SessionResponse(BaseModel):
    """User session representation."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    ip_address: str | None = Field(None, serialization_alias="ipAddress")
    user_agent: str | None = Field(None, serialization_alias="userAgent")
    is_active: bool = Field(..., serialization_alias="isActive")
    expires_at: datetime = Field(..., serialization_alias="expiresAt")
    last_activity: datetime = Field(..., serialization_alias="lastActivity")
    created_at: datetime = Field(..., serialization_alias="createdAt")


class CSRFResponse(BaseModel):
    """CSRF token response."""
    csrf_token: str = Field(..., serialization_alias="csrfToken")
