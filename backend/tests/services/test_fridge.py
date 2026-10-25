"""Tests for the fridge check that flags suggested ingredients the user doesn't have."""

from services.fridge import find_missing_ingredients, meal_ingredient_names

INVENTORY = [
    {"name": "Yumurta"},
    {"name": "Domates"},
    {"name": "Beyaz peynir"},
    {"name": "Olive"},
    {"name": "Un", "group_name": "🫙 Pantry"},
]


def _meal(*items):
    return {"menu_name": "Test", "menu": list(items)}


# Dish sub-ingredients and simple served items are both collected
def test_collects_dish_ingredients_and_simple_items():
    meal = _meal(
        {"name": "Menemen", "ingredients": [{"name": "Yumurta"}, {"name": "Domates"}]},
        {"name": "Olives", "amount": 10, "unit": "adet", "ingredients": []},
    )
    assert meal_ingredient_names(meal) == ["Yumurta", "Domates", "Olives"]


# Old flat-format meals list their ingredients at the top level
def test_collects_flat_format_ingredients():
    meal = {"meal_name": "Toast", "ingredients": [{"name": "Bread"}, "Butter"]}
    assert meal_ingredient_names(meal) == ["Bread", "Butter"]


# Everything in the fridge, compared loosely (case, plural, partial name), is not flagged
def test_fridge_items_match_loosely():
    meal = _meal(
        {"name": "Menemen", "ingredients": [{"name": "yumurta"}, {"name": "DOMATES"}]},
        {"name": "Olives", "amount": 10, "unit": "adet", "ingredients": []},
        {"name": "Peynir", "amount": 50, "unit": "g", "ingredients": []},
    )
    assert find_missing_ingredients(meal, INVENTORY) == []


# Pantry-group items count as fridge items
def test_pantry_group_items_are_available():
    meal = _meal({"name": "Pancakes", "ingredients": [{"name": "Un"}, {"name": "Yumurta"}]})
    assert find_missing_ingredients(meal, INVENTORY) == []


# Salt, oils and common spices are always available, in English or Turkish
def test_basics_are_always_available():
    meal = _meal({"name": "Menemen", "ingredients": [
        {"name": "Yumurta"}, {"name": "Zeytinyağı"}, {"name": "Tuz"},
        {"name": "Pul biber"}, {"name": "Extra virgin olive oil"}, {"name": "Black pepper"},
    ]})
    assert find_missing_ingredients(meal, INVENTORY) == []


# Ingredients outside the fridge and the basics are listed once, in order
def test_flags_missing_ingredients_once():
    meal = _meal(
        {"name": "Avocado toast", "ingredients": [{"name": "Avocado"}, {"name": "Sourdough"}, {"name": "Tuz"}]},
        {"name": "Avocado", "amount": 1, "unit": "adet", "ingredients": []},
    )
    assert find_missing_ingredients(meal, INVENTORY) == ["Avocado", "Sourdough"]


# Produce that only shares a word with a basic is still checked
def test_green_pepper_and_fresh_mint_are_not_basics():
    meal = _meal({"name": "Salad", "ingredients": [{"name": "Green pepper"}, {"name": "Fresh mint"}]})
    assert find_missing_ingredients(meal, INVENTORY) == ["Green pepper", "Fresh mint"]


# A draft without a meal JSON (e.g. "your fridge is empty") has nothing to check
def test_no_meal_means_nothing_missing():
    assert find_missing_ingredients(None, INVENTORY) == []
    assert find_missing_ingredients(["not", "a", "meal"], INVENTORY) == []
