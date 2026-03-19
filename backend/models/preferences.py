from pydantic import BaseModel
from typing import Optional


class PreferenceSet(BaseModel):
    # Only `value` is needed — the key comes from the URL path parameter.
    value: str


class Preference(BaseModel):
    id: int
    key: str
    value: str
    updated_at: str


class HabitCreate(BaseModel):
    description: str
    source: Optional[str] = "stated"


class Habit(BaseModel):
    id: int
    description: str
    source: str
    created_at: str
