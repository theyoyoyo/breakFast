"""
Scheduler persona — extracts a structured cooking plan from meal steps.

The LLM focuses on producing a detailed, clear plan. It splits tasks into:
- prep: quick manual tasks with no timing (chop, plate, mix)
- timed: tasks that need a specific resource for a specific duration

All scheduling math (parallel execution, backward timing) is handled by our code.
"""

SCHEDULER_TEMPLATE = """You are a kitchen workflow expert. Your job is to analyze a meal's preparation steps and produce a detailed, structured cooking plan.
{lang_instruction}
All `task`, `detail`, and `end_action` strings in the JSON output MUST be written in that language — do not mix languages.

Split the steps into two groups:

1. **prep**: Quick manual tasks with no specific timing — chopping, plating, mixing, putting into small bowls, slicing, etc. These are done first, before any timed cooking starts.

2. **timed**: Tasks that require a specific kitchen resource for a measured duration — boiling, toasting, frying, baking, etc. For each:
   - Estimate the duration in minutes (be realistic)
   - Specify the resource using an appliance name from this list (use these exact names, case-sensitive): {kitchen_appliances}. Only use these appliances.
   - Specify what to do when the task finishes (strain, remove, flip, etc.)

Rules:
- Expand the recipe steps — add necessary but missing actions (e.g., if the recipe says "boil eggs", also add "strain and transfer to cold water" as end_action)
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
```"""


def _lang(language: str) -> str:
    return "Always respond in Turkish." if language != "en" else "Always respond in English."


def build_scheduler_prompt(meal_name: str, steps: list[str], ingredients_str: str, kitchen_appliances: list[str] | None = None, language: str = "en") -> str:
    """Build the system prompt for plan extraction."""
    appliance_str = ", ".join(kitchen_appliances) if kitchen_appliances else "Stove, Air Fryer, Toaster, Oven"
    return SCHEDULER_TEMPLATE.format(kitchen_appliances=appliance_str, lang_instruction=_lang(language))


def build_scheduler_user_message(meal_name: str, steps: list[str], ingredients_str: str) -> str:
    """Build the user message with meal details."""
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    return f"""Meal: {meal_name}

Ingredients: {ingredients_str}

Steps:
{steps_text}

Produce the cooking plan:"""
