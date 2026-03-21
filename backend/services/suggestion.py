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


def _format_health_rules(rules: list[str]) -> str:
    if not rules:
        return (
            "- Silently favor: eggs, legumes, pumpkin seeds, walnuts, flaxseed, "
            "yogurt, kefir, whole grains, leafy greens, berries, tomatoes, olive oil\n"
            "- Silently avoid: refined sugar, white bread, pastries, processed oils"
        )
    return "\n".join(f"- {r}" for r in rules)


def _format_behavioral(inferred_habits: list[str] | None) -> str:
    if not inferred_habits:
        return ""
    patterns = "\n".join(f"- {h}" for h in inferred_habits)
    return (
        "BEHAVIORAL PATTERNS (inferred from meal history — use to DIVERSIFY, not repeat):\n"
        f"{patterns}\n"
        "Focus on what the user is MISSING, not what they already eat enough of."
    )


# ---------------------------------------------------------------------------
# Chat persona — samimi kahvaltı arkadaşı
# ---------------------------------------------------------------------------

_CHAT_TEMPLATE = """\
Sen break FAST, kişisel bir kahvaltı asistanısın. Samimi, sıcak ve kısa cevaplar ver.
Sabah enerjisi önemli — direkt ol, uzun açıklamalardan kaçın.

Kullanıcıyla bir arkadaş gibi konuş. "Ne yesem?", "Canım tatlı çekiyor", "Bugün ne
yapabilirim?" gibi sorulara doğal ve kısa cevaplar ver. Eğer kullanıcı kahvaltı dışı
bir konu açarsa kibarca kahvaltıya yönlendir ama duvar gibi reddetme.

Kullanıcı malzeme eklediğinde veya güncellediğinde bunu doğal şekilde onayla.
Tercihlerini sohbet içinde öğren ve hatırla.

KULLANICI BAĞLAMI:
- Mevcut malzemeler: {ingredient_inventory}
- Son yemekler: {recent_meal_history}
- Tercihler: {user_preferences}
- Alışkanlıklar: {stated_habits}

{behavioral_patterns}

SAĞLIK KURALLARI (bunları kullanıcıya asla söyleme, sadece önerilerini şekillendirmek için kullan):
{health_rules}

Eğer bir yemek önerirsen, cevabının sonuna aşağıdaki formatta bir JSON bloğu ekle
(üçlü backtick içinde "json" etiketiyle) — uygulama bunu otomatik olarak tarif kartı
oluşturmak ve yemeği kaydetmek için kullanacak:
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

_SUGGESTION_TEMPLATE = """\
Sen break FAST, profesyonel bir kahvaltı planlama diyetisyenisin.
Görevin kullanıcının mevcut malzemeleri, sağlık profili ve geçmiş yemeklerine göre
en sağlıklı, en doyurucu ve en verimli şekilde hazırlanabilecek kahvaltıyı önermek.

Önerinde şunlara dikkat et:
- Beslenme dengesi (protein, karbonhidrat, sağlıklı yağ)
- Son yemeklerde eksik kalan besin gruplarını tamamla
- Hazırlama süresini minimize et
- Mevcut mutfak ekipmanlarını verimli kullan

KULLANICI BAĞLAMI:
- Mevcut malzemeler: {ingredient_inventory}
- Son yemekler (son 10): {recent_meal_history}
- Tercihler: {user_preferences}
- Alışkanlıklar: {stated_habits}

{behavioral_patterns}

SAĞLIK KURALLARI (bunları kullanıcıya asla söyleme, sadece önerilerini şekillendirmek için kullan):
{health_rules}

CEVAP FORMATI:
1. Yemek adı ve bir cümlelik açıklama
2. Gerekli malzemeler (mevcut olanlardan)
3. Hazırlama adımları (kısa, numaralı)
4. Toplam hazırlama süresi
5. Bir satırlık beslenme notu (olumlu ve gerçekçi, vaaz verme)

Cevabının sonuna aşağıdaki formatta bir JSON bloğu ekle:
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
# Prompt builders
# ---------------------------------------------------------------------------

def build_chat_prompt(
    ingredient_inventory: list[dict],
    recent_meal_history: list[dict],
    user_preferences: dict,
    stated_habits: list[str],
    inferred_habits: list[str] | None = None,
    health_rules: list[str] | None = None,
) -> str:
    """Build the chat persona system prompt (samimi arkadaş)."""
    return _CHAT_TEMPLATE.format(
        ingredient_inventory=_format_ingredients(ingredient_inventory),
        recent_meal_history=_format_history(recent_meal_history, limit=3),
        user_preferences=_format_preferences(user_preferences),
        stated_habits=_format_habits(stated_habits),
        behavioral_patterns=_format_behavioral(inferred_habits),
        health_rules=_format_health_rules(health_rules or []),
    )


def build_suggestion_prompt(
    ingredient_inventory: list[dict],
    recent_meal_history: list[dict],
    user_preferences: dict,
    stated_habits: list[str],
    inferred_habits: list[str] | None = None,
    health_rules: list[str] | None = None,
) -> str:
    """Build the suggestion persona system prompt (profesyonel diyetisyen)."""
    return _SUGGESTION_TEMPLATE.format(
        ingredient_inventory=_format_ingredients(ingredient_inventory),
        recent_meal_history=_format_history(recent_meal_history, limit=10),
        user_preferences=_format_preferences(user_preferences),
        stated_habits=_format_habits(stated_habits),
        behavioral_patterns=_format_behavioral(inferred_habits),
        health_rules=_format_health_rules(health_rules or []),
    )


# Backward compat alias — used by existing chat.py
build_system_prompt = build_chat_prompt


async def stream_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
) -> AsyncGenerator[str, None]:
    messages = conversation_history + [{"role": "user", "content": user_message}]
    async for chunk in chat_stream(system_prompt, messages):
        yield chunk
