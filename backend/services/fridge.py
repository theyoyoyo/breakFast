"""
Fridge check — which ingredients of a suggested meal are not in the user's fridge.

Plain code, not the LLM: the suggestion pipeline runs this on the draft and
hands the result to the refine step as a hard rule. Names are compared one
way round (case, Turkish letters and simple plurals aside): a meal name may
be shorter than a fridge name when it is the fridge name's end, its head noun
("Peynir" for "Beyaz peynir"). Its start names another product: "Olives"
isn't "Olive oil" and "Rice" isn't "Rice cakes". A longer name is another or
a prepared item: "Poached egg", "Simit with tahini" and "White cheese
(peynir)" aren't "Egg", "Simit" or "White cheese", so they come back as
dishes with their fridge ingredients (#115). Nothing is assumed: basics like
salt and oil count only when they are logged (usually in the Pantry group).

The avoid list is matched by exact name (same_name), like the shopping dedupe:
a user who bans "Peynir" and then sees "Beyaz peynir" bans that too, or states
a habit, rather than code guessing which products an item is in.
"""

import re

_FOLD = str.maketrans("ğĞıİşŞçÇöÖüÜâÂîÎûÛ", "gGiIsScCoOuUaAiIuU")


# Water is a utility like electricity and gas, not a fridge item
_WATER_WORDS = {"water", "su", "hot", "cold", "warm", "boiling", "tap", "sicak", "soguk", "ilik", "kaynar"}


def _words(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", name.translate(_FOLD).lower())


def _is_water(name: str) -> bool:
    """'Water', 'hot water', 'Sıcak su'… but not 'Maden suyu' or 'Sparkling water'."""
    words = set(_words(name))
    return bool(words & {"water", "su"}) and words <= _WATER_WORDS


def _tokens(name: str) -> list[set[str]]:
    """Words of a name, each with its simple plural-stripped variants (berries → berry too)."""
    result = []
    for w in _words(name):
        variants = {w}
        for suffix in ("es", "s", "ler", "lar"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                variants.add(w[: -len(suffix)])
        if w.endswith("ies") and len(w) > 4:
            variants.add(w[:-3] + "y")
        result.append(variants)
    return result


def _contains(hay: list[set[str]], needle: list[set[str]]) -> bool:
    """True when the needle's words appear in a row inside hay."""
    n = len(needle)
    return n > 0 and any(
        all(hay[i + j] & needle[j] for j in range(n)) for i in range(len(hay) - n + 1)
    )


def _ends_with(hay: list[set[str]], needle: list[set[str]]) -> bool:
    """True when the needle's words are hay's last words: its head noun, as in "Beyaz peynir"."""
    n = len(needle)
    return 0 < n <= len(hay) and all(h & w for h, w in zip(hay[-n:], needle))


def same_name(a: str, b: str) -> bool:
    """Exact match: the same words in order, ignoring case, Turkish letters and plurals.

    Every word of a product name carries meaning, so "Frozen strawberries" and
    "Strawberries" are different items while "Strawberry" and "strawberries" are not.
    """
    wa, wb = _tokens(a), _tokens(b)
    return len(wa) == len(wb) > 0 and all(x & y for x, y in zip(wa, wb))


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
    """Ingredients of the meal that are not in the inventory."""
    if not isinstance(meal, dict):
        return []
    stock = [_tokens(i["name"]) for i in inventory if i.get("name")]
    missing = []
    for name in meal_ingredient_names(meal):
        if _is_water(name):
            continue
        words = _tokens(name)
        if any(_ends_with(s, words) for s in stock):  # the name ends a fridge name
            continue
        if name not in missing:
            missing.append(name)
    return missing


def find_avoided(meal: dict | None, avoid_list: list[str]) -> list[str]:
    """Names in the meal, its dishes and their ingredients, that are on the avoid list."""
    if not isinstance(meal, dict):
        return []
    dishes = [i.get("name", "") for i in meal.get("menu") or [] if isinstance(i, dict) and i.get("ingredients")]
    names = dict.fromkeys(n for n in dishes + meal_ingredient_names(meal) if n)
    return [n for n in names if any(same_name(n, a) for a in avoid_list)]
