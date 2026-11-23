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
The en, picky and big_fridge users have saved favorite meals; Avocado toast (en) and Salmon
bagel (big_fridge) need an item the fridge lacks, which shopping may suggest (#130).

Five users from the 15-fridge test (2026-10-30), whose replies looked clean but weren't (#131):
- picky: nuts avoided with almond milk in the fridge, dislikes, favorites mode with saved
  favorite meals, staples and ratings from its fridge (#132).
- diabetic: a critical blood sugar rule, with white bread and honey in the fridge.
- student: a budget fridge and a microwave, ten minutes on weekdays.
- big_fridge: about 60 items and every appliance.
Kitchens are a usual home's (stove, oven, toaster, kettle, blender, sandwich press) plus any extra
appliance a user has, and fridges hold about 45-55 items, pantry included, enough for options and rich menus,
except demo (the app's
starter fridge), sparse and bare (#188).
- greek: explore mode, with figs and pomegranate in season.
SAMPLE_MODES holds the Suggest mode a sample's user usually presses.

chat_scenario() gives the chat a Suggest press comes after (--scenario, #159): none (fresh), a few
typed messages (chat), or the same messages between two earlier presses (pressed). The messages are
in the sample's reply language, and mixed has no chat: en and tr cover it (#178).

PLAN_CASES are menus for the prep plan test, shaped the way the Prep Plan button sends them.

REVIEW_CASES are fixed drafts with items the fridge lacks, sent to the reviser alone (#148): a
missing dish ingredient another fridge item can replace, one nothing replaces, a fridge item
written with a cut on either side (big_fridge keeps "Turkey slices"), a favorite's fridge item
the review must keep, prep words to fix (#176), and items nobody eats on their own, served alone
beside the food they go with (#263).
"""

import random

from models.ingredient import DEMO_FRIDGE
from models.kitchen import KITCHEN_APPLIANCES
from models.units import count_unit
from services.fridge import same_name

# A usual home kitchen (#188)
_HOME = {"Stove", "Oven", "Toaster", "Kettle", "Blender", "Sandwich Press"}


def _kitchen(*extra: str) -> list[str]:
    """A usual home kitchen plus a user's extra appliances, in the app's order."""
    return [a["name"] for a in KITCHEN_APPLIANCES if a["name"] in _HOME | set(extra)]


def _fridge(groups: dict[str, list[str]]) -> list[dict]:
    return [{"name": name, "group_name": group} for group, names in groups.items() for name in names]


def _meal(name: str, *ingredients: str) -> dict:
    return {"meal_name": name, "ingredients": [{"name": i} for i in ingredients]}


def _favorite(name: str, *menu: str | tuple[str, list[str]]) -> dict:
    """A meal saved in Favorites: each menu entry is a simple item's name or a (dish, ingredients) pair."""
    return {"meal_name": name, "menu_items": [
        {"name": m[0], "ingredients": [{"name": i} for i in m[1]]} if isinstance(m, tuple)
        else {"name": m, "ingredients": []}
        for m in menu
    ]}


# What every sample shares unless it says otherwise: no preferences, habits, rules or
# supplements, a usual home kitchen, an empty shopping list and no staples, saved favorite meals or ratings
_BASE = {
    "country": "Türkiye",
    "preferences": {},
    "stated_habits": [],
    "inferred_habits": [],
    "health_rules": [],
    "user_profile": None,
    "supplements": [],
    "avoid_list": [],
    "kitchen_appliances": _kitchen(),
    "weekly_summary": None,
    "shopping_list": [],
    "favorites": [],
    "favorite_meals": [],
    "ratings": [],
}

_TURKISH_FRIDGE = _fridge({
    "🐄 Animal Products": [
        "Yumurta", "Beyaz peynir", "Kaşar peyniri", "Lor peyniri", "Tereyağı", "Kaymak", "Yoğurt", "Süt", "Sucuk",
        "Pastırma", "Tulum peyniri", "Hellim"],
    "🥬 Produce": ["Domates", "Salatalık", "Sivri biber", "Maydanoz", "Soğan", "Patates", "Ispanak", "Limon", "Sarımsak", "Taze soğan", "Dereotu", "Kabak", "Muz", "Elma"],
    "🍞 Breads": ["Ekmek", "Simit", "Lavaş", "Pide", "Tam buğday ekmeği"],
    "🍯 Sweets": ["Bal", "Vişne reçeli", "Tahin", "Pekmez", "Kayısı reçeli"],
    "🫒 Breakfast Staples": ["Siyah zeytin", "Yeşil zeytin"],
    "🥜 Nuts & Seeds": ["Ceviz", "Fındık", "Badem", "Susam"],
    "☕ Beverages": ["Çay", "Türk kahvesi", "Portakal suyu"],
    "🧂 Spices": ["Pul biber", "Kekik", "Kimyon", "Nane", "Sumak"],
    "🫙 Pantry": ["Tuz", "Karabiber", "Zeytinyağı", "Ayçiçek yağı", "Un", "Domates salçası", "Yulaf", "Kabartma tozu"],
})

SAMPLES = {
    "en": {
        **_BASE,
        "language": "en",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Eggs", "White cheese", "Cheddar", "Butter", "Yogurt", "Milk", "Sausages", "Cream cheese", "Smoked turkey"],
            "🥬 Produce": [
                "Tomatoes", "Cucumber", "Green peppers", "Onion", "Potatoes", "Spinach", "Mushrooms", "Lemons", "Banana",
                "Apples", "Parsley", "Garlic", "Zucchini", "Strawberries", "Oranges"],
            "🍞 Breads": ["Bread", "Simit", "Whole wheat bread", "Pita bread"],
            "🍯 Sweets": ["Honey", "Strawberry jam", "Tahini", "Chocolate spread"],
            "🫒 Breakfast Staples": ["Olives", "Granola"],
            "🥜 Nuts & Seeds": ["Walnuts", "Almonds", "Hazelnuts", "Sesame seeds"],
            "☕ Beverages": ["Tea", "Coffee", "Orange juice"],
            "🧂 Spices": ["Red pepper flakes", "Paprika", "Cumin", "Oregano", "Cinnamon"],
            "🫙 Pantry": ["Salt", "Black pepper", "Olive oil", "Oats", "Flour", "Tomato paste", "Sunflower oil", "Baking powder", "Sugar"],
        }),
        "history": [
            {"meal_name": "Cheese omelette"},
            {"meal_name": "Oatmeal with banana and honey"},
            {"meal_name": "Menemen"},
        ],
        "favorite_meals": [
            _favorite("Menemen", ("Menemen", ["Eggs", "Tomatoes", "Green peppers", "Olive oil"]), "Bread"),
            _favorite("Avocado toast", ("Avocado toast", ["Bread", "Avocado", "Eggs"])),
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
    # A fridge too small for any breakfast: the press ends with a note that says what to change
    "bare": {
        **_BASE,
        "language": "en",
        "ingredients": _fridge({"☕ Beverages": ["Tea"], "🫙 Pantry": ["Salt"]}),
        "history": [],
        "expects_note": True,
    },
    "vegan": {
        **_BASE,
        "language": "en",
        "ingredients": _fridge({
            "🌱 Plant-Based": ["Soy milk", "Peanut butter", "Tofu", "Oat milk", "Coconut yogurt", "Almond butter"],
            "🥬 Produce": [
                "Banana", "Tomatoes", "Cucumber", "Spinach", "Avocado", "Mushrooms", "Onion", "Bell peppers",
                "Sweet potatoes", "Lemons", "Garlic", "Kale", "Zucchini", "Blueberries", "Apples", "Oranges"],
            "🍞 Breads": ["Bread", "Tortillas", "Bagels"],
            "🍯 Sweets": ["Maple syrup", "Dates", "Dark chocolate"],
            "🫒 Breakfast Staples": ["Olives", "Hummus", "Granola"],
            "🥜 Nuts & Seeds": ["Walnuts", "Almonds", "Chia seeds", "Flax seeds", "Pumpkin seeds", "Cashews"],
            "☕ Beverages": ["Tea", "Coffee", "Orange juice"],
            "🧂 Spices": ["Cinnamon", "Turmeric", "Cumin", "Paprika", "Chili flakes"],
            "🫙 Pantry": ["Oats", "Chickpeas", "Olive oil", "Salt", "Black pepper", "Black beans", "Quinoa", "Nutritional yeast", "Flour", "Baking powder"],
        }),
        "stated_habits": ["Plant-based"],
        "avoid_list": ["Eggs", "Milk", "Cheese", "Butter", "Honey", "Yogurt"],
        "history": [_meal("Overnight oats", "Oats", "Soy milk", "Chia seeds", "Banana")],
    },
    "picky": {
        **_BASE,
        "language": "en",
        "country": "Canada",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Eggs", "Milk", "Butter", "Cheddar", "Cream cheese", "Yogurt", "Bacon", "Ham", "Mozzarella", "Sausages", "Turkey slices"],
            "🥬 Produce": ["Strawberries", "Bananas", "Apples", "Tomatoes", "Mushrooms", "Potatoes", "Onion", "Raspberries", "Peaches", "Bell peppers", "Spinach"],
            "🍞 Breads": ["Bread", "Bagels", "English muffins", "Tortillas", "Croissants"],
            "🍯 Sweets": ["Maple syrup", "Honey", "Chocolate chips", "Strawberry jam"],
            "🫒 Breakfast Staples": ["Olives", "Granola", "Cereal"],
            "🌱 Plant-Based": ["Almond milk"],
            "☕ Beverages": ["Orange juice", "Hot chocolate", "Coffee"],
            "🧂 Spices": ["Cinnamon", "Nutmeg"],
            "🫙 Pantry": ["Flour", "Sugar", "Baking powder", "Vanilla extract", "Oats", "Salt", "Vegetable oil", "Brown sugar", "Cocoa powder"],
        }),
        "preferences": {
            "fav:pancakes": "Pancakes", "fav:cheese": "Cheese",
            "dislike:tomatoes": "Tomatoes", "dislike:olives": "Olives", "dislike:mushrooms": "Mushrooms",
        },
        "avoid_list": ["Peanuts", "Almonds", "Walnuts", "Hazelnuts", "Cashews"],
        "stated_habits": ["Sweet breakfasts on weekends"],
        "kitchen_appliances": _kitchen("Microwave"),
        "history": [
            _meal("Pancakes with maple syrup", "Flour", "Eggs", "Milk", "Maple syrup"),
            _meal("Bagel with cream cheese", "Bagels", "Cream cheese"),
        ],
        "favorite_meals": [
            _favorite("Cheddar toast", ("Cheddar toast", ["Bread", "Butter", "Cheddar"]), "Orange juice"),
            _favorite(
                "Strawberry pancakes",
                ("Strawberry pancakes", ["Flour", "Eggs", "Milk", "Baking powder", "Strawberries", "Maple syrup"]),
            ),
        ],
        "favorites": ["Cheddar", "Strawberries", "Maple syrup", "Bagels"],
        "ratings": [
            {"product_name": "Strawberries", "rating": 9},
            {"product_name": "Cream cheese", "rating": 8},
            {"product_name": "Oats", "rating": 3},
        ],
    },
    "diabetic": {
        **_BASE,
        "language": "en",
        "country": "Germany",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Eggs", "Feta", "Cottage cheese", "Plain yogurt", "Milk", "Smoked salmon", "Turkey slices", "Greek yogurt", "Mozzarella"],
            "🥬 Produce": [
                "Tomatoes", "Cucumber", "Avocado", "Spinach", "Mushrooms", "Onion", "Bell peppers", "Zucchini", "Lemons",
                "Apples", "Strawberries", "Cherry tomatoes", "Blueberries", "Raspberries", "Pears", "Garlic", "Parsley"],
            "🍞 Breads": ["Rye bread", "White bread", "Whole grain crackers", "Whole wheat tortillas"],
            "🍯 Sweets": ["Honey", "Apricot jam"],
            "🫒 Breakfast Staples": ["Olives"],
            "🥜 Nuts & Seeds": ["Walnuts", "Almonds", "Chia seeds", "Flax seeds", "Pumpkin seeds", "Hazelnuts"],
            "☕ Beverages": ["Orange juice", "Coffee", "Green tea", "Herbal tea"],
            "🧂 Spices": ["Cinnamon", "Turmeric", "Oregano"],
            "🫙 Pantry": ["Oats", "Olive oil", "Salt", "Black pepper", "Chickpeas", "Quinoa"],
        }),
        "user_profile": {"age": 58, "gender": "female", "height_cm": 164, "weight_kg": 74, "activity_level": "light"},
        "health_rules": [
            {"rule_text": "Type 2 diabetes: keep blood sugar stable, low glycemic load", "priority": "critical"},
            {"rule_text": "Limit salt, high blood pressure", "priority": "high"},
        ],
        "supplements": [{"name": "Vitamin B12", "contents": "500 mcg B12", "frequency": "daily", "taken_today": 1}],
        "history": [
            _meal("Rye bread with feta", "Rye bread", "Feta", "Tomatoes"),
            _meal("Yogurt with strawberries", "Plain yogurt", "Strawberries"),
        ],
    },
    "student": {
        **_BASE,
        "language": "en",
        "country": "United Kingdom",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Eggs", "Milk", "Cheddar", "Butter", "Sausages", "Ham", "Yogurt"],
            "🥬 Produce": ["Bananas", "Apples", "Tomatoes", "Onion", "Potatoes", "Frozen peas", "Frozen berries", "Mushrooms", "Spinach", "Oranges"],
            "🍞 Breads": ["Bread", "Tortillas", "Bagels", "Crumpets"],
            "🍯 Sweets": ["Strawberry jam", "Peanut butter", "Chocolate spread", "Honey", "Golden syrup"],
            "🫒 Breakfast Staples": ["Baked beans", "Cornflakes", "Granola"],
            "☕ Beverages": ["Instant coffee", "Tea", "Orange juice"],
            "🧂 Spices": ["Chili flakes", "Mixed herbs"],
            "🫙 Pantry": ["Porridge oats", "Flour", "Salt", "Black pepper", "Sunflower oil", "Ketchup", "Brown sauce", "Baking powder", "Sugar"],
        }),
        "user_profile": {"age": 20, "gender": "male", "height_cm": 181, "weight_kg": 70, "activity_level": "light"},
        "stated_habits": ["No time on weekdays, 10 minutes max"],
        "kitchen_appliances": _kitchen("Microwave"),
        "history": [
            _meal("Toast with jam", "Bread", "Strawberry jam", "Butter"),
            _meal("Beans on toast", "Baked beans", "Bread"),
        ],
    },
    "big_fridge": {
        **_BASE,
        "language": "en",
        "country": "United States",
        "ingredients": _fridge({
            "🐄 Animal Products": [
                "Eggs", "Bacon", "Turkey slices", "Cheddar", "Mozzarella", "Cream cheese", "Greek yogurt", "Milk",
                "Butter", "Heavy cream", "Sausages", "Parmesan"],
            "🥬 Produce": [
                "Spinach", "Kale", "Bell peppers", "Onion", "Garlic", "Tomatoes", "Avocado", "Mushrooms", "Zucchini",
                "Sweet potatoes", "Apples", "Bananas", "Blueberries", "Strawberries", "Lemons", "Cherry tomatoes", "Raspberries", "Oranges", "Arugula"],
            "🍞 Breads": ["Whole wheat bread", "Bagels", "Tortillas", "English muffins", "Croissants"],
            "🍯 Sweets": ["Maple syrup", "Honey", "Strawberry jam", "Nutella", "Peanut butter"],
            "🫒 Breakfast Staples": ["Granola", "Cereal"],
            "🥜 Nuts & Seeds": ["Almonds", "Pecans", "Flax seeds", "Walnuts", "Chia seeds"],
            "🌱 Plant-Based": ["Almond milk"],
            "☕ Beverages": ["Coffee", "Orange juice", "Green tea"],
            "🧂 Spices": ["Cinnamon", "Paprika", "Chili flakes"],
            "🫙 Pantry": ["Salt", "Black pepper", "Olive oil", "Flour", "Baking powder", "Sugar", "Vanilla extract", "Oats"],
        }),
        "user_profile": {"age": 35, "gender": "female", "height_cm": 170, "weight_kg": 63, "activity_level": "active"},
        "kitchen_appliances": ["Stove", "Oven", "Air Fryer", "Toaster", "Microwave", "Blender", "Sandwich Press", "Kettle"],
        "history": [
            _meal("Avocado toast", "Whole wheat bread", "Avocado", "Eggs"),
            _meal("Blueberry pancakes", "Flour", "Eggs", "Milk", "Blueberries", "Maple syrup"),
            _meal("Yogurt parfait", "Greek yogurt", "Granola", "Strawberries"),
        ],
        "favorite_meals": [
            _favorite("Salmon bagel", ("Salmon bagel", ["Bagels", "Cream cheese", "Smoked salmon"])),
            _favorite("Berry smoothie", ("Berry smoothie", ["Greek yogurt", "Blueberries", "Bananas", "Almond milk"])),
        ],
    },
    "greek": {
        **_BASE,
        "language": "en",
        "country": "Greece",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Feta", "Greek yogurt", "Eggs", "Butter", "Milk", "Kasseri", "Halloumi"],
            "🥬 Produce": [
                "Tomatoes", "Cucumber", "Red onion", "Green peppers", "Spinach", "Zucchini", "Lemons", "Figs", "Pomegranate",
                "Grapes", "Garlic", "Dill", "Mint", "Oranges", "Potatoes"],
            "🍞 Breads": ["Pita bread", "Sourdough bread", "Phyllo dough", "Koulouri"],
            "🍯 Sweets": ["Honey", "Tahini", "Fig jam", "Sour cherry jam"],
            "🫒 Breakfast Staples": ["Kalamata olives", "Hummus", "Green olives"],
            "🥜 Nuts & Seeds": ["Walnuts", "Almonds", "Pistachios", "Pine nuts"],
            "☕ Beverages": ["Greek coffee", "Mountain tea", "Orange juice"],
            "🧂 Spices": ["Oregano", "Cinnamon", "Thyme"],
            "🫙 Pantry": ["Olive oil", "Salt", "Black pepper", "Flour", "Sesame seeds", "Semolina", "Raisins"],
        }),
        "history": [
            _meal("Greek yogurt with honey and walnuts", "Greek yogurt", "Honey", "Walnuts"),
            _meal("Kagianas", "Eggs", "Tomatoes", "Feta"),
        ],
    },
}

