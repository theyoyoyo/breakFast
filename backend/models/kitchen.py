from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Fixed kitchen appliances — single source of truth.
# To add a new appliance, append to KITCHEN_APPLIANCES and mirror in frontend.
# ---------------------------------------------------------------------------

KITCHEN_APPLIANCES = [
    {"key": "stove", "name": "Ocak"},
    {"key": "oven", "name": "Fırın"},
    {"key": "air_fryer", "name": "Airfryer"},
    {"key": "toaster", "name": "Ekmek Kızartma Makinesi"},
    {"key": "microwave", "name": "Mikrodalga"},
    {"key": "blender", "name": "Blender"},
    {"key": "sandwich_press", "name": "Tost Makinesi"},
    {"key": "kettle", "name": "Su Isıtıcı"},
    {"key": "french_press", "name": "French Press"},
]

# Only stove is enabled by default — user enables the rest
DEFAULT_ENABLED_KEYS = {"stove"}

VALID_APPLIANCE_KEYS = {a["key"] for a in KITCHEN_APPLIANCES}


class KitchenToggle(BaseModel):
    enabled: bool
