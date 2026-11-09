"""The model comparison page builder (#178): pairs, the blind file, the overview."""

import json
from unittest.mock import patch

from tools.compare_runs import build_page, build_pairs, output_view, overview, pair_name
from tools.prompt_samples import PLAN_CASES

CLEAN = {"json": True, "issues": {"missing": []}}
MISSING = {"json": True, "issues": {"missing": ["Salmon"]}}


def _reply(name: str) -> str:
    meal = {"menu_name": name, "menu": [{"name": "Eggs", "amount": 2, "unit": "pcs", "ingredients": []}], "prep_time_min": 5}
    return f"{name} for you.\n\n```json\n{json.dumps(meal)}\n```"


def _record(sample: str, name: str, score: dict = CLEAN, run: int = 1, seconds: float = 10.0) -> dict:
    return {"sample": sample, "mode": None, "run": run, "seconds": seconds, "error": None,
            "replies": {"draft": _reply(name), "final": _reply(name)}, "scores": {"final": score}}


def _write(root, folder: str, model: str, records: list[dict], prompt: str = "aaaaaaa", think=None, test: str = "suggest"):
    path = root / folder / f"{test}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": model, "think": think, "prompt": prompt, "gpu": 100, "runs": 1, "records": records}))


def _inputs(root, test: str = "suggest"):
    path = root / "inputs" / f"{test}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"language": "en", "ingredients": [{"name": "Eggs"}], "avoid_list": [], "preferences": {}, "health_rules": []}
    path.write_text(json.dumps({"samples": {s: {"sample": s, "mode": None, "data": data, "chat": None} for s in ("en", "tr", "vegan")}}))


# Pairs match the two models' replies by test, sample and run; a seeded side order stays the same on a rebuild;
# a sample or test only one model has is listed as not paired
def test_pairs_by_test_and_sample(tmp_path):
    _inputs(tmp_path)
    _write(tmp_path, "base", "qwen2.5:7b", [_record("en", "Base en"), _record("tr", "Base tr")])
    _write(tmp_path, "cand", "qwen3.5:4b", [_record("en", "Cand en"), _record("vegan", "Cand vegan")], think=False)
    _write(tmp_path, "cand", "qwen3.5:4b", [_record("en", "Cand plan")], think=False, test="plan")
    with patch("tools.compare_runs.MODELS_DIR", tmp_path):
        from tools.compare_runs import model_outputs
        base, cand = model_outputs("base"), model_outputs("cand")
        pairs, key, unpaired = build_pairs(base, cand, "x")
        again = build_pairs(base, cand, "x")[1]
    assert [p["id"] for p in pairs] == ["suggest|en|1"] and key == again
    pair = pairs[0]
    names = {pair["A"]["meal"]["menu_name"], pair["B"]["meal"]["menu_name"]}
    assert names == {"Base en", "Cand en"}
    assert (pair["A"]["meal"]["menu_name"] == "Base en") == (key["suggest|en|1"] == "base")
    assert pair["input"]["fridge"] == ["Eggs"] and pair["A"]["text"].endswith("for you.")
    assert unpaired == ["plan: only the candidate", "suggest tr run 1: only the baseline", "suggest vegan run 1: only the candidate"]


# The blind file for Claude has the pairs without model names or seconds, the key says which model each A is,
# and the page carries the models only in its reveal data
def test_blind_file_and_page(tmp_path):
    _inputs(tmp_path)
    _write(tmp_path, "qwen2.5_7b", "qwen2.5:7b", [_record("en", "Base en", seconds=33)])
    _write(tmp_path, "qwen3.5_4b-think-off", "qwen3.5:4b", [_record("en", "Cand en", MISSING, seconds=12)], think=False)
    with patch("tools.compare_runs.MODELS_DIR", tmp_path):
        page, blind, unpaired = build_page("qwen2.5_7b", "qwen3.5_4b-think-off")
    name = pair_name("qwen2.5_7b", "qwen3.5_4b-think-off")
    text = blind.read_text(encoding="utf-8")
    assert "qwen" not in text and '"seconds"' not in text and unpaired == []
    assert json.loads(text)["pairs"][0]["id"] == "suggest|en|1"
    assert set(json.loads((tmp_path / "votes" / f"{name}__key.json").read_text()).values()) <= {"base", "cand"}
    html = page.read_text(encoding="utf-8")
    data = json.loads(html.split("const DATA = ", 1)[1].split(";\nconst store", 1)[0])
    assert data["reveal"]["base"] == "qwen2.5:7b" and data["reveal"]["cand"] == "qwen3.5:4b (think off)"
    assert "qwen" not in json.dumps(data["pairs"])
    assert {f for p in data["pairs"] for side in "AB" for f in p[side]["flags"]} == {"clean", "missing: Salmon"}


# The overview counts each model's clean samples, average seconds and errors per test, and marks a model whose
# outputs came from another prompt version than the baseline's
def test_overview_marks_other_prompt(tmp_path):
    _write(tmp_path, "base", "qwen2.5:7b", [_record("en", "A", seconds=30), _record("tr", "B", MISSING, seconds=10)])
    _write(tmp_path, "cand", "gemma3:4b", [_record("en", "C", seconds=8)], prompt="bbbbbbb")
    with patch("tools.compare_runs.MODELS_DIR", tmp_path):
        models = overview(["base", "cand"], "base")["models"]
    base, cand = (m["tests"]["suggest"] for m in models)
    assert (base["clean"], base["count"], base["seconds"], base["other_prompt"]) == (1, 2, 20, False)
    assert base["samples"]["tr"] == {"clean": False, "flags": ["missing: Salmon"], "seconds": 10}
    assert cand["other_prompt"] and models[1]["label"] == "gemma3:4b" and models[0]["baseline"]


# A plan reply shows as the plan the app builds from it, shopping as its two lists, and chat as one reply per message
def test_output_views():
    case = PLAN_CASES["boiled"]
    raw = {"dishes": [{"dish": "Egg sandwich", "steps": [{"action": "Boil the eggs", "minutes": 10, "hands_on": False}]}]}
    plan = output_view({"replies": {"plan": f"```json\n{json.dumps(raw)}\n```"}, "scores": {"plan": CLEAN}}, "plan", case)
    assert plan["text"].startswith("⏱ Plan (") and plan["clean"]
    items = json.dumps({"items": [{"name": "Feta", "reason": "Salty"}]})
    shop = output_view({"replies": {"suggest": items, "more": "oops"}, "scores": {"suggest": CLEAN, "more": MISSING}}, "shopping", None)
    assert shop["lists"][0]["items"] == [{"name": "Feta", "reason": "Salty"}] and shop["lists"][1]["raw"] == "oops"
    assert shop["flags"] == ["suggest: clean", "more: missing: Salmon"] and not shop["clean"]
    chat = output_view({"replies": {"leave_out": "Sure", "liked": "Nice"}, "scores": {}}, "chat", None)
    assert chat["replies"] == ["Sure", "Nice", None, None]
