"""
Prompt test — runs the real suggestion pipeline against an Ollama server and scores
every reply in code, so a prompt change gets a before and after number (#116).

Run from backend/, with the server's Ollama reachable (docs/SETUPALL.md, BONUS C):
    python -m tools.prompt_check --url http://100.x.x.x:11434 --note "what changed"
    python -m tools.prompt_check --samples en,tr --runs 5 --draft
    python -m tools.prompt_check --history

Each run is one Suggest press for a sample user (tools/prompt_samples.py) through the
real draft → review → refine pipeline. The draft and the final reply are both scored;
--draft stops after the draft (one model call instead of three). Nothing touches the
database. Every test is kept locally in tools/runs/ (git-ignored): a log with the
replies and the exact prompts sent, and a line in history.jsonl that later tests are
compared against, so a prompt change can't quietly make things worse.
"""

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import Counter
from contextlib import aclosing, contextmanager
from datetime import datetime
from pathlib import Path

from models.units import localize_unit, units_for
from routers.chat import SUGGEST_TEMPERATURES
from services import llm, pipeline
# The fridge check's own word matching, used one way round for prepared items
from services.fridge import _contains, _is_water, _tokens, find_missing_ingredients
from tools.prompt_samples import SAMPLES
from utils import extract_json_block

BACKEND = Path(__file__).resolve().parent.parent
RUNS_DIR = BACKEND / "tools" / "runs"
HISTORY = RUNS_DIR / "history.jsonl"

# Everything that shapes what the pipeline sends; their content is the prompt id
PROMPT_SOURCES = [
    "services/personas", "services/knowledge.py", "services/pipeline.py",
    "services/fridge.py", "models/units.py", "tools/prompt_samples.py",
]

# What the Suggest button sends per mode (frontend ChatInterface.jsx, handleSuggest)
SUGGEST_MESSAGES = {
    None: "Suggest Breakfast",
    "favorites": "Suggest breakfast from my favorite meals",
    "explore": "Suggest a different breakfast from world cuisines",
}

STAGES = ("draft", "final")
PROBLEMS = ("missing", "prepared", "units", "turkish")
_TURKISH_LETTERS = set("çğıöşüÇĞİÖŞÜ")


# ── Checks ──────────────────────────────────────────────────────────────────

def prepared_items(meal: dict, inventory: list[dict]) -> list[str]:
    """Simple items (served as-is) whose name doesn't sit inside one fridge name.

    Stricter than the fridge check, which matches both ways round: "Simit with
    tahini dipping sauce" passes there because it contains "Simit" (#115).
    """
    stock = [_tokens(i["name"]) for i in inventory if i.get("name")]
    found = []
    for item in meal.get("menu") or []:
        if not isinstance(item, dict) or item.get("ingredients"):
            continue
        name = str(item.get("name") or "").strip()
        if name and not _is_water(name) and not any(_contains(s, _tokens(name)) for s in stock):
            found.append(name)
    return found


def off_list_units(meal: dict, language: str) -> list[str]:
    """Units the app can't show as one of the language's units (known spellings like "gr" pass)."""
    allowed = {u.lower() for u in units_for(language)}
    found = []
    for item in meal.get("menu") or []:
        if not isinstance(item, dict):
            continue
        for row in item.get("ingredients") or [item]:
            unit = row.get("unit") if isinstance(row, dict) else None
            if not isinstance(unit, str) or not unit.strip() or unit in found:
                continue
            if localize_unit(unit, language).strip().lower() not in allowed:
                found.append(unit)
    return found


def turkish_words(text: str, sample: dict) -> list[str]:
    """Words with Turkish letters in an English reply, other than words of fridge names and the country."""
    if sample["language"] != "en":
        return []
    names = [i["name"] for i in sample["ingredients"]] + [sample.get("country") or ""]
    fridge = {w.lower() for name in names for w in re.findall(r"\w+", name)}
    found = []
    for word in re.findall(r"\w+", text):
        if _TURKISH_LETTERS & set(word) and word.lower() not in fridge and word not in found:
            found.append(word)
    return found


