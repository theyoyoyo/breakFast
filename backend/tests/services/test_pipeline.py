"""
Tests for the 3-step suggestion pipeline (draft → revise → present).
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from models.units import units_for
from services.personas import build_pipeline_analyst_prompt
from services.personas.pipeline_analyst import CHAT_STEP
from services.pipeline import LOW_INGREDIENT_TEXTS, RETRY_TEXTS, reviser_names, revision_schema, run_suggestion_pipeline
from utils import extract_json_block

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONTEXT = {
    "ingredients": [{"name": "eggs", "quantity": "6", "unit": "pcs"}],
    "history": [{"meal_name": "Menemen", "ingredients": '["eggs", "tomato"]'}],
    "preferences": {"favorite": "eggs", "dislike:olives": "Olives"},
    "stated_habits": ["early breakfast"],
    "inferred_habits": None,
    "health_rules": [{"rule_text": "Favor omega-3", "priority": "high"}],
    "user_profile": {"age": 30, "gender": "erkek", "height_cm": 180, "weight_kg": 75, "activity_level": "orta"},
    "supplements": [{"name": "Vitamin D", "frequency": "daily", "contents": "1000IU D3"}],
    "avoid_list": ["shellfish"],
}

EGGS = {"name": "eggs", "amount": 2, "unit": "pcs"}


def _meal(*ingredients: dict) -> dict:
    """A meal with one dish made of the given ingredients."""
    return {
        "menu": [{"name": "Boiled eggs", "ingredients": list(ingredients)}],
        "menu_name": "Eggs", "description": "Warm eggs.", "prep_time_min": 10,
    }


def _draft(meal: dict, text: str = "Enjoy!") -> str:
    return json.dumps({"text": text, "meal": meal})


def _revision(meal, changes=()) -> str:
    return json.dumps({"changes": list(changes), "meal": meal})


async def _run(draft, revision, present="A warm start.", context=SAMPLE_CONTEXT, mode=None, temperature=0.6, chat_block=None):
    """Run the pipeline on canned replies (an Exception raises instead): the draft and the reviser are
    structured calls, the present step streams. Returns the events and every model call."""
    calls = []

    async def fake_stream(system_prompt, history, message, temperature=None, **route):
        calls.append({"kind": "stream", "system": system_prompt, "message": message, "temperature": temperature, "route": route})
        if isinstance(present, Exception):
            raise present
        for char in present:
            yield char

    async def fake_chat_json(system_prompt, messages, schema, temperature=None, **route):
        reply = revision if any(c["kind"] == "json" for c in calls) else draft
        calls.append({
            "kind": "json", "system": system_prompt, "message": messages[0]["content"],
            "temperature": temperature, "schema": schema, "route": route,
        })
        if isinstance(reply, Exception):
            raise reply
        return reply

    with patch("services.pipeline.stream_response", fake_stream), patch("services.pipeline.chat_json", fake_chat_json):
        events = [
            e async for e in run_suggestion_pipeline(
                context=context, user_message="Suggest", mode=mode, temperature=temperature,
                chat_block=chat_block,
            )
        ]
    return events, calls


def _final(events) -> str:
    """The text the user gets: sent as tokens, then done, the same."""
    done = next(e["content"] for e in events if e["type"] == "done")
    assert "".join(e["content"] for e in events if e["type"] == "token") == done
    return done


def _without_emoji(meal: dict) -> dict:
    """The final meal without the icon the server gave it (random, #244)."""
    return {k: v for k, v in meal.items() if k != "emoji"}


# ---------------------------------------------------------------------------
# Reviser prompt and schema
# ---------------------------------------------------------------------------

class TestReviserPrompt:
    # The reviser is an internal step that returns the fixed meal, in the user's language
    def test_identity_and_language(self):
        prompt = build_pipeline_analyst_prompt(recent_meal_history=[])
        assert "English" in prompt and "Turkish" not in prompt
        turkish = build_pipeline_analyst_prompt([], language="tr")
        assert "Turkish" in turkish and "English" not in turkish

    # It sees the profile, supplements, health rules and recent meals
    def test_injects_user_context(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=SAMPLE_CONTEXT["history"],
            user_profile=SAMPLE_CONTEXT["user_profile"],
            supplements=SAMPLE_CONTEXT["supplements"],
            health_rules=SAMPLE_CONTEXT["health_rules"],
        )
        assert "180" in prompt and "Vitamin D" in prompt and "Favor omega-3" in prompt and "Menemen" in prompt

    # It gets the avoid list and the dislikes, which the old reviewer never saw
    def test_gets_avoid_list_and_dislikes(self):
        prompt = build_pipeline_analyst_prompt(
            [], avoid_list=["Almonds"], preferences={"fav:eggs": "Eggs", "dislike:tomatoes": "Tomatoes"},
        )
        assert "Almonds" in prompt
        assert "Tomatoes" in prompt
        assert "Eggs" not in prompt  # a favorite is no limit for the reviser
        assert "Almonds" not in build_pipeline_analyst_prompt([]) and "Tomatoes" not in build_pipeline_analyst_prompt([])

    # The Suggest mode tells it what to keep: a favorite stays familiar without a fixed recipe, explore stays new
    def test_mode_line(self):
        plain = build_pipeline_analyst_prompt([])
        favorites = build_pipeline_analyst_prompt([], mode="favorites")
        explore = build_pipeline_analyst_prompt([], mode="explore")
        assert len({plain, favorites, explore}) == 3
        assert build_pipeline_analyst_prompt([], mode="unknown") == plain

    # The prompt names the sections of the message the pipeline builds and the fields of the reply it reads, so the two
    # stay in step; the fridge reaches it and water stays unmentioned
    def test_prompt_matches_the_message_and_the_reply(self):
        prompt = build_pipeline_analyst_prompt([], ingredient_inventory=[{"name": "Yumurta"}])
        assert "Yumurta" in prompt
        for label in ("Code check", "Not in the fridge", "On the avoid list"):
            assert label in prompt, label
        for field in ("replaces", "prep", "changes"):
            assert field in prompt, field
        assert "water" not in prompt.lower()

    # After a chat it first lists what the chat asks now, each ask after the entries it comes from; a fresh press's prompt stays as it was
    def test_chat_step_only_after_a_chat(self):
        fresh, chat = build_pipeline_analyst_prompt([]), build_pipeline_analyst_prompt([], chat=True)
        for field in ("chat_asks", "from", "ask"):
            assert f'"{field}"' in CHAT_STEP, field
        assert chat.index(CHAT_STEP) < chat.index("Code check")  # the chat step comes before the fixes
        assert CHAT_STEP not in fresh and chat.replace(CHAT_STEP, "") == fresh

    # Units come from the reply language's list, with the fixed spoon and glass sizes
    def test_units_follow_the_language(self):
        english, turkish = build_pipeline_analyst_prompt([]), build_pipeline_analyst_prompt([], language="tr")
        assert all(unit in english for unit in units_for("en")) and all(unit in turkish for unit in units_for("tr"))
        assert "tbsp" in english and "tbsp" not in turkish


class TestRevisionSchema:
    # The changes come before the meal, the menu before its name, and a dish's ingredients before its name
    def test_order_puts_contents_before_names(self):
        schema = revision_schema("en")
        assert list(schema["properties"]) == ["changes", "meal"]
        meal = schema["properties"]["meal"]
        assert list(meal["properties"])[0] == "menu"
        item = meal["properties"]["menu"]["items"]
        assert list(item["properties"])[:2] == ["ingredients", "name"]

    # After a chat the reply starts with chat_asks, each the entries it comes from and then the ask, before the changes and the meal
    def test_chat_asks_come_first_after_a_chat(self):
        schema = revision_schema("en", chat=True)
        assert list(schema["properties"]) == schema["required"] == ["chat_asks", "changes", "meal"]
        ask = schema["properties"]["chat_asks"]["items"]
        assert list(ask["properties"]) == ask["required"] == ["from", "ask"]
        assert ask["properties"]["from"] == {"type": "array", "items": {"type": "integer"}}
        assert schema["properties"]["meal"] == revision_schema("en")["properties"]["meal"]
        assert revision_schema("en")["required"] == ["changes", "meal"]

    # Every item and ingredient has a numeric amount and a unit from the language's list, so no simple item lacks one
    def test_amounts_and_units(self):
        item = revision_schema("en")["properties"]["meal"]["properties"]["menu"]["items"]
        ingredient = item["properties"]["ingredients"]["items"]
        for shape in (item, ingredient):
            assert shape["properties"]["amount"] == {"type": "number"}
            assert "tbsp" in shape["properties"]["unit"]["enum"]
            assert {"amount", "unit"} <= set(shape["required"])
        tr_unit = revision_schema("tr")["properties"]["meal"]["properties"]["menu"]["items"]
        assert "tbsp" not in tr_unit["properties"]["unit"]["enum"]

    # A dish ingredient's name is limited to the given names, while an item's name stays free for a renamed dish;
    # `replaces` is optional, names only the draft's missing items, and is left out when nothing is missing
    def test_names_and_replaces(self):
        item = revision_schema("en", names=["Eggs", "Water"], missing=["Salmon"])["properties"]["meal"]["properties"]["menu"]["items"]
        ingredient = item["properties"]["ingredients"]["items"]
        assert ingredient["properties"]["name"] == {"type": "string", "enum": ["Eggs", "Water"]}
        assert item["properties"]["name"] == {"type": "string"}
        assert ingredient["properties"]["replaces"] == {"type": "string", "enum": ["Salmon"]}
        assert list(ingredient["properties"]) == ["name", "amount", "unit", "prep", "replaces"]
        assert "replaces" not in ingredient["required"] and "replaces" not in item["properties"]
        plain = revision_schema("en", names=["Eggs"])["properties"]["meal"]["properties"]["menu"]["items"]
        assert "replaces" not in plain["properties"]["ingredients"]["items"]["properties"]

    # The reviser's names are the fridge's first, then the draft's own and water, one spelling each
    def test_reviser_names(self):
        draft = _meal({"name": "eggs", "amount": 2, "unit": "pcs"}, {"name": "Salmon", "amount": 50, "unit": "g"})
        draft["menu"].append({"name": "Hot water", "amount": 1, "unit": "glass", "ingredients": []})
        assert reviser_names(draft, [{"name": "Eggs"}, {"name": "Feta"}]) == ["Eggs", "Feta", "Salmon", "Hot water", "Water"]
        assert reviser_names({"menu": []}, [{"name": "Su"}], "tr") == ["Su"]
        assert reviser_names({"menu": []}, [{"name": "Yumurta"}], "tr") == ["Yumurta", "Su"]


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class TestPipelineOrchestrator:
    # The final meal gets one icon from the app's list on the server, so every device shows the same one
    async def test_final_meal_gets_an_emoji(self):
        from models.meal import BREAKFAST_EMOJIS
        events, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)))
        assert extract_json_block(_final(events))["emoji"] in BREAKFAST_EMOJIS
        assert all("emoji" not in c["message"] for c in calls)

    # A meal that already has an icon keeps it
    async def test_meal_keeps_its_emoji(self):
        from models.meal import with_emoji
        assert with_emoji({"menu_name": "Eggs", "emoji": "🥯"})["emoji"] == "🥯"
        assert with_emoji({"menu_name": "Eggs", "emoji": ""})["emoji"]

    # The events come in order: drafting, the draft, analyzing, the review, finalizing, then the text
    async def test_event_order(self):
        events, _ = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS), ["Bigger portion"]))
        kinds = [e.get("step", e["type"]) for e in events]
        assert kinds == ["drafting", "draft", "analyzing", "review", "finalizing", "token", "done"]
        assert [e["content"] for e in events if e["type"] == "review"] == ["- Bigger portion"]

    # The reply is the present step's text, then the revised meal in a json block
    async def test_reply_is_text_then_revised_meal(self):
        bigger = _meal({"name": "eggs", "amount": 3, "unit": "pcs"})
        events, _ = await _run(_draft(_meal(EGGS)), _revision(bigger))
        final = _final(events)
        assert final.startswith("A warm start.\n\n```json\n")
        assert extract_json_block(final)["menu"][0]["ingredients"][0]["amount"] == 3

    # The reviser gets the draft's meal as JSON and what code found in it: fridge misses, avoid hits and units
    async def test_reviser_gets_draft_meal_and_code_check(self):
        draft = _meal(
            EGGS, {"name": "Salt", "amount": 1, "unit": "pinch"},
            {"name": "Shellfish", "amount": 50, "unit": "g"}, {"name": "eggs", "amount": 1, "unit": "cup"},
        )
        events, calls = await _run(_draft(draft), _revision(_meal(EGGS)))
        reviser = [c for c in calls if c["kind"] == "json"][1]
        assert reviser["message"].startswith('Draft menu:\n```json\n{\n  "menu"')
        assert "- Not in the fridge: Salt, Shellfish" in reviser["message"]
        assert "- On the avoid list: Shellfish" in reviser["message"]
        assert "- Units the app can't show: cup" in reviser["message"]
        names = ["eggs", "Salt", "Shellfish", "Water"]
        assert reviser["schema"] == revision_schema("en", names=names, missing=["Salt", "Shellfish"])
        review = next(e["content"] for e in events if e["type"] == "review")
        assert review.startswith("- CODE CHECK: Not in the fridge: Salt, Shellfish")

    # After a chat the block ends the draft's and the reviser's messages, and the review lists the asks first
    async def test_chat_reaches_the_draft_and_the_reviser(self):
        block = "THE CHAT SO FAR\n\n- User (latest message): I only have 10 minutes."
        asks = [{"from": [2, 4], "ask": "Simit is fine again"}, {"from": [], "ask": "Ready in 10 minutes"}, {"from": [3], "ask": " "}]
        revision = json.dumps({"chat_asks": asks, "changes": ["Shorter prep"], "meal": _meal(EGGS)})
        events, calls = await _run(_draft(_meal(EGGS)), revision, chat_block=block)
        draft, reviser, present = calls
        assert draft["message"] == f"Suggest\n\n{block}"
        assert reviser["message"].endswith(f"Code check:\n- Nothing found.\n\n{block}")
        assert reviser["schema"] == revision_schema("en", chat=True, names=["eggs", "Water"]) and CHAT_STEP in reviser["system"]
        assert "THE CHAT SO FAR" not in present["message"] + present["system"]
        review = next(e["content"] for e in events if e["type"] == "review")
        assert review == "- CHAT ASKS: Simit is fine again (from #2, #4)\n- CHAT ASKS: Ready in 10 minutes\n- Shorter prep"

        _, fresh = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)))
        assert fresh[0]["message"] == "Suggest" and CHAT_STEP not in fresh[1]["system"]

    # A clean draft tells the reviser that code found nothing
    async def test_code_check_silent_when_clean(self):
        events, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)))
        assert [c for c in calls if c["kind"] == "json"][1]["message"].endswith("Code check:\n- Nothing found.")
        assert next(e["content"] for e in events if e["type"] == "review") == "- No changes."

    # The revised meal reaches the app's format: a dish loses its servings, a simple item keeps its method
    # (how it's readied, #156), and empty methods and prep words are left out
    async def test_revised_meal_is_cleaned(self):
        revised = _meal({"name": "eggs", "amount": 2, "unit": "pcs", "prep": ""})
        revised["menu"][0].update({"amount": 1, "unit": "pcs", "method": "Boil for 8 minutes"})
        revised["menu"].append({"ingredients": [], "name": "eggs", "method": "Fry in the pan", "amount": 1, "unit": "pcs"})
        revised["menu"].append({"ingredients": [], "name": "eggs", "method": " ", "amount": 1, "unit": "pcs"})
        events, _ = await _run(_draft(_meal(EGGS)), _revision(revised))
        dish, readied, served = extract_json_block(_final(events))["menu"]
        assert dish == {"name": "Boiled eggs", "ingredients": [{"name": "eggs", "amount": 2, "unit": "pcs"}],
                        "method": "Boil for 8 minutes"}
        assert readied == {"ingredients": [], "name": "eggs", "method": "Fry in the pan", "amount": 1, "unit": "pcs"}
        assert served == {"ingredients": [], "name": "eggs", "amount": 1, "unit": "pcs"}

    # A swap's mark stays only when it's true (#148): feta stands in for the missing salmon. A mark naming an item the
    # draft had in the fridge, one on an ingredient the fridge lacks, one whose item is still in the dish, and an
    # empty one are dropped
    async def test_only_true_swaps_keep_their_mark(self):
        context = {**SAMPLE_CONTEXT, "ingredients": [{"name": "eggs"}, {"name": "Feta"}, {"name": "Milk"}]}
        draft = _meal(EGGS, {"name": "Salmon", "amount": 50, "unit": "g"}, {"name": "Chives", "amount": 1, "unit": "tbsp"})
        def g(name, **extra):
            return {"name": name, "amount": 50, "unit": "g", **extra}
        revised = _meal(
            g("eggs", replaces=" "), g("Feta", replaces="salmon"), g("Milk", replaces="eggs"),
            g("Quark", replaces="Salmon"), g("Chives"), g("Feta", replaces="Chives"),
        )
        events, _ = await _run(_draft(draft), _revision(revised), context=context)
        ingredients = extract_json_block(_final(events))["menu"][0]["ingredients"]
        assert [i.get("replaces") for i in ingredients] == [None, "salmon", None, None, None, None]
        assert "replaces" not in ingredients[0]

    # A "dish" made of one item named as itself (Banana: Banana) is that item on its own, and keeps its method
    async def test_self_named_dish_becomes_a_simple_item(self):
        revised = _meal(EGGS)
        revised["menu"].append({
            "ingredients": [{"name": "Bananas", "amount": 100, "unit": "g"}],
            "name": "Banana", "method": "Peel and slice", "amount": 1, "unit": "pcs",
        })
        context = {**SAMPLE_CONTEXT, "ingredients": [{"name": "eggs"}, {"name": "Bananas"}]}
        events, _ = await _run(_draft(_meal(EGGS)), _revision(revised), context=context)
        banana = extract_json_block(_final(events))["menu"][1]
        assert banana == {"ingredients": [], "name": "Banana", "method": "Peel and slice", "amount": 100, "unit": "g"}

    # A revised meal with more fridge or unit problems than the draft loses to the draft's meal
    async def test_falls_back_to_draft_when_revision_is_worse(self):
        worse = _meal({"name": "Poached eggs", "amount": 2, "unit": "pcs"})
        events, _ = await _run(_draft(_meal(EGGS)), _revision(worse))
        assert _without_emoji(extract_json_block(_final(events))) == _meal(EGGS)

    # A revised meal with a new avoid-list item loses to the draft, even when the draft has more fridge misses
    async def test_falls_back_to_draft_when_revision_adds_an_avoided_item(self):
        draft = _meal({"name": "Toast", "amount": 1, "unit": "pcs"}, {"name": "Jam", "amount": 1, "unit": "tbsp"})
        allergen = _meal({"name": "Shellfish", "amount": 100, "unit": "g"})
        events, _ = await _run(_draft(draft), _revision(allergen))
        assert _without_emoji(extract_json_block(_final(events))) == draft

    # A revision that can't be read, or a reviser that fails, leaves the draft's meal
    async def test_unreadable_or_failed_revision_keeps_draft_meal(self):
        from services.llm import LLMUnavailableError
        for revision in ("not json", json.dumps({"changes": []}), LLMUnavailableError("down")):
            events, _ = await _run(_draft(_meal(EGGS)), revision)
            assert _without_emoji(extract_json_block(_final(events))) == _meal(EGGS)

    # The present step reads only the final meal, not the draft's text, and the mode's temperature
    async def test_present_reads_only_the_final_meal(self):
        events, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), temperature=0.9)
        present = next(c for c in calls if c["kind"] == "stream")
        assert present["system"] and present["system"] != calls[0]["system"]
        assert present["message"].startswith("Today's menu:\n```json\n")
        assert "Enjoy!" not in present["message"]
        assert present["temperature"] == 0.9

    # When the present step fails, code writes the text from the menu name and description
    async def test_code_text_when_present_fails(self):
        events, _ = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), present=RuntimeError("down"))
        assert _final(events).startswith("**Eggs**\n\nWarm eggs.\n\n```json\n")

    # A fenced block in the present step's text is dropped, so the meal is the reply's only json block
    async def test_present_text_keeps_no_code_block(self):
        other = 'Enjoy!\n```json\n{"menu": []}\n```'
        events, _ = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), present=other)
        final = _final(events)
        assert final.startswith("Enjoy!\n\n```json\n")
        assert _without_emoji(extract_json_block(final)) == _meal(EGGS)

    # The draft is a structured call: its text first, then the meal in the reviser's shape without a method
    async def test_draft_is_called_with_its_schema(self):
        events, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), temperature=0.9)
        draft = calls[0]
        assert draft["kind"] == "json" and draft["temperature"] == 0.9
        assert list(draft["schema"]["properties"]) == draft["schema"]["required"] == ["text", "meal"]
        meal, revised = draft["schema"]["properties"]["meal"], revision_schema("en")["properties"]["meal"]
        item = meal["properties"]["menu"]["items"]
        assert list(item["properties"]) == item["required"] == ["ingredients", "name", "amount", "unit"]
        revised_item = revised["properties"]["menu"]["items"]
        assert {k: v for k, v in revised_item["properties"].items() if k != "method"} == item["properties"]
        assert {k: v for k, v in revised["properties"].items() if k != "menu"} == {k: v for k, v in meal["properties"].items() if k != "menu"}
        assert next(e["content"] for e in events if e["type"] == "draft").startswith("Enjoy!\n\n```json\n")

    # The draft's meal reaches the reviser in the app's format: a dish loses its servings, a one-item dish named as itself is a simple item
    async def test_draft_meal_is_cleaned_for_the_reviser(self):
        drafted = _meal({**EGGS, "prep": " "})
        drafted["menu"][0].update(amount=1, unit="pcs")
        drafted["menu"].append({"ingredients": [EGGS], "name": "eggs", "amount": 1, "unit": "pcs"})
        _, calls = await _run(_draft(drafted), _revision(_meal(EGGS)))
        sent = extract_json_block(calls[1]["message"])
        assert sent["menu"] == [
            {"name": "Boiled eggs", "ingredients": [EGGS]},
            {"ingredients": [], "name": "eggs", "amount": 2, "unit": "pcs"},
        ]

    # An empty menu is the fridge-too-small note: its text is sent as it is, without a review and with no meal block
    async def test_empty_menu_sends_the_note(self):
        note = "Your fridge has only tea and salt. Add a few items in the Fridge tab."
        events, calls = await _run(_draft({**_meal(EGGS), "menu": []}, text=note), _revision(_meal(EGGS)))
        assert _final(events) == note and extract_json_block(note) is None
        assert [c["kind"] for c in calls] == ["json"]
        assert next(e["content"] for e in events if e["type"] == "review") == "- No meal in the draft, so nothing to revise."

    # An empty menu without a note gets code's low-ingredients text in the reply language, not the retry text
    async def test_empty_menu_without_a_note_says_ingredients_are_low(self):
        empty = _draft({**_meal(EGGS), "menu": []}, text=" ")
        events, calls = await _run(empty, _revision(_meal(EGGS)))
        assert _final(events) == LOW_INGREDIENT_TEXTS["en"] and len(calls) == 1
        events, _ = await _run(empty, _revision(_meal(EGGS)), context={**SAMPLE_CONTEXT, "language": "tr"})
        assert _final(events) == LOW_INGREDIENT_TEXTS["tr"]

    # A draft reply that can't be read ends with the retry text in the reply language, with no meal block
    async def test_unreadable_draft_gets_the_retry_text(self):
        for reply in ('{"text": "Enjoy!", "meal": {"menu": [', "[]", '{"text": "Enjoy!", "meal": {"menu": "eggs"}}'):
            events, calls = await _run(reply, _revision(_meal(EGGS)))
            assert _final(events) == RETRY_TEXTS["en"] and len(calls) == 1
            assert next(e["content"] for e in events if e["type"] == "draft") == reply
        events, _ = await _run("not json", _revision(_meal(EGGS)), context={**SAMPLE_CONTEXT, "language": "tr"})
        assert _final(events) == RETRY_TEXTS["tr"]

    # The draft runs at the mode's temperature with the mode block, and the reviser cool with the mode line
    async def test_passes_temperature_and_mode(self):
        _, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), mode="explore", temperature=0.9)
        draft, reviser = calls[0], calls[1]
        assert draft["temperature"] == 0.9 and "EXPLORE" in draft["system"]
        assert reviser["temperature"] == 0.3
        _, plain_calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), temperature=0.9)
        assert reviser["system"] != plain_calls[1]["system"]  # the mode reaches the reviser

    # The draft and the reply text run on the suggestion model and the review on the reviser's, for the reply
    # language, so a model per task or language can serve them (#192)
    async def test_calls_name_their_task_and_language(self):
        _, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), context={**SAMPLE_CONTEXT, "language": "tr"})
        assert [c["route"] for c in calls] == [
            {"task": "suggestion", "language": "tr"}, {"task": "review", "language": "tr"},
            {"task": "suggestion", "language": "tr"},
        ]

    # Favorites mode's draft prompt lists the context's saved meals, staples and ratings
    async def test_favorites_mode_gets_taste_hints(self):
        context = {
            **SAMPLE_CONTEXT,
            "favorite_meals": [{"meal_name": "Egg toast", "ingredients": '["eggs"]'}],
            "favorites": ["eggs"],
            "ratings": [{"product_name": "eggs", "rating": 9}],
        }
        _, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), context=context, mode="favorites")
        system = calls[0]["system"]
        assert "- Egg toast: eggs" in system  # the saved meal with its items
        _, plain = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), context=context)
        assert "Egg toast" not in plain[0]["system"]  # only favorites mode lists them
        assert len(system) > len(plain[0]["system"])

    # Pipeline propagates LLMUnavailableError from the draft step
    async def test_propagates_llm_error(self):
        from services.llm import LLMUnavailableError
        with pytest.raises(LLMUnavailableError):
            await _run(LLMUnavailableError("Ollama down"), _revision(_meal(EGGS)))
