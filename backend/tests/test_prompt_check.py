"""Tests for the prompt test's reply checks, runner, summary and history, offline with canned replies."""

import json
from unittest.mock import patch

from services import pipeline
from tools.prompt_check import (
    check_reply, compare, describe, is_clean, recording_prompts, score_shopping, shop_once, suggest_once,
    summarize,
)
from tools.prompt_samples import SAMPLES

EN, TR = SAMPLES["en"], SAMPLES["tr"]


def _reply(*menu) -> str:
    return "Enjoy!\n```json\n" + json.dumps({"menu_name": "Test", "menu": list(menu)}, ensure_ascii=False) + "\n```"


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
    assert result["dishes"] == ["menemen", "water", "white cheese"]


# A reply without a meal JSON block fails the JSON check
def test_no_meal_json():
    result = check_reply("Here is a lovely breakfast idea.", EN)
    assert result["json"] is False
    assert not is_clean(result)
    assert describe(result) == "no JSON"


# An ingredient outside the fridge is reported as missing
def test_missing_ingredient():
    text = _reply({"name": "Avocado toast", "ingredients": [
        {"name": "Bread", "amount": 1, "unit": "slice"},
        {"name": "Avocado", "amount": 1, "unit": "pcs"},
    ]})
    assert check_reply(text, EN)["issues"]["missing"] == ["Avocado"]


# Flagged names that contain a fridge item count as renamed, not missing: prepared, combined or translated items
def test_renamed_items_told_from_missing_ones():
    text = _reply(
        {"name": "Simit with tahini dipping sauce", "amount": 1, "unit": "pcs", "ingredients": []},
        {"name": "Plate", "ingredients": [
            {"name": "White cheese (peynir)", "amount": 50, "unit": "g"},
            {"name": "Yogurt or milk", "amount": 100, "unit": "ml"},
            {"name": "Avocado", "amount": 1, "unit": "pcs"},
        ]},
    )
    issues = check_reply(text, EN)["issues"]
    assert issues["renamed"] == ["Simit with tahini dipping sauce", "White cheese (peynir)", "Yogurt or milk"]
    assert issues["missing"] == ["Avocado"]
    assert describe(check_reply(text, EN)) == (
        "missing: Avocado; renamed: Simit with tahini dipping sauce, White cheese (peynir), Yogurt or milk"
    )


# A name shorter than its fridge name is that item
def test_shorter_names_pass():
    text = _reply({"name": "Peynir", "amount": 50, "unit": "g", "ingredients": []})
    assert is_clean(check_reply(text, TR))


# Units the app can't show as a listed unit are reported once each; known spellings (gr, pieces) pass
def test_off_list_units():
    text = _reply(
        {"name": "Menemen", "ingredients": [
            {"name": "Yumurta", "amount": 2, "unit": "adet"},
            {"name": "Süt", "amount": 1, "unit": "cup"},
        ]},
        {"name": "Beyaz peynir", "amount": 50, "unit": "gr", "ingredients": []},
        {"name": "Siyah zeytin", "amount": 10, "unit": "scoop", "ingredients": []},
        {"name": "Süt", "amount": 0.2, "unit": "l", "ingredients": []},
    )
    assert check_reply(text, TR)["issues"]["units"] == ["cup", "scoop"]
    pieces = _reply({"name": "Simit", "amount": 1, "unit": "pieces", "ingredients": []})
    assert check_reply(pieces, EN)["issues"]["units"] == []


# An English reply's words with Turkish letters are reported unless they name a fridge item or the country;
# Turkish replies aren't checked
def test_turkish_words_in_english_reply():
    text = _reply({"name": "Kaşarlı tost", "amount": 1, "unit": "pcs", "ingredients": []}) + "\nKaşar in Türkiye is güzel!"
    sample = {**EN, "ingredients": EN["ingredients"] + [{"name": "Kaşar", "group_name": "🐄 Animal Products"}]}
    assert check_reply(text, sample)["issues"]["turkish"] == ["Kaşarlı", "güzel"]
    assert check_reply(text, TR)["issues"]["turkish"] == []


# One run returns the draft and the final reply; draft-only closes the pipeline before the review
async def test_suggest_once_collects_draft_and_final():
    calls = []

    async def fake_pipeline(context, user_message, mode=None, temperature=None, chat_context=None):
        calls.append((user_message, temperature))
        yield {"type": "progress", "step": "drafting"}
        yield {"type": "draft", "content": "D"}
        calls.append("reviewed")
        yield {"type": "done", "content": "F"}

    with patch("services.pipeline.run_suggestion_pipeline", fake_pipeline):
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
            assert await suggest_once(sample, None, draft_only=False) == {"draft": "ok", "review": "ok", "final": "ok"}


# The recorder keeps each distinct system prompt once, in order of use, and puts the sender back
async def test_recording_prompts_keeps_distinct_system_prompts():
    async def fake_stream(system_prompt, history, message, temperature=None):
        yield "ok"

    sent = {}
    with patch("services.pipeline.stream_response", fake_stream):
        with recording_prompts(sent):
            await suggest_once(EN, None, draft_only=False)
            await suggest_once(EN, None, draft_only=False)
        assert pipeline.stream_response is fake_stream
    prompts = list(sent)
    assert len(prompts) == 2  # suggestion (draft and refine) and analyst
    assert "Append a JSON block" in prompts[0]


