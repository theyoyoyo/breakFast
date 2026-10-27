"""
Prompt test — runs the real prompts against an Ollama server and scores every reply
in code, so a prompt change gets a before and after number (#116).

Run from backend/, with the server's Ollama reachable (docs/SETUPALL.md, BONUS C):
    python -m tools.prompt_check --url http://100.x.x.x:11434 --note "what changed"
    python -m tools.prompt_check --samples en,tr --runs 3 --draft
    python -m tools.prompt_check --persona shopping --samples mixed,demo
    python -m tools.prompt_check --history

Personas, each run for a sample user (tools/prompt_samples.py):
- suggest (default): one Suggest press through the real draft → review → refine
  pipeline. The draft and the final reply are both scored; --draft stops after the
  draft (one model call instead of three).
- shopping: Suggest Shopping, then Suggest More, as the Fridge tab sends them, with
  the same prompt, reply schema and code dedupe.
Nothing touches the database. Every test is kept locally in tools/runs/ (git-ignored): a log with the
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

from models.units import unknown_units
from routers.chat import SUGGEST_TEMPERATURES
from services import llm, pipeline
# The fridge check's own word matching, the other way round, to tell renamed items from missing ones
from services.fridge import _contains, _tokens, find_missing_ingredients, same_name
from services.personas.shopping import build_shopping_prompt
from services.shopping import SUGGESTIONS_SCHEMA, new_suggestions, parse_suggestions
from tools.prompt_samples import SAMPLES
from utils import extract_json_block

BACKEND = Path(__file__).resolve().parent.parent
RUNS_DIR = BACKEND / "tools" / "runs"
HISTORY = RUNS_DIR / "history.jsonl"

# Everything that shapes what the pipeline sends; their content is the prompt id
PROMPT_SOURCES = [
    "services/personas", "services/knowledge.py", "services/pipeline.py",
    "services/fridge.py", "services/shopping.py", "models/units.py", "tools/prompt_samples.py",
]

# What the Suggest button sends per mode (frontend ChatInterface.jsx, handleSuggest)
SUGGEST_MESSAGES = {
    None: "Suggest Breakfast",
    "favorites": "Suggest breakfast from my favorite meals",
    "explore": "Suggest a different breakfast from world cuisines",
}

# What Suggest Shopping asks, and at which temperature (routers/ingredients.py, get_shopping_suggestions)
SHOPPING_MESSAGE = "Generate shopping suggestions for me."
SHOPPING_TEMPERATURE = 0.6

# The stages each persona's runs score, and the problems its checks look for
PERSONAS = {
    "suggest": {"stages": ("draft", "final"), "problems": ("missing", "renamed", "units", "turkish")},
    "shopping": {"stages": ("suggest", "more"), "problems": ("dish", "vague", "repeat", "turkish")},
}
STAGES = PERSONAS["suggest"]["stages"]
_TURKISH_LETTERS = set("çğıöşüÇĞİÖŞÜ")

# Shopping names that aren't one specific product: alternatives, examples or filler words
_VAGUE = re.compile(r"[(/]|\be\.?g\b|\bor\b|\b(fresh|organic|seasonal|assorted|various)\b", re.IGNORECASE)
# Words that make a name a dish rather than a product (a heuristic for flagging; read the log)
_DISH_WORDS = {
    "menemen", "omelette", "omelet", "toast", "tost", "salad", "sandwich", "porridge", "smoothie",
    "pancake", "pancakes", "soup", "scrambled", "boiled", "fried", "poached", "parfait", "bowl",
}


# ── Checks ──────────────────────────────────────────────────────────────────

def renamed_items(names: list[str], inventory: list[dict]) -> list[str]:
    """Names the fridge check flags although they contain a fridge item: prepared, combined or
    renamed items ("Simit with tahini dipping sauce", "White cheese (peynir)", "Yogurt or milk")."""
    stock = [_tokens(i["name"]) for i in inventory if i.get("name")]
    return [n for n in names if any(_contains(_tokens(n), s) for s in stock)]


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


def _no_json(persona: str) -> dict:
    return {"json": False, "dishes": [], "issues": {p: [] for p in PERSONAS[persona]["problems"]}}


def check_reply(text: str, sample: dict) -> dict:
    """Score one suggestion reply: does its meal JSON parse, and what's wrong with the meal."""
    meal = extract_json_block(text or "")
    if not isinstance(meal, dict) or not isinstance(meal.get("menu"), list):
        return _no_json("suggest")
    flagged = find_missing_ingredients(meal, sample["ingredients"])
    renamed = renamed_items(flagged, sample["ingredients"])
    return {
        "json": True,
        # The menu's dish and item names, to count distinct menus across runs
        "dishes": sorted(str(i.get("name", "")).strip().lower() for i in meal["menu"] if isinstance(i, dict)),
        "issues": {
            "missing": [n for n in flagged if n not in renamed],
            "renamed": renamed,
            "units": unknown_units(meal, sample["language"]),
            "turkish": turkish_words(text, sample),
        },
    }