def check_reply(text: str, sample: dict) -> dict:
    """Score one reply: does its meal JSON parse, and what's wrong with the meal."""
    meal = extract_json_block(text or "")
    if not isinstance(meal, dict) or not isinstance(meal.get("menu"), list):
        return {"json": False, "dishes": [], **{p: [] for p in PROBLEMS}}
    missing = find_missing_ingredients(meal, sample["ingredients"])
    return {
        "json": True,
        # The menu's dish and item names, to count distinct menus across runs
        "dishes": sorted(str(i.get("name", "")).strip().lower() for i in meal["menu"] if isinstance(i, dict)),
        "missing": missing,
        # A simple item that isn't in the fridge at all counts once, as missing
        "prepared": [n for n in prepared_items(meal, sample["ingredients"]) if n not in missing],
        "units": off_list_units(meal, sample["language"]),
        "turkish": turkish_words(text, sample),
    }


def is_clean(result: dict) -> bool:
    return result["json"] and not any(result[p] for p in PROBLEMS)


def describe(result: dict) -> str:
    """One line for a scored reply: "clean", "no meal JSON" or its problems."""
    if not result["json"]:
        return "no meal JSON"
    return "; ".join(f"{p}: {', '.join(result[p])}" for p in PROBLEMS if result[p]) or "clean"


# ── Runs ────────────────────────────────────────────────────────────────────

async def suggest_once(sample: dict, mode: str | None, draft_only: bool) -> dict:
    """One Suggest press through the real pipeline: {"draft": text, "final": text}."""
    replies = {}
    events = pipeline.run_suggestion_pipeline(
        context=sample,
        user_message=SUGGEST_MESSAGES[mode],
        mode=mode,
        temperature=SUGGEST_TEMPERATURES.get(mode),
    )
    async with aclosing(events):
        async for event in events:
            if event["type"] == "draft":
                replies["draft"] = event["content"]
                if draft_only:
                    break
            elif event["type"] == "done":
                replies["final"] = event["content"]
    return replies


@contextmanager
def recording_prompts(into: dict):
    """Collect each distinct system prompt the pipeline sends (dict keys keep first-use order)."""
    send = pipeline.stream_response

    async def record(system_prompt, history, message, temperature=None):
        into.setdefault(system_prompt, None)
        async for chunk in send(system_prompt, history, message, temperature=temperature):
            yield chunk

    pipeline.stream_response = record
    try:
        yield
    finally:
        pipeline.stream_response = send


async def run(samples: list[str], runs: int, mode: str | None, draft_only: bool) -> tuple[list[dict], dict]:
    """Every run for every sample, one at a time (they share the server's GPU), and the prompts sent."""
    records, prompts = [], {}
    for key in samples:
        sent = {}
        with recording_prompts(sent):
            for i in range(1, runs + 1):
                start = time.monotonic()
                try:
                    replies, error = await suggest_once(SAMPLES[key], mode, draft_only), None
                except Exception as e:  # keep going; the summary counts errors
                    replies, error = {}, f"{type(e).__name__}: {e}"
                record = {
                    "sample": key,
                    "run": i,
                    "seconds": time.monotonic() - start,
                    "error": error,
                    "replies": replies,
                    "scores": {stage: check_reply(text, SAMPLES[key]) for stage, text in replies.items()},
                }
                records.append(record)
                outcome = error or "  |  ".join(f"{s}: {describe(r)}" for s, r in record["scores"].items())
                print(f"{key:<4}{i:>3}/{runs}  {record['seconds']:>4.0f} s  {outcome}", flush=True)
        prompts[key] = list(sent)
    return records, prompts


# ── Report ──────────────────────────────────────────────────────────────────

_COLUMNS = [
    ("Sample", "<7"), ("Stage", "<7"), ("Runs", ">5"), ("JSON", ">6"), ("Clean", ">7"), ("Distinct", ">10"),
    ("Missing", ">9"), ("Prepared", ">10"), ("Units", ">7"), ("Turkish", ">9"), ("Errors", ">8"), ("Avg s", ">7"),
]


