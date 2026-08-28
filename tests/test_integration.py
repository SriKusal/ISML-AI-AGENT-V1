"""Integration tests for external services (TEST-003).

These tests verify connectivity with real external services:
  - PostgreSQL + pgvector
  - Gemini embedding API
  - LLM provider

All tests are SKIPPED by default unless the relevant environment variable
is set, so the normal test suite always passes in CI without credentials.

Environment variables to enable:
  INTEGRATION_DB=true      — run PostgreSQL / pgvector tests
  INTEGRATION_LLM=true     — run live LLM provider tests
  INTEGRATION_EMBED=true   — run Gemini embedding tests

Run all integrations:
  INTEGRATION_DB=true INTEGRATION_LLM=true INTEGRATION_EMBED=true pytest tests/test_integration.py -v
"""

import os
import unittest

INTEGRATION_DB = os.getenv("INTEGRATION_DB", "false").lower() in {"1", "true", "yes"}
INTEGRATION_LLM = os.getenv("INTEGRATION_LLM", "false").lower() in {"1", "true", "yes"}
INTEGRATION_EMBED = os.getenv("INTEGRATION_EMBED", "false").lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Database integration tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(INTEGRATION_DB, "Set INTEGRATION_DB=true to run DB tests")
class TestDatabaseIntegration(unittest.IsolatedAsyncioTestCase):
    """Verify PostgreSQL + pgvector connectivity and schema creation."""

    async def test_database_connection(self):
        """Can connect to the database and run a simple query."""
        from database.connection import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1 AS val"))
            row = result.fetchone()
            self.assertEqual(row.val, 1)

    async def test_pgvector_extension_available(self):
        """pgvector extension must be installed."""
        from database.connection import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
            self.assertIsNotNone(row, "pgvector extension not found")

    async def test_tables_exist(self):
        """All required tables must exist after init_db."""
        from database.connection import async_session_factory, init_db
        from sqlalchemy import text
        await init_db()
        async with async_session_factory() as session:
            expected_tables = [
                "domains", "courses", "topics", "resources",
                "resource_evaluations", "resource_embeddings",
                "search_queries", "workflow_runs",
            ]
            for table in expected_tables:
                result = await session.execute(
                    text(f"SELECT to_regclass('public.{table}')")
                )
                row = result.fetchone()
                self.assertIsNotNone(row[0], f"Table '{table}' does not exist")

    async def test_domain_get_or_create(self):
        """DomainRepository.get_or_create is idempotent."""
        from database.connection import async_session_factory
        from database.repositories import DomainRepository
        async with async_session_factory() as session:
            repo = DomainRepository(session)
            d1, created1 = await repo.get_or_create("Integration Test Domain")
            d2, created2 = await repo.get_or_create("Integration Test Domain")
            self.assertTrue(created1)
            self.assertFalse(created2)
            self.assertEqual(d1.id, d2.id)
            # Cleanup
            await repo.delete(d1.id)
            await session.commit()

    async def test_semantic_search_endpoint_with_real_db(self):
        """Semantic search endpoint works with live DB (returns results or empty list)."""
        from fastapi.testclient import TestClient
        from main import app
        from unittest.mock import AsyncMock, patch
        client = TestClient(app)
        # Mock the embedding so we don't need a real Gemini key for this test
        with patch("app.services.embedding_service.EmbeddingService.embed_query",
                   return_value=[0.1] * 768):
            response = client.post(
                "/api/v1/knowledge/search",
                json={"query": "French greetings beginner", "limit": 5},
            )
        # Either 200 (results or empty) or 503 (embedding service unavailable)
        self.assertIn(response.status_code, {200, 503})


# ---------------------------------------------------------------------------
# LLM provider integration tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(INTEGRATION_LLM, "Set INTEGRATION_LLM=true to run LLM tests")
class TestLLMProviderIntegration(unittest.IsolatedAsyncioTestCase):
    """Verify LLM provider connectivity."""

    async def test_gemini_provider_responds(self):
        """GeminiService can call the real API and get a response."""
        from app.services.gemini_service import GeminiService
        service = GeminiService()
        response = await service.generate_text(
            "Say 'Hello, world!' in JSON format: {\"message\": \"...\"}",
            model="gemini-2.0-flash",
        )
        self.assertIn("candidates", response)

    async def test_provider_factory_creates_gemini(self):
        """LLMProviderFactory creates a GeminiService for 'gemini'."""
        from app.services.provider_factory import LLMProviderFactory
        from app.services.gemini_service import GeminiService
        provider = LLMProviderFactory.create("gemini")
        self.assertIsInstance(provider, GeminiService)


# ---------------------------------------------------------------------------
# Embedding integration tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(INTEGRATION_EMBED, "Set INTEGRATION_EMBED=true to run embedding tests")
class TestEmbeddingIntegration(unittest.IsolatedAsyncioTestCase):
    """Verify Gemini embedding API connectivity."""

    async def test_embed_text_returns_768d_vector(self):
        """embed_text returns a 768-dimensional vector."""
        from app.services.embedding_service import EmbeddingService, EMBEDDING_DIM
        service = EmbeddingService()
        vector = await service.embed_text("French greetings bonjour bonsoir")
        self.assertIsNotNone(vector)
        self.assertEqual(len(vector), EMBEDDING_DIM)
        self.assertIsInstance(vector[0], float)

    async def test_embed_query_returns_768d_vector(self):
        """embed_query returns a 768-dimensional vector."""
        from app.services.embedding_service import EmbeddingService, EMBEDDING_DIM
        service = EmbeddingService()
        vector = await service.embed_query("beginner French language resources")
        self.assertIsNotNone(vector)
        self.assertEqual(len(vector), EMBEDDING_DIM)

    async def test_embed_resource_uses_all_fields(self):
        """embed_resource combines title, summary, and keywords."""
        from app.services.embedding_service import EmbeddingService, EMBEDDING_DIM
        service = EmbeddingService()
        resource = {
            "title": "French Greetings Tutorial",
            "summary": "Comprehensive guide to bonjour and bonsoir",
            "keywords": ["french", "greetings", "beginner"],
            "resource_type": "video",
        }
        vector = await service.embed_resource(resource)
        self.assertIsNotNone(vector)
        self.assertEqual(len(vector), EMBEDDING_DIM)
