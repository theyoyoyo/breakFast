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
    _format_user_profile,
    _format_supplements,
    _format_avoid_list,
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

    def test_format_health_rules_empty_deprioritize_not_exclude(self):
        result = _format_health_rules([])
        assert "deprioritize" in result
        assert "NEVER fully exclude" in result

    def test_format_health_rules_custom(self):
        result = _format_health_rules(["Avoid gluten", "Favor omega-3"])
        assert "Avoid gluten" in result
        assert "Favor omega-3" in result
        assert "refined sugar" not in result

    def test_format_avoid_list_empty(self):
        assert "No items" in _format_avoid_list(None)
        assert "No items" in _format_avoid_list([])

    def test_format_avoid_list_with_data(self):
        result = _format_avoid_list(["shellfish", "peanuts"])
        assert "shellfish" in result
        assert "peanuts" in result
        assert "NEVER" in result
        assert "cross-contamination" in result

    def test_format_behavioral_empty(self):
        assert _format_behavioral(None) == ""
        assert _format_behavioral([]) == ""

    def test_format_behavioral_with_data(self):
        result = _format_behavioral(["eats eggs daily", "rarely has fruit"])
        assert "eats eggs daily" in result
        assert "DIVERSIFY" in result

    def test_format_user_profile_empty(self):
        assert "Not provided" in _format_user_profile(None)
        assert "Not provided" in _format_user_profile({})

    def test_format_user_profile_with_data(self):
        profile = {
            "age": 30, "gender": "erkek",
            "height_cm": 180, "weight_kg": 75,
            "activity_level": "orta",
        }
        result = _format_user_profile(profile)
        assert "30" in result
        assert "180" in result
        assert "75" in result
        assert "orta" in result

    def test_format_supplements_empty(self):
        assert "No supplements" in _format_supplements(None)
        assert "No supplements" in _format_supplements([])

    def test_format_supplements_daily(self):
        supps = [{"name": "Vitamin D", "frequency": "daily", "contents": "1000IU D3"}]
        result = _format_supplements(supps)
        assert "Vitamin D" in result
        assert "daily" in result
        assert "1000IU D3" in result

    def test_format_supplements_sometimes_taken(self):
        supps = [{"name": "Omega-3", "frequency": "sometimes", "contents": "1000mg EPA/DHA", "taken_today": True}]
        result = _format_supplements(supps)
        assert "taken today" in result

    def test_format_supplements_sometimes_not_taken(self):
        supps = [{"name": "Omega-3", "frequency": "sometimes", "contents": "", "taken_today": False}]
        result = _format_supplements(supps)
        assert "NOT taken today" in result


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
        assert "friendly" in prompt.lower() or "warm" in prompt.lower() or "friend" in prompt.lower()

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
        assert "deprioritize" in prompt
        assert "NEVER fully exclude" in prompt

    def test_json_block_present(self):
        """The JSON example block should render correctly (escaped braces)."""
        prompt = build_chat_prompt([], [], {}, [])
        assert '"meal_name"' in prompt
        assert '"ingredients"' in prompt

    def test_includes_avoid_list_empty(self):
        prompt = build_chat_prompt([], [], {}, [])
        assert "No items on avoid list" in prompt

    def test_includes_avoid_list_with_items(self):
        prompt = build_chat_prompt([], [], {}, [], avoid_list=["shellfish", "peanuts"])
        assert "shellfish" in prompt
        assert "peanuts" in prompt
        assert "NEVER" in prompt

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
        assert "dietitian" in prompt.lower() or "professional" in prompt.lower()

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
        assert "calori" in prompt.lower() or "kcal" in prompt.lower()
        assert "fiber" in prompt.lower()
        assert "omega" in prompt.lower()
        assert "vitamin" in prompt.lower()

    def test_includes_advance_prep_tip(self):
        """Suggestion prompt should mention advance prep section."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "Tip:" in prompt or "advance prep" in prompt.lower()

    def test_includes_avoid_list_empty(self):
        """Suggestion prompt should show no items when avoid list is empty."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "No items on avoid list" in prompt

    def test_includes_avoid_list_with_items(self):
        """Suggestion prompt should inject actual avoid items."""
        prompt = build_suggestion_prompt([], [], {}, [], avoid_list=["gluten", "lactose"])
        assert "gluten" in prompt
        assert "lactose" in prompt
        assert "NEVER" in prompt

    def test_includes_seasonality(self):
        """Suggestion prompt should mention seasonal produce preference."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "seasonal" in prompt.lower()

    def test_includes_turkey_context(self):
        """Suggestion prompt should mention Turkey-available ingredients."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "Turkey" in prompt

    def test_nutrition_detail_in_json_block(self):
        """JSON block should include nutrition_detail fields."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"nutrition_detail"' in prompt
        assert '"calories_kcal"' in prompt
        assert '"protein_g"' in prompt
        assert '"advance_prep_tip"' in prompt

    def test_includes_user_profile(self):
        """Suggestion prompt should render user physical profile."""
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            user_profile={"age": 28, "gender": "kadın", "height_cm": 165, "weight_kg": 60},
        )
        assert "28" in prompt
        assert "165" in prompt
        assert "60" in prompt

    def test_includes_supplements(self):
        """Suggestion prompt should render supplement info."""
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            supplements=[
                {"name": "B12", "frequency": "daily", "contents": "1000mcg"},
                {"name": "Fish oil", "frequency": "sometimes", "contents": "EPA/DHA", "taken_today": False},
            ],
        )
        assert "B12" in prompt
        assert "1000mcg" in prompt
        assert "Fish oil" in prompt
        assert "NOT taken today" in prompt

    def test_profile_and_supplements_default_when_none(self):
        """When no profile/supplements given, should still render without error."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "Not provided" in prompt
        assert "No supplements" in prompt

    def test_includes_calorie_calculation_guidance(self):
        """Prompt should mention Harris-Benedict or calorie calculation."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "calori" in prompt.lower() or "kcal" in prompt.lower()
        assert "30%" in prompt or "30" in prompt

    def test_includes_experienced_cook_note(self):
        """Prompt should indicate user is an experienced cook."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "experienced cook" in prompt.lower()


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_build_system_prompt_is_chat_prompt(self):
        """build_system_prompt is an alias for build_chat_prompt."""
        assert build_system_prompt is build_chat_prompt