def looks_like_dish(name: str, sample: dict) -> bool:
    """A meal from the sample's history, a name "with" something, or a dish word (a heuristic)."""
    lowered = name.lower()
    meals = [m["meal_name"] for m in sample.get("history") or []]
    return (
        " with " in f" {lowered} "
        or bool(set(re.findall(r"\w+", lowered)) & _DISH_WORDS)
        or any(same_name(name, meal) for meal in meals)
    )


def check_shopping(text: str, sample: dict, shown: list[str]) -> tuple[dict, list[str]]:
    """Score one shopping reply and return the names the code dedupe keeps (what the user sees)."""
    items = parse_suggestions(text)
    if items is None:
        return _no_json("shopping"), []
    names = [i["name"] for i in items]
    known = [i["name"] for i in sample["ingredients"]] + sample["shopping_list"] + sample["avoid_list"] + shown
    kept = [i["name"] for i in new_suggestions(items, known)]
    return {
        "json": True,
        "dishes": sorted(n.lower() for n in kept),
        "issues": {
            "dish": [n for n in names if looks_like_dish(n, sample)],
            "vague": [n for n in names if _VAGUE.search(n)],
            # In the fridge, on the list, avoided or shown before: the code dedupe drops these
            "repeat": [n for n in names if n not in kept],
            "turkish": turkish_words(text, sample),
        },
        "note": f"{len(kept)} of {len(names)} kept",
    }, kept


def score_shopping(replies: dict, sample: dict) -> dict:
    """Score Suggest Shopping, then Suggest More against what the first one showed."""
    scores, shown = {}, []
    for stage in PERSONAS["shopping"]["stages"]:
        if stage in replies:
            scores[stage], kept = check_shopping(replies[stage], sample, shown)
            shown += kept
    return scores


def is_clean(result: dict) -> bool:
    return result["json"] and not any(result["issues"].values())


def describe(result: dict) -> str:
    """One line for a scored reply: "clean", "no JSON" or its problems."""
    if not result["json"]:
        return "no JSON"
    text = "; ".join(f"{p}: {', '.join(names)}" for p, names in result["issues"].items() if names) or "clean"
    return f"{text} ({result['note']})" if result.get("note") else text


# ── Runs ────────────────────────────────────────────────────────────────────

async def suggest_once(sample: dict, mode: str | None, draft_only: bool) -> dict:
    """One Suggest press through the real pipeline: {"draft": text, "review": feedback, "final": text}."""
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
            elif event["type"] == "review":
                replies["review"] = event["content"]
            elif event["type"] == "done":
                replies["final"] = event["content"]
    return replies


def shopping_prompt(sample: dict, shown: list[str]) -> str:
    """The shopping system prompt, built the way routers/ingredients.py builds it."""
    return build_shopping_prompt(
        ingredient_inventory=sample["ingredients"],
        recent_meal_history=sample["history"],
        user_preferences=sample["preferences"],
        stated_habits=sample["stated_habits"],
        inferred_habits=sample["inferred_habits"],
        health_rules=sample["health_rules"],
        user_profile=sample["user_profile"],
        supplements=sample["supplements"],
        avoid_list=sample["avoid_list"],
        exclude_names=shown,
        shopping_list=sample["shopping_list"],
        favorites=sample["favorites"],
        ratings=sample["ratings"],
        language=sample["language"],
        country=sample.get("country"),
    )


