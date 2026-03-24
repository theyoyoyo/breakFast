from pydantic import BaseModel
from typing import Optional


class IngredientCreate(BaseModel):
    name: str
    expiry_date: Optional[str] = None


class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    expiry_date: Optional[str] = None


class Ingredient(BaseModel):
    id: int
    name: str
    expiry_date: Optional[str] = None
    added_at: str
    updated_at: str
