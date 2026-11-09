"""Tests for the prompt test's reply checks, runner, summary and history, offline with canned replies."""

import json
from unittest.mock import patch

import pytest

from services import pipeline
from services.chat_block import chat_history, format_chat_block
from services.personas.chat import build_chat_message
from services.fridge import find_missing_ingredients, same_name
from tools.prompt_check import (
    CHECKS, PERSONAS, chat_once, chat_rows, check_chat, check_plan, check_reply, check_review, compare, data_name, describe,
    is_clean, model_folder, parse_args, plan_once, recording_prompts, review_once, run, save_log, save_model_data,
    score_shopping, shop_once, suggest_once, summarize,
)
from tools.prompt_samples import (
    CHAT_MESSAGES, CHAT_MINUTES, PLAN_CASES, REVIEW_CASES, SAMPLE_MODES, SAMPLES, SCENARIOS, chat_picks, chat_scenario,
)

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


# A simple item's method is noted, not flagged, so filler like "serve as is" shows in the log; dishes' methods aren't
def test_simple_item_methods_are_noted():
    text = _reply(
        {"name": "Menemen", "method": "Fry the tomatoes, stir in the eggs", "ingredients": [
            {"name": "Eggs", "amount": 2, "unit": "pcs"}, {"name": "Tomatoes", "amount": 1, "unit": "pcs"},
        ]},
        {"name": "White cheese", "amount": 50, "unit": "g", "method": "Serve as is", "ingredients": []},
        {"name": "Water", "amount": 1, "unit": "glass", "method": " ", "ingredients": []},
    )
    result = check_reply(text, EN)
    assert is_clean(result) and describe(result) == "clean (simple items: White cheese: Serve as is)"


# A dish ingredient's prep words are noted, not flagged, so a word that doesn't change how the dish is made shows in
# the log (#176); an empty one isn't
def test_prep_words_are_noted():
    text = _reply({"name": "Menemen", "method": "Fry the tomatoes, stir in the eggs", "ingredients": [
        {"name": "Eggs", "amount": 2, "unit": "pcs", "prep": "mixed"},
        {"name": "Tomatoes", "amount": 1, "unit": "pcs", "prep": " diced "},
        {"name": "Olive oil", "amount": 1, "unit": "tbsp", "prep": " "},
    ]})
    result = check_reply(text, EN)
    assert is_clean(result) and result["note"] == "prep: Eggs: mixed; Tomatoes: diced"


# A final notes the review's swaps (#148): a dish ingredient marked as standing in for a missing item, and a draft's
# missing item gone with no mark; a rename to the fridge name and a missing item the review kept aren't gone
def test_review_swaps_are_noted():
    ing = lambda name, **extra: {"name": name, "amount": 50, "unit": "g", **extra}
    draft = _reply({"name": "Salmon omelette", "ingredients": [
        ing("Eggs"), ing("Salmon"), ing("Quinoa"), ing("Sliced tomatoes"), ing("Chives"),
    ]})
    final = _reply({"name": "Salmon omelette", "ingredients": [
        ing("Eggs"), ing("White cheese", replaces="Salmon"), ing("Tomatoes", prep="sliced"), ing("Chives"),
    ]})
    result = check_reply(final, EN, draft=draft)
    assert result["note"] == "prep: Tomatoes: sliced; replaced White cheese for Salmon (Salmon omelette); gone, no mark: Quinoa"
    assert "note" not in check_reply(draft, EN)


# A reply without a meal JSON block fails the JSON check
def test_no_meal_json():
    result = check_reply("Here is a lovely breakfast idea.", EN)
    assert result["json"] is False
    assert not is_clean(result)
    assert describe(result) == "no JSON"


# A fridge too small for a breakfast passes with a note to the user; a menu, or a broken block, doesn't
def test_note_for_a_fridge_too_small():
    bare = SAMPLES["bare"]
    note = check_reply("Your fridge has only tea and salt. Add a few items in the Fridge tab.", bare)
    assert is_clean(note) and describe(note).startswith("clean (note: Your fridge has only tea and salt.")
    menu = check_reply(_reply({"name": "Tea", "amount": 1, "unit": "glass", "ingredients": []}), bare)
    assert not is_clean(menu) and menu["issues"]["menu"] == ["Tea"]
    assert not is_clean(check_reply("Enjoy!\n```json\n{broken\n```", bare))
    assert not is_clean(check_reply("", bare))
    assert not is_clean(check_reply(pipeline.RETRY_TEXTS["en"], bare))
    assert check_reply(_reply({"name": "Tea", "amount": 1, "unit": "glass", "ingredients": []}), EN)["issues"]["menu"] == []


# A fraction amount is read the way the app reads it, so the reply still scores as a meal
def test_fraction_amounts_score_as_a_meal():
    text = 'Enjoy!\n```json\n{"menu_name": "Oats", "menu": [{"name": "Oats", "amount": 1/4, "unit": "glass", "ingredients": []}]}\n```'
    assert is_clean(check_reply(text, EN))


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


# A name shorter than its fridge name may be another product, so it's missing, not renamed
def test_shorter_names_are_missing():
    text = _reply({"name": "Cheese", "amount": 50, "unit": "g", "ingredients": []})
    issues = check_reply(text, EN)["issues"]
    assert issues["missing"] == ["Cheese"]
    assert issues["renamed"] == []


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


