"""Tests for Pydantic output schema validation (BUG-014, BUG-016)."""

import unittest

from app.services.output_validator import validate_output, OutputSchema


def _valid_output(**overrides):
    base = {
        "task": {
            "domain": "Language Learning",
            "course": "French Language",
            "topic": "Greetings",
            "difficulty_level": "Beginner",
        },
        "resources": [
            {"id": "r1", "title": "French Greetings Tutorial", "source": "youtube",
             "type": "video", "url": "https://youtube.com/watch?v=abc123", "summary": "Good intro"},
        ],
        "ranked_resources": ["r1"],
        "learning_sequence": [{"step": 1, "resource_id": "r1", "reason": "Start here"}],
    }
    base.update(overrides)
    return base


class TestValidateOutput(unittest.TestCase):

    def test_valid_complete_output_passes(self):
        result = validate_output(_valid_output())
        self.assertTrue(result.valid)
        self.assertIsNotNone(result.schema)
        self.assertEqual(result.errors, [])

    def test_missing_task_fails(self):
        data = _valid_output()
        del data["task"]
        result = validate_output(data)
        self.assertFalse(result.valid)
        self.assertGreater(len(result.errors), 0)

    def test_missing_resources_fails(self):
        data = _valid_output()
        del data["resources"]
        result = validate_output(data)
        self.assertFalse(result.valid)

    def test_empty_resources_list_fails(self):
        data = _valid_output(resources=[])
        result = validate_output(data)
        self.assertFalse(result.valid)
        self.assertTrue(any("resources" in e.lower() or "empty" in e.lower()
                             for e in result.errors))

    def test_resource_missing_id_fails(self):
        data = _valid_output(resources=[{"title": "No ID resource"}])
        result = validate_output(data)
        self.assertFalse(result.valid)

    def test_resource_empty_id_fails(self):
        data = _valid_output(resources=[{"id": "", "title": "Empty ID"}])
        result = validate_output(data)
        self.assertFalse(result.valid)

    def test_resource_missing_title_fails(self):
        data = _valid_output(resources=[{"id": "r1"}])
        result = validate_output(data)
        self.assertFalse(result.valid)

    def test_task_missing_domain_fails(self):
        data = _valid_output()
        data["task"] = {"course": "French", "topic": "Greetings", "difficulty_level": "Beginner"}
        result = validate_output(data)
        self.assertFalse(result.valid)

    def test_non_dict_input_fails(self):
        result = validate_output("not a dict")  # type: ignore
        self.assertFalse(result.valid)
        self.assertEqual(result.errors, ["Output is not a JSON object"])

    def test_extra_fields_ignored(self):
        data = _valid_output()
        data["unexpected_field"] = "should be ignored"
        result = validate_output(data)
        self.assertTrue(result.valid)

    def test_optional_summary_accepted(self):
        data = _valid_output()
        data["summary"] = {"overview": "Good topic", "recommended_learning_goal": "Be fluent"}
        result = validate_output(data)
        self.assertTrue(result.valid)
        self.assertEqual(result.schema.summary.overview, "Good topic")

    def test_learning_step_requires_step_number(self):
        data = _valid_output()
        data["learning_sequence"] = [{"resource_id": "r1", "reason": "Start"}]  # no step
        result = validate_output(data)
        self.assertFalse(result.valid)

    def test_learning_step_number_must_be_positive(self):
        data = _valid_output()
        data["learning_sequence"] = [{"step": 0, "resource_id": "r1", "reason": "Start"}]
        result = validate_output(data)
        self.assertFalse(result.valid)

    def test_repair_prompt_fragment_non_empty_on_failure(self):
        data = _valid_output(resources=[])
        result = validate_output(data)
        self.assertFalse(result.valid)
        fragment = result.repair_prompt_fragment()
        self.assertGreater(len(fragment), 0)
        self.assertIn("validation", fragment.lower())

    def test_repair_prompt_fragment_empty_on_success(self):
        result = validate_output(_valid_output())
        self.assertEqual(result.repair_prompt_fragment(), "")

    def test_multiple_resources_all_valid(self):
        data = _valid_output(resources=[
            {"id": f"r{i}", "title": f"Resource {i}"}
            for i in range(5)
        ])
        result = validate_output(data)
        self.assertTrue(result.valid)
        self.assertEqual(len(result.schema.resources), 5)


class TestRepairRetryInWorkflow(unittest.IsolatedAsyncioTestCase):
    """Verify validate_output_node triggers repair-retry on schema failure."""

    async def test_schema_failure_rewinds_to_build_prompt_when_retries_remain(self):
        from app.agents.state import ResourceIntelligenceState, AgentPhase
        from app.agents.workflow import WorkflowNodes

        state = ResourceIntelligenceState(
            domain="Language Learning",
            course="French Language",
            topic="Greetings",
            difficulty_level="Beginner",
        )
        # Empty resources — will fail Pydantic schema
        state.parsed_output = {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "B"},
            "resources": [],
            "ranked_resources": [],
            "learning_sequence": [],
        }
        state.attempt_count = 0
        state.max_retries = 2

        result = WorkflowNodes.validate_output_node(state)

        self.assertEqual(result.phase, AgentPhase.BUILD_PROMPT)
        self.assertEqual(result.attempt_count, 1)
        self.assertTrue(hasattr(result, "_repair_fragment"))
        self.assertGreater(len(result._repair_fragment), 0)

    async def test_schema_failure_goes_to_complete_when_retries_exhausted(self):
        from app.agents.state import ResourceIntelligenceState, AgentPhase
        from app.agents.workflow import WorkflowNodes

        state = ResourceIntelligenceState(
            domain="d", course="c", topic="t"
        )
        state.parsed_output = {
            "task": {"domain": "d", "course": "c", "topic": "t", "difficulty_level": "B"},
            "resources": [],
            "ranked_resources": [],
            "learning_sequence": [],
        }
        state.attempt_count = 2
        state.max_retries = 2

        result = WorkflowNodes.validate_output_node(state)
        self.assertEqual(result.phase, AgentPhase.COMPLETE)
        self.assertFalse(result.is_valid)

    async def test_repair_fragment_prepended_in_build_prompt(self):
        from app.agents.state import ResourceIntelligenceState, AgentPhase
        from app.agents.workflow import WorkflowNodes

        state = ResourceIntelligenceState(
            domain="Language Learning", course="French Language", topic="Greetings"
        )
        state._repair_fragment = "REPAIR: 'resources' list must not be empty"  # type: ignore
        result = WorkflowNodes.build_prompt_node(state)
        self.assertIn("REPAIR", result.task_prompt)
