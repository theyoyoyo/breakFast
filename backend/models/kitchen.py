from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Fixed kitchen appliances — single source of truth.
# To add a new appliance, append to KITCHEN_APPLIANCES and mirror in frontend.
# `hot`: food from it is hot and cools while it waits, so the prep plan serves it
# as soon as it can (routers/scheduler.py, #152).
# ---------------------------------------------------------------------------

KITCHEN_APPLIANCES = [
    {"key": "stove", "name": "Stove", "hot": True},
    {"key": "oven", "name": "Oven", "hot": True},
    {"key": "air_fryer", "name": "Air Fryer", "hot": True},
    {"key": "toaster", "name": "Toaster", "hot": True},
    {"key": "microwave", "name": "Microwave", "hot": True},
    {"key": "blender", "name": "Blender", "hot": False},
    {"key": "sandwich_press", "name": "Sandwich Press", "hot": True},
    {"key": "kettle", "name": "Kettle", "hot": True},
    {"key": "french_press", "name": "French Press", "hot": True},
]

# Names of the appliances whose food is hot, in lower case
HOT_APPLIANCES = {a["name"].lower() for a in KITCHEN_APPLIANCES if a["hot"]}

# Only stove is enabled by default — user enables the rest
DEFAULT_ENABLED_KEYS = {"stove"}

VALID_APPLIANCE_KEYS = {a["key"] for a in KITCHEN_APPLIANCES}


class KitchenToggle(BaseModel):
    enabled: bool
