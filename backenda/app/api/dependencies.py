"""
Shared FastAPI dependencies — database sessions, authentication, and security.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.database.session import get_db_session  # noqa: F401 — re-export
from app.models.user import User

settings = get_settings()


async def get_token_from_request(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Extract JWT access token from Authorization header or HTTP-only cookie.
    
    Prefers 'Authorization: Bearer <token>' header, falls back to 'access_token' cookie.
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    raise AuthenticationError(
        message="Authentication token missing. Provide Authorization header or access_token cookie."
    )


async def get_optional_token_from_request(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract token if present, otherwise return None without raising an error."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return request.cookies.get("access_token")


async def get_current_user(
    token: str = Depends(get_token_from_request),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Validate access token and return the authenticated User from database.
    """
    payload = decode_access_token(
        token=token,
        secret_key=settings.secret_key,
        algorithm=settings.token_algorithm,
    )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError(message="Invalid token payload: missing subject")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError(message="Invalid token payload: malformed subject UUID")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError(message="User account no longer exists")

    if not user.is_active:
        raise AuthenticationError(message="User account is deactivated")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency verifying the user is active."""
    if not current_user.is_active:
        raise AuthenticationError(message="Inactive user account")
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Dependency requiring superuser privileges."""
    if not current_user.is_superuser:
        raise AuthorizationError(message="Superuser privileges required")
    return current_user


async def get_optional_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """Return the authenticated user if token is provided and valid, otherwise None."""
    token = await get_optional_token_from_request(request, authorization)
    if not token:
        return None

    try:
        payload = decode_access_token(
            token=token,
            secret_key=settings.secret_key,
            algorithm=settings.token_algorithm,
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(user_id_str)
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        return user if user and user.is_active else None
    except Exception:
        return None


def require_role(allowed_roles: list[str]):
    """
    Dependency factory ensuring the current user's active machine has one of the allowed roles.
    Allowed roles: 'master', 'worker', 'admin'.
    """
    async def _role_checker(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> User:
        if "admin" in allowed_roles and current_user.is_superuser:
            return current_user

        from app.models.machine import Machine

        # Check user's paired machines for an active matching role
        stmt = select(Machine).where(
            Machine.paired_user_id == current_user.id,
            Machine.active_role.in_(allowed_roles),
            Machine.is_online == True,  # noqa: E712
        )
        matching_machine = (await db.execute(stmt)).scalars().first()

        if not matching_machine and not current_user.is_superuser:
            raise AuthorizationError(
                message=f"Action requires active role: {', '.join(allowed_roles)}. No online paired machine matches.",
                details={"required_roles": allowed_roles},
            )

        return current_user

    return _role_checker


def require_project_owner():
    """
    Dependency ensuring the current user is the owner of the target project.
    """
    async def _owner_checker(
        project_id: uuid.UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> User:
        from app.models.project import Project
        from app.core.exceptions import NotFoundError

        stmt = select(Project).where(Project.id == project_id)
        project = (await db.execute(stmt)).scalar_one_or_none()

        if not project:
            raise NotFoundError(message=f"Project {project_id} not found.")

        if project.owner_id != current_user.id and not current_user.is_superuser:
            raise AuthorizationError(message="Only the project owner can perform this operation.")

        return current_user

    return _owner_checker

