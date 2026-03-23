"""
/analyst endpoint — nutrition analysis for a specific meal.

Runs the analyst persona (low temperature, structured JSON output).
This is a REST endpoint, not WebSocket — the analysis is a one-shot call
and the user can wait 15-30 seconds for accurate results.

Supports nutrition caching: if meal_id is provided and analysis succeeds,
the result is saved to meal_history.cached_nutrition. On subsequent requests
for the same meal_id, the cached result is returned without calling the LLM.
"""

import asyncio
import json
from datetime import date as date_type
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Union

from auth import require_user
from database import get_db
from services.suggestion import build_analyst_prompt, stream_response
from services.llm import LLMUnavailableError, lyric_cycler
from services.knowledge import format_ingredient_item
from utils import extract_json_block

router = APIRouter(prefix="/analyst", tags=["analyst"])


class AnalyzeRequest(BaseModel):
    meal_name: str
    ingredients: list[Union[dict, str]]
    meal_id: int | None = None


class AnalyzeResponse(BaseModel):
    analysis_text: str
    analysis_data: dict | None = None
    cached: bool = False


async def _load_analyst_context(db, user_id: int) -> dict:
    """Load context needed for the analyst persona (lighter than full suggestion context)."""

    async def fetch_history():
        async with db.execute(
            "SELECT meal_name, ingredients FROM meal_history WHERE user_id = ? ORDER BY logged_at DESC LIMIT 15",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def fetch_profile():
        async with db.execute(
            "SELECT age, gender, height_cm, weight_kg, activity_level FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def fetch_supplements():
        today = date_type.today().isoformat()
        async with db.execute(
            """
            SELECT s.name, s.contents, s.frequency, COALESCE(l.taken, 0) AS taken_today
            FROM user_supplements s
            LEFT JOIN supplement_daily_log l
                ON l.supplement_id = s.id AND l.user_id = s.user_id AND l.date = ?
            WHERE s.user_id = ?
            ORDER BY s.name
            """,
            (today, user_id),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def fetch_health_rules():
        async with db.execute(
            "SELECT rule_text, priority FROM health_rules WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ) as cur:
            return [{"rule_text": r["rule_text"], "priority": r["priority"]} for r in await cur.fetchall()]

    history, profile, supplements, health_rules = await asyncio.gather(
        fetch_history(), fetch_profile(), fetch_supplements(), fetch_health_rules(),
    )

    return {
        "history": history,
        "user_profile": profile,
        "supplements": supplements,
        "health_rules": health_rules,
    }


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_meal(body: AnalyzeRequest, user_id: int = Depends(require_user)):
    """Run the analyst persona on a meal and return structured nutrition analysis."""

    # Check cache if meal_id is provided
    if body.meal_id is not None:
        async with get_db() as db:
            async with db.execute(
                "SELECT cached_nutrition FROM meal_history WHERE id = ? AND user_id = ?",
                (body.meal_id, user_id),
            ) as cur:
                row = await cur.fetchone()
            if row and row["cached_nutrition"]:
                cached = json.loads(row["cached_nutrition"])
                return AnalyzeResponse(
                    analysis_text=cached.get("analysis_text", ""),
                    analysis_data=cached.get("analysis_data"),
                    cached=True,
                )

    async with get_db() as db:
        ctx = await _load_analyst_context(db, user_id)

    system_prompt = build_analyst_prompt(
        recent_meal_history=ctx["history"],
        user_profile=ctx["user_profile"],
        supplements=ctx["supplements"],
        health_rules=ctx["health_rules"],
    )

    # Format ingredients — handles both string and structured forms
    if body.ingredients:
        ingredients_str = ", ".join(format_ingredient_item(i) for i in body.ingredients)
    else:
        ingredients_str = "malzeme listesi yok"
    user_message = f"Analiz et: {body.meal_name}\nMalzemeler: {ingredients_str}"

    # Non-streaming collection with low temperature for accuracy
    full_response = []
    try:
        async for chunk in stream_response(system_prompt, [], user_message, temperature=0.3):
            full_response.append(chunk)
    except LLMUnavailableError:
        return AnalyzeResponse(
            analysis_text=lyric_cycler.next(),
            analysis_data=None,
        )

    response_text = "".join(full_response)

    # Try to extract the structured JSON from the response
    analysis_data = extract_json_block(response_text)

    # Cache the result if meal_id was provided
    if body.meal_id is not None:
        cache_payload = json.dumps({
            "analysis_text": response_text,
            "analysis_data": analysis_data,
        }, ensure_ascii=False)
        async with get_db() as db:
            await db.execute(
                "UPDATE meal_history SET cached_nutrition = ? WHERE id = ? AND user_id = ?",
                (cache_payload, body.meal_id, user_id),
            )
            await db.commit()

    return AnalyzeResponse(
        analysis_text=response_text,
        analysis_data=analysis_data,
    )
