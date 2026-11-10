"""
Meal suggestion logic — backward-compatible re-export layer.

All persona templates and prompt builders now live in services/personas/.
This module re-exports everything so existing imports continue to work.
"""

from typing import AsyncGenerator

from services.llm import chat_stream

# Re-export all persona builders from the personas package
from services.personas import (
    build_chat_prompt,
    build_suggestion_prompt,
    build_present_prompt,
    build_analyst_prompt,
    build_pipeline_analyst_prompt,
    build_shopping_prompt,
)

# Shared formatters from the knowledge module, importable from here too
from services.knowledge import (
    format_ingredients,
    format_history,
    format_preferences,
    format_habits,
    format_health_rules,
    format_avoid_list,
    format_behavioral,
    format_user_profile,
    format_supplements,
)


async def stream_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    temperature: float | None = None,
) -> AsyncGenerator[str, None]:
    messages = conversation_history + [{"role": "user", "content": user_message}]
    async for chunk in chat_stream(system_prompt, messages, temperature=temperature):
        yield chunk
