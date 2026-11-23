"""Tests for request size limits, refusals (422) and what error replies hold (#210).

The limits come from models/limits.py, so a test never repeats a number.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from models import limits


def _menu(count: int) -> list[dict]:
    return [{"name": f"Item {i}", "amount": 1, "unit": "pcs", "ingredients": []} for i in range(count)]


@pytest.mark.asyncio
async def test_fridge_name_over_limit_refused(client):
    """A fridge name over the length limit gets 422, and a long real one is still added."""
    r = await client.post("/ingredients/", json={"name": "x" * (limits.NAME_MAX + 1)})
    assert r.status_code == 422
    r = await client.post("/ingredients/", json={"name": "Extra virgin olive oil from the village, cold pressed"})
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_bulk_shopping_over_limit_refused(client):
    """A bulk shopping request over the list limit gets 422, and a big real list is still added."""
    too_many = [{"item_name": f"Item {i}"} for i in range(limits.BULK_ITEMS_MAX + 1)]
    assert (await client.post("/shopping/bulk", json=too_many)).status_code == 422
    r = await client.post("/shopping/bulk", json=[{"item_name": f"Item {i}"} for i in range(300)])
    assert r.status_code == 201
    assert len((await client.get("/shopping/")).json()) == 300


@pytest.mark.asyncio
async def test_shopping_item_name_over_limit_refused(client):
    """A shopping item name over the length limit gets 422, alone or in a bulk request."""
    long_name = "x" * (limits.NAME_MAX + 1)
    assert (await client.post("/shopping/", json={"item_name": long_name})).status_code == 422
    assert (await client.post("/shopping/bulk", json=[{"item_name": long_name}])).status_code == 422


@pytest.mark.asyncio
async def test_habit_and_rule_text_over_limit_refused(client):
    """Habit and health rule text over the length limit gets 422, and a few sentences still save."""
    too_long = "x" * (limits.TEXT_MAX + 1)
    assert (await client.post("/preferences/habits", json={"description": too_long})).status_code == 422
    assert (await client.post("/health-rules/", json={"rule_text": too_long})).status_code == 422
    sentences = "I skip dairy on weekdays and like something warm when it is cold outside. " * 5
    assert (await client.post("/preferences/habits", json={"description": sentences})).status_code == 201
    assert (await client.post("/health-rules/", json={"rule_text": sentences})).status_code == 201


@pytest.mark.asyncio
async def test_preference_over_limit_refused(client):
    """A preference value or key over the length limit gets 422, and a sentence as the value still saves."""
    assert (await client.put("/preferences/avoid:x", json={"value": "x" * (limits.TEXT_MAX + 1)})).status_code == 422
    long_key = "k" * (limits.PREFERENCE_KEY_MAX + 1)
    assert (await client.put(f"/preferences/{long_key}", json={"value": "x"})).status_code == 422
    sentence = "no cheese, milk included"
    assert (await client.put(f"/preferences/avoid:{sentence}", json={"value": sentence})).status_code == 200


@pytest.mark.asyncio
async def test_meals_limit_bounds(client):
    """GET /meals takes a limit from 1 to the maximum and refuses anything else with 422."""
    assert (await client.get("/meals/?limit=0")).status_code == 422
    assert (await client.get("/meals/?limit=-5")).status_code == 422
    assert (await client.get(f"/meals/?limit={limits.MEALS_LIMIT_MAX + 1}")).status_code == 422
    assert (await client.get("/meals/?limit=1")).status_code == 200
    assert (await client.get(f"/meals/?limit={limits.MEALS_LIMIT_MAX}")).status_code == 200
    assert (await client.get("/meals/")).status_code == 200


@pytest.mark.asyncio
async def test_logged_meal_menu_over_limit_refused(client):
    """A logged meal with a menu over the item limit gets 422, and a long real menu is still logged."""
    r = await client.post("/meals/", json={"meal_name": "Feast", "menu_items": _menu(limits.MENU_ITEMS_MAX + 1)})
    assert r.status_code == 422
    r = await client.post("/meals/", json={"meal_name": "Feast", "menu_items": _menu(30)})
    assert r.status_code == 201
    assert len(r.json()["menu_items"]) == 30


@pytest.mark.asyncio
async def test_logged_meal_oversized_json_refused(client):
    """A logged meal whose menu is too large as a whole gets 422, however few items it has."""
    huge = [{"name": "Dish", "ingredients": [], "method": "x" * limits.MEAL_JSON_MAX}]
    assert (await client.post("/meals/", json={"meal_name": "Feast", "menu_items": huge})).status_code == 422


@pytest.mark.asyncio
async def test_favorite_body_is_typed(client):
    """A favorite whose fields have the wrong type gets 422 instead of being stored."""
    assert (await client.post("/favorites/", json={"meal_name": "Toast", "ingredients": "bread"})).status_code == 422
    assert (await client.post("/favorites/", json={"meal_name": ["Toast"]})).status_code == 422
    assert (await client.post("/favorites/", json=["Toast"])).status_code == 422
    fav_id = (await client.post("/favorites/", json={"meal_name": "Toast"})).json()["id"]
    assert (await client.put(f"/favorites/{fav_id}", json={"meal_name": "Toast", "steps": "toast it"})).status_code == 422


@pytest.mark.asyncio
async def test_favorite_over_limits_refused(client):
    """A favorite with a name or a menu over the limits gets 422."""
    r = await client.post("/favorites/", json={"meal_name": "x" * (limits.MEAL_NAME_MAX + 1)})
    assert r.status_code == 422
    r = await client.post("/favorites/", json={"meal_name": "Feast", "menu_items": _menu(limits.MENU_ITEMS_MAX + 1)})
    assert r.status_code == 422
    r = await client.post("/favorites/", json={"meal_name": "Feast", "menu": _menu(limits.MENU_ITEMS_MAX + 1)})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_favorite_saved_as_the_editor_sends_it(client):
    """A favorite sent with the editor's extra fields, a long menu and a prep time as text is saved."""
    meal = {
        "id": 7, "obtained": ["Egg"], "created_at": "2026-01-01",
        "menu_name": "Big breakfast", "meal_name": "Big breakfast",
        "menu": _menu(30), "menu_items": _menu(30),
        "ingredients": [{"name": "Egg", "amount": 2, "unit": "pcs"}, "Salt"],
        "steps": None, "description": None, "prep_time_min": "15",
    }
    r = await client.post("/favorites/", json=meal)
    assert r.status_code == 201
    saved = (await client.get("/favorites/")).json()[0]
    assert saved["meal_name"] == "Big breakfast"
    assert len(saved["menu_items"]) == 30
    assert saved["ingredients"] == meal["ingredients"]
    assert saved["steps"] == []
    assert saved["prep_time_min"] == 15