# The Suggest mode a sample's user usually presses; the others press plain Suggest
SAMPLE_MODES = {"picky": "favorites", "greek": "explore"}


# ── Chat scenarios ──────────────────────────────────────────────────────────

# What a Suggest press comes after: a fresh chat, typed messages, or typed messages between earlier presses
SCENARIOS = ("fresh", "chat", "pressed")
# The time limit the chat asks for
CHAT_MINUTES = 10
# What each of the chat's four typed messages asks, in order: the chat persona's test scores a reply per message
CHAT_MESSAGES = ("leave_out", "liked", "time", "allowed")
# Seeds each sample's picks, so tests compare
CHAT_SEED = 159
# Basics and drinks are picked only when a fridge has too few other items ("No salt please" is no breakfast wish)
_BASICS = {"🫙 Pantry", "🧂 Spices", "☕ Beverages"}
# Samples with no chat scenario: mixed tests Turkish fridge names with English replies, and en and tr cover the chat
NO_CHAT = {"mixed"}


def chat_picks(sample: dict, key: str) -> list[str] | None:
    """Four different fridge items for a sample's chat, the same on every test: A (left out), B (liked),
    C (left out, then allowed again) and D (only on an earlier menu). None of them is avoided or disliked.
    None when the fridge has fewer than four such items."""
    banned = list(sample["avoid_list"]) + [v for k, v in sample["preferences"].items() if k.startswith("dislike:")]
    names = [i for i in sample["ingredients"] if not any(same_name(i["name"], b) for b in banned)]
    rng = random.Random(f"{CHAT_SEED}:{key}")
    picks = []
    for group in ([i for i in names if i["group_name"] not in _BASICS], [i for i in names if i["group_name"] in _BASICS]):
        picks += rng.sample([i["name"] for i in group], len(group))
    return picks[:4] if len(picks) >= 4 else None


