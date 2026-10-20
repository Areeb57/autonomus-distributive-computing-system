"""
User schemas for API requests and responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user properties."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=128)


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    display_name: str | None = Field(None, min_length=1, max_length=128)
    avatar_url: str | None = Field(None, max_length=512)


class UserResponse(BaseModel):
    """Public user response — never exposes hashed_password or internal secrets."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    email: str
    username: str
    display_name: str = Field(..., serialization_alias="displayName")
    avatar_url: str | None = Field(None, serialization_alias="avatar")
    is_active: bool = Field(..., serialization_alias="isActive")
    created_at: datetime = Field(..., serialization_alias="createdAt")
