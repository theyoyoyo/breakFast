"""Build the model comparison page (#178) from the model test data in tools/runs/models/.

    python -m tools.compare_runs qwen3.5:4b --think off
    python -m tools.compare_runs qwen3.5:4b --think off --baseline qwen2.5:7b

It pairs the baseline's outputs with the candidate's by test, sample and run, and writes into
tools/runs/models/:
- compare_<pair>.html: one page with the blind A/B votes (Reveal shows which model was which and
  the tally) and every model tried, as charts per test and a table of samples by models;
- votes/<pair>__blind.json: the same pairs without the models or seconds, for Claude's blind votes;
- votes/<pair>__key.json: which model each pair's A is.
Votes saved as votes/<pair>__user.json (the page's download) and votes/<pair>__claude.json show on
the page after Reveal. See docs/MODEL_TESTS.md.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

from routers.scheduler import _build_plan, served_items
from tools.prompt_check import BASELINE_MODEL, MODELS_DIR, describe, is_clean, model_folder
from utils import extract_json_block

# The stages a test is judged on, in the order the page shows them
MAIN_STAGES = {
    "suggest": ("final",), "review": ("final",), "plan": ("plan",),
    "shopping": ("suggest", "more"), "chat": ("leave_out", "liked", "time", "allowed"),
}


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def model_outputs(folder: str) -> dict[str, dict]:
    """A model's outputs by test name, from its folder in tools/runs/models/."""
    return {p.stem: data for p in sorted((MODELS_DIR / folder).glob("*.json")) if (data := _load(p))}


def model_label(data: dict) -> str:
    think = data.get("think")
    return data["model"] + ("" if think is None else f" (think {'on' if think else 'off'})")


def _persona(test: str) -> str:
    return test.split("-")[0]


def _clean(record: dict, persona: str) -> bool:
    scores = record.get("scores") or {}
    stages = [s for s in MAIN_STAGES[persona] if s in scores]
    return not record.get("error") and bool(stages) and all(is_clean(scores[s]) for s in stages)


def _flags(record: dict, persona: str) -> list[str]:
    if record.get("error"):
        return [f"error: {record['error']}"]
    scores = record.get("scores") or {}
    return [f"{s}: {describe(scores[s])}" if len(MAIN_STAGES[persona]) > 1 else describe(scores[s])
            for s in MAIN_STAGES[persona] if s in scores]


def _meal_view(text: str | None) -> dict:
    """A reply with a meal block: its text before the block and the meal."""
    text = text or ""
    meal = extract_json_block(text)
    return {"text": re.split(r"```", text)[0].strip(), "meal": meal if isinstance(meal, dict) else None}


def output_view(record: dict, persona: str, sample: dict | None) -> dict:
    """What the page shows for one model's reply to a sample."""
    replies = record.get("replies") or {}
    view = {"flags": _flags(record, persona), "clean": _clean(record, persona), "seconds": round(record.get("seconds") or 0)}
    if persona in ("suggest", "review"):
        view |= {"kind": "meal", **_meal_view(replies.get("final")), "draft": replies.get("draft"), "review": replies.get("review")}
    elif persona == "plan":
        raw, text = extract_json_block(replies.get("plan") or ""), replies.get("plan") or ""
        if isinstance(raw, dict) and isinstance(raw.get("dishes"), list) and sample:
            try:  # the plan the app would show; the raw reply when code can't build one
                text = _build_plan(raw, sample["language"], sample["kitchen_appliances"], served_items(sample["menu"]))["formatted"]
            except (KeyError, TypeError, ValueError):
                pass
        view |= {"kind": "plan", "text": text}
    elif persona == "shopping":
        lists = []
        for stage in MAIN_STAGES["shopping"]:
            parsed = _load_text(replies.get(stage))
            items = parsed.get("items") if isinstance(parsed, dict) else None
            lists.append({"stage": stage, "items": items if isinstance(items, list) else [], "raw": None if items else replies.get(stage)})
        view |= {"kind": "shopping", "lists": lists}
    else:
        view |= {"kind": "chat", "replies": [replies.get(s) for s in MAIN_STAGES["chat"]]}
    return view


