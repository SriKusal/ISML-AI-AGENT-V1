"""Knowledge retrieval API — read from the database.

Endpoints
---------
POST /api/v1/knowledge/search          — Semantic similarity search
GET  /api/v1/knowledge/resources       — List resources for a topic
GET  /api/v1/knowledge/history         — Workflow run history
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.config import _load_env_file
_load_env_file()  # ensure GEMINI_API_KEY is in os.environ before EmbeddingService reads it
from database.connection import get_db_session
from database.models import Resource, Topic, Course, Domain, WorkflowRun
from database.repositories import (
    TopicRepository,
    ResourceRepository,
    EmbeddingRepository,
    WorkflowRunRepository,
)
from app.services.embedding_service import EmbeddingService
from app.logging import get_logger

logger = get_logger("app.api.knowledge_routes")

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10
    min_similarity: float = 0.5
    topic_id: Optional[str] = None


# ---------------------------------------------------------------------------
# 1. Semantic Similarity Search
# ---------------------------------------------------------------------------

@router.post("/search")
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Search for resources semantically similar to the query text.

    Generates an embedding for the query using Gemini text-embedding-004,
    then uses pgvector cosine distance to find the most similar resources
    stored in the database.

    Parameters
    ----------
    query          : Natural language search query
    limit          : Max number of results (default 10)
    min_similarity : Minimum cosine similarity threshold 0-1 (default 0.5)
    topic_id       : Optional UUID to restrict search to a specific topic
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    if not (0.0 <= request.min_similarity <= 1.0):
        raise HTTPException(
            status_code=400, detail="min_similarity must be between 0.0 and 1.0"
        )

    try:
        # Generate embedding for the search query
        embedding_service = EmbeddingService()
        query_vector = await embedding_service.embed_query(request.query)

        if not query_vector:
            raise HTTPException(
                status_code=503,
                detail="Embedding service unavailable — GEMINI_API_KEY may not be set",
            )

        # Search for similar resources using pgvector
        embedding_repo = EmbeddingRepository(db)
        results = await embedding_repo.find_similar(
            query_embedding=query_vector,
            limit=request.limit,
            min_similarity=request.min_similarity,
            topic_id=request.topic_id,
        )

        logger.info(
            "Semantic search for '%s' returned %d results",
            request.query, len(results),
        )

        return {
            "success": True,
            "query": request.query,
            "total_results": len(results),
            "min_similarity": request.min_similarity,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Semantic search failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Semantic search failed: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# 2. List Resources by Topic
# ---------------------------------------------------------------------------

@router.get("/resources")
async def get_resources(
    domain: str = Query(..., description="Domain name e.g. 'Language Learning'"),
    course: str = Query(..., description="Course name e.g. 'Japanese Language'"),
    topic: str = Query(..., description="Topic name e.g. 'Hiragana'"),
    difficulty_level: str = Query("Beginner", description="Difficulty level"),
    category: Optional[str] = Query(None, description="Filter by category: foundation, practice, advanced, supplementary, assessment"),
    limit: int = Query(20, ge=1, le=100, description="Max resources to return"),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Retrieve stored resources for a topic from the database.

    Looks up the domain → course → topic chain and returns all
    resources stored for that topic, optionally filtered by category.
    Results are ordered by rank and composite score.
    """
    try:
        # Resolve topic from domain/course/topic names
        result = await db.execute(
            select(Topic)
            .join(Course, Course.id == Topic.course_id)
            .join(Domain, Domain.id == Course.domain_id)
            .where(
                Domain.name == domain,
                Course.name == course,
                Topic.name == topic,
                Topic.difficulty_level == difficulty_level,
            )
        )
        db_topic = result.scalar_one_or_none()

        if not db_topic:
            return {
                "success": False,
                "message": f"No data found for {domain} > {course} > {topic} ({difficulty_level}). Run /intelligence first.",
                "resources": [],
                "total": 0,
            }

        # Fetch resources
        resource_repo = ResourceRepository(db)

        if category:
            resources = await resource_repo.get_by_category(db_topic.id, category)
        else:
            resources = await resource_repo.get_by_topic(
                db_topic.id, load_evaluation=True
            )

        # Apply limit
        resources = resources[:limit]

        resources_out = []
        for r in resources:
            resource_dict = {
                "id": str(r.id),
                "title": r.title,
                "url": r.url,
                "resource_type": r.resource_type,
                "source": r.source,
                "author": r.author,
                "language": r.language,
                "summary": r.summary,
                "keywords": r.keywords,
                "difficulty_level": r.difficulty_level,
                "category": r.category,
                "rank": r.rank,
                "composite_score": round(r.composite_score, 3),
                "credibility_score": round(r.credibility_score, 3),
                "estimated_study_time": r.estimated_study_time,
            }
            # Include evaluation scores if loaded
            if r.evaluation:
                resource_dict["evaluation"] = {
                    "relevance": round(r.evaluation.relevance_overall, 3),
                    "educational_quality": round(r.evaluation.quality_overall, 3),
                    "credibility": round(r.evaluation.credibility_overall, 3),
                    "learning_effectiveness": round(r.evaluation.effectiveness_overall, 3),
                    "composite": round(r.evaluation.composite_score, 3),
                }
            resources_out.append(resource_dict)

        logger.info(
            "Retrieved %d resources for topic '%s' (%s)",
            len(resources_out), topic, difficulty_level,
        )

        return {
            "success": True,
            "topic": {
                "id": str(db_topic.id),
                "domain": domain,
                "course": course,
                "topic": topic,
                "difficulty_level": difficulty_level,
            },
            "total": len(resources_out),
            "category_filter": category,
            "resources": resources_out,
        }

    except Exception as exc:
        logger.error("Resource retrieval failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Resource retrieval failed: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# 3. Workflow Run History
# ---------------------------------------------------------------------------

@router.get("/history")
async def get_workflow_history(
    limit: int = Query(20, ge=1, le=100, description="Max runs to return"),
    topic: Optional[str] = Query(None, description="Filter by topic name"),
    success_only: bool = Query(False, description="Return only successful runs"),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Retrieve workflow run history from the database.

    Returns a list of recent workflow runs with input parameters,
    outcome, resource counts, and any errors encountered.
    Optionally filtered by topic name or success status.
    """
    try:
        run_repo = WorkflowRunRepository(db)

        if success_only:
            stmt = (
                select(WorkflowRun)
                .where(WorkflowRun.success.is_(True))
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )
        else:
            stmt = (
                select(WorkflowRun)
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )

        if topic:
            stmt = stmt.where(WorkflowRun.topic_name.ilike(f"%{topic}%"))

        result = await db.execute(stmt)
        runs = list(result.scalars().all())

        runs_out = [
            {
                "id": str(r.id),
                "domain": r.domain,
                "course": r.course,
                "topic": r.topic_name,
                "difficulty_level": r.difficulty_level,
                "provider": r.provider,
                "model": r.model,
                "success": r.success,
                "final_phase": r.final_phase,
                "attempt_count": r.attempt_count,
                "resources_discovered": r.resources_discovered,
                "resources_evaluated": r.resources_evaluated,
                "resources_ranked": r.resources_ranked,
                "errors": r.errors or [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]

        logger.info("Retrieved %d workflow runs from history", len(runs_out))

        return {
            "success": True,
            "total": len(runs_out),
            "filters": {
                "topic": topic,
                "success_only": success_only,
            },
            "runs": runs_out,
        }

    except Exception as exc:
        logger.error("History retrieval failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"History retrieval failed: {exc}"
        ) from exc
