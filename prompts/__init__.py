"""Prompt templates for the ISML Academic Resource Intelligence Agent."""

from .system_prompt import SYSTEM_PROMPT_TEMPLATE
from .task_prompt import TASK_PROMPT_TEMPLATE
from .output_schema import OUTPUT_JSON_TEMPLATE

__all__ = ["SYSTEM_PROMPT_TEMPLATE", "TASK_PROMPT_TEMPLATE", "OUTPUT_JSON_TEMPLATE"]
