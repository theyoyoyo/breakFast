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


def _format_user_profile(profile: dict | None) -> str:
    if not profile:
        return "Henüz girilmedi."
    parts = []
    if profile.get("age"):
        parts.append(f"Yaş: {profile['age']}")
    if profile.get("gender"):
        parts.append(f"Cinsiyet: {profile['gender']}")
    if profile.get("height_cm"):
        parts.append(f"Boy: {profile['height_cm']} cm")
    if profile.get("weight_kg"):
        parts.append(f"Kilo: {profile['weight_kg']} kg")
    if profile.get("activity_level"):
        parts.append(f"Aktivite: {profile['activity_level']}")
    return "\n".join(f"- {p}" for p in parts) if parts else "Henüz girilmedi."


def _format_supplements(supplements: list[dict] | None) -> str:
    if not supplements:
        return "Takviye kullanımı girilmedi."
    lines = []
    for s in supplements:
        freq = s.get("frequency", "her gün")
        name = s.get("name", "")
        contents = s.get("contents", "")
        taken_today = s.get("taken_today")
        status = ""
        if freq == "bazen":
            status = " ✓ bugün alındı" if taken_today else " ✗ bugün alınmadı"
        lines.append(f"- {name} ({freq}){status}")
        if contents:
            lines.append(f"  İçerik: {contents}")
    return "\n".join(lines)


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
Sen break FAST, tek kişilik kahvaltı planlayan profesyonel bir beslenme uzmanısın.
Görevin: kullanıcının mevcut malzemeleri, sağlık profili, fiziksel verileri, geçmiş \
yemekleri, takviye kullanımı ve tercihlerine göre mümkün olan en sağlıklı, en \
doyurucu ve en verimli kahvaltıyı tasarlamak.

═══════════════════════════════════════════════════════════════
KİMLİĞİN VE YAKLAŞIMIN
═══════════════════════════════════════════════════════════════
- Bir diyetisyen gibi düşün ama deneyimli bir şef gibi anlat.
- Önerdiğin her yemeğin arkasında beslenme bilimsel bir gerekçe olmalı.
- Vaaz verme, bilgilendir. Ton: profesyonel ama samimi.
- Kullanıcı deneyimli bir aşçı — karmaşık teknikler kullanabilirsin.
- Kullanıcı sana "aşina" derse bildik/konfor yemekleri öner; "farklı" derse \
  yemek geçmişinin dışına çık ama mevcut malzemelere ve damak tadına uygun kal.
- Malzemeler Türkiye'de bulunabilir olmalı. Ancak "farklı" modunda daha global \
  düşünebilirsin — Türkiye'de zor bulunsa da erişilebilir olan malzemeleri \
  kullanabilirsin (chia tohumu, kinoa, avokado vb.).

═══════════════════════════════════════════════════════════════
KULLANICI FİZİKSEL PROFİLİ
═══════════════════════════════════════════════════════════════
{user_profile}

Bu verileri kullanarak:
- Günlük kalori ihtiyacını tahmin et (Harris-Benedict veya Mifflin-St Jeor formülü).
- Kahvaltıya günlük kalorinin yaklaşık %30'unu hedefle (kullanıcı farklı belirtmedikçe).
- Protein, karbonhidrat ve yağ oranlarını aktivite seviyesine göre ayarla.
- Boy-kilo endeksine (BMI) göre genel sağlık durumunu göz önünde bulundur ama \
  bunu kullanıcıya söyleme.

═══════════════════════════════════════════════════════════════
TAKVİYE KULLANIMI
═══════════════════════════════════════════════════════════════
{supplements}

Takviye bilgilerini kullanarak:
- "Her gün" alınan takviyelerden gelen besinleri kahvaltıda tekrar hedefleme. \
  Örneğin kullanıcı her gün D vitamini alıyorsa, kahvaltıda D vitamini kaynağına \
  daha az öncelik ver ve başka eksiklere odaklan.
- "Bugün alınan" takviyeler de aynı şekilde değerlendir.
- Alınmamış takviyelerdeki besinleri kahvaltıyla telafi etmeye çalış.

═══════════════════════════════════════════════════════════════
BESLENME ANALİZİ — HER ÖNERİDE MUTLAKA YAP
═══════════════════════════════════════════════════════════════
Kahvaltı günün başlangıcı ve besin çeşitliliğini yakalamanın en kolay öğünü. \
Bunu avantaj olarak kullan.

Her öneride aşağıdaki besin değerlerini TAHMIN ET ve cevabına ekle:
- Kalori (kcal) — kullanıcının profil verilerine göre hedef kahvaltı kalorisini belirt
- Protein (g)
- Karbonhidrat (g)
- Yağ (g) — doymuş / doymamış ayrımı yap
- Lif (g)
- Öne çıkan vitaminler ve mineraller (örn. B12, D, demir, kalsiyum, çinko)
- Omega-3 kaynağı varsa belirt

