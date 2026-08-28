"""ISML AI AGENT — FastAPI application entry point.

Security controls applied here (ENH-009):
- API key authentication (disabled by default; enable via API_KEY_ENABLED=true)
- Rate limiting on LLM endpoints via slowapi
- Strict CORS origin configuration (set CORS_ORIGINS in .env for production)
- Request correlation ID logging
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import RequestLoggingMiddleware, api_router
from app.api.deepseek_routes import router as deepseek_router
from app.api.gemini_routes import router as gemini_router
from app.api.llm_routes import router as llm_router
from app.api.resource_routes import router as resource_router
from app.api.knowledge_routes import router as knowledge_router
from app.config import settings
from app.errors import http_exception_handler, validation_exception_handler, generic_exception_handler
from app.logging import get_logger
from app.security import limiter, rate_limit, verify_api_key

logger = get_logger("main")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Run startup and shutdown tasks."""
    try:
        from database.connection import init_db
        await init_db()
        logger.info("Database initialised successfully")
    except Exception as exc:  # pragma: no cover
        logger.warning("Database init failed (continuing without DB): %s", exc)
    yield


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Rate limiter state (ENH-009)
# ---------------------------------------------------------------------------
if limiter is not None:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS middleware (ENH-009)
# Defaults to "*" in development. Set CORS_ORIGINS=https://yourdomain.com in .env
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)
app.include_router(gemini_router)
app.include_router(deepseek_router)
app.include_router(llm_router)
app.include_router(resource_router)
app.include_router(knowledge_router)

# ---------------------------------------------------------------------------
# Standardized error handlers (ENH-015)
# ---------------------------------------------------------------------------
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "ISML AI AGENT is running"}