def _plate(name: str, items: list[str], language: str) -> dict:
    """An earlier suggestion: fridge items served as they are."""
    unit = count_unit(language)
    return {
        "menu_name": name,
        "menu": [{"name": i, "amount": 1, "unit": unit, "ingredients": []} for i in items],
        "prep_time_min": 5,
    }


def _lower(name: str, language: str) -> str:
    """A fridge name inside a sentence: lowercase, with Turkish I and İ as ı and i."""
    return (name.replace("I", "ı").replace("İ", "i") if language == "tr" else name).lower()


def chat_texts(a: str, b: str, c: str, language: str) -> tuple[str, ...]:
    """The four typed messages, in the user's reply language: leave out A and C, love B, the time limit,
    then allow C again. A Turkish sentence starts with a fridge name, so no case ending is needed."""
    if language == "tr":
        return (
            f"{a} ve {_lower(c, language)} olmasın lütfen.",
            f"{b} olsun mutlaka, çok seviyorum.",
            f"Sadece {CHAT_MINUTES} dakikam var.",
            f"Aslında {_lower(c, language)} olabilir, sorun değil.",
        )
    return (
        f"No {a.lower()} please, and no {c.lower()} either.",
        f"I love {b.lower()}.",
        f"I only have {CHAT_MINUTES} minutes.",
        f"Actually {c.lower()} is fine again.",
    )


