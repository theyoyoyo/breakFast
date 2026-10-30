"""
Shared utilities used across the backend.
"""

import json
import re
from pathlib import Path
from typing import Optional


# Matches a fenced ```json ... ``` block in LLM output.
# Captures everything between the fences (not just first {...}) so nested
# objects/arrays are included.
_JSON_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```")

# A 7B model sometimes writes fractions as values ("amount": 1/4), which JSON doesn't allow
_FRACTION_RE = re.compile(r"(:\s*)(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?=\s*[,}\]])")


def _decimal(match: re.Match) -> str:
    numerator, denominator = float(match.group(2)), float(match.group(3))
    if not denominator:
        return match.group(0)
    return f"{match.group(1)}{round(numerator / denominator, 2):g}"


def repair_json_block(text: str) -> str:
    """The text with fractions in its ```json block written as decimals ("amount": 1/4 → 0.25),
    so the backend and the chat UI, which re-reads saved replies, can both parse it."""
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return text
    return text[:match.start(1)] + _FRACTION_RE.sub(_decimal, match.group(1)) + text[match.end(1):]


def replace_json_block(text: str, data: dict) -> str:
    """The text with its ```json block holding data instead."""
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return text
    return text[:match.start(1)] + json.dumps(data, ensure_ascii=False, indent=2) + text[match.end(1):]


def extract_json_block(text: str) -> Optional[dict]:
    """
    Extract and parse the first ```json ... ``` block from an LLM response.
    Returns the parsed dict, or None if not found or unparseable.
    """
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(_FRACTION_RE.sub(_decimal, match.group(1).strip()))
    except json.JSONDecodeError:
        return None


def resolve_static_file(root: Path, requested: str) -> Optional[Path]:
    """
    Resolve a URL path to a file inside root.
    Returns None if the file doesn't exist or resolves outside root
    (e.g. "../" or encoded "%2F" traversal).
    """
    root = root.resolve()
    try:
        candidate = (root / requested).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            return candidate
    except (OSError, ValueError):  # e.g. embedded null byte, name too long
        pass
    return None
