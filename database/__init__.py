"""Database package for ISML AI AGENT.

Provides PostgreSQL connection with pgvector extension,
SQLAlchemy async engine, session factory, base model,
all ORM models, repositories, and CRUD operations.
"""

from database.connection import (
    engine,
    async_session_factory,
    get_db_session,
    init_db,
)
from database.base import Base
from database.models import (
    Domain,
    Course,
    Topic,
    Resource,
    ResourceEvaluation,
    ResourceEmbedding,
    SearchQuery,
    WorkflowRun,
)

__all__ = [
    # Connection
    "engine",
    "async_session_factory",
    "get_db_session",
    "init_db",
    # Base
    "Base",
    # Models
    "Domain",
    "Course",
    "Topic",
    "Resource",
    "ResourceEvaluation",
    "ResourceEmbedding",
    "SearchQuery",
    "WorkflowRun",
]
