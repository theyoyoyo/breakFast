"""Unit tests for utils."""

from utils import extract_json_block, resolve_static_file


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


def test_resolve_static_file_inside_root(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("js")
    assert resolve_static_file(tmp_path, "assets/app.js") == (tmp_path / "assets" / "app.js").resolve()


def test_resolve_static_file_missing_returns_none(tmp_path):
    assert resolve_static_file(tmp_path, "nope.js") is None
    assert resolve_static_file(tmp_path, "") is None  # directory, not a file


def test_resolve_static_file_blocks_traversal(tmp_path):
    root = tmp_path / "dist"
    root.mkdir()
    (tmp_path / "secret.db").write_text("secret")
    assert resolve_static_file(root, "../secret.db") is None
    assert resolve_static_file(root, "assets/../../secret.db") is None
    assert resolve_static_file(root, str(tmp_path / "secret.db")) is None  # absolute path
