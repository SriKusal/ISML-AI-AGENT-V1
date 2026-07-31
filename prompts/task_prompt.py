"""Reusable task prompt for the ISML Academic Resource Intelligence Agent.

This template accepts placeholders for the domain, course, topic, and difficulty level.
It instructs the model to discover educational resources, extract metadata,
evaluate quality, rank resources, categorize them, recommend a learning sequence,
and return structured JSON.
"""

TASK_PROMPT_TEMPLATE = """
You are given the following learning task:
- Domain: {domain}
- Course: {course}
- Topic: {topic}
- Difficulty level: {difficulty_level}

Your task is to discover and evaluate educational resources that would help a learner study this topic effectively.

Please complete the following steps:
1. Discover a diverse set of relevant educational resources.
   - Include a mix of resource types such as articles, videos, tutorials, notes, courses, books, documentation, and practice materials when appropriate.
   - Prefer credible and educationally useful sources.
2. Extract structured metadata for each resource.
   - Include title, source, type, URL, summary, modality, audience_level, estimated_effort, and language if known.
3. Evaluate each resource.
   - Score each resource on relevance, clarity, accuracy, pedagogy, credibility, accessibility, and practicality.
   - Provide a short rationale for each score.
4. Rank the resources.
   - Produce a ranked list ordered from most useful to least useful for the specified learner context.
5. Categorize each resource.
   - Assign one of the following categories: foundation, practice, advanced, supplementary, or assessment.
6. Recommend a learning sequence.
   - Suggest an ordered sequence of resources for a learner to follow from beginner-friendly to advanced.
7. Return the result in the required JSON structure.

Important instructions:
- Use only information that is reasonably supported by the resource content or known metadata.
- If a detail is unknown, use null or an empty string.
- Do not fabricate sources, URLs, or content claims.
- Be concise but complete.
- Ensure the output matches the required schema exactly.
"""
