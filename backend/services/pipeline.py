"""
3-step suggestion pipeline: draft → analyze → refine.

Orchestrates the Suggestion and Pipeline Analyst personas to produce
a higher-quality meal suggestion. The user sees progress updates while
waiting, then the final refined meal streams normally.

Steps:
1. Suggestion persona drafts a meal (collected internally, not streamed to user).
2. Pipeline Analyst reviews the draft (thorough feedback as JSON list).
3. Suggestion persona refines the meal using analyst feedback (streamed to user).
"""

from typing import AsyncGenerator

from services.suggestion import (
    build_suggestion_prompt,
    build_pipeline_analyst_prompt,
    stream_response,
)
from utils import extract_json_block


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
      {"type": "token", "content": "..."}   — final streamed tokens
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

    # --- Step 3: Refine ---
    yield {"type": "progress", "step": "finalizing"}

    refinement_message = (
        f"Below is the draft breakfast suggestion you prepared, along with detailed feedback "
        f"from the nutrition analyst. Revise and improve the suggestion by addressing every "
        f"feedback point. Write the result as you would present it to the user.\n\n"
        f"═══ DRAFT SUGGESTION ═══\n{draft_text}\n\n"
        f"═══ ANALYST FEEDBACK ═══\n{feedback_formatted}"
    )

    final_chunks = []
    async for chunk in stream_response(suggestion_prompt, [], refinement_message, temperature=temperature):
        final_chunks.append(chunk)
        yield {"type": "token", "content": chunk}

    final_text = "".join(final_chunks)
    yield {"type": "done", "content": final_text}