async def shop_once(sample: dict, sent: dict) -> dict:
    """Suggest Shopping, then Suggest More with what it showed: {"suggest": reply, "more": reply}.
    The endpoint's one retry after an all-repeat reply is left out; repeats are scored instead."""
    replies, shown = {}, []
    known = [i["name"] for i in sample["ingredients"]] + sample["shopping_list"] + sample["avoid_list"]
    for stage in PERSONAS["shopping"]["stages"]:
        prompt = shopping_prompt(sample, shown)
        sent.setdefault(prompt, None)
        replies[stage] = await llm.chat_json(
            system_prompt=prompt,
            messages=[{"role": "user", "content": SHOPPING_MESSAGE}],
            schema=SUGGESTIONS_SCHEMA,
            temperature=SHOPPING_TEMPERATURE,
        )
        shown += [i["name"] for i in new_suggestions(parse_suggestions(replies[stage]) or [], known + shown)]
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


async def run(
    samples: list[str], runs: int, mode: str | None, draft_only: bool, persona: str = "suggest",
) -> tuple[list[dict], dict]:
    """Every run for every sample, one at a time (they share the server's GPU), and the prompts sent."""
    records, prompts = [], {}
    for key in samples:
        sample, sent = SAMPLES[key], {}
        with recording_prompts(sent):
            for i in range(1, runs + 1):
                start = time.monotonic()
                try:
                    if persona == "shopping":
                        replies = await shop_once(sample, sent)
                    else:
                        replies = await suggest_once(sample, mode, draft_only)
                    error = None
                except Exception as e:  # keep going; the summary counts errors
                    replies, error = {}, f"{type(e).__name__}: {e}"
                if persona == "shopping":
                    scores = score_shopping(replies, sample)
                else:
                    scores = {s: check_reply(replies[s], sample) for s in STAGES if s in replies}
                record = {
                    "sample": key,
                    "run": i,
                    "seconds": time.monotonic() - start,
                    "error": error,
                    "replies": replies,
                    "scores": scores,
                }
                records.append(record)
                outcome = error or "  |  ".join(f"{s}: {describe(r)}" for s, r in record["scores"].items())
                if replies.get("final") is not None and replies["final"] == replies.get("draft"):
                    outcome += " (draft kept)"
                print(f"{key:<4}{i:>3}/{runs}  {record['seconds']:>4.0f} s  {outcome}", flush=True)
        prompts[key] = list(sent)
    return records, prompts


# ── Report ──────────────────────────────────────────────────────────────────

def _columns(persona: str) -> list[tuple[str, str]]:
    problems = [(p.capitalize(), f">{max(len(p) + 3, 7)}") for p in PERSONAS[persona]["problems"]]
    return [
        ("Sample", "<8"), ("Stage", "<9"), ("Runs", ">5"), ("JSON", ">6"), ("Clean", ">7"), ("Distinct", ">10"),
        *problems, ("Errors", ">8"), ("Avg s", ">7"),
    ]


def _row(values, columns: list[tuple[str, str]]) -> str:
    return "".join(f"{v:{spec}}" for v, (_, spec) in zip(values, columns))


def _groups(records: list[dict], persona: str = "suggest"):
    """(sample, stage, runs, scored replies) for every sample and stage that has replies."""
    for key in dict.fromkeys(r["sample"] for r in records):
        runs = [r for r in records if r["sample"] == key]
        for stage in PERSONAS[persona]["stages"]:
            scored = [r["scores"][stage] for r in runs if stage in r["scores"]]
            if scored:
                yield key, stage, runs, scored


def stage_results(records: list[dict], persona: str = "suggest") -> dict[str, dict]:
    """Clean replies and distinct menus (or lists) per sample and stage, e.g. {"en final": {...}}."""
    return {
        f"{key} {stage}": {
            "clean": sum(1 for s in scored if is_clean(s)),
            "scored": len(scored),
            "distinct": len({tuple(s["dishes"]) for s in scored if s["json"]}),
        }
        for key, stage, _, scored in _groups(records, persona)
    }


