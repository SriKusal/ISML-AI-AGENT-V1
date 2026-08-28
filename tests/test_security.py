"""Tests for security controls (ENH-009)."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


class TestApiKeyAuth(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint_accessible_without_key(self):
        """Health check must always be accessible."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)

    def test_auth_disabled_by_default(self):
        """When API_KEY_ENABLED=false (default), all requests pass."""
        with patch("app.security.settings") as mock_settings:
            mock_settings.API_KEY_ENABLED = False
            mock_settings.API_KEY = ""
            from app.security import verify_api_key
            import asyncio
            # Should not raise
            asyncio.run(verify_api_key(x_api_key=""))

    def test_auth_rejects_wrong_key(self):
        """When enabled, wrong key must be rejected."""
        with patch("app.security.settings") as mock_settings:
            mock_settings.API_KEY_ENABLED = True
            mock_settings.API_KEY = "correct-secret"
            from app.security import verify_api_key
            from fastapi import HTTPException
            import asyncio
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(verify_api_key(x_api_key="wrong-key"))
            self.assertEqual(ctx.exception.status_code, 401)

    def test_auth_accepts_correct_key(self):
        """When enabled, correct key must be accepted."""
        with patch("app.security.settings") as mock_settings:
            mock_settings.API_KEY_ENABLED = True
            mock_settings.API_KEY = "correct-secret"
            from app.security import verify_api_key
            import asyncio
            # Should not raise
            asyncio.run(verify_api_key(x_api_key="correct-secret"))

    def test_auth_rejects_empty_key_when_enabled(self):
        """Empty key must be rejected when auth is enabled."""
        with patch("app.security.settings") as mock_settings:
            mock_settings.API_KEY_ENABLED = True
            mock_settings.API_KEY = "secret"
            from app.security import verify_api_key
            from fastapi import HTTPException
            import asyncio
            with self.assertRaises(HTTPException):
                asyncio.run(verify_api_key(x_api_key=""))


class TestSsrfProtection(unittest.TestCase):

    def test_validate_external_url_public_accepted(self):
        from app.security import validate_external_url
        result = validate_external_url("https://example.com/resource")
        self.assertIsNotNone(result)

    def test_validate_external_url_localhost_rejected(self):
        from app.security import validate_external_url
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            validate_external_url("http://localhost/admin")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_external_url_private_ip_rejected(self):
        from app.security import validate_external_url
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            validate_external_url("http://192.168.1.1/secret")

    def test_validate_external_url_cloud_metadata_rejected(self):
        from app.security import validate_external_url
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            validate_external_url("http://169.254.169.254/latest/meta-data/")


class TestErrorEnvelope(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_404_returns_error_envelope(self):
        response = self.client.get("/api/v1/does-not-exist")
        self.assertEqual(response.status_code, 404)
        # FastAPI routes 404s through the HTTPException handler which
        # produces the standard envelope; Starlette-level 404s may use
        # {"detail": "Not Found"} — both are acceptable.
        body = response.json()
        has_envelope = "error" in body
        has_detail = "detail" in body
        self.assertTrue(has_envelope or has_detail)

    def test_422_validation_error_returns_error_envelope(self):
        """Sending invalid JSON body to a typed endpoint returns 422 envelope."""
        response = self.client.post(
            "/api/v1/llm/generate",
            json={"provider": "gemini"},  # missing required 'prompt'
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")


class TestResponseCache(unittest.TestCase):

    def test_cache_key_is_deterministic(self):
        from app.services.response_cache import LRUResponseCache
        k1 = LRUResponseCache.make_key("Language Learning", "French", "Greetings", "Beginner", "gemini")
        k2 = LRUResponseCache.make_key("Language Learning", "French", "Greetings", "Beginner", "gemini")
        self.assertEqual(k1, k2)

    def test_cache_key_differs_by_topic(self):
        from app.services.response_cache import LRUResponseCache
        k1 = LRUResponseCache.make_key("Lang", "French", "Greetings", "Beginner", "gemini")
        k2 = LRUResponseCache.make_key("Lang", "French", "Farewells", "Beginner", "gemini")
        self.assertNotEqual(k1, k2)

    def test_cache_stores_and_retrieves(self):
        from app.services.response_cache import LRUResponseCache
        cache = LRUResponseCache(max_size=10)
        cache.set("k1", {"result": "data"})
        retrieved = cache.get("k1")
        self.assertEqual(retrieved["result"], "data")

    def test_cache_miss_returns_none(self):
        from app.services.response_cache import LRUResponseCache
        cache = LRUResponseCache(max_size=10)
        self.assertIsNone(cache.get("nonexistent"))

    def test_disabled_cache_always_misses(self):
        from app.services.response_cache import LRUResponseCache
        cache = LRUResponseCache(max_size=0)
        cache.set("k1", {"result": "data"})
        self.assertIsNone(cache.get("k1"))

    def test_cache_evicts_lru_entry(self):
        from app.services.response_cache import LRUResponseCache
        cache = LRUResponseCache(max_size=2)
        cache.set("k1", {"v": 1})
        cache.set("k2", {"v": 2})
        cache.get("k1")  # access k1 so k2 becomes LRU
        cache.set("k3", {"v": 3})  # should evict k2
        self.assertIsNone(cache.get("k2"))
        self.assertIsNotNone(cache.get("k1"))
        self.assertIsNotNone(cache.get("k3"))

    def test_cache_stats_track_hits_and_misses(self):
        from app.services.response_cache import LRUResponseCache
        cache = LRUResponseCache(max_size=10)
        cache.set("k1", {"v": 1})
        cache.get("k1")  # hit
        cache.get("k2")  # miss
        stats = cache.stats
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.5)

    def test_cache_clear_empties_all_entries(self):
        from app.services.response_cache import LRUResponseCache
        cache = LRUResponseCache(max_size=10)
        for i in range(5):
            cache.set(f"k{i}", {"v": i})
        cache.clear()
        self.assertEqual(cache.stats["size"], 0)
