"""Unit tests for the kitchen prep plan builder (steps per dish, interleaved, finishing together)."""

import random

from routers.scheduler import _build_plan


def _step(action, minutes, hands_on=True, appliance=""):
    return {"action": action, "minutes": minutes, "hands_on": hands_on, "appliance": appliance}


def _dish(name, *steps):
    return {"dish": name, "steps": list(steps)}


# Boiled eggs wait on the stove while the omelette is made (the example in #144)
EGGS_AND_OMELETTE = {"dishes": [
    _dish("Boiled eggs",
          _step("Put 2 eggs in boiling water", 10, False, "Stove"),
          _step("Cool in cold water", 1),
          _step("Peel and halve", 1)),
    _dish("Greek omelette",
          _step("Whisk 3 eggs with 30 g feta", 1),
          _step("Chop the tomato", 1),
          _step("Heat 1 tbsp olive oil in the pan", 1, True, "Stove"),
          _step("Pour in the eggs and tomato", 3, False, "Stove"),
          _step("Fold and slide onto a plate", 1)),
]}


def _steps(result, dish):
    return [s for s in result["timeline"] if s["dish"] == dish]


def _end(step):
    return step["start_min"] + step["duration_min"]


def _overlap(a, b):
    return a["start_min"] < _end(b) and b["start_min"] < _end(a)


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def test_steps_keep_their_dish_order():
    """Each dish's steps run in the order the LLM listed them, one after the other."""
    result = _build_plan(EGGS_AND_OMELETTE)
    for dish in EGGS_AND_OMELETTE["dishes"]:
        steps = _steps(result, dish["dish"])
        assert [s["task"] for s in steps] == [s["action"] for s in dish["steps"]]
        assert all(_end(a) <= b["start_min"] for a, b in zip(steps, steps[1:]))


def test_hands_on_steps_never_overlap():
    """One cook: no two hands-on steps run at the same time, even across dishes."""
    hands_on = [s for s in _build_plan(EGGS_AND_OMELETTE)["timeline"] if s["hands_on"]]
    assert len(hands_on) == 6
    assert not any(_overlap(a, b) for i, a in enumerate(hands_on) for b in hands_on[i + 1:])


def test_an_appliance_holds_one_step_and_the_stove_two():
    """Two toasts wait for the one toaster, while three pans share the stove two at a time."""
    raw = {"dishes": [
        _dish("Toast", _step("Toast 2 slices of bread", 3, False, "Toaster")),
        _dish("Cheese toast", _step("Toast 1 slice with cheese", 4, False, "Toaster")),
        *(_dish(f"Pan {n}", _step(f"Cook pan {n}", 5, False, "Stove")) for n in (1, 2, 3)),
    ]}
    timeline = _build_plan(raw, appliances=["Stove", "Toaster"])["timeline"]
    toasts = [s for s in timeline if s["resource"] == "Toaster"]
    assert not _overlap(*toasts)
    pans = [s for s in timeline if s["resource"] == "Stove"]
    for minute in range(max(_end(s) for s in pans)):
        assert sum(s["start_min"] <= minute < _end(s) for s in pans) <= 2
    assert max(sum(s["start_min"] <= m < _end(s) for s in pans) for m in range(10)) == 2


def test_dishes_finish_together():
    """Dishes that end by waiting are all done at the finish, the short one started later."""
    raw = {"dishes": [
        _dish("Boiled eggs", _step("Boil 2 eggs", 9, False, "Stove")),
        _dish("Toast", _step("Toast 2 slices of bread", 3, False, "Toaster")),
    ]}
    result = _build_plan(raw)
    assert result["makespan_min"] == 9
    assert [_end(s) for s in result["timeline"]] == [9, 9]
    assert _steps(result, "Toast")[0]["start_min"] == 6


def test_a_wait_is_filled_with_another_dishs_hands_on_steps():
    """The omelette is whisked and its tomato chopped while the eggs boil, not before or after."""
    result = _build_plan(EGGS_AND_OMELETTE)
    boil = _steps(result, "Boiled eggs")[0]
    whisk, chop = _steps(result, "Greek omelette")[:2]
    assert boil["start_min"] < whisk["start_min"] and _end(chop) <= _end(boil)
    # Everything fits inside the boil plus the egg's own hands-on steps
    assert result["makespan_min"] == 12


