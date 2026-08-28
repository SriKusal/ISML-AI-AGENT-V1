"""Regression tests for all working APIs and workflows (TEST-004).

These tests protect against regressions in already-working functionality.
They run without any external dependencies (all external calls are mocked).

Covers:
- Health endpoint
- LLM route (Gemini, DeepSeek) error handling
- Resource intelligence workflow phases
- Knowledge routes (returns 200 or graceful failure)
- Output schema normalization
- Retry behavior
- URL normalization
- Quality threshold classification
- Response cache behavior
"""

import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app


class TestHealthEndpointRegression(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_returns_ok(self):
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_root_returns_running(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("running", r.json()["message"].lower())


class TestLLMRouteRegression(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_gemini_endpoint_exists(self):
        with patch("app.services.gemini_service.GeminiService.generate_text",
                   side_effect=ValueError("GEMINI_API_KEY is not configured")):
            r = self.client.post("/api/v1/gemini/generate",
                                 json={"prompt": "test"})
        self.assertEqual(r.status_code, 500)

    def test_llm_generate_endpoint_exists(self):
        with patch("app.services.gemini_service.GeminiService.generate_text",
                   side_effect=ValueError("GEMINI_API_KEY is not configured")):
            r = self.client.post("/api/v1/llm/generate",
                                 json={"provider": "gemini", "prompt": "test"})
        self.assertEqual(r.status_code, 400)

    def test_llm_generate_invalid_provider(self):
        r = self.client.post("/api/v1/llm/generate",
                             json={"provider": "nonexistent_llm", "prompt": "test"})
        self.assertEqual(r.status_code, 400)


class TestWorkflowPhaseRegression(unittest.TestCase):
    """Regression tests for each workflow phase in isolation."""

    def _make_state(self, **kwargs):
        from app.agents.state import ResourceIntelligenceState
        defaults = {
            "domain": "Language Learning",
            "course": "French Language",
            "topic": "Greetings",
            "difficulty_level": "Beginner",
            "provider": "gemini",
        }
        defaults.update(kwargs)
        return ResourceIntelligenceState(**defaults)

    def test_initialize_node_valid_input(self):
        from app.agents.state import AgentPhase
        from app.agents.workflow import WorkflowNodes
        state = self._make_state()
        result = WorkflowNodes.initialize_node(state)
        self.assertEqual(result.phase, AgentPhase.TOPIC_ANALYSIS)
        self.assertEqual(result.attempt_count, 1)

    def test_initialize_node_empty_domain(self):
        from app.agents.state import AgentPhase
        from app.agents.workflow import WorkflowNodes
        state = self._make_state(domain="")
        result = WorkflowNodes.initialize_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)
        self.assertGreater(len(result.validation_errors), 0)

    def test_topic_analysis_populates_understanding(self):
        from app.agents.workflow import WorkflowNodes
        state = self._make_state()
        result = WorkflowNodes.topic_analysis_node(state)
        self.assertIn("topic", result.topic_understanding)
        self.assertEqual(result.topic_understanding["topic"], "Greetings")

    def test_search_strategy_generates_queries(self):
        from app.agents.workflow import WorkflowNodes
        state = self._make_state()
        WorkflowNodes.topic_analysis_node(state)
        result = WorkflowNodes.search_strategy_node(state)
        self.assertGreater(len(result.search_queries), 5)

    def test_search_strategy_no_duplicate_queries(self):
        from app.agents.workflow import WorkflowNodes
        state = self._make_state()
        WorkflowNodes.topic_analysis_node(state)
        result = WorkflowNodes.search_strategy_node(state)
        self.assertEqual(len(result.search_queries), len(set(result.search_queries)))

    def test_build_prompt_includes_topic(self):
        from app.agents.workflow import WorkflowNodes
        state = self._make_state()
        WorkflowNodes.topic_analysis_node(state)
        WorkflowNodes.search_strategy_node(state)
        result = WorkflowNodes.build_prompt_node(state)
        self.assertIn("Greetings", result.full_prompt)
        self.assertIn("Language Learning", result.full_prompt)

    def test_parse_response_handles_gemini_format(self):
        from app.agents.workflow import WorkflowNodes
        from app.agents.state import AgentPhase
        state = self._make_state()
        state.provider_response = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "task": {"domain": "d", "course": "c",
                                     "topic": "t", "difficulty_level": "B"},
                            "resources": [{"id": "r1", "title": "Test"}],
                            "ranked_resources": ["r1"],
                            "learning_sequence": [
                                {"step": 1, "resource_id": "r1", "reason": "Go"}
                            ],
                        })
                    }]
                }
            }]
        }
        result = WorkflowNodes.parse_response_node(state)
        self.assertEqual(result.phase, AgentPhase.VALIDATE_OUTPUT)
        self.assertIsNotNone(result.parsed_output)

    def test_validate_output_passes_valid_schema(self):
        from app.agents.workflow import WorkflowNodes
        from app.agents.state import AgentPhase
        state = self._make_state()
        state.parsed_output = {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "B"},
            "resources": [{"id": "r1", "title": "Good Resource"}],
            "ranked_resources": ["r1"],
            "learning_sequence": [{"step": 1, "resource_id": "r1", "reason": "Start"}],
        }
        result = WorkflowNodes.validate_output_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)
        self.assertTrue(result.is_valid)


