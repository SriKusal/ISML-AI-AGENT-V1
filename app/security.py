"""Security middleware and dependencies for ISML AI AGENT (ENH-009).

Provides:
1. API key authentication — configurable via API_KEY_ENABLED + API_KEY env vars.
   Disabled by default so local development works without any configuration.
2. Rate limiting — uses slowapi (Limits library) to cap requests on expensive
   LLM endpoints. Configurable via RATE_LIMIT_PER_MINUTE env var.
3. CORS hardening — strict origins configurable via CORS_ORIGINS env var.
   Defaults to "*" (open) for development; set to specific origins in production.
4. SSRF protection for external URL fetching — reuses the normalize_url validator
   which already blocks private/loopback/link-local addresses.

Notes
-----
- API keys are NEVER logged. Only the first 4 characters are shown in debug logs.
- Rate limiting is applied per-client IP. Behind a reverse proxy, ensure
  FORWARDED_ALLOW_IPS is set correctly in your deployment.
- SSRF protection is inherently handled by normalize_url (resource_validator.py).
  This module documents the integration point and provides a helper.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.config import settings
from app.logging import get_logger

logger = get_logger("app.security")


# ---------------------------------------------------------------------------
# API Key authentication dependency (ENH-009)
# ---------------------------------------------------------------------------

async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency that enforces API key authentication.

    Usage (on a route or router):
        @router.post("/endpoint", dependencies=[Depends(verify_api_key)])

    Authentication is disabled unless API_KEY_ENABLED=true AND API_KEY=<secret>
    are both set in the environment. This keeps local development frictionless.

    Security
    --------
    - Uses constant-time comparison to prevent timing attacks.
    - Never logs the actual key value.
    - Returns 401 with a generic message to avoid leaking information.
    """
    if not settings.API_KEY_ENABLED:
        return  # Auth disabled — allow all requests (development mode)

    if not settings.API_KEY:
        logger.warning(
            "API_KEY_ENABLED=true but API_KEY is not set — "
            "all requests will be rejected"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication is enabled but no key is configured",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    import hmac
    provided = x_api_key.encode() if x_api_key else b""
    expected = settings.API_KEY.encode()

    if not hmac.compare_digest(provided, expected):
        # Log a warning without the key value
        prefix = x_api_key[:4] if x_api_key else "<empty>"
        logger.warning("Invalid API key attempt (prefix=%s...)", prefix)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# ---------------------------------------------------------------------------
# Rate limiter setup (ENH-009)
# ---------------------------------------------------------------------------

def create_limiter():
    """Create and return a slowapi Limiter instance.

    The limiter is configured to use client IP as the key function.
    Import and attach to the FastAPI app in main.py.
    """
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        limiter = Limiter(key_func=get_remote_address)
        return limiter
    except ImportError:
        logger.warning("slowapi not installed — rate limiting disabled")
        return None


# The module-level limiter instance — imported by main.py and route handlers
limiter = create_limiter()


def rate_limit(requests_per_minute: int | None = None) -> str:
    """Return the rate limit string for use with @limiter.limit().

    Defaults to RATE_LIMIT_PER_MINUTE from settings if not specified.
    """
    rpm = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
    return f"{rpm}/minute"


# ---------------------------------------------------------------------------
# SSRF protection helper (delegates to resource_validator)
# ---------------------------------------------------------------------------

def validate_external_url(url: str) -> str:
    """Validate and normalize an external URL, raising HTTPException on failure.

    This is the integration point for SSRF protection when the application
    fetches external URLs (e.g. metadata extraction, link verification).

    Currently the discovery layer uses simulated data, so this is a clean
    extension point for when real URL fetching is added.
    """
    from app.services.resource_validator import normalize_url
    normalized = normalize_url(url)
    if normalized is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL rejected: '{url}' is invalid, unsafe, or points to a private network",
        )
    return normalized
