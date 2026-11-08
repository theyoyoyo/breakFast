"""
Prompt test — runs the real prompts against an Ollama server and scores every reply
in code, so a prompt change gets a before and after number (#116).

Run from backend/, with the server's Ollama reachable (docs/SETUPALL.md, BONUS C):
    python -m tools.prompt_check --url http://100.x.x.x:11434 --note "what changed"
    python -m tools.prompt_check --samples en,tr --runs 3 --draft
    python -m tools.prompt_check --persona shopping --samples mixed,demo
    python -m tools.prompt_check --samples all --note "baseline"
    python -m tools.prompt_check --persona plan
    python -m tools.prompt_check --persona review
    python -m tools.prompt_check --samples en,picky --scenario all
    python -m tools.prompt_check --persona chat --samples en,picky --scenario all
    python -m tools.prompt_check --history

Personas, each run for a sample user (tools/prompt_samples.py):
- suggest (default): one Suggest press through the real draft → review → refine
  pipeline, in the mode the sample's user usually presses unless --mode is given.
  The draft and the final reply are both scored; --draft stops after the draft (one
  model call instead of three). --scenario says what the press comes after: a fresh
  chat (default), typed messages (chat), or typed messages between earlier presses
  (pressed), sent the way the app sends them. A reply is then also checked against
  what the chat asks: a food left out, the time limit, and a menu the chat already had.
  A sample whose fridge is too small for a breakfast (expects_note) passes with a note
  to the user instead of a menu.
- shopping: Suggest Shopping, then Suggest More, as the Fridge tab sends them, with
  the same prompt, reply schema and code dedupe.
- plan: one Prep Plan press per menu in PLAN_CASES (every menu by default), with the
  planner's real prompt and menu message. It flags food the menu doesn't list, a
  dish cooked another way than its method says (fry vs boil), and a dish that cuts other
  food after heating something (the heated food waits), and notes how many steps each
  dish got, how often the plan the app builds from them switches dishes, and a heating
  step with no appliance from the kitchen (the cook can use one they have).
- review: the reviser alone on each fixed draft in REVIEW_CASES (every case by default), sent
  the way the pipeline's step 2 sends it, in the case user's usual Suggest mode. A draft has
  items the fridge lacks, so the reply shows how the review swaps them (#148): a name it brings
  in that's neither in the fridge nor the draft is flagged (outside), and the note names each
  swap, what stays missing (the review may keep an item nothing replaces), the draft's fridge
  items it dropped and the prep words it wrote (#176).
- chat: the typed messages of a --scenario (chat by default, or pressed) sent to the chat
  persona one at a time, with the chat so far as history. The chat talks and menus come
  only from a Suggest press (#168), so a reply with food amounts, numbered steps or a
  code block is flagged, and each reply notes whether it points to the Suggest button.
Nothing touches the database. Every test is kept locally in tools/runs/ (git-ignored): a log with the
replies and the exact prompts sent, and a line in history.jsonl that later tests are
compared against, so a prompt change can't quietly make things worse.
"""

import argparse
import asyncio
import hashlib
import json
import random
import re
import subprocess
import sys
import time
from collections import Counter
from contextlib import aclosing, contextmanager
from datetime import datetime
from pathlib import Path

from models.units import UNIT_ALIASES, UNIT_PAIRS, unknown_units
from routers.chat import SUGGEST_TEMPERATURES
from routers.scheduler import _build_plan, served_items
from services import llm, pipeline, suggestion
from services.chat_block import SUGGEST_MESSAGES, chat_history, format_chat_block
# The fridge check's own word handling, to tell renamed items from missing ones
from services.fridge import (
    _FOLD, _tokens, _words, find_avoided, find_missing_ingredients, meal_ingredient_names, name_tokens, same_name,
    same_tokens,
)
from services.personas import build_scheduler_prompt, build_scheduler_user_message
from services.personas.chat import build_chat_message
from services.personas.shopping import build_shopping_prompt
from services.shopping import (
    SUGGESTIONS_SCHEMA, dish_names, new_suggestions, parse_suggestions, pick_input, shopping_request,
)
from tools.prompt_samples import CHAT_MESSAGES, PLAN_CASES, REVIEW_CASES, SAMPLE_MODES, SAMPLES, SCENARIOS, chat_scenario
from utils import extract_json_block

BACKEND = Path(__file__).resolve().parent.parent
RUNS_DIR = BACKEND / "tools" / "runs"
HISTORY = RUNS_DIR / "history.jsonl"

# Everything that shapes what the pipeline sends; their content is the prompt id
PROMPT_SOURCES = [
    "services/personas", "services/knowledge.py", "services/pipeline.py",
    "services/fridge.py", "services/shopping.py", "services/chat_block.py", "models/units.py",
    "tools/prompt_samples.py",
]


def chat_rows(chat: list[dict], mode: str | None) -> list[dict]:
    """A scenario's chat as the session saves it: typed messages as they are, and each earlier Suggest
    press as the button's text (in the sample's usual mode) followed by the reply with its meal card."""
    rows = []
    for entry in chat:
        if "press" in entry:
            card = json.dumps(entry["press"], ensure_ascii=False)
            rows += [
                {"role": "user", "content": SUGGEST_MESSAGES[mode]},
                {"role": "assistant", "content": f"A breakfast for you.\n\n```json\n{card}\n```"},
            ]
        else:
            rows.append(entry)
    return rows


# Suggest Shopping's temperature (routers/ingredients.py, get_shopping_suggestions)
SHOPPING_TEMPERATURE = 0.6
# Seeds the share of fridge items and taste hints each press shows, so tests compare
SHOPPING_SEED = 130
# The Prep Plan button's temperature (routers/scheduler.py, get_schedule)
PLAN_TEMPERATURE = 0.3

# The stages each persona's runs score, and the problems its checks look for
PERSONAS = {
    "suggest": {
        "stages": ("draft", "final"),
        "problems": (
            "missing", "renamed", "units", "amounts", "avoided", "named", "turkish", "left_out", "over_time", "repeat",
            "menu",
        ),
    },
    "shopping": {"stages": ("suggest", "more"), "problems": ("dish", "vague", "repeat", "turkish")},
    "plan": {"stages": ("plan",), "problems": ("unlisted", "method", "order", "turkish")},
    "review": {"stages": ("final",), "problems": ("outside", "renamed", "units", "amounts", "avoided", "named", "turkish")},
    "chat": {"stages": CHAT_MESSAGES, "problems": ("food", "amounts", "steps", "block", "turkish")},
}
STAGES = PERSONAS["suggest"]["stages"]
# Bumped when a check changes what counts as clean, so a test is compared only with tests scored the same way
CHECKS = 6
_TURKISH_LETTERS = set("çğıöşüÇĞİÖŞÜ")