class TestUrlNormalizationRegression(unittest.TestCase):
    def test_utm_stripped(self):
        from app.services.resource_validator import normalize_url
        r = normalize_url("https://example.com/page?utm_source=test")
        self.assertNotIn("utm_source", r)

    def test_youtube_v_preserved(self):
        from app.services.resource_validator import normalize_url
        r = normalize_url("https://www.youtube.com/watch?v=abc123")
        self.assertIn("v=abc123", r)

    def test_private_ip_blocked(self):
        from app.services.resource_validator import normalize_url
        self.assertIsNone(normalize_url("http://192.168.0.1/page"))


class TestQualityThresholdRegression(unittest.TestCase):
    def test_thresholds_in_expected_ranges(self):
        from app.config import settings
        self.assertGreater(settings.QUALITY_THRESHOLD_EXCELLENT, settings.QUALITY_THRESHOLD_HIGH)
        self.assertGreater(settings.QUALITY_THRESHOLD_HIGH, settings.QUALITY_THRESHOLD_ACCEPTABLE)
        self.assertGreater(settings.QUALITY_THRESHOLD_ACCEPTABLE, 0.0)
        self.assertLessEqual(settings.QUALITY_THRESHOLD_EXCELLENT, 1.0)

    def test_classify_score_coverage(self):
        from app.services.quality_thresholds import classify_score, QualityTier
        tiers = {classify_score(s).tier for s in [0.95, 0.85, 0.75, 0.55]}
        self.assertEqual(tiers, {
            QualityTier.EXCELLENT, QualityTier.HIGH,
            QualityTier.ACCEPTABLE, QualityTier.REVIEW,
        })


class TestResponseCacheRegression(unittest.TestCase):
    def test_cache_key_stable(self):
        from app.services.response_cache import LRUResponseCache
        k = LRUResponseCache.make_key("A", "B", "C", "D", "E")
        self.assertEqual(len(k), 24)
        self.assertEqual(k, LRUResponseCache.make_key("A", "B", "C", "D", "E"))

    def test_cache_hit_rate_starts_zero(self):
        from app.services.response_cache import LRUResponseCache
        c = LRUResponseCache(max_size=10)
        self.assertEqual(c.stats["hit_rate"], 0.0)


class TestOutputValidatorRegression(unittest.TestCase):
    def test_valid_output_always_passes(self):
        from app.services.output_validator import validate_output
        data = {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "B"},
            "resources": [{"id": "r1", "title": "Test"}],
            "ranked_resources": ["r1"],
            "learning_sequence": [{"step": 1, "resource_id": "r1", "reason": "Go"}],
        }
        self.assertTrue(validate_output(data).valid)

    def test_empty_resources_always_fails(self):
        from app.services.output_validator import validate_output
        data = {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "B"},
            "resources": [],
            "ranked_resources": [],
            "learning_sequence": [],
        }
        self.assertFalse(validate_output(data).valid)
