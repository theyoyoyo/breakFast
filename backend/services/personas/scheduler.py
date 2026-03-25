"""
Scheduler persona — decomposes meal steps into parallel kitchen tasks.

The LLM extracts structured Task objects from a meal's steps and ingredients,
which are then fed to the job-shop scheduler for optimal parallel execution.
"""

SCHEDULER_TEMPLATE = """You are a kitchen workflow expert. Your job is to decompose a meal's preparation steps into discrete parallel tasks for a kitchen scheduler.

Given a meal's steps and ingredients, output a JSON array of task objects. Each task has:
- "name": short task description (e.g. "boil eggs", "toast bread")
- "resource": exactly one of: "air_fryer", "toaster", "stove", "hands", "none"
  - "hands" = manual work (chopping, plating, mixing)
  - "none" = passive waiting (resting dough, cooling)
  - "stove" = stovetop/pot/pan
  - "toaster" = toaster or oven
  - "air_fryer" = air fryer
- "duration_min": estimated duration in minutes (float)
- "predecessors": list of task names that must finish before this one starts (empty list if none)
- "item": which ingredient/food item this task belongs to

Rules:
- Break compound steps into separate tasks when they use different resources
- Identify parallelism: tasks on different resources can run simultaneously
- Be realistic about durations
- Keep task names short and unique
- Only output the JSON array, nothing else

Output ONLY a JSON array wrapped in ```json ... ``` fences."""


def build_scheduler_prompt(meal_name: str, steps: list[str], ingredients_str: str) -> str:
    """Build the system prompt for task decomposition."""
    return SCHEDULER_TEMPLATE


def build_scheduler_user_message(meal_name: str, steps: list[str], ingredients_str: str) -> str:
    """Build the user message with meal details."""
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    return f"""Meal: {meal_name}

Ingredients: {ingredients_str}

Steps:
{steps_text}

Decompose into parallel kitchen tasks (JSON array):"""
