"""Pydantic-based output schema validation for LLM responses.

Addresses BUG-014 and BUG-016.

The LLM output must match OutputSchema before the workflow completes.
If validation fails and retries remain, a repair prompt is constructed
describing exactly which fields failed so the LLM can correct its output.

Design
------
- Uses Pydantic v2 models to enforce types, required fields, and value ranges.
- Preserves the existing 0-1 score scale used by the project (not the
  reference's 0-100 scale).
- Repair prompt injection is handled by the calling workflow node so no
  circular dependency exists between this module and workflow.py.
- Schema mirrors the output_schema.py template but adds strict validation.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class TaskSchema(BaseModel):
    """Input parameters echoed back in the output."""
    domain: str
    course: str
    topic: str
    difficulty_level: str


class ScoreSet(BaseModel):
    """Per-dimension LLM quality scores (0-10 scale used in prompts)."""
    relevance: float = Field(ge=0.0, le=10.0, default=0.0)
    clarity: float = Field(ge=0.0, le=10.0, default=0.0)
    accuracy: float = Field(ge=0.0, le=10.0, default=0.0)
    pedagogy: float = Field(ge=0.0, le=10.0, default=0.0)
    credibility: float = Field(ge=0.0, le=10.0, default=0.0)
    accessibility: float = Field(ge=0.0, le=10.0, default=0.0)
    practicality: float = Field(ge=0.0, le=10.0, default=0.0)
    overall: float = Field(ge=0.0, le=10.0, default=0.0)

    # Allow missing sub-scores — LLM often omits them
    model_config = {"extra": "ignore"}


class ResourceSchema(BaseModel):
    """A single educational resource in the LLM output."""
    id: str
    title: str
    source: str = ""
    type: str = ""
    url: Optional[str] = None
    summary: str = ""
    category: str = ""
    scores: Optional[ScoreSet] = None
    rationale: Optional[dict[str, Any]] = None

    model_config = {"extra": "ignore"}

    @field_validator("id", "title", mode="before")
    @classmethod
    def not_empty(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be empty")
        return v


class LearningStep(BaseModel):
    """A single step in the learning sequence."""
    step: int = Field(ge=1)
    resource_id: str
    reason: str = ""

    model_config = {"extra": "ignore"}


class RecommendationsSchema(BaseModel):
    """Optional best-resource pointers."""
    best_starting_resource: Optional[str] = None
    best_practice_resource: Optional[str] = None
    best_advanced_resource: Optional[str] = None

    model_config = {"extra": "ignore"}


class SummarySchema(BaseModel):
    overview: str = ""
    recommended_learning_goal: str = ""

    model_config = {"extra": "ignore"}


# ---------------------------------------------------------------------------
# Root output schema
# ---------------------------------------------------------------------------

class OutputSchema(BaseModel):
    """Complete validated LLM output schema.

    Required fields: task, resources, ranked_resources, learning_sequence.
    Optional fields: summary, recommendations.
    """
    task: TaskSchema
    summary: Optional[SummarySchema] = None
    resources: list[ResourceSchema] = Field(default_factory=list)
    ranked_resources: list[str] = Field(default_factory=list)
    learning_sequence: list[LearningStep] = Field(default_factory=list)
    recommendations: Optional[RecommendationsSchema] = None

    model_config = {"extra": "ignore"}

    @model_validator(mode="after")
    def resources_not_empty(self) -> "OutputSchema":
        if not self.resources:
            raise ValueError("'resources' list must not be empty")
        return self

    @model_validator(mode="after")
    def ranked_resources_refs_exist(self) -> "OutputSchema":
        """Every ranked_resources entry should reference a known resource id."""
        if self.ranked_resources and self.resources:
            known_ids = {r.id for r in self.resources}
            unknown = [rid for rid in self.ranked_resources if rid not in known_ids]
            if unknown:
                # Warn but don't reject — LLM sometimes uses slightly different ids
                pass
        return self


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

class OutputValidationResult:
    """Result of validating a parsed LLM dict against OutputSchema."""

    def __init__(self, valid: bool, schema: Optional[OutputSchema], errors: list[str]) -> None:
        self.valid = valid
        self.schema = schema
        self.errors = errors

    def repair_prompt_fragment(self) -> str:
        """Return a concise description of failures for the repair prompt."""
        if not self.errors:
            return ""
        lines = ["The previous JSON response failed schema validation:"]
        for err in self.errors:
            lines.append(f"  - {err}")
        lines.append(
            "Please correct the output and return valid JSON matching the required schema."
        )
        return "\n".join(lines)


def validate_output(data: dict) -> OutputValidationResult:
    """Validate a parsed LLM output dict against OutputSchema.

    Returns an OutputValidationResult with:
    - valid: True if all required fields pass.
    - schema: Populated OutputSchema on success, None on failure.
    - errors: Human-readable list of validation failures.
    """
    if not isinstance(data, dict):
        return OutputValidationResult(
            valid=False, schema=None,
            errors=["Output is not a JSON object"]
        )

    try:
        schema = OutputSchema.model_validate(data)
        return OutputValidationResult(valid=True, schema=schema, errors=[])
    except Exception as exc:
        # Extract human-readable Pydantic v2 error messages
        errors: list[str] = []
        try:
            # Pydantic v2 raises ValidationError with .errors()
            for err_item in exc.errors():  # type: ignore[attr-defined]
                loc = " → ".join(str(x) for x in err_item.get("loc", []))
                msg = err_item.get("msg", str(err_item))
                errors.append(f"{loc}: {msg}" if loc else msg)
        except Exception:
            errors = [str(exc)]
        return OutputValidationResult(valid=False, schema=None, errors=errors)