@pytest.mark.asyncio
async def test_session_message_over_limit_refused(client):
    """A saved chat message over the length limit or with an unknown role gets 422, and a long one still saves."""
    session_id = (await client.post("/sessions/")).json()["session_id"]
    url = f"/sessions/{session_id}/messages"
    too_long = "x" * (limits.MESSAGE_CONTENT_MAX + 1)
    assert (await client.post(url, json={"role": "assistant", "content": too_long})).status_code == 422
    assert (await client.post(url, json={"role": "system", "content": "hi"})).status_code == 422
    r = await client.post(url, json={"role": "assistant", "content": "A long analysis. " * 500})
    assert r.status_code == 200
    message_id = r.json()["id"]
    assert (await client.put(f"{url}/{message_id}", json={"content": too_long})).status_code == 422
    assert (await client.put(f"{url}/{message_id}", json={"ate_draft": "not a meal"})).status_code == 422
    assert (await client.put(f"{url}/{message_id}", json={})).status_code == 422
    assert (await client.put(f"{url}/{message_id}", json={"ate_draft": {"menu": _menu(30)}})).status_code == 200


@pytest.mark.asyncio
async def test_refusals_are_422(client):
    """A blank staple name and a health rule update with nothing to change get 422."""
    assert (await client.post("/favorite-ingredients/", json={"ingredient_name": "   "})).status_code == 422
    rule_id = (await client.post("/health-rules/", json={"rule_text": "Less sugar"})).json()["id"]
    assert (await client.put(f"/health-rules/{rule_id}", json={})).status_code == 422