# Shopping names that aren't one specific product: alternatives, examples or filler words
_VAGUE = re.compile(r"[(/]|\be\.?g\b|\bor\b|\b(fresh|organic|seasonal|assorted|various)\b", re.IGNORECASE)
# Words that make a name a dish rather than a product (a heuristic for flagging; read the log)
_DISH_WORDS = {
    "menemen", "omelette", "omelet", "toast", "tost", "salad", "sandwich", "porridge", "smoothie",
    "pancake", "pancakes", "soup", "scrambled", "boiled", "fried", "poached", "parfait", "bowl",
}
# Food a plan task may name, as word starts in the reply language (so plurals and Turkish suffixes
# match): a heuristic for flagging food the menu doesn't list, like a copied example; read the log
_FOOD_WORDS = {
    "en": (
        "egg", "tomato", "cucumber", "pepper", "cheese", "bread", "olive", "butter", "oil", "milk", "yogurt",
        "honey", "banana", "oat", "walnut", "almond", "onion", "potato", "sausage", "bacon", "avocado",
        "spinach", "mushroom", "apple", "berr", "salt", "jam", "simit", "sucuk",
    ),
    "tr": (
        "yumurta", "domates", "salatalik", "biber", "peynir", "ekme", "zeytin", "tereyag", "sut", "yogur",
        "bal", "sogan", "patates", "sucu", "mantar", "tuz",
    ),
}
# Steps that heat food and steps that cut it, as word starts in either language (#160). English
# actions lead with their verb ("Toast the bread", "Hard-boil the eggs") and Turkish ones end with it
# ("Ekmeği kızart"), so only that word counts: "Spread it on the toast" isn't toasting, and "Cool the
# boiled eggs" isn't boiling.
_HEATING = (
    "toast", "fry", "frie", "boil", "simmer", "bake", "grill", "roast", "saut", "poach", "scrambl",
    "kizart", "kavur", "hasla", "kaynat", "pisir", "firin", "izgara",
)
_CUTTING = (
    "slice", "chop", "dice", "mash", "peel", "grate", "cut", "halve", "cube", "mince",
    "dilim", "dogra", "rende", "soy", "kes",
)
# Cooking methods code can tell apart, as word starts in either language
_COOKING = {
    "boil": ("boil", "simmer", "poach", "hasla", "kaynat"),
    "fry": ("fry", "frie", "saute", "scrambl", "kizart", "kavur"),
}
# Color and form words that don't name a food on their own, so a "Green smoothie" isn't about "Green peppers"
_NOT_FOOD = {
    "white", "black", "green", "red", "yellow", "brown", "fresh", "dried", "frozen", "whole", "plain", "cooked",
    "raw", "smoked", "sliced", "ground", "sweet", "light", "beyaz", "siyah", "yesil", "kirmizi", "taze",
}
_NUMBER = r"(?<![\w.,])(\d+(?:[.,/]\d+)?|[½¼¾])"
# A number with a unit from the app's list, in either language ("50 g", "2 slices", "1 çay kaşığı")
_UNIT_WORDS = sorted({u.lower() for pair in UNIT_PAIRS for u in pair} | set(UNIT_ALIASES), key=len, reverse=True)
_AMOUNT = re.compile(_NUMBER + r"\s*(" + "|".join(map(re.escape, _UNIT_WORDS)) + r")(?!\w)", re.IGNORECASE)
# A number with up to three words after it, to find counted fridge items ("2 eggs")
_COUNTED = re.compile(_NUMBER + r"\s+(\w+(?:\s+\w+){0,2})")
# A line that starts with a step number or a time ("1. Boil…", "**2)** Slice…", "Step 3", "7:05 Toast…")
_STEP = re.compile(
    r"^[ \t]*(?:[*_#>]+[ \t]*)?(?:\d+[.)]|\d{1,2}:\d\d|(?:step|adım)[ \t]+\d+)[*_]*[ \t:]*\S.*$",
    re.IGNORECASE | re.MULTILINE,
)


# ── Checks ──────────────────────────────────────────────────────────────────

def _contains(hay: list[set[str]], needle: list[set[str]]) -> bool:
    """True when the needle's words appear in a row inside hay."""
    n = len(needle)
    return n > 0 and any(
        all(hay[i + j] & needle[j] for j in range(n)) for i in range(len(hay) - n + 1)
    )


def renamed_items(names: list[str], inventory: list[dict]) -> list[str]:
    """Names the fridge check flags although they contain a fridge item: prepared, combined or
    renamed items ("Simit with tahini dipping sauce", "White cheese (peynir)", "Yogurt or milk").
    Only a label for reading the log: a shorter name ("Cheese" for "White cheese") may be
    another product, so it stays missing."""
    stock = [_tokens(i["name"]) for i in inventory if i.get("name")]
    return [n for n in names if any(_contains(_tokens(n), s) for s in stock)]


def _positive_number(value) -> bool:
    """An amount the app reads as a number above zero: 2, 0.5 and "2" pass, "to taste" and 0 don't."""
    if isinstance(value, bool):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def amount_problems(meal: dict) -> list[str]:
    """Ingredients and simple items without a number amount and a unit, with what's wrong:
    "Salt (to taste)", "Avocado (no unit)". The editor would turn such an amount into 1."""
    found = []
    for item in meal.get("menu") or []:
        if not isinstance(item, dict):
            continue
        for row in [s for s in item.get("ingredients") or [] if isinstance(s, dict)] or [item]:
            amount, unit = row.get("amount"), row.get("unit")
            if amount is None:
                problem = "no amount"
            elif not _positive_number(amount):
                problem = str(amount)
            elif not (isinstance(unit, str) and unit.strip()):
                problem = "no unit"
            else:
                continue
            found.append(f"{row.get('name', '?')} ({problem})")
    return found


def named_dishes(meal: dict, inventory: list[dict]) -> list[str]:
    """Dishes whose name has a word of a fridge item that none of their ingredients has, with those words:
    "Chia porridge (chia)". Words that name no fridge item ("pudding", "cake") are left alone. Only a
    label for reading the log: a word can sit in a fridge name by chance."""
    fridge = {v for i in inventory if i.get("name") for word in _tokens(i["name"]) for v in word}
    found = []
    for item in meal.get("menu") or []:
        subs = [s for s in item.get("ingredients") or [] if isinstance(s, dict)] if isinstance(item, dict) else []
        if not subs:
            continue
        used = {v for s in subs for word in _tokens(str(s.get("name", ""))) for v in word}
        name = str(item.get("name", ""))
        lacking = [
            word for word, variants in zip(_words(name), _tokens(name))
            if variants & fridge and not variants & used and not variants & _NOT_FOOD
        ]
        if lacking:
            found.append(f"{name} ({', '.join(lacking)})")
    return found


def turkish_words(text: str, sample: dict) -> list[str]:
    """Words with Turkish letters in an English reply, other than words of fridge names and the country."""
    if sample["language"] != "en":
        return []
    names = [i["name"] for i in sample["ingredients"]] + [sample.get("country") or ""]
    fridge = {w.lower() for name in names for w in re.findall(r"\w+", name)}
    found = []
    for word in re.findall(r"\w+", text):
        if _TURKISH_LETTERS & set(word) and word.lower() not in fridge and word not in found:
            found.append(word)
    return found


