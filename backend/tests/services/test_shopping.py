"""Tests for the shopping suggestion reply parsing and the code dedupe."""

from services.shopping import dish_names, new_suggestions, parse_suggestions, shopping_request


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


# Products made with an avoided item are dropped, while a product free of it stays
def test_new_suggestions_drop_products_made_with_avoided_items():
    items = [{"name": n, "reason": ""} for n in ("Walnut oil", "Feta cheese", "Gluten-free oats", "Pear")]
    kept = new_suggestions(items, [], avoid=["Walnuts", "Cheese", "Gluten"])
    assert [i["name"] for i in kept] == ["Gluten-free oats", "Pear"]


# The same item twice in one reply is kept once
def test_new_suggestions_drop_repeats_within_reply():
    items = [{"name": "Kiwi", "reason": "a"}, {"name": "Kiwis", "reason": "b"}]
    assert new_suggestions(items, []) == [{"name": "Kiwi", "reason": "a"}]
