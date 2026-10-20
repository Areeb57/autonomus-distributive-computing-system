"""
Authentication API routes — register, login, logout, me, refresh, sessions, password change, CSRF.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db_session
from app.core.audit import record_audit_event
from app.core.config import get_settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User, UserSession
from app.schemas.auth import (
    CSRFResponse,
    ChangePasswordRequest,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
)
from app.schemas.user import UserResponse, UserUpdate

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set HTTP-only session cookies on the response."""
    cookie_kwargs = {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.is_production,
    }
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **cookie_kwargs,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        **cookie_kwargs,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear HTTP-only session cookies."""
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")


@router.get(
    "/csrf",
    response_model=CSRFResponse,
    summary="Get CSRF token",
)
async def get_csrf_token(
    request: Request,
    response: Response,
) -> CSRFResponse:
    """
    Return a CSRF token and set the csrftoken cookie.
    Frontend sends this value in the X-CSRF-Token header on mutating requests.
    """
    token = request.cookies.get(CSRF_COOKIE_NAME) or generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite="lax",
        secure=settings.is_production,
    )
    response.headers[CSRF_HEADER_NAME] = token
    return CSRFResponse(csrf_token=token)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Register a new user account, track session, and return authenticated tokens.
    """
    # Check if username or email is already taken
    stmt = select(User).where(
        or_(
            User.email == payload.email.lower().strip(),
            User.username == payload.username.lower().strip(),
        )
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        if existing.email == payload.email.lower().strip():
            raise ConflictError(message="A user with this email address already exists.")
        raise ConflictError(message="A user with this username already exists.")

    # Create new user
    hashed_pwd = hash_password(payload.password)
    user = User(
        email=payload.email.lower().strip(),
        username=payload.username.lower().strip(),
        display_name=payload.display_name or payload.username,
        hashed_password=hashed_pwd,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Generate JWT tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "email": user.email},
        secret_key=settings.secret_key,
        algorithm=settings.token_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "username": user.username},
        secret_key=settings.secret_key,
        algorithm=settings.token_algorithm,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )

    # Track active session
    user_session = UserSession(
        user_id=user.id,
        session_token_hash=hash_token(refresh_token),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(user_session)

    # Set cookies
    _set_auth_cookies(response, access_token, refresh_token)

    # Audit log
    await record_audit_event(
        db=db,
        action="auth.register",
        user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"username": user.username, "email": user.email},
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with username or email and password",
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Authenticate user credentials, start tracked session, return tokens, set cookies.
    """
    identifier = payload.username_or_email.lower().strip()

    stmt = select(User).where(
        or_(
            User.email == identifier,
            User.username == identifier,
        )
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError(message="Invalid credentials. Check your username/email and password.")

    if not user.is_active:
        raise AuthenticationError(message="This account has been deactivated.")

    # Generate JWT tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "email": user.email},
        secret_key=settings.secret_key,
        algorithm=settings.token_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "username": user.username},
        secret_key=settings.secret_key,
        algorithm=settings.token_algorithm,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )

    # Track active session in database
    user_session = UserSession(
        user_id=user.id,
        session_token_hash=hash_token(refresh_token),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(user_session)

    # Set cookies
    _set_auth_cookies(response, access_token, refresh_token)

    # Audit log
    await record_audit_event(
        db=db,
        action="auth.login",
        user_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"username": user.username},
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out, revoke current session and clear cookies",
)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_active_user),
) -> LogoutResponse:
    """
    Clear session cookies, mark session inactive, and record logout event.
    """
    # If refresh token is present in cookies or payload, deactivate that session
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token and current_user:
        token_h = hash_token(refresh_token)
        stmt = update(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.session_token_hash == token_h,
        ).values(is_active=False)
        await db.execute(stmt)

    _clear_auth_cookies(response)

    if current_user:
        await record_audit_event(
            db=db,
            action="auth.logout",
            user_id=current_user.id,
            resource_type="user",
            resource_id=str(current_user.id),
            details={"username": current_user.username},
            ip_address=request.client.host if request.client else None,
        )

    return LogoutResponse()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Return the profile of the currently authenticated user.
    """
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile (displayName, avatar)",
)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Update user profile attributes (display name, avatar).
    """
    if payload.display_name is not None:
        current_user.display_name = payload.display_name.strip()
    if payload.avatar_url is not None:
        current_user.avatar_url = payload.avatar_url.strip()

    db.add(current_user)
    await db.flush()

    return UserResponse.model_validate(current_user)


@router.post(
    "/change-password",
    response_model=LogoutResponse,
    summary="Change user password and revoke other sessions",
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> LogoutResponse:
    """
    Verify current password, update password hash, and revoke existing sessions.
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise AuthenticationError(message="Current password does not match.")

    current_user.hashed_password = hash_password(payload.new_password)
    db.add(current_user)

    # Invalidate all active sessions for security
    stmt = update(UserSession).where(
        UserSession.user_id == current_user.id
    ).values(is_active=False)
    await db.execute(stmt)

    _clear_auth_cookies(response)

    await record_audit_event(
        db=db,
        action="auth.password_change",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        ip_address=request.client.host if request.client else None,
    )

    return LogoutResponse(
        status="password_changed",
        message="Password changed successfully. Please log in again.",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using refresh token",
)
async def refresh_token(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access token and refresh token.
    Validates that the session is still active in the database.
    """
    token_str = None
    if payload and payload.refresh_token:
        token_str = payload.refresh_token
    elif request.cookies.get("refresh_token"):
        token_str = request.cookies.get("refresh_token")

    if not token_str:
        raise AuthenticationError(message="Refresh token missing from request body or cookies.")

    decoded = decode_token(token_str, secret_key=settings.secret_key, algorithm=settings.token_algorithm)
    if decoded.get("type") != "refresh":
        raise AuthenticationError(message="Invalid token type, expected refresh token.")

    user_id_str = decoded.get("sub")
    if not user_id_str:
        raise AuthenticationError(message="Invalid token payload.")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError(message="Malformed token subject.")

    # Verify session is still active in database
    token_h = hash_token(token_str)
    session_stmt = select(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.session_token_hash == token_h,
        UserSession.is_active == True,  # noqa: E712
    )
    user_session = (await db.execute(session_stmt)).scalar_one_or_none()
    if not user_session:
        raise AuthenticationError(message="Session has been revoked or expired.")

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not user.is_active:
        raise AuthenticationError(message="User account no longer active.")

    # Issue new token pair
    new_access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "email": user.email},
        secret_key=settings.secret_key,
        algorithm=settings.token_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id), "username": user.username},
        secret_key=settings.secret_key,
        algorithm=settings.token_algorithm,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )

    # Rotate session token hash in DB
    user_session.session_token_hash = hash_token(new_refresh_token)
    user_session.last_activity = datetime.now(timezone.utc)
    db.add(user_session)

    _set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/sessions",
    response_model=List[SessionResponse],
    summary="List active sessions for current user",
)
async def list_sessions(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> List[SessionResponse]:
    """
    List all active login sessions associated with the user account.
    """
    stmt = (
        select(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.is_active == True)  # noqa: E712
        .order_by(UserSession.last_activity.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return [SessionResponse.model_validate(s) for s in sessions]


@router.delete(
    "/sessions/{session_id}",
    response_model=LogoutResponse,
    summary="Revoke an active session",
)
async def revoke_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> LogoutResponse:
    """
    Revoke a specific active session.
    """
    stmt = select(UserSession).where(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id,
    )
    session_obj = (await db.execute(stmt)).scalar_one_or_none()

    if not session_obj:
        raise NotFoundError(message="Session not found.")

    session_obj.is_active = False
    db.add(session_obj)

    return LogoutResponse(status="revoked", message="Session revoked successfully.")
