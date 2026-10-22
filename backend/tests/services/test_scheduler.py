"""Unit tests for the kitchen prep plan builder (finish-together scheduling)."""

from routers.scheduler import _build_plan


# ---------------------------------------------------------------------------
# _build_plan unit tests (backward scheduling logic)
# ---------------------------------------------------------------------------


def test_build_plan_backward_scheduling():
    """Timed tasks should be scheduled so they all finish at makespan."""
    raw = {
        "prep": [{"task": "Domates dilimle", "detail": "ince"}],
        "timed": [
            {"task": "Yumurta haşla", "duration_min": 7, "resource": "ocak", "end_action": "Süz"},
            {"task": "Ekmek kızart", "duration_min": 2, "resource": "tost_makinesi", "end_action": "Çıkar"},
        ],
    }
    result = _build_plan(raw)
    assert result["makespan_min"] == 7
    # Eggs (7 min) start at 0, toast (2 min) starts at 5
    eggs = next(t for t in result["timeline"] if "Yumurta" in t["task"])
    toast = next(t for t in result["timeline"] if "Ekmek" in t["task"])
    assert eggs["start_min"] == 0
    assert toast["start_min"] == 5


def test_build_plan_prep_section():
    """Prep tasks should appear in formatted output."""
    raw = {
        "prep": [
            {"task": "Salatalık doğra", "detail": "küp küp"},
            {"task": "Zeytinleri süz"},
        ],
        "timed": [],
    }
    result = _build_plan(raw, "tr")
    assert "🔪 Hazırlık" in result["formatted"]
    assert "Salatalık doğra — küp küp" in result["formatted"]
    assert "Zeytinleri süz" in result["formatted"]
    assert result["makespan_min"] == 0


def test_build_plan_end_action_shown():
    """End actions should appear as ↳ lines."""
    raw = {
        "prep": [],
        "timed": [
            {"task": "Haşla", "duration_min": 5, "resource": "ocak", "end_action": "Süz ve soğut"},
        ],
    }
    result = _build_plan(raw, "tr")
    assert "↳ Süz ve soğut" in result["formatted"]
    assert "Hazır! ✓" in result["formatted"]
    assert "(5 dk)" in result["formatted"]


def test_build_plan_labels_default_to_english():
    """Plan labels follow the response language, English by default."""
    raw = {
        "prep": [{"task": "Slice tomatoes"}],
        "timed": [{"task": "Boil eggs", "duration_min": 7, "resource": "Stove", "end_action": "Drain"}],
    }
    formatted = _build_plan(raw)["formatted"]
    assert "🔪 Prep" in formatted
    assert "⏱ Timeline (7 min)" in formatted
    assert "Boil eggs (7 min)" in formatted
    assert "Ready! ✓" in formatted
    assert "Hazır" not in formatted


def test_build_plan_no_timed_no_crash():
    """Should handle plans with only prep tasks."""
    raw = {"prep": [{"task": "Karıştır"}], "timed": []}
    result = _build_plan(raw)
    assert result["makespan_min"] == 0
    assert len(result["timeline"]) == 0
    assert "Karıştır" in result["formatted"]


def test_build_plan_empty_plan():
    """Should handle empty plan gracefully."""
    result = _build_plan({})
    assert result["makespan_min"] == 0
    assert result["formatted"] == ""

