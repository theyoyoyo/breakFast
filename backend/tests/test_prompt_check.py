"""Tests for the prompt test's reply checks, runner and summary, offline with canned replies."""

import json
from unittest.mock import patch

from tools.prompt_check import check_reply, describe, is_clean, suggest_once, summarize
from tools.prompt_samples import SAMPLES

EN, TR = SAMPLES["en"], SAMPLES["tr"]


def _reply(*menu) -> str:
    return "Enjoy!\n```json\n" + json.dumps({"menu_name": "Test", "menu": list(menu)}) + "\n```"


# A meal built only from fridge items (water needs none), in listed units, is clean
def test_clean_reply():
    text = _reply(
        {"name": "Menemen", "ingredients": [
            {"name": "Eggs", "amount": 2, "unit": "pcs"},
            {"name": "Tomatoes", "amount": 1, "unit": "pcs"},
            {"name": "Olive oil", "amount": 1, "unit": "tbsp"},
        ]},
        {"name": "White cheese", "amount": 50, "unit": "g", "ingredients": []},
        {"name": "Water", "amount": 1, "unit": "glass", "ingredients": []},
    )
    result = check_reply(text, EN)
    assert is_clean(result)
    assert describe(result) == "clean"


# A reply without a meal JSON block fails the JSON check
def test_no_meal_json():
    result = check_reply("Here is a lovely breakfast idea.", EN)
    assert result["json"] is False
    assert not is_clean(result)
    assert describe(result) == "no meal JSON"


# An ingredient outside the fridge is reported as missing
def test_missing_ingredient():
    text = _reply({"name": "Avocado toast", "ingredients": [
        {"name": "Bread", "amount": 1, "unit": "slice"},
        {"name": "Avocado", "amount": 1, "unit": "pcs"},
    ]})
    assert check_reply(text, EN)["missing"] == ["Avocado"]


# A prepared item served as one simple item passes the fridge check but is caught here (#115)
def test_prepared_item_caught():
    text = _reply({"name": "Simit with tahini dipping sauce", "amount": 1, "unit": "pcs", "ingredients": []})
    result = check_reply(text, EN)
    assert result["missing"] == []
    assert result["prepared"] == ["Simit with tahini dipping sauce"]
    assert describe(result) == "prepared: Simit with tahini dipping sauce"


# A simple item missing from the fridge counts once, as missing; a shorter fridge name is fine
def test_simple_item_counted_once_and_shorter_names_pass():
    text = _reply(
        {"name": "Avokado", "amount": 1, "unit": "adet", "ingredients": []},
        {"name": "Peynir", "amount": 50, "unit": "g", "ingredients": []},
    )
    result = check_reply(text, TR)
    assert result["missing"] == ["Avokado"]
    assert result["prepared"] == []


# Units outside the reply language's list are reported once each, ignoring case
def test_off_list_units():
    text = _reply(
        {"name": "Menemen", "ingredients": [
            {"name": "Yumurta", "amount": 2, "unit": "adet"},
            {"name": "Süt", "amount": 1, "unit": "cup"},
        ]},
        {"name": "Beyaz peynir", "amount": 50, "unit": "gr", "ingredients": []},
        {"name": "Siyah zeytin", "amount": 10, "unit": "gr", "ingredients": []},
        {"name": "Süt", "amount": 0.2, "unit": "l", "ingredients": []},
    )
    assert check_reply(text, TR)["units"] == ["cup", "gr"]


# One run returns the draft and the final reply; draft-only closes the pipeline before the review
async def test_suggest_once_collects_draft_and_final():
    calls = []

    async def fake_pipeline(context, user_message, mode=None, temperature=None, chat_context=None):
        calls.append((user_message, temperature))
        yield {"type": "progress", "step": "drafting"}
        yield {"type": "draft", "content": "D"}
        calls.append("reviewed")
        yield {"type": "done", "content": "F"}

    with patch("tools.prompt_check.run_suggestion_pipeline", fake_pipeline):
        assert await suggest_once(EN, "explore", draft_only=False) == {"draft": "D", "final": "F"}
        assert await suggest_once(EN, None, draft_only=True) == {"draft": "D"}
    assert calls == [
        ("Suggest a different breakfast from world cuisines", 0.9),
        "reviewed",
        ("Suggest Breakfast", None),
    ]


# Every sample runs through the real pipeline with a fake model, so it has all the context the prompts read
async def test_samples_run_through_the_pipeline():
    async def fake_stream(system_prompt, history, message, temperature=None):
        yield "ok"

    with patch("services.pipeline.stream_response", fake_stream):
        for sample in SAMPLES.values():
            assert await suggest_once(sample, None, draft_only=False) == {"draft": "ok", "final": "ok"}


# The summary counts replies per sample and stage, then lists the most frequent offenders
def test_summary_counts_and_offenders():
    clean = {"json": True, "missing": [], "prepared": [], "units": []}
    simit = {"json": True, "missing": [], "prepared": ["Simit with tahini"], "units": []}
    records = [
        {"sample": "en", "run": 1, "seconds": 30, "error": None, "replies": {}, "scores": {"draft": simit, "final": clean}},
        {"sample": "en", "run": 2, "seconds": 50, "error": None, "replies": {}, "scores": {"draft": simit, "final": simit}},
    ]
    lines = summarize(records).splitlines()
    assert lines[1].split() == ["en", "draft", "2", "2", "0", "0", "2", "0", "0", "40"]
    assert lines[2].split() == ["en", "final", "2", "2", "1", "0", "1", "0", "0", "40"]
    assert "en draft prepared: Simit with tahini ×2" in lines
