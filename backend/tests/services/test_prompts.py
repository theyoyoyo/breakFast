"""
Tests for system prompt personas (chat + suggestion).
Verifies template rendering, context injection, and health rules.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.suggestion import (
    build_chat_prompt,
    build_suggestion_prompt,
    build_analyst_prompt,
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
from services.personas import (
    build_pipeline_analyst_prompt,
    build_scheduler_prompt,
    build_scheduler_user_message,
    build_shopping_prompt,
    build_weekly_analyst_prompt_with_meals,
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
        # History comes newest first, so the first 3 are the newest
        assert "meal_0" in result
        assert "meal_2" in result
        assert "meal_3" not in result

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

    # Formats rules with priority labels when passed as dicts
    def test_format_health_rules_custom(self):
        rules = [
            {"rule_text": "Avoid gluten", "priority": "critical"},
            {"rule_text": "Favor omega-3", "priority": "low"},
        ]
        result = _format_health_rules(rules)
        assert "TOP PRIORITY" in result
        assert "Avoid gluten" in result
        assert "Nice to have" in result
        assert "Favor omega-3" in result
        assert "refined sugar" not in result

    # Backwards-compatible with plain string lists
    def test_format_health_rules_plain_strings(self):
        result = _format_health_rules(["Avoid gluten", "Favor omega-3"])
        assert "Avoid gluten" in result
        assert "Favor omega-3" in result

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

    def test_no_json_block(self):
        """Chat persona replies in plain text; meal blocks only come from Suggest."""
        prompt = build_chat_prompt([], [], {}, [])
        assert "```json" not in prompt

    def test_includes_avoid_list_empty(self):
        prompt = build_chat_prompt([], [], {}, [])
        assert "No items on avoid list" in prompt

    def test_includes_avoid_list_with_items(self):
        prompt = build_chat_prompt([], [], {}, [], avoid_list=["shellfish", "peanuts"])
        assert "shellfish" in prompt
        assert "peanuts" in prompt
        assert "NEVER" in prompt

    def test_history_limit_is_3(self):
        """Chat persona uses the newest 3 meals only (lighter context); history comes newest first."""
        meals = [{"meal_name": f"meal_{i}"} for i in range(10)]
        prompt = build_chat_prompt([], meals, {}, [])
        assert "meal_0" in prompt
        assert "meal_2" in prompt
        assert "meal_3" not in prompt
        assert "meal_9" not in prompt


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

    def test_history_limit_is_4(self):
        """Suggestion persona uses the newest 4 meals; history comes newest first."""
        meals = [{"meal_name": f"meal_{i}"} for i in range(15)]
        prompt = build_suggestion_prompt([], meals, {}, [])
        assert "meal_0" in prompt
        assert "meal_3" in prompt
        assert "meal_4" not in prompt
        assert "meal_14" not in prompt

    def test_includes_health_rules(self):
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            health_rules=["Limit sodium intake"],
        )
        assert "Limit sodium intake" in prompt

    def test_json_block_present(self):
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"menu_name"' in prompt
        assert '"menu"' in prompt

    def test_includes_behavioral_patterns(self):
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            inferred_habits=["high egg consumption"],
        )
        assert "high egg consumption" in prompt
        assert "DIVERSIFY" in prompt

    def test_includes_nutrition_guidance(self):
        """Suggestion prompt should carry internal nutrition guidance."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "protein" in prompt.lower()
        assert "calori" in prompt.lower() or "kcal" in prompt.lower()
        assert "fiber" in prompt.lower()
        assert "omega" in prompt.lower()

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

    def test_favors_widely_available_ingredients(self):
        """Suggestion prompt should steer toward widely available ingredients."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "widely available" in prompt

    def test_nutrition_note_in_json_block(self):
        """JSON block should include the short nutrition note and prep time."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"nutrition_note"' in prompt
        assert '"prep_time_min"' in prompt
        assert '"nutrition_detail"' not in prompt

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
        # 'sometimes' supplements not taken today are left out
        assert "Fish oil" not in prompt

    def test_profile_and_supplements_default_when_none(self):
        """When no profile/supplements given, should still render without error."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "Not provided" in prompt
        assert "None taken today." in prompt

    def test_includes_calorie_calculation_guidance(self):
        """Prompt should mention Harris-Benedict or calorie calculation."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "calori" in prompt.lower() or "kcal" in prompt.lower()
        assert "30%" in prompt or "30" in prompt

    def test_includes_experienced_cook_note(self):
        """Prompt should indicate user is an experienced cook."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "experienced cook" in prompt.lower()

    def test_mode_none_has_no_mode_instruction(self):
        """No mode = no extra mode block appended."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "MODE:" not in prompt

    def test_mode_favorites_appends_comfort_instructions(self):
        """Favorites mode should add comfort/favorites instructions."""
        prompt = build_suggestion_prompt([], [], {}, [], mode="favorites")
        assert "FAVORITES" in prompt
        assert "comfort" in prompt.lower()

    SAVED = [{"meal_name": "Cheddar toast", "menu_items": [
        {"name": "Cheddar toast", "ingredients": [{"name": "Bread"}, {"name": "Cheddar"}]},
        {"name": "Orange juice", "amount": 1, "unit": "glass", "ingredients": []},
    ]}]

    RATINGS = [{"product_name": "Strawberries", "rating": 9}, {"product_name": "Oats", "rating": 3}]

    def test_mode_favorites_lists_taste_hints(self):
        """Favorites mode lists the saved meals with their items, the staples and the ratings as hints to weigh."""
        prompt = build_suggestion_prompt(
            [], [], {}, [], mode="favorites",
            favorite_meals=self.SAVED, favorites=["Bagels", "Cheddar"], ratings=self.RATINGS,
        )
        # One plain item list, so the model doesn't copy "Cheddar toast (Bread, …)" into dish names
        assert "- Cheddar toast: Bread, Cheddar, Orange juice" in prompt
        assert "Cheddar toast (" not in prompt
        assert "Their favorite ingredients: Bagels, Cheddar" in prompt
        assert "High-rated (favour these): Strawberries" in prompt
        assert "Low-rated (avoid or minimise): Oats" in prompt
        assert "Weigh all of it together" in prompt

    def test_other_modes_leave_taste_hints_out(self):
        """Plain Suggest and explore mode don't list the saved meals, staples or ratings."""
        for mode in (None, "explore"):
            prompt = build_suggestion_prompt(
                [], [], {}, [], mode=mode, favorite_meals=self.SAVED, favorites=["Bagels"], ratings=self.RATINGS,
            )
            assert "Cheddar toast" not in prompt, mode
            assert "Bagels" not in prompt, mode
            assert "Strawberries" not in prompt, mode

    def test_mode_explore_appends_discovery_instructions(self):
        """Explore mode should add world cuisine/discovery instructions."""
        prompt = build_suggestion_prompt([], [], {}, [], mode="explore")
        assert "EXPLORE" in prompt
        assert "world" in prompt.lower() or "global" in prompt.lower()

    def test_unknown_mode_has_no_extra_instruction(self):
        """Unknown mode should not crash — just no extra block."""
        prompt = build_suggestion_prompt([], [], {}, [], mode="unknown")
        assert "MODE:" not in prompt


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Analyst persona
# ---------------------------------------------------------------------------