def _no_json(persona: str) -> dict:
    return {"json": False, "dishes": [], "issues": {p: [] for p in PERSONAS[persona]["problems"]}}


def _same_food(a: dict, b: dict) -> bool:
    """Two meals with the same food in any order: items served as they are and dishes' ingredients."""
    left, right = meal_ingredient_names(a), meal_ingredient_names(b)
    if len(left) != len(right):
        return False
    for name in left:
        hit = next((i for i, other in enumerate(right) if same_name(name, other)), None)
        if hit is None:
            return False
        right.pop(hit)
    return True


def chat_problems(meal: dict, scenario: dict | None) -> tuple[dict, str]:
    """What a meal does against what the chat asks, and a note on the foods it must not leave out.
    left_out: a food the chat still leaves out; over_time: a prep time above the chat's limit; repeat:
    an earlier menu of the chat, same food in any order. A liked food or a ban taken back is only noted."""
    if scenario is None:
        return {"left_out": [], "over_time": [], "repeat": []}, ""
    minutes = meal.get("prep_time_min")
    earlier = [e["press"] for e in scenario["chat"] if "press" in e]
    kept = [
        f"{kind} {name}: {'in' if find_avoided(meal, [name]) else 'out'}"
        for kind in ("liked", "allowed") for name in scenario[kind]
    ]
    return {
        "left_out": find_avoided(meal, scenario["leave_out"]),
        "over_time": [f"{minutes} min"] if _positive_number(minutes) and float(minutes) > scenario["max_minutes"] else [],
        "repeat": [m["menu_name"] for m in earlier if _same_food(meal, m)],
    }, ", ".join(kept)


def check_note(text: str, sample: dict) -> dict:
    """Score a reply for a fridge too small for any breakfast (a sample with expects_note): a note to
    the user is clean, and its start is noted; a menu is flagged as one, and the pipeline's retry
    text for a draft it couldn't read is no note. "json" here means the reply has the shape this
    sample asks for."""
    result = _no_json("suggest")
    meal = extract_json_block(text or "")
    menu = meal.get("menu") if isinstance(meal, dict) else None
    if isinstance(menu, list) and menu:
        names = [str(i.get("name", "")).strip() for i in menu if isinstance(i, dict)]
        result |= {"json": True, "dishes": sorted(n.lower() for n in names)}
        result["issues"]["menu"] = names
    elif (text or "").strip() and "```" not in text and text.strip() not in pipeline.RETRY_TEXTS.values():
        result |= {"json": True, "note": "note: " + " ".join(text.split())[:80]}
    result["issues"]["turkish"] = turkish_words(text or "", sample)
    return result


def swap_notes(meal: dict, draft_text: str | None, inventory: list[dict]) -> list[str]:
    """The review's swaps for the log (#148): each dish ingredient marked as standing in for a missing
    item ("replaced Feta for Salmon (Frittata)"), and, given the draft, the draft's missing items that
    are gone from the final with no mark and no rename ("gone, no mark: Quinoa"). Notes only: an item
    the reviser left out is gone too, and code doesn't guess which it was."""
    swaps = [
        (ing.get("name"), ing["replaces"].strip(), item.get("name"))
        for item in meal["menu"] if isinstance(item, dict)
        for ing in item.get("ingredients") or []
        if isinstance(ing, dict) and isinstance(ing.get("replaces"), str) and ing["replaces"].strip()
    ]
    notes = ["replaced " + "; ".join(f"{new} for {old} ({dish})" for new, old, dish in swaps)] if swaps else []
    draft = extract_json_block(draft_text or "")
    if isinstance(draft, dict) and isinstance(draft.get("menu"), list):
        missing = find_missing_ingredients(draft, inventory)
        renamed = renamed_items(missing, inventory)
        kept = meal_ingredient_names(meal) + [old for _, old, _ in swaps]
        gone = [n for n in missing if n not in renamed and not any(same_name(n, k) for k in kept)]
        if gone:
            notes.append("gone, no mark: " + ", ".join(gone))
    return notes


def check_reply(text: str, sample: dict, scenario: dict | None = None, draft: str | None = None) -> dict:
    """Score one suggestion reply: does its meal JSON parse, what's wrong with the meal, and, after
    a chat, what it does against what the chat asks. A note with no menu counts as no meal, except
    for a fridge too small for one (check_note). Given the draft, a final's note names the review's
    swaps (swap_notes)."""
    if sample.get("expects_note"):
        return check_note(text, sample)
    meal = extract_json_block(text or "")
    if not isinstance(meal, dict) or not isinstance(meal.get("menu"), list):
        return _no_json("suggest")
    flagged = find_missing_ingredients(meal, sample["ingredients"])
    renamed = renamed_items(flagged, sample["ingredients"])
    asked, note = chat_problems(meal, scenario)
    result = {
        "json": True,
        # The menu's dish and item names, to count distinct menus across runs
        "dishes": sorted(str(i.get("name", "")).strip().lower() for i in meal["menu"] if isinstance(i, dict)),
        "issues": {
            "missing": [n for n in flagged if n not in renamed],
            "renamed": renamed,
            "units": unknown_units(meal, sample["language"]),
            "amounts": amount_problems(meal),
            "avoided": find_avoided(meal, sample["avoid_list"]),
            "named": named_dishes(meal, sample["ingredients"]),
            "turkish": turkish_words(text, sample),
            **asked,
            "menu": [],
        },
    }
    # Simple items' methods, so filler like "serve as is" shows in the log (#156)
    readied = [
        f"{i.get('name')}: {i['method'].strip()}" for i in meal["menu"]
        if isinstance(i, dict) and not i.get("ingredients") and isinstance(i.get("method"), str) and i["method"].strip()
    ]
    # Dish ingredients' prep words, so a word that doesn't change how the dish is made shows in the log (#176)
    prepped = [
        f"{ing.get('name')}: {ing['prep'].strip()}" for i in meal["menu"] if isinstance(i, dict)
        for ing in i.get("ingredients") or []
        if isinstance(ing, dict) and isinstance(ing.get("prep"), str) and ing["prep"].strip()
    ]
    notes = [
        note,
        "simple items: " + "; ".join(readied) if readied else "",
        "prep: " + "; ".join(prepped) if prepped else "",
        *swap_notes(meal, draft, sample["ingredients"]),
    ]
    if any(notes):
        result["note"] = "; ".join(filter(None, notes))
    return result


