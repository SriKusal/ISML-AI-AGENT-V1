"""Workflow node definitions for the ISML Academic Resource Intelligence Agent.

Each node represents a stage in the agent's workflow and operates on the shared state.
"""

from typing import Optional
import json

from app.agents.state import ResourceIntelligenceState, AgentPhase, ResourceIntelligenceOutput
from app.services.provider_factory import LLMProviderFactory
from prompts import SYSTEM_PROMPT_TEMPLATE, TASK_PROMPT_TEMPLATE
from app.logging import get_logger

logger = get_logger("app.agents.workflow")


class WorkflowNodes:
    """Collection of node functions for the LangGraph workflow."""
    
    @staticmethod
    def initialize_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Initialize the workflow state and validate input."""
        logger.info(
            "Initializing workflow: domain=%s, course=%s, topic=%s, difficulty=%s",
            state.domain, state.course, state.topic, state.difficulty_level
        )
        
        if not all([state.domain, state.course, state.topic]):
            state.add_error("Missing required fields: domain, course, or topic")
            state.phase = AgentPhase.COMPLETE
            return state
        
        state.add_message("Workflow initialized with valid inputs")
        state.phase = AgentPhase.TOPIC_ANALYSIS
        state.increment_attempt()
        return state
    
    @staticmethod
    def topic_analysis_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Analyze the learning topic and extract context."""
        logger.info("Analyzing topic: %s in course: %s", state.topic, state.course)
        
        try:
            topic_context = {
                "domain": state.domain,
                "course": state.course,
                "topic": state.topic,
                "difficulty_level": state.difficulty_level,
                "related_concepts": [],
                "learning_objectives": [],
                "required_skills": [],
                "assessment_criteria": [],
            }
            
            # Analyze based on domain and difficulty
            if "language" in state.domain.lower():
                topic_context["related_concepts"] = ["vocabulary", "grammar", "pronunciation", "comprehension"]
                topic_context["learning_objectives"] = [
                    f"Understand {state.topic} in {state.course}",
                    f"Practice {state.topic} communication",
                    "Build cultural awareness",
                ]
                topic_context["required_skills"] = ["listening", "speaking", "reading", "writing"]
                topic_context["assessment_criteria"] = ["accuracy", "fluency", "comprehension", "cultural appropriateness"]
            
            state.topic_understanding = topic_context
            state.add_message("Topic analysis completed: extracted learning context")
            state.phase = AgentPhase.SEARCH_STRATEGY
        except Exception as exc:
            state.add_error(f"Failed to analyze topic: {exc}")
            state.phase = AgentPhase.COMPLETE
        
        return state
    
    @staticmethod
    def search_strategy_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Generate intelligent search queries based on topic understanding."""
        logger.info("Generating search strategy for: %s", state.topic)
        
        try:
            queries = []
            topic = state.topic
            course = state.course
            domain = state.domain
            difficulty = state.difficulty_level.lower()
            
            # Core topic searches
            queries.append(f"{topic} {course}")
            queries.append(f"{topic} {difficulty} tutorial")
            
            # Resource-type specific searches
            queries.append(f"{topic} video {difficulty}")
            queries.append(f"{topic} guide PDF")
            queries.append(f"{topic} worksheet practice")
            queries.append(f"{topic} pronunciation audio")
            
            # Domain-specific searches
            if "language" in domain.lower():
                language = course.split()[-1] if " " in course else course
                queries.append(f"{language} {topic} beginner")
                queries.append(f"{language} {topic} vocabulary")
                queries.append(f"{language} {topic} conversation")
                queries.append(f"{topic} listening comprehension")
                queries.append(f"{topic} speaking practice")
            
            # Broader context searches
            queries.append(f"learn {topic}")
            queries.append(f"{topic} learning resources")
            queries.append(f"{topic} study materials")
            
            # Remove duplicates while preserving order
            seen = set()
            unique_queries = []
            for q in queries:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    unique_queries.append(q)
            
            state.search_queries = unique_queries
            state.add_message(f"Search strategy generated: {len(unique_queries)} query variations")
            state.phase = AgentPhase.BUILD_PROMPT
        except Exception as exc:
            state.add_error(f"Failed to generate search strategy: {exc}")
            state.phase = AgentPhase.COMPLETE
        
        return state
    
    @staticmethod
    def build_prompt_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Build system and task prompts from templates."""
        logger.info("Building prompts for topic: %s", state.topic)
        
        try:
            state.system_prompt = SYSTEM_PROMPT_TEMPLATE
            state.task_prompt = TASK_PROMPT_TEMPLATE.format(
                domain=state.domain,
                course=state.course,
                topic=state.topic,
                difficulty_level=state.difficulty_level,
            )
            state.full_prompt = f"{state.system_prompt}\n\n{state.task_prompt}"
            
            state.add_message("Prompts built successfully")
            state.phase = AgentPhase.QUERY_PROVIDER
        except Exception as exc:
            state.add_error(f"Failed to build prompts: {exc}")
            state.phase = AgentPhase.COMPLETE
        
        return state
    
    @staticmethod
    async def query_provider_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Send the full prompt to the selected LLM provider."""
        logger.info("Querying provider: %s", state.provider)
        
        try:
            provider = LLMProviderFactory.create(state.provider)
            model = state.model or ""
            
            response = await provider.generate_text(state.full_prompt, model)
            state.provider_response = response
            
            state.add_message(f"Provider response received from {state.provider}")
            state.phase = AgentPhase.PARSE_RESPONSE
        except Exception as exc:
            state.provider_error = str(exc)
            state.add_error(f"Provider request failed: {exc}")
            
            if state.should_retry():
                state.add_message(f"Retry attempt {state.attempt_count + 1}")
                state.increment_attempt()
                state.phase = AgentPhase.BUILD_PROMPT
            else:
                state.phase = AgentPhase.COMPLETE
        
        return state
    
    @staticmethod
    def parse_response_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Parse the provider response into structured JSON."""
        logger.info("Parsing provider response")
        
        if not state.provider_response:
            state.add_error("No provider response to parse")
            state.phase = AgentPhase.COMPLETE
            return state
        
        try:
            response_data = state.provider_response
            
            if isinstance(response_data, dict) and "candidates" in response_data:
                content = response_data["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text_content = parts[0].get("text", "")
                    state.parsed_output = json.loads(text_content)
            elif isinstance(response_data, dict) and "choices" in response_data:
                choice = response_data["choices"][0]
                text_content = choice.get("message", {}).get("content", "")
                state.parsed_output = json.loads(text_content)
            else:
                state.add_error("Unexpected provider response format")
                state.phase = AgentPhase.COMPLETE
                return state
            
            state.add_message("Response parsed successfully")
            state.phase = AgentPhase.VALIDATE_OUTPUT
        except Exception as exc:
            state.add_error(f"Failed to parse response: {exc}")
            state.phase = AgentPhase.COMPLETE
        
        return state
    
    @staticmethod
    def validate_output_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Validate the parsed output against the expected schema."""
        logger.info("Validating parsed output")
        
        if not state.parsed_output:
            state.add_error("No parsed output to validate")
            state.phase = AgentPhase.COMPLETE
            return state
        
        try:
            output = state.parsed_output
            
            required_fields = ["task", "resources", "ranked_resources", "learning_sequence"]
            for field in required_fields:
                if field not in output:
                    state.add_error(f"Missing required field: {field}")
            
            if not state.validation_errors:
                state.is_valid = True
                state.add_message("Output validation passed")
            else:
                state.add_message(f"Validation found {len(state.validation_errors)} issues")
            
            state.phase = AgentPhase.COMPLETE
        except Exception as exc:
            state.add_error(f"Validation check failed: {exc}")
            state.phase = AgentPhase.COMPLETE
        
        return state
    
    @staticmethod
    def complete_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Finalize the workflow and prepare output."""
        logger.info("Workflow complete. Valid: %s, Errors: %d", state.is_valid, len(state.validation_errors))
        return state
