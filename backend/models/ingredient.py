from pydantic import BaseModel
from typing import Optional


# ---------------------------------------------------------------------------
# Fixed ingredient groups — single source of truth.
# To add a new group, append to INGREDIENT_GROUPS (before "Diğer").
# ---------------------------------------------------------------------------

INGREDIENT_GROUPS = ["🧀 Şarküteri", "🥬 Sebze/Meyve", "🌿 Baharatlar", "📦 Diğer"]
DEFAULT_GROUP = "📦 Diğer"


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