def test_random_menus_keep_every_rule():
    """Across many seeded random menus: dish order, one cook, appliance limits, and some dish ends at the finish."""
    rng = random.Random(144)
    for _ in range(300):
        raw = {"dishes": [
            _dish(f"Dish {d}", *(
                _step(f"Step {d}.{k}", rng.randint(1, 6), hands_on := rng.random() < 0.5,
                      rng.choice(["", "Stove", "Toaster"] if not hands_on else ["", "", "Stove"]))
                for k in range(rng.randint(1, 4))
            ))
            for d in range(rng.randint(1, 4))
        ]}
        result = _build_plan(raw)
        timeline = result["timeline"]
        for dish in raw["dishes"]:
            steps = _steps(result, dish["dish"])
            assert [s["task"] for s in steps] == [s["action"] for s in dish["steps"]]
            assert all(_end(a) <= b["start_min"] for a, b in zip(steps, steps[1:]))
        for minute in range(result["makespan_min"]):
            now = [s for s in timeline if s["start_min"] <= minute < _end(s)]
            assert sum(s["hands_on"] for s in now) <= 1
            assert sum(s["resource"] == "Toaster" for s in now) <= 1
            assert sum(s["resource"] == "Stove" for s in now) <= 2
        assert min(s["start_min"] for s in timeline) == 0
        assert max(_end(s) for s in timeline) == result["makespan_min"]


def test_one_dish_plan():
    """A single dish runs its steps back to back from 0:00 to the finish."""
    raw = {"dishes": [_dish("Porridge",
                            _step("Bring 1 glass of milk to a simmer", 3, False, "Stove"),
                            _step("Stir in 1 glass of rolled oats", 1),
                            _step("Simmer, stirring now and then", 5, False, "Stove"),
                            _step("Top with the sliced banana and 1 tsp honey", 1))]}
    result = _build_plan(raw)
    assert [s["start_min"] for s in result["timeline"]] == [0, 3, 4, 9]
    assert result["makespan_min"] == 10


def test_menu_with_no_cooking():
    """A menu of items served as they are has no steps: the plan is ready at once."""
    for raw in ({"dishes": []}, {"dishes": [_dish("White cheese")]}, {}):
        result = _build_plan(raw)
        assert result["timeline"] == []
        assert result["makespan_min"] == 0
        assert result["formatted"] == "⏱ Plan (0 min)\n  0:00  — Ready! ✓"


def test_estimates_code_cant_use_get_defaults():
    """Missing or negative minutes get a default, fractions round up, a step takes at least a
    minute, and an appliance outside the user's list is dropped instead of failing."""
    raw = {"dishes": [_dish("Eggs on toast",
                            {"action": "Crack 2 eggs into a bowl"},
                            _step("Fry the eggs", -3, False, "Stove"),
                            _step("Toast the bread", "2.5", False, "Grill"),
                            {"action": "Slide the eggs onto the toast", "minutes": None, "appliance": "stove"},
                            _step("Add a pinch of salt", 0),
                            {"minutes": 4},
                            "Serve")]}
    timeline = _build_plan(raw, appliances=["Stove"])["timeline"]
    assert [(s["duration_min"], s["hands_on"], s["resource"]) for s in timeline] == [
        (2, True, ""), (5, False, "Stove"), (3, False, ""), (5, False, "Stove"), (1, True, ""),
    ]