def _row(values) -> str:
    return "".join(f"{v:{spec}}" for v, (_, spec) in zip(values, _COLUMNS))


def _groups(records: list[dict]):
    """(sample, stage, runs, scored replies) for every sample and stage that has replies."""
    for key in dict.fromkeys(r["sample"] for r in records):
        runs = [r for r in records if r["sample"] == key]
        for stage in STAGES:
            scored = [r["scores"][stage] for r in runs if stage in r["scores"]]
            if scored:
                yield key, stage, runs, scored


def stage_results(records: list[dict]) -> dict[str, dict]:
    """Clean replies and distinct menus per sample and stage, e.g. {"en final": {...}}."""
    return {
        f"{key} {stage}": {
            "clean": sum(1 for s in scored if is_clean(s)),
            "scored": len(scored),
            "distinct": len({tuple(s["dishes"]) for s in scored if s["json"]}),
        }
        for key, stage, _, scored in _groups(records)
    }


def summarize(records: list[dict]) -> str:
    """A row per sample and stage (problem columns count replies), then the top offenders."""
    results = stage_results(records)
    lines = [_row(name for name, _ in _COLUMNS)]
    notes = []
    for key, stage, runs, scored in _groups(records):
        result = results[f"{key} {stage}"]
        errors = sum(1 for r in runs if r["error"])
        avg = round(sum(r["seconds"] for r in runs) / len(runs))
        problems = [sum(1 for s in scored if s[p]) for p in PROBLEMS]
        json_ok = sum(1 for s in scored if s["json"])
        lines.append(_row([key, stage, len(runs), json_ok, result["clean"], result["distinct"], *problems, errors, avg]))
        for p in PROBLEMS:
            top = Counter(name for s in scored for name in s[p]).most_common(5)
            if top:
                notes.append(f"{key} {stage} {p}: " + ", ".join(f"{name} ×{n}" for name, n in top))
    return "\n".join(lines + ([""] + notes if notes else []))


# ── History ─────────────────────────────────────────────────────────────────

def _git(*args: str) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", check=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return done.stdout.strip()


def _commit() -> str:
    """Short commit of the prompts under test, marked when there are uncommitted changes."""
    return (_git("rev-parse", "--short", "HEAD") or "unknown") + (" + uncommitted changes" if _git("status", "--porcelain") else "")


def prompt_id() -> str:
    """Short hash of the prompt sources as they are now, committed or not (line endings ignored)."""
    digest = hashlib.sha1()
    for source in PROMPT_SOURCES:
        path = BACKEND / source
        for file in sorted(path.rglob("*.py")) if path.is_dir() else [path]:
            digest.update(file.relative_to(BACKEND).as_posix().encode())
            digest.update(file.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:7]


def load_history() -> list[dict]:
    """Earlier tests from history.jsonl, oldest first; unreadable lines are skipped."""
    if not HISTORY.exists():
        return []
    entries = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _share(result: dict) -> tuple[float, float]:
    """What better means: more clean replies first, then more distinct menus."""
    return result["clean"] / result["scored"], result["distinct"] / result["scored"]


def compare(results: dict, history: list[dict], mode: str) -> list[str]:
    """This test against the best earlier one per sample and stage, same mode: ▲ better, ▼ worse, = same."""
    lines = []
    for key, now in results.items():
        text = f"{key}: {now['clean']}/{now['scored']} clean, {now['distinct']} distinct"
        earlier = [e for e in history if e.get("mode") == mode and key in e.get("results", {})]
        if not earlier:
            lines.append(f"{text} · first test")
            continue
        best = max(earlier, key=lambda e: _share(e["results"][key]))
        was = best["results"][key]
        mark = "▲" if _share(now) > _share(was) else "▼" if _share(now) < _share(was) else "="
        note = f' "{best["note"]}"' if best.get("note") else ""
        lines.append(
            f"{text} {mark} best {was['clean']}/{was['scored']} clean, {was['distinct']} distinct: "
            f"prompt {best['prompt']}{note} ({best['date']})"
        )
    return lines


