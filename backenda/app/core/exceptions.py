"""
Application-wide exception hierarchy and FastAPI exception handlers.

All API errors are returned in a consistent JSON envelope:
{
    "error": {
        "code": "MACHINE_ROLE_CONFLICT",
        "message": "This machine already has the 'master' role.",
        "details": { ... }     // optional extra context
    }
}
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Base exception ───────────────────────────────────────────────────────────

class ADCError(Exception):
    """Base exception for all ADC business-logic errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


# ── Concrete exception types ────────────────────────────────────────────────

class NotFoundError(ADCError):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found.", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404, details=details)


class ConflictError(ADCError):
    """State conflict — duplicate registration, role conflict, etc."""

    def __init__(self, message: str = "Conflict.", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="CONFLICT", status_code=409, details=details)


class AuthenticationError(ADCError):
    """Invalid or missing credentials."""

    def __init__(self, message: str = "Authentication required.", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="AUTHENTICATION_REQUIRED", status_code=401, details=details)


class AuthorizationError(ADCError):
    """Insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions.", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="FORBIDDEN", status_code=403, details=details)


class ValidationError(ADCError):
    """Business-rule validation failure (not Pydantic schema errors)."""

    def __init__(self, message: str = "Validation error.", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422, details=details)


class RateLimitError(ADCError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded.", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="RATE_LIMITED", status_code=429, details=details)


class ServiceUnavailableError(ADCError):
    """Backend dependency unavailable (database, storage, etc.)."""

    def __init__(self, message: str = "Service temporarily unavailable.", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="SERVICE_UNAVAILABLE", status_code=503, details=details)


# ── Error response helpers ──────────────────────────────────────────────────

def _error_body(code: str, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build the standard error envelope."""
    body: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


# ── FastAPI exception handlers ──────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app instance."""

    @app.exception_handler(ADCError)
    async def adc_error_handler(_request: Request, exc: ADCError) -> JSONResponse:
        logger.warning(
            "adc_error",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Convert Pydantic errors into our standard envelope
        field_errors = []
        for err in exc.errors():
            loc = " → ".join(str(loc_part) for loc_part in err.get("loc", []))
            field_errors.append({"field": loc, "message": err.get("msg", "Invalid value")})

        logger.info("request_validation_error", errors=field_errors)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("VALIDATION_ERROR", "Request validation failed.", {"fields": field_errors}),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "An unexpected internal error occurred."),
        )
