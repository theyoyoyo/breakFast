"""
Scheduler persona — extracts a structured cooking plan from a meal's menu and steps.

The LLM focuses on producing a detailed, clear plan. It splits tasks into:
- prep: quick manual tasks with no timing (chop, plate, mix)
- timed: tasks that need a specific resource for a specific duration

All scheduling math (parallel execution, backward timing) is handled by our code.
"""

SCHEDULER_TEMPLATE = """You are a kitchen workflow expert. Your job is to turn a breakfast menu (its dishes and ingredients, plus any recipe steps given) into a detailed, structured cooking plan.
{lang_instruction}
All `task`, `detail`, and `end_action` strings in the JSON output MUST be written in that language — do not mix languages.

Split the work into two groups:

1. **prep**: Quick manual tasks with no specific timing — chopping, plating, mixing, putting into small bowls, slicing, etc. These are done first, before any timed cooking starts.

2. **timed**: Tasks that require a specific kitchen resource for a measured duration — boiling, toasting, frying, baking, etc. For each:
   - Estimate the duration in minutes (be realistic)
   - Specify the resource using an appliance name from this list (use these exact names, case-sensitive): {kitchen_appliances}. Only use these appliances.
   - Specify what to do when the task finishes (strain, remove, flip, etc.)

Rules:
- Cover every item on the menu. Work out the actions each dish needs even when no steps are given, and add necessary but missing actions (e.g., for boiled eggs, add "strain and transfer to cold water" as end_action)
- Items served as-is (cheese, olives, honey, fruit) usually need only a prep task such as slicing or plating
- Be realistic about durations
- Output ONLY the JSON object, nothing else

Output format (inside ```json ... ``` fences):

```json
{{
  "prep": [
    {{"task": "Slice tomatoes and cucumber", "detail": "thin rounds"}}
  ],
  "timed": [
    {{
      "task": "Boil eggs",
      "duration_min": 7,
      "resource": "Stove",
      "end_action": "Drain and transfer to cold water"
    }}
  ]
}}
```

FINAL REMINDER: {lang_instruction} Write every task, detail and end_action in that language, even when \
ingredient or meal names are in another language."""


def _lang(language: str) -> str:
    return "Always respond in Turkish." if language != "en" else "Always respond in English."


def build_scheduler_prompt(meal_name: str, steps: list[str], ingredients_str: str, kitchen_appliances: list[str] | None = None, language: str = "en") -> str:
    """Build the system prompt for plan extraction."""
    appliance_str = ", ".join(kitchen_appliances) if kitchen_appliances else "Stove, Air Fryer, Toaster, Oven"
    return SCHEDULER_TEMPLATE.format(kitchen_appliances=appliance_str, lang_instruction=_lang(language))


def _with_amount(item) -> str:
    """'Egg (2 adet)' for a dict with amount/unit, the plain name otherwise."""
    if not isinstance(item, dict):
        return str(item)
    name = item.get("name", "?")
    qty = " ".join(str(v) for v in (item.get("amount"), item.get("unit")) if v not in (None, ""))
    return f"{name} ({qty})" if qty else name


def format_menu(menu: list) -> str:
    """One line per menu item: cooked dishes with their ingredients, simple items with their amount."""
    lines = []
    for item in menu:
        subs = item.get("ingredients") if isinstance(item, dict) else None
        if subs:
            lines.append(f"- {item.get('name', '?')}: {', '.join(_with_amount(s) for s in subs)}")
        else:
            lines.append(f"- {_with_amount(item)}")
    return "\n".join(lines)


def build_scheduler_user_message(meal_name: str, steps: list[str], ingredients_str: str, menu: list | None = None) -> str:
    """Build the user message with meal details. Menu-format meals usually have no steps."""
    parts = [f"Meal: {meal_name}"]
    if menu:
        parts.append(f"Menu:\n{format_menu(menu)}")
    else:
        parts.append(f"Ingredients: {ingredients_str}")
    if steps:
        parts.append("Steps:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)))
    parts.append("Produce the cooking plan:")
    return "\n\n".join(parts)
