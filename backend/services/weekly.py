"""
The weekly analysis (#206): its reply schema and parser, and how analyses are kept.

Each analysis covers the 7 days up to the day it ran. A new one replaces every earlier one whose
days overlap its own and keeps the rest, so there is at most one per week; analyses older than
six months are deleted. The suggestion draft and the reviser read the nutrients of the latest
one when it ran in the last 7 days; the nudge tells the user a new one has something to read.
"""

import json
from datetime import date, timedelta

from models.nutrients import NUTRIENTS, clean_nutrients

WEEK_DAYS = 7
KEEP_FOR = "-6 months"  # SQLite date modifier: analyses older than this are deleted
RECENT = f"-{WEEK_DAYS} days"  # an analysis this new still speaks for the user's breakfasts

_NUTRIENT_LIST = {"type": "array", "items": {"type": "string", "enum": list(NUTRIENTS)}}

# The weekly analyst's reply: its words first, then the scores, then the two nutrient lists,
# each limited to the nutrients in code, so it can never name a food there.
WEEKLY_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative": {"type": "string"},
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "score": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["label", "score", "note"],
            },
        },
        "lacking": _NUTRIENT_LIST,
        "more_than_enough": _NUTRIENT_LIST,
    },
    "required": ["narrative", "scores", "lacking", "more_than_enough"],
}


def analysis_window(today: date) -> tuple[date, date]:
    """The days an analysis run today covers: the 7 days up to today."""
    return today - timedelta(days=WEEK_DAYS - 1), today


def parse_weekly_reply(reply: str) -> dict | None:
    """The analysis in a reply, or None when it can't be read. Scores keep only readable entries,
    and the nutrient lists only listed nutrients, most important first."""
    try:
        data = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("scores"), list):
        return None
    scores = [
        {"label": s["label"], "score": s["score"], "note": s.get("note") if isinstance(s.get("note"), str) else ""}
        for s in data["scores"]
        if isinstance(s, dict) and isinstance(s.get("label"), str)
        and isinstance(s.get("score"), (int, float)) and not isinstance(s.get("score"), bool)
    ]
    lacking, more_than_enough = clean_nutrients(data.get("lacking"), data.get("more_than_enough"))
    narrative = data.get("narrative")
    return {
        "narrative": narrative if isinstance(narrative, str) else "",
        "scores": scores,
        "lacking": lacking,
        "more_than_enough": more_than_enough,
    }


async def delete_old_analyses(db, user_id: int | None = None) -> None:
    """Delete analyses older than six months: one user's, or everyone's at the server start."""
    if user_id is None:
        await db.execute("DELETE FROM weekly_summaries WHERE created_at < datetime('now', ?)", (KEEP_FOR,))
    else:
        await db.execute(
            "DELETE FROM weekly_summaries WHERE user_id = ? AND created_at < datetime('now', ?)",
            (user_id, KEEP_FOR),
        )


async def save_analysis(db, user_id: int, analysis: dict, start: date, end: date, week_key: str) -> None:
    """Keep a new analysis: it replaces the user's analyses whose days overlap its own."""
    await db.execute(
        "DELETE FROM weekly_summaries WHERE user_id = ? AND period_start <= ? AND period_end >= ?",
        (user_id, end.isoformat(), start.isoformat()),
    )
    await delete_old_analyses(db, user_id)
    await db.execute(
        """
        INSERT INTO weekly_summaries
            (user_id, week_key, narrative, scores, period_start, period_end, lacking, more_than_enough)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id, week_key, analysis["narrative"],
            json.dumps(analysis["scores"], ensure_ascii=False),
            start.isoformat(), end.isoformat(),
            json.dumps(analysis["lacking"]), json.dumps(analysis["more_than_enough"]),
        ),
    )


def _names(value) -> list[str]:
    try:
        names = json.loads(value) if value else []
    except (json.JSONDecodeError, TypeError):
        return []
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


async def fetch_recent_analysis(db, user_id: int) -> dict | None:
    """The user's latest analysis when it ran in the last 7 days, else None."""
    async with db.execute(
        """
        SELECT narrative, scores, week_key, period_start, period_end, lacking, more_than_enough
        FROM weekly_summaries
        WHERE user_id = ? AND created_at >= datetime('now', ?)
        ORDER BY created_at DESC, id DESC LIMIT 1
        """,
        (user_id, RECENT),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    lacking, more_than_enough = clean_nutrients(_names(row["lacking"]), _names(row["more_than_enough"]))
    return {
        **dict(row),
        "lacking": lacking,
        "more_than_enough": more_than_enough,
    }


# A meal the analysis would read: logged in the 7 days up to today, like the analysis's own query
MEALS_IN_WINDOW = "user_id = ? AND date(logged_at) >= ? AND date(logged_at) <= ?"


async def needs_analysis(db, user_id: int, today: date) -> bool:
    """True when a meal of the last 7 days was logged or changed after the latest analysis (or
    there is none), so a new analysis has something new to read."""
    start, end = analysis_window(today)
    async with db.execute(
        "SELECT MAX(created_at) AS latest FROM weekly_summaries WHERE user_id = ?", (user_id,)
    ) as cur:
        latest = (await cur.fetchone())["latest"]
    async with db.execute(
        f"""
        SELECT 1 FROM meal_history
        WHERE {MEALS_IN_WINDOW}
          AND (? IS NULL OR MAX(logged_at, COALESCE(updated_at, logged_at)) > ?)
        LIMIT 1
        """,
        (user_id, start.isoformat(), end.isoformat(), latest, latest),
    ) as cur:
        return await cur.fetchone() is not None
