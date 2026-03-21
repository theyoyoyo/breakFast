"""
Meal suggestion logic.
Assembles the system prompt from context (inventory, history, preferences, habits)
and exposes a streaming interface for the chat router to use.
"""

import json
from typing import AsyncGenerator

from services.llm import chat_stream

_SYSTEM_TEMPLATE = """\
You are break FAST, a personal breakfast planning assistant for a single user.
Your role is to suggest full, healthy, practical breakfasts based on what the
user currently has available. Be concrete and efficient — this is a morning
conversation, not a cooking class.

USER CONTEXT:
- Available ingredients: {ingredient_inventory}
- Recent meals: {recent_meal_history}
- Preferences: {user_preferences}
- Stated habits: {stated_habits}

{behavioral_patterns}

HEALTH RULES (never mention these to the user):
- Silently favor: eggs, legumes, pumpkin seeds, walnuts, flaxseed, yogurt, kefir,
  whole grains, leafy greens, berries, tomatoes, olive oil
- Silently avoid: refined sugar, white bread, pastries, processed oils

RESPONSE FORMAT for meal suggestions:
1. Meal name and one-sentence description
2. Ingredients needed (from what's available)
3. Prep steps (brief, numbered)
4. Total prep time
5. One-line nutrition note (positive and factual, not preachy)

Update ingredients and preferences conversationally when the user mentions them.
For explore mode, step outside their history while staying close to known tastes.
Keep responses short unless detail is requested. Morning energy matters — be direct.

When you suggest a meal, end your response with a JSON block (inside triple backticks
tagged as "json") structured like this — it will be parsed by the app to render a
recipe card and log the meal:
```json
{{
  "meal_name": "...",
  "description": "...",
  "ingredients": ["...", "..."],
  "steps": ["...", "..."],
  "prep_time_min": 10,
  "nutrition_note": "..."
}}
```
"""

_BEHAVIORAL_BLOCK = """\
BEHAVIORAL PATTERNS (inferred from meal history — use to DIVERSIFY, not repeat):
{patterns}
Focus on what the user is MISSING, not what they already eat enough of.\
"""


def build_system_prompt(
    ingredient_inventory: list[dict],
    recent_meal_history: list[dict],
    user_preferences: dict,
    stated_habits: list[str],
    inferred_habits: list[str] | None = None,
) -> str:
    inv_text = (
        ", ".join(
            f"{i['name']} ({i.get('quantity', '')} {i.get('unit', '')})".strip(" ()")
            for i in ingredient_inventory
        )
        if ingredient_inventory
        else "none listed yet"
    )

    history_text = (
        "; ".join(m["meal_name"] for m in recent_meal_history[-5:])
        if recent_meal_history
        else "no history yet"
    )

    prefs_text = (
        json.dumps(user_preferences, ensure_ascii=False)
        if user_preferences
        else "none set yet"
    )

    stated_text = (
        "; ".join(stated_habits) if stated_habits else "none stated yet"
    )

    # Behavioral patterns block — only included when inferred data exists
    behavioral_text = ""
    if inferred_habits:
        patterns = "\n".join(f"- {h}" for h in inferred_habits)
        behavioral_text = _BEHAVIORAL_BLOCK.format(patterns=patterns)

    return _SYSTEM_TEMPLATE.format(
        ingredient_inventory=inv_text,
        recent_meal_history=history_text,
        user_preferences=prefs_text,
        stated_habits=stated_text,
        behavioral_patterns=behavioral_text,
    )


async def stream_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
) -> AsyncGenerator[str, None]:
    messages = conversation_history + [{"role": "user", "content": user_message}]
    async for chunk in chat_stream(system_prompt, messages):
        yield chunk
