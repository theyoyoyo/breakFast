"""
Meal suggestion logic — two personas.

Chat persona: samimi kahvaltı arkadaşı, hafif DB context.
Suggestion persona: profesyonel diyetisyen, tam DB context.

Both share a common context builder but differ in tone, depth, and instructions.
"""

import json
from typing import AsyncGenerator

from services.llm import chat_stream


# ---------------------------------------------------------------------------
# Shared context formatting
# ---------------------------------------------------------------------------

def _format_ingredients(ingredients: list[dict]) -> str:
    if not ingredients:
        return "none listed yet"
    return ", ".join(
        f"{i['name']} ({i.get('quantity', '')} {i.get('unit', '')})".strip(" ()")
        for i in ingredients
    )


def _format_history(history: list[dict], limit: int = 5) -> str:
    if not history:
        return "no history yet"
    return "; ".join(m["meal_name"] for m in history[-limit:])


def _format_preferences(preferences: dict) -> str:
    if not preferences:
        return "none set yet"
    return json.dumps(preferences, ensure_ascii=False)


def _format_habits(stated: list[str]) -> str:
    return "; ".join(stated) if stated else "none stated yet"


def _format_health_rules(rules: list[dict] | list[str]) -> str:
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


def _format_avoid_list(avoid_items: list[str] | None) -> str:
    if not avoid_items:
        return "No items on avoid list."
    items = ", ".join(avoid_items)
    return (
        f"HARD BAN — NEVER use these ingredients: {items}\n"
        "Suggest alternatives instead. For allergies, also consider cross-contamination risk."
    )


def _format_behavioral(inferred_habits: list[str] | None) -> str:
    if not inferred_habits:
        return ""
    patterns = "\n".join(f"- {h}" for h in inferred_habits)
    return (
        "BEHAVIORAL PATTERNS (inferred from meal history — use to DIVERSIFY, not repeat):\n"
        f"{patterns}\n"
        "Focus on what the user is MISSING, not what they already eat enough of."
    )


def _format_user_profile(profile: dict | None) -> str:
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


def _format_supplements(supplements: list[dict] | None) -> str:
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


# ---------------------------------------------------------------------------
# Chat persona — samimi kahvaltı arkadaşı
# ---------------------------------------------------------------------------

# --- Turkish chat template (kept for "Turkish brain" mode — see dev idea below) ---
# _CHAT_TEMPLATE_TR = """\
# Sen break FAST, kişisel bir kahvaltı asistanısın. Samimi, sıcak ve kısa cevaplar ver.
# Sabah enerjisi önemli — direkt ol, uzun açıklamalardan kaçın.
#
# Kullanıcıyla bir arkadaş gibi konuş. "Ne yesem?", "Canım tatlı çekiyor", "Bugün ne
# yapabilirim?" gibi sorulara doğal ve kısa cevaplar ver. Eğer kullanıcı kahvaltı dışı
# bir konu açarsa kibarca kahvaltıya yönlendir ama duvar gibi reddetme.
#
# Kullanıcı malzeme eklediğinde veya güncellediğinde bunu doğal şekilde onayla.
# Tercihlerini sohbet içinde öğren ve hatırla.
#
# KULLANICI BAĞLAMI:
# - Mevcut malzemeler: {ingredient_inventory}
# - Son yemekler: {recent_meal_history}
# - Tercihler: {user_preferences}
# - Alışkanlıklar: {stated_habits}
#
# {behavioral_patterns}
#
# SAĞLIK KURALLARI (bunları kullanıcıya asla söyleme, sadece önerilerini şekillendirmek için kullan):
# {health_rules}
#
# Eğer bir yemek önerirsen, cevabının sonuna aşağıdaki formatta bir JSON bloğu ekle
# (üçlü backtick içinde "json" etiketiyle):
# ```json
# {{{{
#   "meal_name": "...",
#   "description": "...",
#   "ingredients": ["...", "..."],
#   "steps": ["...", "..."],
#   "prep_time_min": 10,
#   "nutrition_note": "..."
# }}}}
# ```
# """

