import os
from typing import Any

import httpx

from app.logging import get_logger

logger = get_logger("app.services.deepseek")


class DeepSeekService:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    async def generate_text(self, prompt: str, model: str = "deepseek-chat") -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
