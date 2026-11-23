"""Another user's data: every route that takes an id (in its path, or in its body) answers another
user's id exactly as it answers an id that doesn't exist, and reads, changes or deletes nothing of
theirs. Every app route with a path parameter must have a case here, so a new one fails until it does."""

import json
import uuid

import aiosqlite

import database
from auth import create_token, hash_pin
from main import app
from services import llm
from tests.routes import api_endpoints

MARK = "Zed"  # in every name and text the other user saves, so a reply that shows their data is caught
MEAL = {"meal_name": "My meal", "ingredients": ["Bread"], "steps": []}

# (method, route, path parameters → which id fills them, body made from those ids)
CASES = [
    ("GET", "/meals/{meal_id}", {"meal_id": "meal"}, None),
    ("PUT", "/meals/{meal_id}", {"meal_id": "meal"}, lambda ids: MEAL),
    ("DELETE", "/meals/{meal_id}", {"meal_id": "meal"}, None),
    ("PUT", "/favorites/{fav_id}", {"fav_id": "favorite"}, lambda ids: MEAL),
    ("DELETE", "/favorites/{fav_id}", {"fav_id": "favorite"}, None),
    ("DELETE", "/favorite-ingredients/{ingredient_name}", {"ingredient_name": "staple"}, None),
    ("PATCH", "/ingredients/{ingredient_id}", {"ingredient_id": "ingredient"}, lambda ids: {"name": "Renamed"}),
    ("DELETE", "/ingredients/{ingredient_id}", {"ingredient_id": "ingredient"}, None),
    ("DELETE", "/preferences/{key}", {"key": "preference"}, None),
    ("PUT", "/preferences/{key}", {"key": "preference"}, lambda ids: {"value": "mine"}),
    ("DELETE", "/preferences/habits/{habit_id}", {"habit_id": "habit"}, None),
    ("PUT", "/kitchen/{appliance_key}", {"appliance_key": "appliance"}, lambda ids: {"enabled": False}),
    ("PUT", "/profile/supplements/{supp_id}", {"supp_id": "supplement"}, lambda ids: {"name": "Mine"}),
    ("POST", "/profile/supplements/{supp_id}/toggle", {"supp_id": "supplement"}, lambda ids: {"taken": False}),
    ("DELETE", "/profile/supplements/{supp_id}", {"supp_id": "supplement"}, None),
    ("PUT", "/ratings/{rating_id}", {"rating_id": "rating"}, lambda ids: {"rating": 3}),
    ("DELETE", "/ratings/{rating_id}", {"rating_id": "rating"}, None),
    ("PUT", "/health-rules/{rule_id}", {"rule_id": "rule"}, lambda ids: {"rule_text": "Mine"}),
    ("DELETE", "/health-rules/{rule_id}", {"rule_id": "rule"}, None),
    ("DELETE", "/shopping/{item_id}", {"item_id": "item"}, None),
    ("GET", "/sessions/{session_id}/messages", {"session_id": "session"}, None),
    ("POST", "/sessions/{session_id}/messages", {"session_id": "session"}, lambda ids: {"role": "user", "content": "Hi"}),
    ("PUT", "/sessions/{session_id}/messages/{message_id}", {"session_id": "session", "message_id": "message"},
     lambda ids: {"content": "Changed"}),
    # Their message through the user's own session
    ("PUT", "/sessions/{session_id}/messages/{message_id}", {"session_id": "my_session", "message_id": "message"},
     lambda ids: {"content": "Changed"}),
    ("PUT", "/sessions/{session_id}/selected", {"session_id": "session"}, lambda ids: {"message_id": None}),
    ("PUT", "/sessions/{session_id}/selected", {"session_id": "my_session"}, lambda ids: {"message_id": ids["message"]}),
    ("DELETE", "/sessions/{session_id}", {"session_id": "session"}, None),
    # Ids in the body
    ("POST", "/shopping/bought", {}, lambda ids: {"ids": [ids["item"]]}),
    ("POST", "/ingredients/expired/action", {}, lambda ids: {"keep_ids": [ids["ingredient"]]}),
    ("POST", "/ingredients/expired/action", {}, lambda ids: {"shopping_ids": [ids["ingredient"]]}),
    ("POST", "/ingredients/expired/action", {}, lambda ids: {"delete_ids": [ids["ingredient"]]}),
    ("POST", "/analyst/analyze", {}, lambda ids: {"meal_name": "Toast", "ingredients": [], "meal_id": ids["meal"]}),
    ("POST", "/scheduler/plan", {}, lambda ids: {"meal_name": "Toast", "steps": ["Toast bread"], "meal_id": ids["meal"]}),
]

# Keys every user has (an appliance, a setting name): the request changes the user's own row, so its
# answer isn't compared with a missing key's, only checked for touching nothing of the other user's
SHARED_KEYS = {("PUT", "/kitchen/{appliance_key}"), ("PUT", "/preferences/{key}")}

# Routes that answer a missing id without 404, the same for another user's: a delete that is
# idempotent (204, nothing deleted) and a session's messages (an empty list)
NOT_404 = {
    ("DELETE", "/ingredients/{ingredient_id}"): 204,
    ("DELETE", "/profile/supplements/{supp_id}"): 204,
    ("DELETE", "/shopping/{item_id}"): 204,
    ("DELETE", "/sessions/{session_id}"): 204,
    ("GET", "/sessions/{session_id}/messages"): 200,
    ("POST", "/shopping/bought"): 200,
    ("POST", "/ingredients/expired/action"): 200,
    ("POST", "/analyst/analyze"): 200,
    ("POST", "/scheduler/plan"): 200,
}