def chat_scenario(key: str, name: str) -> dict | None:
    """The chat before the Suggest press under test, and what it asks, so code can check the reply.

    chat lists the user's typed messages ({"role": "user", "content": ...}) and earlier Suggest presses
    ({"press": meal}, the menu that press got), oldest first. leave_out is still asked to be left out,
    liked and allowed (a ban taken back) must not be left out, and max_minutes is the time the chat gives.
    None for a fresh chat, a sample in NO_CHAT, or when the sample's fridge is too small."""
    if name == "fresh" or key in NO_CHAT:
        return None
    sample = SAMPLES[key]
    picks = chat_picks(sample, key)
    if picks is None:
        return None
    a, b, c, d = picks
    language = sample["language"]
    typed = [{"role": "user", "content": text} for text in chat_texts(a, b, c, language)]
    if name == "chat":
        chat = typed
    else:
        chat = [
            {"press": _plate("Breakfast plate", [a, b, c], language)},
            typed[0],
            {"press": _plate("Light plate", [b, d], language)},
            *typed[1:],
        ]
    return {"chat": chat, "leave_out": [a], "liked": [b], "allowed": [c], "max_minutes": CHAT_MINUTES}


def _dish(name: str, method: str, *ingredients: tuple) -> dict:
    return {"name": name, "method": method, "ingredients": [
        {"name": n, "amount": a, "unit": u, **({"prep": p[0]} if p else {})} for n, a, u, *p in ingredients
    ]}


