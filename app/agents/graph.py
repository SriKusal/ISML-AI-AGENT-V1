"""LangGraph graph definition for the ISML Academic Resource Intelligence Agent.

Defines the workflow graph with nodes, edges, and conditional routing.
"""

from typing import Any

from app.agents.state import ResourceIntelligenceState, AgentPhase
from app.agents.workflow import WorkflowNodes
from app.logging import get_logger

logger = get_logger("app.agents.graph")


class ResourceIntelligenceGraph:
    """Manages the LangGraph workflow for resource intelligence."""
    
    def __init__(self):
        """Initialize the graph structure."""
        self.nodes = WorkflowNodes()
    
    def get_node_functions(self) -> dict[str, Any]:
        """Return a mapping of node names to their functions."""
        return {
            "initialize": self.nodes.initialize_node,
            "topic_analysis": self.nodes.topic_analysis_node,
            "search_strategy": self.nodes.search_strategy_node,
            "discover_resources": self.nodes.discover_resources_node,
            "build_prompt": self.nodes.build_prompt_node,
            "query_provider": self.nodes.query_provider_node,
            "parse_response": self.nodes.parse_response_node,
            "validate_output": self.nodes.validate_output_node,
            "complete": self.nodes.complete_node,
        }
    
    def get_edge_mapping(self) -> dict[str, str]:
        """Return the default edge routing based on phase."""
        return {
            AgentPhase.INITIALIZE: "initialize",
            AgentPhase.TOPIC_ANALYSIS: "topic_analysis",
            AgentPhase.SEARCH_STRATEGY: "search_strategy",
            AgentPhase.DISCOVER_RESOURCES: "discover_resources",
            AgentPhase.BUILD_PROMPT: "build_prompt",
            AgentPhase.QUERY_PROVIDER: "query_provider",
            AgentPhase.PARSE_RESPONSE: "parse_response",
            AgentPhase.VALIDATE_OUTPUT: "validate_output",
            AgentPhase.COMPLETE: "complete",
        }
    
    def get_next_node(self, state: ResourceIntelligenceState) -> str:
        """Determine the next node based on current phase."""
        mapping = self.get_edge_mapping()
        next_node = mapping.get(state.phase, "complete")
        logger.debug("Transitioning to node: %s (phase: %s)", next_node, state.phase)
        return next_node


def create_resource_intelligence_graph() -> ResourceIntelligenceGraph:
    """Factory function to create and return a new graph instance."""
    return ResourceIntelligenceGraph()