async def _add_other_user():
    """A second user and their auth header."""
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        cur = await db.execute("INSERT INTO users (name, pin_hash) VALUES (?, ?)", (f"{MARK} user", hash_pin("567890")))
        await db.commit()
    return cur.lastrowid, {"Authorization": f"Bearer {create_token(cur.lastrowid)}"}


async def _seed(client, headers, user_id):
    """One row of every kind for the other user, saved through the API as they would, each with MARK in it."""

    async def made(method, path, body=None):
        r = await client.request(method, path, json=body, headers=headers)
        assert r.status_code < 300, (path, r.text)
        return r.json() if r.content else None

    session = (await made("POST", "/sessions/"))["session_id"]
    message = (await made("POST", f"/sessions/{session}/messages", {"content": f"{MARK} card", "select": True}))["id"]
    supplement = (await made("POST", "/profile/supplements", {"name": f"{MARK} pill", "frequency": "daily"}))["id"]
    await made("POST", f"/profile/supplements/{supplement}/toggle", {"taken": False})
    meal = (await made("POST", "/meals/", {"meal_name": f"{MARK} meal", "ingredients": [f"{MARK} bread"]}))["id"]
    ids = {
        "session": session,
        "message": message,
        "supplement": supplement,
        "meal": meal,
        "favorite": (await made("POST", "/favorites/", {"meal_name": f"{MARK} favorite"}))["id"],
        "staple": (await made("POST", "/favorite-ingredients/", {"ingredient_name": f"{MARK} staple"}))["ingredient_name"],
        "ingredient": (await made("POST", "/ingredients/", {"name": f"{MARK} cheese", "expiry_date": "2000-01-01"}))["id"],
        "preference": (await made("PUT", "/preferences/likes", {"value": f"{MARK} likes"}))["key"],
        "habit": (await made("POST", "/preferences/habits", {"description": f"{MARK} habit"}))["id"],
        "appliance": (await made("PUT", "/kitchen/oven", {"enabled": True}))["key"],
        "rating": (await made("POST", "/ratings/", {"product_name": f"{MARK} jam"}))["id"],
        "rule": (await made("POST", "/health-rules/", {"rule_text": f"{MARK} rule"}))["id"],
        "item": (await made("POST", "/shopping/", {"item_name": f"{MARK} milk"}))["id"],
    }
    # A cached analysis and prep plan, which a request with their meal id must not return or replace
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        cached = json.dumps({"analysis_text": f"{MARK} analysis", "formatted": f"{MARK} plan", "timeline": [], "makespan_min": 1})
        await db.execute("UPDATE meal_history SET cached_nutrition = ?, schedule = ? WHERE id = ?", (cached, cached, meal))
        await db.commit()
    return ids


async def _rows_of(user_id):
    """Every row the user owns, in every table, to show a request changed nothing of theirs."""
    rows = {}
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type = 'table'") as cur:
            tables = [r[0] for r in await cur.fetchall()]
        for table in tables:
            async with db.execute(f"PRAGMA table_info({table})") as cur:
                columns = [r[1] for r in await cur.fetchall()]
            key = "id" if table == "users" else "user_id"
            if key in columns:
                async with db.execute(f"SELECT * FROM {table} WHERE {key} = ?", (user_id,)) as cur:  # noqa: S608
                    rows[table] = sorted(map(repr, await cur.fetchall()))
    return rows


def _request(case, ids):
    """The case's method, URL and body with the given ids."""
    method, route, params, body = case
    return method, route.format(**{name: ids[key] for name, key in params.items()}), body(ids) if body else None


# Each route with an id answers another user's id as it answers a missing one, shows none of their data and changes none of their rows
async def test_other_users_ids_are_not_found(client, monkeypatch):
    monkeypatch.setattr(llm.lyric_cycler, "next", lambda: "A lyric")  # the fallback text stays the same between requests
    other_id, other_headers = await _add_other_user()
    theirs = await _seed(client, other_headers, other_id)
    my_session = (await client.post("/sessions/")).json()["session_id"]
    theirs["my_session"] = my_session
    missing = {key: 999_999 for key in theirs} | {
        "session": str(uuid.uuid4()), "staple": "Nobody's staple", "my_session": my_session,
        "preference": theirs["preference"], "appliance": theirs["appliance"],
    }
    before = await _rows_of(other_id)
    assert all(before[t] for t in ("meal_history", "chat_messages", "supplement_daily_log", "user_kitchen_appliances"))

    for case in CASES:
        method, route = case[0], case[1]
        method, url, body = _request(case, theirs)
        r = await client.request(method, url, json=body)
        assert MARK not in r.text, f"{method} {url} shows the other user's data"
        assert await _rows_of(other_id) == before, f"{method} {url} changed the other user's rows"
        if (method, route) in SHARED_KEYS:
            assert r.status_code == 200, f"{method} {url}: {r.status_code}"
            continue
        assert r.status_code == NOT_404.get((method, route), 404), f"{method} {url}: {r.status_code}"
        method, missing_url, missing_body = _request(case, missing)
        nothing = await client.request(method, missing_url, json=missing_body)
        assert (r.status_code, r.json() if r.content else None) == \
            (nothing.status_code, nothing.json() if nothing.content else None), f"{method} {url} differs from a missing id"


# Every app route with a path parameter has a case above, so a new id route fails until it gets one
def test_every_id_route_has_a_case():
    id_routes = {
        (method, e.path)
        for e in api_endpoints(app)
        if "{" in e.path and e.path != "/{full_path:path}"
        for method in e.methods - {"HEAD", "OPTIONS"}
    }
    covered = {(case[0], case[1]) for case in CASES}
    assert id_routes - covered == set()
    assert set(NOT_404) | SHARED_KEYS <= covered