# Amounts the app can't read as a number above zero, and items without an amount or unit, are reported with what's wrong
def test_amount_problems():
    text = _reply(
        {"name": "Omelette", "ingredients": [
            {"name": "Eggs", "amount": 2, "unit": "pcs"},
            {"name": "Salt", "amount": "to taste", "unit": "pinch"},
            {"name": "Butter", "amount": 0, "unit": "tsp"},
        ]},
        {"name": "Bread", "amount": "2", "unit": "slice", "ingredients": []},
        {"name": "Banana", "amount": 1, "ingredients": []},
        {"name": "Olives", "unit": "pcs", "ingredients": []},
    )
    assert check_reply(text, EN)["issues"]["amounts"] == [
        "Salt (to taste)", "Butter (0)", "Banana (no unit)", "Olives (no amount)",
    ]


# Avoided items are found by exact name, so a longer name the user hasn't banned isn't reported
def test_avoided_items():
    sample = {**EN, "avoid_list": ["Walnuts", "Milk"]}
    text = _reply({"name": "Oat bowl", "ingredients": [
        {"name": "Oats", "amount": 1, "unit": "glass"},
        {"name": "Walnut", "amount": 20, "unit": "g"},
        {"name": "Almond milk", "amount": 1, "unit": "glass"},
    ]})
    assert check_reply(text, sample)["issues"]["avoided"] == ["Walnut"]


# A dish named after a fridge item it doesn't use is reported with that word; words that name no
# fridge item ("pudding") and color words ("Green" of "Green peppers") are left alone
def test_dishes_named_after_what_they_lack():
    text = _reply(
        {"name": "Banana oat porridge", "ingredients": [
            {"name": "Oats", "amount": 1, "unit": "glass"}, {"name": "Milk", "amount": 1, "unit": "glass"},
        ]},
        {"name": "Tomato omelette", "ingredients": [
            {"name": "Eggs", "amount": 2, "unit": "pcs"}, {"name": "Tomatoes", "amount": 1, "unit": "pcs"},
        ]},
        {"name": "Chia pudding", "ingredients": [
            {"name": "Yogurt", "amount": 1, "unit": "glass"}, {"name": "Honey", "amount": 1, "unit": "tsp"},
        ]},
        {"name": "Green scramble", "ingredients": [
            {"name": "Eggs", "amount": 2, "unit": "pcs"}, {"name": "Butter", "amount": 1, "unit": "tsp"},
        ]},
    )
    assert check_reply(text, EN)["issues"]["named"] == ["Banana oat porridge (banana)"]


# One run returns the draft and the final reply; draft-only closes the pipeline before the review
async def test_suggest_once_collects_draft_and_final():
    calls = []

    async def fake_pipeline(context, user_message, mode=None, temperature=None, chat_block=None):
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


# Without --mode each sample's user presses Suggest the way they usually do; --mode overrides it for all
async def test_samples_run_in_their_usual_mode():
    modes = []

    async def fake_suggest_once(sample, mode, draft_only, scenario=None):
        modes.append(mode)
        return {}

    with patch("tools.prompt_check.suggest_once", fake_suggest_once):
        await run(["en", "picky", "greek"], 1, None, False)
        await run(["picky"], 1, "explore", False)
    assert modes == [None, "favorites", "explore", "explore"]
    assert set(SAMPLE_MODES) <= set(SAMPLES)


# The fake model's meal, one fridge dish, and the draft as the prompt test logs it: its text, then the meal
_MEAL = {
    "menu": [{"ingredients": [{"name": "Eggs", "amount": 2, "unit": "pcs"}], "name": "Boiled eggs"}],
    "menu_name": "Eggs", "description": "Warm eggs.", "prep_time_min": 10,
}
_DRAFT = "Enjoy!\n\n```json\n" + json.dumps(_MEAL, ensure_ascii=False, indent=2) + "\n```"


async def _fake_stream(system_prompt, history, message, temperature=None):
    yield "A warm start."


async def _fake_chat_json(system_prompt, messages, schema, temperature=None):
    """The draft's reply for the draft's schema (its text first), else the reviser's."""
    if "text" in schema["properties"]:
        return json.dumps({"text": "Enjoy!", "meal": _MEAL})
    return json.dumps({"changes": [], "meal": _MEAL})


# Every sample runs through the real pipeline with a fake model, so it has all the context the prompts read
async def test_samples_run_through_the_pipeline():
    with patch("services.pipeline.stream_response", _fake_stream), patch("services.pipeline.chat_json", _fake_chat_json):
        for sample in SAMPLES.values():
            replies = await suggest_once(sample, None, draft_only=False)
            assert replies["draft"] == _DRAFT
            assert replies["review"] == "- No changes." or replies["review"].startswith("- CODE CHECK")
            assert replies["final"].startswith("A warm start.\n\n```json\n")


# Each sample's chat picks four different fridge items, none avoided or disliked, and the same ones on every test
def test_chat_picks_are_fixed_fridge_items():
    for key, sample in SAMPLES.items():
        picks = chat_picks(sample, key)
        if sample.get("expects_note"):  # a fridge too small for a breakfast has no chat scenario
            assert picks is None and chat_scenario(key, "chat") is None, key
            continue
        fridge = [i["name"] for i in sample["ingredients"]]
        banned = sample["avoid_list"] + [v for k, v in sample["preferences"].items() if k.startswith("dislike:")]
        assert len(set(picks)) == 4 and set(picks) <= set(fridge), key
        assert not any(same_name(p, b) for p in picks for b in banned), key
        assert chat_picks(sample, key) == picks
    # Basics and drinks only when the other items run out: the sparse fridge has two others
    assert set(chat_picks(SAMPLES["sparse"], "sparse")[:2]) == {"Eggs", "Bread"}
    assert chat_picks({**SAMPLES["sparse"], "ingredients": SAMPLES["sparse"]["ingredients"][:3]}, "sparse") is None


