"""
/analyst endpoint — nutrition analysis for a specific meal.

Runs the analyst persona (low temperature, structured JSON output).
This is a REST endpoint, not WebSocket — the analysis is a one-shot call
and the user can wait 15-30 seconds for accurate results.
"""

import asyncio
import json
from datetime import date as date_type
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import require_user
from database import get_db
from services.suggestion import build_analyst_prompt, stream_response
from services.llm import LLMUnavailableError
from utils import extract_json_block

router = APIRouter(prefix="/analyst", tags=["analyst"])


class AnalyzeRequest(BaseModel):
    meal_name: str
    ingredients: list[str]


class AnalyzeResponse(BaseModel):
    analysis_text: str
    analysis_data: dict | None = None


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
    async with get_db() as db:
        ctx = await _load_analyst_context(db, user_id)

    system_prompt = build_analyst_prompt(
        recent_meal_history=ctx["history"],
        user_profile=ctx["user_profile"],
        supplements=ctx["supplements"],
        health_rules=ctx["health_rules"],
    )

    # Build the user message — the meal to analyze
    ingredients_str = ", ".join(body.ingredients) if body.ingredients else "malzeme listesi yok"
    user_message = f"Analiz et: {body.meal_name}\nMalzemeler: {ingredients_str}"

    # Non-streaming collection with low temperature for accuracy
    full_response = []
    try:
        async for chunk in stream_response(system_prompt, [], user_message, temperature=0.3):
            full_response.append(chunk)
    except LLMUnavailableError:
        return AnalyzeResponse(
            analysis_text="LLM servisi şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin.",
            analysis_data=None,
        )

    response_text = "".join(full_response)

    # Try to extract the structured JSON from the response
    analysis_data = extract_json_block(response_text)

    return AnalyzeResponse(
        analysis_text=response_text,
        analysis_data=analysis_data,
    )
