from pydantic import BaseModel, field_validator
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
    "🫙 Pantry",  # long-life items and basics: flour, oil, sesame, oats…
    "🍽️ Other",
]
DEFAULT_GROUP = "🍽️ Other"

# Starter fridge for the opt-in demo user (DEMO_USER=true), added only when the
# account is first created. Basics are included because suggestions assume nothing.
DEMO_FRIDGE = [
    ("Salt", "🫙 Pantry"),
    ("Black pepper", "🫙 Pantry"),
    ("Olive oil", "🫙 Pantry"),
    ("Sunflower oil", "🫙 Pantry"),
    ("Red pepper flakes", "🧂 Spices"),
    ("Butter", "🐄 Animal Products"),
    ("Eggs", "🐄 Animal Products"),
    ("White cheese", "🐄 Animal Products"),
    ("Tomatoes", "🥬 Produce"),
    ("Cucumber", "🥬 Produce"),
    ("Bread", "🍞 Breads"),
    ("Olives", "🫒 Breakfast Staples"),
    ("Honey", "🍯 Sweets"),
    ("Tea", "☕ Beverages"),
]


def _clean_name(name: str | None) -> str | None:
    """Trim a fridge name; a blank one is refused (422). None stays None."""
    if name is None:
        return None
    name = name.strip()
    if not name:
        raise ValueError("Name can't be blank")
    return name


class IngredientCreate(BaseModel):
    name: str
    expiry_date: Optional[str] = None
    group_name: Optional[str] = None

    _trim_name = field_validator("name")(_clean_name)


class IngredientUpdate(BaseModel):
    name: Optional[str] = None  # None leaves the name as it is
    expiry_date: Optional[str] = None
    group_name: Optional[str] = None

    _trim_name = field_validator("name")(_clean_name)


class Ingredient(BaseModel):
    id: int
    name: str
    expiry_date: Optional[str] = None
    expiry_acknowledged: bool = False
    group_name: str = DEFAULT_GROUP
    added_at: str
    updated_at: str
