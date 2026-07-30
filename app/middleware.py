from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging import get_logger

logger = get_logger("app.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info("Request received: %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("Response sent: %s %s -> %s", request.method, request.url.path, response.status_code)
        return response
