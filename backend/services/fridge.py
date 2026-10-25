"""
Fridge check — which ingredients of a suggested meal are not in the user's fridge.

Plain code, not the LLM: the suggestion pipeline runs this on the draft and
hands the result to the refine step as a hard rule. Names are compared
loosely (case, Turkish letters, simple plurals, "Beyaz peynir" ~ "Peynir"),
so the check only flags clear misses.
"""

import re

from models.ingredient import ALWAYS_AVAILABLE_NAMES

_FOLD = str.maketrans("ğĞıİşŞçÇöÖüÜâÂîÎûÛ", "gGiIsScCoOuUaAiIuU")


def _tokens(name: str) -> list[set[str]]:
    """Words of a name, each with its simple plural-stripped variants."""
    words = re.findall(r"[a-z0-9]+", name.translate(_FOLD).lower())
    result = []
    for w in words:
        variants = {w}
        for suffix in ("es", "s", "ler", "lar"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                variants.add(w[: -len(suffix)])
        result.append(variants)
    return result


def _contains(hay: list[set[str]], needle: list[set[str]]) -> bool:
    """True when the needle's words appear in a row inside hay."""
    n = len(needle)
    return n > 0 and any(
        all(hay[i + j] & needle[j] for j in range(n)) for i in range(len(hay) - n + 1)
    )


def _same_item(a: list[set[str]], b: list[set[str]]) -> bool:
    return _contains(a, b) or _contains(b, a)


_BASICS = [_tokens(n) for n in ALWAYS_AVAILABLE_NAMES]


def meal_ingredient_names(meal: dict) -> list[str]:
    """Every ingredient a meal uses: dish sub-ingredients and simple served items."""
    names = []
    for item in meal.get("menu") or []:
        if not isinstance(item, dict):
            names.append(str(item))
        elif item.get("ingredients"):
            names += [s.get("name", "") if isinstance(s, dict) else str(s) for s in item["ingredients"]]
        else:
            names.append(item.get("name", ""))
    if not meal.get("menu"):  # old flat format
        names += [i.get("name", "") if isinstance(i, dict) else str(i) for i in meal.get("ingredients") or []]
    return [n.strip() for n in names if n and n.strip()]


def find_missing_ingredients(meal: dict | None, inventory: list[dict]) -> list[str]:
    """Ingredients of the meal that are neither in the inventory nor always-available basics."""
    if not isinstance(meal, dict):
        return []
    stock = [_tokens(i["name"]) for i in inventory if i.get("name")]
    missing = []
    for name in meal_ingredient_names(meal):
        words = _tokens(name)
        if any(_same_item(words, s) for s in stock) or any(_contains(words, b) for b in _BASICS):
            continue
        if name not in missing:
            missing.append(name)
    return missing
