# ---------------------------------------------------------------------------
# Units per response language — single source of truth.
# Each row pairs an English unit with its Turkish match (1-1), so a known unit
# can be shown in either language. Mirrored in frontend utils/ingredients.js.
# ---------------------------------------------------------------------------

UNIT_PAIRS = [
    ("pcs", "adet"),
    ("g", "g"),
    ("kg", "kg"),
    ("ml", "ml"),
    ("l", "L"),
    ("tsp", "çay kaşığı"),
    ("dsp", "tatlı kaşığı"),
    ("tbsp", "yemek kaşığı"),
    ("tea glass", "çay bardağı"),
    ("glass", "su bardağı"),
    ("slice", "dilim"),
    ("bunch", "demet"),
    ("pinch", "tutam"),
    ("handful", "avuç"),
    ("clove", "diş"),
    ("sprig", "dal"),
    ("pack", "paket"),
]

UNITS = {
    "en": [en for en, _ in UNIT_PAIRS],
    "tr": [tr for _, tr in UNIT_PAIRS],
}

# Spoons and glasses have one fixed size, the same in both languages, so an amount
# means the same whichever language shows it (stated in the suggestion prompt)
UNIT_ML = {"tsp": 5, "dsp": 10, "tbsp": 15, "tea glass": 100, "glass": 200}

# Other spellings of a listed unit, from older meals (the prompt example once said "gr") and the model
UNIT_ALIASES = {
    "gr": "g", "gram": "g", "grams": "g",
    "pc": "pcs", "piece": "pcs", "pieces": "pcs", "tane": "pcs",
    "liter": "l", "litre": "l", "lt": "l",
    "teaspoon": "tsp", "teaspoons": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp",
    "glasses": "glass", "slices": "slice", "bunches": "bunch", "pinches": "pinch",
    "handfuls": "handful", "cloves": "clove", "sprigs": "sprig", "packs": "pack",
}

# Row index for every known spelling, in either language
_ROW = {name.lower(): i for i, pair in enumerate(UNIT_PAIRS) for name in pair}
_ROW.update({alias: _ROW[unit] for alias, unit in UNIT_ALIASES.items()})


def units_for(language: str) -> list[str]:
    """The unit list of the response language (Turkish unless it's English, like the prompts)."""
    return UNITS["en"] if language == "en" else UNITS["tr"]


def count_unit(language: str) -> str:
    """The plain count unit (pcs / adet), used when an item has no unit."""
    return units_for(language)[0]


def localize_unit(unit, language: str):
    """A known unit in the given language; anything else as written."""
    if not isinstance(unit, str):
        return unit
    row = _ROW.get(unit.strip().lower())
    if row is None:
        return unit
    return UNIT_PAIRS[row][0 if language == "en" else 1]


def unit_sizes(language: str) -> str:
    """Spoon and glass sizes with the language's unit names, e.g. "tsp 5 ml, …, glass 200 ml"."""
    return ", ".join(f"{localize_unit(unit, language)} {ml} ml" for unit, ml in UNIT_ML.items())
