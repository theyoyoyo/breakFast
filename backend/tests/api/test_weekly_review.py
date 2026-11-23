"""The weekly analysis (#206): its structured reply, how analyses are kept, the refusal for a week
without meals, and the nudge to run one. The weekly analyst's model is faked."""

import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest

import database
from models.nutrients import NUTRIENTS
from services.llm import LLMUnavailableError
from services.weekly import WEEKLY_SCHEMA

MEAL = {"meal_name": "Oats", "ingredients": [], "menu_items": [{"name": "Oats", "amount": 50, "unit": "g", "ingredients": []}]}

REPLY = {
    "narrative": "A sweet week.",
    "scores": [
        {"label": "Nutritional Balance", "score": 60, "note": "Low on fiber."},
        {"label": "Variety", "score": 70, "note": "Some repeats."},
    ],
    "lacking": ["fiber", "protein"],
    "more_than_enough": ["sugar"],
}


def fake_analyst(reply=REPLY):
    """A stand-in for the weekly analyst's structured call; `calls` keeps each call's arguments by name."""
    calls = []

    async def chat_json(system_prompt, messages, schema, temperature=None, **route):
        calls.append({"system_prompt": system_prompt, "messages": messages, "schema": schema, **route})
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)

    return chat_json, calls


async def _user_id(db, name="testuser") -> int:
    async with db.execute("SELECT id FROM users WHERE name = ?", (name,)) as cur:
        return (await cur.fetchone())["id"]


async def _analysis(db, user_id, days_ago: int, narrative="Earlier", lacking=None, more=None):
    """An analysis run `days_ago` days ago, covering the 7 days up to then."""
    ran = date.today() - timedelta(days=days_ago)
    await db.execute(
        """
        INSERT INTO weekly_summaries
            (user_id, week_key, narrative, scores, created_at, period_start, period_end, lacking, more_than_enough)
        VALUES (?, 'old', ?, '[]', datetime('now', ?), ?, ?, ?, ?)
        """,
        (
            user_id, narrative, f"-{days_ago} days",
            (ran - timedelta(days=6)).isoformat(), ran.isoformat(),
            json.dumps(lacking or []), json.dumps(more or []),
        ),
    )
    await db.commit()


async def _narratives(db, user_id) -> list[str]:
    async with db.execute(
        "SELECT narrative FROM weekly_summaries WHERE user_id = ? ORDER BY created_at", (user_id,)
    ) as cur:
        return [r["narrative"] for r in await cur.fetchall()]


async def _run(client, reply=REPLY):
    chat_json, calls = fake_analyst(reply)
    with patch("routers.meals.chat_json", chat_json):
        r = await client.post("/meals/weekly-review")
    return r, calls


# ---------------------------------------------------------------------------
# The reply
# ---------------------------------------------------------------------------

# The schema limits both nutrient lists to the nutrients in code, so the reply can't name a food there
def test_schema_limits_nutrients_to_the_list():
    for field in ("lacking", "more_than_enough"):
        assert WEEKLY_SCHEMA["properties"][field]["items"]["enum"] == list(NUTRIENTS)
    assert set(WEEKLY_SCHEMA["required"]) == {"narrative", "scores", "lacking", "more_than_enough"}


# The analysis keeps only listed nutrients, each once and most important first, and drops one marked both ways
async def test_reply_nutrients_are_limited_to_the_list(client, db):
    await client.post("/meals/", json=MEAL)
    reply = {
        **REPLY,
        "lacking": ["vitamin C", "Salmon", "fiber", "fiber", "salt"],
        "more_than_enough": ["salt", "sugar", "bread"],
    }
    r, calls = await _run(client, reply)
    assert r.status_code == 200
    assert calls[0]["schema"] == WEEKLY_SCHEMA and calls[0]["task"] == "weekly"
    async with db.execute("SELECT lacking, more_than_enough FROM weekly_summaries") as cur:
        row = await cur.fetchone()
    assert json.loads(row["lacking"]) == ["fiber", "vitamin C"]
    assert json.loads(row["more_than_enough"]) == ["sugar"]


# The review screen gets the narrative and scores; the nutrient lists stay on the server
async def test_reply_shows_narrative_and_scores_only(client):
    await client.post("/meals/", json=MEAL)
    r, _ = await _run(client)
    data = r.json()
    assert data["narrative"] == REPLY["narrative"] and data["scores"] == REPLY["scores"]
    assert "lacking" not in data and "more_than_enough" not in data
    shown = await client.get("/meals/weekly-review")
    assert shown.status_code == 200 and shown.json()["narrative"] == REPLY["narrative"]


# A reply that can't be read keeps nothing and gets a fixed message, not the model's words
async def test_unreadable_reply_keeps_nothing(client, db):
    await client.post("/meals/", json=MEAL)
    r, _ = await _run(client, "not json {")
    assert r.status_code == 500 and "not json" not in r.text
    assert await _narratives(db, await _user_id(db)) == []