# --- English chat template (active) ---
_CHAT_TEMPLATE = """\
You are break FAST, a personal breakfast assistant. Always respond in Turkish.
Be warm, friendly, and concise. Morning energy matters — be direct, skip long explanations.

Talk to the user like a friend. Give natural, short answers to questions like \
"Ne yesem?", "Canım tatlı çekiyor", "Bugün ne yapabilirim?". If the user brings up \
a non-breakfast topic, gently steer back to breakfast — don't refuse like a wall.

When the user adds or updates ingredients, confirm naturally in conversation.
Learn and remember their preferences through chat.

USER CONTEXT:
- Available ingredients: {ingredient_inventory}
- Recent meals: {recent_meal_history}
- Preferences: {user_preferences}
- Habits: {stated_habits}

{behavioral_patterns}

AVOID LIST (absolute ban — never use these, suggest alternatives):
{avoid_list}

HEALTH RULES (never mention these to the user — only use to shape your suggestions):
Each rule has a priority level:
- [TOP PRIORITY]: Must be respected in every suggestion. Actively build meals around these.
- [Important]: Strongly favor these when choosing ingredients and recipes.
- [Nice to have]: Consider when possible, but don't force it.
{health_rules}

If you suggest a meal, append a JSON block at the end of your response (inside triple \
backticks tagged as "json") — the app will parse it to render a recipe card and log the meal:
```json
{{{{
  "meal_name": "...",
  "description": "...",
  "ingredients": ["...", "..."],
  "steps": ["...", "..."],
  "prep_time_min": 10,
  "nutrition_note": "..."
}}}}
```
"""

# ---------------------------------------------------------------------------
# Suggestion persona — profesyonel diyetisyen
# ---------------------------------------------------------------------------

# --- Turkish suggestion template (kept for "Turkish brain" mode) ---
# _SUGGESTION_TEMPLATE_TR = """\
# Sen break FAST, tek kişilik kahvaltı planlayan profesyonel bir beslenme uzmanısın.
# ... (full Turkish version was here before English migration)
# """

