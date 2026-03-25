"""
Kitchen job-shop scheduler.
Minimizes makespan (total wall-clock time) by parallelizing cooking tasks
across available appliances using a greedy earliest-start-time algorithm.

Resources: air_fryer, toaster, stove, hands
Thermal momentum: air fryer tasks scheduled back-to-back get a 20% cook-time reduction.
"""

from dataclasses import dataclass, field

from utils import extract_json_block


@dataclass
class Task:
    name: str
    resource: str          # 'air_fryer' | 'toaster' | 'stove' | 'hands' | 'none'
    duration_min: float
    predecessors: list[str] = field(default_factory=list)  # task names
    item: str = ""         # which food item this task belongs to


@dataclass
class ScheduleEntry:
    time: float
    label: str
    resource: str
    note: str = ""


def schedule(tasks: list[Task]) -> dict:
    """
    Given a list of Task objects, return a dict with:
      - 'timeline': list of dicts (sorted by start_time)
      - 'makespan_min': total time in minutes
      - 'formatted': human-readable schedule string

    Task objects are NOT mutated. Computed times are tracked in local dicts.
    """
    # Separate dicts for computed times — keeps Task objects immutable
    end_times: dict[str, float] = {}      # task name -> computed end time
    resource_free_at: dict[str, float] = {}  # resource -> earliest free time
    last_air_fryer_end: float = 0.0

    def earliest_start(task: Task) -> float:
        pred_end = max((end_times.get(p, 0.0) for p in task.predecessors), default=0.0)
        res_free = resource_free_at.get(task.resource, 0.0)
        return max(pred_end, res_free)

    remaining = list(tasks)
    timeline: list[ScheduleEntry] = []

    while remaining:
        # Find tasks whose predecessors have all been scheduled
        ready = [t for t in remaining if all(p in end_times for p in t.predecessors)]
        if not ready:
            break  # cycle or bad input — stop to avoid infinite loop

        # Pick the task that can start earliest (min avoids redundant sort)
        task = min(ready, key=earliest_start)
        start = earliest_start(task)
        duration = task.duration_min

        # Thermal momentum: back-to-back air fryer use saves 20% cook time
        note = ""
        if task.resource == "air_fryer":
            if last_air_fryer_end > 0 and start <= last_air_fryer_end + 2.0:
                duration *= 0.8
                note = "thermal momentum — residual heat"
            last_air_fryer_end = start + duration

        end = start + duration
        end_times[task.name] = end

        if task.resource != "none":
            resource_free_at[task.resource] = end

        timeline.append(ScheduleEntry(
            time=start,
            label=f"{task.item} — {task.name}" if task.item else task.name,
            resource=task.resource,
            note=note,
        ))
        remaining.remove(task)

    makespan = max(end_times.values(), default=0.0)
    timeline.sort(key=lambda e: e.time)

    return {
        "timeline": [
            {"time": e.time, "label": e.label, "resource": e.resource, "note": e.note}
            for e in timeline
        ],
        "makespan_min": makespan,
        "formatted": _format_timeline(timeline, makespan),
    }


_RESOURCE_LABELS = {
    "air_fryer": "airfryer",
    "toaster": "ekmek kızartma makinesi",
    "stove": "ocak",
    "hands": "elle",
    "none": "bekleme",
}


def _format_timeline(timeline: list[ScheduleEntry], makespan: float) -> str:
    lines = []
    for entry in timeline:
        m = int(entry.time)
        s = int((entry.time - m) * 60)
        res = _RESOURCE_LABELS.get(entry.resource, entry.resource)
        line = f"{m}:{s:02d}  — {entry.label}  [{res}]"
        if entry.note:
            line += f"  ({entry.note})"
        lines.append(line)
    lines.append(f"Toplam süre: {int(makespan)} dakika.")
    return "\n".join(lines)


# Re-export the shared JSON extractor under the original name for compatibility
parse_schedule_from_llm = extract_json_block
