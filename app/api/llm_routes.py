from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.provider_factory import LLMProviderFactory

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


class LLMRequest(BaseModel):
    provider: str = "gemini"
    prompt: str
    model: str | None = None


@router.post("/generate")
async def generate_with_provider(request: LLMRequest) -> dict:
    try:
        provider = LLMProviderFactory.create(request.provider)
        model = request.model or ""
        result = await provider.generate_text(request.prompt, model)
        return {"success": True, "provider": request.provider, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        error_message = str(exc)
        if "429" in error_message or "Too Many Requests" in error_message:
            raise HTTPException(
                status_code=429,
                detail=f"Provider rate limit exceeded: {request.provider}",
            ) from exc
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc
