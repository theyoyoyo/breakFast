"""
3-step suggestion pipeline: draft → revise → present.

Orchestrates the Suggestion and Pipeline Analyst personas to produce
a higher-quality meal suggestion. The user sees progress updates while
waiting, then the final meal.

Steps:
1. Suggestion persona drafts a menu through structured outputs (draft_schema): its own
   words, then the meal in the reviser's shape. An empty menu means the fridge is too
   small: its words are sent as the note, or code's low-ingredients text
   (LOW_INGREDIENT_TEXTS) when it wrote none. A reply that can't be read gets the retry
   text (RETRY_TEXTS), and so does a press whose pipeline fails (routers/chat.py).
   Neither shows a meal card.
2. Plain code checks the draft's meal (fridge, units, avoid list), and the
   Pipeline Analyst returns the fixed meal itself through structured outputs
   (revision_schema): what the chat asks for (after a chat), its changes, then
   the meal. If code finds more problems in the revised meal than in the
   draft, or can't read it, the draft's meal is used: avoid-list hits first,
   then fridge misses and units.
3. Suggestion persona writes the short reply text from the final meal alone,
   so the text never promises what the menu doesn't have. If that call fails,
   code writes the text from the menu name and description.
The reply keeps its shape: the text, then the meal in a ```json block.

After a chat, the draft and the reviser both get the chat block
(services/chat_block.py), placed last in their message, so both follow what
the user typed.
"""

import json
import logging
import re
from typing import AsyncGenerator

from models.meal import with_emoji
from models.units import units_for, unknown_units
from services.fridge import find_avoided, find_missing_ingredients, in_fridge, meal_ingredient_names, same_name
from services.llm import chat_json, stream_response
from services.personas import build_pipeline_analyst_prompt, build_present_prompt, build_suggestion_prompt

# The reviser applies its changes and checks the result, so it runs cool like the old analyst
REVISE_TEMPERATURE = 0.3

# A fenced block in the present step's text; the reply's only ```json block is the meal
_FENCED_RE = re.compile(r"```[\s\S]*?(```|$)")


# What the user reads when the draft's reply can't be read at all (rare with its schema): no meal
# card, and their next press is the retry. The UI is English only, so the button keeps its name.
RETRY_TEXTS = {
    "en": "I couldn't put a menu together this time. Please press Suggest again.",
    "tr": "Bu sefer bir menü hazırlayamadım. Lütfen Suggest düğmesine tekrar basın.",
}
LOW_INGREDIENT_TEXTS = {
    "en": "There aren't enough ingredients for a breakfast yet. Add some in the Fridge tab, or press Suggest Shopping for ideas.",
    "tr": "Kahvaltı için henüz yeterli malzeme yok. Fridge sekmesinden malzeme ekleyin ya da fikir için Suggest Shopping düğmesine basın.",
}


def in_language(texts: dict, language: str) -> str:
    """One of the code-written texts above in the reply language, English by default."""
    return texts.get(language, texts["en"])


def _meal_schema(language: str, method: bool = True, names: list[str] | None = None, missing: list[str] = ()) -> dict:
    """The meal the draft and the reviser both return, one shape so the two stay the same. Each
    menu item lists its ingredients before its name, so a dish's name is written after what goes
    in, and every item has a numeric amount in the app's units (a dish's servings, which code
    drops; a simple item's portion). One item shape for both: offered a choice of shapes, the 7B
    model dropped a dish's ingredients. The draft's items have no `method`: the reviser writes it,
    and a method rule in the draft scored worse.

    For the reviser, `names` limits a dish ingredient's name to these (reviser_names), and
    `missing`, the draft's items the fridge lacks, are what an optional `replaces` may name. Item
    names stay free, since a dish may need a new name after a swap."""
    units = units_for(language)
    ingredient = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "enum": names} if names else {"type": "string"},
            "amount": {"type": "number"},
            "unit": {"type": "string", "enum": units},
            "prep": {"type": "string"},
        },
        "required": ["name", "amount", "unit"],
    }
    if missing:
        ingredient["properties"]["replaces"] = {"type": "string", "enum": list(missing)}
    fields = {"ingredients": {"type": "array", "items": ingredient}, "name": {"type": "string"}}
    if method:
        fields["method"] = {"type": "string"}
    fields |= {"amount": {"type": "number"}, "unit": {"type": "string", "enum": units}}
    item = {"type": "object", "properties": fields, "required": list(fields)}
    return {
        "type": "object",
        "properties": {
            "menu": {"type": "array", "items": item},
            "menu_name": {"type": "string"},
            "description": {"type": "string"},
            "prep_time_min": {"type": "integer"},
        },
        "required": ["menu", "menu_name", "description", "prep_time_min"],
    }


def draft_schema(language: str) -> dict:
    """The draft's reply: its own words first, so the model plans the menu in words before it fills
    in the meal, then the meal. An empty menu means the fridge is too small for a breakfast, and the
    text is then the note the user reads."""
    properties = {"text": {"type": "string"}, "meal": _meal_schema(language, method=False)}
    return {"type": "object", "properties": properties, "required": list(properties)}


def revision_schema(language: str, chat: bool = False, names: list[str] | None = None, missing: list[str] = ()) -> dict:
    """The reviser's reply: its changes first, then the meal (the draft's shape, with methods, its
    ingredient names limited to `names` and an optional `replaces` naming one of `missing`).
    After a chat it starts with `chat_asks`, what the chat asks for now, so it holds the meal
    against each ask. Each ask lists the chat entries it comes from before its words, so a later
    message is read together with the earlier one it changes (one general shape, no field per kind
    of request)."""
    ask = {
        "type": "object",
        "properties": {"from": {"type": "array", "items": {"type": "integer"}}, "ask": {"type": "string"}},
        "required": ["from", "ask"],
    }
    properties = {"chat_asks": {"type": "array", "items": ask}} if chat else {}
    properties |= {
        "changes": {"type": "array", "items": {"type": "string"}},
        "meal": _meal_schema(language, names=names, missing=missing),
    }
    return {"type": "object", "properties": properties, "required": list(properties)}


# Recipes may list water, a utility the fridge doesn't hold, so the reviser may name it too
_WATER = {"en": "Water", "tr": "Su"}


def reviser_names(draft_meal: dict, inventory: list[dict], language: str = "en") -> list[str]:
    """The names the reviser may give a dish's ingredients: the fridge's, so a swap brings in only
    what the user has, then the draft's own, so a missing item it keeps keeps its name, and water.
    One spelling per name (same_name), the fridge's first."""
    names = []
    for name in [i["name"] for i in inventory if i.get("name")] + meal_ingredient_names(draft_meal) + [_WATER.get(language, "Water")]:
        if name and not any(same_name(name, n) for n in names):
            names.append(name)
    return names


def _check_swaps(meal: dict, missing: list[str], inventory: list[dict]) -> dict:
    """Keep a dish ingredient's `replaces` only when it's true (#148): the item it names was missing
    in the draft, the ingredient itself is in the fridge, and the item it names is gone from that
    dish. A simple item isn't a recipe, so it carries none."""
    for item in meal["menu"]:
        if not isinstance(item, dict):
            continue
        item.pop("replaces", None)
        dish = [str(i.get("name", "")) for i in item.get("ingredients") or [] if isinstance(i, dict)]
        for ingredient in item.get("ingredients") or []:
            if not isinstance(ingredient, dict):
                continue
            old = str(ingredient.pop("replaces", "") or "").strip()
            if (
                old and any(same_name(old, m) for m in missing)
                and in_fridge(str(ingredient.get("name", "")), inventory)
                and not any(same_name(old, n) for n in dish)
            ):
                ingredient["replaces"] = old
    return meal


def _readable_meal(meal) -> dict | None:
    return meal if isinstance(meal, dict) and isinstance(meal.get("menu"), list) and meal["menu"] else None


def _meal_problems(meal: dict | None, context: dict) -> tuple[float, float]:
    """Code-checked problems in a meal, compared in order: avoid-list hits (a hard ban,
    so one outweighs any number of the rest), then fridge misses and units the app can't show.
    No meal counts as the worst."""
    if meal is None:
        return float("inf"), float("inf")
    avoided = find_avoided(meal, context["avoid_list"])
    missing = find_missing_ingredients(meal, context["ingredients"])
    return len(avoided), len(missing) + len(unknown_units(meal, context.get("language", "en")))


def _code_check(meal: dict, context: dict) -> list[str]:
    """What code found in the draft's meal, one line per kind, for the reviser to fix."""
    checks = [
        ("Not in the fridge", find_missing_ingredients(meal, context["ingredients"])),
        ("On the avoid list", find_avoided(meal, context["avoid_list"])),
        ("Units the app can't show", unknown_units(meal, context.get("language", "en"))),
    ]
    return [f"{label}: {', '.join(names)}" for label, names in checks if names]


def _clean_meal(meal: dict) -> dict:
    """The reviser's meal in the app's format: a dish has no amount or unit of its own, and empty
    prep words or methods are left out. A "dish" that is one item named as itself (Banana: Banana)
    is that item on its own, so it becomes a simple item and keeps its method: how it's readied,
    none when it's served as it is (#156)."""
    for item in meal["menu"]:
        if not isinstance(item, dict):
            continue
        sub = item.get("ingredients") or []
        if len(sub) == 1 and isinstance(sub[0], dict) and same_name(str(sub[0].get("name", "")), str(item.get("name", ""))):
            item.update(amount=sub[0].get("amount"), unit=sub[0].get("unit"), ingredients=[])
        if item.get("ingredients"):
            item.pop("amount", None)
            item.pop("unit", None)
        else:
            item["ingredients"] = []
        if not str(item.get("method") or "").strip():
            item.pop("method", None)
        for ingredient in item["ingredients"]:
            for key in ("prep", "replaces"):
                if isinstance(ingredient, dict) and not str(ingredient.get(key) or "").strip():
                    ingredient.pop(key, None)
    return meal


def _lines(value) -> list[str]:
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


def _asks(value) -> list[str]:
    """The reviser's chat asks as review lines, each with the chat entries it cites ("No eggs (from #2)")."""
    lines = []
    for item in value if isinstance(value, list) else []:
        ask = str(item.get("ask") or "").strip() if isinstance(item, dict) else str(item).strip()
        if not ask:
            continue
        cited = item.get("from") if isinstance(item, dict) else None
        cited = [f"#{n}" for n in cited if isinstance(n, int)] if isinstance(cited, list) else []
        lines.append(f"{ask} (from {', '.join(cited)})" if cited else ask)
    return lines


def _parse_revision(reply: str) -> tuple[list[str], list[str], dict | None]:
    """What the reviser read in the chat, its changes and its meal (None when the meal can't be read)."""
    try:
        data = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return [], [], None
    if not isinstance(data, dict):
        return [], [], None
    meal = _readable_meal(data.get("meal"))
    return _asks(data.get("chat_asks")), _lines(data.get("changes")), _clean_meal(meal) if meal else None


def _parse_draft(reply: str) -> tuple[str, dict | None] | None:
    """The draft's text and its meal in the app's format, the meal None for an empty menu (the fridge
    is too small, and the text, maybe empty, is the note). None when the reply can't be read."""
    try:
        data = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    text, meal = str(data.get("text") or "").strip(), data.get("meal")
    menu = meal.get("menu") if isinstance(meal, dict) else None
    if not isinstance(menu, list):
        return None
    return text, _clean_meal(meal) if menu else None


def _meal_reply(text: str, meal: dict) -> str:
    """A reply in the app's shape: the text, then the meal in a ```json block."""
    return f"{text}\n\n```json\n{json.dumps(meal, ensure_ascii=False, indent=2)}\n```"


def _with_chat(message: str, chat_block: str | None) -> str:
    """A step's message with the chat block placed last, where the model reads it freshest."""
    return f"{message}\n\n{chat_block}" if chat_block else message


def _revision_message(draft_meal: dict, problems: list[str]) -> str:
    check = "\n".join(f"- {p}" for p in problems) if problems else "- Nothing found."
    return f"Draft menu:\n```json\n{json.dumps(draft_meal, ensure_ascii=False, indent=2)}\n```\n\nCode check:\n{check}"


def _code_text(meal: dict) -> str:
    """The reply text when the present step fails: the menu name and description."""
    name, description = str(meal.get("menu_name") or "").strip(), str(meal.get("description") or "").strip()
    return "\n\n".join(part for part in (f"**{name}**" if name else "", description) if part)


async def revise(
    context: dict, draft_meal: dict, mode: str | None = None, chat_block: str | None = None,
) -> tuple[list[str], list[str], list[str], dict | None]:
    """Step 2 on its own, so the prompt test can send the reviser a fixed draft: code checks the
    draft's meal, and the reviser returns the fixed meal through revision_schema, its ingredient
    names limited to the fridge's and the draft's own (reviser_names). Code keeps an ingredient's
    `replaces` only when it's true (_check_swaps). Returns the code check's lines, what the reviser
    read in the chat, its changes and its meal (None when the meal can't be read or the call fails)."""
    language = context.get("language", "en")
    reviser_prompt = build_pipeline_analyst_prompt(
        recent_meal_history=context["history"],
        user_profile=context["user_profile"],
        supplements=context["supplements"],
        health_rules=context["health_rules"],
        ingredient_inventory=context["ingredients"],
        avoid_list=context["avoid_list"],
        preferences=context["preferences"],
        mode=mode,
        language=language,
        chat=bool(chat_block),
    )
    problems = _code_check(draft_meal, context)
    missing = find_missing_ingredients(draft_meal, context["ingredients"])
    schema = revision_schema(
        language, chat=bool(chat_block), names=reviser_names(draft_meal, context["ingredients"], language), missing=missing,
    )
    asks, changes, revised_meal = [], [], None
    try:
        reply = await chat_json(
            system_prompt=reviser_prompt,
            messages=[{"role": "user", "content": _with_chat(_revision_message(draft_meal, problems), chat_block)}],
            schema=schema,
            temperature=REVISE_TEMPERATURE,
            task="review",
            language=language,
        )
        asks, changes, revised_meal = _parse_revision(reply)
        if revised_meal is None:
            logging.warning("Suggestion reviser: could not read the meal in %r", reply)
    except Exception:
        logging.exception("Suggestion reviser failed; the draft's meal is used")
    if revised_meal is not None:
        _check_swaps(revised_meal, missing, context["ingredients"])
    return problems, asks, changes, revised_meal


async def run_suggestion_pipeline(
    context: dict,
    user_message: str,
    mode: str | None = None,
    temperature: float | None = None,
    chat_block: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Run the 3-step suggestion pipeline, yielding events for the WebSocket handler.

    Yields dicts with:
      {"type": "progress", "step": "drafting"|"analyzing"|"finalizing"}
      {"type": "draft", "content": "..."}   — the full draft (for the prompt test; chat ignores it)
      {"type": "review", "content": "..."}  — the code check and the reviser's changes (same)
      {"type": "token", "content": "..."}   — the final text, sent once the meal is chosen
      {"type": "done", "content": "..."}    — full final response

    context: the full context dict from _load_context() in chat.py
    chat_block: the session's chat (services/chat_block.py), or None before any chat
    """

    # --- Build prompts ---
    language = context.get("language", "en")

    suggestion_prompt = build_suggestion_prompt(
        ingredient_inventory=context["ingredients"],
        recent_meal_history=context["history"],
        user_preferences=context["preferences"],
        stated_habits=context["stated_habits"],
        inferred_habits=context["inferred_habits"],
        health_rules=context["health_rules"],
        user_profile=context["user_profile"],
        supplements=context["supplements"],
        avoid_list=context["avoid_list"],
        mode=mode,
        kitchen_appliances=context.get("kitchen_appliances"),
        weekly_summary=context.get("weekly_summary"),
        language=language,
        country=context.get("country"),
        favorite_meals=context.get("favorite_meals"),
        favorites=context.get("favorites"),
        ratings=context.get("ratings"),
    )

    # --- Step 1: Draft ---
    yield {"type": "progress", "step": "drafting"}

    reply = await chat_json(
        system_prompt=suggestion_prompt,
        messages=[{"role": "user", "content": _with_chat(user_message, chat_block)}],
        schema=draft_schema(language),
        temperature=temperature,
        task="suggestion",
        language=language,
    )
    draft = _parse_draft(reply)
    if draft is None:
        logging.warning("Suggestion draft: could not read %r", reply)
    draft_text, draft_meal = draft or (reply, None)
    yield {"type": "draft", "content": _meal_reply(draft_text, draft_meal) if draft_meal else draft_text}

    # No menu: when the fridge is too small, the draft's note, or code's low-ingredients text if it
    # wrote none; the retry text when its reply can't be read. It is sent as text without a review,
    # so the chat shows no meal card.
    if draft_meal is None:
        if draft:
            note = draft_text or in_language(LOW_INGREDIENT_TEXTS, language)
        else:
            note = in_language(RETRY_TEXTS, language)
        yield {"type": "progress", "step": "analyzing"}
        yield {"type": "review", "content": "- No meal in the draft, so nothing to revise." if draft else "- The draft couldn't be read."}
        yield {"type": "progress", "step": "finalizing"}
        yield {"type": "token", "content": note}
        yield {"type": "done", "content": note}
        return

    # --- Step 2: Revise ---
    yield {"type": "progress", "step": "analyzing"}

    problems, asks, changes, revised_meal = await revise(context, draft_meal, mode, chat_block)
    review = (
        [f"- CHAT ASKS: {a}" for a in asks]
        + [f"- CODE CHECK: {p}" for p in problems]
        + [f"- {c}" for c in changes]
    )
    yield {"type": "review", "content": "\n".join(review) or "- No changes."}

    # The review may only improve the meal: when code finds more problems after it, keep the draft's
    if _meal_problems(revised_meal, context) <= _meal_problems(draft_meal, context):
        meal = revised_meal
    else:
        meal = draft_meal

    # --- Step 3: Present ---
    yield {"type": "progress", "step": "finalizing"}

    text = ""
    try:
        chunks = []
        present_message = f"Today's menu:\n```json\n{json.dumps(meal, ensure_ascii=False, indent=2)}\n```"
        async for chunk in stream_response(
            build_present_prompt(language), [], present_message, temperature=temperature, task="suggestion", language=language,
        ):
            chunks.append(chunk)
        text = _FENCED_RE.sub("", "".join(chunks)).strip()
    except Exception:
        logging.exception("Suggestion present step failed; code writes the text")
    # The card's icon is picked once here, so every device and reload shows the same one (#244)
    meal = with_emoji(meal)
    final_text = _meal_reply(text or _code_text(meal), meal)

    yield {"type": "token", "content": final_text}
    yield {"type": "done", "content": final_text}
