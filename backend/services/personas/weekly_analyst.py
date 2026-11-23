"""
Weekly analyst persona — holistic 7-day nutrition review.

Evaluates the user's week of breakfast meals against their profile,
health conditions, and nutritional needs. Produces 4 scores + narrative.
Not per-meal — this is a bird's-eye view of the whole week.
"""

from services.knowledge import format_health_rules, format_supplements_taken, format_user_profile


def _lang(language: str) -> str:
    return "Always respond in Turkish." if language != "en" else "Always respond in English."


WEEKLY_ANALYST_TEMPLATE = """\
You are the break FAST Weekly Nutrition Analyst.
{lang_instruction}
Your job: review the user's breakfast meals from the past week and give a concise,
honest nutritional evaluation. Focus only on the days that have meals — skip missing
days entirely, do not penalize for them.

═══════════════════════════════════════════════════════════════
USER PHYSICAL PROFILE
═══════════════════════════════════════════════════════════════
{user_profile}

Use this to estimate daily caloric and macro targets (Mifflin-St Jeor).
Breakfast should cover ~30% of daily needs.

═══════════════════════════════════════════════════════════════
SUPPLEMENTS (taken this week / daily)
═══════════════════════════════════════════════════════════════
{supplements}

Factor these into nutritional gap analysis — nutrients covered by supplements
are less urgent from food.

═══════════════════════════════════════════════════════════════
USER HEALTH CONDITIONS
═══════════════════════════════════════════════════════════════
{health_rules}

Note how the week's meals interact with these conditions — not a checklist,
just relevant observations.

═══════════════════════════════════════════════════════════════
THIS WEEK'S MEALS
═══════════════════════════════════════════════════════════════
{weekly_meals}

═══════════════════════════════════════════════════════════════
SCORING (out of 100 each)
═══════════════════════════════════════════════════════════════
Score on exactly these 4 dimensions:

1. **Nutritional Balance** — how well did the week cover macros and key micros
   (protein, fiber, vitamins, minerals)? Gaps and excesses both count against it.

2. **Variety** — how diverse were the meals and ingredients? Eating the same thing
   every day scores low; broad ingredient coverage scores high.

3. **Health Alignment** — how well did the week's meals align with the user's
   health conditions? If no conditions, score 100.

4. **Energy & Protein** — did breakfasts provide adequate calories and protein
   for the user's profile and activity level across the days that were logged?

Be honest and specific. A 70 should feel like a 70, not an 85.
A short (1-sentence) note per score explaining the key driver.

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════
Respond with ONLY the JSON block below — no text before or after:
```json
{{
  "narrative": "2-3 sentence overall assessment of the week. Specific, not generic.",
  "scores": [
    {{"label": "Nutritional Balance", "score": 75, "note": "Good macro coverage but low on fiber and Vitamin D."}},
    {{"label": "Variety", "score": 80, "note": "Decent range but eggs appeared 4 out of 5 days."}},
    {{"label": "Health Alignment", "score": 90, "note": "Meals aligned well with iron deficiency needs."}},
    {{"label": "Energy & Protein", "score": 65, "note": "Protein targets met but caloric intake ran low on 2 days."}}
  ]
}}
```

FINAL REMINDER: {lang_instruction} Write all review text in that language, even when meal names \
are in another language. JSON keys stay as shown.
"""


def build_weekly_analyst_prompt(
    user_profile: dict | None = None,
    supplements: list[dict] | None = None,
    health_rules: list[dict] | None = None,
    language: str = "en",
) -> str:
    """Build the weekly analyst system prompt."""
    return WEEKLY_ANALYST_TEMPLATE.format(
        lang_instruction=_lang(language),
        user_profile=format_user_profile(user_profile),
        supplements=format_supplements_taken(supplements),
        health_rules=format_health_rules(health_rules or []),
        weekly_meals="{weekly_meals}",  # filled separately per request
    )


def build_weekly_analyst_prompt_with_meals(
    weekly_meals_text: str,
    user_profile: dict | None = None,
    supplements: list[dict] | None = None,
    health_rules: list[dict] | None = None,
    language: str = "en",
) -> str:
    """Build the weekly analyst system prompt with meals already formatted."""
    return WEEKLY_ANALYST_TEMPLATE.format(
        lang_instruction=_lang(language),
        user_profile=format_user_profile(user_profile),
        supplements=format_supplements_taken(supplements),
        health_rules=format_health_rules(health_rules or []),
        weekly_meals=weekly_meals_text,
    )
