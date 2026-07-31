from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.deepseek_service import DeepSeekService

router = APIRouter(prefix="/api/v1/deepseek", tags=["deepseek"])


class DeepSeekRequest(BaseModel):
    prompt: str
    model: str = "deepseek-chat"


@router.post("/generate")
async def generate_deepseek_text(request: DeepSeekRequest) -> dict:
    try:
        service = DeepSeekService()
        result = await service.generate_text(request.prompt, request.model)
        return {"success": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail=f"DeepSeek API request failed: {exc}") from exc
