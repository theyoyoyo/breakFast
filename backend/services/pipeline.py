"""
3-step suggestion pipeline: draft → analyze → refine.

Orchestrates the Suggestion and Pipeline Analyst personas to produce
a higher-quality meal suggestion. The user sees progress updates while
waiting, then the final meal.

Steps:
1. Suggestion persona drafts a meal (collected internally, not streamed to user).
2. Pipeline Analyst reviews the draft (a few changes as a JSON list), and plain
   code lists any draft ingredient that isn't in the fridge.
3. Suggestion persona refines the meal using that feedback. If code finds more
   problems in the refined meal than in the draft, the user gets the draft:
   avoid-list hits first, then fridge misses and unknown units.
"""

from typing import AsyncGenerator

from models.units import unknown_units
from services.fridge import find_avoided, find_missing_ingredients
from services.suggestion import (
    build_suggestion_prompt,
    build_pipeline_analyst_prompt,
    stream_response,
)
from utils import extract_json_block, repair_json_block


def _meal_problems(text: str, context: dict) -> tuple[float, float]:
    """Code-checked problems in a reply's meal, compared in order: avoid-list hits (a hard ban,
    so one outweighs any number of the rest), then fridge misses and units the app can't show.
    A reply without a meal counts as the worst."""
    meal = extract_json_block(text)
    if not isinstance(meal, dict) or not isinstance(meal.get("menu"), list):
        return float("inf"), float("inf")
    avoided = find_avoided(meal, context["avoid_list"])
    missing = find_missing_ingredients(meal, context["ingredients"])
    return len(avoided), len(missing) + len(unknown_units(meal, context.get("language", "en")))


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
      {"type": "review", "content": "..."}  — the feedback the refine step gets (same)
      {"type": "token", "content": "..."}   — the final text, sent once the fallback check is done
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
    )

    analyst_prompt = build_pipeline_analyst_prompt(
        recent_meal_history=context["history"],
        user_profile=context["user_profile"],
        supplements=context["supplements"],
        health_rules=context["health_rules"],
        ingredient_inventory=context["ingredients"],
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

    # --- Step 2: Analyst review ---
    yield {"type": "progress", "step": "analyzing"}

    analyst_message = f"Draft suggestion:\n\n{draft_text}"
    analyst_chunks = []
    async for chunk in stream_response(analyst_prompt, [], analyst_message, temperature=0.3):
        analyst_chunks.append(chunk)
    analyst_text = "".join(analyst_chunks)

    # Extract feedback list from analyst response
    feedback_data = extract_json_block(analyst_text)
    if feedback_data and "feedback" in feedback_data:
        feedback_lines = feedback_data["feedback"]
        feedback_formatted = "\n".join(f"- {line}" for line in feedback_lines)
    else:
        # Analyst didn't produce structured JSON — use raw text
        feedback_formatted = analyst_text

    # The 7B model misses fridge-only violations, so code checks the draft's JSON too
    missing = find_missing_ingredients(extract_json_block(draft_text), context["ingredients"])
    if missing:
        fridge_feedback = (
            "- FRIDGE CHECK (hard rule, fix this first): these ingredients are not in the fridge: "
            f"{', '.join(missing)}. Replace each one with an inventory item, writing its name "
            "exactly as listed, or remove it. Drop a dish only if it can't be made without it."
        )
        feedback_formatted = f"{fridge_feedback}\n{feedback_formatted}"
    yield {"type": "review", "content": feedback_formatted}

    # --- Step 3: Refine ---
    yield {"type": "progress", "step": "finalizing"}

    refinement_message = (
        f"Below is the draft breakfast suggestion you prepared, along with feedback from the "
        f"nutrition analyst. Make the changes the feedback asks for that work with the available "
        f"ingredients, and keep everything else exactly as in the draft (items, names, amounts, "
        f"wording), so the review only improves the meal. Write the result as you would present "
        f"it to the user.\n\n"
        f"═══ DRAFT SUGGESTION ═══\n{draft_text}\n\n"
        f"═══ ANALYST FEEDBACK ═══\n{feedback_formatted}"
    )

    final_chunks = []
    async for chunk in stream_response(suggestion_prompt, [], refinement_message, temperature=temperature):
        final_chunks.append(chunk)
    final_text = "".join(final_chunks)

    # The review may only improve the meal: when code finds more problems after it, keep the draft
    if _meal_problems(final_text, context) > _meal_problems(draft_text, context):
        final_text = draft_text
    final_text = repair_json_block(final_text)

    yield {"type": "token", "content": final_text}
    yield {"type": "done", "content": final_text}
