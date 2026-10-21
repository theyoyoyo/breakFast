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
    # If ingredients have group_name, format as grouped sections for LLM context
    if any("group_name" in i for i in ingredients):
        from models.ingredient import INGREDIENT_GROUPS
        grouped: dict[str, list[str]] = {}
        for i in ingredients:
            g = i.get("group_name", "🍽️ Other")
            grouped.setdefault(g, []).append(i["name"])
        parts = []
        for group in INGREDIENT_GROUPS:
            if group in grouped:
                parts.append(f"[{group}] {', '.join(grouped[group])}")
        return "; ".join(parts) if parts else "none listed yet"
    return ", ".join(i["name"] for i in ingredients)


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
    """Full supplement list with frequency and taken-today status — for analyst use."""
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


def format_supplements_taken(supplements: list[dict] | None) -> str:
    """Only supplements active today — for meal planner use.

    Includes daily supplements always, and 'sometimes' supplements only if
    taken today. Returns name + contents so the LLM knows what nutrients
    are already covered without any scheduling logic.
    """
    if not supplements:
        return "None taken today."
    lines = []
    for s in supplements:
        freq = s.get("frequency", "daily")
        taken_today = s.get("taken_today")
        if freq != "daily" and not taken_today:
            continue  # skip not-taken-today
        name = s.get("name", "")
        contents = s.get("contents", "")
        line = f"- {name}"
        if contents:
            line += f": {contents}"
        lines.append(line)
    return "\n".join(lines) if lines else "None taken today."


def format_favorites(favorites: list[str]) -> str:
    if not favorites:
        return "No favorites set."
    return ", ".join(favorites)


def format_ratings(ratings: list[dict]) -> str:
    """Top-10 high-rated and bottom-10 low-rated items for shopping context."""
    high = [r["product_name"] for r in ratings if r.get("rating", 0) >= 7][:10]
    low  = [r["product_name"] for r in ratings if r.get("rating", 10) <= 4][:10]
    parts = []
    if high:
        parts.append(f"High-rated (favour these): {', '.join(high)}")
    if low:
        parts.append(f"Low-rated (avoid or minimise): {', '.join(low)}")
    return "\n".join(parts) if parts else "No ratings yet."


def format_ingredient_item(item) -> str:
    """Format a single ingredient — handles both string and dict forms."""
    if isinstance(item, dict):
        return item.get("name", "")
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


def format_history_for_weekly_review(meals: list[dict]) -> str:
    """Format meals for the weekly analyst prompt, grouped by date.

    Each entry shows the date, meal name, ingredient list, and nutrition note.
    Meals are presented oldest-first so the analyst reads them chronologically.
    """
    if not meals:
        return "No meals logged this week."
    # Sort oldest-first
    sorted_meals = sorted(meals, key=lambda m: m.get("logged_at", ""))
    lines = []
    for m in sorted_meals:
        date_str = m.get("logged_at", "")[:10]  # YYYY-MM-DD
        name = m.get("meal_name", "Unknown")
        ingredients = m.get("ingredients", "[]")
        if isinstance(ingredients, str):
            try:
                ingredients = json.loads(ingredients)
            except (json.JSONDecodeError, TypeError):
                ingredients = []
        items = ", ".join(format_ingredient_item(i) for i in ingredients) if ingredients else "no items listed"
        note = m.get("nutrition_note") or ""
        line = f"[{date_str}] {name} — {items}"
        if note:
            line += f"\n  Note: {note}"
        lines.append(line)
    return "\n".join(lines)


def format_weekly_summary(summary: dict | None) -> str:
    """Format a saved weekly summary for the suggestion prompt (lean version).

    Only surfaces the narrative and weak areas (score < 75) — the planner
    doesn't need raw scores for well-covered dimensions.
    """
    if not summary:
        return "No weekly summary available yet."
    narrative = summary.get("narrative", "")
    scores_raw = summary.get("scores", "[]")
    if isinstance(scores_raw, str):
        try:
            scores = json.loads(scores_raw)
        except (json.JSONDecodeError, TypeError):
            scores = []
    else:
        scores = scores_raw

    weak = [s for s in scores if isinstance(s.get("score"), (int, float)) and s["score"] < 75]

    lines = [narrative] if narrative else []
    if weak:
        weak_parts = ", ".join(f"{s['label']} ({s['score']}/100)" for s in weak)
        lines.append(f"Weak this week — prioritize: {weak_parts}.")
    return "\n".join(lines) if lines else "No weekly summary available yet."
