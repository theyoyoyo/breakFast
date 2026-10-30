"""
Scheduler persona — extracts a structured cooking plan from a meal's menu and steps.

The LLM focuses on producing a detailed, clear plan. It splits tasks into:
- prep: quick manual tasks with no timing (chop, plate, mix)
- timed: tasks that need a specific resource for a specific duration

All scheduling math (parallel execution, backward timing) is handled by our code.
"""

from models.units import localize_unit

SCHEDULER_TEMPLATE = """You are a kitchen workflow expert. Your job is to turn a breakfast menu (its dishes and ingredients, plus any recipe steps given) into a detailed, structured cooking plan.
{lang_instruction}
All `task`, `detail`, and `end_action` strings in the JSON output MUST be written in that language — do not mix languages.

Split the work into two groups:

1. **prep**: Quick manual tasks with no specific timing — chopping, slicing, grating, whisking, mixing. These are done first, before any timed cooking starts.

2. **timed**: Tasks that require a specific kitchen resource for a measured duration — boiling, toasting, frying, baking, etc. For each:
   - Estimate the duration in minutes (be realistic)
   - Specify the resource using an appliance name from this list (use these exact names, case-sensitive): {kitchen_appliances}. Only use these appliances.
   - Specify what to do when the task finishes (strain, remove, flip, etc.)

Rules:
- Plan only what the menu lists. Work out the actions each dish needs even when no steps are given; an ingredient's words after its amount (chopped, grated) say how to prepare it.
- A dish's method, in brackets after its name, is how the dish was designed, so plan it that way.
- Items served as they are need no timed task, and a prep task only when they must be cut first.
- Be realistic about durations
- Output ONLY the JSON object, nothing else

Output format (inside ```json ... ``` fences). This shows the format only; the <…> parts are yours to fill:

```json
{{
  "prep": [
    {{"task": "<manual task>", "detail": "<how, in a few words>"}}
  ],
  "timed": [
    {{
      "task": "<cooking task>",
      "duration_min": 5,
      "resource": "<appliance from the list>",
      "end_action": "<what to do when it finishes>"
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
    """One line per menu item: cooked dishes with their method and ingredients
    ('Egg sandwich (hard-boil the eggs, peel, slice into the bread): Egg (2 pcs), …'),
    simple items with their amount, marked as served as they are."""
    lines = []
    for item in menu:
        subs = item.get("ingredients") if isinstance(item, dict) else None
        if subs:
            method = str(item.get("method") or "").strip().rstrip(".")
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
    parts.append("Produce the cooking plan:")
    return "\n\n".join(parts)
