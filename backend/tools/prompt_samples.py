"""
Sample users for the prompt test, shaped the way load_chat_context() and
load_shopping_context() return them, so the real prompts run without a database.

- en / tr: an English and a Turkish breakfast fridge, replies in that language.
- mixed: Turkish fridge names with English replies, like a real user mid-setup.
  Its staples include dishes (Menemen, Sucuklu tost), which shopping must turn
  into their missing ingredients.
- demo: the demo account's starter fridge (DEMO_FRIDGE) with a filled-in profile,
  health rules, a supplement, staples and meal history.
- sparse: a nearly empty fridge.
- vegan: a plant-based fridge with animal products on the avoid list.
Simit sits in the en, tr and mixed fridges without tahini, to catch prepared items (#115).
"""

from models.ingredient import DEMO_FRIDGE


def _fridge(groups: dict[str, list[str]]) -> list[dict]:
    return [{"name": name, "group_name": group} for group, names in groups.items() for name in names]


def _meal(name: str, *ingredients: str) -> dict:
    return {"meal_name": name, "ingredients": [{"name": i} for i in ingredients]}


# What every sample shares unless it says otherwise: no preferences, habits, rules or
# supplements, a basic kitchen, an empty shopping list and no staples or ratings
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
    "shopping_list": [],
    "favorites": [],
    "ratings": [],
}

_TURKISH_FRIDGE = _fridge({
    "🐄 Animal Products": ["Yumurta", "Beyaz peynir", "Kaşar peyniri", "Tereyağı", "Yoğurt", "Süt", "Sucuk"],
    "🥬 Produce": ["Domates", "Salatalık", "Sivri biber", "Maydanoz"],
    "🍞 Breads": ["Ekmek", "Simit"],
    "🍯 Sweets": ["Bal"],
    "🫒 Breakfast Staples": ["Siyah zeytin"],
    "🥜 Nuts & Seeds": ["Ceviz"],
    "☕ Beverages": ["Çay"],
    "🧂 Spices": ["Pul biber"],
    "🫙 Pantry": ["Tuz", "Karabiber", "Zeytinyağı"],
})

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
        "ingredients": _TURKISH_FRIDGE,
        "history": [
            {"meal_name": "Kaşarlı tost"},
            {"meal_name": "Sucuklu yumurta"},
            {"meal_name": "Menemen"},
        ],
    },
    "mixed": {
        **_BASE,
        "language": "en",
        "ingredients": _TURKISH_FRIDGE,
        "history": [
            _meal("Sucuklu tost", "Ekmek", "Sucuk", "Kaşar peyniri"),
            _meal("Menemen", "Yumurta", "Domates", "Sivri biber", "Zeytinyağı"),
            _meal("Simit and white cheese", "Simit", "Beyaz peynir", "Çay"),
        ],
        "favorites": ["Menemen", "Sucuklu tost", "Simit", "Beyaz peynir", "Çay"],
        "shopping_list": ["Süt"],
    },
    "demo": {
        **_BASE,
        "language": "en",
        "ingredients": [{"name": name, "group_name": group} for name, group in DEMO_FRIDGE],
        "user_profile": {"age": 34, "gender": "female", "height_cm": 168, "weight_kg": 62, "activity_level": "moderate"},
        "health_rules": [
            {"rule_text": "Enough protein to stay full until lunch", "priority": "critical"},
            {"rule_text": "Keep added sugar low", "priority": "high"},
            {"rule_text": "More vegetables", "priority": "low"},
        ],
        "supplements": [{"name": "Vitamin D3", "contents": "1000 IU vitamin D", "frequency": "daily", "taken_today": 1}],
        "stated_habits": ["Light breakfast on weekdays", "Tea every morning"],
        "preferences": {"fav:menemen": "Menemen", "dislike:cucumber": "Cucumber"},
        "history": [
            _meal("Menemen", "Eggs", "Tomatoes", "Butter"),
            _meal("Toast with honey", "Bread", "Butter", "Honey"),
            _meal("White cheese and olives", "White cheese", "Olives", "Bread"),
        ],
        "favorites": ["Eggs", "Bread", "Menemen", "Honey"],
        "ratings": [{"product_name": "Honey", "rating": 9}, {"product_name": "Cucumber", "rating": 3}],
        "shopping_list": ["Milk"],
    },
    "sparse": {
        **_BASE,
        "language": "en",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Eggs"],
            "🍞 Breads": ["Bread"],
            "☕ Beverages": ["Tea"],
            "🫙 Pantry": ["Salt"],
        }),
        "history": [_meal("Boiled eggs", "Eggs", "Salt")],
    },
    "vegan": {
        **_BASE,
        "language": "en",
        "ingredients": _fridge({
            "🌱 Plant-Based": ["Soy milk", "Peanut butter"],
            "🥬 Produce": ["Banana", "Tomatoes", "Cucumber", "Spinach"],
            "🍞 Breads": ["Bread"],
            "🥜 Nuts & Seeds": ["Walnuts", "Chia seeds"],
            "☕ Beverages": ["Tea"],
            "🫙 Pantry": ["Oats", "Olive oil", "Salt"],
        }),
        "stated_habits": ["Plant-based"],
        "avoid_list": ["Eggs", "Milk", "Cheese", "Butter", "Honey", "Yogurt"],
        "history": [_meal("Overnight oats", "Oats", "Soy milk", "Chia seeds", "Banana")],
    },
}
