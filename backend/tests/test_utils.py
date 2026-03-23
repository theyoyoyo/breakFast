"""Unit tests for utils.extract_json_block."""

from utils import extract_json_block


def test_extracts_valid_json_block():
    text = 'Here is the result:\n```json\n{"meal_name": "Eggs"}\n```\nEnjoy!'
    assert extract_json_block(text) == {"meal_name": "Eggs"}


def test_returns_none_when_no_block():
    assert extract_json_block("No JSON here at all.") is None


def test_returns_none_on_invalid_json():
    assert extract_json_block("```json\n{bad json}\n```") is None


def test_handles_multiline_json():
    text = '```json\n{\n  "meal_name": "Toast",\n  "prep_time_min": 5\n}\n```'
    result = extract_json_block(text)
    assert result == {"meal_name": "Toast", "prep_time_min": 5}


def test_ignores_text_outside_block():
    text = "Some intro.\n```json\n{\"key\": \"value\"}\n```\nSome outro."
    assert extract_json_block(text) == {"key": "value"}


def test_handles_nested_objects_and_arrays():
    """Meal JSON with nested ingredients array should parse correctly."""
    text = '```json\n{"meal_name": "Serpme", "ingredients": [{"name": "Peynir", "quantity": 50, "unit": "g"}, {"name": "Zeytin", "quantity": 6, "unit": "adet"}]}\n```'
    result = extract_json_block(text)
    assert result["meal_name"] == "Serpme"
    assert len(result["ingredients"]) == 2
    assert result["ingredients"][0]["name"] == "Peynir"