def check_review(text: str, case: dict, draft: str) -> dict:
    """Score the reviser's meal for a review case's fixed draft: check_reply's problems, except that a
    missing item is only noted, since the review may keep one nothing replaces, and a missing name the
    draft didn't have is flagged as brought in from outside the fridge (`outside`). A name the case
    lets the review keep as written (`may_keep`: another item that contains a fridge name, #176) is
    still missing rather than renamed. The note names the swaps, what stays missing and the draft's
    fridge items the review dropped."""
    result = check_reply(text, case, draft=draft)
    if not result["json"]:
        return _no_json("review")
    meal, drafted = extract_json_block(text), meal_ingredient_names(case["draft"])
    missing = result["issues"]["missing"]
    result["issues"] = {p: result["issues"].get(p, []) for p in PERSONAS["review"]["problems"]}
    result["issues"]["outside"] = [n for n in missing if not any(same_name(n, d) for d in drafted)]
    allowed = [r for r in result["issues"]["renamed"] if any(same_name(r, k) for k in case.get("may_keep", ()))]
    result["issues"]["renamed"] = [r for r in result["issues"]["renamed"] if r not in allowed]
    final = meal_ingredient_names(meal)
    stocked = [n for n in drafted if n not in find_missing_ingredients(case["draft"], case["ingredients"])]
    dropped = [n for n in stocked if not any(same_name(n, f) for f in final)]
    kept = [m for m in missing if m not in result["issues"]["outside"]] + allowed
    notes = [
        result.get("note", ""),
        "still missing: " + ", ".join(kept) if kept else "",
        "dropped: " + ", ".join(dropped) if dropped else "",
    ]
    result["note"] = "; ".join(n for n in notes if n)
    if not result["note"]:
        result.pop("note")
    return result


def looks_like_dish(name: str, sample: dict) -> bool:
    """One of the sample's own dishes, a name "with" something, or a dish word (a heuristic)."""
    lowered = name.lower()
    return (
        " with " in f" {lowered} "
        or bool(set(re.findall(r"\w+", lowered)) & _DISH_WORDS)
        or any(same_name(name, dish) for dish in _dishes(sample))
    )


def check_shopping(text: str, sample: dict, shown: list[str]) -> tuple[dict, list[str]]:
    """Score one shopping reply and return the names the code dedupe keeps (what the user sees)."""
    items = parse_suggestions(text)
    if items is None:
        return _no_json("shopping"), []
    names = [i["name"] for i in items]
    known = [i["name"] for i in sample["ingredients"]] + sample["shopping_list"] + sample["avoid_list"] + shown
    kept = [i["name"] for i in new_suggestions(items, known, _dishes(sample))]
    return {
        "json": True,
        "dishes": sorted(n.lower() for n in kept),
        "issues": {
            "dish": [n for n in names if looks_like_dish(n, sample)],
            "vague": [n for n in names if _VAGUE.search(n)],
            # In the fridge, on the list, avoided or shown before: the code dedupe drops these
            "repeat": [n for n in names if any(same_name(n, k) for k in known)],
            "turkish": turkish_words(text, sample),
        },
        "note": f"{len(kept)} of {len(names)} kept",
    }, kept


def _dishes(sample: dict) -> list[str]:
    """The sample's own dishes from its logged and favorite meals, which the endpoint drops from suggestions."""
    return dish_names((sample.get("history") or []) + (sample.get("favorite_meals") or []))


def score_shopping(replies: dict, sample: dict) -> dict:
    """Score Suggest Shopping, then Suggest More against what the first one showed."""
    scores, shown = {}, []
    for stage in PERSONAS["shopping"]["stages"]:
        if stage in replies:
            scores[stage], kept = check_shopping(replies[stage], sample, shown)
            shown += kept
    return scores


def _folded(text: str) -> list[str]:
    """The words of a text in lower case, Turkish letters folded ("Yumurtaları" → "yumurtalari")."""
    return [w.translate(_FOLD).lower() for w in re.findall(r"\w+", text)]


def _menu_names(menu: list[dict]) -> list[str]:
    return [n for item in menu for n in [item["name"], *(s["name"] for s in item.get("ingredients") or [])]]


def _plan_dishes(plan: dict) -> list[tuple[str, list[str]]]:
    """Each dish of a plan with its step actions in order: [("Egg sandwich", ["Boil the eggs", …]), …]."""
    return [
        (str(d.get("dish") or ""), [str(s.get("action") or "") if isinstance(s, dict) else str(s) for s in d.get("steps") or []])
        for d in plan["dishes"] if isinstance(d, dict)
    ]


def unlisted_food(tasks: list[str], case: dict) -> list[str]:
    """Food words in the plan that no menu name, method or prep word starts the same way ("Cucumbers"
    when the menu has none)."""
    menu = case["menu"]
    listed = _folded(" ".join(
        [*_menu_names(menu), *(i.get("method") or "" for i in menu),
         *(s.get("prep") or "" for i in menu for s in i.get("ingredients") or [])]
    ))
    found = []
    for word in re.findall(r"\w+", " ".join(tasks)):
        folded = _folded(word)[0]
        roots = [r for r in _FOOD_WORDS[case["language"]] if folded.startswith(r)]
        if roots and not any(w.startswith(r) for r in roots for w in listed) and word not in found:
            found.append(word)
    return found


def _cooking(words: list[str]) -> set[str]:
    return {way for way, starts in _COOKING.items() if any(w.startswith(starts) for w in words)}


def contradicted_methods(dishes: list[tuple[str, list[str]]], case: dict) -> list[str]:
    """Steps that cook a dish's food another way than its method says, as "Fry the eggs (Egg sandwich:
    boil)". A plan dish's steps are checked against the menu dish it names, or every menu dish when it
    names none, so an omelette's fried eggs aren't held to the boiled eggs beside it. A menu dish whose
    method names both ways or neither is skipped."""
    found = []
    for dish_name, actions in dishes:
        for dish in _menu_dishes(dish_name, case):
            ways = _cooking(_folded(dish.get("method") or ""))
            if len(ways) != 1:
                continue
            # The dish's own words: its name and its ingredients
            roots = _food_roots([dish["name"], *(s["name"] for s in dish.get("ingredients") or [])])
            for action in actions:
                words = _folded(action)
                if any(w.startswith(roots) for w in words) and _cooking(words) and not _cooking(words) & ways:
                    found.append(f"{action} ({dish['name']}: {next(iter(ways))})")
    return found


def _menu_dishes(dish_name: str, case: dict) -> list[dict]:
    """The menu items a plan dish is held to: the one it names, or, when it names none, every item
    that gets steps (a dish, or a simple item with a method)."""
    menu = [d for d in case["menu"] if d.get("ingredients") or d.get("method")]
    return [d for d in menu if same_name(d["name"], dish_name)] or menu


def _food_roots(names) -> tuple[str, ...]:
    """The names' words, plural-stripped, as word starts ("Eggs" → "egg")."""
    return tuple(r for name in names for r in (min(v, key=lambda w: (len(w), w)) for v in _tokens(name)) if len(r) >= 3)


def _verb_is(action: str, starts: tuple[str, ...], language: str) -> bool:
    """Whether a step's verb starts like one of these: its first word in English (both parts of
    "Hard-boil"), its last in Turkish."""
    words = action.split()
    verb = (words[-1:] if language == "tr" else words[:1]) or [""]
    return any(w.startswith(starts) for w in _folded(verb[0]))


def _plan_steps(plan: dict) -> list[tuple[str, list[dict]]]:
    """Each dish of a plan with its steps in order, as the planner gave them."""
    return [
        (str(d.get("dish") or ""), [s for s in d.get("steps") or [] if isinstance(s, dict)])
        for d in plan["dishes"] if isinstance(d, dict)
    ]


