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

# Replies saved before the draft's schema may have fractions as values ("amount": 1/4), which JSON doesn't allow
_FRACTION_RE = re.compile(r"(:\s*)(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?=\s*[,}\]])")


def _decimal(match: re.Match) -> str:
    numerator, denominator = float(match.group(2)), float(match.group(3))
    if not denominator:
        return match.group(0)
    return f"{match.group(1)}{round(numerator / denominator, 2):g}"


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
