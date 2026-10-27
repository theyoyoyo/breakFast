"""
Sample users for the prompt test: an English and a Turkish breakfast fridge, shaped
the way load_chat_context() returns them, so the real prompts run without a database.
Both fridges hold Simit but no tahini, to catch prepared items served as one (#115).
"""


def _fridge(groups: dict[str, list[str]]) -> list[dict]:
    return [{"name": name, "group_name": group} for group, names in groups.items() for name in names]


# What every sample shares: no preferences, habits, rules or supplements, a basic kitchen
_BASE = {
    "country": "Türkiye",
    "preferences": {},
    "stated_habits": [],
    "inferred_habits": [],
    "health_rules": [],
    "user_profile": None,
    "supplements": [],
    "avoid_list": [],
    "kitchen_appliances": ["Stove", "Toaster", "Kettle"],
    "weekly_summary": None,
}

SAMPLES = {
    "en": {
        **_BASE,
        "language": "en",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Eggs", "White cheese", "Butter", "Yogurt", "Milk"],
            "🥬 Produce": ["Tomatoes", "Cucumber", "Green peppers", "Banana"],
            "🍞 Breads": ["Bread", "Simit"],
            "🍯 Sweets": ["Honey"],
            "🫒 Breakfast Staples": ["Olives"],
            "🥜 Nuts & Seeds": ["Walnuts"],
            "☕ Beverages": ["Tea"],
            "🧂 Spices": ["Red pepper flakes"],
            "🫙 Pantry": ["Salt", "Black pepper", "Olive oil", "Oats"],
        }),
        "history": [
            {"meal_name": "Cheese omelette"},
            {"meal_name": "Oatmeal with banana and honey"},
            {"meal_name": "Menemen"},
        ],
    },
    "tr": {
        **_BASE,
        "language": "tr",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Yumurta", "Beyaz peynir", "Kaşar peyniri", "Tereyağı", "Yoğurt", "Süt", "Sucuk"],
            "🥬 Produce": ["Domates", "Salatalık", "Sivri biber", "Maydanoz"],
            "🍞 Breads": ["Ekmek", "Simit"],
            "🍯 Sweets": ["Bal"],
            "🫒 Breakfast Staples": ["Siyah zeytin"],
            "🥜 Nuts & Seeds": ["Ceviz"],
            "☕ Beverages": ["Çay"],
            "🧂 Spices": ["Pul biber"],
            "🫙 Pantry": ["Tuz", "Karabiber", "Zeytinyağı"],
        }),
        "history": [
            {"meal_name": "Kaşarlı tost"},
            {"meal_name": "Sucuklu yumurta"},
            {"meal_name": "Menemen"},
        ],
    },
}
