"""Standardized API error responses for ISML AI AGENT (ENH-015).

All API errors are returned in a consistent envelope:
{
    "error": {
        "code": "MACHINE_READABLE_CODE",
        "message": "Human-readable description",
        "details": {}   # optional extra context
    }
}

Internal stack traces are NEVER exposed in API responses.
Full details are logged server-side for debugging.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def error_response(
    code: str,
    message: str,
    status_code: int = 500,
    details: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    """Build a standardized error response.

    Parameters
    ----------
    code        : Machine-readable error code from ErrorCode constants.
    message     : Human-readable description (safe for end-users).
    status_code : HTTP status code.
    details     : Optional extra context (never include secrets or stack traces).

    Returns
    -------
    JSONResponse with the standard error envelope.
    """
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------

async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """Convert FastAPI HTTPException to the standard error envelope."""
    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        # Map common HTTP status codes to error codes
        _code_map = {
            400: ErrorCode.BAD_REQUEST,
            401: ErrorCode.AUTHENTICATION_REQUIRED,
            403: ErrorCode.AUTHENTICATION_REQUIRED,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            422: ErrorCode.VALIDATION_ERROR,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.INTERNAL_ERROR,
            502: ErrorCode.PROVIDER_ERROR,
            503: ErrorCode.PROVIDER_UNAVAILABLE,
        }
        code = _code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return error_response(code, str(exc.detail), exc.status_code)
    return error_response(ErrorCode.INTERNAL_ERROR, "An unexpected error occurred", 500)


async def validation_exception_handler(request: Request, exc) -> JSONResponse:
    """Convert Pydantic RequestValidationError to the standard error envelope."""
    try:
        field_errors = [
            {"field": " → ".join(str(loc) for loc in e["loc"]), "msg": e["msg"]}
            for e in exc.errors()
        ]
    except Exception:
        field_errors = []
    return error_response(
        ErrorCode.VALIDATION_ERROR,
        "Request validation failed",
        status_code=422,
        details={"field_errors": field_errors},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler that returns a safe error message without stack traces."""
    from app.logging import get_logger
    logger = get_logger("app.errors")
    logger.error("Unhandled exception on %s %s: %s",
                 request.method, request.url.path, exc, exc_info=True)
    return error_response(
        ErrorCode.INTERNAL_ERROR,
        "An internal server error occurred. Please try again later.",
        status_code=500,
    )
