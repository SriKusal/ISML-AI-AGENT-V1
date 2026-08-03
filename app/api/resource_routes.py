from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio

from prompts import SYSTEM_PROMPT_TEMPLATE, TASK_PROMPT_TEMPLATE
from app.services.provider_factory import LLMProviderFactory
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


async def execute_workflow(state: ResourceIntelligenceState, graph) -> ResourceIntelligenceState:
    """Execute the LangGraph workflow to completion."""
    max_iterations = 50  # Safety limit to prevent infinite loops
    iteration = 0
    
    while state.phase != AgentPhase.COMPLETE and iteration < max_iterations:
        iteration += 1
        node_name = graph.get_next_node(state)
        node_func = graph.get_node_functions().get(node_name)
        
        if not node_func:
            state.add_error(f"Unknown node: {node_name}")
            state.phase = AgentPhase.COMPLETE
            break
        
        logger.debug(f"Executing node: {node_name} (iteration {iteration})")
        
        # Check if node is async
        if asyncio.iscoroutinefunction(node_func):
            state = await node_func(state)
        else:
            state = node_func(state)
    
    if iteration >= max_iterations:
        state.add_error("Workflow exceeded maximum iterations")
        state.phase = AgentPhase.COMPLETE
    
    return state


@router.post("/intelligence")
async def generate_resource_intelligence(request: ResourceIntelligenceRequest) -> dict:
    """
    Execute complete resource intelligence workflow.
    
    Workflow phases:
    1. Initialize - Validate inputs
    2. Topic Analysis - Extract learning context
    3. Search Strategy - Generate search queries
    4. Build Prompt - Construct LLM prompt
    5. Query Provider - Call LLM
    6. Parse Response - Extract JSON
    7. Validate Output - Check schema
    8. Complete - Return results
    """
    try:
        logger.info(
            "Starting resource intelligence workflow: domain=%s, course=%s, topic=%s",
            request.domain, request.course, request.topic
        )
        
        # Create initial state
        state = ResourceIntelligenceState(
            domain=request.domain,
            course=request.course,
            topic=request.topic,
            difficulty_level=request.difficulty_level,
            provider=request.provider,
            model=request.model,
        )
        
        # Create and execute graph
        graph = create_resource_intelligence_graph()
        state = await execute_workflow(state, graph)
        
        # Log workflow completion
        logger.info(
            "Workflow complete. Valid=%s, Errors=%d, Messages=%d",
            state.is_valid, len(state.validation_errors), len(state.messages)
        )
        
        # Prepare response
        response = {
            "success": not bool(state.validation_errors),
            "workflow": {
                "phase": state.phase.value,
                "messages": state.messages,
                "errors": state.validation_errors,
                "attempts": state.attempt_count,
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
                "search_queries": state.search_queries[:10],  # Return first 10 queries
                "discovered_resources_count": sum(
                    len(resources) for resources in state.discovered_resources.values()
                ) if state.discovered_resources else 0,
                "discovered_resources_by_query": {
                    query: len(resources)
                    for query, resources in state.discovered_resources.items()
                } if state.discovered_resources else {},
            },
            "evaluation": {
                "evaluated_resources_count": len(state.evaluated_resources),
                "evaluation_dimensions": ["relevance", "educational_quality", "credibility", "learning_effectiveness"],
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
        
        return response
        
    except ValueError as exc:
        logger.error(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(f"Workflow error: {exc}")
        error_message = str(exc)
        if "429" in error_message or "Too Many Requests" in error_message:
            raise HTTPException(
                status_code=429,
                detail=f"Provider rate limit exceeded: {request.provider}",
            ) from exc
        if "503" in error_message or "Service Unavailable" in error_message:
            raise HTTPException(
                status_code=503,
                detail=f"Provider temporarily unavailable: {request.provider}",
            ) from exc
        raise HTTPException(status_code=502, detail=f"Workflow execution failed: {exc}") from exc
