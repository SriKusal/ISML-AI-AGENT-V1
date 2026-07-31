from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, model: str = "") -> dict[str, Any]:
        raise NotImplementedError