# The summary counts replies and distinct menus per sample and stage, then lists the most frequent offenders
def test_summary_counts_and_offenders():
    none = {"missing": [], "renamed": [], "units": [], "turkish": []}
    clean = {"json": True, "dishes": ["menemen"], "issues": none}
    simit = {"json": True, "dishes": ["simit"], "issues": {**none, "renamed": ["Simit with tahini"]}}
    records = [
        {"sample": "en", "run": 1, "seconds": 30, "error": None, "replies": {}, "scores": {"draft": simit, "final": clean}},
        {"sample": "en", "run": 2, "seconds": 50, "error": None, "replies": {}, "scores": {"draft": simit, "final": simit}},
    ]
    lines = summarize(records).splitlines()
    assert lines[1].split() == ["en", "draft", "2", "2", "0", "1", "0", "2", "0", "0", "0", "40"]
    assert lines[2].split() == ["en", "final", "2", "2", "1", "2", "0", "1", "0", "0", "0", "40"]
    assert "en draft renamed: Simit with tahini ×2" in lines


# Each sample and stage is compared with its best earlier test in the same mode
def test_compare_with_best_earlier_test():
    old = {"date": "2026-10-27 23:21", "prompt": "aaaaaaa", "mode": "plain", "note": "baseline",
           "results": {"en final": {"clean": 1, "scored": 2, "distinct": 1}}}
    best = {**old, "prompt": "bbbbbbb", "note": "", "results": {"en final": {"clean": 2, "scored": 2, "distinct": 2}}}
    explore = {**old, "mode": "explore", "results": {"en final": {"clean": 3, "scored": 3, "distinct": 3}}}
    now = {"en final": {"clean": 1, "scored": 2, "distinct": 2}, "en draft": {"clean": 0, "scored": 2, "distinct": 1}}
    assert compare(now, [old, best, explore], "plain") == [
        "en final: 1/2 clean, 2 distinct ▼ best 2/2 clean, 2 distinct: prompt bbbbbbb (2026-10-27 23:21)",
        "en draft: 0/2 clean, 1 distinct · first test",
    ]


def _shopping_reply(*names) -> str:
    return json.dumps({"items": [{"name": n, "reason": "Good"} for n in names]}, ensure_ascii=False)


# Shopping flags dishes, vague names and repeats, and Suggest More is checked against what the first reply showed
def test_shopping_checks():
    mixed = SAMPLES["mixed"]
    first = _shopping_reply("Menemen", "Leafy greens (e.g. spinach)", "Spinach", "Domates", "Süt", "Fresh basil")
    more = _shopping_reply("Spinach", "Kale", "Whole wheat toast")
    scores = score_shopping({"suggest": first, "more": more}, mixed)
    assert scores["suggest"]["issues"]["dish"] == ["Menemen"]
    assert scores["suggest"]["issues"]["vague"] == ["Leafy greens (e.g. spinach)", "Fresh basil"]
    assert scores["suggest"]["issues"]["repeat"] == ["Domates", "Süt"]  # in the fridge, on the shopping list
    assert scores["suggest"]["note"] == "2 of 6 kept"  # the endpoint also drops the dish and the vague name
    assert scores["more"]["issues"]["repeat"] == ["Spinach"]  # shown by the first reply
    assert scores["more"]["issues"]["dish"] == ["Whole wheat toast"]
    assert describe(score_shopping({"suggest": "not json"}, mixed)["suggest"]) == "no JSON"


# One shopping run asks twice, the second time with the first reply's new items as already shown
async def test_shop_once_asks_for_more_with_what_was_shown():
    requests = []

    async def fake_chat_json(system_prompt, messages, schema, temperature=None):
        requests.append(messages[0]["content"])
        return _shopping_reply("Spinach", "Domates") if len(requests) == 1 else _shopping_reply("Kale")

    sent = {}
    with patch("services.llm.chat_json", fake_chat_json):
        replies = await shop_once(SAMPLES["mixed"], sent)
    assert list(replies) == ["suggest", "more"]
    assert requests[0] == "Generate shopping suggestions for me, in English."
    assert requests[1].endswith("which I've already seen: Spinach.")  # Domates is in the fridge
    assert len(sent) == 1  # the system prompt stays the same


# The shopping summary uses the shopping stages and problem columns
def test_shopping_summary():
    issues = {"dish": ["Menemen"], "vague": [], "repeat": [], "turkish": []}
    score = {"json": True, "dishes": ["kale"], "issues": issues, "note": "1 of 2 kept"}
    records = [{"sample": "mixed", "run": 1, "seconds": 20, "error": None, "replies": {}, "scores": {"suggest": score}}]
    lines = summarize(records, "shopping").splitlines()
    assert lines[0].split()[6:10] == ["Dish", "Vague", "Repeat", "Turkish"]
    assert lines[1].split() == ["mixed", "suggest", "1", "1", "0", "1", "1", "0", "0", "0", "0", "20"]
