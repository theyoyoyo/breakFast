"""
Request size limits — single source of truth.

They stop abuse and mistakes (a script posting megabytes, a paste gone wrong), never real
use, so each one sits far above what the app sends. A request over a limit gets 422
(413 for a body too large to read at all). Change a number here, nowhere else.
"""

import json
from typing import Annotated, Any

from pydantic import AfterValidator, StringConstraints

# --- Text fields (characters) ---
NAME_MAX = 200             # a food, product, supplement or unit name
MEAL_NAME_MAX = 300        # a meal or menu name
SHORT_TEXT_MAX = 60        # a short pick: country, gender, activity level, a date
TEXT_MAX = 2_000           # a sentence or two the user writes: habit, health rule, preference
PREFERENCE_KEY_MAX = TEXT_MAX + 100  # a preference's key: its kind, then the text itself
NOTE_MAX = 5_000           # longer notes: description, supplement contents, a recipe step
CHAT_MESSAGE_MAX = 20_000  # one typed chat message
MESSAGE_CONTENT_MAX = 200_000  # a stored chat message: a reply with its meal card, an analysis, a plan
SESSION_ID_MAX = 100       # a chat session id

# --- Lists (items) ---
MENU_ITEMS_MAX = 100       # dishes and items on one menu
INGREDIENTS_MAX = 200      # ingredients of one meal
STEPS_MAX = 200            # recipe steps of one meal
BULK_ITEMS_MAX = 1_000     # one bulk request: shopping items, ids, names

# --- Free-form JSON (a meal as the app keeps it) ---
MEAL_JSON_MAX = 200_000    # characters once written as JSON

# --- Whole request ---
MAX_BODY_BYTES = 2 * 1024 * 1024

# --- Queries ---
MEALS_LIMIT_DEFAULT = 50
MEALS_LIMIT_MAX = 500      # GET /meals?limit=


def _sized(value: Any) -> Any:
    """Refuse free-form JSON that is too large once written out."""
    if value is not None and len(json.dumps(value, ensure_ascii=False, default=str)) > MEAL_JSON_MAX:
        raise ValueError("Too large")
    return value


Name = Annotated[str, StringConstraints(max_length=NAME_MAX)]
MealName = Annotated[str, StringConstraints(max_length=MEAL_NAME_MAX)]
ShortText = Annotated[str, StringConstraints(max_length=SHORT_TEXT_MAX)]
Text = Annotated[str, StringConstraints(max_length=TEXT_MAX)]
Note = Annotated[str, StringConstraints(max_length=NOTE_MAX)]
MessageContent = Annotated[str, StringConstraints(max_length=MESSAGE_CONTENT_MAX)]

# Free-form JSON values with a size cap
SizedDict = Annotated[dict, AfterValidator(_sized)]
SizedList = Annotated[list, AfterValidator(_sized)]
SizedItem = Annotated[dict | str, AfterValidator(_sized)]
