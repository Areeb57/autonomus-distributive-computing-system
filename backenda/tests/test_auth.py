"""
Tests for authentication endpoints: registration, login, logout, me, refresh.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.user import User


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "adc-backend"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, test_session: AsyncSession):
    """Test successful user registration."""
    payload = {
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "Password123!",
        "display_name": "Test User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "testuser"
    assert data["user"]["email"] == "testuser@example.com"
    assert data["user"]["displayName"] == "Test User"
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]

    # Check cookies were set
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    # Verify user exists in database
    stmt = select(User).where(User.username == "testuser")
    user = (await test_session.execute(stmt)).scalar_one_or_none()
    assert user is not None
    assert user.email == "testuser@example.com"

    # Verify audit event was created
    audit_stmt = select(AuditEvent).where(AuditEvent.action == "auth.register")
    event = (await test_session.execute(audit_stmt)).scalar_one_or_none()
    assert event is not None
    assert event.user_id == user.id


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Test registering with an existing email returns 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "username": "userone",
        "password": "Password123!",
        "display_name": "User One",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with same email
    payload2 = {
        "email": "duplicate@example.com",
        "username": "usertwo",
        "password": "Password123!",
        "display_name": "User Two",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409
    error_data = res2.json()
    assert error_data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Test registering with an existing username returns 409 Conflict."""
    payload = {
        "email": "unique1@example.com",
        "username": "sameuser",
        "password": "Password123!",
        "display_name": "User 1",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    payload2 = {
        "email": "unique2@example.com",
        "username": "sameuser",
        "password": "Password123!",
        "display_name": "User 2",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Test registering with short password returns 422 Validation Error."""
    payload = {
        "email": "shortpass@example.com",
        "username": "shortpass",
        "password": "123",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test login with valid username and password."""
    # Register
    reg_payload = {
        "email": "loginuser@example.com",
        "username": "loginuser",
        "password": "Password123!",
        "display_name": "Login User",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # Login with username
    login_payload = {
        "username_or_email": "loginuser",
        "password": "Password123!",
    }
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "loginuser"
    assert "access_token" in res.cookies

    # Login with email
    login_email_payload = {
        "username_or_email": "loginuser@example.com",
        "password": "Password123!",
    }
    res_email = await client.post("/api/v1/auth/login", json=login_email_payload)
    assert res_email.status_code == 200


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """Test login with wrong password returns 401."""
    reg_payload = {
        "email": "wrongpwd@example.com",
        "username": "wrongpwd",
        "password": "Password123!",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "username_or_email": "wrongpwd",
        "password": "IncorrectPassword!",
    }
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_auth_me_bearer_and_cookie(client: AsyncClient):
    """Test /api/v1/auth/me with Bearer token and with cookie."""
    # Register
    reg_payload = {
        "email": "me_user@example.com",
        "username": "me_user",
        "password": "Password123!",
        "display_name": "Me User",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    # 1. Access with Bearer token
    res1 = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 200
    assert res1.json()["username"] == "me_user"
    assert res1.json()["displayName"] == "Me User"

    # 2. Access with cookie
    res2 = await client.get(
        "/api/v1/auth/me",
        cookies={"access_token": token},
    )
    assert res2.status_code == 200
    assert res2.json()["username"] == "me_user"

    # 3. Access without token returns 401 (clear client cookie jar first)
    client.cookies.clear()
    res3 = await client.get("/api/v1/auth/me")
    assert res3.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Test refreshing tokens with valid refresh token."""
    reg_payload = {
        "email": "refresh_user@example.com",
        "username": "refresh_user",
        "password": "Password123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    refresh_tok = reg_res.json()["refresh_token"]

    # Request refresh via payload
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_tok})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["username"] == "refresh_user"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout clears cookies."""
    reg_payload = {
        "email": "logout_user@example.com",
        "username": "logout_user",
        "password": "Password123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    # Call logout
    res = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "logged_out"


@pytest.mark.asyncio
async def test_csrf_endpoint_and_protection(client: AsyncClient):
    """Test CSRF token issuance and enforcement on cookie-based requests."""
    # 1. Get CSRF token
    csrf_res = await client.get("/api/v1/auth/csrf")
    assert csrf_res.status_code == 200
    csrf_token = csrf_res.json()["csrfToken"]
    assert len(csrf_token) > 10

    # 2. Register user to get cookies
    client.cookies.clear()
    reg_payload = {
        "email": "csrf_test@example.com",
        "username": "csrf_test",
        "password": "Password123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # 3. Mutating request with cookie auth but without CSRF header should fail (403)
    client.cookies.set("csrftoken", "dummy-csrf-token")
    change_res = await client.patch(
        "/api/v1/auth/me",
        json={"display_name": "New Name"},
    )
    assert change_res.status_code == 403
    assert change_res.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    # 4. Mutating request with matching CSRF header succeeds
    client.cookies.set("csrftoken", "valid-csrf-token")
    change_res2 = await client.patch(
        "/api/v1/auth/me",
        json={"display_name": "New Name"},
        headers={"X-CSRF-Token": "valid-csrf-token"},
    )
    assert change_res2.status_code == 200
    assert change_res2.json()["displayName"] == "New Name"


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient):
    """Test updating user profile details."""
    client.cookies.clear()
    reg_payload = {
        "email": "update_me@example.com",
        "username": "update_me",
        "password": "Password123!",
        "display_name": "Old Name",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    update_payload = {
        "display_name": "Updated Display Name",
        "avatar_url": "https://example.com/avatar.png",
    }
    res = await client.patch(
        "/api/v1/auth/me",
        json=update_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["displayName"] == "Updated Display Name"
    assert data["avatar"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    """Test password change and logging in with new password."""
    client.cookies.clear()
    reg_payload = {
        "email": "pwd_user@example.com",
        "username": "pwd_user",
        "password": "OldPassword123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    # Wrong current password fails
    fail_res = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword!", "new_password": "NewPassword123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fail_res.status_code == 401

    # Correct current password succeeds
    success_res = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword123!", "new_password": "NewPassword123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert success_res.status_code == 200

    # Old password no longer works
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "pwd_user", "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # New password works
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "pwd_user", "password": "NewPassword123!"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_sessions_list_and_revocation(client: AsyncClient):
    """Test listing user sessions and revoking one."""
    client.cookies.clear()
    reg_payload = {
        "email": "session_user@example.com",
        "username": "session_user",
        "password": "Password123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    # List sessions
    list_res = await client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]
    assert sessions[0]["isActive"] is True

    # Revoke session
    revoke_res = await client.delete(
        f"/api/v1/auth/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    # Refresh with revoked session's refresh token should fail
    refresh_tok = reg_res.json()["refresh_token"]
    fail_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
    )
    assert fail_refresh.status_code == 401

