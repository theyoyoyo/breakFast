"""
Tests for the 3-step suggestion pipeline (draft → revise → present).
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from services.suggestion import build_pipeline_analyst_prompt
from services.pipeline import revision_schema, run_suggestion_pipeline
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


def _draft(meal: dict) -> str:
    return f"Enjoy!\n```json\n{json.dumps(meal)}\n```"


def _revision(meal, changes=()) -> str:
    return json.dumps({"changes": list(changes), "meal": meal})


async def _run(draft, revision, present="A warm start.", context=SAMPLE_CONTEXT, mode=None, temperature=0.6):
    """Run the pipeline on canned replies (an Exception raises instead); returns the events and every model call."""
    calls = []

    async def fake_stream(system_prompt, history, message, temperature=None):
        streamed = [c for c in calls if c["kind"] == "stream"]
        calls.append({"kind": "stream", "system": system_prompt, "message": message, "temperature": temperature})
        text = draft if not streamed else present
        if isinstance(text, Exception):
            raise text
        for char in text:
            yield char

    async def fake_chat_json(system_prompt, messages, schema, temperature=None):
        calls.append({
            "kind": "json", "system": system_prompt, "message": messages[0]["content"],
            "temperature": temperature, "schema": schema,
        })
        if isinstance(revision, Exception):
            raise revision
        return revision

    with patch("services.pipeline.stream_response", fake_stream), patch("services.pipeline.chat_json", fake_chat_json):
        events = [
            e async for e in run_suggestion_pipeline(
                context=context, user_message="Suggest", mode=mode, temperature=temperature,
            )
        ]
    return events, calls


def _final(events) -> str:
    """The text the user gets: sent as tokens, then done, the same."""
    done = next(e["content"] for e in events if e["type"] == "done")
    assert "".join(e["content"] for e in events if e["type"] == "token") == done
    return done


# ---------------------------------------------------------------------------
# Reviser prompt and schema
# ---------------------------------------------------------------------------

class TestReviserPrompt:
    # The reviser is an internal step that returns the fixed meal, in the user's language
    def test_identity_and_language(self):
        prompt = build_pipeline_analyst_prompt(recent_meal_history=[])
        assert "meal reviser, an internal step the user never sees" in prompt
        assert "Always respond in English." in prompt
        assert "Always respond in Turkish." in build_pipeline_analyst_prompt([], language="tr")

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
        assert "NEVER use these ingredients: Almonds" in prompt
        assert "Dislikes: Tomatoes" in prompt
        assert "Dislikes: none" in build_pipeline_analyst_prompt([])

    # The Suggest mode tells it what to keep: a favorite stays familiar without a fixed recipe, explore stays new
    def test_mode_line(self):
        assert "A saved meal is a hint, not a fixed recipe." in build_pipeline_analyst_prompt([], mode="favorites")
        assert "keep what makes this menu new to them" in build_pipeline_analyst_prompt([], mode="explore")
        assert "The user asked for a breakfast suggestion." in build_pipeline_analyst_prompt([])

    # It fixes what code found and answers narrow questions whose usual answer is no change
    def test_fixes_code_problems_then_narrow_questions(self):
        prompt = build_pipeline_analyst_prompt([], ingredient_inventory=[{"name": "Yumurta"}])
        assert "Yumurta" in prompt
        assert 'Fix every problem listed under "Code check"' in prompt
        assert "When none fits, keep it: the app marks it" in prompt
        assert "The answer is usually no" in prompt
        assert "three changes at most" in prompt
        assert "water" not in prompt.lower()

    # Units come from the reply language's list, with the fixed spoon and glass sizes
    def test_units_follow_the_language(self):
        assert "tsp, dsp, tbsp" in build_pipeline_analyst_prompt([])
        assert "tsp, dsp, tbsp" not in build_pipeline_analyst_prompt([], language="tr")


class TestRevisionSchema:
    # The changes come before the meal, the menu before its name, and a dish's ingredients before its name
    def test_order_puts_contents_before_names(self):
        schema = revision_schema("en")
        assert list(schema["properties"]) == ["changes", "meal"]
        meal = schema["properties"]["meal"]
        assert list(meal["properties"])[0] == "menu"
        item = meal["properties"]["menu"]["items"]
        assert list(item["properties"])[:2] == ["ingredients", "name"]

    # Amounts are numbers and units come from the language's list; a dish's own amount and unit may be null
    def test_amounts_and_units(self):
        item = revision_schema("en")["properties"]["meal"]["properties"]["menu"]["items"]
        ingredient = item["properties"]["ingredients"]["items"]
        assert ingredient["properties"]["amount"] == {"type": "number"}
        assert "tbsp" in ingredient["properties"]["unit"]["enum"]
        assert item["properties"]["amount"]["type"] == ["number", "null"]
        assert None in item["properties"]["unit"]["enum"]
        tr_unit = revision_schema("tr")["properties"]["meal"]["properties"]["menu"]["items"]
        assert "tbsp" not in tr_unit["properties"]["ingredients"]["items"]["properties"]["unit"]["enum"]


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class TestPipelineOrchestrator:
    # The events come in order: drafting, the draft, analyzing, the review, finalizing, then the text
    @pytest.mark.asyncio
    async def test_event_order(self):
        events, _ = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS), ["Bigger portion"]))
        kinds = [e.get("step", e["type"]) for e in events]
        assert kinds == ["drafting", "draft", "analyzing", "review", "finalizing", "token", "done"]
        assert [e["content"] for e in events if e["type"] == "review"] == ["- Bigger portion"]

    # The reply is the present step's text, then the revised meal in a json block
    @pytest.mark.asyncio
    async def test_reply_is_text_then_revised_meal(self):
        bigger = _meal({"name": "eggs", "amount": 3, "unit": "pcs"})
        events, _ = await _run(_draft(_meal(EGGS)), _revision(bigger))
        final = _final(events)
        assert final.startswith("A warm start.\n\n```json\n")
        assert extract_json_block(final)["menu"][0]["ingredients"][0]["amount"] == 3

    # The reviser gets the draft's meal as JSON and what code found in it: fridge misses, avoid hits and units
    @pytest.mark.asyncio
    async def test_reviser_gets_draft_meal_and_code_check(self):
        draft = _meal(
            EGGS, {"name": "Salt", "amount": 1, "unit": "pinch"},
            {"name": "Shellfish", "amount": 50, "unit": "g"}, {"name": "eggs", "amount": 1, "unit": "cup"},
        )
        events, calls = await _run(_draft(draft), _revision(_meal(EGGS)))
        reviser = next(c for c in calls if c["kind"] == "json")
        assert reviser["message"].startswith('Draft menu:\n```json\n{\n  "menu"')
        assert "- Not in the fridge: Salt, Shellfish" in reviser["message"]
        assert "- On the avoid list: Shellfish" in reviser["message"]
        assert "- Units the app can't show: cup" in reviser["message"]
        assert reviser["schema"] == revision_schema("en")
        review = next(e["content"] for e in events if e["type"] == "review")
        assert review.startswith("- CODE CHECK: Not in the fridge: Salt, Shellfish")

    # A clean draft tells the reviser that code found nothing
    @pytest.mark.asyncio
    async def test_code_check_silent_when_clean(self):
        events, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)))
        assert next(c for c in calls if c["kind"] == "json")["message"].endswith("Code check:\n- Nothing found.")
        assert next(e["content"] for e in events if e["type"] == "review") == "- No changes."

    # The revised meal reaches the app's format: a dish loses its null amount and unit, a simple item its method
    @pytest.mark.asyncio
    async def test_revised_meal_is_cleaned(self):
        revised = _meal({"name": "eggs", "amount": 2, "unit": "pcs", "prep": ""})
        revised["menu"][0].update({"amount": None, "unit": None, "method": "Boil for 8 minutes"})
        revised["menu"].append({"ingredients": [], "name": "eggs", "method": "Serve", "amount": 1, "unit": "pcs"})
        events, _ = await _run(_draft(_meal(EGGS)), _revision(revised))
        dish, simple = extract_json_block(_final(events))["menu"]
        assert dish == {"name": "Boiled eggs", "ingredients": [{"name": "eggs", "amount": 2, "unit": "pcs"}],
                        "method": "Boil for 8 minutes"}
        assert simple == {"ingredients": [], "name": "eggs", "amount": 1, "unit": "pcs"}

    # A revised meal with more fridge or unit problems than the draft loses to the draft's meal
    @pytest.mark.asyncio
    async def test_falls_back_to_draft_when_revision_is_worse(self):
        worse = _meal({"name": "Poached eggs", "amount": 2, "unit": "pcs"})
        events, _ = await _run(_draft(_meal(EGGS)), _revision(worse))
        assert extract_json_block(_final(events)) == _meal(EGGS)

    # A revised meal with a new avoid-list item loses to the draft, even when the draft has more fridge misses
    @pytest.mark.asyncio
    async def test_falls_back_to_draft_when_revision_adds_an_avoided_item(self):
        draft = _meal({"name": "Toast", "amount": 1, "unit": "pcs"}, {"name": "Jam", "amount": 1, "unit": "tbsp"})
        allergen = _meal({"name": "Shellfish", "amount": 100, "unit": "g"})
        events, _ = await _run(_draft(draft), _revision(allergen))
        assert extract_json_block(_final(events)) == draft

    # A revision that can't be read, or a reviser that fails, leaves the draft's meal
    @pytest.mark.asyncio
    async def test_unreadable_or_failed_revision_keeps_draft_meal(self):
        from services.llm import LLMUnavailableError
        for revision in ("not json", json.dumps({"changes": []}), LLMUnavailableError("down")):
            events, _ = await _run(_draft(_meal(EGGS)), revision)
            assert extract_json_block(_final(events)) == _meal(EGGS)

    # The present step reads only the final meal, not the draft's text, and the mode's temperature
    @pytest.mark.asyncio
    async def test_present_reads_only_the_final_meal(self):
        events, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), temperature=0.9)
        present = [c for c in calls if c["kind"] == "stream"][1]
        assert "Introduce it in a few short lines" in present["system"]
        assert present["message"].startswith("Today's menu:\n```json\n")
        assert "Enjoy!" not in present["message"]
        assert present["temperature"] == 0.9

    # When the present step fails, code writes the text from the menu name and description
    @pytest.mark.asyncio
    async def test_code_text_when_present_fails(self):
        events, _ = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), present=RuntimeError("down"))
        assert _final(events).startswith("**Eggs**\n\nWarm eggs.\n\n```json\n")

    # A fenced block in the present step's text is dropped, so the meal is the reply's only json block
    @pytest.mark.asyncio
    async def test_present_text_keeps_no_code_block(self):
        other = 'Enjoy!\n```json\n{"menu": []}\n```'
        events, _ = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), present=other)
        final = _final(events)
        assert final.startswith("Enjoy!\n\n```json\n")
        assert extract_json_block(final) == _meal(EGGS)

    # A draft with no meal block is a note to the user, sent as it is without a review
    @pytest.mark.asyncio
    async def test_note_without_meal_is_sent_as_is(self):
        events, calls = await _run("Your fridge is nearly empty.", _revision(_meal(EGGS)))
        assert _final(events) == "Your fridge is nearly empty."
        assert [c["kind"] for c in calls] == ["stream"]

    # A draft whose meal block can't be read goes to the reviser as text, and its meal is used
    @pytest.mark.asyncio
    async def test_broken_draft_meal_is_rebuilt_by_the_reviser(self):
        events, calls = await _run("Enjoy!\n```json\n{\"menu\": [\n```", _revision(_meal(EGGS)))
        assert "its meal block couldn't be read" in next(c for c in calls if c["kind"] == "json")["message"]
        assert extract_json_block(_final(events)) == _meal(EGGS)

    # A draft meal with fractions ("amount": 1/2) reaches the user with decimals, so the chat can read it again
    @pytest.mark.asyncio
    async def test_draft_fractions_become_decimals(self):
        halves = "Enjoy!\n```json\n" + json.dumps(_meal(EGGS)).replace('"amount": 2', '"amount": 1/2') + "\n```"
        events, _ = await _run(halves, "not json")
        assert extract_json_block(_final(events))["menu"][0]["ingredients"][0]["amount"] == 0.5

    # The draft runs at the mode's temperature with the mode block, and the reviser cool with the mode line
    @pytest.mark.asyncio
    async def test_passes_temperature_and_mode(self):
        _, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), mode="explore", temperature=0.9)
        draft, reviser = calls[0], calls[1]
        assert draft["temperature"] == 0.9 and "EXPLORE" in draft["system"]
        assert reviser["temperature"] == 0.3 and "keep what makes this menu new to them" in reviser["system"]

    # Favorites mode's draft prompt lists the context's saved meals, staples and ratings
    @pytest.mark.asyncio
    async def test_favorites_mode_gets_taste_hints(self):
        context = {
            **SAMPLE_CONTEXT,
            "favorite_meals": [{"meal_name": "Egg toast", "ingredients": '["eggs"]'}],
            "favorites": ["eggs"],
            "ratings": [{"product_name": "eggs", "rating": 9}],
        }
        _, calls = await _run(_draft(_meal(EGGS)), _revision(_meal(EGGS)), context=context, mode="favorites")
        assert "- Egg toast: eggs" in calls[0]["system"]
        assert "Their favorite ingredients: eggs" in calls[0]["system"]
        assert "High-rated (favour these): eggs" in calls[0]["system"]

    # Pipeline propagates LLMUnavailableError from the draft step
    @pytest.mark.asyncio
    async def test_propagates_llm_error(self):
        from services.llm import LLMUnavailableError
        with pytest.raises(LLMUnavailableError):
            await _run(LLMUnavailableError("Ollama down"), _revision(_meal(EGGS)))
