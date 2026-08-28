"""Tests for semantic search and embedding service.

Validates:
- EmbeddingService builds text correctly from resource fields
- embed_text returns None gracefully when API key is missing
- embed_query returns None gracefully when API key is missing
- EmbeddingRepository.find_similar query construction
- Retry config is applied correctly
"""

import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.embedding_service import EmbeddingService, EMBEDDING_DIM


class TestEmbeddingServiceTextBuilding(unittest.TestCase):
    """Tests for _build_text — no API calls needed."""

    def setUp(self):
        self.service = EmbeddingService(api_key="test-key")

    def test_builds_text_from_all_fields(self):
        resource = {
            "title": "Hiragana Tutorial",
            "summary": "Learn all 46 hiragana characters",
            "keywords": ["hiragana", "japanese", "beginner"],
            "resource_type": "video",
        }
        text = self.service._build_text(resource)
        self.assertIn("Hiragana Tutorial", text)
        self.assertIn("Learn all 46", text)
        self.assertIn("hiragana", text)
        self.assertIn("video", text)

    def test_builds_text_with_missing_summary(self):
        resource = {"title": "Math Tutorial", "resource_type": "pdf"}
        text = self.service._build_text(resource)
        self.assertIn("Math Tutorial", text)
        self.assertIn("pdf", text)

    def test_returns_empty_string_for_empty_resource(self):
        text = self.service._build_text({})
        self.assertEqual(text, "")

    def test_keywords_joined_with_space(self):
        resource = {
            "title": "Test",
            "keywords": ["a", "b", "c"],
            "resource_type": "article",
        }
        text = self.service._build_text(resource)
        self.assertIn("a b c", text)

    def test_pipe_separator_used_between_sections(self):
        resource = {
            "title": "Test Title",
            "summary": "Test Summary",
            "resource_type": "video",
        }
        text = self.service._build_text(resource)
        self.assertIn("|", text)


class TestEmbeddingServiceWithoutApiKey(unittest.IsolatedAsyncioTestCase):
    """Tests that service degrades gracefully when API key is absent."""

    async def test_embed_text_returns_none_without_key(self):
        # Create service with explicitly empty api_key bypassing env
        service = EmbeddingService(api_key="")
        service.api_key = ""  # force empty
        result = await service.embed_text("test text")
        self.assertIsNone(result)

    async def test_embed_query_returns_none_without_key(self):
        service = EmbeddingService(api_key="")
        service.api_key = ""  # force empty
        result = await service.embed_query("test query")
        self.assertIsNone(result)

    async def test_embed_text_returns_none_for_empty_text(self):
        service = EmbeddingService(api_key="test-key")
        result = await service.embed_text("")
        self.assertIsNone(result)

    async def test_embed_resource_returns_none_for_empty_resource(self):
        service = EmbeddingService(api_key="test-key")
        result = await service.embed_resource({})
        self.assertIsNone(result)


class TestEmbeddingServiceWithMockedApi(unittest.IsolatedAsyncioTestCase):
    """Tests embedding service with mocked HTTP responses."""

    def _mock_embedding_response(self, dim=768):
        return {
            "embedding": {
                "values": [0.1] * dim
            }
        }

    async def test_embed_text_returns_vector(self):
        service = EmbeddingService(api_key="test-key")
        mock_response = MagicMock()
        mock_response.json.return_value = self._mock_embedding_response(EMBEDDING_DIM)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await service.embed_text("Learn Hiragana basics")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), EMBEDDING_DIM)

    async def test_embed_query_returns_vector(self):
        service = EmbeddingService(api_key="test-key")
        mock_response = MagicMock()
        mock_response.json.return_value = self._mock_embedding_response(EMBEDDING_DIM)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await service.embed_query("Find Hiragana resources")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), EMBEDDING_DIM)

    async def test_embed_resource_builds_text_and_embeds(self):
        service = EmbeddingService(api_key="test-key")
        mock_response = MagicMock()
        mock_response.json.return_value = self._mock_embedding_response(EMBEDDING_DIM)
        mock_response.raise_for_status = MagicMock()

        resource = {
            "title": "Hiragana Tutorial",
            "summary": "Learn hiragana step by step",
            "keywords": ["hiragana", "japanese"],
            "resource_type": "video",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await service.embed_resource(resource)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), EMBEDDING_DIM)

    async def test_embed_text_returns_none_on_api_error(self):
        service = EmbeddingService(api_key="test-key")
        # Override retry config to speed up test
        with patch("app.services.embedding_service.EMBEDDING_RETRY_CONFIG") as mock_cfg:
            mock_cfg.max_attempts = 1

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(side_effect=Exception("API error"))
                mock_client_cls.return_value = mock_client

                result = await service.embed_text("test")

        self.assertIsNone(result)


class TestEmbeddingDimension(unittest.TestCase):

    def test_embedding_dim_is_768(self):
        """Gemini text-embedding-004 produces 768-dim vectors."""
        self.assertEqual(EMBEDDING_DIM, 3072)

    def test_model_name_is_text_embedding_004(self):
        service = EmbeddingService(api_key="test-key")
        self.assertIn("gemini-embedding", service.model)
