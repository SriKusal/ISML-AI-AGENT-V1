"""PostgreSQL async connection with pgvector extension setup.

Configures SQLAlchemy async engine, session factory, and
provides the FastAPI dependency for injecting DB sessions.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

# Load .env BEFORE reading any env vars so DATABASE_URL is always populated
# regardless of whether the shell environment already has it set.
from app.config import _load_env_file
_load_env_file()

from app.logging import get_logger

logger = get_logger("database.connection")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/isml_agent",
)

# asyncpg does not accept pgbouncer=true as a query parameter — strip it
if "pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")

_pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
_echo = os.getenv("DB_ECHO", "false").lower() in {"1", "true", "yes"}

engine = create_async_engine(
    DATABASE_URL,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    echo=_echo,
    pool_pre_ping=True,
    # PgBouncer transaction-mode (Supabase port 6543) does not support
    # prepared statements — disable asyncpg's statement cache entirely.
    connect_args={"statement_cache_size": 0},
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for use as a FastAPI dependency.

    Usage::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create all tables and enable the pgvector extension.

    Uses the session-mode pooler (DATABASE_SYNC_URL / port 5432) for DDL
    because the transaction-mode pooler (port 6543 / pgbouncer=true) does
    not support multi-statement transactions like CREATE EXTENSION or
    CREATE TABLE.

    Called once at application startup from main.py.
    In production prefer Alembic migrations over this.
    """
    from database.base import Base  # local import to avoid circular deps
    import database.models  # noqa: F401 — ensure all models are registered

    # Prefer the session-mode URL for DDL; fall back to the main URL
    ddl_url = os.getenv("DATABASE_SYNC_URL") or DATABASE_URL

    # Replace psycopg2 driver with asyncpg for async DDL execution
    if "+psycopg2" in ddl_url:
        ddl_url = ddl_url.replace("+psycopg2", "+asyncpg")

    # Strip pgbouncer=true query param — not valid for asyncpg
    if "pgbouncer=true" in ddl_url:
        ddl_url = ddl_url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")

    ddl_engine = create_async_engine(ddl_url, pool_pre_ping=True)

    try:
        async with ddl_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension enabled")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created / verified")
            # HNSW index for fast cosine similarity search
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_resource_embeddings_hnsw "
                "ON resource_embeddings USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            ))
            logger.info("pgvector HNSW index created / verified")
    finally:
        await ddl_engine.dispose()