def _load_text(text: str | None):
    try:
        return json.loads(text or "")
    except json.JSONDecodeError:
        return None


def input_view(entry: dict | None, persona: str) -> dict:
    """What the page shows of a sample's input: the fridge and the user, the draft or menu, the chat."""
    if not entry:
        return {}
    data = entry.get("data") or {}
    view = {"language": data.get("language"), "mode": entry.get("mode")}
    if persona == "plan":
        return view | {"menu": {"menu_name": data.get("meal_name"), "menu": data.get("menu")}, "kitchen": data.get("kitchen_appliances")}
    view |= {
        "fridge": [i["name"] for i in data.get("ingredients") or [] if i.get("name")],
        "avoid": data.get("avoid_list") or [],
        "dislikes": [v for k, v in (data.get("preferences") or {}).items() if k.startswith("dislike:")],
        "health": [r.get("rule_text") or str(r) for r in data.get("health_rules") or []],
        "kitchen": data.get("kitchen_appliances"),
    }
    if persona == "review":
        view["draft"] = data.get("draft")
    chat = (entry.get("chat") or {}).get("chat") or []
    view["chat"] = [e["content"] if "content" in e else f"[Suggest press: {e['press'].get('menu_name', 'a menu')}]" for e in chat]
    return view


def pair_name(base: str, cand: str) -> str:
    return f"{base}__vs__{cand}"


def build_pairs(base: dict[str, dict], cand: dict[str, dict], name: str) -> tuple[list[dict], dict, list[str]]:
    """Pairs of the two models' replies by test, sample and run, each with its input; which side is A
    (seeded by the pair, so a rebuild keeps it); and what only one model has."""
    pairs, key, unpaired = [], {}, []
    for test in sorted(set(base) | set(cand)):
        if test not in base or test not in cand:
            unpaired.append(f"{test}: only {'the baseline' if test in base else 'the candidate'}")
            continue
        persona = _persona(test)
        inputs = (_load(MODELS_DIR / "inputs" / f"{test}.json") or {}).get("samples", {})
        theirs = {(r["sample"], r["run"]): r for r in cand[test]["records"]}
        for r in base[test]["records"]:
            other = theirs.pop((r["sample"], r["run"]), None)
            if other is None:
                unpaired.append(f"{test} {r['sample']} run {r['run']}: only the baseline")
                continue
            entry = inputs.get(r["sample"])
            sample = (entry or {}).get("data")
            pid = f"{test}|{r['sample']}|{r['run']}"
            a_is_base = random.Random(f"{name}|{pid}").random() < 0.5
            a, b = (r, other) if a_is_base else (other, r)
            key[pid] = "base" if a_is_base else "cand"
            pairs.append({
                "id": pid, "test": test, "persona": persona, "sample": r["sample"], "run": r["run"],
                "input": input_view(entry, persona),
                "A": output_view(a, persona, sample), "B": output_view(b, persona, sample),
            })
        unpaired += [f"{test} {s} run {n}: only the candidate" for s, n in theirs]
    return pairs, key, unpaired


def overview(folders: list[str], base_folder: str) -> dict:
    """Every model tried: per test its clean share, average seconds, errors and GPU share, a mark when its
    prompt version isn't the baseline's, and each sample's flags."""
    base = model_outputs(base_folder)
    models = []
    for folder in folders:
        outputs = model_outputs(folder)
        if not outputs:
            continue
        tests = {}
        for test, data in outputs.items():
            persona, records = _persona(test), data["records"]
            tests[test] = {
                "clean": sum(_clean(r, persona) for r in records), "count": len(records),
                "seconds": round(sum(r.get("seconds") or 0 for r in records) / max(len(records), 1)),
                "errors": sum(bool(r.get("error")) for r in records), "gpu": data.get("gpu"),
                "other_prompt": test in base and data.get("prompt") != base[test].get("prompt"),
                "samples": {f"{r['sample']} · {r['run']}" if data.get("runs", 1) > 1 else r["sample"]:
                            {"clean": _clean(r, persona), "flags": _flags(r, persona), "seconds": round(r.get("seconds") or 0)}
                            for r in records},
            }
        label = model_label(next(iter(outputs.values())))
        models.append({"folder": folder, "label": label, "baseline": folder == base_folder, "tests": tests})
    return {"models": models}