def heated_before_prep(steps: list[tuple[str, list[dict]]], case: dict) -> list[str]:
    """Cutting steps that come after the dish heated other food, as "Mash the avocado (after Toast the
    bread)": the hot food waits while the cook cuts (#160). Cutting the food that was heated (peel the
    boiled eggs) is fine, and so is any cut after a heating step whose food code can't tell."""
    found = []
    for dish_name, dish_steps in steps:
        roots = _food_roots(
            name for item in _menu_dishes(dish_name, case)
            for name in [s["name"] for s in item.get("ingredients") or []] or [item["name"]]
        )
        heated = []
        for step in dish_steps:
            action = str(step.get("action") or "")
            foods = {r for r in roots if any(w.startswith(r) for w in _folded(action))}
            if _verb_is(action, _CUTTING, case["language"]) and foods and heated and all(heated_foods for _, heated_foods in heated):
                other = next((a for a, heated_foods in heated if not heated_foods & foods), None)
                if other:
                    found.append(f"{action} (after {other})")
            if _verb_is(action, _HEATING, case["language"]):
                heated.append((action, foods))
    return found


def unheated_steps(steps: list[tuple[str, list[dict]]], case: dict) -> list[str]:
    """Heating steps with no appliance from the case's kitchen, as "Toast the bread (Avocado toast)":
    code serves food from a hot appliance last, so a heating step without one may be made first (#160).
    Any appliance from the kitchen passes. It's a note, not a problem: the cook can toast in the Oven
    when the plan says Toaster."""
    kitchen = {a.lower() for a in case["kitchen_appliances"]}
    return [
        f"{action} ({dish_name})" for dish_name, dish_steps in steps for step in dish_steps
        if _verb_is(action := str(step.get("action") or ""), _HEATING, case["language"])
        and str(step.get("appliance") or "").strip().lower() not in kitchen
    ]


def switches(plan: dict, case: dict) -> int:
    """How often the plan the app shows moves from one dish to another, scheduled by the app's own code."""
    timeline = _build_plan(plan, case["language"], case["kitchen_appliances"], served_items(case["menu"]))["timeline"]
    return sum(a["dish"] != b["dish"] for a, b in zip(timeline, timeline[1:]))


def check_plan(text: str, case: dict) -> dict:
    """Score one prep plan reply: does its JSON parse, does it plan only the menu, each dish as designed,
    and its prep before its heating. The note counts each dish's steps, so a plan of one step per dish
    shows, and the plan's switches between dishes, so a plan that hops from dish to dish every minute
    shows too, and names heating steps with no appliance from the kitchen."""
    plan = extract_json_block(text or "")
    if not isinstance(plan, dict) or not isinstance(plan.get("dishes"), list):
        return _no_json("plan")
    dishes, dish_steps = _plan_dishes(plan), _plan_steps(plan)
    fridge = {"language": case["language"], "ingredients": [{"name": n} for n in _menu_names(case["menu"])]}
    steps = ", ".join(f"{name or '?'} {len(actions)}" for name, actions in dishes) or "none"
    unheated = unheated_steps(dish_steps, case)
    return {
        "json": True,
        # The plan's steps, to count distinct plans across runs
        "dishes": sorted(f"{name}: {action}".lower() for name, actions in dishes for action in actions),
        "issues": {
            "unlisted": unlisted_food([text for name, actions in dishes for text in (name, *actions)], case),
            "method": contradicted_methods(dishes, case),
            "order": heated_before_prep(dish_steps, case),
            "turkish": turkish_words(text, fridge),
        },
        "note": f"steps {steps}; switches {switches(plan, case)}" + (f"; no appliance: {', '.join(unheated)}" if unheated else ""),
    }


def chat_amounts(text: str, sample: dict) -> list[str]:
    """Food amounts in a chat reply: a number with a unit from the app's list ("50 g", "1 slice") or
    with a fridge item's name ("2 eggs"). A number with anything else ("10 minutes") isn't one."""
    units = {m.start(): f"{m[1]} {m[2]}" for m in _AMOUNT.finditer(text)}
    found = list(units.values())
    names = [i["name"] for i in sample["ingredients"]]
    for match in _COUNTED.finditer(text):
        if match.start() in units:  # a unit's amount, even when its unit starts like a fridge item ("1 çay kaşığı")
            continue
        number, words = match[1], match[2].split()
        for k in range(len(words), 0, -1):
            phrase = " ".join(words[:k])
            if any(same_name(phrase, name) for name in names):
                found.append(f"{number} {phrase}")
                break
    return list(dict.fromkeys(found))


def brought_in(text: str, sample: dict, said: list[str]) -> list[str]:
    """Fridge items a chat reply names that the user's messages so far don't, by exact name. Two or more
    put a meal together ("a yogurt bowl with honey and walnuts"), so only then are they returned."""
    def named(name: str, words: list[str]) -> bool:
        tokens = name_tokens(name)
        return any(same_tokens(tokens, name_tokens(" ".join(words[i:i + len(tokens)]))) for i in range(len(words)))

    reply, user = re.findall(r"\w+", text), [w for message in said for w in re.findall(r"\w+", message)]
    found = [i["name"] for i in sample["ingredients"] if named(i["name"], reply) and not named(i["name"], user)]
    return found if len(found) >= 2 else []


def check_chat(text: str, sample: dict, said: list[str] = ()) -> dict:
    """Score one chat reply: the chat talks with the user, and menus and plans come only from a Suggest
    press (#168). Fridge items it brings in together, food amounts, numbered or timed steps and a code
    block make a menu or a plan, so they're flagged; said is the user's messages so far, whose foods the
    reply may repeat. The note says whether the reply points to the Suggest button. "json" here means a
    reply came back."""
    text = text or ""
    return {
        "json": bool(text.strip()),
        # The reply itself, to count distinct replies across runs
        "dishes": [" ".join(text.lower().split())],
        "issues": {
            "food": brought_in(text, sample, list(said)),
            "amounts": chat_amounts(text, sample),
            "steps": [line.strip()[:40] for line in _STEP.findall(text)],
            "block": ["```"] if "```" in text else [],
            "turkish": turkish_words(text, sample),
        },
        "note": "points to Suggest" if re.search(r"\bSuggest\b", text) else "no Suggest",
    }


def is_clean(result: dict) -> bool:
    return result["json"] and not any(result["issues"].values())


def describe(result: dict) -> str:
    """One line for a scored reply: "clean", "no JSON" or its problems."""
    if not result["json"]:
        return "no JSON"
    text = "; ".join(f"{p}: {', '.join(names)}" for p, names in result["issues"].items() if names) or "clean"
    return f"{text} ({result['note']})" if result.get("note") else text


# ── Runs ────────────────────────────────────────────────────────────────────

