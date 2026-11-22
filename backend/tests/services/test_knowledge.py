"""
Tests for the shared knowledge module — context formatters used by all personas.
Verifies that knowledge.py formatters produce the same output as the old suggestion.py ones.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.knowledge import (
    format_history,
    format_history_detailed,
    format_history_for_weekly_review,
    format_ingredient_item,
    format_ingredients,
    format_meal_detail,
)


class TestKnowledgeFormatters:
    # Empty ingredients returns fallback string
    def test_format_ingredients_empty(self):
        assert format_ingredients([]) == "none listed yet"

    # Ingredients render as name-only list (no group_name)
    def test_format_ingredients_with_data(self):
        items = [{"name": "eggs"}, {"name": "milk"}]
        result = format_ingredients(items)
        assert "eggs" in result
        assert "milk" in result

    # Grouped ingredients render with group labels for LLM context
    def test_format_ingredients_grouped(self):
        items = [
            {"name": "sucuk", "group_name": "🐄 Animal Products"},
            {"name": "tomato", "group_name": "🥬 Produce"},
            {"name": "salt", "group_name": "🍽️ Other"},
        ]
        result = format_ingredients(items)
        assert "[🐄 Animal Products] sucuk" in result
        assert "[🥬 Produce] tomato" in result
        assert "[🍽️ Other] salt" in result

    # Empty history returns fallback
    def test_format_history_empty(self):
        assert format_history([]) == "no history yet"

    # History comes newest first, so the limit keeps the newest meals
    def test_format_history_with_limit(self):
        meals = [{"meal_name": f"meal_{i}"} for i in range(10)]
        result = format_history(meals, limit=3)
        assert "meal_0" in result
        assert "meal_9" not in result

    # Detailed history keeps the newest meals too
    def test_format_history_detailed_keeps_newest(self):
        meals = [{"meal_name": f"meal_{i}", "ingredients": "[]"} for i in range(10)]
        result = format_history_detailed(meals, limit=3)
        assert "meal_0" in result
        assert "meal_9" not in result

    # A menu meal (DB strings, as fetched) lists its dishes with their ingredients and its simple items
    def test_format_meal_detail_menu_items(self):
        menu = [
            {"name": "Menemen", "ingredients": [{"name": "Yumurta"}, {"name": "Domates"}]},
            {"name": "Beyaz peynir", "amount": 50, "unit": "g", "ingredients": []},
        ]
        meal = {"meal_name": "Kahvaltı", "ingredients": "[]", "menu_items": json.dumps(menu)}
        assert format_meal_detail(meal) == "Kahvaltı: Menemen (Yumurta, Domates), Beyaz peynir"

    # The weekly review lists a menu meal's items too
    def test_weekly_review_lists_menu_items(self):
        menu = [{"name": "Toast", "ingredients": [{"name": "Bread"}, {"name": "Butter"}]}]
        meal = {"meal_name": "Toast", "ingredients": "[]", "menu_items": json.dumps(menu), "logged_at": "2026-10-30 08:00"}
        assert format_history_for_weekly_review([meal]) == "[2026-10-30] Toast — Toast (Bread, Butter)"

    # Meal detail formats name + ingredients
    def test_format_meal_detail_basic(self):
        meal = {"meal_name": "Menemen", "ingredients": '["yumurta", "domates"]'}
        result = format_meal_detail(meal)
        assert "Menemen" in result
        assert "yumurta" in result

    # Meal detail handles pre-parsed list
    def test_format_meal_detail_list_ingredients(self):
        meal = {"meal_name": "Toast", "ingredients": ["ekmek", "peynir"]}
        result = format_meal_detail(meal)
        assert "ekmek" in result

    # Detailed history includes ingredient info
    def test_format_history_detailed(self):
        meals = [
            {"meal_name": "Menemen", "ingredients": '["yumurta", "domates"]'},
            {"meal_name": "Toast", "ingredients": '["ekmek"]'},
        ]
        result = format_history_detailed(meals, limit=5)
        assert "Menemen" in result
        assert "yumurta" in result
        assert "Toast" in result

    # Detailed history with no meals returns fallback
    def test_format_history_detailed_empty(self):
        assert format_history_detailed([]) == "no history yet"


class TestFormatIngredientItem:
    # Structured ingredient extracts name
    def test_structured_ingredient(self):
        result = format_ingredient_item({"name": "yumurta"})
        assert result == "yumurta"

    # Plain string ingredient
    def test_string_ingredient(self):
        result = format_ingredient_item("peynir")
        assert result == "peynir"


class TestMealDetailStructured:
    # Meal detail with structured ingredients extracts names
    def test_structured_ingredients(self):
        meal = {
            "meal_name": "Menemen",
            "ingredients": [
                {"name": "yumurta"},
                {"name": "domates"},
            ]
        }
        result = format_meal_detail(meal)
        assert "Menemen" in result
        assert "yumurta" in result
        assert "domates" in result

    # Meal detail with JSON-encoded structured ingredients
    def test_structured_json_string(self):
        import json
        meal = {
            "meal_name": "Toast",
            "ingredients": json.dumps([{"name": "ekmek"}])
        }
        result = format_meal_detail(meal)
        assert "ekmek" in result

    # Meal detail still works with old string format
    def test_backward_compat_strings(self):
        meal = {"meal_name": "Basit", "ingredients": '["yumurta", "peynir"]'}
        result = format_meal_detail(meal)
        assert "yumurta" in result
        assert "peynir" in result


# Today's date reads as an English sentence part, with the country when set
def test_format_today():
    from datetime import date

    from services.knowledge import format_today
    day = date(2026, 10, 27)
    assert format_today(day) == "Tuesday, 27 October 2026"
    assert format_today(day, "Türkiye") == "Tuesday, 27 October 2026, in Türkiye"


# Saved favorites read as a name and one plain item list, each item once, from the DB's JSON or an old flat meal
def test_format_favorite_meals():
    from services.knowledge import format_favorite_meals
    menu = json.dumps([
        {"name": "Omelette", "ingredients": [{"name": "Eggs"}, {"name": "Cheddar"}]},
        {"name": "Boiled egg", "ingredients": [{"name": "Eggs"}]},
        {"name": "Orange juice", "amount": 1, "unit": "glass", "ingredients": []},
    ])
    meals = [{"meal_name": "Egg plate", "menu_items": menu}, {"meal_name": "Toast", "ingredients": '["Bread"]'}]
    assert format_favorite_meals(meals) == "- Egg plate: Eggs, Cheddar, Orange juice\n- Toast: Bread"
    assert format_favorite_meals([]) == "none saved yet"
