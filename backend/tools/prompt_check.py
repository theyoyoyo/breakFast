"""
Prompt test — runs the real suggestion pipeline against an Ollama server and scores
every reply in code, so a prompt change gets a before and after number (#116).

Run from backend/, with the server's Ollama reachable (docs/SETUPALL.md, BONUS C):
    python -m tools.prompt_check --url http://100.x.x.x:11434
    python -m tools.prompt_check --runs 5 --samples tr --draft

Each run is one Suggest press for a sample user (tools/prompt_samples.py). Both the
draft and the final reply are scored; --draft stops after the draft. Nothing touches
the database. The replies are saved to tools/runs/ (git-ignored).
"""

import argparse
import asyncio
import subprocess
import sys
import time
from collections import Counter
from contextlib import aclosing
from datetime import datetime
from pathlib import Path

from models.units import units_for
from routers.chat import SUGGEST_TEMPERATURES
from services import llm
# The fridge check's own word matching, used one way round for prepared items
from services.fridge import _contains, _is_water, _tokens, find_missing_ingredients
from services.pipeline import run_suggestion_pipeline
from tools.prompt_samples import SAMPLES
from utils import extract_json_block

RUNS_DIR = Path(__file__).parent / "runs"

# What the Suggest button sends per mode (frontend ChatInterface.jsx, handleSuggest)
SUGGEST_MESSAGES = {
    None: "Suggest Breakfast",
    "favorites": "Suggest breakfast from my favorite meals",
    "explore": "Suggest a different breakfast from world cuisines",
}

STAGES = ("draft", "final")
PROBLEMS = ("missing", "prepared", "units")


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
    """Units of simple items and dish ingredients that aren't in the reply language's list."""
    allowed = {u.lower() for u in units_for(language)}
    found = []
    for item in meal.get("menu") or []:
        if not isinstance(item, dict):
            continue
        for row in item.get("ingredients") or [item]:
            unit = row.get("unit") if isinstance(row, dict) else None
            if isinstance(unit, str) and unit.strip() and unit.strip().lower() not in allowed and unit not in found:
                found.append(unit)
    return found


def check_reply(text: str, sample: dict) -> dict:
    """Score one reply: does its meal JSON parse, and what's wrong with the meal."""
    meal = extract_json_block(text or "")
    if not isinstance(meal, dict) or not isinstance(meal.get("menu"), list):
        return {"json": False, "missing": [], "prepared": [], "units": []}
    missing = find_missing_ingredients(meal, sample["ingredients"])
    return {
        "json": True,
        "missing": missing,
        # A simple item that isn't in the fridge at all counts once, as missing
        "prepared": [n for n in prepared_items(meal, sample["ingredients"]) if n not in missing],
        "units": off_list_units(meal, sample["language"]),
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
    pipeline = run_suggestion_pipeline(
        context=sample,
        user_message=SUGGEST_MESSAGES[mode],
        mode=mode,
        temperature=SUGGEST_TEMPERATURES.get(mode),
    )
    async with aclosing(pipeline) as events:
        async for event in events:
            if event["type"] == "draft":
                replies["draft"] = event["content"]
                if draft_only:
                    break
            elif event["type"] == "done":
                replies["final"] = event["content"]
    return replies


async def run(samples: list[str], runs: int, mode: str | None, draft_only: bool) -> list[dict]:
    """Every run for every sample, one at a time (they share the server's GPU)."""
    records = []
    for key in samples:
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
    return records


# ── Report ──────────────────────────────────────────────────────────────────

_COLUMNS = [
    ("Sample", "<7"), ("Stage", "<7"), ("Runs", ">5"), ("JSON", ">6"), ("Clean", ">7"),
    ("Missing", ">9"), ("Prepared", ">10"), ("Units", ">7"), ("Errors", ">8"), ("Avg s", ">7"),
]


def _row(values) -> str:
    return "".join(f"{v:{spec}}" for v, (_, spec) in zip(values, _COLUMNS))


def summarize(records: list[dict]) -> str:
    """A row per sample and stage (problem columns count replies), then the top offenders."""
    lines = [_row(name for name, _ in _COLUMNS)]
    notes = []
    for key in dict.fromkeys(r["sample"] for r in records):
        runs = [r for r in records if r["sample"] == key]
        errors = sum(1 for r in runs if r["error"])
        avg = round(sum(r["seconds"] for r in runs) / len(runs))
        for stage in STAGES:
            scored = [r["scores"][stage] for r in runs if stage in r["scores"]]
            if not scored:
                continue
            problems = [sum(1 for s in scored if s[p]) for p in PROBLEMS]
            clean = sum(1 for s in scored if is_clean(s))
            lines.append(_row([key, stage, len(runs), sum(1 for s in scored if s["json"]), clean, *problems, errors, avg]))
            for p in PROBLEMS:
                top = Counter(name for s in scored for name in s[p]).most_common(5)
                if top:
                    notes.append(f"{key} {stage} {p}: " + ", ".join(f"{name} ×{n}" for name, n in top))
    return "\n".join(lines + ([""] + notes if notes else []))


def _commit() -> str:
    """Short commit of the prompts under test, marked when there are uncommitted changes."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return sha.stdout.strip() + (" + uncommitted changes" if dirty.stdout.strip() else "")


def save_log(records: list[dict], header: str, summary: str) -> Path:
    """Write the summary and every reply to a Markdown file in tools/runs/."""
    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.md"
    out = ["# Prompt test", "", header, "", "```", summary, "```"]
    for r in records:
        out += ["", f"## {r['sample']} · run {r['run']} · {r['seconds']:.0f} s"]
        if r["error"]:
            out += ["", f"**Error:** {r['error']}"]
        for stage, text in r["replies"].items():
            out += ["", f"### {stage.capitalize()}: {describe(r['scores'][stage])}", "", "````text", text, "````"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score the suggestion prompts against an Ollama server.")
    parser.add_argument("--url", default=llm.OLLAMA_BASE_URL, help="Ollama address (default: OLLAMA_BASE_URL)")
    parser.add_argument("--runs", type=int, default=10, help="Suggest presses per sample (default: 10)")
    parser.add_argument("--samples", default=",".join(SAMPLES), help=f"comma-separated, from: {', '.join(SAMPLES)}")
    parser.add_argument("--mode", choices=["favorites", "explore"], help="Suggest mode (default: plain Suggest)")
    parser.add_argument("--draft", action="store_true", help="stop each run after the draft")
    args = parser.parse_args(argv)
    args.samples = [s.strip() for s in args.samples.split(",") if s.strip()]
    unknown = [s for s in args.samples if s not in SAMPLES]
    if unknown:
        parser.error(f"unknown sample: {', '.join(unknown)}")
    return args


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    llm.OLLAMA_BASE_URL = args.url  # llm reads it on every call, so every persona uses this server
    if not await llm.check_llm_availability():
        print(f"Ollama isn't reachable at {args.url}. See docs/SETUPALL.md, BONUS C.")
        return 1
    header = (
        f"Ollama {args.url} · model {llm.OLLAMA_MODEL} · commit {_commit()} · "
        f"mode {args.mode or 'plain'} · {args.runs} runs per sample" + (" · draft only" if args.draft else "")
    )
    print(header, flush=True)
    records = await run(args.samples, args.runs, args.mode, args.draft)
    summary = summarize(records)
    print("\n" + summary)
    print(f"\nReplies saved to {save_log(records, header, summary)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Turkish names on a Windows console
    sys.exit(asyncio.run(main()))