async def suggest_once(sample: dict, mode: str | None, draft_only: bool, scenario: dict | None = None) -> dict:
    """One Suggest press through the real pipeline: {"draft": text, "review": feedback, "final": text}.
    After a chat, the press sends the chat block the server builds from the session, kept as "chat"
    for the log."""
    replies = {}
    chat_block = format_chat_block(chat_rows(scenario["chat"], mode)) if scenario else None
    if chat_block:
        replies["chat"] = chat_block
    events = pipeline.run_suggestion_pipeline(
        context=sample,
        user_message=SUGGEST_MESSAGES[mode],
        mode=mode,
        temperature=SUGGEST_TEMPERATURES.get(mode),
        chat_block=chat_block,
    )
    async with aclosing(events):
        async for event in events:
            if event["type"] == "draft":
                replies["draft"] = event["content"]
                if draft_only:
                    break
            elif event["type"] == "review":
                replies["review"] = event["content"]
            elif event["type"] == "done":
                replies["final"] = event["content"]
    return replies


def shopping_prompt(sample: dict, hints: list[str]) -> str:
    """The shopping system prompt with this press's taste hints, built the way routers/ingredients.py builds it."""
    return build_shopping_prompt(
        taste_hints=hints,
        user_preferences=sample["preferences"],
        health_rules=sample["health_rules"],
        user_profile=sample["user_profile"],
        supplements=sample["supplements"],
        avoid_list=sample["avoid_list"],
        shopping_list=sample["shopping_list"],
        ratings=sample["ratings"],
        language=sample["language"],
        country=sample.get("country"),
    )


async def shop_once(sample: dict, sent: dict) -> dict:
    """Suggest Shopping, then Suggest More with what it showed: {"suggest": reply, "more": reply}.
    Each press draws its share of fridge items and taste hints like the endpoint, from a seeded
    source so tests compare. The endpoint's one retry after an all-repeat reply is left out;
    repeats are scored instead."""
    replies, shown = {}, []
    known = [i["name"] for i in sample["ingredients"]] + sample["shopping_list"] + sample["avoid_list"]
    rng = random.Random(SHOPPING_SEED)
    for stage in PERSONAS["shopping"]["stages"]:
        fridge, hints = pick_input(sample, rng)
        prompt = shopping_prompt(sample, hints)
        sent.setdefault(prompt, None)
        replies[stage] = await llm.chat_json(
            system_prompt=prompt,
            messages=[{"role": "user", "content": shopping_request(sample["language"], shown, fridge)}],
            schema=SUGGESTIONS_SCHEMA,
            temperature=SHOPPING_TEMPERATURE,
        )
        items = parse_suggestions(replies[stage]) or []
        shown += [i["name"] for i in new_suggestions(items, known + shown, _dishes(sample))]
    return replies


async def plan_once(case: dict, sent: dict) -> dict:
    """One Prep Plan press, built the way routers/scheduler.py builds it: {"request": menu message, "plan": reply}."""
    language, name = case["language"], case["meal_name"]
    prompt = build_scheduler_prompt(name, [], "", kitchen_appliances=case["kitchen_appliances"], language=language)
    message = build_scheduler_user_message(name, [], "", menu=case["menu"], language=language)
    sent.setdefault(prompt, None)
    chunks = [c async for c in suggestion.stream_response(prompt, [], message, temperature=PLAN_TEMPERATURE)]
    return {"request": message, "plan": "".join(chunks)}


async def review_once(case: dict, mode: str | None) -> dict:
    """The reviser alone on the case's fixed draft, the way the pipeline's step 2 sends it:
    {"draft": the draft as a reply, "review": the code check and the changes, "final": the revised
    meal as a reply, empty when it can't be read}."""
    draft = json.loads(json.dumps(case["draft"]))  # the reviser's meal is cleaned in place
    problems, _, changes, meal = await pipeline.revise(case, draft, mode)
    review = [f"- CODE CHECK: {p}" for p in problems] + [f"- {c}" for c in changes]
    return {
        "draft": pipeline._meal_reply(case["draft"]["menu_name"], case["draft"]),
        "review": "\n".join(review) or "- No changes.",
        "final": pipeline._meal_reply(meal["menu_name"], meal) if meal else "",
    }


def chat_prompt(sample: dict) -> str:
    """The chat persona's system prompt, built the way routers/chat.py builds it."""
    return suggestion.build_chat_prompt(
        ingredient_inventory=sample["ingredients"],
        recent_meal_history=sample["history"],
        user_preferences=sample["preferences"],
        stated_habits=sample["stated_habits"],
        inferred_habits=sample["inferred_habits"],
        health_rules=sample["health_rules"],
        avoid_list=sample["avoid_list"],
        kitchen_appliances=sample.get("kitchen_appliances"),
        language=sample["language"],
    )


async def chat_once(sample: dict, mode: str | None, scenario: dict, sent: dict) -> dict:
    """The scenario's typed messages sent to the chat persona one at a time, the way routers/chat.py sends
    them: each with the chat so far as history (an earlier Suggest press as its button text and its meal
    card's one line) and its reply added after it. {"chat": the typed messages, then a reply per message
    kind}. A reply is scored as the model wrote it, before the app drops a meal block from it."""
    prompt = chat_prompt(sample)
    sent.setdefault(prompt, None)
    typed = [entry["content"] for entry in scenario["chat"] if "press" not in entry]
    replies, history, kinds = {"chat": "\n".join(typed)}, [], iter(CHAT_MESSAGES)
    for entry in scenario["chat"]:
        if "press" in entry:
            history += chat_history(chat_rows([entry], mode))
            continue
        message = build_chat_message(entry["content"], sample["language"])
        reply = "".join([c async for c in suggestion.stream_response(prompt, history, message)])
        replies[next(kinds)] = reply
        history += [entry, {"role": "assistant", "content": reply}]
    return replies


@contextmanager
def recording_prompts(into: dict):
    """Collect each distinct system prompt the pipeline sends, streamed (draft, present) or as a
    structured call (the reviser); dict keys keep first-use order."""
    send, send_json = pipeline.stream_response, pipeline.chat_json

    async def record(system_prompt, history, message, temperature=None):
        into.setdefault(system_prompt, None)
        async for chunk in send(system_prompt, history, message, temperature=temperature):
            yield chunk

    async def record_json(system_prompt, messages, schema, temperature=None):
        into.setdefault(system_prompt, None)
        return await send_json(system_prompt=system_prompt, messages=messages, schema=schema, temperature=temperature)

    pipeline.stream_response, pipeline.chat_json = record, record_json
    try:
        yield
    finally:
        pipeline.stream_response, pipeline.chat_json = send, send_json


def _pool(persona: str) -> dict:
    """What a persona's --samples name: plan menus, review drafts, or sample users."""
    return {"plan": PLAN_CASES, "review": REVIEW_CASES}.get(persona, SAMPLES)


def _cases(samples: list[str], scenarios: list[str]) -> list[tuple[str, str, dict | None]]:
    """(label, sample, chat scenario) for every sample and scenario: "en" for a fresh chat, "en:chat"
    after one. A scenario the sample's fridge is too small for is skipped with a note."""
    cases = []
    for key in samples:
        for name in scenarios:
            scenario = chat_scenario(key, name)
            if name != "fresh" and scenario is None:
                print(f"{key}: fridge too small for the {name} scenario, skipped", flush=True)
                continue
            cases.append((key if name == "fresh" else f"{key}:{name}", key, scenario))
    return cases


