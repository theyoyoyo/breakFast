"""Tests for the fridge check that flags suggested ingredients the user doesn't have."""

from services.fridge import find_missing_ingredients, meal_ingredient_names

INVENTORY = [
    {"name": "Yumurta"},
    {"name": "Domates"},
    {"name": "Beyaz peynir"},
    {"name": "Olive"},
    {"name": "Un", "group_name": "🫙 Pantry"},
    {"name": "Tuz", "group_name": "🫙 Pantry"},
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


# Everything in the fridge, ignoring case and plurals, is not flagged
def test_fridge_items_match_by_exact_name():
    inventory = [{"name": n} for n in ("Eggs", "Tomatoes", "Cream cheese", "Olive")]
    meal = _meal(
        {"name": "Omelette", "ingredients": [{"name": "egg"}, {"name": "TOMATO"}]},
        {"name": "Olives", "amount": 10, "unit": "pcs", "ingredients": []},
        {"name": "cream cheese", "amount": 50, "unit": "g", "ingredients": []},
    )
    assert find_missing_ingredients(meal, inventory) == []


# A name longer than its fridge name is another or a prepared item, so it's flagged (#115)
def test_longer_names_are_not_their_fridge_item():
    inventory = [{"name": "Egg"}, {"name": "Simit"}, {"name": "White cheese"}, {"name": "Yogurt"}]
    meal = _meal(
        {"name": "Poached egg", "amount": 2, "unit": "pcs", "ingredients": []},
        {"name": "Simit with tahini dipping sauce", "amount": 1, "unit": "pcs", "ingredients": []},
        {"name": "Plate", "ingredients": [{"name": "White cheese (peynir)"}, {"name": "Greek yogurt or milk"}]},
    )
    assert find_missing_ingredients(meal, inventory) == [
        "Poached egg", "Simit with tahini dipping sauce", "White cheese (peynir)", "Greek yogurt or milk",
    ]


# A shorter name may be another product, so it's flagged even when it is a fridge name's start or end
def test_shorter_names_are_not_their_fridge_item():
    inventory = [{"name": n} for n in ("Olive oil", "Cream cheese", "Cooked rice", "White cheese", "Blueberries")]
    meal = _meal(
        {"name": "Olives", "amount": 10, "unit": "pcs", "ingredients": []},
        {"name": "Cheese", "amount": 50, "unit": "g", "ingredients": []},
        {"name": "Bowl", "ingredients": [{"name": "Cream"}, {"name": "Rice"}, {"name": "Blueberry"}]},
    )
    assert find_missing_ingredients(meal, inventory) == ["Olives", "Cheese", "Cream", "Rice"]


# Avoided dishes and ingredients are found by exact name, so a longer name the user hasn't banned passes
def test_find_avoided_matches_exact_names():
    from services.fridge import find_avoided
    meal = _meal(
        {"name": "Granola bowl", "ingredients": [{"name": "Granola"}, {"name": "Almond milk"}]},
        {"name": "almond", "amount": 20, "unit": "g", "ingredients": []},
        {"name": "Beyaz peynir", "amount": 50, "unit": "g", "ingredients": []},
    )
    assert find_avoided(meal, ["Almonds", "Peynir"]) == ["almond"]
    assert find_avoided(meal, ["Granola bowl", "Almond milk"]) == ["Granola bowl", "Almond milk"]
    assert find_avoided(meal, []) == []
    assert find_avoided(None, ["Almonds"]) == []


# Pantry-group items count as fridge items
def test_pantry_group_items_are_available():
    meal = _meal({"name": "Pancakes", "ingredients": [{"name": "Un"}, {"name": "Yumurta"}]})
    assert find_missing_ingredients(meal, INVENTORY) == []


# Basics like salt and oil count only when logged; nothing is assumed
def test_basics_count_only_when_logged():
    meal = _meal({"name": "Menemen", "ingredients": [
        {"name": "Yumurta"}, {"name": "Tuz"}, {"name": "Zeytinyağı"}, {"name": "Pul biber"},
    ]})
    assert find_missing_ingredients(meal, INVENTORY) == ["Zeytinyağı", "Pul biber"]


# Ingredients outside the fridge are listed once, in order
def test_flags_missing_ingredients_once():
    meal = _meal(
        {"name": "Avocado toast", "ingredients": [{"name": "Avocado"}, {"name": "Sourdough"}, {"name": "Tuz"}]},
        {"name": "Avocado", "amount": 1, "unit": "adet", "ingredients": []},
    )
    assert find_missing_ingredients(meal, INVENTORY) == ["Avocado", "Sourdough"]


# Water is a utility like gas and electricity, not a fridge item; bottled waters still are
def test_water_is_never_missing():
    meal = _meal({"name": "Boiled eggs", "ingredients": [
        {"name": "Yumurta"}, {"name": "Water"}, {"name": "Hot water"}, {"name": "Sıcak su"},
        {"name": "Maden suyu"}, {"name": "Sparkling water"},
    ]})
    assert find_missing_ingredients(meal, INVENTORY) == ["Maden suyu", "Sparkling water"]


# A draft without a meal JSON (e.g. "your fridge is empty") has nothing to check
def test_no_meal_means_nothing_missing():
    assert find_missing_ingredients(None, INVENTORY) == []
    assert find_missing_ingredients(["not", "a", "meal"], INVENTORY) == []


# Exact names match across case, Turkish letters and simple plurals
def test_same_name_ignores_case_letters_and_plurals():
    from services.fridge import same_name
    assert same_name("Strawberry", "strawberries")
    assert same_name("Zeytinler", "zeytin")
    assert same_name("Şeftali", "seftali")
    assert same_name("Eggs", "Egg")
    assert same_name("Blueberry", "Blueberries")


# Every word counts, so a longer or shorter name is a different product
def test_same_name_needs_every_word():
    from services.fridge import same_name
    assert not same_name("Frozen strawberries", "Strawberries")
    assert not same_name("Almond milk", "Milk")
    assert not same_name("Yogurt", "Greek yogurt")
    assert not same_name("", "")
