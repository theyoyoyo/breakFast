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
    format_meal_detail,
    format_history_detailed,
)


class TestKnowledgeFormatters:
    # Empty ingredients returns fallback string
    def test_format_ingredients_empty(self):
        assert format_ingredients([]) == "none listed yet"

    # Ingredients with quantities render correctly
    def test_format_ingredients_with_data(self):
        items = [{"name": "eggs", "quantity": "6", "unit": "pcs"}]
        result = format_ingredients(items)
        assert "eggs" in result
        assert "6" in result

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
