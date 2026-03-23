"""
Shared utilities used across the backend.
"""

import json
import re
from typing import Optional


# Matches a fenced ```json ... ``` block in LLM output.
# Captures everything between the fences (not just first {...}) so nested
# objects/arrays are included.
_JSON_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```")


def extract_json_block(text: str) -> Optional[dict]:
    """
    Extract and parse the first ```json ... ``` block from an LLM response.
    Returns the parsed dict, or None if not found or unparseable.
    """
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None
