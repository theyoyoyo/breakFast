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
- student: no stove (microwave, kettle, toaster), ten minutes on weekdays.
- big_fridge: about 50 items and every appliance.
- greek: explore mode, with figs and pomegranate in season.
SAMPLE_MODES holds the Suggest mode a sample's user usually presses.

PLAN_CASES are menus for the prep plan test, shaped the way the Prep Plan button sends them.
"""

from models.ingredient import DEMO_FRIDGE


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
# supplements, a basic kitchen, an empty shopping list and no staples, saved favorite meals or ratings
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
    "favorite_meals": [],
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
    "picky": {
        **_BASE,
        "language": "en",
        "country": "Canada",
        "ingredients": _fridge({
            "🐄 Animal Products": ["Eggs", "Milk", "Butter", "Cheddar", "Cream cheese", "Yogurt"],
            "🥬 Produce": ["Strawberries", "Bananas", "Tomatoes", "Mushrooms"],
            "🍞 Breads": ["Bread", "Bagels"],
            "🍯 Sweets": ["Maple syrup", "Honey"],
            "🫒 Breakfast Staples": ["Olives", "Granola"],
            "🌱 Plant-Based": ["Almond milk"],
            "☕ Beverages": ["Orange juice", "Hot chocolate"],
            "🫙 Pantry": ["Flour", "Sugar", "Baking powder", "Oats", "Salt", "Vegetable oil"],
        }),
        "preferences": {
            "fav:pancakes": "Pancakes", "fav:cheese": "Cheese",
            "dislike:tomatoes": "Tomatoes", "dislike:olives": "Olives", "dislike:mushrooms": "Mushrooms",
        },
        "avoid_list": ["Peanuts", "Almonds", "Walnuts", "Hazelnuts", "Cashews"],
        "stated_habits": ["Sweet breakfasts on weekends"],
        "kitchen_appliances": ["Stove", "Toaster", "Microwave"],
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
            "🐄 Animal Products": ["Eggs", "Feta", "Plain yogurt", "Milk"],
            "🥬 Produce": ["Tomatoes", "Cucumber", "Avocado", "Spinach", "Mushrooms", "Apples", "Strawberries"],
            "🍞 Breads": ["Rye bread", "White bread"],
            "🍯 Sweets": ["Honey", "Apricot jam"],
            "🥜 Nuts & Seeds": ["Walnuts", "Chia seeds"],
            "☕ Beverages": ["Orange juice", "Coffee"],
            "🧂 Spices": ["Cinnamon"],
            "🫙 Pantry": ["Olive oil", "Salt"],
        }),
        "user_profile": {"age": 58, "gender": "female", "height_cm": 164, "weight_kg": 74, "activity_level": "light"},
        "health_rules": [
            {"rule_text": "Type 2 diabetes: keep blood sugar stable, low glycemic load", "priority": "critical"},
            {"rule_text": "Limit salt, high blood pressure", "priority": "high"},
        ],
        "supplements": [{"name": "Vitamin B12", "contents": "500 mcg B12", "frequency": "daily", "taken_today": 1}],
        "kitchen_appliances": ["Stove", "Oven", "Toaster", "Kettle"],
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
            "🐄 Animal Products": ["Eggs", "Milk", "Cheddar", "Butter"],
            "🥬 Produce": ["Bananas", "Frozen peas"],
            "🍞 Breads": ["Bread"],
            "🍯 Sweets": ["Strawberry jam", "Peanut butter"],
            "🫒 Breakfast Staples": ["Baked beans"],
            "☕ Beverages": ["Instant coffee", "Tea"],
            "🫙 Pantry": ["Porridge oats", "Salt", "Sunflower oil", "Ketchup"],
        }),
        "user_profile": {"age": 20, "gender": "male", "height_cm": 181, "weight_kg": 70, "activity_level": "light"},
        "stated_habits": ["No time on weekdays, 10 minutes max"],
        "kitchen_appliances": ["Microwave", "Kettle", "Toaster"],
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
                "Butter", "Heavy cream",
            ],
            "🥬 Produce": [
                "Spinach", "Kale", "Bell peppers", "Onion", "Garlic", "Tomatoes", "Avocado", "Mushrooms", "Zucchini",
                "Sweet potatoes", "Apples", "Bananas", "Blueberries", "Strawberries", "Lemons",
            ],
            "🍞 Breads": ["Whole wheat bread", "Bagels", "Tortillas", "English muffins"],
            "🍯 Sweets": ["Maple syrup", "Honey", "Strawberry jam", "Nutella"],
            "🫒 Breakfast Staples": ["Granola", "Cereal"],
            "🥜 Nuts & Seeds": ["Almonds", "Pecans", "Flax seeds"],
            "🌱 Plant-Based": ["Almond milk"],
            "☕ Beverages": ["Coffee", "Orange juice"],
            "🧂 Spices": ["Cinnamon", "Paprika", "Chili flakes"],
            "🫙 Pantry": ["Salt", "Black pepper", "Olive oil", "Flour", "Baking powder", "Sugar", "Vanilla extract"],
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
            "🐄 Animal Products": ["Feta", "Greek yogurt", "Eggs"],
            "🥬 Produce": ["Tomatoes", "Cucumber", "Red onion", "Figs", "Pomegranate"],
            "🍞 Breads": ["Pita bread"],
            "🍯 Sweets": ["Honey", "Tahini"],
            "🫒 Breakfast Staples": ["Kalamata olives", "Hummus"],
            "🥜 Nuts & Seeds": ["Walnuts"],
            "☕ Beverages": ["Greek coffee"],
            "🧂 Spices": ["Oregano"],
            "🫙 Pantry": ["Olive oil", "Salt"],
        }),
        "kitchen_appliances": ["Stove", "Oven", "Kettle"],
        "history": [
            _meal("Greek yogurt with honey and walnuts", "Greek yogurt", "Honey", "Walnuts"),
            _meal("Kagianas", "Eggs", "Tomatoes", "Feta"),
        ],
    },
}

# The Suggest mode a sample's user usually presses; the others press plain Suggest
SAMPLE_MODES = {"picky": "favorites", "greek": "explore"}


def _dish(name: str, method: str, *ingredients: tuple) -> dict:
    return {"name": name, "method": method, "ingredients": [
        {"name": n, "amount": a, "unit": u, **({"prep": p[0]} if p else {})} for n, a, u, *p in ingredients
    ]}


def _served(name: str, amount: float, unit: str) -> dict:
    return {"name": name, "amount": amount, "unit": unit, "ingredients": []}


# Menus for the prep plan test (--persona plan), as a suggestion designs them: dishes with their
# method, plus simple items served as they are. The meal names don't give the method away.
# - boiled: an egg sandwich made with hard-boiled eggs, which a planner without the method fried (#121).
# - fried: the other way round, so a plan that boils these eggs is caught too.
# - porridge: simmered, with prep words on its ingredients.
# - menemen: a Turkish menu with a Turkish reply.
# - omelette: two cooked dishes, so one dish's steps can fill the other's wait (#144); both use eggs,
#   cooked two ways.
# - bowls: the server menu whose plan switched dishes every minute (#152): two dishes made of short
#   hands-on steps around their waits. The sweet potato is a simple item, served as it is until a
#   simple item may carry a method (#156); the air fryer is there for that method.
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
        "kitchen_appliances": ["Stove", "Air Fryer", "Kettle"],
        "meal_name": "Autumn bowls",
        "menu": [
            _dish("Chia pudding", "Stir the chia seeds into the milk with the honey, let it set, top with the banana",
                  ("Chia seeds", 3, "tbsp"), ("Milk", 1, "glass"), ("Honey", 1, "tsp"),
                  ("Banana", 1, "pcs", "sliced")),
            _dish("Pumpkin oatmeal", "Simmer the oats in the milk, stir in the pumpkin purée, top with the tahini",
                  ("Oats", 1, "glass", "rolled"), ("Milk", 1, "glass"), ("Pumpkin purée", 100, "g"),
                  ("Tahini", 1, "tbsp")),
            _served("Sweet potato", 300, "g"),
        ],
    },
}
