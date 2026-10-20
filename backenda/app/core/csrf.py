"""
CSRF Protection using Double-Submit Cookie pattern.

Safe methods (GET, HEAD, OPTIONS) set or refresh a CSRF token.
Mutating methods (POST, PUT, PATCH, DELETE) that authenticate via cookies
must present matching 'X-CSRF-Token' header. Bearer-token requests are exempt.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings
from app.core.exceptions import ADCError

settings = get_settings()

CSRF_COOKIE_NAME = "csrftoken"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS: Set[str] = {"GET", "HEAD", "OPTIONS"}

# Endpoints exempt from CSRF (initial auth, health checks, machine agent endpoints)
EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/machines/register",
    "/api/v1/machines/pairing/challenge",
    "/api/v1/machines/heartbeat",
    "/api/v1/agent/",
)


def generate_csrf_token() -> str:
    """Generate a secure cryptographically random CSRF token."""
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces Double-Submit Cookie CSRF protection.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check if the path is exempt
        path = request.url.path
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            response = await call_next(request)
            return self._ensure_csrf_cookie(request, response)

        # For state-modifying requests, verify CSRF if cookie-based authentication is used
        if request.method not in SAFE_METHODS:
            auth_header = request.headers.get("Authorization")
            has_bearer = auth_header and auth_header.startswith("Bearer ")

            # If authenticated via access_token cookie without Bearer header, require CSRF
            cookie_auth = request.cookies.get("access_token")
            if cookie_auth and not has_bearer:
                cookie_csrf = request.cookies.get(CSRF_COOKIE_NAME)
                header_csrf = request.headers.get(CSRF_HEADER_NAME)

                if not cookie_csrf or not header_csrf:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "CSRF_TOKEN_MISSING",
                                "message": f"CSRF token missing. Include '{CSRF_HEADER_NAME}' header matching cookie.",
                                "details": {},
                            }
                        },
                    )

                if not hmac.compare_digest(cookie_csrf, header_csrf):
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "CSRF_TOKEN_INVALID",
                                "message": "CSRF token mismatch.",
                                "details": {},
                            }
                        },
                    )

        response = await call_next(request)
        return self._ensure_csrf_cookie(request, response)

    def _ensure_csrf_cookie(self, request: Request, response: Response) -> Response:
        """Ensure the csrftoken cookie is set so clients can read it."""
        existing = request.cookies.get(CSRF_COOKIE_NAME)
        if not existing:
            token = generate_csrf_token()
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=token,
                httponly=False,  # Client JS needs to read this cookie to send in header
                samesite="lax",
                secure=settings.is_production,
            )
            response.headers[CSRF_HEADER_NAME] = token
        return response