class TestAnalystPrompt:
    # Analyst prompt renders without template errors
    def test_renders_without_error(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    # Analyst identifies as analysis engine, not chat assistant
    def test_contains_analyst_identity(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "analyst" in prompt.lower() or "analysis" in prompt.lower()

    # Analyst must NOT be a chat assistant
    def test_no_chat_behavior(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "NOT a chat assistant" in prompt

    # Analyst prompt responds in Turkish
    def test_responds_in_english_by_default(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "Always respond in English." in prompt

    def test_responds_in_turkish_when_set(self):
        prompt = build_analyst_prompt([], None, None, None, language="tr")
        assert "Always respond in Turkish." in prompt

    # Analyst uses low temperature (instruction embedded in prompt)
    def test_mentions_low_temperature(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "0.3" in prompt

    # Analyst includes user profile data
    def test_includes_user_profile(self):
        prompt = build_analyst_prompt(
            [], user_profile={"age": 30, "weight_kg": 80, "height_cm": 180},
        )
        assert "30" in prompt
        assert "80" in prompt
        assert "180" in prompt

    # Analyst includes supplement data
    def test_includes_supplements(self):
        prompt = build_analyst_prompt(
            [], supplements=[{"name": "D3", "frequency": "daily", "contents": "1000IU"}],
        )
        assert "D3" in prompt
        assert "1000IU" in prompt

    # Analyst includes recent history with ingredient details
    def test_includes_history(self):
        meals = [{"meal_name": "Menemen", "ingredients": '["yumurta", "domates"]'}]
        prompt = build_analyst_prompt(meals)
        assert "Menemen" in prompt
        assert "yumurta" in prompt

    # Analyst includes health rules
    def test_includes_health_rules(self):
        rules = [{"rule_text": "Limit sodium", "priority": "high"}]
        prompt = build_analyst_prompt([], health_rules=rules)
        assert "Limit sodium" in prompt

    # JSON output block includes required fields
    def test_json_block_has_required_fields(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert '"narrative"' in prompt
        assert '"daily_coverage"' in prompt
        assert '"macros"' in prompt
        assert '"micros"' in prompt
        assert '"supplement_warnings"' in prompt

    # Daily coverage has all 4 fixed categories
    def test_daily_coverage_fixed_categories(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "Calories" in prompt
        assert "Protein" in prompt
        assert "Fiber" in prompt
        assert "Vitamins & Minerals" in prompt

    # Supplement excess check instruction is present
    def test_supplement_excess_check(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "EXCESS CHECK" in prompt
        assert "upper limit" in prompt.lower() or "UL" in prompt

    # Analyst prompt mentions Mifflin-St Jeor for calorie calculation
    def test_mentions_calorie_formula(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "Mifflin" in prompt

    # Default when no profile/supplements provided
    def test_defaults_when_empty(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "Not provided" in prompt
        assert "No supplements" in prompt


# ---------------------------------------------------------------------------
# Scheduler (prep plan)
# ---------------------------------------------------------------------------

class TestSchedulerPrompt:
    def test_example_shows_the_format_only(self):
        """The 7B model copies a full example plan into real ones, so the example holds placeholders only."""
        prompt = build_scheduler_prompt("", [], "")
        assert "This shows the format only" in prompt
        assert '"task": "<manual task>"' in prompt
        assert "tomato" not in prompt.lower() and "boil eggs" not in prompt.lower()

    def test_items_served_as_they_are_get_no_cooking(self):
        """Simple items need no timed task, and a prep task only when they must be cut."""
        prompt = build_scheduler_prompt("", [], "")
        assert "Items served as they are need no timed task, and a prep task only when they must be cut first." in prompt
        assert "Plan only what the menu lists." in prompt

    def test_dish_method_is_followed(self):
        """One rule says a dish's method is how it was designed, so the plan makes it that way."""
        prompt = build_scheduler_prompt("", [], "")
        assert "A dish's method, in brackets after its name, is how the dish was designed, so plan it that way." in prompt


class TestSchedulerUserMessage:
    MENU = [
        {"name": "Menemen", "ingredients": [
            {"name": "Egg", "amount": 2, "unit": "adet"},
            {"name": "Tomato", "amount": 1, "unit": "adet"},
        ]},
        {"name": "White cheese", "amount": 50, "unit": "g", "ingredients": []},
    ]

    def test_menu_without_steps_lists_every_dish(self):
        """A menu-format meal sends its dishes and amounts, with no empty Steps section."""
        msg = build_scheduler_user_message("Classic Breakfast", [], "Egg, Tomato", menu=self.MENU)
        assert "- Menemen: Egg (2 pcs), Tomato (1 pcs)" in msg
        assert "- White cheese (50 g), served as it is" in msg
        assert "Steps:" not in msg
        assert "Ingredients:" not in msg

    def test_units_follow_the_reply_language(self):
        """Known units are sent in the reply language; unknown ones as written."""
        menu = [*self.MENU, {"name": "Protein powder", "amount": 1, "unit": "scoop", "ingredients": []}]
        msg = build_scheduler_user_message("Kahvaltı", [], "", menu=menu, language="tr")
        assert "- Menemen: Egg (2 adet), Tomato (1 adet)" in msg
        assert "- Protein powder (1 scoop)" in msg

    def test_prep_words_follow_the_amount(self):
        """An ingredient's prep words reach the planner beside its amount, so the dish is made as suggested."""
        menu = [{"name": "Porridge", "ingredients": [
            {"name": "Oats", "amount": 1, "unit": "glass", "prep": "rolled"},
            {"name": "Banana", "prep": "sliced"},
        ]}]
        msg = build_scheduler_user_message("Porridge", [], "", menu=menu)
        assert "- Porridge: Oats (1 glass, rolled), Banana (sliced)" in msg

    def test_dish_method_follows_the_name(self):
        """A dish's method reaches the planner in brackets after its name; older dishes without one are unchanged."""
        menu = [
            {"name": "Egg sandwich", "method": "Hard-boil the eggs, peel, slice into the bread. ", "ingredients": [
                {"name": "Egg", "amount": 2, "unit": "pcs"},
                {"name": "Bread", "amount": 2, "unit": "slice"},
            ]},
            *self.MENU,
        ]
        msg = build_scheduler_user_message("Egg sandwich", [], "", menu=menu)
        assert "- Egg sandwich (Hard-boil the eggs, peel, slice into the bread): Egg (2 pcs), Bread (2 slice)" in msg
        assert "- Menemen: Egg (2 pcs), Tomato (1 pcs)" in msg

    def test_water_is_planned_like_any_item(self):
        """Water in a recipe reaches the planner with the dish; a glass of water on its own is served as it is."""
        menu = [
            {"name": "Porridge", "ingredients": [
                {"name": "Oats", "amount": 1, "unit": "glass"},
                {"name": "Water", "amount": 1, "unit": "glass"},
            ]},
            {"name": "Water", "amount": 200, "unit": "ml", "ingredients": []},
        ]
        msg = build_scheduler_user_message("Porridge", [], "", menu=menu)
        assert "- Porridge: Oats (1 glass), Water (1 glass)" in msg
        assert "- Water (200 ml), served as it is" in msg

    def test_steps_still_included(self):
        """Older meals with recipe steps keep sending them, numbered."""
        msg = build_scheduler_user_message("Eggs", ["Boil eggs", "Peel"], "Egg")
        assert "Ingredients: Egg" in msg
        assert "Steps:\n1. Boil eggs\n2. Peel" in msg


# ---------------------------------------------------------------------------
# Fridge-only rule (basics like salt and oil included)
# ---------------------------------------------------------------------------

class TestFridgeRule:
    # One constructive rule: copy names from the list, basics included; water goes unmentioned, so the model isn't drawn to it
    def test_suggestion_prompt_has_one_copy_from_list_rule(self):
        prompt = build_suggestion_prompt([{"name": "Yumurta"}], [], {}, [])
        assert "copied exactly as listed (no alternatives like \"X or Y\", translations or notes; a cut or form" in prompt
        assert "`prep` (optional, dish ingredients only)" in prompt
        assert "basics like salt and oil included" in prompt
        assert "water" not in prompt.lower()
        assert "never appear in the JSON" not in prompt

    # Code checks the fridge, so the reviewer only uses the list to suggest swaps
    def test_pipeline_analyst_leaves_fridge_check_to_code(self):
        prompt = build_pipeline_analyst_prompt([], ingredient_inventory=[{"name": "Yumurta"}])
        assert "Yumurta" in prompt
        assert "suggest swaps only from these" in prompt
        assert "FRIDGE CONSTRAINT" not in prompt
        assert "water" not in prompt.lower()


# ---------------------------------------------------------------------------
# Language directive repeated at the end
# ---------------------------------------------------------------------------

class TestLanguageReminder:
    @staticmethod
    def _user_facing(language):
        return {
            "suggestion": build_suggestion_prompt([], [], {}, [], language=language),
            "suggestion_favorites": build_suggestion_prompt([], [], {}, [], mode="favorites", language=language),
            "suggestion_explore": build_suggestion_prompt([], [], {}, [], mode="explore", language=language),
            "analyst": build_analyst_prompt([], None, None, None, language=language),
            "weekly_analyst": build_weekly_analyst_prompt_with_meals("Mon: eggs", language=language),
            "scheduler": build_scheduler_prompt("Menemen", [], "eggs", language=language),
            "shopping": build_shopping_prompt([], [], {}, [], language=language),
        }

    def test_english_directive_is_last(self):
        """A 7B model drifts toward the language of Turkish data, so English is restated at the very end."""
        for name, prompt in self._user_facing("en").items():
            tail = prompt[-400:]
            assert "FINAL REMINDER: Always respond in English." in tail, name
            assert "respond in Turkish" not in tail, name

    def test_turkish_directive_is_last(self):
        """The Turkish setting gets the same closing reminder."""
        for name, prompt in self._user_facing("tr").items():
            assert "FINAL REMINDER: Always respond in Turkish." in prompt[-400:], name

    def test_menu_name_follows_response_language(self):
        """The menu name is a title in the response language, not a dish name kept in Turkish."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert "`menu_name`: a short title for the whole menu in the response language" in prompt
        assert "never to the menu name" in prompt


# ---------------------------------------------------------------------------
# JSON examples shown to the model
# ---------------------------------------------------------------------------

def _all_prompts():
    return {
        "chat": build_chat_prompt([], [], {}, []),
        "suggestion": build_suggestion_prompt([], [], {}, []),
        "analyst": build_analyst_prompt([], None, None, None),
        "pipeline_analyst": build_pipeline_analyst_prompt([]),
        "weekly_analyst": build_weekly_analyst_prompt_with_meals("Mon: eggs"),
        "scheduler": build_scheduler_prompt("Menemen", ["cook"], "eggs"),
        "shopping": build_shopping_prompt([], [], {}, []),
    }


class TestJsonExamples:
    def test_no_doubled_braces(self):
        """Templates are formatted once, so {{ must not survive into the prompt."""
        for name, prompt in _all_prompts().items():
            assert "{{" not in prompt, name

    def test_json_examples_are_valid_json(self):
        """Small models copy examples, so every example must parse."""
        for name, prompt in _all_prompts().items():
            for block in re.findall(r"```json\n([\s\S]*?)\n```", prompt):
                try:
                    json.loads(block)
                except json.JSONDecodeError as e:
                    raise AssertionError(f"{name}: invalid JSON example ({e})") from e



# ---------------------------------------------------------------------------
# Units follow the response language
# ---------------------------------------------------------------------------

class TestSuggestionUnits:
    def test_english_example_and_rule_use_english_units(self):
        """In English mode the JSON example and the unit rule use pcs, tbsp…"""
        prompt = build_suggestion_prompt([], [], {}, [], language="en")
        assert '"unit": "pcs"' in prompt
        assert "`unit`: one of pcs, g, kg, ml, l, tsp, dsp, tbsp" in prompt
        assert "adet" not in prompt

    def test_turkish_example_and_rule_use_turkish_units(self):
        """In Turkish mode the same places use adet, yemek kaşığı…"""
        prompt = build_suggestion_prompt([], [], {}, [], language="tr")
        assert '"unit": "adet"' in prompt
        assert "`unit`: one of adet, g, kg, ml, L, çay kaşığı, tatlı kaşığı, yemek kaşığı" in prompt
        assert '"unit": "pcs"' not in prompt

    def test_spoon_and_glass_sizes_in_reply_language(self):
        """The unit rule gives the fixed spoon and glass sizes, named in the reply language."""
        english = build_suggestion_prompt([], [], {}, [], language="en")
        turkish = build_suggestion_prompt([], [], {}, [], language="tr")
        assert "(tsp 5 ml, dsp 10 ml, tbsp 15 ml, tea glass 100 ml, glass 200 ml)" in english
        assert "çay bardağı 100 ml, su bardağı 200 ml)" in turkish

    def test_example_uses_listed_grams(self):
        """The example writes grams as "g", the listed unit, not "gr"."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"unit": "gr"' not in prompt
        assert '"unit": "g"' in prompt



# ---------------------------------------------------------------------------
# Shopping: buyable products, date and country
# ---------------------------------------------------------------------------

class TestShoppingPrompt:
    DAY = date(2026, 10, 27)

    def test_items_are_specific_products_not_dishes(self):
        """One rule asks for plain, specific product names and turns a dish into its missing ingredients."""
        prompt = build_shopping_prompt([], [], {}, [])
        assert '"Salmon", not "Fatty fish"' in prompt
        assert "never a filler like fresh" in prompt
        assert "A dish is not a product" in prompt
        assert "suggest the ingredients it needs that are not in the inventory" in prompt

    def test_no_dish_in_naming_examples(self):
        """Menemen is a dish, so it no longer appears as a naming example."""
        assert "Menemen" not in build_shopping_prompt([], [], {}, [])

    def test_exclusions_are_stated_once_and_positively(self):
        """Code drops repeats, so the prompt only lists what is covered, without a pile of bans."""
        prompt = build_shopping_prompt([], [], {}, [], shopping_list=["Kiwi"])
        assert "CURRENT SHOPPING LIST:\nKiwi" in prompt
        assert "Do NOT suggest" not in prompt

    def test_reply_is_an_items_object(self):
        """The reply shape matches the schema Ollama enforces: an object with an items list."""
        prompt = build_shopping_prompt([], [], {}, [])
        assert 'Reply with a JSON object whose "items" list holds 15-25 products' in prompt

    def test_date_and_country(self):
        """Today's date and the user's country tell the model what is in season."""
        prompt = build_shopping_prompt([], [], {}, [], country="Türkiye", today=self.DAY)
        assert "Today is Tuesday, 27 October 2026, in Türkiye." in prompt
        assert "in season at this time and place" in prompt

    def test_date_without_country(self):
        """Without a country the prompt still gets the date."""
        prompt = build_shopping_prompt([], [], {}, [], today=self.DAY)
        assert "Today is Tuesday, 27 October 2026." in prompt

    def test_suggestion_prompt_gets_date_and_country(self):
        """The suggestion prompt's seasonality hint uses the same date and country."""
        prompt = build_suggestion_prompt([], [], {}, [], country="Türkiye", today=self.DAY)
        assert "Today is Tuesday, 27 October 2026, in Türkiye. Prefer fruits and vegetables in season" in prompt