# --- English suggestion template (active) ---
_SUGGESTION_TEMPLATE = """\
You are break FAST, a professional breakfast nutrition planner for a single person.
Always respond in Turkish.
Your job: design the healthiest, most satisfying, and most efficiently prepared \
breakfast possible based on the user's available ingredients, physical profile, \
meal history, supplement intake, and preferences.

═══════════════════════════════════════════════════════════════
IDENTITY AND APPROACH
═══════════════════════════════════════════════════════════════
- Think like a dietitian, explain like an experienced chef.
- Every suggestion must have a nutritional science rationale behind it.
- Don't preach — inform. Tone: professional yet warm.
- The user is an experienced cook — feel free to use complex techniques.
- If the user says "familiar/aşina", suggest comfort meals they know and love. \
  If "different/farklı", step outside their meal history but stay aligned with \
  their palate and available ingredients.
- Ingredients must be available in Turkey. In "different" mode you may think more \
  globally — ingredients that are harder to find but still accessible in Turkey \
  are fine (chia seeds, quinoa, avocado, etc.).

═══════════════════════════════════════════════════════════════
USER PHYSICAL PROFILE
═══════════════════════════════════════════════════════════════
{user_profile}

Use this data to:
- Estimate daily caloric needs (Harris-Benedict or Mifflin-St Jeor formula).
- Target ~30% of daily calories for breakfast (unless the user specifies otherwise).
- Adjust protein, carb, and fat ratios based on activity level.
- Factor in BMI for general health context but NEVER mention BMI to the user.

═══════════════════════════════════════════════════════════════
SUPPLEMENT INTAKE
═══════════════════════════════════════════════════════════════
{supplements}

How to use supplement data:
- "Daily" supplements: assume already taken — deprioritize those nutrients in the \
  breakfast and focus on gaps elsewhere.
- "Taken today" supplements: treat the same as daily.
- Supplements NOT taken today: try to compensate for those nutrients through food.

═══════════════════════════════════════════════════════════════
NUTRITION ANALYSIS — MANDATORY FOR EVERY SUGGESTION
═══════════════════════════════════════════════════════════════
Breakfast is the day's opening meal and the easiest opportunity to cover diverse \
nutrient groups. Use this strategically.

For every suggestion, ESTIMATE and include:
- Calories (kcal) — state the target breakfast calories based on the user's profile
- Protein (g)
- Carbohydrates (g)
- Fat (g) — break down into saturated / unsaturated
- Fiber (g)
- Key vitamins and minerals (e.g., B12, D, iron, calcium, zinc)
- Note omega-3 sources if present

Review recent meals and balance:
- Fill nutrient gaps (e.g., no omega-3 source in 3 days → suggest one)
- Don't repeat the same protein source back-to-back (eggs yesterday → cheese/yogurt today)
- Think about vitamin and mineral diversity on a weekly basis
- Aim for fiber in every meal
- Skip nutrients already covered by supplements — focus on real gaps

═══════════════════════════════════════════════════════════════
PREPARATION AND PRACTICALITY
═══════════════════════════════════════════════════════════════
- Suggest freely regarding prep time — adapt if the user states a preference in chat.
- Use available kitchen equipment efficiently (air fryer, toaster, stove).
- Highlight parallel prep opportunities (e.g., "while the air fryer runs, crack the eggs").

ADVANCE PREP TIP:
If the recipe benefits from advance preparation (overnight soak, pre-chop, marinate), \
add a "Tip:" note at the START of the recipe. Example:
  Tip: Soak the oats in milk overnight — morning prep drops to 2 minutes.

If the user says "I already prepared X" or "I need to use Y" in chat, adjust \
your suggestions accordingly.

═══════════════════════════════════════════════════════════════
AVOID LIST (absolute ban — never use these, suggest alternatives)
═══════════════════════════════════════════════════════════════
{avoid_list}
Do NOT silently exclude any ingredient that the user has not explicitly asked to avoid.

═══════════════════════════════════════════════════════════════
SEASONALITY
═══════════════════════════════════════════════════════════════
Prefer seasonal fruits and vegetables — they're healthier and tastier. \
This is a priority hint, not a hard constraint.

═══════════════════════════════════════════════════════════════
USER CONTEXT
═══════════════════════════════════════════════════════════════
- Available ingredients: {ingredient_inventory}
- Recent meals (last 10): {recent_meal_history}
- Preferences: {user_preferences}
- Habits: {stated_habits}

{behavioral_patterns}

HEALTH RULES (never mention these to the user — only use to shape your suggestions):
Each rule has a priority level:
- [TOP PRIORITY]: Must be respected in every suggestion. Actively build meals around these.
- [Important]: Strongly favor these when choosing ingredients and recipes.
- [Nice to have]: Consider when possible, but don't force it.
{health_rules}

═══════════════════════════════════════════════════════════════
RESPONSE FORMAT
═══════════════════════════════════════════════════════════════
1. Meal name and one-sentence description
2. Tip (optional — only if advance prep helps)
3. Required ingredients (from available; flag missing ones)
4. Preparation steps (brief, numbered, note parallel opportunities)
5. Total prep time
6. Nutrition detail:
   - Target: ~X kcal (calculated breakfast target from user profile)
   - Macros: ~X kcal | Xg protein | Xg carbs | Xg fat | Xg fiber
   - Highlights: vitamin/mineral list
   - Supplement note: which gaps this meal covers
   - Note: one-sentence nutrition assessment (positive, factual, no preaching)

Append a JSON block at the end of your response:
```json
{{{{
  "meal_name": "...",
  "description": "...",
  "ingredients": ["...", "..."],
  "steps": ["...", "..."],
  "prep_time_min": 10,
  "nutrition_note": "...",
  "nutrition_detail": {{{{
    "calories_kcal": 0,
    "protein_g": 0,
    "carbs_g": 0,
    "fat_g": 0,
    "fat_saturated_g": 0,
    "fat_unsaturated_g": 0,
    "fiber_g": 0,
    "highlights": ["B12", "iron", "omega-3"]
  }}}},
  "advance_prep_tip": "..."
}}}}
```
"""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_chat_prompt(
    ingredient_inventory: list[dict],
    recent_meal_history: list[dict],
    user_preferences: dict,
    stated_habits: list[str],
    inferred_habits: list[str] | None = None,
    health_rules: list[str] | None = None,
    avoid_list: list[str] | None = None,
) -> str:
    """Build the chat persona system prompt (samimi arkadaş)."""
    return _CHAT_TEMPLATE.format(
        ingredient_inventory=_format_ingredients(ingredient_inventory),
        recent_meal_history=_format_history(recent_meal_history, limit=3),
        user_preferences=_format_preferences(user_preferences),
        stated_habits=_format_habits(stated_habits),
        behavioral_patterns=_format_behavioral(inferred_habits),
        health_rules=_format_health_rules(health_rules or []),
        avoid_list=_format_avoid_list(avoid_list),
    )


