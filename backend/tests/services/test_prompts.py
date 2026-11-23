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

from models.units import UNIT_ML, UNIT_PAIRS, units_for
from services.knowledge import (
    format_avoid_list,
    format_behavioral,
    format_habits,
    format_health_rules,
    format_history,
    format_ingredients,
    format_preferences,
    format_supplements,
    format_supplements_taken,
    format_user_profile,
)
from services.personas import (
    build_analyst_prompt,
    build_chat_prompt,
    build_pipeline_analyst_prompt,
    build_present_prompt,
    build_scheduler_prompt,
    build_scheduler_user_message,
    build_shopping_prompt,
    build_suggestion_prompt,
    build_weekly_analyst_prompt_with_meals,
)
from services.personas.chat import build_chat_message

# ---------------------------------------------------------------------------
# Shared formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    # An empty ingredient list reads as none listed yet
    def test_format_ingredients_empty(self):
        assert format_ingredients([]) == "none listed yet"

    # Every ingredient name reaches the text
    def test_format_ingredients_with_data(self):
        items = [
            {"name": "eggs", "quantity": "6", "unit": "pcs"},
            {"name": "milk", "quantity": "1", "unit": "L"},
        ]
        result = format_ingredients(items)
        assert "eggs" in result
        assert "milk" in result

    # An empty history reads as no history yet
    def test_format_history_empty(self):
        assert format_history([]) == "no history yet"

    # The history keeps only the newest meals up to the limit
    def test_format_history_with_limit(self):
        meals = [{"meal_name": f"meal_{i}"} for i in range(10)]
        result = format_history(meals, limit=3)
        # History comes newest first, so the first 3 are the newest
        assert "meal_0" in result
        assert "meal_2" in result
        assert "meal_3" not in result

    # Empty preferences read as none set yet
    def test_format_preferences_empty(self):
        assert format_preferences({}) == "none set yet"

    # Preferences reach the text
    def test_format_preferences_with_data(self):
        result = format_preferences({"favorite": "eggs"})
        assert "eggs" in result

    # No habits read as none stated yet
    def test_format_habits_empty(self):
        assert format_habits([]) == "none stated yet"

    # Every stated habit reaches the text
    def test_format_habits_with_data(self):
        result = format_habits(["early breakfast", "no sugar"])
        assert "early breakfast" in result
        assert "no sugar" in result

    # With no rules the model still gets text to work from, and it is no ban, since only the avoid list bans
    def test_format_health_rules_empty_is_guidance_not_a_ban(self):
        result = format_health_rules([])
        assert result.strip()
        assert "TOP PRIORITY" not in result
        assert format_avoid_list(["x"]).splitlines()[0] not in result

    # Formats rules with priority labels when passed as dicts
    def test_format_health_rules_custom(self):
        rules = [
            {"rule_text": "Avoid gluten", "priority": "critical"},
            {"rule_text": "Favor omega-3", "priority": "low"},
        ]
        result = format_health_rules(rules)
        lines = {r["rule_text"]: next(line for line in result.splitlines() if r["rule_text"] in line) for r in rules}
        # Each rule is listed with a priority label, and the two priorities are labeled differently
        label = {text: line.replace(text, "") for text, line in lines.items()}
        assert label["Avoid gluten"] != label["Favor omega-3"]
        assert "refined sugar" not in result

    # Backwards-compatible with plain string lists
    def test_format_health_rules_plain_strings(self):
        result = format_health_rules(["Avoid gluten", "Favor omega-3"])
        assert "Avoid gluten" in result
        assert "Favor omega-3" in result

    # An empty avoid list is the same text whether it is None or [], and it carries no ban
    def test_format_avoid_list_empty(self):
        assert format_avoid_list(None) == format_avoid_list([])
        assert "NEVER" not in format_avoid_list([])

    # The avoid list names every item and states the ban
    def test_format_avoid_list_with_data(self):
        result = format_avoid_list(["shellfish", "peanuts"])
        assert "shellfish" in result
        assert "peanuts" in result
        assert "NEVER" in result

    # No behavioral patterns give no text at all
    def test_format_behavioral_empty(self):
        assert format_behavioral(None) == ""
        assert format_behavioral([]) == ""

    # Every inferred pattern reaches the text
    def test_format_behavioral_with_data(self):
        result = format_behavioral(["eats eggs daily", "rarely has fruit"])
        assert "eats eggs daily" in result
        assert "rarely has fruit" in result

    # No profile, or an empty one, gives the same non-empty default text
    def test_format_user_profile_empty(self):
        assert format_user_profile(None) == format_user_profile({}) != ""

    # Every profile field reaches the text
    def test_format_user_profile_with_data(self):
        profile = {
            "age": 30, "gender": "erkek",
            "height_cm": 180, "weight_kg": 75,
            "activity_level": "orta",
        }
        result = format_user_profile(profile)
        assert "30" in result
        assert "180" in result
        assert "75" in result
        assert "orta" in result

    # No supplements, or an empty list, gives the same non-empty text
    def test_format_supplements_empty(self):
        assert format_supplements(None) == format_supplements([]) != ""

    # A daily supplement is listed with its frequency and contents
    def test_format_supplements_daily(self):
        supps = [{"name": "Vitamin D", "frequency": "daily", "contents": "1000IU D3"}]
        result = format_supplements(supps)
        assert "Vitamin D" in result
        assert "daily" in result
        assert "1000IU D3" in result

    # An occasional supplement taken today is marked as taken
    def test_format_supplements_sometimes_taken(self):
        supps = [{"name": "Omega-3", "frequency": "sometimes", "contents": "1000mg EPA/DHA", "taken_today": True}]
        result = format_supplements(supps)
        assert "taken today" in result

    # An occasional supplement not taken today is marked as not taken
    def test_format_supplements_sometimes_not_taken(self):
        supps = [{"name": "Omega-3", "frequency": "sometimes", "contents": "", "taken_today": False}]
        result = format_supplements(supps)
        assert "NOT taken today" in result

    # A daily supplement the user skipped today is marked as not taken, and one without a mark stays plain
    def test_format_supplements_daily_skipped(self):
        skipped = format_supplements([{"name": "Vitamin D", "frequency": "daily", "taken_today": 0}])
        usual = format_supplements([{"name": "Vitamin D", "frequency": "daily", "taken_today": 1}])
        assert "NOT taken today" in skipped
        assert "taken today" not in usual

    # The planner's list leaves out a daily supplement skipped today and keeps one taken as usual
    def test_format_supplements_taken_follows_today(self):
        supps = [
            {"name": "Vitamin D", "frequency": "daily", "contents": "", "taken_today": 0},
            {"name": "Iron", "frequency": "daily", "contents": ""},
            {"name": "Omega-3", "frequency": "sometimes", "contents": "", "taken_today": 1},
        ]
        result = format_supplements_taken(supps)
        assert "Vitamin D" not in result
        assert "Iron" in result
        assert "Omega-3" in result


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

    # The fridge items reach the chat prompt
    def test_includes_ingredients(self):
        prompt = build_chat_prompt(
            ingredient_inventory=[{"name": "peynir", "quantity": "200", "unit": "g"}],
            recent_meal_history=[],
            user_preferences={},
            stated_habits=[],
        )
        assert "peynir" in prompt

    # Health rules from the database reach the chat prompt
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

    # With no health rules in the database, the default guidance reaches the prompt
    def test_default_health_rules_when_none(self):
        prompt = build_chat_prompt([], [], {}, [])
        assert format_health_rules([]) in prompt

    def test_no_json_block(self):
        """Chat persona replies in plain text; meal blocks only come from Suggest."""
        prompt = build_chat_prompt([], [], {}, [])
        assert "```json" not in prompt

    def test_menus_go_to_suggest(self):
        """The chat points to the Suggest button, which makes the menu, so its prompt asks for no meal block (#168)."""
        prompt = build_chat_prompt([], [], {}, [])
        assert "Suggest" in prompt
        assert "menu_name" not in prompt

    def test_message_ends_with_the_reply_note(self):
        """Each typed message reaches the model with the app's note last: the menu rule with its reason and the reply language (#168)."""
        message = build_chat_message("I only have 10 minutes.", language="tr")
        words, note = message.split("\n\n", 1)
        assert words == "I only have 10 minutes."
        assert note.startswith("(") and note.endswith(")")
        assert "Suggest" in note
        assert note.rfind("Turkish") > note.rfind("Suggest")  # the reply language comes last

    def test_ends_with_language_reminder(self):
        """The language directive is the last thing the model reads, like every user-facing prompt."""
        prompt = build_chat_prompt([], [], {}, [], language="tr")
        last = prompt.rstrip().splitlines()[-1]
        assert "Turkish" in last and "English" not in last

    # An empty avoid list reaches the prompt as the formatter's empty text, with no ban
    def test_includes_avoid_list_empty(self):
        prompt = build_chat_prompt([], [], {}, [])
        assert format_avoid_list([]) in prompt

    # Avoid list items reach the chat prompt with the ban
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
    # The suggestion template renders without a missing field
    def test_renders_without_error(self):
        prompt = build_suggestion_prompt([], [], {}, [])
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_history_limit_is_4(self):
        """Suggestion persona uses the newest 4 meals; history comes newest first."""
        meals = [{"meal_name": f"meal_{i}"} for i in range(15)]
        prompt = build_suggestion_prompt([], meals, {}, [])
        assert "meal_0" in prompt
        assert "meal_3" in prompt
        assert "meal_4" not in prompt
        assert "meal_14" not in prompt

    # Health rules reach the suggestion prompt
    def test_includes_health_rules(self):
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            health_rules=["Limit sodium intake"],
        )
        assert "Limit sodium intake" in prompt

    # The reply's JSON keys are in the suggestion prompt
    def test_json_block_present(self):
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"menu_name"' in prompt
        assert '"menu"' in prompt

    # Inferred patterns reach the suggestion prompt
    def test_includes_behavioral_patterns(self):
        prompt = build_suggestion_prompt(
            [], [], {}, [],
            inferred_habits=["high egg consumption"],
        )
        assert "high egg consumption" in prompt
        assert "high egg consumption" not in build_suggestion_prompt([], [], {}, [])

    def test_includes_avoid_list_empty(self):
        """An empty avoid list reaches the prompt as the formatter's empty text, with no ban."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert format_avoid_list([]) in prompt

    def test_includes_avoid_list_with_items(self):
        """Suggestion prompt should inject actual avoid items."""
        prompt = build_suggestion_prompt([], [], {}, [], avoid_list=["gluten", "lactose"])
        assert "gluten" in prompt
        assert "lactose" in prompt
        assert "NEVER" in prompt

    def test_json_block_has_prep_time_without_nutrition_note(self):
        """The JSON block asks for the prep time; the nutrition note is gone, since nothing showed it."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert '"prep_time_min"' in prompt
        assert "nutrition_note" not in prompt
        assert '"nutrition_detail"' not in prompt

    def test_no_example_lists_that_pull_menus_off_the_fridge(self):
        """The rules stay without example dishes or superfoods, which a 7B model copied into menus."""
        for mode in (None, "favorites", "explore"):
            prompt = build_suggestion_prompt([], [], {}, [], mode=mode)
            assert "Sucuk" not in prompt and "Ayran" not in prompt, mode
            assert "chia" not in prompt.lower() and "quinoa" not in prompt.lower(), mode

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
        """When no profile/supplements given, the formatters' default texts reach the prompt."""
        prompt = build_suggestion_prompt([], [], {}, [])
        assert format_user_profile(None) in prompt
        assert format_supplements_taken(None) in prompt

    def test_modes_each_add_their_own_instructions(self):
        """Each Suggest mode changes the prompt, and a plain press and an unknown mode add nothing."""
        plain = build_suggestion_prompt([], [], {}, [])
        favorites = build_suggestion_prompt([], [], {}, [], mode="favorites")
        explore = build_suggestion_prompt([], [], {}, [], mode="explore")
        assert len({plain, favorites, explore}) == 3
        assert build_suggestion_prompt([], [], {}, [], mode="unknown") == plain

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
        assert "Bagels" in prompt
        # A high-rated item and a low-rated one are listed apart
        lines = prompt.splitlines()
        assert "Oats" not in next(line for line in lines if "Strawberries" in line)
        assert "Strawberries" not in next(line for line in lines if "Oats" in line)

    def test_other_modes_leave_taste_hints_out(self):
        """Plain Suggest and explore mode don't list the saved meals, staples or ratings."""
        for mode in (None, "explore"):
            prompt = build_suggestion_prompt(
                [], [], {}, [], mode=mode, favorite_meals=self.SAVED, favorites=["Bagels"], ratings=self.RATINGS,
            )
            assert "Cheddar toast" not in prompt, mode
            assert "Bagels" not in prompt, mode
            assert "Strawberries" not in prompt, mode


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

    # The reply language follows the setting: English by default, Turkish when set
    def test_responds_in_english_by_default(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert "English" in prompt and "Turkish" not in prompt

    # The Turkish setting names Turkish in the analyst prompt
    def test_responds_in_turkish_when_set(self):
        prompt = build_analyst_prompt([], None, None, None, language="tr")
        assert "Turkish" in prompt and "English" not in prompt

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

    # Default texts of the formatters reach the prompt when no profile or supplements are given
    def test_defaults_when_empty(self):
        prompt = build_analyst_prompt([], None, None, None)
        assert format_user_profile(None) in prompt
        assert format_supplements(None) in prompt


# ---------------------------------------------------------------------------
# Scheduler (prep plan)
# ---------------------------------------------------------------------------

class TestSchedulerPrompt:
    def test_example_shows_the_format_only(self):
        """The 7B model copies a full example plan into real ones, so the example holds placeholders only."""
        prompt = build_scheduler_prompt("", [], "")
        assert "<" in prompt and ">" in prompt
        assert "tomato" not in prompt.lower() and "boil eggs" not in prompt.lower()

    def test_reply_format_names_the_step_fields(self):
        """The reply parser reads these keys, so the prompt names every one of them."""
        prompt = build_scheduler_prompt("", [], "")
        for key in ("dishes", "dish", "steps", "action", "minutes", "hands_on", "appliance"):
            assert f'"{key}"' in prompt or f"`{key}`" in prompt, key

    def test_appliances_are_the_users_or_the_defaults(self):
        """The user's appliances are offered by name, and the defaults when none are enabled."""
        custom = build_scheduler_prompt("", [], "", ["Stove", "Kettle"])
        assert "Stove" in custom and "Kettle" in custom
        assert "Oven" not in custom and "Toaster" not in custom
        default = build_scheduler_prompt("", [], "", [])
        assert all(name in default for name in ("Stove", "Air Fryer", "Toaster", "Oven"))

    def test_dish_method_is_explained(self):
        """The prompt tells the planner what the method in brackets is, since the request sends it that way."""
        assert "method" in build_scheduler_prompt("", [], "")

    def test_no_example_dish_in_the_rules(self):
        """The appliance rule and the order rule name no example dish, which the 7B model copied into plans (#160)."""
        prompt = build_scheduler_prompt("", [], "", kitchen_appliances=["Stove", "Oven"])
        assert "avocado" not in prompt.lower() and "Stove" in prompt and "Oven" in prompt

    def test_order_rule_ends_the_request(self):
        """The request ends with the prep-before-heating rule, after the menu, since the 7B model follows the
        last message best (#160)."""
        msg = build_scheduler_user_message("Toast", [], "", menu=[{"name": "Toast", "ingredients": [{"name": "Bread"}]}])
        rule = msg.split("\n\n")[-1]
        assert msg.index("Toast: Bread") < msg.index(rule)
        assert "prep" in rule and "heat" in rule and rule.endswith(":")


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

    def test_simple_item_with_a_method_is_planned_as_a_dish_of_itself(self):
        """A simple item that is cut or cooked reaches the planner like a dish of itself, with its method;
        one with an empty method is served as it is (#156)."""
        menu = [
            {"name": "Sweet potato", "amount": 300, "unit": "g", "method": "Peel, cube and roast. ", "ingredients": []},
            {"name": "White cheese", "amount": 50, "unit": "g", "method": " ", "ingredients": []},
        ]
        msg = build_scheduler_user_message("Bowls", [], "", menu=menu)
        assert "- Sweet potato (Peel, cube and roast): Sweet potato (300 g)" in msg
        assert "- White cheese (50 g), served as it is" in msg

    def test_paired_item_names_its_pair(self):
        """An item served with or on another one names it in its line, after a dish's method or on a served
        item's line, and a pairing that names no other item of the menu is left out (#263)."""
        menu = [
            {"name": "Omelette", "ingredients": [{"name": "Egg", "amount": 2, "unit": "pcs"}]},
            {"name": "Tahini dressing", "method": "Mix the tahini with the oat milk.", "serve_with": "Omelette", "ingredients": [
                {"name": "Tahini", "amount": 1, "unit": "tbsp"},
                {"name": "Oat milk", "amount": 2, "unit": "tbsp"},
            ]},
            {"name": "Honey", "amount": 1, "unit": "tsp", "serve_with": "Omelette", "ingredients": []},
            {"name": "Banana", "amount": 1, "unit": "pcs", "serve_with": "Pancakes", "ingredients": []},
        ]
        lines = build_scheduler_user_message("Green morning", [], "", menu=menu).splitlines()
        dressing = next(line for line in lines if line.startswith("- Tahini dressing ("))
        assert "Mix the tahini with the oat milk" in dressing and "Omelette" in dressing.split(":")[0]
        assert dressing.endswith("Tahini (1 tbsp), Oat milk (2 tbsp)")
        assert "Omelette" in next(line for line in lines if line.startswith("- Honey"))
        assert "Pancakes" not in next(line for line in lines if line.startswith("- Banana"))
        assert "- Omelette: Egg (2 pcs)" in lines

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
    # The fridge reaches the prompt, the `prep` field is offered for a dish's cut or form, and water goes unmentioned,
    # so the model isn't drawn to it
    def test_suggestion_prompt_has_the_fridge_and_the_prep_field(self):
        prompt = build_suggestion_prompt([{"name": "Yumurta"}], [], {}, [])
        assert "Yumurta" in prompt
        assert "`prep`" in prompt
        assert "water" not in prompt.lower()

    # Only a fridge too small for any breakfast gets an empty menu, which code relies on, with a note in `text`, and the
    # reply is one JSON object that gives `text` before `meal` (the draft schema's order)
    def test_too_small_fridge_gets_an_empty_menu_and_a_note(self):
        prompt = build_suggestion_prompt([{"name": "Tea"}], [], {}, [])
        assert "leave `menu` empty" in prompt
        assert prompt.index("`text`") < prompt.index("`meal`")

    # Code checks the fridge, so the reviser gets the list and code's findings, not a fridge rule of its own
    def test_pipeline_analyst_leaves_fridge_check_to_code(self):
        prompt = build_pipeline_analyst_prompt([], ingredient_inventory=[{"name": "Yumurta"}])
        assert "Yumurta" in prompt
        assert "water" not in prompt.lower()

    # The reviser is asked for the fields the revision schema has: a method on every item, and prep words on ingredients
    def test_pipeline_analyst_names_the_method_and_prep_fields(self):
        prompt = build_pipeline_analyst_prompt([])
        assert "`method`" in prompt
        assert "`prep`" in prompt

    # The reviser's narrow questions (step 2) ask whether a menu item is something nobody eats on its own, with no
    # food named, since the model copies examples into menus (#263)
    def test_pipeline_analyst_asks_about_items_nobody_eats_alone(self):
        prompt = build_pipeline_analyst_prompt([], ingredient_inventory=[{"name": "Oats"}])
        questions = prompt[prompt.index("\n2. "):prompt.index("\n3. ")]
        assert "on its own" in questions
        assert "cinnamon" not in prompt.lower()


# ---------------------------------------------------------------------------
# Present step: the reply text from the final meal
# ---------------------------------------------------------------------------

class TestPresentPrompt:
    # The text is plain, since the app shows the menu under it
    def test_plain_text_only(self):
        assert "plain text" in build_present_prompt().lower()


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
            "present": build_present_prompt(language),
            "analyst": build_analyst_prompt([], None, None, None, language=language),
            "weekly_analyst": build_weekly_analyst_prompt_with_meals("Mon: eggs", language=language),
            "scheduler": build_scheduler_prompt("Menemen", [], "eggs", language=language),
            "shopping": build_shopping_prompt([], language=language),
        }

    def test_english_directive_is_last(self):
        """A 7B model drifts toward the language of Turkish data, so English is restated at the very end."""
        for name, prompt in self._user_facing("en").items():
            tail = prompt[-400:]
            assert "English" in tail, name

    def test_turkish_directive_is_last(self):
        """The Turkish setting gets the same closing reminder."""
        for name, prompt in self._user_facing("tr").items():
            tail = prompt[-400:]
            assert "Turkish" in tail and "English" not in tail, name


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
        "shopping": build_shopping_prompt([]),
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
        """In English mode the prompt lists every English unit, the example uses one, and no Turkish unit shows."""
        prompt = build_suggestion_prompt([], [], {}, [], language="en")
        assert all(unit in prompt for unit in units_for("en"))
        assert '"unit": "pcs"' in prompt
        assert "adet" not in prompt

    def test_turkish_example_and_rule_use_turkish_units(self):
        """In Turkish mode the prompt lists every Turkish unit, the example uses one, and no English count unit shows."""
        prompt = build_suggestion_prompt([], [], {}, [], language="tr")
        assert all(unit in prompt for unit in units_for("tr"))
        assert '"unit": "adet"' in prompt
        assert '"unit": "pcs"' not in prompt

    def test_spoon_and_glass_sizes_in_reply_language(self):
        """The prompt gives each fixed spoon and glass size, with the unit named in the reply language."""
        for language, index in (("en", 0), ("tr", 1)):
            prompt = build_suggestion_prompt([], [], {}, [], language=language)
            for unit, ml in UNIT_ML.items():
                name = next(pair[index] for pair in UNIT_PAIRS if pair[0] == unit)
                assert f"{name} {ml} ml" in prompt, (language, unit)

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

    def test_no_dish_in_naming_examples(self):
        """Menemen is a dish, so it no longer appears as a naming example."""
        assert "Menemen" not in build_shopping_prompt([])

    def test_exclusions_are_stated_once_and_positively(self):
        """Code drops repeats, so the prompt only lists what is covered, without a pile of bans."""
        prompt = build_shopping_prompt([], shopping_list=["Kiwi"])
        assert "Kiwi" in prompt
        assert "Kiwi" not in build_shopping_prompt([])

    def test_reply_is_an_items_object(self):
        """The reply shape matches the schema Ollama enforces: an object with an items list."""
        prompt = build_shopping_prompt([])
        assert '"items"' in prompt

    def test_taste_hints_are_listed_to_weigh_together(self):
        """This press's taste hints are listed one per line, to weigh together; with none, a varied pantry."""
        prompt = build_shopping_prompt(["Likes Pancakes", "Keeps around: Cheddar"])
        assert "- Likes Pancakes\n- Keeps around: Cheddar" in prompt
        assert "Pancakes" not in build_shopping_prompt([])

    def test_limits_are_always_in(self):
        """Dislikes, low-rated items and the avoid list are limits every press gets, not drawn hints."""
        prompt = build_shopping_prompt(
            [],
            user_preferences={"fav:pancakes": "Pancakes", "dislike:olives": "Olives"},
            avoid_list=["Peanuts"],
            ratings=[{"product_name": "Oats", "rating": 3}, {"product_name": "Honey", "rating": 9}],
        )
        assert "Olives" in prompt and "Oats" in prompt and "Peanuts" in prompt
        assert "Pancakes" not in prompt and "Honey" not in prompt  # likes are hints, drawn per press

    def test_date_and_country(self):
        """Today's date and the user's country tell the model what is in season."""
        prompt = build_shopping_prompt([], country="Türkiye", today=self.DAY)
        assert "27 October 2026" in prompt and "Türkiye" in prompt

    def test_date_without_country(self):
        """Without a country the prompt still gets the date."""
        prompt = build_shopping_prompt([], today=self.DAY)
        assert "27 October 2026" in prompt

    def test_suggestion_prompt_gets_date_and_country(self):
        """The suggestion prompt's seasonality hint uses the same date and country."""
        prompt = build_suggestion_prompt([], [], {}, [], country="Türkiye", today=self.DAY)
        assert "27 October 2026" in prompt and "Türkiye" in prompt
        assert "Türkiye" not in build_suggestion_prompt([], [], {}, [], today=self.DAY)