@pytest.mark.asyncio
async def test_invalid_group_reply_does_not_repeat_the_input(client):
    """An unknown group gets 422 with a fixed message that doesn't repeat what was sent."""
    r = await client.post("/ingredients/", json={"name": "Milk", "group_name": "Made-up group"})
    assert r.status_code == 422
    assert "Made-up group" not in r.text


@pytest.mark.asyncio
async def test_validation_reply_does_not_echo_the_input(client):
    """A 422 reply says where and why, without the value that was sent or library details."""
    secret = "s3cret-value-" + "x" * limits.NAME_MAX
    r = await client.post("/ingredients/", json={"name": secret})
    assert r.status_code == 422
    assert "s3cret-value" not in r.text
    assert "pydantic" not in r.text
    assert r.json()["detail"][0]["loc"] == ["body", "name"]
    assert set(r.json()["detail"][0]) == {"loc", "msg"}


@pytest.mark.asyncio
async def test_login_validation_reply_does_not_echo_the_pin(client):
    """A login refused for its size doesn't send the PIN back."""
    pin = "9" * 65
    r = await client.post("/auth/login", json={"name": "testuser", "pin": pin})
    assert r.status_code == 422
    assert pin not in r.text


@pytest.mark.asyncio
async def test_request_body_over_limit_refused(client):
    """A request body over the size limit gets 413 before it is read."""
    r = await client.post("/shopping/", json={"item_name": "x" * (limits.MAX_BODY_BYTES + 1)})
    assert r.status_code == 413
    assert r.json() == {"detail": "Request too large"}


async def _chunks(body: bytes, size: int = 64 * 1024):
    """A body sent in pieces, without a declared length (chunked)."""
    for start in range(0, len(body), size):
        yield body[start:start + size]


@pytest.mark.asyncio
async def test_undeclared_body_over_limit_refused(client):
    """A body sent without a declared length gets 413 once it passes the size limit, and nothing is saved."""
    body = json.dumps({"item_name": "x" * (limits.MAX_BODY_BYTES + 1)}).encode()
    r = await client.post("/shopping/", content=_chunks(body), headers={"Content-Type": "application/json"})
    assert "content-length" not in {k.lower() for k in r.request.headers}
    assert r.status_code == 413
    assert r.json() == {"detail": "Request too large"}
    assert (await client.get("/shopping/")).json() == []


@pytest.mark.asyncio
async def test_undeclared_body_under_limit_works(client):
    """A body sent without a declared length, in several pieces, under the size limit is read as usual."""
    items = [{"item_name": f"Item {i} " + "x" * 150} for i in range(limits.BULK_ITEMS_MAX)]
    body = json.dumps(items).encode()
    assert limits.MAX_BODY_BYTES > len(body) > 64 * 1024
    r = await client.post("/shopping/bulk", content=_chunks(body), headers={"Content-Type": "application/json"})
    assert "content-length" not in {k.lower() for k in r.request.headers}
    assert r.status_code == 201
    assert len((await client.get("/shopping/")).json()) == limits.BULK_ITEMS_MAX