async def run(
    samples: list[str], runs: int, mode: str | None, draft_only: bool, persona: str = "suggest",
    scenarios: list[str] = ("fresh",),
) -> tuple[list[dict], dict]:
    """Every run for every sample (and chat scenario), one at a time (they share the server's GPU), and the
    prompts sent. Without a mode, each sample's user presses Suggest the way they usually do."""
    records, prompts = [], {}
    for label, key, scenario in _cases(samples, scenarios if persona in ("suggest", "chat") else ["fresh"]):
        sample, sent = _pool(persona)[key], {}
        sample_mode = mode or SAMPLE_MODES.get(sample.get("sample", key))
        with recording_prompts(sent):
            for i in range(1, runs + 1):
                start = time.monotonic()
                try:
                    if persona == "shopping":
                        replies = await shop_once(sample, sent)
                    elif persona == "plan":
                        replies = await plan_once(sample, sent)
                    elif persona == "review":
                        replies = await review_once(sample, sample_mode)
                    elif persona == "chat":
                        replies = await chat_once(sample, sample_mode, scenario, sent)
                    else:
                        replies = await suggest_once(sample, sample_mode, draft_only, scenario=scenario)
                    error = None
                except Exception as e:  # keep going; the summary counts errors
                    replies, error = {}, f"{type(e).__name__}: {e}"
                if persona == "shopping":
                    scores = score_shopping(replies, sample)
                elif persona == "plan":
                    scores = {"plan": check_plan(replies["plan"], sample)} if "plan" in replies else {}
                elif persona == "review":
                    scores = {"final": check_review(replies["final"], sample, replies["draft"])} if "final" in replies else {}
                elif persona == "chat":
                    typed = [e["content"] for e in scenario["chat"] if "press" not in e]
                    scores = {
                        s: check_chat(replies[s], sample, typed[:i + 1]) for i, s in enumerate(CHAT_MESSAGES) if s in replies
                    }
                else:
                    scores = {
                        s: check_reply(replies[s], sample, scenario, draft=replies.get("draft") if s == "final" else None)
                        for s in STAGES if s in replies
                    }
                record = {
                    "sample": label,
                    "mode": sample_mode if persona in ("suggest", "review") else None,
                    "run": i,
                    "seconds": time.monotonic() - start,
                    "error": error,
                    "replies": replies,
                    "scores": scores,
                }
                records.append(record)
                outcome = error or "  |  ".join(f"{s}: {describe(r)}" for s, r in record["scores"].items())
                if replies.get("final") is not None and replies["final"] == replies.get("draft"):
                    outcome += " (draft kept)"
                print(f"{label:<15}{i:>3}/{runs}  {record['seconds']:>4.0f} s  {outcome}", flush=True)
        prompts[label] = list(sent)
    return records, prompts


# ── Report ──────────────────────────────────────────────────────────────────

def _columns(persona: str) -> list[tuple[str, str]]:
    problems = [(p.capitalize(), f">{max(len(p) + 3, 7)}") for p in PERSONAS[persona]["problems"]]
    return [
        ("Sample", "<16"), ("Stage", "<9"), ("Runs", ">5"), ("JSON", ">6"), ("Clean", ">7"), ("Distinct", ">10"),
        *problems, ("Errors", ">8"), ("Avg s", ">7"),
    ]


def _row(values, columns: list[tuple[str, str]]) -> str:
    return "".join(f"{v:{spec}}" for v, (_, spec) in zip(values, columns))


def _groups(records: list[dict], persona: str = "suggest"):
    """(sample, stage, runs, scored replies) for every sample and stage that has replies."""
    for key in dict.fromkeys(r["sample"] for r in records):
        runs = [r for r in records if r["sample"] == key]
        for stage in PERSONAS[persona]["stages"]:
            scored = [r["scores"][stage] for r in runs if stage in r["scores"]]
            if scored:
                yield key, stage, runs, scored


def stage_results(records: list[dict], persona: str = "suggest") -> dict[str, dict]:
    """Clean replies and distinct menus (or lists) per sample and stage, e.g. {"en final": {...}}."""
    return {
        f"{key} {stage}": {
            "clean": sum(1 for s in scored if is_clean(s)),
            "scored": len(scored),
            "distinct": len({tuple(s["dishes"]) for s in scored if s["json"]}),
        }
        for key, stage, _, scored in _groups(records, persona)
    }


def summarize(records: list[dict], persona: str = "suggest") -> str:
    """A row per sample and stage (problem columns count replies), then the top offenders."""
    results, columns, problems = stage_results(records, persona), _columns(persona), PERSONAS[persona]["problems"]
    lines = [_row((name for name, _ in columns), columns)]
    notes = []
    for key, stage, runs, scored in _groups(records, persona):
        result = results[f"{key} {stage}"]
        errors = sum(1 for r in runs if r["error"])
        avg = round(sum(r["seconds"] for r in runs) / len(runs))
        counts = [sum(1 for s in scored if s["issues"][p]) for p in problems]
        json_ok = sum(1 for s in scored if s["json"])
        lines.append(_row([key, stage, len(runs), json_ok, result["clean"], result["distinct"], *counts, errors, avg], columns))
        for p in problems:
            top = Counter(name for s in scored for name in s["issues"][p]).most_common(5)
            if top:
                notes.append(f"{key} {stage} {p}: " + ", ".join(f"{name} ×{n}" for name, n in top))
    return "\n".join(lines + ([""] + notes if notes else []))


# ── History ─────────────────────────────────────────────────────────────────

def _git(*args: str) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", check=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return done.stdout.strip()


def _commit() -> str:
    """Short commit of the prompts under test, marked when there are uncommitted changes."""
    return (_git("rev-parse", "--short", "HEAD") or "unknown") + (" + uncommitted changes" if _git("status", "--porcelain") else "")


def prompt_id() -> str:
    """Short hash of the prompt sources as they are now, committed or not (line endings ignored)."""
    digest = hashlib.sha1()
    for source in PROMPT_SOURCES:
        path = BACKEND / source
        for file in sorted(path.rglob("*.py")) if path.is_dir() else [path]:
            digest.update(file.relative_to(BACKEND).as_posix().encode())
            digest.update(file.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:7]


def load_history() -> list[dict]:
    """Earlier tests from history.jsonl, oldest first; unreadable lines are skipped."""
    if not HISTORY.exists():
        return []
    entries = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _share(result: dict) -> tuple[float, float]:
    """What better means: more clean replies first, then more distinct menus."""
    return result["clean"] / result["scored"], result["distinct"] / result["scored"]


