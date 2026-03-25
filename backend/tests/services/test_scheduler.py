"""Unit tests for the kitchen job-shop scheduler and plan builder."""

from services.scheduler import Task, schedule
from routers.scheduler import _build_plan


def test_single_task_starts_at_zero():
    tasks = [Task(name="toast", resource="toaster", duration_min=3)]
    result = schedule(tasks)
    assert result["makespan_min"] == 3
    assert len(result["timeline"]) == 1
    assert result["timeline"][0]["time"] == 0


def test_independent_tasks_run_in_parallel():
    """Tasks on different resources overlap, so makespan equals the longest task."""
    tasks = [
        Task(name="eggs", resource="stove", duration_min=5),
        Task(name="toast", resource="toaster", duration_min=3),
    ]
    result = schedule(tasks)
    assert result["makespan_min"] == 5  # stove task is the bottleneck


def test_predecessor_forces_sequential_execution():
    tasks = [
        Task(name="heat_pan", resource="stove", duration_min=2),
        Task(name="fry_eggs", resource="stove", duration_min=4, predecessors=["heat_pan"]),
    ]
    result = schedule(tasks)
    # fry_eggs can only start after heat_pan ends at t=2
    fry = next(e for e in result["timeline"] if "fry_eggs" in e["label"])
    assert fry["time"] == 2
    assert result["makespan_min"] == 6


def test_thermal_momentum_reduces_back_to_back_air_fryer_duration():
    tasks = [
        Task(name="fries", resource="air_fryer", duration_min=10),
        Task(name="nuggets", resource="air_fryer", duration_min=10),
    ]
    result = schedule(tasks)
    # nuggets starts at t=10 (immediately after fries), gets 20% reduction → 8 min
    assert result["makespan_min"] == 18.0


def test_no_thermal_momentum_when_gap_exceeds_two_minutes():
    tasks = [
        Task(name="fries", resource="air_fryer", duration_min=10),
        # hands task delays the second air fryer use by 5 minutes
        Task(
            name="wait",
            resource="hands",
            duration_min=5,
            predecessors=["fries"],
        ),
        Task(
            name="nuggets",
            resource="air_fryer",
            duration_min=10,
            predecessors=["wait"],
        ),
    ]
    result = schedule(tasks)
    # nuggets starts at t=15 — gap from t=10 to t=15 is 5 min > 2 → no discount
    nuggets = next(e for e in result["timeline"] if "nuggets" in e["label"])
    assert nuggets["note"] == ""
    assert result["makespan_min"] == 25


def test_empty_task_list_returns_zero_makespan():
    result = schedule([])
    assert result["makespan_min"] == 0
    assert result["timeline"] == []


def test_formatted_output_contains_total_time():
    tasks = [Task(name="boil", resource="stove", duration_min=7)]
    result = schedule(tasks)
    assert "Toplam süre: 7 dakika" in result["formatted"]


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
    result = _build_plan(raw)
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
    result = _build_plan(raw)
    assert "↳ Süz ve soğut" in result["formatted"]
    assert "Hazır! ✓" in result["formatted"]


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