# A fresh chat has no scenario; chat is four typed messages, and pressed puts them between two earlier menus
def test_chat_scenarios():
    assert chat_scenario("en", "fresh") is None
    chat, pressed = chat_scenario("en", "chat"), chat_scenario("en", "pressed")
    (a,), (b,), (c,) = chat["leave_out"], chat["liked"], chat["allowed"]
    typed = [e["content"] for e in chat["chat"]]
    assert typed == [
        f"No {a.lower()} please, and no {c.lower()} either.", f"I love {b.lower()}.",
        f"I only have {CHAT_MINUTES} minutes.", f"Actually {c.lower()} is fine again.",
    ]
    assert chat["max_minutes"] == CHAT_MINUTES
    assert [e.get("content") for e in pressed["chat"]] == [None, typed[0], None, *typed[1:]]
    first, second = (e["press"] for e in pressed["chat"] if "press" in e)
    assert [i["name"] for i in first["menu"]] == [a, b, c]
    assert b in [i["name"] for i in second["menu"]] and not {a, c} & {i["name"] for i in second["menu"]}
    assert {k: v for k, v in pressed.items() if k != "chat"} == {k: v for k, v in chat.items() if k != "chat"}


# A scenario's chat is saved like the app saves it, and the press sends the block the server builds from it
def test_scenario_chat_is_the_server_block():
    chat, pressed = chat_scenario("en", "chat"), chat_scenario("en", "pressed")
    typed = [e["content"] for e in chat["chat"]]
    rows = chat_rows(pressed["chat"], None)
    assert [r["role"] for r in rows] == ["user", "assistant", "user", "user", "assistant", "user", "user", "user"]
    assert rows[0]["content"] == "Suggest Breakfast" and '"menu_name": "Breakfast plate"' in rows[1]["content"]
    assert chat_rows(pressed["chat"], "favorites")[0]["content"] == "Suggest breakfast from my favorite meals"
    assert format_chat_block(rows).split("\n\n", 1)[1].splitlines() == [
        "- #1 Menu shown: Breakfast plate. Items: Eggs, Cucumber, Simit",
        f"- #2 User: {typed[0]}",
        "- #3 Menu shown: Light plate. Items: Cucumber, Milk",
        f"- #4 User: {typed[1]}",
        f"- #5 User: {typed[2]}",
        f"- #6 User (latest message): {typed[3]}",
    ]


def _plain(*names, minutes=8) -> str:
    """A reply serving fridge items as they are."""
    menu = [{"name": n, "amount": 1, "unit": "pcs", "ingredients": []} for n in names]
    return "Enjoy!\n```json\n" + json.dumps({"menu_name": "Test", "menu": menu, "prep_time_min": minutes}) + "\n```"


# After a chat a reply is flagged for a food still left out, a time over the limit and an earlier menu,
# while a liked food and a ban taken back are only noted
def test_chat_checks():
    scenario = chat_scenario("en", "pressed")
    (a,), (b,), (c,) = scenario["leave_out"], scenario["liked"], scenario["allowed"]
    other = next(i["name"] for i in EN["ingredients"] if i["name"] not in {a, b, c})

    fine = check_reply(_plain(b, c, other), EN, scenario)
    assert is_clean(fine)
    assert fine["note"] == f"liked {b}: in, allowed {c}: in"
    assert check_reply(_plain(other), EN, scenario)["note"] == f"liked {b}: out, allowed {c}: out"

    issues = check_reply(_plain(a, other, minutes=CHAT_MINUTES + 15), EN, scenario)["issues"]
    assert issues["left_out"] == [a]
    assert issues["over_time"] == [f"{CHAT_MINUTES + 15} min"]
    assert check_reply(_plain(b, minutes=CHAT_MINUTES), EN, scenario)["issues"]["over_time"] == []

    # The first menu again, in another order and case, is a repeat
    assert check_reply(_plain(c.upper(), b.lower(), a), EN, scenario)["issues"]["repeat"] == ["Breakfast plate"]
    assert check_reply(_plain(c, b), EN, scenario)["issues"]["repeat"] == []

    # A fresh chat asks nothing
    fresh = check_reply(_plain(a, minutes=60), EN)
    assert is_clean(fresh) and "note" not in fresh


# Each sample runs once per scenario, labelled by it, and a fridge too small for a chat is skipped
async def test_run_labels_each_scenario():
    calls = []

    async def fake_suggest_once(sample, mode, draft_only, scenario=None):
        calls.append(scenario)
        return {}

    tiny = {**SAMPLES["sparse"], "ingredients": SAMPLES["sparse"]["ingredients"][:3]}
    with patch("tools.prompt_check.suggest_once", fake_suggest_once), patch.dict(SAMPLES, {"sparse": tiny}):
        records, prompts = await run(["en", "sparse"], 1, None, False, scenarios=list(SCENARIOS))
    assert [r["sample"] for r in records] == ["en", "en:chat", "en:pressed", "sparse"]
    assert calls == [None, chat_scenario("en", "chat"), chat_scenario("en", "pressed"), None]
    assert list(prompts) == ["en", "en:chat", "en:pressed", "sparse"]


# The chat block ends the draft's and the reviser's messages, every sample's scenarios run through the pipeline, and the log keeps it
async def test_scenarios_run_through_the_pipeline():
    drafts, revisions = [], []

    async def chat_json(system_prompt, messages, schema, temperature=None):
        (drafts if "text" in schema["properties"] else revisions).append(messages[-1]["content"])
        return await _fake_chat_json(system_prompt, messages, schema, temperature)

    with patch("services.pipeline.stream_response", _fake_stream), patch("services.pipeline.chat_json", chat_json):
        for key, sample in SAMPLES.items():
            if sample.get("expects_note"):
                continue
            for name in ("chat", "pressed"):
                scenario = chat_scenario(key, name)
                replies = await suggest_once(sample, SAMPLE_MODES.get(key), False, scenario=scenario)
                sent = format_chat_block(chat_rows(scenario["chat"], SAMPLE_MODES.get(key)))
                assert replies["chat"] == sent
                assert drafts[-1].endswith(sent) and revisions[-1].endswith(sent)
                assert replies["final"].startswith("A warm start.")