@pytest.mark.asyncio
async def test_declared_length_that_is_not_a_number_refused(client):
    """A declared body length that isn't a number gets 413."""
    r = await client.post("/shopping/", content=b'{"item_name": "Milk"}', headers={
        "Content-Type": "application/json", "Content-Length": "abc",
    })
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_prep_time_out_of_range_refused(client):
    """A prep time below zero or over the maximum gets 422 on logged meals and favorites, and one in range saves."""
    for minutes in (-1, limits.PREP_TIME_MAX + 1):
        assert (await client.post("/meals/", json={"meal_name": "Toast", "prep_time_min": minutes})).status_code == 422
        r = await client.post("/favorites/", json={"meal_name": "Toast", "prep_time_min": minutes})
        assert r.status_code == 422
    meal = (await client.post("/meals/", json={"meal_name": "Toast", "prep_time_min": 20})).json()
    r = await client.put(f"/meals/{meal['id']}", json={"meal_name": "Toast", "prep_time_min": limits.PREP_TIME_MAX + 1})
    assert r.status_code == 422
    assert (await client.post("/favorites/", json={"meal_name": "Toast", "prep_time_min": 20})).status_code == 201


@pytest.mark.asyncio
async def test_ingredient_quantity_out_of_range_refused(client):
    """An ingredient quantity below zero or over the maximum gets 422, and a real one is logged."""
    for quantity in (-1, limits.AMOUNT_MAX + 1):
        body = {"meal_name": "Toast", "ingredients": [{"name": "Bread", "quantity": quantity, "unit": "slice"}]}
        assert (await client.post("/meals/", json=body)).status_code == 422
    body = {"meal_name": "Toast", "ingredients": [{"name": "Bread", "quantity": 2, "unit": "slice"}]}
    assert (await client.post("/meals/", json=body)).status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize("field, too_low, too_high", [
    ("age", 0, limits.AGE_MAX + 1),
    ("height_cm", 0, limits.HEIGHT_CM_MAX + 1),
    ("weight_kg", 0, limits.WEIGHT_KG_MAX + 0.5),
])
async def test_profile_numbers_out_of_range_refused(client, field, too_low, too_high):
    """A profile age, height or weight outside its range gets 422, and one at the maximum saves."""
    assert (await client.put("/profile/", json={field: too_low})).status_code == 422
    assert (await client.put("/profile/", json={field: too_high})).status_code == 422
    top = {"age": limits.AGE_MAX, "height_cm": limits.HEIGHT_CM_MAX, "weight_kg": limits.WEIGHT_KG_MAX}[field]
    r = await client.put("/profile/", json={field: top})
    assert r.status_code == 200
    assert r.json()[field] == top


@pytest.mark.asyncio
async def test_profile_saved_before_the_ranges_still_reads(client, db):
    """A profile stored with a value outside today's ranges is still returned."""
    await client.put("/profile/", json={"age": 30})
    await db.execute("UPDATE user_profiles SET height_cm = ?", (limits.HEIGHT_CM_MAX + 50,))
    await db.commit()
    r = await client.get("/profile/")
    assert r.status_code == 200
    assert r.json()["height_cm"] == limits.HEIGHT_CM_MAX + 50


