"""HTTP middleware for ISML AI AGENT.

RequestLoggingMiddleware
- Injects a unique correlation_id into every request context
- Logs method, path, status code, and response latency
- Attaches correlation_id as X-Correlation-ID response header
  so clients can trace requests in logs
"""

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.logging import get_logger, correlation_id_var

logger = get_logger("app.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate or propagate correlation ID
        correlation_id = (
            request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:8]
        )
        token = correlation_id_var.set(correlation_id)

        start = time.perf_counter()

        logger.info(
            "→ %s %s",
            request.method,
            request.url.path,
            extra={"correlation_id": correlation_id},
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "✗ %s %s unhandled error after %.0fms: %s",
                request.method, request.url.path, duration_ms, exc,
                extra={"duration_ms": duration_ms},
            )
            raise
        finally:
            correlation_id_var.reset(token)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "← %s %s %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"duration_ms": duration_ms},
        )

        # Attach correlation ID to response so client can reference it
        response.headers["X-Correlation-ID"] = correlation_id
        return response