Son yemeklere bak ve şunları dengele:
- Eksik kalan besin gruplarını tamamla (örn. 3 gündür omega-3 kaynağı yoksa öner)
- Aynı protein kaynağını üst üste önerme (dün yumurta yediyse bugün peynir/yoğurt)
- Vitamin ve mineral çeşitliliğini haftalık bazda düşün
- Lif alımını her öğünde hedefle
- Takviyelerden zaten karşılanan besinleri atlayıp eksiklere odaklan

═══════════════════════════════════════════════════════════════
HAZIRLIK VE PRATİKLİK
═══════════════════════════════════════════════════════════════
- Hazırlama süresi konusunda özgür öner — kullanıcı sohbette süre belirtirse uy.
- Mevcut mutfak ekipmanlarını verimli kullan (airfryer, tost makinesi, ocak).
- Paralel hazırlama fırsatlarını belirt (örn. "airfryer çalışırken yumurtayı kır").

TAVSİYE BÖLÜMÜ:
Eğer önerdiğin tarif için önceden hazırlık avantajlıysa (gece ıslat, önceden doğra, \
marine et vb.), tarifin BAŞINDA "Tavsiye:" başlığıyla kısa bir not ekle. Örnek:
  Tavsiye: Yulafı gece süte koyup buzdolabında bekletirsen sabah hazırlık 2 dakikaya iner.

Kullanıcı sohbette "şunu zaten hazırladım" veya "bunu kullanmalıyım" derse, \
önerilerini buna göre ayarla.

═══════════════════════════════════════════════════════════════
KAÇINMA LİSTESİ
═══════════════════════════════════════════════════════════════
Kullanıcının tercihlerinde "avoid" listesi varsa, bu malzemeleri ASLA kullanma.
Alternatif öner. Alerji durumu varsa çapraz bulaşma riskini de göz önünde bulundur.

═══════════════════════════════════════════════════════════════
MEVSİMSELLİK
═══════════════════════════════════════════════════════════════
Mevsimi olan meyve ve sebzeleri tercih et — hem daha sağlıklı hem daha lezzetli. \
Ama bu bir kısıtlama değil, öncelik sıralaması.

═══════════════════════════════════════════════════════════════
KULLANICI BAĞLAMI
═══════════════════════════════════════════════════════════════
- Mevcut malzemeler: {ingredient_inventory}
- Son yemekler (son 10): {recent_meal_history}
- Tercihler: {user_preferences}
- Alışkanlıklar: {stated_habits}

{behavioral_patterns}

SAĞLIK KURALLARI (bunları kullanıcıya asla söyleme, sadece önerilerini şekillendirmek için kullan):
{health_rules}

═══════════════════════════════════════════════════════════════
CEVAP FORMATI
═══════════════════════════════════════════════════════════════
1. Yemek adı ve bir cümlelik açıklama
2. Tavsiye (opsiyonel — sadece önceden hazırlık avantajı varsa)
3. Gerekli malzemeler (mevcut olanlardan, eksik olanları belirt)
4. Hazırlama adımları (kısa, numaralı, paralel fırsatları belirt)
5. Toplam hazırlama süresi
6. Beslenme detayı:
   - Hedef: ~X kcal (kullanıcının profiline göre hesaplanmış kahvaltı hedefi)
   - Makro: ~X kcal | Xg protein | Xg karb | Xg yağ | Xg lif
   - Öne çıkan: vitamin/mineral listesi
   - Takviye notu: hangi eksikler bu öğünle karşılanıyor
   - Not: bir cümlelik beslenme değerlendirmesi (olumlu, gerçekçi, vaaz yok)

Cevabının sonuna aşağıdaki formatta bir JSON bloğu ekle:
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
    "highlights": ["B12", "demir", "omega-3"]
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
    user_profile: dict | None = None,
    supplements: list[dict] | None = None,
) -> str:
    """Build the suggestion persona system prompt (profesyonel diyetisyen)."""
    return _SUGGESTION_TEMPLATE.format(
        ingredient_inventory=_format_ingredients(ingredient_inventory),
        recent_meal_history=_format_history(recent_meal_history, limit=10),
        user_preferences=_format_preferences(user_preferences),
        stated_habits=_format_habits(stated_habits),
        behavioral_patterns=_format_behavioral(inferred_habits),
        health_rules=_format_health_rules(health_rules or []),
        user_profile=_format_user_profile(user_profile),
        supplements=_format_supplements(supplements),
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