# Each route with an id in its path, as (method, path with {id}, body)
_ID_PATHS = [
    ("PUT", "/favorites/{id}", {"meal_name": "Toast"}),
    ("DELETE", "/favorites/{id}", None),
    ("PUT", "/health-rules/{id}", {"rule_text": "Less sugar"}),
    ("DELETE", "/health-rules/{id}", None),
    ("PATCH", "/ingredients/{id}", {"name": "Milk"}),
    ("DELETE", "/ingredients/{id}", None),
    ("GET", "/meals/{id}", None),
    ("PUT", "/meals/{id}", {"meal_name": "Toast"}),
    ("DELETE", "/meals/{id}", None),
    ("DELETE", "/preferences/habits/{id}", None),
    ("PUT", "/profile/supplements/{id}", {"name": "Vitamin D"}),
    ("DELETE", "/profile/supplements/{id}", None),
    ("POST", "/profile/supplements/{id}/toggle", {"taken": True}),
    ("PUT", "/ratings/{id}", {"rating": 5}),
    ("DELETE", "/ratings/{id}", None),
    ("PUT", "/sessions/s1/messages/{id}", {"content": "hi"}),
    ("DELETE", "/shopping/{id}", None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method, path, body", _ID_PATHS)
async def test_path_id_out_of_range_refused(client, method, path, body):
    """An id in a path below 1 or over the maximum gets 422, and an unknown id in range gets the route's usual reply."""
    for bad in (0, -1, limits.ID_MAX + 1):
        r = await client.request(method, path.format(id=bad), json=body)
        assert r.status_code == 422, (path, bad)
    r = await client.request(method, path.format(id=limits.ID_MAX), json=body)
    assert r.status_code in (204, 404), path


@pytest.mark.asyncio
async def test_ids_in_bodies_out_of_range_refused(client):
    """An id in a request body or list below 1 or over the maximum gets 422 on each endpoint that takes one."""
    session_id = (await client.post("/sessions/")).json()["session_id"]
    for bad in (0, limits.ID_MAX + 1):
        assert (await client.post("/shopping/bought", json={"ids": [bad]})).status_code == 422
        for field in ("delete_ids", "keep_ids", "shopping_ids"):
            assert (await client.post("/ingredients/expired/action", json={field: [bad]})).status_code == 422
        r = await client.put(f"/sessions/{session_id}/selected", json={"message_id": bad})
        assert r.status_code == 422
        r = await client.post("/analyst/analyze", json={"meal_name": "Toast", "ingredients": [], "meal_id": bad})
        assert r.status_code == 422
        r = await client.post("/scheduler/plan", json={"meal_name": "Toast", "meal_id": bad})
        assert r.status_code == 422
    assert (await client.post("/shopping/bought", json={"ids": [limits.ID_MAX]})).status_code == 200
    assert (await client.put(f"/sessions/{session_id}/selected", json={"message_id": None})).status_code == 200


@pytest.mark.asyncio
async def test_long_path_text_refused(client):
    """Text in a path longer than its matching field gets 422: session ids, preference keys, appliance keys, staples."""
    long_session = "s" * (limits.SESSION_ID_MAX + 1)
    assert (await client.delete(f"/sessions/{long_session}")).status_code == 422
    assert (await client.get(f"/sessions/{long_session}/messages")).status_code == 422
    assert (await client.put(f"/sessions/{long_session}/selected", json={"message_id": None})).status_code == 422
    assert (await client.put(f"/sessions/{long_session}/messages/1", json={"content": "hi"})).status_code == 422
    assert (await client.delete(f"/preferences/{'k' * (limits.PREFERENCE_KEY_MAX + 1)}")).status_code == 422
    r = await client.put(f"/kitchen/{'k' * (limits.APPLIANCE_KEY_MAX + 1)}", json={"enabled": True})
    assert r.status_code == 422
    assert (await client.delete(f"/favorite-ingredients/{'n' * (limits.NAME_MAX + 1)}")).status_code == 422
    # In range, an unknown one is still just not found
    assert (await client.delete("/favorite-ingredients/Eggs")).status_code == 404
    assert (await client.put("/kitchen/spaceship", json={"enabled": True})).status_code == 404


@pytest.mark.asyncio
async def test_shopping_suggestions_error_holds_no_exception_text(client, caplog):
    """When shopping suggestions fail, the reply carries a fixed message and the cause goes to the log only."""
    cause = "Traceback: C:\\server\\secret\\path.py connection refused at 10.0.0.5"
    with patch("routers.shopping.chat_json", AsyncMock(side_effect=RuntimeError(cause))):
        r = await client.post("/shopping/suggestions/generate", json={"exclude": []})
    assert r.status_code == 200
    assert r.json()["suggestions"] == []
    assert "secret" not in r.text and "10.0.0.5" not in r.text and "RuntimeError" not in r.text
    assert r.json()["error"] == "Could not get suggestions. Please try again."
    assert "connection refused" in caplog.text


@pytest.mark.asyncio
async def test_shopping_context_error_holds_no_exception_text(client):
    """When loading the shopping context fails, the reply carries the same fixed message."""
    cause = "no such table: secret_table"
    with patch("routers.shopping.load_shopping_context", AsyncMock(side_effect=RuntimeError(cause))):
        r = await client.post("/shopping/suggestions/generate", json={"exclude": []})
    assert r.status_code == 200
    assert "secret_table" not in r.text
    assert r.json()["error"] == "Could not get suggestions. Please try again."


@pytest.mark.asyncio
async def test_replies_leave_out_the_account_id(client):
    """Replies about the user's own data don't carry the account's internal id."""
    await client.post("/favorites/", json={"meal_name": "Toast"})
    await client.post("/favorite-ingredients/", json={"ingredient_name": "Eggs"})
    await client.post("/profile/supplements", json={"name": "Vitamin D"})
    await client.post("/ratings/", json={"product_name": "Eggs", "rating": 9})
    await client.post("/health-rules/", json={"rule_text": "Less sugar"})
    await client.put("/profile/", json={"age": 30})
    for url in (
        "/favorites/", "/favorite-ingredients/", "/profile/supplements", "/profile/supplements/today",
        "/ratings/", "/health-rules/", "/profile/",
    ):
        r = await client.get(url)
        assert r.status_code == 200
        assert r.json(), url
        assert "user_id" not in r.text, url


# --- Every request field has a limit (#246) ---

def _unbounded(schema: dict, where: str, components: dict, seen: tuple = ()) -> list[str]:
    """The places in a request schema without a limit: text without a maximum length, a number
    without a range, a list or a map without a maximum count, free-form JSON without a size cap."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return [] if name in seen else _unbounded(components[name], where, components, seen + (name,))
    if "x-max-json-chars" in schema or "enum" in schema or "const" in schema:
        return []
    found = []
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(key, []):
            found += _unbounded(sub, where, components, seen)
    kind = schema.get("type")
    if kind == "string" and "maxLength" not in schema and schema.get("format") not in ("date", "date-time"):
        found.append(f"{where}: text without a maximum length")
    if kind in ("integer", "number"):
        has_min = "minimum" in schema or "exclusiveMinimum" in schema
        has_max = "maximum" in schema or "exclusiveMaximum" in schema
        if not (has_min and has_max):
            found.append(f"{where}: a number without a range")
    if kind == "array":
        if "maxItems" not in schema:
            found.append(f"{where}: a list without a maximum count")
        found += _unbounded(schema.get("items", {}), f"{where}[]", components, seen)
    if kind == "object":
        for name, sub in schema.get("properties", {}).items():
            found += _unbounded(sub, f"{where}.{name}", components, seen)
        extra = schema.get("additionalProperties")
        if extra is not False and not schema.get("properties"):
            if "maxProperties" not in schema:
                found.append(f"{where}: a map without a maximum count")
            if isinstance(extra, dict):
                found += _unbounded(extra, f"{where}.*", components, seen)
            found += _unbounded(schema.get("propertyNames", {"type": "string"}), f"{where} (key)", components, seen)
    return found


def test_every_request_field_has_a_limit():
    """Every body, path and query field of every route has a limit, so a new field without one fails here."""
    from fastapi.openapi.utils import get_openapi

    from main import app

    spec = get_openapi(title="check", version="1", routes=app.routes)
    components = spec.get("components", {}).get("schemas", {})
    found = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            for param in operation.get("parameters", []):
                if param["in"] in ("path", "query"):
                    found += _unbounded(param["schema"], f"{method.upper()} {path} {param['name']}", components)
            for content in operation.get("requestBody", {}).get("content", {}).values():
                found += _unbounded(content["schema"], f"{method.upper()} {path} body", components)
    assert len(spec["paths"]) > 30  # the walk saw the app's routes
    assert found == []
