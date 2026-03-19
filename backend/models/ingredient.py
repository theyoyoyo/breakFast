from pydantic import BaseModel
from typing import Optional


class IngredientCreate(BaseModel):
    name: str
    quantity: Optional[str] = None
    unit: Optional[str] = None


class IngredientUpdate(BaseModel):
    quantity: Optional[str] = None
    unit: Optional[str] = None


class Ingredient(BaseModel):
    id: int
    name: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    added_at: str
    updated_at: str
