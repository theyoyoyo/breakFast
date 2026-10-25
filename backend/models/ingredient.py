from pydantic import BaseModel
from typing import Optional


# ---------------------------------------------------------------------------
# Fixed ingredient groups — single source of truth.
# To add a new group, append to INGREDIENT_GROUPS (before "Other").
# ---------------------------------------------------------------------------

INGREDIENT_GROUPS = [
    "🐄 Animal Products",
    "🥬 Produce",
    "🍞 Breads",
    "🍯 Sweets",
    "🫒 Breakfast Staples",
    "🥜 Nuts & Seeds",
    "🌱 Plant-Based",
    "☕ Beverages",
    "🧂 Spices",
    "🫙 Pantry",
    "🍽️ Other",
]
DEFAULT_GROUP = "🍽️ Other"


# ---------------------------------------------------------------------------
# Basics every kitchen has. Suggestions may use these without them being in
# the fridge; everything else (flour, sesame, oats…) goes in the Pantry group.
# ---------------------------------------------------------------------------

ALWAYS_AVAILABLE_TEXT = (
    "salt, black pepper, water, cooking oil, olive oil and common dried spices "
    "(red pepper flakes, cumin, oregano, dried mint, paprika, sumac, cinnamon)"
)

# Names the fridge check accepts as basics, in English and Turkish, written
# without Turkish letters (the check folds ğ→g, ı→i, ş→s… before comparing).
# No bare "pepper" or "mint": green peppers and fresh mint are produce.
ALWAYS_AVAILABLE_NAMES = [
    "salt", "tuz", "black pepper", "karabiber", "water", "su",
    "oil", "cooking oil", "vegetable oil", "sunflower oil", "olive oil",
    "yag", "sivi yag", "aycicek yagi", "zeytinyagi", "zeytin yagi",
    "spice", "spices", "baharat", "red pepper flakes", "chili flakes", "pul biber",
    "cumin", "kimyon", "oregano", "kekik", "thyme", "dried mint", "kuru nane",
    "paprika", "toz biber", "sumac", "sumak", "cinnamon", "tarcin",
]


class IngredientCreate(BaseModel):
    name: str
    expiry_date: Optional[str] = None
    group_name: Optional[str] = None


class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    expiry_date: Optional[str] = None
    group_name: Optional[str] = None


class Ingredient(BaseModel):
    id: int
    name: str
    expiry_date: Optional[str] = None
    expiry_acknowledged: bool = False
    group_name: str = DEFAULT_GROUP
    added_at: str
    updated_at: str
