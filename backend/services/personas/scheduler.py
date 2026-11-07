"""
Scheduler persona — breaks a meal's menu into the steps each dish needs.

The LLM lists every dish's steps in order, each with its minutes, whether the cook is busy
(hands-on) or the food cooks on its own (waiting), and the appliance it uses.

All scheduling math (interleaving dishes, backward timing) is handled by our code
(routers/scheduler.py, _build_plan).
"""

from models.units import localize_unit

# The appliances the prompt offers when the user has none enabled
DEFAULT_APPLIANCES = ["Stove", "Air Fryer", "Toaster", "Oven"]

SCHEDULER_TEMPLATE = """You are a kitchen workflow expert. Your job is to break a breakfast menu (its dishes and ingredients, plus any recipe steps given) into the steps each dish needs. Code then orders the steps of all dishes into one timeline, so everything is ready at once.
{lang_instruction}
All `action` strings in the JSON output MUST be written in that language — do not mix languages.

For each dish, list its steps in the order they are done. Break the dish into its real steps, one action each: usually a few, as many as the dish needs, because code fills one dish's waiting time with another dish's work. Each step has:
- `action`: what to do, naming the menu's own ingredients and amounts
- `minutes`: how long the step takes, realistically
- `hands_on`: true while the cook is busy (whisk, chop, flip, plate), false while the food cooks on its own (boil, toast, bake) and the cook is free
- `appliance`: the appliance the step uses, from this list with these exact names (case-sensitive): {kitchen_appliances}; empty when the step needs none

Rules:
- Plan only what the menu lists. An ingredient's words after its amount (chopped, grated) say how to prepare it.
- A dish's method, in brackets after its name, is how the dish was designed, so plan it that way.
- Items served as they are go straight to the table, so they get no steps.
- Name each dish as the menu does, so the plan matches the meal.
- Output ONLY the JSON object, nothing else

Output format (inside ```json ... ``` fences). This shows the format only; the <…> parts are yours to fill:

```json
{{
  "dishes": [
    {{
      "dish": "<dish name from the menu>",
      "steps": [
        {{"action": "<first action>", "minutes": 2, "hands_on": true, "appliance": ""}},
        {{"action": "<next action>", "minutes": 6, "hands_on": false, "appliance": "<appliance from the list>"}},
        {{"action": "<last action>", "minutes": 1, "hands_on": true, "appliance": ""}}
      ]
    }}
  ]
}}
```

FINAL REMINDER: {lang_instruction} Write every action in that language, even when ingredient or meal names are in another language."""


def _lang(language: str) -> str:
    return "Always respond in Turkish." if language != "en" else "Always respond in English."


def build_scheduler_prompt(meal_name: str, steps: list[str], ingredients_str: str, kitchen_appliances: list[str] | None = None, language: str = "en") -> str:
    """Build the system prompt for plan extraction."""
    appliance_str = ", ".join(kitchen_appliances or DEFAULT_APPLIANCES)
    return SCHEDULER_TEMPLATE.format(kitchen_appliances=appliance_str, lang_instruction=_lang(language))


def _with_amount(item, language: str = "en") -> str:
    """'Egg (2 pcs)' for a dict with amount/unit, plus its prep words ('Oats (1 glass, rolled)'),
    the plain name otherwise. Units follow the language."""
    if not isinstance(item, dict):
        return str(item)
    name = item.get("name", "?")
    unit = localize_unit(item.get("unit"), language)
    qty = " ".join(str(v) for v in (item.get("amount"), unit) if v not in (None, ""))
    details = ", ".join(v for v in (qty, str(item.get("prep") or "").strip()) if v)
    return f"{name} ({details})" if details else name


def format_menu(menu: list, language: str = "en") -> str:
    """One line per menu item: dishes with their method and ingredients
    ('Egg sandwich (hard-boil the eggs, peel, slice into the bread): Egg (2 pcs), …'), a simple
    item with a method the same way, as a dish of itself ('Sweet potato (peel, cube and roast):
    Sweet potato (300 g)', #156), and the others with their amount, marked as served as they are."""
    lines = []
    for item in menu:
        method = str(item.get("method") or "").strip().rstrip(".") if isinstance(item, dict) else ""
        subs = (item.get("ingredients") or ([item] if method else [])) if isinstance(item, dict) else None
        if subs:
            name = f"{item.get('name', '?')} ({method})" if method else item.get("name", "?")
            lines.append(f"- {name}: {', '.join(_with_amount(s, language) for s in subs)}")
        else:
            lines.append(f"- {_with_amount(item, language)}, served as it is")
    return "\n".join(lines)


def build_scheduler_user_message(meal_name: str, steps: list[str], ingredients_str: str, menu: list | None = None, language: str = "en") -> str:
    """Build the user message with meal details. Menu-format meals usually have no steps."""
    parts = [f"Meal: {meal_name}"]
    if menu:
        parts.append(f"Menu:\n{format_menu(menu, language)}")
    else:
        parts.append(f"Ingredients: {ingredients_str}")
    if steps:
        parts.append("Steps:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)))
    parts.append("List each dish's steps:")
    return "\n\n".join(parts)
