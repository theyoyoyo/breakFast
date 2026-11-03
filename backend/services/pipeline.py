"""
3-step suggestion pipeline: draft → revise → present.

Orchestrates the Suggestion and Pipeline Analyst personas to produce
a higher-quality meal suggestion. The user sees progress updates while
waiting, then the final meal.

Steps:
1. Suggestion persona drafts a menu (collected internally, not shown).
2. Plain code checks the draft's meal (fridge, units, avoid list), and the
   Pipeline Analyst returns the fixed meal itself through structured outputs
   (revision_schema): its changes first, then the meal. If code finds more
   problems in the revised meal than in the draft, or can't read it, the
   draft's meal is used: avoid-list hits first, then fridge misses and units.
3. Suggestion persona writes the short reply text from the final meal alone,
   so the text never promises what the menu doesn't have. If that call fails,
   code writes the text from the menu name and description.
The reply keeps its shape: the text, then the meal in a ```json block.
"""

import json
import logging
import re
from typing import AsyncGenerator

from models.units import unknown_units, units_for
from services.fridge import find_avoided, find_missing_ingredients, same_name
from services.llm import chat_json
from services.suggestion import (
    build_suggestion_prompt,
    build_pipeline_analyst_prompt,
    build_present_prompt,
    stream_response,
)
from utils import extract_json_block, repair_json_block

# The reviser applies its changes and checks the result, so it runs cool like the old analyst
REVISE_TEMPERATURE = 0.3

# A fenced block in the present step's text; the reply's only ```json block is the meal
_FENCED_RE = re.compile(r"```[\s\S]*?(```|$)")


def revision_schema(language: str) -> dict:
    """The reviser's reply: its changes first, then the meal. Each menu item lists its ingredients
    before its name, so a dish's name is written after what goes in, and every item has a numeric
    amount in the app's units (a dish's servings, which code drops; a simple item's portion). One
    item shape for both: offered a choice of shapes, the 7B model dropped a dish's ingredients."""
    units = units_for(language)
    ingredient = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "amount": {"type": "number"},
            "unit": {"type": "string", "enum": units},
            "prep": {"type": "string"},
        },
        "required": ["name", "amount", "unit"],
    }
    item = {
        "type": "object",
        "properties": {
            "ingredients": {"type": "array", "items": ingredient},
            "name": {"type": "string"},
            "method": {"type": "string"},
            "amount": {"type": "number"},
            "unit": {"type": "string", "enum": units},
        },
        "required": ["ingredients", "name", "method", "amount", "unit"],
    }
    meal = {
        "type": "object",
        "properties": {
            "menu": {"type": "array", "items": item},
            "menu_name": {"type": "string"},
            "description": {"type": "string"},
            "prep_time_min": {"type": "integer"},
        },
        "required": ["menu", "menu_name", "description", "prep_time_min"],
    }
    return {
        "type": "object",
        "properties": {"changes": {"type": "array", "items": {"type": "string"}}, "meal": meal},
        "required": ["changes", "meal"],
    }


def _readable_meal(meal) -> dict | None:
    return meal if isinstance(meal, dict) and isinstance(meal.get("menu"), list) and meal["menu"] else None


def _meal_problems(meal: dict | None, context: dict) -> tuple[float, float]:
    """Code-checked problems in a meal, compared in order: avoid-list hits (a hard ban,
    so one outweighs any number of the rest), then fridge misses and units the app can't show.
    No meal counts as the worst."""
    if meal is None:
        return float("inf"), float("inf")
    avoided = find_avoided(meal, context["avoid_list"])
    missing = find_missing_ingredients(meal, context["ingredients"])
    return len(avoided), len(missing) + len(unknown_units(meal, context.get("language", "en")))


def _code_check(meal: dict, context: dict) -> list[str]:
    """What code found in the draft's meal, one line per kind, for the reviser to fix."""
    checks = [
        ("Not in the fridge", find_missing_ingredients(meal, context["ingredients"])),
        ("On the avoid list", find_avoided(meal, context["avoid_list"])),
        ("Units the app can't show", unknown_units(meal, context.get("language", "en"))),
    ]
    return [f"{label}: {', '.join(names)}" for label, names in checks if names]


def _clean_meal(meal: dict) -> dict:
    """The reviser's meal in the app's format: a dish has no amount or unit of its own, a simple
    item no method, and empty prep words or methods are left out. A "dish" that is one item named
    as itself (Banana: Banana) is that item served as it is, so it becomes a simple item."""
    for item in meal["menu"]:
        if not isinstance(item, dict):
            continue
        sub = item.get("ingredients") or []
        if len(sub) == 1 and isinstance(sub[0], dict) and same_name(str(sub[0].get("name", "")), str(item.get("name", ""))):
            item.update(amount=sub[0].get("amount"), unit=sub[0].get("unit"), ingredients=[])
        if item.get("ingredients"):
            item.pop("amount", None)
            item.pop("unit", None)
        else:
            item["ingredients"] = []
            item.pop("method", None)
        if not str(item.get("method") or "").strip():
            item.pop("method", None)
        for ingredient in item["ingredients"]:
            if isinstance(ingredient, dict) and not str(ingredient.get("prep") or "").strip():
                ingredient.pop("prep", None)
    return meal


def _parse_revision(reply: str) -> tuple[list[str], dict | None]:
    """The reviser's changes and its meal (None when the meal can't be read)."""
    try:
        data = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return [], None
    if not isinstance(data, dict):
        return [], None
    changes = [str(c).strip() for c in data.get("changes") or [] if str(c).strip()]
    meal = _readable_meal(data.get("meal"))
    return changes, _clean_meal(meal) if meal else None


