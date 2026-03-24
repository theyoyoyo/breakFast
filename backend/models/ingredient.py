from pydantic import BaseModel


class IngredientCreate(BaseModel):
    name: str


class Ingredient(BaseModel):
    id: int
    name: str
    added_at: str
    updated_at: str
