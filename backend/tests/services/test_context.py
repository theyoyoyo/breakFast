"""Tests for the per-user context loaders that feed the prompts."""

from services.context import _food_preferences


# App settings and avoid entries never reach prompts as food preferences
def test_food_preferences_drop_settings_and_avoid_entries():
    prefs = {
        "fav:1": "olives",
        "avoid:1": "peanuts",
        "response_language": "tr",
        "theme": "purple",
        "weekly_summary_in_suggestions": "true",
    }
    assert _food_preferences(prefs) == {"fav:1": "olives"}
