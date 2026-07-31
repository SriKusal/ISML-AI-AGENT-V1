from typing import Any

from app.services.base import BaseLLMProvider
from app.services.deepseek_service import DeepSeekService
from app.services.gemini_service import GeminiService


class LLMProviderFactory:
    @staticmethod
    def create(provider: str, **kwargs: Any) -> BaseLLMProvider:
        provider_name = (provider or "gemini").lower()
        if provider_name == "gemini":
            return GeminiService(**kwargs)
        if provider_name == "deepseek":
            return DeepSeekService(**kwargs)
        raise ValueError(f"Unsupported provider: {provider}")