def _votes(name: str) -> dict:
    """Votes saved for a pair: the user's download and Claude's blind votes."""
    found = {}
    for who in ("user", "claude"):
        data = _load(MODELS_DIR / "votes" / f"{name}__{who}.json")
        if data:
            found[who] = data.get("votes", data)
    return found


def build_page(base_folder: str, cand_folder: str) -> tuple[Path, Path, list[str]]:
    """Write the page, the blind pairs and the key; return the page, the blind file and what isn't paired."""
    base, cand = model_outputs(base_folder), model_outputs(cand_folder)
    if not base or not cand:
        missing = base_folder if not base else cand_folder
        raise SystemExit(f"No model test data in {MODELS_DIR / missing}. Run tools.model_battery first.")
    name = pair_name(base_folder, cand_folder)
    pairs, key, unpaired = build_pairs(base, cand, name)
    folders = sorted(p.name for p in MODELS_DIR.iterdir() if p.is_dir() and p.name not in ("inputs", "votes"))
    data = {
        "pair": name, "pairs": pairs, "unpaired": unpaired, "overview": overview(folders, base_folder),
        "reveal": {"base": model_label(next(iter(base.values()))), "cand": model_label(next(iter(cand.values()))),
                   "key": key, "votes": _votes(name)},
    }
    votes_dir = MODELS_DIR / "votes"
    votes_dir.mkdir(parents=True, exist_ok=True)
    blind = votes_dir / f"{name}__blind.json"
    blind_pairs = [{**p, "A": {k: v for k, v in p["A"].items() if k != "seconds"},
                    "B": {k: v for k, v in p["B"].items() if k != "seconds"}} for p in pairs]
    blind.write_text(json.dumps({"pairs": blind_pairs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (votes_dir / f"{name}__key.json").write_text(json.dumps(data["reveal"]["key"], indent=1) + "\n", encoding="utf-8")
    page = MODELS_DIR / f"compare_{name}.html"
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page.write_text(PAGE.replace("__DATA__", payload), encoding="utf-8")
    return page, blind, unpaired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the blind model comparison page from tools/runs/models/.")
    parser.add_argument("model", help="the candidate's Ollama tag, e.g. qwen3.5:4b")
    parser.add_argument("--think", choices=["on", "off"], help="the candidate's think setting (default: none sent)")
    parser.add_argument("--baseline", default=BASELINE_MODEL, help=f"the model to compare with (default: {BASELINE_MODEL})")
    parser.add_argument("--baseline-think", choices=["on", "off"], help="the baseline's think setting")
    args = parser.parse_args(argv)
    think = {"on": True, "off": False}
    page, blind, unpaired = build_page(
        model_folder(args.baseline, think.get(args.baseline_think)), model_folder(args.model, think.get(args.think)),
    )
    for line in unpaired:
        print(f"Not paired: {line}")
    print(f"Page: {page}\nBlind pairs: {blind}")
    return 0


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model comparison</title>
<style>
:root { --bg:#fbfaf8; --card:#fff; --ink:#1d1b18; --muted:#6b655d; --line:#e6e1da; --accent:#c2571b;
  --soft:#f6efe8; --good:#2f7a3d; --bad:#b3261e; --warn:#8a6d00; --chip:#efebe5; }
@media (prefers-color-scheme: dark) { :root { --bg:#161513; --card:#201e1b; --ink:#ece8e2; --muted:#a39d94;
  --line:#34312c; --accent:#f08a4b; --soft:#2b241e; --good:#7cc68a; --bad:#f2918a; --warn:#e3c35a; --chip:#2c2925; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
header { position:sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--line); padding:10px 16px;
  display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; }
h1 { font-size:18px; margin:0 8px 0 0; }
main { max-width:1200px; margin:0 auto; padding:16px; }
button, select { font:inherit; border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:8px; padding:6px 10px; cursor:pointer; }
button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
button.on { background:var(--accent); border-color:var(--accent); color:#fff; }
.muted { color:var(--muted); }
.tabs { display:flex; gap:6px; margin:4px 0 16px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; margin:0 0 18px; overflow:hidden; }
.card h2 { font-size:15px; margin:0; padding:10px 14px; background:var(--soft); border-bottom:1px solid var(--line);
  display:flex; gap:10px; flex-wrap:wrap; align-items:baseline; }
.input { padding:10px 14px; border-bottom:1px solid var(--line); font-size:13.5px; }
.input b { font-weight:600; }
.sides { display:grid; grid-template-columns:1fr 1fr; }
.side { padding:12px 14px; min-width:0; }
.side + .side { border-left:1px solid var(--line); }
@media (max-width:760px) { .sides { grid-template-columns:1fr; } .side + .side { border-left:0; border-top:1px solid var(--line); } }
.side h3 { margin:0 0 6px; font-size:14px; display:flex; justify-content:space-between; gap:8px; }
.flag { font-size:12.5px; color:var(--warn); margin:4px 0; word-break:break-word; }
.flag.ok { color:var(--good); }
.meal-name { font-weight:650; }
ul.menu { margin:6px 0; padding-left:18px; }
ul.menu li { margin:3px 0; }
.ing { color:var(--muted); font-size:13.5px; }
.method { font-size:13px; color:var(--muted); font-style:italic; }
pre { white-space:pre-wrap; word-break:break-word; font:12.5px/1.45 ui-monospace, Consolas, monospace; margin:6px 0;
  background:var(--chip); padding:8px; border-radius:8px; }
details summary { cursor:pointer; color:var(--muted); font-size:13px; }
.vote { display:flex; flex-wrap:wrap; gap:6px; padding:10px 14px; border-top:1px solid var(--line); align-items:center; }
.vote input { flex:1; min-width:160px; font:inherit; border:1px solid var(--line); border-radius:8px; padding:6px 8px;
  background:var(--card); color:var(--ink); }
.reveal { padding:8px 14px; border-top:1px dashed var(--line); font-size:13.5px; }
.chips span { display:inline-block; background:var(--chip); border-radius:999px; padding:1px 8px; margin:2px 3px 2px 0; font-size:12.5px; }
.turn { margin:6px 0; }
.turn .who { font-size:12px; color:var(--muted); }
table { border-collapse:collapse; width:100%; font-size:13px; }
th, td { border:1px solid var(--line); padding:5px 7px; text-align:left; vertical-align:top; }
th { background:var(--soft); }
td.ok { color:var(--good); }
td.bad { color:var(--warn); }
.table-wrap { overflow-x:auto; margin:8px 0 22px; }
.chart { margin:6px 0 4px; }
.legend { font-size:12.5px; color:var(--muted); }
.tally { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin:0 0 18px; }
</style>
</head>
<body>
<header>
  <h1>Model comparison</h1>
  <span id="progress" class="muted"></span>
  <select id="filter" aria-label="Test"></select>
  <button id="revealBtn" class="primary">Reveal</button>
  <button id="download">Download votes</button>
</header>
<main>
  <div class="tabs"><button id="tabVotes" class="on">Blind A/B</button><button id="tabAll">All models</button></div>
  <section id="votes"></section>
  <section id="all" hidden></section>
</main>
<script>
const DATA = __DATA__;
const store = (() => { try { return window.localStorage; } catch (e) { return null; } })();
const KEY = "bf-votes-" + DATA.pair;
let votes = {};
try { votes = JSON.parse((store && store.getItem(KEY)) || "{}"); } catch (e) { votes = {}; }
let revealed = false;
const save = () => { try { store && store.setItem(KEY, JSON.stringify(votes)); } catch (e) {} };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const el = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstChild; };

function amount(x) { return x.amount != null ? `${x.amount} ${x.unit || ""}`.trim() : ""; }
function mealHtml(meal) {
  if (!meal || !Array.isArray(meal.menu)) return '<p class="flag">No meal</p>';
  const items = meal.menu.map(item => {
    const ings = (item.ingredients || []);
    if (!ings.length) {
      return `<li>${esc(item.name)} <span class="ing">${esc(amount(item))}</span>${item.method ? `<div class="method">${esc(item.method)}</div>` : ""}</li>`;
    }
    const list = ings.map(i => `${esc(i.name)} ${esc(amount(i))}${i.prep ? ` (${esc(i.prep)})` : ""}${i.replaces ? ` ✱ instead of ${esc(i.replaces)}` : ""}`).join(", ");
    return `<li><b>${esc(item.name)}</b>: <span class="ing">${list}</span>${item.method ? `<div class="method">${esc(item.method)}</div>` : ""}</li>`;
  }).join("");
  return `<div><span class="meal-name">${esc(meal.menu_name || "")}</span>${meal.prep_time_min ? ` <span class="muted">· ${esc(meal.prep_time_min)} min</span>` : ""}</div><ul class="menu">${items}</ul>`;
}
function outputHtml(o, input) {
  let body = "";
  if (o.kind === "meal") {
    body = (o.text ? `<p>${esc(o.text)}</p>` : "") + mealHtml(o.meal)
      + (o.draft ? `<details><summary>Draft and review</summary><pre>${esc(o.draft)}</pre>${o.review ? `<pre>${esc(o.review)}</pre>` : ""}</details>` : "");
  } else if (o.kind === "plan") {
    body = `<pre>${esc(o.text)}</pre>`;
  } else if (o.kind === "shopping") {
    body = o.lists.map(l => `<div class="muted">${l.stage === "more" ? "Suggest More" : "Suggest Shopping"}</div>`
      + (l.items.length ? `<ul class="menu">${l.items.map(i => `<li>${esc(i.name)} <span class="ing">${esc(i.reason || "")}</span></li>`).join("")}</ul>` : `<pre>${esc(l.raw || "no items")}</pre>`)).join("");
  } else {
    body = (input.chat || []).filter(t => !t.startsWith("[")).map((t, i) =>
      `<div class="turn"><div class="who">User</div>${esc(t)}<div class="who">Reply</div>${esc(o.replies[i] || "—")}</div>`).join("");
  }
  const flags = o.flags.map(f => `<div class="flag${f === "clean" ? " ok" : ""}">${esc(f)}</div>`).join("");
  return flags + body;
}
function inputHtml(p) {
  const i = p.input, parts = [];
  parts.push(`<span class="muted">${esc(i.language || "")}${i.mode ? " · " + esc(i.mode) + " mode" : ""}</span>`);
  if (i.fridge) parts.push(`<div><b>Fridge:</b> <span class="chips">${i.fridge.map(f => `<span>${esc(f)}</span>`).join("")}</span></div>`);
  if (i.avoid && i.avoid.length) parts.push(`<div><b>Avoid:</b> ${esc(i.avoid.join(", "))}</div>`);
  if (i.dislikes && i.dislikes.length) parts.push(`<div><b>Dislikes:</b> ${esc(i.dislikes.join(", "))}</div>`);
  if (i.health && i.health.length) parts.push(`<div><b>Health:</b> ${esc(i.health.join("; "))}</div>`);
  if (i.kitchen) parts.push(`<div><b>Kitchen:</b> ${esc(i.kitchen.join(", "))}</div>`);
  if (i.menu) parts.push(`<div><b>Menu:</b></div>` + mealHtml(i.menu));
  if (i.draft) parts.push(`<details><summary>Draft sent to the reviser</summary>${mealHtml(i.draft)}</details>`);
  if (p.persona !== "chat" && i.chat && i.chat.length) parts.push(`<div><b>Chat before the press:</b><ol>${i.chat.map(t => `<li>${esc(t)}</li>`).join("")}</ol></div>`);
  return `<details${p.persona === "plan" ? " open" : ""}><summary>Input</summary>${parts.join("")}</details>`;
}
function label(side, pid) {
  const k = DATA.reveal.key[pid];
  const base = DATA.reveal.base, cand = DATA.reveal.cand;
  return side === "A" ? (k === "base" ? base : cand) : (k === "base" ? cand : base);
}
const VOTE_TEXT = { A: "A better", tie: "Both equally good", B: "B better" };
function card(p) {
  const v = votes[p.id] || {};
  const claude = (DATA.reveal.votes.claude || {})[p.id];
  const node = el(`<article class="card" data-test="${esc(p.test)}">
    <h2><span>${esc(p.test)}</span><span>${esc(p.sample)}${p.run > 1 ? " · run " + p.run : ""}</span></h2>
    <div class="input">${inputHtml(p)}</div>
    <div class="sides">${["A", "B"].map(s => `<div class="side"><h3><span>${s}</span><span class="muted">${p[s].seconds} s</span></h3>${outputHtml(p[s], p.input)}</div>`).join("")}</div>
    <div class="vote">${["A", "tie", "B"].map(c => `<button data-v="${c}" class="${v.vote === c ? "on" : ""}">${VOTE_TEXT[c]}</button>`).join("")}
      <input placeholder="Note (optional)" value="${esc(v.note || "")}"></div>
    ${revealed ? `<div class="reveal">A: <b>${esc(label("A", p.id))}</b> · B: <b>${esc(label("B", p.id))}</b>${claude ? `<br>Claude: ${esc(VOTE_TEXT[claude.vote] || claude.vote)} — ${esc(claude.reason || "")}` : ""}</div>` : ""}
  </article>`);
  node.querySelectorAll("button[data-v]").forEach(b => b.onclick = () => {
    votes[p.id] = { ...(votes[p.id] || {}), vote: b.dataset.v }; save();
    node.querySelectorAll("button[data-v]").forEach(x => x.classList.toggle("on", x === b)); progress();
  });
  node.querySelector("input").oninput = e => { votes[p.id] = { ...(votes[p.id] || {}), note: e.target.value }; save(); };
  return node;
}
function progress() {
  const done = DATA.pairs.filter(p => votes[p.id] && votes[p.id].vote).length;
  document.getElementById("progress").textContent = `${done} / ${DATA.pairs.length} voted`;
}
function tally(source) {
  const rows = {};
  for (const p of DATA.pairs) {
    const v = (source[p.id] || {}).vote; if (!v) continue;
    const r = rows[p.test] = rows[p.test] || { base: 0, cand: 0, tie: 0 };
    if (v === "tie") r.tie++; else r[(v === "A") === (DATA.reveal.key[p.id] === "base") ? "base" : "cand"]++;
  }
  return rows;
}
function tallyHtml() {
  const mine = tally(votes), claude = tally(DATA.reveal.votes.claude || {});
  const tests = [...new Set(DATA.pairs.map(p => p.test))];
  const agree = DATA.pairs.filter(p => votes[p.id] && (DATA.reveal.votes.claude || {})[p.id]);
  const same = agree.filter(p => votes[p.id].vote === DATA.reveal.votes.claude[p.id].vote).length;
  const cell = r => r ? `${r.base} / ${r.cand} / ${r.tie}` : "—";
  return `<div class="tally"><b>Tally</b> <span class="muted">(${esc(DATA.reveal.base)} wins / ${esc(DATA.reveal.cand)} wins / equal)</span>
    <div class="table-wrap"><table><tr><th>Test</th><th>You</th><th>Claude</th></tr>
    ${tests.map(t => `<tr><td>${esc(t)}</td><td>${cell(mine[t])}</td><td>${cell(claude[t])}</td></tr>`).join("")}</table></div>
    ${agree.length ? `<div class="muted">You and Claude agree on ${same} of ${agree.length} pairs voted by both.</div>` : ""}</div>`;
}
function renderVotes() {
  const box = document.getElementById("votes"); box.innerHTML = "";
  const want = document.getElementById("filter").value;
  if (revealed) box.appendChild(el(tallyHtml()));
  if (DATA.unpaired.length) box.appendChild(el(`<details class="muted"><summary>Not paired (${DATA.unpaired.length})</summary><ul>${DATA.unpaired.map(u => `<li>${esc(u)}</li>`).join("")}</ul></details>`));
  DATA.pairs.filter(p => !want || p.test === want).forEach(p => box.appendChild(card(p)));
  progress();
}
function bars(values, max, fmt) {
  const w = 520, row = 22, h = values.length * row + 6;
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" width="100%" style="max-width:${w}px" role="img">${values.map((v, i) => {
    const bw = max ? Math.max(2, (w - 230) * v.value / max) : 2;
    return `<text x="0" y="${i * row + 15}" font-size="12" fill="currentColor">${esc(v.label)}</text>
      <rect x="180" y="${i * row + 4}" width="${bw}" height="14" rx="3" fill="${v.mark ? "var(--muted)" : "var(--accent)"}"></rect>
      <text x="${186 + bw}" y="${i * row + 15}" font-size="12" fill="currentColor">${esc(fmt(v))}</text>`;
  }).join("")}</svg>`;
}
function renderAll() {
  const box = document.getElementById("all"), models = DATA.overview.models;
  if (!revealed) { box.innerHTML = "<p>This tab names the models and their flags, so it opens after Reveal.</p>"; return; }
  const tests = [...new Set(models.flatMap(m => Object.keys(m.tests)))].sort();
  let html = `<p class="legend">Clean share of the judged stages per test, then average seconds per sample. A grey bar ran on another prompt version than the baseline, so it doesn't compare. GPU share is how much of the model Ollama held on the GPU.</p>`;
  for (const t of tests) {
    const rows = models.filter(m => m.tests[t]).map(m => ({ m, r: m.tests[t] }));
    html += `<h3>${esc(t)}</h3>`
      + bars(rows.map(({ m, r }) => ({ label: m.label + (m.baseline ? " ★" : ""), value: r.clean / Math.max(r.count, 1), mark: r.other_prompt, r })), 1,
             v => `${v.r.clean}/${v.r.count} clean${v.r.errors ? `, ${v.r.errors} errors` : ""}${v.r.gpu != null ? ` · GPU ${v.r.gpu}%` : ""}`)
      + bars(rows.map(({ m, r }) => ({ label: m.label, value: r.seconds, mark: r.other_prompt })), Math.max(...rows.map(x => x.r.seconds), 1), v => `${v.value} s`);
    const samples = [...new Set(rows.flatMap(x => Object.keys(x.r.samples)))];
    html += `<div class="table-wrap"><table><tr><th>Sample</th>${rows.map(x => `<th>${esc(x.m.label)}</th>`).join("")}</tr>${samples.map(s => `<tr><td>${esc(s)}</td>${rows.map(x => {
      const c = x.r.samples[s]; if (!c) return "<td>—</td>";
      return `<td class="${c.clean ? "ok" : "bad"}">${c.clean ? "✓" : esc(c.flags.join("; "))} <span class="muted">${c.seconds} s</span></td>`;
    }).join("")}</tr>`).join("")}</table></div>`;
  }
  box.innerHTML = models.length ? html : "<p>No model tests yet.</p>";
}
const filter = document.getElementById("filter");
filter.innerHTML = `<option value="">All tests</option>` + [...new Set(DATA.pairs.map(p => p.test))].map(t => `<option>${esc(t)}</option>`).join("");
filter.onchange = renderVotes;
document.getElementById("revealBtn").onclick = () => { revealed = !revealed; document.getElementById("revealBtn").textContent = revealed ? "Hide models" : "Reveal"; renderVotes(); renderAll(); };
document.getElementById("download").onclick = () => {
  const blob = new Blob([JSON.stringify({ pair: DATA.pair, votes }, null, 1)], { type: "application/json" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = DATA.pair + "__user.json"; a.click();
};
const tabs = { tabVotes: "votes", tabAll: "all" };
for (const [btn, sec] of Object.entries(tabs)) document.getElementById(btn).onclick = () => {
  for (const [b, s] of Object.entries(tabs)) { document.getElementById(b).classList.toggle("on", b === btn); document.getElementById(s).hidden = s !== sec; }
};
renderVotes(); renderAll();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
