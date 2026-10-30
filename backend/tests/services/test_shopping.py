"""Tests for the shopping suggestion reply parsing and the code dedupe."""

from services.shopping import new_suggestions, parse_suggestions


# A schema-shaped reply gives its items, names and reasons trimmed
def test_parse_reads_items():
    reply = '{"items": [{"name": " Salmon ", "reason": "Omega-3"}, {"name": "Kiwi", "reason": ""}]}'
    assert parse_suggestions(reply) == [
        {"name": "Salmon", "reason": "Omega-3"},
        {"name": "Kiwi", "reason": ""},
    ]


# Items without a usable name are skipped
def test_parse_skips_nameless_items():
    reply = '{"items": [{"name": ""}, "Kiwi", {"reason": "x"}, {"name": "Pear"}]}'
    assert parse_suggestions(reply) == [{"name": "Pear", "reason": ""}]


# Anything that isn't a JSON object with an items list counts as unparseable
def test_parse_rejects_other_shapes():
    assert parse_suggestions("Here are some ideas: salmon, kiwi") is None
    assert parse_suggestions('[{"name": "Salmon"}]') is None
    assert parse_suggestions('{"items": "Salmon"}') is None
    assert parse_suggestions(None) is None


# Known names are dropped by exact match, so a more specific product survives
def test_new_suggestions_drop_exact_matches_only():
    items = [
        {"name": "Strawberries", "reason": ""},
        {"name": "Frozen strawberries", "reason": ""},
        {"name": "Almond milk", "reason": ""},
        {"name": "eggs", "reason": ""},
    ]
    known = ["Strawberry", "Milk", "Egg"]
    assert [i["name"] for i in new_suggestions(items, known)] == ["Frozen strawberries", "Almond milk"]


# The same item twice in one reply is kept once
def test_new_suggestions_drop_repeats_within_reply():
    items = [{"name": "Kiwi", "reason": "a"}, {"name": "Kiwis", "reason": "b"}]
    assert new_suggestions(items, []) == [{"name": "Kiwi", "reason": "a"}]
