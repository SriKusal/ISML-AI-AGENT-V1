"""Embedding generation service for educational resources.

Uses the Gemini text-embedding-004 model (768-dim, free tier available).
Generates a single dense vector per resource from its title + summary + keywords.

The vector is stored in the resource_embeddings table via EmbeddingRepository
and enables semantic similarity search via pgvector cosine distance.
"""

import os
from typing import Optional

import httpx

from app.logging import get_logger
from app.utils.retry import async_retry, EMBEDDING_RETRY_CONFIG

logger = get_logger("app.services.embedding")

# Gemini embedding model — 768 dimensions, free with API key
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")
EMBEDDING_DIM = 3072  # gemini-embedding-001 output dimension


class EmbeddingService:
    """Generates text embeddings using the Gemini Embeddings API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url or os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        )
        self.model = EMBEDDING_MODEL

    def _build_text(self, resource: dict) -> str:
        """Build a single text string from resource fields for embedding.

        Combines title, summary, and keywords so the vector captures
        the full semantic meaning of the resource.
        """
        parts = []

        title = resource.get("title", "").strip()
        if title:
            parts.append(title)

        summary = resource.get("summary", "").strip()
        if summary:
            parts.append(summary)

        keywords = resource.get("keywords", [])
        if keywords and isinstance(keywords, list):
            parts.append(" ".join(str(k) for k in keywords))

        resource_type = resource.get("resource_type", "")
        if resource_type:
            parts.append(resource_type)

        return " | ".join(parts)

    @async_retry(EMBEDDING_RETRY_CONFIG)
    async def embed_text(self, text: str) -> Optional[list[float]]:
        """Generate an embedding vector for a single text string.

        Returns None if the API call fails — callers should handle gracefully.
        """
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set — skipping embedding generation")
            return None

        if not text.strip():
            logger.warning("Empty text passed to embed_text — skipping")
            return None

        url = f"{self.base_url}/{self.model}:embedContent?key={self.api_key}"
        payload = {
            "model": self.model,
            "content": {
                "parts": [{"text": text}]
            },
            "taskType": "RETRIEVAL_DOCUMENT",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                vector = data.get("embedding", {}).get("values", [])
                if not vector:
                    logger.warning("Gemini returned empty embedding vector")
                    return None
                return vector
        except Exception as exc:
            logger.error("Embedding API call failed: %s", exc)
            return None

    async def embed_resource(self, resource: dict) -> Optional[list[float]]:
        """Generate an embedding for a resource dict.

        Builds the text from title + summary + keywords then calls embed_text.
        """
        text = self._build_text(resource)
        if not text:
            return None
        return await self.embed_text(text)

    @async_retry(EMBEDDING_RETRY_CONFIG)
    async def embed_query(self, query: str) -> Optional[list[float]]:
        """Generate an embedding for a search query string.

        Uses RETRIEVAL_QUERY task type for better semantic search accuracy.
        """
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set — skipping query embedding")
            return None

        url = f"{self.base_url}/{self.model}:embedContent?key={self.api_key}"
        payload = {
            "model": self.model,
            "content": {
                "parts": [{"text": query}]
            },
            "taskType": "RETRIEVAL_QUERY",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                vector = data.get("embedding", {}).get("values", [])
                if not vector:
                    return None
                return vector
        except Exception as exc:
            logger.error("Query embedding failed: %s", exc)
            return None
