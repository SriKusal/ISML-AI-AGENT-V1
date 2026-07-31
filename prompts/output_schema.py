"""Output JSON template for the ISML Academic Resource Intelligence Agent.

This module defines a structured JSON schema that the agent should return.
It can be used as a documentation reference or as a literal template for prompts.
"""

OUTPUT_JSON_TEMPLATE = {
    "task": {
        "domain": "{domain}",
        "course": "{course}",
        "topic": "{topic}",
        "difficulty_level": "{difficulty_level}"
    },
    "summary": {
        "overview": "string",
        "recommended_learning_goal": "string"
    },
    "resources": [
        {
            "id": "string",
            "title": "string",
            "source": "string",
            "type": "string",
            "url": "string|null",
            "summary": "string",
            "modality": "string|null",
            "audience_level": "string|null",
            "estimated_effort": "string|null",
            "language": "string|null",
            "category": "foundation|practice|advanced|supplementary|assessment",
            "scores": {
                "relevance": 0.0,
                "clarity": 0.0,
                "accuracy": 0.0,
                "pedagogy": 0.0,
                "credibility": 0.0,
                "accessibility": 0.0,
                "practicality": 0.0,
                "overall": 0.0
            },
            "rationale": {
                "relevance": "string",
                "clarity": "string",
                "accuracy": "string",
                "pedagogy": "string",
                "credibility": "string",
                "accessibility": "string",
                "practicality": "string",
                "overall": "string"
            }
        }
    ],
    "ranked_resources": ["resource_id_1", "resource_id_2"],
    "learning_sequence": [
        {
            "step": 1,
            "resource_id": "string",
            "reason": "string"
        }
    ],
    "recommendations": {
        "best_starting_resource": "string|null",
        "best_practice_resource": "string|null",
        "best_advanced_resource": "string|null"
    }
}
