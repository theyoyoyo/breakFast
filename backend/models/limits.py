"""
Request size limits — single source of truth.

They stop abuse and mistakes (a script posting megabytes, a paste gone wrong), never real
use, so each one sits far above what the app sends. A request over a limit gets 422
(413 for a body too large to read at all). Every field a request carries (body, path,
query) uses one of the types below or a constraint built on these numbers: a test walks
the app's routes and fails on a field without one. Change a number here, nowhere else.
"""

import json
from typing import Annotated, Any

from pydantic import AfterValidator, Field, StrictInt, StringConstraints

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
EMOJI_MAX = 16             # a meal's icon: one emoji, a few code points with its variation selectors
APPLIANCE_KEY_MAX = 100    # a kitchen appliance's key in a path

# --- Lists (items) ---
MENU_ITEMS_MAX = 100       # dishes and items on one menu
INGREDIENTS_MAX = 200      # ingredients of one meal
STEPS_MAX = 200            # recipe steps of one meal
BULK_ITEMS_MAX = 1_000     # one bulk request: shopping items, ids, names

# --- Free-form JSON (a meal as the app keeps it) ---
MEAL_JSON_MAX = 200_000    # characters once written as JSON

# --- Numbers ---
ID_MAX = 2**63 - 1         # a row id: SQLite's largest integer
PREP_TIME_MAX = 24 * 60    # a meal's prep time in minutes: a day
AMOUNT_MAX = 1_000_000     # an ingredient's quantity, in any unit
AGE_MAX = 150              # years
HEIGHT_CM_MAX = 300
WEIGHT_KG_MAX = 1_000

# --- Whole request ---
MAX_BODY_BYTES = 2 * 1024 * 1024  # counted as it arrives, declared length or not
# One chat socket frame, in characters, refused before it is read: a typed message at its
# limit fits many times over, even with every character escaped in the frame's JSON
CHAT_FRAME_MAX = 8 * CHAT_MESSAGE_MAX

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
Emoji = Annotated[str, StringConstraints(strip_whitespace=True, max_length=EMOJI_MAX)]

# Free-form JSON values with a size cap; the schema names the cap, so the route check sees it
_SIZED_SCHEMA = Field(json_schema_extra={"x-max-json-chars": MEAL_JSON_MAX})
SizedDict = Annotated[dict, AfterValidator(_sized), _SIZED_SCHEMA]
SizedList = Annotated[list, AfterValidator(_sized), _SIZED_SCHEMA]
SizedItem = Annotated[dict | str, AfterValidator(_sized), _SIZED_SCHEMA]

# Numbers
Id = Annotated[int, Field(ge=1, le=ID_MAX)]
StrictId = Annotated[StrictInt, Field(ge=1, le=ID_MAX)]
PrepMinutes = Annotated[int, Field(ge=0, le=PREP_TIME_MAX)]
Amount = Annotated[float, Field(ge=0, le=AMOUNT_MAX, allow_inf_nan=False)]
Age = Annotated[int, Field(ge=1, le=AGE_MAX)]
HeightCm = Annotated[int, Field(ge=1, le=HEIGHT_CM_MAX)]
WeightKg = Annotated[float, Field(gt=0, le=WEIGHT_KG_MAX, allow_inf_nan=False)]

# Text in a path
SessionId = Annotated[str, StringConstraints(max_length=SESSION_ID_MAX)]
PreferenceKey = Annotated[str, StringConstraints(max_length=PREFERENCE_KEY_MAX)]
ApplianceKey = Annotated[str, StringConstraints(max_length=APPLIANCE_KEY_MAX)]