def history_lines(history: list[dict]) -> list[str]:
    """One line per earlier test: when, prompt id, mode, results and note."""
    lines = []
    for e in history:
        results = ", ".join(f"{k} {r['clean']}/{r['scored']} ({r['distinct']} distinct)" for k, r in e["results"].items())
        note = f'  "{e["note"]}"' if e.get("note") else ""
        lines.append(f"{e['date']}  {e['prompt']}  {e['mode']:<9}  {results}{note}")
    return lines or ["No tests yet."]


def save_log(records: list[dict], prompts: dict, header: str, report: str) -> Path:
    """Write the report, any uncommitted prompt changes, every reply and the prompts sent to tools/runs/."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.md"
    out = ["# Prompt test", "", header, "", "```", report, "```"]
    diff = _git("diff", "HEAD", "--", *PROMPT_SOURCES)
    if diff:
        out += ["", "## Uncommitted prompt changes", "", "```diff", diff, "```"]
    for r in records:
        out += ["", f"## {r['sample']} · run {r['run']} · {r['seconds']:.0f} s"]
        if r["error"]:
            out += ["", f"**Error:** {r['error']}"]
        for stage, text in r["replies"].items():
            out += ["", f"### {stage.capitalize()}: {describe(r['scores'][stage])}", "", "````text", text, "````"]
    out += ["", "## Prompts sent"]
    for key, sent in prompts.items():
        for i, prompt in enumerate(sent, 1):
            out += ["", f"<details><summary>{key} · system prompt {i}</summary>", "", "````text", prompt, "````", "", "</details>"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score the suggestion prompts against an Ollama server.")
    parser.add_argument("--url", default=llm.OLLAMA_BASE_URL, help="Ollama address (default: OLLAMA_BASE_URL)")
    parser.add_argument("--runs", type=int, default=3, help="Suggest presses per sample (default: 3)")
    parser.add_argument("--samples", default="en", help=f"comma-separated, from: {', '.join(SAMPLES)} (default: en)")
    parser.add_argument("--mode", choices=["favorites", "explore"], help="Suggest mode (default: plain Suggest)")
    parser.add_argument("--draft", action="store_true", help="stop each run after the draft")
    parser.add_argument("--note", default="", help="what this prompt version changes, kept in the history")
    parser.add_argument("--history", action="store_true", help="list earlier tests and exit")
    args = parser.parse_args(argv)
    args.samples = [s.strip() for s in args.samples.split(",") if s.strip()]
    unknown = [s for s in args.samples if s not in SAMPLES]
    if unknown:
        parser.error(f"unknown sample: {', '.join(unknown)}")
    return args


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.history:
        print("\n".join(history_lines(load_history())))
        return 0
    llm.OLLAMA_BASE_URL = args.url  # llm reads it on every call, so every persona uses this server
    if not await llm.check_llm_availability():
        print(f"Ollama isn't reachable at {args.url}. See docs/SETUPALL.md, BONUS C.")
        return 1
    mode, prompt = args.mode or "plain", prompt_id()
    header = (
        f"Prompt {prompt} · commit {_commit()} · {llm.OLLAMA_MODEL} at {args.url} · mode {mode} · "
        f"{args.runs} runs per sample" + (" · draft only" if args.draft else "") + (f' · "{args.note}"' if args.note else "")
    )
    print(header, flush=True)
    records, prompts = await run(args.samples, args.runs, args.mode, args.draft)
    results = stage_results(records)
    report = summarize(records) + "\n\n" + "\n".join(compare(results, load_history(), mode))
    log = save_log(records, prompts, header, report)
    if results:
        entry = {
            "date": f"{datetime.now():%Y-%m-%d %H:%M}", "prompt": prompt, "commit": _commit(), "mode": mode,
            "draft_only": args.draft, "runs": args.runs, "note": args.note, "log": log.name, "results": results,
        }
        with HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print("\n" + report)
    print(f"\nReplies and prompts saved to {log}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Turkish names on a Windows console
    sys.exit(asyncio.run(main()))
