"""
Shared food knowledge module — context formatters used by all personas.

Extracts common formatting logic so chat, suggestion, and analyst personas
share a single source of truth for how DB context is rendered into prompts.
This is the slim template — will be expanded with nutritional knowledge,
ingredient databases, and Turkish food context as needed.
"""

import json


# ---------------------------------------------------------------------------
# Context formatters
# ---------------------------------------------------------------------------

def format_ingredients(ingredients: list[dict]) -> str:
    if not ingredients:
        return "none listed yet"
    return ", ".join(
        f"{i['name']} ({i.get('quantity', '')} {i.get('unit', '')})".strip(" ()")
        for i in ingredients
    )


def format_history(history: list[dict], limit: int = 5) -> str:
    if not history:
        return "no history yet"
    return "; ".join(m["meal_name"] for m in history[-limit:])


def format_preferences(preferences: dict) -> str:
    if not preferences:
        return "none set yet"
    return json.dumps(preferences, ensure_ascii=False)


def format_habits(stated: list[str]) -> str:
    return "; ".join(stated) if stated else "none stated yet"


def format_health_rules(rules: list[dict] | list[str]) -> str:
    if not rules:
        return (
            "No user-defined health rules. Use your own nutrition knowledge to "
            "deprioritize unhealthy options (e.g., refined sugar, processed oils) "
            "but NEVER fully exclude anything the user has not explicitly asked to avoid."
        )
    priority_labels = {"critical": "TOP PRIORITY", "high": "Important", "low": "Nice to have"}
    lines = []
    for r in rules:
        if isinstance(r, dict):
            label = priority_labels.get(r.get("priority", "high"), "Important")
            lines.append(f"- [{label}] {r['rule_text']}")
        else:
            lines.append(f"- {r}")
    return "\n".join(lines)


def format_avoid_list(avoid_items: list[str] | None) -> str:
    if not avoid_items:
        return "No items on avoid list."
    items = ", ".join(avoid_items)
    return (
        f"HARD BAN — NEVER use these ingredients: {items}\n"
        "Suggest alternatives instead. For allergies, also consider cross-contamination risk."
    )


def format_behavioral(inferred_habits: list[str] | None) -> str:
    if not inferred_habits:
        return ""
    patterns = "\n".join(f"- {h}" for h in inferred_habits)
    return (
        "BEHAVIORAL PATTERNS (inferred from meal history — use to DIVERSIFY, not repeat):\n"
        f"{patterns}\n"
        "Focus on what the user is MISSING, not what they already eat enough of."
    )


def format_user_profile(profile: dict | None) -> str:
    if not profile:
        return "Not provided yet. Use general healthy adult defaults."
    parts = []
    if profile.get("age"):
        parts.append(f"Age: {profile['age']}")
    if profile.get("gender"):
        parts.append(f"Gender: {profile['gender']}")
    if profile.get("height_cm"):
        parts.append(f"Height: {profile['height_cm']} cm")
    if profile.get("weight_kg"):
        parts.append(f"Weight: {profile['weight_kg']} kg")
    if profile.get("activity_level"):
        parts.append(f"Activity level: {profile['activity_level']}")
    return "\n".join(f"- {p}" for p in parts) if parts else "Not provided yet. Use general healthy adult defaults."


def format_supplements(supplements: list[dict] | None) -> str:
    if not supplements:
        return "No supplements registered."
    lines = []
    for s in supplements:
        freq = s.get("frequency", "daily")
        name = s.get("name", "")
        contents = s.get("contents", "")
        taken_today = s.get("taken_today")
        status = ""
        if freq == "sometimes":
            status = " [taken today]" if taken_today else " [NOT taken today]"
        lines.append(f"- {name} ({freq}){status}")
        if contents:
            lines.append(f"  Contents: {contents}")
    return "\n".join(lines)


def format_ingredient_item(item) -> str:
    """Format a single ingredient — handles both string and structured {name, quantity, unit} forms."""
    if isinstance(item, dict):
        name = item.get("name", "")
        qty = item.get("quantity")
        unit = item.get("unit", "")
        if qty is not None:
            return f"{qty} {unit} {name}".strip()
        return name
    return str(item)


def format_meal_detail(meal: dict) -> str:
    """Format a single meal with its ingredients for analyst context."""
    name = meal.get("meal_name", "Unknown")
    ingredients = meal.get("ingredients", "[]")
    if isinstance(ingredients, str):
        try:
            ingredients = json.loads(ingredients)
        except (json.JSONDecodeError, TypeError):
            ingredients = []
    items = ", ".join(format_ingredient_item(i) for i in ingredients) if ingredients else "no items listed"
    return f"{name}: {items}"


def format_history_detailed(history: list[dict], limit: int = 5) -> str:
    """Format meal history with ingredient details (for analyst use)."""
    if not history:
        return "no history yet"
    meals = history[-limit:]
    return "\n".join(f"- {format_meal_detail(m)}" for m in meals)
