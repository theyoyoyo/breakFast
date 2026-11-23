"""Integration tests for the /scheduler endpoints."""

import json
from unittest.mock import patch

from services.llm import FALLBACK_LYRICS, LLMUnavailableError


def _mock_stream(text):
    """Mock stream_response that yields the whole reply in one chunk."""
    async def stream(*args, **kwargs):
        yield text
    return stream


async def test_plan_no_steps(client):
    """Should return empty timeline when no steps provided."""
    r = await client.post("/scheduler/plan", json={
        "meal_name": "Test Meal",
        "steps": [],
        "ingredients": [],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["timeline"] == []
    assert data["makespan_min"] == 0
    assert data["formatted"] == "No steps found."


MENEMEN_MENU = [
    {"name": "Menemen", "ingredients": [{"name": "Egg", "amount": 2, "unit": "adet"}]},
    {"name": "White cheese", "amount": 50, "unit": "g", "ingredients": []},
]


async def test_plan_from_menu_without_steps(client):
    """A menu-format meal with no steps still gets a plan from the LLM, its units in the reply language,
    and the item it serves as it is stays out of the plan."""
    reply = (
        '```json\n{"dishes": [{"dish": "Menemen", "steps": ['
        '{"action": "Sauté the peppers", "minutes": 4, "hands_on": true, "appliance": "Stove"}, '
        '{"action": "Stir in 2 eggs and cook", "minutes": 6, "hands_on": false, "appliance": "Stove"}]}, '
        '{"dish": "White cheese", "steps": [{"action": "Serve 50 g", "minutes": 0, "hands_on": false}]}]}\n```'
    )
    with patch("routers.scheduler.stream_response", side_effect=_mock_stream(reply)) as llm:
        r = await client.post("/scheduler/plan", json={
            "meal_name": "Classic Breakfast",
            "steps": [],
            "menu": MENEMEN_MENU,
        })
    assert r.status_code == 200
    data = r.json()
    assert data["makespan_min"] == 10
    assert [s["task"] for s in data["timeline"]] == ["Sauté the peppers", "Stir in 2 eggs and cook"]
    assert data["formatted"].startswith("⏱ Plan (10 min)\n  0:00  — Menemen: Sauté the peppers\n")
    user_message = llm.call_args.args[2]
    assert "Menemen: Egg (2 pcs)" in user_message


async def test_plan_keeps_only_the_users_appliances(client):
    """The planner is offered the user's appliances (the stove by default), and a step on another
    appliance keeps its place without one."""
    reply = (
        '```json\n{"dishes": [{"dish": "Toast", "steps": ['
        '{"action": "Toast 2 slices of bread", "minutes": 3, "hands_on": false, "appliance": "Toaster"}]}]}\n```'
    )
    with patch("routers.scheduler.stream_response", side_effect=_mock_stream(reply)) as llm:
        r = await client.post("/scheduler/plan", json={"meal_name": "Toast", "menu": MENEMEN_MENU})
    assert "these exact names (case-sensitive): Stove;" in llm.call_args.args[0]
    assert r.json()["formatted"].splitlines()[1] == "  0:00  — Toast: Toast 2 slices of bread (3 min)"


async def test_plan_in_another_shape_is_unreadable(client):
    """A reply without a dishes list asks the user to try again instead of showing an empty plan."""
    reply = '```json\n{"prep": [{"task": "Slice cheese"}], "timed": []}\n```'
    with patch("routers.scheduler.stream_response", side_effect=_mock_stream(reply)):
        r = await client.post("/scheduler/plan", json={"meal_name": "Classic Breakfast", "menu": MENEMEN_MENU})
    assert r.json()["formatted"] == "Couldn't read the plan. Please try again."


async def test_plan_with_cached_schedule(client, db):
    """A meal's cached plan comes back as stored, older formats included."""
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        row = await cur.fetchone()
        user_id = row[0]

    cached = {
        "timeline": [
            {"start_min": 0, "task": "Yumurtaları haşla", "duration_min": 7,
             "resource": "ocak", "end_action": "Süz ve soğuk suya al"},
        ],
        "makespan_min": 7,
        "formatted": "🔪 Hazırlık\n  • Domates dilimle\n\n⏱ Zamanlama (7 dk)\n  0:00  — Yumurtaları haşla (7 dk)  [ocak]\n  7:00  — Hazır! ✓",
    }
    cur = await db.execute(
        """INSERT INTO meal_history (user_id, meal_name, ingredients, steps, schedule)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, "Cached Meal", "[]", "[]", json.dumps(cached)),
    )
    meal_id = cur.lastrowid
    await db.commit()

    r = await client.post("/scheduler/plan", json={
        "meal_name": "Cached Meal",
        "steps": ["Yumurtaları haşla"],
        "ingredients": [],
        "meal_id": meal_id,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["cached"] is True
    assert data["makespan_min"] == 7
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["task"] == "Yumurtaları haşla"
    assert data["formatted"] == cached["formatted"]


# With Ollama unreachable a plan without a meal_id gets the next lyric and an empty plan
async def test_plan_without_meal_id_llm_down(client):
    async def down(*args, **kwargs):
        raise LLMUnavailableError()
        yield

    with patch("routers.scheduler.stream_response", side_effect=down) as llm:
        r = await client.post("/scheduler/plan", json={
            "meal_name": "Simple Meal",
            "steps": ["Toast bread", "Spread butter"],
            "ingredients": [{"name": "Bread"}, {"name": "Butter"}],
        })
    assert r.status_code == 200
    data = r.json()
    assert llm.call_count == 1
    assert data["formatted"] in FALLBACK_LYRICS
    assert data["timeline"] == [] and data["makespan_min"] == 0 and data["cached"] is False


TOAST_REPLY = (
    '```json\n{"dishes": [{"dish": "Toast", "steps": ['
    '{"action": "Toast 2 slices of bread", "minutes": 3, "hands_on": false, "appliance": "Stove"}]}]}\n```'
)


async def _add_meal(db, user_name, meal_name, schedule=None):
    """Log a meal for a user (created when missing) and return the meal's id."""
    await db.execute("INSERT OR IGNORE INTO users (name, pin_hash) VALUES (?, '')", (user_name,))
    async with db.execute("SELECT id FROM users WHERE name = ?", (user_name,)) as cur:
        user_id = (await cur.fetchone())[0]
    cur = await db.execute(
        "INSERT INTO meal_history (user_id, meal_name, ingredients, steps, schedule) VALUES (?, ?, '[]', '[]', ?)",
        (user_id, meal_name, schedule),
    )
    await db.commit()
    return cur.lastrowid


async def _schedule_of(db, meal_id):
    """The plan stored with a meal, or None."""
    async with db.execute("SELECT schedule FROM meal_history WHERE id = ?", (meal_id,)) as cur:
        return (await cur.fetchone())[0]


# A plan for the user's own meal is asked of the LLM once, saved with the meal, and the next request gets it from the cache
async def test_plan_caches_result(client, db):
    meal_id = await _add_meal(db, "testuser", "Toast")
    body = {"meal_name": "Toast", "menu": [{"name": "Toast", "ingredients": [{"name": "Bread", "amount": 2, "unit": "slice"}]}],
            "meal_id": meal_id}

    with patch("routers.scheduler.stream_response", side_effect=_mock_stream(TOAST_REPLY)) as llm:
        first = (await client.post("/scheduler/plan", json=body)).json()
        second = (await client.post("/scheduler/plan", json=body)).json()

    assert llm.call_count == 1
    assert first["cached"] is False and second["cached"] is True
    assert first["makespan_min"] == 3 and first["formatted"].startswith("⏱ Plan (3 min)")
    plan = ("timeline", "makespan_min", "formatted")
    assert {k: second[k] for k in plan} == {k: first[k] for k in plan}
    assert json.loads(await _schedule_of(db, meal_id))["formatted"] == first["formatted"]


# Another user's meal id neither returns that user's cached plan nor gets this plan saved over it
async def test_plan_never_uses_another_users_meal(client, db):
    theirs = json.dumps({"timeline": [], "makespan_min": 9, "formatted": "Their plan"})
    cached_id = await _add_meal(db, "other", "Their meal", schedule=theirs)
    empty_id = await _add_meal(db, "other", "Their other meal")

    with patch("routers.scheduler.stream_response", side_effect=_mock_stream(TOAST_REPLY)) as llm:
        for meal_id in (cached_id, empty_id):
            r = await client.post("/scheduler/plan", json={"meal_name": "Toast", "steps": ["Toast bread"], "meal_id": meal_id})
            assert r.status_code == 200
            assert r.json()["cached"] is False and r.json()["formatted"].startswith("⏱ Plan (3 min)")

    assert llm.call_count == 2
    assert await _schedule_of(db, cached_id) == theirs
    assert await _schedule_of(db, empty_id) is None
