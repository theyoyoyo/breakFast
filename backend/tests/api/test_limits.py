"""Tests for request size limits, refusals (422) and what error replies hold (#210).

The limits come from models/limits.py, so a test never repeats a number.
"""

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
