from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union, Any

from models.limits import (
    INGREDIENTS_MAX, MENU_ITEMS_MAX, STEPS_MAX,
    MealName, Name, Note, SizedDict, SizedItem, SizedList,
)


class MealIngredient(BaseModel):
    name: Name
    quantity: float
    unit: Name


class MealLog(BaseModel):
    meal_name: MealName
    description: Optional[Note] = None
    ingredients: Optional[List[Union[MealIngredient, Note]]] = Field(default=None, max_length=INGREDIENTS_MAX)
    steps: Optional[List[Note]] = Field(default=None, max_length=STEPS_MAX)
    prep_time_min: Optional[int] = None
    nutrition_note: Optional[Note] = None
    schedule: Optional[SizedDict] = None
    menu_items: Optional[SizedList] = Field(default=None, max_length=MENU_ITEMS_MAX)  # new multi-item menu format


class FavoriteIn(BaseModel):
    """A meal saved to Favorites, as the editor sends it (fields it doesn't list are ignored).
    The name comes as `menu_name` or `meal_name`, the menu as `menu_items` or `menu`."""
    meal_name: Optional[MealName] = None
    menu_name: Optional[MealName] = None
    description: Optional[Note] = None
    ingredients: Optional[List[SizedItem]] = Field(default=None, max_length=INGREDIENTS_MAX)
    steps: Optional[List[Note]] = Field(default=None, max_length=STEPS_MAX)
    prep_time_min: Optional[int] = None
    nutrition_note: Optional[Note] = None
    menu_items: Optional[SizedList] = Field(default=None, max_length=MENU_ITEMS_MAX)
    menu: Optional[SizedList] = Field(default=None, max_length=MENU_ITEMS_MAX)

    @field_validator("prep_time_min", mode="before")
    @classmethod
    def _whole_minutes(cls, v):
        """Older cards may carry the time as text or a fraction: keep a number, drop the rest."""
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return round(v)
        if isinstance(v, str):
            try:
                return round(float(v))
            except ValueError:
                return None
        return None

class Meal(BaseModel):
    id: int
    meal_name: str
    description: Optional[str] = None
    ingredients: Optional[List[Union[MealIngredient, str]]] = None
    steps: Optional[List[str]] = None
    prep_time_min: Optional[int] = None
    nutrition_note: Optional[str] = None
    schedule: Optional[dict] = None
    rating: Optional[int] = None
    cached_nutrition: Optional[dict] = None
    menu_items: Optional[List[Any]] = None  # new multi-item menu format
    logged_at: str
