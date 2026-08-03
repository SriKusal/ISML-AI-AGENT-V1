"""LangGraph agent state model for ISML Academic Resource Intelligence Agent.

This module defines the state structure and workflow for discovering,
evaluating, and ranking educational resources using LangGraph.
"""

from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class AgentPhase(str, Enum):
    """Phases in the resource intelligence workflow."""
    INITIALIZE = "initialize"
    TOPIC_ANALYSIS = "topic_analysis"
    SEARCH_STRATEGY = "search_strategy"
    BUILD_PROMPT = "build_prompt"
    QUERY_PROVIDER = "query_provider"
    PARSE_RESPONSE = "parse_response"
    VALIDATE_OUTPUT = "validate_output"
    COMPLETE = "complete"


@dataclass
class ResourceIntelligenceState:
    """State model for the resource intelligence agent workflow.
    
    Tracks the progression of a resource discovery and evaluation task
    from initial input through final validated output.
    """
    
    # Task input
    domain: str
    course: str
    topic: str
    difficulty_level: str = "Beginner"
    
    # Provider configuration
    provider: str = "gemini"
    model: Optional[str] = None
    
    # Workflow phase
    phase: AgentPhase = AgentPhase.INITIALIZE
    
    # Topic analysis output
    topic_understanding: dict = field(default_factory=dict)
    
    # Search strategy output
    search_queries: list[str] = field(default_factory=list)
    
    # Constructed prompts
    system_prompt: str = ""
    task_prompt: str = ""
    full_prompt: str = ""
    
    # Provider interaction
    provider_response: Optional[dict] = None
    provider_error: Optional[str] = None
    
    # Parsed and validated output
    parsed_output: Optional[dict] = None
    validation_errors: list[str] = field(default_factory=list)
    is_valid: bool = False
    
    # Metadata
    attempt_count: int = 0
    max_retries: int = 2
    messages: list[str] = field(default_factory=list)
    
    def add_message(self, message: str) -> None:
        """Log a workflow message."""
        self.messages.append(message)
    
    def add_error(self, error: str) -> None:
        """Log a validation error."""
        self.validation_errors.append(error)
    
    def should_retry(self) -> bool:
        """Check if the workflow should retry after a failure."""
        return self.attempt_count < self.max_retries
    
    def increment_attempt(self) -> None:
        """Increment the attempt counter."""
        self.attempt_count += 1


@dataclass
class ResourceIntelligenceOutput:
    """Structured output from the resource intelligence agent.
    
    Contains the final discovered, ranked, and categorized resources.
    """
    task: dict
    summary: dict
    resources: list[dict] = field(default_factory=list)
    ranked_resources: list[str] = field(default_factory=list)
    learning_sequence: list[dict] = field(default_factory=list)
    recommendations: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dictionary."""
        return {
            "task": self.task,
            "summary": self.summary,
            "resources": self.resources,
            "ranked_resources": self.ranked_resources,
            "learning_sequence": self.learning_sequence,
            "recommendations": self.recommendations,
        }