def _served(name: str, amount: float, unit: str, method: str = "") -> dict:
    """A simple item: served as it is, or readied the way its method says (#156)."""
    return {"name": name, "amount": amount, "unit": unit, "ingredients": [], **({"method": method} if method else {})}


# The server menu whose avocado toast was toasted first and went cold while the avocado was mashed (#160).
# Its method names the toasting first, the way the reviser wrote it.
_SERVER_MENU = [
    _dish("Banana chia pudding", "Stir the chia seeds into the milk, let it set, top with the banana",
          ("Chia seeds", 3, "tbsp"), ("Milk", 1, "glass"), ("Banana", 1, "pcs", "sliced")),
    _dish("Salmon oatmeal", "Simmer the oats in the water, stir in the chard, top with the salmon",
          ("Oats", 1, "glass", "rolled"), ("Water", 1, "glass"), ("Chard", 50, "g", "chopped"),
          ("Smoked salmon", 50, "g")),
    _dish("Avocado toast", "Toast the bread, mash the avocado with the lemon juice and salt, spread it on the toast",
          ("Bread", 2, "slice"), ("Avocado", 1, "pcs"), ("Lemon juice", 1, "tsp"), ("Salt", 1, "pinch")),
]


# Menus for the prep plan test (--persona plan), as a suggestion designs them: dishes with their
# method, plus simple items served as they are. The meal names don't give the method away.
# - boiled: an egg sandwich made with hard-boiled eggs, which a planner without the method fried (#121).
# - fried: the other way round, so a plan that boils these eggs is caught too.
# - porridge: simmered, with prep words on its ingredients.
# - menemen: a Turkish menu with a Turkish reply.
# - omelette: two cooked dishes, so one dish's steps can fill the other's wait (#144); both use eggs,
#   cooked two ways.
# - bowls: the server menu whose plan switched dishes every minute (#152): two dishes made of short
#   hands-on steps around their waits. The sweet potato is a simple item with a method: roasted in
#   the air fryer, so it gets steps (#156).
# - avocado, avocado_oven: the server menu with toast (#160), once in a home kitchen and once with an Oven
#   and no Toaster, so toasting may use either.
# - paired: a server menu once its review paired a spread and a dressing with the dishes they're served on or
#   with (serve_with, #263), so the plan input names each pairing.
PLAN_CASES = {
    "boiled": {
        "language": "en",
        "kitchen_appliances": _BASE["kitchen_appliances"],
        "meal_name": "Sandwich morning",
        "menu": [
            _dish("Egg sandwich", "Hard-boil the eggs, peel, slice into the buttered bread",
                  ("Eggs", 2, "pcs"), ("Bread", 2, "slice"), ("Butter", 1, "tsp")),
            _served("White cheese", 50, "g"),
            _served("Olives", 8, "pcs"),
        ],
    },
    "fried": {
        "language": "en",
        "kitchen_appliances": _BASE["kitchen_appliances"],
        "meal_name": "Toast morning",
        "menu": [
            _dish("Eggs on toast", "Fry the eggs in butter, toast the bread, lay the eggs on top",
                  ("Eggs", 2, "pcs"), ("Butter", 1, "tsp"), ("Bread", 2, "slice")),
            _served("Cucumber", 1, "pcs"),
        ],
    },
    "porridge": {
        "language": "en",
        "kitchen_appliances": _BASE["kitchen_appliances"],
        "meal_name": "Warm bowl",
        "menu": [
            _dish("Porridge", "Simmer the oats in the milk, top with the banana and honey",
                  ("Oats", 1, "glass", "rolled"), ("Milk", 1, "glass"), ("Banana", 1, "pcs", "sliced"),
                  ("Honey", 1, "tsp")),
            _served("Walnuts", 20, "g"),
        ],
    },
    "menemen": {
        "language": "tr",
        "kitchen_appliances": _BASE["kitchen_appliances"],
        "meal_name": "Kahvaltı tabağı",
        "menu": [
            _dish("Menemen", "Biberi ve domatesi zeytinyağında kavur, yumurtaları ekleyip karıştır",
                  ("Yumurta", 2, "adet"), ("Domates", 2, "adet", "doğranmış"), ("Sivri biber", 2, "adet"),
                  ("Zeytinyağı", 1, "yemek kaşığı")),
            _served("Beyaz peynir", 50, "g"),
            _served("Ekmek", 2, "dilim"),
        ],
    },
    "omelette": {
        "language": "en",
        "kitchen_appliances": _BASE["kitchen_appliances"],
        "meal_name": "Two egg plates",
        "menu": [
            _dish("Greek omelette", "Whisk the eggs with the feta, pour into the oiled pan over the tomato, fold",
                  ("Eggs", 3, "pcs"), ("Feta", 30, "g", "crumbled"), ("Tomatoes", 1, "pcs", "chopped"),
                  ("Olive oil", 1, "tbsp")),
            _dish("Boiled eggs", "Boil the eggs, cool them in cold water, peel and halve",
                  ("Eggs", 2, "pcs"), ("Salt", 1, "pinch")),
            _served("Bread", 1, "slice"),
        ],
    },
    "bowls": {
        "language": "en",
        "kitchen_appliances": _kitchen("Air Fryer"),
        "meal_name": "Autumn bowls",
        "menu": [
            _dish("Chia pudding", "Stir the chia seeds into the milk with the honey, let it set, top with the banana",
                  ("Chia seeds", 3, "tbsp"), ("Milk", 1, "glass"), ("Honey", 1, "tsp"),
                  ("Banana", 1, "pcs", "sliced")),
            _dish("Pumpkin oatmeal", "Simmer the oats in the milk, stir in the pumpkin purée, top with the tahini",
                  ("Oats", 1, "glass", "rolled"), ("Milk", 1, "glass"), ("Pumpkin purée", 100, "g"),
                  ("Tahini", 1, "tbsp")),
            _served("Sweet potato", 300, "g", "Peel and cube the sweet potato, roast it in the air fryer"),
        ],
    },
    "avocado": {
        "language": "en",
        "kitchen_appliances": _kitchen(),
        "meal_name": "Green morning",
        "menu": _SERVER_MENU,
    },
    "avocado_oven": {
        "language": "en",
        "kitchen_appliances": ["Stove", "Oven", "Kettle"],
        "meal_name": "Green morning",
        "menu": _SERVER_MENU,
    },
    "paired": {
        "language": "en",
        "kitchen_appliances": _kitchen(),
        "meal_name": "Pine nut morning",
        "menu": [
            _dish("Avocado and Pine Nut Toast", "Toast the bread, top with the avocado and the toasted pine nuts",
                  ("Bread", 2, "slice"), ("Avocado", 1, "pcs", "sliced"), ("Pine nuts", 1, "tbsp", "lightly toasted")),
            {**_dish("Pumpkin Puree Spread", "Spread on the toast", ("Pumpkin puree", 3, "tbsp")),
             "serve_with": "Avocado and Pine Nut Toast"},
            _dish("Chard and Chia Seed Omelette", "Whisk the eggs with the chia seeds, wilt the chard in the pan, pour the eggs over and fold",
                  ("Eggs", 2, "pcs"), ("Chard", 1, "handful", "chopped"), ("Chia seeds", 1, "tbsp"), ("Olive oil", 1, "tsp")),
            {**_dish("Tahini Dressing", "Mix the tahini with the oat milk", ("Tahini", 1, "tbsp"), ("Oat milk", 2, "tbsp")),
             "serve_with": "Chard and Chia Seed Omelette"},
            _served("Banana", 1, "pcs"),
        ],
    },
}


