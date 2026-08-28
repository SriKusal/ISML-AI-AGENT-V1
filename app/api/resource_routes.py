from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import asyncio
import inspect
import time

from app.services.db_persistence import DatabasePersistenceService
from app.services.response_cache import get_cache, LRUResponseCache
from app.agents import (
    ResourceIntelligenceState,
    AgentPhase,
    create_resource_intelligence_graph,
)
from app.logging import get_logger

logger = get_logger("app.api.resource_routes")

router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


class ResourceIntelligenceRequest(BaseModel):
    domain: str
    course: str
    topic: str
    difficulty_level: str = "Beginner"
    provider: str = "gemini"
    model: str | None = None


def _get_db_session():
    """Lazy import so the app still starts even if DB is not configured."""
    from database.connection import get_db_session
    return get_db_session


async def execute_workflow(
    state: ResourceIntelligenceState, graph
) -> ResourceIntelligenceState:
    """Execute the LangGraph workflow to completion."""
    max_iterations = 50
    iteration = 0

    while state.phase != AgentPhase.COMPLETE and iteration < max_iterations:
        iteration += 1
        node_name = graph.get_next_node(state)
        node_func = graph.get_node_functions().get(node_name)

        if not node_func:
            state.add_error(f"Unknown node: {node_name}")
            state.phase = AgentPhase.COMPLETE
            break

        logger.debug("Executing node: %s (iteration %d)", node_name, iteration)

        if inspect.iscoroutinefunction(node_func):
            state = await node_func(state)
        else:
            state = node_func(state)

    if iteration >= max_iterations:
        state.add_error("Workflow exceeded maximum iterations")
        state.phase = AgentPhase.COMPLETE

    return state


@router.post("/intelligence")
async def generate_resource_intelligence(
    request: Request,
    body: ResourceIntelligenceRequest,
    db: AsyncSession = Depends(_get_db_session()),
) -> dict:
    """
    Execute complete resource intelligence workflow.

    Workflow phases:
    1. Initialize             - Validate inputs
    2. Topic Analysis         - Extract learning context
    3. Knowledge Retrieval    - Check DB for existing resources (ENH-006)
    4. Search Strategy        - Generate search queries
    5. Discover Resources     - Multi-source resource discovery
    6. Evaluate Resources     - Validate + normalize + score (BUG-005/006/007)
    7. Rank Resources         - Composite ranking + recommendations
    8. Build Prompt           - Construct LLM prompt
    9. Query Provider         - Call LLM (Gemini / DeepSeek)
    10. Parse Response        - Extract JSON from LLM response
    11. Validate Output       - Pydantic schema validation + repair-retry (BUG-014/016)
    12. Complete + Persist    - Save to DB, generate embeddings, return results
    """
    try:
        logger.info(
            "Starting resource intelligence workflow: domain=%s, course=%s, topic=%s",
            body.domain, body.course, body.topic,
        )

        # ENH-007: Check response cache before running the full pipeline
        cache: LRUResponseCache = get_cache()
        cache_key = cache.make_key(
            body.domain, body.course, body.topic,
            body.difficulty_level, body.provider,
        )
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("Returning cached response for key=%s", cache_key)
            cached["_cached"] = True
            return cached

        # Capture start time for ENH-002 duration tracking
        start_time = time.perf_counter()

        # Build initial state
        state = ResourceIntelligenceState(
            domain=body.domain,
            course=body.course,
            topic=body.topic,
            difficulty_level=body.difficulty_level,
            provider=body.provider,
            model=body.model,
        )

        # Run workflow
        graph = create_resource_intelligence_graph()
        state = await execute_workflow(state, graph)

        logger.info(
            "Workflow complete. Valid=%s, Errors=%d, Messages=%d",
            state.is_valid, len(state.validation_errors), len(state.messages),
        )

        # ------------------------------------------------------------------
        # Persist all results to the database
        # ------------------------------------------------------------------
        workflow_run_id = None
        try:
            persistence = DatabasePersistenceService(db)
            workflow_run_id = await persistence.persist(state, start_time=start_time)
            logger.info("Persisted workflow run: %s", workflow_run_id)
        except Exception as db_exc:
            # DB failure must never break the API response
            logger.error("DB persistence error (non-fatal): %s", db_exc)

        # ------------------------------------------------------------------
        # Build API response
        # ------------------------------------------------------------------
        response = {
            "success": not bool(state.validation_errors),
            "workflow_run_id": str(workflow_run_id) if workflow_run_id else None,
            "workflow": {
                "phase": state.phase.value,
                "messages": state.messages,
                "errors": state.validation_errors,
                "attempts": state.attempt_count,
                "knowledge_retrieved": state.knowledge_retrieved,
                "duration_ms": int((time.perf_counter() - start_time) * 1000),
            },
            "input": {
                "domain": state.domain,
                "course": state.course,
                "topic": state.topic,
                "difficulty_level": state.difficulty_level,
                "provider": state.provider,
                "model": state.model,
            },
            "analysis": {
                "topic_understanding": state.topic_understanding,
                "search_queries_generated": len(state.search_queries),
                "search_queries": state.search_queries[:10],
                "discovered_resources_count": sum(
                    len(r) for r in state.discovered_resources.values()
                ) if state.discovered_resources else 0,
                "discovered_resources_by_query": {
                    q: len(r)
                    for q, r in state.discovered_resources.items()
                } if state.discovered_resources else {},
                "validation": {
                    "validated": state.validated_count,
                    "rejected": state.rejected_count,
                } if state.validated_count or state.rejected_count else None,
            },
            "evaluation": {
                "evaluated_resources_count": len(state.evaluated_resources),
                "evaluation_dimensions": [
                    "relevance",
                    "educational_quality",
                    "credibility",
                    "learning_effectiveness",
                ],
            } if state.evaluated_resources else None,
            "ranking": {
                "ranked_resources_count": len(state.ranked_resources),
                "top_recommendations": state.ranked_resources[:10] if state.ranked_resources else [],
                "learning_sequence_length": len(state.learning_sequence),
                "learning_sequence": state.learning_sequence[:5] if state.learning_sequence else [],
            } if state.ranked_resources else None,
            "recommendations": state.recommendations if state.recommendations else None,
            "output": {
                "is_valid": state.is_valid,
                "parsed_output": state.parsed_output,
            } if state.parsed_output else None,
        }

        # Cache successful responses (ENH-007)
        if state.is_valid:
            cache.set(cache_key, response)

        return response

    except ValueError as exc:
        logger.error("Validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Workflow error: %s", exc)
        error_message = str(exc)
        if "429" in error_message or "Too Many Requests" in error_message:
            raise HTTPException(
                status_code=429,
                detail=f"Provider rate limit exceeded: {body.provider}",
            ) from exc
        if "503" in error_message or "Service Unavailable" in error_message:
            raise HTTPException(
                status_code=503,
                detail=f"Provider temporarily unavailable: {body.provider}",
            ) from exc
        raise HTTPException(
            status_code=502, detail=f"Workflow execution failed: {exc}"
        ) from exc


@router.get("/cache/stats")
def get_cache_stats() -> dict:
    """Return current response cache statistics (ENH-007)."""
    return {"cache": get_cache().stats}


@router.delete("/cache")
def clear_cache() -> dict:
    """Clear the response cache (useful after data updates)."""
    get_cache().clear()
    return {"success": True, "message": "Cache cleared"}
