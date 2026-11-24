"""Integration tests for POST /shopping/suggestions/generate with the LLM call mocked."""

import json
import logging
from unittest.mock import AsyncMock, patch

from services.llm import LLMUnavailableError
from services.shopping import SUGGESTIONS_SCHEMA


def _reply(*names):
    return json.dumps({"items": [{"name": n, "reason": "Good"} for n in names]})


def _llm(*replies):
    return patch("routers.shopping.chat_json", AsyncMock(side_effect=list(replies)))


async def _suggest(client, exclude=None):
    r = await client.post("/shopping/suggestions/generate", json={"exclude": exclude or []})
    assert r.status_code == 200
    return r.json()


# Fridge items, the shopping list, shown items and the avoid list are dropped by exact name
async def test_drops_known_items_by_exact_name(client):
    await client.post("/ingredients/", json={"name": "Strawberries"})
    await client.post("/shopping/", json={"item_name": "Kiwi"})
    await client.put("/preferences/avoid:Milk", json={"value": "Milk"})
    reply = _reply("Strawberry", "Frozen strawberries", "Kiwis", "Pear", "Milk", "Almond milk", "Salmon")
    with _llm(reply):
        data = await _suggest(client, exclude=["Pear"])
    assert [s["name"] for s in data["suggestions"]] == ["Frozen strawberries", "Almond milk", "Salmon"]
    assert data["lyric"] is None


# The call uses the schema, the shopping temperature and the profile country
async def test_call_uses_schema_and_country(client):
    await client.put("/profile/", json={"country": "Türkiye"})
    with _llm(_reply("Salmon")) as llm:
        await _suggest(client)
    kwargs = llm.call_args.kwargs
    assert kwargs["schema"] == SUGGESTIONS_SCHEMA
    assert kwargs["temperature"] == 0.6
    assert "Türkiye" in kwargs["system_prompt"]


# The request lists about 70% of the fridge, while code still drops anything in the whole fridge
async def test_request_lists_a_share_of_the_fridge(client):
    names = [f"Item {i}" for i in range(10)]
    for name in names:
        await client.post("/ingredients/", json={"name": name})
    with _llm(_reply(*names, "Salmon")) as llm:
        data = await _suggest(client)
    request = llm.call_args.kwargs["messages"][0]["content"]
    have = request.split("\n")[0].removeprefix("Some of what I have now: ").removesuffix(".").split(", ")
    assert len(have) == 7 and set(have) <= set(names)
    assert not any(n in llm.call_args.kwargs["system_prompt"] for n in names)
    assert [s["name"] for s in data["suggestions"]] == ["Salmon"]


# Dishes from the meal history are dropped, and the request names the reply language
async def test_drops_eaten_dishes_and_asks_in_the_reply_language(client):
    await client.post("/meals/", json={"meal_name": "Menemen", "ingredients": []})
    with _llm(_reply("Menemen", "Green peppers")) as llm:
        data = await _suggest(client)
    assert [s["name"] for s in data["suggestions"]] == ["Green peppers"]
    assert "English" in llm.call_args.kwargs["messages"][0]["content"][-60:]  # the reply language ends the request


# Dishes inside logged menus and favorite meals are dropped too, while their simple items stay products
async def test_drops_dishes_inside_menus_and_favorites(client):
    menemen = {"name": "Menemen", "ingredients": [{"name": "Eggs", "amount": 2, "unit": "pcs"}]}
    cheese = {"name": "White cheese", "amount": 50, "unit": "g", "ingredients": []}
    await client.post("/meals/", json={"meal_name": "Weekend breakfast", "menu_items": [menemen, cheese]})
    pancakes = {"name": "Pancakes", "ingredients": [{"name": "Flour", "amount": 100, "unit": "g"}]}
    await client.post("/favorites/", json={"meal_name": "Sunday plate", "menu_items": [pancakes]})
    with _llm(_reply("Menemen", "Pancakes", "White cheese", "Green peppers")):
        data = await _suggest(client)
    assert [s["name"] for s in data["suggestions"]] == ["White cheese", "Green peppers"]


