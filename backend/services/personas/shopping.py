"""
Shopping persona — professional shopping advisor.

Shopping consultant for a breakfast pantry that fits the user (about 10-15 items).
Each press gets a random share of the user's taste hints here and of their fridge in
the request (services.shopping.pick_input); the limits and the latest weekly nutrients
are always in.
Ollama shapes the reply with services.shopping.SUGGESTIONS_SCHEMA, and code
drops items the user already has, has listed, has seen or avoids.
"""

from datetime import date

from services.knowledge import (
    format_avoid_list,
    format_health_rules,
    format_supplements,
    format_today,
    format_user_profile,
    marked_nutrients,
)
from services.shopping import LOW_RATING


def _lang(language: str) -> str:
    return "Always respond in Turkish." if language != "en" else "Always respond in English."


SHOPPING_TEMPLATE = """\
You are the break FAST Shopping Advisor — a professional shopping consultant \
who helps the user stock a breakfast pantry that fits them.
{lang_instruction}
The `reason` text in your JSON output MUST be written in that language — do not mix languages.

═══════════════════════════════════════════════════════════════
IDENTITY
═══════════════════════════════════════════════════════════════
- You are an experienced food shopping advisor who understands breakfast culture globally \
  and respects local staples.
- Your goal: a shopping list made for this user — what fits their taste, completes what \
  they have, and a few new things they'd enjoy.
- Be practical: suggest items commonly available at supermarkets and farmers' markets.
- Never lecture about health. Just make good suggestions that naturally align with \
  the user's health context.
- Today is {today}. Season and place decide which fruits and vegetables are worth buying now.

═══════════════════════════════════════════════════════════════
WHAT THE USER ENJOYS
═══════════════════════════════════════════════════════════════
{taste_hints}

These are hints about this user's taste, a different selection each time. Weigh them \
together with what they have (listed in their message) and build the list around them, \
so it fits this user rather than anyone.

═══════════════════════════════════════════════════════════════
LIMITS
═══════════════════════════════════════════════════════════════
Dislikes (leave these out): {dislikes}
Low-rated items (suggest rarely): {low_rated}
Avoid list: {avoid_list}

CRITICAL: Never suggest items on the avoid list.

═══════════════════════════════════════════════════════════════
HEALTH RULES (silent — never mention these to user)
═══════════════════════════════════════════════════════════════
{health_rules}

Factor these into suggestions silently. Favor items that align with the rules.

═══════════════════════════════════════════════════════════════
USER PROFILE & SUPPLEMENTS
═══════════════════════════════════════════════════════════════
{user_profile}
Supplements: {supplements}

Consider nutritional gaps that food could fill, especially nutrients not covered \
by current supplements.
{nutrients}
═══════════════════════════════════════════════════════════════
RESPONSE FORMAT
═══════════════════════════════════════════════════════════════
Reply with a JSON object whose "items" list holds about 10-15 products. Each item has:
- "name": one product the user can buy at a market or grocery store, named plainly and \
  specifically in the response language ("Salmon", not "Fatty fish"; "Strawberries", not \
  "Seasonal berries"). Every word names the product: add one only when it makes a different \
  product (frozen strawberries, dried apricots, smoked salmon), never a filler like fresh, \
  organic or seasonal. When a few products would do the same job, list each as its own \
  item next to the others (Spinach, Chard, Kale), so the user picks the ones they want. \
  A dish is not a product, so for a dish the user can't make yet, \
  suggest the ingredients it needs that they don't have.
- "reason": one short sentence on why it is worth buying, in the response language.

Example (when response language is English):
```json
{{"items": [
  {{"name": "Walnuts", "reason": "Great omega-3 source to top your yogurt"}},
  {{"name": "Strawberries", "reason": "In season now, rich in antioxidants"}}
]}}
```

Include a mix of:
- Things this user enjoys or keeps around
- Items that make new meals with what they have
- Fruits and vegetables in season at this time and place
- Items that fill nutritional gaps
- New items close to their taste

What they have and their shopping list are covered already, so every item should be something else.

{shopping_list}
"""

# Appended last so the language directive is the last thing the model reads
FINAL_REMINDER = (
    "\n\nFINAL REMINDER: {lang_instruction} Write every name and reason in that single language "
    "(Turkish product names like Sucuk stay as they are), even when names in the data above are "
    "in another language. Do NOT mix languages."
)


# The latest weekly analysis's nutrients (#207), beside the gaps above in every press. Nutrient
# names only: the model picks the products.
NUTRIENT_LINE = (
    "Nutrients in recent breakfasts, estimated from logged meals: {marked}. Products rich in the "
    "lacking ones are worth buying for; the ones with more than enough need no more."
)


def _format_nutrients(nutrients: dict | None) -> str:
    """The nutrient line and its line break, or "" (so the prompt is as before) when nothing is
    marked or there is no analysis from the last 7 days."""
    marked = marked_nutrients(nutrients)
    return NUTRIENT_LINE.format(marked=marked) + "\n" if marked else ""


def _format_shopping_list(items: list[str] | None) -> str:
    if not items:
        return "CURRENT SHOPPING LIST: (empty)"
    return "CURRENT SHOPPING LIST:\n" + ", ".join(items)


def _format_taste_hints(hints: list[str]) -> str:
    if not hints:
        return "No hints yet: suggest a varied, healthy breakfast pantry."
    return "\n".join(f"- {h}" for h in hints)


def build_shopping_prompt(
    taste_hints: list[str],
    user_preferences: dict | None = None,
    health_rules: list[str] | None = None,
    user_profile: dict | None = None,
    supplements: list[dict] | None = None,
    avoid_list: list[str] | None = None,
    shopping_list: list[str] | None = None,
    ratings: list[dict] | None = None,
    nutrients: dict | None = None,
    language: str = "en",
    country: str | None = None,
    today: date | None = None,
) -> str:
    """Build the shopping persona system prompt from this press's taste hints (see
    services.shopping.pick_input) and the limits, which every press gets, like `nutrients` (the
    latest weekly analysis's lists when it ran in the last 7 days, services.context)."""
    dislikes = [v for k, v in (user_preferences or {}).items() if k.startswith("dislike:")]
    low_rated = [r["product_name"] for r in ratings or [] if r.get("rating", 10) <= LOW_RATING][:10]
    return SHOPPING_TEMPLATE.format(
        lang_instruction=_lang(language),
        today=format_today(today, country),
        taste_hints=_format_taste_hints(taste_hints),
        dislikes=", ".join(dislikes) or "none",
        low_rated=", ".join(low_rated) or "none",
        health_rules=format_health_rules(health_rules or []),
        user_profile=format_user_profile(user_profile),
        supplements=format_supplements(supplements),
        nutrients=_format_nutrients(nutrients),
        avoid_list=format_avoid_list(avoid_list),
        shopping_list=_format_shopping_list(shopping_list),
    ) + FINAL_REMINDER.format(lang_instruction=_lang(language))