# The recorder keeps each distinct system prompt once, in order of use, streamed or structured, and puts both senders back
async def test_recording_prompts_keeps_distinct_system_prompts():
    sent = {}
    with patch("services.pipeline.stream_response", _fake_stream), patch("services.pipeline.chat_json", _fake_chat_json):
        with recording_prompts(sent):
            await suggest_once(EN, None, draft_only=False)
            await suggest_once(EN, None, draft_only=False)
        assert pipeline.stream_response is _fake_stream
        assert pipeline.chat_json is _fake_chat_json
    prompts = list(sent)
    assert len(prompts) == 3  # draft, reviser and present
    assert "Reply with one JSON object" in prompts[0]
    assert "meal reviser" in prompts[1]
    assert "Introduce it in a few short lines" in prompts[2]


# The summary counts replies and distinct menus per sample and stage, then lists the most frequent offenders
def test_summary_counts_and_offenders():
    none = {p: [] for p in PERSONAS["suggest"]["problems"]}
    clean = {"json": True, "dishes": ["menemen"], "issues": none}
    simit = {"json": True, "dishes": ["simit"], "issues": {**none, "renamed": ["Simit with tahini"]}}
    records = [
        {"sample": "en", "run": 1, "seconds": 30, "error": None, "replies": {}, "scores": {"draft": simit, "final": clean}},
        {"sample": "en", "run": 2, "seconds": 50, "error": None, "replies": {}, "scores": {"draft": simit, "final": simit}},
    ]
    lines = summarize(records).splitlines()
    assert lines[1].split() == ["en", "draft", "2", "2", "0", "1", "0", "2", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "40"]
    assert lines[2].split() == ["en", "final", "2", "2", "1", "2", "0", "1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "40"]
    assert "en draft renamed: Simit with tahini ×2" in lines


# Each sample and stage is compared with its best earlier test in the same mode, scored by the same checks
def test_compare_with_best_earlier_test():
    old = {"date": "2026-10-27 23:21", "prompt": "aaaaaaa", "mode": "usual", "checks": CHECKS, "note": "baseline",
           "results": {"en final": {"clean": 1, "scored": 2, "distinct": 1}}}
    best = {**old, "prompt": "bbbbbbb", "note": "", "results": {"en final": {"clean": 2, "scored": 2, "distinct": 2}}}
    explore = {**old, "mode": "explore", "results": {"en final": {"clean": 3, "scored": 3, "distinct": 3}}}
    fewer_checks = {**explore, "mode": "usual", "checks": CHECKS - 1}
    now = {"en final": {"clean": 1, "scored": 2, "distinct": 2}, "en draft": {"clean": 0, "scored": 2, "distinct": 1}}
    assert compare(now, [old, best, explore, fewer_checks], "usual") == [
        "en final: 1/2 clean, 2 distinct ▼ best 2/2 clean, 2 distinct: prompt bbbbbbb (2026-10-27 23:21)",
        "en draft: 0/2 clean, 1 distinct · first test",
    ]


# A test is compared only with earlier tests of its model and think setting (#178); a test from before --model
# counts as the baseline model's
def test_compare_by_model():
    old = {"date": "2026-11-08 18:11", "prompt": "aaaaaaa", "mode": "usual", "checks": CHECKS, "note": "",
           "results": {"en final": {"clean": 2, "scored": 2, "distinct": 2}}}
    other = {**old, "prompt": "ccccccc", "model": "gemma3:4b", "results": {"en final": {"clean": 1, "scored": 2, "distinct": 1}}}
    thinking = {**other, "think": True, "results": {"en final": {"clean": 2, "scored": 2, "distinct": 2}}}
    now = {"en final": {"clean": 1, "scored": 2, "distinct": 1}}
    assert compare(now, [old, other, thinking], "usual", model="gemma3:4b")[0].endswith("= best 1/2 clean, 1 distinct: prompt ccccccc (2026-11-08 18:11)")
    assert "best 2/2 clean" in compare(now, [old, other, thinking], "usual")[0]
    assert "best 2/2 clean" in compare(now, [old, other, thinking], "usual", model="gemma3:4b", think=True)[0]
    assert compare(now, [old], "usual", model="llama3.1:8b") == ["en final: 1/2 clean, 1 distinct · first test"]


# A model test's data files (#178): the inputs by sample label, with the chat a press comes after, and the model's
# outputs in a folder per model and think setting, named after the test
def test_model_data_files(tmp_path):
    records = [
        {"sample": "en", "mode": None, "run": 1, "seconds": 9.5, "error": None, "replies": {"final": "Hi"}, "scores": {}},
        {"sample": "en:chat", "mode": None, "run": 1, "seconds": 8.0, "error": None, "replies": {"final": "Hi"}, "scores": {}},
    ]
    meta = {"model": "qwen3.5:4b", "think": False, "prompt": "aaaaaaa", "gpu": 100}
    with patch("tools.prompt_check.MODELS_DIR", tmp_path):
        inputs, outputs = save_model_data(records, "suggest", data_name("suggest", "all"), meta)
    assert inputs == tmp_path / "inputs" / "suggest-all.json"
    assert outputs == tmp_path / "qwen3.5_4b-think-off" / "suggest-all.json"
    saved = json.loads(inputs.read_text(encoding="utf-8"))["samples"]
    assert saved["en"]["chat"] is None and saved["en"]["data"]["ingredients"] == EN["ingredients"]
    assert saved["en:chat"]["chat"] == chat_scenario("en", "chat")
    out = json.loads(outputs.read_text(encoding="utf-8"))
    assert (out["model"], out["think"], out["gpu"], out["test"]) == ("qwen3.5:4b", False, 100, "suggest-all")
    assert [r["sample"] for r in out["records"]] == ["en", "en:chat"]
    assert [data_name("suggest", "fresh"), data_name("chat", "chat"), data_name("review", "fresh", "explore")] == [
        "suggest", "chat", "review-explore",
    ]
    assert model_folder("qwen2.5:7b", None) == "qwen2.5_7b"
    assert parse_args(["--data"]).data and not parse_args([]).data


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


# One shopping run asks twice, the second time with the first reply's new items as already shown,
# and each press draws its share of the fridge from a seeded source, so every run sends the same
async def test_shop_once_asks_for_more_with_what_was_shown():
    requests = []

    async def fake_chat_json(system_prompt, messages, schema, temperature=None):
        requests.append(messages[0]["content"])
        return _shopping_reply("Spinach", "Domates") if len(requests) == 1 else _shopping_reply("Kale")

    with patch("services.llm.chat_json", fake_chat_json):
        replies = await shop_once(SAMPLES["mixed"], {})
        first = list(requests)
        requests.clear()
        await shop_once(SAMPLES["mixed"], {})
    assert list(replies) == ["suggest", "more"]
    assert first[0].startswith("Some of what I have now: ")
    assert first[0].endswith("\nGenerate shopping suggestions for me, in English.")
    assert first[1].endswith("which I've already seen: Spinach.")  # Domates is in the fridge
    assert requests == first


# The shopping summary uses the shopping stages and problem columns
def test_shopping_summary():
    issues = {"dish": ["Menemen"], "vague": [], "repeat": [], "turkish": []}
    score = {"json": True, "dishes": ["kale"], "issues": issues, "note": "1 of 2 kept"}
    records = [{"sample": "mixed", "run": 1, "seconds": 20, "error": None, "replies": {}, "scores": {"suggest": score}}]
    lines = summarize(records, "shopping").splitlines()
    assert lines[0].split()[6:10] == ["Dish", "Vague", "Repeat", "Turkish"]
    assert lines[1].split() == ["mixed", "suggest", "1", "1", "0", "1", "1", "0", "0", "0", "0", "20"]


def _plan(**dishes) -> str:
    """A planner reply in #144's shape: each keyword is a dish (underscores for spaces) with its step actions,
    each an action or an (action, appliance) pair."""
    plan = {"dishes": [
        {"dish": name.replace("_", " "), "steps": [
            {"action": a, "minutes": 2, "hands_on": not appliance, "appliance": appliance}
            for a, appliance in ((s, "") if isinstance(s, str) else s for s in actions)
        ]}
        for name, actions in dishes.items()
    ]}
    return "```json\n" + json.dumps(plan, ensure_ascii=False) + "\n```"


# A plan that makes the egg sandwich as designed, with only menu food, is clean, and its note counts the steps
# and the switches between dishes
def test_plan_following_the_method_is_clean():
    text = _plan(Egg_sandwich=[("Hard-boil the eggs", "Stove"), "Peel and slice them", ("Toast the bread", "Toaster"), "Fill the bread"])
    result = check_plan(text, PLAN_CASES["boiled"])
    assert is_clean(result), describe(result)
    assert describe(result) == "clean (steps Egg sandwich 4; switches 0)"


# Frying what the method boils is flagged, and so is food the menu doesn't list, like a copied example
def test_plan_against_the_method_and_off_the_menu():
    text = _plan(Egg_sandwich=["Fry the eggs in oil", "Slide onto the bread"], Salad=["Slice tomatoes and cucumbers"])
    result = check_plan(text, PLAN_CASES["boiled"])
    assert result["issues"]["method"] == ["Fry the eggs in oil (Egg sandwich: boil)"]
    assert result["issues"]["unlisted"] == ["oil", "tomatoes", "cucumbers"]
    assert result["note"] == "steps Egg sandwich 2, Salad 1; switches 1; no appliance: Fry the eggs in oil (Egg sandwich)"


# Each plan dish is held to its own menu dish's method: the omelette may fry eggs beside boiled eggs,
# while frying under the boiled eggs, or under a dish the menu doesn't name, is still flagged
def test_plan_method_is_checked_per_dish():
    case = PLAN_CASES["omelette"]
    clean = _plan(Greek_omelette=["Whisk 3 eggs with the feta", "Fry the eggs in the oiled pan", "Fold"],
                  Boiled_eggs=["Boil 2 eggs", "Cool, peel and halve"])
    assert check_plan(clean, case)["issues"]["method"] == []
    mixed = _plan(Boiled_eggs=["Fry 2 eggs"], Eggs=["Fry the eggs in oil"])
    assert check_plan(mixed, case)["issues"]["method"] == [
        "Fry 2 eggs (Boiled eggs: boil)", "Fry the eggs in oil (Boiled eggs: boil)",
    ]


# The switch count is taken from the plan the app shows: the oatmeal fills the pudding's wait, so the plan
# moves to the oatmeal and back once each, and the step the model gave a served sweet potato isn't counted
def test_plan_switches_count_the_plan_the_app_shows():
    plan = {"dishes": [
        {"dish": "Chia pudding", "steps": [
            {"action": "Stir the chia seeds into the milk with the honey", "minutes": 1, "hands_on": True},
            {"action": "Let it set", "minutes": 10, "hands_on": False},
            {"action": "Top with the sliced banana", "minutes": 1, "hands_on": True},
        ]},
        {"dish": "Pumpkin oatmeal", "steps": [
            {"action": "Simmer the oats in the milk", "minutes": 5, "hands_on": False, "appliance": "Stove"},
            {"action": "Stir in the pumpkin purée", "minutes": 1, "hands_on": True},
            {"action": "Top with the tahini", "minutes": 1, "hands_on": True},
        ]},
        {"dish": "Sweet potato", "steps": [{"action": "Serve 300 g sweet potato", "minutes": 1, "hands_on": True}]},
    ]}
    bowls = PLAN_CASES["bowls"]
    served = {**bowls, "menu": [*bowls["menu"][:2], {"name": "Sweet potato", "amount": 300, "unit": "g", "ingredients": []}]}
    result = check_plan("```json\n" + json.dumps(plan) + "\n```", served)
    assert is_clean(result), describe(result)
    assert result["note"] == "steps Chia pudding 3, Pumpkin oatmeal 3, Sweet potato 1; switches 2"


# Toasting the bread before mashing the avocado is flagged (the toast waits), while peeling eggs after boiling
# them, cutting after a heating step whose food code can't tell, and toast spread last are not
def test_plan_heating_before_prep():
    case = PLAN_CASES["avocado"]
    late = _plan(Avocado_toast=[("Toast the bread", "Toaster"), "Mash the avocado with the lemon juice", "Spread it on the toast"])
    assert check_plan(late, case)["issues"]["order"] == ["Mash the avocado with the lemon juice (after Toast the bread)"]
    early = _plan(Avocado_toast=["Mash the avocado with the lemon juice", ("Toast the bread", "Toaster"), "Spread it on the toast"])
    assert check_plan(early, case)["issues"]["order"] == []
    unknown = _plan(Avocado_toast=[("Toast it", "Toaster"), "Mash the avocado"])
    assert check_plan(unknown, case)["issues"]["order"] == []
    eggs = _plan(Boiled_eggs=[("Boil the eggs", "Stove"), "Peel and halve the eggs"])
    assert check_plan(eggs, PLAN_CASES["omelette"])["issues"]["order"] == []
    turkish = _plan(Menemen=[("Yumurtaları haşla", "Stove"), "Domatesleri doğra"])
    assert check_plan(turkish, PLAN_CASES["menemen"])["issues"]["order"] == ["Domatesleri doğra (after Yumurtaları haşla)"]


# A heating step with no appliance from the case's kitchen is noted, not a problem, since the cook can use one
# they have: toast in the Oven where there is no Toaster isn't noted, a Toaster there is, and spreading on the
# toast or cooling the boiled eggs isn't heating
def test_plan_heating_without_an_appliance_is_noted():
    cooled = _plan(Boiled_eggs=[("Hard-boil the eggs", "Stove"), "Cool the boiled eggs in cold water"])
    assert "no appliance" not in check_plan(cooled, PLAN_CASES["omelette"])["note"]
    bare = check_plan(_plan(Boiled_eggs=["Hard-boil the eggs"]), PLAN_CASES["omelette"])
    assert is_clean(bare), describe(bare)
    assert bare["note"].endswith("; no appliance: Hard-boil the eggs (Boiled eggs)")
    steps = lambda appliance: _plan(Avocado_toast=["Mash the avocado", ("Toast the bread", appliance), "Spread it on the toast"])
    noted = lambda appliance, case: check_plan(steps(appliance), PLAN_CASES[case])["note"].partition("; no appliance: ")[2]
    assert noted("Oven", "avocado_oven") == ""
    assert noted("Toaster", "avocado_oven") == "Toast the bread (Avocado toast)"
    assert noted("", "avocado") == "Toast the bread (Avocado toast)"
    assert noted("Toaster", "avocado") == ""


# Turkish suffixes still match: boiling the eggs of a menemen is flagged, its peppers and tomatoes are on the menu;
# a reply in the old prep and timed shape counts as no JSON
def test_turkish_plan_against_the_method():
    text = _plan(Menemen=["Biberleri ve domatesleri doğra", "Yumurtaları haşla"])
    issues = check_plan(text, PLAN_CASES["menemen"])["issues"]
    assert issues["method"] == ["Yumurtaları haşla (Menemen: fry)"]
    assert issues["unlisted"] == []
    assert describe(check_plan("No plan today.", PLAN_CASES["menemen"])) == "no JSON"
    old = '```json\n{"prep": [{"task": "Slice"}], "timed": []}\n```'
    assert describe(check_plan(old, PLAN_CASES["menemen"])) == "no JSON"


# One plan run sends the planner's real prompt and the menu with each dish's method, for every plan menu
async def test_plan_once_sends_the_menu_with_its_methods():
    calls = []

    async def fake_stream(system_prompt, history, message, temperature=None):
        calls.append(temperature)
        yield "ok"

    requests = {}
    with patch("services.suggestion.stream_response", fake_stream):
        for key, case in PLAN_CASES.items():
            sent = {}
            replies = await plan_once(case, sent)
            assert replies["plan"] == "ok"
            assert len(sent) == 1 and "kitchen workflow expert" in next(iter(sent))
            requests[key] = replies["request"]
    assert "- Egg sandwich (Hard-boil the eggs, peel, slice into the buttered bread): Eggs (2 pcs)" in requests["boiled"]
    assert "- Sweet potato (Peel and cube the sweet potato, roast it in the air fryer): Sweet potato (300 g)" in requests["bowls"]
    assert set(calls) == {0.3}


def _pancakes(*ingredients) -> str:
    """The pancakes review case's reply with the dish made of these ingredients, beside its orange juice."""
    dish = {"name": "Blueberry pancakes", "method": "Mix, fry", "ingredients": [
        {"name": n, "amount": 1, "unit": "glass", **extra} for n, extra in ingredients
    ]}
    return _reply(dish, {"name": "Orange juice", "amount": 1, "unit": "glass", "ingredients": []})


# A review that swaps the missing blueberries for strawberries and marks it is clean, its note naming the swap; one
# that keeps them notes them as still missing, and one that brings in a food from outside the fridge and the draft
# (raspberries) is flagged, its note naming the fridge food it dropped (the maple syrup)
def test_review_scores_swaps_and_outside_names():
    case = REVIEW_CASES["pancakes"]
    draft = pipeline._meal_reply("", case["draft"])
    base = [("Flour", {}), ("Eggs", {}), ("Milk", {}), ("Baking powder", {}), ("Maple syrup", {})]
    swapped = check_review(_pancakes(*base, ("Strawberries", {"replaces": "Blueberries"})), case, draft)
    assert is_clean(swapped), describe(swapped)
    assert swapped["note"] == "replaced Strawberries for Blueberries (Blueberry pancakes)"
    kept = check_review(_pancakes(*base, ("Blueberries", {})), case, draft)
    assert is_clean(kept) and kept["note"] == "still missing: Blueberries"
    outside = check_review(_pancakes(*base[:4], ("Raspberries", {})), case, draft)
    assert outside["issues"]["outside"] == ["Raspberries"]
    assert outside["note"] == "gone, no mark: Blueberries; dropped: Maple syrup"
    assert describe(check_review("", case, draft)) == "no JSON"


# The omelette case may keep Egg whites as written, since a rename to Eggs loses the part, so a kept one is still
# missing, not renamed; a kept Diced onion, a fridge item with its cut, is still flagged as renamed (#176)
def test_review_case_may_keep_a_part():
    case = REVIEW_CASES["omelette"]
    draft = pipeline._meal_reply("", case["draft"])
    ing = lambda name, **extra: {"name": name, "amount": 1, "unit": "pcs", **extra}
    stocked = [ing("Sweet potatoes"), ing("Cheddar", prep="grated"), ing("Spinach")]
    toast = {"name": "Jam toast", "method": "Toast the bread, spread the jam", "ingredients": [
        ing("Whole wheat bread"), ing("Strawberry jam"),
    ]}
    coffee = {"name": "Coffee", "amount": 1, "unit": "glass", "ingredients": []}
    omelette = lambda *items: {"name": "Sweet potato omelette", "method": "Cook", "ingredients": [*items, *stocked]}
    kept = check_review(_reply(omelette(ing("Egg whites"), ing("Onion", prep="diced")), toast, coffee), case, draft)
    assert is_clean(kept), describe(kept)
    assert kept["note"].endswith("still missing: Egg whites")
    renamed = check_review(_reply(omelette(ing("Egg whites"), ing("Diced onion")), toast, coffee), case, draft)
    assert renamed["issues"]["renamed"] == ["Diced onion"]
    assert case["may_keep"] == ["Egg whites", "Smoked cheddar"] and REVIEW_CASES["pancakes"]["may_keep"] == []


# A review run sends the case's draft and code check to the reviser in the case user's mode, and returns the draft,
# the review lines and the revised meal; every case's draft has an item the fridge lacks
async def test_review_once_sends_the_draft():
    calls = []

    async def fake_chat_json(system_prompt, messages, schema, temperature=None):
        calls.append(messages[0]["content"])
        meal = json.loads(json.dumps(REVIEW_CASES["pancakes"]["draft"]))
        return json.dumps({"changes": ["Strawberries for the blueberries"], "meal": meal})

    with patch("services.pipeline.chat_json", fake_chat_json):
        replies = await review_once(REVIEW_CASES["pancakes"], "favorites")
    assert "- Not in the fridge: Blueberries" in calls[0]
    assert replies["review"] == "- CODE CHECK: Not in the fridge: Blueberries\n- Strawberries for the blueberries"
    assert replies["draft"].startswith("Pancake morning\n\n```json") and replies["final"].startswith("Pancake morning")
    assert "Blueberries" in replies["final"]
    for case in REVIEW_CASES.values():
        assert find_missing_ingredients(case["draft"], case["ingredients"])
        assert all("method" not in item for item in case["draft"]["menu"])


# A review run's log keeps the draft it sent, which isn't scored, under its own title beside the scored final
def test_review_log_keeps_the_draft(tmp_path):
    record = {
        "sample": "pancakes", "mode": "favorites", "run": 1, "seconds": 9, "error": None,
        "replies": {"draft": "Pancake morning", "review": "- No changes.", "final": "Pancake morning"},
        "scores": {"final": check_review("", REVIEW_CASES["pancakes"], "")},
    }
    with patch("tools.prompt_check.RUNS_DIR", tmp_path):
        text = save_log([record], {}, "header", "report", "").read_text(encoding="utf-8")
    assert "### Draft sent" in text and "### Review feedback" in text and "### Final: no JSON" in text


# The review persona runs every review case by default, each in its user's usual mode
def test_review_samples():
    assert parse_args(["--persona", "review"]).samples == list(REVIEW_CASES)
    assert REVIEW_CASES["frittata"]["sample"] == "greek" and SAMPLE_MODES["greek"] == "explore"
    with pytest.raises(SystemExit):
        parse_args(["--persona", "review", "--samples", "en"])


# The plan persona runs every plan menu by default and only knows plan menus
def test_plan_samples():
    assert parse_args(["--persona", "plan"]).samples == list(PLAN_CASES)
    assert parse_args([]).samples == ["en"]
    with pytest.raises(SystemExit):
        parse_args(["--persona", "plan", "--samples", "en"])


# --scenario picks what a Suggest press comes after, a fresh chat by default, and is for Suggest presses only
def test_scenario_flag():
    assert parse_args([]).scenarios == ["fresh"]
    assert parse_args(["--scenario", "pressed"]).scenarios == ["pressed"]
    assert parse_args(["--scenario", "all"]).scenarios == list(SCENARIOS)
    with pytest.raises(SystemExit):
        parse_args(["--persona", "shopping", "--scenario", "chat"])


# --samples all runs every sample of the persona
def test_all_samples():
    assert parse_args(["--samples", "all"]).samples == list(SAMPLES)
    assert parse_args(["--persona", "shopping", "--samples", "all"]).samples == list(SAMPLES)
    assert parse_args(["--persona", "plan", "--samples", "all"]).samples == list(PLAN_CASES)


# A chat reply that talks and points to the Suggest button is clean; a number with a unit or a fridge item,
# a numbered or timed step and a code block make a menu or a plan, while "10 minutes" is no food amount
def test_chat_reply_checks():
    talk = check_chat("Ten minutes is plenty! Tap Suggest when you're ready and I'll keep it quick.", EN)
    assert is_clean(talk) and talk["note"] == "points to Suggest"

    plan = check_chat(
        "In 10 minutes you can make this:\n1. Boil 2 eggs\n**2.** Toast 1 slice of bread\n"
        "7:05 Serve with 50 g Feta\n```json\n{}\n```", EN,
    )
    assert plan["issues"]["amounts"] == ["1 slice", "50 g", "2 eggs"]
    assert plan["issues"]["steps"] == ["1. Boil 2 eggs", "**2.** Toast 1 slice of bread", "7:05 Serve with 50 g Feta"]
    assert plan["issues"]["block"] == ["```"]
    assert plan["note"] == "no Suggest"
    assert check_chat("Adım 1: 2 yumurta haşla, 1 çay kaşığı tuz ekle.", TR)["issues"]["amounts"] == ["1 çay kaşığı", "2 yumurta"]
    assert not check_chat("", EN)["json"]


# Two or more fridge items the user didn't name put a meal together in a chat reply; repeating the user's
# own foods, or naming one more, is talk
def test_chat_reply_bringing_in_food():
    said = ["No eggs please, and no simit either."]
    idea = check_chat("Got it, no eggs or simit! How about a yogurt bowl with honey and walnuts?", EN, said)
    assert idea["issues"]["food"] == ["Yogurt", "Honey", "Walnuts"]
    assert check_chat("Got it, no eggs and no simit today. Tap Suggest when you're ready.", EN, said)["issues"]["food"] == []
    assert check_chat("No eggs or simit, then. Some honey maybe?", EN, said)["issues"]["food"] == []


# The chat persona gets the typed messages one at a time with the chat so far as history, an earlier
# Suggest press as its button text and its card's one line (no JSON to copy), and each reply is kept under its message's kind
async def test_chat_once_sends_the_typed_messages_in_turn():
    calls = []

    async def fake_stream(system_prompt, history, message, temperature=None):
        calls.append((system_prompt, [dict(h) for h in history], message, temperature))
        yield f"reply {len(calls)}"

    scenario = chat_scenario("en", "pressed")
    typed = [e["content"] for e in scenario["chat"] if "press" not in e]
    sent = {}
    with patch("services.suggestion.stream_response", fake_stream):
        replies = await chat_once(EN, None, scenario, sent)
    assert list(replies) == ["chat", *CHAT_MESSAGES]
    assert replies["chat"] == "\n".join(typed) and replies["allowed"] == "reply 4"
    # Each message carries the app's note, as the server sends it, while the history keeps the words alone
    assert [message for _, _, message, _ in calls] == [build_chat_message(t, "en") for t in typed]
    assert [h["content"] for h in calls[-1][1] if h["role"] == "user"][-1] == typed[2]
    assert {temperature for *_, temperature in calls} == {None}
    assert len(sent) == 1 and "breakfast assistant" in next(iter(sent))
    # The first message comes after the first press; the last has the whole chat before it
    first_history, last_history = calls[0][1], calls[-1][1]
    assert first_history == chat_history(chat_rows(scenario["chat"][:1], None))
    assert first_history[1]["content"].startswith("A breakfast for you.\n\nMenu shown: Breakfast plate.")
    assert not any("```" in h["content"] for _, history, _, _ in calls for h in history)
    assert len(last_history) == 2 * 2 + 3 * 2  # both presses, and the three typed messages before it with their replies
    assert last_history[-1] == {"role": "assistant", "content": "reply 3"}


# A chat persona run scores each reply by its message's kind, labelled by the scenario
async def test_chat_persona_run():
    async def fake_stream(system_prompt, history, message, temperature=None):
        yield "Sounds good! Press Suggest when you're ready."

    with patch("services.suggestion.stream_response", fake_stream):
        records, _ = await run(["en"], 1, None, False, persona="chat", scenarios=["chat"])
    assert [r["sample"] for r in records] == ["en:chat"]
    assert list(records[0]["scores"]) == list(CHAT_MESSAGES)
    assert all(is_clean(s) for s in records[0]["scores"].values())
    assert "leave_out" in summarize(records, "chat")


# The chat persona answers typed messages: chat by default, all is chat and pressed, and a fresh chat is refused
def test_chat_persona_scenarios():
    assert parse_args(["--persona", "chat"]).scenarios == ["chat"]
    assert parse_args(["--persona", "chat", "--scenario", "all"]).scenarios == ["chat", "pressed"]
    with pytest.raises(SystemExit):
        parse_args(["--persona", "chat", "--scenario", "fresh"])


# --model and --think choose the model and Ollama's think field for one test
def test_model_and_think_options():
    args = parse_args(["--model", "gemma3:4b", "--think", "off"])
    assert (args.model, args.think) == ("gemma3:4b", "off")
    assert (parse_args([]).model, parse_args([]).think) == (None, None)
