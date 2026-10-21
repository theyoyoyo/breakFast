"""
Tests for the shared knowledge module — context formatters used by all personas.
Verifies that knowledge.py formatters produce the same output as the old suggestion.py ones.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.knowledge import (
    format_ingredients,
    format_history,
    format_preferences,
    format_habits,
    format_health_rules,
    format_avoid_list,
    format_behavioral,
    format_user_profile,
    format_supplements,
    format_ingredient_item,
    format_meal_detail,
    format_history_detailed,
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

    # History respects limit parameter
    def test_format_history_with_limit(self):
        meals = [{"meal_name": f"meal_{i}"} for i in range(10)]
        result = format_history(meals, limit=3)
        assert "meal_9" in result
        assert "meal_0" not in result

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


class TestKnowledgeMatchesSuggestion:
    """Verify knowledge.py exports are the same functions used by suggestion.py aliases."""

    # Knowledge formatters are imported and re-exported in suggestion.py
    def test_suggestion_uses_knowledge_formatters(self):
        from services.suggestion import (
            _format_ingredients,
            _format_history,
            _format_preferences,
            _format_habits,
            _format_health_rules,
            _format_avoid_list,
            _format_behavioral,
            _format_user_profile,
            _format_supplements,
        )
        assert _format_ingredients is format_ingredients
        assert _format_history is format_history
        assert _format_preferences is format_preferences
        assert _format_habits is format_habits
        assert _format_health_rules is format_health_rules
        assert _format_avoid_list is format_avoid_list
        assert _format_behavioral is format_behavioral
        assert _format_user_profile is format_user_profile
        assert _format_supplements is format_supplements
