"""Tests for individual workflow nodes.

Validates:
- Each node transitions to the correct next phase
- Input validation works for missing fields
- Topic analysis populates topic_understanding correctly
- Search strategy generates deduplicated queries
- Build prompt populates all prompt fields
- Parse response handles Gemini and DeepSeek formats
- Parse response handles markdown code fences
- Validate output normalises LLM alias keys
- Retry logic triggers correctly on provider failure
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.agents.state import ResourceIntelligenceState, AgentPhase
from app.agents.workflow import WorkflowNodes
from tests.test_dataset import TOPIC_DATASET, LANGUAGE_TOPICS, CS_TOPICS


def make_state(**kwargs) -> ResourceIntelligenceState:
    defaults = {
        "domain": "Language Learning",
        "course": "Japanese Language",
        "topic": "Hiragana",
        "difficulty_level": "Beginner",
        "provider": "gemini",
    }
    defaults.update(kwargs)
    return ResourceIntelligenceState(**defaults)


class TestInitializeNode(unittest.TestCase):

    def test_valid_input_transitions_to_topic_analysis(self):
        state = make_state()
        result = WorkflowNodes.initialize_node(state)
        self.assertEqual(result.phase, AgentPhase.TOPIC_ANALYSIS)

    def test_missing_domain_goes_to_complete(self):
        state = make_state(domain="")
        result = WorkflowNodes.initialize_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)
        self.assertTrue(len(result.validation_errors) > 0)

    def test_missing_course_goes_to_complete(self):
        state = make_state(course="")
        result = WorkflowNodes.initialize_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)

    def test_missing_topic_goes_to_complete(self):
        state = make_state(topic="")
        result = WorkflowNodes.initialize_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)

    def test_attempt_count_incremented(self):
        state = make_state()
        result = WorkflowNodes.initialize_node(state)
        self.assertEqual(result.attempt_count, 1)

    def test_all_50_topics_pass_validation(self):
        """Every topic in the dataset should pass initialize_node."""
        failures = []
        for t in TOPIC_DATASET:
            state = ResourceIntelligenceState(**t, provider="gemini")
            result = WorkflowNodes.initialize_node(state)
            if result.phase == AgentPhase.COMPLETE:
                failures.append(t["topic"])
        self.assertEqual(failures, [], f"Topics failed init: {failures}")


class TestTopicAnalysisNode(unittest.TestCase):

    def test_language_domain_populates_concepts(self):
        state = make_state()
        state.phase = AgentPhase.TOPIC_ANALYSIS
        result = WorkflowNodes.topic_analysis_node(state)
        self.assertIn("related_concepts", result.topic_understanding)
        self.assertIn("learning_objectives", result.topic_understanding)
        self.assertIn("required_skills", result.topic_understanding)

    def test_topic_understanding_contains_input_fields(self):
        state = make_state()
        result = WorkflowNodes.topic_analysis_node(state)
        self.assertEqual(result.topic_understanding["topic"], "Hiragana")
        self.assertEqual(result.topic_understanding["domain"], "Language Learning")

    def test_transitions_to_search_strategy(self):
        state = make_state()
        result = WorkflowNodes.topic_analysis_node(state)
        # topic_analysis now transitions to KNOWLEDGE_RETRIEVAL (ENH-006)
        # which then routes to SEARCH_STRATEGY when no DB resources exist
        self.assertEqual(result.phase, AgentPhase.KNOWLEDGE_RETRIEVAL)

    def test_cs_domain_completes_without_error(self):
        for t in CS_TOPICS[:5]:
            state = ResourceIntelligenceState(**t, provider="gemini")
            result = WorkflowNodes.topic_analysis_node(state)
            self.assertNotEqual(result.phase, AgentPhase.COMPLETE,
                                f"Topic analysis failed for {t['topic']}")


class TestSearchStrategyNode(unittest.TestCase):

    def test_generates_queries(self):
        state = make_state()
        WorkflowNodes.topic_analysis_node(state)
        result = WorkflowNodes.search_strategy_node(state)
        self.assertGreater(len(result.search_queries), 0)

    def test_queries_are_deduplicated(self):
        state = make_state()
        WorkflowNodes.topic_analysis_node(state)
        result = WorkflowNodes.search_strategy_node(state)
        self.assertEqual(len(result.search_queries), len(set(result.search_queries)))

    def test_transitions_to_discover_resources(self):
        state = make_state()
        WorkflowNodes.topic_analysis_node(state)
        result = WorkflowNodes.search_strategy_node(state)
        self.assertEqual(result.phase, AgentPhase.DISCOVER_RESOURCES)

    def test_language_domain_generates_more_queries(self):
        state = make_state(domain="Language Learning", course="Japanese Language")
        WorkflowNodes.topic_analysis_node(state)
        result = WorkflowNodes.search_strategy_node(state)
        self.assertGreaterEqual(len(result.search_queries), 10)

    def test_all_dataset_topics_generate_queries(self):
        failures = []
        for t in TOPIC_DATASET:
            state = ResourceIntelligenceState(**t, provider="gemini")
            WorkflowNodes.topic_analysis_node(state)
            result = WorkflowNodes.search_strategy_node(state)
            if len(result.search_queries) == 0:
                failures.append(t["topic"])
        self.assertEqual(failures, [], f"No queries generated for: {failures}")


class TestBuildPromptNode(unittest.TestCase):

    def _prepared_state(self):
        state = make_state()
        WorkflowNodes.initialize_node(state)
        WorkflowNodes.topic_analysis_node(state)
        WorkflowNodes.search_strategy_node(state)
        return state

    def test_prompts_are_populated(self):
        state = self._prepared_state()
        result = WorkflowNodes.build_prompt_node(state)
        self.assertTrue(len(result.system_prompt) > 0)
        self.assertTrue(len(result.task_prompt) > 0)
        self.assertTrue(len(result.full_prompt) > 0)

    def test_task_prompt_contains_topic(self):
        state = self._prepared_state()
        result = WorkflowNodes.build_prompt_node(state)
        self.assertIn("Hiragana", result.task_prompt)

    def test_task_prompt_contains_domain(self):
        state = self._prepared_state()
        result = WorkflowNodes.build_prompt_node(state)
        self.assertIn("Language Learning", result.task_prompt)

    def test_transitions_to_query_provider(self):
        state = self._prepared_state()
        result = WorkflowNodes.build_prompt_node(state)
        self.assertEqual(result.phase, AgentPhase.QUERY_PROVIDER)


class TestParseResponseNode(unittest.TestCase):

    def _state_with_response(self, response_data):
        state = make_state()
        state.provider_response = response_data
        return state

    def _valid_output(self):
        return {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "Beginner"},
            "resources": [{"id": "r1", "title": "Test"}],
            "ranked_resources": ["r1"],
            "learning_sequence": [{"step": 1, "resource_id": "r1", "reason": "Start here"}],
        }

    def test_parses_gemini_format(self):
        response = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(self._valid_output())}]}}]
        }
        state = self._state_with_response(response)
        result = WorkflowNodes.parse_response_node(state)
        self.assertIsNotNone(result.parsed_output)
        self.assertEqual(result.phase, AgentPhase.VALIDATE_OUTPUT)

    def test_parses_deepseek_format(self):
        response = {
            "choices": [{"message": {"content": json.dumps(self._valid_output())}}]
        }
        state = self._state_with_response(response)
        result = WorkflowNodes.parse_response_node(state)
        self.assertIsNotNone(result.parsed_output)

    def test_strips_markdown_code_fences(self):
        fenced = "```json\n" + json.dumps(self._valid_output()) + "\n```"
        response = {"candidates": [{"content": {"parts": [{"text": fenced}]}}]}
        state = self._state_with_response(response)
        result = WorkflowNodes.parse_response_node(state)
        self.assertIsNotNone(result.parsed_output)
        self.assertEqual(result.phase, AgentPhase.VALIDATE_OUTPUT)

    def test_no_response_goes_to_complete(self):
        state = make_state()
        state.provider_response = None
        result = WorkflowNodes.parse_response_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)

    def test_invalid_json_triggers_retry_when_attempts_remain(self):
        response = {"candidates": [{"content": {"parts": [{"text": "not valid json {{{}"}]}}]}
        state = self._state_with_response(response)
        state.attempt_count = 0
        state.max_retries = 2
        result = WorkflowNodes.parse_response_node(state)
        self.assertEqual(result.phase, AgentPhase.BUILD_PROMPT)

    def test_invalid_json_goes_to_complete_when_retries_exhausted(self):
        response = {"candidates": [{"content": {"parts": [{"text": "not valid json {{{}"}]}}]}
        state = self._state_with_response(response)
        state.attempt_count = 2
        state.max_retries = 2
        result = WorkflowNodes.parse_response_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)


class TestValidateOutputNode(unittest.TestCase):

    def _state_with_output(self, output):
        state = make_state()
        state.parsed_output = output
        return state

    def test_valid_output_passes(self):
        output = {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "B"},
            "resources": [{"id": "r1", "title": "Test Resource"}],
            "ranked_resources": ["r1"],
            "learning_sequence": [{"step": 1, "resource_id": "r1", "reason": "Start"}],
        }
        state = self._state_with_output(output)
        result = WorkflowNodes.validate_output_node(state)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.validation_errors), 0)

    def test_normalises_ranked_resource_ids_alias(self):
        output = {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "B"},
            "resources": [],
            "ranked_resource_ids": ["r1"],
            "learning_sequence": [],
        }
        state = self._state_with_output(output)
        result = WorkflowNodes.validate_output_node(state)
        self.assertIn("ranked_resources", result.parsed_output)
        self.assertNotIn("ranked_resource_ids", result.parsed_output)

    def test_normalises_recommended_sequence_alias(self):
        output = {
            "task": {},
            "resources": [],
            "ranked_resources": [],
            "recommended_sequence": [{"step": 1, "resource_id": "r1", "reasoning": "Start here"}],
        }
        state = self._state_with_output(output)
        result = WorkflowNodes.validate_output_node(state)
        self.assertIn("learning_sequence", result.parsed_output)
        # reasoning should be normalised to reason
        seq = result.parsed_output["learning_sequence"]
        if seq:
            self.assertIn("reason", seq[0])

    def test_synthesises_task_from_state_when_missing(self):
        output = {
            "resources": [],
            "ranked_resources": [],
            "learning_sequence": [],
        }
        state = self._state_with_output(output)
        result = WorkflowNodes.validate_output_node(state)
        self.assertIn("task", result.parsed_output)
        self.assertEqual(result.parsed_output["task"]["topic"], "Hiragana")

    def test_synthesises_task_from_top_level_fields(self):
        output = {
            "domain": "Language Learning",
            "course": "Japanese Language",
            "topic": "Hiragana",
            "difficulty_level": "Beginner",
            "resources": [],
            "ranked_resources": [],
            "learning_sequence": [],
        }
        state = self._state_with_output(output)
        result = WorkflowNodes.validate_output_node(state)
        self.assertIn("task", result.parsed_output)

    def test_synthesises_ranked_resources_from_resource_ranking_field(self):
        output = {
            "task": {},
            "resources": [{"id": "r1", "ranking": 1}, {"id": "r2", "ranking": 2}],
            "learning_sequence": [],
        }
        state = self._state_with_output(output)
        result = WorkflowNodes.validate_output_node(state)
        self.assertIn("ranked_resources", result.parsed_output)
        self.assertEqual(result.parsed_output["ranked_resources"][0], "r1")

    def test_synthesises_learning_sequence_from_ranked_resources(self):
        output = {
            "task": {},
            "resources": [],
            "ranked_resources": ["r1", "r2", "r3"],
        }
        state = self._state_with_output(output)
        result = WorkflowNodes.validate_output_node(state)
        self.assertIn("learning_sequence", result.parsed_output)
        self.assertGreater(len(result.parsed_output["learning_sequence"]), 0)

    def test_no_output_goes_to_complete(self):
        state = make_state()
        state.parsed_output = None
        result = WorkflowNodes.validate_output_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)
        self.assertFalse(result.is_valid)


class TestRetryBehaviour(unittest.IsolatedAsyncioTestCase):

    async def test_query_provider_retries_on_failure(self):
        """If provider fails and retries remain, phase should rewind to BUILD_PROMPT."""
        state = make_state()
        state.full_prompt = "test prompt"
        state.attempt_count = 0
        state.max_retries = 2

        with patch(
            "app.agents.workflow.LLMProviderFactory.create"
        ) as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.generate_text.side_effect = Exception("503 Service Unavailable")
            mock_factory.return_value = mock_provider

            result = await WorkflowNodes.query_provider_node(state)

        self.assertEqual(result.phase, AgentPhase.BUILD_PROMPT)
        self.assertGreater(result.attempt_count, 0)

    async def test_query_provider_goes_to_complete_when_retries_exhausted(self):
        state = make_state()
        state.full_prompt = "test prompt"
        state.attempt_count = 2
        state.max_retries = 2

        with patch(
            "app.agents.workflow.LLMProviderFactory.create"
        ) as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.generate_text.side_effect = Exception("503 error")
            mock_factory.return_value = mock_provider

            result = await WorkflowNodes.query_provider_node(state)

        self.assertEqual(result.phase, AgentPhase.COMPLETE)
