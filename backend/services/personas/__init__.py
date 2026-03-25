"""
Persona templates and prompt builders.

Each persona lives in its own file for easier editing and better token usage.
The suggestion.py module re-exports everything for backward compatibility.
"""

from services.personas.chat import CHAT_TEMPLATE, build_chat_prompt
from services.personas.dietitian import SUGGESTION_TEMPLATE, MODE_INSTRUCTIONS, build_suggestion_prompt
from services.personas.analyst import ANALYST_TEMPLATE, build_analyst_prompt
from services.personas.pipeline_analyst import PIPELINE_ANALYST_TEMPLATE, build_pipeline_analyst_prompt
from services.personas.shopping import SHOPPING_TEMPLATE, build_shopping_prompt
from services.personas.scheduler import SCHEDULER_TEMPLATE, build_scheduler_prompt, build_scheduler_user_message

__all__ = [
    "CHAT_TEMPLATE",
    "SUGGESTION_TEMPLATE",
    "ANALYST_TEMPLATE",
    "PIPELINE_ANALYST_TEMPLATE",
    "SHOPPING_TEMPLATE",
    "SCHEDULER_TEMPLATE",
    "MODE_INSTRUCTIONS",
    "build_chat_prompt",
    "build_suggestion_prompt",
    "build_analyst_prompt",
    "build_pipeline_analyst_prompt",
    "build_shopping_prompt",
    "build_scheduler_prompt",
    "build_scheduler_user_message",
]
