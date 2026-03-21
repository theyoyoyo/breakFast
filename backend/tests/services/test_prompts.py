"""
Tests for system prompt personas (chat + suggestion).
Verifies template rendering, context injection, and health rules.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from services.suggestion import (
    build_chat_prompt,
    build_suggestion_prompt,
    build_system_prompt,
    _format_ingredients,
    _format_history,
    _format_preferences,
    _format_habits,
    _format_health_rules,
    _format_behavioral,
)


# ---------------------------------------------------------------------------
# Shared formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    def test_format_ingredients_empty(self):
        assert _format_ingredients([]) == "none listed yet"

    def test_format_ingredients_with_data(self):
        items = [
            {"name": "eggs", "quantity": "6", "unit": "pcs"},
            {"name": "milk", "quantity": "1", "unit": "L"},
        ]
        result = _format_ingredients(items)
        assert "eggs" in result
        assert "milk" in result

    def test_format_history_empty(self):
        assert _format_history([]) == "no history yet"

    def test_format_history_with_limit(self):
        meals = [{"meal_name": f"meal_{i}"} for i in range(10)]
        result = _format_history(meals, limit=3)
        # Should include last 3
        assert "meal_7" in result
        assert "meal_9" in result

    def test_format_preferences_empty(self):
        assert _format_preferences({}) == "none set yet"

    def test_format_preferences_with_data(self):
        result = _format_preferences({"favorite": "eggs"})
        assert "eggs" in result

    def test_format_habits_empty(self):
        assert _format_habits([]) == "none stated yet"

    def test_format_habits_with_data(self):
        result = _format_habits(["early breakfast", "no sugar"])
        assert "early breakfast" in result
        assert "no sugar" in result

    def test_format_health_rules_empty_uses_defaults(self):
        result = _format_health_rules([])
        assert "eggs" in result
        assert "refined sugar" in result

    def test_format_health_rules_custom(self):
        result = _format_health_rules(["Avoid gluten", "Favor omega-3"])
        assert "Avoid gluten" in result
        assert "Favor omega-3" in result
        assert "refined sugar" not in result

    def test_format_behavioral_empty(self):
        assert _format_behavioral(None) == ""
        assert _format_behavioral([]) == ""

    def test_format_behavioral_with_data(self):
        result = _format_behavioral(["eats eggs daily", "rarely has fruit"])
        assert "eats eggs daily" in result
        assert "DIVERSIFY" in result


# ---------------------------------------------------------------------------
# Chat persona
# ---------------------------------------------------------------------------

class TestChatPrompt:
    def test_renders_without_error(self):
        """Template braces are properly escaped — no KeyError."""
        prompt = build_chat_prompt(
            ingredient_inventory=[],
            recent_meal_history=[],
            user_preferences={},
            stated_habits=[],
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_chat_tone(self):
        prompt = build_chat_prompt([], [], {}, [])
        assert "arkadaş" in prompt.lower() or "samimi" in prompt.lower()

    def test_includes_ingredients(self):
        prompt = build_chat_prompt(
            ingredient_inventory=[{"name": "peynir", "quantity": "200", "unit": "g"}],
            recent_meal_history=[],
            user_preferences={},
            stated_habits=[],
        )
        assert "peynir" in prompt

    def test_includes_health_rules_from_db(self):
        prompt = build_chat_prompt(
            ingredient_inventory=[],
            recent_meal_history=[],
            user_preferences={},
            stated_habits=[],
            health_rules=["Avoid refined sugars", "Favor walnuts"],
        )
        assert "Avoid refined sugars" in prompt
        assert "Favor walnuts" in prompt

    def test_default_health_rules_when_none(self):
        prompt = build_chat_prompt([], [], {}, [])
        assert "eggs" in prompt
        assert "refined sugar" in prompt

    def test_json_block_present(self):
        """The JSON example block should render correctly (escaped braces)."""
        prompt = build_chat_prompt([], [], {}, [])
        assert '"meal_name"' in prompt
        assert '"ingredients"' in prompt

    def test_history_limit_is_3(self):
        """Chat persona uses last 3 meals only (lighter context)."""
        meals = [{"meal_name": f"meal_{i}"} for i in range(10)]
        prompt = build_chat_prompt([], meals, {}, [])
        assert "meal_9" in prompt
        assert "meal_7" in prompt
        assert "meal_0" not in prompt


# ---------------------------------------------------------------------------
# Suggestion persona
# ---------------------------------------------------------------------------

class TestSuggestionPrompt:
    def test_renders_without_error(self):
        prompt = build_suggestion_prompt([], [], {}, [])
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_professional_tone(self):
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "diyetisyen" in prompt.lower() or "profesyonel" in prompt.lower()

    def test_history_limit_is_10(self):
        """Suggestion persona uses last 10 meals (fuller context)."""
        meals = [{"meal_name": f"meal_{i}"} for i in range(15)]
        prompt = build_suggestion_prompt([], meals, {}, [])
        assert "meal_14" in prompt
        assert "meal_5" in prompt
        assert "meal_0" not in prompt

    def test_includes_health_rules(self):
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            health_rules=["Limit sodium intake"],
        )
        assert "Limit sodium intake" in prompt

    def test_json_block_present(self):
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"meal_name"' in prompt

    def test_includes_behavioral_patterns(self):
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            inferred_habits=["high egg consumption"],
        )
        assert "high egg consumption" in prompt
        assert "DIVERSIFY" in prompt

    def test_includes_nutrition_detail_fields(self):
        """Suggestion prompt should ask for detailed macro breakdown."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "protein" in prompt.lower()
        assert "kalori" in prompt.lower() or "kcal" in prompt.lower()
        assert "lif" in prompt.lower() or "fiber" in prompt.lower()
        assert "omega" in prompt.lower()
        assert "vitamin" in prompt.lower()

    def test_includes_advance_prep_tip(self):
        """Suggestion prompt should mention advance prep (Tavsiye) section."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "Tavsiye" in prompt

    def test_includes_avoid_list_guidance(self):
        """Suggestion prompt should tell LLM to respect avoid list."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "avoid" in prompt.lower() or "kaçın" in prompt.lower()

    def test_includes_seasonality(self):
        """Suggestion prompt should mention seasonal produce preference."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "mevsim" in prompt.lower()

    def test_includes_turkey_context(self):
        """Suggestion prompt should mention Turkey-available ingredients."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "Türkiye" in prompt

    def test_nutrition_detail_in_json_block(self):
        """JSON block should include nutrition_detail fields."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"nutrition_detail"' in prompt
        assert '"calories_kcal"' in prompt
        assert '"protein_g"' in prompt
        assert '"advance_prep_tip"' in prompt


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_build_system_prompt_is_chat_prompt(self):
        """build_system_prompt is an alias for build_chat_prompt."""
        assert build_system_prompt is build_chat_prompt
