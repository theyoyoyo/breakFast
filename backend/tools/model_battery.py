"""Run the prompt test's model-comparison set for one model and think setting.

    python -m tools.model_battery qwen2.5:7b
    python -m tools.model_battery qwen3:8b --think off --url http://100.x.x.x:11434

It loads the model with the app's num_ctx, logs where Ollama put it (GPU or a CPU share,
from /api/ps), then runs each test in SUITES through tools.prompt_check with --model, --think
and a note naming both. Every test lands in tools/runs/ and history.jsonl as usual.
See docs/MODEL_TESTS.md.
"""

import argparse
import subprocess
import sys

import httpx

from config import OLLAMA_BASE_URL, OLLAMA_NUM_CTX

# What every model is tested on: (persona, extra options)
SUITES = [
    ("suggest", ["--samples", "all"]),
    ("suggest", ["--samples", "all", "--scenario", "chat"]),
    ("review", []),
    ("plan", []),
    ("shopping", ["--samples", "en,tr,vegan,diabetic"]),
    ("chat", ["--samples", "en,tr,student"]),
]


def load(url: str, model: str) -> str:
    """Load the model at the app's context length and say where it sits (GPU share, size)."""
    with httpx.Client(timeout=600.0) as client:
        client.post(f"{url}/api/generate", json={
            "model": model, "prompt": "", "options": {"num_ctx": OLLAMA_NUM_CTX},
        }).raise_for_status()
        for m in client.get(f"{url}/api/ps").json().get("models", []):
            if m.get("name") == model or m.get("model") == model:
                size, vram = m.get("size", 0), m.get("size_vram", 0)
                gpu = round(100 * vram / size) if size else 0
                return f"{model}: {size / 1e9:.1f} GB loaded, {gpu}% on the GPU, context {m.get('context_length', '?')}"
    return f"{model}: loaded, not listed by /api/ps"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the model-comparison tests for one model.")
    parser.add_argument("model", help="Ollama model tag, e.g. gemma3:4b")
    parser.add_argument("--think", choices=["on", "off"], help="Ollama's think field (default: none sent)")
    parser.add_argument("--url", default=OLLAMA_BASE_URL, help="Ollama address (default: OLLAMA_BASE_URL)")
    args = parser.parse_args(argv)

    print(load(args.url, args.model), flush=True)
    note = f"model {args.model}" + (f" think {args.think}" if args.think else "")
    extra = ["--model", args.model, "--url", args.url, "--note", note] + (["--think", args.think] if args.think else [])
    failed = 0
    for persona, options in SUITES:
        print(f"\n### {persona} {' '.join(options)}", flush=True)
        done = subprocess.run([sys.executable, "-m", "tools.prompt_check", "--persona", persona, *options, *extra])
        failed += done.returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