def summarize(records: list[dict], persona: str = "suggest") -> str:
    """A row per sample and stage (problem columns count replies), then the top offenders."""
    results, columns, problems = stage_results(records, persona), _columns(persona), PERSONAS[persona]["problems"]
    lines = [_row((name for name, _ in columns), columns)]
    notes = []
    for key, stage, runs, scored in _groups(records, persona):
        result = results[f"{key} {stage}"]
        errors = sum(1 for r in runs if r["error"])
        avg = round(sum(r["seconds"] for r in runs) / len(runs))
        counts = [sum(1 for s in scored if s["issues"][p]) for p in problems]
        json_ok = sum(1 for s in scored if s["json"])
        lines.append(_row([key, stage, len(runs), json_ok, result["clean"], result["distinct"], *counts, errors, avg], columns))
        for p in problems:
            top = Counter(name for s in scored for name in s["issues"][p]).most_common(5)
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


def compare(results: dict, history: list[dict], mode: str, persona: str = "suggest") -> list[str]:
    """This test against the best earlier one per sample and stage, same persona and mode: ▲ better, ▼ worse."""
    lines = []
    for key, now in results.items():
        text = f"{key}: {now['clean']}/{now['scored']} clean, {now['distinct']} distinct"
        earlier = [
            e for e in history
            if e.get("persona", "suggest") == persona and e.get("mode") == mode and key in e.get("results", {})
        ]
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
        lines.append(f"{e['date']}  {e['prompt']}  {e.get('persona', 'suggest'):<9} {e['mode']:<9}  {results}{note}")
    return lines or ["No tests yet."]


def save_log(records: list[dict], prompts: dict, header: str, report: str, diff: str) -> Path:
    """Write the report, uncommitted prompt changes, every reply and the prompts sent to tools/runs/."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.md"
    out = ["# Prompt test", "", header, "", "```", report, "```"]
    if diff:
        out += ["", "## Uncommitted prompt changes", "", "```diff", diff, "```"]
    for r in records:
        out += ["", f"## {r['sample']} · run {r['run']} · {r['seconds']:.0f} s"]
        if r["error"]:
            out += ["", f"**Error:** {r['error']}"]
        for stage, text in r["replies"].items():
            title = f"{stage.capitalize()}: {describe(r['scores'][stage])}" if stage in r["scores"] else "Review feedback"
            out += ["", f"### {title}", "", "````text", text, "````"]
    out += ["", "## Prompts sent"]
    for key, sent in prompts.items():
        for i, prompt in enumerate(sent, 1):
            out += ["", f"<details><summary>{key} · system prompt {i}</summary>", "", "````text", prompt, "````", "", "</details>"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score the suggestion and shopping prompts against an Ollama server.")
    parser.add_argument("--url", default=llm.OLLAMA_BASE_URL, help="Ollama address (default: OLLAMA_BASE_URL)")
    parser.add_argument("--runs", type=int, default=1, help="Suggest presses per sample (default: 1)")
    parser.add_argument("--samples", default="en", help=f"comma-separated, from: {', '.join(SAMPLES)} (default: en)")
    parser.add_argument("--persona", choices=list(PERSONAS), default="suggest", help="what to test (default: suggest)")
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
    # The code under test as it is now; later edits during the run don't belong to this test
    mode, prompt, commit = args.mode or "plain", prompt_id(), _commit()
    diff = _git("diff", "HEAD", "--", *PROMPT_SOURCES)
    header = (
        f"Prompt {prompt} · commit {commit} · {llm.OLLAMA_MODEL} at {args.url} · {args.persona} · mode {mode} · "
        f"{args.runs} runs per sample" + (" · draft only" if args.draft else "") + (f' · "{args.note}"' if args.note else "")
    )
    print(header, flush=True)
    records, prompts = await run(args.samples, args.runs, args.mode, args.draft, args.persona)
    results = stage_results(records, args.persona)
    report = summarize(records, args.persona) + "\n\n" + "\n".join(compare(results, load_history(), mode, args.persona))
    log = save_log(records, prompts, header, report, diff)
    if results:
        entry = {
            "date": f"{datetime.now():%Y-%m-%d %H:%M}", "prompt": prompt, "commit": commit,
            "persona": args.persona, "mode": mode,
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
