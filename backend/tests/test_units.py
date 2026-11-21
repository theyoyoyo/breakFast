"""Unit tests for the per-language unit lists and the 1-1 mapping between them."""

from models.units import UNIT_ML, UNIT_PAIRS, UNITS, count_unit, localize_unit, unit_sizes, units_for, unknown_units


# Every unit has exactly one match in the other language, so both lists line up
def test_lists_match_one_to_one():
    assert len(UNITS["en"]) == len(UNITS["tr"]) == len(UNIT_PAIRS)
    assert len(set(UNITS["en"])) == len(UNITS["en"])
    assert len(set(UNITS["tr"])) == len(UNITS["tr"])


# English is the default list; Turkish is used whenever the reply language isn't English
def test_units_for_follows_the_language():
    assert units_for("en")[:2] == ["pcs", "g"]
    assert units_for("tr")[:2] == ["adet", "g"]
    assert count_unit("en") == "pcs"
    assert count_unit("tr") == "adet"


# Known units switch language in both directions, ignoring case and spaces
def test_localize_known_units():
    assert localize_unit("adet", "en") == "pcs"
    assert localize_unit("pcs", "tr") == "adet"
    assert localize_unit("Yemek kaşığı ", "en") == "tbsp"
    assert localize_unit("tea glass", "tr") == "çay bardağı"
    assert localize_unit("l", "tr") == "L"
    assert localize_unit("g", "tr") == "g"


# Su bardağı is a 200 ml glass, and "cup" (a 240 ml US cup) isn't treated as one
def test_glass_is_su_bardagi_and_cup_is_unknown():
    assert localize_unit("su bardağı", "en") == "glass"
    assert localize_unit("Glasses", "tr") == "su bardağı"
    assert localize_unit("cup", "tr") == "cup"


# Every sized unit is a listed one, and its size reads the same in both languages
def test_unit_sizes_per_language():
    assert set(UNIT_ML) <= set(UNITS["en"])
    assert unit_sizes("en") == "tsp 5 ml, dsp 10 ml, tbsp 15 ml, tea glass 100 ml, glass 200 ml"
    assert unit_sizes("tr") == (
        "çay kaşığı 5 ml, tatlı kaşığı 10 ml, yemek kaşığı 15 ml, çay bardağı 100 ml, su bardağı 200 ml"
    )


# A meal's units the app can't show are listed once each; listed units and known spellings pass
def test_unknown_units_in_a_meal():
    meal = {"menu": [
        {"name": "Menemen", "ingredients": [{"name": "Yumurta", "unit": "adet"}, {"name": "Süt", "unit": "cup"}]},
        {"name": "Beyaz peynir", "amount": 50, "unit": "gr", "ingredients": []},
        {"name": "Zeytin", "amount": 10, "unit": "scoop", "ingredients": []},
        {"name": "Bal", "amount": 1, "unit": "cup", "ingredients": []},
    ]}
    assert unknown_units(meal, "tr") == ["cup", "scoop"]
    assert unknown_units({"menu": [{"name": "Simit", "amount": 1, "unit": "pieces"}]}, "en") == []


# Other spellings of a listed unit (old "gr", plurals) count as that unit
def test_localize_aliases():
    assert localize_unit("gr", "en") == "g"
    assert localize_unit("Slices", "tr") == "dilim"
    assert localize_unit("pieces", "en") == "pcs"
    assert localize_unit("tane", "en") == "pcs"


# Unknown units and missing values come back as written
def test_localize_unknown_units_unchanged():
    assert localize_unit("scoop", "tr") == "scoop"
    assert localize_unit("", "en") == ""
    assert localize_unit(None, "en") is None