def test_items_served_as_they_are_get_no_steps():
    """A plan dish named like an item the menu serves as it is (any case, plurals) is left out,
    as in the prompt test where the model gave the cheese and olives a "serve" step."""
    raw = {"dishes": [
        _dish("Egg sandwich", _step("Boil 2 eggs", 10, False, "Stove"), _step("Slice the eggs into the bread", 2)),
        _dish("White Cheese", _step("Serve 50 g white cheese", 0, False)),
        _dish("Olive", _step("Serve 8 olives", 0, False)),
    ]}
    result = _build_plan(raw, served=["White cheese", "Olives"])
    assert {s["dish"] for s in result["timeline"]} == {"Egg sandwich"}
    assert result["makespan_min"] == 12


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def test_display_interleaves_dishes_under_one_heading():
    """One list in time order: a dish's steps that follow each other share one time line with a ↳
    for each after the first, and a dish picks up again after another dish's steps."""
    assert _build_plan(EGGS_AND_OMELETTE)["formatted"] == "\n".join([
        "⏱ Plan (12 min)",
        "  0:00  — Boiled eggs: Put 2 eggs in boiling water (10 min) [Stove]",
        "  0:03  — Greek omelette: Whisk 3 eggs with 30 g feta",
        "         ↳ Chop the tomato",
        "         ↳ Heat 1 tbsp olive oil in the pan",
        "         ↳ Pour in the eggs and tomato (3 min) [Stove]",
        "         ↳ Fold and slide onto a plate",
        "  0:10  — Boiled eggs: Cool in cold water",
        "         ↳ Peel and halve",
        "  0:12  — Ready! ✓",
    ])


def test_dishes_take_turns():
    """Two dishes that both wait come back in turns, each picking up after the other's steps."""
    raw = {"dishes": [
        _dish("Toast", _step("Slice the bread", 1), _step("Toast the bread", 3, False, "Toaster"),
              _step("Butter the toast", 1)),
        _dish("Fried eggs", _step("Crack 2 eggs into the pan", 1), _step("Fry the eggs", 3, False, "Stove"),
              _step("Slide the eggs onto a plate", 1)),
    ]}
    assert _build_plan(raw)["formatted"] == "\n".join([
        "⏱ Plan (6 min)",
        "  0:00  — Fried eggs: Crack 2 eggs into the pan",
        "         ↳ Fry the eggs (3 min) [Stove]",
        "  0:01  — Toast: Slice the bread",
        "         ↳ Toast the bread (3 min) [Toaster]",
        "  0:04  — Fried eggs: Slide the eggs onto a plate",
        "  0:05  — Toast: Butter the toast",
        "  0:06  — Ready! ✓",
    ])


def test_dish_names_lose_colons_and_keep_one_line():
    """Code keeps colons and line breaks out of dish names, so a time line's dish is the text
    before its first colon; a dish without a name is numbered."""
    raw = {"dishes": [
        {"dish": "Omelette: Greek style", "steps": [_step("Whisk the eggs:\nslowly", 1)]},
        {"dish": "", "steps": [_step("Toast the bread", 2, False, "Toaster")]},
    ]}
    result = _build_plan(raw)
    assert "Omelette Greek style: Whisk the eggs: slowly" in result["formatted"]
    assert "— Dish 2: Toast the bread (2 min) [Toaster]" in result["formatted"]
    for line in result["formatted"].splitlines()[1:-1]:
        assert line.split("— ")[1].split(":")[0] in {"Omelette Greek style", "Dish 2"}


def test_labels_follow_the_language():
    """Plan labels follow the response language, English by default."""
    raw = {"dishes": [_dish("Haşlanmış yumurta", _step("Yumurtaları haşla", 7, False, "Stove"))]}
    english = _build_plan(raw)["formatted"]
    assert english.splitlines()[0] == "⏱ Plan (7 min)"
    assert "(7 min) [Stove]" in english and "Ready! ✓" in english and "Hazır" not in english
    turkish = _build_plan(raw, "tr")["formatted"]
    assert turkish.splitlines()[0] == "⏱ Plan (7 dk)"
    assert "— Haşlanmış yumurta: Yumurtaları haşla (7 dk) [Stove]" in turkish
    assert turkish.endswith("  0:07  — Hazır! ✓")
    assert _build_plan({"dishes": [{"steps": [_step("Kızart", 1)]}]}, "tr")["timeline"][0]["dish"] == "Yemek 1"


def test_long_plans_show_hours():
    """Times are hours and minutes, so a plan over an hour reads 1:05."""
    raw = {"dishes": [_dish("Bread", _step("Bake the bread", 65, False, "Oven"))]}
    assert _build_plan(raw)["formatted"].endswith("  1:05  — Ready! ✓")