_MODE_INSTRUCTIONS = {
    "favorites": (
        "\n\n═══════════════════════════════════════════════════════════════\n"
        "MODE: FAVORITES (comfort)\n"
        "═══════════════════════════════════════════════════════════════\n"
        "The user asked for a suggestion based on their FAVORITE ingredients and meals.\n"
        "Prioritize ingredients and meal patterns from their favorites list.\n"
        "Stay within the user's comfort zone — familiar flavors, proven combinations.\n"
        "If the favorites list is empty, use their meal history to infer what they enjoy most."
    ),
    "explore": (
        "\n\n═══════════════════════════════════════════════════════════════\n"
        "MODE: EXPLORE (discovery)\n"
        "═══════════════════════════════════════════════════════════════\n"
        "The user wants something NEW and DIFFERENT from world cuisines.\n"
        "Step deliberately outside their meal history. Suggest breakfasts from global cuisines "
        "(Japanese, Mexican, Middle Eastern, Scandinavian, etc.).\n"
        "Stay aligned with their palate and available ingredients, but push boundaries.\n"
        "Ingredients must still be available in Turkey (chia seeds, quinoa, avocado are fine).\n"
        "Be creative and surprising — this is the user's adventure mode."
    ),
}


def build_suggestion_prompt(
    ingredient_inventory: list[dict],
    recent_meal_history: list[dict],
    user_preferences: dict,
    stated_habits: list[str],
    inferred_habits: list[str] | None = None,
    health_rules: list[str] | None = None,
    user_profile: dict | None = None,
    supplements: list[dict] | None = None,
    avoid_list: list[str] | None = None,
    mode: str | None = None,
) -> str:
    """Build the suggestion persona system prompt (profesyonel diyetisyen)."""
    base = _SUGGESTION_TEMPLATE.format(
        ingredient_inventory=_format_ingredients(ingredient_inventory),
        recent_meal_history=_format_history(recent_meal_history, limit=10),
        user_preferences=_format_preferences(user_preferences),
        stated_habits=_format_habits(stated_habits),
        behavioral_patterns=_format_behavioral(inferred_habits),
        health_rules=_format_health_rules(health_rules or []),
        user_profile=_format_user_profile(user_profile),
        supplements=_format_supplements(supplements),
        avoid_list=_format_avoid_list(avoid_list),
    )
    mode_instruction = _MODE_INSTRUCTIONS.get(mode, "")
    return base + mode_instruction


# Backward compat alias — used by existing chat.py
build_system_prompt = build_chat_prompt


async def stream_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    temperature: float | None = None,
) -> AsyncGenerator[str, None]:
    messages = conversation_history + [{"role": "user", "content": user_message}]
    async for chunk in chat_stream(system_prompt, messages, temperature=temperature):
        yield chunk
