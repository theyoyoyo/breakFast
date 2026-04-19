from pydantic import BaseModel
from typing import Optional, List, Union, Any


class MealIngredient(BaseModel):
    name: str
    quantity: float
    unit: str


class MealLog(BaseModel):
    meal_name: str
    description: Optional[str] = None
    ingredients: Optional[List[Union[MealIngredient, str]]] = None
    steps: Optional[List[str]] = None
    prep_time_min: Optional[int] = None
    nutrition_note: Optional[str] = None
    schedule: Optional[dict] = None
    menu_items: Optional[List[Any]] = None  # new multi-item menu format


class MealRating(BaseModel):
    rating: int  # 1 = thumbs down, 5 = thumbs up


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