def compare(results: dict, history: list[dict], mode: str, persona: str = "suggest") -> list[str]:
    """This test against the best earlier one per sample and stage, same persona, mode and checks: ▲ better, ▼ worse."""
    lines = []
    for key, now in results.items():
        text = f"{key}: {now['clean']}/{now['scored']} clean, {now['distinct']} distinct"
        earlier = [
            e for e in history
            if e.get("persona", "suggest") == persona and e.get("mode") == mode and e.get("checks", 1) == CHECKS
            and key in e.get("results", {})
        ]
        if not earlier:
            lines.append(f"{text} · first test")
            continue
        best = max(earlier, key=lambda e: _share(e["results"][key]))
        was = best["results"][key]
        mark = "▲" if _share(now) > _share(was) else "▼" if _share(now) < _share(was) else "="
        note = f' "{best["note"]}"' if best.get("note") else ""
        lines.append(
            f"{text} {mark} best {was['clean']}/{was['scored']} clean, {was['distinct']} distinct: "
            f"prompt {best['prompt']}{note} ({best['date']})"
        )
    return lines


def history_lines(history: list[dict]) -> list[str]:
    """One line per earlier test: when, prompt id, mode, results and note."""
    lines = []
    for e in history:
        results = ", ".join(f"{k} {r['clean']}/{r['scored']} ({r['distinct']} distinct)" for k, r in e["results"].items())
        note = f'  "{e["note"]}"' if e.get("note") else ""
        lines.append(f"{e['date']}  {e['prompt']}  {e.get('persona', 'suggest'):<9} {e['mode']:<9}  {results}{note}")
    return lines or ["No tests yet."]


# What the log calls the replies that aren't scored
_UNSCORED = {"draft": "Draft sent", "review": "Review feedback", "request": "Menu sent", "chat": "Chat sent"}


def save_log(records: list[dict], prompts: dict, header: str, report: str, diff: str) -> Path:
    """Write the report, uncommitted prompt changes, every reply and the prompts sent to tools/runs/."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.md"
    out = ["# Prompt test", "", header, "", "```", report, "```"]
    if diff:
        out += ["", "## Uncommitted prompt changes", "", "```diff", diff, "```"]
    for r in records:
        mode = f" · {r['mode']} mode" if r.get("mode") else ""
        out += ["", f"## {r['sample']}{mode} · run {r['run']} · {r['seconds']:.0f} s"]
        if r["error"]:
            out += ["", f"**Error:** {r['error']}"]
        for stage, text in r["replies"].items():
            title = f"{stage.capitalize()}: {describe(r['scores'][stage])}" if stage in r["scores"] else _UNSCORED[stage]
            out += ["", f"### {title}", "", "````text", text, "````"]
    out += ["", "## Prompts sent"]
    for key, sent in prompts.items():
        for i, prompt in enumerate(sent, 1):
            out += ["", f"<details><summary>{key} · system prompt {i}</summary>", "", "````text", prompt, "````", "", "</details>"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score the suggestion, shopping, prep plan and chat prompts against an Ollama server.")
    parser.add_argument("--url", default=llm.OLLAMA_BASE_URL, help="Ollama address (default: OLLAMA_BASE_URL)")
    parser.add_argument("--runs", type=int, default=1, help="Suggest presses per sample (default: 1)")
    parser.add_argument(
        "--samples",
        help=f"comma-separated or all, from: {', '.join(SAMPLES)} (default: en); "
             f"plan menus: {', '.join(PLAN_CASES)}; review drafts: {', '.join(REVIEW_CASES)} (both default: all)",
    )
    parser.add_argument("--persona", choices=list(PERSONAS), default="suggest", help="what to test (default: suggest)")
    parser.add_argument(
        "--mode", choices=["favorites", "explore"],
        help="Suggest mode for every sample (default: each sample's usual mode, plain Suggest for most)",
    )
    parser.add_argument(
        "--scenario", choices=[*SCENARIOS, "all"],
        help="what each Suggest press comes after: a fresh chat, typed messages, or typed messages "
             "between earlier presses (default: fresh); for the chat persona, the typed messages it gets "
             "(chat or pressed, default: chat)",
    )
    parser.add_argument("--draft", action="store_true", help="stop each run after the draft")
    parser.add_argument("--note", default="", help="what this prompt version changes, kept in the history")
    parser.add_argument("--history", action="store_true", help="list earlier tests and exit")
    args = parser.parse_args(argv)
    pool = _pool(args.persona)
    args.samples = [s.strip() for s in (args.samples or "").split(",") if s.strip()] or (
        list(pool) if pool is not SAMPLES else ["en"]
    )
    if args.samples == ["all"]:
        args.samples = list(pool)
    unknown = [s for s in args.samples if s not in pool]
    if unknown:
        parser.error(f"unknown sample: {', '.join(unknown)}")
    if args.persona == "chat":
        # The chat persona answers typed messages, so a fresh chat gives it nothing to answer
        args.scenario = args.scenario or "chat"
        if args.scenario == "fresh":
            parser.error("the chat persona needs typed messages: --scenario chat, pressed or all")
        chats = [s for s in SCENARIOS if s != "fresh"]
        args.scenarios = chats if args.scenario == "all" else [args.scenario]
        return args
    args.scenario = args.scenario or "fresh"
    if args.scenario != "fresh" and args.persona != "suggest":
        parser.error("--scenario is for Suggest presses and the chat persona only")
    args.scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    return args


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.history:
        print("\n".join(history_lines(load_history())))
        return 0
    llm.OLLAMA_BASE_URL = args.url  # llm reads it on every call, so every persona uses this server
    if not await llm.check_llm_availability():
        print(f"Ollama isn't reachable at {args.url}. See docs/SETUPALL.md, BONUS C.")
        return 1
    # The code under test as it is now; later edits during the run don't belong to this test
    mode, prompt, commit = args.mode or "usual", prompt_id(), _commit()
    diff = _git("diff", "HEAD", "--", *PROMPT_SOURCES)
    header = (
        f"Prompt {prompt} · commit {commit} · {llm.OLLAMA_MODEL} at {args.url} · {args.persona} · mode {mode} · "
        f"{args.runs} runs per sample" + (f" · scenario {args.scenario}" if args.scenario != "fresh" else "")
        + (" · draft only" if args.draft else "") + (f' · "{args.note}"' if args.note else "")
    )
    print(header, flush=True)
    records, prompts = await run(args.samples, args.runs, args.mode, args.draft, args.persona, args.scenarios)
    results = stage_results(records, args.persona)
    report = summarize(records, args.persona) + "\n\n" + "\n".join(compare(results, load_history(), mode, args.persona))
    log = save_log(records, prompts, header, report, diff)
    if results:
        entry = {
            "date": f"{datetime.now():%Y-%m-%d %H:%M}", "prompt": prompt, "commit": commit,
            "persona": args.persona, "mode": mode, "scenario": args.scenario, "checks": CHECKS,
            "draft_only": args.draft, "runs": args.runs, "note": args.note, "log": log.name, "results": results,
        }
        with HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print("\n" + report)
    print(f"\nReplies and prompts saved to {log}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Turkish names on a Windows console
    sys.exit(asyncio.run(main()))
