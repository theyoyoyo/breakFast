from pydantic import BaseModel
from typing import Optional

from models.limits import ShortText, Text


class PreferenceSet(BaseModel):
    # Only `value` is needed — the key comes from the URL path parameter.
    value: Text


class Preference(BaseModel):
    id: int
    key: str
    value: str
    updated_at: str


class HabitCreate(BaseModel):
    description: Text
    source: Optional[ShortText] = "stated"


class Habit(BaseModel):
    id: int
    description: str
    source: str
    created_at: str
