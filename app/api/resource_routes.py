from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from prompts import SYSTEM_PROMPT_TEMPLATE, TASK_PROMPT_TEMPLATE
from app.services.provider_factory import LLMProviderFactory

router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


class ResourceIntelligenceRequest(BaseModel):
    domain: str
    course: str
    topic: str
    difficulty_level: str = "Beginner"
    provider: str = "gemini"
    model: str | None = None


@router.post("/intelligence")
async def generate_resource_intelligence(request: ResourceIntelligenceRequest) -> dict:
    try:
        task_prompt = TASK_PROMPT_TEMPLATE.format(
            domain=request.domain,
            course=request.course,
            topic=request.topic,
            difficulty_level=request.difficulty_level,
        )

        full_prompt = (
            f"{SYSTEM_PROMPT_TEMPLATE}\n\n"
            f"{task_prompt}"
        )

        provider = LLMProviderFactory.create(request.provider)
        model = request.model or ""
        result = await provider.generate_text(full_prompt, model)

        return {
            "success": True,
            "provider": request.provider,
            "domain": request.domain,
            "course": request.course,
            "topic": request.topic,
            "difficulty_level": request.difficulty_level,
            "data": result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
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
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc
