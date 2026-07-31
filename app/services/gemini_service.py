import os
from typing import Any

import httpx

from app.logging import get_logger
from app.services.base import BaseLLMProvider

logger = get_logger("app.services.gemini")


class GeminiService(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url or os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")

    def _build_url(self, model: str) -> str:
        return f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

    async def generate_text(self, prompt: str, model: str = "gemini-2.0-flash") -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self._build_url(model), json=payload)
            response.raise_for_status()
            return response.json()
