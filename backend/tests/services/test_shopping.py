"""Tests for the shopping suggestion reply parsing and the code dedupe."""

import random

from services.shopping import (
    dish_names,
    new_suggestions,
    parse_suggestions,
    pick_input,
    random_share,
    shopping_request,
    taste_hints,
)


# A schema-shaped reply gives its items, names and reasons trimmed
def test_parse_reads_items():
    reply = '{"items": [{"name": " Salmon ", "reason": "Omega-3"}, {"name": "Kiwi", "reason": ""}]}'
    assert parse_suggestions(reply) == [
        {"name": "Salmon", "reason": "Omega-3"},
        {"name": "Kiwi", "reason": ""},
    ]


# Items without a usable name are skipped
def test_parse_skips_nameless_items():
    reply = '{"items": [{"name": ""}, "Kiwi", {"reason": "x"}, {"name": "Pear"}]}'
    assert parse_suggestions(reply) == [{"name": "Pear", "reason": ""}]


# Anything that isn't a JSON object with an items list counts as unparseable
def test_parse_rejects_other_shapes():
    assert parse_suggestions("Here are some ideas: salmon, kiwi") is None
    assert parse_suggestions('[{"name": "Salmon"}]') is None
    assert parse_suggestions('{"items": "Salmon"}') is None
    assert parse_suggestions(None) is None


# Known names are dropped by exact match, so a more specific product survives
def test_new_suggestions_drop_exact_matches_only():
    items = [
        {"name": "Strawberries", "reason": ""},
        {"name": "Frozen strawberries", "reason": ""},
        {"name": "Almond milk", "reason": ""},
        {"name": "eggs", "reason": ""},
    ]
    known = ["Strawberry", "Milk", "Egg"]
    assert [i["name"] for i in new_suggestions(items, known)] == ["Frozen strawberries", "Almond milk"]


# Names that aren't one product and the user's own dishes are left out, so alternatives come as separate items
def test_new_suggestions_drop_vague_names_and_dishes():
    items = [{"name": n, "reason": ""} for n in (
        "Leafy greens (e.g. spinach)", "Milk or yogurt", "Spinach", "Chard", "Menemen", "Tomatoes",
    )]
    kept = new_suggestions(items, [], dishes=["Menemen", "Sucuklu tost"])
    assert [i["name"] for i in kept] == ["Spinach", "Chard", "Tomatoes"]


# Dishes are meal names and menu items made with ingredients; simple items and meals named after
# one of their own ingredients stay products
def test_dish_names_come_from_meals_and_their_menus():
    meals = [
        {"meal_name": "Weekend breakfast", "menu_items": [
            {"name": "Menemen", "ingredients": [{"name": "Eggs"}, {"name": "Tomatoes"}]},
            {"name": "Beyaz peynir", "amount": 50, "unit": "g", "ingredients": []},
            {"name": "Yogurt", "ingredients": [{"name": "Yogurt"}, {"name": "Honey"}]},
        ]},
        {"meal_name": "Simit", "ingredients": ["Simit", "Tea"]},
        {"meal_name": "Menemen", "ingredients": [{"name": "Eggs"}]},
    ]
    assert dish_names(meals) == ["Weekend breakfast", "Menemen"]


# The request names the reply language and, for Suggest More, what was already shown
def test_shopping_request_names_the_language_and_shown_items():
    assert shopping_request("en") == "Generate shopping suggestions for me, in English."
    assert shopping_request("tr", ["Kiwi", "Pear"]) == (
        "Generate more shopping suggestions for me, in Turkish, all different from these, "
        "which I've already seen: Kiwi, Pear."
    )


# The request starts with this press's share of the fridge, so the language stays the last thing said
def test_shopping_request_lists_the_fridge_share():
    assert shopping_request("en", fridge=["Eggs", "Bread"]) == (
        "Some of what I have now: Eggs, Bread.\nGenerate shopping suggestions for me, in English."
    )


# A random share is about 70% of the items, each once, at least one, and the same for the same seed
def test_random_share():
    items = [f"Item {i}" for i in range(10)]
    drawn = random_share(items, random.Random(1))
    assert len(drawn) == 7 and len(set(drawn)) == 7 and set(drawn) <= set(items)
    assert random_share(items, random.Random(1)) == drawn
    assert len(random_share(["Eggs"], random.Random(1))) == 1
    assert random_share([], random.Random(1)) == []


# Taste hints come from likes, staples, saved meals with their items, habits, patterns and high ratings
def test_taste_hints():
    ctx = {
        "preferences": {"fav:pancakes": "Pancakes", "dislike:olives": "Olives"},
        "favorites": ["Cheddar"],
        "favorite_meals": [{"meal_name": "Avocado toast", "ingredients": '["Bread", "Avocado"]'}],
        "stated_habits": ["Sweet breakfasts on weekends"],
        "inferred_habits": ["Rarely eaten, suggest more: fish"],
        "ratings": [{"product_name": "Honey", "rating": 9}, {"product_name": "Oats", "rating": 3}],
    }
    assert taste_hints(ctx) == [
        "Likes Pancakes",
        "Keeps around: Cheddar",
        "Saved favorite meal: Avocado toast: Bread, Avocado",
        "Habit: Sweet breakfasts on weekends",
        "Pattern: Rarely eaten, suggest more: fish",
        "Rated 9/10: Honey",
    ]


# One press draws a share of the fridge names and of the taste hints
def test_pick_input():
    ctx = {"ingredients": [{"name": f"Item {i}"} for i in range(10)], "favorites": ["A", "B", "C"]}
    fridge, hints = pick_input(ctx, random.Random(1))
    assert len(fridge) == 7 and set(fridge) <= {f"Item {i}" for i in range(10)}
    assert len(hints) == 2 and set(hints) <= {"Keeps around: A", "Keeps around: B", "Keeps around: C"}


# The same item twice in one reply is kept once
def test_new_suggestions_drop_repeats_within_reply():
    items = [{"name": "Kiwi", "reason": "a"}, {"name": "Kiwis", "reason": "b"}]
    assert new_suggestions(items, []) == [{"name": "Kiwi", "reason": "a"}]