def _revision_message(draft_text: str, draft_meal: dict | None, problems: list[str]) -> str:
    if draft_meal is None:
        draft = f"Draft (its meal block couldn't be read, so build the meal from it):\n{draft_text}"
    else:
        draft = f"Draft menu:\n```json\n{json.dumps(draft_meal, ensure_ascii=False, indent=2)}\n```"
    check = "\n".join(f"- {p}" for p in problems) if problems else "- Nothing found."
    return f"{draft}\n\nCode check:\n{check}"


def _code_text(meal: dict) -> str:
    """The reply text when the present step fails: the menu name and description."""
    name, description = str(meal.get("menu_name") or "").strip(), str(meal.get("description") or "").strip()
    return "\n\n".join(part for part in (f"**{name}**" if name else "", description) if part)


async def run_suggestion_pipeline(
    context: dict,
    user_message: str,
    mode: str | None = None,
    temperature: float | None = None,
    chat_context: list[str] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Run the 3-step suggestion pipeline, yielding events for the WebSocket handler.

    Yields dicts with:
      {"type": "progress", "step": "drafting"|"analyzing"|"finalizing"}
      {"type": "draft", "content": "..."}   — the full draft (for the prompt test; chat ignores it)
      {"type": "review", "content": "..."}  — the code check and the reviser's changes (same)
      {"type": "token", "content": "..."}   — the final text, sent once the meal is chosen
      {"type": "done", "content": "..."}    — full final response

    context: the full context dict from _load_context() in chat.py
    """

    # --- Build prompts ---
    language = context.get("language", "en")

    suggestion_prompt = build_suggestion_prompt(
        ingredient_inventory=context["ingredients"],
        recent_meal_history=context["history"],
        user_preferences=context["preferences"],
        stated_habits=context["stated_habits"],
        inferred_habits=context["inferred_habits"],
        health_rules=context["health_rules"],
        user_profile=context["user_profile"],
        supplements=context["supplements"],
        avoid_list=context["avoid_list"],
        mode=mode,
        kitchen_appliances=context.get("kitchen_appliances"),
        weekly_summary=context.get("weekly_summary"),
        language=language,
        country=context.get("country"),
        favorite_meals=context.get("favorite_meals"),
        favorites=context.get("favorites"),
        ratings=context.get("ratings"),
    )

    reviser_prompt = build_pipeline_analyst_prompt(
        recent_meal_history=context["history"],
        user_profile=context["user_profile"],
        supplements=context["supplements"],
        health_rules=context["health_rules"],
        ingredient_inventory=context["ingredients"],
        avoid_list=context["avoid_list"],
        preferences=context["preferences"],
        mode=mode,
        language=language,
    )

    # Enrich user_message with recent chat context when provided
    if chat_context:
        recent_lines = "\n".join(f"- {m}" for m in chat_context)
        user_message = (
            f"{user_message}\n\n"
            f"User's recent chat messages "
            f"(treat as breakfast preference/feedback if relevant):\n"
            f"{recent_lines}"
        )

    # --- Step 1: Draft ---
    yield {"type": "progress", "step": "drafting"}

    draft_chunks = []
    async for chunk in stream_response(suggestion_prompt, [], user_message, temperature=temperature):
        draft_chunks.append(chunk)
    draft_text = "".join(draft_chunks)
    yield {"type": "draft", "content": draft_text}

    # A draft with no meal block at all is a note to the user (the fridge is too small): send it as is
    draft_meal = _readable_meal(extract_json_block(draft_text))
    if draft_meal is None and "```json" not in draft_text:
        yield {"type": "progress", "step": "analyzing"}
        yield {"type": "review", "content": "- No meal in the draft, so nothing to revise."}
        yield {"type": "progress", "step": "finalizing"}
        final_text = repair_json_block(draft_text)
        yield {"type": "token", "content": final_text}
        yield {"type": "done", "content": final_text}
        return

    # --- Step 2: Revise ---
    yield {"type": "progress", "step": "analyzing"}

    problems = _code_check(draft_meal, context) if draft_meal else []
    changes, revised_meal = [], None
    try:
        reply = await chat_json(
            system_prompt=reviser_prompt,
            messages=[{"role": "user", "content": _revision_message(draft_text, draft_meal, problems)}],
            schema=revision_schema(language),
            temperature=REVISE_TEMPERATURE,
        )
        changes, revised_meal = _parse_revision(reply)
        if revised_meal is None:
            logging.warning("Suggestion reviser: could not read the meal in %r", reply)
    except Exception:
        logging.exception("Suggestion reviser failed; the draft's meal is used")
    review = [f"- CODE CHECK: {p}" for p in problems] + [f"- {c}" for c in changes]
    yield {"type": "review", "content": "\n".join(review) or "- No changes."}

    # The review may only improve the meal: when code finds more problems after it, keep the draft's
    if _meal_problems(revised_meal, context) <= _meal_problems(draft_meal, context):
        meal = revised_meal
    else:
        meal = draft_meal

    # --- Step 3: Present ---
    yield {"type": "progress", "step": "finalizing"}

    if meal is None:  # neither the draft nor the reviser gave a meal that can be read
        final_text = repair_json_block(draft_text)
    else:
        meal_json = json.dumps(meal, ensure_ascii=False, indent=2)
        text = ""
        try:
            chunks = []
            present_message = f"Today's menu:\n```json\n{meal_json}\n```"
            async for chunk in stream_response(build_present_prompt(language), [], present_message, temperature=temperature):
                chunks.append(chunk)
            text = _FENCED_RE.sub("", "".join(chunks)).strip()
        except Exception:
            logging.exception("Suggestion present step failed; code writes the text")
        final_text = f"{text or _code_text(meal)}\n\n```json\n{meal_json}\n```"

    yield {"type": "token", "content": final_text}
    yield {"type": "done", "content": final_text}