# While Ollama is unreachable the user gets a lyric and nothing is kept
async def test_unreachable_model_keeps_nothing(client, db):
    await client.post("/meals/", json=MEAL)
    r, _ = await _run(client, LLMUnavailableError("down"))
    assert r.status_code == 200 and r.json()["scores"] == []
    assert await _narratives(db, await _user_id(db)) == []


# ---------------------------------------------------------------------------
# Keeping analyses
# ---------------------------------------------------------------------------

# A new analysis replaces one whose 7 days overlap its own and keeps one whose days don't
async def test_new_analysis_replaces_overlapping_keeps_others(client, db):
    user_id = await _user_id(db)
    await _analysis(db, user_id, days_ago=10, narrative="Two weeks ago")
    await _analysis(db, user_id, days_ago=3, narrative="This week")
    await client.post("/meals/", json=MEAL)
    await _run(client)
    assert await _narratives(db, user_id) == ["Two weeks ago", REPLY["narrative"]]


# Analyses older than six months are deleted, at a new analysis and at the server's start
async def test_analyses_older_than_six_months_are_deleted(client, db):
    user_id = await _user_id(db)
    await _analysis(db, user_id, days_ago=200, narrative="Long ago")
    await _analysis(db, user_id, days_ago=100, narrative="Spring")
    await client.post("/meals/", json=MEAL)
    await _run(client)
    assert await _narratives(db, user_id) == ["Spring", REPLY["narrative"]]

    await _analysis(db, user_id, days_ago=190, narrative="Long ago again")
    await database.init_db()
    assert await _narratives(db, user_id) == ["Spring", REPLY["narrative"]]


# Another user's analyses are neither shown nor replaced by this user's
async def test_analyses_stay_with_their_user(client, db):
    await db.execute("INSERT INTO users (name, pin_hash) VALUES ('other', 'x')")
    await db.commit()
    other = await _user_id(db, "other")
    await _analysis(db, other, days_ago=1, narrative="Zed's week")
    assert (await client.get("/meals/weekly-review")).status_code == 404

    await client.post("/meals/", json=MEAL)
    await _run(client)
    assert await _narratives(db, other) == ["Zed's week"]
    assert "Zed" not in (await client.get("/meals/weekly-review")).text


# ---------------------------------------------------------------------------
# No meals, no analysis
# ---------------------------------------------------------------------------

# Without a meal logged in the last 7 days the analysis is refused and the model isn't asked
async def test_no_meals_in_seven_days_gives_no_analysis(client, db):
    await client.post("/meals/", json=MEAL)
    await db.execute("UPDATE meal_history SET logged_at = datetime('now', '-9 days')")
    await db.commit()
    r, calls = await _run(client)
    assert r.status_code == 422
    assert calls == []
    assert await _narratives(db, await _user_id(db)) == []


# ---------------------------------------------------------------------------
# The nudge
# ---------------------------------------------------------------------------

async def _nudge(client) -> bool:
    r = await client.get("/meals/weekly-review/status")
    assert r.status_code == 200
    return r.json()["nudge"]


# The nudge shows for a new meal, clears when the analysis runs and shows again when a meal of the week changes
async def test_nudge_shows_and_clears(client, db):
    assert await _nudge(client) is False  # nothing to analyze
    meal = (await client.post("/meals/", json=MEAL)).json()
    assert await _nudge(client) is True

    await _run(client)
    assert await _nudge(client) is False

    # An edit after the analysis (made a second later, so the times differ)
    await db.execute("UPDATE weekly_summaries SET created_at = datetime('now', '-1 minute')")
    await db.commit()
    await client.put(f"/meals/{meal['id']}", json={**MEAL, "meal_name": "Oats with honey"})
    assert await _nudge(client) is True


# A meal older than the analysis's 7 days doesn't nudge, even with no analysis yet
async def test_old_meal_does_not_nudge(client, db):
    await client.post("/meals/", json=MEAL)
    await db.execute("UPDATE meal_history SET logged_at = datetime('now', '-9 days')")
    await db.commit()
    assert await _nudge(client) is False


# A meal logged before the latest analysis doesn't nudge, whenever in the week it was logged
@pytest.mark.parametrize("days_ago", [0, 6])
async def test_meal_before_analysis_does_not_nudge(client, db, days_ago):
    await client.post("/meals/", json=MEAL)
    await db.execute("UPDATE meal_history SET logged_at = datetime('now', ?)", (f"-{days_ago} days", ))
    await db.commit()
    await _analysis(db, await _user_id(db), days_ago=0, narrative="Today")
    await db.execute("UPDATE weekly_summaries SET created_at = datetime('now', '+1 minute')")
    await db.commit()
    assert await _nudge(client) is False
