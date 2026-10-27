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


# The profile's country reaches the chat and shopping contexts, but not the profile text the analysts read
async def test_country_in_contexts(client, db):
    from services.context import load_chat_context, load_shopping_context
    from services.knowledge import format_user_profile

    await client.put("/profile/", json={"age": 30, "country": "Türkiye"})
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        user_id = (await cur.fetchone())[0]

    chat = await load_chat_context(db, user_id)
    shopping = await load_shopping_context(db, user_id)
    assert chat["country"] == "Türkiye"
    assert shopping["country"] == "Türkiye"
    assert "Türkiye" not in format_user_profile(chat["user_profile"])