# A reply made only of repeats is retried once, with those names listed as already shown
async def test_retries_once_when_everything_repeats(client):
    await client.post("/ingredients/", json={"name": "Eggs"})
    with _llm(_reply("Egg"), _reply("Egg", "Salmon")) as llm:
        data = await _suggest(client, exclude=["Pear"])
    assert [s["name"] for s in data["suggestions"]] == ["Salmon"]
    assert llm.call_count == 2
    retry_request = llm.call_args_list[1].kwargs["messages"][0]["content"]
    assert retry_request.endswith("which I've already seen: Pear, Egg.")


# When the retry repeats too, the reply is an empty list without an error
async def test_gives_up_after_one_retry(client):
    with _llm(_reply("Pear"), _reply("Pears")) as llm:
        data = await _suggest(client, exclude=["Pear"])
    assert data == {"suggestions": [], "lyric": None}
    assert llm.call_count == 2


# An unreadable reply returns an error and logs the raw text
async def test_unparseable_reply_is_logged(client, caplog):
    with _llm("Sure! Salmon, kiwi"), caplog.at_level(logging.WARNING):
        data = await _suggest(client)
    assert data["suggestions"] == []
    assert data["error"]
    assert "Sure! Salmon, kiwi" in caplog.text


# When Ollama is down the panel gets a lyric instead of suggestions
async def test_llm_unavailable_returns_lyric(client):
    with _llm(LLMUnavailableError("down")):
        data = await _suggest(client)
    assert data["suggestions"] == []
    assert data["lyric"]


# An item removed from the suggestions list is left out for 7 days, then it may come back
async def test_removed_item_left_out_for_seven_days(client, db):
    await client.put("/shopping/suggestions", json={"items": [], "removed": ["Salmon"]})
    with _llm(_reply("Salmon", "Kiwi")):
        data = await _suggest(client)
    assert [s["name"] for s in data["suggestions"]] == ["Kiwi"]

    await db.execute("UPDATE shopping_suggestions SET removed_at = datetime('now', '-8 days')")
    await db.commit()
    with _llm(_reply("Salmon", "Kiwi")):
        data = await _suggest(client)
    assert [s["name"] for s in data["suggestions"]] == ["Salmon", "Kiwi"]


# After Settings brings back the removed items, the next press may suggest them again
async def test_brought_back_item_may_be_suggested_again(client):
    await client.put("/shopping/suggestions", json={"items": [], "removed": ["Salmon"]})
    await client.delete("/shopping/suggestions/removed")
    with _llm(_reply("Salmon", "Kiwi")):
        data = await _suggest(client)
    assert [s["name"] for s in data["suggestions"]] == ["Salmon", "Kiwi"]


async def _weekly_analysis(db, days_ago: int):
    """An analysis of the test user's meals run `days_ago` days ago: fiber lacking, sugar more than enough."""
    await db.execute(
        "INSERT INTO weekly_summaries (user_id, week_key, narrative, scores, created_at, lacking, more_than_enough) "
        "SELECT id, 'w', 'A sweet week', '[]', datetime('now', ?), '[\"fiber\"]', '[\"sugar\"]' "
        "FROM users WHERE name = 'testuser'",
        (f"-{days_ago} days",),
    )
    await db.commit()


# Suggest Shopping and Suggest More both get the nutrients of an analysis from the last 7 days (#207)
async def test_recent_analysis_nutrients_reach_every_press(client, db):
    await _weekly_analysis(db, days_ago=2)
    with _llm(_reply("Salmon"), _reply("Kiwi")) as llm:
        await _suggest(client)
        await _suggest(client, exclude=["Salmon"])
    for call in llm.call_args_list:
        assert "lacking fiber; more than enough sugar." in call.kwargs["system_prompt"]


# An analysis older than 7 days, or none, gives the shopping prompt no nutrient line (#207)
async def test_no_nutrient_line_without_a_recent_analysis(client, db):
    with _llm(_reply("Salmon")) as llm:
        await _suggest(client)
    assert "Nutrients in recent breakfasts" not in llm.call_args.kwargs["system_prompt"]

    await _weekly_analysis(db, days_ago=8)
    with _llm(_reply("Salmon")) as llm:
        await _suggest(client)
    assert "Nutrients in recent breakfasts" not in llm.call_args.kwargs["system_prompt"]
