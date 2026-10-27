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
    ("cup", "su bardağı"),
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

# Row index for every known spelling, in either language
_ROW = {name.lower(): i for i, pair in enumerate(UNIT_PAIRS) for name in pair}


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