def _review(
    sample: str, name: str, minutes: int, *menu: dict, may_keep: tuple = (), lone: tuple = (), stocked: dict | None = None,
) -> dict:
    """A review case: the sample's user, in the Suggest mode they usually press, and a draft meal in
    the app's format, the way the pipeline hands it to the reviser. `may_keep` names missing items
    the review may keep as written although they contain a fridge name, so they count as still
    missing, not renamed (#176). `lone` names the draft's items nobody eats on their own, which the
    review moves into a dish, pairs with the item they're served with or on (`serve_with`), or leaves
    out when they go with nothing (#263). `stocked` adds items to the sample's fridge for this case, by group."""
    for item in menu:
        if not item.get("method"):  # the draft writes no methods; the reviser does
            item.pop("method", None)
    sample_user = SAMPLES[sample]
    return {
        **sample_user,
        "ingredients": sample_user["ingredients"] + _fridge(stocked or {}),
        "sample": sample,
        "may_keep": list(may_keep),
        "lone": list(lone),
        "draft": {"menu": list(menu), "menu_name": name, "description": f"{name} from the fridge.", "prep_time_min": minutes},
    }


REVIEW_CASES = {
    # The salmon has no fridge item that does its job, so it may stay missing (#148's frittata)
    "frittata": _review("greek", "Aegean morning", 20,
                        _dish("Salmon frittata", "", ("Eggs", 3, "pcs"), ("Smoked salmon", 50, "g"),
                              ("Feta", 40, "g", "crumbled"), ("Red onion", 0.5, "pcs", "chopped")),
                        _served("Pita bread", 1, "pcs"), _served("Greek coffee", 1, "tea glass")),
    # A far dish whose base the fridge has, like greek's real explore drafts (miso soup, edamame pancakes): two missing
    # seasonings in one dish, Sugar, which Honey replaces, and Soy sauce, which nothing in the fridge replaces
    "tamagoyaki": _review("greek", "Tokyo morning", 15,
                          _dish("Tamagoyaki", "", ("Eggs", 3, "pcs"), ("Sugar", 1, "tsp"), ("Soy sauce", 1, "tsp"),
                                ("Olive oil", 1, "tsp")),
                          _served("Mountain tea", 1, "glass")),
    # Renames both ways: the fridge's "Turkey slices" written plain, and "Avocado" written with its cut
    "wrap": _review("big_fridge", "Wrap morning", 10,
                    _dish("Turkey wrap", "", ("Tortillas", 1, "pcs"), ("Turkey", 60, "g"), ("Cream cheese", 1, "tbsp"),
                          ("Sliced avocado", 0.5, "pcs"), ("Spinach", 1, "handful")),
                    _served("Coffee", 1, "glass")),
    # A missing fruit a fridge fruit replaces, beside orange juice the fridge has (O's picky case)
    "pancakes": _review("picky", "Pancake morning", 25,
                        _dish("Blueberry pancakes", "", ("Flour", 1, "glass"), ("Eggs", 2, "pcs"), ("Milk", 1, "glass"),
                              ("Baking powder", 1, "tsp"), ("Blueberries", 80, "g"), ("Maple syrup", 2, "tbsp")),
                        _served("Orange juice", 1, "glass")),
    # Prep words (#176): a fridge item written with a cut (Diced onion), the fridge item with the cut in prep; a part
    # of one (Egg whites) and a product (Smoked cheddar), kept as written unless a swap does the same job, since a
    # rename loses the part; a word that changes nothing (mixed) and one that belongs to the bread (toasted), dropped;
    # and sweet potatoes with no prep word, which the method covers
    "omelette": _review("big_fridge", "Garden morning", 25,
                        _dish("Sweet potato omelette", "", ("Egg whites", 4, "pcs"), ("Sweet potatoes", 150, "g"),
                              ("Diced onion", 0.5, "pcs"), ("Smoked cheddar", 30, "g", "grated"),
                              ("Spinach", 1, "handful", "mixed")),
                        _dish("Jam toast", "", ("Whole wheat bread", 2, "slice"), ("Strawberry jam", 1, "tbsp", "toasted")),
                        _served("Coffee", 1, "glass"), may_keep=("Egg whites", "Smoked cheddar")),
    # A seasoning served as a menu item of its own beside the dish it flavors, the way a server menu listed cinnamon
    # (#263); everything is in the fridge, so the code check finds nothing and only the review's own question is left
    "cinnamon": _review("en", "Oat morning", 10,
                        _dish("Banana oatmeal", "", ("Oats", 0.5, "glass"), ("Milk", 1, "glass"),
                              ("Banana", 1, "pcs", "sliced"), ("Honey", 1, "tsp")),
                        _served("Cinnamon", 1, "tsp"), _served("Tea", 1, "tea glass"), lone=("Cinnamon",)),
    # A server menu (#263) that listed a spread, a dressing and cinnamon as items of their own beside the toast, the
    # omelette and a banana; the fridge has everything, so only the review's own question is left
    "paired": _review("en", "Pine nut morning", 20,
                      _dish("Avocado and Pine Nut Toast", "", ("Bread", 2, "slice"), ("Avocado", 1, "pcs", "sliced"),
                            ("Pine nuts", 1, "tbsp", "lightly toasted"), ("Oat milk", 2, "tbsp", "as a dressing or dip")),
                      _dish("Pumpkin Puree Spread", "", ("Pumpkin puree", 3, "tbsp")),
                      _dish("Chard and Chia Seed Omelette", "", ("Eggs", 2, "pcs"), ("Chard", 1, "handful", "chopped"),
                            ("Chia seeds", 1, "tbsp"), ("Olive oil", 1, "tsp")),
                      _served("Banana", 1, "pcs"),
                      _dish("Tahini Dressing", "", ("Tahini", 1, "tbsp"), ("Oat milk", 2, "tbsp")),
                      _served("Cinnamon", 1, "tsp"),
                      lone=("Pumpkin Puree Spread", "Tahini Dressing", "Cinnamon"),
                      stocked={"🥬 Produce": ["Avocado", "Chard"], "🥜 Nuts & Seeds": ["Pine nuts", "Chia seeds"],
                               "🌱 Plant-Based": ["Oat milk"], "🫙 Pantry": ["Pumpkin puree"]}),
}
