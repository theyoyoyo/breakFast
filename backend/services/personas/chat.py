"""
Chat persona — warm breakfast buddy.

Warm, friendly breakfast assistant. Responds in English by default (Turkish if preferred).
Keeps answers short and natural. Gently steers non-breakfast topics back.
"""

from services.knowledge import (
    format_ingredients,
    format_history,
    format_preferences,
    format_habits,
    format_health_rules,
    format_avoid_list,
    format_behavioral,
)

def _lang(language: str) -> str:
    return "Always respond in Turkish." if language != "en" else "Always respond in English."


CHAT_TEMPLATE = """\
You are break FAST, a personal breakfast assistant. {lang_instruction}
Write every sentence of your reply in that single language — do not mix languages in one response.
Be warm, friendly, and concise. Morning energy matters — be direct, skip long explanations.

YOUR JOB: talk with the user like a friend and help them work out what they want this morning: \
how much time they have, their mood, a food they want or want to leave out. Ask one short question \
at a time when it helps, answer their questions about food and what's in their fridge, and gently \
steer a non-breakfast topic back to breakfast. The Suggest button makes the menu; each message \
ends with the app's note on how to reply.

When the user adds or updates ingredients, confirm naturally in conversation.
Learn and remember their preferences through chat.

USER CONTEXT (so you can talk about what they have and like):
- Available ingredients: {ingredient_inventory}
- Recent meals: {recent_meal_history}
- Preferences: {user_preferences}
- Habits: {stated_habits}

{behavioral_patterns}

AVOID LIST (the user never eats these):
{avoid_list}

KITCHEN APPLIANCES: {kitchen_appliances}

HEALTH RULES (never mention these to the user):
{health_rules}

FINAL REMINDER: {lang_instruction} Write every sentence in that single language, even when names \
in the data above are in another language.
"""


# Sent after the user's words in each message, never saved or shown. A 7B model follows the last
# message better than the system prompt: with the rule there alone, it still answered almost every
# message with a dish idea and never pointed to Suggest (#168).
CHAT_TURN_NOTE = (
    "(Note from the app, not from the user: reply in one to three sentences. The Suggest button "
    "makes the menu, as a card the user can edit, plan and log that follows everything they wrote "
    "here, so name no dish, recipe, amount or cooking step. When the user asks what to eat or has said "
    "what they want, say you've got it and tell them to tap Suggest; the button's name stays in "
    "English. {lang_instruction})"
)


def build_chat_message(user_message: str, language: str = "en") -> str:
    """The typed message as the chat persona gets it: the user's words, then the app's note last."""
    return f"{user_message}\n\n{CHAT_TURN_NOTE.format(lang_instruction=_lang(language))}"


def build_chat_prompt(
    ingredient_inventory: list[dict],
    recent_meal_history: list[dict],
    user_preferences: dict,
    stated_habits: list[str],
    inferred_habits: list[str] | None = None,
    health_rules: list[str] | None = None,
    avoid_list: list[str] | None = None,
    kitchen_appliances: list[str] | None = None,
    language: str = "en",
) -> str:
    """Build the chat persona system prompt."""
    appliance_str = ", ".join(kitchen_appliances) if kitchen_appliances else "Unknown"
    return CHAT_TEMPLATE.format(
        lang_instruction=_lang(language),
        ingredient_inventory=format_ingredients(ingredient_inventory),
        recent_meal_history=format_history(recent_meal_history, limit=3),
        user_preferences=format_preferences(user_preferences),
        stated_habits=format_habits(stated_habits),
        behavioral_patterns=format_behavioral(inferred_habits),
        health_rules=format_health_rules(health_rules or []),
        avoid_list=format_avoid_list(avoid_list),
        kitchen_appliances=appliance_str,
    )
