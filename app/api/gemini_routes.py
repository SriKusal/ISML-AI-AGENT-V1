from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.gemini_service import GeminiService

router = APIRouter(prefix="/api/v1/gemini", tags=["gemini"])


class GeminiRequest(BaseModel):
    prompt: str
    model: str = "gemini-2.0-flash"


@router.post("/generate")
async def generate_gemini_text(request: GeminiRequest) -> dict:
    try:
        service = GeminiService()
        result = await service.generate_text(request.prompt, request.model)
        return {"success": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail=f"Gemini API request failed: {exc}") from exc
