"""Unit tests for the per-language unit lists and the 1-1 mapping between them."""

from models.units import UNIT_PAIRS, UNITS, count_unit, localize_unit, units_for


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


# Unknown units and missing values come back as written
def test_localize_unknown_units_unchanged():
    assert localize_unit("scoop", "tr") == "scoop"
    assert localize_unit("", "en") == ""
    assert localize_unit(None, "en") is None
